"""Validate provisioning data without creating or altering a Proxmox VM."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/proxmox-vm.sh'


def test_installer_starts_with_bash_c_and_still_supports_sourcing():
    result = subprocess.run(
        ['bash', '-c', SCRIPT.read_text(), 'bash', '--help'],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'Solarman Hub VM installer' in result.stdout
    sourced = subprocess.run(
        ['bash', '-c', 'source "$1"; printf "sourced safely"', 'test', str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert sourced.returncode == 0, sourced.stderr
    assert sourced.stdout == 'sourced safely'


def invoke(function, *args):
    return subprocess.run(
        ['bash', '-c', 'source "$1"; shift; "$@"', 'test', str(SCRIPT), function, *map(str, args)],
        capture_output=True, text=True,
    )


def test_cloud_init_preserves_keys_and_script_without_shell_interpolation(tmp_path):
    bootstrap = '#!/bin/bash\nprintf "%s" "$(do-not-execute)"\n'
    key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest example@example'
    (tmp_path / 'bootstrap').write_text(bootstrap)
    (tmp_path / 'authorized-key').write_text(key + '\n')
    password_hash = '$6$salt$example'
    result = invoke('build_cloud_config', tmp_path, 'solarman-hub', password_hash)
    assert result.returncode == 0, result.stderr
    output = (tmp_path / 'user-data.yaml').read_text()
    assert output.startswith('#cloud-config\n')
    config = json.loads(output.split('\n', 1)[1])
    assert config['ssh_pwauth'] is False
    assert config['users'] == [{'name': 'root', 'lock_passwd': False,
                               'hashed_passwd': password_hash, 'shell': '/bin/bash',
                               'ssh_authorized_keys': [key]}]
    files = {entry['path']: entry for entry in config['write_files']}
    assert files['/usr/local/sbin/solarman-hub-install']['content'] == bootstrap
    unit = files['/etc/systemd/system/solarman-hub-install.service']['content']
    assert 'After=network-online.target cloud-final.service' in unit
    assert 'Restart=on-failure' in unit
    # Starting asynchronously lets cloud-final finish before the unit runs.
    assert config['runcmd'][-1][-2:] == ['--no-block', 'solarman-hub-install.service']
    subprocess.run(['bash', '-n', str(SCRIPT)], check=True)


def test_cloud_init_console_access_without_ssh_key(tmp_path):
    (tmp_path / 'bootstrap').write_text('#!/bin/bash\ntrue\n')
    (tmp_path / 'authorized-key').write_text('')
    assert invoke('build_cloud_config', tmp_path, 'solarman-hub', '$6$hash').returncode == 0
    config = json.loads((tmp_path / 'user-data.yaml').read_text().split('\n', 1)[1])
    assert 'ssh_authorized_keys' not in config['users'][0]
    assert config['chpasswd']['expire'] is False


def test_debian_image_checksum_rejects_corruption_and_ambiguous_entries(tmp_path):
    image = 'debian-13-genericcloud-amd64.qcow2'
    (tmp_path / image).write_bytes(b'synthetic cloud image')
    digest = hashlib.sha512((tmp_path / image).read_bytes()).hexdigest()
    sums = tmp_path / 'SHA512SUMS'
    sums.write_text(f'{digest}  {image}\n')
    assert invoke('verify_image', tmp_path, image).returncode == 0
    (tmp_path / image).write_bytes(b'corrupted')
    assert invoke('verify_image', tmp_path, image).returncode != 0
    sums.write_text(f'{digest}  {image}\n{digest}  {image}\n')
    assert invoke('verify_image', tmp_path, image).returncode != 0
    sums.write_text(f'{digest}  different-image.qcow2\n')
    assert invoke('verify_image', tmp_path, image).returncode != 0


@pytest.mark.parametrize('value', ['0', '19', '1000000000', '-1', '$(false)', '20G'])
def test_invalid_disk_sizes_are_rejected(value):
    assert invoke('require_number', 'Disk', value, 20, 1048576).returncode != 0


def test_installer_password_hash_matches_hub_auth():
    from solarman_hub.auth import check_password, validate_password_record
    password = 'test1234'
    result = subprocess.run(
        ['bash', '-c', 'source "$1"; hash_ui_password', 'test', str(SCRIPT)],
        input=password, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    record = validate_password_record(json.loads(result.stdout))
    assert check_password(password, record)
    assert password not in result.stdout


@pytest.mark.parametrize(('address', 'gateway', 'dns', 'valid'), [
    ('192.168.1.50/24', '192.168.1.1', '192.168.1.1 9.9.9.9', True),
    ('192.168.1.50', '192.168.1.1', '1.1.1.1', False),
    ('192.168.1.0/24', '192.168.1.1', '1.1.1.1', False),
    ('192.168.1.255/24', '192.168.1.1', '1.1.1.1', False),
    ('192.168.1.50/24', '192.168.2.1', '1.1.1.1', False),
    ('192.168.1.50/24', '192.168.1.50', '1.1.1.1', False),
    ('192.168.1.50/24', '192.168.1.1', '1.1.1.1;false', False),
])
def test_static_network_validation(address, gateway, dns, valid):
    assert (invoke('validate_network', address, gateway, dns).returncode == 0) is valid


@pytest.mark.parametrize('address', ['', '192.168.1.50/24', '192.168.1.50/255.255.255.0'])
def test_single_network_question_selects_dhcp_or_static(tmp_path, address):
    prompts = tmp_path / 'prompts'
    result = subprocess.run(
        ['bash', '-c', '''source "$1"
ask() {
    printf '%s\\n' "$1" >> "$PROMPTS"
    case "$1" in
        'VM IPv4'*) printf '%s' "$ADDRESS" ;;
        'IPv4 gateway'*) printf '192.168.1.1' ;;
        'DNS IPv4'*) printf '1.1.1.1 9.9.9.9' ;;
        *) exit 1 ;;
    esac
}
configure_network
printf '%s\\n' "$ipconfig" "$dns"
''', 'test', str(SCRIPT)],
        env={**os.environ, 'ADDRESS': address, 'PROMPTS': str(prompts)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    questions = prompts.read_text().splitlines()
    if address:
        assert result.stdout.splitlines() == ['ip=192.168.1.50/24,gw=192.168.1.1', '1.1.1.1 9.9.9.9']
        assert len(questions) == 3
    else:
        assert result.stdout.splitlines() == ['ip=dhcp', '']
        assert len(questions) == 1
