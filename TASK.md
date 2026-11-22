# Task 57.2 — 在系统设置签发、使用和吊销 API 令牌

Next Action: DEVELOPER FIXES TASK57.2

```text
Task ID: 57.2
Task Type: SLICE
Parent Slice: 57
Status: FIX REQUIRED
Task Base: c12cae6fe0226e7efe6850ac68e6581785fb87e3
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: AUTHORIZED BY USER FOR TASK57.2
```

用户已授权激活 Task 57.2。Developer 开始实施时将状态从 `PLANNED` 转为 `IN PROGRESS`。

## 目标与范围

管理员在「系统设置 → API 令牌」分别为监控脚本和整理分析脚本签发令牌。脚本在选定权限内
调用现有 API。管理员能核对签发结果、独立吊销和轮换令牌，网页会话和按计划整理继续正常工作。
本 Task 交付 RO-2 和 RO-3 中的令牌独立性。继续使用 Slice 57 的单管理员、空库部署和同版本重启
边界。多用户、普通用户恢复和自定义角色属于 Slice 合同的延期范围。
[Slice 57 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

生产入口已有 Web Cookie 会话、同源写入校验和基于身份的审计。现有 Bearer 分支使用旧的
进程内 principal 表，生产部署没有签发可用令牌的入口。系统设置已有页面，`GET /api/tasks`
及整理准备、分析和确认分别使用现有权限。分析权限在代码里由 `SUBMIT_DRY_RUN` 和其别名
`MANAGE_MANUAL_ORGANIZE` 表达，后者也覆盖整理准备和分析相关操作。定时计划的发布授权和执行
检查已有独立持久状态。
[系统设置](web/src/features/configuration/ConfigurationPage.tsx) · [API 派发](mediaflow/interfaces/service_api.py) ·
[权限定义](mediaflow/domain/security.py) · [后台执行授权](mediaflow/application/automation_execution_authority.py)

## Developer 开发指导

1. 在现有 SQLite 运行库中加入 API 令牌记录，保存稳定的令牌 ID、名称、权限、时间和吊销状态。
   签发时由服务端生成高熵随机值，持久化校验哈希和必要的审计元数据。签发及吊销记录关联
   当前管理员。列表响应只返回状态和非秘密元数据。使用运行库现有的启动、同版本重开和
   不支持版本拒绝路径。
2. 在 HTTP 入口用已签发令牌解析 Bearer 身份，把权限直接交给现有业务权限检查。只读对应
   `READ`，整理分析对应 `READ` 加 `SUBMIT_DRY_RUN`。用现有整理准备、分析和执行入口
   核对这些权限的实际边界。签发、列表、吊销由管理员 Cookie 会话访问，沿用同源写入校验。
   令牌审计采用稳定令牌 ID。显式 Authorization 的认证结果优先于 Cookie。
3. 在现有系统设置页面加入「API 令牌」，默认只读和 90 天。签发成功后只在当次页面状态展示
   明文供复制。列表显示名称、权限、到期时间和有效、过期、已吊销。签发结果不明时在同处
   刷新列表并按名称和签发记录核对，吊销取不到明文的令牌后再签。轮换沿用「签发新令牌 →
   验证脚本调用 → 吊销旧令牌」。
4. 在部署和配置指南记录现有 API 的使用示例。配置包继续只承载业务配置。Web 会话、服务端
   脚本身份和定时执行分别使用当前入口。用一个已经发布的计划复核吊销和轮换脚本令牌时的
   Scheduler 受理与 Worker 文件结果。

## 验收

- [ ] 从「系统设置 → API 令牌」签发只读令牌和整理分析令牌，确认默认权限和 90 天。刷新或
  重新打开时仍能看到状态，明文只在签发成功时显示。签发响应丢失后按记录找到对应条目，
  吊销这枚令牌并重新签发，核对列表和实际凭证状态。
- [ ] 用两枚令牌调用正式 API。两枚都能读 `/api/tasks`。整理分析令牌可提交现有准备和分析，
  结果可读且文件效果为零。只读令牌提交分析返回 `403`。两枚令牌调用令牌管理、定时计划
  发布或启用、确认执行均返回 `403`，已有任务和文件效果可核对。
- [ ] 检查缺失、过期、吊销凭证的 `401`，并验证显式无效 Authorization 优先于有效 Cookie。
  轮换时先验证新令牌，再吊销旧令牌，两枚令牌的结果可分别核对。用生产 Compose 重启四个
  服务，回读令牌状态并用有效令牌调用 API。审计可分别按管理员 ID 和令牌 ID 核对行为。
- [ ] 发布并启用一个定时计划。轮换或吊销监控令牌后，观察下一次正常受理和 Worker 结果。
  核对 SQLite、日志、列表、配置包及浏览器持久存储的凭证保护。

## 测试

**Developer — 新增／修改与直接受影响测试**

- 在仓库根目录执行 `.venv/bin/python -m unittest tests.test_api_credentials tests.test_web_account_auth`。
  将凭证回归放在现有测试模块，覆盖签发和持久状态、两组权限、`401/403`、Authorization 优先级、
  同源写入和审计。运行 `.venv/bin/python -m unittest tests.test_container_deployment`，
  核对运行库变更后的空库预检和同版本重开。
- 在 `web/` 执行
  `npm run test -- run src/features/configuration/ConfigurationPage.test.tsx`、`npm run typecheck`
  和 `npm run build`。从现有系统设置浏览器规范增补令牌旅程，以
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/configuration-settings.python.spec.ts`
  验证签发、丢回包核对和吊销。跑改动文件的静态检查及 `git diff --check`。

**B — 独立验收与完整回归**

- 从真实 Compose 的系统设置签发两种令牌，用正式 Tasks 及整理 API 核对权限、效果、轮换、
  会话和审计，重启后复查。用隔离媒体观察既有计划在脚本凭证变化后继续受理及完成。
- 运行[共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)，对候选镜像
  和源码外安装的 wheel 验收，并取齐 Slice 57 的最终证据。

## Developer 交接 — TASK 57.2

```text
Candidate: 2f3bff357fb5dad7894c7a9437fc6451e0d5acb8
```

- 候选实现提交为 `2f3bff35`，范围为 `c12cae6f..2f3bff35`。运行库 schema 从 59 升到 60，
  新增 `api_tokens` 表；只保存稳定令牌 ID、签发管理员、名称、范围、权限、创建/到期/吊销/
  最近使用时间和 SHA-256 摘要，未回填或改写既有账号、任务、结果与配置。
- 后端新增令牌签发、列表、独立吊销和每次请求的令牌解析。只读范围为 `READ`，整理分析范围
  为 `READ + SUBMIT_DRY_RUN`；令牌管理、计划发布/启用和确认执行仍只接受管理员 Cookie
  会话。显式 Authorization 无效时不会回退到 Cookie；成功请求审计使用令牌 ID，签发/吊销
  另以管理员账号 ID 写入既有账号审计。
- 系统设置新增「API 令牌」卡：默认只读/90 天，明文仅在签发响应/当前页面状态展示，列表
  回读非秘密状态；丢回包后刷新并按名称与签发时间核对，吊销前二次确认。部署与配置指南
  记录了现有 API 的 Bearer 调用示例和凭证保护边界。
- 实际执行：
  - `.venv/bin/python -m unittest tests.test_api_credentials tests.test_web_account_auth`
    → **26 passed**；`.venv/bin/python -m unittest tests.test_container_deployment` → **20 passed**。
  - `web/`：`npm run test -- run src/features/configuration/ConfigurationPage.test.tsx` →
    **15 passed**；`npm run typecheck`、改动文件 ESLint/Prettier、`npm run build` 通过。
  - `npm run test:e2e -- --config=playwright.python.config.ts
    tests/e2e/configuration-settings.python.spec.ts` → **6 passed**，覆盖真实 Python 设置页、
    两种令牌签发、丢回包列表核对、只读 `403`、吊销 `401` 和浏览器持久存储无明文。
  - `python3 scripts/check_governance.py`、改动 Python Ruff/format、编译、完整范围
    `git diff --check` 通过。
- 用时约 16 分钟；测试与检查实际执行约 2–3 分钟，低于本轮 30%。
- 剩余风险与 B 验收：完整 T4 Python/Web/E2E、真实 Compose 四服务重启、真实 Scheduler/Worker
  在令牌轮换后的受理与文件结果、候选镜像、wheel/源码外安装仍待 B 独立执行。本轮定向测试
  在无 Active 的隔离库验证了整理分析令牌通过既有分析入口的权限边界，但实际准备/分析成功、
  零文件效果与结果回读需在 B 的真实 Active/Worker 环境中完成。

## Task 57.2 — B 独立复核

```text
Reviewed: c12cae6fe0226e7efe6850ac68e6581785fb87e3..8cc082a14212aa4691a0e908f5f87740970e2732
Implementation: 2f3bff357fb5dad7894c7a9437fc6451e0d5acb8
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — 丢回包后的列表核对提示不实（RO-2 / AC-03）。** 管理员签发监控令牌时，服务端已签发，浏览器收不到回包，随后列表读取也因断网失败。页面同时显示「列表已重新读取」和「API 令牌读取失败」，管理员此时无法找到那枚已签发的令牌来吊销。`refresh()` 未把读取结果交给签发或吊销的提示。见 [ApiTokensPanel](web/src/features/configuration/ApiTokensPanel.tsx#L202)。
- **P1 — 令牌管理收到 401 后没有进入重新登录流程（RO-1 / AC-02）。** 管理员在一台设备打开令牌卡，在另一台设备改密后回到旧页面点「刷新列表」。真实 API 返回 `401`，令牌卡提示重新登录，页面仍显示管理员菜单。令牌卡只在内部处理错误，未接入现有会话失效处理。见 [令牌 API](web/src/shared/api/api-tokens-api.ts#L165) 和 [共用会话恢复](web/src/shared/auth/AuthorizedReadBoundary.tsx#L40)。

### Developer 返工指导

1. 在令牌卡复用一次列表重读，把这次读取的结果交给签发、吊销的核对提示。成功后引导按名称和签发时间找到对应记录。读取失败时显示核对仍待完成，引导连接恢复后重新读取。以签发为例，管理员看到对应记录后先吊销取不到明文的令牌，再签发一枚给脚本使用。整个核对过程只重读列表。
2. 将令牌列表的 `401` 接入现有受保护读取的会话失效流程。签发和吊销收到 `401` 时也使用同一会话恢复入口。重新登录后回到系统设置并读取令牌列表，原写请求由管理员根据列表结果决定是否再次发起。
3. 在 `web/tests/e2e/configuration-settings.python.spec.ts` 补齐两个真实页面旅程。服务端成功签发但回包及随后列表读取丢失时，验证失败提示、恢复读取、找到并吊销原令牌后重新签发，按请求数核对每次签发来自管理员点击。用独立浏览器会话通过账号菜单改密，在旧页面点「刷新列表」触发真实 `401`，验证旧管理员菜单消失，并用新密码回到系统设置读到原列表。

**Developer 受影响检查**。从 `web/` 执行 `npm run test -- run src/features/configuration/ConfigurationPage.test.tsx`、`npm run typecheck` 和 `npm run build`，再运行 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/configuration-settings.python.spec.ts`。检查改动文件及 `git diff --check`。

**B 本轮实测**。Python 凭证、Web 账号和容器部署定向测试 46 项通过。Web 生产构建通过，原有系统设置真实 Chromium 测试 6 项通过。独立追加检查复现了以上两项阻塞。首次用同一浏览器两标签退出，原页面已由现有跨标签同步移走，未触发令牌列表请求。后续以独立会话中的真实改密完成复现。测试命令累计约 18 秒。原始日志位于 `.git/validation-evidence/8cc082a14212aa4691a0e908f5f87740970e2732/b-review/`。

**Slice 结果核对**。首次设置和密码恢复保留 Task 57.1 的验收记录。RO-1 的令牌卡会话恢复与 RO-2 的丢回包恢复等本 Task 修正。RO-3 中令牌轮换后计划仍正常执行、当前候选的四服务同版本重启还需实测。B 在修正候选上复核这两项阻塞，再执行 T4、真实整理分析及零文件效果、Compose 和 wheel 验收。

## Developer 返工交接 — TASK 57.2

```text
Candidate: 1c1e366fdeb5ebf59bcd559b42bc82c3a680f3c9
Fix range: 8cc082a14212aa4691a0e908f5f87740970e2732..1c1e366f
```

- 丢回包核对改为一次持久列表重读并把结果交给提示。签发或吊销结果未知时，列表重读成功才提示「列表已重新读取」并引导按名称和签发时间找到记录；重读失败时明确「核对仍未完成」，引导恢复连接后点击「重新读取」。手动重读成功后同一提示更新为已读取状态。核对过程只发列表 `GET`，不会重放签发或吊销 `POST`。
- 令牌列表 `401` 复用既有受保护读取的会话失效流程；签发和吊销的 `401` 通过新增的共用 `useRejectedAuthorityEntry` 执行同一两阶段恢复：先清除被拒身份并停用读取，再清空已认证查询缓存，不自动重放原写请求。重新登录后回到系统设置重新读取列表，由管理员决定是否再次签发或吊销。
- `ApiTokensApiError` 继承共用 `ApiReadError`，使受保护读取边界识别令牌列表拒绝；列表加载失败时仍保留原有错误提示和显式重读。
- `web/tests/e2e/configuration-settings.python.spec.ts` 新增两个真实页面旅程：服务端成功签发后回包和随后列表读取均丢失，验证失败提示、恢复读取、按名称找到并吊销原令牌后由管理员点击重新签发，按请求数核对无自动重放；独立浏览器会话通过账号菜单真实改密，在旧页面点「刷新列表」触发真实 `401`，验证旧管理员菜单消失，再用新密码回到系统设置读到原列表。
- 实际执行：
  - `web/`：`npm run test -- run src/features/configuration/ConfigurationPage.test.tsx` → **19 passed**；`npm run test -- run src/shared/auth/AuthorizedReadBoundary.test.tsx` → **8 passed**。
  - `npm run typecheck`、改动文件 ESLint/Prettier、`npm run build` 通过。
  - `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/configuration-settings.python.spec.ts` → **8 passed**，覆盖新增丢回包与改密 `401` 旅程。
  - `python3 scripts/check_governance.py`、`git diff --check` 通过。
- 用时约 14 分钟；测试与定向检查实际约 2 分钟，低于本轮 30%。
- 剩余风险与 B 验收：完整 T4、真实 Compose 四服务重启、真实 Scheduler/Worker 在令牌轮换后的受理与文件结果、候选镜像和 wheel/源码外安装仍待 B 独立执行。本轮 E2E 在隔离 Python/SQLite 环境验证了页面旅程，未替代 B 的真实部署与整理分析权限验收。

## Task 57.2 — B 返工复核

```text
Reviewed: c12cae6fe0226e7efe6850ac68e6581785fb87e3..981870752f8490e2520b5a383e5c7ebaa7e00506
Implementation: 1c1e366fdeb5ebf59bcd559b42bc82c3a680f3c9
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- 上轮两个场景通过。签发回包和随后列表读取中断时，页面显示核对未完成，连接恢复后可读回、吊销并单独签发替代令牌。在另一台设备改密后，旧页面刷新收到 `401`，可用新密码回到原令牌列表。
- **P1 — 代理超时掩盖已签发的令牌（RO-2 / AC-03）。** 管理员经 HTTPS 反向代理签发监控令牌。复核用真实后端完成签发并返回 `201`，在浏览器侧模拟代理回 `504`。页面显示「后端拒绝了本次请求」，也没读取列表。管理员手动刷新才看到新增令牌仍有效，并从同一张卡吊销。令牌客户端将这个写入结果归类为普通失败，跳过了已有的结果核对流程。这个分类从 `2f3bff35` 引入，在本次修正中仍存在。[令牌 API](web/src/shared/api/api-tokens-api.ts#L168) · [部署入口](docs/deployment.md#build-and-start)
- 默认浏览器门禁有两条设置页回归失败。原检查要确认配置区没有旧的「刷新」操作，其整页模糊匹配命中了新令牌卡的「刷新列表」。默认 Node 测试服务也未提供 `/api/auth/tokens` 列表读回，同屏出现令牌读取失败。真实系统设置的 8 项浏览器用例通过。[设置页回归](web/tests/e2e/configuration-settings.spec.ts#L53)

### Developer 返工指导

1. 把令牌签发与吊销在收到代理超时、服务端状态未确认时的响应接入同一个「结果待核实」流程。沿用现有的只读列表核对及提示。明确拒绝的响应沿用原处理。参考系统设置配置写入的已有处理方式。[令牌 API](web/src/shared/api/api-tokens-api.ts#L168) · [配置写入](web/src/shared/api/configuration-api.ts#L152)
2. 在真实系统设置用例中，从原签发按钮发起写请求，保留后端成功创建的结果，在浏览器一侧让代理回包为 `504`。验证页面显示待核实，只发一次签发请求，能读回有效记录并从列表吊销。
3. 让默认测试服务返回该场景的令牌空列表。把原有「刷新／重新读取」断言限定在配置区域或使用精确名称，继续核对旧配置刷新入口是否出现。

Developer 从 `web/` 运行 `npm run test:e2e -- tests/e2e/configuration-settings.spec.ts` 和 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/configuration-settings.python.spec.ts`，先执行 `npm run build`，并检查类型和改动文件。

B 通过了治理、全范围 `git diff --check`、Web 类型检查、Lint、格式检查、Web 构建和候选镜像构建。系统设置真实 Chromium 8 项通过，代理回包用例复现失败。默认 Chromium 中止时为 117 通过、2 失败、1 中断、159 未运行。Python 和 Web 单元全量在确认阻塞后停止。真实整理分析、Compose 四服务重启和轮换后定时执行、wheel 与其余 T4 门禁待下一候选。日志位于 `.git/validation-evidence/981870752f8490e2520b5a383e5c7ebaa7e00506/b-review/`。

## Developer 返工交接（第二轮）— TASK 57.2

```text
Candidate: afb945180fa351f2c7ed8ba09bae9ea77bf2c169
Fix range: 981870752f8490e2520b5a383e5c7ebaa7e00506..afb94518
```

- `api-tokens-api.ts` 把签发、吊销的 `>=500` 写入结果接入既有「结果待核实」流程：没有明确持久状态声明的代理超时（如 `504`）或服务端错误不再报成「拒绝」，而是标记结果未知，只重读持久令牌列表，不重放写请求。`401/403`、显式 `4xx` 拒绝和 2xx 但无法解析的结果沿用原有分类。签发与吊销共用同一写入通道。
- 默认 Node 测试服务补齐已登录账号的 `GET /api/auth/tokens` 空列表投影；设置页回归的「刷新／重新读取」断言改为精确名称，继续核对旧配置刷新入口，并断言令牌卡处于「尚未签发 API 令牌」而非读取失败。
- 真实 Python 设置页新增代理超时旅程：从原「签发令牌」按钮发起写请求，真实后端返回 `201` 并持久化令牌，浏览器侧拿到 `504`；页面显示「签发结果待核实」并只重读列表，按请求数核对只有一次签发、无明文展示，读回有效记录后从列表吊销，原凭证调用返回 `401`。
- 单元测试新增两个 `504` 场景：已提交的签发、已提交的吊销都显示待核实并从列表重读，写请求各只发一次。
- 实际执行（最终工作树）：
  - `web/`：`npm run test -- run src/features/configuration/ConfigurationPage.test.tsx` → **21 passed**。
  - `npm run typecheck`、改动文件 ESLint/Prettier、`npm run build` 通过。
  - `npm run test:e2e -- tests/e2e/configuration-settings.spec.ts` → **4 passed**；`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/configuration-settings.python.spec.ts` → **9 passed**（含新增 `504` 用例）。
  - `python3 scripts/check_governance.py`、全范围 `git diff --check` 通过。
- 用时约 12 分钟；测试与定向检查执行约 1.5 分钟，低于本轮 30%。
- 剩余风险与 B 验收：完整 T4、真实 Compose 四服务重启、真实 Scheduler/Worker 在令牌轮换后的受理与文件结果、候选镜像和 wheel/源码外安装仍待 B 独立执行。默认 Node 测试服务只提供空令牌列表读取，不承载签发/吊销；本轮未改动 Python 后端。

## Task 57.2 — B 复核代理超时修正与全量门禁

```text
Reviewed: c12cae6fe0226e7efe6850ac68e6581785fb87e3..58d89a26b9506a6d7d790b514011db8480aff0be
Implementation: afb945180fa351f2c7ed8ba09bae9ea77bf2c169
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — 监控脚本成功读取任务，审计缺少对应令牌（RO-2 / AC-03）。** 管理员在系统设置为监控脚本签发只读令牌。脚本调用文档中的 `GET /api/tasks` 得到 `200`，列表能看到最近使用时间。随后以管理员身份读取 `/api/security-audit`，该令牌 ID 的对应记录是零条。候选 Compose 和最小 API 路径均已复现。`2f3bff35` 接入令牌身份时沿用了 `/api/tasks` 对普通读取的审计过滤。[审计过滤](mediaflow/interfaces/service_api.py#L9959)
- **T4 Python 回归阻塞。** `2f3bff35` 使 HTTP 应用构造过程探查 `authenticate_api_token`，静态入口和只读系统状态的隔离验证在发出请求前就失败，共 16 项。运行库升到 60，但两个 Worker 服务默认仍为 59，整理契约测试注册的 Worker 拿不到任务，另一个就绪测试报告的预期版本为 59。真实 Compose 启动显式传入 60，独立的分析和定时复制已通过。[入口组装](mediaflow/interfaces/service_api.py#L430) · [Worker 版本](mediaflow/application/automation.py#L67)

### Developer 返工指导

1. 让已签发令牌成功调用 `/api/tasks` 时使用现有审计记录，保留稳定令牌 ID、方法、路由和结果。从新建只读令牌出发，先只调用这条正式入口，再用管理员身份读取审计，断言记录来自这次成功调用。令牌列表的最近使用时间继续用于运营查看。
2. 在已有账号运行库的入口组装令牌服务。只有固定 principal 的静态入口和系统状态测试继续按原路径构造并验证。把 Worker 注册与就绪服务两处现行默认版本同本轮运行库 60 对齐，保留真实版本不匹配时的拒绝。
3. Developer 定向运行 `.venv/bin/python -m unittest tests.test_web_account_auth tests.test_v2_ui tests.test_configuration_status tests.test_manual_operations_contract tests.test_processing_worker_readiness`，并检查改动文件。B 负责完整门禁和候选镜像复验。

### Slice 结果与本轮证据

- **RO-1** 首次部署和后台主机密码恢复有 Task 57.1 证据。候选默认 Chromium 中的账号旅程和系统设置改密重登通过。
- **RO-2** 代理模拟 `504` 后的签发核对通过，真实浏览器只发一次签发写请求，可从列表读回并吊销。真实 Compose 通过两种令牌的权限、轮换和重启回读。分析令牌在 Worker 中生成可读方案，源与目标文件效果为零。核对了浏览器存储、SQLite 数据及 WAL、令牌列表、配置导出和服务日志，均无明文。监控脚本的任务列表审计仍阻塞。
- **RO-3** 候选空实例、隔离媒体、发布安全、重启和故障门禁通过。监控令牌轮换并重启四服务后，原启用计划产生一个可回读的已完成任务，源文件保留并得到一份字节一致的复制。当前候选真实自动化浏览器 32 项通过。
- Web 单测 1,611 项、默认 Chromium 279 项、真实设置 Chromium 9 项通过。Web 构建、静态检查、两份配置样例及源码外 wheel 冒烟通过。Python 2,357 项中 18 失败、2 错误、7 跳过。其中一项为 Task 标题与发布门禁约定不符，B 已将两处标题对齐并单独复跑。候选镜像 `sha256:c63533fc44fbe497c8f33b496bb695ebe3ab8b1d272c1d8fdf489c08b858150e`。日志、截图和制品位于 `.git/validation-evidence/58d89a26b9506a6d7d790b514011db8480aff0be/b-review/`。

## Developer 返工交接（第三轮）— TASK 57.2

```text
Candidate: e85fba92241dabf71aa16ac77cec136e0e5c04dc
Fix range: 58d89a26b9506a6d7d790b514011db8480aff0be..e85fba92
```

- 已签发令牌的读取不再沿用浏览器只读投影的审计豁免：`_suppress_file_detail_audit` 只为账号会话和固定 principal 的投影免审计，`AuthenticatedApiToken` 的每次请求都写入既有安全审计，保留稳定令牌 ID、方法、路由、动作与结果状态。浏览器会话与固定 principal 的只读投影行为不变，既有 `/api/tasks` 不产生审计行的断言继续成立。新增用例从新建只读令牌出发，只调用一次正式入口 `GET /api/tasks`，再以管理员身份读取 `/api/security-audit`，断言该令牌 ID 的 `started`/`allowed` 记录来自这次成功调用、`/api/tasks` 审计只属于该令牌、响应不含明文；令牌列表的最近使用时间继续用于运营查看。
- 入口组装改为在已有账号运行库上装配令牌服务：只有传入 `account_service` 才创建 `ApiTokenService`，固定 principal 的静态入口、只读系统状态与配置对象隔离测试恢复原构造路径，不再探测 `authenticate_api_token`。已签发令牌的认证、签发、列表和吊销路径本身未改。
- Worker 注册服务与常驻 Worker 两处默认运行库版本由 59 对齐到 60，与当前 `SCHEMA_VERSION` 一致；真实版本不匹配仍由既有 `SCHEMA_MISMATCH` 路径拒绝。新增用例分别用两处默认值注册，断言记录的版本等于当前运行库版本。
- `docs/deployment.md` 令牌段落补充：成功的令牌调用以稳定令牌 ID、方法和路由出现在 `GET /api/security-audit`，供管理员核对脚本实际行为。
- 实际执行（最终工作树）：
  - `.venv/bin/python -m unittest tests.test_web_account_auth tests.test_v2_ui tests.test_configuration_status tests.test_manual_operations_contract tests.test_processing_worker_readiness` → **70 passed**。
  - 直接受影响扩展：`test_web_account_auth test_api_credentials test_v2_ui test_configuration_status test_configuration_objects test_manual_operations_contract test_processing_worker_readiness test_api_security test_container_deployment test_container_probe` → **195 passed**；另 `test_container_deployment test_task_scheduling test_v2_manual_organize test_manual_organize_execution test_execution_authorization` → **143 passed**，`test_management_setup test_automation_entrance_recovery test_automation_task_definition test_organize_source_history test_v2_automation_run_once` → **103 passed**。
  - 改动文件 Ruff format/check、`python -m compileall`、`scripts/check_governance.py`、`git diff --check` 通过。
- 用时约 25 分钟；定向测试与检查实际执行约 1.5 分钟，低于本轮 30%。
- 剩余风险与 B 验收：完整 T4、真实 Compose 四服务重启、候选镜像、wheel/源码外安装及真实 Scheduler/Worker 在令牌轮换后的受理与文件结果仍待 B 独立执行。本轮审计证据来自进程内真实 WSGI 分发与 SQLite 运行库，未在候选镜像上复验。

## Task 57.2 — B 复核令牌审计与窄屏操作

```text
Reviewed: c12cae6fe0226e7efe6850ac68e6581785fb87e3..eef4d601baabfff70f534d7a016dc4a86bbad867
Implementation: e85fba92241dabf71aa16ac77cec136e0e5c04dc
Decision: FIX REQUIRED
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — 窄屏签发后无法从令牌列表吊销（RO-2 / AC-03）。** 管理员在 390px 触屏打开「系统设置 → API 令牌」，签发第一枚监控令牌并保存明文。列表出现后，表格把设置卡撑宽到 890px。「刷新列表」和该行「吊销」都落在屏幕右侧。B 在原列表横滑，表格没有滚动，操作仍在视口之外。管理员需要从同一张卡核对并吊销旧令牌才能完成轮换。问题随 `2f3bff35` 的令牌表格引入。截图 `settings-narrow-token-row.png` 和正式页面触屏记录 `settings-touch.log` 见下方证据目录。[设置页网格](web/src/shared/ui/styles.css#L10851) · [令牌表格](web/src/shared/ui/styles.css#L11081)

### Developer 返工指导

1. 让令牌卡宽度随设置页可用空间收缩。处理 `.mf-settings-page` 网格中令牌卡的最小宽度，让现有表格滚动容器承接宽表格，表单和「刷新列表」留在视口内。管理员在列表横滑可以看到同一条令牌的状态和吊销操作。
2. 在 `web/tests/e2e/configuration-settings.python.spec.ts` 首个令牌用例之前增补 390px 真实触屏旅程。从空令牌列表签发监控令牌，保存当次明文，验证脚本能读 `/api/tasks`，再刷新列表。核对卡片和刷新按钮仍在视口内，横滑列表后能点到该行的「吊销」并确认。核对只发出一次吊销请求，同一行显示「已吊销」，原令牌调用返回 `401`。保留桌面和签发丢回包的既有测试。
3. Developer 在 `web/` 运行 `npm run build`、`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/configuration-settings.python.spec.ts` 及改动文件静态检查。B 对修正候选运行共享门禁并复验窄屏轮换、真实部署及全部 Slice 结果。

### Slice 结果与本轮证据

- **RO-1** 候选默认 Chromium 复验首位管理员、深链、会话恢复、Web 改密与主机重置。无媒体的空库部署和旧入口退役沿用 Task 57.1 证据，并通过本轮候选镜像的发布检查。
- **RO-2** 上轮审计阻塞已修复。真实 Compose 的只读、整理分析及替换令牌都能读取 `/api/tasks`，管理员可按各自令牌 ID 读回对应 `200` 审计。分析令牌经正式入口生成方案，文件效果为零。已验证各权限边界、明文保护、轮换和四服务重启后的状态。真实设置 Chromium 9 项通过，覆盖 `504`、断线恢复和改密 `401`。窄屏列表操作仍阻塞。
- **RO-3** 候选空库、隔离媒体、发布安全和重启故障检查均通过。旧 schema 59 库预检拒绝启动，文件摘要前后相同。轮换监控令牌并重启四服务后，原计划产生可回读的已完成任务，Worker 保留源文件并生成一份字节一致的复制。停用与重新启用保留 Task 57.1 的实测，本轮真实自动化对应场景也通过。
- 真实自动化首跑 31 通过、1 失败。首次复制完成后，测试在列表与配置授权异步刷新期间点击第二次。页面提示尚未发送，trace 仅有第一次复制请求，第二次丢回包场景没有发生。同一用例原样单独执行通过，列表与配置授权不同步时的专门用例也通过。B 保留首跑日志，下一候选复跑原门禁。
- Python 全量 2,359 项中 2,352 通过、7 项可选外部环境跳过。Web 单测 1,611 项、默认 Chromium 279 项通过。Python 和 Web 静态检查、两份配置样例、生产构建及源码外 wheel 冒烟通过。候选镜像 `sha256:aee8fe2e45fa18a7611e343f1616382c8b308d6cbc058044220e348ba4d25d7f`，wheel SHA-256 `a56bfb84e5ce6e77e02a890611955e1b08a15d52a9493ae5a889cc5302389244`。原始日志、截图和制品位于 `.git/validation-evidence/eef4d601baabfff70f534d7a016dc4a86bbad867/b-review/`。

## Task 57.1 — B 复核结论

```text
Reviewed: 4566a74055c698aec704215dd431eb8521bcfedb..c12cae6fe0226e7efe6850ac68e6581785fb87e3
Implementation: 3636331bebdc0f8364c02c64c3e14d055bce37bd
Decision: PASS
Task blockers: NONE
Slice Required Outcomes / Surfaces all satisfied: NO
Next: NEXT TASK
```

- **RO-1 已验收。** 用配置生成器和正式镜像启动无媒体挂载的空实例，从主机领取设置码，
  在网页创建唯一管理员并发布空配置。从同一标签页改密可用新密码登录，主机重置可恢复，
  两次操作的旧会话均返回 `401`。核对了 390px 首次设置和 1440px 系统设置的截图。
  四服务同版本重启后回读有效会话和同一 Active。真实账号浏览器 5 项通过，Python 全量覆盖
  一次性码并发、过期和错用、会话边界、同源校验和审计。
- **RO-2 待 Task 57.2。** 当前系统设置缺少 API 令牌签发和管理，需验收脚本身份、权限和轮换。
- **RO-3 的 Task 57.1 范围已验收。** 三项发布指南容器验收退出码均为 0，覆盖无媒体和
  隔离媒体栈、结果与审计回读及同版本故障重启。匿名与旧环境令牌返回 `401`，退役字段
  被拒绝。候选镜像拒绝运行库 schema 58，隔离副本前后 SHA-256 相同。真实自动化浏览器
  32 项通过。从编辑卡停用，Scheduler 到期零新增。先入队再停用，Worker 保留旧任务，
  执行详情显示停止原因及已知效果，处理文件前停止的用例零新增文件效果。重新启用产生独立
  新任务，再次停用时旧记录保留原因并指向当前计划列表。令牌轮换或吊销期间计划照常执行待
  Task 57.2 验收。
- **共享门禁通过。** Python 运行 2,354 项，7 项跳过。Web 单测 1,604 项、默认 Chromium
  279 项、Web 质量检查和生产构建通过。治理、Ruff、编译、依赖、示例配置、完整范围
  `git diff --check` 及源码外 wheel 冒烟通过。候选镜像
  `sha256:a934845ee1bc590df4aed30d7ae0c59c0d460db4f99ca2608c70c2cf0189bee9`。
  wheel SHA-256 `d49329146fbdcf4985fa5464e429d2abb76b9c71d6013e18fd8d6e97276abe06`。
- **记录供最终文档对齐。** 部署指南的两项附加冒烟示例仍指向使用退役环境令牌的脚本。
  已在健康候选栈核对其共享的 Tasks 鉴权步骤会返回 `401`，未完整运行这两项附加脚本。
  发布指南三个当前入口均通过。空配置发布成功后，系统运行设置卡仍带一条 Base 已有的
  Draft 提示，主配置区正确显示空配置已生效，从现有业务入口继续发布及执行的验收已通过。

原始日志和截图位于本地 `.git/validation-evidence/c12cae6fe0226e7efe6850ac68e6581785fb87e3/b-review/`。
真实 CLI 的停用、效果与新执行证据见 `.git/validation-evidence/0c55e8e17fe318692033af93a8a32e7192395a70/b-review/resident-proof.log`。
Task 57.1 约定与各轮交付见 `git show c12cae6f:TASK.md`。
