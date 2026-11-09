# NO ACTIVE IMPLEMENTATION TASK

Task PATCH-20261109-2 — 查询类型统一与已确认元数据的整理摘要续接 — **B PASS**。

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: PASS
Task Base: 233f6a25769856087d10cb4483c0f1a621a76546
Reviewed Head: fbabe7f80614dd35faa096dcb55198d183784501
Accepted Implementation Head: 86d9b7618acd88d640563ffc90f5e9d98c7e8b74
Reviewer: B
Review Date: 2026-11-09
Difficulty: Medium
Test Level: T4
Task blockers: NONE
Authorized bug acceptance complete: YES
Next: NO ACTIVE IMPLEMENTATION TASK
```

已验收：策略只保留查询类型；新整理重新识别；当前任务使用本次明确保存的候选及类型继续生成摘要。
整理意图页已有候选选择、保存、刷新读回及重新分析闭环通过。电影／电视剧结果类型仍供查询、命名和分类使用；
无数据库结构变更或历史记录重写。

完整 Base..Head 独立审查、AC-1–6、T4实际结果、浏览器产物目录冲突补跑及证据限制见
[固定 B 验收报告](https://github.com/kentinya/mediaflow/blob/da47f9dd1af56cc281d6e42323ae4892caed5f83/TASK.md#b-final-review--pass)。
原规划与 Developer 报告见
[候选检查点](https://github.com/kentinya/mediaflow/blob/fbabe7f80614dd35faa096dcb55198d183784501/TASK.md)。
本地原始证据：`.git/validation-evidence/fbabe7f8/b-final-review/`；Git 推送不包含这些本机材料，也不代表部署。

此独立修正不重开 Slice52，不改 SLICE／Roadmap／Progress，也不授权后续实施。

---

## 规划草案 — PATCH-20261109-3：失败整理的文件释放与摘要入口一致性

**仅规划，未授权实施。** 当前仍为 NO ACTIVE IMPLEMENTATION TASK。用户本轮要求“规划一个
Task”，授权范围为前述失败文件被旧整理意图／摘要继续占用，以及失败任务仍显示“继续整理”的
体验修正。实施授权到达后，将本草案提升为根 Task；保留以下不可变 Task Base，不改已接受任务
或 Slice52 的关闭事实，不自动开始 Developer、其他角色或子代理工作。

```text
Task ID: PATCH-20261109-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: fe3bd99b1cf6046ac716052e5c8ee63851c80f15
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: PLANNING ONLY — IMPLEMENTATION NOT AUTHORIZED
```

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

**Developer — affected tests（实施后）**

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

**B — acceptance and full regression（候选提交后）**

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

待实施授权及 coherent checkpoint。报告实际 checkpoint、改动／根因、受影响命令与结果、
已知失败／未验证边界，状态 READY FOR B REVIEW；全量验收仍由 B 执行。

### B Review Result

未开始。规划不代表实施、验收 PASS 或自动开启后续角色。
