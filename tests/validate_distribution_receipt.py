"""Validate captured GitHub CI receipts against local release inputs.

This reads receipts collected through the authenticated GitHub connector; it does
not query GitHub or execute native installers. Local files are not an identity or
attestation boundary. Reviewers must follow the recorded job/run URLs.
"""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
REQUIRED={
 'installer-github-entry','installer-ubuntu-latest','installer-macos-latest',
 'installer-windows-latest','installer-native-codex-ubuntu-latest',
 'installer-native-claude-ubuntu-latest','installer-native-opencode-ubuntu-latest',
 'installer-native-codex-windows-latest'
}

def main():
    receipt=json.loads((ROOT/'.planning/intents/LOOP-INSTALLER/ci-receipt.json').read_text(encoding='utf-8'))
    jobs={j['name']:j for j in receipt['jobs']}
    missing=REQUIRED-set(jobs)
    stale=[p for p,h in receipt['release_inputs'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    failed=[n for n in REQUIRED & set(jobs) if jobs[n]['conclusion']!='success']
    if missing or stale or failed:
        print(json.dumps({'result':'fail','missing':sorted(missing),'stale':stale,'failed':failed}));return 1
    print(json.dumps({'result':'pass','kind':'captured_ci_receipt_validation','head_sha':receipt['head_sha'],'run_id':receipt['run_id'],'job_ids':[jobs[n]['id'] for n in sorted(REQUIRED)],'native_execution_in_this_command':False,'boundary':'Receipt integrity/release-input check, not a new native run or authenticated attestation.'},indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
