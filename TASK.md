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

#### B 评审结果

```text
Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..8c0e2c850de370e4c2f832deb3c1454b95f61ee1
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P0｜空库首页无法创建首位管理员，有效会话也无法恢复。** 使用仓库生成的最小配置启动
  空 SQLite 库，主机成功签发设置码。服务端状态显示需要创建管理员，390px 浏览器打开
  根地址只看到账号密码登录，没有设置码输入。通过正式设置 API 建立隔离夹具后，同一浏览器
  新开任务中心仍跳到登录页，服务端确认 Cookie 对应的会话仍有效。
- **P1｜已接受的中文密码无法在网页改密。** 初设接受中文密码，用户能用它从首页登录。
  从账号菜单进入「改密码」并提交后，服务端返回 500，旧会话仍然有效。
- **P1｜经 HTTPS 登录时，会话 Cookie 缺少 Secure。** 浏览器通过本地 TLS 反向代理
  打开生产 Web，勾选保持登录并成功登录，真实会话 Cookie 有 HttpOnly 和到期时间，
  缺少 Secure。
- **P1｜非容器启动及新配置仍接收退役字段。** 以候选生成器创建最小部署配置，在隔离
  目录用此前随仓示例的 `api.principals` 校验及发布业务配置，校验成功且发布结果是
  Active。用原启动配置在本机执行 `mediaflow api serve` 也能启动。Compose 预检
  已拒绝该字段，本机启动与新配置输入需要给出同样明确的删除指引。

#### Developer 返工指导

1. 在真实 Web 启动时触发一次 `/api/auth/status`，状态返回后再显示首位设置、登录或
   继续已有会话。用现有根路由与共享认证边界处理重试和深链回跳。首位设置成功后进入
   系统设置，退出后根入口显示登录。有效会话刷新及新标签保留原站内页面和允许的查询参数。
   会话失效后，使用原有受理结果查询恢复业务上下文。
2. 让改密和初设、登录、重置接受同一密码字符范围。用 UTF-8 字节处理新旧密码相等的
   比较，沿用现有改密事务写入新密码并撤销旧会话。回归中文旧密码改为中文新密码、
   同密码提示、新密码可登录和旧会话失效。
3. 在生产 Waitress 入口落实部署指南的 HTTPS 代理配置。让经可信 TLS 代理的请求以
   HTTPS 签发会话 Cookie，同时保留回环 HTTP。用真实生产监听器和 TLS 代理验证登录
   及改密等同源写入，核对浏览器收到的 Cookie 属性。同步反向代理配置说明。
4. 在当前启动和新配置输入的共同边界拒绝 `api.principals` 与 `api.tokenEnv`，
   将提示指向具体应删除的键。覆盖本机启动、Compose 预检、`config validate`、
   `config publish` 和系统设置的完整配置输入。验证拒绝后完整保留原数据库和 Active。
5. 把现有浏览器测试夹具接到账号登录和会话，保留深链、权限和原请求核对的业务断言。
   补上本 Task 已约定的真实 Python 浏览器用例，从打开空库首页开始，由 Web 入口读取
   服务端认证状态。开发者按上节命令跑受影响测试，并执行
   `.venv/bin/python -m unittest discover -s tests -p test_api_credentials.py`、
   `.venv/bin/python -m unittest discover -s tests -p test_management_setup.py`，
   以及 `web/` 下的
   `npm run test:e2e -- tests/e2e/deep-link.spec.ts` 和
   `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/web-account-auth.python.spec.ts`。

生产 Web 构建通过。B 使用正式产物、Chromium、真实 Python 与隔离 SQLite 复现上述
用户旅程。现有 `deep-link.spec.ts` 的定向用例 1 项失败，仍等待已退役的令牌表单。
本轮按工作流在复现阻塞后结束验收，完整 T4、Compose、wheel、真实 Scheduler／Worker
和原请求非重放验收留待修正候选。日志位于
`.git/validation-evidence/8c0e2c850de370e4c2f832deb3c1454b95f61ee1/b-review/`。

Slice 57 的 RO-1 首位设置、会话恢复、改密和 HTTPS 会话尚未达标。RO-2 的用户管理、
角色与脚本令牌后续交付。RO-3 已提供空库在线入口，退役配置字段验收未达标，同版本重启和
后台按当前账号权限处理原工作待实测。

**Developer 返工交付记录（READY FOR B REVIEW）**

- 实现候选：`0847a1d918aca6e98930181e7e0f5d4ac8d3746c`（Task Base
  `4566a74055c698aec704215dd431eb8521bcfedb`）。保留原 Slice 合同、原评审记录和
  未授权范围；本记录只覆盖 B 的 P0/P1 返工指导。
- P0 修复：认证 store 从 `restoring` 开始，共享认证边界在根入口、受保护路由和未知路由
  每次加载都先读取 `/api/auth/status`；空库先显示首位设置，有效 Cookie 刷新和新标签
  直接恢复深链。未知路由也显示真实账号状态，不再永久停在「Checking sign-in」。
- P1 修复：改密的新旧密码相等比较改为 UTF-8 字节，中文旧密码到中文新密码、同密码
  提示、新密码登录和旧会话撤销均有服务端与真实浏览器用例。
- P1 修复：生产 Waitress 保留可信代理转发的 `X-Forwarded-Proto`，应用只对回环/私有
  代理 peer 采信 HTTPS，签发 `HttpOnly; SameSite=Lax; Secure` 会话 Cookie；回环 HTTP
  不标记 Secure。部署指南补充 `Host` 与 `X-Forwarded-Proto` 反向代理配置。
- P1 修复：启动、`config validate`、`config publish`、系统设置完整配置输入统一拒绝
  `api.principals` 与 `api.tokenEnv`，提示具体删除键和主机设置码入口；拒绝不创建
  数据库、不改变 Active。历史不可变 Active 的既有权威仍只读兼容。
- 测试夹具：Node fake 与真实 Python harness 都改为真实账号登录和 HttpOnly 会话；
  `deep-link.spec.ts` 覆盖空库/登录/深链/刷新/新标签/退出/401/403/恢复/无重放。
  新增 `scripts/web_account_auth_harness.py` 与
  `web/tests/e2e/web-account-auth.python.spec.ts`，从隔离空 SQLite 首页开始，覆盖
  首位设置、深链、重启、中文改密、主机重置码和旧会话撤销。
- 实际验证：
  - `test_web_account_auth` 15 项、`test_api_security` 13 项、
    `test_container_deployment` 15 项、`test_container_probe` 12 项、
    `test_execution_authorization` 10 项、`test_api_credentials` 8 项、
    `test_management_setup` 17 项、`test_configuration_snapshot` 41 项通过。
  - Web 单测 1599 项、完整 Node E2E 278 项通过；`npm run typecheck`、`lint`、
    `format:check`、`build` 通过。
  - `web/tests/e2e/deep-link.spec.ts` 15 项通过；真实 Python/SQLite
    `web-account-auth.python.spec.ts` 4 项通过。
  - 真实 Waitress 监听器加 `X-Forwarded-Proto: https` 登录返回带 `Secure` 的会话
    Cookie；`ruff format --check`、`ruff check`、`compileall`、`pip check`、
    `git diff --check`、治理检查 PASS；两份示例配置 `config validate` 通过。
- 剩余风险：其他真实 Python 浏览器 spec 的独立 harness/config 组合未在本轮逐个重跑；
  Docker 多角色发布安全脚本和部分诊断脚本仍按已退役的多角色环境令牌模型编写，属 Slice
  后续账号管理范围。B 应按本 Task 新链路使用隔离空库、真实 Compose 和候选镜像验收，
  不应以旧多角色脚本作为本 Task 的通过条件。真实 Compose、wheel、Scheduler/Worker
  账号权限实测仍由 B 完成。

#### B 复核结果

```text
Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..42ee79cb5237a091f0c13cdd6d2b065976c8bda6
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 多标签账号切换后仍显示上一位用户。** 同一浏览器用管理员打开任务中心，在另一个
  标签页退出并以只读账号登录，再回原标签页点击「刷新」。`/api/operations/runs`
  返回 200，会话状态是只读账号，原页面仍显示 `admin`。两个标签共享 Cookie，原标签
  的账号和查询缓存只在它自己的认证状态改变时更新。
- **P1 本机 Worker 和 Scheduler 启动仍接受旧启动配置。** 使用上一版本生成器输出的
  `api.principals` bootstrap，分别启动本机 API、Worker、Scheduler。API 退出并指明
  要删除的键，两个后台进程却创建数据库、继续运行，并只提示业务配置不可用。常驻进程
  直接使用旧 bootstrap 加载分支，跳过了新校验。

#### Developer 本轮返工指导

1. 在共享认证层接通同一浏览器各标签的登录与退出状态。账号变化后用现有
   `/api/auth/status` 确认当前身份，再恢复受保护页面。按原账号清理查询缓存和会话上下文，
   按当前账号重新读取页面，保留允许的路由和查询参数。用已有真实 Python 夹具中的
   管理员和只读账号回归「标签 A 打开任务中心 → 标签 B 退出并以只读账号登录 → 标签 A
   刷新任务中心」，断言页面账号、可用操作和读取结果归属一致。
2. 将退役身份字段的现行校验接到本机常驻服务读取 bootstrap 的入口，在打开数据库前
   给出包含具体删除键的错误。覆盖 `worker run`、`scheduler run` 和共用此入口的
   `notification-worker run`。用旧生成器产物复测启动拒绝，再用当前生成器的最小配置
   验证常驻服务可正常等待首次业务配置。
3. Developer 执行受影响的
   `.venv/bin/python -m unittest discover -s tests -p test_resident_services.py`、
   `.venv/bin/python -m unittest discover -s tests -p test_api_credentials.py`，
   以及 `web/` 下的
   `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/web-account-auth.python.spec.ts`。
   在交付记录中列出新增的双标签场景以及本机启动拒绝的结果。

B 独立运行生产 Web 构建、真实 Python/SQLite 认证浏览器用例 4 项、深链浏览器用例
15 项、API 凭证用例 8 项。打开 HTTPS 生产入口创建管理员成功，在系统设置初始化空配置
成功，浏览器会话 Cookie 有 Secure、HttpOnly 和 SameSite=Lax。本机 API 已拒绝旧字段。
多标签切换和本机常驻启动的实测支持上述结论。按工作流在复现阻塞后结束本轮验收，
完整 T4、Compose、wheel、Scheduler／Worker 运行权限和原提交结果核对待修正候选。
日志位于 `.git/validation-evidence/42ee79cb5237a091f0c13cdd6d2b065976c8bda6/b-review/`。

Slice 57 的 RO-1 已验证上述设置、登录恢复与改密旅程，账号切换尚未达标。RO-2 用户管理
和脚本令牌仍待后续 Task。RO-3 的本机常驻启动与实作重启验收仍有缺口。

**Developer 返工交付记录（READY FOR B REVIEW）**

- 实现候选：`cae11b421552293be43a0159d73f860825872fc0`（Task Base
  `4566a74055c698aec704215dd431eb8521bcfedb`）。保留原 Slice 合同、原评审记录和
  未授权范围；本记录只覆盖 B 本轮的两项 P1 返工指导。
- P1 多标签账号切换修复：新增同源 `BroadcastChannel` 的非秘密会话变更信号；登录、退出、
  改密和主机重置成功后通知其他标签，其他标签用现有 `/api/auth/status` 确认当前身份。
  后台恢复的标签在可见/重新聚焦时也会确认，覆盖错过广播的悬挂页面。确认到不同账号或
  角色/权限集合后，同步清理上一账号的浏览器上下文（含 React Query 缓存），推进权威
  generation 并只让受保护页面按原 URL 路径和允许的查询参数重新挂载读取；相同账号确认
  不触发缓存或请求栅栏抖动。没有把 Cookie 或账号秘密放入存储或跨标签消息。
- P1 本机常驻启动修复：`worker`、`scheduler`、`notification-worker` 的 bootstrap
  读取分支与 API／配置入口使用同一退役字段校验，在打开数据库前拒绝 `api.principals`
  与 `api.tokenEnv`，错误包含应删除的具体键。旧生成器产物不再创建数据库或继续常驻；
  当前生成器的 locator-only bootstrap 继续正常等待首次业务配置。
- 测试夹具：`test_resident_services` 改用当前生成器的最小 bootstrap；新增旧产物对
  `worker run`、`scheduler run`、`notification-worker run` 的拒绝用例，逐项断言退出码、
  删除指引和数据库未创建。真实 Python harness 增加隔离只读账号夹具控制；
  `web-account-auth.python.spec.ts` 新增「标签 A 管理员打开任务中心 → 标签 B 退出并以
  只读账号登录 → 标签 A 返回、账号更新为 readonly 并刷新任务中心」的真实浏览器场景，
  同时核对 `/api/auth/session` 的账号、`viewer` 角色和只读权限归属。
- 实际验证：
  - `test_resident_services` 29 项、`test_api_credentials` 8 项、
    `test_web_account_auth` 15 项、`test_api_security` 13 项、
    `test_container_deployment` 15 项、`test_container_probe` 12 项、
    `test_execution_authorization` 10 项、`test_management_setup` 17 项、
    `test_configuration_snapshot` 41 项通过。
  - Web 单测 1601 项（104 个文件）通过；`npm run typecheck`、`lint`、
    `format:check`、`build` 通过。
  - 真实 Python/SQLite `web-account-auth.python.spec.ts` 5 项通过（含新增双标签场景）；
    正式产物下 `deep-link.spec.ts` 15 项通过。
  - 改动 Python 文件的 Ruff 格式与检查、`compileall`、`git diff --check` 通过；
    治理检查 PASS。
- 剩余风险：完整 T4 全量 Python、真实 Compose、候选镜像、wheel、真实 Scheduler／Worker
  账号权限运行验收和其他真实 Python 浏览器 spec 未由 Developer 执行，按工作流留给 B
  独立验收。Docker 多角色发布安全脚本和部分诊断脚本仍按后续账号管理范围处理。

#### B 回归复核结果

```text
Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..e85752e7c11f545d59328278915f5280fd44132b
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1｜Python 回归未走到当前业务入口。** 全量执行 2,344 项，10 项断言失败、143 项报错、
  7 项跳过。152 项失败或报错来自测试准备阶段提交的旧 `api.principals`，剩余 1 项来自
  Worker 夹具读取当前 bootstrap 已移除的 `api` 节。比如「用有效账号启用自动化 → 由
  Scheduler 受理 → 收回权限 → 下一次执行被拒绝」的用例在准备 Active 时已停止，尚未
  检查后台行为。
- **P1｜任务中心的真实浏览器回归仍按旧登录流程计数。** 用例从登录前开始记录请求。
  新账号登录发出的 `POST /api/auth/login` 被计入「打开任务详情和刷新」的只读断言，
  这次 POST 来自登录表单。实测 6 项通过，任务中心该用例失败，49 项在首个失败后未执行。

#### Developer 回归修正指导

1. 迁移 Python 日志中失败的 12 个模块共用的准备步骤。用当前生成器的最小配置或其等价
   locator-only 夹具建立数据库，以测试账号和当前角色验证需要身份的业务路径。在执行权限
   用例中通过数据库账号角色变化回归授权、撤权和明确拒绝，沿用现有任务、固定快照、效果及
   非重放断言。旧字段用在专门验证退役拒绝的输入中。
2. 让任务中心回归先完成登录，再记录打开列表、详情和刷新的全部请求，继续断言该阶段只有
   GET。把刷新与显式会话失效作为各自的测试动作。刷新验证原页与查询参数，失效后重新登录
   验证恢复原任务和核对原请求，保留执行次数和效果断言。
3. 同步 `docs/deployment.md` 的前置步骤与 README 现行入口。用最小配置启动 Compose，
   在容器内领取设置码，通过首页创建管理员，再进入系统设置初始化。
4. Developer 运行受影响的 Python 模块。首轮可按文件执行
   `.venv/bin/python -m unittest discover -s tests -p test_v2_automation_lifecycle.py`、
   `.venv/bin/python -m unittest discover -s tests -p test_automation_execution_intent.py` 和
   `.venv/bin/python -m unittest discover -s tests -p test_automation_settings_resident.py`。
   在 `web/` 运行
   `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`。
   B 负责下一候选的完整回归与发布验收。

上轮两项阻塞通过定向复测。真实 Python/SQLite 登录旅程 5 项通过，包含双标签账号切换并核对
只读角色。常驻服务 29 项通过，覆盖三种本机命令在打开数据库前拒绝退役字段。生产 Web
构建、wheel 构建及源码目录外安装冒烟通过。真实系统设置浏览器用例 5 项通过，含丢失发布
回包后的原请求核对。完整 T4、Compose、真实 Scheduler／Worker 执行和整理提交的不重放
验收待修正候选。日志见
`.git/validation-evidence/e85752e7c11f545d59328278915f5280fd44132b/b-review/`。

Slice 57 的 RO-1 已通过本轮设置、会话恢复、改密和账号切换定向验证。RO-2 的用户管理与
脚本令牌待后续 Task。RO-3 的本机启动校验已通过，后台执行和部署验收待完成。


**Developer 回归修正交付记录（READY FOR B REVIEW）**

- 实现候选：`4eaeace9b1fba53691f232d26c7e0a85875a4981`（源码修正
  `924847ceec0f4d0e5d58125cc7b16a872e5d7124`，本轮起点 `4181183f`，Task Base
  `4566a74055c698aec704215dd431eb8521bcfedb`）。保留原 Slice 合同、原评审记录和
  未授权范围；本记录只覆盖 B 本轮回归修正指导。
- Python 回归修正：新增 `tests/account_fixtures.py`，通过真实 repository 创建账号并用
  `AccountService.login` 签发会话；迁移 B 点名的 12 个失败模块及共享媒体发现 fixture，
  删除测试配置中的 `api.principals`，业务请求改用数据库账号 Cookie 和当前角色。
  执行权限用例通过隔离夹具更新同一持久账号的角色，验证授权、撤权和明确拒绝；旧字段只
  保留在专门的退役拒绝输入。账号管理入口属于后续 Slice，fixture 的角色变更不是产品入口。
- 浏览器任务中心修正：任务中心只读回归先完成真实登录再记录请求；刷新保留原目录、任务和
  允许的查询参数，显式退出后重新登录核对原任务及原请求，执行次数和效果断言保持。
  `reconnectAtCurrentRoute` 同时支持有效会话直接恢复和失效后的登录表单。harness 的托管
  配置去除了退役身份字段，真实 Worker 的自动执行重新读取当前 Active。
- 同步测试夹具到现行入口：共享真实 Python harness 使用账号会话，保留直接 API 断言所需的
  focused principal；修正退役 `/ui` 为当前入口文档、非 GET 静态请求、资源库引用计数、
  双 Webhook 投递和 definition-bound Worker 等过期夹具断言。Unicode 主身份浏览器用例
  也改为有效会话刷新后直接恢复。
- 文档：`docs/deployment.md` 的前置步骤改为 locator-only 生成、主机设置码、首页创建首位
  管理员再初始化系统设置；README 现行入口已一致，无额外改动。
- 实际验证：
  - 定向 Python：12 个回归模块 209 项、`test_automation_settings_resident` 25 项、
    `test_web_account_auth`／`test_api_credentials`／`test_management_setup`／
    `test_api_security`／`test_execution_authorization`／`test_resident_services`／
    `test_container_deployment`／`test_container_probe`／`test_configuration_snapshot`
    160 项，共 394 项通过。
  - Web：身份与入口定向单测 43 项通过；`npm run typecheck`、`npm run build`、Prettier
    与 ESLint 改动文件检查通过。
  - 真实 Python/SQLite：`operations-inventory.python.spec.ts` 51 项通过（含登录后记录、
    刷新、显式退出重登、深链和原请求核对）；Unicode 主身份浏览器用例 1 项通过。
  - `ruff check`、`ruff format --check`、`compileall`、`git diff --check`、治理检查 PASS。
- 剩余风险：完整 T4 Python、真实 Compose、候选镜像、wheel、真实 Scheduler／Worker
  账号权限执行验收仍由 B 执行；本轮未重跑其余真实 Python 浏览器 spec。真实 harness 仍保留
  仅供直接 API 夹具断言使用的 focused principal，浏览器旅程已全部使用数据库账号会话。

#### B 复核结果

```text
Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..a0ec018c16946cf60de0b1d36bb377cc10e78a4a
Implementation: 4eaeace9b1fba53691f232d26c7e0a85875a4981
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1｜新镜像启动时改写了上一版本的数据库。** 用 Task Base 的仓库生成器和真实 API
  启动并停止上一版本，保留它创建的 SQLite 文件。用本候选生成最小启动配置，在 Compose 中
  挂载这份数据目录的隔离副本。新 API 正常监听，`/health` 返回 200 并显示等待首位管理员。
  SQLite 的 runtime 版本由 `58` 变为 `59`，文件的 SHA-256 随之改变。Slice 57 的部署
  边界要求在启动前拒绝这份库、保留原文件，并指引部署者使用新空目录。

#### Developer 修正指导

1. 在现有部署预检的数据库适用性判断中落实 Slice 57 的范围。启动只接收空库和本版本创建的
   数据库。使用上一版本生成器和 API 创建的库时，在初始化仓库或启动服务前退出，说明当前
   数据目录不适用，指引使用新空目录。当前预检沿用最低 runtime 版本 `58` 的通用判断，
   仓库打开后补建认证表并将版本写成 `59`。
2. 在 `test_container_deployment.py` 或现有预检用例中覆盖真实上一版数据库的拒绝，核对
   退出结果、提示和文件哈希。覆盖空库启动以及本版本创建的库带着账号和 Active 重启后仍可用。
   同步 `docs/deployment.md` 的部署边界与失败后的操作指引。
3. Developer 执行 `.venv/bin/python -m unittest discover -s tests -p test_container_deployment.py`
   和 `.venv/bin/python -m unittest discover -s tests -p test_container_probe.py`，在候选
   镜像上复测上述启动旅程。B 负责修正候选的完整验收。

上轮两项回归已恢复。Python 全量执行 2,344 项，7 项跳过，其余通过。Web 单测 1,601 项、
Node 浏览器 279 项、真实 Python/SQLite 浏览器 61 项通过。本轮核对了任务中心登录后只读刷新、
重登恢复查询及原任务、整理请求丢回包后的结果核对，以及数据库账号撤权的 Python 回归。
生产 Web 构建、Python/Web 静态检查、示例配置校验、wheel 构建和源码目录外安装冒烟通过。
候选镜像 `sha256:4510c185ebb29e36c99d00d52683e2119c0f4390fe37845b026ff0bdd793d46c`
通过了 Compose 空库四服务启动、首位管理员创建、空配置发布、API 重启后恢复书签会话、
网页改密、主机重置和旧会话撤销。旧环境令牌访问任务接口返回 `401`。此前浏览器尝试的等待
超时和设置码解析失败保留日志，后续使用主机 CLI 的 JSON 输出从新空库重跑成功。

Slice 57 的 RO-1 首位设置、会话恢复、改密和重置已通过上述旅程。RO-2 用户管理与 API
令牌仍待后续 Task。RO-3 的旧库启动拒绝尚未通过。实作 Scheduler／Worker 撤权执行和
剩余发布安全验收待修正候选。原始证据位于本地
`.git/validation-evidence/a0ec018c16946cf60de0b1d36bb377cc10e78a4a/b-review/`，
其中 `compose-prior-release-startup.log` 记录旧库启动及文件哈希。

**Developer 修正交付记录（READY FOR B REVIEW）**

- 实现候选：`5d7fcfb0f708c0dab3aa771c352310f0d96fdd51`（Task Base
  `4566a74055c698aec704215dd431eb8521bcfedb`）。保留原 Slice 合同、原评审记录和
  未授权范围；本记录只覆盖 B 本轮指出的上一版本数据库启动阻塞。
- 根因与修复：适用性判断只检查最低 runtime 版本 `58`，因此上一版本的 `58` 库被接受，
  仓库随后补建认证表并把版本写成 `59`。现在启动边界只接受空库或当前 runtime schema
  创建的库；低于当前版本的运行时库在初始化仓库、容器预检或本机 API 启动前拒绝，错误
  给出 found/expected schema，并指引使用新的空数据目录。拒绝发生在任何建表或标记写入
  之前，原文件字节保持不变。容器预检、健康探针、本机 API 与配置/任务仓库共用同一判断。
  配置 schema 11 的显式 data switch 仍限 runtime schema 缺失或已当前的库；旧 runtime
  库不再进入该切换。部署、配置、架构与发布边界文档已同步。
- 定向 Python：`test_container_deployment` 17、`test_container_probe` 12、
  `test_task_persistence` 22、`test_configuration_status` 15、`test_api_credentials` 8、
  `test_web_account_auth` 15、`test_management_setup` 17、`test_sqlite_restore` 5、
  `test_api_security` 13，共 124 项通过。新增用例覆盖上一版本 runtime 库的预检、仓库、
  本机 API 拒绝与文件哈希不变，以及空库和带账号/Active 的当前库同版本重开。
- 真实上一版本库：从 Task Base `4566a740` 的旧代码创建 runtime `58` 库（无认证表），
  候选预检、仓库与本机 `api serve` 均在写入前拒绝；错误含 found/expected 与新空目录
  指引，库 SHA-256 保持
  `22c825ef4a764bfbbd84476202c436feec99547643846c2eddfe4f024c6cbe35`。
- 候选镜像 `mediaflow:task571-prior-db-fix`
  （`sha256:09cb1fe4b9a516ac931ba6c54429896e29e1b340764c945c9116d782d9d657fb`）：
  直接以生产入口启动上一版本库时退出 `1`，预检给出同一拒绝和新空目录指引，文件哈希不变；
  空库启动后 `/health` 返回等待首位管理员与业务配置，库标记为 configuration 12 /
  runtime 59；当前库带管理员和 Active 启动、登录、停止并以同一数据目录重启后，`/health`
  与实际登录会话仍归属该管理员，Active 仍为 1 条。
- 静态检查：改动 Python 文件 `ruff format --check`、`ruff check`、`compileall`、
  完整范围 `git diff --check` 与治理检查 PASS。未改 Web 产物或前端源码，本轮未运行 Web
  单测、Lint 或浏览器用例。
- 剩余风险：完整 T4、四服务真实 Compose、wheel/源码外安装、真实 Scheduler／Worker
  权限执行、生产 Web 浏览器旅程及其他真实 Python spec 仍由 B 在修正候选上独立验收。
  Developer 本轮只做了单容器生产入口复测，未运行完整 Compose 矩阵。证据位于本地
  `.git/validation-evidence/task57.1-prior-db-recheck/`。

#### B 复核结果：上一版本仅初始化配置的数据库

```text
Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..04d917e180ca24557b6bf96fb105469607570f89
Implementation: 5d7fcfb0f708c0dab3aa771c352310f0d96fdd51
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1｜旧版只初始化配置的数据目录仍会被新版本改写。** 部署者可以按旧版配置指南生成最小
  启动配置，执行 `mediaflow config initialize`，稍后再启动服务。B 用 Task Base 的 CLI
  执行这一步，得到已有 Active、只有配置版本 `12` 的 SQLite 库。换用候选镜像和新版本的
  最小配置挂载该目录后，Compose API 正常监听。`/health` 显示已有业务配置、等待首位管理员，
  数据库增加了 `runtime 59`，文件 SHA-256 也发生变化。Slice 57 要求拒绝该数据目录，
  保留原文件并提示使用新空目录。
- 候选 `5d7fcfb0` 在 2026-11-22 加入的限制仅检查已有的 runtime 标记。旧版 `config
  initialize` 是现有 CLI 入口，通过配置仓库发布 Active，不创建 runtime 标记。新预检把这份
  库当成可启动数据，随后 API 打开仓库并建立运行时及账号表。

#### Developer 修正指导

1. 让本版本的 `config initialize` 和 `config publish` 首次创建数据库时留下能表明本版本
   创建来源的标记。按现有数据库适用性入口检查该标记。在任何建表前拒绝旧版 CLI 创建的仅配置
   数据库，提示保留旧文件并使用新空目录。同步部署与配置指南所列的可启动范围。
2. 用 Task Base 的生成器和 `config initialize` 生成旧版夹具，验证 Compose 预检退出、没有
   API 监听、数据库文件哈希一致。保留已有 `runtime 58` 拒绝测试。用本版本的相同 CLI
   流程验证首次启动读取原 Active，然后创建管理员并重启，确认账号和 Active 可用。
3. Developer 运行 `test_container_deployment.py`、`test_container_probe.py` 和
   `test_configuration_status.py`，并记录以上两条部署旅程。B 负责修正候选的 T4 验收。

B 独立使用候选镜像 `sha256:09cb1fe4b9a516ac931ba6c54429896e29e1b340764c945c9116d782d9d657fb`
复测。旧版 API 创建的 `runtime 58` 库在 Compose 预检退出 `1`，文件哈希一致，日志给出
新空目录指引。空数据目录可启动并显示等待首位管理员和业务配置。首次探测复用了上一版本的
测试端口，无法判断响应归属。证据以每个场景分配独立端口后的复测为准。原始记录位于本地
`.git/validation-evidence/04d917e180ca24557b6bf96fb105469607570f89/b-review/`，
其中 `config-only-r2-verified-health.json` 与相应的 schema、SHA-256 日志记录本轮阻塞。

RO-1 的既有浏览器证据保留，RO-2 用户管理和 API 令牌仍待后续 Task。RO-3 的旧库拒绝待
修正，本轮以已复现的阻塞结束验收。当前候选的完整 T4、同版本浏览器重启及实际
Scheduler／Worker 撤权执行仍待验收。

**Developer 修正交付记录（READY FOR B REVIEW）**

- 实现候选：`da0b246054d7f5faa8279672a4c7a46b682728b4`（Task Base
  `4566a74055c698aec704215dd431eb8521bcfedb`）。保留原 Slice 合同、原评审记录和
  未授权范围；本记录只覆盖 B 本轮指出的仅配置旧库启动阻塞。
- 根因与修复：配置 schema 12 在各版本间未变，上一版本 `config initialize`／`config
  publish` 创建的仅配置库只有配置标记，没有可区分创建来源的记录；候选按通用配置版本
  接受后补建 runtime 表并写入 `runtime 59`。现在本版本首次创建数据库（配置仓库或运行时
  仓库）在同一事务写入 `store_origin`，其值为创建构建的 runtime schema；共享适用性入口
  在打开仓库、容器预检、健康探针、`config status`／`config publish` 和本机启动时要求
  仅配置库带有当前来源标记。缺少标记的旧库在任何建表、标记或监听前退出，错误保留
  found/expected 配置版本、缺少来源标记和新的空数据目录指引。
- 已接受的配置 schema 11 显式 data switch 保留：其事务在把受支持的旧库改写到当前布局时
  一并记录当前来源标记，所以文档中的切换后启动仍然有效；普通打开旧库不会进入该分支。
  自动启动边界仍只接受空库或本版本创建的库。
- 定向 Python：`test_container_deployment` 19 项、`test_container_probe` 12 项、
  `test_configuration_status` 15 项、`test_api_credentials` 8 项；此前直接受影响的
  `test_task_persistence` 22、`test_configuration_snapshot` 41、`test_api_security` 13、
  `test_web_account_auth` 15、`test_resident_services` 29、`test_sqlite_restore` 5、
  `test_sqlite_backup` 3 项通过。新增用例覆盖旧仅配置库的预检／配置命令／仓库／本机 API
  拒绝与文件哈希不变，以及本版本 CLI 首次建库读取 Active、建首位管理员并同版本重开。
- 真实旧库：从 Task Base `4566a740` 的代码与生成器执行 `config initialize`，得到只有
  `configuration_management 12` 和一条 Active、无 runtime／来源标记的库，SHA-256 为
  `1b3cfeffeb066ddf1a7cb1657d9e1135751ebb6ac89a71240dfa813cd5cba7d5`。候选容器入口
  预检退出 `1`，本机 `api serve` 退出 `2`，端口未监听；`config status`／`config publish`
  退出 `2`；每次拒绝后哈希保持上述值，标记仍只有配置 12。
- 当前 CLI 旅程：用本版本生成器生成最小 bootstrap，`config initialize` 留下
  `configuration_management 12` 与 `store_origin 59`；真实本机 API 首次启动读取原 Active
  （`/health` 的 `configurationRequired=false`），主机签发设置码后经 HTTP 建立首位管理员，
  停止并以同一数据目录重启后 `/api/auth/session` 仍返回该管理员，账户数与 Active 各为 1。
- 静态检查：改动 Python 文件 `ruff format --check`、`ruff check`，完整 `compileall`、
  `git diff --check` 和治理检查 PASS。
- 剩余风险：完整 T4、四服务真实 Compose、候选镜像、wheel/源码外安装、正式 Waitress
  生产入口、Web 浏览器与其他真实 Python spec 仍由 B 在修正候选上独立验收。Developer 本轮
  未构建镜像；旧库验证使用本机容器入口与本机 API，不替代 B 的 Compose 验收。
  测试只跑上述定向模块和两条真实旅程，未运行完整套件。

#### B 复核结果

```text
Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..8ed74bcc4ed6fc1d763f28cb8d8d9d603626474b
Implementation: da0b246054d7f5faa8279672a4c7a46b682728b4
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1｜启动服务会在确认配置切换前写入旧库。** 部署者按旧版配置指南运行 `config
  draft-import --file ...` 后，SQLite 保存了一个草稿，记录配置版本 `11`。B 用旧版
  `be55d699` 的生成器与 CLI 创建这份库，再用候选镜像和最小启动配置运行标准四服务
  Compose。API 与 Worker 提示等待确认切换后退出，Scheduler 与 Notification Worker
  继续运行。文件增加了 `runtime 59` 和 `store_origin 59`，SHA-256 也发生变化。部署者
  还没有执行 `config retire-unpublished --confirm`，库已被改写。
- 本候选 `da0b2460` 于 2026-11-22 加入库来源标记，配置版本 `11` 走原有待切换入口。
  Compose 的预检允许启动，后台服务先打开运行时仓库，再读取配置。运行时仓库在建表时
  写入来源标记，使普通启动提前改变仍在等待确认切换的文件。

#### Developer 修正指导

1. 在现有预检与本机常驻服务启动入口中识别待确认切换的配置库。普通服务启动应在打开
   运行时仓库前退出，保全原文件并准确指引下一步。将现有 `config status` 的只读范围
   检查和 `config retire-unpublished --confirm` 的原子切换留在各自的正式入口。
2. 用 `be55d699` 的生成器和 `config draft-import --file ...` 生成实际旧库。复测四服务
   Compose 启动，核对四个进程退出、原草稿与文件哈希保持一致。用另一份副本走文档里的
   显式切换，再验证启动和读取已发布配置。保留本轮已通过的两个旧库拒绝用例及当前版本
   从 `config initialize` 预置配置后启动的旅程。
3. Developer 运行 `test_container_deployment.py`、`test_container_probe.py`、
   `test_configuration_status.py` 和 `test_resident_services.py`，记录受影响的实际部署
   结果。B 负责修正候选的 T4 验收。

B 使用本轮源码构建候选镜像
`sha256:047d15904ab62b8075b3b8742f40b1bcdf7040edf9299848c60f3f76e9ff8db0`。
Task Base 生成的仅配置 `12` 库和 `runtime 58` 库均在 Compose 的四个服务预检中退出 `1`，
文件哈希一致。本机 `api serve` 也拒绝仅配置 `12` 的旧库。容器部署 19 项、健康探针
12 项及配置状态 15 项通过，Ruff、编译、依赖、治理和示例配置校验通过。
用默认容器 UID/GID 和独立卷通过新版 `config initialize` 创建 Active，四服务达到健康状态。
窄屏浏览器完成首位管理员设置，桌面读取已生效配置。四服务同版本重启后，书签、查询参数和
原账号会话恢复。首次测试为挂载宿主机目录改用了宿主 UID，镜像内网页文件不可访问，根页
返回 500。恢复默认 UID 与标准数据卷后通过同一旅程，原记录仍在 `current-compose-browser.log`。
本地日志目录为 `.git/validation-evidence/8ed74bcc4ed6fc1d763f28cb8d8d9d603626474b/b-review/`。
待切换旧库的结果见 `v11-compose.log`、`v11-state.json` 和 `v11-sha-before.log`、
`v11-sha-after.log`。

RO-1 的既有浏览器证据保留。RO-2 用户管理与 API 令牌待后续 Task。RO-3 的四服务旧库
启动仍有阻塞，本轮完整 T4 与实际 Scheduler／Worker 撤权执行待修正候选。

**Developer 修正交付记录（READY FOR B REVIEW）**

- 实现候选：`a639fa953afa1da781ebff61e2d7e9f08e88b26b`（Task Base
  `4566a74055c698aec704215dd431eb8521bcfedb`）。保留原 Slice 合同、原评审记录和
  未授权范围；本记录只覆盖 B 本轮指出的待确认配置切换启动阻塞。
- 根因与修复：上一版本 `config draft-import` 留下配置 schema 11 和未发布草稿，但
  没有 runtime／当前来源标记。容器预检按通用配置版本放行，Scheduler 与 Notification
  Worker 又从 bootstrap 直接打开运行时仓库，于是先写入 runtime 59 和 store_origin 59。
  现在共享只读检查在普通服务启动边界识别待确认切换：Compose 四服务预检和本机
  `worker/scheduler/notification-worker` 的 `run` 入口都在创建 runtime 表、来源标记或
  租约前退出，错误列出受影响 revision 并指向 `config status` 与
  `config retire-unpublished --confirm`。`config status` 仍只读，确认切换仍只在
  `retire-unpublished --confirm` 事务内发生；`api credentials check` 与配置管理命令
  不被误伤。
- 自动化用例：`tests/managed_config_fixture.py` 新增上一版本 draft-era 库夹具；
  `test_container_deployment` 覆盖四服务预检拒绝、文件哈希／标记不变、`config status`
  只读、副本显式切换后 Active 保留及四服务预检放行；`test_resident_services` 覆盖
  `worker run`、`scheduler run`、`notification-worker run` 在建表前退出且原文件不变。
- 真实旧库：从 `be55d699` 的生成器与 CLI 执行 `config draft-import --file`，得到只有
  `configuration_management 11` 和一条 draft、无 runtime／来源标记的库，SHA-256 为
  `12372b73825e3f976d08a79c5708392be69d87eb41eb6b79f833d291562b4b7d`。候选容器入口
  对 api／worker／scheduler／notification-worker 四个命令均退出 `1`，本机三个常驻
  `run` 均退出 `2`，错误包含草稿 revision 与两个下一步命令；每次拒绝后哈希保持上述值。
  另一份同源副本执行 `config status` 仍为哈希不变，`retire-unpublished --confirm` 后
  标记为 configuration 12／store_origin 59、草稿已移除；四服务预检全部通过。
- 带 Active 的旧库：同一旧版流程建立 Active 后再导入一份 draft，候选预检退出 `1` 且
  哈希 `c01e3289a79f020a4afa3e479696df1db4bf8b83a380c26c0c06ae8e317f4364` 不变。
  显式切换只移除 draft，保留原 Active 的 revision ID／digest；切换后 `scheduler tick`
  成功读取已发布 Active 并正常退出 `0`，四服务预检全部通过。
- 定向测试：`test_container_deployment` 20 项、`test_container_probe` 12 项、
  `test_configuration_status` 15 项、`test_resident_services` 30 项，共 77 项通过。
  改动文件的 `ruff format --check`、`ruff check`，完整 `compileall`、`git diff --check`
  与治理检查 PASS。
- 剩余风险：完整 T4、四服务真实 Compose、候选镜像、wheel／源码外安装、正式 Waitress
  入口、Web 浏览器及其他真实 Python spec 仍由 B 在修正候选上独立验收。Developer 本轮
  未构建镜像或运行 Compose；旧库验证使用本机容器入口与真实 CLI，证据位于本地
  `.git/validation-evidence/task57.1-pending-switch/`。

**Developer 实作复测记录（READY FOR B REVIEW）**

- 源码身份：实现候选 `a639fa953afa1da781ebff61e2d7e9f08e88b26b`（`91c23b00` 及本记录只
  更新文档）。Task Base `4566a74055c698aec704215dd431eb8521bcfedb`。本轮未改产品源码、
  Web 或测试。
- 候选镜像：从当前源码构建 `mediaflow:dev-task571-91c23b00`（本地镜像 ID
  `e56816566608`），仅用于真实四服务 Compose，未推送。
- 旧库夹具：沿用 `be55d699` 生成器与 `config draft-import --file` 产物，复制到隔离数据
  目录，SHA-256 `12372b73825e3f976d08a79c5708392be69d87eb41eb6b79f833d291562b4b7d`；
  标记为 configuration 11、草稿 `0997550f-a901-48cb-b212-9fa062bde1e1`，无 runtime／
  store_origin。
- 四服务拒绝：`compose.yaml` 加隔离数据/配置绑定启动 api、worker、scheduler、
  notification-worker，四项均为 `Exited (1)`；各自日志给出同一待切换错误、草稿 revision
  及 `config status`／`config retire-unpublished --confirm` 指引。API 端口未监听，
  数据库 SHA-256 和标记保持不变。为读取终态退出码，本次复测覆盖 `restart: "no"`；默认
  `unless-stopped` 会在同一只读拒绝上重试。
- 显式切换：同一副本 `config status` 退出 0 且哈希不变；`retire-unpublished --confirm`
  移除草稿，写入 configuration 12／store_origin 59。四服务随后 health 正常，`/health`
  显示等待首位管理员与业务配置。
- 带 Active 的副本：SHA-256 `c01e3289a79f020a4afa3e479696df1db4bf8b83a380c26c0c06ae8e317f4364`
  经同一显式切换保留 Active revision `f86724a2-5a9f-4d2e-88fc-d5e98d551978`／digest
  `6c468f55dce832ca4b83223e51477c16c5e38d205e2ae8aff8038463c2b3c38c`。四服务 health
  正常，`/health.configurationRequired=false`；匿名 `/api/tasks` 返回 `401`，
  `/api/auth/status` 仍要求首位管理员。
- 定向测试：`test_container_deployment` 20 项、`test_container_probe` 12 项、
  `test_configuration_status` 15 项、`test_resident_services` 30 项，共 77 项通过；
  `git diff --check` 与治理检查 PASS。证据位于本地
  `.git/validation-evidence/task57.1-a639fa95-compose/`。
- 剩余风险：完整 T4、B 的候选镜像／正式 Waitress／生产 Web 浏览器、wheel／源码外安装、
  真实 Scheduler／Worker 撤权执行仍由 B 验收；本记录只补四服务 Compose 的待切换旧库旅程。

## PATCH-20261120-5 — 彻底退役配置草稿 — B PASS

- 复核范围为 `e279077c4bca208ab7168983d15eca66ec8833d1..039284e2cfb44ece7b4625d7b50bdcd02691ecb3`，实现版本为 `2837d9bc6c0dcc1360b02ccf659922a121bba667`。独立 Task 验收完成。实施计划及交付记录见 `039284e2:TASK.md`。
- 真实部署验收通过。无媒体挂载的新实例从系统设置初始化空配置。有媒体挂载的实例直接发布完整配置，并用原进程完成整理和两类库复制。部署指引和生成脚本帮助与实际操作一致。
- 候选的 Docker 健康、重启与故障、发布安全和 wheel 安装冒烟通过。撤销来源目录权限时，只读检查报告权限不足，API 仍在线。恢复权限后复查通过，生效版本和任务清单一致。容器部署 15 项、配置状态与配置包 27 项定向用例通过，改动脚本的 Ruff、编译以及完整范围的 `git diff --check` 通过。
- 产品、Web、产品测试和示例配置与 `fa8f9dd8` 一致。复用该版本的 B 全量证据。Python 执行 2327 项，7 项跳过，其余通过。Web 单测 1594 项、Node 浏览器 276 项、真实设置和运行设置 20 项、真实通知 3 项通过。验证了桌面及 390px 的设置直接应用、按原请求核实丢回包，以及旧草稿 API、CLI 与包格式拒绝。
- 用真实 Base 库的临时副本验证切换。确认后移除未发布记录，保留已发布版本、相关审计、任务固定引用及结果。异常引用阻止切换，写入失败完整回滚。
- 证据位于本地 `.git/validation-evidence/039284e2cfb44ece7b4625d7b50bdcd02691ecb3/b-review/` 和 `.git/validation-evidence/fa8f9dd8c3be69bf6460cd38335f03709fac71c1/b-review/`。验证使用本地隔离环境。
