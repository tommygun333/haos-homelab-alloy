# Changelog

## 0.1.9 — Classify HAOS Docker BuildKit progress without hiding failures

- Detect normal `#N` BuildKit progress from `app_builder_*` journal sources and classify it as `info` rather than treating stderr's journal priority 3 as an error.
- Keep genuine `ERROR`/failed-build output and unrecognized lines at the original journal severity; preserve original journal priority as structured metadata.
- Add source-scoped regression fixtures, including failed builds and unrelated apps, and extend the real Alloy runtime test.
- Leave ANSI decolorization, application severity rules, Core multiline collection, Loki and Prometheus counters unchanged.

## 0.1.8 — Normalize OpenCode timestamp= application levels

- Recognize anchored `timestamp=... level=INFO/WARN/ERROR` log headers used by the HAOS OpenCode app alongside the existing `ts=...` and `time=...` forms.
- Prefer the explicit application severity over the sometimes incorrect Docker journal priority, retaining `journal_priority_original`, `journal_priority_numeric`, and `severity_origin` metadata.
- Add the actual OpenCode INFO event and fallback/negative examples to Python fixtures and the pinned Docker Alloy runtime smoke test.
- No changes to the working ANSI decolorization, HA Core file/traceback pipeline, Loki destination, or Prometheus counters.

## 0.1.7 — Strip ANSI colors before journal severity classification

- **Fix:** HAOS Supervisor emits terminal-colored journal messages beginning with an ANSI sequence (for example `\x1b[32m`) before the timestamp. Existing anchored `stage.regex` rules could not match, causing `INFO` and `WARNING` to be counted as journal-priority `error`.
- Use official Alloy `stage.decolorize {}` at the start of the journal normalization processor, ahead of all message-prefix severity extractors; preserve the journald-priority fallback and raw journal priority metadata.
- Add actual ANSI-prefixed Supervisor/urllib3 fixtures and Docker-based runtime regression validation in GitHub Actions.
- Leave native Home Assistant Core file collection and its traceback merging unchanged.


## 0.1.6 — Fix journal application severity overrides for Supervisor and others

- Remove the `unit="docker.service"` `stage.match` wrapper around the anchored message-prefix severity extractors, which failed to apply to observed Supervisor INFO and WARNING entries despite the indexed unit label.
- Apply strictly anchored application-level log patterns to all journal records, falling back to journald PRIORITY where no explicit application prefix matches.
- Preserve raw `journal_priority_numeric`, `journal_priority_original`, and the `severity_origin` structured metadata.
- Continue to exclude Home Assistant Core journal copies and collect Core exceptions as intact records from the native log file. No changes to metric families or scrape configuration.
- Add exact observed Supervisor INFO/WARNING fixtures plus an assertion that the journal override is not silently nested inside another match stage.


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
