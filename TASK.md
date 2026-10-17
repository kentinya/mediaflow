# Task 45.3 — 分类恢复的同页计划摘要与确认继续

遵循 [Development Workflow](docs/development-workflow.md)，从属于已提交的
[Slice45 Contract](SLICE.md)。规划/审查读取 [B 经验](docs/agent-experience/task-planner-reviewer.md)，
实现读取 [Developer 经验](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.3
Parent Slice: 45
Status: PLANNED
Task Base: 8f5cf4e284766bcc8894817d7640231e85050fb2
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Next Action: DEVELOPER IMPLEMENTS TASK 45.3
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

实现 Task45.3：五类恢复从“跳独立 Preview / 手工管理 DryRun Task”改为在同一处理界面完成
“保存决定/修复依赖 → 显式安全分析 → 同页计划摘要 → 选择就绪子集 → 确认继续整理 N 项 →
真实 Worker 执行”。复用既有 checkpoint、review/decision、analysis/batch continuation、
pin、Planner、`ManualOrganizeExecutionService.begin_web_execution` 与原子准入，未建立第二套
队列、恢复引擎或授权体系。

- **Domain** (`manual_recovery.py`)：新增 `ManualRecoveryPreparation` 与
  `ManualRecoveryPreparationStatus`。`PREPARED` 明确**不含** `authorization_id`/`execution_id`，
  不会为填字段提前签发权限；`CONFIRMED` 才链接精确执行。
- **Persistence** (`sqlite_runtime.py`)：新增 `manual_recovery_preparations` 表（additive，
  既有库重开即建，不改写旧行/结果/pin）及 create/get/get_current/list/supersede/complete；
  `admit_manual_execution` 增加可选 `preparation_id`，在同一原子事务内完成“消费一次性权限 +
  创建执行 + 链接摘要”，守卫式更新失败即整体回滚，不留孤立权限或执行。
- **Application** (`manual_recovery_continuation.py`)：抽出共享的 `_prepare_continuation`，
  `authorize_continued` 与新增 `prepare_summary` 复用同一套原项/分析/决定/来源/pin 校验与精确
  Preview；新增 `confirm_prepared` 绑定摘要、Preview、checkpoint 版本与 actor，仅准入所选就绪
  子集，并复用 `begin_web_execution` 的原子准入与重复/并发折叠。`discovery_for_preparation`
  提供无权限投影。
- **API** (`service_api.py`)：新增 `POST .../recovery/prepare-summary`（201，零权限、零 mutation）、
  `POST /api/v1/manual-recovery-preparations/{id}/confirm`（202，真实执行身份）及路由归一化；
  恢复详情投影附带 `manualRecoveryPreparation`。
- **Web**：`task-item-recovery.ts`/`api-client.ts` 增加严格 typed model 与两个调用；新增共享
  `SamePagePlanSummary.tsx`（复用 `organize-summary` 的 `ItemFindings`/破坏性影响说明），
  `TaskItemRecoveryPanel.tsx` 主路径为“生成计划摘要并在此确认 → 选子集 → 确认继续整理 N 项”；
  暂停整理的 withheld Continue 在 `OperationsLanding` 同一面板内生成剩余范围摘要并确认，
  不再跳独立 Preview（按钮改为“在当前界面生成剩余范围摘要”）；原一次性权限的精确 Preview
  兼容入口保留为折叠高级选项。
- **Tests/脚本**：`test_recovery_continuation.py` 新增 6 个后端旅程用例（只读摘要/确认子集与原子
  链接/过期与supersede/权限/actor/并发去重）；`test_task_persistence.py` 新增 preparation 往返与
  additive 迁移用例；`TaskItemRecoveryPanel.test.tsx` 新增同页 prepare→confirm 组件用例；
  `OperationsInventory.test.tsx` 新增暂停运行同页摘要确认用例；`operations-inventory.python.spec.ts`
  的原生恢复与暂停继续旅程改为同页摘要+确认；`wheel_smoke_test.py` 增加恢复准备 consumer 加载
  证明；新增 `docker_task_center_recovery_browser_proof.py`。

### 最终候选

- Implementation Head：`3d8fdbf308b34a81497849e7568481d64a2195ae`。
- 本 Task 实现 checkpoint：`ca86094522222e4a44c12864cdba0be0cfc90036`（实现）与
  `a507bda0665a4b8f6a8b2b4e7ac1ee925c7db805`（Docker 证明+报告），`0ae8fb9`（暂停继续 E2E），
  末次 `3d8fdbf`（报告）。`ca860945..3d8fdbf` 无 `mediaflow/`/`web/src/` 字节变化。
- Task Base：`8f5cf4e284766bcc8894817d7640231e85050fb2`（未移动）。
- 证据索引：`.git/validation-evidence/3d8fdbf308b34a81497849e7568481d64a2195ae/developer-45.3/`
  （`INDEX.md` 与 `docker-recovery/` 原始日志/矩阵/截图；仅本地可达，未推送）。

### 验证（候选 = 最终 checkpoint `0ae8fb9`）

- 隔离干净 checkout（exact `0ae8fb9`，无共享 schema48 运行库）：
  `python -m unittest discover -s tests` → **2488 tests / 7 skipped / OK / 187.3s**。
- `scripts/check_governance.py` PASS；`ruff format --check .`（371 files）、`ruff check .` 全通过；
  `compileall -q mediaflow tests scripts` OK；`pip check` 无破损；两份示例配置 `config validate`
  OK；`rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（exit 1）。
- Web：`typecheck`、`lint`、`format:check` 全通过；`npm run test -- run` **1123 passed (76 files)**；
  `npm run build` 成功；fake E2E **246 passed**。
- 真实 Python 浏览器：`playwright.python.config.ts operations-inventory.python.spec.ts`
  **27 passed / 45.1s**，含同页恢复旅程（prepare 201/零权限、confirm 202、真实 Worker MOVE）
  与暂停运行同页摘要确认。
- wheel：`pip wheel . --no-deps`（`sha256 5fa498c11cd13a75db3b6015c4378393d0035944db4547ef34b73dbf959a8688`）
  后用 `wheel_smoke_test.py` 安装验证，新增 `recoveryPreparationConsumer: loaded`。
- **既有失败（已在 Base 独立复现）**：主工作区共享 ignored 运行库 `.mediaflow/mediaflow.sqlite3`
  为 schema48，导致 `test_resource_library_pipeline.test_scan_cli_needs_no_path_or_metadata_token`
  报 “runtime database schema is newer”；在 Task Base 干净 checkout 中该用例 PASS，干净候选全量
  2488/OK，判定为环境既有失败，非本 Task 回归，交 B 判断。
- Docker 恢复浏览器证明：`.venv/bin/python scripts/docker_task_center_recovery_browser_proof.py
  --image mediaflow:task45.3-recovery`（需 `MEDIAFLOW_SMOKE_TEMP_DIR` 指向 Docker 可挂载目录）
  → **通过**：真实镜像/API/SQLite/常驻 Worker，识别决定→分析→同页摘要→精确确认→真实 MOVE；
  确认前 `sourceExists=True, targetExists=False`，确认后 `False/True`；`prepare-summary` 1 次、
  `confirm` 1 次、旧 `manual-recovery-links/execute` 0 次。image `4f5f00cd44fb`；证据：
  `/tmp/mediaflow-task45-3-docker-recovery-proof/{matrix.json,evidence.json,*.png}`。
- Docker release-security：`TMPDIR=<Docker 可挂载目录> .venv/bin/python
  scripts/docker_release_security_smoke_test.py --image mediaflow:task45.3-security`
  → **通过**（image `efe6148ca9d1`）；镜像内 `prepare_summary`/`confirm_prepared`/
  `create_manual_recovery_preparation` 均存在。
- **环境约束（非回归）**：本机 Docker Desktop 的挂载命名空间不含 `/var/folders`（默认 `TMPDIR`），
  因此两个 Docker 脚本必须用 `TMPDIR`/`MEDIAFLOW_SMOKE_TEMP_DIR` 指向项目内可挂载目录；
  `docker_release_security_smoke_test.py` 在 Task Base 用默认 `TMPDIR` 复现同一挂载失败，
  非本 Task 引入。

### 决定

- 摘要与执行权限分离：`PREPARED` 行不携带 `authorization_id`，确认才在同一原子准入内消费权限
  并链接执行，满足“保存决定不取得 mutation 权限、确认前零变更”。
- `confirm_prepared` 以摘要身份+Preview+checkpoint+actor 绑定，重复/并发确认折叠为同一次执行。
- 保留原 `authorize_continued`/`manual-recovery-links/execute` 兼容语义，未删除既有已接受旅程。

### 风险 / 偏差

- 五类恢复共用同一套 prepare/confirm 入口与既有决策表单；识别完整旅程已原生浏览器跑通，
  其余四类的专用表单保存→分析→同页摘要→确认已在后端与组件层接入并验证，但每类专用文案、
  窄屏细节与逐类浏览器分支的进一步细化仍属本 Task 可继续的剩余工作。
- 暂停整理的 Continue 重新授权已接入同页摘要（步骤 17），复用既有
  `ScopeContinuationService`/`submitRemainingScopePreview`，未新增队列或权限。
- 任务内有界多选（步骤 16）复用既有 `RecoveryBatchContinuationService`；批次的同页按项摘要
  汇总尚未接入，仍保留既有逐项准入/拒绝与恢复链接。

### 可复用经验候选

- 无（待 Slice 收尾统一整理）。

## B Review Result

```text
Reviewed Range: NOT REVIEWED
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: DEVELOPER IMPLEMENTS TASK 45.3
```
