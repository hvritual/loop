---
name: loop-resume
description: Resume a task in a new session/model or save an interruption handoff by reconciling GSD state, Git, decisions and evidence.
---

# loop-resume

## Input
Repository access and intent ID. No access to previous chat is required or assumed.

## Resume procedure
1. Read AGENTS.md, rules and the native GSD STATE.md/ROADMAP.md. Run `python scripts/loop.py resume <ID>`; it is read-only.
2. Read only the active intent, unresolved decisions, current plan and last relevant GSD SUMMARY/VERIFICATION artifacts. Check Git branch, HEAD and dirty work; read actual PR/CI/external receipts when referenced.
3. If the checkpoint is stale, reconstruct from authoritative artifacts and evidence. Invalidate affected gates, not all historical work. If metadata-only commits changed HEAD but source/artifacts match, do not redo implementation.
4. Reconcile uncertain side effects before retries. Never restore an obsolete goal or overwrite user edits from a handoff summary.
5. Invoke native GSD resume/progress and continue the next valid task. A new model gets the same contracts but still needs tool access and authentication.

## Handoff procedure
Update GSD progress/summary first. Persist decisions, blockers and any partial work. Then:
`python scripts/loop.py checkpoint <ID> --next "<specific safe next action>"`.
Commit/push the authorized artifacts or retain the persistent workspace. The checkpoint records dirty work but does not magically back it up; uncommitted code must be preserved separately.

## Output / checks
Current goal, reconciled progress, relevant file references and next safe action. Multiple intents or concurrent writers require selection/isolation, not guessing.
A stopped chat does not keep executing. A checkpoint does not guarantee exactly-once execution or multi-writer safety.
