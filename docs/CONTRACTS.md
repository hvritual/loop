# 可执行契约

每个意图使用 `.planning/intents/<ID>/`。ID 为 1–64 位字母、数字、短横线或下划线，不接受路径穿越。所有文件引用均相对仓库根目录，不能跳出工作区。

| 文件 | 关键字段 | 校验 |
|---|---|---|
| intent.json | 原话、actor/scenario/problem/outcome、范围、约束、成功指标、证据、备选、未决问题、批准 | 不允许阻断未知；未知基线必须有测量计划；批准绑定内容 |
| spec.json | intent_sha256、稳定 requirements/acceptance ID、Given/When/Then、检查 ID | 每个 outcome 有覆盖；标准/高风险覆盖失败和恢复 |
| design.json | spec_sha256、架构/旅程/恢复/测试文件引用及哈希、风险处置 | UI 需真实可阅预览及快照批准 |
| plan-map.json | spec/design 哈希、原生 GSD PLAN 路径/哈希、验收覆盖、依赖、范围、检查 | 无遗漏、未知依赖、自依赖和循环；禁止存 status |
| evidence-index.json | spec 哈希、acceptance → result.json | 每个验收项有对应检查，不能引用其他检查冒充 |
| review.json | reviewer/executor、report 与哈希、spec/source 摘要、findings | 不能自称独立审查；阻断问题已解决 |
| release.json | 约定目标、外部引用、结果、操作回执、恢复方案 | 不降级交付目标；不确定操作先对账；部署还需观察与批准 |
| closure.json | remaining_blockers、learning_disposition、learning_candidates | 无隐藏阻塞；沉淀可为有理由的不变更 |
| checkpoint.json | 目标、下一安全动作、来源快照、Git 信息 | 仅投影；新会话检查失效，不作为完成事实 |

模板放在所属 Skill 的 assets 中；空模板应无法通过门禁，不生成默认批准。

## 摘要

文件摘要是原始 UTF-8 字节 SHA-256。批准主题摘要是去除 `approval` 对象后，按 key 排序、紧凑分隔、保留 Unicode 的 JSON SHA-256。脚本 `scripts/common.py` 的 `digest` 和 `stable` 是实现。

## 执行证据

`evidence <CHECK-ID>` 只从 `.loop/checks.json` 读取 argv，以无 shell 子进程执行，记录真实退出码、超时、前后代码摘要、检查定义摘要和原始日志。日志可能含业务数据，提交前必须检查并移除敏感内容；改动日志后必须重新生成证据，不能手工修补哈希伪装执行。

源码摘要包含 Git 已跟踪及未忽略的新文件，包括规则、技能与测试；不包含 `.planning/`（避免证据自引用）及明确的上游生成/缓存目录。规范、设计、计划内容另外逐级绑定，不能把产品源代码放进排除目录规避验证。

## 门禁的限度

字段完整不能证明用户需求正确。通过测试不能证明测试覆盖恰当。不同 reviewer 字段不能证明独立身份。回执字符串不能替代访问外部系统。每个阶段 Skill 明确要求相应语义检查；平台机制负责授权。
