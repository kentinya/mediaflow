# NO ACTIVE IMPLEMENTATION TASK

独立小修 `PATCH-20261113-2` 已由 B 独立验收 **PASS — 2026-11-13**，三项授权修复完成，
无活动实施 Task。下方 `PATCH-20261113-3` 仅为用户请求的独立修复规划草案，尚未授权实施。
生命周期依据 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。
Slice54 保持原 **PASS / CLOSED**；下一大 Slice 由 A 另选。

## PATCH-20261113-2 — B PASS

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Difficulty / Test Level: Medium / T3
Reviewer: B
Decision: PASS — 2026-11-13
Reviewed Base: 9811df4559d94db5b648f6152476f39035a12ae5
Reviewed Head: 14da49b8489e511a8ea588a40f7a10a869522c05
Product Checkpoint: a2effc4b0ed4503d230ff9b684d3d1e869793e95
Next: NONE
```

[固定 B 验收](https://github.com/kentinya/mediaflow/blob/53bcc0a3d6e6506bec23dfa92aa35e27cc1864f5/TASK.md#patch-20261113-2--b-pass)
保留八项结果重评、两项原始返工与修正、实际命令／计数、首轮产物目录冲突及隔离重跑、
截图和证据限制；[原计划、开发指导与两轮交付](https://github.com/kentinya/mediaflow/blob/14da49b8489e511a8ea588a40f7a10a869522c05/TASK.md)
保留完整范围。

文件页指定蓝色说明已移除；两页列表／网格可感知悬停、按下、焦点和选择，切视图保留
准确条目。名称／大小仅当前页排序，列宽可拖动／键盘调节；打开目录、翻页和读取重试保留
会话设置，整页重载恢复默认。B 验收 106 项受影响单元、71 项 Node 浏览器及 10 项真实
Python 浏览器用例通过，静态／构建／治理与三视口检查通过。原始证据保留本机。

现行浏览旅程见 [Product Experience](docs/product-experience.md#browse-feedback-selection-and-table-controls)，
页面约定见 [Files](docs/file-page-visual-spec.md)／[MediaLibrary](docs/media-library-page-visual-spec.md)；
[文档导航](docs/README.md) 索引此前独立修正，
[Release](docs/release.md#current-v2-validation-boundary) 统一记录验证范围。
文档治理只协调现行说明、固定验收和导航；SLICE／Roadmap／Progress、产品与测试均未改。

## PATCH-20261113-3 — 继续整理保持任务中心背景并删除独立接收页（规划草案）

**PLANNING ONLY：用户本轮只授权规划；本草案不激活实施、不授权其他角色或代理开展工作。**
范围来自用户对现有行为的纠正：“在任务中心的任务详情页点击继续整理后背景改变了，
不应该改变背景同时改变后的这个背景页应该删除的。” 不重开已接受 Slice。

```text
Task ID: PATCH-20261113-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 1c625220b9552bd1e75bfd351a54ddb524ff3e65
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: NOT AUTHORIZED — PLANNING DRAFT ONLY
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
   SLICE／Roadmap／Progress 不改。本轮规划只写 TASK，不提前改这些产品文档。

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
Slice、推送、发布、部署；本轮不实施、不委派、不自验收。

### Developer Completion Report

待明确授权实施后填写：固定检查点 SHA／READY FOR B REVIEW、变更与关键决定、实际
受影响测试结果／失败／风险。完整验收由 B 执行。

### B Review Result

待实施候选；无 PASS／FIX REQUIRED 决定。完成后由 B 独立审查整个 Task Base..Head；
PASS 后恢复紧凑 NO ACTIVE IMPLEMENTATION TASK 通知，不关闭或重开任何 Slice。
