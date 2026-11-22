# Task 57.2 — 在系统设置签发、使用和吊销 API 令牌

Next Action: DEVELOPER STARTS TASK57.2 IMPLEMENTATION

```text
Task ID: 57.2
Task Type: SLICE
Parent Slice: 57
Status: PLANNED
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

**Developer — 受影响范围**

- 在仓库根目录执行 `.venv/bin/python -m unittest tests.test_api_credentials tests.test_web_account_auth`。
  将凭证回归放在现有测试模块，覆盖签发和持久状态、两组权限、`401/403`、Authorization 优先级、
  同源写入和审计。运行 `.venv/bin/python -m unittest tests.test_container_deployment`，
  核对运行库变更后的空库预检和同版本重开。
- 在 `web/` 执行
  `npm run test -- run src/features/configuration/ConfigurationPage.test.tsx`、`npm run typecheck`
  和 `npm run build`。从现有系统设置浏览器规范增补令牌旅程，以
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/configuration-settings.python.spec.ts`
  验证签发、丢回包核对和吊销。跑改动文件的静态检查及 `git diff --check`。

**B — 独立验收**

- 从真实 Compose 的系统设置签发两种令牌，用正式 Tasks 及整理 API 核对权限、效果、轮换、
  会话和审计，重启后复查。用隔离媒体观察既有计划在脚本凭证变化后继续受理及完成。
- 运行[共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)，对候选镜像
  和源码外安装的 wheel 验收，并取齐 Slice 57 的最终证据。

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
