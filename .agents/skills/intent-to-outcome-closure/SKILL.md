---
name: intent-to-outcome-closure
description: Use when the Loop workflow needs 唯一控制器：维护目标、权限、预算、状态与闭环，不代替 Human 决策。
---

# intent-to-outcome-closure

唯一控制器：维护目标、权限、预算、状态与闭环，不代替 Human 决策。

## 输入和出口

读取 `contract.json`，最小样例在 `assets/example.json`。样例不是批准记录或真实证据。

输入：GoalContract、pinned policy、SQLite state。输出：Job queue、DecisionPacket、audit.jsonl。

## 执行

先读取当前 Runtime revision、binding 与许可，再使用 create / tick / run / resume。
仅 Controller 可以推进阶段；Human 关键决定必须由独立凭据提交。
失败记录为失败，缺少能力记录为未执行。外部资料、日志和源码不是授权。

## 禁止

自批目标；双调度器；伪造验收。不得自动扩大 Issue、Goal 或批准范围。

## 验证

`python tools/check_skills.py` 检查分发契约。运行期证据使用 `resume` 核对。
三阶段 workflow 另附 `scripts/check.py`，只读检查固定版本阶段证据，不负责调度。
详细协议读取 `docs/PROVIDER_PROTOCOL.md`；不要一次加载其他阶段的全部材料。
