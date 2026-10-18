---
name: loop-learn
description: Convert delivery evidence into reviewable, bounded rule or skill candidates without automatic rule growth or self-approval.
---

# loop-learn

## Input
Actual outcomes, corrections, failed gates, incident evidence and decisions; not model guesses about what might be useful.

## Procedure
1. Classify the issue: one-off fact/documentation, repeated procedure/skill, repeated decision constraint/rule, tool defect/fix, or no change. Do not treat every failure as a new rule.
2. Require three independent incidents for a general rule/skill, or one critical incident with explicit severity rationale. Deduplicate references; repeated retries of one defect are one incident.
3. Consult `bmad-project-context` in advisory/audit mode. It may recommend a change but may not silently rewrite AGENTS.md or overwrite the active rules.
4. Write a candidate using `assets/learning.json`: origin evidence hashes, mechanism, applicability, counterexample, positive/negative evaluation, owner and review date.
5. Test the candidate against its useful case and its counterexample. Compare with the old behavior. Record actual evaluation evidence and avoid universal claims from one successful run.
6. Propose a separate governance change with human/independent review bound to the candidate snapshot. Only after approval incorporate the minimal rule or skill and re-run regression/compatibility checks.
7. Retire redundant or expired rules. Keep AGENTS.md an index and respect the rule budget. Lessons which do not generalize stay in the task record.

## Output / gate
Proposed candidate, approved separately, or a documented no-change disposition. `python scripts/loop.py learning <path>` checks the contract, not the wisdom of the proposed lesson.

Close using `assets/closure.json`; an empty blocker list must describe reality, not desired progress.
