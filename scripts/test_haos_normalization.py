#!/usr/bin/env python3
"""Test v0.1.4 Core-file record grouping, severity, source split and invariants.

No live Alloy runtime is emulated. GitHub Actions validates the real Alloy
configuration with the pinned container image.
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
alloy = (root / "homelab_alloy/config.alloy").read_text()
app = (root / "homelab_alloy/config.yaml").read_text()

# Exactly one HA formatted header begins a new event. Chained tracebacks do
# not begin new events, and unrelated events must not be combined.
HEADER = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}(?:[+-]\d{2}:\d{2})? (?:DEBUG|INFO|WARNING|ERROR|CRITICAL)\b')
EXTRACT = re.compile(r'^(?P<ha_timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}(?:[+-]\d{2}:\d{2})?) (?P<app_level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\b')
lines = [
    "2026-10-30 10:16:07.618 ERROR (MainThread) [homeassistant.helpers.event] Error while processing template",
    "Traceback (most recent call last):",
    '  File "/usr/src/homeassistant/homeassistant/helpers/template/extensions/math.py", line 381, in forgiving_round',
    "    value = round(float(value), precision)",
    "ValueError: could not convert string to float: 'unknown'",
    "",
    "During handling of the above exception, another exception occurred:",
    "",
    "Traceback (most recent call last):",
    "  File \"<template>\", line 1, in top-level template code",
    "ValueError: Template error: round got invalid input 'unknown'",
    "",
    "The above exception was the direct cause of the following exception:",
    "",
    "Traceback (most recent call last):",
    '  File "/usr/src/homeassistant/homeassistant/helpers/template/__init__.py", line 466, in async_render',
    '    raise TemplateError(err) from err',
    "homeassistant.exceptions.TemplateError: ValueError: Template error",
    "2026-10-30 10:16:08.105 INFO (MainThread) [homeassistant.core] Next event",
    "2026-10-30 10:16:09.311+01:00 WARNING (MainThread) [homeassistant.helpers.event] Slow template",
]
groups=[]
for line in lines:
    if HEADER.match(line):
        groups.append([line])
    elif groups:
        groups[-1].append(line)
    else:
        raise AssertionError('orphan continuation')
assert list(map(len,groups)) == [18,1,1], list(map(len,groups))
# Regression: the actual 2026-10-30 HAOS file has NO +01:00 suffix.
# V0.1.4's mandatory offset caused every line to fall through ungrouped,
# and severity extraction to yield 'unknown'. Support both real formats.
real_header = '2026-10-30 10:47:46.401 WARNING (SyncWorker_0) [homeassistant.loader] We found a custom integration'
offset_header = '2026-10-30 10:47:46.401+01:00 WARNING (SyncWorker_0) [homeassistant.loader] We found a custom integration'
for header in (real_header, offset_header):
    assert HEADER.match(header), header
    assert EXTRACT.match(header)['app_level'] == 'WARNING', header
for trace_line in ('Traceback (most recent call last):', '  File "some.py", line 4', 'ValueError: failure'):
    assert not HEADER.match(trace_line), trace_line

# A timezone-less timestamp comes from HA's configured local clock, not UTC.
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
a = datetime.strptime('2026-10-30 10:47:46.401', '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=ZoneInfo('Europe/Bratislava'))
b = datetime.strptime('2026-10-30 10:47:46.401+01:00', '%Y-%m-%d %H:%M:%S.%f%z')
assert a.astimezone(timezone.utc) == b.astimezone(timezone.utc)
assert groups[0].count('Traceback (most recent call last):') == 3
assert [EXTRACT.match(g[0]).group('app_level').lower() for g in groups] == ['error','info','warning']
assert groups[0][0].startswith('2026-10-30 10:16:07.618 ERROR')
assert 'level=error' not in lines[-1]  # false match in ordinary text shouldn't be relevant

# Only precise Core identifier is excluded; other HAOS/Supervisor apps remain.
REJECT_CORE = re.compile('homeassistant')
assert REJECT_CORE.fullmatch('homeassistant')
assert not REJECT_CORE.fullmatch('hassio_supervisor')
assert not REJECT_CORE.fullmatch('app_9f46d388_homelab_alloy')
assert not REJECT_CORE.fullmatch('dockerd')

assert 'version: "0.1.11"' in app
assert 'path          = "/var/log/journal"' in alloy
assert 'source_labels = ["__journal_syslog_identifier"]\n    regex         = "homeassistant"\n    action        = "drop"' in alloy
assert alloy.index('action        = "drop"') < alloy.index('target_label  = "unit"')
assert 'loki.process "journal_merge_core_tracebacks"' not in alloy
assert 'loki.process.journal_merge_core_tracebacks.receiver' not in alloy
assert 'loki.source.file "homeassistant_core"' in alloy
assert 'local.file_match "homeassistant_core"' in alloy
assert '__path__          = "/homeassistant/home-assistant.log"' in alloy
assert 'tail_from_end = true' in alloy
assert 'source            = "ha_timestamp"' in alloy
assert 'format            = "2006-01-02 15:04:05.000"' in alloy
assert 'fallback_formats  = ["2006-01-02 15:04:05.000-07:00"]' in alloy
assert 'location          = "Europe/Bratislava"' in alloy
assert HEADER.pattern in alloy
assert EXTRACT.pattern in alloy
assert 'max_lines     = 512' in alloy
assert 'max_wait_time = "3s"' in alloy
assert 'severity_origin = ""' in alloy
assert 'source            = "journal"' not in alloy  # journal is a stream label instead
assert 'loki.write.central.receiver, loki.process.severity_counters.receiver, loki.process.service_counters.receiver' in alloy
# Docker application-level severity normalization survives unchanged.
for fragment in ('source = "effective_severity"', 'source_labels = ["unit", "syslog_identifier"]',
                 'source_labels = ["__journal_priority_keyword"]', 'name              = "service_events_total"'):
    assert fragment in alloy, fragment

# Retain previous Docker/journal severity regression examples. This parsing
# emulates only the anchored patterns; the runtime Alloy CI validates HCL.
PYLOG = re.compile(r'(?i)^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?\s+(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')
GOTIME = re.compile(r'(?i)^(?:(?:ts|timestamp)=\S+|time="[^"]+"|time=\S+)\s+level=(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')
GOLEVEL = re.compile(r'(?i)^level=(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')
SEVERITY_CASES = [
    ('2026-10-30 09:18:59.912 ERROR (MainThread) [homeassistant.components.rest.data] Error fetching data', 'error', 'error'),
    ('2026-10-30 09:17:36.377+01:00 WARNING (sentry-sdk.BackgroundWorker) [urllib3.connectionpool] Retrying', 'error', 'warning'),
    ('ts=2026-10-30T08:12:22.961675722Z level=info msg="now listening for http traffic"', 'error', 'info'),
    ('time="2026-10-30T09:27:40.378407071+01:00" level=error msg="[resolver] failed to query DNS"', 'info', 'error'),
    ('2026-10-30 09:12:22.883+01:00 INFO (MainThread) [supervisor.docker.app] Starting Docker app', 'error', 'info'),
    ('2026-10-30 09:10:00.000 WARN (MainThread) [foo] Something happened', 'error', 'warning'),
    ('ts=2026-10-30T08:12:22Z level=debug msg="error description in text"', 'error', 'debug'),
    ('Some other info mentioning level=error in a string', 'info', 'info'),
    ('Traceback (most recent call last):', 'error', 'error'),
]
for msg, journal, expected in SEVERITY_CASES:
    app_level = None
    for pattern in (PYLOG, GOTIME, GOLEVEL):
        if m := pattern.search(msg):
            app_level = m['app_level'].lower()
    actual = ('warning' if app_level == 'warn' else app_level) or journal
    assert actual == expected, (msg, actual, expected)
for pattern in (PYLOG, GOTIME, GOLEVEL):
    assert pattern.pattern in alloy, pattern.pattern


# v0.1.6: These are the precise Supervisor journal records that were still
# wrongly labeled as error in v0.1.5. All application prefix extractors must
# execute for any journal source and must not depend on the unit label.
SUPERVISOR_CASES = [
    (
        '2026-10-30 11:54:31.255+01:00 INFO (MainThread) [supervisor.resolution.fixup] System autofix complete',
        'error', 'info',
    ),
    (
        '2026-10-30 11:57:36.397+01:00 WARNING (sentry-sdk.BackgroundWorker) [urllib3.connectionpool] Retrying after connection broken',
        'error', 'warning',
    ),
    (
        'time="2026-10-30T09:27:40.378407071+01:00" level=error msg="[resolver] failed to query external DNS server"',
        'info', 'error',
    ),
    (
        '2026-10-30 09:18:59.912 ERROR (MainThread) [homeassistant.components.rest.data] Cannot connect',
        'error', 'error',
    ),
    (
        'This info line mentions error and WARNING in body only',
        'info', 'info',
    ),
]
for msg, journal, expected in SUPERVISOR_CASES:
    level = None
    for pattern in (PYLOG, GOTIME, GOLEVEL):
        if m := pattern.search(msg):
            level = m['app_level'].lower()
    actual = ('warning' if level == 'warn' else level) or journal
    assert actual == expected, (msg, actual, expected)

journal_normalizer = alloy.split('loki.process "journal_normalize_metadata" {', 1)[1].split('// END JOURNAL NORMALIZATION V2', 1)[0]
# This assertion would have caught the previous guarded configuration, even
# though its regexes passed the old Python fixtures.
assert 'stage.match {' not in journal_normalizer, 'Severity override is incorrectly guarded by stage.match'
assert 'selector = `{unit="docker.service"}`' not in journal_normalizer
assert journal_normalizer.count('stage.regex {') == 5
assert journal_normalizer.count('source = "effective_severity"') == 1
assert journal_normalizer.count('stage.labels {') == 1
assert 'source = "severity_origin"' in journal_normalizer
assert 'severity_origin           = ""' in journal_normalizer
assert 'journal_priority_original = ""' in journal_normalizer

print('Passed Supervisor INFO/WARNING, dockerd ERROR, journal fallback and unguarded processing tests.')

print('Passed Core-file fixtures, journal severity overrides, and pipeline invariants.')

# v0.1.7: real Supervisor messages begin with ANSI color escapes,
# e.g. ESC[32m timestamp INFO (...), so the regex cannot match until stripped.
ANSI = re.compile(r'\x1b\[[0-9;]*m')
ANSI_TESTS = [
    ("\x1b[32m2026-10-30 12:27:23.018+01:00 INFO (MainThread) [supervisor.store.git] Update app\x1b[0m", "error", "info"),
    ("\x1b[33m2026-10-30 11:57:36.397+01:00 WARNING (sentry-sdk.BackgroundWorker) [urllib3.connectionpool] Retrying\x1b[0m", "error", "warning"),
    ("\x1b[31m2026-10-30 09:18:59.912+01:00 ERROR (MainThread) [supervisor.docker] Actual failure\x1b[0m", "info", "error"),
    ("time=\"2026-10-30T09:27:40.378407071+01:00\" level=error msg=\"Failed to query external DNS\"", "info", "error"),
    ("ordinary message mentioning error inside its body", "info", "info"),
]
position_decolorize=alloy.index('  stage.decolorize {}',alloy.index('loki.process "journal_normalize_metadata"'))
position_regex=alloy.index('  stage.regex {',alloy.index('loki.process "journal_normalize_metadata"'))
assert position_decolorize<position_regex, 'decolorize must run before journal severity regex'
assert alloy.count('  stage.decolorize {}') == 1
for line, initial, expected in ANSI_TESTS:
    cleaned=ANSI.sub('',line)
    app_level=None
    for pattern in (PYLOG,GOTIME,GOLEVEL):
        if match:=pattern.search(cleaned):
            app_level=match['app_level'].lower()
    actual=('warning' if app_level=='warn' else app_level) or initial
    assert actual==expected,(repr(line),actual,expected)
    if line.startswith('\x1b'):
        assert not PYLOG.search(line), 'raw ANSI line should fail the anchored regex'
        assert '\x1b' not in cleaned
print('Passed v0.1.7 ANSI-prefixed Supervisor, warning, error and fallback fixtures.')


# v0.1.8: OpenCode uses timestamp=... level=INFO; journal priority is often 3.
# Use the application prefix even when journald classifies stdout as error.
OPENCODE_CASES = [
    (
        'timestamp=2026-10-30T18:45:07.720Z level=INFO run=1678d4f8 message=event event.id=evt_18e214608002Xo2FbgUtHICRfZ event.type=command.updated event.location.directory=/data event.location.workspaceID=undefined event.data={}',
        'error', 'info',
    ),
    ('timestamp=2026-10-30T18:45:07.720Z level=WARN run=1678d4f8 message=retry', 'error', 'warning'),
    ('timestamp=2026-10-30T18:45:07.720Z level=ERROR run=1678d4f8 message=failed', 'info', 'error'),
    ('timestamp=2026-10-30T18:45:07.720Z message=event event.data=level=ERROR', 'info', 'info'),
    ('event.data={"level":"ERROR"} command.updated', 'info', 'info'),
]
for line, journal, expected in OPENCODE_CASES:
    app_level = None
    for expression in (PYLOG, GOTIME, GOLEVEL):
        if matched := expression.search(line):
            app_level = matched['app_level'].lower()
    actual = ('warning' if app_level == 'warn' else app_level) or journal
    assert actual == expected, (line, actual, expected)
assert '(?:ts|timestamp)=' in GOTIME.pattern
assert 'stage.decolorize {}' in journal_normalizer
print('Passed v0.1.8 OpenCode timestamp= severity overrides and embedded-word fallbacks.')


# v0.1.9: BuildKit logs from HAOS app builders use journal PRIORITY=3 for
# ordinary progress. Do not hide genuine failures or affect other services.
BUILDKIT = re.compile(r'(?i)^#[0-9]+\s+(?P<buildkit_progress>CACHED\b|DONE\b|\[[^\]\r\n]+\]|transferring\b|building\b|exporting\b|writing\b|naming\b|unpacking\b|extracting\b|resolving\b|resolve\b)')
BUILDER = 'app_builder_9f46d388_homelab_alloy'
BUILD_CASES = [
    ('#0 building with "default" instance using docker driver', BUILDER, 'info'),
    ('#1 [internal] load build definition from Dockerfile', BUILDER, 'info'),
    ('#1 transferring dockerfile: 568B done', BUILDER, 'info'),
    ('#2 [internal] load metadata for docker.io/grafana/alloy:v1.20.1', BUILDER, 'info'),
    ('#4 transferring context: 14.47kB done', BUILDER, 'info'),
    ('#5 [1/2] FROM docker.io/grafana/alloy:v1.20.1', BUILDER, 'info'),
    ('#5 CACHED', BUILDER, 'info'),
    ('#4 DONE 0.0s', BUILDER, 'info'),
    ('#6 exporting to image', BUILDER, 'info'),
    ('#6 ERROR: failed to solve: build step exited with code 1', BUILDER, 'error'),
    ('#6 0.13 ERROR: failed inside a RUN step', BUILDER, 'error'),
    ('ERROR: failed to solve: build terminated', BUILDER, 'error'),
    ('failed to solve: process did not complete successfully', BUILDER, 'error'),
    ('#5 CACHED', 'dockerd', 'error'),
    ('#5 CACHED', 'app_f5588468_ha_opencode', 'error'),
    ('Buildkit string mentioning #5 CACHED inside payload', BUILDER, 'error'),
]
for line, identifier, expected in BUILD_CASES:
    progress = BUILDKIT.search(line)
    actual = 'info' if progress and re.fullmatch(r'app_builder_[A-Za-z0-9_]+', identifier) else 'error'
    assert actual == expected, (line, actual, expected)
assert BUILDKIT.pattern in journal_normalizer
assert 'buildkit_progress{{- else -}}' in journal_normalizer
assert 'app_builder_[A-Za-z0-9_]+$' in journal_normalizer
assert journal_normalizer.index('stage.decolorize {}') < journal_normalizer.index('(?P<buildkit_progress>') < journal_normalizer.index('source = "effective_severity"')
print('Passed v0.1.9 builder progress and true-failure severity regression fixtures.')


# v0.1.11: classify a format, not each executable/add-on prefix separately.
# Start-anchored executable/path + colon + explicit level + colon. No guessing
# from the presence of "error" or "info" later in an arbitrary log message.
PROGRAM_LEVEL_PATTERN = r'(?i)^[A-Za-z0-9_./-]{1,160}:[ \t]+(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL):(?:[ \t]|$)'
PROGRAM_LEVEL = re.compile(PROGRAM_LEVEL_PATTERN)
PROGRAM_CASES = [
    ('s6-rc: info: service legacy-services successfully started', 'error', 'info'),
    ('\x1b[32ms6-rc: info: service prepare successfully started\x1b[0m', 'error', 'info'),
    ('s6-rc: warning: service prepare failed to start', 'error', 'warning'),
    ('s6-rc: fatal: unable to take locks', 'info', 'fatal'),
    ('s6-rc: error: service prepare failed', 'info', 'error'),
    ('cont-init: info: /etc/cont-init.d/30-esphome-fork.sh exited 0', 'error', 'info'),
    ('/package/admin/s6-overlay/libexec/preinit: info: /run permissions: uid=0 (root), gid=0 (root), perms=oxorgxgruxuwur', 'error', 'info'),
    ('/package/admin/s6-overlay/libexec/preinit: warning: permissions look wrong', 'error', 'warning'),
    ('another-tool: DEBUG: task started', 'error', 'debug'),
    ('my-service: CRITICAL: database corrupted', 'info', 'critical'),
    ('other application mentions s6-rc: info: in the body', 'error', 'error'),
    ('cont-init: process failed without a severity token', 'error', 'error'),
    ('cont-init: info:script.sh executed', 'error', 'error'),
    ('https://example.com: info: this is a URL not a log prefix', 'error', 'error'),
    ('Weird arbitrary phrase: info: not a program token', 'error', 'error'),
]
for line, journal, expected in PROGRAM_CASES:
    cleaned = ANSI.sub('', line)
    match = PROGRAM_LEVEL.search(cleaned)
    level = match['app_level'].lower() if match else None
    actual = ('warning' if level == 'warn' else level) or journal
    assert actual == expected, (line, actual, expected)
assert PROGRAM_LEVEL_PATTERN in journal_normalizer
assert journal_normalizer.index('stage.decolorize {}') < journal_normalizer.index(PROGRAM_LEVEL_PATTERN) < journal_normalizer.index('source = "effective_severity"')
assert '^(?i)^s6-rc' not in journal_normalizer
print('Passed generic executable/path level parsing, ANSI, and negative fixtures.')
