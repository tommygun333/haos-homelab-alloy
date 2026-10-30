#!/usr/bin/env python3
"""Exercise the shipped journal processor with a real Alloy Docker runtime.

Intentionally not a mock of the Alloy regex or template engine. This feeds
ANSI-colored journal messages through the exact production Loki processor,
then checks the exported Prometheus counter labels and event counts.
Run in GitHub Actions, where Docker is available.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ALLOY = (ROOT / "homelab_alloy/config.alloy").read_text()
START = ALLOY.index('loki.process "journal_normalize_metadata" {')
END = ALLOY.index('// END JOURNAL NORMALIZATION V2', START)
PROCESSOR = ALLOY[START:END].rstrip()
PROD_FORWARD = '  forward_to = [loki.write.central.receiver, loki.process.severity_counters.receiver, loki.process.service_counters.receiver]'
assert PROCESSOR.count(PROD_FORWARD) == 1, "Cannot isolate production pipeline"
PROCESSOR = PROCESSOR.replace(PROD_FORWARD, '  forward_to = [loki.process.test_metrics.receiver]')
assert PROCESSOR.index('stage.decolorize {}') < PROCESSOR.index('stage.regex {')

CONFIG = r'''logging { level = "warn" }

local.file_match "test" {
  path_targets = [
    {
      __path__          = "/fixtures/supervisor.log",
      host              = "homeassistant",
      source            = "journal",
      unit              = "docker.service",
      syslog_identifier = "hassio_supervisor",
      fixture           = "supervisor",
      severity          = "error",
      level             = "error",
      severity_origin   = "journal_priority",
    },
    {
      __path__          = "/fixtures/docker.log",
      host              = "homeassistant",
      source            = "journal",
      unit              = "docker.service",
      syslog_identifier = "dockerd",
      fixture           = "docker",
      severity          = "info",
      level             = "info",
      severity_origin   = "journal_priority",
    },
  ]
  sync_period = "1s"
}

loki.source.file "test" {
  targets       = local.file_match.test.targets
  tail_from_end = false
  forward_to    = [loki.process.journal_normalize_metadata.receiver]
}
''' + PROCESSOR + r'''

loki.process "test_metrics" {
  forward_to = []
  stage.label_keep {
    values = ["severity", "fixture"]
  }
  stage.metrics {
    metric.counter {
      name              = "records_total"
      prefix            = "haos_test_"
      description       = "Processed test logs by effective application severity"
      match_all         = true
      action            = "inc"
      max_idle_duration = "1h"
    }
  }
}
'''

SUPERVISOR = (
    '\x1b[32m2026-10-30 12:27:23.018+01:00 INFO (MainThread) [supervisor.store.git] Update app\x1b[0m\n'
    '\x1b[33m2026-10-30 11:57:36.397+01:00 WARNING (sentry-sdk.BackgroundWorker) [urllib3.connectionpool] Retrying\x1b[0m\n'
    '\x1b[31m2026-10-30 09:18:59.912+01:00 ERROR (MainThread) [supervisor.docker] Failed\x1b[0m\n'
    'This message mentions error but is missing an application log level\n'
)
DOCKER = 'time="2026-10-30T09:27:40.378407071+01:00" level=error msg="Failed to query external DNS"\n'
EXPECTED = {('supervisor', 'info'): 1, ('supervisor', 'warning'): 1,
            ('supervisor', 'error'): 2, ('docker', 'error'): 1}


def metrics(url: str) -> dict[tuple[str, str], float]:
    with urllib.request.urlopen(url, timeout=2) as r:
        raw = r.read().decode('utf-8')
    found: dict[tuple[str, str], float] = {}
    for line in raw.splitlines():
        if not line.startswith('haos_test_records_total{'):
            continue
        group = re.search(r'fixture="([^"]+)"', line)
        severity = re.search(r'severity="([^"]+)"', line)
        if group and severity:
            found[(group[1], severity[1])] = float(line.rsplit(' ', 1)[1])
    return found


def run() -> None:
    if not shutil.which('docker'):
        raise SystemExit('Docker required to test actual Grafana Alloy v1.20.1 runtime')
    with tempfile.TemporaryDirectory(prefix='haos-alloy-runtime-') as tmp:
        d = Path(tmp)
        (d/'config.alloy').write_text(CONFIG)
        (d/'supervisor.log').write_text('')
        (d/'docker.log').write_text('')
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        container = 'haos-alloy-smoke-' + str(os.getpid())
        cmd = [
            'docker', 'run', '-d', '--name', container, '--user', '0:0',
            '-p', f'127.0.0.1:{port}:12345',
            '-v', f'{d}:/fixtures:ro', 'grafana/alloy:v1.20.1',
            'run', '--server.http.listen-addr=0.0.0.0:12345',
            '--storage.path=/tmp/alloy', '/fixtures/config.alloy',
        ]
        print('Starting pinned real Alloy runtime ...', flush=True)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        try:
            url = f'http://127.0.0.1:{port}/metrics'
            end = time.monotonic()+40
            while time.monotonic()<end:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/-/ready', timeout=1) as r:
                        if r.status == 200:
                            break
                except (OSError, urllib.error.HTTPError):
                    pass
                time.sleep(.4)
            else:
                raise RuntimeError('Alloy did not become ready in 40 seconds')
            # Allow local.file_match to register the empty file targets before
            # writing new lines, so no file-tail startup policy can hide them.
            time.sleep(2)
            with (d/'supervisor.log').open('a') as f: f.write(SUPERVISOR)
            with (d/'docker.log').open('a') as f: f.write(DOCKER)
            until = time.monotonic()+40
            found = {}
            while time.monotonic()<until:
                try: found = metrics(url)
                except OSError: pass
                if all(found.get(k) == v for k,v in EXPECTED.items()):
                    break
                time.sleep(.5)
            assert all(found.get(k) == v for k,v in EXPECTED.items()), \
                f'Expected {EXPECTED}, got {found}'
            print('PASS: real Alloy runtime normalized ANSI INFO/WARNING/ERROR, Go error and no-prefix fallback:', found)
        except Exception:
            print('--- Alloy logs ---', flush=True)
            subprocess.run(['docker','logs',container],check=False)
            print('--- end Alloy logs ---', flush=True)
            raise
        finally:
            subprocess.run(['docker','rm','-f',container],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    run()
