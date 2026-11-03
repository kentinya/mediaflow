# NO ACTIVE IMPLEMENTATION TASK

```text
Status: NO ACTIVE IMPLEMENTATION TASK
Last Task: 47.6 — Three system runtime settings and stale-age removal
B Decision: PASS
Reviewed Task Base: c8657032dae768d93b12387a5e58db502e23a7ee
Reviewed Implementation Head: 5134c78b22057781d472e6ebf61a1799d9e40324
Slice Decision: 47 — PASS / CLOSED by independent A Final Review, 2026-11-03
Selected Slice: 48 — Task Flow Status and Automation Success Rate — ACTIVE
Next Action: B REVALIDATES AND PROMOTES AUTHORIZED TASK 48.1 DRAFT AFTER ACTIVE CONTRACT CHECKPOINT
```

The complete B review, actual T4 results/limits and six-outcome Closure Packet remain at
`749507ca9000329484bdc9fb7ad5c44e0efc0cd0:TASK.md`. Slice47's whole-range A review, immutable
Base and accepted Head remain at `ba84272721961c970f1eb85d616a0d129523ab92:SLICE.md`.
[SLICE.md](SLICE.md) is being activated at the user's request. This draft remains inactive until
the ACTIVE Contract is committed and B promotes it. Independent minor bugs retain their separate workflow.

## Task 48.1 草案 — 任务流程结束与文件结果分开

本节是用户要求 Codex 代替 B 编写的第一版计划。用户现已要求激活，先提交 A 所有的 ACTIVE
Contract，再由 B 核对原基线、重新运行治理检查并启用本 Task；此检查点仍保留上方
NO ACTIVE IMPLEMENTATION TASK，不开始开发。范围与验收不变。

Authority: committed [Slice48](SLICE.md) RO-1–3，以及 RO-4 中执行记录与 Task 状态一致的部分；
[Development Workflow](docs/development-workflow.md) 负责生命周期、测试和检查点。
本 Task 不承担自动化成功率计算的交付，也不据此宣告整个 Slice 完成。

```text
Task ID: 48.1
Task Type: SLICE
Parent Slice: 48
Status: PLANNED
Task Base: 4f11762d617d50555f3b106357e8f41988f7c2f9
Difficulty: High
Test Level: T4
Planner / Reviewer: B — Codex performs planning at user request; review NOT STARTED
Development Authorization: DRAFT / PLANNING ONLY
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

### Actual gaps and implementation scope

以下是本草案基线的实际缺口；实现时沿这些真实调用关系接入共享规则，不按文件拆交付。

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
草案本身不声称产品测试通过。使用临时 SQLite/Storage、fake/本地 Provider 和确定性故障注入。

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
可操作且不溢出。种数据读取可验证分页，但结算和继续必须有真实应用调用/Worker 证据。

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

NOT STARTED。正式启用并完成实现后，填写实际检查点、READY FOR B REVIEW、改动和关键选择、
受影响测试命令/结果、已知风险和本 Task 剩余工作；完整验收留给 B，不自批 PASS。

### B review result

NOT STARTED。当前只有规划，没有候选实现、验收或 PASS 决定。
正式提交候选后按模板填写 Reviewed Base..Head、PASS/FIX REQUIRED、真实验收和阻塞项。
Task PASS 时重新核对整个 Slice；本计划不预设 Slice 已完成，也不代替 A Final Review。

### Planning workspace and validation

规划仓库 `/Users/songzhidong/mediaflow`，分支 `main`，检查基线为上述 Task Base；
治理预检 PASS，开始时 tracked 文件干净。预存未跟踪 OS/log/reference/output 文件及 `15`
保留且不加入检查点；私有配置、用户数据库/媒体不读取或修改。
本次只写 `TASK.md`；草案本地链接/锚点、命令引用的现有路径（明确标出的新增测试除外）、
`python3 scripts/check_governance.py` 和 `git diff --check` 均通过。
规划未执行产品测试，没有产品改动、push 或部署。
