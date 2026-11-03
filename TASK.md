# Task 48.1 — 任务流程结束与文件结果分开

用户于 2026-11-03 要求激活本 Task。父 Slice48 已在
`802b6ae4145f30da79751388fca285d5752b47b9` 提交为 ACTIVE。B 核对原 Task Base 至该检查点
只有文档变更，保留原基线、目标、范围、验收和验证计划，现正式启用本 Task。
候选 `2450680f646f6d45e3dfc2180863775bbebb4b5c` 已交 B 复核，结论为 FIX REQUIRED。
Developer 按文末修正指导在同一 Task 继续；原 Task Base、目标、授权和范围不变。

Authority: committed [Slice48](SLICE.md) RO-1–3，以及 RO-4 中执行记录与 Task 状态一致的部分；
[Development Workflow](docs/development-workflow.md) 负责生命周期、测试和检查点。
本 Task 不承担自动化成功率计算的交付，也不据此宣告整个 Slice 完成。

```text
Task ID: 48.1
Task Type: SLICE
Parent Slice: 48
Status: FIX REQUIRED
Task Base: 4f11762d617d50555f3b106357e8f41988f7c2f9
Difficulty: High
Test Level: T4
Planner / Reviewer: B — Codex; independent candidate review completed, FIX REQUIRED
Development Authorization: AUTHORIZED — USER REQUEST, 2026-11-03 — TASK 48.1 SCOPE ONLY
Next Action: DEVELOPER FIXES TASK 48.1 BLOCKERS; SAME TASK BASE
```

### Goal

用户从 Files、支持的 API/CLI、定时自动化或定义“运行一次”提交工作后，能分别看懂
“这个任务有没有处理完”和“每个文件整理成了什么样”。正常收尾的任务显示“流程已完成”，
即使文件全部失败、部分成功或效果未知；这些文件事实仍逐项保留。
四类人工处理、首次执行确认和真正尚在执行的工作保持未完成，Task 自身跑不下去则显示
“流程失败”。两种库的普通文件操作遵循同样的 Task 语义，在原库页保留实际操作结果。

完整旅程：原有入口提交 → 任务中心/原库本地状态查看阶段和文件结果 → 使用已有取消或
四类决定、分析、精确摘要、明确继续 → 查看持久结果。刷新、重连、同版本重启能找回原任务；
文件技术失败和未知效果保留事实，不新增通用重试、核查步骤或第五类恢复。

需求追踪：`V2-TASK-012–014`、`V2-AUTO-012` 的执行记录部分；Slice AC-1–8、11–15 的
相应行为。保留 `UX-001–007/010`、`REQ-TASK-005–010`、`REQ-RESULT-*`、`REQ-SAFE-*`，
及 `V2-OPS-014–017`、`V2-FILES-007`、`V2-AUTO-010/011` 未被 Slice 明确修订的要求。
阅读 [TARGET 旅程](docs/product-experience.md#target--task-flow-status-and-automation-success-rate-slice48-active)、
[TARGET 架构](docs/architecture.md#target--task-flow-status-and-automation-success-rate-slice48-active)、
完整手动整理/普通维护/四类恢复/自动化旅程，以及被修订的 CURRENT 结算、源历史和记录契约。

### 页面提示

按用户要求，任务中心、自动化执行记录及原库操作弹窗的提示使用简短、日常的中文。
先显示状态和文件结果，需要解释时再加一句具体原因；现有详情保留必要证据。
可采用下列短句，按实际操作和已知事实调整，不要求逐字一致：

| 情况 | 页面示例 |
|---|---|
| 正常收尾、文件结果混合 | 任务已结束。成功 7，部分成功 2，失败 1。 |
| 全部文件失败，任务已收尾 | 任务已结束。失败 10。 |
| 需要处理四类问题 | 等待你处理。 |
| 首次执行确认 | 等待你确认。 |
| 复制超时且效果未知，本轮已结束 | 复制超时，是否成功尚不清楚。不会自动重试。 |
| 文件结果未记录 | 该文件的处理结果未记录。 |
| Task 自身因源目录无法读取而失败 | 任务失败：无法读取源目录。 |

“已结束”表达流程收尾，文件成败另列；等待、排队、正在处理仍显示真实阶段。
页面主提示不出现“技术终止、结算、围栏、owner、pin、Result、mutation”等内部词汇，
不把架构规则、状态码或长段免责说明塞给用户。原因说具体操作及问题，下一步只显示后端
实际允许的动作；不新增通用重试、远端核查或人工确认要求。缺结果与效果未知分别按证据表达。
本节只明确现有页面的表达方式，不改变 Slice 的五状态、统计口径、执行安全或 Task 边界。

### 页面改动位置

沿用现有页面布局、八个标签和统计卡的位置，把本 Task 的显示调整放在以下现有区域。
统计卡、标签归属和分页数量按新的 Task 流程状态计算；沿用布局不表示冻结旧统计语义。

| 位置 | 显示调整 |
|---|---|
| 任务中心列表的“状态”列及现有“当前阶段”列 | 状态显示任务是否结束；当前阶段说明正在处理或等待确认，不把文件部分成功作为任务状态。 |
| “已结束”列表的“结果摘要”列 | 分别显示真实文件结果，例如“成功 7，部分成功 2，失败 1”；存在效果未知或结果未记录的文件时保留简短提醒。 |
| 任务详情的进度、文件列表 | 分开显示处理进度和文件成败，保留每个文件的独立状态；处理进度 100% 不代表全部成功。 |
| 具体文件详情的现有提示区 | 用短句说明具体原因，例如“复制超时，是否成功尚不清楚。不会自动重试。”；已知步骤及必要技术证据保留在现有详情中。 |
| 自动化执行记录的状态、结果摘要及既有详情 | 同一任务的当前状态和文件结果与任务中心一致，详情保留具体原因；继续使用紧凑只读记录。 |
| 两种库的“当前页面操作状态”弹窗 | 分别显示任务是否结束和复制、移动、删除等操作的实际结果，失败、部分完成、未知或缺结果照实呈现。 |

列表用于快速看结果，详情用于查看具体问题。复用现有列、详情区和弹窗，不新增页面、
列表列或独立提示面板，不重排八个标签和统计卡，不增加恢复入口或按钮。
同一文件的重要失败/未知提醒不能因放入详情而在列表结果摘要中被“已结束”掩盖。

### Actual gaps and implementation scope

以下是本 Task 基线的实际缺口；实现时沿这些真实调用关系接入共享规则，不按文件拆交付。

| 位置 | 当前缺口与本 Task 要处理的行为 |
|---|---|
| `domain/task_persistence.py`：`PersistentTaskStatus`、`task_work_status`、`task_item_counts` | Task 仍有 paused/partial_success；收尾由文件成败推导，全部取消文件也能推出 Task cancelled。分开流程结算、文件结果和进度。 |
| `application/task_runtime.py`：`finish`；`manual_task_engine.py`：各 settle/failure 分支；`manual_organize_execution.py`：`_task_after_item`；`final_cli.py`：`_settle_direct_organize` | 多条最终及中间发布路径各自聚合文件结果；不能只改最后一次 finish。保留各入口意图和合法同 Task 续作。 |
| `application/task_scheduling.py`；`infrastructure/sqlite_runtime.py`：`release_scheduled_claim`、`_recorded_unknown_boundary_is_finished_locked`、源所有权交接 | 现有未知边界释放要求受影响项有 Result，processing 标记也被直接当作剩余工作。允许已技术结束的尝试在缺 Result 时收尾，同时保留真正在途、取消、当前 owner 和不重放保护。 |
| `application/direct_file_commands.py`、`direct_file_transfers.py` 及相关 SQLite 发布 | 文件操作结果决定 Task 终态，读回又把 Task completed 映射为操作 SUCCESS。两种库均须分别结算、分别读回。 |
| `domain/operations_run.py`；SQLite `_run_query_document`、`_automation_record_query_document`；`application/operations_lifecycle.py`、`automation_record_display.py`；`interfaces/service_api.py` | 列表、详情、分组、进度和自动化记录仍有文件派生状态或冻结首轮状态。当前 Task 流程采用同一事实，原始时间/尝试/文件效果单独保留。 |
| `web/src/entities/operations/{task,run,run-detail,automation,lifecycle}.ts`；任务中心、自动化记录、`LibraryFileOperationsDialog` 及 Dashboard 的实际消费者 | 旧状态、completed 必须有成功文件等校验和文案需要跟随调整；不要因 completed 隐藏失败/未知警告。 |
| `application/notification.py`、Dashboard、日志/JSON export 的现有 Task-status 消费者 | 跟随五状态和流程含义，保留原通知类型、订阅策略、脱敏、范围和投递机制。 |
| `domain/tasks.py`、`domain/scanner.py` | 旧十二状态词汇实际被内部 ScanResult/测试使用。审计并隔离内部扫描结果/阶段与持久 Task，不能形成第二套 Task 生命周期；不要求重写扫描算法或全仓删除相同字符串。 |

### Implementation steps

1. **先确定一份应用层结算规则。** 输入必须能区分本轮是否结束、是否仍有真实机器/人工工作、
   范围是否完整、是否有 Task 自身错误和已确认取消；不能只接收文件列表然后猜 Task 状态。
   复用现有 engine/coordinator 和仓储事务，不建第二套执行系统。Task 当前状态仅为
   pending/running/completed/failed/cancelled；阶段、文件/附件/传输结果、不可用读取仍各有含义。
   paused/partial_success 不再被当前 Task 写入或展示；保留历史读取时不得凭旧文件汇总猜新流程成功。

2. **接入所有真实生产路径和中间发布。** 覆盖 Files 单文件/目录/混选、支持的直接 API/CLI/remote、
   due、Run once、同 Task 四类继续，以及两种库的现有普通文件 Task。正常处理完与文件技术失败
   都按下表收尾；根目录/范围不完整、必要 pin/关联丢失、阻止完成的 Task 编排错误仍是流程失败。
   有界文件局部错误与整个范围无法证明完整分开；不因缺 Result 就改判 Task 编排失败。
   保留独立兄弟文件和原失败策略，不把一个文件结束当成整个 Task 完成。

3. **处理技术结束、缺结果与执行围栏。** “本轮技术结束”指该文件的应用调用已报错/超时退出，
   或结束的应用尝试已按既有围栏退休；不要求证明远端 Storage 成功、失败或停止。
   不能用 Worker 消失、租约过期、一个旧 processing 标记或异常文字单独断言处理已结束。
   复用实际调用/执行边界，必要持久证据放在现有 Task/尝试责任内，不增加远端轮询或普通用户步骤。
   先核验有效 owner、取消与真实剩余工作，再在原事务中保存 Task 收尾和相应容量/当前处理状态。
   缺正式 Result 本身不阻止结束，也不能单独占住已结束尝试的普通名额。保留已知步骤、失败、
   缺结果和未知效果；旧 owner 不能再发布结果或获准发起新执行，已发出的远端调用仍按实际
   已知/未知效果保留。真正还在本地执行的调用保持保护。
   数据库写入失败保留最后持久状态，不报告“已经完成/已经失败”，不因重读或重启重做媒体操作。

4. **把进度与文件成败分开。** 一份已确认具体源只计一项，后续尝试、Result 行和附件不重复计主文件。
   在范围/数量已知时，进度表示本轮已结束处理项占全部项的比例，包含已记录失败和本轮技术结束项；
   不能拿成功文件数充当已结束项。全部处理项结束可到 100%，仍可有失败或未知效果。
   总量不明/范围不完整时不得编造百分比；健康空范围单独说明无工作。
   成功、部分成功、失败、跳过、忽略、单项取消按相应文件事实展示；未知效果和结果未记录是独立事实，
   可与已知处置重叠，不能再与各处置数相加当总数。结果缺失不必然等于效果未知。
   主文件已验证成功而附件失败时保留主文件成功和附件警告。保留已有计数字段的明确兼容语义，
   如需增加最少字段，同步 API、解码和展示，禁止悄悄把同一字段同时解释成成功数与处理进度。

5. **完成用户能看到的读回。** 任务中心八视图和原有管理过滤/分页统一使用持久 Task 流程；
   需要处理仍是四类当前问题及其必要人工步骤的去重并集。普通首次确认不冒充四类待办。
   技术失败不新增 Attention 类型，也不因流程 completed 显示“恢复成功”。
   自动化记录当前流程结果、结果过滤/计数/分页与任务中心一致，文件原因/效果独立；首轮执行
   时间和原始尝试证据不改写。同 Task 合法继续可更新当前状态，不能新增原始运行。
   记录保持紧凑只读，不新增恢复控件。修正完成但成功文件为 0 的合法数据校验，不能归为无工作。
   原库普通操作弹窗从操作证据读取 SUCCESS/PARTIAL/FAILED/UNCERTAIN，而非从 Task completed
   推出文件操作成功。Dashboard、API/CLI、现有日志/export/通知跟随相同语义；不增加页面或通知政策。
   页面改动按上方“页面改动位置”落入现有区域，主提示按“页面提示”使用短句，技术证据放在
   现有详情；同一任务在不同页面的含义一致。

6. **以实际流程验证并交接。** 新增共享规则测试，更新各真实入口、事务、记录和 Web 的直接受影响测试。
   用真实服务执行/故障注入证明结算，不能仅手工种一个 completed 行就声称生产链路通过。
   旧断言只按本 Task 明确变化更新；保留独立文件结果、权限、越界、围栏和不重放断言。
   不修改 CURRENT 为已交付，不填 Slice 验收；受影响验证完成后交一个可审阅检查点给 B。

### Acceptance criteria

下表默认“整个 Task 自身没有阻止收尾的流程错误或已确认取消，且其他机器/人工工作也已结束”。
不能省略这个前提，把一个文件的技术失败扩大成整批提前完成。

| 场景 | Task 和可见结果 |
|---|---|
| 全部成功；成功/部分成功/失败混合；全部失败/部分成功；全部跳过/忽略或单项取消 | completed；所有独立文件事实保留，单项取消不能推导整 Task cancelled。 |
| 四类人工问题及必要决定/分析/摘要确认 | running；原 Task 内处理，需人工时保留相应类型；无机器工作时释放普通名额。 |
| 普通首次确认、排队、稳定性等待、实际仍在本地执行的调用 | 保持 pending/running 和真实阶段，不能提前收尾；首次确认不增加四类待办。 |
| 文件技术失败，实际效果明确 | completed；显示实际失败/部分完成/已完成步骤。 |
| 文件技术失败，实际效果未知 | 本轮技术结束后 completed；保留未知事实和不重放，无远端停止/结果核查门槛。 |
| 文件技术失败，正式 Result 未产生，或只留下旧 processing/变更标记 | 已结束尝试可在现有所有权保护下收尾为 completed；缺结果不能独占名额，也不制造成功或正式文件历史。真正未完成工作仍保留。 |
| 健康空范围、完整历史排除 | completed；分别说明无文件或排除原因；全部失败、缺 Result 不得冒充健康空范围。 |
| 根目录/完整遍历失败或超界、必要 pin/关系损坏、阻止完成的 Task 编排错误 | failed；已知文件即使全部成功也不能掩盖流程失败；不能执行前 N 项。 |
| 用户取消被安全确认 | cancelled；并发正常收尾不能覆盖取消；已完成/未知效果保留，未确认请求不提前变成 cancelled。 |
| Task 终态保存失败或 Task 状态读取不可用 | 保留最后持久事实/不可用说明，不编造成功、失败、零数量或第六种生命周期。 |

- [ ] 上表适用于所有列入范围的入口；后端当前 Task 写入、API/CLI/Web 状态一致。阶段和操作结果
  不被机械压缩成五值，内部 ScanResult 不再冒充持久 Task 生命周期。
- [ ] 同一 Task 有 7 成功、2 部分成功、1 失败且已正常收尾时，显示流程已完成及各文件数；
  全部 10 个失败也显示流程已完成和失败 10。已知范围的处理进度可为 100%，成功数仍为 0。
- [ ] 页面提示简短易懂，主提示能直接看出当前状态、文件结果及适用的下一步；技术词汇不作为
  普通提示。未知效果与结果未记录说清楚，既不冒充成功，也不增加核查/确认负担。
- [ ] 页面改动位于上表所列的现有区域；列表能快速看结果，详情能查看原因。八个标签、统计卡
  及其布局沿用现有结构，计数和归属按新语义更新；未新增页面、列表列、独立提示面板或恢复控件。
- [ ] 同一 Task 同时包含成功、四类待办、明确失败和未知效果时，不重跑成功/未知项，
  其他合法工作独立；存在人工待办时保持未结束。需要处理任务总数去重，各类型任务/文件数正确。
- [ ] 四类决定 → 分析 → 摘要 → 明确继续在同一 Task 完成刷新/重连/重启旅程；
  新问题换类型、纯技术失败离开 Attention。流程完成不能清除未解决问题或证明恢复成功。
- [ ] Task Center 和自动化执行记录对同一 Task/一致读取时显示相同当前流程结果；服务端状态过滤、
  总数和分页一致。合法继续更新当前结果，原始开始/结束时间、尝试、文件效果保留，无新运行计数。
- [ ] 两种库的普通 Copy/Move/Delete 及实际共享 Task 的同步命令，在原库页可找回；
  Task completed 与实际操作失败/部分完成/未知/缺结果同时正确显示，无全局普通任务中心或新重试。
- [ ] cancel/finalize、过期/替换 owner、缺 Result 的技术终止、变更前后中断和同版本重启，
  保持当前权限、pin、源所有权、容量与不重放；不能用全局清锁或单纯放开 Result 检查满足完成。
- [ ] due/Run once 仍按最新正式文件失败/部分成功排除同源版本；新 Files 请求保留原警告和普通确认。
  completed 不抹除历史排除；缺 Result 不伪造历史，已有 TaskItem 失败证据也不能被忽略。
- [ ] Dashboard、API/CLI、相关日志/JSON export 和现有 Task 状态通知正确表达流程；
  原有事件类型/投递策略不扩展，通知故障不改变 Task 或触发媒体重放。
- [ ] RBAC、完整有界范围/Storage confinement、手动与自动化执行意图、零变更读取/分析、
  RecognitionType C 使用 Naming A/Classification A 仍为 C、附件事实和成功/未知不重放有实际覆盖。

### Required tests

遵守 [工作流 §6](docs/development-workflow.md#6-test-levels)：Developer 只跑本轮新增/修改和
直接受影响测试、相关静态检查；B 负责 T4 完整回归、原生和产物验收。以下均是未来执行计划，
Task 启用本身不声称产品测试通过。使用临时 SQLite/Storage、fake/本地 Provider 和确定性故障注入。

#### Developer — affected tests

仓库根目录；新增 `tests/test_task_flow_status.py` 覆盖上表及“全部文件终结仍有流程错误”等反例：

```sh
.venv/bin/python -m unittest tests.test_task_flow_status tests.test_task_persistence tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_manual_task_engine tests.test_manual_organize_execution tests.test_operations_task_center tests.test_v2_automation_run_once
.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers tests.test_media_library_transfers tests.test_library_file_operation_history tests.test_organize_source_history tests.test_task_source_ownership_race
.venv/bin/python -m unittest tests.test_final_integration tests.test_batch_cli tests.test_confirmation_api tests.test_workflow_retry tests.test_recognition_review
.venv/bin/python -m unittest tests.test_scanner tests.test_resource_library_pipeline tests.test_dashboard tests.test_notifications tests.test_operational_logging
python3 scripts/check_governance.py
git diff --check
```

前两组分别覆盖结算/围栏/真实入口和普通操作/源历史；第三组覆盖 CLI/API 和同 Task 续作，
第四组覆盖内部扫描状态、共享消费者和身份/管线回归。实际改到其他消费者时，加跑其直接
受影响用例，并在交接中列明。
新增/修改的 Python 文件运行 `.venv/bin/ruff check <实际文件列表>` 与
`.venv/bin/ruff format --check <同一列表>`，报告中展开实际命令。

`web/` 下运行直接受影响单元/组件测试；新增/调整同目录其他实际消费者时追加精确路径：

```sh
npm run test -- run src/entities/operations/task.test.ts src/entities/operations/run.test.ts src/entities/operations/run-detail.test.ts src/entities/operations/lifecycle.test.ts src/entities/operations/automation.test.ts src/entities/library/file-operations.test.ts src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx src/features/dashboard/DashboardPage.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

新增 `task-flow.python.spec.ts` 复用隔离 Python/API/SQLite/Worker harness，覆盖混合结果收尾、
人工等待到明确继续、已技术结束且缺 Result/未知效果、真实调用仍未返回、记录与中心一致。
只在测试基础设施注入本地故障，不给产品增加测试 API 或远端探测要求。
对实际修改的 TS/TSX/测试文件运行 `npx eslint <实际文件列表>`、`npx prettier --check <同一列表>`。
不把全量 Web/Python/E2E 或发布矩阵分配给 Developer。

#### B — acceptance and full regression

B 审查精确 Task Base..候选，独立复现上表关键反例，尤其核对：缺 Result 的已结束尝试、
真正本地在途、仍有人工兄弟、Task 自身失败、取消竞态及只读缺失状态，不能只看 badge 或退出码。
按 [共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands) 执行完整 Python、
Web、静态/构建、安全和适用产物检查；既有结果仅按工作流证据复用规则使用。

在 `web/` 下对生产构建跑真实 Python 浏览器旅程；各配置顺序执行，避免同端口互相占用：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts tests/e2e/organize-source-history.python.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

实际检查桌面和窄屏截图：流程完成仍看得到文件失败/未知警告；四类待办、原库弹窗、记录详情
可操作且不溢出，按“页面改动位置”检查各现有区域，主提示使用上述短句能直接理解状态和文件结果。
按含义与可见行为验收，不把示例文案逐字固定成唯一断言。种数据读取可验证分页，
但结算和继续必须有真实应用调用/Worker 证据。

根目录完成已构建 wheel 和源树外安装检查，并对同一候选镜像运行适用的现有证明脚本：

```sh
.venv/bin/python scripts/wheel_smoke_test.py <exact-wheel>
.venv/bin/python scripts/docker_task_center_recovery_browser_proof.py --image <candidate-image>
.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image <candidate-image>
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image <candidate-image>
.venv/bin/python scripts/docker_release_security_smoke_test.py --image <candidate-image>
```

沿用脚本时只更新本 Task 改变的状态/读回断言，保留操作、pin、权限和不重放断言。
新工作 → 刷新/重开 → 同版本服务重启后，五状态、等待/继续、文件事实及时间/尝试均须保留；
不把旧任务接管、跨版本迁移或历史重建加进来。
日志/截图/产物身份按工作流保存，失败/跳过/环境不可用照实报告，所需未执行门禁不算 PASS。

### Non-goals and remaining Slice outcomes

- 自动化成功率的分子/分母、取消排除、卡片说明及相关月度指标验收不在本 Task 交付范围；
  不把记录/Task 的新流程状态冒充成功率已经完成。共享状态变化带来的必要编译/解码兼容必须处理，
  不借此保留文件派生的 Task/记录结果。后续仍需在 Slice 内完成 RO-4 的指标计算和 AC-9/10。
- 不改变原有媒体决策/命名/分类/冲突/附件算法，不新增 Provider、Storage 命令、恢复类型、
  附件重试、通用回滚、自动未知重放或人工核验门槛；不重做队列、并发、设置、监督或普通操作控制。
- 不恢复 Pause、retry-failed、独立 Scan/Preview/FileIndex/V1；不做旧任务/status 迁移、
  历史批量改标、跨版本升级/回滚、混合版本写入、生产数据/媒体清理或架构外重构。
- 不预先规划下一份 Task，不关闭 Slice，不改 Roadmap/Progress 或宣布 TARGET 成为 CURRENT。

### Developer completion report

READY FOR B REVIEW。Developer 按本 Task 范围实现并交出一个检查点（即本提交，分支 `main`）。

**改动与关键选择**

1. **共享结算规则**（新增 `mediaflow/application/task_flow_settlement.py`）：
   `settle_task_flow` 以边界事实（本轮是否结束、是否仍有机器/人工工作、本地调用是否仍在执行、
   范围是否可证完整、Task 自身编排错误、已确认取消）推导五状态之一，优先级为
   取消 > 流程失败/范围不完整 > 未结束（running）> completed。文件结果不再是输入。
2. **领域层**：`PersistentTaskStatus` 标注 five-state 语义（`partial_success`/`paused`
   仅限历史行诚实读取）；`task_work_status` 重写为“全部 settle 即 completed”，
   取消文件/全部失败不再推导取消/失败 Task；`task_item_counts` 的中间值改为
   **已结束处理项数**（含失败/部分/跳过/忽略/单项取消），`failed_items` 保持为其中
   的文件失败子集（Task `completed_items` 语义同步更新，Web 解码/展示跟随）。
3. **生产者接入**：`manual_task_engine`（自动通道用共享规则结算；历史门排除通过改为
   completed+原因；discovery 暂停映射为 running）、`task_runtime.finish`（等待人工则
   保持 running；文件混合/全败完成收尾）、`manual_organize_execution._task_after_item`
   （终态即 completed）、`final_cli._settle_direct_organize`、调度内核暂停确认
   （Task 聚合不再写 paused，队列行保留暂停资格；`coordinator.requeue` 接受新表示）。
4. **技术结束与围栏**：`_recorded_unknown_boundary_is_finished_locked` 不再要求
   Result 存在（仅限当前 owner 在本轮返回后收尾；真正 processing 兄弟仍拒释放）；
   自动通道 runner 抛出且带 mutation 标记时，`_settle_finished_unknown_pass` 先按
   围栏退休该已结束尝试（item FAILED/`technical_stop`，错误文本声明结果未记录、
   效果未知，不制造 Result），随后按共享规则收尾 completed。
5. **普通文件操作**：传输 Task 流程终态一律 completed（文件聚合留在传输行与
   item/Result 证据）；仅 corrupt pinned authority（`files_transfer_invalid_authority`）
   与 Worker 启动即失败（无 item 启动）判为流程失败；传输行/投影的 SUCCESS/PARTIAL/
   FAILED/UNCERTAIN 全部改从 item/Result 证据推导；Delete 投影同理；Files 暂停
   （已退役）改从传输行读取暂停状态。
6. **读回**：`_automation_record_query_document` 的 record_outcome 改为当前 Task
   流程状态（cancelled 为独立值，legacy partial_success→failed、paused→paused
   保留历史诚实标签），新增 per-file 证据列（success/partial/failed_status/
   missing_result）；运行清单新增 `success_items/partial_items/uncertain_effect_items/
   missing_result_items`；“无工作完成”要求 total_items==0；记录展示与 statement
   按流程+文件事实重写（页面短句，无技术词汇）；通知映射注释更新（映射本身兼容）。
7. **Web**：`task.ts`/`run.ts`/`automation.ts` 计数校验改为 failed⊆ended、
   completed+0 成功合法、记录筛选新增/标注 cancelled；已结束列表结果摘要
   显示“成功 X，部分成功 Y，失败 Z”及未知效果/缺结果提醒；记录徽章“已完成”；
   Dashboard/详情/弹窗跟随既有证据读取，未新增页面/列/控件。

**受影响测试（实际执行）**

- 新增 `tests/test_task_flow_status.py`（21 例）：规则表、聚合推导、真实 SQLite+
  内核+引擎的自动通道场景表、技术结束缺 Result 收尾、取消胜过收尾、流程失败反例。
- 更新 19 个既有测试模块中按本 Task 明确变化的断言（文件失败/部分/忽略/历史门/
  不确定效果改为流程 completed；等待人工保持 running；暂停聚合为 running+
  队列/条目暂停；传输 Task 流程 completed；记录口径）。
- `.venv/bin/python -m unittest discover -s tests`：**2568 通过，7 skip，0 失败**。
- `.venv/bin/ruff format --check .`、`.venv/bin/ruff check .`、`compileall`、`pip check`、
  `python3 scripts/check_governance.py`、`git diff --check`：全部通过。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、
  `npm run build` 通过；`npm run test -- run` 全量 **1267 通过**；Task 列出的 12 个
  受影响测试文件全部通过。
- e2e（真实 Python/API/SQLite/Worker）：`task-flow.python.spec.ts`（**新增**，混合结果
  收尾+记录与中心一致+重启保留+已确认取消）、`operations-inventory`（43）、
  `organize-source-history`、`operations-task-center-visual`、`direct-files`（22）、
  `automation-run-once`（5）、`automation-workspace`（8）全部通过。

**已知风险与剩余工作**

- 自动化成功率计算（RO-4 分子/分母、卡片说明、AC-9/10）不在本 Task，为 Slice 内
  下一个交付；现有指标查询未改，其 file-derived 口径需在下一 Task 处理。
- “真实调用仍未返回”的浏览器级注入未入新 spec（引擎/内核级已由
  `test_task_flow_status` 与既有围栏测试覆盖）；B 可在验收中决定是否补充 harness 接缝。
- 运行清单/记录新增只读证据列，均为 additive；旧数据无迁移，历史行按原值诚实读取。

### B review result

```text
Reviewed Base: 4f11762d617d50555f3b106357e8f41988f7c2f9
Reviewed Head: 2450680f646f6d45e3dfc2180863775bbebb4b5c
Decision: FIX REQUIRED — 2026-11-04
Review scope: complete Task Base..Head manifest/diff and existing entry call chains
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

已实现共享流程规则、自动通道技术结束处理及大部分读回调整；本轮独立验收仍发现以下
两个 P1 阻塞。候选的 Developer 完成报告保留为交接事实，不等同于 B 的验收结果。

**B48.1-01 — 文件结果重复计数，直接 API 的处理进度仍使用旧含义。**

- 真实旅程：发布定义 → POST 现有定义 Run once → 真实 Worker/组织服务处理两个文件，
  本地执行边界分别返回 partial 和 failed → GET 任务中心已结束列表及自动化执行记录。
  Task 正确 completed，但任务中心返回 `total_items=2, partial_items=1, failed_items=2`，
  现有列表会显示“部分成功 1，失败 2”；同一 Task 的自动化记录显示“部分成功 1，失败 1”。
  `failed_items` 仍包含 partial，列表把它当成独立失败数，与单独列出的 partial 重叠。
- 现有直接 API 的授权 → 明确 execute → GET Task 也复现：唯一文件失败后返回
  `completed, total_items=1, completed_items=0, failed_items=1`。该入口仍把成功数当
  已处理数，与本 Task 已启用的 Web `failedItems <= completedItems` 校验不一致。
- 对应原验收：独立文件计数、处理进度、支持的直接 API，以及 Slice RO-3 / AC-5/7/13。

**B48.1-02 — 源目录无法读取，却保存成无错误的已完成任务。**

- 真实旅程：使用临时配置运行现有 `organize <source-directory> --execute`，Storage 的
  源目录 list/list_page 返回权限拒绝 → CLI 正确退出 1 并输出 `Failed: 1` → 读取持久 Task。
  实际保存为 `completed, total_items=0, error=None`，无法从任务历史找回源目录读取失败。
  这不是健康空目录，也不是已经证明范围完整的单文件失败。
- 直接 CLI 收尾没有接收本次扫描的范围/错误事实，只按文件列表（空列表直接 completed）
  收尾；`PersistentTaskCoordinator.finish` 同样把 `scope_proven_complete` 固定为 True。
  共享规则的纯函数测试并不能证明真实入口传入了正确的范围事实。
- 对应原验收：根目录/完整遍历失败仍为流程失败，以及 Slice RO-1/2 / AC-4/5/13。

#### Developer 修正指导（同一 Task）

1. **统一计数含义并接通现有入口。** 保留 `failed_items` 已有的失败/部分成功汇总兼容含义，
   列表展示独立“失败 N”时使用仅 failed 的文件事实；可复用现有 partial 计数作明确推导，
   或增加必要的最少只读字段，同步 API/解码。不要通过改文案掩盖重复，也不要悄悄改变旧字段
   的不同消费者。同步修正 `ManualOrganizeExecutionService._task_after_item` 的非 kernel
   当前入口（含其现有中断收尾调用）：已处理数应含所有已结束项，成功数另计。
   核对任务中心列表/详情、直接 Task API、自动化记录对同一文件总体的结果一致。
2. **让范围事实到达收尾边界。** 从现有 CLI 调用的真实扫描结果传递“范围可证完整/范围失败”
   及有界原因，接入共享流程规则；同步核对 coordinator 的 finish。根目录或子树无法完整
   枚举时保存 failed 和可读原因，不能保存成健康 0 项完成，不能执行尚未证明完整的前缀。
   已证明范围完整的单文件技术失败仍 completed；合法空范围仍 completed。
   保留已有 CLI 明确选择的范围/limit 语义，不把修正扩大为新扫描或恢复系统。
3. **补真实入口回归。** 在现有 Run once 集成测试和任务中心组件/浏览器旅程中补
   “1 partial + 1 failed”及“7 success + 2 partial + 1 failed”；同 Task 两处分别显示
   正确独立计数，已处理数等于总量，未知效果提醒保留。现有直接 API 的授权/execute/readback
   补单项失败与混合结果；不要仅调用 `_task_after_item` 或手工种 completed 行。
   CLI 补根目录拒读、子树拒读、正常空目录，并断言持久状态/原因、零不当媒体变更和
   既有 owner/取消保护；实际 file-local 故障仍 completed。
4. **受影响验证后交新检查点。** 建议在原有模块中补回归，运行下列精确受影响命令；
   实际修改其他消费者时追加对应测试及 changed-file Ruff/ESLint/Prettier 检查。
   修正轮测试耗时须小于该轮总耗时的 50%；全量/产物门禁继续由 B 负责，不交回 Developer。

```sh
.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_manual_organize_execution tests.test_automation_entrance_recovery tests.test_task_flow_status tests.test_final_integration tests.test_task_persistence tests.test_task_scheduling_fencing
```

`web/` 下：

```sh
npm run test -- run src/entities/operations/task.test.ts src/entities/operations/run.test.ts src/features/operations/OperationsInventory.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

不得删除/放宽 decoder 校验来接受旧进度数据，不把 partial 改成 failed，不改变文件 Result、
未知效果、不重放或源历史规则；不修改 Slice/Roadmap/Progress、预先实现成功率或规划下一 Task。

#### B 实际验证和剩余门禁

- 仓库/分支：`/Users/songzhidong/mediaflow` / `main`；开始 HEAD 即 Reviewed Head，tracked 干净，
  工作区/Git 可写。原有未跟踪 OS/log/reference/output 文件及 `15` 全部保留、不纳入检查点。
- 根目录运行 `.venv/bin/python -m unittest tests.test_task_flow_status tests.test_final_integration`：
  **26 通过，0 skip，0 失败，0.508 秒**。这验证已有规则/集成用例通过，但未覆盖上述阻塞。
- 根目录运行 `PYTHONPATH=. .venv/bin/python .git/validation-evidence/2450680f646f6d45e3dfc2180863775bbebb4b5c/b-review-20261104/reproduce.py`：
  实际从 Run once、注册的 CLI organize、直接 API authorize/execute/readback 三条现有链路
  复现上述数据；最终运行 0.219 秒。仅使用临时 SQLite/Storage、fake Provider 和本地故障注入，
  没有读取用户数据库/媒体或调用真实外部服务。
- `python3 scripts/check_governance.py`、`git diff --check` 及对 Reviewed Base..Head 的
  `git diff --check` 均通过；本轮 tracked 变更仅 `TASK.md`。
- 原始脚本/输出和 focused-unittest 日志保存在本机忽略目录
  `.git/validation-evidence/2450680f646f6d45e3dfc2180863775bbebb4b5c/b-review-20261104/`。
  不声称远程可访问。产品测试和复现（含接线试跑）累计不足 3 秒，低于本轮审查耗时的 50%。
- 按工作流 §6 的已证实阻塞提前返工规则，**完整 Python/Web/E2E、桌面/窄屏截图、wheel、
  Docker/restart/security 门禁本轮未执行，保持待验收**；Developer 自报全量结果不替代 B 的
  匹配验收。修正候选仍须按原 T4 计划完成 B 门禁，当前不授予 Task PASS。

全部 Slice 结果重评：RO-1 的大部分正常/技术结束规则已有实现，但上述真实入口仍有缺口；
RO-2 的目录范围失败未满足；RO-3 的独立计数/处理进度未满足；RO-4 的记录流程状态已改但
本 Task 验收未完成，成功率计算仍明确留在后续范围。故本轮保持当前 Task 返工，
不规划下一 Task，也不提交 Slice Closure Packet 或宣布 Slice 完成。

### Workspace and activation validation

仓库 `/Users/songzhidong/mediaflow`，分支 `main`；激活开始 HEAD 为
`037efb20280310f5c2f8d69624cf0449a191b3b6`，已提交 ACTIVE Contract 为上述检查点。
原 Task Base 不变；其后到启用前没有代码/测试变更，实际代码缺口和计划仍适用。
治理预检及 ACTIVE Contract 提交后检查 PASS，开始时 tracked 文件干净。预存未跟踪
OS/log/reference/output 文件及 `15` 保留且不加入检查点；私有配置、用户数据库/媒体不读取或修改。
激活只更新文档状态、TARGET 标签/链接及当前指针；本地链接/锚点、命令引用的现有路径
（明确标出的新增测试除外）、`python3 scripts/check_governance.py` 和 `git diff --check` 均通过。
本次未开始产品实现，未执行产品测试、push 或部署；Developer/B 的上述测试计划保持待执行。
