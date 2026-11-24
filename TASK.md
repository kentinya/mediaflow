# Task 59.1 — Files 手动整理流程

Next Action: B REVIEWS CORRECTED FILES READBACK, CONFIRMATION GUIDANCE AND CONTINUATION BODY

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: READY FOR B REVIEW
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: db6a505407e5dc1781e1913be5f0db6b960d3f23
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 CORRECTION SCOPE
```

## Developer 修正交接 — READY FOR B REVIEW

候选：`44f95aef9ebd4fc7754b248d225403825e281f30`（父提交 `33cbe4ae`，Task Base
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf`）。本轮只改 Files 整理弹窗、共享恢复表单接入、
Files 正文样式、隔离夹具和直接受影响测试。

- **A59-01。** Files 弹窗保留的逐条 TaskItem 读回现在驱动回落：正常回包沿用原结果，回包丢失时
  由同一 itemId/TaskItem 的 `skipped/ignored` 读回记录结果；只有操作者仍在原文件、原编辑位置且
  未进入复核时才回概览并聚焦该行，否则只更新对应结果。移除了挂在被替换表单上的无效 effect。
  决定后重新读取同一摘要，概览与整批按实际资格显示。
- **A59-03 确认提示。** 概览与整批复用实际 `confirmationBlocker` 和摘要当前资格，分别显示已选/
  可确认；待处理只计未结束条目，已跳过/忽略单列为已有结果；仅当剩余未结束项为零且原准备广告
  分析动作时提供「重新分析同一准备」，保留已结束原因与合法下一步。
- **正文承载。** Files 按 `33cbe4ae` 使用三栏计数、紧凑就绪行、来源与目标整批行及固定底部动作；
  非 Files 恢复 Slice Base 的「当前文件／来源库／当前方案」和原整批正文。新增样式按 Files 类隔离。

实际验证（`web/`）：`npm run typecheck`、改动文件 `npm exec -- eslint`、`prettier --check`、
`npm run build` 均通过。组件测试 2 个文件 83 项通过。原生 grep 六项 6 passed（54 秒），包括新增的
真实丢回包旅程：保存后拦截并断开发送决定响应，概览仍从同一 TaskItem 读回「已跳过」，兄弟项保留
1 项确认资格；一次决定、零次 continue、媒体不变。Task Center 原位续作 1 项 19 秒通过，断言
「当前文件」「来源库」「当前方案」及 Base 整批正文。`check_governance.py` 与 `git diff --check`
通过。桌面、390 px、矮窗概览与整批截图保存于
`.git/validation-evidence/44f95aef9ebd4fc7754b248d225403825e281f30/developer/`。测试墙钟约 13
分钟，低于本轮总耗时 30%。

剩余风险：剩余项全部已结束、摘要需重新分析的状态由组件用例覆盖后端广告动作；本轮真实冲突跳过后
摘要仍为当前方案，未在真实夹具构造该失效分支，请 B 在 A59-03 复核时补真实验证。100 项截图覆盖
待处理分组与整批；就绪/已有结果分组的完整四屏对照仍需 B 按 AC-06 汇总。

## 目标与范围

用户从资源库 Files 打开「整理所选文件」，读准备进度，在概览找到要处理的文件，保存决定并
核对读回结果，再从整批复核确认合法范围。执行受理后打开准确的任务详情。原计划见
`7d5b256504dfef48e6664af3468c6ad9440f3092:TASK.md`。本轮完成 A59-01 的丢回包回落，
使 A59-03 的概览和整批复核说明真实确认资格，并恢复 Task Center「继续整理」所打开的原弹窗正文。
正常回包后的跳过、A59-02 的作品搜索入口及同批四类决定已有通过证据。
[A 终审及补充结论](SLICE.md#a-final-review--fix-required)

A 在 `848a293e` 和 `f915c2f1` 提交 AC-06，并在 `45f9916a` 补充任务详情的逐屏验收。按已认可离线预览对齐布局、分组、阅读顺序和
主操作位置，使用实际状态和合法动作。此 Task 负责原 Files 承载的正文。Task Center 的详情正文
属于原 Task 59.2，原功能验收仍有效，AC-06 的该项待原范围接续。当前先在原 Task 59.1 复核
Files 行为与视觉，Slice 级验收覆盖两处正文及同一任务的完整交接。
[AC-06 与预览校验值](SLICE.md#acceptance-criteria)

## 开发指导

1. **让持久结果完成回落。** 丢回包后，Files 弹窗查询已经读到原 TaskItem 的 `skipped`，并以结果
   正文替换原决定表单。当前补丁把回落放到了被替换的表单的 effect，实际未执行。让保留在该弹窗
   的现有确切条目读取驱动回落，沿用决定发起时的准备、文件、位置和编辑身份。原位置仍有效时回
   概览并聚焦该文件。已翻页或进入复核时只更新对应结果。保留正常回包的计数、未纳入说明和兄弟选择。
   [Files 弹窗](web/src/features/operations/ManualOrganizeDialog.tsx) · [恢复表单](web/src/features/operations/TaskItemRecoveryPanel.tsx)
2. **让状态卡说明实际确认资格。** `Readability` 有 90 个就绪文件、10 个需要作品搜索修正，当前
   整批受方案有效性限制。概览和整批复用现有执行资格及阻塞原因，分别显示已选范围和此刻可确认范围，
   说明从哪个原文件或原准备继续。跳过后摘要若仍需更新，复核保留已跳过原因，并按实际方案状态给出
   合法下一步。后端明确允许的当前就绪子集仍可单次确认。
3. **隔离 Files 正文布局。** 「继续整理」仍打开同一准备的原有逐项正文。把文件头、范围事实、
   方案段和整批行的新增布局及样式限定在 Files 承载。对照 `fc4369d5` 和 Slice Base 恢复
   Task Center 原位承载的「当前文件」、来源库信息和「当前方案」以及原整批正文。保留原位回落、
   草稿、历史只读和精确确认。保留 Files 本次已呈现的状态卡、分组、固定保存及附件计数。
   [承载边界与 AC-06](SLICE.md#acceptance-criteria)

实施落点为 Files 弹窗、必要的共享表单接入以及限定于 Files 正文的样式与回归。原入口、外框、标题、
Task Center 的承载和业务逻辑、API、Worker、Storage 及授权边界以 Slice 合同为准。复用现有原生用例、
隔离数据和离线预览，沿正常入口验证。

## 验收

- [ ] 从真实冲突和就绪兄弟同批打开，保存合法跳过后回概览。概览正文与底部对待处理的口径一致，
  原文件行与整批未纳入区说明已跳过及零媒体变更，原文件可再次查看。复用同一入口分别验证正常
  回包和后端已保存但回包丢失。核对读回原 TaskItem、一次决定写入、兄弟项选择和临时媒体效果。
  延迟回包期间换到兄弟继续编辑或整批复核，原读回更新对应条目、保持当前正文和焦点。
- [ ] 在现有入口走「准备／读取方案 → 分组概览 → 逐项决定 → 整批复核」。按合同做桌面、390 px
  和矮窗的同状态预览对照。覆盖可读的真实等待与拒绝、状态卡及事实行、三组文件、固定区的合法
  主操作、精确可读的来源目标及附件。核对键盘、焦点和一个正文滚动区。记录为保留真实状态、
  合法动作或安全约束而与预览不同的具体状态。
- [ ] 选择 `Readability` 文件夹，比较概览状态卡、整批复核按钮和实际后端给出的同一计划资格。
  操作者在概览便能读到需要完成的修正以及暂时无法确认的事实。跳过后的原文件仍读为已处理，
  兄弟项保留原选择；合法子集在后端许可后用一次明确确认提交。
- [ ] 重跑 100 项 `Readability` 的作品搜索入口和第 101 项整批停止。重跑同一 Files 批次四类决定，
  包括候选确认与作品搜索修正。确认前只改变决定，最后只确认一次合法范围。用准确任务详情核对
  真实文件／附件和原请求回包丢失。从任务列表打开原任务并点击「继续整理」，核对第二层原逐项及
  整批正文，关闭后回到原详情。Task Center 详情自身的视觉对照列入原 Task 59.2 和 Slice 级复核。

## 测试与交接

**Developer** 在 `web/` 运行 `npm run typecheck`，对实际改动文件运行 `npm exec -- eslint` 和
`npm exec -- prettier --check`。运行 `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx`，
以及下列原生入口回归。把同一文件各处原因、确切读回和布局主操作的断言补入现有用例。根目录运行
`git diff --check`。提交候选 SHA、实跑结果与仍需核对的状态。

```sh
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'A59-01|A59-02|AC-02 mixed Files decisions|100-file batch|101-file directory|compact first-plan'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place'
```

**B** 独立看完整 Task 与 Slice Base..Head，先复验原阻塞和四屏对照。按 T3 在新候选运行 Web 类型、
Lint、格式、构建和直接相关的组件测试，以及下列集成验证。复用已认可预览、既有 Files 用例和
原位续作入口，对真实 API、SQLite、Worker 和临时媒体核对效果。两处正文均达到 AC-06 后进入
Slice 最终门禁。各轮测试墙钟低于本轮总耗时的一半。

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place|detail tab and filter context|recovery'
npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/task-center-layout.spec.ts
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)

## B 本轮复核 — FIX REQUIRED

`main` 起始为 `45f9916acba2f32e146e77b4f9e902d943f79a2d`，工作区与暂存区干净，治理通过。
复核完整 Task `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..db6a505407e5dc1781e1913be5f0db6b960d3f23`
及 Slice `212acdef5d97c14a01353b22c103d44b911d6147..db6a505407e5dc1781e1913be5f0db6b960d3f23`。
后续 `45f9916a` 只补充合同证据要求。构建、类型、Lint、格式和 4 个组件测试文件共 177 项通过。
既有重点原生 5 项通过，正常跳过的补充原生旅程也通过。原生 47、32 和 34 秒，Web 检查并行 66 秒。
首组原生与 Web 检查重叠，测试墙钟低于本轮总耗时的一半。补充首轮的文案匹配与定位错误已在
后续运行更正，原始日志保留。

- **A59-01（P1，RO-2 / AC-02）。** 从 Files 跳过实际目标冲突，实际保存完成后让浏览器回包断开。
  原 TaskItem 及逐项正文均显示「已跳过」，当前文件仍留在逐项页。正常回包已回概览，正文和底部
  都显示需要处理 0 项，原文件在整批复核中明确为已跳过，原来源与目标保持原状。
- **A59-03 确认提示（P1，RO-1–3 / AC-06）。** 在 Files 批量整理 `Readability`，概览提示可直接
  确认已就绪项，进入整批却无法确认 90 项。实际方案仍需处理 10 项问题。跳过冲突后的复核还可能
  要求处理已经结束的条目。按步骤 2 用实际摘要资格和原条目结果给出下一步。
- **Task Center 原位承载边界（P1，RO-4 / AC-04）。** 从 Files 准备 `Two.2002.mkv` 后关闭，
  从任务列表点原任务，再点「继续整理」。正确打开原准备，正文却使用 Files 新文件头和方案段，
  原「来源库」事实被存储路径替代。共享正文和样式改动超出了该入口的合同范围。

RO-1 的具体准备状态、来源／范围／进度三行、概览分组及 100／101 项已有证据，确认提示待修正。
RO-2 的四类决定与正常跳过通过，丢回包回落待修正。RO-3 混合任务确认四项后精确交接通过，
暂不能确认的阅读和下一步待修正。RO-4 的任务详情功能证据保留，第二层原位承载需恢复，详情
正文的 AC-06 仍需原 Task 59.2 接续。Files 四屏已对照批准预览的桌面、390 px 和矮窗截图，
准备状态卡、分组、固定保存及附件计数已呈现。示例预览的就绪范围可以确认，隔离应用中失效的
摘要仍须按当前权威阻止执行。AC-05 的焦点及相关失败恢复随修正重验。

本机原生运行日志、截图及失败 trace 位于
`.git/validation-evidence/db6a505407e5dc1781e1913be5f0db6b960d3f23/b-task59.1-review/`。
已有产品阻塞，完整 T3 门禁在修正候选上运行。下节保留 A 退回前的 B 交接记录。

## B 复核与 Slice 59 交接

```text
Slice: 59 — 手动整理流程与任务详情弹窗正文
Task Reviewed: 868ff9daab6972473cfb7344ca02cbdbc30077cf..27a430b7098a75f4fd040bc1109c678808629b1a
Slice Base: 212acdef5d97c14a01353b22c103d44b911d6147
Implementation Head: 27a430b7098a75f4fd040bc1109c678808629b1a
Tasks completed: 59.1, 59.2
Required Outcomes and Surfaces: COMPLETE
Decision: SLICE READY FOR A REVIEW
```

Developer 实现为 `85e689cf221b8d4372e81db14f0176369ae24d54`。交接 `426c6cc` 只改
`TASK.md`，含 Task 59.1 验收链接、Task 59.2 修正及上轮 B 阻塞。B 独立复核完整差异，
并在 `27a430b7` 让 OpenList 原用例从现行概览点击「查看文件」，再执行原有断言。
正式构建和运行输入与 Developer 候选相同。

### 合同结果

- **AC-01 / RO-1。** Files 的先受理、准备进度、读失败后的重读和同弹窗概览已有 Task 59.1
  的隔离验收。最终候选复跑 100 项复核和第 101 项整批停止，检查窄窗的精确路径、未纳入
  文件与原因。原 Files 入口、标题、背景和回落随布局组核对。
- **AC-02 / RO-2。** 最终候选从 Files 对 10 个候选分别保存并重新分析，每个条目读回后返回
  概览，最后一次确认准确交接原 Task。另验证元数据服务技术失败与就绪兄弟的独立处置。
  Files 的拒绝、迟到读回、分类后续问题、草稿及焦点由组件和 Task 59.1 入口回归覆盖。
  四类处理在原生任务中心逐类型走到同任务的新摘要及执行，其中混合任务验证独立兄弟；
  原生证据按这些旅程组合，未将四类集中到单个 Files 夹具运行。
- **AC-03 / RO-3。** 复跑兄弟项重分析后核对原提交，确认响应丢失仍指向精确 Task 且只提交
  一次。真实复制后目标存在、源文件保留；冲突重命名时原目标保留。有明确许可的覆盖经同页
  确认；组件验证方案更新时重新核对授权，及原请求保留文件子集和效果选项。OpenList 隔离
  旅程证明确认前零媒体变更，确认后恰有两次移动和两次重命名，两份结果均已验证。
- **AC-04 / RO-4。** 从 Files 交接、列表、深链和四类问题入口打开原任务。运行详情按流程、
  进度、动作、文件结果和证据阅读。原位「继续整理」关联准确，关卡返回原任务及焦点；
  同任务证据随筛选/跨页迁移，保留原草稿。重认证、两页签、记录筛选、读取失败重读和有界
  JSON 导出均有验收证据。
- **AC-05 / RO-1–4。** 复制成功后行内显示「已验证成功」，跳过项保持自己的结果，常规重放
  限制在诊断里。历史未确认效果在文件行、汇总和证据中可区分。元数据候选行和证据均指明
  要确认候选，各类型沿用原恢复。组件和原生任务覆盖主文件已完成但附件失败、混合结果、
  无正式 Result、技术失败、流程失败及协作取消。检查了桌面、390 px 和矮窗截图，回归
  覆盖长路径、键盘、焦点、reduced-motion、原列表和弹窗层级。

### 门禁、证据与交接

- 最终源码经 Web 类型、Lint、格式、构建及五个相关单测文件 174 项通过。布局与 Files
  64 项、原生 24 项、OpenList 1 项通过。实跑命令、截图、制品摘要和失败 trace 保存在
  `.git/validation-evidence/426c6cc67ec4732192c3a7293d85d066519339a6/task59.2/`。
  Task 59.1 另有原生 Files 21 项、原位续作 2 项通过的原始日志及截图。
- OpenList 旧用例等待直接进入单文件页，原失败已留档。它现可从概览进入该页，格式、
  Lint 及专用浏览器用例通过。其他门禁在前一提交的相同产品代码与各自原测试输入上通过。
  测试和质量检查按并行墙钟合计约 3 分钟，低于本轮复核用时的一半。治理和完整差异检查通过。
- 使用本地隔离 Provider、SQLite、Worker 和临时媒体根。按合同保持 T3，生产部署、全量
  发布矩阵、引擎与配置边界沿用 Slice 范围。A 终审通过后同步 V2 要求、用户旅程、任务中心
  当前正文、架构说明和接受账本。
