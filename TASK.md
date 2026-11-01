# NO ACTIVE IMPLEMENTATION TASK

Task47.3 已由 B 验收 PASS；记录在 `383d8834787674675183f4b251d9dfd26a5dc511:TASK.md`，
接受候选为 `a0f09afefac2a85a70aca43c4cfbe1e36e04f1de`，原 Base 不变。
用户本轮只要求**规划下一 Task**。以下为 Task47.4 草案，不授权实施、派生代理、push、
部署或 Slice 关闭；后续明确授权开发时原地激活，并核对中间变更，不静默重定 Base。

# Task 47.4 — 独立 Job 系统退出与 Task 管理闭环（规划草案）

Authority: committed [SLICE.md](SLICE.md), RO-1/2/4/5、AC-4/11/12–18；
[Development Workflow](docs/development-workflow.md) 是生命周期、测试和收尾依据。
用户已明确**没有旧任务、不考虑升级**，此指令覆盖引用合同中的旧任务迁移、跨版本
升级/历史兼容要求；保留本版本 fresh、新任务和同版本 reopen/restart 的安全义务。
B 不改 A-owned Slice/Roadmap/Progress，不自行宣告 Slice PASS / CLOSED。

```text
Task ID: 47.4
Task Type: SLICE
Parent Slice: 47
Status: PLANNED
Task Base: 383d8834787674675183f4b251d9dfd26a5dc511
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation authorization: NOT GIVEN — PLANNING DRAFT ONLY
```

## Preflight / accepted baseline

仓库 `/Users/songzhidong/mediaflow`，branch `main`，规划起点为上述完整 Base；governance
preflight PASS，workspace/Git 可写。无预存 tracked 修改；预存 OS/log/参考图片、`15`、
`output/database-reference-2026-11-01/` 与 imagegen ZIP 保留且不暂存。不读用户数据库、
媒体或秘密配置。本轮只改此草案，不改生产、测试、schema 或 A-owned 文件。

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

## Implementation Scope — ordered guidance

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

  workspace/settings 分开 harness，避免共享 Active 污染。增加受影响 Dashboard/V1 和
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

未开始实施。明确授权激活草案后再填写：coherent code/test SHA、READY FOR B REVIEW、
变化/受影响命令及真实结果、剩余风险；不自评 PASS、不要求准备全量门禁 dossier。

## B Review Result

```text
Reviewed: NOT IMPLEMENTED — PLANNING DRAFT
Decision: NOT REVIEWED
Task blockers: no implementation assessment yet
Slice Required Outcomes / Surfaces all satisfied: NO — remaining Job system/surfaces
Next: await explicit implementation authorization; retain the same Task draft/Base
```
