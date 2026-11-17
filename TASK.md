# Task55.3 — 整理受理、执行与续作只由当前 Task 内核拥有

Next Action: B REVIEWS TASK55.3 B55.3-05 CONCURRENCY FIX CANDIDATE（READY FOR B REVIEW，SAME TASK FIX LOOP）。

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

### B independent review — FIX REQUIRED（2026-11-17，候选01d7ee7f）

完整审查范围：`b73c36353e5427cbe60fbb7c1b8cc85b139edca4..01d7ee7f0f10e583179504b901184b645ca1843d`。
本轮产品修正：`ad199146077981f1609b5ac526ace4988a8ecb09`；候选为其文档交接。
main，初始tracked/untracked工作区干净，治理PASS；在此前完整范围审查上，核对本轮
四文件全部变化、正式入口、当前Task领取与事务／请求核对。Base、Goal、Scope、High/T4
保持；本轮未修改生产代码。

前轮完整验收与原失败见
[145ded12:TASK.md](https://github.com/kentinya/mediaflow/blob/145ded121ba555b8c73ab39eacbe28c3c5f36224/TASK.md)，
上轮B复现／指导见
[f3ae2a69:TASK.md](https://github.com/kentinya/mediaflow/blob/f3ae2a69c638883ef25d18b267e6860e619459b7/TASK.md)，
Developer本轮affected结果和风险见
[01d7ee7f:TASK.md](https://github.com/kentinya/mediaflow/blob/01d7ee7f0f10e583179504b901184b645ca1843d/TASK.md)。
历史结果保留各自候选边界，不作为本候选完整T4通过。

**结论：SAME TASK FIX REQUIRED。上轮无法执行、额外创建Task的两处复现已通过；
B55.3-05剩余的是并发核对误报失败，AC-5的同一请求收敛／准确耐久状态未满足。**
本次响应问题为P2；已验证的执行和身份保持结果仍有效。
B55.3-01–04及已通过修正保持，不规划新Task。

#### 已验证修正

Task Base真实代码通过现有API创建intent、保存C识别／A命名分类、生成摘要并确认，
在Worker执行前由候选打开同一临时库，原请求再次确认：202回读原execution／Task。
原Task补上queued/execution调度，当前真实Task engine领取并完成原Task／execution，
产生1条Result，Task数始终1，discovery链接原Task，pin保持。
原“无人执行”和“Task从1增为2”均已修正。Developer的当前同Task正向断言保留。

独立运行本Task相关八模块：225 tests OK，14.255秒，墙钟14.46秒；含V2整理、
execution、内核、API contract、持久化、容量、fencing和来源竞争。未把这些affected
结果替代完整T4。

#### B55.3-05剩余项 / P2 — 两个相同核对请求，一个成功、一个误报失败

**实际完整旅程：** 用户此前已确认整理，程序更新后继续原工作。两个客户端同时核对
同一项原确认（相同用户、摘要、选中项、版本、破坏性权限），一个收到202及原execution，
另一个收到409“已经确认的工作无法重新登记到当前Task内核”。此时原工作实际已经进入
queued，Task数仍1。第二个客户端看到“受理变化／拒绝”而不是原工作身份，不能从本次
响应得知这项工作已排队。

本轮分别用Task Base `b73c3635`、Slice Base `2b2e7c18`真代码，经正式入口建立数据：

1. `POST /api/v1/resource-libraries/library/files/organize`，201。
2. 原intent逐项choice API保存C／A／A，200；原intent/previews API分析，201；
   Base当时正式discovery Worker生成previewed摘要。
3. `POST /api/v1/operations/organize/previews/{previewId}/execute`，正常确认体，202。
4. 候选打开同库，通过第3步的同一正式WSGI入口，同时发起两个完全相同请求。
   仅在请求开始前同步两个客户端线程；没有挂钩内部事务、手工插入业务行或改写状态。
5. **两种Base数据都得到202／409**；409为`admission_changed`，原因ValueError，
   提示`rejected_without_mutation`，没有原executionId。原工作此时已queued，Task数1。

正常生产`api serve-production`使用Waitress并支持并发线程（final_cli.py:3360–3375），
所以这是已有入口的真实并发语义；不依赖不存在的入口或内部故障注入。
对照：Task Base同一正式入口的两个相同请求均202，回读同一execution，Task数1；
其原Worker随后完成同一Task并产生1条Result。所有媒体在临时Local根，Provider为fake。
八请求的首次并发观察同样保留在日志，最终判断使用上述两个请求的最小复现。

**代码原因：** `_continue_confirmed_execution`在事务外先读scheduling（649–655行），
两个请求都可能读到不存在，随后依次进入`adopt_confirmed_manual_execution`。
第一个事务登记调度，并把原Task从running改为pending。第二个事务在
`sqlite_runtime.py:12080`先强制要求Task仍为running，抛ValueError；到12116行才读取
“已经登记”的调度，因此本来用于幂等回读的分支无法处理这个正常竞争结果。
应用服务最终把它映射为409。新增方法的“并发／重复收敛”承诺与实际响应不一致。

#### Developer指导与修正验收

1. 在`adopt_confirmed_manual_execution`的同一个事务中，先识别该原Task／execution
   已经由同一工作登记的当前调度。精确身份和pin相同的重复请求回读原工作，不再套用
   “尚未登记时必须running”的一次性前置条件，不重写现有queue／claim／效果状态。
   只有确实尚未登记的首次补链才执行旧状态、容量、未开始及原确认检查和写入。
2. 事务外读取只能减少一次写入调用，不能承担并发正确性。保留当前权限、原pin、来源、
   精确确认与逐效果fence；不用捕获所有ValueError后直接当成功，也不重试／重建Task。
   上轮已修正的原Task／TaskItem／execution身份保持和实际完成结果继续成立。
3. 在现有`test_prechange_confirmed_execution_continues_on_its_original_task`旅程旁
   加入两个真实API请求的并发核对：两者均返回同一execution／Task，Task数1、仅一条
   scheduling，分析／核对阶段零媒体效果。随后当前Worker实际执行一次，结果与媒体
   效果各一次；后续核对继续读取原工作。保留容量满、原确认不等价和已开始／已完成
   不重放的现有断言。只调整这条事务的幂等顺序，不增加迁移／队列／探测工具。

Developer运行新增／修改及直接受影响测试：
`tests.test_v2_manual_organize`、`tests.test_manual_organize_execution`、
`tests.test_manual_task_engine`、`tests.test_task_persistence`、
`tests.test_task_scheduling`、`tests.test_task_scheduling_fencing`；涉及API消费者时同时跑
`tests.test_manual_operations_contract`。完整T4／原生／wheel／Docker仍由B承担。

#### 本轮证据、门禁与全部Slice结果重评

本地稳定忽略证据根：`.git/validation-evidence/01d7ee7f/task55-3-b/`。

| 验证 | 实际结果 |
|---|---|
| 上轮原待执行工作复现 | 同Task／execution完成，1条Result，1项Task，pin保持；base-queued-execution.log |
| 本Task八模块 | 225 tests OK，14.255秒，墙钟14.46秒；focused.log |
| Task Base→候选双请求 | 202／409，原工作queued，Task数1；two-requests.log |
| Slice Base→候选双请求 | 同样202／409；slice-base-two-requests.log |
| Task Base原行为对照 | 双请求均202同execution，随后原Worker完成；base-two-control.log |
| 首次八请求观察 | 7个202／1个409，保留原日志；concurrent-repeat.log |
| 治理／文档／whitespace | check_governance.py PASS；tests.test_governance 20 tests OK，6.364秒；完整Base..Head及文档git diff --check通过 |
| 当前候选完整T4／原生／产物／Docker | 本轮未执行；已证实AC-5缺口后按工作流提前FIX REQUIRED，不记PASS |

ResourceWarning保留在focused.log；前轮原生组合失败与Docker未通过事实仍在Git指向
报告和原证据目录中。本轮不改写历史结果或将验收环境工作转交Developer。

全部RO重评：RO-1保留55.1接受事实；RO-2保留55.2及55.3已接受清理，当前新请求、
存量分析及已确认未执行工作均可由Task继续；本Task剩余并发核对准确性待修正，全局V1
审核保持原后续边界。RO-3完整JSON权威／管理员回落、RO-4其余旧flow／升级清理、
RO-5其余session／协议仍待后续；本轮原请求核对属于55.3。RO-6最终候选完整门禁待B。
Slice55保持ACTIVE；SLICE／Roadmap／Progress不变，不声明Task或Slice PASS。

计时：已记录复核区间2026-11-17 13:00:22–13:04:49（Asia/Shanghai），4分27秒。
225项相关测试墙钟14.46秒，20项治理测试墙钟6.39秒；真实入口短复现和治理命令计入后，
测试／验证合计按不足30秒记录，小于本轮50%。
下一步Developer修正同一B55.3-05并发核对后交B。

## Developer 修正交接 — 2026-11-17（B55.3-05 并发核对）— READY FOR B REVIEW

```text
Task Base: b73c36353e5427cbe60fbb7c1b8cc85b139edca4
Fix checkpoint: 42b9a3ee9ece8de8cab2a5fa5320ecac7a034e1e
Branch: main
Initial workspace: clean (tracked/untracked), governance PASS
B finding addressed: B55.3-05 (P2)
```

本轮只修正已确认、尚未执行的原 Task 在两个相同核对请求下返回 202／409 的并发
语义；未改 Base／Goal／Scope／AC，未新增入口、迁移、队列或探测工具。

**根因与修正**

- 根因：应用层 `_continue_confirmed_execution` 在事务外读取 scheduling，两个并发
  请求都可能读到“尚未登记”；第一个事务登记并把原 Task 从 running 改为 pending，
  第二个事务仍先要求 Task 为 running，于是在读到“已登记”之前抛 ValueError，最终
  被映射为 409 `admission_changed`。
- 修正 `SQLiteTaskRepository.adopt_confirmed_manual_execution`：在同一个
  `BEGIN IMMEDIATE` 内先读取原 Task pin 与该 Task 的 scheduling；scheduling 已存在
  时，只在 principal／Task／pin 精确一致下回读原工作，连接仍未链接的 discovery，
  不重写 queue／claim／item／effect 状态。只有确实尚未登记的首次补链才执行原
  RUNNING、consumed authority、无 Result、TaskItem 未开始和共享容量检查并写入。
- 事务外读取仍只作为减少写入调用的快路径，不承担并发正确性；未捕获所有
  ValueError 当成功，未重试、重建 Task 或重放媒体效果。
- 原 execution、TaskItem、Preview、intent、pin、保存决策、确认证据和逐效果 fence
  保持；首次登记仍写一条 scheduling 并把原 Task 置为 pending。

**实际验证（仓库根目录）**

- 新增
  `tests.test_v2_manual_organize.V2ManualOrganizeJourneyTests.test_prechange_confirmed_execution_concurrent_readback_keeps_one_task`：
  经真实 Files intent／choice、Preview、execute 和 admission 入口形成 Base 形态
  （1 Task、0 scheduling、未链接 discovery），再通过同一正式 WSGI execute 入口以
  两个线程在请求发出前同步，并发提交两个完全相同的核对请求。
- 断言两请求均 202 并返回原 execution／Task；Task 数 1、scheduling 仅 1 条且为
  queued／execution；discovery 链回原 Task；pin 与 TaskItem 身份保持；核对阶段
  源／目标媒体效果为零。随后第三次核对仍返回原工作，真实 Task engine 只执行一次，
  产生 2 条 C Result、2 次源删除／目标写入和 2 个目标文件；完成后 admission 核对
  仍读原 execution 并报告 completed。
- 反证：仅在测试前恢复 Base 源码、保留新测试，同一用例 10/10 次以 409
  `admission_changed`（reason ValueError）失败；恢复修正后 10/10 次通过。
- `.venv/bin/python -m unittest tests.test_v2_manual_organize
  tests.test_manual_organize_execution tests.test_manual_task_engine
  tests.test_task_persistence tests.test_task_scheduling
  tests.test_task_scheduling_fencing tests.test_manual_operations_contract`
  → **213 tests OK，13.363 秒，墙钟 13.672 秒**。
- `.venv/bin/python -m unittest tests.test_execution_authorization
  tests.test_manual_task_engine tests.test_automation_task_admission
  tests.test_task_scheduling tests.test_task_scheduling_fencing
  tests.test_automation_entrance_recovery tests.test_v2_manual_organize
  tests.test_operations_task_center tests.test_task_item_metadata_search
  tests.test_task_source_ownership_race tests.test_manual_operations
  tests.test_manual_operations_contract tests.test_processing_worker_readiness`
  → **267 tests OK，15.254 秒，墙钟 15.473 秒**。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` → PASS；
  `ruff check` 与 `ruff format --check`（两个改动文件）→ PASS。
- ResourceWarning 为既有 SQLite 测试痕迹，未见产品失败。

**剩余风险／未执行**

- 完整 T4、全量 Python/Web、Node 原生、wheel、候选镜像 Docker 与浏览器验收仍由 B
  执行；本报告不声明这些通过。
- 容量满、原确认不等价、已开始／已完成不重放等既有断言保留并由上述模块实际通过；
  本轮未新增满额夹具，未改变其生产路径。
- Web src、README、Docker harness 未改；本轮无新配置键、页面或恢复类型。
- 真实并发由两个正式 API 请求验证，请求前同步客户端线程；未挂钩内部事务或手工
  插入业务行。

计时：本轮约 13:55–14:05（Asia/Shanghai）。实际测试墙钟合计约 32 秒（含两次
10 次反证／稳定性重跑），约占总耗时 6%，低于 30%。Slice55 保持 ACTIVE，
SLICE／Roadmap／Progress 不变，不声明 Task 或 Slice PASS。
