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
