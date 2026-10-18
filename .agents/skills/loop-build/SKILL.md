---
name: loop-build
description: Execute an approved GSD plan with bounded test-driven repair, scope discipline and resumable evidence.
---

# loop-build

## Input
An approved native GSD plan selected by GSD, mapped acceptance, allowed paths, project rules and checks.

## Procedure
1. Pass `plan` immediately before implementation. Confirm workspace and existing dirty changes; never discard another actor's work.
2. Use test-first RED/GREEN/REFACTOR for behavior changes where executable tests are feasible. Reproduce a defect before fixing it. Explain alternative verification for non-code work.
3. Execute one cohesive task at a time in an isolated worktree when available. Parallelize only independent plans through GSD; Loop does not provide a cross-session lease manager.
4. Capture actual check executions with `python scripts/loop.py evidence <CHECK-ID>`. Preserve native GSD SUMMARY.md with affected acceptance IDs and evidence paths.
5. Classify failures: temporary tool failure, implementation defect, invalid assumption, scope conflict, permission/dependency issue. Retry transient failures with bounded backoff. After two identical failed attempts change hypothesis; after three distinct failed strategies make a decision packet.
6. On a spec/design problem, return to the owning phase and invalidate affected downstream artifacts. Never weaken tests, approvals or active rules to fit the implementation.
7. An uncertain external side effect is a reconciliation task, not a repeat action. Record operations with idempotency key, receipt and observed result.

## Output / exit
Code + tests + native GSD summary + evidence. Build completion is not release completion.
Use `loop-verify` for acceptance. If interrupted, write GSD progress then run the `loop-resume` handoff procedure.
