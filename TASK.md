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
Next Action: DEVELOPER FIXES REAL CLI PAGINATION AND ITS FALSE-POSITIVE PROOF IN THE SAME TASK
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

READY FOR B REVIEW at implementation HEAD `52e13ce2c316aafa0bd1c2b424587572cee41d06`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`a3fbb36c7f86ed08629e08247a08e5f154d4adbb`). Same Task, Base / Goal / T4 unchanged.

### 行为与关键决策

- **P1 稳定观察约束重试与执行。** `PersistentTaskItem`/`PersistentResultRecord` 新增
  `source_observed_at`（runtime schema 48，additive 列，fresh 创建、旧库原地升级不回填）。
  `MediaOrganizerService.process_file` 首次选择记录该工作自己的真实首观察时刻；retry/resume/
  recovery/Worker/Automation 调用在 Provider/执行前用同一 `stability_decision` 策略、按工作原
  pin 与 live `stat` 重新判定。`resolve_source_evidence=False` 只允许继续观察/等待，不再把
  “指纹相同”当作“区间已满足”。稳定证据缺失时从当前时刻重新计时。
- **P2 持久等待闭环。** 观察起点/来源证据落在该显式工作的 TaskItem/Result（`source_observed_at`），
  重开/新进程可读；合法证据继续、丢失证据重新观察。到期后真实重观察，来源变化重置区间。
  长区间（>60s）不阻塞同步命令，记录为等待项并由 retry 继续观察；0 秒不新增等待、真实空目录
  仍 0 项结束。未建第二队列/全局目录。
- **B-2/P1 Worker 校验原证据可信状态。** `PersistedSourceEvidence.has_exact_evidence` 现在同时
  要求 `fingerprint_state == verified`。`ManualSourceValidator.validate_persisted_source` 与
  `_persisted_source_refusal` 对缺失/半缺失/unverified/legacy 一律 `source_unverified` 拒绝，
  保留记录并指向重新选择/准备；不再根据当前 stat 升级不可信原记录。真实 Worker 续作与直接
  CLI 重试采用同义检查。
- **fixture 反映生产。** 稳定性反例用 61 秒配置的立即重试快速验证“未到期零 Provider/零
  mutation”，不必真等；到期允许与重开用受控持久观察（改 `source_observed_at`，非 mtime）
  验证。可信状态反例保留真实且匹配的 occurrence/fingerprint，只把状态改为 unverified/legacy，
  再驱动真实 `worker run-next`。

### 实际受影响命令/结果

- `python3 scripts/check_governance.py` → PASS；`git diff --check` 干净；
  `python -m compileall -q mediaflow tests scripts` → OK。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_recovery_continuation test_metadata_correction_continuation test_task_persistence` → 98 tests OK。
- `... test_scanner test_resource_library_pipeline test_final_integration test_scan_retirement_stability test_organize_preparation` → 47 tests OK。
- `... test_automation_definition_execution test_automation_authorized_execution_matrix test_task_center_recovery_lineage` → 38 tests OK。
- `... test_task_retry test_scope_continuation test_processing_recovery_admission test_task_pause_resume` → 85 tests OK。
- `... test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 108 tests OK。
- 条件消费者组（task_persistence/sqlite_backup/sqlite_restore、direct_file_operations/
  manual_operations_contract/operations_task_center、automation_task_definition_preview/
  automation_definition_execution/automation_authorized_execution_matrix/configuration_organize、
  metadata_correction_continuation/recovery_batch）全部 OK。
- 追加直接受影响组：`test_classification_review`/`test_file_media_detail`/`test_metadata_correction`/
  `test_metadata_review`/`test_recognition_review`/`test_workflow_retry` → 45 OK；
  `test_operations_run_detail_log_isolation`/`test_resource_library_activation`/
  `test_media_library_activation`/`test_scan_retirement` → 58 OK；
  `test_restart_fault_boundary`/`test_queued_job_execution_boundary`/`test_operations_run_detail`/
  `test_operations_workspace`/`test_operations_run_inventory` → 105 OK；
  `test_operator_observability`/`test_processing_checkpoint`/`test_direct_file_transfers` → 126 OK；
  `test_media_discovery`/`test_scan_retirement_stability`/`test_automation_task_definition_preview` → 133 OK；
  `test_processing_worker_readiness`/`test_configuration_status`/`test_api_security` → 39 OK；
  `test_sqlite_backup`/`test_sqlite_restore`/`test_migration_rehearsal`/`test_upgrade_preflight` → 18 OK。
- 新增 `FreshCliSourceEvidenceAndStabilityTests`（9 cases）覆盖：fresh CLI 失败项已有 verified
  occurrence/fingerprint；替换来源恢复在 Provider 前拒绝；空/半缺失/legacy/unverified 拒绝；
  61 秒配置立即重试仍等待（0 Provider/零 mutation，含 `--execute`）；记录的区间真正到期后
  dry-run 继续分析；1 秒真实等待；默认 0 不等待；变化重置；真实 Worker 对 unverified/legacy
  原证据拒绝（0 Provider/零 mutation、无新项/结果）。
- `.venv/bin/ruff check mediaflow/ tests/` → All checks passed；
  `.venv/bin/ruff format --check mediaflow/ tests/` → 322 files already formatted。
- Web（cwd `web/`）：`npm run typecheck` 干净；`npm run test -- run` 指定 4 文件 → 93 passed。

### B 独立复现对照（同一 ignored 脚本，行为已翻转）

- `reproduce_long_stability_retry.py`：61 秒配置下首次 `organize --execute` 仍
  failed/unstable_source（0 Provider/0 目标）；立即 `tasks retry-failed --execute` 现为
  exit1、0 Provider、来源仍在、0 目标文件（旧结果 exit0/completed/success/实际 MOVE 已不再成立）。
- `reproduce_untrusted_worker_evidence.py`：unverified/legacy 两种状态现均 `worker_exit=1`、
  Provider 0、continuation failed、无新项/结果（旧结果 exit0/completed/verified 已不再成立）。
- `verify_fresh_task_evidence.py` / `verify_cli_short_stability.py` 保持通过（fresh 证据链与
  1 秒真实等待进入分析）。

### 已知失败/风险

- 仍待 B 独立确认 `tests/e2e/direct-files.python.spec.ts` 的既有 flaky（非本 Task 引入）。
- 稳定等待上限 `_MAX_STABILITY_WAIT_SECONDS=60s`：更长的配置区间不阻塞同步 CLI，而是记录
  等待项与 retry 下一步；B 可在真实入口确认该交互。
- wheel/隔离安装、生产 Docker、真实 SMB/OpenList/S3/TMDB 与 1536×1024/380×720 截图等
  T4 门禁仍 pending B；Developer 不跑全量/发布矩阵。
- RO-8 独立 Preview 完整退出未交付；本 Task 只清理其必要索引耦合。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/` 及开发 `.log` 文件。私有ignored配置不读取、不暂存。

## B Review Result

```text
Reviewed: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..52e13ce2c316aafa0bd1c2b424587572cee41d06
Decision: FIX REQUIRED — CLI-issued cursor cannot open its second page
Acceptance runs: previous two blockers independently fixed; Web 81 files / 1173 tests + quality/build OK
Task blockers: RO-7 CLI paging; live-files pagination proof must assert actual rows
Slice Required Outcomes / Surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

固定实现候选为上述Head，交接 `bf5155340cc270cefb347a80a7009b1787541cee` 相对候选仅改
`TASK.md`，执行输入一致。已读需求/完整旅程/架构及父Contract无变更；本轮核对真实指针、
修正diff，并继续原Task Base..Head的CLI/API/Worker/持久化/浏览及前端审查。已证实P1后
按workflow §6提前拒绝；不宣称全部diff或完整T4已经完成，不将环境/证据缺口交回Developer。

上轮两个阻塞本轮独立通过：61秒策略立即执行重试仍拒绝（0 Provider/零mutation），
真实Worker对unverified/legacy原证据也拒绝（无续作项/结果）。保留这些已证实修正；
本轮缺口是原RO-7实时文件列表的正常分页，继续同一Task，不重做已修好的处理管线。

### 当前必需修正与执行顺序

1. **先复现真实CLI分页。** 在新建隔离Managed Active/临时Local根准备多于limit的混合条目，
   用独立进程调用 `.venv/bin/mediaflow --config CONFIG files list --resource-library ID
   --path DIR --limit 1`，取真实Next cursor，再启动第二进程带 `--cursor CURSOR`。
   本轮实际第一页返回1项/hasNext，第二页却 `storage_browser_cursor_invalid`；数据库字节
   不变，故问题是续页不能完成，并非创建/升级/写库失败。不要只在同一对象里调用codec。
2. **修复生产密钥生命周期。** 定位 `final_cli._live_library_directory_document` 每次新建
   `RuntimeFilesBrowserService`，没有传入 `cursor_secret`；其下
   `StorageBrowserCursorCodec.__init__` 每次 `secrets.token_bytes(32)`。不同CLI调用的
   codec无法校验前一次签发的游标。复用现有codec/库级浏览及 `cursor_secret` 注入点，
   使同一正常配置/未过期作用域的游标在后续CLI进程可验证；不能只在测试harness里固定key。
3. **推荐落地路径：自动管理内部key，列表只读。** 优先复用项目已有的等义稳定内部key机制；
   如确无机制，在现有管理配置/正常服务初始化路径中原子create-if-absent生成内部随机key，
   存于受保护的内部配置元数据（不属于业务配置文档/Active内容），CLI通过只读helper读取并
   注入现有browser，API装配沿用同一机制。并发初始化不能覆盖key，正常重开/新CLI进程稳定；
   缺失/损坏明确拒绝并由正常受支持初始化/恢复处理，不在读取中偷偷生成一个一次性key。
   不引入密钥管理页面、普通用户手工配置/复制key、第二套配置权威/游标算法或外部服务。
   如有等义更小方案，用同样验收证明并解释，不降低现有边界。
4. **保持只读、安全与原精确作用域。** CLI helper继续 `mode=ro`，不为list构造可写配置/
   任务仓库，不创建/升级数据库、key文件、Task/观察/结果/许可。不用公开的revision digest、
   固定硬编码key或不验证签名来让分页“通过”；内部key不输出、不进入日志/便携配置导出。
   保留库种类/ID/root/目录/Active、TTL、篡改/跨作用域拒绝和Storage路径约束。不是改成
   一次列完整库、忽略cursor、每页重复首页或通过shell/API绕行生产列表。
5. **修正假阳性的原生证明。** `web/tests/e2e/live-files.python.spec.ts` 的分页测试当前
   仅断言 `second.code == 0`；CLI错误也返回0，故没有证明第二页存在。必须断言无游标错误、
   实际非空第二页、与首页条目不重叠，继续到尾页后与静态fixture全体条目逐项一致。
   在 `tests/test_file_index_retirement.py` 增加真正跨CLI进程的成功/失败回归；对两种库、
   同ID/同root、目录/配置变化、篡改/过期cursor、Unicode/空白/长名、空目录与末页覆盖。
   读取前后核对数据库schema/内容、Task/观察/许可/媒体不变；新增内部key的初始化检查与
   列表只读检查分开，不能把浏览写入key当作无副作用。harness继续走真实生产入口。
6. **先受影响验证再交接固定SHA。** 若增加内部元数据/初始化，更新必要TARGET架构事实及
   对应初始化/重开/备份/失败原子性测试，不改Slice边界、不宣称已验收CURRENT。
   原有稳定性/可信来源修正不回退；不改冻结43业务或展开RO-8。细节历史保留Git，当前Task
   只保留最新Developer交接与B结论。

### Developer 本次受影响验证

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser
# 实际修改配置初始化/内部元数据时追加
PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_management test_configuration_snapshot test_sqlite_backup test_sqlite_restore
# cwd web/；此页是新增/修改的直接受影响真实入口
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts
# 实际改动文件的ruff/eslint/prettier检查，及
git diff --check
```

Developer不跑全仓Python/Web/E2E或发布矩阵。B在新固定候选独立重做跨进程CLI多页、
作用域/过期/篡改拒绝及只读反例，审完原Base..新Head，并执行Required Tests原分配的
全部T4/真实入口/安装消费者/wheel/Docker/视觉门禁。匹配证据依workflow复用；执行输入
改变刷新分配验收，不机械重跑Final。

### 本轮实际证据与待办

本机ignored storage（非远程CI产物）：
`.git/validation-evidence/52e13ce2c316aafa0bd1c2b424587572cee41d06/task45.5/b-review/`。
`long-stability-retry.json` / `untrusted-worker-evidence.json` 为上轮修正通过的独立复现；
`cli-cursor.json` 为新P1的真实跨CLI进程反例。完整脚本/日志/说明在同目录。

- 全仓ruff format/check通过（386 files）；compileall、pip check、两份示例config validate
  通过，禁止依赖检索无匹配（exit1）。
- Web typecheck/lint/format、81 files /1173 tests及build通过；整组83.15秒（Vitest62.01秒）。
- 全Python unittest discover已启动；发现明确P1后主动SIGINT停止，exit130、250.90秒。
  原始输出/ResourceWarning/中断栈保留，未完成、无PASS/完整测试数声明，不能作为全量通过证据。
- 未启动完整E2E/real-Python浏览器、wheel/安装消费者/Docker/视觉验收；Docker daemon可用，
  这些继续由B在修正候选完成。Developer的direct-files Base/flaky归因仍未独立确认，不豁免。

测试/质量命令保守累计少于340秒（并行命令仍相加），本轮复核已超过680秒，低于用户50%
上限；实际起止与计算见同目录 `review-timing.json`。

本轮治理/whitespace通过；仅Task文档checkpoint，不含预存图片删除、未跟踪截图/.DS_Store/
ZIP/浏览器结果/开发日志；未读取私有配置、用户运行库或媒体。Slice/Roadmap/Progress、
45.4历史PASS与验证例外均不变。RO-7/RO-8仍未全部满足，未规划新Task或提交Closure Packet。
preflight main@bf5155340cc270cefb347a80a7009b1787541cee，workspace/Git可写。
此前交接/复核详细记录保留于 `9d64914:TASK.md` 与历史Git。
