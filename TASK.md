# Task 55.1 — 完整移除旧 Web 与迁移入口

Next Action: DEVELOPER SYNCS CURRENT NATIVE TEST CONSUMERS; B COMPLETES RELEASE-SECURITY EVIDENCE。

Authority: committed [Slice55](SLICE.md#ro-1--只有当前-web-入口没有迁移承接) RO-1，
以及 RO-6 中本次 Web 退役所需的消费者／交付物；生命周期与测试分工见
[Development Workflow](docs/development-workflow.md)。

```text
Task ID: 55.1
Task Type: SLICE
Parent Slice: 55
Status: FIX REQUIRED
Task Base: d62436be6f5848329a628356c13fdb28e760239a
Difficulty: High
Test Level: T4
Planner: A acting for B — explicit user authorization, planning only
Reviewer: B — B55.1-01 corrected; B55.1-02 acceptance incomplete
Implementation Authorization: AUTHORIZED BY USER — TASK55.1 ONLY
```

规划前治理 PASS；仓库 `/Users/songzhidong/mediaflow`，分支 main，上述 Task Base 为已提交
ACTIVE 合同检查点，工作区干净、Git／文档可写；无前置脏文件。Slice Base 仍为
`2b2e7c1824fa5681864455714d0f97b26555c7dc`，Implementation Head NOT SET。
A 代 B 的角色例外仅适用于这次规划，后续审查按工作流执行。

用户于 2026-11-15 要求“激活Task”，本 Task 据此成为正式实施 Task。激活前 HEAD 为
`719004df2ef62d54b8a82f27434329ab14167ca8`，分支 main、工作区干净，治理检查 PASS。
Task ID、Base、目标、范围、验收和测试分工沿用已提交规划；Status 为 PLANNED，
Developer 开始实际实施时转为 IN PROGRESS。

## Goal

当前 V2 成为唯一 Web 产品：用户从九个主页面和正式深链完成既有操作；V1 页面及旧地址
承接从源码、路由、静态资源、导航、测试消费者和构建产物中退出。
对应 `V2-RETIRE-001/009/010`、Slice AC-01，以及 AC-08/11/12 的 Web 部分。
适用旅程为 [TARGET](docs/product-experience.md#target--complete-v1-and-migration-residue-retirement-slice55-active)、
[Entry](docs/product-experience.md#readable-actions-and-entry)、
[首次设置](docs/product-experience.md#first-time-setup)、
[当前 Web／Task Center](docs/product-experience.md#v2-operator-web-migration)；共享认证、
`V2-AUTH-*`、`V2-SAFE-*`、`REQ-SAFE-005` 和当前设置／规则／任务旅程继续适用。

完整旅程：打开当前地址 → 认证并看到对应页面／弹卡 → 执行原有合法动作 → 看到原结果，
读取失败／权限变化时按原上下文恢复。打开旧地址 → 普通 not-found（适用时普通认证）
→ 用户主动选择当前导航；访问本身不转换意图、不建立工作。SPA 可返回入口文档，
浏览器最终必须显示通用未找到。旧 `tab=settings` 与其他未知 tab 按相同规则处理，
自动化保留当前列表，不专门跳往系统设置。

现状已核对：`operator_ui.py` 仍提供四项 V1 静态资源，API 直接分派；Router 仍注册
MigrationPage、RetiredLibraryRoute、四个 LegacyTask/Job 页面和旧自动化新建入口；
导航仍有 `migration`／`v1Path`、旧地址／查询白名单，AutomationListPage 仍处理 settings
跳转。19 个 Python 测试文件直接消费旧 UI；Node 假服务、浏览器用例和 Docker probes
仍要求旧页面存在。这些依赖作为同一 Web 退役结果处理。

## Implementation Scope

1. **删除 V1 静态产品。** 删除 `mediaflow/interfaces/operator_ui.py`，移除
   `service_api.py` 的导入、ASSETS 分派及仅供 V1 使用的静态安全头分支。
   当前 `v2_ui.py`、生产资产读取和当前 CSP／安全头继续工作；共用代码按实际调用保留。
   `/ui`、`/ui/`、`/ui/app.js`、`/ui/style.css` 及其查询／其他 method 使用普通未知路由，
   不新增重定向、说明页、开关或专用拒绝处理。
2. **删除旧 V2 页面与接线。** 清除 `web/src/routes/router.tsx` 中 `/review` 及以下
   七条路由和专属组件：`/library`、`/library/files`、`/operations/tasks`、
   `/operations/tasks/$taskId`、`/operations/jobs`、`/operations/jobs/$jobId`、
   `/operations/automation/new`。删除 MigrationPage、RetiredLibraryRoute、
   LegacyTaskRoutes 及专属依赖；当前仍使用的 API client／业务服务保留其当前职责。
3. **收敛导航与认证续转。** 从 `destination-model.ts`、相关类型／标题／导航和查询
   allowlist 删除上述身份、`v1Path`／`migration` 模型及旧 Task/Job 解析承接；移除
   AutomationListPage 的 `tab=settings` effect 和专属白名单。清除已退役
   definition/editor/execution/new-organize 的残余专用接线；未知地址统一走当前
   not-found。系统设置标为真实已实现能力。保留当前 lifecycle 新建／编辑、规则 Edit、
   `/operations?run=…`＋hosted-card、两种库和通知等正式地址与必要来源返回参数。
   同步 AppShell 的旧路径判断，以及 AutomationInventory／AutomationListPage／
   AutomationRunOncePage／OperationsLanding 仍生成旧 Task 地址的动作：使用动作已知的
   当前 Task／item 及经核对的运行身份进入正式上下文，保留来源返回；复用必要当前读取，
   不靠旧 URL resolver 转跳。两种库删除弹卡的引用纠正动作接到当前整理规则等实际管理
   入口，保留引用说明和返回，不能删掉纠正按钮来消除 `/review` 链接。
4. **同步当前消费者和说明。** 清除旧 UI 专属测试、假服务分支、夹具、源码导入及清单
   要求；将仍适用的业务／安全断言接到当前链路。至少核对下列 Python 消费者和
   Router/AuthBoundary/destination-model、AutomationSettings、OperationsRouter、
   MediaLibraryFilesPage 测试，以及 deep-link／operations／operations-inventory／
   action-readability E2E。修正四个 Docker smoke 脚本的旧 UI 探针：smoke、
   restart_fault、release_security、upgrade_recovery；本次只处理其 Web 探针，
   后续升级工具退出仍归 Slice RO-4/6。当前 README／部署／配置说明中的 Web 入口和
   安全头描述同步准确，TARGET／历史接受身份按原文档职责保留。
5. **验证唯一当前入口。** 在现有单元／E2E 和真实 Python harness 上补齐下列验收，
   使用构建后资产；不另造演示壳。为新增原生用例统一使用 `Task55.1` 标题前缀，
   复用 `operations-inventory.python.spec.ts`，让受影响原生用例可独立运行。

## Acceptance Criteria

- [ ] AC-1：四项 V1 URL 在有效配置下、匿名／有效身份、GET／其他 method／带查询时，
      与任意同级未知地址一致；无 V1 HTML/JS/CSS、redirect、迁移页或专用拒绝。
      静态／未知路径不读业务库、不访问 Provider／Storage、不建 Task 或发布配置。
- [ ] AC-2：`/review` 与七条旧 V2 路由的直达、刷新、带旧 query、浏览器返回和连接／
      重认证最终使用普通 not-found／认证行为；不查询旧身份映射、不导航到推测的当前
      Task／库／自动化表单，不生成新意图。注销路由与浏览器可见结果均有验证。
- [ ] AC-3：`tab=settings` 没有专用识别、白名单或跳转，其表现等同未知 tab；系统设置
      从正式 `/configuration` 入口可达。导航和认证续转仅保留当前正式目的地，删除
      `migration`、`v1Path` 及专属 resolver；没有孤立链接、残余导入或隐藏页。
- [ ] AC-4：当前九页导航、首次 Draft／空 Active、规则 Add/Copy/Edit、自动化 lifecycle
      新建／编辑和 Run once、Task run＋hosted-card、两种库与通知入口保持可用。
      当前“查看任务”／关联分析／引用纠正动作生成正式地址，进入对应真实记录或规则，
      没有当前按钮通往已删除路由。正式深链的刷新／认证、弹卡关闭／后退、原来源输入／
      位置和未知提交核对保持。
      viewer／401／403、迟到读取和切换身份仍按当前契约处理，凭据仅存内存。
- [ ] AC-5：Python 当前静态安全头、固定 TMDB 图片来源限制、资源类型／路径穿越／
      缺失资产拒绝和 API RBAC 保持；旧 UI 安全断言中仍适用的内容由当前响应验证。
      删除旧正向展示测试不减少当前业务、权限、零变更和安全断言。
- [ ] AC-6：新构建浏览器、wheel／源码外安装及候选镜像均无 operator_ui 模块／旧静态
      产品，HTTP 结果与源码一致；当前 V2 资产、health 和四服务重启 smoke 通过。
      更新后的部署／安全探针不再要求 V1 存在。
- [ ] AC-7：桌面、390px 和矮窗口实际检查旧内容移除后的入口、not-found、导航与代表性
      正式弹卡；文字／键盘焦点／关闭／返回可用。既有业务数据、正式配置键／权限名、
      数据库结构和 Task 执行状态维持本 Task Base 的契约。

## Required Tests

测试归属遵循 [工作流 §6](docs/development-workflow.md#6-test-levels)。本 Task 涉及共享
API 静态安全头及认证续转白名单，采用 T4；Developer 跑受影响测试，B 负责完整门禁。
所有运行使用示例／本地 fake 和临时根；证据保存在忽略目录或 CI。

### Developer — affected tests

仓库根执行治理、上述删除影响到的 Python 模块及修改过的脚本测试。下面 18 个保留的
Python 消费者须完成旧 UI 解耦；`test_operator_ui.py` 的专属展示测试随产品退出，
仍适用断言落在当前测试，新增测试同样执行：

```sh
.venv/bin/python scripts/check_governance.py
for case in test_automation_task_definition test_configuration_package_exchange \
  test_configuration_snapshot test_configuration_status test_configuration_successor_draft \
  test_guided_storage_lifecycle test_management_setup test_notification_delivery_management \
  test_operational_logging test_phase21_closure test_processing_checkpoint \
  test_runtime_files_browser test_storage_browser test_storage_setup_check \
  test_system_settings_management test_v2_ui test_webhook_management test_webhook_url_security; do
  .venv/bin/python -m unittest discover -s tests -p "$case.py" || exit 1
done
.venv/bin/python -m unittest discover -s tests -p test_release_security.py
git diff --check
```

Python 的 Ruff format/check 和脚本 consumer 测试只跑本轮新增／修改文件；删除文件不传
给检查器。新测试／新增直接调用者按同样命令补入，不把全仓测试改称 affected。

`web/` 执行下面受影响用例；若某文件随专属产品删除，把仍适用断言迁入当前测试后执行：

```sh
npm run typecheck
npm run test -- run src/routes/router.test.tsx \
  src/shared/auth/AuthBoundary.test.tsx src/shared/navigation/destination-model.test.ts \
  src/shared/ui/AppShell.test.tsx \
  src/features/operations/OperationsRouter.test.tsx \
  src/features/operations/AutomationSettingsPage.test.tsx \
  src/features/operations/AutomationRunOncePage.test.tsx \
  src/features/library/MediaLibraryFilesPage.test.tsx
npm run build
npm run test:e2e -- tests/e2e/deep-link.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/operations-inventory.python.spec.ts --grep 'Task55\.1|retired Task collections'
npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/action-readability.python.spec.ts --grep 'Entry and representative business/dialog actions'
```

同时跑实际修改的其余 Web test 文件，并用 `npx eslint <changed-files>`、
`npx prettier --check <changed-files>` 检查本轮 Web 文件。以真实 API＋SQLite、当前
构建资产验证注销路径与正式入口；无需等待 B 的全量／Docker 验收即可交接。

### B — acceptance and full regression

审查不可变 Task Base..candidate，重现 AC-1–7，执行
[shared full gates](docs/development-workflow.md#shared-full-regression-commands) 的 T4 全量
Python／Web／Node E2E、质量、示例与安全检查。旧断言的每处删除应能对应产品退出，
或指出当前链路承担其保留义务。RO-2–5 的其他兼容尚在时按本 Task 边界记录。

补充真实原生／产物命令（精确 wheel、image 及检查点写入实际报告）：

```sh
# cwd web/; serial, after npm run build
npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/operations-inventory.python.spec.ts tests/e2e/action-readability.python.spec.ts
# cwd repository root
.venv/bin/python scripts/storage_settings_browser_proof.py
.venv/bin/python -m pip wheel . --no-deps -w dist
.venv/bin/python scripts/wheel_smoke_test.py <exact-candidate-wheel>
docker build -t mediaflow:slice55-task55.1 .
.venv/bin/python scripts/docker_smoke_test.py --image mediaflow:slice55-task55.1
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image mediaflow:slice55-task55.1
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:slice55-task55.1
```

在精确 wheel ZIP 清单及源码外隔离安装中检查 `mediaflow.interfaces.operator_ui` 不存在，
从安装产物请求旧四路径／当前 V2／API；候选镜像重复入口核对。若实际改动包含其他
受 Web 静态边界影响的 harness／probe，B 运行其直接消费者；升级机制最终退役的矩阵
在后续 RO-4 Task 执行。以当前原生九页和正式深链检查 AC-4，包含真实状态、失败／恢复
和桌面 1536×1024、390×844、矮窗口 1280×600 的键盘／返回检查；无需重设计页面。
完整门禁由 B 记录实际结果、失败／跳过与证据身份。

## Non-goals

本 Task 完成 RO-1 和直接相关的 Web 消费者／产物，不处理 schedules／执行票据／grant、
旧 API／CLI、配置字段／bootstrap、schema／升级机制、非内核 Worker、Pause／恢复链、
领域响应／session 格式清理；这些仍按 Slice 其余结果推进。
现有 V2 正式配置键 `automation.maximumActiveJobs`、权限 `CANCEL_JOB/cancel_job`、
`/api/v1`／`/ui-v2` 和有效 V2 数据／pins 保持；不修改数据库或执行引擎。

## Developer Completion Report

Developer 已完成 Task55.1 affected implementation 并交接 READY FOR B REVIEW。

```text
Implementation candidate: 87387e24
Task Base: d62436be6f5848329a628356c13fdb28e760239a
Reviewer: B
```

**变更**

- 删除 `mediaflow/interfaces/operator_ui.py`、`tests/test_operator_ui.py`、V1 ASSETS 导入／
  静态分派及 V1 专用 CSP 默认分支；`/ui`、`/ui/`、`/ui/app.js`、`/ui/style.css` 及其查询／
  其他 method 现为普通 404。`/ui-v2/` 生产资产、固定 TMDB `img-src`、路径穿越／缺失资产
  拒绝和 API RBAC 保持。
- 删除 `/review`、旧 `/library`、`/library/files`、`/operations/tasks[/:id]`、
  `/operations/jobs[/:id]`、`/operations/automation/new` 路由及 MigrationPage、
  RetiredLibraryRoute、LegacyTaskRoutes、未再使用的 OrganizeNewPage；旧地址无别名、重定向、
  说明壳或身份解析，按普通 not-found／认证边界处理。
- 收敛 destination model／标题／Shell 判断／认证续转 allowlist：移除 `migration`、
  `v1Path`、旧 Task/Job 分支和 `settings` tab token；`tab=settings` 与任意未知 tab 相同。
  自动化 admitted “查看任务” 改到 `/operations?run=<Task>`，关联分析保留 `item` 与
  `returnOps`，两种库引用纠正改到当前 `/rules`；当前 lifecycle、规则 Edit、
  `/operations?run=`＋hosted-card、两种库和通知地址保持。
- API 中 Automation `definitionSettings`／`supportedCommandPath` 的旧 definition 地址
  改到当前 lifecycle 地址；Web fixture 同步。删除 Node 假服务 V1 `/ui` 分支，更新四个
  Docker smoke 的 Web 探针为当前 V2 入口＋旧 `/ui` 404。
- README／部署／配置说明同步当前唯一 `/ui-v2/` 入口、旧 `/ui` 普通 unknown 和当前静态
  安全头描述；构建入口 title 去掉 migration 字样。

**实际验证**

- 治理：`.venv/bin/python scripts/check_governance.py` PASS；`git diff --check` PASS。
- Python affected：`test_automation_task_definition`、`test_configuration_package_exchange`、
  `test_configuration_snapshot`、`test_configuration_status`、
  `test_configuration_successor_draft`、`test_guided_storage_lifecycle`、`test_management_setup`、
  `test_notification_delivery_management`、`test_operational_logging`、`test_phase21_closure`、
  `test_processing_checkpoint`、`test_runtime_files_browser`、`test_storage_browser`、
  `test_storage_setup_check`、`test_system_settings_management`、`test_v2_ui`、
  `test_webhook_management`、`test_webhook_url_security`、`test_release_security`：
  **218 项通过**。`ruff format`／`ruff check` 对本轮修改 Python 文件通过；
  `compileall -q mediaflow tests scripts` 通过。
- Web unit：13 个受影响文件（router、AuthBoundary、destination-model、AppShell、
  OperationsRouter、OperationsInventory、RunDetailTabs、AutomationSettingsPage、
  AutomationRunOncePage、AutomationRouter、AutomationListRunOnce、MediaLibraryFilesPage、
  MediaLibraryConfigDialogs）**280 项通过**；`npm run typecheck`、`npm run build` 通过；
  修改文件 ESLint／Prettier 通过。
- Browser：built 资产＋Node fake 的 `deep-link`／`operations` **42 项通过**，另
  `automation`／`medialib-config`／`medialib-transfers`／`library-files` **86 项通过**；
  真实 Python harness 的新增 `Task55.1` 原生用例 **2 项通过**（含 `/ui` 四路径 404、
  `/review`／Library／Task／Job／旧 Automation／旧 Organize 直达＋reload＋back、当前库／
  系统设置入口、`tab=settings` 未知 tab 行为）；action-readability 代表动作 **1 项通过**；
  automation run-once 列表 admitted 跳转 **1 项通过**。
- Packaging：清理生成的忽略 `build/` 后重建 wheel（`mediaflow-2.0.0.dev0-py3-none-any.whl`，
  SHA-256 `db8089a3df20eb02846e29f6b7e6f39d78a4728edb0d5f8571a59304259e324a`），ZIP 内
  不含 `operator_ui`；`scripts/wheel_smoke_test.py` 对精确 wheel **PASS**，schema 58、
  migration required NO、restore/verify/upgrade preflight 通过。
- 构建资产扫描未发现旧 `/ui/app.js`、`operator_ui` 或迁移页文案。

**剩余风险／未执行**

- 未运行 Docker build 及四服务 smoke／restart／release-security／upgrade-recovery；四个脚本
  已按本 Task Web 范围更新，但镜像和真实部署矩阵由 B 执行。
- 未运行完整 Python／Web／E2E 回归、完整真实原生 spec 或全站视觉矩阵；B 按 T4 门禁执行。
  AC-7 的 1536×1024 与 390×844 由 action-readability 自动覆盖，1280×600 矮窗口未单独人工
  检查；旧地址的移动端 not-found 视觉也未单独人工检查。
- 首次 wheel 构建发现本机未跟踪的 `build/lib` 仍残留已删除模块；删除该生成目录后重建才
  得到干净 wheel。干净 checkout／CI 不包含该目录，B 应从干净候选或先清理生成目录构建。
- `definitionSettings`／`supportedCommandPath` 的字符串改动只由 Web fixture 和完整构建消费；
  Python 侧没有单独断言该 URL 字符串，B 可随自动化 journey 一并复核。
- 未推送、未发布、未操作运行库或用户媒体。


## B Review Result

**FIX REQUIRED — 2026-11-16，B55.1-01（P1，AC-4 未完成）。**

```text
Review Base: d62436be6f5848329a628356c13fdb28e760239a
Implementation candidate: 87387e24fa5165fb9dbc975c2a4ac4816c8b822b
Reviewed Head: b8909f6ad770dea94f161fb88f450492326d08f9
Branch: main
Initial workspace: clean
```

审查以整个 Base..Head 的变更清单、产品代码、删除的旧页面／测试、路由消费者、部署探针
及文档为范围。旧静态分派与指定 Router 注册已删除，当前任务按钮改接正式 run 地址。
本轮发现下列必需结果未完成，按工作流 §6 提前返工，不开展下一 Task。

### B55.1-01 — 资源库的自动化引用没有对应的纠正入口

真实已有旅程：文件 → 选择资源库 → 资源库操作 → 删除资源库。当前删除预览会列出
recognitionRules 和 automationTaskDefinitions 引用。候选把唯一“前往整理规则处理这些引用”
按钮接到 `/rules`；该页只有七类规则和概览，不能编辑自动化定义。

复现使用现有 `scripts/operations_inventory_harness.py --port 4183`、真实 API／SQLite 与
本轮构建资产，未添加入口或修改种子数据。选择 `Unified media source` 后，弹窗列出
8 个识别规则及 `harness-scheduled`、`harness-continuation` 两个自动化定义；点击纠正按钮
进入整理规则页，自动化引用仍无法在该目标处理。删除仍被正确阻止、资源库及文件未删除。

这是本 Task 明确要求的“引用纠正动作接到实际管理入口”未完成。修复留在 Task55.1，
不调整 Slice、数据库、配置发布或删除权限。

### Developer correction guidance

1. 从 `DeleteResourceLibraryDialog.tsx` 现有 `preview.references.items[].section` 出发，
   给实际引用种类提供对应管理动作：识别规则进入现有整理规则，自动化定义进入现有
   自动化管理入口。混合引用同时提供两类可理解的动作和原引用说明；不要把全部引用
   继续交给同一个规则按钮。复用已存在的 Router／列表／编辑卡，不新增管理页或转换入口。
2. 保持原删除禁止条件和关闭行为，返回文件页仍能找到原资源库／路径。媒体库的分类
   引用继续使用整理规则入口，不扩成删除流程重构。
3. 在现有资源库删除弹窗测试／`library-files.spec.ts` 中覆盖只含规则、只含自动化和混合
   引用；验证动作进入能管理该引用的当前页面，返回保留来源，访问不提交配置或删除命令。
   至少一条使用真实 Python harness 的现有混合引用完成相同旅程。不能只断言 `/rules`
   地址或标题出现就认为所有引用都可纠正。
4. Developer 运行修改组件及直接消费者测试、该原生用例、typecheck、build 和修改文件
   lint／format；无需代 B 跑全量或 Docker。记录实际结果并提交新的不可变检查点，回到
   READY FOR B REVIEW。Task ID、Base、Difficulty High／T4、原验收保持。

### B actual validation and remaining gates

证据目录（本地、Git 忽略）：`.git/validation-evidence/b8909f6a/b-review/`。

- `python3 scripts/check_governance.py` 与 `git diff --check` PASS。
- `web/ npm run build` PASS，日志 `build.log`。
- `web/ npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts --grep 'Task55\.1|retired Task collections'`
  **2 passed (3.9s)**，日志 `native.log`。
- 现有浏览器入口的独立引用纠正复现完成；`reference-journey.log`、
  `resource-references.png`、`wrong-recovery-destination.png` 保存了可见引用和目标页。
  已查看截图，未使用猜测请求或不可触发输入。
- 已启动完整 Python unittest 和 Web unit；发现上述阻塞后主动中止（exit 130），
  `python.log`／`web-unit.log` 只是未完成运行，**没有全量通过结论**。
  Python 中止时的 KeyboardInterrupt 是人工停止，不能视为产品失败。
- `docker info` 无法连接 `/var/run/docker.sock`；`colima status/list` 显示已有本地环境停止。
  本轮未构建镜像或启动部署，Docker／restart／release-security 验收仍由 B 补齐，
  不是交给 Developer 的产品返工项。
- 其余 T4 质量、全量 E2E、完整原生／三种视口和 wheel／源码外安装门禁尚未完成；
  不复用 Developer 报告冒充 B 验收。本轮先读代码／旅程再做定向复现，发现阻塞即停止
  全量测试，测试运行墙钟小于本轮总耗时的一半。

### Slice outcome reassessment

RO-1 的旧入口移除已有代码和定向实证，但现行引用纠正旅程未完成，尚不接受；RO-6
的 Web 消费者／交付物已改动，完整产物与门禁待验收。RO-2 旧业务入口／执行、RO-3
严格当前配置、RO-4 schema／五态残留、RO-5 session／响应收敛不属于本 Task，仍待后续
实现。本 Slice 维持 ACTIVE；不填写 Closure Packet，不声明 PASS／CLOSED，不规划下一 Task。

## Developer Completion Report — B55.1-01 修正（2026-11-16）

Status: READY FOR B REVIEW。

```text
Implementation candidate: ca9deea647ac3542e47ddbe12eda469c49e1793e
Final test head: 52c50e8ef704b1dfaaa6be0309fe9f7fa7082853
Task Base: d62436be6f5848329a628356c13fdb28e760239a
Reviewer: B — B55.1-01
```

**变更**

- `DeleteResourceLibraryDialog.tsx` 按 `preview.references.items[].section` 识别当前实际
  引用种类，并给每种已知引用提供对应管理动作：识别规则进入
  `/rules?section=recognitionRules`（当前识别规则清单，可直接编辑被引用规则）；自动化
  定义进入 `/operations/automation`（当前自动化清单，可从行内“编辑”进入现有编辑卡）。
  混合引用同时显示两个动作；引用列表继续显示中文种类与对象 ID。
- 引用证据被截断时同时提供两个管理入口并明确“仅显示前 N 项”，不根据可见前缀猜测；
  删除按钮仍按原引用总数、Active 预览、停用状态和版本匹配条件阻止删除。取消／关闭行为
  未改，动作先关闭弹窗再进入当前页面，浏览器返回仍回到原 Files 地址与原资源库／路径。
- 未新增管理页、转换入口、重定向或后端读取；媒体库的分类引用继续使用原整理规则入口，
  删除流程、权限、配置发布和数据库均未改动。
- Node 假服务新增只含规则／只含自动化／混合引用的 session 预览模式；单元测试覆盖三类
  引用与截断证据；`library-files.spec.ts` 覆盖两个明确动作、进入真实当前页面（规则清单
  / 自动化行编辑入口）、浏览器返回来源，并断言整个访问没有非 GET API 命令。真实 Python
  harness 的 `Task55.1` 用例使用现有 8 个规则＋2 个自动化定义混合引用完成同一旅程。

**实际验证**

- `npm run typecheck` PASS；`npm run build` PASS（`dist/index.html`、
  `index-Cvv7FA31.css`、`index-Byllywp2.js`）。
- `npm run test -- run src/features/library/StorageFilesPage.test.tsx`：**66 项通过**
  （7.69s）。
- `npm run test:e2e -- tests/e2e/library-files.spec.ts`：**51 项通过**（38.1s）。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts --grep 'Task55\.1|retired Task collections'`：
  **3 项通过**（3.4s，最终 test head `52c50e8e`），包含新增真实混合引用旅程；
  两处返回点均重新核对 `resourceLibraryId=source` 与原路径 `/`。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/action-readability.python.spec.ts --grep 'Entry and representative business/dialog actions'`：
  **1 项通过**（12.0s）。
- 修改文件 ESLint／Prettier、`git diff --check`、`python3 scripts/check_governance.py`
  均 PASS。定向测试墙钟约 2 分钟，低于本轮总耗时 30%。

**剩余风险／未执行**

- 未运行完整 Python／Web／E2E、Docker 镜像与四服务 smoke、wheel／源码外安装和完整视觉
  矩阵；这些仍由 B 按 T4 门禁执行，本轮结果不能替代 B 接受。
- 引用证据截断时显示两个入口是明确的产品选择：后端当前只可能产生这两类资源库引用，
  但截断前缀不能证明隐藏引用的种类；该情况下双方都给出入口并保留总数与截断说明。
- 未修改后端、数据库、权限、配置发布、Task 执行或用户数据；未推送、发布或部署。

## B correction review — 2026-11-16

**FIX REQUIRED — B55.1-02：当前消费者同步及必需验收未完成。**
原 B55.1-01 已修复；本轮没有确认新的产品回归，不把既有测试失败描述成产品故障。

```text
Review Base: d62436be6f5848329a628356c13fdb28e760239a
Product correction: ca9deea647ac3542e47ddbe12eda469c49e1793e
Final implementation/test Head: 52c50e8ef704b1dfaaa6be0309fe9f7fa7082853
Reviewed Head: f156c51fdbcb32de95707bea94e82d75fa01161b
Branch: main
Initial workspace: clean
Evidence: .git/validation-evidence/f156c51f/b-review/ (local, ignored)
```

已独立审查完整 Base..Head 的 71 文件变更，包括旧页面／测试删除、当前生产者、路由、
安全头、消费者及交付探针。真实已有“文件 → Unified media source → 资源库操作 →
删除资源库”列出 8 个识别规则和 2 个自动化定义，两类纠正动作分别进入当前规则清单和
自动化管理；返回保留 resourceLibraryId=source 和原路径，访问没有提交写命令。
桌面、390×844、1280×600 截图已实际查看；矮窗可滚动到动作，键盘聚焦取消和 Escape
关闭可用；旧 Task 地址在窄／矮窗显示普通 not-found，可主动返回当前导航。

### Remaining acceptance blockers and Developer guidance

1. **当前浏览器测试消费者仍依赖旧界面。** 完整原生两个 spec 为 51 passed / 3 failed。
   用 Base 自身源码、构建资产、Python harness 重跑这三例，三例在相同位置失败，故不是
   Task55.1 新引入。它们属于本 Task 明确要求核对的消费者，当前断言尚不能证明完整旅程：
   - 设置 → 高级配置 → 当前 JSON → 导出脱敏包：测试仍点击已不存在的“查看 Active JSON”。
   - 通知 → 查看事件与定义 → 编辑 Draft：测试仍等待英文 Notifications heading。
   - Task 完成 → 通知投递列表 → 对应投递详情：测试仍点击旧 Open deliveries 链接。
   Developer 仅同步这三个现有用例到实际当前入口和中文文案，走完各自后续步骤；保留
   export 请求挂起期间的 disabled／可读性、真实 task.* 事件／Draft 与编辑入口边界、唯一
   outbox 投递／详情及 Task 不重放等原业务断言。不要只改第一个定位器便交接，不删除
   用例、不改生产界面迎合旧断言、不加重试或延长超时。执行这三个定向用例和修改文件
   ESLint／Prettier、typecheck；提交同 Task 的测试消费者检查点。完整原生回归仍由 B 跑。
2. **release-security 必需门禁未完成，由 B 负责。** 候选在手工整理 choice 返回
   metadata_unverified／rejected_without_mutation；Base 精确源码镜像也同样失败。
   脚本只 seed PersistentResultRecord，而当前 choice 的来源身份由 evidence／review／
   preview 提供；因此尚未到达“确认整理 → 常驻 Worker 执行 → 导出与日志脱敏”的后半程。
   这不是已证明的权限或整理产品缺陷，不要求 Developer 修改身份校验或扩张本次 Web
   实施。B 继续用现有当前来源证据完成夹具核对和安全验收，保留本轮原始失败日志；
   不将尚未执行的后半程算作通过。

Task ID／Base／目标／High／T4 不变，不开始下一 Task。`docs/configuration.md` 仍有
旧 tab=settings 会跳转的事实文案，可随当前 Web 说明同步；该文案不是独立产品阻塞。

### Actual validation

- 全量 Python unittest：2630 tests，OK，7 skipped；Web unit：103 文件／1655 passed；
  Node E2E：285 passed。日志分别为 python-full.log、web-unit.log、node-e2e.log。
- 治理、Ruff format/check、compileall、pip check、两个示例 config validate、Web
  typecheck/lint/format/build 均通过；禁止依赖搜索无匹配。见 quality-results.json。
- 真实 Python 定向 Task55.1 3 passed；完整两个原生 spec 51 passed / 3 failed，
  native-full.log／native-artifacts 保留原始失败；Base 对照见 base-native.log／
  base-native-artifacts。storage_settings_browser_proof.py PASS。
- 从 git archive 候选构建 wheel，SHA256
  88ee454521baf393fa06fc834b5c501b7506b1923383fbdbf03cefe50a4427e2；wheel smoke PASS。
  ZIP／源码外隔离安装无 operator_ui；安装后真实 HTTP 四个旧路径均 404，当前 V2 200，
  API 匿名 401（wheel-http-final.log）。V2 资产为本候选构建后复制到安装目录外配置根。
- Docker 候选 mediaflow:slice55-task55.1，首次构建 image ID
  sha256:62c72aa9fffa0c44478734fc55476c4b85ab5a206b809b86aab06c9833dcc485；
  镜像无 operator_ui，四服务 smoke／API 重启及 restart-fault PASS。
  release-security FAIL 如上，不能写成整个 Docker 矩阵通过。
- Docker 使用已有 colima-mediaflow-review context 与其已挂载的隔离临时目录；早期
  socket／挂载错误不是产品故障。Base 首次探测的归档引用不正确，结果未用于归因；
  base-docker-security-exact.log 才是明确归档 Task Base 的对照结果。
  源码外 HTTP 初次探针的构造器／空 repository 错误也已纠正，原日志保留。
- 当前截图见 references-desktop/narrow/short/short-scrolled.png、retired-narrow/short.png。
  本轮浏览器和临时 4185 服务已关闭。未推送、发布或操作用户运行库／媒体。
- 可计时测试命令并行区间去重约 588 秒（timing.json），另有短暂人工交互和质量检查；
  测试服务等待期间不计为测试运行。总复核在首个 00:54 构建日志前已开始，至 01:24
  后仍在审查／记录，测试时间低于本轮总耗时的 50%。

### All Slice outcomes reassessed

RO-1 的产品退役和引用纠正已有实证；Task 的当前消费者／必需门禁仍待完成，尚不 PASS。
RO-2 旧业务入口／执行、RO-3 当前配置、RO-4 schema／五态和 RO-5 session／响应收敛
均仍待后续实现；RO-6 仅 Web 部分已交付，安全门禁及 Slice 其余消费者仍未全部完成。
Slice55 保持 ACTIVE，Roadmap／Progress 不变，不提交 Closure Packet 或声明 Slice 关闭。

## Latest accepted Task — PATCH-20261115-1

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: B PASS — 2026-11-15
Task Base: d5803682ac3e37cae6d46f3064c4cf252dc8aa30
Product implementation Head: 6947b0f2f417aca68cf99c7634d288978386a0e2
Final implementation / test Head: 5c40583f4b2e558b522ca11d1f87e4d798e1b073
Reviewed Handoff Head: 8ba01d676bb47ae37966e639265d87959afb8395
Acceptance checkpoint: 8c09f276409be2cf969ccd8d037bf083312c2d32
Remaining blockers: NONE
```

设置页现为单一中文标题、紧凑状态与运行参数优先；高级设置按类型分组，按组保存／放弃，
默认精确 Active JSON，规则／命令和技术标识移入诊断。高级日志修改可仅从网页完成
草稿→验证→适用只读检查→失败纠正→checked 激活；首次设置／来源返回、输入、并发、
未知写入不重放及发布／实际采用的区分保持。所有授权验收项已逐项重评满足。

B 独立审查完整 Base..交接 Head。最终 Node E2E **286 项通过**；原失败用例独立通过，
变更 spec 的 ESLint／Prettier 与完整类型检查通过。经源码／夹具／依赖与资产身份核对，
复用 B 上轮 Python 2692 项（2685 通过、7 项既有外部／耐久测试跳过）、Web 103 文件／
1635 项、真实 Python 设置 18 项、首次设置／返回、三视口视觉／键盘，以及质量、示例、
构建、wheel 和源目录外安装结果。Docker 镜像／线上部署未执行；本次未改相关边界。

完整规划、开发指导、历次 FIX、最终逐项验收、命令与限制见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/8c09f276409be2cf969ccd8d037bf083312c2d32/TASK.md#patch-20261115-1--b-pass)。
原始失败、截图、trace、资产／wheel digest 和复用身份在本机忽略目录
`.git/validation-evidence/patch-20261115-1/b-round3/` 与 `b-round4/`，未上传远程 CI。
当前操作说明见 [System Settings Web](docs/configuration.md#system-settings-web)。

依 [Development Workflow](docs/development-workflow.md) §3.1 恢复本指针，详细历史留于 Git。
SLICE54 保持原 PASS / CLOSED，SLICE／Roadmap／Progress 及其接受身份未变。
收尾仅同步操作说明与本指针；文档消费者 8 项、治理和 whitespace 检查通过。
接受轮测试／质量命令累计约 221 秒，复核超过 7 分 40 秒，测试时间低于 50%。
上述结果为开发验收，未发布或部署；后续文档治理和 Git 推送不改变接受身份。

## Previous accepted corrections

- PATCH-20261114-3：接受检查点 `4134ea8f6be6ac2de920d25eda56d77fcf800526`。
- PATCH-20261114-2：接受检查点 `7ffe380669e50c46da15982a86e14e54228a38d8`。
- PATCH-20261114-1：接受检查点 `280fc5fdedaf8c079dee52480e1eb4d3bf26449a`。

各 Task 的完整范围、审查与限制继续保留于对应 Git 检查点的 `TASK.md`。
