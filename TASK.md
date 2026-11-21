# Task 57.1 — 从空实例创建管理员并完成 Web 登录

Next Action: B REVIEWS TASK57.1 IMPLEMENTATION

本 Task 落实 Slice 57 的 RO-1 与 RO-3。用户已授权激活，Developer 开始实施时将状态从
`PLANNED` 转为 `IN PROGRESS`。A 按用户授权代 B 规划本 Task，B 独立验收，A 终审。
[Slice 57 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 57.1
Task Type: SLICE
Parent Slice: 57
Status: READY FOR B REVIEW
Task Base: 4566a74055c698aec704215dd431eb8521bcfedb
Difficulty: High
Test Level: T4
Planner: A on behalf of B (user-authorized planning only)
Reviewer: B
Implementation Authorization: AUTHORIZED BY USER FOR TASK57.1
```

### 目标与现有缺口

部署者启动空实例，从主机生成一次性码，在首页创建首位管理员，再到系统设置初始化业务
配置。之后用账号密码登录，刷新和新标签继续使用。管理员可改密码、退出或凭主机重置码
找回访问。设置码过期时指引从主机重新生成，密码错或服务不可用时留在入口修正或重试。

目前部署生成器写入 `api.principals`，API 启动解析环境变量令牌，Web 表单仅检查非空后
跳页。浏览器凭证和自动化权限来源还依赖旧模型。本 Task 交付首位管理员的完整认证旅程，
同时将所有现行入口的身份判断接入数据库账号。相关入口见
[部署生成器](scripts/make_deployment_config.py)、[API 启动](mediaflow/final_cli.py)、
[API 权限](mediaflow/interfaces/service_api.py) 和 [Web 入口](web/src/features/entry/EntryPage.tsx)。

### 实施顺序

1. 建立独立的账号、密码哈希、会话和一次性码持久层及应用服务。事务内校验实例、用途、
   到期状态和首位管理员创建条件，原子消耗码并写入审计。改密或重置原子撤销目标账号的
   Web 会话。后端按当前数据库角色使用现有 RBAC，Scheduler 和 Worker 共用该权限判断，
   延续已受理工作的业务快照、效果范围和 claim/fence。
2. 更新部署生成、容器预检、配置输入与启动装配。空库在等待首位管理员时提供首页和独立
   健康状态，业务 API 要求有效身份。预检拒绝退役字段以及不受支持的数据库，并保留原
   文件。提供主机本地管理命令生成首位设置码和目标管理员重置码，同步更新生产部署指引。
   旧浏览器 Bearer 流程和环境令牌授权随当前入口一起退役。
3. 提供首页状态、首位设置、登录、会话身份、退出、改密码和重置入口。服务端验证成功后
   签发 Cookie，落实当期会话及「保持登录」到期规则，跨设备走 HTTPS，回环支持本机 HTTP。
   Cookie 写请求按同源规则校验，失败尝试限流，凭证和码按敏感信息处理。业务接口仍使用
   现有路径与 RBAC，`401` 清除失效登录状态，`403` 显示权限不足。
4. Web 从服务端恢复会话再加载保护页。首次建号进入系统设置，正常从根登录进入探索。
   保存安全站内深链及查询，过期登录后仅恢复读取和原请求结果核对。退出撤销服务端会话，
   清理客户端身份相关缓存并显示根登录页。多标签、账号切换及迟到响应按身份隔离，
   调整随仓测试和诊断消费者，使它们使用新链路及隔离夹具。

### 验收标准

- [ ] 用最小配置和空库启动真实 Compose，生成一次性码、创建首位管理员并通过系统
  设置初始化业务配置。匿名业务请求和旧环境令牌返回 `401`。预检给出现行配置指引，
  拒绝退役字段及不支持的库，原文件保持完整。
- [ ] Web 在桌面和窄屏验证错码、过期、重试、账号密码正常登录、真实账号菜单、退出、
  改密和主机重置。并发使用同一码或不同首位设置码，整个实例最多创建一位初始管理员。
  重置码绑定账号，改密和重置后旧 Web 会话在下一次请求失效。
- [ ] 持有效会话刷新、新开标签及同版本重启后回到合法深链。验证保持登录的到期和退出后
  访问保护页。过期重新登录后保留原目录或原任务，核对未知提交时原受理次数及效果计数
  保持准确。验证跨站写入防护、不同账号的缓存隔离、受限身份 `403` 和秘密脱敏。
- [ ] 用新建账号发布业务配置并受理任务，以真实 Scheduler 和 Worker 验证数据库身份
  检查及任务、结果、审计可回读。通过隔离夹具收回权限，验证后续适用检查明确拒绝执行。

### 验证计划

**Developer — 新增／修改与直接受影响测试**

- `.venv/bin/python -m unittest discover -s tests -p test_web_account_auth.py`
  验证新增的身份、一次性码、会话、并发及原子撤销用例。
- 分别执行 `.venv/bin/python -m unittest discover -s tests -p test_api_security.py`、
  `.venv/bin/python -m unittest discover -s tests -p test_container_deployment.py`、
  `.venv/bin/python -m unittest discover -s tests -p test_container_probe.py` 和
  `.venv/bin/python -m unittest discover -s tests -p test_execution_authorization.py`，
  验证 HTTP 权限、预检及后台执行边界。
- 在 `web/` 执行 `npm run test -- run src/features/entry/EntryPage.test.tsx src/shared/api/auth-store.test.ts src/shared/auth/AuthBoundary.test.tsx src/shared/auth/AuthorizedReadBoundary.test.tsx`，
  覆盖登录、恢复、错误状态和缓存清理。执行 `npm run typecheck`、`npm run build` 及
  改动文件静态检查与 `git diff --check`。如测试文件随重构改名，同步更新命令。

**B — 独立验收与完整回归**

- 在 `web/` 构建正式产物后执行
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/web-account-auth.python.spec.ts`，
  新增用例使用隔离的真实 Python/SQLite 空库，覆盖首位设置、深链、重启、撤销及非重放。
- 执行 `.venv/bin/python scripts/docker_web_account_auth_smoke_test.py --image <candidate-image>`。
  新增验收脚本从随仓配置生成器和真实 Compose 空库启动，并验证设置、恢复及重启。使用
  隔离库与测试凭证完成执行授权检查。记录候选镜像身份及实际验证结果。
- 按[共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)运行适用的
  T4 全量、生产打包与 wheel 验收。Developer 先交付受影响用例结果，B 用对应候选验收。

### Slice 后续范围

网页用户清单及新增用户、角色管理、普通用户初设和重置、API 令牌签发和轮换属于 Slice
后续成果。Task 57.1 内的权限变化验证通过隔离测试夹具完成。

### 交付与评审记录

**Developer 交付记录（READY FOR B REVIEW）**

- 交付范围：数据库账号、密码哈希、服务端会话、一次性设置／重置码及审计；Web 首页首位
  设置、登录、会话恢复、账号菜单、改密、退出与主机码重置；Scheduler／Worker 当前账号权限
  检查；最小部署生成、预检、配置示例与运维指引退役 `api.principals`／环境令牌入口。
- 实际验证：`test_web_account_auth` 13 项、受限 RBAC／预检／容器／执行边界等 126 项定向
  Python 用例通过；全量 Python 2340 项通过（7 项跳过）。Web 单测 1597 项、类型检查、Lint、
  Prettier、构建通过；身份/入口定向 45 项通过。示例配置校验、Ruff、编译、`pip check` 与
  `git diff --check` 通过，治理检查 PASS。
- 剩余风险：既有 Docker 多角色发布安全脚本和若干浏览器诊断脚本仍按退役环境令牌模型编写；
  本 Task 的多角色账号管理属于后续 Slice 成果，B 应按本 Task 新链路使用隔离空库验收，
  不应以旧多角色脚本作为本 Task 的通过条件。真实 Compose 与 E2E 候选验收由 B 执行。

B 评审结果待填写。

## PATCH-20261120-5 — 彻底退役配置草稿 — B PASS

- 复核范围为 `e279077c4bca208ab7168983d15eca66ec8833d1..039284e2cfb44ece7b4625d7b50bdcd02691ecb3`，实现版本为 `2837d9bc6c0dcc1360b02ccf659922a121bba667`。独立 Task 验收完成。实施计划及交付记录见 `039284e2:TASK.md`。
- 真实部署验收通过。无媒体挂载的新实例从系统设置初始化空配置。有媒体挂载的实例直接发布完整配置，并用原进程完成整理和两类库复制。部署指引和生成脚本帮助与实际操作一致。
- 候选的 Docker 健康、重启与故障、发布安全和 wheel 安装冒烟通过。撤销来源目录权限时，只读检查报告权限不足，API 仍在线。恢复权限后复查通过，生效版本和任务清单一致。容器部署 15 项、配置状态与配置包 27 项定向用例通过，改动脚本的 Ruff、编译以及完整范围的 `git diff --check` 通过。
- 产品、Web、产品测试和示例配置与 `fa8f9dd8` 一致。复用该版本的 B 全量证据。Python 执行 2327 项，7 项跳过，其余通过。Web 单测 1594 项、Node 浏览器 276 项、真实设置和运行设置 20 项、真实通知 3 项通过。验证了桌面及 390px 的设置直接应用、按原请求核实丢回包，以及旧草稿 API、CLI 与包格式拒绝。
- 用真实 Base 库的临时副本验证切换。确认后移除未发布记录，保留已发布版本、相关审计、任务固定引用及结果。异常引用阻止切换，写入失败完整回滚。
- 证据位于本地 `.git/validation-evidence/039284e2cfb44ece7b4625d7b50bdcd02691ecb3/b-review/` 和 `.git/validation-evidence/fa8f9dd8c3be69bf6460cd38335f03709fac71c1/b-review/`。验证使用本地隔离环境。
