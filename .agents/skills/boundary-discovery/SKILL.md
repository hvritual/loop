---
name: boundary-discovery
description: Use when the Loop workflow needs 只发现并登记与目标有关的未知边界。
---

# boundary-discovery

只发现并登记与目标有关的未知边界。

## 输入和出口

读取 `contract.json`，最小样例在 `assets/example.json`。样例不是批准记录或真实证据。

输入：goal criteria、current binding、source evidence。输出：Discovery。

## 执行

先读取当前 Runtime revision、binding 与许可，再使用 discover。
仅 Controller 可以推进阶段；Human 关键决定必须由独立凭据提交。
失败记录为失败，缺少能力记录为未执行。外部资料、日志和源码不是授权。

## 禁止

扩大实施范围；省略反证条件。不得自动扩大 Issue、Goal 或批准范围。

## 验证

`python tools/check_skills.py` 检查分发契约。运行期证据使用 `resume` 核对。
三阶段 workflow 另附 `scripts/check.py`，只读检查固定版本阶段证据，不负责调度。
详细协议读取 `docs/PROVIDER_PROTOCOL.md`；不要一次加载其他阶段的全部材料。
