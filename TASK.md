# Task 57.1 — 单管理员 Web 登录与定时计划停用

```text
Task ID: 57.1
Task Type: SLICE
Parent Slice: 57
Status: READY FOR B REVIEW
Task Base: 4566a74055c698aec704215dd431eb8521bcfedb
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK57.1 CORRECTION SCOPE
Next Action: B REVIEWS TASK57.1 CORRECTION
```

## A 终审退回

**A57-01（P1，RO-1 / AC-01、AC-02）**。从现有首页创建管理员或从账号菜单改密时，
真实提交已经生效，但浏览器丢失回包后提示账号或会话未变更，并要求重提。
复现、原始证据和验收条件见 [A 终审](SLICE.md#a-final-review--fix-required)。

Task 57.1 原计划、范围和测试安排见
`c12cae6fe0226e7efe6850ac68e6581785fb87e3:TASK.md`。原 Task 57.1 PASS 见
`5c04cf53:TASK.md`，Task 57.2 PASS 和原最终验收包见
`2961baeb5eae2028a3e6db23fc6076e3c62caf2a:TASK.md`。

## 修正目标与范围

部署者从首页提交设置码，或管理员从「账号菜单 → 改密码」提交新密码。回复中断后，页面说明
提交结果待核对，并读取当前设置和会话状态。部署者能继续初始化业务配置，管理员能用新密码重新
登录。覆盖同一认证客户端服务的首页登录、主机码重置及账号菜单退出。修正范围是 Web 认证提交
与现有状态读取的衔接，沿用当前账号事务、会话、权限和路由。

## 开发指导

1. 在 [认证请求客户端](web/src/shared/api/auth-api.ts) 区分现有服务端明确拒绝、状态读取失败和
   提交结果未知。错密码、失效码等明确拒绝继续显示服务端原因及对应操作。提交遇到连接中断、
   代理超时或成功回复无法读取时，交给表单的结果核对分支。用现有
   `fetchAuthStatus` 读取 `GET /api/auth/status`，落实页面的下一步。状态暂不可用时保留待核对
   提示和「检查当前状态」操作。发起一次用户提交，后续自动或手动核对均只发送读取请求。
2. 在 [首页](web/src/features/entry/EntryPage.tsx) 根据状态读取退出已完成设置的表单。设置已完成
   且当前浏览器有有效会话时进入系统设置；设置已完成但未登录时显示登录，并在业务配置仍待
   初始化时登录后进入系统设置。设置仍待完成时显示当前状态和主机领取设置码的入口，由部署者
   决定是否重新填写提交。日常登录丢回包时，有效会话按原站内目标续转；当前未登录时保留登录名
   和原目标，让用户显式登录。重置丢回包且已退出时，从现有登录表单让用户用刚设置的密码登录；
   如仍无法登录，保留主机重新领取重置码的路径。
3. 在 [改密页面](web/src/features/entry/ChangePasswordPage.tsx) 和
   [账号菜单](web/src/shared/auth/AuthControls.tsx) 用该状态读取核对当前会话。旧会话已失效
   时沿用现有的本地会话、缓存清理和多标签同步，退出到登录。在改密恢复中提示用户用刚输入的
   新密码登录，文案只确认会话已失效。会话仍有效时，改密页继续提供状态核对，账号菜单保留
   用户主动退出当前会话的操作。密码、设置码和重置码随现有表单清理，反馈在切到登录后仍可见。
4. 在现有 [账号浏览器用例](web/tests/e2e/web-account-auth.python.spec.ts) 复用真实 Python/SQLite
   和生产 Web 产物。用现有页面按钮发起提交，等正式 API 处理后再让浏览器丢失响应。用
   `accounts status`、会话读取及实际重新登录核对结果，记录对应 POST 次数。

## 验收标准

- [ ] 空库领取设置码，从首页创建管理员，真实 API 完成后丢回包。页面读出当前已完成设置，
  提供当前会话对应的继续操作。回复头一起丢失时，部署者在同一标签页从登录进入系统设置并初始化；
  有效 Cookie 已到达时可直接进入系统设置。原建号 POST 一次，库中只有一个管理员。
- [ ] 已登录时从账号菜单改密，真实 API 完成后丢回包。页面核对并显示当前会话已失效，能用
  新密码登录，另一标签页在下一次受保护请求反映退出。改密 POST 一次，旧密码和旧会话均失效。
  当前会话状态及登录结果分别以各自的服务端证据呈现。
- [ ] 从现有登录、重置和退出入口核对同类未知结果。登录可恢复原站内深链和查询参数；主机码
  重置后可用新密码登录；退出核对到会话已失效后回到登录。状态读取暂不可用时，页面保留
  未知提示并可重新检查。核对前后各原操作的 POST 数均为一次。
- [ ] 错密码、错码、过期码及已有首次设置并发回归通过。明确拒绝后仍可按指引修正；代理
  `504` 用例仍将已提交操作显示为待核对。窄屏可直接完成上述恢复。

## 测试安排

**Developer — 新增、修改和直接受影响的测试**

- 在 `web/` 运行 `npm run test -- run src/features/entry src/shared/auth src/shared/api/auth-store.test.ts src/shared/ui/AppShell.test.tsx`，
  覆盖拒绝、待核对和现有会话／账号菜单回归。运行 `npm run typecheck` 与 `npm run build`。
- 在 `web/` 运行
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/web-account-auth.python.spec.ts`，
  验证正式入口中的丢回包及恢复、现有成功路径和多标签会话。检查改动文件和 `git diff --check`。

**B — 独立验收**

- 用生产 Web 产物和正式 Waitress 入口独立复验建号和改密，沿上述浏览器用例核对登录、重置、
  退出和状态暂不可读后的恢复。检查完整 Task Base 到交接提交和 Slice Base 到实施提交的差异。
- 对修正候选执行[适用 T4 全量门禁](docs/development-workflow.md#shared-full-regression-commands)。
  按[发布指南](docs/release.md#quality-gate)用候选 wheel 和真实 Compose 复核纯净启动、同版本重启
  和发布安全。重新核对 RO-1、RO-2 和 RO-3，记录各项实测结果及可复用证据的对应版本。
- 每轮记录总耗时与测试耗时，测试耗时小于该轮总耗时的 50%。Developer 交受影响测试，B 负责
  完整回归、制品验证和更新后的 Closure Packet。

## B 当前判定

```text
Task Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..ba2f01e97d8f4f73ded20ebfcbeae3622a58a1b9
Slice Implementation Reviewed: ad7f29a1cc6d73ce17106b513f4b763cfd0c22ab..2b1042470765f5d9bf546780921de3fa499a0461
Decision: FIX REQUIRED
Task Blocker: A57-01 / P1
Next: SAME TASK FIX LOOP
```

规划起点为干净的 `main`，HEAD `ba2f01e9`，治理检查通过。实施提交之后只有治理文档变化。
B 构建生产 Web 产物，用生成器、正式 Waitress 入口和隔离空库独立复现。建号实际返回 `201`，
主机状态确认唯一管理员已创建。改密实际返回 `200`，旧会话返回 `401`，新密码可登录。
页面两次都要求重提，实际各提交一次。日志和窄屏截图位于本机
`.git/validation-evidence/ba2f01e97d8f4f73ded20ebfcbeae3622a58a1b9/b-review/`。

RO-1 仍由 A57-01 阻塞。RO-2 令牌签发、轮换、权限和审计，以及 RO-3 空库部署、重启、旧库
拒绝和计划停用，已按原验收包与原始日志核对。当前轮止于已复现的阻塞；修正候选提交后，
B 复核全部结果，执行适用门禁，通过后将更新的 Closure Packet 交 A。

## Developer 返工交接 — TASK 57.1 A57-01

```text
Candidate: 701605547aeee876ce7bc7954582779ca6b9bf14
Fix range: 50f85df74e77ac122d43abb2224c5cd3b4b2bfee..70160554
Task range: 4566a74055c698aec704215dd431eb8521bcfedb..70160554
```

- **提交结果分类。** `auth-api.ts` 区分用户提交与服务端状态读取：提交遇到连接中断、`5xx`
  或成功响应体不可读，返回 `AuthUnknownOutcomeError`；明确的 `4xx` 拒绝继续保持原有服务端
  code、durable state 和 next action。状态读取失败仍是独立的可用性错误。
- **首页恢复。** 建号、登录、重置丢回包后自动用 `GET /api/auth/status` 读取真实状态，并在页面
  保留「Check current status」手动重试入口。建号完成且无 Cookie 时退出设置表单、保留登录名，
  登录后进入系统设置；Cookie 已到达时直接进入系统设置。设置仍待完成时保留主机领取新设置码的
  路径。登录未建立会话时保留登录名和原站内目标；重置后显示新密码登录和重新领取重置码两条路径。
- **改密与退出恢复。** 改密丢回包后读取会话：会话已失效则清理本地身份/缓存、通知其他标签页，
  带一次性非秘密提示回到登录，提示只用新密码登录；会话仍有效则保留改密页和状态核对；读取失败
  时保留未知提示和重试。账号菜单退出采用同一核对方式，会话仍有效时明确显示仍已登录并提供核对。
- **真实浏览器证据。** `web-account-auth.python.spec.ts` 使用真实 Python/SQLite 和生产 Web
  产物，用页面原按钮提交，等正式 API 完成后中断回包；核实建号、改密、重置、退出、代理 `504`
  和状态读取中断。建号/改密/重置/退出均核对原 POST 一次；改密核对旧 Cookie `401`、旧密码失败、
  新密码成功，另一标签页在下一次受保护请求回到登录。新增第二个隔离实例核对「Cookie 已到达时
  直接进入系统设置」，并保留正常建号成功、深链回填、刷新、新标签和同版本重启旅程。
- **实际执行（候选工作树）。**
  - `web/`：`npm run test -- run src/features/entry src/shared/auth src/shared/api/auth-store.test.ts src/shared/ui/AppShell.test.tsx` → **86 passed**。
  - `npm run test -- run src/shared/api/auth-api.test.ts` → **5 passed**。
  - 新增/受影响用例重复执行 3 次 → **22 passed**（每次）。
  - `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/web-account-auth.python.spec.ts` → **11 passed**。
  - `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过。
  - `python3 scripts/check_governance.py` 与 `git diff --check` 通过。
- 用时约 20 分钟；Web 单测、E2E、构建和静态检查的实际执行合计约 2 分钟，低于本轮 30%。
- **剩余风险与 B 验收。** 本轮未改 Python、会话/账号事务、权限或持久 schema。B 仍需用正式
  Waitress/生成器入口独立复验 A57-01 两条原始旅程，执行完整 T4、wheel/源码外安装和真实
  Compose 同版本重启，并复核 RO-1、RO-2、RO-3 与更新后的 Closure Packet。真实 Python 浏览器
  证据使用现有账号 harness，不是正式 Waitress 进程。
