# Task 59.4 — 整理弹窗共用真实阶段的准备页

Next Action: DEVELOPER IMPLEMENTS TASK 59.4

```text
Task ID: 59.4
Task Type: SLICE
Parent Slice: 59
Status: PLANNED
Task Base: bccfb2c4c014eb181d33ebc5b99140c1c722b446
Planning Contract: 36f60fe0ef75c9cbb9e0b30e258c2d6f4075f24d
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

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
