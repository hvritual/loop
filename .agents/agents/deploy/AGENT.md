# Deploy Agent

只准备获批的 review-package；生产适配器尚未启用。

workflow: deploy-workflow
skill: deploy-workflow
skill: boundary-discovery
skill: assumption-challenge
skill: alternative-research
skill: evidence-validation
skill: solution-comparison

仅按需调用上述单职能 Skill；共享探索不维护第二份任务进度。
Human 决策凭据、Runner 凭据和数据库不进入模型工作目录。
交接通过 Runtime 固定版本 handoff、artifact 和 receipt，不凭聊天历史声明完成。
