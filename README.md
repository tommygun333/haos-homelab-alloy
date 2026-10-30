# Homelab Grafana Alloy — Home Assistant OS app repository

A Home Assistant **app repository** (formerly an add-on repository), not a HACS integration. Install from **Settings → Apps → Install app → ⋮ → Repositories**, not from HACS. HA Supervisor manages installation, rebuilds and versioned updates. This repository contains one app: **Homelab Grafana Alloy**.

This source-specific configuration is designed for the homelab's existing log pipeline:

- Reads the **Home Assistant OS host journal** using the supported `journald: true` read-only mount.
- Sends recent logs to Loki at `http://192.168.1.13:3100/loki/api/v1/push`.
- Indexes Alloy-normalized `severity`, `host="homeassistant"`, `source="journal"`, `service_name` and journal metadata.
- Exposes `homelab_log_events_total` and `homelab_log_service_events_total` at the Alloy metrics endpoint on HAOS TCP 12345, for central Prometheus to scrape.
- Uses Grafana Alloy **v1.20.1** (pinned in the Dockerfile).
- Does not access the Docker socket, write to host directories, or run an extra Home Assistant integration.

The Alloy pipeline is kept identical to the previously prepared manual HAOS add-on. The initial app version is `0.1.0`. The add-on container is **built on the HAOS device** from the Dockerfile; you do not need GHCR or GitHub Releases to start.

## 1. Create your GitHub repository

Create a **public** GitHub repository named `haos-homelab-alloy` under `tommygun333` (suggested for the links already included), *without* initializing it with a README or license. Extract the distributed ZIP and push the **contents** of the archive to the root of the new repository:

```bash
cd /path/to/extracted/haos_alloy_github_app_repo_v0_1_0
git init -b main
git add .
git commit -m "Initial HAOS Grafana Alloy app repository"
git remote add origin https://github.com/tommygun333/haos-homelab-alloy.git
git push -u origin main
```

If you choose another repository name, change the `url` in both `repository.yaml` and `homelab_alloy/config.yaml`, and change the remote URL above. The `slug` **must** remain `homelab_alloy` to match the app folder. Keep the repository URL stable once added to HAOS; changing it creates a different repository/app identity.

## 2. Add and install the app in Home Assistant OS

1. Open **Settings → Apps → Install app** (the Home Assistant app store).
2. Select the top-right **⋮ → Repositories**.
3. Add the GitHub URL `https://github.com/tommygun333/haos-homelab-alloy`.
4. Find **Homelab Monitoring Apps → Homelab Grafana Alloy**.
5. Install, then enable **Start on boot** and **Watchdog**, and start.
6. Read the app's **Logs** tab for Docker build/startup errors.

**Do not add this repository under HACS → Custom repositories.** HACS would not install a Supervisor-managed container.

If you previously installed the **manual local add-on** from `/local_apps/homelab_alloy`, it is a *different app installation*. Stop it before starting the GitHub version; do not run two HAOS journal collectors simultaneously (duplicate logs and TCP 12345 collision). Removing the old app may remove its stored journal offsets; expect a fresh cursor. Check the new app works before deleting any manual source files.

## 3. Verify the log pipeline

Use the app's Logs tab first. Then from a trusted LAN host (replace `HAOS_IP`):

```bash
curl -fsS http://HAOS_IP:12345/-/ready
curl -fsS http://HAOS_IP:12345/metrics | grep 'homelab_log_service_events_total'
```

The counter appears only after at least one new journal event has been processed. Visit `http://HAOS_IP:12345` for the Alloy inspector (trusted LAN only). In Grafana/Loki:

```logql
{host="homeassistant",source="journal"}
{host="homeassistant",severity=~"^(emergency|alert|critical|fatal|error)$"}
```

On central Prometheus **CT107**, add HAOS to the existing `homelab-alloy-logs` file-SD list, rather than creating a new Prometheus job. Back up `/etc/prometheus/file_sd/homelab-alloy-logs.json`, then append the following object within the existing JSON array (replace `HAOS_IP`):

```json
{"targets": ["HAOS_IP:12345"], "labels": {"collector_node": "haos"}}
```

Verify on Prometheus:

```promql
up{job="homelab-alloy-logs",collector_node="haos"}
count(homelab_log_service_events_total{job="homelab-alloy-logs",collector_node="haos"})
```

The Loki HA integration and Grafana panels use the same `homelab_log_service_events_total` metric and indexed `severity` label. For more details, see [`homelab_alloy/DOCS.md`](homelab_alloy/DOCS.md).

## 4. Publish updates (the reason for this repository)

Update the app configuration in `homelab_alloy/config.alloy` or the pinned Alloy Docker base image, then **bump `version`** in `homelab_alloy/config.yaml` (e.g. `0.1.0` → `0.1.1`). Update [`homelab_alloy/CHANGELOG.md`](homelab_alloy/CHANGELOG.md), then commit and push:

```bash
git add homelab_alloy
git commit -m "Bump HAOS Alloy app to 0.1.1"
git push origin main
```

In HAOS, refresh the app store/repositories, open the installed app, and use **Update** when the new version is offered. Supervisor rebuilds the image locally and restarts the app. A GitHub Release/tag is **not required** for this source-built repository. **Never change app files without incrementing its `version` if you expect HAOS to offer an update.**

The existing app-specific `/data` volume is designed for persistent Alloy offsets, but treat source or image changes as potentially disruptive and keep HA backups for important migrations.

### Validation workflow

GitHub Actions runs a YAML/source contract check and `alloy validate` in the pinned official container on every push/PR. Review that workflow result before publishing a version bump. It does not run a HAOS Supervisor build; install/build still needs a live HAOS test.

## Security and current limitations

- TCP **12345** serves metrics and the Alloy debug UI **without authentication**. Restrict access using LAN firewalls to your monitoring instance. Never expose it publicly.
- The Loki push address and `host="homeassistant"` are currently **source configuration**, not adjustable from the app UI. Edit `homelab_alloy/config.alloy` in Git and bump the app version if they change.
- Only `amd64` HAOS is listed because that is the target VM; ARM64 support can be added after testing.
- The archive and YAML have been statically checked, but the full app image build, Alloy HCL runtime validation and HAOS journal permissions must be verified in GitHub Actions and on the HAOS host.

Useful upstream documentation: [Home Assistant app repositories](https://contributors.home-assistant.io/apps/guides/repository/), [Home Assistant app publishing](https://contributors.home-assistant.io/apps/guides/publishing/), [Grafana Alloy](https://grafana.com/docs/alloy/latest/).

## HAOS severity and traceback improvements (v0.1.2)

Docker-mediated journal priority can disagree with the level inside the
application log (in either direction). The HAOS Alloy pipeline now trusts
well-defined leading log severity prefixes for Docker entries, maintains the
original journal priority in structured metadata, attributes Docker-carried
logs to their actual `syslog_identifier` service, and groups Home Assistant
Core Python tracebacks before counting or shipping them. See
[`homelab_alloy/DOCS.md`](homelab_alloy/DOCS.md).

## Native HA Core log-file pipeline (v0.1.4)

**Supersedes the earlier journal traceback experiments.** The Core log file
`/homeassistant/home-assistant.log` (read-only `homeassistant_config` mount) is
the authoritative source for Home Assistant Core. The journal excludes records
with `syslog_identifier=homeassistant`, preventing duplicated Loki messages and
Prometheus counts. Supervisor, DNS, apps, Docker and HAOS host logs remain
collected from `/var/log/journal`.

**Before applying this update** on HAOS, run `ha core options
--duplicate-log-file=true` and then `ha core rebuild`; verify the file exists
in the configuration directory. Only then install v0.1.4. Source and scraper
label contracts are documented in [`homelab_alloy/DOCS.md`](homelab_alloy/DOCS.md).


## v0.1.5 — Core traceback parsing fix

v0.1.4 did not recognize this HAOS installation's timezone-less log headers.
The new parser recognizes both `2026-10-30 10:47:46.401 WARNING ...` and
`2026-10-30 10:47:46.401+01:00 WARNING ...`, groups exceptions before
counting, and interprets zoneless timestamps in `Europe/Bratislava`.
No extra Home Assistant Core rebuild is needed; update the custom app normally.
