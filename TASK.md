# Task 47.1 — Task 调度与持久化内核

Authority: committed [SLICE.md](SLICE.md) at `45d2e951eb00ffdd4cecbaafed50039668e445f0`；
[Development Workflow](docs/development-workflow.md) 管理生命周期、检查点和测试分工。
阅读对应 [B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md) 经验。

```text
Task ID: 47.1
Task Type: SLICE
Parent Slice: 47
Status: FIX REQUIRED
Task Base: 45d2e951eb00ffdd4cecbaafed50039668e445f0
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Authorization: PLAN ONLY — 2026-10-30; USER-AUTHORIZED IMPLEMENTATION — 2026-10-30
```

## Goal

完成可复用的 Task 调度内核：一个 Task 的原子入队、容量计数、去重、Worker 领取/心跳、
协作控制、安全重入队，以及受领取栅栏保护的逐项结果发布，均由 Task 自己的持久状态管理。
以真实 SQLite 验证入队 → 领取 → 发布 → 人工等待/安全暂停 → 原 Task 重入队这条完整内部链。

这是 Slice47 **RO-1 的架构基础单元**，同时承担 **RO-4 的增量 schema 基础与数据保护**，
覆盖 AC-2/3/8/12/16 的内核部分以及 AC-9/10 的本轮增量升级部分。
`V2-TASK-001/003/004/006`、`REQ-TASK-002/005/006/007/009/010`、适用 `REQ-RECOVERY-006`、
`REQ-RESULT-*` 和 `REQ-SAFE-*` 保持有效。

本轮不宣称 RO-2/3/5 或 Job 退休已交付。新调度服务不接入现有生产入口/驻留循环，不接管或
复制现存 Job/Task；现有入口继续使用其原执行路径。新接口是最终 Task 引擎可直接复用的
内部能力，不增加用户可选的新旧队列、第二套整理/恢复产品或常驻 Worker。

## Actual-code gap

- `PersistentTask` 已有状态、计数、快照和暂停请求，但没有完整的 Task 领取/心跳/队列资格。
  `PersistentTaskCoordinator.create()` 默认直接 Running；`begin_queued()` 不是通用领取边界。
- `AutomationJobService` / `claim_next_job()` 仍拥有容量和领取；本轮读懂并复用其正确的原子性、
  现有 Worker 注册/命令/schema 校验，不复制 Job 对象或更改其当前行为。
- 通用 `update_task`、`upsert_item`、`append_result`、`complete_item_with_evidence` 没有 Task
  领取栅栏；现有 guarded 方法绑定 Files transfer，不可拿 transfer ID 冒充 organizing Task。
- `SQLiteTaskRepository._initialize()` 当前为 schema53，含 `executescript`、多阶段增量操作及
  位于后续增量操作之前的 schema marker 写入。Task 多个写入点使用无列名的位置 INSERT；
  新列不能破坏手动执行、Files discovery、Run once 和普通传输的现有入库。
- `tests/test_task_persistence.py` 已覆盖历史布局差异、源占用及重开；部分现行版本断言为53。
  只可按真实升级更新版本预期，不能删掉数据、非重放或权限断言来通过测试。

## Implementation Scope

优先修改/扩展 `mediaflow/domain/task_persistence.py`、`mediaflow/application/task_runtime.py`、
`mediaflow/infrastructure/sqlite_runtime.py`。可以新增轻量的 Task 调度值对象/端口及
`mediaflow/application/task_scheduling.py`；它们属于同一 Task 聚合，使用同一个 task_id，
没有独立 queue/job ID、业务生命周期或执行器。物理字段布局由 Developer 选择，不能据此
引入竞争的调度权威。业务代码依赖端口，不直接访问 SQLite/Storage。

1. **定义内部调度契约与明确接入资格。**
   定义 Task 的准入上下文、队列资格/下次机器工作时间、领取代次、Worker/心跳、控制请求和
   栅栏输入输出。区分业务状态、阶段、队列资格和原结果。明确只有经该应用边界显式准入的
   Task 可被新内核领取；默认旧行不入队，不能根据 command、Pending 状态或当前 Active
   自动接管旧工作。校验有界 command/trigger/actor/request、完整快照 ID/digest、正整数容量
   和有效时间/租期；内部调度标志不是执行权限。本轮不签发/消费真实执行授权或新增外部接口。

2. **实现 schema53 → 54 的非破坏升级和持久化。**
   新建、真实 Base 升级和重开均得到 schema54；新增调度事实只属于 Task。保留全部旧字段值、
   关系、标识、pins、Results、授权消费、审计/日志及未知/退役 Job 原始记录，不回填可执行资格。
   若追加 tasks 列，逐一调整受影响的所有 INSERT/序列化/读取，使用显式列或等价安全布局，
   验证真实消费者，不能只改 `create_task()`。新增迁移、相关索引和版本标记在正确的事务中提交，
   schema marker 必须最后推进；故障不能留下半套54或已推进的版本。保留更高版本拒绝和已有
   旧库兼容路径；遵循现有部署维护租约/schema 检查，不新增进程监督或重写无关迁移历史。

3. **实现原子准入、去重及容量重入队。**
   Task、必要有界显示/请求上下文和队列资格同时提交。principal/request 的精确重复在满队列时
   仍返回原 Task；上下文不一致的重复请求拒绝，不能合并别人的工作或扩权。每个有排队机器工作/
   活动 Worker 阶段的 Task 只占一个名额，涵盖发现、分析、执行及机器定时稳定性等待，多文件/
   多次尝试不重复计数。整项人工等待/已安全确认暂停且无机器工作时为零；请求暂停/取消但调用
   尚未安全结束时继续占用。安全重入队须检查原状态/版本/原 pin/资格并重新原子检查容量，沿用
   原 Task；满队列保留状态、已保存选择/摘要/结果及既有授权记录，不登记待自动续作。
   入队/重入队/领取不能自行把 analysis-only 的 execute_authorized 改为 true，或仅凭来源标签
   推导执行权限；原始准入上下文和授权事实不能被普通 Worker 发布覆盖。
   保存决定本身不入队。释放名额不释放耐久源占用，不使 uncertain/完成步骤变得可重放。

4. **实现有栅栏的领取、心跳和协作控制。**
   真实多连接/多进程只能有一个有效 Task owner。复用现有 Worker 注册/心跳/schema/支持命令
   检查，读取 Task 原 pin，不从当前 Active 偷换上下文。领取代次和 Worker 必须同时匹配；
   失效/错误 owner 的心跳、控制确认及发布无效。心跳与用户观察到的业务控制版本语义分离，
   避免一次正常心跳令合法暂停/取消误报陈旧。暂停/取消先保存请求，当前 owner 到安全边界
   才确认/释放其执行名额；并发终结不能覆盖已接受的取消。不得中断外部调用或借控制强行解锁。

5. **贯通 Task/TaskItem/Result 的安全发布。**
   应用服务或 coordinator 的调度上下文把同一 Task claim 传到 item 开始、进度/证据、结果和
   Task 聚合提交。接收记录必须属于同一 Task/源版本/pin；逐项结果/证据/状态按现有原子边界
   提交，成功/历史记录不被新尝试覆盖。不能只 fence 最后一个 Task UPDATE，遗漏 item/result
   或在通用 writer 上留下无栅栏回退。对被新内核管理的 Task，适用的旧无栅栏机器发布接口
   必须拒绝绕过；未接入的旧工作和普通传输继续其原保护语义。复用现有源占用/锁代次，旧 owner
   的 finally/release 不能删除新 owner 的锁。无需固定内部 TaskItem ID；有新 ID 必须保留明确
   历史关联、准确文件数及源/权限边界，不新建恢复系统。

6. **明确中断/效果边界，完成可复用内核而非新恢复流程。**
   提供未来 Executor 集成所需的、受 owner 栅栏保护的进入变更/记录结果边界；本服务自身不调用
   Storage/Provider/Executor。用持久标记和现有 checkpoint/effect 语义证明已发送变更但未可靠
   记录结果的步骤不再可领取/重放。超时、租约过期、重启或缺少 Result 本身均不足以恢复。
   支持范围内、有耐久安全证据的未执行剩余阶段可在显式安全控制下重入队；不做通用过期抢占、
   自动重试 uncertain、技术失败新恢复入口或附件重放。读接口/构造服务/重开数据库不启动工作。

7. **完成真实持久化/竞争/升级验证及兼容交接。**
   以临时 SQLite、多连接及进程重开、可控时钟/调用阻塞和故障注入覆盖下列验收。复用现有迁移
   演练，以 Task Base 的真实代码建库，不用给新库改版本号冒充旧库。只更新必要版本消费者、
   包装/验证脚本和实际受影响测试；保留全部真实失败、跳过和限制。交接实际 checkpoint 与变更
   清单，说明尚未切换生产入口/迁移 Job 数据/退役接口，不能宣布本 Slice 完成。

## Acceptance Criteria

- [ ] **T1 — Task 内部链完整。** 显式准入得到一个持久 Task；不建立 Job；入队、领取、心跳、
  逐项发布、人工等待/安全暂停和原 Task 重入队可经应用服务 + 真实 SQLite 完成并重开读回。
  非调度旧行/未知 command/不完整 pin/非法上下文不能自动变成新内核工作。
- [ ] **T2 — 容量原子且符合 Contract。** 多个来源标签和多个真实连接竞争最后一个名额不会超额；
  多 item/attempt 只计一项，机器定时等待仍计一项。全人工等待/已确认暂停为零，混合任务仍有
  机器工作或暂停/取消尚未确认时为一。释放/重入队竞争按真实事务结果确定，无隐含自动续作。
- [ ] **T3 — 幂等/拒绝不留副作用。** 同 principal/request 精确重复收敛同 Task，满队列也能查询
  原请求；相同 ID 不同上下文/不同 principal 不混淆。满队列/陈旧版本/非法输入保留既有 Task、
  choices/summary/Results/授权状态，无孤儿 Task 或新 Job；入队/恢复/Worker 发布不能擅改 pin/
  准入上下文或把 analysis-only 升为 execute-authorized；源占用不因容量变零而释放。
- [ ] **T4 — 领取与控制安全。** 正确 Worker/schema/命令/pin 才可领取，同一 Task 只有一个有效
  owner。旧 owner/错误代次/错误 Worker 的心跳、item/result/证据/聚合发布和锁释放全部无效。
  心跳不误伤合法控制；暂停/取消有请求与确认区别，不提前释放 in-flight 名额，不丢已接受取消。
- [ ] **T5 — 发布原子且不串项。** 当前 claim 的逐项结果/证据/状态能共同提交；故障全部回滚。
  错 Task/item/pin/源版本不能写入，旧无栅栏接口不能绕过新内核。此前成功/历史结果、独立 sibling
  及现有锁保护不被覆盖；验收不要求底层 TaskItem ID 恒等。
- [ ] **T6 — 重启不重放。** 排队未开始工作可重开按原 pin 领取；领取失效后只按既有可证明安全
  边界处理。模拟变更派发前及派发后未证实结果的中断，后者保留 uncertain/不可重放事实，重启/
  到期/无 Result 不清除；不承诺任意崩溃点自动无缝续作。
- [ ] **T7 — 真正增量升级。** Task Base 原代码建立的 schema53 与新建库都能到54并重开；旧 Task/
  item/result/plan/checkpoint/Job/continuation/授权/日志等原值与关系保持，无授权提升和自动入队。
  覆盖 Unicode/合法长路径/nullable旧证据/活动及终结工作，完整性/FK检查通过。更高版本拒绝。
- [ ] **T8 — 升级失败原子。** 在新增 schema/索引及版本推进的代表性边界注入失败，原 schema53
  数据/版本/旧代码可读性保持，去掉故障后可安全重开到54；不把只读副本演练成功当作直接升级
  失败原子的唯一证据。新 schema 下各真实 Task 创建/写入入口仍工作，不受列顺序影响。
- [ ] **T9 — 过渡边界清晰。** 新内核没有生产外部入口/驻留消费者，不接管、复制或双写 Job，
  也不对现存 Task 额外领取。原 API/CLI/Web、Worker、手动整理/发现、Run once、普通文件两库
  操作、记录与恢复保持原行为；保留 Job 仅为尚未切换的现行路径，不宣称最终退休完成。
- [ ] **T10 — 可安装/可运行。** 源码外安装实际 wheel 后能导入/使用同一调度服务与 SQLite 升级；
  B 的适用 T4 全回归和当前原生/容器兼容验收通过，或实际不可用门禁明确待完成，不能记为 PASS。

## Required Tests

遵循 [测试等级与分工](docs/development-workflow.md#6-test-levels)。以下是**实施后的要求**，
不是本次规划已执行的产品验收。新测试模块名为计划名，实施交接须给出最终对应命令。

### Developer — affected tests

1. 新增 `tests/test_task_scheduling.py`、`tests/test_task_scheduling_fencing.py`、
   `tests/test_task_scheduling_migration.py`，覆盖 T1–T8 的成功/非法输入/竞争/失败/重要边界。
   使用真实 SQLite 事务/连接和重开验证，不用内存列表模拟队列原子性；不只比较字段或代码文本。

   ```sh
   .venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration tests.test_task_persistence tests.test_task_pause_resume tests.test_automation_admission tests.test_automation_job_fencing
   ```

   后四个既有模块验证 Task schema/coordinator、源占用、现有控制及尚未切换的 Job 容量/领取。
   新迁移测试须从真实 Task Base 创建含数据的库并做故障回滚/旧版本读取证明。

2. 实际受影响的代表性 Task 写入/执行链：

   ```sh
   .venv/bin/python -m unittest tests.test_manual_organize_execution.ManualOrganizeExecutionTests.test_type_c_exact_move_persists_result_effect_and_checkpoint tests.test_manual_organize_execution.ManualOrganizeExecutionTests.test_result_publication_failure_persists_uncertain_effects_without_replay tests.test_media_discovery.AdmissionAndScopeTests.test_files_admission_commits_a_real_pending_organizing_task tests.test_direct_file_transfers.SameStorageTransferTests.test_same_storage_file_copy_and_move_use_only_the_native_operation tests.test_media_library_transfers.MediaLibraryTransferTests.test_media_transfer_progress_survives_api_restart_during_active_outage tests.test_v2_automation_run_once
   ```

   覆盖 C→A identity、manual/discovery/Run once 和两种库 transfer 的 Task 创建、结果及重启；
   若修改更多生产 writer/授权/lease 入口，补充其直接受影响测试并在交接列明原因。

3. 静态检查以 `git diff --name-only --diff-filter=ACMR <Task Base>` 确定的 Python 文件为准，
   对实际文件运行 `.venv/bin/ruff format --check <changed-python-files>`、
   `.venv/bin/ruff check <changed-python-files>` 和
   `.venv/bin/python -m compileall -q <changed-python-files>`；运行
   `.venv/bin/python scripts/check_governance.py` 与 `git diff --check`。
   不把全仓 Python/Web/E2E/容器门禁改名为“受影响测试”交给 Developer。

### B — acceptance and full regression

- 独立审查精确 `Task Base..candidate`，先复现 T2/T4/T6/T8：多连接最后名额、旧 owner 结果/
  锁发布、派发后不确定不重放、直接升级故障回滚。核对新内核没有外部消费者且未双写/接管旧行。
- 执行 [共享 T4 全量门禁](docs/development-workflow.md#shared-full-regression-commands)：完整
  Python/Web/静态/示例/禁止依赖、安装包、安全和适用原生/持久化检查；本 Task 涉及共享 schema/
  writers/栅栏，具备全回归的实际理由。不要重复已被完整运行覆盖的 focused 用例。
- 真正 Task Base → candidate 升级演练：

  ```sh
  .venv/bin/python scripts/schema_upgrade_rehearsal.py --base-sha 45d2e951eb00ffdd4cecbaafed50039668e445f0 --expect-schema 53 --expect-candidate-schema 54
  ```

  复用/必要扩展该脚本的新字段 round-trip 与旧行不入队证明，不能只验证 schema 数字。
  新的直接升级故障注入测试和演练相互补充，不互相替代。
- 在 `web/` build 后，真实 Python/API/SQLite/Worker 兼容旅程：

  ```sh
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts tests/e2e/direct-files.python.spec.ts
  ```

  核对现有列表/普通工作/手动摘要和结果可读、重启后不丢、desktop/narrow 截图无退化。
  这是 schema54 的原流程兼容证据，不作为三入口已切换新 Task 引擎的证明。
- 安装本候选实际 wheel，运行共享 wheel smoke 及源码外的 Task 调度服务/SQLite小链路，确认
  导入来自 site-packages、不是源码；记录确切 artifact 路径/哈希，防止旧构建目录漏包。
- 共享 schema/Worker 兼容性需要容器 fresh/restart/真实53→54升级和安全证明：

  ```sh
  .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py --base-sha 45d2e951eb00ffdd4cecbaafed50039668e445f0 --base-schema 53
  ```

  以及共享 gates 中本候选镜像的 security smoke；证明新进程使用新 schema、旧不兼容注册不能
  领取新内核工作，既有 transfer/manual/Job 不被意外额外领取。复用现有维护租约/隔离容器，
  不构造新进程监督器。脚本打印 SKIP/返回0 不等于门禁已通过；缺失环境由 B 记录待完成。

## Non-goals

- 不在本 Task 执行 Job→Task 的整批历史转换，不删除12张表中的 Job引用/旧 Job表，
  不发布“双队列共用容量”的临时产品，也不把 additive schema54 宣称最终迁移完成。
- 不切换 Scheduler/Run once/Files/API/CLI/驻留 Worker 的生产 dispatch；不实现完整整理引擎
  或四类恢复的生产改接，不新建 UI/管理接口/功能开关。最终共用引擎、Job退休仍是 Slice 必需结果。
- 不重写识别/元数据/命名/分类/附件/稳定性规则，不改现有授权模式、Task Center 八视图或自动化
  原始记录结果语义；不新增 Provider、文件命令、并行度、监督器或恢复类型。
- 不要求历史 TaskItem 编号恒定，不做全历史数据合并、自动 repin、通用过期抢占、uncertain重放、
  任何崩溃点无缝恢复或 universal rollback；不以本 Task PASS 关闭 Slice 或自动规划额外工作。

## Workspace and planning record

Repository `/Users/songzhidong/mediaflow`；branch `main`；planning HEAD / Task Base 如上。
治理 preflight PASS；workspace/Git 可写。开始时无 tracked edits；既有 untracked OS/log/参考图/
压缩包均为无关文件，保留且不暂存。只读代码调查未访问用户运行库、私有配置、媒体或生产服务。

Slice47 已 ACTIVE，无需重复激活/改写 A-owned SLICE/Roadmap/Progress。B 接受 A 的最新已提交
契约修订，按其逐文件关联、明确容量及有条件恢复边界规划。规划检查点（`cb0e2885`）只提交了计划
及相关文档检查，未修改产品代码/测试、未实施/自审，也未运行或宣称本 Task 的 T4 产品门禁；实施
从该规划 HEAD 开始，记录见下方 Developer Completion Report。过往183项基线只是 Slice Base 的
已记录观察。此前独立修正及验收记录保留于
`45d2e951eb00ffdd4cecbaafed50039668e445f0:TASK.md`。

## Developer Completion Report

```text
Checkpoint: e53e38999459f81da65f625ee3b73d39e9ff793e (implementation; this Task record is the
following docs checkpoint on the same branch — B reviews Task Base..HEAD)
Task Base: 45d2e951eb00ffdd4cecbaafed50039668e445f0 (unchanged, per plan)
Implementation start HEAD: cb0e288598cdffa399256b5ae694522f92ce6ce9 (planning checkpoint)
Status: READY FOR B REVIEW — full T4/acceptance and the Closure Packet are B's, not claimed here
```

### 变更内容与关键决定

- **调度事实只属于 Task（schema 53 → 54）。** 新增 1:1 `task_scheduling` 表（`task_id` 主键、
  外键 Task），承载队列资格/机器阶段/可领取时刻、领取代次与 Worker/租约/心跳、控制请求与
  `control_revision`、以及 in-flight 变更标记。选择独立 1:1 表而非给 `tasks` 追加列：现存 5 个
  位置 `INSERT INTO tasks VALUES (...)` 与多处以列数写死的写入点全部保持原样，fresh 与就地升级
  得到完全相同的物理布局（T8 的“不受列顺序影响”由此成立），旧 Task 行原值、关系、pin、
  Results、Job 行、授权与日志零改动。
- **marker 最后推进。** 原先位于后续增量操作之前的 `schema_version` 写入移到
  `_initialize()` 真正末尾（`_advance_runtime_schema_marker()`），新布局先可验证存在再声明版本；
  失败保留 53 且旧代码可读，重开可补完（T8 两个注入点实测）。
- **准入 = 一个事务。** `admit_scheduled_task()` 在 `BEGIN IMMEDIATE` 内完成 principal/request
  去重（唯一索引）、容量计数、Task/显示证据/调度行插入。满容量零写入、零授权消耗、无孤儿
  Task；精确重复即使满队列也返回原 Task；同 ID 不同上下文拒绝（`TaskAdmissionConflict`）。
  `execute_authorized` 只作为显式入参存一次，trigger 只是标签，任何发布都不能改写 command/
  authority/created_at/scope/item_limit/pin（`_require_scheduled_authority_locked` + 只更新发布列）。
- **容量语义。** 只有 `queued`/`claimed` 计一个名额（一 Task 一名额，多 item/多 attempt 不重复；
  机器定时等待仍是 queued）。全人工等待（`defer_to_human` → `waiting_human`）、已确认暂停
  （`paused`）和终态（`settled`）为零；请求暂停/取消但尚未到安全边界时保持 `claimed` 名额。
- **领取与控制。** 领取在 `BEGIN IMMEDIATE` 内选择并 CAS 代次，复用既有 Worker 注册/停止/schema/
  心跳失效判定，并额外要求 Task command ∈ Worker 支持命令、Worker pin（若声明）与 Task pin
  完全一致；返回的 claim 携带 Task 自身 pin。只领取 `pending` 且未进入机器阶段的 Task：已发布
  RUNNING 的 Task 即使租约过期也不被普通领取接管（超时/重启本身不是“未发生”的证明）。
  控制请求先持久化（同一请求幂等、pause→cancel 升级、cancel 不可降级），心跳只延长租约、
  不触碰 `control_revision`，因此不会令合法控制显得陈旧。
- **发布栅栏。** item 开始/进度/结果/证据/Task 聚合全部经 `TaskClaimFence`
  （task+worker+token+generation+now）比较；`release_scheduled_claim()` 把聚合、受影响 item 与
  名额释放一次提交。item 发布区分 start/progress/outcome 三种 attempt 规则，结果行改为
  不可 replace 的 INSERT，因此历史 attempt 的成功记录不会被新尝试覆盖。未接入的旧 Task 与
  普通传输行为不变；对内核管理的 Task，通用无栅栏写入（`update_task`/`upsert_item`/
  `append_result`/`append_evidence`/`complete_item_with_evidence`、transfer-fence 写入、
  旧 pause/cancel）一律 `TaskSchedulingBypass` 拒绝。
- **不确定效果边界。** `begin_scheduled_mutation()` 写入持久标记后，该 Task 不能被领取、
  不能重入队、不能因超时/租约到期/重启/控制请求释放名额；只有当前 owner 在同一事务内发布
  受影响 item 的已证实结果才清除标记。服务本身不调用 Storage/Provider/Executor。
- **安全重入队。** 仅 `waiting_human`/`paused` 可重入队；校验调用方观察到的
  `control_revision` 与原 pin，同事务重查容量；满队列抛 `TaskQueueFull` 且不改状态/已存
  选择/摘要/结果、不登记自动续作；成功后同一 Task、代次 +1、pin 与 authority 不变。
- **本轮无生产入口（T9）。** 新增测试断言除内核三文件外，`mediaflow/` 与 `web/src` 均不引用
  内核符号；Scheduler/Files/Run once/Worker/API/CLI/Web 未切换、未双写、未接管现存 Task/Job。

### 实际受影响测试（Developer 范围，均已实际执行）

| 命令（cwd 仓库根） | 实际结果 |
|---|---|
| `.venv/bin/python -m unittest` 计划指定 7 模块（新增 3 模块 + `test_task_persistence`、`test_task_pause_resume`、`test_automation_admission`、`test_automation_job_fencing`） | 103 tests, OK（含新增 46：调度 23 / 栅栏与并发 17 / 迁移 6） |
| 计划指定代表性写入/执行链 6 用例（C→A 精确移动与 uncertain 不重放、Files 准入、两种库 transfer、Run once） | 29 tests, OK |
| `tests.test_direct_file_operations test_confirmation_api test_task_retry test_task_scope test_manual_operations_contract test_file_index_retirement` | 110 tests, OK |
| `tests.test_operations_run_detail test_operations_task_center test_dashboard test_task_center_recovery_lineage test_processing_worker_readiness test_api_security` | 115 tests, OK |
| `tests.test_automation_settings_resident test_release_security test_container_probe` + 5 个 `test_configuration_*` 版本断言模块 | 101 tests, OK |
| `tests.test_automation_definition_occurrence tests.test_automation_run_once tests.test_cron_scheduler tests.test_workflow_retry tests.test_resident_correction tests.test_runtime_lease` | 87 tests, OK |
| `tests.test_direct_file_transfers test_media_library_transfers test_media_discovery test_manual_organize_execution test_task_center_recovery_lineage` | 333 tests, OK |
| `.venv/bin/python scripts/schema_upgrade_rehearsal.py --base-sha 45d2e951… --expect-schema 53 --expect-candidate-schema 54` | `ok: true`，165 条断言通过（含新增 `task_scheduling.absent_for_legacy_task` / `no_capacity_use` / `pin_unchanged`） |
| `ruff format --check` / `ruff check` / `compileall` 于 14 个改动 Python 文件；`scripts/check_governance.py`；`git diff --check` | 全部通过 |

新增测试使用真实临时 SQLite、独立连接、真实子进程（3 进程抢 1 个名额）与真实 Task Base 代码
（`git archive` 后子进程建库），不以内存储模拟原子性；未使用任何用户运行库/媒体/私有配置。

### 已知限制、范围说明与剩余风险（交 B 判定）

1. **未接入生产入口**：手工整理、Scheduler due、Run once、Files、API/CLI、驻留 Worker 仍走原
   Job/Task 路径；本 Task 未迁移 Job 数据、未退役 Job 接口/表、未实现共用整理引擎与四类恢复
   的生产改接。RO-2/3/5 与 Job 退休未交付，Slice 未完成。
2. **无通用过期抢占**：已发布 RUNNING 的 Task 在 owner 消失后保留名额与 uncertain 事实，本轮
   不提供“接管并分析边界”的入口（该路径属于后续 Task 与既有四类恢复边界）。
3. **`scripts/schema_upgrade_rehearsal.py` 的既有缺陷**：base 阶段因 `ManualSourceIdentity` 多传一个
   位置参数（`occurrence_state` 收到 datetime）而整体不可运行，与本 Task 实现无关但会阻断 B 的
   升级演练；我按其构造签名做了最小修正（改为关键字传 `occurrence_id`/`occurrence_state`/
   fingerprint），并新增旧行不入队断言。请在审查时确认该修正范围可接受。
4. **版本常量同步**：`SCHEMA_VERSION` 53→54，并同步 `ProcessingWorkerService` 默认值（该处注释
   明确要求随 schema bump 更新）与 7 处现行版本断言。`AutomationWorker` 的陈旧默认
   `runtime_schema_version=34` 未改（生产调用点均显式传 `SCHEMA_VERSION`），未扩大范围。
5. **文档未改**：`docs/architecture.md` 的 CURRENT/TARGET 契约、Task Center 规格与 Progress/Roadmap
   由 A/B 在 Slice 层维护；本 Task 只按增量 schema 事实交付代码与测试。
6. **性能/规模**：容量计数依赖 `task_scheduling(queue_state, …)` 索引；未做超大批量基准（容量
   上限 1024、租约上限 1 天为硬界）。真机多进程仅 3 进程规模验证，未做长时间压力。
7. **未执行的共享门禁**：完整 Python/Web/E2E、wheel、容器 fresh/restart/53→54 升级与 security
   smoke、desktop/narrow 截图等均由 B 按 T4 执行；本报告不宣称这些结果。

## B Review Result

```text
Reviewed Base: 45d2e951eb00ffdd4cecbaafed50039668e445f0
Reviewed Head: 21fe2a58f029baf58f6359eeafd41b551015116f
Implementation: e53e38999459f81da65f625ee3b73d39e9ff793e
Decision: FIX REQUIRED — 5 P1 blockers, same Task fix loop
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; preserve Task ID/Base/Goal/Scope
```

B 独立审查完整 Base..Head 的15个文件（含实现、测试、脚本、版本断言和交接记录），未修改
产品实现或测试，没有自审/角色例外。范围先按本 Task 的内部内核交付评估：生产三入口未切换、
旧 Job 未转换/退休是既定边界，不作为缺陷，也不误记为 Slice 完成。

### 五项阻塞的开发指导

以下指导细化同一 Task 的修正，不改变 Goal/Base/Difficulty/Test Level 或 T1–T10。
修正范围限于现有调度内核及直接受影响测试，不接生产入口，不增加恢复类型、队列、后台补偿器或
对外接口。下面的生活化例子解释接入后的保护目标；实际缺陷均从已有内部服务/锁端口复现，
不是当前 Web 故障证据。尤其第4项没有已证实的正常用户操作触发链，按内部归属契约修复。

主要修改位置：[应用服务](mediaflow/application/task_scheduling.py)、
[调度端口](mediaflow/domain/task_scheduling.py)、[SQLite 持久化](mediaflow/infrastructure/sqlite_runtime.py)；
回归放在既有[调度测试](tests/test_task_scheduling.py)与[栅栏/并发测试](tests/test_task_scheduling_fencing.py)，
不另建过程工具。

建议先修第4项的共用身份检查，再修第1项的执行资格、第2/3项的状态转换，最后完成第5项的
锁清理交错验证；可以合并共享事务逻辑，不拆新 Task。先把已复现链写进现有测试并确认失败，
再改实现；只做解决下述结果所必需的调整。

#### 1. P1 — 继续剩余文件时，不能重做成功项或结果不明的操作（T5/T6）

**保护目标与复现。** 同批 A 已成功、B 还需处理，继续时只能处理 B；A 的移动结果不明时，
也不能因为再试一次就重新移动 A。现有入口是 `TaskSchedulingService.begin_item()`、
`begin_mutation()`、`complete_item()`。已复现成功 A → 再 begin_item(A) → 再 begin_mutation(A)，
以及 begin_mutation(A) → 发布 partial/unknown Result → mutation 标记清除 → A 再次开始变更。

**开发步骤：**

1. 在 `mediaflow/application/task_scheduling.py` 明确开始/继续的资格；在
   `sqlite_runtime.py` 的 `_require_scheduled_item_locked()` / `upsert_scheduled_item()`
   等实际写入事务中重查耐久 item、Result、已有 checkpoint/effect 事实和当前 claim。
   不能只在服务层读一次状态，也不能仅凭 attempt +1 许可重做。
2. 已成功、已忽略的项不能重新开始；已派发但未证实的效果不能再次执行。首次未派发的新项
   仍可正常开始；证实无效果且已有规则允许的剩余分析/续作保留。复用
   `mediaflow/domain/processing_checkpoint.py`、`mediaflow/application/processing_checkpoint.py` 的安全语义，
   不把所有失败都当可重试，也不把所有历史项一律封死；本轮不接四类恢复的生产 dispatch。
3. `publish_scheduled_item_outcome()` 应在结果/item/evidence 同一事务中，按该次操作的证据
   决定能否清除 mutation 边界。`clear_mutation=True` 或 item ID 相同均不是安全证明。
   unknown、attempted_unverified 或非空 uncertain_effects 必须保留不重放保护；记录事实仍可
   落库，不能丢弃 uncertain Result 来过测试。成功证明和证实无效果按既有语义处理。
4. 核对现有 `record_item()` / `begin_mutation()` 不能绕过同一保护，拒绝将成功/不确定项改回
   可执行状态后重放。拒绝须保留原 item/attempt/Result/evidence、pin、授权和源占用。

**回归验收：**

- 在 `tests/test_task_scheduling.py` / `test_task_scheduling_fencing.py` 增加上述两条失败链；
  成功项再次开始或直接再次申请变更均拒绝，成功 sibling 的历史保持原值。
- uncertain Result 保存后，从另一真实 SQLite 连接及关闭重开后仍不能重放；超时/租约到期
  不会将其变成“未发生”。合法首次开始、证实结果清除边界和允许的无效果分析续作仍通过。
- 调整 `test_a_later_attempt_cannot_replace_a_recorded_outcome`：不再用重做成功项制造 attempt2，
  改用既有允许、明确无效果的分析尝试；保留旧 Result 不可覆盖和新历史可追加两类断言。
  证据 fixture 使用既有枚举含义（如 `verified_complete` / `none`），不能把非标准 `complete`
  当作已证实效果。沿用结果/item/evidence 的故障回滚测试。

#### 2. P1 — 等待或暂停时取消，之后不能又恢复执行（T4）

**保护目标与复现。** 用户在等待确认时取消本次整理，这个 Task 后续不能又排队执行；取消不
撤销已完成文件的效果。现有 `request_control()` 仅立即结算未领取的 QUEUED；已复现
waiting_human → request_control(CANCEL) → 带最新 control_revision 的 requeue → pending/queued，
已接受的 CANCEL 被清空。paused 的相同入口也须覆盖。

**开发步骤：**

1. 修改 `request_control()` 及其仓储边界：对已支持、无活动 owner 且无 in-flight 的等待/暂停
   状态，确认安全后完成取消；Task、适用未完成项、queue 和取消确认事实保持原子一致。
   所有安全条件和 control_revision 均在事务内重查，不能拿服务层旧快照释放后来取得的 claim。
2. 在 `requeue_scheduled_task()` 的事务内，除 Task.status 外还必须检查已接受的 CANCEL；
   即使调用方携带最新 revision，也不能把 CANCEL 清掉再入队。拒绝时不改 generation、pin、
   choices/summary/Results 或容量，不消耗/刷新授权。
3. 仍有 owner 或 in-flight 时只保存取消意图，由当前 owner 按原安全边界确认；不强制解锁、
   不打断 Storage 调用。保留取消请求/确认和历史，重复请求幂等，不允许 CANCEL 降级成 PAUSE。
   正常 PAUSE → 显式恢复仍保留，不能用“所有控制都禁止恢复”堵住问题。

**回归验收：**

- waiting_human、paused 各做“取消 → 恢复”和重复取消：最终取消事实保留，恢复零写入拒绝；
  已成功项和历史 Result 不改写。保留排队取消及 owner 安全确认的现有正向测试。
- 两个真实连接竞争取消/恢复，按事务先后验收：取消先提交，恢复不能抹掉它；恢复先提交，
  后续取消仍按恢复后的真实状态生效。不要求取消回溯撤销已经完成的效果。
- pending-control/in-flight 的名额不提前释放，正常暂停恢复、pin/revision 拒绝及满容量保留
  原状态的既有测试继续通过。

#### 3. P1 — 一部等待确认，另一部仍处理时，整批不能提前释放名额（T2/T4）

**保护目标与复现。** A 等用户选影片、B 仍处理中时，B 继续受当前 Worker 管理，这一批仍占
一个名额。现有 `defer_to_human()` 只提交 A 为 WAITING_CONFIRM、遗漏仍 PROCESSING 的 B，
`release_scheduled_claim()` 就接受整批 waiting_human、清除 owner，容量1→0并允许另一 Task 入队。

**开发步骤：**

1. 在 `release_scheduled_claim()` 的同一释放事务内，读取该 Task 已有 item/机器阶段事实，
   合并本次拟更新后判断是否真的全人工等待；遗漏在调用参数外的 sibling 也要参加判断。
   不能只相信 task.total_items/completed_items、传入 items 子集，或“没有 mutation 标记”。
2. 对仍有 PROCESSING/PENDING 机器工作的混合项，`defer_to_human()` 零写入拒绝释放。
   单个 A 的等待状态可经现有 `record_item()` 保存，B 继续用原 claim 发布；不新增调度入口，
   不把 B 改成等待来满足计数。只有真正全等待，才原子提交聚合、items 和名额释放。
3. 保持其他合法边界：全等待/安全确认暂停/终结依原语义释放，in-flight 继续拒绝；释放容量
   不释放耐久源占用、不删除已保存选择或成功/不确定效果。复用第4项的同 Task 身份检查。

**回归验收：**

- 创建同一 Task 的 A/B 两项，仅 A 等待、B PROCESSING（并覆盖仍排队的机器项）时释放被拒，
  owner/generation/容量保持，B 仍能合法发布。拒绝不会留下半个聚合更新。
- 对照：A/B 均进入合法人工等待后，名额只释放一次；重开仍为 waiting_human，源占用、选择、
  Results 保持。混合项变全等待的正常链仍可完成。
- capacity=1，用两个真实连接验证混合项期间新准入仍 QueueFull；全等待释放与新准入竞争
  不超额、不留孤儿 Task。不要只断言返回值，读回 claim、容量和 sibling 结果。

#### 4. P1 — 甲任务的数据不能用乙任务的领取凭据发布（T4/T5）

**证据边界与复现。** 这是已有内部接口的归属校验缺口；没有证实普通用户同时操作两个任务
就会触发。两个 Task 分别正常领取后，`defer_to_human(claim_B, task=A, items=A的项)` 会释放 A，
B 仍 claimed。没有伪造 token；原因是 `release_scheduled_claim()` 按 task.task_id 读目标，
却独立验证 fence 指向的 Task。

**开发步骤：**

1. 在任何写入前，验证 `task.task_id == fence.task_id`，并确保随后的 claim 检查、Task/item
   更新、控制版本、queue transition 均针对同一持久身份和领取代次。
2. 服务层可给出明确拒绝，仓储边界必须同样校验，不能让现有 repository 调用绕过。错误输入
   按既有有界领域错误拒绝，不得通过改写参数中的 task_id“纠正”后继续发布。
3. 保留 `fence=None` 仅适用于既有无 owner 安全控制结算的边界；不能借此释放已领取 Task。
   不新增前端参数、路由、权限弹窗或第二套身份映射。

**回归验收：**

- 用两个 Task、两个不同 Worker 的正常 claim，经上述已有服务复现交叉输入，修后拒绝；
  两个 Task 的聚合、items、queue/claim/generation、control、Result/evidence、锁均保持原值。
- 在实际仓储入口补绕过服务的同类拒绝，正确 claim_A + task_A 的释放仍成功；旧 owner/
  错代次/过期 claim 及无 fence 不能释放有 owner Task 的既有测试继续通过。
- 不为制造用户链路增加 Web/API 消费者；测试结论只写内部契约，不声称已复现当前页面串任务。

#### 5. P1 — 暂停后马上恢复，旧一轮收尾不能删掉新一轮的文件保护（T4）

**保护目标与复现。** 文件有“正在处理，其他执行者别碰”的保护。暂停后马上恢复，新 Worker
取得了新一轮保护，旧一轮迟到的收尾只能清理自己的保护。当前 `_settle_control()` 先提交暂停/
释放 claim，再调用不带 owner_token 的 `reclaim_task_locks(task_id)`，会删掉同 Task 的全部锁。
已用现有锁端口、两个连接和同步屏障复现“新锁存在 → 旧清理到达 → 新锁消失”。已证明的是
执行锁被误删，未证明当前页面已发生重复移动；耐久源占用也不能代替修复执行锁的归属错误。

**开发步骤：**

1. 核对 `_settle_control()`、`release_scheduled_claim()` 及既有
   `FileOperationLockRepository` 的 acquire/adopt/release 语义，明确本次实际拥有的锁代次。
   `owner_token` 是锁的实际代次，不能未经关联就假定它等于 Task 的 claim_token。
2. 选择一个最小、可证明的修法：在现有同库、仍验证当前 claim 的释放事务中清理该轮执行锁，
   与暂停确认一起提交；或在交出 claim 前绑定本轮实际锁代次，之后只对这些代次条件删除。
   跨两个独立仓储调用不能只靠调用顺序宣称原子。不引入新锁系统、额外清理 Worker 或等待时间。
3. 旧 owner 迟到/重复 cleanup 必须对新代次无效，不能在未匹配时回退到按 Task ID 全删。
   对既有 owner_token=None 锁走受 claim 保护的安全兼容处理，不能用 None 删除未来新锁；
   也不能简单移除全部清理造成旧执行锁永久残留。保留耐久源占用与短期执行锁的区别。
4. 暂停/取消仍只在原支持的安全边界确认；in-flight/uncertain 时不强行解锁。不改普通 transfer/
   manual 等尚未接入内核的锁语义，除非共享改动确实直接影响且附相应回归。

**回归验收：**

- 在 `tests/test_task_scheduling_fencing.py` 使用真实临时 SQLite 两连接、线程 Event/Barrier
  控制既有暂停结算与 cleanup 的交错，不用 sleep 碰运气，不直接改数据库伪造 claim/锁。
- 对暂停提交后的延迟清理方案：原 Task requeue → worker-2 正常领取 → 现有 adopt_or_acquire
  取得新 owner_token → 允许旧 cleanup 继续；新锁归属必须仍在，旧 claim 不能发布/删除它。
  若选择同事务清理，应证明恢复只能在该事务完成后取得新锁，旧确认返回后不会再做无归属清理。
- 正常暂停/取消仍清掉该轮应释放的旧执行锁，其他 Task 的锁不受影响；覆盖带 token 和既有
  None 锁、重复 cleanup、新 owner 自身合法释放，并保留源占用。沿用/扩展
  `test_acknowledging_a_pause_retires_only_this_tasks_execution_locks`，不能仅令清理完全不发生。

### 实际验证、范围及限制

以下产品验证对应上方 Reviewed Head，未因补充指导而重新运行。本次指导补充起点为 `main` /
`a13c4a7162f3f153743bac0f45482d308dcfe9d4`，只修改 TASK.md，保留既有无关 untracked 文件；
未改产品/测试实现，未新增产品测试结果。治理及差异检查通过，Task 仍为 FIX REQUIRED。

- 新增3模块：`.venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration`
  **46 / OK**，runner 3.163s、完整子进程墙钟3.345s；存在未关闭 SQLite 连接 ResourceWarning。
  通过并未覆盖以上拒绝/交错场景，不据此接受 T4。
- 使用上述已有测试夹具与真实临时 SQLite，从已有 `TaskSchedulingService` 方法及现有锁端口
  复现6条缺陷链（第1项两条，第2–5项各一条）。没有构造不存在的路由、改写原始数据，或把
  尚未接入内核的普通 UI/生产用户声称为已遭受影响。第5项仅在现有锁释放调用处设置同步屏障。
- 复用原测试相同的真实 Task Base schema53 建库/公开 repository 升级入口及容量索引故障注入：
  失败后 schema 仍53，`task_scheduling*` 残留对象为零。这次检查未发现迁移回滚阻塞；不扩大为
  所有历史版本/容器升级已通过。版本常量同步及演练脚本签名适配在必要范围内。
- 原始日志/可重复调用脚本仅本机 ignored evidence 可达：
  `.git/validation-evidence/b-task47.1-21fe2a58/` 下 `focused-tests.log`、`repro.log`、
  `lock-repro.log` 和对应脚本/README。未使用用户运行库、媒体、私有配置或外部服务。
- 本轮计时从 2026-10-30 11:39:48 UTC 开始；截至11:47:55 已有487秒复核，测试保守合计不足6秒，
  低于本轮50%限制。没有通过等待凑时长，也未把读码或写审查记录算成测试。
- 按 workflow §6，已证实 Task 阻塞，先 FIX REQUIRED，未执行昂贵全 Python/Web/E2E、wheel、
  native/截图和容器矩阵；它们仍是 B 在修正候选上的 T4 责任，不转交 Developer，不标通过。

### 修正交接与 Slice 全结果重评

Developer 在同一 Task 修正以上5项，运行新增失败回归、新增/变更及直接受影响测试，保留真实
失败和结果；无需先跑 B 的全量门禁。按用户要求安排实际工作使本轮测试时间低于总用时50%，
不通过删除安全断言、加重试或过度开发过程工具解决。提交新 checkpoint 后再次 READY FOR B REVIEW。
B 随后审完整 Base..新 Head，先重现上述关键链，再执行仍适用的 T4 验收。

| Slice outcome | 本次实际结论 |
|---|---|
| RO-1 Task 统一调度/执行 | 内核已实现部分能力，但上述阻塞未解决；未完成 |
| RO-2 三入口共用引擎 | 本 Task 明确未接生产入口；未交付 |
| RO-3 同工作四类恢复 | 只有内核基础，既有四类生产改接未交付，非重放/控制仍有本 Task 阻塞 |
| RO-4 数据保留并删除 Job | 增量54及代表性回滚检查通过；Job 整体转换/结构删除及完整升级门禁仍未完成 |
| RO-5 操作与管理旅程完整 | 仍保留原入口，Task 化集成尚未交付；完整兼容/最终验收未完成 |

Slice47 保持 ACTIVE，不关闭 Slice、不改变 A 的 Contract/原 Base，不规划下一 Task。
