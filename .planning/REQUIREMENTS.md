# Requirements — Loop bootstrap

| ID | Required result | Verification |
|---|---|---|
| LOOP-01 | Evidence-driven intent clarification with alternatives and prepared decisions | loop-intent + eval cases |
| LOOP-02 | Goal → requirements → acceptance → native GSD plan → evidence traceability | contract tests |
| LOOP-03 | One GSD state owner, no competing BMAD scheduler | installer filtering + plan-map rejection tests |
| LOOP-04 | Native multi-client installer integration without copying raw GSD agents | three-runtime install CI |
| LOOP-05 | Current-source executed verification evidence, negative-path failure | evidence/gate tests |
| LOOP-06 | New-session recovery and stale-state/uncertain-side-effect reconciliation | checkpoint/resume tests |
| LOOP-07 | Rule/Skill proposals with evidence, counterexamples and approval | learning tests + governed adoption |
| LOOP-08 | CI and external permission boundaries stated truthfully | CI + ruleset readback |
| LOOP-09 | Real-model semantic improvement and cross-model continuation | live pilot, not synthetic tests |

Detailed contracts are in the owning skill assets and docs/CONTRACTS.md. Do not treat an existing Markdown requirement as evidence of completion.
