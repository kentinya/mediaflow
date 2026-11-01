# Task 47.3 — 自动入口统一到现有 Task 引擎

Authority: committed [SLICE.md](SLICE.md), especially RO-1/RO-2/RO-3 and the necessary RO-5
readback; [Development Workflow](docs/development-workflow.md) governs planning, review and closure.
The user confirmed on 2026-10-31 that B should establish the next active Task, not retain a
planning-only draft. Task47.3 remains the same formal Task within committed ACTIVE Slice47;
the current implementation has been handed off and B owns the remaining independent acceptance.
The previous upgrade-only finding remains withdrawn. The current B review identifies one new-task
CLI retry scheduling gap below. No delegation, push or deployment is authorized.
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

## User-confirmed boundary — 2026-11-01

用户明确：**没有旧任务，不考虑升级。** 本轮以本版本新任务/新初始化运行环境为验收对象；
不要求跨版本升级、旧任务迁移、旧待处理任务恢复或历史执行兼容，也不将这些场景的反例
作为返工/PASS 阻塞。此用户指令优先于本 Task 早先及引用文档中的升级/旧任务条款。
既有相关代码/测试无需为此额外改造或删除，不能借此扩大本 Task 做全项目清理。

本版本新受理 Task 的真实入口、四类续作、原记录、权限、来源占用、并发/fence、
已完成/不确定效果非重放、fresh 初始化与同版本服务重启/reopen 继续验收。Task Base、
High/T4 和新任务安全义务不变。A-owned Slice/Roadmap/Progress 本次不改，不宣告 Slice 关闭。

## User-confirmed CLI simplification — 2026-11-01

用户明确要求：**两种 CLI 重试命令只保留 `tasks retry-failed`，删除
`tasks retry-request`。** 这是当前 Task 的显式用户授权，覆盖下文原先保留两条命令的
入口处置；不需要为已退役 resume 补一条继续命令，也不保留仅把 failed 改为 pending
却无法由 CLI 完成处理的准备步骤。`ignore-item` / `ignore-pending` 不在本次删除范围。

本轮 B 仅更新 Task 的实施范围/验收/开发指导，尚未修改生产代码或宣称命令已删除。
Task 保持 FIX REQUIRED、原 Base 和 High/T4；Developer 同时完成下面的命令删除及
已有 retry-failed 共享调度 P1。没有旧任务/升级，不增加 pending 迁移、兼容别名或恢复层。
四类业务恢复内部的请求、决定、checkpoint、审计和同 Task 分析/确认仍须保留。

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
   reopen 的最小 schema 存储变更；跨版本升级不在本轮范围，不新建竞争生命周期。
   只改为显示/控制新 Task 所必需的关联和查询，不重做这些页面、全套设置或已有恢复流程。

### Transitional boundary

本 Task 的“无 Job”验收对象是所有新受理的整理及其后续四类处理，不声称仓库已彻底没有
Job。按上述用户边界，不要求旧 queued/history 的迁移、恢复或升级兼容；不新增兼容执行器、
不双写、不让新提交回落旧队列。全量独立 Job schema/domain/dispatcher 移除不由本 Task
提前展开；本轮的旧任务升级反例已撤回，不能据此要求 Developer 再返工。

### Existing-entry coverage and disposition

以下清单来自当前 CLI parser/dispatch 和 API route，不代表新增产品入口。按真实输入及现有
合法条件逐项核对；不能只验收 Automation 主按钮，也不能把解析到的命令一律视为可执行。
对每项说明实际处置、权限/授权、返回身份和读回，并给出对应受影响测试；新提交的整理执行
走 Task；旧历史相关条目仅描述既有处置，不产生本轮升级/兼容实施义务。不为清单里的每个命令另建 Task 或实现一套新流程。

| 当前实际入口 | 本 Task 的处置/必须保留的区别 |
|---|---|
| Files 手动整理及其既有确认链 | 复用已接好的 Task 路径，回归摘要/选择确认、精确请求核对；不重做交互。 |
| `scheduler tick` / `scheduler run` → `IntervalScheduler` 的 interval/Cron 及 managed definition due | 新整理原子受理一个 Task，保持时区、occurrence/due 和权限约束；不能只切换其中一个分支。 |
| `POST /api/v1/operations/automation/task-definitions/{id}/run-once` 及该功能已有 GET/list/detail | 新运行直接进入 Task，查询仍找到原运行；disabled、一次运行意图、上限及不推进 due 保持。 |
| `organize --execute`、`batch organize --execute` | 统一到 Task 整理执行，保留路径/全资源库两种实际源范围、limit 和显式执行意图。 |
| 不带 `--execute` 的 `organize` / `batch organize`，以及现有 `jobs submit organize` | 逐项保留原有非执行授权/分析或合法拒绝语义，不能因命令含 organize 而获得执行权；分析只复用管线并保留证据，不新增 Job 或整理执行队列项。 |
| `POST /api/v1/jobs` 的 remote organize 提交分支 | 新整理改用 Task；remote enablement、当前权限、`execute=true`、执行票据和 limit 全部保留。若替换旧提交路由，须在同一 Task 提供并测试同等受限的 Task 入口与明确指引，不留新 Job 后门。 |
| `tasks retry-failed`；删除 `tasks retry-request` | 按用户指令仅保留可完成重新分析/显式执行的 retry-failed，并修复共享调度 P1；retry-request 从 parser/help/dispatch 删除，旧输入普通参数错误且零效果，不自动转成 retry-failed。保持源/结果/授权核对，四类业务续作仍回原 Task；不扩展技术/uncertain 重放，不做旧请求迁移。 |
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
- [ ] **CLI 重试入口收敛：** `tasks --help` 不再列出 retry-request；真实 CLI 传入
  `tasks retry-request --actor ...` 在参数解析阶段失败，零 Task/item/request/audit/queue
  写入、零 Provider/Storage effects，不保留别名或自动转为执行。`retry-failed` 保留默认
  分析零修改、显式 `--execute` 及原执行授权/固定配置/来源/效果核对，执行使用共享队列。
  四类恢复的 Save→analysis→summary→explicit continue 与 ignore 两个命令不回归。
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
- [ ] **新运行环境数据完整：** fresh 初始化、同版本 reopen/重启保留本版本新建的 Task、
  关系、pins、授权消耗/audit/logs、原阶段摘要和结果；失败原子，不虚构成功/权限。
  使用临时 fixture，不读用户数据库。旧任务/跨版本升级不作为本轮验收要求。

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
交接时列准确命令。schema 变化验证 fresh 初始化、同版本 reopen 和直接受影响的失败原子边界；
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
   Docker fresh/restart/security。按用户边界保留本版本 reopen/重启验证，不安排跨版本
   升级或旧任务迁移门禁，也不将完整 RO-4 Job-removal 迁移提前变成本 Task 门禁。
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

## B Review Result

```text
Reviewed candidate: dfcfebbdb9c879b38806e29c7b41c9192aeca83e..c139e0419a86a6a0d5fa0912e9dce2783071f9eb
Implementation checkpoint: 75a12d344a3dfd560cbdcf917e2480246974d2fc
Decision: FIX REQUIRED — one P1, existing CLI retry-failed bypasses shared Task scheduling
Previous upgrade finding: WITHDRAWN; old tasks / cross-version upgrades remain excluded
Next: Developer fixes retry-failed scheduling and removes retry-request as user directed; B reviews the corrected candidate
```

完整 Task Base..Head 的 43 个变更文件已独立审查。此前已修的同 Task 四类续作、原执行
记录冻结和原子来源占用未发现新的阻塞；T4 回归结果见下。当前只剩以下真实入口问题，
不是要求恢复旧任务、升级兼容或增加新的技术故障恢复产品。用户随后新增的 CLI 命令
删除要求尚待实现，见本 Task 的 User-confirmed CLI simplification 及下方开发指导。

### P1 — 失败项重试仍能绕过统一队列直接修改文件

**用户会怎样遇到：** 本版本新建的 `organize <file> --execute` Task 在文件修改前失败，
文件仍在来源。管理员修好故障后使用现有命令
`tasks retry-failed <task-id> --execute`。若此时其他新整理 Task 已占满配置容量，普通
`organize --execute` 会提示队列已满，但失败项重试仍直接移动文件并返回成功。
因此容量限制和统一 claim/fence 对这个实际可执行入口失效。

**真实复现（fresh 临时数据库、假 Provider、临时 LocalStorage）：**

1. 使用 `tests/test_automation_entrance_recovery.py::entrance_journey` 的真实 managed
   配置/运行时/API/CLI 组合，仅配置合法电影识别规则、`maximumActiveJobs=1` 和来源显示根。
2. 真实 CLI `organize <临时来源>/One (2001) [tmdbid-1].mkv --execute --limit 5`；
   在实际 `OrganizerExecutor.execute` 依赖边界注入一次明确无效果的失败。原 Task 和 item
   均为 failed、来源文件存在、共享容量占用为 0。没有伪造 Task、Result 或调度记录。
3. 通过现有票据服务和 `POST /api/v1/jobs` 受理另一份合法 remote organize Task，
   返回 202 / `executionMethod=task_engine`；该 Task queued，共享容量为 1。
4. 对照调用普通 CLI organize，返回 exit 2，明确说明 shared organizing queue is full，
   没有创建新工作或移动文件。
5. 执行原 Task 的 `tasks retry-failed <id> --execute`，却返回 exit 0 / Moved 1；
   来源文件消失，目标文件真实存在。新建 `retry-failed:<id>` Task 已 completed，
   `get_task_scheduling(new_id)` 为 None；另一 Task 仍 queued，容量读回仍为 1。

`cli_retry_capacity_probe.py` / `cli-retry-capacity.log` 保留完整入口、对照、文件效果和断言；
最终断言按预期失败（0.48s），不能记作通过。最初缺少可执行 item 的 fixture 探索及
探针自身语法错误保留在日志，不作为产品反例；最终使用正常的单文件 CLI 路径。

**原因与位置：** `mediaflow/final_cli.py:1219–1243` 的 `tasks` 分支仍使用通用
`PersistentTaskCoordinator.create()`，之后直接 `process_file()`，不设置 `kernel_context`。
相邻普通 organize 分支已经使用 `_admit_direct_organize_task()`、命名 claim 和
`KernelTaskCoordinator`。这是接入统一引擎时遗漏的既有入口，不是新需求。
该重试分支在 Task Base 前已存在；本 Task 的 `1e46e5ba`（2026-11-01 00:25 +08:00）
只接入了旁边的 organize 分支，当前候选仍保留此缺口，不声称旧重试代码是该提交新写的。
对应当前 Task 的“真实入口完整”“共享容量/Worker”及 Slice RO-1/RO-2、AC-2/3/4。

### Developer guidance — 修复这个入口，保持现有授权边界

1. 在现有 `tests/test_automation_entrance_recovery.py` / `tests/test_batch_cli.py` 中加入
   上述本版新任务复现，保留满队列普通 organize 对照。故障注入在真实 Executor 边界，
   明确原失败无效果；不得伪造调度状态，不能使用旧任务/升级作为前提。
2. 让该入口可合法执行的整理工作复用现有 Task scheduling admission、共享容量、命名
   claim、心跳及 item/result/aggregate fence，再进入现有管线和 OrganizerExecutor。
   不另建重试队列/执行器，不通过先建普通 Task 再补 scheduling 绕过原子性。保持原 pin、
   来源版本、现有重试资格、显式 `--execute` 和原 execute-authorized 检查。不要把技术
   retry 简单冒充四类业务 continuation；四类合法续作仍回原 Task，不能新增 Web 通用重试。
3. 满队列必须在新执行工作创建、旧锁/占用释放或执行权消耗之前明确拒绝。拒绝后原失败
   证据/来源/结果不变，无孤儿 Task/Job，无 Storage 修改，无后台自动重试。容量释放后，
   仍由用户明确重试，通过正常来源/效果/授权核对后在共享引擎执行。
4. 回归合法成功、满队列、未获原执行授权、无 `--execute` 零修改，以及已有成功 sibling
   不重放。按原有可执行资格保留安全边界：本项不授权重放 partial/uncertain 或结果不明
   的操作，不扩展技术/附件恢复，不刷新已消费权限，不做旧任务迁移。空失败集合不能为
   证明接入成功而伪造可执行工作。
5. Developer 只运行新/修改及直接受影响的 CLI、入口、Task scheduling/source ownership
   回归和 changed-file lint，提交实际 checkpoint/results/risks。B 保留 full T4 门禁责任，
   修复仍在本 Task，不另规划 Task 或提前关闭 Slice。

### Developer guidance — 删除独立 retry-request CLI，保留共享恢复证据

用户结果：修好临时技术故障后，CLI 重试只提供 `tasks retry-failed <task-id>`，默认
重新分析、显式加 `--execute` 才允许整理。用户无需先登记 pending；业务四类决定继续走
原 Task 的既有流程。保留命令必须同时完成上方共享调度 P1，不能以删除另一条命令代替。

1. 在 `mediaflow/final_cli.py` 删除 retry-request parser/参数、只读管理分发集合中的
   名称、该分支的 `TaskRetryRequestService.request()` 调用及专属 renderer/import。
   不留隐藏分支、别名、兼容入口，不把旧输入转成 retry-failed，也不再要求 actor/登记
   请求作为 retry-failed 的前置步骤。`ignore-item` / `ignore-pending` 的 admission 保持。
2. 基于实际引用清理专属代码：`application/task_retry.py::TaskRetryRequestService`
   当前生产消费者只有该 CLI；删除入口后若无生产调用者，清理这份专属封装及只为它
   服务的测试。不要按 retry 字符串删除共享代码：`RecoveryAdmissionService`、
   `task_retry_requested` 内部阶段、`domain/task_retry.py` 的共享审计类型、repository
   审计/请求以及四类继续链仍有实际调用者。无需为这次命令删除改 schema、搬旧 pending
   或实现升级兼容；不以清理为由扩大到整个恢复系统。
3. 同步当前 CLI 使用说明及适用文档中“retry-request 后 tasks resume”的过时指引。
   `docs/requirements.md` 当前批量操作说明含该指引，按本次用户决策说明 CLI 只保留
   retry-failed；不改 Git 历史或 `docs/history/` 的历史事实，不修改 A-owned
   Slice/Roadmap/Progress，不重新规划别的 Task。
4. 用真实 `final_main` / 已安装入口验证 help 和旧输入：旧命令为普通参数错误，解析即
   停止，不建立数据库/Storage/Provider、不产生恢复请求、pending 改写或执行。仅检查
   help 文本不算完整删除证明。给 retry-failed 加对照，验证无需 retry-request 即可独立
   完成合法重新分析/显式执行；保留满队列拒绝、无授权拒绝、成功 sibling 不重放。
5. Developer 跑新/修改和直接受影响的入口、批量 CLI、recovery admission/continuation、
   manual Task engine 测试及 changed-file 静态检查；现有 `tests/test_task_retry.py`
   中专属 CLI 成功用例替换为退役拒绝用例，共享恢复测试保留。B 复核真实入口/Task
   Base..新 Head 并负责所需 T4 门禁。不得删掉共享安全断言来使删除命令后的测试通过。

### B 实际验收结果

证据目录：
`.git/validation-evidence/47aa9f9ee78253a088bb2bf065a8631876957d65/b-acceptance-20261101/`。
产品代码输入为 `75a12d34`，B 验收适配提交为 `fc911bf3`、`c139e041`；这两个提交只调整
测试/harness，没有修改生产行为或 A-owned 文档。

| 门禁 | 实际结果 |
|---|---|
| Python full regression | 首次完整运行 3025 项，7 个版本 56 断言失败、1 个旧 API 响应字段错误；B 对齐当前 57/Task 响应后，完整四组 918+554+709+844=3025 项 OK，7 skipped，无遗漏文件。最终分组最慢 206.33s，并行运行。 |
| Python quality / examples | Ruff format/check、compileall、pip check、两个 example 配置验证、禁用依赖搜索均通过；example 仅在隔离副本改数据库路径，不使用用户数据库。 |
| Web full | typecheck/lint/format/build 通过；88 files / 1320 unit tests、253 E2E 全通过。构建仅有既有 chunk-size 提示。 |
| Native Automation | Run once 17、workspace 8、settings resident 12，全部通过；原始 failed/1 记录/结束时间不随恢复成功改写，当前 Task 如实更新，成功 sibling 不重放。 |
| Native Task Center | 八视图/分页/问题定位/重连和创建摘要确认共 2 项通过；已人工查看桌面、窄屏和各视图截图，布局和动作可用。 |
| 新任务 Metadata correction | 真实 Run once→保存标题修正→同 Task 分析→摘要→明确确认→真实文件整理通过；Save/analysis 零修改，未新建 Job/顶层 Task。 |
| Wheel | build + source-external installed CLI/API smoke 通过；wheel SHA256 `78f110c4f989abf9f803a55d7f2b25dd455095b05c87abe7def34121ba1ea3bc`。 |
| Docker | 使用候选镜像完成 fresh/security/nonroot/RBAC/静态资源/managed Active/同版本 Worker 重启及真实新 Task 执行，全部通过；image `sha256:968319b1b4bbd1da57ac78bff8f581c804f71b4eddaca5406049c330aee5a95e`。 |
| 新任务 CLI retry-failed | **FAIL — 唯一 P1**；真实满队列仍移动 1 个文件，新 Task 无 scheduling，见上述复现。 |
| Governance / diff | governance PASS、完整范围 diff whitespace clean；预存未跟踪文件保持原状。 |

7 个 skips 是既有 real SMB/S3/OpenList 及 Local/SMB/OpenList/S3 endurance 专用环境缺失；
不声称跑过外部生产服务或耐久矩阵。现有相关升级测试保留且随全量运行通过，但不是本轮
新增升级义务；用户排除的旧任务探针保持撤回。wheel/container 之后只有 B 测试输入变化，
生产代码/资源一致，明确复用其结果。

B 自行修正的验收输入不转成 Developer 产品阻塞：原生 Run once harness 原来还消费 Job/
child Task；现已驱动实际 Task Worker/同 Task 记录。旧安全测试改读真实新 Task 响应；
七个版本预期改为 57，没有增加升级实现。workspace/settings 同时运行会竞争同一共享
Active fixture，分开 fresh harness 执行后通过；Docker 首次失败源于 Colima 不可见的
macOS 临时挂载目录，改用仓库内隔离临时目录后通过。首次失败/中断日志均保留，未删断言、
加重试或调整超时掩盖失败。全量 Python、Web、原生、打包和关键探针均使用临时数据。

本轮从 2026-11-01 14:30:31 +08:00 开始；所有带计时日志的测试实际占用墙钟按重叠区间
去重约 13 分钟（并行命令累计约 25 分钟，二者明确区分）。测试占本轮总墙钟不足 50%，
其余用于完整 diff/入口/合同核对、fixture 修正、截图审查及验收指导，没有空等凑比例。
精确结束时间和重叠区间统计保存在证据目录 `acceptance-manifest.json`。

### 已验收的来源占用行为（保留开发指导）

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
另一份是无修改的拒绝记录；等待人工时 owner 不变；B 不被整批连带阻塞。沿用现有结果/恢复模型，不新增等待队列或占用管理界面。

### Entire Slice outcome reassessment under the user boundary

| Outcome | Current result |
|---|---|
| RO-1 — stable Task / shared scheduling | 主路径、容量/来源/并发回归通过；CLI retry-failed 绕过队列，未完成。 |
| RO-2 — one engine across entrances | due/Run once/direct/remote 及续作通过；现有 retry-failed 仍走通用非 kernel 执行路径，未完成。 |
| RO-3 — same-work four-type recovery | 新任务四类、原执行记录与独立 sibling 回归通过；不要求旧任务升级。 |
| RO-4 — Job removal | 旧任务迁移/升级按用户指令排除；独立 Job schema/model/dispatcher 的完整移除仍不由本 Task 声称完成。 |
| RO-5 — operator/admin journeys | Web/native/records/readiness/packaging 回归通过；CLI 管理入口仍受上述 P1 阻塞。 |

相关回归覆盖 AC-1/5–8/12–17/19 的本 Task 适用新任务场景；不代替整个 Slice 的逐项
结论。AC-2/3/4/15 因该实际入口缺口不能完整通过。AC-9/10 和旧版本升级证明已排除；AC-11 全量 Job 移除未交付；AC-18 的
B 证据已提供但 Task/Slice 未 PASS，仍需修复与最终独立 A 审查。没有新 Task、Slice closure
或 A-owned 状态修改，Task47.2 PASS 保持不变。

### Developer guidance — complete the three corrections in this Task

以下保留原三项实施指导供新任务验收回归参照；已修部分以上述验收结果为准。
其中任何旧任务/升级/历史兼容条款均受本轮用户边界覆盖，不再产生返工义务。
上轮升级反例仍无需修复；本次 IN PROGRESS 修复上方 retry-failed 缺口，并按用户指令删除
独立 retry-request CLI，已修的三项行为继续保留。

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
   `jobs submit organize`、retry-failed 按本 Task 最新处置核对；retry-request 按用户指令删除，不顺便开放
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

schema 变化仅增加本轮适用的 fresh/同版本 reopen/失败原子验证；修改 resident adoption 时增加
`tests.test_automation_settings_resident`。修改 Web/其 API 投影时，按上文 Developer affected
计划运行改动页面测试、typecheck/lint/格式/build 和直接受影响原生 browser spec；不能只用
mock 组件证明真实链接/恢复成功。修改的 Python 文件跑 ruff format/check，最后跑 governance
和 `git diff --check`。本轮累计测试耗时仍须低于总用时 50%；不靠空等凑比例。

交接提供同一候选 SHA，按三项列出真实完成结果/受影响命令及结果/剩余阻塞与原因；任何
尚未完成的必要入口或链路要明确写出，不能自行缩小范围后称 Task 完成。已有上轮修复保持
回归。B 继续负责本 Task 原 T4 full/native/package gates 和最终独立审查，Developer 无需
重复全 Python/Web/E2E/发布矩阵；本指导也不将这些 B 门禁转交 Developer。

## Developer Completion Report — Round 8

**Status: READY FOR B REVIEW.** 同 Task 修复本轮唯一 P1 阻塞（原记录仍把后续恢复成功和
结束时间算进首次自动执行）；不是自评 PASS。

```text
Task Base: dfcfebbdb9c879b38806e29c7b41c9192aeca83e (not repinned)
Code/test checkpoint: 75a12d34 (fix(task47.3): freeze the first automatic stage's original record facts)
Report checkpoint: this documentation commit
Pre-existing untracked files: preserved, unstaged. No push/deploy/self-approval.
```

### Correction implemented（按 B 的语义裁决四步）

1. **确定并冻结首次自动执行结束边界。** `ManualTaskEngineWorker` 只在初次 automatic
   阶段真实结束的边界冻结：`_settle_automatic` 完全交人工（`waiting_human`）与终端
   结算（published terminal status）、`_run_automatic` 的失败安全退出（`failed`）、
   自动 Task 的取消结算（`cancelled`，以"无 manual execution 且无 Files discovery"
   判定自动路径；Files 取消保持原读语义）。机器工作未完成（yield/稳定性等待）、
   在途未证实 mutation（`release_scheduled_claim` 本身拒绝）、从未开始的取消
   （`started_at` 为空）都不冻结，不因单个 run_next 返回/超时/缺 Result 伪造结束。
   后续 continuation/再结算受写一次保护，永不改写原摘要。
2. **最小存储方向，无第二生命周期。** schema 57 新增 additive `task_initial_executions`
   （1:1 键 = 原 Task `task_id`；无独立身份/队列/claim/执行控制），在
   `release_scheduled_claim` 的同一 claim-fenced 事务内、item 发布之后写入：
   原阶段 stage_status、真实 started/finished、总数/成功/未完成/不确定/跳过/取消/
   附件失败/不可核对/等待人工计数。逐项证据表达式抽取为
   `_TASK_ITEM_STAGE_EVIDENCE_SELECT`，冻结写入与 records 读模型共用同一词汇，
   并用与读模型相同的"最新 Result"窗口选取。迁移 additive、幂等、marker 最后推进、
   可 reopen；不回填、不改写任何既有行。
3. **限定消费者与原事实。** records-only `record_outcome`、`original_status`、各项
   计数与 `outcome=` 过滤在冻结行存在时读冻结证据（`waiting_human → failed` 按
   records-only 既有规则映射，其余 stage_status 直接映射）；记录展示的
   `executionStartedAt/FinishedAt` 优先取冻结窗口（API 文档层覆盖，SQL 列名不冲突）。
   Task Center、Task 聚合、`result` 信封、handling、metrics/latest 继续读当前工作；
   Round 7 的同 Task 可见性、due trigger 与旧 child 排除修复全部保留。展示层为
   冻结交人工阶段新增如实的失败原因/下一步（"有 N 个文件等待人工决定"/"在任务中心
   保存决定并明确继续处理该工作"），不隐藏计数、不删恢复关系、不冻结全部 API 字段。
4. **扩展真实测试后交接。** 冲突反例测试现在：首次自动处理结束后立即固定原
   records-only 事实（failed/1 成功/1 等待 + 真实起止），推进 fixture 时钟 1 小时，
   再走决定→分析→确认→执行；断言 recordId/来源/trigger/原结果/原时间跨分析、确认、
   恢复执行与 reopen 不变，`outcome=failed` 命中且 `outcome=completed` 为空，同时
   原 Task 确实 completed/2、成功 sibling 只执行一次、metrics/latest 仍只计一次原运行。
   due 场景同样先冻结再推进时钟后断言不变；健康空（noWork）、全成功、不可读失败
   各自断言冻结证据；schema 57 迁移新增 56→57 升级（空表、零回填、事实不变、
   幂等、integrity/foreign key 检查）与 fresh/upgrade 同布局两测试。

### Actual validation（本轮命令与结果，候选 75a12d34）

```sh
.venv/bin/python -m unittest tests.test_automation_admission \
  tests.test_automation_definition_occurrence tests.test_automation_execution_intent \
  tests.test_v2_automation_run_once tests.test_automation_definition_execution \
  tests.test_automation_run_once tests.test_execution_authorization tests.test_automation_api
# Ran 178 tests — OK（14.0s）

.venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing \
  tests.test_manual_task_engine tests.test_processing_worker_readiness \
  tests.test_automation_job_fencing
# Ran 127 tests — OK（9.7s；含 ProcessingWorkerService 默认 schema 版本 56→57 同步）

.venv/bin/python -m unittest tests.test_automation_workspace_read_model \
  tests.test_operations_run_inventory tests.test_operations_task_center \
  tests.test_task_center_recovery_lineage tests.test_v2_automation_operations
# Ran 144 tests — OK（26.7s）

.venv/bin/python -m unittest tests.test_automation_entrance_recovery \
  tests.test_operator_job_submission tests.test_task_source_ownership_race \
  tests.test_recovery_continuation tests.test_batch_cli
# Ran 83 tests — OK（23.2s）

.venv/bin/python -m unittest tests.test_task_scheduling_migration   # Ran 10 — OK（2.0s）
.venv/bin/python -m unittest tests.test_automation_settings_resident # Ran 25 — OK（43.4s）
.venv/bin/python -m unittest tests.test_operations_run_detail        # Ran 34 — OK（2.9s）
.venv/bin/python -m unittest tests.test_automation_task_admission    # Ran 8  — OK（0.4s）

.venv/bin/ruff format --check / ruff check <8 个修改文件>  # 全部通过
.venv/bin/python -m compileall -q mediaflow tests          # OK
python3 scripts/check_governance.py                        # PASS
git diff --check                                           # clean
```

计时测试合计约 176s，低于本轮总耗时 50%；无空等凑比例，未删断言、未加重试、未改超时。
未修改 Web 投影/harness（API 文档字段形状不变），故未跑 Web 构建/E2E。

### 边界说明（供 B 独立核对）

- **冻结只覆盖 kernel 自动路径。** legacy Job→Task 历史行无冻结证据，records 读模型
  对其保持既有当前事实语义（不反推、不伪造旧结束时间）；Files 手动 Task 不在
  Automation records 人口，其初始摘要确认/取消不冻结。排队中（未 claim）即被取消的
  自动 Task 无已执行阶段，保持既有取消读语义。
- **`result` 信封与 statusCounts 仍为当前语义。** 按 B 的收窄（"不要求所有原始 API
  字段冻结"），`result.status/successItems`、`statusCounts`、metrics/latest 继续
  反映当前 Task；冻结对象是 records-only `recordOutcome`、展示起止时间与 outcome
  过滤事实。
- **B 的 native Automation spec 适配提示。** 若现有原生 spec 在恢复完成后断言
  records 页"本次成功，已整理 2 个文件"一类文案，按本轮语义应改为断言原阶段事实
  （failed/1 成功/等待人工决定 + 原时间）与 handling resolved 并存；这是 B 的
  harness/验收工作，Developer 未改任何 spec。

### Remaining work / risks（如实陈述，未自评 PASS）

1. Metadata / Metadata-correction 的自动续作仍无各自独立 API 端到端测试（Round 4/5
   遗留，本轮未扩大）；本轮反例覆盖 conflict 与 due-recognition 两类。
2. 自动 Task 执行中途取消的冻结行为由实现覆盖（`_settle_pending_control` 自动判定），
   但无专门端到端断言；现有取消回归（排队中取消等）全部通过。
3. B 仍负责本 Task 原 T4 full Python/Web/E2E/wheel/Docker/native 门禁与独立审查；
   本轮未运行这些门禁，之前披露的 native harness 旧失败仍归 B 适配。

### Scope statement

未读写用户数据库/生产媒体；未修改 A-owned Slice/Roadmap/Progress；未 push/部署；预存
无关未跟踪文件保持未暂存。B 负责本 Task 原 T4 验收与独立审查。
