# Homelab Grafana Alloy — app documentation

This app uses Home Assistant Supervisor's read-only `journald: true` host journal mount. It runs the official Grafana Alloy container and collects journal entries from Home Assistant OS, including Core/Supervisor/app logs **if those logs appear in the host journal**.

## Start and verify

1. Install the app from the **Homelab Monitoring Apps** custom app repository, then start it.
2. Check the app's Logs tab: component start-up and Loki connection failures appear there.
3. From the LAN: `curl -fsS http://HAOS_IP:12345/-/ready`.
4. After new journal events, check `http://HAOS_IP:12345/metrics` for `homelab_log_service_events_total`.
5. In Grafana/Loki query: `{host="homeassistant",source="journal"}`.
6. In Prometheus, add an additional scrape target `HAOS_IP:12345` to **the existing** `homelab-alloy-logs` file-SD list with label `collector_node="haos"`; verify `up{job="homelab-alloy-logs",collector_node="haos"}` becomes 1.

Do not run a second Alloy/Promtail journal reader on the same HAOS machine: repeated log shipping would lead to duplicated Loki entries and counters.

## Pipeline

- Source: `loki.source.journal.system`, `max_age="10m"`, host `homeassistant`, source `journal`.
- Normalization: `loki.relabel.journal` preserves unit, transport, syslog identifier and journal-priority metadata, and sets the indexed `severity` label from journal priority.
- Loki receiver: `http://192.168.1.13:3100/loki/api/v1/push`.
- Legacy counter: `homelab_log_events_total{host,severity_group}` for high/warning/unknown events.
- Service counter: `homelab_log_service_events_total{host,source,service_name,severity_group}` for high/warning/normal/unknown events.
- Scrape job: `homelab-alloy-logs`, assigned by Prometheus's existing service discovery, **not** by Alloy.

## Troubleshooting

- **App missing:** confirm the GitHub repo is public, has `repository.yaml` at its root, and that `homelab_alloy/config.yaml` is valid; refresh the app store and check Supervisor logs.
- **Build fails:** verify HAOS can pull `grafana/alloy:v1.20.1` from Docker Hub; read Supervisor logs and GitHub Actions validation output.
- **No journal lines:** check `loki.source.journal.system` in the Alloy UI; verify HAOS journal access via the app's `journald` option before considering privileges.
- **Logs arrive but no counters:** counters are only created for new logs; inspect `loki.process.service_counters` and `loki.process.severity_counters`.
- **Loki data missing:** confirm HAOS can reach TCP 3100 on `192.168.1.13`; avoid a public reverse-proxy endpoint.
- **Prometheus misses metrics:** confirm Prometheus CT107 can reach HAOS TCP 12345, that the new file-SD JSON remains valid, and that the job is `homelab-alloy-logs`.
- **New version not offered:** increment `homelab_alloy/config.yaml`'s `version`, push to the tracked branch, refresh the app store.

## Security

Alloy exposes an unauthenticated debug interface and metrics endpoint on 12345. Permit only trusted LAN/CT107 access. The Docker socket is not mounted; AppArmor/protection mode aren't disabled; the journal is mapped read-only by Supervisor. Raw logs may contain sensitive data; keep Loki restricted too.

The pipeline is built into `config.alloy`, not editable through the app Configuration tab. Source updates require a Git push plus app version bump.

## Docker log severity and traceback handling (v0.1.2)

The host journal sometimes records container stdout/stderr with a priority that
differs from the application's own level. For `unit="docker.service"`, an
anchored HA/Python timestamp+level, `ts=... level=...`, `time=... level=...`
or leading `level=...` takes precedence; otherwise journal priority remains
authoritative. The original `journal_priority_numeric` and
`journal_priority_original` are still structured metadata. The metadata
`severity_origin=message_prefix` indicates a message-level override;
`journal_priority` indicates the fallback.

Docker journal records use `syslog_identifier` for indexed `service_name`
when available. The original `unit="docker.service"` stays indexed.
Existing dashboards and the Loki HA integration continue using `host`,
`service_name`, `source`, `severity`, and the original metric family names.

Only HA Core records (`syslog_identifier="homeassistant"`) enter the
multiline processor. It uses the anchored HA timestamp+severity as the
beginning of an event, allows up to 128 lines, and waits at most 2 seconds
for continuation lines. Tracebacks interleaved with unrelated messages or
changing journal labels may still split.

The normalizer runs **after** multiline grouping and **before** the Loki
writer and both Prometheus counters. This means each merged traceback is
counted once rather than once per journal line, while the journal reader's
own `loki_source_journal_target_lines_total` still counts raw lines.
Historical Loki entries and existing counter samples are not rewritten.

To check recent examples:

```logql
{host="homeassistant",syslog_identifier="dockerd",severity="error"}
{host="homeassistant",syslog_identifier="hassio_supervisor",severity="info"}
{host="homeassistant",syslog_identifier="homeassistant",severity="error"}
```


## v0.1.4 — Native Home Assistant Core log-file source (current)

This section **replaces** the v0.1.2 journal multiline recommendation above.

### Required preparation, in this order

1. Before updating Alloy, use an HAOS terminal: `ha core options --duplicate-log-file=true`
2. Run `ha core rebuild` (restarts Home Assistant Core), and wait for Core to return.
3. Confirm the current file exists and is nonempty with `ls -lh /config/home-assistant.log` on the Terminal & SSH app. The file is named `home-assistant.log` and resides in HA's configuration directory.
4. Refresh the custom app repository and update **Homelab Grafana Alloy** to v0.1.4.
5. Verify an active `loki.source.file.homeassistant_core` target in the Alloy UI and query new Loki records.

**Do not install v0.1.4 before enabling and confirming the log file.** This
version intentionally drops Home Assistant Core's fragmented journal messages
to avoid duplicates, even if the file is missing.

### Sources and normalization

- Core file: read-only Supervisor `homeassistant_config` map at
  `/homeassistant/home-assistant.log`. No Docker socket or privileged access.
  `local.file_match` discovers the active file, and `loki.source.file` tails it.
  `tail_from_end=true` avoids replaying existing contents on first deployment.
- One Home Assistant formatted header begins one Loki entry. The multiline
  processor accumulates Python stack frames and chained exceptions for up to
  512 lines, flushing after 3 seconds idle. A new header begins a new record.
  It is **record grouping, not Home Assistant's occurrence deduplication**.
- Core indexed labels: `host=homeassistant`, `source=homeassistant_core`,
  `service_name=homeassistant`, `syslog_identifier=homeassistant` and normalized
  `severity` / `level`. Original file timestamps are parsed including local UTC offset.
- Journal collection retains the explicit working `path=/var/log/journal` and
  all existing Docker application severity overrides, raw journal-priority
  structured metadata and per-service attribution. It excludes only the
  exact journal identifier `homeassistant` at source before Loki or counters.
- Both sources flow into the **same** Loki endpoint and existing
  `homelab_log_events_total` and `homelab_log_service_events_total` counters.
  Prometheus does not need a new scrape target or new job.

### Queries after the update

```logql
{host="homeassistant",source="homeassistant_core",severity="error"}
{host="homeassistant",source="homeassistant_core"} |= "Traceback (most recent call last):"
{host="homeassistant",source="journal",syslog_identifier="hassio_supervisor"}
```

To verify Core journal copies are no longer accepted, restrict Loki queries to
a time range **after** the upgrade and inspect
`{host="homeassistant",source="journal",syslog_identifier="homeassistant"}`.
Historic journal copies are not deleted or rewritten.

If the file source shows no targets, confirm both duplicate-log-file and the
read-only mount. Core file writing increases local I/O, and the read-only map
exposes the broader HA configuration folder to the Alloy container; treat the
app as trusted. Only the active `home-assistant.log` is followed; previous
rotated logs aren't replayed. After a Core restart, new log entries will be
picked up through file discovery. When the duplicate-file option is disabled,
Core log collection stops (journal remains intentionally excluded).

### Rollback

To go back to v0.1.2, reinstall the earlier version of the add-on repository
and verify its journal source. Only once Core journal shipping is restored,
optionally disable the duplicate file with
`ha core options --duplicate-log-file=false` and `ha core rebuild`.


## v0.1.5 — Actual HAOS log-file header format (current)

The HAOS duplicate file on this machine emits timestamps like
`2026-10-30 10:47:46.401 WARNING`, **without an embedded UTC offset**.
V0.1.4 required a `+01:00` suffix in both its multiline matcher and
severity parser, so no line was recognized as a record start and tracebacks
were passed through as separate `unknown` entries.

The v0.1.5 parser accepts headers with or without an offset. Timestamp
parsing uses a local `Europe/Bratislava` location for zoneless headers,
with offset-bearing fallback. The original `/homeassistant/home-assistant.log`
file source, journal exclusion of Core copies, and all metric families are
unchanged. No additional Core rebuild is needed; update the Alloy app only.

Validation must include a fresh traceback produced **after** the v0.1.5
update. Historical split entries retain their old labels in Loki. Entries
without an explicit offset are ambiguous at the autumn DST clock change.
