# Task 59.1 — 文件入口的手动整理弹窗与整批确认

Next Action: DEVELOPER CORRECTS TASK 59.1 AND RESUBMITS FOR B REVIEW

用户已授权激活 Task 59.1。Developer 开始实施时将状态从 `PLANNED` 转为
`IN PROGRESS`。原 Task ID、Base、范围和验收条件沿用。A 代 B 的授权限于本 Task 的规划，
B 独立复核实施候选，A 负责 Slice 终审。
[Slice 59](SLICE.md) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
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

### B Re-review Result

**FIX REQUIRED**。审查 `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..327f111d39a795288bb975cb14696bb3e4cf963b`。
前轮原生冲突表单的成功回包丢失后，已能读回新方案并自动回到概览，原生用例继续通过精确确认
与任务交接。整批复核的附件清单已能展开，前轮缺口通过定向用例复核。

- **AC-02 / P1**。在 Files 打开就绪文件的概览，进入该文件，展开「修正识别或作品」，
  选择另一种允许的识别类型并点击「保存并重新分析」。真实 API 已受理，浏览器丢失响应，
  同一准备的首次重读稍慢时，页面直接提示可以再点击并启用按钮。B 在原生浏览器用现有
  冲突旅程的第一段复现，放行真实 API 请求并只延后后续准备 GET，实际第二次点击发出了
  第二个分析请求。没有提交文件执行，临时源和目标未发生变更。分析失败统一放开按钮的行为
  可追溯至 `99328d5d`（2026-11-09），本候选继续使用它。Task 验收要求读回明确未受理后
  才补做分析。
- **T3 验收门禁**。Files 新概览符合此处的界面合同。现有浏览器用例仍在 Files 等待原
  单文件首屏，截断了实际选择、重开、确认及从任务中心继续的后半段。Web 实跑 17 项通过、
  4 项因等待旧首屏失败、1 项中断、42 项未运行。原生定向组 2 项通过、1 项在
  Files 准备完成后等待旧首屏失败，尚未走到「继续整理」。快照均已显示「本次整理概览」。
  该断言与界面差异来自首个实施提交 `815c2ca1`。

实际验收（cwd `web/`）：typecheck、lint、format:check、build 通过。六个受影响单测文件
154 项通过，包括附件展开。原生冲突和详情筛选上下文通过。临时原生探测运行 1 项，
复现第二次请求，并已移除探测脚本。已停止剩余长套件，完整 T3 验收待修正候选。
治理及 Base..候选的 `git diff --check` 通过。

### Developer correction guide for re-review

1. 在 Files 的「修正识别或作品」直连分析入口，把已保存选择后的未知分析结果接入现有的
   同一准备读回。受理与否未读清时保留已保存的选择，展示读取状态。读到已受理时等待并显示
   后续方案，明确未受理时原按钮只补做分析。沿用现有请求和版本身份。真实冲突表单的回落、
   整批附件、确认身份和 Task Center 原位续作按现行合同保持。
2. 在现有原生冲突用例的第一段或同一入口的直接修正用例复测。成功受理后丢失分析响应，
   在同一准备读回期间检查页面保持等待，保存按钮不可再次提交。读回后核对只发一次分析、
   自动回到概览、文件未变更。再用原有拒绝数据检查只有明确未受理才恢复分析按钮，
   且先前选择只保存一次。
3. 更新受影响的 `library-files.spec.ts` 和 `operations-inventory.python.spec.ts`。
   Files 阶段先验概览，单项操作经对应文件进入详情，再继续原有断言。Task Center
   「继续整理」仍验直接打开既有单文件界面，保留准确任务、草稿、位置、只读和无重复受理
   断言。Developer 跑新改和直接受影响用例，B 在新候选执行原 T3 门禁。

Slice 重评：RO-1 仍待完整核对，RO-2 的直接分析未知状态阻塞本轮通过。RO-3 附件修正
已覆盖，完整交接门禁仍待复核。RO-4 的详情正文仍待交付，留在原 Slice 边界。

### Developer Correction Report (re-review)

已按上一轮 B 复核指引修正，范围仍限于 Task 59.1。实现候选
`bc0e04063d996aef2c1619198df62033e03f2569`：

- Files 的「修正识别或作品」直连分析在保存选择后，把任何未确认的分析结果先接入现有
  同一准备读回。读回期间保持当前文件、已保存选择和输入现场，保存按钮与识别/身份选择
  均锁定，并显示实际读取状态；慢速首次读回无法再发第二个分析请求。
- 读回由同一准备/条目的真实事实决定：仍在分析、新方案已链接或准备版本变化视为受理，
  进入等待并沿用现有概览回落；版本、状态和方案均未变化才恢复原按钮的分析-only 补做；
  读取失败保持锁定，只提供同一准备的重新读取，不自动重发分析。
- 已受理后的方案事实没有变化时（例如仅兄弟摘要变化）释放等待，不再无限锁定当前文件；
  离开文件、返回概览、翻页、整批复核和新编辑都会终止旧条目读回。
- 现有原生冲突表单、整批附件、确认身份、Task Center 原位续作和只读历史未改变。
- 更新 `library-files.spec.ts` 与 `operations-inventory.python.spec.ts` 的 Files 阶段为
  先验「本次整理概览」、再经对应文件进入详情；Task Center「继续整理」仍直接打开既有
  单文件界面。
- 更新 `TaskItemRecoveryPanel` 原有无障碍路径未变；未新增 API、schema、Worker、权限或
  执行授权。

实际命令与结果（cwd `web/`）：

- `npm run typecheck` — 通过。
- `npx eslint` 触及的 5 个源/测试/E2E 文件 — 通过。
- `npx prettier --check` 同上 — 通过。
- `npm run test -- run` 六个受影响单测文件 — 6 files / 156 tests passed，包含新增
  回包丢失锁定、明确未受理后分析-only 补做、兄弟摘要释放等待用例。
- `npm run build` — 通过。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep "lost direct analysis|a real destination conflict"` —
  2 passed；新增直连分析丢回包用例首轮曾因地址更新 10 秒超时失败一次，扩为 30 秒后重跑
  6.1 秒通过，既有冲突旅程 11.6 秒通过。
- `npm run test:e2e -- tests/e2e/library-files.spec.ts` — 51 passed（37.0 秒），包含
  Files 概览、单项详情、重开与确认前零执行断言。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "...前序 10 项|new task selection reconciles"` —
  11 passed（15.0 秒）；另跑更新的 opened-item、selected-execution、ambiguous-source、
  ordinary Files navigation、initial preparation 五个用例 — 5 passed。
- 仓库根 `git diff --check` — 通过。

先前一次仅取前序单个文件加 `new task selection` 子集时在 `run-manual-worker` 超时，
补齐该文件真实声明顺序前序 10 项后重跑通过；属于夹具状态顺序依赖，不是产品断言失败。

已知限制/风险：B 的完整 T3 仍须覆盖 100/101 项、窄屏、Task Center 原行为和真实混合
批次；本轮未重跑这些长套件。未推送或发布。


### B Review of the analysis read-back correction

**FIX REQUIRED**。独立复核范围
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..02aa6e6d746ecf7bb3f4ecbdd6360606976af10f`。
Files 原地慢读的丢包旅程已验证只请求一次分析，新方案读回后自动返回概览。
上轮因等待旧首屏而中断的五条 Files Web 旅程、本次任务中心常规续作和详情筛选上下文均通过。

- **P1 / 原位续作边界**。在 Files 准备一项后关闭弹窗，从任务中心找到同一任务并点
  「继续整理」。进入文件的「修正识别或作品」，将移动改成复制，点击「保存并重新分析」。
  原生复核只丢弃真实 API 已受理的分析回包，Worker 仍发布了不同于原摘要的新方案。
  当前方案正文已经显示「复制 · 来源保留」，同一弹窗却仍显示「等待新的零变更方案…」、
  宣称将自动回到概览，并将当前文件的「纳入」保持禁用。整个复现仅有一次分析请求，零
  文件执行。回归来自 2026-11-24 的 `bc0e0406`：共享弹窗在两种入口都建立了新增的
  分析等待状态，但只有 Files 概览回落会在方案读回后解除它。
- **T3 用例顺序**。原生冲突和新增 Files 直连丢包用例在同一次运行时，前者通过，后者在
  进入整理准备前被真实来源占用拒绝。先跑的冲突用例将 `DialogSibling.2023.mkv` 留作
  未结束任务的兄弟项，后一个用例又用同一来源开始整理。界面的「所选文件已有未结束的
  整理工作」解释了地址为何未更新。丢包用例单独运行通过。需要让它能和原冲突旅程同跑。

复核结果（cwd `web/`）：typecheck、lint、format:check、build 通过。Files 定向 Web
5 项通过，直连读回相关定向单测 3 项通过。原生正常续作和详情上下文 2 项通过。
原生冲突、直连丢包分别通过，其中组合运行
为 1 通过、1 因来源占用失败。临时原生探测两次复现任务中心等待，第二次同时验证新复制
方案已经显示。尝试从 Files 概览返回同一文件时，慢读期间控件仍禁用，预设的第二次请求
未复现。临时脚本已移除。治理及完整范围的 `git diff --check` 通过。
根据已复现的回归提前返回，100/101 项、窄屏和其余 T3 组合验收待修正候选。

### Developer correction guide after analysis read-back review

1. 按入口落实两条旅程。Files 保留本轮已通过的同一准备核对和读回后回概览。任务中心
   「继续整理」沿用合同中的原位逐文件复核，新方案读回后在原位置核对并可操作，显示适用于
   当前入口的状态和动作。利用现有 host 边界隔离 Files 的概览读回状态，复用原任务与方案。
2. 在现有「继续整理」原生旅程复测。通过 Files 建立准备，经任务列表打开同一任务，点击
   「继续整理」，用已有的识别类型选项改成可区分的新方案。让真实 API 受理，只丢失浏览器
   回包。Worker 发布新方案后断言页面显示新操作、等待结束、可调整纳入，随后从原弹窗
   复核精确范围。核对仍是同一任务，确认前只有一次分析、零执行。
3. 给 Files 直连丢包用例使用独立的临时媒体来源及相应现有 Provider 夹具。把它和现有
   冲突旅程放在同一次原生运行，保留来源占用、实际分析次数、回到概览和零媒体变更断言。
   Developer 运行这两条旅程、修改后的任务中心用例及直接受影响检查；B 继续原 T3 验收。

Slice 重评：RO-1 的定向概览和重开已验证。RO-2 的 Files 直连丢包已通过，任务中心原位续作
出现本轮回归。RO-3 的单项精确交接、附件展开已有通过证据，其余组合待完整验收。RO-4 的
任务详情正文仍待交付。本轮继续修正 Task 59.1。

### Developer Correction Report (in-place analysis read-back)

按上轮修正指引实施，范围仍限 Task 59.1。实现候选
`b74cfb07d60187ecfedb04135f7b07f2eb0c5029`：

- 共享弹窗按 host 落实两条旅程。Files 仍用同一条目/同一准备的读回回到概览；任务中心
  「继续整理」保留原位逐文件复核：未知分析结果经同一准备读回证明受理后，新方案或该条目
  自身结果在原文件就地显示，纳入与后续动作恢复可用，措辞为当前入口的状态。
- 原位基线仅在分析结果未知时启用，普通成功回包保持 Base 表现；离开该文件、进入整批复核、
  新编辑或迟到受理证明都不会替换已显示的原位结果。兄弟摘要只按条目事实处理：本条目事实
  未变时释放等待并说明，不推断本条已处理。
- Files 直连丢包旅程改用独立临时来源 `Dialog/DialogDirectLoss.2038.mkv` 与既有 Provider
  夹具新增身份 718，不再借用冲突旅程的兄弟来源；两条原生旅程同次运行通过。
- 现有「继续整理」原生旅程（PATCH-20261113-3）扩为丢包旅程：真实 API 受理 MOVE→COPY
  修正、Worker 发布新方案，浏览器只丢该回包。断言等待期间不重发、新方案显示「复制 ·
  来源保留」与真实目标、纳入可调整、原弹窗整批复核仍是同一任务精确范围、分析仅一次、
  确认前零执行与临时媒体零变更；确认后由真实 Worker 复制（来源保留），后续只读历史不变。

实际命令与结果（cwd `web/`）：

- `npm run typecheck` — 通过。
- `npx eslint` 触及的 2 个源/测试文件与 2 个 E2E 文件 — 通过。
- `npx prettier --check` 同上 — 通过。
- `npm run test -- run` 七个受影响文件（新增 `OperationsInventory.test.tsx` 两条原位用例）
  — 7 files / 220 tests passed。
- `npm run build` — 通过。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'a real destination conflict|lost direct analysis response stays locked'` —
  2 passed（19.2 秒），两条旅程同次运行无来源占用失败。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'PATCH-20261113-3 initial manual preparation remains reachable in place from Task Center'` —
  1 passed（17.3 秒）。
- 反向验证：临时停用本条修复后同一原生旅程在「原位读回新方案」断言超时失败（30.2 秒），
  恢复后通过；临时改动未提交。新增两条单测在停用修复时同样失败。
- 仓库根 `git diff --check` — 通过。

已知限制/风险：B 的完整 T3 仍须覆盖 100/101 项、窄屏与任务详情正文；原位等待仅由该条目
自身的新方案、离开/返回或新编辑解除，若分析被受理却始终未发布新方案（旧方案仍可读），
本轮不变更该既有边界；附件展开与任务详情正文仍属 Slice 后续范围。未新增 API、schema、
Worker、权限或执行授权；未推送或发布。


### B Review of the in-place continuation correction

**FIX REQUIRED**。独立复核 `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..c25f69a2e28f40a9d3e5276b244a00e480e72193`。
实现为 `b74cfb07`，其后两个提交仅更新 TASK 报告。上轮两项已验证：任务中心丢回包后
在原文件显示复制方案、恢复纳入并继续到原任务结果。Files 的冲突与直连丢包用例在同一次
原生运行中均通过。

- **AC-02 / P1：元数据服务连接失败被显示成候选待选。** 在 Files 同时选中两个实际文件，
  点击「批量整理」。隔离原生复核只让其中一个文件的测试 Provider 返回连接失败，正常
  API 和 Worker 发布结果。概览却提示「需要处理元数据候选；保存决定并重新分析」；点入
  该文件没有候选恢复表单，详情称「Storage failure」，下一步又要求检查 Metadata Provider。
  后端摘要记录的是元数据阶段技术失败，没有关联的候选问题项。就绪兄弟项仍独立纳入，
  浏览和核对期间零执行。首次探测因页面使用有界错误文案而未匹配夹具原文，第二次按实际
  可见状态及 API 结果验证复现。误导性的概览指引来自 2026-11-24 的 `815c2ca1`：
  概览把元数据阶段直接当成候选决定，导致技术失败既看不清原因，也没有提示中承诺的动作。
- **T3 完整原生套件仍有来源串用。** 新增概览与焦点用例和原有单文件来源／目标可读性用例
  都从 Files 选 `ReadabilityOne/ReadableOne.2011.mkv`。前一用例留下未确认准备，后一用例
  被后端如实拒绝重复受理。页面明确显示「所选文件已有未结束的整理工作」，等待地址更新
  只是后续超时。单文件可读性用例在独立运行中通过，来源串用由 `815c2ca1` 新增的概览
  用例引入。

实跑（cwd `web/`）：typecheck、lint、format:check、build 通过。Files／任务中心布局
Web 64 项通过。原生整理全文件套件 16 项通过、1 项来源占用失败、3 项未运行。另从干净
夹具运行单／十／100／101 项可读性和边界及任务中心两个定向旅程，共 6 项通过。
已查看 100 项整批复核的桌面、390 px 和矮屏截图。原生 Provider 故障探测最终 1 项通过，
结果证明上述用户可见问题。临时探测脚本及配置已移除。治理和完整范围的 `git diff --check`
通过。完整同次原生门禁及余下组合验收待修正候选。

### Developer correction guide after the in-place review

1. 在 Files 概览和文件详情中，沿用已有条目状态、分析结果及关联的业务问题，统一呈现该
   文件的当前结论。有真实候选决定时引导选择；元数据服务技术失败时说明当前阶段和已知
   影响，附上适用的 Provider 排查及原任务结果查看方式。四类业务问题和技术阶段各用
   自己的已发布证据。详情中与技术事实矛盾的 Storage 提示同样用现有元数据证据纠正。
   修正限定在当前 Files 正文，复用现有读模与动作。
2. 用现有 Files 批量入口验证一个 Provider 连接失败文件和一个就绪兄弟。让正常 API/Worker
   产生摘要，只在本地测试 Provider 注入错误。核对概览、该文件详情、兄弟选择与零执行，
   并用已有元数据候选旅程对照真实候选仍可选、可重新分析并返回概览。
3. 让概览焦点用例与单文件可读性用例使用不同的临时来源，或在一次已受理准备中完成二者
   的原断言。保留概览返回、精确来源与目标、窄屏和矮窗断言。Developer 同次跑受影响两条
   用例及 Provider 故障对照。B 在修正候选上运行完整原生门禁。

Slice 重评：RO-1 的主要入口、预览回读与 100/101 项边界已有通过证据。RO-2 的原位回落
已验证，本轮技术失败指引阻塞。RO-3 的附件、精确子集及原请求交接已有通过证据，组合
验收继续。RO-4 任务详情正文仍待交付。修正继续在 Task 59.1。


### Developer Correction Report (metadata stage and source separation)

已按 B 的修正指引完成候选 `b59c86b7b8b74534e63544e8e9da003b5f6a4500`（含
`2ee98c1e`），范围仍限 Task 59.1。

- Files 概览与文件详情统一从条目的已发布证据得出当前结论：只有真实的识别、元数据
  候选/修正、分类或冲突问题才提示保存决定；`analysis.metadata.status=provider_error`
  显示「元数据服务技术失败」，说明元数据阶段未完成、没有可用候选与候选恢复表单、
  当前文件不可纳入且未修改任何文件，并提供 Metadata Provider 排查及任务中心原整理准备
  任务的结果查看方式。详情不再显示与元数据证据矛盾的 Storage failure 分类，方案区也
  不再写成仍在等待分析。Task Center 原位/历史继续沿用含 stage 的 Base 问题判定，
Files 才只读取已发布的业务证据。
- 概览的迟到分析回落不再把 Worker 重规划期间可读的、已被取代的旧摘要当作本次分析结果；
  只有新摘要中的该条目仍是当前事实，或出现明确业务问题/可执行方案时，才改变页面或
  释放等待。该保护修复了去掉 stage 猜测后暴露的旧摘要回退，不改变既有同条目劝阻、
  兄弟摘要和迟到读回边界。
- 原生夹具新增 `ProviderFailure/ProviderFail.2011.mkv`（本地测试 Provider 连接失败）
  与 `ProviderReady.2011.mkv`（就绪兄弟），经真实 Files 批量入口、真实 API/Worker
  产生摘要；概览与详情显示元数据技术失败，就绪兄弟仍独立纳入，核对和整批复核期间
  Execute 为 0。
- 概览焦点用例改用独立来源 `ReadabilityDialog/ReadableDialog.2011.mkv`，不再与单文件
  来源/目标可读性用例串用 `ReadabilityOne/ReadableOne.2011.mkv`；两条用例同次原生
  运行通过。

实际命令与结果（cwd `web/`）：

- `npm run typecheck` — 通过。
- `npx eslint src/features/operations/ManualOrganizeDialog.tsx src/features/operations/ManualOrganizeDialog.test.tsx tests/e2e/manual-organize-dialog.python.spec.ts` — 通过。
- `npx prettier --check` 同上 — 通过。
- `npm run test -- run` 六个受影响单测文件 — 6 files / 157 tests passed（最终候选）。
- `npm run test -- run src/features/operations/OperationsInventory.test.tsx -t "Task59.1 reads a lost in-place analysis|Task59.1 releases an in-place analysis wait"` —
  2 passed，最终候选的原位 Base 判定无回归。
- `npm run build` — 通过；当前入口 `dist/index.html` SHA-256
  `eaa6a96c189d736da1ca4ef45520a10fa312124f4ebb35d90a329579c30ee23e`。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'Task59[.]1|unknown original submission|100-file batch|101-file directory'` —
  19 passed（2.1 分钟），在 `2ee98c1e` 上包含新增 Provider 故障旅程、共享来源两用例、
  100/101 项边界；最终候选另复跑供应商故障与元数据候选对照 2 passed，隔离仅恢复
  Task Center 的 Base 回落。
- 仓库根 `python3 scripts/check_governance.py`、`.venv/bin/ruff check/format --check
  scripts/operations_inventory_harness.py`、`git diff --check` — 均通过。

已知限制/风险：Provider 故障由隔离夹具的本地测试 Provider 注入，生产 TMDB 的真实连接
故障留给 B 的完整 T3；本轮只把已发布的 `provider_error` 识别为元数据技术阶段，其他技术
阶段沿用原受限失败文案。若被取代的旧摘要是唯一可读状态且整理流程仍未结束，同文件等待
保持锁定，结束后的只读历史仍由既有结束流程展示。B 的完整原生/Web 门禁与桌面、390 px、
矮窗证据仍需在修正候选上执行；未推送或发布。

### B Review of the metadata failure journey

**FIX REQUIRED**。独立复核
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..6fb9e977134f0ac0f302aed649a36c230ae38463`。
实施 HEAD 为 `b59c86b7`，后继提交只更新 TASK 报告。上轮两处修正已验证：概览和文件详情正确
识别元数据服务技术失败，原生概览焦点、单文件可读性用例在同一次完整运行通过。

**AC-02／AC-03 / P1：同一个技术失败在后续操作中变成 Storage 故障，详情还指向当前不可用的操作。**
B 使用已经提交的 Provider 故障夹具和正常 Files 批量整理入口，复现两条实际操作：

- 选中故障文件和就绪文件。故障文件的当前状态提示「然后重新分析同一准备」。打开「修正识别或
  作品」并保留原选择时，「保存并重新分析」禁用，该页没有可执行的分析动作。返回概览、进入
  「整批复核」、展开「未纳入本次确认的文件」时，同一文件又显示为 Storage failure，
  而就绪兄弟仍可独立确认。
- 只选择故障文件。原任务结束后，Files 弹窗的「只读原计划摘要」仍将该文件显示为 Storage failure。
  两条探测均未发起文件执行。

整批未纳入和 Files 只读历史仍直接使用通用失败文字，未采用 `2ee98c1e` 已用于概览和详情的
明确元数据证据。该提交也加入了「重新分析同一准备」提示，但详情中的分析按钮要求有可保存改动，
现有独立运行分析入口只用于尚未链接第一份计划的准备。这里要修正前后贯通的原因和下一步。

实跑（cwd `web/`）：`npm run typecheck`、`npm run lint`、`npm run format:check`、
`npm run build` 通过。Files／任务中心布局 Web 64 项通过。真实 Python 整理全文件 21 项在同一轮通过（约 2.2 分钟），
含 100／101 项边界。任务中心原位续作与详情上下文 2 项通过。查看了整批复核在桌面、390 px 和
矮屏的截图。额外沿现有入口做的两条故障探测均复现上述现象，临时脚本和配置已移除。
治理及完整范围的 `git diff --check` 通过。

### Developer correction guide after the metadata review

1. 把已用于 Files 概览和详情的元数据故障结论复用于整批未纳入行及 Files 只读摘要。就绪兄弟的
   选择和现有确认入口照常使用。Task Center 的独立历史入口沿用合同规定的呈现和只读边界。
2. 把「重新分析同一准备」改为当前条目实际可走的动作。该技术失败可以核对 Provider 和原任务结果；
   已结束的失败项按已有 Files 入口重新发起独立准备。详情避免把技术失败写成等待人选择或修改识别
   类型的任务。沿用现有活动范围和状态，不新增技术重试入口。
3. 扩展现有原生 Provider 故障用例：混合批次打开故障详情和整批未纳入项，核对相同原因与现有
   下一步、就绪兄弟可确认及确认前零执行。仅选故障文件的准备结束后，核对只读摘要的同一原因
   及无执行入口。使用现有本地夹具并遵循独立来源或原准备已结束的条件。

Slice 重评：RO-1 的主要入口与准备边界已验证。RO-2 的故障原因和下一步、RO-3 的未纳入原因须
在同一 Files 旅程内统一。RO-4 任务详情正文仍待交付。修正继续在 Task 59.1。
