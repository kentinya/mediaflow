# Task 59.6 — 保存并重新分析状态对齐

```text
Task ID: 59.6
Task Type: SLICE
Parent Slice: 59
Status: READY FOR B REVIEW
Task Base: 71787a05f18a089753966fbc9b1469c7fb3b4877
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER-REQUESTED A59-08 CORRECTION
```

## 目标与实施范围

实现 [A59-08](SLICE.md#a-独立复验--80ad8d63--fix-required)。用户此前授权代 B。本轮在
`main`、干净工作区、治理通过后复现。只调整已有保存、等待、未受理及未知状态的呈现。

1. 两处共用批准稿的状态卡和可证明的已保存决定。等待时移除重复的提交提示与确认入口。
   Files 保留原文件身份及返回和翻页。任务中心保留原文件证据位置。
2. 保存失败保留输入。队列明确未受理时原按钮只补做分析。不确定时保留原请求锁，提供重读。
3. 验证 Files 真实结果回到概览，原任务行内恢复按原有读回进入新计划摘要。
   复验兄弟项切换、重开及后台轮询。沿用现有 API、工作流、执行权限和幂等规则。

## 验收与测试

Developer 在 `web/` 运行 `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx
src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/RunDetailTabs.test.tsx`、
类型检查、变动文件的静态检查和生产构建。以本机独立测试库从两入口真实保存，暂停再恢复 Worker，
对照批准稿的桌面和 390 px 等待画面，核对完成回落、队列拒绝及未知读回。

B 独立检查 Task Base 到候选差异、浏览器关键旅程与相应 T3 安全门禁，提交 Slice 终验包。
原交接保存在 `71787a05:TASK.md`。

## Developer 交接

两入口显示统一的重新分析区，复用原保存、分析与回落。保存前的入口与底栏已恢复原样。
受影响组件回归 143 项通过。原生浏览器验证混合四类、十项逐个处理后的单次确认、
任务中心识别恢复共 3 项通过。生产构建、类型检查、变动文件 ESLint 和 Prettier 通过。
本机测试站验证桌面、390 px、Files 概览回落、任务中心原行新计划、保存失败、
队列拒绝后仅补分析、回包未知的有／无受理。截图及日志见
`.git/validation-evidence/71787a05/slice59-local-site/reanalysis-*.log` 和同目录 `after-*.png`。
B 独立验收待完成。
