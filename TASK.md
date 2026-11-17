# Task55.3 — 整理受理、执行与续作只由当前 Task 内核拥有

Next Action: B REVIEWS TASK55.3 B55.3-05 FIX CANDIDATE（READY FOR B REVIEW，SAME TASK FIX LOOP）。

Task55.2 的 B 独立复核为 **PASS**，完整范围
`ebec19bb7592306980a4f288c78378b264f3321f..96ae77450e96b9103007ef29714ce29dcb4669cd`。
实际验收、返工、原始失败、复用依据及全部 Slice 结果重评见
[b73c3635:TASK.md](https://github.com/kentinya/mediaflow/blob/b73c36353e5427cbe60fbb7c1b8cc85b139edca4/TASK.md)。
Task55.1 接受事实见
[ebec19bb:TASK.md](https://github.com/kentinya/mediaflow/blob/ebec19bb7592306980a4f288c78378b264f3321f/TASK.md)。
既有 PASS 保持；Slice55 保持 ACTIVE。

Authority: committed [SLICE.md](SLICE.md) 的 RO-2 中远程票据、非内核整理、旧恢复链
退出，以及 RO-3/4/5/6 的对应依赖；生命周期依
[Development Workflow](docs/development-workflow.md)。用户明确要求“激活Task吧”，据此
将已提交草案转为正式 Task55.3，授权 Developer 按本 Task 实施。

```text
Task ID: 55.3
Task Type: SLICE
Parent Slice: 55
Status: READY FOR B REVIEW
Task Base: b73c36353e5427cbe60fbb7c1b8cc85b139edca4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: TASK55.3 IMPLEMENTATION AUTHORIZED
```

规划现场：2026-11-17，`/Users/songzhidong/mediaflow`，main，上述 HEAD；初始工作区
干净，文件与 Git 可写，治理 PASS。未读取私有配置、运行库或用户媒体。
Base 固定，规划提交不换 Base；实施前核对介入改动和治理。本轮没有新的 Developer
候选，不重审或改写 Task55.2 PASS。

激活现场：main，HEAD `064d942af978fca963e3f838335fc367cd2b217d`，工作区干净，
治理 PASS；相对 Task Base 仅有草案文档提交。保留原 Goal／Scope／Base／验收／测试
分工，状态为 PLANNED；Developer 开始实施时更新为 IN PROGRESS。

### Goal / complete journey

用户在资源库 Files 选文件／批量／有界文件夹并点击整理，立即获得一项耐久 Task；
发现、稳定性等待和分析都属于该 Task。逐项保存决策并重新分析，检查精确摘要，
一次确认选中项；Worker 只领取该 Task，在任务中心呈现独立文件及附件结果。
自动化到期与列表“运行一次”使用相同内核，保留各自已接受的执行意图。

识别、Metadata、分类、冲突在原 Task 内完成决策→分析→摘要→显式继续。关闭、刷新、
重认证或 Worker 重启后仍读取原工作；丢响应核对原请求，满额保留已保存决策和摘要，
权限／来源／pin 失效说明实际阶段与下一步。成功兄弟及未知效果不重复执行。
普通文件 Copy/Move/Delete 继续在原库页面查看进度与恢复。

完成后没有远程票据受理、独立 discovery/execution 队列或旧恢复子 Task 执行链。
当前内部 intent、preview、单次确认、execution/effect 和恢复摘要保留证据职责。

适用：`V2-RETIRE-002–006/008–010` 的上述部分；保留 `V2-TASK-001–006/010–014`、
`V2-OPS-007/008/010/012/017–019`、`V2-AUTO-010–015`，以及当前修订后的
`REQ-TASK-005–007/009/010`、`REQ-RECOVERY-001–009`、`REQ-SAFE-001–008`。
完整旅程见 Product Experience 的 One organizing Task、Manual organize（含文件夹与
Slice53 弹窗）、Tasks/results/recovery、Scheduled unattended organization；受影响
CURRENT/TARGET 契约见 Architecture 的 Slice47 与 Slice55 TARGET。

### Actual code / existing entries

下表来自实际注册、生产调用和现有入口测试，不用臆造地址或不可达状态作为缺口。

| 位置 | 已核对事实与本 Task 改变 |
|---|---|
| `cli.py`、`final_cli.py` parser／dispatch | help 实际注册 execution-authorizations {issue,list,show,revoke}。删除该组命令、渲染及注入；当前 organize --execute 和不带 execute 的分析入口保留。 |
| `service_api.py` POST /api/v1/tasks | 仍检查 REMOTE_EXECUTE、api.remoteExecution、X-MediaFlow-Execution-Token，再用 ExecutionAuthorizationService 受理。整条票据表面退出；GET /tasks、详情、日志／导出、当前直接恢复与取消保持。 |
| `application/execution_authorization.py`、同名 domain、`sqlite_runtime.py` | 票据 issue/consume/revoke/audit 和专属表仍在；与当前 Web 的 ManualExecutionAuthorization 是不同职责。 |
| `application/automation.py` ResidentProcessingWorker、`final_cli.py` composition | run_next 依次轮询 Task、MediaDiscoveryWorker、ManualOrganizeExecutionWorker、FilesTransferWorker。删除中间两个独立领取包装，直接给 Task engine 装配原 discovery/execution service；普通文件 runner 保持。 |
| `media_discovery.py`、`manual_organize_execution.py`、仓库 | task_scheduling_enabled=False、claim_next_media_discovery、claim_next_manual_execution、可缺 task_context 的执行仍支持独立路径。删除该路径，保留内核按精确记录领取、续租、逐项执行与 fence。 |
| `manual_recovery_continuation.py`、`scope_continuation.py`、`task_item_recovery.py`、`processing_checkpoint.py` | 混有旧 source→new Task/analysis/link 查询与当前摘要／资格检查。删除旧链与无消费者 reader；共享来源、剩余安全范围、权限和效果检查按当前职责保留。 |
| `service_api.py` 恢复 routes | authorize-organize、manual-recovery-links/execute、continue-batch、recovery-batches、remaining-scope-previews 及旧链专用 410 仍在。退出这些表面；continue、prepare-summary 中当前同 Task 行为保留。 |
| 当前恢复确认 | `automatic_task_continuation.py:_publish_summary` 向 manual_recovery_preparations 写入 source_task_id=analysis_task_id=原 Task 的摘要；Web 仍调用 /manual-recovery-preparations/{id}/confirm。该表、确认路径和原摘要 ID 有当前职责，保留当前行为并删除跨 Task 兼容。Files native 摘要确认也保留。 |
| manual 别名／独立授权 | manual-organize、manual-organize-intents 被改写为 manual-intents；manual-previews 下仍有独立授权／执行步骤。删除别名与独立步骤，当前 operations/organize、内部单次确认及历史证据保持。 |
| Web api-client、RunDetailTabs、recovery-batch-session | 仍有旧 batch／authorize／execute 函数与旧链模型；RunDetailTabs 引用 submitTaskRecoveryBatch。删除旧链交互与未用函数，当前四类逐项处理、摘要确认和原请求核对保持。 |

### 两项退出对象的当前使用与实际影响

**远程票据：目前仍可使用的一项外部脚本入口。** 管理员启用
`api.remoteExecution.enabled` → 用 `mediaflow execution-authorizations issue` 领取
单次票据 → 外部脚本携带 `X-MediaFlow-Execution-Token` 调用 `POST /api/v1/tasks`
发起整理。该入口在 [README](README.md) 中仍有正式用法，系统设置消费者
`web/src/features/configuration/configuration-settings.ts` 仍有启用／TTL 字段说明；
`docker_empty_baseline_smoke_test.py`、`docker_restart_fault_smoke_test.py`、
`docker_release_security_smoke_test.py` 和 `operations_inventory_harness.py` 仍使用它。

`ExecutionAuthorizationService.submit_organize` 已将票据受理为带 scheduling 记录的
当前 Task，后续由当前内核运行；票据是额外的准入方式。本 Task 按 Slice55 RO-2
删除这项仍可用的受理能力。删除后外部脚本不能
再通过该命令／header／POST 组合发起整理；当前 Files 整理、due、Run once、direct
CLI 和 Web 内部单次确认继续使用各自现有入口。相关设置说明、README 与验收脚本
同步退出票据用法，当前功能断言接回已有支持入口。

**独立领取：常驻 Worker 仍装配的两条额外轮询路径。** `final_cli.py` 构造
MediaDiscoveryWorker 和 ManualOrganizeExecutionWorker，交给 ResidentProcessingWorker；
其 run_next 在 Task runner 之后依次调用二者，再调用普通文件 runner。实际查询范围为：

- `claim_next_media_discovery` 只领取没有 organize_task_id，或其关联 Task 没有
  task_scheduling 记录的 discovery。
- `claim_next_manual_execution` 只领取其 Task 没有 task_scheduling 记录的 execution。

正常 V2 Files 整理在受理时启用 Task 调度，走 ManualTaskEngineWorker；上述两个
独立查询明确排除这种记录。当前 Task 引擎仍从这两个包装对象的 `.service` 取得
真实 discovery/execution service，并按已领取 Task 关联的精确记录调用处理服务。
本 Task 删除两个包装 worker、额外轮询和面向非内核记录的全局领取，改为直接装配
原 service；当前发现、稳定性等待、分析、精确执行、记录级 claim 与逐效果 fence
继续保留。普通文件 runner 保持其现有独立职责。

规划实测：`.venv/bin/mediaflow --help` 与 `execution-authorizations --help` 显示上述命令；
现有 `ExecutionAuthorizationTests.test_api_ticket_admits_one_queued_authorized_task_without_a_job`
与 `test_cli_organize_execute_admits_and_executes_one_kernel_task` **2 tests OK，0.084秒**。
前者证明现存票据入口可受理，后者证明当前直接 CLI 内核能力可保留；不是退役验收。

### Implementation scope / Developer 指导

1. **固定当前调用和证据职责。** 沿 Files、direct CLI、due、Run once、四类恢复的生产
   调用调整夹具，明确 Task/item/preview/execution 关联。保留自动化当前 preparation 和
   Files native 摘要的原 ID／确认语义；不要整删 manual_* 表、recovery_requests 或审核
   模型。删除旧正向测试时，将仍有当前职责的断言接回上述入口。
2. **退出远程票据产品。** 一起删除 CLI 注册、API POST 受理、header 消费、专用权限／
   配置字段、服务／领域／仓库 CRUD 与新库专属结构；同步样例、部署生成器、当前说明、
   上述 Web 设置消费者、安装／Docker smoke 和测试。新输入含 api.remoteExecution
   按废弃参数拒绝，不静默忽略。
   现有合法 V2 发布文档及 pin 原字节／digest 保持，读取不能重新赋予票据执行资格；
   用真实 Base V2 配置验证，不改写历史原文来满足新输入要求。
3. **Worker 只从 Task 领取整理。** composition 直接构造 discovery/execution service，
   供 ManualTaskEngineWorker 调用；删除两个独立 worker 模块、轮询、全局 claim_next、
   无 scheduling 回落与非内核执行。保留内核嵌套的精确 claim、心跳、逐效果 fence 和
   OrganizerExecutor 唯一变更职责。run-next 只呈现实际保留 runner 的结果；普通文件
   不改进整理队列。保留当前 Worker 健康／无 Active 常驻和原 pin 重建。
4. **续作只属于原 Task。** 混合恢复服务收敛为当前同 Task 分析、摘要和确认；删除独立
   authorize/execute、子 Task／批次／scope 链的受理、运行、查询、专用 409/410 和
   新库专属结构。保留自动化同 Task preparation、版本化 item/attempt/请求/结果、原
   来源与 pin、重复确认回读及当前资格。current continue 对不适用工作使用当前资格／
   状态说明，不保留 Job 退休说明；不新造替代映射／恢复系统。
5. **同步消费者。** 删除 manual 别名／独立授权传输及旧 Web batch/link 分支；保留当前
   prepare-summary、confirm 和 direct /tasks 恢复／取消。权限、满额、已保存决策、
   unknown 与 sibling summary 身份用原证据；同步 fake/fixture/harness、路径模板和
   包清单，保留当前安全断言。现有 V2 库的历史原样保留，当前查询不依赖旧链 CRUD。
6. **交完整检查点。** affected tests 后提交 READY FOR B REVIEW，简述删除项的退出职责
   和保留的当前断言。B 承担全量及最终验收；本 Task 问题留在同一修正循环。复用已有
   测试入口，不开发新的治理／通用探测／证据平台。

### Acceptance Criteria

- [ ] AC-1：正常配置、合法 principals 与现存真实请求下，票据 CLI 不注册，旧 POST
  /tasks 为普通未知方法／路由，旧 header 不消费；没有专用退休响应或暗中受理。
  README、Web 设置消费者和上述脚本不再提供或依赖票据入口；当前 GET /tasks、
  direct CLI organize／分析和 Web 工作正常。
- [ ] AC-2：源码／包／镜像无票据服务、专用权限、配置运行权威和 CRUD；新库无
  execution_authorizations／execution_authorization_audit。存量历史不自动删除。
  含旧字段的新输入准确拒绝，零发布／Task／媒体效果，合法 V2 配置及 pins 保持。
- [ ] AC-3：Files 单项／批量／文件夹、due、Run once、四类恢复仅从 Task scheduling
  claim 执行；独立 discovery/execution worker、全局领取、非内核回落退出。真实稳定性、
  完整范围、容量1–10000、来源所有权、当前取消和三项设置实际采用保持。
- [ ] AC-4：四类保存决策／分析／摘要／确认仍在原 Task；旧子 Task／批次／scope 执行
  及专用入口退出。当前自动化 preparation、Files native 摘要、原 ID／关联／确认路径
  继续有效；Task/item/结果/问题计数及自动化统计不重复。
- [ ] AC-5：满额、并发确认、来源变化、权限撤回、pin 不可用和 claim 丢失给出准确
  阶段／耐久状态／效果／下一步；拒绝保留决策与摘要。完成／未知主文件或附件不重放，
  丢响应仍核对原提交，兄弟新摘要不改变它；分析与读取零媒体变更。
- [ ] AC-6：Slice Base 真代码经已有 V2 入口建立正常配置、待确认 Files、四类恢复
  决策／摘要、待执行 due/Run once、完成／未知结果和丢响应请求，由候选继续使用同库；
  原 ID/关系/digest/pins/结果/核对保持，无需重建或重发。新库及同版本 reopen/restart
  正常；旧链专属表不再新建，当前共用结构完整。
- [ ] AC-7：两种库普通维护／异步 Copy/Move/Delete、任务中心详情／导出／权限与脱敏、
  通知和当前 CLI 保持；C 使用 A 命名／分类仍为 C。安全断言没有随旧测试整删。
- [ ] AC-8：当前浏览器构建、源码外 wheel 安装与候选四服务 Docker 一致；桌面、390px、
  矮视口、键盘／关闭／来源返回可用。当前说明只声明本 Task 已交付范围。

### Required Tests

按 [测试分工](docs/development-workflow.md#6-test-levels) 执行。每轮测试墙钟占该轮总耗时
**小于50%**；先核对实现与真实旅程再跑所需门禁，简记实际起止时间。未完成的必需门禁
由 B 继续完成，不削断言或把未跑写成 PASS；不为计时改造工具。

**Developer — affected tests（仓库根目录）：**

```sh
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_execution_authorization tests.test_manual_task_engine tests.test_automation_task_admission tests.test_task_scheduling tests.test_task_scheduling_fencing
.venv/bin/python -m unittest tests.test_automation_entrance_recovery tests.test_v2_manual_organize tests.test_operations_task_center tests.test_task_item_metadata_search tests.test_task_source_ownership_race
.venv/bin/python -m unittest tests.test_manual_operations tests.test_manual_operations_contract tests.test_processing_worker_readiness
git diff --check
```

票据模块改为入口退出断言，保留其中 direct CLI 的执行／分析／容量／claim 断言；旧链
测试改接当前同 Task 入口。新增／修改及直接受影响模块还跑自身测试与 changed-file
Ruff；不指派整个 Python/Web/E2E 或发布矩阵给 Developer。

Web 改动在 `web/`：

```sh
npm run typecheck
npm run test -- run src/entities/operations/task-item-recovery.test.ts src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'native recognition recovery|native Metadata candidate recovery|native Metadata correction|native Classification recovery|native conflict recovery'
```

这些既有真实 Python 入口覆盖同 Task 四类保存／分析／摘要／确认；被修改的 fake/API
consumer 测试同时运行，不凭伪 Task 关系证明存量 V2 连续使用。

**B — acceptance：** 独立审查完整 Task Base..candidate，包含删除、默认 composition、
当前消费者和存量 V2 连续使用。执行 [T4 shared full gates](docs/development-workflow.md#shared-full-regression-commands)，
包括 Python/Web 全量、Node E2E、质量／依赖／示例、wheel 与源码外消费者；不转交 Developer。

在 `web/` build 后，用现有 playwright.python.config.ts 跑完整
operations-inventory.python.spec.ts、manual-organize-dialog.python.spec.ts、
organize-source-history.python.spec.ts、metadata-search-year.python.spec.ts、
task-flow.python.spec.ts、automation-run-once.python.spec.ts、
automation-workspace.python.spec.ts、automation-settings.python.spec.ts。
同一真实 SQLite harness 串行；其他 E2E 使用独立 output-dir。查看截图并核对取消、
普通文件与通知。候选镜像执行现有 docker_smoke_test.py、docker_restart_fault_smoke_test.py、
docker_release_security_smoke_test.py，按各脚本 --help 使用精确镜像和隔离根。

复用已有 Base 连续使用夹具／入口，补本 Task 原恢复摘要／未知请求数据，不建通用迁移
工具。旧路径反证只用上表已注册路径与正常请求，先证明当前入口可用。证据依工作流
存稳定忽略目录，保留失败及跳过事实。

### Non-goals / 全部 Slice 结果重评

不增加入口、恢复类型、权限、队列、数据转换或页面设计；不改变当前 CLI 审核／确认
服务，不处理本单元以外的 V1 全局审核队列。完整 JSON 运行权威、tokenEnv 管理员回落、
其余配置／事件别名、paused/partial_success flow／字段、全局 schema 升级清理、旧
session／协议适配留在 Slice 后续完整单元。本 Task 的旧链专属结构／执行回落必须
一起完成，不能据此推迟。

全部六项 RO 重评：RO-1 已由 Task55.1 完成；RO-2 schedules/grant 已由55.2
完成，本 Task 处理票据／独立整理与旧续作链，V1 全局审核表面仍待后续。RO-3 的全局
配置权威、RO-4 的历史 flow／升级、RO-5 的旧 session／响应仍未完成；RO-6 随各完整
结果同步产物与说明，尚未达到全仓退役。激活不代表任何新结果已交付。

下一步由 Developer 实施正式 Task55.3。Slice55 保持 ACTIVE，SLICE/Roadmap/Progress
边界保持；实施验收 PASS 后再核对全部 RO，决定 NEXT TASK 或 Closure Packet。

### B independent review — FIX REQUIRED（2026-11-17，候选20500963）

完整审查范围：`b73c36353e5427cbe60fbb7c1b8cc85b139edca4..205009635b73f4dbe8c8e618aad0b3ba7949088a`。
本轮源码检查点 `dfcf028471b8a79f68800b73e209439759290b38`；候选 HEAD 为其文档交接。
main，初始 tracked/untracked 工作区干净；治理 PASS。基于此前完整范围审查，核对本轮
六文件全部变化、正式入口、独立 Worker 删除及当前 Task claim／持久化关系。
原 Base、Goal、Scope、High/T4 不变；本轮没有修改生产代码。

前轮完整验收与原失败见
[145ded12:TASK.md](https://github.com/kentinya/mediaflow/blob/145ded121ba555b8c73ab39eacbe28c3c5f36224/TASK.md)，
上轮 B 结论与指导见
[f737be57:TASK.md](https://github.com/kentinya/mediaflow/blob/f737be573818bac9372896ec66d6368aaedb5c97/TASK.md)，
Developer 本轮 affected 结果、失败原子性与风险原文见
[20500963:TASK.md](https://github.com/kentinya/mediaflow/blob/205009635b73f4dbe8c8e618aad0b3ba7949088a/TASK.md)。
历史证据保持各自候选边界，不作为本候选完整 T4 通过。

**结论：SAME TASK FIX REQUIRED。原存量分析分支已修正；B55.3-05 尚有已确认待执行
工作无法继续，重复核对还产生额外 Task。AC-6、Slice AC-05 与原请求身份要求未满足。**
B55.3-01–04 沿用已接受修正，不规划新 Task。

#### 已验证修正

使用 Task Base 真代码，经原资源库 Files API 创建 intent 并请求分析，停在原
analyzing 状态，再由候选打开同库、继续原 intent：201，原 discoveryId 与 pin 保持；
当前引擎领取新增的唯一 Task，生成 preview。上轮完全无人领取的短复现通过。
本轮独立运行 API contract／V2 整理／持久化三模块，73 tests OK，4.453秒。
当前测试覆盖分析补 Task、原摘要确认、实际同 Task 效果及结构写入回滚；这些通过事实
保持，不把本轮未完成的完整验收写成 PASS。

#### B55.3-05 / P1 — 已确认的原工作仍无人执行，核对请求产生第二个 Task

**用户完整旅程：** 改版前，用户选择 `Movies/One.2001.mkv` 整理，保存 C 识别类型与
A 命名／分类，分析得到精确摘要，确认整理后收到202“已受理、等待 Worker”。此时升级
并继续查看原工作，任务一直 running、执行一直 admitted，没有结果。用户按原请求核对
同一确认，响应仍是原 Task／execution，库中却多出第二个 Task；原工作依然不会执行。

本轮分别用 Task Base `b73c3635` 与 Slice Base `2b2e7c18` 的真实代码，经现存正式
API 完整生成以上数据，再交候选打开同库。没有手工构造 Task／execution 行。
Slice Base 在首次发布前使用正常 V2 配置的旧 schedules 空槽，未改写已发布文档。
入口依次为：

1. `POST /api/v1/resource-libraries/library/files/organize`，201，取得原 intent。
2. 原 `/api/v1/operations/organize/intents/{intentId}/items/{itemId}/choice` 保存决定，200；
   原 `/api/v1/operations/organize/intents/{intentId}/previews` 请求分析，201。
   Base 当时正式独立 discovery Worker 生成 previewed 摘要。
3. `POST /api/v1/operations/organize/previews/{previewId}/execute`，正常确认体，202。
   库中已有1项 Task、原 execution 与 TaskItem，原 Task 没有 scheduling，discovery
   未链接 Task。这是 Base 正式入口的合法结果。
4. 候选注册当前 Worker，真实 Task engine 领取结果为 None。重复第3步的同一请求，
   202回读同 executionId／taskId；原 Task 的 scheduling 仍为空。
5. Task 数量从1变为2，discovery链接新 Task；原 Task仍running，原execution仍admitted，
   Result数量0。重复之后当前引擎仍无可领取工作，原 pin保持。

对照：Task Base 的相同正式请求由当时装配的独立 execution Worker 完成，保留原 Task，
产生1条 Result及实际目标写入／源删除。全部媒体均在临时 Local 根，Provider 使用 fake。

**代码原因：** `_adopt_prechange_summary`（manual_organize_execution.py:924）按
尚未链接 Task 的 discovery 新建 Task，未先采用已有 execution 所属的原 Task。
`execute`在1417行调用它并独立提交，再进入 `admit_manual_execution` 检查已受理项。
重复项被拒绝后，`begin_web_execution` 在498行回读原 execution，但先提交的新 Task
不会回滚。因此既没有给原待执行 Task补上调度，也改变了核对请求的持久化关系。
Developer 报告中的“已有 Task 但缺 scheduling”现已证实是正常 Base 正式入口可生成
的数据，属于本 Task AC-6，不是可排除的畸形库或通用迁移范围。

#### Developer 指导与修正验收

1. 沿原 intent→discovery→preview→execution→Task／TaskItem 的实际关系收敛同一工作。
   对已确认、尚未执行的合法 Base 工作，采用原 execution 的 Task／TaskItem 身份，
   补齐当前内核领取所需的调度与关联；保留原确认、选中范围、来源、pin、决定、请求
   和效果证据。用户继续原工作并获得原 Task 的结果，无需重新选择或再次授权整理。
2. 把“查明原请求是否已受理”与所需关联写入放在同一一致性边界处理。重复／丢响应
   核对只返回原工作；原 Task／execution 已存在时，不能先提交新的 Task再由后续
   duplicate_execution返回原 execution。并发核对收敛到原身份；写失败无额外 Task、
   调度或 discovery 错链。使用当前共享容量、来源所有权、claim和逐效果fence。
3. 本轮已通过的无 Task 分析、保存决定后分析、未确认原摘要直接确认保持。将同一
   正式旅程延长到“Base已确认但Worker尚未执行→候选继续原Task→实际完成→原请求
   回读”；同时核对成功／未知效果与兄弟项仍保留各自历史和当前可执行范围。
   不恢复独立 Worker／全局领取，不建设通用迁移或新恢复类型。
4. 在现有 V2／内核／持久化夹具加入已确认工作断言：原 Task／TaskItem／execution／
   preview／intent ID、pin均保持，Task数量不增长，当前Worker实际执行原工作，
   Result与效果独立准确；先核对和执行后核对都返回原工作。上轮要求的“较早请求在
   兄弟工作之后仍可核对”仍需保留当前真实旅程断言，不能只读执行列表代替原提交回读。

Developer运行新增／修改及直接受影响测试：
`tests.test_v2_manual_organize`、`tests.test_manual_organize_execution`、
`tests.test_manual_task_engine`、`tests.test_manual_operations_contract`、
`tests.test_task_persistence`。若修改共享受理，加跑 `tests.test_task_scheduling`、
`tests.test_task_scheduling_fencing`、`tests.test_task_source_ownership_race`。
本次真实 Base 失败链优先验证；结构／关联写入保持失败原子性。完整 T4、原生、wheel、
Docker与验收环境工作仍由B负责，不转交Developer。

#### 本轮证据、门禁与全部 Slice 结果重评

本地稳定忽略证据根：`.git/validation-evidence/20500963/task55-3-b/`。

| 验证 | 实际结果 |
|---|---|
| 原存量分析→候选 | 原discovery／pin保持，1项Task被领取并生成preview；base-pending.log |
| API contract／V2／持久化 | 73 tests OK，4.453秒，墙钟4.70秒；focused.log |
| Base已确认→候选 | Task Base与Slice Base均停滞；同请求202返回原execution但Task从1增为2；base-queued-execution.log、slice-base-queued.log |
| Base原execution Worker对照 | completed，同Task，1条Result及实际媒体效果；base-queued-control.log |
| 治理／文档／whitespace | check_governance.py PASS；tests.test_governance 20 tests OK，6.486秒；完整Base..Head及文档git diff --check通过 |
| 当前候选完整T4／原生／产物／Docker | 本轮未执行；明确产品阻塞后按工作流提前FIX REQUIRED，未记PASS |

首次证据重定向因目录建在源码归档内而失败，随后改用仓库绝对证据路径，未更改产品或
Base源码。ResourceWarning保留于focused.log；历史原生组合失败与Docker未通过事实
保留于前轮Git报告及原始日志，没有删断言或改成通过。

全部RO重评：RO-1保留55.1接受事实；RO-2保留55.2与55.3已接受清理，当前新请求和
存量分析已接入Task，但已确认存量execution仍阻塞55.3；全局V1审核留在原后续边界。
RO-3完整JSON权威／管理员回落、RO-4其他旧flow／升级清理、RO-5其余session／协议
仍按原后续范围；已确认合法工作继续条件属于本Task。RO-6最终候选完整门禁仍待B。
Slice55保持ACTIVE，SLICE／Roadmap／Progress不变，不声明Task或Slice PASS。

计时：已记录复核区间2026-11-17 12:08:18–12:13:25（Asia/Shanghai），5分07秒。
73项相关测试墙钟4.70秒，20项治理测试墙钟6.52秒，真实入口复现及治理短命令计入后
测试／验证按不足20秒记录，小于本轮50%。下一步Developer修正同一B55.3-05后交B。


## Developer 修正交接 — 2026-11-17（B55.3-05 round 2）— READY FOR B REVIEW

```text
Task Base: b73c36353e5427cbe60fbb7c1b8cc85b139edca4
Fix checkpoint: ad199146
Branch: main
Initial workspace: clean (tracked/untracked), governance PASS
B findings addressed: B55.3-05 (P1)
```

本轮只修正已确认、尚未执行的合法 Base 工作无法继续，以及重复核对产生额外 Task 的
问题；未改 Base／Goal／Scope／AC，未恢复独立 Worker、全局领取、页面或恢复类型。

**根因与修正**

- 根因：`execute` 先调用 `_adopt_prechange_summary` 为未链接 Task 的 discovery 提交
  新 Task，然后才进入 `admit_manual_execution`；原 execution 已存在时按
  `duplicate_execution` 回读原 execution，但先提交的新 Task 不回滚。原 Task 没有
  scheduling，当前内核永远领取不到。
- 收敛：`begin_web_execution` 在创建任何 authority 之前，用本次提交的 Preview、意图
  版本、pin、精确选中项、逐项版本／指纹、principal、两处破坏性权限与既有
  execution 的持久化确认证据比对；仅 exact submission 收敛回原 execution。启动／
  完成的 execution 不走此捷径，保持原授权再核对与不重放。
- 原子补链：新增 `SQLiteTaskRepository.adopt_confirmed_manual_execution`，在一个
  `BEGIN IMMEDIATE` 内复核 execution 仍为 admitted、0 attempts、无 claim、授权为
  精确 consumed、Task 为未结束的原 pin owner、无 Result、每个 execution item 与
  TaskItem 仍未开始，然后一起写 scheduling（queued／execution）、Task pending 与
  仍未链接、同 intent／Preview 的 discovery 关联。共享容量不足抛
  `TaskQueueFull`（409 capacity_full）；任何写入失败整体回滚，不留 Task／调度／
  错链。重复领取收敛同一执行身份，已登记调度时不重写。
- 不先建 Task：`execute` 对 exact existing execution 只撤销本次未使用的 authority
  并返回原工作；非等价的重叠提交跳过 prechange 采纳，让 admission 以自身原因拒绝
  且不提交 Task。
- 原 Task、TaskItem、execution、Preview、intent、pin、保存决定、锁与确认证据保持；
  当前 Worker 按既有 claim／心跳／逐效果 fence 执行并产生原 Task 的 Result。

**实际验证（仓库根目录，最终候选 ad199146）**

- 新增回归
  `test_prechange_confirmed_execution_continues_on_its_original_task`：两个文件经真实
  Preview 与 execute 入口形成 Base 形态（1 Task、0 scheduling、未链接 discovery），
  再走现有 API 重发同一确认。断言原 Task／execution／Preview／intent ID、pin、
  TaskItem 身份保持；Task 数仍 1；scheduling queued／execution；discovery 链回原
  Task；无媒体变更。随后真实 `ManualTaskEngineWorker` 领取原 Task 完成，2 条 C 结果、
  2 次源删除／目标写入，执行前后 admission 核对均返回原 execution。
  临时去掉本次生产改动时该测试在原断言失败 `1 != 2`，即 B 报告的第二 Task；恢复后
  通过。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` → PASS。
- `ruff check`（三个改动文件）→ PASS；`ruff format --check`（三个改动文件）→ PASS。
- `.venv/bin/python -m unittest tests.test_v2_manual_organize
  tests.test_manual_organize_execution tests.test_manual_task_engine
  tests.test_manual_operations_contract tests.test_task_persistence
  tests.test_task_scheduling tests.test_task_scheduling_fencing
  tests.test_task_source_ownership_race` → **225 tests OK，墙钟 13.06 秒**。
- 相邻消费者另跑 `tests.test_automation_task_admission`、
  `tests.test_processing_recovery_admission` → 22 tests OK，0.67 秒；
  `tests.test_automation_entrance_recovery`、`tests.test_execution_authorization`、
  `tests.test_manual_operations`、`tests.test_processing_worker_readiness`、
  `tests.test_task_item_metadata_search`、`tests.test_operations_task_center` →
  88 tests OK；同批另指定了不存在的 `tests.test_automation_run_once`，仅该模块
  导入报 ModuleNotFoundError，未计为通过。ResourceWarning 为既有 SQLite 测试
  痕迹，未见产品失败。

**剩余风险／未执行**

- 完整 T4、全量 Python/Web、Node 原生、wheel、候选镜像 Docker 与浏览器验收仍由 B
  执行；本报告不声明这些通过。
- 已开始（execution attempts>0／running）的 Base execution 不重放、不重建调度，
  保持原耐久记录；本轮只承诺 B 所指的“已确认、尚未执行”工作。
- 满额路径映射为既有 `capacity_full` 409，未在本轮新增满额夹具；共享容量本身由既有
  scheduling 测试覆盖。
- Web src、README、Docker harness 未改；本轮无新增入口、配置键或恢复类型。

计时：本轮开始约 12:20，交接约 12:38（Asia/Shanghai）。实际测试墙钟合计约 40 秒
（含缺模块导入批次），约占总耗时 4%，低于 30%，也低于 Task 规定的 50%。
Slice55 保持 ACTIVE，Roadmap／Progress 不变，不声明 Task 或 Slice PASS。
