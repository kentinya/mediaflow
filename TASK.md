# Task55.3 — 整理受理、执行与续作只由当前 Task 内核拥有

Next Action: B RE-REVIEWS TASK55.3 B55.3-05 FIX（SAME TASK，READY FOR B REVIEW）。

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

### B independent review — FIX REQUIRED（2026-11-17，候选6d4747be）

完整审查范围：`b73c36353e5427cbe60fbb7c1b8cc85b139edca4..6d4747be1b913ec8cdffafb5316b7fb52d282c67`。
本轮产品修正为 `70410601f1462610400c60bae749884f9f5360f7`；交接为候选 HEAD。
现场 main，初始 tracked/untracked 工作区干净，治理 PASS；Base、Goal、Scope、High/T4
保持。本轮在此前完整范围审查上复核新增六文件及当前真实消费者，没有修改生产代码。

前轮完整门禁、原始失败、B55.3-01–04 已通过事实与上轮指导见
[145ded12:TASK.md](https://github.com/kentinya/mediaflow/blob/145ded121ba555b8c73ab39eacbe28c3c5f36224/TASK.md)；
Developer 本轮 344 项 affected tests、107 项 Web tests 与剩余风险原文见
[6d4747be:TASK.md](https://github.com/kentinya/mediaflow/blob/6d4747be1b913ec8cdffafb5316b7fb52d282c67/TASK.md)。
这些结果保留其精确候选边界，不作为当前候选全量通过。

**结论：SAME TASK FIX REQUIRED。B55.3-05 的新请求已修正，合法存量工作仍未闭合；
AC-6 与 Slice AC-05 未满足。B55.3-01–04 沿用已接受修正，不增加新 Task。**

#### B55.3-05 / P1 — 改版前已受理的分析无法继续

操作者在改版前通过现有资源库文件整理 API 选择 `Movies/One.2001.mkv`，取得 intent，
请求分析后得到“分析中”；此时重启升级，继续读取／分析原 intent。候选仍返回同一
“分析中”记录，但当前 Task Worker 没有可领取工作，摘要始终为空，用户无法检查摘要、
确认整理并获得结果。原媒体未变，原 pin 保持；这个工作没有可完成的继续路径。

真实入口依次为：

1. `POST /api/v1/resource-libraries/library/files/organize`，正常 `paths` 请求，201。
2. `POST /api/v1/operations/organize/intents/{intentId}/previews`，原 expectedVersion，201。
3. 候选直接打开同一库，经第二个入口继续原工作，201 且 discoveryId 相同。
4. 当前 `ManualTaskEngineWorker.run_next()` 返回 None；Task 数量 0，
   organize_task_id 为 null，status=analyzing，preview_id 为 null，原 digest 相同。

以上分别由 **Task Base b73c3635** 和 **Slice Base 2b2e7c18** 的真实代码与正式 API
生成数据，再交候选使用；没有手工插入业务行或构造不存在的入口。Slice Base 在首次
发布前设置正常 V2 配置的旧 schedules 空槽，没有修改已发布配置或 pin。
Slice Base 夹具、分析服务和原 Worker 均逐字节核对对应 Git blob。
对照：Task Base 的同一正式旅程由当时装配的 `MediaDiscoveryWorker` 生成 preview，
源／目标零变更。候选新建同类请求则建立 1 项 Task，当前引擎能够领取推进；48 项
当前 API contract／V2 旅程测试通过。本轮阻塞集中在尚未接通的存量分支。

代码位置：`mediaflow/application/media_discovery.py:2496–2503`。
`begin_intent_analysis` 找到原 discovery 后，pending 分支直接回读原记录，完全不经过
本轮 `_admit_intent_analysis` 的 Task 受理；原独立 Worker 已退出，没有消费者。
Developer 报告将“存量无 Task discovery”列为不做数据转换，不能覆盖 Slice RO-4 与
AC-6 对合法 V2 工作原 ID／pin／结果／继续条件的明确要求。此处只需完成本 Task
删除独立执行链时必需的最小衔接，边界不变。

#### Developer 指导与修正验收

1. 从上述原 intent 的分析入口及其后续确认入口梳理原 discovery、intent、preview 与
   execution 的真实关联。对本 Task 仍保留的合法 V2 整理工作，补齐由当前 Task 内核
   拥有和领取所需的最小持久化关联；现有 Task 继续使用原 Task，不生成重复工作。
   已存在的 intent／discovery／摘要 ID、已保存决定、原 pin／digest、请求核对与结果
   保持。用户直接继续原工作，无需重新选择文件或重发整理。
2. 领取、共享容量、来源所有权、精确范围、claim／effect fence 继续使用当前内核。
   只分析时零媒体变更，确认后由同一 Task 执行。处理本单元所需的原子写入，不建设
   通用迁移／接管工具，不恢复独立 discovery/execution worker 或全局领取。
3. 用现有夹具覆盖真实 Base API 受理后升级：至少包括已开始但未完成的分析，以及
   已保存决定／已有待确认摘要继续分析和确认。先验证本条明确失败，再验证原 ID、
   pin、范围和请求历史保持，摘要生成、显式确认、同 Task 结果与重复请求回读。
   新请求已通过的同 Task 正向断言保留。
4. 保留当前兄弟项与原请求核对断言。改写后的
   `test_exact_repeat_resolves_across_the_full_preview_bound` 只重复当前 pending 请求，
   原“较早请求在兄弟工作之后仍可核对”的断言应在当前 Task 旅程继续覆盖；不以改成
   只读执行列表代替原提交回读。此项是当前覆盖要求，不另列未经复现的产品阻塞。

Developer 跑新增／修改测试和直接受影响的
`tests.test_media_discovery`、`tests.test_manual_task_engine`、
`tests.test_manual_operations_contract`、`tests.test_v2_manual_organize`；若改共享受理，
加跑 `tests.test_task_scheduling`、`tests.test_task_scheduling_fencing`、
`tests.test_task_source_ownership_race`。结构写入变化同时验证失败原子性。
完整 Python/Web/原生/wheel/Docker T4 仍由 B 在修正候选执行；不下放全量门禁。

#### 本轮实际验证与全部 Slice 结果重评

本地证据根：`.git/validation-evidence/6d4747be/task55-3-b/`。

| 验证 | 实际结果 |
|---|---|
| 当前 API contract／V2 旅程 | `tests.test_manual_operations_contract tests.test_v2_manual_organize`，48 tests OK，3.235秒；focused.log |
| 候选新 API 分析请求 | 201，1 项真实 Task，引擎能够领取推进，源／目标零变更；fresh-intent.log |
| Task Base 原 Worker 对照 | 正式 API 受理，原 Worker 生成 preview，源／目标零变更；base-control.log |
| Task Base → 候选原工作 | 原 intent 再分析201，仍无 Task／无摘要；base-pending.log |
| Slice Base → 候选原工作 | 相同断点，原 discoveryId 与 pin 保持；slice-base-pending.log |
| 治理／文档／whitespace | check_governance.py PASS；tests.test_governance 20 tests OK，6.410秒；git diff --check通过 |
| 当前候选完整 T4／原生／产物／Docker | 本轮未执行；已证实阻塞，按工作流提前 FIX REQUIRED，不能记 PASS |

Python ResourceWarning 保留在 focused.log，不影响48项通过，也不掩盖上述业务失败。
前轮完整门禁和原生组合失败保留在 Git 指向的报告及原证据目录，未删除或改成通过。

RO-1 保持55.1接受事实；RO-2 保持55.2与本Task已接受清理，新请求改为Task拥有，
合法存量分析的继续条件仍阻塞55.3，全局V1审核留在原后续边界。RO-3完整JSON权威／
管理员回落、RO-4其余旧flow／升级清理、RO-5其余session／协议均按原边界待后续；
本次存量断点属于55.3的AC-6，不能移到后续。RO-6仍欠最终候选完整安全／原生／
产物门禁。Slice55保持ACTIVE；SLICE／Roadmap／Progress不变，不声明Task或Slice PASS。

计时：已记录复核区间为2026-11-17 11:27:09–11:33:20（Asia/Shanghai），6分11秒；
48项测试墙钟3.41秒，治理20项6.410秒，四次真实入口短复现合计不足2秒，
包含治理短命令后按测试／验证不足15秒记录，小于本轮50%。
下一步 Developer 修正同一 B55.3-05 后交 B。

## Developer 修正交接 — 2026-11-17（B55.3-05）— READY FOR B REVIEW

```text
Task Base: b73c36353e5427cbe60fbb7c1b8cc85b139edca4
Source checkpoint: dfcf0284
Branch: main
Initial workspace: clean (tracked/untracked), governance PASS
B findings addressed: B55.3-05 (P1)
```

本轮只修正 B55.3-05 的合法存量整理继续条件，未改 Base／Goal／Scope／验收，
未恢复独立 discovery/execution Worker、全局领取或数据转换工具。

**根因与修正**

- 根因：候选的 intent 分析入口找到改造前已受理的 discovery 后，`pending` 分支
  直接回读原记录；该记录没有 `organize_task_id`，而当前 Task engine 只领取 Task
  scheduling 记录，摘要永远没有消费者。直接确认改造前已有摘要也会创建没有
  scheduling 的 Task，同样无人执行。
- `begin_intent_analysis` 与既有冻结分析/重分析入口现在区分“已有内核 Task”和
  “改造前无 Task 分析”。对后者，新增
  `SQLiteTaskRepository.adopt_files_organize_work` 在一个 `BEGIN IMMEDIATE` 中提交
  Task、scheduling、display 与 discovery 的精确投影；原 discovery/intent ID、pin、
  digest、范围、来源、已保存决定和旧摘要保持，旧 claim 字段清空，由当前引擎按原
  discovery 身份领取。
- 已开始未完成的分析保持原记录并补 Task；已保存决定或已有待确认摘要经原 intent
  分析入口重新进入时，仍由同一 discovery 生成新摘要并确认。
- 改造前仍为 current 的待确认摘要可直接确认：新的 summary adoption 在既有精确
  admission 之前，为该项旧工作建立同一 Task，并将摘要中每个来源投影为独立
  TaskItem（ready 为 waiting_confirm，四类问题保留对应等待态，技术失败保留失败），
  确认只登记被选中的执行工作；未选兄弟保持独立等待，不重放、不合并。
- 并发/丢响应：两个继续请求由 `BEGIN IMMEDIATE` 串行化，输家回读同一 discovery
  和 Task；不会产生第二个 Task/discovery。容量满返回既有 `capacity_full`，不写
  Task、item 或 discovery 链接。

**实际验证（仓库根目录；最终源码候选 dfcf0284）**

- `python3 scripts/check_governance.py` → PASS；`git diff --check` → 通过；
  `compileall -q mediaflow tests` → 通过；
  `ruff format --check mediaflow tests/test_v2_manual_organize.py
  tests/test_task_persistence.py` → 165 files already formatted；
  `ruff check mediaflow tests/test_v2_manual_organize.py
  tests/test_task_persistence.py` → PASS。
- Task 指定 affected 15 模块（含 `test_media_discovery`、`test_task_persistence`）：
  `.venv/bin/python -m unittest tests.test_execution_authorization
  tests.test_manual_task_engine tests.test_automation_task_admission
  tests.test_task_scheduling tests.test_task_scheduling_fencing
  tests.test_automation_entrance_recovery tests.test_v2_manual_organize
  tests.test_operations_task_center tests.test_task_item_metadata_search
  tests.test_task_source_ownership_race tests.test_manual_operations
  tests.test_manual_operations_contract tests.test_processing_worker_readiness
  tests.test_media_discovery tests.test_task_persistence`
  → **291 tests OK，16.300s，0 skipped**。
- 直接受影响服务：`tests.test_manual_organize_execution
  tests.test_manual_organize_preview tests.test_manual_organize_intent`
  → **60 tests OK，1.974s**。
- `tests.test_v2_manual_organize tests.test_media_discovery
  tests.test_manual_task_engine tests.test_manual_operations_contract`
  → **95 tests OK，11.823s**；新增旅程覆盖未完成分析补 Task、已保存决定/
  待确认摘要继续分析、直接确认旧摘要、同 discovery/同 Task、pin/范围保持、
  丢响应重复收敛、源/目标在分析阶段零变更及确认后的真实结果。
- 结构失败原子性：`tests.test_task_persistence.DiscoveryAdmissionIdentityTests.
  test_prechange_adoption_rolls_back_task_scheduling_and_items_together`
  → OK；重复 item identity 触发写失败后，Task、scheduling、item 与 discovery link
  均无残留。
- 未运行（仍属 B 的 T4 验收）：全量 Python/Web/Node E2E、原生 playwright、
  wheel／源码外安装、Docker 三项 smoke；本轮没有把未跑写成 PASS。

**剩余风险／交 B**

- 直接确认改造前摘要时，若旧摘要中的来源处于四类问题等待态，候选只投影相同的
  等待状态，不重建当时的 review/conflict 证据；需要新证据时可经原 intent 分析
  入口重新分析，Task 保持开放，不会自动重放或执行该来源。
- 已有 Task 行但缺少 scheduling 的混合旧形态仍不会被本修正接管；B 的真实 Base
  数据若出现该形态需在同一 Task 内进一步确认。
- 本轮未执行完整 T4／原生／产物／Docker 门禁，不能视为 Task 或 Slice PASS。

**计时**：本轮开发约 2026-11-17 11:36–12:01（Asia/Shanghai，约 25 分钟）；
测试与真实入口复现墙钟合计约 1 分钟，小于本轮 30%。

下一步：B 独立复审 Base..dfcf0284 与本文档检查点，按 T4 验收给出 PASS 或
SAME TASK FIX REQUIRED。
