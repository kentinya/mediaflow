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

### B Review Result — FIX REQUIRED（2026-11-04，本轮复核）

B 独立审查完整范围
`2aa791a6b66d968f473a6875fe2ebf072c5500df..e050f89f1adb9cc845b14b0f533b6008c19ca6d5`；
最新产品实现为 `b00e1253a464eb2bc358b1e2b445e04a86e0c878`，其后仅 TASK.md 交接说明。
上轮三个阻塞均已解决：退出选择在卡片内可见并可继续/放弃、提交中显示禁用的“创建中…”且
浏览器返回被拦截、无效 Cron 有中文纠正摘要并定位字段。独立真实浏览器覆盖
1440×900、390×844、320×844；慢响应放行后仍只有一条 disabled definition，无额外运行。

本轮仍有一个原验收项未完成，故不能 PASS。修正留在 **BUG-AUTO-CREATE-UX**，原 Base、目标、
范围与 T3 不变。Slice48 RO-1–4 的既有接受结论、Base/accepted Head 和延期未被本 Task 改动；
SLICE/Roadmap/Progress 保持原样，不重开 Slice，不规划后继 Task。

#### 唯一阻塞：P1 — 取消新建后原列表滚动位置丢失（AC-2）

真实用户旅程：在 390×844 的自动化默认列表向下滚动 100px，新建按钮此时仍在屏内
（按钮 y=140px），正常点击“新建自动化任务”，不填写内容，点击“取消”。
返回列表后 scrollY 从 **100 变成 0**；带 `q=Harness&sort=name` 搜索条件也复现，搜索条件本身保留。
这不需要隐藏入口、伪造页面高度或强制点击屏外按钮。普通点击/取消不应丢掉原浏览位置。

定位：`AutomationListPage.tsx` 的 `listSearchKey`（约165行）按原始 URL 字符串组成列表身份；
`openCreateDialog` 保存该身份，而 `listReturnState` 为创建路由补入 `tab=definitions`、
`sort=name`、`dir=next`。关闭时这些默认值被带回，`memory.key !== listKey`（约335行）使恢复被跳过。
对照用相同页面、同一操作，但初始 URL 已显式包含上述默认值，100px 能恢复为100px，证明是
同一列表的默认值表达不一致。原先仅核对 URL/筛选的绿色用例没有覆盖实际滚动结果。

#### Developer 修正指导（同一 Task）

1. 在打开/返回/恢复时使用一致的**有效列表上下文**：省略默认值和显式默认值应代表同一列表。
   复用现有列表状态与有界返回能力，修正身份计算或保存/恢复衔接；不得清空筛选/分页来凑匹配，
   不解释或改写服务器 cursor，不增加通用导航系统、本地持久化草稿或后端协议。
2. 列表真实行恢复后保留原滚动位置，同时保持焦点返回新建按钮。若焦点调用会再次滚动，协调
   恢复顺序或使用合适的 preventScroll；仍应防止把旧列表位置应用到另一组筛选/分页。
   新建深链没有原列表上下文时继续使用现有确定的默认返回位置。
3. 在现有 `automation-create-dialog.python.spec.ts` 增加实际滚动的浏览器回归：默认入口、
   省略默认值的搜索入口、显式默认值的对照入口；从按钮仍在屏内的100px位置真实点击。
   检查取消、填写后明确放弃以及成功关闭后的原列表条件/位置/焦点；取消与放弃仍须零发布。
   使用现有临时数据与真实页面，不通过改 DOM 高度、强制屏外点击或无条件 sleep 制造通过。
4. 运行原计划的新改/直接受影响测试与质量检查后交接 coherent checkpoint。原三个修正继续保留；
   不扩展到其他页面。B 在修正候选上完成原 T3 验收，已发现的本项不能以绿色测试数量替代。

#### B 实际验证、证据与限度

- 初始分支 main，HEAD `e050f89f1adb9cc845b14b0f533b6008c19ca6d5`；已跟踪文件干净，
  工作区/Git 可写，治理 preflight PASS，预存未跟踪文件保留。完整 Base..Head manifest、生产代码、
  新改测试、harness 与直接消费者已审查；后端 authority/执行/schema 没有变化，T3 仍适用。
- `web/` 原 Required Tests 指定的六文件 Vitest 命令 → **86 passed**（6文件，12.98s）；
  `npm run typecheck` / `lint` / `format:check` / `build` 全部 PASS（合计约24.93s）。
  JSDOM scrollTo 未实现提示与生产 bundle 大小提示保留；前者不能证明真实滚动已恢复。
- 根目录：`PYTHONPATH=tests:. .venv/bin/python -m unittest -v test_automation_definition_publication
  test_automation_execution_intent test_v2_automation_operations` → **81 passed**，39.24s。
- 生产构建 + 既有 `scripts/operations_inventory_harness.py --port 4185` 的临时 Python/API/SQLite：
  独立复现上轮三个原操作场景，检查真实反馈/焦点、三种视口和慢响应后的一次实际创建；
  同时发现本次滚动问题，并用默认/搜索/显式默认值三种真实地址对照复现。没有新增产品入口、
  伪造最终数据库状态或访问用户运行数据库/生产媒体。
- 已检查390px关闭选择、320px Cron纠正、桌面提交中返回提示、列表前后对照等实际截图；
  原生交互视频保留。首次探测对单条字段错误入视区的断言未通过，原日志保留在
  `initial-inline-visibility.*`；随后检查了固定摘要可见、字段焦点与实际截图，这些提供了
  可读的纠正路径，不将该额外断言作为产品阻塞，也不把首次失败计为通过。
- 依 workflow §6 在已证实 AC-2 缺口后提前 FIX REQUIRED：35例完整 Python 浏览器矩阵、
  fake-server 两文件回归、放大字体/完整动效验收本轮未执行；Developer 的结果不计为 B 本轮结果。
  产品验证命令累计不足2分钟，低于本轮复核耗时50%。没有全仓库/安装包/容器/外部服务验收声明。

稳定本地证据（忽略目录，不宣称远程可访问）：
`.git/validation-evidence/e050f89f1adb9cc845b14b0f533b6008c19ca6d5/b-review/`：
`affected-web.log`、`python-acceptance.log`、`quality-results.json` 与各检查日志、
`native-review.mjs/.json/.log`、`list-return-review.mjs/.json/.log`、`initial-inline-visibility.*`、
PNG 与 `video/`。本轮只更新 B 决定和开发指导，不实施产品修正、不推送或部署。

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

### Developer Fix Report — 列表滚动位置恢复（2026-11-04）

**Status: READY FOR B REVIEW**
**Implementation Head: `701600ec9dfb395668768f716094ead626984e8f`**
**Task Base: `2aa791a6b66d968f473a6875fe2ebf072c5500df`（未改变）**

本轮只修正 B 唯一阻塞的 AC-2 列表滚动位置丢失；实现 checkpoint 仅含
`AutomationListPage.tsx` 与新增浏览器回归，未推送、未部署，未修改 SLICE/Roadmap/Progress，
未重开 Slice，也未新增业务能力、后端协议、调度/发布/执行语义或本地持久化草稿。预存未跟踪
日志、图片、输出与系统文件保留。

#### 根因与修正

- **有效列表身份不一致。** 列表入口保存原始 URL 身份（默认入口为空），而创建路由从
  `listReturnState` 获得显式 `tab=definitions`、`sort=name`、`dir=next`；关闭时这些默认值被
  带回，`memory.key !== listKey` 使滚动恢复被跳过。现在 `listSearchKey` 将这三个默认值与省略
  形式视为同一有效列表上下文，仍保留筛选、分页 cursor/direction 等真实差异。
- **返回地址被创建路由改写。** `openCreateDialog` 在模块内保存用户点击时的原始有界列表
  search；关闭时仅在保存身份与当前创建背景的有效身份一致时使用该原始 search，否则回退到当前
  创建路由的列表上下文。默认入口关闭回 `/operations/automation`，带 `q`/`sort` 的入口不再被
  补写 `tab`/`dir`；深链仍使用既有确定默认返回位置。
- **焦点不再与滚动抢夺位置。** 关闭后列表行恢复的同时，新建按钮通过
  `focus({ preventScroll: true })` 取回焦点；滚动恢复仍在列表查询完成后的原位置执行。
  旧列表位置只应用于同一有效筛选/分页，不应用到另一组结果。

#### 实际验证结果（Developer 受影响范围）

- `web/` 六文件 Vitest（`AutomationCreateDialog`、`automation-create-form`、
  `AutomationLifecyclePage`、`AutomationRouter`、`AutomationWorkspaceReadModel`、
  `automation-lifecycle`）→ **86 passed**（6 文件，9.23s）。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` → 全部 PASS。
- 真实 Python/SQLite 浏览器（`playwright.python.automation.config.ts`，生产构建）：
  `automation-create-dialog.python.spec.ts` → **11 passed**（10.6s）。新增 3 个真实滚动场景：
  390×844 默认入口滚到 100px 后取消 → 原 URL、scrollY=100、按钮焦点、零发布；
  `?q=Harness&sort=name` 省略默认值入口填写后明确放弃 → 筛选条件、100px、焦点保留、零发布；
  显式 `?tab=definitions&sort=name&dir=next` 入口创建成功关闭 → 原条件、100px、焦点、
  当前页真实新行与“刚刚创建”标记。三个场景均从按钮仍在视口内的 100px 位置真实点击，
  不使用屏外强制点击、DOM 高度伪造或无条件 sleep。
- 根目录：`test_automation_definition_publication.py` → **48 passed**；
  `test_automation_execution_intent.py` → **14 passed**；`python3 scripts/check_governance.py` →
  PASS；`git diff --check` → 通过。
- 稳定本地日志（忽略目录，不宣称远程可访问）：
  `.git/validation-evidence/701600ec9dfb395668768f716094ead626984e8f/developer-scroll-fix/`
  包含 `vitest-affected.log`、`automation-create-dialog.python.log`、两份 Python unittest 日志、
  `typecheck.log`、`lint.log`、`format-check.log`、`build.log`、`governance.log`、`diff-check.log`。

#### 剩余风险与验证限度

- 未执行完整仓库回归、完整 Python 浏览器矩阵、fake-server 回归、打包/容器或真实外部服务；
  这些仍由 B 按 T3 验收决定。
- Developer 未人工录制滚动交互视频；新增 Python spec 已直接断言真实 `window.scrollY`、URL、
  焦点和列表行，视觉连续性仍请 B 在验收候选上目视核对。
- JSDOM 仍输出既有的 `window.scrollTo()` 未实现提示；单元测试不把该提示当作真实滚动证据，
  真实滚动由上述 Python/Chromium spec 覆盖。
- 本轮没有截图或录屏新增；B 可沿用既有证据目录并在修正候选上补充实际观察。
