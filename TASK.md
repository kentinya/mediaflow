# Task PATCH-20261030-6 — 自动化执行记录只展示本次结果

Authority: 用户要求详情只保留“执行结果和时间、失败原因、下一步”，不提供失败后恢复
入口、不显示后续状态；一次执行结束后有任何受理条目未成功，就显示失败。记录须使用
普通使用者能理解的简洁中文，说清结果、原因和下一步。用户已授权激活本 Task，范围限定
记录的只读展示及与其一致的结果筛选，不改变全局执行语义。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

```text
Task ID: PATCH-20261030-6
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 9b9626d130a46eb8676b3514558ed845e26c598b
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER ACTIVATED TASK — 2026-10-30
```

## Goal / Existing entry and gap

入口是 自动化 → 执行记录 → 某行“查看详情”。目前 `AutomationRecordRow` 展示四区，
直接输出 `handling` 状态/恢复计数和多段 `handoff`/恢复建议；行标签仍有“部分成功”。
`AutomationListPage.RECORD_STATUS_OPTIONS` 按原始状态筛选；现有
`GET /api/v1/operations/automation/records` 经 `_automation_records_query` 和
`SQLiteRuntimeRepository.operations_runs_window` 在分页前执行 `derived_status = ?`。
只改前端标签会使“失败”筛选遗漏原部分成功、取消或其他未全部成功的记录。

目标：读取本次执行 → 看结果及实际时间 → 失败时读直接原因 → 读简短下一步说明。
执行记录始终只读；刷新/筛选/分页可找回原记录。读取失败保留现有明确错误与刷新；
原因不可读要明示。处理问题继续使用既有独立工作区，记录内没有恢复操作或跳转。

这里的“取消”指取消某一次已受理的运行。现有入口为 任务中心 → 选择该次运行 →
运行控制 → 取消运行，由后端状态和权限决定是否可用；`OperationsLanding` 实际挂载
`RunLifecycleControls`。取消请求尚未确认时仍是进行中的控制请求，不能提前归终态失败。
自动化定义的“停用”不是这个动作；当前“运行一次”通过关联任务查看控制，不能把保留
的历史分析分支按钮当作正常取消入口。本 Task 不新增、迁移或改变这些控制。

适用 `V2-AUTO-001/005/006`、`V2-OPS-016`、`REQ-TASK-002/003`、
`REQ-RECOVERY-001/002`、`REQ-API-002/003`、`REQ-SAFE-005/007`。
已读 [完整自动化旅程](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
及 [CURRENT 架构](docs/architecture.md#current--v2-automation-workspace-and-consumed-engine-settings-slice43-pass--closed)。
本 Task 记录用户对记录页的明确修订；既有 Slice 验收身份和任务中心恢复契约不变。

## Implementation Scope / ordered steps

1. 在现有记录读取链路统一本页的结果分类，复用原始受理/TaskItem/Result 证据。
   既有原始 `status`、`result`、`handling`、`handoff` 语义及共享状态枚举保留。
   以展示和筛选结果为验收对象，不预先要求新增字段或查询参数；如确有必要增补，
   仅扩展现有记录读契约并保持类型校验和其他调用者默认行为。分类规则如下：

   | 本次执行证据 | 执行记录页显示 |
   |---|---|
   | 已结束，本次受理工作全部明确成功 | 成功 |
   | 已结束，本次受理工作中有失败、部分完成、跳过/忽略、取消或效果不确定 | 失败；说明未全部完成的具体原因，已成功的效果不被抹去 |
   | 本次运行已确认取消或已知失败，包括没有正式 Task 的前置失败 | 失败；明确写“本次运行已取消”或具体前置原因，不把取消说成程序异常 |
   | 已证明正常空范围、没有受理条目的无工作完成 | 成功并保留“无工作完成”；不能把跳过全部条目当作空范围 |
   | Pending / Running / Paused / Waiting | 保留实际未结束状态，不提前归失败 |
   | 状态或必要证据不可核对 | 明确未知/不可读，不推断成功或伪造失败原因 |

   本次受理工作包括应处理的主媒体及关联附件，不能只看主文件成功数量；复用既有
   逐项结果，不为展示再遍历 Storage。过滤掉、从未受理的非候选文件不参与失败判定。
   跳过和取消也按“本次没有全部成功”归失败，原因须区分正常策略跳过、主动取消与
   实际错误。不能仅靠缺失值、单页条数或未验证的 `total - success` 猜结果。
   原次失败不会因后续恢复完成而变成功；分类不消费后续 `handling`/恢复完成显示，
   不创建新的历史库或快照机制。
2. 在现有记录 GET 的全量授权人口上应用专用成功/失败筛选，再算总数、分页和游标，
   与第 1 步使用同一分类。Web 结果选项移除“部分成功/已取消”独立类别，仍支持真实
   进行/等待状态。实际筛选条件纳入 query key 与 principal/filter/direction 游标作用域。
   刷新和前后翻页保留当前条件，变更条件不沿用不匹配的游标。既有带筛选 URL 按当前
   入口校验处理，不能出现选中条件与展示结果矛盾；不要求专门的旧 URL 转换或兼容层。
   原有 API 原始状态筛选契约及其他消费者默认行为保持。
   禁止客户端过滤单页、拼接多页或无界加载来伪造失败全集。
3. 精简 `AutomationRecordRow`，每行仍只有查看/收起详情，最多三个内容区：
   - **执行结果和时间**：本次结果与真实开始/结束时间；缺失时间为 `—`，不借用创建/
     更新时间。摘要行和详情不出现“部分成功”标签或互相矛盾的结果说明。
   - **失败原因**：仅失败时出现，用简短中文说明本次为什么未全部成功。多个原因可简洁
     归纳，不要求铺开逐项证据表或复制所有技术字段；仍须保留必要的部分/不确定效果
     提示。原因缺失或证据截断明确标注，不编造异常、无效果或安全重试。
   - **下一步**：仅简短、具体的文字建议。全成功表示本次无需修复，不代表来源已全部
     处理；未结束提示等待；跳过提示检查相应文件/策略；取消说明本次已取消且已完成
     操作保留；实际错误提示检查具体原因；效果不确定提示先核对、勿重复执行。
     不把修复配置等同于恢复原任务，不承诺自动重试。
   删除整个“后续处理”、恢复状态/最近关联/恢复数量，并清理仅供本页显示它们的代码。
   不把 `handling.nextAction` 或整段 `handoff` 原文搬到另一区域；不新增第四区、恢复菜单、
   任务中心/定义链接、重试/继续/重新分析/执行等入口。
   三个区都面向普通使用者：不直接显示内部字段名、状态码、恢复归属或大段技术说明，
   不把“下一步”变成恢复教程。例如同名跳过可写“目标已有同名文件，1 个文件被跳过”，
   下一步写“检查目标文件和同名文件处理设置”；这只是表达示例，不要求逐字匹配。
4. 调整既有组件、API/SQLite 和浏览器用例。实现时同步 `V2-AUTO-006`、完整旅程、
   CURRENT 记录架构及 README 中直接受影响的表述，说明记录专用分类与原始数据边界；
   不开展额外文档治理，不改 SLICE/Roadmap/Progress。

## Acceptance Criteria

- [ ] 详情最多上述三个区；失败原因仅失败时出现。无“后续处理”及其状态、关联、恢复
  数量或移位替代；每行保留一个可访问的查看/收起详情按钮。
- [ ] 摘要、详情及结果筛选采用同一记录专用分类；已结束的混合/跳过/取消/不确定记录
  归失败，主媒体成功但关联附件未成功也不能漏掉。全成功及真实空范围准确，进行/
  等待/未知和待确认取消请求不被误判；取消不等同于停用定义。真实已成功效果仍明确。
- [ ] 结果、原因和下一步是简短、易懂的中文，能看懂本次发生什么、为什么及应检查什么；
  不直接展示内部字段/状态码、原始异常、英文技术段落或恢复教程。多原因可简洁归纳，
  前置失败及原因不可读有明确说明，不确定效果没有无效果/可重试的假承诺。
  无恢复、执行或导航入口，读取和展开零写入。
- [ ] 失败筛选跨页完整，总数及双向游标一致；定义/触发方式/时间组合筛选、清除、刷新/
  重连保持正确。非法参数、跨 principal/筛选/方向游标及 401/403 沿用有界拒绝。
- [ ] 后续处理变化和重启不改写原次失败；API 原始字段、持久化结果、Task Center 原始/
  恢复显示、任务列表最近结果、Automation 统计和成功率保持既有口径与功能。
- [ ] 1536/390px 实际页面可读、无页面横向溢出，原有表格内部滚动及键盘展开可用。
  仅必要文档随实现同步，原 Slice Base/Head/关闭事实、权限、调度/执行和成功/不确定
  条目不重放等安全契约保持。

## Required Tests

遵循 [测试分工](docs/development-workflow.md#6-test-levels)。所有用例从现有记录 GET、
组件路由和自动化实际入口开展，使用现有隔离假服务/临时 SQLite/Local 媒体；不猜测或
构造不存在的接口，不使用用户配置、数据库或媒体。测试含静态/构建累计须少于每轮
总用时 50%；计入失败运行，不以等待凑比例，发现阻塞先返回同一 Task 修正。

Developer — 新改及直接受影响检查：

- 根目录：`.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_operations_run_inventory`。
  在既有用例中覆盖表中分类、原始状态与统计不变、混合人口超过一页、准确总数、组合
  筛选/双向及作用域冲突、附件未成功、取消请求与已取消的区别、原失败与后续成功分离、
  失败原因不可读、READ 权限和零写入；不为分类测试新增取消功能或测试专用产品入口。
- `web/`：`npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationRouter.test.tsx src/entities/operations/automation.test.ts src/shared/api/api-client.test.ts`。
  覆盖三内容区、无后续状态/恢复入口、中文原因/下一步与实际情形相符、摘要/详情/筛选
  一致及现有带筛选入口；仅在读契约确有改动时补其严格解码测试，不要求为测试增字段。
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
  原始 API 效果/统计断言保留。通过真实页面内容和桌面/窄屏截图检查中文是否简洁易懂，
  不用 CSS/DOM 结构或示例文案逐字相等代替可读性验收。记录候选、实际数量/失败/跳过
  与本机 ignored 日志位置。该 T3 不要求无关全仓、容器或外部服务验收。

## Non-goals / Workspace / handoff

不改持久化状态、schema、执行成功判定、调度/授权/Worker、任务中心恢复或全局统计；
不删除其他消费者的 `handling`/`handoff`，不新增队列、历史快照或通用状态系统，不重构
共享查询。必要 SQL 增量仅服务记录专用分类/筛选，所有既有调用默认行为保持。

激活工作区：`main` / `611bf628862f42f84e06bef35ca6eedbbd792ef0`，无预存已跟踪修改。
Task Base 保持 `9b9626d130a46eb8676b3514558ed845e26c598b`；从 Base 到激活前 HEAD
仅 `TASK.md` 变化，产品代码不变。预存未跟踪文件原样保留，清单见本机
`.git/validation-evidence/plan-PATCH-20261030-6/baseline.txt`。
Developer 已按本 Task 实施，交本文件所在本地 implementation checkpoint 给 B；
全部验收框保留未勾选，等待 B 独立给 PASS 或 FIX REQUIRED，不代表实现者自签验收。
PASS 后由 B 恢复简短无活动 Task 通知，保持 Slice46
PASS / CLOSED，不规划额外工作。前次独立修正的 B 审查保留于
`5bd95546921d7dcee7f95b0360a0d6200f0a8791:TASK.md`。

## Developer handoff — 2026-10-30

**Candidate / workspace：** 本文件所在 implementation commit（使用 `git rev-parse HEAD` 获取
完整 SHA）；B 审查 `9b9626d130a46eb8676b3514558ed845e26c598b..candidate`。
实现起点为 `main` / `0a3c4658c3f96e25b84e58ea36c728ecda008e1f`；起点无已跟踪修改。
预存未跟踪文件保持原样、未暂存，基线见本机证据 `baseline.txt`。未推送或发布。

**实现：** 现有记录 GET 增加 records-only `recordOutcome` 和可选 `outcome` 筛选；SQLite
在完整授权人口计数/双向分页前使用相同分类，读取原次 TaskItem、Result 和附件证据，
不消费恢复完成投影。原始 status/result/handling/handoff、状态筛选和全局统计保持。
Web 严格解码并统一摘要/详情/筛选，仅显示最多三个简短中文内容区，无恢复或导航入口。
非法旧结果条件沿用有界拒绝并可清除；窄屏详情在表格内部滚动时仍可读。
仅同步直接受影响文档，未改 SLICE/Roadmap/Progress、schema、调度、执行或权限。

**实际验证：** 日志均在本机 `.git/validation-evidence/PATCH-20261030-6/`，不是远程证据。
下表结果属于 Developer，不代替 B 独立验收；执行输入在最后成功运行后未再修改。

| cwd / 实际检查 | 最终结果 | 日志 |
|---|---|---|
| 根目录 `.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_operations_run_inventory` | 81 tests，OK | `python-verified.log` |
| 根目录 `.venv/bin/python -m unittest tests.test_task_center_recovery_lineage tests.test_v2_automation_run_once` | 36 tests，OK | `related-regression.log` |
| `web/`：Required Tests 所列四模块的 `npm run test -- run ...` | 4 files / 68 tests 通过 | `web-final-gates.log` |
| `web/`：`npm run typecheck`、修改 TS/TSX 的 ESLint、修改 Web 文件的 Prettier 检查、`npm run build` | 通过 | `web-final-gates.log` |
| 根目录 `.venv/bin/ruff check` / `format --check`（本次 5 个 Python 文件）、`python3 scripts/check_governance.py`、`git diff --check` | 通过 | `python-static-final.log` |
| `web/`：`npm run test:e2e -- tests/e2e/automation-presentation.spec.ts` | 2 tests 通过，1536/390px | `e2e-presentation-verified.log` |
| `web/`：`npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts` | 8 tests 通过，真实 Python/API/SQLite/Worker | `e2e-python-verified.log` |

已人工查看 `presentation-verified-artifacts/**/record-detail.png` 和
`python-verified-artifacts/**/records-technical-{1536,390}.png`：简短中文原因/下一步可读，
详情不被右侧按钮焦点带来的横向滚动隐藏。实际记录 GET/组件路由为验证入口；跨页取消
使用任务中心读取所提供的可用 cancel 路径及 `expectedUpdatedAt`，没有新增产品或
测试专用取消入口。技术混合结果通过真实 Run once/Worker 产生；历史损坏、缺失证据
单元用例使用隔离 SQLite。读取/展开零写入、已成功效果保留及后续处理不改原次失败
均有实际断言。所有用例使用隔离假服务/临时媒体，未读取用户数据库/配置/媒体。

**源码/构建身份：** 本机 `source-inputs.sha256` 包含 644 个源码、测试、harness、锁文件
及配置输入，manifest SHA-256 为
`1ff99a97c87ef363a93d28c60799b670df35352dbe47c61813a42b905f79e31c`。
`build-artifacts.sha256` 的 SHA-256 为
`214b942ceac8c205287bcda7916ff08e91a34230e60fed9a280cc5e362c3a64b`；
`source-identity.json` 说明这是交接时对未再修改输入/最终构建的快照，非冒称测试当时
已生成 manifest。环境 Python 3.13.14 / Node v22.23.3 / npm 10.9.9。

**失败与剩余风险：** 早期 import、未进入 unittest discovery 的新用例、错误断言、
取消请求字段及窄屏详情/viewport 断言曾失败，修正后上述最终运行通过；原失败日志
保留，未删除断言/增加重试掩盖。构建 chunk-size、JSDOM `scrollTo`、SQLite
ResourceWarning 和 Playwright 颜色环境提示仍存在。静态/构建累计（含失败运行）低于
本轮总用时 50%，未以等待凑比例。未执行/不声称全仓、容器、外部服务或发布验收。
记录全人口 SQL 分类的规模性能未做专项压测；B 仍需独立核对全部验收、原始消费者
不变及真实旅程可达性。本报告不声明独立 PASS。
