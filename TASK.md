# Task PATCH-20261120-3 — 手动整理提交自动核对

用户于 2026-11-20 授权激活独立 Task，待 Developer 开始实施。
[上一独立修复的 B 验收](https://github.com/kentinya/mediaflow/blob/e5fd939f17bf43fcff55d0fed66ec13d644868a6/TASK.md#patch-20261120-2--b-验收-pass)

```text
Task ID: PATCH-20261120-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: FIX REQUIRED
Task Base: 20df0749e3d949d378969f34bc64bdb860a6fadf
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-20
```

规划基线为 `mediaflow/main`，初始工作区及暂存区干净，工作区和 Git 可写，治理检查通过。
依据 [Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)、
任务详情可读性 `V2-UX-006` 和手动整理 `V2-OPS-018/019`。Slice 56 的历史验收保留原检查点。
[任务中心现行体验](docs/task-center-page-spec.md) · [Files 整理旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)

### 目标与现状

用户确认一批文件后，系统负责查明服务端是否受理。正常提交直接打开原任务，断线重连或刷新后系统接着查询。
查看任务详情时，用户先看到进度、文件结果和待处理项。「原整理提交」是当前默认展开的并列卡片，会重复展示每批的文件名和状态。
Files 整理弹窗及任务中心继续整理共用的组件把原提交身份保存在内存，丢响应后由用户点按钮查询。
任务中心逐项恢复的最终确认已经保留了原请求身份，也以人工入口触发查询。
[任务详情卡片](web/src/features/operations/OperationsLanding.tsx#L1912) · [手动整理查询](web/src/features/operations/ManualOrganizeDialog.tsx#L705) · [逐项恢复确认](web/src/features/operations/TaskItemRecoveryPanel.tsx#L928)

### 实施范围与步骤

1. **先保存再提交。** Files 手动整理及任务中心的继续整理、逐项恢复最终确认，在发请求前按当前实例、登录主体和原工作上下文
   保存本次确认的原摘要 ID、版本、文件选择和覆盖／清理选项。以逐项恢复的保留机制为基础，支持同一浏览器的刷新、重开原工作
   和同一主体重新认证。核对认证失效、凭据更新与主动切换账号的清理行为，仅在重新验证实例和主体后恢复读取。
   对保留条目做容量与输入校验，只保存身份和读取所需字段。保存失败时保留选项，在原入口说明本次提交未发送。
2. **自动读取原确认。** 正常响应按服务端返回的准确 Task ID 交接。确认请求响应丢失、超时、格式错误或受理响应缺少可用 Task ID
   时，通过现有受理查询发起有界、带退避的只读检查。恢复连接、重新认证或重新打开原工作后接着查，避免同一确认并发查询。
   每一批只使用自己保存的摘要与选择，另一批重分析、切换任务或切换账号都不会错用原请求。原窗口仍在时，确认受理后打开对应任务。
   异步结果在原任务相关入口以「已受理 · 查看任务」反馈，避免把操作中的用户带离其他页面。
3. **按证据反馈和恢复。** 待确认期间只显示一行状态。服务端明确拒绝原请求且能确认未受理时，说明原因并保留选择供用户刷新方案后确认。
   受理查询暂时没有记录、查询失败或证据不匹配时保留原确认，尤其覆盖原 POST 仍在途的情形。若连接已恢复、服务端暂无受理记录，
   用户需要重新发出时，仅在原摘要和原选择仍有效且现有[原子准入检查](mediaflow/infrastructure/sqlite_runtime.py#L10296)可安全去重的情况下，
   提供一次显式确认同一批的动作。竞争中的重复或过期响应回到原确认的查询，按查询证据更新状态。等待期间的自动恢复只发查询。
   已受理、部分完成和效果未确认分别按各自的证据呈现。
4. **收回详情中的整块卡片。** 移除「原整理提交」及本旅程内用于核对执行受理的人工按钮。保留持久受理记录和现有查询契约。
   已知历史任务从原入口查看同一任务的进度、文件结果和逐项证据。与本次正在查询或刚查明的提交关联时显示一行反馈，
   无待确认记录时正常打开任务无需逐批发查询。需要用户决定的覆盖、清理、取消及逐项恢复继续走既有授权入口。

### 验收条件

- [ ] 正常确认一次，直接打开服务端返回的任务。完成详情没有「原整理提交」、重复文件清单或人工核对按钮。进度、文件结果、
  失败原因和合法动作在桌面及 390px 窄屏可读。旧版已受理任务可按原 ID 查看状态和逐项证据。
- [ ] 服务端已受理但丢弃响应，原弹窗内以及刷新、重新认证或重开原工作后均自动读取原确认。查到后关联同一 Task ID，
  原提交总数为一次。后台查证期间写请求为零。区分「已受理」和文件实际成功。
- [ ] 同一任务先确认 A，再确认 B，丢弃 B 的响应并更新未确认兄弟文件的方案后，自动查询仍使用 B 的原摘要、版本、选择和效果选项。
  A 和 B 各受理一次，未确认兄弟、成功项和效果不确定项的执行次数符合原有规则。
- [ ] 初次查询早于原请求提交且没有记录时，界面显示「暂未确认」。随后完成原请求时能自动收敛到同一 Task。
  覆盖明确拒绝、始终未到达服务端后的合法显式确认、原延迟请求与显式确认并发、摘要变更、权限变化及查询失败。
  用持久记录验证竞争请求对同一批只受理一次。查询异常、证据不一致及主体切换时保留正确的阻断与隔离。
- [ ] 账号切换、晚到响应、不可用或损坏的浏览器保留记录均有针对性测试。记录提供者不会发布 token 或可复用执行授权。
  身份与原工作上下文关联失败时，用户可读到真实状态并在原入口恢复。

### 测试与分工

**Developer 受影响检查**

- 在 `web/` 运行 `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/task-item-recovery-confirmation-session.test.ts src/features/operations/RunDetailTabs.test.tsx` 和 `npm run typecheck`。新保留或调度模块的单测随对应模块执行。
- 根目录运行 `.venv/bin/python -m unittest tests.test_manual_organize_execution.CurrentSourceManualOrganizeTests.test_task_center_reconciles_the_original_submission_for_its_submitter_only tests.test_manual_organize_execution.CurrentSourceManualOrganizeTests.test_concurrent_execute_consumes_authority_once`。
  对延迟受理与合法重复确认进行隔离服务回归，核对权限、受理次数和文件变更次数。提交候选前运行 `git diff --check`。

**B 独立验收**

- 审查 Base 到候选检查点的完整差异。在 `web/` 运行 `npm run build` 和 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts`。
  复用真实 Python、SQLite、Worker 与请求拦截，验证丢响应后重开、同任务第二次确认、兄弟方案变动与受理延迟。
  用 Base 受理过的隔离数据重开任务，验证历史详情及受理记录可读。检查桌面和窄屏的实际呈现。
- 在 `web/` 运行 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g 'native .*recovery'`，
  在同一真实服务链路覆盖逐项恢复的确认交接，并对其中一个恢复入口注入丢响应，检查自动读回同一 Task 与唯一文件效果。
- 执行[适用的 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)，记录候选 SHA、测试结果及实际受理和文件效果计数。

### 边界与交接

本次范围为 Files 手动确认、任务中心继续整理和逐项恢复的最终执行确认。自动化、CLI、其他命令的未知结果、跨设备续查及通用通知属于独立范围。
验收后的现行说明在任务中心页面规范和 Files 整理旅程记录。Developer 交受影响测试和候选 SHA 后，由 B 独立记录 PASS 或 FIX REQUIRED。

### B 独立复核 — 2026-11-20

```text
Reviewed: 20df0749e3d949d378969f34bc64bdb860a6fadf..b1d1c6290fc592bdea70b69f6b1e8a61912f56be
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

任务详情已移除「原整理提交」卡片。生产 Web 构建通过。真实 Python、SQLite 和 Worker 的三个浏览器用例通过，覆盖
Files 丢响应后自动打开原任务、重新打开原任务后自动查询、同一任务的第二次确认按自己的范围查询。
命令见本 Task 的 Playwright 计划，使用 `-g 'an unknown Execute response|a Task reopened after a lost Execute|a second confirmation on the same Task'`。
日志见 `.git/validation-evidence/b1d1c629/patch-b/native.log`。T4 全量验收留待修正候选。

#### 阻塞项 — 逐项恢复提前宣布未受理并停止查询

从任务中心打开有分类问题的文件，选择分类、重新分析、复核摘要，再点击「确认继续整理 1 项」。B 在现有真实浏览器用例中
模拟这次确认的响应丢失和服务端迟到。两次受理查询都发生在原请求到达服务端之前。此时页面显示「本次确认未获受理」，
同时删除原确认记录。随后让同一笔原请求到达真实服务，服务端返回 `202` 和原任务 ID，Worker 完成该文件。
逐项恢复面板把第二次查不到记录当成终态，之后的自动查询失去了原确认。
[逐项恢复自动查询](web/src/features/operations/TaskItemRecoveryPanel.tsx#L711)

#### 本轮开发指导

1. 在 `TaskItemRecoveryPanel.tsx` 复用已有自动查询。只读查询暂无记录时保留原确认，显示「暂未确认」并继续现有退避查询。
   收到可关联的受理记录时清理该次确认并刷新原任务和文件。处理现有人工「重新读取条目后再继续」入口时，
   让最终确认沿用同一套自动查询。该入口仍可服务于其他操作。
2. 逐项恢复的再次确认沿用 Task 当前约定。校验原摘要和选择仍有效，有权限时才允许用户显式确认同一批。
   遇到重复或过期响应继续查询原确认。保留原请求身份直到有确定结果。
3. 在 `operations-inventory.python.spec.ts` 的原生分类恢复旅程中加入迟到用例。
   点击原确认按钮，让真实受理查询连续两次在原请求到达前返回。核对页面仍显示待确认，
   再让原请求到达，验证系统自动显示已受理、仍在原任务，且该文件只执行一次。
   同一测试入口覆盖原请求始终未到达后用户显式确认同一批，以及该确认与迟到原请求竞争时的受理与执行次数。
