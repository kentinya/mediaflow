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
Next Action: DEVELOPER FIXED DIRECT-FILE STABILITY AND DURABLE WAITING; B RE-REVIEWS AND FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
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

READY FOR B REVIEW at implementation HEAD `204441f70c0678e9b6526a54f6af8aac75b126f4`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`77dcb8e23003f729ea5b32785a329e0aade2f79a`). Same Task, Base / Goal / T4 unchanged.

### 本轮（B FIX REQUIRED）修正：直接文件入口稳定性 helper 参数与持久等待

**复现（先于修复）。** 复用 B 的隔离 Managed Active / LocalStorage / SQLite / 真实 CLI 与
functioning fake Provider 矩阵（displayRootPath 精确对应 ResourceLibrary root，Storage path
`Media/C/Correct.2024.mkv`）：单文件 `organize` 在 `stableSizeDurationSeconds=1` 与 `61` 时约
0.05s exit1、Provider 0 次、0 TaskItem/0 Result，输出 `'FileStabilityPolicy' object has no
attribute 'stability_policy'`；`--execute` 同样立即 exit1、零媒体变更。`stable-size=0` 单文件与
`stable-size=1` 目录入口作为成功对照 exit0。

**根因。** `MediaOrganizerService._observe_direct_source` 调用
`stability_wait_seconds(policy, entry, ...)`，但该共享 helper 的首参是 `ResourceLibrary`，
内部读取 `library.stability_policy`。直接入口传入了 `FileStabilityPolicy`，任何非零等待区间
都在 `remaining = ...` 抛 `AttributeError`，被 `process_file` 外层 `except Exception` 归为
普通失败，既没有真实等待也没有保存逐文件观察/结果。目录入口走 `_wait_seconds(library, ...)`
所以正常。

**修复（单点复用现有 helper，不新增稳定性引擎）。** `_observe_direct_source` 改传
`resource_library`；`stability_decision` 继续接收 policy。审查全部生产调用：
`media_discovery`（`library`）、`media_organizer._wait_seconds`（`library`）、
`_observe_direct_source`（现为 `resource_library`）均与 helper 首参一致。真实等待、
minimum-age / modified-threshold / stable-size 组合与变化重置语义不变。

**持久等待与恢复。** 长区间（>60s）不再同步阻塞：直接入口返回 `pending=True`，调用方
`_direct_waiting_item` 以 `begin_item` 保存该精确来源的 occurrence/fingerprint/verified
state/`source_observed_at` 并 `_complete` 写入逐文件 Result（`unstable_source`，
`effect_certainty=none`）；不再只出现在 SUMMARY。短区间真实 `time.sleep` 后二次 stat，未变
才进入 Provider/计划；期间变化则以第二次观察重置区间并保持等待。续跑/重试
（`resolve_source_evidence=False`）先经 `_persisted_source_refusal` 校验原证据，再经
`_stability_deadline_refusal` 以原固定 pin 下的策略和原 `source_observed_at` 判定；立即重试仍
等待，原区间真正满足且来源未变才继续。重开/重试不重放成功或未知效果。

### 实际受影响命令/结果（本轮）

- `python3 scripts/check_governance.py` → PASS；`git diff --check` 干净；
  `.venv/bin/python -m compileall -q mediaflow tests scripts` → OK。
- 修正后真实 CLI 矩阵（B 脚本，5 cases）：单文件 0 → exit0/provider1/1 item/1 dry_run Result；
  单文件 1 → exit0/elapsed≈1.13s/provider1/1 dry_run；单文件 61 → exit1/0.06s/provider0/
  1 failed item + 1 failed Result（`unstable_source`，durable evidence）；目录 1 → exit0/provider1；
  单文件 1 `--execute` → exit0/elapsed≈1.13s/provider1/1 success + 真实媒体变更。全部无
  `stability_policy` 错误。
- 新增 `tests/test_recovery_continuation.DirectFileStabilityTests`（7 cases）覆盖：0 立即分析且
  有证据、短区间真实 elapsed 后分析、长区间不阻塞且落库 waiting item/Result、minimum-age 未满足
  持久拒绝、等待中来源改变重置、记录区间驱动的 retry（立即仍等待→真实满足后分析、零重放）、
  `--execute` 真实等待后执行。
- `test_recovery_continuation test_task_persistence test_scope_continuation` → 138 OK（含新 7）。
- `test_final_integration test_workflow_retry test_resource_library_pipeline test_scanner test_scan_retirement_stability` → 43 OK。
- `test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser` → 40 OK（分页修正保留）。
- `test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize` → 116+121 OK。
- `test_task_center_recovery_lineage test_direct_file_operations test_manual_operations_contract test_operations_task_center` → 98 OK。
- `test_classification_review test_metadata_review test_metadata_correction test_recognition_review test_file_media_detail test_operations_run_detail_log_isolation` → 43 OK。
- `test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_recovery_batch` → 140 OK。
- `test_scan_retirement` → 9 OK；`test_sqlite_backup test_sqlite_restore` → 8 OK；
  `test_processing_checkpoint test_processing_worker_readiness test_processing_recovery_admission test_task_retry` → 48 OK。
- `.venv/bin/ruff check mediaflow/application/media_organizer.py tests/test_recovery_continuation.py` → All checks passed；
  `.venv/bin/ruff format --check` 同两文件 → already formatted。
- 本轮测试实际耗时保守合计约 110s，占本轮开发时间不足 30%；未跑全量/Web/E2E/wheel/Docker。

### 已知失败/风险

- `tests/e2e/direct-files.python.spec.ts` 既有 flaky 仍待 B 独立确认（非本 Task 引入）。
- 长区间等待上限 `_MAX_STABILITY_WAIT_SECONDS=60s` 的交互已由持久 waiting item + retry 证明，
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
Reviewed candidate: 77dcb8e23003f729ea5b32785a329e0aade2f79a
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..77dcb8e23003f729ea5b32785a329e0aade2f79a
Handoff: 333ff57ed6da34da66a6369bde6d2f940cad5fbd (TASK.md only; execution inputs identical)
Decision: FIX REQUIRED — direct-file organizing cannot complete configured stability
Previous CLI pagination blocker: independently fixed
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

本轮 main 固定上述候选；治理检查 PASS，workspace/Git 可写，预存图片删除、未跟踪截图、
日志、ZIP、浏览器结果和私有配置均保持。读毕角色/workflow、已提交 Contract/当前指针并
核对适用需求、完整列表/整理/恢复旅程及 CURRENT/TARGET；未修改 A-owned 边界。
继续原 Task Base..Head 审查，按 workflow §6 对已证实 P1 提前 FIX REQUIRED；不宣称
全部 diff 审完或完整 T4 通过。详细旧轮次保留 Git，不重开 Task45.4 的历史接受/例外。

### 已确认修正

真实独立 CLI 进程的首页游标能取得第二页，实际返回条目且数据库字节不变。新增跨进程
回归 5 cases 通过；本轮检查了持久 key 创建/只读注入和 E2E 第二页断言，原分页阻塞解除。
初始化发生在正常可写配置仓库初始化（例如服务启动/配置管理），并非 files list；CLI
读取仍以 mode=ro 打开。此处只确认相应修正，不代替尚未执行的完整初始化/备份/产物门禁。

### 当前阻塞：直接文件入口的稳定性 helper 参数不匹配

在真实 Managed Active / LocalStorage / SQLite / CLI 和可工作的 fake Metadata Provider 下，
使用实际存在的本地文件；displayRootPath 与库根精确对应，Storage path 为
`Media/C/Correct.2024.mkv`。对照结果：

| 入口 / 策略 | 实际结果 |
|---|---|
| 单文件 organize，stable-size=0 | exit0，Provider 1次，1 TaskItem / 1 dry_run Result |
| 单文件 organize，stable-size=1 | 约0.04秒 exit1，Provider 0次，0 TaskItem / 0 Result |
| 单文件 organize，stable-size=61 | 约0.04秒 exit1，Provider 0次，0 TaskItem / 0 Result |
| 目录 organize，stable-size=1 | 实际约1.12秒后 exit0，Provider 1次，1 dry_run Result |
| 单文件 organize --execute，stable-size=1 | 立即 exit1，Provider 0次，0 TaskItem / 0 Result，零媒体变更 |

失败输出均为 `'FileStabilityPolicy' object has no attribute 'stability_policy'`。
这不是正常等待：没有保存逐文件观察/结果，不能按该项重试或跨进程继续等待。
61秒立即拒绝本身不构成正确性证明，必须同时核对原因、TaskItem/Result 和观察证据。

### Developer 必需修正与顺序

1. **先按上述矩阵复现真实单文件入口。** 使用隔离 Active、现存文件和 functioning fake
   Provider；设置 displayRootPath 对应 ResourceLibrary root，核对最终 Storage path，
   不用重复拼接 root 的不存在路径。必须检查输出、逐文件持久记录及 Provider/媒体副作用，
   不能仅断言 exit1 或 Provider0。保留 stable-size=0 和目录入口作为成功对照。
2. **修正现有共享 helper 调用，勿新增稳定性引擎。**
   `MediaOrganizerService._observe_direct_source` 调用
   `stability_wait_seconds(policy, entry, ...)`，但该 helper 的第一个参数是
   `ResourceLibrary`，内部读取 `.stability_policy`。此处传入 `resource_library`，并审查
   同一 helper 的全部生产调用；`stability_decision` 才接收 policy，不要把两者混为一谈。
   保持真实等待、原 pin 下的 minimum-age / modified-threshold / stable-size 组合和变化重置。
3. **保证有界等待和可恢复持久结果。** 短区间真实等待后二次 stat，未变才进入 Provider/
   计划；超过同步上限时按既有 waiting 路径保存该精确来源的 occurrence/fingerprint/
   verified state/source_observed_at 与逐项结果、明确下一步。重开后立即重试仍等待，真实
   区间满足且来源未变后才继续；旧pin、源替换/丢证据/未知效果不得放宽或重绑定。
   检查 `_direct_waiting_item` 与 `_continuation_waiting_item` 实际落库结果，不让预观察错误
   只出现在 SUMMARY 且原 Task 无项。此项修正保留原任务/结果机制，不另建等待目录或队列。
4. **补直接入口的正向和恢复回归。** 在直接受影响测试中覆盖单文件 0 / 短非零 / 超过60秒
   的策略、minimum-age 或 modified-threshold 未满足、等待中来源改变、记录重开及 retry。
   至少一个短区间用真实 elapsed time 到成功，不 mock sleep 后谎称已证明稳定；长区间
   立即等待反例不需要同步等待61秒。补充可控时钟单测可以验证长区间截止逻辑，但与真实
   入口证据分开。断言恰当原因/持久观察/项/结果、Provider 调用时机、分析零 mutation、
   实际执行仍需既有权限，且成功/未知效果不重放。保留目录路径与本轮分页修正。
5. **受影响验证后提交固定候选。** 不修改 Slice/Roadmap/Progress，不展开 RO-8 或冻结43。
   修正继续 Task45.5，Base / Goal / Difficulty / T4 不变；交接简述真实结果与剩余风险。

### 本次 Developer 受影响验证

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_final_integration test_workflow_retry test_resource_library_pipeline test_scanner test_scan_retirement_stability
PYTHONPATH=tests .venv/bin/python -m unittest test_recovery_continuation test_task_persistence test_scope_continuation
# 新增直接文件稳定性回归及实际修改模块的直接消费者；按改动追加，不扩大为全仓
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
```

B 对新固定候选独立复现上述关键正反例，完成原 Task Base..Head 审查，并承担 Required
Tests 中已指定的完整 Python/Web/E2E、真实浏览器/视觉、wheel/安装消费者/Docker、安全与
初始化/重开/备份/失败原子性门禁。不得把本轮未执行门禁交回 Developer；匹配证据按
workflow 复用，执行输入改变刷新所分配验收，不机械重跑 Slice Final。

### 本轮实际验证与证据

本机稳定 ignored storage（非远程 CI）：
`.git/validation-evidence/77dcb8e23003f729ea5b32785a329e0aade2f79a/task45.5/b-review/`。

- `verify_cli_cursor.py` / `cli-cursor.json`：独立真实 CLI 两进程实际续页及只读通过。
- `cross-process-tests.log`：新增跨进程 5 tests OK，实际2.159秒（外层2.40秒）。
- `reproduce_direct_stability.py` / `direct-stability.json`：上述5组真实入口正反例，脚本断言
  确认当前缺陷和成功对照；不会因预期缺陷而把产品标为 PASS。
- 新 key reader 和 organizer 的 ruff check 通过；治理与 git diff --check 通过。
- 已证实 P1 后未启动完整 T4 / E2E / wheel / Docker；这些仍由 B 待修正候选完成。
  之前52候选的完整Web/部分Python结果只保留历史，不冒充当前执行输入的验收通过。
- 测试及质量命令累计保守上限15秒，远低于本轮复核时间的50%；精确起止与保守计算见
  同目录 `review-timing.json`。不靠空等拉长分母。

RO-7 未通过、RO-8 仍未实现，因此本轮不造新 Task、不提交 Closure Packet、不关闭 Slice。
