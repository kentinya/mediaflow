# Task 59.1 — Files 手动整理流程

Next Action: DEVELOPER CORRECTS FILES CONFIRMABLE COUNTS AND UPDATES THE AFFECTED BROWSER CHECKS

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: 44f95aef9ebd4fc7754b248d225403825e281f30
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

## 目标、范围与开发指导

从 Files 批量整理两个就绪文件。逐项暂不纳入其中一个，回概览能读到「已选 / 可确认」为
`1 / 2`，进入整批只复核并提交选中的一项，之后可从原任务继续余下文件。A 在 `33cbe4ae`
明确了概览两项计数及整批正文的验收要求。继续原 Task 59.1 修正，原计划与上轮指导保存在
`7d5b2565:TASK.md` 和 `674a0660:TASK.md`。Task Center 运行详情自身的视觉验收仍由原 Task 59.2 接续。
[Slice AC-06](SLICE.md#acceptance-criteria)

1. 在 Files 概览复用已有就绪分组和实际方案资格。分子计已选文件，分母计当前可纳入确认的就绪文件，
   包含暂未勾选的项。把当前方案的整体阻塞与操作者的勾选分别用于计数。`Readability` 方案整批不可确认时
   继续显示 `90 / 0` 与实际原因。概览底部用同一口径，整批清单、确认按钮和提交仍以确切已选范围为准。
   [计数与整批复核](web/src/features/operations/ManualOrganizeDialog.tsx)
2. 更新两个已实跑失败的旧断言。`library-files.spec.ts` 的 Files 整批读取「本次确认」和零媒体变更说明。
   `manual-organize-dialog.python.spec.ts` 的两次确认旅程中，Files 首次读「本次确认」，从原任务继续的
   第二次读原「将整理」。保留两次的数量、精确交接、Worker 实际效果、丢回包核对及无重放断言。
   [Files 浏览器回归](web/tests/e2e/library-files.spec.ts) · [真实两次确认](web/tests/e2e/manual-organize-dialog.python.spec.ts)

## 验收

- [ ] 按真实两次确认用例的 Files 入口操作。两个文件均就绪时，默认 `2 / 2`，取消选中一项后 `1 / 2`，
  整批仍只包含一项。确认后核对兄弟文件留在原处，从原任务点「继续整理」，用原整批正文确认余下文件。
  保留 `Readability` 的 `90 / 0` 以及整批实际拒绝。两套浏览器回归使用各自承载方的正文验证同一功能。
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
npm run test:e2e -- tests/e2e/library-files.spec.ts --grep 'same-page preparation links the summary and confirms one exact subset'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'A59-01|A59-02|AC-02 mixed Files decisions|100-file batch|101-file directory|compact first-plan'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'second confirmation on the same Task'
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

`main` 起始为 `b28c1ddbf98f9eee6de21c74b23bbe307976cdbe`，工作区与暂存区干净，治理通过。
复核完整 Task `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..44f95aef9ebd4fc7754b248d225403825e281f30`
及 Slice `212acdef5d97c14a01353b22c103d44b911d6147..44f95aef9ebd4fc7754b248d225403825e281f30`。
后续 `b28c1ddb` 仅增加 Developer 交接。构建、类型、Lint、格式和 4 个组件测试文件共 178 项通过。
重点原生 7 项通过，包括正常和丢回包的跳过、四类混合决定、方案读取、100／101 项及原任务续作。
Files 和 Task Center 布局套件 63 项通过，1 项因旧 Files 文案断言失败。用对应承载方的现行文案
重跑该用例通过。真实两次确认首轮还命中反向的旧断言，即续作中使用 Files 新标签。核对续作原标签后，
两次实际执行、原任务交接及丢回包核对均通过对应断言。原生 86 秒与 Web 检查 89 秒并行，后续聚焦
测试 16 秒加 8 秒，测试墙钟低于总耗时一半。

- **A59-03（P1，RO-1/3 / AC-06）。** 从 Files 批量整理两个就绪文件，打开第二项取消纳入，再回概览。
  两项都在「就绪文件」，第二项仍标记「可确认」，概览和底部却把总可确认数显示为 1。批准预览同一步显示
  `1 / 2`。`44f95aef` 把分母直接取为已选文件数。实际整批只提交所选项，两个文件各自的效果及原提交核对通过。

RO-1 的准备、分组及 100／101 项通过，普通就绪子集的可确认数待修正。RO-2 的四类决定及跳过丢回包回落
通过。RO-3 的选定范围、单次提交、原任务交接与第二次提交核对通过，概览范围计数需反映实际选择。
RO-4 原位第二层已恢复原逐项和整批正文，详情自身的 AC-06 仍需原 Task 59.2 接续。已核对批准预览校验值，
同状态子集的实页与预览对照及 100 项桌面、390 px 和矮窗截图有记录，Files 修正后继续复核 AC-05/06。

本机运行日志、截图和 trace 位于
`.git/validation-evidence/44f95aef9ebd4fc7754b248d225403825e281f30/b-task59.1-review/`。
已有产品阻塞，完整 T3 门禁在修正候选运行。下节保留 A 退回前的 B 交接记录。

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
