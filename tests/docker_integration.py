"""Real Docker isolation probe. No mocks, no fallback; run separately from portable unit tests."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from examples.demo import create_source, credentials, example_goal, example_policy, send
from loop_runtime.model import file_hash
from loop_runtime.runtime import Runtime
from loop_runtime.runner import Runner
from loop_runtime.store import Store

PROBE = r'''
import json, os, socket, sys
from pathlib import Path
ctx, work, out = map(Path, sys.argv[1:])
network_denied = False
try:
    with socket.create_connection(("1.1.1.1", 443), timeout=0.3):
        pass
except OSError:
    network_denied = True
root_write_denied = False
try:
    Path("/etc/loop-write-probe").write_text("must fail")
except OSError:
    root_write_denied = True
probe = {"uid": os.getuid(), "network_denied": network_denied,
         "root_write_denied": root_write_denied,
         "host_secret_absent": "LOOP_SECRET_TEST" not in os.environ,
         "control_credentials_absent": not Path("/input/.credentials").exists(),
         "docker_socket_absent": not Path("/var/run/docker.sock").exists()}
(out / "artifacts").mkdir()
(out / "artifacts").chmod(0o777)  # Permit the unprivileged CI host to remove fixture outputs.
(out / "artifacts/probe.json").write_text(json.dumps(probe))
(out / "result.json").write_text(json.dumps({"protocol": 1, "findings": [],
    "reviewed": ["requirements", "alternatives", "boundaries", "counterexamples", "outcomes"],
    "notes": "Real Docker isolation probe; not a real-model evaluation"}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="loop-docker-"))
    c = r = None
    try:
        commit = create_source(root / "source")
        (root / "probe.py").write_text(PROBE)
        policy = example_policy("docker", args.image)
        policy["adapters"]["explorer"].update(script="probe.py", sha256=file_hash(root / "probe.py"))
        Store.initialize(root / "state", policy)
        c = Runtime(root / "state", credentials(root / "state", "controller"))
        r = Runtime(root / "state", credentials(root / "state", "runner"))
        send(c, "create", {"goal": example_goal(), "repo": str(root / "source"), "commit": commit, "paths": ["cups.csv"]})
        send(c, "tick")
        os.environ["LOOP_SECRET_TEST"] = "must-not-reach-worker"
        result = Runner(r, root).run_once("DEMO")
        assert result["status"] == "succeeded", result
        receipt = root / "state" / result["receipt"]
        probe = json.loads((receipt.parent / "artifacts/probe.json").read_text())
        assert probe["uid"] == 65534, probe
        assert all(v is True for k, v in probe.items() if k != "uid"), probe
        c.resume("DEMO")
        print(json.dumps({"result": "pass", "image": args.image, "probe": probe,
                          "receipt_sha256": file_hash(receipt), "scope": "real Docker integration; synthetic task"}, indent=2))
    finally:
        if c: c.close()
        if r: r.close()
        os.environ.pop("LOOP_SECRET_TEST", None)
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
