# Homelab Grafana Alloy

Ships HAOS host-journal logs to your existing Loki and exposes per-service severity counters for Prometheus, matching the rest of the homelab.

**Loki:** `192.168.1.13:3100`  
**Metrics/UI:** HAOS port `12345`  
**Host label:** `homeassistant`  
**Alloy image:** `grafana/alloy:v1.20.1`

See the **Documentation** tab for installation, verification and troubleshooting. The Loki destination is embedded in the source configuration; update in GitHub and bump the app version when changing it.
