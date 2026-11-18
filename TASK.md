# Task55.5 — 审核与整理确认只使用当前 Task 旅程

用户于 2026-11-17 明确要求“激活Task”，据此将已提交草案激活为正式实施 Task。
依据已提交 [Slice55](SLICE.md) 的 RO-2、RO-5、RO-6，保留 RO-4 的有效 V2 数据；
生命周期和测试分工遵循 [开发流程](docs/development-workflow.md)。

```text
Task ID: 55.5
Task Type: SLICE
Parent Slice: 55
Status: FIX REQUIRED
Task Base: 8a9d2460d0fb4df1afee0e157af3736f136a64c8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: TASK55.5 IMPLEMENTATION AUTHORIZED
Next Action: DEVELOPER FIXES B55.5-01 AND B55.5-02 IN TASK55.5
```

规划时 main／上述 HEAD，tracked／untracked 干净，工作区和 Git 可写，治理 PASS。
Base 为本单元实施前的真实提交，后续草案／激活提交不重设 Base。
Task55.1–55.4 的已接受结果保持；本单元当前候选及 B 判断见下方独立复核记录。

激活前 main／HEAD `6c1852579b8953bad97c2310adfcc880a21a35cf`，工作区干净、文档与 Git
可写，治理 PASS；Task Base..HEAD 仅 TASK.md 草案变更。原 Base、Goal、Scope、验收及
High／T4 和测试分工保持。上一 Task55.4 的完整 PASS 与证据见
[激活前接受记录](https://github.com/kentinya/mediaflow/blob/6c1852579b8953bad97c2310adfcc880a21a35cf/TASK.md#b-最终验收--2026-11-17)。
本次激活仅修改 TASK.md；激活后的治理检查和 `git diff --check` 通过。

### Goal 与完整操作旅程

用户从资源库 Files 选择文件／有界文件夹整理，或让已保存的自动化定义 due／Run once
受理工作；有业务问题时，在原 Task 的识别／元数据／分类／冲突处理中保存合法决定并
重新分析，查看准确文件／附件／目标和影响，仅确认选中子集，随后在同一任务读取结果。
离开、刷新、重新认证或重启后仍回到该任务和原请求；失败兄弟独立处理，已完成和未知
效果保留。保存失败保留输入；分析已拒绝保留已保存决定并允许原分析动作；确认响应未知
先读取原提交的受理证据，已受理后查看原 Task，未能核对时保留未知状态。

交付结果：这一当前旅程及所需管理 API／CLI 使用共享业务服务；全局审核队列和旧
manual-* 传输不再注册、展示或被当前客户端调用。保留审核、精确摘要、一次性授权、
执行和历史记录的当前职责，退出其旧独立操作表面。

对应 `V2-RETIRE-002/003/008–010`、`V2-OPS-010/012/016–019`、
`V2-TASK-003–006/008–010`、`REQ-REC-004/005`、`REQ-META-008`、
`REQ-CLASS-003–005`、`REQ-ORG-003/004/007/008/012`、`REQ-RECOVERY-004–009`。
阅读 [完整手工旅程](docs/product-experience.md#manual-organize)、
[四类恢复旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[Task Center 说明](docs/task-center-page-spec.md) 和
[当前审核／恢复架构](docs/architecture.md#tasks-results-and-processing-recovery)。

### 已核实的代码与入口

- `mediaflow/interfaces/service_api.py` 的 supported_roots、dispatch、route template 和
  workflow-producing 判断仍包含全局审核与 manual-*。本轮用现有
  `scripts/operations_inventory_harness.py:build_managed_fixture/wsgi_request` 在临时根
  建立正常 managed Active，以该 harness 的管理员读取以下集合，均实际返回 **200**：
  recognition-reviews、metadata-reviews、metadata-corrections、classification-reviews、
  confirmations、manual-intents。未运行 Worker、Provider 查询或媒体操作。
- `.venv/bin/mediaflow --help` 实际列出上述五种全局审核命令；注册与执行在
  `mediaflow/final_cli.py`。conflict 对应真实 `confirmations`，没有另造 conflict-reviews 地址。
- `web/src/shared/api/api-client.ts:confirmTaskItemRecoveryPreparation` 当前确实请求
  `/api/v1/manual-recovery-preparations/{id}/confirm`，
  `TaskItemRecoveryPanel.tsx` 调用并保存未知提交身份。不能只删后端路由。
- `manual_recovery_continuation.py` 的手工 native 摘要关联 discovery＋准确 Preview；
  自动化／直接 organize 的当前摘要使用真实 preparation 记录，`confirm_prepared` 在
  准入事务中保存 execution 关系。两者都是当前用途，不能按名称或记录年代删除。
- 正式 `/operations/organize/previews/{id}/execute`、`/admission` 以及 execution 查询已
  存在；`begin_web_execution` 已接受 preparation_id。先复用这些当前边界，保留原
  preparation 的 actor、checkpoint、选中项、权限和事务关联，再移除旧确认传输。

### Implementation Scope 与 Developer 开发指导

1. **先接通当前确认。** 从 `TaskItemRecoveryPanel` 的真实操作向后核对手工与自动化两条
   摘要链。让当前确认与未知受理核对走已有正式 operations organizing 边界；仅补齐该
   链路必需的精确摘要关联。保留 `confirm_prepared` 已有 actor／checkpoint／当前摘要
   校验和原子 preparation→execution 关联；手工 native 摘要仍绑定原 discovery＋Preview。
   不把自动化摘要当成手工 discovery，不绕开当前 permission、容量或同 Task 准入。
2. **删除已确认的旧传输。** 下表为注册表与代码中真实存在的退出集合；连同方法、查询、
   route templates、workflow 分类、广告路径和专用 reader／renderer 一起清理。
   当前 `/operations/manual-actions` 是正式动作投影，保留；不要按 manual 字符串批量删。
3. **沿真实调用清理专属实现。** 全局 CLI 的 parser/help、dispatch、专属批处理／渲染／
   import 退出；共享 `RecognitionReviewService`、Metadata、Classification、Confirmation
   及其有效记录继续供 TaskItemRecovery／分析／执行使用。删除确认路径中已无消费者的
   旧适配，当前 schema 和有效历史保持。`tasks ignore-item/ignore-pending` 等当前命令
   按原有作用域保留，不把所有任务管理或全部 CLI 作为旧产品删除。
4. **同步当前消费者。** 更新 API client、Task recovery model／panel 及实际调用的 fake、
   fixture、Python harness、安装包 smoke 和文档消费者。当前未保存输入、焦点、原 Task
   返回与当前未知提交上下文继续可读。只调整这次确认所需模型，不扩展到 Run once／Copy／
   Settings 其他 session 清理。现有 session 若记录旧 URL，由当前耐久请求身份读取原结果；
   不把存储内容变成向旧地址重发命令的依据。
5. **把原断言接回当前旅程后交接。** 旧全局 API／CLI 正向测试改为注销反证；其中审核
   决策、审计、权限、并发、逐项结果等业务断言保留在当前入口。由 Files／due／Run once
   实际受理，驱动原 Task 到决定、分析、摘要、确认和 Worker 结果。只修改必要测试接线，
   不开发新的验收平台。完成 affected tests 后提交一个连贯候选，交 B 独立验收。

| 退出表面（均为现有注册） | 本单元边界 |
|---|---|
| `/api/v1/recognition-reviews`、`metadata-reviews`、`metadata-corrections`、`classification-reviews`、`confirmations` 及其现有 detail／resolve／audit 子路由 | 退出全局队列／决策传输；四类 Task 决策与审计保留 |
| 同名五组 CLI，包含现有 list／show／resolve／resolve-pending | parser／help／执行分支退出，无改名的全局替代命令 |
| `/api/v1/manual-intents`、`manual-previews`、`manual-executions` 的现有列表／详情／choice／preview(s)／cancel／reconcile | 旧别名退出；operations organizing 的当前意图／摘要／受理核对／execution 读取保留 |
| `POST /api/v1/files/{id}/manual-intent`，`GET /api/v1/files/{id}/previews`，`GET /api/v1/resource-libraries/{id}/previews` | 旧准备／列表传输退出；当前 live Files 受理与精确 Task 关联保留 |
| `POST /api/v1/manual-recovery-preparations/{id}/confirm` | 先接回当前确认和原请求核对，再注销；不删当前 preparation 数据职责 |

旧地址在正常 Active／合法权限下使用通用 unknown route，旧 CLI 使用普通 parser 错误。
不添加专门退休处理、别名、转换、隐藏开关或替代全局队列。

### Acceptance Criteria

- [ ] AC-1：上表旧 API 的全部已注册方法／子路由与 CLI 命令退出。在正常 Active 和合法
  身份下 API 为通用 404；CLI 不在 help／parser。没有新 Task、授权、Provider 查询或
  Storage 效果；普通认证与脱敏安全审计保持。以代码中的真实注册清单验收，不构造假入口。
- [ ] AC-2：Files 单项／批量／有界文件夹和 Task Center 的四类处理均完成决定→一次允许的
  分析→准确摘要→显式选中确认→同 Task 结果。due／禁用定义 Run once 的初始意图和
  其后四类恢复保持；保存／分析零媒体变更，未选择／未就绪兄弟不被执行。
- [ ] AC-3：同一任务的手工 native 摘要与自动化 persisted 摘要都能确认，保留 actor、
  checkpoint、Preview／intent version、原 pin、选中子集和覆盖／清理权限。过期摘要、
  权限变化、满额及并发确认保留原状态与明确下一步；仅精确等价提交指向原 execution。
- [ ] AC-4：丢确认响应后关闭／刷新／重新认证、兄弟重新分析产生新摘要、双管理员操作，
  都核对原请求和原 execution／Task；不以最新摘要或最近任务替代。原请求无法读回时仍
  为未知，读取不重发。已完成／未知效果与附件独立结果保留，Worker 再次运行不重放。
- [ ] AC-5：用 Slice Base 真实入口建立正常 V2 的待决定、待确认和已受理请求／结果，再由
  候选打开继续；ID、digest／pin、原历史和有效 preparation 关系保持。候选同版本
  reopen／restart 后原请求仍可核对，不要求重新创建任务或配置。本单元不重写 schema。
- [ ] AC-6：当前九页、Files hosted organizer、Task Center 原详情／四类恢复、两种库普通
  Copy/Move/Delete 和通知继续使用。受影响处理界面在桌面、390px 和矮窗口可读，键盘、
  关闭／返回、未保存输入和未知确认状态保持；不增加常规确认步骤。
- [ ] AC-7：源码／测试／fake／harness／wheel／镜像／当前说明没有本单元旧传输消费者；
  所有被删除的正向测试说明其退出义务或保留断言的新位置。C 复用 A Naming／Classification
  仍为 C。T4 必需验收有实际结果后，B 才作 PASS／FIX REQUIRED。

### Required Tests

测试分工依 [workflow §6](docs/development-workflow.md#6-test-levels)。本轮开发及复核的
测试／构建累计时间分别小于该轮总耗时50%，含失败运行；记录实际区间。所需验收未完成
时保持待验收，不降低门禁、不删断言或用重复运行凑通过。先定位真实阻塞，再运行昂贵门禁。

**Developer — affected tests**（根目录；新增注销用例放现有受影响模块）：

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_confirmation_api tests.test_recognition_review tests.test_metadata_review tests.test_metadata_resolution tests.test_classification_review
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_manual_task_engine tests.test_processing_checkpoint tests.test_v2_manual_organize tests.test_automation_entrance_recovery
.venv/bin/ruff check mediaflow/interfaces/service_api.py mediaflow/final_cli.py mediaflow/application/manual_recovery_continuation.py
git diff --check
```

第一组保留共享决策与审计断言并检验旧入口注销；第二组覆盖当前确认、同 Task、容量、
原 pin、源变化、兄弟独立和已完成／未知非重放。另对实际修改文件运行 Ruff format/check。
若触及其他共享执行模块，加其直接受影响测试，在交接列明原因；不承担全仓回归。

Web（cwd `web/`）：

```sh
npm run test -- run src/shared/api/api-client.test.ts src/entities/operations/task-item-recovery.test.ts src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
```

更新确认及原请求核对的受影响用例；使用已有真实 Python harness，不从虚构请求直接
造可执行任务。Developer 只跑变更和直接受影响的原生旅程，不跑完整 Web／E2E／发布矩阵。

**B — acceptance 与 full regression**：对固定 Task Base..candidate 全部改动审查后，
独立核对 AC-1 的真实注册清单，复现 AC-2–5 的手工与自动化恢复、丢响应／兄弟分析／
并发／容量／pin 旅程；运行 [shared T4 full gates](docs/development-workflow.md#shared-full-regression-commands)。
风险专项原生命令（cwd `web/`，先完成 build；不同组各用新实例）：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/metadata-search-year.python.spec.ts tests/e2e/task-flow.python.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
```

B 另用现有 Base 夹具建立／候选打开方式验证 AC-5，核对同版本重启和精确结果导出；
检查桌面／390px／矮窗口真实截图及操作，完成候选 wheel 源码外消费者和 Docker 安全／
重启 smoke。完整日志、候选身份和复用依据存 `.git/validation-evidence/<sha>/task55-5-b/`。
只有输入相同的验收结果可依工作流复用；本次规划探测不作为实现验收。

### Non-goals 与全部 Slice 结果重评

本单元不做全局 schema 初始化／升级／重建清理、paused flow／pause_requested 与 Pause
专门处理退出、旧领域 Task／ScanTask 模型退出、其他 session／协议收敛或全站重设计。
不新增队列／恢复类型／权限／配置键／CLI 产品，不改变当前取消与五态语义。
这些保留的未交付范围仍由 Slice55 合同约束，不被本 Task 的验收代替。

| Slice 结果 | 当前交付与本 Task 覆盖 |
|---|---|
| RO-1 | 55.1 和55.4 已接受 Web 退出；保持正式九页／深链，不新增页面工作 |
| RO-2 | 55.2／55.3 已接受调度／票据／grant／非内核领取退出；本单元交付剩余全局审核与 manual-* 传输，Pause 专门处理随 flow 收敛 |
| RO-3 | 55.4 配置／身份／合法 V2 读取已 PASS；旧 Task／ScanTask 模型仍未交付 |
| RO-4 | 55.3 旧恢复链退出已 PASS；当前摘要记录保持，全局 schema／历史迁移与暂停清理仍未交付 |
| RO-5 | 本单元清理审核／确认直接消费者；其他 Run once／Copy／Settings 旧 session 等仍未交付 |
| RO-6 | 本单元同步其消费者／制品；全 Slice 最终门禁与 CURRENT 协调尚未完成 |

### Developer Completion Report / B Review Result

```text
Task: 55.5
Task Base: 8a9d2460d0fb4df1afee0e157af3736f136a64c8
Candidate: 3bff923de4127506c02a55b76cc7263b868554a6
Status: READY FOR B REVIEW
```

**实际改动**

- 恢复摘要确认改走现有 `POST /api/v1/operations/organize/previews/{id}/execute`：新增
  `preparationId` 关联；`confirm_prepared` 与 `confirm_native_preparation` 继续校验
  actor、checkpoint、当前摘要、原 Preview 和 intent version，并保留原子
  preparation→execution 关系。native 摘要仍绑定原 discovery＋Preview；persisted 自动摘要
  不被当成手工 discovery。
- 删除上表旧传输：五个全局审核 API／同名 CLI、`manual-intents`／`manual-previews`／
  `manual-executions`、`files/{id}/manual-intent`、旧 Preview 列表和
  `manual-recovery-preparations/{id}/confirm` 均不再注册，也无别名或退休分支。清理对应
  dispatch、route templates、workflow 分类、审计抑制、CLI parser／dispatch／renderer／import。
- Task Center 的摘要／执行／blocker 链接改指当前 operations organizing 与 Task recovery
  路径。checkpoint 的展示路径使用当前 Task recovery；其 hash 输入保留旧路径字面量，仅用于
  让未变化状态的既有 checkpoint digest／pin 保持可确认，绝不作为传输返回或调用。
- Web 同步：`TaskItemRecoveryPanel` 的确认走当前 Execute；session 固定保存完整提交身份
  （preparation、preview、itemIds、intent version、effects）；未知响应按该身份读取
  operations admission 证据再读原 Task；新增 preparation `intentVersion` 契约，删除旧确认
  client 与模型。E2E 中 task-flow／automation-run-once／operations-inventory 的确认拦截改指
  当前 Execute。
- 旧全局 API／CLI 正向测试改为 404／parser 反证；业务决定、权限、审计、并发、逐项结果
  断言保留在当前 Task recovery 入口或共享服务。更新当前说明中的旧审核／批量 CLI 描述。

**实际验证**

- 激活时治理 PASS；候选 `python3 scripts/check_governance.py` PASS，`git diff --check` PASS，
  `.venv/bin/ruff format --check .` 与 `.venv/bin/ruff check .` PASS。
- Required Developer Python 组：第一组 **31 tests OK（1.155秒）**；第二组
  **172 tests OK（11.911秒）**。另跑全量 `unittest discover -s tests`：
  **2385 tests OK, skipped=7（261.200秒）**。中间一次全量失败定位到一个被删除 helper 遗留的
  `@staticmethod` 挂到 `_safe_audit`，导致安全审计漏写；移除后上述相关测试与全量通过。
- Web（cwd `web/`）：typecheck、lint、format:check PASS；变更三组 Vitest
  **29 tests passed（2.73秒）**；`npm run build` PASS。真实 Python harness E2E
  `manual-organize-dialog.python.spec.ts` **8 passed（52.6秒）**。
- 未运行：B 的 T4 全量门禁、task-flow／automation-run-once／operations-inventory 两个风险
  E2E 组、wheel／镜像／Docker smoke；这些留给 B 在候选上执行。
- 时间：本轮自激活检查点 `5ac80672`（2026-11-17 23:58 +0800）至候选 `3bff923d`
  （2026-11-18 01:37 +0800）约 99 分钟；实际测试／构建命令合计约 11 分钟，低于本轮 30%。

**剩余风险／待 B 核对**

- 旧全局批处理 service 方法（如 `resolve_pending`）仍在共享审核服务内，但已无 CLI／API／
  Web 入口或调用者；本单元只退出其传输与专属渲染，未删除共享领域方法。
- checkpoint hash 保留旧路径字面量属于 pin 兼容输入，不是当前消费者；B 需确认既有
  preparation／Pinned request 在候选上仍可确认。
- 更新后的三份风险 E2E spec 只做了静态格式／lint 检查，尚未由 Developer 运行；B 需按
  Task 验收计划在候选上执行。
- 未运行 wheel／镜像及源码外消费者验证；B 的 T4 验收需覆盖。

### B 独立复核 — 2026-11-18 / FIX REQUIRED

```text
Reviewed Task Base: 8a9d2460d0fb4df1afee0e157af3736f136a64c8
Implementation Candidate: 3bff923de4127506c02a55b76cc7263b868554a6
Reviewed Handoff Head: 9c1322a742f2b5270c88bafedffcad58fb85a032
Decision: FIX REQUIRED
Next Action: DEVELOPER FIXES THE SAME TASK
```

B 从干净的 main／上述交接 Head 开始，治理 PASS、工作区和 Git 可写，独立审查完整
Base..Head 的41个文件。candidate..handoff Head 只有 TASK.md 交接说明；本轮执行输入
就是上述产品候选。以下两项留在同一 Task，原 Base、Goal、Scope、High／T4 不变。

**B55.5-01 — 已核对到选中兄弟的原执行，界面仍停在未知确认（P1；AC-2／AC-4）。**

实际用户旅程：Files 同一批中的 One、Two 均完成识别决定与分析；在 Task Center 打开
One 的新计划摘要，取消选择 One，只确认 Two。真实 Execute 返回202，浏览器丢失这次
响应，再点击“重新读取条目后再继续”。原 admission GET 已返回 `outcome=known`，包含
精确选中的 Two、原 executionId 和同一 taskId；One 的逐项摘要仍为 prepared，因为用户
本来没有选择它。页面却显示“已读回同一预览的受理执行，但未核对到本次计划摘要”，保留
锁定和“正在受理…”。此次原请求读取没有解除锁定。日志仅有一次 Execute POST。

原因在 `TaskItemRecoveryPanel.tsx` 的 `reconcile`：已绑定原提交的 admission 证明为 known
后，又要求当前打开文件的摘要必须 confirmed 且 executionId 一致。当前文件和用户选择的
子集可以不同；One 未被执行不应推翻 Two 的已受理事实。这个判断由候选 `3bff923d`
（2026-11-18 01:37:49 +0800）加入。本轮直接证明该候选有上述阻塞；未据此推断 Base
在同一丢响应场景的完整表现。

**开发指导：** 用本次提交保存的 Preview、选择、intent version、效果许可及对应 admission
证据完成原请求核对；known 后展示返回的原 execution／Task 受理事实，并刷新当前文件的
合法状态。修正集中在当前 panel 的核对完成与反馈，沿用现有 admission service；当前打开
的未选文件继续保有自己的待处理状态。把上述 One 摘要只确认 Two 的操作加到现有 panel
测试及 `operations-inventory.python.spec.ts` 的真实旅程，覆盖关闭重开、
刷新／重新认证和兄弟重新分析后的原请求核对。验收时原执行只受理一次，Two 的结果归属
原 Task，One 可按当前状态继续处理。

**B55.5-02 — 任务详情的迟到确认回归用例仍使用旧测试数据（AC-7 门禁阻塞）。**

`RunDetailTabs.test.tsx` 的 `keeps a late confirmation success from navigating a closed card`
在全量和单独运行均失败：生成摘要后找不到“新计划摘要”。其 `preparedSummaryDocument`
没有本次新增必填的 `intent_version`，因此当前 normalizer 拒绝该响应；同一测试稍后的
确认返回值也仍是旧确认接口的简短结构，缺少当前 Execute 的 items／actions／计数等。
测试尚未进入原本要证明的“提交中切换文件、关闭弹卡、迟到成功、重开读原结果”阶段。
这是测试消费者接线问题，不是已经证明生产界面会因迟到响应跳转。

同一 Task Base 的原测试在隔离源码中为 **1 passed**，候选为 **1 failed**
（两者其余24项均按测试名称过滤，未执行）。引入点同为 `3bff923d`：新 normalizer／Execute
返回契约已切换，该测试只更新了 URL 匹配。

**开发指导：** 将本用例的 preparation 和确认返回接到当前真实契约，可复用现有当前
organize execution fixture，并使用真实同 Task 身份；完整保留原本的单次提交、文件间隔离、
关闭不导航和重开读取已受理事实的断言。随后运行整个 RunDetailTabs 模块，确认实际执行到
这些断言。

**Developer 本次修复的直接测试（cwd `web/`）：**

```sh
npm run test -- run src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/RunDetailTabs.test.tsx src/entities/operations/task-item-recovery.test.ts src/shared/api/api-client.test.ts
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

将新场景放进该现有原生 spec，通过正常 Files 受理、Task 决定／分析和当前 Execute／admission
完成；沿用现有临时 SQLite／Local／Provider 夹具。交接修正候选及实际 affected 结果。
本轮未完成的 T4／Base 数据／制品验收继续由 B 执行。

**B 实际结果与证据：** 稳定本地目录
`.git/validation-evidence/3bff923d/task55-5-b/`；`runs.jsonl` 记录命令、cwd、时间和退出码，
原始日志、`subset-requests.json`、真实桌面截图 `subset-unknown.png` 一并保留。这些是本地
证据，没有声称远程可访问。复现只用了现有 Files／Task recovery／Execute／admission
入口和现有临时夹具；未读取用户配置、数据库、凭据或媒体，未修改产品代码或开发过程工具。

- Python 直接组：**68 tests OK**；完整回归：**2385 tests OK，skipped=7**
  （真实 SMB／OpenList／S3 及 endurance 环境的既有可选项）。Ruff format／check、compileall、
  pip check 均 PASS。完整回归保留 ResourceWarning 和故障注入运行信息。
- Web typecheck／lint／format:check／build PASS；完整 Vitest 为 **102 files passed／1 failed，
  1636 tests passed／1 failed**，失败即 B55.5-02。单独运行重现同一失败。
- 已有真实 Python 浏览器六条恢复旅程 **6 passed**：识别、Metadata 候选／修正、分类、
  冲突 Rename／明确 Overwrite，均通过同 Task 确认和实际 Worker 结果；其中既有390px
  分类／容量旅程通过。B55.5-01 的另一次真实浏览器复现记录 known 证据与页面持续锁定。
- Base 单项回归首次放在 `.git` 下的隔离源码时，Vite 无法读取 setup，尚未执行测试；
  改用仓库外临时源码后原用例通过。两次原始日志均保留，未把 setup 失败归因产品。
- 确认上述阻塞后按工作流提前 FIX REQUIRED。完整默认 E2E、两组完整风险 E2E、Slice Base
  数据由候选继续使用、完整窄／矮窗口检查、wheel／源码外消费者和 Docker 安全／重启尚未
  完成，均不记 PASS。Docker 初始未运行；本轮启动 Colima 后因已证明阻塞而未开始镜像
  门禁，已停止本轮启动的临时环境。当前测试输入改变后的所需门禁由 B 在修正候选重跑。

**本轮时间：** 以首次明确时间记录 2026-11-18 07:07:52 至
2026-11-18 07:23:56（+0800）计，复核至少 16.08 分钟；
`runs.jsonl` 中测试／构建命令累计 475.9 秒（49.3%），另有不足1秒的
治理短检查，合计仍小于50%。失败运行计入；计时保存在同目录 `timing.json`。

**全部 Slice 结果重评：** RO-1 的55.1／55.4 已接受结果保持；RO-2 的本次旧传输退出代码
及正常恢复路径已核对，但 B55.5-01 使当前确认恢复未完成，Pause 专门处理仍未交付；
RO-3 的已接受配置结果保持，旧 Task／ScanTask 模型仍未交付；RO-4 的全局 schema／暂停
清理未交付，本轮也未完成 Base 真实数据继续使用验收；RO-5 的本次未知确认仍需修正，
其他已列出的 session 清理仍未交付；RO-6 因 Web 回归失败及最终制品门禁待验收而未完成。
Slice55 继续 ACTIVE；本轮只交还 Task55.5 修复，不规划下一 Task，不作 Slice 关闭结论。

### Developer 修复报告 — 2026-11-18 / READY FOR B REVIEW

```text
Task: 55.5
Task Base: 8a9d2460d0fb4df1afee0e157af3736f136a64c8
Fix Candidate: 2f574e5d
Status: READY FOR B REVIEW
Prior Candidate: 3bff923de4127506c02a55b76cc7263b868554a6
```

**B55.5-01（P1）已修复。** `TaskItemRecoveryPanel` 的确认核对只以本次提交保存的
Preview、选择、intent version、效果许可及 `organize/previews/{id}/admission` 证据为准。
`known` 现在直接解除原提交锁定并显示返回的原 execution／Task、状态、选中数、完成／
失败计数，随后刷新当前文件的合法状态；不再用“当前打开文件的摘要必须 confirmed 且
execution 相同”反证已受理的兄弟子集。当前打开但未选择的文件继续保有自己的 prepared
摘要和确认入口，没有重发 Execute，也没扩大权限或清理范围。

**B55.5-02（AC-7 门禁阻塞）已修复。** `RunDetailTabs.test.tsx` 的迟到确认用例改用当前
契约：preparation 带必填 `intent_version`，Execute 202 返回完整 execution 文档（含精确
选中项、actions、计数与同 Task 身份）。原断言（单次提交、文件间隔离、关闭不导航、
重开读取已受理事实）全部保留并实际执行。

**受影响测试与接线**

- `TaskItemRecoveryPanel.test.tsx` 新增“One 摘要只确认 Two、响应丢失、admission known”
  用例：提交体只含兄弟项，读取 URL 只含该兄弟项与 intent version，known 后解除锁定并
  显示原执行／Task，One 的摘要仍可确认，确认 POST 仍为 1 次。
- `operations-inventory.python.spec.ts` 新增真实 Python 旅程：Files 受理同批两个文件→
  Task Center 分别保存识别决定并完成零变更分析→打开其中一个摘要→取消选择本文件→只
  确认兄弟→真实 Execute 202 被代理丢弃→读取 admission→显示原 execution／Task→关闭／
  重开证据仍读取已受理事实→真实 Worker 只完成被选兄弟→刷新并重新认证后原 Task 可读→
  在 Files 同卡修正并重新分析未执行文件后，原 admission 仍指向原 execution，Execute
  仍只有 1 次。该旅程使用既有临时 SQLite／Local／Provider 夹具，新增 Fifteenth／
  Sixteenth 专用源文件与 Provider 候选，避免消费其他旅程的媒体。

**实际结果（cwd、命令、真实计数）**

- `web/`：`npm run test -- run TaskItemRecoveryPanel.test.tsx RunDetailTabs.test.tsx
  task-item-recovery.test.ts api-client.test.ts` → **4 files / 55 tests passed（6.08秒）**。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`
  均 PASS。构建必须先于 Python E2E，否则 harness 仍服务旧 `web/dist`。
- `web/` 聚焦原生旅程：新增用例 **1 passed（2.8秒）**；既有兄弟独立／重新分析用例
  **1 passed（3.6秒）**（两者同一新 harness 顺序运行）。
- `web/` 完整 `operations-inventory.python.spec.ts`：**34 passed / 14 failed（1.6分）**。
  同一完整文件在 Task Base 源码（同一 harness、同一 provider／build 输入）为
  **34 passed / 13 failed**，失败集合与候选完全相同（候选多出的 1 个正是新增用例）。
  Base 复现已确认这些失败是既有环境／夹具问题，不是本次修复引入：
  `POST /__harness__/run-manual-organize` 在 Base 同样返回 500
  “Manual Organize Worker did not complete the admitted execution”，导致后续
  `run-manual-worker` 取到遗留 admitted execution。新增用例在干净 harness 单独运行通过；
  在完整文件顺序中，它受前面既有失败遗留队列影响而“取到别的执行”。B 的 T4 门禁如在该
  环境复现同一 Base 失败，应据此归因并在修正环境后重跑；没有据此声称 Web／E2E 全部通过。
- `scripts/operations_inventory_harness.py`：Ruff format／check PASS；
  `python3 scripts/check_governance.py` PASS；`git diff --check` PASS。

**时间与剩余风险**

- 本轮自开始读取（约 2026-11-18 07:22 +0800）至修复候选 `2f574e5d`
  （2026-11-18 08:10 +0800）约 48 分钟；实际测试／构建命令（含失败运行、完整 spec 与
  Task Base 复现）约 11 分钟，低于本轮 30%。
- 遗留：完整默认 E2E 的既有 13 个失败、T4 全量门禁、wheel／镜像／源码外消费者、
  Docker 安全／重启、Base 真实数据继续使用仍由 B 在修正候选上执行。B 需在干净 harness
  重跑新增旅程并确认已知 13 个 Base 失败的环境归因；本报告不声称这些门禁 PASS。
- 未改动产品 API／schema／权限／CLI 注册；没有新增全局队列、别名或隐性替代入口。

### 规划阶段检查记录（激活前）

本轮仅修改本文件；治理检查、`tests.test_governance` **20 tests OK（6.242秒）**、
`git diff --check` 通过。入口探测使用临时 managed Active 和已有 WSGI helper，六个集合
均为200；首次探测因引用错误的 harness 常量名在导入时中止，未发请求，核对实际常量后
完成上述探测。测试及探测耗时少于本轮阅读代码和规划总耗时的50%。这些是规划检查，
不是 Task55.5 产品 T4 验收；没有修改实现、Slice／Roadmap／Progress 或开发过程工具。
