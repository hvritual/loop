"""Offline integration fixture, NOT an LLM or evidence of real customer value."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

context_path, workspace, output = map(Path, sys.argv[1:])
context = json.loads(context_path.read_text())
artifacts = output / "artifacts"
artifacts.mkdir(exist_ok=True)
rows = list(csv.DictReader((workspace / "cups.csv").open()))
kind, stage = context["kind"], context["stage"]
result = {"protocol": 1, "findings": []}
if kind in ("pre", "post"):
    result.update(reviewed=["requirements", "alternatives", "boundaries", "counterexamples", "outcomes"],
                  notes=f"Synthetic fixture: inspected {len(rows)} rows. No claim that real-world unknowns are exhausted.")
elif kind == "compare":
    result["recommendation"] = {"action": "keep", "reason": "Fixture evidence does not establish a superior route; keep the baseline"}
elif kind == "experiment":
    measurement = {"records": len(rows), "customers": len({r['customer'] for r in rows}),
                   "credential_file_present": (context_path.parent / "authority.json").exists()}
    (artifacts / "experiment.json").write_text(json.dumps(measurement))
    result["conclusion"] = "Measured the frozen dataset; experiment scope is an offline fixture only."
elif stage == "discover":
    result["handoff"] = {"requirements": ["Aggregate cups per customer from the frozen CSV"],
                         "assumptions": ["Rows are synthetic and authorized for this fixture"],
                         "alternatives": ["Keep raw CSV baseline", "Produce a deterministic customer summary"]}
elif stage == "design":
    result["handoff"] = {"architecture": "Offline CSV -> stable customer aggregation -> review package",
                         "tasks": ["Read explicit snapshot", "Aggregate", "Independently compare", "Package"]}
elif stage == "build":
    totals = defaultdict(int)
    for row in rows:
        totals[row["customer"]] += int(row["cups"])
    with (artifacts / "summary.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["customer", "cups"])
        writer.writerows(sorted(totals.items()))
    result["handoff"] = {"summary": "Generated deterministic customer totals", "changed_files": ["summary.csv"],
                         "test_plan": "Independent verifier recomputes expected totals from source rows"}
elif stage == "deploy":
    source = context_path.parent / "upstream" / "build" / "artifacts" / "summary.csv"
    (artifacts / "summary.csv").write_bytes(source.read_bytes())
    result["handoff"] = {"target": "review-package", "release_notes": "Synthetic offline fixture; no production write",
                         "rollback": "Discard this isolated review package; original source is unchanged",
                         "observation_plan": "Real business outcomes require separately attributed measurements"}
else:
    raise SystemExit("unsupported fixture task")
(output / "result.json").write_text(json.dumps(result))
