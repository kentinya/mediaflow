# NO ACTIVE IMPLEMENTATION TASK

Task48.1 — **任务流程结束与文件结果分开** — 已通过 B 独立验收（2026-11-04）。
产品检查点 `449817e158ef2278f809c4f8d243eb079415b6eb`；含 B 验收脚本适配的检查点
`6f2115d1033779aa2d21a7f0b6ebd9f558f66345`。完整 Task 计划、范围、验收和 Developer
交接保留在上述检查点的 TASK.md；本文件记录当前完成决定和可核验的 B 证据。

Slice48 仍 ACTIVE。剩余 RO-4 自动化成功率未交付；本次仅验收 Task48.1，
没有新的实施授权，不计划/启用下一 Task，不关闭 Slice。

以上为 Task48.1 验收轮的停止点。下方新增 Task48.2 **规划草案**（2026-11-04），
仅供后续实施决策；当前仍无 ACTIVE implementation Task，未扩大合同的实施授权。

### B final Task review

```text
Reviewed Base: 4f11762d617d50555f3b106357e8f41988f7c2f9
Product Head: 449817e158ef2278f809c4f8d243eb079415b6eb
Reviewed Acceptance Head: 6f2115d1033779aa2d21a7f0b6ebd9f558f66345
Decision: PASS — 2026-11-04
Task blockers: NONE; B48.1-01 / B48.1-02 / B48.1-03 RESOLVED
Slice Required Outcomes / Surfaces all satisfied: NO — RO-4 metric calculation remains
Next: NO ACTIVE IMPLEMENTATION TASK; REMAINING SLICE OUTCOME AWAITS AUTHORIZATION
```

B 独立审查完整 Base..Head，并从真实入口复现原阻塞，确认：

- Run once 的部分成功、失败分别展示；直接 API 失败文件计入已处理进度。
- CLI 源目录/子树不能完整读取时保存流程失败和原因，不执行可读前缀；正常空范围仍完成。
- Files 选择 → 识别决定 → 分析 → 精确摘要确认 → 真实 Worker/Storage 移动 → 文件结果发布
  失败后，Task completed、Result 仍缺失、队列名额为 0；保留未知效果，三次后续 Worker 零重放。
  仍有兄弟待办时回到同 Task 人工等待；取消优先；真正未结束/终态不可写时不编造完成。
- 当前八视图、四类恢复、自动化记录、原库普通操作及同版本重开/重启保留原意图、pin、
  源所有权、已完成/未知事实。任务流程完成没有被当成所有文件整理成功。

#### B 实际验证

证据根目录（本机忽略存储，不声称远程可访问）：
`.git/validation-evidence/449817e158ef2278f809c4f8d243eb079415b6eb/b-review/`。
起始分支 main、HEAD 为 Product Head，tracked 干净、工作区/Git 可写；原有未跟踪
OS/log/reference/output 文件和 `15` 保留，不纳入提交。所有产品验证使用隔离数据/临时
Storage、fake/本地 Provider，不使用用户数据库/媒体或真实外部服务。

| 验证 | 实际结果 / 原始证据 |
|---|---|
| 根目录 `.venv/bin/python -m unittest discover -s tests` | 2579 项运行，7 skip，0 failure/error，319.790 秒；`python-full.log`。7 项为既有外部服务/耐久环境可选项，未当作通过。 |
| Python 质量/配置 | Ruff 全仓格式/检查、compileall、pip check、两个 example config validate、治理与 Base..Head whitespace 均通过；`python-quality.log`。禁用依赖查询无匹配。 |
| `web/` 完整质量/构建/单元 | typecheck、lint、format:check、build 通过；88 个文件、1270 项单元通过；`web-quality.log`、`web-full.log`。 |
| 默认浏览器 | `npm run test:e2e -- --workers=1 --output=<evidence>/e2e-default`，253 通过；`e2e-default.log`。 |
| 真实 Python 浏览器 | operations-inventory 43、task-center-visual 2、source-history 1、task-flow 2，共 48 通过；原 `e2e-python.log` 的首文件 43 项结果及 `visual-isolated.log`、`history-isolated.log`、`flow-isolated.log`。 |
| Automation / 普通文件浏览器 | automation-workspace 8、automation-run-once 5、direct-files 22，均通过；`automation-isolated.log`、`runonce-isolated.log`、`direct-isolated.log`。 |
| wheel / 源树外消费 | pip wheel --no-deps 构建并运行 `scripts/wheel_smoke_test.py <exact-wheel>` 通过，含源树外临时安装消费者；`wheel.log`、`artifact-identity.json`。 |
| 同一候选 Docker image | build、`docker_files_transfer_lifecycle_smoke_test.py`、`docker_restart_fault_smoke_test.py`、`docker_release_security_smoke_test.py` 均通过；对应 `docker-*.log`。 |
| 容器内当前恢复/结束处理 | 直接运行已安装 `/usr/local/lib/python3.13/site-packages/mediaflow`，6 个真实 Files/Task API 集成用例通过，覆盖同 Task 继续、缺 Result、兄弟、取消、不可用及不重放；`docker-installed-current-flow.log`。未挂载源树的 mediaflow 包。 |
| 原反例 | 原 B `manual-missing-result.py` 原样复跑通过；`manual-missing-result.log`。 |

真实浏览器按各原配置顺序执行；除 inventory 复用已完成的首文件结果，其余 spec 每次启动
全新隔离 Python harness，`--workers=1`，命令、spec 和输出目录写在相应日志首部。
实际检查桌面/窄屏截图：混合结果的流程完成和失败事实能同时阅读，进度与成功率分开，
原库弹窗和四类问题区可读；截图保存在 `flow-isolated/`、`visual-screens/`、
`automation-isolated/`、`direct-isolated/`。没有要求额外页面/控件或重做既有布局。

验收输入身份：image `mediaflow:task48-1-6f2115d10337`，
ID `sha256:85154f5b4668936745c887b4d7d7e716a639a26c3d708f032079942d3dc260d3`；
wheel digest 和精确路径见 `artifact-identity.json`。
`449817e1..6f2115d1` 的产品、单元/native 测试、native harness、依赖/config 输入无变化，
对比证明见 `source-equivalence.txt`；新改的验收路由和脚本另有静态检查，浏览器/容器使用新检查点。

#### 失败、适用性与限度（不隐藏）

- 首次 Docker 启动失败是 daemon 看不到系统临时目录。确认项目目录可挂载后，将
  `TMPDIR`（及恢复脚本的 `MEDIAFLOW_SMOKE_TEMP_DIR`）设为证据目录下的隔离 docker-tmp，
  重跑现行 transfer/restart/security 证明通过。初始失败日志保留。
- 多个 Python browser spec 共用一个可变 harness 时，前三个文件已移动样本/留下记录，
  后续 3 项失败（缺样本、seed 被拒、全局行数大于 1）。保持所有断言/timeout 不变，改为
  每个文件全新隔离实例后通过。不是产品重试或放宽断言，原失败及 trace 保留。
- 旧 `docker_task_center_recovery_browser_proof.py` 仍调用已接受47退役的独立 Job continuation，
  返回 **410 job_continuation_retired**，故该旧旅程不适用于当前合同，未记为通过。
  未恢复旧入口，也未以不可触发的 seed 状态要求产品返工；当前同 Task 恢复改由上述
  43 项 native 真实旅程、容器内 6 项安装包集成和四服务重启/安全证明覆盖。
  6f2115d1 只修正测试路由和 Task 状态断言，不宣称已迁移整个旧恢复脚本。
- 构建保留既有 bundle-size 提示；Python 的 ResourceWarning、Web 测试环境提示保留。
  没有删除/隐藏 skip、增加自动重试或放宽 timeout。
- 本轮完整门禁及旧脚本诊断使测试时间安排未满足用户要求的低于总耗时 50%；如实记录，
  不用降低验证要求或额外耗时凑比例。后续先核对脚本适用性与隔离边界，再分配测试预算。

#### 全部 Slice 结果重评和停止点

RO-1/2/3 及 RO-4 的执行记录状态/独立文件事实部分已满足本 Task，当前无 Task 阻塞。
RO-4 的自动化成功率仍使用旧计算口径：completed/(completed+failed)、取消排除、无评估数据
和分母解释等 AC-9/10 **尚未交付**。本次截图里的旧成功率不能当作新口径已验收。
因此仅 Task48.1 PASS，Slice48 仍 ACTIVE、未准备 A Final Review；不改 CURRENT、SLICE、
Roadmap/Progress 或已接受历史。不预先实现或启用下一 Task，等待对剩余结果的授权。

## Task48.2 规划草案 — 自动化成功率按 Task 流程统计

**DRAFT / PLANNING ONLY — 本草案不授权实施。** 本轮用户要求 B 基于真实代码规划；
已提交合同的实施授权仍限 Task48.1。启用后才替换根文件的 no-active notice，正式记录
Task 元数据；若期间出现产品改动，先重核其对本草案的影响，不能静默移动正式 Task Base。

```text
Proposed Task ID: 48.2
Task Type: SLICE
Parent Slice: 48
Draft Status: PLANNING ONLY — NOT AN ACTIVE TASK
Proposed Task Base: 469ecc076c6efc660055f47277d7917a0b64a9aa
Difficulty: Medium
Test Level: T3 — INTEGRATION
Planner / Reviewer: B
```

规划工作区：`/Users/songzhidong/mediaflow`，分支 `main`，起始 HEAD 为上述 proposed Base；
tracked 起始干净、工作区/Git 可写。原有未跟踪 OS/log/reference/output 文件和 `15` 全部保留，
不纳入 checkpoint；本轮只改 TASK.md。治理与 whitespace 检查通过，未改产品或运行全量门禁。

Authority：[已提交合同](SLICE.md) RO-4、AC-9/10；保全 AC-11/12/14/15。
需求 `V2-AUTO-012`、`V2-AUTO-005` 的成功率修订；完整旅程与技术边界见
[Product Experience TARGET](docs/product-experience.md#target--task-flow-status-and-automation-success-rate-slice48-active)、
[Architecture TARGET](docs/architecture.md#target--task-flow-status-and-automation-success-rate-slice48-active)。
保留 `V2-TASK-012–014`、`V2-AUTO-010/011`、`UX-001/002/003/006/007/010` 和
`REQ-SAFE-*` 的现有约束。Task48.1 的已接受状态/记录行为是本 Task 的基础。

### Goal / 完整用户旅程

用户进入“自动化”，从已保存定义“运行一次”，或等待已启用定义到期；随后查看本月执行次数、
成功率及执行记录。成功率只回答这些自动化 Task 的流程是否正常收尾。文件全部失败、部分完成、
跳过、忽略、效果未知、缺正式 Result、健康空范围、完整历史排除，只要 Task completed 都计成功；
记录仍独立显示文件结果。待人工处理仍未结束，用户沿现有任务中心决定→分析→摘要→明确继续，
回到自动化刷新时同一 Task 只算一次。用户确认取消后，该记录和已结束次数保留，成功率不计它。

真实 Task 流程失败计 failed；统计读取失败显示不可用及现有刷新/检查数据库指引，不能显示 0%。
读取、筛选、翻页和展开记录不执行工作；文件问题、未知效果及其现有安全下一步不因百分比变更而消失。

### 当前代码缺口与可核验证据

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
- B 在 proposed Base 复用 `tests/test_v2_automation_run_once.py::RunOnceApiTests` 的
  `journey/admit/execute/request`，调用现有 Run once、cancel 和 metrics API；只覆盖既有
  `_automation_now` 测试时钟。健康空范围 completed：admitted=1、ended=1、completedCount=0、
  rate=0；单个 cancelled：admitted=1、ended=1、cancelled=1、rate=0。两例均零 Storage mutation。
  这是计划缺口，未否定 Task48.1 的 PASS，也未用 SQL 手工造状态探测产品缺陷。
  本机证据：`.git/validation-evidence/469ecc076c6efc660055f47277d7917a0b64a9aa/b-planning/existing-entry-metrics.json`。

### Implementation Scope / 开发指导

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
若实现确实需要触及这些安全/写入边界，先交 B 重评范围和 T4，不能按本草案顺便重构。

### Acceptance Criteria

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

### Required Tests

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

- 审查正式 Task Base..候选完整 diff；首先从既有 API 重现本草案两例并验证修复，再按 AC 的混合人群、
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
  不降测试级别或先判 PASS。本规划轮仅两次最小复现约 0.14 秒，未跑全套产品测试。

### Non-goals / 交接与复核

不重做 Task48.1、八视图/四类恢复/执行记录布局，不新增度量页面、执行/恢复入口、调度器/队列、
Provider/Storage 操作、旧任务迁移或跨版本支持；不改 CURRENT、Slice/Roadmap/Progress 或接受历史。
可见统计不一致是本 Task 问题，退役脚本、可选美化和通用过程工具不自动成为产品阻塞。

Developer 正式交接只需候选完整 SHA、READY FOR B REVIEW、实际变化与受影响命令结果/失败/风险；
B 尚未收到 Task48.2 实施候选，**没有本 Task 的 PASS / FIX REQUIRED 产品结论**。
收到候选后对完整 Base..Head 独立给结论；返工留在同 Task，Task PASS 后重评全部 Slice 结果。
当前 RO-1/2/3 及记录状态部分沿用 Task48.1 PASS；RO-4 成功率仍未交付，Slice48 不能送 A 终审。
