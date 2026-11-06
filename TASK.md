# NO ACTIVE IMPLEMENTATION TASK

Task50.1：**PASS**（B 独立验收，2026-11-06）。
已交付存储查看/添加/编辑卡片与更多菜单，以及自动化新建/编辑卡片稳定性。
完整 Task 计划、Developer 交接与原验收见 Git `8573445f13a3f67cc434a576ee87e1d048d8362a:TASK.md`；
本页保留精确审查范围、实际结果和 Slice 重评。

Slice50 仍为 ACTIVE。RO-1、RO-3 及 RO-4 的侧栏主页面切换/两种库加载尚未交付。
本轮已规划下方 Task50.2 草案，未激活，不授权实施；没有新的活动实施 Task。
Task50.1 的原验收如下保留；本轮不重复验收，不由 B 关闭 Slice。

## B Review Result

**Decision: PASS — 2026-11-06。Task50.1 完成；Slice50 保持 ACTIVE。**

```text
Reviewed Base: f24dce7a0a97e035078879e2a93855de02d74f54
Reviewed Head: 8573445f13a3f67cc434a576ee87e1d048d8362a
本轮增量: 4f4c5f49..8573445f
Implementation: b7636a87 + 22618d70 + cb3b6436 + 736aa5df + 5b390581
Branch: main
Next Action: WAIT FOR NEXT TASK PLANNING REQUEST; NO AUTOMATIC IMPLEMENTATION
```

结合此前完整差异复核，审查整个 Task Base..Head、本轮全部增量以及实际用户入口；没有把
Developer 的通过声明当作独立验收。上次 ESLint/Prettier 失败在精确候选已复验通过，之前
保存中遮罩关闭、存储退出缺失也保持修复。未发现剩余 Task 阻塞。
原有 `.DS_Store`、日志、`15`、`output/` 等工作区文件保留；没有修改产品/测试源码或推送。

### 用户结果与验收

- 存储列表查看、添加、编辑均使用居中卡片，读取/失败/正文保持协调布局；正常关闭平顺
  退出，reduced-motion 不强制动画。关闭后回到原入口，滚动锁和焦点约束准确释放。
- Local、SMB、OpenList、S3/R2 原有字段、精确根、不可变 ID、隐藏选项及 Active/fence
  配对保留。正常 Save 真实发布读回；重复/无效/冲突/权限/未知结果保持各自纠正或核实路径。
- 保存中点遮罩不能退出或重发；成功后退出期间 Save 禁用。查看、取消、菜单、加载和
  读取失败返回不会自动提交配置或媒体操作；慢读取关闭/换对象后的响应不重开旧意图。
- “更多”锚定正确行，普通/危险操作清楚，桌面/窄屏与键盘可用。复制输入焦点不被迟到
  回焦抢走，既有启停、显式只读检查、引用/移除确认和未知核实仍可达。
- 自动化新建/真实已保存定义编辑的慢读取与正文使用稳定卡片；已滚动背景、实际渲染的
  占位滚动条和 reduced-motion 逐帧用例通过，原字段、保存、启停、复制、Run once 与
  深链/列表返回保持。没有以停稳截图代替打开中间过程检查。

例如：添加存储后点击保存，误点灰色背景时仍等待原请求；成功后卡片退出并显示真实清单。
编辑读取失败时显示失败和重新读取/返回，回到列表不会变更配置。自动化列表已滚动时打开
新建或编辑，背景不回顶，加载到表单不从矮壳突然撑大。

### 精确候选的实际门禁与证据

稳定 ignored 目录：`.git/validation-evidence/8573445f/b-review-20261106/`，仅本机可取。
`python.json` / `web.json` 记录逐条命令、cwd、退出码、耗时；同名 `.log` 保留完整输出。

| cwd | 实际命令 | 结果 |
|---|---|---|
| 根目录 | `python3 scripts/check_governance.py`；`git diff --check f24dce7a..8573445f` | PASS |
| 根目录 | `.venv/bin/ruff format --check .`；`.venv/bin/ruff check .` | PASS |
| 根目录 | `.venv/bin/python -m unittest discover -s tests` | **2603 tests，OK，skipped=7**，313.434s；`python-tests.log`。包含四个指定存储/自动化后端模块、C→A 身份、pins/并发/非重放及生产静态服务相关回归。 |
| 根目录 | `.venv/bin/python -m compileall -q mediaflow tests scripts`；`.venv/bin/python -m pip check` | PASS |
| 根目录 | `.venv/bin/mediaflow --config config/strategy.example.json config validate`；同命令使用 `config/mediaflow.phase13.2.example.json` | PASS |
| 根目录 | `rg -n -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml`（正则为交替） | 无匹配，预期 exit 1 |
| `web/` | `npm run typecheck`；`npm run lint`；`npm run format:check` | 全部 PASS |
| `web/` | `npm run test -- run` | **94 files / 1352 tests passed** |
| `web/` | `npm run build` | PASS，既有 chunk 大小提示 |
| `web/` | `npm run test:e2e` | **253 passed** |
| `web/` | `npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/storage-dialog.python.spec.ts tests/e2e/automation-create-dialog.python.spec.ts` | **22 passed**，含本轮实际修正的测试文件 |
| 根目录 | `.venv/bin/python -m pip wheel . --no-deps -w dist` | PASS；`wheel-build.log` |
| 根目录 | `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-2.0.0.dev0-py3-none-any.whl` | PASS；源码目录外新 venv 安装、实际 CLI/数据库/准备消费者均通过，`wheel-smoke.log` |

wheel SHA256：`792d39c06ebb77806ba5cc170e8b20f30f1a141e3a833780c01c2f736a942ed5`。
`artifact-identity.json` 记录 wheel 与本候选 Web 构建摘要。按既有发布合同，wheel 本身不含
Web 资源；生产 Web 构建作为独立静态根由 Python 服务，真实 Python E2E 使用该构建。

**原生交互与复用：** 本轮另以已有 `operations_inventory_harness.py --port 4184`、真实
API、临时 SQLite/Local 根，在 1536×1024 和 390px 从存储真实入口注入已有 GET 的网络失败，
验证详情/编辑失败返回、添加授权失败输入保留、菜单到复制输入焦点和零变更。
`failure-probe.mjs`、`failure-results.json`、对应截图与日志保存上述目录，已检查截图。
原正常开关卡片/自动化对照截图与逐帧退出证据复用 B 自己的
`.git/validation-evidence/8b16ba6f/b-review-20261106/`：
`git diff 8b16ba6f..8573445f -- web/src web/package.json web/package-lock.json scripts mediaflow`
无差异，产品、样式、依赖和该探针/harness 输入未变；本轮全部正式 Web/真实 E2E 已重新运行。
自动化占位滚动条用同源样式产生真实浏览器 gutter 并逐帧测量，不是模拟 clientWidth；
没有跨 OS 滚动条设置矩阵或生产部署验收的声明。

**限制与适用性：** 7 项可选外部服务/耐久测试仍因缺少专用 profile 跳过，未连接生产服务。
Python 有 ResourceWarning、jsdom 有既有 scrollTo 提示，均如实保留。Docker daemon 当前
不可用，未运行镜像/Compose/重启安全矩阵；本 Task 只改前端呈现及测试，不改 Dockerfile、
Compose、入口/部署权限、后端、schema 或常驻服务合同，因此该矩阵不选为本 Task 的必需
门禁。打包、源码外安装消费、Python 真实静态服务和适用安全行为已由上述检查覆盖；不将
此判定扩大为发布/部署批准。

**时间分配说明：** 全回归后台并行执行，最长单组 Python 测试约 314 秒。本轮测试运行的
墙钟时间超过用户设定的本轮 50% 分配；这是本次执行安排未满足的约束，如实记录，不通过
拖长审查或隐去测试耗时凑比例。没有因此省略失败、修改断言或转交全回归给 Developer。

### 全 Slice 结果重评与下一步

| Required Outcome | 当前结果 |
|---|---|
| RO-1 任务详情卡片/可读性 | 未实施，仍需后续 Task。 |
| RO-2 存储三卡片/更多菜单 | **Task50.1 已完成并验收。** |
| RO-3 两种库去目录树、菜单/配置卡片 | 未实施，仍需后续 Task。 |
| RO-4 自动化新建/编辑稳定性补充 | **Task50.1 已完成并验收。** |
| RO-4 侧栏主页面切换/两种库加载 | 未实施，仍需后续 Task。 |

本 Task PASS 不能证明整个 Slice 完成。不提交 Slice Closure Packet，不由 B 宣告 Slice
PASS / CLOSED；保留 A 的合同/原 Base 及既有接受账本。当前用户请求为修正复核，未另建
下一活动 Task；本轮后续规划见下方草案，实施仍需对应授权。

---

# Task50.2 草案 — 任务详情弹卡与可读性（未激活）

Authority：已提交 `575898ebaae593568be59699bb40116f9e6f2d91:SLICE.md` 的 RO-1、
AC-1/2、适用 AC-10/11；遵循 [Development Workflow](docs/development-workflow.md) 与
[Task 模板](Task/TEMPLATE.md)。当前合同的实施授权仍仅为 Task50.1；本草案不授权实施。

规划现场：分支 `main`，HEAD/Task Base 如下；仓库与 Git 可写，治理预检 PASS。
预存 `mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、日志、`15`、`output/` 等均保留，
不纳入 checkpoint。本轮仅改本页；治理、文档链接/测试路径、Base 祖先关系及 whitespace
检查通过，未运行产品测试。检查耗时不足 1 秒，低于本轮实际工作时间的 50%。

```text
Task ID: 50.2
Task Type: SLICE
Parent Slice: 50
Status: PLANNED
Activation: DRAFT ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
Task Base: 575898ebaae593568be59699bb40116f9e6f2d91
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal 与完整用户旅程

落实 `V2-UX-005/006`：在任务中心点击名称，以保持原列表宽度和上下文的居中详情卡读懂
“哪个任务、流程到哪一步、文件实际如何、有什么需要处理”，并完成已有允许的操作。

- **入口：** 八个现有视图的任务名称、原精确任务链接、刷新和认证续转到达同一任务。
- **可见状态：** 优先让用户读懂任务身份、五态流程、阶段/等待、进度、独立文件/附件
  结果和当前业务问题；来源/目标、条目、记录、诊断分层可查。具体排列、分组和标签按
  内容设计。读取中有协调卡片，不闪假成功。
- **动作：** 已有控制、四类决定→分析→精确摘要→明确继续，以及计划、日志/审计、记录、
  JSON 导出仍可达；只使用后端已经允许的动作。
- **成功/退出：** 能读懂“流程已完成；部分文件失败”；关闭/返回恢复原合法视图、日期、
  页、问题文件定位、滚动和入口焦点。开关卡片不执行或取消工作。
- **失败/恢复：** 缺失、拒绝、读取失败、流程失败、未知效果/无 Result 如实显示，保留
  原有合法下一步。允许的退出/重开不丢原请求核对；技术终结失败保持事实查看。

完整依据：[TARGET 任务详情旅程](docs/product-experience.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)、
[CURRENT Tasks/results/recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[任务中心规范](docs/task-center-page-spec.md)、
[Architecture TARGET](docs/architecture.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)。
沿用 `UX-001–010`、`REQ-TASK-*`/`REQ-RESULT-*`/`REQ-RECOVERY-*` 的现行 V2 修订、
`REQ-WEB-004/005`、`REQ-SAFE-001–009`、`V2-OPS-014/016`、`V2-TASK-012–014`。

## 真实代码与范围

- `OperationsLanding.tsx`：`RunTable → selectRun → ?run= → RunDetailPanel` 是名称点击
  链路；`listSearch`/`applyDetailState`/`closeRun` 管列表、详情和问题定位返回。
- `shared/ui/styles.css`：`.mf-run-layout.mf-run-has-detail` 按约 34% 分配侧详情，并
  配套缩窄列表；窄屏详情占满视口。替换目标布局，按实际使用者保留其他布局。
- `RunDetailTabs.tsx` 已有进度、文件/附件、条目证据、记录、导出和同页摘要；
  `RunDetailFacts` 将业务内容与 Worker/固定配置等技术信息并列，需重排信息层级。
- `shared/ui/modal-card.tsx` 的 `ModalCardShell`、`useModalLayer`、`useModalCardExit`
  已提供无业务依赖的居中外壳、进出、滚动占位、inert、键盘/焦点能力。
- `routes/router.tsx`、`run-detail-state.ts`、`shared/navigation/operations-return.ts`
  已有精确链接和返回状态；`operations.spec.ts` 明确断言旧“桌面右列/窄屏全屏”几何。

范围是该完整详情旅程的 Web 呈现、必要导航/状态生命周期适配及测试。复用现有 typed API、
Query 与 Task/结果/恢复行为，不改变 API/application/runtime/schema、八视图总体和日期语义。

## 开发指导

1. 从上述真实入口梳理列表/详情 URL、问题文件返回、控制与恢复请求的状态归属，确认哪些
   状态须跨卡片退出保留。沿用既有业务语义，允许必要的组件与状态归属调整；未决请求
   的身份和核对上下文须保留。
2. 为选中任务实现协调的居中卡片，列表保持完整宽度，背景约束正确。优先复用现有共享
   外壳、锁滚动/占位、焦点和退出能力，允许按详情内容作必要适配，以可见交互和业务语义
   验收。处理首个聚焦点，避免旧 Escape/回焦与外壳重复响应。
   详情导航采用已有局部保滚动做法；深链没有原入口时给合法列表返回和焦点落点。
3. 让用户优先读懂任务、流程、文件效果和待处理项；具体排列、分组、标签及折叠方式由
   开发按内容设计。技术 ID、Worker、固定配置等诊断保持可查，失败阶段/未知效果/
   待处理项保持明显。历史名称、状态和计数使用已有任务证据。长路径和多列表格有界
   滚动/换行，关闭与必要操作在窄屏/键盘下可达。保留既有用户可见业务信息和必要证据
   的可达性，允许合并重复展示、折叠诊断，不要求展示所有内部字段。
4. 接入既有条目/记录过滤分页、单项证据、导出、控制、四类恢复和精确摘要。
   用真实在途/未知响应后的关闭、返回、重开验证核对保留；仅在实际链路需要时调整状态
   生命周期，不增加通用命令框架，不把展示重排变成新的执行入口。
5. 慢读取、拒绝/缺失/失败使用协调卡片；正文接入和退出平顺，reduced-motion 可用。
   关闭后晚到响应不重开旧任务，快速换任务不串结果，同条件刷新保留可用内容/阅读位置。
   不为动画延时，也不以重发业务命令更新界面。
6. 更新旧几何断言及受影响说明，完成下面 Developer 测试后交接一个完整 checkpoint。
   共享外壳如有修改，补直接受影响的存储/自动化回归；不顺带清理旧不可达恢复代码或
   重做其他中心业务。完整验收由 B 负责。

## Acceptance Criteria

- [ ] **卡片/返回（AC-1）：** 八视图真实名称点击打开协调居中卡片，原列表不挤窄。
  关闭、Escape、遮罩、浏览器返回遵循合法退出规则；视图/日期/页/问题定位/滚动/焦点
  保留。精确链接、刷新/认证续转到达正确任务，缺少原入口时可回合法列表。
- [ ] **可读性（AC-2）：** 流程、阶段/等待、处理进度与独立文件/附件效果层级清楚。
  混合结果、completed+技术失败/未知/无 Result、failed、cancelled、等待确认不互相冒充；
  未知总数不造百分比，恢复成功仍要求既有精确证据。按用户能否读懂和完成操作验收，
  允许不同排列、分组和标签设计，以及合并重复展示、折叠诊断；既有用户可见业务信息
  和必要证据保持可达。
- [ ] **证据/操作（AC-2/10）：** 来源/目标、结果、计划解释、日志/审计、记录/过滤/分页、
  导出和合法控制可达；四类处理完成原同一 Task 旅程。技术终结失败保持事实查看，成功
  兄弟项/未知效果不重放。纯查看/导航/刷新不发执行、取消或决定请求。
- [ ] **核对/并发（AC-10）：** 显式提交保持原权限、意图、身份及 pins/fences；允许的
  退出/重开仍核对原请求，不能变成再次提交。换任务不串选择、权限、核对或结果。
- [ ] **加载/失败：** 读取中到正文稳定，缺失/拒绝/读失败可辨且保留原合法下一步；
  晚到读取不重开旧卡，快速换任务只显示当前任务，同条件刷新不清空可用内容。
- [ ] **可见交互（AC-11）：** 1536×1024 / 390px 长名称、路径、多文件和证据可读，内部
  有界滚动，关闭/必要操作不遮挡，焦点留在卡内并正确返回；背景宽度/滚动稳定，进出与
  自动化/存储协调，reduced-motion 可用。截图与动态操作共同验收。
- [ ] B 完成适用完整 T4 与真实入口验收后才 PASS。共享呈现若受影响，存储/自动化已接受
  旅程保持；RBAC、显式破坏性意图、独立结果、核对和成功/未知效果非重放保持。

## Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。使用既有隔离 harness、临时
SQLite/Local 根及合成 Provider；从真实 UI/已实现链路进入，只对该链路实际请求注入慢响应/
失败，不构造不存在的入口。场景按风险组合覆盖，不要求全排列。

每轮记录实际工作和测试时间，测试运行墙钟时间须少于本轮实际工作时间的 50%；并行运行
计区间并集。先完成实际代码/旅程审查和用例选择，不靠空等凑比例、不把 B 全回归交给
Developer。可证实阻塞先 FIX REQUIRED；必需门禁未完成不得 PASS。

### Developer — affected tests

在 `web/` 运行：

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/RunLifecycleControls.test.tsx src/features/operations/run-detail-state.test.ts src/shared/navigation/operations-return.test.ts src/features/operations/OperationsRouter.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/operations-inventory.python.spec.ts --grep 'the selected run detail reads|detail tab and filter context|dated views and 21-file|native .*recovery|native Metadata correction|policy-permitted overwrite'
```

覆盖布局/返回、状态与文件结果、证据/导出及真实四类恢复；将新增慢读取、焦点/退出、未知
提交重开用例纳入受影响测试执行。替换旧几何断言，保留有效业务断言。对实际变更文件跑
ESLint/Prettier；仅修改下列生产文件时示例为：

```sh
npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/RunDetailTabs.tsx
npx prettier --check src/features/operations/OperationsLanding.tsx src/features/operations/RunDetailTabs.tsx src/shared/ui/styles.css
```

新增/修改的测试和其他文件同样加入检查。如修改共享 modal，另跑
`npm run test -- run src/shared/ui/modal-card.test.tsx src/features/storage/StorageManagementPage.test.tsx src/features/operations/AutomationCreateDialog.test.tsx`
及 `storage-dialog.python.spec.ts` / `automation-create-dialog.python.spec.ts` 的直接受影响用例。
Developer 不承担完整 Python/Web/E2E 或发布矩阵。

### B — acceptance / full regression

1. 独立审查完整 Task Base..候选 Head，先从真实名称/原精确链接验证关键旅程，含关闭返回、
   五态/文件结果、四类处理、在途/未知后重开。实际阻塞留在同一 Task 修复。
2. 运行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
   的适用完整 T4：Python/Web 全回归/质量、构建、示例、依赖、wheel/源码外消费及适用
   安全用例。Docker/重启矩阵按实际修改和部署合同选择并说明理由/限制；纯前端呈现不
   自动增加生产部署验收。不得用缺少 Developer 全回归作为产品阻塞。
3. `web/` 构建后运行真实 Python 浏览器：

   ```sh
   npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
   ```

   在既有真实 harness 补齐桌面/390px 新详情截图和动态交互，人工检查信息层级、长内容、
   加载/失败、键盘/焦点、reduced-motion；旧八视图截图不能代替新详情验收。
4. 记录精确 SHA、命令/cwd、实际结果/失败/skip、原始日志及视觉证据，放稳定 ignored
   目录或 CI。仅复用自己的匹配执行输入/产物并给出差异证明。
5. PASS 后重评所有 Slice 结果：本草案只覆盖 RO-1；RO-2 和自动化稳定性仍已接受，RO-3
   与 RO-4 切页/库加载仍待交付。不自动规划/实施下一 Task，不提前交 A 终审。

## Non-goals

两种库去树/配置卡片、侧栏主页面切换和库加载另行规划。不新增 Task 状态/恢复、通用重试、
跨 Task 批量操作、引擎/队列/后端/schema、Provider、动画设置或生产部署；不重做其他列表
业务。不以固定像素/毫秒/DOM 结构作为唯一验收，不把可选清理变成阻塞。

## Developer Completion Report

待激活实施后填写：完整 checkpoint SHA、READY FOR B REVIEW、关键变化、实际受影响
测试结果、已知失败/风险和剩余工作。完整验收待 B，不要求完整回归证据册。

## B Review Result

Task50.2 尚无实现候选，本草案不作产品 PASS / FIX REQUIRED 判断。后续须记录完整
Base..Head、实际门禁、阻塞及其用户影响、全部 Slice 结果和下一步。
