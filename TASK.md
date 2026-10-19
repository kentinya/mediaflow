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
Next Action: B REVIEWS CANDIDATE 86f8af95 FOR BOTH P1 FIXES AND COMPLETES ASSIGNED T4 / BASE..HEAD REVIEW
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

READY FOR B REVIEW at implementation HEAD `86f8af953cf9c2501e107831a2da754bd68c0640`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previously reviewed candidate
`4afeb5eea39130325e1739a9eb2602f57262719b`). Same Task, Base / Goal / High / T4 unchanged.

### 本轮（B 第四次 FIX REQUIRED）修正

**先重现（修复前）。** 直接运行 B 的 `reproduce_recovery_scope.py`（Task Base 不变）：
P1-1 真实 409 `no_remaining_scope`（`remaining()` 已返回 Left、预算 >0）；P1-2 Task B 恢复
409 `discovery_conflict`，普通 Files 准备 202 却拿到 A 的同一 discovery 且带 A 的
recoverySourceTaskId、计划只剩 Left。两处均在修改前复现，未改动断言。

**P1-1 根因与修复：未决来源必须留在恢复范围。**
`admit_recovery_preparation` 把 `remaining_scope()` 的 `already_recorded`（所有已记录项，
含 Pending/Processing/Failed/Paused）整体当作排除项，同时用 `remaining_limit==0` 判定"无剩余"。
当原预算已全部被记录占用、但其中仍有未决项时，范围被排空且拒绝。

- 新增 `application.scope_continuation.recovery_scope()`：`undecided_items` =
  仍在 `_REMAINING_ITEM_STATUSES` 且无终态 Result/不确定效果的项；
  `replay_excluded_sources` = 已记录 − 未决（即成功/DryRun/Skipped/Ignored/不确定效果）；
  `new_source_budget` = 原剩余未记录预算 + 未决项数（未决项已计入原准入，不重复扣减、也不放宽原预算）。
- 准入：排除集只取 `replay_excluded_sources`；`no_remaining_scope` 仅在既无未决项又无进一步
  来源预算时给出；有界只读探针与 admitted primary bound 使用同一固定选择
  （`max_primary_sources = new_source_budget`）。
- 排除集超过 `max_scope_paths` 时明确 409 `recovery_scope_over_limit`，不截断（截断会重新提供已决来源）。
- Worker walk 的排除语义不变：成功/忽略/未知效果 sibling 仍不 observe/不重新提供/不重放。

**P1-2 根因与修复：统一应用层与存储层的完整准入身份。**
`_admission_signature`（唯一索引检查工具）与 `find_open_media_discovery` 各自拼装，且都不含
definition origin / recovery origin / 排除集 / 预算，因此恢复准备、普通准备、其他 Task 的恢复
在存储层是同一身份。

- 新增 `domain.media_discovery.discovery_admission_identity()` 作为**唯一**身份权威：
  actor / 库 / Storage / pin / 规范 scope / autoPrepare，加上 definition（定义身份+指纹）与
  恢复（原 Task、排序去重排除集、primary bound）；origin 键仅在实际属于该入口时出现，因此
  普通 Files 准入保持**逐字节相同**的旧签名（已开普通记录仍可协调，无需清库/回填）。
- writer（`_discovery_values`/`_admission_signature`）、`find_open_media_discovery`、
  `find_open_recovery_discovery` 全部改用该函数；普通 finder 额外以
  `recovery_source_task_id IS NULL` 硬隔离，恢复 finder 以 `recovery_source_task_id=?` 绑定。
- `_reconcile_admission` 传入 definition origin；内存替身回退路径同样排除恢复记录并比对定义。
- 原子性不变：`create_media_discovery` 仍在 `BEGIN IMMEDIATE` 内做请求身份/别名/签名检查；
  重复/并发/丢响应同一原请求收敛同一记录，不同 Task 与普通新意图互不借用 origin/排除集。

### 实际受影响命令/结果（本轮）

仓库根，`PYTHONPATH=tests`：

- `test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_organize_preparation` → **187 OK**
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_task_center_recovery_lineage test_recovery_continuation test_automation_run_once test_v2_automation_run_once test_preview_analysis` → **189 OK**
- `test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser test_scanner test_resource_library_pipeline test_scan_retirement_stability test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_direct_file_operations test_manual_operations_contract test_operations_task_center test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_recovery_batch` → **405 OK**
- 新增用例（真实 API/SQLite/LocalStorage/fake Provider，`_drive_recovery` 驱动持久 Worker）：
  - `test_scope_continuation`：`test_recovery_keeps_an_undecided_recorded_source_in_the_reviewed_scope`
    （Kept 成功 + Left Pending 已记录、原 budget 4 → 202；计划恰为 `Incoming/Sub/Left.2005.mkv`，
    Preview 带原 Task、媒体零变更、target 0）；
    `test_recovery_identity_isolates_tasks_and_ordinary_files_preparations`
    （A 重复→同 discovery；B 恢复→202 独立；普通 Sub 准备→202 独立且 origin 为 null；
     recovery→ordinary 后再 recovery 仍 202 且计划只含 Left；三份计划逐项相等）。
  - `test_task_persistence`：`DiscoveryAdmissionIdentityTests`（普通/恢复/两 Task 恢复/两定义
     在真实 SQLite 中互不 alias、变更排除集为不同准入、跨连接重开后仍按原身份读取）与
     `test_an_ordinary_admission_keeps_its_previous_durable_identity`（普通签名与旧实现逐字节相等）。
- 证据脚本 `.git/validation-evidence/task45.5-developer-fix2/verify_recovery_scope_and_identity.py`
  与输出 `recovery-scope.json`（exit 0；两案均通过，`elapsedSeconds` 0.3s）。
- 静态/治理：`python3 scripts/check_governance.py` PASS；`git diff --check` 干净；
  `.venv/bin/python -m compileall -q mediaflow tests scripts` OK；
  `.venv/bin/ruff check` 与 `ruff format --check` 覆盖全部 6 个改动 Python 文件 → passed / formatted。
- 本轮未改 Web/API 契约（仍返回 discovery 投影），故未重跑 Web/E2E；TASK 追加的
  Web 直接受影响项留给 B 在候选上执行。

### 已知失败/风险

- B 的 `reproduce_recovery_scope.py` 中 P1-1/P1-2 的**旧断言**现在按设计失败（它们编码的是缺陷
  行为）；本报告以上述新用例和证据脚本的等价/更强断言取代，未删除或弱化任何产品断言。
- 恢复身份现在包含排除集与 primary bound：同一原 Task 在**排除集实质变化**（例如某未决项被
  纠正为已决）后会成为新准入，而不再复用一个已不匹配的记录——这是有意的精确语义，B 需确认
  其符合"原请求重复收敛、实质改变拒绝/新准备"的要求。
- runtime schema 仍为 49（本次仅新增身份字符串内容，无新列/表）；B 仍需在真实 wheel/Docker 上
  复核 fresh/reopen 与支持版本迁移。
- `tests/e2e/direct-files.python.spec.ts` 既有 flaky 仍待 B 独立确认（非本 Task 引入）。
- wheel/隔离安装、生产 Docker、真实 Worker 长区间、1536×1024/380×720 截图等 T4 门禁仍 pending B。

预存修改保留且不纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
私有 ignored 配置不读取、不暂存。RO-8 未交付，本 Task 不宣称 Slice ready。

## B Review Result

```text
Reviewed candidate: 4afeb5eea39130325e1739a9eb2602f57262719b
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..4afeb5eea39130325e1739a9eb2602f57262719b
Handoff: 852bf306bf5256e48bec0b7410ee8a97f378884e (TASK.md only; execution inputs identical)
Decision: FIX REQUIRED — pending source loss and cross-work discovery identity collision
Previous nonzero-stability blocker: independently fixed through real API/durable Worker
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

本轮 main 固定上述候选，治理 PASS、Git/workspace可写；预存图片删除、未跟踪截图/日志/
ZIP/浏览器结果、私有配置均保持。读毕必读治理/角色/Contract/Task/当前指针，复核适用
需求、完整列表/整理/恢复旅程和 CURRENT/TARGET。原Base..Head审查继续核对新恢复准入/
Worker/持久化/schema49/API/Web及其既有消费者；发现明确P1后依workflow §6提前拒绝，
不宣称全diff审完或完整T4通过。未改A-owned边界、历史45.4接受或冻结43。

### 上轮修正已独立通过

真实 organize Task + Managed Active/API/SQLite/LocalStorage/fake Provider：稳定期0通过
202持久准入后生成摘要；稳定期1秒首次Worker为waiting_stability、Provider0，立即不能
重领，真实等待超过1秒后可完成并链接仅Left.2005.mkv的精确摘要，成功兄弟Kept未重放。
两组临时媒体内容保持、目标文件0。B基于前轮独立脚本适配真实202→Worker契约和断言，
不把Developer脚本标签当作验收，也未降低稳定期。

### 当前P1-1：已记录但未处理的来源被当成成功兄弟排除

独立真实API fixture：organize Task暂停，Kept已成功；Left已有可信源证据但为Pending，
尚无结果/效果；原item_limit=4，`remaining_scope()`实际返回Left，剩余未发现预算2。
请求该Task的剩余范围摘要却409 `no_remaining_scope`，没有准备记录。

根因：`admit_recovery_preparation`取到了`remaining`，但构造`excluded`时把
`already_recorded`全部排除，没有减去仍合法未决项；该集合包含Pending/Processing等原工作
尚未决定的来源，不等于成功/忽略/未知效果。随后探针与Worker都跳过Left，恢复失去范围。

### 当前P1-2：新恢复准备与普通准备/其他任务共享错误去重身份

同actor/库/root/pin/目录Sub、autoPrepare=true：

1. Task A恢复202；重复同A请求仍202同discovery，正常。
2. 独立Task B在同目录恢复，却409 `discovery_conflict`，因为存储层认为它就是A的工作。
3. 随后普通Files请求整个Sub（Kept+Left），202返回A的同一discovery，响应仍带A的
   recoverySourceTaskId；实际Worker计划只含Left。普通新意图错误继承A的排除项和原任务关联，
   隐藏了用户此次明确选择的Kept。全程零媒体mutation，并不因此满足范围正确性。

根因：`find_open_recovery_discovery`按Task区分，但实际`create_media_discovery`原子事务用
`_admission_signature`检查唯一身份，其内容仍只有actor/库/Storage/pin/scope/autoPrepare。
`find_open_media_discovery`也构造同一签名，因此既会阻塞别的恢复，又会让普通准入借用恢复。
仅修改application快速查找或仅换discovery UUID不能修复实际原子边界。

### Developer 必需修正与顺序

1. **先重现上表真实API范围。** 保留原Task pin/预算、Kept成功、Left可信Pending的反例；
   验证remaining非空且有预算，不能只检查source已recorded。再以两个Task和普通Files目录
   准备按两种先后顺序提交，检查真实discovery身份、origin、exclusions、最终manifest/计划。
   不只检查HTTP202、source文件没被改或单Task重复通过。
2. **区分未决来源与禁止重放来源。** 在现有`remaining_scope`及checkpoint/result语义下，
   排除已成功/忽略/已决定且不应重试/未知效果，保留该恢复允许继续的未决项；构造持久
   排除集时不要将all recorded视为all completed。探针和Worker使用同一固定选择。
   已有未决项的预算占用与尚未发现项的剩余预算分开核对，既不重复扣掉Pending，也不把
   原预算增加；只有确实无合法剩余才no_remaining_scope。真实来源重验、稳定期、原pin、
   锁/claim/fence与成功/未知不重放保持。不能删排除功能让所有成功兄弟重新进入。
3. **统一应用和存储层的完整准入身份。** 普通Files准备、定义来源、Task恢复按实际意图
   隔离；恢复身份至少绑定原Task/不可变pin/精确scope及影响行为的排除/预算上下文。
   同一原请求重复/并发/丢响应收敛原记录；不同Task及普通新意图不得互借origin/排除集。
   修改`_admission_signature`、对应普通/恢复finder、`create_media_discovery`事务竞争检查
   和必要持久读取，使各层语义一致；现有requestId/跨family绑定不能被绕过。
   对支持版本普通开放工作保留安全重开/识别默认语义，不清库、清签名或放弃原子去重。
   原上下文实质改变须明确拒绝或走合法新准备，不能静默复用不匹配记录。
4. **验证最终行为与同源消费者。** 同A重复保留同discovery；A/B互不阻塞/混淆；普通Files
   每次独立新意图按其完整选择发现，不继承任何恢复排除。覆盖ordinary→recovery和
   recovery→ordinary、同actor并发、同root/pin、响应丢失与跨连接重开，检查manifest逐项相等。
   未决Left能进入稳定观察→摘要；Kept/忽略/未知效果不会重放。保留上轮真实非零等待修正。
5. **交接仍为同一Task。** 提交连贯固定SHA，Task45.5/Base/Goal/High/T4不变；不展开RO-8
   独立Preview退役或冻结43，不改Slice/Roadmap/Progress。不为修复新建索引或第二引擎。
   当前文档只保留最新报告，详细旧轮次留Git。

### Developer 本次受影响验证

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_task_persistence test_sqlite_backup test_sqlite_restore test_task_center_recovery_lineage
# 修改共有准入签名时，追加直接使用该边界的消费者
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_run_once test_v2_automation_run_once test_preview_analysis
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
# cwd web/：新增/修改真实交互证明的直接受影响项
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

新增上述未决/终结混合、两个Task/普通意图顺序与并发的API/持久Worker回归，断言准确scope/
manifest/origin/exclusions/原预算/重开，不削弱原断言。现有等待/稳定/源变更/原pin安全不回退。
Developer不跑全Python/Web/E2E/发布矩阵。B复现修正，完成原Base..Head审查，承担Required
Tests原分配的完整T4、独立原生/视觉、wheel/安装消费者、Docker和schema49的fresh/reopen/
支持版本升级/失败原子性门禁。匹配输入/产物依workflow复用，不机械重复Final；本轮未执行
门禁不算PASS，不交回Developer补全量证据。

### 本轮实际验证与证据

本机稳定ignored storage（非远程CI）：
`.git/validation-evidence/4afeb5eea39130325e1739a9eb2602f57262719b/task45.5/b-review/`。

- `verify_remaining_stability.py` / `remaining-stability.json`：真实202→持久Worker→真实1秒
  稳定区间→同源摘要通过；等待阶段Provider0、无mutation/执行权。
- `reproduce_recovery_scope.py` / `recovery-scope.json`：两个P1的真实API/SQLite/Worker复现；
  脚本exit0表示已证实缺陷及成功对照，非产品PASS。临时媒体保持、target0。
- 修改核心文件ruff check通过，治理和git diff --check通过。
- 已证实阻塞，本轮未启动完整Python/Web/E2E/wheel/Docker/视觉门禁，继续pending B；
  不把此前中断或其他执行输入的结果算本候选完整通过。
- 验证命令保守累计上限10秒，低于本轮总复核时间50%；实际起止/比例见同目录timing。

仅checkpoint Task，预存用户变化不纳入。RO-7未通过、RO-8未实现，不造新Task，不提交
Closure Packet，不关闭Slice。
