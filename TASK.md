# NO ACTIVE IMPLEMENTATION TASK

PATCH-20261111-4 已通过 B 最终复核；下文保留完整固定审查记录，随后根 Task 压缩为检查点指针。

# Task PATCH-20261111-4 — 任务详情文件证据就地展开

用户先授权调查，再授权规划；规划提交于 `4ec6cbf55fd936824790585d2280325b2cca36a6`。
2026-11-11 用户明确“激活Task”，正式授权本 Task 实施。
原 ID／Base／目标／范围、Medium／T3 和 Developer／B 测试分工保持。初次候选
`b407dbdba80cb1e9cfd4fb22b37edd3b95a7b2bb` 曾因筛选清空未提交标题被 B 退回；
修正候选 `ff8f3a699d2d6a1a27a2a221299cec9c616207ed` 已经 B 独立完整复核 PASS。
历史返工与最终结果分别保留于下文，本独立 Task 完成。

上一独立修复 PATCH-20261111-3 的
[固定 B PASS](https://github.com/kentinya/mediaflow/blob/7bf958fb1b61b358c5f3f0305fa5137b2caa38f2/TASK.md#b-decision--patch-20261111-3-pass)
保留原范围与结果。本 Task 不重开 [Slice54](SLICE.md)，其 PASS / CLOSED、原始
Base／接受 Head、Roadmap／Progress 和延期保持。

Authority: 用户授权的独立呈现修复；生命周期遵循
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

```text
Task ID: PATCH-20261111-4
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PASS
Task Base: 42e666ca6c600cbaf93625dd5b389763c28ddade
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: IMPLEMENTATION USER AUTHORIZED ON 2026-11-11
```

### Goal and actual gap

任务中心 → 打开任务详情 → 点击某文件“查看证据”，在该条目正下方阅读它自己的
处理结果、来源／目标、处理经过及已有恢复操作，关闭后继续查看相邻条目，不必到
整份列表末尾寻找。保留现有一次查看一个文件的语义。

实际根因：`web/src/features/operations/RunDetailTabs.tsx` 的 `inspectItem` 只更新 URL
所属 `evidenceItem`；`RunEvidenceSection` 是整个 `RunItemsSection` 后的兄弟区域，
而主条目行按钮只调用 `onInspectItem(item.itemId)`，所以任意行的证据都落在列表末尾。
操作记录“查看条目”、问题文件入口及批量分析子项也复用该条目选择链路。
现有 `RunDetailTabs.test.tsx`／`operations.spec.ts` 验证内容及开关，未验证相邻位置；
另有 `item=item-9` 且列表不含该文件的有效证据用例，不能因改为行内而丢失。
以上为源码／现有测试静态调查，本轮未声明浏览器复现或产品测试通过。

适用约束：`V2-OPS-005/008/012`、`V2-TASK-003/012–014`，以及
[完整任务／逐项恢复旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[任务正文与文件证据](docs/task-center-page-spec.md#current--任务正文与文件证据)、
[当前投影边界](docs/architecture.md#current--v2-operations-projection-foundations42-amended48)。
本修复只改变现有文件证据的位置，不改变这些已接受结果或安全边界。

### Implementation scope and ordered guidance

1. 在 `RunDetailTabs.tsx` 将证据选择与呈现位置协调起来：目标在当前服务器页时，
   在对应主条目之后呈现唯一证据区域，优先使用合法表格展开行，跨全部 8 列；
   列表下方不再保留重复面板。复用 `RunEvidenceSection` 和既有 query／恢复组件，
   不复制证据读取或产生第二套恢复状态。按钮暴露展开状态及与区域的关联；保留关闭。
2. 处理页外／筛选隐藏／列表空态、读取中或读取失败的选中条目：保留原 `run + item`
   精确读取，在主条目区域、表格之前显示该文件的独立证据卡，说明其不在当前列表中
   或列表尚不可用。读取成功后才展示真实文件名／路径；加载或拒绝不虚构文件信息。
   不在分页结果中插入伪造业务条目、不改计数、不清除筛选／游标、不遍历全量找页。
   目标回到当前页后只保留对应条目下的一个面板。
3. 保留 URL 所属选择、刷新／前后退／认证恢复、操作记录和问题／批量入口的准确性。
   页内切换、轮询更新导致位置迁移或列表暂不可用时，不能重发决定／分析／确认、
   丢失既有未知提交核对记录，或把旧文件的迟到证据／表单显示到新文件；检查组件
   key 和挂载边界，保留原账号／任务／条目隔离及既有恢复能力，不另造恢复协议。
4. 只在必要范围补充 `web/src/shared/ui/styles.css`：证据明显从属于上一条目，
   长路径、诊断、附件及恢复动作可读；390px 下不因表格横向最小宽度把正文／关闭
   动作推到不可读的远处。表格自身可继续内部横向滚动，任务卡和整页不被撑宽。
   关闭回到合理的原触发焦点；正常背景刷新不反复抢焦点或滚动至列表底部。
5. 补充位置、边界与浏览器验证，运行下列受影响检查后提交一个完整实现检查点，
   状态为 READY FOR B REVIEW。若实际必须改变后端或恢复协议，先交 B 重评范围／等级。

允许文件：上述组件／必要样式，直接受影响的 operations 单元／浏览器测试及最小假服务
fixture；确需调整 URL／query 的传参时限于保持现有契约。不得借机重构整个任务详情。

### Acceptance criteria

- [x] 多条目列表中，首／中／末任意行打开后，唯一证据紧跟所选条目、位于下一业务
  条目和分页／批量区之前；切换到另一个文件后位置和内容都跟随新文件，关闭可回看原行。
- [x] 保留处理结果→来源／目标→处理经过→实际原因及可展开诊断、附件、日志／审计、
  既有四类恢复动作；流程完成不变为文件成功，未知效果／缺失 Result 不被改写。
- [x] 有效页外深链接、筛选后隐藏、空页、列表错误仍可独立查看准确文件；权限拒绝、
  不存在、证据读取失败在同一位置显示真实原因及既有安全下一步，不串到邻项。
- [x] 筛选／翻页／刷新／前后退／重认证及操作记录、问题文件、批量子项入口保持原
  准确任务／文件上下文；列表更新不吞掉证据或制造两个面板，不伪造条目数或自动遍历。
- [x] A→B 快速切换且 A 迟到、同文件轮询、页内／页外迁移均无错配；既有在途命令、
  未知提交核对和账号隔离保持，打开／关闭／重排证据零写命令、零媒体变更、零自动重放。
- [x] 1536px 桌面、390px 窄屏及矮窗口可读可操作；展开不使相邻列重叠或整页横向
  溢出。键盘可展开／关闭、状态可感知、焦点合理，现有任务卡关闭／返回行为保持。

### Required tests

#### Developer — affected tests

激活后先运行根目录 `python3 scripts/check_governance.py`。以下命令 cwd 为 `web/`：

```sh
npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/run-detail-state.test.ts src/features/operations/run-detail-query.test.ts src/features/operations/OperationsInventory.test.tsx
npm run typecheck
npx eslint src/features/operations/RunDetailTabs.tsx src/features/operations/RunDetailTabs.test.tsx tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npx prettier --check src/features/operations/RunDetailTabs.tsx src/features/operations/RunDetailTabs.test.tsx src/shared/ui/styles.css tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
```

静态命令补入本轮其他实际改动文件；运行根目录 `git diff --check`。单元测试应明确验证
业务条目与证据相邻及仅一份，而非只验证区域存在；覆盖上列错误／页外／迟到与恢复核对
风险。浏览器验证可见上下关系、正文宽度、键盘与关闭／返回，检查实际截图；表格增加
展开行后，原列宽／溢出断言要仍验证业务行，不能删断言掩盖正文溢出。

#### B — independent acceptance

审查固定 Task Base..候选完整差异，复核 Developer 结果和执行输入后可复用匹配证据；
独立验证多条目就地展开、页外／列表失败降级、迟到响应及无重复命令。执行上列受影响
单元／E2E 与 `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`。
对新构建另外执行真实 Python／临时 SQLite 的现有相关旅程：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

该旅程核对真实 Task 流程／文件结果和精确恢复确认不受呈现迁移影响。所有假服务和原生
fixture 均使用隔离测试数据，不读取生产配置、用户媒体或外部 Provider。B 保留桌面／
窄屏／矮窗口截图及实际结果到稳定忽略目录 `.git/validation-evidence/<candidate>/patch-20261111-4/`。
本 T3 是前端位置与路由／异步／恢复消费者集成修复，不改后端、权限、schema、Storage
或执行引擎；无具体新增影响时不要求全 Python／全 Web／全 E2E、wheel 或 Docker 矩阵。
原生测试若发现实际安全语义改动，由 B 重评并补充适用门禁，不能以 T3 名义跳过。

### Non-goals and workspace

不增加多文件同时展开、自动定位任意服务器页、新证据接口／全局搜索、第二套恢复流程、
恢复表单改版、其他页面重设计或新配置。SLICE／Roadmap／Progress 及已接受 Slice 的
身份／Base／Head／关闭事实保持；规划／激活仅更新 TASK.md，不同步产品说明为“已实现”。

规划基线：`/Users/songzhidong/mediaflow`，`main`，HEAD 为上列 Task Base；治理预检 PASS，
TASK.md／Git 可写，暂存区原为空。预存 `mediaflow/.DS_Store` 修改以及未跟踪的 `.DS_Store`、
`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、各目录 `.DS_Store` 和 `output/`
调查材料原样保留、不纳入检查点。不读取私有配置／运行数据库，不推送或部署。

激活前 HEAD：`4ec6cbf55fd936824790585d2280325b2cca36a6`，分支仍为 `main`；
Base..HEAD 仅含本 Task 规划文档，未出现中间产品变更，原 Task Base 保持。
激活前治理检查 PASS，暂存区为空，预存工作区文件同上保留。

### Developer Completion Report

**候选检查点：** 本提交，任务 Base `42e666ca..` 之上的实现提交；分支 `main`。
状态 READY FOR B REVIEW。

**变化：**

- `web/src/features/operations/RunDetailTabs.tsx`：当前服务器页确实包含所选文件时，
  证据改为紧跟在对应主条目后的合法表格展开行（单一 `td`，`colSpan=8`），列表下方
  不再保留第二个面板；同页切换到另一文件时证据位置与内容一起跟随。页外、筛选隐藏、
  空页、列表加载中或列表读取失败时，证据仍在“主条目”区域、表格之前按原 `run + item`
  精确读取并显示独立卡，说明不在当前列表或列表暂不可用；不插入伪条目、不改计数／筛选／
  游标、不遍历其他页。打开按钮暴露 `aria-expanded` 与 `aria-controls`，关闭后焦点回到
  原触发控件，原触发入口已离开时回到同文件行按钮或“任务详情”页签；背景刷新不移动焦点。
- `web/src/shared/ui/styles.css`：仅补充证据展开行、独立卡和上下文说明的样式。展开证据
  跨全部八列，内部卡片在表格自身横向滚动时贴住左侧并限制为可视宽度，长路径、诊断、
  附件与恢复动作可换行；任务卡和整页不被撑宽。桌面、矮窗口与 390px 实际截图中证据
  标题、正文和关闭动作均可读。
- 单元测试补充：多条目首／次行打开后唯一证据紧邻所选行、跨八列、切换后位置与内容跟随、
  关闭后焦点回到原按钮；页外有效深链接、列表加载中、列表失败仍独立读取准确文件；
  A→B 快速切换后 A 的迟到证据不会出现在 B 下。原深链接证据用例改为等待列表与行内位置
  稳定后重新定位证据，保留原内容与恢复断言。
- 浏览器测试补充：1536px 下证据紧邻所选行且唯一、跨八列；1536×600 矮窗口标题与关闭
  可操作；390px 键盘打开、关闭动作横向在视口内、表格内部滚动不撑宽页面、关闭后焦点
  回到原按钮。未改后端、权限、schema、Storage、URL 契约或恢复协议。

**受影响检查（cwd `web/`；未新增依赖）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/run-detail-state.test.ts src/features/operations/run-detail-query.test.ts src/features/operations/OperationsInventory.test.tsx` | 5 文件通过，90/90 测试通过（无 skip） |
| `npm run typecheck` | 通过 |
| `npx eslint src/features/operations/RunDetailTabs.tsx src/features/operations/RunDetailTabs.test.tsx tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts` | 通过，无输出 |
| `npx prettier --check` 同组件／测试／样式／两个 E2E 文件 | 通过 |
| `npm run build` | Vite 构建成功；仅保留既有 chunk >500 kB 提示 |
| `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts` | 40/40 通过，21.7s |
| 仓库根 `python3 scripts/check_governance.py` | PASS |
| 仓库根 `git diff --check` | 无输出 |

实际检查了桌面 `inline-evidence-1536.png`、矮窗口 `inline-evidence-1536x600.png`、窄屏
`patch-file-evidence-390.png`：证据位于所选行之后，正文和关闭动作可读，390px 无整页
横向溢出。截图位于本次本地 `test-results/`（忽略目录），B 需在稳定证据目录保留自己的
最终截图。

**剩余风险：**

- 初始列表尚未返回时证据先在表格前显示，列表返回后再迁入行内，React 会重挂载证据组件；
  在途／未知恢复请求与核对记录由 landing 级会话存储保留，但尚未提交的本地决策草稿或
  临时准备缓存可能在这次位置迁移中重置。列表稳定后的同页切换不触发该迁移。
- 浏览器验证使用既有 Node 假服务与 Chromium；未运行 B 负责的真实 Python／临时 SQLite
  `task-flow.python.spec.ts`、全量 Web／Python／E2E、wheel 或 Docker 门禁。本 Task 未改
  后端、权限或执行引擎，新增影响范围内无这些门禁的具体触发点，仍由 B 判定。
- 横向贴边样式只在 Chromium 的 1536、1536×600、390px 实际视口验证，未做其他浏览器矩阵。

**工作区：** 预存 `mediaflow/.DS_Store` 修改及未跟踪的 `.DS_Store`、`.explore_adapter_block.py`、
`.mgmt.log`、`.t*.log`、`15`、`output/` 调查材料保持原样，未进入本检查点；未推送、未发布。

### B Review Result

```text
Reviewer: B
Date: 2026-11-11
Reviewed Base: 42e666ca6c600cbaf93625dd5b389763c28ddade
Reviewed Head: b407dbdba80cb1e9cfd4fb22b37edd3b95a7b2bb
Decision: FIX REQUIRED
Task blockers: B-PATCH4-01
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

**交付结果核对：** 完整 Base..Head 共 6 个文件，仅 Task、任务详情组件／样式及相关
测试。当前页证据已紧跟对应文件，页外证据仍可准确读取；桌面与 390px 的可见位置、
正文／关闭动作和键盘开关经 B 新构建浏览器验证。Slice54 已关闭且不属于本独立 Task，
其交付与关闭记录、本次 SLICE／Roadmap／Progress 均未修改。Task 尚未满足同文件
输入在筛选／位置变化后保持的要求，不能以主布局已完成代替整个 Task 验收。

**B-PATCH4-01（P1）— 改状态筛选会清空正在编辑的同文件标题。**

实际完整旅程：任务中心 → 元数据恢复 → 对现有问题任务点击“查看问题文件” →
“查看该文件证据与恢复记录” → 在“搜索标题”输入 `Operator edited metadata title` →
把条目“状态筛选”从全部改为等待处理。相同任务、相同文件仍显示，输入却变为空串。
B 使用既有 `operations_inventory_harness.py` 的 `metadata_correction` fixture、真实
Python API／临时 SQLite、新构建和 Chromium 复现；未构造新产品入口、未提交决定／整理。

原因定位：`RunDetailTabs.tsx:896` 的列表 key 包含状态筛选和分页游标；本提交将证据
及其恢复表单从列表外移入列表内，筛选变化会连表单一起重新挂载。
`TaskItemRecoveryPanel.tsx:427` 的未提交输入仍由组件本地保存，当前 Task Center 没有
接入其既有草稿传参，重新挂载后读回初始输入。Base 中证据是列表的兄弟组件，筛选不
卸载该表单；引入变更为 `b407dbdb`（2026-11-11 22:07:47 +08:00）。此次原生结果说明
影响也发生在已经加载完成的正常筛选操作，不仅是 Developer 已披露的初次列表迟到。

#### 本次修正的开发指导

1. 让同一账号／任务／文件的既有编辑上下文不随列表筛选或证据位置变化而丢失。
   可把现有草稿状态放到列表 key 之外的稳定 owner，并通过已有
   `decisionDraft`／`onDecisionDraftChange` 传递；或保持同一证据表单实例再调整其位置。
   选择与当前组件结构相符的最小修改，继续沿用原检查点／决定的草稿归属规则。
   允许为此接通 `RunDetailTabs`、`RunEvidenceSection` 与既有恢复组件的必要传参。
2. 保持本次已实现的行内位置及页外卡片。用户在同文件编辑后改变状态筛选，输入仍
   在原文件；列表先显示页外卡、读取完成后迁入行内时也保留该文件的编辑上下文。
   原有保存、分析、确认和核对继续使用已有流程。
3. 在现有 `RunDetailTabs.test.tsx` 用真实状态筛选控件补充“编辑同文件标题 → 筛选 →
   标题保留”的回归，覆盖上述位置迁移。沿用现有原生 fixture 从同一 Web 入口验证，
   不以重填输入或增加额外确认步骤替代修复。Developer 运行失败用例与原受影响计划，
   提交新候选；B 复核修正并完成下述尚未运行的原生验收。

#### B 实际验证与证据

证据目录：`.git/validation-evidence/b407dbdb/patch-20261111-4-b/`（本机忽略目录）。

| 验证（产品命令 cwd 为 web/） | 实际结果 |
|---|---|
| 原计划 5 个受影响 Vitest 文件 | 90/90 通过，无 skip；9.02s，`affected-unit.log` |
| `npm run typecheck`、`npm run lint`、`npm run format:check` | 均通过，各自同名日志 |
| `npm run build` | 通过，`build.log`；保留 chunk >500 kB 构建提示 |
| `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts` | 40/40 通过，26.1s，`browser.log` |
| 既有原生元数据入口编辑／筛选 | 失败：标题从上述文字变为空串；`native-draft-filter.log` 及前后截图 |
| 根目录治理检查、完整 Base..Head `git diff --check` | PASS／无输出 |

B 已检查本轮桌面与窄屏截图；1536×600 截图也保存在同一稳定目录。
原生失败的账号、任务／文件、操作前后值及准确 URL 保存在日志中，数据仅来自临时
测试 runtime。本轮测试及静态检查执行时间低于总复核时间的 50%；单元和浏览器套件
合计 35.12s，原生复现约 1s。确认阻塞后依流程提前 FIX REQUIRED，未运行原计划
`task-flow.python.spec.ts`；该项保留给修正候选的 B 验收，未标记通过。
本轮仅维护 TASK.md 审查结果，未改产品代码；预存脏文件保持，未推送／部署。

### Developer Fix Report — B-PATCH4-01

**候选检查点：** 本提交（`READY FOR B REVIEW`），任务 Base `42e666ca..` 之上的修正提交；
分支 `main`。前次候选 `b407dbdb` 的完整实现、既有行内位置与页外卡保持不变。

**根因与修正：** `b407dbdb` 把证据及其恢复表单从列表兄弟位置移入由
`runId + itemStatus + itemCursor + token` 键控的 `RunItemsSection`；筛选变化重挂载整个
列表，`TaskItemRecoveryPanel` 的本地 `internalDecisionDraft` 随之回到初始输入。
本次将未提交决定草稿的所有权上移到列表 key 之外的 `RunDetailTabs`，按文件条目保存，
并通过组件既有的 `decisionDraft` / `onDecisionDraftChange` 契约经 `RunItemsSection`、
`RunEvidenceSection` 传入恢复面板；没有新增存储协议、恢复命令或第二套表单状态。
同一文件在“页外卡 → 行内展开”及筛选切换中继续使用同一草稿；草稿仍由既有
`decisionKey`（检查点版本 + 决定类型）约束，过时检查点按原逻辑清除，不同条目按
`itemId` 隔离。选择另一运行会重挂载 `RunDetailPanel`，认证切换会重挂载 landing 的
恢复会话提供者，均不会继承前一运行／账号的草稿。关闭、保存、分析、确认、未知核对
及零写命令语义未改。

**新增回归：** `RunDetailTabs.test.tsx` 使用真实“状态筛选”控件，对当前页的
`metadata_correction` 文件在“搜索标题”输入 `Operator edited metadata title`，切换到
`waiting` 筛选；等待筛选请求、列表重挂载及证据迁回该文件行内后，断言同一输入仍在、
证据仅一份且紧邻该文件。该用例在 `b407dbdb` 源码上失败（元素值为空串），在本次候选
通过，证明覆盖 B 指出的实际路径而非仅调用组件。

**受影响检查（cwd `web/`，未新增依赖）：**

| 命令 | 实际结果 |
|---|---|
| 新回归单测（`-t "keeps the same file's unsaved title"`） | 修正前源码失败：期望 `Operator edited metadata title`，实际为空串；修正后 1/1 通过 |
| `npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/run-detail-state.test.ts src/features/operations/run-detail-query.test.ts src/features/operations/OperationsInventory.test.tsx` | 5 文件通过，91/91 测试通过（无 skip），9.47s |
| `npm run typecheck` | 通过 |
| `npx eslint src/features/operations/RunDetailTabs.tsx src/features/operations/RunDetailTabs.test.tsx` | 通过，无输出 |
| `npx prettier --check src/features/operations/RunDetailTabs.tsx src/features/operations/RunDetailTabs.test.tsx` | 通过 |
| `npm run build` | Vite 构建成功；仅保留既有 chunk >500 kB 提示 |
| `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts` | 40/40 通过，23.2s |
| 仓库根 `python3 scripts/check_governance.py` | PASS |
| 仓库根 `git diff --check` | 无输出 |

本轮未改 `styles.css`、后端、权限、schema、Storage、URL 契约或恢复协议；当前代码
差异仅 `RunDetailTabs.tsx`、其单元测试与本报告。既有浏览器位置／可读性断言在本次
复跑中保持通过，未以删除断言换取通过。

**剩余风险：**

- 草稿在 `RunDetailTabs` 存活期间按文件保留，包括关闭证据后再次打开、切换条目或
  切换操作记录再返回；这与 B 要求的位置迁移保留一致，但比修正前“关闭即丢弃”保留
  更久。过时检查点仍由既有 `decisionKey` 清除，运行关闭或账号变化会重挂载清理。
- 初始列表尚未返回时证据仍先在表格前显示、随后迁入行内；两次挂载现在共享同一
  草稿，B 指出的筛选清空路径已消除，但该迁移仍会重置仅存在于面板实例的展开状态。
- 本 Task 未运行 B 负责的真实 Python／临时 SQLite `task-flow.python.spec.ts`、全量
  Web／Python／E2E、wheel 或 Docker 门禁；真实原生元数据入口的编辑→筛选旅程由 B
  在本次候选上复核。浏览器假服务套件不包含该原生 fixture，不能替代该验收。

**工作区：** 预存 `mediaflow/.DS_Store` 修改及未跟踪的 `.DS_Store`、
`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、`output/` 调查材料保持原样，
未进入本检查点；未推送、未发布。

### B Final Review — PATCH-20261111-4 PASS

```text
Reviewer: B
Date: 2026-11-11
Reviewed Base: 42e666ca6c600cbaf93625dd5b389763c28ddade
Reviewed Head: ff8f3a699d2d6a1a27a2a221299cec9c616207ed
Decision: PASS
Task blockers: NONE
B-PATCH4-01: RESOLVED
Authorized bug acceptance complete: YES
Next: NO ACTIVE IMPLEMENTATION TASK
```

**完整交付复核：** B 独立审查原始 Base..修正候选的全部 6 文件差异，包含原实现、
修正及测试；没有仅看最后一次补丁。任务中心 → 打开任务详情 → 点击文件“查看证据”，
唯一证据紧跟对应文件，切换文件后内容与位置一致，关闭后回到触发按钮。页外／筛选隐藏／
列表尚未返回或失败时保留精确文件独立卡，回到当前页后仅有行内一份；计数与分页保持。
原有结果、附件、日志／审计和恢复链路继续使用既有组件与服务，未改后端执行语义。
桌面、390px 和 1536×600 实际截图中正文及关闭动作可读，键盘开关与焦点检查通过。

**原阻塞的真实旅程：** 任务中心 → 元数据恢复 → 查看问题文件 → 查看该文件证据与
恢复记录 → “搜索标题”输入 `Operator edited metadata title` → 状态筛选改为等待处理，
同一文件的标题保持。再筛选到不包含该文件的成功列表、返回全部，独立卡与行内迁移后
标题仍保持且证据始终只有一份，全程未发送产品写请求。使用既有
`operations_inventory_harness.py` 的 `metadata_correction` fixture、真实 Python API／
临时 SQLite、新构建和 Chromium；没有新增产品入口。草稿复用已有传参及检查点归属，
稳定 owner 在列表 key 之外，任务／账号的挂载边界继续隔离草稿。B-PATCH4-01 已解决。

**B 实际验收（产品命令 cwd 为 `web/`）：**

| 命令／检查 | 实际结果及本地证据 |
|---|---|
| Required tests 中的 5 文件受影响 Vitest 命令 | 91/91，5 文件通过，无 skip；9.32s；`affected-unit.log` |
| `npm run typecheck`、`npm run lint`、`npm run format:check` | 全部退出 0；`typecheck.log`、`lint.log`、`format.log` |
| `npm run build` | 成功；`build.log`；保留既有 chunk >500 kB 提示 |
| `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts` | 40/40，无 skip；22.8s；`browser.log` |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts --output=../.git/validation-evidence/ff8f3a69/patch-20261111-4-b/python-results` | 3/3，无 skip；7.4s；`task-flow-python.log`；真实混合文件结果、流程失败与文件成功并存、精确恢复确认及协作取消通过 |
| 既有原生元数据入口编辑→筛选→独立卡→行内 | PASS，零产品写请求；`native-draft-filter.log` 与两张原生截图 |
| 根目录 `python3 scripts/check_governance.py`、完整 Base..Head `git diff --check` | PASS／无输出 |

稳定本地证据：`.git/validation-evidence/ff8f3a69/patch-20261111-4-b/`（忽略目录，
不声明远程可访问）。已实际查看 `inline-evidence-1536.png`、
`inline-evidence-1536x600.png`、`patch-file-evidence-390.png` 和
`native-draft-restored-inline.png`；前轮失败证据原样保留。本轮测试及静态检查执行时间
低于总复核时间的 50%，上述三个测试套件运行合计 39.52s。

**范围与限制：** 本次是 T3 前端呈现／恢复消费者集成修复，全部计划门禁已完成。
浏览器实测为 Chromium；未运行全 Python／全 Web／全 E2E、wheel 或 Docker 矩阵，
本次无后端、权限、schema、Storage 或执行引擎变更需要扩大门禁。原生流程失败用例中
预期的 OperationalError 状态保留提示与该用例断言一致，不构成额外阻塞。
草稿在当前任务详情存活期间保留；任务关闭／账号切换按现有挂载边界清理。

复核分支 `main`，候选未移动。B 本轮仅维护 TASK.md；预存脏文件全部保留且不纳入提交。
Slice54 及其全部接受结果／关闭事实、SLICE／Roadmap／Progress 均保持。
本独立修复授权结果已全部满足，停止规划；未推送或部署。
