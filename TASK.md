# Task49.2 — 统一自动化创建/编辑卡片与明确启停

Authority: committed [Slice49](SLICE.md) RO-3 / RO-4；生命周期遵循
[开发流程](docs/development-workflow.md)。用户本轮明确要求“激活Task”，B据此将
`7b7e9aaa24684ee59552ca95641843706dc7680d:TASK.md` 中的草案转为正式任务。

```text
Task ID: 49.2
Task Type: SLICE
Parent Slice: 49
Status: READY FOR B REVIEW
Task Base: efc628cf62b102f689e779bbee7747d88006598d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: USER ACTIVATED TASK49.2; IMPLEMENT ONLY THIS TASK
Next Action: B REVIEWS THE B49.2-03 FIX CHECKPOINT 9d6b7814
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

### Developer — affected tests

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

### B — acceptance and full regression

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

### Developer Completion Report（B49.2-01/02 修正轮）

Checkpoint: `e5fe262a`（main，Task Base `efc628cf62b102f689e779bbee7747d88006598d`..`e5fe262a`；
实现起点为 B Reviewed Head `ff7e3f99`）— **READY FOR B REVIEW**。本轮只修复 B49.2-01/02，
governance PASS，`git diff --check` 通过；预存 untracked 文件（日志/`15`/output/图片等）
全部保留且未入提交（本轮曾误在仓库根跑 vitest 留下仅含缓存目录的 `node_modules/`，
已确认内容后删除，恢复起始状态）。

**B49.2-01 修复（共用卡片旅程）：**

- 新建共享卡片容器 `automation-card-shell.tsx`：创建/编辑共用同一 layer/backdrop/
  中文头部、退出动画、继续编辑/放弃修改钉住选择、Escape/Tab 焦点圈、body 滚动锁、
  邻接 inert、路由/浏览器返回拦截（submitting 或未保存输入时阻断，未知结果保留原命令
  允许离开重开核对）、关闭后焦点返回原入口。`AutomationCreateDialog` 重构到该容器，
  行为不变（原 13 项组件测试全过）。
- 新 `AutomationEditDialog.tsx`：列表行编辑与普通已保存编辑入口打开列表背景上的同一
  张中文卡片；共享字段/校验组件与命令差异保留（PUT 保存、独立启停/复制/移除命令及其
  确认/权限/未知阻断）；内部 ID、Active 修订、发布机制、executionEffects 收进折叠的
  「诊断信息」；编辑卡无「运行一次」。深链/刷新/登录续转进入同一体验；Draft-only/历史/
  不可读按原错误状态呈现，不伪装 Active；复制成功后导航沿用 resetExit 保持卡片可用。
- 确认保存成功返回原列表：刷新真实行/统计、标记该行、横幅显示“已保存并启用 /
  已保存，当前停用”，被筛选掉时解释；取消/放弃/保存保留合法列表条件、页、滚动，
  焦点回到该行编辑入口。提交中的保存防重复命令并阻断离开（取消按钮禁用、Escape/
  返回均不弃命令）；提交期间继续输入的场景确认合并（仅替换未重打字段）并如实提示，
  不静默丢弃。
- `RefreshControl` 显式 `type="button"`：修复其位于编辑卡表单内时点击会触发表单提交
  （意外发布保存）的真实缺陷。

**B49.2-02 修复（核对区分当时结果与当前状态）：**

- 后端 `publication_intent`：证明发布时新增当前状态证据
  `currentDefinitionState`(current/modified/absent/unreadable) + `currentDefinition` +
  `currentActive`，从当前 Active 读取并指纹比对提交候选；当前 Active 不可读时如实返回
  unreadable，绝不以发布修订冒充当前状态，也不影响已证明的发布事实。
- Web 模型/客户端 fail-closed 归一化：published 响应缺少/畸形当前证据时降级 unreadable，
  仅 current/modified 携带当前定义。
- 创建卡核对文案与列表横幅按证据区分：“已核对本次创建；已创建并启用，当前保存状态与
  之一致”（current）/“创建当时已启用；该定义之后被再次修改，当前为停用状态…”（modified，
  横幅标题为「已核对本次创建」，不再出现现在时“已创建并启用”）/absent/unreadable
  （当前状态无法确认，不推断仍启用）；核对不重新创建、不自动启停。
- 编辑卡核对：仅 current 时以当前 Active 为新基线合并；modified/absent/unreadable 保留
  操作者后续输入与原 observed authority（不配新基线），由既有“未保存的修改基于较旧的
  配置”横幅引导显式重读采用；未知查找缺失仍不允许重发。

**实际受影响测试（Developer 范围，均在候选 `e5fe262a` 构建上运行）：**

- Python（仓库根，`.venv/bin/python -m unittest`）：
  - `tests.test_automation_definition_publication tests.test_v2_automation_lifecycle
    tests.test_automation_execution_intent` → **110 tests OK，51.6s**（新增 4 项：
    modified/still-current/absent/unreadable 当前状态证据，含当前 Active 读取故障注入）。
  - `tests.test_v2_automation_run_once tests.test_automation_authorized_execution_matrix`
    → **48 tests OK**；邻域 `tests.test_automation_task_admission
    tests.test_automation_definition_occurrence tests.test_task_scheduling
    tests.test_task_scheduling_fencing` → **87 tests OK**。
- Web（`web/`）：任务指定 8 文件清单 + 生命周期组件测试全过；全量 `npm run test`
  → **92 files / 1321 tests OK，103s**；`npm run typecheck`、`npm run lint`、
  `npm run format:check`、`npm run build`（既有 chunk 体积 warning）通过。
- 原生 E2E（`playwright.python.automation.config.ts`，真实 Python API/SQLite harness，
  单 worker）：四个指定 spec → **46 passed，1.2 分钟**。新增：行编辑卡片在列表背景上
  打开/未改直关/修改后退出选择/放弃恢复列表上下文/保存返回并标记行/再编辑；提交中
  阻断离开+未知结果关闭重开核对（PUT 恰一次）；390px 无溢出+键盘可达；创建启用丢响应
  →另一会话经行编辑停用→刷新重连核对→横幅同时说明“创建当时已启用、当前为停用”、
  无第二次创建 POST、无自动启停。既有旅程按“保存返回列表”实际语义改写（保存成功断言
  URL/横幅/持久状态，不再断言旧页内提示）。
- Python 变更文件 ruff format/check 通过；Web 变更文件 Prettier check 通过。
- 用时：本轮测试与门禁实测执行累计约 25–30 分钟（Python 专项约 5 分钟、Web 单元
  全量+聚焦约 5 分钟、原生 E2E 多轮约 9 分钟、build/typecheck/lint/format 约 6 分钟）；
  本轮窗口含轮次间等待，无论按何种窗口口径计算该占比都远低于 30%。测试排障中发现并
  修复的真实产品缺陷一并计入实现：RefreshControl 缺 type="button" 会在其被置于表单内
  时把刷新点击变成表单提交。

**剩余风险 / B 需注意：**

1. 编辑卡保存成功即关闭返回列表；提交期间继续输入是唯一留在卡片内的路径（合并+提示
   “你在提交后的新输入已保留”）。列表横幅是保存成功的主反馈面。
2. 保存成功路径会同步把确认后的 Active 写入 authority 查询缓存，消除“保存后立即重开
   仍用旧 fence”的 409 窗口；若 B 在极端时序下复现 409，既有冲突文案+过期候选横幅
   提供显式重读路径。
3. e2e 中 “corrupt published evidence” 旅程遗留的 open Draft 会作为 draft-only 行出现
   在列表背景中（既有已接受 workspace 行为，harness 无丢弃 Draft 的生产边界）；该测试
   的“不得渲染 Draft 候选”断言已按合同意图收窄到编辑卡片，请 B 审查该收窄是否可接受。
4. 未执行 B 的全量 T4 门禁（全量 Python/Web 默认 E2E、wheel/source 外消费者、容器安全
   证明、fresh/同版本重开安装证明）——按分工由 B 执行；`npm run build` 已在候选通过，
   E2E 使用该构建产物。
5. 删除/复制/启停成功提示仍在卡片内（保持既有命令语义）；移除成功关闭卡片返回列表，
   未新增列表横幅——如 B 认为需要保存同级反馈，请在同一 Task 内指出。

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

### B Re-review — 2026-11-05（B49.2-01/02 修正候选）

**FIX REQUIRED — SAME TASK FIX LOOP**。原Task ID、Base、Goal、范围和T4分工不变。

- Reviewed：`efc628cf62b102f689e779bbee7747d88006598d`..
  `3f91045555fb32f20cfdc360314fc23b88f23eb5`，完整24个变更文件。
- 本轮实现checkpoint：`e5fe262a4051bfd10d973f55453b8da390f1cac7`，之后仅Task交接文档。
- 结合上一轮已审且未变的实现，核对本次全部16个变更文件及合并结果：卡片容器/退出、
  编辑发布与回填、列表缓存/返回、当前状态核对、共享刷新控件和全部变更测试。
- **B49.2-01/02 的已知阻塞复现已通过**：真实列表编辑卡片、修改后退出选择、保存返回、
  提交中拦截离开、未知保存重开核对、390px键盘操作，以及“创建启用回复丢失→他人停用→
  刷新重连核对”四项原生测试通过。相关旧阻塞不再重复提出；这不是整个Task的PASS。
- 发现下述连续编辑P1，暂不启动昂贵全量/安装门禁。

#### B49.2-03 — P1：再次编辑必须使用同一已保存版本的值和提交基线

真实完整旅程：“列表新建停用任务 → 行编辑 → 勾选启用并保存 → 返回列表显示已保存并
启用 → 立即再点编辑 → 只改名称并保存”。当再次打开时的定义读取稍慢，卡片先显示旧缓存
的停用值，却允许用刚才成功保存的新版本提交。实际原生复现中：第二次保存前持久enabled
仍为true，卡片显示false，提交只改名称却携带false及**最新的有效版本**；后端正常接受，
最终名称保存且enabled变为false。用户没有在第二次编辑中取消启用，计划却被停用了。
违反Task AC2/AC4/AC6、Slice RO-3/RO-4及AC-8/9的精确回填、连续保存和版本一致性。

复现仅延迟现有`GET /api/v1/operations/automation/definitions/{id}`真实响应的交付，
模拟普通读取延迟；创建、两次PUT及SQLite持久结果均走生产链，没有改响应数据或手写状态。
请求/回读证据表明这不是被409拒绝的旧版本保存，而是旧字段与新基线拼接后被正式发布。

开发修正指导：

1. 表单值与保存基线必须来自同一次已审定义投影。复用已有edit projection携带的Active，
   不能将旧edit-query缓存的定义与独立authority-query的较新Active组合成可提交候选；
   已输入候选继续保留其原值和基线，并发改变仍由明确重读处理。
2. 成功保存返回列表前，保持已确认定义及其版本的回填数据一致：同步采用匹配的确认结果，
   或在拿到匹配的真实回读之前暂不开放基于旧缓存的提交。不能只更新authority缓存、期待
   稍后的GET碰巧修正旧字段，也不能靠要求用户手动刷新解决普通连续编辑。
3. 同一绑定规则覆盖保存、启停和已证实的核对结果；保留后续输入与旧响应不覆盖规则。
   不改后端并发校验、不增加自动重试，不把旧字段自动配上最新版本来绕过冲突。
4. 在现有原生harness加入本旅程：普通及读取延迟两组都从真实行编辑启用保存，立即再次
   编辑只改名称，断言回填、提交候选/基线与持久enabled一致。再核对来源/计划等未修改字段
   不被旧缓存带回；保留原有退出/返回/丢响应及同伴冲突用例。组件级覆盖已确认缓存与
   定义投影版本不一致的状态；Developer只跑新增/修改和直接受影响测试，B负责后续T4。

#### 本轮实际验收与全部Slice重评

- `web/`：`npm run build`通过，有既有bundle体积warning。
- 上轮关键复现：`npm run test:e2e -- --config=playwright.python.automation.config.ts
  tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-create-dialog.python.spec.ts
  --grep 'row edit entry|submitting save blocks|edit card fits|proved create reconciliation'`
  → **4 passed（9.6秒）**。测试运行在本轮生产构建、真实Python API/临时SQLite上。
- B追加原生：`npm run test:e2e -- --config=playwright.python.automation.config.ts
  tests/e2e/task49-2-b-reopen.python.spec.ts` → **1 failed**，断言第二次只改名称后enabled
  应保持true，实际false。源码、实际PUT与持久回读JSON、截图及trace留存；临时spec已撤出
  工作树。没有读取生产媒体或用户运行库。
- governance、链接/范围及`git diff --check`通过。测试/构建累计不足20秒，本轮总用时
  已超过4分钟，满足测试低于50%；未重跑上轮后端专项，不将Developer结果冒充本轮验收。
- 已证明P1，按workflow提前FIX REQUIRED；完整Python/Web/默认E2E、wheel/source外、容器
  及fresh/同版本重开等必需门禁仍由B在修正候选执行，尚未完成，不能PASS。

**Slice全部结果：** RO-1/RO-2保留Task49.1接受事实，最终仍需结合共享列表回归；RO-3的
卡片/退出/保存返回及RO-4的历史核对已补齐已知复现，但连续编辑可能把启用值改回停用，
所以RO-3/RO-4尚未完整满足。Slice49保持ACTIVE，不建下一Task、不提交Closure Packet、
不关闭Slice。

本地证据：`.git/validation-evidence/3f91045555fb32f20cfdc360314fc23b88f23eb5/b-task49.2/`。
审查起点main / Reviewed Head，tracked干净，工作区/Git可写，预存untracked清单完整保留。
本轮只提交Task审查结论/修正指导，不改产品、Slice/Roadmap/Progress，不push/部署/改写历史。

### Developer Completion Report（B49.2-03 修正轮）

Checkpoint: `9d6b7814`（main；Task Base `efc628cf62b102f689e779bbee7747d88006598d`..
`9d6b7814`，实现起点为 B Re-review 已审候选 `e5fe262a`）— **READY FOR B REVIEW**。
本轮只修复 B49.2-03，未重开 B49.2-01/02 结论，未动后端并发校验、schema、Slice/Roadmap/Progress。
governance PASS、`git diff --check` 通过；预存 untracked 文件（日志、`15`、output、图片、
`.DS_Store`）全部保留且未入提交。

**根因（实际代码与实测）：**

1. 编辑卡片的「已保存字段」与「提交基线」来自两次不同读取：回填值来自
   `automation-lifecycle-edit` projection（含 `definition`+`active`），而提交 fence 取自独立的
   `automation-lifecycle-authority` 的 Active。定义读取较慢/命中旧缓存时，旧字段被配上最新
   Active，成为「合法」候选。
2. 保存成功只推进 authority 缓存（`updateAuthorityCache`），未同步该定义自身的 projection 缓存，
   因此「返回列表 → 立即再编辑」会先渲染旧缓存字段，却已能用刚确认的新版本提交；只改名称保存
   就把 enabled 改回停用（B 的原生复现）。
3. 复核同一路径时发现的对称风险：启停/复制/移除同样取该混合 fence；且 `candidateIsStale`
   只与 authority 查询比对，当定义投影比 authority 更新（如显式重读后）会把当前候选误判过期
   并禁用保存。

**修复（`web/src/features/operations/AutomationEditDialog.tsx`，唯一生产文件）：**

1. 新增 `candidateAuthorityOf` 与 `loadedAuthority`：未修改表单的候选与其 fence 只来自同一次
   定义投影（`model.active`）；保存/启停/复制/移除四条命令统一使用这一对。`canManage` 额外要求
   本页已有可用 fence（本页值与被提交基线必须成对）。
2. 新增 `seedDefinitionProjection`：保存成功（含提交中输入被保留分支）、启停成功、核对结果为
   `current` 时，把「已确认定义 + 其对应 Active」写回该定义的 projection 缓存，使关闭→立即
   重开（即便下一次定义读取很慢）回填与基线仍是同一对；下一次打开照常从持久状态重读。
   写入的 `definitionFingerprint` 为 `null`（该命令响应没有此证据，不臆造），当前仅编辑卡片
   消费该键。
3. `candidateIsStale` 改为按 `revisionSequence` 与「已观测到的最新 Active」比较：更旧的读取不再
   被当成并发变更证据并误禁保存；更新的读取仍显示过期横幅、禁用保存并要求显式重读。
   并发改变仍由后端精确 fence 拒绝、不自动重试、不偷偷换基线。

**测试（Developer 范围，均在候选 `9d6b7814` 生产构建上运行）：**

- Web 组件（`web/`，`npx vitest run src/features/operations/AutomationLifecyclePage.test.tsx`）
  → **22 tests OK**，新增 3 项：
  - 慢读再编辑：行编辑启用并保存（上限 7）→ 定义 GET 延迟 1.2 秒时立即再编辑，快照断言回填
    名称/上限/启用均为已确认值；随即只改名称保存 → PUT 携带 `enabled=true`、`itemLimit=7`，
    fence = 上一次确认的 Active，SQLite 回读仍启用。
  - 旧字段不得配新 fence：authority 已观测更新 Active、projection 较旧时，输入后出现
    「未保存的修改基于较旧的配置」、保存禁用、零 PUT；显式重读后按 peer 的 Active 保存。
  - 投影比 authority 更新时不误判过期，保存使用投影 fence 并保留 peer 的上限 9。
  - 前两项在修复前源码（`HEAD:web/.../AutomationEditDialog.tsx`）上实测失败：回填
    `Harness automation`/5/未勾选，fence 提交 `revision-peer`；修复后通过。
- Web 任务清单 8 文件 → **119 tests OK**（先前一轮，同一构建链）。
- 静态：`npm run typecheck`、`npm run lint`、变更文件 Prettier check、`npm run build`
  （`index-Dlq65Kgv.js`，既有 chunk 体积 warning）通过。
- 原生 E2E（`playwright.python.automation.config.ts`，真实 Python API + 临时 SQLite + 生产
  构建产物，单 worker）：`tests/e2e/automation-lifecycle.python.spec.ts` → **18 passed，
  36.4s**，含新增「re-editing right after an enabled save keeps the saved values and fence」：
  普通读与 1.2 秒延迟读两组各从真实行编辑启用保存、立即再次编辑只改名称，断言开启前快照回填、
  PUT 候选 `enabled`/`itemLimit`、fence = 上一次确认的 Active，且持久回读 enabled 仍为 true；
  保留原有退出/返回/提交中离开/丢响应核对/同伴冲突/narrow 用例。该原生用例在修复前构建上实测
  失败（回填为旧缓存值 `Harness automation`/5/未勾选），修复后通过。
- 用时：本轮窗口约 20 分钟，测试/门禁执行累计约 2.7 分钟（vitest 约 40 秒、E2E 约 89 秒、
  typecheck/lint/format 约 33 秒、build 约 2 秒），约 13%，低于本轮 30% 上限；排障重跑
  已知失败用例（修复前后对照）计入上述时间。

**剩余风险 / B 需注意：**

1. 延迟读窗口内若操作者在定义读取返回前开始改其它字段，候选会以当时读到的那一版 fence 记录
   并显示过期横幅，需要显式「核对当前值并采用」。这是刻意的安全取舍，不自动换基线。
2. `candidateIsStale` 改为依赖 `revisionSequence` 单调递增（现有缓存推进逻辑已如此假设）。
3. 复制/移除沿用同一 fence 来源，语义未变；其 409 仍复用通用保存冲突文案（既有行为）。
4. 未执行 B 的 T4 全量/默认 E2E/wheel、source 外消费者、容器与 fresh/同版本重开门禁——按分工
   由 B 在 `9d6b7814` 上执行；`npm run build` 已在候选通过，E2E 使用该产物（`web/dist` 被忽略）。
