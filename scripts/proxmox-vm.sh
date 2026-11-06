#!/usr/bin/env bash
# Run on a Proxmox VE host. Creates a new Debian VM using the project's Compose file.
set -Eeuo pipefail
umask 077

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
ask() {
    local answer
    read -r -p "$1 [$2]: " answer </dev/tty
    printf '%s' "${answer:-$2}"
}
hash_ui_password() {
    python3 -c 'import hashlib,json,secrets,sys
password=sys.stdin.read()
if not 8 <= len(password) <= 1024: raise SystemExit("Use 8–1024 characters")
salt=secrets.token_bytes(16)
print(json.dumps({"version":1,"iterations":600000,"salt":salt.hex(),"digest":hashlib.pbkdf2_hmac("sha256",password.encode(),salt,600000).hex()}))'
}
validate_network() {
    python3 - "$1" "$2" "$3" <<'NET'
import ipaddress,sys
try:
    address=ipaddress.IPv4Interface(sys.argv[1]); gateway=ipaddress.IPv4Address(sys.argv[2])
    assert '/' in sys.argv[1] and 1 <= address.network.prefixlen <= 30
    assert address.ip not in (address.network.network_address,address.network.broadcast_address)
    assert gateway in address.network and gateway not in (address.ip,address.network.network_address,address.network.broadcast_address)
    servers=sys.argv[3].split(); assert servers
    for server in servers:
        value=ipaddress.IPv4Address(server)
        assert not value.is_unspecified and not value.is_multicast and not value.is_loopback
except (ValueError,AssertionError):
    raise SystemExit('Use an IPv4 address with /prefix, a different gateway in the same subnet, and IPv4 DNS servers separated by spaces.')
NET
}
configure_network() {
    cidr=$(ask 'VM IPv4 address/mask (example: 192.168.1.50/24; empty = DHCP)' '')
    if [[ -z $cidr ]]; then
        network_mode=dhcp
        ipconfig=ip=dhcp
        dns=''
    else
        network_mode=static
        gateway=$(ask 'IPv4 gateway (example: 192.168.1.1)' '')
        dns=$(ask 'DNS IPv4 addresses, separated by spaces' '1.1.1.1 9.9.9.9')
        validate_network "$cidr" "$gateway" "$dns"
        cidr=$(python3 -c 'import ipaddress,sys; print(ipaddress.IPv4Interface(sys.argv[1]))' "$cidr")
        ipconfig="ip=$cidr,gw=$gateway"
    fi
}

json_field() { python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1"; }
require_number() {
    [[ $2 =~ ^[0-9]+$ && ${#2} -le 9 ]] || fail "$1 must be a number."
    (( 10#$2 >= $3 && 10#$2 <= $4 )) || fail "$1 must be between $3 and $4."
}

verify_image() {
python3 - "$1" "$2" <<'PY'
from pathlib import Path
import hashlib,re,sys
root=Path(sys.argv[1]); name=sys.argv[2]
checks=[line.split() for line in (root/'SHA512SUMS').read_text().splitlines()]
checks=[parts[0] for parts in checks if len(parts)==2 and parts[1].lstrip('*').removeprefix('./')==name]
if len(checks)!=1 or not re.fullmatch('[a-fA-F0-9]{128}',checks[0]):
    raise SystemExit('Missing or ambiguous Debian image checksum')
with (root/name).open('rb') as stream: digest=hashlib.file_digest(stream,'sha512').hexdigest()
if digest.lower()!=checks[0].lower(): raise SystemExit('Debian image checksum mismatch')
PY
}

build_cloud_config() {
python3 - "$1" "$2" "$3" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1]); name=sys.argv[2]; password_hash=sys.argv[3]
user={'name':'root','lock_passwd':False,'hashed_passwd':password_hash,'shell':'/bin/bash'}
key=(root/'authorized-key').read_text().strip()
if key: user['ssh_authorized_keys']=[key]
unit='''[Unit]
Description=Install Solarman Hub
Wants=network-online.target
After=network-online.target cloud-final.service
ConditionPathExists=!/var/lib/solarman-hub/ready.json
StartLimitIntervalSec=0
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/solarman-hub-install
TimeoutStartSec=0
Restart=on-failure
RestartSec=60
[Install]
WantedBy=multi-user.target
'''
config={'hostname':name,'manage_etc_hosts':True,'disable_root':False,'ssh_pwauth':False,
 'users':[user],'chpasswd':{'expire':False},
 'write_files':[{'path':'/usr/local/sbin/solarman-hub-install','permissions':'0700','content':(root/'bootstrap').read_text()},
 {'path':'/etc/systemd/system/solarman-hub-install.service','permissions':'0644','content':unit}]+(
 [{'path':'/root/solarman-hub-ui-password.json','permissions':'0600','content':(root/'ui-password.json').read_text()}]
 if (root/'ui-password.json').exists() else []),
 'runcmd':[['systemctl','daemon-reload'],['systemctl','enable','--now','--no-block','solarman-hub-install.service']]}
(root/'user-data.yaml').write_text('#cloud-config\n'+json.dumps(config,indent=2)+'\n')
PY
}

main() {
[[ ${1:-} == --help ]] && {
    cat <<'HELP'
Solarman Hub VM installer — run as root on a Proxmox VE 8/9 amd64 host.
Interactive choices: unused VM ID, name, disk storage, snippet directory storage,
LAN bridge/VLAN, DHCP or static IPv4, CPU, memory, disk, SSH key and web password.
Creates a fresh Debian 13 cloud VM with Docker and the existing Hub Compose file.
Requires Internet; choose DHCP or static IPv4 and a web-panel password. Does not configure the logger.
HELP
    exit 0
}
[[ $# == 0 ]] || fail 'Use --help or run without arguments.'
[[ $EUID == 0 ]] || fail 'Run this script as root on the Proxmox host.'
[[ $(uname -m) == x86_64 ]] || fail 'Only amd64 Proxmox hosts are supported.'
for tool in qm pvesm pvesh pveversion python3 wget openssl qemu-img ip sha512sum; do
    command -v "$tool" >/dev/null || fail "Required command is missing: $tool"
done
version=$(pveversion)
[[ $version =~ ^pve-manager/(8|9)\. ]] || fail 'This installer supports Proxmox VE 8 and 9.'
[[ -r /dev/tty ]] || fail 'An interactive terminal is required.'

work=$(mktemp -d /tmp/solarman-hub-vm.XXXXXX)
created=0
cleanup() {
    local result=$?
    rm -rf -- "$work"
    if (( result != 0 && created == 1 )); then
        printf '\nInstallation stopped. VM %s was kept for inspection; no VM was deleted.\n' "$vmid" >&2
        printf 'Console: qm terminal %s\nGuest install log: journalctl -u solarman-hub-install\n' "$vmid" >&2
    fi
}
trap cleanup EXIT

printf '\nSolarman Hub — Debian 13 VM + Docker\n\n'
pvesm status --content images
storage_default=$(pvesm status --content images | awk 'NR>1 && $3=="active" {print $1; exit}')
[[ -n $storage_default ]] || fail 'No active storage supports VM disks.'
vmid=$(ask 'New VM ID' "$(pvesh get /cluster/nextid)")
require_number 'VM ID' "$vmid" 100 999999999
vmid=$((10#$vmid))
pvesh get /cluster/resources --type vm --output-format json > "$work/vms.json"
python3 - "$vmid" "$work/vms.json" <<'PY' || fail 'That VM ID is already in use.'
import json,sys
sys.exit(any(int(row['vmid']) == int(sys.argv[1]) for row in json.load(open(sys.argv[2]))))
PY
name=$(ask 'VM name' solarman-hub)
[[ $name =~ ^[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$ ]] || fail 'Use a hostname containing letters, digits and hyphens.'
storage=$(ask 'VM disk storage' "$storage_default")
[[ $storage =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || fail 'Invalid storage name.'
pvesm status --content images | awk -v id="$storage" '$1==id && $3=="active" {found=1} END {exit !found}' || fail 'Selected disk storage is unavailable.'
snippets=$(ask 'Directory storage for cloud-init snippets' local)
[[ $snippets =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || fail 'Invalid snippet storage name.'
snippet_config=$(pvesh get "/storage/$snippets" --output-format json)
[[ $(json_field type <<< "$snippet_config") == dir ]] || fail 'Choose a directory (dir) storage for snippets.'
snippet_root=$(json_field path <<< "$snippet_config")
[[ $snippet_root == /* && -d $snippet_root ]] || fail 'Snippet storage path is not mounted.'
pvesm status | awk -v id="$snippets" '$1==id && $3=="active" {found=1} END {exit !found}' || fail 'Snippet storage is not active on this node.'
content=$(json_field content <<< "$snippet_config")
bridge=$(ask 'LAN bridge' vmbr0)
[[ $bridge =~ ^[A-Za-z0-9_.-]+$ ]] || fail 'Invalid bridge name.'
ip -j -d link show dev "$bridge" | python3 -c 'import json,sys; rows=json.load(sys.stdin); sys.exit(not rows or rows[0].get("linkinfo",{}).get("info_kind")!="bridge")' || fail 'Choose an existing Linux bridge.'
vlan=$(ask 'VLAN tag (0 = untagged)' 0)
require_number 'VLAN' "$vlan" 0 4094
configure_network
cores=$(ask 'vCPU' 2); require_number 'vCPU' "$cores" 1 64
memory=$(ask 'Memory in MB' 2048); require_number 'Memory' "$memory" 2048 1048576
disk=$(ask 'Disk size in GB' 20); require_number 'Disk' "$disk" 20 1048576
key=$(ask 'SSH public key file (none = console access only)' none)
if [[ $key != none ]]; then
    [[ -f $key ]] || fail 'SSH public key file not found.'
    command -v ssh-keygen >/dev/null || fail 'ssh-keygen is required to validate the public key.'
    ssh-keygen -l -f "$key" >/dev/null || fail 'Not a valid SSH public key.'
    [[ $(wc -l < "$key") -le 1 ]] || fail 'Use a file containing one public key.'
    cp -- "$key" "$work/authorized-key"
else
    : > "$work/authorized-key"
fi
printf '\nChoose the Hub web-panel password (8–1024 characters). It is stored only as a salted hash.\n'
while true; do
    read -r -s -p 'Web password: ' ui_password </dev/tty; printf '\n' >&2
    read -r -s -p 'Repeat web password: ' ui_repeat </dev/tty; printf '\n' >&2
    if [[ $ui_password != "$ui_repeat" ]]; then
        printf 'Passwords do not match. Try again.\n' >&2
    elif printf '%s' "$ui_password" | hash_ui_password > "$work/ui-password.json"; then
        break
    fi
done
unset ui_password ui_repeat
access="/root/solarman-hub-${vmid}-access.txt"
[[ ! -e $access ]] || fail "Access file already exists: $access"
snippet_file="solarman-hub-${vmid}.yaml"
[[ ! -e $snippet_root/snippets/$snippet_file ]] || fail 'A snippet with that VM ID already exists.'

printf '\nVM: %s (%s), %s vCPU, %s MB RAM, %s GB on %s\n' "$vmid" "$name" "$cores" "$memory" "$disk" "$storage"
printf 'Network: %s, VLAN %s, %s; panel TCP 8080, logger TCP 10000\n' "$bridge" "$vlan" "$ipconfig"
[[ -z $dns ]] || printf 'DNS: %s\n' "$dns"
printf 'Web login: the password you just chose.\n'
printf 'Cloud-init snippet: %s:snippets/%s\n' "$snippets" "$snippet_file"
if [[ ,$content, != *,snippets,* ]]; then
    printf 'The snippets content type will be added to %s; existing content types are preserved.\n' "$snippets"
fi
printf 'Debian and Hub dependencies will be downloaded from the Internet.\n'
read -r -p 'Create this VM? [y/N]: ' answer </dev/tty
[[ $answer == y || $answer == Y ]] || { printf 'Cancelled.\n'; exit 0; }

image=debian-13-genericcloud-amd64.qcow2
image_base=https://cloud.debian.org/images/cloud/trixie/latest
printf '\nDownloading the official Debian cloud image and its SHA-512 checksum…\n'
wget -q --timeout=30 --tries=3 -O "$work/$image" "$image_base/$image"
wget -q --timeout=30 --tries=3 -O "$work/SHA512SUMS" "$image_base/SHA512SUMS"
verify_image "$work" "$image"
[[ $(qemu-img info --output=json "$work/$image" | json_field format) == qcow2 ]] || fail 'Expected a qcow2 cloud image.'

# This bootstrap runs only inside the new VM. Reuse compose.yaml rather than
# maintaining a second container definition or a separate installer image.
cat > "$work/bootstrap" <<'GUEST'
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export DEBIAN_FRONTEND=noninteractive
state=/var/lib/solarman-hub
mkdir -p "$state"
[[ ! -f $state/ready.json ]] || exit 0
apt-get update
apt-get install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl openssh-server
systemctl enable --now docker
systemctl start qemu-guest-agent
mkdir -p /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/00-solarman-hub.conf <<'SSH'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
SSH
systemctl restart ssh
if [[ ! -d /opt/solarman-hub/.git ]]; then
    checkout=$(mktemp -d /opt/solarman-hub-checkout.XXXXXX)
    trap 'rm -rf -- "$checkout"' EXIT
    git clone --depth 1 --branch main https://github.com/ordigital/solarman-hub.git "$checkout"
    mv -- "$checkout" /opt/solarman-hub
    trap - EXIT
fi
cd /opt/solarman-hub
docker compose build hub
if [[ -f /root/solarman-hub-ui-password.json ]]; then
    docker compose run --rm --no-deps -T hub solarman-hub password --data-dir /data --hash-stdin < /root/solarman-hub-ui-password.json
    rm /root/solarman-hub-ui-password.json
fi
docker compose up -d --wait --wait-timeout 180
curl --fail --silent http://127.0.0.1:8080/health >/dev/null
python3 - <<'PY'
import json,pathlib,socket
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
    sock.connect(('1.1.1.1',80))
    address=sock.getsockname()[0]
path=pathlib.Path('/var/lib/solarman-hub/ready.json')
path.write_text(json.dumps({'ip':address,'web_port':8080,'logger_port':10000})+'\n')
PY
printf 'Solarman Hub is ready. Get the administrator token with:\n'
printf 'cd /opt/solarman-hub && docker compose exec hub solarman-hub token --data-dir /data\n'
GUEST
password=$(openssl rand -hex 16)
password_hash=$(printf '%s' "$password" | openssl passwd -6 -stdin)
# JSON is valid YAML: serialization keeps passwords, keys and script text out of
# shell interpolation and produces a single self-contained cloud-init snippet.
build_cloud_config "$work" "$name" "$password_hash"
if [[ ,$content, != *,snippets,* ]]; then
    pvesm set "$snippets" --content "${content:+$content,}snippets"
fi
mkdir -p -- "$snippet_root/snippets"
# Refuse concurrent overwrites of an existing VM's configuration/credentials.
(set -o noclobber; cat "$work/user-data.yaml" > "$snippet_root/snippets/$snippet_file")
(set -o noclobber; cat > "$access" <<ACCESS
Solarman Hub VM $vmid ($name)
Local console: qm terminal $vmid
Console username: root
Console password: $password
SSH password login is disabled; SSH uses the supplied public key, if any.
Web login: use the password you chose in the installer (not saved here).
Recovery token (run on the Proxmox host):
qm guest exec $vmid -- /usr/bin/docker compose --project-directory /opt/solarman-hub exec -T hub solarman-hub token --data-dir /data
Guest install log: journalctl -u solarman-hub-install
Guest retry: systemctl restart solarman-hub-install
Cloud-init snippet: $snippets:snippets/$snippet_file
ACCESS
)
unset password password_hash
net="virtio,bridge=$bridge"
(( 10#$vlan == 0 )) || net+=",tag=$((10#$vlan))"
qm create "$vmid" --name "$name" --memory "$((10#$memory))" --cores "$((10#$cores))" \
    --ostype l26 --scsihw virtio-scsi-pci --net0 "$net" --serial0 socket --vga serial0 \
    --agent enabled=1 --onboot 1
created=1
qm set "$vmid" --scsi0 "$storage:0,import-from=$work/$image,discard=on"
qm resize "$vmid" scsi0 "$((10#$disk))G"
qm set "$vmid" --ide2 "$storage:cloudinit" --boot order=scsi0 \
    --ipconfig0 "$ipconfig" --cicustom "user=$snippets:snippets/$snippet_file"
[[ -z $dns ]] || qm set "$vmid" --nameserver "$dns"
qm start "$vmid"
printf '\nVM %s started. Installation continues inside Debian (usually several minutes).\n' "$vmid"
printf 'Console password and token command: %s (root-only file).\n' "$access"
printf 'Waiting up to 15 minutes; Ctrl+C stops waiting and leaves the VM running.\n'
deadline=$((SECONDS+900))
while (( SECONDS < deadline )); do
    if response=$(qm guest exec "$vmid" --timeout 10 -- /bin/cat /var/lib/solarman-hub/ready.json 2>/dev/null); then
        if address=$(python3 -c 'import ipaddress,json,sys; r=json.load(sys.stdin); assert r.get("exitcode")==0; print(ipaddress.IPv4Address(json.loads(r["out-data"])["ip"]))' <<< "$response" 2>/dev/null); then
            printf '\nReady: http://%s:8080\nLogger destination: %s:10000 (TCP)\n' "$address" "$address"
            printf 'Panel: http://%s:8080\nLogger destination: %s:10000 (TCP)\n' "$address" "$address" >> "$access"
            if [[ $network_mode == dhcp ]]; then
                printf 'Reserve the VM address in DHCP before configuring the logger.\n'
            fi
            printf 'Sign in with the web password you chose during installation.\n'
            printf 'Read %s for the console password and administrator-token command.\n' "$access"
            exit 0
        fi
    fi
    sleep 10
done
printf '\nThe VM is running, but installation has not yet confirmed readiness.\n'
printf 'Open qm terminal %s and inspect journalctl -u solarman-hub-install.\n' "$vmid"
printf 'The installer retries failed guest installation automatically every minute.\n'
printf 'Access details: %s\n' "$access"
exit 1

}

if [[ ${BASH_SOURCE[0]:-$0} == "$0" ]]; then
    main "$@"
fi
