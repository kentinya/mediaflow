# NO ACTIVE IMPLEMENTATION TASK

以下为用户于 2026-11-11 授权的独立修复**规划草案**，尚未授权实施；不启动 Developer
或其他角色／代理，不修改产品代码。实施授权后再移除此通知，保留同一 Task ID／Base／目标。

上一独立修正 PATCH-20261111-1 已 B PASS，Reviewed Head 为
`09f55d4be864410a28d22bea125ef4432aceb88c`；范围、原失败与实际验收保留在
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/d1631be651eefc5ed9c0b1bb80dcb195cf921cda/TASK.md)。
Slice54 的 Base、接受 Head、PASS / CLOSED 及 Roadmap／Progress 保持不变。

# Task PATCH-20261111-2 — 四类恢复可确认计划下移除重复分析按钮（规划草案）

Authority: 用户明确指出元数据恢复保存选择后，“确认整理”下方仍有
“继续此条目的安全分析”，并要求规划四类恢复的独立修复。按
[Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)
纠正现有动作呈现，不重开已接受 Slice。B 经验见
[Task Planner / Reviewer](docs/agent-experience/task-planner-reviewer.md)。

```text
Task ID: PATCH-20261111-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: df44b82f9c184e1598a3a97a680d7e565310370a
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: NOT AUTHORIZED — PLANNING ONLY
```

规划前 `python3 scripts/check_governance.py` PASS。工作区 `/Users/songzhidong/mediaflow`，
分支 `main`，HEAD 为 Task Base，暂存区为空，工作区／Git 可写。预存
`mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、调查脚本、日志、`15`、`output/`
材料保持原样，不进入本 Task 检查点。本轮仅修改根 Task 规划，不读取私有配置或用户媒体。

## Goal

用户在任务中心处理识别／元数据／分类／冲突问题，保存合法选择并完成分析后，检查精确
计划并确认整理；已有可确认计划时，其下方不再出现独立“继续此条目的安全分析”按钮。
元数据同时覆盖已有候选选择与标题／年份／类型修正搜索。保存后重新分析仍是必要流程，
正常操作不增加第二次分析点击；异常时仍能从原条目安全完成后续步骤。

实际缺口：`TaskItemRecoveryPanel.saveDecision` 保存成功后已用新 checkpoint 调用
`continueAt`，但 full-mode 的独立按钮只判断 `owesRecoveryAction && permitted.has("retry")`。
`ProcessingCheckpointService._actions` 在决定已保存和零变更 WAITING_CONFIRM 时都可能提供
`retry`，所以存在可确认摘要时仍显示重复入口。再次请求可能使旧计划退为历史并重新排队。
该后端能力本身仍用于未受理分析或确需更新计划，不能通过删除 `retry` 能力修复显示问题。

适用要求：`REQ-RECOVERY-006/007/009`、`V2-OPS-007/008/016`、`V2-TASK-003/014`；
完整旅程为 [Tasks, results and per-item recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)
和 [Task Center §4](docs/task-center-page-spec.md#4-四类恢复决定--分析--摘要确认--真实结果)。
沿用 [Architecture recovery contract](docs/architecture.md#tasks-results-and-processing-recovery)。
这些规则要求合法分析及明确执行确认，不要求成功摘要旁常驻第二个分析按钮。

## Implementation Scope

主要修改 `web/src/features/operations/TaskItemRecoveryPanel.tsx` 的任务中心 full-mode
动作显示、必要的请求状态处理及直接受影响测试。仅在需要保持同一条目请求生命周期时，
最小调整 `task-item-recovery-session.tsx`；不引入第二套恢复流程或持久化模型。

1. 先补充用户所述缺口的用例：后端仍提供 `retry`，但原条目已存在当前可确认计划，
   明确断言摘要／确认可用且独立分析按钮不存在。不能只删除测试夹具里的 `retry`。
2. 按当前条目的后端分析就绪状态、当前摘要及请求状态决定是否还需要独立分析动作；
   保持持久摘要优先于旧本地缓存。分析就绪后保留生成／检查摘要与明确确认；当前摘要
   可确认、已经确认或分析已受理／进行中时，不再引导重复分析。不能只按按钮文案、
   本地“曾保存”标记或任意历史摘要判断，也不能一律隐藏所有 `retry`。
3. 保留真实未完成分析的恢复：决定保存成功但 `queue_full`／`capacity_full` 拒绝时，
   说明决定已保存、分析未受理、没有文件变更，并提供就近明确的分析重试入口。只提交
   当前合法 checkpoint 的 continuation，不再次保存决定；刷新／重开后仍可从持久状态继续。
   响应未知先保持锁定并读取原状态；若读回已就绪／有可确认摘要，直接进入摘要步骤。
4. 摘要确实失效且后端要求重新分析时，保留必要的合法更新入口；读取失败不把旧摘要
   当可确认，过期／无权／未知效果不自动重发。不同条目独立，不因 A 就绪隐藏 B 的必要操作。
   新四类阻塞仍回到对应合法决定；纯技术失败保持现有只读边界。
5. 回归共用组件的 Files `mode="decision"`：保存与分析、失败补救及父弹窗的一次最终确认
   保持；不重做其布局或新增确认。补齐受影响测试并按下面计划交付检查点。

后端 endpoint／checkpoint 能力／Task 引擎／准入、权限、配置 pin、执行确认及 Storage
行为保持。若实际实现必须改变这些契约，先返回 B 重新评估范围与 Test Level，不在本 Task
内按纯呈现修改静默扩张。产品文档没有要求常驻该按钮，本修复不改 Requirements／
Product Experience／Architecture／SLICE／Roadmap／Progress。

## Acceptance Criteria

- [ ] 用户原场景：元数据选择保存 → 分析 → 当前计划“确认继续整理 N 项”可用，下方无
      “继续此条目的安全分析”；刷新、关闭重开／重新认证读回同一计划后也不回到重复入口。
- [ ] 识别、元数据候选／修正、分类、冲突采用相同成功态规则；一次合法保存仍衔接一次
      分析请求，轮询／重开不自动发出额外 continuation 或执行。分析受理不冒充整理成功。
- [ ] 决定保存但分析未受理时，保留已保存决定并可显式仅重试分析；队列恢复后能到摘要
      和明确确认，不要求重新选择／重复保存。请求仍在途或结果未知时不能重复提交。
- [ ] 真实失效计划保留后端允许的更新步骤；过期 checkpoint、读取失败、权限拒绝有准确
      原因／持久状态／下一步，既不拿旧计划执行，也不自动重放。无效决定不触发分析。
- [ ] 已确认／已完成／效果未知及纯技术历史不获得新重放入口；成功兄弟不重跑，其他
      尚需决定或分析的兄弟仍可处理。覆盖／源清理仍需原精确摘要的明确许可。
- [ ] Files 共用决定面板仍完成保存／分析与原精确子集的一次确认，Task 身份、原 pin、
      已有未知请求核对和结果关联不变；桌面／390px 无残留空操作区，异常恢复按钮可达。

## Required Tests

执行分工遵循 [Workflow §6](docs/development-workflow.md#6-test-levels)。本轮为 T3：
验证跨 UI／真实 API／Worker 的既有恢复行为，但不改变媒体 mutation、权限或持久化契约；
没有要求全仓回归的共享引擎变更。若风险边界改变由 B 升级测试，不转交 Developer 全量门禁。

### Developer — affected tests

在既有测试中加入上述成功／拒绝／未知／失效及兄弟隔离案例；原有保存失败、年份搜索、
确认丢响应、旧本地摘要不能覆盖持久已确认记录的断言保持。

cwd `web/`：

```sh
npm run test -- run src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/OrganizePlanConfirmation.test.tsx src/features/operations/RunDetailTabs.test.tsx
npm run typecheck
npx eslint src/features/operations/TaskItemRecoveryPanel.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npx prettier --check src/features/operations/TaskItemRecoveryPanel.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
```

新增／修改其他文件时加入其直接受影响测试与对应 lint／format 检查。如修改原生 E2E／
harness，先 `npm run build`，再用下一节的对应原生命令运行本轮新增／修改用例；不要求
Developer 跑完整 Python／Web／E2E 或交全量证据包。仓库根执行 `git diff --check`。

### B — acceptance and regression

独立审查完整 `Task Base..candidate`，先复现原按钮缺口并检查新条件没有吞掉异常入口。
重跑上述受影响 Web 测试；cwd `web/` 执行 `npm run lint`、`npm run format:check`、
`npm run typecheck`、`npm run build`，用本次新产物进行真实 Python／临时 SQLite／Worker
浏览器验收。复用现有原生恢复 helper，在四类摘要确认前增加“无重复按钮”和无额外
continuation 的断言，另补队列拒绝后的重试及当前／失效摘要状态覆盖；新用例名含 Task ID。

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'PATCH-20261111-2|native recognition recovery|native Metadata|native Classification|native conflict|policy-permitted overwrite'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts --grep 'ten per-file|real destination conflict|missing metadata candidate|unknown original submission'
```

仓库根回归现有后端的队列拒绝／同 Task 摘要／原计划绑定约定：

```sh
.venv/bin/python -m unittest tests.test_manual_task_engine.ManualTaskDiscoveryTests.test_continue_at_full_capacity_keeps_the_saved_decision_and_waits tests.test_manual_task_engine.ManualTaskDiscoveryTests.test_native_metadata_candidate_confirms_on_the_same_task tests.test_manual_task_engine.ManualTaskDiscoveryTests.test_native_confirmation_is_bound_to_the_reviewed_preview
python3 scripts/check_governance.py
git diff --check
```

原生验收含元数据候选、元数据修正和另外三类的保存 → 分析 → 无重复按钮 → 明确确认 →
真实结果，以及准备后刷新／重开、拒绝后重试和未知响应核对。抽查桌面／390px 的成功
摘要和异常提示。Provider 使用本地假服务，Storage 使用临时根；不访问用户媒体。
不机械运行全仓 Python／Web／E2E 或 Docker／外部服务矩阵；无运行时／打包路径变更，
本轮无需 wheel／Docker 验收。记录精确候选、实际命令／结果、失败／跳过及本机证据位置。

## Non-goals

删除重新分析能力或后端 `retry`、保存即执行、自动队列重试、通用技术失败恢复、
重设计任务中心／Files 弹窗、改引擎／schema／权限／Storage／Provider、跨任务恢复、
批量重放／万能回滚、修改 Slice 接受边界、下一 Task／Slice 规划、推送／发布／部署。

## Developer Completion Report

未实施。后续交付记录精确检查点、`READY FOR B REVIEW`、行为／文件、受影响测试实际
结果及剩余风险；完整验收由 B 执行。

## B Review Result

尚未开始。独立审查实施候选后填写 Reviewed Base..Head、PASS／FIX REQUIRED、实际验收
及剩余阻塞；PASS 后结束该独立修复，恢复精简无活动实施 Task 通知，不关闭任何 Slice。
