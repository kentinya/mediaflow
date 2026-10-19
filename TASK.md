# Task45.5 — FileIndex 完全退出与 CLI/Web 库级实时列表统一

Authority：已提交 [SLICE.md](SLICE.md) 与 [Development Workflow](docs/development-workflow.md)。
角色经验：[B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.5
Parent Slice: 45
Status: FIX REQUIRED
Task Base: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Required Outcome: RO-7; S-8 / S-9; AC-7; affected RO-1–6 safety and journeys
Next Action: DEVELOPER FIXES FULLY RECORDED BUT UNDECIDED RECOVERY IN SAME TASK; B RETAINS ALL FINAL GATES
```

## Goal

操作者通过 `mediaflow files list`、资源库文件页和媒体库页读取同一精确 Active 库/目录的
真实 Storage 条目；打开、刷新、翻页只读，不保存文件目录或产生工作。明确发起整理后，
无 FileIndex 装配仍完成真实稳定观察→分析→同页摘要→就绪子集确认→Worker 执行→结果/
安全恢复。失败说明阶段、持久状态、已知效果及修复/重新读取/安全重新检查的下一步。

完整旅程和退出边界见 [FileIndex 退役设计](docs/file-index-retirement-spec.md) 第1–7节、
V2-FILES-005/006、REQ-SCAN-002/003/005/006、REQ-ORG-012、REQ-WEB-003、REQ-SAFE-009
的当前修订；整理/恢复遵循 [任务中心规范](docs/task-center-page-spec.md) 第3–5节。

Task Base 规划时的实际缺口：`final_cli.py` 的 files list/show/stats 仍装配 FileCatalog/SQLiteFileIndex；
StorageScanner 仍 upsert/reconcile 全局目录；CLI/API/Worker、部分恢复和 Automation 基础
消费者仍注入或要求索引；SQLite Result 自动同步、整理结果 DTO/Web 同步修复动作仍存在。
`RuntimeFilesBrowserService` 已有两种库的实时列表和隔离游标，应复用。

## Implementation Scope

一个完整 RO-7 行为单元，覆盖必要 domain/application/infrastructure/CLI/API/V1/V2、
schema、Worker 和安装/测试消费者，不按模块拆 Task。按以下顺序实施：

1. 沿真实调用列出索引产品/消费者及去向，区分全局目录与显式工作的来源、观察、pin、
   计划、锁、Result。检查 `file_catalog`、`file_index_lifecycle`、`scanner`、
   `manual_organize*`、`manual_source_validation`、各 continuation、
   `automation_task_definition_preview`、`automation_definition_execution`、
   `final_cli.py` / `cli.py`、`service_api.py` / `operator_ui.py` 和 SQLite 装配。
   交接简述实际移除/承接位置，不另建索引抽象、内存替身或 no-op 仓储。
2. files list 直接复用现有 `RuntimeFilesBrowserService` 库级行为：必须互斥选择
   `--resource-library ID` 或 `--media-library ID`，支持 `--path`、`--limit`、
   `--cursor`。CLI/Web 读取同一 Managed Active；不从竞争 JSON 快照列举、不复制遍历器、
   不经 shell/API 绕行。分离只读配置解析与运行库初始化：列表不创建/升级数据库，不装配
   Task/索引写仓储；缺 Active、配置损坏及缺库给出修复路径。保留精确名称、类型、
   大小/mtime、有界分页/截断和未知总量。移除旧索引筛选/时间/FileID 游标，非法输入不改义。
3. 移除 FileIndex list/detail/stats/reprocess 产品、V1/V2/API/CLI 链接、DTO/状态/
   Dashboard 索引指标、Result/普通维护同步与修复动作。旧索引入口删除或按设计薄拒绝并
   指向库级浏览/任务中心；无兼容查询引擎。移除 RuntimeFilesBrowser 无用索引参数。
   两库页现有普通维护、返回、错误/空态与任务结果保持，不制造整库统计。
4. 所有支持的处理消费者改用工作内精确来源与 live Storage 校验，复用现有有界 discovery/
   持久观察、纯过滤及 ManualSourceValidator 等能力。来源/计划受原固定配置约束，
   来源替换/缺失在变更前拒绝。无全局 New/Modified/Unchanged/Missing 对账或长期
   occurrence/disposition 目录；同路径新文件不被旧结果永久压住。stable-size 必须跨真实
   区间，不能用旧mtime/首次stat替代；大小/mtime/有效指纹变化重置区间。重开保留合法观察，
   丢证据需重新观察。保留 scope/条目/时间边界、协作控制、claim/lease/fence、原子准入、
   重复/丢响应核对、精确就绪子集和主文件/附件独立结果。
5. 删除 domain 索引模型/协议、FileCatalog/lifecycle、SQLite/内存索引实现、专用 schema/
   初始化/后台写入和死代码。`file_lifecycle.py` / `file_index_schema.py` 中仍被 Task/计划
   使用的纯来源证据或 Task 字段迁到真实所属职责，不盲删安全证据、不保留更名全局目录。
   fresh 无索引表；受支持工作重开/重启/失败原子性保持。按未上线边界验收，不建设旧索引
   生产迁移/双写；不自动 DROP/清空/重建任何现存运行库或媒体。不支持的开发旧 schema
   明确拒绝并指向隔离新数据目录。
6. 更新索引播种 tests/fixture、wheel/Docker/Worker harness，从临时 live Storage 与显式
   工作证据出发，保留等义安全断言，不删断言/扩大重试超时/隐藏skip。必要说明仅陈述候选
   事实，不将未验收退役标为已交付 CURRENT；全 Slice 文档闭合由 A 处理。
   受影响验证后提交连贯实现 checkpoint，交 B 固定候选验收。

RO-8 独立 Preview 完整退出不在本 Task；清理其必要索引耦合，不新建索引兼容/修复服务，
不要求保留废弃 FileID 入口。共享分析/固定计划/Rules/配置/授权检查必须无索引可运行。
不得借此实施整个 Preview 生命周期重构，或冻结 Slice43 页面/Run once/指标/设置重设计。
若必须改变父 Contract，交 B→A，不自行放宽范围或安全语义。

## Acceptance Criteria

- [ ] CLI 两种库选择与对应 Web/API 同源；混合媒体/非媒体/目录、Unicode、长名/边界
  空白逐项一致，不套用整理过滤。游标绑定库种类/ID/root/配置/目录；同名跨种类库不混淆，
  非法/过期/跨目录游标与越界可恢复拒绝，不承诺无快照跨页静态一致性。
- [ ] 无/冲突库选择、旧参数、无Active、停用/不存在库、Storage故障/权限失败可解释，
  不显示为空、不回退JSON/索引；CLI只读不创建数据库或升级schema。
- [ ] 列举/导航/刷新/翻页前后无目录/观察/Task/Job/Result/许可写入，Provider/Hash/
  媒体mutation为零；允许配置读取及普通访问日志。fresh无索引专用表/索引。
- [ ] 生产源码/装配/包无可运行FileIndex产品、仓储、内存/no-op替身、全局目录/
  occurrence/disposition、同步/reprocess/修复与死代码；其他支持工作不因缺索引拒绝。
  按职责审查残余引用，不要求历史文本/否定断言字符串零匹配。
- [ ] 无预扫描/索引完成真实稳定观察、变化重置、同页摘要、精确子集确认、Worker执行、
  结果及安全恢复/重开；直接选择与目录遍历同约束，实质边界不完整不执行first-N。
  分析零mutation/零执行权；结果保存/显示失败不重放效果。
- [ ] 源变化、合法旧pin/缺pin、并发/重复准入/丢响应、stale owner和混合成功/失败/
  未知效果保持拒绝及恢复安全；成功兄弟和已完成主文件不因附件异常重放，附件原因/
  目标/按策略指引可见，未知效果只核查。C用NamingA/ClassificationA仍为C。
- [ ] 普通维护/传输、任务历史/详情/控制/导出、共享分析/检查及仍支持的Automation
  基础授权/执行消费者不装配索引仍可用；不强制恢复已合并43专属UI。
- [ ] 受影响验证与B指定T4/真实入口/产物门禁有实际结果；未提供门禁pending，
  不由旧PASS或Task45.4历史例外推定通过。

## Required Tests

分工/复用遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。
使用临时根/fake/local-server Provider，不读用户库、私有配置或真实媒体。

### Developer — affected tests

仓库根执行；`PYTHONPATH=tests` 仅提供测试模块导入路径：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser
PYTHONPATH=tests .venv/bin/python -m unittest test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage
git diff --check
```

新增 `tests/test_file_index_retirement.py` 覆盖CLI/API live parity、旧索引输入退出、只读
无建库/升级、副作用计数及fresh/重开无索引事实。scanner/fixture随职责调整，不要求
保留索引专属测试，但保留其过滤、稳定性与安全等义覆盖。

若修改下列消费者，追加对应直接受影响组；已知失败修复必须重跑失败用例：

```bash
PYTHONPATH=tests .venv/bin/python -m unittest test_task_persistence test_sqlite_backup test_sqlite_restore
PYTHONPATH=tests .venv/bin/python -m unittest test_direct_file_operations test_manual_operations_contract test_operations_task_center
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize
PYTHONPATH=tests .venv/bin/python -m unittest test_metadata_correction_continuation test_recovery_batch
```

对实际新增/修改Python文件运行 `.venv/bin/ruff check <files>`、
`.venv/bin/ruff format --check <files>`，报告实际路径/结果，不跑全仓替代受影响检查。
Web在 `web/`：

```bash
npm run typecheck
npm run test -- run src/entities/operations/organize.test.ts src/features/operations/OrganizeRouter.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts
```

新增 `live-files.python.spec.ts`，复用/调整现有real-Python harness，在production build上
验证两库列表/分页/错误恢复/只读；同一隔离fixture调用真实CLI对照条目，不播种索引、
不用mock API。其他前端测试有修改则追加精确路径，changed files运行 `npx eslint <files>` /
`npx prettier --check <files>`。Developer不跑全Python/Web/E2E或Docker/release matrix，
不准备B的全量证据包；受影响检查后即可交接。

### B — acceptance and full regression

在READY FOR B REVIEW明确SHA上检查 **Task Base..Head全部diff**、消费者/死代码与文档，
核对用户脏文件及frozen43/RO-8边界；先独立复现已知P0/P1，可提前FIX REQUIRED，修正留45.5。

B执行 [共享全量门禁](docs/development-workflow.md#shared-full-regression-commands) 的全部
Python/Web/示例/依赖/禁止依赖/编译/完整E2E/wheel/安装消费者/安全覆盖，另执行：

```bash
# cwd web/；先完成production build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
```

B独立关键复现，不能以源码检索或Developer测试标签替代：

1. 隔离Managed Active、同ID/Storage/root两种库、混合非媒体/目录/Unicode/长名/空白名与
   多页条目，真实CLI/Web/API比对；跨种类/目录/配置游标拒绝，无Active/403/Storage故障→
   修复→重读。前后核对媒体、工作/观察/许可记录、Provider/Hash/mutation计数；库不存在/
   数据库缺失/旧schema只读不建库不升级。检查生产源码/包/fresh schema无索引/替身。
2. 新来源零预扫描：直接文件和文件夹分别真实stable-size等待/替换重置→同页摘要，
   未确认零效果，子集确认后实际Worker执行。独立核对来源变化、重复/丢响应、旧pin/
   新Active、混合失败/附件/未知效果及重启/重开，不能重放成功或未知效果。
3. wheel隔离安装、离开源码运行真实CLI/API/Worker和无索引整理/恢复，核对import路径、
   wheel hash、served assets与fresh/重开。B编写/保存必要独立脚本，不把证据补齐交回Developer。

生产Docker使用固定候选新建镜像；`<candidate-sha>`替换为实际完整SHA，不误用同名旧镜像。
B执行现有harness，实施中的必要索引fixture改动应纳入本Task：

```bash
docker build -t mediaflow:task45-5-<candidate-sha> .
.venv/bin/python scripts/docker_scan_retirement_browser_proof.py --image mediaflow:task45-5-<candidate-sha> --artifacts .git/validation-evidence/<candidate-sha>/task45.5/scan-stability
.venv/bin/python scripts/docker_task_center_recovery_browser_proof.py --image mediaflow:task45-5-<candidate-sha>
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image mediaflow:task45-5-<candidate-sha>
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45-5-<candidate-sha>
```

B另在该镜像真实CLI/API/常驻Worker复现第1–2项及普通维护、仍支持的Automation基础消费者。
fresh无索引、同版本重开/重启、受影响支持版本迁移和失败原子性必需，不扩成旧索引生产迁移。
实际检查1536×1024及380×720截图、键盘、深链/返回/重连。日志/截图/脚本/产物digest保存于
`.git/validation-evidence/<candidate-sha>/task45.5/`，报告cwd/命令/结果/数量/skip/不可用。
必需环境不可用由B保留pending，不判完整T4 PASS，不冒充产品缺陷返工。

执行输入改变则刷新分配的验收；仅报告变更证明源码/测试/harness/依赖/配置/产物不变，
跑受影响文档检查。匹配结果可复用到Slice-final，缺失覆盖由B补齐，不机械重跑Final。

## Non-goals

- RO-8独立Preview完整退出尚未交付，本Task不因此宣称Slice ready。
- 旧FileIndex迁移/双写/FileID兼容/同步恢复，无用户数据清空/删除。
- Slice43工作区重设计、MediaLibrary Organize、新Provider/引擎、附件-only自动恢复、
  未知效果重放、无限遍历或跨任务批量mutation。
- 改A-owned Slice/Roadmap/Progress边界、重开45.4或补记其历史全量PASS、自行关闭Slice。

## Developer Completion Report

READY FOR B REVIEW at implementation HEAD `6f79676a12147a671a1b466af885fff1e7ce1790`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previously reviewed candidate
`86f8af953cf9c2501e107831a2da754bd68c0640`; this handoff differs only in TASK.md). Same Task,
Base / Goal / High / T4 unchanged. B's review finding was **FIX REQUIRED — a fully recorded budget
still hides/refuses undecided recovery**; this fix round commits only that correction and its
tests.

### 先复现（修复前）

Running B's own script (unchanged candidate, unchanged assertions) reproduced the P1 exactly:
`item_limit=2`, `Kept` successful, `Left` recorded-but-`pending`, so `remaining_scope()` returned
`Left` with `remaining_limit == 0`. The real API answered `POST
/api/v1/tasks/{id}/remaining-scope-previews` with 409 `no_remaining_scope` ("every unit ... already
recorded"), and `GET /api/v1/operations/runs/{id}` exposed a `resume` action with **no** `preview`
recovery entry — the required journey was unreachable. Media unchanged, target files 0.

Root cause was exactly the three-layer one B described: `continuation_obstacle()` decided
"nothing remaining" from the queued continuation's *budget*, the API passed that verdict straight
into `admit_recovery_preparation()`, which refused before ever reaching the recovery scope, and the
native projection published the recovery entry only for the `authority_required` code. Before
touching application code, the new `test_a_fully_recorded_budget_still_recovers_its_undecided_item`
was executed against the unmodified modules (stash of the five application files) and failed at
`resume["preview"]` — the failing case is real, not retro-fitted.

### 修正：区分"没有新的发现名额"与"没有任何可安全恢复项"

1. **共享边界显式建模两种操作** (`domain/scope_continuation.py`, `application/scope_continuation.py`):
   新增 `ScopeContinuationOperation{QUEUED_CONTINUATION, RECOVERY_PREPARATION}`，`continuation_obstacle()`
   和 `ScopeContinuationService.obstacle()/recovery_obstacle()` 按操作给出结论。两者共享同一条链、
   paused 状态、不可变 pin、continuation 所有权与 live authority 校验；只有两处按操作分叉：
   - **预算**：queued continuation 把*未记录*发现名额交给 Worker 且跳过已记录来源，因此原准入
     全部记录后确实没有可排队工作，仍给出 `no_remaining_scope`；recovery preparation 重新观察
     已记录但**未决**的项，只有"既无未决项又无剩余名额"才拒绝。
   - **授权**：queued continuation 若会修改媒体仍需 live 可复用授权；零变更 recovery
     preparation 不要求也不授予执行权（执行仍需一次全新显式确认）。
   其他拒绝（命令类型、paused、pin、chain owner/continuation 已存在、RBAC、claim/fence）对
   两种操作完全一致，未被绕过。普通 Continue 的预算限制保留。

2. **精确恢复范围** (`RecoveryScopePlan`): `recovery_scope()` 保持原三元组返回，新增
   `recovery_scope_plan()` 提供同一计算的 `unrecorded_budget`。原准入被完全记录时
   (`unrecorded_budget == 0`)，preparation 观察**恰好那些未决来源**而不是重走目录，因此满额之后
   才出现的新文件不能借用未决名额、静默替换或扩大范围；新来源准入身份由 scope signature 逐项
   绑定，重复请求仍收敛同一 durable preparation。仍有未记录名额时继续走原有目录遍历与预算。

3. **原生投影按恢复资格发布** (`application/operations_lifecycle.py`):
   `TaskExecutionContext.recovery_available` 来自共享边界的 recovery 结论，`lifecycle.resume`
   的 `preview` 入口据此发布（仍仅对有 `MANAGE_MANUAL_ORGANIZE` 的主体）。真正全已决的运行
   不发布入口。API `_remaining_scope_obstacle()` 改为调用 `recovery_obstacle()`，真实 POST 与
   投影不再可能不一致。

4. **一致性**: fake server 与 real-Python harness 同步表达同一规则（recovery 资格而非单一
   refusal code），新增 harness fixture `seed-full-budget-recovery` 与专用 Provider 候选。

### 实际受影响命令/结果（本轮，仓库根，`PYTHONPATH=tests`）

- `test_scope_continuation` → **65 OK**（含 4 个新增用例）
- `test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser` → **40 OK**
- `test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize` → **257 OK**
- `test_recovery_continuation test_task_center_recovery_lineage test_scope_continuation test_media_discovery_provider_manifest test_organize_preparation` → **152 OK**
- `test_operations_run_inventory test_operations_run_detail test_operations_task_center` → **100 OK**
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_direct_file_operations test_manual_operations_contract` → **98 OK**
- `test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_recovery_batch` → **140 OK**

新增/修改用例（真实 API/SQLite/LocalStorage/fake Provider/持久 Worker）：

- `test_a_fully_recorded_budget_still_recovers_its_undecided_item`：`item_limit=2`、两名额全部
  记录、`Left` Pending。断言 `remaining_scope` 的 `new_budget == 0`；原生 task 投影与
  `/operations/runs/{id}` 都不提供 Continue 但**提供** `preview` 入口；真实 POST → 202；持久
  Worker 摘要恰为 `Left`，`Kept` 不重放，媒体字节不变、目标 0。
- `test_a_single_recorded_pending_item_is_recoverable_at_a_full_budget`：`item_limit=1` 且唯一
  Pending 的最小满额边界。
- `test_a_fully_decided_chain_at_a_full_budget_is_still_refused`：成功+Pending 之外的真正全已决
  仍 409 `no_remaining_scope`，且不发布 `preview`、不创建任何 Preview。
- `test_a_full_budget_never_lets_a_new_file_borrow_the_pending_unit`：满额后新增
  `New.2020.mkv`，摘要仍恰为 `Left`，三个源文件都在、目标 0。
- `test_a_fully_recorded_budget_keeps_the_queued_continue_refusal`：同一状态 `POST /resume`
  仍 409 `no_remaining_scope`、零 Job、零 continuation 记录；只有零变更复核可用。
- 修正原 `test_recovery_keeps_an_undecided_recorded_source_in_the_reviewed_scope` 的说明：它
  实际是 budget=4 的对照（两名额未用），现明确写出并断言 `unrecorded_budget == 2`。

Web（cwd `web/`）：`npm run test -- run src/entities/operations/lifecycle.test.ts
src/features/operations/RunLifecycleControls.test.tsx src/features/operations/RunDetailTabs.test.tsx
src/features/operations/OperationsInventory.test.tsx` → **65 passed**（新增"非 authority refusal
仍保留 recovery 入口"与"满额仍有未决项时渲染摘要按钮"两个断言）；`npm run typecheck` 通过；
`npm run build` 成功（production assets 供 E2E 使用）；
`npm run test:e2e -- --config=playwright.python.config.ts
tests/e2e/operations-inventory.python.spec.ts -g "fully recorded budget|mutation-authorized paused
run|missing configuration pin"` → **3 passed**，其中新增的 full-budget 浏览器旅程在 production
build + 真实 Python API/Worker 上完成：Continue 不可用但摘要按钮可见 → 摘要恰含
`FullBudgetLeft.2005.mkv`、不含 `Kept`/新文件 → `确认继续整理剩余 1 项` → 无 mediaflow CLI 文案 →
目标 0 → 重复 POST 202 收敛。

静态/治理：`python3 scripts/check_governance.py` PASS；`git diff --check` 干净；
`.venv/bin/python -m compileall -q mediaflow tests scripts` OK；`ruff check` 与
`ruff format --check` 覆盖全部 7 个改动 Python 文件 → passed / formatted；
`npx prettier --check`、`npx eslint` 覆盖 3 个改动 Web 文件。

证据：`.git/validation-evidence/task45.5-developer-fix3/verify_full_budget_scope.py` 与
`full-budget-scope.json`（exit 0；四案：budget4/budget2 均 202 且摘要恰为 Left；两种准入顺序的
三份独立 admission 与真实 Worker 清单），以及 `README.md` 记录候选、命令与实际结果。

### 已知风险/边界

- 恢复身份现在包含**观察形态**：原准入满额时 scope signature 是未决文件集合，仍有名额时是目录。
  未决集合或排除集实质变化会产生新准入（既有 B 已确认的精确语义），不变则收敛同一记录。
- 满额恢复只观察未决来源，因此对"原目录里后来出现的文件"是显式不扩大；这符合 B 第 4 条要求，
  但也意味着新文件需要通过新的有界运行处理。
- runtime schema 仍为 49（无新列/表）；B 仍需在真实 wheel/Docker 复核 fresh/reopen 与支持版本
  迁移。
- `tests/e2e/direct-files.python.spec.ts` 既有 flaky 仍待 B 独立确认（非本 Task 引入）。
- wheel/隔离安装、生产 Docker、真实长区间 Worker、1536×1024/380×720 全套截图与 failover 仍是
  B 的 T4 门禁，本轮未运行也未声称通过。
- 本轮测试执行合计约 2 分钟，占本开发轮次总时长（约 48 分钟）约 3%，低于 30% 上限。

预存修改保留且不纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
私有 ignored 配置不读取、不暂存。RO-8 未交付，本 Task 不宣称 Slice ready，也不自判 PASS。

## B Review Result

```text
Reviewed candidate: 86f8af953cf9c2501e107831a2da754bd68c0640
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..86f8af953cf9c2501e107831a2da754bd68c0640
Handoff: 800092e45bae65cc3e6802b6cab5d7c743dedfed (TASK.md only; execution inputs identical)
Decision: FIX REQUIRED — a fully recorded budget still hides/refuses undecided recovery
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

main、上述候选和原Task Base固定，治理PASS，Git/workspace可写；预存图片删除、未跟踪
截图/日志/ZIP/浏览器结果及私有配置保留、不暂存。必读治理/角色/Contract/Task/当前指针及
适用需求、完整列表/整理/恢复旅程和CURRENT/TARGET已核对。继续原Base..Head审查，
依workflow §6先独立复现关键修正；明确P1允许提前拒绝。本轮未宣称全部diff审完或T4通过，
未改A-owned边界、45.4历史接受或冻结43。

### 已独立确认的修正

真实Managed Active/API/SQLite/LocalStorage/fake Provider与持久Worker，临时媒体：

- Kept成功、Left可信Pending，原item_limit=4：202准入，摘要恰为Left，Kept不重放。
- 同actor/库/pin/Sub目录，分别ordinary→recovery和recovery→ordinary：同A重复仍同记录；
  A/B两个Task和普通Files分别取得三份不同discovery，origin依次为A/B/null；实际Worker
  摘要逐项为Left、Kept+Left、Kept+Left。普通准备不继承恢复排除项。
- 稳定期0与真实1秒分别通过202→Worker→摘要。1秒首次waiting_stability、Provider0，
  立即不能重领，真实等待超过1秒后完成，摘要仅Left。媒体内容保持，目标文件0。

这些是上述分支的独立结果，不代替并发/重开、完整原生或发布门禁。

### P1：所有名额均已记录，但仍有Pending时，没有恢复入口且直接请求409

真实organize Task，原item_limit=2、durably paused、原配置pin合法、一次性执行权已消费：
Kept已成功，Left有可信来源证据但Pending，无Result/Storage效果。

- `remaining_scope()`返回Left，未发现预算0；新`recovery_scope()`正确返回Left、排除Kept、
  恢复bound=1。
- 实际POST `/api/v1/tasks/{id}/remaining-scope-previews`仍409 `no_remaining_scope`：
  "every unit ... already recorded, so no remaining scope exists to continue"。
- 实际GET `/api/v1/operations/runs/{id}`为200，但lifecycle.resume没有preview恢复动作；
  普通用户在原生界面也无法为Left生成摘要。对照limit=4时该动作存在且POST202。
- 媒体未变更、target0；这是必需恢复旅程不通，不能据零mutation判通过。

**根因跨三层。** `scope_continuation.continuation_obstacle()`仍以remaining_limit==0
认定没有任何剩余；API `_remaining_scope_obstacle()`将这个普通Continue结论原样传入；
`MediaDiscoveryService.admit_recovery_preparation()`先执行obstacle并拒绝，根本到不了本次
新加的`recovery_scope()`。`operations_lifecycle`也只在authority_required时投影恢复按钮。
因此单改新预算函数或后置if条件不够。本次Developer新增用例实际仍为limit=4，有两个未用
名额；其docstring声称“whole scope budget already recorded”，没有测试到这个边界。
该旧Continue guard早于本Task存在；本结论是当前RO-7恢复义务仍未完成，不冒称它由本轮新增。

### Developer 必需修正与顺序

1. **先增加真实满额反例，确认修改前失败。** 保留organize/原pin/真实Pending证据；
   limit=2、Kept成功+Left Pending，两名额全部记录。同时断言原生overview提供合法恢复
   action、直接POST202、持久Worker摘要仅Left；不要只调用`recovery_scope()`验证数值。
   修正现有测试“满额”的错误说明，不能继续用limit=4的成功对照代替。
2. **把恢复资格贯通到共享应用边界和原生投影。** 明确区分“没有新的发现名额”与“没有任何
   可安全恢复项”；零变更重新准备可以保留原已占用名额的未决项。复用现有scope/chain/
   checkpoint/result计算，为恢复准备形成同一资格结论，真实API和lifecycle动作均消费它。
   核对`continuation_obstacle`、API `_remaining_scope_obstacle`、discovery前置准入和
   `operations_lifecycle`。不要仅前端显示按钮，也不要仅跳过POST的no_remaining_scope。
3. **保留其他拒绝和权限。** 不直接删掉普通Continue的预算限制，不把原execute标志当许可；
   不因满额绕过paused、支持类型、原pin、Task/chain owner、已有continuation、RBAC、
   claim/fence等校验。真正全已决仍拒绝。若共用obstacle支持不同操作，显式建模其语义，
   不能全局忽略no_remaining_scope或authority_required之外所有拒绝。仍只通过既有持久
   discovery/Worker观察、分析、精确摘要和新确认，不创建第二引擎或直接mutation。
4. **覆盖边界的最终行为。** 至少limit=1且唯一Pending、limit=2成功+Pending、尚有未发现
   预算的成功对照、全部成功/忽略/未知效果无合法剩余的拒绝；满额目录后来出现新文件不能
   借用Pending名额静默替换/扩大范围。原未决项重验来源和稳定期，成功/未知不重放。
   普通Continue、API准备和原生动作的区别要有对应断言；保留原pin缺失/权限/非paused/
   后续Task已拥有范围等既有拒绝覆盖。并发及重开去重测试随实际共享边界改动追加。
5. 提交同一Task45.5的连贯修正checkpoint与简短实际报告，Base/Goal/High/T4不变。
   不展开RO-8或冻结43，不改Slice/Roadmap/Progress。当前文档只保留最新报告，详细历史留Git。

### Developer 本次受影响验证

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_operations_run_inventory test_operations_run_detail test_operations_task_center test_task_center_recovery_lineage test_recovery_continuation
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
```

以上模块名已用`rg --files tests`核对；新增满额API/Worker/action集成断言。若改Web，追加changed交互单测、
`npm run typecheck`、production build及真实Python task-center/inventory受影响E2E。
Developer不跑全Python/Web/E2E或Docker发布矩阵。

B在修正候选上独立复现以上边界，继续原Base..Head全部审查并完成Required Tests原分配的
完整T4、原生/视觉、wheel/安装CLI/API/Worker、固定候选生产Docker，以及fresh/reopen/
支持版本升级/失败原子性。不将全量或证据补齐交回Developer。只有匹配执行输入/产物的
既有结果可复用；不机械重跑Final，不把未跑/中断门禁算PASS。

### 本轮实际证据、耗时与后续

本机稳定ignored存储（非远程CI）：
`.git/validation-evidence/86f8af953cf9c2501e107831a2da754bd68c0640/task45.5/b-review/`。

- `verify_scope_and_identity.py` / `scope-and-identity.json`：满额P1及limit4成功对照、两种
  顺序的三份独立准入与真实Worker清单；exit0表示包括P1在内的事实均被断言，不是产品PASS。
- `verify_remaining_stability.py` / `remaining-stability.json`：真实非零观察独立通过。
- 治理、改动6个Python文件的ruff check/format检查及git diff --check均通过。
- README记录cwd/命令/候选/实际结果与探索脚本修正；timing记录本轮保守累计验证耗时，
  含失败探索与重复运行上限30秒，占本轮复核时间不足8%，低于50%。
- 发现明确P1，未启动本候选完整Python/Web/E2E/wheel/Docker/截图门禁；全部仍由B承担，
  不挪用其他候选或未完成结果。本轮仅checkpoint TASK.md。

RO-7仍未通过、RO-8未实现，不新造Task，不提交Closure Packet，不关闭Slice。
