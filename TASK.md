# Task55.7 — 当前会话与协议，保留原请求核对

用户要求“激活Task”，据此将已提交的 Task55.7 草案激活为正式实施 Task。

Task55.6 **PASS**。B 已审查 `2e460b71735ac0284e58928c884baac9d3f46009..8e9acf76bb120bf2ece902911bb9f9fe75b83a91`。
用 `git show 27789283a0e1b04bc1e9204002ecdb8cfc44e946:TASK.md` 查看本地复核记录及 Slice55 全部结果重评。

依据已提交 [Slice55](SLICE.md) RO-5 及与本单元直接相关的 RO-6，
覆盖 [V2-RETIRE-008–010](docs/v2-requirements.md#target--complete-v1-and-migration-residue-retirement-slice55-active)
中客户端协议、会话和验收要求。生命周期及测试分工遵循 [开发流程](docs/development-workflow.md)。

```text
Task ID: 55.7
Task Type: SLICE
Parent Slice: 55
Status: FIX REQUIRED
Task Base: 27789283a0e1b04bc1e9204002ecdb8cfc44e946
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: TASK55.7 IMPLEMENTATION AUTHORIZED
Next Action: DEVELOPER FIXES TASK55.7 AND RESUBMITS FOR B REVIEW
```

规划起点为 `/Users/songzhidong/mediaflow` 的 `main`，HEAD 为上述提交，原工作区及暂存干净，
工作区与 Git 可写，治理检查通过。Slice Base `2b2e7c1824fa5681864455714d0f97b26555c7dc`
仍用来验证原有 V2 用户数据和未确认请求继续可用。Task Base 用来审查本单元的完整差异。
激活前 `main` 的 HEAD 为 `89882891f346d74e37b1f49e7fd827d6aa586b01`，工作区及暂存干净，
治理检查通过。Task Base 至该草案提交仅变更本文件。

### 目标与用户旅程

管理员在「自动化 → 任务列表」点击已保存定义的「运行一次」。服务器已接收请求，浏览器没收到
响应。管理员刷新、用同一身份重新连接，从列表核对本次运行，打开原 Task 看实际结果。另一条
定义可以独立运行。列表上的「复制」同样核对原请求，成功时指向唯一的新禁用副本。另一个管理员
可能已编辑来源或发布了后继版本，核对仍显示这次操作自己的结果。服务端证据暂不可读时，页面
继续标示结果未知，保留核对入口并禁止重复提交。

同一管理员也能从「系统设置」保存三个运行参数，重开后核对该次发布或拒绝。明确拒绝后可纠正
原输入。另一管理员更新过的字段按实际基线比较，同字段冲突仍需要用户选择。规则卡的未保存
输入、通知的当前投递核对、任务中心同一 Task 的决定和分析继续按原入口工作。

### 当前代码依据

- `AutomationListPage.tsx` 调用 `automation-run-once-session.ts` 与
  `automation-copy-session.ts`。Slice Base 已从列表按身份及定义写独立记录，reader 仍额外读
  旧编辑卡的单条 key、混入待核对列表，页面仍显示专用旧记录提示。旧写入点可在 Run once
  移入列表前的 `AutomationLifecyclePage.tsx`（`325b3133^`）及 Copy 移入列表前的
  `AutomationEditDialog.tsx`（`d6e8f979^`）查证。
- `AutomationSettingsPanel.tsx` 普通编辑从已读 target 保存三项原值。Base 的 reader 还允许
  缺 `baselineValues` 的旧会话。旧会话核对为未发布、基线修订仍相同后，若用户纠正并再次
  保存，原代码还能发送一条新的正式提交且把会话里的基线值省略。该二次提交是否须作为 Base
  的有效请求保留，应由真实写入和服务端证据判断。现有 `automation_settings.py` 用身份、
  提交 ID 和请求内容核对，不依赖浏览器基线原值判断是否发布。
- `rules-workspace-labels.ts` 每次载入当前 v3 草稿都专门删除两个旧 key。当前草稿另有
  `rules-unknown-save.ts` 保存精确发布上下文。通知读模型还映射 `job.*`，当前通知事件目录
  为 `task.*` 和 `schedule.emitted`。自动化表单的 modes reader 吞掉未知值，而
  `AutomationWorkspaceCommands` 的现行授权文档来自唯一可运行模式。
- 真实协议对照包括 `AutomationOccurrencesPage` 的 outcome summary（当前生产者输出
  `statusCounts` 和 `bound.statement`）、Task Center 的 Ignore 与 Continue（当前分别返回
  `requestId` 与 `nativeAnalysis`，前端共用 reader 仍接收旧批次／续作 ID），以及 Files
  准备链路的 `actions.prepare`。手工 action matrix 的 Web 查询模块已有导出但无产品调用。
  后端 `GET /api/v1/operations/manual-actions` 仍有注册，真实响应只有 organize action。
  `OrganizeContinuationHost` 仍由 `OperationsLanding` 使用，历史 occurrence 与 run-once
  详情仍有 Router 注册，沿当前入口和生产者逐一确认其职责。

### 开发指导

1. **收敛列表会话到当前逐项记录。** 沿现有列表按钮捕获真实的 Slice Base 和 Task Base 写入，
   以现有逐身份、逐定义 key 和正式记录为当前格式。删除两个旧编辑卡 key 的读取、合并、清理
   分支和专用状态提示。列表保持原请求 ID／Copy 的原来源和发布版本，现有核对入口在来源被
   筛掉时仍可用。正常响应、明确拒绝和证据暂不可读沿用各自处理；一条结果只清理对应的待办。
2. **将设置的发布核对与表单合并分开。** 普通 Save 从实际读到的精确版本写入完整三项
   `baselineValues`，以同样的身份、提交 ID 及请求值核对原结果。去掉以缺基线旧格式恢复
   表单及逐项猜测的分支。用前一步的真实 Base 复核区分纯旧会话和 Base 用户后来确实发出的
   正式请求；后者用已有的精确核对入口确认结果。只有已读到相同原修订的值才能作为表单合并
   基线，当前 Active 的值不能补成历史原值。已证实未发布且原基线不可用时，读当前发布值，
   让用户明确选择修正后再保存。保留当前冲突处理、输入草稿和发布／采用状态。
3. **按实际生产者收敛 Web 协议。** 从自动化建／编／复制、执行历史、通知、两种库编辑及
   Task Center 正式入口追到 API 响应和前端读模型。删除无生产者支持的旧模式、事件、统计
   字段回落、旧 action／Storage 列表及字段回落。优先处理已定位的统计、模式、通知别名、
   手工 action matrix 客户端、Task Ignore/Continue 的两种现行答复及 Files Prepare。
   对 Storage 用当前发布的系统状态、库存及编辑投影核对每一处字段实际是否总会生成；保留合法
   缺省 Storage 名称、可选 fingerprint、真实不可用状态和现有可读结果。若同一投影还有现行
   API／CLI 消费者，保留其正式字段和行为。删除确认无注册或无生产调用的旧卡和专属请求／模型
   时同时清掉调用链；真实路由、同 Task hosted-card、未知效果的原请求与后续恢复继续存在。
4. **保留当前规则和通知的会话。** 移除规则旧 key 专用清理，保留 v3 未保存草稿和确切发布
   核对、身份隔离、返回与焦点。通知沿原定义／投递入口读规范事件，保留同版本未知发布和
   合法投递恢复。清理随本次退出的测试假服务、样例响应和制品内容，把权限、原请求核对、
   带有效数据的失败以及当前恢复断言接到现有入口。旧输入仅使用旧提交中有写入点的形状和
   现有真实读入口核对。

### 验收

- [ ] **AC-1（Slice AC-06/07）** 列表 Run once 和 Copy 各一次真实已接收、浏览器丢响应，
  从 Slice Base 产生记录后一并由候选在同一浏览器来源重连核对。真实 Task 或唯一副本与原请求
  对应，无第二次业务提交。覆盖两项彼此独立、候选同版本的刷新／重认证、其他管理员后来修改、
  查不到确证仍未知，以及旧编辑卡单条形状退出。Run once 原执行链接可达，Copy 副本禁用。
- [ ] **AC-2（Slice AC-03/07）** 系统设置当前三项保存、精确核对已发布或明确拒绝，原始值与
  输入仍可用。用真实 Base 写入验证保留义务，包括确认上节描述的再次 Save 路径；确实提交
  并有 durable 证据的请求可核对。跨重开及另一管理员改值后，旧请求、当前发布值、实际运行
  采用和下一步分明，较晚响应与同字段冲突不会覆盖较新的输入或别人的发布。
- [ ] **AC-3（Slice AC-06/07/09/10）** 规范模式与统计、通知事件、两种库 Storage 选择及当前
  Task actions 按真实 Python 响应呈现。纯旧形状不能给出新操作、把旧事件重解释或伪造成功。
  规则 v3 输入和 unknown Save 在重开后可核对；通知当前投递恢复与同 Task 的决定、分析、
  精确摘要和确认仍按原旅程，成功兄弟或未知媒体效果不重放。
- [ ] **AC-4（Slice AC-11/12 的本 Task 部分）** 源、真实注册、假服务和候选制品对得上。
  当前按钮、深链和返回仍可用。退役断言用实际旧写入或已存在的协议形状，当前安全断言用实际
  操作和最终结果。候选 Web、源码外安装及适用 Docker 安全检查通过。

### 测试

**Developer — 新增／修改与直接受影响测试**

以下从已有套件中按实际改动选取，交接保留
实际命令及结果。测试和构建的耗时小于本轮总用时的 50%。

```sh
# web/，列表原请求、设置字段合并、规则输入及相关协议
npm run test -- run src/features/operations/automation-run-once-session.test.ts src/features/operations/AutomationListRunOnce.test.tsx src/features/operations/AutomationListCopy.test.tsx
npm run test -- run src/features/operations/automation-settings-session.test.ts src/features/operations/automation-settings-recovery.test.ts src/features/operations/AutomationSettingsPage.test.tsx src/features/rules/RulesEditPage.test.tsx
npm run test -- run src/entities/operations/automation.test.ts src/entities/operations/automation-lifecycle.test.ts src/entities/operations/notification.test.ts src/entities/operations/discovery.test.ts src/entities/operations/organize.test.ts src/shared/api/operations-api.test.ts src/shared/api/storage-management-api.test.ts
npm run typecheck
npm run lint
# 涉及真实响应时，构建后用独立实例运行直接受影响的原生用例
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts -g "lost Copy response"
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-run-once.python.spec.ts -g "lost reply"
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-settings.python.spec.ts -g "lost rejection response"
# 仓库根，改 Python 响应时只选直接受影响的模块
.venv/bin/python -m unittest discover -s tests -p test_automation_definition_occurrence.py
.venv/bin/python -m unittest discover -s tests -p test_v2_notification_operations.py
git diff --check
```

**B — 独立验收与完整回归**

审查完整 `Task Base..Developer candidate`，先对照真实生产者与用户旅程复现原请求场景，
再跑适用的 [T4 全量门禁](docs/development-workflow.md#shared-full-regression-commands)。
在 `web/` 构建后，逐条启动隔离的 Python/Playwright 实例，覆盖发布和复制、Run once、设置
与统计、同 Task 决定和确认，以及两种库普通操作。

```sh
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-run-once.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-settings.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-workspace.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

默认 Web 全量浏览器门禁中的 `notifications.spec.ts`、`rules-readiness.spec.ts` 和
`storage-management.spec.ts` 覆盖相关页面和交互。证据记录 Base 和候选的身份、原请求、实际
写入次数、结果与候选制品。用已有 harness 捕获已提交、丢响应的实际浏览器 session 及隔离库，
在同一来源换候选资产／服务读取，复用 Base 连续性证据中仍匹配的部分。测试和构建计入时间上限，
保留所有原始结果。验收完成后重评 Slice55 的全部 RO。

### 范围边界

本单元限当前会话、协议消费者及其生产者和对应测试。保留正式路由、配置键、权限、Task 内核、
既有有效数据、独立结果与原 pins。旧全局批量审核应用／持久化实现，以及空实例部署脚本和发布说明
的全链路收敛，仍为 RO-6 待交付项，按实际后续重评处理。

### 交接状态 — READY FOR B REVIEW

候选 `cdfcdd6d887d9c03df0167b7f5e80c9dfda53ebc`（Task Base `27789283a0e1b04bc1e9204002ecdb8cfc44e946`..该提交），分支 `main`，提交后工作区／暂存仅余本文件
状态更新。B 审查完整 `27789283a0e1b04bc1e9204002ecdb8cfc44e946..cdfcdd6d887d9c03df0167b7f5e80c9dfda53ebc`。

**本候选的改动**

1. **列表会话只保留当前逐项格式。** `automation-run-once-session.ts` 与
   `automation-copy-session.ts` 删除旧编辑卡整身份 key 的读取、合并、清理和
   `legacy`／`invalidLegacy` 标记；列表页删除两处专用旧记录提示。当前逐身份、逐定义／来源的
   正式记录、原请求 ID、Copy 原来源与发布版本、核对入口不变；一条结果仍只清理对应待办。
2. **设置发布核对与表单合并分开。** 普通 Save 从实际读到的精确版本写入完整三项
   `baselineValues`；`planRecovery` 的“缺基线逐项猜测”分支和
   `EditState.baselineValues | null` 删除。读取侧仍接受 Slice Base 曾写出的无基线记录，
   但只作为可精确核对的未决提交：不恢复其表单输入，也不补当前 Active 值作为历史基线；
   核对证明未发布后表单改为显示当前发布值，用户明确输入后另行保存。
3. **按真实生产者收敛协议。** 执行历史 summary 只读 `statusCounts` 与 `bound.statement`
   （删除 `counts`／`boundStatement` 回落）；自动化定义只读 `occurrenceState`（删除
   `occurrence` 回落）；表单 modes 对未知值 fail-closed 而非静默过滤；Continue／Ignore
   共用答复只接受当前 `requestId`／`nativeAnalysis`（删除 `continuation_id`、
   `continuationId`、`batch_id`）；discovery 的 `actions.prepare` 缺失视为格式错误；
   删除无产品调用的手工 action matrix Web 调用链（实体、查询模块、`api-client` 请求函数及
   专属测试）；run-once 页删除无生产者的 `pausing`／`paused` 文案。
4. **规则会话。** 删除 v3 草稿载入时对两个旧 key 的专用清理；v3 未保存草稿、精确发布核对、
   身份隔离、返回与焦点不变。
5. **测试与夹具。** 旧 list key 形状改为“不被读取”的负向断言；Copy 恢复用例改用当前
   逐来源 key；Task Center 续作用真实 `nativeAnalysis` 答复；settings 用例覆盖“有基线
   冲突合并”和“无基线只核对、再显式修正”两条真实入口路径；删除已退出协议的假响应分支。

**Base 事实复核（用于第 2 项保留义务）**

- `2b2e7c18:web/src/features/operations/AutomationSettingsPanel.tsx`（Slice Base）的普通 Save
  已写入 `baselineValues`（第 689 行），后端 `automation_settings.py` 用身份、提交 ID 与
  请求内容核对，不依赖浏览器基线原值。
- Base 唯一可能写出“无 `baselineValues` 的正式提交”的路径：从更早会话恢复后、原基线修订
  仍相同的情况下直接 Save（`submitBaselineValues = edit.baselineValues ?? null` → 省略字段）。
  该记录对应真实 durable 提交，故本候选仍按原身份／提交 ID／提交值核对，只禁止把它当表单
  合并基线。

**实际验证（命令与结果，cwd `/Users/songzhidong/mediaflow/web`）**

- `npm run typecheck` 通过；`npm run lint` 通过；`npm run format:check` 通过。
- `npm run test -- run` → 102 个文件、1631 项全部通过（162.7 秒）。其中直接相关：
  `automation-run-once-session`／`automation-settings-session`／`automation-settings-recovery`／
  `automation-lifecycle`／`discovery`／`automation`／`notification`／`organize`／
  `operations-api`／`storage-management-api` 实体与 API 用例，
  `AutomationListRunOnce`／`AutomationListCopy`／`AutomationSettingsPage`／
  `AutomationWorkspaceReadModel`／`AutomationRouter`／`OperationsInventory`／
  `RunDetailTabs`／`OrganizeDiscoveryPage`／`OrganizeRouter`／`ManualOrganizeDialog`／
  `TaskItemRecoveryPanel`／`RulesEditPage`／`StorageFilesPage`。
- `npm run build` 通过（仅有既有 chunk 体积提示）。
- 仓库根：`python3 scripts/check_governance.py` → PASS；`git diff --check` 通过。
- 本轮未改 Python 响应，故未运行 Python 模块用例；这些属于 B 的 T4 验收。
- 测试与构建累计约 10 分钟，小于本轮约 45 分钟的 30%。

**未由 Developer 执行（不记为通过；B 的 T4 门禁）**

- 真实 Python／Playwright 丢响应链路（`lost Copy response`、run-once `lost reply`、
  settings `lost rejection response` 等）、Base→候选同一浏览器来源换资产的连续性、完整 Web
  E2E、Docker 空实例／重启／安全镜像、wheel 外安装与镜像身份、Python 全量回归。
- 因此“从 Slice Base 产生记录后由候选同源核对”“另一管理员并发修改后的原请求核对”等
  仍待 B 的实际实机证据。

**已知未完成／需 B 裁定的相邻残留（未扩大范围）**

- 通知 `job.*` 读别名**未删除**：真实 Python 投影 `ConfigurationObjectService._webhooks_projection`
  对已接受定义原样返回存储字节，`tests/test_webhook_management.py` 明确断言该保留；
  当前输入校验已在服务端拒绝新写 `job.*`。删除 Web 别名会使用既有合法 Active 定义在
  Web 不可读。若 B 认为该别名仍须在本 Task 退出，需要同时改投影为规范事件并调整该
  Python 断言，超出本轮已确认的 Web 消费者范围。
- `GET /api/v1/operations/manual-actions` 仍有真实注册与 Python 用例，但已无任何产品消费者；
  本候选只清掉 Web 调用链，是否撤销该 API 属于服务端接口边界决定。
- 执行历史生产者仍同时输出 `counts`、`occurrence`、`boundReached` 等重复字段；Web 已不再读取，
  生产者的重复字段清理未在本候选执行。
- 完整 T4 回归、E2E 与打包门禁保持 B 所有；本报告不构成 PASS。

### B 独立复核 — FIX REQUIRED（2026-11-19，北京时间）

```text
Task Base: 27789283a0e1b04bc1e9204002ecdb8cfc44e946
Reviewed Candidate: cdfcdd6d887d9c03df0167b7f5e80c9dfda53ebc
Reviewed Handoff Head: bd0acfd31688e48255a792457b18333cafa9aafb
Decision: FIX REQUIRED / SAME TASK FIX LOOP
```

从干净的 `main` 审查了完整 Task Base..Reviewed Candidate。候选之后的两次提交仅更新
本文件的交接内容。Run once、Copy 和设置分别用现有真实 Python 浏览器入口核对。

| 阻塞 | 实际结果 |
|---|---|
| B55.7-01 · P1 · AC-3/4 | 管理员从运营首页进入自动化任务列表，Task Base 显示统计和任务行，候选在默认浏览器门禁显示「自动化不可用」。候选要求 `occurrenceState`，仓库浏览器测试服务的已发布、仅草稿定义仍只返回 `occurrence`。同一旅程中，真正的 Python 定义与到期执行历史仍同时发布新旧字段。实际响应包含 `occurrence`／`occurrenceState` 和 `counts`／`statusCounts`，两份计数完全相同。 |
| B55.7-02 · P1 · AC-3 | 管理员在 Slice Base 经正式配置 API 导入、验证并激活当时样例中的 Webhook。候选重开同一隔离库，Active ID、摘要和运行时订阅保持，通知列表和定义详情却仍把 `job.*` 交给浏览器翻译。当前 Web 读模型及正向断言继续支持旧拼写。这个前端协议仍有两套事件名，既有正式通知定义又必须继续使用。 |
| B55.7-03 · P1 · AC-4 | 授权用户在有效库上调用曾用于 Files 的 `GET /api/v1/operations/manual-actions`，候选仍返回 HTTP 200 并提供整理动作矩阵。当前用户直接从文件页选择文件、发起整理、修正选择、核对摘要后确认，真实浏览器已走通。旧矩阵只剩注册、专用实现及测试。 |

#### 本轮开发指导

1. 从实际 Python 定义和到期执行历史投影收敛 `occurrenceState`、`outcomeSummary.statusCounts`
   及 `bound`。删除已核对无正式用途的重复字段 `occurrence`、`counts`、`itemOutcomeSummary`
   和与 `bound.reached` 重叠的字段。保留现有 API 入口、实际统计、文件结果、注意项和 Task 链接。
   把真实 API 集成测试的失败计数断言从 `counts` 接到 `statusCounts`。同步更新默认浏览器测试
   服务的已发布和仅草稿定义，使用 `occurrenceState`，保留原浏览器操作及断言。验收为管理员从
   运营首页进自动化，看到统计、任务行和既有动作，查看到期记录时打开原 Task。
2. 通知列表、详情和草稿编辑响应统一使用当前事件名。复用既有已接受通知定义解析结果生成读投影，
   让 Slice Base 发布的同一 Active／Webhook 在候选显示 `task.*` 和 `schedule.emitted`。
   以原 ID、原文档和原摘要校验持久化完整性；既有订阅、投递历史及投递恢复继续按现行入口工作。
   当前提交继续拒绝 `job.*`，Web 读模型和测试只接受当前投影。把原来检查投影等于存储字节的
   断言调整为同时验证规范响应、原存储字节和读取前后的 Active 身份。保留配置、通知权限和脱敏断言。
3. 退出无产品消费者的旧矩阵注册、专用服务端投影和对应假服务分支。沿已注册的旧入口和既有
   正常授权测试断言通用 `404/not_found`。把依赖旧矩阵的现行安全断言接到 Files 的文件选择、
   整理分析、原摘要、确认及原 Task 结果，保留有界选择、权限、源身份、最终效果和零重放检查。

Developer 运行以下失败用例和直接受影响的验证。各浏览器命令使用既有入口及自带测试服务。

```sh
# 仓库根
.venv/bin/python -m unittest discover -s tests -p test_automation_authorized_execution_matrix.py -k test_api_definition_detail_and_occurrence_routes_share_summary
.venv/bin/python -m unittest discover -s tests -p test_v2_automation_operations.py
.venv/bin/python -m unittest discover -s tests -p test_webhook_management.py
.venv/bin/python -m unittest discover -s tests -p test_v2_notification_operations.py
.venv/bin/python -m unittest discover -s tests -p 'test_manual_operations*.py'
.venv/bin/python -m unittest discover -s tests -p test_v2_manual_organize.py
git diff --check
# web/
npm run test -- run src/entities/operations/automation.test.ts src/entities/operations/notification.test.ts src/features/operations/NotificationRouter.test.tsx
npm run build
npm run test:e2e -- tests/e2e/automation.spec.ts -g 'definition table|occurrence history'
npm run test:e2e -- tests/e2e/notifications.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g 'brand-new ambiguous source|Notifications page reads the real Task event contract'
```

#### B 实际验证与余项

- 隔离构建了 Task Base 和候选。默认浏览器 `automation.spec.ts -g 'definition table'` 在 Base
  通过，候选失败。页面快照和 trace 记录「自动化不可用」及响应与当前协议不符。
- 候选真实 Python 浏览器用例共 5 项通过，覆盖 Run once 丢响应后的原 Task 核对、Copy 丢响应
  后重载并核对唯一副本、设置拒绝响应丢失后继续修正、Files 原页修正后整理，以及当前通知生命周期事件。
- 用既有 Python 测试环境验证授权的旧矩阵返回 200，实际到期工作产生的定义与历史响应仍含重复字段。
  另用 Slice Base 的正式导入、验证、激活 API 建立无旧调度的 V2 配置。候选重开同库，确认通知列表
  和详情均返回 200、相同 Active ID 和摘要，应用内部订阅为 `task.*`，页面接口仍输出 `job.*`。
- 本地证据在 `.git/validation-evidence/cdfcdd6d887d9c03df0167b7f5e80c9dfda53ebc/task55-7-b/`。
  测试和构建按串行相加保守小于 45 秒，审查已超过 5 分钟。依据已复现的阻塞，B 将完整 T4、
  Base 到候选同一浏览器来源的原请求核对、双管理员操作及包／镜像验收留到修正候选。

#### Slice55 全部结果重评

| 结果 | 当前状态与剩余范围 |
|---|---|
| RO-1 | 已接受的旧 Web 入口退出证据仍适用。候选入页回归列在 B55.7-01，真实 Python 当前自动化、Files 和通知入口的相关原生用例通过。 |
| RO-2 | 旧调度、票据、grant 和 Pause/resume 的既有验收仍适用。当前 Files 到整理结果走 Task；旧动作矩阵退出见 B55.7-03。 |
| RO-3 | 正式规则、容量键和取消权限沿用已接受结果。已接受通知定义的现行协议收敛见 B55.7-02。 |
| RO-4 | 五态、新库结构及合法 V2 库的较早验收仍适用，候选差异涉及 Web 消费端。此次独立跨版本通知读回保留 Active ID 与摘要。 |
| RO-5 | 候选已清退列表单条旧会话和规则旧 key 清理。当前会话的真实丢响应核对已有上述结果。协议收敛及 Base 浏览器原请求连续性仍待完成。 |
| RO-6 | 本候选的浏览器测试服务与真实协议差异已定位。全局批量审核应用／持久化残留、空实例脚本和发布说明的全链路收敛、Slice 最终制品与安全验收仍待交付。 |

### Developer 修正交接 — READY FOR B REVIEW（2026-11-19，北京时间）

```text
Task Base: 27789283a0e1b04bc1e9204002ecdb8cfc44e946
Developer Candidate: 83423d212af207d3d99807506d173c7bfb211c00
Branch: main
```

候选由 `cb0145fe6ca7fdf1176322b1dfeac80c9917de5a` 与
`83423d212af207d3d99807506d173c7bfb211c00` 两个本地检查点组成；后一提交仅删除
`outcomeSummary` 中未被任何消费者读取的 `attentionItems`／`moreAttention` 重复投影。
候选提交后工作区仅余本文件，下一次文档检查点只记录这份交接。B 审查完整
`27789283a0e1b04bc1e9204002ecdb8cfc44e946..83423d212af207d3d99807506d173c7bfb211c00`。

**对应 B55.7-01 — 自动化定义与执行历史投影**

- `automation_definition_occurrence.py` 定义只发布 `occurrenceState`，删除同值的
  `occurrence`；摘要删除 `counts`、`itemOutcomeSummary`、`boundReached`、
  `stoppedAtBound`，保留 `statusCounts`、`bound.reached`、`bound.statement`、注意项、
  文件结果和 Task 链接。
- 真实 API 集成测试的失败计数断言改为 `statusCounts`，并断言上述重复字段不再出现。
- `web/tests/fake-server.mjs` 的已发布与仅草稿定义改用 `occurrenceState`；执行历史夹具
  删除无当前生产者的 `jobId`／Job action，保留原 Task 链接和既有浏览器操作。

**对应 B55.7-02 — 通知规范事件投影**

- `ConfigurationObjectService._webhooks_projection` 复用
  `accepted_webhook_definition` 的已接受定义解析结果，把读取投影的 `events` 规范为
  `task.*`／`schedule.emitted`；不改写持久化文档、原 ID、digest 或 Active 指针。
- `test_webhook_management.py` 用旧事件字节建立并激活一个真实历史 Active，验证配置对象、
  通知列表、详情、草稿编辑均返回规范事件，同时复核原存储字节、原摘要和读取前后 Active
  ID／digest 不变。
- `web/src/entities/operations/notification.ts` 删除 `job.*` 读别名；列表、详情、草稿、
  投递只接受当前事件目录，旧拼写按格式错误保守拒绝。相关前端用例改为拒绝旧拼写。

**对应 B55.7-03 — 旧手工 action matrix 退出**

- 删除 `GET /api/v1/operations/manual-actions` 的注册、`_manual_action_matrix` 专用投影、
  `manual_action_matrix_operator_document` 导出及 Node 假服务路由／文档函数。
- 旧入口在有效普通授权下返回通用 `404/not_found`；契约、原生旅程和假服务用例均按此断言，
  并验证零 Task、零 Storage 变更。
- 原矩阵测试删除；有界选择、权限、源身份、分析摘要、确认、最终效果和零重放继续由真实
  Files 入口用例覆盖（`FilesAdmissionJourneyTests`、manual Organize 旅程和契约夹具）。

**实际验证（cwd 与命令，结果）**

- 仓库根 `ruff format --check`／`ruff check` 于全部改动 Python 文件通过；
  `python3 scripts/check_governance.py` → PASS；`compileall -q mediaflow tests scripts`
  通过；`git diff --check` 通过。
- `.venv/bin/python -m unittest tests.test_manual_operations tests.test_manual_operations_contract
  tests.test_v2_manual_organize tests.test_webhook_management tests.test_v2_automation_operations
  tests.test_automation_authorized_execution_matrix` → 93 项通过（9.8 秒）。
- 另跑 `test_automation_definition_occurrence`（13 项）、`test_v2_notification_operations`
  （25 项）、`test_v2_automation_operations`（19 项）及最终两次改动后复跑，均通过。
- web `npm run test -- run src/entities/operations/automation.test.ts
  src/entities/operations/notification.test.ts src/features/operations/NotificationRouter.test.tsx
  src/entities/operations/organize.test.ts src/entities/operations/preview.test.ts` →
  5 文件／166 项通过（6.7 秒）。
- web `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过
  （构建仅既有 chunk 体积提示）。
- 默认浏览器 `npm run test:e2e -- tests/e2e/automation.spec.ts
  -g 'definition table|occurrence history'` → 3 项通过；
  `notifications.spec.ts` → 12 项通过；`manual-operations.spec.ts` → 6 项通过。
- 真实 Python 浏览器
  `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts -g "Notifications page reads the real Task event contract"`
  → 1 项通过。
- 测试与构建累计约 55 秒，小于本轮总用时（约 50 分钟）的 30%。

**未由 Developer 执行（不记为通过；B 的 T4 门禁）**

- 完整 T4 回归、真实 Python 丢 Copy／Run once／设置响应链路、双管理员并发、Base→候选
  同一浏览器来源换资产连续性、Docker 空实例／重启／安全镜像、wheel 与源码外安装。
- 全量 Web 浏览器门禁及其余 Python 模块回归。
- 本报告不构成 PASS；B 需按修正后的候选重新复现三个阻塞并完成适用门禁。

**剩余风险／需 B 核对**

- 通知读取投影规范化的是响应 `events`，原 Active／Draft 存储字节仍保留旧事件拼写；
  这是有意保留的已接受配置读取，写入新定义仍由现有校验拒绝 `job.*`。
- 自动化定义的顶层便利字段（如 `nextRunAt`、`outcomeSummary`）未在本轮 B 指定删除
  列表内，仍保留原 API 形状；Web 只消费 `occurrenceState`。如 B 认为同属重复协议，
  需在同一 Task 继续裁定。
- `scopeExhausted` 仍随摘要输出且当前恒为 `None`；不在本轮明确删除列表内。

### B 第二轮独立复核 — FIX REQUIRED（2026-11-19，北京时间）

```text
Task Base: 27789283a0e1b04bc1e9204002ecdb8cfc44e946
Reviewed Candidate: 83423d212af207d3d99807506d173c7bfb211c00
Reviewed Handoff Head: a1a5e2328c9c45a523e22ed75c8f12e507449991
Decision: FIX REQUIRED / SAME TASK FIX LOOP
```

从干净的 `main` 复核完整 Task Base..Reviewed Candidate，交接提交仅变更本文件。
B55.7-01 已复验通过，真实历史响应和默认浏览器使用当前字段，自动化列表、统计和原 Task 链接可用。
B55.7-03 已复验通过，旧矩阵在真实有效库上返回通用 `404/not_found`，现行 Files 整理旅程通过。
B55.7-02 已复验列表、详情及草稿的规范事件投影，已接受定义的后续操作仍有一个阻塞。

#### B55.7-04 · P1 · AC-3 — 既有 Webhook 无法复制或启用

在 Slice Base 用正式 API 导入、验证并激活配置，其中已有一个停用的 Webhook。用候选重开同一 SQLite
库，Active ID 和摘要一致。管理员在「通知」打开此定义并创建后继草稿，详情正确显示当前事件，也提供
「复制到草稿」和「在草稿中启用」。这两个按钮实际均返回 `400 invalid_request`，页面分别提示动作没有执行，
候选的草稿版本保持 1。用 Slice Base 和同样的操作做对照，复制成功写入一个停用副本，启用成功写入原定义，
两个结果各推进一次草稿版本，写入的都是当前事件，Active 仍保持原版。

在候选中，现有编辑入口提交页面显示的当前事件可保存、验证并发布。向同一个编辑入口提交旧事件名时
仍返回 400，草稿版本保持。这把修正范围落在服务端替用户组装草稿内容的两个方法。

11 月 17 日的 `7962432a` 收紧了新写入的事件校验，`f6ab37c8` 恢复了对已接受定义的运行时读取。
本候选又让浏览器收到规范事件名。复制及启用／停用仍将数据库里的旧事件原样送入新写入校验，
因此管理员看到可用动作，点击后却无法继续。两项操作都由服务端从已保存定义组装输入，浏览器只提交所见草稿版本。

#### 本轮开发指导

1. 在 `ConfigurationObjectService.copy_object` 和 `set_object_enabled` 的 Webhook 分支，读取准确
   草稿里的已保存源定义后，复用 `accepted_webhook_definition` 得到当前事件名。将当前事件写入本次新副本
   或明确要启用／停用的定义，继续走现有 `mutate`、权限、版本校验和审计。保留源项、未选的其他定义及
   原 Active 的已保存字节。用户新建或手工提交的 `job.*` 仍由当前输入校验拒绝。
2. 扩充 `test_accepted_historical_webhook_is_projected_with_current_events` 所在用例组。以已发布的
   Slice Base Webhook 为起点，从详情所给动作建立草稿，分别核对复制与启用／停用。复制产生唯一停用副本，
   原定义字节保持。启用／停用只改所选定义，返回当前事件，发布前 Active ID 与摘要保持。用独立草稿核对
   既有的检查和显式发布流程，确认原定义仍可按原订阅读取、事件历史和投递记录仍可见。保留真实 stale 版本、
   权限和同草稿其他定义发布限制的现有断言。

```sh
# 仓库根
.venv/bin/python -m unittest tests.test_webhook_management tests.test_v2_notification_operations
git diff --check
# web/，如有通知界面或夹具改动，复验同一详情入口
npm run build
npm run test:e2e -- tests/e2e/notifications.spec.ts
```

#### 本轮验证与 Slice55 重评

- 候选 Python 定向 67 项、默认浏览器定向 28 项通过。Web 单测 102 文件／1631 项、默认浏览器全量
  285 项通过，Web typecheck、lint、format、build 和 Python 质量检查通过。真实 Python 浏览器分实例
  通过自动化生命周期 21 项、Run once 8 项、系统设置 18 项、自动化工作区 9 项、运营与整理 47 项。
- Python 全量 2326 项，2318 项通过、7 项既有可选用例跳过、1 项失败。失败仅来自本 Task 测试分工标题
  缺少仓库模板标记，B 已在本文件修正分工标题，独立复跑 `tests.test_release_security` 8 项通过。
- 候选 wheel 构建与源码外安装 smoke 通过，SHA-256 为
  `b8d51887f6335db264d085e3f223b45275c81cd0f71c6a9f199333ea9caad890`。
- 两种库普通文件的原生套件启动时与生命周期套件占用同一端口，该次运行未进入用例。Docker 镜像门禁、
  剩余文件原生套件及 Slice Base 到候选的同浏览器原请求核对留给修正候选。
- 实际证据在 `.git/validation-evidence/83423d212af207d3d99807506d173c7bfb211c00/task55-7-b/`。
  `webhook-base-publish.log`、`webhook-base-commands.log`、`webhook-candidate-commands.log` 和
  `webhook-browser.log` 记录同库重开、真实请求、草稿版本和浏览器反馈，`webhook-editor-control.log`
  记录现行编辑、发布和旧事件输入拒绝。

| 结果 | 当前状态与剩余范围 |
|---|---|
| RO-1 | 旧 Web 入口退出的既有验收继续适用。本轮默认浏览器全量和当前自动化入口通过。 |
| RO-2 | 旧矩阵通过注销验收。当前 Files 选取、整理、同 Task 决策和执行通过原生案例，旧调度和授权的既有验收继续适用。 |
| RO-3 | 当前通知事件投影已验证，已接受的 Webhook 继续使用仍受 B55.7-04 阻塞。正式配置键和权限沿用既有验收。 |
| RO-4 | 五态及正常库重开证据仍适用。本轮跨版本通知复验读到同一 Active 与摘要。 |
| RO-5 | 当前原请求恢复和规范响应在本轮对应浏览器中通过，已有 Webhook 的完整管理旅程及跨版本浏览器原请求验收待完成。 |
| RO-6 | 当前构建和 wheel 已验证。剩余全局批量审核实现、空实例部署脚本及发布说明，以及最终候选镜像与 Slice 验收仍待交付。 |
