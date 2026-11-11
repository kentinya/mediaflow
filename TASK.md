# NO ACTIVE IMPLEMENTATION TASK

最近独立修复 **PATCH-20261111-2 — 四类恢复可确认计划下移除重复分析按钮** 已由 B
于 2026-11-11 验收 **PASS**，无剩余 Task 阻塞。

- Reviewed Base: `df44b82f9c184e1598a3a97a680d7e565310370a`
- Reviewed Head: `c26557f4c1a2404a281f02e735c40032d9b5a21c`
- [固定 B 验收记录](https://github.com/kentinya/mediaflow/blob/aff254ce0e3dc8b47714b197a7023509e6cc5f66/TASK.md#b-decision--patch-20261111-2-pass)：完整范围、实际结果、原始失败、证据位置及验证限制。
- [原 Task 与开发指导](https://github.com/kentinya/mediaflow/blob/6293817180291c3208e997624878d2413a4799de/TASK.md)：授权、目标、验收和 Developer 交接。
- 上一独立修复 PATCH-20261111-1 的 [固定 B 验收](https://github.com/kentinya/mediaflow/blob/d1631be651eefc5ed9c0b1bb80dcb195cf921cda/TASK.md) 保留原范围与结果。

当前行为见 [恢复旅程](docs/product-experience.md#tasks-results-and-per-item-recovery) 和
[任务中心四类恢复](docs/task-center-page-spec.md#4-四类恢复决定--分析--摘要确认--真实结果)。
独立修复不重开 [Slice54](SLICE.md)，其 PASS / CLOSED、原始 Base／接受 Head、
Roadmap／Progress 及延期保持。下一大 Slice 由 A 单独选择；当前没有授权中的实施 Task。

---

## 规划草案 — PATCH-20261111-3：精简任务详情“文件整理准备”说明

本草案仅落实用户“规划一个修复Task”的授权，不授权实施、启动其他角色或推送。
获得实施授权后再移除顶部无活动实施通知，正式启用以下 Task；原 Base 保持不变。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

```text
Task ID: PATCH-20261111-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 7b6cadd050591c339589d042235013ca9ff1f26d
Difficulty: Low
Test Level: T2
Planner / Reviewer: B
Implementation Authorization: NOT AUTHORIZED — PLANNING ONLY
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

### Developer Completion Report

待实施授权及实际开发后填写：候选 SHA、READY FOR B REVIEW、变化、受影响检查实际结果和剩余风险。

### B Review Result

待独立验收。PASS 后记录准确 Base..Head 与实际结果，恢复紧凑的无活动实施通知；
不关闭或修改任何 Slice，不规划授权范围之外的后续工作。
