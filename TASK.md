# Task 57.1 — 单管理员 Web 登录与定时计划停用

```text
Task ID: 57.1
Task Type: SLICE
Parent Slice: 57
Status: FIX REQUIRED
Task Base: 4566a74055c698aec704215dd431eb8521bcfedb
Difficulty: High
Test Level: T4
Implementation Authorization: ORIGINAL TASK SCOPE; B CORRECTION PLAN PENDING
```

## A 终审退回

**A57-01（P1，RO-1 / AC-01、AC-02）**。从现有首页创建管理员或从账号菜单改密时，
真实提交已经生效，但浏览器丢失回包后提示账号或会话未变更，并要求重提。
复现、原始证据和验收条件见 [A 终审](SLICE.md#a-final-review--fix-required)。

B 在原 Task 的目标、范围及 T4 下规划并提交修正指导。修正后由 B 独立验收新候选，更新
Slice 57 Closure Packet，提交 A 复审。Task 57.1 原计划、范围和测试安排见
`c12cae6fe0226e7efe6850ac68e6581785fb87e3:TASK.md`。原 Task 57.1 PASS 见
`5c04cf53:TASK.md`，Task 57.2 PASS 和原最终验收包见
`2961baeb5eae2028a3e6db23fc6076e3c62caf2a:TASK.md`。
