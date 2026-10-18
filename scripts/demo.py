#!/usr/bin/env python3
"""Offline, synthetic contract walkthrough; never a real model/deployment demo."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.gates import gate, STAGES
from scripts.context import checkpoint, resume
from tests.support import ID, create, verified, reviewed, released, text

with tempfile.TemporaryDirectory(prefix='loop-contract-demo-') as tmp:
    root=Path(tmp); create(root)
    results=[gate(root,ID,s) for s in ('discover','specify','design','plan')]
    verified(root); reviewed(root); released(root)
    results += [gate(root,ID,s) for s in ('verify','review','release','close')]
    checkpoint(root,ID,'Continue native GSD after checking external status')
    before=resume(root,ID)['result']
    text(root,'check.py','print("changed source")\n')
    after=resume(root,ID)['result']
    assert before=='ready_to_resume' and after=='reconcile'
    print(json.dumps({'kind':'synthetic_contract_demo','not_tested':['live_model_reasoning','authenticated_independent_review','real_deployment'],'gates':results,'fresh_resume':before,'changed_source_resume':after},ensure_ascii=False,indent=2))
