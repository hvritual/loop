# 安装、恢复与平台权限

## 安装

在此仓库运行 `python scripts/bootstrap.py --runtime codex`，或者选择 `claude` / `opencode`。先用 `--print-only` 审阅即将执行的固定版本命令。

需要 Node.js 22+、npm、Python 3.11+、uv、Git 和网络。安装器不会登录模型或创建付费资源。它调用官方安装器完成原生 Agent/Skill 转换；禁止从 GSD 源码目录直接复制 Agent 定义。

失败查看 `.loop-cache/install-<runtime>-*.log`。安装器发现规则或已有 `.planning` 文件发生变化会失败并要求对账，而不是静默覆盖上下文。该安装不是事务；中断后检查已生成文件，不能把返回码当成全部回滚。

如果已有禁用 BMAD 入口备份，重新安装时会要求审阅；不要覆盖原有备份以隐藏变化。无需安装 TEA、BMAD Builder 等外部模块来完成基础流程。

固定 installer 版本不锁定其所有传递依赖。供应链要求更严格时，应审核 npm lock/cache、安装日志及生成文件后晋级；不要将 `@latest` 当作可重复构建。

## 恢复

启动新会话时先执行 resume 并读取 GSD STATE/ROADMAP/current PLAN/SUMMARY。单写者、单工作流状态是当前约束，不声称提供多会话事务与分布式互斥。

checkpoint 不备份未提交的代码。跨机器需先提交/推送允许公开的意图、决策、设计和进度，或共享持久化工作区。密钥、个人数据和敏感日志不可提交。

PR、部署和迁移响应丢失时，记录 unknown 操作及幂等键；下次访问外部系统对账，不盲目重复执行。

## CI 与平台硬门禁

`quality.yml` 运行契约/失败路径测试，并在三种客户端安装布局上验证上游集成。它不调用收费模型，不测试真实模型能力，不自动合并或部署。

`.github/rulesets/main.json` 是**待应用**的设置候选，不代表仓库已经启用保护。检查名称必须与实际 CI 结果完全一致；不要在检查未运行前盲目设置 required checks。

应用规则集需要具有仓库 Administration 权限的身份；当前 GitHub 连接的可用写操作不包含规则集管理。应先确认有可用的独立审阅人，避免只有 PR 作者一人却强制其批准自己的 PR。CODEOWNERS 本身不启用强制审阅。

治理文件、校验器或 CI 自身的变更必须独立审核。普通 feature Agent 不拥有管理权限，也不能自行创建豁免。审核后的平台设置可使用 GitHub 原生 Settings / Rules 或官方 gh/API 应用；完成后应 GET 回读，不能只凭执行成功文字宣布生效。

## 真实模型验收

使用 `evals/intent-cases.json` 的相同输入，对比不用 Loop 与使用 Loop 的输出，保留模型/客户端版本和原始结果。随后完成一项小功能，中断会话并换一个已授权模型继续，验证不重复任务、不丢已确认决策、失败不虚报成功。

未取得账号、运行环境或外部依赖时标记 not_run，不创建模拟记录来代替真实验收。
