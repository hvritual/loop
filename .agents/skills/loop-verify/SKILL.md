---
name: loop-verify
description: Check implementation against every acceptance criterion using current-source execution evidence and a separate review pass.
---

# loop-verify

## Input
Spec/design/plan mapping, code, raw check output, native GSD summaries.

## Procedure
1. Run all required checks from the reviewed registry. Bind each acceptance ID to a real result.json in `evidence-index.json` using `assets/evidence-index.json`.
2. Pass `verify`. Missing, failed, wrong-command, modified or stale evidence is failure. Regenerate evidence after source/rules/tests/spec changes.
3. Invoke native GSD verification and installed `bmad-review` as appropriate. The second reviewer gets the frozen goal/spec/diff/evidence, not an instruction to defend the implementer's conclusions.
4. Review scope, actual user journey, error/recovery states, architecture, security and test meaning. A passing broad unit suite does not alone prove that every acceptance behavior was tested.
5. Write `review.json` and its report. The reviewer must actually be a different reviewer; a second paragraph by the same executor is not independent review. Record missing reviewer capacity as a blocker, not a fabricated identity.
6. Resolve critical/high findings and rerun affected checks. Lower-severity debt needs an owner and tracking reference. Do not suppress findings in order to close the task.

## Output / gate
Run `python scripts/loop.py gate <ID> verify` then `... gate <ID> review`.
The script validates provenance fields and freshness, not reviewer identity or semantic truth. Protected platform review/CI supplies the hard boundary.

Review artifact: `assets/review.json`. Populate it from an actual separate review; a different name is not proof of independence.
