# 从旧 Loop 迁移

基线：`01dab3068c2f5810e3220541c8afabaead8007e3`。旧包定义“GSD 唯一调度；Loop 仅校验与交接”，与此次用户批准的 Full Runtime 架构冲突，故重建活动源码而不继续保留双调度权威。

保留 Git 历史；没有 force-push，没有删除其他分支。旧 Skills、`.planning` 状态、安装器脚本及历史验收可从旧提交读取。它们不被自动转换成新 Runtime 的批准或进度。

PR #4 的 `feat/cross-project-installer` 是未合并的旧 0.2 分发实现，本次未合入、未改写。不能直接把它的原生安装成功记录用于本版。后续移植应移除 GSD 权威假设，改为分发此 Runtime + Skills，并重新测试 install/update/uninstall 与项目保护。

## 操作步骤

1. 保存旧仓库和未提交工作；读取旧 Goal/Spec/决策及实际证据，不沿用聊天进度断言。
2. 在新独立状态目录初始化 Runtime，注册批准的适配器和验收命令；原生提供商登录留在自己的受控环境。
3. 从实际 Git 提交及显式输入清单创建新 Intent。旧产物可作为待验证资料，但不能冒充本轮回执。
4. 完成目标/设计 Human 评审后进入 Build。与已有项目集成时，不改变其框架、布局和权限边界，除非单独获批。

`python -m loop_runtime ... export` 导出审阅包，不是备份。跨机器恢复须一致备份 SQLite、固定策略和全部证据，同时安全迁移或轮换凭据。不得仅复制 checkpoint/STATE.md 后宣布恢复成功。

本次合并权限仍独立于实现授权：创建实现分支和 PR 不表示 main 已获准合并。
