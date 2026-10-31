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
Status: FIX REQUIRED
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

## Developer Completion Report — Round 3

**Status: READY FOR B REVIEW.** Same-Task correction checkpoint for the three B blockers of
Round 2; not a self-approved PASS.

```text
Task Base: dfcfebbdb9c879b38806e29c7b41c9192aeca83e (not repinned)
Code/test checkpoint: 1e46e5ba (fix(task47.3): same-Task automatic continuation, ...)
Report checkpoint: this documentation commit
Pre-existing untracked files: preserved, unstaged. No push/deploy/self-approval.
```

### Corrections implemented

1. **P1 — 自动任务的决定、分析、摘要和明确执行已接通（同一 Task，无新 Job）。**
   - `application/manual_task_continuation.py`: 自动分支——无 Files discovery 的 kernel
     automatic Task 在既有全部校验（checkpoint 版本、不确定效果、permitted action、活跃
     continuation、pin 一致）之后，通过 `TaskSchedulingService.requeue()` 原子地把同一 Task
     重新排入 ANALYSIS 阶段；满队列返回有界 409（`queue_full`，决定/结果/人等状态不变），
     已排队时的重复 continue 返回有界 409，不多排工作。
   - 新 `application/automatic_task_continuation.py`: Worker 续作通道。仅对 PENDING 且
     stage 为 `*_resolved` 的本 Task 条目做零变更重分析：先 claim-fenced `begin_item`
     （含跨 Task 源所有权检查），再经既有 intent/Preview 分析机器（受理 pin +
     `collect_resolved_continuation_decisions` 应用已保存决定）生成计划摘要，条目发布为
     `waiting_confirm`/`continuation_planned` 并写入真实的 `manual_recovery_preparations`
     行。源失效、决策不完整、Preview 被阻、异常分别发布为有界 effect-free FAILED 条目；
     成功/忽略/不确定 sibling 与仍等待决策的 sibling 一律跳过，不重放。
   - 摘要/确认：`native_preparation_summary` 扩展自动 Task 分支（读真实 preparation 行，
     PREPARED/CONFIRMED/STALE 语义与 Files 一致）；`confirm_prepared` 复用既有
     `begin_web_execution` 一次性授权；`_adopted_organize_task` 增加以 preparation 行的
     (intent_id, actor, pin, 未完成 Task, WAITING_CONFIRM item) 为证明的同 Task 采纳；
     `admit_manual_execution` 的采纳分支把 summary 版本栅栏移到条目重写之前，并保留被采纳
     Task 的既有 display 身份（不覆盖定义 origin）。确认后 Task 由 SQL 采纳事务原子重排入
     EXECUTION，Worker 经既有 `_run_execution`/`run_admitted` 在 claim fence 下执行允许子集。
   - Task Center 判定：`_native_pending_confirmation_sql` 接受自动 Task 的
     manual_recovery_preparations 关联，四类问题在 保存决定→分析→摘要→确认 全程保持
     business_problem，不被折叠为技术历史。
   - Web：`normalizeRecoveryCommandAck` 接受自动续作文档（nativeAnalysis 存在即原生续作，
     identity 回退到 taskId），UI 文案分支（“原 Task 已重新排入零变更分析”）保持不变。

2. **P1 — 定时 occurrence/定义详情/运行结果读回接上真实 Task 关联。**
   - `list_automation_definition_occurrences` / `list_latest_automation_definition_occurrences`
     的关联解码改为可证明关系：有 `automation_jobs` 行的旧发生点仍经 Job 解码（含
     failure_category）；无 Job 行且 `tasks` 表存在该 id 的新发生点，把旧命名 `job_id`
     列内容解码为受理 Task id；两者都不是则保持 NULL，不按时间/名称/Active 猜测。
   - `_automation_occurrence_operator_document` 不再为 Task-only 发生点公布指向
     `/api/v1/operations/jobs/{taskId}` 的动作（该链接此前 404）；Task 动作照常公布。
   - latest/outcome summary（per-item 计数、attention、`lastTaskId`）经同一解码自然恢复；
     `AutomationDefinitionOccurrenceService` 投影无需改动即读到真实 Task 与条目状态。

3. **P1 — 直接 CLI 与 remote API 整理统一到共同 Task 调度。**
   - `final_main` 的 `organize --execute`（含 batch 归一后的 path=None）改为共享 kernel
     准入（`build_scheduled_task_admission` + `admit_scheduled_task`，display
     origin=`direct-organize`，principal=`cli`，受理 pin/limit/scope），随后以受控临时
     Worker 注册、claim、`begin_work`，用 `KernelTaskCoordinator` 在 claim fence 下驱动
     同一生产管线并按既有聚合规则 settle（等待项→defer_to_human，终局→settle）。CLI
     输出文本与退出码语义保持；claim 900s lease + 心跳续约；取消经既有 control 边界。
     无 `--execute` 的分析保持原 generic coordinator 路径与零修改语义，不进执行队列。
   - `run_direct_organize`（`automation_definition_execution.py`）为常驻 Worker 消费该类
     Task 的恢复分支：无 scope→全库，目录→所在 ResourceLibrary，文件→该源，复用
     `run_legacy_schedule` 同一管线/围栏/结果发布。
   - remote：`ExecutionAuthorizationService.submit_organize` 与 repository 新
     `consume_execution_authorization_task` 事务改为原子消费票据并受理 Task（共享容量
     检查、`consumed_job_id`/audit 携带 Task id），不写 Job；满队列保持既有
     `AutomationQueueFull` 传输语义。`POST /api/v1/jobs` organize 分支返回 202 + 明确
     Task 身份（`taskId`/`task` 读回路径/`executionMethod`）；remote enablement、
     REMOTE_EXECUTE、`execute=true`、header ticket、limit 检查全部保留。
   - Worker 路由：`ManualTaskEngineWorker._is_automatic` 按 durable 形态（无 discovery/
     无执行/有 scheduling row）路由到共享 runner，不再按 trigger 标签拒绝。

### Actual validation（本轮命令与结果）

```sh
# 本轮新增/修改的端到端与受影响组
.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_manual_task_engine
# Ran 63 tests — OK（含新增 test_recognition_decision_continures... 全链路）

.venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing \
  tests.test_automation_task_admission tests.test_execution_authorization
# Ran 84 tests — OK

.venv/bin/python -m unittest tests.test_recovery_continuation tests.test_automation_definition_occurrence \
  tests.test_operations_run_inventory tests.test_operations_task_center
# Ran 159 tests — OK

.venv/bin/python -m unittest tests.test_batch_cli tests.test_automation_api \
  tests.test_automation_definition_execution tests.test_automation_run_once \
  tests.test_automation_admission tests.test_automation_definition_occurrence
# Ran 116 tests — OK

.venv/bin/python -m unittest tests.test_automation_workspace_read_model \
  tests.test_automation_definition_execution tests.test_automation_run_once \
  tests.test_automation_task_admission tests.test_automation_execution_intent
# Ran 128 tests — OK

.venv/bin/python -m unittest tests.test_manual_operations tests.test_manual_organize_execution \
  tests.test_manual_organize_preview tests.test_processing_worker_readiness \
  tests.test_automation_job_fencing
# Ran 99 tests — OK

.venv/bin/ruff check mediaflow tests/test_automation_admission.py \
  tests/test_v2_automation_run_once.py tests/test_execution_authorization.py
# All checks passed!
.venv/bin/python -m compileall -q mediaflow tests   # OK
git diff --check                                     # clean
```

新增关键链路测试 `test_recognition_decision_continues_analysis_summary_and_execution_on_one_task`
真实驱动：API Run once → 真实 Worker 产生 Recognition 问题 → decision → continue(202) →
重复 continue(409) → 续作通道零变更分析 → `waiting_confirm` + preparation → GET recovery/
preview → confirm(202, 同 Task 采纳) → Worker 执行 → COMPLETED + 1 SUCCESS Result + 文件
真实移动 + 全程 0 Job、分析期 0 Storage 变更。CLI 两条新测试分别证明 execute 入口为 kernel
Task 且文件真实移动，analysis-only 入口无 scheduling 行、零执行。

### Remaining work / risks（如实陈述，未自评 PASS）

1. **Metadata/Metadata-correction/Classification/Conflict 四类的自动续作链未各自写端到端
   测试。** 共用同一通道与决定装载（`collect_resolved_continuation_decisions`），Recognition
   已端到端验证；其余三类的真实 API 序列测试是本轮未完成的必要覆盖，请 B 在验收中复现或
   退回补齐。
2. **读回面只改了 occurrence/definition/records 已验证部分。** inventory/latest/metrics/
   Dashboard/readiness 的 Job-less 读回未逐一独立复核（上一轮遗留风险延续）。
3. **direct CLI 崩溃窗口：** admit 与 claim 之间崩溃时 Task 保持 QUEUED，由常驻 Worker 经
   `run_direct_organize` 恢复（含文件/目录/全库三种范围）；该恢复分支未写独立测试。
4. **历史 Job 兼容边界保持过渡态**：`IntervalScheduler` 无 kernel 时的 Job 回退、旧 queued
   Jobs 的只读/取消能力、RO-4 全量迁移/删除均不在本 Task。

### Scope statement

无 schema 版本变更（复用既有 schema55 列语义）；未读写用户数据库/生产媒体；未修改
A-owned Slice/Roadmap/Progress；未 push/部署；预存无关未跟踪文件保持未暂存。B 负责 T4
full/native/package 门禁与独立审查。

## B Review Result

```text
Reviewed: dfcfebbdb9c879b38806e29c7b41c9192aeca83e..38e68643cdcd10e9a969b30c505d3ade623ec33a
Implementation checkpoint: 1e46e5baa0ea1dc1d3400ef42bf80d80b8a954cb
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

B reviewed the complete 23-file Base..Head change, including the new continuation adapter, CLI,
remote authorization, SQLite, Web decoder and changed tests, and checked the new correction against
prior review findings. `1e46e5ba..38e68643` changes only `TASK.md`. Branch main; no initial tracked
edits. Pre-existing untracked OS/log/reference/archive files were preserved and remain unstaged.
Governance preflight passed. Original Task Base/Goal/scope and High/T4 remain unchanged. Older
reports/decisions remain in Git at `405d2757` / `cbf80518`; only the latest handoff is retained here.

### Verified corrections

- Run once → Recognition decision → same-Task analysis → summary → explicit confirmation → actual
  execution succeeds in the new full-journey test. The original `no_linked_preparation` refusal is
  resolved for that scenario; analysis remains zero-mutation and no Job is created.
- B repeated production-runner Run once/due/legacy file execution: all completed one Task/Result,
  with real source movement and zero Jobs. For the completed due Task, occurrence now resolves the
  correct Task, and its returned Task action opens successfully (200); no nonexistent Job action is
  advertised. This resolves the prior concrete occurrence-link blocker.
- New direct CLI ready-file and analysis-only tests pass. Remote API now admits a queued Task with
  atomic ticket consumption and no Job. These checks confirm admission improvements, not acceptance
  of every required entry/recovery/capacity/readback outcome.

### Task blockers and corrections

1. **P1 — 定时自动任务的恢复摘要归属错误，用户无法确认执行。**
   Real Scheduler due → Recognition waiting → admin saves type A → continue (202) → analysis
   produces a ready summary. Reading that summary succeeds, but its actor is `automation-scheduler`.
   Admin confirms the offered ready subset through the existing preparation confirm API and receives
   **403 `preparation_actor_mismatch`**. No effects occurred. `_continue_automatic_analysis` receives
   the authenticated actor but does not persist/pass it to the Worker; continuation `_task_actor()`
   instead takes the original admission principal. Run once tests use admin for both roles and miss
   this normal scheduled journey.
   **Fix:** carry the real continuation initiator and applicable authority through existing durable
   Task/attempt/preparation relations; bind intent/summary/confirmation to that authenticated context.
   Keep original scheduling provenance separate. Do not remove actor/current-permission checks or
   impersonate the scheduler. Cover scheduled and Run once full API journeys, another permitted
   operator, foreign-actor refusal, refresh/reopen, same Task and explicit selected execution.
2. **P1 — 恢复分析发现新的四类业务问题时，被错误终结为技术失败。**
   Existing Run once with no recognition rule and a valid TV-only Classification rule → save
   Recognition A for a movie → continue → real analysis reaches “ClassificationPolicy did not select
   a MediaLibrary”. The item and Task become **FAILED**, recovery is **technical_history**, and the
   existing Classification list has total **0**. No effects occurred. The operator cannot resolve
   the actual destination ambiguity through the promised Classification flow.
   `AutomaticTaskContinuationService._continue_item()` treats every non-PREVIEWED preview as failed
   instead of publishing its structured business blocker through existing four-type services.
   **Fix:** route actual Recognition/Metadata/Classification/Conflict findings into their native
   review/checkpoint state on the same source/Task; retain old decisions/history and accurate counts.
   Distinguish real transport/technical failure from a new business decision using existing structured
   results, not exception text. Continue through the next decision, zero-mutation analysis, summary
   and explicit execution; completed/uncertain siblings stay untouched. Add the failing Recognition
   → Classification transition and complete the other required automatic four-type journeys.
3. **P1 — CLI 在共享队列已有工作时领取了别人的 Task，随后报错并遗留领取。**
   B first admitted a normal Run once through its actual API, without running its Worker, then invoked
   real `organize --execute --limit 5` on the same fixture runtime. CLI returned **exit 2** (“Task is
   not claimable in this run”). Its own newly admitted Task stayed pending/queued; the older Run once
   stayed pending/**claimed by direct-organize-…**, with no processing and no file effects.
   `_drive_direct_organize_claim()` calls global `claim_next()` and only afterwards compares Task id;
   when another task is first, it raises without handing that claim back or running it.
   **Fix:** obtain ownership of the intended admitted Task atomically, or wait/read the same Task's
   shared execution if a resident owner already has it. Do not claim unrelated work and then reject
   its id, reset another Task, mint a duplicate or leave abandoned claims/temporary Worker records.
   Preserve global capacity/fences and synchronous CLI success/failure semantics. Cover a real
   pre-existing queued Run once/due plus direct CLI and batch, concurrent resident claim and failure
   cleanup; assert both Tasks' correct ownership, eventual results and no duplicate effects.

### Actual validation and pending gates

Local ignored evidence:
`.git/validation-evidence/38e68643cdcd10e9a969b30c505d3ade623ec33a/b-review-20261101/`.

- Root `.venv/bin/python -m unittest tests.test_v2_automation_run_once
  tests.test_execution_authorization tests.test_task_scheduling_fencing` — **69 tests passed**,
  6.227 seconds / 6.50 seconds wall (`focused.log`). Database ResourceWarnings remain disclosed.
- `probes.py`/`.log` — existing Run once API then real CLI against the same temporary runtime
  reproduces blocker 3; existing Run once/decision/continue/Worker with a valid unmatched destination
  reproduces blocker 2. Uses the existing test fixtures, real SQLite/Local Storage, fake Provider;
  no guessed routes or user data. 0.43 seconds wall.
- `scheduled_recovery_probe.py`/`.log` — real Scheduler due, initial pipeline, existing decision,
  analysis, preview and confirm routes reproduce blocker 1 (403). 0.34 seconds wall.
- `native_readback.py`/`.log` — current production runner with temporary fixture configuration and
  local service factories: three successful actual file runs, no Jobs; follows the occurrence's
  advertised Task link, asserts 200/correct identity/no Job action. 0.59 seconds wall.
- Total timed tests/probes **7.86 seconds**, below 50% of this review turn; no idle waits to manufacture
  the ratio. `python3 scripts/check_governance.py` PASS; `git diff --check Base..candidate` clean.
  Review-document checks accompany this checkpoint. Production/test/Web source is unchanged by B.
- Full T4 Python/Web/E2E/native visual/wheel/Docker gates remain **pending**. Proven P1 blockers
  permit early FIX REQUIRED under workflow §6; no gate is waived or reported PASS. Developer fixes
  and runs new/failing/affected tests; B retains full regression/native/package ownership.

### Entire Slice outcome reassessment

| Outcome | Current result |
|---|---|
| RO-1 — stable Task and shared scheduling | Improved admissions; incomplete because CLI claims unrelated queued work and automatic continuation still has required gaps. |
| RO-2 — all triggers share the engine | Due/Run once/legacy and direct/remote admission are connected; shared-queue CLI behavior remains blocked. |
| RO-3 — same-work four-type recovery | Run once happy Recognition chain works; scheduled confirmation and transition to a new business blocker fail. |
| RO-4 — safe historical Job migration/removal | Not delivered; complete historical migration remains outside Task47.3, not an added blocker here. |
| RO-5 — complete operator/admin journeys | Occurrence links/results improved; required recovery journeys remain blocked, broader readback acceptance is pending. |

Keep fixes in Task47.3. No new Task, Closure Packet or Slice acceptance is planned/claimed. Slice47
remains ACTIVE; original Task47.2 PASS and A-owned Slice/Roadmap/Progress are unchanged.

### Developer guidance — complete the three corrections in this Task

以下保留三项原实施指导（最初基于 `405d2757`）；其中旧反例已修部分以上述 Verified
corrections 为准，本轮必须修复的具体症状以上述三条为准。本指导细化已有
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
