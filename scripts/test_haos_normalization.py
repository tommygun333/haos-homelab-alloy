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

assert 'version: "0.1.6"' in app
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
GOTIME = re.compile(r'(?i)^(?:ts=\S+|time="[^"]+"|time=\S+)\s+level=(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')
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
assert journal_normalizer.count('stage.regex {') == 3
assert journal_normalizer.count('source = "effective_severity"') == 1
assert journal_normalizer.count('stage.labels {') == 1
assert 'source = "severity_origin"' in journal_normalizer
assert 'severity_origin           = ""' in journal_normalizer
assert 'journal_priority_original = ""' in journal_normalizer

print('Passed Supervisor INFO/WARNING, dockerd ERROR, journal fallback and unguarded processing tests.')

print('Passed Core-file fixtures, journal severity overrides, and pipeline invariants.')
