# Task 57.1 — 从空实例创建管理员并完成 Web 登录

Next Action: B REVIEW TASK57.1

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

- 实现候选：`5028fa595cc5d3cfb557a020225ab43651201518`（Task Base
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
  同时核对 `/api/auth/session` 归属只读账号。
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

## PATCH-20261120-5 — 彻底退役配置草稿 — B PASS

- 复核范围为 `e279077c4bca208ab7168983d15eca66ec8833d1..039284e2cfb44ece7b4625d7b50bdcd02691ecb3`，实现版本为 `2837d9bc6c0dcc1360b02ccf659922a121bba667`。独立 Task 验收完成。实施计划及交付记录见 `039284e2:TASK.md`。
- 真实部署验收通过。无媒体挂载的新实例从系统设置初始化空配置。有媒体挂载的实例直接发布完整配置，并用原进程完成整理和两类库复制。部署指引和生成脚本帮助与实际操作一致。
- 候选的 Docker 健康、重启与故障、发布安全和 wheel 安装冒烟通过。撤销来源目录权限时，只读检查报告权限不足，API 仍在线。恢复权限后复查通过，生效版本和任务清单一致。容器部署 15 项、配置状态与配置包 27 项定向用例通过，改动脚本的 Ruff、编译以及完整范围的 `git diff --check` 通过。
- 产品、Web、产品测试和示例配置与 `fa8f9dd8` 一致。复用该版本的 B 全量证据。Python 执行 2327 项，7 项跳过，其余通过。Web 单测 1594 项、Node 浏览器 276 项、真实设置和运行设置 20 项、真实通知 3 项通过。验证了桌面及 390px 的设置直接应用、按原请求核实丢回包，以及旧草稿 API、CLI 与包格式拒绝。
- 用真实 Base 库的临时副本验证切换。确认后移除未发布记录，保留已发布版本、相关审计、任务固定引用及结果。异常引用阻止切换，写入失败完整回滚。
- 证据位于本地 `.git/validation-evidence/039284e2cfb44ece7b4625d7b50bdcd02691ecb3/b-review/` 和 `.git/validation-evidence/fa8f9dd8c3be69bf6460cd38335f03709fac71c1/b-review/`。验证使用本地隔离环境。
