# Task 58.2 — 通用 CLI 与配置 schema 11 退出

Next Action: DEVELOPER FIXES REPEAT RESTORE AND FINISHES THE RETAINED NOTIFICATION BROWSER ENTRY

[Slice 58 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 58.2
Task Type: SLICE
Parent Slice: 58
Status: FIX REQUIRED
Task Base: 307eaaf8b006527a11fa2514de839a5528e6c202
Reviewed Head: 1be61cff3e508af171093b23c55836a341564fd5
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 58.2 CORRECTION SCOPE — A58-01
```

## B 复审 — FIX REQUIRED

**P1（RO-3 / AC-03）恢复到已腾空的旧路径后，原资源库打不开。** 第一次停机备份后，从
`mediaflow.sqlite3` 恢复到 `mediaflow-restored.sqlite3`，原管理员会话能打开 Files。后来将现用库
再次停机备份，归档第一次的原库，按发布指引用新 bootstrap 恢复到已腾空的 `mediaflow.sqlite3`。
主机命令报告 `RESTORED`，现用库和备份的校验值一致。只启动 API 后，原会话能读到同一 Active ID
和 digest，但就绪接口显示运行时未采用配置，Files 返回 503 `runtime_invalid`。源媒体仍保持原字节。

`2c05bc19` 引入的恢复记录用列表的末项表示当前数据库路径。恢复目标若已在历史中，写入时去重保留
了它第一次出现的位置，末项仍是上一次的路径。运行时因此拒绝了本次恢复使用的正确 bootstrap。
[恢复写入](mediaflow/infrastructure/sqlite_configuration_management.py#L835) ·
[运行时读取](mediaflow/infrastructure/runtime_configuration.py#L598) ·
[正式恢复步骤](docs/release.md#offline-restore-procedure)

**P1（RO-4）保留的通知浏览器脚本无法进入通知页。** 维护者构建 Web 后，运行现有的
`.venv/bin/python scripts/notifications_workspace_browser_proof.py --artifacts <证据目录>`。
脚本已能生成死信夹具，但打开根页后仍等待已经退役的 `API token` 登录字段，30 秒后退出。
现行根页使用管理员账号和会话。这是保留验收入口的切换遗漏。B 另用现行真实 Python 浏览器用例核对了
任务中心已取消状态和通知投递详情，另用正式 API 用例核对了死信原 ID 重排并再次投递。
[通知浏览器脚本](scripts/notifications_workspace_browser_proof.py#L264)

### 本轮返工开发指导

1. 修改 `SQLiteConfigurationRepository.record_deployment_location`。汇总已有历史和已发布快照的路径，
   从历史位置取出本次目的路径，再把它写为末项。使用现有的历史格式和加载入口。由正式离线恢复完成这次写入，
   保留各原快照的内容、ID、digest 和 Task pin。
2. 在 `tests/test_sqlite_restore.py` 的现有恢复旅程里增加第二次恢复。先从 A 恢复到 B 并读 Files，
   再停用 B，备份并校验 B，归档 A，用新 bootstrap 恢复到空出的 A。只启 API 后核对原会话、Active
   和 Files，比较现用库、备份和媒体的前后摘要。运行
   `PYTHONPATH=tests .venv/bin/python -m unittest test_sqlite_restore test_configuration_snapshot`。
3. 对照 `web/tests/e2e/operations-inventory.python.spec.ts`、`web/tests/e2e/notifications.spec.ts`
   和 `tests/test_v2_notification_operations.py` 核对脚本的现有断言。已有等效覆盖的重复脚本可以移除。
   把仍缺的合同断言接到现有测试的管理员会话和正式通知链路。以浏览器进入通知页、打开目标投递、确认重排，
   以及正式 API 核对原投递 ID 和接收端作为交接证据。

### 本轮验收

- B 核对完整 `307eaaf8..1be61cff` 和 `5b2e0de4..1be61cff`，工作区与暂存区起始干净。
  上一项通知阻塞已复验通过。正式 Files 受理后，取消生成恰好一条 `task.cancelled`，再次取消仍为一条，
  源文件保留。死信重排保留原 ID，Worker 再次投递。真实 Python 浏览器两项通过。
- 候选镜像通过空库和媒体挂载、重启故障、发布安全和 schema 11 拒绝。受控接收端收到签名 Webhook，
  旧投递在改地址后保持阻塞，恢复原地址后才继续投递。wheel 源码外冒烟通过。
- 首次停机恢复在源码和正式 Compose 通过。Compose 恢复前后，Rules 完整流程检查对同一离线样例给出
  同一整理计划。固定 Slice Base 的原库、账号、令牌和工作可读。恢复库发布新 Active 后，浏览器继续
  原 Task 的一个明确选择的条目，Worker 用原 pin 完成。已完成和不确定效果条目保留原结果。
- Python 全量 2328 项，2321 通过、7 跳过。治理、Ruff、编译、依赖、样例和禁用依赖检查通过。
  完整 Web 门禁留待修正候选。原验收包保留此前 4 个原生整理夹具失败和对应 Compose 验收结果。
- 第二次恢复和独立通知浏览器脚本均有失败日志。镜像和本轮日志在
  `.git/validation-evidence/1be61cff3e508af171093b23c55836a341564fd5/b-review/`。

## Developer 交接 — 取消通知与投递恢复使用已发布快照

```text
Candidate: 1be61cff
Scope: MediaFlowApi 的 Active Webhook 发布与通知中心投递恢复目标加载
```

- `_active_webhook_definitions` 和 `_notification_recovery_targets` 改用
  `ManagedConfigurationService.load_published_runtime`，保留 Active 完整性校验、启用及密钥过滤和现有投递目标摘要校验。
  任务中心取消在持久化终态后生成一条投递；死信详情与重排恢复按原投递 ID 工作，重排后的投递仍由原 Active Webhook 定义投递。
- 通知工作区证明脚本同步改用同一加载器；仓库内不再有 `_load_for_runtime` 调用。

本轮实际运行（仓库根目录）：

- 修复前复现 `PYTHONPATH=tests .venv/bin/python -m unittest test_notifications.TerminalTaskNotificationTests.test_queued_cancellation_publishes_one_event_without_media_effect`
  → 失败，0 条投递（`ValueError: not enough values to unpack (expected 1, got 0)`）。修复后同一用例通过：
  任务已取消、源媒体仍在、恰好一条 `task.cancelled` 投递；重复取消返回 409 且仍为一条。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_notifications test_v2_notification_operations`
  → 43 项通过；`test_notification_delivery_management` → 9 项通过。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` 无输出；改动文件
  `ruff format --check`、`ruff check`、`compileall` 通过。

剩余风险与待 B 验收：

- 本轮未启动 Web/Worker 或 Compose；任务中心取消通知的浏览器入口、通知中心死信恢复页面及 T4 全量仍由 B 复跑。
- 其余 Slice 58 验收边界不变。

## 上一轮 B 复审 — 取消通知（本轮已通过）

**P1，RO-1 / AC-01。** 管理员先启用订阅 `task.cancelled` 的 Webhook，再在 Files 提交整理，趁 Worker
尚未处理时从任务中心取消。正式 API 报告任务已取消，源文件仍在，通知却没有生成投递记录。Python 全量验收发现这个
问题，单独复跑了同一正式受理和取消入口，结果一致。`2c05bc19` 在切换到已发布快照加载器时移除了 `_load_for_runtime`，
但 `service_api.py` 的 `_active_webhook_definitions` 仍调用该方法。异常被转成空的 Webhook 列表，取消事件未入队。

### 本轮返工开发指导

1. 把 `_active_webhook_definitions` 和通知中心投递恢复使用的 `_notification_recovery_targets` 接到现有的
   `ManagedConfigurationService.load_published_runtime`，沿用 Active 完整性检查和原投递规则。
2. 运行现有通知测试 `PYTHONPATH=tests .venv/bin/python -m unittest test_notifications test_v2_notification_operations`。
   核对任务中心取消后恰好生成一条对应的通知投递，重复取消保持一条，源媒体无变更。用现有死信投递详情和恢复入口
   核对原投递 ID 与原接收端。

**上轮首次恢复验收通过。** 源码和正式 Compose 均可用原会话读取恢复库的 Active 和 Files。Compose 上恢复前后同一
离线 Rules 样例生成了同一计划。固定 Slice Base 的原账号、只读令牌、Task、Item、原请求、结果和审计可读。恢复后
保存新 Active，再由浏览器分析、确认原任务里的一项，Worker 按原 pin 完成该项。原库和备份校验值一致，已完成与
效果不确定条目保留原结果。候选镜像还通过空库和媒体挂载、重启、发布安全与 schema 11 拒绝检查。wheel 源码外冒烟通过。

Python 全量 2328 项，2319 通过、7 跳过、1 失败、1 错误。B 修正了 Task 的测试分工标题并复跑对应文档断言，已通过。
取消通知错误独立复现。其余 Slice 结果和验收边界见下表。证据位于
`.git/validation-evidence/f7de678a2e4e0384b89b8de991726ba756ce9f86/b-review/`。

## Developer 交接 — 恢复后的完整流程检查使用已发布快照

```text
Candidate: f7de678a
Scope: ConfigurationObjectService 的 complete-flow 运行时加载 + 恢复夹具中的正式 Rules API 回归
```

- `_load_runtime_for_analysis` 改用 `ManagedConfigurationService.load_published_runtime`。完整流程读取本次
  检查指向的当前 Active 时沿用已发布快照加载边界：接受恢复记录的原定位，始终按 bootstrap 实际打开的恢复库
  构造运行时；原快照 ID、digest、样例和只读响应不变。新候选发布仍走严格的
  `load_managed_runtime_configuration`。
- 现有 `RestoredDeploymentConsumptionTests` 在正式 host backup/restore 前后，以同一 Active、digest 和
  离线样例 `电影/Example.Movie.2024.mkv` 调用正式 Rules complete-flow API。两次均返回
  `complete_plan_ready`，响应除 `testedAt` 外一致；两次检查前后源媒体字节及目标目录/文件均未变化。
  原 Task pin、旧快照读取、错误 locator 拒绝和恢复后系统设置 Save 的既有断言保留。

本轮实际运行（仓库根目录）：

- `PYTHONPATH=tests .venv/bin/python -m unittest test_sqlite_restore test_v2_rules_object_analysis`
  → 102 项通过。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_snapshot test_sqlite_backup
  test_runtime_lease` → 50 项通过。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` 无输出；改动文件
  `ruff format --check`、`ruff check` 与 `compileall` 通过。

剩余风险与待 B 验收：

- 本轮未启动 Docker/Compose；API-only 恢复后的正式 Compose 旅程、两处媒体挂载和后台启用仍由 B 复跑。
- T4 全量、原 Task 的 Web/Worker 接续、媒体效果及 wheel/镜像门禁属于 B 的验收范围。

## B 复审 — FIX REQUIRED

**A58-01（P1，RO-3 / AC-03）仍未完成。** B 从原 Task Base 核对候选范围，并用候选镜像执行正式
Compose 停机、备份、校验、恢复和 API-only 启动。原库摘要一致，两处媒体挂载保留，原 Files 条目可读，
系统设置保存和四服务启动均通过。

B 通过「规则总览 → 完整流程检查」使用的正式 API，在原库以管理员身份选择资源库并提交离线样例
`电影/Example.Movie.2024.mkv`，生成了完整整理计划。恢复后只启动 API，用同一 Active ID、digest 和样例再运行，
得到「配置图无法加载，完整流程不可用」。`_load_runtime_for_analysis` 仍按新配置候选的规则比较原路径和恢复路径。
[配置加载入口](mediaflow/application/configuration_objects.py#L3577) · [规则旅程](docs/product-experience.md#object-scoped-tests-and-complete-flow-checks)

### 本轮返工开发指导

1. 让「完整流程检查」用现有已发布快照加载入口读取本次检查指向的 Active，按恢复部署路径构造运行时。
   保留这次检查的原快照 ID、digest、样例和只读结果。配置发布继续用已有的候选校验。
2. 在现有恢复夹具加入同一条正式 Rules API 回归。在恢复前后使用同一份配置和离线样例，两次均生成同一计划，
   均为零媒体变更。用 `PYTHONPATH=tests .venv/bin/python -m unittest test_sqlite_restore
   test_v2_rules_object_analysis` 运行受影响模块。交接时记录候选 SHA 和实际结果。

B 本轮两次 Compose 检查共约 67 秒。治理、差异检查、镜像内改动的 Python 文件与候选提交的摘要比对通过。
证据见 `.git/validation-evidence/2c05bc195c73fb59fba809474c52d04e7ba4d36e/b-review/`。
T4 全量和原任务 Web 接续验收待修正候选。RO-1、RO-2 和 RO-4 的既有证据见下表，RO-3 仍阻塞交回 A。

## A58-01 目标与首次复现

**FIX REQUIRED — A58-01（P1，RO-3 / AC-03）。** B 在原候选镜像用正式 Compose 和媒体 overlay
建立隔离实例。原资源库可打开。按发布指引停机、备份、校验并恢复到新文件，命令报告恢复成功，原库摘要一致。
仅启动恢复库 API 后，原会话可读到原 Active 记录，但 Files 返回 `503 configuration_unavailable`。
指引中的 Compose 命令丢掉了两处媒体挂载。带原 overlay 重启 API 后，两处挂载恢复，Files 仍返回
503（`runtime_invalid`）。原发布快照记录的是原库路径，共享加载器把它与恢复 bootstrap 的新路径直接比较。
[正式恢复入口](docs/release.md#offline-restore-procedure) · [共享加载器](mediaflow/infrastructure/runtime_configuration.py)

部署者应能按正式指引停机备份、校验并非覆盖恢复。恢复后先用原管理员登录，只开 API 核对 Active 已实际采用，
打开原资源库看到原文件，并在任务中心对照原任务、逐项结果和审计。核对备份时点之后的实际文件效果和待处理任务后，
用同一恢复配置及原挂载启用后台，按原任务入口继续符合条件的条目。若校验或发布拒绝，按现有提示保留原文件，
换用符合版本要求的备份或不存在的新目标。若恢复已发布但业务核对失败，保留原库与备份，按当前失败信号核对恢复
bootstrap 或原部署挂载，核对完成前保持后台停用。

## 本轮开发指导

1. **落实恢复库的部署定位。** 从 `host_operations.py` 的 `restore` 和 `SQLiteRestoreService` 跟到读取
   已发布快照的共用边界。由正式、显式的离线恢复建立新库的部署定位，复用现有租约、临时副本校验及非覆盖发布。
   恢复副本保留业务记录和原快照内容、ID、digest、Task pin。恢复 bootstrap 固定服务实际打开的 SQLite。
2. **让运行时和发布各走现有业务规则。** 从 `runtime_support.py`、`service_api.py` 和 `resident_entry.py`
   核对 Active 采用、就绪检查和历史 pin 消费，接通 Files 浏览、原任务分析与继续、Worker、Scheduler 和
   Notification Worker。原快照继续按发布状态、schema、完整性和 pin 读取。用 `configuration_snapshot.py`
   中的 `stage_successor_draft` 为常规 Save 候选带入当前部署定位，现有发布输入仍受 bootstrap 路径校验。
   在共用边界处理部署定位，沿用 `REQ-CONFIG-008` 对 Active 和历史 pin 的要求。
3. **修正操作指引。** 更新 `docs/release.md` 的源码及 Compose 步骤和相关部署指引。Compose 从停机到 API-only
   启动、后台启动沿用该部署的 Compose 文件组合和原媒体根。有挂载时给出含 `compose.media-mounts.yaml`
   的可执行命令，普通部署继续用基础 Compose。先核对认证后的管理就绪状态、Files 实际读取及原业务记录，
   再核对实际文件效果并启用后台。源码与 Compose 从已保存备份接续时沿用相同的 API-only 核对顺序。

## 验收

- [ ] 源码和正式 Compose 各自从已发布配置且有合法工作的隔离实例出发，按修正指引停机、备份、校验、恢复到
  不存在的新文件。先只启 API，用原管理员登录，核对 Active 的原 ID 和 digest、管理就绪状态、资源库 Files
  的真实条目及原任务、逐项结果和审计。Compose 媒体 overlay 的两处原挂载在启 API 及启后台时均有效。
- [ ] 对照备份时点后的媒体效果，再用恢复 bootstrap 启后台。在原 Task 显式选择符合条件的原条目，按现有页面
  分析、核对精确摘要并确认。保留原 Task、Item 和固定快照，其中旧 pin 能读取已被后续发布替换的快照。仅
  选定条目发生预期效果，已完成或效果不确定条目的历史结果和文件效果保持原样。
- [ ] 恢复发布、API 读取及分析阶段均为零媒体变更，原数据库及源备份各自的前后摘要一致。沿用缺少确认、目标已存在、
  目标旁路文件、租约冲突、损坏或不适用备份的真实入口与现有失败结果，核对原文件及目标状态。
- [ ] 恢复库的系统设置沿原权限及 checked publication 完成一次常规 Save。原 pin 可继续使用。原有错路径发布
  输入仍被拒绝，普通部署继续通过现有配置采用和快照完整性用例。

## 测试分工

### Developer — affected tests

在仓库根目录扩充现有恢复或配置集成用例，证明通过主机恢复入口切换数据库路径后，原发布快照可实际消费。复用
现有镜像和部署夹具沿正式命令核对带 overlay 的 API-only 启动及 Files 读取。运行受影响模块并记录结果及镜像标识。

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_sqlite_restore test_sqlite_backup test_runtime_lease \
  test_configuration_snapshot test_resident_services test_container_deployment
git diff --check
```

### B — acceptance and full regression

从原 Task Base 审查完整候选差异，先对照本轮真实 Compose 复现走修正后的源码与 Compose 指引，再做原 Task
的 Web/Worker 接续和文件效果核对。复用现有隔离夹具和正式命令。按 [T4 共享门禁](docs/development-workflow.md#6-test-levels)
覆盖精确候选，并在仓库根目录用该候选镜像执行现有 Compose 门禁。

```bash
.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image "$candidate_image"
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image "$candidate_image"
.venv/bin/python scripts/docker_release_security_smoke_test.py --image "$candidate_image"
```

同一候选用固定 Slice Base 建立并接续合法工作，按 AC-05 核对原任务、权限、pin 和逐项效果。按工作流核对可复用的
验收输入与相关失败，记录实际门禁结果。各测试轮次的测试耗时少于当轮总耗时的一半。

## Slice 结果重评

| 结果 | 当前结论 |
| --- | --- |
| RO-1 / AC-01 | 四服务、空库与挂载、整理、传输、定时工作和签名 Webhook 投递通过。正式 API 取消恰好生成一条通知。通知投递详情和任务中心取消状态在现行浏览器用例可见。 |
| RO-2 / AC-02 | 候选复验主机设置码、建号和登录。固定 Base 的原账号及只读令牌权限读回一致。首次设置、找回和撤销会话沿用 58.1 的验收证据。 |
| RO-3 / AC-03 | **未达到。** 首次恢复后的 Active、Files、Rules 和原任务续作通过。第二次恢复到已腾空的旧路径后，运行时无法采用原 Active，Files 读不到原资源库。 |
| RO-4 / AC-04、AC-05 | **未达到。** wheel、镜像旧入口移除、schema 11 拒绝以及固定 Base 的原库重开、恢复及显式续作通过。保留的通知浏览器脚本仍依赖旧登录表单。 |

本轮范围限于合同内的同版本停机恢复及实际继续使用。跨版本迁移、媒体备份、Web 备份管理和新的维护入口属于合同
延期范围。原 Task 的全部验收边界见 `32c269044ad14843d37f80f9b855e0b668062daa:TASK.md`。

B 核对了 `307eaaf8..1a238394` 和 `5b2e0de4..1a238394` 的范围及此前验收证据，确认候选至规划前 HEAD
`a75c6e9e50d09ff88339eb6a8e1917cf9182c5e1` 仅变更治理文档。规划开始时 `main` 工作区和暂存区干净，
仓库和 Git 可写。B 在镜像 `sha256:6aba5a154fcaaed5017067260c368b84fb9fbb8dbbb86514ce55da5402e724d8`
复现 A58-01。Compose 复跑耗时 44 秒。两次日志位于
`.git/validation-evidence/1a2383942aff3200f99c9c0560dec3e191ce611e/b-review-a58-01/`。
此前 Closure Packet 及其中记载的 4 个原生整理夹具失败保存在
`435a0b42904765820c85cc71cb904c14bf66f10e:TASK.md`。收到修正候选后，由 B 按本 Task 复验并更新 Closure Packet。
