# Pinned to the version used by the other homelab Alloy agents.
FROM grafana/alloy:v1.20.1
USER root
ARG BUILD_ARCH=amd64
ARG BUILD_VERSION=0.1.0
LABEL io.hass.name="Homelab Grafana Alloy" \
      io.hass.description="HAOS journal to Loki and Prometheus log counters" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      io.hass.version="${BUILD_VERSION}"
COPY config.alloy /etc/alloy/config.alloy
CMD ["run", "--server.http.listen-addr=0.0.0.0:12345", "--storage.path=/data/alloy", "/etc/alloy/config.alloy"]
