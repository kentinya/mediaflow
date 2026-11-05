# Task49.2 — 统一自动化创建/编辑卡片与明确启停

Authority: committed [Slice49](SLICE.md) RO-3 / RO-4；生命周期遵循
[开发流程](docs/development-workflow.md)。用户本轮明确要求“激活Task”，B据此将
`7b7e9aaa24684ee59552ca95641843706dc7680d:TASK.md` 中的草案转为正式任务。

```text
Task ID: 49.2
Task Type: SLICE
Parent Slice: 49
Status: FIX REQUIRED
Task Base: efc628cf62b102f689e779bbee7747d88006598d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: USER ACTIVATED TASK49.2; IMPLEMENT ONLY THIS TASK
Next Action: DEVELOPER FIXES B49.2-01/02 IN THIS TASK; B REVIEWS THE NEW CHECKPOINT
```

Task49.1已接受的PASS、精确Base..Head和完整证据保留于
`7b7e9aaa24684ee59552ca95641843706dc7680d:TASK.md`，不重开或改写该结论。
本Task的目标、范围、开发指导、验收及测试分工沿用已审草案，原Base不变。

### Goal / 完整旅程

完成剩余 RO-3 / RO-4、合同 AC-7–13/15–16；保留 Task49.1 已接受的 RO-1 / RO-2
及 AC-1–6/14。对应 `V2-AUTO-013/014`，沿用 `V2-AUTO-002/010–012/015`、
`UX-001–007/010` 和适用安全约束。开发前读完整
[TARGET 旅程](docs/product-experience.md#target--automation-forms-and-direct-run-once-slice49-active)、
[CURRENT 自动化旅程](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
与 [TARGET 技术合同](docs/architecture.md#target--automation-forms-and-direct-run-once-slice49-active)。

操作者从“自动化 → 任务列表”新建，选择来源、计划和上限，默认创建停用定义；明确勾选
“启用自动化任务”时，一次界面提交完成创建并启用。成功返回原列表，提示实际状态，不立即
运行。随后从该行“编辑”打开同一卡片，读取原值，修改或切换启停并保存；再打开仍可继续
修改。取消/放弃/保存保留列表条件、页、滚动和焦点。错误定位字段并保留输入；并发变更
明确重读；丢响应在关闭、刷新、重连后核对原发布，不重复创建/盲目启停。无启用权限仍可
依现有配置权限创建停用定义。

### 实际代码依据与范围

| 已有入口 / 当前结果 | 复用点及本 Task 缺口 |
|---|---|
| 列表新建、`/operations/automation/new`、无 ID lifecycle 已使用中文卡片 | `routes/router.tsx`、`AutomationListPage.tsx`、`AutomationCreateDialog.tsx`；复用目录浏览、计划控件、动画、退出保护和列表返回。 |
| 行“编辑”与详情“Edit saved definition”进入有 ID lifecycle 的英文长页 | `AutomationLifecyclePage.tsx`；接入同一卡片，保留精确回填、不可变 ID 和连续保存。 |
| 详情另有 successor Draft 编辑入口 | `AutomationDetailPage.tsx`、`AutomationEditorPage.tsx`；区分已发布普通编辑与真实 Draft-only/历史，不把未发布内容呈现为 Active，不重做高级 Draft 生命周期。 |
| 创建模型没有 enabled，候选、提交上下文、核对重建固定 false | `automation-create-form.ts` 的 `buildCreateCandidate/publicationFormFromCreateForm/buildCandidateFromPublicationForm`；统一字段/校验和精确候选转换。 |
| focused create 拒绝新定义 enabled=true，已有 edit/enable 可发布启用状态 | `automation_workspace_commands.py:save_object/set_enabled/_publish`；复用后继发布和审计。 |
| 未知发布已绑定主体、动作、候选及基线，create/definition 分开留存 | `automation-publication-session.ts`、后端 `publication_intent`；共用卡片延续实际提交身份与现有未决上下文。 |
| 表单 authority 的动作是固定布尔值，Web 模型只消费 create | `form_authority`、`service_api.py`、`automation-lifecycle.ts`；投影真实主体的创建/编辑/启用权限及原因，命令仍后端权威校验。 |
| 激活链已有 scheduled intent、当前执行权限及作用域审计 | `automation_execution_intent.py:publication_intents`、`_publish` 的 `automation_intent_ids`；创建启用复用相同链路。 |

涉及共享 Web 表单、列表与相关路由/提示，既有 API models/client、focused publication、
权限投影及相应测试/现有原生 harness。无新增 schema、配置库、队列或执行引擎需求。

### 开发指导

1. **共享表单输入输出。** 从创建卡片及纯模型提取字段、校验、目录选择、后端计划预览
   和展示；分别提供创建初始化、已保存回填。创建只生成一次 ID，编辑 ID 不变。
   保存任意合法 Cron/时区、小数间隔与子范围；便利控件只能无损对应原值，不能打开表单
   或只改名称就被默认计划改写。不要复制第二套表单/校验器。
2. **接通真实编辑入口与返回。** 列表编辑、详情普通编辑、有 ID lifecycle 深链/刷新/
   登录续转都进入同一卡片及列表背景；复用受限返回条件、滚动和入口焦点。逐一核对旧
   editor 入口的真实状态：已发布普通编辑归共享卡片，明确 Draft-only/历史能力保持真实。
   复制/删除继续可达且沿用确认/权限；只纠正本次直接相关的旧提示。
3. **完成启用选择与发布。** 创建默认关，选中显示“创建并启用”；编辑回填 enabled 并可
   保存切换。优先利用 `_publish` 已有的原子后继发布与 intent 校验，选最直接的实现；
   合同同样允许安全编排 create/enable，不以命令数量验收。真正创建请求省略 enabled
   仍关闭，非法类型按类型规则拒绝。创建启用与启用编辑均走配置管理/激活、当前
   `GRANT_UNATTENDED_EXECUTION`、引用校验及审计；复制仍关闭。后端投影当前主体
   可用性与原因，不能用隐藏开关替代 API 权限。
4. **完成成功、失败与核对。** 提交精确候选及读到的基线，防连击/意外离开。确认成功
   才更新保存状态与列表；提示真实结果及被筛选掉的原因。再次打开同一定义可继续保存，
   旧响应不覆盖后来输入。拒绝保留输入；同伴并发须明确重读，不自动换基线。
   未知保留原主体/动作/候选/基线，复用只读核对覆盖关闭、重开、刷新、重连与换身份。
   若分步实现，逐步保留实际已提交身份：创建已成功但启用失败/未知要如实显示，先核对
   未知步骤；已证实启用未执行/拒绝后，允许按当前权限/版本明确完成启用，不重新创建。
5. **验证实际消费再移除重复代码。** 创建/保存/浏览/预览不准入 Task 或变更媒体；
   Scheduler 后续 due 按真实主体、范围、权限准入，Worker 保留固定上下文和执行校验。
   从现有入口补正常/拒绝/并发/未知测试，确认消费者已覆盖后移除重复表单；不新造探测
   入口、通用命令框架或无真实触发依据的防御分支。

### Acceptance Criteria

- [ ] **AC1 共用卡片：** 新建/编辑共享中文字段和校验，包含目录浏览、间隔单位、每日/
  每周、Cron/时区、后端近期时间、上限、启用状态及按钮；编辑无“运行一次”。
- [ ] **AC2 入口与回填：** 实际普通编辑链接、lifecycle 深链、刷新、登录续转一致可达；
  ID不变。只改名称保存后，合法任意 Cron（如 `*/7 1-5 * * 1-5`）、1.5秒间隔、中文空格
  子范围及 enabled 保持原语义。Draft-only/历史/不可读不伪装 Active，复制/删除仍可用。
- [ ] **AC3 退出/布局：** 未改直接关，已改可见继续编辑/放弃；取消/放弃/保存保留合法
  列表条件、页、滚动和焦点，筛选掉的结果有解释。桌面和390px无页面溢出，键盘/退出
  选择可达，动画与 reduced-motion 有真实交互及截图证明。
- [ ] **AC4 创建与再编辑：** 开关默认关闭，省略 enabled 创建停用；明确选择一次界面
  提交完成创建并启用。提示“已创建，未启用 / 已创建并启用”依据真实 Active。两种创建
  结果均能再次编辑，启用→停用→启用、保存后再改名称/计划均生效，旧响应不覆盖后来输入。
- [ ] **AC5 权限/非法输入：** 有配置管理/激活但无 scheduled 权限，可创建停用且看见
  不能启用的原因；伪造 true 也不能启用发布。缺配置权限、非法 enabled 类型、无效计划/
  引用拒绝；每个拒绝保留提交前 Active。审计绑定实际主体/候选/来源/版本，无兄弟 Draft
  搭车。复制关闭且不继承授权，权限丢失在真实提交/执行边界生效。
- [ ] **AC6 提交/冲突：** 提交中无重复保存及意外离开；错误定位并保留输入。同伴发布
  冲突后可明确重读/再提交，不偷偷替换候选或基线重试。
- [ ] **AC7 未知核对：** 真实提交后的丢响应/5xx/畸形响应，经关闭/重开/刷新/同主体重连
  核对原命令，无重复创建/启停POST；换主体不读取/操作他人的未决上下文。发布后又被
  他人修改区分 current/prior/unknown；没找到不是未执行证明。当前 create/edit/enable/
  disable 未决上下文仍可从合适入口核对，不因替换页面丢失。
- [ ] **AC8 分步方案（仅采用时）：** 创建成功而启用拒绝/未知如实显示，保留已有ID和
  原启用选择；按实际步骤核对，确认启用未执行/拒绝后可按当前权限/版本明确完成启用。
  原子方案则证明创建启用失败保留原 Active，不为测试强加第二命令或中间状态。
- [ ] **AC9 实际运行/回归：** 发布、读取、目录浏览、预览零 Task admission/媒体变更；
  Scheduler 后续真正 due 消费新建启用定义并核对主体/范围/权限。停用/权限撤销停止相应
  未来准入及剩余 scheduled effects；原 pin、结果、成功/不确定不重放保持。RO-1/RO-2
  来源与列表运行、五态/独立文件结果、记录/成功率、四类恢复、C使用A策略仍为C回归通过。
- [ ] **AC10 持久化/最终门禁：** Fresh及同版本重开保留定义启停、原命令核对/Task/结果；
  B完成匹配候选的适用T4、原生、source外wheel及容器证明，列明失败/skip/限制。

### Required Tests / 分工

**Developer — 新增/修改/直接受影响测试。** 调整旧 disabled-only 断言以覆盖新选择，
保留默认关闭与权限拒绝覆盖。仓库根执行：

```sh
.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle tests.test_automation_execution_intent
.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_automation_authorized_execution_matrix
```

第一组覆盖发布、引用、非法输入、权限、精确核对与零即时执行；第二组核对共享授权/运行
消费边界。新增用例放现有对应模块；如修改其他生产边界，补其直接受影响用例。
Web在 `web/` 执行，新提取组件/model的测试加入明确文件列表：

```sh
npm run test -- run src/features/operations/AutomationCreateDialog.test.tsx src/features/operations/automation-create-form.test.ts src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationListRunOnce.test.tsx src/entities/operations/automation-lifecycle.test.ts src/shared/api/api-client.test.ts
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-workspace.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
```

沿现有列表/详情编辑入口和真实API→SQLite链扩展原生用例：默认/选启用、重复编辑/启停、
返回/错误定位、真实提交后未知刷新核对、并发、桌面/390px/键盘。故障注入绑定实际请求/
现有权限或持久化边界，不手写最终 Active/Task 冒充生产行为。现有 automation harness
维持单worker，只补旅程确需fixture，不扩建过程工具。Python变更文件ruff format/check、
Web变更文件Prettier check、governance及 `git diff --check` 通过后交实际结果/风险。

**B — 独立验收及完整回归。** 审查固定 Task Base..candidate 全部文件与AC，从列表
走完完整旅程；先复现关键阻塞，再跑昂贵门禁。T4执行
[workflow §6完整命令](docs/development-workflow.md#shared-full-regression-commands)，
包含全Python/Web/默认E2E、生产资源原生、wheel/source外消费者和适用容器安全证明。
专项复用上列原生四文件及全量中的 `tests.test_automation_task_admission`、
`tests.test_automation_definition_occurrence`、`tests.test_task_scheduling`、
`tests.test_task_scheduling_fencing`、`tests.test_organize_source_history` 等；同次全量覆盖
不机械重跑。以实际构建wheel名/镜像ID运行 `scripts/wheel_smoke_test.py` 和
`scripts/docker_release_security_smoke_test.py`；安装消费者/容器证明 fresh→同版本重开、
创建启用→due→Worker、权限和原命令核对，记录候选/依赖/产物身份与本地证据路径。

**测试用时约束：** Developer与B各自本轮测试时间须小于整轮50%。先做结果、代码和
旅程审查并估算门禁成本，再安排测试；记录测试及整轮实际用时，并行测试不能隐去。
不以空等/重复测试或转嫁B全量凑比例；必需门禁未完成保持待验，不能提前PASS。

### Non-goals

不重开Task49.1，不重构已接受的来源/列表运行反馈/历史；不重做详情、记录、Task Center、
复制/删除业务或高级Draft产品，只修本次相关入口/提示。不加列表启停开关、批量运行、
模式/Provider/Storage、自动重试/未知重放、补偿回滚或旧失败Task迁移。不做跨版本升级、
生产外部服务验收/部署。不改Slice/Roadmap/Progress，不提前把TARGET改为CURRENT。
如确需schema或兼容边界扩展，列具体用户阻塞交A作范围决定。

### Developer Completion Report

Checkpoint: `9eae8f666c50f8bfc488b914336c2c4be8b750b7`（main，Task Base
`efc628cf62b102f689e779bbee7747d88006598d`..`9eae8f66`）— **READY FOR B REVIEW**。
实施起点为激活提交 `0d85b48e`；预存 untracked 文件（日志/`15`/output/图片等）全部保留且未入提交。
本轮实施前 governance PASS，`git diff --check` 通过。

**变更行为（对应 RO-3 / RO-4、AC1–7、AC9）：**

- 后端（`automation_workspace_commands.py`、`service_api.py`）：`save_object`
  新增 create 命令的显式可选启用参数——省略仍停用，严格布尔 `true`
  在同一次原子激活内发布启用定义并复用既有共享发布意图链（作用域主体、
  激活边界的 `GRANT_UNATTENDED_EXECUTION`、审计）；仅凭候选内 `enabled: true`
  仍被拒绝（409 `automation_definition_enable_requires_command`），非布尔类型
  400 拒绝；PUT 编辑命令不接受额外 `enabled` 键（启用经类型化候选提交）。
  `form_authority` 按连接主体权限投影 `create/edit/copy/toggle/remove/enable/
  createEnabled` 及有界无秘需的中文原因；API 层始终传主体权限，直接服务调用
  保留宽容投影。创建启用复用 `_publish` 的原子后继发布与
  `automation_intent_ids`，无分步编排（AC8 原子方案路径，无第二命令/中间态）。
- Web（新 `AutomationDefinitionFormFields.tsx`）：新建与已保存编辑共用同一张
  中文卡片（字段、校验展示、有界目录浏览、后端近期时间预览、启用开关），
  无第二套表单/校验器；`AutomationCreateForm` 增加启用选择（默认关），
  `editFormFromDefinition` 精确回填（任意合法 Cron/`1.5` 秒等小数间隔原文保留、
  ID 不变）；创建选中开关后主按钮变「创建并启用」一次提交完成，成功提示
  「已创建并启用 / 创建成功，尚未启用」依据持久真值（响应定义），列表横幅同步；
  编辑回填 enabled 并可保存切换；无 `createEnabled`/`enable` 权限时开关禁用
  并显示后端原因；lifecycle 页移除旧英文长表单与本地预览按钮，共享卡片
  自动预览；编辑「运行一次」保持不存在；复制/移除及 successor-Draft 编辑器
  （`/operations/automation/editor/$definitionId`）边界不变。

**实际受影响测试（Developer 范围，均于 Task candidate 上运行）：**

- Python（仓库根，`.venv/bin/python -m unittest`）：
  - `tests.test_automation_definition_publication tests.test_v2_automation_lifecycle
    tests.test_automation_execution_intent` → **106 tests OK**（新增：原子创建启用、
    缺定时权限拒绝+同主体可停用创建、非布尔拒绝、form_authority 主体投影（服务级+API 级）、
    创建启用定义的 Scheduler 意图链、PUT 拒绝 `enabled` 侧键、非布尔 400）。
  - `tests.test_v2_automation_run_once tests.test_automation_authorized_execution_matrix`
    → **48 tests OK**；直接受影响邻域 `tests.test_classification_destination_contract
    tests.test_automation_run_once tests.test_v2_rules_workspace_commands` → **111 tests OK**；
    `tests.test_automation_task_admission tests.test_automation_definition_occurrence
    tests.test_task_scheduling tests.test_task_scheduling_fencing` → **87 tests OK**。
- Web（`web/`）：任务指定 8 文件清单 → **117 tests OK**；全量 `npm run test`
  → **92 files / 1321 tests OK**；`npm run typecheck`、`npm run lint`、
  `npm run build` 通过；Prettier check（含变更 e2e spec）通过。
- 原生 E2E（`playwright.python.automation.config.ts`，真实 harness，单 worker）：
  四个指定 spec → **41 passed**；新增旅程用例「一次提交创建并启用」验证
  默认关→选中变「创建并启用」→恰好一个 POST→持久 enabled→再开编辑卡回填 checked。
- Python 变更文件 ruff format/check 通过；`git diff --check` 通过；
  governance PASS。
- 用时：本轮实施约 85 分钟，测试/验证（含单元、集成、E2E、类型/构建门禁）
  累计约 15 分钟（<30%）。

**剩余风险 / B 需注意：**

1. 未采用分步 create→enable 编排，AC8 仅适用原子方案的证明（已提供：失败保留
   原 Active、无第二命令）；AC7 的创建后核对复用现有 `publication-intent`
   （create action、候选含真实 enabled），组件级/后端级已覆盖，未扩建 harness 主体
   切换工具——「无 scheduled 权限创建停用并见原因」由 API 级（configurator 主体）
   与组件级用例覆盖，如 B 需要浏览器级证据需新增 harness 主体 fixture。
2. e2e 断言从旧英文文案改为共享卡片中文文案/`exact: true`（如 `保存`、启用/停用
   提示、复制核对文案），B 审查时请按新 UI 文案核对匹配面。
3. lifecycle 页仅翻译了与本次直接相关的提示（头部/保存/启停/错误横幅）；
   removal/copy 区块的其余英文说明保留原样，属 Non-goal 范围。
4. 编辑保存成功后停留在当前页继续编辑（不再导航），旧响应不覆盖后来输入的语义
   由共享 accept-merge 逻辑保持。
5. 未执行 B 的全量 T4 门禁（全量 Python/Web、默认 E2E、wheel/source 外消费者、
   容器安全证明、fresh/同版本重开安装证明）——按分工由 B 执行；`npm run build`
   已在候选上通过，E2E 使用该构建产物。

### B 规划核对 / 全部 Slice 结果重评（激活前记录）

RO-1/RO-2已由Task49.1交付接受；相对其Reviewed Head至本轮起点仅Task审查文档变化，
本轮核对实际来源及列表命令路径，不冒充重新跑过全量。RO-3/RO-4仍有上述代码缺口，
合并为本草案一个完整行为单位，无需按字段/层拆分。本轮无新实现候选，故不新增实现
PASS/FIX REQUIRED。未来此Task PASS后重评全部RO/表面；满足即停止规划，补齐Slice最终
证据交A，不由B关闭Slice。

本轮基线：governance PASS；三个现有用例 **3 tests OK / 0.197秒**：
`AutomationPublicationTests.test_create_rejects_an_enabled_candidate_without_publishing`、
`AutomationLifecycleApiTests.test_form_authority_is_bounded_and_secret_free`、
`ExecutionIntentTests.test_checked_enable_supplies_scoped_principal_without_grants_or_immediate_work`。
它们证明现状/复用点，不是目标功能验收；没有运行全量、浏览器或安装产物门禁。

规划起点：`/Users/songzhidong/mediaflow`，main，HEAD/拟定Task Base如上，tracked干净，
工作区/Git可写。预存untracked完整清单保存在
`.git/validation-evidence/efc628cf62b102f689e779bbee7747d88006598d/b-task49.2-planning/workspace-before.txt`。
只维护Task草案，保留全部预存日志、OS文件、参考图、`15`和output且不入提交；不读用户
数据库/私有配置/生产媒体，不push、部署或改写历史。

### B 激活记录 — 2026-11-05

激活起点：`/Users/songzhidong/mediaflow`，main，HEAD
`7b7e9aaa24684ee59552ca95641843706dc7680d`；tracked工作树干净，工作区/Git可写。
从原Task Base到激活起点只变更TASK.md，产品代码、测试、harness和依赖未改变；
B确认既有草案仍符合已提交ACTIVE Slice49，目标、范围、验收与测试计划不变。
本次只激活Task49.2，不实施产品、不产生实现验收或关闭Slice。

governance预检PASS；激活后核对正式Task元数据、父Slice与Base祖先关系、文档链接及
`git diff --check`。未重跑产品测试；此前3项基线结果属于规划轮，不冒充本轮验收。
全部预存untracked文件保留且不入提交，起始清单位于
`.git/validation-evidence/7b7e9aaa24684ee59552ca95641843706dc7680d/task49.2-activation/workspace-before.txt`。
本轮只提交TASK.md，不改Slice/Roadmap/Progress，不读用户数据库、私有配置或生产媒体，
不push、部署或改写历史。

### B Review Result — 2026-11-05

**FIX REQUIRED**，保留原Task ID、Base、Goal和全部验收；修正留在Task49.2。

- Task Base：`efc628cf62b102f689e779bbee7747d88006598d`。
- Reviewed Head：`ff7e3f998ecbe48389a79f5fb3c244caf2bfd6ba`。
- 实现checkpoint：`9eae8f666c50f8bfc488b914336c2c4be8b750b7`；其后两次提交仅修改交接报告。
- 已审完整Base..Head的19个文件，包括共享字段提取、创建/编辑/列表与API候选、后端权限/
  发布/核对消费及全部变更测试；未以Developer测试报告替代独立验收。

**交付核对：** 共用字段、中文时间控件和精确回填已落地；创建默认停用与明确选择启用
通过同一原子发布链，当前权限拒绝保留Active，后端专项106项通过。原生浏览器实际创建
启用及后续编辑停用成功。但共享字段尚未形成合同要求的共用卡片旅程，且核对旧发布后
把过去的启用结果当成当前状态，因此不能接受完整RO-3/RO-4。

#### B49.2-01 — P1：补齐列表背景上的编辑卡片、退出与保存返回

实际旅程：“自动化 → 新建 → 创建停用定义 → 行编辑 → 修改名称 → 返回自动化”。
编辑进入独立长页，无新建卡片/列表背景；返回直接离开，没有继续编辑/放弃修改选择，
再开编辑恢复原名，刚输入的名称丢失。另一条旅程保存名称后，后端已保存但仍留在编辑页；
再提交修改并暂缓实际成功响应，点击返回仍能离开，此时保存已生效而界面尚未确认。
桌面和390px截图均已检查；不是仅根据dialog数量或CSS认定缺陷。
违反Task AC1/AC3/AC4/AC6及Slice RO-3、AC-7/9；交接所述“保存成功后停留当前页”
不能替代合同的保存成功返回列表。

开发修正指导：

1. 将列表编辑和已有普通已保存编辑入口接入与新建共用的卡片容器/列表背景，沿用共享
   字段及命令差异；保留深链、刷新、登录续转、Draft-only/历史和复制/删除的现有边界。
   普通表单头部收起内部ID/Active修订/发布步骤说明到必要诊断，不继续以技术教程占据主入口。
2. 复用已有创建卡片的退出/焦点/动画能力：未修改直接关，修改后可见继续编辑/放弃；
   保存中防重复命令及意外离开，结束未知结果允许保留原命令后离开并重开核对。
3. 确认保存成功后返回原列表，刷新真实行/统计并恢复合法条件、页、滚动和入口焦点，
   被筛选掉时解释。再打开同一定义仍可改字段或启停；旧响应不能覆盖后来输入。
4. 补真实列表→编辑→退出/保存的原生用例，覆盖未改关闭、修改退出选择、提交中返回/
   浏览器返回、成功回列表再编辑、深链、桌面/390px/键盘/reduced-motion。沿用已有harness，
   不只把旧长页断言翻译成中文。保留现有重复保存/并发/核对能力的受影响回归。

#### B49.2-02 — P1：核对本次发布时区分当时结果与当前保存状态

实际旅程：“新建并勾选启用 → 后端已创建，浏览器收到503 → 另一会话从列表编辑并保存
停用 → 原会话刷新、同身份重连 → 核对本次创建”。核对正确找到了原创建，且没有第二次
创建POST，但随后横幅说“已创建并启用；后续将按保存的计划定时运行”；同页统计已启用0、
该行停用，持久回读在核对前后均enabled=false。操作者无法据此判断当前是否会定时运行。
违反Task AC7、Slice RO-4/AC-12和Active真实状态语义；媒体没有被此核对重放。

开发修正指导：

1. 保留原principal/action/candidate/base精确核对，原发布成功证明不能充当当前Active
   证明。复用既有只读发布/定义证据，在API/application与Web明确区分本次发布仍为当前、
   本次发布已成功但后来被修改、证据仍未知；不只改横幅词语而继续混用版本/状态。
2. 上述场景应显示“本次创建曾成功并启用；当前已停用（后续修改）”等准确事实，列表/
   统计/再编辑依据当前保存定义。读不到当前状态时明确当前状态不可确认，不推断仍启用；
   核对不能自动再创建、重新启停或把用户原选择悄悄改掉。
3. 同样检查共享编辑/启停核对后的回填/下一次保存：旧已审候选不能冒充当前已保存值或
   被配上新的基线。保留后来输入，按实际当前版本明确继续；未知查找缺失仍不允许重发。
4. 加入真实已提交后503→另一会话发布→刷新/同身份重连→核对的原生测试，断言当前
   enabled/列表/成功提示一致、原POST只有一次、没有自动启停。后端/组件覆盖current/prior/
   unknown及现有未决上下文，沿已有入口和发布链验证，不扩建通用恢复系统。

#### B实际验证、限制和下一步

- Python：`.venv/bin/python -m unittest tests.test_automation_definition_publication
  tests.test_v2_automation_lifecycle tests.test_automation_execution_intent` → **106 tests OK，
  49.390秒**（进程49.731秒）；权限、原子创建启用与调度意图专项通过。
- Web：`web/`下`npm run build`通过（进程0.640秒），有bundle体积warning，不是验收失败。
- 原生：本轮build的生产资源、现有`playwright.python.automation.config.ts`、单worker、
  真实Python API/临时SQLite/合成Storage，经真实列表新建/编辑发命令；B追加三个验收
  用例，`web/`运行`npm run test:e2e -- --config=playwright.python.automation.config.ts
  tests/e2e/task49-2-b-review.python.spec.ts` → **3 failed，6.090秒进程用时**。
  失败分别为编辑非卡片、成功不回列表、核对历史
  创建误称当前启用；前两用例同时记录无退出确认、输入丢失及提交中可离开。
- 首次探针因B把正常列表查询参数与普通strong提示当成URL/heading失败，尚未走完验收；
  修正探针后重新运行取得以上产品失败。首次35.201秒及其日志/trace完整保留，不计作
  产品阻塞，也没有修改产品代码或放宽目标断言。
- governance、链接目标及`git diff --check`通过。本轮测试/构建进程累计约91.7秒，包含
  首轮探针；低于本轮总用时50%。已有P1，按workflow先FIX REQUIRED；完整Python/Web/
  默认E2E、wheel/source外、容器与最终fresh/同版本重开门禁尚未运行，由B在修正候选上负责，
  不是要求Developer补全量。

本地证据：`.git/validation-evidence/ff7e3f998ecbe48389a79f5fb3c244caf2bfd6ba/b-task49.2/`，
含完整diff、workspace起始清单、命令/退出码/用时、探针源码、JSON回读、桌面/390px截图、
首轮与最终trace；仅本地可取。临时验收spec已从工作树撤出，源码留在该证据目录。

**全部Slice结果重评：** RO-1/RO-2保留Task49.1已接受结果，本Task未修改其来源准入/
列表运行核心实现；修正后的共享表面仍需最终回归。RO-3尚未完成完整编辑卡片旅程；
RO-4正常创建启用链已实现，但并发后的核对显示仍未满足。Slice49保持ACTIVE，不提交
Closure Packet、不规划下一Task、不由B关闭Slice。下一步为 **SAME TASK FIX LOOP**。

审查起点main / Reviewed Head，tracked干净、工作区/Git可写；预存untracked全部保留。
本轮只提交Task结论/修正指导，不改Slice/Roadmap/Progress，不读用户数据库、私有配置或
生产媒体，不push、部署或改写历史。
