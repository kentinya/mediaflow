# Task BUG-AUTO-CREATE-UX — 自动化新建弹出卡片与完整交互修正

Authority：用户已明确要求改善新建表单的人类可读性、视觉与操作体验，并指定点击新建后使用
弹出卡片、自然连贯的动画；2026-11-04 已明确授权激活本 Task。Developer 可按本计划实施，
当前激活检查点只转换 Task 状态与授权，不包含产品实现，不授权其他角色自动启动、推送或部署。
生命周期及角色职责遵循
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)，参考
[B experience](docs/agent-experience/task-planner-reviewer.md) 与
[Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: BUG-AUTO-CREATE-UX
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 2aa791a6b66d968f473a6875fe2ebf072c5500df
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: GRANTED BY USER — TASK SCOPE ONLY
Working Branch: main
```

上一独立修复 **BUG-AUTO-FORM** 已于 2026-11-04 由 B 复核 PASS，无阻塞项；Reviewed Head 为
`8758913aa6c543242a2dfe5df6df4cc71a61c334`。完整验收与验证限度见
[原验收检查点](https://github.com/kentinya/mediaflow/blob/f364a335c4ecff62e58ef889bf68847edb41b006/TASK.md)。
[Slice48](SLICE.md) 的 PASS / CLOSED、Base、实现 Head 和全部延期保持不变；本 Task 不重开
已接受 Slice，不改 Roadmap/Progress。下一大 Slice 仍由 A 另行选择。

规划前治理检查 PASS；工作树没有已跟踪改动，预存未跟踪日志、图片、输出与系统文件全部保留。
Base 是本次规划前的完整 HEAD；后续规划检查点不能替换 Base。
激活前 HEAD 为 `844a3f2e002a198d799c18d2dd6140e78d8625fd`；治理检查 PASS，无已跟踪改动，
预存未跟踪文件继续保留。Task 保持 PLANNED，待 Developer 实际开始时转 IN PROGRESS。

### Goal and actual gap

用户从「自动化 → 新建自动化任务」完成名称、来源目录、时间计划与处理上限设置，以一次
明确创建保存默认未启用的自动整理定义；全过程在列表上的弹出卡片内完成，能理解错误、
保留输入并安全纠正，创建成功后回到原列表上下文。

当前实际入口位于 `AutomationListPage.tsx`，打开 `AutomationLifecyclePage.tsx` 的无 ID 路由。
该创建分支混用英文技术说明、要求手填内部 ID，并用未套用表单样式的窄小原生控件纵向堆叠。
每日/每周快捷项固定八点，仍展示 Cron 和默认 UTC；调度预览不随候选变化失效。
新建分支还允许选择 enabled，但 `automation_workspace_commands.py` 明确拒绝启用状态创建。
这些是既有创建旅程的呈现与反馈缺陷；弹层沿用同一创建命令，不增加业务能力或发布权限。

适用约束：`UX-001/002/004/007–010`、`REQ-SCHED-001/004`、`V2-UX-004`、
`V2-AUTO-001/002/010/011`。完整现行旅程见
[Product Experience](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)，
发布边界见 [Architecture](docs/architecture.md#current--v2-automation-workspace-and-consumed-engine-settings-slice43-pass--closed)。
创建仍是 configuration-only；默认关闭、启用、Run once 和实际执行的区别保持现状。

### Implementation Scope

#### 1. 在现有列表上承载同一个创建弹层

- 主入口打开居中卡片，保留背景列表的筛选、分页与滚动位置；不先闪现独立长表单再弹出卡片。
  卡片使用单一中文标题「新建自动化任务」，关闭后焦点回到调用按钮。
- 无 ID 的 `/operations/automation/lifecycle` 直接访问、刷新、登录后续转也进入同一创建体验，
  没有历史列表上下文时使用自动化默认列表作为背景/返回位置。浏览器前进后退与可见弹层一致，
  不使用盲目的 `history.back()` 跳出本站。
- 既有 `/operations/automation/new` 创建入口收敛到同一体验，避免保留另一套手工 Draft 创建流程；
  不改有 ID 的编辑、详情、复制、删除和 Run once 旅程。仅移除因本次入口收敛而确证无消费者的代码。
- 复用现有路由、`automation-list-return.ts`、查询、按钮和弹层样式。可抽取最小创建组件，
  不重构整个生命周期页或把 Files 业务依赖引入 Automation。共用基础代码的改动必须覆盖原消费者。

#### 2. 将字段整理成人能直接填写的表单

- 按「基本信息与来源 / 运行时间 / 处理限制」分组；名称全宽，相关短字段在桌面并列，窄屏单列。
  常用字段直接可见，内部 ID、Active revision/digest 与发布机制放入按需诊断信息。
- 内部 ID 在一次创建会话内稳定生成，符合既有后端字符/长度/唯一性约束；重渲染、预览和提交失败
  不另换 ID，不用名称派生易冲突 ID；随机源不可用时给出明确状态，不使用弱随机或时间戳冒充唯一性。
- 来源从后端 ResourceLibrary 选项选择。默认「整个资源库」，可选择「指定子目录」；复用现有
  ResourceLibrary-scoped 只读 Files API 提供有界目录选择，分页、加载失败和权限不足都明确可见。
  仅选择后端允许遍历的目录，不跨库/越根、不递归拉取整树；保留明确的相对路径输入以纠正目录。
  切换资源库时清除旧库子目录，并可见地说明范围变化；目录读取失败不能默认为整个库。
- 默认每隔 1 小时、上限 100；间隔提供秒/分钟/小时单位并准确转换为现有 intervalSeconds，
  保留后端支持的正小数秒。每日提供时间、每周提供星期和时间；高级 Cron 可展开编辑。
  所有普通时间选择编译到既有 interval/Cron 字段，不重写调度规则或自行计算实际 due 时间。
- Cron 时区显式可见；新建可预填浏览器可识别的 IANA 本地时区，无法识别时明确使用 UTC。
  不将北京时间硬编码给所有用户，不静默修正用户已选时区。摘要和预览都注明所用时区。
- 上限按后端 authority 的 bounds 校验，并简短解释它限制单次来源范围，超限需缩小范围，
  不承诺自动分批或只执行前 N 个。没有 mode 选择器；新建始终提交 enabled=false，
  提示「创建后未启用，可在列表中启用或运行一次」，不提供已知会被拒绝的启用选项。
- 可见文案、加载、校验、错误及恢复动作均使用简洁中文。必填、格式、数值上下限就近解释，
  定位第一个问题字段；不能只有灰色按钮而无原因。后端仍是最终校验与权限权威。

#### 3. 完成预览、创建、成功与恢复反馈

- 使用既有零变更 schedule-preview。候选满足当前接口前置条件后，合并连续输入、自动更新
  即将运行时间；前置条件未满足时说明缺什么，不以客户端计算替代后端结果。预览失败不新增
  强制保存门禁，实际创建仍由现有 checked Save 校验。
- 任何影响预览的候选变化立即使旧结果失效；响应绑定确切候选与创建会话，旧响应、关闭后的响应
  和前一个 ResourceLibrary 的响应不得覆盖新状态。时间按所选时区显示为可读日期、星期和时分。
  提示时间计划仅在启用后生效，不把默认关闭的定义描述成已安排运行。
- 固定底栏提供「取消 / 创建任务」。提交保留表单尺寸和输入，按钮显示「创建中…」，禁止重复提交；
  动画、Enter、快速双击、重开与路由切换都不能多发创建命令。
- 继续调用 `createAutomationDefinitionFocused` 的既有 checked publication，保留候选绑定的
  observed Active fence、当前 principal、版本冲突与 `reconcileAutomationPublicationFocused`。
  刷新 authority 不静默给旧输入换 fence；冲突保留输入，提供明确的重新核对步骤。
- 明确成功或精确核对成功后，更新列表与统计、平顺关闭并提示「创建成功，尚未启用」。
  保留原列表条件；新条目在当前页可见时短暂标明，不可见时提示当前筛选/分页下未展示，
  不伪造一行、不清空筛选、不跳到编辑页，也不自动启用或运行。
- 可纠正的拒绝留在卡片内，说明失败阶段、是否保存和下一步。网络丢失/5xx/畸形响应按既有规则
  视为结果待核对，保留该 principal/ID/candidate/base 的命令身份，通过「核对本次创建」读取真实
  发布结果；不能重新生成 ID 或重发来掩盖不确定结果。登录失效沿用现有 auth 流程。
- 未改动时直接关闭；确有未保存输入时，关闭按钮、遮罩、Esc 和站内返回统一提供卡片内
  「继续填写 / 放弃修改」选择；自动 ID、默认时区和预览加载不算用户修改。
  提交中防止误关；请求结束后不能永久困住用户。
  不确定结果允许保留原命令身份后关闭，重开先恢复核对状态；沿用现有会话持久化和 principal 隔离，
  不新增本地持久化草稿产品或存储 token。

#### 4. 为卡片设计一致的布局与自然动效

- 桌面目标宽度 720–800px，白色卡片、柔和遮罩、适度圆角和阴影；控件统一约 40px 高度、
  合理文字行宽与间距，视觉与现有 V2 light shell 一致。标题/底栏可见，仅内容区滚动。
  窄屏留安全边距并适配动态视口、软键盘与长目录；没有页面横向溢出、遮挡或双重滚动。
- 入场约 180–240ms：遮罩淡入，卡片由轻微下移/约 0.98 缩放平顺到位；退出约 140–180ms，
  完成后再卸载和恢复焦点/背景滚动。使用柔和减速，不明显弹跳，不因数据读取延迟重播进场。
- 展开高级项、错误和预览更新保留稳定布局及操作位置，避免硬切、闪白、内容跳动。
  动画优先使用 transform/opacity；禁止人为延迟请求或保存结果来凑动画时长。
- 覆盖打开、关闭中、重新打开的竞争，不残留遮罩/滚动锁，不让退出中的旧回调关掉新会话。
  实现 dialog 语义、焦点约束、背景不可交互、Esc、可见焦点与读屏错误提示；
  `prefers-reduced-motion` 下取消位移/缩放与不必要等待。增强限此旅程，不做全站动画系统。

### Acceptance Criteria

- [ ] AC-1：列表点击、创建深链、刷新和登录后续转进入同一中文弹出卡片；打开/取消不发布配置，
  不创建 Draft、运行、执行授权或 Storage 写入；旧创建入口不再展示另一套多步骤流程。
- [ ] AC-2：原列表筛选、分页和滚动得到保留，直接访问有确定的返回位置；前进后退和关闭一致，
  编辑/详情/复制/删除/Run once 的现有独立行为没有回归。
- [ ] AC-3：名称、资源库、范围、计划与上限可直接理解；常规创建不要求内部 ID、Cron 或发布机制知识；
  内部 ID 稳定且合法，始终以 enabled=false 创建，创建后未启用的状态清楚。
- [ ] AC-4：目录选择有界且 confined，支持根目录和子目录；换库不会误用旧路径；读取失败、无权限、
  空目录与禁用库分别可见，不将未知范围变成根目录或制造 Storage mutation。
- [ ] AC-5：间隔单位、每日时间、每周星期/时间、Cron 和 IANA 时区正确映射现有字段；
  秒/分钟/小时换算不丢精度，小数秒可用；无效值/上下限/非法路径/无库等均有就近可操作反馈。
- [ ] AC-6：预览使用后端规则、可读时间与显式时区；修改候选立即失效，晚到旧响应不得覆盖新预览；
  非 UTC、非法 Cron/时区、切换计划、预览失败均不误导，也不新增强制预分析或执行权限。
- [ ] AC-7：一次明确创建只发布 intended disabled definition，API 和持久化读回一致；
  无兄弟 Draft 搭车、无运行/媒体写入/隐式启用。成功关闭、提示并刷新权威列表/统计。
- [ ] AC-8：409 并发冲突保留输入与旧 fence；结果未知时仅精确核对，不重发、不换 ID；
  关闭/重开/刷新/换 principal 后仍遵循现有命令隔离与 non-replay。拒绝不虚报保存成功。
- [ ] AC-9：快速双击、Enter、关闭/重开竞争、提交时导航和迟到响应不重复提交、不串会话，
  也不遗留遮罩、焦点约束或滚动锁。未保存退出的选择可理解且不会无故打断无修改关闭。
- [ ] AC-10：桌面 1440×900、窄屏 390×844/320px 和放大字体下，字段可读、底栏可达、无横向溢出；
  打开/退出、动态内容、网络慢与报错时的动画自然连续。检查实际截图与交互录屏，不只断言 CSS 数值。
- [ ] AC-11：键盘完整操作、焦点留在卡片、关闭后焦点返回、背景不可误点/滚动；
  减少动态效果时仍能完整创建与关闭，无动画事件缺失导致的卡死。
- [ ] AC-12：新建 UI 及直接消费者的单元、集成、真实 Python/SQLite 浏览器验证通过，
  B 独立检查实际候选与视觉证据；已有 BUG-AUTO-FORM 的合法规则保存后打开/创建场景继续通过。

### Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。本 Task 是 T3：只调整 Web 创建呈现、
路由、表单映射和既有 API 消费，后端 authority、checked publication、调度/执行、schema 与 Storage
接口均不改变。若实现需要改变上述安全边界，先交 B 重评范围及 T4，不把后端改动藏进 UI Task。

#### Developer — affected tests

实施后新增 `AutomationCreateDialog.test.tsx` 与 `automation-create-form.test.ts`，覆盖本 Task 的
表单映射/校验、稳定 ID、关闭/重开、候选预览时序、焦点和精确创建/核对；修改既有入口测试。
生产组件可按需合理命名，测试命令需随实际测试文件名同步。

在 `web/` 执行：

```sh
npm run test -- run src/features/operations/AutomationCreateDialog.test.tsx src/features/operations/automation-create-form.test.ts src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/entities/operations/automation-lifecycle.test.ts
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-create-dialog.python.spec.ts
```

新增的真实 Python spec 使用现有隔离 harness 覆盖正常创建持久化、打开/取消零写入、目录 confinement、
冲突/丢响应核对、列表返回和桌面/窄屏/减少动态效果。竞态用可控响应，不加无条件 sleep。
自动生成 ID 后，更新原创建 helper 从确切提交/持久化结果取得 ID，保留一条定义/零额外运行等断言。
将新增 Python spec 加入默认 fake-server Playwright 配置的 testIgnore，保持两套环境分离；
因创建入口收敛而需要补充的 fake API 必须镜像真实契约，不能以放宽 decoder/权限断言让用例通过。
如改到共享 modal/navigation/Files API decoder，补跑被修改共享代码的直接消费者测试并在交接说明。

在仓库根执行：

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_automation_definition_publication.py'
.venv/bin/python -m unittest discover -s tests -p 'test_automation_execution_intent.py'
python3 scripts/check_governance.py
git diff --check
```

这两组 Python 回归验证 unchanged checked create/disabled-first/权限和精确核对契约。
Developer 完成受影响验证后提交 coherent checkpoint，不执行 B 的完整验收。

#### B — independent acceptance

- 检查整个 Task Base..candidate，只按此独立修正范围验收；独立复现 AC-1–12，不能只接受 Developer 的 PASS。
- 在候选上复核上述受影响用例和 Web 静态检查/生产构建；与相同输入的结果复用按 workflow，
  新代码/测试/harness 改动后的受影响结果必须更新。根目录补跑：

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_v2_automation_operations.py'
```

- 在 `web/` 使用同一个隔离实例串行执行实际创建及既有生命周期、工作区、Run once 浏览器回归：

```sh
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-workspace.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
npm run test:e2e -- tests/e2e/automation.spec.ts tests/e2e/automation-presentation.spec.ts
```

- 截图核对普通/高级/字段错误/慢请求/结果待核对/窄屏/放大字体；录屏或实际观察打开→填写→预览变化
  →提交→关闭→回到列表及快速重开。检查减少动态效果与键盘操作。数据与媒体只用临时库及 fake/local
  fixtures；不读取用户运行数据库、私有配置或生产 Storage。证据按 workflow 保存在稳定忽略路径。
- 本范围不要求全 Python/Web 单元仓库回归、安装包/容器或真实外部服务；没有安全协议或构建边界变更。
  若实际改动扩展至共享执行/权限/持久化或打包边界，B 先重评 Test Level 与对应门禁，不降低要求。

### Non-goals

不把编辑/复制/删除等改成弹层，不重做整个自动化工作区、执行记录、任务中心或其他页弹层；
不增加运行模式、执行入口、保存即启用、创建即运行、独立授权、执行前强制预览、后台草稿同步、
跨 Task 恢复、调度引擎/队列/Storage 操作或数据库变更。不修改 SLICE/Roadmap/Progress、
已接受范围、旧定义 ID、权限/发布/运行语义，不为本 Task 规划后继 Task。

### Developer Completion Report

**Status: READY FOR B REVIEW**
**Implementation Head: `128ab24bbbf390a1fe05ee92666194bfc6670548`**
**Task Base: `2aa791a6b66d968f473a6875fe2ebf072c5500df`（未改变）**

Developer 已按本 Task 的授权范围完成实现与受影响验证；未推送、未部署，未修改
SLICE/Roadmap/Progress，未重开任何已接受 Slice。工作树仅保留实施前已存在的未跟踪日志、
图片、输出与系统文件。

#### 实际改动

- 新建旅程收敛到列表上的同一中文弹层：`/operations/automation/lifecycle` 与旧
  `/operations/automation/new` 都渲染列表背景和同一个创建卡片；删除不再有消费者的
  `AutomationNewPage.tsx`，并移除 `AutomationLifecyclePage.tsx` 中无 ID 的创建分支。
  列表筛选、分页和打开前滚动位置通过路由搜索与有界模块内存保留；创建成功后不跳编辑页。
- 表单按「基本信息与来源 / 运行时间 / 处理限制」组织；名称全宽、桌面并列、窄屏单列。
  内部 ID 使用 Web Crypto 生成并只在诊断信息展示；随机源不可用时明确阻止创建，不回退到
  弱随机或时间戳。无启用选择器，提交始终为 `enabled=false`。
- 来源使用后端 ResourceLibrary 选项；默认整个资源库，可切换指定子目录并复用现有
  ResourceLibrary-scoped 只读 Files API 做单层、可遍历、可分页目录选择。切换资源库会清空
  原子目录并显示范围变化；目录读取失败保留未知范围并给出中文恢复动作。
- 间隔支持秒/分钟/小时与小数精确换算；每日/每周编译为现有 Cron；高级 Cron 与 IANA 时区
  显式可见，时区预填本机 IANA 或明确回退 UTC。上限按后端 authority bounds 校验并解释
  “缩小范围”而不是自动分批/只执行前 N 个。
- 预览在候选满足条件后自动防抖调用既有零变更 schedule-preview；候选变化立即失效旧结果，
  代际/候选键校验丢弃旧响应、关闭后响应和前一资源库响应。失败不新增保存门禁。
- 创建继续使用 `createAutomationDefinitionFocused` 与观察到的 Active fence；409 保留输入并
  提供显式重新核对；网络丢失/5xx/畸形响应保留 principal-scoped 命令身份，只通过
  `reconcileAutomationPublicationFocused` 核对，不重发、不换 ID。会话上下文抽取到
  `automation-publication-session.ts`，与既有编辑/启停上下文隔离。
- 成功或精确核对成功后刷新列表/统计、短暂标出当前页可见的新行、提示“创建成功，尚未启用”，
  不自动启用或运行；未保存关闭统一提供「继续填写 / 放弃修改」；路由离开由 blocker 统一
  拦截；提交中防重复与防误关。弹层具备 dialog 语义、焦点约束/返回、背景 inert、滚动锁、
  约 220ms 入场/160ms 退出动画和 `prefers-reduced-motion` 降级。

#### 实际验证结果（Developer 受影响范围）

- `web/`: `npm run test -- run AutomationCreateDialog.test.tsx automation-create-form.test.ts
  AutomationLifecyclePage.test.tsx AutomationRouter.test.tsx
  AutomationWorkspaceReadModel.test.tsx automation-lifecycle.test.ts` → **82 passed**。
- `web/`: `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` → 全部通过。
- 根目录：`test_automation_definition_publication.py` → **48 passed**；
  `test_automation_execution_intent.py` → **14 passed**；`test_v2_automation_operations.py` →
  **19 passed**。
- 真实 Python/SQLite 浏览器（`playwright.python.automation.config.ts`）：
  `automation-create-dialog`、`automation-lifecycle`、`automation-workspace`、
  `automation-run-once` 串行 → **32 passed**。新 spec 覆盖真实创建持久化、打开/取消零写入、
  目录 confinement 与读取失败、丢响应后 reload 核对不重发、窄屏/减少动态效果/键盘焦点。
- fake Python 之外入口：`automation.spec.ts` + `automation-presentation.spec.ts` → **15 passed**；
  `task-flow.python.spec.ts` → **3 passed**；`action-readability.python.spec.ts` → **7 passed**。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` → 通过。

#### 剩余风险与验证限度

- Developer 未执行完整仓库回归、打包/容器或真实外部服务；这些仍由 B 按 T3 验收决定。
- 未由 Developer 人工逐张审阅桌面/窄屏截图或录屏；新 Python spec 已检查真实窄屏宽度、
  底栏可达、无横向溢出、减少动态效果和键盘焦点，视觉证据仍请 B 独立核对。
- 列表滚动位置恢复与“创建成功后不展示时提示”已有实现，但自动化主要断言 URL/行/提示；
  B 可在真实浏览器补充滚动与分页边界检查。
- fake-server 只用于旧入口收敛与既有 fake 旅程；真实创建/核对持久化由 Python harness 证明。
  目录权限/提供方失败由既有 Files 契约覆盖，本 Task 的 Python spec 用可控 503 证明失败不会
  把未知范围改成根目录。

### B Review Result — FIX REQUIRED（2026-11-04）

B 独立审查完整范围
`2aa791a6b66d968f473a6875fe2ebf072c5500df..ceb30c1492fa4ea4a3894e2a88db2898a07c0b13`；
产品实现 Head 为 `128ab24bbbf390a1fe05ee92666194bfc6670548`，其后仅 TASK.md 交接说明。
本次是独立小修正，不属于 Slice48；Slice48 的 RO-1–4、关闭结论、Base/accepted Head 和延期
保持原接受结果。本范围没有修改其流程状态/指标/执行协议，亦没有修改 SLICE/Roadmap/Progress。
不规划新 Task；修正在 **BUG-AUTO-CREATE-UX** 内继续，原 Base/Goal/Scope/AC/T3 保留。

已确认的交付：新旧创建地址收敛为中文卡片，表单生成稳定 ID、编译既有时间计划字段；
创建与核对继续调用既有接口。B 从真实列表打开卡片、明确创建、读回隔离 SQLite，确认新增
一条 disabled definition、没有 occurrence；没有发现本轮探测中的重复创建或媒体执行。
但退出选择、提交中状态和无效时间计划的可操作恢复尚未完成，以下三项均阻塞 Task 验收。

#### 阻塞项与开发指导（同一 Task）

1. **P1：未保存退出和创建拒绝的提示不可见。** 对应 AC-8/9/10/11。
   用户从列表打开卡片，只填写名称，在内容顶部点右上角 × 或按 Esc，卡片保持打开，但
   「继续填写 / 放弃修改」位于滚动区末尾，未滚入视野、焦点也未进入选择区。
   1440×900、390×844、320×844 均复现，提示与内容可视区的交集为 0。
   后端拒绝创建的 alert 也位于同一不可见位置。定位：`AutomationCreateDialog.tsx`
   的 `commandError` / `discardPromptOpen` 渲染都在 `.mf-automation-create-scroll` 末尾。
   - 在卡片内为关闭选择提供始终可见、可聚焦的呈现；所有关闭入口和站内/浏览器返回复用
     同一选择。出现时将焦点交给安全的「继续填写」，取消退出后恢复原字段/焦点。
   - 明确提交后的失败也应主动呈现可见反馈和可达的下一步；可聚焦错误摘要或相应字段。
     不依赖用户自行滚到底部寻找提示，不把普通预览更新变成强制焦点跳转。
   - 修改限新建旅程，不建设全站弹层/动画系统。补充真实浏览器断言：从顶部触发关闭后，
     选择按钮实际在可视区且键盘可操作；选择继续保留输入，放弃恢复列表上下文和焦点。
     覆盖 ×、Esc、遮罩、取消与浏览器返回，并检查窄屏截图，不能只断言 DOM 的 visible。

2. **P1：正在创建被显示成上次结果待核对，并可提前核对、返回关闭。** 对应 AC-8/9，
   以及 Scope §3 的「创建中…」「提交中防止误关」。用户完成表单并点击创建，网络尚未返回时，
   页面立即显示「上次创建结果待核对」和可点击的「核对本次创建」，没有「创建中…」按钮。
   在真实创建请求被暂缓时点击核对，会先得到「本次创建仍未证实」；释放原请求后创建成功。
   此时按浏览器返回也直接卸载卡片。重开可以保留命令身份，故不将其描述为重复执行或数据丢失。
   定位：`submit` 提前设置 pending；底栏优先渲染 pending 分支；`useBlocker` 在提交中返回 false。
   - 可以在发送前保留原命令身份以支持刷新恢复，但 UI 必须区分当前请求仍在进行与请求结束后
     的结果未知。进行中固定显示「创建中…」，创建/核对互斥，禁止提前核对和重复命令。
   - 修正本卡片的路由阻止条件：提交中的站内/浏览器返回应有可见的等待反馈，防止误关；
     正常响应后解除约束。真实刷新/断线/登录恢复仍沿用既有 pending 身份与 non-replay，
     不把 auth 恢复困在卡片，不自动重发或更换 ID/fence。
   - 用可控的真实 POST 响应覆盖提交中按钮/Enter/双击/返回，证明放行成功、明确拒绝、
     丢响应三种结果各自到达正确状态。不要用无条件 sleep 或新增后台轮询产品。

3. **P1：无效 Cron 没有可定位的中文纠正信息。** 对应 AC-5/6/8。
   用户填写名称/资源库，选高级 Cron，填 `61 8 * * *` 后创建，后端返回 400
   `automation_definition_invalid_field`，Active 保持不变。即使滚到错误位置，也只看到
   「在组合候选阶段被拒绝，请修正后重试」和内部错误码；Cron 字段无错误标记，未说明
   应检查时间计划，预览也只显示失败码。定位：`commandErrorMessage` 的 rejected 分支、
   预览 error 分支和 `automation-create-form.ts` 的 Cron 校验/字段关联。
   - 利用既有返回的有界字段/错误类型及当前计划上下文，在时间计划区域给出中文纠正指引，
     提交失败时定位相应字段/区域；不能确定单个字段时清楚说明检查 Cron 与时区，勿假称
     已确定某字段。保留输入、ID 与原 authority，不渲染原始异常。
   - 不改后端调度/发布协议，不另写一套 due 计算，不把预览成功变成新增创建门禁。
     补充从上述无效 Cron → 可见解释 → 改为有效 Cron → 明确创建成功的真实浏览器回归；
     断言纠正前 Active 未变、纠正后只有 intended disabled definition、零额外运行。

Developer 按以上三个行为一起修正，再执行原 Required Tests 中的新改/直接受影响用例及检查，
提交一个 coherent checkpoint。除新增上述真实场景外，不扩展业务功能或重构其他弹层。
B 在修正候选上完成原 T3 验收；已发现阻塞不能用现有绿色用例数量替代。

#### B 实际验证与限度

- 治理 preflight PASS；完整范围 manifest/生产 diff/测试与 harness 变更已审查。
  初始分支 main，HEAD `ceb30c1492fa4ea4a3894e2a88db2898a07c0b13`，已跟踪文件干净，
  工作区/Git 可写；预存未跟踪文件原样保留。
- `web/ npm run build` PASS；`npm run test -- run` 加原计划的六个受影响文件 → **82 passed**，
  6 个文件、8.97 秒。JSDOM 的 scrollTo 未实现提示不等于已验证真实滚动；生产构建保留
  bundle 大小提示，本轮不扩展为打包优化。
- 使用该生产构建及既有 `scripts/operations_inventory_harness.py --port 4185`，
  全程从真实 Web 列表/创建入口操作临时 Python/API/SQLite 实例。独立脚本验证三种视口的
  退出选择、真实创建持久化、可控慢响应/提前核对、非法 Cron、提交中返回与重开核对。
  暂缓的是既有真实请求；没有构造产品入口、伪造最终状态、读取用户数据库或调用生产 Storage。
- 已检查桌面初始动效帧、提交/非法 Cron 与 320/390px 退出截图；其余 PNG 和视频
  本轮未逐一验收，不宣称完整视觉验收通过。
  原生探测首次在最后读回时因脚本没有配置 baseURL 而报 `Invalid URL`，这是探测脚本问题；
  补齐配置后同入口重跑完成，没有修改产品代码，也未把初次脚本失败计为通过。
- 依 workflow §6 的已证实阻塞提前 FIX REQUIRED：其余 Python、静态检查和完整 T3 浏览器矩阵
  本轮未执行，Developer 交接中的通过数不冒充 B 本轮结果。剩余 AC 保持待最终验收。
  产品验证命令累计不足 1 分钟，低于本轮复核耗时的一半。

稳定本地证据（忽略目录，不宣称远程可访问）：
`.git/validation-evidence/ceb30c1492fa4ea4a3894e2a88db2898a07c0b13/b-auto-create-review/`：
`build.log`、`affected-web.log`、`native-review.mjs/.json/.log`、
`recovery-review.mjs/.json/.log`、PNG 与 `video/`。此轮只更新 B 的 Task 决定与修正指导，
没有实现产品修复、推送、部署、改写历史或关闭 Slice。

### Developer Fix Report — BUG-AUTO-CREATE-UX（2026-11-04）

**Status: READY FOR B REVIEW**
**Implementation Head: `b00e1253a464eb2bc358b1e2b445e04a86e0c878`**
**Task Base: `2aa791a6b66d968f473a6875fe2ebf072c5500df`（未改变）**

本轮只在同一 Task 内修正 B 列出的三个阻塞项；未推送、未部署，未修改 SLICE/Roadmap/Progress，
未新增业务能力、后端协议、调度/发布/执行语义或本地持久化草稿。

#### 实际改动（产品实现 Head 只含六个文件）

- **P1 退出选择与失败反馈不可见 → 固定“关注区”。** `AutomationCreateDialog.tsx` 在标题下方、
  滚动字段上方新增常驻关注区（`.mf-automation-create-attention`，见 `styles.css`）：退出选择、
  创建命令结果、校验摘要与提示始终可见，区域自身在极窄视口内可滚动，不新增全站弹层系统。
  关闭手势（右上×、Esc、遮罩、取消）、站内拦截与浏览器返回统一进入同一选择；出现时焦点进入
  「继续填写」，取消后恢复到最近编辑的字段（`focusin` 记录），再次按 Esc 等同「继续填写」。
  创建拒绝/冲突/待核对/本地错误与重新核对提示也移入该区，并在出现时聚焦可读的错误摘要；
  时间计划被拒绝时额外显示“检查时间计划”按钮并把焦点移到对应计划字段。
- **P1 提交中误显示为“上次结果待核对” → 区分进行中与已结束未知。** 提交前仍保留命令身份以支持
  刷新恢复，但界面按 `submitting` 分支渲染：固定显示「正在创建…」与底栏禁用的「创建中…」，
  不再出现「核对本次创建」或「上次创建结果待核对」；`reconcile()` 在提交中直接拒绝。
  `useBlocker` 改为在提交中也拦截导航，底栏主体在提交中显示「取消」（禁用，不再误示为可关闭），
  站内/浏览器返回显示“已暂时阻止离开本页”，响应到达后才解除约束并显示真实结果。
  拒绝/未知/成功三条路径各自的焦点与下一步保持原契约：未知仍只允许精确核对，不重发、不换 ID。
- **P1 无效 Cron 无可定位纠正 → 本地按后端语法校验并定位字段。**
  `automation-create-form.ts` 新增 `cronExpressionIssue()`，按 `mediaflow/domain/cron.py` 的五段
  语法与各段上下界检查（仅格式/范围，不计算触发时间），错误信息精确到“第 N 段（字段）”。
  Cron 输入补上 `aria-invalid`/`aria-describedby`，校验失败时聚焦该字段。后端仍为最终权威：
  `automation_definition_invalid_field` 拒绝时在“运行时间”区域给出中文纠正指引（先检查 Cron 与
  IANA 时区，再由名称/范围/上限），错误码只作诊断行，不再作为标题；输入、内部 ID 与 authority 保留。

#### 实际验证结果（Developer 受影响范围）

- `web/`：`npm run test -- run AutomationCreateDialog.test.tsx automation-create-form.test.ts
  AutomationLifecyclePage.test.tsx AutomationRouter.test.tsx AutomationWorkspaceReadModel.test.ts
  automation-lifecycle.test.ts` → **86 passed**（新增 4 个用例：固定关注区与焦点恢复、提交中单次
  状态与禁止提前核对/重复提交、被拒绝时间计划的定位与输入保留、Cron 语法与边界映射）。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` → 全部通过。
- 真实 Python/SQLite 浏览器（`playwright.python.automation.config.ts`，生产构建）：
  `automation-create-dialog.python.spec.ts` → **8 passed**，新增三个真实场景：
  各关闭入口（×/Esc/遮罩/取消/浏览器返回）选择区在卡片可视区内、键盘可操作、继续保留输入并
  恢复字段、放弃回到原列表与焦点；可控真实 POST 下提交中仅一条创建、无提前核对、返回被挡住并
  提示，放行后成功且只有一条 disabled definition、零 occurrence；`61 8 * * *` → 可见中文纠正、
  Active 与定义未变、不发送创建 → 改为 `0 8 * * *` → 后端拒绝路径可见且可定位（受控真实 400 信封）
  → 再次明确创建成功，只有 intended disabled definition、零额外运行。原窄屏/减少动态效果用例扩展
  到 390/320px 的退出选择与键盘操作。
- 同配置串行直接受影响回归：`automation-create-dialog` + `automation-lifecycle` + `automation-workspace`
  + `automation-run-once` → **35 passed**。
- fake-server 入口：`automation.spec.ts` + `automation-presentation.spec.ts` → **15 passed**。
- 根目录：`test_automation_definition_publication.py` → **48 passed**；
  `test_automation_execution_intent.py` → **14 passed**；`python3 scripts/check_governance.py` → PASS；
  `git diff --check` → 通过。

#### 视觉证据（本地忽略目录，不宣称远程可访问）

`.git/validation-evidence/b00e1253a464eb2bc358b1e2b445e04a86e0c878/dev-auto-create-review/`：
`desktop-close-choice.png`、`desktop-invalid-cron.png`、`desktop-in-flight.png`、
`desktop-in-flight-blocked-back.png`、`desktop-created.png`、`narrow-390-close-choice.png`、
`narrow-320-close-choice.png`、`narrow-320-invalid-cron.png`。均已由 Developer 目视核对：
1440×900 与 320/390px 下选择区/失败摘要在卡片可视区内，320px 无横向溢出。

#### 剩余风险与验证限度

- Developer 未执行完整仓库回归、打包/容器或真实外部服务；这些仍由 B 按 T3 验收决定。
- 浏览器证据来自隔离 harness 的临时 SQLite 与生产构建；未读取用户运行数据库或生产 Storage。
  “后端拒绝无效 Cron”的浏览器用例使用受控的真实 400 信封（浏览器会本地先拦截同一 `61 8 * * *`），
  后端拒绝路径的真实持久效果由 B 的 `test_v2_automation_operations.py` 与既有发布回归覆盖。
- 关注区在极窄/极矮视口内自身可滚动，未做全高度动画调优；未新增全站动画系统。
- 未由 Developer 录制视频；打开→填写→预览→提交→关闭→重开的手势连续性仍请 B 目视/录屏确认。
