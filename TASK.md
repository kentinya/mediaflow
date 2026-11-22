# Task 58.1 — 切换正式部署和主机恢复入口

Next Action: DEVELOPER STARTS TASK 58.1 IMPLEMENTATION

用户已授权激活 Task 58.1。Developer 开始实施时将状态从 `PLANNED` 转为 `IN PROGRESS`。
用户授权 A 代 B 规划首个 Task，角色例外限于首个 Task 的规划。B 独立验收，A 按工作流终审。
[Slice 58 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 58.1
Task Type: SLICE
Parent Slice: 58
Status: PLANNED
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
