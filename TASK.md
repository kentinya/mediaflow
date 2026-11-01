# Task 47.3 — 自动入口统一到现有 Task 引擎

Authority: committed [SLICE.md](SLICE.md), especially RO-1/RO-2/RO-3 and the necessary RO-5
readback; [Development Workflow](docs/development-workflow.md) governs planning, review and closure.
The user confirmed on 2026-10-31 that B should establish the next active Task, not retain a
planning-only draft. Task47.3 remains the same formal Task within committed ACTIVE Slice47;
the partial checkpoint received FIX REQUIRED below. Developer returns it to IN PROGRESS for the
same-Task correction; B owns independent review. No delegation, push or deployment is authorized.
Recheck intervening commits without silently repinning the Task Base.

```text
Task ID: 47.3
Task Type: SLICE
Parent Slice: 47
Status: IN PROGRESS
Task Base: dfcfebbdb9c879b38806e29c7b41c9192aeca83e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Preflight and actual-code gap

Planning/activation checkpoint: repository `/Users/songzhidong/mediaflow`, branch `main`,
starting HEAD equals the Task Base above; workspace/Git writable; governance preflight passed.
The initial planning turn had no pre-existing tracked edits; at activation the only tracked edit
was B's preceding Task47.3 draft in `TASK.md`, promoted in place without changing its Base or scope.
Existing untracked OS files, logs, `15`, reference PNGs and the imagegen ZIP remain unrelated and
untouched/unstaged. No push or delegation authorized.

- `application/automation.py`: `IntervalScheduler.tick()` / `_tick_automation_definitions()` still
  construct Jobs, then call `enqueue_due_schedule()` / `enqueue_due_automation_definition()`.
- `application/automation_run_once.py`: `admit_execution()` creates a Pending Task plus Job through
  `admit_automation_run_once_job()`; request reconciliation and documents still start from that Job.
- `application/task_scheduling.py` already supplies Task admission/capacity/claim/fence semantics;
  `application/manual_task_engine.py::ManualTaskEngineWorker` connects Files discovery/execution to
  it. The module's initial kernel-only docstring is outdated: inspect actual callers, not that prose.
- `final_cli.py`: the resident Worker still mixes the manual Task consumer with `AutomationWorker`;
  `_run_queued_workflow()` can invoke `final_main()` and parse `Task ID:` from its printed output.
  Direct `organize`, `organize --execute`, `jobs submit organize`, and administrative recovery are
  separate actual CLI paths; their differing analysis/authority semantics cannot be flattened.
- `interfaces/service_api.py`: definition Run once and its readback use `AutomationRunOnceService`;
  `POST /api/v1/jobs` organize requires remote execution permission, enablement, `execute=true`, and
  the execution token. `application/execution_authorization.py::submit_organize()` consumes that
  ticket into a Job. Preserve these gates when changing the durable work identity.
- `infrastructure/sqlite_runtime.py` is schema55. `_shared_capacity_use_locked()` already counts
  Task scheduling plus non-duplicated legacy Job capacity. Extend this existing boundary; do not
  replace it with independent limits. Occurrence, record/query, log and notification relationships
  must follow the actual persisted IDs, not command-name/timestamp guesses.

All code paths above are relative to `mediaflow/`. This is an entry map, not a file allowlist.
Requirements: `V2-TASK-001/002/003/005/006`, `V2-AUTO-010/011`, `V2-OPS-014–017`,
`REQ-SCHED-001/004/005`, applicable task/result/API/safety rules; interpret CURRENT through the
Slice47 TARGET in Architecture and Product Experience. AC-9/10/11 full Job migration/removal is
not claimed by this Task.

## Goal

让本 Task 之后新受理的 Scheduler due、Automation Run once 和受支持 API/CLI 整理，
与 Files 手动整理共用现有 Task-owned admission、claim/heartbeat/fence 和整理引擎。
一次到期发生点或一次明确 Run once，从业务分析之前就有一个稳定 Task，贯穿发现、分析、
执行、结果和四类续作；不再先排新 Job、后创建/寻找 Task。

用户链路：Automation 保存/启用定义或点击 Run once → 看见同一 Task 的排队/发现/分析/执行
及每项结果 → 成功、健康空范围、部分失败或不确定效果分别如实呈现。四类问题通过既有
决定→分析→精确摘要→明确继续处理；技术失败只提供实际原因、已知效果和允许的下一步。
刷新、重连、服务重启和未知提交结果核对不能发起第二次工作。Files 的初始摘要/选择确认保持不变。

## Implementation Scope

1. **复用 Task 准入与队列，不重建内核。** 在现有 `TaskSchedulingService` 和 repository
   原子事务中持久化 Task、触发来源、principal/request、源范围/上限、精确配置/定义 pin、
   必需的 display/occurrence/一次性授权证据。不得将 Storage/Provider I/O 放入事务。
   同一精确请求先核对已受理身份，队满时仍能找到原 Task；同一键但内容冲突明确拒绝。
2. **Scheduler 直接受理 Task。** 同时覆盖受支持的 legacy interval/Cron schedule 和 managed
   definition due 入口；原子提交 Task/队列、occurrence、due advance 和已有审计关系。
   继续复用实际的时区、到期计算和 publication authority。队满不生成 occurrence/孤儿 Task，
   不推进 due；配置/权限失败可保留原有独立诊断，但不能伪造成功准入。Scheduler 只管何时触发。
3. **Run once 直接受理同类 Task。** 保留当前 saved definition/principal/request/publication
   核对、disabled 可运行一次、`min(definition itemLimit,100)` 和完整遍历预算，不推进 due。
   命令自身提供一次运行意图，不增加初始二次确认/独立 grant。旧 analysis-only preparation
   只保留原语义，读取或切换引擎不能自动执行它。
4. **接通真实 API/CLI/Worker。** 新整理执行提交不再写 Job；直接 CLI 的执行请求、remote
   token organizing、现有后台执行提交等实际支持的入口调用同一 Task application 行为。
   application 调用者直接取得结构化 Task 身份，不再从 CLI 打印文字提取 Task ID；这不要求
   把面向用户的 CLI 文本输出改成 JSON，也不取消原有退出/返回语义。不带 `--execute` 的
   CLI 分析及既有 analysis-only preparation 只复用分析管线并保留原分析记录，不因共享能力
   进入 organizing 执行队列/Task Center 人口或取得执行权。保留各入口原有 authority、
   scoped limits 和安全重复语义。旧 Job 命令/路由若需在本
   Task 提前切换或拒绝新提交，必须给出可用 Task 等价入口及明确返回，不能悄悄失去功能。
   泛化现有 Task Worker 的 trigger context，消费 admitted pin，保留 Task/discovery 和父 Worker
   长调用心跳、当前 claim fence。不要让 manual Worker 抢到自动 Task 后按“缺少手动关联”失败。
5. **保留入口差异，复用生产管线。** 自动入口保留 saved filtering、primary/attachment、
   source ownership、完整范围、真实稳定观察及适用的一次 `(0,60]` 秒等待/重扫。due/Run once
   在合法初始意图下自动处理 ready items，Files 仍先确认精确摘要；共同使用原策略管线及
   OrganizerExecutor，不能另起自动版解析/规划/执行器。
6. **贯穿控制、恢复与原始记录。** 所有新自动 Task 的取消、claim loss、业务等待与四类型
   continuation 复用现有 same-Task 路径，保留 source/version/pin、attempt/item/result/附件
   关系和不可重放约束。Enabled/current permission/disable-removal ancestry 在剩余 effect
   边界仍有效；Run once 与 schedule disable 的区别不变。原始执行结果/实际起止时间/已知
   效果冻结为原执行事实，后续恢复不能重写或多算一个原运行。
7. **完成必要读回与兼容。** 更新 Automation inventory/latest/metrics/records、Task Center
   八视图、Dashboard、任务日志/JSON、API/CLI、readiness/settings 的受影响查询，使新工作
   不依赖 Job row 才能显示/控制，队列容量/实际 resident adoption 说的就是 Task 语义。
   保留不可变旧 JSON/digest/parser 和 overrides。必要时可做最小、版本化、失败原子且可
   reopen 的 schema55 增量存储变更，但不得借此开始全部历史 Job 转换/删除或新建竞争生命周期。
   只改为显示/控制新 Task 所必需的关联和查询，不重做这些页面、全套设置或已有恢复流程。

### Transitional boundary

本 Task 的“无 Job”验收对象是所有新受理的整理及其后续四类处理，不是声称仓库已彻底没有
Job。既存历史/旧 queued Jobs 及其安全处理、原关联和已有共享容量防重保留；不新增 Job
兼容执行器、不双写、不让新提交回落旧队列、不把旧工作静默重置/丢弃。全面迁移旧历史和
删除原有 Job reader/dispatcher/schema/surfaces 属于剩余 RO-4/RO-5；不能据此给 Slice PASS。

### Existing-entry coverage and disposition

以下清单来自当前 CLI parser/dispatch 和 API route，不代表新增产品入口。按真实输入及现有
合法条件逐项核对；不能只验收 Automation 主按钮，也不能把解析到的命令一律视为可执行。
对每项说明实际处置、权限/授权、返回身份和读回，并给出对应受影响测试；新提交的整理执行
走 Task，旧历史的兼容边界保持上述限制。不为清单里的每个命令另建 Task 或实现一套新流程。

| 当前实际入口 | 本 Task 的处置/必须保留的区别 |
|---|---|
| Files 手动整理及其既有确认链 | 复用已接好的 Task 路径，回归摘要/选择确认、精确请求核对；不重做交互。 |
| `scheduler tick` / `scheduler run` → `IntervalScheduler` 的 interval/Cron 及 managed definition due | 新整理原子受理一个 Task，保持时区、occurrence/due 和权限约束；不能只切换其中一个分支。 |
| `POST /api/v1/operations/automation/task-definitions/{id}/run-once` 及该功能已有 GET/list/detail | 新运行直接进入 Task，查询仍找到原运行；disabled、一次运行意图、上限及不推进 due 保持。 |
| `organize --execute`、`batch organize --execute` | 统一到 Task 整理执行，保留路径/全资源库两种实际源范围、limit 和显式执行意图。 |
| 不带 `--execute` 的 `organize` / `batch organize`，以及现有 `jobs submit organize` | 逐项保留原有非执行授权/分析或合法拒绝语义，不能因命令含 organize 而获得执行权；分析只复用管线并保留证据，不新增 Job 或整理执行队列项。 |
| `POST /api/v1/jobs` 的 remote organize 提交分支 | 新整理改用 Task；remote enablement、当前权限、`execute=true`、执行票据和 limit 全部保留。若替换旧提交路由，须在同一 Task 提供并测试同等受限的 Task 入口与明确指引，不留新 Job 后门。 |
| `tasks retry-request` / `tasks retry-failed` | 核对既有允许动作、源/结果/授权证据；新 Task 的合法四类续作必须回到同一 Task。不能仅凭 retry 字样归为四类业务恢复，不能据此增加技术失败/uncertain 的重放能力；历史工作不借此批量迁移。 |
| `POST /api/v1/tasks/{id}/cancel`、已有 item recovery 的 decision/prepare-summary/authorize-organize/continue 和 `POST /api/v1/tasks/{id}/recovery/continue-batch` | 新自动 Task 能通过原生控制/四类流程处理；保存/分析无修改效果，执行仍要合法明确继续，不能另建 Job 或顶层 Task。保留 backend-offered 动作边界，不能恢复 Pause/resume。 |
| `jobs cancel` / `jobs requeue`、`POST /api/v1/jobs/{id}/cancel` / `requeue-stale` | 过渡期只处理其原有合法历史对象，不把新 Task 转回旧队列；尤其 API stale requeue 现有限定于 File correction continuation，不扩大为任意整理重试。新 Task 使用 Task 控制；若缺少完成原支持能力的等价入口，只补最小必要入口并验证权限和非重放。 |
| 原有 Task/Job list/show/GET、Automation records、Dashboard、logs/export/readiness | 新 Task 不依赖 Job row 才能读回；原 Job 标识仅按可证明关系展示历史，保留当前只读能力。不把查看当作提交、重试或授权。 |

## Acceptance Criteria

- [ ] **单一新工作：** 首次成功受理新的整理执行工作时，业务规则尚未就绪也要创建且只创建
  一个 durable Task；精确重复请求返回原 Task，其后四类恢复/续作不得另建顶层 Task。
  新整理工作及其四类续作不新增 `automation_jobs` 行，也不另排竞争队列。manual 的精确
  摘要确认、remote ticket、due 和 Run once 权限区别保持。CLI analysis-only/preparation
  保留原分析记录与零修改语义，不混入 organizing 执行队列/Task Center 人口或取得执行权；
  此项不禁止系统受理其他有明确意图、通过源所有权/非重放检查的独立新工作。
- [ ] **真实入口完整：** 对上表逐项核对现有合法/非法输入、权限、实际处置、Task 身份/
  历史读回及必要的失败/重复行为；不能只接主按钮而遗留可受理新 Job 的旧提交分支。
  若换入口，保留原支持能力和同等权限/安全限制并给出可用指引；已退役或原本不合法的
  命令不为满足“入口覆盖”而恢复成可执行路径。不要求全组合/所有理论崩溃点穷举。
- [ ] **原子到期与重复核对：** 并发 Scheduler ticks/进程重启，一发生点只受理一次、due
  只推进一次；注入提交失败不留半条关系。满队列拒绝新手动/Run once/due 时无孤儿/授权
  消耗，due occurrence/state 不变；已受理的精确重复仍返回原 Task，冲突请求不能混入。
- [ ] **共享容量/Worker：** 各入口、重分析和继续共用 distinct-Task bound；多 item/attempt
  只一槽，完全人等零槽但保留源所有权，混合机器/人等一槽，稳定性等一槽。取消未确认/
  慢 Provider 或在途 Storage 未结束不能提前释放；re-entry 满时保留决定/摘要/结果，
  不消费 execute authority、不暗中注册自动重试。并发 Worker 不产生有效双 owner。
- [ ] **自动意图与安全：** disabled Run once 可运行但不 enable/advance due；Enabled 的
  publication/current principal、scope 和 disable/remove/re-enable 竞态仍阻止旧未执行
  effects。Active/pin 缺失/损坏/变更失败关闭，合法旧 pin 不被新 Active 悄悄替换；
  remote token 受理/消耗与容量原子提交，重复/失效/越界不能扩大权限。
- [ ] **范围与管线：** scope/filter/extensions/attachments/complete traversal/limits/real
  stability 与现有义务一致；ready/unstable siblings、健康空、不可读、溢出和截断可区分。
  不能以 first-N prefix 当成功，也不能由未验证 mtime 推断 stable size。
- [ ] **生命周期与非重放：** 从真实入队/Worker 链验证长批次/单次慢 Provider 心跳、陈旧
  owner 的 heartbeat/item/result/aggregate/control 被 fence；取消保留成功 sibling。
  支持边界的 mutation 前中断只能凭 durable proof 安全续作；dispatch 后缺结果必须
  uncertain/只读检查，timeout/lease/restart 不自动重放，也不恢复已消费授权。
- [ ] **同 Task 恢复与原记录：** 四种问题分别完成决定→分析→摘要→明确继续，顶层 Task
  身份不变，每个文件的 source/version/pin、决定、attempt 和结果可追溯。内部 TaskItem
  ID 可以复用或版本化；若创建后继 ID，须保留原 ID/历史及明确的持久关系，不能重复源所有权、
  丢失旧链接、扩大范围/权限或重复执行。按实际文件核对数量/结果，不强制内部 item ID 相等。
  后续成功不改变原 Automation outcome、真实时间/效果、记录过滤/分页，也不再创建原执行记录。
- [ ] **用户读回：** Automation/Task Center/Dashboard/API/CLI/health/log-export 对新 Task
  一致，pre-start failure 和 unknown admission 有真实证据；刷新/重连/重启不重复提交。
  Web 桌面/窄屏可读：due 不增加每次运行确认，Run once 不增加第二次初始确认，Files
  初始摘要确认和四类恢复的明确继续仍保留；读取无 Provider/Storage effects。原 ordinary-file
  local work、通知、Files summary 和已退役 Pause/resume 不回归。
- [ ] **过渡数据完整：** fresh/reopen/必要增量升级保留原 Jobs、关系、pins、消耗/audit/logs
  和结果；升级失败原权威/schema marker 不变。旧 queued/history 不丢、不虚构合并/权限。
  以实际已有迁移/临时 fixture 验证，不读用户数据库、不靠字符串替换降低断言。

## Required Tests

Follow [test levels and ownership](docs/development-workflow.md#6-test-levels). 以下为计划，
不是本轮已运行结果。探测从实际入口发起；故障注入只放在真实调用链会经过的依赖边界，
不构造不存在的路由/调用组合来阻塞交付。每轮累计测试耗时须少于该轮总耗时的 50%；
记录真实耗时，优先审查/关键复现，再跑分配门禁，不靠空等凑比例。来不及或不可用的
必需门禁保持 pending，不能删断言、加重试掩盖或提前 PASS。

### Developer — affected tests

根目录，先扩展现有测试覆盖上面准入/事务/authority 变化，再执行相关组：

```sh
.venv/bin/python -m unittest \
  tests.test_automation_admission tests.test_automation_definition_occurrence \
  tests.test_automation_execution_intent tests.test_v2_automation_run_once \
  tests.test_automation_definition_execution tests.test_automation_run_once \
  tests.test_execution_authorization tests.test_automation_api

.venv/bin/python -m unittest \
  tests.test_task_scheduling tests.test_task_scheduling_fencing \
  tests.test_manual_task_engine tests.test_processing_worker_readiness \
  tests.test_automation_job_fencing

python3 scripts/check_governance.py
git diff --check
```

每组覆盖准入/到期唯一、disabled Run once、票据不升级权限、Worker fence/容量、手动和
旧 Job 共存回归；新增真实 CLI submission/control 和 API/readback 断言放在直接受影响
测试模块，依照入口处置表核对实际执行、只分析和合法拒绝，不将所有入口强行变成执行成功；
交接时列准确命令。变更 schema 时额外跑 `tests.test_task_scheduling_migration`；
变更 resident adoption 时额外跑 `tests.test_automation_settings_resident`。对修改的 Python
文件执行 `.venv/bin/ruff format --check <changed-files>` 和 `.venv/bin/ruff check <changed-files>`。

若修改 Web 投影/浏览器 harness，cwd `web/` 执行 `npm run typecheck`、`npm run lint`、
`npx prettier --check <changed-files>`、对应文件的 `npm run test -- run <test-files>` 和
`npm run build`；更新并运行直接受影响的真实 Python Automation browser spec，仍使用
`playwright.python.automation.config.ts` 与 `scripts/operations_inventory_harness.py` 的
实际 API/Worker 链，不新增测试专用产品入口。Developer 不承担全 Python/Web/E2E/发布矩阵。

### B — acceptance and full regression

1. 独立审查完整 `Task Base..candidate`（包括测试/harness/doc 与 source/package 的新旧
   调用者），逐项核对上述结果，确认不是改名/换断言后继续走 Jobs。先复现关键阻塞，
   修复保持同一 Task。按入口处置表检查实际 parser/route/dispatch 和相应测试，包含现有
   batch/重试/控制入口，防止遗漏旧分支；不探测虚构接口，不将其升级成额外产品范围。
   新测试的细分断言不能取代用户实际链路。
2. 在临时 SQLite/Storage、fake/local Provider 上从真实 Scheduler、Run once API/Web、
   direct CLI、remote ticket submission 与 resident Worker 运行；核对数据库 Task、
   occurrence/due、授权消费、原 execution record、结果/附件及源/目标的实际变化。覆盖
   并发、队满、权限/配置变化、取消、长调用、重启和上述 uncertain 非重放边界。
3. 根目录执行 workflow 的 [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)：
   全 Python/static/examples/forbidden-dependency、Web/full E2E、wheel/source-external consumer、
   Docker fresh/restart/适用升级/security。如本 Task 无新 schema，reopen/原有兼容升级仍需
   验证，但不将完整 RO-4 Job-removal 迁移提前变成本 Task 门禁。
4. 完成 Web build 后在 `web/` 运行真实原生 Automation journeys：

   ```sh
   npm run test:e2e -- --config=playwright.python.automation.config.ts \
     tests/e2e/automation-lifecycle.python.spec.ts \
     tests/e2e/automation-run-once.python.spec.ts
   npm run test:e2e -- --config=playwright.python.config.ts \
     tests/e2e/automation-workspace.python.spec.ts \
     tests/e2e/automation-settings.python.spec.ts
   ```

   桌面/窄屏检查 Automation/Task Center 的真实 Task 读回、记录和允许动作。沿用现有
   harness；若旧 spec 仍断言旧分析交互/Job identity，更新为真实用户结果而非删弱安全义务。
   full gate 已覆盖的 focused case 不机械重跑。证据按 workflow 留在稳定 ignored
   `.git/validation-evidence/<candidate>/<run>/`，记录 SHA/命令/cwd/结果/耗时/未完成项。
5. PASS 后重评 Slice47 全部 RO-1–5 和 AC-1–19；RO-4/剩余 RO-5 尚未完成就说明缺口，
   不替 A 关闭 Slice，不在本 Task 预先展开更多 Task。

## Non-goals

- 不做全部 schema53 historical Job 迁移/Job table-index-FK/domain/dispatch/API/CLI/Web
  删除，不声称完成 AC-9–11；仅本 Task 必需的新 Task 入口/读回切换和增量 schema 在范围内。
- 不清历史、不猜关系、不加 legacy compatibility executor、第二队列/整理引擎/恢复系统。
- 不改已确认的摘要交互，不新增“有效但实际错误元数据”的新人工更正功能。
- 不新增 recovery type、自动 uncertain replay、attachment-only retry、万能 rollback。
- 不恢复 Pause/resume、Scan/Preview/FileIndex，不扩展 Provider/Storage/并行策略或改进程监督。
- 不修改 A-owned Slice/Roadmap/Progress 或既往验收事实，不实现/规划后续 Task。

## Developer Completion Report — Round 5

**Status: READY FOR B REVIEW.** Same-Task correction checkpoint for the two B blockers of
review `807d8951`; not a self-approved PASS.

```text
Task Base: dfcfebbdb9c879b38806e29c7b41c9192aeca83e (not repinned)
Code/test checkpoint: 92399f75 (fix(task47.3): direct/remote organize continuation and bounded jobs-submit refusal)
Report checkpoint: this documentation commit
Pre-existing untracked files: preserved, unstaged. No push/deploy/self-approval.
```

### Corrections implemented

1. **P1 — CLI/remote organize Tasks now continue their own saved decision.**
   - `ManualTaskContinuationService._continue_kernel_analysis` (renamed from
     `_continue_automatic_analysis`) accepts a manual Task exactly when its durable
     `operations_run_display.origin_kind` proves a `direct-organize`/`remote-organize`
     admission (the row is written in the same admission transaction, never guessed).
     Files Tasks keep their linked-discovery branch; any other manual origin — including a
     missing/unreadable display row — keeps the bounded `no_linked_preparation` refusal.
     SCHEDULE/RUN_ONCE behavior is unchanged.
   - The rest of the chain is the already-proved shared path: kernel `requeue` with the
     authenticated `continuation_actor`, the resident continuation pass under the live
     claim fence, the durable preparation row, the actor-bound confirm and the same-Task
     execution. No new gate was added and no Files/Run once/due recovery changed.
   - New `tests/test_automation_entrance_recovery.py` drives both entrances end to end on a
     production-shaped layout (one SQLite file holds the managed revisions and the runtime;
     the JSON bootstrap names that database):
     - direct CLI: real `--config … organize --execute --limit 5` → one Task
       (`trigger=manual`, `principal=cli`, origin `direct-organize`) → waiting_recognition →
       API decision A → continue 202 naming the same Task (`continuation_actor="admin"`,
       capacity 1, zero Jobs, zero mutations, source untouched) → duplicate continue 409 →
       real production `_automatic_task_runner` continuation pass → `waiting_confirm` +
       prepared summary (`actor="admin"`, admission principal stays `cli`) → foreign
       operator confirm 403 `preparation_actor_mismatch` → admin confirm 202 → real
       `ManualTaskEngineWorker` execution → file moved, one SUCCESS Result, Task settled,
       capacity 0, zero Jobs; the confirmed summary reads back with its execution link.
     - remote ticket: real `POST /api/v1/jobs` with `execute=true`, REMOTE_EXECUTE principal
       and a one-time token → 202 Task identity (`principal=remote-execution`, origin
       `remote-organize`, pin = current Active revision, authorization consumed) → real
       Worker initial pass → waiting_recognition → decision → continue 202 → continuation
       pass → summary → confirm 202 → same-Task execution → one Result, zero Jobs; a
       replayed submission with the consumed token returns 400 and admits nothing.
     - fail-closed guard: a manual Task whose durable display origin is missing or foreign
       (`definition-run-once`, `legacy-schedule`) keeps the bounded refusal (unit-level
       boundary test with fakes; no real entrance produces that shape today).
2. **P1 — the original `jobs submit organize` entrance no longer admits new Jobs.**
   - `final_main`'s live submit branch now refuses before opening the repository: exit 2,
     bounded message naming the usable equivalents (`organize` zero-mutation analysis,
     `organize --execute` explicit execution, the remote-ticket API) and the retained
     historical read paths (`jobs list`/`jobs show`). No Job row, no Task, no queue entry,
     no execution authority, no Storage effect — for valid and invalid limits alike.
   - Historical Job semantics stay inside the transition boundary: `jobs list`, `jobs show`
     and `jobs cancel` keep working on retained rows (new CLI assertions seed and verify a
     historical Job end to end).
   - `tests/test_queued_job_execution_boundary.test_api_command_matrix_and_one_shot_organize_authority`
     still asserted the retired Job response (`execute_authorized`, one new Job row); this
     pre-existing failure was reproduced on HEAD in a throwaway worktree before updating its
     identity/readback assertions to the supported Task entry. Every permission, token,
     field-validation and one-shot-consumption assertion is unchanged.

### Actual validation（本轮命令与结果）

```sh
.venv/bin/python -m unittest tests.test_automation_entrance_recovery
  tests.test_operator_job_submission tests.test_v2_automation_run_once
  tests.test_manual_task_engine tests.test_recovery_continuation
  tests.test_task_scheduling_fencing
# Ran 165 tests — OK（含两条新入口全链路、拒绝入口与 fail-closed 守卫）

.venv/bin/python -m unittest tests.test_automation_definition_occurrence
  tests.test_automation_workspace_read_model tests.test_operations_run_inventory
  tests.test_operations_task_center
# Ran 130 tests — OK

.venv/bin/python -m unittest tests.test_batch_cli tests.test_execution_authorization
  tests.test_automation_api tests.test_task_scheduling tests.test_automation_task_admission
# Ran 87 tests — OK

.venv/bin/python -m unittest tests.test_automation_admission
  tests.test_automation_definition_occurrence tests.test_automation_execution_intent
  tests.test_automation_definition_execution tests.test_automation_run_once
  tests.test_automation_api tests.test_task_scheduling_migration
  tests.test_processing_worker_readiness tests.test_automation_job_fencing
  tests.test_manual_operations
# Ran 183 tests — OK

.venv/bin/python -m unittest tests.test_automation_settings_resident
  tests.test_manual_organize_execution tests.test_manual_organize_preview
  tests.test_manual_operations
# Ran 93 tests — OK

.venv/bin/python -m unittest tests.test_queued_job_execution_boundary
  tests.test_scan_retirement tests.test_preview_retirement
  tests.test_resident_correction tests.test_configuration_snapshot
# Ran 74 tests — OK（含修正后的 API 命令矩阵）

.venv/bin/ruff format --check <changed files>   # 5 files already formatted
.venv/bin/ruff check <changed files>            # All checks passed!
.venv/bin/python -m compileall -q mediaflow tests   # OK
python3 scripts/check_governance.py             # PASS
git diff --check                                # clean
```

Real-entry probes (same fixture and entrances B used, recorded in
`.git/validation-evidence/dev-round5-probes/`): before the fix, CLI continue returned
409 `no_linked_preparation` and `jobs submit organize --limit 1` exited 0 with one new
pending Job; after the fix, continue returns 202 on the same Task with zero Jobs/effects
and the submit entrance exits 2 with zero Jobs/Tasks/effects. Timed tests plus probes this
round total ≈145s against ≈26min wall time (review/reproduction first), well below the 50%
budget; no idle waits were used.

### Remaining work / risks（如实陈述，未自评 PASS）

1. Metadata / Metadata-correction / Conflict 的自动续作仍共用同一条已验证通道，但各自尚无
   独立 API 端到端测试（Round 4 遗留，本轮未扩大）。
2. direct CLI 在 admit 与 claim 之间崩溃时仍由常驻 Worker 恢复；该恢复分支仍无独立测试
   （Round 4 遗留）。
3. Inventory/latest/metrics/Dashboard/readiness 的 Job-less 读回仍未逐一独立复核
   （上轮遗留风险，属 B 的更广验收）。
4. `jobs submit organize` 的拒绝发生在配置解析之后、仓库打开之前；配置本身不可用时仍先
   报配置错误，这是既有解析顺序，未为本 Task 改动。
5. 历史 Job 兼容边界与 RO-4 全量迁移/删除保持过渡态；Web 投影未改，故未跑 Web 构建/E2E。
6. B 仍负责 T4 full Python/Web/E2E/wheel/Docker/native 门禁与独立审查；本轮未运行这些门禁。

### Scope statement

无 schema 变更（延续 schema56）；未读写用户数据库/生产媒体；未修改 A-owned
Slice/Roadmap/Progress；未 push/部署；预存无关未跟踪文件保持未暂存。B 负责本 Task 原
T4 验收与独立审查。

## B Review Result

```text
Reviewed: dfcfebbdb9c879b38806e29c7b41c9192aeca83e..c746b61e72c2a88d5e583bbe9877ce074d7a74e1
Implementation checkpoint: 92399f7532c3d1ce7730aed80066ccf353aa217a
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

B reassessed the complete 38-file Task Base..Head change, building on the preceding full-range
reviews and inspecting every change in the current six-file correction. The successor
`92399f75..c746b61e` changes only `TASK.md`; executable inputs are identical. Review started on
main with no tracked edits. All pre-existing untracked OS/log/reference/archive files remain
untouched/unstaged. Governance passed; Base/scope/High/T4 remain unchanged.

### Verified corrections

- 上轮两个 P1 已修复：真实 CLI 和 remote-ticket API 整理分别完成 Recognition 决定 →
  同 Task 分析 → 精确摘要 → 明确确认 → 共享 Worker 执行，产生 SUCCESS Result；全程无新 Job。
  MANUAL 续作仅接受持久记录证明的 direct/remote organizing 来源，Files 保留原 discovery，
  缺失/不匹配来源仍拒绝。不是将所有 MANUAL Task 都放行。
- 真实 `jobs submit organize` 现在明确拒绝，指向可用的分析/显式执行命令，不创建 Job、
  Task、队列或效果；有效/无效 limit 和历史 Job list/show/cancel 的受影响测试通过。
- B 补验实际 Run once 的 Metadata 候选选择和 Conflict rename：决定、继续分析、读取摘要
  均无修改；明确确认返回 202，原 Task 经共享 Worker 完成，分别一个 SUCCESS Result。
  这些成功结果解除相应链路疑虑，不代替全部 T4 门禁或声称所有 Metadata-correction 情况已覆盖。

### Remaining Task blocker and actionable correction

**P1 — 同一来源的占用核对和 TaskItem 登记没有原子完成，两个任务可同时占用同一文件。**

用户触发：同一来源短时间内发起两次 Run once（不同合法请求），两个已有 Worker 并发处理。
两次 Task 受理本身允许；发现具体文件后只能有一个未完成工作拥有该来源。本轮从真实
Run once API 分别受理两个 Task，交给真实 `ManualTaskEngineWorker` 和生产
`_automatic_task_runner`，仅在实际 repository 所有权查询返回之后控制线程交错。
配置无匹配 Recognition rule，两个查询均答“未占用”，随后两个 Task 均进入 waiting_human，
各有一个 waiting_recognition item；Storage、路径和已验证 occurrence 完全相同。
这使操作者面对同一文件的两份可处理工作，违反现有“人等释放容量但保留来源占用”及
atomic source ownership 合同。本次效果列表为空，不声称已发生双重移动或数据丢失。

根因位于 `KernelTaskCoordinator.begin_item()`：先调用 `find_owned_source_work()` 读检查，
再调用 `TaskSchedulingService.begin_item()` / `upsert_scheduled_item()` 写入。
后者事务验证当前 claim、同 item 的 source/attempt/history，却没有再核对其他 Task 的
来源占用。Task ID 派生的 item ID 只能防止同 Task 重复行，不能阻止两个 Task 拥有同源。
原来的 `claim_task_item_with_ownership()` 已有事务内共享占用检查，新协调器没有保留它。
这属于原 scope 4/5/6、安全不变量及共享 Worker/ownership 验收缺口，不新增并发策略或功能。

**预期用户行为与验收示例（本轮开发指导）：**

- 同一精确请求重复提交，返回原 Task；两次不同的合法 Run once 请求可分别受理为
  Task 1、Task 2，不因来源范围重叠就一律拒绝整个请求。
- 两个 Worker 同时发现同一已验证文件 A 时，只有一个能原子取得 A 的占用并登记可处理
  TaskItem；以成功提交该事务为准，不要求固定由 Task 1 或先点击的请求获胜。
- 未取得 A 的 Task 对 A 持久记录现有 `source_already_organizing` 拒绝结果，用户能看懂
  “此文件已有未完成的整理任务，本次未处理”。不再为 A 查询元数据、生成第二份可操作的
  待识别/待确认工作或执行文件修改；必要的只读发现/来源核对仍允许。结果应说明本次无
  文件修改，指引有权限的用户处理原工作；不泄露无权查看的 Task 信息，不给无依据的重试。
- 若拥有 A 的 Task 停在等待识别、元数据、分类决定或确认，A 仍归它负责；用户的决定 →
  分析 → 摘要 → 明确执行在原 Task 中继续。完全人等可以不占队列容量，但不能释放 A
  给另一 Task；超时、重启或 Worker claim 变化也不能单独成为重放/抢占理由。
- 对 A 的拒绝只影响该文件。另一个尚未被占用的文件 B 仍可按自己的权限、来源和状态
  独立处理；批次结果如实保留每项成败，不回放已成功的 sibling。
- A 的原工作结束后，已拒绝 A 的 Task 不会自动等待并重跑 A。后续操作仅遵循现有
  明确请求及来源/权限/效果检查，不能借占用解除恢复已完成或不确定效果的执行权。

验收至少用上述两个 Task 的实际 item/Result 和用户读回证明：A 只有一个未完成 owner，
另一份是无修改的拒绝记录；等待人工时 owner 不变；B 不被整批连带阻塞。事务要求和
受影响测试按下列步骤落实，沿用现有结果/恢复模型，不新增等待队列或占用管理界面。

在本 Task 修复，按以下顺序完成：

1. **先固化真实反例。** 复用现有 Run once/临时 SQLite/Storage fixture，两个合法 API
   请求、两个 Worker，在真实占用查询与登记的竞争边界确定性交错。断言同一已验证来源最多
   一个未完成 owner；另一工作记录现有有界 `source_already_organizing` 原因/下一步，
   无 Provider/Storage 效果、不暴露其他 principal 的工作详情。不要断言只能受理一个外层
   Task，也不要将同一路径但真正不同内容/Storage 的工作无条件当成冲突。
2. **合并决定性事务。** 在现有 repository 事务中一次完成 live Task claim/fence 校验、
   共享 source ownership 核对和本次 TaskItem start 写入。复用
   `_find_owned_source_work_locked()` / `claim_task_item_with_ownership()` 已有身份、版本、
   discovery reservation 和合法 lineage 规则；同时保留 scheduled item 的 attempt/结果/
   不确定效果保护。不能仅调用不带当前 claim 校验的旧写入方法，也不能用进程内锁、
   第二次事务外查询或新锁系统代替数据库原子性。Storage/Provider I/O 仍在事务之外。
3. **保留 source 与续作语义。** 将实际 source version、Storage-relative identity、合法
   lineage/exclusion 等必要证据传到决定性写入边界，保留旧 pin/occurrence/history。
   人等工作仍拥有来源；允许的 same-Task 续作不会拒绝自己。检查并复用 manual/due/
   Run once/CLI/remote 的共同边界，不为每个入口复制一套占用实现，不恢复成功/uncertain
   sibling 的执行能力。
4. **跑失败及受影响回归后交接。** 至少验证上述两 Worker 竞争、已有 Files reservation
   与自动入口竞争、顺序重复来源拒绝、合法同 Task continuation、不同来源可处理，以及
   当前 claim 失效时无 item/attempt 写入。复用现有 ownership/claim/fence 测试，新增必要的
   真实入口回归即可；列准确命令和结果。Developer 不承担 B 的全仓/发布矩阵。

### Actual validation and pending gates

Local ignored evidence:
`.git/validation-evidence/c746b61e72c2a88d5e583bbe9877ce074d7a74e1/b-review-20261101/`.

- Root `.venv/bin/python -m unittest tests.test_automation_entrance_recovery
  tests.test_operator_job_submission tests.test_v2_automation_run_once
  tests.test_execution_authorization` — **55 tests passed**, 5.505s / 5.79s wall (`focused.log`).
  Expected failure-path Worker notices disclosed; no B production/test/Web source changes.
- `four_type_probes.py` / `.log` — actual Metadata choice and Conflict rename journeys above,
  complete confirmation and execution, 0.42s wall; initial summary-only probe 0.35s wall.
- `ownership_probe.py` / `.log` — actual two admissions and concurrent production Workers,
  **FAIL**, 0.32s wall: two waiting_recognition items, same verified source occurrence,
  no Storage effects. Thread scheduling controls an actual dependency boundary, not an invented
  endpoint or impossible call combination. This failed assertion remains visible in evidence.
- Timed tests/probes total **6.88s**, below 50% of this review turn, no idle waits.
  Governance preflight PASS; full Base..Head `git diff --check` clean; current report checks
  accompany this checkpoint. Fixtures use temporary roots, fake Provider and isolated runtime,
  never user media/databases or production services.
- Full T4 Python/Web/E2E/native visual/wheel/Docker gates remain **pending**, not waived or PASS.
  The proven P1 permits early FIX REQUIRED under workflow §6. Broader readback/remaining acceptance
  remains B-owned; Developer fixes this implementation blocker and runs its affected tests.

### Entire Slice outcome reassessment

| Outcome | Current result |
|---|---|
| RO-1 — stable Task and shared scheduling | New Task admission exists; cross-Task atomic source ownership is incomplete. |
| RO-2 — one engine across entrances | Previous CLI/remote continuation and new-Job submission gaps are fixed; concurrent concrete-source admission still violates the shared engine contract. |
| RO-3 — same-work four-type recovery | Recognition/Classification corrections retained; Metadata and Conflict full-chain probes pass. Required ownership and remaining acceptance prevent full completion. |
| RO-4 — safe historical Job migration/removal | Not delivered and outside this Task's complete-migration scope; not an added blocker. |
| RO-5 — complete operator/admin journeys | Current entrance fixes pass focused checks; broader readback/native/full acceptance and the source-ownership correction remain. |

Continue the same Task47.3 fix loop; no new Task or Slice closure is planned/claimed. Task47.2 PASS
and A-owned Slice/Roadmap/Progress remain unchanged. Slice47 remains ACTIVE.

### Developer guidance — complete the three corrections in this Task

以下保留三项原实施指导（最初基于 `405d2757`）；其中旧反例已修部分以上述 Verified
corrections 为准，本轮必须修复的是上述 source ownership 原子性问题。本指导细化已有
scope 4/6/7，不改变 Task Base、验收或 High/T4。开始修改时将状态置为 IN PROGRESS。
建议按“恢复链路 → 读回 → 剩余提交入口”实施，在同一候选中完成连接；三项不能自行移到
下一 Task。函数名是复用线索，不是文件白名单。不要借此提前实施 RO-4 全量历史迁移。

#### 1. 自动任务的决定、分析、摘要和明确执行接起来

用户结果：Run once/due 中某文件进入四类问题 → 在任务中心保存决定 → 继续分析 → 查看
精确摘要 → 明确确认允许的文件 → 原 Task 更新结果；刷新后仍能找到该进度和原历史。

1. 先把已复现的 Recognition 链加入 `tests/test_v2_automation_run_once.py`：真实 API
   Run once、真实 Worker 产生问题，GET item，POST 现有 `recovery/decision`，再取最新
   checkpoint，POST `recovery/continue`。旧反例最后一步为 409；该拒绝现已修复，继续保留同 Task 分析回归。
   复用 `tests/test_manual_task_engine.py` 的后续摘要/确认链，继续断言真实文件和 Result。
2. 从 `ManualTaskContinuationService.applies/continue_analysis/_linked_discovery` 入手。
   目前“有 scheduling row”选中了自动 Task，而后面又强制有 Files discovery。保留有效的
   checkpoint、权限、pin、源版本和不确定效果检查；把“可继续分析的工作上下文”从
   Files 专属前置条件中分离出来。Files 使用原 discovery；自动任务使用受理时的来源和
   已有 TaskItem/checkpoint/决定/固定配置。复用既有分析和准备记录能力，建立真实的持久
   关联，不伪造用户曾在 Files 提交，也不让用户重新选择来源。
3. 接通 `ManualTaskEngineWorker` 的后续消费以及 `ManualRecoveryContinuationService`
   的 summary/authorization/confirmation 路径。特别检查 `prepare_native_summary` 和
   `native_preparation_summary` 的 Files 关联假设；只改 continue 的返回码仍无法完成链路。
   初次自动运行可以按原意图执行；**业务恢复分析必须零修改**。不能仅凭 trigger 为
   SCHEDULE/RUN_ONCE 就重新调用初次 `run(... execute=True)`，重扫整个定义或自动执行。
   继续分析只处理该 Task 允许的剩余文件；摘要后的执行复用既有明确确认和同 Task 准入。
4. 在数据库原子边界处理排队/重复/取消/容量和适用授权消费。满队列保留决定、摘要、结果
   与人等状态；重复继续不多排工作。Worker 的 Task/父 Worker 心跳、item/result fence 和
   修改标记沿用已修复路径。成功/忽略/不确定项不重放；source/version/pin 与历史 attempt
   可追溯。随后补齐 Metadata（含既有候选/更正）、Classification、Conflict 的完整链，
   覆盖混合成功 sibling、源变化、过期 checkpoint、拒绝权限和队满；不另起恢复引擎。

完成判据：四类均能从真实入口走到明确执行或真实的新阻塞；同一个顶层 Task、无新 Job，
保存/分析零效果，确认只执行允许子集。旧 Files 恢复和初始确认不回归。

#### 2. 统一定时 occurrence、定义详情和运行结果读回

用户结果：定时任务处理一个文件后，定义详情显示对应 Task 和真实文件结果；返回的可用
详情动作可打开它。执行记录、latest 和指标各自遵守原语义，后续恢复不改写原执行事实。

1. 以“真实 due → Worker 完成一个文件 → GET definition occurrences → 跟随返回动作”
   建回归。保留 B 的反例：原反例 records 已显示成功，而 occurrence 为 taskId=null、
   文件数 0，链接指向不存在的 Job。增加一次真实失败/人工等待，避免只修成功显示。
2. 同时核对 SQLite 的 `list_automation_definition_occurrences`、
   `list_latest_automation_definition_occurrences` 与 occurrence decoder。
   新发生点的旧命名关联列保存的是受理 Task id，旧发生点仍可能通过 Job 关联 Task；
   使用可证明的受理/配置/来源关系分别解码，不把所有旧 job_id 直接当 Task id，
   不按时间、名称或当前 Active 猜关系。必要的最小关联存储变更须版本化、失败原子并可 reopen。
3. 接到 `AutomationDefinitionOccurrenceService` 的 latest/outcome/per-item 投影，再到
   `MediaFlowApi._automation_occurrence_operator_document`。新 Task 返回可用 Task 详情
   动作，不能继续公布不存在的 Job 动作。保留真实旧 Job 历史读取，未知关系明确不可用。
   `emitted` 可以保留其发生点受理语义，但界面必须另有正确的执行状态/结果，不能单纯
   把 occurrence 字符串改成 completed 来掩盖缺失关联或虚构成功。
4. 顺着实际调用检查 Automation inventory/latest/metrics/records、Task Center、Dashboard、
   logs/export/readiness/settings 的受影响读回。只改受影响关系/语义，不重做页面。
   原执行结果和实际时间与后续恢复状态分开；不直接拿可变 Task 当前聚合覆盖原记录。
   覆盖新旧数据混合、分页/计数/过滤、刷新/reopen、恢复前后原记录不变，读取零副作用。

完成判据：新发生点真实关联 Task，文件数/结果和允许动作正确；跟随 advertised link
返回正确对象；旧历史不丢，定义/记录/Task 视图按各自语义一致，无重复原运行。

#### 3. 完成直接 CLI、batch 和 remote API 的 Task 准入

用户结果：原有合法命令/请求继续可用，整理执行共用容量、Worker、固定配置和结果；
非执行分析仍只分析，拒绝路径不增加工作或权限。

1. 按本 Task 的 Existing-entry 表核对真实 parser/route/dispatch 和调用者，列清
   每项“执行 / 只分析 / 合法拒绝 / 旧历史只读”的最终处置。`final_cli.py` 的 batch 会先
   归一为 organize/path=None；复用这个实际分支，不能只改带 path 的 organize。
   `jobs submit organize`、retry-request/retry-failed 等按原有合法语义核对，不顺便开放
   执行或技术失败重放，也不为已退役命令恢复能力。
2. 将 `final_main` 中直接 execute 的 generic coordinator 入口接到共享 Task application
   准入/引擎，传递路径或全库范围、limit、trigger/principal、固定配置和明确执行意图。
   保留同步 CLI 当前的结果/退出语义：需要等待或驱动执行时使用同一 Task 引擎，不能
   排队就报告整理成功，不能保留 CLI 专用平行执行器。已有 `_task_observer` 只负责结构化
   身份交付，不等于完成调度整合。无 `--execute` 的分析保留记录和零修改，不进执行队列。
3. 将 `ExecutionAuthorizationService.submit_organize` 及 repository 的票据消费事务改为
   原子提交 Task/队列/必要来源和审计关系；复用既有 shared-capacity 与票据校验。
   API 现有 remote enablement、REMOTE_EXECUTE、execute=true、header ticket、limit 和
   固定配置检查全部保留。队满/无效/过期/已撤销/越界票据不产生孤儿或消费授权；重复请求
   按原支持的安全核对语义处理，不能把一次性票据重新变为执行权。
4. 调整 `POST /api/v1/jobs` organize 分支的响应/调用者，返回明确 Task 身份和可用读回。
   若提前替换这个旧提交入口，在同一 Task 提供权限和能力等价的 Task 入口及清晰指引，
   并完成消费者切换；不能只删除/拒绝接口而丢失原能力，也不能为兼容响应再写一个 Job。
   四类续作回到指导 1 的同 Task 路径。保留已有历史 queued Jobs 的安全过渡，不双写新工作。

完成判据：入口表无遗漏的新整理 Job 后门；CLI 单路径和全库 batch、remote 合法请求都
进入共同 Task 调度，能读回真实结果。权限/票据/队满/重复/只分析/取消和未知响应不扩大效果。

#### 本轮 Developer 受影响测试与交接

在上述现有模块中加入或扩展真实链路测试；先跑新用例和已知失败，再按实际改动执行相关组。
下面是受影响测试分组，不是全仓库回归；无需对未修改、未受影响的组机械重跑。

```sh
# 1: automatic recovery + retained Files recovery/claims
.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_manual_task_engine \
  tests.test_recovery_continuation tests.test_task_scheduling_fencing
# 2: occurrence/history/read model and Task Center population
.venv/bin/python -m unittest tests.test_automation_definition_occurrence \
  tests.test_automation_workspace_read_model tests.test_operations_run_inventory \
  tests.test_operations_task_center
# 3: real CLI/API submission, ticket/capacity/atomicity
.venv/bin/python -m unittest tests.test_batch_cli tests.test_execution_authorization \
  tests.test_automation_api tests.test_task_scheduling tests.test_automation_task_admission
```

修改 schema 时增加 `tests.test_task_scheduling_migration`；修改 resident adoption 时增加
`tests.test_automation_settings_resident`。修改 Web/其 API 投影时，按上文 Developer affected
计划运行改动页面测试、typecheck/lint/格式/build 和直接受影响原生 browser spec；不能只用
mock 组件证明真实链接/恢复成功。修改的 Python 文件跑 ruff format/check，最后跑 governance
和 `git diff --check`。本轮累计测试耗时仍须低于总用时 50%；不靠空等凑比例。

交接提供同一候选 SHA，按三项列出真实完成结果/受影响命令及结果/剩余阻塞与原因；任何
尚未完成的必要入口或链路要明确写出，不能自行缩小范围后称 Task 完成。已有上轮修复保持
回归。B 继续负责本 Task 原 T4 full/native/package gates 和最终独立审查，Developer 无需
重复全 Python/Web/E2E/发布矩阵；本指导也不将这些 B 门禁转交 Developer。
