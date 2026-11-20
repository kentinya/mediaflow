# Task PATCH-20261120-1 — 修复后续季剧集匹配与逐文件元数据修正

Next Action: B PERFORMS T4 ACCEPTANCE ON THE PATCH-20261120-1 CANDIDATE

用户于 2026-11-20 授权激活独立 Task。B 已核实上一轮修正并通过真实浏览器发现任务中心表单阻塞。依据为 `REQ-META-005/008`、`REQ-RECOVERY-005`、`V2-OPS-007/016`。
[独立缺陷流程](docs/development-workflow.md#31-independent-minor-bugs) · [现有逐项恢复流程](docs/product-experience.md#tasks-results-and-per-item-recovery) · [上一独立修复的 B 验收](https://github.com/kentinya/mediaflow/blob/c8039f1f3d7bdfdb7fd927c75f99df0cb8a9e523/TASK.md#patch-20261119-2--b-验收-pass)

```text
Task ID: PATCH-20261120-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: FIX REQUIRED
Task Base: 660fecb6637ed36910493c65b94b0b8c3ced7681
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-20
```

### 目标与基线

用户从资源库文件页选中《黑袍纠察队》S04E01–E08 并整理时，应得到 2019 年作品对应剧集的待确认摘要。
如果当前文件的候选仍有歧义，或找不到包含所需季集的作品，用户在文件页整理对话框和任务中心都能处理该文件的元数据问题，
保存决定并重新分析，再确认该文件的新摘要。自动整理复用同一识别和任务中心恢复规则。

基线模拟 TMDB 对两部同名剧按首播年过滤。八个含 `2024` 的 S04 文件都只命中错误候选，查第四季返回 404 后全部失败，
没有人工修正阻塞项。同一个场景把查询年改为 `2019` 后，八集均到达待确认摘要。返回 200 但缺集同样没有可用修正入口。
根因在 `TMDBProvider._search` 将 `ParseResult.year` 用作 `first_air_date_year`、匹配器按整剧年份计分，
以及 `MetadataIdentificationService.identify` 将季查询的 `NOT_FOUND` 归到 `PROVIDER_ERROR`，现有流程只为搜索 `NOT_FOUND` 发布修正。
人工选定 Provider ID 的识别分支目前也只查整剧详情。

### 实施步骤

1. 在共享识别层区分解析年份与人工编辑的搜索条件。自动识别已有明确季集的 S02+ 文件时，保留解析年份作证据，
   搜索、候选筛选和评分均不按该年份排除首播年份不同的剧集。复用标题证据和现有候选、分页、请求预算，
   用所需季及全部集数验证可比候选。具备足够标题证据且仅一个可比候选通过完整验证时允许自动匹配，
   多个通过或证据不足时交给现有候选确认。排除已证实季集不符的候选，对尚未验证的可比候选保留人工决定并在重新分析时验证。
   电影、首季及未明确季集的现有搜索规则继续适用。
2. 在季集查询边界识别对象不存在与缺集，保留可读的作品与季集不匹配原因。将这类结果和搜索无结果接入同一个元数据修正入口，
   同步文件页分析、共享整理、持久化决定与任务证据。认证、限流、超时、网络异常、无效响应等继续采用各自的技术失败和重试语义。
3. 人工编辑标题和年份，或选定候选／输入 Provider ID 后，使用同一 Task 固定的 Provider、策略和当前文件季集重新分析。
   显式年份按实际输入搜索，清空年时不限年份。对季集不符的人工选择，在同一文件恢复可编辑的修正状态，
   显示失败原因并保留已有决定审计。复用同项决定记录与现有版本检查，原子发布等待状态和修正记录。
   通过验证后使用该项已验证的作品和季集生成新摘要，沿用现有显式执行确认。

### 验收标准

- [ ] 真实 Files API 和 Worker 处理八个 `黑袍纠察队.2024.S04E01–E08` 模拟文件时，两部同名剧都进入有界判定。
      2024 候选的 S04 404、2019 候选有 E01–E08，八项均使用 2019 年作品，摘要包含各自的季集和匹配依据。
      交换候选顺序结论一致。同名剧均有对应集数或预算耗尽时，需要人工确认。
- [ ] 所有可比候选均证实季集不符（季 404 或季存在但缺任一请求集），以及搜索无结果时，均有逐文件「修正作品搜索」。
      Files 对话框和任务中心显示同一 TaskItem 的原因和决定。
      同批可确认的文件可独立继续。真正的 Provider 技术故障保留技术原因和原有处理语义。
- [ ] 用户可改为 `2019`、清空年份、选择候选或按现有权限指定 Provider ID。错误 TV ID 无法生成可执行摘要，纠正后同一项可进入确认。
      刷新可读回决定和状态，过期版本不能覆盖新决定。电影同名年份匹配、手填年份及显式清空、RecognitionType 和固定配置语义保持。
- [ ] 搜索、保存和重新分析均为零 Storage 变更，只有显式确认的新摘要允许执行。执行范围只包含确认的文件，已完成或效果不确定的兄弟项不重放。
      已结束的历史失败如需重新处理，通过文件页发起新的整理，原任务和结果按原事实展示。

### 测试计划

**Developer — 新增／修改与直接受影响测试**

- 从仓库根目录运行 `.venv/bin/python -m unittest tests.test_media_parser tests.test_metadata tests.test_metadata_resolution tests.test_metadata_correction tests.test_task_item_metadata_search tests.test_manual_task_engine tests.test_automation_entrance_recovery`。
  在这些模块中补齐同名剧、季集验证、业务结果与技术故障、请求预算、修正后再失败、按不同入口重分析和混合批次的回归。
- 从 `web/` 运行 `npm run test -- run src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/RunDetailTabs.test.tsx`。
  验证两个入口的原因、已有操作和保存后新摘要。运行 `git diff --check` 及改动文件对应的 Ruff 或 Web 静态检查。

**B — 独立验收与完整回归**

- 在冻结候选上独立复现八集与反例，检查 Files 和自动整理逐项状态、同一 Task 恢复、权限和固定配置、等待记录写入的原子性、
  过期决定拒绝及明确效果边界。在临时 SQLite、本地 Storage、模拟 Provider 和构建产物上补跑真实浏览器验收。
- 从 `web/` 构建后运行 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/metadata-search-year.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts`。
  在现有原生测试和 harness 中加入后续季用例，验证 Files 和任务中心的修正操作、刷新及确认前零变更。
  按[共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)运行全量回归和适用的封装及安全检查。

### 边界

范围限于现有 TV 匹配、元数据决定与整理恢复路径。沿用现有 Provider 配置、API 路由、任务状态和 SQLite 结构。
既有文件页和任务中心承接本次恢复，已验收的 Slice 作为参考。


## Developer Completion Report

```text
Task Base: 660fecb6637ed36910493c65b94b0b8c3ced7681
Implementation Candidate: bf3f81c2d59f31c96fa7cc1d7ad490a0f28501c1
Branch: main
Status: READY FOR B REVIEW
```

**实施结果**

- 自动识别显式季集的 S02+ 电视文件时，解析年份只保留为评分证据，Provider 搜索不发送
  `first_air_date_year`，候选筛选与评分不按首播年排除。标题证据达到确认阈值后，用所需季和全部
  集数逐项验证可比候选；仅一个通过时自动匹配，多个通过、请求预算未能完成验证或未验证候选
  保留时进入现有候选确认。已证实季不存在或缺集的候选不进入候选选择，并在任务证据中保留原因。
- 季集查询边界把季/集不存在归为作品与文件季集不匹配，不再误报为 Provider 技术故障；搜索无结果
  和该不匹配都进入现有逐文件元数据修正。认证、限流、超时、网络和无效响应仍保持原技术失败与
  重试语义。电影、首季及未明确季集的搜索规则未改。
- 人工编辑标题/年份、清空年份、候选选择和直接 Provider ID 都使用 Task 固定 Provider、策略和
  当前文件季集重新分析。直接 ID 与候选选择现在会验证季集；失败后原子地恢复同一修正记录的
  待处理状态、同一 TaskItem 等待状态和新原因，保留既有决定审计。多个已解决元数据决定按
  `updated_at` 只消费最新一项，避免旧候选覆盖后一次修正。
- Files 对话框与任务中心共用恢复投影，新增显示上次修正未通过验证的原因；`outcome` 既有字段
  承载状态与可读原因，无 SQLite 结构变更。搜索、保存和重新分析保持零 Storage 变更，确认前
  不执行整理。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选工作树）**

```text
python3 scripts/check_governance.py                                   -> PASS
git diff --check                                                      -> clean
.venv/bin/ruff format --check mediaflow + changed tests               -> 164 files formatted
.venv/bin/ruff check mediaflow + changed tests                        -> All checks passed
.venv/bin/python -m compileall -q mediaflow tests                     -> OK
.venv/bin/python -m unittest <12 affected/integration modules>        -> 297 tests OK (10.70s)
web: npm run typecheck / lint / format:check                          -> OK
web: npm run test -- run TaskItemRecoveryPanel, ManualOrganizeDialog,
     RunDetailTabs                                                     -> 3 files, 71 tests OK (19.93s)
```

12 个 Python 模块为 `test_media_parser`、`test_metadata`、`test_metadata_resolution`、
`test_metadata_correction`、`test_task_item_metadata_search`、`test_manual_task_engine`、
`test_automation_entrance_recovery`、`test_v2_manual_organize`、`test_configuration_objects`、
`test_operations_task_center`、`test_processing_recovery_admission`、`test_metadata_review`。
新增用例覆盖同名剧八集、候选顺序互换、多个候选通过、季 404、缺集、预算耗尽、技术故障、
首季/电影年份规则、显式与清空年份、错误直接 ID 恢复、候选选择失败后仅消费最新决定，以及
混合批次零执行范围。真实 Worker 场景使用仓库既有 Files 受理、CLI 整理、恢复 API 和常驻
Worker 路径；未构造不存在的入口。

**剩余与风险**

- B 仍需在冻结候选上运行 Task 指定的真实浏览器、全量回归、构建与封装门禁；Developer 未运行
  Playwright、全量 Python/Web 套件或生产产物验证。
- 自动匹配以确认阈值的标题证据加完整季集验证为条件；若真实 TMDB 返回多个同等节目且均有
  所需集数，按设计进入人工候选确认，需 B 用真实 Files API 核对两个入口的一致投影。
- 修正原因复用既有 `outcome` 文本载体，未迁移历史记录；历史 pending/resolved 行按原状态读取。

## B Review Result — FIX REQUIRED

```text
Reviewed Base: 660fecb6637ed36910493c65b94b0b8c3ced7681
Reviewed Implementation: bf3f81c2d59f31c96fa7cc1d7ad490a0f28501c1
Reviewed Head: 42178555f06c3646ad8ff8d6432f07670cb77c64
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

B 使用现有 Files 整理受理、Worker 和逐文件恢复 API，配合临时 SQLite、Local Storage 与模拟 Provider，复测了八集。
模拟 2024 年同名剧的第四季返回 404，八项仍都以 2019 年作品生成待确认摘要，Storage 变更为零。
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_metadata tests.test_metadata_correction tests.test_task_item_metadata_search`
通过 65 项，`git diff --check` 与治理检查通过。发现下列两处阻塞后，全量和原生浏览器验收留待修正候选。

### Developer 返工指导

1. **修正后仍有多候选时，恢复同一文件的候选选择。** 从 Files 打开整理，选中需要确认的 S04E01 同名候选。
   所选作品没有第四季，系统打开「修正作品搜索」。保存搜索条件并重新分析时，Provider 仍返回两个可比候选，现候选把文件置为失败并收掉修正入口。
   复现使用「整理规则」现有的最大 Provider 请求数 `2`，因此首次和再次搜索都需人工选择。
   `MetadataReviewService.create` 为同一文件生成相同的审核 ID，SQLite 仍尝试插入已存在的候选审核。
   在现有候选审核写入路径上复用同一文件的记录，将当前候选替换、待选状态和等待项一起写入。保留之前的选择审计，旧确认版本不可用。
   从同一个文件重新选择有正确季集的作品后，应进入新摘要确认。覆盖「候选确认 → 季集不符 → 只保存查询 → 再次候选确认 → 正确摘要」全链路，确认前保持零 Storage 变更。
   在 `tests.test_manual_task_engine` 或 `tests.test_task_item_metadata_search` 的现有入口加回归，运行对应模块及 `tests.test_metadata_review`。
2. **恢复电影的候选详情查询预算。** 从 Files 整理 `哈姆奈特.2025.mkv`，电影策略的最大 Provider 请求数为 `2`。
   模拟搜索结果只返回 `Hamnet`，电影详情提供译名「哈姆奈特」。Base 使用一次搜索和一次详情查询到达待确认摘要。
   候选在 `_enrich_candidates` 一律预留一次请求，电影只执行搜索便进入元数据修正。
   让调用方按既有规则预留实际需要的季集请求，S02+ 校验分支沿用自身预算。补充电影在两次请求内通过译名匹配的回归，并运行 `tests.test_metadata` 和 `tests.test_manual_task_engine`。

完成后运行上述受影响的测试及 `git diff --check`，交付新候选。B 在新候选上复核两段操作并执行本 Task 的 T4 验收。

## Developer Completion Report — B 反馈：候选审核重开与电影详情预算

```text
Task Base: 660fecb6637ed36910493c65b94b0b8c3ced7681
Reviewed Fix Target: 62c47df4f66ea688fb90ff7daef51ceaf7a5f25f
Implementation Candidate: ec8dce1b92003218a61e3404b870f7ac0ea6a518
Branch: main
Status: READY FOR B REVIEW
```

**起点**

本轮从 `main`／`62c47df4`（B 的 FIX REQUIRED 检查点）开始，工作区与暂存区干净，无既存
未提交文件。修正提交为 `ec8dce1b`，本报告与 TASK.md 交接单独提交。

**修正结果**

1. **同文件候选审核重开。** `MetadataReviewService.create` 先读取该 TaskItem 已有的候选审核；
   存在时复用同一 `review_id` 与 `created_at`，在当前候选审核写入路径上原子替换查询、结果、
   候选清单、待选状态和等待项。`metadata_reviews` 的选择字段与决定时间被清空，已有
   `metadata_review_decision_audit` 保留；不改 SQLite 结构。`reopen_metadata_review[_with_evidence]`
   在同一事务中删除旧候选、写入新候选并推进 TaskItem，插入失败时整体回滚，旧审核和旧候选
   保持原事实。ID 重开使过期的检查点版本不能用于选择新快照中的候选。
2. **电影详情预算。** `_enrich_candidates` 不再一律预留一次请求；调用方按既有规则传入实际
   需要：电影为 `0`（匹配直接复用已获取的详情身份），明确季集的 S01/未验证分支为 `1`，
   S02+ 季集校验分支继续使用自身的 `2` 请求预算。电影搜索加一次详情请求即可通过译名进入
   待确认摘要，不再提前进入元数据修正。
3. 在两个现有入口补充回归：`tests.test_task_item_metadata_search` 覆盖
   「候选确认 → 季集不符 → 只保存查询 → 再次候选确认 → 正确摘要」全链路，验证同一
   `review_id`、候选替换、旧审计保留、旧候选检查点版本被拒绝、确认前零 Storage 变更；
   `tests.test_manual_task_engine` 通过真实 Files 受理、Worker 和两请求电影策略验证
   `Hamnet` 详情译名匹配；`tests.test_metadata` 验证两次请求内完成匹配。
   `tests.test_metadata_review` 同时覆盖重开成功与候选写入失败时的原子回滚。
   为复现任务中的真实请求预算，测试助手 `entrance_journey` 与 `_DiscoveryFixture.journey`
   增加可选的最大 Provider 请求数参数，并由对应旅程显式传入 `2`。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选工作树）**

```text
python3 scripts/check_governance.py                                   -> PASS
git diff --check                                                      -> clean
.venv/bin/ruff format --check <10 changed files>                      -> 10 files already formatted
.venv/bin/ruff check <10 changed files>                               -> All checks passed
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest <12 affected modules> -> 301 tests OK (10.25s)
web: npm run test -- run TaskItemRecoveryPanel.test.tsx
     ManualOrganizeDialog.test.tsx RunDetailTabs.test.tsx              -> 3 files, 71 tests OK (20.37s)
web: npm run typecheck                                                 -> OK
```

12 个 Python 模块为 `test_media_parser`、`test_metadata`、`test_metadata_resolution`、
`test_metadata_correction`、`test_metadata_review`、`test_task_item_metadata_search`、
`test_manual_task_engine`、`test_automation_entrance_recovery`、`test_v2_manual_organize`、
`test_configuration_objects`、`test_operations_task_center`、
`test_processing_recovery_admission`。另运行了受测试助手变更影响的
`tests.test_media_discovery` 与 `tests.test_operations_task_center`（31 tests OK）。
新增链路中的 Provider 为本地模拟实现，Files/Worker、真实 API、SQLite 与 Local Storage
均使用仓库既有入口，没有构造不存在的入口。

**剩余与风险**

- B 仍需在冻结候选上执行本 Task 的 T4 全量 Python/Web/E2E、构建与封装门禁；Developer 未运行
  Playwright、全量套件或生产产物验证。
- 本轮未连接真实 TMDB；同名剧、季集缺失、译名和预算场景均由本地模拟 Provider 覆盖，B 需在
  独立验收中核对真实 Provider 返回形态与两个入口的一致投影。
- 候选审核重开复用既有记录与审计，不迁移历史数据；历史 pending/resolved 行仍按原状态读取。

## B Re-Review — FIX REQUIRED

```text
Reviewed Base: 660fecb6637ed36910493c65b94b0b8c3ced7681
Reviewed Implementation: ec8dce1b92003218a61e3404b870f7ac0ea6a518
Reviewed Head: a25b4e54bb6c867b44a6ca40a963388822a16be1
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

B 通过现有 Files API 和 Worker 独立复测，八集以 2019 年作品生成待确认摘要。选错同名剧后只保存搜索条件，可在同一文件再次选择候选并生成摘要。
电影从 Files 受理后花费一次搜索和一次详情查询即匹配译名。三段操作在确认前均为零 Storage 变更。

真实浏览器中，从文件页整理 `黑袍纠察队.2024.S04E01.mkv`，选择 2024 年候选并重新分析。看到该作品没有第四季后，关闭对话框，
进入「任务中心 → 元数据恢复 → 查看问题文件」，打开同一文件。系统显示第四季不匹配，但搜索标题和年份为空，类型显示「电影」，保存按钮禁用。
该项 `/recovery` 读取仍返回标题「黑袍纠察队」、年份 `2024`、类型 `tv`。

### Developer 返工指导

1. 修改 `TaskItemRecoveryPanel` 的表单初始值。文件页已加载同一条目时，任务中心首次渲染就能读到当前决定。
   用该次渲染的决定与检查点初始化内部表单，保留宿主对同一检查点的草稿。当前代码始终以空值初始化，而同一次渲染已记录当前检查点，因此后续读取相同检查点不会填入表单。
2. 在现有元数据原生浏览器验收中增加一条从 Files 到任务中心的 S04E01 用例。选择缺少第四季的作品后打开同一条目的修正表单，确认标题、年份、剧集类型和失败原因正确。
   只清空年份并保存，回到候选选择，选能验证第四季的作品后查看待确认摘要。搜索、保存和重新分析期间检查源与目标零变更。
   补充首次挂载已有查询数据的前端回归，运行 `npm run test -- run src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx`，以及涉及的原生用例。

### B 实际验收

- Python 全量运行 2332 项，1 项失败，7 项跳过。唯一失败来自 `TASK.md` 测试分工标题，B 已对齐工作流模板并单独复测该检查。
- Web 单测 1642 项、Web 浏览器 287 项、现有真实 Python 浏览器 12 项通过。额外的 S04E01 浏览器复测发现上述跨入口阻塞。
- Python 与 Web 静态门禁、Web 构建、wheel 安装验收、Docker 镜像构建及发布安全验收通过。首次 Docker 安全验收因 Colima 不共享系统临时目录未启动容器，改用已共享临时目录通过。
- 本地证据 `.git/validation-evidence/a25b4e54/b-review/`，重点为 `native-season.log`、`native-season-center-confirm.log`、`native-season-center-data.log` 和 `python.log`。

## Developer Completion Report — 任务中心表单初始化与原生 S04E01 验收用例

```text
Task Base: 660fecb6637ed36910493c65b94b0b8c3ced7681
Reviewed Fix Target: a25b4e54bb6c867b44a6ca40a963388822a16be1
Implementation Candidate: 54e624491ca957e60d82e115d5ae8d4ebc0b9d83
Branch: main
Status: READY FOR B REVIEW
```

**起点**

本轮从 `main`／`48a53122`（B 的返工指导检查点）开始，工作区与暂存区干净，无既存未提交文件。
实现提交为 `54e62449`，本报告与 TASK.md 交接单独提交。

**修正结果**

1. **首次渲染即读取当前决定。** `TaskItemRecoveryPanel` 的内部决定草稿改为用首次渲染已经持有的
   决定与检查点初始化。Files 对话框和任务中心共用同一个恢复读取缓存：任务中心首次挂载同一
   TaskItem 时表单立即显示已保存的标题、年份、剧集类型和失败原因，保存按钮可用；读取仍在途时
   （空身份）保持原空表单并由既有按检查点重置逻辑在真实身份到达后填充；宿主对同一检查点的草稿
   仍优先于服务端决定，过期检查点草稿仍被拒绝保留。未改任何 SQLite 结构或 API。
2. **原生浏览器验收用例（Files → 任务中心 S04E01）。** 在 `metadata-search-year.python.spec.ts`
   新增端到端用例：`SeasonProbe/黑袍纠察队.2024.S04E01.mkv` 经真实 Files 受理后，两部同名剧进入
   有界候选判定；操作者选择 2024 候选并重新分析，看到「第四季不匹配」的可读原因、已保存的标题/
   年份/剧集类型；关闭对话框后在任务中心「元数据恢复 → 查看问题文件」打开同一文件，修正表单
   首次渲染即正确；只清空年份保存后，Provider 收到无年份搜索并回到候选选择；选择能验证第四季的
   2019 作品后同一面板显示待确认摘要。全程断言源与目标零变更、无 Execute 命令、Provider 从未
   收到 `2024` 年过滤。该用例在未修正的构件上复现 B 报告的空表单阻塞（标题为空、保存禁用），
   修正后通过。
3. **harness 支持（仅测试基础设施）。** `operations_inventory_harness.py` 新增
   `_SeasonProbeMetadataProvider`（两部同名剧、季读取按身份区分 404 与 E01–E08、记录探测搜索）、
   `SeasonProbe` 夹具源文件、专用识别规则/类型/策略（两请求 TV 元数据策略，与既有夹具隔离）及
   `manual-file-state` 白名单条目；既有用例未改。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选工作树）**

```text
python3 scripts/check_governance.py                                   -> PASS
git diff --check                                                      -> clean
.venv/bin/ruff format --check scripts/operations_inventory_harness.py -> already formatted
.venv/bin/ruff check scripts/operations_inventory_harness.py          -> All checks passed
web: npm run typecheck / lint / format:check                          -> OK
web: npm run test -- run TaskItemRecoveryPanel.test.tsx
     ManualOrganizeDialog.test.tsx RunDetailTabs.test.tsx              -> 3 files, 72 tests OK (19.75s)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_media_parser
     tests.test_metadata tests.test_metadata_resolution
     tests.test_metadata_correction tests.test_task_item_metadata_search
     tests.test_manual_task_engine tests.test_automation_entrance_recovery -> 133 tests OK (5.55s)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_metadata_review
     tests.test_operations_task_center tests.test_task_item_metadata_search -> 44 tests OK (1.21s)
web: npm run build                                                     -> OK
web: npx playwright test --config=playwright.python.config.ts
     tests/e2e/metadata-search-year.python.spec.ts                     -> 3 tests OK (23.6s)
web: npx playwright test --config=playwright.python.config.ts
     tests/e2e/manual-organize-dialog.python.spec.ts                   -> 10 tests OK (1.0m)
```

新增前端回归覆盖首次挂载已有查询数据：预置缓存后渲染面板，断言标题/年份/类型/原因立即正确、
保存可用、无任何变更请求，且编辑年份后搜索按输入值提交。原生用例中的 Provider 为本地模拟实现；
Files 受理、Worker、恢复 API、SQLite 与 Local Storage 均使用仓库既有真实入口，未构造不存在的入口。
另以临时脚本按同一入口顺序离线驱动了完整链路（候选选择→错误候选→季不匹配→清空年份→候选选择→
正确候选→待确认摘要），与浏览器用例结论一致。

**剩余与风险**

- B 仍需在冻结候选上执行本 Task 的 T4 全量 Python/Web 回归、构建与封装门禁；Developer 未运行
  Playwright 之外的其余原生套件、全量单测或生产产物验证。
- 原生用例的请求预算依赖夹具策略的 `maxProviderRequests: 2`；真实 TMDB 在同等预算下同样进入
  人工候选判定，但候选顺序由评分决定，B 需在独立验收中核对真实返回形态下的两入口一致投影。
- 本轮未连接真实 TMDB；同名剧与季集场景均由本地模拟 Provider 覆盖，与上一轮风险一致。
