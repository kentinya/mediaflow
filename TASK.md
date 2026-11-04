# Task49.1 — 来源范围正确的列表一键运行

Authority: committed ACTIVE [Slice49 Contract](SLICE.md) at
`3cdc82678f693b4d7e4fb0b2a5efde42b47fc3d5`；
[Development Workflow](docs/development-workflow.md) 是唯一生命周期/测试/审查依据。
本助手按用户要求代行 **B 规划/激活确认职责**；本轮不担任 Developer、不做 B 验收或 A Final Review。

```text
Task ID: 49.1
Task Type: SLICE
Parent Slice: 49
Status: PLANNED
Task Base: 129d1c060dea05a91755dbd2ed70632f09655fd4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Planning Authorization: USER REQUESTED B SUBSTITUTE; DRAFT CONFIRMED AGAINST ACTIVE CONTRACT
Implementation Authorization: USER ACTIVATED TASK49.1; DEVELOPER MAY IMPLEMENT THIS TASK ONLY
```

## Activation confirmation

用户明确要求激活 Slice 和 Task。A 已先在 `3cdc82678f693b4d7e4fb0b2a5efde42b47fc3d5` 提交 ACTIVE Contract；
本 B 随后确认原草案 `9d70d0c211db1403bbcf536d8e619672ffd8b3d1` 的 Goal、Implementation Scope、
12 项验收和受影响/完整测试分工均仍位于该 Contract 的 RO-1 / RO-2 内，原 Task Base 至当前
生产代码/测试/harness 无变化。原 Task Base `129d1c060dea05a91755dbd2ed70632f09655fd4`
与原 Slice Base `02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e` 不变；不借激活重设起点或
扩大 Task。现转为正式 **PLANNED**，可由 Developer 按本 Task 开始，尚未进入 IN PROGRESS。
本次只完成激活，不运行实现、验收或下一 Task。

## Goal

完成 Slice49 **RO-1 / RO-2**：操作者从自动化列表对已保存定义点击一次“运行一次”，在原列表
看到提交/受理/拒绝/未知反馈，实际受限来源能被 Worker 正确处理。整个资源库不再因内部尾
斜杠拼接失败；删除编辑页运行按钮，将原未决运行请求的核对收敛到列表。停用定义仍可手动
运行一次，计划与启用状态不变。正常空范围、Task 流程失败、独立文件失败和人工待办各自如实显示。

追踪：`V2-AUTO-015`、相关 `V2-AUTO-004/011/012`、`V2-TASK-001–014` 的既有 V2 含义；
Slice49 AC-1–6 为本 Task 的主要验收，AC-13–16 取本次实际影响的权限、执行、回读与验证部分。
本 Task 不交付 RO-3 的统一编辑卡片或 RO-4 的创建可选启用，不会据此宣布 Slice 完成。
完整适用旅程/契约已读：[TARGET journey](docs/product-experience.md#target--automation-forms-and-direct-run-once-slice49-active)、
[TARGET architecture](docs/architecture.md#target--automation-forms-and-direct-run-once-slice49-active)、
[CURRENT Automation journey](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)。
保留 `UX-001–007/010`、适用 `REQ-TASK-005–010`、`REQ-SCHED-004–007` 和 `REQ-SAFE-001–009`。

### Actual code and baseline gaps

- `mediaflow/application/automation_run_once.py:admit_execution` 将库根和空子范围直接 join，
  非空库根 `Incoming` 得到 `Incoming/`；`automation_definition_execution.py:_resolve_scope_root`
  用严格相对路径规则拒绝该 Task 范围。已有核心 API 测试的 `storagePath` 为空，没覆盖该组合。
- `AutomationListPage.tsx` 的 `onRunOnce={openDefinition}` 只导航详情；列表没有真实命令状态。
  实际运行、请求生成和 principal-scoped 未决上下文都在 `AutomationLifecyclePage.tsx`，
  而本 Slice 明确要求删除编辑页运行按钮。不能只删按钮，把未决核对能力一起遗失。
- 列表已提供 Active `revisionId/version/revisionSequence` 和 backend action availability；
  其 operator 投影刻意不含 digest/fingerprint。现有 Run once API 允许用 revision ID +
  实际 sequence/version 校验所见快照，服务端另核对快照完整性；但 `api-client.ts` 在
  提供 expectedRevisionId、未提供 digest 时会补空字符串，应按实际可选字段契约处理。
  不需把内部证据暴露到列表，也不能省略全部版本条件或点击后读取新版再偷偷绑定。
- 编辑页的旧 session key 为
  `mediaflow.operations.automation-run-once-intent:<principalIdStorageSegment>`，只保存一条请求；
  列表需能接续它，并为多行提供独立且有界的状态，不能覆盖另一行的未知请求。

本轮隔离 API→SQLite→Worker 对照：非空库根/整个库 HTTP202 后 Task failed，Storage 读取0、
变更0，记录“来源范围设置无效”；空库根/整个库 completed/noWork。同次探针只提交所见
revision ID/version 即可准入，过期 version 为409且 Task数0。源码/测试/harness与原调查
基线间的 diff 为空，原浏览器“列表只导航”证据仍匹配。可复现触发记录如上；原始本地材料：
`.git/validation-evidence/129d1c060dea05a91755dbd2ed70632f09655fd4/task49.1-planning/`，
及 Slice49 记录的先前调查目录。调查不是修复验收，不声称已核对用户运行库或远程证据。

## Implementation Scope

复用现有 Run once 服务、Task admission/Worker、API client、列表和局部 session 机制。
可改必要的 `automation_run_once.py` 及实际受影响的范围消费代码；Web 列表/行组件、
生命周期页的运行相关代码、API client/model（如确需）、命令 session/helper 与对应测试。
仅允许必要的测试 fixture/harness 扩展，不引入产品专用测试端点或第二工作存储。

1. **先固化真实入口缺陷。** 在现有 `test_v2_automation_run_once.py` 增加非空库根＋整个库
   的 API→Task→Worker 用例和有效根/子范围矩阵；列表用例必须点击并检查真实准入，不只
   断言按钮可见。初始失败应指向已确认的拼接/导航缺口，不能手写终态冒充 Worker。
2. **修正来源组合，保留严格校验。** 优先在准入生产者规范化已经验证的库根＋子范围拼接
   结果，使持久 Task 与既有 Worker 校验含义一致；只在必要时调整受影响的共享消费逻辑。
   使用已有规范化/约束能力，不新增一套路径体系；不通过删除所有斜杠、trim文件名字符或
   放宽 `..`/绝对路径来修复。覆盖空、非空、多层、中文空格库根，整个库/子目录及健康空
   和有媒体来源；保留 Storage 身份、精确源路径和 immutable pin。due 做同范围对照。
   不迁移旧 Task、不改历史失败记录、不自动重跑原失败或不确定效果。
3. **接入所见保存定义的明确命令。** 使用列表同一次读取的 definitionId、Active revisionId
   和 `revisionSequence`（按服务已有 sequence/version 规则），形成受控版本条件；后端仍
   核对快照完整性和当前 `EXECUTE_MANUAL_ORGANIZE`。客户端应正确省略未提供的可选 digest，
   不发送空字符串；已有调用明确提供的 digest/fingerprint 仍按原规则验证，不能删掉其
   校验。优先复用既有投影/API，不新增授权 token，也不把内部 digest/fingerprint搬入列表。
   缺少真实版本/身份时显示无法提交；禁止从表单未保存值推导、无条件提交或静默改绑最新版本。
   这里约束列表命令的所见版本，不把原有直接API的可选条件改成新的强制字段。
4. **把运行请求与核对从编辑页移到列表。** 提取最小局部 helper/session（建议
   `automation-run-once-session.ts`），将生成请求、提交、确定拒绝和未知核对衔接好。
   在 POST 前确认 principal、可用随机请求身份及可跨刷新保留的上下文；能力不可用时
   明确阻止本次提交，不能发出随后无法核对的请求。按 principal/definition/request 隔离
   多行忙碌/未知状态；有界保存且不覆盖/静默丢弃未决项，不建通用命令框架。
   读取旧编辑 key 的合法记录，保留原 request/identity，只做显示和精确 GET核对，不POST；
   校验不合法旧值并有界说明，不能把它变成新的运行请求。读取/重连/登出清理符合现有身份规则，
   旧异步响应不得清掉新登录身份或其他行的上下文。被筛选/翻页隐藏的未决项仍有列表内
   可达的核对提示，不强迫操作者丢失当前列表条件。移除编辑页运行按钮及其独占事件/状态，
   保留启停、保存、复制、删除和既有未决发布的行为；已提交运行的核对入口在列表接续。
5. **完成原列表反馈与回读。** 行按钮一次点击直接 POST，没有前置跳转、选文件或第二次
   初始确认；后台完整遍历/分析/计划/校验不变。受理后留在列表，保留已提交筛选、页、滚动
   与焦点，刷新真实最近运行/统计；显示“已提交”及精确本次运行/Task的主动查看链接，
   不声称已完成或文件成功。重复点击在同步提交窗口及未决状态下不能再准入；后端继续
   依据原 request 去重。确定拒绝用普通中文说明阶段/状态/效果和下一步，允许明确纠正后
   新提交；旧版本拒绝先刷新所见保存值，不自动重试。status0/5xx/畸形响应或异步异常按
   未知保留原请求并核对；“没找到”不证明未受理，不自动新建请求，不用放弃按钮掩盖安全约束。
   “查看任务”直接打开该 Task 的现有 Task Center 详情，不新增中转页、运行详情或恢复系统；
   既有 Run once 只读地址仍可正常读取原工作。
   用户已明确要求反馈人类可读、好看：使用现有页面的字体、颜色、间距、圆角和按钮风格，
   在对应行操作附近以紧凑状态文字/标记呈现，提交中用克制的忙碌提示；必要原因和下一步
   就近清楚显示，不堆技术说明、不遮挡操作或靠截断隐藏原因。与名称/路径和相邻行对齐，
   窄屏可自然换行且无页面横向溢出，状态变化不造成明显跳动；以清楚文字说明状态、图标辅助，
   不只依赖颜色，键盘焦点和现有减少动效设置仍有效。具体布局由实现按实际页面决定。
   普通界面不使用“丢响应”“原请求”“幂等”“principal/fence”等内部术语，不展示请求编号、
   revision/digest或原始错误码，也不让用户复制/填写这些信息。建议短文案：提交中“正在提交…”，
   已受理“已提交”配“查看任务”，确定拒绝“未能提交”配具体原因；没收到确定回复时写
   “暂未收到回复”，说明“任务可能已提交，请先查看提交结果”，动作为“查看提交结果”，
   查询中“正在确认…”。查询只读取刚才那次提交的结果，不再次运行；未查到不显示“未启动”。
   文案可随页面润色，但不能把未知写成失败，或把受理写成文件整理成功。
6. **补齐受影响验证并交候选。** 原生浏览器从真实列表启动、完成实际 Worker 和独立结果
   回读；把原先从编辑页启动的相关测试/fixture改到列表，保留其权限/重启/四类恢复等原有
   有效断言，不删测或改弱断言。必要注释/直接相关的过时导航说明随代码校正；TARGET不能
   提前写成 Slice已接受的CURRENT。Developer 完成下列受影响检查后提交一致 checkpoint，
   `READY FOR B REVIEW`；全量与产物证据由 B 负责。

### 列表提交反馈与现有 Task 状态的边界

“运行一次”始终接入现有 Task admission→Worker→整理→Result 链路。列表只补齐这一次点击的
提交反馈，不新增 Task 状态、工作流、常驻状态列、独立进度条或恢复面板。

| 发生的事情 | 列表显示与行为 |
|---|---|
| 点击后等待接口回复 | 按钮短暂显示“正在提交…”并防连击，不跳页面。 |
| 接口确认受理并返回 Task ID | 立即结束按钮忙碌状态，给短暂“已提交”提示及“查看任务”入口，刷新现有最近结果/统计；不等 Task 执行完成才结束提交反馈。 |
| Task 后续排队、运行、等待人工处理或结束 | 状态与结果继续读取现有 Task、列表最近结果及执行记录；不从本地提交提示推断或维护另一份运行状态。 |
| 接口明确拒绝且本次没有准入 | 简短显示“未能提交”及具体原因/下一步，不把未创建的工作伪装成失败 Task。 |
| 网络中断等导致没有确定回复 | 保留刚才那次提交身份，通过现有精确查询接口找回已受理 Task；必要时显示轻量提示和“查看提交结果”。查到后展示同一 Task，不再次创建；查询仍无结果时不能断言未受理。 |

正常路径是“点击→短暂加载→提交提示”，没有每次必经的额外核对步骤。已提交不代表
Task 已完成或文件成功；异常查询是提交层的网络恢复，不是新的整理阶段或 Task 生命周期。

## Acceptance Criteria

| ID | Required proof |
|---|---|
| T49.1-AC1 | 非空库根＋整个库不再保存会被自身 Worker 拒绝的来源表示；空/多层/中文空格根、整个库/子目录、空和非空来源经真实 API→Task→Worker 得到精确受限范围。due 对照不回归；不是只测字符串。 |
| T49.1-AC2 | 绝对/穿越/越界子范围、缺失/禁用引用、篡改范围或固定上下文均拒绝；不扩大源/改变 Storage或重写旧pin。来源目录无法完整发现/真实超限仍 failed且零前缀执行；健康空 completed/noWork；文件技术失败独立保存，正常结束且无待办的流可completed。 |
| T49.1-AC3 | 真实列表一次点击→一次POST→一个Task，无预先导航/文件重选/第二初始确认；停用定义有执行权限仍可运行，enabled/due不变，未保存编辑值不执行。正常有媒体用例证明真实规划和Storage效果，不以202冒充完成。 |
| T49.1-AC4 | 列表提交使用该行同次读取的已发布定义/Active版本，旧revision或sequence拒绝且零新Task；不绑定后取新版。列表仍无digest/fingerprint/raw plans/secrets；原本提供内部证据的调用保留后端校验，列表缺失身份/版本不发命令，直接API的既有可选字段契约不变。Draft-only/只读/不可用状态无可执行漏洞。 |
| T49.1-AC5 | 列表按上述提交反馈表就近显示简短中文，拿到 Task ID 即结束按钮忙碌并短暂提示，不能等 Task 完成才结束；后续运行状态复用现有 Task/最近结果/执行记录，不增常驻状态列或独立进度。主动“查看任务”直达原 Task Center 详情。风格统一、布局/窄屏/焦点可用且无明显跳动，保留筛选/页/滚动；隐藏行的未决提交仍可查询，读取不准入工作。 |
| T49.1-AC6 | 连击/延迟响应/等价重复请求/容量竞争无重复Task或孤儿Task，其他行反馈独立；成功后后续新的明确运行仍可用。缺少随机身份、principal或可持久核对上下文时阻止POST并给可执行说明。 |
| T49.1-AC7 | 权限不足、队列满、过期定义、不可用读取有普通中文原因与安全下一步；未知提示说明“可能已提交”，以“查看提交结果”等可理解动作查询原提交，不叫用户辨认“丢响应/原请求/幂等”等术语或复制内部编号。未知与明确拒绝不混淆，无自动POST重试、隐式权限/快照替换或原始异常/错误码暴露。 |
| T49.1-AC8 | 丢响应/5xx/畸形响应经关闭/刷新/重连后核对同一principal/definition/request；旧编辑key记录亦接续到列表。只核对不重发，未找到仍未知，不重复Storage效果；身份切换、旧回调、多个未决行和不合法session值不串数据/清除他项。 |
| T49.1-AC9 | 编辑页运行按钮消失；既有保存、启用/停用、复制、删除与发布核对保持现行行为。本Task不提前改造编辑卡片或创建启用；Run once状态/TaskCenter读入口仍有效。 |
| T49.1-AC10 | 共享源所有权、固定快照、容量/claim/fence、实际稳定性、完整遍历上限和源历史过滤保持；只有OrganizerExecutor变更Storage。四类原生决定→分析→摘要→明确继续仍在同一Task；成功/不确定兄弟效果不重放，C使用Naming A/Classification A仍为C的回归通过。 |
| T49.1-AC11 | 原运行在TaskCenter、执行记录、最近运行和成功率中计一次并保持五态流/独立文件结果；提交提示不得覆盖或推断 Task 状态。健康空completed、真实流程失败、文件失败、人工待办与取消不混淆；核对/刷新/同Task继续不新增运行或改原次数/时间/结果。 |
| T49.1-AC12 | Fresh新任务、同版本重开/重启和原生桌面/390px窄屏完成上述真实入口、失败/未知核对及合法后续查看；无外部生产服务/用户媒体。B按T4完成匹配候选的完整与适用产物门禁并记录实际失败/skip/限度，Task PASS不等于Slice CLOSED。 |

## Required Tests

测试等级与分工仅按 [workflow §6](docs/development-workflow.md#6-test-levels)。
下面是实施/验收计划，不是本次激活已运行的产品验证结果。新测试文件应随本Task实现建立；
命令中的实际变更文件、候选wheel/image/证据路径在交接/验收时绑定精确值。

### Developer — affected tests

1. 仓库根：`python3 scripts/check_governance.py`（Developer实施前执行）；
   `PYTHONPATH=tests:. .venv/bin/python -m unittest -v test_v2_automation_run_once test_automation_task_admission test_v2_automation_operations`。
   在这些真实应用测试中增加 AC1–4/6/10/11 的根范围、完整性、所见版本、权限/容量/去重与
   文件/流程独立用例，复用临时Storage/合成Provider；保留原有效覆盖。若实际修改其他
   共享范围/consumer，再补其直接受影响用例并在报告说明，不把全仓发现当affected。
2. `web/`：`npm run test -- run src/entities/operations/automation.test.ts src/entities/operations/run-once.test.ts src/shared/api/api-client.test.ts src/features/operations/AutomationListRunOnce.test.tsx src/features/operations/automation-run-once-session.test.ts src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationRouter.test.tsx`。
   新建的列表命令与session测试证明实际payload/版本、重复与未知响应、旧key、身份切换、
   不可用存储、隐藏行核对和键盘/上下文；不只断言helper内部值或按钮可见。
3. `web/`：`npm run build`，随后
   `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-run-once.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-workspace.python.spec.ts --workers=1`；
   `npm run test:e2e -- tests/e2e/automation.spec.ts`。
   这些既有文件直接消费编辑运行入口/列表，迁移起点但保留原执行/恢复断言；扩展现有
   Python harness隔离fixture，覆盖非空库根整体来源、列表真实一击、忙碌、未知响应后实际
   核对与重启不重放。至少保留并实际检查桌面/390px窄屏列表反馈与主动查看截图。
   原生视觉检查涵盖忙碌、受理、确定拒绝与未知反馈的实际展示/查询动作；验证短文案、
   风格一致、排版/换行/焦点/减少动效及无明显跳动，不能只数DOM节点或断言按钮存在。
   明确验证：已有 Task ID 而 Worker 尚未完成时，提交按钮已结束忙碌；后续状态来自现有
   Task 回读。“查看任务”直达该 Task 现有详情，没有新增整理步骤或本地运行状态副本。
4. `web/`：`npm run typecheck`；对实际变更的TS/TSX运行 `npx eslint <changed-web-files>` 和
   `npx prettier --check <changed-web-files>`。仓库根对实际变更Python文件运行
   `.venv/bin/ruff check <changed-python-files>` / `.venv/bin/ruff format --check <changed-python-files>`；
   `git diff --check`。未改Python消费者不机械扩大测试；失败/skip如实报告。

Developer 到此提交候选，不承担全Python/Web/E2E或wheel/container矩阵，不等B全量才交接。

### B — acceptance and full regression

- 先独立检查精确 Task Base..candidate、复现最关键场景：非空库根/整个库从真实列表启动后
  执行或健康空完成，错误范围/不完整仍拒绝，丢响应不重复、编辑入口移除且启停保留。
  可达 blocker先返回同Task FIX REQUIRED，不先浪费完整门禁。
- 对同一候选按 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
  完成T4：全Python/全Web单元/默认浏览器、质量与example/dependency、build、权限/范围/
  fixed pins/fences/源历史/四类恢复/C→A/不重放，以及适用wheel/container安全/重启验证。
  命令与所有权不重抄到Developer。原生专项沿用上列三个Python浏览器文件（单worker）；
  补足实际根矩阵、故障/并发和所需回读证据，保留真实Storage trace、Task/result与截图。
- 产物沿用共享的 `.venv/bin/python -m pip wheel . --no-deps -w dist`、
  `.venv/bin/python scripts/wheel_smoke_test.py <exact-wheel>`、
  `.venv/bin/python scripts/docker_release_security_smoke_test.py --image <exact-candidate-image>`。
  B准备一个保存在 `.git/validation-evidence/<candidate>/b-task49.1/` 的独立installed probe，
  用临时根和合成Provider构造与AC1–4/10/11相同的API→Worker范围/权限/去重/重开用例，
  不导入仓库生产代码或写入伪造终态。命令形态：在source外cwd运行
  `<wheel-venv>/bin/python <evidence>/installed-run-once-probe.py`；对精确镜像运行
  `docker run --rm --network none --mount type=bind,src=<probe-dir>,dst=/proof,readonly --tmpfs /tmp:rw,mode=1777 --entrypoint python <exact-candidate-image> /proof/installed-run-once-probe.py`。
  probe绑定实际打包模块身份并验证fresh和同版本重开/重启，不把source或旧dist当产物通过。
  新probe和完整产物证据由B承担，非Developer额外功能任务；不要求生产Storage/Provider。
- 记录候选SHA、命令/cwd、数量/skip/失败、证据路径、所见配置/产物身份和验证限度。
  匹配运行可按workflow复用；不把调查或本轮文档检查当产品验收。Task PASS后仅重新评估
  Slice结果，不自批Slice、本次激活不创建下一Task。

## Non-goals

不实现共用创建/编辑卡片、创建时可选启用、后端create/enable编排或复制/删除/详情重做；
不改已接受五态流/文件结算、统计口径、四类恢复、源历史策略、队列/调度/设置或Storage能力。
不增加初始确认、强制规则预检、授权token手工操作、通用命令框架、批量运行或第二工作模型；
不恢复退役产品或自动重放历史。不为修复迁移旧失败/任务、重写pins/Result/配置digest，
不动生产媒体/运行数据库/私有配置。A的Slice/Roadmap边界和既有接受事实不变。

## Planning workspace（原规划记录）

仓库 `/Users/songzhidong/mediaflow`，branch `main`，本轮起始HEAD/Task Base如上，治理预检PASS，
tracked工作树干净。预存untracked OS/日志、`15`、自动化参考图与output等完整状态保留在
本轮本地证据的 `workspace-before.txt`，全部保留/不入提交。工作区/Git可写；本轮仅改根
`TASK.md` 规划草案，Slice/Roadmap/Progress及产品代码不改，不push/部署/改写历史。

## Developer Completion Report

未开始：无实现checkpoint、无受影响产品测试结果，不能宣称READY FOR B REVIEW。

## B Review Result

未开始：无已提交实现候选、无B产品验收；激活不构成PASS或Slice关闭。

## Activation workspace

本轮从 `main` / `9d70d0c211db1403bbcf536d8e619672ffd8b3d1` 开始；A先提交上述ACTIVE
Contract，本B确认前治理检查PASS、tracked工作树干净，任务实质计划不变。预存untracked
OS/日志/参考图/output及`15`全部保留、不入提交；本轮状态清单在该起始HEAD本地
`slice49-task49.1-activation/workspace-before.txt`。本B只将根Task正式化，未改产品代码、
Slice结果边界或历史接受；未读取用户数据库/私有配置/生产媒体，无push/部署/历史改写。

## Accepted baseline reference

上一独立修正 `BUG-AUTO-CREATE-UX` 保持 B PASS：Base
`2aa791a6b66d968f473a6875fe2ebf072c5500df`，Reviewed Head
`ea127459ace765857ae8386c1d0df1610117185b`；完整计划/验收保留在
`b0bbc8125d06057d042b139469bb170c3284cc79:TASK.md`，不作为本 Task 的验收。
