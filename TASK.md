# NO ACTIVE IMPLEMENTATION TASK

Slice56 **ACTIVE**. Next Action: USER AUTHORIZES TASK56.1 IMPLEMENTATION.
A 依用户授权代 B 完成首个 Task 的规划。以下为规划草案，实施须按工作流获得授权。
最近验收仍为 Slice55，固定审查记录见 [Progress](docs/progress.md#latest-accepted-closure--slice55)。

## Task 56.1 — 同一候选版本切换 Web 与 API 入口（规划草案）

已提交的 [Slice 56 合同](SLICE.md) 定义范围。对应 RO-1／RO-2 全部公开入口、RO-3
中链接与既有身份的交接，以及 RO-4 中随仓的路径消费者。[Development Workflow](docs/development-workflow.md)

```text
Task ID: 56.1
Task Type: SLICE
Parent Slice: 56
Status: PLANNED
Task Base: 6ff7213bf770e94d4e7f90a5e8c57d6fe21985b3
Difficulty: High
Test Level: T4
Planner: A acting for B — explicit first-Task planning delegation
Reviewer: B — independent implementation review
Implementation Authorization: AWAITING USER AUTHORIZATION
```

规划前治理检查通过。工作仓库为 `/Users/songzhidong/mediaflow`，分支为 `main`，Task Base
为 Slice 激活检查点，索引和工作区干净、文档及 Git 可写。Slice Base 仍记录在 [SLICE.md](SLICE.md)。

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

待实施授权与候选检查点。

## B Review Result

待独立审查。
