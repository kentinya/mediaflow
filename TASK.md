# Task 56.1 — 同一候选版本切换 Web 与 API 入口

Next Action: B REVIEWS THE B56-01–B56-03 CORRECTED CANDIDATE

已提交的 [Slice 56 合同](SLICE.md) 定义范围。对应 RO-1／RO-2 全部公开入口、RO-3
中链接与既有身份的交接，以及 RO-4 中随仓的路径消费者。[Development Workflow](docs/development-workflow.md)

```text
Task ID: 56.1
Task Type: SLICE
Parent Slice: 56
Status: READY FOR B REVIEW
Task Base: 6ff7213bf770e94d4e7f90a5e8c57d6fe21985b3
Difficulty: High
Test Level: T4
Planner: A acting for B — explicit first-Task planning delegation
Reviewer: B — independent implementation review
Implementation Authorization: AUTHORIZED BY USER FOR TASK56.1
```

规划前治理检查通过。工作仓库为 `/Users/songzhidong/mediaflow`，分支为 `main`，Task Base
为 Slice 激活检查点，索引和工作区干净、文档及 Git 可写。Slice Base 仍记录在 [SLICE.md](SLICE.md)。

用户已授权激活本 Task。激活前 HEAD 为 `7ee6910b957b5f34b296fcbe085378859dd5fd77`，
工作区干净，治理检查通过。正式 Task 为 `PLANNED`，Developer 开始实施时转为 `IN PROGRESS`。

## Goal

用户从 `/` 连接进入探索，或打开带目录参数的 `/resourcelib/files` 直接回到原目录。
用户从新任务中心打开既有任务、查看逐项结果并显式执行授权允许的动作。API 客户端通过
`GET /api/tasks` 获取任务列表。凭据失效时可重新连接并返回原位置。旧地址进入普通
未找到流程，用户可自行打开正式地址。适用要求为 `V2-ROUTE-001–004` 和 `REQ-API-001–003`。
[目标旅程](docs/product-experience.md#target--canonical-entry-journey-slice56-active) ·
[目标架构](docs/architecture.md#target--root-web-and-unversioned-api-slice56-active)

当前 `service_api.py` 用前缀决定请求进入静态、健康或 API 分支。`v1` 路径段参与分发、
Active 检查、审计模板及只读审计例外。Vite、TanStack Router、Python 静态资源表和
Storage 设置链接校验各自引用 `/ui-v2`。请求 URL 和后端返回的操作 URL 来自多处。
`processing_checkpoint.py` 的同一阻塞项包含两种路径用途。响应中的恢复链接用于继续操作，
`_checkpoint_hash_blocker_resolution_path` 内的固定历史路径字符串参与 `checkpointVersion`
计算。恢复准入及已准备的摘要用这个版本核对同一条目。切换时必须分别验证公开链接和内部版本。

## Implementation Scope

1. **切换 Python HTTP 边界。** 在 `mediaflow/interfaces/service_api.py` 及 `v2_ui.py`
   以路径段区分 API、独立 `/health` 与 Web，从 `/` 提供入口和生产资源。
   正式 `/api/*` 调用既有分发器和应用服务，同步 Active／权限判定、只读审计及路由模板。
   校对按数组下标或长度匹配的分支，涵盖异常与直接组装的审计记录。旧 `/api/v1`、`/api/v2`
   及其子路由以 JSON 404 终止。`/ui-v2`、切换前的深链和旧静态资源进入普通未知路由处理。
   正式资源使用现行安全头、类型和方法限制。SPA 回退只服务 Web 导航，验证合法带点的
   Rules Edit ID、路径边界及缺失资源或构建产物。
2. **同一候选切换 Web 调用和服务端链接。** 校对 `web/vite.config.ts`、浏览器 router、
   同源代理、认证续转、来源返回以及 `storage-management.ts` 对设置链接的校验。
   对齐所有当前命令与读取端点，以及服务端返回的设置、Task、取消、checkpoint、逐项恢复、
   配置包、自动化及通知操作路径。分别验证 `/api/tasks`、`/api/operations/tasks`、
   `/api/operations/runs` 和两个 worker 投影。Web 与 API 沿用当前方法、查询、字段投影和错误。
3. **以原身份投影新链接。** 核对 `processing_checkpoint.py`、`sqlite_runtime.py`、
   整理和恢复服务对版本、摘要及原请求身份的依赖。用 Task／Item ID 构造对外新链接。
   固定的哈希输入按原算法参与版本计算，历史审计按原值读取。用 Base 的真实测试状态核对
   无业务变化时的版本、pin、原请求和新链接，再用候选验证实际状态变化仍能触发原冲突判断。
   保留已完成／不确定效果，显式动作仅处理服务端确认可安全继续的条目。
4. **同步随仓消费者和探针。** 更新 Python 和 Web 测试、Node 假服务、Playwright、脚本、
   生产验证与当期操作示例的正向地址，包括正则路径匹配。清单区分当前对外路径、旧路径拒绝
   断言和有现行用途的内部历史身份。修改过的测试沿用既有业务与权限断言。候选产物中的服务端、
   JS／CSS 和上述消费者按同一套路径验收。

## Acceptance Criteria

- [ ] AC-1 从真实构建和 Python 入口验证根地址、两种库带参数的深链、刷新／重连、设置回跳、
  任务弹卡及带点 ID 的 Rules Edit。核对九个主页面的入口和导航。有效资源与 `/health`
  各由自身分支提供，缺失构建、缺失静态资源和非法路径得到现行安全失败。
- [ ] AC-2 正式 API 通过已认证读写、未认证 401、权限 403、无效查询、分页、审计模板和
  适用的只读审计检查。使用正常配置和有效身份验证旧 API 的 GET 与至少一个实际原写入
  路径返回 JSON 404，且业务状态无变化。浏览器确认旧 Web 是通用未知路由，旧资源不可达。
  检查旧路径、API 和 Web 分支不会相互接管。Slice55 已退役入口仍拒绝。
- [ ] AC-3 用 Base 实际生成的同一 checkpoint 比对版本和 pin，候选重开同一隔离数据后，
  读回旧审计原值，生成可实际调用的新逐项恢复路径。更新条目状态后，原版本触发
  现行过期冲突。核对原请求回读和显式继续的区分，以及已完成／不确定效果的次数。
- [ ] AC-4 真正安装的构建产物和候选镜像的页面、静态资源、API 和 `/health` 一致，
  随仓脚本及测试消费者使用正式路径。核对本 Task 的影响路径中所有残留引用的用途。

## Required Tests

下列为实施和候选验收的计划命令。使用隔离 SQLite、临时文件根及本地假服务。
[测试等级和归属](docs/development-workflow.md#6-test-levels)

### Developer — affected tests

从仓库根执行，重点覆盖路由分派、权限、投影及 checkpoint 版本。新增或直接受影响的用例
按同样方式执行。Ruff 对修改的 Python 文件运行 `format --check` 和 `check`。

```sh
.venv/bin/python scripts/check_governance.py
for case in test_v2_ui test_api_security test_container_deployment test_processing_checkpoint \
  test_configuration_package_exchange test_v2_manual_organize test_automation_entrance_recovery; do
  .venv/bin/python -m unittest discover -s tests -p "$case.py" || exit 1
done
git diff --check
```

在 `web/` 执行，覆盖认证续转、Storage 设置链接、客户端路径、前端资源与真实库读取。

```sh
npm run typecheck
npm run test -- run src/routes/router.test.tsx src/shared/auth/AuthBoundary.test.tsx \
  src/shared/api/api-client.test.ts src/entities/storage/storage-management.test.ts
npm run build
npm run test:e2e -- tests/e2e/deep-link.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts
```

### B — acceptance and full regression

在实际提交候选运行 [T4 共享回归和生产门禁](docs/development-workflow.md#shared-full-regression-commands)，
独立复现两类新入口、旧前缀终止和版本保真。记录候选 SHA、精确产物与实际结果。
使用 Base 真实代码在隔离目录构建已阻塞的 Task item 和旧审计，候选重开同一数据库副本，
验证 AC-3 的同一版本、新链接、实际权限与过期冲突。

构建前端后，从 `web/` 使用真实 Python harness 检查真实文件、执行概览和原请求核对。

```sh
npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/live-files.python.spec.ts tests/e2e/operations-inventory.python.spec.ts \
  tests/e2e/manual-organize-dialog.python.spec.ts
```

从根目录将下列变量设为门禁刚构建的实际产物。轮子安装验证在源码树外运行。
浏览器确认构建资源的实际 URL、旧 Web 未找到及刷新/重连后的内容。

```sh
.venv/bin/python scripts/wheel_smoke_test.py "$task56_wheel"
.venv/bin/python scripts/installed_recovery_smoke_test.py "$task56_wheel"
.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image "$task56_image"
.venv/bin/python scripts/docker_release_security_smoke_test.py --image "$task56_image"
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image "$task56_image"
```

Slice 最终按合同核对完整的 Base → 候选跨切换丢响应场景、四类恢复及全部 RO。
范围相同且有可复用证据的本 Task 运行按工作流计入 Slice 最终验收。

## Non-goals

本 Task 的行为改动限于入口、响应中的可操作地址和随仓消费者。业务、数据库、配置及部署
拓扑以 Slice 的交付边界为准。历史审计和哈希身份按其现行职责读取。

## Developer Completion Report

```text
Task Base: 6ff7213bf770e94d4e7f90a5e8c57d6fe21985b3
Implementation Candidate: bb6704c4429a995bf883affae1c9f5ef6ec66f3f
Branch: main
Status: READY FOR B REVIEW
```

**B56-01 修复**

1. `GET /api/operations/runs/{run}` 在既有 `filesPreparation` 之外投影所选 Task 的
   `manualOrganizeSubmission`：只读取该 Task 最早一条由当前读取主体提交的持久
   `manual_executions` 记录，带原 `previewId`、`intentVersion`、选中条目、覆盖/来源清理
   权限、当前执行状态及逐项来源和结果状态；不发布 token、摘要授权或重放能力。另一读取主体
   得到 `null`，不会看到原提交人的请求身份。
2. Task 详情的既有事实区新增「原整理提交」只读卡。卡片显示原方案摘要、摘要版本、提交范围、
   效果权限及逐项结果，并用 `ManualOrganizeDialog` 同一 `fetchOrganizeAdmissionOutcome`
   与同一五个原始参数调用现有正式核对 GET；不自动读取，不重新 Execute，不提供继续动作。
   结果区分本任务 `known`、另一任务、`not_equivalent`、`not_admitted` 与读取失败；失败保留
   原记录并给显式重试。继续仍由原 Task 的逐项恢复入口负责。
3. 新增真实 Python 浏览器回归：`DialogReopen.2029` 经真实 Files→整批复核→丢失 Execute
   响应受理，真实 Worker 完成后整页重载、重连并打开同一 Task 深链；卡片显示原文件、摘要
   版本和效果权限，点击只发一次正式 admission GET，`known` 指向同一 Task，期间无写请求、
   无第二次 Execute。

**B56-02 修复**

`docker_empty_baseline_smoke_test.py` 的首草稿及 `validate|activate` 正向匹配、以及
`storage_settings_browser_proof.py` 的验证匹配均改为正式 `/api/configuration/...`；精确
方法、请求次数、原 Draft 版本、checked 激活与零媒体写入断言未改。README 的切换清单补充
旧书签 `/ui-v2`→`/`、旧 API `/api/v1|v2`→`/api`、随仓脚本替换和只读核对示例。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选 `bb6704c`）**

```text
.venv/bin/python scripts/check_governance.py                         -> PASS
git diff --check                                                     -> clean
.venv/bin/ruff format --check <changed .py>                          -> 5 files already formatted
.venv/bin/ruff check <changed .py>                                   -> All checks passed

.venv/bin/python -m unittest tests.test_manual_organize_execution \
  tests.test_operations_task_center                                    -> 61 tests, OK (1.330s)
.venv/bin/python -m unittest tests.test_v2_ui tests.test_api_security \
  tests.test_manual_task_engine tests.test_operations_run_progress_defaults \
  tests.test_operations_run_detail_plan_evidence                      -> 80 tests, OK (5.117s)
.venv/bin/python -m unittest tests.test_manual_organize_execution \
  tests.test_operations_task_center tests.test_v2_ui tests.test_api_security
                                                                       -> 89 tests, OK (1.309s)
```

Python 新增断言直接核对：原属性与持久执行一致、viewer 无投影、正式 admission 返回
`200 known` 和同一 Task、`sideEffects=none`、读取后 Task 数与 execution 数不变。

```text
web: npm run typecheck                                               -> OK
web: npm run lint                                                    -> OK
web: npm run format:check                                            -> All matched files use Prettier
web: npm run test -- run run.test.ts OrganizeSubmissionVerification.test.tsx \
  OperationsInventory.test.tsx                                       -> 3 files / 104 tests passed
web: npm run test -- run RunDetailTabs.test.tsx ManualOrganizeDialog.test.tsx
                                                                       -> 2 files / 48 tests passed
web: npm run build                                                   -> dist/index.html + hashed JS/CSS
web: npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/manual-organize-dialog.python.spec.ts \
  -g 'unknown Execute response|unknown original submission|reopened after a lost Execute'
                                                                       -> 3 passed (13.5s)
.venv/bin/python scripts/storage_settings_browser_proof.py            -> PASS
  writes: POST /api/configuration/drafts/first,
          POST /api/configuration/revisions/<id>/validate,
          POST /api/configuration/revisions/<id>/activate;
          empty Active published, tokenStored=false
```

**剩余与风险**

- 未由 Developer 执行最终 T4 门禁：完整 Python/Web 回归、wheel／源码外安装、Docker 空实例
  与发布/重启/Compose、Base 实际受理数据跨候选重开、Base→候选四类恢复。以上归 B 验收。
- Docker 空实例脚本已按正式地址修正并做静态检查，但本机未运行该 Docker 阶段；其实际通过
  仍需 B 的候选镜像门禁。Storage 首设置脚本已在当前构建产物上实跑通过。
- 新增浏览器回归由候选自身受理数据完成；B 还需用 Base 已受理的隔离数据重放同一重开核对，
  以证明历史受理记录直接可用。`web/dist` 不入 Git，B 需从本候选重新构建。

## B Review Result

```text
Reviewed: 6ff7213bf770e94d4e7f90a5e8c57d6fe21985b3..bb6704c4429a995bf883affae1c9f5ef6ec66f3f
Report-only Head: 28360763fe0b6ae169c44e72eba2020ef3c49191
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

上轮决定见 `e5b49872:TASK.md`。候选 Web 用 Base 已受理的隔离库原地重开后，用户可在
原任务点击「核对提交结果」。页面发送一次 GET，确认同一 Task 和原文件结果，期间没有写请求。
Storage 首次设置与候选镜像空实例均完成草稿创建、恢复、验证和激活。

### B56-01 · P1 · 同一任务的第二次确认无法从任务中心核对（RO-3 / AC-3）

用户在资源库选择两个文件，只确认第一项。Worker 完成第一项后，用户在同一任务里分析并确认
剩下的一项。真实 API 和 Worker 复现了两次受理和两条结果，分别用原参数都能核对为已受理，
指向同一 Task。任务详情只提供第一条受理记录。如果第二次确认的响应丢失，用户重连后点击
「核对提交结果」只能查到第一项。候选的 `_operations_run_manual_organize_submission`
用 `min` 选一条执行记录，页面也只渲染这一条。

1. 从同一 Task 已持久受理的记录投影当前提交人可核对的确认，沿用既有读取权限和结果口径。
   在「原整理提交」里按摘要、提交范围和提交时间区分记录。复用现有核对 GET，使用用户选中
   的那条记录的原选择、版本和效果选项。
2. 用 `test_ready_sources_remain_on_the_task_after_subset_execution` 的两次确认旅程验证查询，
   再从现有 Task 详情补真实浏览器用例。丢弃第二次确认的响应，刷新重连后核对第二项，断言 GET
   命中第二个摘要和原选择，两个逐项结果可分别查看，执行次数仍为两次。复跑另一读取主体的权限
   断言和单次受理的 Base 重开用例。

```sh
.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_manual_organize_execution
npm --prefix web run build
npm --prefix web run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts -g 'lost Execute|unknown original submission|second confirmation'
```

### B56-02 · P1 · Docker 重启与基础检查沿用旧导航的 HTTP 断言（RO-4 / AC-4）

管理员依照随仓脚本验收，两个脚本请求 `/ui` 时都中止，其中重启脚本已实际重启四服务。
根路径改版后，服务器返回入口 HTML，浏览器仍在原地址呈现普通未找到。两个脚本都要求
旧导航和旧静态资源返回相同的 HTTP 404。

1. 同步 `scripts/docker_restart_fault_smoke_test.py` 和 `scripts/docker_smoke_test.py`，
   沿用发布安全脚本对同一入口 HTML 和旧静态文件 404 的两种断言。旧导航的用户可见未找到
   继续使用现有深链浏览器用例证明。保留重启、脱敏和读操作无业务变更的其余断言。
2. 在实际候选镜像跑这两个脚本。切换说明里把 token 赋值写成可被 Bash 解析的示例。

```sh
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image "$task56_restart_image"
.venv/bin/python scripts/docker_smoke_test.py --image "$task56_smoke_image"
```

### B56-03 · P1 · wheel 专项恢复脚本无法运行现行用例（RO-4 / AC-4）

维护者依照 Task 的命令构建并在源码外安装 wheel。通用 smoke 通过，随后专项恢复脚本安装成功，
复制测试文件时因路径不存在而退出。该用例在 Slice 56 Base 前已删除。B 从同一已安装 wheel 的
`site-packages` 独立跑通现行的两项同任务恢复用例，随仓命令仍会中止。

1. 更新 `scripts/installed_recovery_smoke_test.py`，复用 `test_manual_task_engine.py`
   的现行 Task 原生摘要确认和元数据恢复用例以及既有 fixture。在源码外运行这两个明确命名的
   用例，并核对模块从所安装 wheel 导入。用例验证确认后由 Worker 在原 Task 上写入实际结果。
2. 构建新 wheel，运行 Task 所列的通用和专项 wheel 命令，核对专项恢复用例实际执行并通过。

### 独立验证

- Python 质量、配置示例、生产 Web 构建通过。Python 全量 2313 项，其中 7 项既有可选跳过。
  Web 单测 1640 项，默认浏览器 286 项，真实 Python 浏览器 10 项通过。后者覆盖两库实时读取、
  丢响应核对及四类逐项恢复。RO-1、RO-2 本轮已跑项目均通过。
- 通用 wheel、源码外两项现行恢复用例、候选 Docker 空实例及发布安全通过。Docker 初跑的挂载与
  回调失败已通过共享临时目录解决。重启与基础验收仍在旧导航断言处失败。首次尝试把 Base 库复制
  到另一位置，引发运行配置校验失败。用原隔离库路径重新复验，浏览器核对通过。
- 证据见 `.git/validation-evidence/bb6704c4/task56-1-b/`。RO-3、RO-4 仍有上述阻塞。
  三项修正后由 B 独立复验并重新评估 Slice 全部结果。

## Developer Completion Report — B56-01–B56-03 修复

```text
Task Base: 6ff7213bf770e94d4e7f90a5e8c57d6fe21985b3
Implementation Candidate: 472759665a42a73d24910464e903382adeb37e56
Branch: main
Status: READY FOR B REVIEW
```

**B56-01 修复**

1. `/api/operations/runs/{run}` 把 `manualOrganizeSubmission` 改为按提交时间排列的
   `manualOrganizeSubmissions`：只投影该 Task 中由当前读取主体提交的每一条持久
   `manual_executions`，每条保留自己的原 `previewId`、`intentVersion`、选中条目、
   覆盖/来源清理权限、当前执行状态及逐项来源和结果。记录不含 token、摘要授权或重放能力；
   另一读取主体得到空列表。固定的首个 `min` 选择已移除。
2. Task 详情「原整理提交」按记录分别显示提交时间、原方案摘要、摘要版本、提交范围和逐项结果；
   每条使用自己的原参数调用现有正式 admission GET。卡片不自动读取、不重新 Execute、
   不提供继续动作；继续仍由原 Task 的逐项恢复入口负责。前端解码按新数组字段校验，重复执行
   身份或逐项范围不一致按 malformed 失败。
3. 在 `test_ready_sources_remain_on_the_task_after_subset_execution` 的两次确认旅程中新增
   真实 API 断言：两条记录各自的 Preview、摘要版本和选中条目正确，提交主体可见两条，
   viewer 读取为 `[]`。新增 `DialogSubsetFirst.2030.mkv`／`DialogSubsetSecond.2031.mkv`
   浏览器回归：第一项经真实 Files→整批复核确认并完成；从 Task Center「继续整理」回到同一
   preparation，对剩余项保存修正并零变更重分析，再丢弃第二次 Execute 响应；真实 Worker
   完成后整页重载、重连同一 Task 深链，页面显示两条提交和两条成功结果，点击第二条只发一次
   admission GET 且命中第二个 Preview/原选择，全程 Execute 仍为两次。

**B56-02 修复**

README 切换清单中的 `TOKEN` 示例改为可被 Bash 直接解析的带引号占位值。
`scripts/docker_smoke_test.py` 和 `scripts/docker_restart_fault_smoke_test.py` 的旧导航断言
改为发布安全脚本同口径：`/ui`、`/ui-v2` 及其页面地址返回同一入口 HTML（普通未找到视图），
`/ui/app.js`、`/ui/style.css`、`/ui-v2/app.js` 返回 404。重启、脱敏、读操作无业务变更等
其余断言未改。两项脚本已在实际候选镜像上通过。

**B56-03 修复**

`scripts/installed_recovery_smoke_test.py` 不再复制已删除的
`tests/test_task_center_recovery_lineage.py`；改为复制现行 `tests` fixture
（`test_media_discovery.py`、`task_engine_test_helpers.py`、`test_manual_task_engine.py`
及包标记）和示例配置，在源码外按名称运行
`test_native_summary_is_confirmable_on_the_same_task_from_the_center` 与
`test_native_metadata_candidate_confirms_on_the_same_task`，并断言 `mediaflow` 从
`site-packages` 导入。两项用例由真实 Worker 在原 Task 上写入结果。

**实际验证（cwd `/Users/songzhidong/mediaflow`，最终工作树）**

```text
.venv/bin/python scripts/check_governance.py                         -> PASS
git diff --check                                                     -> clean
.venv/bin/ruff format --check <7 changed .py>                        -> 7 files already formatted
.venv/bin/ruff check <7 changed .py>                                 -> All checks passed

.venv/bin/python -m unittest tests.test_manual_task_engine   tests.test_manual_organize_execution   tests.test_operations_run_detail_plan_evidence                     -> 84 tests, OK
for case in test_v2_ui test_api_security test_container_deployment   test_processing_checkpoint test_configuration_package_exchange   test_v2_manual_organize test_automation_entrance_recovery; do ...; done
                                                                       -> 15/13/15/10/12/50/12 tests, all OK
```

```text
web: npm run typecheck                                               -> OK
web: npm run lint                                                    -> OK
web: npm run format:check                                            -> All matched files use Prettier
web: npm run test -- run run.test.ts OrganizeSubmissionVerification.test.tsx   OperationsInventory.test.tsx                                       -> 3 files / 105 tests passed
web: npm run build                                                   -> dist/index.html + hashed JS/CSS
web: npm run test:e2e -- --config=playwright.python.config.ts   tests/e2e/manual-organize-dialog.python.spec.ts   -g 'lost Execute|unknown original submission|second confirmation'  -> 3 passed (17.5s)
```

```text
wheel: /tmp/task56wheels/mediaflow-2.0.0.dev0-py3-none-any.whl
sha256: e70414fc96369441ab17120004ac130bfd148ccdde478eb88e6c5936fb87a360
scripts/wheel_smoke_test.py <wheel>                                  -> exit 0
scripts/installed_recovery_smoke_test.py <wheel>                     -> 2 named tests OK,
  installedPackage=.../site-packages/mediaflow, successfulInstalledRecovery=true

docker build -t mediaflow:task56-1-b56-02 .                          -> exit 0
scripts/docker_smoke_test.py --image mediaflow:task56-1-b56-02       -> passed
  (TMPDIR at repo .git/tmp-task56 so the daemon sees the temp mounts)
scripts/docker_restart_fault_smoke_test.py --image mediaflow:task56-1-b56-02
                                                                       -> passed
  (MEDIAFLOW_SMOKE_TEMP_DIR at repo .git/tmp-task56)
```

**剩余与风险**

- Developer 未执行 T4 全量 Python/Web/默认浏览器、Base 已受理数据跨候选重开、Base→候选
  四类恢复、空实例/发布安全/Compose 等门禁；以上仍归 B 验收。B 应从本候选提交重新构建
  镜像和前端产物。
- 新增浏览器回归依赖新增的两个 Dialog fixture；fixture 只用于该两条确认旅程，未复用其他
  已消费来源。
- 历史 Task 记录和哈希身份未改；仍按原值读取。
