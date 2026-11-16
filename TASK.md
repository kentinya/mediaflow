# Task55.3 — 整理受理、执行与续作只由当前 Task 内核拥有

Next Action: DEVELOPER STARTS TASK55.3 IMPLEMENTATION。

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
Status: PLANNED
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
   安装 smoke 和测试。新输入含 api.remoteExecution 按废弃参数拒绝，不静默忽略。
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
  当前 GET /tasks、direct CLI organize／分析和 Web 工作正常。
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

尚未实施，无候选 SHA、无本 Task PASS/FIX REQUIRED。Developer 按模板提交不可变
READY FOR B REVIEW 检查点、改动、实际 affected tests、剩余工作／风险；B 独立审查
完整 Base..Head 并完成验收后给出 PASS 或 SAME TASK FIX REQUIRED。
