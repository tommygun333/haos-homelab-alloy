#!/usr/bin/env python3
"""Sanity-check the v0.1.2 HAOS Alloy patterns against reported real examples.

This emulates selected regex/relabel rules; the real Alloy parser is separately
validated by the existing GitHub Actions Docker job.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONF = (ROOT / 'homelab_alloy' / 'config.alloy').read_text()
TESTS = [
    ('2026-10-30 09:18:59.912 ERROR (MainThread) [homeassistant.components.rest.data] Error fetching data: 192.168.1.18', 'error', 'error'),
    ('2026-10-30 09:17:36.377+01:00 WARNING (sentry-sdk.BackgroundWorker) [urllib3.connectionpool] Retrying after connection broken by error', 'error', 'warning'),
    ('ts=2026-10-30T08:12:22.961675722Z level=info msg="now listening for http traffic"', 'error', 'info'),
    ('time="2026-10-30T09:27:40.378407071+01:00" level=error msg="[resolver] failed to query external DNS server"', 'info', 'error'),
    ('2026-10-30 09:12:22.883+01:00 INFO (MainThread) [supervisor.docker.app] Starting Docker app', 'error', 'info'),
    ('2026-10-30 09:10:00.000 WARN (MainThread) [foo] Something happened', 'error', 'warning'),
    ('ts=2026-10-30T08:12:22Z level=debug msg="error description in text"', 'error', 'debug'),
    ('Some other info mentioning level=error in a string', 'info', 'info'),
    ('Traceback (most recent call last):', 'error', 'error'),
]
PYLOG = re.compile(r'(?i)^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?\s+(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')
GOTIME = re.compile(r'(?i)^(?:ts=\S+|time="[^"]+"|time=\S+)\s+level=(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')
GOLEVEL = re.compile(r'(?i)^level=(?P<app_level>TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')

for message, journal, expected in TESTS:
    level = None
    for expr in (PYLOG, GOTIME, GOLEVEL):
        match = expr.search(message)
        if match:
            level = match['app_level'].lower()
    result = ('warning' if level == 'warn' else level) or journal
    assert result == expected, (message, result, expected)

# HA Core's timestamp+level starts each block; traceback continuation does not.
HEADER = re.compile(r'(?i)^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?\s+(?:TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|CRITICAL|FATAL)\b')
records = [
    '2026-10-30 09:10:28.757 ERROR (MainThread) [homeassistant.helpers.template] Template failed',
    'Traceback (most recent call last):',
    '  File "/usr/src/homeassistant/helpers/template/__init__.py", line 574, in async_render_to_info',
    '    raise TemplateError(err) from err',
    'homeassistant.exceptions.TemplateError: ValueError: round got invalid input unknown',
    '2026-10-30 09:11:00.000 INFO (MainThread) [homeassistant.core] Started',
]
groups = []
for record in records:
    if HEADER.match(record) or not groups:
        groups.append([record])
    else:
        groups[-1].append(record)
assert len(groups) == 2 and len(groups[0]) == 5 and len(groups[1]) == 1

for expr in (PYLOG, GOTIME, GOLEVEL, HEADER):
    # Check that all of the RE2-compatible patterns appear in Alloy as raw regexes.
    assert expr.pattern in CONF, f'missing regex: {expr.pattern}'
assert 'path          = "/var/log/journal"' in CONF
assert 'selector = `{syslog_identifier="homeassistant"}`' in CONF
assert 'selector = `{unit="docker.service"}`' in CONF
assert 'replacement   = "$1"\n    target_label  = "service_name"' in CONF
assert 'loki.process.journal_merge_core_tracebacks.receiver' in CONF
assert 'loki.process.severity_counters.receiver' in CONF
assert 'loki.process.service_counters.receiver' in CONF
print(f'Passed {len(TESTS)} severity fixtures, traceback grouping and configuration invariants.')
