# Task48.2 — 自动化成功率按 Task 流程统计

用户于 2026-11-04 明确要求“激活Task吧”，现将 `7824c2de71378ab5f69ed8e988c59689850437c1`
中的草案转为正式实施 Task。合同授权先行检查点：`16a94eaceedfd03733b50331e34e8806d93fde6a`。
实施只限本 Task；Developer 实施，B 独立复核。Task48.1 的 PASS、完整计划及实际证据保留于
`469ecc076c6efc660055f47277d7917a0b64a9aa:TASK.md`；不改其结论，不宣告 Slice 关闭。

```text
Task ID: 48.2
Task Type: SLICE
Parent Slice: 48
Status: PLANNED
Task Base: 469ecc076c6efc660055f47277d7917a0b64a9aa
Difficulty: Medium
Test Level: T3 — INTEGRATION
Planner / Reviewer: B
```

沿用草案的 Task Base；从 Base 到激活前 HEAD `7824c2de71378ab5f69ed8e988c59689850437c1`
只有 TASK.md 草案，随后合同授权检查点也只有文档改动，产品/测试/依赖输入未变，无须重规划。
Slice Base 仍为 `ba84272721961c970f1eb85d616a0d129523ab92`；Slice final 仍要求 T4。

激活工作区：`/Users/songzhidong/mediaflow`，分支 `main`，起始 HEAD 为上述激活前 HEAD；
tracked 起始干净、工作区/Git 可写。原有未跟踪 OS/log/reference/output 文件和 `15` 保留且不暂存。
本轮仅同步授权/指针并提升 Task；无产品实现、媒体/用户数据库访问、推送或部署。

Authority：[已提交合同](SLICE.md) RO-4、AC-9/10；保全 AC-11/12/14/15。
需求 `V2-AUTO-012`、`V2-AUTO-005` 的成功率修订；完整旅程与技术边界见
[Product Experience TARGET](docs/product-experience.md#target--task-flow-status-and-automation-success-rate-slice48-active)、
[Architecture TARGET](docs/architecture.md#target--task-flow-status-and-automation-success-rate-slice48-active)。
保留 `V2-TASK-012–014`、`V2-AUTO-010/011`、`UX-001/002/003/006/007/010` 和
`REQ-SAFE-*` 的现有约束。Task48.1 的已接受状态/记录行为是本 Task 的基础。

## Goal / 完整用户旅程

用户进入“自动化”，从已保存定义“运行一次”，或等待已启用定义到期；随后查看本月执行次数、
成功率及执行记录。成功率只回答这些自动化 Task 的流程是否正常收尾。文件全部失败、部分完成、
跳过、忽略、效果未知、缺正式 Result、健康空范围、完整历史排除，只要 Task completed 都计成功；
记录仍独立显示文件结果。待人工处理仍未结束，用户沿现有任务中心决定→分析→摘要→明确继续，
回到自动化刷新时同一 Task 只算一次。用户确认取消后，该记录和已结束次数保留，成功率不计它。

真实 Task 流程失败计 failed；统计读取失败显示不可用及现有刷新/检查数据库指引，不能显示 0%。
读取、筛选、翻页和展开记录不执行工作；文件问题、未知效果及其现有安全下一步不因百分比变更而消失。

## 当前代码缺口与可核验证据

- `mediaflow/infrastructure/sqlite_runtime.py::automation_run_metrics` 已复用原始自动化 admission
  条件和单事务全量查询，但成功数仍要求 `organization_success_items > 0` 且无不确定成功项；
  terminal 分母含 cancelled，`currentNoWork` 又将零成功文件视为无工作。
- `mediaflow/interfaces/service_api.py::_automation_metrics_document` 以 completed/terminal 计算，
  `denominatorStatement` 仍说“已结束”；独立 metrics GET 与定义清单内嵌 metrics 共用此方法。
- `web/src/entities/operations/automation.ts::normalizeAutomationMetrics` 用已结束数校验分母；
  `web/src/features/operations/AutomationInventory.tsx::AutomationMetricCards` 的成功率卡只解释
  已结束数量。Web 必须同步接收和区分“参与成功率的 Task 数”和“全部已结束 Task 数”。
- 已有入口为 `/ui-v2/operations/automation`、定义的 `run-once`、
  `GET /api/v1/operations/automation/metrics` 及 `GET .../task-definitions` 的内嵌 metrics。
  原始 population 由 `_ORIGINAL_AUTOMATION_ADMISSION_WHERE` 和 admission 写入的
  definition/origin/Task 身份限定；不得用当前定义、按钮名称或本页记录推断来源。
- B 在 Task Base（草案核验时） 复用 `tests/test_v2_automation_run_once.py::RunOnceApiTests` 的
  `journey/admit/execute/request`，调用现有 Run once、cancel 和 metrics API；只覆盖既有
  `_automation_now` 测试时钟。健康空范围 completed：admitted=1、ended=1、completedCount=0、
  rate=0；单个 cancelled：admitted=1、ended=1、cancelled=1、rate=0。两例均零 Storage mutation。
  这是计划缺口，未否定 Task48.1 的 PASS，也未用 SQL 手工造状态探测产品缺陷。
  本机证据：`.git/validation-evidence/469ecc076c6efc660055f47277d7917a0b64a9aa/b-planning/existing-entry-metrics.json`。

## Implementation Scope / 开发指导

1. 在现有 SQLite metric read model 保留原始 due + definition Run once 人群、Task 身份去重、
   入库时间与本地月份窗口、同期比较和一次读取快照。以**当前耐久 Task.status** 计算 completed、
   failed、cancelled、pending/running，不能用 frozen 文件结果或恢复成功推导代替 Task 状态。
   completed 为成功数，completed+failed 为评估分母，三种终态之和为已结束，pending/running 为进行中。
   明确限定五态；未知/不可读 Task 证据不能落入 `NOT IN terminal` 后被伪装为正常进行中。
2. 在现有 API 文档提供明确的评估分母（建议 `evaluatedCount`，名称可按现有规范协调），
   `completedCount` 改为流程 completed 数；保留 `monthToDateTerminal` 的含取消语义。
   分母为零返回 `successRate: null`；查询失败维持 available=false 和 nextAction。
   独立 GET 与清单内嵌 metrics 使用同一口径；说明字段不能继续要求整理成功、非空或文件 Result。
   保留对现有消费字段的兼容；partial/uncertain/no-work 等附加事实不能成为成功率条件。
3. 分开成功率和“无工作”事实。保留无工作统计/提示时，复用已持久化的完整范围/首次执行证据，
   只在确证健康空范围或完整排除时显示；零成功、全失败、全跳过、未知或缺 Result 不证明无工作。
   不重新遍历 Storage、不新增结果存储、不为了证明统计而补写 Task/Result/历史。
4. 修改上述 TS model/normalizer 和卡片，并更新 API/组件/E2E fixture。按评估分母验证 rate 与
   completedCount 的一致性，拒绝零分母百分比、越界/不完整/自相矛盾的可用文档，不回退用 ended。
   卡片用一行简短中文区分分母与已结束数；沿用现有百分比精度、暂无统计、不可用刷新引导和响应布局，
   不增加常驻统计教程、页面、控制或恢复入口。前端不根据当前页文件/记录重算率。
5. 从现有 due / Run once / cancel / 四类 continuation 入口建立集成与浏览器证据；故障注入只放在
   正常旅程实际会经过的 Storage/Result/数据库边界。确认记录/Task Center 状态和文件事实未改变。
   所有读取零 mutation；先跑新增/受影响验证后交不可变 checkpoint，完整验收交 B。

只改必要查询/API/TS/卡片/fixture 与测试；不改调度准入、结算、容量、fence、pin、权限或 schema。
若实现确实需要触及这些安全/写入边界，先交 B 重评范围和 T4，不能按本 Task顺便重构。

## Acceptance Criteria

- [ ] due 与 definition Run once 均进入人群；Files/CLI 手动整理、普通文件操作、未准入请求和
  analysis/preparation 均不进入。合法同 Task 继续只更新当前状态贡献，不新增执行次数或更换原始 trigger。
- [ ] 8 completed、1 failed、1 cancelled 得 8/9（约 88.9%，UI 沿用既有精度），本月已准入/已结束均为 10，
  进行中为 0；增加取消、无关手动/普通任务不改变该比值，增加 Run once 按它自己的状态参与。
- [ ] completed 的全失败/partial/skip/ignore/未知效果/缺 Result/健康空范围/完整历史排除均计成功；
  不改文件结果、不补 Result、不改未知效果。全失败或零成功文件不能标成“无工作完成”。
- [ ] 无自动化、仅取消、取消加未结束、仅未结束自动化加已完成手动任务都没有百分比。
  一个真实 failed、零 completed 则是 0%；取消仍在记录/已准入/已结束中，不能被当成进行中。
- [ ] 同 Task 人工待办→决定→分析→确认→完成前后，统计按当前状态变化且执行次数不变；
  Task Center 与记录保持一致，原始开始/结束时间、尝试、文件和未知效果证据不被统计改写。
- [ ] 统计基于完整授权人群，列表筛选/limit/双向翻页不改变卡片；定义编辑/禁用/删除不抹去原始已准入来源。
  同一快照分子分母一致，本地月首边界和同期窗口保留已有半开区间/系统时区语义。
- [ ] metrics GET/内嵌文档、TS 校验和卡片对分母解释一致；无评估数据与不可用可区分，失败可按已有
  指引恢复读取，不伪造百分比。鉴权/多余 query/错误数据拒绝保持有界，不泄露内部错误或秘密。
- [ ] 桌面/窄屏可同时读到流程成功率、正确分母/已结束数和独立文件结果；刷新/筛选/展开不创建工作，
  同版本重开/重启保留统计来源和状态；没有已完成/未知效果重放或新执行权限。

## Required Tests

执行命令均从仓库根目录开始，标明 web 的命令在 `web/` 执行。新断言放入已有真实旅程测试，
小规模聚合边界可使用与真实 admission 一致的隔离 fixture；产品阻塞必须能追溯到实际入口。
不新增通用验证框架，不调用已退役 Job continuation，也不批量手工伪造产品不可达状态。

**Developer — 仅新增/变更与直接受影响测试：**

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_v2_automation_run_once.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_automation_operations.py'
.venv/bin/python -m unittest discover -s tests -p 'test_task_flow_status.py'
```

第一组扩展 metric API/真实 due、Run once、cancel、同 Task 恢复与重开断言；第二组覆盖清单内嵌
文档、权限/拒绝/读取失败；第三组保全既有五态结算和缺 Result 行为。窗口和不可用边界测试与
聚合测试一起补齐，不通过真实外部服务或生产数据库。

在 `web/`：

```sh
npm run test -- run src/entities/operations/automation.test.ts src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationRouter.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts --workers=1
```

对应 decoder 无效输入、统计卡片/不可用状态及生产构建真实 Python 页面；native spec 扩展本 Task
成功率旅程及桌面/窄屏检查。另对实际修改的 Python/Web 文件运行 Ruff/ESLint/Prettier 相应检查和
`git diff --check`。Developer 不运行全仓 Python/Web/E2E 或打包发布矩阵。

**B — 独立验收与 Slice final：**

- 审查正式 Task Base..候选完整 diff；首先从既有 API 重现本 Task两例并验证修复，再按 AC 的混合人群、
  等待/取消、缺结果、同 Task 继续、时区、分页/定义变化、不可用、零写入和重开检查。
- 运行上述受影响命令；在 `web/` 再运行
  `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-run-once.python.spec.ts --workers=1`，
  与 workspace 分为两次独立命令/全新 harness，不共享可变样本和状态。保留原断言/timeout/失败日志。
- 本 Task 只读跨层改动按 T3；Slice48 最终验收仍为 T4。若此 Task PASS 后 RO-1–4/全部 surfaces 已满足，
  停止规划，B 在最终候选执行 workflow §6 的适用 full/native/wheel/container/restart/security 门禁并交
  Closure Packet，A 才能审查 Slice Base..Implementation Head 和关闭。不能以 T3 代替最终 T4。
  已有匹配 B 结果可依 workflow 复用；变更查询/API/Web/build 输入后，旧 Task48.1 全量/制品结果
  不能直接当作新候选的全量/制品通过。测试环境/旧脚本适用性由 B 处理，不额外造 Developer Task。
- 各轮先分配分析/代码审查与测试预算，测试累计执行时间必须小于该轮实际总工作时间 50%；
  记录实际时间，不靠等待凑比例。预算不足则保留必需门禁 pending，后续验收轮完成；不删断言、
  不降测试级别或先判 PASS。草案规划时两次最小复现约 0.14 秒，未跑全套产品测试。

## Non-goals / 交接与复核

不重做 Task48.1、八视图/四类恢复/执行记录布局，不新增度量页面、执行/恢复入口、调度器/队列、
Provider/Storage 操作、旧任务迁移或跨版本支持；不改 CURRENT、Slice/Roadmap/Progress 或接受历史。
可见统计不一致是本 Task 问题，退役脚本、可选美化和通用过程工具不自动成为产品阻塞。

## Developer Completion Report

NOT STARTED。完成后提供候选完整 SHA、Status READY FOR B REVIEW、实际变化及受影响命令的
真实结果/失败/风险；完整验收待 B，不要求 Developer 提供全量证据包。

## B Review Result

```text
Reviewed: NOT SUBMITTED
Decision: NOT REVIEWED
Acceptance runs: PENDING
Task blockers: NOT ASSESSED — no implementation candidate
Slice Required Outcomes / Surfaces all satisfied: NO — RO-4 metrics remain
Next: DEVELOPER IMPLEMENTS TASK48.2
```

B 收到候选后对完整 Task Base..Head 独立给 PASS / FIX REQUIRED；返工留在同 Task，
Task PASS 后重评全部 Slice 结果。当前 RO-1/2/3 及记录状态部分沿用 Task48.1 PASS；
RO-4 成功率仍未交付，Slice48 不能送 A 终审。激活不是实施完成或验收通过。
