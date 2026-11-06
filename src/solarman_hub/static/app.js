"use strict";
const { t } = I18n;
const $ = (id) => document.getElementById(id);
const state = {
  csrf: "",
  config: null,
  revision: "",
  profiles: [],
  status: null,
  events: [],
  view: "dashboard",
  selectedProfile: null,
};
const titles = {
  dashboard: "Overview",
  settings: "Configuration",
  profiles: "Decoder profiles",
  logs: "Logs and archive",
  help: "User guide",
  devices: "Devices",
  firmware: "ESP32 / Flashing",
};
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
function toast(text, error = false) {
  $("toast").textContent = text;
  $("toast").className = error ? "is-error" : "";
  $("toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($("toast").hidden = true), 6500);
}
async function api(path, method = "GET", body) {
  const response = await fetch("/api/" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      $("app").hidden = true;
      $("login-screen").hidden = false;
    }
    throw Error(
      t(data.error || data.message || response.statusText || `HTTP ${response.status}`) +
        (data.details
          ? " · " +
            data.details.map((x) => x.field + ": " + x.message).join("; ")
          : ""),
    );
  }
  return data;
}
function action(fn) {
  return async (event) => {
    event?.preventDefault();
    const button = event?.currentTarget;
    if (button?.tagName === "BUTTON") button.disabled = true;
    try {
      await fn(event);
    } catch (error) {
      toast(error.message, true);
    } finally {
      if (button?.tagName === "BUTTON") button.disabled = false;
    }
  };
}
function getPath(obj, path) {
  return path.split(".").reduce((v, k) => v[k], obj);
}
function setPath(obj, path, value) {
  const parts = path.split(".");
  const last = parts.pop();
  parts.reduce((v, k) => v[k], obj)[last] = value;
}
function date(value) {
  return value
    ? new Date(typeof value === "number" ? value * 1000 : value).toLocaleString(
        I18n.locale,
      )
    : "—";
}
async function loadConfig() {
  const result = await api("config");
  state.config = result.config;
  state.revision = result.revision;
  document.querySelectorAll("[data-config]").forEach((input) => {
    const value = getPath(state.config, input.dataset.config);
    if (input.type === "checkbox") input.checked = value;
    else input.value = value;
  });
  $("mqtt-password").value = "";
  $("clear-mqtt-password").checked = false;
  $("mqtt-password-state").textContent = state.config.mqtt.password_set
    ? t("A password is saved. Leave blank to keep it.")
    : t("No password saved.");
  $("config-revision").textContent = t("Saved revision: {revision}", {
    revision: state.revision,
  });
  renderLoggerEditor();
}
async function loadProfiles() {
  state.profiles = (await api("profiles")).profiles;
  renderProfileList();
}
function profileSelect(value) {
  const select = node("select");
  select.append(new Option(t("Forward only"), ""));
  for (const p of state.profiles) select.append(new Option(p.name, p.id));
  select.value = value || "";
  return select;
}
function editorField(title, key, value, type = "text") {
  const label = node("label", title);
  const input = node("input");
  input.type = type;
  input.dataset.logger = key;
  if (type === "checkbox") input.checked = value;
  else input.value = value ?? "";
  if (type === "number") {
    input.min = key === "serial" ? 1 : 30;
    input.max = key === "serial" ? 4294967295 : 86400;
  }
  label.append(input);
  return label;
}
function renderLoggerEditor() {
  const root = $("logger-editor");
  root.replaceChildren();
  for (const logger of state.config.loggers) {
    const row = node("div", undefined, "logger-edit-row field-grid");
    row.append(
      editorField(t("Logger serial number"), "serial", logger.serial, "number"),
      editorField(t("Name"), "name", logger.name),
      editorField(t("Allowed IP (optional)"), "allowed_ip", logger.allowed_ip),
    );
    const label = node("label", t("Profile"));
    const select = profileSelect(logger.profile);
    select.dataset.logger = "profile";
    label.append(select);
    row.append(
      label,
      editorField(
        t("Stale after (s)"),
        "stale_after",
        logger.stale_after,
        "number",
      ),
      editorField(t("Enabled logger"), "enabled", logger.enabled, "checkbox"),
    );
    const remove = node("button", t("Remove logger"), "button danger");
    remove.type = "button";
    remove.onclick = () => row.remove();
    row.append(remove);
    root.append(row);
  }
}
function readConfig() {
  const result = structuredClone(state.config);
  delete result.mqtt.password_set;
  document
    .querySelectorAll("[data-config]")
    .forEach((input) =>
      setPath(
        result,
        input.dataset.config,
        input.type === "checkbox"
          ? input.checked
          : input.type === "number" || input.hasAttribute("data-number")
            ? Number(input.value)
            : input.value,
      ),
    );
  if ($("mqtt-password").value) result.mqtt.password = $("mqtt-password").value;
  if ($("clear-mqtt-password").checked) result.mqtt.clear_password = true;
  result.loggers = [...document.querySelectorAll(".logger-edit-row")].map(
    (row) => {
      const logger = { protocol: "solarman-v5" };
      row
        .querySelectorAll("[data-logger]")
        .forEach(
          (input) =>
            (logger[input.dataset.logger] =
              input.type === "checkbox"
                ? input.checked
                : input.type === "number"
                  ? Number(input.value)
                  : input.dataset.logger === "profile"
                    ? input.value || null
                    : input.value),
        );
      return logger;
    },
  );
  return result;
}
async function saveConfig() {
  const result = await api("config", "PUT", {
    revision: state.revision,
    config: readConfig(),
  });
  state.revision = result.revision;
  await loadConfig();
  await refresh();
  toast(t("Configuration saved. Apply it to switch sessions."));
}
async function apply() {
  await api("apply", "POST", {});
  await refresh();
  toast(t("Configuration applied. The logger may take a moment to reconnect."));
}
function renderStatus() {
  if (state.status) $("app-version").textContent = "Solarman V5 · v" + state.status.version;
  const s = state.status;
  if (!s) return;
  $("pending-banner").hidden = s.saved_revision === s.applied_revision;
  $("restart-banner").hidden = !s.restart_required;
  $("footer-revision").textContent = t("Saved: {saved} · Active: {applied}", {
    saved: s.saved_revision,
    applied: s.applied_revision,
  });
  $("server-address").textContent =
    "TCP " + s.listener.host + ":" + s.listener.port;
  const enabled = s.loggers.filter((l) => l.enabled);
  $("stat-loggers").replaceChildren(
    document.createTextNode(enabled.filter((l) => l.connected).length),
    node("span", "/ " + enabled.length),
  );
  $("stat-fresh").textContent = t("Current readings: {count}", {
    count: enabled.filter((l) => l.fresh).length,
  });
  $("stat-cloud").textContent = !s.cloud.enabled
    ? t("Disabled")
    : s.loggers.some((l) => l.cloud_connected)
      ? t("Connected")
      : t("Waiting");
  $("cloud-address").textContent = s.cloud.host + ":" + s.cloud.port;
  $("stat-mqtt").textContent = !s.mqtt.enabled
    ? t("Disabled")
    : s.mqtt.connected
      ? t("Connected")
      : t("Disconnected");
  $("mqtt-detail").textContent =
    s.mqtt.last_error || t("MQTT Discovery · local sensors");
  $("stat-archive").textContent = s.archive.last_error
    ? t("Write error")
    : t("Ready");
  $("archive-detail").textContent = t(
    "Queued: {queued} · Dropped: {dropped}",
    s.archive,
  );
  const cards = $("logger-cards");
  cards.replaceChildren();
  if (!s.loggers.length)
    cards.append(
      node("p", t("Add your first logger in Configuration."), "empty-note"),
    );
  for (const logger of s.loggers) {
    const card = node("article", undefined, "card");
    card.append(
      node("h3", logger.name),
      node("p", "SN " + logger.serial, "muted small"),
      node(
        "span",
        !logger.enabled
          ? t("Logger disabled")
          : logger.fresh
            ? t("Current readings")
            : logger.connected
              ? t("Connected · awaiting a measurement")
              : t("Not connected"),
        "tag "+(logger.enabled&&logger.connected?"status-good":"status-bad"),
      ),
      node(
        "p",
        t("Last received: {time}", { time: date(logger.last_frame_at) }),
        "small",
      ),
      node(
        "p",
        t("Cloud: {status}", {
          status: logger.cloud_connected ? t("connected") : t("disconnected"),
        }),
        "small",
      ),
    );
    if (logger.decode_error)
      card.append(node("p", logger.decode_error, "error small"));
    const button = node("button", t("Reconnect"), "button quiet");
    button.onclick = action(async () => {
      await api("loggers/" + logger.serial + "/reconnect", "POST", {});
      toast(t("Session closed. Waiting for the logger."));
    });
    card.append(button);
    cards.append(card);
  }
  const selected = $("measurement-logger").value;
  $("measurement-logger").replaceChildren(
    ...s.loggers.map((l) => new Option(l.name + " · " + l.serial, l.serial)),
  );
  if (s.loggers.some((l) => String(l.serial) === selected))
    $("measurement-logger").value = selected;
  renderMeasurements();
  DevicesUI.render(s,state.profiles);
  const h=s.history;
  if(h)$("history-storage-status").textContent=t('History: {size} MB · queued: {queued} · dropped: {dropped}',{size:(h.size_bytes/1048576).toFixed(1),queued:h.queued,dropped:h.dropped})+(h.last_error?' · '+h.last_error:'');
  $("stat-cloud").classList.toggle('state-good',s.cloud.enabled&&s.loggers.some(l=>l.cloud_connected));
  $("stat-cloud").classList.toggle('state-bad',!s.cloud.enabled||!s.loggers.some(l=>l.cloud_connected));
  $("stat-mqtt").classList.toggle('state-good',s.mqtt.enabled&&s.mqtt.connected);
  $("stat-mqtt").classList.toggle('state-bad',!s.mqtt.enabled||!s.mqtt.connected);
  $("stat-archive").classList.toggle('state-good',!s.archive.last_error);
  $("stat-archive").classList.toggle('state-bad',Boolean(s.archive.last_error));
}
function latestSample() {
  return state.status?.loggers.find(l=>String(l.serial)===$("measurement-logger").value)?.latest;
}
function renderMeasurements() {
  const logger = state.status?.loggers.find(
    (l) => String(l.serial) === $("measurement-logger").value,
  );
  const sample = HistoryUI.sample();
  const filter = $("measurement-filter").value.toLowerCase();
  const values = Object.entries(sample?.values || {}).filter(([id, v]) =>
    (id + " " + v.name).toLowerCase().includes(filter),
  );
  const body = $("measurements-body");
  body.replaceChildren();
  for (const [id, value] of values) {
    const row = node("tr");
    const label = node("td");
    const button=node("button",value.name,"parameter-link");
    button.type="button";button.onclick=()=>HistoryUI.open(id);label.append(button);
    label.append(node("small", id));
    row.append(
      label,
      node(
        "td",
        new Intl.NumberFormat(I18n.locale, { maximumFractionDigits: 6 }).format(
          value.value,
        ),
      ),
      node("td", value.unit || "—"),
      node("td", String(value.raw)),
    );
    body.append(row);
  }
  $("measurement-count").textContent = t("Fields: {count}", {
    count: values.length,
  });
  $("measurement-empty").hidden = Boolean(sample);
  $("measurement-time").textContent = sample
    ? t("Sample time: {sample} · Received: {received}", {
        sample: date(sample.sample_time),
        received: date(sample.received_at),
      })
    : t("Waiting for a matching report.");
}
function renderProfileList() {
  const list = $("profile-list");
  list.replaceChildren();
  for (const profile of state.profiles) {
    const button = node("button", profile.name, "nav-item");
    button.onclick = () => selectProfile(profile);
    list.append(button);
  }
  if (!state.selectedProfile && state.profiles.length)
    selectProfile(state.profiles[0]);
}
function selectProfile(profile) {
  state.selectedProfile = profile;
  const document = structuredClone(profile);
  delete document.builtin;
  delete document.revision;
  $("profile-json").value = JSON.stringify(document, null, 2);
  $("profile-json").readOnly = Boolean(profile.builtin);
  $("profile-title").textContent = profile.name;
  $("profile-description").textContent = profile.description || "";
  $("profile-badge").textContent = profile.builtin
    ? t("Built-in · read only")
    : t("Custom profile");
  $("save-profile").disabled = Boolean(profile.builtin);
  $("delete-profile").disabled =
    Boolean(profile.builtin) ||
    !state.profiles.some((p) => p.id === profile.id);
}
function renderEvents() {
  const filter = $("log-filter").value.toLowerCase();
  const level = $("log-level").value;
  const events = state.events
    .filter(
      (e) =>
        (!level || e.level === level) &&
        JSON.stringify(e).toLowerCase().includes(filter),
    )
    .reverse();
  $("logs-body").replaceChildren(
    ...events.map((event) => {
      const row = node("tr");
      const detail = { ...event };
      delete detail.time;
      delete detail.event;
      delete detail.level;
      row.append(
        node("td", date(event.time)),
        node("td", event.level || "info"),
        node("td", event.event),
        node("td", JSON.stringify(detail)),
      );
      return row;
    }),
  );
  $("logs-empty").hidden = events.length > 0;
}
async function refresh() {
  state.status = await api("status");
  renderStatus();
  if (state.view === "logs") {
    state.events = (await api("events")).events;
    renderEvents();
  }
}
async function setView(view) {
  if (!titles[view]) view = "dashboard";
  state.view = view;
  for (const key of Object.keys(titles)) $("view-" + key).hidden = key !== view;
  document
    .querySelectorAll("[data-view]")
    .forEach((button) =>
      button.classList.toggle("active", button.dataset.view === view),
    );
  $("page-title").textContent = t(titles[view]);
  if (view === "help") await GuideUI.load(api);
  if (view === "firmware") await GuideUI.loadFirmware(api);
  if (view === "logs") {
    state.events = (await api("events")).events;
    renderEvents();
  }
  location.hash = view;
  window.scrollTo(0, 0);
}
async function enter() {
  await loadProfiles();
  await loadConfig();
  $("login-screen").hidden = true;
  $("app").hidden = false;
  await setView(location.hash.slice(1) || "dashboard");
  await refresh();
}
$("login-form").onsubmit = async (event) => {
  event.preventDefault();
  try {
    state.csrf = (
      await api("login", "POST", { token: $("admin-token").value })
    ).csrf;
    $("admin-token").value = "";
    $("login-error").textContent = "";
    await enter();
  } catch (error) {
    $("login-error").textContent = error.message;
  }
};
document
  .querySelectorAll("[data-view],[data-go]")
  .forEach(
    (button) =>
      (button.onclick = action(() =>
        setView(button.dataset.view || button.dataset.go),
      )),
  );
$("logout").onclick = action(async () => {
  await api("logout", "POST", {});
  location.reload();
});
$("config-form").onsubmit = action(saveConfig);
$("reload-config").onclick = action(loadConfig);
$("apply-settings").onclick = action(apply);
$("apply-banner").onclick = action(apply);
$("add-logger").onclick = () => {
  const current = readConfig();
  current.loggers.push({
    serial: "",
    name: t("New logger"),
    allowed_ip: null,
    profile: state.profiles[0]?.id || null,
    stale_after: 900,
    enabled: true,
  });
  state.config.loggers = current.loggers;
  renderLoggerEditor();
};
HistoryUI.init({api,serial:()=>$("measurement-logger").value,latest:latestSample,render:renderMeasurements,date});
$("measurement-logger").onchange = ()=>{HistoryUI.changed();renderMeasurements();};
$("measurement-filter").oninput = renderMeasurements;
$("log-filter").oninput = renderEvents;
$("log-level").onchange = renderEvents;
$("clone-profile").onclick = action(() => {
  const profile = JSON.parse($("profile-json").value);
  profile.id = profile.id.slice(0, 56) + "-custom";
  profile.name += t(" · copy");
  selectProfile(profile);
});
$("new-profile").onclick = () =>
  selectProfile({
    schema_version: 1,
    id: "custom-report",
    name: t("New profile"),
    description: "",
    manufacturer: "",
    model: "",
    match: { code: 16912, length: 100 },
    timestamp: null,
    fields: [
      {
        id: "power",
        name: t("Power"),
        offset: 20,
        size: 2,
        endian: "big",
        signed: false,
        scale: 1,
        unit: "W",
        device_class: "power",
        state_class: "measurement",
        register: null,
      },
    ],
  });
$("save-profile").onclick = action(async () => {
  const profile = JSON.parse($("profile-json").value);
  await api("profiles", "POST", profile);
  await loadProfiles();
  selectProfile(state.profiles.find((p) => p.id === profile.id));
  await refresh();
  toast(t("Profile saved. Apply configuration changes."));
});
$("delete-profile").onclick = action(async () => {
  await api("profiles/" + state.selectedProfile.id, "DELETE", {});
  state.selectedProfile = null;
  await loadProfiles();
  await refresh();
  toast(t("Profile deleted."));
});
$("preview-profile").onclick = action(async () => {
  $("preview-result").textContent = JSON.stringify(
    await api("preview", "POST", {
      profile: JSON.parse($("profile-json").value),
      hex: $("preview-hex").value,
    }),
    null,
    2,
  );
});
$("test-mqtt").onclick = action(async () => {
  $("mqtt-test-result").textContent = t("Testing…");
  try {
    const result = await api("mqtt/test", "POST", { config: readConfig() });
    $("mqtt-test-result").textContent = t(result.message);
  } catch (error) {
    $("mqtt-test-result").textContent = error.message;
    throw error;
  }
});
document.querySelectorAll("[data-download]").forEach(
  (button) =>
    (button.onclick = action(async () => {
      const response = await fetch("/api/archive/" + button.dataset.download);
      if (!response.ok) throw Error(t((await response.json()).error));
      const url = URL.createObjectURL(await response.blob());
      const link = node("a");
      link.href = url;
      link.download = button.dataset.download + ".jsonl";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    })),
);
$("theme-toggle").onclick = () => {
  document.body.classList.toggle("dark");
  localStorage.setItem(
    "hub-theme",
    document.body.classList.contains("dark") ? "dark" : "light",
  );
};
if (localStorage.getItem("hub-theme") === "dark")
  document.body.classList.add("dark");
(async () => {
  await I18n.ready;
  try {
    state.csrf = (await api("session")).csrf;
    await enter();
  } catch (error) {
    if ($("app").hidden) return;
    toast(error.message, true);
  }
})();
setInterval(() => {
  if (!$("app").hidden) refresh().catch((error) => toast(error.message, true));
}, 3000);

window.addEventListener("hub-language-change", () => {
  $("page-title").textContent = t(titles[state.view]);
  if(state.view==="help")GuideUI.load(api).catch(error=>toast(error.message,true));
  if(state.view==="firmware")GuideUI.loadFirmware(api).catch(error=>toast(error.message,true));
  if (state.config) {
    // Relabel existing controls; preserve every draft string, selection and focus.
    const labels = {
      serial: "Logger serial number",
      name: "Name",
      allowed_ip: "Allowed IP (optional)",
      profile: "Profile",
      stale_after: "Stale after (s)",
      enabled: "Enabled logger",
    };
    document.querySelectorAll("[data-logger]").forEach((input) => {
      input.parentElement.firstChild.nodeValue = t(
        labels[input.dataset.logger],
      );
      if (input.tagName === "SELECT")
        input.querySelector('option[value=""]').textContent = t("Forward only");
    });
    document
      .querySelectorAll(".logger-edit-row button")
      .forEach((button) => (button.textContent = t("Remove logger")));
    $("mqtt-password-state").textContent = state.config.mqtt.password_set
      ? t("A password is saved. Leave blank to keep it.")
      : t("No password saved.");
    $("config-revision").textContent = t("Saved revision: {revision}", {
      revision: state.revision,
    });
  }
  if (state.selectedProfile)
    $("profile-badge").textContent = state.selectedProfile.builtin
      ? t("Built-in · read only")
      : t("Custom profile");
  renderStatus();
  renderEvents();
});

let pendingImport=null;
$("profile-import-file").onchange=action(async()=>{
  pendingImport=null;$("profile-import-confirm").disabled=true;
  const file=$("profile-import-file").files[0];if(!file)return;
  if(file.size>512*1024)throw Error(t('Import file is too large.'));
  const value=JSON.parse(await file.text());
  if(value.bundle_version){
    const summary=await api('import/preview','POST',value);
    $("profile-import-summary").textContent=JSON.stringify(summary,null,2);
    if(!summary.conflicts.length){pendingImport={bundle:value,revision:summary.revision};$("profile-import-confirm").disabled=false;}
  }else{
    $("profile-import-summary").textContent=t('Standalone profile: {name} · fields: {count}',{name:value.name||value.id,count:value.fields?.length||0});
    pendingImport={profile:value};$("profile-import-confirm").disabled=false;
  }
});
$("profile-import-confirm").onclick=action(async()=>{
  if(!pendingImport)return;
  if(pendingImport.bundle)await api('import','POST',pendingImport);else await api('profiles','POST',pendingImport.profile);
  pendingImport=null;$("profile-import-confirm").disabled=true;await loadProfiles();await loadConfig();await refresh();toast(t('Import saved. Apply configuration when ready.'));
});
