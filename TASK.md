# NO ACTIVE IMPLEMENTATION TASK

Task52.2 已由独立 B 复核 PASS。本轮基于真实代码规划 Task52.3；以下为 **PLANNING ONLY**
草案，不授权实施。Slice52 仍 ACTIVE，剩余 RO-4 尚未交付。

# Task52.3 — 自动化旧“打开”与后继 Draft Web 链路退出（规划草案）

Authority: committed [Slice52 Contract](SLICE.md)（合同 checkpoint
`c7913f6a751ee980db2b82ffaefec40d3d43528c`）的 RO-4、AC-7/8；生命周期和测试分工遵循
[Development Workflow](docs/development-workflow.md)。实施者阅读
[Developer experience](docs/agent-experience/developer-implementation-role.md)，审查者阅读
[B experience](docs/agent-experience/task-planner-reviewer.md)。

```text
Task ID: 52.3
Task Type: SLICE
Parent Slice: 52
Status: PLANNED
Task Base: f4279b95a1ee05095fa940247f2fa26f15cbf042
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: NOT AUTHORIZED — PLANNING ONLY
```

## Planning checkpoint and accepted delivery

2026-11-08，仓库 `/Users/songzhidong/mediaflow`，分支 `main`，HEAD 即上述 Task Base。
治理检查 PASS；TASK.md 和 Git 可写、暂存区为空。预存跟踪变更仅 `mediaflow/.DS_Store`；
未跟踪 `.DS_Store`、`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、
`docs/`／`docs/pics/`／`output/`／`testdata/`／`web/` 元数据和 output 下既有调查／预览
材料均保留，不纳入提交。本轮仅维护根 TASK.md，不读取用户运行数据库、私有配置或媒体。

先核对已交付结果：

- RO-1／RO-2：Task52.1 的独立 B PASS 保持，Base
  `c7913f6a751ee980db2b82ffaefec40d3d43528c` → 实现
  `62a158f684996372b08b7a570368ffcf1b4cb194`；见
  [固定报告](https://github.com/kentinya/mediaflow/blob/4cf0efdf23981351ee3c7ef19d599726a070a4bb/TASK.md#b-review-result)。
- RO-3：Task52.2 的独立 B PASS 保持，Base
  `4cf0efdf23981351ee3c7ef19d599726a070a4bb` → 实现
  `35fec54ccd412d061f75ff22075fbe3472829ea8`；见
  [固定报告](https://github.com/kentinya/mediaflow/blob/f4279b95a1ee05095fa940247f2fa26f15cbf042/TASK.md#b-review-result)。
  本轮核对该实现至 HEAD 仅 TASK.md 变化；不重新签署其产品验收。
- RO-4：名称／打开、旧 definition／editor 路由及历史返回链接仍在，尚未交付。
  本 Task 完成后必须重评全部 Slice 结果；若全部满足，停止规划并准备交 A，不能再造清理 Task。

旧报告中的 403 文案重复定位、三条设置容量脚本使用旧 Files“目录”入口的实际失败及
Base 对照事实保留，不宣称旧 E2E 全绿。Slice/Roadmap/Progress 早期“首次规划”措辞及
CURRENT/TARGET 的最终协调留给 A；本草案不改合同或旧接受事实。

## Goal and complete journey

完成 `V2-AUTO-016`，保留 `V2-AUTO-001/002/004–006/013–015` 的有效管理、记录和恢复
语义，以及 `UX-001/002/004/007/009/010`、`REQ-WEB-001/004–006`、`REQ-SAFE-005–007`。
完整依据为 [Slice52 TARGET 旅程](docs/product-experience.md#target--slice52-experience-refinement-active)、
同文 CURRENT Automation forms/direct Run once 与 Complete native Automation workspace，
以及 [Architecture TARGET](docs/architecture.md#target--slice52-experience-refinement-active)
和 CURRENT Automation forms、intent/Run once、workspace 合同。旧 Web 保留义务由本 Slice
授权退出，其他 CURRENT 能力保持。

用户从侧栏“自动化 → 任务列表”查看名称、状态、来源、调度和最近结果；名称是普通文本，
不再有“打开”。明确点击新建、编辑、复制或运行一次仍进入原有旅程：新建／编辑及有效
深链打开列表上的中文卡片，保存及启停以真实读回反馈并返回原列表；复制产生停用副本，
运行一次保留本行独立结果和准确 Task 链接。执行记录继续查看本次运行的结果、时间、
原因与下一步；历史 occurrences／run-once 页面和原有 Task 查看／四类恢复保持可达。

读取失败保留该页已有的重读／返回入口；校验／权限拒绝保留可纠正输入，冲突要求明确
重读，未知创建／保存／复制／运行一次继续核对原请求。访问旧 definition／editor 地址
得到现有普通未找到页面；退出页面不提交或重放命令，不提供替代旧详情的说明／跳转页。

## Actual code and existing entries

路径均为已注册入口，浏览器前缀为 `/ui-v2`。探测从侧栏、现有控件或这些已知深链进行；
失败／迟到响应只作用于该旅程真实发出的请求，不构造产品中不存在的操作。

| 实际入口／消费者 | 当前代码与本 Task 处理 |
|---|---|
| 列表 `/operations/automation` | `AutomationInventory.tsx::AutomationDefinitionRow` 的名称 button 和“打开”都调用 onOpen；`AutomationListPage.tsx::openDefinition` 及中间列表 props 转发该回调。删除整条回调链，名称改普通文本，保留有效行操作及反馈。 |
| 旧 `/operations/automation/definition/$definitionId` | Router 挂载 `AutomationDetailPage.tsx`；页面提供 Start successor Draft、Edit successor Draft 和 Copy into Draft。删除页面、路由、导航身份及专属客户端依赖，不将旧控件迁入中文卡片。 |
| 旧 `/operations/automation/editor/$definitionId` | Router 挂载 `AutomationEditorPage.tsx`，独立执行 Draft 保存／校验／激活。与上述旧详情一起退出。 |
| 有效 `/operations/automation/lifecycle`、`/lifecycle/$definitionId`、`/new` | 前两者为当前新建／编辑卡，new 是已有同卡创建入口；`AutomationLifecyclePage` 复用 `AutomationListPage`。全部保留，含登录续转、重载、列表返回与未保存选择。 |
| `/operations/automation/occurrences/$definitionId` | `AutomationOccurrencesPage.tsx` 的成功及失败分支都返回旧详情。改为合法列表／执行记录入口（默认执行记录并带该 definition 的筛选；已有合法列表返回条件可保留）；保留分页、真实历史、Run once 历史及准确 Task 链接。 |
| 导航／认证返回 | `router.tsx` 注册、`destination-model.ts` 的两个 destination、dynamicPrefix 及 search 恢复分支都包含旧路径。随路由删除，不影响 lifecycle、occurrences、run-once 或通知路由。 |
| 查询与 API 客户端 | `automation-query.ts` 的 definition／draft 查询仅供两旧页消费；API 客户端对应 detail/draft 读取、旧 successor／save／copy／activation 包装按实际消费者清理。列表使用独立的 `copyAutomationDefinitionFocused`，不属于旧 Copy into Draft。 |
| 共享边界 | `NotificationEditorPage.tsx` 仍调用 `validateAutomationDraft`，必须保留其传输和共用解析；`automation-list-return.ts` 仍有有效卡片消费者。`normalizeAutomationDefinition`／actions／draftState 被 inventory 使用，不可因旧页删除一并去掉。 |

records payload 的 `handoff.definitionSettings` 在当前 `AutomationInventory` 记录行不渲染为
链接；它不是另一个可点击入口。保留后端共享投影／API 契约，不为清掉字符串而改服务端。
客户端模型、样式、夹具和 fake-server 分支仅在确认专属于退役页且无其他消费者时删除。

## Implementation scope and Developer guidance

1. **先移除入口和路由。** 在 `AutomationDefinitionRow` 移除名称交互和“打开”，逐层删除
   onOpen／openDefinition；保留名称阅读、行高亮及现有动作顺序与权限反馈。删除 Router
   两旧页 import／注册、destination 元数据与仅为其恢复 search 的分支，使用已有普通
   not-found。保留当前 lifecycle 卡片和 new 创建入口，核对 Shell 的自动化身份／标题。
2. **修好历史返回。** 调整 occurrences 成功和失败返回链接，落在有效自动化列表／记录
   及正确 definition 范围，不再依赖旧详情。保留原分页、Run once 历史、准确 Task 查看；
   不在执行记录详情中新增导航、恢复或执行控件。更新仍存文件里对旧旅程的过时注释。
3. **按消费者删除旧实现。** 删除 `AutomationDetailPage`／`AutomationEditorPage`，清理
   definition／draft 查询及两页专属 API 包装、DTO／解析、样式和夹具。先用引用搜索核对
   每项存活消费者；共享的通知 Draft 校验、配置管理、列表 focused Copy、未知请求会话、
   inventory 模型和历史查询保留。不建设退役注册表、兼容层、通用命令框架或新防御分支。
4. **迁移直接受影响测试。** `AutomationRouter.test.tsx`、`automation.spec.ts` 有大量旧
   detail／Draft 旅程断言；这些专属能力的断言随退役删除，并补已有旧地址普通未找到、
   列表名称无交互及动作可用、历史返回有效的行为覆盖。`automation-lifecycle.python.spec.ts`
   仍通过旧详情核对保存／删除后历史／损坏发布证据：保留有效入口的原保障，把历史事实
   放到现有 occurrences／records／有效 lifecycle 或共享 API 的现有测试中核对，不要求
   保留退役页面，也不整段删掉仍有效的历史／Active／错误保障。fake-server 只清专属部分。
5. **完成真实旅程和交接。** 用既有 Node／真实 Python 临时 SQLite 夹具走完整入口，核对
   桌面1536×1024和390×844列表、新建／编辑卡、复制／运行一次、执行记录、历史返回及
   键盘／焦点；只补本 Task 缺的覆盖。交出一个完整实现 checkpoint、真实测试结果和剩余
   限制，由 B 独立审完整 Task Base..Head。不得在本轮宣布 Slice 关闭。

代码范围为上述 Web 页面、Router／导航模型、专属 API 客户端／模型／样式及直接受影响
测试、必要夹具和注释。后端／CLI、数据和 schema、发布／权限／执行引擎、Storage、已有
请求身份和未知核对机制不改。若实际必须改变这些边界，先交 B 重评范围及 T4 风险。

## Acceptance Criteria

- [ ] **TAC-1 列表入口退出：** 有结果、筛选／分页、刚创建／保存／复制高亮时，名称均为
  可读普通文本，不能点击或键盘进入旧详情；无“打开”。现有新建、编辑、复制、运行一次
  及其权限／独立反馈保持，桌面和390px可用；不新增另一旧详情入口。
- [ ] **TAC-2 旧链路完整退出：** 两旧已知地址包括原有查询条件，直接访问／重载及原登录
  续转均按现有普通未找到处理，不保留 alias、redirect、说明页、旧导航身份、页面或专属
  依赖。单纯查看不发旧详情／Draft 请求、配置命令或工作准入。
- [ ] **TAC-3 当前管理完整：** 列表及有效创建／编辑深链仍到同一中文卡片；确切值、保存、
  显式启停、取消／未保存选择、权限／校验／冲突、未知发布核对及列表条件／位置／焦点
  返回保持；复制仍是新 ID 的停用副本，运行一次仍明确提交一次并可查看准确 Task。
- [ ] **TAC-4 历史与恢复：** occurrences 成功／失败均可返回合法列表／执行记录及正确范围，
  删除定义后的记录／原 pin／结果仍可读，损坏证据仍显示读取失败与原恢复入口；分页／
  Run once 历史／Task 链接保持。执行记录的简洁结果／原因／下一步与四类恢复原归属不变。
- [ ] **TAC-5 清理及不重放：** 专属代码和测试退出，存活消费者无悬空依赖；通知编辑与
  共用 Draft 校验仍可用，共享管理 API／CLI 保留。旧页面退出不删除定义、配置、Task、
  Result、审计或运行记录，不丢未知创建／保存／复制／运行一次核对上下文，不自动重发。
- [ ] **TAC-6 已交付结果保持：** 探索 RO-1/2、九页切换／读取与两库刷新 RO-3 无直接回归；
  探索／纯导航零业务 mutation、原鉴权隔离／Active／pins／fences 保持。B 在本 Task
  PASS 后逐项重评 RO-1–4／AC-1–8，并按完整 Slice Base..Head 准备交 A。

## Required Tests

按[工作流测试分工](docs/development-workflow.md#6-test-levels)。本轮仅规划，以下为未来
候选上的执行计划；未执行产品测试，未给新实现 PASS。

**时间约束：** 每轮实施／B 复核，测试耗时必须小于该轮总耗时50%；记录起止和测试时段，
并行测试按区间并集计。先审实际代码和完整用户旅程，复现已知阻塞后再跑昂贵门禁；不以
等待凑比例、不重复相同覆盖。必需门禁未完成则保留待验收及原因，不宣称 PASS。

### Developer — new/changed and directly affected

仓库根先运行 `python3 scripts/check_governance.py`；以下命令 cwd 为 `web/`。

```sh
npm run typecheck
npm run test -- run src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationCreateDialog.test.tsx src/features/operations/AutomationListCopy.test.tsx src/features/operations/AutomationListRunOnce.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/routes/router.test.tsx src/shared/navigation/destination-model.test.ts src/shared/ui/AppShell.test.tsx
npm run build
npm run test:e2e -- tests/e2e/automation.spec.ts tests/e2e/automation-presentation.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts
```

单测覆盖入口／普通未找到、有效卡片、列表请求身份及记录语义；Node E2E 覆盖真实 Router、
历史返回及两种视口；Python lifecycle 验证修改后的测试在真实配置／SQLite上仍核对保存、
删除后历史和失败。对新增用例就在这些现有文件中扩展，无需新增测试框架。

若清理到 `api-client.ts`／automation 共享模型，追加以下直接消费者回归：

```sh
npm run test -- run src/shared/api/operations-api.test.ts src/entities/operations/automation.test.ts src/features/operations/NotificationRouter.test.tsx
```

改动文件运行 `npx eslint <实际修改且仍存在的TS/TSX文件>`、
`npx prettier --check <实际修改且仍存在的格式化支持文件>`；仓库根 `git diff --check`。
若改动其他既有测试文件，追加该文件的实际命令并报告；不把全 Web／Python／E2E交给
Developer。已证实的实现阻塞在同 Task 修正，不降低断言或加重试掩盖失败。

### B — independent acceptance and Slice-final coverage

独立检查完整 Task Base..candidate manifest／diff，包含删除、夹具及测试迁移；从真实列表
验证 TAC-1–5和旧已知深链，人工查看桌面／390px完整页面和卡片行为。保留实际失败和
原始日志。以下 cwd 为 `web/`，候选构建后执行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run test -- run
npm run build
npm run test:e2e -- tests/e2e/automation.spec.ts tests/e2e/automation-presentation.spec.ts tests/e2e/notifications.spec.ts tests/e2e/page-transition.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-workspace.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

全 Web 单测的依据是共用 Router／导航身份和 API 客户端清理，影响其他路由及存活客户端
消费者；不推导为全 Python／发布矩阵。自动化四文件真实旅程覆盖当前卡片、复制／Run
once、历史及未知响应核对；通知 E2E核对共享 Draft 校验，导航／两库／探索覆盖本 Slice
已交付表面。各 Python harness 及同端口测试顺序运行，使用独立 `--output` 保存材料。
根目录治理和 `git diff --check` 必须通过。

最后按 Slice AC-1–8核对完整 `9aa6054e0a2f624b9fb5c0e0fa8d70b232a6cfa8..candidate`。
RO-1/2检查同视口探索布局、详情滚动／返回和有界分页；RO-3检查九页切换、读取接入及
两库刷新；RO-4检查本 Task 管理／历史完整旅程。既有验收材料仅在执行输入匹配且覆盖该
结论时复用，并记录精确范围；Router／导航／API变动的受影响旅程需在最终候选实跑。
本 Task 未改设置读取实现；若复用 Task52.2设置接入材料，列出源码／测试／构建差异并
解释未受影响；存在实际影响则由 B补跑对应既有设置旅程，不给 Developer追加全套。

已记录的旧脚本定位失败不是本 Task 的自动免责或新增实现阻塞：B核对当前归属和完整
用户入口，报告证据限制；只将真实在范围内的未满足结果列为 FIX REQUIRED。证据按工作流
存于 `.git/validation-evidence/<candidate>/<run>/`，不新造过程工具。T3不要求无影响的
wheel／Docker门禁；如范围触及 T4则先重评并执行工作流适用全量门禁。

## Non-goals

不重设计自动化业务或其他页面，不全面退役后端 API／CLI／通用 Draft，不改配置、权限、
schema、引擎、恢复或媒体操作，不清理历史，不重开旧 Slice，不修无关既有测试，不推送／
部署。Slice最终 CURRENT协调及 PASS / CLOSED由 A负责。

## Developer Completion Report

待实施授权及完整 checkpoint 后填写：准确 SHA／READY FOR B REVIEW、变化／关键决策、
受影响测试实际命令／结果／耗时、已知失败和剩余风险。完整验收由 B负责。

## B Review Result

尚无 Task52.3 实现候选；当前仅规划，未作产品 PASS／FIX REQUIRED 判断。
实施后独立审查完整 Task Base..Head；PASS后重评全部 Slice结果。全部满足则停止规划、
完成 Slice-final验证并交 `SLICE READY FOR A REVIEW`，不由 B关闭 Slice；有真实阻塞留在
同 Task修正，并以用户的完整操作旅程说明失败阶段、原因和可执行修正。
