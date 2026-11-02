# Task47.6 — 保持合法容量设置到实际整理的一致性

Authority: committed [SLICE.md](SLICE.md) 的 A-P1-2、RO-1/2/5、AC-2/4/12/15/16/18，
以及 [Development Workflow](docs/development-workflow.md)。要求依据：V2-TASK-001/002/005/006、
V2-AUTO-007/008、REQ-TASK-005/006、REQ-SCHED-001/004/005、REQ-SAFE-001–009。
按 Slice 用户修订解释；旧任务/跨版本升级与 V1 不在本轮范围。

```text
Task ID: 47.6
Task Type: SLICE
Parent Slice: 47
Status: PLANNED
Task Base: c8657032dae768d93b12387a5e58db502e23a7ee
Difficulty: Medium
Test Level: T4
Planner / Reviewer: B
Blocking finding: A-P1-2 — published legal capacity exceeds Task kernel range
```

## Planning preflight / retained facts

- 仓库 `/Users/songzhidong/mediaflow`，branch `main`，起始 HEAD 为上述 Task Base；
  `python3 scripts/check_governance.py` PASS。工作区/Git 可写，无预存 tracked 修改。
  预存未跟踪项：`.DS_Store`、`.mgmt.log`、`.t.log`、`.t_test_*.log`、`15`、
  `docs/.DS_Store`、`docs/pics/.DS_Store`、`docs/pics/自动化页-全局设置.png`、
  `docs/pics/自动化页.png`、`output/database-reference-2026-11-01/`、
  `output/imagegen/slice45-task-center-v1.zip`、`output/organize-flow-2026-11-01.html`、
  `testdata/.DS_Store`、`web/.DS_Store`，全部保留、不暂存；私密配置不纳入提交。
- Slice Base 保留 `5144ab1fc2344b06194969cc2c496835729664c0`；Slice FIX REQUIRED，
  Roadmap ACTIVE。A 最新完整审查候选为 `5c808d4a67bedfbafb71d88a1ffa8d3480ef5316`。
- Task47.1–47.5 的接受历史不改写。Task47.5 完整 B PASS/六结果 packet 保留在
  `7ac253dd11ab3453f36cd40500c79c72b4f888de:TASK.md`；A 已独立验证 CLI 结束名额
  A-P1-1 和批量 Storage 路径解析 B-P1-1 修复。本 Task 不重开其原 Goal/Base。
- 本轮是规划，不实施产品修复、不签新候选 PASS、不替 A 关闭 Slice；不改 A-owned
  SLICE/Roadmap/Progress、CURRENT/TARGET 或流程工具，不派生代理、push 或部署。
- 规划检查：governance、`git diff --check` PASS；
  `.venv/bin/python -m unittest tests.test_release_security` **8 tests OK / 0.022s**。
  关键复现与该测试合计约 0.50s，连同短检查远低于本轮总用时 50%；未跑全仓验收。

## Goal / complete journey

用户在 **自动化 → 全局设置** 将并行任务上限保存为合法值 1025 或 10000，看到确切
Active 值；之后从既有资源库 Files、运行一次、定时或普通 CLI/remote 发起已授权的
整理，实际消费者接受同一个合法范围，少量正常媒体能完成真实整理并保留 Task/Result。
容量是同时占用共享准入名额的 Task 数，不是文件数、Worker 数或新并行度。

异常输入仍在发布/消费边界被拒绝，保留原 Active 且没有新增工作/效果。真正队满时，
保持已有任务、选择、摘要、结果和授权；用户看到队满原因，可以在名额释放后主动重试
原命令。定时工作保留原 due，等正常下轮调度，不产生孤儿 Task 或偷偷自动续作。
不要求用户手改配置文件、降低合法容量、重启或重做已经成功的文件来绕过该缺口。

## Observed gap / actual-code scope

B 独立复跑 A 已有真实入口脚本（仅临时 SQLite/LocalStorage，MetadataProvider 为 fake）：
`Settings GET 200 / capacity 100 → PUT 1025 201 → CLI organize exit 2 / Tasks 0 →
GET Active 1025 → PUT 1024 201 → 原 CLI exit 0 / 实际 COPY 目标 1`。
原 CLI 为 `mediaflow --config <bootstrap> organize <source> --execute --limit 1`。
没有虚构路由、手填数据库或用一万条任务制造失败。
本轮原始日志：`.git/validation-evidence/c8657032/b-planning-47.6/capacity-settings-journey.log`
（本地 ignored），脚本位于 `.git/validation-evidence/5c808d4a/a-final-review/`；
这是缺陷复现成功，不是修复验收通过，执行用时约 0.48s。

实际不一致：

- `domain/automation_settings.py::ENGINE_FIELD_SPECS`、`domain/system_settings.py`、
  `domain/automation.py::SchedulerConfigurationSnapshot`、
  `infrastructure/runtime_configuration.py`、`application/execution_authorization.py`
  保留整数 1–10000；现有设置 GET/PUT 的确发布该范围。
- `domain/task_scheduling.py::MAX_TASK_CAPACITY = 1024` / `require_capacity` 把消费范围缩小。
  `application/task_scheduling.py::TaskSchedulingService` 构造和
  `infrastructure/sqlite_runtime.py` 的准入、due、重新分析、确认/requeue 等事务复用它。
- `final_cli.py` 普通准入与常驻组合使用 runtime 容量；
  `application/media_discovery.py::_shared_capacity` 服务 Files，
  `application/manual_organize_execution.py` 服务确认；
  `application/automation_run_once.py` 从 Active 取值；`application/automation.py`
  的 Scheduler 从快照取值后调用原子 repository。修复不能只让设置读回或 CLI 构造通过。

## Implementation Scope / Developer guidance

1. **先补真实回归。** 复用 `tests/test_automation_entrance_recovery.py::entrance_journey`
   与 `tests/test_automation_settings_management.py` 的真实 WSGI GET/PUT/helper，在同一
   managed DB 保存 1025/10000 后运行真实 CLI，断言 Active、Task/pin、Result、COPY
   文件效果及终态容量，而非只断言常量/函数接受整数。修改前应复现现有消费失败。
2. **最小统一合法边界。** 保持所有公开设置/配置路径的整数 1–10000 契约，让 kernel
   及 repository 的同一验证覆盖此范围。优先复用一个无依赖循环的 domain 容量上界，
   必要时在现有 domain 模块中共享；各边界的输入错误语义可以保留。无需为一个数建立
   配置框架或做全仓重命名。不能改成无限制、放过 bool/小数，或把 1025 静默夹到 1024。
3. **核对真实消费者。** 在现有 fixture/入口中覆盖高合法值的 Files 准入→摘要→确认→
   Worker 效果、Run once、due→Worker、普通 CLI 和已支持 remote ticket。可以跨场景
   分配 1025/10000；所有入口不必重复完整数值矩阵，但不能只 mock 参数传递。
   不改其权限、选取范围、itemLimit、Run once `min(itemLimit,100)`、定义 due/一次意图。
4. **保留容量/持久化安全。** 沿用现有 count 与事务，不改 queue-full/authority/source
   检查顺序或 slot 语义。用容量 1 的既有少量工作证明满/释放/重试、并发重复准入及
   人工等待重入；无须塞满 10000。高合法配置发布后同版本 reopen/消费者重新装载仍能
   实际工作；已有 admitted pin、文档内容/digest 和结果不可因新设置被重写。
5. **只交接本 Task。** 跑新/改/直接受影响测试与改动文件静态检查，提交完整实现 checkpoint
   和简明结果，置 READY FOR B REVIEW。若实际发现需改 schema/流程/范围，先交 B 评估；
   不顺手修无关文案、重构调度器、清理旧源码注释或开发新验收工具。B 负责 full gates。

## Acceptance Criteria

- [ ] **AC-CAP1 — 合法设置可用。** 既有全局设置 GET 仍发布 1–10000；Save/readback
  1025、10000 后，同一部署的普通 CLI 完成实际 COPY；1/1024 的已有能力保持。
  每次成功有正确 Task、对应 Result、确切配置 pin 和文件效果，结束占用 0。
- [ ] **AC-CAP2 — 各入口一致。** Files 的原摘要/确认、Run once、due 和支持的
  remote-ticket 工作在高合法容量下经真实消费者推进并产生真实结果；没有 Job/第二队列，
  无参数绕过或入口专用 clamp。定时/Run once/手动各自授权、范围和限额不变。
- [ ] **AC-CAP3 — 输入与发布失败安全。** 0、10001、bool、小数及错误类型不被当作
  合法容量；现有设置 Save 拒绝时 Active/pin 不变、零工作/Provider/媒体效果。
  kernel/repository 消费验证不比公开范围更窄或更宽，沿用现有严格类型检查。
- [ ] **AC-CAP4 — 原子容量语义。** 真实队满拒绝不创建孤儿 Task、不消耗授权；due
  不推进、不新增 occurrence；已有 waiting 选择/摘要/results 保留，显式重试可恢复。
  同一请求去重、来源互斥与 fencing、人工等待占 0/机器工作占 1、活动调用取消不提前
  释放、结束失败/未知证据保留但无机器工作时释放均不退化。使用小容量既有测试即可。
- [ ] **AC-CAP5 — 配置与历史。** 同版本 reopen/restart 后高合法值仍可消费；新发布
  不修改已有 admitted pin/历史快照/digest、Result 或未知效果。不降低支持范围，不以
  改 key、清库、重写快照或新增迁移消除错误；显式部署/CLI override 优先语义保持。
- [ ] **AC-CAP6 — 独立验收/停止。** B 审完整 Task Base..candidate 并做适用 T4 验收；
  对全部 Slice RO-1–6/AC-1–25 给出当前重评、实际证据和限制。满足则新 Closure Packet
  交 A 审完整 Slice Base..Head，不再为可选证明造 Task，不由 B 宣布 Slice CLOSED。

## Required Tests

[workflow §6](docs/development-workflow.md#6-test-levels) 规定分工。每轮测试时间必须
小于该轮总用时 50%；先查代码/结果、复现关键阻塞再执行门禁，记录实际耗时。
不以空等补比例、不删断言/跳过失败或放宽超时。若本轮无法满足时间约束并完成所需门禁，
保留验收待完成及实际原因，不能签 PASS 或转交 Developer 跑全量。

### Developer — affected tests

新增数值矩阵和真实发布→消费旅程放上述现有模块；Scheduler/Files/Run once 分别复用
下列现有集成测试，按实际改动补断言，不新建通用 runner。直接受影响集合：

```bash
.venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_automation_settings_management tests.test_automation_settings_resident tests.test_automation_entrance_recovery tests.test_automation_task_admission tests.test_automation_run_once tests.test_media_discovery tests.test_manual_organize_execution tests.test_task_source_ownership_race
.venv/bin/python scripts/check_governance.py
git diff --check
```

对实际新增/修改的 Python 文件执行 `.venv/bin/ruff check <files>`、
`.venv/bin/ruff format --check <files>`、`.venv/bin/python -m compileall -q <files>`。
若修改 runtime/Scheduler/authorization 等共享验证，追加其直接受影响模块
（例如 `tests.test_automation_definition_occurrence`、`tests.test_automation_execution_intent`、
`tests.test_system_settings_management`），报告实际命令。测试只用临时媒体/SQLite、fake/local
Provider。Developer 不承担完整 Python/Web/E2E、wheel 或容器矩阵。

### B — acceptance and full regression

- 先审 `c8657032dae768d93b12387a5e58db502e23a7ee..candidate` 全部变更；独立通过现有
  settings GET/PUT→真实 CLI 验证 AC-CAP1/3/5，再查 AC-CAP2/4 的实际结果。不复用仍然
  断言 bug 存在的 A 脚本作为“修复通过”；用正确效果断言独立验证。
- 执行 [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)：
  新候选全 Python、静态质量/示例/禁依赖、适用 Web/unit/fake E2E、native、安全/持久化、
  干净 wheel/source-external installed consumers 和 Docker fresh/security/同版本 restart。
  安装包也验证合法高容量的真实 CLI 准入/效果，不以 help 或源码测试代替。
- native 复用真实 Python harness（cwd `web/`，先 `npm run build`）：
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-settings.python.spec.ts tests/e2e/automation-run-once.python.spec.ts tests/e2e/automation-workspace.python.spec.ts`。
  对实际全局设置 Save→读回→整理结果检查桌面/窄屏；原 Files、四类续作、历史提醒与
  普通文件操作等全 Slice 必需 native 依据现有最终包补齐/匹配复用，不写新的测试平台。
- 如输入完全未变，按 workflow 的明确 source/tests/harness/dependencies/config/artifact
  diff 复用 B 已有相同 Web 验收；Python runtime/安装产物已变的 native/wheel/image 不可
  仅沿用旧 PASS。每项记录精确候选、命令/目录、实际结果/skip 和稳定 ignored 原始日志。
- 最终同时检查原 Slice Base `5144ab1fc2344b06194969cc2c496835729664c0..candidate`
  的全部结果/所需表面，不以本修正的小 diff 代替 Slice 重评。没有新的必需缺口则停止。

## Non-goals

新并行度/线程/Worker 数、容量压力或性能测试、10000 个 Task、第二队列、schema/迁移、
旧任务/跨版本升级、V1、扩大每次整理文件数、改 key/历史 pin、自动未知重放、第五恢复、
新页面/新 API、广泛统一验证器/过程工具、重做已通过 Task47.5 或 A 终审/关闭。

## Current whole-Slice reassessment

先核对实际交付再选本 Task；以下是规划判断，不是新候选接受或重复全量验收：

| 结果 | 当前判断 |
|---|---|
| RO-1 — Task 调度/执行 | 已有统一 Task/claim/slot；合法配置不能准入，A-P1-2 阻塞。 |
| RO-2 — 所有入口共用引擎 | 共享链路已存在；CLI 已证实受阻，其他实际消费者须验证高合法值。 |
| RO-3 — 同 Task 四类续作 | 前序已通过；本轮不新增恢复，修复验收保留等待重入/授权/独立结果。 |
| RO-4 — Job 退出/配置持久化 | fresh/同版本证据保留；AC-12 的支持配置意义因容量不一致未满足。旧任务/跨版本排除。 |
| RO-5 — 完整操作入口 | Settings 显示合法 Active 而普通整理失败，仍未完成。其他既有表面不扩展。 |
| RO-6 — 来源历史/新整理 | Task47.5 接受与 A 验证保留；本轮验收防止共享准入调整破坏其行为。 |

仅此兼容缺口支持本轮修正；没有证据要求重做四类恢复、历史或队列架构。

## Developer Completion Report

待实现。交接填写完整 checkpoint SHA、READY FOR B REVIEW、行为/文件/决策、受影响测试
实际命令与结果、失败/风险/剩余工作；full acceptance pending B，不自判 PASS。

## B Review Result

尚无本 Task 的实现候选，不能作产品 PASS。A-P1-2 独立复现确认，Slice 当前仍
FIX REQUIRED；Task47.6 已规划，下一步为 Developer 在此范围实现并交接，再由 B 独立
审完整 Task Base..Head、完成所需验收与六结果重评。旧 Task47.5 PASS 不作为此缺口的豁免。
