# Task 53.1 — 手动／批量整理逐文件弹窗与任务中心交接

Authority: committed [Slice53](SLICE.md) at `145e9050514faf88c0805af798a4ae941b217a20`;
[Development Workflow](docs/development-workflow.md) governs lifecycle and test ownership.
Read the [B](docs/agent-experience/task-planner-reviewer.md) or
[Developer](docs/agent-experience/developer-implementation-role.md) experience for your role.

```text
Task ID: 53.1
Task Type: SLICE
Parent Slice: 53
Status: READY FOR B REVIEW
Task Base: 95c24cd0a3cc51acd6143e37e72371445cb15a72
Implementation Checkpoint: 800e4fd8c694c22366597abbf41ebf2943699eb1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: USER-AUTHORIZED TASK ACTIVATION — READY FOR IMPLEMENTATION
Next Action: B INDEPENDENT REVIEW OF CURRENT-FILE METADATA CORRECTION FIX
```

用户于 2026-11-09 明确“把这些在Task明确后激活Task”。本 Task 已正式激活，替换上一轮
草案；PLANNED 表示可进入实施，不表示已开始开发。本轮止于文档与激活 checkpoint。
A 的 Slice 范围已先提交，本计划按该 Contract 正式化，覆盖 RO-1／RO-2／RO-3，不扩范围。
同一执行者完成 A 范围设置与 B 规划只是规划；后续 B 必须独立于实现验收，不代行同一
Slice 的 A Final Review。未授权自动启动其他角色、推送或部署。

## Goal / actual gap

用户从资源库文件页选择单文件、多个文件或有界文件夹，点击整理后，在文件页背景上的
居中弹窗中完成准备、逐文件复核、必要修正和明确执行确认；**确认受理成功后进入任务中心，
直接打开后端返回的对应任务，查看进度、逐文件结果及已有后续处理。**

“每页一个文件”指一个主媒体文件及其关联附件，不是每页一个技术阶段，也不是给每个文件
另建 Task／另点一次执行。批量采用逐项复核、最后集中确认所选就绪子集；单文件复用同一
流程。上一项／下一项只浏览，不保存决定、不调用 Provider、不授权执行。

实际缺口（调查 Base 如上）：

- `StorageFilesPage.tsx` 的单项／多选均先 `submitFilesDiscovery(autoPrepare: true)`，
  然后离开 Files 跳至 `/operations/organize/new`。
- `OrganizeCreationPage.tsx` 将准备说明、五项计数、所有文件的 `ItemFindings`、集中修正及
  确认纵向堆叠；`organize-summary.tsx` 默认展开策略 ID、来源／目标存储标识、候选理由等。
- 摘要页下拉框立即保存并重新分析，而 `OrganizeIntentPage.tsx` 另有保存→生成摘要流程；
  四类业务问题由 `TaskItemRecoveryPanel.tsx` 处理。普通用户需要跨呈现理解同一文件。
- 初次 Files 确认及未知结果核对成功，在没有 `returnOps` 时默认去执行页；本 Task 需要将
  新入口的这两条成功路径都交给准确任务中心详情，不能只改正常 POST 成功分支。
- 库配置已有 `ModalCardShell`／固定 footer／步骤导航；自动化已有稳定居中卡片。
  复用呈现能力，各领域命令和授权模型保持归属。

适用基线：`REQ-RECOVERY-004–009`、`REQ-WEB-005`、`REQ-SAFE-001–007`、
`V2-OPS-010/012/015–017`、`V2-UX-005/006/011/013`；完整当前旅程为
[Manual organize](docs/product-experience.md#manual-organize)、
[Tasks/results/recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)，
受影响合同为 [Files-admitted Task](docs/architecture.md#current--files-admitted-organizing-task-and-verified-source-ownership-slice46)
及 [Slice50 presentation reuse](docs/architecture.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)。
新增 `V2-OPS-018/019` 的 [TARGET 合同](docs/v2-requirements.md#target--manual-organize-dialog-slice53-active)
与 [完整 TARGET 旅程](docs/product-experience.md#target--manual-organize-dialog-slice53-active)
属于正式范围，尚未交付，不宣称已经成为 CURRENT。

## Complete journey

1. **入口／准备：** 从文件行整理或批量整理立即打开弹窗，保留背景库、目录、选择、滚动和
   入口焦点。弹窗就近显示提交中、发现／等待稳定／分析，继续使用现有耐久准入；不是等
   分析完成才打开。文件夹先展示真实发现状态，冻结后按主文件浏览，排除／拒绝原因可查。
2. **逐项复核：** 标题显示当前文件名、`第 i / N 个` 和状态；正文按作品匹配→来源到目标→
   操作及附件→当前问题排列。目标库使用可获得的可读名称并保留准确路径；不从当前配置
   猜测历史 pin 的名称／目标。长路径可完整阅读，不靠删除精确信息美化。
3. **选择／修正：** 每项明确“纳入本次整理／暂不纳入”，不把取消勾选写成持久“忽略”。
   未就绪、已受理或只读项说明原因。识别类型、合法作品候选及本 Task 的识别／元数据／
   分类／冲突问题在当前文件附近处理；复用后端允许的决定→分析→新摘要能力，不另建恢复
   引擎。采用明确“保存并重新分析”动作，翻页不自动保存，未保存输入离开时可返回继续。
4. **确认：** 固定底栏保留翻页和主操作。确认前提供紧凑的整批复核区：选中数量、准确文件
   范围、操作／目标和实际危险影响；可返回对应文件，不再次展开全部诊断字段。仅有实际
   覆盖／清理影响时要求已有明确授权。最终按钮为 `确认整理 N 项`，这是执行确认。
5. **成功／交接：** 后端证明受理成功后关闭整理弹窗，导航任务中心并选中返回的原 Task。
   **沿用既有任务详情**负责执行进度、独立结果和确认后恢复；不在整理弹窗另造执行结果中心。
   提交在途显示“正在提交…”，禁用重复确认；受理不代表文件整理成功。
   已受理却暂时读不到详情时，保留准确任务身份并允许重读，不把读取失败当提交失败。
6. **失败／恢复／退出：** 明确失败阶段、保存了什么、是否修改文件及合法下一步。未知请求
   只核对原请求，不自动重提。关闭不取消已准入工作；通过原任务“继续整理”或有效深链
   重开同一准备。已结束工作保持只读原摘要，原读失败可重读，不重新分析或重新执行。

## 明确场景 — 10 个文件全部需要元数据确认

1. 点击批量整理，先在文件页背景上看到准备状态，随后显示 `第 1 / 10 个`、当前文件与
   可读候选（片名、年份、电影／剧集及足够区分的证据）。不把 10 个文件的候选全部纵向展开。
2. 选择第 1 项候选，点击 **保存并重新分析**；保存合法选择后请求分析。显示当前文件的
   新作品身份、目标路径、操作与附件，确认无误再点“下一项”。保存成功而分析失败时，
   明确候选已保存、尚未获得可确认的新摘要，允许合法的重新分析，不重复保存或执行。
3. 对第 2–10 项重复；共 **10 次候选选择、10 次保存／重新分析动作**。上一项／下一项
   仅浏览，按 itemId 保留已存选择、新结果及未保存输入，不自动套用上一项的作品。
   这里的 10 次是正常无失败的用户动作，不承诺恰好 10 个底层 HTTP／Provider 请求。
4. 全部就绪且纳入后，在紧凑整批复核区确认准确 10 项与影响；可回到对应文件核查。
   统一点击一次 **确认整理 10 项**；此前没有逐文件执行确认，也没有任何媒体变更。
5. 按钮变为 **正在提交…**，禁止重复提交。后端证明受理后关闭整理弹窗，进入任务中心，
   **自动打开本次返回的准确 Task 的现有详情弹窗**。用户在那里看排队／运行、结果与已有
   后续处理；本 Task 不重新设计这些界面，不以“受理”提示“10 项整理成功”。
6. 若确认响应丢失，弹窗保留原提交的核对状态与明确下一步，只核对原请求，不自动重提；
   核对证明确已受理后执行同一任务中心交接。缺少可证明的 Task 关联时保留原上下文继续
   核对，不选最新任务、不返回猜测的执行页、不生成第二次执行。

## 任务中心详情冻结边界

**本 Task 不涉及任务中心页任务详情弹窗更改。** 不更改其布局、内容、进度、结果及恢复
UI；此前关于执行进度的例子只是解释确认后的既有行为，不是新界面需求。
仅整理侧导航使用现有选中 Task／自动打开详情能力。任务中心现有“继续整理”／
“查看只读摘要”入口、文案与呈现保持，由它们原有深链重开准确整理上下文。
若为整理弹窗复用能力而提取共享逻辑，必须保持任务中心消费者现有呈现／操作不变；
不以“必要共享适配”扩大为详情改造，也不在整理弹窗增加执行进度／结果中心。

## Implementation scope / ordered steps

1. 将当前准备／意图／摘要／提交核对中的必要能力组织为可复用的整理弹窗内容，领域读写
   仍使用原 typed API／query；复用公共 modal 的遮罩、背景 inert、锁滚、焦点和动效。
   文件页挂载背景，保留有效准备深链及认证续转；从任务中心继续时保留其合法返回上下文。
   不为视觉效果先跳页、回顶再恢复，不拷贝自动化字段／命令会话。
2. 用耐久 `itemId` 和对应准备／摘要身份管理当前文件、逐项草稿及纳入选择；同名文件不同
   路径不串项。新摘要到来时按准确身份核对当前项，失效摘要不可确认；原覆盖／清理授权
   必须随摘要或选择变化失效，不能按数组下标继承。
3. 重组每项可读方案和有界附件，技术 ID、原始理由、策略及存储检查放入展开诊断。
   常用操作／状态／下一步使用自然中文；后端英文或未知码保留于诊断，不猜测未提供的事实。
   正常情况下只呈现必要提示，真正的失败、历史不确定效果和危险影响就近可见。
4. 将本次 Files 准备中可达的修正／四类决定呈现到同一逐文件容器，保持任务／条目／版本
   绑定和合法 choices。复用现有处理组件的必要部分，避免弹窗套弹窗及跳回旧整页。
   已确认后的任务中心四类恢复继续使用其现有入口与 UI；共享部分只作保持原行为的必要提取，
   不改任务中心详情呈现或交互。
5. 整批确认复用 exact plan／selected subset／权限边界和未知提交核对。正常受理与核对证明
   成功均导航任务中心对应任务；仅本次选中项进入执行。缺少可证明的 taskId 时保留准确
   请求／执行核对上下文，显示读取／关联问题，不随意选最新任务或重新提交。
6. 保持原准备／只读历史深链、刷新／重新认证和返回可用；清理仅因本旅程替换而无消费者的
   Web 呈现。旧执行地址的已有历史读取不属于本 Task 的全面退役范围。补齐直接受影响
   测试与正式实施／接受时必要的现行旅程／架构文档协调；未验收不得先称 TARGET 已交付。

## Acceptance criteria

- [ ] AC-1 单项与批量从 Files 打开同一种居中卡片，风格对齐现有库／自动化卡片；背景
      目录、滚动、选择不丢失，提交和慢准备期间有真实且稳定的反馈。
- [ ] AC-2 每次仅展开一个主文件及其附件，页码和文件准确；前后浏览保留逐项输入与纳入
      选择。同名异路径、混合就绪／未就绪、文件夹／混选、0 项及现有上限范围可辨。
- [ ] AC-3 默认能直接读懂作品、来源、目标、操作、附件和当前问题；技术细节展开可查。
      桌面、390px 和矮窗口布局协调，无横向页面溢出；正文独立滚动，标题及底栏可达。
      以实际同视口画面和操作验收，不能仅靠有 dialog／没有溢出证明美观。
- [ ] AC-4 识别／元数据／分类／冲突修正可在当前文件完成；明确保存并分析，保存本身不
      执行。规则映射缺失、无候选、Provider 失败和无权限提供准确下一步；不新增任意身份／
      任意目标注入，不允许独立改下游策略改变 RecognitionType。
- [ ] AC-5 新分析／翻页／迟到响应不串文件或覆盖草稿；摘要过期、来源变化、并发改动、
      历史读取未完成时不可确认旧证据。批次选择和危险授权严格绑定当前精确摘要。
- [ ] AC-6 最终可清楚核对将执行的文件子集和影响；翻页／查看／关闭／保存／分析均零媒体
      mutation。确认只提交所选就绪项，已受理、已完成、不确定及未选择兄弟不重放。
- [ ] AC-7 提交在途显示“正在提交…”并禁止重复确认；确认受理成功与未知响应核对成功
      都关闭整理弹窗、进入任务中心准确 Task 并打开现有详情；流程状态
      与文件结果独立，任务仍排队／运行时不显示为整理成功。新旅程不去独立执行结果页。
- [ ] AC-8 未知准入／确认、网络断开、关闭重开、刷新和重新认证不重复创建／执行。
      可继续工作重开原准备；结束工作及失败项的只读与新发起边界、仍健康兄弟的合法确认保持。
- [ ] AC-9 Escape、Tab 焦点约束、回焦、背景锁滚、关闭／浏览器后退及 reduced-motion 可用；
      未保存输入／在途提交／未知命令按现有规则保护，不能通过关闭自动取消或丢失核对。
- [ ] AC-10 媒体库页不新增整理；普通文件操作及库／自动化配置弹窗无回归。原 RBAC、
      immutable pins、并发 fencing、审计脱敏、Storage confinement、仅 Executor mutation 与
      RecognitionType C 使用命名／分类 A 后仍为 C 保持。
- [ ] AC-11 10 项均需候选确认时，完成 10 次独立候选选择与 10 次明确保存／分析，逐项
      新方案可读且返回不丢状态；只有最后一次“确认整理 10 项”准入精确执行。测试观察
      操作与执行边界，不以底层请求次数等同用户动作。
- [ ] AC-12 任务中心详情布局、内容、进度、结果、恢复 UI 与既有继续／只读摘要入口保持；
      正常与核对成功通过既有准确 Task 选择机制交接，整理弹窗不显示另一个结果中心。

## Required tests

遵循 [Workflow §6](docs/development-workflow.md#6-test-levels)；T4 是后续实施验收等级，
因为改变执行确认、子集状态和未知提交交接。下列是计划命令，不是已运行结果。

**Developer — 新增／修改及直接受影响验证**

- 在 `web/`：`npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/OrganizeRouter.test.tsx src/features/operations/OrganizePlanConfirmation.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/ui/modal-card.test.tsx`。
  新增弹窗独立测试时将其明确文件加入同一命令，覆盖逐项选择／草稿、旧响应、确认锁定、
  焦点及两种成功交接；加入上述 10 项候选确认的行为测试，断言最终确认前零执行，
  在途双击不重复执行。运行实际改动的 normalize／navigation／API 模块测试。
- 在 `web/`：`npm run typecheck`、`npm run lint`、`npm run build`，对改动文件运行
  `npx prettier --check <实际改动文件清单>`。
- 在 `web/`：`npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/manual-organize.spec.ts`，
  调整旧整页／执行页断言为新用户行为，保留原安全断言，不以减少覆盖通过。
- 在仓库根：`.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_manual_organize_execution tests.test_organize_source_history`，
  核对准入／子集／同源占用／已结束及混合兄弟边界；如确需改动其他后端适配，只加其直接
  受影响测试，不交给 Developer 全量套件。
- 在 `web/` 新增 `tests/e2e/manual-organize-dialog.python.spec.ts`，复用临时 SQLite／Local
  Storage／假 Provider 与真实 Worker 的现有 harness；运行
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts`。
  覆盖 Files→准备→10 项候选逐文件修正→一次精确确认→对应任务既有详情的真实链路，
  以及正常／未知受理核对成功交接、混合兄弟和任务详情原 UI 不变，不能仅 Node 假响应。
  按现有约定将新 Python spec 加入普通 `playwright.config.ts` 的 `testIgnore`，避免全量
  Node 假服务套件误跑；harness 扩展只限本旅程所需的隔离夹具／观察，不改产品权限。
- 仓库根：`python3 scripts/check_governance.py`、`git diff --check`。

**B — 独立验收及完整回归**

- 独立审查固定 Task Base..candidate；先复现 AC-1–12 的完整正常／异常旅程，检查请求和
  实际源／目标效果。视觉证据覆盖同视口改前／改后、桌面／390px／矮窗口、长文件名、
  多候选／多附件、加载／失败、打开／关闭中间过程及键盘操作。
- 在 `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/organize-source-history.python.spec.ts`。
  核对继续整理／只读摘要、四类恢复、成功兄弟不重放和历史未知效果的原有覆盖；已有失败
  必须复现定位，不能凭旧 PASS 或改变定位器就掩盖产品问题。
- 执行 [共享 T4 全量门禁](docs/development-workflow.md#shared-full-regression-commands)：
  Python／Web 全量质量与回归、示例／禁用依赖检查、打包及 wheel smoke、适用的安全／
  原生／重启验证。若容器路径未受影响，不要求 Docker 广域发布矩阵，B 记录影响依据；
  不把生产部署或用户媒体测试作为本 Task 的前置。
- 检查共享 modal 的库／存储／自动化入口及任务详情无回归，验证 C→A 身份、安全绑定和
  未知效果非重放；保留真实失败／跳过／不可运行门禁，不记为 PASS。

## Non-goals / frozen boundaries

不实现新的 Provider、命名／分类规则、Storage 命令、数据库 schema、任务状态、队列或
恢复引擎；不扩大跨任务批量恢复／任意历史重处理，不新增媒体库整理。保留现有发现预算、
稳定性、主文件／附件语义、准入时机和五态／独立结果；不把准入延后到确认后。
任务中心任务详情弹窗布局／内容／进度／结果／恢复 UI 均不更改；不重设计任务中心列表、
自动化／库配置表单或独立历史执行产品，不新建弹窗结果中心，
不自动忽略／取消／重试／覆盖／清理／回滚。仅因本旅程需要作必要共享适配，不进行全站
样式／路由／API 清理。推送、发布、部署和改写既有关闭结论均不在本轮授权中。

## Activation evidence and handoff

规划／激活前治理检查 PASS；原始分支 main，Task Base 固定如上，起点暂存区为空。
A 已提交 Slice53 ACTIVE、匹配 Roadmap 与 TARGET 合同，B 正式规划前再次治理 PASS。
Task／Git 可写；本轮只提交明确治理文档。预存 `mediaflow/.DS_Store` 和全部未跟踪
系统元数据、调查脚本／日志、`15`、`output/` 材料保留，未读取用户数据库、凭据或媒体。

此前独立修正 PATCH-20261109-3 仍为 B PASS／T4，原 Task Base
`fe3bd99b1cf6046ac716052e5c8ee63851c80f15`、Reviewed Head
`9d05396b02f5f1375819f630a4e7d5a5a7c2c77a`、Accepted Implementation
`7abfca505d13239b1030fee94327c18437858d48` 及失败／证据限制见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/379c3746de2c4cd31ed8a1f558f42c3d2175c2dd/TASK.md#b-final-review--pass)。
不把其接受身份并入本 Task，也不重开 Slice52。

本轮只执行文档／治理检查；产品测试未运行，以上命令均为后续实施／验收计划。
Task53.1 PLANNED 可进入实施；没有 Developer 完工报告、B PASS 或 Slice 关闭结论。

## Developer Completion Report

**Status:** READY FOR B REVIEW。修正 checkpoint 为
`31211d9ad4c4aabcf7fccc1042cc8c13af5fa008`（main，Task Base 未变）。本报告只提交
Developer 对 B 指出的 P1 的修正与受影响验证，不替代 B 的 T4 全量验收；未推送、未发布、
未部署。

### B P1 修正

- `/operations/organize/new` 不再渲染旧长整页。携带有效 `discoveryId` 的既有
  “继续整理／查看只读摘要”链接现在直接挂载同一个 `ManualOrganizeDialog`，只读取原耐久
  准备、意图与计划摘要；打开路由不提交准入、不请求分析、不执行。通用无准备地址仍保留
  原“从资源库文件页开始整理”指引，不读取也不创建任何工作。
- 接收路由消费原链接的有界 `resourceLibraryId`、Files 返回上下文与 `returnOps`：关闭回到
  准确的任务中心已选运行、原 Files 目录或普通 Files 入口；确认受理后仍通过既有
  `operationsLandingSearch` 选中返回的准确 `taskId`，打开现有运行详情。任务中心链接、
  详情布局、内容、进度、结果与恢复 UI 未改动。
- 已结束准备在弹窗中读取原计划只读历史；原意图读取失败会显示失败阶段与合法重读动作，
  不再误报“从未生成计划摘要”，读取中也不再提前下结论。已结束状态仅保留“关闭”，不再
  出现翻页、整批复核、保存并重新分析或确认整理。
- 接收路由的关闭是真实导航；显式“放弃草稿并关闭”现在使用与任务交接相同的单次放行，
  避免在 reduced-motion 或跳过草稿状态后仍被旧草稿 guard 阻塞。
- 删除旧创建工作区的 1400 余行呈现与旧页测试，改为接收路由／同一弹窗的直接回归；
  `OrganizeCreationPage` 名称保留给稳定路由。未新增 Provider／Storage／schema／任务状态／
  恢复引擎，未改 RBAC、pin、fence、审计或 RecognitionType C 使用命名／分类 A 的映射。

### 实际验证（Developer 受影响范围）

- `web/`：`NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx
src/features/operations/ManualOrganizeDialog.test.tsx
src/features/operations/OrganizeCreationPage.test.tsx
src/features/operations/OrganizeRouter.test.tsx
src/features/operations/OrganizePlanConfirmation.test.tsx
src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/ui/modal-card.test.tsx
src/shared/navigation/destination-model.test.ts` → 8 files / **156 passed**。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run build` → passed；4 个改动文件
  `npx prettier --check` → all matched。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts
tests/e2e/operations-inventory.python.spec.ts
tests/e2e/manual-organize-dialog.python.spec.ts
tests/e2e/organize-source-history.python.spec.ts` → **48 passed（1.9m）**。其中真实
  Files→关闭→任务中心→既有“继续整理”→同一弹窗（`第 1 / 1 个`、`Two.2002.mkv`）→一次
  确认→同一 `taskId` 运行详情，以及结束后“查看只读摘要”→同一弹窗只读原摘要，均由真实
  临时 SQLite、Local Storage、synthetic provider 和真实 Worker 验证；并覆盖 10 文件逐项
  候选与未知 Execute 核对。
- `web/`：`npm run test:e2e -- tests/e2e/library-files.spec.ts
tests/e2e/deep-link.spec.ts` → **64 passed（38.6s）**，在最终 build 上验证 Files 弹窗与
  通用 Organize 指引无回归。较早合并运行的 `manual-operations.spec.ts` 也通过；最终改动
  只涉及弹窗显式放弃草稿的放行，已由上述单测与 library-files 覆盖。
- 仓库根：`python3 scripts/check_governance.py` → PASS；`git diff --check` → clean。

### 剩余风险 / 未运行

- 未运行 B 的 T4 全量门禁：Web／Python 全量回归、wheel／打包、重启、Docker 影响评估、
  同视口桌面／390px／矮窗口视觉证据与真实键盘操作验收仍由 B 执行。本报告不声称 PASS。
- 接收路由使用整理上下文背景而非任务中心活列表；关闭与受理交接均回到准确任务中心
  已选运行。视觉连续性与返回体验仍应由 B 在同视口旅程中核对。
- 新 Python 验证使用临时 Local Storage／synthetic provider；未读取用户数据库、私有配置、
  凭据或生产媒体。预存 `.DS_Store`、未跟踪调查脚本／日志／`15`／`output/` 材料保持未动、
  未提交；本轮未推送或发布。

## B Review Result

**FIX REQUIRED — B 独立复核，2026-11-09。** 当前文件的冲突决定修正通过；原 AC-4
要求的无候选元数据修正仍未接入当前弹窗。继续 Task53.1，Base、范围与 T4 不变。

### 审查范围与已通过修正

- Branch：`main`；固定 Base：`95c24cd0a3cc51acd6143e37e72371445cb15a72`；
  Reviewed Head：`6a5c10c87639535d6219f86d4db1c9827a3902fc`；
  修正实现：`16b949fcd649498b03bd8d0c15289817d471cfa3`；
  测试补强：`98596bb2a2feabf1fbd143ff647514de90c65030`。
- 结合此前完整审查，重新核对完整 Base..Head 清单，并审查新增 10 文件差异：原生问题
  条目关联、投影、typed normalization、共享决定组件、弹窗挂载、测试与夹具。未改产品代码。
- 真实 Python 回归 **3 passed**：10 项候选保存与一次精确交接、未知提交核对、真实目标
  冲突重命名。冲突用例验证决定／分析不执行、最终确认后保留原目标并生成重命名目标，
  未选中的健康兄弟源／目标不变，打开准确任务详情。上一轮冲突 P1 解除。
- 继续／只读摘要入口的前轮通过记录保留；共享恢复组件默认 full 模式仍保留任务中心
  原有呈现，本 Task 的任务详情冻结边界不变。

### P1：找不到作品时，当前文件无法修正元数据并继续

对应 RO-2、Complete journey §3、Implementation step 4、AC-4、`V2-OPS-018`。

**完整操作与实际结果：** 在现有隔离 Python harness 中，从 Files 打开
`Unified media source`，使用已有右键“重命名”，将 `Four.2004.mkv` 改为
`MissingFilm.2004.mkv`。选择该文件→批量整理→在当前弹窗选择已有 `Normal Movie / A`
识别类型→保存并重新分析→真实 Worker 完成分析。

弹窗此时显示“当前没有可读的元数据候选”，却没有搜索标题、年份、媒体类型或 Provider
搜索动作；未再改识别类型时保存按钮禁用，文件未就绪、不可纳入，整批已选 0 项。
“当前问题”只有英文通用失败与“request a fresh Preview for this item”，无法指导继续。
用户不能在当前文件完成修正→分析→新方案→最终确认。

关闭弹窗，经现有任务中心“元数据恢复→查看问题文件→同一文件”入口，**同一 Task** 的
既有审核区显示“等待元数据修正”，提供“搜索标题”“媒体类型”“年份(可留空)”、
“显式搜索 Metadata Provider”及“保存决策并继续安全分析”。原有能力存在，缺口在弹窗
接入；复现没有构造产品 URL、注入故障记录或改 Provider 响应。

代码根因：`ManualOrganizeDialog.tsx:1445` 仅在 `item.conflicts.length > 0` 分支挂载
`TaskItemRecoveryPanel mode="decision"`。本例 Preview 已提供准确 `problemTaskItemId`，
但 conflicts 为空，因此走通用 failure 展示。后端 NOT_FOUND 已发布 `metadata_correction`，
共享决定模式也已有该表单与保存／分析能力。缺口始于 `99328d5d` 的新弹窗实现；
`16b949fc` 接通了冲突分支，未完成原 Task 的其余当前文件决定范围，并非新增需求。

### Developer 修正指导与验收

1. 按当前文件与原生问题条目的准确关联及后端合法决定接入共享决定模式，不以冲突数量
   作为全部决定的入口条件。复用已有识别／元数据／分类／冲突能力，在同一逐文件容器
   完成原 AC-4；本轮独立复现的是无候选元数据修正，分类等可达分支仍须按原范围核对。
2. 无候选时直接说明未找到作品，在当前文件提供原有搜索标题／年份／类型及显式搜索、
   合法选择、保存／分析操作。保存后继续显示该文件的新精确摘要，最终统一确认执行。
   原始异常放诊断；任务中心消费者的布局、文案和操作保持现状。
3. 补真实入口回归：Files 正常重命名形成无匹配文件→批量整理→选识别类型→无候选→
   在当前弹窗修正为夹具已有作品的标题／年份并搜索→保存／重新分析→核对新目标→
   最终一次确认→准确任务详情。断言确认前零媒体效果、文件／决定关联准确，保留已通过
   的冲突与健康未选兄弟用例；补直接受影响的保存失败／分析失败及逐文件输入回归。
4. Developer 运行新改与直接受影响测试、静态检查，提交同一 Task 的完整修正候选。
   B 继续验收全部 Slice 结果并承担 T4 全量门禁；不拆成逐字段新 Task。

### B 本轮实际验证与证据

- 仓库根 `python3 scripts/check_governance.py`：PASS（审查前）；
  `git diff --check 95c24cd..6a5c10c8`：clean。
- `web/`：`npm run build`：PASS（297 modules，既有体积提示）。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts`：
  **3 passed（40.9s）**，覆盖上述 10 项候选、未知提交与冲突／健康兄弟完整旅程。
- 使用该构建产物、现有隔离 harness、临时 SQLite／Local Storage／假 Provider／真实
  Worker，独立完成上述元数据复现及同任务既有修正入口核对，未执行该问题文件。
- 本地证据 `.git/validation-evidence/6a5c10c8/b53-review/`：`build.log`、
  `dialog-e2e.log`、`metadata-reproduction.json`、`metadata-current-file.png`、
  `existing-metadata-correction.png`。截图为 1536×1000；JSON 保留准确发现／任务／条目
  关联、原 Preview 和既有修正区内容。详细前轮结论保留在 Git。
- 已有确定 P1，按 Workflow §6 提前 FIX REQUIRED。完整 Python／Web／E2E、wheel／重启
  等适用 T4 门禁及完整桌面／390px／矮窗口／键盘验收仍由 B 继续，未声称已通过。
  本轮测试与浏览器验证用时低于本轮总用时 50%，没有启动昂贵全量套件。

### 全部 Slice 结果重评

| 结果                        | 当前判断                                                                 |
| --------------------------- | ------------------------------------------------------------------------ |
| RO-1 逐文件弹窗             | Files 初次入口及桌面已核对；完整视觉、窄／矮窗口和键盘验收待完成。       |
| RO-2 当前文件修正与集中确认 | 候选与冲突决定通过；无候选元数据修正缺少弹窗入口，未满足。               |
| RO-3 精确任务中心交接       | 正常与未知提交本轮通过；继续／只读摘要已有前轮证据，最终候选待完整回归。 |

Task53.1 为 FIX REQUIRED；不交 Closure Packet、不关闭 Slice、不规划新 Task。
本轮只更新 TASK，预存 `.DS_Store`、调查脚本／日志、`15`、`output/` 保留；隔离 harness
与浏览器已结束，未读取用户媒体／数据库，未推送或部署。

## Developer Completion Report — P1 修正

**Status:** READY FOR B REVIEW。修正实现 checkpoint 为
`16b949fcd649498b03bd8d0c15289817d471cfa3`，测试/夹具补强 checkpoint 为
`98596bb2a2feabf1fbd143ff647514de90c65030`（main；Task Base 未变）。本报告不声称
PASS，不关闭 Slice，不替代 B 的 T4 验收；未推送、未发布、未部署。

### 本轮改动

- 后端在已有的 `publish_task_item_problem` 返回值上发布当前原生问题的精确
  `problemTaskItemId`。它进入原零变更计划文档并经现有操作员投影输出，用于打开该
  TaskItem 已有的恢复决定；没有新增 Provider、Storage、schema、任务状态、队列或
  恢复引擎，也没有放宽任何决定/执行权限。
- `ManualOrganizeDialog` 的“当前问题”在真实目标冲突时直接显示中文
  “目标已有文件”、来源、目标与“保存决定后重新分析”的下一步；后端英文失败说明
  移入“展开技术诊断”。原“纳入本次整理”在未解决时仍禁用。
- 冲突决定通过现有 typed recovery API 在当前逐文件容器内完成：保存决定随后重跑
  同一 Task 的零变更分析；决定保存与文件执行分离，最终仍只由“确认整理 N 项”发起。
  未在整理弹窗另建结果中心，未改任务中心详情布局、内容、进度、结果或恢复 UI。
- `TaskItemRecoveryPanel` 增加仅整理弹窗使用的 `mode="decision"` 与
  `onAnalysisRequested`：复用同一决定/分析会话，隐藏恢复摘要/执行区；默认
  `full` 模式的 Task Center 呈现与操作保持不变。
- Python harness 增加隔离的 `Dialog/DialogConflict.2022.mkv` 与 synthetic provider
  candidate；真实冲突旅程先复制保留来源，再从 Files 发起移动，产生真实目标冲突，
  在弹窗内保存重命名决定并重新分析，最后只确认一次。

### 实际验证（Developer 受影响范围）

- `web/`：`NODE_ENV=test npx vitest run src/features/operations/TaskItemRecoveryPanel.test.tsx
  src/features/operations/ManualOrganizeDialog.test.tsx
  src/features/operations/OrganizeCreationPage.test.tsx
  src/features/operations/OrganizeRouter.test.tsx
  src/features/operations/OrganizePlanConfirmation.test.tsx
  src/shared/ui/modal-card.test.tsx src/features/library/StorageFilesPage.test.tsx
  src/shared/navigation/destination-model.test.ts` → **8 files / 158 passed**。新增
  冲突决定失败、分析失败的安全回归；既有 10 项候选、未知提交、草稿和焦点覆盖保留。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run build` → passed；5 个改动
  Web 文件 `npx prettier --check` → all matched。
- 仓库根：`.venv/bin/python -m unittest tests.test_organize_preparation` → **33 passed**；
  `.venv/bin/python -m unittest tests.test_v2_manual_organize
  tests.test_manual_organize_execution tests.test_organize_source_history` → **104 passed**。
  新增断言证明问题计划的 `problemTaskItemId` 与同一 TaskItem 完全一致，解决后新摘要
  不再携带该关联。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/manual-organize-dialog.python.spec.ts` → **3 passed（40.1s）**（含健康
  兄弟断言后的完整复跑）；真实冲突用例该轮 **10.5s**。真实链路验证：第一次
  `Copy fixture` 保留来源并生成一个目标；第二次默认移动产生 `DESTINATION_EXISTS`；
  当前文件显示中文目标冲突并保存 `rename` 决定；决定保存与重新分析前后文件效果不变；
  新摘要后可确认。第二次同时选择健康兄弟 `DialogSibling.2023.mkv`，最终只确认冲突
  文件一项；Worker 保留原目标、移除来源并生成第二个重命名目标，健康兄弟的源文件与
  目标不变，任务中心打开本次返回的准确 Task。
- `web/`：`npm run test:e2e -- tests/e2e/library-files.spec.ts
  tests/e2e/manual-organize.spec.ts` → **63 passed（38.6s）**。
- 仓库根：`python3 scripts/check_governance.py` → PASS；`git diff --check` → clean；
  改动 Python 文件 `ruff check` → clean。

### 剩余风险 / 未运行

- B 的 T4 全量门禁、wheel／打包、重启、Docker 影响、完整桌面／390px／矮窗口视觉与
  真实键盘验收未运行；本轮测试/验证合计约 3 分钟，低于本轮总用时 30%。
- 旧持久 Preview 没有 `problemTaskItemId` 时，弹窗会明确显示“无法证明关联”并保留
  原上下文，不会按路径或时间猜测 TaskItem；该文件需重新分析以取得新关联。
- 真实冲突回归使用临时 SQLite／Local Storage／synthetic provider／真实 Worker；未读取
  用户数据库、私有配置、凭据或生产媒体。预存 `.DS_Store`、未跟踪调查脚本／日志／
  `15`／`output/` 材料保持未动、未提交。


## Developer Completion Report — 无候选元数据修正 P1

**Status:** READY FOR B REVIEW。代码 checkpoint 为
`800e4fd8c694c22366597abbf41ebf2943699eb1`（main；Task Base 未变），本报告随后的
文档 checkpoint 为最终候选 HEAD。本报告不声称 PASS，不关闭 Slice，不替代 B 的 T4
验收；未推送、未发布、未部署。

### 本轮改动

- `ManualOrganizeDialog` 的“当前问题”现在以当前文件真实关联的原生问题条目
  `problemTaskItemId` 打开共享 `TaskItemRecoveryPanel mode="decision"`，不再只以
  `conflicts.length > 0` 作为决定入口。无候选时直接说明“没有找到匹配的作品”并给出
  修正搜索标题、年份、媒体类型、显式搜索、选择候选和保存/分析的同文件路径；后端英文
  失败说明与分类仍保留在“展开技术诊断”。
- 无候选失败的元数据修正、识别、元数据候选、分类和冲突决定共用原有 typed recovery
  API 与同一 Task；保存只记录决定并请求原 Task 的零变更分析，不执行整理，最终仍只由
  “确认整理 N 项”提交精确子集。未改任务中心详情布局、内容、进度、结果或恢复 UI，
  默认 `full` 模式的任务中心呈现保持不变。
- `TaskItemRecoveryPanel` 在整理弹窗中支持由调用方按准确 TaskItem 保存决定草稿：
  搜索标题、年份、媒体类型、搜索结果、候选选择和冲突策略在翻页后保留，并按
  checkpoint/decision 身份失效；同名异路径不会串项。Task Center 不传草稿时沿用原
  本地状态行为。
- Python harness 新增隔离的 `Dialog/DialogRename.2024.mkv` 与 synthetic provider
  candidate。真实回归先在 Files 正常重命名为 `DialogNoMatch.2024.mkv`，经真实 Worker
  得到识别问题，在当前弹窗选择识别类型；随后得到无候选元数据问题，在当前弹窗显式
  搜索 `DialogRename`/2024、保存修正并重新分析，最后只确认一次准确任务。
- 修复本 Task 冲突回归留下的合法等待兄弟任务影响后续 `operations-inventory` 首行
  假设：该测试改按自身 `0 / 0 项` 证据选择 seeded indeterminate run，仍验证“总数未知”
  且不伪造分母；不是放宽产品断言。

### 实际验证（Developer 受影响范围）

- `web/`：`NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx
  src/features/operations/ManualOrganizeDialog.test.tsx
  src/features/operations/OrganizeCreationPage.test.tsx
  src/features/operations/OrganizeRouter.test.tsx
  src/features/operations/OrganizePlanConfirmation.test.tsx
  src/features/operations/TaskItemRecoveryPanel.test.tsx
  src/shared/ui/modal-card.test.tsx src/shared/navigation/destination-model.test.ts`
  → **8 files / 160 passed**。新增无候选当前文件修正、逐文件输入跨页保留、决定保存
  失败和分析失败零执行回归；既有 10 项候选、冲突、未知提交和焦点覆盖保留。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run build` → passed；5 个改动
  Web 文件 `npx prettier --check` → all matched。
- 仓库根：`.venv/bin/python -m unittest tests.test_v2_manual_organize
  tests.test_manual_organize_execution tests.test_organize_source_history` → **104 passed**。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts
  tests/e2e/manual-organize-dialog.python.spec.ts
  tests/e2e/organize-source-history.python.spec.ts` → **50 passed（2.2m）**。新真实用例
  **7.9s**：Files 重命名→批量整理→识别类型保存/分析→无候选元数据修正→显式搜索与
  保存/分析→新目标可核对→一次确认→准确 Task 详情；确认前源文件仍在、目标不存在，
  保存/分析请求前后零 Execute，Worker 完成后来源移除并生成 `DialogRename (2024)` 目标。
- `web/`：`npm run test:e2e -- tests/e2e/library-files.spec.ts
  tests/e2e/manual-organize.spec.ts` → **63 passed（39.2s）**。
- 仓库根：`python3 scripts/check_governance.py` → PASS；`git diff --check` → clean；
  `ruff check scripts/operations_inventory_harness.py`、`py_compile` → clean。
- 本轮测试/验证合计约 5 分钟，低于本轮总用时 30%。

### 剩余风险 / 未运行

- B 的 T4 全量门禁、wheel／打包、重启、Docker 影响、完整桌面／390px／矮窗口视觉与
  真实键盘验收未运行；本报告不声称 PASS。
- 旧持久 Preview 没有 `problemTaskItemId` 时仍会显示“无法证明关联”并保留原上下文；
  该文件需重新分析取得新关联，不按路径或时间猜测 TaskItem。
- 真实回归使用临时 SQLite／Local Storage／synthetic provider／真实 Worker；未读取
  用户数据库、私有配置、凭据或生产媒体。预存 `.DS_Store`、未跟踪调查脚本／日志／
  `15`／`output/` 材料保持未动、未提交。
