# Changelog

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
