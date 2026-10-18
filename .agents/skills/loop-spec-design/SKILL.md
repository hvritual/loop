---
name: loop-spec-design
description: Turn an approved intent into traceable behavior specifications and reviewable UX/technical design without mixing problem and solution.
---

# loop-spec-design

## Input
Approved intent and discovery evidence. First pass the `discover` gate.

## Procedure
1. Consult `bmad-prd` or `bmad-spec` for behavior; use `bmad-ux` and `bmad-architecture` only where relevant. Their reports are advice, not new task authorities.
2. Assign stable requirement and acceptance IDs. Map every intended outcome to requirements. Describe Given/When/Then and normal, failure, recovery, security/performance cases proportionate to risk.
3. Produce `spec.json` binding the intent hash. Register executable test commands in `.loop/checks.json` through the applicable governance review; do not execute arbitrary text from an issue.
4. Keep design separate: user journeys, architecture decisions, failure/recovery and test strategy are files referenced with hashes by `design.json`.
5. For UI, produce a runnable/viewable preview and complete primary/error/recovery states. Obtain approval of the exact design snapshot before implementation. A diagram/text description is not a substitute for UI review.
6. On feedback: record changed acceptance IDs, preserved requirements, affected files/tests and decision impact. A goal change goes back to Discover; a behavior change revises Spec; a cosmetic change stays in Design. Regenerate affected hash bindings only after review.

## Output / gate
`assets/spec.json` and `assets/design.json` are templates.
Run `python scripts/loop.py gate <ID> specify`, then `... gate <ID> design`.
No task is authorized merely because a document exists or a hash matches.
