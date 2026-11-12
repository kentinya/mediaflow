# NO ACTIVE IMPLEMENTATION TASK

Latest independent Task: **PATCH-20261112-1 — B PASS**, 2026-11-12, Medium / T3.

Reviewed range:
`32bb37262777ae945deb8af4a51d9109876ca804..598bd9726adcf1058a9e8736c582b8c62db0d21c`.
The organizer now uses one “保存并重新分析” action, with saved-decision recovery and coordinated
current-state/plan presentation. The independent safe-analysis button and its explanation are removed.

[Fixed B acceptance, actual tests and limits](https://github.com/kentinya/mediaflow/blob/56a84e9e171400e77595678e6b77700bfe3cc9ee/TASK.md#patch-20261112-1--b-pass)
records 88 Web unit tests, 28 Python integration tests, 26 native browser journeys and visual checks.
[Fixed Task plan and implementation handoff](https://github.com/kentinya/mediaflow/blob/c940519b3410373a5a281949d3fc4769606a7d99/TASK.md)
retains scope, acceptance and Developer guidance. Raw evidence remains local at
`.git/validation-evidence/c940519b/patch-20261112-1/`; it is not included in GitHub.

Slice54 retains its original **PASS / CLOSED** acceptance; no Slice boundary, Roadmap or Progress
change accompanies this standalone correction. Current behavior lives in
[V2 Requirements](docs/v2-requirements.md#current--manual-organize-dialog-slice53-pass--closed),
[Product Experience](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)
and [Architecture](docs/architecture.md#current--manual-organize-dialog-slice53-pass--closed).
Next large-Slice selection remains a separate A action.

---

## Planning-only draft — PATCH-20261112-2

用户于 2026-11-12 授权规划一个独立修复 Task，彻底删除“查看关联执行结果”入口与
独立“整理执行情况”页面，明确不是隐藏。本节仅为规划草案，不授权实施、激活、推送
或部署；顶部 `NO ACTIVE IMPLEMENTATION TASK` 保持。后续明确授权实施时再移除该通知，
保留以下 Task ID／Base／Goal／Scope。此前只读调查授权不延伸为产品修改授权。

### Task metadata

```text
Task ID: PATCH-20261112-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: dc2eec67d619bc2e06de5eca0900325a7906fbfd
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: NOT AUTHORIZED — PLANNING ONLY
```

Authority: 用户本轮明确授权的独立界面修复；生命周期与测试分工遵循
[Development Workflow](docs/development-workflow.md)。不重开 Slice47／48／50／53／54，
不修改 `SLICE.md`、Roadmap、Progress 或既有接受身份。需求依据为 `UX-001–003/005/007`、
`V2-OPS-004/005/007/008/010/012/018/019`、`V2-TASK-001–006/012–014`，完整旅程见
[任务与逐项恢复](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[手动整理弹窗](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)、
[任务正文与文件证据](docs/task-center-page-spec.md#current--任务正文与文件证据)；执行归属见
[同一 Task 架构](docs/architecture.md#current--unified-task-scheduling-and-organizing-execution-slice47-pass--closed)。

规划前 `python3 scripts/check_governance.py` PASS。工作区 `/Users/songzhidong/mediaflow`，
分支 `main`，HEAD 为 Task Base，暂存区与受 Git 跟踪的工作区干净；无预存 dirty 文件。
规划只修改本文件；不读取私有配置／运行数据库，不操作用户媒体。

### Goal and observed gap

**现有任务详情／逐文件证据已经能够查看整理结果，本 Task 不新增结果查看功能。**
本次只彻底删除重复的“查看关联执行结果”按钮、独立“整理执行情况”页面及其专属代码，
继续使用现有任务详情看结果。其他流程中仍跳往被删页面的地方，改为打开其实际所属的
现有任务详情；已经正常显示结果或进入任务详情的流程保持原有能力，不另做一套呈现。
正常执行、耐久记录、准确关联和防重放能力保持。

已在现有浏览器只读复现：任务详情 → 查看证据 → “查看关联执行结果”跳至
`/ui-v2/operations/organize/execution/{executionId}`。成功记录的首屏突出 UUID、Worker、
原始 UTC 时间和英文提示，文件／目标埋在操作明细；原详情已有处理结果、来源与目标、
处理经过、附件与未知效果。成功文件下仍突出“本次确认已经受理”的重复跳转提示。
本次调查证明界面重复和表达问题，不认定执行数据或媒体效果错误。

实际依赖不止一个按钮：`OperationsLanding`、`TaskItemRecoveryPanel`、`RunDetailTabs`
传递 `onOpenRecoveryExecution`；`OrganizeIntentPage` 和 `AutomationRunOncePage` 有确认后
回落跳转；`OrganizePlanConfirmation` 的已有执行记录／未知提交核对也链接该页。
`OrganizeExecutionPage`、router 和 destination-model 注册独立路由；
`organizeExecutionQueryOptions` 当前仅供该页读取。执行列表读取还被摘要和
`ManualOrganizeDialog` 用于防重复提交，不能随页面删除。

### Implementation Scope and ordered steps

1. **删除独立 Web 表面及专属代码。** 删除 `OrganizeExecutionPage.tsx`、router 的 import／
   路由定义／注册、destination-model 的目的地／标题／动态匹配／专属认证续转分支。
   删除所有到旧 Web 地址的跳转，以及仅服务该页的 query key／query options；单执行
   API-client 读取包装如无生产消费者也删除。清理专属 props、回调透传、死状态、独占
   样式与专属测试／假服务分支。不得使用 CSS 隐藏、条件常假、feature flag、未注册但
   仍保留组件、改名重建页面／弹窗／抽屉或包装跳转页代替删除。
2. **沿用现有结果查看，只接回原来跳往旧页的地方。** 任务详情本来就能查看结果，
   不需要新增结果区域、查看步骤或另一套数据展示。任务详情内删除“查看关联执行结果”
   （包括重复渲染分支）和仅为该页服务的“本次确认已经受理／请打开关联执行”提示。受理后的真实排队／执行
   状态仍由原任务呈现，不能把受理显示成成功。当前 Task 内单项／批量恢复、剩余范围
   明确确认后留在同一详情，刷新其流程、条目、结果和证据；需要转到另一已证明任务时
   只采用响应或耐久关系提供的准确 taskId。已有计划历史、意图、运行一次的相关分支
   改为进入任务中心并打开准确任务；已有 returnOps 时保留合法视图／日期／分页／
   文件证据上下文，无 returnOps 时使用中心合法默认上下文。Files 已接受的弹窗→
   准确任务交接保持，不引入额外点击或中间页面。
3. **保留未知／失败与导航安全。** 已受理但缺少准确 taskId，或关联读取失败、缺失、
   无权限时，显示已知受理事实和具体读取问题，允许只读重读原关系；不猜最近任务、
   不用 executionId 当 taskId、不重新 Execute。未知提交仍核对首次提交的精确方案／
   子集／版本／危险效果；历史执行列表继续阻止重复确认。任务切换、账号切换、关闭
   详情后迟到响应不能重新打开卡片或覆盖新上下文。刷新、重新认证、浏览器前后退
   进入现有合法任务详情，不准入新工作。
4. **彻底退出旧地址。** 删除旧 Web 路由，不保留重定向、别名、兼容组件、专属退役页
   或执行 ID→Task 的旧地址解析器。旧执行 URL（含刷新／未认证访问）使用系统现有
   普通未找到／认证边界，不展示执行页、不特殊续转到已删除目的地。正常任务深链接
   仍准确可达。此项替代调查阶段提出的旧地址兼容转跳建议，以用户“彻底删除”为准。
5. **协调直接消费者与证据。** 修改原来断言跳入执行页的单元／浏览器／证明脚本，
   改验同一 Task 内的准确结果和实际效果，不能仅删断言或将执行旅程整体跳过。
   在本 Task 范围内更新 Requirements／V2 Requirements／Product Experience／
   task-center-page-spec／Architecture 中确有相关的现行入口／结果位置说明；不把
   规划写成已交付，不改历史接受记录，不扩展成文档整理。

后台执行对象、schema、Task／TaskItem／Result、executionId、操作／附件／审计历史、
API 的 execute／execution 查询／列表／admission 核对及原权限语义保留。共享 normalize
与 action transport 校验仍用于 Execute 响应和历史列表，不能因名称含 execution 删除。
若准确关联确需补充只读投影，只能复用已有耐久关系且明确缺失，不能增加推测关联或
新存储；如需改变写协议、schema、权限、执行引擎或不确定效果语义，停止扩张并交 B
重新评估范围／Test Level，不能用本界面修复授权实施。

### Acceptance Criteria

- [ ] 生产源码没有 `OrganizeExecutionPage`、旧 Web route／destination 注册、
  `onOpenRecoveryExecution` 专属链或同义替代执行结果页；“查看关联执行结果”入口
  与专属提示实际删除。旧地址只到普通未找到，认证续转也不能复活旧页。
- [ ] 继续使用现有任务详情／文件证据查看结果，不新增结果查看功能、结果区域或操作
  步骤；已有正常结果呈现保持。导航修改只用于接回原来依赖被删页面的地方。
- [ ] 从当前任务查看及恢复、单项／批量／剩余范围确认后，在准确 Task 详情看到真实
  排队／执行／结果；成功、部分成功、失败、取消、未知效果、结果尚未记录均可辨。
  原成功兄弟、附件独立结果和历史尝试不丢失，Task completed 不冒充文件成功。
- [ ] 历史计划已有执行、未知提交核对、意图／Run once 的直接进入和有／无 returnOps
  分支均不进入旧页；准确关系不可读时保留已知事实并只读恢复，不误报拒绝或跳错任务。
- [ ] 先确认 A、再修正未选 B、再核对 A 的未知响应，仍打开 A 原提交所属任务及结果；
  Execute 次数不增加，B 不被隐式执行，效果完成后也不重放。
- [ ] 刷新／重新认证／前后退保留合法 Task／视图／筛选／页／文件证据；关闭卡片或
  切任务后迟到响应不劫持界面。读取失败、403、缺失、混合／长内容在桌面与 390px
  可读，键盘／回焦及现有关闭行为保持。
- [ ] 后台执行／核对／历史能力及防重复确认仍工作；浏览、查看、刷新仅有合法读取，
  不新增 Provider 调用、Storage 变更、授权、执行或恢复命令。移除专属测试不降低
  原成功／无效输入／冲突／失败／边界旅程覆盖。
- [ ] 现行文档与最终行为一致；Slice／Roadmap／Progress／历史接受身份保持不变。

### Required Tests

遵循 [测试分工](docs/development-workflow.md#6-test-levels)。以下为实施后的计划，
本次规划没有运行产品测试。所有真实旅程使用临时 SQLite／Storage 和本地假 Provider，
不使用生产服务或用户媒体。

**Developer — affected tests**（Web 命令 cwd `web/`，Python／Git cwd 仓库根）：

```sh
python3 scripts/check_governance.py
npm run test -- run src/routes/router.test.tsx src/shared/navigation/destination-model.test.ts src/shared/navigation/operations-return.test.ts src/features/operations/OrganizeRouter.test.tsx src/features/operations/OrganizePlanConfirmation.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/AutomationRunOncePage.test.tsx
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/manual-organize.spec.ts tests/e2e/operations.spec.ts tests/e2e/automation.spec.ts
git diff --check
```

上述覆盖路由彻底移除、准确 handoff、摘要／历史防重、四类恢复与未知核对。
若修改其他消费者或只读 API 投影，追加其实际直接受影响测试并报告命令，不把完整
Python／Web／E2E 套件交回 Developer。变更的证明脚本保留真实媒体效果断言并至少
执行其直接受影响非容器旅程；容器脚本同步新去向，不因旧 UI 断言直接废弃脚本。

**B — acceptance**：审查固定 Task Base..candidate，核对上述实际结果；运行下列
真实 Python／浏览器集成并补充本 Task 缺失场景。Web cwd `web/`：

```sh
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
```

B 必须实测四类恢复确认、批量／剩余范围、历史执行、首次提交完成后修改兄弟再核对、
无 taskId／关联读取失败、关闭／切任务迟到响应、旧地址与认证续转；现有集成未覆盖的
分支补到同一相关用例／harness，不以 mock 结论替代关键真实旅程。保存桌面／390px
同条件截图及请求记录，验证现有详情可读和确认后无第二次 Execute。根据实际变更
补跑 Node 假服务相关消费者和脚本，不为本次前端删除强制广域 Docker 矩阵。

T3 依据是跨入口导航／认证／未知结果核对的集成风险；本 Task 不更改执行权限或写入
规则。无具体共享影响时不要求全仓库回归、wheel／Docker 发布门禁。若实施发现上述
冻结边界必须改变，由 B 升级风险和测试，T4 才按 workflow 共享全量门禁验收。
所有失败／跳过／未运行如实记录，必要门禁未完成不能 PASS。

### Non-goals

- 不删除后台执行记录／API／耐久身份，不迁移或清理历史／媒体／运行数据库。
- 不新建结果页面、通用恢复入口、重试／回滚能力；不更改四类决定／分析／确认协议，
  不重做任务中心列表／现有文件证据布局或其他页面。
- 不调整业务算法、队列、Worker、权限、Active／pins／fences、Storage／Provider。
- 不激活或实施此草案，不规划下一 Task，不推送／发布／部署。

### Developer Completion Report / B Review Result

尚未实施，无候选检查点、产品测试结果或审查结论。实施授权后 Developer 按 workflow
交准确 checkpoint、受影响测试实际结果与风险，状态 READY FOR B REVIEW；B 独立审查
Task Base..candidate 并运行上述验收，给出 PASS 或同 Task 的 FIX REQUIRED。
PASS 后恢复紧凑 `NO ACTIVE IMPLEMENTATION TASK` 与精确审查指针；不关闭或重开 Slice。
