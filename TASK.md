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
Next Action: DEVELOPER FIXES CROSS-ATTEMPT COMPLETED-SOURCE REPLAY IN SAME TASK; B RETAINS FULL GATES
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

READY FOR B REVIEW. Same Task, Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974` / Goal / High /
T4 unchanged; implementation HEAD is this checkpoint's SHA (recorded in the B handoff). B's finding
was **FIX REQUIRED — a completed linked recovery can execute the same source again** (P1). This
round fixes only that root cause, its boundaries and its tests.

### 先复现（修复前）

B's own script, unchanged candidate and unchanged assertions, reproduced the P1 end to end:

- `recovery_scope_plan()` still returned the ancestor `Left` item as `Pending` even though the
  linked recovery execution had a real `SUCCESS`/`verified_complete` Result, so the exclusion set
  held only `Kept`;
- the surviving native overview still advertised the recovery summary action, and a second real
  `POST .../remaining-scope-previews` + explicit confirm + `ManualOrganizeExecutionWorker` produced
  a **second** destination file `Left (2005) (1).mkv`; both sources stayed intact (COPY).

Two independent defects were proven by that reproduction:

1. **Domain-coding mismatch.** The manual-Organize executor persists the organizer's own
   `ExecutionStatus` spelling (`SUCCESS`), while `remaining_scope()` compared only the lowercase
   `TaskItemStatus` values, so a really successful recovery Result was invisible as a decision.
2. **Identity mismatch.** `remaining_scope()` retired only the *same* `item_id`. A recovery attempt
   records its own TaskItem/Result under its own item ID, so an ancestor `pending` item of the same
   exact source stayed "undecided" forever, and `already_recorded - undecided` then removed that
   source from the replay exclusion set.

### 修正：按显式来源把已完成效果归并回它承接的原工作来源

1. **共享边界按操作/来源判定，不再只看 item 身份** (`application/scope_continuation.py`):
   `remaining_scope()` 沿既有 `continuation_chain()`（queued continuation 链接 + 精确 Preview
   恢复链接）收集整条链的 items/Results，然后用 *显式来源* 决定终态：
   - 新增 `_result_is_decided()`：状态比较大小写不敏感（同时覆盖 `success`/`SUCCESS`），
     `attempted_unverified` 与执行域 `unknown` 都视为已决（只核查），且 `primary_completed=True`
     的裁决即使状态是 `PARTIAL` 也算主文件已完成（附件警告不重放主项）。
   - 新增 `_decided_source_observations()`：只要 Result 已决，或 TaskItem 自己落在非未决状态，
     它就成为该来源的一条已决观察（`item_id` 仍按身份消除）。
   - 新增 `_SourceObservation.is_the_same_file_as()`：必须 Storage + 精确相对路径一致；当两侧都
     有指纹时指纹也必须相等。因此**同路径被替换的新文件**保留自己的未决状态，不同 Storage/
     路径的成功不会误伤本来源；无指纹的旧行按同一来源保守处理（拒绝重复 mutation 优于重放）。
   结果：完成/忽略/未知效果会退休链上**所有**指向同一来源的 item，`replay_excluded` 因此包含
   该来源，满额链给出 `unrecorded_budget == 0`、无未决项。
2. **预算按去重来源计费**: `remaining_limit` 用 `{(storage_id, path)}` 的去重数量，而不是
   item 行数；`recovery_scope_plan()` 的 `undecided_items` 也按来源去重（同一来源只提出一次）。
   多一条恢复尝试既不重复扣减也不放宽原准入。
3. **动作/摘要/准入消费同一结论**: `_remaining_scope_obstacle()` 与
   `admit_recovery_preparation()` 都走同一个 `recovery_scope_plan()`，因此原生 lifecycle
   `preview` 入口、真实 `POST` 与 Worker 观察不可能互相不一致：全已决的满额链不发布入口、
   直接请求 409 `no_remaining_scope`、零 preparation/零 Job/零 Provider。
4. **不受影响的行为保持**: 可证明零效果（`effect_certainty == "none"`）的失败仍是未决工作，
   仍可再次摘要与确认，且同一来源只出现一次；"未知效果"只核查、绝不转为可重试。

### 新增/修改的真实旅程测试（`tests/test_scope_continuation.py`）

固定 COPY+Rename（真实 managed Active）与真实 API/SQLite/LocalStorage/fake Provider/持久
Worker，新增 8 个用例：

- `test_a_completed_recovery_never_offers_its_source_again`：原 Pending→恢复摘要→显式 execute
  API→真实 Worker COPY 成功（断言真实 `SUCCESS`/`verified_complete` 与同指纹、不同 item ID）→
  新连接重开仍为全已决→原生 overview 不再提供 preview→再次 POST 409 且不新增 Preview→
  目标只有 1 份 `Left (2005).mkv`，两个来源字节不变。
- `test_a_completed_move_recovery_is_terminal_for_the_original_pending`：MOVE 成功同样终态
  （不因源文件消失而误判为可重放）。
- `test_an_attachment_warning_keeps_the_verified_primary_terminal`：`PARTIAL` +
  `primary_completed` + 附件原因不被重放。
- `test_an_ignored_attempt_never_resurrects_the_pending_ancestor`：只有 TaskItem 变更、无 Result
  的显式 ignore 也退休来源。
- `test_an_uncertain_effect_never_resurrects_the_pending_ancestor`：执行域 `unknown` 只核查。
- `test_a_zero_effect_failure_stays_safely_recoverable`：`none` 失败仍可恢复，且同一来源只提
  交一次、预算不放宽。
- `test_a_replaced_file_at_the_same_path_keeps_its_own_undecided_state`：同路径新指纹是新工作。
- `test_a_new_independent_run_is_never_suppressed_by_an_old_success`：不同 Task 链不受旧成功压制
  （无全局路径黑名单）。

修复前先跑新用例（application 文件未改）失败于 `plan.undecided_items != ()`，证明用例真实捕获
该 P1，而不是事后补写。

### Harness / 原生浏览器旅程

- `scripts/operations_inventory_harness.py`：新增真实 `copy-fixture` COPY+Rename 策略与
  `copy-fixture-library` 识别规则（仅 `FullBudget` 目录）；`seed_full_budget_recovery` 追加一次
  **可证明零效果** 的早期独立尝试（决定默认选择为 COPY，且仍不改变来源未决性）；
  `authority_execution_state` 对该 scope 报告本 fixture 自己的目标副本。
- `web/tests/e2e/operations-inventory.python.spec.ts` 的 full-budget 旅程现在真实完成
  `摘要→确认→Worker COPY`，随后 `restart` 重开、断言原生 overview 不再提供 preview、
  再次 POST 409 `no_remaining_scope`，且目标副本数量保持 1。

### 实际受影响命令/结果（仓库根，`PYTHONPATH=tests`）

- `test_scope_continuation` → **73 OK**（含 8 个新增用例）
- `test_recovery_continuation test_task_center_recovery_lineage test_media_discovery test_media_discovery_provider_manifest test_organize_preparation` → **199 OK**
- `test_manual_organize_execution test_recovery_batch test_recovery_continuation test_task_center_recovery_lineage` → **178 OK**
- `test_media_discovery test_media_discovery_provider_manifest test_organize_preparation test_v2_manual_organize test_manual_organize_preview test_manual_organize_intent` → **192 OK**
- `test_operations_run_inventory test_operations_run_detail test_operations_task_center` → **100 OK**
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_direct_file_operations test_manual_operations_contract` → **98 OK**
- `test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation` → **72 OK**
- `test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser test_scanner test_scan_retirement_stability` → **65 OK**
- Web (`cwd web/`): `npm run test -- run src/entities/operations/organize.test.ts src/features/operations/OrganizeRouter.test.tsx` → **35 passed**；
  `npx prettier --check` / `npx eslint` 覆盖改动 spec → 干净；`npx tsc --noEmit` 无该文件错误。
- 原生：`npx playwright test --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts -g "fully recorded budget still recovers"`
  → **1 passed**（真实 production build + 真实 Python API/Worker + restart）；
  同文件 `-g "mutation-authorized paused run|missing configuration pin"` → **2 passed**。
- 静态/治理：`python3 scripts/check_governance.py` PASS；`git diff --check` 干净；
  `python -m compileall -q mediaflow scripts tests` OK；
  `ruff check` 与 `ruff format --check` 覆盖 4 个改动 Python 文件 → passed / formatted。

证据（本机 ignored 存储，非远程 CI）：`.git/validation-evidence/task45.5-developer-fix4/`
包含本轮的复现/验证脚本与 JSON（修复前 `remaining_after_success` 含 `Left`、第二次 execute 202
且生成两份目标；修复后 `remaining_after_success` 为空、第二次 409、目标 1 份）。

### 已知风险/边界

- 已决来源的归并是**读时投影**：旧 Task/Result 行不被改写，链内历史保持可独立检查。归并只沿
  既有 `scope_continuations` 与 `manual_previews.recovery_source_task_id` 显式链接，不按标题、
  时间或路径跨任务猜测；无法证明承接关系时不归并（保守拒绝重复）。
- 无指纹的旧行在同一 Storage+路径上视为同一来源（拒绝重复 mutation 优先）。真实执行产生的
  Result 都带指纹，因此正常路径是精确指纹比较。
- 恢复仍要求同来源在链内只被提出一次；因此**满额**恢复后新出现的文件需通过新的有界运行处理
  （既有 B 已确认语义，未改变）。
- runtime schema 仍为 49（无新列/表）；wheel/隔离安装、生产 Docker、fresh/reopen 与支持版本
  迁移、完整 Python/Web/E2E/视觉矩阵仍是 B 的 T4 门禁，本轮未运行也未声称通过。
- 同文件既有 `a paused run continues only its remaining scope through the real Worker` 在本轮
  基线上**同样失败**（已用 `git stash` 在未修改 HEAD 上复现），非本 Task 引入，留给 B 判定。
- 本轮测试执行合计约 1.5 分钟，占本开发轮次总时长（约 55 分钟）约 2.7%，低于 30% 上限。

预存修改保留且不纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
私有 ignored 配置不读取、不暂存。RO-8 未交付，本 Task 不宣称 Slice ready，也不自判 PASS。

## B Review Result

```text
Reviewed candidate: 6f79676a12147a671a1b466af885fff1e7ce1790
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..6f79676a12147a671a1b466af885fff1e7ce1790
Handoff: acb8c0a38c9e53b4400331eeba6bfd99e969c9c5 (TASK.md only; execution inputs identical)
Decision: FIX REQUIRED — a completed linked recovery can execute the same source again
Previous fully recorded Pending blocker: independently fixed through real API/durable Worker
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

main固定上述候选；治理PASS、Git/workspace可写。预存图片删除、未跟踪截图/日志/ZIP/
浏览器结果和私有配置均保留、不暂存。已读AGENTS/workflow/B经验/已提交Contract/当前Task/
Roadmap/Progress，复核适用需求、完整列表/整理/恢复旅程和CURRENT/TARGET。不改A-owned
边界、45.4历史接受或冻结43。原Base..Head审查继续；本轮发现明确P1，依workflow §6提前
拒绝，未声称全部diff审完或完整T4通过。

### 已独立确认的修正

真实Managed Active/API/SQLite/LocalStorage/fake Provider/持久Worker，临时媒体：

- 原限额2、Kept成功+Left可信Pending：原生overview提供恢复摘要动作、普通Continue仍不可用；
  POST202，实际Worker摘要仅Left。原限额4的对照同样通过。
- 两种顺序ordinary→recovery、recovery→ordinary：同A重复收敛；A/B两个Task与普通Files各
  得到不同discovery/origin和准确清单，普通准备不继承恢复排除。
- 稳定期0/真实1秒通过202→Worker→摘要；1秒首次waiting_stability且Provider0，立即不可
  重领，真实等待超过1秒后完成。准备阶段媒体不变、目标0。

以上是具体分支的独立通过，不代替完整原生/并发/发布门禁。

### P1：后续恢复已成功，祖先Pending仍被当作剩余，再次确认可产生第二份COPY

独立fixture使用受支持的COPY+Rename固定策略，不修改生产配置、不删目标文件：

1. 原organize Task暂停，item_limit=2，Kept已成功；Left有可信指纹但仍Pending。
2. 从原Task真实POST恢复准备，持久Worker生成仅Left摘要；真实execute API显式确认，
   `ManualOrganizeExecutionWorker`完成COPY。后续Task有真实`SUCCESS/verified_complete`
   Result，目标已有一份Left，源文件仍在（COPY的正常行为）。
3. 同一显式恢复链中，`recovery_scope_plan()`仍返回祖先Left Pending，排除集只有Kept。
   新SQLite连接重开读取也一样；原生overview继续提供恢复摘要动作。
4. 再次POST恢复准备→202、新摘要仍包含同一Left；再次明确确认→202，真实Worker再次
   completed，Rename生成`Left (2005) (1).mkv`。两次Result和原Pending的指纹完全相同，
   不是同路径后来出现的新文件。目标最终两份，原Left/Kept内容保持。

这是“原任务只恢复剩余、成功项不重放”的实际破坏；没有声称自动重试或绕过确认。
用户按原界面提供的合法动作重复继续，就会复制已经完成的文件。

**定位。** `remaining_scope()`汇总了链，但按`result.item_id`消除未决项；恢复执行使用新的
Task/item ID，所以它的成功不能消除祖先item的Pending。`recovery_scope_plan()`随后用
`already_recorded - undecided`做路径排除，祖先Pending又把这个已成功来源从排除集中拿掉。
满额分支据此创建FILE scope，API/原生动作/执行一路接受；只保证item ID唯一不足以防止
同一显式恢复来源跨尝试重放。真实Result还存在执行域`SUCCESS`与Task域状态字符串差异，
修正终态判断时须核对真实编码，不只使用测试播种的小写状态。

### Developer 必需修正与顺序

1. **先复现完整成功后分支。** 在现有scope-continuation/API fixture新增原Task Pending→
   恢复摘要→execute API→真实Worker COPY成功→重开→再次请求原Task恢复的回归。
   固定COPY+Rename，断言同一source occurrence/fingerprint与显式祖先/后续关联；不能只
   验证第一次202、摘要或用手工播种原Task成功替代真实后续Result。
2. **按显式恢复关系计算有效剩余项。** 沿既有scope continuation、recovery Preview、
   execution/Task/Result关联，将后续尝试完成/忽略/未知效果归并到它实际承接的原工作来源。
   使用原pin、Storage/ResourceLibrary和可信occurrence/fingerprint/精确来源证据；不同item
   ID不能使同一来源重新未决。可复用现有持久关联与证据；若其缺少必要映射，在现有工作
   职责内补齐，不新建全局索引或第二恢复引擎。保留独立历史，不为过门禁伪改旧Task Result。
3. **完成与未知效果有优先级。** 同一合法关联来源已成功/忽略/不应重试，祖先Pending不能
   再提供它；未知效果只核查，不能被祖先Pending或其他失败状态降格为可恢复。统一真实
   Task/Result/执行状态编码，不能只按Result小写标签或当前item状态断言。无法证明同一
   来源/安全承接关系时明确拒绝或引导核查，不能猜测最近Task或仅按路径/标题跨工作去重。
4. **范围、预算、动作与准入一致。** `remaining_scope`/`recovery_scope_plan`、discovery
   FILE/目录范围与排除集、原生lifecycle动作和实际POST都消费同一有效结论。全已决的
   满额链不提供动作，直接请求409且不创建新工作/Provider/执行许可。核对同一原工作多次
   尝试的名额占用，不因多一条恢复item就重复扣减或放宽原预算。已有开放准备在后续完成/
   变成未知效果后不能继续按旧排除集发布或确认可重放计划；复核现有发布/确认原子边界。
5. **覆盖同一根因的边界。** 至少COPY+Rename成功后不再准备/执行；MOVE成功与附件异常
   不重放主项；原Pending+后续忽略/跳过/未知效果均不能复活；原Pending+后续可证明零效果
   失败仍可安全恢复；多代/混合成功兄弟/仅确认子集/重复与丢响应/跨连接重开。新文件或
   独立普通Files新意图不被旧成功永久压住；无新全局路径黑名单。保留首次满额Pending、
   真实稳定期、原pin/来源变更、预算/RBAC/owner/claim/fence的成功与拒绝断言。
6. 同一Task45.5提交连贯修正checkpoint与实际报告，Base/Goal/High/T4不变。不展开RO-8/
   冻结43，不改Slice/Roadmap/Progress。当前报告保持最新，细节历史留Git。

### Developer 本次受影响验证

仓库根，模块名已核对；只跑新增/修改与直接受影响项：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_execution test_recovery_continuation test_task_center_recovery_lineage test_recovery_batch
PYTHONPATH=tests .venv/bin/python -m unittest test_operations_run_inventory test_operations_run_detail test_operations_task_center
# 修改持久映射/共有预算时追加
PYTHONPATH=tests .venv/bin/python -m unittest test_task_persistence test_sqlite_backup test_sqlite_restore
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
```

新增“原Pending→真实恢复成功→重开后不能再执行同一来源”的API/Worker集成断言。
受影响原生交互在`web/tests/e2e/operations-inventory.python.spec.ts`补充真实Python旅程，
只跑新增/修改用例及原满额/缺pin/原mutation-authorized恢复用例；若改Web代码，追加对应
交互单测、typecheck、production build和changed文件eslint/prettier。不得删断言、扩超时/
重试掩盖问题。Developer不跑完整Python/Web/E2E或发布矩阵。

B在修正候选上独立重现完整成功后分支，完成原Base..Head审查及Required Tests既定全部T4、
原生/视觉、wheel/隔离安装CLI/API/Worker、固定候选生产Docker、fresh/reopen/支持版本升级/
失败原子性。完整门禁和证据补齐仍由B负责；只有匹配源码/测试/harness/依赖/配置/产物的
结果可复用，不机械重跑Final，不把未跑/中断结果算PASS。

### 本轮实际证据与门禁状态

本机稳定ignored存储（非远程CI）：
`.git/validation-evidence/6f79676a12147a671a1b466af885fff1e7ce1790/task45.5/b-review/`。

- `verify_scope_and_identity.py` / `scope-and-identity.json`：原限额2/4恢复修正和两个顺序的
  三份准入身份/实际清单独立通过。
- `verify_remaining_stability.py` / `remaining-stability.json`：0/真实1秒稳定观察独立通过。
- `reproduce_completed_recovery.py` / `completed-recovery.json`：真实两次execute/Worker
  completed和两份目标文件；新连接重开仍有旧Pending；脚本exit0证明P1而非产品PASS。
- 治理、changed Python ruff/format与git diff --check结果、命令/cwd、耗时见quality.log/
  README.md/review-timing.json。计入探索及重复验证，验证累计保守上限20秒，
  占本轮复核时间约5.9%，严格低于50%。
- 明确P1后未启动完整Python/Web/E2E/wheel/Docker/视觉门禁，继续pending B；旧候选或中断
  结果不充作当前完整PASS。本轮仅checkpoint TASK.md，用户预存变化保留。

RO-7仍未通过、RO-8未实现，不新造Task，不提交Closure Packet，不关闭Slice。
