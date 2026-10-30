# Task 47.1 — Task 调度与持久化内核

Authority: committed [SLICE.md](SLICE.md) at `45d2e951eb00ffdd4cecbaafed50039668e445f0`；
[Development Workflow](docs/development-workflow.md) 管理生命周期、检查点和测试分工。
阅读对应 [B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md) 经验。

```text
Task ID: 47.1
Task Type: SLICE
Parent Slice: 47
Status: READY FOR B REVIEW
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

尚未审查。等 B 独立复核 `Task Base..candidate`、复现 T2/T4/T6/T8，并执行适用 T4 门禁后填写
PASS 或 FIX REQUIRED；Slice 结果仍待该验收。
