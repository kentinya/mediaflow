# Task PATCH-20261030-5 — 执行记录仅保留详情按钮

Authority: 用户明确要求删除自动化执行记录的“打开任务中心运行”和“打开定义设置”，
执行记录页不再提供这两个入口；不迁移到展开详情、菜单或其他位置。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

```text
Task ID: PATCH-20261030-5
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: a7bcd92fb5b40dbf636e5aeab99aafc5db701e39
Difficulty: Low
Test Level: T2
Planner / Reviewer: B
```

## Goal

现有入口为 自动化 → 执行记录；AutomationRecordRow 根据 handoff 中的关联信息，
在操作列额外渲染任务中心/定义按钮。移除这两个入口，操作列仅保留“查看详情 /
收起详情”，展开后继续查看完整结果、失败与逐项效果。收起、筛选、分页及刷新可继续
查看记录，读取失败沿用原有恢复；不增加状态、命令或权限。

## Implementation Scope

1. 删除 AutomationRecordRow 的两个跳转按钮及独占派生值/参数；清理 RecordsTab 和
   AutomationListPage 中仅供这些按钮使用的回调，任务列表自己的定义入口保持原行为。
2. 同步既有组件和桌面/窄屏浏览器用例：即便后端关联信息齐全，收起/展开时均无两个
   入口，摘要行只有一个按钮；失败证据仍可读且展开/收起不提交写请求。
3. 对齐现行需求、完整旅程和架构中的记录页入口表述；API handoff 数据及其他消费者不变。

## Acceptance Criteria

- [ ] 每条执行记录的操作列仅有一个查看详情/收起详情按钮，展开仍可正常切换。
- [ ] 记录页与展开详情均无任务中心/定义跳转按钮或替代链接，无新增执行/恢复命令。
- [ ] 完整时间、结果、失败阶段、逐项效果和下一步不丢失，独立记录、筛选及分页保留。
- [ ] 任务列表自己的定义入口、后端 API/权限/关联数据/执行逻辑、Slice/Roadmap/Progress 不变。

## Required Tests

Developer（cwd `web/`）：
- `npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationRouter.test.tsx`，覆盖关联齐全/无正式 Task 的记录、证据与列表路由。
- `npm run typecheck`；改动 TS/TSX 的 ESLint/Prettier；`npm run build`。
- `npm run test:e2e -- tests/e2e/automation-presentation.spec.ts`，覆盖 1536/390px 的真实页面操作和零写入；查看截图。
- 根目录 `python3 scripts/check_governance.py`、`git diff --check`。

B 独立审查完整 Base..candidate，验收上述范围；从既有真实入口复核折叠前后仅一个按钮、
无相关跳转与完整证据。必要时运行既有 `automation-workspace.python.spec.ts`，不跑无关全仓。
测试与静态/构建累计耗时小于本轮总用时 50%。实现者不自审 PASS，交 READY FOR B REVIEW。

## Non-goals / Workspace

不改变任务中心或定义页自己的入口/能力，不改后端，不引入替代入口、重构、部署或推送。
`main`，初始 HEAD 为 Task Base，无已跟踪文件修改；预存未跟踪文件原样保留，清单在
本机 ignored `.git/validation-evidence/PATCH-20261030-5/baseline.txt`。
前次独立修正的完整验收保留在 `2dd4febccd52ec2ffcbdcef6196aceb35f30bd9c:TASK.md`。
