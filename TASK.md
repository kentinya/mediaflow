# Task55.5 — 审核与整理确认只使用当前 Task 旅程

用户于 2026-11-17 明确要求“激活Task”，据此将已提交草案激活为正式实施 Task。
依据已提交 [Slice55](SLICE.md) 的 RO-2、RO-5、RO-6，保留 RO-4 的有效 V2 数据；
生命周期和测试分工遵循 [开发流程](docs/development-workflow.md)。

```text
Task ID: 55.5
Task Type: SLICE
Parent Slice: 55
Status: READY FOR B REVIEW
Task Base: 8a9d2460d0fb4df1afee0e157af3736f136a64c8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: TASK55.5 IMPLEMENTATION AUTHORIZED
Next Action: B REVIEWS TASK55.5 CANDIDATE 3bff923de4127506c02a55b76cc7263b868554a6
```

规划时 main／上述 HEAD，tracked／untracked 干净，工作区和 Git 可写，治理 PASS。
Base 为本单元实施前的真实提交，后续草案／激活提交不重设 Base。
Task55.1–55.4 的已接受结果保持；本单元尚无实现候选或 PASS／FIX REQUIRED 判断。

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

### 规划阶段检查记录（激活前）

本轮仅修改本文件；治理检查、`tests.test_governance` **20 tests OK（6.242秒）**、
`git diff --check` 通过。入口探测使用临时 managed Active 和已有 WSGI helper，六个集合
均为200；首次探测因引用错误的 harness 常量名在导入时中止，未发请求，核对实际常量后
完成上述探测。测试及探测耗时少于本轮阅读代码和规划总耗时的50%。这些是规划检查，
不是 Task55.5 产品 T4 验收；没有修改实现、Slice／Roadmap／Progress 或开发过程工具。
