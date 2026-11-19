# Task PATCH-20261120-1 — 修复后续季剧集匹配与逐文件元数据修正

用户于 2026-11-20 授权激活独立 Task，待 Developer 开始实施。依据为 `REQ-META-005/008`、`REQ-RECOVERY-005`、`V2-OPS-007/016`。
[独立缺陷流程](docs/development-workflow.md#31-independent-minor-bugs) · [现有逐项恢复流程](docs/product-experience.md#tasks-results-and-per-item-recovery) · [上一独立修复的 B 验收](https://github.com/kentinya/mediaflow/blob/c8039f1f3d7bdfdb7fd927c75f99df0cb8a9e523/TASK.md#patch-20261119-2--b-验收-pass)

```text
Task ID: PATCH-20261120-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
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

**Developer**

- 从仓库根目录运行 `.venv/bin/python -m unittest tests.test_media_parser tests.test_metadata tests.test_metadata_resolution tests.test_metadata_correction tests.test_task_item_metadata_search tests.test_manual_task_engine tests.test_automation_entrance_recovery`。
  在这些模块中补齐同名剧、季集验证、业务结果与技术故障、请求预算、修正后再失败、按不同入口重分析和混合批次的回归。
- 从 `web/` 运行 `npm run test -- run src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/RunDetailTabs.test.tsx`。
  验证两个入口的原因、已有操作和保存后新摘要。运行 `git diff --check` 及改动文件对应的 Ruff 或 Web 静态检查。

**B**

- 在冻结候选上独立复现八集与反例，检查 Files 和自动整理逐项状态、同一 Task 恢复、权限和固定配置、等待记录写入的原子性、
  过期决定拒绝及明确效果边界。在临时 SQLite、本地 Storage、模拟 Provider 和构建产物上补跑真实浏览器验收。
- 从 `web/` 构建后运行 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/metadata-search-year.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts`。
  在现有原生测试和 harness 中加入后续季用例，验证 Files 和任务中心的修正操作、刷新及确认前零变更。
  按[共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)运行全量回归和适用的封装及安全检查。

### 边界

范围限于现有 TV 匹配、元数据决定与整理恢复路径。沿用现有 Provider 配置、API 路由、任务状态和 SQLite 结构。
既有文件页和任务中心承接本次恢复，已验收的 Slice 作为参考。
