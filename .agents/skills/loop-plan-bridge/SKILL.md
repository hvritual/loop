---
name: loop-plan-bridge
description: Hand approved BMAD-assisted specifications to native GSD planning with one progress authority and complete acceptance coverage.
---

# loop-plan-bridge

## Input
Approved intent, spec/design artifacts, their hashes and required test commands.

## Procedure
1. Pass `design`. Invoke the installed native GSD discuss/plan-phase skill; discover the actual command spelling for the client instead of guessing aliases.
2. Put settled choices in the native phase CONTEXT.md. Reference the canonical intent/spec/design files; do not copy another authoritative PRD into REQUIREMENTS.md.
3. Produce native `.planning/phases/<phase>/<phase>-<plan>-PLAN.md` tasks with files, action, verify and done conditions. Slice vertically into independently testable increments and declare dependencies/allowed paths.
4. Create `plan-map.json` using `assets/plan-map.json`: requirement/acceptance-to-native-plan mapping plus plan hashes. It has NO task status. GSD alone updates execution progress.
5. Run the plan gate. Repair omissions, over-broad scope, cycles and stale plans. Ask only for choices that change approved scope, risk or authority.
6. Attach `loop-build` and `loop-verify` to the current executor's explicit context. A global rule is not assumed to have reached every subagent.

## Output / gate
Native GSD plans/context and a validated mapping. Run `python scripts/loop.py gate <ID> plan`.
Do not start `bmad-build`, `bmad-build-auto`, sprint planning, PO/ticket orchestration or any second implementation dispatcher.
