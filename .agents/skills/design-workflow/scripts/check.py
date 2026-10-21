"""Read-only stage gate; does not mutate progress or manufacture approvals."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from loop_runtime.runtime import Runtime
from loop_runtime.model import binding, require
p = argparse.ArgumentParser()
p.add_argument("--root", type=Path, required=True)
p.add_argument("--token-file", type=Path, required=True)
p.add_argument("intent")
a = p.parse_args()
rt = Runtime(a.root, a.token_file.read_text().strip())
try:
    state = rt.resume(a.intent)["state"]
    jobs = [j for j in state["jobs"].values() if j["stage"] == "design" and j["binding"] == binding(state) and j.get("discovery") is None]
    for kind in ("pre", "execute", "verify", "post"):
        candidates = sorted([j for j in jobs if j["kind"] == kind], key=lambda j: j["sequence"])
        require(candidates and candidates[-1]["status"] == "succeeded", "missing or failed " + kind)
    print("design: evidence gate passed; Human authority is still checked by the controller")
finally:
    rt.close()
