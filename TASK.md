# Task PATCH-20261111-3 — 精简任务详情“文件整理准备”说明

用户于 2026-11-11 明确“激活Task吧”，本 Task 已获得实施授权。
原规划检查点为 `6dc0619b856f03ca5750e8592336d197f3788366`；Task ID、Base、目标、范围、
验收及测试分工保持不变。已由 Developer 实施完成并转入 READY FOR B REVIEW。
本次激活只更新任务授权，不启动其他角色、不实施产品代码，也不授权推送或部署。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

上一独立修复 PATCH-20261111-2 的 [固定 B PASS 记录](https://github.com/kentinya/mediaflow/blob/aff254ce0e3dc8b47714b197a7023509e6cc5f66/TASK.md#b-decision--patch-20261111-2-pass)
保留原审查范围、实际结果及限制，不因本次激活改变。

```text
Task ID: PATCH-20261111-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 7b6cadd050591c339589d042235013ca9ff1f26d
Difficulty: Low
Test Level: T2
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-11
```

### Goal / 调查依据

用户从任务中心打开任务详情，在“文件整理准备”中快速理解下一步。
目前 `web/src/features/operations/OperationsLanding.tsx` 的 `RunDetailFacts` 将准备入口、
确认边界、历史保留及重新发起说明全部展开；可继续状态一段，已结束状态两大段，
重复解释详情已有的状态、结果和按钮用途。本 Task 只纠正这一区域说明冗长的问题。

沿用 CURRENT `V2-UX-006`、`V2-OPS-010/017`、`UX-001/002/006`，以及
[Manual organize 完整旅程](docs/product-experience.md#manual-organize) 和
[任务中心手动受理与确认](docs/task-center-page-spec.md#手动受理与确认)。
历史失败阶段、文件结果和已知效果继续由原详情及只读摘要呈现，不转化为成功或新增恢复入口。
这是已接受页面的独立文案修正，不重开 Slice50／53／54；Slice53 当时冻结详情的实施边界
不构成本 Task 的父范围，SLICE／Roadmap／Progress 与既有接受事实保持不变。

### Implementation Scope / 开发步骤

1. 只修改 `OperationsLanding.tsx` 中“文件整理准备”的说明段落，保持标题及区域语义。
   按原 `run.filesPreparation.continuable` 分支使用以下文案：

   | 状态 | 说明 | 原有按钮 |
   |---|---|---|
   | 可继续 | 查看整理摘要，确认后执行。 | 继续整理 |
   | 不可继续／已结束 | 本次整理已结束。如需再次整理，请从文件页发起。 | 查看只读摘要、从文件页重新发起 |

   每个分支只显示上述一句说明；不增加折叠说明、提示图标或另一组帮助文案。
2. 保持三个链接的显示条件、名称、路径、`discoveryId`、`resourceLibraryId`、
   `returnOps`、`organize` 参数及原返回上下文。无 `filesPreparation` 时仍不显示此区域。
   打开详情／摘要和前往文件页仍是原有导航；确认执行、只读历史和新工作准入沿用原行为。
3. 复用 `OperationsInventory.test.tsx` 的两个原入口用例，更新受文案影响的可见文字断言，
   保留其精确关联／只读入口／零提交断言；不为文字或 DOM 结构另建测试体系。
   完成受影响检查后提交连贯候选并交 B 独立验收。

### Acceptance Criteria

- [ ] 可继续任务显示“查看整理摘要，确认后执行。”及原“继续整理”按钮。
- [ ] 已结束任务仅显示约定短句，保留“查看只读摘要”和“从文件页重新发起”；
      不显示执行性质的“继续整理”，不暗示文件全部成功或旧任务可以再次执行。
- [ ] 原长说明不再显示。失败原因、逐文件／附件结果、效果未知等证据在原位置保持可达；
      两种状态的链接和精确任务返回上下文保持，无关联记录不出现准备区域。
- [ ] 桌面与 390px 窄屏中短句和按钮清晰可读、正常换行；无需布局／样式改造。
- [ ] 差异限定为上述前端文案、直接受影响既有用例及本 Task 状态／交接。

### Required Tests

T2：只改一个前端区域的静态文案，不改变权限、Storage、配置、schema、并发、执行或恢复规则。
测试分工遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。

**Developer — affected tests**

在 `web/` 执行：

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx
npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx
npx prettier --check src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx
```

原入口测试覆盖准确摘要关联、Task Center 返回参数和已结束只读分支；仅调整必要断言。
在仓库根执行 `python3 scripts/check_governance.py`、`git diff --check`。
报告实际结果与候选 SHA，不承担全仓回归。

**B — independent acceptance**

审查固定 Task Base..候选完整差异；独立执行上述受影响用例和文件检查，并在 `web/` 执行：

```sh
npm run test -- run src/features/operations/OrganizeCreationPage.test.tsx
npm run typecheck
```

核对可继续／不可继续／无关联三种详情状态；使用隔离测试数据检查桌面和 390px 的实际呈现，
确认两种短句、按钮及只读／继续边界，沿原链接打开准确摘要并保留返回上下文。
已结束入口前往正确资源库文件页，导航本身不创建或执行工作。
可复用现有测试设施，不引入新浏览器测试框架、后端能力或生产媒体验证。
不要求 Python／Web／E2E 全量、wheel 或 Docker 门禁；纯静态文案没有相应共享运行时影响。
验收实际结果、不可用项及风险如实记录，未执行不记 PASS。

### Non-goals

不改其他详情说明、准备弹窗、四类恢复、按钮名称、路由、后端资格判断、业务文档、
任务状态／统计／结果、权限或执行安全；不做布局／CSS 重设计、重构、下一 Task／Slice、推送或部署。

### Workspace / planning check

仓库 `/Users/songzhidong/mediaflow`，分支 `main`，HEAD 为上方 Task Base。
规划前 `python3 scripts/check_governance.py` PASS；TASK／Git 可写，暂存区为空。
预存 `mediaflow/.DS_Store` 修改，以及未跟踪的 `.DS_Store`、`.explore_adapter_block.py`、
`.mgmt.log`、`.t*.log`、`15`、各目录系统元数据和 `output/` 调查材料原样保留，
不进入规划检查点。规划只修改本文件，未实施产品修复或运行产品验收。

激活前 HEAD 为上述规划检查点，分支仍为 `main`，暂存区为空；预存脏文件与未跟踪材料
保持原样。激活前治理检查 PASS；本次仍仅修改 TASK.md，不改变 SLICE／Roadmap／Progress。

### Developer Completion Report

**候选检查点：** 本提交，`Task Base 7b6cadd0..` 之上的实现提交；分支 `main`。
状态 READY FOR B REVIEW。

**变化：**

- `web/src/features/operations/OperationsLanding.tsx` 的 `RunDetailFacts`“文件整理准备”区域按
  `run.filesPreparation.continuable` 只显示约定单句：可继续为“查看整理摘要，确认后执行。”，
  已结束为“本次整理已结束。如需再次整理，请从文件页发起。”。原“本次整理工作已结束…”、
  “原计划摘要保留为只读历史…”及“需要再次整理其中的文件…”长说明删除。
  标题、区域语义、三个链接的显示条件／名称／路径／`discoveryId`／`resourceLibraryId`／
  `returnOps`／`organize` 参数、无 `filesPreparation` 时不显示区域，以及按钮行为均未改动。
- `web/src/features/operations/OperationsInventory.test.tsx` 两个原入口用例更新受文案影响的
  可见文字断言：新增两种短句可见、被删长句不可见的检查，保留精确摘要关联、Task Center 返回
  参数、已结束无“继续整理”及只读摘要跳转断言，并补上既有“从文件页重新发起”链接的
  `resourceLibraryId=source` 检查；未新增测试体系或入口。

**受影响检查（cwd `web/`，Node/Vitest 现有工具链，未新增依赖）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/features/operations/OperationsInventory.test.tsx` | 1 文件通过，40/40 测试通过，用时约 4s（无 skip） |
| `npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx` | 通过，无输出 |
| `npx prettier --check` 同两文件 | 首次因新断言换行不符报 1 文件；同文件 `prettier --write` 后复查通过 |
| 仓库根 `python3 scripts/check_governance.py` | PASS |
| 仓库根 `git diff --check` | 无输出 |

**未执行（B 范围）：** `OrganizeCreationPage.test.tsx`、`npm run typecheck`、全量 Web／Python／E2E、
wheel／Docker 门禁，以及桌面与 390px 实机视觉核对。差异为单区域静态文案，不改变
权限、Storage、配置、schema、并发、执行或恢复规则。

**剩余风险：** 窄屏换行与整体观感仅有既有 CSS（`p` 单行短句）推断，未由 Developer 实机截图验证；
`web/tests/e2e/operations-inventory.python.spec.ts` 仅通过链接名称与目标弹窗文案断言，
未匹配本次删除的说明段落，但 Developer 未运行该 E2E。

**工作区：** 预存 `mediaflow/.DS_Store` 修改及未跟踪的 `.DS_Store`、`.explore_adapter_block.py`、
`.mgmt.log`、`.t*.log`、`15`、`output/` 调查材料保持原样，未进入本检查点；未推送、未发布。

### B Review Result

待独立验收。PASS 后记录准确 Base..Head 与实际结果，恢复紧凑的无活动实施通知；
不关闭或修改任何 Slice，不规划授权范围之外的后续工作。
