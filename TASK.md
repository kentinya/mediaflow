# Task 59.3 — 任务详情文字进度与结算后的文件读回

Next Action: DEVELOPER CORRECTS A59-04 AND A59-05 IN TASK 59.3

```text
Task ID: 59.3
Task Type: SLICE
Parent Slice: 59
Status: FIX REQUIRED
Task Base: d1ea5f667c5ebc08e1a6835030197c1724f4f4d2
Reviewed Implementation Head: 6c54559b054d75682fc9ead615191d6c0b351285
Planning Contract: 36f60fe0ef75c9cbb9e0b30e258c2d6f4075f24d
Working Head at Planning: f4c739e461e79412d4dbf032186f10caf4d0391a
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 59.3 CORRECTIONS A59-04 AND A59-05
```

## B 复核与 Slice 59 交接

**Task 59.1 · PASS。** B 独立审查 `3bc9ad99137e5a2f8ff53add92041185ceb8ebbf..88f5d536610a7d9a31d5aa4cfe5ce04e02d8ba38`。
从真实 Files 混合批次在 1440 和 390 px 打开五种决定表单，修改前后均核对底栏动作分组和顺序。
草稿提示位于当前文件，顶栏关闭要求核对未保存的草稿。返回概览保留当前文件的焦点、草稿和已选
范围。跳过结果在新版摘要与刷新后保留。一次确认只执行四个合法文件，源文件与已有目标保持原状。
Task 59.2 的通过范围见 `171b3de6:TASK.md`，本轮任务中心同页恢复六项复验通过。

- 治理、Task 和 Slice 完整区间空白检查、Web 类型、ESLint、Prettier 与构建通过。组件 108 项、
  Node 浏览器 77 项、真实 Python/API/SQLite/Worker 原生浏览器累计 19 项通过。
- 首轮三条任务中心相关回归和两条容量用例使用旧文案或旧页面位置。B 对照失败现场更新测试定位，
  保留提交条件、精确子集、持久任务和媒体效果断言，并复跑对应五条及两条受同一回落文案影响的用例。
  测试提交 `f4c739e4` 仅改变三个测试文件。生产、配置及夹具与实施候选相同，沿用未改变输入的通过结果。
- 本机原始通过、失败与重跑日志、截图及区间清单位于
  `.git/validation-evidence/88f5d536610a7d9a31d5aa4cfe5ce04e02d8ba38/b-task59.1-review/`。
  上轮 A59-07 的关闭及准确重开、逐次跳过持久读回在 `6f2477b8:TASK.md` 有固定记录。

B 按用户授权接续原 Task 59.3。规划时 `main` 位于上述 Working Head，工作区和暂存区干净，治理
检查通过。原 Task Base 沿用，启用范围以最新批准预览和提交合同为准。
[终审合同](SLICE.md#a-独立复验--6c54559b--fix-required)

## 目标

操作者从任务中心打开已准备的任务，能读出准备或分析到了多少、几个文件尚待确认，以及「继续整理」
是否可用。显式确认并等待原任务完成后，能读到流程进度和独立文件结果。再次打开结算前已访问过的
筛选和游标页时，页面自动查询原任务的正式结果。原页签、当前筛选和文件证据仍可继续使用。

## 范围与实施步骤

1. **A59-04。** 按批准预览调整 `ProgressCard`。任务状态标题及适用说明下方用「处理进度」和当前
   阶段的数量文字呈现，移除该卡的条形控件及宽度计算。等待确认明确列出准备或分析口径、待确认文件数
   与当前合法动作。正常完成时，进度文字后接独立的文件结果。未知总数、进度证据暂不可读、扫描错误
   及异常情况继续说明真实状态、已知结果和适用的下一步。
   [任务进度](web/src/features/operations/RunDetailTabs.tsx#L1012)
2. **A59-05。** 在两页签共用的 `RunDetailTabs` 观察到同一任务从进行中进入终态时，按
   `[runItemsQueryKey, runId]` 前缀取消该任务结算前的条目读取，并让同前缀的已访问缓存失效。
   当前条目页立即重读，隐藏页重新打开时读回。复用现有 Query 取消和失效机制，避免旧响应覆盖终态。
   保留当前页签、筛选、游标、行内证据和焦点。切换到另一任务时按其自身状态读回，同任务的重复终态
   读回维持稳定。
   [当前终态读取](web/src/features/operations/RunDetailTabs.tsx#L837) ·
   [条目查询键](web/src/features/operations/run-detail-query.ts#L56)
3. 本轮实现限任务详情进度与条目读回，复用现有任务状态、结果口径、有界分页及后端动作资格。

A 的对照与读取日志位于本机
`.git/validation-evidence/6c54559b054d75682fc9ead615191d6c0b351285/a-slice59-files-recovery-visual/`。
`progress-and-filter.log` 有成功筛选回访沿用旧结果的请求证据。

## 验收

- [ ] 从 Files 留下同一份未确认方案，从任务中心续作并通过真实 Worker 完成。桌面和 390 px 查看等待确认、
  完成两个状态的标题和文字进度，核对预执行计数及正式文件结果。复验未知总数、读回失败、混合结果和
  效果待核对。
- [ ] Worker 完成前访问「成功」见空列表，回「全部状态」等待结算，再选「成功」。检查请求实际重发，
  页面显示原文件「已验证成功」及目标。验证用户停在「操作记录」时后台结算，切回文件详情显示更新结果。
  保留旧条目请求迟到的隔离用例，核对新的查询结果在迟到响应后仍准确。
- [ ] 用 21 个已就绪文件覆盖结算前访问第二页、回第一页、结算后再访问第二页。核对第二页的游标、
  原任务、条目身份与实际读回。复验筛选隐藏、跨页证据和关闭后焦点。组件覆盖另一任务的缓存隔离及
  相同终态重复读回。

## 测试

Developer 在 `web/` 运行以下命令，交接精确候选、实际结果与桌面和 390 px 对照图。组件覆盖进度口径、
缓存失效和迟到结果。原生用例覆盖任务中心原位续作、真实复制结算与分页。将筛选和分页跨结算的具体断言
加入对应旅程。

```sh
npm run typecheck
npm run build
npx eslint src/features/operations/{OperationsInventory.test.tsx,RunDetailTabs.tsx,RunDetailTabs.test.tsx,run-detail-query.ts} tests/e2e/{operations-inventory,manual-organize-dialog}.python.spec.ts
npx prettier --check src/features/operations/{OperationsInventory.test.tsx,RunDetailTabs.tsx,RunDetailTabs.test.tsx,run-detail-query.ts} tests/e2e/{operations-inventory,manual-organize-dialog}.python.spec.ts
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'initial manual preparation remains reachable in place|real destination conflict is decided|21-file recovery pages preserve'
```

B 审查原 Task Base 至精确实现候选与完整 Slice 区间，独立复跑上列组件及原生验收。从真实入口对照
等待确认、流程完成及异常的文字进度，核对另一个筛选、游标页、页签往返和迟到响应。仓库根目录运行
治理及区间空白检查，在 `web/` 运行 `npm run lint`、`npm run format:check`，并补跑任务中心布局与原位恢复。

```sh
# 仓库根目录
python3 scripts/check_governance.py
git diff --check d1ea5f667c5ebc08e1a6835030197c1724f4f4d2..HEAD
# web/
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'native recognition recovery|native Metadata candidate recovery|native Metadata correction|native Classification recovery reconciles|native conflict recovery renames|policy-permitted overwrite'
```

[开发与验收分工](docs/development-workflow.md#6-test-levels)

## Slice 接续

Slice 59 仍为 `FIX REQUIRED`。59.3 通过后重新核对剩余结果。共用准备页仍需按真实状态呈现检查范围、
生成方案或正在执行的单步。任务中心仍需把「需要处理」下的四类筛选和问题文件接到原任务详情、同文件恢复
与返回定位。后续按完整旅程分别规划，通过后交独立 A 终验。
