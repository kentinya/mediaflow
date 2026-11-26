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
Implementation Authorization: USER-REQUESTED A59-08 / A59-09 CORRECTION
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

## 本轮修正 A59-09

在原 Task 内修正用户报告的等待页、交接和文件行展开。任务 Base 保持不变。

1. 文件行展开按批准稿组织当前结果、来源、可用目标、操作与影响以及适用附件和未知效果。
   处理依据和技术记录折叠。点同一行收起。列表及证据正常状态移除重复刷新。
   读取失败、离开筛选页和四类决定保留可用下一步。
2. 保存后稳定显示同一条目。新方案读取期间留在重新分析交接，避免回到首次准备页或重复淡入。
   回落由原有真实读回和同条目守卫决定。
3. 确认受理后交接到现有任务详情，消除从透明开始的第二次入场。验证确定和未知响应路径。

开发使用受影响组件、原生 Playwright 和原测试站的桌面及 390 px 录帧验证三处问题。
B 独立复核准确任务、权限、读取失败与重开的安全边界。

## 本轮开发交接

文件证据使用批准稿的行内字段和两项折叠，普通条目收起由原行控制。四类恢复确认仍保留原请求的受理核对。
真实效果未知记录可以读出其未确认的操作步骤。新方案读回保留当前文件，确认受理后原任务详情首帧可见。

受影响组件分别通过 144 项和 99 项（其中条目详情集重跑）。真实 Python 浏览器 15 项通过，
模拟浏览器 7 项通过。类型、变动文件 ESLint 与 Prettier、生产构建和治理均通过。
本机 53 个场景均可创建、登录并打开。桌面和 390 px 录帧验证了两处切换，
并复验了附件失败、效果未知、结果缺失和新方案读取失败后重读。日志及截图见
`.git/validation-evidence/71787a05/slice59-local-site/followup-*.log` 和同目录 `verified-*.png`。
B 独立验收待完成。

## 上一候选交接

两入口显示统一的重新分析区，复用原保存、分析与回落。保存前的入口与底栏已恢复原样。
受影响组件回归 143 项通过。原生浏览器验证混合四类、十项逐个处理后的单次确认、
任务中心识别恢复共 3 项通过。生产构建、类型检查、变动文件 ESLint 和 Prettier 通过。
本机测试站验证桌面、390 px、Files 概览回落、任务中心原行新计划、保存失败、
队列拒绝后仅补分析、回包未知的有／无受理。截图及日志见
`.git/validation-evidence/71787a05/slice59-local-site/reanalysis-*.log` 和同目录 `after-*.png`。
B 独立验收待完成。
