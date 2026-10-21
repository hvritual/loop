# Loop Full Runtime

**一句意图 → 有界探索 → Human 决策 → Design / Build / Deploy → 证据验收 → 结果反馈。**

这是模式 B 的可执行控制面，不再是 GSD 调度器外围的文档校验包。实现使用 Python 3.11+ 标准库和 SQLite；没有模型 API Key 的强制依赖。模型或 Coding Agent 通过固定 Worker 协议接入，不能自行改变授权。

## 已实现的运行边界

| 能力 | 实际实现 |
|---|---|
| 唯一调度源 | SQLite 事务状态、幂等命令、事件链、乐观版本检查 |
| 四阶段 | Discover（Design Agent 负责）、Design、Build、Deploy；每阶段 pre/execute/verify/post |
| 主动探索 | 问题去重、目标关联、反证条件、父子深度、候选上限、实验、独立验证、方案比较 |
| Human 权限 | 独立凭据；目标/设计/发布准备/预算/基线变更审批绑定精确提案摘要 |
| 预算 | 全局、探索、阶段探索的多维预留；未知实际 Token/费用保留 null，不伪装为零 |
| 恢复 | 租约与 fencing、超时变 unknown、人工确认停止后才能重试；不把不确定执行转成成功 |
| 交接与证据 | 固定 Git 提交输入、内容哈希、原始输出、独立检查、过期证据拒绝、下游重新验证 |
| 运行器 | 默认失败关闭的 Docker 适配器；显式启用的 trusted 本地适配器；不自动降级 |
| 结果闭环 | 交付与经营结果分开；指标差距生成有反例解释的 Human 重做提案 |

**当前发布目标只有 `review-package`。没有实现生产发布凭据、远程生产写入或分布式高可用。**

## 立即验证

```sh
python -m unittest discover -s tests -v
python tools/check_skills.py
python examples/demo.py
```

默认演示使用合成咖啡机客户出杯 CSV，执行到目标评审后停止，**不会自动代替 Human 批准**。

完整集成测试可显式启用测试用审批：

```sh
python examples/demo.py --test-auto-approve
```

该命令生成真实子进程回执，但 Human 身份明确标记为 `SIMULATED`，业务数据和 Agent 均为 fixture，不能证明真实模型或生产效果。

## Docker 沙箱验证

先由操作人准备镜像，Runtime 本身不拉取镜像：

```sh
docker pull python:3.11-slim
IMAGE_ID=$(docker image inspect python:3.11-slim --format '{{.Id}}')
python tests/docker_integration.py --image "$IMAGE_ID"
python examples/demo.py --docker-image "$IMAGE_ID" --test-auto-approve
```

镜像使用内容 ID 固定；执行时禁止网络、只读根文件系统、移除 capabilities、非 root 身份，并限制进程数、内存、CPU、运行时间和输出。Docker 不可用即拒绝运行。完整安全边界见 `docs/SECURITY.md`。

## 真实项目接入

首先注册**项目专用**的 Design/Build/Deploy/Explorer 适配器和独立 Verifier；内置 CSV Worker 不是通用编程模型。
`docs/PROVIDER_PROTOCOL.md` 给出了输入输出协议、目录约定、适配器摘要和失败行为。已有 ChatGPT/Codex 等 Coding Agent 可以读取 Skills、准备任务与结果；真实账号接力仍需单独验收。

```sh
python -m loop_runtime --root /secure/loop-state init --policy approved-policy.json
python -m loop_runtime --root /secure/loop-state \
  --token-file /secure/loop-state/.credentials/controller.token \
  command INTENT-001 create --data request.json --key create-001 --expected 0

# 自动推进到需要人决策、预算/风险阻塞或本次步数上限，不自动后台常驻。
python -m loop_runtime --root /secure/loop-state \
  --token-file /secure/loop-state/.credentials/controller.token \
  run INTENT-001 --runner-token-file /secure/loop-state/.credentials/runner.token \
  --adapter-root /approved/adapters --max-steps 64
```

Human 阅读 `review` 输出后，以自己的凭据提交决定；不要把 Human Token 交给执行 Agent。示例及恢复操作见 `docs/OPERATIONS.md`。

## 仓库导航

`loop_runtime/` 为控制器、存储、契约、执行器和 CLI；`.agents/` 为三个 Agent 与共享单职能 Skills；`contracts/` 为交换格式；`tests/` 为运行时和沙箱验收；`docs/` 为架构、迁移、权限和验证边界。

旧主干 `01dab3068c2f5810e3220541c8afabaead8007e3` 可从 Git 历史恢复。未合并安装器 PR #4 不在本次重建的实现基线中；迁移说明见 `docs/MIGRATION.md`。不要把旧安装器的通过记录算作本 Runtime 的验收。
