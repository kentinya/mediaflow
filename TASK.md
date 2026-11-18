# Task55.6 — 现有 V2 数据继续使用，Task 只走五态

用户明确要求“激活Task”，据此将已提交的 Task55.6 草案激活为正式实施 Task。

Task55.5：**B PASS**。固定审查范围
`8a9d2460d0fb4df1afee0e157af3736f136a64c8..63d87814bc61f5da8b6300c70e4f5d3b62110d15`；
完整报告与证据索引见 `git show 2e460b71735ac0284e58928c884baac9d3f46009:TASK.md`。
依据已提交 [Slice55](SLICE.md) 的 RO-4 及 RO-2/3/5/6 中和 Task 状态、持久化直接相关的部分。
需求为 [V2-RETIRE-002–007/009–010](docs/v2-requirements.md#target--complete-v1-and-migration-residue-retirement-slice55-active)；
生命周期和测试分工遵循 [开发流程](docs/development-workflow.md)。

```text
Task ID: 55.6
Task Type: SLICE
Parent Slice: 55
Status: FIX REQUIRED
Task Base: 2e460b71735ac0284e58928c884baac9d3f46009
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: TASK55.6 IMPLEMENTATION AUTHORIZED
Next Action: DEVELOPER FIXES B55.6-05 AND B55.6-06 IN TASK55.6
```

规划起点：`/Users/songzhidong/mediaflow`，`main`，HEAD 为上述提交，工作区及暂存干净，
治理检查通过。Slice Base 仍为 `2b2e7c1824fa5681864455714d0f97b26555c7dc`，它是证明原有 V2
数据继续使用的起点；Task Base 是本单元的代码比较起点。草案和激活提交不重设任一 Base。
激活前 `main` 的 HEAD 为 `3991ddc9`，工作区干净，治理检查通过；Task Base 到草案
提交仅变更本文件。激活不改变目标、范围、验收和测试分工。

### Goal 与完整操作旅程

管理员已有 Active 配置，通过资源库 Files 提交整理。其中一个文件已完成，另一个等识别、
元数据、分类或冲突决定。安装候选并重启后，管理员从任务中心打开原 Task，看到原结果和仍
须处理的文件，不必重新配置或重发任务。保存决定后重新分析，核对精确摘要、明确确认，只让
Worker 处理选中的合法工作；也可用现有 Cancel 停止未执行部分。已完成或效果未知的文件不重做，
等待不显示成暂停，流程完成也不冒充每个文件成功。两种库的 Copy/Move/Delete 仍在来源页
显示各自结果。若部署指向原本不支持或损坏的库，启动说明读到了什么、原库未被改动，以及应
检查数据库路径或选择已验证的支持备份；已有的备份、校验和明确非覆盖恢复入口仍可用。

**现在的代码缺口：** `service_api.py` 仍分派 Task 的 `pause`/`resume` 并返回专用
`pause_retired`；`task_runtime.py`、`task_scheduling.py`、discovery 和普通文件 transfer
仍保留暂停路径，Web Task/run 读模型仍接收废弃的 aggregate 状态。CLI 的真实
`mediaflow upgrade --help` 仍列出 `check`、`rehearse`。两个 SQLite repository 启动时
仍混用新库建表、旧补列和历史回填；其中 scheduling 和首轮执行证据是当前必需结构，而
`manual_recovery_preparations` 旧 NOT NULL 列会阻挡当前 INSERT。这些不能按 helper 名称整段删除。

### 开发指导

1. **沿现行入口核对读写归属。** 从最小 bootstrap 启动 API/Worker/Scheduler/Notification，从
   Files、Task Center、Automation、现行 CLI 和数据库备份恢复入口追到读写结构。用 Slice Base
   的实际生产入口生成 V2 夹具，记下候选要保留的 ID、关系、原 digest、pins、请求和效果；
   用 Task Base 的派发与注册确定要退出的旧入口。已有库上的闲置旧表不等于正常 V2 数据不能用。
2. **一次收敛五态及其传输。** 删除 Task 和普通文件的暂停指令、状态、队列/transfer 转移、
   投影、CLI 字段及 Web 消费；注销实际注册的 Pause/resume 分派与审计分类，让旧请求走相同的
   未知路由。拆开 `PersistentTaskStatus` 与文件、附件、扫描/分析结果：删除旧 Task aggregate
   的 `paused`、`partial_success`，保留当前结果的部分成功、效果未知和缺 Result。移除旧
   `domain/tasks.py` 的 Task/ScanTask/阶段状态；`domain/scanner.py` 的现行扫描输出使用其
   实际需要的领域状态，不再代表另一套 Task 生命周期。保留安全取消、Worker claim/lease/fence、
   human/stability waiting、原 Task 的四类续作、Automation 统计与当前通知事实。
   `CANCEL_JOB/cancel_job` 和 `automation.maximumActiveJobs` 不改名。
3. **把新库建表与既有库读取分开。** 在 `sqlite_runtime.py` 和
   `sqlite_configuration_management.py` 直接定义完整当前表、列、索引和版本标记；包括 Task
   scheduling、首轮执行证据、当前来源证据、版本化摘要及 managed 发布权威。移除纯历史补列、
   回填、旧 lock owner 和旧恢复子 Task/remaining-scope 专属结构及读写。沿真实调用确认
   同 Task 摘要、请求、attempt 和结果仍完整；不清除来源归属证据或重算现有 checkpoint/pin。
   对真实 Base 形状只做采用当前行为所需的最小结构调整，例如保留能够原样读取和继续新建
   同 Task 摘要的结构；Base 已满足的列和索引不重写。必要调整置于同一事务，成功后才完成
   初始化；核对 API 与常驻服务同时打开时不会各自提交一半结构。在任何写入前分清新库、支持
   的 V2 库与原本不支持或畸形的库。现有 V2 库不为
   去掉闲置表而删除历史，不靠重设版本号或补授权来接续。
4. **退出旧工具并迁回当前断言。** 注销 `upgrade check/rehearse`，删除专属服务和只验证旧
   升级的脚本；同步 wheel smoke、release 验证、实际引用它们的 CI/部署说明。不改变
   `database backup/verify/restore`。把现有暂停、升级正向测试中仍有意义的断言接到当前
   取消、重启接管、来源变化和效果不重放旅程；只删除为已退役行为本身背书的断言。

### 验收

- [ ] **AC-1（Slice AC-02/06）：** 正常 Active 和合法身份下，已注册的旧 Pause/resume 返回
  普通 unknown route，旧 Upgrade 不在 CLI help 中且进入普通参数错误；无新请求、Task 或
  媒体效果。当前 Cancel、Task 继续与数据库备份入口仍可用。源码及安装包不含旧执行/升级工具。
- [ ] **AC-2（Slice AC-04/06/09/10）：** Files、due/Run once、同 Task 四类恢复及两种库
  普通操作使用五态；任务中心、来源页、API/CLI、日志、导出、通知和 Automation 记录/统计仍
  区分流程、等待原因、文件/附件结果与效果确定性。取消只在安全边界生效；已完成和未知效果
  不重放，权限、满额与 fence 等现有断言不变。
- [ ] **AC-3（Slice AC-05/08）：** 空目录的正式 bootstrap 初始化完整当前库，首次创建
  Draft 并激活后能够直接受理当前工作；新库无 Pause/旧恢复链等专属结构，不靠旧补列或回填
  才具备当前功能。同版本重开、四服务重启、在线备份/核验和显式非覆盖恢复通过。
- [ ] **AC-4（Slice AC-05/06/07）：** 候选打开 Slice Base 用真实入口形成的 V2 库，继续读取原
  Draft/Active、合法 Task 和结果/审计，并完成原待办或核对原未知请求；原 ID、关系、digest、
  pins 及已知/未知效果保持。至少覆盖人等、已受理未执行、已有成功或未知执行效果，以及
  有普通文件操作的库；不要求用户重配或重发。若存在实际结构调整，证明失败时原结构和记录
  不变；原本不支持、损坏或不支持的混合库在启动时报出真实情况，拒绝前后原文件、结构、行
  不变，且无业务执行。
- [ ] **AC-5（Slice AC-11/12 的本 Task 部分）：** 当前 wheel/源码外安装及候选 Docker 的
  启动、空库、重启和相关安全门禁通过。新库结构、实际注册、测试和发布清单相符。以当前
  入口验证保留行为，不用造一个没有注册的地址或只能经测试直接调用的方法证明产品问题。

### 测试

**Developer — 新增／修改与直接受影响测试。** 以下为已有入口，按实际修改的用例选取；
交接给出实际命令/结果，测试和构建累计时间须小于本轮用时的一半。

```sh
# 仓库根：五态、调度与 fence，配置初始化及备份恢复
.venv/bin/python -m unittest tests.test_task_flow_status tests.test_task_scheduling tests.test_task_scheduling_fencing
.venv/bin/python -m unittest tests.test_configuration_management tests.test_sqlite_backup tests.test_sqlite_restore
.venv/bin/python -m unittest tests.test_release_validation
git diff --check
# web/：Task/run 读模型、当前控制及真实浏览器五态/取消旅程
npm run test -- run src/entities/operations/task.test.ts src/entities/operations/run.test.ts src/features/operations/RunLifecycleControls.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

本轮修改的 Files、transfer、discovery、CLI/源库证明用例随改动运行；不把整套原生、全回归
或镜像矩阵转交 Developer。

**B — 独立验收与完整回归。** 对冻结候选审查完整 Task Base..Head，先用现行入口证明 AC-1、Base 数据继续使用
及拒绝坏库，再跑 [共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)。
原生覆盖 `task-flow.python.spec.ts`、`operations-inventory.python.spec.ts`、`direct-files.python.spec.ts`
与 `automation-run-once.python.spec.ts` 的相关旅程；使用各自隔离的实例及产物目录。用 Task55.5
的固定证据定位现成夹具，仅把它当作本候选复验起点。额外在已验证镜像上运行
`.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image <candidate-image>`、
`.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image <candidate-image>`，并核对
两种库普通文件生命周期的实际效果。记录 SHA、运行结果和稳定证据位置；累计测试/构建时间
小于该轮总耗时的 50%，未运行的门禁不记为通过。

### 非目标与剩余 Slice 结果

不重做 Task55.1–55.5 已接受的入口、配置与确认功能。RO-1 已验收；RO-2 的剩余暂停/旧链、
RO-3 的旧模型、RO-4 的当前库/五态以及 RO-5/6 中对应消费者与制品归本 Task。Run once/Copy/
Settings 等纯迁移 session、无生产调用的旧全局批量审核及其他非状态协议残留不混入本单元，
待本 Task PASS 后重新核实；全 Slice 最终门禁、CURRENT 协调与 A 终审仍未完成。保留 Git 历史，
不做通用迁移器、部署/推送、运行用户库或新增开发过程工具。

### 交接状态

Developer 以 READY FOR B REVIEW 提交了两个本地候选检查点：

- `e53bf3f9cd13b281475181ff747ad85d495d9839` —
  `feat(retirement): make five Task flow states the only lifecycle`
- `8adfe426` — `test(web): keep removed pause phases out of the current journeys`
  （最终产品候选）

Developer 交接截止 `12617ae9b1bdfaf90d53a1fe521e157c18e29233`；从
`8adfe426` 到交接提交只改本文件，产品代码和测试未变。
工作区在提交前除本 Task 文件外无其他改动；`config/alist.json` 未读取、未改动。
Slice55 仍为 ACTIVE，Slice、Roadmap、Progress 未改。

**本轮实现（按开发指导）**

1. 五态收敛：`PersistentTaskStatus`、`TaskQueueState`、`TaskControl`、
   `FilesTransferStatus`、`OperationsRunStatus`、`DiscoveryStatus`（仅暂停）、
   `TaskItemStatus`、`CheckpointStage` 中的 `paused` 成员删除；
   `PersistentTaskStatus.partial_success` 删除，流程完成一律 `completed`，文件级
   `partial`／效果未知／缺 Result 保持独立。Task/Item 的 `pause_requested`、Pause／resume
   控制、调度请求、transfer 暂停／重排、discovery 暂停／继续、projection、CLI 字段和 Web
   消费全部删除；源码中不再有 Pause 生产者或 reader。取消、claim/lease/fence、人等／稳定等、
   四类续作、Automation 统计与通知事实未改。
2. 入口：`/api/v1/tasks/{id}/pause|resume`、organize discovery 与 Run once 的暂停路由不再
   注册，落入通用 `not_found`（测试用真实 HTTP 入口验证）；`TaskCenter` 与 discovery／
   run-once／transfer 投影只发布 Cancel。
3. 升级工具：CLI `upgrade check|rehearse`、`upgrade_preflight.py`、
   `migration_rehearsal.py` 及专属测试删除；wheel smoke 与 release 验证清单同步。
   `mediaflow --help` 无 `upgrade`，`mediaflow upgrade check` 为 argparse 参数错误（exit 2）。
4. 领域拆分：删除 `domain/tasks.py`（旧 Task/ScanTask/阶段状态）；扫描输出改用
   `domain/scanner.py` 自己的 `ScanStatus`；文件／附件／发现结果保留各自的
   `partial_success`。
5. 持久化：新库一次性创建当前完整结构（含 Task 调度、首轮执行证据、来源列与当前索引）后
   才写版本标记；新库无 `pause_requested` 或暂停专属列，任务 INSERT 改为显式列名，不再依
   赖列顺序。既有库打开时仍执行当前最小结构收敛（`manual_recovery_preparations` 旧
   NOT NULL 列重建、`manual_executions.task_id` UNIQUE 收敛等），全部位于同一事务，版本
   标记最后写；有效记录、ID、pin、结果不重写。

**实际验证（命令与结果）**

- `.venv/bin/python -m unittest tests.test_task_flow_status tests.test_task_persistence
  tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_operations_task_center
  tests.test_manual_task_engine tests.test_media_discovery tests.test_processing_checkpoint
  tests.test_library_file_operation_history tests.test_media_library_direct_commands
  tests.test_direct_file_operations tests.test_organize_source_history
  tests.test_automation_authorized_execution_matrix tests.test_operations_run_detail_log_isolation`
  → 312 项通过（19.6 秒）。
- `.venv/bin/python -m unittest tests.test_direct_file_transfers` → 98 项通过（60 秒）；
  `.venv/bin/python -m unittest tests.test_media_library_transfers` → 26 项通过；
  `tests.test_configuration_management tests.test_sqlite_backup tests.test_sqlite_restore
  tests.test_release_validation` → 15 项通过；
  `tests.test_scanner tests.test_domain_models` → 25 项通过；
  `tests.test_governance` → 20 项通过（6.3 秒）。
- `.venv/bin/ruff check mediaflow tests scripts` 通过；`ruff format --check` 343 个文件已格式化；
  `.venv/bin/python -m compileall -q mediaflow tests scripts` 通过；
  `python3 scripts/check_governance.py` 通过；`git diff --check` 通过。
- `web/`：`npm run typecheck` 通过；`npm run lint` 通过；`npm run format:check` 通过；
  `npm run test -- run` → 104 个文件、1643 项通过；`npm run build` 通过（仅既有 chunk
  体积提示）。
- 真实入口反证：`.venv/bin/mediaflow --help` 不含 `upgrade`；`mediaflow upgrade check`
  exit 2（argparse）；`mediaflow` 的 `/api/v1/tasks/{id}/pause|resume` 与 discovery／
  run-once 暂停路由由 `tests.test_manual_task_engine`、`tests.test_media_library_transfers`
  经真实认证 API 验证为 404 `not_found`，无 Task、授权或 Storage 效果。

**剩余风险与未完成项（不记为通过）**

- 旧「remaining-scope 恢复准备」的 discovery/preview 专属列与 `scope_continuation.py`
  读写仍在：本轮把其来源条件从 `paused` 改为「未结束」，未删除整条旧链。按本 Task
  「移除旧恢复子 Task/remaining-scope 专属结构及读写」仍属未完成。
- `_initialize` 对既有库的纯历史补列／回填块仅删除了 `pause_requested` 与
  `file_locks.owner_token` 两处，其余旧补列块仍在；Base 形状已满足这些列，故不影响
  新库与 Base 库，但与本 Task 要求的「移除纯历史补列」尚有差距。
- B 的 T4 门禁（完整 Python／Web E2E、Docker 空库／重启、wheel 外安装与镜像身份、
  备份恢复实机链路）未由 Developer 运行，不能由本次结果替代。

### B 独立复核：FIX REQUIRED

固定比较范围：`2e460b71735ac0284e58928c884baac9d3f46009..8adfe42617b1a9bfd4776758dd3ab45c94f4e6bf`。
另核对了后续两个交接提交，止于 `12617ae9b1bdfaf90d53a1fe521e157c18e29233`，差异仅为
本 Task 文档。复核前 `main`、暂存和工作区干净。结论只针对 Task55.6，Base、范围和 T4 不变。

| 阻塞 | 复核事实及用户影响 |
|---|---|
| **B55.6-01（P1，AC-3/4）启动拒绝前改写旧库** | 用 `release/v1` 实际 CLI `logs list` 建隔离库，然后用现行最小 bootstrap 和有效本机端口启动 `mediaflow api serve`。API 报旧 Job schema 拒绝启动（退出 2），但原库 SHA-256 已变，配置版本从 10 改为 11，runtime 仍为 33。管理员回头拿到的已不是启动前原库。原因是 API 查 Active 时先打开了会建表、写标记的配置仓库，runtime 拒绝发生在后面。 |
| **B55.6-02（P1，AC-2/3）退役链和历史补写尚未移除** | SQLite 新库仍建立旧 remaining-scope discovery/preview 的专属列，Worker 和执行服务仍读取；候选把父 Task 的判定从「暂停」改成「没结束」，不是删除旧链。Task Center 当前四类问题走同 Task 的摘要及确认，复核没有把旧链冒充当前 Web 入口，也没有观察到新建旧子 Task。现行正常启动仍执行既有库旧补列／条件回填；新库仍调用来源列补列 helper，配置仓库仍创建发布权威后从旧 revision／audit 回填。当前有效来源证据、配置发布权威和同 Task 摘要本身不属于退役对象。 |
| **B55.6-03（P1，AC-2/5）验收入口未跟上五态** | 按已有 Playwright 入口实际执行「21 文件恢复分页」用例，初始化时访问已删除的 `PersistentTaskStatus.PARTIAL_SUCCESS`，测试收到 500，没有走到管理员查看分页的断言。Docker release security/restart 的现用夹具也仍引用已删除的枚举（源码核对，未运行镜像门禁）。旧 schema 通用 rehearsal、旧镜像升级 smoke 和历史 Task45.3 的迁移专用 proof 仍留在现行 `scripts/`。这不是已证实的生产分页故障。 |

### Developer 返工指导

1. **先修正式启动。** 沿最小 bootstrap 到 API、Worker、Scheduler、Notification 的现行入口，
   将共享 SQLite 文件的适用性判定放到首次建表、设置发布权威或登记服务之前。按已支持的
   V2 布局核对，不从“没有版本行”推断现有文件是空库。用 V1 自己的现有命令生成隔离库，
   经现行入口重现修复，比较启动前后文件摘要、版本和结构；启动错误说明数据库未改动，
   并指向核对路径或已验证的支持备份。备份核验／明确非覆盖恢复仍走原入口。
2. **按当前用例收敛数据库和续作。** 把空库所需结构（包括来源证据、调度、首轮执行证据、
   配置发布权威）放到直接建表路径。既有库只保留从真实 Slice Base 验证确实必需、能在
   同一事务完成的结构调整，删掉已废弃的逐列布局补写和历史权威推断。移除旧
   remaining-scope discovery/preview 的专属写入、读取、字段、索引、执行授权分支和对应旧
   Web 控件；删除 SQL／投影里把退役的 Task 流程状态转为当前状态的分支。发布时保留现有
   有效 V2 记录及原 pins，不清历史闲置列；保留当前 Task 四类恢复、文件级部分结果和来源
   归属。在现有测试中检查正常建库、真实 Base 库续作及必要结构调整失败后的原库。
3. **修掉断在旅程之前的夹具。** 更新现有 `operations_inventory_harness.py` 和当前 Docker
   security/restart 夹具：仍欠决定的 Task 是 running；已结束的流程按实际结果使用当前五态，
   文件失败、成功及不确定的证据保持独立。去掉只为 Pause 或已废弃升级存在的夹具／脚本，
   保留当前备份和重启验证。用上面的 21 文件用例走完原断言；不删除分页、RBAC、原 pin 或
   不重放断言。仅跑改动和直接受影响测试，交新候选及实际结果；整套 T4 仍由 B 执行。

```sh
# web/；先用 npm run build 构建当前候选
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'dated views and 21-file recovery pages'
```

**本轮实测。** `tests.test_manual_task_engine` 的三条认证 HTTP 停用与同 Task 续作，以及
`tests.test_sqlite_backup`、`tests.test_sqlite_restore` 合计 12 项通过。正式 CLI help 无
`upgrade`，旧命令走参数错误（退出 2）。从 Slice Base 的现有隔离 API/Worker 夹具重新生成
四个库：等识别决定、已有摘要、已受理未执行、已有成功结果均通过；原 Task、pin、请求核对
和结果保留，未选兄弟文件未动，C 仍为 C。首跑因未传 Base 源码到 `PYTHONPATH` 未加载夹具，
更正后上述四例通过。Web build 通过；现有真实 Python E2E 指定用例 1 失败，真实 V1 库
启动检查发现写入。日志及失败 trace：
`.git/validation-evidence/8adfe426/task55-6-b/`。本轮测试／构建累计远少于总用时一半；
确认以上阻塞后未启动完整 T4、wheel 或 Docker，不计为通过。未触碰用户运行库或媒体。

**Slice55 结果重评。** RO-1 维持此前接受，正式浏览器回归待新候选；RO-2 旧 Pause／resume
入口退出已抽查通过，但旧 remaining-scope 执行链未退役；RO-3 旧 Task／ScanTask 模型已删，
此前接受的配置键与权限名不变；RO-4 四种 Base 整理状态抽测通过，启动零改写、纯旧补写与
新库完整结构仍未通过；RO-5 同 Task 恢复抽测通过，旧链消费者待删，既定 session 清理不并入
本轮返工；RO-6 旧 CLI 退出，当前原生及制品门禁仍未完成。Slice 继续 ACTIVE，不新开 Task，
不改 Slice／Roadmap／Progress，不交 A 终审。


### Developer 返工交接：B55.6-01–03

候选产品检查点：`5174c308b8fac7a989addfd6beac6ccca386abcb`
（`fix(task55.6): reject unsupported databases before writes and retire the old recovery chain`）。
本交接提交只改本文件；Task Base 仍为 `2e460b71735ac0284e58928c884baac9d3f46009`。

**B55.6-01 — 启动前判定共享 SQLite 文件**

- 新增只读 `sqlite_applicability`：在任何建表、写 marker、登记 resident 或设置发布权威
  之前读取 schema marker 与表名。V1 Job schema（runtime < 58）、更新版本、畸形
  SQLite、未带 marker 的配置表/运行表均拒绝；新路径、配置-only 首设库、真实 Slice Base
  库继续。
- `SQLiteTaskRepository` 与 `SQLiteConfigurationRepository` 都在连接后、`_initialize`
  写入前调用同一判定；既有库路径不再先执行 `executescript` 再检查，而是先验证完整当前结构，
  只保留 Base 必需的 `manual_recovery_preparations` 最小重建。
- 配置仓库不再补 `base_active_revision_id`、`revision_sequence`、setup check 列，不再从旧
  revision/audit 推断发布权威；新库直接创建 `managed_configuration_authority` 和唯一
  revision sequence 索引，marker 最后写。真实 Base 库只读打开时配置库哈希不变。

**B55.6-02 — 退役 remaining-scope 旧链与历史补写**

- 删除 `scope_continuation.py`、`task_scope.py`、`task_source_schema.py` 以及 discovery /
  preview / execution 中的 `recovery_source_task_id`、`recovery_excluded_paths`、旧 eligibility
  分支、`find_open_recovery_discovery`、lineage 排除参数和对应 API/前端消费。
- 新库直接创建 task source occurrence 列与索引，不调用补列 helper；新 discovery/preview
  没有旧 remaining-scope 专属列。既有 Base 库保留其历史闲置列和 `recovery_continuations`
  行，不清历史；只重建阻挡当前 INSERT 的旧 `manual_recovery_preparations` 列。
- 运行投影删除 `paused`/`partial_success` Task flow 到当前状态的转换分支；历史值按
  `unknown`/不可用处理，不再发布为暂停或失败。
- 当前同 Task 四类恢复、`manual_recovery_preparations`、claim/lease/fence、文件级
  partial/未知效果/缺 Result、取消和两种库普通操作保持。

**B55.6-03 — 验收入口跟上五态**

- 21 文件夹具 Task 改为 `running`，mixed/batch 仍欠决定的 Task 改为 `running`，已结束的
  Docker security/restart 夹具改用 `completed`；文件失败/未知效果证据保持独立。
- 删除无产品入口的 paused continuation 夹具、`seed-continuation`/`continuation-state` 端点
  及对应 Playwright 用例；remaining-scope 退役入口仍用真实 Task/API 证明为普通 404。
- 删除旧 `schema_upgrade_rehearsal.py`、`docker_upgrade_recovery_smoke_test.py`、
  `task_base_migration_proof.py`，同步 `docs/release.md`。

**实际验证（命令与结果）**

- `.venv/bin/python -m unittest tests.test_task_persistence tests.test_task_flow_status
  tests.test_task_scheduling tests.test_task_scheduling_fencing
  tests.test_configuration_management tests.test_sqlite_backup tests.test_sqlite_restore
  tests.test_release_validation tests.test_configuration_status` → 111 项通过。
- `.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_media_discovery
  tests.test_processing_checkpoint tests.test_operations_task_center
  tests.test_task_source_ownership_race tests.test_organize_source_history` → 116 项通过。
- `.venv/bin/python -m unittest tests.test_direct_file_transfers
  tests.test_media_library_transfers tests.test_media_library_direct_commands
  tests.test_direct_file_operations tests.test_library_file_operation_history
  tests.test_scanner tests.test_domain_models` → 255 项通过（68 秒）。
- `.venv/bin/python -m unittest tests.test_governance` → 20 项通过；
  `.venv/bin/python -m unittest tests.test_configuration_status.RetiredDatabaseStartupTests`
  → 1 项通过。
- 真实入口反证：用 release/v1 形态的隔离库（configuration 10、runtime 33、jobs 表）启动
  `.venv/bin/mediaflow --config ... api serve --host 127.0.0.1 --port 45678`，exit 2，
  提示“retired V1 Job schema…file was not modified”，启动前后 SHA-256 一致。
- 真实 Base 库（`task55-4-b/slice-base-v2-work`）打开后读到原 Active、Task/Item/Result；
  配置-only 打开前后 SHA-256 一致。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check` 通过；
  `npm run test -- run` → 104 个文件、1642 项通过；`npm run build` 通过。
- `web/` 真实 Python E2E：
  `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts --grep 'dated views and 21-file recovery pages|retired remaining-scope|retired batch continuation'`
  → 3 项通过。
- `.venv/bin/ruff check mediaflow tests scripts` 通过；`ruff format --check` 337 个文件已格式化；
  `python -m compileall -q mediaflow tests scripts`、`python3 scripts/check_governance.py`、
  `git diff --check` 通过。

**剩余风险与未完成项（不记为通过）**

- 现有 Base 库仍保留历史闲置的 `recovery_source_task_id`、`recovery_excluded_paths_json`、
  `pause_requested` 等列和 `recovery_continuations` 行；本轮按“不为删除残留而清历史”保留，
  新库均不再创建。
- 浏览器单测中仍保留少量 direct-file/历史状态文案映射（如 `paused` 标签）；本轮未扩大为
  全站文案清理。
- B 的完整 T4（全量 Python、全部原生 E2E、Docker 空库/重启、wheel 外安装、镜像身份、
  备份恢复实机链路）未由 Developer 运行，不能由本次结果替代。

### B 返工复核 — FIX REQUIRED

独立审查完整范围 `2e460b71735ac0284e58928c884baac9d3f46009..5174c308b8fac7a989addfd6beac6ccca386abcb`。
`f4e20cc8922cb30e2a9ed39a0f4e84f6d939dd04` 只改 Task 交接文档。本轮起点为该提交，`main`
暂存和工作区干净，治理检查通过。交接原先写错候选完整 SHA，已用 Git 核对并更正。

| 阻塞 | 实际操作及原因 |
|---|---|
| **B55.6-01（P1，AC-3/4）空库并发首启会中断** | 管理员准备空数据目录，用最小 bootstrap 同时启动默认部署的 API、Worker、Scheduler 和 Notification Worker。四次隔离启动中一次 API 因配置版本记录重复写入退出，通知服务则把另一个进程已建表但尚未提交版本的库判为不支持并退出。管理员此时无法打开 API 完成首次设置。`5174c308`（2026-11-18）把是否新库的判定、建表和版本提交分开，进程因此看见中间状态。真实 V1 库四服务拒绝前后校验和、版本、结构一致，上轮 V1 改写已修复。 |
| **B55.6-02（P1，AC-2）Automation 统计仍单独读取退役的 Task 流程值** | 管理员打开 Automation，月度统计的现行 API 仍从 Task 表筛选 `partial_success`，用 `monthToDatePartial` 发布该计数。这个筛选来自此前的历史状态处理，本轮修改后仍在。旧 remaining-scope 模块、新库专属列和主要读写已退出，当前同 Task 恢复通过抽查。此项来自现有统计入口的源码核对。 |
| **B55.6-03（P1，AC-2/5）当前原生验收仍依赖已经移除的 Pause 响应** | 在资源库选择目录并点击移动，Worker 移完三个子项后，管理员取消并打开当前页操作状态。浏览器确认已取消并逐项显示三个已移动的子项。现有用例随后访问以前实际注册的 resume 路径，候选正确返回普通 404，测试仍按 2026-10-31 引入的旧约定要求 `409 pause_retired`，因此跳过了后续 Worker 再跑和剩余三个文件未动的验证。MediaLibrary 假服务和两个 Files discovery proof 脚本仍主动构造或要求暂停，来自源码核对。上一轮失败的 21 文件分页已经通过。 |

#### Developer 返工指导

1. 先收敛 SQLite 首次初始化。让同路径的进程在 SQLite 写事务内判断已提交的结构，再在
   同一事务完成需要创建的表、索引和版本记录。新进程等前一笔提交后按已有库继续打开。
   现有 V2 的最小结构调整和数据保留仍走当前路径，V1 或不支持的库在写入前拒绝。用现有
   四服务空库入口复现首次并发启动，核对各服务能到达就绪，随后完成首次 Draft 与激活。
2. 从现行 Automation 月度统计去掉退役 Task 状态的专属筛选和响应字段，清理相应消费者。
   保留 completed、failed、cancelled、运行中和不可用事实，文件级部分结果继续由现有
   文件结果路径展示。沿现有 `task-flow.python.spec.ts` 核对管理员看到的统计和文件效果。
3. 让资源库原生用例核对普通 `404 not_found`，并走完原有的取消证据、Worker 再跑和
   文件未重放断言。把假服务 MediaLibrary 的暂停夹具改接当前操作，退出两个 discovery
   proof 的旧 Pause/Continue 路径，保留仍适用的当前旅程断言。被移除的暂停测试中涉及
   未知效果、Worker 换班和取消的独立断言接回现有相关案例。只运行改动与直接受影响的测试。

```sh
# web/，先用 npm run build 构建候选
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep "cancelled folder Move's known effects locally"
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

**独立实测。** Web 构建通过；真实 Task 五态用例 3 项、21 文件分页及两条旧恢复入口用例
3 项、认证停用／同 Task 续作及 SQLite 备份恢复单测 11 项通过。用 `release/v1 jobs list`
建库验证四个当前服务均以退出码 2 拒绝，数据库未改动。用 Slice Base 在同一隔离路径发布
有效 V2 Active、经 Files 接口受理后，候选 CLI 成功读取原 Active 和待执行 Task，核对了
原 digest 与 pin。最初复制夹具时更改了固定路径，另一次 Base 夹具自带旧调度配置；两次
均在改用原路径和发布时使用有效 V2 输入后重新验证。目录移动首跑采用了通用浏览器配置，
更正为 Files 专用配置后复现上表断言失败。证据在
`.git/validation-evidence/5174c308b8fac7a989addfd6beac6ccca386abcb/task55-6-b/`。
测试和构建累计约 25 秒，少于本轮一半。完整 T4、wheel 和 Docker 门禁待修正候选。

**Slice55 结果重评。** RO-1 保留此前接受的 Web 入口结果。RO-2 本轮验证普通未知路由，
旧 remaining-scope 执行路径已清理，Cancel 与同 Task 续作通过抽查。RO-3 此前接受的配置
和权限契约保留，旧 Task／ScanTask 删除。RO-4 已通过 V1 零改写、局部 V2 重开及五态原生
抽查，空库并发首启仍阻塞。RO-5 当前同 Task 续作及 21 文件恢复通过，本 Task 仍有旧状态
统计，既定 session 清理仍待完成。RO-6 旧升级工具已退出，当前验收仍有上述遗漏，最终门禁
待执行。Slice55 继续 ACTIVE，返工留在 Task55.6。


### Developer 返工交接：B55.6-01–03

候选产品检查点：`38a0a6d2f161159a356b12578ce3b980c17b74d1`
（`fix(task55.6): initialize SQLite atomically and align current acceptance`）。
本交接提交只改本文件；Task Base 仍为 `2e460b71735ac0284e58928c884baac9d3f46009`。
工作区提交前除本文件外无其他改动；`config/alist.json` 未读取、未改动。

**B55.6-01 — 首次初始化收敛为一个写事务**

- 两个仓库都在 `sqlite3.connect` 后先执行 `BEGIN IMMEDIATE`，在本连接、本事务内重新读取
  marker/表名后再决定“新库建表”还是“既有库验证”。表、索引、内部键和版本 marker 在同一
  事务提交；失败整体回滚。第二个进程等待首笔提交后按既有库继续，不会再看到“有表无 marker”
  的中间状态或重复写入版本记录。
- DDL 由 `sqlite_initialization.execute_script` 逐条执行，避免 `executescript` 隐式提交；
  新库与既有库的当前结构检查、V1/更新/畸形库拒绝都仍在任何业务写入前完成。真实 V1 库启动
  拒绝前后 SHA-256、版本和结构不变；配置-only 首设库、真实 Slice Base 库继续。
- 新增 `ConcurrentFirstInitializationTests`：四个线程以两种仓库顺序同时打开同一空路径，
  断言仅有一组 11/58 marker 且随后两个仓库均可重开。

**B55.6-02 — Automation 月度统计退出 partial 流程值**

- 从 `automation_run_metrics` 删除 `linked_task_status = 'partial_success'` 的专属筛选与
  `currentPartial` 返回字段；非五态历史值统一进入既有 `unavailable` 事实，不再作为独立
  partial 桶。保留 completed/failed/cancelled、运行中、不可用、文件级部分结果和效果未知。
- `/api/v1/operations/automation/metrics` 不再发布 `monthToDatePartial`；Web 读模型、测试
  fixture 与 fake 响应同步清理。Python 指标用例增加“响应不含 `monthToDatePartial`”断言。

**B55.6-03 — 当前验收入口跟上取消**

- 真实 Python `direct-files` 目录移动用例不再要求 `409 pause_retired`；对已取消 Task 的旧
  resume 地址断言普通 `404 not_found`，然后继续执行 Worker 再跑、3 个已移动子项保留、
  3 个剩余文件未重放的原断言。
- fake server 的 MediaLibrary 暂停夹具改为当前取消夹具（`transferCancel`），不再构造
  PAUSED 传输；Task 控制只注册 cancel，discovery 控制不再匹配 pause/resume，未注册 API
  路由统一返回 JSON `not_found`。两个 MediaLibrary 用例改为验证取消传输的普通 404、durable
  CANCELLED 和退役深链不触发 API。
- 两个 Files discovery proof 脚本退出 pause/continue 路径：控制/预算范围直接由 Worker 走完，
  仍断言 101 visited/100 sources/primary_limit、finalize 拒绝、取消终态、Worker 不推进已
  取消记录和原冻结/前缀不重放；矩阵不再发布 paused/resumed。

**实际验证（命令与结果）**

- `.venv/bin/python -m unittest tests.test_configuration_management tests.test_configuration_status
  tests.test_task_persistence tests.test_task_scheduling tests.test_task_scheduling_fencing`
  → 79 项通过；其中新增并发首启用例通过。
- `.venv/bin/python -m unittest tests.test_v2_automation_operations tests.test_organize_source_history`
  → 42 项通过；`.venv/bin/python -m unittest tests.test_v2_automation_run_once` → 39 项通过
  （先发现旧 fixture 仍带 `pause_requested` 导致 1 项失败，去掉退役字段后复跑通过）。
- `.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_media_library_transfers`
  → 66 项通过；`tests.test_operations_task_center tests.test_media_discovery
  tests.test_processing_checkpoint` → 40 项通过；
  `tests.test_release_validation tests.test_sqlite_backup tests.test_sqlite_restore`
  → 11 项通过。
- 真实四服务空库入口（最小 bootstrap，API/Worker/Scheduler/Notification 同时启动）连续三次：
  无异常退出；`/health` 200，management readiness `managementReady=true`/`setupRequired=true`，
  首次 Draft 校验并激活成功；marker 为 11/58。脚本与日志在
  `.git/validation-evidence/38a0a6d2f161159a356b12578ce3b980c17b74d1/task55-6-dev/`。
- 真实 Slice Base 夹具临时副本由两个仓库打开后仍读到原 completed Task，打开前后 SHA-256
  一致。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过；
  自动化/API 单测 30 项通过；真实 Python `direct-files` 指定移动用例 1 项、`task-flow` 3 项、
  `medialib-transfers` 9 项通过；fake-server 的 operations/task-center-layout/automation/
  deep-link 四个既有套件 38 项通过。
- `.venv/bin/ruff check mediaflow tests scripts`、`ruff format --check`（338 文件）、
  `compileall`、`python3 scripts/check_governance.py`、`git diff --check` 通过。
- 测试和构建累计约 11 分钟（其中四个视觉/布局套件 8.9 分钟），少于本轮耗时 30%。

**剩余风险与未完成项（不记为通过）**

- B 的完整 T4（全量 Python、全部原生 E2E、wheel 外安装、Docker 空库/重启/安全镜像、备份
  恢复实机链路）未由 Developer 运行，不能由本次结果替代。

- 两个 discovery proof 脚本的 pause/continue 路径已改为当前完成/取消旅程，但本轮未实际执行
  这两个浏览器 proof 或 Docker 变体；B 应在相应门禁或源码复核中确认。
- fake server 的 Task Center 历史夹具中仍有 `task-006/task-007` paused 行及若干 paused 文案
  映射，Web 单测也保留若干可选 `pauseRequested` 字段；它们不在本次三个阻塞的当前入口断言中，
  未扩大为全站夹具清理。
- 任何浏览器/原生门禁若再发现旧响应约定，应回到本 Task 修正，而不是删除现有断言。

### B 返工复核 — FIX REQUIRED（候选 `38a0a6d2`）

独立审查完整范围 `2e460b71735ac0284e58928c884baac9d3f46009..38a0a6d2f161159a356b12578ce3b980c17b74d1`。
交接 `fe8755e6cb5e7a80211b5f595937df4811cd40f4` 仅更新本 Task。复核起点为该提交，
`main` 工作区和暂存干净，治理检查通过。

| 阻塞 | 实际操作与原因 |
|---|---|
| **B55.6-01（P1，AC-4）API 拒绝其他应用的 SQLite 文件前已改写该文件** | 管理员设置 bootstrap 时误选另一个 SQLite 文件，再用 `mediaflow api serve` 启动。B 用 `sqlite3` 创建一份只含笔记的隔离库实测，API 退出 2，提示文件未改动，但前后 SHA-256 不同，已新增管理配置、发布权威及版本表，原笔记记录仍在。共享检查对无 MediaFlow 标记的普通 SQLite 没有作出完整判断，API 读取 Active 时配置仓库先提交建表；runtime 随后才拒绝。`5174c308`（2026-11-18）引入了这一先写后拒绝的路径，`38a0a6d2` 解决了并发首启，仍保留这条路径。 |
| **B55.6-03（P1，AC-5）现有目录整理 proof 仍绑定退役的 Job 表** | 运行已修改的 `scripts/files_organize_discovery_browser_proof.py`，它通过当前 API 启动和配置激活，准备验证管理员选择目录、观察扫描并明确确认。首轮本机文件系统拒绝原长路径夹具；仅将隔离夹具缩至 706 字符，保留超过 512 的条件后，从同一 proof 入口运行。脚本在读取基线时查询已退役的 `automation_jobs`，SQLite 报表不存在，未进入目录旅程。该查询引入于 `657e137d`（2026-10-09）。资源库移动取消的浏览器用例已走完并通过，现有报告没有证实目录整理产品操作失败。 |

#### Developer 返工指导

1. 让共享库适用性判断在 API 第一次打开配置仓库时就能识别其他应用的 SQLite 库。沿现有
   共用判定把零表空库、现有正常 V2、配置-only 首设库和不支持的布局分清，并在任一仓库
   首次建表或写标记前完成判定。保留本轮建表、索引、版本同事务提交。用最小 bootstrap
   指向正常创建的非 MediaFlow SQLite，从正式 `api serve` 验证退出原因及文件、表和行
   均未改变，再确认原四服务空库与首个 Draft 激活通过。
2. 让目录整理的验收使用现行记录证明实际效果。清理 proof 对旧 Job、旧配置审计和旧 Task
   流程状态的断言。保留有界扫描、失败原因、取消、零变更预览和明确确认后的文件效果。
   现有原生或集成用例已能覆盖的断言复用现有入口，收掉重复的旧 proof。用保留下来的
   现行入口走完整旅程，并交改动与直接受影响的测试结果。

**本轮通过。** 四服务同时打开空库，HTTP health 与 readiness 正常，首个 Draft 校验并激活，
只写入一组 configuration 11 / runtime 58 标记。B55.6-02 的旧指标字段已从查询、API 和
Web 读模型退出，真实 Task flow 浏览器用例通过。资源库目录移动在取消后逐项显示三个已移动
文件，旧地址 `404 not_found`，Worker 再跑后三个剩余文件仍在。Web build、5 项原生浏览器
用例、10 项 SQLite／V1 拒绝／备份恢复测试及 19 项 Automation 测试通过。测试和构建累计
约 31 秒，少于本轮一半。证据在
`.git/validation-evidence/38a0a6d2f161159a356b12578ce3b980c17b74d1/task55-6-b/`。
完整 T4、wheel 和 Docker 门禁待修正候选。

**Slice55 结果重评。** RO-1 的既有 Web 入口结果保留。RO-2 旧恢复路径退出，当前移动取消
与同 Task 的续作路径已抽查。RO-3 既有正式配置和权限契约保留，五态统计不读旧流程值。
RO-4 空库并发首启通过，其他 SQLite 误配的零改写仍阻塞。RO-5 21 文件分页、当前流程
与逐项效果通过，既定 session 清理待完成。RO-6 对当前目录整理的 proof 还有上述欠项，
最终门禁待执行。Slice55 继续 ACTIVE，返工留在 Task55.6。


### Developer 返工交接：B55.6-01、B55.6-03

候选产品检查点：`dd0cd20f958b78da68a905551a35285abee797ca`
（`fix(task55.6): reject foreign SQLite stores and retire the stale discovery proof`）。
本交接提交只改本文件；Task Base 仍为 `2e460b71735ac0284e58928c884baac9d3f46009`。
工作区提交前除本文件外无其他改动；`config/alist.json` 未读取、未改动。

**B55.6-01 — 在首次写入前识别其他应用的 SQLite 库**

- `sqlite_applicability.evaluate_database_applicability` 在既有 V1/更新/配置表检查之后
  增加统一判定：既无 runtime 也无 configuration marker、但任一张表存在的文件不是空库，
  直接 `DatabaseApplicabilityError`；错误说明仍为“文件未改动，检查数据库路径或恢复已验证
  的支持备份”。零表 SQLite、正常当前 V2、配置-only 首设库和运行库-only 库继续。
- 配置仓库与运行仓库仍各自在 `BEGIN IMMEDIATE` 内重读 marker，建表、索引、内部键和版本
  marker 同事务提交；判定失败发生在任何 DDL 之前。第二进程等待首笔提交后按既有库打开。
- 新增两条现行入口测试：
  `RetiredDatabaseStartupTests.test_api_serve_rejects_another_application_database_without_modifying_it`
  用 `sqlite3` 建立只含 `notes` 表和一行笔记的隔离库，经正式
  `mediaflow api serve` 启动，断言退出 2、提示表和行未变，启动前后 SHA-256 一致，表集合
  仍只有 `notes`、笔记行原样保留；
  `test_zero_table_sqlite_file_is_initialized_as_a_current_store` 用带 header 的零表
  SQLite 经两个仓库打开，断言写入唯一一组 configuration 11 / runtime 58 marker。

**B55.6-03 — 目录整理验收改用当前现行入口**

- 删除重复且已过时的 `scripts/files_organize_discovery_browser_proof.py` 及其
  `scripts/docker_files_organize_discovery_browser_proof.py` 包装：它们仍查询退役
  `automation_jobs`、旧 `managed_configuration_audit`，并按旧 Task/页面形态断言；同旅程
  已由现行真实 Python 浏览器入口 `web/tests/e2e/manual-organize-dialog.python.spec.ts`
  覆盖，有界扫描/预算/深度/取消断言由 `tests.test_media_discovery` 等现行测试承载。
- 运行库投影删除 discovery `partial_success` 作为 Operations run 流程状态的旧分支：有界
  discovery 的完成流程按当前五态发布 `completed`，其自身记录继续保留 `partial_success`、
  incomplete reason 和 finding；`original_status` 和统计集合同步退出该旧值。
  新增 `test_operations_task_center...test_discovery_partial_result_is_a_completed_run_flow`，
  用真实 repository 写入一个 definition-origin、budget-limited 的 discovery，断言 run
  为 `completed`、discovery 自身仍为 `partial_success`，status counts 不含旧值。

**实际验证（命令与结果）**

- `.venv/bin/python -m unittest tests.test_configuration_status` → 9 项通过。
- `.venv/bin/python -m unittest tests.test_operations_task_center` → 27 项通过。
- `.venv/bin/python -m unittest tests.test_resident_services tests.test_management_setup`
  → 45 项通过；`.venv/bin/python -m unittest tests.test_media_discovery
  tests.test_media_discovery_provider_manifest tests.test_v2_automation_run_once` → 45 项通过。
- `.venv/bin/python -m unittest tests.test_configuration_management tests.test_sqlite_backup
  tests.test_sqlite_restore tests.test_release_validation` → 15 项通过；
  `tests.test_operations_run_progress_defaults tests.test_operations_run_detail_plan_evidence
  tests.test_operations_run_detail_log_isolation tests.test_task_persistence
  tests.test_task_flow_status` → 61 项通过。
- `web/`：`npm run build` 通过（仅既有 chunk 体积提示）；`npm run typecheck` 通过；
  真实 Python 浏览器
  `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/manual-organize-dialog.python.spec.ts --grep 'ten per-file candidate decisions'`
  → 1 项通过（10.5 秒），覆盖目录选择→准备→逐项决定→精确 10 项确认→Task 中心。
- `.venv/bin/ruff check mediaflow tests scripts`、`ruff format --check`（336 文件）、
  `python -m compileall -q mediaflow tests scripts`、`python3 scripts/check_governance.py`、
  `git diff --check` 通过。
- 最终测试/构建累计约 30 秒；旧 proof 探路运行合计约 100 秒后确认其断言已过时并删除，
  合计仍少于本轮约 30 分钟的 30%。

**剩余风险与未完成项（不记为通过）**

- 本轮未重跑四服务同时空库启动和首个 Draft 激活；共享判定未改空路径与事务路径，B 应在
  修正候选上复验该门禁。
- 删除旧目录整理 proof 后，其原有预算、深度、取消、长路径浏览器断言由现有模块测试和
  `manual-organize-dialog` 等入口承载；本轮只运行了后者指定 1 项，没有重跑其全部用例，
  也没有运行 Docker 包装。
- B 的完整 T4（全量 Python、全部原生 E2E、Docker 空库/重启/安全镜像、wheel 外安装、
  备份恢复实机链路）未由 Developer 运行，不能由本次结果替代。

### B 返工复核 — FIX REQUIRED（候选 `dd0cd20f`）

独立审查完整范围 `2e460b71735ac0284e58928c884baac9d3f46009..dd0cd20f958b78da68a905551a35285abee797ca`。
交接 `7f9e8a35e82231dd8acc2e0ab07280b5c7051c05` 仅更新本 Task。复核起点为该提交，
`main` 工作区和暂存干净，治理检查通过。

**上轮阻塞已通过复验。** 最小 bootstrap 误指其他应用的 SQLite 时，正式 `api serve` 退出 2，
前后文件校验和、结构与笔记行一致。四服务并发空库首启的 health、readiness 和首个 Draft
校验激活通过，只生成一组 11/58 标记。旧目录整理脚本已退出，现行 `manual-organize-dialog`
真实浏览器 8 项全通过，覆盖目录选择、逐项决策、精确确认、Task Center 交接和丢响应核对。

**B55.6-04（P1，AC-3/4）启动前凭据检查被数据库拒绝截断。** 管理员配置好当前 bootstrap
和令牌，准备启动服务，先运行 `mediaflow api credentials check` 核对环境变量。命令在读取
凭据设置之前走了 `_configuration()`，打开并可能初始化配置仓库。对比同一正式入口，Task
Base 和候选在空路径上都报告凭据已设置，同时创建数据库。将 bootstrap 指向另一应用的隔离
SQLite 后，Task Base 报告凭据状态同时改写文件，候选保持文件不变，但退出 2，仅报告
数据库不支持。Task55.6 从 `5174c308`（2026-11-18）引入共享适用性拒绝，`dd0cd20f` 把
拒绝扩展到其他应用的库；原有的 `credentials check` 配置解析顺序使拒绝挡住了这一诊断入口。
全量 Python 首轮两条既有凭据用例失败，它们沿用示例的相对数据库位置。上述绝对隔离路径
实测复现了候选的实际行为，避免把环境错误用作结论。

#### Developer 返工指导

在 `api credentials check` 的正常解析分支直接使用现有最小部署身份解析和凭据状态输出，
让管理员能在首次启动及修正数据库路径之前读取环境变量的 SET／UNSET。保留现有参数校验、
退出码、禁用身份状态及脱敏输出，现行 `api serve` 继续在启动前拒绝不适用的库。把既有凭据
用例改用明确的隔离数据库路径，核对已设置、缺失和旧 `api.tokenEnv` 的结果，并断言凭据检查
既不新建数据库，也不改写已存在的文件。Developer 跑现有凭据和直接相关启动测试，B 负责 T4。

**实际测试与证据。** Web build 通过，目录整理浏览器 8 项通过，四服务首启与正式 CLI
隔离复验如上。完整 Python 首轮出现失败，定位凭据问题后中止（退出 130），不记为完整结果。
测试和构建累计约 138 秒，少于本轮一半。原始日志见
`.git/validation-evidence/dd0cd20f958b78da68a905551a35285abee797ca/task55-6-b/`。
完整 T4、wheel 和 Docker 仍待验收。

**Slice55 结果重评。** RO-1 的既有 Web 入口结果保留。RO-2 当前目录整理及同 Task 确认
通过原生复验。RO-3 正式配置与权限名保留，凭据诊断入口仍阻塞。RO-4 上轮 SQLite 误配
的零改写和空库并发首启通过。RO-5 当前确认、丢响应核对和返回路径通过，既定 session 清理
仍待完成。RO-6 当前目录验收已接到现行入口，完整回归与制品门禁未完成。Slice55 继续
ACTIVE，返工留在 Task55.6。

### Developer 返工交接：B55.6-04

候选产品检查点：`ff008989482ba3c649a9456094e2f80b17ac213b`
（`fix(task55.6): read credentials before opening the database`）。
本交接提交只改本文件；Task Base 仍为 `2e460b71735ac0284e58928c884baac9d3f46009`。
提交前工作区除实现与测试两文件外无其他改动；`config/alist.json` 未读取、未改动。

**B55.6-04 — 凭据检查先于数据库打开**

- `api credentials check` 现在与常驻服务一样，从 `_configuration_document` 读取部署 bootstrap，
  再经现有 `load_management_bootstrap` 解析 `persistence.databasePath` 和 `api.principals`，
  直接调用同一 `api_credential_statuses()` 与 `render_api_credentials()`。
- 该分支在 `_configuration()`、`SQLiteConfigurationRepository`、`SQLiteTaskRepository` 和
  `RuntimeDatabaseLease` 之前返回，不建表、不写 marker、不创建父目录、不获得共享或独占租约。
  因此空路径、首次启动前、以及指向其他应用 SQLite 或损坏库的 bootstrap 都能读到环境变量的
  SET／UNSET，而不会把数据库适用性拒绝显示成凭据状态错误。
- 保留原有 CLI 参数解析、凭据检查退出码（全部启用身份已设置 0，缺令牌 1，参数或文档错误 2）、
  禁用身份仍显示、输出只含 principal ID、角色、`tokenEnv` 名与 SET／UNSET，不含令牌值。
  旧 `api.tokenEnv` 仍在读取任何数据库前以原错误拒绝并退出 2。
- `api serve` 的启动顺序未改：仍先经 `_configuration()` 判定配置库适用性，再打开运行库；
  其他应用 SQLite、V1 Job schema、更新版本和畸形库仍在任何写入前拒绝。

**测试调整**

- 既有凭据用例改用明确的隔离数据库路径，并在两次检查中同时屏蔽配置仓库与运行仓库，
  断言已设置／缺失两种状态都不新建数据库文件。
- 新增 `test_credential_check_leaves_an_existing_foreign_database_untouched`：用真实 SQLite
  建立只含 `notes` 表和一行内容的文件，经正式 `final_main` 执行凭据检查，核对退出码 0、
  SET 输出、无 secret，且 SHA-256、表集合和笔记行原样保留。
- 旧 `api.tokenEnv` 用例同时断言退出 2、无 secret 输出且未新建数据库。

**实际验证（命令与结果）**

- `.venv/bin/python -m unittest tests.test_api_credentials tests.test_configuration_status
  tests.test_runtime_lease` → 20 项通过（0.27 秒）。
- `.venv/bin/python -m unittest tests.test_management_setup` → 17 项通过（0.28 秒）。
- 正式 `mediaflow api credentials check`：指向含 `notes` 表的隔离 SQLite 时退出 0、显示
  `local-admin | admin | MEDIAFLOW_API_TOKEN | ENABLED | SET`，前后 SHA-256
  `d5384491339117a6df4846574bb7d8961ec5d92b4979c38ca423e0c054488aeb` 一致；指向不存在
  的嵌套路径时退出 0，数据库和父目录均未创建；旧 `api.tokenEnv` 退出 2、无 secret、无数据库。
- 同一 foreign SQLite 上正式 `mediaflow api serve` 仍退出 2，提示 “tables but no current
  MediaFlow schema marker … file was not modified”，前后 SHA-256 一致。
- `.venv/bin/ruff check mediaflow tests scripts`、`ruff format --check`（336 文件）、
  `python -m compileall -q mediaflow tests scripts`、`python3 scripts/check_governance.py`、
  `git diff --check` 通过。
- 本文件、上述命令输出与静态检查日志在
  `.git/validation-evidence/ff008989482ba3c649a9456094e2f80b17ac213b/task55-6-dev/`。
  本轮测试累计约 1 秒，远少于总耗时 30%。

**剩余风险与未完成项（不记为通过）**

- 凭据检查现在只验证部署 bootstrap 的 locator 与 API 身份，不再为读取凭据而校验完整 workflow
  文档；畸形策略字段由 `api serve`、`config validate` 和发布入口继续拒绝。这是本 Task 要求的
  诊断边界，但改变了旧命令顺带校验完整配置的行为。
- B 的完整 T4（全量 Python、全部原生 E2E、Docker 空库／重启／安全镜像、wheel 外安装、
  备份恢复实机链路）未由 Developer 运行，不能由本次结果替代。

**Slice55 结果重评。** RO-1、RO-2、RO-4、RO-5、RO-6 的既有抽测结果保留；RO-3 的凭据诊断
入口在本候选上解除阻塞，正式配置与权限名未改。Slice55 继续 ACTIVE，返工留在 Task55.6，
不改 Slice／Roadmap／Progress，不交 A 终审。

### B 返工复核 — FIX REQUIRED（候选 `ff008989`）

独立审查完整范围 `2e460b71735ac0284e58928c884baac9d3f46009..ff008989482ba3c649a9456094e2f80b17ac213b`。
`ede7624f0500c4c56e668cd14ecf5470d8530900` 只改交接文档。复核起点 `main` 工作区及暂存干净，
治理检查通过。验收使用候选的隔离 Git 工作区、现有本机依赖和独立 Docker 复核环境。

**B55.6-04 已通过。** 正式 `api credentials check` 对空路径和另一应用的 SQLite 均正确报告
SET（退出 0）／UNSET（退出 1），空路径的父目录未创建；同一 SQLite 经正式 `api serve`
拒绝（退出 2），文件未改动。相关既有测试 20 项通过。

| 阻塞 | 实际操作与原因 |
|---|---|
| **B55.6-05（P1，AC-2/4）已保存的有效 V2 整理摘要无法确认** | 用真实 Slice Base 的 Files、逐项决策和 Worker 分析入口生成已审阅的摘要，此时还没有 Task。更换为候选后，仍能读到原摘要与配置 pin，但沿现行 Execute 确认收到 HTTP 500，未产生 Task，源文件仍在。`e53bf3f9`（2026-11-18）删了 Task 的暂停字段，`_adopt_prechange_summary` 仍按旧参数位置传入；另一路已存在的精确确认入库仍用 17 列的无列名 INSERT，新表只有 16 列。全量 Python 的旧摘要确认 3 项失败，直接复测共享执行用例也报列数不匹配。用真实 Slice Base 生成、已有 Task 的四类状态继续通过复验。 |
| **B55.6-06（P1，AC-5）现行验收仍要求已退役的 schema 和流程状态** | 管理员创建草稿并完成命名、分类、整理授权与目标预检后，应能重开当前配置并看到原证据。四个现有 Python 用例在重开前改成 schema 6／7／8／9 并期待旧升级成功，候选按合同拒绝，导致后续业务断言未执行。默认浏览器从 Files 确认或直接打开 Task Center 时，三条失败 trace 的假 API 仍返回 `job-004` 的 `paused` 流程；当前读模型拒绝整页，页面显示「任务中心暂不可用」。另一个真实 API 对照用例的前端 fixture 仍含 `pauseRequested`。真实 Python 浏览器中的现行 Task Center、确认和交接通过。 |

#### Developer 返工指导

1. 按当前 `PersistentTask` 字段创建旧摘要确认所需的 Task，去掉退役暂停参数。共享精确确认
   的 Task 入库复用现有显式列清单，保留事务范围、原 preview／pin、来源归属和一次性授权。
   沿真实 Base 生成的合法未确认摘要走「打开原摘要→确认→Worker 领取→查结果」；再核对
   已受理的原请求重读及并发确认仍指向原执行。现行 Files 和四类续作继续走原 Task 内核。
2. 将四个配置用例接回当前 V2 schema 的重开，继续断言保存的策略、预览、证据和 Active
   约束。保留现有正式入口对不支持库的零改写验证。用现有真实 API fixture 生成入口更新
   精确比对数据，把假 Task Center 列表／详情／计数的生产值收敛到现行状态；保留独立文件
   部分结果。用原有 Files→确认→Task Center、列表／分页和窄屏用例核对这条验收旅程。
   Developer 只运行新增／修改及直接受影响测试。整套 T4 由 B 复跑。

```sh
# 仓库根，正式 Execute、原请求核对、现行配置重开和 API fixture
.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_manual_organize_execution tests.test_manual_operations_contract
.venv/bin/python -m unittest tests.test_configuration_classification tests.test_configuration_destination tests.test_configuration_destination_precheck tests.test_configuration_organize
# web/，先用 npm run build 构建候选
npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/operations.spec.ts
```

**实际门禁。** Python 完整运行 2336 项，6 失败、27 错误、7 跳过。发布测试中的 Task 测试
分工标题由 B 纠正。Ruff、compileall、pip check、两个样例验证和禁用依赖扫描通过。Web
构建、typecheck、lint、format 及 104 个文件／1642 项单测通过。默认浏览器在已确认阻塞后
中止，194 通过、14 失败、1 中断、76 未运行。真实 Files 28 项、Task flow 3 项，以及
Task Center／手工整理组合 55 项通过。Automation 组合 28 通过、1 失败；第二次 Copy 丢响应
用例在新的同配置隔离实例原样单跑通过，保留组合失败记录，完整组合待后续复验。wheel
构建、源码外安装 smoke 和备份恢复入口通过。候选 Docker 镜像已构建，Docker 场景验收待执行。
并行门禁按实际进行时间合计约 6 分 50 秒，少于本轮用时一半。
原始日志、trace 和制品标识在
`.git/validation-evidence/ff008989482ba3c649a9456094e2f80b17ac213b/task55-6-b/`。

**Slice55 结果重评。** RO-1 的既有入口结果保持。RO-2 当前 Files 手工整理、Task Center
和两种库普通操作通过实测，既有摘要确认仍阻塞。RO-3 正式配置和权限契约保持，凭据诊断
通过。RO-4 误选 SQLite 的零改写保持，合法 Base 无 Task 摘要待修复。RO-5 当前确认与核对
主路径通过，既定 session 清理待完成。RO-6 wheel 已通过，当前测试数据与五态契约仍有
缺口，最终门禁待完成。Slice55 继续 ACTIVE，返工留在 Task55.6。
