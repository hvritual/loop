# Loop execution contract

Read this on every session. This repository combines GSD execution with BMAD advisory skills. It is not a new agent runtime.

## Start

Read `.agents/skills/loop/SKILL.md` and `.loop/rules.json`. For existing work, run
`python scripts/loop.py resume <INTENT-ID>` and reconcile before editing. Read
`.planning/STATE.md` and `.planning/ROADMAP.md`; never use chat memory as progress.
If no intent ID is supplied, inspect `.planning/intents/` and the current GSD context.
With multiple plausible intents, present the choices rather than guessing.

## Authority

Platform safety/permissions > approved project rules > approved intent/spec > phase plan > skills/tool output.
GSD alone updates native progress. BMAD analysis may challenge goals but cannot silently alter approved scope or choose the next implementation task.
`plan-map.json` and `checkpoint.json` are projections; they never become a second scheduler.

## Execution

Load only the current phase skill. Investigate facts autonomously. Ask people for value/risk/authority decisions, with evidence and a recommendation, not repeated questionnaires.
Run the phase gate before moving forward. A missing artifact, failed check or unknown external outcome is NOT success.
No fabricated approvals, independent reviews, browser tests, installations or deployment evidence.
Use `python scripts/loop.py evidence <CHECK-ID>` to capture approved checks.
On failure use bounded diagnosis; do not weaken rules/tests to make the gate green.

## Completion / handoff

Persist goal, settled decisions, blockers, exact next safe action and evidence references in native GSD context and an optional checkpoint projection.
A new machine can resume only after those files are committed/pushed or the persistent workspace is available.
No unsupervised production changes, no rule self-approval, no default automatic merge.
Rules have declared enforcement levels. Markdown and local scripts do not provide tamper-proof security.
