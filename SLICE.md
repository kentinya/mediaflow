# Slice 57 — 单管理员 Web 登录与分权限 API 令牌

```text
Slice ID: 57
Name: Single Web Administrator and Scoped API Tokens
Owner: A — Slice Owner / Architect / Final Reviewer
Status: FIX REQUIRED
Base SHA: ad7f29a1cc6d73ce17106b513f4b763cfd0c22ab
Implementation Head: 2b1042470765f5d9bf546780921de3fa499a0461
Working Branch: main
Development Authorization: ORIGINAL TASK57.1 CORRECTION SCOPE; B CORRECTION PLAN PENDING
Risk: High
Target Test Level: T4
Next Action: B PLANS TASK57.1 CORRECTION FOR A57-01 AND RENEWS SLICE CLOSURE PACKET AFTER ACCEPTANCE
```

## 授权与基线

用户要求从第一次纯净部署设计 Web 登录，退役 `api.principals` 与部署环境变量令牌认证。
Slice 的数据范围从空数据库开始，覆盖本版本创建的配置、管理员、令牌和工作，以及同版本重启后的
使用。本合同记录目标和验收，激活及 Task 规划按工作流进行。[Development Workflow](docs/development-workflow.md)

用户授权 A 代 B 规划首个 Task，并要求激活 Task 57.1。Developer 按既定 Task 范围实施，
B 独立验收，A 独立终审。A 代 B 的角色例外限于首个 Task 的规划。

用户授权 A 将产品范围调整为单管理员和分权限 API 令牌，并授权同步调整当前 Task。
Task 57.1 的登录、恢复和部署证据仍按对应提交核对。后台停止改以自动化停用入口验收。
Web 多用户管理延期，令牌管理继续作为本 Slice 的交付结果。

Task 57.1 已由 B 验收通过。用户已授权实施 [Task 57.2](TASK.md)。

规划基线为上面的 Base，规划前治理检查 PASS，工作区与暂存区干净。Slice 56 的关闭事实、
原验收范围和验证证据见固定终审。配置草稿退役的 B PASS 见当前 Task 指针。
[Slice 56 A Final Review](https://github.com/kentinya/mediaflow/blob/ce502d161dde1268fa26a8665db14cbb932f2e57/SLICE.md#a-final-review--pass--closed) · [TASK.md](TASK.md)

## 用户目标与范围

部署者从主机领取一次性设置码，在网页创建实例唯一的管理员。管理员用账号密码登录，刷新、
新开标签页和打开书签可沿用有效会话，过期后登录回到原位置。需要接入脚本时，管理员从
「系统设置 → API 令牌」按用途签发。只使用网页的实例可以直接完成部署和业务配置。

候选已接通数据库管理员会话、主机设置及重置码、系统设置的分权限 API 令牌和后台账号校验。
管理员从自动化编辑卡停用计划，在执行记录核对停止原因和原有结果。
[部署生成器](scripts/make_deployment_config.py) · [Web 登录入口](web/src/features/entry/EntryPage.tsx) · [执行权限检查](mediaflow/interfaces/service_api.py)

验收后以 `V2-AUTH-004/005/007–009` 取代 V2 的 `V2-AUTH-001/002` 身份和认证要求，更新
`V2-ROUTE-001/002/004` 的认证和恢复表述。后端业务裁决与 Storage 安全义务继续适用。
[目标要求](docs/v2-requirements.md#target--single-web-administrator-and-scoped-api-tokens-slice57-active) · [目标旅程](docs/product-experience.md#target--single-web-administrator-and-scoped-api-tokens-slice57-active) · [目标架构](docs/architecture.md#target--single-web-administrator-and-scoped-api-tokens-slice57-active)

## Required Outcomes and Surfaces

### RO-1 — 单管理员、日常登录和恢复

- 空实例可用最小部署配置启动。部署者凭主机上的本地管理权限取得短期
  一次性设置码，经根入口创建首位管理员。设置码与实例、用途绑定，领取与使用可审计。
  管理员创建和消耗码在同一事务内完成，并发提交只创建一个管理员。创建成功后进入系统设置
  初始化业务配置。此后的未登录访问从根入口进入登录页，主机可为同一管理员重置密码。
- 登录页提供账号、密码、可选「在此设备保持登录」，支持密码管理器。服务端验证成功后
  才进入原站内目标，根入口默认进入探索。凭证不正确时保留账号并清空密码，网络或服务
  不可用时提供原地恢复动作。会话有效时刷新和新开标签页直接进入目标页。
- 过期、管理员撤销或退出后，页面展示实际的登录状态。重新登录时恢复当前权限允许的
  站内深链和查询参数，先核对原提交结果，再由用户决定后续操作。账号菜单显示真实账号
  与退出操作，退出立即撤销当前会话。同一浏览器的其他标签页在下次受保护请求时反映状态。
- 保持登录的规划默认值为连续 7 天未使用到期、最长 30 天。未勾选时使用浏览器会话
  Cookie，仍受服务端到期边界约束。已登录用户可改自己的密码。部署者从主机为管理员
  发放一次性重置码。重置或改密码后撤销该账号的现有 Web 会话，并要求重新登录。

### RO-2 — 在系统设置管理分权限 API 令牌

- 管理员通过「系统设置 → API 令牌」为每个脚本或集成单独签发令牌。签发时填写名称，
  选择权限和有效期，默认「只读」及 90 天。只读使用现行 `READ`，可查询 `/api/tasks`。
  「只读与整理分析」另外授予 `SUBMIT_DRY_RUN`，可走现有整理准备和分析入口，权限说明覆盖
  现有的分析相关操作。令牌管理、发布或启用定时计划、确认文件执行保留给管理员 Web 会话。
- 服务端生成高熵随机令牌，保存用于校验的哈希和非秘密元数据，明文只在签发成功时显示
  一次。页面列出名称、权限、到期时间及有效、过期、已吊销状态。签发响应丢失时可按名称
  和签发记录核对，吊销无法取得明文的令牌后再签发。轮换先签发并验证新令牌，再单独吊销
  旧令牌。到期或吊销后的请求返回 `401`。
- 浏览器以会话 Cookie 调用现有业务 API，脚本以新签发的 Bearer 令牌调用相同业务 API。
  每次请求按有效令牌签发的权限使用现有业务权限检查。审计以管理员 ID 区分网页操作者，
  以稳定的令牌 ID 区分脚本请求。缺失或失效凭证为 `401`，凭证有效但权限不足为 `403`。
  请求显式携带 Authorization 时以该凭证的验证结果为准。

### RO-3 — 最小部署与同版本重启

- 生产入口、随仓示例、配置生成器、预检及运维指引统一使用新启动方式。最小 bootstrap
  提供数据库路径等启动信息。启动配置和新配置输入拒绝已退役的 `api.principals`，并提示
  删除位置。环境变量 `MEDIAFLOW_API_TOKEN` 不能创建账号或为请求授权。
- 从空实例初始化业务配置后，管理员受理任务并从网页启用自动化。同版本重启后可查看原任务、
  结果与审计。Scheduler 和 Worker 校验管理员发布的定时执行授权及当前生效计划，并沿用原任务
  的业务快照和执行保护。吊销、过期或轮换脚本令牌只影响对应的脚本请求，管理员发布的计划
  继续按配置运行。
- 管理员在自动化编辑卡停用计划并保存。列表显示计划已停用，Scheduler 停止受理，已入队或执行中
  的任务在下一次适用的授权检查停止后续文件操作。执行记录说明停止原因，保留原任务与已有结果。
  重新启用后按计划产生新的执行，原任务和已有文件效果保持可核对。

## 架构与交付边界

- SQLite 持有管理员、会话及令牌状态。API 使用凭证对应的身份及业务权限，后台定时执行使用
  管理员发布授权及当前计划。已受理任务使用原固定的业务上下文和当前适用的执行检查。
  读和重连触发的业务变更数为零。
- 凭证使用成熟的密码哈希、服务端会话和短期一次性码。跨设备部署走 HTTPS，回环
  HTTP 按本机入口单独验收。会话 Cookie 由服务端设置，限制脚本访问和跨站发送，
  HTTPS 下启用 Secure。Cookie 认证的写入做显式跨站请求防护。失败尝试限流。
  审计、日志、配置导出和 API 错误只记录脱敏信息。
- 生产 Compose 的健康检查区分服务在线、等待首位管理员和等待业务配置。交付覆盖
  配置生成、启动验证、设置与密码恢复、新签发令牌的使用及同版本重启。
  业务配置包导入导出与账号存储分离。
- 支持的部署数据限于空库和本版本创建的库。预检发现不受支持的数据库时，停止启动、
  保留原文件，并提示使用新的数据目录进行纯净部署。
- 延期能力包括 Web 多用户、角色分配和普通用户恢复、自助注册、邮件找回、OIDC、
  反向代理身份接入、Passkey、多因素认证、自定义角色及专用服务账号体系。

## Acceptance Criteria

- [ ] AC-01 / RO-1 从空库、无媒体挂载及无旧 API 令牌的真实 Compose 安装开始，
  验证建首位管理员、系统设置初始化、Web 改密、主机侧管理员重置、重启后的状态。
  验证过期、错用及并发使用设置／重置码，以及一次有效提交最多改变一次账号状态。
- [ ] AC-02 / RO-1 用生产 Web 产物在桌面和窄屏验证正常登录、表单错误与不可用状态、
  同站深链回跳、刷新、新标签、超时和退出。验证退出或改密后的多标签会话同步、跨站写入
  防护和原请求核对。写请求受理次数和效果计数符合原契约。
- [ ] AC-03 / RO-2 管理员在系统设置分别为监控和整理分析脚本签发令牌。验证默认只读及
  90 天、一次性展示、签发丢回包后的核对和轮换。用两枚令牌调用正式业务 API，核对各自权限、
  独立吊销、到期、`401/403`、重启后状态和按令牌标识区分的审计。确认列表、日志、配置包
  和浏览器持久存储的凭证保护。轮换或吊销监控令牌时，原定时计划照常执行。
- [ ] AC-04 / RO-3 用随仓配置生成器和空库部署，验证退役字段拒绝，设置旧令牌环境变量也
  不能取得业务权限。用管理员发布业务配置、受理任务、启用自动化，验证同版本重启前后的任务、
  结果与审计。分别在到期前和任务入队后停用，验证 Scheduler 零新增、Worker 零新增文件效果、
  用户可见原因及旧记录回读。使用不受支持的测试库验证预检停止且原文件保持完整。
  完成 T4、构建、wheel 及真实 Compose 验收。

## Final validation and closure

高风险范围采用 T4。B 独立复核纯净部署与同版本重启、认证并发、浏览器与 API 权限、
Worker/Scheduler 执行边界，保留各项实际结果及限制。A 在独立终审核对
完整 Base..Implementation Head 与 Closure Packet 后决定关闭。
[测试级别及验收分工](docs/development-workflow.md#6-test-levels)

B 已验收 Task 57.1 和 Task 57.2。原 Closure Packet 保存在
`2961baeb5eae2028a3e6db23fc6076e3c62caf2a:TASK.md`。

## A Final Review — FIX REQUIRED

```text
Review Date: 2026-11-22
Reviewed Base: ad7f29a1cc6d73ce17106b513f4b763cfd0c22ab
Reviewed Implementation Head: 2b1042470765f5d9bf546780921de3fa499a0461
B Closure Packet: 2961baeb5eae2028a3e6db23fc6076e3c62caf2a:TASK.md
Decision: FIX REQUIRED
Blocker: A57-01 / P1 — committed account changes presented as unapplied after response loss
```

A 核对完整 Base..Implementation Head 的 157 文件清单及生产改动，涵盖部署配置切换与预检、
SQLite 账号、会话及令牌事务、HTTP 认证与业务权限、Web 入口及恢复、后台计划授权和停用、
打包测试与操作文档。Implementation Head 到 B 交接提交的差异仅含 `SLICE.md` 与 `TASK.md`。

**A57-01（P1）阻塞 RO-1 / AC-01、AC-02。** 在隔离空库用生成器、正式 Waitress 入口和生产
Web 产物启动。通过主机命令领取设置码，从首页创建管理员，再从账号菜单进入改密。两次都让真实
提交完成，在回复到达浏览器前断开。设置返回 `201`，主机状态确认唯一管理员已创建，刷新后可登录。
改密返回 `200`，旧会话随即返回 `401`，新密码可登录。两条旅程各实际提交一次，页面却都断言
账号或会话未变更，并要求再次提交表单。该错误提示会让部署者重用已消耗的设置码，也会让管理员
用已失效的会话重提改密。共享认证客户端将 fetch 失败当作未写入，由 `8c0e2c850de370e4c2f832deb3c1454b95f61ee1`
（2026-11-21）引入。[认证请求处理](web/src/shared/api/auth-api.ts)

通过条件是认证表单区分已确认拒绝与结果未知，并通过正式入口读取可证实的当前设置及会话状态，
给出能够继续的操作。结果仍不可判定时维持未知，由用户决策。用真实后端验证建号和改密的丢回包、
可见恢复与单次提交，同时核对共享处理涉及的其他认证表单。B 在[原 Task 57.1](TASK.md)下规划修正，
独立验收并重交 Closure Packet。

A 实际运行生产构建、17 项真实 Python Chromium 用例和 39 项 Python 认证／容器部署测试，均通过。
额外浏览器复现确认 A57-01。复现日志、脚本、截图、范围清单及测试日志位于本机
`.git/validation-evidence/2b1042470765f5d9bf546780921de3fa499a0461/a-review/`。
A 核对 B 的全量测试、同版本 Compose、轮换、停用和旧库拒绝日志及 wheel 摘要。B 的 7 项可选
Storage／耐久测试跳过继续披露。当前 Docker 缓存中已找不到原候选 image ID，Compose 结论取自
B 原始日志。
