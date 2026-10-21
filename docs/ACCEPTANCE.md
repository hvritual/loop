# 验收范围与证据

## 本地执行

环境为当前 ChatGPT Linux 执行容器，Python 3.13.5。首批 40 项和扩展后的 53 项 unittest 已实际执行通过。默认演示停止在 Human 目标评审；完整演示以明确标记的 SIMULATED TEST HUMAN 走完 16 个 Job、16 份原始回执。

最终源码回归命令：

```sh
python -m unittest discover -s tests -v
python tools/check_skills.py
python examples/demo.py
python examples/demo.py --test-auto-approve
```

实际日志保存在 `evidence/local/`。本地没有 Docker，因此不能用本地单元测试冒充实际容器隔离。GitHub `Loop Full Runtime` 工作流另在真实 Docker 下验证非 root、禁止外网、只读根、无宿主凭据、无 Docker socket，并执行完整沙箱流程。

## 核心验收映射

| 要求 | 主要测试 |
|---|---|
| 四阶段 + pre/post + 独立验证 | full_runtime_delivery_has_sixteen_real_receipts |
| Human-only、拒绝/延期/重审 | all_nonhuman_roles_cannot_approve、rejected_review、deferred_review |
| 目标、审批、证据版本绑定 | approved_change、stale_evidence、wrong_packet_digest |
| 幂等、并发和恢复 | idempotency、two_connections、expired_lease、reconciliation |
| 探索有界、风险不被预算吞掉 | discovery_dedup、depth_limit、candidate_limit、critical_risk |
| 预算预留与扩展 | each_budget_dimension、stage_exploration_budget、human_can_extend |
| PoC → 验证 → 比较 | experiment_and_independent_remediation、compare_routes_validated_discovery |
| 结果反馈与替代解释 | outcome_gap_creates_prepared_human_rework_decision |
| 证据完整性和隔离 | snapshot/audit/evidence tampering、adapter_hash_drift、output_symlink |
| 有界失败与真实运行 | invalid_worker_output、timeout、real Docker integration |

## 不声称已验证的内容

真实模型的需求理解/未知边界发现质量、真实 Codex/Claude/其他账号登录与接力、跨平台宿主进程树安全、生产服务部署、客户收益和 GitHub 分支保护。当前所有内置业务数据均为 fixture。

这是 Full Runtime 控制面和执行协议的实现验收，不是 Production 验收。E3 验证由独立注册程序执行，不等于已有外部人员独立代码审查。

初次测试准备阶段曾因数据库快照连接未及时关闭而中断；已修正并重新完整运行，没有将中断运行计为通过。
