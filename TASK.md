# PATCH-20261113-3 — 继续整理保持任务中心背景并删除独立接收页

用户于 2026-11-13 明确“激活Task”，正式授权本 Task 实施；原 Task ID／Base／Goal／Scope
保持。Developer 已在实施检查点 `fb8c35a7` 完成实现、受影响测试与文档同步，
当前状态为 READY FOR B REVIEW；B 的独立验收仍未执行。
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

- 实施检查点：`fb8c35a7`（Task Base `1c625220` → HEAD；本报告的 docs(task) 提交仅更新
  本 Task 状态／结果，不含产品改动）。分支 `main`；实施前治理检查 PASS 且工作区干净。
- 关键决定：继续意图使用 `/operations` 的准确 `run` + 闭合 `dialog=organize` 标记；
  准备身份只从该 Task 的 `filesPreparation` 后端关联读取，URL 不携带 discovery／资源库。
  共享 `ManualOrganizeDialog` 通过 portal 挂在任务中心最上层；运行详情保持挂载但暂停
  自身键盘陷阱／inert，关闭只移除标记并回焦原继续入口。拒绝卡片与无关联/读取失败使用
  同一最上层说明，不猜准备、不创建工作。正常或核对证明受理后显式清除标记、按响应
  taskId 选择并 invalidate 概览/条目/记录，不依赖同路径导航卸载或旧页刷新。
- 删除：`OrganizeCreationPage` 产品文件与专属测试、路由注册/import、destination 元数据、
  `/operations/organize/new` 认证续转分支，以及 readiness 旧 recovery destination；
  其余共享 organizer、API、查询、数据库与历史保留。原接收页场景迁入
  `OperationsInventory.test.tsx` 宿主测试（历史只读、原计划读取失败重读、从未生成、
  未保存离开、缺失/无关联/非法标记、A→B 不串准备、受理交接）。

**实际测试结果（均在本检查点源码/构建上）**

```text
python3 scripts/check_governance.py — PASS
git diff --check — PASS
web: npm run test -- run src/features/operations/OperationsInventory.test.tsx
  src/features/operations/OperationsRouter.test.tsx
  src/features/operations/ManualOrganizeDialog.test.tsx
  src/features/operations/RunDetailTabs.test.tsx src/routes/router.test.tsx
  src/shared/navigation/destination-model.test.ts
  src/shared/navigation/operations-return.test.ts
  src/shared/ui/modal-card.test.tsx — 8 files / 168 tests PASS
web: npm run typecheck / lint / format:check / build — PASS
web: npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
  tests/e2e/deep-link.spec.ts tests/e2e/manual-organize.spec.ts — 42 passed
web: npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts
  --grep 'PATCH-20261113-3|ordinary Files navigation opens the exact linked run'
  — 2 passed（含真实 Python API／SQLite／Worker：原位打开、列表位置、Escape 关闭回焦、
  Back/Forward、刷新/重认证、正常受理交接、结束任务只读历史；关闭按钮回焦由宿主
  单元用例覆盖；截图见
  web/test-results/PATCH-20261113-3/）
web: npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/manual-organize-dialog.python.spec.ts — 8 passed
python: .venv/bin/python -m unittest tests.test_management_setup — 18 passed
```

- 未运行项／剩余风险（交 B）：按 Developer 分工未执行全仓 Python、Web 全量单测、
  T4 共享全量门禁、wheel／源码外安装 smoke、Docker 与 B 指定的完整
  `operations-inventory.python.spec.ts`／`operations-task-center-visual`／
  `organize-source-history` 视觉验收。真实浏览器未单独以未保存草稿触发 popstate Back
  （单元已覆盖 route blocker；`manual-organize-dialog` 的真实 Back 用例覆盖共享弹窗）。
  `dialog=organize` 与旧隐藏列表条件同时存在的直达 URL 仅在单元层覆盖；B 应在完整
  Python 旅程中复核最终候选的中间帧、三视口与键盘证据。

### B Review Result

待实施候选；无 PASS／FIX REQUIRED 决定。完成后由 B 独立审查整个 Task Base..Head；
PASS 后恢复紧凑 NO ACTIVE IMPLEMENTATION TASK 通知，不关闭或重开任何 Slice。

## Prior accepted Task

独立小修 `PATCH-20261113-2` 的 B PASS、精确范围与验证限制保留于
[固定记录](https://github.com/kentinya/mediaflow/blob/24cc107a8b0c83d43e5b29673221247f8e370ce1/TASK.md#patch-20261113-2--b-pass)。
Slice54 保持原 PASS / CLOSED，SLICE／Roadmap／Progress 不变。
