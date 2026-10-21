# 架构：模式 B，Full Runtime

## 控制面与执行面

Human / Coding Agent -> CLI 命令 -> 身份与策略检查 -> SQLite 单事务状态机 -> 待执行 Job。
Runner -> 固定版本 Context Packet -> 已注册适配器 -> 隔离工作目录 -> 原始回执 -> 验证器 -> 阶段门禁。

唯一控制面是 Runtime。Design Agent 同时负责 Discover 与 Design；Build Agent 实施；Deploy Agent准备发布包和观测方案。Explorer 负责跨阶段调查/实验/比较，Verifier 执行独立注册的验收程序。二者是按需能力，不维护另一份计划。

## 阶段推进

每阶段严格执行 `pre -> execute -> verify -> post`。发现/设计阶段分别等待目标和设计审批；Deploy 执行前等待发布准备授权。缺失、失败、过期、被篡改或结果未知的证据均不能通过。

pre/post 检查需求、替代方案、系统边界、反例、结果五个维度。覆盖字段不是“未知边界已穷尽”的证明；具体内容质量取决于适配器，必须用真实任务另行评价。

本版本采用阶段串行、阶段内部一个执行 Job 的契约。适配器可在该 Job 内完成获批的计划；Runtime 不冒充通用多节点 DAG 引擎。最多两个同意图在途 Job，多个意图由 SQLite 事务隔离；不是分布式调度系统。

## 探索闭环

`observed -> experiment -> independent verify -> compare -> keep / propose / defer`。

发现必须关联已登记验收标准，含假设与可推翻该假设的条件。重复问题合并，但严重程度升级不能被去重吞掉。候选过多、深度超限或相邻机会进入独立待办，不自动新增实施范围。

实验失败有次数和无新增证据上限。验证后的替代方案由 compare 返回 keep/propose/defer；propose 自动形成 Scenario / Capacity / Risk / Cost 决策包。Human 批准后才改变基线。严重风险不允许凭一句话豁免；必须有独立验证器明确关联的修复证据。

## 版本和重做

绑定包括 epoch、Goal/Spec/Plan 版本、source_commit、source_hash、policy_hash；执行回执还绑定 Job、租约、适配器摘要与输入摘要。

Human 审批携带提案摘要，旧版本不能套用。批准基线变更时保留历史、废弃排队任务、清空阶段交接与审批、返回 Discover 重验。当前采用保守的全链重验，不做不可靠的增量影响猜测。未解决及旧基线已修复的严重风险均重新评估，不能随新版本消失。

## 故障语义

所有变更在 `BEGIN IMMEDIATE` 内完成，快照、事件与幂等结果原子提交。相同幂等键和相同请求返回原结果；不同请求冲突。revision 冲突要求回读，不覆盖另一执行者。

Job 在开始前预留资源。租约过期、进程清理无法确认时状态为 unknown；人工核对工作进程已停止且无外部副作用后，只能取消旧执行并创建新尝试，不能直接转成成功。旧 fencing token 不能提交结果。预留不自动退还。

## 结果而非单纯交付

技术交付完成是 delivered；存在业务指标时保持 outcome_pending。人提交的观测明确标为 human_attested，不伪称 E4 生产遥测。达到指标才 outcome_confirmed；存在差距则保留 outcome_gap，并生成重做提案，包含“可能是测量误差或外部因素”的替代解释。是否改目标仍由 Human 决定。

## 层级边界

MVP 已被本实现覆盖；Full Runtime 增加了跨阶段任务、事务恢复、探索回流、运行器、凭据隔离和验收。Production 还需要服务端身份、远程凭据代理、持久化卷备份、平台策略、真实模型/业务评价及受控生产发布适配器。这些不因本地测试通过而自动成立。
