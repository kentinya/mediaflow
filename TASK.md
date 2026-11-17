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

### Developer Completion Report / B Review Result

**Status: READY FOR B REVIEW（本检查点）**

Developer 已按 Task55.3 范围实施并提交本地候选检查点。源码身份以本提交 HEAD 为准，
Task Base 保持 `b73c36353e5427cbe60fbb7c1b8cc85b139edca4`。

改动摘要：

- 删除远程票据产品：CLI `execution-authorizations`、`POST /api/v1/tasks` 票据受理、
  `X-MediaFlow-Execution-Token`、`REMOTE_EXECUTE`、`api.remoteExecution` 运行权威、
  service/domain/repository CRUD 和新库 `execution_authorizations*` 表。历史文档中的
  `api.remoteExecution` 仍可读但被忽略；设置编辑按 `field_retired` 拒绝。
- 常驻 Worker 只装配 `ManualTaskEngineWorker` 与普通文件 runner；删除
  `media_discovery_worker.py`、`manual_organize_worker.py`、全局
  `claim_next_media_discovery`／`claim_next_manual_execution` 和 `task_scheduling_enabled`
  回落。发现/执行服务仍由 Task 内核按精确记录 claim、续租和 fence 调用。
- 旧恢复链退出：删除独立 authorize/execute、`manual-recovery-links`、`continue-batch`、
  `recovery-batches`、`remaining-scope-previews` 及不再存在的 `metadata-correction-continuation`
  退休 410 表面；新库不再创建 link/batch 表。保留自动化同 Task preparation、Files native
  摘要、`prepare-summary`／`confirm` 和原 Task 摘要身份。
- Web 删除 batch/link 交互、旧 API 客户端与 `recovery-batch-session`；保留四类逐项恢复、
  当前摘要确认和 Task Center 读取。设置消费者移除远程执行字段。
- 同步 README、示例配置、部署/harness/wheel smoke 与相关入口断言；删除仅覆盖旧正向
  路径的测试（含旧 ticket/Worker 轮次），保留并接回当前 Task 内核断言。

实际验证（仓库根目录，本轮）：

- `python3 scripts/check_governance.py` → PASS。
- `ruff check .` → PASS；`ruff format --check .` → PASS；`compileall mediaflow tests scripts` → PASS。
- 全量 Python：`.venv/bin/python -m unittest discover -s tests` → **2373 tests OK（7 skipped）**。
- 指定 affected suite → **258 tests OK**。
- Web：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` → PASS；
  `npm run test -- run` → **103 files / 1642 tests PASS**。
- Playwright `operations-inventory.python.spec.ts` 指定的五个 native recovery 场景 → **5 passed**。
- `config/strategy.example.json`、`config/mediaflow.phase13.2.example.json` JSON 与 CLI config
  validate 路径保持可用；新库不存在票据/旧 link/batch 表。

剩余工作／风险（交 B）：

- B 仍需执行完整 T4 验收、其余 E2E 文件、wheel／源码外安装和三项 Docker smoke（Developer
  本轮未把它们当作 affected gates 运行）。
- `application/scope_continuation.py` 保留只读的既有恢复资格校验以保护现存 V2 历史记录；
  其创建、领取、批量执行和专用入口已删除。B 需判断是否还需进一步收敛该只读面。
- 架构／迁移说明中仍可能有历史票据描述；本 Task 未改写 A-owned 的 CURRENT/TARGET 叙述，
  由 B 验收时核对并交 A 做最终文档 reconciliation。
- 删除了仅验证已退役独立 Worker/旧恢复链的测试文件与方法；当前 Task 内核、Files、自动化
  due/Run once、四类恢复和普通文件覆盖由保留测试与全量回归承接。

下一步由 B 独立审查 Base..本候选，给出 PASS 或 SAME TASK FIX REQUIRED。

### B independent review — FIX REQUIRED（2026-11-17，产品候选8a8e7d38）

完整范围：`b73c36353e5427cbe60fbb7c1b8cc85b139edca4..7abc055d16c929016dc24b26eb11ccb4133a7b75`。
Developer 产品候选为 `8a8e7d38d53f84a832bf7c5bacfee1f7495412eb`；其后四个文件仅为 B
在验收过程中对当前测试消费者的校正，详见下文。产品源码／Web src／配置／依赖未变，
原 Base、Goal、Scope、High/T4 不变。现场 main、初始工作区干净、治理 PASS。
本轮没有改变 SLICE／Roadmap／Progress，也不是 A 的 Slice 终审。

前轮判断、原失败及指导保留在
[49328b64:TASK.md](https://github.com/kentinya/mediaflow/blob/49328b64a3d73ce326e437fc6c06f7bf15c4c723/TASK.md)。
当前结论：**B55.3-01–04 的已列修正通过；SAME TASK FIX REQUIRED，阻塞为 B55.3-05。**

#### 已完成的两项修正

- **B55.3-04 已修正。** 当前哈希输入保留稳定 null 承诺，旧传输／模型不恢复。用
  Task Base 真代码在现有 Run once API 中受理、保存识别决定并分析出原摘要，候选
  打开同一库后，checkpoint 与原摘要完全一致；原确认202，候选 Task Worker完成
  同一Task，重复确认202回读同一 execution，只留一条SUCCESS Result，原pin保持。
- **B55.3-02 已修正。** 新库不再安装两旧列，现存有效V2摘要做本单元所需的最小
  表结构收敛。对 Base 真代码生成的库，在DROP之后、rename之前注入SQLite失败，
  原表定义和全部摘要行完整回滚；正常再次打开、确认、执行和重复确认通过。
  旧历史表没有为清理而删除；本轮未扩展到其他旧schema／flow。
- Slice Base真源码也通过同一旅程：在最初发布前使用正常V2配置（旧schedules空槽、
  当前定义），候选继续原库的摘要与pin并执行成功。最初直接沿Base示例携带两条已
  退役非空旧schedule的尝试被准确拒绝，原日志保留；未把这类纯旧输入当成当前V2
  连续使用失败，也没有修改已发布历史配置。

证据在 `.git/validation-evidence/8a8e7d38/task55-3-b/` 的
`base-summary-atomicity.log`、`base-summary-candidate-completion.log`、
`slice-base-current-v2-summary.log`。首次旧诊断脚本在候选受理202后仍让Base代码
回读收敛后的表，旧reader报错；后续验证由候选Worker完成，未将旧代码回退当成支持义务。

#### B55.3-05 / P1 — 正式API仍受理无Task的分析，常驻Worker不会处理

**完整操作与实际结果：** 操作者通过现有资源库文件整理API提交
`Movies/One.2001.mkv` → 返回intent → 请求该intent的方案 → API返回“resident Worker
正在分析” → 常驻Task Worker无可领取工作，读取仍停在analyzing，没有方案可确认。
Docker安全验收中的真实C类型／A命名分类检查也在同一请求链等不到分析结果。

已有入口、正常权限和配置下，在临时Local根／真实API／SQLite复现：

1. `POST /api/v1/resource-libraries/library/files/organize`，正常`paths` → **201**。
2. `POST /api/v1/operations/organize/intents/{原intentId}/previews`，发送返回的
   `expectedVersion` → **201**，返回`analysis.phase=analyzing`、`previewId=null`。
3. 真实`ManualTaskEngineWorker.run_next()` → **None**。持久记录的
   `organize_task_id=None`，**Task总数0**；源／目标Storage变更均为空。
4. Task Base相同真实入口由当时生产装配的`MediaDiscoveryWorker`领取后，变成
   **completed并产生preview**，同样零媒体变更。

**原因与范围：** `service_api.py:5558` 的Files API仍只创建intent，随后
`MediaDiscoveryService.begin_intent_analysis`在无关联discovery时调用
`_admit_intent_analysis`（2538–2640），直接`create_media_discovery`，没有Task受理与
scheduling。原独立Worker删除后，该写入分支与“正在处理”响应没有收敛。问题由初始
实施`6d48fbdf`删除消费者时留下，8a8e7d38的摘要／结构修正本身已通过。
这是现存正式入口可触发的停滞，不是构造旧链记录或探测猜测地址；对应AC-3/5/7/8及
本Task“只有Task内核受理／执行”和真实消费者一致性。

**Developer 指导：**

1. 沿上述两个已注册入口核对首次Files受理与intent再次分析，将这条现行整理行为接回
   已有Task受理、discovery／intent关联和Task engine；同一次工作具有真实Task身份、
   原pin／范围／选择和共享额度／来源所有权。当前Files弹窗的原Task重分析继续复用它。
2. 收敛 `_admit_intent_analysis` 的无Task写入及相关真实消费者；保留当前零变更分析、
   精确方案、独立确认与结果职责。当前合法已存intent／摘要的ID、决定、pin和请求关联
   保持可继续。由当前Task claim驱动发现／分析／发布，不重新引入独立领取包装。
3. `tests.test_manual_operations_contract` 的当前正向旅程正在用
   `tests.task_engine_test_helpers.claim_and_run`直接领取discovery，绕开生产Task
   调度，因而全量通过没有暴露此问题。将这条API旅程接回真实Task engine，保留原
   成功／权限／脱敏／精确确认断言。同步Docker安全脚本中的同一真实消费者。
4. 在现有夹具中覆盖API受理→真实Task领取→计划／真实未就绪原因→精确确认→同Task
   结果；直接受影响的重复请求、已保存决定、满额、权限／来源变化与原pin断言保持。
   本次短复现和Docker安全超时是修正前的明确失败依据，先跑它们对应的affected cases。

Developer运行新增／修改及上述直接受影响测试，含`tests.test_manual_operations_contract`、
`tests.test_media_discovery`、`tests.test_manual_task_engine`、`tests.test_v2_manual_organize`；
若改变共享受理，再跑原Task对应受理／容量／来源竞争模块。完整T4与环境验收由B承担。
本轮返工仅此链路，不规划下一Task，不扩展队列／页面／治理工具。

#### B验收实绩与保留失败

完整日志、源码归档、raw trace、产物身份和短复现均在上述本地忽略目录，不声称远程可达。

| 门禁／复核 | 实际结果 |
|---|---|
| Developer候选affected复核 | 139 tests OK，11.891秒；focused.log |
| Python full | 2386 tests OK，7 skipped，265.044秒；python-full.log |
| Web质量／全量／构建 | typecheck、lint、format、build通过；103文件／1636 tests通过，161.59秒 |
| Node完整E2E | 285 passed，3.5分钟；node-e2e.log |
| 真实Automation Run once／workspace | 17 passed，29.5秒；native-automation.log |
| 原生组合：operations／manual-dialog／source-history／metadata-year／flow | 55 passed、6 failed，3.0分钟；native-operations.log及原始trace保留 |
| 原生组合：settings／operations／flow | 51 passed、17 failed，3.0分钟；settings18项通过，其余失败未记PASS，见native-current-consumers.log |
| 校正后的polling／终态通知消费者 | 2 passed，2.8秒；native-consumer-focused.log；不代替整套原生通过 |
| Python质量／依赖／示例 | Ruff format／check、compileall、pip check、两example validate通过；FFmpeg／FFprobe检索无匹配（预期exit1） |
| 干净来源wheel／源码外安装 | 构建通过；旧prepare_summary断言失败后由B接当前消费者，源码外smoke通过；原失败wheel-smoke.log保留 |
| 候选四服务Docker | 启动／API重启通过；Worker／Scheduler／Notification重启／未知效果证据通过；docker-smoke-visible-mount.log、docker-restart.log |
| Docker安全 | 初轮viewer旧票据403断言已由B接为404；后续真实intent分析在120秒超时，属B55.3-05，未通过 |
| Base连续使用／结构失败原子 | 上文原摘要确认／执行／重复／pin保持及DROP后失败回滚通过；其他Base数据完整组合门禁仍待最终修正候选 |

7项跳过仍为既有真实外部服务／耐久环境未配置；临时媒体、fake Provider／本地服务使用
范围不变。ResourceWarning、JSDOM scrollTo、Vite chunk提示保留在日志，不抹去失败。
视觉／其余原生／最终Docker安全仍待B，已证实阻塞后不继续扩跑，也不把验收环境工作
当成额外产品返工。原生组合中读取／计数／关联失败由B在各自独立harness继续定位；
settings会发布Active／容量，本轮同实例组合不能用来单独认定新的产品故障。

B本轮只校正了验收消费者四文件：wheel检查当前native summary，Docker未知路由，
原生E2E的当前`?run=`链接、精确rich-row和明确queued fixture。提交见
`1e3155a5`、`190f7082`、`6aa74cc0`、`7abc055d`。polling fixture结束时正常取消自己受理
的Task；原始失败与后续两项通过都保留。没有修改生产逻辑、弱化版本／权限／效果断言，
没有把Docker后续超时改成通过。本轮不自批这些变化为Task PASS。

产物核对：wheel SHA-256
`97707fed229fed1f86b2c334e29c0f1bd0b499afe1f769e9699db2776b5cb4ec`；镜像
`mediaflow:task55.3-b-8a8e7d38`，ID
`sha256:c88d13106db783e802cfcab693a40e4ff3daf01e85fcff2e6e2cfa6f71b7abd7`。
163个包内Python文件在wheel、镜像与当前生产源码逐字节一致，见artifact-identity.json。
完整回归输入复用边界：8a8e7d38..7abc055d仅上述验收消费者，mediaflow／Web src／
unit tests／配置／依赖树完全相同；原全量结果不声称已覆盖后续native脚本修正。
Docker通过既有Colima专用上下文与已有可见挂载下的新隔离子目录运行，未操作现有部署。
首次默认socket不可用、第一次临时目录不在VM挂载内的失败也保留，后续使用已存在的
`colima-mediaflow-review`和可见根，没有改变全局Docker上下文。

计时：2026-11-17 09:09:55–09:35:58（Asia/Shanghai），已记录复核26分03秒；
验证／构建日志区间合并725.804秒，计入短命令按12.3分钟记录，小于本轮50%，
见timing.json。文档检查：治理PASS、8 tests OK（0.022秒）、git diff --check通过。

#### 全部Slice结果重评

RO-1沿用55.1已接受入口退休；RO-2沿用55.2 schedules/grant与本55.3已完成票据／
旧Worker／旧恢复链清理，但B55.3-05表明当前受理仍有非Task路径，全局V1审核仍按原
后续边界。RO-3的完整JSON运行权威／tokenEnv管理员回落仍在；RO-4全局旧flow／升级
清理仍未完成，本次仅完成当前摘要结构与安全收敛；RO-5旧Run once／Copy session与
其余协议承接仍待后续；RO-6本单元仍欠真实安全旅程与完整原生门禁。未提前协调CURRENT
或关闭Slice。**Slice55保持ACTIVE；下一步Developer修正同Task的B55.3-05后交B。**


## Developer 修正交接 — 2026-11-17（B55.3-05）— READY FOR B REVIEW

```text
Task Base: b73c36353e5427cbe60fbb7c1b8cc85b139edca4
Fix checkpoint: 70410601f1462610400c60bae749884f9f5360f7
Branch: main
Initial workspace: clean (tracked/untracked), governance PASS
B findings addressed: B55.3-05 (P1)
```

本轮只修正 B55.3-05 的现行整理受理链路，未改 Base／Goal／Scope／验收，未扩队列、
页面或治理工具。

**根因与修正**

- 根因：`MediaDiscoveryService._admit_intent_analysis` 仍用
  `create_media_discovery` 直写没有 Task 的 discovery；独立 discovery/execution
  Worker 退出后，这条正式入口无人领取，plan 永远不出现。
- 首次 Files 受理（`POST /resource-libraries/{id}/files/organize`）保持既有契约：
  只建 durable intent，不建 Task／Preview。intent 的页面分析入口
  (`POST /operations/organize/intents/{id}/previews`) 现在把该 intent 已解析的精确
  来源作为一项真实 organizing Task，经 `create_files_organize_work` 原子受理：
  intent 原 pin、范围、display、共享容量和逐来源预留与冻结 discovery 同一提交。
  常驻 Task engine 用真实 claim／心跳／fence 调用 `_analyze` 并发布精确 plan，
  Task 进入人工等待；确认时既有 `_adopted_organize_task` 采用同一 Task 执行。
- 并发／丢响应：同 intent 的并发分析请求由先提交者胜出，重复请求收敛到同一
  discovery／Task；另一未结工作持有的来源按 `owned_source_refusal` 拒绝并给出既有
  工作引用；共享额度满返回 `capacity_full`，不建 Task。
- 重分析 requeue 与受理共用有界的 pinned-runtime 回退（preview 服务持有的 pin），
  组合装配仍能重新登记同一 Task 的分析。
- 测试消费者：contract 旅程改为真实 `ManualTaskEngineWorker` 领取并断言确认后的
  execution／完成结果就是该分析 Task；V2 旅程所有 intent 分析改用真实引擎，新增
  丢响应重复受理、worker 缺失时 Task 保持 queued 且无伪造 plan、真实发布的 pending
  conflict decision 解析；Docker release security 增加“analysis→execution→
  completion 同一 Task”断言。Web fixture 随真实文档重新生成（preview 的
  `organizeFlow` 由 null 变为真实 Task）；未改 Web src。

**实际验证（仓库根目录；均为最终候选）**

- `python3 scripts/check_governance.py` → PASS。
- `ruff check mediaflow tests scripts` → PASS；`ruff format --check mediaflow tests
  scripts` → 345 files already formatted；`compileall -q mediaflow tests scripts` → PASS。
- affected 18 模块（Task 指定清单 + `test_media_discovery*` / 自动化现有消费者）：
  `.venv/bin/python -m unittest tests.test_execution_authorization
  tests.test_manual_task_engine tests.test_automation_task_admission
  tests.test_task_scheduling tests.test_task_scheduling_fencing
  tests.test_automation_entrance_recovery tests.test_v2_manual_organize
  tests.test_operations_task_center tests.test_task_item_metadata_search
  tests.test_task_source_ownership_race tests.test_manual_operations
  tests.test_manual_operations_contract tests.test_processing_worker_readiness
  tests.test_media_discovery tests.test_media_discovery_provider_manifest
  tests.test_v2_automation_operations tests.test_v2_automation_run_once
  tests.test_manual_organize_preview` → **344 tests OK，28.584s，0 skipped**。
- Web（`web/`）fixture 消费者：`npm run test -- run
  src/entities/operations/manual-actions.test.ts
  src/entities/operations/manual-operations-contract.test.ts
  src/features/operations/OrganizePlanConfirmation.test.tsx
  src/features/operations/OrganizeRouter.test.tsx
  src/features/operations/RunDetailTabs.test.tsx
  src/features/operations/ManualOrganizeDialog.test.tsx
  src/features/operations/TaskItemRecoveryPanel.test.tsx`
  → **7 files / 107 tests PASS，22.93s**。
- 未运行（仍属 B 的 T4 验收）：全量 Python/Web/Node E2E、原生 playwright、
  wheel／源码外安装、Docker 三项 smoke（含本轮加入断言但未实际运行的
  `docker_release_security_smoke_test.py`）。本轮没有把未跑写成 PASS。

**剩余风险／交 B**

- 存量**无 Task 的 discovery** 仍没有 Task claim 消费者；本 Task 按边界不实施数据
  转换，正常 V2 已存摘要／intent 的原 ID、pin、确认与结果保持可继续。
- 同一来源被另一未结工作持有时，intent 分析现在 409 拒绝（真实来源所有权），与旧
  无 Task 分析不同；B 需在真实 Files 旅程确认提示与下一步。
- 多文件 intent 的逐项确认遵守 Task 单执行槽：每次执行完成后需重新分析剩余范围再
  确认（与既有 Files 准备语义一致）；`test_exact_repeat_resolves_across_the_full_preview_bound`
  已按该语义改写，重复提交解析、逐项唯一执行与既有权限／脱敏断言保留。
- 架构／迁移文档的 CURRENT/TARGET reconciliation 仍待 B/A 收口。
- 本轮未执行 Docker／原生完整门禁，不能视为通过。

**计时**：本轮约 09:37–10:17（Asia/Shanghai，约 40 分钟）；测试墙钟合计约 3 分钟
（含早期失败运行，约 7%），小于本轮 30%。

下一步：B 独立审查 Base..本候选并按 T4 验收给出 PASS 或 SAME TASK FIX REQUIRED。
