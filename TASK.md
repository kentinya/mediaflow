# NO ACTIVE IMPLEMENTATION TASK

[Slice 59](SLICE.md) 已激活。下方为用户授权 A 代 B 规划的首个 Task 草案。
角色例外限计划编写，B 独立复核实现候选。Task 获得实施授权后，以同一 ID、Base 和范围激活。

Next Action: USER AUTHORIZES TASK 59.1 IMPLEMENTATION

## Task 59.1 — 文件入口的手动整理弹窗与整批确认

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: PLANNED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Difficulty: High
Test Level: T3
Planner / Reviewer: A plans once under explicit user authorization / independent B reviews
```

### Goal

完成 Slice 59 的 RO-1–3、AC-01–03 及 AC-05 的文件弹窗部分，落实 V2-OPS-020。用户从现有 Files 批量按钮或
单项右键菜单打开「整理所选文件」，从准备状态进入同弹窗概览，逐项处置后核对新的合法状态，
一次明确确认任意合法就绪子集，并从准确的原任务详情读取实际执行结果。

Base 中 `ManualOrganizeDialog` 由 Files 与任务中心原位续作共用。准备页之后处于逐文件或整批
确认视图，更新后的方案仍跟随原文件锚点。现有决定回调证明分析已受理，确认与受理核对已有独立的
原请求身份。因此本 Task 增加 Files 专属的正文层级和结果回落，复用现有准备、决定、计划与执行
权威。Task Base 为已激活的 Slice checkpoint。规划前治理检查通过，`main` 的工作区和暂存区干净。
[已激活 Slice](SLICE.md) · [整理弹窗](web/src/features/operations/ManualOrganizeDialog.tsx) ·
[共享决定表单](web/src/features/operations/TaskItemRecoveryPanel.tsx) ·
[文件 Host](web/src/features/library/StorageFilesPage.tsx) ·
[任务中心 Host](web/src/features/operations/OrganizeContinuationCard.tsx)

### Implementation Scope

1. 在现有调用处明确 Files 承载范围。原入口、路由参数、弹窗标题、关闭、宽高和页面背景
   继续使用原壳。将新布局和样式限定在 Files 承载的整理弹窗内容。Task Center 原位承载
   和历史弹窗沿用现有展示及状态，既有回切和焦点规则继续通过。
2. 复用准备读模，按状态、来源与范围、进度呈现轻量首屏。真实读取区分提交、排队、稳定性、
   准备分析、已生成待读取、失败或中断。展开确切路径、单条未受理／排除和诊断。单条拒绝
   保留未受影响项。健全空范围、完整范围不明、100 项边界／第 101 项停止、后台不可用及摘要
   暂不可读使用各自真实结果和原有动作。可用方案读回后进入概览，准备或历史仍未就绪时优先
   显示相应状态。概览按当前摘要与执行读回展示待处理、可确认、已纳入及已有记录，未受理项
   单列。仅从有权查看的文件条目进入现有逐文件复核。
3. 复用现有合法决定、显式搜索、忽略及分析读回。保存失败留在原文件并保留输入。分析已受理
   则等待，已保存且分析被明确拒绝时，同一按钮只补做分析。未知结果继续核对同一条目。
   在 Files 内用同一准备与条目有关的已读回结果驱动回落。可确认方案、明确跳过/忽略或新的
   四类阻塞出现时，仅在操作发起的文件上下文仍有效且无新编辑的情况下回概览。仍需同类修正
   时保留输入和位置。技术终结失败显示该项已知结果。不得以请求接收、任意新摘要或其他文件
   的读回推断本条已处理。翻页、往返、关闭重开、刷新、重连和较新草稿分别保持现有可保存范围、
   读回状态和准确身份。背景读回仅更新命中的条目，保留已离开的当前界面、焦点及选项。
4. 复用现有整批确认与手动受理交接。将精确来源、目的地、操作及源文件影响、附件和不纳入原因
   放到可读的复核正文。按钮及原因仍受当前计划、精确子集、独立覆盖／清理权限、已受理历史及
   现有窗口约束。准备、概览和详情之间的浏览保持零媒体变更。最终点击保留发送时的不可变
   请求，原丢回包核对优先且与后续编辑的计划分别保存。证明受理后用原有回调打开准确 Task。
5. 用本地弹窗的内容边界管理滚动和焦点。新阶段合理定位标题或反馈，手动查看可回到概览的对应
   文件，状态轮询维持稳定。保留关闭／Escape、草稿提示、键盘、长路径换行、单正文滚动、缩小
   视口和 reduced-motion。

### Acceptance Criteria

- [ ] 在 Files 现有单项、批量、文件夹和混合范围入口打开原弹窗。从初次准备到概览，再打开文件
  核对路径、操作、附件和证据。分别核对等待稳定、后台不可用、范围拒绝／排除、无主文件、取消、
  源读取失败、计划读取失败和恢复读取。100 项进入正常复核，第 101 项或实质范围不足没有可确认
  的截断前缀。对照 Base 比较顶栏、原标题、Files 和 Task Center 背景入口。
- [ ] 真实混合批次逐项处理识别、元数据候选/搜索修正、分类和冲突。合法跳过/忽略、新问题、
  原阻塞仍在和技术失败显示对应事实。核对无效元数据输入、决定保存失败、决定已保存但分析拒绝、
  分析排队以及未知后证明受理/未受理。分析尚在等待时，不能提前回概览或放出重复操作。
  已选择 10 项时用原动作逐项处理，最终只确认一次。
- [ ] 保存 A 后打开 B 并编辑，或查看整批复核时，A 的迟到读回不切页、不替换 B 草稿、不抢焦点。
  同一文件返回、新状态说明、真实计数、目标路径、已纳入选择、刷新、重连、准确重开与关闭提示
  可核对。用桌面、390 px、矮窗口、长路径、键盘和 reduced-motion 看正文。未变化的后台读回
  保持当前滚动。
- [ ] 分别验证明确选择、排除未就绪/已受理项、覆盖/清理的独立授权、计划过期和权限/来源变化。
  模拟双击、失去最终回包、受理读取失败、有效的原批确认以及兄弟重新分析。检查同一原请求，
  核对原 Task、最终 Result 与 pin，确认前媒体目录零变更，执行只触及明确范围。成功或效果
  未知兄弟不重放。
- [ ] Task Center 的「继续整理」仍打开原逐文件弹窗，首次关联、已开弹窗后的读失败、原任务
  详情回落、历史准确只读地址和原生四类恢复的行为沿用 Base。已受理的 Files 交接准确打开原
  任务详情。任务详情正文在这个 Task 内保持 Base。

### Required Tests

遵循 [开发和验收分工](docs/development-workflow.md#6-test-levels)。以下 npm 命令在 `web/`
运行。新增或调整的原生用例标题以 `Task59.1` 标记，便于定位本 Task 的回归。

**Developer**

- `npm run typecheck`。用 `npm exec -- eslint src/features/operations/ManualOrganizeDialog.tsx src/features/library/StorageFilesPage.tsx` 和
  `npm exec -- prettier --check src/features/operations/ManualOrganizeDialog.tsx src/features/library/StorageFilesPage.tsx`
  检查触及的源文件，并将实际新增或修改的其他源文件、样式和测试纳入对应命令。仓库根运行
  `git diff --check`。
- `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/organize-confirmation-session.test.ts src/features/operations/organize-admission-watch.test.ts src/features/operations/OperationsRouter.test.tsx src/features/library/StorageFilesPage.test.tsx`。
  核对两种 Host、准备/概览、四类状态、延迟读回保护、选择与保留原提交。新增的纯 UI 规则
  缺口覆盖稳定锚点、相同旧摘要、不同兄弟或操作轮次以及更新后当前权威动作。
- `npm run build` 后运行
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'Task59[.]1|unknown original submission|100-file batch|101-file directory'`。
  核对实际入口、受影响的进度和失败恢复、更新过断言的旅程和不重放。将新的视觉、导航和精确范围
  断言放在上述受影响用例中。

**B**

- 在精确候选上核对实际 diff 和保护边界，并运行 `npm run typecheck`、`npm run lint`、
  `npm run format:check`、`npm run build`。直接复用符合工作流条件的单测证据，补跑受影响
  用例。T3 针对受影响原生旅程和 Web 门禁，若出现影响执行安全的变更先交 A 核对范围。
- `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/task-center-layout.spec.ts`。
  核对原选择、入口、背景、任务定位、标题和布局。捕获桌面与窄屏关键阶段的可读性证据。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts`。
  用隔离 API/SQLite/Worker 走通 AC-01–03，包括新四类混合任务、100/101 项、兄弟并行输入、
  保存阶段拒绝以及原提交丢回包后新计划生成。比对临时源／目标、请求项、原 pin、Result 和审计。
  若出现以前的夹具失败，在 Task Base 复现并保留两边实测结果，按工作流判定。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place|detail tab and filter context'`。
  核对原位二层弹窗与背景详情位置、读回、历史和任务返回。独立复核允许的继续仍沿用原精确关联。

### Non-goals

任务中心任务详情正文的视觉改造属 RO-4。任务中心另开的整理弹窗、原生四类恢复承载、全局
Shell、文件和任务列表、共享弹窗外壳、命令与权限、API/Worker/Storage/schema、运行时配置
及离线演示交互均在本 Task 实现范围之外。实现期按 Slice 范围复用现有机制。

### Developer Completion Report

待实施候选和受影响测试结果。

### B Review Result

待对实施候选独立审查。
