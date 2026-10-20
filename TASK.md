# Task45.5 — FileIndex 完全退出与 CLI/Web 库级实时列表统一

Authority：已提交 [SLICE.md](SLICE.md) 与 [Development Workflow](docs/development-workflow.md)。
角色经验：[B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.5
Parent Slice: 45
Status: READY FOR B REVIEW
Task Base: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Required Outcome: RO-7; S-8 / S-9; AC-7; affected RO-1–6 safety and journeys
Next Action: B COMPLETES ORIGINAL BASE..HEAD REVIEW AND ASSIGNED ACCEPTANCE; NO NEW DEVELOPER FIX
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
T4 unchanged; implementation HEAD is this checkpoint's SHA (recorded in the B handoff). B's latest
finding was **FIX REQUIRED — overall recovery eligibility still authorizes a decided source in a
mixed scope** (P1). This round fixes only that root cause, its four boundaries and its tests; the
previous single-source blocker remains fixed.

### 先复现（本轮修复前）

B 的精确混合时序：A 摘要同时发布 `Left`+`Right`；B 在两者都未决时受理并推进到 **frozen**；A 随后只
真实完成 `Left`，`Right` 仍待处理，因此整链 `eligible=True`。B 的冻结 manifest 已含 `Left`，重新
发布时逐来源权威虽已拒绝 `Left`，但发布/授权/准入/Worker 都只看整体 `True`，于是 B 再次发布
`Left`+`Right`，只确认 `Left` 仍二次 COPY 出 `Left (2005) (1).mkv`。

用真实 Managed Active/API/SQLite/LocalStorage/Worker 复现（`reproduce-b-p1-fixed.log`）。

### 修正：把整体资格与具体范围资格分开，并在四个边界重问逐来源结论

`RecoveryPreparationEligibility` 新增 `check_sources()` / `refused_sources()`：`eligible` 只表示整链
仍有工作，不能作为全部来源的许可；每个待发布/授权/准入/执行的来源按 `(storage_id, path)` 逐项
判定（未决=可，已决/忽略/未知效果=不可，新来源仅在原准入仍有预算时可）。四个独立边界都消费
同一结论：

1. **冻结后发布** (`application/media_discovery.py`)：`_begin_preparation_analysis` 与 `_analyze`
   在冻结/发布前用 `_filter_frozen_recovery_sources` 逐项丢弃已决来源；全部已决则按既有 stale
   结清（`CANCELLED`+`phase=stale`，零 Preview/权限/mutation）。`_undecided_intent_item_ids`
   把同一逐来源结论叠加到普通“已受理执行”排除之上，混合范围只发布仍未决的来源。
2. **应用 authorize/execute** (`application/manual_organize_execution.py`)：`authorize`、
   `execute`/`admit` 先解析本次精确选择，`_assert_recovery_preparation_live(preview, sources=)`
   逐项核对，已决来源返回 409 `recovery_scope_decided` 并点名来源。
3. **确认的原子边界** (`infrastructure/sqlite_runtime.py`)：`admit_manual_execution` 在同一
   `BEGIN IMMEDIATE` 事务内把 `authorization.scope` 的真实 selected items 逐项传入
   `_assert_recovery_preparation_live_locked(..., sources=)`，前置校验之后发生的完成事实也无法
   准入；`eligible=True` 不再放行。
4. **Worker 逐项效果边界** (`application/manual_organize_execution.py`)：`_run_worker_items`
   在每个即将执行的来源/步骤前重问 `_recovery_eligibility_for(preview)` 的逐来源结论；仅该来源
   以 `effect_certainty=none` 结清，独立合法兄弟照常执行，未决来源不会自拒绝。

### 新增真实旅程测试（`tests/test_scope_continuation.py`，6 个）

- `test_a_frozen_mixed_preparation_never_publishes_a_decided_sibling`：B 先冻结两来源，A 只完成
  `Left`，B 只发布 `Right`，目标恰一份 `Left`，`Right` 仍合法执行。
- `test_a_frozen_manifest_that_loses_every_source_settles_stale`：B 冻结后两来源全被 A 完成，B 不
  再发布、无权限、目标不变。
- `test_a_published_mixed_summary_refuses_only_the_decided_sibling`：已发布混合摘要确认时按名拒绝
  已决 `Left`，保留合法 `Right`。
- `test_a_mixed_scope_is_refused_by_the_atomic_admission_alone`：关闭应用预检后，仅仓库事务拒绝
  已决 `Left`，不创建执行、不消费一次性授权。
- `test_a_queued_mixed_execution_refuses_the_decided_source_per_item`：混合执行已准入等待中 `Left`
  被显式忽略，Worker 逐项以 `none` 结清 `Left`、`Right` 真实 SUCCESS。
- `test_a_mixed_scope_reopens_with_the_same_per_source_refusal`：新连接同结论。

四个边界分别用“仅禁用该边界”验证独立必要性：冻结过滤、应用断言、Worker 逐项各使至少一个用例失败；
原子事务由 `test_a_mixed_scope_is_refused_by_the_atomic_admission_alone` 在关闭应用预检时独立证明。

### Harness / 原生浏览器旅程

- `scripts/operations_inventory_harness.py`：新增 `seed_mixed_scope_recovery` 与
  `GET/POST /__harness__/seed-mixed-scope-recovery`、两个 COPY 候选与 `MixedScope` COPY 规则，
  使混合范围两来源都解析为 COPY，重复执行可见为第二份目标文件。
- `web/tests/e2e/operations-inventory.python.spec.ts` 新增
  `a frozen mixed recovery preparation never republishes a decided sibling`：真实 production build +
  真实 Python API/Worker，深链精确 run；B 冻结后 A 只完成 `Left`，断言 B 驱动后只发布 1 项、目标
  副本数不再增加、源文件不变。

### 实际受影响命令/结果（仓库根，`PYTHONPATH=tests`）

- `test_scope_continuation` → **89 OK**（含 6 个新增用例）
- `test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_organize_preparation` → **216 OK**
- `test_manual_organize_preview test_manual_organize_execution test_recovery_continuation test_task_center_recovery_lineage test_recovery_batch` → **191 OK**
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_operations_run_inventory test_operations_run_detail test_operations_task_center` → **129 OK**
- `test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_v2_manual_organize test_manual_organize_intent` → **124 OK**
- Web（`cwd web/`）：`npm run typecheck` 干净；`npm run test -- run src/entities/operations/organize.test.ts src/features/operations/OrganizeRouter.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx` → **93 passed**；`npx eslint`/`npx prettier --check` 改动 spec 干净；`npm run build` 成功。
- 原生：`npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g "frozen mixed recovery preparation|already-admitted recovery preparation|fully recorded budget still recovers|mutation-authorized paused run|missing configuration pin|selected execution never blocks"` → **6 passed**（真实 production build + Python API/Worker）。
- 静态/治理：`python3 scripts/check_governance.py` PASS；`git diff --check` 干净；`python -m compileall -q mediaflow tests scripts` OK；`ruff check` / `ruff format --check` 覆盖 6 个改动 Python 文件 → passed / formatted。

证据（本机 ignored 存储，非远程 CI）：`.git/validation-evidence/task45.5-developer-fix6/`：
`reproduce-b-p1-fixed.log`、`verify_mixed_scope_fixed.py`、`fence_independence.py`、
`unittests.log`、`quality.log`、`README.md`。

### 已知风险/边界

- 逐来源过滤是**读时投影**，不改写任何 Task/Result/Intent/Preview 行；全已决时沿用既有 stale 结清，
  原观察、计数器、findings、refusals 与 intent 历史仍可独立检查。
- 普通 Files/定义准入完全不受影响（`applies=False`），独立新意图/新 occurrence 不被旧成功永久压制；
  跨任务批量 mutation 仍不在本 Task。
- runtime schema 仍为 49（无新列/表）；wheel/隔离安装、生产 Docker、fresh/reopen 与支持版本迁移、
  完整 Python/Web/E2E/视觉矩阵仍是 B 的 T4 门禁，本轮未运行也未声称通过。
- 同文件既有 `a paused run continues only its remaining scope through the real Worker` 在上一轮基线上
  即失败，本轮未改变其范围；留给 B 判定。
- 本轮测试执行合计约 2 分钟，占本开发轮次总时长约 7%，低于 30% 上限。

预存修改保留且不纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
私有 ignored 配置不读取、不暂存。RO-8 未交付，本 Task 不宣称 Slice ready，也不自判 PASS。

## B Review Result

```text
Reviewed candidate: 90b697f3b689b57d1d8a155076781d1501a4525c
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..90b697f3b689b57d1d8a155076781d1501a4525c
Decision: NOT PASS — prior P1 classification withdrawn; B acceptance incomplete
Previous frozen mixed-scope blocker: independently fixed; legal Right executes without replaying Left
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: B FINISHES ORIGINAL BASE..HEAD REVIEW / ASSIGNED T4; NO PROVEN NEW PRODUCT BLOCKER HERE
```

main固定上述候选；治理PASS、Git/workspace可写，预存图片删除、未跟踪截图/日志/ZIP/
浏览器结果及私有配置保持、不暂存。已读AGENTS/workflow/B经验/已提交Contract/Task/
当前指针，复核适用需求、完整列表/整理/恢复旅程和CURRENT/TARGET。原Base..Head审查
继续；本轮撤回下述证据直接构成P1的判断，未宣称全部diff审完或完整T4通过。不改A-owned
边界、45.4历史接受或冻结43。当前仅留最新Developer/B报告，删除的重复旧报告仍在Git。

### 已独立确认的修正

真实Managed Active/API/SQLite/LocalStorage/fake Provider/持久Worker，临时媒体：

- 上轮冻结混合时序：A/B均含Left+Right，B先冻结→A只完成Left→B分析仅发布Right→
  确认Right，真实Worker完成；目标各一份Left/Right，无重命名重复Left，源内容保持。
- 上轮单来源queued准备在A成功后cancelled、无可确认摘要、目标恰一份；完成后新请求
  409、overview无恢复动作、新连接重开终态保持。
- 原限额2/4首次Pending恢复、两个ordinary/recovery顺序的独立身份/准确清单正常。
- 稳定期0/真实1秒通过，首次等待Provider0、立即不可重领，真实等待后形成精确摘要。

以上是具体分支的独立结果，不代替完整原生/并发/发布门禁。

### 已确认代码事实与未确认的产品语义

B的隔离确定性时序：原organize Task暂停，Left为Pending、Right为Processing；通过真实
恢复API确认两项，产生已授权的关联执行。在真实Left COPY返回后，测试回调调用
MetadataReviewService令原Right进入等待，再通过真实原任务recovery API忽略Right。
原Right持久为ignored，新读准备资格Right=False，但已准入的关联执行仍COPY Right并成功。

代码原因已确认：`_run_worker_items`在循环前读取一次恢复资格，循环内复用读时集合。
该测试在正常暂停之后手工把Right改回Processing，再通过服务/API注入并发事件；
这与正常暂停将Pending/Processing改为Paused的流程不同，不能证明普通用户可到达该时序。
更关键的是，原任务的忽略与已明确确认的关联执行属于不同TaskItem；现有需求没有明确
规定前者会撤销后者的执行授权。准备资格变为False也不能直接等同于既有执行权限已撤销。

因此撤回上轮“本应已忽略、仍执行即P1”的确定判断，以及据此强制Developer逐项刷新并
终止第二项的修正清单。该反例证明缓存行为，不独立证明产品违反必需功能；不是候选PASS。

### 正常入口调查结论与后续分工

对`f7a7117`独立核对，产品/测试代码与`90b697f`一致（两者间只改TASK.md）。
正常协调器暂停、真实API、精确摘要和真实Worker/Executor COPY三组隔离场景通过：

| 正常旧条目状态 | 旧条目的忽略动作 | 实际继续整理范围与结果 |
|---|---|---|
| Processing经真实暂停变成Paused | 不提供ignore；直接请求400；迟到MetadataReview创建被事务拒绝且无残留 | Left、Right均合法确认并各完成一次 |
| 暂停前已有待处理MetadataReview | 提供ignore，执行期间请求200 | Right被排除在精确摘要之外；仅Left执行，Right持久忽略 |
| MetadataReview已合法解决 | 新checkpoint无ignore，请求400；旧等待checkpoint请求409 | Left、Right均合法确认并各完成一次 |

按钮显示读取后端`permittedActionIds`，只在含ignore时显示；以上为代码检查及真实接口/
Worker验证，不冒充浏览器点击。第一组在Left真实完成后再试忽略Right仍拒绝，第三组也验证
旧页面过期提交拒绝；第二组允许处理的旧文件根本不在新执行内，因此没有忽略与执行冲突。

结论限定为这些正常状态转换：上轮注入反例不能证明用户能在旧任务忽略同一已确认来源，
不构成本轮Developer产品返工依据。缓存事实保留，未证明的新并发语义不作为A待决阻塞，
不增加跨尝试撤权或永久忽略功能。若以后真实入口出现矛盾决定，再按可达性及授权契约复核。

Developer无须按已撤回清单增加行为；Task45.5目标、Base、High/T4及安全约束保持。
B继续原Base..Head审查、原生失败定位及既定完整T4，不把门禁或证据工作转交Developer。
本调查只解决该可达性疑问，不等于Task PASS，也不豁免现有原生失败和未完成门禁。

本机稳定证据：`.git/validation-evidence/f7a711764f022d77934223673255088c60938ad2/task45.5/old-task-ignore/`
中的`probe.py`、`result.json`、`README.md`。三组正常流程均通过，所有媒体为临时fixture。
首次探测把实际400误断言为409而失败，回调导致的unknown不算产品缺陷，原stderr保留；
两次验证连同治理/文档检查保守计2秒，本轮调查已超过120秒，验证占比低于50%。

### 本轮实际证据与原生续跑失败核查

本机稳定ignored存储（非远程CI）：
`.git/validation-evidence/90b697f3b689b57d1d8a155076781d1501a4525c/task45.5/b-review/`。

- `verify_mixed_frozen_scope.py` / `mixed-frozen-scope.json`：冻结混合修正+Right实际执行通过。
- `verify_admitted_preparation.py`、`verify_completed_recovery.py`、`verify_scope_and_identity.py`、
  `verify_remaining_stability.py`及对应JSON：前轮单来源、满额、去重、真实稳定区间通过。
- `reproduce_live_worker_decision.py` / `live-worker-decision.json`：真实Review+Ignore API200、
  live Right=False，但Worker仍执行Right并verified_complete。exit0证明该注入时序和缓存行为；
  脚本原P1断言标签不构成跨尝试撤权需求或产品缺陷的独立证据，不是产品PASS。
- 当前production `npm run build`通过；B实际执行原生
  `operations-inventory.python.spec.ts -g "a paused run continues only its remaining scope through the real Worker"`
  失败1项。准入202/真实Worker/仅剩余来源持久清单及首次重开步骤均已通过；失败发生在
  后续全局`预览+已完成`row计数：期望1、实际2。原始log/trace/error-context保留在
  `native-continuation.log` / `native-continuation/`，不是产品拒绝续跑或重复处理的独立证明。
  B未独立跑Task Base，不采信“上一候选也失败”作为Base失败豁免；该原生门禁仍FAIL，
  正确身份定位/fixture/验收处理由B承担，不作为本次Developer产品P1返工理由。
- 治理、changed Python ruff/format及git diff --check结果、build/原生命令/cwd/实际耗时、
  回调探索/重复验证见quality.log/native-timing.json/README/review-timing.json；验证累计保守
  上限40秒，占本轮复核时间约6.0%，低于50%。
- 上轮按P1判断提前停止，未启动完整Python/Web/E2E/wheel/Docker/视觉门禁；撤回判断后仍
  pending B，需继续完成。其他候选或
  中断结果不冒充当前完整PASS。本轮仅checkpoint TASK.md，用户预存变化保留。

RO-7仍未通过、RO-8未实现，不新造Task，不提交Closure Packet，不关闭Slice。

本次正常入口调查仅修改B-owned Task，无产品改动；上述受控验证、治理及文档差异检查通过。
