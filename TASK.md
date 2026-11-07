# Task 51.1 — 探索完整旅程与 V2 首页切换

```text
Task ID: 51.1
Task Type: SLICE
Parent Slice: 51
Status: FIX REQUIRED
Task Base: 3c8053b06c218e76084ec1c06cf57f03259da84c
Difficulty: High
Test Level: T3
Planner / Reviewer: Original plan — user-authorized B substitution; correction guidance/review — B
Implementation Authorization: ORIGINAL TASK SCOPE RETAINED; B CORRECTION GUIDANCE PENDING
```

## A final-review return — 2026-11-07

本页恢复原 Task51.1 的修正边界，不创建新 Task，不重设 Base／Goal／Scope／High／T3，
也不由 A 代替 B 规划。原完整计划、验收与测试分工见 `9efe8ccd:TASK.md`；原 B PASS、
已修正问题、原始失败／Base 对照／证据限制见 `01f4e05d:TASK.md`。
原目标仍为 Slice51 RO-2／3／4 和 RO-1 的 V2 Web 首页替换：浏览 → 筛选／搜索 →
详情 → 返回，加载、真实空态及失败分别可见且可恢复。

A 已独立审查完整 Slice
`214b69b1e64b24fc22068c2e1760cd1b0c6ac787..d91a9dd2fd5833a5977a319e90d0283b05625e9a`，
结论 **FIX REQUIRED**。唯一阻塞 **A51-01（P1）**：现有筛选／作品名搜索收到合法零结果
（`total_pages=0`）时返回 `502 / provider_malformed`，显示读取失败；原夹具将空页强制
为 1 掩盖了该分支。根因、真实入口复现、官方契约、精确修正结果与 A 独立证据见
[SLICE.md 的 A Final Review](SLICE.md#final-validation-closure-packet-and-a-final-review)。
这是未关闭 Slice 的必需空态修正，留在本 Task，不转为独立小 bug。

下一步由 **B** 在已提交 Contract 内补充本次修正指导并重评直接受影响测试，Developer
随后修正、提交候选，B 独立验收并重交 Slice Closure Packet。A 本轮没有规划实施步骤、
修改产品或批准修正候选；最终 Slice 接受仍待新范围及证据审查。

## Preserved checkpoints

- Task51.1 原已审范围：`3c8053b06c218e76084ec1c06cf57f03259da84c..9efe8ccd480b257e12eee29b9b90075ee8f809f6`；
  产品实现 `de86eab84e8627c0f656e51cea66e17e8ef1baf2`。原 B PASS 是当时结论，不抹除；
  本页当前 FIX REQUIRED 反映 A 最终审查发现的必需修正。
- Task51.2 原 B PASS：`01f4e05d5cc03822d2e9ced3dfa91a2838990f62..d91a9dd2fd5833a5977a319e90d0283b05625e9a`；
  完整报告及原 Closure Packet 在 `ab3edf8d3973012b2fb4f7152a18b90a0bf6e3f8:TASK.md`。
  Dashboard 全退出等已验证事实保持；原包的 COMPLETE／READY 是 B 当时结论，已由 A51-01
  退回，不能作为 Slice 已接受或已关闭的证据。
- Slice50、PATCH-20261107-1 及更早接受身份与延期不变；原 Task 文档及 Progress 账本保留指针。

本次仅记录 A 审查和交接。预存 dirty／未跟踪文件保留；未推送、发布或部署。
