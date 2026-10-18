from pathlib import Path
import tempfile
import unittest
from scripts.common import ContractError, read, write, digest, stable, source_digest, resolve
from scripts.gates import gate, learning
from scripts.evidence import capture
from scripts.context import checkpoint, resume
from tests.support import ID, BASE, create, verified, reviewed, released, sign, text

class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        create(self.root)
    def edit(self,name,change):
        obj=read(self.root,BASE+'/'+name)
        change(obj); write(self.root,BASE+'/'+name,obj)
    def fails(self,stage,message):
        with self.assertRaisesRegex(ContractError,message): gate(self.root,ID,stage)
    def test_discovery_valid(self): self.assertEqual(gate(self.root,ID,'discover')['result'],'pass')
    def test_blank_actor(self):
        self.edit('intent.json',lambda o:o.update(actor='')); self.fails('discover','actor')
    def test_no_alternative(self):
        self.edit('intent.json',lambda o:o.update(alternatives=[])); self.fails('discover','alternative')
    def test_blocking_unknown(self):
        self.edit('intent.json',lambda o:o.update(open_questions=[{'question':'Which payer?','blocking':True}])); self.fails('discover','blocking')
    def test_nonblocking_needs_plan(self):
        self.edit('intent.json',lambda o:o.update(open_questions=[{'question':'Volume?','blocking':False}])); self.fails('discover','owner')
    def test_no_baseline_plan(self):
        self.edit('intent.json',lambda o:o['success_metrics'][0].pop('baseline_plan')); self.fails('discover','baseline_plan')
    def test_agent_cannot_self_approve(self):
        self.edit('intent.json',lambda o:o['approval'].update(authority='agent')); self.fails('discover','Human decision')
    def test_obsolete_approval(self):
        self.edit('intent.json',lambda o:o.update(problem='Changed problem')); self.fails('discover','obsolete')
    def test_missing_approval_source(self):
        (self.root/'.planning/requests/fixture.md').unlink(); self.fails('discover','Approval source')
    def test_spec_valid(self): self.assertEqual(gate(self.root,ID,'specify')['result'],'pass')
    def test_spec_stale_intent(self):
        self.edit('intent.json',lambda o:sign({**o,'problem':'New approved problem'}))
        # edit helper does not use return values; replace explicitly.
        obj=read(self.root,BASE+'/intent.json'); obj['problem']='New approved problem'; write(self.root,BASE+'/intent.json',sign(obj))
        self.fails('specify','Stale reference')
    def test_unmapped_outcome(self):
        self.edit('spec.json',lambda o:o['requirements'][0].update(outcomes=['UNKNOWN'])); self.fails('specify','trace')
    def test_duplicate_acceptance(self):
        self.edit('spec.json',lambda o:o['requirements'][0]['acceptance'].append(o['requirements'][0]['acceptance'][0])); self.fails('specify','Duplicate')
    def test_missing_failure_recovery(self):
        self.edit('spec.json',lambda o:o['requirements'][0].update(acceptance=o['requirements'][0]['acceptance'][:1])); self.fails('specify','failure and recovery')
    def test_unknown_check(self):
        self.edit('spec.json',lambda o:o['requirements'][0]['acceptance'][0].update(check='invented')); self.fails('specify','unregistered')
    def test_design_valid(self): self.assertEqual(gate(self.root,ID,'design')['result'],'pass')
    def test_missing_design_file(self):
        (self.root/BASE/'design.md').unlink(); self.fails('design','Missing artifact')
    def test_design_stale(self):
        text(self.root,BASE+'/design.md','changed'); self.fails('design','Stale reference')
    def test_ui_preview_required(self):
        obj=read(self.root,BASE+'/intent.json'); obj['ui']=True; write(self.root,BASE+'/intent.json',sign(obj))
        self.edit('spec.json',lambda o:o.update(intent_sha256=digest(self.root,BASE+'/intent.json')))
        self.edit('design.json',lambda o:o.update(spec_sha256=digest(self.root,BASE+'/spec.json')))
        self.fails('design','Path must')
    def test_plan_valid(self): self.assertEqual(gate(self.root,ID,'plan')['result'],'pass')
    def test_incomplete_coverage(self):
        self.edit('plan-map.json',lambda o:o['plans'][0].update(acceptance=['AC-1'])); self.fails('plan','coverage is incomplete')
    def test_parallel_progress_store_rejected(self):
        self.edit('plan-map.json',lambda o:o['plans'][0].update(status='done')); self.fails('plan','second progress')
    def test_self_dependency(self):
        self.edit('plan-map.json',lambda o:o['plans'][0].update(depends_on=['01-01'])); self.fails('plan','dependency')
    def test_cycle(self):
        def change(o):
            second={**o['plans'][0],'id':'01-02','depends_on':['01-01']}
            o['plans'][0]['depends_on']=['01-02']; o['plans'].append(second)
        self.edit('plan-map.json',change); self.fails('plan','cycle')
    def test_stale_native_plan(self):
        text(self.root,'.planning/phases/01-fixture/01-01-PLAN.md','changed'); self.fails('plan','Stale reference')
    def test_scope_traversal(self):
        self.edit('plan-map.json',lambda o:o['plans'][0].update(allowed_paths=['../outside'])); self.fails('plan','escapes')
    def test_no_test_evidence(self): self.fails('verify','Missing artifact')
    def test_real_command_evidence(self):
        result=verified(self.root); self.assertEqual(result['exit_code'],0); self.assertEqual(gate(self.root,ID,'verify')['result'],'pass')
    def test_rebinding_spec_cannot_reuse_old_evidence(self):
        verified(self.root)
        self.edit('spec.json',lambda o:o['requirements'][0].update(behavior='A different approved behavior'))
        self.edit('design.json',lambda o:o.update(spec_sha256=digest(self.root,BASE+'/spec.json')))
        self.edit('plan-map.json',lambda o:o.update(spec_sha256=digest(self.root,BASE+'/spec.json'),design_sha256=digest(self.root,BASE+'/design.json')))
        self.edit('evidence-index.json',lambda o:o.update(spec_sha256=digest(self.root,BASE+'/spec.json')))
        self.fails('verify','intent/spec/design/plan')
    def test_unbound_evidence_cannot_prove_acceptance(self):
        result=capture(self.root,'unit')
        write(self.root,BASE+'/evidence-index.json',{'spec_sha256':digest(self.root,BASE+'/spec.json'),'acceptance':{a:result['evidence'] for a in ('AC-1','AC-2','AC-3')}})
        self.fails('verify','unspecified intent')
    def test_resume_detects_referenced_design_change(self):
        checkpoint(self.root,ID,'Continue')
        text(self.root,BASE+'/design.md','Changed design without updating its index')
        self.assertIn(BASE+'/design.md',resume(self.root,ID)['changed'])
    def test_failed_command(self):
        result=capture(self.root,'fail'); self.assertEqual(result['exit_code'],2)
    def test_stale_evidence_on_code_change(self):
        verified(self.root); text(self.root,'check.py','print("changed")\n'); self.fails('verify','stale')
    def test_stale_evidence_on_rule_change(self):
        verified(self.root); write(self.root,'.loop/rules.json',{'rules':[{'id':'new'}]}); self.fails('verify','stale')
    def test_tampered_log(self):
        result=verified(self.root); text(self.root,result['log'],'fake pass'); self.fails('verify','Stale reference')
    def test_evidence_wrong_check(self):
        result=verified(self.root)
        obj=read(self.root,result['evidence']); obj['check']='fail'; write(self.root,result['evidence'],obj)
        self.fails('verify','wrong check')
    def test_timeout_recorded_as_failure(self):
        registry=read(self.root,'.loop/checks.json'); registry['checks']['slow']={'argv':['{python}','-c','import time; time.sleep(3)'],'timeout_seconds':1}; write(self.root,'.loop/checks.json',registry)
        result=capture(self.root,'slow'); self.assertTrue(result['timed_out']); self.assertEqual(result['exit_code'],124)
    def test_source_mutating_check_rejected(self):
        text(self.root,'check.py','from pathlib import Path\nPath("mutated.txt").write_text("changed")\n')
        result=verified(self.root); self.assertFalse(result['source_unchanged']); self.fails('verify','stale|mutated')
    def test_shell_text_is_not_executed(self):
        registry=read(self.root,'.loop/checks.json'); registry['checks']['bad']={'argv':'echo ok; touch owned','timeout_seconds':1}; write(self.root,'.loop/checks.json',registry)
        with self.assertRaisesRegex(ContractError,'array'): capture(self.root,'bad')
        self.assertFalse((self.root/'owned').exists())
    def test_independent_review_contract(self):
        verified(self.root); reviewed(self.root); self.assertEqual(gate(self.root,ID,'review')['result'],'pass')
    def test_self_review_rejected(self):
        verified(self.root); reviewed(self.root)
        self.edit('review.json',lambda o:o.update(reviewer=o['executor'])); self.fails('review','self-certify')
    def test_blocking_review_finding(self):
        verified(self.root); reviewed(self.root)
        self.edit('review.json',lambda o:o.update(findings=[{'severity':'high','status':'open'}])); self.fails('review','blocking review')
    def test_close_full_synthetic_cycle(self):
        verified(self.root); reviewed(self.root); released(self.root); self.assertEqual(gate(self.root,ID,'close')['result'],'pass')
    def test_no_target_downgrade(self):
        verified(self.root); reviewed(self.root); released(self.root)
        self.edit('release.json',lambda o:o.update(target='staging')); self.fails('release','downgrade')
    def test_unknown_side_effect(self):
        verified(self.root); reviewed(self.root); released(self.root)
        self.edit('release.json',lambda o:o['operations'][0].update(status='unknown')); self.fails('release','reconciled')
    def test_open_closure_blocker(self):
        verified(self.root); reviewed(self.root); released(self.root)
        self.edit('closure.json',lambda o:o.update(remaining_blockers=['CI missing'])); self.fails('close','blockers')
    def test_resume_without_checkpoint(self):
        self.assertEqual(resume(self.root,ID)['result'],'reconcile')
    def test_fresh_session_resume(self):
        checkpoint(self.root,ID,'Run verify for AC-1 through AC-3')
        self.assertEqual(resume(self.root,ID)['result'],'ready_to_resume')
    def test_resume_detects_source_change(self):
        checkpoint(self.root,ID,'Continue'); text(self.root,'check.py','changed')
        self.assertEqual(resume(self.root,ID)['result'],'reconcile')
    def test_resume_detects_decision_change(self):
        checkpoint(self.root,ID,'Continue'); self.edit('intent.json',lambda o:o.update(problem='changed'))
        self.assertIn(BASE+'/intent.json',resume(self.root,ID)['changed'])
    def test_resume_detects_new_artifact(self):
        checkpoint(self.root,ID,'Continue')
        write(self.root,BASE+'/new-decision.json',{'decision':'Changed scope'})
        self.assertIn(BASE+'/new-decision.json',resume(self.root,ID)['changed'])
    def test_learning_duplicate_incident_rejected(self):
        incident={'path':'.planning/requests/fixture.md','sha256':digest(self.root,'.planning/requests/fixture.md')}
        obj={'id':'L1','kind':'rule','status':'proposed','problem':'one failure','proposed_change':'new rule','applies_when':'batch import','does_not_apply_when':'single input','owner':'owner','review_after':'2099-01-01','incidents':[dict(incident,id='I'+str(i)) for i in range(3)],'positive_case':'useful','counterexample':'overreach'}
        write(self.root,BASE+'/lesson.json',obj)
        with self.assertRaisesRegex(ContractError,'Duplicate incident'): learning(self.root,BASE+'/lesson.json')
    def test_resume_is_read_only(self):
        checkpoint(self.root,ID,'Continue'); before=digest(self.root,'.planning/STATE.md'); resume(self.root,ID)
        self.assertEqual(before,digest(self.root,'.planning/STATE.md'))
    def test_resume_does_not_retry_unknown_operation(self):
        write(self.root,BASE+'/operations.json',{'operations':[{'idempotency_key':'op1','status':'unknown'}]})
        checkpoint(self.root,ID,'Deploy again')
        result=resume(self.root,ID); self.assertEqual(result['result'],'reconcile'); self.assertNotEqual(result['next_action'],'Deploy again')
    def test_path_traversal(self):
        with self.assertRaises(ContractError): resolve(self.root,'../../outside')
    def test_absolute_path(self):
        with self.assertRaises(ContractError): resolve(self.root,str(self.root/'check.py'))
    def test_learning_needs_repetition(self):
        obj={'id':'L1','kind':'rule','status':'proposed','problem':'one failure','proposed_change':'new rule','applies_when':'batch import','does_not_apply_when':'single input','owner':'owner','review_after':'2099-01-01','incidents':[{'id':'I1','path':'.planning/requests/fixture.md','sha256':digest(self.root,'.planning/requests/fixture.md')}],'positive_case':'useful','counterexample':'overreach'}
        write(self.root,BASE+'/lesson.json',obj)
        with self.assertRaisesRegex(ContractError,'Insufficient'): learning(self.root,BASE+'/lesson.json')
    def test_critical_incident_can_propose_once(self):
        obj={'id':'L1','kind':'rule','status':'proposed','severity':'critical','problem':'credential leak','proposed_change':'prevent secret logging','applies_when':'credential paths','does_not_apply_when':'public docs','owner':'owner','review_after':'2099-01-01','incidents':[{'id':'I1','path':'.planning/requests/fixture.md','sha256':digest(self.root,'.planning/requests/fixture.md')}],'positive_case':'detect secret','counterexample':'allow public example'}
        write(self.root,BASE+'/lesson.json',obj); learning(self.root,BASE+'/lesson.json')
    def test_learning_cannot_auto_activate(self):
        obj={'id':'L1','kind':'documentation','status':'active','problem':'missing docs','proposed_change':'add doc','applies_when':'setup','does_not_apply_when':'execution','owner':'owner','review_after':'2099-01-01'}
        write(self.root,BASE+'/lesson.json',obj)
        with self.assertRaisesRegex(ContractError,'self-activate'): learning(self.root,BASE+'/lesson.json')

if __name__=='__main__': unittest.main()
