# Task PATCH-20261109-3 — 失败整理的文件释放与摘要入口一致性

用户于 2026-11-09 要求“写到Task里并激活Task”，确认下述开发后体验并授权将规划草案提升为
正式实施 Task。最新候选已由 B 独立复核完整 Base..Head，结论仍为 FIX REQUIRED：上一轮
两个阻塞已修正，当前剩余问题及同 Task 开发指导见文末最新 B 复核。不可变 Base、范围与
测试分工保持。

```text
Task ID: PATCH-20261109-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: FIX REQUIRED
Task Base: fe3bd99b1cf6046ac716052e5c8ee63851c80f15
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: USER-AUTHORIZED TASK ACTIVATION — SAME TASK CORRECTION
```

上一独立修正 PATCH-20261109-2 的 B PASS、精确 Reviewed Head／Accepted Implementation Head
及证据限制保留于[固定验收报告](https://github.com/kentinya/mediaflow/blob/da47f9dd1af56cc281d6e42323ae4892caed5f83/TASK.md#b-final-review--pass)。
本 Task 不重开 Slice52，不改变 SLICE／Roadmap／Progress 或既有验收事实。

### Goal / Authority

修复已有手动整理的失败恢复：失败文件可以从普通文件页重新发起，不必取消已经失败的任务、
清理内部意图或删除记录；任务中心只在原工作确实仍可继续时提供“继续整理”。正常未确认摘要
可在任务中心找回，混合批次保留有效文件的原确认流程，旧摘要不能重新获得失败文件的执行资格。

这是既有行为的独立修正，不新增重试系统或放宽执行边界。依据：
`V2-UX-001–003`、`V2-TASK-009`、`V2-OPS-014/016/017`、`UX-006`、
`REQ-RECOVERY-006/008/009`；任务五态与文件结果独立遵循 `V2-TASK-012–014`。
完整适用旅程为 [Manual organize](docs/product-experience.md#manual-organize)、
[failed/partial 新整理](docs/product-experience.md#current--new-organizing-after-failedpartial-history-slice47)，
及当前任务中心内正常等待首次确认的继续入口。
架构依据为 [source ownership](docs/architecture.md#current--files-admitted-organizing-task-and-verified-source-ownership-slice46)
与 [source-history gate](docs/architecture.md#current--source-history-gate-for-new-organizing-slice47)。
Slice46/47/52 仅作已接受合同引用，均不作为本 Task 的父 Slice。

### 开发后体验 / Delivery Outcome

下表为本 Task 必须交付的用户可见结果，作为 AC-1–6 和原生浏览器验收的具体场景；它描述
目标行为，不代表当前已实现或已通过验收。

| 场景 | 用户可见状态与可执行动作 |
|---|---|
| 整个任务已失败 | 任务中心不再显示“继续整理”；保留失败阶段、原因、历史结果和已知效果，指引回文件页重新发起。已失败任务无需再次取消。 |
| 文件项已失败，旧摘要尚未确认 | 该失败文件不再被原意图／摘要占用，可直接从文件页重新整理；旧摘要中的失败项只读且不可确认。旧任务／摘要仍保留失败证据。 |
| A失败，B/C正常待确认，任务仍有合法继续资格 | 原摘要保留B/C的选择与确认流程；A显示失败原因、已知效果和重新整理指引，单独从文件页重新发起，不必取消整批。 |
| 正常生成摘要，未确认就离开 | 从“任务中心 → 全部任务／进行中 → 对应任务详情 → 继续整理”回到同一摘要，选择条目后明确确认；关闭页面不取消、不丢失原工作。 |

普通重新整理沿用“文件页选择 → 重新分析 → 新摘要 → 明确确认 → 新工作结果”，使用当前
配置；已有同一请求的响应未知时先核对原请求，不自动重发。确认前不执行媒体文件变更。
用户无需清理内部整理意图或解锁记录；旧页面／旧授权不能再次执行已经失败的文件项。
成功兄弟不重跑，原记录和已完成效果保持；部分／不确定效果继续显示既有提醒并检查当前源、
目标和冲突，不把新请求当成对旧效果的自动重放或撤销。

### Observed gap / Planning evidence

- `SQLiteTaskRepository._find_owned_source_work_locked` 排除已结束的 TaskItem 后，还会调用
  `_discovery_source_owners_locked`；后者依据准备记录的状态、路径、版本和是否已有执行记录
  判占用，未统一核对关联 Task／该文件项已失败的事实。
- `MediaFlowApi._operations_run_files_preparation` 只证明关联身份，
  `RunDetailFacts` 只判断 `filesPreparation != null` 即显示“继续整理”，没有业务继续资格。
- `TaskLifecycleService` 拒绝取消终态任务；不能把“取消失败任务”当作恢复方案。
- `ManualOrganizeExecutionService` 的原 Task 采用逻辑遇到终态返回 `None`，可能走普通新 Task
  路径；必须实测旧摘要确认／授权／准入各入口，不能只隐藏按钮，也不能让已关联但失效的
  Files 摘要降级成无关联的新任务。现有未关联手动/API/CLI 路径仍保留自身合法语义。
- B 在本 Base 使用 `_SupersededHandoffFixture`：真实临时 Local／SQLite／假 Provider／
  Task engine 生成普通摘要，文件项实际为 `waiting_confirm`；随后**仅在临时数据库注入**
  文件项 `failed`，占用查询仍返回 `kind=discovery`；再注入关联 Task `failed`，真实详情 API
  返回200且仍有 `filesPreparation`，普通 Files 新提交返回409 `source_already_organizing`。
  这证明状态组合下的判断缺口；尚未证明用户现场的失败触发原因或自然故障路径。
  Developer 必须沿当前生产失败发布／读取路径补充可达性复现，区分真实文件失败、读取失败、
  正常四类业务等待和单纯发现完成；不能拿注入结果声称已有自然旅程验收。

### Workspace baseline

规划前 `python3 scripts/check_governance.py` PASS。分支 `main`，HEAD 为上述 Base；
工作区及 `.git` 可写，暂存区为空。预存已跟踪修改只有 `mediaflow/.DS_Store`；未跟踪
`.DS_Store`、`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、
`docs/`／`testdata/`／`web/` 元数据及 `output/` 既有材料全部保留且不纳入 checkpoint。
不读取用户运行数据库、私有配置、凭据或媒体。规划只改本文件；不修改 SLICE／Roadmap／Progress。

激活前 HEAD 为规划 checkpoint `785d5f621293ca7ab2740c9d3ab34a53c7bcc701`，
治理检查 PASS；工作区预存变化与上述清单一致且暂存区为空。本次只提交本文件的激活与体验
补充，不改变 Task Base，不纳入任何预存文件，不推送或部署。

### Implementation Scope

1. **先复现并统一资格。** 沿 Files 直接选择／目录发现 → 分析 → 摘要 → 确认 → Task／文件项
   结果发布，找到生产可达的失败边界。复用现有 application／repository 的身份、终态与
   per-item handling 规则，给出一致的“仍持有该文件／仍能确认该文件”判断；API／Web 消费同一
   后端事实。不得根据摘要存在、父 Task running 或前端布尔量推断执行资格。
2. **失败释放与旧资格收回一致。** 已记录 `failed/partial` 的确切文件不能再被其原准备记录
   重新占用；关联 Task 流程失败后，原准备与摘要不再有继续执行资格。复用既有事务／版本／
   claim fencing，在失败落定、旧确认和新手动准入竞争时保持一致；不以整个 Task 批量删除锁。
   不能只凭 discovery `completed` 释放正常待确认摘要，它表示发现完成而非整理工作结束。
   无法读取必要状态应给出明确读取失败与重读动作，不能当成“可用”或“已失败”。
3. **服务端防旧摘要执行。** 当前读取、重新分析、授权签发、已有授权消费、执行准入和 Worker
   发布等相关边界核对该 Files 关联与确切文件资格。失败落定后旧摘要／旧 token／迟到页面不能
   生成另一 Task、重开旧工作、执行失败项或覆盖新工作的结果。拒绝说明本次已结束／该项已结束、
   已知效果与从 Files 重新发起的下一步；网络未知提交继续按原请求核对，不另建工作。
4. **按批次成员恢复。** Task 仍合法且 B/C 等待首次确认时，仅 A 失败不能废弃 B/C 的摘要、
   选择或正常确认。摘要里 A 的失败原因／已知效果只读，不可选、不计入可执行数量；仍显示
   有效 B/C。旧客户端显式选择 A 或混合 A/B 时服务端拒绝该非法选择，不静默缩成 B 执行。
   A 的新手动整理使用当前配置并走已有历史提醒／完整新摘要／普通显式确认。
5. **任务中心及旧链接呈现。** 未结束且有合法准备工作可继续时保留“继续整理”（含尚在正常
   扫描／分析或四类业务处理中、可以打开查看的原工作），正常待确认保留全部／进行中归属。
   整个 Task 已失败、已取消或工作已真正结束时不再显示执行性质的“继续整理”；展示现有
   结果／失败阶段／已知效果，提供普通 Files 路径和“本次已结束，请从文件页重新发起”的指引。
   历史摘要在已有页面中只读可查，不新建独立历史中心；直接旧链接、刷新、后退、同版本重启
   必须得到同样判定。单个失败不能把仍有效的整批入口藏掉；流程失败也不能因有成功文件
   被改成 completed。不强制为每个文件新加恢复按钮。
6. **验证与必要事实协调。** 增补下面的直接回归和真实 Web 旅程；只在必要时细化现行
   Product Experience／Architecture 的上述规则，不重写 Requirements 接受事实或扩大合同。
   优先无 schema 变更；确需改变 schema、既有四类恢复语义或其他范围时先交 B 重评边界。

### Acceptance Criteria

- [ ] **AC-1 单文件失败可重发：** 当前支持的新 Files 工作产生真实失败后，原 Task／文件结果
  保持事实；未确认的原意图／摘要不再单独持有该失败文件。文件页新手动整理可正常准入，
  无需取消终态任务或清理记录；新请求只生成一份工作，仍需完整分析和新摘要显式确认。
- [ ] **AC-2 入口真实：** 整个 Task 已失败时详情无“继续整理”，历史与 Files 指引可达；旧摘要
  链接只读且解释失败阶段、已知效果、后续动作。无确认的普通健康摘要从全部／进行中仍可
  打开并确认同一 Task，关闭／刷新／认证续转不丢上下文、不自动执行或另建工作。
- [ ] **AC-3 混合批次独立：** A失败、B/C待确认时，A释放且不可选；B/C仍能在原摘要选择确认。
  A新工作不改 B/C 的 pin、资格和结果；父 Task 的 running 不是 A 占用依据。若整个流程已
  失败，则全部旧执行资格结束，已完成效果保留，不能用仍待确认的 B/C 复活失败流程。
- [ ] **AC-4 服务端与并发：** 旧页面确认／旧授权消费、失败发布、新 Files 直接／目录／混合
  选择准入并发，按已提交状态和确切版本收敛，不双执行、不把失效 Files 摘要转为新任务；
  失败已落定后的旧 Worker／迟到发布被 fence，健康在途工作仍保持互斥。状态读取失败不能
  释放占用；重复请求、响应丢失按原身份核对。
- [ ] **AC-5 安全历史保持：** `partial/unknown` 只沿既有手动新整理规则处理，保留步骤、源／
  目标、Results、原 pin／时间及不确定证据；自动化 due／Run once 的失败历史排除保持。
  不自动重放成功兄弟／不确定效果，不声称停止已发出的远端调用，不新增远端停止检测。
  没有自己的终态结果的 queued／processing 文件及真正未结束工作仍正常互斥。
- [ ] **AC-6 正常路径与输入边界：** 四类问题的合法保存／分析／摘要／显式继续保持；普通未关联
  API／CLI手动路径、RBAC、跨操作员隔离、Storage/path/version身份、当前权限、immutable pins、
  容量、conflict/overwrite/cleanup及 C→A识别身份不回归。错关联、越权、越界、失效版本、
  不存在来源和错误条目选择均有有界拒绝、零未授权媒体效果。读取历史零业务 mutation。

### Required Tests

遵循 [测试分工](docs/development-workflow.md#6-test-levels)：Developer 只跑新改和直接受影响
检查；B 对完整 Base..candidate 独立验收并承担 T4 全回归，不把全量门禁交回 Developer。
所有复现使用临时 Local／SQLite／假 Provider，不使用用户运行数据或生产外部 Storage。

### Developer — affected tests

实施后：

新增 `tests/test_failed_preparation_ownership.py` 聚合本 bug 的真实失败旅程、单项／混合批次、
事务竞争、旧授权及同版本 reopen 回归；尽量复用现有测试夹具，不为生产引入测试状态接口。
同时更新直接受影响的现有 Python／Web 用例，实际命令至少为：

```sh
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_failed_preparation_ownership tests.test_operations_task_center tests.test_manual_organize_execution
.venv/bin/python -m unittest tests.test_organize_source_history.PartialItemIsHistoryNotOwnerTests tests.test_organize_source_history.SupersededSingleFileOwnerHandoffTests tests.test_organize_source_history.SupersededOwnerWithRemainingWorkTests tests.test_organize_preparation.AdmittedSourceOwnershipTests tests.test_organize_preparation.SourceReidentificationJourneyTests
git diff --check
```

新增测试须覆盖：失败发生在摘要生成前／后、准备完成但任务未结束的区别、部分失败与整流程
失败、正常四类等待、父 Task running、错绑定与不可读资格、旧摘要／授权拒绝、新提交并发、
源版本替换／不同路径、失败 A 与待确认 B/C 的实际效果以及未知提交核对；production failure
publication测试与必要的状态注入竞争测试分别标注证据，不以注入代替全旅程。
失败前后的 Storage effects／Results／pins 和 sibling资格要实际断言。

在 `web/`：

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/library/StorageFilesPage.test.tsx src/entities/operations/run.test.ts
npm run typecheck
npm run lint
```

若实现改动对应意图页／摘要共享组件或其他模型，追加其现有直接受影响测试并记录具体命令。
对实际改变的 Python 文件执行 `.venv/bin/ruff check <changed-python-files>` 与
`.venv/bin/ruff format --check <changed-python-files>`；对改变的 Web 文件在 `web/` 执行
`npx prettier --check <changed-web-files>`，占位参数按实际清单替换，不运行全库格式化。

### B — acceptance and full regression

候选提交后：

- 独立复现 AC-1–6，审查所有受影响入口及事务；记录 Base是否自然可达、实际根因和引入来源，
  不把本轮注入调查当成产品验收。Task的五态／独立文件结果按当前规则判读。
- 执行 [T4共享全门禁](docs/development-workflow.md#shared-full-regression-commands) 中完整
  Python／Web／默认E2E／配置／禁止依赖／wheel及安装后smoke，并记录实际结果／不可用门禁。
  新增任务与文件占用及确认并发安全覆盖；Docker／同版本restart验证仅复用或补跑与当前修改
  相关的准入／恢复／生产边界，不为此重做无关部署基础设施。无生产推送或部署授权。
- 用现有 `scripts/operations_inventory_harness.py` 的临时真实 Python／SQLite／Worker 与
  production Web build，在现有 `web/tests/e2e/organize-source-history.python.spec.ts`、
  `operations-inventory.python.spec.ts`、`task-flow.python.spec.ts` 增补本 bug 旅程（如需夹具，
  仅增加隔离 harness 控制，走生产发布边界，不进产品 API）。明确命令，cwd `web/`：

```sh
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/task-flow.python.spec.ts
```

真实浏览器检查：单文件失败后返回任务中心无误导入口 → Files新摘要明确确认；健康未确认
离开再返回同一摘要；A失败／B/C待确认两条并行旅程；旧深链与刷新／认证续转；检查桌面与
390px失败文案、只读历史、可选文件与确认数量。确认前零媒体mutation，确认后只有合法选定
项有效果，旧页不能启动新工作；同版本reopen后结果一致。必要证据保存在候选SHA对应的
`.git/validation-evidence/`，不提交私有fixture或依赖已删除临时路径交接。

### Non-goals

不新增取消失败任务、意图管理／解锁页、独立 Retry入口、独立历史中心或确认checkbox；
不改变普通健康待确认摘要的占用语义、五态流程、四类业务恢复、自动化历史排除、CLI产品边界、
源指纹算法或Storage provider；不做队列／schema大重构、全局文件索引、远端停止证明／探测、
附件恢复扩展、旧任务转换／跨版本升级、历史清理、生产数据修复、推送或部署。
已支持新工作的同版本重启／重新打开必须覆盖；不以“无迁移”排除这条义务。

### Developer Completion Report

**Status: READY FOR B REVIEW。** 实现 checkpoint `192d3c44e2613e7d0beb6c511475ffe14e9ad5181`
（Base `fe3bd99b`，前一提交 `605a1598` 为本 Task 激活记录）；分支 `main`，未推送。
预存脏文件（`mediaflow/.DS_Store` 及全部未跟踪文件）未纳入任何提交。

**根因与实现。** 生产可达失败边界：Task engine 的 `_fail_discovery`（分析/读取 pass 异常时
发布 Task FAILED + PENDING/PROCESSING item FAILED，不动 discovery 行、不动 waiting item）。
该落定后：(a) `_discovery_source_owners_locked` 仍按记录存在判占用，新 Files 提交 409；
(b) `find_open_media_discovery`/事务内 open-signature 检查把新请求收敛进死记录；
(c) 详情 API 仅证明关联身份，`filesPreparation` 存在即渲染“继续整理”；
(d) 旧摘要确认经 `_adopted_organize_task` 返回 None 后静默另建新 Task。
统一资格事实 = `PersistentTaskStatus` 五态终态集合，新增 domain 常量
`SETTLED_TASK_FLOW_STATUSES`（completed/legacy partial_success/failed/cancelled）：

- `sqlite_runtime.py`：item 分支 SQL 排除终态 Task 的未决 item；discovery 分支新增
  `_discovery_owner_still_holds_source_locked`——链路 Task 终态则整份释放，Task 未决则按
  确切 Storage 身份逐文件判定（该文件 item 全部 settled 才释放；无 item 或不可读保持保守
  占用）；两个 admission 收敛边界同样排除已终态 flow 的记录（同 requestId 重试仍对到原记录）。
- `manual_organize_execution.py`：`authorize` 与 `execute`（消费）均新增
  `_assert_files_preparation_live`——Files 关联且链路 Task 终态时 409
  `preparation_flow_ended`，读取失败 503 `eligibility_unreadable`；普通未关联 API/CLI 路径
  与 recovery 准备不受管辖。
- `service_api.py`：`filesPreparation` 增加 `continuable`；discovery/preview 文档增加
  `organizeFlow` 并据此关闭 `actions.execute.available`；共享 `_organize_flow_document`。
- Web：`RunFilesPreparation.continuable`、`OrganizeDiscoveryModel.organizeFlow`（严格归一化，
  缺字段即拒绝）；运行详情终态改渲染“本次整理工作已结束”+只读摘要链接+从文件页重新发起；
  摘要页终态 banner、禁用修正/重新分析/确认（服务端 execute action 同步拒绝）。

**实际命令与结果（全部通过，无 skip 掩盖）。**

```sh
python3 scripts/check_governance.py                    # PASS
.venv/bin/python -m compileall -q mediaflow tests scripts  # OK
.venv/bin/python -m unittest tests.test_failed_preparation_ownership
  tests.test_operations_task_center tests.test_manual_organize_execution   # 68 OK
.venv/bin/python -m unittest tests.test_organize_source_history.{PartialItemIsHistoryNotOwner,
  SupersededSingleFileOwnerHandoff,SupersededOwnerWithRemainingWork}Tests
  tests.test_organize_preparation.{AdmittedSourceOwnership,SourceReidentificationJourney}Tests  # 16 OK
.venv/bin/python -m unittest tests.test_task_source_ownership_race tests.test_organize_preparation  # 46 OK
.venv/bin/python -m unittest tests.test_organize_source_history        # 23 OK
.venv/bin/python -m unittest tests.test_media_discovery                # 156 OK
.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_task_persistence  # 58 OK
.venv/bin/ruff check <6 changed py files> / ruff format --check <同上>      # All checks passed
git diff --check                                       # clean
web: npm run typecheck / npm run lint / npx prettier --check <6 changed files>  # clean
web: npm run test -- run OperationsInventory.test.tsx OrganizeCreationPage.test.tsx
  StorageFilesPage.test.tsx run.test.ts                # 146+ tests OK（含新增终态呈现用例）
```

新增 `tests/test_failed_preparation_ownership.py`（4 旅程，全部走真实 Files/API/engine 入口，
失败经 engine 自身 `_fail_discovery` 生产发布边界产生，标注于模块 docstring）：摘要前整流程
失败→释放+新准入+同 requestId 对账；摘要后重分析失败→waiting item 冻结证据+释放+旧摘要
确认 409 `preparation_flow_ended`+零 mutation；混合批次（One 逐项分析失败/Two waiting）→
One 释放、Two 仍占用、选 A 拒绝、确认 B 采纳原 Task 执行、A 新工作独立完成；健康未确认摘要
→continuable、重开同一摘要、延后确认成功、完成后转只读。`run.test.ts` 增加 continuable
归一化/拒绝用例；`OperationsInventory.test.tsx` 增加终态无“继续整理”+只读链接用例。

**已知边界与风险（供 B 审查）。**

1. B 的注入式调查（`_SupersededHandoffFixture` 风格注入 item/task failed）未被复用为本轮
   证据；本轮以 engine 失败发布边界复现，未证明用户现场具体触发原因（如真实 Provider 中断
   或 Worker 崩溃的具体形态），根因引入时间待 B 判读。
2. 逐文件释放对“同 path 多 item（不同 occurrence）”按“全部 settled 才释放”保守判定；
   四类业务等待以 waiting（unsettled）保持占用，仅以 waiting_confirm/终态 journey 断言，
   未单独构造 waiting_metadata 自然旅程（同 unsettled 集合同一路径）。
3. 执行阶段整流程失败（worker 崩溃→`_record_failure`）与取消路径未新增专属 journey；其
   终态判定与本轮同一 status 事实，既有 `test_manual_task_engine`/handoff 用例未回归。
4. B 的 T4 全回归、E2E（organize-source-history / operations-inventory / task-flow python
   specs）、wheel/packaging 门禁未由 Developer 执行，按分工属 B。

### B Review Result

**FIX REQUIRED — 2026-11-09。** 独立审查完整 Task Base
`fe3bd99b1cf6046ac716052e5c8ee63851c80f15` .. Reviewed Head
`1edce6655933f7f9cc5f2abc85667a0c067b57de`（13 个变化文件，含规划、实现、测试及交付报告）。
实际实现 SHA 为 `192d3c44c53ca43d3535349380d7bf9091030faf`；上方 Developer 报告所写
`192d3c44e2613e7d0beb6c511475ffe14e9ad5181` 不是该实现的真实 SHA，以本次 Git 核对为准。
本轮只维护本 Task，不修改产品实现，不重开已关闭 Slice52，不变更 SLICE／Roadmap／Progress。

**交付核对。** 四个新增 Python 旅程通过，表明顺序执行时失败释放、旧摘要拒绝、混合批次及
健康确认已有部分实现。Web 的真实准备页却无法读取记录，正常摘要和只读历史均不能完成；
失败发布与旧确认交错时，还会另建任务并执行旧摘要。因此 AC-1–6 不能判定整体通过。

| 阻塞 | 实际用户旅程及结果 | 原因与验收对应 |
|---|---|---|
| B3-01 — 准备页无法读取正常后端记录 | 文件页选择 One → 批量整理 → 已进入带 discoveryId 的准备页 → Worker 已分析 → 页面仍显示“无法读取准备状态”，没有计划摘要，不能确认；刷新仍读同样的数据。任务中心返回同一准备页也受影响。 | `web/src/entities/operations/discovery.ts` 的 `boundedText` 按对象键读取；新增调用却用 `organizeFlow.taskId`／`organizeFlow.status`，而后端嵌套对象实际只有 `taskId`／`status`。所有带关联 Task 的正常记录都解析失败。阻断 AC-1/2/3/6。 |
| B3-02 — 已失败任务的在途确认另建任务并复制文件 | 同一准备摘要在两个窗口打开：窗口一确认原摘要，执行当前源检查期间，窗口二请求重新分析；Worker 的分析读取失败将原 Task 落为 failed。窗口一随后仍收到 202，新增另一 Task；运行既有执行 Worker 后，临时目标出现 One 的实际副本。 | 新增 `_assert_files_preparation_live` 在准入事务之前读取状态；之后 `_adopted_organize_task` 看到原 Task 已失败返回 None，`task_id = adopted_task_id or uuid4()` 转入新任务。`admit_manual_execution` 仅在传入 adopt_task_id 时核对原任务，未在同一事务固定 Files 关联。违反 AC-3/4 的旧摘要不能变成新任务要求。 |

B3-01 由本候选实现提交于 2026-11-09 09:46:56 +08:00 新增。B3-02 的终态返回 None／
新任务路径可追溯至 `1e46e5baa`（2026-11-01）；本轮新增的事务外检查未覆盖这个原有竞争窗口，
它仍是本 Task 明确要求修复的范围，不是另开需求。这里的两窗口交错通过现有确认／重新分析
入口复现；夹具只安排源检查中的时间点并在分析调用处产生读取异常，Task FAILED 由生产
Worker 自身发布，没有直接改写 Task／文件状态，也没有构造新产品入口。未声称复现用户现场
具体的服务中断原因或真实并行浏览器操作。

### 同 Task 修正开发指导

1. **先恢复准备页实际读取。** 在现有归一化函数按嵌套对象的真实键读取 `taskId`、`status`；
   直接用后端实际响应形状覆盖 running／failed 两种记录。让正常摘要、任务中心返回与失败
   只读摘要真正显示，不增加另一套模型或宽松兼容路径。现有页面用例也必须带该真实字段，
   避免仅用缺少 organizeFlow 的旧夹具验证页面。
2. **把 Files 身份带进现有准入事务。** 已关联 Files 的确认只能接回确切原 Task；在
   `admit_manual_execution` 同一事务内读取原关联和流程状态，决定采纳或拒绝。原 Task 已结束
   就返回既有的结束说明，不能走普通未关联 intent 的新建 Task 分支。保留普通 API／CLI
   未关联路径及合法四类恢复的现行语义；不要仅在事务前再加一次读取。
3. **固定真实交错回归。** 复用 `tests/test_failed_preparation_ownership.py` 的临时 Local／
   SQLite 夹具，从现有摘要确认入口进入，在 execute 的源检查期间经现有 analyze 入口和
   Worker 发布原 Task failed，再完成确认；断言拒绝、没有第二 Task、授权没有被准入消费、
   目标零新效果、原失败与兄弟证据保留。另覆盖旧授权消费在同一窗口内落后的情况；同一原
   确认先提交成功时，以该实际提交结果为准，不伪造“失败已先落定”。
4. **交付仍是原 Task。** 修正后跑原 Developer affected tests，追加
   `web/src/entities/operations/discovery.test.ts` 和新增竞争用例；只更新实际改动的测试／夹具。
   原 B T4 全回归、三个真实 Python E2E、桌面／390px、同版本 reopen 和包装验收保持由 B
   负责。无需开发新的治理或探测工具，不要求 Developer 代跑全量门禁。

### B 本轮实际验证与剩余验收

本地证据目录：`.git/validation-evidence/1edce6655933f7f9cc5f2abc85667a0c067b57de/b-review/`。
证据为当前机器本地材料，不声称已上传或远程可达。

| 命令／检查 | 实际结果／证据 |
|---|---|
| `python3 scripts/check_governance.py`（复核前／文档更新后） | PASS；main，Reviewed Head 如上，复核起点暂存区空，预存脏文件保持原样。 |
| `.venv/bin/python -m unittest tests.test_failed_preparation_ownership` | 4 tests，OK，0 skips；`failed-preparation-tests.log`。 |
| `npm run build`（cwd `web/`） | PASS；`web-build.log`，真实 E2E 使用本次 production build。 |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts --max-failures=1`（cwd `web/`） | 1 failed，30.1s；停在原 spec 第124行等待“计划摘要”。实际页面显示“无法读取准备状态”；见 `source-history-e2e.log`、`error-context.md`、`trace.zip`。未改 spec／selector／timeout。 |
| `PYTHONPATH=. .venv/bin/python .git/validation-evidence/1edce6655933f7f9cc5f2abc85667a0c067b57de/b-review/race_probe.py` | 确定性交错复现 B3-02：原 Task failed，旧确认202，第二 Task 最终 completed，临时目标实际产生 One 副本；`race-probe.log`。 |
| `git diff --check fe3bd99b..1edce665`；`git diff --check` | PASS；分别核对候选范围与本轮文档更新。 |

已证明产品阻塞,按工作流提前 FIX REQUIRED;未继续全量 Python/Web/默认 E2E/wheel/
Docker 等门禁,不把未执行项写成 PASS,也不转交 Developer。失败只读页、健康摘要返回、
混合批次的原生桌面/390px与认证续转/同版本 reopen 仍待修正候选后由 B 验收。
本轮测试耗时约一分钟,低于本轮代码审查、复现定位和 Task 记录总耗时的一半;不靠延长等待
满足时间比例。没有新增 Task 或扩大修正范围。

### Developer 同 Task 修正交付 — 2026-11-09

**READY FOR B REVIEW。** 修正实现 checkpoint(实现提交)
`d39765bfbb1cc3fbd2d7831208dc053f375743ff`,实测于 `git rev-parse HEAD`(本节随后以
`docs(task)` 提交,两者共同构成本候选;若 SHA 与 Git 不一致以 Git 为准)。
Task Base `fe3bd99b` 不变,
分支 `main`,未推送。7 个变化文件全部在本 Task 范围;预存 `mediaflow/.DS_Store`、全部
未跟踪文件与 `.git/validation-evidence/` 本地材料未纳入任何提交,规划前治理检查 PASS。

**B3-01 修复(准备页读取)。** `web/src/entities/operations/discovery.ts` 的归一化改为按
嵌套对象的真实键读取:`normalizeBoundedText(flow["taskId"], "organizeFlow.taskId", ...)`
与 `flow["status"]`(旧代码把带点的路径当字面键读,后端真实文档必然解析失败,页面只显示
“无法读取准备状态”)。`organizeFlow` 键缺失现在 fail closed,`continuable` 缺失或非布尔
拒绝,`null` 仍表示无关联流;不引入第二套模型。页面/实体夹具改为带真实嵌套形状:
`OrganizeCreationPage`/`OrganizeDiscoveryPage`/`StorageFilesPage` 的准备页文档、
`discovery.test.ts` 的 payload 均带 `organizeFlow`,并新增 running/failed 两个真实形状
读取用例与缺键/缺字段拒绝用例;新增准备页终态用例(计划摘要可读、无“无法读取准备状态”、
已结束 banner、确认按钮因真实 `execute.available=false` 拒绝理由而禁用、无重新分析入口)。

**B3-02 修复(事务内 Files 身份)。** `sqlite_runtime.admit_manual_execution` 在同一
`BEGIN IMMEDIATE` 事务的 intent 校验之后新增 `_assert_files_preparation_live_locked`:
按与 `_adopted_organize_task` 相同的查询(intent 最新 discovery 行)读取关联
`organize_task_id` 与 Task 状态——无关联行/无 Task(仅分析 run)保持普通新建路径;
已终态返回与应用层一致的 409 `preparation_flow_ended`(同文案同 details);
Task 存活但 adoption 未重接(主体/引脚不一致)返回 409 `admission_changed`,绝不落入
未关联 intent 的新建 Task 分支;关联 Task 行不可读同样 409 拒绝。应用层原来的章程前
预检查(authorize/execute)保留,作为事务 fence 之前的服务性快拒绝;普通未关联 API/CLI
与 recovery preparation(`preparation_id`)语义不变。

**真实交错回归与遮断自证。** 新增 `ConfirmationCrossingFlowFailureTests`(均走真实入口,
失败只由 engine 自身 `_fail_discovery` 发布,标注于 docstring):

1. 摘要确认( `/previews/{id}/execute` 联合入口):authorize(健康)后,execute 自身的源检查内
   经现有 analyze 入口触发读取失败并 drive 出 Task FAILED,随后完成确认 → 实测 409
   `preparation_flow_ended`;无第二 Task、预授权未被准入消费(无执行行、状态非 consumed)、
   目标零 mutation、原 waiting item 证据保留、发现文档 `organizeFlow` 健康/失败两态逐键断言。
2. 旧授权( `/manual-previews/{id}/authorize` 健康时签发)在 `/consume` 的源检查内同一窗口
   落后 → 409;失败已落定后再次 consume 仍 409;授权始终未被消费,同一组零效果断言。

遮断自证:临时移除事务 fence 后重跑这两个新用例,均复现 202 且产生第二 Task(与 B
`race_probe.py` 同形态);恢复 fence 后全部通过——用例不是对既有实现的镜像。fixture
编排仅选择源检查中的时间点并驱动生产失败发布,未直接改写 Task/文件状态。

**实际命令与结果(全部实测,无 skip 掩盖)。**

```sh
.venv/bin/python scripts/check_governance.py                  # PASS(实施前/文档后各一次)
.venv/bin/python -m compileall -q mediaflow tests scripts     # OK
.venv/bin/python -m unittest tests.test_failed_preparation_ownership \
  tests.test_operations_task_center tests.test_manual_organize_execution   # 70 OK
.venv/bin/python -m unittest tests.test_organize_source_history.{PartialItemIsHistoryNotOwner,
  SupersededSingleFileOwnerHandoff,SupersededOwnerWithRemainingWork}Tests \
  tests.test_organize_preparation.{AdmittedSourceOwnership,SourceReidentificationJourney}Tests  # 16 OK
.venv/bin/python -m unittest tests.test_organize_preparation \
  tests.test_processing_recovery_admission tests.test_automation_entrance_recovery  # 58 OK
.venv/bin/python -m unittest tests.test_task_source_ownership_race      # 13 OK
.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_task_persistence  # 58 OK
.venv/bin/python -m unittest tests.test_media_discovery                # 156 OK
.venv/bin/ruff check mediaflow/infrastructure/sqlite_runtime.py tests/test_failed_preparation_ownership.py
.venv/bin/ruff format --check <同上两文件>                             # pass(先 ruff format 后复查)
git diff --check                                                        # clean
web: npm run test -- run OperationsInventory.test.tsx OrganizeCreationPage.test.tsx
  StorageFilesPage.test.tsx run.test.ts discovery.test.ts OrganizeDiscoveryPage.test.tsx
                                                                       # 164 OK(含新增终态/键拒绝用例)
web: npm run typecheck / npm run lint / npx prettier --check <5 changed web files>  # pass
```

**剩余风险与行为变化(供 B 复核,未自行判定通过)。**

1. 用户现场的具体失败触发形态与根因引入时间仍待 B 独立判读;本轮仍沿 engine 失败发布边界
   组织交错,未声称复现真实 Provider 中断或 Worker 崩溃的具体形态。
2. 行为收窄:关联 Task 存活但 adoption 不能重接(跨操作员确认他人 Files 摘要、引脚不一致)
   现在拒绝 `admission_changed`,旧实现会静默新建第二 Task。受影响既有用例全部通过,未发现
   依赖旧路径的测试,但是否触及既有合法多操作员旅程请 B 复核。
3. Python 侧 `organizeFlow` 文档形状与 Web 读取器由双侧用例钉住,但真实浏览器
   (prepare 页、任务中心返回、旧深链)仍以 B 的 python E2E 与桌面/390px 验收为准;
   本轮未跑 E2E/T4 全门禁/wheel/Docker/同版本 reopen,按分工属 B。
4. 预检查与事务 fence 双层:读取失败仍保持 503 `eligibility_unreadable` 的 fail-closed
   语义,未改为宽松;`preparation_flow_ended` 出现在预检查与事务两个边界的文案保持一致。

本轮总耗时约 85 分钟,其中测试执行(单测、静态检查、typecheck/lint)累计约 6 分钟,
低于 30% 上限;测试编写与 B3-01 失败定位属实现工作,未以延长等待凑比例。未越权改
SLICE/Roadmap/Progress,未推送,未自签 PASS。


### B 独立复核 — FIX REQUIRED（2026-11-09，最新）

Reviewed Base: `fe3bd99b1cf6046ac716052e5c8ee63851c80f15`。
Reviewed Head: `b33415e98c3f9bdca36c170ef950d32f50b024c8`。
Implementation Head: `d39765bfbb1cc3fbd2d7831208dc053f375743ff`。
独立审查完整 17 文件差异及关联准入／发布／页面链路。**B3-01、B3-02 已修正**：真实准备
响应能够读取；失败跨过确认源检查时，事务内拒绝失效 Files 关联，没有第二 Task 或媒体效果。
没有新增数据库表、列、迁移、schema version 或状态枚举值；`organizeFlow`／`continuable`
是现有状态的响应投影，终态常量只集合已有值。

**B3-03 / P1 — 已结束工作的只读历史与页面动作没有完整交付（AC-2／Implementation Scope 5）。**

用户完整操作：文件页选择 One → 批量整理 → 得到完整摘要 → 点击已有的“重新检查并更新
摘要” → 本次分析读取失败 → 刷新／重新认证 → 任务中心对应失败任务 →“查看只读摘要”。
真实 Worker 已发布 Task failed，准备记录仍为 analyzing，previewId 已清空。页面同时说
“正在完整分析并生成计划摘要”和“本次整理工作已结束”；所谓计划摘要只有等待 Worker 的
占位文字，没有原文件／方案内容。任务中心只读链接返回同一占位页，同版本 reopen 后保持。
原摘要通过其原 ID 仍能读取（HTTP 200），所以记录未删除，缺的是已有页面上的历史关联及
正确结束呈现。未确认的临时源文件仍存在，目标无媒体效果。

另一条不注入故障的正常旅程：文件页摘要 → 明确确认 → Worker 真正完成 One 的 MOVE →
任务中心“查看只读摘要”。该页仍显示并启用“重新检查并更新摘要”，点击实测 409
`analysis_rejected`。已结束工作不应继续提供该操作。后端拒绝有效，未出现再次执行。

根因：`_enter_analysis` 进入重分析时清除当前 preview 关联；`_fail_discovery` 只发布 Task
失败，保留原 discovery 的 analyzing 事实。本次 Web 新增结束 banner，却仍无条件按 discovery
状态渲染主进度和无摘要占位；有摘要分支的重新检查按钮也没有消费结束事实。追溯前者现有
链路至 `b5a21ea3`／`75a12d34`；本次未补齐 Task 已要求的失败历史旅程。不要用改写原失败
状态、重开工作或单纯改提示文字代替实际历史内容。

**B3-04 — API 合同变更未同步全部直接受影响的夹具。**

完整 Python 回归的 golden contract 比对失败，差异是真实响应新增的两处 `organizeFlow: null`；
默认浏览器五条准备旅程因 `web/tests/fake-server.mjs` 缺少这个必需键而停在读取失败，无法
显示摘要／范围不完整结果。不可变 Base 上 golden contract 用例通过；Base production build
上的原目录整理浏览器用例通过（497ms），当前同用例失败。这证明本轮夹具遗漏；真实后端
正常准备已通过，不能将这些 fake 失败描述成生产文件页全面故障。

### 同 Task 剩余开发指导

1. 沿现有 discovery→intent→已保存 preview 关系，让已结束准备页能读取原有方案作为历史；
   复用 repository 的 `get_latest_manual_preview`／`list_manual_previews` 及既有只读读取语义，
   后端给出确切关联。重分析中的旧方案不能成为当前可执行方案，不新建表／状态／历史中心。
   从未生成过摘要时明确说明没有摘要；已有摘要时必须能看到原条目、方案和当时证据。
2. 已结束的流程统一显示结束事实及任务详情／Files 下一步，不再显示 Worker 正在分析或等它
   完成的提示。所有摘要分支的选择、修正、重新分析和确认都消费同一后端继续资格；保持正常
   未确认摘要及 A失败、B待确认的原批次行为。保留本轮已通过的事务 fence。
3. 回归从以上两条真实入口完成，不只构造 `failed + previewId` 的页面文档。现有结束页单测
   用 `/重新分析/` 查询按钮，漏掉实际名为“重新检查并更新摘要”的按钮；按用户真实名称及
   动作检查只读性。补充重分析读取失败后原摘要可达／无假等待、刷新／同版本 reopen 的断言。
4. 同步直接受影响的 golden contract 和 fake API：前者用
   `MEDIAFLOW_UPDATE_FIXTURES=1 .venv/bin/python -m unittest tests.test_manual_operations_contract`
   从真实响应生成并审查差异；后者按其真实关联语义提供 `organizeFlow`（无关联明确为 null）。
   既有真实浏览器用例第3918行对完成后“继续整理”的期望，改为验证“查看只读摘要”及真正的
   只读内容／动作；不得删掉正常未确认返回同一 Task 的验证。
5. Developer 仍只跑原 affected plan 及本次直接改变的合同／页面／浏览器用例。B 保留全回归、
   原生桌面／390px和包装验收责任；其他未定位的旧浏览器失败不转成 Developer 的泛化返工。
   不另开 Task，不改 SLICE／Roadmap／Progress，不开发新治理工具。

### B 本轮结果、证据与验收边界

证据目录：`.git/validation-evidence/b33415e98c3f9bdca36c170ef950d32f50b024c8/b-review/`，
仅在当前机器本地。`native_harness.py` 复用现有 production-build harness，仅在用户显式重分析
后的依赖调用抛一次 DiscoveryUnavailable；Task failed 由生产 Worker 发布，没有写入测试
状态、伪造资格或新增产品入口。`native-probe.cjs`、`completed-probe.cjs` 记录真实页面操作；
`native-probe.log`、`completed-probe.log`、`failed-page.txt` 及 desktop／390px截图保留复现。

| 验证 | 实际结果 |
|---|---|
| 治理、完整范围 diff check；全部已跟踪 Python Ruff format/check；compileall、pip check、两份 example config、禁止依赖检查 | PASS。全目录 Ruff 原命令被预存未跟踪 `.explore_adapter_block.py` 语法错误阻断；该文件保留，未计为产品问题。 |
| 本 Task 直接失败／混合／健康／确认竞争用例 | 6 tests OK，0 skips，0.706s；`failed-preparation-tests.log`。混合批次额外走现有重新分析入口，只更新和整理健康 Two，One 失败历史保留；`mixed-reanalysis.log`。 |
| Web 全部单测及 typecheck/lint/format/build | 98 files／1473 tests 全通过；单测127.74s；其余检查通过。 |
| Python 全回归 | 2677 tests，2 failures、7 skips，309.322s；`python-full.log`。一个是上述 golden fixture；另一个是本 Task 的测试分工标题格式不满足现有文档测试，本轮 B 已恢复标准标题并单独复验。无全量全绿声明。 |
| 默认 E2E | 262 passed／6 failed，3.9m。五个准备页 fixture 失败如上；另一个 trace ENOENT 来自两套并行 Playwright 共用产物目录，B 用独立输出目录重跑该认证用例后1 passed（777ms），不是产品故障。 |
| 真实 Python source-history E2E | 1 passed（3.5s），真实新整理实际生效；`source-history-e2e.log`。 |
| 真实 Python inventory＋task-flow E2E | 40 passed／8 failed（2.6m）。健康摘要从任务中心恢复、重新认证、同一 Task 确认及实际完成均已走通；其最后仍查找“继续整理”的旧期望失败。其余7个失败涉及旧筛选／步骤证据／Worker效果，未做 Base 对照，不宣称是既有问题或本次产品回归；保留 `python-browser.log`，后续由 B 继续核对。 |
| Base 精确对照 | Base 两个对应 Python合同／文档测试均通过（0.067s）；原目录整理 E2E 1 passed（1.2s）。使用独立 git archive 源码和 Base build，不改当前工作区。 |
| 原生失败历史、正常完成只读入口 | 重现 B3-03；桌面／390px均可见矛盾状态；刷新、重新认证、同版本数据库 reopen 后一致。正常完成只读页重新分析返回409。 |

按全部 Task 结果重评：AC-1／3／4 的失败释放、混合兄弟及事务竞争后端证据通过；AC-2
的只读历史与动作一致性未满足。AC-5已有真实历史提醒／新整理证据；AC-6完整回归尚不通过。
混合批次完整原生验收及 wheel／安装后消费者／相关Docker边界尚未完成；产品阻塞已确认，
本轮不继续这些门禁，不记为 PASS，也不交回 Developer 代跑。Slice52 保持既有 PASS／CLOSED。

本轮并行测试的墙钟占用约6分钟，低于本轮审查、真实链路定位、Base对照和记录总时间的
50%；未以延长等待凑比例。B 本轮只维护本 Task 和本地证据，预存工作区文件保持，未推送。
