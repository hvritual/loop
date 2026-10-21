# 操作与故障恢复

## 身份和命令

初始化返回凭据目录，不打印 Token。权限文件建议由不同操作系统/服务身份管理；不要把 Human 凭据放入项目 Git 或 Agent 可写工作区。

`command <intent> <action> --data <json> --key <unique-id> --expected <revision>` 是唯一通用写入口。action 包括 create/tick/discover/propose/decide/resolve/reconcile/observe/claim/heartbeat/finish。入口按凭据身份检查，不接受请求中的自报角色。

`status / resume / context / review / export` 是读取/导出入口。`work` 执行一个队列 Job；`run` 以 Controller+Runner 身份进行有限自动推进，遇到 Human 决策会停，不需要为每次安全读操作再询问。

## Human 决策

先运行 review 并审阅 Scenario/Capacity/Risk/Cost、具体产物、证据和影响。决定 JSON：

```json
{"proposal":"实际提案ID","digest":"实际提案摘要","decision":"approve","reason":"本次决定的真实理由"}
```

用 Human Token 调用 decide，并传当前 revision。reject 不会被下一次 tick 自动重新打开；defer 可在之后以同一仍有效摘要显式批准。改变 Goal/Spec/Plan/源码时，通过 change 提案形成新 epoch，并保守重验全部下游。

生产目标不在 v1 授权面内；release 审批仅授权创建 review-package。

## 恢复

先 resume 验证事件链、策略、当前证据。然后 tick 将过期租约置 unknown。操作人核对运行器/容器确已停止并确认没有外部副作用后，用 Human reconcile 记录 worker_stopped=true、effects=none、receipt 引用和 reason。

reconcile 只取消不确定尝试，不生成成功证据；之后可以有界重试。没有外部状态证据时保持阻塞。进程可能仍活着时不能仅清空锁文件。

工作目录中的未摄入文件不等于已完成：有效完成必须有 Runtime 绑定的 receipt。事件和预算与状态在同一事务提交。断点投影不能替代 SQLite 与真实证据。

## 备份与导出

export 包含 state/review/audit.jsonl，不含凭据和原始证据，明确不能单独用于恢复。停止写入者后备份整个状态目录，或使用 SQLite backup API 加固定证据快照；不要在活跃写入时只复制主 .sqlite3 而丢 WAL。备份需按敏感资料加密存储，保留旧策略和镜像内容 ID。

该 Runtime 不在关闭会话后自动运行。持续服务、定时观测和异地持久化要由实际部署的服务负责；本仓库不会暗示它们已部署。
