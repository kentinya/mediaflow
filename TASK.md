# Task 59.2 — 任务中心运行详情正文

Next Action: B REVIEWS THE TASK 59.2 CORRECTION CANDIDATE

依据已提交的 [Slice 59](SLICE.md) RO-4、AC-04 和 AC-05 的任务详情部分，落实
`V2-OPS-021`。开发与验收按[开发工作流](docs/development-workflow.md)执行。

用户已授权实施 Task 59.2。Developer 已完成本轮修正并交 B 独立复核。激活前的规划提交为 `92057bc2`，原实施候选为 `d1a58b91`，本轮修正候选为 `85e689cf`；工作区在实施前干净，治理检查通过。

```text
Task ID: 59.2
Task Type: SLICE
Parent Slice: 59
Status: READY FOR B REVIEW
Task Base: 868ff9daab6972473cfb7344ca02cbdbc30077cf
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: AUTHORIZED BY USER FOR TASK 59.2
```

## 上一 Task 的 B 复核

**Task 59.1 PASS**。独立审查
`3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..868ff9daab6972473cfb7344ca02cbdbc30077cf`。
实施提交为 `ea5a198a38d92719c0813ca0bbcb7844aa9c5298`，后继仅改变 TASK 交接记录。
从 Files 批量选中元数据服务故障项和就绪项，概览、文件详情、整批未纳入项均显示相同的故障
阶段和可走的下一步，就绪项可以单独确认。只选故障项并等任务结束，原摘要以只读方式显示
同一故障与从 Files 重新发起的路径。故障探测走隔离的本地测试 Provider。
概览焦点、精确选择、附件核对、100／101 项边界、分析或确认丢包后的原请求核对、同任务
交接、任务中心原位续作及历史均按现有入口复核。

B 实跑（cwd `web/`）：typecheck、lint、format:check、build 通过。Web 的
`library-files.spec.ts` 和 `task-center-layout.spec.ts` 共 64 项通过。
`manual-organize-dialog.python.spec.ts` 全部 21 项通过；
`operations-inventory.python.spec.ts` 的原位续作和详情上下文共 2 项通过。
查看了桌面、390 px、矮窗与原位弹窗证据。复用实施提交的 158 项受影响单测。治理与
`git diff --check` 通过。实跑日志及截图在本地
`.git/validation-evidence/868ff9daab6972473cfb7344ca02cbdbc30077cf/task59.1/`。
此前的 Task 59.1 计划和每轮修正保留在上述审查范围的 Git 历史中。

Slice 重评：Files 的准备、同弹窗概览、决定回落与整批确认构成 RO-1–3 的已审交付。
RO-4 的任务中心正文是剩余实现，四类组合和跨表面结果随 Slice 最终候选共同复核。
Slice 保持 ACTIVE。

## Goal

用户从 Files 确认交接、任务列表、原任务链接或四类问题列表进入准确的「运行详情」。
先读清任务到了哪一步、是否需要行动、文件和附件实际发生了什么。某一文件仍需决定时，
在它自己的证据下完成决定、分析、核对新计划并显式继续。关闭证据或顶层续作卡后回到
原任务和触发处。

当前 `RunDetailPanel` 已接入后端流程、进度、文件计数、任务动作和原准备关联。
`RunDetailTabs` 把原位「继续整理」放在文件结果下方的事实区，文件行展开前仍显示原始阶段、
尝试和失败码。仅有未知效果或结果缺失证据时，结果摘要可能不显示。正文的阅读顺序、适用动作和清晰
的结果层级是这个 Task 的交付。行内证据、重读、诊断、翻页、审核和导出已有在用组件。
[详情弹窗](web/src/features/operations/OperationsLanding.tsx) ·
[页签与文件证据](web/src/features/operations/RunDetailTabs.tsx) ·
[任务中心现行旅程](docs/task-center-page-spec.md#current--任务正文与文件证据)

## Developer implementation guide

1. 调整 `RunDetailPanel`、`RunDetailTabs` 与本地样式。正文顺序为流程状态与阶段／等待、
   实际进度和当前适用操作，然后是文件结果、需处理项及证据。用现有动作管道呈现取消、读回
   或「文件整理准备 → 继续整理」。把任务触发时间、范围和技术诊断放在主结果之后，用现有
   可展开证据呈现固定配置和 Worker。保持原弹卡标题、关闭、页签、列表背景和滚动约定。
2. 用 `RunSummary`、进度、条目及持久 Result 原有字段显示彼此独立的流程和文件／附件结果。
   逐文件先显示可读处置和需处理原因，原始阶段、策略和记录可在有效的证据区查阅。来源／目标、
   识别、作品、命名、分类、附件、逐次执行、日志和审计按对应文件和尝试组织。按已有读回分别
   描述总量未知、缺少记录、读取失败和效果未知。保留「操作记录」页签及原有筛选、分页和有界导出。
3. 沿用 `RunItemsSection`、`RunEvidenceSection`、`TaskItemRecoveryPanel` 的任务和条目
   身份、挂接与草稿归属。行内唯一证据贴着自己的文件，筛选／跨页时沿用迁移及返回。识别、
   元数据、分类、冲突继续用同一任务的原表单、分析、同页新摘要与显式确认。父详情保留现有
   `run + dialog=organize` 的准确关联和二层卡片焦点规则，正常关闭后恢复相同页签和位置。
4. 从现有任务入口验收布局。用桌面、390 px 和矮视口核对长名称、路径折行、操作位置、键盘与
   reduced-motion。保持实时更新时的阅读位置；必要提示随已读到的流程或文件事实更新。

## Acceptance criteria

- [ ] 从实际 Files 交接和任务列表打开同一任务详情。先看到流程、阶段或等待、独立进度、当前
  动作，再看到文件结果与待处理项。已结束或无准确准备关联时，正文仍可查明结果。Task 读取
  缺失、文件列表读取失败、记录读取失败各自显示原因，并能从原位置重读。
- [ ] 核对成功、混合、主文件完成而附件失败、单文件技术终结、Task 失败、取消、跳过或忽略、
  效果未知与缺少正式 Result。结论各自来自原持久证据。「恢复成功」同时具备流程完成与必要
  文件效果验证。展开证据可核对去向、处理依据和以往尝试。
- [ ] 通过四类列表打开准确条目，完成原决定、分析、新计划摘要和一次明确确认。切换问题类型
  时以最新任务事实更新。筛选、翻页、读取异常期间能够继续查看同一条目，草稿保留，关闭
  返回原触发处或既有回落位置。已完成或效果未知的文件保持原有只读证据。
- [ ] 「继续整理」只在后端确有可继续准确关联时出现。打开、关闭、刷新及认证续转保留精确
  任务和原列表、页签、焦点。两页签可读，原记录筛选和导出仍有效。桌面、窄屏、矮窗口、
  键盘、长路径、滚动和 reduced-motion 的实际界面验收通过。

## Required tests

以下命令从 `web/` 运行。新改用例以 `Task59.2` 标记。

**Developer**

- `npm run typecheck`，对实际触及的文件运行 ESLint 和 Prettier，仓库根运行
  `git diff --check`。
- `npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx`。
  覆盖正文顺序、可用动作、独立结果和失败重读，保留证据唯一性、筛选迁移、草稿、导出与原续作。
- `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts`。结合现有桌面、390 px 和
  reduced-motion 布局用例验证正文、可见操作和焦点。
- `npm run build` 后运行
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'Task59[.]2|the selected run detail reads progress|detail tab and filter context|initial manual preparation remains reachable in place'`。
  用真实入口核对变化后的正文、证据与同任务续作。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts`。
  对照真实的混合结果、任务流程失败和协作取消，核对新正文的结果表达。

**B**

- 运行 T3 Web 门禁并出具桌面、窄屏与矮窗证据。复跑
  `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/library-files.spec.ts`
  检查原背景和 Files 交接。
- 复跑 Developer 清单中的原生定向命令，并覆盖原生四类恢复、混合技术／未知结果与有界导出。
  按现有用例名运行。
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'native recognition recovery|native Metadata candidate recovery|native Metadata correction|native Classification recovery|native conflict recovery|a mixed run never offers|the eligible run exports'`。
- 对精确候选复核全部 Slice 结果。最终按 Slice 合同补齐仍适用的跨任务原生证据，提交给 A 终审。

## Non-goals

范围限原「运行详情」正文。原 Shell、运行卡外壳与标题、列表与八个视图、日期筛选、分页、
问题文件定位面板、Task 59.1 Files 弹窗和独立续作／历史卡以当前行为为准。复用现有 API、
持久读模、任务状态、权限和执行语义。通用恢复、新生产配置或发布部署沿用 Slice 延期边界。

## Developer completion report

已按 Task 边界完成修正候选 `85e689cf221b8d4372e81db14f0176369ae24d54`（源码与测试；
后继仅更新本 TASK 交接记录）：

- 文件行以持久检查点效果事实给出当前结果：`verified_complete` 显示「已验证成功」；成功
  状态但效果为 `attempted_unverified`/`unknown` 时在「处理结果」显示「效果未确认」，同名
  行指向「查看证据核对目标与已记录效果」；失败/部分完成在效果未确认时同时在结果中标注。
  跳过、忽略、取消和 DryRun 各自显示结果；普通收尾的 `replay_not_offered` 不再进入
  「需处理原因」，只留在该文件的原有技术诊断。
- 文件证据的「处理结果」只把 success/partial/failed 的零结果读为「结果未记录」；跳过等
  正常终态不再被误报为结果缺失。已尝试但效果未确认的 success/partial/failed 在有持久
  执行记录时显示未确认原因和原有核对动作。
- 「文件结果」成功计数改用进度读模的 `confirmedSuccess`，按会计基础显示「已验证成功」／
  「分析完成」／「已验证传输」／「已验证操作」／「已记录成功」；无进度读模时回退到持久
  状态计数并明确标为「成功（已记录状态）」。部分、失败、未知和缺失计数保持原有独立口径。
- 阻塞原因改用实际检查点类型 `recognition`／`metadata`／`metadata_correction`／
  `classification`／`conflict`：分别说明确认识别结果、确认元数据候选、修正元数据搜索、
  确认分类目标、处理目标冲突；文件行与展开证据复用同一文案。文件行级恢复表单、同任务
  摘要与确认、精确续作、两页签、筛选分页、草稿和有界导出未改。
- 未改 API、schema、Worker、权限或执行语义；未新增入口或页面。

实际命令与结果（cwd `web/`）：

- `npm run typecheck` — 通过。
- `npm run lint`、`npm run format:check` — 通过。
- `npx eslint`／`npx prettier --check` 修改文件 — 通过。
- `npm run test -- run src/features/operations/RunDetailTabs.test.tsx
  src/features/operations/OperationsInventory.test.tsx
  src/features/operations/TaskItemRecoveryPanel.test.tsx` — 3 files / 121 tests passed
  （29.03 秒），含新增 Task59.2 三种文件行结论、未确认效果的原尝试/目标/效果核对和
  真实 blocker 类型文案用例。
- `npm run build` — 通过；最终产物 `dist/index.html`、`index-hXIaOMvw.css`、
  `index-Cz-cdBnZ.js`。
- `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts` — 13 passed（9.5 秒），
  含桌面、390 px、矮窗、键盘与 reduced-motion 布局用例。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts --grep
  'Task59[.]2|the selected run detail reads progress|detail tab and filter context|initial manual preparation remains reachable in place'`
  — 3 passed（21.1 秒）；历史混合任务读取已验证成功、未确认效果、正常跳过及其证据。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/manual-organize-dialog.python.spec.ts --grep
  'a real destination conflict is decided'` — 1 passed（17.7 秒）；Worker 完成后文件行
  为「已验证成功」、无重放提示，证据显示原目标与已验证效果。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts --grep
  'native recognition recovery|native Metadata candidate recovery|native Metadata correction|native Classification recovery|native conflict recovery'`
  — 7 passed（15.1 秒）；逐类型核对文件行/证据原因与「查看证据」动作。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/task-flow.python.spec.ts` — 3 passed（5.9 秒）。
- `npm run test:e2e -- tests/e2e/operations.spec.ts --grep
  'the selected run detail reads flow|keeps the mixed completed run'` — 2 passed（1.8 秒）。
- 仓库根 `python3 scripts/check_governance.py`、`git diff --check` — 通过。

已知限制/风险：`openlist-metadata.python.spec.ts` 的本机运行在打开页面后的
`/__harness__/openlist-state` 读取返回非 2xx，失败发生在本次结果标签断言之前；已按两条
`verified_complete` 结果将该断言更新为「2已验证成功」，需 B 在具备完整 OpenList 夹具的
环境复核。未单独查看截图，桌面／390 px／矮窗视觉证据由 B 在候选上复核。E2E 使用既有隔离
夹具与临时媒体根，未触及生产 Provider、真实用户媒体或新的执行路径。本轮测试执行约 3 分钟，
低于本轮开发总耗时的 30%。未推送或发布。

## B review result

**FIX REQUIRED**。B 独立复核
`868ff9daab6972473cfb7344ca02cbdbc30077cf..9ed64f28493f6e97a87ca7fda4aa16c91d9ac96f`。
实施候选为 `d1a58b9199e07840cf3ce9ae5842637a47f4c7e5`，后继提交只更新本 Task 的交接记录。
任务动作已移到进度之后、文件结果之前。以下两项阻塞 RO-4、AC-04/05 的文件结果和需处理原因。

1. **文件行把普通收尾列为需处理，并把未确认效果列为成功。** 从 Files 选中
   `DialogConflict.2022.mkv`，复核并确认复制，进入交接的运行详情。Worker 完成后，隔离
   Storage 中已验证目标存在、来源保留；该行仍在「需处理原因」显示「已结束的条目不再提供重放」。
   从任务中心「已结束」打开现有历史混合任务，已跳过项也有这条提示。另一条文件显示「成功」，
   旁边写「目标文件结果尚未确认」，展开同一文件的证据亦为效果未确认。用户无法根据主结果判断
   哪些文件已经有可核实结果、哪些仍要查看证据。
2. **候选决策行给出泛化原因。** 从任务中心「元数据恢复」点击「查看问题文件」，打开
   `MetadataChoice.2015.mkv`。证据中的表单要求确认具体候选，文件行的「需处理原因」却只
   显示「需要人工处理决定」。真正读到的检查点类型是 `metadata`，现有新测试用的是
   `metadata_review`；识别和分类的生产类型同样是 `recognition`、`classification`。

### 本 Task 修正的开发指导

1. 在 `RunDetailTabs` 的文件行中，用现有检查点效果事实表达当前处理结果。对于已验证成功、
   跳过和忽略，显示各自结果，普通收尾的重放限制放在原诊断里。对已尝试但效果未确认的历史
   文件，在「处理结果」直接写明未确认，点「查看证据」后能对照原尝试、已知效果和目标。
   核对正文的成功计数与这些结果的口径。可用时，以现有进度读模的 `confirmedSuccess` 表达
   已验证成功；使用持久状态计数时明确它表示已记录状态。沿用原列表、结果查询和各自的权限。
2. 用实际返回的检查点类型生成当前原因。识别说明需要确认识别结果；元数据候选和作品搜索修正
   分别说明要确认候选或修正搜索；分类说明要确认目标；冲突说明要处理目标冲突。复用同一类型
   对应的文案，让文件行和展开证据指向该文件的当前阶段。从原四类列表进入后，继续用现有表单
   完成决定、重新分析、查看同页新摘要并明确确认。
3. 更新 Task59.2 受影响单测，用实际 API 的检查点值。从现有
   `manual-organize-dialog.python.spec.ts` 的 Files 确认交接用例，验证 Worker 完成后成功文件
   的结果和提示；从 `operations-inventory.python.spec.ts` 的历史混合任务及原生恢复用例，验证
   同一行的已验证成功与未确认效果、正常跳过、以及真实问题类型的文案和对应动作。继续运行原
   Developer 清单中的直接受影响检查，将命令及结果随新候选交 B。

B 实跑 `npm run build` 通过，产物与交接记录一致。两条定向真实浏览器旅程复现上述断言失败，
Playwright 命令墙钟合计约 24 秒，低于本轮复核用时的一半。日志、截图与 trace 保存在
`.git/validation-evidence/9ed64f28493f6e97a87ca7fda4aa16c91d9ac96f/task59.2/`。
其余 T3 门禁在修正候选复核时完成。

Slice 重评：RO-1/2 的准备首屏、概览及决定读回沿用 Task 59.1 已审结果；RO-3 的精确确认、
同任务交接和 Worker 效果在本轮 Files 实跑中通过。RO-4 的正文顺序已交付，逐文件结论和原因
仍有上述阻塞。修正留在 Task 59.2，Slice 保持 ACTIVE。
