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
Next Action: DEVELOPER PERSISTS SOURCE REFUSALS AND TRUTHFUL TASK OUTCOMES IN THE SAME TASK; B RETAINS FULL ACCEPTANCE
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

READY FOR B REVIEW at implementation HEAD `8732c2588cda76646a72dfbea60bd72abc93e935`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`204441f70c0678e9b6526a54f6af8aac75b126f4`). Same Task, Base / Goal / T4 unchanged.

### 本轮（B 第二次 FIX REQUIRED）修正：安全拒绝必须持久为真实失败

**复现（先于修复）。** 直接运行 B 的 `reproduce_refusal_completion.py`（replaced / missing /
unverified 三例）与 `reproduce_discovery_refusal.py`：拒绝本身正确（exit1、Provider0、零媒体变更、
原指纹保留），但重开数据库后 Task 均为 `completed / total_items=0 / failed_items=0`，
无 TaskItem / Result，`tasks show` 只显示 `Total: 0`。脚本断言旧缺陷（exit0 表示复现成功）。

**根因。** `process_file` 的 `resolve_source_evidence=False` 分支在 `begin_item` 之前命中
`_persisted_source_refusal` 并以 `_failed(..., tracked_item=None, stage="storage")` 返回；
`_complete` 因没有 tracked item 不发布任何 TaskItem/Result，`PersistentTaskCoordinator.finish`
读取空持久 items 且无 scan_errors，于是把该次尝试汇总成 Completed/0。首次目录整理在发现与处理
之间的来源竞态走同一 `except Exception` → `_failed(tracked_item=None)` 路径，同样假成功。

**修复（复用既有持久完成路径，不新增结果库）。**

1. `_persisted_source_refusal` 返回 `FailureExplanation` 而非裸字符串，按真实原因区分
   `source_changed` / `source_missing` / `source_unverified` / `storage_failure`（含
   `StorageErrorCode.NOT_FOUND` 与连接类错误），不再把来源缺失/连接故障混为泛化 storage。
2. 新增 `_refused_source_item`：以原 occurrence/fingerprint/verified state/`source_observed_at`
   调用既有 `begin_item`，再走既有 `_failed`/`_complete`/`complete_item` 发布该次尝试的逐文件
   TaskItem + Result；不重建旧可信证据、不覆盖成功兄弟、不授予分析/执行权、零 Provider、零 mutation。
3. `process_file` 的通用 `except Exception`：当 `tracked_item is None` 且不是
   `TaskLockError/TaskPauseRequested/TaskClaimLost`（这些已在 `begin_item` 内发布自身拒绝）时，
   同样经 `_refused_source_item` 发布，堵住首次目录整理的竞态假成功。
4. `_failed` 对已分类的 `FailureExplanation` 一律持久化其 envelope（CLI 路径也如此），
   `_failure_message` 兼容 `FailureExplanation`。
5. `ErrorCategory` 增加 `source_changed` / `source_missing` / `source_unverified`；
   `failure_explanation` 增加同类别 message/next action 与文本归类；`classify_failure` 直传
   已构造的 `FailureExplanation`。
6. `tasks show` 用 `decode_failure_explanation` 渲染 category/message/next action，不再打印原始
   `mediaflow-failure-v1:` token。
7. Web `ProblemFilePanel` 增加三个类别的中文原因/下一步；不改动任何既有 category 文案。

**汇总语义。** 拒绝项现在进入 `failed` counts，Task 汇总为 FAILED；真正的空目录/合法零项仍为
Completed/0（未改 `finish` 聚合逻辑，也不伪造 scan error）。

### 实际受影响命令/结果（本轮）

- 修复前：B 两个复现脚本分别命中旧断言（Task completed/0、无 item/result）。修复后：
  `reproduce_refusal_completion.py` 三例均 `failed / total 1 / failed 1 / items 1 / results 1 / provider 0 / target 0 / fp_unchanged`；
  `reproduce_discovery_refusal.py` 为 `failed / 1 / 1 / items 1 / results 1 / source_changed / provider 0 / target 0 / 源内容保留`。
- 新增 `tests/test_recovery_continuation.RefusedSourceCompletionTests`（5 cases）：replaced→
  `source_changed`、missing→`source_missing`、unverified→`source_unverified`、Storage 连接故障→
  `storage_failure`（retry-safe，区别于来源变化）、首次目录竞态→`source_changed`；每例断言重开
  数据库后 status/counts/error、TaskItem、Result、effect_certainty、原证据保留、`tasks show`
  解码与零 Provider/零 mutation。
- `test_recovery_continuation test_task_persistence test_scope_continuation test_final_integration test_workflow_retry test_resource_library_pipeline` → 160 OK。
- `test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser` → 40 OK。
- `test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 369 OK。
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_processing_checkpoint test_operations_run_detail test_operations_task_center test_direct_file_operations test_manual_operations_contract test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_recovery_batch` → 305 OK。
- `test_automation_definition_execution test_automation_authorized_execution_matrix` → 33 OK；
  `test_processing_checkpoint test_operations_run_detail test_operations_task_center test_task_center_recovery_lineage` → 74 OK；
  `test_direct_file_transfers test_operations_run_detail` → 134 OK；
  `test_organizer test_conflict_resolution test_organizer_rollback test_organizer_mutation_authority test_direct_file_operations test_media_library_direct_commands` → 147 OK；
  `test_processing_recovery_admission test_task_retry test_processing_worker_readiness test_scan_retirement test_scope_continuation test_configuration_snapshot` → 148 OK；
  `test_task_pause_resume test_scan_retirement test_sqlite_backup test_sqlite_restore` → 27 OK；
  `test_metadata_correction test_recognition_review test_classification_review test_metadata_review test_file_media_detail` → 36 OK。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` 干净；
  `.venv/bin/python -m compileall -q mediaflow tests scripts` → OK。
- `.venv/bin/ruff check` / `ruff format --check` 覆盖
  `failure_explanation.py media_organizer.py domain/processing_checkpoint.py final_cli.py tests/test_recovery_continuation.py` → passed / formatted。
- Web：`npm run typecheck` 通过；`npm run test -- run OperationsInventory.test.tsx OperationsRouter.test.tsx run-detail.test.ts` → 82 passed；
  `npx prettier --check` / `npx eslint` 修改文件通过。
- 本轮测试实际耗时保守合计约 180s，占本轮开发时间不足 30%；未跑全量/Web build/E2E/wheel/Docker。

### 已知失败/风险

- `tests/e2e/direct-files.python.spec.ts` 既有 flaky 仍待 B 独立确认（非本 Task 引入）。
- 长区间等待上限 `_MAX_STABILITY_WAIT_SECONDS=60s` 的持久 waiting item + retry 交互已由单元测试覆盖，
  真实入口 61s 反例与恢复仍待 B 在真实浏览器/Worker 路径确认。
- wheel/隔离安装、生产 Docker、真实 SMB/OpenList/S3/TMDB 与 1536×1024/380×720 截图等
  T4 门禁仍 pending B；Developer 不跑全量/发布矩阵。
- RO-8 独立 Preview 完整退出未交付；本 Task 只清理其必要索引耦合。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/` 及开发 `.log` 文件。私有ignored配置不读取、不暂存。

## B Review Result

```text
Reviewed candidate: 204441f70c0678e9b6526a54f6af8aac75b126f4
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..204441f70c0678e9b6526a54f6af8aac75b126f4
Handoff: 3e1bbdaef87e9ca559d8be9ac72e9721eee79c56 (TASK.md only; execution inputs identical)
Decision: FIX REQUIRED — refused sources are persisted as Completed / 0 items / 0 failures
Previous direct-file stability blocker: independently fixed, including real elapsed execution
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

本轮 main 固定上述候选，治理 PASS，workspace/Git 可写；预存图片删除、未跟踪截图、
日志、ZIP、浏览器结果和私有配置均保持。读毕 AGENTS/workflow/B experience、已提交
Contract/Task/当前指针，并核对适用需求、列表/整理/恢复完整旅程及 CURRENT/TARGET。
本次继续原 Base..Head 的浏览、源证据、恢复、扫描/批量、Automation、API、持久化与前端
审查；发现确定 P1 后按 workflow §6 提前拒绝，不宣称全部 diff 或完整 T4 已完成。

### 上轮修正已独立通过

真实 CLI / Active / LocalStorage / SQLite / functioning fake Provider：单文件稳定期0立即
分析成功；1秒真实等待后分析成功；61秒立即保存1个可信等待 TaskItem 和1个 Result，
Provider0；目录1秒成功；单文件1秒 --execute 真实等待后实际 Move 成功。未再出现
helper 参数错误。B 脚本断言实际结果/时间/持久状态与临时媒体效果，不复用旧失败期待。

### 当前 P1：安全拒绝没有落入逐文件结果，任务反而显示完成

四组独立真实入口反例均 exit1、Provider0、零媒体变更，但数据库重开后的 Task 均为
`completed / total_items=0 / failed_items=0 / error=None`，无 TaskItem / Result。
`tasks show <new-task>` 也明确打印 `Status: completed`、`Total: 0`。

| 真实触发 | CLI 当次输出 | 持久结果缺口 |
|---|---|---|
| 单文件61秒等待落库后，替换该文件，再 retry-failed --execute | reviewed source changed/replaced | 新尝试 Completed0，无拒绝原因 |
| 同样等待后删除源文件，再重试 | reviewed source no longer present | 同上 |
| 同样等待后模拟原证据信任状态丢失，再重试 | cannot prove original occurrence | 同上；未把 live stat 冒充旧证据 |
| 新目录 organize --execute；真实 list 返回观察后、处理前替换源文件 | reviewed source changed/replaced | 原始整理任务直接 Completed0 |

最后一组只在临时 fixture 对真实 LocalStorage.list 返回与消费者处理之间注入外部写入，
不 mock 校验结果或 Provider。证明同一缺陷也影响普通首次整理，不只是历史重试。
安全拒绝本身正确，禁止恢复成“继续执行”；要修的是已受理尝试的逐文件失败证据和真实
汇总状态。CLI 一次输出、普通访问/操作日志不能替代重连/重开后可查看的正式结果。

### Developer 必需修正与执行顺序

1. **先复现并断言数据库重开后的结果。** 使用上表隔离 fixture；保留原等待 Task 的
   精确 evidence/pin，分别替换/删除/丢失信任后重试，并覆盖发现与处理之间变化的首次
   目录整理。必须同时看 exit / 输出、Task status / counts / error、TaskItem、Result、
   检查点及已知效果，不只断言 exit1、Provider0、源未变或原指纹没被覆盖。
2. **让早期拒绝沿现有持久完成路径发布。** 定位
   `MediaOrganizerService.process_file` 的 `resolve_source_evidence=False` 分支：
   `_persisted_source_refusal` 拒绝后调用 `_failed(..., tracked_item=None, stage="storage")`，
   此时尚未 `begin_item`，故 `_complete` 不会发布 TaskItem/Result。
   在既有 Task/coordinator 职责内记录该新尝试的精确受理项和拒绝结果，复用现有
   `_complete` / `complete_item` / checkpoint / evidence 机制；不要另建结果库或索引。
   若需调整开始记录的时机，保持 pin、库/路径范围、锁/claim/fence、去重及已终结项保护；
   不把其他 owner 的进行中项当作本次失败覆盖。
3. **持久保留原证据与可执行的补正说明。** 拒绝记录沿用原受理的来源、occurrence /
   fingerprint / trust state / observation time 与 pin；不以当前文件重建旧可信证据，
   不覆盖原任务/成功兄弟/未知效果，也不因为保存失败而重放媒体。分别解释来源已变化、
   已缺失、不可验证和真实 Storage 连接故障，记录未执行/已知零效果。
   变化/不可验证应引导回当前 Files 重新选择并准备新摘要；缺失说明恢复原来源或重新选择；
   连接故障按现有修复/安全重验流程。不要把上述全部归成泛化 storage_failure + Retry，
   不授予自动分析/执行或放松来源比较。使用既有 bounded failure 投影/共享语义。
4. **修正汇总的假成功，并保留真实零项语义。**
   `PersistentTaskCoordinator.finish` 当前只从持久 items / scan_errors 决定状态，遗漏
   SUMMARY 中已拒绝却未持久化的 item。修复主路径后，核对拒绝项和 failed counts 一致；
   审查同类 `_failed` 提前返回，避免再制造没有正式记录的失败。
   只把 aggregate 改成 FAILED、仍不保存逐文件原因不满足本 Task；也不能把所有正常空目录/
   合法零结果都改失败，或伪造 scan error 掩盖来源校验阶段。
5. **直接消费者与交接。** 覆盖单文件 retry/resume、目录/批量新发现到处理、实际调用同一
   分支的 Worker/定义基础消费者。按必要范围修改，不展开 RO-8 或冻结43。
   提交固定候选，保留 Task45.5 / Base / Goal / High / T4，不新造修正 Task。

### Developer 本次受影响验证

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_recovery_continuation test_task_persistence test_scope_continuation test_final_integration test_workflow_retry test_resource_library_pipeline
# 若修改共享失败说明/投影或 coordinator，追加其直接消费者
PYTHONPATH=tests .venv/bin/python -m unittest test_processing_checkpoint test_operations_run_detail test_operations_task_center test_task_center_recovery_lineage
# 若生产修改实际影响定义执行/Worker，追加对应组；不扩成全仓
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_definition_execution test_automation_authorized_execution_matrix
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
```

新增/加强回归须核对持久失败和下一步（包括 reopen / tasks show / 对应任务详情的实际投影），
保留未变正常成功、真正空目录零项、立即等待与区间满足、混合成功/失败及未知效果非重放。
没有 Web 产品修改时不要求 Developer 跑全仓 Web；有实际投影变更则只追加直接受影响测试。
B 对修正候选重做关键正反例、原 Base..Head 审查，继续承担 Required Tests 原分配的完整
T4 / Python / Web / E2E / 真实浏览器与视觉 / wheel / 安装消费者 / Docker / 安全与持久化
门禁；未跑或中断不算 PASS，不把全量交回 Developer。按 workflow 复用匹配证据，不机械
重跑 Slice Final，也不拿旧执行输入的结果充当本候选全量通过。

### 本轮实际验证与证据

本机稳定 ignored storage（非远程 CI）：
`.git/validation-evidence/204441f70c0678e9b6526a54f6af8aac75b126f4/task45.5/b-review/`。

- `verify_direct_stability.py` / `direct-stability.json`：上轮修正的5组真实成功/等待/执行对照。
- `reproduce_refusal_completion.py` / `refusal-completion.json`：源替换、缺失、unverified 的
  真实 CLI 重试 + 重开数据库 + tasks show；脚本成功表示已重现缺陷，非产品 PASS。
- `reproduce_discovery_refusal.py` / `discovery-refusal.json`：首次目录整理的来源竞态反例。
- 全仓 ruff format / check 通过；compileall、pip check、两份示例 config validate 通过；
  禁止依赖检索无匹配（exit1）。原始日志/实际命令见同目录 README。
- 全 Python unittest discover 已启动；发现确定 P1 后 SIGINT 终止已核实的该子进程，
  外层181.93秒、exit130，原始输出/ResourceWarning/中断栈保留。无完整测试数/PASS声明。
  未启动 Web/E2E/wheel/Docker/视觉门禁，仍 pending B；Docker daemon29.5.2可用。
- 测试/质量命令累计保守上限195秒，起止和比例见同目录 review-timing.json；本轮收尾
  必须低于用户50%上限，不靠空等增加分母。

本轮只提交 Task 审查/执行指导，不含预存用户文件变化；Slice/Roadmap/Progress、45.4
历史 PASS/例外均不变。RO-7 尚未通过、RO-8 未实现，不规划下个 Task 或提交 Closure Packet。
