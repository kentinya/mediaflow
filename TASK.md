# NO ACTIVE IMPLEMENTATION TASK

本轮仅规划。下方 PATCH-20261030-6 为完整规划草案，不授权实施；进入实施前由 B 核对
当时工作区和 Base 后，将草案转为正式 Task。此次不修改产品实现或现行产品文档。

最近独立修正：**PATCH-20261030-5 — 执行记录仅保留详情按钮，B PASS（2026-10-30）**。
四项验收全部满足，无待实施/返工项。记录操作仅有查看/收起详情，完整证据与筛选分页保留。

- Task Type：STANDALONE MINOR BUG；Parent Slice：NONE；Difficulty：Low；Test Level：T2。
- Reviewed Base：`a7bcd92fb5b40dbf636e5aeab99aafc5db701e39`。
- Reviewed Head：`64793019d522116a6d7a60e5c83baa62e24c96c0`；产品实现：
  `a4d6057cb228d4cd2027cd2e00de18cc3c1d47a5`。
- 完整授权、计划、验收与 Developer 交接保留于上述 Reviewed Head 的 `TASK.md`。
  B 完整范围独立审查、实际验收及证据限制：
  `5bd95546921d7dcee7f95b0360a0d6200f0a8791:TASK.md`；无角色例外。
- B 验收组件/路由 **20/20**、桌面/窄屏浏览器 **2/2**、真实 Python 记录旅程 **3/3**
  及适用静态/构建检查通过，无失败、跳过或重试；测试时间符合用户的 50% 限制。
  证据限隔离 Node/Python/SQLite 与 Chromium 模拟视口，原始日志及截图仅本机 ignored
  存储可达，精确命令/耗时与位置见上述 B 审查记录。

现行要求见 [V2 Requirements](docs/v2-requirements.md#automation-workspace-requirements--current-slice-43-pass--closed)，
完整旅程见 [Product Experience](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)，
界面与 API 关联数据的边界见 [Architecture](docs/architecture.md#current--v2-automation-workspace-and-consumed-engine-settings-slice43-pass--closed)。

Slice46 保持 A 已接受的 **PASS / CLOSED**，原 Base/已接受 Head、SLICE/Roadmap/Progress
及延期边界不变。下一大版本由 A 选择；本次不选择或授权下一 Task/Slice。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

## 规划草案 — PATCH-20261030-6：自动化执行记录只展示本次结果

Authority: 用户要求详情只保留“执行结果和时间、失败原因、下一步”，不提供失败后恢复
入口、不显示后续状态；一次执行结束后有任何受理条目未成功，就显示失败。当前仅授权
规划，范围限定自动化执行记录的只读展示及与其一致的结果筛选，不改变全局执行语义。

```text
Task ID: PATCH-20261030-6
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 9b9626d130a46eb8676b3514558ed845e26c598b
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: NOT GRANTED — PLANNING ONLY
```

### Goal / Existing entry and gap

入口是 自动化 → 执行记录 → 某行“查看详情”。目前 `AutomationRecordRow` 展示四区，
直接输出 `handling` 状态/恢复计数和多段 `handoff`/恢复建议；行标签仍有“部分成功”。
`AutomationListPage.RECORD_STATUS_OPTIONS` 按原始状态筛选；现有
`GET /api/v1/operations/automation/records` 经 `_automation_records_query` 和
`SQLiteRuntimeRepository.operations_runs_window` 在分页前执行 `derived_status = ?`。
只改前端标签会使“失败”筛选遗漏原部分成功、取消或其他未全部成功的记录。

目标：读取本次执行 → 看结果及实际时间 → 失败时读直接原因 → 读简短下一步说明。
执行记录始终只读；刷新/筛选/分页可找回原记录。读取失败保留现有明确错误与刷新；
原因不可读要明示。处理问题继续使用既有独立工作区，记录内没有恢复操作或跳转。

适用 `V2-AUTO-001/005/006`、`V2-OPS-016`、`REQ-TASK-002/003`、
`REQ-RECOVERY-001/002`、`REQ-API-002/003`、`REQ-SAFE-005/007`。
已读 [完整自动化旅程](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
及 [CURRENT 架构](docs/architecture.md#current--v2-automation-workspace-and-consumed-engine-settings-slice43-pass--closed)。
本草案记录用户对记录页的明确修订；既有 Slice 验收身份和任务中心恢复契约不变。

### Implementation Scope / ordered steps

1. 在现有记录读取链路增加记录专用的结果分类，复用原始受理/TaskItem/Result 证据。
   既有原始 `status`、`result`、`handling`、`handoff` 数据契约及共享状态枚举保留；
   可增补有类型的展示字段和专用查询参数。记录列表/详情使用同一个分类，规则如下：

   | 本次执行证据 | 执行记录页显示 |
   |---|---|
   | 已结束，受理条目全部得到明确成功结果 | 成功 |
   | 已结束，受理条目中有失败、部分完成、跳过/忽略、取消或效果不确定 | 失败；保留真实已成功数量/已知效果，不暗示全部未执行 |
   | 整次已取消或已知失败，包括没有正式 Task 的前置失败 | 失败；取消及前置原因仍可读 |
   | 已证明正常空范围、没有受理条目的无工作完成 | 成功并保留“无工作完成”；不能把跳过全部条目当作空范围 |
   | Pending / Running / Paused / Waiting | 保留实际未结束状态，不提前归失败 |
   | 状态或必要证据不可核对 | 明确未知/不可读，不推断成功或伪造失败原因 |

   过滤掉、从未受理的非候选文件不是“未成功条目”。不能仅靠缺失值、当前页面条数或
   未验证的 `total - success` 猜测结果。原始失败不会因后续恢复完成而变成功；分类不消费
   后续 `handling`/恢复完成显示，不创建新的历史库或快照机制。
2. 在现有记录 GET 的全量授权人口上应用专用成功/失败筛选，再算总数、分页和游标，
   与第 1 步使用同一分类。Web 结果选项移除“部分成功/已取消”独立类别，仍支持真实
   进行/等待状态。新筛选纳入 query key 与 principal/filter/direction 游标作用域。
   旧页面 `rstatus=partial_success/cancelled` 规范为失败并清除不适配的游标，刷新和
   前后翻页保留当前条件；原有 API 原始状态筛选契约及其他消费者默认行为保持。
   禁止客户端过滤单页、拼接多页或无界加载来伪造失败全集。
3. 精简 `AutomationRecordRow`，每行仍只有查看/收起详情，最多三个内容区：
   - **执行结果和时间**：本次结果与真实开始/结束时间；缺失时间为 `—`，不借用创建/
     更新时间。摘要行和详情不出现“部分成功”标签或互相矛盾的结果说明。
   - **失败原因**：仅失败时出现，以有界、可读原因说明为什么失败；多个独立原因不互相
     覆盖。必要阶段/已知部分或不确定效果合并为简短说明，保持不能安全重复的事实；
     原因缺失或证据截断明确标注，不堆原始内部标识，也不编造异常、无效果或安全重试。
   - **下一步**：仅简短文字。成功无需处理，未结束等待，已知失败提示修正原因，效果
     不确定时提示先核对、勿重复执行；不把修复配置等同于恢复原任务，不承诺自动重试。
   删除整个“后续处理”、恢复状态/最近关联/恢复数量，并清理仅供本页显示它们的代码。
   不把 `handling.nextAction` 或整段 `handoff` 原文搬到另一区域；不新增第四区、恢复菜单、
   任务中心/定义链接、重试/继续/重新分析/执行等入口。
4. 调整既有组件、API/SQLite 和浏览器用例。实现时同步 `V2-AUTO-006`、完整旅程、
   CURRENT 记录架构及 README 中直接受影响的表述，说明记录专用分类与原始数据边界；
   不开展额外文档治理，不改 SLICE/Roadmap/Progress。

### Acceptance Criteria

- [ ] 详情最多上述三个区；失败原因仅失败时出现。无“后续处理”及其状态、关联、恢复
  数量或移位替代；每行保留一个可访问的查看/收起详情按钮。
- [ ] 摘要、详情及结果筛选采用同一记录专用分类；已结束的混合/跳过/取消/不确定记录
  归失败，全成功及真实空范围准确，进行/等待/未知不被误判。真实已成功效果仍明确。
- [ ] 失败原因和下一步清楚、有界、无秘密；前置失败、多个失败和证据不可读仍可理解，
  不确定效果没有无效果/可重试的假承诺。无恢复、执行或导航入口，读取和展开零写入。
- [ ] 失败筛选跨页完整，总数及双向游标一致；定义/触发方式/时间组合筛选、清除、刷新/
  重连保持正确。非法参数、跨 principal/筛选/方向游标及 401/403 沿用有界拒绝。
- [ ] 后续处理变化和重启不改写原次失败；API 原始字段、持久化结果、Task Center 原始/
  恢复显示、任务列表最近结果、Automation 统计和成功率保持既有口径与功能。
- [ ] 1536/390px 实际页面可读、无页面横向溢出，原有表格内部滚动及键盘展开可用。
  仅必要文档随实现同步，原 Slice Base/Head/关闭事实、权限、调度/执行和成功/不确定
  条目不重放等安全契约保持。

### Required Tests

遵循 [测试分工](docs/development-workflow.md#6-test-levels)。所有用例从现有记录 GET、
组件路由和自动化实际入口开展，使用现有隔离假服务/临时 SQLite/Local 媒体；不猜测或
构造不存在的接口，不使用用户配置、数据库或媒体。测试含静态/构建累计须少于每轮
总用时 50%；计入失败运行，不以等待凑比例，发现阻塞先返回同一 Task 修正。

Developer — 新改及直接受影响检查：

- 根目录：`.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_operations_run_inventory`。
  在既有用例中覆盖表中分类、原始状态与统计不变、混合人口超过一页、准确总数、组合
  筛选/双向及作用域冲突、原失败与后续成功分离、失败原因不可读、READ 权限和零写入。
- `web/`：`npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationRouter.test.tsx src/entities/operations/automation.test.ts src/shared/api/api-client.test.ts`。
  覆盖三内容区、无后续状态/恢复入口、摘要/详情/筛选一致、新字段严格解码及旧 URL。
- `web/`：`npm run typecheck`；修改文件的 ESLint/Prettier；`npm run build`；
  `npm run test:e2e -- tests/e2e/automation-presentation.spec.ts`。
  在现有 1536/390px 旅程覆盖三内容区、展开/收起、零写入并查看截图。
- Python 修改文件的 `.venv/bin/ruff check <changed-python-files>` 和
  `.venv/bin/ruff format --check <changed-python-files>`；根目录
  `python3 scripts/check_governance.py`、`git diff --check`。

B — 独立审查和验收：

- 审查完整 Task Base..candidate；核对本次结果、只读边界及全部验收，先复现阻塞。
  在候选上运行上述 Python/Web 模块与适用静态检查；相同执行输入的 B 自有结果可按
  流程复用，不把实现者报告当作独立验收，不机械跑无关全仓。
- 根目录：`.venv/bin/python -m unittest tests.test_task_center_recovery_lineage tests.test_v2_automation_run_once`，
  核对共享读取不改变任务中心恢复和正常自动化执行/历史口径。
- `web/` 构建后：`npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts`。
  延伸现有记录/分页/技术失败/独立失败旅程，以真实 Python/API/SQLite/Worker 数据验证
  记录失败分类、跨页筛选、原因、后续证据变化不改本次结果，以及页面没有恢复入口；
  原始 API 效果/统计断言保留。查看桌面和窄屏真实截图，记录候选、实际数量/失败/跳过
  与本机 ignored 日志位置。该 T3 不要求无关全仓、容器或外部服务验收。

### Non-goals / Workspace / handoff

不改持久化状态、schema、执行成功判定、调度/授权/Worker、任务中心恢复或全局统计；
不删除其他消费者的 `handling`/`handoff`，不新增队列、历史快照或通用状态系统，不重构
共享查询。必要 SQL 增量仅服务记录专用分类/筛选，所有既有调用默认行为保持。

规划工作区为 `main` / 上述 Task Base，无预存已跟踪修改；预存未跟踪文件原样保留，
清单见本机 `.git/validation-evidence/plan-PATCH-20261030-6/baseline.txt`。本轮仅修改
本 Task 草案；实施前复核期间变化，不静默更换 Base。产品验收尚未执行，无 PASS 声明。
之后获授权的 Developer 只实现本 Task，提交连贯 checkpoint 和实际受影响测试结果至
READY FOR B REVIEW；B 独立给 PASS 或 FIX REQUIRED。PASS 后恢复简短无活动 Task 通知，
保持 Slice46 PASS / CLOSED，不规划额外工作。
