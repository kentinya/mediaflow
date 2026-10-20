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
Next Action: DEVELOPER FENCES EVERY SELECTED RECOVERY SOURCE IN MIXED SCOPES; SAME TASK AND B-OWNED FULL GATES
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
was **FIX REQUIRED — an already-admitted preparation still replays a completed recovery source**
(P1). This round fixes only that root cause, its boundaries and its tests.

### 先复现（修复前）

A recovery preparation is admitted while its exact source is still undecided. Its discovery /
freeze / analysis then run later in the resident Worker, and the deciding effect of an *earlier*
preparation is recorded on a **descendant** Task/Result. Nothing on the preparation's own Task row,
Preview, intent, versions or pin changes, so the fixed admission snapshot kept offering the source.

I reproduced B's exact sequential shape with the real managed Active revision, real SQLite runtime,
real LocalStorage, real API and the real `ManualOrganizeExecutionWorker`
(`.git/validation-evidence/task45.5-developer-fix5/before-fix/reproduce_without_fences.py`, each new
boundary neutralized only in memory):

1. summary A published for `Left`; 2. preparation B admitted (202) while `Left` was undecided and
deliberately **not** driven; 3. A explicitly confirmed and really COPY-executed → `Left (2005).mkv`;
4. B driven → it published a **second** summary for the same `Left`; 5. B confirmed (202) → real
Worker completed again → `Left (2005) (1).mkv`. Both sources stayed intact and all three attempts
shared one fingerprint. Raw result: `before-fix/reproduced.json` (`targets_after_second` has two
files).

### 修正：把"已受理准备是否仍可提供其来源"收敛成一个共享权威，并在四个边界重问

`application/scope_continuation.py` 新增 `recovery_preparation_eligibility()` +
`RecoveryPreparationEligibility.may_offer()`：只读地重算源 Task 仍暂停/同 pin、整条显式链仍
有未决来源或无记录预算，并给出逐来源的 `may_offer`（未决=可，已决/未知效果=不可，从未记录的
来源仅在原准入仍有预算时可）。已决、忽略、主项已完成、未知效果都使来源退休；可证明零效果
失败（`effect_certainty == "none"`）仍是未决工作；同路径被替换的新文件保留自己的未决状态；
普通 Files/定义准入 `applies=False` 完全不受治理。

四个独立边界都重问同一结论：

1. **Worker 推进/冻结/分析** (`application/media_discovery.py`)：`run_claimed` 在 observe/
   freeze/analyse 前、`_begin_preparation_analysis` 冻结前、`_analyze` 发布摘要前调用
   `_stale_recovery_preparation()`，以 `CANCELLED` + `phase="stale"` + 有界原因/下一步结清；
   清空 manifest 与 `preview_id`，不发布 intent/Preview、不授予权限、零 mutation。
2. **逐来源 walk 过滤**：`_advance` 用 `may_offer(library.storage_id, storage_path)` 在
   `observe()` 与目录条目两处丢弃"准入后已决"的来源，即使 `recovery_excluded_paths` 是准入时
   的固定集合。
3. **授权/执行应用边界** (`application/manual_organize_execution.py`)：`authorize`、
   `execute`/`admit`、Worker 的 `_reconstruct_reviewed_scope` 都调用
   `_assert_recovery_preparation_live()`；已决来源返回 409 及真实 code（如
   `recovery_scope_decided`）。
4. **确认的原子边界** (`infrastructure/sqlite_runtime.py`)：`admit_manual_execution` 在
   `BEGIN IMMEDIATE` 事务内（消费一次性授权、创建执行、取得来源所有权同一事务）调用
   `_assert_recovery_preparation_live_locked()`，HTTP 预检之后才发生的完成事实也无法准入。

### 新增真实旅程测试（`tests/test_scope_continuation.py`，10 个）

- `test_an_already_admitted_preparation_cannot_replay_a_completed_source`：B P1 的确定性时序；
  修复前第二次准备仍发布摘要，修复后 B 结清、无 Preview、目标恰一份。
- `test_a_queued_preparation_never_offers_a_source_decided_by_an_ignore`：显式忽略只改 TaskItem、
  无 Result，B 仍必须停止提供；已发布 A 摘要的确认被原子边界拒绝。
- `test_a_recovery_preparation_is_refused_once_its_source_is_unknown`：执行域 `unknown` 只核查。
- `test_a_zero_effect_failure_keeps_every_preparation_and_confirmation_legal`：`none` 失败后
  同一来源仍是合法工作，新摘要可确认并真实执行一次。
- `test_a_source_decided_while_the_execution_waits_in_the_queue_is_refused`：A 执行完成时 B 的
  摘要已发布但未确认，确认被原子边界拒绝、目标保持一份。
- `test_the_worker_refuses_a_source_decided_after_its_own_admission`：执行已受理并持有自己的
  Storage fence 后来源被忽略，Worker 在调用 `OrganizerExecutor` 前以 `effect_certainty=none`
  结清，零新效果。
- `test_a_pre_authorized_confirmation_is_refused_at_the_atomic_admission`：一次性授权仍 live 时
  来源被决定；关闭应用层预检后仅靠仓库事务拒绝，证明原子边界独立成立。
- `test_a_walk_skips_a_source_decided_after_admission_with_budget_left`：仍有未记录预算、按目录
  观察时，准入后已决来源由 walk 逐来源规则丢弃，新文件保留自己的合法单位。
- `test_a_reopened_database_keeps_the_same_admitted_preparation_refusal`：新连接同结论。
- `test_an_ordinary_files_preparation_is_never_governed_by_recovery_eligibility`：普通 Files
  准入不受治理，仍能发布并执行。

四个边界分别用"仅禁用该边界"验证过独立必要性（walk、run_claimed、Worker、SQLite 事务各使至少
一个用例失败）。

### Harness / 原生浏览器旅程

- `scripts/operations_inventory_harness.py`：新增 `run_discovery_worker_for()` 与
  `GET/POST /__harness__/run-discovery-worker?discoveryId=`，可只推进指定 discovery，使浏览器
  旅程能真实"先受理 B、再驱动 A、最后驱动 B"。
- `web/tests/e2e/operations-inventory.python.spec.ts` 新增
  `an already-admitted recovery preparation never replays a completed source`：真实 production
  build + 真实 Python API/Worker，深链到精确 run；断言 B 驱动后无 `previewId`、`sourceCount=0`、
  目标副本数只增加一次且源文件不变。禁用修复后该旅程失败（`sourceCount` 为 1）。

### 实际受影响命令/结果（仓库根，`PYTHONPATH=tests`）

- `test_scope_continuation` → **83 OK**（含 10 个新增用例）
- `test_media_discovery test_media_discovery_provider_manifest test_organize_preparation` → **127 OK**
- `test_manual_organize_preview test_manual_organize_execution test_recovery_continuation test_task_center_recovery_lineage test_recovery_batch` → **191 OK**
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_operations_run_inventory test_operations_run_detail test_operations_task_center` → **129 OK**
- `test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_v2_manual_organize test_manual_organize_intent` → **124 OK**
- Web（`cwd web/`）：`npm run typecheck` 干净；`npm run test -- run src/entities/operations/organize.test.ts src/features/operations/OrganizeRouter.test.tsx` → **35 passed**；`npx eslint`/`npx prettier --check` 改动 spec 干净；`npm run build` 成功。
- 原生：`npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g "already-admitted recovery preparation|fully recorded budget still recovers|mutation-authorized paused run|missing configuration pin"` → **4 passed**（真实 production build + Python API/Worker）。
- 静态/治理：`python3 scripts/check_governance.py` PASS；`git diff --check` 干净；`python -m compileall -q mediaflow scripts tests` OK；`ruff check` / `ruff format --check` 覆盖 6 个改动 Python 文件 → passed / formatted。

证据（本机 ignored 存储，非远程 CI）：`.git/validation-evidence/task45.5-developer-fix5/`：
`verify-fences.json`（修复后：B `cancelled`、`previewId=null`、`sources=[]`、目标一份）、
`before-fix/reproduced.json`（修复前：B `completed`、第二份目标）、`unittests.log`、`web.log`、
`quality.log`、`e2e.log`、`README.md`。

### 已知风险/边界

- 重新校验是**读时投影**，不改写任何 Task/Result/Intent/Preview 行；结清只清空该 preparation
  自己的 manifest/preview 链接，原观察、计数器、findings、refusals 与 intent 历史仍可独立检查。
- 普通 Files/定义准入完全不受影响（`applies=False`），独立新意图/新 occurrence 不被旧成功永久
  压制；跨任务批量 mutation 仍不在本 Task。
- runtime schema 仍为 49（无新列/表）；wheel/隔离安装、生产 Docker、fresh/reopen 与支持版本
  迁移、完整 Python/Web/E2E/视觉矩阵仍是 B 的 T4 门禁，本轮未运行也未声称通过。
- 同文件既有 `a paused run continues only its remaining scope through the real Worker` 在上一轮
  基线上即失败，本轮未改变其范围；留给 B 判定。
- 本轮测试执行合计约 2 分钟，占本开发轮次总时长约 6%，低于 30% 上限。

预存修改保留且不纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
私有 ignored 配置不读取、不暂存。RO-8 未交付，本 Task 不宣称 Slice ready，也不自判 PASS。


## B Review Result

```text
Reviewed candidate: a290b1aa4f3a440b0a98bebada21d25421cfee97
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..a290b1aa4f3a440b0a98bebada21d25421cfee97
Decision: FIX REQUIRED — overall recovery eligibility still authorizes a decided source in a mixed scope
Previous single-source queued-preparation blocker: independently fixed through real API/Worker
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

main固定上述候选，治理PASS、Git/workspace可写；预存图片删除、未跟踪截图/日志/ZIP/
浏览器结果及私有配置保留、不暂存。已读AGENTS/workflow/B经验/已提交Contract/Task/
当前指针及适用需求、完整列表/整理/恢复旅程与CURRENT/TARGET。原Base..Head审查继续，
明确P1后依workflow §6提前拒绝；未声称全部diff审完或完整T4通过。不改A-owned边界、
45.4历史接受或冻结43。

### 已独立确认的修正

真实Managed Active/API/SQLite/LocalStorage/fake Provider/持久Worker，临时媒体：

- 上轮单来源时序：A摘要ready→B queued→A真实COPY成功→再驱动B，B cancelled、无
  可确认摘要、来源数0、目标恰一份。上轮独立脚本改为正确期望，未把旧缺陷断言当PASS。
- 完成后新请求409、原生overview无恢复动作、新连接重开终态保持；目标恰一份。
- 原限额2/4首次Pending恢复、两种ordinary/recovery提交顺序的独立身份与准确清单正常。
- 稳定期0/真实1秒通过；首次等待Provider0、立即不可重领，真实等待后形成精确摘要。

以上为具体分支结果，不代替完整并发/原生/发布门禁。

### P1：Right仍未决，让已经完成的Left通过全部整体门禁再次COPY

独立fixture使用COPY+Rename、原organize Task暂停、item_limit=2；Left和Right均为可信
Pending，不播种成功Result或修改数据库时序：

1. 准备A真实生成Left+Right摘要；再准入准备B，驱动B **一次**正常discovery Worker，
   其已frozen、sources=2、已有intent、status=analyzing，尚无Preview。
2. 从A摘要仅显式选择Left，真实execute API202与ManualOrganizeExecutionWorker完成COPY。
   Right保持Pending，目标有一份Left。
3. 共享`recovery_scope_plan()`正确只剩Right；新权威的实际结论是
   `eligible=True / may_offer(Left)=False / may_offer(Right)=True`。
4. 再驱动B的分析：仍发布Left+Right摘要，两项均previewed。仅选择已完成的Left确认，
   实际API仍202、真实Worker再次completed，生成`Left (2005) (1).mkv`。两次Result均
   SUCCESS/verified_complete、与原Left指纹完全相同；源内容不变，Right没有执行。

因此单来源已修，但混合来源仍实际重放成功项。无需概率并发、关闭门禁或改用户配置；
只使用受支持的冻结/分析阶段和显式就绪子集确认。属于上轮要求的混合兄弟/子集分支，
继续同一Task，不新增目标或Task。

**定位。** walk已调用逐来源`may_offer`，但B在Left成功前就冻结了manifest。其后的
`_stale_recovery_preparation`/`_analyze`只检查整体`eligibility.eligible`，不逐项核对
frozen sources；Right尚待处理使整体一直为True。应用authorize/execute/Worker的
`_assert_recovery_preparation_live(preview)`以及SQLite事务的
`_assert_recovery_preparation_live_locked(source_task_id)`也只看整体True，后者甚至没有
接收本次selected scopes。权威已明确拒绝Left，实际发布/准入/Worker却没有消费该逐项结论。
事务内重读“还有任意未决项”不等于原子证明“本次选择的每项都合法”。

### Developer 必需修正与顺序

1. **先补真实混合反例。** A/B均含Left+Right，B已冻结但未分析→A仅完成Left→驱动B→
   尝试只确认Left。修改前真实第二次COPY产生两份Left；修改后Left不再作为可执行恢复项
   发布、确认或执行，目标始终一份。断言Right仍未决且经合法准确摘要可以继续，不能用
   “唯一来源全已决所以整体False”的现有测试代替。
2. **区分整体状态与具体范围资格。** 复用现有共享终态/可信来源/pin计算，提供接受精确
   source集合与本次selected subset的统一校验；`eligible=True`只表示整条链仍可准备，
   不能作为全部来源的许可；本次每个selected来源都须合法，不能用任意一个合法项代表全部。
   逐项使用Storage/ResourceLibrary/路径与occurrence/fingerprint/
   原pin，缺证据或不匹配按既有安全语义拒绝/核查；预算和原固定范围保持，不借其他未决项
   给已决来源、新来源或不确定来源腾出名额。不复制各层自定义判断。
3. **修复冻结后的发布。** 核对`_begin_preparation_analysis`、`_analyze`、Preview发布事务
   及手动重分析路径，对其**实际持有**的sources/items逐项校验，不能只拦walk或queued。
   Left已完成/忽略/未知效果时，旧manifest不能继续发布可执行Left。若Right仍合法，给出
   准确新摘要/明确状态和必要新确认；不自动把用户选中的Left替换为Right，也不改历史结果。
   可终结旧准备并合法重新准备，不能为省校验永久禁用仍合法的Right或所有第二次准备。
4. **修复确认的原子边界。** 应用authorize/execute将本次准确选择传入统一校验；SQLite
   `admit_manual_execution`在消费许可、创建执行、取得来源所有权的同一事务内对
   `authorization.scope`/真实selected execution items逐项核对当前链结果及其他尝试占用。
   `_assert_recovery_preparation_live_locked`不能仅接收原Task ID然后判断整链True。
   前置校验后Left才变已决时事务仍须拒绝Left；其他未决Right不能使它通过。
5. **Worker逐项校验效果边界。** 在每个即将执行的来源/步骤前复核本次来源资格，不能仅
   在`_reconstruct_reviewed_scope`对整份Preview检查一次。区分当前合法尝试自身的保留/
   已完成步骤与其他尝试结果，防止自拒绝、整批误伤或重放自己的已完成步骤；成功兄弟保持
   完成，未知效果只核查，零效果失败可恢复。继续使用现有claim/lease/fence与Executor。
6. **把时序与混合状态交叉覆盖。** 在至少两个来源下覆盖B queued、frozen/analyzing、
   summary已发布、授权已取得、执行已准入等待时，A仅完成/忽略/变成未知效果一个来源；
   对Left的确认拒绝，对合法Right保留准确恢复途径。独立证明原子仓库校验与Worker校验，
   不能只测应用层拒绝。保留真实一次执行多个来源正常完成、只选子集、零效果失败、重开/
   重启、并发确认/丢响应、普通Files独立新意图、原pin/来源变化/稳定期/RBAC/预算不变量。
7. 同一Task45.5提交连贯修正与最新实际报告，Base/Goal/High/T4不变；不展开RO-8/冻结43，
   不改Slice/Roadmap/Progress，不建第二队列、索引或引擎。详细旧轮次留Git。

### Developer 本次受影响验证

仓库根；仅新增/修改与直接受影响项，模块名已核对：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_preview test_manual_organize_execution test_recovery_continuation test_task_center_recovery_lineage test_recovery_batch
PYTHONPATH=tests .venv/bin/python -m unittest test_task_persistence test_sqlite_backup test_sqlite_restore
PYTHONPATH=tests .venv/bin/python -m unittest test_operations_run_inventory test_operations_run_detail test_operations_task_center
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
```

新增上述混合来源的真实API/SQLite/LocalStorage/Worker反例与当前合法多项执行成功对照；
在`operations-inventory.python.spec.ts`补真实Python混合子集旅程，只跑新增/修改及原已有
准备、满额Pending、mutation-authorized恢复、缺pin用例。若改Web代码，追加changed单测/
类型/build与changed文件eslint/prettier；不删除断言、加重试或扩超时掩盖问题。
Developer不跑完整Python/Web/E2E或发布矩阵，不准备B的全量证据包。

B在修正候选独立复现上述混合来源时序，继续原Base..Head全部审查并完成Required Tests
原分配的完整T4、原生/视觉、wheel/安装CLI/API/Worker、固定候选生产Docker，以及
fresh/reopen/支持版本升级/失败原子性。全量和证据补齐继续由B承担；匹配源码/测试/
harness/依赖/配置/产物的结果才可复用，不机械重跑Final，不把未跑/中断结果算PASS。

### 本轮实际证据与门禁状态

本机稳定ignored存储（非远程CI）：
`.git/validation-evidence/a290b1aa4f3a440b0a98bebada21d25421cfee97/task45.5/b-review/`。

- `verify_admitted_preparation.py` / `admitted-preparation.json`：上轮单来源queued时序独立通过。
- `verify_completed_recovery.py` / `completed-recovery.json`：完成后新请求/重开终态通过。
- `verify_scope_and_identity.py` / `scope-and-identity.json`：满额/对照与两种顺序三个意图清单
  通过；`verify_remaining_stability.py` / `remaining-stability.json`：真实稳定区间通过。
- `reproduce_mixed_frozen_scope.py` / `mixed-frozen-scope.json`：冻结两来源、仅Left成功后
  整体True/Left False/Right True，实际第二次Left确认/Worker完成且两份目标。exit0证明P1，
  不表示产品PASS。
- 治理、changed Python ruff/format及git diff --check结果、cwd/命令/耗时见quality.log/
  README.md/review-timing.json；累计验证包含所有探索/重复/等待，保守上限15秒，
  占本轮复核时间约4.9%，严格低于50%。
- Developer报告另一个paused-continuation原生E2E在前checkpoint已失败；B尚未核定首次引入，
  不据其标签豁免；后续门禁由B独立核实。本次FIX只基于独立证实的重复COPY。
- 明确P1后未启动完整Python/Web/E2E/wheel/Docker/视觉门禁，继续pending B；其他候选或中断
  结果不冒充当前完整PASS。本轮仅checkpoint TASK.md，用户预存变化保留。

RO-7仍未通过、RO-8未实现，不新造Task，不提交Closure Packet，不关闭Slice。
