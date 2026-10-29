# Task PATCH-20261029-1 — 修复自动化执行记录的预启动失败响应

Authority: 用户指定的独立小版本 bug；本会话先由助手按用户明确要求代行 B 规划，随后用户
明确授权实施该草案。遵循 [Development Workflow](docs/development-workflow.md) 的安全、
测试分工、Git 和独立审查规则。本 Task 不重新开启大版本 Slice，不自动启动其他 agent。

Slice46 保持 PASS / CLOSED。其原始 Base、已验收实现和关闭记录仍以
[SLICE.md](SLICE.md)、[Roadmap](docs/roadmap.md) 和 [Progress](docs/progress.md) 为准。

## Task PATCH-20261029-1 — 修复自动化执行记录的预启动失败响应

```text
Task ID: PATCH-20261029-1
Task Type: STANDALONE MINOR BUG
Status: READY FOR B REVIEW
Parent Slice: NONE
Task Base: a9d5c5f1914f5590f0ebe1f60e58d7f91ca56381
Planning HEAD: 9092f7df03dafdd8929e75313db18dc12fd44d7d
Difficulty: Low
Test Level: T3
Planner: 当前助手代行 B — 用户明确授权
Implementation: COMPLETE — READY FOR B REVIEW
```

Task Base 保留已确认缺陷的真实源码基线；Base 到 Planning HEAD 只有先前的 TASK.md
规划提交，没有产品或测试代码变更。规划历史保留在 Git，本草案不授权启动其他角色或实施。

### 用户结果与真实入口

用户进入“自动化 → 执行记录”，能够同时查看正常记录和正式整理开始前的失败记录，
看到真实失败阶段、原因及下一步动作。刷新仍是只读查询；失败记录不会使整页不可用。
无记录时显示正常空状态；真实读取错误保留错误状态及同一只读查询的刷新入口。

现有入口：`GET /api/v1/operations/automation/records?limit=20`。
正常 Scheduler 产生 Job，Worker 在创建正式 Task 前检查来源目录；目录不可用可产生
`scope_root_missing` 等结构化失败。当前 API 的预启动失败分支只返回
stage/category/nextAction/statement，缺少前端必需的 itemsTruncated/unavailable，
导致严格解析器抛异常，整个 records 页被显示为“执行记录不可用”。

适用约定：`V2-AUTO-001/005/006`、`UX-002/003/005/007`、`REQ-API-002/003`，以及完整的
[CURRENT Automation journey](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
和 [CURRENT read-model contract](docs/architecture.md#current--v2-automation-workspace-and-consumed-engine-settings-slice43-pass--closed)。

### 实施范围与步骤

1. 只补齐 `mediaflow/interfaces/service_api.py` 中
   `_automation_record_failure_stage` 的已证实预启动失败返回分支：
   `items=[]`、`effects={none:0, known:0, uncertain:0, partial:0}`、
   `itemsTruncated=False`、`unavailable=False`。保留原阶段、类别、说明和下一步动作。
   复用既有响应结构，保持前端严格校验，不增加新的抽象或执行机制。
2. 在现有隔离测试 fixture 中，通过正常 Scheduler/Worker 产生无正式 Task 的来源目录
   预检查失败，再调用真实 records API。断言完整响应、真实失败原因、没有媒体效果，
   以及查询/刷新前后工作与授权数量不变。扩展既有混合记录用例，覆盖已持久化的
   `unattended_execution_authority_missing` 历史记录，仅查询、不重新执行。
3. 将上述真实 API 响应交给现有 Web fetch/严格 decoder/records 页面，验证失败行与
   一条真实正常或无工作完成记录共同显示。允许复用或补充最小测试 fixture 连接，
   不以手工修正过的 JSON 代替真实后端响应，不添加产品探测入口。验证刷新只重复读取，
   页面不增加执行控制。复用既有空历史、正式 Task 失败/证据不可读、拒绝及格式错误回归。
4. Developer 完成受影响测试和必要静态检查后，提交精确候选 SHA 与简短报告，状态交为
   READY FOR B REVIEW；由 B 独立审查完整 Task Base..candidate 并执行验收。

### 验收条件

- [ ] 真实调度及 Worker 的来源目录预检查失败产生完整、可被严格前端解析的 failureStage；
  无正式 Task、无逐项结果、无媒体效果的事实和原失败原因均保留。
- [ ] 现存预启动失败记录通过查询时的投影即可正常显示，保留原持久化结果和执行上下文。
- [ ] 正常与失败记录混排时均可见，查询总数和筛选保持真实；刷新不新增工作或执行授权。
- [ ] 健康空历史、正式 Task 失败/部分完成、证据不可读与真实 401/403/格式错误仍能区分。
- [ ] records 维持只读、有界和脱敏；原恢复归属、重试条件、权限及不可重放约束保持有效。
- [ ] 新增关键回归在 Task Base 上能复现失败，在修正候选上通过；证据包含实际命令和结果。

### 测试分工

Developer 只运行本轮新增/变更及直接受影响测试，从仓库根目录执行：

- `.venv/bin/python -m unittest tests.test_automation_workspace_read_model`
- `.venv/bin/python -m unittest tests.test_v2_automation_run_once`：在该既有 fixture/module
  内加入正常调度的预启动失败回归，避免另建重复测试体系。
- 在 `web/`：`npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx`
- `.venv/bin/ruff check mediaflow/interfaces/service_api.py tests/test_automation_workspace_read_model.py tests/test_v2_automation_run_once.py`
- `.venv/bin/ruff format --check mediaflow/interfaces/service_api.py tests/test_automation_workspace_read_model.py tests/test_v2_automation_run_once.py`
- 在 `web/`：`npx prettier --check src/features/operations/AutomationWorkspaceReadModel.test.tsx`
  及 `npx eslint src/features/operations/AutomationWorkspaceReadModel.test.tsx`。
  如增加最小测试连接文件，对该文件补同类检查并在交接报告写明精确命令。
- `git diff --check`。Developer 不承担全仓 Python/Web/E2E 或发布矩阵。

B 对精确候选独立检查关键复现、完整差异和证据，运行：

- `.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_v2_automation_run_once`
- 在 `web/`：`npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx src/entities/operations/automation.test.ts src/shared/api/api-client.test.ts`
- 在 `web/`：`npm run typecheck`、`npm run build`。
- 在 `web/`：`npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts --grep 'records tab|records page traverses|healthy empty history'`
- 精确输入一致时可说明并复用 Developer 结果，不机械重复；缺失的验收由 B 补齐。
  生产改动仅为只读响应补字段，无权限、写入、schema 或并发改动，未安排 T4 全仓门禁。

### 边界与治理状态

本 Task 只规划本地修复。资源库编辑的部署身份问题、远端操作、部署、推送、历史清理、
数据库迁移、执行授权/调度行为修改及无关重构均不在范围内。

现行流程和校验器已支持 `Task Type: STANDALONE MINOR BUG`、`Parent Slice: NONE`，
并继续检查合法状态、完整且存在的祖先 Base，以及保留 Slice/Roadmap 的一致性。
本 Task 已在用户明确授权后转为正式 Task 头部并进入 READY FOR B REVIEW；不挂靠已关闭
Slice，不使用治理豁免，也不因流程同步自动启动其他 agent 或改变 SLICE/Roadmap/Progress。

B 给出 PASS 或 FIX REQUIRED。当前 Developer 报告如下，B 验收结果仍为 PENDING。

## Developer Completion Report

**READY FOR B REVIEW — 实施完成，未自行声明 Task PASS / Slice CLOSED。**

- Task Base：`a9d5c5f1914f5590f0ebe1f60e58d7f91ca56381`。
- 产品/受影响测试 checkpoint：`36e4634ea3a6b6ccb339aaa62f265f464e5f70b3`。
- 本报告提交为 report-only successor；产品源码/测试输入不变，B 可复核 checkpoint 后
  以本报告为交接说明。
- 未 push、未部署，未修改 SLICE/Roadmap/Progress。预存 untracked OS/log/参考图/测试产物
  保持原状且未纳入 checkpoint。

### 已实施修复

1. `mediaflow/interfaces/service_api.py::_automation_record_failure_stage` 的已证实预启动
   失败分支补齐 `items=[]`、`effects` 全零、`itemsTruncated=False`、`unavailable=False`；
   保留原 `stage/category/nextAction/statement`，无执行、权限、schema 或并发改动。
2. `tests/test_v2_automation_run_once.py` 用既有真实 fixture 启动 production
   `IntervalScheduler` + `AutomationWorker`：健康空 scope 产生 completed/no-work Task；
   缺失 scope 在正式 Task 前产生 `scope_root_missing` Job 失败。随后调用真实
   `GET /api/v1/operations/automation/records`，断言完整 failureStage、真实原因、零媒体效果、
   无正式 Task，并在刷新前后核对 Task/Job/grant/discovery 数量和 Active revision 不变。
   同一用例把真实 API 页面仅对生成 UUID/时间做稳定替换后与 Web fixture 相等比较。
3. `tests/test_automation_workspace_read_model.py` 扩展现有混合记录用例，验证已持久化的
   `unattended_execution_authority_missing` 历史记录仅查询即得到完整同形 failureStage。
4. 新增 `web/tests/fixtures/automation-records-prestart.json`，由上述真实 API 响应生成；
   `web/src/features/operations/AutomationWorkspaceReadModel.test.tsx` 将其交给现有 fetch/
   严格 decoder/records 页面，验证失败行与真实 completed/no-work 行共同显示，刷新只重复
   GET 读取，页面不出现执行/重试控制。既有空历史、正式 Task 失败、证据不可读、拒绝和格式
   错误回归保持通过。

基线复现：在修正前运行新增的 Scheduler/Worker 用例，真实响应中的 `failureStage` 仅有
`stage/category/nextAction/statement`，缺少 `items/effects/itemsTruncated/unavailable`，
断言失败；补齐后同一用例通过。未构造产品不存在的入口，也未以手工修正 JSON 代替后端响应。

### 实际验证

| 命令（cwd） | 实际结果 |
| --- | --- |
| `.venv/bin/python -m unittest tests.test_automation_workspace_read_model`（repo root） | 35 / OK |
| `.venv/bin/python -m unittest tests.test_v2_automation_run_once`（repo root） | 24 / OK |
| `.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_v2_automation_run_once` | 59 / OK，6.9s |
| `npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx`（web/） | 9 / 9 passed |
| `.venv/bin/ruff check mediaflow/interfaces/service_api.py tests/test_automation_workspace_read_model.py tests/test_v2_automation_run_once.py` | All checks passed |
| `.venv/bin/ruff format --check` 同上三文件 | 3 files already formatted |
| `npx prettier --check src/features/operations/AutomationWorkspaceReadModel.test.tsx tests/fixtures/automation-records-prestart.json`（web/） | All matched files use Prettier code style |
| `npx eslint src/features/operations/AutomationWorkspaceReadModel.test.tsx`（web/） | PASS |
| `npm run typecheck`（web/） | PASS |
| `git diff --check` | PASS |

### 剩余风险与 B 交接

- 本轮只执行 Task 指定的 Developer 受影响验证；完整 T3 验收、Web build、real-Python
  Playwright records/empty-history 矩阵及全仓 Python/Web 门禁仍由 B 在精确候选上执行。
- Web fixture 对生成 UUID/完成时间做了稳定替换；Python 同一用例逐字段比较真实 API 页面，
  因此不存在手写旧 JSON 冒充后端响应。若 API 响应再变化，该跨边界用例会失败并要求更新
  fixture。
- jsdom 测试仍输出既有 `window.scrollTo not implemented` 提示，不影响 9/9 结果；本 Task
  未新增/隐藏失败或放宽断言。远端部署身份、调度/授权行为、数据库迁移和无关重构未触碰。
- B 应按本 Task 的验收条件决定 PASS 或 FIX REQUIRED，并重新评估该独立 minor bug 的完成；
  Developer 不规划下一 Task、不关闭 Slice、不自动 push/发布。

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Acceptance runs: not yet run by B
Task blockers: none recorded by Developer
Next: B reviews Task Base..36e4634 plus this report-only successor and runs assigned acceptance
```
