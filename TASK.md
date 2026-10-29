# NO ACTIVE IMPLEMENTATION TASK

当前仅有下述独立小版本 bug 的规划草案。用户本轮明确授权“你代替 B 规划 Task”，
未授权启动 Developer、子 agent 或实施；不得将本草案视为开工指令。

Slice46 保持 PASS / CLOSED。其原始 Base、已验收实现和关闭记录仍以
[SLICE.md](SLICE.md)、[Roadmap](docs/roadmap.md) 和 [Progress](docs/progress.md) 为准。

## Task PATCH-20261029-1 — 修复自动化执行记录的预启动失败响应

Authority: 用户指定的独立小版本 bug 规划；本会话助手按用户明确要求代行 B 规划职责。
遵循 [Development Workflow](docs/development-workflow.md) 的安全、测试分工、Git 和独立审查规则。
本次不重新开启大版本 Slice，不自动实施或启动其他 agent。

```text
Task ID: PATCH-20261029-1
Task Type: STANDALONE MINOR BUG
Status: DRAFT — PLANNING ONLY
Parent Slice: NONE
Task Base: a9d5c5f1914f5590f0ebe1f60e58d7f91ca56381
Planning HEAD: 9092f7df03dafdd8929e75313db18dc12fd44d7d
Difficulty: Low
Test Level: T3
Planner: 当前助手代行 B — 用户明确授权
Implementation: NOT STARTED / NOT AUTHORIZED BY THIS PLAN
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
本草案仍保留“无活动实施 Task”状态；只有用户授权实施后，才改为正式 Task 头部及
`Status: PLANNED` 并重新运行治理检查。不挂靠已关闭 Slice，不使用治理豁免，
也不因流程同步而自动实施本 bug、启动其他 agent 或改变 SLICE/Roadmap/Progress。

后续交接必须包含 Task Base、候选完整 SHA、实际测试结果/限制和剩余风险；B 给出
PASS 或 FIX REQUIRED。当前尚无 Developer 完成报告或 B 验收结果。
