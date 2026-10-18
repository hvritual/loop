# Loop

## Core Value
Transform incomplete software intentions into evidenced, reviewable delivery while preserving intent and progress across sessions.

## Requirements
See `.planning/REQUIREMENTS.md`. GSD owns the roadmap and plan execution; BMAD provides advisory skills.

## Constraints
No self-developed orchestration service. Use real upstream installers and pinned versions. Do not fabricate installed capabilities, user approvals or production evidence. Source repository was empty at bootstrap.

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| GSD is sole progress owner | Avoid duplicate state and scheduling | Adopted in implementation |
| BMAD is advisory allowlist | Reuse expertise without competing build flow | Adopted; live installer verification remains separate |
| Thin deterministic scripts | Validate contracts/evidence without building a runtime | Implemented and unit tested |
| Independent platform enforcement | Models can edit local instructions | Settings need real external application/verification |
