# Task50.4 — V2 侧栏主页面切换体验

Task50.3 已由 B 独立验收 **PASS**。完整报告及证据见
ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749:TASK.md；已审范围保留为
073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d..a284c0135701d949afcae1cfe15fbba904eb16e0，
最终实现 checkpoint 为 a7a2b669da4611efd84778aabd4435145bcfd159。
用户已明确授权激活修订后的 Task50.4。本 Task 仍为唯一当前实施 Task，
B 已复核修正候选 4c511fc7d18d66d01c70c7a695f88c77376135f6 及交付 Head
733250e836615317340c563f603efea41492987f，结论 **FIX REQUIRED**。B50.4-01 已解决；
B50.4-02 的认证续转及跨页 URL 回归已在同一 Task 修正，当前实现候选为
ad40d23538cb3bf30d416ae7cefb6920d2375f5b，交回 B 复核。原 Base、范围、验收及测试分工保持。

Authority：已提交 [Slice50](SLICE.md) 的 RO-4、AC-8/10/11 与 V2-UX-012 的主页面
切换部分；生命周期遵循 [Development Workflow](docs/development-workflow.md)。
本次复核不改变 Slice 范围、Base、Task 验收或既有 Task 接受事实。

```text
Task ID: 50.4
Task Type: SLICE
Parent Slice: 50
Status: READY FOR B REVIEW
Task Base: ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749
Candidate: ad40d23538cb3bf30d416ae7cefb6920d2375f5b
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Working Branch: main
Development Authorization: TASK50.4 ONLY — EXPLICIT USER ACTIVATION
Next Action: B REVIEW — B50.4-02 AUTH CONTINUATION AND CROSS-PAGE URL
```

### Goal 与真实代码缺口

用户从首页进入文件，再到媒体库、存储、整理规则、自动化、任务中心、通知或系统设置，
主内容自然切换，导航和页头稳定，抵达后可直接操作。浏览器前后退、既有跨主页面链接
和认证后的精确续转，都按当前内容属于哪个侧栏入口判断是否切页；同页打开目录、标签
或详情卡片保留局部体验。例如自动化列表与编辑卡片都属于“自动化”，两者之间不播放
整页过渡；从“文件”进入“自动化”则播放。这只是动效分组，不改变页面、权限或路由。
慢读、无权限或读取失败仍显示目标页真实状态与原有恢复操作，动效不遮住错误。

本 Task 依据原 Base 源码；截至本次激活，仅有规划文档变化，未构造新入口或假设缺陷：

- web/src/shared/ui/AppShell.tsx 直接渲染 children，尚无主页面切换呈现；
  web/src/routes/router.tsx 的 RootRoute 在共享 Shell 下放置 AuthBoundary 与 Outlet。
- web/src/shared/navigation/destination-model.ts 的 shellDestinations 定义九个真实
  侧栏入口。destinationForPath 用于精确目的地/标题/认证，会区分主页面和多个详情目的地，
  不能把每个返回 ID 的变化当作切页。侧栏 isActive 也不覆盖所有详情归属，例如规则编辑；
  需要明确呈现用的主页面归属，保留现有认证允许范围。
- web/src/shared/ui/styles.css 已有库加载和卡片动画，尚无统一主页面过渡。
  shared/ui/modal-card.tsx 和 features/operations/automation-card-shell.tsx 已负责
  卡片退出、焦点、背景锁定与退出保护，保留其行为。

完整旅程与技术边界：[Product Experience 的 Slice50 目标旅程](docs/product-experience.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)、
[Architecture 的 Slice50 TARGET](docs/architecture.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)
及 CURRENT V2 Shell/认证合同；沿用 UX-001/002/007、REQ-WEB-005/006、
REQ-SAFE-005/007 与 V2-UX-001–004。

### Implementation Scope 与开发指导

1. 判断当前内容属于哪个侧栏入口，用来区分“换了主页面”和“仍在同页内操作”。
   从现有路由与目的地模型复用这层关系，下表是范围映射，不新增路由或业务入口。
   自动化、通知不能被宽泛的 operations 前缀吞并；规则编辑属于整理规则。
   将呈现身份与认证允许范围保持各自职责，复用现有模型，采用最小必要改动。

   | 真实侧栏入口 | Router 内路径（浏览器前缀 /ui-v2）及已有同页内容 |
   |---|---|
   | 首页 | /dashboard |
   | 文件 | /resourcelib/files，已有库/目录/配置卡片 |
   | 媒体库 | /medialib/files，已有库/目录/配置卡片 |
   | 存储管理 | /storage，已有筛选/查看/添加/编辑卡片 |
   | 整理规则 | /rules 与已支持的 /rules/edit/$family/$objectId |
   | 自动化 | /operations/automation 及现有定义/编辑/记录/运行详情子路由 |
   | 任务中心 | /operations 与既有任务/整理详情旅程，排除自动化和通知 |
   | 通知 | /operations/notifications 及既有 Webhook/投递详情子路由 |
   | 系统设置 | /configuration，已有页内设置/返回上下文 |

2. 在共享 Shell/主内容边界实现协调过渡，只在当前内容所属的侧栏主页面改变时触发，
   不随 query、轮询、同页子路由或菜单开关触发。侧栏、页头、语义 main 与既有布局
   保持稳定，时长/缓动协调现有卡片，并尊重 reduced-motion。采用最小必要的呈现方式，
   不引入动画框架或等待旧页退出才准许导航的流程。
3. 由实际 Router/Query 继续管理页面和读取。不能因播放动画额外丢失表单/查询/命令
   上下文或重复提交；同页操作不为整页动画卸载重挂业务内容。正常路由切换及其必要的
   组件生命周期仍允许，不限定 key 或 DOM 结构。快速 A→B→C 以实际抵达的 C 为准，
   结束的动效不覆盖新页。
   已有未保存/在途导航拦截未放行时，卡片与输入留在原页；放行后才切换。
4. 检查实际叠层关系：当前卡片在业务内容内渲染，若选用 transform/opacity 等方式，
   核对动画中和结束后的 fixed 卡片、遮罩、菜单层级及居中，避免改变定位或裁切。
   维持 Task50.1–50.3 的背景滚动、gutter、焦点/键盘、窄屏与退出保护。
   复用现有卡片逻辑，允许为本次切页做最小必要的兼容调整，不扩展卡片业务。
5. 优先扩展现有测试，必要时增加专门用例文件，覆盖主页面切换和同页排除，
   通过真实导航验证可见结果。
   延迟/失败使用现有隔离 fake API 或 Python harness 的真实读取路由；
   用 fixture 中实际存在的库、任务、规则和定义打开详情，不造不存在的链接或命令。
   复用 Playwright 截图/trace 记录动效，无需新增治理或取证工具。

### Acceptance Criteria

九个主页面全部覆盖；慢读、错误、卡片、键盘和 reduced-motion 按实际入口及风险选择
代表场景，不要求九页与全部条件做全排列。DOM/CSS 测量用于辅助，验收以可见结果为准。

- [ ] 九个侧栏主页面均有协调切换。桌面 1536×1024、窄屏 390×844 连续导航中，
  侧栏/页头稳定，内容不挤压、闪白、叠影或残留旧页；动画中仍可操作新页并继续导航。
- [ ] 首页→文件→媒体库→返回、快速往返和既有跨主页面链接使用同一主页面判断；
  目标、URL、安全返回上下文和原滚动规则正确，不以点击来源决定是否切换。
- [ ] 自动化标签/新建/编辑/现有详情、任务中心筛选/详情及其标签、规则分类/编辑子路由、
  库/目录切换、配置卡片开关、刷新/轮询不重播整页动画。同页深链/认证续转仍到正确内容，
  首入不先闪出错误父列表；合法局部动效保留。
- [ ] 在真实表单输入后尝试离开：继续编辑保留输入和卡片，明确放弃后抵达所选页面。
  在途/未知命令保护与核对保留；整页动画不把未放行的页面显示成已切换。
- [ ] 过渡不遮挡目标页已有且适用的加载、空态、无 Active、403、读失败及恢复操作，
  不要求为九页统一新增这些状态或恢复机制。两种库保持已交付的分阶段加载要求；
  读取恢复后是当前页面内容，快速导航不露出旧上下文，不留在无限动画中。
- [ ] 键盘、跳至主内容、卡片焦点/关闭回焦和背景锁定正常；reduced-motion 下可直接
  阅读/操作。无人为等待；进场中立即打开已有卡片，也不移位、裁切或失去遮罩。
- [ ] 纯导航、卡片开关和读取不自行触发配置/文件/整理写命令；显式保存/执行仍按原
  权限和结果工作。Task50.1–50.3 的卡片、两种库布局/加载和返回行为保持通过。

### Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。本 Task 为 T3：共享呈现
影响 Router/认证和多页交互，须跨页集成及真实浏览器验收；不改变后端权限、Storage、
schema 或业务并发合同。若实现需要改变这些边界，先由 B 重评，范围问题交 A。
Slice 最终仍为 T4，本 Task 的 T3 不替代整体验证。

Developer 与 B 各自本轮的测试时间须小于该轮总用时 50%。记录实际起止和测试区间并集，
并行时间不重复相加，不空等凑比例。先复现已知阻塞再运行适用门禁；在本轮约束内
未完成的验收如实记为待完成，不省略后宣告 PASS。

### Developer — affected tests

cwd web/，补充上述行为用例后执行：

    npm run test -- run src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts src/routes/router.test.tsx src/shared/auth/AuthBoundary.test.tsx src/shared/ui/modal-card.test.tsx
    npm run typecheck
    npx eslint src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.ts src/shared/navigation/destination-model.test.ts src/routes/router.tsx
    npx prettier --check src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.ts src/shared/navigation/destination-model.test.ts src/routes/router.tsx src/shared/ui/styles.css
    npm run build
    npm run test:e2e -- tests/e2e/dashboard.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/automation-presentation.spec.ts tests/e2e/task-center-layout.spec.ts

新增/另改文件追加到上述受影响检查。Shell 测试覆盖九个身份、同页排除、快速导航和退出
拦截；E2E 覆盖真实入口、前后退、认证续转、窄屏/键盘与 reduced-motion。
优先扩展上述现有 spec，新增专门测试文件时追加其命令，不以原样通过代替新行为断言。
其他组件有实际改动时增加其直接受影响测试。
根目录运行 python3 scripts/check_governance.py 与 git diff --check。
受影响测试完成后提交 coherent checkpoint，Developer 不承担 B 全量门禁。

### B — acceptance and full regression

独立审查完整 Task Base..候选 Head，复现首页→文件→媒体库→返回、九入口覆盖、
快速往返、同页详情/标签排除、自动化未保存输入后尝试离开的真实旅程。使用最终生产资产
查看桌面/窄屏过程截图与 trace，检查进场中立即开卡、遮罩/定位、键盘和 reduced-motion；
不能只以 animation 属性或停稳截图作为结论。

共享 Shell 影响九页，B 运行完整 Web 单元、默认 E2E 和静态门禁覆盖既有交互：
cwd web/ 执行 npm run typecheck、npm run lint、npm run format:check、
npm run test -- run、npm run build、npm run test:e2e。
真实 Python 验收使用现有配置与最终生产资产，针对直接受影响的旅程选取以下既有用例，
用 -g 筛选后分别运行以隔离有状态 fixture，不将五个完整模块无条件列为本 Task 门槛：

    npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g 'the selected run detail reads progress, filtered items, evidence and records'
    npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/storage-dialog.python.spec.ts -g 'closes view, add and edit cards through the shared visible exit'
    npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-create-dialog.python.spec.ts -g 'opens create and edit cards from a scrolled list without moving or resizing the background'
    npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/direct-files.python.spec.ts -g 'both library edit cards accept a legal Active with an unnamed Storage and save only the name'
    npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts -g 'CLI and the Web .* page list the same live directory'

分别核对任务详情、Storage 卡片退出、自动化新建/编辑稳定性、两种库编辑和真实目录浏览。
新切页场景及同页排除用例仍须补齐，不能以既有用例代替新结果；依据实际改动追加直接
受影响的权限/命令/返回用例。通过实际页面记录纯导航不增加业务写命令。
跨 Storage 移动、批量删除等未受本次改动直接影响的完整矩阵由 Slice 最终 T4 统一承担。
只用临时 Local/SQLite/合成数据，不使用用户配置、运行数据库或媒体。

本 Task PASS 后重评全部 RO/Surface：若剩余主页面切换结果完成，停止规划，
由 B 完成 [共享完整 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)
及 Slice AC-11 要求的最终安全/打包/原生验证，提交 Closure Packet 给 A。
同一最终候选上已经完成、执行输入匹配的 Task 验收可同时计入最终验证，不重复跑相同门禁。
最终资产变化后不能直接复用 Task50.3 的旧浏览器/打包结果，复用须按 workflow 列证。
Docker/重启等适用性依据最终差异说明，既有外部服务 skip 保留；未运行项不标为 PASS。

### Non-goals

不重做九页业务或增加入口；Task50.1–50.3 的已交付结果保持，允许为本次切页做必要的
最小兼容修正，不借机扩展其业务或重做无关部分。
不增加动画设置、设计系统、Provider、后端能力、状态/恢复类型、队列或迁移；
不将可选视觉调整、固定像素/时长或过程工具作为新阻塞。A 拥有 Slice 最终接受与关闭。

### Developer Completion Report — 2026-11-07 fix

实现候选：`4c511fc7d18d66d01c70c7a695f88c77376135f6`（2026-11-07 00:20 +08:00），
Task Base 仍为 `ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749`。原候选 ad81eb6b 的
B50.4-01 在同一 Task 内修正；未重设 Base、未扩大范围、未推送或部署。本报告记录后由
docs checkpoint 交回 **READY FOR B REVIEW**，不自行宣告 PASS。

**修正事实**

- `ShellPageSurface` 只在主页面挂载时渲染一次 `mf-page-surface-enter-start`；下一帧移除
  该启动类，由 `mf-page-surface-entering` 触发一次 200ms opacity transition。启动类不会
  因同页查询、标签、卡片或刷新重新添加。
- `styles.css` 删除持久 `animation`/keyframes；`:has(...)` 在真实卡片/抽屉层存在时将本次
  进入立即落到 opacity 1、transition none。层移除后 opacity/transition 不再变化，因此
  不会重播；reduced-motion 下直接 opacity 1、transition none。
- 扩展现有 `page-transition.spec.ts`：九个主页面逐页采样进入过程的 opacity/启动类；新增
  自动化真实“新建→取消”两次（1536×1024）与存储真实“查看→关闭”两次（390×844）的关闭后
  过程断言；保留 forward detail overlay、认证续转、键盘与 reduced-motion 用例。
  `AppShell.test.tsx` 补充启动类只移除一次的单元断言。
- 未改路由、权限、API、Storage、schema、业务命令或卡片业务；仅共享切页呈现与测试。

**实际执行（cwd `web/`，除注明外）**

| 命令 | 实际结果 |
|---|---|
| `npx playwright test tests/e2e/page-transition.spec.ts -g "same-page card open and close never replays"`（修正前，当前 dist） | 失败：`automation.every(sample.opacity === 1)` 为 false，复现关闭后整页变浅；随后同命令在修正后通过 |
| 同上（修正后） | 1 passed（4.9s） |
| `npx playwright test tests/e2e/page-transition.spec.ts` | 5 passed（11.2s），含九页逐页采样、同页关闭、forward overlay、认证/键盘/reduced-motion |
| `npm run test -- run src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts src/routes/router.test.tsx src/shared/auth/AuthBoundary.test.tsx src/shared/ui/modal-card.test.tsx` | 5 files / 68 tests passed（3.64s） |
| `npm run typecheck` | passed |
| `npx eslint src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.ts src/shared/navigation/destination-model.test.ts src/routes/router.tsx tests/e2e/page-transition.spec.ts` | passed |
| `npx prettier --check`（上述文件及 `styles.css`） | passed |
| `npm run build` | passed（150ms；保留既有大 chunk 提示） |
| `npx playwright test tests/e2e/dashboard.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/automation-presentation.spec.ts tests/e2e/task-center-layout.spec.ts` | 32 passed（14.9s） |
| 根目录 `python3 scripts/check_governance.py`、`git diff --check` | PASS |

**测试时间**：本轮从 `2026-11-07 00:16:36 +08:00` 开始；可核实测试区间为
00:17:11–00:17:14（修正前复现）、00:18:30–00:18:35（修正后回归）、
00:18:39–00:18:50（完整 page-transition）、00:19:48–00:19:51（单元）、
00:19:55–00:20:10（四个受影响 E2E），并集约 37 秒；构建/typecheck/静态检查发生在
00:18:20–00:18:30 窗口，保守计入 10 秒，合计约 47 秒。按报告记录时点约 5.5 分钟
工作窗口计，低于 30%（约 99 秒）。

**剩余风险 / 未执行**：B 的全量 Web/Python 回归、完整默认 E2E、真实 Python 浏览器旅程、
打包/安全/Slice 最终 T4 门禁未由 Developer 执行，不记为通过；浏览器证据来自 Playwright
Chromium 1536×1024 与 390×844，B 仍须在最终候选上查看实际过程截图/trace 并完成其验收。
未接触用户配置、运行数据库或生产媒体；预存 dirty/untracked 文件全部保留，不纳入 checkpoint。

### B Review Result — 2026-11-07（修正候选复核）

```text
Reviewed Base: ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749
Reviewed Head: 733250e836615317340c563f603efea41492987f
Implementation Candidate: 4c511fc7d18d66d01c70c7a695f88c77376135f6
Decision: FIX REQUIRED
Resolved: B50.4-01 — 同页关闭弹卡不再重播整页进入
Task blocker: B50.4-02 / P1 — 切页呈现重挂业务/认证，破坏续转与目标 URL
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

已独立审查完整 Base..Head 累计 10 个文件（4 个规划/激活文档、6 个产品/测试文件）。
4c511fc7..733250e8 仅改 TASK.md，执行输入相同。分支 main、复核起点 HEAD 如上；
workspace/Git 可写，预存 dirty/untracked 保留。本轮只更新 B 报告，不改产品或 A 所有文档。

**B50.4-01 已解决。** 专用切页 E2E 5 项通过，含桌面自动化与窄屏存储反复打开/关闭。
实际过程截图/trace 与关闭后采样均支持不再重播；另用普通侧栏点击、只监听 transition
事件核对九页，均有实际 transitionrun/end。此项不再作为阻塞。

**B50.4-02 / P1：共享切页容器重新挂载认证及业务内容，既有导航被页面副作用抢写。**

两条均为现有受支持入口，已用隔离生产资产分别对照 Task Base、初版和当前候选：

1. 尚未连接时，打开已保存的任务中心链接
   `/ui-v2/operations?view=ended&status=failed&run=job-005`
   （现有 operations.spec.ts:710 的精确任务续转旅程）。Base 自动进入连接页，显示
   API token 输入框；候选停在 `/ui-v2/operations?view=ended&run=job-005`，
   显示 “Not connected”，没有连接输入框，无法继续正常的“连接→原任务详情”旅程。
2. 连接 → 侧栏“媒体库” → 正常选中现有 movies 库 → 侧栏“文件”。Base 到达
   `/ui-v2/resourcelib/files`；候选最终变成
   `/ui-v2/resourcelib/files?mediaLibraryId=movies`。历史记录证明侧栏先导航到正确地址，
   随后旧媒体库页面把自己的参数写入文件页。媒体库→任务中心也出现相同参数残留。

根因在 `AppShell.tsx:118–137,280–296`：以 Router location 的主页面身份作为整个
ShellPageSurface 的 key，而 children 包含 `router.tsx:46–51` 中的 AuthBoundary 与
Outlet。切换 key 重新挂载这棵子树；在 location 与当前路由内容交接时，旧内容的挂载
副作用参与新导航。任务中心 `OperationsLanding.tsx:542–561` 的原有筛选规范化导航
与认证跳转竞争；媒体库 `MediaLibraryFilesPage.tsx:3209–3217` 的挂载同步通过
`:230–245` 写当前浏览器 pathname，导致目标页带上旧页参数。

引入提交为 `ad81eb6be204aee7baf91a1a48273675a554f872`，时间
2026-11-06 23:53 +08:00。对该初版重新构建后，两条旅程均复现；不是本次 4c511fc7
才引入。Base 两条均通过。当前证据表明必需的认证续转与精确跨页 URL 不满足；
权限隔离用例在 URL 断言处失败，不将其描述为越权读取或权限绕过。

### 本次修正开发指导（同一 Task）

1. 从共享切页呈现边界修正生命周期：动画应反映已抵达的主页面，不应为播放动画额外
   重新挂载 AuthBoundary 或交接中的旧业务页。保留 Router 对匹配/导航的管理和认证
   组件的正常生命周期；允许在 AppShell/router 做最小必要调整，不限定具体 DOM/key 实现。
2. 保留现有筛选规范化、安全续转、库地址同步及权限规则。不要给各业务页面增加路径
   判断来掩盖共享层问题，不加延迟/重试、不禁用规范化、不扩大认证允许范围或削弱断言。
   同时保留已解决的同页关闭不重播、下次真正切页仍过渡和立即开卡定位。
3. 优先复用现有失败旅程；如需增强断言，扩展既有 spec，覆盖自动转入连接页、连接后精确
   任务详情，以及媒体库→文件/任务中心的干净 URL。先运行以下实际失败模块与切页用例：

       npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/page-transition.spec.ts

   再按原 Developer affected-test 计划完成直接受影响单元、typecheck、changed-file
   lint/format、build、四个既定受影响 E2E、治理和 whitespace。改动测试追加相应检查。
   Developer 不承担全量 Web/Python 或最终发布矩阵；交同一 Task 的新 checkpoint，
   B 在修正候选上完成分配的完整验收。

### 本轮实际验证与证据

本地原始日志/生产资产摘要/截图/trace 保存在
`.git/validation-evidence/733250e8/B50.4-review/`，未发布到远程。
`inputs.json` 记录 dist、依赖锁、fake API 与两套 Playwright 配置 SHA256。
最终 JS 为 index-BM7jOxaD.js，CSS 为 index-BUcXw9MU.css。

| 验证（未注明时 cwd web/） | 实际结果 / 原始证据 |
|---|---|
| 根目录 `npm --prefix web run build` | PASS；build.log，既有大 chunk 提示保留 |
| `npm run typecheck`、`npm run lint`、`npm run format:check` | 全部 PASS；各同名 log/json |
| `npm run test -- run` | 94 files / 1390 tests PASS，131.33s；unit.log/json，保留 jsdom scrollTo 提示 |
| `npx playwright test tests/e2e/page-transition.spec.ts`（trace on） | 5 PASS，12.2s；transition.log、transition-results/ |
| `npm run test:e2e` 对应完整默认 Playwright 配置（trace on） | 254 PASS / 6 FAIL，3.6min；default.log、default-results/ |
| 原计划五条 Python Playwright 精确筛选命令（各独立 harness，trace on） | 合计 6 PASS：任务详情、存储关闭、自动化新建/编辑、两库配置、CLI/两 Web 实际目录；native-*.log/json 及各目录 |
| 根目录 `.venv/bin/python -m unittest discover -s tests` | 2603 tests OK / 7 个既有可选 skip，305.039s；python-full.log/json，ResourceWarning 保留 |
| 根目录共享 Python 质量命令：ruff format/check、compileall、pip check、两个公开示例 config validate | 全部 PASS；ruff-format/ruff/compile/pip/example-*.log/json |
| 根目录 `rg -n -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml` | 无匹配，exit 1 符合预期；准确命令见 forbidden.json |
| 根目录 `python3 scripts/check_governance.py`、`git diff --check ea8aad6..733250e8` 和报告 whitespace | PASS，报告记录后再次核对 |
| 普通九页导航及 Base/初版/候选对照 | natural-entry.*、route-regression.*、original-regression.*；各 trace/截图保留 |
| 动态视觉 | 已查看桌面自动化退出、窄屏存储退出、正常进入帧及未连接任务中心截图；transition-results/ 与 close-frames/、entry-frames/ |
| wheel/安装消费者/容器与 Slice 最终完整安全、打包、原生矩阵 | 未运行；已确认阻塞，停止追加昂贵门禁，不记为 PASS |

完整默认 E2E 的六项失败全部保留：medialib-files.spec.ts:45、:422（目标 URL），
operations.spec.ts:184、:492、:710（未出现连接表单）及 :435（跨页 URL）。
专用切页测试的简单认证用例通过不能替代这些现有带筛选/任务选择的续转旅程。
本轮 Python 全量已在发现默认浏览器阻塞前启动；其通过不抵消 Web 的实际失败。

测试计时：有效记录窗口从 2026-11-07 00:25:07 +08:00 开始；并行测试按区间并集计，
已记录区间 365.453 秒，另为短构建/治理/whitespace 保守计入 20 秒，上界约 385.5 秒。
00:40:16 记录时有效工作已 909.4 秒，占比上界 42.4%，低于 50%；后续仅报告与收尾，
未空等凑比例。各起止记录和 timing.json 保留。

### 全部 Slice 结果重评

| Required Outcome / Surface | 当前判断 |
|---|---|
| RO-1：任务详情卡片、可读性和既有操作 | 保留 Task50.2 B PASS；当前原生详情用例通过，精确任务认证续转被 B50.4-02 阻塞 |
| RO-2：存储卡片/菜单 | 保留 Task50.1 B PASS；本候选共享关闭原生旅程及窄屏重复关闭通过 |
| RO-3：两种库布局、菜单、四个配置入口 | 保留 Task50.3 B PASS；本候选原生配置/目录通过，跨页 URL 被 B50.4-02 阻塞 |
| RO-4：库加载与自动化新建/编辑稳定性 | 保留 Task50.1/50.3 已接受结果；本轮已滚动自动化新建/编辑原生旅程通过 |
| RO-4：九主页面过渡及同页排除 | 同页重播已解决，九页进入通过；认证/导航兼容性尚不满足 AC-8，本 Task 继续修正 |
| 全部 Surface 的共同安全与最终 AC-11 | 尚未完整完成，不提交 Closure Packet；既有 Task 接受事实不改写 |

继续同一 Task，不创建新 Task，不更改 Slice/Roadmap/Progress 边界或宣告 Slice READY/CLOSED。

### 规划基线与本次激活

原 Task Base 保持 ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749；本次激活起点为 main /
66c165e710065fb6ee0a169a2858da6a975af019，workspace/Git 可写，激活前治理检查 PASS。
预存 mediaflow/.DS_Store 修改、各层 .DS_Store、根目录日志和 15、
output/ 下数据库参考/图片/HTML/预览等未跟踪产物全部保留，不纳入 checkpoint。
本轮仅激活本 Task 并同步 Slice/Roadmap/Progress 的事实指针；范围、验收和测试分工
沿用已修订计划。未开始产品实现或 Task50.4 验收，不宣告 Slice 完成。

### Developer Completion Report — 2026-11-07 B50.4-02 fix

实现候选：`ad40d23538cb3bf30d416ae7cefb6920d2375f5b`（2026-11-07 00:49 +08:00）。
Task Base 未变，仍为 `ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749`；未重设 Base、未扩大范围、
未推送或部署。本报告记录后交回 **READY FOR B REVIEW**，不自行宣告 PASS。

**根因与修正**

- B50.4-02 根因确认：`ShellPageSurface` 以主页面身份作 `key`，把 `AuthBoundary` 与
  Router `Outlet` 一起重挂。导航交接期间旧业务页的挂载副作用参与新 location，造成
  未连接深链不进入连接页、媒体库参数写入文件/任务中心 URL。
- 修正只改共享呈现边界：移除身份 `key`，同一 DOM 包装和其内路由子树持续挂载；
  `entryVersion` 仅在 `shellPageForPath` 到达身份变化时递增，驱动一次启动类→下一帧
  移除→200ms opacity transition。同页 query/标签/卡片/刷新不递增，不重播。
- `AuthBoundary` 恢复普通 Router 生命周期；未给业务页面增加路径判断，未加延迟/重试，
  未禁用筛选规范化、认证续转或库地址同步，未改权限、API、Storage、schema、路由或业务命令。
  Task50.1–50.3 的卡片、库加载/返回和 reduced-motion 行为保留。

**测试改动（真实入口）**

- `AppShell.test.tsx`：主页切换后断言仍是同一个 `[data-main-page]` 包装（不是新 key
  节点），同页子路由保持同一节点，真正切页仍进入一次。
- `page-transition.spec.ts`：九页真实侧栏导航前标记当前包装，逐步断言标记跨九页保留；
  reduced-motion 下从存储进入媒体库后断言精确的
  `/ui-v2/medialib/files?mediaLibraryId=movies`，不残留上一页 search。
- `operations.spec.ts`：未连接的任务中心精确深链继续断言自动进入连接页、连接后
  `view=ended&run=job-005` 的任务详情；媒体库→任务中心断言目标 URL 不含
  `mediaLibraryId`。
- `medialib-files.spec.ts`：媒体库→文件仍断言精确 `/ui-v2/resourcelib/files`，并显式
  断言不带入 `mediaLibraryId`。

**实际执行（cwd `web/`，除注明外）**

| 命令 | 实际结果 |
|---|---|
| 修正前 `npx playwright test tests/e2e/operations.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/page-transition.spec.ts` | 6 failed / 38 passed（90.2s），复现 B 列出的连接页与跨页 URL 失败 |
| 修正后同一三模块命令 | 44 passed（27.5s） |
| `npx playwright test ... -g "all nine sidebar\|...\|authentication continuation"` | 5 passed（6.1s），含新增包装持久标记与精确 URL 断言 |
| `npm run test -- run src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts src/routes/router.test.tsx src/shared/auth/AuthBoundary.test.tsx src/shared/ui/modal-card.test.tsx` | 5 files / 68 tests passed（3.67s，最终格式后复跑） |
| `npm run typecheck` | passed |
| `npx eslint`（上述源文件及三个改动 E2E spec） | passed（格式修正后再次复检） |
| `npx prettier --check`（上述源文件、`styles.css` 及三个改动 E2E spec） | passed（一次格式修正后复检） |
| `npm run build` | passed；`dist/assets/index-BBNz3k9m.js`、`dist/assets/index-BUcXw9MU.css`，既有大 chunk 提示保留 |
| `npx playwright test tests/e2e/dashboard.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/automation-presentation.spec.ts tests/e2e/task-center-layout.spec.ts` | 32 passed（15.7s） |
| 根目录 `python3 scripts/check_governance.py`、`git diff --check` | PASS |

**测试计时**：本轮从 `2026-11-07 00:42:39 +08:00` 开始；可核实测试/静态检查区间并集
约 188.3 秒（含修正前复现 90.2 秒、修正后三模块 27.8+27.9 秒、四模块 15.7 秒、
定向 6.6 秒、单元 3.6+4.0 秒、typecheck/lint/prettier/build 约 12.9 秒及报告后
最终 eslint/prettier 复检 1.8 秒），低于本轮
总用时的 30%。未空等凑比例。

**剩余风险 / 未执行**：B 的全量 Web/Python 回归、完整默认 E2E、真实 Python 浏览器旅程、
打包/安全/Slice 最终 T4 门禁未由 Developer 执行，不记为通过；B 仍须在最终候选上查看
实际过程截图/trace，确认九页过程、认证续转、快速导航及同页排除。未接触用户配置、
运行数据库或生产媒体；预存 dirty/untracked 文件全部保留，不纳入 checkpoint。
