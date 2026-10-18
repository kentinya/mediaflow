# Task 45.3 — 分类恢复的同页计划摘要与确认继续

遵循 [Development Workflow](docs/development-workflow.md)，从属于已提交的
[Slice45 Contract](SLICE.md)。规划/审查读取 [B 经验](docs/agent-experience/task-planner-reviewer.md)，
实现读取 [Developer 经验](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.3
Parent Slice: 45
Status: FIX REQUIRED
Task Base: 8f5cf4e284766bcc8894817d7640231e85050fb2
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Next Action: DEVELOPER CORRECTS THE SAME TASK 45.3 PER B REVIEW 8
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

### 16 — 接任务内有界多选及附件结果提示

- **改哪里：** 复用 `RecoveryBatchContinuationService`、现有批次结果和精确选择机制。
- **做什么：** 多选只限当前任务允许范围，分析逐项接受/拒绝；汇总各自持久摘要，只确认所选就绪项。
  保留每项原 pin/来源/版本/影响；上下文不兼容时明确分组或拒绝，不拼成一个伪共同快照。
- **完成标准：** 两个就绪项只选一个执行，未选项继续可处理；成功/忽略/未知/过期项分别拒绝。
  主文件执行并验证完成即可形成主项成功；附件步骤独立持久化。附件失败、未执行或冲突必须
  展示具体原因、来源/目标和按已绑定策略决定的处理指引（人工移动只是策略允许时的示例），
  不新增附件-only 自动恢复、不重放主文件，也不把附件警告显示为无警告的完整成功。

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
  根据真实当前状态变化。原 pin 不可用不静默 repin。主文件验证成功即可保留主项完成；附件
  失败/未执行/冲突需显示原因、来源/目标和按策略处理指引（人工移动仅是策略允许时的示例），
  不提供附件-only 自动恢复。
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
   子集确认→实际 Worker 结果；网络/权限修复后的新阻塞转类、附件结果/人工处理指引、再次失败。
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

按 B Review 3 在同一 Task 45.3 内修复 R2/R3 未知批次确认、R4 TV durable identity 与 R5 迁移/候选证据缺口，并补充 Task Center 恢复动作对比度及键盘焦点验证。没有扩大 Contract 或 Task 范围，没有改 Slice、Roadmap 或稳定需求。

- 分析结果单独持久化完整、限长且脱敏的执行身份；TV episode title、episode metadata 与 facets 在 durable summary 重建后保留。旧版/不完整展示证据要求 Worker 重分析，summary 准备不调用 live Provider。
- 批量确认的网络结果未知时，按主体/Task/子项维持独立提交锁；只有读回同一 batch、preparation、选择与 effect 后才解锁。未自动重发；兄弟项仍独立可见和可恢复。
- Migration proof 从真实 Task Base 旧代码与记录出发，验证 schema 45→46、重新打开、ALTER 中途失败回滚及恢复；旧 preparation 不会取得执行权限。
- Task Center 识别保存、单项摘要确认、批量确认和未知结果锁定动作均有 ≥4.5:1 对比度和键盘焦点回归检查。

### 检查点

- Task Base：`8f5cf4e284766bcc8894817d7640231e85050fb2`。
- 最终 executable checkpoint：`46f54bc2a33fb5ab486a11f96714c6c1a41119f6`。
- 已 fast-forward `slice/45-scope-pending` 到该 SHA。Base..Head 共 37 个文件；提交只含 Task 45.3 合同文档与所需实现、脚本、测试，没有改 `SLICE.md` 或 Roadmap。
- T4 原始日志、截图、wheel、迁移证明、容器矩阵与 AC 映射：`.git/validation-evidence/46f54bc2a33fb5ab486a11f96714c6c1a41119f6/developer-45.3-final-20261018/INDEX.md`。

### 验证

最终候选在隔离、干净 worktree 完成 T4 门禁：

- Governance、`ruff format --check .`（372 files）、`ruff check .`、compileall、`pip check`、两份示例配置验证和 FFmpeg/FFprobe 禁用扫描全部 PASS。
- 完整 Python：2503 tests，7 skipped，240.948s，PASS。真实 Task Base schema45→46 migration proof 与 ALTER 失败回滚 PASS。
- Web typecheck/lint/format PASS；Vitest 76 files / 1129 tests PASS；production build PASS；fake Playwright E2E 246 PASS。
- 真实 API/SQLite/Worker Operations 浏览器 E2E 28 PASS / 51.6s；Unicode 主体 1 PASS；Task Center production visual E2E 2 PASS。实际检查桌面与 380×720 窄屏截图、同页摘要和恢复按钮。
- wheel build SHA-256：`a09d48f308f34d1813bd25ce7f677db5f6bf0d3d61598dd7aae68273ac10d36d`；wheel smoke PASS。另在独立 venv 从 `site-packages` 导入安装 wheel，TV durable identity→摘要重建用例 1 PASS。
- Docker release-security 与 recovery browser proof 均 PASS，并使用同一完整镜像 ID `sha256:3dc19a97bea674b464ae2c673a25e71b24dbc33b7afaae41ad8a377a01014760`。从镜像提取后，163 个 Python 源文件及 4 个 Web served assets 与候选构建逐字节相同。Recovery proof 在确认前 source 存在且 target 不存在；显式确认后只有选中项被真实 Worker 移动。
- `git diff --check 8f5cf4e284766bcc8894817d7640231e85050fb2..46f54bc2a33fb5ab486a11f96714c6c1a41119f6` PASS；候选 worktree 最终 clean。

### 失败记录与风险

- 较早候选 `65fb170b4ba7ab861836c6bf4f2224498ad89032` 的全量 Python 曾有 1 项失败：测试期望有界展示 evidence 不含 `overview`。在 `76902dba6ab762bec30c356ed223af443148f567` 将 overview 从展示字段移除、同时保留独立的完整执行身份后，全量测试通过；最终候选再次通过。首次失败日志保留于对应 SHA 证据目录。
- 最终全量 Python 报告的 7 个 skip 保持可见。Vite 仍报告一个 minified JavaScript chunk 大于 500 kB；`npm ci` 报告依赖树中 2 个 high severity audit findings，本 Task 未改依赖。
- Docker/Colima 的挂载临时目录指向候选 worktree 内 `.mediaflow/validation-temp/`；没有访问用户运行库或生产介质。

### 决定

**READY FOR B REVIEW。** 本报告不声明 Task PASS，不更改 B Review 3 结论或 Task 状态。

### 可复用经验候选

无；留待 Slice 收尾统一整理。

### Developer correction — Review 5 / 2026-10-18（本轮最终报告）

**Executable checkpoint:** a6ed23b030bd1a685562ad4028786caa70b197c1。
本轮连贯修正提交：722b4854bc91c54236754bf5e0a1516e851c3320（R6–R8/测试）及
上述最终视觉遮挡修正。不 amend 任何既有审查历史，不推送。
Task Base 保持 8f5cf4e284766bcc8894817d7640231e85050fb2，High/T4/Goal/Scope/AC 不变。

交付：
- R6：以真实 preparation→execution→selected item→verified Result 及最多16段、同来源/库/pin
  的持久分析 lineage 统一当前 failure/attention/文件分页计数和 checkpoint 动作；
  排队/再次失败/未知/未选项不冒充解决，不改原失败历史。
- R7：五类列表行内进入原 Task/type/item 上下文，新阻塞直接嵌入共享合法表单；
  保存/继续提交真实关联项，原页面更新摘要，不需要操作内部分析 Task 后手工返回。
  关闭详情保留文件列表筛选/分页；视觉复核发现双面板遮挡后修复为只显示一个处理面板。
- R8：fake Provider 按查询标题隔离候选，完整spec不再被前序fixture累积候选污染；
  未扩大生产max_candidates、未skip或弱化业务断言。新增成功/再次失败、重开、来源/pin不符、
  覆盖策略拒绝及独立影响确认；安装wheel真实成功恢复测试不再只验证missing-item拒绝。

最终候选在干净隔离checkout /private/tmp/mediaflow-task45-a6ed23b 完整验证：
- Python full：2512 tests，7 skipped，236.434s，PASS；包含本轮聚焦回归。
- Governance、ruff format（374 files）/check、compileall、pip check、两份示例配置验证、
  FFmpeg/FFprobe禁止依赖扫描 PASS。
- Web typecheck/lint/format PASS；Vitest76 files/1130 PASS；production build PASS；fake E2E246 PASS。
- 真实Python/API/SQLite/Worker完整spec36 PASS；Unicode1 PASS；production视觉spec2 PASS。
  五类标签→文件处理、技术失败→新Metadata→同页摘要→再次失败/成功、批次少选与unknown、
  暂停重新授权/重开均有实际用例。实际查看桌面/380×720及键盘确认区域，修复遮挡；
  部分自动截图锚点只显示表头而非整个表单，不将capture exit扩大为全面视觉PASS。
- 真实Task Base schema45→46迁移/合法pin/许可消费/结果保留/重开/ALTER故障回滚 PASS。
- wheel build/smoke PASS；安装site-packages版本执行5项真实恢复/确认/Worker/MOVE回归 PASS。
  wheel SHA256：359d14f7f42a3324754c1c78dcaa1183772dd5a0f9222cf99092a044ba3820c4。
- Docker release-security和recovery proof PASS；真实常驻Worker消费，同页准备零权限、确认后MOVE。
  完整image ID：sha256:ac21aa396fc6cd768842b7818cfc63090595c8cec5e08e4a6a02a6dcb24f0463。
  提取镜像/安装包：163个Python源码、4个Web served assets与本候选逐字节一致。
- 证据、命令/cwd/依赖/构建摘要/exit/duration、AC映射、原始logs/trace/截图及299件产物hash：
  .git/validation-evidence/a6ed23b030bd1a685562ad4028786caa70b197c1/developer-review5-final-20261018/INDEX.md。
  仅本地可达，未推送。最终报告为document-only successor；须以实际diff证明后复用此证据。

真实失败与限制：
- 开发期红测、fixture污染、测试选择/URL顺序/disabled焦点错误以及视觉遮挡均保留原日志；
  首次Docker在/private/tmp挂载失败，定位daemon命名空间后改为项目内可挂载临时目录。
  最终候选Docker recovery首次因build尚未完成记UNAVAILABLE，依赖完成后实际重跑PASS。
- 前ff34报告曾错误写成只有schema48失败；其原始full实际2507/7skipped/OK，真实浏览器
  32PASS/2FAIL。此前证据不代替当前候选完整门禁。Vite大chunk及既有ResourceWarnings保留。
- **未完成的条件验收，交B/A判定而非豁免：附件-only剩余步骤。** 现有OrganizerExecutor
  先处理并验证附件再执行主文件；manual execution持久步骤但无独立附件-only admission/consumer。
  checkpoint对一般partial/known effects仅investigate，未知明确拒绝；manual recovery要求
  task_retry_requested + 完成单项DryRun并重验原source。未找到“主文件已完成、仅续附件”的
  现有合法路径。没有发明补偿引擎、放开partial/unknown、伪造失败状态或重放主文件。
  具体代码/边界记录于INDEX，B核对后按Review5交A处理Contract差异；不以所有附件拒绝冒充完成。

**READY FOR B REVIEW（带上述未解决条件验收项）。** 保持FIX REQUIRED供B决定；本报告不自判
Task PASS，不改变B Review5结论、Slice/Roadmap/Progress/稳定需求，不规划下一Task、不关闭Slice。
预存图片删除意图、未跟踪图片/.DS_Store/zip/旧测试产物保持，私有配置ignored/untracked/unstaged。
可复用经验：无新增，留待A在Slice收尾统一整理。

## B Review Result

### B Review 8 — 2026-10-18 (Contract recheck)

```text
Contract Clarification Checkpoint: a346f144981770b915558b2839b8282d0322e20f
Decision: TASK45.3 CONTINUES WITH LEGAL WORDING ADJUSTMENT; PRIOR FIX REQUIRED REMAINS
Next: DEVELOPER CORRECTS THE SAME TASK 45.3 AGAINST THE CHECKPOINTED CLARIFICATION
```

用户补充说明“用户手动移动”只是举例，实际附件处理必须由固定的 OrganizePolicy/策略能力决定。
因此 Review 7 中把手动移动写成统一 next action 的表述被本次 Contract clarification supersede；
Review 7 的执行顺序、主文件不被附件阻塞、逐附件耐久结果、未知效果不可重放和 warning 不得冒充
完整成功等结论全部保留。

Developer correction must expose the strategy-derived bounded next action for each known attachment
outcome. It may say manual move only when that exact policy permits or requires it; otherwise it must
show the policy-allowed skip, rename, explicit conflict decision, re-analysis, inspection or other
existing action. When no safe action is permitted, show the reason and investigation/correction path.
Unknown or attempted-unverified effects remain investigation-only and must never be rendered as a
known manual move or replay instruction.

### B Review 7 — 2026-10-18

```text
Reviewed Range: 8f5cf4e284766bcc8894817d7640231e85050fb2..a6ed23b030bd1a685562ad4028786caa70b197c1
Executable Candidate: a6ed23b030bd1a685562ad4028786caa70b197c1
Contract Checkpoint: 9657d96
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: DEVELOPER CORRECTS TASK45.3 IN THE SAME TASK LOOP
```

#### Review 7 evidence

- The A-authorized Contract revision is now checkpointed at `9657d96`; governance passes against the
  committed `HEAD:SLICE.md`. The revised meaning is: a verified primary-file operation is enough for
  the primary item to complete, while every attachment failure, skipped step or target conflict stays
  visible with its reason, source, target and manual-move guidance. Attachment-only automatic recovery,
  compensation execution and primary replay remain out of scope.
- The candidate's prior R6/R7/R8 recovery fixes and its reported T4 evidence remain valid. This review
  is limited to the newly effective attachment completion contract and does not reopen those passed
  recovery findings.

#### Blocking implementation gaps

1. **Primary execution is still blocked by attachment state.**
   `OrganizerExecutor.execute` first requires every attachment source/target to be readable and
   conflict-free (`mediaflow/application/organizer.py:481-507`), mutates all attachment plans before
   the primary plan (`:537-587`), and only then executes the primary (`:588-614`). A missing sidecar,
   attachment collision, attachment verification error or attachment-only Storage failure therefore
   prevents the main file from being moved. This directly violates the revised user outcome.
2. **Attachment outcomes are not durable enough for the promised journey.**
   The current `ExecutionResult`/`PersistentResultRecord` path records aggregate errors and completed
   operation markers, but it does not create a bounded per-attachment outcome carrying reason, exact
   source and exact target when an attachment is skipped or fails after the primary succeeds. The
   existing plan attachment list is not a substitute for a runtime failure explanation.
3. **Operator copy does not give the requested manual recovery.**
   `ProblemFilePanel` maps `attachment_collision` to “check the attachment target and choose conflict
   handling” and `PreviewDetailPage` only lists attachment type/language/operation/filename. Neither
   states that the primary is complete, names the attachment reason/source/target in the result view,
   and tells the operator to move that attachment manually. A warning must not render as unqualified
   full success.

#### Required correction (same Task, detailed implementation order)

1. Keep the existing primary Storage validation, exact pin/source checks, mutation authority,
   concurrency fencing and unknown-effect rules unchanged. A missing or conflicted attachment must
   not weaken any primary safety check.
2. Change execution ordering/admission so the primary operation can be completed and verified even
   when an attachment is unavailable, collides, or is otherwise known to be unexecutable. Do not
   replay or compensate the primary. Do not silently overwrite or delete an attachment.
3. For each attachment, retain a bounded independent outcome with at least: attachment type/language
   when known, operation/status, exact source Storage/path, exact target Storage/path, normalized reason,
   and next action `手动移动附件` (or an equivalent bounded localized message). Successful attachment
   steps may remain successful; failed/unexecuted/blocked steps must be distinct and durable.
4. If an attachment mutation has already crossed the mutation boundary and its effect is uncertain,
   preserve the existing `unknown`/investigation-only semantics. Do not convert it into a manual-move
   instruction that implies the source/target state is known, and do not advertise retry/replay.
5. Project the per-attachment outcomes through the existing Result/detail/export/audit contracts and
   the same-page summary. The primary success plus attachment warning must be visibly `partial` or
   equivalent warning state, never a silent full-success view. Show reason, source, target and manual
   move guidance without exposing secrets or host roots.
6. Update the focused backend, persistence, API and Web tests. Required cases are: primary success +
   missing attachment; primary success + attachment target collision; primary success + attachment
   Storage unavailable; successful primary/attachment regression; attachment mutation uncertain;
   exact source/target/reason/manual guidance in summary, result, detail, export and audit. Preserve
   the existing no-replay tests and all prior recovery/batch/authority tests.

#### Review 7 decision

`FIX REQUIRED` remains in the same Task. This is a direct implementation defect under the now
checkpointed Contract, not permission to create an attachment-only recovery Task. The Developer must
submit a new coherent checkpoint and actual T4 evidence; B will then review the candidate again.

### B Review 6 — 2026-10-18

```text
Reviewed Range: 8f5cf4e284766bcc8894817d7640231e85050fb2..a6ed23b030bd1a685562ad4028786caa70b197c1
Executable Candidate: a6ed23b030bd1a685562ad4028786caa70b197c1
Report-only successor: 1ee9c82a62530e08b9c80731f01285dbd478b6e6 (TASK.md only)
Decision: FIX REQUIRED — CONTRACT DECISION REQUIRED FROM A
Slice Required Outcomes all satisfied: NO
Next: A CHECKPOINTS WHETHER ATTACHMENT-ONLY CONTINUATION IS IN OR OUT OF THIS CONTRACT
```

#### Review 6 evidence

- Governance passed with `python3 scripts/check_governance.py`. The executable candidate is the
  exact source named by the Developer report; the successor commit changes only `TASK.md`.
- The candidate's retained T4 index and source/served-artifact identities were inspected. The
  reported final gates are internally consistent: isolated Python `2512 tests / 7 skipped / OK`,
  Web quality/unit/fake/real-browser, migration, wheel and Docker evidence. Independent focused
  checks on this checkout also passed: Python recovery/lineage/batch/checkpoint/manual execution/
  mutation authority `171 tests / 18.865s / OK`; Web operations Vitest `43 tests / 3 files / PASS`;
  `npm run build` PASS; `git diff --check` PASS.
- R6/R7/R8 corrections are present in the executable diff: multi-hop lineage now closes only the
  verified current problem, new blockers render inside the original Task/type/item context, and
  the batch fixture isolates Provider candidates. No new P1 was found in these corrected paths.

#### Blocking Contract gap — attachment-only continuation

This is not a safe Developer omission that can be repaired by another small patch:

1. `OrganizerExecutor.execute` requires the primary source to exist before any plan is admitted
   (`mediaflow/application/organizer.py:462-471`), validates the primary destination, then mutates
   the attachment plans and always mutates/verifies the primary plan (`:537-599`). There is no
   attachment-only admission or consumer in the existing manual execution path.
2. Manual recovery preparation still requires the original item to be in `task_retry_requested`,
   finds a completed linked single-item DryRun, and rebuilds the exact primary plan under the same
   pin (`mediaflow/application/manual_recovery_continuation.py:488-505`). This cannot represent a
   completed primary whose source is gone while only a sidecar remains.
3. The checkpoint safety projection intentionally exposes investigation, not replay, for unknown
   or attempted-unverified effects (`mediaflow/application/processing_checkpoint.py:919-923`).
   Relaxing this, fabricating a failed attachment state, or replaying the primary would violate
   the Slice safety invariants.

The user-triggered scenario is a real main-file move followed by a sidecar failure: the operator
returns to the task expecting the remaining attachment to be explained and, when an existing
authority can prove it safe, continued in the same summary/confirmation flow. The current
architecture can only fail closed and preserve investigation evidence. That is safe, but the
Task's step 16, AC-3/AC-4, and Required Tests explicitly prohibit using refusal of every attachment
case as a substitute for an existing safe capability. Adding such capability would introduce a
new mutation admission, durable remaining-step state, and execution fencing; it is High-risk work,
not a legal continuation of this Task without a Contract decision.

#### Decision and required next action

`FIX REQUIRED` remains the only valid Task result; this is a Contract blocker, not a request to
invent a compensating executor. B does **not** create Task45.4, weaken the attachment requirement,
or submit a Closure Packet. A must checkpoint one of the following before Developer work resumes:

- **Defer/clarify:** explicitly defer attachment-only continuation and define the accepted
  investigation/refusal journey, then B rechecks whether the current Task can PASS against the
  revised Contract; or
- **Keep in scope:** authorize a new coherent implementation boundary for attachment-only
  admission/consumer (with durable remaining-step semantics, exact source/pin/permission binding,
  no primary replay, Worker claim/fence, and failure/reopen tests), then B legally adjusts or
  replans this Task after the A checkpoint.

Until that A decision, the candidate is not PASS and Slice closure is not eligible. Existing dirty
user files and all prior review history remain untouched.

#### User clarification pending A checkpoint — 2026-10-18

用户明确倾向于：主文件执行并验证完成即可视为主项完成；附件若失败或未执行，只展示具体原因、
目标和人工处理指引，由用户自行移动附件，不提供附件自动恢复或主文件重放。该方向可作为上方
“Defer/clarify”选项，但它仍是对当前 Slice/Task 验收语义的材料性收窄；在 A checkpoint 之前，
不得把它当作已生效 Contract、不得将附件失败标成无警告的完整成功，也不得继续 Developer 实现。

```text
Reviewed Range: 8f5cf4e284766bcc8894817d7640231e85050fb2..ff34f0faa4a8697e9ef6e5b659a57d31a5795e0a
Executable Candidate: ff34f0faa4a8697e9ef6e5b659a57d31a5795e0a
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: DEVELOPER CORRECTS THE SAME TASK 45.3
```

### B 独立验证 — Review 5 / 2026-10-18（当前结论）

本轮审查实际 Task Base..ff34f0f，结论 **FIX REQUIRED**。继续同一 Task45.3；
ID/Base/Goal/Scope/AC、High/T4 不变。保留 Developer 报告、历史 Review 和所有无关脏文件；
未改产品代码、SLICE、Roadmap、Progress 或稳定需求。当前行动以下方 Review 5 为准。

#### 已确认进展与实际验证

- 治理 PASS，工作树 SLICE 与已提交 Contract 一致；完整 Base..Head manifest 及关键实现已核查。
- B 在精确候选隔离 checkout 独立运行恢复/批次/checkpoint/manual execution/persistence
  五模块：**175 tests / 21.596s / OK**。Review 4 长简介问题已修复，3900/5200/4096/4097、
  尾部分类关键词、重开与 TV identity 回归通过，不再要求重复改该边界。
- B 独立完整真实 Python/API/SQLite/Worker 浏览器 spec：**33 passed / 1 failed / 54.5s**，
  workers=1、retries=0、trace on、独立输出目录。新增 Metadata 候选/纠正、分类、Rename、
  技术失败→新Metadata→再次失败及暂停确认/未知响应/重启确已运行；不等于全部入口验收。
- B 独立生产服务/API/SQLite + 临时 Local/fake Provider 完成两段分析→精确确认→真实Worker
  成功，再查当前问题并重开数据库，复现 R6。未操作用户媒体/配置/运行库；未发现或宣称实际
  重复 Storage mutation。已查看本轮新阻塞桌面图和380×720摘要图，普通路径仍进入内部Task。
- 当前候选 Developer 原始日志确有隔离 full Python **2507 / 200.697s / OK (7 skipped)**、
  Web unit **1129**、fake E2E **246**、Unicode **1**、静态质量/build/wheel smoke 结果。不能
  继续说“只有schema48失败”；工作树报告需与实际日志对齐并保留首次失败。Developer real-Python
  是 **32 passed / 2 failed**（同一批次失败及trace ENOENT）；B独立输出仅复现批次失败，
  未把ENOENT当产品缺陷。未重跑完整T4，未把46f旧镜像当作本候选证据。
- 原始日志、probe、trace、实际截图及证据限制索引：
  `.git/validation-evidence/ff34f0faa4a8697e9ef6e5b659a57d31a5795e0a/b-review5-20261018/INDEX.md`。
  仅本地可达；按workflow在已证实阻塞后提前拒绝，不以不完整验证声明PASS。

#### R6 / P1 — 多段恢复成功后当前失败/待处理投影未闭合（AC-3/5/7）

最终execution已completed且选中主文件已MOVE；原任务的failure文件页仍返回已恢复的
`TechnicalRecovery.2019.mkv`及真正效果未知的兄弟项，共**2项**，前者还提供retry。
中间Metadata分析任务虽无类型问题却仍占attention。数据库/API重开前后相同。期望当前失败
仅剩未知兄弟项**1项**，中间任务退出attention；原任务因未知兄弟仍需处理，历史失败不删改。

Developer依次完成，不新建Task：

1. 将证据目录 `recovery_probe_reopen.py` 的成功链收敛进现有测试：失败+成功/未知兄弟→
   新Metadata→合法决定→下一段分析→原项摘要确认→Worker成功。先断言当前问题item_id集合、
   文件/任务计数和中间项attention，形成确实捕获本反例的红测。
2. 核对 `sqlite_runtime.py:_run_query_document` 的 `completed_preparation_follow_up` /
   `safe_continuation` 与 `_problem_item_predicate('failure')`；现投影仅消费直接source_item
   或一段child blocker，未与 `_find_completed_analysis` 的持久多段链一致。复用明确的
   lineage/preparation/execution/item/result，建立一致的当前问题判断，不另建恢复状态体系。
3. 列表、总数和类型文件页在分页前共用后端权威。只在该精确项有已验证成功效果后移除待办；
   prepared/accepted/queued/analyzing/再次失败/unknown不算解决。同一execution的其他项成功
   不替代本项成功；不按文件名/时间/相同目标猜关联，不伪造原Task/Result为成功。
4. 核对checkpoint及可操作入口，已解决链不再指导重新分析，保留结果/历史查看。不能靠前端
   隐藏、删除旧task/item/result/review或整任务清零掩盖问题。
5. 补fresh/reopen、再次失败、未选项、不同来源/pin回归；原生类型入口完成后刷新核对原文件
   退出当前失败、中间待办退出、成功兄弟不变、未知兄弟仍只可核查。

#### R7 / P1 — 新阻塞仍要求处理内部分析Task（AC-1/3/5）

`TaskItemRecoveryPanel.tsx` 的“查看关联分析条目”经 `OperationsLanding.tsx` /
`TaskDetailPage.tsx` 跳到 `/operations/tasks/$taskId`。新增technical用例断言内部分析Task URL，
再靠 `page.goBack()` 回原项准备摘要，不满足RO-3普通恢复无需处理内部DryRun Task。
`openNativeRecovery` 从全部任务→通用详情→查看证据开始，不能代替五类列表行内入口验收。

1. 保留共享恢复API、原pin/决定校验和Worker；以原Task/type/item处理上下文承载后端明确
   关联的当前阻塞及对应合法表单，不另外建立五套恢复服务。
2. 保存和继续发往真实关联item，不把决定写到旧原项。保留原任务身份、尝试链、输入/选择和
   分析进度；下一段完成后在当前处理界面展示原恢复摘要并确认。
3. 普通路径不要求用户打开内部Task后手工返回；可以保留次级诊断/历史链接。新阻塞提供问题
   说明和直接处理动作，不把内部状态枚举或授权材料当作用户下一步。
4. 真实浏览器从五类标签的行内动作进入task/type文件列表，完成各自输入。技术失败案例在
   同一上下文完成新Metadata→摘要→确认→结果，检查筛选/分页/返回、重连、窄屏和键盘；
   不删除后端lineage/权限断言以绕过缺口。

#### R8 / 必需门禁失败 — 修复共享Provider fixture污染（AC-4/7）

完整spec的 `two ready batch children aggregate their summaries and only the selected subset is confirmed`
在 `seed_batch_summary_recovery` 准入409。B fresh fixture成功；先播种六类恢复及混合批次
则失败。fake Provider累积候选，正常 `max_candidates=20` 截断后BatchSummaryB候选不可选；
这是harness污染，不是证实生产准入错误，更不能提高生产上限规避。

1. 让现有harness按fixture/请求正确隔离或确定性匹配候选；保留首次失败，重复fresh/污染反例。
   禁止扩大生产候选边界、绕过合法选择、skip、减断言或只跑grep来造绿。
2. 修正后运行完整真实Python spec，含原批次未知确认和少于就绪总量选择；再冻结候选完成
   原Required Tests全部T4，新源码/测试/harness不能继承旧候选最终PASS。
3. 补准确INDEX：source SHA、dirty内容、cwd、依赖/构建/wheel/image身份、命令/exit/counts/
   skips/首次失败与复跑。现有ff34日志可据实引用，但报告或目录名不替代来源与产物校验。
4. 当前wheel consumer仅验证missing-item/missing-preparation拒绝，不是成功恢复执行证明。
   按原门禁以安装产物实际完成恢复/确认消费；补当前候选Docker recovery/security、源码与
   served assets一致性、迁移/重开和实际桌面/窄屏/键盘证据。本轮没有找到这些边界的完整
   新候选索引，不声称已失败或已通过，也不重复要求已经证明的功能从零重写。

#### R5 剩余验收及安全边界核对（承接Review 4，不扩建新引擎）

- Rename用例不证明覆盖许可/破坏性影响确认。按原Required Tests补实际冲突许可路径，
  验证无原策略许可拒绝、合法许可仍需精确确认、确认前目标零覆盖。
- 附件仅限**既有权威可证明安全的剩余步骤**。当前checkpoint对unknown effect及一般partial
  仅允许investigate，不能为补案例放开拒绝或重放主文件。先交代现有executor/持久步骤/准入
  路径及适用状态；能证明的路径接同页摘要并用真实Worker验证仅处理附件。若不存在，提交
  具体能力/Contract差异给B核对并交A判定，不自创通用补偿、不改Task/Contract弱化义务，
  不以“所有附件拒绝”冒充完成；其他确定修正可继续。
- 暂停继续及五类输入已有实证进展。将原pin A→Active B、原pin缺失、GET不调用Provider、
  未知响应非重发与权限边界映射到最终候选具体测试/日志，而非泛称full suites covered。

#### Slice复核与下一步

RO-1/S-1、RO-2/S-2先前Task PASS保留，本次新增链的当前问题回归必须修复；RO-3/S-3/S-4、
RO-4/S-5异常连续性及RO-6/S-6当前验收仍未完成。RO-5/S-7独立Scan退役未实现且不并入本Task。
**继续Task45.3，不创建45.4、不提交Closure Packet、不宣布Slice关闭。** 修正后重新审查
实际checkpoint及全部Required Outcomes；经验留待Slice收尾统一提炼。

---

### B 独立验证 — Review 4 / 2026-10-18（历史结论；候选46f54bc）

本轮审查新的实际 checkpoint；Developer 的工作树 Completion Report 已读取并保留。
Task45.3 继续合法，ID/Base/Goal/Scope/AC/High/T4 不变；不需 A 修改 Contract。
旧 Review 3 原文保留在后面供当轮修正对照；当前行动以上方 Review 5 为准。

- 治理 PASS；已提交 Slice45 ACTIVE、工作树 Contract 与 Roadmap 对齐。检查完整
  Base..Head manifest、15cee31..46f54bc correction 范围及关键实现/测试；未改产品代码、
  Slice/Roadmap/Progress/稳定需求。保留本轮前已存在的 TASK 报告/Review 3 与全部无关脏文件。
- 在精确候选隔离 worktree 独立执行相关 Python 五模块：**171 tests / 15.546s / OK**。
  完整真实 Python/API/SQLite/Worker 浏览器 spec：**28 passed / 51.6s**。
- 独立 TV 原反例：Worker 分析和摘要目标都保留 `Episode 1`，prepare-summary=201，
  Provider **7→7**；两个电影决定分支 Provider detail **4→4 / 2→2**，摘要201且真实继续成功。
- 独立原生批次反例：两个就绪项只选一个，后端202提交后丢响应，barrier延迟批次GET完成；
  页面正确显示未知并锁定，精确读回后确认一项confirmed/另一项prepared，确认POST始终**1**。
  随后驱动真实生产 Worker，只移动已选 B，未选 A 来源保留；查看1536×1024/380×720实际截图。
- 独立运行真实 Task Base schema45→46 migration proof PASS：合法 published revision/pin
  通过生产 validator，原许可消费/关联/结果保留，ALTER中途故障回滚及安全重开通过。
- Developer 最终原始证据现已可读：全Python **2503 / 7 skipped / 240.948s / OK**、Web unit
  **1129**、fake E2E **246**、real-Python **28**、Unicode **1**、visual **2**、wheel和Docker。
  独立校验全部**207**件产物hash、提取镜像**163**个Python文件与候选逐字节一致，4个Web产物
  与精确候选构建一致；wheel摘要与报告一致。旧“日志缺失/只有schema48失败”缺口本轮已解决，
  不再作为阻塞。计数通过只证明实际案例，不能推定下面尚未运行的原生分支。
- 查看实际批次/窄屏/容器摘要图；本轮未独立重跑完整Python/Web fake/Unicode/wheel/Docker，
  未声称完成五类恢复、全部键盘/暂停/附件的整体验收。新确定阻塞允许按workflow提前拒绝。
- 耐久原始日志、probes、trace、截图、产物核对与命令索引：
  `.git/validation-evidence/46f54bc2a33fb5ab486a11f96714c6c1a41119f6/b-review4-20261018/INDEX.md`。
  仅本地可达，未推送。

#### R4 / P1 仍未完成 — 合法长简介导致已完成分析无法生成恢复摘要（AC-2/3/7）

定位：`evidence_capture.py:_execution_identity_document.exact_text`（约400–406行）及
`manual_recovery_continuation.py:_reusable_analysis_identity/_build_identity`。
单字段4096字符限制遇到较长overview时将**整个**执行身份置空；读取方只接受该身份，
摘要遂拒绝并要求重新分析，而相同Provider输入经新Worker分析仍会触发相同限制。

独立真实链路采用同一合法Movie/策略/临时源，仅改变不含敏感信息的简介长度：

| Provider overview | Worker分析 | 执行身份 | 同页摘要 | Provider计数 |
|---|---|---|---|---|
| 3900字符 | completed，生成合法目标 | 已保存 | 201 prepared | 4→4 |
| 5200字符 | completed，生成相同合法目标 | 被整条丢弃 | 409 preview_blocked，指引重新分析 | 4→4 |

5200字符远小于现有128KiB整体身份边界，域对象和正常规划均接受；这是当前恢复链的可用性缺陷，
不是要求支持任意无界输入。源文件均保留，未发现重复mutation或数据损失。

Developer按下面顺序修正，不新建Task，不改用户配置或模板规避：

1. 先将上述3900/5200真实回归加入现有恢复fixture；补4096附近边界。保持原完整Worker分析，
   断言数据库reopen后仍可prepare→confirm→实际Worker结果，准备阶段零新增Provider/许可/mutation。
2. 对照实际 `MediaIdentity`、Naming和Classification消费者核对持久输入边界。修正**写入和读取**
   两处4096限制，使该合法案例可无损重建；优先复用现有整体字节预算/规范化模型或已完成的精确
   计划，避免扩大改动。仅增大写入限制而不改读取方仍会失败。保持有界与secret-free，不同步回源。
3. 禁止裁剪简介后继续分类：`classification.py:_keyword`实际读取overview；至少用简介末尾的
   分类关键词证明原分析与重建摘要的MediaLibrary/目标完全一致。单集/多集字段、facets及C身份
   继续沿用已修好的无损规则，不以只保留title/providerId代替完整语义。
4. 对真实旧/不完整记录保留明确重新分析动作；新Worker必须能产生可复用事实。对真正超过整体
   支持边界的输入给出准确且可行的说明，不能将“再分析”当作不会改变结果的循环动作，也不能
   拒绝本次已被正常主链接受的5200字符输入来制造通过。
5. 先跑该反例、TV和metadata候选/纠正回归，再冻结新候选按原T4 Required Tests完整交付。
   本轮已通过证据只属于46f54bc，新的executable修正不能直接继承旧候选的最终全量PASS。

#### R5 / 原定验收缺口仍未完成 — 补齐缺失旅程，准确收窄证据声明（AC-1/3/5/6/7）

不是要求再补可选反证。原Required Tests已明确要求下列业务分支；当前28项spec与容器proof
实际没有完整执行它们。Python旧兼容authorize/execute测试不能替代新的原生同页旅程。

1. 复用现有harness/临时源/假Provider，分别从Metadata候选/纠正、分类、主文件或附件冲突、
   技术失败对应类型入口，完成合法输入→Worker分析→同页摘要→确认→真实Worker结果；
   识别已通过可复用，不重新建立五套编排。至少一例需要覆盖冲突许可及零提前覆盖。
2. 用同一混合任务跑“依赖修好→分析产生新Metadata阻塞→进入新类型补正→摘要确认→执行再失败”，
   读回当前类型/计数及两次失败历史；保留成功/未知兄弟项。不能只测试九标签能打开或旧API返回200。
3. 使用既有能力可证明安全的附件剩余步骤fixture，确认摘要展示已完成主文件/待续附件，实际执行
   不重放主文件。若现有能力确实不支持该输入，交B核对具体边界，不能以拒绝所有附件案例替代接入。
4. 扩展现有paused-authority浏览器用例（当前在“可见确认按钮”即结束）：实际确认、必要未知响应
   精确对账、刷新/重连/重开后恢复同一剩余摘要/执行，运行Worker并核对已完成范围未重放。
   原pin A在Active B下仍用A，原pin缺失拒绝；引用已有实际证明时给出具体测试/日志位置。
5. 每条标注最终候选、用例名、原始日志/实际截图及覆盖AC。更新Completion Report/索引中
   “covered by full suites”等泛化映射，使其只声明确已执行的分支；保留本轮完整日志和首次失败。
   不改变原Goal/Scope/AC/Required Tests，先修已知产品失败再跑最终候选全部门禁。

#### Slice 复核与下一步

RO-1/S-1、RO-2/S-2保留Task45.1/45.2既有B PASS；RO-3/S-3/S-4、RO-4/S-5异常连续性及
RO-6/S-6完整验证仍incomplete；RO-5/S-7独立Scan退役仍是后续范围，不混入本次修正。
**Decision: FIX REQUIRED；Developer继续同一Task45.3。** 不创建Task45.4，不交Closure Packet，
不改变Contract/Roadmap，不代A作最终审查。修好后再次审查全部Required Outcomes。

---

### B 独立验证 — Review 3 / 2026-10-18

- 治理 PASS；已提交 Slice45 ACTIVE、工作树 Contract、Task Base 和 Roadmap 对齐。必读文档沿用
  本会话已读版本并检查其未变；重读 Slice/当前 Task/B 经验，检查完整 Base..Head manifest 与
  本轮 correction diff。`d09245e..15cee31` 只有 TASK.md；`7c94028..d09245e` 仅测试补充，
  Docker 输入不变的复用理由本身成立，但仍须有原始运行/内容证据。
- 独立 `.venv/bin/python -m unittest tests.test_recovery_continuation tests.test_recovery_batch
  tests.test_task_persistence tests.test_processing_checkpoint tests.test_manual_organize_execution`：
  **169 tests / 18.510s / OK**；`web/ npm run build` PASS，保留大小 warning。
- 本轮已修好的两条原反例独立复验通过：
  - 候选选择 detail **4→4**、Metadata correction detail **2→2**；prepare-summary 返回201，
    临时来源保留。该结论针对这两条电影分支，不推定 TV 元数据往返完整。
  - production build + 真实 Python/SQLite/consumer harness，本页准备→confirm202后丢响应→
    显式对账：durable confirmed、关联执行入口存在、确认按钮数 **0**，只发一次确认 POST。
- 新批次反例：真实两项 manual failure→批量 Worker 分析→两个独立摘要→只选一项确认。
  后端提交202、浏览器丢响应；用 barrier 暂停批次 GET 的完成，页面显示
  **“未获受理（transport_unavailable）”** 并重新启用确认；再次点击实际发出第二次 POST。
  API独立读回为一项confirmed、一项prepared，两次POST返回同一execution，未证实重复媒体变更。
- TV独立真实调用链：临时电视剧源、合法B选择、假Provider含Episode 1、实际手动失败、Worker
  分析完成；原结果目标含 `Correct - S01E01 - Episode 1.mkv`，摘要201却变成
  `Correct - S01E01.mkv`。Provider calls **7→7**，来源保留。将同一合法Naming策略的
  missingVariableStrategy设为error后，分析仍成功且含标题，prepare-summary返回 **409 preview_blocked**。
- 真实Task Base迁移脚本独立PASS，确认新增授权行和ALTER故障注入已存在；但对其生成的临时库
  另调生产 `validate_runtime_snapshot`：Task pin `snap-base/digest-base` 无法读取，唯一revision
  是 `base-revision/d…d`，抛 `RuntimeSnapshotUnavailable`。不能把表行保留扩大为合法旧pin可用。
- 已检查Developer索引和实际日志：full Python原始结果 **2501 / 7 skipped / 1 failed / 198.250s**；
  traceback路径仍指向主工作区，报告的schema48环境说明不等于干净候选全量PASS。
  当前索引目录中的Web unit仅4行摘要，无完整real-Python/Unicode/fake E2E原始日志，
  wheel日志亦不足以核对报告中的91f3…；先前候选不能自动替代这次改动的T4证据。
  不把这些差异单独宣称为产品回归，具体最终补证见R5。
- 证据、可重跑probe、原始日志/trace、实际桌面/窄屏截图、source/lockfile/build摘要：
  `.git/validation-evidence/15cee31bdb98eccb2ba3ef5ea3d74524234361f9/b-review3-20261018/INDEX.md`。
  已查看批次1536×1024/380×720截图。本轮不是完整五类/键盘/暂停/容器验收。
  已有确定阻塞，按workflow提前拒绝，不重复全量Python/Web/完整spec/wheel/Docker，未跑不记PASS。

### 修正核对

| 原条目 | 当前事实 |
|---|---|
| R1 精确绑定/事务内checkpoint | 保留；独立相关回归通过，未复现原问题 |
| R2 单项及暂停对账 | 单项本地prepared遮盖confirmed已独立证明修好；暂停增加exact outcome读取，但本轮未作完整原生验收 |
| R3 批次/五类恢复 | 已增加真实两就绪项和汇总子集准入；新增批次确认未继承unknown保护，见下；五类/新阻塞/附件完整门禁仍须满足 |
| R4 摘要重复Provider | 两条电影决定分支计数已修好；durable身份缺少TV必要字段，不能保证同一Naming/Classification语义 |
| R5 迁移/最终证据 | 增加授权表行及实际ALTER失败注入；pin样本仍失配，最终T4原始证据不齐 |

### 同 Task 修正指导

ID/Base/Goal/Scope/AC/High/T4和原Required Tests保持不变。保留已修好的行为，先修以下确定
反例，再固定最终候选完成原门禁；不拆新Task，不把删除断言、改文案或拒绝有效输入当作修复。

#### R2/R3 / P1 — 新增批次确认把未知结果当作拒绝，未对账就解锁（AC-4/5）

定位：`RunDetailTabs.tsx:1585–1640` 的 `BatchRecoverySummary.confirmSelected`。
所有非ok响应都进入“未获受理”，没有逐项提交身份/unknown锁或精确读回；finally立即解除busy。
等待中的refetch不能代替已完成的精确对账。本轮controlled barrier与真实API读回证明该窗口。

Developer按顺序做：

1. 先加入本轮真实反例：两项已就绪，只选一项；确认事务提交后丢响应，以event/barrier延后
   批次读取。断言显示“结果未知”，该项没有可用再次确认，并保留另一项可诊断状态。
   不用sleep碰运气，不把后端返回404/409冒充网络未知。
2. 抽取或复用已有单项exact reconciliation行为，记录每个已发出确认的preparationId、确切
   selected itemIds/影响许可及已核实主体。每项独立表示未提交/未知/已受理/明确拒绝；
   未知不是未受理，也不是成功。不得自动重发POST或按最近执行猜测。
3. 对未知项读取该次preparation及执行绑定；已受理显示已有执行并移除该项确认；确实未受理
   才恢复同一合法摘要的显式确认；读到另一摘要、过期或读取失败保持该项锁定并给出下一步。
   旧GET的prepared不能盖过已经知道的confirmed，local与durable协调须保持同一身份。
4. 刷新、同主体重连、换主体、重启、两项一项已受理一项拒绝/未知都保留各自结果，不让
   一个unknown覆盖兄弟项或触发新批次。批次确认完成前后的自动导航不得丢失未完成对账。
5. 补组件和真实Python浏览器回归：未知提交、延迟/失败读回、精确确认去重、部分成功、未选项
   后续继续；保持原子准入/一次性权限/OrganizerExecutor及已修好的单项路径。

#### R4 / P1 — durable身份重建丢失单集标题，使有效TV恢复变更目标或无法生成摘要（AC-2/3/7）

定位：`evidence_capture.py:_metadata_section`、
`manual_recovery_continuation.py:874–944`。当前保存/重建season/episode/episodes，却没有
`episode_title`/`episode_metadata`；分类所需其它身份信息也不能仅因展示投影省略而改变。
原Worker分析已成功，摘要无Provider复用时仍必须保持同一命名/分类语义。

1. 用临时源 `Correct.S01E01.2024.mkv`、合法B选择、假Provider返回Episode 1，先通过完整
   原手动失败→Worker重新分析，再准备摘要。分别覆盖omit_token和error策略；
   断言原分析与摘要目标都包含Episode 1、后者可确认，且Provider计数不增加。
   保留源/许可/执行计数，不以去掉模板变量或更换Naming策略规避。
2. 明确复用的是完整可重建的分析身份/已完成计划。保存并严格还原实际参与Naming、
   Classification和逐集计划的字段；不能把有界脱敏的展示摘要当成无损的执行输入，
   也不能只补一个标题常量。复用现有耐久模型，必要时最小增量演进并验证旧记录兼容。
3. 核对episode_title、episode_metadata与keywords等实际下游消费者。单集/多集及Movie/TV
   在保存→重开→摘要中的目标/附件/解释一致；非法或过期决定仍拒绝，Type C身份仍保持C。
4. 旧记录确实没有必要字段时，返回明确可执行的重新分析动作，由现有Worker产生完整证据；
   不能同步Provider fallback，也不能无限重复分析却仍写出同样不完整证据。
5. 回归已有候选选择、query/direct ID correction、metadata reference以及默认自动匹配，
   保持本轮已经证明的零新增Provider调用；补TV原生摘要和后续实际Worker结果。

#### R5 / 阻塞验证缺口 — 旧pin样本不可用，最终T4仍缺可复用原始证据（AC-7）

定位：`task_base_migration_proof.py:109–125,385–430`。
保存的唯一revision为base-revision/d…d，Task/intent/Preview却pin到snap-base/digest-base；
revision.document还是无法构建真实runtime的占位文档。新preparation亦引用base-task/base-item等
未对应实际seed对象的字符串。ALTER失败注入已有效增加，不要求推倒重写它。

1. 用实际Task Base服务和安全临时示例配置发布一个可加载的旧revision，取得真实ID/digest；
   Task、intent、Preview、许可和恢复关联统一引用它及真实seed对象。
   升级前后均通过生产validate_runtime_snapshot并重开读回，不能只比较ID字符串是否未变。
2. 使用真实许可创建/消费及关联执行状态，保留已消费/撤销不复活、原Result/成功/未知效果不变；
   新边界引用真实原项/分析/Preview。保留现有中途ALTER故障和安全重开，核对整个相关权威一致。
3. 修好产品反例后，按原Required Tests固定最终source SHA，在真正干净的隔离checkout完成
   T4全量。确保子进程/import/config/database根都属于临时测试环境；不读取用户schema48库。
   环境失败保留原始结果/Base反证，但它不能代替原计划要求的干净候选全量证据。
4. 索引附精确cwd/命令/版本/依赖/fixture/源码与产物摘要、exit/counts/skips/duration及原始logs，
   不只存grep出的“passed”行。补完整Web fake E2E、real-Python五类恢复/新阻塞/安全附件、
   暂停重新授权/unknown/重连及Unicode等原门禁，不能按共享入口或28个测试推定全部覆盖。
5. wheel的实际构建/安装/consumer与候选digest一致；Docker可复用内容相同的7c94028镜像，
   提供完整image ID、内容匹配和原始运行/浏览器证据。缺失文件明确标注待补，不仅重复报告PASS。

### Slice 核对与范围决定

- RO-1/S-1、RO-2/S-2保留Task45.1/45.2既有B PASS，不扩大到本Task尚未完成的恢复链。
- RO-3/S-3/S-4、RO-4/S-5异常连续性、RO-6/S-6完整验证仍incomplete。
- RO-5/S-7独立Scan完整退役尚未完成，保持本Task非目标。
- **不创建Task45.4，不提交Closure Packet，不宣称Slice关闭。** 当前Contract仍可满足；
  Task45.3继续合法，不需A改范围，同Task完成上述修正后重新交审。
- 经验候选：同一种确认保护必须覆盖新接入的批次入口；耐久复用必须验证下游真实语义，
  展示字段的子集不能自动视为完整业务身份。Slice收尾再合并，不另增经验流水账。
