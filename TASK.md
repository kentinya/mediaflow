# Task 50.1 — 稳定共享弹卡并完成存储卡片与更多菜单

Authority：已提交的 [Slice50](SLICE.md)，以及
[Development Workflow](docs/development-workflow.md)。用户明确授权同一代理先承担 A 激活、
再承担 B 首次规划，并已明确授权激活 Task50.1。Developer 已完成 B 指出的保存中遮罩退出
修正；B 已复验该问题通过，整体验收仍为 **FIX REQUIRED（存储三卡片缺少退出过渡）**。
Task Base、范围与验收不变。Developer 本轮只实施本
Task，未自审 PASS、未执行 B 的完整 T4、未继续其他 Slice50 结果，也未推送或部署。
执行前阅读对应的 [B](docs/agent-experience/task-planner-reviewer.md) 或
[Developer](docs/agent-experience/developer-implementation-role.md) 经验。

```text
Task ID: 50.1
Task Type: SLICE
Parent Slice: 50
Status: FIX REQUIRED
Task Base: f24dce7a0a97e035078879e2a93855de02d74f54
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

完整交付 Slice50 **RO-2**（`V2-UX-007/008`）和 **RO-4 的自动化新建/编辑稳定性补充**
（`V2-UX-013`）：修正现有自动化卡片打开抖动，使存储查看、添加、编辑获得同样稳定、
协调的居中卡片体验，并让存储“更多”菜单清楚可读。对应 Slice AC-3、AC-4、AC-12，
同时满足本 Task 适用的 AC-10/11；不以此代替其他 Slice 结果。

适用契约：
[TARGET 完整旅程](docs/product-experience.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)、
[TARGET 架构](docs/architecture.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)、
[现行存储旅程](docs/product-experience.md#storage-management-and-root-recovery)、
[现行自动化旅程](docs/product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)，
及 `REQ-STO-001–007`、`REQ-SAFE-001–009`、`UX-001–010`、`V2-STO-001`、
`V2-AUTO-013–015` 和现行 Web/权限/配置发布约束。

完整用户旅程：

- **目标/入口：** 在 `/ui-v2/storage` 的原列表查看、添加或编辑存储，或展开某行“更多”；
  在自动化列表点击“新建自动化任务”或真实已保存定义的“编辑”。
- **可见状态/动作：** 卡片在原背景上稳定出现；慢权限/详情/定义读取有适配内容的加载反馈，
  就绪后平顺呈现正文。存储查看按状态/位置、能力/凭据就绪、引用、检查组织；添加/编辑保留
  Provider 字段和值。“更多”的复制、启停、只读检查、移除配置层级明确且定位正确行。
- **成功/退出：** 显式保存仍完成真实 checked Active 发布并读回状态；回到原列表条件、页和
  可见位置，恢复合法入口焦点。自动化新建/编辑从打开、加载到就绪、关闭不回顶或横向跳动。
- **失败/恢复：** 读取失败/拒绝/缺失与加载可辨；保存校验、引用、并发拒绝保留输入和旧
  Active；未知结果保留既有核对路径，不能自动重发。取消/关闭、未保存退出、在途提交分别
  遵守该入口的现有规则，不为统一外观新增发布步骤或重复确认。

## Implementation Scope

### 实际缺口与修改边界

- `web/src/features/operations/automation-card-shell.tsx` 已有居中遮罩、进出、键盘/inert、
  回焦及退出保护；滚动锁定目前只设 `body.overflow`，没有处理实际滚动条占位。
  `AutomationListPage.tsx` 的弹层路由打开/返回未指定保留滚动；
  `AutomationCreateDialog.tsx` / `AutomationEditDialog.tsx` 的短加载卡片切完整表单会突然变高。
  新建已有隔离浏览器复现，编辑已由源码确认同类机制，须分别验证修复。
- `StorageManagementPage.tsx` 的查看是侧抽屉，添加/编辑由 `StorageEditDrawer.tsx` 呈现；
  “更多”用 `details/summary`，现有 `mf-storage-more*` 无专属视觉样式。当前添加/编辑先等待
  authority/projection 再开抽屉，读取失败在页内提示；新卡片需完整承接读取、失败和退出。
  编辑值及并发 fence 来自同一次精确投影，保存/核对逻辑继续归属存储功能，允许在功能内
  按需要提取组件或 hook。
- 改动限上述入口、必要的 `web/src/shared/ui/` 呈现与
  `web/src/shared/ui/styles.css`、直接相关测试/隔离 fixture，以及反映本 Task 实际交付的文档。
  只提取必要的无业务依赖弹层呈现/滚动/焦点能力；存储不能依赖自动化业务模块。
  表单、退出策略、权限、命令与未知核对保留各自所有者，不建立新的通用命令框架。
  下述文件/组件/测试路径用于定位和执行计划，可在相同职责与行为边界内调整；其名称、
  文件数量或拆分方式不是独立验收条件。

### 实施步骤

1. **修正外壳与自动化两入口。** 先用受控慢权限/慢定义读取复现打开过程。在这些叠层路由
   的打开/返回局部保留背景滚动（如现有 Router 的 `resetScroll: false`），保留筛选、分页和
   深链/认证续转；不全局改 Router 滚动规则，也不先回顶再补滚。按实际滚动条占位选择稳定
   gutter 或实测补偿，避免无占位时多补、重复补偿；关闭/离开/卸载准确释放原样式。
   首次聚焦及回焦避免额外滚动。新建和编辑的加载、错误、拒绝、缺失、完整表单均使用与
   视口/长表单协调的卡片布局，保持标题、关闭和主操作区域稳定，正文内部滚动；不人为延时，
   不跳过真实权限/定义读取，不使用旧 authority 放开提交。保留现有未保存退出和在途保护。
2. **存储查看改卡片。** 复用修正后的必要共享呈现；实际等待时在卡片内反馈该存储的读取
   状态，并承接详情或可读错误/合法下一步。快速响应/有效缓存可直接呈现正文，不强制先播
   占位或人为停留在加载阶段。保留 Provider 根、启用/只读、能力、凭据就绪、
   包含停用引用及截断说明的引用、检查证据/失败和显式只读检查/核实入口。打开、刷新、
   关闭本身不触发检查或变更。取消读取或切换对象后，旧响应不得重开卡片或覆盖当前对象。
3. **存储添加/编辑改卡片。** 沿用 `storage-form` 的字段、校验、候选生成与既有 Save/verify；
   分组/步骤按卡片适配，不锁定原四步抽屉几何。Local、SMB、OpenList、S3/R2 等现有类型
   全部保留；OpenList 空根及 `/` 按原值往返，编辑 ID 不变，同 Provider 未展示配置保留，
   Provider 切换沿用现有规则。未取得精确投影不能把未经核实的旧值当作当前对象编辑，
   authority/fence 未就绪不得提交；添加时无副作用的本地输入可先填写并保留，不因此授予
   保存权限。快速重复打开、关闭、换对象或认证变化时，迟到读取不得串到新意图，编辑值
   与其 fence 始终成对使用。
   保存失败保留输入，冲突/未知结果用既有显式核对；不得因动画卸载丢失未决状态或放开重发。
   存储目前没有自动化式未保存确认，不把“保留已有保护”误写成已有此能力；沿用存储关闭
   放弃语义，不额外增加确认。表单内重渲染/提交状态变化不重新抢焦点；在途提交保护不退化。
   依据成功命令返回的权威配置或必要读取确认真实保存状态，再关闭/反馈并保持列表上下文；
   不强制额外 GET 或固定请求顺序，后续清单读取失败不冒充保存回滚或自动新增。
4. **重做存储“更多”呈现。** 给正确行锚定的菜单明确边界、间距、图标/文字、悬浮/焦点、
   禁用/忙碌状态，区分移除配置危险项。桌面/窄屏与视口边缘不裁切、不挤坏列表；键盘可
   打开、选择、退出。沿用既有 copy/toggle/check/remove 业务处理、RBAC、Active 并发及引用
   保护；菜单关闭回焦不能在后续异步帧抢走新表单焦点。移除只移除配置、保留物理文件，
   原确认/复制输入/未知核对仍可达；不顺带重做这些独立业务流程。
5. **补测试并交接。** 更新仅绑定旧抽屉结构的呈现断言，保留合法字段/权限/冲突/核对断言。
   增加对实际抖动机制、存储读/写状态及菜单交互的回归，按下列 affected tests 验证；同步
   必要 CURRENT 文档，仍将本 Task 未覆盖的 Slice50 结果标为 TARGET。提交精确 checkpoint
   和真实结果给 B，不自审 PASS、不继续实现其他 Slice 结果。

## Acceptance Criteria

- [ ] 存储查看、添加、编辑三个真实入口均在原列表背景打开与自动化协调的居中卡片；
  遮罩、层级、留白、主次操作和进出一致，详情/表单按自身内容安排。桌面和窄屏可读可操作，
  长名称/路径/表单内部滚动不遮挡关闭和必要操作。
- [ ] 存储详情全部既有事实、引用/检查及安全下一步可达；各 Provider 字段、精确回填、
  不可变编辑 ID、未展示配置和 Provider-valid 根保持。读取加载/失败/拒绝/缺失不伪装为空态
  或成功，迟到响应不串对象、不在取消后重新打开。
- [ ] 存储正常添加/编辑仍通过既有 checked Save 发布并读回；无效/重复输入、引用阻塞、
  无权限、并发变化、已知失败与结果未知均保留正确 Active/输入和合法纠正/核对路径。
  不新增 Validate/Activate 步骤、不因重开/动画重发；保存后读失败不宣称回滚。
- [ ] “更多”四个现有操作清楚美观、锚定正确行；普通/危险、禁用/忙碌可辨，悬浮/键盘/
  退出与窄屏/边缘可用。复制输入及移除确认/引用拒绝保留；配置移除不删除物理文件。
- [ ] 自动化新建及真实已保存定义编辑分别证明：从首帧、读取到就绪、关闭，背景不回顶或因
  锁滚动横向重排，卡片不由矮空壳突然撑大跳位；读取慢/失败/拒绝/缺失仍稳定且有真实下一步。
  首次/重复打开、换定义、深链/刷新/认证续转/浏览器返回仍正确，不残留锁定或旧上下文。
- [ ] 所选卡片关闭/取消回到合法列表筛选、页、可见位置及入口焦点；入口已消失时回到合理
  可用控件，深链进入时有合法默认列表返回，不要求恢复不存在的来源。键盘、inert 背景、
  reduced-motion、各自既有未保存/在途规则和未知核对可用。自动化字段、显式保存/启停及
  列表 Run once/复制/独立反馈不因共享呈现而退化。
- [ ] 开关卡片/菜单、导航及加载本身不准入或重放配置/执行命令；正常读取和用户显式命令
  保留。只读检查仍需显式动作，零媒体变更；RBAC、精确 Active/fence、引用、路径、审计/
  脱敏、原有 pins/独立结果/成功及未知效果非重放均不变。
- [ ] B 提供匹配候选的适用 T4 和真实浏览器证据，包含 1536×1024、390px、动态过程及
  reduced-motion。验收依据可见体验/行为，不把固定毫秒/像素、DOM/节点身份或读取请求
  次数设成产品合同，不要求条件全排列；单张停稳截图或仅标题 y 坐标不能证明抖动已修复。

## Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels) 的所有权分工。以下是实施后的
计划命令，本次规划/激活没有执行产品测试或产生修复验收结果。所有数据使用隔离临时根/SQLite、
fake/local server 与合成 Provider，不读取用户配置/媒体或连接生产服务。

### Developer — affected tests

在仓库根执行 `python3 scripts/check_governance.py`、`git diff --check`。在 `web/` 执行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run test -- run src/features/storage/StorageManagementPage.test.tsx src/entities/storage/storage-form.test.ts src/entities/storage/storage-management.test.ts src/shared/api/storage-management-api.test.ts src/features/operations/AutomationCreateDialog.test.tsx src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationListCopy.test.tsx src/features/operations/AutomationListRunOnce.test.tsx
npm run build
npm run test:e2e -- tests/e2e/storage-management.spec.ts tests/e2e/automation-presentation.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/storage-dialog.python.spec.ts
```

- 在实际新增/修改的共享呈现测试上另跑 `npm run test -- run <实际测试路径>` 并在交接列出；
  不为每个 CSS 数值造镜像测试。覆盖焦点/滚动锁清理、卡片退出、慢读取取消/换对象、菜单
  交接焦点、字段保留、失败/冲突/未知核对及不重发。保留现有列表复制和 Run once 回归。
- 扩展现有自动化 real-Python spec，分别覆盖新建和编辑的打开中间过程、慢 authority/
  definition 及已滚动列表；不只保留停稳标题坐标检查。可控读取延迟不伪造命令结果。
- `storage-dialog.python.spec.ts` 为本 Task **计划新增**的聚焦用例：复用现有
  `playwright.python.config.ts` / `scripts/operations_inventory_harness.py` 的生产构建、真实
  API/临时 SQLite 和 Local 根，证明查看、显式添加/编辑、精确读回及拒绝/输入保留。
  必要时只补最小隔离 fixture，不另造测试服务或业务发布通道。fake spec 覆盖其余 Provider/
  失败注入与菜单边缘；真实 Python 契约测试补足后端权威，不对生产远程存储做浏览器实验。
- 共享样式若实际影响其他已有入口，增加其直接受影响用例；交接记录新增/修改测试的真实
  命令、结果和限制。Developer 不承担全 Python/Web/E2E、发布矩阵或 B 的完整证据包。

### B — acceptance and full regression

- 审查 Task Base..candidate 和全部上述验收，先复现自动化两入口及存储三卡片/菜单的关键
  行为；有 Task blocker 则同 Task FIX REQUIRED，修正后复验，不以规划或测试数量替代体验。
- 按 [shared full gates](docs/development-workflow.md#shared-full-regression-commands) 在精确
  候选运行完整 T4，含 Python/Web/默认 E2E、真实应用、适用 wheel/安装消费者/生产安全门禁。
  Docker/重启等按实际受影响契约判断并记录适用性或匹配复用证据，不要求为纯前端呈现重造
  无关故障矩阵；无效迁移/真实外部服务不因此进入本 Task。
- 真实 Python 浏览器使用上述专用 config，在 `npm run build` 后执行两个聚焦 spec；若完整
  门禁已包含相同受影响用例，无需机械重跑。Python 全回归须包含
  `tests.test_v2_storage_operations`、`tests.test_storage_page_local_save`、
  `tests.test_storage_configuration_management`、`tests.test_automation_definition_publication`，
  覆盖 exact Active、Provider 根、隐藏字段、只读检查/零变更、RBAC、并发/失败原子性。
  C→A 身份、pins/结果与成功/未知非重放由适用完整回归保留，不修改处理流水线。
- 桌面 1536×1024 与 390px 实际交互并检查截图/动态证据：存储三入口、长内容、更多菜单
  及视口边缘；自动化新建/编辑分别覆盖页顶/已滚动、实际占位滚动条/无占位、首次/重开、
  慢权限/慢定义、失败/拒绝/缺失、关闭/返回、reduced-motion。按风险组合，不做全排列。
  比较首帧→加载→正文→退出的背景与卡片关键区域，不能让等待动画掩盖读失败。
- 验证纯开关/导航不产生 mutation/admission，显式 Save/启停/检查仍有原权限和精确上下文；
  存储成功后清单读失败、菜单到复制输入的焦点交接、快速关开/换对象不丢状态、不串响应。
  自动化原未知命令核对、保存回填/精确 fence、复制和 Run once 不退化。
- 记录实际命令/cwd、candidate、结果/skip/失败与限制；证据保留于稳定 ignored 路径或 CI，
  不宣称本地文件远程可取。PASS 后重新核对整个 Slice Required Outcomes；本 Task 仅覆盖
  RO-2 和 RO-4 补充，不能直接宣告 Slice50 完成。

## Non-goals

- 本 Task 不实施任务详情弹卡/信息层级（RO-1）、两种库去树/库菜单/配置卡片（RO-3），
  也不实施侧栏主页面切换和两种库加载（RO-4 其余部分）；这些仍是 Slice50 必需结果。
- 不重做自动化字段/复制/移除/Run once、存储业务发布/复制/移除流程，不新增业务字段、
  Provider、命令、发布确认、持久化恢复协议或主题/动效设置；必要呈现复用不升级成全站
  设计系统，也不批量迁移其他弹层。
- 不改变后端/API、配置/权限/媒体执行语义、Task 五态/文件结果/四类恢复，不改数据库、
  Schema、Worker、Scheduler 或处理流水线；不实现下一 Task、不重写历史、不推送/部署。

## Developer Completion Report

状态：**READY FOR B REVIEW**（B P1 修正完成，Developer 交接，未自审 PASS）。

```text
本轮修正 checkpoint: 22618d708a68eeb076d9ed42755a69bf996656df
补充真实浏览器回归: cb3b64362f869c315d782fcefcd5cd813384a9a1
初次实现 checkpoint: b7636a874d643c36fabc90b51080aa67a1c8c543
分支: main
Task Base: f24dce7a0a97e035078879e2a93855de02d74f54
B 审查范围: Task Base..本报告提交 HEAD
```

B 的审查范围是 Task Base..本报告提交 HEAD；实现源码身份为上述两个 checkpoint。工作区既有的
`mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、日志、`15`、`output/` 调查产物均保持原样，
未纳入本次 checkpoint。

### 本轮 P1 修正（B 审查阻塞项）

- **原因：** `ModalCardShell` 的遮罩与层外沿 `onMouseDown` 无条件调用 `onRequestClose`，
  `closeDisabled` 只约束右上角关闭按钮。存储保存中取消按钮、关闭按钮与 Escape 已禁止退出，
  但点击卡片外灰遮罩仍会卸载卡片；保存请求继续完成。
- **修正：** 共享呈现只执行所有者传入的退出许可。`closeDisabled` 现在同时阻止遮罩、层外沿
  和关闭按钮的关闭请求；存储所有者继续以同一 `saving`（`saveMutation.isPending`）传入该
  许可，Escape 沿用既有 `escapeDisabled`。未改变任何存储/自动化业务规则、字段、命令、
  请求顺序或保存状态处理，也未新增确认步骤。
- **结果：** 保存未结束时卡片保持挂载，输入与结果承接位置不丢失；请求仍只发送一次，不会
  因遮罩点击卸载、取消、清空或重发。成功、已知拒绝和未知结果继续走原有返回/核对路径。

### 实际变更（累计 Task 候选）

- 共享呈现：新增 `web/src/shared/ui/modal-card.tsx` 的居中卡片/遮罩/标题/正文/底部结构、
  滚动锁定与滚动条占位、inert 背景、Tab 焦点圈和 `preventScroll` 回焦；本轮补齐遮罩/层外沿
  的保存中退出许可。
- 自动化新建/编辑：叠层路由保留背景滚动，列表按之前可见位置恢复；稳定卡片几何与加载骨架，
  权限/定义读取、失败和完整表单共用同一布局；关闭/错误/拒绝回焦且不滚动背景。
- 存储查看/添加/编辑：改为同一共享居中卡片；查看保留详情、引用、检查证据与显式检查；
  添加/编辑保留四步 Provider 字段、精确投影/fence、迟到读取丢弃和既有 Save/核对逻辑。
- 存储“更多”：正确行锚定的 fixed 菜单、视口钳制、普通/危险层级、键盘焦点与 busy 状态；
  复制/启停/检查/移除的业务、权限、确认和未知核对未改。
- 测试：更新旧抽屉结构断言；新增共享卡片退出许可、存储慢读取/输入保留/菜单焦点、真实
  Python 存储卡片聚焦 spec 和自动化打开中间帧证据。本轮新增保存中遮罩/外沿回归（真实
  添加/编辑入口、桌面与 390px、显式请求门闩、单次命令、成功/已知拒绝/未知核对）。
- 未修改后端、API、Schema、Task 生命周期、发布/权限/媒体执行语义或 CURRENT 产品/架构
  Contract 文本；Slice50 其余 RO-1/RO-3/RO-4 仍未实施，本 Task 不宣告 Slice 完成。

### 实际执行结果（cwd、命令、结果）

以下均为本候选源码实际执行结果：

- 仓库根：`python3 scripts/check_governance.py` → PASS；`git diff --check` → 无输出。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 全部通过
  （build 仅有既存 chunk >500 kB 提示）。
- `web/` 单元/组件（10 个文件）：`npm run test -- run src/features/storage/StorageManagementPage.test.tsx
  src/entities/storage/storage-form.test.ts src/entities/storage/storage-management.test.ts
  src/shared/api/storage-management-api.test.ts src/features/operations/AutomationCreateDialog.test.tsx
  src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationRouter.test.tsx
  src/features/operations/AutomationListCopy.test.tsx src/features/operations/AutomationListRunOnce.test.tsx
  src/shared/ui/modal-card.test.tsx` → **10 files / 188 tests passed**。其中焦点回归 2 文件
  **52 tests passed**，覆盖保存中 Escape、遮罩/层外沿、单次 POST/PUT、输入保留、已知拒绝与
  未知核对入口。
- `web/` 默认 E2E：`npm run test:e2e -- tests/e2e/storage-management.spec.ts
  tests/e2e/automation-presentation.spec.ts` → **31 passed**。
- `web/` 真实 Python E2E：`npm run test:e2e -- --config=playwright.python.config.ts --workers=1
  tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/storage-dialog.python.spec.ts` →
  **19 passed**（自动化 14、存储 5）。新增存储用例从真实添加/编辑入口持有请求，在
  `aria-busy=true` 且取消禁用后分别点击 1536×1024 背景遮罩/卡片外沿与 390px 遮罩，证明卡片
  不消失、输入在确认摘要中保留、POST/PUT 各一次；放行后真实保存读回成功。同一用例继续在
  390px 对重复 ID 再次持有请求、点击遮罩并放行，证明真实 409 拒绝留在表单、输入可导航回读
  且无自动重发。其余用例继续覆盖慢读取关闭竞态、重复拒绝、菜单键盘/边界和精确读回。
- 本轮自动化测试执行累计约 2 分钟，低于本轮实际用时 30%；未执行 B 的完整 T4、
  wheel/Docker/发布门禁。

### 已知风险与剩余工作

- B 仍须在精确候选复验本 P1，并执行适用完整 T4、原生 1536×1024 / 390px 动态与截图验收；
  Developer 未执行 B 的完整回归、wheel/Docker/发布门禁。
- 自动化卡片的经典滚动条动态证据由测试侧 same-origin 样式强制；真实浏览器占位滚动条和无
  占位滚动条仍应由 B 的原生证据确认。
- 存储添加 authority 失败时卡片内保存按钮禁用并提供重试；B 应结合慢/拒绝/缺失响应复核。
- 本 Task 只覆盖 RO-2 与 RO-4 的自动化新建/编辑稳定性补充；RO-1、RO-3、RO-4 其余结果仍
  等待后续 Task，不能据此宣告 Slice50 完成。
- CURRENT 文档未提前改写为已验收事实；Task PASS 或 A closure 时再按实际验收统一对账。

Developer 未作出 PASS/FIX REQUIRED 判断，交给 B 独立审查。

## B Review Result

**Decision: FIX REQUIRED — 2026-11-06。保存中退出问题已修复；存储三卡片的退出体验仍未完成。**

```text
Reviewed Base: f24dce7a0a97e035078879e2a93855de02d74f54
Reviewed Head: 50233ce47bc69b2e0ccddcd95249a6e39764994c
本轮增量: e5df56ca..50233ce4
修正源码: 22618d708a68eeb076d9ed42755a69bf996656df
补充回归: cb3b64362f869c315d782fcefcd5cd813384a9a1
Branch: main
```

结合前轮完整差异审查，重新核对整个 Task Base..本候选及本轮全部增量；Task Base 不变。
原有 `.DS_Store`、日志、`15`、`output/` 等工作区变更均保留。本轮只更新本 Task 的复核结果，
未改产品实现、Slice 合同、Roadmap 或 Progress。

### 上次阻塞：已修复并独立复验通过

`ModalCardShell` 现以所有者传入的 `closeDisabled` 同时约束遮罩、外沿和关闭按钮，存储仍
使用原 `saving` 状态。真实 Python 浏览器聚焦用例通过：桌面添加/390px 编辑保存中点遮罩，
卡片保留、请求只发一次，放行后真实保存并读回；重复 ID 的真实拒绝仍保留表单与输入。
新增/变更的共享和存储组件用例 52 项通过，包含未知结果核实入口。本次不把旧阻塞继续列为
未修复，也未发现该修正增加新业务状态或命令。

### 当前阻塞：P1 — 存储查看、添加、编辑关闭时直接消失，退出过渡没有接入

**用户完整操作例子：** 从存储管理点击 Source 的“查看”，读完详情后点击右上角关闭；
卡片和灰色遮罩立即消失。点击“添加存储”后取消，或打开 Source 的“编辑”后取消，也是
同样结果。随后进入已有自动化列表，打开“新建自动化任务”再取消，可见卡片与遮罩平顺淡出。
在正常动效偏好下，存储三个入口没有与该基准协调的退出过程。桌面 1536×1024 和 390px
均复现；这不是 reduced-motion 下应有的立即关闭。

**为何阻塞：** Goal/验收第一项要求存储三卡片“进出一致”，实施步骤 2/3 要复用共享呈现；
Slice RO-2、适用产品旅程和架构同时要求与自动化协调的进出体验。当前只完成入场，退出仍
缺失，因此属于原要求未交付，不是要求新增动效设置、精确时长或可选美化。

**实际原因：** `StorageManagementPage.tsx:842` 的查看卡片、`StorageEditDrawer.tsx:338/393`
的加载/错误及表单卡片都固定 `closing={false}`。查看关闭直接 `setDetailId(null)`，表单
`closeDrawer`（1753 行）直接设置 `open:false`，当次渲染就卸载。`styles.css:7548` 已存在
退出样式，但这些真实入口永远不进入退出状态。该缺口始于初次实现
`b7636a874d643c36fabc90b51080aa67a1c8c543`（2026-11-06 01:32:12 +0800），
不是本轮保存保护修正引入；前轮尚未完成这一原生体验验收，本轮继续整体复核时确认。

**独立证据：** 生产构建、仓库已有 Python harness、临时 SQLite/Local 根，正常动效偏好；
从上述真实按钮操作，同时记录关闭后逐帧实际透明度/动效和截图。两个视口中存储三卡片
关闭后的首个绘制帧都已完全消失；自动化在相同操作中仍有逐步降低的透明度和退出动效。
这用于证明可见过程缺失，不把帧数、毫秒、CSS 类名或 DOM 存续时间规定成产品合同。

### 给 Developer 的修正指导

1. 为存储三卡片接入现有退出呈现：合法关闭请求先进入退出状态，正常偏好下完成协调的
   卡片/遮罩退出后再交由各所有者关闭；reduced-motion 按偏好直接或减少动态地完成。
   可在现有无业务共享呈现内复用必要生命周期，不引入通用命令框架，不依赖自动化业务。
2. 将关闭按钮、取消、遮罩、外沿、Escape 及读取失败的返回操作接到同一退出路径。
   保存中继续保持本轮已经修好的退出禁止；结束后成功关闭也应与呈现协调，已知失败/
   未知结果继续留在原有处理路径，不取消/重发保存，不清掉未决结果来播放动画。
3. 退出期间保持原背景、焦点约束和滚动锁，结束后准确释放并回到合法入口；连续关闭/
   重开及慢读取晚返回不能让旧退出结束回调关闭新卡片。使用原有真实状态做最小改动，
   不新增存储未保存确认、业务字段、后端能力或延迟数据读取。
4. 补真实入口的退出回归：查看、添加、编辑均检查正常动效下实际退出过程和最终返回；
   桌面/390px 按风险组合，另验 reduced-motion、快速关闭重开和保存中遮罩保护。
   检查可见效果及零额外命令，不只断言存在退出 CSS，也不绑定固定毫秒/像素。
5. Developer 跑新增/变更及直接受影响测试和相关静态检查后提交精确 checkpoint，重新交
   READY FOR B REVIEW。B 对修正候选先复验阻塞，再执行剩余验收与适用完整 T4。
   同一 Task 修正，不规划下一 Task，不把全仓回归或 B 证据工作交给 Developer。

### 本轮实际验证与限制

本机稳定 ignored 证据：`.git/validation-evidence/50233ce4/b-review-20261106/`，仅本机可取。

| cwd | 实际命令/操作 | 结果与证据 |
|---|---|---|
| 根目录 | `python3 scripts/check_governance.py` | PASS |
| 根目录 | `git diff --check f24dce7a..50233ce4` | PASS |
| `web/` | `npm run build` | PASS，既有 chunk 大小提示 |
| `web/` | `npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/storage-dialog.python.spec.ts --grep 'keeps in-flight'` | 1 passed，3.02s 总进程用时；`critical-e2e.log` / `.result.json` |
| `web/` | `npm run test -- run src/shared/ui/modal-card.test.tsx src/features/storage/StorageManagementPage.test.tsx` | 2 files / 52 tests passed，5.37s 总进程用时；`focused-unit.log`。jsdom 仍有既有 scrollTo 未实现提示，不作为实际滚动证据。 |
| 根目录 | `.venv/bin/python scripts/operations_inventory_harness.py --port 4183` + `node .git/validation-evidence/50233ce4/b-review-20261106/exit-probe.mjs` | 两视口各完成三种存储卡片和自动化基准的打开/关闭；`exit-frames.json`、`exit-probe.log` 和 `*-open.png` / `*-closing.png`，已检查截图；产品退出体验不通过。 |

初次退出调查脚本把侧栏可见中文当成精确 accessible name，定位超时；这是调查选择器错误，
非产品失败。改用仓库既有自动化页面入口后完整调查成功，未构造新业务入口。
本轮测试含这次无效等待仍小于总用时 50%；主要工作为契约、完整差异、根因与开发交接审查。
已发现确定产品阻塞，按 workflow §6 提前 FIX REQUIRED；完整 Python/Web/默认 E2E、其余
真实应用/动态滚动条、wheel/安装消费者及适用生产门禁尚未完成，本轮不声明 T4 PASS。
这些验收仍由 B 承担，不因 Developer 的交接报告标为已完成或豁免。

### 全 Slice 结果重评

| Required Outcome | 当前判断 |
|---|---|
| RO-1 任务详情卡片/可读性 | 本 Task 未实施，仍待后续交付。 |
| RO-2 存储三卡片/更多菜单 | 候选已实施；保存中退出已修复，三卡片退出过渡仍阻塞，剩余完整验收待完成。 |
| RO-3 两种库去目录树、库菜单与配置卡片 | 本 Task 未实施，仍待后续交付。 |
| RO-4 自动化新建/编辑稳定性 | 候选已有修复，B 的完整动态验收尚未完成。 |
| RO-4 侧栏主页面切换/两种库加载 | 本 Task 未实施，仍待后续交付。 |

Slice50 保持 ACTIVE，Task50.1 保持同一 Base 和范围。下一步修正本 Task 的退出呈现；
不宣告 Task PASS、Slice ready/closed，不启动其他 Slice 结果。
