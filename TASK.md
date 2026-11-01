# Task 47.4 — 独立 Job 系统退出与 Task 管理闭环

Task47.3 已由 B 验收 PASS；记录在 `383d8834787674675183f4b251d9dfd26a5dc511:TASK.md`，
接受候选为 `a0f09afefac2a85a70aca43c4cfbe1e36e04f1de`，原 Base 不变。
用户本轮明确授权按此草案实施并交 B 审查；本文件原地激活该 Task，不重定 Base，
不派生代理、不 push、不部署、不宣告 Slice PASS / CLOSED。

Authority: committed [SLICE.md](SLICE.md), RO-1/2/4/5、AC-4/11/12–18；
[Development Workflow](docs/development-workflow.md) 是生命周期、测试和收尾依据。
用户已明确**没有旧任务、不考虑升级**，此指令覆盖引用合同中的旧任务迁移、跨版本
升级/历史兼容要求；保留本版本 fresh、新任务和同版本 reopen/restart 的安全义务。
B 不改 A-owned Slice/Roadmap/Progress，不自行宣告 Slice PASS / CLOSED。

用户补充边界（2026-11-02）：**V1 已不受支持**。本 Task 只以当前 V2 用户旅程、
仍被 V2 消费的共享 API/CLI/运行时和安全能力验收；V1 独有页面/行为不作为门禁或返工
要求。下文旧 V1 保留措辞依此收窄；不要求恢复旧产品或旧 Job 兼容。

```text
Task ID: 47.4
Task Type: SLICE
Parent Slice: 47
Status: FIX REQUIRED
Task Base: 383d8834787674675183f4b251d9dfd26a5dc511
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation authorization: USER-AUTHORIZED — SAME TASK CORRECTION REQUIRED
```

## Preflight / accepted baseline

仓库 `/Users/songzhidong/mediaflow`，branch `main`，规划起点为上述完整 Base；governance
preflight PASS，workspace/Git 可写。无预存 tracked 修改；预存 OS/log/参考图片、`15`、
`output/database-reference-2026-11-01/`、`output/organize-flow-2026-11-01.html` 与 imagegen
ZIP 保留且不暂存。不读用户数据库、
媒体或秘密配置。本轮由 Developer 按用户授权实施生产、测试与前端；A-owned Slice/Roadmap/Progress 不变。

Task47.3 已接受：新 Files/due/Run once/direct CLI/batch/remote organizing 共享 Task
admission/claim/fence/管线；四类恢复留在原 Task；原 Automation 结果/时间冻结；正常
安全失败可由 retry-failed 明确重试，效果不明的文件被拒绝且保留原占用/证据。
retry-request、Pause/resume、Scan/Preview/FileIndex 均不恢复。

## Goal / complete journey

完成 Slice47 尚未交付的独立 Job model/schema/queue/API/CLI/Web 退出。部署到空目录后，
用户从 Files、Automation、受限 remote API 或 CLI 发起整理，只看到同一整理 Task 的
排队、进度、原记录、文件结果和允许操作；管理者通过 Task 查看/取消，四类恢复按既有
决定→分析→摘要→明确继续执行。系统、设置、通知、日志和导出不再依靠 Job 行。

成功：所有新整理由现有 Task engine 负责；数据库及可安装产物没有独立 Job 存储/Worker/
执行入口，现有合法能力由 Task 或原有分析/准备能力完成。失败：RBAC/票据/队满/源变更/
配置不可用/未知效果仍说明阶段、保留状态、已知效果和具体下一步；读取或修正不自动执行。
不要求用户管理内部 claim/token/revision，也不要求先登记 pending。旧 Job 输入使用正常
参数错误/not-found 边界，不能自动变成新的整理或执行授权。

## Actual-code gap / dependency map

以下均来自 Base 真实代码；是依赖地图，不是逐文件拆 Task 或实施清单上限。

| 真实位置 | 当前残留与本 Task 的结果 |
|---|---|
| `domain/automation.py`、`application/automation.py` | 仍有 AutomationJob/Status/Repository、AutomationJobService/AutomationWorker。只删 Job 专属对象/队列，保留 Definition/Schedule/Occurrence、到期规则及共享异常/能力。 |
| `final_cli.py::_run_worker/_run_queued_workflow` | resident 仍组合旧 Job Worker，保留 Job→CLI dispatch；应由现有 Task consumer 承担合法工作，普通文件/通知 resident 继续可用。 |
| `metadata_correction_continuation.py`、`recovery_continuation.py`、`recovery_batch.py`、`scope_continuation.py` | 有实际创建 AutomationJob 的恢复分支、job_id 关系或已退役 pause scope 专属代码；不能只删主提交而留下恢复 Job writer。共享决定/请求/摘要/审计仍保留。 |
| `sqlite_runtime.py`（schema57） | automation_jobs 和索引仍存在，共享容量仍加 legacy Job count；schedule/occurrence、票据/audit、continuation/batch、logs 等仍有 Job 列/FK。部分 last_job_id/consumed_job_id 已实际装 Task ID，应切换为真正 Task 关系，不能换个 Job 表名。 |
| `service_api.py` | `/api/v1/jobs` 及 operations alias 仍提供 list/detail/stale/submit/cancel/requeue；remote organize 虽创建 Task，公开入口仍叫 jobs。Task cancel 实际仍校验 CANCEL_JOB 权限，不能删枚举后顺便丢掉鉴权。 |
| `web/src/entities/operations/job.ts`、`api-client.ts`、`LegacyTaskRoutes.tsx`、Dashboard/navigation | 仍有 Job model/query/归属查找/链接，run/detail/recovery 文档也含 Job 分支；需要让受支持的当前页面只消费 Task。 |
| `interfaces/operator_ui.py`、logging / authorization / notification | V1 页仍有 Job 导航/提交/陈旧队列按钮，日志和消费记录仍带 Job identity；只改依赖部分，保留同等管理、审计、通知能力，不做 V1 整体改版。 |

适用要求：V2-TASK-001–003/005–007、V2-OPS-014–017、V2-AUTO-010/011，REQ-TASK/
SCHED/API/RESULT/SAFE/DEPLOY 的适用条款；完整旅程见 Product Experience 的 TARGET、
Manual organize、Tasks/results/recovery、Scheduled/Automation、Operations administration。
Architecture 的 TARGET task identity/engine/query/removal 为本 Task 技术边界；旧 CURRENT
和旧 requirements 不能要求恢复被用户排除的升级或退役产品。

## Entry disposition / API contract

| 已有入口 | 本 Task 处置 |
|---|---|
| Files、Scheduler interval/Cron/managed due、Run once、organize/batch、retry-failed | 保留 Task47.3 已验行为及身份/权限/范围差异；继续 Task engine，零新 Job。 |
| `POST /api/v1/jobs` remote organize | 由 **`POST /api/v1/tasks`** 等价替代：只接受原已支持的 `{command:"organize", execute:true, limit:N}` 和原 HTTP execution-token header；REMOTE_EXECUTE、remote enabled、单次票据、TTL/limit、当前权限、容量/消费原子性全部保留。返回 202、taskId 与可读回 Task 地址，不接受泛化任意 command 或新增 destructive 参数。此 POST 是待实施替代入口，不能当作 Base 已存在入口去探测。 |
| GET Task/run/Automation/log/export/readiness | 继续使用现有入口，只读且 Task-authoritative；有界列表/计数/游标、原运行结果/时间、当前处理状态不丢、不重复。 |
| Task cancel API / CLI `jobs cancel` | 复用现有 `POST /api/v1/tasks/{id}/cancel` 和 TaskLifecycleService；补最小 **`tasks cancel <task-id>`** CLI 等价入口，命令内部读取版本后走相同后端核对。保留安全取消与旧角色的实际权限，不把原 CANCEL_JOB 保护直接删除；当前权限/前端能力改为准确 Task 含义，角色不扩权。 |
| item metadata-correction-continuation / recovery continue / batch | 核对真实来源与允许动作，支持的新整理四类继续回原 Task kernel；Metadata 别名若保留就验证原 review/version 后复用同一行为。已被 kernel 明确拒绝的 batch 不能为去 Job 而恢复。支持的管理分析能力仍零修改，不借机变成通用整理重试。 |
| Job stale/requeue 与 scope-continuation | 删除 Job 专属状态/命令/路由/dispatch；原限定的安全分析由既有 Task 允许动作完成。stale/timeout 不成为重新执行许可，不新增通用 requeue-stale、Pause/resume 或技术故障恢复。 |
| `jobs` CLI 整组、`/api/v1/jobs[/...]`、`/api/v1/operations/jobs[/...]` | 从 parser/help/route/dispatcher 删除，普通认证/参数错误或 not-found，零受理/授权消耗/Provider/Storage 效果。不保留 hidden executor/alias 或自动转成 Task；同步实际调用者与文档。 |
| Web/V1 Job collection/detail/导航/按钮 | 移除其 model/query/注册及实际调用；已有 Task/Automation/Files 入口继续完整。旧 Job URL 普通有界不可用即可，不新建历史映射或兼容页面，不凭旧 ID/名称/时间猜 Task。 |

## Implementation Scope

1. **沿真实调用者确定替代，再删 Job writer。** 从上表及已有 schema/日志/票据/通知
   引用完成生产调用核对，逐项说明“转 Task / 复用只读分析准备 / 退役拒绝”。复用
   TaskSchedulingService、ManualTaskEngineWorker、现有 automatic/manual 管线与
   OrganizerExecutor；清掉所有 new Job admission、claim/heartbeat/control、Job→CLI
   bridge 和恢复回落。Task/TaskItem/Result/必要 attempt/摘要是证据，不能新增另一套
   带独立 queue/claim/lifecycle 的“run”表替代 Job。
2. **打通等价 remote / cancel 及恢复。** 按上述明确接口更换 API/client/CLI；remote
   票据准入仍事务内绑定 Task 与消费/audit，队满/非法重复无半条关系。取消是请求→安全
   边界确认，不能中断在途 Storage 或抹掉成功。可执行/分析-only 身份和 Task Center
   人口保持；只分析失败的管理能力不因为去 Job 获得执行权，不另造技术恢复 UI。
   四类继续保留原 Task/source/version/pin/decision/attempt/result 和精确确认，不新建
   顶层 Task；独立合法 retry-failed 保留已验安全检查与结果关系。
3. **形成 fresh Job-free 布局与真实 Task 关系。** 移除 automation_jobs/table/index/FK、
   Job repository/model 与冗余 Job-only 列，将 occurrence/due、消费/audit、logs、
   continuation/batch 的仍需关系绑定真实 Task/TaskItem/Result。只有证据作用的
   continuation/preparation 可以保留，不能继续拥有竞争队列或再 mint Job/child work。
   共享容量只数 distinct admitted Tasks，schema marker 与实际结构一致，初始化失败原子。
   不设计旧 schema→新 schema 迁移，不运行数据清理/drop 用户库、不补旧 pending。
   只验证空目录 fresh 和本版本产生数据后的 reopen/restart；不兼容布局沿既有版本检查
   失败关闭，不能为了跑旧测试重建 Job 或自动清数据库。
4. **消除查询、设置、通知和 Web 的 Job 依赖。** 改正 SQL joins/unions、run lifecycle、
   Dashboard、八视图/Attention、Automation records/metrics/latest、readiness/settings
   resident、日志/export/audit，使读取无需 Job 表也完整。原阶段 outcome/实际时间冻结
   不变，四类恢复成功不改写原记录。适配 V2 及必要 V1 调用者、URL/model/normalizer；
   仅移除 Job 专属表面，不重做页面。通知用 Task 事实保持原触发/去重和独立投递，不
   依赖已删 Job，也不双发同一业务结果或改变投递重试的作用范围。
5. **保留共享协议，删除专属实现。** Automation definitions/schedules/occurrence、
   Storage/Provider、普通文件/通知 runner、已发表 immutable snapshot/JSON/digest
   不能随 Job 模块整文件误删。现有 maximumActiveJobs/staleJobAgeSeconds 等配置如需
   保持支持，可作为有界解析别名映射 Task 语义；不得改写历史快照或要求用户手工改内部
   pin。必要的旧配置/通知事件字面值不等于 Job 系统，可在保持已支持协议所必需时保留
   有界映射，但须写明用途，不能留 Job identity/store/writer 或双队列。不要机械要求
   全仓库连文档历史中的 `job` 字符都为零。
6. **同步受影响测试、产物和使用说明。** Job-only 测试改为退役拒绝或等价 Task 行为，
   shared recovery/pins/authority/notification/storage 断言保留；不用伪造 legacy Job
   fixture 证明本轮新能力。更新 approved examples、API/CLI/config/deployment 的受影响
   说明和 harness/smoke consumers。新结果做必要设计事实说明；全部 CURRENT/TARGET
   最终对齐与 Slice/Roadmap/Progress 关闭仍交 A，不在此 Task 提前宣告。

## Developer guidance — 具体文件、实施顺序和收口

### 先明确要交付什么

一句话：**拆掉还在使用的 Job 系统，把挂在它上面的能力接到现有 Task；用户照常提交、
查看、取消和处理问题。** Task47.3 已把新整理接入 Task，不能再写一套 Task 引擎。

范围大是因为模型、SQL、Worker 和页面相互引用，不按层拆成多个 Task。范围只到 Job
退出所必需的改动：不重写全库、整个 Worker、整个 API 或页面；remote Task POST 和
CLI Task cancel 是原能力的等价承接，不扩展成任意命令提交/通用任务控制平台。
没有旧任务，不做升级、数据搬迁或兼容执行层。本节不改变草案状态或授权开始实施。

### 文件地图：改哪些部分，不是整文件删除

下表 Python 路径统一相对于 `mediaflow/`；同一单元格内省略前缀的文件与前一文件同目录。
主要文件已有实际引用；“按引用联动”只在改动确实影响该消费者时修改，不为凑文件清单
扩大范围。最终以真实调用者闭环为准。

| 类别 | 主要文件 | 具体处理 |
|---|---|---|
| Job 模型与存储 | `domain/automation.py`、`domain/operations_run.py`、`infrastructure/sqlite_runtime.py` | 删除独立 Job 对象/状态/port/表/索引/FK/union；保留 Definition/Schedule/Occurrence、Task/TaskItem/Result 和必须的证据表。已有 Task ID 装在 Job 列中的关系改成准确 Task 字段，不能改名保留第二个队列。 |
| 准入与 Worker/CLI | `application/automation.py`、`final_cli.py` | 删除 AutomationJobService/AutomationWorker 和 `_run_queued_workflow` Job→CLI 分发；现有 Task consumer 接管受支持工作；移除 jobs 命令组、补 tasks cancel，普通文件与通知 runner 保留。 |
| 自动化执行/读回 | `application/automation_run_once.py`、`automation_definition_execution.py`、`automation_definition_occurrence.py`、`unattended_execution.py` | 替换 Job 专属类型/查询/来源判断，保持 due/Run once 的权限差异、definition/pin 和原记录。不重做调度算法、业务管线或启用/运行一次交互。 |
| 恢复调用链 | `application/metadata_correction_continuation.py`、`recovery_continuation.py`、`recovery_batch.py`、`scope_continuation.py`；对应 `domain/metadata_correction.py`、`recovery_continuation.py`、`recovery_batch.py`、`scope_continuation.py` | 删除 Job producer/consumer/link 和已退役 scope 恢复专属实现；共享决定、checkpoint、摘要、审计继续留用。正常四类继续回同一 Task，不因旧代码叫 continuation 就恢复旧能力。 |
| API 与授权 | `interfaces/service_api.py`、`domain/security.py`、`application/execution_authorization.py`、`domain/execution_authorization.py` | 按入口合同换 remote POST、删除 Job API；票据消费/audit 直接绑定 Task；Task 取消权限与前端能力同步改名/映射，保持旧角色实际权限和后端检查。 |
| 前端数据与请求 | `web/src/entities/operations/job.ts`、`run.ts`、`run-detail.ts`、`run-once.ts`、`task-item-recovery.ts`；`web/src/shared/api/api-client.ts` | 删除 Job entity/query/normalizer 分支；运行、恢复、原记录读取真正 Task 文档，不能为旧 normalizer 继续拼一个 Job。对应单测按实际用户结果更新。 |
| 前端/V1 入口 | `web/src/features/operations/LegacyTaskRoutes.tsx`、`job-query.ts`、`web/src/features/dashboard/DashboardView.tsx`、`web/src/routes/router.tsx`、`web/src/shared/navigation/destination-model.ts`、`interfaces/operator_ui.py` | 去掉 Job 路由/导航/按钮/请求；旧 Job 输入普通不可用，现有 Task/Files/Automation 路径完整。只改相关控件与调用，不改整页布局或整个 V1。 |
| 按引用联动的共享部分 | `application/operations_lifecycle.py`、`processing_checkpoint.py`、`manual_recovery_continuation.py`、`domain/logging.py`、`infrastructure/operational_logging.py`；通知/设置和运行模型消费者 | 清理确有的 Job 投影/关联/日志参数；保留安全检查、独立投递、原阶段事实与 resident adoption。没受影响的通知/设置/Task kernel 不重写。 |

**容易漏掉的现成例子：** `AutomationRunOnceService._execution_view()` 现在即使拿到的是
新 Task，仍会 `return AutomationJob(...)` 来适配读模型。因此“没有新增 Job 行”还不够；
必须连这种包装一起退出。改完用真实 Run once 的提交/查询/刷新/同版本重启证明返回的
Task、definition、来源、状态和原结果仍准确，不能只替换类名或删掉字段断言。

### 建议实施顺序

1. **先固定对外合同和安全回归。** 使用上方 Entry disposition 中已指定的 remote
   POST、Task cancel、Job 退役处置；先补真实合法/拒绝用例，明确原权限、scope/limit、
   票据/容量原子边界。复用 Task47.3 的安全重试、来源占用、原记录和四类继续用例。
   不为实现去探测未授权的新路由/通用命令，也不另造依赖管理工具或测试平台。
2. **接生产者和消费者，清掉恢复回落。** 逐一改 Scheduler/Run once/remote/CLI/
   四类继续及管理分析的实际调用。使用已有 Task admission/consumer/pipeline；来源、
   固定配置、决定、attempt/result、claim 和效果证据仍属于原工作。临时适配只可用于
   同一改动中的调用切换，交付时不能残留 AutomationJob 包装或可调用的 Job 分发。
3. **把读侧和用户入口接好。** 改 API DTO、SQL 查询、normalizer、页面/V1 和审计/
   日志/通知消费者，保证不再读 Job 表也能显示、取消、查原记录和导出。原始运行结果与
   当前处理状态分开，成功后不改写原失败/时间；技术失败不进入新的第五类 Web 恢复。
   字段缺失不能伪造成功、把未知计数当 0 或悄悄省略不确定文件。
4. **再完成底层删除和 fresh 布局。** 删除不再需要的 Job model/port/service/DDL/
   索引/FK/专属关系；核对所有模块 import、SQL、新表写入和产物，而不只删 Web 按钮。
   保留共享定义/计划/摘要/证据；无独立 queue/claim 的读回结构可用，独立执行对象不能
   换名留下。只做空库初始化和本版本新数据 reopen，不编写旧任务升级/清库路径。
5. **沿用户旅程完成验证并交一个完整 checkpoint。** 用 fresh fixture 实际完成
   remote 提交→Worker→结果→查询、queued/running 取消、due/Run once、四类继续；再核对
   Job CLI/API 的实际拒绝、页面不发 Job 请求、fresh SQL 无 Job 依赖。边界失败保留
   原 Task/票据/来源/效果，不拿“队列已接入”代替文件执行与安全检查。实施中可以有
   正常检查点，最终交付必须连贯；不按这五步另建 Task 或自评 Slice 完成。

### 验证和交接怎么做

- Developer 先跑新增/修改及直接受影响测试，具体命令沿用下方 Required Tests；旧 Job
  专属测试转为退役拒绝/Task 等价能力，共享安全断言保留。失败项不靠删断言、改超时或
  自动 retry 变绿。不要求 Developer 重跑 B 的完整 Python/Web/E2E/发布矩阵。
- 交接简要列出：删除了哪些 Job producer/consumer/schema；remote/cancel/恢复/读回
  如何承接；保留的旧配置/事件字面值及理由；实际测试命令/结果/风险。不是要求编写
  额外治理报告。B 复核完整 Base..Head、所有 Slice 结果，并负责适用 T4/原生/打包门禁。
- 无旧任务/不考虑升级仍有效；不能把外部服务缺失、历史兼容探针或过程文档当成新产品
  返工理由。真正未完成的必要入口/安全/数据关系要如实写出，不缩小验收后称完成。

## Acceptance Criteria

- [ ] fresh SQLite 无 automation_jobs、Job 专属 index/FK、独立 Job id/queue/claim 表；
  仍需 occurrence/消费/审计/log/恢复关系是准确 Task 身份。新任务写入后 integrity/
  foreign_key_check、同版本 reopen/restart 保留关系、pins、原摘要、授权消费及不确定效果。
- [ ] 源码、clean wheel、容器无 AutomationJob/JobRepository/JobService/JobWorker 或
  专属 Job→CLI dispatch；没有改名的第二工作生命周期，无 callable Job writer。仅为
  支持配置/外部协议保留的字面值有明确说明与测试，不依赖 Job 存储。
- [ ] 真实 remote Task POST 完成授权→原子受理→Worker→独立文件效果→读回；无权限/
  remote disabled/缺 execute/票据失效或重复/越界/队满/坏 pin 均零扩大权限，拒绝不
  消耗票据或留孤儿；旧 jobs POST/alias 不再能受理。
- [ ] CLI Task cancel 与现有 API 一致：queued、运行中/在途、重复/陈旧版本、终端
  状态均遵守现有允许动作，成功 sibling 保留，未确认在途工作不提前释放容量/源占用。
  viewer 不因权限改名获得取消/执行权；CLI 无需用户搬运版本/claim。
- [ ] Job CLI/API/Web 专属入口实际退出，旧输入普通有界拒绝且零业务效果；页面没有
  仍发 jobs 请求的按钮/导航。Task 有效链接、details、records、logs/export 不依赖 Job；
  旧 ID 不被猜成新 Task。Retired Scan/Preview/FileIndex/Pause/resume/retry-request 不恢复。
- [ ] Files/due/disabled Run once/direct CLI/batch/retry-failed 的入口差异、原子幂等、
  filtering/attachments/完整遍历/limits/真实稳定性保持；只分析仍零修改且不混入整理人口。
- [ ] 四类分别完成同 Task 决定→分析→精确摘要→明确确认，成功/忽略/不确定 siblings
  独立，混合批次允许/拒绝逐项可读。没有旧恢复 Job 回落、重放已完成/不确定效果或刷新
  已消费授权；Task47.3 的安全重试和原子来源占用反例继续通过。
- [ ] eight-view Task Center/Attention、Automation definitions/records/metrics/latest、
  Files 本地普通操作、Dashboard、API/CLI/health/readiness/settings 的 count/filter/
  cursor/刷新/重连语义准确；原运行结果/实际时间不随恢复改写，一次原运行只计一次。
- [ ] 通知/outbox、授权/audit/log/JSON 以 Task 事实工作，零 secrets，投递失败不改媒体
  结果；普通文件 runner、resident 无 Active/缺依赖/重启/override/adoption 继续真实。
- [ ] Developer 交受影响证据；B 在完整 Base..Head 上完成适用 T4、原生/视觉、clean
  installed wheel/Docker fresh/restart/security 验收并重评所有 Slice 结果，才可 Task PASS。
  旧任务/跨版本升级不作为本 Task 门禁，不对用户库做试验。

## Required Tests

遵守 workflow 的测试分工。所有成功、非法输入、冲突、失败、重要边界来自已有入口或
本 Task 明确授权的替代入口；不探测猜出的路由或不支持的状态组合。每轮测试墙钟少于
本轮总用时 50%，记录耗时，优先关键复现，不能靠空等、删断言/放宽超时/加重试凑结果。

### Developer — affected tests

先在实际修改模块扩展新 route/取消/Job-free fresh/恢复/查询测试，再按改动运行现有组；
命令按 Base 现有文件列出，若移除或改名 Job 专属测试，同一次交接给出准确替代命令及
保留的行为断言。不是要求 Developer 跑全仓库/全 Web/发布矩阵。

```sh
.venv/bin/python -m unittest tests.test_automation_entrance_recovery \
  tests.test_execution_authorization tests.test_api_security \
  tests.test_operator_job_submission tests.test_operator_job_cancellation \
  tests.test_queued_job_execution_boundary

.venv/bin/python -m unittest tests.test_task_persistence \
  tests.test_task_scheduling tests.test_task_scheduling_fencing \
  tests.test_manual_task_engine tests.test_processing_recovery_admission \
  tests.test_recovery_continuation tests.test_recovery_batch tests.test_resident_correction

.venv/bin/python -m unittest tests.test_automation_definition_occurrence \
  tests.test_automation_workspace_read_model tests.test_operations_run_inventory \
  tests.test_operations_run_detail tests.test_operations_task_center \
  tests.test_processing_worker_readiness
```

改到对应分支时追加 `tests.test_notifications`、`tests.test_operational_logging`、
`tests.test_automation_settings_resident`、`tests.test_v2_automation_run_once`；只跑新/修改/
直接受影响组合。Python changed-file Ruff format/check、compileall、governance 和
`git diff --check` 必做。Web cwd `web/`：对修改文件跑 Prettier、相关 unit/normalizer/
API/router tests、typecheck/lint/build；只跑直接受影响原生 spec。fixtures 用临时根/
SQLite/fakes，不用用户生产 SMB/OpenList/S3/TMDB。

### B — independent acceptance / full regression

- 审完整 Task Base..candidate，重查所有实际 new Job writer/恢复/查询/控制/产物引用，
  完整入口表逐项有处置。负向搜索只是辅助，不能代替真实入口和文件效果/数据库证据。
- fresh 同库运行 Scheduler/due/Run once/Files/CLI/new remote 和 worker，验证真实 Task/
  item/result/occurrence/票据消费/log/outbox、并发/队满/取消/claim loss/源变更及 uncertain。
  从实际四类决定/确认和管理分析入口证明删除 Job 后仍闭环，不新增第五类恢复。
- 执行 [workflow shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)：
  full Python/static/examples/禁依赖、全 Web/unit/E2E、clean installed wheel 及 Docker
  fresh/restart/security。源码变更后的实际产物重建；不复用残留 build 缓存中的已删模块。
- build 后在隔离 fresh Python harness 运行现有原生：

  ```sh
  npm run test:e2e -- --config=playwright.python.automation.config.ts \
    tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
  npm run test:e2e -- --config=playwright.python.config.ts \
    tests/e2e/automation-workspace.python.spec.ts
  npm run test:e2e -- --config=playwright.python.config.ts \
    tests/e2e/automation-settings.python.spec.ts
  npm run test:e2e -- --config=playwright.python.config.ts \
    tests/e2e/operations-task-center-visual.python.spec.ts
  ```

  workspace/settings 分开 harness，避免共享 Active 污染。增加受影响 Dashboard/V2 和
  remote/cancel/Job-absence 的真实验证，复用已有 harness。人工查看桌面/窄屏，确保
  原记录/摘要/确认/下一步仍可用；不为收尾另建过程平台。
- 核对 fresh SQL layout/clean source/wheel/image 的 Job 专属对象退出；新数据同版本
  reopen/restart、备份验证/失败原子、RBAC、不可变 pins 和非重放必须保留。无旧 schema
  升级/旧任务迁移测试义务，失败不自动删除已有数据。证据放稳定 ignored 目录/CI，披露
  skips/未完成项；Task PASS 后重新判断 Slice RO-1–5 / AC-1–19，不替 A 自审或关闭。

## Non-goals

旧任务/旧 Job/旧 pending 的迁移、跨版本升级、旧历史恢复/ID 映射或兼容 executor；
更换 Storage/Provider、分布式队列/并行策略/进程监督、全 schema/仓库重构、全 V1 改版；
新增通用技术故障/附件重试/自动 uncertain replay/补偿/rollback；重新设计 Files/Automation/
Task Center/通知；删除共享配置/安全/证据；恢复 Pause/resume/retry-request 或已退役产品。
不清用户库/媒体，不改 A-owned Slice/Roadmap/Progress 或 Task47.3 的接受事实。

## Developer Completion Report

```text
Status: READY FOR B REVIEW
Task Base: 383d8834787674675183f4b251d9dfd26a5dc511
Candidate: 4dd55b87c59807e2816313e8c26121bae8e85651 (implementation checkpoint; this handoff commit follows)
```

### 变化摘要

- **终态通知（P1 #1）**：`SQLiteTaskRepository.release_scheduled_claim()` 在 SETTLED 提交后调用
  已注册的终态观察者；`NotificationPublisher` 以 `task:<taskId>:<status>` 为确定性事件身份写入
  outbox，覆盖 completed / partial_success / failed / cancelled。观察者在提交后运行、异常被隔离，
  不改变媒体结果；重复 settle/重启/再次读取不会重复写同一原始事件。Worker、直接 CLI、CLI
  `tasks cancel` 和 API 即时取消均接入同一持久化边界。
- **坏 pin 的可操作失败**：`_automatic_task_runner` 通过 `_pinned_task_configuration` 将
  `RuntimeSnapshotUnavailable` 转成既有 `AutomationConfigurationUnavailable` 证据
  （category / durable state / side effects / retry-safe / next action），不再退化为通用异常。
- **保留能力证明（P1 #2）**：
  - 恢复并适配 `tests/test_configuration_snapshot.py`（44 项，含 OLD 45 项中 1 项纯 Job legacy
    被等价 Task 用例替代）、`tests/test_automation_settings_resident.py`（24 项；移除 1 项用户
    明确排除的 schema-49 升级用例）。
  - 恢复 `tests/test_operations_task_center.py`（24 项 Task Center 视图/计数/游标/Attention）、
    `tests/test_automation_definition_occurrence.py`（13 项 occurrence/due）、
    `tests/test_operations_run_detail_log_isolation.py`（6 项 scoped log 隔离）与
    `tests/test_operations_run_detail_plan_evidence.py`（10 项 plan evidence/redaction）。
  - 全部 66 处 `assertEqual((), ())` 恒真断言替换为真实 Task / capacity / result 断言。
  - 恢复配置发布失败回滚、并发发布/受理 pin、有效 resident adoption、Task Center 分页与
    原记录、scoped log/plan redaction、准入 pin/容量/授权等仍适用的断言。
- **消费者与文档（P1 #3）**：README、`docs/deployment.md` 的 remote/cancel 说明改为
  `POST /api/v1/tasks` / `tasks cancel`；Docker health/fresh/security/restart/empty-baseline
  smoke 改读 Task API、Task 承载、旧 `/api/v1/jobs*` 断言 bounded 404；`operations-inventory`
  harness 的 `run-worker`、`run-automation-run-once-worker`、recovery worker、discovery fallback
  改为真实 Task engine/claim，删除 Worker "retired" stub；原生 spec 的旧 legacy-continuation /
  paused-Job 子任务期望删除或改 bounded refusal，保留当前四类/八视图旅程。
- **测试产物修复**：`web/src/shared/api/operations-api.test.ts` 缺失的 `const result` 修复；
  `tests/test_release_security.py` 接受 TASK.md 当前 B 标题。

### 实际验证（Developer 受影响范围）

| 命令 / cwd | 实际结果 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -q` (`/Users/songzhidong/mediaflow`) | **2503 tests, OK, 7 skipped**（337.1s） |
| `.venv/bin/python -m unittest tests.test_notifications -q` | 15 tests, OK（0.6s；含 remote→worker completed / failed / cancel 与去重/重启/无二次媒体效果） |
| `.venv/bin/python -m unittest tests.test_configuration_snapshot -q` | 44 tests, OK |
| `.venv/bin/python -m unittest tests.test_automation_settings_resident -q` | 24 tests, OK |
| `.venv/bin/python -m unittest tests.test_operations_task_center -q` | 24 tests, OK |
| `.venv/bin/python -m unittest tests.test_automation_definition_occurrence tests.test_operations_run_detail_log_isolation tests.test_operations_run_detail_plan_evidence -q` | 29 tests, OK |
| `.venv/bin/ruff format --check .` / `.venv/bin/ruff check .` | 345 files formatted；All checks passed |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` / `python3 scripts/check_governance.py` / `git diff --check` | 全部通过；governance PASS |
| `config/strategy.example.json` / `mediaflow.phase13.2.example.json` `config validate` | 两者通过 |
| fresh SQLite inspect | schema 58；无 `%job%` 表；`notification_deliveries`/`task_scheduling` 存在 |
| Web `npm run typecheck` / `lint` / `format:check` / `test -- run` / `build` | 全部通过；1259 unit tests（87 files） |
| E2E `operations-inventory.python.spec.ts`（python config） | 35 passed |
| E2E `automation-lifecycle` + `automation-run-once`（python.automation config） | 17 passed |
| E2E `automation-workspace` / `automation-settings` / `operations-task-center-visual` | 8 / 12 / 2 passed |
| `py_compile` 全部受影响 Docker smoke 脚本 + harness | 通过（未在本机执行 Docker 真机矩阵） |

实际测试墙钟约 20 分钟（含两次全量 Python 回归、Web unit/build 与 6 组原生 E2E）；本轮
开发总时长约 1 小时 50 分钟，测试占比约 18%，低于 30%。最近一次全量 Python 为 337s。

### 未完成 / 风险（交 B 处置）

- `test_operations_run_detail.py`、`test_operations_run_inventory.py`、
  `test_automation_workspace_read_model.py` 的 Base fixture 仍以 `AutomationJob` 行构造
  “Job→Task 链接/预启动 Job”场景，未整体恢复；相同保留能力的 Task-only 覆盖已由
  `test_operations_task_center`、`test_operations_run_detail_log_isolation`、
  `test_operations_run_detail_plan_evidence`、`test_configuration_snapshot` 与通过的
  `operations-inventory` 原生旅程承担，但 Automation records/metrics/latest 的逐项 Base
  断言仍需 B 在完整 T4 中核对。
- `operations-inventory` spec 删除了 6 项 legacy manual-intent recovery 与 2 项 Job batch /
  attachment recovery 子任务；它们依赖已退役的 Job continuation，当前四类同 Task 旅程由
  `automation-run-once` 的 conflict/technical sibling 用例覆盖。
- Docker smoke 只做语法/断言核对，未在本机执行；release-security/fresh/restart/empty-baseline
  的真实容器矩阵仍归 B。
- 旧 schema 升级/旧数据迁移按用户明确排除未实现；schema 58 对旧 Job 库失败关闭。
- B 仍须在完整 Base..candidate 上执行 T4、原生/视觉、clean wheel/Docker fresh/restart/security
  并重评 Slice RO-1–5 / AC-1–19；Developer 不自评 PASS。

## Developer Fix Report — notification contract and native recovery coverage

```text
Status: READY FOR B REVIEW
Task Base: 383d8834787674675183f4b251d9dfd26a5dc511
Source candidate: bebf7a3a9217b7f06fb14649d6197ac1c9e0366b
```

### 本轮修复

- **P1 通知 Web 合同**：`web/src/entities/operations/notification.ts` 的规范事件改为
  `task.completed/task.failed/task.cancelled/schedule.emitted`；已有的 `job.*` 配置字面值
  经有界别名映射为同一 Task 事件后再显示/保存，未知值仍 fail-closed。定义、草稿、投递
  normalizer 与 fixtures/E2E 同步为 Task wire，旧 sample 配置仍可读。
- **旧嵌套配置的真实草稿解析**：`ManagedConfigurationService.latest_open_draft_containing`
  在 `webhooks` 根段缺失时读取已支持的 `notifications.webhooks` 旧拼写，使示例配置的
  successor Draft 可正常进入定义详情/编辑器；规范根段仍优先。
- **真实 Notifications 页面旅程**：新增原生 Python harness 测试，从侧栏打开通知页、
  读取真实 `GET /api/v1/operations/notifications/webhooks`、核对 `task.*` catalog 与
  `operations-webhook` 定义，再启动 successor Draft 并在真实 Draft 编辑器确认 Task
  事件选项；页面不再显示 contract unavailable。
- **同 Task 四类恢复闭环**：修正 Files 发现 Task 的原恢复摘要识别。当前 Preview 与旧
  已准入 execution 的 Preview 不同时，旧 execution 视为历史；保存决定后的新分析在
  `waiting_confirm` 时可暴露当前摘要。新增 resolved four-type decision 持久判定，使
  Task Center 仍把该条目归入 recovery lineage，而不是 technical history。确认仍走同一
  Task 的既有 Files Preview/execution admission。
- **原生恢复覆盖**：harness 的 recovery fixture 改为真实 `POST /files/discoveries`
  （autoPrepare）创建 Files Task、discovery、intent、analysis 和 Preview，再在当前
  Task 上登记四类 review/confirmation；不再构造旧 Job/legacy manual Task。
  `operations-inventory.python.spec.ts` 新增识别、Metadata 候选、Metadata 修正、
  分类、冲突重命名、冲突 overwrite 六个真实浏览器旅程，覆盖决定→分析→摘要→显式
  确认→同一 Task 文件效果、Metadata 显式搜索次数、成功 sibling/原结果保留、冲突目标
  保留与 overwrite 拒绝/同意。
- **测试资产同步**：fake notification server、NotificationRouter/notification 单测改为
  Task 事件；保留 `job.*` 别名回归；V1 通知事件说明改为 Task 名称。

### 实际验证（Developer 受影响范围）

| 命令 / cwd | 实际结果 |
|---|---|
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` (`web/`) | **42 passed，1.1m**；含真实通知页与六个恢复旅程。 |
| `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-run-once.python.spec.ts --grep "preserves a successful sibling"` | **2 passed，3.6s**。 |
| `npm run test:e2e -- tests/e2e/notifications.spec.ts` | **12 passed，6.6s**。 |
| `.venv/bin/python -m unittest tests.test_notifications tests.test_v2_notification_operations tests.test_webhook_management tests.test_notification_delivery_management tests.test_configuration_snapshot -q` | **102 tests OK，6.1s**。 |
| `.venv/bin/python -m unittest tests.test_processing_recovery_admission tests.test_automation_entrance_recovery tests.test_manual_task_engine tests.test_operations_task_center -q` | **76 tests OK，9.0s**。 |
| `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_operations_run_detail_log_isolation tests.test_operations_run_detail_plan_evidence -q` | **49 tests OK，5.5s**。 |
| `.venv/bin/python -m unittest tests.test_automation_settings_resident tests.test_v2_notification_operations tests.test_notifications -q` | **64 tests OK，45.3s**（ResourceWarnings 保留）。 |
| `npm run typecheck` / `lint` / `format:check` / `build` (`web/`) | 全部通过；构建 281 modules、149ms。 |
| `npm run test -- run src/entities/operations/notification.test.ts src/features/operations/NotificationRouter.test.tsx` | **83 passed，3.3s**。 |
| `.venv/bin/ruff format --check .` / `ruff check .` / `compileall` / `check_governance.py` / `git diff --check` | 全部通过；375 files formatted；governance PASS。 |

本轮测试墙钟约 6 分钟（含失败复现与重跑）；本轮开发总时长约 1 小时 15 分钟，测试占比
约 8%，低于 30%。失败复现保留实际命令与错误，未删断言、放宽超时或增加自动 retry。

### 未完成 / 风险（交 B）

- 全量 Python/Web/E2E、clean installed wheel、Docker fresh/restart/security、原生视觉矩阵
  仍归 B；本轮未执行，不宣称 T4 通过。
- recovery fixture 的 review/confirmation 行和 Task/item 等待态由 harness 测试 seam 直接
  登记，Task/discovery/Preview/决策/分析/摘要/确认/执行均走生产入口；该 seam 仅用于
  确定性构造四类阻塞，不是产品入口。
- harness 的 recovery fixture 不再提供 technical/attachment 旧 seed；技术失败只读历史由
  `automation-workspace` 的真实 Run once 旅程覆盖，附件自动重试按 Task 非目标不恢复。
- 旧任务/跨版本升级仍按用户明确排除；没有运行用户库、媒体或外部 Provider/Storage。
- B 须在完整 Base..candidate 上重跑通知/恢复原生旅程及 T4/包装/容器门禁，并重评 Slice
  RO-1–5 / AC-1–19；Developer 不自评 PASS。

## Developer Fix Report — real delivery event identity

```text
Status: READY FOR B REVIEW
Task Base: 383d8834787674675183f4b251d9dfd26a5dc511
Source candidate: 8db3ce45c1e589e9b8b9e48aa71d355061f1d1b3
```

### 本轮修复

- **P1 根因**：`normalizeDeliveryIdentity` 用 `NOTIFICATION_URI_SAFE_SEGMENT`
  校验 `eventId`，只接受字母数字与 `._-`；生产者实际写入
  `task:<taskId>:<status>`、`schedule:<scheduleId>:task:<taskId>`、
  `automation-definition:<definitionId>:task:<taskId>`，冒号使整份 list/detail
  文档被判 malformed，页面只能显示 contract unavailable。
- **有界事件身份**：新增 `NOTIFICATION_EVENT_ID`
  `/^[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9._-]+)*$/` 与 `eventIdentity()`，
  保留完整冒号分隔原值、沿用 128 上限并拒绝空白/路径/百分号编码/空段/前后冒号；
  `deliveryId`、`webhookId` 仍走严格 URI 段规则，`eventType` 仍只接受 catalog 与
  既有 `job.*` 别名映射。list 与 detail 共用同一 parser，因此两处同时修复。
- **回归**：`notification.test.ts` 现覆盖真实 `task:`/`schedule:` 身份的 list 与
  detail 原值保留、非法身份（管道/空格/路径/百分号/空段/超长）拒绝；先以现有
  parser 复现 `NotificationNormalizationError (eventId)` 再修复。
- **真实生产者原生旅程**：`operations_inventory_harness.py` 的 Active fixture 通过
  既有 checked draft→activate 路径把示例 Webhook 发布为 enabled（订阅仍是已支持的
  历史 `job.*` 字面值，配置解析映射到规范 Task 事件），因此 Task 内核settle 后的
  post-commit observer 成为唯一 outbox writer；harness 不运行 Notification Worker、
  不发外部 HTTP，投递行如实保持 pending。未手工构造 delivery。
- **原生用例扩展**：`operations-inventory.python.spec.ts` 新增最后一个旅程：
  真实 `run-worker` 结算 definition-pinned Task → 读取 `task:<taskId>:completed`
  outbox 行（唯一、task.completed、pending）→ 打开 Notifications → Open deliveries
  （真实 `GET /api/v1/notifications` 200，无 unavailable）→ 首个（最新）Open delivery
  进入精确 `deliveryId` 详情，显示完整 `task.completed (task:…:completed)` 与
  `pending`/`not_leased` → Refresh 重读详情 → 同一 eventId 仍只有 1 条 delivery、
  Task `completed_at` 未变、无 item、页面零 `/api/v1/jobs` 请求。

### 实际验证（Developer 受影响范围）

| 命令 / cwd | 实际结果 |
|---|---|
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` (`web/`) | **43 passed，1.1m**；含新增真实 outbox delivery 旅程。 |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "Notifications page reads\|settled Task publishes"` | **2 passed，2.3s**（seed 状态独立可复现）。 |
| `npm run test:e2e -- tests/e2e/notifications.spec.ts` | **12 passed，7.1s**；既有投递列表/详情/恢复/RBAC fake-server 旅程无回归。 |
| `npm run test -- run src/entities/operations/notification.test.ts` | **61 passed**；新增真实身份/非法身份用例。 |
| `npm run test -- run src/entities/operations/notification.test.ts src/features/operations/NotificationRouter.test.tsx` | **86 passed，3.3s**。 |
| `.venv/bin/python -m unittest tests.test_notifications tests.test_v2_notification_operations -q` | **40 tests OK，3.0s**（保留既有 ResourceWarning）。 |
| `npm run typecheck` / `lint` / `format:check` / `build` (`web/`) | 全部通过；Prettier 已格式化两个改动测试文件。 |
| `.venv/bin/ruff format --check` / `ruff check`（harness）/ `python3 scripts/check_governance.py` / `git diff --check` | 全部通过；governance PASS。 |

本轮测试墙钟约 4 分钟（含全量 43 项原生 harness 旅程 1.1m、fake-server 通知旅程与
单元组）；本轮开发总用时约 30 分钟，测试占比约 13%，低于 30%。失败的 refresh 等待
是测试自身路径写成 `/api/v1/notifications/{id}`（实际 detail 走
`/api/v1/operations/notifications/deliveries/{id}`），按真实契约修正等待路径，未放宽
超时或删除断言。

### 未完成 / 风险（交 B）

- 全量 Python/Web/E2E、原生视觉、clean installed wheel、Docker fresh/restart/security
  仍归 B；本轮未执行，不宣称 T4 通过。
- harness 的 Webhook 订阅继续使用示例配置里已支持的历史 `job.*` 字面值（Python 解析
  映射为规范 Task 事件），用于证明真实别名配置也能产生 Task 事件投递；fixture 未运行
  Notification Worker，因此投递始终 pending、无外部请求。
- fake-server `notifications.spec.ts` 的事件编号仍是无冒号测试夹具；真实生产身份由
  新增单测与真实 Python harness 原生旅程覆盖，未用它替代生产数据。
- harness 未配置 `MEDIAFLOW_WEBHOOK_SECRET`，详情页因此如实显示“目标不可交付、无手工
  恢复”；既有 dead-letter requeue/stale resolve 行为仍由 fake-server 旅程与 Python
  通知测试覆盖，本轮未新增恢复 UI。
- 旧任务/跨版本升级仍按用户明确排除；未接触用户库、媒体、Provider 或外部端点。
- B 须在完整 Base..candidate 上重跑通知原生旅程及 T4/包装/容器门禁，并重评 Slice
  RO-1–5 / AC-1–19；Developer 不自评 PASS。

## B Review Result

```text
Reviewed: 383d8834787674675183f4b251d9dfd26a5dc511..b55ce74c4a1145e2218e11dd23de8c82777e3e99
Latest implementation: 8db3ce45c1e589e9b8b9e48aa71d355061f1d1b3
Decision: FIX REQUIRED
Task blockers: resident Worker cannot perform first registration; five V2 E2E expectations still use retired Job behavior
Previous notification/recovery findings: VERIFIED FIXED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP — preserve Task ID/Base/Goal and user exclusions
```

B 起点 main / 上述候选，governance PASS、workspace/Git 可写；无 tracked 修改，预存
未跟踪文件原样保留。独立核对完整 Base..candidate 的 168 文件变更及前序修正，未改
生产或测试源码。handoff 只改 Task；最新执行输入为 8db3ce4。旧审查/Developer 证据
留在 Git。本轮开始适用用户“V1 不受支持”边界；共享路径 `/api/v1/*` 仍按实际 V2
消费者验证，未把 V1 独有界面当作返工项。旧任务/跨版本升级继续排除。

### 已验证的交付

- 真实 Task 自动产生通知，V2 通知配置、投递列表、精确详情、刷新和事件身份都通过；
  不再保留上轮 eventType/eventId 两个阻塞。六个同 Task 四类恢复及 Overwrite 明确
  同意旅程也已通过；不重新要求退役 Job/子 Task/暂停流程。
- 全 Python **2503 tests / OK / 7 skipped**，144 个 test 模块按四组完整覆盖；共享
  容量、claim/fence、权限/固定配置、原运行记录、真实稳定性、附件、来源占用和
  uncertain 非重放等在当前完整回归中通过。skips 为现有 real remote/endurance 环境。
- Web **87 files / 1264 unit tests PASS**，typecheck/lint/format/build 通过。
- 当前生产资产 + 真实 Python/API/SQLite 的原生组 **43 + 17 + 8 + 12 + 2 = 82 PASS**：
  inventory/四类/通知、Automation lifecycle/Run once、workspace/records、settings
  adoption、Task Center/摘要/确认。桌面与窄屏截图已人工查看并保留。
- clean HEAD archive 构建 wheel，源树外安装/CLI/API/fresh/配置/backup/read consumers
  smoke PASS；Ruff、compileall、pip check、examples 和完整范围 whitespace 通过。

上述原生 harness 会明确调用单次 Worker；它们的成功不能证明常驻 `worker run`
启动链可用。正式容器和下述独立进程复现揭示了这一差异。

### 阻塞及 Developer 指导

**1. P0 — 常驻 Worker 从首次启动起无法注册，已受理工作永远留在队列。**

用户旅程：“启动正式四服务 → 在 V2 Files/Automation 提交整理 → Worker 自动推进 →
查看逐项结果”。实际 API/Scheduler/notification-worker healthy，Worker 进程存活，
但 health 一直是 **resident worker is not transfer-ready (no_worker)**，容器 fresh
验收等待 150s 仍失败，无法进入自动消费。媒体没有被误动，但整理/普通文件 Worker
用户旅程整体中断，符合 workflow 的 whole-journey outage。

B 另从已有 remote Task POST 受理一个 fresh Task，启动真正的
`mediaflow --config <临时配置> worker run --poll-seconds 0.1`，跨多个真实轮询观察：
`processAlive=true, residentWorkers=1, processingWorkers=0, taskStatus=pending,
queueState=queued, claimGeneration=0, resultCount=0, sourceExists=true`。
该进程使用临时 LocalStorage/SQLite，子进程移除了 Provider 凭据，无外部请求；随后已
正常终止并清理。并非凭空构造的不可达状态，也不是 V1 页面问题。

**精确修法：**

1. 修正 `mediaflow/final_cli.py::_run_worker` 的 `step()`：目前无条件先调用
   `worker_service.heartbeat()`；新的 ResidentProcessingWorker 初始尚未注册，心跳
   返回 false，于是进入 waiting，后面的 `run_next()` 永远不可达；而真正注册就在
   `ResidentProcessingWorker.run_next()` 内。让首次合法注册按现有 snapshot resolver/
   supported-command 边界先完成，再执行正常心跳/领取（或恢复首次未注册时可到达
   既有注册边界的正确顺序）。不要用恒真心跳、只隐藏 health 错误或改超时绕过。
2. 保持注册后的心跳丢失/停用/schema/pin 拒绝、claim generation/source ownership、
   取消边界及 uncertain 非重放。注册本身不能创建媒体工作、换固定配置或补发权限。
   无 Active 时消费者仍要如实注册并等待；后来发布/重启后同样能合法消费。
3. 在现有 resident 测试中增加真正 `worker run` 的首次启动/消费回归：不仅检查
   resident_services/adoption（当前这些检查会通过），还检查 processing_workers 的
   实际命令注册与可领取工作，证明已受理 Task 被推进且既有结果不重放。复用现有
   临时库/本地假 Provider/原有进程 fixture，不创建新 Worker 或新测试平台。
   正常 `worker run-next` 已通过，不可拿它替代常驻入口。

**2. 现有 V2 全量 E2E 的五项 Job 预期尚未同步。**

原始全量为 245 passed / 8 failed；其中 3 项纯 artifact ENOENT 已由 B 处置如下，
剩下五项是明确的当前测试/fixture 对接缺口，均来自现有 V2 spec：

- `automation.spec.ts:453`：当前链接实际为 Task ID，断言仍要求 automation-job ID。
- `operations.spec.ts:234`：关闭旧集合的标题断言仍固定旧 Job 文案。
- `operations.spec.ts:341`：仍要求旧 Job deep link 自动解析成旧 pre-Task 身份。
- `operations.spec.ts:403`：Dashboard 仍查找已删除的 Open this Job 链接。
- `operations.spec.ts:847`：仍构造“尚无 Task 的 Job”并要求其旧进度文案。

**修法：** 依 Task 的 Entry disposition，将支持的 Automation/Dashboard/current run
断言改为实际 Task 身份，保留正确链接、只读和不重复工作的检查；旧 Job/旧身份输入改
为既定有界不可用，不恢复映射、Job collection/历史兼容或旧执行器。标题纯改名不作为
产品缺陷；这里要求完成已授权的实际测试消费者切换，使全量不再要求已退役行为。
无需新功能，也无需 V1 验收。

### 本轮验证事实 / 证据

证据根（本机 ignored，不声称远端可达）：
`.git/validation-evidence/b55ce74c4a1145e2218e11dd23de8c82777e3e99/b-task47.4/`。
`acceptance-manifest.json` 记录候选、命令/日志 hash、测试区间及覆盖；完整 Python
模块与命令清单在 `python-full-manifest.json`。

| 验收 | 真实结果 / 日志 |
|---|---|
| Full Python | 698/700/559/546 = 2503，7 skips，均 OK；四组 131.299/136.095/116.439/43.981s，执行并行；`python-full-0..3.log`。无漏模块，未将分组变为只挑 affected。 |
| Python quality/examples | Ruff format/check、compileall、pip check、governance、两份 approved example validate、禁 FFprobe/FFmpeg 无匹配（预期 exit 1）、Base..Head whitespace 均通过。 |
| Full Web | typecheck/lint/Prettier/build PASS；87 files、1264 unit PASS（118.62s）；`web-full.log` 留完整 pipeline。full fake E2E 245 PASS / 8 FAIL（3.4m），五项待按上表同步，三项 artifact 问题另见下段。未声称全量 E2E PASS。 |
| Real native/visual | inventory 43（1.2m）、Automation 17（22.4s）、workspace 8（9.7s）、settings 12（11.5s）、visual 2（9.7s）全通过；`native-*.log` 与 17 张 `native-screenshots/`；另有先跑的 notification critical 2 PASS。 |
| Clean wheel | clean committed archive 构建、installed source-external smoke exit 0；`wheel-build.log` / `wheel-smoke.log`。wheel SHA256 `94de9c73a838c6fdc25ec0f40e1c3f45852f5194c55b26526dde2322d3c1542c`。 |
| Docker fresh/security | 使用可共享的本仓库 ignored TMPDIR，clean committed context/image build 完成；四服务中 Worker no_worker/unhealthy，fresh 等待超时，**FAIL**；`docker-security.log`。镜像 `sha256:e9291a58628c84375a1ed7524e2785ffcef05f2600bc4adead1e63e3b1607dc5`；脚本已清理自己的容器。不是上轮临时 bind 路径问题。 |
| 独立常驻复现 | `repro_resident_bootstrap.py` + `resident-bootstrap.log`，1.740s；真实受理→常驻 run 后没有 processing Worker/claim/Result，注册断言 FAIL。 |
| 未执行/未完成 | Docker 后续运行期安全/同版本 restart 门禁被启动故障阻塞；不继续跑昂贵重复矩阵，不要求旧任务/跨版本升级，不以 V1 页面兼容作为门禁。 |

**B 自身 artifact 干扰的处置：** 本轮同时跑 fake/native Playwright 使用了同一个
默认 `web/test-results`，造成 fractional integer、MediaLibrary hierarchy、stale
notification recovery 三项在 browserContext.close 时 trace 文件 ENOENT。该责任归 B，
未派回 Developer。保留原失败，三个原用例在独立 `--output <证据根>/artifact-isolation`
下均通过（2.6s），无 timeout/断言变化或自动 retry；不能把这三项计作产品缺陷。
后续 B 浏览器组使用独立输出或顺序运行。五项真实旧预期失败未被掩盖。

测试墙钟按重叠区间合并，不把并行命令相加：日志 birth/mtime、Python manifest 与
full Web last-run 时刻给出保守上界 **379.362s**，另加相关检查 15s 余量。其余时间
用于完整范围、真实入口、根因、fixture/错误归属、产物/视觉和 Slice 结果审查及报告。
本轮记录时总用时 881.9s，含余量的测试上界 394.362s，占比 44.7%，低于 50%。
没有空等凑比例，也未省略失败或删断言。

Developer 修正只跑新/修改的 resident 及直接受影响 engine/入口测试，改到的 V2 E2E
用例和静态检查，交 coherent checkpoint。B 负责重新验收 Docker fresh/安全/restart、
当前全量与必要复用；不把 B 的完整矩阵转交 Developer。

### Entire Slice reassessment — 全部结果和 AC

| 结果 | 本轮判断 |
|---|---|
| RO-1 — 同一 Task / 统一调度 | 全 Python 的原子容量/claim/fence 等通过，但正式常驻无法首次注册，整体未满足。 |
| RO-2 — 一个引擎 | 单次入口、四类同 Task/native 已验；正式 resident 无法进入消费，实际自动推进闭环未完成。 |
| RO-3 — 同 Task 四类恢复 | 六个真实浏览器旅程及 Python/Run once/原结果独立通过；常驻 Worker 修正后仍需证明普通部署可推进，不新建恢复类型。 |
| RO-4 — Job 退出 | fresh 主体、源码和 clean wheel 已核对；image build 已完成；同版本 restart/容器运行证明受启动故障阻塞。旧任务/跨版本迁移排除。 |
| RO-5 — 用户与管理闭环 | 通知/详情、八视图、Automation/records/settings/native 和当前配置证明改善；常驻队列不动是实际部署阻塞，五项 V2 测试消费者仍待同步。 |

| AC | 本轮判断 |
|---|---|
| AC-1–3 | 受理/共享容量/claim/control 的 Python/full 回归通过；实际 resident readiness/启动消费不通过。 |
| AC-4–6 | 统一引擎/入口差异/filtering/附件/完整范围/稳定性在 Python/native 通过，正式常驻消费链不通过。 |
| AC-7–8 | 四类原生、独立结果/固定配置/不确定效果反例通过；容器同版本 restart 剩余门禁待修复后完成。 |
| AC-9–10 | 用户排除旧任务/跨版本升级；fresh/同版本 restart、failure atomicity/uncertain 义务保留。 |
| AC-11–12 | Job schema/对象退出、source-external wheel 与 pin/settings 回归通过；resident 真正执行健康和容器最终证明尚未满足。 |
| AC-13–16 | 八视图/原记录/日志/通知/权限/导出等当前 Python/native 通过；五项 fake E2E 测试消费者仍未对齐，不因此恢复 Job 或 V1。 |
| AC-17–18 | native/wheel 通过，Docker fresh FAIL、full fake E2E 未全绿；未达到 SLICE READY FOR A REVIEW，不做 A Final Review。 |
| AC-19 | Pause/resume 退出、合法取消与四类继续覆盖通过；修复不得恢复旧控制执行器。 |

结论：保持 Task47.4 / FIX REQUIRED，同 Base 修正，不拆新 Task。A-owned Slice/
Roadmap/Progress 不变，不声明 Slice PASS / CLOSED。
