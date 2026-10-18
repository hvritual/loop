"""Synthetic fixtures only. Their approvals/reviews are never production evidence."""
from pathlib import Path
import json
import subprocess
import sys
from scripts.common import write, digest, stable, source_digest
from scripts.evidence import capture

ID='TEST-001'
BASE='.planning/intents/'+ID

def text(root: Path, name: str, value: str) -> None:
    p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(value,encoding='utf-8')

def sign(value: dict) -> dict:
    value.pop('approval',None)
    value['approval']={'authority':'human','actor':'fixture-user','source':'.planning/requests/fixture.md','subject_sha256':stable(value)}
    return value

def create(root: Path) -> dict:
    subprocess.run(['git','init','-q',str(root)],check=True)
    text(root,'.gitignore','__pycache__/\n*.pyc\n.loop-cache/\n')
    text(root,'AGENTS.md','# Synthetic fixture\n')
    write(root,'.loop/rules.json',{'rules':[]})
    text(root,'.planning/STATE.md','# Project State\nStatus: In progress\n')
    text(root,'.planning/ROADMAP.md','# Roadmap\nPhase 1: fixture\n')
    text(root,'.planning/requests/fixture.md','SYNTHETIC TEST DATA. Not a real approval or independent review.\n')
    text(root,'check.py','print("fixture check executed")\n')
    write(root,'.loop/checks.json',{'checks':{'unit':{'argv':['{python}','check.py'],'timeout_seconds':10},'fail':{'argv':['{python}','-c','raise SystemExit(2)'],'timeout_seconds':10}}})
    idea={'schema_version':1,'id':ID,'original_request':'Import many records','actor':'Operator','scenario':'Monthly data preparation','problem':'Repeated entry is slow','desired_outcome':'Less repeated entry with recoverable errors','risk':'standard','ui':False,'delivery_target':'pull_request','success_metrics':[{'id':'OUT-1','measure':'Time per batch','target':'Under five minutes in a representative task','baseline':'unmeasured','baseline_plan':'Measure three representative runs','method':'Timed task observation'}],'in_scope':['Validate a batch'],'out_of_scope':['Production deployment'],'constraints':[],'alternatives':[{'option':'Bulk paste','tradeoff':'Avoids a file but still needs validation'}],'recommendation':'Validate the most common source format first','evidence':[{'id':'EV-1','claim':'This is a fixture, not user research','source':'.planning/requests/fixture.md','status':'verified'}],'open_questions':[]}
    write(root,BASE+'/intent.json',sign(idea))
    spec={'schema_version':1,'intent_sha256':digest(root,BASE+'/intent.json'),'requirements':[{'id':'REQ-1','behavior':'Accept valid rows; explain invalid rows; retry without duplicates','outcomes':['OUT-1'],'acceptance':[{'id':'AC-'+str(i),'given':'A representative batch','when':when,'then':then,'kind':kind,'check':'unit'} for i,(kind,when,then) in enumerate([('normal','Rows are valid','Rows are accepted'),('failure','A row is malformed','The row error is explicit'),('recovery','An import is retried','No duplicate rows appear')],1)]}]}
    write(root,BASE+'/spec.json',spec)
    text(root,BASE+'/design.md','# Fixture design\nA synthetic journey, architecture, recovery and test plan.\n')
    ref={'path':BASE+'/design.md','sha256':digest(root,BASE+'/design.md')}
    design={'schema_version':1,'spec_sha256':digest(root,BASE+'/spec.json'),'architecture':ref,'journeys':ref,'failure_recovery':ref,'test_strategy':ref,'risk_treatments':['Retry identity is checked']}
    write(root,BASE+'/design.json',design)
    planpath='.planning/phases/01-fixture/01-01-PLAN.md'
    text(root,planpath,'---\nphase: 01-fixture\nplan: 01\ntype: execute\n---\n<task type="auto"><name>Fixture</name><files>check.py</files><action>Implement the fixture</action><verify>python check.py</verify><done>AC-1 AC-2 AC-3</done></task>\n')
    plans={'schema_version':1,'projection_only':True,'spec_sha256':digest(root,BASE+'/spec.json'),'design_sha256':digest(root,BASE+'/design.json'),'plans':[{'id':'01-01','path':planpath,'sha256':digest(root,planpath),'acceptance':['AC-1','AC-2','AC-3'],'depends_on':[],'allowed_paths':['check.py'],'checks':['unit']}]}
    write(root,BASE+'/plan-map.json',plans)
    return {'intent':idea,'spec':spec,'design':design,'plans':plans}

def verified(root: Path) -> dict:
    record=capture(root,'unit',ID)
    write(root,BASE+'/evidence-index.json',{'spec_sha256':digest(root,BASE+'/spec.json'),'acceptance':{a:record['evidence'] for a in ('AC-1','AC-2','AC-3')}})
    return record

def reviewed(root: Path) -> None:
    text(root,BASE+'/review.md','SYNTHETIC separate-review fixture, not a real review.\n')
    write(root,BASE+'/review.json',{'reviewer':'fixture-reviewer','executor':'fixture-executor','source_sha256':source_digest(root),'spec_sha256':digest(root,BASE+'/spec.json'),'report':BASE+'/review.md','report_sha256':digest(root,BASE+'/review.md'),'findings':[]})

def released(root: Path) -> None:
    write(root,BASE+'/release.json',{'target':'pull_request','source_sha256':source_digest(root),'external_ref':'fixture://not-a-real-pr','observed_result':'Synthetic confirmed receipt','rollback_or_recovery':'Discard fixture','operations':[{'idempotency_key':'fixture-op','status':'confirmed','receipt':'fixture-receipt','observed_at':'2026-10-18T00:00:00Z'}]})
    write(root,BASE+'/closure.json',{'remaining_blockers':[],'learning_disposition':'No generalized lesson from a synthetic test','learning_candidates':[]})
