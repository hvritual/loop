# 固定来源与集成核查

核查日期：2026-10-18。选择稳定发布而非默认开发分支。以下链接均为官方项目来源；能力以实际源码及安装产物为准。

| 项目 | 版本 / 固定提交 | 用途 |
|---|---|---|
| GSD Core | 1.17.0 / `87bc15cd70ad8a2f086f105992e78c2eafcba5a1` | 唯一原生执行/进度体系 |
| BMAD Method | 6.12.4 / `bab9082c3e884e0d72c759bcd1a6d90bcc01be84` | 专业分析和设计 Skills |

GSD 的原项目已声明迁移；此包采用 open-gsd/gsd-core，不引用旧项目作为活动上游。

- [GSD 安装及客户端转换](https://github.com/open-gsd/gsd-core/blob/87bc15cd70ad8a2f086f105992e78c2eafcba5a1/docs/how-to/install-on-your-runtime.md)
- [GSD 原生状态模板](https://github.com/open-gsd/gsd-core/blob/87bc15cd70ad8a2f086f105992e78c2eafcba5a1/gsd-core/templates/state.md)
- [BMAD 6.12.4 Release](https://github.com/bmad-code-org/BMAD-METHOD/releases/tag/v6.12.4)
- [BMAD 官方安装命令参数](https://github.com/bmad-code-org/BMAD-METHOD/blob/bab9082c3e884e0d72c759bcd1a6d90bcc01be84/tools/installer/commands/install.js)
- [BMAD 客户端路径定义](https://github.com/bmad-code-org/BMAD-METHOD/blob/bab9082c3e884e0d72c759bcd1a6d90bcc01be84/tools/installer/ide/platform-codes.yaml)
- [Forge Idea 原始 Skill](https://github.com/bmad-code-org/BMAD-METHOD/blob/bab9082c3e884e0d72c759bcd1a6d90bcc01be84/src/core-skills/bmad-forge-idea/SKILL.md)
- [Agent Skills 开放规范](https://agentskills.io/specification)

**已纠正的假设：** 不能把 Forge Idea/Deep Recon 简单说成“只有 v7 才有”。固定的 v6.12.4 源码树中实际包含这些目录。本集成同时检查 installer 输出中所需的 SKILL.md 与共享脚本；源码存在不等于安装成功。

各上游保留其 MIT 许可证。本仓库没有复制上游全部实现，只记录版本与调用契约；下载安装的原文件保留各自许可证。Loop 不是 GSD 或 BMAD 的官方产品。
