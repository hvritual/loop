"""Independent deterministic verifier for the bundled fixture (different producer code/digest)."""
import csv
import json
import sys
from pathlib import Path

context_path, workspace, output = map(Path, sys.argv[1:])
context = json.loads(context_path.read_text())
previous = context_path.parent / "previous"
producer = json.loads((previous / "result.json").read_text())
rows = list(csv.DictReader((workspace / "cups.csv").open()))
artifacts = output / "artifacts"
artifacts.mkdir(exist_ok=True)
resolved = []
if context["discovery"]:
    measured = json.loads((previous / "artifacts" / "experiment.json").read_text())
    passed = measured["records"] == len(rows) and measured["customers"] == len(set(r["customer"] for r in rows))
    if context["discovery"]["question"] == "Fixture: ensure input contains no credential file" and not measured["credential_file_present"]:
        resolved = [context["discovery"]["id"]]
elif context["stage"] in ("build", "deploy"):
    actual = {r["customer"]: int(r["cups"]) for r in csv.DictReader((previous / "artifacts" / "summary.csv").open())}
    expected = {customer: sum(int(r["cups"]) for r in rows if r["customer"] == customer) for customer in {r["customer"] for r in rows}}
    passed = actual == expected
elif context["stage"] == "discover":
    passed = len(producer["handoff"]["alternatives"]) >= 2 and len(rows) > 0
else:
    passed = "Offline CSV" in producer["handoff"]["architecture"] and len(producer["handoff"]["tasks"]) <= 4
checks = [{"id": c["id"], "passed": passed, "artifact": "artifacts/checks.json"} for c in context["criteria"]]
(artifacts / "checks.json").write_text(json.dumps({"checks": checks, "dataset_rows": len(rows), "scope": "fixture"}))
(output / "result.json").write_text(json.dumps({"protocol": 1, "checks": checks, "findings": [], "resolved_discoveries": resolved}))
