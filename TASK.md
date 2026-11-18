# NO ACTIVE IMPLEMENTATION TASK

Task55.6 **PASS**。B 已审查 `2e460b71735ac0284e58928c884baac9d3f46009..8e9acf76bb120bf2ece902911bb9f9fe75b83a91`。
用 `git show 27789283a0e1b04bc1e9204002ecdb8cfc44e946:TASK.md` 查看本地复核记录及 Slice55 全部结果重评。
Slice55 仍为 **ACTIVE**。下文为规划草案，等待实施授权。

## 草案 — Task55.7 当前会话与协议，保留原请求核对

依据已提交 [Slice55](SLICE.md) RO-5 及与本单元直接相关的 RO-6，
覆盖 [V2-RETIRE-008–010](docs/v2-requirements.md#target--complete-v1-and-migration-residue-retirement-slice55-active)
中客户端协议、会话和验收要求。生命周期及测试分工遵循 [开发流程](docs/development-workflow.md)。

```text
Proposed Task ID: 55.7
Proposed Task Type: SLICE
Proposed Parent Slice: 55
Draft Status: PLANNED — NOT AUTHORIZED FOR IMPLEMENTATION
Proposed Task Base: 27789283a0e1b04bc1e9204002ecdb8cfc44e946
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

规划起点为 `/Users/songzhidong/mediaflow` 的 `main`，HEAD 为上述提交，原工作区及暂存干净，
工作区与 Git 可写，治理检查通过。Slice Base `2b2e7c1824fa5681864455714d0f97b26555c7dc`
仍用来验证原有 V2 用户数据和未确认请求继续可用。Task Base 用来审查本单元的完整差异。

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

**Developer** 运行新增、改动和直接受影响的用例。以下从已有套件中按实际改动选取，交接保留
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

**B** 审查完整 `Task Base..Developer candidate`，先对照真实生产者与用户旅程复现原请求场景，
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
既有有效数据、独立结果与原 pins。本草案不纳入独立的旧全局批量审核应用／持久化实现，及空实例
部署脚本与发布说明的全链路收敛。这两项仍为 RO-6 的已知待交付项，按实际后续重评处理。
任务完成报告和 B 复核待授权实施并提交候选后填写。
