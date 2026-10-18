---
name: loop-release
description: Complete the explicitly approved PR, staging or production target with real receipts, runtime checks and recovery instructions.
---

# loop-release

## Input
Passing review and approved delivery target. No production credentials or deployment platform is implied by this toolkit.

## Procedure
1. Use native GSD ship/PR preparation. Keep integration, deployment and observed outcome distinct.
2. Before each external mutation confirm scope, target revision, authorization, expected result and recovery. Use the provider's idempotency support when available.
3. Create/update the PR and read back its head, CI and review state. Do not merge by default. Repository settings must actually enforce required checks/reviews; a workflow file does not activate branch protection.
4. For staging/production targets, require approved environment/revision, migration handling, smoke checks and rollback/recovery. Inspect the real deployed version and collect actual monitoring/user-flow evidence.
5. Record receipts, external references and observation timestamps in `release.json` using `assets/release.json`. If an operation response is lost, read the external system before attempting it again.
6. Run release gate, then `loop-learn`; write closure with no hidden blockers. Do not downgrade production to PR-only simply because deployment access is missing.

## Output / gate
`python scripts/loop.py gate <ID> release`, then `... gate <ID> close` after retrospective disposition.
An external operation record is not proof by itself; inspect the external system. A connector outage remains explicit.

Persist operation outcomes with `assets/operations.json`; unknown outcomes force reconciliation.
