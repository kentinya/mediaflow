# NO ACTIVE IMPLEMENTATION TASK

Last Task: 49.1 — 来源范围正确的列表一键运行
Decision: PASS
Parent Slice: 49（保持ACTIVE，尚未关闭）
Next Action: REVIEW TASK49.2 DRAFT BELOW; NO IMPLEMENTATION AUTHORIZED UNTIL A FORMAL TASK

Task49.1复核已完成；其已接受结论保留于下方，Task49.2规划草案在本文末尾，不授权实施。
Task49.1完整计划与Developer交接保留于
`cd955d3cff474d124d0119291e0d3ed9a8b13b31:TASK.md`；当前接受结论和证据如下。

## Task49.1 — B Review Result

**PASS — 2026-11-05，B 独立审查。**

- Task Base：`129d1c060dea05a91755dbd2ed70632f09655fd4`（不变）。
- Reviewed Head：`cd955d3cff474d124d0119291e0d3ed9a8b13b31`。
- 最终实现 checkpoint：`3fa0297afc69af34dd3e95f7589bd64f32c08049`。
- 审查完整 Base..Head 的24个文件：沿用上一轮逐文件审查的未变部分，再核对本次全部修正，
  重新评估合并后的Task结果；本轮T4基于当前候选重新执行，不以Developer报告代替B验收。

### 交付结果与原阻塞

操作者进入“自动化 → 任务列表”，对已保存定义点击“运行一次”，当前行提交中防连击，
受理后留在列表并可直接查看该Task；非空资源库根的整个库运行能实际进入Worker并整理合成媒体。
停用定义仍可运行，不改变启用状态或调度。健康空、流程失败及独立文件结果继续由现有Task回读。

**B49.1-01 已修复**：第一次受理提示尚未消失时再次明确运行，新提交立即撤下该行旧提示；
第二次明确拒绝就显示本次原因，第二次回复不确定就显示“暂未收到回复 / 查看提交结果”。
查询按第二次实际提交找到第二个Task，旧链接不再冒充本次结果，其他行保持独立。
本轮真实浏览器还验证了第二次受理后替换503→刷新页面→同一身份重新连接→精确查询，
只发生原来的两次明确POST，核对不会再次运行。

| 验收 | B结论与证据 |
|---|---|
| AC1–2 来源范围/失败边界 | API→SQLite→Worker根范围矩阵、due对照、空/不可读/超限、固定上下文与权限拒绝通过；已验证组成部分的规范化不放宽输入，未改Worker严格校验或历史。 |
| AC3–4 列表入口/所见版本 | 原生列表一击准入、停用定义及实际Incoming媒体执行通过；按该行Active ID/sequence提交，过期版本零新Task，未提供的digest不伪造。 |
| AC5–8 本次反馈/安全核对 | 本次列表/session 19项通过，新增连续拒绝/未知/成功及其他行隔离通过；原生桌面/390px和独立刷新重连证明通过。忙碌/拒绝/未知/核对后的截图已人工检查。 |
| AC9 编辑既有能力 | 编辑运行按钮已移除；现有生命周期13例及workspace9例通过，保存、启停、复制/删除和发布核对未被本次修正改变。 |
| AC10–11 安全/结果回读 | 全Python包含源所有权、claim/fence、真实稳定性、四类恢复、C使用Naming/Classification A仍为C、成功/不确定不重放；原生冲突继续与记录/统计保持同一Task、原时间和独立文件结果。 |
| AC12 同版本/完整门禁 | 本轮全Python/Web/默认浏览器、原生30+刷新1、wheel与容器安全、安装产物各15例通过；安装产物验证fresh及SQLite同版本重开，生产模块来源和哈希匹配。 |

### 本轮实际门禁

- Python：`.venv/bin/python -m unittest discover -s tests` → **2588 tests，OK，skipped=7，379.979秒**。
  7项为未配置的真实OpenList/SMB/S3验收及Local/SMB/OpenList/S3耐久性专项，属于合同排除范围。
  日志有ResourceWarning（未关闭连接/临时目录等），无测试失败；不将warning说成产品成功证据。
- Web：完整Vitest **92文件 / 1315 passed**；默认Playwright **253 passed，2.2分钟**。
- 原生：`playwright.python.automation.config.ts`下run-once/lifecycle/workspace三文件单worker
  **30 passed，48.2秒**；B追加真实刷新重连探针 **1 passed，3秒**，探针源码和截图已保留，
  临时测试文件已撤出工作树；原生UI使用本轮build的生产资源、临时SQLite/Local与合成Provider。
- 质量：governance、ruff format/check、compileall、pip check、两份example config validate、
  Web typecheck/lint/format/build、`git diff --check`通过；FFprobe/FFmpeg检索无匹配（预期退出1）。
- 产物：wheel build / wheel smoke通过；source外cwd的installed probe **15 tests OK**。
  精确镜像 `mediaflow:b-task49-1-cd955d3c` release-security smoke通过；相同probe在无网络容器内
  **15 tests OK**，包含真实来源/权限/去重/恢复/指标和fresh→同版本重开，不导入仓库生产模块。
  wheel SHA256与镜像ID、关键源码/lockfile哈希见证据`artifact-manifest.json`。
- 初次wheel smoke误用了旧版本文件名，按实际构建文件名修正后通过；初次Docker门禁因Colima
  无法挂载`/var/folders`临时目录失败，改用共享目录的TMPDIR后通过。两者是B执行环境/命令问题，
  没有隐藏产品失败或放宽断言，首轮/重跑日志均保留。未知响应使用真实受理后的浏览器503注入，
  不声称制造物理网络分区。未验证生产外部服务、旧失败任务迁移或跨版本升级。

**测试时间分配偏差**：本轮完整Python单项约6分20秒，门禁虽与代码/契约/视觉审查并行，
测试占比仍未满足用户要求的低于50%。这是B本轮执行安排的偏差，不能声称达标；本次没有因此
省略必需T4或扩大Developer测试责任。后续应先为完整门禁预留审查时间预算再启动执行。

本地证据：`.git/validation-evidence/cd955d3cff474d124d0119291e0d3ed9a8b13b31/b-task49.1/`。
其中`gates.jsonl`、`web-gates.jsonl`记录命令/退出码/用时，`native.log`、`default-e2e.log`、
`reload-native.log`、wheel/container日志及安装消费者源码/截图均保留；`review-notes.md`给出
验收映射，`artifact-manifest.json`绑定候选。证据仅在本地，不声称远程可取。

### Slice全部结果重评与下一步

RO-1正确来源范围、RO-2列表直接运行：**本Task交付并通过**。
RO-3统一新建/编辑卡片、RO-4创建可选启用：**尚未实施**；当前已有定义仍进入旧生命周期编辑，
新建仍只创建停用定义。Slice49保持ACTIVE，不能提交Closure Packet或宣告关闭。
下一步方向为NEXT TASK，继续合同剩余RO-3/RO-4；本轮只完成当前Task复核，不激活下一Task。根Task已恢复无活动实施任务，完整计划和Developer交接见Reviewed Head中的TASK.md。

本轮起点main / Reviewed Head，tracked工作树干净；只改Task审查状态/结论，保留预存全部
untracked OS文件、日志、参考图、`15`与output，不读取用户数据库/私有配置/生产媒体，不push、
部署或改写历史。此前FIX REQUIRED详情保留在`f6912dff:TASK.md`，不复写历史结论。

## Task49.2 — 统一自动化创建/编辑卡片与明确启停（规划草案）

**仅规划草案，不授权实施。** 本轮按用户 B 规划指令维护此草案。正式激活时保留以下
Base、目标和边界，复查后续差异，再替换顶部无活动实施任务声明。权威为已提交
[Slice49](SLICE.md) RO-3 / RO-4 与 [开发流程](docs/development-workflow.md)。

```text
Task ID: 49.2
Task Type: SLICE
Parent Slice: 49
Status: PLANNING DRAFT — NOT AUTHORIZED FOR IMPLEMENTATION
Task Base: efc628cf62b102f689e779bbee7747d88006598d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

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

Checkpoint: NOT SUBMITTED。正式实施后交固定SHA、READY FOR B REVIEW、变更行为、
实际受影响测试和剩余风险；不要求全量证据档案。本草案无实施交接。

### B 本轮规划核对 / 全部 Slice 结果重评

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
