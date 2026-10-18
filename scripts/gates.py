"""Read-only exit gates. Successful checks are evidence, not authorization."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from scripts.common import ContractError, require, nonempty, resolve, read, digest, stable, source_digest, target_dir, unique

STAGES = ('discover', 'specify', 'design', 'plan', 'verify', 'review', 'release', 'close')

def fields(obj: dict, names: tuple[str, ...], label: str) -> None:
    require(isinstance(obj, dict), f'{label} must be an object')
    for name in names:
        require(nonempty(obj.get(name)), f'{label}.{name} must be explicit')

def bound(root: Path, relative: str, expected: str) -> None:
    require(digest(root, relative) == expected, f'Stale reference: {relative}')

def approval(root: Path, record: dict, subject: str) -> None:
    # This verifies provenance fields, NOT the identity/authenticity of the author.
    fields(record, ('actor', 'source', 'subject_sha256'), 'approval')
    require(record.get('authority') == 'human', 'Human decision required; model self-approval is not accepted')
    require(record['subject_sha256'] == subject, 'Approval is bound to an obsolete artifact')
    require(resolve(root, record['source']).is_file(), 'Approval source must be preserved in the repository')

def intent(root: Path, base: str) -> dict:
    obj = read(root, base + '/intent.json')
    fields(obj, ('id', 'original_request', 'actor', 'scenario', 'problem', 'desired_outcome', 'recommendation', 'delivery_target'), 'intent')
    require(obj.get('schema_version') == 1, 'Unsupported intent schema')
    require(obj['delivery_target'] in {'pull_request', 'staging', 'production'}, 'Declare an exact delivery target')
    require(obj.get('risk') in {'low', 'standard', 'high'}, 'Declare risk')
    require(isinstance(obj.get('ui'), bool), 'Declare whether UI design is required')
    require(isinstance(obj.get('in_scope'), list) and obj['in_scope'], 'Define scope')
    require(isinstance(obj.get('out_of_scope'), list) and obj['out_of_scope'], 'Define exclusions')
    require(isinstance(obj.get('constraints'), list), 'List constraints explicitly, even when empty')
    metrics = obj.get('success_metrics', [])
    unique(metrics, 'success metrics')
    for metric in metrics:
        fields(metric, ('measure', 'target', 'baseline', 'method'), 'metric')
        if metric['baseline'] == 'unmeasured':
            fields(metric, ('baseline_plan',), 'metric')
    require(obj.get('alternatives'), 'Compare the proposed solution with at least one alternative/no-build option')
    for alt in obj['alternatives']:
        fields(alt, ('option', 'tradeoff'), 'alternative')
    evidence = obj.get('evidence', [])
    unique(evidence, 'discovery evidence')
    for item in evidence:
        fields(item, ('claim', 'source'), 'evidence')
        require(item.get('status') in {'verified', 'assumed', 'unknown', 'conflicting'}, 'Do not promote an assumption into a fact')
    require(isinstance(obj.get('open_questions'), list), 'List open questions explicitly')
    for question in obj['open_questions']:
        require(not question.get('blocking', True), 'Unresolved blocking question: '+str(question.get('question')))
        fields(question, ('question', 'owner', 'resolution_plan'), 'open question')
    approval(root, obj.get('approval', {}), stable({k:v for k,v in obj.items() if k != 'approval'}))
    return obj

def specification(root: Path, base: str, idea: dict) -> dict:
    obj = read(root, base + '/spec.json')
    bound(root, base + '/intent.json', obj.get('intent_sha256', ''))
    requirements = obj.get('requirements', [])
    unique(requirements, 'requirements')
    metrics = {m['id'] for m in idea['success_metrics']}
    covered_metrics = set()
    criteria = []
    for req in requirements:
        fields(req, ('behavior',), 'requirement')
        require(set(req.get('outcomes', [])) <= metrics and req.get('outcomes'), 'Every requirement must trace to an intended outcome')
        covered_metrics.update(req['outcomes'])
        require(req.get('acceptance'), 'A requirement without acceptance criteria cannot be planned')
        criteria.extend(req['acceptance'])
    require(covered_metrics == metrics, 'An intended outcome has no requirement')
    unique(criteria, 'acceptance criteria')
    commands = read(root, '.loop/checks.json')['checks']
    for ac in criteria:
        fields(ac, ('given', 'when', 'then', 'check'), 'acceptance')
        require(ac['check'] in commands, 'Acceptance references an unregistered check')
        require(ac.get('kind') in {'normal','failure','recovery','security','performance'}, 'Classify acceptance scenarios')
    kinds = {a['kind'] for a in criteria}
    require('normal' in kinds, 'Missing normal-path acceptance')
    if idea['risk'] != 'low':
        require({'failure','recovery'} <= kinds, 'Standard/high risk changes need failure and recovery acceptance')
    return obj

def design(root: Path, base: str, idea: dict, spec: dict) -> dict:
    obj = read(root, base + '/design.json')
    bound(root, base + '/spec.json', obj.get('spec_sha256',''))
    for key in ('architecture', 'journeys', 'failure_recovery', 'test_strategy'):
        ref = obj.get(key, {})
        bound(root, ref.get('path',''), ref.get('sha256',''))
    require(obj.get('risk_treatments') or idea['risk']=='low', 'Document risk treatment')
    if idea['ui']:
        preview = obj.get('preview', {})
        bound(root, preview.get('path',''), preview.get('sha256',''))
        approval(root, obj.get('approval', {}), stable({k:v for k,v in obj.items() if k!='approval'}))
    return obj

def plan(root: Path, base: str, spec: dict) -> dict:
    obj = read(root, base + '/plan-map.json')
    bound(root, base + '/spec.json', obj.get('spec_sha256',''))
    bound(root, base + '/design.json', obj.get('design_sha256',''))
    plans = obj.get('plans', [])
    ids = unique(plans, 'plans')
    require(all('status' not in p for p in plans), 'plan-map is a projection, not a second progress store')
    required = {ac['id'] for r in spec['requirements'] for ac in r['acceptance']}
    coverage = set()
    commands = read(root, '.loop/checks.json')['checks']
    graph = {}
    for item in plans:
        ref = item.get('path','')
        require(ref.startswith('.planning/phases/') and ref.endswith('-PLAN.md'), 'Plan must reference a native GSD PLAN.md')
        bound(root, ref, item.get('sha256',''))
        text = resolve(root, ref).read_text(encoding='utf-8')
        for name in ('<task', '<verify>', '<done>'):
            require(name in text, f'GSD plan missing {name}: {ref}')
        acs = set(item.get('acceptance', []))
        require(acs and acs <= required, 'Unknown or empty acceptance coverage')
        coverage.update(acs)
        require(item.get('allowed_paths') and item.get('checks'), 'Plan needs scope and executable checks')
        for path in item['allowed_paths']:
            resolve(root,path)
        require(set(item['checks']) <= set(commands), 'Unknown check in plan')
        dependencies = set(item.get('depends_on', []))
        require(dependencies <= ids and item['id'] not in dependencies, 'Invalid plan dependency')
        graph[item['id']] = dependencies
    require(coverage == required, 'Acceptance-to-plan coverage is incomplete')
    done = set()
    while len(done) < len(ids):
        ready = {i for i,deps in graph.items() if i not in done and deps <= done}
        require(ready, 'Plan dependency cycle')
        done.update(ready)
    return obj

def evidence(root: Path, path: str, command: str | None = None) -> dict:
    obj = read(root,path)
    require(obj.get('kind') == 'command_execution', 'Model prose is not executable evidence')
    require(obj.get('exit_code') == 0 and not obj.get('timed_out'), 'Required check did not pass')
    require(obj.get('source_sha256') == source_digest(root), 'Evidence is stale for current source/rules/tests')
    require(obj.get('source_unchanged') is True, 'Check mutated the source; rerun on the final source')
    require(command is None or obj.get('check') == command, 'Evidence ran the wrong check')
    bound(root,obj.get('log',''),obj.get('log_sha256',''))
    config = read(root,'.loop/checks.json')['checks']
    require(obj.get('check') in config, 'Evidence check no longer exists')
    require(obj.get('check_definition_sha256') == stable(config[obj['check']]), 'Check definition changed')
    return obj

def verification(root: Path, base: str, spec: dict) -> None:
    obj = read(root,base+'/evidence-index.json')
    bound(root,base+'/spec.json',obj.get('spec_sha256',''))
    criteria = {a['id']:a for r in spec['requirements'] for a in r['acceptance']}
    require(set(obj.get('acceptance',{})) == set(criteria), 'Every acceptance criterion needs current evidence; no extras')
    for ac,reference in obj['acceptance'].items():
        evidence(root,reference,criteria[ac]['check'])

def review(root: Path, base: str) -> None:
    obj = read(root,base+'/review.json')
    fields(obj,('reviewer','executor','source_sha256','report'), 'review')
    require(obj['reviewer'] != obj['executor'], 'Implementation cannot self-certify independent review')
    require(obj['source_sha256'] == source_digest(root), 'Review is stale')
    bound(root,obj['report'],obj.get('report_sha256',''))
    bound(root,base+'/spec.json',obj.get('spec_sha256',''))
    require(isinstance(obj.get('findings'),list), 'Review findings must be explicit')
    require(not any(f.get('severity') in {'critical','high'} and f.get('status')!='resolved' for f in obj['findings']), 'Unresolved blocking review findings')

def release(root: Path, base: str, idea: dict) -> None:
    obj = read(root,base+'/release.json')
    require(obj.get('target') == idea['delivery_target'], 'Cannot silently downgrade delivery target')
    require(obj.get('source_sha256') == source_digest(root), 'Release evidence is stale')
    fields(obj, ('external_ref','observed_result','rollback_or_recovery'), 'release')
    require(obj.get('operations'), 'Persist external operation receipts')
    for op in obj['operations']:
        fields(op,('idempotency_key','receipt','observed_at'), 'operation')
        require(op.get('status')=='confirmed', 'Uncertain side effect must be reconciled, not repeated')
    if idea['delivery_target'] != 'pull_request':
        fields(obj,('environment','deployed_revision','smoke_evidence','observation_evidence'), 'release')
        for key in ('smoke_evidence','observation_evidence'):
            require(resolve(root,obj[key]).is_file(), 'Missing runtime/observation evidence')
        approval(root,obj.get('approval',{}),stable({k:v for k,v in obj.items() if k!='approval'}))

def learning(root: Path, path: str) -> None:
    obj = read(root,path)
    fields(obj,('id','kind','problem','proposed_change','applies_when','does_not_apply_when','owner','review_after'), 'learning')
    require(obj['kind'] in {'rule','skill','documentation','no_change'}, 'Classify the lesson before codifying it')
    require(obj.get('status') in {'proposed','approved','retired'}, 'Learning cannot self-activate')
    incidents = obj.get('incidents',[])
    unique(incidents, 'learning incidents')
    require(len({(i.get('path'), i.get('sha256')) for i in incidents}) == len(incidents), 'Duplicate incident evidence cannot inflate repetition')
    for item in incidents:
        bound(root,item.get('path',''),item.get('sha256',''))
    require(len(incidents)>=3 or obj.get('severity')=='critical' or obj['kind'] in {'documentation','no_change'}, 'Insufficient evidence for a general rule/skill; keep as incident data')
    require(obj.get('positive_case') and obj.get('counterexample'), 'Require both useful and overreach cases')
    if obj['status']=='approved':
        require(datetime.fromisoformat(obj['review_after']).date() >= datetime.now(timezone.utc).date(), 'Lesson review is overdue')
        approval(root,obj.get('approval',{}),stable({k:v for k,v in obj.items() if k!='approval'}))
        evidence(root,obj.get('evaluation_evidence',''))

def gate(root: Path, target: str, stage: str) -> dict:
    require(stage in STAGES, 'Unknown gate')
    base=target_dir(target)
    idea=intent(root,base)
    require(idea['id']==target,'Intent ID/path mismatch')
    if stage=='discover': return {'gate':stage,'result':'pass'}
    spec=specification(root,base,idea)
    if stage=='specify': return {'gate':stage,'result':'pass'}
    design(root,base,idea,spec)
    if stage=='design': return {'gate':stage,'result':'pass'}
    plan(root,base,spec)
    if stage=='plan': return {'gate':stage,'result':'pass'}
    verification(root,base,spec)
    if stage=='verify': return {'gate':stage,'result':'pass'}
    review(root,base)
    if stage=='review': return {'gate':stage,'result':'pass'}
    release(root,base,idea)
    if stage=='release': return {'gate':stage,'result':'pass'}
    close=read(root,base+'/closure.json')
    require(close.get('remaining_blockers')==[], 'Open blockers prevent closure')
    fields(close,('learning_disposition',), 'closure')
    for proposal in close.get('learning_candidates',[]): learning(root,proposal)
    return {'gate':stage,'result':'pass','boundary':'Structural/evidence gate; not authenticated authorization or business-effect proof.'}
