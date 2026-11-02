# Task47.6 — 自动化设置只影响自动化工作，手动整理保持独立

Authority: committed `c443a769d5bcdd8dfa61b08f4655ed219b6c167b:SLICE.md`
的 settings-scope amendment、RO-1–5、AC-2/3/4/12/15/16/18/26，及
[Development Workflow](docs/development-workflow.md)。要求依据：V2-TASK-001–006/011、
V2-AUTO-007/008（按新修订解释）、REQ-TASK-005/006、REQ-SCHED-001/004/005、
REQ-SAFE-001–009。保留 RO-6/AC-20–25 和全部既有用户修订。

```text
Task ID: 47.6
Task Type: SLICE
Parent Slice: 47
Status: PLANNED
Task Base: c8657032dae768d93b12387a5e58db502e23a7ee
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Current correction: Automation-only settings scope (V2-TASK-011 / AC-26) and A-P1-2
```

## Replanning decision / preflight

**明确采用最新合同，重规划同一 Task。** 原“把所有入口统一到自动化容量 1–10000”的
指导已被覆盖，不能按旧计划实施；本轮不是单独改数字，也不是新 Task 或独立 minor bug。
Task ID/真实 Base 不变；目前没有实现候选，不签产品 PASS，不改 A-owned 合同或关闭 Slice。

- 本轮起点 `/Users/songzhidong/mediaflow`，branch `main`，HEAD
  `c443a769d5bcdd8dfa61b08f4655ed219b6c167b`。governance PASS，无预存 tracked 修改；
  workspace/Git 可写。原有 `.DS_Store`、`.mgmt.log`、`.t.log`、`.t_test_*.log`、`15`、
  docs 参考图/OS 文件、output 参考目录/ZIP/HTML、testdata/web OS 文件全部保留不暂存。
  不读取用户媒体、数据库或私密配置；不派生代理、push 或部署。
- Slice Base 保留 `5144ab1fc2344b06194969cc2c496835729664c0`；Slice FIX REQUIRED，
  Roadmap ACTIVE。A 最后审查候选仍为 `5c808d4a67bedfbafb71d88a1ffa8d3480ef5316`。
  Task47.1–47.5 接受历史不变，Task47.5 packet 留在 `7ac253dd:TASK.md`；CLI 收尾
  A-P1-1 和批量路径 B-P1-1 已验证修复，本 Task 不重开其原 Goal/Base。
- 前序本 Task 规划/补充证据保留在 `d0c071c8:TASK.md`、`abbbd5af:TASK.md`。B 已独立
  复现“设置 Save 1025 成功 → 普通 CLI 被 1024 拒绝 → Save 1024 → 实际 COPY”；
  A 补证“Web Save 1025 → Files 批量整理 400/无效刷新提示 → Save 1024 → 原摘要/确认
  → 实际 MOVE”。证据在 `.git/validation-evidence/c8657032/b-planning-47.6/` 及
  `.git/validation-evidence/5c808d4a/a-final-review/web-capacity/`，均为本地 ignored。
  这些缺陷事实保留，但旧的全入口共享额度解释不再有效；本轮未重跑旧浏览器缺陷脚本。
- 本轮仅改 B-owned Task。governance、`git diff --check` PASS；
  `.venv/bin/python -m unittest tests.test_release_security` 为 **8 tests OK / 0.021s**。
  本轮测试耗时远低于总用时 50%；未实施产品修改或宣称完成新合同验收。

## Goal / complete journeys

**自动化设置仅控制自动化，手动整理不受它的额度、轮询或失效判定限制。** 保留一个
Task 生命周期、repository 调度权威、claim/heartbeat/fence、整理应用引擎和 Executor。
不新增队列、运行身份、Worker 并行度或配置页面。

1. **正常设置与手动整理：** 自动化 → 全局设置 → 保存合法 1/1025/10000 与其他三个
   字段 → 看见本次 Active 与真实自动化消费范围。然后 Files 单选/多选/文件夹/混选 →
   批量整理 → 同 Task 的原摘要 → 正常明确确认 → Worker 产生实际 MOVE/COPY 与独立
   Results。普通直接 CLI/API/remote-source 整理也可按原授权完成。无需降低自动化设置、
   重启、绕过确认或手填内部信息。
2. **自动化额度已满：** 设置自动化容量 1；定义 due/Run once 的来源 A 已占用该额度。
   用户对另一个来源 B 发起 Files 手动整理或普通直接 CLI/API/remote 整理，可以准入并
   完成，不增加自动化占用。反向先存在手动工作，也不占用自动化的 1 个名额。
   同一具体来源仍有跨入口所有权保护；独立额度不是重复整理同一文件的许可。
3. **自动化保持原约束：** Run once 虽由用户点击，仍属于定义自动化工作。额度真的满时，
   新 Run once 拒绝而不创建孤儿/消耗授权，due 保持待调度；等待人工的自动化 Task 在
   Task Center 决定/分析/确认后仍用原自动化范围重入。用户等自动化名额释放后主动重试
   原允许操作，不因换页面、换点击者或人工恢复而变成手动工作。
4. **消费、失败与恢复：** 改变自动化 Worker/Scheduler 轮询或观察阈值后，实际常驻
   消费者在安全边界采用并如实回报自动化范围；手动工作自己的调度周期、心跳/lease/
   失败规则不随之改变。配置非法则不发布，原 Active/输入保留；未知发布按现有精确
   读回核对。真满的是哪类额度要说清，现有工作/选择/摘要/结果不丢。取消、未知效果
   和同版本 restart 沿用安全边界，不新增自动重放、自动标失败或抢占承诺。

## Actual-code gap / sources of independent manual policy

当前代码仍把这些设置提升成所有整理的策略，尚未实现上述范围：

| 当前真实出处 | 本 Task 的具体处理 |
|---|---|
| `domain/task_scheduling.py::MAX_TASK_CAPACITY=1024` / `require_capacity`；settings/runtime/Scheduler 支持 1–10000 | 自动化消费接受原整数 1–10000；通用上界可复用，但不得等同于所有入口的实际额度来源。 |
| `sqlite_runtime.py::_scheduled_capacity_use_locked` 无来源过滤，所有 queued/claimed 都计数；各 admit/requeue/确认事务复用 | 在同一 repository/事务中按持久来源选适用范围并计数；手动与自动化各有有界名额，不再共用自动化设置额度。总量诊断若保留须与额度计数区分。 |
| `media_discovery.py::_shared_capacity`、`manual_organize_execution.py`、`service_api.py` 的 continuation factory、`final_cli.py::_admit_direct_organize_task` 都读自动化值；remote `ExecutionAuthorizationService` 也接收该值 | 每个准入/确认/重新分析/继续/remote 消耗路径均使用可信原工作范围解析策略；不能只改新建 Files 或 CLI。 |
| `final_cli.py::_run_worker` 把自动化 Worker poll 装进进程级 `ResidentLoop`，step 再调用混合 `ResidentProcessingWorker.run_next` | 同一常驻进程按范围选择可运行候选和下次检查时刻；自动化 poll 只驱动自动化，手动周期独立。选择 pending pin、注册和 claim 必须对齐候选，防止队头自动化长轮询挡住手动。 |
| `TaskTrigger`、Task scheduling 原始准入记录、定义 occurrence/Run once origin 及 display/intent 关联已存在；`ManualTaskEngineWorker._is_automatic` 也会运行 CLI/remote | 复用持久关联证明来源；不能靠 runner 名、是否点击按钮、恢复动作发起页面或客户端字段来分类。不要把共用 automatic runner 的 CLI/remote 算进自动化。 |
| `automation_settings.py` 逐实例 cadence evidence 和 API-local capacity/stale 发布说明；`service_api.py` 传递 stale 参数 | 读回必须如实说明自动化范围和真正使用的值。现有 stale 参数并不等于已运行观察器；核对实际消费者，不能用参数/Active 回显伪造采用。 |

**本轮明确的手动运行策略来源（内部默认，非新产品设置）：**

- 手动容量采用集中定义的 **100**，取自现有 `TaskSchedulingService` 各组合路径、API
  与 `ExecutionAuthorizationService` 的默认/回退值 100；本轮把它独立成手动默认，
  不再从 Active 的 `automation.maximumActiveJobs` 派生。保留现有受信构造注入能力
  供运行组合/测试使用；`MediaFlowApi.maximum_active_jobs` 现有自动化 override 不可
  再经共享 binding 泄漏成手动策略。不添加手动 CLI flag、环境变量或表单。
- 手动常驻调度默认 **5.0s**，来自 `final_cli.py::_resident_infrastructure_defaults()`
  的现有 poll fallback。既有 `worker run --poll-seconds` 是显式运行 override，保持
  高于默认/自动化表单；其实际适用范围与回报必须明确，不能因表单 Save 被覆盖。
  自动化自己的 cadence 继续按其配置/已有 override 消费；不把手动 tick 变成提前
  自动化 poll，也不让很长的自动化 poll 阻止手动 tick。
- 手动 claim/失联安全沿用现有值与来源：Task service 默认 lease 30s、
  `ManualTaskEngineWorker.DEFAULT_LEASE_SECONDS=300s`、注册 heartbeat 5s 及
  `domain/automation.py::worker_stale_threshold_seconds`。不是本轮要统一的数值，
  各原路径保持原规则，均不得读取 `automation.staleJobAgeSeconds`。失联仍不证明无效果。
  自动化 stale 只用于其已有无更新观察语义；若 Job 退出后丢失有效消费，在现有 Task
  观察/读回边界最小补齐，不能新增超时取消、强制终态、重排或恢复产品。

## Implementation Scope / Developer guidance

1. **先固化真实入口回归。** 复用 `entrance_journey`、既有 settings WSGI helpers、
   Scheduler/Run once/Files fixtures 和真实 resident subprocess。保存自动化容量 1 后
   从真实定义准入 A，占住自动化名额；经真实 Files/CLI 对不同文件 B 准入并完成。
   反向验证已有 manual 不吃自动化名额，再验证真正第二个自动化工作拒绝。禁止直接
   INSERT 队列、伪造 Task 状态或 mock count 来代替主要集成证明。
2. **在共享 domain/application 表达范围策略。** 复用后端写入的 trigger 与定义 provenance
   建立单一可信范围解析，供 admission、count、claim eligibility、continuation 共用。
   只在真实入口决定新工作来源；已存在 Task 从自己的持久记录解析，冲突/无法证明的
   自动化关联不能默认降成手动绕限。保持原 pin、request idempotency 和授权语义。
   尽量利用已有列/关系；不建立第二队列或独立状态机，不为此建设历史迁移系统。
3. **改全事务边界。** 在 SQLite 同一事务内核对来源、适用容量、来源所有权、due 唯一性、
   具体操作授权/消费与工作重入。覆盖 due、Run once、Files、direct CLI、remote ticket，
   以及等待人工后的分析/摘要确认/四类继续。Task 全部人工等待占 0；机器工作/稳定等待
   占本范围 1；在途取消仍占原范围，安全结束才释放。不要先在应用层 count 再写库。
   范围隔离不能放松跨范围的同文件互斥、fence 或历史未知非重放。
4. **分离消费周期而非执行引擎。** 保留单个 `ResidentLoop`/Worker 和 claim 协议；在既有
   step/候选查询增加范围资格和各自业务 deadline，物理 wake 可取下一手动/自动化/
   heartbeat/config-recheck 的最早时刻。自动化唤醒不能提前处理自动化，手动 deadline
   不受其 Save 改变。仅一个 in-flight pass；不抢占 Storage 调用、不另开 Worker/线程。
   `pending_snapshot` 和真实 claim 选择应一致，避免用不合适 pin 注册后饿死另一范围。
   手动无需“立刻执行”保证；正在处理的其他工作带来的资源等待保持诚实。
5. **四字段与 UX 一起闭环。** Scheduler poll 仅管自动化 due；Worker poll 仅管自动化
   候选；stale 观察仅作用于自动化；capacity 只算自动化原始工作及其继续。API/Web 的
   简短意义、队满拒绝和逐实例采用证据须讲清自动化范围，移除误称所有整理共享的含义，
   不换表单位置、不添加新控件/额外确认。不能用旧 Published 提示证明本次 Save，等待
   本次 PUT 与新 Active/采用读回。保留 Save 对无关 Draft/设置的隔离和不可变 digest。
6. **补真实 Web 与交接。** 在 `web/tests/e2e/automation-settings.python.spec.ts` 增加
   `automation settings leave manual organizing independent` 场景：表单 Save 1025/10000
   后 Files 正常摘要/确认/真实效果；另以容量 1 的真实自动化占用验证不同来源手动仍可
   完成。既有 harness 只推进真实 Worker/读取隔离文件事实，不代替正常页面命令。
   改前应暴露错误，改后不能靠降值/重启/route mock/吞 400 通过。跑受影响检查后提交
   READY FOR B REVIEW，B 再做 T4 与整个 Slice 重评，不自判 PASS。

## Acceptance Criteria

- [ ] **AC-S1 — 自动化合法范围与严格发布。** 现有表单/API 仍支持 capacity 1–10000，
  1/1025/10000 均供真实 due/Run once 准入、执行并持久化正确 Task/Result；无需创建
  10000 个任务。0/10001/bool/小数/错误类型拒绝，保留 Active/输入，无工作/Provider/
  媒体效果；三个其他字段保留既有严格范围，Save 不发布无关 Draft。
- [ ] **AC-S2 — 双向额度隔离。** 自动化容量 1 被真实 due 或定义 Run once 占用时，
  不同来源的 Files/direct CLI/API/remote-source 工作仍能准入和完成；反向多个手动
  queued/claimed 工作不挤占自动化额度。手动仍受独立默认 100 或受信注入的适用有界
  容量保护，不是无限准入。真满的自动化 Run once/due 和手动各自拒绝/恢复正确，
  不新增孤儿、消费授权、推进 due 或偷偷自动续作；同请求重复满时仍精确读回原工作。
  手动真满可用现有受信构造注入小容量验证，不要求堆满默认 100；正常入口默认值另核对。
- [ ] **AC-S3 — 原来源与同 Task 继续。** due/Run once 不论入口 Web/API/CLI 都属于
  自动化；ordinary remote/direct CLI 不因共用 runner 变自动化。等待人工后由 Task
  Center 触发四类决定/分析/确认，仍用原来源与 pin，不因点击者/页面变换额度或刷新
  授权。覆盖两类等待重入、原子最后名额竞争、并发重复 due、unknown/伪造来源拒绝。
  来源反例基于现有入参校验和持久关联，不构造不存在的入口或正常旅程不可达的漏洞。
- [ ] **AC-S4 — 四字段真正隔离消费。** 逐个合法改变 capacity、stale、Worker poll、
  Scheduler poll，手动准入/确认/重入容量、实际常驻调度 deadline、观察/失败规则不变。
  在真实 resident 中保存很长自动化 poll（如 3600s），不同来源手动仍按独立周期推进
  到实际效果；不能只调用 `run-next` 或读采用行替代常驻行为。手动短 tick/配置 recheck
  不提前触发自动化业务 poll/due。观察阈值与 lease/heartbeat 区分，不自动重放/标终态。
  采用读回只证明实际已安装的自动化范围/值，显式 override、live/stopped/pending 保真。
- [ ] **AC-S5 — 完整 Web。** 两个高合法容量经真实表单 Save→本次 Active→Files 单选
  →批量整理 202→原摘要→正常确认→真实 Worker/Executor 整理，确认前零媒体变更，
  后有正确源/目标、Result/pin 和页面状态。容量 1 且自动化已满时该不同来源旅程也成功。
  保留多选/文件夹/混选实际范围和过滤；无本次 400/无效刷新提示、降值、额外确认或
  CLI 代替操作。检查桌面/窄屏关键状态；按钮回归和类型检查随受影响 Web 文件覆盖。
- [ ] **AC-S6 — 跨范围安全/持久化。** 自动化与手动争用同一真实来源仍只允许有效所有者；
  claim/control/fence、未知结果非重放、取消调用中不提前释放、全部人工等待占 0、独立
  Result/成功兄弟保留。设置发布和同版本 reopen/restart 不改 admitted pin、原始来源、
  结果/digest；重启后自动化采用/手动独立周期与额度仍真实。A-P1-1/B-P1-1 不回归。
- [ ] **AC-S7 — 独立接受与停止。** B 审完整原 Task Base..candidate 并执行适用 T4；
  重评全部 Slice RO-1–6/AC-1–26，满足后提交 fresh Closure Packet 交 A 终审整个 Slice
  Base..Head。未执行门禁不能算 PASS；无必需缺口即停止规划，不由 B 关闭 Slice。

## Required Tests

遵守 [workflow §6](docs/development-workflow.md#6-test-levels)。每轮测试时间小于本轮
总用时 50%；优先真实关键复现与代码/结果分析，记录实际测试耗时，不空等补比例、不删
断言/加重试/放宽超时。无法完成的验收保留 pending，不能签 PASS 或交 Developer 跑全量。
测试使用临时 DB/媒体、fake/local Provider 和既有 harness，不用用户服务或生产数据。

### Developer — affected tests

在现有模块补成功/非法输入/真满/来源冲突/失败/并发和实际 resident 隔离回归：

```bash
.venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_source_ownership_race tests.test_automation_task_admission tests.test_automation_run_once tests.test_automation_entrance_recovery tests.test_execution_authorization tests.test_media_discovery tests.test_manual_organize_execution tests.test_manual_task_engine
.venv/bin/python -m unittest tests.test_automation_settings_management tests.test_automation_settings_resident tests.test_resident_services
.venv/bin/python scripts/check_governance.py
git diff --check
```

第一组覆盖来源/事务/各入口/授权/四类继续/安全结束，第二组覆盖四字段 Save/readback、
真实子进程 cadence/override/heartbeat/restart。需要重新评估旧断言的业务含义：旧“手动
占满自动化”或进程级 poll 断言按新合同改为双向隔离的效果断言，不只删除测试。
按实际改动追加直接受影响的 `tests.test_operations_task_center`、
`tests.test_automation_definition_occurrence`、`tests.test_automation_execution_intent` 等模块。
Python 改动文件跑 ruff check / ruff format --check / compileall；Web 改动跑相关静态/
unit 检查。Developer 不承担全仓 Python/Web/E2E、wheel/Docker 或发布矩阵。

新增 Web 回归由 Developer 在 `web/` 执行（复用独立发布 harness，不是全量 E2E）：

```bash
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts --grep 'automation settings leave manual organizing independent'
```

命令必须实际选中高值两例和自动化已满例，零匹配不算通过；不同临时来源避免前例 MOVE
移走文件。正常表单/导航/选择/确认都用页面动作，harness 仅驱动真实后台/读取证据。

### B — acceptance and full regression

- 审完整 `c8657032dae768d93b12387a5e58db502e23a7ee..candidate`，同时单独核对本次
  `c443a769..candidate` 的实现增量和新合同；不 repin Base、不以改常量替代范围隔离。
  从上述已有入口独立验证 AC-S1–6，包含实际满额双向隔离、人工重入/授权与 resident
  长自动化 poll 下的手动真实执行。旧缺陷脚本只证明旧事实，不是新接受结果。
- 按 [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)
  执行新候选全 Python、适用 Web/static/unit/fake E2E、示例/禁依赖、安全/并发/持久化，
  clean wheel/source-external installed consumers、Docker fresh/security/同版本 restart。
  安装产物中也证明自动化容量已满/高合法值下的普通 CLI 与自动化实际结果，不以 help
  或源码测试代替。旧任务/跨版本升级与 V1 按用户边界排除。
- native 在 `web/` 先 build；设置及新 Web 场景：
  `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts`。
  其他自动化场景另开新 harness：
  `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-run-once.python.spec.ts tests/e2e/automation-workspace.python.spec.ts`。
  不并行共用可变 Active。检查真实桌面/窄屏；原 Files/四类恢复/历史提醒/两类库普通操作
  等全 Slice 必需 native 按最终新输入补齐，不建新过程平台。
- 仅依 workflow 的 source/tests/harness/dependencies/config/artifact 一致性证据复用 B
  原验收；本 Task 改变 scope/repository/resident 后受影响的执行证明要重跑，不能仅凭旧
  PASS。记录精确 SHA、命令/cwd、实际结果/skip、稳定 ignored 日志与产物身份。
- 最后重评 Slice 原 Base `5144ab1fc2344b06194969cc2c496835729664c0..candidate` 的
  RO-1–6/AC-1–26 与全部必需表面；符合后停止并交 A，不新增可选清理任务。

## Non-goals

新设置页/手动调参入口、表单改位置、第二队列/Worker/引擎、并行度/抢占/全新公平调度、
容量压力或 10000 Task 测试、普通文件/通知队列重做、旧任务/跨版本迁移、V1、历史/pin
改写、自动 unknown 重放/超时失败/强制取消、第五恢复、远端核验系统、广泛无关重构或
验收平台、重做 Task47.5 目标、A 终审/关闭。必要调度 ports/查询/组合调整属于本 Task。

## Current whole-Slice reassessment

| 结果 | 新合同下的当前判断（不是新候选接受） |
|---|---|
| RO-1 | 一 Task/claim/fence 已交付；全局计数未按来源划分，独立额度与 AC-2/26 待本 Task。 |
| RO-2 | 引擎已共享；必须保留共用管线并隔离入口策略，手动不能继承自动化四字段。 |
| RO-3 | 原四类同 Task 证据保留；继续时来源/额度/cadence 不能被人工点击改变，需受影响验收。 |
| RO-4 | fresh/同版本和 Job 退出前序事实保留；配置合法范围/不可变 pins/AC-12/26 未满足。 |
| RO-5 | 现 Web/CLI 阻塞及误导恢复仍在；设置范围/实际消费者/说明需闭环，其他已交付表面保留。 |
| RO-6 | Task47.5 与 A 验证事实保留；本 Task 保持最新失败历史规则、手动提示与来源互斥，防止回归。 |

## Developer Completion Report

待实现。交接完整 checkpoint SHA / READY FOR B REVIEW、行为/文件/策略来源和关键
决策、新改/受影响测试实际命令结果与耗时、失败/风险/剩余工作；full acceptance pending B。

## B Review Result

本轮决策：按 committed settings-scope amendment **重规划同一 Task47.6**；原数字统一
方案已替换，ID/Base 与缺陷事实保留。当前无实现候选，Task PLANNED、Slice FIX REQUIRED。
下一步 Developer 仅按此新范围实施，随后 B 独立审完整原 Task Base..Head 并按 AC-S7 收尾。
