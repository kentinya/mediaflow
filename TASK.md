# Task50.4 — V2 侧栏主页面切换体验

Task50.3 已由 B 独立验收 **PASS**。完整报告及证据见
ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749:TASK.md；已审范围保留为
073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d..a284c0135701d949afcae1cfe15fbba904eb16e0，
最终实现 checkpoint 为 a7a2b669da4611efd84778aabd4435145bcfd159。
用户已明确授权激活修订后的 Task50.4，本 Task 为唯一当前实施 Task，状态 PLANNED。
本轮由 B 完成激活记录，待 Developer 实施，不自动启动 Developer，不推送或部署。

Authority：已提交 [Slice50](SLICE.md) 的 RO-4、AC-8/10/11 与 V2-UX-012 的主页面
切换部分；生命周期遵循 [Development Workflow](docs/development-workflow.md)。
本次激活不改变 Slice 范围、Base、Task 验收或既有 Task 接受事实。

```text
Task ID: 50.4
Task Type: SLICE
Parent Slice: 50
Status: PLANNED
Task Base: ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Working Branch: main
Development Authorization: TASK50.4 ONLY — EXPLICIT USER ACTIVATION
Next Action: DEVELOPER IMPLEMENTS TASK50.4; THIS TURN ACTIVATION ONLY
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

### Developer Completion Report（待实施后填写）

精确 checkpoint / READY FOR B REVIEW、实际改动与取舍、受影响测试命令/结果、
失败/风险和未完成项。测试时间与本轮总时间据实给出，无需全量验收材料包。

### B Review Result

尚无 Task50.4 实现候选，未进行本 Task 的 Base..Head 产品验收，不给出虚构 PASS。
Task50.3 的 PASS 保持；Slice50 仍 ACTIVE：RO-1、RO-2、RO-3、RO-4 的库加载与自动化
稳定性已有 B 接受记录，RO-4 的主页面过渡尚未交付。通过本 Task 后按上述 stop rule
重评全部结果，完成最终门禁并交 A，不自动创建新 Task 或宣告 Slice CLOSED。

### 规划基线与本次激活

原 Task Base 保持 ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749；本次激活起点为 main /
66c165e710065fb6ee0a169a2858da6a975af019，workspace/Git 可写，激活前治理检查 PASS。
预存 mediaflow/.DS_Store 修改、各层 .DS_Store、根目录日志和 15、
output/ 下数据库参考/图片/HTML/预览等未跟踪产物全部保留，不纳入 checkpoint。
本轮仅激活本 Task 并同步 Slice/Roadmap/Progress 的事实指针；范围、验收和测试分工
沿用已修订计划。未开始产品实现或 Task50.4 验收，不宣告 Slice 完成。
