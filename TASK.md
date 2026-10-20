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
Next Action: DEVELOPER FIXES EXACT PREPARATION READ FAILURE / GET RECOVERY IN THIS TASK; B RETAINS FULL ACCEPTANCE
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
按本轮用户明确修订，不涉及旧版/A版升级兼容；只验fresh无索引、当前版本重开/重启和
当前版本失败原子性，不跑Base/旧版数据升级、历史字段兼容或升级回滚矩阵。
实际检查1536×1024及380×720截图、键盘、深链/返回/重连。日志/截图/脚本/产物digest保存于
`.git/validation-evidence/<candidate-sha>/task45.5/`，报告cwd/命令/结果/数量/skip/不可用。
必需环境不可用由B保留pending，不判完整T4 PASS，不冒充产品缺陷返工。

执行输入改变则刷新分配的验收；仅报告变更证明源码/测试/harness/依赖/配置/产物不变，
跑受影响文档检查。匹配结果可复用到Slice-final，缺失覆盖由B补齐，不机械重跑Final。

## Non-goals

- RO-8独立Preview完整退出尚未交付，本Task不因此宣称Slice ready。
- 旧版/A版升级、旧数据/字段兼容、跨版本迁移及升级回滚验证（用户本轮明确排除）；
  旧FileIndex迁移/双写/FileID兼容/同步恢复，无用户数据清空/删除。
- Slice43工作区重设计、MediaLibrary Organize、新Provider/引擎、附件-only自动恢复、
  未知效果重放、无限遍历或跨任务批量mutation。
- 改A-owned Slice/Roadmap/Progress边界、重开45.4或补记其历史全量PASS、自行关闭Slice。

## Developer Completion Report

READY FOR B REVIEW. Same Task, Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974` / Goal / High /
T4 unchanged; implementation HEAD is this checkpoint's SHA (recorded in the B handoff). B's latest
finding was **FIX REQUIRED — assigned Web lint / formatting gates fail on Task changes**. This
round fixes only that root cause (the effect state sync), its derived state and the missing
journey assertions; the previous exact-directory recovery fix remains in place.

### 先复现（本轮修复前）

B 在候选 `2a19b89154947184ba093c1f11b0fa164e8e08e3` 上实际执行 `npm run lint` 与
`npm run format:check`：前者在 `web/src/features/operations/OperationsLanding.tsx:1604` 报
`react-hooks/set-state-in-effect`；后者对同一生产文件及
`web/src/features/operations/OperationsInventory.test.tsx` 报 Prettier 不一致。本轮已在本机
复现同一 lint 报错（`setRemainingScope` 在 effect 中同步 setState）与 Prettier 警告，确认后再修。

### 根因与修正

原实现用 `useEffect` 把 `remainingPreparationQuery` 的服务器状态复制到 `remainingScope`、
`remainingDiscoveryId`、`remainingMessage`，既触发 `set-state-in-effect`，也依赖
`setRemainingDiscoveryId(null)` 停止轮询。修正只改前端状态推导，不新建生命周期/缓存：

- 删除该同步 effect。链接的精确 Preview、终结准备提示与“已受理即抑制”规则全部在渲染时
  从持久读取（`remainingPreparationQuery` 与 overview 的 durable recovery）加本地准入状态派生。
- 本地只保留显式用户事件的结果：`remainingMessageState`（确认被拒/响应未知/核对结果）
  与 `remainingAdmitted`（本页已受理的精确 `previewId` + `executionId`）。
- `effectiveRemainingScope` 仅在链接的 Preview 不等于已受理 Preview 时可确认；同一 discovery
  的缓存 GET 不再重新开放执行，其他运行的历史执行也不会被当成当前受理。
- `remainingDiscoveryId` 保留供精确读取，轮询继续由既有 `refetchInterval` 终止（有 preview
  或已终结即停），不靠 effect 清空 ID。读取/刷新/重连只 GET，绝不重发准备或执行 POST。
- 确认成功或核对为 known 时写入 `remainingAdmitted`，绑定该精确恢复上下文；提交失败/未知
  仍由用户事件回调优先显示。

### 新增/调整测试

`tests/...` 无改动。`OperationsInventory.test.tsx` 扩展 fixture 支持终结状态/nextAction，并新增：

- `surfaces a terminal remaining-scope preparation failure without a summary`：准备 `failed` 时显示
  持久 `nextAction`，不渲染“新计划摘要”，零 `/execute` POST。
- `does not reopen a confirmed summary when the overview carries its admitted execution`：overview 已带
  同一 `recoveryPreviewId` + `executionId` 时不再展示可确认摘要，且零 POST。
- 既有“同页准备+确认”“丢响应核对”“持久摘要恢复”旅程断言全部保留并通过。

### 实际受影响命令/结果

B 指定门禁（cwd `web/`）：

- `npx prettier --check src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx`
  → **All matched files use Prettier code style!**
- `npx eslint <两文件>` → **0 problems**（原 `set-state-in-effect` 已消除）
- `npm run typecheck` → **PASS**
- `npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunLifecycleControls.test.tsx`
  → **2 files, 40 tests passed**（OperationsInventory 27，其中 2 个为新增）
- `npm run build` → **PASS**（仅既有 bundle-size 警告）
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'a paused run continues only its remaining scope through the real Worker'`
  → **1 passed**（2.2s）

仓库根：`python3 scripts/check_governance.py` → **PASS**；`git diff --check` → 干净。

### 已知风险/边界

- 仅前端状态推导；未触碰后端、共享解析、pin/锁/准入/非重放语义。分析仍零 mutation，
  读取/刷新/重连只 GET。
- 完整 Python/Web/E2E/视觉、wheel、生产 Docker 仍由 B 的 T4 门禁执行，本轮未运行也未声称通过。
  本机无远程 CI。
- 预存修改保留且不纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
  `docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
  `output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
  私有 ignored 配置不读取、不暂存。RO-8 未交付，本 Task 不宣称 Slice ready，也不自判 PASS。
- 本轮测试执行（typecheck/eslint/prettier/2 组 unit/build/E2E）合计约 5–6 分钟，占本开发轮次
  总时长约 22%，低于 30% 上限。

## B Review Result

```text
Reviewed candidate: 39f132ba0b698d18bedba1666871704efcad28f9
Product implementation: 7381a1ff9d917cbe5a39bf57e89b2ca52be4d409
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..39f132ba0b698d18bedba1666871704efcad28f9
Decision: FIX REQUIRED — remaining-scope preparation read failure has no truthful GET recovery
Previous Web lint / formatting blocker: FIXED; full assigned checks pass on this candidate
Slice outcomes/surfaces all satisfied: NO — RO-7 acceptance / RO-8 implementation pending
Next: DEVELOPER FIXES THIS TASK; B RETAINS REMAINING FULL ACCEPTANCE
```

### 独立复现的 P1 与修正

真实 production build + 隔离 Python/API/SQLite fixture，不改产品代码、不手改数据库，不使用用户媒体：

1. 以具备权限的操作者打开真实暂停运行 Authority，明确点击“在当前界面生成剩余范围摘要”。
   后端成功持久准入一个零变更 discovery，整个复现只有这一次 POST。
2. 只拦截该 discovery 的 GET 返回503。`fetchOrganizeDiscovery` 正确返回失败结果，但
   `OperationsLanding.tsx:1574–1591` 将失败等同于没有 preparation，并停止轮询；
   `:1621–1628` 随后不显示任何准备状态/读取失败/下一步。面板仍显示原生成摘要按钮。
3. 去掉故障，点击任务中心实际 Refresh，再等待一个轮询区间：仍只有最初一次 discovery GET，
   没有恢复读取该已受理准备。独立认证 GET 同一ID返回200/queued/zeroMutation=true；
   因而不是准备未受理、权限拒绝或服务持续故障，而是同页缺少明确的读取失败恢复路径。
   未执行媒体，不声称产生媒体损坏。不得要求操作者猜测再次点击生成按钮来重复POST。

这是既定 Goal/AC 中“失败→恢复”和 RO-3/RO-5 保留旅程的缺口，不是新功能或可选提示。
在**同一45.5**修正，Base/Goal/High/T4不变：

1. 从精确 remainingPreparationQuery 的读取状态派生 loading、已受理进行中和读取失败；
   不把transport/503/403/401/畸形响应当空态或完成，不抹去已受理ID/已知持久状态，
   不伪称后台工作失败或Storage发生/未发生本次执行效果。
2. 同页显示故障阶段、准备已经受理（不是执行已受理）、最后已知状态/未知新状态和下一步；
   提供明确的“重新读取本次准备”动作，仅refetch同一ID的GET。恢复成功后继续既有轮询/
   同页精确摘要，失败时保留可读原因；鉴权失效沿用共享认证恢复。不要新增队列、生命周期、
   schema或缓存，不靠重复POST、自动mutation重试或effect复制状态修复。
3. 保留精确摘要版本/就绪子集/覆盖清理授权/未知确认先核对/受理后抑制重复执行。
   扩展现有旅程测试覆盖首次GET失败及轮询中失败→故障解除→明确GET恢复→同一摘要；
   断言准备POST始终1次，确认前execute POST为0，失败不显示为“未创建工作”或空态。
   不能弱化已有断言、扩大超时、关闭lint规则。
4. Developer运行下面受影响验证，提交连贯checkpoint及实际结果；全量仍由B负责。

```bash
# cwd web/
npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx
npx prettier --check src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx
npm run typecheck
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunLifecycleControls.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'a mutation-authorized paused run without live authority is refused natively'
# cwd repository root
python3 scripts/check_governance.py
git diff --check
```

若修改直接消费者，追加其精确测试/changed-file检查；新失败恢复用例可加入同一real-Python
spec并运行该用例。不要让Developer跑全Python/Web/E2E、wheel或Docker矩阵。

### 本轮实际结果与证据

本地稳定ignored证据根：
`.git/validation-evidence/39f132ba0b698d18bedba1666871704efcad28f9/task45.5/b-review/`。
独立复现脚本/命令/时间/输出为 `remaining-read-proof.cjs`、
`remaining-read-independent.log/json`、`remaining-read-proof.json` 和
`remaining-read-503.png`；脚本exit0表示反例成立，不表示产品通过。

- governance与Task Base..Head whitespace通过；全仓ruff check/format通过（389 files）。
- 复用B此前完整Python：**2725 tests，OK，skipped=7，264.772s**；精确空白目录完整执行/
  重开及缺失时拒绝反例复用。`reuse-inputs.json`/`prior-input-diff.txt`证明349ca47→候选
  只变TASK及两个Web文件，非Web/非TASK tracked tree hash一致；本轮无依赖/配置安装变化。
  不复用/恢复已被用户排除的旧版本升级调查结论。
- cwd web/ 实际：lint、format:check、typecheck、build通过；unit **81 files /1177 tests PASS**；
  完整普通E2E **240 PASS**。首个unit运行未捕获最终退出结果，不计PASS，计入测试用时；
  第二次有明确1177/exit0结果。以上完整控制台证据在本轮工具会话，当前目录README仅摘要，
  未伪称已有逐条raw log文件或远程CI可访问。
- real-Python合并命令出现共享可变fixture跨spec干扰：11 passed、4 failed、1 interrupted、
  32 did not run（51.9s），原始 `real-python.log` 保留，不作为产品失败或完整通过。
  独立新harness首个inventory用例通过；随后单独完整inventory **41 PASS，87.390s**。
  独立visual **2 PASS，11.093s**，截图已立即复制至`visual/`；检查窄屏和本P1截图，
  其余截图尚未逐张完成视觉验收，不声称完整visual PASS。live-files在合并运行中5项通过，
  独立完整刷新尚未执行。
- 发现上述真实P1后提前FIX REQUIRED。完整132文件Base..Head内容审查尚未结束；Unicode
  原生、其余共享门禁、wheel/离开源码安装消费者、固定候选Docker/常驻Worker/安全证明
  均pending，由B在修正候选继续；不把缺证据当产品错误返给Developer。
- 更改执行输入后刷新相应Web/原生/产物验收；Python及其他匹配证据需重新核对后复用。
  real-Python各共享可变spec必须独立harness运行，不机械复制已证实会互扰的合并命令，
  不删除断言/加重试来掩盖。匹配最终证据可满足Slice Final，不机械重跑。

### 范围与时间

用户明确排除旧版/A版升级兼容：不跑Base/旧数据库升级、历史来源字段兼容及升级回滚矩阵，
不要求compatibility decoder，不自动清空媒体/运行库。只验fresh、当前版本重开/重启/
失败原子性与来源/pin/权限/非重放。A-owned Slice/Roadmap/Progress和冻结43未修改。
RO-8尚未交付；本Task未PASS，不规划下个Task、不提交Closure Packet、不宣称Slice ready。

本轮测试含首个未捕获unit、重复unit、失败合并浏览器及独立复现；前半段部分命令只有
会话时间，非秒级完整计时。保守约8–10分钟，复核自约14:17–14:19至本轮收尾，已超过
30分钟；按10分钟/30分钟保守计不超过33.4%，低于用户50%。未用等待凑比例。
预存21条用户dirty/untracked记录保持，私有配置不读取/暂存。更详细过程保留Git/ignored证据。
