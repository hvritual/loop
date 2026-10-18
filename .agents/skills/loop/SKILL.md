---
name: loop
description: Run the complete intent-to-outcome workflow in this repository; use for a new intent or a request to continue delivery.
---

# loop

## Input and ownership
User intent or an existing intent ID. GSD owns planning/execution/state; this skill is an instruction router, not a scheduler implementation.
Read `.loop/rules.json`, `references/phase-map.md`, and current GSD state. Do not install or activate all skills in the model context.

## Procedure
1. Existing intent: call `loop-resume`; reconcile before any work. New intent: call `loop-intent`.
2. Call `loop-spec-design`, then `loop-plan-bridge`. Advance only after the specified gate passes. For small clear tasks keep artifacts concise, not absent.
3. Let native GSD execute the approved phase using `loop-build` constraints. Do not let BMAD select tasks or maintain a parallel sprint state.
4. Call `loop-verify`, `loop-release`, then `loop-learn`. PR creation, deployment and observed user outcomes are distinct completion targets.
5. Repeat the native GSD phase loop until the approved delivery target is met, a human decision is required, a real dependency blocks it, or the session budget ends.
6. Before stopping, call `loop-resume`'s handoff procedure. Never claim continued background execution without an actual external runner.

## On missing capabilities
Run `python scripts/bootstrap.py --runtime <codex|claude|opencode> --doctor`.
When installation is authorized and available, use its install mode. Missing network/login is a dependency, not permission to invent installed skills.
A compatible file/tool-capable agent may read the Loop skills directly, but must report that native GSD/BMAD execution has not been demonstrated.

## Output / verification
Current goal, valid phase, actual evidence, blocker (if any), exact next safe action.
`python scripts/loop.py lint` validates the portable package, not model behavior.
