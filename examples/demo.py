"""Run a synthetic example. Default pauses at Human review; --test-auto-approve is test-only."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop_runtime.model import DEFAULT_LIMITS, EXPLORE_LIMITS, STAGES, file_hash
from loop_runtime.runtime import Runtime
from loop_runtime.runner import Runner
from loop_runtime.store import Store

ROOT = Path(__file__).resolve().parents[1]


def example_policy(mode="trusted", image=None):
    adapters = {}
    routing = {"discover": "design", "design": "design", "build": "build", "deploy": "deploy", "explorer": "explorer", "verifier": "verifier"}
    for role in ("design", "build", "deploy", "explorer", "verifier"):
        script = "examples/verification_worker.py" if role == "verifier" else "examples/delivery_worker.py"
        adapters[role] = {"role": role, "mode": mode, "script": script, "sha256": file_hash(ROOT / script),
                          "scope": "fixture", "seconds": 10, "tokens": 0, "cost_microusd": 0}
        if mode == "docker":
            adapters[role]["image"] = image
    return {"mode": "B", "limits": DEFAULT_LIMITS.copy(), "exploration_limits": EXPLORE_LIMITS.copy(),
            "max_depth": 2, "max_candidates": 3, "max_attempts": 2, "no_gain_limit": 2, "lease_seconds": 60,
            "routing": routing, "adapters": adapters,
            "stage_exploration_limits": {s: {"jobs": 6, "seconds": 300, "tokens": 20000, "cost_microusd": 0, "pocs": 2} for s in STAGES}}


def example_goal(metrics=False):
    return {"outcome": "Deliver a reproducible customer cups summary review package",
            "non_goals": ["No production writes", "No real-model quality claim"],
            "constraints": ["Only explicit source snapshot", "Human approves frozen goal, design and release"],
            "criteria": {s: [{"id": s.upper() + "-1", "description": "Verify the frozen fixture contract for " + s}] for s in STAGES},
            "metrics": [{"id": "time_saved", "operator": ">=", "target": 10, "unit": "minutes"}] if metrics else []}


def create_source(path):
    path.mkdir()
    (path / "cups.csv").write_bytes((ROOT / "examples/cups.csv").read_bytes())
    for args in (["init", "-q"], ["add", "cups.csv"], ["-c", "user.name=Loop Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Synthetic fixture"]):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"]).decode().strip()


def credentials(root, role):
    return (root / ".credentials" / (role + ".token")).read_text().strip()


def send(rt, action, data=None, intent="DEMO"):
    try:
        revision = rt.get(intent)["revision"]
    except ValueError:
        if action != "create":
            raise
        revision = 0
    return rt.command(intent, action, data or {}, key="op-" + uuid.uuid4().hex, expected=revision)


def drive(controller, runner, human=None, limit=100):
    """Finite driver; no background loop and no fabricated Human consent in normal mode."""
    for _ in range(limit):
        state = send(controller, "tick")
        if state["status"] == "waiting_human":
            if human is None:
                return state
            for proposal in state["proposals"].values():
                if proposal["status"] == "pending" and proposal["blocking"]:
                    send(human, "decide", {"proposal": proposal["id"], "digest": proposal["digest"], "decision": "approve", "reason": "SIMULATED TEST HUMAN; not a real approval"})
            continue
        if state["stage"] == "closed" or state["status"] in ("outcome_pending", "outcome_gap"):
            return state
        ran = runner.run_once("DEMO")
        if not ran["ran"] and state["status"] == "blocked":
            return state
    raise RuntimeError("finite driver step budget exhausted")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path)
    p.add_argument("--test-auto-approve", action="store_true")
    p.add_argument("--docker-image")
    args = p.parse_args()
    root = args.directory or Path(tempfile.mkdtemp(prefix="loop-demo-"))
    root.mkdir(parents=True, exist_ok=True)
    commit = create_source(root / "source")
    state_root = root / "state"
    Store.initialize(state_root, example_policy("docker" if args.docker_image else "trusted", args.docker_image))
    controller = Runtime(state_root, credentials(state_root, "controller"))
    worker = Runtime(state_root, credentials(state_root, "runner"))
    human = Runtime(state_root, credentials(state_root, "human"))
    try:
        send(controller, "create", {"goal": example_goal(), "repo": str(root / "source"), "commit": commit, "paths": ["cups.csv"]})
        state = drive(controller, Runner(worker, ROOT, allow_trusted=not args.docker_image), human if args.test_auto_approve else None)
        controller.export("DEMO", root / "export")
        expected = "delivered" if args.test_auto_approve else "waiting_human"
        if state["status"] != expected:
            raise RuntimeError("demo did not reach expected " + expected + ": " + state["status"])
        print(json.dumps({"root": str(root), "status": state["status"], "stage": state["stage"],
                          "jobs": len(state["jobs"]), "evidence": len(state["evidence"]),
                          "human_approvals": "SIMULATED" if args.test_auto_approve else "NONE; awaiting real review",
                          "scope": "fixture; no production or real-model validation"}, indent=2))
    finally:
        controller.close(); worker.close(); human.close()


if __name__ == "__main__":
    main()
