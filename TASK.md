# Task 58.1 — 切换正式部署和主机恢复入口

Next Action: DEVELOPER COMPLETES THE TASK 58.1 ACCEPTANCE CONSUMERS

用户已授权实施 Task 58.1。Developer 开始本轮返工时将状态改为 `IN PROGRESS`。
用户授权 A 代 B 规划首个 Task，角色例外限于首个 Task 的规划。B 独立验收，A 按工作流终审。
[Slice 58 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 58.1
Task Type: SLICE
Parent Slice: 58
Status: FIX REQUIRED
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

## B 返工复核 — FIX REQUIRED

```text
Reviewed Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Head: 9f4e526ac7b8eb7a5f71b926a4d82e6c71b07d87
Decision: FIX REQUIRED
Slice Outcomes / Surfaces complete: NO
Next: SAME TASK FIX LOOP
```

复验通过源码空库启动、主机发码建号、非默认 Compose 宿主端口和正式探针、待切换备份拒绝
恢复、独占租约保护空目标，以及恢复后单独启动 API 读回管理员。离线恢复指引仍缺少两种部署
从停机到选定空目标的实际操作。源码安装按 README 建号后停机，在新终端照发布指引只传
`--config` 验证备份，命令到 `/data` 查找数据目录并退出。Compose 按部署指南生成备份并保留
原库时，直接执行所列恢复命令仍指向现有库而被拒绝。使用与启动一致的部署目录，并将 bootstrap
指向同一持久卷中的新文件后，两个入口均可恢复。

### 本轮开发指导与验收

1. 在 [离线恢复步骤](docs/release.md#offline-restore-procedure) 写出可从新终端接续的源码命令。
   沿用 README 已创建的本地 `.venv`、`MEDIAFLOW_CONFIG` 和 `MEDIAFLOW_DATA_DIR`，把这两项部署
   变量明确带入备份、校验、恢复和单独启动 API 的步骤。
2. 从 Compose 部署指南默认的 `/data/mediaflow.sqlite3` 和 `/data/runtime-backup.sqlite3` 接续，
   写出使用现有 bootstrap 配置方法把数据库定位改为同一卷内的新文件的步骤。源码示例也给出
   新文件路径。应能按所列步骤保留原库及旁路文件、校验备份、恢复到新文件、单独启动 API 并读回。
   保持同一份离线恢复步骤作为两处指引的链接目标。
3. Developer 用全新维护终端和隔离数据目录逐条执行修正后的源码、Compose 示例，核对命令退出状态、
   原库及备份摘要、目标是否正确，以及 API 读回原管理员。运行 `git diff --check` 及
   `python3 scripts/check_governance.py`。B 用修正后的指引复验，再完成本 Task 的 T4 验收。

证据在 `.git/validation-evidence/9f4e526ac7b8eb7a5f71b926a4d82e6c71b07d87/b-review/`。
Slice 58 仍需完成通用业务 CLI、专属任务路径和 schema 11 切换退役，并验收 Base 合法任务续作。

## Developer fix handoff — Task 58.1 offline recovery guide

```text
Fix Implementation Head: 58daac8478d868c94df81f9c9663c20eeb6401fb
Task Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Candidate: 9f4e526ac7b8eb7a5f71b926a4d82e6c71b07d87
Candidate state: READY FOR B REVIEW
```

### 本轮改动

- 重写 [离线恢复步骤](docs/release.md#offline-restore-procedure)，分成源码安装和 Compose 两条
  可从停机状态接续的实际流程。两者都先记录原库摘要，再备份、校验，生成指向同一数据目录／
  卷内新文件的 bootstrap，恢复到新文件，重新核对原库摘要，最后只启动 API 读回。原库、旁路
  文件和原备份始终保留。
- 源码流程在新终端显式导出 README 使用的 `.venv`、`MEDIAFLOW_CONFIG` 和
  `MEDIAFLOW_DATA_DIR`；备份、校验、`config/mediaflow.restore.json` 生成、恢复和单独启动
  API 都使用同一组部署变量。目标示例为
  `$MEDIAFLOW_DATA_DIR/mediaflow-restored.sqlite3`。
- Compose 流程从默认 `/data/mediaflow.sqlite3` 和 `/data/runtime-backup.sqlite3` 接续，用
  `scripts/make_deployment_config.py --database-path /data/mediaflow-restored.sqlite3` 生成
  `config/mediaflow.restore.json`，再用 `MEDIAFLOW_CONFIG_FILE` 让一次性恢复容器和仅启动的
  API 挂载新 bootstrap。说明后续 Compose 命令必须继续使用该变量或写入项目 `.env`，否则会
  重新打开原库；启用后台前仍要核对文件效果和待处理任务。
- [部署指南](docs/deployment.md#backup-and-same-version-recovery) 不再列出会覆盖现有库的恢复
  命令，改为保留备份步骤并链接到唯一的离线恢复步骤；README 的源码段落补充同一变量和“新文件、
  保留原库”的说明。

### 实际验证

- 源码安装（新维护终端、隔离配置／数据目录、仓库 `.venv`）：按文档命令验证原库
  `fa5da657...`，生成并验证备份 `4fe41eaf...`，用新 bootstrap 恢复出新库 `4fe41eaf...`；
  恢复输出 `Source SHA-256 ... (unchanged)`，恢复后原库摘要仍为 `fa5da657...`。仅用新
  bootstrap 启动 API 后 `/health` 为 `firstAdministratorRequired: false`，原管理员 `admin`
  登录返回 200，`/api/auth/session` 返回同一 accountId。
- Compose（隔离项目、候选镜像 `mediaflow:b-task581-9f4e526a` / `68ff7c437891`、无宿主
  MediaFlow Python 包）：默认库摘要 `0e8a0e10...` 在备份和恢复前后不变；备份与恢复目标摘要
  均为 `cd79113f...`，恢复输出的源摘要未变。仅用 `MEDIAFLOW_CONFIG_FILE` 启动 API 后
  `/health` 为 `firstAdministratorRequired: false`，原管理员登录返回 200 并读回同一 accountId；
  再用同一 bootstrap 启动四个服务，API 健康且四服务运行。隔离项目、网络和卷已清理。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_container_deployment test_container_probe test_api_credentials test_runtime_lease test_sqlite_backup test_sqlite_restore`：65 项通过。
- `npm --prefix web run test -- run src/features/entry/EntryPage.test.tsx`：17 项通过。
- `.venv/bin/ruff format --check .`、`.venv/bin/ruff check .`、`git diff --check`、
  `python3 scripts/check_governance.py` 通过。

证据在 `.git/validation-evidence/58daac8478d868c94df81f9c9663c20eeb6401fb/developer-fix/`，
含源码和 Compose 的命令输出、原库／备份／恢复目标摘要、健康状态及登录会话记录。

### 剩余风险与待 B 验收

- 本轮只改文档，未改运行时代码；Compose 实测使用已由 B 在 `9f4e526a` 复核的候选镜像，文档
  提交本身不改变镜像内容。B 仍需用最终候选重新构建／打标镜像并执行本 Task 的 T4 门禁。
- Developer 的 API 读回使用真实 HTTP 登录和会话，不替代 B 的真实浏览器 E2E；全量回归、精确
  wheel 候选、发布安全检查和 Chrome 旅程仍按 Task 分工由 B 执行。
- 全量测试未在本轮重跑；既有 `test_configuration_package_exchange` 失败仍是父版本可复现的
  既有问题，未用跳过或弱断言掩盖。

## B 离线恢复复核 — FIX REQUIRED

```text
Reviewed Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Head: ce3c9e0aa2ab876a619c27910daaeac3789b3864
Decision: FIX REQUIRED
Slice Outcomes / Surfaces complete: NO
Next: SAME TASK FIX LOOP
```

复验已确认从新终端校验与恢复、选定空目标、保留原库和备份，以及单独启动恢复后的 API。
Compose 用恢复 bootstrap 接续启动了四个服务。`9f4e526a..ce3c9e0a` 只有文档差异，本次
Compose 定向复验沿用同一镜像 `sha256:68ff7c437891dfb6356a0717f9475cfa7cc4707e76d1296de96df73596b0dddf`。
当前离线恢复指引还有两处旅程断点。源码步骤只给 API 的单条命令设置恢复 bootstrap，维护终端
依然导出了原 bootstrap。登录确认后从该环境按 README 启动后台，三个后台服务登记在原库，
恢复库只有 API。有一份已验证备份且原库损坏时，按指引校验原库和重新备份都失败；从已保存
的备份恢复到新文件仍能读回管理员。

### 开发指导与返工验收

1. 给出源码后台接续的实际命令。在核对通过后，把恢复 bootstrap 和原数据目录明确带入三个
   后台服务所在的终端，并说明后续启动继续使用这组部署变量。确认四个职责都打开恢复库。
   将文档生成的 `config/mediaflow.restore.json` 按原 bootstrap 的规则加入 Git 忽略。
2. 在两种部署的同一恢复指引里，从校验已有备份接续恢复。原库可读时可另行生成备份并记录
   原库摘要。原库不可读时，直接校验并使用已保存的备份，在保留原文件的情况下选新目标、
   恢复、启动 API 读回，再按原有条件启用后台。
3. Developer 用隔离实例按文档验收两条完整旅程。从完好的原库恢复并登录核对后，按说明
   启动后台，确认新启动的服务注册都落在恢复库。再验证原库不可读时从已有备份恢复到新文件，
   核对原文件和备份摘要不变。运行 `git check-ignore config/mediaflow.restore.json`、
   `git diff --check` 和 `python3 scripts/check_governance.py`。B 复验后完成原 T4 验收。

本机证据在 `.git/validation-evidence/ce3c9e0aa2ab876a619c27910daaeac3789b3864/b-review/`。
Slice 58 的通用业务 CLI、专属任务路径、schema 11 切换退役和 Base 合法任务续作验收仍待完成。

## Developer fix handoff — Task 58.1 recovery journey gaps

```text
Fix Implementation Head: db1d82b4d7aed64f94ca941a1e6efe415f3fd180
Task Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Candidate: ce3c9e0aa2ab876a619c27910daaeac3789b3864
Candidate state: READY FOR B REVIEW
```

### 本轮改动

- [离线恢复步骤](docs/release.md#offline-restore-procedure)源码流程：原第 6 步拆为“登录
  核对”与“启用后台”两步。新的第 7 步先说明本节开头 `export` 的 `MEDIAFLOW_CONFIG` 仍指向
  原 bootstrap、直接启动会让后台服务打开原库，再给出把部署变量固定到恢复 bootstrap 的两行
  `export`（`MEDIAFLOW_DATA_DIR` 仍是原数据目录，变更的只是 bootstrap 文件）和三个后台服务
  的实际启动命令；并说明之后在本终端或新终端启动任何 MediaFlow 进程前先执行这两行。“四个
  职责都打开恢复库”的确认入口指向部署指南的认证只读 `GET /api/management/readiness`（或
  Web 系统视图同一信号），`infrastructure.services` 应同时显示四职责在线。
- 同一指引为源码和 Compose 两条流程各增加“原库不可读时，从已保存的备份接续”小节：原库
  损坏或 `verify` 失败时跳过对原库的备份，不删除、改写或重命名原库及旁路文件；校验已保存
  且此前校验通过的备份，按第 3–4 步生成指向新目标的 bootstrap 并恢复，之后核对原文件摘要
  未变化（Compose 同时重验备份摘要），再按原步骤仅启动 API、读回账号与任务，并按原有条件
  固定恢复 bootstrap 启用后台。源码路线用 `shasum -a 256` 记录原文件摘要（损坏库的字节摘要
  仍可计算）；Compose 路线用 `docker compose cp` 把原库复制到主机再记录摘要（停止后的容器
  仍可读取卷内文件，已实测）。
- 两条流程的第 1、2 步补充“原库不可读时”的路由指引；`config/mediaflow.restore.json` 按
  原 bootstrap 规则加入 `.gitignore`。

### 实际验证

- 源码旅程 1（完好原库、隔离配置／数据目录、仓库 `.venv`）：verify 原库与备份后恢复到同一
  数据目录内新目标；原库 SHA-256 恢复前后同为 `443b6d0d…`；恢复 bootstrap 单独启动 API，
  admin 登录读回同一 accountId（`b4f92700…`）；按修正后第 7 步固定恢复 bootstrap 启动三个
  后台服务，认证只读 `GET /api/management/readiness` 的 `infrastructure.services` 同时显示
  `api`／`worker`／`scheduler`／`notification-worker` ready 且 `liveServices ≥ 1`。
- 源码旅程 2（原库覆写为非法字节）：记录原文件摘要 `661b6ebf…`，`verify` 以有界错误拒绝；
  从已验证备份（`00080d8f…`）恢复到另一个新目标，原文件摘要不变；单独启动 API 后读回同一
  admin accountId。
- Compose 旅程（隔离项目、无宿主 MediaFlow Python 包、候选镜像
  `mediaflow:b-task581-9f4e526a`／`68ff7c437891`）：容器内备份 `a75812e3…`；原库损坏后用
  `compose cp` 复制出并记录摘要 `661b6ebf…`，从已验证备份恢复到 `/data/mediaflow-restored
  .sqlite3`，原文件摘要与备份摘要均不变；恢复 bootstrap 仅启动 API，admin 登录读回同一
  accountId（`a35ce198…`）；固定 `MEDIAFLOW_CONFIG_FILE` 后 `docker compose up -d` 启动四
  服务，readiness 四职责同时 ready。
- `git check-ignore config/mediaflow.restore.json`、`git diff --check`、
  `python3 scripts/check_governance.py` 全部通过；`docs/release.md` 代码围栏配对完整。无残留
  常驻进程或 Compose 容器。命令输出证据在
  `.git/validation-evidence/db1d82b4d7aed64f94ca941a1e6efe415f3fd180/developer-fix/`。

### 剩余风险与待 B 验收

- 本轮仅改 `docs/release.md` 与 `.gitignore`，未改运行时代码；部署文档参与构建上下文，B
  需在最终候选上重新构建并打标镜像，再执行本 Task 的 T4 门禁（全量回归、精确 wheel、发布
  安全、真实浏览器 E2E 与 Docker 旅程）。
- `test_configuration_package_exchange` 既有失败仍保留（父版本可复现），未用跳过或弱断言
  掩盖。
- Slice 58 的通用业务 CLI、专属任务路径、schema 11 切换退役和 Base 合法任务续作验收仍属
  剩余范围。

## B 复核 — T4 门禁 FIX REQUIRED

```text
Reviewed Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Head: c0315d8795fb042448fdc22f1e05b1fb43fcb29f
Decision: FIX REQUIRED
Slice Outcomes / Surfaces complete: NO
Next: SAME TASK FIX LOOP
```

从完好原库与已有备份恢复损坏库的定向验证通过。原文件和备份摘要保持一致，恢复后读回原账号，
四个服务报告就绪。T4 发现正式空库 Docker 冒烟仍有两处旧调用，Python 全量还有一项样例夹具
失败。门禁修正留在 58.1。

### 开发指导与返工验收

1. 在 `scripts/docker_empty_baseline_smoke_test.py` 的真实空库浏览器流程中，初始化并刷新后
   先打开「配置工具」，再展开「诊断」。保留仅一次初始化、零额外受理、读回同一 Active、浏览器
   凭据脱敏的原断言。B 用这一处导航调整原样复测，通过了无媒体挂载的整段旅程。
2. 同一脚本的媒体挂载流程，从 `POST /api/resource-libraries/source/files/organize` 受理指定
   文件，复用已有的 intent、分析、精确摘要和显式 Execute 请求，等待常驻 Worker 推进同一 Task。
   可参考同一候选已通过的
   `scripts/docker_release_security_smoke_test.py` 整理流程。沿用脚本已配置的测试媒体根和本地
   TMDB TLS 夹具。验证确认前源／目标零变化，确认后正好完成一份原字节 COPY，两种库的普通
   Copy 都能完成，服务身份始终一致。移除该流程对容器 `organize --execute --limit 1` 的调用。
3. 修正 `tests/test_configuration_package_exchange.py` 的脱敏单测夹具。样例合并后 `_examples`
   带有额外变量引用，测试仍精确匹配合并前的三条。用独立明确的输入核对原引用和字面凭据脱敏，
   或按现行样例精确断言所有输入的引用。保留原有的字段位置、值保留及明文移除断言。
4. 离线恢复指引的 Compose 诊断副本使用已被 Git 忽略的目录，现行示例把整个原库复制到项目
   根目录。两种部署的损坏库支路在摘要核对后直接接到第 5 步的 API 启动命令，避免重新运行
   已知失败的原库 `verify`。

Developer 运行 `PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_package_exchange`、
`git diff --check`、`python3 scripts/check_governance.py`，并用隔离 Compose 核对两段改动的
用户入口。B 对修正候选复跑正式 Docker 冒烟与全量 Python，并按工作流核对其余 T4 证据的
复用条件。

本轮 Python 运行 2373 项，2365 通过、1 失败、7 跳过；唯一失败在隔离 Task Base 复现。
Web 单测 1642 通过，常规 Chromium E2E 289 通过，原生整理 E2E 18 通过。候选镜像的根页
实测用主机命令领码建号和重置密码，旧会话失效后用新密码登录。Python 静态、样例
校验、Web 静态与构建、wheel 源码外安装、Docker 重启故障和发布安全通过。发布安全首跑的
宿主挂载失败改用 Docker 可见临时目录后通过。空库 Docker 门禁首跑停在「诊断」；临时补上
现行导航之后，媒体挂载段在退役命令处被正式入口拒绝，均保留原日志。

证据在 `.git/validation-evidence/c0315d8795fb042448fdc22f1e05b1fb43fcb29f/b-review/`。
Slice 58 仍须完成通用 CLI、专属任务路径、schema 11 切换退役和 Base 合法任务续作验收。

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
