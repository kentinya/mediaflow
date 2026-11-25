# Task 59.3 — 任务详情状态、进度与文件行

Next Action: DEVELOPER REFRESHES FILE ROWS WHEN THE TASK SETTLES ON THE RECORDS TAB

```text
Task ID: 59.3
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: d1ea5f667c5ebc08e1a6835030197c1724f4f4d2
Reviewed Implementation Head: 47b2a48b1aba865fb06f1505019ae131ea84c541
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: SLICE 59 RO-4 / AC-06 TASK DETAIL STATUS AND FULL-ROW DISCLOSURE
```

## B 复核与 Slice 59 交接

**Task 59.1 — PASS。** B 从干净的 `main` 审查完整 Task
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..d1ea5f667c5ebc08e1a6835030197c1724f4f4d2`
及完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..d1ea5f667c5ebc08e1a6835030197c1724f4f4d2`。
在 `ReadabilityOne` 和 `ReadabilityTen` 从现有 Files 入口读回方案。逐项复核的 Storage 目标和整批
确认的库内目标都保留完整路径，在桌面、390 × 844、390 × 520 一致。补验从 `Dialog` 选两部影片，
确认前逐项与整批均显示同一目标，临时媒体根无变更。只确认第一部，实际 Worker 将其移到
`Movies/Movies/Anime/…` 对应位置，第二部留在原处，只有一笔执行提交。
[目标展示](web/src/features/operations/ManualOrganizeDialog.tsx#L270)

治理、全区间差异检查、类型、构建、改动文件 ESLint／Prettier 通过。57 项原组件及 2 项新增组件测试
共 59 项通过，Files 和任务中心布局浏览器 64 项通过，原生回归 10 项通过。另有 1 条真实目标与
最终 Storage 效果的补验通过。本机日志及截图在
`.git/validation-evidence/d1ea5f667c5ebc08e1a6835030197c1724f4f4d2/b-task59.1-review/`。
上轮阻塞见 `f97c9199:TASK.md`。

**Task 59.3 — FIX REQUIRED（P1，RO-4 / AC-06）。** B 从干净的 `main` 审查完整 Task
`d1ea5f667c5ebc08e1a6835030197c1724f4f4d2..47b2a48b1aba865fb06f1505019ae131ea84c541`
及完整 Slice `212acdef5d97c14a01353b22c103d44b911d6147..47b2a48b1aba865fb06f1505019ae131ea84c541`。
上轮问题记录在 `03267c9f:TASK.md`。

- **已通过。** 留在「任务详情」时，Worker 完成会对同一文件分页发出新的读取。首次文件分页真实
  响应在终态后迟到的用例也通过，原文件行显示「已验证成功」。元数据分析失败、确认前零执行、整行
  展开、筛选回落和原位续作的相关回归通过。
- **当前阻塞。** 从 Files 确认复制 `DialogConflict.2022.mkv`，在自动打开的详情读到「待处理」后
  切到「操作记录」。Worker 完成，导出可用，切回「任务详情」。首区显示「流程已完成」，结果区
  显示「1 已验证成功」，同一文件行却仍是「待处理」及原原因。页面只有一次文件分页请求，点击
  条目区「刷新」后才显示正确的行。终态读取放在 `RunItemsSection` 中，切到记录页时它离开页面，
  概览在记录页读到完成时，文件页旧读回没有失效。回到详情时挂载的文件页按终态起步并复用缓存，
  因此没有触发新读取。实跑使用现有 Task、Worker 和两页签，没有延迟或改写响应。
  [页签切换](web/src/features/operations/RunDetailTabs.tsx#L922) ·
  [终态读取](web/src/features/operations/RunDetailTabs.tsx#L1366)

**本轮实跑。** 治理、完整区间差异、类型、构建、Web ESLint 和 Prettier 通过。206 项组件、
103 项浏览器测试通过。原生组合 10 项通过，元数据修正的提交核对首跑超时，独立复跑通过。
记录页往返补验失败，手动刷新读到正确文件状态。原生日志、截图和失败轨迹在本机
`.git/validation-evidence/47b2a48b1aba865fb06f1505019ae131ea84c541/b-task59.3-review/`。

**Slice 59 仍为 FIX REQUIRED。** RO-1 的准备、概览和 100/101 文件边界，RO-2 的四类决定及回落，
RO-3 的整批复核、明确确认和原任务交接均通过。RO-4 原有共用操作区、原位续作焦点及四类恢复
沿用 Task 59.2 PASS，见 `171b3de6:TASK.md`。Task 59.3 保留原 Base，验收 A 在 `a14edf20` 批准的
状态区与在 `45d89ce3` 批准的文件整行展开。当前待修任务在「操作记录」读到终态时的文件分页更新。
[Slice 验收](SLICE.md#acceptance-criteria)

## 目标与真实入口

用户从任务中心打开原任务，能读到当前阶段、接下来可做什么、后台进度在计什么，以及文件已经
产生的效果。通过现有「继续整理」核对和明确确认原方案，回到同一任务查看实际结果。异常时，
在状态区和对应文件证据可读到原因、影响及下一步。用户点按文件行即可在该行下方阅读详情或收起，
也可切到另一行核对兄弟文件，原文件的恢复操作继续由详情内控件触发。

B 用 Files 留下 `Two.2002.mkv` 的未确认方案并打开原任务。读回为待确认一项、文件结果零项，
`progress.kind=organize` 且 `processed=1/1`，当前页面仍显示「已处理 1 / 1 个主条目」。
明确确认并由 Worker 完成后，同一任务才产生一份文件结果。此时页面同时显示「已完成」
「本次整理已完成」和一行重复说明。真实前后读回及桌面、390 px 截图在本机
`.git/validation-evidence/0a3c619c22b89119a3b5611b163c03090545f737/b-task59.1-review/`。
A 批准的状态区预览 SHA-256 为 `f7bf7d04beffdb7f4b2b548f5a65f126288a43a753bb9f889135bc79640e8f7d`。
[合同](SLICE.md#ro-4--任务详情正文易读保留原入口与同任务恢复)

B 在 `45d89ce3` 从任务中心列表打开已有真实多条目任务。点 `Arrival.2016.2160p.mkv` 文件名时
证据保持收起，点行末「查看证据」后才展开。再用 `Blade.Runner.1982.1080p.mkv` 的按钮，会将唯一
证据区移到该文件。现有精确关联与单项展开可直接复用。实页截图和日志在本机
`.git/validation-evidence/45d89ce3e97618804e8c62b500b93df3ff6e82d2/b-task59.3-planning/`。
整行展开预览 SHA-256 为 `2893e5295dde995792138e22e5215bc9f478a2045e78fd19a7cb1ae7aa88109c`，
桌面与 390 px 对照在本机 `.git/validation-evidence/slice59-task-full-row-preview/`。

## 范围与 Developer 开发指导

1. 收拢 `OperationsLanding.tsx` 中的 `runStatusHeadline` 和 `RunFlowSummary`。进度上方用
   一个标题表达实际状态或阶段。正常完成用「流程已完成」，直接接进度和文件结果。混合结果、
   恢复成功、失败、取消、效果待核对和缺失结果仍呈现各自结论、具体原因与适用入口。
2. Files 未生成方案时使用现有 `linkedDiscoveryQuery` 的真实阶段。排队、准备、分析和确认后的执行
   排队各显示实际状态。准备读回产生新阶段或新方案时，联动现有状态刷新更新同一关联读。
   「等待确认」从同一任务的当前读回取得范围，提示与共用「继续整理」的实际资格一致。
   `progress.dispositions.waiting` 还包含等待识别、元数据和分类，`filesPreparation.continuable`
   表示可打开原卡。遇到混合任务时，从现有问题读回及确切关联的准备和当前方案取得可确认范围。
   复用原准备／方案查询与既有确认资格。历史或当前不能确认的方案保留实际原因和下一步。
   只有合计或读取暂不可用时，说明能核实的等待状态和
   当前合法动作。已执行的兄弟文件继续报告自己的结果。
3. 在 `RunDetailTabs.tsx` 的 `ProgressCard` 按实际阶段说明进度。现有 `processed` 会计入已进入
   等待的条目，`kind=organize` 也会出现在等待确认阶段。准备或分析已满时在可见文字和进度条
   的可访问名称中标明实际口径。混合任务分别说明已执行结果和仍待确认范围，执行阶段继续使用
   后端真实进度，证据缺失时保留未知说明。独立文件结果继续采用既有正式结果及
   效果确定性。范围限 Web 详情正文，沿用持久状态、API、动作权限、顶栏操作、页签、原位续作和记录。
   等待确认的提示只说明当前范围。准备、识别或元数据失败沿用该层的可见原因和文件证据。文件曾有
   执行时，沿用现有正式结果区呈现已验证成功、部分成功、文件失败或效果未知。进度处需要补充既有
   结果时使用真实结果可证的结论，`failed_partial` 等流程处置计数不作执行文件数。
   [状态区](web/src/features/operations/OperationsLanding.tsx#L1883) ·
   [进度与文件结果](web/src/features/operations/RunDetailTabs.tsx#L952)
4. 在 `RunItemsSection` 将文件图标、文件名、简述和文件状态合成覆盖整行的原生按钮，行末只保留
   状态。沿用 `data-evidence-item`、`aria-expanded` 与实际展开区的 `aria-controls`，按文件名称
   提供可辨识的按钮名称。复用原 `evidenceItem` 和 `onInspectItem`，再次点同一行清除所选，换行时
   选中准确 `itemId`。补整行悬停、展开态及可见键盘焦点，Enter、空格和触屏走同一个入口。
5. `RunEvidenceSection` 随选中项就地呈现，位于行按钮之后。各项诊断、重新读取、决定、分析和确认
   由展开区内部的原独立控件触发。当前行可见时通过行收起，筛选或分页导致证据独立显示时仍提供
   关闭入口。复用原 `run + item` 读取、草稿和 `inspectItem` 的焦点归还，关闭后回到原触发控件、
   同文件行或「任务详情」页签。原问题文件定位和操作记录入口继续打开准确条目，保留服务器筛选、
   分页、加载或读取失败时的独立证据及回迁；状态轮询继续保持当前焦点和滚动位置。
   [文件行](web/src/features/operations/RunDetailTabs.tsx#L1209) ·
   [证据焦点](web/src/features/operations/RunDetailTabs.tsx#L833) ·
   [问题文件入口](web/src/features/operations/OperationsLanding.tsx#L706)
6. 由两页签共用的 `RunDetailTabs` 或详情容器处理同一任务的终态。复用精确分页查询键。
   文件页可见时保留本轮取消旧请求、发出新请求的行为；在「操作记录」读到终态时标记原文件分页
   已过期，切回「任务详情」读取该页的真实终态。保持当前任务、服务器筛选、页码、展开项、焦点和
   滚动。读取失败沿用已有说明和「刷新」。

## 验收与测试

- [ ] 从 Files 发起准备并关闭弹窗，在 Worker 运行之前从任务列表打开原任务。核对标题明确为
  等待准备或实际准备阶段，执行提交和正式结果为零。保留详情等待 Worker 发布方案，核对同一
  详情按当前读回从准备过渡，按适用权限提供核对入口。用两项先确认一项的原任务核对剩余范围，
  确认后已有结果和待确认进度各自清楚。
- [ ] 复用 `ProviderFailure` 中两部影片的真实用例。在明确确认之前到原任务详情，核对一项元数据
  分析失败、一项待确认，页面显示相应阶段和待确认数，执行提交与正式结果为零。再用两次确认用例
  核对一项已执行和一项仍待确认并存时，既有结果仍可按原文件读回。
- [ ] 从现有复制用例确认 `DialogConflict.2022.mkv` 后留在自动打开的详情，允许页面先读到待处理行。
  Worker 完成且详情读到终态后，同一文件行自动更新为「已验证成功」，对应证据可展开。
  复验首次分页真实响应迟到时仍会发出新的终态分页请求。在同一复制用例中再走一遍切页签路径，
  先看到待处理行，转到「操作记录」等导出可用，再切回「任务详情」，文件行自动显示验证结果。
  核对原筛选及展开条目，证明这些步骤只读取同一任务。
- [ ] 从实际 Files 留下已分析但未执行的方案，从任务中心打开同一任务。桌面和 390 px 核对单一
  「等待确认」、准确范围、合法下一步和进度口径。沿原按钮继续并明确确认，读回同一任务。
  正常完成只显示一个「流程已完成」，紧接相应进度和正式结果。
- [ ] 从现有入口核对纯等待确认、部分已执行且仍待确认或待决定、只有业务问题、分析进行中、混合
  文件结果、任务失败、协作取消／核对、效果不明和读取失败等适用状态。核对原因、已知效果与原有
  文件证据入口；「操作记录」往返、续作关闭及原焦点仍可达。
- [ ] 从同一任务列表入口打开至少两个有独立证据的文件。在桌面用鼠标点文件名和行内状态位置，390 px
  用触控点整行。验证每行一个 Tab 停靠、行末只显示状态、键盘焦点清晰、Enter 和空格可切换展开态，
  点同一行可收起。换行时只展开新文件并读回其详情，详情紧跟该行。检查长文件名换行和可点击区域。
- [ ] 从现有问题文件入口打开证据，录入决定草稿，筛选隐藏或跨页时同文件证据移至列表前，恢复匹配
  后回到对应行，草稿与原筛选分页保持。核对从行或独立证据关闭的焦点。实走合法的保存、分析、
  同页摘要和确认，内部操作对应同一个文件、详情保持展开。已结束文件仍可查证据与历史。
- [ ] Developer 在 `web/` 运行类型、构建、改动文件 ESLint／Prettier 和下列受影响测试。更新
  旧流程失败短标签及 Files 概览入口等定位，按真实文件名找到行按钮。B 审查完整 Task 和 Slice，按 T3 从真实
  入口对照两个批准预览，核对确认前后、异常结果、两行切换、证据回迁和原生恢复，再补齐适用的
  Slice 最终门禁。各轮测试墙钟低于本轮用时一半。

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- tests/e2e/manual-organize.spec.ts --grep 'a terminal failed Task states its durable failure'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/task-flow.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'initial manual preparation remains reachable in place|second confirmation on the same Task|a metadata provider technical failure|the selected run detail reads progress|21-file recovery pages preserve|native Metadata correction|a mixed file population completes|a saved flow failure stays authoritative|an acknowledged cancellation|real destination conflict is decided|101-file directory'
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)
