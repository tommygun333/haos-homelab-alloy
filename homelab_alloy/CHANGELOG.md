# Changelog

## 0.1.5 — Fix Core log header detection and traceback grouping

- Accept timezone-less HAOS log-file headers (observed `2026-10-30 10:47:46.401 WARNING`) and offset-bearing headers.
- Fix severity extraction and join chained Python tracebacks before Loki and Prometheus counters.
- Parse local timestamps as `Europe/Bratislava`, with explicit-offset fallback.
- Preserve all journal processing and v0.1.4 file/journal source separation.
- Add regression fixtures for the real HAOS header and both timestamp formats.


## 0.1.4 — Native Home Assistant Core log-file collection

- Collect complete HA Core logging records from the native duplicate log file.
- Mount the HA config directory read-only; detect active file dynamically.
- Drop Core's fragmented journal stream before Loki and Prometheus to avoid duplicates.
- Keep journald for Supervisor, add-ons, host and Docker; preserve normalized severity.
- Parse HA Core timestamp and severity; combine chained Python tracebacks.
- Add source-separation and traceback regression tests, and documentation.
- Upgrade directly from 0.1.2 or 0.1.3; no intermediate deployment required.


## 0.1.2 — HAOS severity, service attribution, traceback grouping

- Prefer anchored application prefixes to unreliable Docker journal priority; preserve raw journal priority metadata.
- Use Docker journal syslog identifiers as service names instead of lumping all apps under docker.service.
- Recombine Home Assistant Core traceback continuation lines before Loki and Prometheus counters.
- Add fixtures for examples, plus Alloy config validation through existing CI.


## 0.1.0 — Initial GitHub app-store release

- Converted the existing manually deployed HAOS collector into a Supervisor-managed GitHub app repository.
- Kept the pinned Grafana Alloy v1.20.1 runtime, read-only host journald access, normalized indexed severity, existing Loki destination, legacy and service-level Prometheus counters.
- Exposed Alloy `/metrics` and inspector on HAOS port 12345.
- Added repository verification and CI validation; no additional system privileges requested.
