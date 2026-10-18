"""Read-only recovery plus disposable checkpoint projections, not task state."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from scripts.common import read, write, require, resolve, digest, source_digest, git, target_dir, contract_files

def checkpoint(root: Path, target: str, next_action: str) -> dict:
    base=target_dir(target)
    require(resolve(root,base+'/intent.json').is_file(),'Intent does not exist')
    require(next_action.strip(),'Write an actionable handoff')
    require(resolve(root,'.planning/STATE.md').is_file(),'GSD STATE.md is the progress authority; initialize GSD first')
    refs=['AGENTS.md','.loop/rules.json','.planning/STATE.md','.planning/ROADMAP.md']
    refs += [p for p in ('.planning/PROJECT.md','.planning/REQUIREMENTS.md') if resolve(root,p).is_file()]
    refs += [p.relative_to(root).as_posix() for p in resolve(root,base).glob('*.json') if p.name!='checkpoint.json']
    refs=sorted(set(refs) | set(contract_files(root,base)))
    record={'schema_version':1,'projection_only':True,'intent_id':target,'next_action':next_action,'captured_at':datetime.now(timezone.utc).isoformat(),'git_head':git(root,'rev-parse','HEAD',optional=True),'source_sha256':source_digest(root),'references':{p:digest(root,p) for p in refs},'dirty_at_capture':bool(git(root,'status','--porcelain'))}
    write(root,base+'/checkpoint.json',record)
    return record

def resume(root: Path, target: str) -> dict:
    base=target_dir(target)
    require(resolve(root,'.planning/STATE.md').is_file(),'Missing GSD STATE.md; reconstruct from plans/summaries and Git, never invent progress')
    require(resolve(root,base+'/intent.json').is_file(),'Unknown intent')
    p=resolve(root,base+'/checkpoint.json')
    if not p.exists():
        return {'intent_id':target,'result':'reconcile','next_action':'Read STATE.md, ROADMAP.md, native plans/summaries and intent artifacts; no checkpoint yet.','read':['AGENTS.md','.loop/rules.json','.planning/STATE.md','.planning/ROADMAP.md',base+'/intent.json']}
    cp=read(root,base+'/checkpoint.json')
    require(cp.get('projection_only') is True and cp.get('intent_id')==target,'Invalid checkpoint projection')
    changed=[]
    for ref,sha in cp['references'].items():
        if not resolve(root,ref).is_file() or digest(root,ref)!=sha:
            changed.append(ref)
    current_artifacts={p.relative_to(root).as_posix() for p in resolve(root,base).glob('*.json') if p.name!='checkpoint.json'} | set(contract_files(root,base))
    captured_artifacts=set(cp['references'])
    changed.extend(sorted(current_artifacts - captured_artifacts))
    if source_digest(root)!=cp['source_sha256']: changed.append('source/rules/tests')
    # An uncertain external side effect is never a safe retry instruction.
    receipts=resolve(root,base+'/operations.json')
    uncertain=[]
    if receipts.exists():
        uncertain=[op.get('idempotency_key','unknown') for op in read(root,base+'/operations.json').get('operations',[]) if op.get('status')!='confirmed']
    result='reconcile' if changed or uncertain else 'ready_to_resume'
    return {'intent_id':target,'result':result,'changed':changed,'uncertain_operations':uncertain,'next_action':('Reconcile Git/PR/CI/external receipts and rerun affected gates before continuing.' if result=='reconcile' else cp['next_action']),'authority':'.planning/STATE.md + native GSD plans/summaries; checkpoint is not authority','read':list(cp['references']),'git_head':git(root,'rev-parse','HEAD',optional=True),'dirty_worktree':bool(git(root,'status','--porcelain')),'warning':'A new machine needs committed/pushed artifacts or the same persistent workspace. No background work is implied.'}
