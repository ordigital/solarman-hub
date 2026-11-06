# Instructions for project agents

Read this file, then [docs/AGENT_INDEX.md](docs/AGENT_INDEX.md), then the source and tests listed for your task. Read README.md when product behavior or user instructions matter; read docs/ARCHITECTURE.md when changing behavior or module boundaries. Do not scan the whole repository by default.

Before completing any change, review docs/AGENT_INDEX.md. Update it in the same change whenever files, entry points, responsibilities, test locations, commands, generated artifacts or cross-file dependencies change. If none of these change, leave the index unchanged. Keep architecture explanations in docs/ARCHITECTURE.md; do not duplicate them in the index.

- This is a standalone clean project. Files outside the repository may contain deployment data and secrets; a deployed Docker service may be receiving live reports. Do not modify legacy files, logger configuration, or running services unless the user explicitly requests deployment or migration. Use temporary data directories and ephemeral/separate ports. Never send synthetic reports to the real cloud.
- Keep Python, asyncio and small modules. SQLite is justified for bounded, queryable measurement history; no ORM or separate database server. Avoid a plugin framework, frontend build chain or duplicated configuration models without a concrete need.
- Transport must keep working if decoding, archive or MQTT fails. Profiles are declarative data; never execute expressions from profiles. Keep serials out of decoder definitions.
- One cloud ACK OR one local ACK per known upload. Bound sockets, queues, timeouts and archive growth. No promise of cloud history backfill.
- Saved configuration is not applied configuration. Listener changes require process restart. Do not silently switch live sessions during config edits.
- Never return/log MQTT passwords, admin tokens or cookies. Protect all management APIs and archives. Preserve blank password edits; clearing must be explicit.
- README.md is a short entry point. The canonical guide is src/solarman_hub/guides/en.md; translations preserve chapter IDs, commands, links and scope. The web manual serves these same files. Built-in profiles are immutable through the UI; custom profiles live in the data directory.
- Add meaningful regression tests for changed behavior; run pytest and node --check src/solarman_hub/static/app.js. For UI changes run a browser check. For image changes build/run Docker on ports that do not conflict with existing services.
- Test fixtures must be synthetic/sanitized. Never commit data/, .env, wifi.txt, cookies.txt, or raw personal captures. Do not print secrets while testing.

- UI source messages are English, catalogs live in static/locales.json. Keep all nine catalogs complete and preserve interpolation tokens. Locale selection must not reload configuration or change draft values. Verify desktop and mobile layouts.

- Firmware sources are under firmware/esp32-companion. The platform and libraries are pinned; the known profile is generated from the canonical Hub JSON. Dist images are intended product artifacts, with SHA256SUMS/manifest. Never embed Wi-Fi credentials, real serials or MACs in firmware. Flash only user-authorized boards; test against fake upstreams, never send synthetic reports to the real cloud.
- History writes/retention and identity errors must not affect ACKs. Retention age uses received time, and size includes database/journal files. Preserve profile revisions for historical interpretation.
