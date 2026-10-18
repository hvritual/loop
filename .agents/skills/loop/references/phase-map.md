# Phase map and ownership

| Logical phase | Native owner | Advisory capability | Loop exit gate |
|---|---|---|---|
| Discover | GSD context / project intake | Forge Idea, Deep Recon | discover |
| Specify | GSD requirements references | PRD / Spec | specify |
| Design | GSD Discuss / CONTEXT | UX / Architecture | design |
| Plan | GSD Plan Phase | targeted elicitation | plan |
| Build | GSD Execute Phase | no second dispatcher | plan before executing |
| Verify | GSD Verify | independent Review | verify / review |
| Integrate / Deploy / Observe | GSD Ship + existing platform | not BMAD Ship | release |
| Learn / Close | GSD phase closure | Project Context advice | learning / close |

Read `.loop/upstreams.lock.json` for exact packages. Use the official installer for native GSD command/agent transformations. Client-specific aliases and hooks differ; do not assume Claude hook coverage applies to Codex.

Intent, behavior spec, design and GSD progress are different authorities over different concerns. `plan-map` is a hash-bound coverage projection, not a task database. A new upstream decision invalidates the downstream bindings.

Human decisions: value/scope tradeoffs, preview approval, high risk/irreversible action, permissions, exceptions and active-rule promotion. Normal implementation and bounded repairs proceed without repeated permission requests.
