# Task 55.1 — 完整移除旧 Web 与迁移入口

Next Action: DEVELOPER STARTS TASK55.1 IMPLEMENTATION。

Authority: committed [Slice55](SLICE.md#ro-1--只有当前-web-入口没有迁移承接) RO-1，
以及 RO-6 中本次 Web 退役所需的消费者／交付物；生命周期与测试分工见
[Development Workflow](docs/development-workflow.md)。

```text
Task ID: 55.1
Task Type: SLICE
Parent Slice: 55
Status: PLANNED
Task Base: d62436be6f5848329a628356c13fdb28e760239a
Difficulty: High
Test Level: T4
Planner: A acting for B — explicit user authorization, planning only
Reviewer: B — independent implementation review pending
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

待 Developer 实施。完成本 Task 和 affected tests，提交不可变检查点并交接
READY FOR B REVIEW；报告变更、实际结果、剩余问题。Implementation Head 尚未产生。

## B Review Result

待 Developer 检查点；尚无审查结论。B 验收后重评 Slice 全部结果；本 Task 覆盖 RO-1，
其余 RO 尚待后续连贯 Task。A 代 B 规划不构成 B 验收或 A 终审。

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
