# NO ACTIVE IMPLEMENTATION TASK

PATCH-20261111-5 已由 B 独立验收 PASS。下方保留本次完整 Task／审查检查点，
不是活动实施任务；后续收尾以此固定检查点恢复简短指针。

## Accepted Task PATCH-20261111-5 — 任务详情整理入口收敛与提示留白

用户先授权调查，再授权独立 Task 规划；规划提交于
`21132098d2bc4484ad2da48a41632d5b2d861c16`。2026-11-11 用户明确“激活Task”，
现移除草案／无活动实施通知，正式授权本 Task 实施。原 ID／Base／目标／范围、
Medium／T3 和 Developer／B 测试分工保持。Developer 已完成实现；B 独立审查完整
Base..候选、运行受影响验收并核对实际截图，结论 PASS，详见下方 B Final Review。
本次未启动其他代理、推送或部署。

Authority: 用户本轮独立修复范围；遵循
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。
上一独立修复 PATCH-20261111-4 的
[固定 B PASS](https://github.com/kentinya/mediaflow/blob/5ad944f079f617036393440e8e6802d7ee6c7414/TASK.md#b-final-review--patch-20261111-4-pass)
保留原范围、结果及验证限制；不重开 Slice54，其 PASS / CLOSED、Base／接受 Head、
SLICE／Roadmap／Progress 不变。

```text
Task ID: PATCH-20261111-5
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PASS
Task Base: 436117e0588d30794dc3ee17d4fc1d0988a79442
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: IMPLEMENTATION USER AUTHORIZED ON 2026-11-11
```

### Goal and actual gap

任务中心 → 打开已整理成功任务详情 → 直接阅读流程、独立文件／附件结果与就地证据，
无需再进入另一个准备摘要或看到重新发起整理的重复入口。只有仍需确认／处理的工作
保留相应的现有合法摘要与继续动作。查看失败／取消／混合结果时，真实原因、阶段、
已完成／不确定效果及证据继续可读，不因删入口误报成功。

源码调查确认：

- `OperationsLanding.tsx` 的 `RunDetailFacts` 对所有非空 `filesPreparation` 展示
  “文件整理准备”。`continuable: false` 时固定显示结束说明、“查看只读摘要”和
  “从文件页重新发起”，未区分正常完成与异常结果，成功任务因此也带有重复操作区。
- “查看只读摘要”导航至 `/operations/organize/new`，`OrganizeCreationPage.tsx`
  将任务中心背景换成“整理所选文件／逐文件整理准备”接收页，再打开
  `ManualOrganizeDialog`，所以这不是保留原列表背景的就地查看。
- `StatusBanner` 以 `section.mf-status` 输出，公共样式原有 `padding: 16px 20px`；
  `styles.css` 的 `.mf-organize-dialog-body section` 优先级更高，将其覆盖为
  `padding: 10px 0`，使警告框文字紧靠棕色左边框；该规则也影响其他整理提示。
- 已有测试明确要求已结束任务保留这两个入口；其中真实 Python 浏览器旅程
  `initial manual preparation remains reachable from Task Center` 在执行完成后点击
  “查看只读摘要”。修复时要更新入口预期，同时保留其只读历史／零重放的实质覆盖。

以上是源码及测试静态调查，尚未作当前构建的浏览器视觉复现，未声明产品测试通过。
适用 `V2-OPS-005/007/008/018/019`、`V2-UX-005/006`、`V2-TASK-012–014`，以及
[任务／逐项恢复完整旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[整理弹窗完整旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)、
[任务中心页面约定](docs/task-center-page-spec.md#手动受理与确认)、
[整理弹窗架构边界](docs/architecture.md#current--manual-organize-dialog-slice53-pass--closed)。
用户本次授权收敛上述现有呈现；不改变历史记录、继续资格或执行安全语义。

### Implementation scope and ordered guidance

1. 在 `RunDetailFacts` 删除“查看只读摘要”和“从文件页重新发起”两个入口；
   `filesPreparation` 不存在或后端 `continuable` 不为 true 时，不渲染整个
   “文件整理准备”区域，包含标题、结束提示和空按钮容器。正常完成、失败和取消
   一致处理该重复区域；这些状态的真实结果与失败事实仍由原任务详情／文件证据呈现。
   不新增一条替代性“已结束／去文件页”提示或折叠版重复入口。
2. 明确“需要时显示”的边界：已有准确关联且后端允许继续时保留现有“继续整理”及
   其原 discovery／library／returnOps；等待确认可继续到准确摘要。四类处理中的
   决定→分析→摘要→确认及未知提交核对保留原入口。不能依据 Task completed 推定
   文件全成功，不能仅因 failed／cancelled 再挂一个只读摘要按钮，也不另造前端
   继续资格／通用恢复判断。排队／执行中的既有继续资格不在本 Task 重新设计。
3. 收窄整理弹窗的通用 `section` 样式，避免覆盖 `StatusBanner` 的水平内边距与
   提示框边界。删除入口后，正常从已结束任务详情查看结果不会再打开只读摘要弹窗；
   本项间距修复针对仍由“继续整理”、资源库 Files 整理和已有历史深链接共用的
   `ManualOrganizeDialog` 提示框，不要求保留或重新添加已删除的入口。
   原只读深链接、加载／读取失败、未就绪和明确确认中的 info／warning／
   error 提示均有协调留白，长路径与多段文字可读；正常业务分区的布局仍清晰。
   优先排除 `.mf-status` 或明确限定业务分区，不通过全站增加特异性或 `!important`
   叠补，不删除警告来隐藏间距问题。
4. 保留准确历史准备深链接及其只读能力，包括没有计划、计划读取失败与页内重新读取；
   已结束工作不得重新选择、修正、分析或确认。普通文件页的整理入口保留。
   本 Task 用移除正常任务详情的多余跳转消除用户报告的背景切换路径，不重构
   `OrganizeCreationPage` 路由背景，也不承诺旧深链接或保留的“继续整理”改为同页弹窗。
5. 更新旧入口预期并补充直接受影响测试。只读历史用已有准确 preparation URL
   验证，不为测试增加隐藏产品入口；确认后的正常旅程在原 Task 查看结果，不能
   通过删掉末尾只读断言同时丢失零写／零重放覆盖。视觉检查包括已结束任务详情
   原列表背景、普通 Files 整理弹窗及旧只读链接的警告留白。

允许产品文件限于 `OperationsLanding.tsx`、`shared/ui/styles.css` 及确有必要的
`ManualOrganizeDialog.tsx` 呈现调整；测试限于直接受影响的 operations／organize 单元、
浏览器用例及最小本地 fixture。无需改后端、API 类型、继续资格、路由或共享 modal 行为。
若发现必须改变这些契约，先交 B 重评，不借本 Task 扩展实现。

### Acceptance criteria

- [ ] 已结束任务详情无两个旧入口、无“文件整理准备”标题／结束说明／空区；正常成功、
  completed 但文件失败或未知、failed、cancelled、无准备关联均有覆盖。
- [ ] 流程与文件／附件结果、失败／取消事实、效果未知／结果缺失保持真实；逐文件就地
  证据、记录／导出及历史计划说明可达，不重放成功兄弟项或不确定效果。
- [ ] 未结束且后端允许继续的准确准备入口保留；待确认与四类原生恢复仍能检查摘要并
  明确确认一次，完成后回到原 Task；轮询转终态后旧操作区消失，不自动跳转或提交。
- [ ] 任务详情的打开／关闭／刷新保持原视图、日期／页／滚动与合理焦点。删除入口后的
  正常完成查看全程留在任务中心，不打开只读摘要弹窗、不切换到整理准备背景；
  不引入新的背景路由。
- [ ] 原只读深链接、刷新／认证恢复仍读取准确准备；有计划／无计划／读取失败可辨，
  仅允许安全重读，不重新分析、确认或执行，未知请求仍核对原提交身份。
- [ ] 1536px 桌面、390px 窄屏及矮窗口中，提示标题／正文与棕色条有清楚水平留白，
  多段文字、长路径、错误和关闭动作可读可达；提示框与正常业务分区均无整页溢出。
  从保留的“继续整理”、Files 整理及准确历史深链接验收共用弹窗，不通过恢复已结束
  任务的旧入口来验证间距。
- [ ] 移除入口及改变提示样式不增加业务写请求、Provider／媒体 Storage I/O；普通 Files
  整理仍可新发起，既有草稿、精确确认、危险授权和未知提交非重放保护不变。

### Required tests

激活后先运行根目录 `python3 scripts/check_governance.py`。下列 Web 命令 cwd 为 `web/`。

#### Developer — affected tests

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run typecheck
npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts tests/e2e/operations-inventory.python.spec.ts
npx prettier --check src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/shared/ui/styles.css tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts tests/e2e/operations-inventory.python.spec.ts
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable from Task Center|PATCH-20261111-5'
```

静态检查追加实际修改文件。根目录运行 `git diff --check`。新增浏览器回归可放在上列
文件并以本 Task ID 命名，覆盖提示框真实留白／长文与终态区域消失；不能只断言
按钮隐藏或 CSS 数值。查看桌面／390px／矮窗口截图并记录实际结果。测试只用隔离
假服务或真实 Python／临时 SQLite／临时 Local 根，不使用运行数据库或用户媒体。

单元覆盖终态矩阵、可继续／无关联、轮询变化、历史计划读取失败及不重复命令。
直接受影响的原生手动旅程必须保留 Files 准入→离开→Task 继续→明确确认→原 Task
真实结果；结束后再用准确旧链接验证只读无重放，不依赖已删除按钮。

#### B — independent acceptance

审查固定 Task Base..候选全部差异，独立复核上述旅程、零写请求和截图；执行上述
受影响单元／Node E2E，以及 `npm run typecheck`、`npm run lint`、
`npm run format:check`、`npm run build`。在当前构建上执行：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable from Task Center|PATCH-20261111-2|PATCH-20261111-5'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

核对五类 Task 流程与独立文件效果、四类同 Task 恢复、原计划只读、精确确认和原请求
核对；对无计划／读失败的旧深链接保留明确下一步。视觉验收涵盖成功详情与混合结果、
Files 弹窗及旧只读卡的提示留白／滚动／键盘关闭，不能将旧深链接自身已有接收页背景
误判为本 Task 要求改成任务中心背景。证据留于
`.git/validation-evidence/<candidate>/patch-20261111-5/`，保留原失败与实际限制。

T3 依据为已有入口、异步状态和共享整理弹窗呈现的消费者集成；不改变权限、schema、
Storage、后端确认／调度／执行协议。不要求全 Python／全 Web／全 E2E、wheel 或 Docker
矩阵；发现实际安全契约变更须重评，不能以当前等级跳过新增风险。

### Non-goals and documentation boundary

不删除资源库文件页、不删除真实历史计划／证据或后台 API，不退役准确历史深链接；
不新增“仅异常时查看只读摘要”的第二套判断、不改 Task 状态／统计／执行资格、不做
整个任务中心／整理路由／全站提示框重设计。PATCH-20261111-4 的就地证据位置和
同文件输入保留保持；SLICE／Roadmap／Progress 与已接受 Slice 身份不变。

规划／激活仅更新 TASK.md，不提前把 CURRENT 产品文档写为已实现。B PASS 后，按实际
结果最小协调 task-center-page-spec、Product Experience 以及 V2 Requirements／
Architecture 中直接提及已删除入口的现行措辞；保留原接受身份与安全契约，不把本次
独立呈现修复写成重开或关闭 Slice。

### Workspace and handoff

规划基线：`main`，HEAD／Task Base 如上；治理预检 PASS，暂存区原为空。预存
`mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、`.explore_adapter_block.py`、日志、
`15`、各目录系统元数据和 `output/` 调查材料原样保留，不纳入规划提交；不读取
私有配置／运行数据库／用户媒体，不推送或部署。

激活前 HEAD：`21132098d2bc4484ad2da48a41632d5b2d861c16`，分支仍为 `main`；
Base..HEAD 仅含本 Task 规划文档，没有中间产品变更，原 Task Base 保持。
激活前治理检查 PASS，暂存区为空，预存工作区文件同上保留。

Developer 在下列检查点交 READY FOR B REVIEW；B 已完成本 Task 适用验收并给出 PASS。
收尾恢复简短无活动实施通知及固定审查指针，不规划授权外工作。


### Developer Completion Report

**候选检查点：** 本提交，任务 Base `436117e0588d30794dc3ee17d4fc1d0988a79442..`；
分支 `main`；状态 READY FOR B REVIEW。

**变化：**

- `web/src/features/operations/OperationsLanding.tsx`：`RunDetailFacts` 只在后端为
  该 Task 关联的 `filesPreparation.continuable === true` 时渲染“文件整理准备”及
  “继续整理”。已结束（completed／failed／cancelled）、结果混合或后端不可继续、
  以及无准备关联时，整个区域（标题、结束说明、空动作容器与两个旧入口）都不渲染；
  任务详情原有流程、处理进度、文件结果、条目证据与记录保持。未新增替代性结束提示、
  只读摘要第二判断或前端继续资格。
- `web/src/shared/ui/styles.css`：将整理弹窗的业务分区 padding 选择器收窄为
  `section:not(.mf-status)`，让共享 `StatusBanner` 恢复自身 `16px 20px` 内边距与
  左边框间距；未使用 `!important`、全站特异性叠加或删除提示。
- `web/src/features/operations/OperationsInventory.test.tsx`：无关联运行不再出现准备区；
  更新原已结束运行用例，明确无标题／说明／“查看只读摘要”／“从文件页重新发起”；
  新增终态矩阵（completed 成功、completed 含失败／未知／缺结果、failed、cancelled、
  无关联）、可继续入口在自身轮询转终态后消失且全程仅 GET、既有“继续整理”与文件结果
  可读。历史计划读取失败与无计划仍由既有 `OrganizeCreationPage.test.tsx` 覆盖。
- `web/tests/e2e/operations-inventory.python.spec.ts`：在原真实 Files 准入→离开→
  Task 继续→明确确认→原 Task 结果旅程后，断言已结束详情无重复准备区与旧入口、原
  列表仍在；再用同一准确历史深链接经认证恢复只读弹窗，验证无确认／整批复核／重新
  分析、原计划仍可读且零重放；在 1536、390 与 1536×600 实际截图并测量 warning
  提示左右留白、内部无横向溢出。未改后端、API 类型、路由、继续资格或共享 modal。

**实际检查（cwd `web/`；未新增依赖）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx` | 5 文件通过，120/120 测试通过（无 skip） |
| `npm run typecheck` | 通过 |
| `npx eslint`（实际改动的 operations 单元、两个 E2E 与 `operations.spec.ts`） | 通过，无输出 |
| `npx prettier --check`（同组件／测试／样式／E2E 文件） | 通过 |
| `npm run build` | Vite 构建成功；仅既有 chunk >500 kB 提示 |
| `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts` | 40/40 通过，22.0s |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable from Task Center\|PATCH-20261111-5'` | 1/1 通过，10.8s；真实 Python／临时 SQLite／Local fixture |
| 仓库根 `python3 scripts/check_governance.py` | PASS |
| 仓库根 `git diff --check` | 无输出 |

已查看实际截图：`ended-task-detail-1536.png` 中已结束详情只保留真实流程／结果且原列表
背景仍在；`ended-history-1536.png`、`ended-history-390.png`、
`ended-history-short.png` 中 warning 标题／正文与棕色左边框有清楚水平留白，390px 与
矮窗口无整页横向溢出，关闭动作可达。截图在本轮 `web/test-results/PATCH-20261111-5/`
（忽略目录），B 需在稳定证据目录保留自己的最终截图。

**剩余风险／限制：**

- 本 Task 未运行 B 负责的全量 Web／Python／E2E、wheel 或 Docker 矩阵；也未运行
  `manual-organize-dialog.python.spec.ts`、`task-flow.python.spec.ts`。未改后端、
  权限、schema、Storage 或执行协议，由 B 判定适用门禁。
- 共享整理弹窗的其它真实 warning／error／info 状态由同一 CSS 规则覆盖；开发者只
  实际截图了已结束 warning 状态，B 应在保留的“继续整理”、Files 整理与历史深链接
  上继续核对长路径、多段文字和滚动／键盘关闭。
- 后端 `_operations_run_files_preparation` 的说明仍描述已结束流程“保留只读摘要链接”；
  本 Task 未授权改后端注释，待 B PASS 后按结果最小协调现行文档措辞。
- 设计上仍保留“继续整理”继续打开稳定的 `/operations/organize/new` 接收页；本 Task
  只移除已结束详情的重复入口，未把该继续旅程改为同页弹窗。
- 未读取私有配置、运行数据库或用户媒体；未推送、未发布。

### B Final Review — PATCH-20261111-5 PASS

```text
Reviewer: B
Date: 2026-11-11
Task Type: STANDALONE MINOR BUG
Reviewed Base: 436117e0588d30794dc3ee17d4fc1d0988a79442
Reviewed Head: 408b5303cdabad202188ed252ceaa741159cdeaa
Decision: PASS
Task blockers: NONE
Authorized bug acceptance complete: YES
Next: NO ACTIVE IMPLEMENTATION TASK
```

**完整结果核对：** Base..Head 共五个文件，包含 Task 规划／激活／澄清及一个实现
检查点。产品只改 `RunDetailFacts` 的准备区出现条件和整理弹窗业务分区 CSS；
另外两处为直接受影响测试。未改变后端、路由、API 类型、状态／继续资格、执行与
原请求核对。Slice54 已 PASS / CLOSED，本 Task 无父 Slice，不重新验收或关闭旧 Slice。

真实入口旅程：从 Files 选择 Two.2002.mkv 整理，离开未确认弹窗，在任务中心打开
该任务，刷新／认证后继续到原准备，明确确认一次并由 Worker 完成。完成后的详情
不再显示“文件整理准备”、结束提示及两个旧入口，原列表背景、真实结果和就地文件
证据仍在。再打开该旅程实际保存的准备地址，认证后读取原计划历史，无第二次 Execute。
没有猜造产品入口或通过恢复被删按钮来验收历史只读。

终态矩阵、无关联及轮询变化由单元覆盖；真实混合成功／失败、流程自身失败及取消
由 Python 旅程覆盖。四类同 Task 决定／分析／摘要／明确确认、策略允许覆盖的
单独授权、十文件一次批量确认及未知 Execute 在兄弟重分析后核对原请求均通过。
原计划读取失败／重读及无计划事实由当前受影响单元验证。

**B 实际执行，cwd `web/`：**

| 检查 | 实际结果／日志 |
|---|---|
| Task 指定五个 operations／organize 单元文件 | 120/120，5 文件，29.23s；`unit.log` |
| `npm run typecheck && npm run lint && npm run format:check && npm run build` | 全部通过，22.19s；`quality-build.log` |
| `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts` | 40/40，23.28s；`node.log` |
| 下列真实 Python 浏览器组合 | 18/18，77.14s；`native.log` 与每项 `trace.zip` |

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/task-flow.python.spec.ts --grep 'initial manual preparation remains reachable from Task Center|PATCH-20261111-2|PATCH-20261111-5|ten per-file|unknown Execute response|real destination conflict|follows the completed walk|reports the preparation|missing metadata candidate|keeps the exact admitted|unknown original submission|mixed file population|saved flow failure|acknowledged cancellation' --trace on --output=../.git/validation-evidence/408b5303/patch-20261111-5/native
```

组合覆盖 Task 原定八项 `manual-organize-dialog`、三项 `task-flow`、六项四类恢复／
覆盖授权与一项初始准备旅程，未漏选测试。Node 结果也保存到同一证据根的 `node/`。
独立执行治理检查与完整 Base..Head `git diff --check` 均通过。

**视觉核对：** 查看本次实际生成的成功详情、1536／390／1536×600 历史警告截图，
确认文字留白、长目标换行、正文及关闭可达；同时查看 trace 中 Files 准备 info、
逐文件决定、分析反馈、执行结果未知 warning 与 Task“继续整理”实际画面。
原有滚动／键盘退出／返回用例通过；旧地址仍有自己的接收页背景，正常完成详情
不再进入它，符合本 Task 的明确边界。

证据根：`.git/validation-evidence/408b5303/patch-20261111-5/`，含原始命令日志、
trace、`visual/` 截图。以上是本机隔离 Python／临时 SQLite／Local 与 Node 假服务
验证，不是生产服务或远程 CI。复核以代码、用户旅程和视觉结果为主；测试及质量／
构建命令分别计时，累计约 152 秒，少于本轮复核总用时的 50%。

全部指定验收通过，无失败或 skip。保留非失败输出：单元环境的 scrollTo 未实现
提示、Vite chunk 大小提示、Python publication-failure 用例主动注入的
OperationalError（该用例验证真实文件效果旁的 failed 流程，最终通过）。不要求
全仓 Python／Web／E2E、wheel 或 Docker 矩阵；本次没有相关执行路径变化。

**收尾：** 本 Task 授权结果全部满足，不增加下一 Task。后续只最小协调已删除入口的
CURRENT 说明并恢复无活动实施通知；原 Slice54、上一独立修复接受身份和预存脏文件
保持。不修改运行配置／用户媒体，不推送或部署。
