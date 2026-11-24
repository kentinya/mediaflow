# Task 59.1 — 文件入口的手动整理弹窗与整批确认

Next Action: B REREVIEWS THE TASK 59.1 CORRECTION CANDIDATE

用户已授权激活 Task 59.1。Developer 开始实施时将状态从 `PLANNED` 转为
`IN PROGRESS`。原 Task ID、Base、范围和验收条件沿用。A 代 B 的授权限于本 Task 的规划，
B 独立复核实施候选，A 负责 Slice 终审。
[Slice 59](SLICE.md) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: READY FOR B REVIEW
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Difficulty: High
Test Level: T3
Planner / Reviewer: A plans once under explicit user authorization / independent B reviews
Implementation Authorization: AUTHORIZED BY USER FOR TASK 59.1
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

已按 Task 范围实施并冻结候选：

- Files 现有入口显式承载新增层级；Task Center 原位/历史仍走原逐文件视图。
- 准备首屏补充真实阶段文案；方案读回后进入「本次整理概览」，按当前摘要与执行读回显示
  待处理、可确认、已纳入、已有记录，未受理范围单列；同一弹窗可打开逐文件复核并返回概览，
  返回时定位对应文件。
- 逐文件决定仅在原文件仍被查看、没有新编辑、且该条目自身的更新读回证明结果时回落：
  可确认方案/明确跳过回概览，新的四类问题回概览，同类问题保留输入与位置，技术结果原位显示；
  迟到兄弟摘要只更新数据，不切页、不抢焦点。
- 整批复核补充 Files 专属来源、操作、附件与不纳入原因；Task Center 批次展示保持 Base。
- 复用原准备、决定、计划、确认与原请求核对权威；未新增 API/schema/Worker/权限。

实际命令与结果（cwd `web/`）：

- `npm run typecheck` — 通过。
- `npx eslint` 触及源/测试文件 — 通过。
- `npx prettier --check` 触及源/样式/测试 — 通过。
- `npm run test -- run` 六个受影响文件 — 6 files / 152 tests passed。
- `npm run build` — 通过。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'Task59[.]1|unknown original submission|100-file batch|101-file directory'` —
  首轮 16 passed / 1 既有入口时序失败（`Task59.1 manual organize readability: one file` 在
  `organizeDiscovery=` 地址更新前读取，弹窗已可见）；单独重跑通过（1 passed），首轮失败保留记录。
- 另跑受影响的 6 个原生旅程（逐项决定、第二次确认、冲突、元数据修正、未知原提交、新概览）全部通过。

已知限制/风险：概览行按当前摘要逐条渲染，100 项时正文较长但保持单一滚动；真实原生全量由 B 执行，
B 需重点复核 100 项可读性、兄弟迟到读回和 Task Center 原行为。

### B Review Result

**FIX REQUIRED**。B 独立审查范围为
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..815c2ca194e23922d1440f0162e4ffa532c0a068`。
原 Task 的 Base、范围和 T3 门禁沿用。

- **AC-02 / P1**。从资源库文件页选中有真实目标冲突的文件和一个就绪兄弟，打开整理概览，
  进入冲突文件，选择「重命名目标」，点击「保存并重新分析」。隔离原生浏览器复核放行真实
  分析请求，确认 API 返回成功后只让该响应在浏览器丢失。弹窗读到后台正在分析。Worker
  发布新方案后，同一文件出现可勾选的「纳入」和新方案，但概览和该文件的新状态反馈没有
  自动出现，用户须手动返回。该步骤只有一次分析请求，确认前的临时媒体状态保持原样。
  正常收到成功响应的同一旅程可以自动回概览，并显式确认到原任务。
- **AC-03 / P1**。整批复核里有附件的已选文件只显示附件数量。用户选中带字幕或 NFO 的
  文件并进入最后一次确认时，需要离开整批复核、逐个打开文件，才能看到附件。该页的已选
  文件清单缺少合同要求的附件核对内容。依据是原候选的整批行只呈现计数，逐文件正文已
  持有附件的计划事实。

复核证据（cwd `web/`）：`npm run build` 通过，构建前后入口制品哈希一致。
原生 `manual-organize-dialog.python.spec.ts` 的 `a real destination conflict` 通过
（1 项，13.3 秒）。临时复现实验沿用该旅程，第一次等待手动重读按钮超时（19.4 秒），
因为旧方案被已读到的分析中状态替换。改为从页面实际显示的分析阶段推进原 Worker 后，
复现断言通过（1 项，12.4 秒）：新方案可纳入、仍停留单项详情、手动返回可打开概览。
针对 `ManualOrganizeDialog.test.tsx` 的概览相关筛选通过（3 项，2 秒，其余 39 项未选）。
临时探测脚本已移除。聚焦测试和复现合计约 47 秒，低于本轮复核耗时的一半。
依据已复现的阻塞提前返回，完整 T3 验收留待修正候选。

### Developer correction guide

1. 在 Files 的同一文件点击「保存并重新分析」时，保留这次操作对应的准备、条目和当时界面
   上下文。沿用现有同一条目／准备的读回，以本次操作对应的新方案或明确条目结果决定回落。
   让正常成功响应与成功回包丢失后读到同一结果走同一个概览回落路径。等待、明确拒绝和
   同类待修改仍保留原位和合法下一步。用户已去看其他文件或整批复核、或开始新的编辑时，
   只更新相应条目。复用现有读回与动作，不增加重提操作。
2. 在 Files 的「本次确认的文件」里为有附件的条目加可展开的附件清单。沿用逐文件复核的
   现有计划数据，展示该附件的来源、目标、操作和已记录的排除或异常原因，让用户能在最终
   确认页完成核对。继续沿用原选中子集、授权和提交入口。
3. 在现有 `Task59.1` 原生冲突旅程的同一入口覆盖成功回包丢失。仅拦截页面真实点击发出的
   分析响应，真实 API 受理与 Worker 发布照常执行。断言等待期间仍在同一弹窗，发布后自动
   回到概览并显示当前文件可纳入，其他项不变，分析请求只一次，确认前媒体无变更。用已有
   概览与整批复核用例的带附件数据核对展开内容、选择范围及确认前零变更。Developer 运行
   本 Task 原列出的受影响检查和对应 `Task59.1` 旅程，提交修正候选供 B 重审。

Slice 重评：RO-1 的准备和概览入口已有实现，完整门禁待复核。RO-2 的异常回包后回落及
RO-3 的附件核对仍有上述缺口。RO-4 的任务详情正文当前未交付，仍属 Slice 的后续范围。
本轮继续修正 Task 59.1。

### Developer Correction Report

已按 B 的修正指引完成候选，范围仍限于 Task 59.1：

- Files 的逐文件「保存并重新分析」在请求发出前捕获该条目与当时方案的读回基线；
  手动选择与原生决定共用同一回落判定。正常成功回包和回包丢失后，均由同一准备／条目
  的新方案读回决定是否回概览；等待、明确拒绝和同类待修改仍留原处。原生决定的分析状态
  `analysis_waiting`／`analysis_unknown` 也会触发同一准备的读回，不依赖任务中心另一次读取。
- 「本次确认的文件」中有附件的已选条目可展开查看每项附件的来源、目标、操作、
  `blockedReason` 与 `nextAction`；沿用原选中子集、授权和确认入口，展开不产生执行。
- 现有原生冲突旅程改为拦截页面真实点击发出的 `/recovery/continue` 响应：
  `route.fetch()` 让真实 API 受理与 Worker 发布照常执行，浏览器侧只丢失该响应。
  旅程断言未知等待期仍在原弹窗、发布后自动回概览并显示当前文件可纳入、
  分析请求仅一次、确认前媒体零变更；随后仍只确认冲突文件，健康兄弟项不重放。

实际命令与结果（cwd `web/`）：

- `npm run typecheck` — 通过。
- `npx eslint` 触及源/测试/E2E 文件 — 通过。
- `npx prettier --check` 触及源/样式/测试/E2E 文件 — 通过。
- `npm run test -- run` 六个受影响文件 — 6 files / 154 tests passed（新增 2 个 Task59.1
  回包丢失用例；概览用例补充附件展开、选择范围与零 Execute 断言）。
- `npm run build` — 通过。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep "a real destination conflict"` —
  1 passed（11.7 秒），已覆盖成功回包丢失后的自动概览回落。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep "a missing metadata candidate is corrected"` —
  1 passed（7.3 秒），原生正常成功路径无回归。
- 仓库根 `git diff --check` — 通过。

剩余风险：B 的完整 T3 验收与 100／101 项、窄屏、Task Center 原行为仍需在修正候选上执行；
附件展开的原生数据由 B 按其计划覆盖。未新增 API/schema/Worker/权限，未推送或发布。
