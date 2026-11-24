# Task 59.2 — 任务中心运行详情正文

Next Action: DEVELOPER ALIGNS THE RUN DETAIL BODY WITH SLICE 59 AC-06

```text
Task ID: 59.2
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 868ff9daab6972473cfb7344ca02cbdbc30077cf
Reviewed Implementation Head: bf02484162ae9982d697825698ba541646665e02
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.2 / SLICE 59 A59-03 CORRECTION SCOPE
```

## B 复核与 Slice 59 交接

**Task 59.1 — PASS。** B 从 `main` 的 `62345436` 开始复核，工作区与暂存区干净。
完整 Task `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..bf02484162ae9982d697825698ba541646665e02`，
完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..bf02484162ae9982d697825698ba541646665e02`。
`62345436` 只更新 Developer 交接。上轮 Files 阻塞见 `9c0b9921:TASK.md`。

- **RO-1（AC-01/05/06）。** 从原入口看到准备阶段、来源、范围和进度，方案读取后在同一弹窗进入
  概览。概览只显示一条三栏计数，窄窗首屏露出首个就绪文件。100 项显示 `90 / 0` 和作品搜索
  修正入口。第 101 项整批停止，重新进入较小范围后有正常复核路径。
- **RO-2（AC-02）。** 同一真实批次完成识别、候选确认、作品搜索修正、分类和冲突处理。冲突正常
  和丢回包跳过读回原条目后回概览，仍显示相应结果；技术失败保留确切原因和可执行的下一步。
  十个文件逐项决定后只提交一次。首次方案读取失败和分析丢回包继续沿实际原入口核对。
- **RO-3（AC-03/05/06）。** 两个就绪文件从 `2 / 2` 到 `1 / 2`。整批的状态卡和三栏计数紧接
  「来源与目标」，诊断在文件之后；桌面、390 × 844 与 390 × 520 上返回与确认同排。首次只执行
  选中的一项，另一项从同一任务继续，第二次确认丢回包由原受理记录查明。未受理原因及原阻塞
  仍可读，隔离 OpenList 旅程核对实际移动和重命名。
- **RO-4（AC-04/05/06）。** 原位「继续整理」、详情页签和筛选、四类同任务恢复已通过功能复验。
  `RunDetailTabs` 仍分别渲染流程、进度和操作，文件用含路径、条目标识和目标的宽表格，展开证据
  将结果和实际操作效果分散在多个区块。对照批准预览，任务详情正文的层级仍是 A59-03 的剩余交付。
  B 接续原 Task 59.2 的同一 Base，Slice 59 继续等待本轮正文修正及最终门禁。

构建、类型、改动文件 ESLint 和 Prettier、治理及完整差异检查通过。相关组件 **179 项**，
Files 和 Task Center 布局 **64 项**，任务中心原生 **8 项**，OpenList **1 项**通过。
同一产品构建的原生 Files 24 项均取得通过结果。首跑 14 项通过、3 项失败、7 项因全组时限
中断；随后冲突与混合决策组 4/4、剩余组 7/7 通过，其中一项冲突回归重复验证。

B 的 `bc38849a2d143a60674b723fb2b8f8b28d43356f` 只更新两个验收测试。重命名冲突用例核对
实际 202、浏览器响应丢失、原准备分析读回及 UI 等待状态。首跑已经读回的分析被旧测试当成
等待超时，导致共享 Worker 为后继两项领取到前一任务。另一用例从新位置展开诊断，照常核对
兄弟项新方案、原执行请求及单次执行。最初的失败、诊断定位中断及后续通过均保留原日志。

截图和日志位于本机
`.git/validation-evidence/bf02484162ae9982d697825698ba541646665e02/b-task59.1-review/`。
`current/`、`approved/` 和 `readability/` 包含三个视口的四屏对照与 100 项真实阻塞。标准
子集实页为移动且无附件，预览示例为带字幕的硬链接。100 项无法确认时，窄窗底栏保留原因和
下一步，确认按钮禁用，正文可滚动核对计数和条目。批准预览 SHA-256 与 Slice 合同一致。

## 目标、范围与开发指导

从 Files 的确认交接或任务中心列表打开原「运行详情」。先看到任务状态、进度、当前操作和文件结果。
从文件就地查明来源、目标、操作和实际效果；需要处理时，在该文件证据内做决定、分析、核对新计划，
再明确继续。查看操作记录或关闭上一层卡片后，回到原任务和原入口。

本轮落实 RO-4、AC-04/05/06 和 `V2-OPS-021`。范围限运行详情两个页签正文和本地样式。沿用原弹窗
标题和关闭控件、任务列表与八视图、问题文件定位面板、Files 和 Task Center 的原位整理卡。复用实际
任务和文件读模、现有 API、权限、执行意图和持久历史。原授权见 `504e6eba:TASK.md`，原功能候选
`85e689cf` 的 B 复核见 `aa20989a:TASK.md`。
[Slice 验收](SLICE.md#acceptance-criteria) · [任务中心现行旅程](docs/task-center-page-spec.md#current--任务正文与文件证据)

1. 在 `RunDetailPanel` 与 `RunDetailTabs` 把现有流程状态、阶段或等待原因、真实进度和适用动作
   收在首张卡，紧随独立的文件结果计数。沿用现有流程、进度、取消和受理核对逻辑。总量未知时照实
   显示。「继续整理」保留原关联和可用条件。流程已完成与文件成功、部分结果、失败、未知效果、结果
   未记录各自读回事实。
2. 把 `RunItemsSection` 的展开前宽表改成紧凑文件行。优先显示文件名、适用原因、处置和「查看证据」，
   完整路径和技术标识在原文件证据查阅。沿用实际状态筛选、服务端分页和唯一证据身份。证据紧接
   原文件；筛选隐藏、换页或列表读取失败时沿用同一文件的独立证据与原因，关闭回原触发处或已有回落
   位置。同文件的草稿按现有任务、条目和账号边界保留。
3. 在 `RunEvidenceSection` 让当前结果、来源、目标、实际操作和效果先可读，附件异常跟随对应文件。
   处理依据、历史尝试、日志和审计按原条目组织，通过就地展开查阅。允许恢复时复用
   `TaskItemRecoveryPanel` 的原决定、分析、新摘要及一次明确确认。原任务的准备续作继续使用准确的
   `run + dialog=organize` 关联，关闭顶层卡片回到原详情与焦点。
4. 调整 `RunRecordsSection` 正文为紧凑、可折行的记录。每条可读时间、类型、摘要和适用的原条目入口。
   保留实际 `runRecordsQueryOptions` 的类型筛选、分页、截断说明、读取失败后的重读和有界 JSON 导出。
   [任务详情入口](web/src/features/operations/OperationsLanding.tsx) ·
   [详情与记录](web/src/features/operations/RunDetailTabs.tsx) ·
   [原位恢复](web/src/features/operations/TaskItemRecoveryPanel.tsx)

## 验收

- [ ] 从现有任务列表分别打开运行中、已完成和含问题文件的任务，在 1280 × 900、390 × 844、
  390 × 520 与批准预览逐屏对照。核对首区状态和适用操作、其后结果计数、紧凑文件行以及正常键盘
  进入和关闭。「继续整理」打开并关闭原整理卡后保留父详情、页签和焦点。重连读回原任务。
- [ ] 从 Files 确认进入准确任务。打开该文件证据，先读当前结果和实际路径、操作及效果，再展开依据与
  诊断。核对成功、混合、仅附件失败、技术终结、流程失败、取消、跳过、效果未知及结果未记录；
  已验证恢复继续由实际流程与文件效果共同决定。证据跨筛选迁移时保持唯一、可读且保留草稿。
- [ ] 从四类问题入口，在原文件证据中做决定、分析并显式确认新计划，核对同一任务的真实结果。
  切换「操作记录」，从原记录定位文件。核对类型筛选、分页、长名称折行、读失败重读及真实导出。
  截图对照说明实际状态、操作资格和记录类型导致的具体差异。

## 测试

Developer 在 `web/` 运行 `npm run typecheck`、`npm run build`，对改动文件运行 ESLint 和
Prettier，仓库根运行 `git diff --check`。复用现有组件和入口用例。现有宽表断言随正文更新，保留
文件身份、结果真值、证据位置、读错重试及历史。提交候选、实际运行结果和同状态逐屏对照。

```sh
npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'the selected run detail reads progress|detail tab and filter context|initial manual preparation remains reachable in place|the eligible run exports'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

B 复核完整 Task 和 Slice Base..Head，先核对首屏、展开证据、同任务续作和操作记录的验收缺口，再按
T3 重跑相关布局与原生集成。用现有 Files 精确子集和原生四类恢复、`dated views and 21-file recovery`
及混合未知效果用例核对跨页、交接和实际效果。测试墙钟低于本轮耗时一半。全 Slice 结果满足后交 A 终审。
[测试分工](docs/development-workflow.md#6-test-levels)
