# Task PATCH-20261029-3 — Task Center time-range-only filtering and search removal

Authority: the user-authorized standalone correction and
[Development Workflow](docs/development-workflow.md). 用户于 2026-10-29 明确要求激活本 Task；
本文件为正式独立 Task；Developer 已提交候选，等待 B 独立审查。
Slice46 继续 PASS / CLOSED，原 Base、已审 Head 及 Roadmap/Progress 保持不变。
前一独立 Task PATCH-20261029-2 的 PASS 记录保留在 `542496a8:TASK.md` 及 Git 历史中。

```text
Task ID: PATCH-20261029-3
Name: Task Center time-range-only filtering and search removal
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 542496a8cb9b69e5146fe8c702cd6f695752accd
Difficulty: Low
Test Level: T3
Planner / Reviewer: B
Development Authorization: USER-ACTIVATED TASK — 2026-10-29
```

### Goal and authorized boundary

删除任务中心顶部的共享 Shell 搜索框，以及“全部任务”列表的搜索框、搜索提交动作和
搜索专属状态；该列表**只保留任务创建时间范围筛选**，移除来源、状态、操作类型筛选。
未选择时间时显示全部获准整理任务，选择后只显示创建时间在范围内的任务，清除时间后
恢复全部任务；“全部”指完整总体，仍采用正常有界分页。

保留标题、统计、八个标签、通知/账号、任务详情与允许的处理/控制；其他七个视图的业务
范围及现有交互、其他页面的顶部搜索保持原有边界。管理 API 其他消费者的既有搜索/筛选
能力不因 All 页控件移除而一并删除。

Applicable requirements/journey: `UX-001/002/007`, `REQ-API-003`, `REQ-SAFE-001/005/007/009`,
`V2-OPS-001–005/009/014/016`, `V2-AUTH-001–003`, `V2-SAFE-001`；
[Product Experience — Tasks, results and per-item recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[Task Center specification](docs/task-center-page-spec.md) 及
[Architecture — CURRENT Task Center query](docs/architecture.md#current--task-center-query-summary-confirmation-and-typed-recovery-slice45)。

### Observed gap and implementation anchors

- `web/src/shared/ui/AppShell.tsx` 在 `/operations` 仍渲染只读通用搜索框。
- `web/src/features/operations/OperationsLanding.tsx` 共用关键词、来源、状态、操作类型和日期
  筛选，需要仅在 All 简化为时间范围，删除该视图不再使用的搜索草稿/提交逻辑。
- 现有 `from/to` API、后端完整总体查询、计数/分页及 URL 返回上下文可复用，不需要新增
  文件名查询参数、文件证据匹配或索引。日期当前结束日只到 `23:59:59`，遗漏该秒的小数部分。

### Implementation scope and ordered steps

1. **移除页面搜索和 All 多余筛选。** 在任务中心八个视图所在的共享 Shell 隐去顶部搜索，
   保留账号/通知与正常布局；其他页面搜索不受影响。在 All 删除搜索框/搜索按钮、来源、
   状态、操作类型控件，只显示时间起止范围及含义明确的清除时间动作。按实际消费者清理
   搜索专属的局部状态和处理器，保留其他视图/管理 API 仍使用的共享能力。

2. **保留并完成时间筛选。** 沿用任务创建时间范围，通过日期选择器选定范围后应用到任务列表；未选
   时间不附带“今天/最近 N 天”等默认限制，清除后恢复全部获准任务。保留原控件已有的
   单侧/双侧范围能力，筛选和列表显示使用一致、明确的时区，不新增时区设置或写死 UTC。
   日期有效性及双侧范围的起止顺序由选择控件约束，结束日期覆盖完整一天及小数秒。
   时间控件独立可操作，不依赖已删除的搜索提交按钮；不增加“非法时间输入”的报错流程。
   底层 API 已有参数校验保持原规则，不作为本次新增的界面能力或验收项。

   | 时间条件 | 查询总体 |
   |---|---|
   | 未选择或已清除 | 全部获准整理任务 |
   | 已选择范围 | 创建时间位于该范围内的任务 |

3. **保持完整总体、统计和分页一致。** 复用后端时间过滤和同一读快照，将时间条件一致用于
   列表、总数及既有统计；不在浏览器当前页过滤。更改/清除时间后重新分页，禁止复用其他
   时间/主体的分页上下文；同一 Job/Task 继续按真实关系去重。正常分页不因“全部显示”
   变成无界加载。快速选择范围时旧响应不能覆盖新结果。

4. **处理 URL、返回与旧条件。** All 的正常查询及返回不应暗中携带已删除的关键词、来源、
   状态、操作类型或其他不可见限制。核对旧链接、Files/Automation 精确任务定位、详情
   开关和返回上下文，按真实入口做明确兼容处理；不预设统一删参数或跨所有视图清空条件，
   不留下隐形限制，也不丢失精确任务身份。刷新、详情返回和认证重连恢复合法时间/分页。
   其他七个视图及管理 API 的现有查询语义保持兼容，不做全站搜索/API 退役。

5. **完成失败与页面旅程。** 加载、无匹配和网络失败明确对应当前时间条件；失败保留时间，
   允许安全重读查询，读取不提交工作。保留 401/403、脱敏、轮询和任务结果真值。桌面与
   390px 下，起止日期、清除动作、统计/标签和列表均可达，无残留搜索按钮或无效空位。
   验收可见结果与键盘可用性，不以特定 DOM、CSS 数值或参数名作为硬约束。

6. **同步直接相关事实并交接。** 实现后仅同步本改动涉及的 Task Center 页面约定、Product
   Experience 和必要查询说明，保留稳定要求 ID 与历史验收身份。Developer 提交连贯候选
   及受影响测试结果，B 独立审查；不自批、不计划下一 Task，
   不修改 Slice/Roadmap/Progress。

### Acceptance criteria

- [ ] 任务中心顶部不再有搜索框；All 列表只提供创建时间范围及清除时间，无搜索框/按钮、
  来源、状态、操作类型控件或暗中生效的旧条件。其他页面顶部搜索、其他七视图正常。
- [ ] 未选/清除时间显示全部获准任务；选定范围只显示范围内任务。日期选择及双侧范围起止
  顺序由控件约束。覆盖起止边界、跨日、原控件支持的单侧范围和结束日最后一秒，
  显示/筛选时区一致；不要求单独的非法输入报错流程。
- [ ] 超过一页、并列时间和真实 Job→Task 关联下，行/计数/统计/分页一致，不漏项或重复；
  改变/清除时间从对应总体重新分页，不能复用其他范围/主体的分页上下文。
- [ ] 快速调整时间、网络失败、无结果和重新读取均不丢失条件；旧响应不覆盖新条件结果。
  时间筛选无需搜索动作，清除后没有隐藏限制。
- [ ] 刷新、详情开关、明确返回、重连恢复合法时间与分页；旧链接兼容不丢失精确任务定位。
  Files/Automation 任务入口和其他视图不会因 All 简化而失效。
- [ ] 筛选、清除、刷新、分页保持只读，不调用 Provider/Storage 补全数据，不创建/重提工作；
  权限/脱敏、任务身份、恢复关联及成功/失败/不确定效果保持原规则。
- [ ] 桌面/390px 实际浏览器检查通过：顶部和 All 搜索消失，时间控件与列表可操作，真实
  Python/API/SQLite 的范围过滤、计数和分页正确。不存在原文件名搜索方案的必验项。

### Required tests and ownership

**Developer — new/changed and directly affected checks only**

- `web/`: `npm run test -- run src/shared/ui/AppShell.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/run-query.test.ts src/shared/navigation/operations-return.test.ts`。
  覆盖搜索/多余筛选移除、日期/范围选择约束、应用/清除、时间边界、旧响应、返回/重连和其他视图兼容；
  删除只针对 All 搜索的旧断言，保留其原本保护的任务定位/权限/结果行为。
- Root: `.venv/bin/python -m unittest tests.test_operations_run_inventory.RunInventoryTestCase.test_time_filters_compose_with_status tests.test_operations_run_inventory.RunInventoryTestCase.test_cursors_bind_the_submitted_filter_scope`。
  复用既有真实 API 时间与分页契约，不增加非法日期输入或文件名查询测试。
- `web/`: `npm run typecheck`、`npm run lint`、`npm run build`；实际修改的文件运行对应
  Ruff/Prettier 检查，不做全仓格式修复。
- 在现有 `tests/e2e/operations-inventory.python.spec.ts` 补充以 `time filter:` 为前缀的
  原生旅程；构建后运行
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "time filter:"`。
  使用既有隔离 harness 验证默认全部、选范围、清除、跨页和返回；只用合成任务/临时数据库。
- Root: `python3 scripts/check_governance.py`、`git diff --check`。

**B — independent acceptance on exact Task Base..candidate**

- 核对完整差异，独立验证搜索移除、时间未选/已选/清除、结束日完整性、旧链接无隐形限制，
  再运行上述直接受影响的 Web/Python 测试；不保留原双名搜索、输入法/防抖或附件检索门禁。
- `web/`: `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`；
  `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts`；
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "time filter:"`。
  检查桌面/390px、真实时间总体/统计/分页、详情返回与其他视图基本导航；采用原实际入口，
  不要求完成与本改动无关的整理/恢复全链路。
- T3：共享 Shell/All 页面、API 时间契约及 URL/分页返回的只读集成修正；不默认要求全量
  Python/Web/E2E、wheel 或 Docker 矩阵。如发现确需 schema、权限、执行或并发写入改变，
  先由 B 重新评估范围与测试级别，不能自动扩展本 Task。
- 记录精确 SHA、实际命令/结果及限制；独立 bug PASS 后恢复简洁 no-active notice，
  不关闭/重开 Slice，不追加大 Slice closure ledger。

### Non-goals and workspace

不实现文件名或整理前后名字匹配、附件检索、新搜索 API/索引、全站搜索、数据回填或第二套
任务归并；不调整执行/命名/冲突/恢复策略，不重设计其他七视图，不做未授权部署/push。
保留现有业务数据模型与执行/权限契约。原 C→A 识别类型不变式不受影响。

规划时为 `main` / `542496a8cb9b69e5146fe8c702cd6f695752accd`，无预先存在的 tracked 修改。
预先 untracked 文件保留：根目录 `.DS_Store`、`.mgmt.log`、`.t.log`、
`.t_test_dashboard.log`、`.t_test_final_integration.log`、`.t_test_media_library_direct_commands.log`、
`.t_test_operations_run_detail_log_isolation.log`、`.t_test_phase21_closure.log`、
`.t_test_recognition_review.log`、`.t_test_workflow_retry.log`、`15`；
`docs/.DS_Store`、`docs/pics/.DS_Store`、`docs/pics/自动化页-全局设置.png`、
`docs/pics/自动化页.png`、`output/imagegen/slice45-task-center-v1.zip`、
`testdata/.DS_Store`、`web/.DS_Store`。不读取私有配置/运行库，不 stage 这些文件。
激活前 HEAD 仍为上述 Task Base；预先 tracked 修改仅为本 Task 的未提交规划草案。
工作区及 Git 目录可写。本轮将该草案转为正式 PLANNED Task，并只为 TASK.md 建立本地
checkpoint；不修改产品实现、其他文档或预先 untracked 文件，不 push。

### Developer completion report

- **Status: READY FOR B REVIEW**；源码候选 `40cdcf6cc26b7b4f244094d86e87dc1872e3c908`。
  B 审查范围：`542496a8cb9b69e5146fe8c702cd6f695752accd..40cdcf6cc26b7b4f244094d86e87dc1872e3c908`。
  后继报告提交只修改 TASK.md，不改变已验证的源码/测试/harness/构建输入。
- 实现：任务中心 Shell 隐去搜索；All 只保留本地创建日期的单侧/双侧范围与清除，
  列表/详情显示同一时区偏移，结束日覆盖最后一微秒；沿用后端完整总体、统计和分页。
  All 旧隐藏条件及其游标在首次查询前清除，保留精确任务；其他视图/API 保留既有筛选。
  修正空列表残留的 Scan/Preview 入口文案，同步三个直接相关说明文档。
- 入口真实性：时间用例实际操作现有日期控件/清除/分页/详情/重连；临时数据库仅注入合成
  时间分布，不新增产品入口。旧 Files 浏览器断言按真实的普通侧栏 → 整理执行页 →
  “查看关联任务”修正，不拼造 `returnOps`，保留实际执行、身份、C→A 和不重放断言。
- 工作区：开始为 `main` / `aa77d5c38b29132511f313893b11444a76eccf7a`。
  已有 14 个 tracked 文件修改及未跟踪 `run-time.ts` 均为本 Task 内容，先保存差异再继续
  核对/修复并显式纳入源码 checkpoint；原始清单与补丁在下述证据目录。所有无关未跟踪
  日志/图片/OS 文件保留且未 stage；SLICE/Roadmap/Progress 未修改，未读私有运行库/媒体。

实际验证（2026-10-29，命令 cwd 按 Required tests）：

| 检查 | 实际结果 |
|---|---|
| Required tests 的五个 Web 文件：`npm run test -- run ...` | 5 文件 / 64 passed |
| Required tests 的两个 `tests.test_operations_run_inventory.RunInventoryTestCase` 用例 | 2 / OK |
| `npm run typecheck`、`npm run lint`、`npm run build` | 均通过 |
| 全部修改的 TS/TSX 文件 Prettier；harness Ruff check / format --check | 均通过 |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --output=../.git/validation-evidence/dev-patch-20261029-3/python-browser-delivery` | 43/43（含全部 3 个 `time filter:` 用例），1.4m |
| `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts --output=../.git/validation-evidence/dev-patch-20261029-3/browser-delivery` | 30/30，12.5s |
| `python3 scripts/check_governance.py`、`git diff --check` | 通过 |

真实 Python spec 扩展运行覆盖此次修改影响的既有共享入口/详情 helper；没有执行全仓矩阵。
桌面/390px 截图已实际检查，顶部搜索消失、日期控件/统计/列表可达；窄屏保留表格内部滚动。
日期选择及八个标签、精确详情的焦点/Enter/Escape 路径通过实际 Chromium 检查。

证据：本地 `.git/validation-evidence/dev-patch-20261029-3/README.md`，`*-delivery.log`、
`input-sha256.json`（源码/测试/harness/生产资产 SHA256）及浏览器截图/trace。
首轮浏览器并行运行因默认输出目录共享导致 trace ENOENT，随后使用独立输出目录。
扩展真实后端首轮 17 failed / 26 passed：四个旧入口断言阻断执行后造成后续共享 Worker/fixture
连锁失败；中间修正轮在发现准备页仍有默认中心链接后主动中断，日志未删除。
修正为实际页面链接并完成既有执行后，最终新 harness 上 43/43 通过；未放宽断言/加重试或超时。

剩余风险/限制：无已知本 Task 实现阻塞；B 独立 T3 验收仍待执行，验收勾选由 B 决定。
本次为本机时区/Chromium/临时 SQLite/合成媒体验证，不声称跨时区矩阵、远程 Storage 或全量
回归通过。保留 jsdom scrollTo、Vite 大 chunk 和 NO_COLOR 等工具警告。
无新角色经验；未自签 PASS，未推送或发布。

### B review result

Pending an implementation checkpoint. No product test PASS or independent review is claimed by
Task activation; B reviews the complete Task Base..candidate and records PASS or FIX REQUIRED.
