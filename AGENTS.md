# Loop Full Runtime execution contract

This replaces the legacy GSD-only scheduler contract at 01dab3068c2f5810e3220541c8afabaead8007e3.
Read `.agents/skills/intent-to-outcome-closure/SKILL.md`, then only the current stage's workflow.

## Authority
Human intent and approved safety constraints > pinned runtime policy > versioned goal/acceptance > approved design > worker output.
The SQLite controller is the sole scheduler. GSD/BMAD may supply advisory material, never another progress authority.
Mode B: autonomous research and bounded validation; Human alone approves goal/scope/design/budget/release changes.
Never manufacture Human consent, independent review, production evidence, confidence percentages or model quality results.

## Execution
Use `python -m loop_runtime ... resume <ID>` before continuing. Reconcile unknown jobs before retry.
Design owns Discover and Design. Build and Deploy are separate agents. Exploration is shared, not a fourth scheduler.
Every stage runs pre -> execute -> independent verify -> post. Critical discoveries block affected execution even after budget exhaustion.
Keep discoveries separate from committed work. A validated alternative triggers comparison, not automatic scope expansion.
Use only registered, content-pinned adapters. Docker unavailable means blocked, never a fallback to trusted execution.
The `trusted` adapter is for reviewed host programs and is NOT a security sandbox.
Do not supply `.credentials/human.token` to Coding Agents or workers. Human review tokens belong to the operator.

## Delivery and recovery
Collect actual tests, exit codes, raw artifacts, exact source binding and decision digests. Failed checks remain failed evidence.
Release target in this version is `review-package`; production writes are deliberately disabled.
A completed delivery is not proof of business benefit. Metric gaps produce a Human-reviewed rework proposal.
Tests marked fixture/SIMULATED do not count as real approvals or real-model evaluations.
Run `python -m unittest discover -s tests -v` and `python tools/check_skills.py` before proposing completion.
Do not auto-merge main, publish a package, change repository permissions, or discard unrelated branches.
