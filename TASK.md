# NO ACTIVE IMPLEMENTATION TASK

Task55.4 **PASS**。B 已独立审查固定 Task Base 到候选 Head 的完整改动，
完成本单元 T4 验收。下一步：**Task55.5 规划草案，待实施授权**，见下文。
Slice55 仍 ACTIVE，尚未满足全部结果，不进入 A 终审或关闭。

```text
Accepted Task: 55.4 — 唯一当前配置：管理启动、发布与运行消费
Task Type / Parent: SLICE / 55
Task Status: PASS
Difficulty / Test Level: High / T4
Task Base: 64006c8d3b0a2791e5228417420250a064c75cea
Reviewed Head: 1d9b229b6e1910c2e3739d3836bee622332befbc
Latest Implementation: cc876e5ed7dcf803c4615a5663ec3c9399d20a11
Reviewer: B
Decision: PASS / NEXT TASK NEEDED
```

原计划、Developer 开发指导、AC-1–7、测试分工、前次 FIX REQUIRED 和修正交接保留在
[已审查候选的 TASK.md](https://github.com/kentinya/mediaflow/blob/1d9b229b6e1910c2e3739d3836bee622332befbc/TASK.md)。
Task55.1–55.3 的接受事实不变；Task55.3 固定接受范围
`b73c36353e5427cbe60fbb7c1b8cc85b139edca4..78d3e252090ca13149bf953b803eeb37918d9b30`，
其详细接受记录仍见
[64006c8d:TASK.md](https://github.com/kentinya/mediaflow/blob/64006c8d3b0a2791e5228417420250a064c75cea/TASK.md)。

## B 最终验收 — 2026-11-17

复核前 main／上述 Reviewed Head，tracked／untracked 工作区干净。治理通过，固定 Base
不变。最新提交只同步真实 Python E2E 的三处分类路径断言及注释和交接报告，没有产品改动。
本收尾只维护本文件，不修改 Slice／Roadmap／Progress 或实现。

| 验收 | 实际用户结果 |
|---|---|
| AC-1／2 | 四服务经最小 bootstrap 和明确 principals 启动；未初始化与空 Active 可区分。管理员在系统设置创建首个 Draft、检查精确版本并激活，之后才取得业务配置；规范导入／导出可用，新输入中的指定旧字段准确拒绝。 |
| AC-3 | 当前 typed Save、对象检查和 checked 发布可用；权限、并发、失效检查和未知请求核对保留。普通规则编辑成功，桌面、390px 和矮窗口可读，无旧分类转换卡。 |
| AC-4 | 分别由 Slice Base 和 Task Base 真实入口建立的 V2 数据在候选继续编辑、发布和执行。原 revision、digest、pin 和任务保持；原分类完整目录保持，原任务只完成一次媒体操作，后续 Worker 不重放。 |
| AC-5 | maximumActiveJobs、CANCEL_JOB／cancel_job 及当前容量、运行采用、取消和 Run once 保持；RecognitionType C 使用 A Naming／Classification 后仍为 C。 |
| AC-6 | 独立 strategy-test、默认业务装配及本单元指定旧输入／事件别名退出；当前分析、对象测试、手工整理、due／Run once、同 Task 四类恢复和通知仍可完成，原通知效果与历史保留。 |
| AC-7 | 空四服务 → 首 Draft／空 Active → 后继配置发布 → 常驻服务采用 → 实际业务操作和重启读回通过。源码外 wheel、镜像及本单元消费者与实现一致。 |

例如：管理员升级原实例后，在规则页只修改分类规则的名称，再分析原文件并确认原任务，
最终目录仍含 `Movies/Anime` 等原完整前缀；原请求、pin 和已完成结果继续可读，
再次运行 Worker 不会重复搬动文件。当前手工整理的桌面、390px、导出和重启读回也验证
同一完整路径；本轮修正的是过时的显示断言，原实际目标断言始终保留。

### 实际测试与证据复用

当前证据根为 `.git/validation-evidence/1d9b229b/task55-4-b/`，保留命令、退出码、
完整日志、trace、截图及制品身份；均为本地忽略产物，不声称远程可访问。

- 当前候选完整 Python 原生四 spec 组：**59 passed**，原计划命令在新实例直接通过。
  单独手工整理旅程另 **1 passed**，准备阶段经既有 Worker 入口处理较早 seed 任务，
  未改变生产领取顺序。完整组无此额外准备；Developer 先前失败日志保留。
- 当前候选 Docker 空实例／可选媒体挂载验收和 release-security 验收 **通过**。
  验证首 Draft／空 Active、精确发布、四服务不重启采用、签名通知、原目标恢复、实际
  COPY、常驻库操作、权限、镜像秘密扫描及结果／审计／日志脱敏。
- 复用 B 在 `2062f7f4` 的 **2385 tests OK，7 skipped**，以及 Ruff check／format、
  compileall、pip check、两份规范配置校验和 wheel 源码外安装／consumers；该处
  Docker 标准 smoke、restart／fault smoke 也通过。原命令和日志仍在该候选证据根。
- Web 执行输入与 B 的 `299d6e25` 保持一致，复用 **103 files／1636 unit tests**、
  typecheck／lint／format／build 和 **285 Node fake E2E passed**。
  本次改变的 Python 原生 spec 不参与这些套件，已重新完整运行。
- Automation 的47个场景均有匹配证据：原组 **46 passed、1 failed**，其中 Settings
  容量测试把前序 Copy 已存在的文件当成此次新增效果；完整 Settings spec 在独立实例
  **18 passed**，涵盖该用例。原 Lifecycle／Run once 的29项通过保持。
  原组失败和另一次中止的共享实例重复运行均保留，不计为通过。
- Slice Base／Task Base 真实 V2 配置、普通编辑、原 pin 续作和一次 Worker MOVE 的
  独立证据复用自 `2062f7f4`；校对原目标、原结果和第二次 Worker 无待执行项。
  `reuse-proof.json` 明确列出未变化的源码、测试、harness、依赖和配置输入，
  `reviewed-manifest.txt` 保留完整 Task 范围清单。

Docker 验收沿用现有脚本和全部业务断言，由 B 在忽略目录接通当前旅程：空实例脚本用
现有首 Draft 浏览器流程，media-free fixture 使用存在的隔离根，独立 CLI 经正式容器
entrypoint 加载部署环境；security 脚本在 managed Active 建立后执行其退休入口404断言。
第一次 CLI 未经 entrypoint 缺少 fake Provider 环境而失败，原失败日志保留，修正验收
调用后完整通过；这些接线未改产品或增加产品任务。

当前镜像 `mediaflow:task55.4-b-1d9b229b`，ID
`sha256:56579d0b284a06d34c1aeba27b67f1b96b85926e43154c901b6f72319de430af`。
与通过旧标准／重启门禁的镜像逐文件比较，安装 Python 源码、前端 dist 和依赖版本
完全相同；wheel 内 Python 与候选源码一致，构建输入也未改变。wheel SHA-256
`6d00f1224de4f417c04f201923273a60262b8312217331aba0352ed6a87d1be3`。
身份和比较见 `artifact-identities.json`／`image-executable-manifests.json`。

本轮计时记录时已工作921秒，合并测试／构建并加未单独计时命令的保守上界为393秒，
约42.7%，小于50%；原始区间含失败运行，见 `review-timing.json`。
本 Task 无未完成的必需门禁或阻塞项。隔离验收服务已清理，恢复原先停止的 Colima review
profile；未推送、发布或操作用户运行数据。

## 全部 Slice55 结果重评

固定 Slice Base `2b2e7c1824fa5681864455714d0f97b26555c7dc`，合同仍为 ACTIVE。

| 结果 | 本 Task 接受后状态与剩余范围 |
|---|---|
| RO-1 | Task55.1 已接受的当前 Web 入口保持，本单元规则转换表面退出已验收。 |
| RO-2 | 55.2／55.3 的 schedules、票据、grant 和非内核领取退出保持；全局 recognition／metadata／classification／conflict 审核入口及剩余 manual-* 传输表面仍待交付。 |
| RO-3 | 本单元配置权威、身份、严格新输入、合法 V2 读取及默认 runner 已完成；旧领域 Task／ScanTask 模型等与 flow／schema 耦合部分仍在。 |
| RO-4 | 55.3 已接受的旧恢复链结构退出保持；全局 schema 升级／重建、历史迁移结构及 paused 等五态收敛仍待交付。 |
| RO-5 | 本单元配置、事件、分类消费者完成；Run once／Copy／Settings 中缺 baselineValues 等旧 session 及其他协议适配仍待交付。 |
| RO-6 | 本单元样例、生成器、wheel、Docker 和说明完成；剩余单元、全 Slice 最终门禁及 CURRENT 协调仍待完成。 |

例如，当前用户已经能从首次设置一路完成配置发布和整理，但合同还要求审核与恢复只从
当前 Task 旅程进入、既有 V2 数据在清理 schema 和旧会话后继续可用；这些结果不能由
本配置 Task 的 PASS 代替。上述为 Task55.4 接受时的结果重评；本轮规划见下文，
不提交 Closure Packet，不提前将 TARGET 改为 CURRENT。

## Task55.5 规划草案 — 审核与整理确认只使用当前 Task 旅程

**本节仅为 B 规划草案，不授权实施。** 根文件保持 NO ACTIVE IMPLEMENTATION TASK。
依据已提交 [Slice55](SLICE.md) 的 RO-2、RO-5、RO-6，保留 RO-4 的有效 V2 数据；
生命周期和测试分工遵循 [开发流程](docs/development-workflow.md)。

```text
Task ID: 55.5
Task Type: SLICE
Parent Slice: 55
Proposed Status: PLANNED — DRAFT ONLY
Task Base: 8a9d2460d0fb4df1afee0e157af3736f136a64c8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

规划时 main／上述 HEAD，tracked／untracked 干净，工作区和 Git 可写，治理 PASS。
Base 为本单元实施前的真实提交，后续草案／激活提交不重设 Base。
Task55.1–55.4 的已接受结果保持；本单元尚无实现候选或 PASS／FIX REQUIRED 判断。

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

### Non-goals 与本轮全部 Slice 结果重评

本单元不做全局 schema 初始化／升级／重建清理、paused flow／pause_requested 与 Pause
专门处理退出、旧领域 Task／ScanTask 模型退出、其他 session／协议收敛或全站重设计。
不新增队列／恢复类型／权限／配置键／CLI 产品，不改变当前取消与五态语义。
这些保留的未交付范围仍由 Slice55 合同约束，不被本 Task 的验收代替。

| Slice 结果 | 当前交付与本草案覆盖 |
|---|---|
| RO-1 | 55.1 和55.4 已接受 Web 退出；保持正式九页／深链，不新增页面工作 |
| RO-2 | 55.2／55.3 已接受调度／票据／grant／非内核领取退出；本单元交付剩余全局审核与 manual-* 传输，Pause 专门处理随 flow 收敛 |
| RO-3 | 55.4 配置／身份／合法 V2 读取已 PASS；旧 Task／ScanTask 模型仍未交付 |
| RO-4 | 55.3 旧恢复链退出已 PASS；当前摘要记录保持，全局 schema／历史迁移与暂停清理仍未交付 |
| RO-5 | 本单元清理审核／确认直接消费者；其他 Run once／Copy／Settings 旧 session 等仍未交付 |
| RO-6 | 本单元同步其消费者／制品；全 Slice 最终门禁与 CURRENT 协调尚未完成 |

### Developer Completion Report / B Review Result

尚未实施。Developer 在实施授权后提交不可变检查点、实际 affected 命令／结果与剩余风险，
状态 READY FOR B REVIEW；B 审查完整 Base..Head 并作 PASS 或 FIX REQUIRED。
本轮结论：**规划草案完成；Slice55 仍 ACTIVE，尚未进入 A 终审。**

本轮仅修改本文件；治理检查、`tests.test_governance` **20 tests OK（6.242秒）**、
`git diff --check` 通过。入口探测使用临时 managed Active 和已有 WSGI helper，六个集合
均为200；首次探测因引用错误的 harness 常量名在导入时中止，未发请求，核对实际常量后
完成上述探测。测试及探测耗时少于本轮阅读代码和规划总耗时的50%。这些是规划检查，
不是 Task55.5 产品 T4 验收；没有修改实现、Slice／Roadmap／Progress 或开发过程工具。
