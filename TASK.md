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
Status: PLANNED
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

已授权、尚未开始实现。Developer 按 workflow 记录实际 checkpoint、
READY FOR B REVIEW、改动与受影响测试结果、剩余风险；全量验收仍由 B 负责。

### B Review Result

已从规划草案激活为正式独立 Task，保留原 ID/Base/目标/范围与验收标准；未实施、未验收，
不存在产品 PASS。B 独立复核整个 Base..candidate 后记录 PASS 或 SAME TASK FIX REQUIRED。
独立修正 PASS 后恢复简短 NO ACTIVE IMPLEMENTATION TASK 与精确验收检查点，不关闭 Slice。
