from __future__ import annotations

import copy
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from examples.demo import ROOT, create_source, credentials, drive, example_goal, example_policy, send
from loop_runtime.model import Rejected, STAGES, binding, digest, file_hash, goal_contract, policy_contract
from loop_runtime.runner import Runner, docker_command, regular_files
from loop_runtime.runtime import Runtime, git_snapshot
from loop_runtime.store import Store


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = Path(tempfile.mkdtemp(prefix="loop-tests-shared-"))
        cls.repo = cls.shared / "source"
        cls.commit = create_source(cls.repo)
        cls.snapshots = {}
        root = cls.shared / "base"
        Store.initialize(root, example_policy())
        c = Runtime(root, credentials(root, "controller"))
        h = Runtime(root, credentials(root, "human"))
        r = Runtime(root, credentials(root, "runner"))
        send(c, "create", {"goal": example_goal(), "repo": str(cls.repo), "commit": cls.commit, "paths": ["cups.csv"]})
        def save(name):
            destination = cls.shared / name
            shutil.copytree(root, destination, ignore=shutil.ignore_patterns("runtime.sqlite3", "runtime.sqlite3-wal", "runtime.sqlite3-shm", "work"))
            (destination / "work").mkdir()
            for suffix in ("-wal", "-shm"):
                (destination / ("runtime.sqlite3" + suffix)).unlink(missing_ok=True)
            backup = sqlite3.connect(destination / "runtime.sqlite3")
            try:
                c.db.backup(backup)
            finally:
                backup.close()
            cls.snapshots[name] = destination
        save("initial")
        for stage in ("discover", "design", "deploy"):
            state = drive(c, Runner(r, ROOT, allow_trusted=True))
            assert state["stage"] == stage, state
            save(stage)
            for proposal in state["proposals"].values():
                if proposal["status"] == "pending":
                    send(h, "decide", {"proposal": proposal["id"], "digest": proposal["digest"], "decision": "approve", "reason": "SIMULATED TEST HUMAN"})
        state = drive(c, Runner(r, ROOT, allow_trusted=True))
        assert state["status"] == "delivered", state
        save("delivered")
        c.close(); h.close(); r.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared)

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="loop-test-"))
        self.handles = []
        self.load("initial")

    def tearDown(self):
        for rt in self.handles:
            rt.close()
        shutil.rmtree(self.temp)

    def load(self, name):
        for rt in self.handles:
            rt.close()
        self.handles = []
        self.root = self.temp / ("state-" + uuid.uuid4().hex)
        shutil.copytree(self.snapshots[name], self.root)
        self.c = self.client("controller")
        self.h = self.client("human")
        self.r = self.client("runner")
        self.worker = Runner(self.r, ROOT, allow_trusted=True)

    def client(self, role, clock=None):
        kw = {"clock": clock} if clock else {}
        rt = Runtime(self.root, credentials(self.root, role), **kw)
        self.handles.append(rt)
        return rt

    def state(self):
        return self.c.get("DEMO")

    def pending(self):
        return next(p for p in self.state()["proposals"].values() if p["status"] == "pending")

    def approve(self):
        p = self.pending()
        return send(self.h, "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "approve", "reason": "SIMULATED TEST HUMAN"})

    def finding(self, severity="medium", question="Compare normalized customer aggregation", **changes):
        return {"category": "alternative", "question": question, "hypothesis": "An alternative reduces ambiguity",
                "falsifier": "No measurable difference from baseline", "criterion": "DISCOVER-1",
                "severity": severity, "scope": list(STAGES), **changes}

    def propose(self, kind="change", replacement=None):
        state = self.state()
        refs = list(state["evidence"])[:1]
        return send(self.c, "propose", {"kind": kind, "reason": "Measured evidence warrants bounded rework",
                    "counter_evidence": "Current route may already be sufficient", "unknowns": "Real user impact unverified",
                    "evidence": refs, "replacement": replacement or {"goal": example_goal(), "resume_stage": "discover"}})

    def test_full_runtime_delivery_has_sixteen_real_receipts(self):
        self.load("delivered")
        state = self.c.resume("DEMO")["state"]
        self.assertEqual(state["status"], "delivered")
        self.assertEqual(len(state["evidence"]), 16)
        self.assertEqual(set(state["approvals"]), {"goal", "design", "release"})
        for stage in STAGES:
            self.assertEqual({j["kind"] for j in state["jobs"].values() if j["stage"] == stage}, {"pre", "execute", "verify", "post"})
        self.assertEqual(state["outcome"]["status"], "not_required")
        self.assertTrue(all(e["scope"] == "fixture" for e in state["evidence"].values()))

    def test_default_demo_waits_for_real_human(self):
        self.load("discover")
        self.assertEqual(self.state()["status"], "waiting_human")
        self.assertFalse(self.state()["approvals"])
        before = len(self.state()["jobs"])
        send(self.c, "tick")
        self.assertEqual(len(self.state()["jobs"]), before)

    def test_all_nonhuman_roles_cannot_approve(self):
        self.load("discover")
        p = self.pending()
        for role in ("controller", "runner", "design", "build", "deploy", "explorer", "verifier"):
            with self.subTest(role=role), self.assertRaises(Rejected):
                send(self.client(role), "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "approve", "reason": "unauthorized"})

    def test_invalid_credential_rejected(self):
        with self.assertRaises(Rejected):
            Runtime(self.root, "human")

    def test_idempotency_exact_retry_has_no_second_event(self):
        state = self.state()
        kwargs = {"key": "same-command", "expected": state["revision"]}
        first = self.c.command("DEMO", "tick", {}, **kwargs)
        second = self.c.command("DEMO", "tick", {}, **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(self.state()["revision"], state["revision"] + 1)

    def test_idempotency_conflicting_payload_rejected(self):
        send(self.c, "tick")
        revision = self.state()["revision"]
        self.c.command("DEMO", "discover", self.finding(), key="collision", expected=revision)
        with self.assertRaises(Rejected):
            self.c.command("DEMO", "discover", self.finding(question="different"), key="collision", expected=revision)

    def test_stale_revision_rejected_without_mutation(self):
        rev = self.state()["revision"]
        send(self.c, "tick")
        with self.assertRaises(Rejected):
            self.c.command("DEMO", "tick", {}, key="stale", expected=rev)

    def test_two_connections_cannot_claim_same_job(self):
        state = send(self.c, "tick")
        job = next(iter(state["jobs"]))
        revision = state["revision"]
        def claim():
            runtime = Runtime(self.root, credentials(self.root, "runner"))
            try:
                runtime.command("DEMO", "claim", {"job": job}, key=uuid.uuid4().hex, expected=revision)
                return True
            except Rejected:
                return False
            finally:
                runtime.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.state()["spent"]["jobs"], 1)

    def test_expired_lease_becomes_unknown_and_blocks_replay(self):
        state = send(self.c, "tick")
        jid = next(iter(state["jobs"]))
        state = send(self.r, "claim", {"job": jid})
        expiry = state["jobs"][jid]["expires_at"]
        future = self.client("controller", clock=lambda: expiry + 1)
        state = send(future, "tick")
        self.assertEqual(state["jobs"][jid]["status"], "unknown")
        self.assertEqual(state["status"], "blocked")
        with self.assertRaises(Rejected):
            send(self.r, "claim", {"job": jid})
        with self.assertRaises(Rejected):
            send(self.r, "finish", {"job": jid, "lease": state["jobs"][jid]["lease"], "receipt": "missing"})

    def test_heartbeat_requires_unexpired_matching_fence(self):
        state = send(self.c, "tick")
        jid = next(iter(state["jobs"]))
        state = send(self.r, "claim", {"job": jid})
        with self.assertRaises(Rejected):
            send(self.r, "heartbeat", {"job": jid, "lease": "wrong"})
        expiry = state["jobs"][jid]["expires_at"]
        future = self.client("runner", clock=lambda: expiry + 1)
        with self.assertRaises(Rejected):
            send(future, "heartbeat", {"job": jid, "lease": state["jobs"][jid]["lease"]})

    def test_reconciliation_never_promotes_unknown_to_success_or_refunds(self):
        state = send(self.c, "tick")
        jid = next(iter(state["jobs"]))
        state = send(self.r, "claim", {"job": jid})
        state = send(self.client("controller", clock=lambda: state["jobs"][jid]["expires_at"] + 1), "tick")
        spent = state["spent"].copy()
        state = send(self.h, "reconcile", {"job": jid, "worker_stopped": True, "effects": "none", "receipt": "operator-inspection-001", "reason": "Test operator verified worker no longer exists"})
        self.assertEqual(state["jobs"][jid]["status"], "cancelled")
        self.assertEqual(state["spent"], spent)

    def test_agent_cannot_reconcile_unknown(self):
        with self.assertRaises(Rejected):
            send(self.c, "reconcile", {"job": "x"})

    def test_discovery_dedup_does_not_create_two_experiments(self):
        send(self.c, "discover", self.finding())
        state = send(self.c, "discover", self.finding(question="  compare   normalized customer aggregation "))
        self.assertEqual(len(state["discoveries"]), 1)
        state = send(self.c, "tick")
        self.assertEqual(sum(j["kind"] == "experiment" for j in state["jobs"].values()), 1)

    def test_duplicate_finding_can_escalate_to_critical(self):
        send(self.c, "discover", self.finding())
        state = send(self.c, "discover", self.finding(severity="critical"))
        self.assertEqual(next(iter(state["discoveries"].values()))["severity"], "critical")
        self.assertEqual(send(self.c, "tick")["status"], "blocked")

    def test_opportunity_does_not_expand_implementation_scope(self):
        state = send(self.c, "discover", self.finding(category="opportunity"))
        self.assertEqual(next(iter(state["discoveries"].values()))["status"], "deferred")
        state = send(self.c, "tick")
        self.assertEqual([j["kind"] for j in state["jobs"].values()], ["pre"])
        self.assertEqual(state["goal"], example_goal())

    def test_critical_risk_blocks_even_when_discovery_is_deferred(self):
        send(self.c, "discover", self.finding(severity="critical", category="opportunity"))
        state = send(self.c, "tick")
        self.assertEqual(state["status"], "blocked")
        self.assertFalse(state["jobs"])

    def test_depth_limit_stops_recursion(self):
        parent = None
        for n in range(5):
            finding = self.finding(question=f"depth-{n}")
            if parent:
                finding["parent"] = parent
            state = send(self.c, "discover", finding)
            parent = next(d["id"] for d in state["discoveries"].values() if d["question"] == f"depth-{n}")
        self.assertEqual(state["discoveries"][parent]["status"], "deferred")
        self.assertEqual(state["discoveries"][parent]["stop_reason"], "depth_or_candidate_budget")

    def test_candidate_limit_keeps_critical_warning(self):
        for n in range(4):
            state = send(self.c, "discover", self.finding(question=f"candidate-{n}", severity="critical" if n == 3 else "medium"))
        d = next(x for x in state["discoveries"].values() if x["question"] == "candidate-3")
        self.assertEqual(d["status"], "deferred")
        self.assertTrue(self.c._risk_blockers(state))

    def test_finding_requires_goal_link_and_falsifier(self):
        for changes in ({"criterion": "unknown"}, {"falsifier": ""}, {"scope": ["production"]}, {"confidence": 0.99}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                send(self.c, "discover", self.finding(**changes))

    def test_critical_cannot_be_waived_with_human_text_only(self):
        state = send(self.c, "discover", self.finding(severity="critical"))
        did = next(iter(state["discoveries"]))
        for resolution in ("deferred", "rejected", "accepted", "remediated"):
            with self.subTest(resolution=resolution), self.assertRaises(Rejected):
                send(self.h, "resolve", {"discovery": did, "resolution": resolution, "reason": "waive without evidence"})

    def test_experiment_and_independent_remediation(self):
        state = send(self.c, "discover", self.finding(severity="critical", category="security", question="Fixture: ensure input contains no credential file"))
        did = next(iter(state["discoveries"]))
        for _ in range(4):
            send(self.c, "tick")
            self.worker.run_once("DEMO")
        state = self.state()
        evidence = next(j["evidence"] for j in state["jobs"].values() if j["kind"] == "verify" and j["status"] == "succeeded")
        state = send(self.h, "resolve", {"discovery": did, "resolution": "remediated", "reason": "Independent fixture verifier passed", "evidence": evidence})
        self.assertFalse(self.c._risk_blockers(state))
        self.assertEqual(state["discoveries"][did]["status"], "remediated")

    def test_rejected_review_does_not_automatically_reopen(self):
        self.load("discover")
        p = self.pending()
        send(self.h, "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "reject", "reason": "Change the proposed outcome"})
        for _ in range(2):
            state = send(self.c, "tick")
            self.assertEqual(state["status"], "blocked")
            self.assertEqual(state["proposals"][p["id"]]["status"], "rejected")

    def test_deferred_review_can_be_explicitly_resumed(self):
        self.load("discover")
        p = self.pending()
        send(self.h, "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "defer", "reason": "Review later"})
        state = send(self.c, "tick")
        self.assertEqual(state["status"], "blocked")
        state = send(self.h, "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "approve", "reason": "Explicit test approval now"})
        self.assertIn("goal", state["approvals"])

    def test_wrong_packet_digest_rejected(self):
        self.load("discover")
        p = self.pending()
        with self.assertRaises(Rejected):
            send(self.h, "decide", {"proposal": p["id"], "digest": "wrong", "decision": "approve", "reason": "test"})

    def test_approved_change_invalidates_downstream_and_old_review(self):
        self.load("design")
        old = self.pending()
        self.propose()
        p = next(p for p in self.state()["proposals"].values() if p["kind"] == "change")
        state = send(self.h, "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "approve", "reason": "Approved scope change"})
        self.assertEqual(state["epoch"], 2)
        self.assertEqual(state["stage"], "discover")
        self.assertFalse(state["approvals"])
        self.assertFalse(state["handoffs"])
        with self.assertRaises(Rejected):
            send(self.h, "decide", {"proposal": old["id"], "digest": old["digest"], "decision": "approve", "reason": "stale"})

    def test_critical_risk_survives_goal_change(self):
        self.load("discover")
        send(self.c, "discover", self.finding(severity="critical"))
        self.propose()
        p = next(p for p in self.state()["proposals"].values() if p["kind"] == "change")
        state = send(self.h, "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "approve", "reason": "new baseline"})
        d = next(iter(state["discoveries"].values()))
        self.assertEqual(d["binding"], binding(state))
        self.assertEqual(d["status"], "observed")
        self.assertTrue(self.c._risk_blockers(state))

    def test_failed_or_missing_evidence_cannot_approve_release(self):
        self.load("deploy")
        p = self.pending()
        eid = p["packet"]["evidence"][0]
        evidence_path = self.root / self.state()["evidence"][eid]["path"]
        evidence_path.unlink()
        with self.assertRaises((Rejected, OSError)):
            self.approve()

    def test_snapshot_tampering_is_detected(self):
        self.c.db.execute("UPDATE intents SET state=json_set(state, '$.status', 'delivered') WHERE id='DEMO'")
        with self.assertRaises(Rejected):
            self.c.resume("DEMO")

    def test_audit_tampering_is_detected(self):
        send(self.c, "tick")
        self.c.db.execute("UPDATE events SET payload='{}' WHERE revision=1")
        with self.assertRaises(Rejected):
            self.c.resume("DEMO")

    def test_policy_edit_is_not_self_authorization(self):
        policy = json.loads((self.root / "policy.json").read_text())
        policy["limits"]["jobs"] += 1
        (self.root / "policy.json").write_text(json.dumps(policy))
        with self.assertRaises(Rejected):
            self.c.get("DEMO")

    def test_evidence_file_tampering_is_detected_on_resume(self):
        self.load("discover")
        e = next(iter(self.state()["evidence"].values()))
        receipt = self.root / e["path"]
        result = receipt.parent / "result.json"
        result.chmod(0o644)
        result.write_text('{"forged":true}')
        with self.assertRaises(Rejected):
            self.c.resume("DEMO")

    def test_export_is_review_material_not_a_fake_backup(self):
        self.load("discover")
        result = self.c.export("DEMO", self.temp / "export")
        self.assertFalse(result["evidence_included"])
        self.assertEqual(len((self.temp / "export/audit.jsonl").read_text().splitlines()), self.state()["revision"])
        self.assertFalse((self.temp / "export/.credentials").exists())
        with self.assertRaises(Rejected):
            self.c.export("DEMO", self.temp / "export")

    def test_trusted_mode_needs_explicit_opt_in(self):
        send(self.c, "tick")
        with self.assertRaises(Rejected):
            Runner(self.r, ROOT).run_once("DEMO")
        self.assertEqual(self.state()["spent"]["jobs"], 0)

    def test_git_snapshot_uses_commit_not_dirty_worktree(self):
        self.assertEqual(git_snapshot(self.repo, self.commit, ["cups.csv"])["cups.csv"], (ROOT / "examples/cups.csv").read_text())
        with self.assertRaises(Rejected):
            git_snapshot(self.repo, self.commit, ["../cups.csv"])
        with self.assertRaises(Rejected):
            git_snapshot(self.repo, "main", ["cups.csv"])

    def test_no_worker_can_create_or_schedule_goal(self):
        for role in ("design", "build", "deploy", "explorer", "verifier", "runner"):
            rt = self.client(role)
            with self.subTest(role=role), self.assertRaises(Rejected):
                send(rt, "tick")

    def test_docker_configuration_is_isolated_and_pinned(self):
        image = "sha256:" + "a" * 64
        cmd = docker_command(image, "loop-test", Path("/adapter.py"), Path("/input"), Path("/work"), Path("/output"))
        for flag in ("--read-only", "--cap-drop", "--pids-limit", "--memory", "--user"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--network") + 1], "none")
        self.assertNotIn("/var/run/docker.sock", " ".join(cmd))
        self.assertIn(image, cmd)
        with self.assertRaises(Rejected):
            docker_command(image, "bad", Path("/bad,path"), Path("/input"), Path("/work"), Path("/output"))

    def test_output_symlink_and_hardlink_rejected(self):
        output = self.temp / "unsafe"
        output.mkdir()
        (output / "link").symlink_to(self.root / "authority.json")
        with self.assertRaises(Rejected):
            regular_files(output)
        (output / "link").unlink()
        os.link(self.root / "authority.json", output / "hardlink")
        with self.assertRaises(Rejected):
            regular_files(output)

    def test_invalid_contract_numbers_and_provider_self_review_rejected(self):
        for field in ("jobs", "seconds", "tokens", "cost_microusd", "pocs"):
            policy = example_policy()
            policy["limits"][field] = -1
            with self.subTest(field=field), self.assertRaises(Rejected):
                policy_contract(policy)
        policy = example_policy()
        policy["adapters"]["verifier"]["sha256"] = policy["adapters"]["design"]["sha256"]
        with self.assertRaises(Rejected):
            policy_contract(policy)
        goal = example_goal()
        goal["criteria"]["build"][0]["id"] = "DISCOVER-1"
        with self.assertRaises(Rejected):
            goal_contract(goal)

    def test_stale_evidence_after_change_cannot_be_reused(self):
        self.load("discover")
        eid = next(iter(self.state()["evidence"]))
        self.propose()
        p = next(p for p in self.state()["proposals"].values() if p["kind"] == "change")
        send(self.h, "decide", {"proposal": p["id"], "digest": p["digest"], "decision": "approve", "reason": "change"})
        with self.assertRaises(Rejected):
            send(self.c, "discover", self.finding(evidence=[eid]))

    def test_cli_invalid_actor_and_version(self):
        result = subprocess.run([sys.executable, "-m", "loop_runtime", "--version"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)
        result = subprocess.run([sys.executable, "-m", "loop_runtime", "--root", str(self.root), "status", "DEMO"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("token-file", result.stderr)

    def fresh(self, policy=None, goal=None, adapter_root=None):
        self.root = self.temp / ("fresh-" + uuid.uuid4().hex)
        Store.initialize(self.root, policy or example_policy())
        self.c = self.client("controller"); self.h = self.client("human"); self.r = self.client("runner")
        self.worker = Runner(self.r, adapter_root or ROOT, allow_trusted=True)
        return send(self.c, "create", {"goal": goal or example_goal(), "repo": str(self.repo), "commit": self.commit, "paths": ["cups.csv"]})

    def test_each_budget_dimension_is_enforced_before_start(self):
        for dimension in ("jobs", "seconds", "tokens", "cost_microusd"):
            policy = example_policy()
            policy["limits"][dimension] = 0
            if dimension in ("tokens", "cost_microusd"):
                policy["adapters"]["explorer"][dimension] = 1
            self.fresh(policy)
            state = send(self.c, "tick")
            jid = next(iter(state["jobs"]))
            state = send(self.r, "claim", {"job": jid})
            with self.subTest(dimension=dimension):
                self.assertEqual(state["jobs"][jid]["status"], "budget_blocked")
                self.assertEqual(state["spent"]["jobs"], 0)

    def test_poc_budget_does_not_suppress_critical_warning(self):
        policy = example_policy(); policy["limits"]["pocs"] = 0
        self.fresh(policy)
        send(self.c, "discover", self.finding(severity="critical"))
        state = send(self.c, "tick")
        jid = next(iter(state["jobs"]))
        state = send(self.r, "claim", {"job": jid})
        self.assertEqual(state["jobs"][jid]["status"], "budget_blocked")
        self.assertTrue(self.c._risk_blockers(state))

    def test_stage_exploration_budget_enforced(self):
        policy = example_policy(); policy["stage_exploration_limits"]["discover"]["jobs"] = 0
        self.fresh(policy)
        state = send(self.c, "tick")
        state = send(self.r, "claim", {"job": next(iter(state["jobs"]))})
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["exploration_spent"]["jobs"], 0)

    def test_human_can_extend_exhausted_budget_without_policy_edit(self):
        policy = example_policy(); policy["limits"]["jobs"] = 0
        self.fresh(policy)
        state = send(self.c, "tick"); jid = next(iter(state["jobs"]))
        send(self.r, "claim", {"job": jid})
        new = copy.deepcopy(policy["limits"]); new["jobs"] = 10
        self.propose("budget", {"limits": new})
        self.approve()
        state = send(self.r, "claim", {"job": jid})
        self.assertEqual(state["jobs"][jid]["status"], "running")
        self.assertEqual(state["policy_hash"], digest(policy))

    def test_context_excludes_raw_source_by_default(self):
        state = send(self.c, "tick")
        context = self.c.context("DEMO", next(iter(state["jobs"])))
        self.assertNotIn("source_files", context)
        self.assertIn("source_manifest", context)
        self.assertNotIn(".credentials", json.dumps(context))

    def test_missing_ui_preview_fails_before_build(self):
        self.load("design")
        state = self.state(); state["goal"]["ui_required"] = True
        job = next(j for j in state["jobs"].values() if j["stage"] == "design" and j["kind"] == "execute")
        receipt, _ = self.c._load_receipt(state["evidence"][job["evidence"]]["path"])
        with self.assertRaises(Rejected):
            self.c._validate_result(state, job, job["result"], receipt)

    def test_untrusted_confidence_is_not_authority(self):
        self.load("discover")
        state = self.state()
        job = next(j for j in state["jobs"].values() if j["kind"] == "pre")
        output = {**job["result"], "confidence": 0.99}
        receipt, _ = self.c._load_receipt(state["evidence"][job["evidence"]]["path"])
        with self.assertRaises(Rejected):
            self.c._validate_result(state, job, output, receipt)

    def test_outcome_gap_creates_prepared_human_rework_decision(self):
        self.fresh(goal=example_goal(metrics=True))
        state = drive(self.c, self.worker, self.h)
        self.assertEqual(state["status"], "outcome_pending")
        state = send(self.h, "observe", {"measurements": {"time_saved": 2}, "source": "Synthetic operator measurement", "limitations": "Fixture, not real customer telemetry"})
        self.assertEqual(state["outcome"]["status"], "gap")
        self.assertEqual(state["status"], "outcome_gap")
        proposal = next(p for p in state["proposals"].values() if p["status"] == "pending")
        self.assertEqual(proposal["kind"], "change")
        self.assertTrue(proposal["blocking"])
        self.assertIn("measurement error", proposal["packet"]["counter_evidence"][0])
        self.approve()
        self.assertEqual(self.state()["stage"], "discover")
        self.assertEqual(self.state()["epoch"], 2)

    def test_metric_calculation_does_not_call_attestation_production_proof(self):
        self.load("delivered")
        state = self.state(); state["status"] = "outcome_pending"; state["stage"] = "deploy"
        state["goal"]["metrics"] = example_goal(metrics=True)["metrics"]
        self.h._observe(state, {"measurements": {"time_saved": 11}, "source": "test measurement", "limitations": "not independently verified"})
        self.assertEqual(state["outcome"]["status"], "human_attested_pass")
        self.assertIn("not independently verified", state["outcome"]["provenance"])
        self.assertEqual(state["stage"], "closed")

    def test_adapter_hash_drift_rejected_before_reservation(self):
        scripts = self.temp / "scripts"; (scripts / "examples").mkdir(parents=True)
        shutil.copyfile(ROOT / "examples/delivery_worker.py", scripts / "examples/delivery_worker.py")
        (scripts / "examples/delivery_worker.py").write_text("print('changed')")
        send(self.c, "tick")
        with self.assertRaises(Rejected):
            Runner(self.r, scripts, allow_trusted=True).run_once("DEMO")
        self.assertEqual(self.state()["spent"]["jobs"], 0)

    def test_invalid_worker_output_records_failure_and_bounded_repair(self):
        adapters = self.temp / "adapters"; (adapters / "examples").mkdir(parents=True)
        script = adapters / "examples/delivery_worker.py"
        script.write_text("import sys; from pathlib import Path; Path(sys.argv[3], 'result.json').write_text('not-json')")
        policy = example_policy()
        for role in ("design", "build", "deploy", "explorer"):
            policy["adapters"][role]["sha256"] = file_hash(script)
        self.fresh(policy, adapter_root=adapters)
        for _ in range(3):
            send(self.c, "tick"); self.worker.run_once("DEMO")
        state = self.state()
        self.assertEqual(len(state["jobs"]), 2)
        self.assertTrue(all(j["status"] == "failed" for j in state["jobs"].values()))
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(len(state["evidence"]), 2)

    def test_timeout_does_not_refund_reserved_budget(self):
        adapters = self.temp / "slow"; (adapters / "examples").mkdir(parents=True)
        script = adapters / "examples/delivery_worker.py"
        script.write_text("import time; time.sleep(5)")
        policy = example_policy(); policy["adapters"]["explorer"]["sha256"] = file_hash(script); policy["adapters"]["explorer"]["seconds"] = 1
        self.fresh(policy, adapter_root=adapters)
        send(self.c, "tick"); result = self.worker.run_once("DEMO")
        self.assertEqual(result["status"], "failed")
        state = self.state()
        self.assertEqual(state["spent"]["seconds"], 1)
        self.assertTrue(next(iter(state["jobs"].values()))["error"])

    def test_compare_routes_validated_discovery_without_silent_goal_change(self):
        send(self.c, "discover", self.finding())
        for _ in range(4):
            send(self.c, "tick"); self.worker.run_once("DEMO")
        state = self.state()
        d = next(iter(state["discoveries"].values()))
        self.assertEqual(d["recommendation"]["action"], "keep")
        self.assertEqual(state["goal_version"], 1)
        self.assertTrue(any(j["kind"] == "compare" for j in state["jobs"].values()))


if __name__ == "__main__":
    unittest.main()
