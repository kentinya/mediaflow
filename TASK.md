# Task 59.1 — Files 手动整理流程

Next Action: DEVELOPER COMPLETES A59-01 AND ALIGNS THE FILES BODY WITH AC-06

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: fc4369d5b98d0915b03647919d11a9acab9a0759
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 CORRECTION SCOPE
```

## 目标与范围

用户从资源库 Files 打开「整理所选文件」，读准备进度，在概览找到要处理的文件，保存决定并
核对读回结果，再从整批复核确认合法范围。执行受理后打开准确的任务详情。原计划见
`7d5b256504dfef48e6664af3468c6ad9440f3092:TASK.md`。本轮处理 A59-01 的剩余问题和
A59-03 在 Files 的四屏正文。A59-02 已通过验收，混合批次的四类决定已有原生证据。
[A 终审及补充结论](SLICE.md#a-final-review--fix-required)

A 在 `848a293e` 和 `f915c2f1` 提交 AC-06。按已认可离线预览对齐布局、分组、阅读顺序和
主操作位置，使用实际状态和合法动作。此 Task 负责原 Files 承载的正文。Task Center 的详情正文
属于原 Task 59.2，原功能验收仍有效，AC-06 的该项待原范围接续。当前先在原 Task 59.1 复核
Files 行为与视觉，Slice 级验收覆盖两处正文及同一任务的完整交接。
[AC-06 与预览校验值](SLICE.md#acceptance-criteria)

## 开发指导

1. **让同一条目的结果贯穿概览和复核。** 在 `ManualOrganizeDialog` 里复用候选已取得的确切
   TaskItem 结果，给概览行、正文和底部计数、逐项状态、以及整批未纳入原因使用同一结果。
   已跳过的文件显示「已跳过」及来源保留，替换旧方案的「移动／来源不保留」和「文件已失效」。
   兄弟项的草稿、选中范围与后端确认资格各自保留。真正失效的摘要继续给出其实际限制。
2. **让丢回包后的确切读回也能完成回落。** `TaskItemRecoveryPanel` 保存成功时的回落目前来自
   POST 的返回，而保存回包丢失后现有恢复查询已能读到终结状态。沿用发起动作时捕获的 TaskItem
   与位置，将该次同条目的持久结果接到同一回落。发起页仍是原文件且没有新编辑时回概览并聚焦
   该文件行。切到兄弟项或整批复核时只更新原结果。继续按现行条件显示拒绝、待核对和确已排队的分析。
   [Files 弹窗](web/src/features/operations/ManualOrganizeDialog.tsx) · [恢复表单](web/src/features/operations/TaskItemRecoveryPanel.tsx)
3. **按预览调整准备与概览。** 共用同一状态区样式，用正在读取方案、等待稳定等实际阶段做标题，并给
   出对应下一步。其下按行显示来源、范围、准备进度，未知数量显示实际状态。概览先给「已选／可确认」、
   「需要处理」、「已有记录」计数，再按待处理、就绪、已有结果分组。文件行优先显示文件名、状态和
   下一步，精确路径和方案标识按需展开。保持单正文滚动和从概览进入同一文件的焦点回落。
4. **按预览调整逐项与整批。** 逐项正文优先显示当前文件和当前决定或结果。将当前合法的
   「保存并重新分析」放到 Files 的固定操作区，复用原表单的提交、校验、等待与分析补做，保持
   键盘操作、焦点及原草稿。方案尚未生成时简明说明，生成后可读真实来源、目标、操作、附件和
   纳入资格。整批复核从实际确认状态和范围摘要开始，先读已纳入、未纳入和附件数，再核对每项
   来源、目标和源文件实际影响。沿用最后的显式确认、危险效果选项和原请求核对。
   [A 的五屏对照](SLICE.md#a-final-review--fix-required)

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
- [ ] 重跑 100 项 `Readability` 的作品搜索入口和第 101 项整批停止。重跑同一 Files 批次四类决定，
  包括候选确认与作品搜索修正。确认前只改变决定，最后只确认一次合法范围。用准确任务详情核对
  真实文件／附件、原请求回包丢失和原位继续整理。Task Center 的正文视觉对照列入 Slice 级复核。

## 测试与交接

**Developer** 在 `web/` 运行 `npm run typecheck`，对实际改动文件运行 `npm exec -- eslint` 和
`npm exec -- prettier --check`。运行 `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx`，
以及下列原生入口回归。把同一文件各处原因、确切读回和布局主操作的断言补入现有用例。根目录运行
`git diff --check`。提交候选 SHA、实跑结果与仍需核对的状态。

```sh
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'A59-01|A59-02|AC-02 mixed Files decisions|100-file batch|101-file directory|compact first-plan'
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

`main` 起始为 `fc4369d5b98d0915b03647919d11a9acab9a0759`，工作区与暂存区干净，治理通过。
复核完整 Task `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..fc4369d5b98d0915b03647919d11a9acab9a0759`
及 Slice `212acdef5d97c14a01353b22c103d44b911d6147..fc4369d5b98d0915b03647919d11a9acab9a0759`。
构建、类型、Lint、格式和 4 个组件测试文件共 175 项通过。候选自带的 3 个原生用例通过，
包括真实冲突正常回包、100 项作品搜索及同一 Files 批次四类决定后确认四项。两条补充原生旅程失败。
原生两组分别耗时 35 秒和 25 秒，Web 检查并行耗时 60 秒。首组原生与 Web 检查重叠，本轮
测试墙钟低于总耗时的一半。

- **A59-01（P1）。** 跳过已保存后回概览，正文显示待处理 0 项，底部仍显示 1 项。
  进入「整批复核」并展开未纳入项，同一文件显示已失效。概览行还展示旧方案的「移动／来源不保留」。
  另从同一冲突入口保存，后端写入跳过后模拟回包断开。原文件正文读到「此文件已跳过」，
  弹窗继续停在逐项复核。底部和整批原因仍直接读方案，回落只收到成功响应回调。
- **A59-03（P1）。** 当前候选概览仍平铺文件并露出方案标识和路径，窄窗的整批复核仍沿旧阅读层级。
  对照已认可预览和 A 的真实截图，再查当前代码，准备阶段仍用通用标题，逐项保存仍在正文，
  任务详情的流程与进度仍分区，处置列表仍用宽表格。Files 的四屏按上方指导调整，任务详情项
  保留在原 59.2 边界。已核对预览 SHA-256 与合同一致。

RO-1 的原入口、容量边界及作品搜索可达，准备与概览的预览对照仍待完成。RO-2 的四类决定
已有原生验证，A59-01 的待处理计数、未纳入原因及丢回包回落需修正。RO-3 的精确子集和单次
确认在混合批次通过，整批视觉与跳过原因待修正。RO-4 的原功能验收沿用早期 B 记录，当前 A59-03
的详情正文尚未达到 AC-06。AC-05 中 Files 的焦点与窄窗随修正重新验收。

本机原生运行日志、截图及失败 trace 位于
`.git/validation-evidence/fc4369d5b98d0915b03647919d11a9acab9a0759/b-task59.1-review/`。
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
