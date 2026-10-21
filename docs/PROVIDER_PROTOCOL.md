# Provider-neutral Worker 协议 v1

运行器只调用批准且内容摘要固定的 Python 适配器：

```text
python -I <approved-script> <context.json> <workspace> <output-directory>
```

Docker 运行同一协议，镜像以内容 ID 固定，网络默认关闭。受信任宿主适配器须显式 `--allow-trusted`。不加载任意环境变量或 shell 字符串；没有自动模型账号登录、自动付费、自动安装。

## 输入

context 包含 protocol、intent、stage、kind、binding、goal、当前阶段 criteria、已有 handoffs、当前 discovery、source_manifest、previous 与 repair_feedback。实际白名单源码复制到 workspace；之前阶段交接位于 context 所在目录的 upstream/<stage>/；独立验证输入在 previous/。

kind：pre/post 为五维探索检查，execute 为当前阶段实施，verify 为独立验收，experiment 为发现的有界验证，compare 为验证后的方案比较。Context Packet 上限 64 KiB（不内嵌源码），源码单文件 1 MiB/总计 4 MiB；超限必须收敛输入，不能静默截断。

## 输出

写 `<output>/result.json` 与 `<output>/artifacts/*`。stdout/stderr 由 Runner 自动留存，不可代替结构化结果。

所有结果包含 `protocol: 1` 和可选 `findings`。详细结构见 contracts/worker-result.schema.json 和运行时验证器：

- pre/post：reviewed 精确覆盖 requirements/alternatives/boundaries/counterexamples/outcomes；notes 描述真实观察与未知项。
- execute：handoff。Discover 要求 requirements/assumptions/至少两个 alternatives；Design 要求 architecture/tasks；Build 要求 summary/changed_files/test_plan；Deploy 要求 target=review-package/release_notes/rollback/observation_plan。
- verify：checks 必须逐一对应当前阶段冻结的 criterion ID，包含 passed 布尔值和实际 artifact 路径。少一项、重复项或 false 均失败。验证器代码摘要必须区别于生产者；独立不等于另一段模型自述。
- experiment：conclusion 加可留存实验产物。不能把实验成功直接升级为新目标。
- compare：recommendation.action 为 keep/propose/defer。propose 还需 reason/counter_evidence/unknowns/replacement；Runtime 用既有实验和验证证据形成 Human 提案。Worker 不允许提出宿主 source 读取。

所有 finding 必须关联 criterion，并含 hypothesis/falsifier/scope/severity。不得包含“我有99%置信度所以批准”等绕行字段。

## 实际模型接入边界

此仓库内置的是可复现 CSV Producer 和独立 Verifier，**不是伪装的真实 LLM**。接入 Coding Agent 时由受信任适配器或外部工具宿主组织模型调用，将结果写回上述协议；身份/费用/网络权限必须明确配置并另验。禁止直接把同一模型的两次回答叫作独立工程验收。

外部资料检索由已授权工具宿主或适配器提供；Docker 离线沙箱不自带网页搜索。保留来源、时间、固定版本、反证及未核实事项。模型账号和生产服务不在默认沙箱内，未知能力应报 missing capability 而非假装执行。
