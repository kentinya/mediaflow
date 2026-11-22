# Task 58.1 — 切换正式部署和主机恢复入口

Next Action: B INDEPENDENT REVIEW AND ACCEPTANCE OF TASK 58.1 FIXES

用户已授权实施 Task 58.1。Developer 返工已完成，状态为 `READY FOR B REVIEW`。
用户授权 A 代 B 规划首个 Task，角色例外限于首个 Task 的规划。B 独立验收，A 按工作流终审。
[Slice 58 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 58.1
Task Type: SLICE
Parent Slice: 58
Status: READY FOR B REVIEW
Task Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Difficulty: High
Test Level: T4
Planner: A on behalf of B (user-authorized planning only)
Reviewer: B
Implementation Authorization: AUTHORIZED BY USER FOR TASK 58.1
```

## 目标与现有缺口

落实 RO-1、RO-2、RO-3 和 RO-4 中的部署入口退役。部署者用正式 Compose 启动空实例，通过
`/health` 和 Web 看见等待管理员，凭主机权限领取设置码，在 Web 建号并初始化配置。忘记密码
时从同一部署领取重置码，在 Web 找回账号。停机维护时可备份、校验并恢复到空目标，再先启动
API 核对状态。预检、发码或恢复失败时说明实际状态、已有效果和安全的下一步。

当前 Compose 的四个服务由容器预检后转给通用 CLI。发码、数据库维护也用同一 CLI，备份指引
通过 Compose 的一次性容器启动它。探针用旧 CLI 参数识别服务，部分容器验收还用 CLI 直接整理
来证明后台业务。此次切换须将这些生产入口和依赖同时改接到正式链路。
[Compose](compose.yaml) · [容器入口](mediaflow/container_entrypoint.py) ·
[探针](mediaflow/container_probe.py) · [当前装配与分派](mediaflow/final_cli.py) ·
[部署指引](docs/deployment.md)

## 实施顺序

1. 从现有装配提取 API、Worker、Scheduler 和 Notification Worker 的启动和停止逻辑。
   入口显式选择四个固定服务，直接调用服务装配，使用同一最小 bootstrap、适用性检查和共享
   数据库租约。空库可正常上线并等待配置。保留 Waitress、现行监听及代理边界，保留 Worker
   的整理发现、分析、执行、普通文件传输和已受理任务的 pin，保留 Scheduler 的当前管理员
   授权与计划检查，以及 Notification Worker 的已固定投递目标。心跳、实时 Active 采用和退出
   继续使用现有机制。
2. 将镜像、Compose、源码外安装和探针接到固定服务入口。复用部署环境加载和只读预检，
   以服务职责替代探针所用的旧参数元组。无效服务名、任意命令或旧启动参数在运行时装配前
   拒绝。删掉 `MEDIAFLOW_COMMAND`、通用容器转发、旧服务启动、`run-next` 和 `tick`
   的产品入口。测试需要单步时直接使用现有处理器及隔离夹具。
3. 交付主机设置码和重置码签发，以及停机 SQLite 备份、校验和恢复的专用入口，与常驻服务
   使用相同的部署配置和实例身份。发码复用 AccountService，参与共享数据库租约，延续码的
   用途、时限、一次性消费及审计。恢复复用同版本适用性校验、独占租约、显式确认、空目标和
   非覆盖发布。先校验来源和暂存结果，失败时保护备份、原库和已有目标。备份与恢复只处理
   SQLite，校验输出区分文件完整性和能否在本版本使用。
4. 从通用 CLI 移除已切换的账户与数据库分派。更新首页发码提示、启动拒绝提示、README、
   部署／恢复指引、wheel 检查及受影响的容器和浏览器消费者。当前样例校验义务继续由
   共享门禁覆盖。Compose 文档中的配置发布
   改走系统设置，容器例行验收中的 CLI 整理改为 Web/API 受理并交给常驻 Worker。
   原确定性测试接到相应职责，保留权限、文件效果和失败边界的断言。

## 验收标准

- [ ] 正式镜像按原四服务拓扑启动空库且无需媒体挂载。进程、健康、等待管理员、等待 Active
  和工作就绪各自如实显示。修正无效配置、挂载或权限后可启动相应服务。预检和探针读取零媒体
  效果、零 Provider 调用，拒绝无效服务选择、旧启动参数和任意转发，也不采纳旧环境覆盖。
- [ ] 从新入口发码，在生产页面完成首次设置、配置初始化和忘记密码找回。验证错误实例／用途、
  过期、重复和并发消费、丢回包后的原状态核对以及重置后的旧会话撤销。公开 HTTP 的接口范围、
  现有 Web 会话及脚本令牌权限符合原契约，码明文仅出现在获授权的主机调用输出。
- [ ] 用正式镜像验证文件夹准备、分析、原任务确认、文件传输、Automation 到期与 Run once
  以及 Webhook 投递。切换和重启后按原 ID 核对受支持库内的 Web/API 任务、Active、固定
  快照与效果。无确认的分析零文件变更，已有完成或不确定效果零重放。
- [ ] 停止隔离栈并用正式主机入口备份、校验和恢复。先从新 API 读回备份时点的账号、配置、
  任务和审计，再按指引启用后台。损坏或不适用备份、缺少确认、租约竞争、数据库文件或
  旁路文件已存在、发布竞争均安全失败。核对源备份及原库仍完整，媒体目录效果为零。
- [ ] 用源码外 wheel 安装和正式镜像验证新入口。旧服务、账户与数据库的参数在各相关解析
  层拒绝，新路径直接使用共享装配和服务。候选指引、探针和验收脚手架使用同一套调用。

## 验证计划

按 [测试级别及分工](docs/development-workflow.md#6-test-levels) 执行。

### Developer — affected tests

- `PYTHONPATH=tests .venv/bin/python -m unittest test_container_deployment test_container_probe test_resident_services test_processing_worker_readiness test_runtime_lease`
  覆盖四服务注册、挂载预检、就绪状态、原任务处理和租约。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_snapshot test_resident_correction test_cron_scheduler test_notifications`
  覆盖启动装配直接影响的 pin、Active 恢复、调度及投递。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_api_credentials test_api_security test_sqlite_backup test_sqlite_restore test_release_validation test_release_security`
  覆盖发码、服务绑定安全、非覆盖维护、制品入口和保留的发布断言。补测新入口拒绝旧参数、
  无效输入和不适用备份的效果边界。
- 从 `web/` 运行 `npm run test -- run src/features/entry/EntryPage.test.tsx` 核对首页两个
  主机提示和认证恢复。`.venv/bin/python scripts/check_governance.py`、改动文件检查及
  `git diff --check` 从仓库根目录运行。

### B — acceptance and full regression

- 在 [共享全量门禁](docs/development-workflow.md#shared-full-regression-commands) 上验证精确
  候选。用 `.venv/bin/python -m pip wheel . --no-deps -w dist` 构建 wheel，并把精确产物
  路径传给 `.venv/bin/python scripts/wheel_smoke_test.py`，核对源码外四个职责入口和主机操作。
- 从同一精确候选构建并标识镜像，用 `candidate_image` 传入候选标签，分别运行
  `.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image "$candidate_image"`、
  `.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image "$candidate_image"` 和
  `.venv/bin/python scripts/docker_release_security_smoke_test.py --image "$candidate_image"`。
  用隔离 Compose 和生产浏览器验证发码、找回和备份恢复，从候选读回恢复状态，实测占用租约
  时恢复失败、进程正常重启和任务无重复效果。各脚本如自行构建，分别记录其镜像 ID、
  源码检查点、步骤、结果和限制。
- 在 `web/` 先运行 `npm run build`，再分别运行
  `npm run test:e2e -- --output=test-results/task58.1-accounts tests/e2e/web-account-auth.python.spec.ts` 和
  `npm run test:e2e -- --config=playwright.python.config.ts --output=test-results/task58.1-organize tests/e2e/manual-organize-dialog.python.spec.ts`。
  使用独立实例和输出目录验证认证恢复、文件夹准备及同任务续作，采集正式入口的证据。

## 非目标

完成整个通用 CLI 的源码和制品删除、退役业务命令与 CLI 专属整理分支、结束 schema 11
切换支持属于本 Slice 的剩余范围。此 Task 内维持现有数据库适用性拒绝和历史保护，
不引入新的升级或兼容入口。认证机制、业务 API 权限、Web 整理交互和媒体备份沿用 Slice 边界。

## Developer handoff — Task 58.1 Candidate

```text
Implementation Head: 5b6d966995cddc37e29a7442efa68300812f600b
Task Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Candidate state: READY FOR B REVIEW
```

### 实际改动

- 新增 `mediaflow/resident_entry.py`，固定四服务入口只接受一个职责名。API、Worker、Scheduler、
  Notification Worker 直接复用原装配；共享数据库租约、只读预检、Active/admission 边界、心跳、
  原任务 pin 和终端通知保留。API 仍使用 Waitress，默认 `0.0.0.0:8080`，仅通过
  `MEDIAFLOW_API_HOST/PORT/THREADS` 提供有界部署覆盖。
- 新增 `mediaflow/runtime_support.py`，承载服务与剩余业务 CLI 共用的数据库定位、managed Active
  解析、pin 和 Task 终端通知逻辑，避免服务入口依赖通用 CLI。
- `container_entrypoint` 只接受四个服务名或固定 `host` 维护模式；删除 `MEDIAFLOW_COMMAND`、
  任意可执行文件转发和旧服务参数。Compose 四服务命令改为 `["api"]`、`["worker"]`、
  `["scheduler"]`、`["notification-worker"]`；探针按服务职责复用同一预检。
- 新增 `mediaflow/host_operations.py`，只支持 `issue-setup-code`、`issue-reset-code`、`backup`、
  `verify`、`restore`。发码复用 `AccountService` 和共享租约；恢复使用独占租约、显式确认、空目标
  和旁路文件检查。`verify` 分开报告 SQLite 完整性、schema 和本版本可用性；当前 runtime store 与
  当前 configuration-only store 可备份/恢复，旧版本或不适用备份在写入前拒绝。
- 从通用 CLI 删除 `api`、`worker`、`scheduler`、`notification-worker`、`accounts`、`database`
  的分派和参数面；保留本 Task 外的剩余业务命令与 schema 11 切换，未扩大 Slice 范围。
- 同步更新 README、部署/配置/发布/架构指引、首页首次设置与重置提示、wheel/容器/浏览器脚手架。

### 实际验证

- `PYTHONPATH=tests .venv/bin/python -m unittest discover -s tests`：2365 项中通过 2364，
  7 项跳过；唯一失败为 `test_configuration_package_exchange.PackageRedactionTests.test_environment_references_preserved_and_literal_secrets_redacted`。
  该失败已在未改动的 `HEAD:c8d8d30f` 隔离 worktree 复现，是既有失败，不是本候选引入。
- Developer 受影响清单：196 项通过（含容器部署、探针、四服务、Worker readiness、租约、配置快照、
  resident correction、调度、通知、账户入口、SQLite 备份/恢复、发布校验）。
- 最终定向：60 项通过（容器入口/预检、探针、SQLite、租约、账户入口、发布校验）。
- 轮子：`pip wheel` 生成 `mediaflow-2.0.0.dev0-py3-none-any.whl`，`scripts/wheel_smoke_test.py`
  通过；源码外验证覆盖四职责入口拒绝旧参数及五个主机操作。
- Web：`npm run test -- run src/features/entry/EntryPage.test.tsx` 17 项通过；
  `npm run typecheck`、`npm run lint`、`npm run format:check` 通过。
- `python3 scripts/check_governance.py`、`ruff format --check .`、`ruff check .`、
  `python -m compileall -q mediaflow tests scripts`、`git diff --check` 通过。

### 剩余风险与待 B 验收

- Docker/真实 Compose、候选镜像发布安全检查、真实浏览器 E2E、wheel 精确候选门禁按 Task 分工留给 B。
- 本 Task 删除了 `--poll-seconds` 服务参数；发布 cadence 是唯一来源，相关旧覆盖测试已退役。
  Slice 合同中的 chunk 级服务启动源码/制品删除、事务性 schema 11 切换退役仍属本 Slice 剩余范围。
- `test_configuration_package_exchange` 既有失败仍保留，未用跳过或削弱断言掩盖；本地 ResourceWarning
  噪声存在于既有 SQLite 测试夹具，不影响断言结果。

## B 独立复核 — FIX REQUIRED

```text
Reviewed Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Head: 9a49bcea2cc52de945f973e065009b4c954699c3
Decision: FIX REQUIRED
Slice Outcomes / Surfaces complete: NO
Next: SAME TASK FIX LOOP
```

从候选镜像启动无媒体挂载的四服务，`/health` 可访问，根地址提供生产资源。用部署指引的
Compose 命令发码后成功建立管理员。停机备份与校验成功，已有目标拒绝恢复，换到空目标
恢复后单独启动 API，读回管理员已存在。以下返工留在 58.1。B 在修正候选上完成原 T4 验收。

### 开发指导与返工验收

1. **新部署到首次登录与密码找回。** README 的源码步骤先创建本地数据目录，再启动 API，
   后台和发码示例也使用同一 bootstrap 与数据目录。把根页首次设置和重置提示指向可执行的
   同实例命令，说明 Compose 在项目目录用 `docker compose exec -T api`，源码安装使用自己的
   Python 和相同部署变量。同步现行配置拒绝提示以及部署指南所链接的离线恢复步骤，为 Compose
   写出 `host verify`、`host restore` 和仅启动 API 的实际命令。验收从无 `.mediaflow` 的源码
   安装和无宿主 Python 包的 Compose 项目分别起步，沿页面指引领码并完成建号、重置和重新登录，
   沿发布指南恢复同一部署的备份。
2. **Compose 端口与健康一致。** 保持正式 Compose 中的监听、端口映射和探针使用同一个容器端口。
   将宿主端口的 `MEDIAFLOW_API_PORT` 与源码直启的监听配置说明区分清楚，消除部署环境文件能让
   Compose 的监听端口与探针分离的情况。验收在默认部署和明确更换宿主端口的部署中，浏览器和
   主机 `/health` 能访问，Compose 自带 API probe 通过。复测在部署环境文件设置端口后的实际结果。
3. **校验能否启动再恢复。** 让 `SQLiteBackupService.verify` 和 `SQLiteRestoreService.restore`
   复用正式服务启动对待切换库的判定。校验可确认文件完整，并显示当前不能启动及现行处理途径。
   还原前验证原备份与暂存副本的可用性，待切换备份无法发布到空目标，源备份摘要保持一致。
   继续验证当前 runtime 库和当前 configuration-only 库的成功路径。沿用现有 schema 11 切换边界。
4. **先取得租约再打开会写入的配置仓储。** `resident_entry.main` 从 bootstrap 取得数据库定位，
   在共享租约内解析 API 的 Active 和初始化仓储。租约竞争沿用有界启动错误，说明恢复完成后
   再启动服务。验收从空恢复目标开始，独占租约占用时走正式 API 启动入口，该进程退出且目标仍空，
   随后继续从确认恢复到 API 读回。

Developer 从仓库根目录定向运行：

```bash
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_container_deployment test_container_probe test_api_credentials \
  test_runtime_lease test_sqlite_backup test_sqlite_restore
npm --prefix web run test -- run src/features/entry/EntryPage.test.tsx
```

使用隔离数据目录按修正指引核对源码空库启动、Compose 领码和端口、停机恢复。
B 在修正候选上复现本节四条旅程，并运行本 Task 的 T4 门禁。

证据在 `.git/validation-evidence/9a49bcea2cc52de945f973e065009b4c954699c3/b-review/`。
Slice 58 的通用业务 CLI、专属任务路径和 schema 11 切换退役仍待交付。切换后的合法任务续作
与原效果保留仍待按合同复验。

## Developer fix handoff — Task 58.1 B review fixes

```text
Fix Implementation Head: 03aa59fc
Task Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Candidate: 9a49bcea2cc52de945f973e065009b4c954699c3
Candidate state: READY FOR B REVIEW
```

### 返工项与做法

1. **新部署到首次登录与密码找回。** README 源码步骤先 `mkdir -p .mediaflow` 再生成 bootstrap、启动
   API；发码、重置码和三个后台服务沿用同一 `MEDIAFLOW_CONFIG`/`MEDIAFLOW_DATA_DIR`。首页设置与
   重置提示指向同实例可执行命令：Compose 在项目目录用
   `docker compose exec -T api python -m mediaflow.host_operations ...`，源码安装用
   `.venv/bin/python -m mediaflow.host_operations ...` 并沿用启动 API 的部署变量。
   `api.principals` 拒绝提示由已退役的 `mediaflow accounts issue-setup-code` 改为
   `python -m mediaflow.host_operations issue-setup-code`。部署指南与发布指引写出 Compose 的
   `host verify`、`host restore` 和仅启动 API（`docker compose up -d --no-deps api`）的实际命令。
2. **Compose 端口与健康一致。** 容器内 API 监听固定为容器端口 8080；Compose 只把宿主端口
   `${MEDIAFLOW_API_PORT}` 映射到 8080，API 探针请求同一 8080。部署环境文件设置
   `MEDIAFLOW_API_HOST/PORT/THREADS` 时，容器入口和探针在装配前拒绝并说明：宿主端口在 Compose
   项目（shell 或项目 `.env`）设置，这组变量只用于源码直启的监听配置。
3. **校验能否启动再恢复。** `SQLiteBackupService.verify` 在文件完整性、版本适用性之外复用正式
   服务启动的待切换库判定，结果新增 `startup_blocked_reason`；`verify`/`backup` 输出新增
   `Cannot start yet:` 及其现行处理途径。`restore` 对原备份与暂存副本做同一判定，待切换备份不会
   发布到空目标；发布前重算源备份摘要，摘要变化则不发布，恢复输出记录保持不变的源摘要。
   schema 11 切换判定沿用 `reject_pending_configuration_switch`。待切换库的备份本身保持可用
   （切换前留存备份是既有指引），仅启动与恢复按启动判定拒绝。
4. **先取得租约再打开会写入的配置仓储。** `resident_entry.main` 先由 bootstrap 定位数据库并取得
   共享租约，租约内才拒绝待切换库、解析 API 的 Active 和管理模式仓储。宿占租约时以有界错误退出，
   说明恢复结束后再启动该服务，空目标不产生数据库文件。

### 实际验证（本轮返工）

- `PYTHONPATH=tests .venv/bin/python -m unittest test_container_deployment test_container_probe test_api_credentials test_runtime_lease test_sqlite_backup test_sqlite_restore`：65 项通过。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_resident_services test_processing_worker_readiness test_runtime_lease test_configuration_snapshot test_resident_correction test_cron_scheduler test_notifications test_release_validation test_release_security`：131 项通过。
- `npm --prefix web run test -- run src/features/entry/EntryPage.test.tsx`：17 项通过；新增断言覆盖首页设置与重置两处主机命令及 Compose／源码两种调用。
- 真实源码入口（临时目录，起步无 `.mediaflow`）：`resident_entry api` 启动后 `/health` 返回 200 且
  `firstAdministratorRequired: true`；`host_operations issue-setup-code` 发码后
  `/api/auth/bootstrap` 建号，health 转为 `firstAdministratorRequired: false`。停机执行
  `host backup` 得到 schema 60 备份（Integrity OK、Usable YES，无 `Cannot start yet`）；独占租约
  占用期间再次启动 API，进程退出码 2 并打印“Finish it, then start the api service again”，数据目录
  中没有数据库文件；释放租约后 `host restore --confirm-empty-destination` 成功，输出记录源备份摘要
  不变，仅启动 API 后读到同一管理员账号。
- `.venv/bin/ruff format --check .`、`.venv/bin/ruff check .`、`python3 scripts/check_governance.py`、
  `git diff --check`、Web `prettier --check`、`eslint`、`tsc --noEmit` 通过。

### 剩余风险与待 B 验收

- 本次返工未运行 Docker／真实 Compose、候选镜像发布安全、真实浏览器 E2E、wheel 精确候选与全量
  回归；按 Task 分工由 B 在修正候选上执行，重点复测默认与显式更换宿主端口的部署、部署环境文件
  设置端口后的实际结果、空目标独占租约后继续恢复，以及从源码空库与 Compose 项目分别走完建号、
  重置和同一部署的恢复。
- `test_configuration_package_exchange` 既有失败仍未修复（父版本可复现），未用跳过或弱断言掩盖。
- 待切换库的 `verify` 处理途径仍引用保留中的 `mediaflow config status`/`config retire-unpublished`；
  该切换的源码与制品退役仍属本 Slice 剩余范围。

## Latest accepted Task — PATCH-20261122-3

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: B PASS
Task Base: c714e0806620bb54701639a8776517ba5e1e9685
Implementation and Test Head: 6615a2b79fb01cec1b7aafebf55d507339ab2579
Reviewed Handoff Head: 05d07566685d282eaf3b42f6ecafa724355e7d37
```

B 审查完整 Base..交接 Head。生产 CLI 注册的 Worker 能处理文件发现，正常排队显示就绪并生成同一任务的方案。
桌面和 390px 保留准备提示、来源、受理范围和关闭入口。文件夹准备从无计数更新到真实的 10 个主文件。
后台离线时在文件页发起并刷新，随后从任务中心「继续整理」打开同一任务。后台恢复后在原弹窗进入复核。
全程受理一次，复核前执行请求和文件变更均为零。

只有文本文件的文件夹完成检查后，停止 Worker 再刷新仍显示「未找到可整理的主文件」和返回文件页的下一步。
首份摘要延迟及读取失败保留原准备上下文，重新读取同一摘要后进入复核。验证了人工分析恢复、部分未受理、
100 项复核、101 项超限，以及重新分析、整批确认和准确的任务交接。

- Python 整理和 Worker 相关 78 项通过。Web 受影响单测 164 项通过。生产构建、类型检查、lint、格式、
  Ruff 和治理检查通过。构建有大包提示，单测有 jsdom 的 `scrollTo` 提示。
- 真实 Chromium 整理套件覆盖全部 18 项。首跑 14 项通过、4 项失败。追踪记录显示回包丢失用例在
  Execute 返回 202 前启动了测试 Worker，后续三个用例在同一测试库中取到了先前任务。按原断言重跑
  这组相关旅程，候选和 Base 各 8 项通过。另完成任务中心继续整理、后台恢复及目录计数的定向验收。
  后台恢复的定向首跑所用文件超出夹具读回清单，改用清单内文件后核对源文件和目标。
- 零主文件提示沿用既有任务结算规则。任务中心仍保留对应整理记录。Web 来源按既有资源库标识显示。

本机日志、请求时间线、构建摘要和截图位于
`.git/validation-evidence/6615a2b79fb01cec1b7aafebf55d507339ab2579/b-review/`。
原 Task、返工记录和 Developer 交接见 `05d07566:TASK.md`。
