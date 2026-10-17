# Task 45.3 — 分类恢复的同页计划摘要与确认继续

遵循 [Development Workflow](docs/development-workflow.md)，从属于已提交的
[Slice45 Contract](SLICE.md)。规划/审查读取 [B 经验](docs/agent-experience/task-planner-reviewer.md)，
实现读取 [Developer 经验](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.3
Parent Slice: 45
Status: READY FOR B REVIEW
Task Base: 8f5cf4e284766bcc8894817d7640231e85050fb2
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Next Action: B REVIEWS THE TASK 45.3 R2–R5 CORRECTION AT THE NEW IMPLEMENTATION HEAD
```

## Goal

操作者从识别、元数据、分类、冲突或失败恢复列表进入该任务的问题文件，保存合法决定或修复
依赖，经显式安全分析在当前处理界面查看新计划摘要，再选择就绪子集明确“确认继续整理 N 项”，
跟踪关联 Worker 执行及逐项结果；安全暂停的整理工作需要重新授权时走同一摘要/确认旅程。
完成 **RO-3 / S-3、S-4**，**RO-4 / S-5 的同页继续授权及异常连续性**，以及必需的
**RO-6 / S-6 共享编排与验证部分**；不改变 RO-1/2 已验收行为。

适用要求：V2-OPS-007–010/012，V2-UX-001–003，V2-AUTH-001–003，V2-SAFE-001，
UX-001–007/010、REQ-RECOVERY-*、REQ-TASK-*、REQ-ORG-*、REQ-RESULT-*、REQ-SAFE-*。
用户流转以 [最终页面规范第 4–5 节](docs/task-center-page-spec.md) 和 Contract RO-3 为准。

## Why This Task Exists / Previous Review

### Task45.2 B PASS — 2026-10-17

- 审查范围：`1fbb709e9273d9b6b7fa3648a1eb2cfceaf0b743..da4b70c9c9ccfe92d8b407a215aef9e893e1e83f`。
  Report Head 为本 Task Base；候选至报告只有 TASK.md，无 executable 变化。
- 前轮 P1 已解决：SQL 在排序/限量前精确过滤，候选绑定来源版本、库/Storage 和固定配置；
  展示与 choice 保存共用权威。独立验证同文件不同 pin、不同库绑定，以及新来源分析前/后
  均不借旧候选；旧合法 pin 仍可保存。11 个无关准备后原生页面候选不丢失，同页选 911 后
  生成新摘要，确认前零变更，确认后真实 Worker MOVE 到 tmdbid-911 目标。
- B 独立相关 Python **303 tests / 17.904s / OK**；完整真实 Python 浏览器 spec
  **27 passed / 46.2s**，含未知确认对账、C→A 身份、兄弟项独立补正/非重放与重连/重启。
  独立来源变化 409→不可执行摘要→显式新准备，以及真实 Task Base schema45→候选新增两列、
  迁移拒绝/旧行和 pin 保留/重开已验证；桌面、窄屏和实际容器图片已查看。
- 匹配原始证据复用：隔离全量 Python **2474 / 175.143s / OK / 7 skipped**；Web
  typecheck/lint/format/build、Vitest **1121**、fake E2E **246**、Unicode principal **1**、
  visual **2**、wheel consumer 和 release-security。主工作区 schema48 环境失败仍按失败保留，
  以 Base 对照及干净候选全量排除回归；未读取或修改用户运行库。
- **容器证据纠正：** Developer creation 标签实际是较早镜像，7 个本 Task 源文件不匹配，
  该次 PASS 不用于本候选。B 校验 security 镜像源码及 Web 字节匹配，再在精确候选 checkout
  上用该镜像重跑 creation proof：9 个浏览器断言、发现/拒绝/附件、真实常驻 Worker MOVE
  和非重放通过。未将旧标签或打印的 candidateSha 当作内容证明。
- 完整判定、原始日志、API/SQLite 读回、trace、截图、产物身份与证据复用说明：
  `.git/validation-evidence/da4b70c9c9ccfe92d8b407a215aef9e893e1e83f/b-review4-20261017/INDEX.md`。
  仅本地可达；未提交独立 review checkpoint、未推送、未改 Slice/Roadmap/稳定需求。
  上一 Task 原计划与 Developer 报告仍在本 Task Base 的 TASK.md。

### PASS 后重新核对 Slice

| Outcome / Surface | 当前事实 |
|---|---|
| RO-1 / S-1 | Task45.1 PASS；九标签、完整总体查询/计数及 Task/type 文件定位已完成 |
| RO-2 / S-2 | Task45.2 PASS；创建/Files 同页准备、摘要、精确选择确认与真实 Worker 已完成 |
| RO-3 / S-3、S-4 | 列表/定位完成；专用处理→同页摘要→确认继续仍缺，本 Task 完成 |
| RO-4 / S-5 | 详情/记录/导出/控制已有；需要重新授权的暂停整理与恢复异常连续性仍缺，本 Task 完成 |
| RO-5 / S-7 | 独立 Scan 的全入口/运行分支退役未完成；不纳入本 Task |
| RO-6 / S-6 | 既有共享权威保留；本次恢复编排与后续退役、Slice-final 仍缺 |

因此 **NEXT TASK**，不是 Closure Packet。规划前治理 PASS；已提交 Slice45 ACTIVE Contract
与工作树一致，Roadmap 仍 ACTIVE。Task Base 固定为规划前 HEAD，不随规划/实现提交移动。

### 实际可复用能力与缺口

- `OperationsLanding` / `ProblemFilePanel` 已从跨任务类型列表定位后端过滤/分页的问题文件，
  但处理仍连接通用 evidence/detail 与旧 `TaskItemRecoveryPanel`；不能仅换列表按钮文案。
- `TaskItemRecoveryService` 已有 task/item/checkpoint-version 约束、合法识别/Metadata/
  分类/冲突决定与显式 Metadata search；`ProcessingCheckpointService`、
  `RecoveryContinuationService` / `RecoveryBatchContinuationService` 已有独立分析准入、
  固定 pin、逐项接受/拒绝和 Worker 关联。优先复用，不建立第二套恢复队列或 review。
- `ManualRecoveryContinuationService.authorize_continued` 当前在分析后重新生成 Preview 并
  签发一次性权限；旧页面先勾影响、准备精确 Preview、再跳独立页面检查。不能把这一带授权
  的步骤当作“读取/准备摘要”，也不能让普通用户操作内部 DryRun Task。
- `OperationsLanding` 的 remaining-scope Preview 及恢复 Preview 回调仍离开处理界面；
  `ScopeContinuationService` 已有剩余范围、原 pin、实际权限和 chain owner 检查，
  应保留而将需要的新摘要/确认整合到当前界面。
- Task45.2 的 `organize-summary`、不可变 Preview、精确子集 admission、未知提交对账和
  常驻执行 Worker 可复用；新建准备 findings 与正式执行恢复仍是不同持久语义，不能混为一队。

这是一个“修复问题文件并安全继续”的跨层业务单元；不按五类表单、摘要字段或测试拆 Task。

## User Journey

| 环节 | 本 Task 必需结果 |
|---|---|
| 用户目标 | 理解本文件为何未完成，只继续后端证明安全且明确确认的剩余范围 |
| 入口 | 五类恢复列表行内处理；需要处理/详情同类入口；安全暂停整理的继续/重新授权入口 |
| 可见状态 | 原任务/类型内文件，失败阶段/来源/目标、附件步骤、已完成效果/确定性，当前合法输入和动作，分析进度、就绪/未就绪及新摘要 |
| 动作 | 保存类型/候选/纠正/分类/冲突决定或修复依赖；显式重新检查；选择就绪子集；必要影响确认；“确认继续整理 N 项”；核对未知提交和查看已有尝试 |
| 成功 | 准入精确剩余范围，真实 Worker/OrganizerExecutor 执行；结果与当前问题/计数按持久事实更新，原结果和成功兄弟项保留 |
| 失败 | 新阻塞转相应类型；拒绝、再次失败、缺原上下文、权限/Worker 不足及未知响应说明持久状态与下一步，不冒充已解决 |
| 恢复 | 保留输入/范围/返回上下文，修正并显式重新分析；未知提交先读精确请求；效果未知仅核查证据/来源/目标/日志/导出 |

## 逐步开发清单 — Developer 执行指导

这是 **Task45.3 内部的开发顺序**，不是新增 Task、独立验收或缩小范围。
Task ID/Base/Goal、High/T4、下方 Scope/AC/Required Tests 全部不变。
每次只完成一个小步骤，先验证本步及直接受影响行为，再继续下一步；这些步骤不需要逐项申请批准，
也不要求逐步创建提交。最终仍交付一个完整、连贯的 Task checkpoint。

### 开始前的固定做法

- 先运行治理检查并记录 status，保留本 Task 已有规划和所有无关脏文件。开发只使用临时库、
  fake/local-server Provider 和测试 Storage，不打开用户运行数据库或私密配置。
- 每步在 Completion Report 草稿简记“改了哪里、已验证什么、实际失败是什么”；最终合并成简洁报告，
  不另外建立步骤档案、微型 Task 或通用框架。
- 保持已有接口兼容；抽取共享逻辑时先保住原回归，不批量重命名状态/表/路由，不重写 OrganizerExecutor。
- 开发时允许某步尚未接 UI，但不能因此声明用户旅程完成。全部步骤和最终门禁完成后才返回 B 审查。

### 01 — 先画清已有调用链，不改行为

- **看哪里：** `task_item_recovery.py`、`recovery_continuation.py`、`recovery_batch.py`、
  `manual_recovery_continuation.py`、`manual_organize_execution.py`、`scope_continuation.py`；
  Web 的 `OperationsLanding`、`ProblemFilePanel`、`TaskItemRecoveryPanel`。
- **做什么：** 在报告草稿列出保存决定、分析准入、Worker 分析、生成 Preview、授权、执行准入、
  Worker 执行各自的现有入口；标出读、分析、授权和 mutation 边界。
- **完成标准：** 能指明普通恢复当前在哪一步跳独立 Preview、在哪一步提前签权限、哪里同步执行。
  不能把 `authorize_continued` 当成只读摘要接口。

### 02 — 建立一个可反复运行的小型真实 fixture

- **改哪里：** 优先扩展 `tests/test_recovery_continuation.py` 的现有 fixture/helper。
- **做什么：** 创建一个原任务，包含成功项、可恢复问题项、效果未知项；需要多项选择时再加入第二个
  可恢复项。使用真实 SQLite 与临时 Local Storage，记录 Provider 调用、mutation 和执行许可数量。
- **完成标准：** 能独立读回原结果、问题与 pin；每次运行从干净 fixture 开始，不依赖其他测试先运行。
  后续每个测试按需要复用，不一次预建所有异常组合。

### 03 — 抽出无授权的计划准备逻辑

- **改哪里：** `ManualRecoveryContinuationService`，复用现有 intent/Preview 服务。
- **做什么：** 将 `authorize_continued` 中可共用的原项/分析结果/决定/来源/pin 校验和计划生成
  分离出来，供无授权的摘要准备调用；旧显式授权接口继续复用相同校验，不复制第二套规则。
- **完成标准：** 准备摘要前后 Storage mutation、执行许可和实际 execution 数量都不增加；
  原有授权/执行回归仍通过。计划分析走已有 Worker，不能新增长 HTTP 分析循环。

### 04 — 让摘要和原问题有可重开的持久关联

- **看哪里：** `domain/manual_recovery.py`、现有 Preview/continuation 关联与 SQLite repository。
- **做什么：** 优先利用已有持久来源关联定位精确摘要，记录原项、采用的分析尝试、输入版本和原 pin；
  现有字段不足才补最小关联字段及迁移，同时保留历史关联。
- **注意：** 现有 `ManualRecoveryLink` 要求 `authorization_id`，且已有 AUTHORIZED/CONSUMED/STALE
  含义。未授权摘要不能冒用 AUTHORIZED、不能创建假授权 ID，也不能为了填该字段提前签权限。
- **完成标准：** 数据库重开后找回同一个摘要；其存在不意味着获得执行权限。页面阶段尽量从已有记录
  推导，不另造 Task 状态机；必要新持久状态须写清含义、转换条件及旧记录默认值，随本 Task 交 B 审查。

### 05 — 防止过期分析成为当前摘要

- **改哪里：** 现有分析 admission/Worker 完成发布与上述关联更新位置。
- **做什么：** 分析绑定所用决定、checkpoint/输入版本、来源与 pin；发布前复核仍匹配。
  较旧分析晚返回时保留历史，不能覆盖新输入对应的当前摘要。
- **完成标准：** 用可控制的 barrier/event 暂停旧分析，保存新决定后再放行旧分析；读回的当前摘要
  不采用旧结果。测试不靠随意 sleep 赌顺序，不让 Provider/Storage 长调用占住 SQLite 写事务。

### 06 — 实现精确确认的后端入口

- **改哪里：** 恢复 application service，复用 `ManualOrganizeExecutionService.begin_web_execution`
  /现有原子 admission 和 repository 约束。
- **做什么：** 确认绑定确切摘要、原项/输入版本、actor、就绪子集及影响许可；重新校验当前合法性。
  准入、许可消费与恢复执行关联在同一数据库事务边界内成立，避免先授权或先建执行再另补关键关联。
- **完成标准：** 确认只排入既有执行队列，HTTP 返回耐久执行身份；未就绪/成功/忽略/未知/已受理项
  被拒绝，未选兄弟项不受影响。事务中故意失败不遗留可执行孤立权限、重复执行或缺失恢复关联。

### 07 — 让真实执行 Worker 回写关联结果

- **改哪里：** 既有 manual execution Worker 和恢复读投影，必要时补注册/装配。
- **做什么：** 使用已有 claim/lease/fence，实际变更前重验精确 Storage 来源与权限；结果仍写现有
  Task/TaskItem/Result，恢复页通过持久关联展示排队、执行、成功和失败。
- **完成标准：** “已受理/许可已消费”不当作文件成功；Worker 失去所有权不能发布或继续新的 mutation。
  重开/重启不重放已完成和效果未知项；媒体 mutation 仍只由 OrganizerExecutor 执行。

### 08 — 加上精确提交对账

- **改哪里：** 恢复确认/查询 application 与 repository，复用现有 admission outcome 语义。
- **做什么：** 确认前保留可定位本次请求的精确身份和选择；重复同一请求读回原执行，改变绑定则拒绝。
  未知结果查询绑定当前认证主体，不能查“最近一个任务”猜测成功。
- **完成标准：** 模拟数据库已提交而响应被丢弃，再查回同一次执行；两个并发确认最多受理一次，
  不产生多余可用权限。单靠按钮 disabled 或 service 的“先读后写”不算并发保护。

### 09 — 接 API 和严格的 Web 数据模型

- **改哪里：** `service_api.py`、`web/src/shared/api/api-client.ts` 与 operations entity/query。
- **做什么：** 将已有决定/分析、无授权摘要读取、精确确认和提交对账连接到同一 application 行为；
  返回当前允许动作、版本、就绪/未就绪、摘要及关联结果，前端只展示这些事实。
- **完成标准：** API 单独调用也不能绕过权限或输入校验；GET 不创建工作/调用 Provider/签发权限。
  401/403、过期、缺 pin、Worker 等待和未知提交能被 typed model 明确表达，不用 `any` 吞错误。

### 10 — 先完成只读的同页处理容器

- **改哪里：** `OperationsLanding` / `ProblemFilePanel`，允许抽取一个小的共享处理组件。
- **做什么：** 保留 Task/type 与列表上下文，上方列问题文件，下方显示选中项原因和处理区域；
  复用 `organize-summary` 显示真实摘要。先接真实读取，再加写按钮。
- **完成标准：** 点击文件、刷新、分页、返回和深链都不提交命令；切文件不会带入上一文件的选择/错误。
  桌面可查看完整信息，窄屏纵向排列，键盘可到达列表、表单和摘要。

### 11 — 跑通单项识别恢复的完整旅程

- **改哪里：** 复用 `TaskItemRecoveryPanel` 的识别决定和新同页处理容器。
- **做什么：** 选择后端允许的类型→保存并安全分析→同页摘要→明确确认→Worker 结果；
  移除该旅程必须跳独立 Preview 或手工管理分析 Task 的步骤。
- **完成标准：** 原生浏览器能完成一次真实恢复；保存/分析阶段零 mutation/零许可，确认后才执行。
  选择 C 且复用 A 策略时，摘要和结果中的 RecognitionType 都保持 C。

### 12 — 接入元数据的两条输入分支

- **改哪里：** 复用 `TaskItemRecoveryService.metadata_search/resolve` 及现有 Metadata 表单。
- **做什么：** 先接持久候选选择，再接标题/年份/电影或剧集纠正与显式搜索；两者汇合到步骤 11
  已跑通的分析/摘要/确认路径，不再复制一套执行状态。
- **完成标准：** 原 pin 决定 Provider；旧版本/跨来源候选与任意 identity 注入拒绝；读取不搜索。
  进入新 Metadata 阻塞、无候选、搜索失败及过期输入均保留可修正内容和真实下一步。

### 13 — 接入分类恢复

- **改哪里：** 现有 classification decision/application 和对应表单。
- **做什么：** 选择固定上下文允许的分类结果，或显示规则修复指引；保存后复用同一分析/摘要/确认。
- **完成标准：** 无法提交任意媒体库/目标路径；发布新 Active 不替换旧 pin。旧 pin 缺失时明确拒绝，
  不以重新保存配置、切换当前库或读新 Active 偷偷继续旧任务。

### 14 — 接入主文件和附件冲突处理

- **改哪里：** 现有 conflict decision/application、冲突表单及摘要中的影响确认。
- **做什么：** 只按当前许可显示 Skip/Rename/Overwrite；保存决定后再分析，在实际摘要里展示
  哪个文件会替换/移动/清理，并在确认时绑定精确子集的独立影响许可。
- **完成标准：** 保存 Overwrite 决定不立即执行、不自动获得覆盖权；没有政策许可时不能覆盖。
  主文件/附件冲突能独立解释，未选项的影响不能顺带取得权限。

### 15 — 接入技术失败修复和新阻塞转类

- **改哪里：** checkpoint 动作投影、失败表单及关联分析读回。
- **做什么：** 给出网络/Provider/Storage 权限等具体修复指引；修复后点“重新检查并生成摘要”。
  分析仍失败则留原因；出现新的识别/Metadata/分类/冲突时按真实关联进入对应处理。
- **完成标准：** 至少跑通“技术失败→修复→Metadata 待选→选择→新摘要→执行再次失败”。
  两次失败记录都保留，新原因可操作，原成功项不重跑；效果未知只核查，不出现执行确认。

### 16 — 接任务内有界多选及附件剩余步骤

- **改哪里：** 复用 `RecoveryBatchContinuationService`、现有批次结果和精确选择机制。
- **做什么：** 多选只限当前任务允许范围，分析逐项接受/拒绝；汇总各自持久摘要，只确认所选就绪项。
  保留每项原 pin/来源/版本/影响；上下文不兼容时明确分组或拒绝，不拼成一个伪共同快照。
- **完成标准：** 两个就绪项只选一个执行，未选项继续可处理；成功/忽略/未知/过期项分别拒绝。
  主文件已完成时只允许既有权威能证明安全的附件剩余步骤；不能证明就拒绝并保留核查证据，
  不能为补附件从头执行主文件，也不能以拒绝所有附件用例代替已有安全能力的接入。

### 17 — 接暂停整理的继续与重新授权

- **改哪里：** `ScopeContinuationService`、`OperationsLanding.remainingScopePreview` 及同页摘要组件。
- **做什么：** 保留原剩余范围/chain owner/权限检查；可直接合法继续就直接继续，需要新授权才
  在当前界面展示剩余摘要并明确确认。只改整理相关旅程，不为将退役的 Scan 设计新能力。
- **完成标准：** 已完成范围不重放；已消费许可或撤销 grant 不复活；旧 A pin 在 Active B 下仍是 A。
  Pause/Cancel 显示请求与生效区别，不声称在途文件操作被撤回。

### 18 — 对齐问题列表、计数和历史

- **改哪里：** 现有 operations run/problem 查询与 application 投影，Web 只刷新权威结果。
- **做什么：** 根据原项及明确关联尝试的当前真实问题归类；保留原失败历史，已解除的问题移出，
  新问题进入对应类型。同任务可属于多类；分析中/执行中显示真实尝试，不以点击按钮清除问题。
- **完成标准：** 混合任务逐项处理前后，列表/文件数/任务数跨页一致；一个任务恢复不改变另一任务。
  不用浏览器当前页、文件名或时间相近来推断关系；分析完成不冒充整理成功。

### 19 — 补齐重连、未知响应和并发的固定反例

在上面已经跑通的链路上逐个加反例，不同时改状态、超时和 UI 绕过失败：

| 安排的交错/异常 | 必须看到的结果 |
|---|---|
| A 分析暂停，B 保存新决定，A 最后返回 | A 只留历史，当前摘要不回退 |
| 两个连接同时确认同一原项 | 单次有效受理或一方明确拒绝，无重复有效权限/执行 |
| 从两个不同摘要确认同一原项 | 按原项及有效恢复关联防重，不能只依靠相同 Preview ID 去重 |
| 两个选择集合部分重叠 | 重叠项不重复准入，非重叠项按实际独立接受/拒绝结果解释 |
| A 查看旧摘要，B 保存决定，A 再确认 | 旧输入确认拒绝，同页更新摘要 |
| 确认已提交，浏览器收不到响应 | 查回原请求，整个过程只有一次有效准入 |
| 已受理后进程中断，随后重启 | 关联可读；已完成/未知效果不重放 |
| 旧 Worker 被新 owner 接替，再返回 | 旧 owner 不能发布或执行新的 mutation |
| 执行准入/关联写入中途故意失败 | 数据库回滚，无可执行孤立记录 |
| 查看摘要后来源被替换，或原 pin 丢失 | 执行前拒绝，不能改绑当前 Active 或自动执行新方案 |

- 使用实际两个 SQLite connection、barrier/event 或已有 fencing 测试方式控制顺序。
  Storage/Provider I/O 不放进长写事务；SQLite 的原子性不代表能锁住外部文件，Worker 仍要重验。
- 刷新/重新认证保留当前合法返回位置；未知提交提示绑定已核实的主体。换主体不继承旧确认提示或许可，
  UI 禁止自动 POST 重试，不把浏览器布尔值当后端权限。

### 20 — 完成旧库、安装/容器和最终候选验证

- **先做什么：** 有持久化变化，使用实际 Task Base 的代码创建旧库，再升级/重开/注入失败，
  核对旧结果、pin、许可消费和恢复关联；不能只测新库，不能将旧记录升级成待执行。
- **再做什么：** 按下方 Required Tests 完成精确最终候选的 Python、Web、真实浏览器、wheel、
  Docker 及安全/质量门禁。完整 suite 已覆盖聚焦测试时记录覆盖，不重复跑同一反馈命令。
- **完成标准：** 实看五类同页流程、暂停授权、桌面/窄屏/键盘截图；保留原始失败和精确复跑。
  校验镜像内源码/served assets 和 wheel 对应候选，不能复用名字相同但内容过期的镜像。
  检查完整 diff/私密文件/冻结范围，补 Completion Report 后提交一个连贯 checkpoint。

### 每步用哪些反馈命令

下面是下方 Required Tests 的使用顺序，不替代或删减最终门禁。命令从仓库根目录运行，Web 除外。

| 开发内容 | 优先反馈 |
|---|---|
| 步骤 02–08：恢复准备、关联、确认和对账 | `.venv/bin/python -m unittest tests.test_recovery_continuation tests.test_processing_checkpoint tests.test_manual_organize_execution tests.test_organizer_mutation_authority` |
| 步骤 09–11：API 与首条原生旅程 | `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_recovery_continuation`；Web 在 `web/` 跑 `npm run test -- run src/features/operations src/entities/operations src/shared/api` |
| 步骤 12–15：各类决定与故障 | 先跑本次新增/失败用例，再跑对应 `tests.test_recognition_review` / `tests.test_metadata_review` / `tests.test_classification_review` / `tests.test_conflict_resolution` 及恢复集成用例 |
| 步骤 16–18：批次、暂停与当前问题查询 | `.venv/bin/python -m unittest tests.test_recovery_batch tests.test_scope_continuation tests.test_operations_task_center tests.test_operations_run_inventory` |
| 步骤 19：并发与异常 | 先跑每个新增反例，再跑受影响恢复/执行/批次/暂停模块；不能只 mock 掉 repository 的原子性 |
| 步骤 20：最终候选 | 完整执行下方 Final checkpoint gates；真实浏览器使用完整 spec 或自包含 fixture，匹配候选的原始证据可按规则复用 |

如果某一步必须改变原 pin、扩大 mutation 权限、允许未知效果重放或另建队列才能继续，
先保留现场并向 B 说明具体边界和现有代码限制；不能为了完成步骤自行削弱不变量。

## Implementation Scope

### 1. 五类原生处理与合法决定

- 在现有 Task/type 文件处理界面完成识别、Metadata 候选/查询纠正、分类、冲突及失败处理。
  各类型有合适的表单、业务说明和可行下一步，不能以跳通用 evidence drawer 替代该旅程。
  入口、深链、原任务详情与返回的 view/filter/page 保持；窄屏、键盘与权限状态可完成同样结果。
- 仅展示和接受后端当前允许的选择/动作，保存时复核 checkpoint/decision/source/pin/version。
  Metadata 搜索必须显式请求且经原固定配置的 Provider；GET/轮询/切页不访问 Provider。
  旧候选、跨项 identity、任意目标/策略注入和权限绕过均拒绝；C 复用 A 策略仍是 C。
- 保存决定/忽略/安全分析不授予执行权限，不要求普通用户管理 DryRun Task、token 或 UUID。
  可安全组合没有新 human intent 的步骤；保留所选项及独立接受/拒绝结果，拒绝不擦除合法输入。
  主文件和附件的已完成/失败/等待/未知分别可诊断。

### 2. 显式安全分析、同页摘要与当前问题流转

- Domain/ports → Persistence → Application → API/Worker → typed Web/测试共同完成。
  复用已有 checkpoint、review/decision、analysis/batch continuation、pin 与 Planner；
  长分析由既有持久工作和常驻 Worker 执行，不能放在长 HTTP 请求或浏览器循环中。
- 用户修复网络/权限等条件或保存合法决定后，仅显式重新分析允许的问题范围，不重跑整任务。
  原上下文仍校验，发布新 Active 不改绑旧任务；缺失/损坏原 pin 明确拒绝并提供修复指引。
  新方案只在既有准入允许时显式新准备，不扩成任意历史 Reprocess。
- 当前处理界面显示实际分析进度、未就绪原因、新遇识别/Metadata/分类/冲突及可继续范围；
  不能把分析受理/完成当作整理解决。关联分析遇到新问题后，可从相应类型继续处理真实关联项；
  原 Task/item/Result 与每次尝试可追溯，不造假 resolved 或按文件名/时间猜关联。
- 新摘要展示本次来源→目标、操作、策略/身份解释、主文件/附件、实际剩余步骤、已完成且不重复
  的步骤、完整性/就绪/未就绪、冲突及覆盖/来源清理影响。摘要准备零 Storage mutation、零许可。
  复用共享呈现但不要求操作者先进入独立 Preview，也不把准备 findings 塞进正式失败清单。
- 原问题解决后按真实 durable state 更新类型列表/文件数和任务计数；其他问题、任务/文件不受影响。
  安全分析/执行已受理但未完成时显示关联尝试及真实状态，不能清空问题制造完成假象。

### 3. 精确确认继续、持久执行和异常连续性

- 用户可选就绪子集，再明确“确认继续整理 N 项”；无合法就绪项不提供可执行确认。
  覆盖与来源清理按实际剩余计划及原策略许可分别表达；保存冲突决定不执行覆盖或删除。
- 使用同一 application admission/OrganizerExecutor、当前 RBAC、不可变精确计划/来源/子集/pin、
  optimistic version、claim/lease/fence 和真实 Storage 校验；原子准入及一次性权限消费，
  不新增 fallback 或更广 mutation authority。Web 与对应 API 同权威，执行经真实常驻 Worker。
- 已成功/跳过/忽略/效果不确定及已经受理的项不重新进入确认选择；主文件已完成但附件失败时，
  仅允许既有权威能证明安全的剩余步骤，不能重放主文件或发明通用补偿。
- 恢复尝试排队、运行、再失败和结果独立持久，关联原任务与原文件；再次失败说明新原因和动作。
  重复/并发确认收敛为同次精确执行或明确拒绝。丢响应/重连先查该次耐久请求，不猜最近任务，
  不自动 POST 重试。确认前后来源/计划实质变化回到同页更新摘要并取得新意图。
- 效果未知提供持久步骤、来源/目标核查、相关日志与有界脱敏导出；不提供直接 retry/强制重放/
  自动回滚。结果同步/日志失败不能把已完成或未知 mutation 变成可重放。
- 安全暂停的整理工作 Continue 保留剩余范围、原 pin、chain owner/fence 与当前真实权限。
  可直接合法继续的工作不增加确认；需新权限时在当前任务界面生成剩余范围摘要并明确确认。
  已消费的一次性许可和已撤销的 unattended grant 不因 Continue 复活；暂停/取消区分请求和生效。

### 4. 兼容、清理与所有权

- 旧 Task/Job、恢复/执行/Preview 深链仍可诊断原记录；普通恢复/继续旅程不再导向独立 Preview。
  可保留内部不可变计划/Preview 存储和显式 API 管理兼容语义，不能保留普通 Web 的替代绕路。
  通用诊断 DryRun/Rules 测试不退役；其他页面和普通文件命令保持。
- 必要增量持久化/索引保留旧结果、pins、来源身份、许可/消费状态与关联历史；补实际旧版本
  migration/reopen/失败安全证明。不建立第二套任务/队列、配置权威、恢复或 mutation 引擎。
- 限恢复/继续、所需应用编排/投影、Worker 装配、共享摘要、返回/深链、测试/验收工具。
  新建/Files 仅为共享逻辑必要兼容；不重构其已接受旅程，不导入冻结 Slice43 代码。
- 不修改 SLICE.md、Roadmap、Progress、稳定需求或已接受 CURRENT 声明。Contract 无法满足
  时交 B/A，不通过删测试或改文案减义务。
- 保留所有预存脏文件：`docs/pics/操作与任务.png` 删除意图、两张未跟踪自动化页图、
  各处 `.DS_Store` 和 `output/imagegen/slice45-task-center-v1.zip`；不纳入 checkpoint。
  `config/alist.json` 保持 ignored/untracked/unstaged，不读取/输出私密配置或用户运行 DB。

## Acceptance Criteria

- [ ] **AC-1：** 五类跨任务列表均可进入该任务/类型的原生问题文件处理并完成适合该问题的
  决定/修复动作；后端过滤分页、深链/返回、窄屏/键盘、空/无权限/不可用可行；不用 CLI、V1、
  raw token、内部 DryRun Task 或独立 Preview 完成普通恢复。
- [ ] **AC-2：** 保存决定与分析零 mutation/零执行许可；显式 Metadata search 和完整安全分析
  使用原 pin/Provider/策略与既有持久 Worker；过期/跨源/非法输入拒绝且保留其他项和可修正输入。
- [ ] **AC-3：** 同页摘要精确展示本次可继续范围/剩余步骤/附件/目标/影响及未就绪原因。
  修复后出现新阻塞可转对应处理，原失败与成功兄弟项保留；受理/分析不冒充解决，列表/计数
  根据真实当前状态变化。原 pin 不可用不静默 repin。
- [ ] **AC-4：** 精确就绪子集经“确认继续整理 N 项”原子准入，只有明确允许的剩余效果经
  Worker/OrganizerExecutor 执行；成功、忽略、已受理、未知效果和未选项不重放/互相覆盖。
  有界任务内批量分析保留各项独立接受/拒绝，不新增跨任务批量 mutation。
- [ ] **AC-5：** 并发/重复、未知确认响应、来源/计划变化、Worker 等待、再次失败、刷新/重连/
  重启均有准确持久状态和原生下一步；未知效果只核查；无需恢复用户手工保存的内部授权材料。
- [ ] **AC-6：** 安全暂停整理的可直接 Continue 与必须重新授权区分；后者在当前界面生成
  精确剩余范围摘要并确认，保持原 pin、当前权限、owner/fence，已消费/撤销许可不重新获得。
- [ ] **AC-7：** Task45.1/45.2、详情/导出/历史、普通 Files/MediaLibrary、RBAC/脱敏/
  memory-only auth、Type C 和全部 Slice 安全不变量不回归。T4 全部门禁与实际浏览器/
  安装/容器适用边界有精确候选、产物和耐久原始证据；checkpoint 仅含本 Task。

## Required Tests

T4 来自恢复执行授权、原 pin/来源、并发/非重放与持久 Worker 边界。按 workflow 先反馈、
再最终候选；不在每次改动后机械跑全量。当前主工作区 ignored runtime DB 为 schema48，
全量在精确候选的干净隔离 checkout 执行，不触碰用户库、不隐藏失败或修改断言造绿。

### Development and correction feedback

1. 根目录：`.venv/bin/python -m unittest tests.test_processing_checkpoint
   tests.test_processing_recovery_admission tests.test_recovery_continuation tests.test_recovery_batch
   tests.test_scope_continuation tests.test_conflict_resolution tests.test_recognition_review
   tests.test_metadata_review tests.test_classification_review`：合法决定、分析独立准入/拒绝、
   原 pin、remaining scope、当前权限/owner、逐项问题与非重放。新编排模块补专用回归并记录实际命令。
2. `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_manual_organize_execution
   tests.test_organizer_mutation_authority tests.test_operations_task_center
   tests.test_operations_run_inventory tests.test_operations_run_detail
   tests.test_operations_run_detail_plan_evidence tests.test_organize_preparation`：API/Web 同权威、
   精确确认及影响、源/附件、历史/计数流转、创建补正/未选项不回归。
3. `web/`：`npm run test -- run src/features/operations src/entities/operations
   src/shared/api src/shared/navigation`：五类专用输入、同页摘要/子集、unknown、返回/401/403/
   主体隔离，批次/session hint 仍按后端认证主体隔离。
4. 扩展真实 `operations_inventory_harness.py` 与 `operations-inventory.python.spec.ts`：
   混合成功/待识别/Metadata/分类/冲突/技术失败/未知效果；每类从列表到补正→分析→同页摘要→
   子集确认→实际 Worker 结果；网络/权限修复后的新阻塞转类、只继续附件允许步骤、再次失败。
   对照确认前 mutation/执行许可计数、GET Provider 计数、原成功/未知项不进入执行选择。
   覆盖 pin A→B/原 pin 缺失、来源变化、暂停重新授权、撤销/消费许可、重复/并发、未知响应、
   Worker 缺失、重连/重启与独立接受/拒绝。使用 fake/local-server Provider/Storage，禁接生产。

### Final checkpoint gates

最终 executable candidate 满足全部下列门禁；full 已包含 focused cases 时记录覆盖而不机械重跑。
先修复已知失败；源码/测试/harness/config/产物变更后按 T4 对最终候选完成全部指定门禁。

- 根目录：`.venv/bin/python scripts/check_governance.py`、`.venv/bin/ruff format --check .`、
  `.venv/bin/ruff check .`、`.venv/bin/python -m unittest discover -s tests`、
  `.venv/bin/python -m compileall -q mediaflow tests scripts`、`.venv/bin/python -m pip check`。
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` 与
  `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（exit 1）；新增依赖与 Type C
  计划/实际结果检查。Storage mutation、权限/固定配置、claim/fence/并发回归纳入全量。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run test -- run`、
  `npm run build`、`npm run test:e2e`。共享 Operations/typed contract/返回/摘要涉及完整 Web 入口。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`；
  `npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts`。
  使用 production build + 真实 API/SQLite/Worker，执行上方恢复分支。现有 spec 共享顺序 fixture，
  最终门禁运行完整 spec；独立关键 probe 用新隔离 fixture，不用缺少前置状态的 grep 结果宣称通过。
- production build 原生五类处理/混合问题、同页摘要/子集确认、未知确认对账、暂停重新授权，
  Tasks/Files 返回、深链/重连、键盘与 1536×1024/380×720 实际截图/trace；人工查看摘要、输入、
  焦点、可达动作及遮挡，不以 capture exit 或固定例图计数代替验收。
- `.venv/bin/python -m pip wheel . --no-deps -w dist`；
  `.venv/bin/python scripts/wheel_smoke_test.py <本候选确切 wheel 路径>`，补安装版本实际加载本次
  恢复/执行 consumer 的证明（扩展 smoke 或等价隔离验证并记录精确入口）。
- 在已有 Docker proof helper 上新增或合理扩展恢复 proof，最终提供可直接运行命令，例如
  `.venv/bin/python scripts/docker_task_center_recovery_browser_proof.py --image mediaflow:task45.3-recovery`：
  精确候选 production image 的真实 API/SQLite/常驻 Worker 完成决定/安全分析/同页摘要/精确确认/
  独立结果，含未确认零变更、原成功和未知 effects 不重放及重连。可用隔离 fake/local-server
  外部依赖，不以静态响应或测试内直接执行替代容器 consumer。
- `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45.3-security`。
  两项可用经内容证明相同的候选 image；不无理由复制 Docker 全矩阵。镜像须匹配本候选源码/
  served assets，记录完整 image ID；复用 mutable tag 前检查内容，不把打印的 SHA 当作证明。
  容器不可用/失败如实报告，不记 PASS。
- 有持久化变更时：由实际 Task Base 的旧代码创建含原 Task/Result/pin/许可/恢复链的临时库，
  验证新增字段/表迁移、reopen 和失败不改写原权威/结果、旧记录不自动执行；相关旧 fixture 回归
  纳入全量。无变更则提供实际 diff，不虚构迁移通过。全量旧迁移测试不自动证明本次新列已覆盖。
- `git diff --check`、完整 Base..Head manifest/name-status/stat/diff 与冻结范围检查；私密配置、
  用户 DB、证据产物和全部预存脏文件不被读取/覆盖/偷偷纳入 checkpoint。

### B independent verification

B 检查实际 Task Base..Head、持久关联/版本/权限与可复用能力是否走同一生产链，检查匹配候选
的完整原始证据；缺失/不匹配/矛盾的门禁才重跑，不机械重复全部 Developer 矩阵。
独立用 production build + 真实 Python/SQLite/Worker：从恢复类型列表处理真实混合任务，
保存合法决定/修复一个失败→新阻塞转类→同页新摘要→确认少于就绪总量→仅该子集/允许附件步骤
执行，原成功/未知/未选项及其他任务保留；实际核对未知确认请求与再次失败。
另复现暂停重新授权、旧 A pin 在 Active B 下仍使用 A、原 pin 缺失拒绝以及读取不调用 Provider。
实看桌面/窄屏/键盘关键状态；不只接受 mock/“aligned”标签或测试数量。

### Evidence and rerun rules

使用 `.git/validation-evidence/<full-source-sha>/<run-id>/` 或 CI artifact，保留 source/checkpoint
SHA、精确 dirty content、cwd/命令、runtime/dependency/lockfile/安全 fixture、Worker/selection/
retry settings、产物/image/wheel 摘要、exit/counts/skips/duration、首次失败/复跑、logs/trace/
实际截图与 AC 映射。`/tmp` 不是唯一交接位置；证据不进普通 source/config/用户参考图。
文档 successor 先证明 executable inputs 未变再复用；report 不覆盖原失败，不降低 timeout/
assertion、隐藏 skip 或删除测试造绿。纯环境失败需 Base 证明；只报可读原始结果，不虚构远端可达。

## Non-goals

- RO-5 独立 Scan 全入口/Worker/重试/继续退役；现有 Scan 历史/兼容暂保留，不为其设计新恢复能力。
- 新建整理/Files 完整重做、其他管理页面改版、通用诊断 DryRun/Rules 退役或 V1 全面 cutover。
- 冻结 Slice43 的 Automation 页面/模式/Run once/engine settings，不导入其未接受实现。
- 跨任务批量 mutation/批量覆盖、任意历史 Reprocess、通用 rollback、未知效果 replay、
  新 Provider/配置/队列/身份/权限体系、MediaLibrary Organize、提高既有有界限制。
- 可选证明/文案/视觉 P2 清理任务、下一 Task 定义、Slice-final/Closure Packet 或 A 最终审查。

## Developer Completion Report

### 交付

Task45.3 继续修正 B Review 2 的 R2–R5。四类阻塞均按同一 Task 的 Scope/AC/Required Tests
修正，未改 ID/Base/Goal/范围/High/T4，未建新 Task，未改 Slice/Roadmap/稳定需求。

本轮（B Review 2 后）按 R2–R5 修正：

- **R2 本地摘要不再覆盖 durable 结果，暂停范围也精确对账**：
  `TaskItemRecoveryPanel` 以 durable `manualRecoveryPreparation` 为唯一读权威：只要持久摘要
  不是 `prepared`（`confirmed`/`superseded`/`stale`），本地缓存就不得再提供确认按钮；确认时
  记录本次 `preparationId`，`reconcile` 必须读回**同一** preparation 才解锁，读回
  `confirmed`+`executionId` 显示已受理、读回 `prepared` 才允许再次确认，读回其它摘要或仅 GET
  成功都保持锁定。暂停剩余范围复用既有 exact-Preview admission outcome/readback：
  `OperationsLanding` 从 run overview 的 durable `continuation.recoveryKind=exact_preview` /
  `recoveryPreviewId` / `executionId` 派生有效摘要（无 effect、无状态同步），刷新/重连/重启先
  恢复持久摘要或已受理执行；confirm 丢响应后只核对本次提交的 preview/选择/版本/破坏性许可，
  不猜最近任务、不自动重发。
- **R3 批次子项同页就绪子集汇总与确认**：`_recovery_batch_document` 为每个 child 附带其
  durable preparation、当前 checkpoint 版本、continuation 状态与 `manualRecoveryAvailable`；
  `RunDetailTabs` 新增 `BatchRecoverySummary`，逐项读取独立摘要、逐项选择、统一
  “确认继续整理所选 N 项”，经既有 `confirmTaskItemRecoveryPreparation` 逐项原子准入；未就绪项
  单列且不可确认，成功/未知/拒绝项不进入执行选择。
- **R4 摘要准备不再同步调用 Provider（含已有决定/候选/reference）**：`_run_item` 在决定/
  reference 存在时也优先消费完成分析解析出的 durable identity，并新增
  `_metadata_decision_mismatch`：保存的决定与 durable identity 在 provider/media type（及已命名
  providerId）上不一致时 fail closed，而不是静默二选一；`require_durable_identity` 让同页摘要
  在缺少/不完整/过期身份时给出明确重新分析动作，绝不在 HTTP 内 fallback 到 live Provider。
  `_reusable_analysis_identity` 优先采用含分类 facets 的完整 evidence metadata 段。
- **R5 迁移证明真实且含失败注入**：`task_base_migration_proof.py` 用实际 Task Base 代码创建
  真实 published revision、manual intent/item、exact Preview/PreviewItem、一个 active 与一个已
  consumed 的 one-shot authorization、恢复 continuation/link 与 Task/Result；升级/重开逐项比较
  这些事实，验证旧工作未变成可执行；再复制真实旧库构造 pre-46 preparation 表并在 ALTER 中途
  注入 `sqlite3.OperationalError`，断言 schema marker/列/旧记录原子回滚，移除故障后安全重开并
  完成迁移，legacy 行读回空选择。

- **Application** (`manual_organize_preview.py`)：`require_durable_identity`、
  `_metadata_decision_mismatch`、决定分支的 durable identity 复用。
- **Application** (`manual_recovery_continuation.py`)：`_prepare_continuation` 传
  `require_durable_identity=True`；`_reusable_analysis_identity` 优先完整 evidence 段。
- **API** (`service_api.py`)：`_recovery_batch_document` 为每个 child 附
  `manualRecoveryPreparation`/`currentCheckpointVersion`/`recoveryContinuationStatus`/
  `manualRecoveryAvailable`（GET，零创建）。
- **Web**：`TaskItemRecoveryPanel` durable-wins 协调与提交绑定对账；`OperationsLanding` 暂停范围
  durable 恢复 + exact admission 对账；`RunDetailTabs.BatchRecoverySummary`；
  `SamePagePlanSummary` 支持父级统一确认；entity 增加 child preparation 模型。
- **Tests/脚本**：R4 决定分支零 Provider 调用回归；R3 批次 child durable 摘要 API 回归与 Web
  组件回归；R2 本地准备丢响应/durable 覆盖回归与暂停范围对账回归；R5 真实旧库+失败注入迁移
  证明；真实浏览器新增两项就绪只选一的原生旅程。

### 最终候选

- Implementation Head：`d09245e2d49622f8e88ead4fc1583d55cffe9727`（R2–R5 修正 checkpoint + 测试补充）。
- Task Base：`8f5cf4e284766bcc8894817d7640231e85050fb2`（未移动）。
- 全部运行时门禁均在该候选的隔离 worktree / 精确 image 上验证。
- 证据索引：`.git/validation-evidence/d09245e2d49622f8e88ead4fc1583d55cffe9727/developer-45.3-r3/`
  （`INDEX.md`、`logs/` 原始日志；仅本地可达，未推送）。

### 验证（本轮候选）

- 治理：`.venv/bin/python scripts/check_governance.py` → **PASS**。
- 隔离全量：`.venv/bin/python -m unittest discover -s tests` → **2501 tests / 7 skipped / 1 failed / 198.3s**。
  唯一失败 `test_resource_library_pipeline.ResourceLibraryPipelineTests.test_scan_cli_needs_no_path_or_metadata_token`
  为本机工作区 ignored `.mediaflow/mediaflow.sqlite3` 为 schema48 导致的环境失败；已在 Task Base
  （`8f5cf4e`）独立复现同一失败，非本轮回归，交 B 判断。
- 聚焦恢复/执行/权限/任务中心/批次/暂停：`tests.test_processing_checkpoint
  tests.test_processing_recovery_admission tests.test_recovery_continuation tests.test_recovery_batch
  tests.test_scope_continuation tests.test_conflict_resolution tests.test_recognition_review
  tests.test_metadata_review tests.test_classification_review` → **215 tests / OK**；
  `tests.test_v2_manual_organize tests.test_manual_organize_execution tests.test_organizer_mutation_authority
  tests.test_operations_task_center tests.test_operations_run_inventory tests.test_operations_run_detail
  tests.test_operations_run_detail_plan_evidence tests.test_organize_preparation` → **217 tests / OK**。
- 质量门禁：`ruff format --check .`（372 files）、`ruff check .`、`compileall -q mediaflow tests scripts`、
  `pip check`、两份示例配置 `config validate` 全通过；`rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml`
  无匹配（exit 1）。
- 真实旧库迁移证明：`.venv/bin/python scripts/task_base_migration_proof.py` → **PASS**，
  schema 45→46，真实 revision/intent/Preview/active+consumed 许可/link/Result 不变、
  `manualExecutions=0`，新列与边界往返成功，ALTER 中途注入失败原子回滚后安全重开。
- Web：`typecheck`/`lint`/`format:check` 全通过；`npm run test -- run` **1129 passed (76 files)**；
  `npm run build` 成功（保留产物大小 warning）。
- 真实 Python 浏览器：`operations-inventory.python.spec.ts` **28 passed / 53.8s**，含新增
  “两个就绪批次子项汇总摘要、只选一个确认”的原生旅程；`operations-principal-identity.python.spec.ts`
  **1 passed**。
- wheel：`pip wheel . --no-deps -w dist`（`sha256 91f3f44a2009326ad1ecee566667373f3a0ce826001621dc06ad1022949049e4`），
  `wheel_smoke_test.py` → `preparationConsumer`/`recoveryPreparationConsumer: loaded`（schema 46）。
- Docker release-security：`TMPDIR=<项目内可挂载目录> .venv/bin/python
  scripts/docker_release_security_smoke_test.py --image mediaflow:task45.3-security-r3b` → **通过**
  （image `bf10b798d56d`）。
- Docker 恢复浏览器证明：`MEDIAFLOW_SMOKE_TEMP_DIR=<项目内可挂载目录> .venv/bin/python
  scripts/docker_task_center_recovery_browser_proof.py --image mediaflow:task45.3-recovery-r3b`
  → **通过**（image `a7f394c7282d`）；同页 prepare（零权限）→ 选就绪子集 → 确认 → 真实常驻
  Worker MOVE 到 `Movies/其他电影/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv`；仅一次
  prepare/confirm，无 legacy `manual-recovery-links/execute`。
- **环境约束（非回归）**：本机 Docker Desktop 挂载命名空间不含 `/var/folders`（默认 `TMPDIR`），
  两个 Docker 脚本需用 `TMPDIR`/`MEDIAFLOW_SMOKE_TEMP_DIR` 指向项目内可挂载目录；主工作区共享
  ignored 运行库为 schema48，全量唯一失败已在 Task Base 复现。
- **证据复用**：Docker 镜像在 executable checkpoint `7c94028` 上构建（image `bf10b798d56d` /
  `a7f394c7282d`）；`git diff 7c94028..d09245e -- mediaflow scripts web/src web/tests` 为空，
  仅 `tests/test_recovery_continuation.py` 变化，而 Dockerfile 不包含 `tests/`，因此两个镜像的
  executable 输入与本候选一致，Docker 证据可复用；Web 单元/浏览器在本候选上重新执行。

### 决定

- durable preparation 是页面读权威：本地缓存只能加速到同一条记录，绝不能覆盖
  `confirmed`/`superseded`/`stale`；确认对账绑定本次 `preparationId`，读回别的摘要不解锁。
- 暂停剩余范围从 run overview 的 durable exact-Preview 恢复派生有效摘要，无 effect、无自动 POST；
  丢响应只按本次提交的 preview/选择/版本/许可核对。
- 摘要准备一律消费完成分析的 durable identity；保存决定与身份冲突时 fail closed 要求重新分析，
  不在 HTTP 内 live Provider fallback。
- 批次逐项独立摘要、逐项原子准入，只确认所选就绪子集，不伪造共同 Preview/pin。

### 风险 / 偏差

- 五类恢复共用同一套 prepare/confirm 入口与既有决策表单；识别、分类、元数据、冲突与技术失败的
  专用输入均汇入同一分析→摘要→确认链，逐类专用文案与窄屏细节仍可在后续迭代细化。
- 任务内有界多选复用既有 `RecoveryBatchContinuationService` 与逐项 admission；批次面板只在
  child 已有/可准备 durable 摘要时提供确认，未就绪项明确单列。

### 可复用经验候选

- 无（待 Slice 收尾统一整理）。

## B Review Result

```text
Reviewed Range: 8f5cf4e284766bcc8894817d7640231e85050fb2..e851d05978a773fd15ae09d4249122e0a613b7e4
Executable Candidate: 1d4a9870b153ee5fe127296d9f809e157661f938
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: DEVELOPER CORRECTS THE SAME TASK 45.3
```

### B 独立验证 — Review 2 / 2026-10-17

- 规划/审查前治理 PASS；已提交 Slice45 ACTIVE 与工作树一致，Base/Contract 未变。
  `git diff 1d4a987..e851d05 --name-only` 仅 TASK.md，明确本轮运行时候选。
  已检查完整 Task manifest 和本轮 correction diff；本轮仅修改 B-owned TASK.md，
  保留全部预存脏文件，不修改产品代码、Slice/Roadmap/Progress/稳定需求，不推送。
- `.venv/bin/python -m unittest tests.test_recovery_continuation tests.test_task_persistence
  tests.test_processing_checkpoint tests.test_manual_organize_execution`：**104 tests / 8.274s / OK**。
  包含新的等价确认、事务内 checkpoint 栅栏及成功解除 attention 回归。
  `web/ npm run build` PASS，产物大小 warning 保留。
- 两条真实 Python API/临时 SQLite/Local Storage/假 Provider 反例：复用原候选选择和
  correction 集成 fixture，Worker 分析完成后 POST prepare-summary 仍同步增加 detail：
  候选分支 **4→5**，纠正分支 **2→3**；均返回 201，源仍存在。不是 GET 调用 Provider 的结论。
- 精确 production build + 真实 Python API/SQLite/生产 consumer harness 原生复现：
  页面新生成摘要（不先刷新），confirm 后端提交 202 再丢响应，显式重新读取后 durable status
  为 confirmed，已有关联执行按钮，但旧摘要/确认按钮仍 enabled；再次点击实际发出第二次 POST。
  两次独立新 fixture 复现；后端等价去重保住同一执行，未声称重复 mutation 或数据损失。
  已查看 **1536×1024 / 380×720** 实际截图。此证据不是五类、键盘或容器整体验收。
- 实际重跑 `scripts/task_base_migration_proof.py` PASS；已核对脚本与原始输出，只证明其
  实际执行的旧代码建库、schema45→46、新字段往返与所选字段重开比较，不能扩大为失败注入/
  真实授权消费/pin 全部保留的证明。
- Developer 原始 logs 现在存在：full Python **2496 / 7 skipped / 227.310s / OK**、
  Web/浏览器/wheel 等已有日志；报告中的 193.6s、wheel a41ee… 与本轮索引/原始日志
  （wheel **3a3911…**）不一致，交回时须统一具体运行身份。此次没有据此单独判产品回归，
  也没有把日志存在等同于原 Required Tests 全覆盖。
- 证据、可复跑 probes、原始 logs/trace/截图、source/lockfile/build 摘要及精确命令：
  `.git/validation-evidence/e851d05978a773fd15ae09d4249122e0a613b7e4/b-review2-20261017/INDEX.md`。仅本地可达。
  已有确定阻塞，按 workflow 提前拒绝；不重跑完整 Python/Web/E2E/Unicode/wheel/Docker
  或全部旧库矩阵，不将未跑门禁记 B PASS。

### 上轮修正核对

| 上轮条目 | 本轮实际结论 |
|---|---|
| R1 精确确认 / 原 checkpoint 原子栅栏 | 已加入选择/许可比较及事务内重新投影；独立聚焦集通过，本轮未复现原两个缺陷。保持这些保护及原并发门禁 |
| R2 durable preparation / 对账 / 当前问题 | 刷新可读 preparation、confirmed 链参与成功解除查询已补；本地新准备后的 unknown 对账仍有下述阻塞，暂停剩余范围也未接精确对账 |
| R3 普通 Preview 绕路 / 完整恢复处理 | 高级独立 Preview 控件已移除；批次按钮改回原项，但汇总就绪子集旅程未交付，五类/新阻塞/附件原生覆盖不足 |
| R4 摘要内重复 Provider | 无已保存 Metadata 决定的分支已可复用；候选、correction 和已有 metadata reference 分支仍绕过复用 |
| R5 最终证据 / 实际旧库 | 原始日志与实际 Base 建库已补；脚本未执行所声称的失败注入，旧许可/pin/恢复链验证仍不完整 |

### 同 Task 阻塞与简单修正顺序

以下仅细化已有 Scope/AC/Required Tests，不改变 ID/Base/Goal/范围/High/T4。
先完成一个反例及其修正，再做下一项；全部完成后固定最终候选跑原 T4 门禁。
不把任一条拆成新 Task，不以改文案、隐藏控件或删断言代替行为修复。

#### R2 / P1 — 新准备摘要的本地状态覆盖 durable 结果；暂停确认也缺精确对账（AC-5/6）

定位：`TaskItemRecoveryPanel.tsx:126–138,335–389,470–506`；
`OperationsLanding.tsx:1456–1476,1513–1563`。
独立 browser probe 证明本地 preparation 为 prepared 时，durable confirmed 不会替代它；
reconcile 解锁后仍可提交旧确认。现有组件 unknown 用例从 GET 恢复摘要起步，没有覆盖此路径，
且只断言出现受理标题，没有断言确认消失/禁用。
暂停确认只把错误文案改为未知，后续 reconcile 仍仅 refetch 原 run 并解锁，未读回本次 Preview
对应的精确执行；remainingScope 也仅在组件内，刷新无法恢复该摘要/提交状态。

1. 先把上述 browser probe 改成产品回归：**本页显式准备→confirm 已提交但丢响应→重新读取**，
   断言显示同一执行且不再有可用确认，后续读取/重连不 POST。保留从 GET 恢复摘要的旧用例。
2. 以同一 preparation ID 的 durable 状态为准协调本地缓存；confirmed/stale/superseded
   不能被旧 prepared 遮盖。过期或不同输入只显示当前合法下一步；不能静默复用旧选择/许可。
   在前端回调也阻止已确认摘要再次提交，不仅依赖按钮或后端去重。
3. 对账保存本次 preparation/Preview、精确选择/影响和已核实主体所需的安全定位材料；读取
   **这一次**执行与实际绑定。读到别的当前 preparation 或仅原 TaskItem GET 成功不能直接解锁。
4. 暂停剩余范围复用既有 exact Preview admission outcome/readback，读取该次确认的已有执行，
   受理后显示真实入口/结果。刷新/重连/重启先恢复持久摘要与状态，不能自动 POST 或猜最近任务。
5. 分别测试本地准备、GET 恢复、另一摘要取代、过期、same/different principal、原请求已受理
   与确实未受理；暂停范围补已提交丢响应及刷新。两个实际连接/主体仍遵循原权限和非重放规则。

#### R4 / P1 — Metadata 决定分支仍在摘要 HTTP 内调用 Provider（AC-2；Scope 2）

定位：`manual_organize_preview.py:2270–2310`，
`manual_recovery_continuation.py:_prepare_continuation/_reusable_analysis_identity`。
复用只在 metadata_selection/correction 都为空且没有 metadata_reference 的分支启用；
任一已有候选或纠正决定继续走 live metadata。本轮两个真实 API 计数反例已复现。

1. 先扩展现有候选选择、直接 ID/query correction 集成用例，在 **Worker 分析完成后**记录
   search/detail/season/episode 计数，再调用 prepare-summary，断言这些计数不增加。
   另覆盖原 intent 已有 metadata reference；不要只测无决定的电影自动匹配。
2. 摘要消费该次完成分析的耐久身份/计划及决定版本，保留来源/pin/策略/选择的精确绑定。
   决定存在时也验证它与 durable identity 一致，不能直接跳过决定或用任意 identity 覆盖。
   需要完整命名/分类数据时从完整耐久证据读取；不靠只有 provider/id/title 的 Result 猜补。
3. 旧证据缺失/不完整/已过期时给出明确重新分析动作，由既有 Job/Worker 处理；
   不以同步 live fallback 掩盖缺失。保留 bounded Storage source/plan 校验，零执行权限/零 mutation。
4. 假 Provider 设为可阻塞/失败，证明摘要 HTTP 不等待它；确需新长分析仅准入可重开的工作。
   补 Movie/TV 必需字段及分类/命名一致性，不能因省 Provider 改变目标或丢掉 episode 信息。

#### R3 / P1 — 批次只逐项返回，未完成同页就绪子集与恢复分支（AC-1/3/4）

定位：`RunDetailTabs.tsx:1395–1416` 仅 `onInspectItem(child.itemId)`；
`ManualRecoveryContinuationService._prepare_continuation` 仍创建一个原项的单 item Preview；
`TaskItemRecoveryPanel` 同时只持有一个 preparation。
没有在当前任务处理界面收集多个独立就绪摘要、展示统一选择并只确认所选就绪项的组合。
现有真实浏览器 spec 的批次测试只断言返回证据区域，未生成/确认两个就绪项的子集；
专用五类完整处理、新阻塞再处理和安全附件剩余步骤也没有所要求的真实原生分支证据。

1. 先建一个真实原手动执行的两项可恢复失败 fixture，经现有任务内批量分析完成；
   不用只有 coordinator Task、没有 manual execution 关联的合成行冒充可执行恢复。
2. 在当前任务/类型处理界面读取每项已完成分析和独立 preparation，汇总就绪/未就绪/拒绝，
   展示每项原 pin、目标、附件与影响；不要求操作者逐个打开内部分析 Task 管理。
3. 用当前任务的多选只确认一个就绪项；调用现有精确逐项 admission，保留独立受理/拒绝。
   不伪造共同 Preview/pin，不新增跨任务批量 mutation。未选项仍有摘要和后续处理入口；
   成功/忽略/未知/过期项不进入执行选择，上下文不兼容明确分组或拒绝。
4. 对五类现有合法表单逐条连通保存/修复→分析→同页摘要→确认→真实 Worker。
   分析产生新 blocker 时在原任务/类型上下文处理其真实关联项，再回原恢复链；
   不以跳到内部 DryRun Task 结束旅程。至少跑原计划的技术失败→Metadata→确认→再次失败。
5. 用现有能证明安全的附件恢复权威接入“主文件已完成、附件剩余”的摘要，展示不重复的步骤，
   验证主文件/成功兄弟项未重放。不能证明的范围保留证据并拒绝；不能一概拒绝已有安全能力。
6. 完整 spec/自包含真实 fixture 覆盖两就绪只选一、五类、新阻塞、再次失败、未知只核查、
   桌面/窄屏/键盘/深链返回；看实际截图与动作，不能凭共享组件或测试总数宣称逐类完成。

#### R5 / 阻塞验证缺口 — migration proof 与最终证据仍超出实际证明（AC-7）

`task_base_migration_proof.py` 头部声称注入失败，但 main 只有建库/升级/比较，**没有失败注入**。
旧库 seed 的 snap-base/digest-base 只是 Task/intent 字符串，未保存真实 published revision；
base-authorization 只填入恢复 link，未创建/消费 manual execution authorization 记录。
`_read_facts` 只比较部分 Result 字段和 link，无法证明原计划约定的 pin/许可消费保留。

1. 保留真正 Task Base 建库的方法，使用其实际服务创建可读的历史 revision/pin、原 Task/Results、
   有效/已消费许可与关联执行/恢复链；保存准确 fixture 身份，不用悬空 ID 代替真实记录。
2. 比较升级前后所承诺的完整关键状态，重开读取并核对：合法旧 pin 可用，消费/撤销不复活，
   旧成功/未知效果不变，不因迁移新建执行。新增边界记录引用真实 task/item/Preview。
3. 在 migration 的实际新表/列写入中途注入错误，检查 schema marker、旧记录/pin/许可/关联及
   新边界没有留下可执行半状态；移除故障后能安全重开升级。保留首次失败及恢复读回日志。
4. R2–R4 修正后固定 executable candidate，按原 Required Tests 完整执行 T4；索引写清每条
   命令、候选/产物/依赖/fixture、退出码/计数/耗时及首次失败/复跑。Completion Report 使用
   同一轮真实数字和 wheel/image digest。已有正确门禁不需在开发每步反复跑，但最终候选必须齐全。
5. 对 wheel/Docker 的精确源码/served assets 和真实驻留恢复链保留内容证明；import loaded
   仍只证明装配。原计划的混合项/非重放/重连不能由单识别 happy path 自动推断。

### Slice 核对与范围决定

- RO-1/S-1、RO-2/S-2 保留 Task45.1/45.2 的既有 B PASS；本轮不扩大其接受范围。
- RO-3/S-3、S-4，RO-4/S-5 的 unknown/暂停连续性，RO-6/S-6 的完整验证仍 incomplete。
- RO-5/S-7 独立 Scan 完整退役仍未实现，保持本 Task 非目标。
- **不创建 Task45.4，不提交 Closure Packet，不宣称 Slice 关闭。** 当前 Contract 仍可满足，
  Task45.3 继续合法，不需 A 改范围；相同 ID/Base/Goal/Scope/AC/High/T4 修正后重新交审。
- 经验候选留 Slice 收尾合并：共享入口的分支证据必须覆盖“本地新建状态”和“持久恢复状态”；
  两者生命周期不同，不能用一个恢复测试替代另一个。
