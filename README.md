# Loop — 意图到结果的可恢复软件交付工作流

**GSD 唯一推进任务，BMAD 提供专业分析，Rules 约束边界，证据决定是否完成。**

这是可安装的仓库工作流与 Skills 集成包，不是新开发的 Orchestrator、后台服务或模型 API。业务开发由已有 Coding Agent + GSD 执行。Python 脚本只做契约校验、执行证据采集和上下文交接。

## 从这里开始

环境：Git、Python 3.11+。安装上游还需要 Node.js 22+、npm、uv 和网络。

```sh
# 不需要模型账号或网络：验证 Loop 自身
python -m unittest discover -s tests -v
python scripts/loop.py lint
python scripts/demo.py

# 在目标仓库安装固定版本的原生工作流（选一个客户端）
python scripts/bootstrap.py --runtime codex
# 或 --runtime claude / --runtime opencode
python scripts/bootstrap.py --runtime codex --doctor
```

安装后在该仓库打开 Coding Agent，输入：

> 阅读 AGENTS.md，使用 loop 工作流处理这个意图：……。先调查和澄清，不要直接编码。在已授权范围内持续推进；需要我决定时提供证据、推荐和影响。

新会话输入：

> 阅读 AGENTS.md，使用 loop-resume 恢复 <INTENT-ID>。先对账真实仓库、GSD 状态和验证证据，再继续下一项有效任务。

Loop 自有 Skills 的权威目录是 `.agents/skills/loop*/`。Claude 使用生成的薄入口引用同一份内容。其他能读仓库和调用工具的模型可显式加载这些文件；这不等于它们已经通过原生客户端兼容测试。

## 开发流程

**意图 → 事实调查与反例 → Intent Brief → 行为规格 → 可审阅设计 → GSD 规划 → 执行与修复 → 验收与独立审查 → 集成/部署/观察 → 规则与 Skill 候选 → 下一轮。**

| 能力 | 落地内容 |
|---|---|
| 更好的理解 | actor / scenario / problem / outcome；证据状态；替代方案；单个高价值决策；可拒绝错误意图 |
| 更准的规划 | outcome → requirement → acceptance → 原生 GSD PLAN → evidence；上游变更使下游引用失效 |
| 更自主的执行 | 由 GSD 执行；BMAD 不维护第二份 sprint/task 状态；有界修复；独立任务可继续 |
| 更可靠的验收 | 检查真实命令、退出码、日志哈希和代码/规则/测试版本；UI 预览与审查；外部回执对账 |
| 有依据的沉淀 | 事件 → 候选 → 正反例评估 → 独立/人工审批 → 合入 → 定期复查，不自动堆积 Rules |
| 跨会话 | GSD STATE/ROADMAP/PLAN/SUMMARY 是进度权威；checkpoint 是可丢弃投影；恢复先对账 |

## 常用命令

```sh
python scripts/loop.py gate <ID> discover
python scripts/loop.py gate <ID> plan
python scripts/loop.py evidence unit --intent <ID>
python scripts/loop.py gate <ID> verify
python scripts/loop.py checkpoint <ID> --next "核对 PR 的当前 CI，然后继续下一计划"
python scripts/loop.py resume <ID>
python scripts/loop.py learning .planning/intents/<ID>/lesson.json
```

完整门禁：`discover / specify / design / plan / verify / review / release / close`。这些是 Loop 的真实 CLI 命令；GSD/BMAD 的原生命令由官方安装器按客户端生成，不假设不同客户端使用相同前缀。

## 目录

```text
.agents/skills/loop*/        单一职责 Skills、参考和模板
.loop/                      固定上游版本、Rules、允许执行的检查
.planning/                  GSD 进度，以及意图/规格/设计/证据产物
scripts/                    薄校验与交接工具，不做模型编排
tests/                      正常与失败路径测试
evals/                      意图理解的真实模型评测用例与评分方法
docs/                       架构、契约、运维和验证边界
.github/                    CI、PR 模板、Issue 模板、治理设置候选
```

## 不能混淆的边界

自动化测试证明契约检查和交接逻辑可执行，不证明模型的意图理解已经提升。`demo.py` 使用明确标记的合成场景，不伪装为真实产品、人工批准或生产部署。

安装器兼容检查不登录模型；真实 Codex/Claude/OpenCode 接力开发必须使用已授权账号单独验证。新机器仍需取得相同仓库及已提交/推送的状态。关闭聊天不会自动继续工作。

仓库内的 Rules、CODEOWNERS 和 CI 文件不等于 GitHub 分支保护已经启用。平台治理配置及独立审查能力必须实际可用后才能形成硬门禁。见 [运维与权限](docs/OPERATIONS.md) 和 [验证记录](docs/VALIDATION.md)。

上游版本和能力来源见 [来源与集成](docs/UPSTREAMS.md)。
