#!/usr/bin/env python3
"""Append structured step/issue records for v19 QAT pipeline."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOG_JSONL = REPO / 'results' / 'v19_qat_tracker.jsonl'
STATUS_JSON = REPO / 'results' / 'v19_qat_status.json'


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def append_record(record: dict) -> None:
    LOG_JSONL.parent.mkdir(parents=True, exist_ok=True)
    record.setdefault('ts', utc_now())
    with LOG_JSONL.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + '\n')
    status = {}
    if STATUS_JSON.is_file():
        status = json.loads(STATUS_JSON.read_text(encoding='utf-8'))
    status.update({
        'updated_at': record['ts'],
        'last_step': record.get('step', status.get('last_step')),
        'last_status': record.get('status', status.get('last_status')),
        'last_message': record.get('message', status.get('last_message')),
    })
    if record.get('metrics'):
        status['metrics'] = record['metrics']
    if record.get('issue'):
        issues = status.get('issues', [])
        issues.append(record['issue'])
        status['issues'] = issues
    STATUS_JSON.write_text(json.dumps(status, indent=2), encoding='utf-8')


def main() -> int:
    step = os.environ.get('V19_STEP', 'unknown')
    status = os.environ.get('V19_STATUS', 'info')
    message = os.environ.get('V19_MESSAGE', '')
    record = {'step': step, 'status': status, 'message': message}
    metrics_raw = os.environ.get('V19_METRICS', '')
    if metrics_raw:
        record['metrics'] = json.loads(metrics_raw)
    issue_raw = os.environ.get('V19_ISSUE', '')
    if issue_raw:
        record['issue'] = json.loads(issue_raw)
    append_record(record)
    print('tracked: step=%s status=%s %s' % (step, status, message))
    return 0


if __name__ == '__main__':
    sys.exit(main())
