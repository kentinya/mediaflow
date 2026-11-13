# PATCH-20261113-3 — 继续整理保持任务中心背景并删除独立接收页

用户于 2026-11-13 明确“激活Task”，正式授权本 Task 实施；原 Task ID／Base／Goal／Scope
保持。Developer 已在实施检查点 `fb8c35a7` 交付实现、受影响测试与文档同步。
B 独立审查 `1c625220..68e6c347` 后于 2026-11-13 返回 FIX REQUIRED：任务详情后台
轮询失败会卸载正在编辑的整理卡，重新读取后未保存的选择丢失。Developer 已在修正
检查点 `ee0b41e4` 完成 B-01 修复、受影响测试与真实 Python 浏览器复验；当前状态为
READY FOR B REVIEW，B 对完整 Base..Head 的独立再审与 T4 验收仍未执行。
范围来自用户对现有行为的纠正：“在任务中心的任务详情页点击继续整理后背景改变了，
不应该改变背景同时改变后的这个背景页应该删除的。” 不重开已接受 Slice。

```text
Task ID: PATCH-20261113-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 1c625220b9552bd1e75bfd351a54ddb524ff3e65
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: USER AUTHORIZED ON 2026-11-13
```

### Goal

用户在任务中心打开准确任务详情，点击合法的“继续整理”，直接在原任务中心背景上
复用逐文件整理弹窗。关闭后回到原任务详情；确认受理后在任务中心显示响应证明的准确
Task 及真实进度。全程不出现“整理所选文件／逐文件整理准备”的独立背景页面。

现有缺口：`OperationsLanding.tsx` 的按钮链接到 `/operations/organize/new`；该路径是
根级独立路由，卸载任务中心，`OrganizeCreationPage.tsx` 再渲染页头、提示背景和
`ManualOrganizeDialog`。2026-11-09 `31211d9a` 把原准备工作区改为共享弹窗时保留了这层
接收页。当前单元及真实 Python E2E 明确断言该跳转，没有验收背景连续性。

依据 `V2-UX-005/006/012`、`V2-OPS-015/018/019`、完整 Manual organize 与 Tasks/recovery
旅程、任务中心规范及 Architecture 的 Files-admitted Task／Manual organize 契约。
本修正替换其中独立 `/operations/organize/new` 接收页及其旧深链保留约定；保留准确
准备关联、历史事实可读和原执行安全。新 canonical 继续地址属于 `/operations`，旧地址
删除后走普通未找到／认证边界，不保留别名、重定向或另一张迁移说明背景页。

### Implementation Scope

1. **任务中心内承载。** 在 `OperationsLanding` 的稳定任务／账号边界内承载共享
   `ManualOrganizeDialog`。继续意图使用 `/operations` 的有界 URL 状态，包含准确 `run`
   及一个闭合集合的弹窗标记；准备 ID／资源库从该 Task 的后端持久关联读取，不能凭
   浏览器任意来源参数、最新任务或当前 Active 猜测。仅后端允许继续时提供入口。
   打开时任务列表保持挂载、宽度、位置及合法上下文；详情可在整理卡后保留或暂时
   停用，原详情状态不丢失。只允许最上层弹窗交互，避免双焦点陷阱与双重滚动锁。
2. **完整导航与状态。** 更新 `/operations` 查询校验、认证续转白名单和必要返回上下文。
   关闭、Escape、浏览器 Back／Forward、刷新及重认证均恢复同一合法任务／准备；
   普通关闭回到原详情与继续入口焦点，保留视图、日期、游标页、详情页签／条目筛选和
   背景滚动，不重播主页面动画。读取失败／401／403／关联缺失分别解释并提供适用重读／
   认证动作；失去继续资格后不得继续编辑、分析或确认，不新加已结束任务的准备入口。
   已结束状态及原计划／失败历史仍按既有只读边界展示。
3. **保护原命令与准确交接。** 复用原逐文件决定、分析、精确子集确认、显式危险效果授权
   及未知提交核对，不重做业务引擎。未保存离开必须明确继续编辑／放弃；在途或未知
   提交禁止关闭／后退绕过保护。Task 切换、权限变化、晚到响应不能把 A 的准备／输入／
   未决命令交给 B。正常或核对证明受理后，清除整理弹窗状态，按响应准确 taskId 选择
   Task 并重读必要详情／条目／记录；保留合法列表条件。不能假定导航到同一路径就会
   卸载弹窗，也不能依赖旧页卸载来清理或触发刷新。未知 Execute 始终核对首次提交的
   previewId／itemIds／intentVersion／危险效果，不随兄弟重分析改变，不自动重发。
4. **删除独立页面及专属引用。** 删除 `OrganizeCreationPage` 产品实现、路由注册／导入、
   destination 元数据及专属认证参数分支；原测试中有用的准备／历史／关闭／核对场景
   迁到任务中心宿主测试。清理实际消费者，包括 `service_api.py` readiness 的旧 Web
   recovery destination（新建整理指向正常 Files 入口），及 Node／Python 浏览器用例。
   删除接收页的通用 Files 引导壳，旧路径普通未找到。保留共享 organizer、API、执行／
   admission 查询、数据库和历史；不扩大删除到独立 intent／discovery 页或无关孤立模块。
5. **协调现行说明。** 实施交付时仅同步 Requirements／V2 Requirements、Product
   Experience、Architecture、任务中心规范及实际受影响的导航说明；写清原地弹窗、
   新 canonical 继续地址、旧接收页退出。原 Slice／B 接受身份与限制保留在 Git，
   SLICE／Roadmap／Progress 不改。本次激活只写 TASK，不提前改这些产品文档。

### Developer Guidance — B 本轮修正

本轮只修复 B-01，不另建 Task，不扩大到任务详情或查询框架重构。

1. 从资源库 Files 选中一个文件并整理，等待摘要，关闭整理卡；进入任务中心，打开该
   Task 详情并点击“继续整理”。展开“修正识别或作品”，把识别类型从已有 A 改为下拉
   提供的 B（原生 fixture 为 Normal Movie → TV），先不保存。让现有五秒任务详情轮询
   的下一次 GET 返回 503，再恢复该读取。当前实现会改显示“无法继续这次整理”；点击
   “重新读取任务”后类型回到 A。此旅程不构造新产品入口，不提交 Save／分析／Execute。
2. 修改 `OperationsLanding.tsx` 的继续会话承载与 `OrganizeContinuationCard.tsx` 的
   组件切换：已经从准确 Task 关联打开的整理会话，不随同任务后台概览的一次读取失败
   被卸载／重建。读取问题在原会话内说明并允许读取恢复；原逐文件输入、选择及现有
   命令核对状态保留。首次进入尚未取得关联时仍使用原读取失败入口；真正结束或权限
   拒绝仍遵守现有资格与认证行为。不要通过吞掉读取错误、关闭轮询或重放命令修复。
3. 在现有宿主单元用例和 `operations-inventory.python.spec.ts` 正常继续旅程中加入上述
   场景：选 B → 轮询失败 → 恢复读取 → 仍为 B，整理卡和原任务中心背景连续保留，
   不弹放弃提示、不发送写请求。沿同一入口验证已有在途／未知提交核对不会被这次
   背景读取失败清除；继续核对首次提交的方案，不重发 Execute。复用现有测试与假服务。
4. 运行新增／直接受影响测试及静态检查，提交同 Task 的修正检查点并交 B；不承担 B 的
   全仓门禁。按用户本轮要求，各轮测试用时小于该轮总用时的 50%，实际结果与未运行
   项如实记录。B 对修正后的完整 Base..Head 再审并执行剩余 T4 验收，不降低原验收范围。

### Acceptance Criteria

- [ ] 从有日期／游标页且已滚动的任务列表打开详情并继续整理，主路径始终为
  `/ui-v2/operations`，原任务中心背景全程可见、稳定且不重挂载；无独立接收页内容／闪帧。
- [ ] 正常关闭返回原详情，详情页签／筛选／证据、列表视图／日期／页／滚动保留，焦点回到
  原继续入口或准确且可用的任务详情控件；Back／Forward 不跳到 Files 或其他任务。
- [ ] 新 canonical 地址直达、刷新、重认证恢复准确 Task 的原准备；标记非法、缺失 run、
  无关联、读取失败、403 及已失去资格均不猜工作、不创建工作、不提供失效确认。
  原计划读取失败与从未生成计划可辨，允许的历史重读保持零变更。
- [ ] 未保存决定、在途 Save／分析／Execute、未知 Execute 下的关闭／Escape／Back 保护
  正确；晚响应、任务 A→B、认证主体切换不串草稿、请求、结果或执行资格。
- [ ] 原准备可逐文件修正／重新分析并确认精确子集；正常受理及丢响应核对证明受理均只
  提交一次 Execute，关闭整理卡并显示准确 Task。不能仅显示列表或卡片仍停在提交成功态。
  原提交后修改兄弟方案再核对仍使用原请求；成功／不确定项及已受理项不被重放。
- [ ] 删除旧接收页及其专属路由、导航／认证声明和生产链接；带／不带 discoveryId 的
  `/ui-v2/operations/organize/new` 均普通未找到，无旧页、自动跳转或准备／执行请求。
  SPA 返回 index.html 不作为页面仍存在的依据；正常鉴权／Shell 读取可保留。
- [ ] Files 单项／批量／文件夹整理及原任务四类恢复不回归；不出现已结束 Task 的重复准备
  按钮。当前任务结果／文件证据、只读历史与普通 Files 新整理入口仍可达。
- [ ] 桌面 1440×900、390×844 及矮窗口 1280×600 核对打开中间帧、关闭／重开、慢读取／
  错误和长路径；无背景替换、滚动跳动、横向溢出或双弹窗交互；Tab／Escape／回焦和
  reduced-motion 可用。用同视口截图／过程证据证明，不能只断言路径或最终标题。

### Required Tests

依照 [测试归属](docs/development-workflow.md#6-test-levels)。T4 因本修正移动实际执行
确认宿主、改变刷新／认证／卸载和未知结果核对生命周期；业务引擎不变不代表无重放风险。
以下为**待实施／待验收**命令，不宣称本轮已执行产品验收。

#### Developer — affected tests

根目录：`python3 scripts/check_governance.py`、`git diff --check`。

`web/`：

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/RunDetailTabs.test.tsx src/routes/router.test.tsx src/shared/navigation/destination-model.test.ts src/shared/navigation/operations-return.test.ts src/shared/ui/modal-card.test.tsx
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/manual-organize.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable|PATCH-20261113-3'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
```

新增宿主测试归入上述 Inventory／Router 文件；新真实浏览器用例用 Task ID 标记纳入 grep。
准备页原场景迁移后删除该页专属测试，不能靠删断言获得通过。新用例覆盖背景与列表
连续性、认证／历史导航、失效／串任务、未保存／在途保护和精确请求核对／交接。
如最小改动涉及 readiness 地址，补充相应 Python 单元用例并运行实际所属模块，报告确切
命令及结果；修改测试 harness 时包含其直接受影响验证。Developer 不承担全仓全量门禁。

#### B — acceptance and full regression

独立审查固定 Task Base..候选完整范围，重现原任务详情继续入口，检查中间帧与列表节点
连续性、三视口／键盘、直达／刷新／重认证／后退，以及原请求已受理后兄弟重分析再核对。
在新生产资产＋真实 Python API／临时 SQLite／本地 Provider 假服务／临时 Storage 根运行：

```sh
# cwd: web/
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts tests/e2e/organize-source-history.python.spec.ts
```

并负责适用 [T4 共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)：
Python、Web 单元／Node E2E、静态／生产构建、新 wheel 与源码外安装 smoke，以及 pins／
权限／零变更读取／C→A 身份及已完成／不确定效果非重放。无容器执行路径变更时广域
Docker 矩阵不适用，说明依据；不使用生产媒体或外部生产服务。保存精确候选、实际
命令／结果／失败／跳过与视觉证据，不把只通过旧路径测试或文档标签当作验收。

### Non-goals

不重做任务详情、列表八视图、Files 整理表单或四类恢复；不新增历史准备入口、自动重试、
跨 Task 恢复或通用失败恢复；不新增后端状态／schema／队列／权限／Provider／Storage
操作，不重写历史 pins／结果，不改业务确认或危险授权协议。无无关模块清理、下一 Task／
Slice、推送、发布、部署；本次激活不代行实施、不委派、不自验收。

### Developer Completion Report

READY FOR B REVIEW

- 原实施检查点：`fb8c35a7`（Task Base `1c625220`）。B 在 `68e6c347` 审查后返回
  FIX REQUIRED / B-01；原实现、受影响测试与文档同步的完整证据保留在该检查点及 Git
  历史中，本次不重写。
- 修正检查点：`ee0b41e4`（产品与测试；本报告的 docs(task) 提交只更新本 Task 状态／
  结果，不含产品改动）。分支 `main`；修正前工作区干净，治理检查 PASS。
- B-01 根因：后台任务详情轮询把 `filesPreparation` 投影读成 `{ok:false}` 后，
  `resolveOrganizeContinuation` 将已打开的准确关联降级为 `unavailable`；宿主随即用
  提示卡替换 `ManualOrganizeDialog`，其本地草稿、选择和未知命令核对状态随卸载丢失。
- 修复：`OperationsLanding` 以准确 Task + discovery 关联作为已打开会话的保留锁存，
  只在同一选中 Task 的非认证读取失败时继续挂载原卡；`OrganizeContinuationCard` 在该
  卡内说明读取问题并提供同一任务的重新读取。成功读取始终覆盖锁存；关闭、切换 Task、
  `no-association`、`not_found`、401/403 或真实结束仍按既有资格／认证边界处理。
  共享 `ManualOrganizeDialog` 新增可选的内嵌读取提示，不改变 Files 宿主调用；没有
  吞掉读取错误、关闭轮询、自动重试或重放任何保存／分析／Execute。
- 新增测试：首次进入读取失败仍显示原不可用卡；已打开会话在五秒轮询 503 后保留 B
  选择、背景与单卡，恢复读取后仍为 B 且无写请求；未知 Execute 核对跨同一次读取失败
  保持，恢复后只按首次提交的 preview 核对一次，Execute 仍为一次。真实 Python
  正常继续旅程加入同一 503／恢复／选择保留、列表列宽连续与显式放弃后重开断言。

**本轮实际测试结果（均在 `ee0b41e4` 源码与同一生产构建上）**

```text
python3 scripts/check_governance.py — PASS
git diff --check — PASS
web: npm run test -- run src/features/operations/OperationsInventory.test.tsx
  src/features/operations/OperationsRouter.test.tsx
  src/features/operations/ManualOrganizeDialog.test.tsx
  src/features/operations/RunDetailTabs.test.tsx src/routes/router.test.tsx
  src/shared/navigation/destination-model.test.ts
  src/shared/navigation/operations-return.test.ts
  src/shared/ui/modal-card.test.tsx — 8 files / 171 tests PASS
web: npm run typecheck — PASS
web: npm run lint — PASS
web: npm run format:check — PASS
web: npm run build — PASS
web: npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
  tests/e2e/deep-link.spec.ts tests/e2e/manual-organize.spec.ts — 42 passed
web: npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts --grep 'PATCH-20261113-3'
  — 1 passed（15.3s，真实 Python API／SQLite／Worker；新增 503 轮询、恢复读取、
  B 选择保留、背景列宽连续与显式放弃后重开；截图见
  web/test-results/PATCH-20261113-3/）
web: npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/manual-organize-dialog.python.spec.ts — 8 passed（49.6s）
```

- 未运行项／剩余风险（交 B）：按 Developer 分工未执行全仓 Python、Web 全量单测、
  T4 共享全量门禁、wheel／源码外安装 smoke、Docker，以及 B 指定的完整
  `operations-inventory.python.spec.ts`、`operations-task-center-visual`、
  `organize-source-history` 与三视口视觉验收。真实浏览器 503 由 Playwright 路由
  注入到同一真实 API 读取路径，不是后端主动故障；未在真实浏览器单独复验未知
  Execute 跨读取失败（宿主单元用例覆盖），也未在失败窗口内提交 Save／分析／Execute。
  B 应在完整 Base..Head 上复核中间帧、三视口、键盘与首次提交核对证据。

### B Review Result

```text
Reviewed Base: 1c625220b9552bd1e75bfd351a54ddb524ff3e65
Reviewed Head: 68e6c3478bf1935ab9879dd68a1f9dd8822497c5
Product Checkpoint: fb8c35a7f639fd88bb10bc806e370509e0cfd7c2
Reviewer: B
Decision: FIX REQUIRED — 2026-11-13
Task blockers: B-01 / P1 — 后台任务详情轮询失败丢失整理卡未保存选择
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

**交付结果重评。** 本 Task 是独立 bug，Parent Slice 为 NONE；Slice54 仍为原 PASS / CLOSED，
其合同／Roadmap／Progress 无变更。审查覆盖完整 Base..Head 的 22 个变更文件，包括
旧页删除、路由／认证／导航、继续宿主、公共弹窗、readiness 地址、测试和旅程文档。
原“继续整理不换背景、删除独立接收页”主行为已实现；B 从已有 Files → Task 详情 →
继续整理入口运行原生 Python 浏览器用例，原地打开／关闭回焦、Back／Forward、刷新／
重认证、准确受理交接及结束历史只读路径通过。旧接收页文件／注册／专属导航已删除。
尚未完成全部 T4／三视口过程验收，不将 Developer 报告或已有截图当作 B 全部验收。

**B-01。** 用户在整理卡内改选类型 B，未保存；五秒后台概览 GET 503 后原整理组件消失，
点击“重新读取任务”重开时选择恢复成持久值 A，没有经过明确放弃。原因是
`resolveOrganizeContinuation` 将后台概览读取失败变为 unavailable，Host 随即用提示
组件替换 `ManualOrganizeDialog`，其本地草稿随卸载丢失。这是本次 `fb8c35a7` 引入的
宿主生命周期问题，命中原 Task 的输入／失败恢复要求；无需扩展任务范围。

**B 实际验证。** `web/`，使用工作区现有生产构建及隔离 Python／SQLite／临时媒体根：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'PATCH-20261113-3'
```

原候选用例 1 passed（11.8s）。在同一用例实际点击继续入口后追加后台读取 503／恢复
与输入保留断言：初次清空下拉选择的重现失败；再以页面实际提供的合法 TV（B）选择
复核亦失败（两次各 18.9s）：期望 B，实得 A，错误期间整理卡数量为 0。截图人工查看
确认卡片被替换、恢复后原选择丢失。临时复现插入已恢复为候选原文，未提交产品或测试
改动；日志、复现片段、截图与 trace 保存在本机
`.git/validation-evidence/68e6c347/patch-20261113-3-b/`。三次产品浏览器测试报告用时合计约 50s，
少于本轮总用时的 50%。治理与差异检查 PASS。

已证实 P1 后按流程先返修，未继续全仓 Python／Web／Node E2E、完整原生矩阵及 wheel／
安装门禁，本轮未重新构建。这些仍由 B 在修正候选上负责，不交回 Developer，也不记为
已通过。无新增引擎／schema／权限变更，无广域 Docker 执行路径变更；无推送／部署。

## Prior accepted Task

独立小修 `PATCH-20261113-2` 的 B PASS、精确范围与验证限制保留于
[固定记录](https://github.com/kentinya/mediaflow/blob/24cc107a8b0c83d43e5b29673221247f8e370ce1/TASK.md#patch-20261113-2--b-pass)。
Slice54 保持原 PASS / CLOSED，SLICE／Roadmap／Progress 不变。
