---
name: loop-intent
description: Clarify an incomplete feature idea with evidence, alternatives and prepared human decisions before specification.
---

# loop-intent

## Input
Original request; available code/docs/user research; `.loop/rules.json`.
Use `assets/intent.json` as the output skeleton, not as a questionnaire.

## Investigation loop
1. Restate the actor, situation, problem and intended outcome. Separate a requested implementation (e.g. Excel import) from the real result.
2. Search the actual repository first, then primary external sources when needed. Record source/revision/date and verified/assumed/unknown/conflicting status. Code proves implemented behavior, not user value.
3. Consult installed `bmad-deep-recon` for consequential unknowns and `bmad-forge-idea` for pressure-testing. Pass existing answers explicitly; do not make the user reconfirm what they already settled.
4. Find at least one counterexample and one alternative, including doing nothing or reusing existing capability. Do not invent stakeholder interviews, metrics or market facts.
5. Rank gaps by impact, uncertainty and rework risk. Resolve discoverable facts yourself. Ask at most one high-impact value/authority question at a time, with the recommendation, alternatives and consequences.
6. Re-evaluate after every answer. Capture decisions and rejected routes. Stop exploring when extra research is unlikely to change the decision; record unresolved nonblocking assumptions with owners and validation plans.
7. Valid exits: ready for specification, more research, waiting for a specific decision, rejected/deferred. Do not force a killed idea into Build.

## Output
`.planning/intents/<ID>/intent.json`; preserve decision source text under `.planning/requests/` without secrets or unrelated personal data.
The approval binds the canonical JSON digest excluding its `approval` object. User authority must be real; local fields alone do not authenticate it.
`python scripts/loop.py gate <ID> discover` is necessary, not sufficient to prove discovery quality.
Load `references/decision-packet.md` only when escalating.
