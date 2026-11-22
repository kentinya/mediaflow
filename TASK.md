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

## B 复核 — FIX REQUIRED

```text
Task Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..f54cf44e9bd1b4f92db0143fc8050fe4b5a9855f
Slice Implementation Reviewed: ad7f29a1cc6d73ce17106b513f4b763cfd0c22ab..03f054ea02f818b5cde73e77fccf06c3ad14ad1c
Decision: FIX REQUIRED
Task Blocker: A57-01 / P1 — first-setup recovery ends before the original submission is resolved
Next: SAME TASK FIX LOOP
```

**A57-01 / P1 仍阻塞 RO-1 的 AC-01、AC-02。** 部署者从主机领取设置码，在首页点一次
「Create administrator」。代理先返回 `504`，首次状态读取显示实例仍待设置。页面断言原提交
没有建号，要求领取新码，并关闭「Check current status」。原请求随后返回 `201`，主机状态确认
已创建唯一管理员。回到主机按页面指引领取新码时，命令提示管理员已存在，网页仍停在建号
表单。刷新后可用原密码登录，建号 POST 共一次。
[首页恢复分支](web/src/features/entry/EntryPage.tsx)

**本轮证据。** 起点为干净的 `main`，治理及完整差异检查通过。交接提交只更新 `TASK.md`，
候选范围和 Developer 测试记录见 `f54cf44e:TASK.md`。B 构建生产 Web 产物，真实账号浏览器
用例 **11 项通过**。用生成器、正式 Waitress 入口和隔离库复验了原两条丢回包旅程。提交已完成
时，部署者在同一标签页登录进入系统设置，管理员从可见会话失效提示进入登录并用新密码登录，
原提交各一次。另以同一正式入口复现上面的 `504` 顺序。构建、测试和复现累计约 13 秒，
低于本轮复核用时的一半。原始日志及窄屏截图位于本机
`.git/validation-evidence/03f054ea02f818b5cde73e77fccf06c3ad14ad1c/b-review/`。

**Slice 重评。** RO-1 仍有上述恢复缺口。RO-2 的令牌签发、轮换、权限与审计，以及 RO-3
的空库部署、重启、旧库拒绝和计划停用，已根据完整差异与原验收包及原始日志复核。
候选的 T4 全量、wheel 和 Compose 待本条修复后执行。

### 给 Developer 的本轮开发指导

1. 修正 `EntryPage.tsx` 的建号恢复分支。状态读取显示实例仍待设置时，呈现当前设置状态，
   保留原提交的「结果待核对」及「Check current status」。设置状态读取只报告当前是否已有
   管理员。错码、过期码等明确拒绝继续走原有表单指引。
2. 原请求完成后，从同一页面点击「Check current status」。读取已有管理员时沿用当前成功
   路径。有会话进入系统设置，无会话则显示登录，登录后进入待初始化的系统设置。核对只发
   GET，原建号 POST 仍为一次。
3. 在现有账号浏览器用例加入「`504` → 首次读取仍待设置 → 原 POST 完成 → 再次核对 →
   登录并进入系统设置」的真实后端回归，核对可见提示、一次建号和唯一管理员。运行原测试
   安排里的 Web 入口受影响单测、生产构建及真实账号浏览器用例，保留建号和改密原通过分支。

## Developer 修正交接 — A57-01 首次建号状态核对

```text
Candidate: 5d2f215fb7afaceeae677877fdb4990fc6815077
Fix range: f54cf44e9bd1b4f92db0143fc8050fe4b5a9855f..5d2f215f
Task range: 4566a74055c698aec704215dd431eb8521bcfedb..5d2f215f
```

- **首页建号恢复。** 提交结果未知后的首次 `GET /api/auth/status` 仍显示实例待设置时，页面
  只报告当前设置状态，不再断言设置码没有建号，也不要求领取新码。原提交的待核对结果和
  「Check current status」保持可见，表单仍由部署者决定是否重新填写提交。明确错码、过期码等
  `4xx` 拒绝继续显示服务端原因并停留在原表单，不发状态读取。
- **原请求完成后的核对。** 在同一页面再次核对到管理员已存在时，沿用原成功路径：有有效
  会话直接进入系统设置；无会话显示登录，保留提交时的登录名，登录后进入待初始化的系统
  设置。核对只调用现有状态读取，原建号 POST 不重放。
- **真实后端回归。** `web-account-auth.python.spec.ts` 新增隔离空库用例：真实浏览器提交
  被代理 `504` 后，首次读取仍为待设置；随后原上游请求以同一提交内容真实完成 `201`；再次
  点「Check current status」显示管理员已创建，登录后进入系统设置。断言首次读取时库中无管理员、
  完成后只有一个管理员，建号 POST 一次，核对只发 GET，窄屏 `390×844` 可完成。
- **实际执行（候选工作树）。**
  - `web/`：`npm run test -- run src/features/entry src/shared/auth src/shared/api/auth-store.test.ts src/shared/ui/AppShell.test.tsx` → **87 passed**（8 files，7.98s）。
  - `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/web-account-auth.python.spec.ts` → **12 passed**（9.2s），含原建号、改密、重置、退出、深链、重启及新 `504` 顺序。
  - `npm run typecheck`、`npm run build` 通过；改动文件 Prettier 与 ESLint 检查通过；
    `python3 scripts/check_governance.py`、`git diff --check` 通过。
  - 本轮约 6 分钟；测试执行合计约 23 秒（含构建和静态检查约 40 秒），低于本轮 30%。
- **剩余风险。** 未改 Python、账号事务、会话、权限或持久 schema；真实浏览器证据使用现有
  账号 harness，不是正式 Waitress/Compose。B 仍需按要求复核完整差异，独立复验原 `504`
  顺序和改密旅程，并执行适用 T4 全量、wheel 与真实 Compose 门禁。
