# Task 59.1 — Files 手动整理流程

Next Action: DEVELOPER IMPLEMENTS THE A59-01 AND A59-02 CORRECTION

```text
Task ID: 59.1
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: 3bc9ad99137e5a2f8ff53add92041185ceb8ebbf
Reviewed Implementation Head: 27a430b7098a75f4fd040bc1109c678808629b1a
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.1 CORRECTION SCOPE
```

## 目标与范围

从资源库 Files 选择文件或文件夹，打开「整理所选文件」。在概览里直接读懂每个待处理文件需要什么决定，
打开原文件完成处置，再回同一概览看见实际结果并继续兄弟项。符合后端执行条件的范围仍从整批复核明确确认，
执行受理后打开原任务详情。修正限于原 Task 59.1 的 Files 概览与决定回落，涵盖 A59-01、A59-02 和
AC-02 已要求的四类混合旅程。Task 59.2 的 B PASS 保持有效。
[Slice 59 合同及 A 终审](SLICE.md#a-final-review--fix-required) · [原 Task 59.1 计划及交接](https://github.com/kentinya/mediaflow/blob/868ff9daab6972473cfb7344ca02cbdbc30077cf/TASK.md)

## 开发指导

1. **用原条目结果完成回落。** `TaskItemRecoveryPanel` 的「保存并重新分析」已经读取决定响应并写入原
   TaskItem 的查询缓存。真实冲突跳过在此处返回 `skipped`，因此自然走无后续分析的分支。让 Files
   承载方在发起决定时记住原准备、原文件和编辑位置，接收这一决定的原条目结果。用读回的
   `skipped` 完成该项的跳过流程。原有忽略动作返回受理回执，按同一条目的现有恢复读取确认已忽略。
   原位失败保留输入。响应不明确时继续用已有的原条目核对入口，按读回事实显示结果，再决定可用动作。
   [共享决定表单](web/src/features/operations/TaskItemRecoveryPanel.tsx) · [原条目恢复查询](web/src/features/operations/run-detail-query.ts)
2. **先更新结果，再按当前位置决定是否回概览。** 用 `ManualOrganizeDialog` 现有的条目关联、回落和焦点逻辑。
   原文件仍在当前逐项页且没有新编辑时，回概览并指出该文件「已跳过」或「已忽略」。同一条记录的行、
   计数和再次查看使用确切结果，包含刷新或重开同一准备后的读取。用户已经翻页、编辑其他文件或进入
   整批复核时，更新原条目并保持当前位置、兄弟草稿和选择。真正排入分析的决定仍等原文件自己的方案读回。
   [Files 弹窗](web/src/features/operations/ManualOrganizeDialog.tsx)
3. **按当前可处理事实解释概览行。** `overviewPendingReason` 目前先检查条目是否能用于当前方案，因而把
   `Readability` 里仍可纠正的作品搜索描述为已离开方案。在活动准备的概览里，通过原任务和条目的确切关联
   复用逐项页已有的问题类型、技术失败事实和可用动作。让待处理标签及其下一步和打开该文件后看到的内容
   一致。真正被更新取代的摘要及失效文件继续说明其状态。实际确认资格仍来自后端方案和执行动作。
   [Files 概览和逐项入口](web/src/features/operations/ManualOrganizeDialog.tsx)

实现落点为 Files 弹窗、所需的共享表单结果传递和直接回归。沿用 Task Center 的现有承载、读回及恢复，
原 API、Worker、Storage、数据库、权限、确认选项和提交身份继续提供权威。

## 验收

- [ ] **A59-01。** 在原 `Dialog` 原生旅程中，先确认一次复制以留下真实目标，再从 Files 选中冲突文件和
  兄弟项。对冲突文件选择「跳过此条目」并保存。原任务记录显示已跳过，弹窗回到概览，对应行显示结果、
  退出待处理且不进入执行清单。再次打开同一文件或刷新同一准备仍能读到该结果。核对只有一次决定提交，
  源文件、原目标和未提交兄弟项的媒体状态与保存前一致。遇到合法忽略时用原条目读回核对结果。
- [ ] **位置与选择。** 用已有测试在同一决定请求发出后延迟返回，转到兄弟项编辑或进入整批复核。读回后
  原文件结果更新，当前浏览位置、键盘焦点、兄弟草稿及已选范围保持。整批确认继续遵循后端资格。
  保存被拒绝或结果待核对时，在原文件提供实际原因和现有下一步；被受理的分析继续等原方案。
- [ ] **A59-02。** 从 Files 勾选 `Readability` 文件夹并批量整理，在概览找到 `Unmatched001.2011.mkv`。
  该行指向作品搜索修正，点开即进入原任务、原文件的「修正作品搜索」。来回查看只浏览。对照技术失败、
  已被更新取代的摘要及 100 项夹具的原确认状态，分别看见真实原因和相应动作。
- [ ] **AC-02 混合旅程。** 一次 Files 批量整理中走完识别、元数据候选确认及作品搜索修正、分类和冲突的合法决定。
  按各自读回核对概览和兄弟项，记录确认前媒体根零变更，再明确确认一次合法就绪范围，核对同一 Task
  及实际文件、附件效果。原十项候选单次确认、原请求回包丢失与 Task Center 原位续作回归仍通过。

## 测试与交接

**Developer** 在 `web/` 运行下列检查，单测覆盖保存失败、原条目读回、迟到响应和真正失效的摘要。
如涉及其他 Web 文件，同样纳入 Lint 和格式检查。

```sh
npm run typecheck
npm exec -- eslint src/features/operations/ManualOrganizeDialog.tsx src/features/operations/TaskItemRecoveryPanel.tsx tests/e2e/manual-organize-dialog.python.spec.ts
npm exec -- prettier --check src/features/operations/ManualOrganizeDialog.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx tests/e2e/manual-organize-dialog.python.spec.ts
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'A59-01|A59-02|AC-02 mixed Files decisions|100-file batch'
```

复用原 `Dialog` 冲突、`Readability` 100 项和现有原生辅助函数。把 A59-02 断言并入 100 项用例，
保持原精确复核断言。混合批次沿用隔离 harness 的临时媒体、固定配置和本地 Provider；如缺分类样本，
在测试配置中给该样本绑定一条可手选但自动条件不命中的规则，由真实 Files 准备和分析生成问题。提供候选 SHA、
实际命令、结果和已知限制，交 `READY FOR B REVIEW`。根目录运行 `git diff --check`。

**B** 独立复核完整 Task Base 到新候选及 Slice 的完整范围。先复跑上述原生旅程，随后按 T3 执行 Web
类型检查、Lint、格式、构建和直接相关组件回归。在 `web/` 对新候选运行：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable in place|detail tab and filter context|recovery'
npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/task-center-layout.spec.ts
```

检查桌面和 390 px 的回落、键盘焦点及同任务续作。对应输入相同的验收按工作流复用，受影响原生证据在新候选上取得。
各轮测试执行墙钟低于该轮总耗时的一半，保留实跑结果和用时。
[开发与验收分工](docs/development-workflow.md#6-test-levels)

## B 本轮复核 — FIX REQUIRED

`main` 起始为 `3c2e00c94f4198ae77ec69b81cc334c6cbdd2ffd`，工作区和暂存区干净。工作区和 Git
可写，治理通过。审查 Task 的 `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..27a430b7098a75f4fd040bc1109c678808629b1a`
及 Slice 的 `212acdef5d97c14a01353b22c103d44b911d6147..27a430b7098a75f4fd040bc1109c678808629b1a`。
候选到 `main` 起始点只有文档差异。Web 构建通过。原生 Playwright 从 Files 复跑 A 的两个已有操作旅程，
两项均命中原阻塞，浏览器运行 29 秒。跳过后从原条目读回已跳过，弹窗仍留在旧冲突页。100 项准备中的
同一文件可进入作品搜索修正，概览仍显示该文件已离开方案。原始命令、源文件、日志和 trace 在本机
`.git/validation-evidence/27a430b7098a75f4fd040bc1109c678808629b1a/b-task59.1-correction-plan/`。

- **RO-1 / AC-01。** 原入口、首屏、100 项读取和第 101 项停止有通过证据。概览待处理原因受 A59-02 阻塞。
- **RO-2 / AC-02。** 原十项逐项处理、分析读回及技术失败有通过证据。A59-01、A59-02 阻塞回落和解释；
  原生证据仍缺同一个 Files 批次覆盖四类决定。
- **RO-3 / AC-03。** 精确子集、一次确认、原请求核对及同 Task 交接有通过证据。修正后以跳过和就绪兄弟
  同批旅程重验选择与媒体效果。
- **RO-4 / AC-04。** 任务详情正文、两页签、同任务四类恢复和精确原位续作已有 B PASS 和 A 检查证据。
  修正涉及共享恢复表单时复跑对应原生入口。AC-05 的 Task 证据仍有效，Files 回落和焦点随修正复核。

继续原 Task 59.1 修正。B 收到新候选后复核并补齐 Slice 验收，再向 A 交接。下面是原候选的验收记录。

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
