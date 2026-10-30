#!/usr/bin/env python3
"""Minimal structural checks (not a substitute for the HAOS Supervisor validator)."""
from pathlib import Path
import re
import yaml

root=Path(__file__).resolve().parents[1]
repo=yaml.safe_load((root/'repository.yaml').read_text())
app=yaml.safe_load((root/'homelab_alloy/config.yaml').read_text())
assert isinstance(repo,dict) and repo.get('name'), 'Missing repository name'
assert isinstance(app,dict)
assert app.get('slug')=='homelab_alloy'
assert app.get('name')=='Homelab Grafana Alloy'
assert re.fullmatch(r'\d+\.\d+\.\d+',app['version'])
assert app['arch']==['amd64']
assert app.get('journald') is True
assert app.get('init') is False
assert app.get('ports',{}).get('12345/tcp')==12345
assert not app.get('image'), 'This repository must build from its Dockerfile'
assert (root/'homelab_alloy/Dockerfile').exists()
alloy=(root/'homelab_alloy/config.alloy').read_text()
assert 'homelab_log_' in alloy
assert 'name              = "service_events_total"' in alloy
assert 'loki.source.journal "system"' in alloy
assert 'loki.write "central"' in alloy
assert 'http://192.168.1.13:3100/loki/api/v1/push' in alloy
assert 'host = "homeassistant"' in alloy
assert 'source = "journal"' in alloy
assert 'severity' in alloy

# v0.1.4: HA Core file and journal access, read-only by default.
assert {'type': 'homeassistant_config', 'read_only': True} in app.get('map', []), 'Missing read-only Core config mount'
assert 'loki.source.file "homeassistant_core"' in alloy, 'Missing HA Core file source'
assert 'local.file_match "homeassistant_core"' in alloy
assert '/homeassistant/home-assistant.log' in alloy
assert 'action        = "drop"' in alloy, 'Missing journal Core deduplication'
assert 'loki.process "journal_merge_core_tracebacks"' not in alloy

print('Repository schema/contract checks passed (Alloy HCL validated by Docker CI).')
