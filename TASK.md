# Task 59.4 — 整理弹窗共用真实阶段的准备页

Next Action: DEVELOPER VERIFIES CONTINUATION AT FIRST PLAN HANDOFF IN TASK 59.4

```text
Task ID: 59.4
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: bccfb2c4c014eb181d33ebc5b99140c1c722b446
Planning Contract: 36f60fe0ef75c9cbb9e0b30e258c2d6f4075f24d
Reviewed Implementation Head: 0af3e6ec89d8ac3d6331d7ac9b80f60b82f500f6
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Task 59.4 B 复核

**`0af3e6ec` · FIX REQUIRED · RO-1 / AC-01、AC-06。** 复核原 Task Base 至本候选及完整 Slice
区间。首份摘要等待期间，先读到取消状态的路径已通过。准备页结束动效，保留原范围和进度，
随后在同页显示只读摘要，并可返回原 Files 位置和焦点。

从 Files 发起整理并等待首份摘要，在另一标签页从任务中心取消同一任务。使用真实 Worker、API
及 SQLite，仅调整浏览器收到两个原响应的先后。后台已保存 `cancelled` 和 `continuable=false`，
此时先交付早先读取的摘要，下一次准备状态读取尚未返回。Files 错进「本次整理概览」并显示
「整批复核」。摘要到达后组件沿用此前的可继续状态，记录已进复核并停止准备轮询，等待多个正常
轮询周期后仍在概览。该次验证发送的分析和执行请求均为零。

1. 首份摘要可读时，在进入概览或托管复核前，使用现有读口核对同一准备和关联任务的当前可继续
   状态，以及当前关联的摘要身份。以与本次交接对应的状态读回为准。读回在等待时保留准备页，
   读取失败时提供原位重读。正常读回直接交接。
2. 当上一步读回已取消时，让原摘要作为只读内容加入共用准备终态，保留原范围、进度和「返回文件页」。
   仅在检查通过且实际交接时记录已进入复核。保留准确历史地址以及进入复核后结算的原有只读行为。
3. 在现有真实浏览器取消用例添加摘要响应先到的变体。断言取消在摘要交付前已持久生效，随后一直留在
   准备页，读到取消后仍可核对同一只读摘要并恢复返回焦点。保留取消状态先到、正常交接和零分析及执行请求断言。

治理、Task 与 Slice 区间空白检查、Web 类型、Lint、格式、构建及夹具 Ruff 检查通过。
组件 150 项及计划内真实浏览器 12 项通过，补充的响应顺序用例复现上述阻塞。
`.git/validation-evidence/0af3e6ec89d8ac3d6331d7ac9b80f60b82f500f6/b-task59.4-review/`
中的 `cancel-response-order-retest.log` 和对应浏览器产物记录实际先后顺序、页面和请求。

### 前序复核

**`9845da52` · FIX REQUIRED · RO-1 / AC-01、AC-06。** 复核原 Task Base 至本候选及完整 Slice
区间。首次读取前已超限结算、经历两次读回后超限结算、排队期间从另一标签页取消均通过。
桌面与 390 px 的准备终态保留状态、原受理范围、进度和返回动作，准确历史地址仍可只读核对。

从 Files 选中 `DialogPrepAction.2026.mkv`，由真实 Worker 生成方案。暂缓浏览器的首份摘要
响应，在任务中心另一标签页取消同一任务。API 读回准备与任务均为 `cancelled`，`continuable`
为 `false`，原 `previewId` 仍在。Files 弹窗一直显示「正在读取整理方案」。释放先前已取得的
摘要后，弹窗进入「本次整理概览」并显示「整批复核」。浏览器没有发送执行或分析请求。

1. 首份摘要读取或重读期间，继续核对关联的原准备，直到首次正式交接或确认结算。原准备已停止时，
   以该终态结束动效并阻止旧摘要触发概览。正常可用摘要及时交接，保持现有查询边界和原任务身份。
2. 只在可继续的方案实际交接给复核界面时记录已进入复核。终态下迟到的摘要作为只读内容加入
   共用准备页，保留取消标题、原受理范围、进度和「返回文件页」。通过准确历史地址或已进入
   复核后结算的任务仍沿用原只读路径。
3. 增加真实浏览器回归，暂缓首份摘要响应，经任务中心取消并验证原任务已持久结算。分别在
   释放摘要前后核对准备终态、范围、只读边界、返回焦点及零分析和执行请求。保留快速方案交接、
   首读超限、两次读回超限、排队取消及准确历史地址覆盖。

治理、Task 与 Slice 区间空白检查、Web 类型、Lint、格式、构建及夹具 Ruff 检查通过。
组件测试 150 项、计划内真实浏览器 11 项通过。补充的摘要等待取消用例复现上述阻塞。
日志与截图位于 `.git/validation-evidence/9845da5236e5bcfa6c4f262ff180841ccfdd4d4e/b-task59.4-review/`。
`cancel-first-summary-retry.log` 与对应浏览器产物记录取消事实和释放摘要前后的页面。

### 上一轮复核

**`5a20e866` · FIX REQUIRED · RO-1 / AC-01、AC-06。** 复核原 Task Base 到本候选及完整 Slice
区间。标准超限旅程在 1440 和 390 px 保留了「超出主文件上限」、来源、范围、准备进度和返回动作。
取消旅程在本机补齐 Worker 就绪夹具后也通过，截图确认保留了范围，且没有矛盾的摘要提示。

从 Files 提交 `PrimaryLimit` 文件夹，保持弹窗在「正在读取准备状态」，将浏览器首次准备 GET
暂缓至实际 Worker 完成。第一份真实读回是 `partial_success`，关联 Task 为 `failed`，
超限事实为 `primary_limit`，执行请求为零。弹窗进入「本次整理工作已结束」，受理范围、
准备进度和「返回文件页」均消失。候选仅在本次挂载已经读到过未结束状态时使用共用收尾页面，
遗漏本次从 Files 发起且在首次读回前结算的路径。

1. 用同一弹窗已发起这次准备及是否已进入复核的事实决定准备收尾归属。Files 本次提交的首次读回
   如果已停止，直接显示真实准备终态和适用动作。通过准确历史地址打开，或在已进入复核后结算时，
   沿现有历史读取条件显示只读内容。
2. 加入真实 101 项用例的首次读回变体，保持页面等待，直至实际 Worker 将原 Task 结算，再释放首个
   GET。断言原范围、进度、返回焦点及零执行请求。保留两次读回的超限变体和准确历史地址的断言。
   取消回归在本用例内注册测试 Worker，使它可以单独运行。

Web 类型、Lint、格式、构建、治理、区间空白检查、148 项组件测试及计划中的 9 项原生浏览器
用例通过。新增时序复现失败，单独运行提交版取消用例时缺少 Worker 就绪，补齐同一测试夹具后通过。
日志、截图和复现代码位于
`.git/validation-evidence/5a20e866a4e9f158bc2fae2e0baa5ae959efca58/b-task59.4-review/`。
`probe.log` 记录首次读回，`limit-visual.log` 与 `cancel-fixture.log` 记录标准超限和取消。

### 早期复核

上轮复核了 `bccfb2c4c014eb181d33ebc5b99140c1c722b446..523628eab5b0f3c3ea7287e16f88c0642f5f4110`
和完整 Slice 区间。治理、区间空白检查、Web 类型、Lint、格式、构建及夹具 Ruff 检查通过。
两组组件共 146 项通过。真实 Python/API/SQLite/Worker 原生浏览器 9 项通过，含 Files 方案交接、
摘要读取失败及重读、100/101 项边界、任务中心准备中重开及已就绪原位续作。

**FIX REQUIRED · RO-1 / AC-01、AC-06。** Files 中打开 101 个主文件的目录，真实 Worker 首先
发布超限，弹窗显示「超出主文件上限」、原受理范围和准备进度。关联任务结算为失败后，同一弹窗
切成「本次整理工作已结束」，受理范围、进度和范围核对入口消失。从另一个标签页经任务中心取消
排队中的 Files 准备，也复现通用终态，正文同时声称原摘要保留和从未生成。API 读回准备及任务
均为 `cancelled`，`previewId` 为空，浏览器的执行请求为零。批准离线稿在两种终态都保留共用
准备状态区、来源、受理范围和准备进度，并给出适用的返回动作。

1. 在首次准备的正文选择中，按真实准备和关联任务事实识别停止原因。在仍是准备首屏时，让取消、
   超限和完整范围不足的结算沿用共用准备正文，显示对应状态、已知影响、来源、受理范围、进度
   和按需核对的范围。超限的两次耐久读回仍区分正在收尾和最终失败。
2. 在 Files 的准备终态提供「返回文件页」并沿用现有关闭和焦点恢复。终态停止动效，正文与底栏
   说明实际效果。按真实摘要关联决定展示只读原方案或未生成提示。已经进入复核后的终态和准确
   历史地址继续遵守原有只读入口与摘要读取条件。
3. 扩展真实 101 项旅程，在 Worker 发布超限和关联任务结算后分别断言状态区、范围明细、进度、
   返回位置和无执行请求。补一条取消准备旅程，从另一标签页取消同一 Task，核对准确的终态、
   未生成摘要、Files 返回及 1440、390 px 表现。同时复验实质范围不完整时的合法动作。

日志与同视口对照位于
`.git/validation-evidence/523628eab5b0f3c3ea7287e16f88c0642f5f4110/b-task59.4-review/`。
`probe-retry.log`、`cancel-retry.log` 记录实际页面证据，`preparation-probe/screens/`
与 `approved-states/` 存放截图。原 Task Base 沿用，修正完成后进入同一 Task 的 B 复核。

## B 复核与 Slice 59 交接

- **Task 59.3 · PASS。** 独立复核 `d1ea5f667c5ebc08e1a6835030197c1724f4f4d2..bccfb2c4c014eb181d33ebc5b99140c1c722b446`
  和完整 Slice 区间。Task 范围及上轮退回事项见 `ae98701c:TASK.md`。
- **A59-04。** 从 Files 留下未确认方案，经任务中心原位重开并由真实 Worker 完成同一任务。
  在 1440 和 390 px 对照批准稿，等待确认时显示实际准备和分析计数、待确认范围及合法动作。
  完成后显示「流程已完成」「已处理 1 / 1 个主条目」及独立文件结果。两个状态都使用文字进度。
  等待页保留预览之外的准备计数口径和零媒体变更说明，避免把已准备解读为已执行。
  另核对未知总数、读取失败、混合结果和效果待核对。
- **A59-05。** 用 A 当时的复现路径核对，结算前访问「成功」为空，结算后回访的实际请求从 1 次增至
  2 次，直接显示同一文件的已验证结果和真实目标。21 文件真实旅程回访相同游标的第二页时重发请求，
  条目身份相同且显示结算结果。组件复验操作记录停留、迟到的旧响应、另一任务缓存隔离、
  相同终态重复读回，原生浏览器复验筛选、分页、证据与焦点。
- 治理、两段 Git 区间空白检查、Web 类型、Lint、Prettier、构建通过。组件 110 项、Node 浏览器
  14 项、真实 Python/API/SQLite/Worker 浏览器 12 项通过。另跑一次 A 的复现路径并通过。
  原始日志及截图位于 `.git/validation-evidence/bccfb2c4c014eb181d33ebc5b99140c1c722b446/b-task59.3-review/`。
  `a-regression.log` 和 `a-regression-probe/screens/` 记录同一任务前后对照，`approved-detail/`
  是固定离线稿的相同状态对照，`settlement.log` 记录分页结算用例。
- Task 59.1 的通过记录见 `ae98701c:TASK.md`，59.2 的既有通过范围见 `171b3de6:TASK.md`。

Slice 59 仍为 `FIX REQUIRED`。已通过的概览、四类决定、精确整批确认与任务详情可作为本轮回归基线。
准备首屏差距纳入本 Task，任务中心「需要处理」的四类问题文件列表及入口按 RO-5 接续规划。
全部结果通过后交独立 A 终验。

## 目标

从 Files 选择单文件、文件夹或混合范围，使用原按钮或右键打开现有整理弹窗。首次概览前，用户
一眼看到当前动作、来源、范围与真实进度。完整准备依次显示「检查所选范围」和「生成整理方案」。
进入时只剩生成或读取等一步，直接显示那一步。任务中心从合法的「继续整理」重开原准备时使用
同一首屏，若原方案已可用便进入原复核。遇到中断时说明本次受理、已知影响及可以采取的下一步。
适用 Slice 59 RO-1、AC-01、AC-05/06，以及 AC-07 的原准备重开。设计依据见提交版 [SLICE.md](SLICE.md)。

## 实施步骤

1. 在 `ManualOrganizeDialog` 收敛 Files 和任务中心托管时的首次准备正文。当前 Files 使用阶段卡，
   托管入口落到另一套等待正文。共用批准稿的状态区、准备进度和按需范围明细。阶段只读同一准备的
   受理状态、发现进度、方案关联和摘要读回。收起路径、排除原因及技术详情，阻止或拒绝原因与
   合法动作就近呈现。
2. 完整准备中，排队、检查和等待稳定随读回呈现第一步，完成检查并开始等候生成或分析时呈现
   第二步。生成后的摘要读取属于这次完整准备的收尾。进入时只需生成、读取原状态或读取已生成
   方案，显示实际单步。快速完成直接到可读结果。同阶段轮询保持动效、焦点、展开项及滚动稳定，
   减少动态效果时即时呈现真实新阶段。
3. 在现有受理、查询和重读边界接入失败及等待状态。区分后台不可用、来源读取错误、部分未受理、
   无主文件、取消、范围不完整、超限及摘要读取失败。保持原任务与已受理范围。读取失败时重读
   同一准备或摘要，等待期间保留适用提示。只有后端允许时可以补做原分析。第 101 个合格主文件
   按现有规则使整批停止。部分未受理时，其他已合法受理且有完整方案的项仍可复核。
4. 保持现有进入条件和关卡。Files 首份有效方案读回后进入原概览，任务中心关联的原方案就绪时
   进入现有托管复核。关闭恢复原列表或文件背景上下文。工作边界是首次准备正文和它的入口交接。
   复用既有 API、查询、权限、失败处理和确认边界。

## 验收

- [ ] 原 Files 单文件、批量、文件夹与混合入口打开同一弹窗。桌面和 390 px 对照离线稿，观察
  完整两步，由真实 Worker 的不同阶段切换。进入时只需生成或读取的场景显示实际单步，
  进度与发现计数一致，未知总数保留原义，方案可读后即时到概览。
- [ ] 从任务中心合法重开进行中的原准备，正文的当前阶段与原任务一致。重开已就绪方案直达复核。
  关闭回到原弹窗或列表、页签和入口焦点。刷新和迟到读回仍关联准确 Task 和准备。
- [ ] 核对排队、等待稳定、暂不可用 Worker、来源读取失败、部分未受理、无主文件、取消、完整范围
  不足、100 项和第 101 项、摘要暂不可读及同摘要重读。终止时结束动效并解释影响，未完整的
  截断范围不能确认。已受理项依据自身结果进入复核。确认前媒体根无变化。
- [ ] 相同阶段的轮询保持展开、滚动与焦点，阶段变化清楚可读。键盘和 reduced-motion 可访问，
  桌面、390 px 与矮视口保留原标题、背景、关闭和可用动作。

## 测试

Developer 运行新增及直接受影响的组件和真实入口测试。补充阶段切换、稳定同阶段、单步生成或
读取、已就绪重开、摘要失败和 reduced-motion 断言。扩展原生 Files 准备及任务中心继续整理用例，
覆盖真实 Worker 驱动的首屏交接及进行中重开。保留原零变更、身份与确认断言。

```sh
# 仓库根目录
python3 scripts/check_governance.py
git diff --check
# web/
npm run typecheck
npm run build
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/OperationsInventory.test.tsx
npx eslint src/features/operations/{ManualOrganizeDialog,ManualOrganizeDialog.test,OrganizeContinuationCard}.tsx tests/e2e/{manual-organize-dialog,operations-inventory}.python.spec.ts
npx prettier --check src/features/operations/{ManualOrganizeDialog,ManualOrganizeDialog.test,OrganizeContinuationCard}.tsx src/shared/ui/styles.css tests/e2e/{manual-organize-dialog,operations-inventory}.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/operations-inventory.python.spec.ts --grep 'completed walk into the same preparation|first-plan preparation while the linked summary|re-reads its exact summary|no primary file|human-waiting frozen preparation|101-file directory|initial manual preparation remains reachable'
```

B 运行上述验收组、新用例以及 Web 全量 Lint 和格式检查，审查 Task Base 与完整 Slice 区间。
用临时媒体根从原入口走完真实准备、暂停阅读、重开、等待、失败及首份方案交接。留存批准稿与
候选在 1440、390 px 和适用矮屏的对照图、阶段和请求证据。等级依据见 [开发与验收分工](docs/development-workflow.md#6-test-levels)。

## 范围边界

批量或逐文件复核正文、四类决定与回落、任务详情进度、任务中心问题列表由原任务或后续 Task 管辖。
保持现行数据读模、阶段定义、持久任务、执行条件、后端权限及安全边界。
