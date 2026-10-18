# 跨项目安装与升级

Loop 0.2.0 是项目级工具包，不是 SaaS、编排后台或业务脚手架。它分发 Loop 规则、Skills、契约工具，并调用固定版本的 GSD/BMAD 官方安装器。npm 包设置了 `private: true` 防止误发布；当前使用 **GitHub 固定提交或 npm tarball**，不能把它描述成已发布到 npm registry。

## 一个入口

本次代码版本为 `093458821ec5ab2f04b1891fa8a5ac26779e3023`，在目标 Git 仓库根目录运行：

```sh
npx --yes --package="https://github.com/hvritual/loop/archive/093458821ec5ab2f04b1891fa8a5ac26779e3023.tar.gz" loop install --project . --runtime codex
```

该命令固定源提交，不跟随 main 或 latest 漂移。PR #4 记录实际 CI 与后续文档修订。也可从源码运行 `node /path/to/loop/bin/loop.cjs install --project /path/to/project --runtime codex`，或用 `npx --yes --package=/path/to/hvritual-loop-0.2.0.tgz loop install --project . --runtime codex`。不需要把 Loop 加入业务的 package.json。Claude Code 使用 `--runtime claude`；OpenCode 使用 `--runtime opencode`。

环境：Git、Node.js 22+、Python 3.11+；真实上游安装还需要 npm、uv 和网络。`LOOP_PYTHON` 可指定 Python 可执行文件（不是 shell 命令）。安装不负责账号登录或全局软件安装。空目录需要先明确执行 `git init`。不接受仓库子目录作为安装根目录；不会默默在 monorepo 子包里建立另一套状态。

## 安装不等于验收

```sh
# 预览不写文件，也不下载上游；实际原生输出仍需 staging 才能确定。
node /path/to/loop/bin/loop.cjs install --project . --runtime codex --dry-run

# 仅安装离线核心；报告明确是 not_installed，不能当作完整原生安装。
node /path/to/loop/bin/loop.cjs install --project . --runtime codex --skip-upstreams

# 之后原地补齐上游；不要直接对消费项目调用旧 bootstrap 安装模式。
node /path/to/loop/bin/loop.cjs install --project . --runtime codex

# 安装后的检查不再依赖源包目录。
node .loop/core/bin/loop.cjs doctor --project .
node .loop/core/bin/loop.cjs doctor --project . --require-native --require-project-checks
```

报告分别列出文件完整性、native 安装兼容性、项目检查配置、平台保护和真实模型执行状态。配置了测试命令也只是 `configured_not_executed`，不是业务验收通过；`platform_protection` 和 `live_model_execution` 不会因为安装而变成已验证。

## 三种文件归属

| 类别 | 示例 | 升级/卸载 |
|---|---|---|
| Loop 受管 | `.loop/core/`、统一 `.agents/skills/loop*/`、框架规则/上游锁 | 只有摘要仍匹配的受管文件可被替换或删除 |
| 项目配置 | `.loop/checks.json`、`.loop/project-rules.json`、AGENTS 受管区外文字 | 保留，不自动改写 |
| 项目状态 | `.planning/`、业务源码、已有 CI、其他 Skills | 从不从框架仓库复制，也不随卸载删除 |

原有 AGENTS/CLAUDE/gitignore 只插入标记区块，区块外字节保留，包括 CRLF。已存在的同内容文件是共享文件，不自动认领删除权。已有 GSD/BMAD 配置与新输出冲突时，安装停止并列出文件，不会提供一个隐蔽的强制覆盖开关。不能仅凭技能名字以 `bmad-` 开头就删除原项目的技能。

`.loop/core/ORIGIN.md` 记录通用规则来源；目标项目不继承 Loop 自身任务中的用户批准记录。项目规则只能补充适用约束，不能凭安装器自动解决价值/权限冲突。

## 接入真实项目检查

安装会从根目录、backend、frontend 的 go.mod 和 package.json 提供有限的检查建议，但不会执行、自动批准或把它们填入有效 `checks`。更复杂的项目从原 CI 选择实际命令。

可通过 `--checks /path/to/reviewed-checks.json` 在首次安装时初始化注册表：

```json
{
  "schema_version": 1,
  "checks": {
    "backend-unit": {"argv": ["go", "-C", "backend", "test", "./..."], "timeout_seconds": 120},
    "frontend-test": {"argv": ["npm", "--prefix", "frontend", "run", "test"], "timeout_seconds": 120}
  }
}
```

上面是示例，不代表你的项目有这些脚本。现有检查配置不会被 `--checks` 静默覆盖。不支持用一段 shell 字符串代替 argv，也不会把 Loop 自己的演示与单元测试作为业务验收。

## 升级、恢复、卸载

```sh
# 用新版本源包执行 update；项目状态/配置不变。
npx --yes --package="https://github.com/hvritual/loop/archive/NEW_REVIEWED_COMMIT_SHA.tar.gz" loop update --project .

# 中断后，在确认旧安装进程已结束时恢复。
node /path/to/loop/bin/loop.cjs recover --project .

# 卸载前可预览；未修改的受管文件才会删除。
node .loop/core/bin/loop.cjs uninstall --project . --dry-run
node .loop/core/bin/loop.cjs uninstall --project .
```

更新不降级。更换上游锁不能使用 `--skip-upstreams` 冒充已验证升级。可重复 install；相同版本且内容完整时为无改动操作。新增客户端使用 install 的 `--runtime`，复用同一份项目状态。

更新前后有文件摘要检查；写入前保留本地 journal，普通异常自动回退。进程被杀死会留下恢复标记，`recover` 根据 before/after 逐文件对账；发现后来编辑过的文件会拒绝覆盖。只保证本次清单内的项目文件，不承诺 npm 缓存或上游进程的系统级副作用可回滚。staging 是隔离目录，不是操作系统安全沙箱。

`.loop-cache/` 内可能有本地备份和上游安装日志，应保密、不提交。并发保护限单机文件工作区；不提供分布式互斥。不同主机的遗留锁需要人工核实，不会强制解锁。

移动或重新克隆到不同路径后，原生客户端的绝对路径引用可能过期。doctor 会检查原生安装目录绑定；在新工作区重新运行 install 生成新入口，而不是重置 `.planning/`。各客户端会话通常需要重新打开以发现新入口。原生文件兼容测试并不证明某个具体模型的技能调用或上下文恢复质量。

卸载默认保留 `.loop/checks.json`、`.loop/project-rules.json`、`.planning/` 和后来修改过的受管文件，报告这些保留项。空目录/本地缓存可能留下，不会递归删除用户目录。

## 实现与验证边界

文件安装和状态保存不等于无法绕过的安全门禁。源码可写的执行者仍可修改本地 manifest；真正的授权、独立审查和受保护分支由外部平台保障。此功能不关闭已有 Issue #2/#3，也不自动合并自己的 PR。

测试分三类：离线生命周期与故障注入；实际 `npm pack` 后在其他目录运行；真实官方上游安装与新路径再安装。模型登录、付费模型请求和生产部署不在这些测试内。

使用 GitHub archive URL 而不是 `github:owner/repo#sha`，避免本轮 npm GitFetcher 的 Arborist 错误。源码归档会进入 npm 缓存，但安装器只把白名单资源写入目标项目；不复制源码任务历史。正式 npm tarball 则在打包时就排除了项目历史与测试。
