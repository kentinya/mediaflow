# Task PATCH-20261030-1 — 任务中心八标签统一时间筛选

Authority：用户在发现仅“全部任务”完成简化后，明确要求“其他标签页也改”。本 Task 将同一
创建时间范围交互补齐到其余七页，明确替换上一修正中“其他七视图保留原筛选”的限制；
不改各标签的业务收录范围、任务详情和四类恢复权限。遵循
[AGENTS.md](AGENTS.md)、[Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)
及 [B 角色指南](docs/agent-experience/task-planner-reviewer.md)。
本轮由 B 完成规划并建立 PLANNED checkpoint，交 Developer 实施；不自动启动其他角色/agent。

```text
Task ID: PATCH-20261030-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Authorization: USER-REQUESTED CORRECTION — 2026-10-30
Task Base: e40093aa2400794f4423987658fba3095c7adda5
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

上一独立修正 PATCH-20261029-4 已 PASS；完整 B 记录在 `3e0e7d62:TASK.md`，治理后指针在
`e40093aa:TASK.md`。Slice46 仍为 PASS / CLOSED，其原 Base、Implementation Head、SLICE、
Roadmap、Progress 和延期边界不变。本次不是重新评审或关闭原 Slice。

## Goal and complete journey

用户从侧栏进入任务中心，切换全部任务、进行中、需要处理、已结束、识别恢复、元数据恢复、
分类恢复、冲突处理，八页的列表筛选均只提供“创建时间从（本地）／至（本地）＋清除时间”。
默认或清除后读取**当前标签完整获准总体**，选定日期后读取其中创建时间在范围内的任务，
仍采用有界服务端分页。切换标签保留合法时间范围并从新标签第一页读取；清除日期不切回 All，
也不把“需要处理／识别恢复”等标签变成全状态任务列表。

- Entry/state：八标签及统计卡片沿用现有入口和布局，默认不打开详情；时间、数量、任务行及
  当前标签一致，区分加载、空总体、范围内无匹配和读取失败。
- Action：选单侧/双侧日期即应用，无搜索提交；可清除时间、刷新、翻页、打开/关闭详情，
  以及按当前任务/类型查看问题文件和合法后续动作。
- Success：列表、总数/统计、分页使用相同服务端条件；浏览器刷新、前进后退、重连和现有
  合法回程保留标签/时间/分页及精确任务、问题文件定位，不留下不可见列表限制。
- Failure/recovery：读取失败保留可见日期和明确的只读重读动作；401/403 沿用共享边界。
  空结果可清除时间回到当前标签；筛选/刷新/返回不提交工作、调用 Provider 或重放命令。

适用要求：UX-001/002/007、REQ-API-003、V2-OPS-001/003/005/009/012/014/016、
V2-AUTH-001–003、V2-SAFE-001；完整旅程见
[Tasks, results and per-item recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[任务中心页面约定](docs/task-center-page-spec.md) 与
[CURRENT query contract](docs/architecture.md#current--task-center-query-summary-confirmation-and-typed-recovery-slice45)。
现行文档中“其他七视图保留原筛选”是待本 Task 替换的旧界面定义；用户本轮明确授权统一，
不扩大整理总体、恢复能力或管理 API 的权限/查询能力。

## Actual code gap and implementation anchors

- `OperationsLanding.tsx` 的筛选展示、`readFilters`、`filtersToSearch`、旧条件规范化和查询组装
  均以 `view === "all"` 特判；其他七页仍渲染搜索、来源、状态、操作类型和搜索提交。
  仅删除控件会使原 URL 中条件继续影响总体。
- 同文件已有 `RunTimeRangeFields`、本地日界限转换、清除、查询 key、服务端游标与标签切换，
  可以复用。`view` 是后端标签总体谓词；不能与附加列表条件一并删除。
- `operations-return.ts` 的 `operationsLandingSearch` 只对 All 清除旧列表条件/游标，
  非 All 回程仍会恢复旧搜索等条件。实际详情、四类处理和现有 Files/Automation 链路还携带
  `run`、`problemRun`、`problemType`、问题文件/详情游标，需区分列表限制与精确定位。
- `OperationsInventory.test.tsx`、`operations-return.test.ts` 及现有 real-Python
  `time filter:` 用例明确断言其他页保留旧控件；这些断言需要替换，保留原权限、范围、
  结果和返回安全检查。不是新建筛选系统或退役管理 API。

## Implementation Scope and ordered steps

1. **复用八页统一筛选条。** 其余七页采用现有 All 创建日期交互；删除旧搜索/提交、来源、
   状态、操作类型及其独占草稿/处理器，适当消除已失效的 All/非 All 展示分支。
   请求中/清除/空结果文案统一表达时间条件与当前标签；无日期时可沿用不显示清除按钮。
   既有标题、统计、八标签、表格列、行操作和详情/问题文件布局不重做。

2. **统一提交条件，保留标签语义。** 所有列表请求只提交当前 `view`、可见日期及正常分页；
   不再从旧 URL/组件状态/返回上下文发送 q、source、status、command、attention 或 problem
   等额外列表限制。`view=attention` 及四类恢复 view 本身仍由后端限定真实四类总体；
   不以删除可见状态筛选为由删除它们。保持管理 API 和其余消费者的搜索/筛选契约。
   复用当前本机时区日界限，结束日含完整小数秒；日期 min/max、单侧范围及自动应用保持。
   切换标签保留日期、清空旧标签分页；改变/清除日期重新从当前标签第一页读取。

3. **完成真实入口的 URL/回程恢复。** 将 All 已有的规范化覆盖到全部八页，避免首次请求或
   回程中隐形条件/旧游标短暂生效。不携带旧条件铸造的列表游标；合法时间/view 的正常游标
   则继续用于刷新/详情关闭/重连。
   精确 `run`、详情 tab/item、`problemRun`/`problemType` 和问题文件分页不是普通列表筛选，
   不得机械按名称全删。需要处理页多类型任务必须继续允许明确选择类型；四类恢复页仍按其
   本身类型展示。基于实际可达的查看问题文件→详情→返回、已有 Files/Automation 链接及
   旧页面能够产生的书签/回程核对，必要时同步已有 URL 生成者/allowlist，不新造入口。
   仅在列表条件改变时清理与旧条件绑定的分页；不扩展为通用 URL/认证重构。

4. **保持服务端总体与恢复独立。** 复用现有查询、计数、去重和分页，不在浏览器当前页过滤
   或伪造日期统计。统计卡片保留各自原有总体/分区含义，仅同步当前日期范围，不将当前
   标签的行数套到所有卡片。多类型重叠、四类任务/文件数、普通初次待确认和技术失败归属保持。
   快速改日期/标签时旧响应不覆盖当前状态；失败/401/403 不显示旧总体为新条件成功。
   本轮不改后端业务、任务状态、存储、schema、执行、恢复决定或权限。

5. **同步直接相关 CURRENT 文档与测试。** 在同一实现 checkpoint 更新 README、
   Requirements 的修订说明、V2-OPS-001/003、Product Experience、Architecture 和
   task-center-page-spec，统一改为八标签时间范围；说明清除后仍为当前标签总体，
   管理 API 能力保留。历史参考图不改，原 Slice/旧 Task 的验收事实不重写。
   测试替换“其他七页保留原筛选”断言，保留既有 All、安全/身份/回程检查。

优先文件：`web/src/features/operations/OperationsLanding.tsx`、
`web/src/shared/navigation/operations-return.ts` 及直接测试；允许必要的查询/导航 helper、
现有隔离 harness/fixture 和局部样式调整。生产修改限 Web 查询呈现，不改 Python 业务/API。

## Acceptance Criteria

- [ ] AC-1：八个真实标签逐一检查，列表筛选只有两个创建日期控件及按需清除时间，无搜索、
  来源、状态、操作类型或搜索提交；All 原结果保持，其他页面共享搜索不受影响。
- [ ] AC-2：每个标签无日期/清除后都是该标签完整获准总体，日期限制与标签谓词组合正确。
  Running、Attention、Ended 和四类恢复不串总体；切换/清除不改变四类问题/任务身份、
  待处理去重、问题文件数量或已有合法操作的含义。
- [ ] AC-3：单侧/双侧日期直接应用；本地显示/筛选时区一致，含结束日最后小数秒。
  切标签保留日期并重开第一页，日期变更/清除弃用旧列表游标。跨页行、总数/统计一致，
  没有当前页内筛选、无界全量加载或旧响应覆盖新条件。
- [ ] AC-4：旧页面真实可产生的非 All 书签、刷新、详情关闭、认证重连及原有合法回程均
  不复活已删除条件，也不重用旧条件游标。精确任务详情、必要问题类型/文件定位及合法
  详情/问题文件页状态保留；管理 API 的其他消费者仍支持原搜索/筛选。
- [ ] AC-5：四类页“查看问题文件”、需要处理页的明确类型选择、单项证据/详情及返回可用，
  不因删除 `problem` 列表条件误删 `problemType` 定位。保留已有 Files/Automation 精确链接；
  不要求本轮重跑恢复执行全链路或新增恢复动作。
- [ ] AC-6：加载、空总体、日期无匹配、请求失败、401/403 分支正确，失败保留日期并只重读；
  清除按钮回到当前标签总体。筛选/标签/刷新/分页/打开及返回只有有界只读请求，零新工作、
  Provider/媒体写入或成功/不确定效果重放。
- [ ] AC-7：1536×1024 和 390×844 下实看八标签入口、日期/清除、代表性列表/详情/问题文件；
  键盘可达，焦点可见，无本次引入的整页横向溢出/控件遮挡；既有标签/表格容器滚动允许。
- [ ] AC-8：CURRENT 文档不再把其他七页写成保留旧筛选；原 Slice 和已接受 Task 的历史结论
  不变。实际结果/失败/限制、精确 checkpoint 和测试用时清楚记录，交 READY FOR B REVIEW。

## Required Tests

T3：跨 Web 列表/URL/回程与既有 API 时间/分页边界的只读集成修正。无新领域状态、权限或
执行协议。按 [workflow §6](docs/development-workflow.md#6-test-levels) 分工；不要求全仓
Python/Web/E2E、wheel/Docker/外部服务矩阵。若确需改 schema、权限、执行或后端业务，先交 B
重评边界/等级。测试用时须小于本轮工作用时 50%；优先已知问题/直接影响，不以扩跑无关测试
填充验收，不通过删除安全断言、重试或放宽超时解决失败。

### Developer — affected tests

根目录：`python3 scripts/check_governance.py`，结束前 `git diff --check`。
`web/`：

```sh
npm run test -- run src/shared/ui/AppShell.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/run-query.test.ts src/shared/navigation/operations-return.test.ts
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "time filter:"
```

对实际改动的 TS/TSX/CSS/测试文件运行 `npx prettier --check <实际文件清单>`；新增 helper/test
加入受影响清单。如修改 `scripts/operations_inventory_harness.py`，根目录运行：

```sh
.venv/bin/ruff check scripts/operations_inventory_harness.py
.venv/bin/ruff format --check scripts/operations_inventory_harness.py
```

- 单元用例按八 view 参数化覆盖控件、无日期/选日期/清除、请求参数及旧条件移除；覆盖
  快速切换、读取失败与必要回程分支。独立问题文件/详情筛选不是本次删除对象。
- 扩展现有 `time filter:` real-Python 旅程，使用 `operations_inventory_harness.py` 现有时间、
  轮询/恢复隔离 fixture，必要时有限扩展已有 seed。覆盖 Running/Ended 时间总体与至少一个
  有实际四类问题的 Attention/恢复视图，断言范围内/外记录、计数/分页、旧非 All 链接及精确
  问题文件/详情回程。仅打开已有处理/证据，不把恢复执行全链路加入本布局/查询修正门禁。
- 默认浏览器用例从现有标签入口逐一验证八页一致，桌面/390px 实看并保存截图；复杂回程
  选代表案例，不要求八页 × 所有错误 × 全部视口的笛卡尔积。
- 临时 SQLite/Local 和一次性身份；不访问用户配置、运行库、媒体或外部 Provider。
  不新增产品路由/探测端点，不构造实际使用中不可能触发的问题。

### B — independent acceptance

独立审查完整 Task Base..candidate，先核对八页一致与标签总体不串，再核对旧条件清理、
问题文件定位及回程；不把旧 Task 限定 All 的 PASS 当作本 Task 验收。
执行上述受影响命令（完整包含的用例不重复执行），额外在 `web/` 运行 `npm run format:check`；
根目录核对后端既有时间/游标契约：

```sh
.venv/bin/python -m unittest tests.test_operations_run_inventory.RunInventoryTestCase.test_time_filters_compose_with_status tests.test_operations_run_inventory.RunInventoryTestCase.test_cursors_bind_the_submitted_filter_scope
python3 scripts/check_governance.py
git diff --check e40093aa2400794f4423987658fba3095c7adda5..HEAD
```

B 独立实看八标签筛选，桌面/390px 截图与一个真实四类问题文件→证据→返回路径，保留
实际命令、精确候选、计数/失败/skips 与用时；证据保存在 CI 或 ignored 稳定本地目录。
只复用输入/产物完全一致的 B 自有证据；本轮规划只做治理及代码/文档核对，未跑产品验收。

## Non-goals and workspace

不重开/关闭 Slice、不改 Roadmap/Progress、不重做页面/统计/详情或 Rules/Automation 产品；
不新增搜索、任务归并、Provider/API/schema/索引，不改变管理 API 的其他消费者；
不删问题文件/详情自身必要筛选，不修改四类恢复/初次确认/控制/执行/权限或效果真值；
不创建新流程工具、远端/生产测试或新 agent，不自动推送/部署本轮新 Task。

规划预检 PASS；`main` / Task Base 如上，初始无 tracked 改动，工作区及 Git 可写。
原有未跟踪各级 `.DS_Store`、`.mgmt.log`、`.t.log`、`.t_test_*.log`、`15`、
`docs/pics/自动化页.png`、`docs/pics/自动化页-全局设置.png`、
`output/imagegen/slice45-task-center-v1.zip` 均保留，不移动/清理/暂存；私有配置不读取或纳入。
实施前重新记录实际分支/HEAD/status；本 Base 不随规划、实施、返工或报告提交移动。

## Developer Completion Report

尚未实施。Next：Developer 按本 Task 实施、完成受影响检查后交 READY FOR B REVIEW。

## B Review Result

尚未复核；规划及预检不是 PASS。B 在收到精确 checkpoint 后审查完整 Base..Head，
给出 PASS 或 FIX REQUIRED；独立修正完成后恢复 compact NO ACTIVE IMPLEMENTATION TASK。
