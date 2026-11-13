# Task PATCH-20261113-1 — 任务详情与记录表达去重

Authority: 用户于 2026-11-13 授权独立界面修复规划，随后明确“激活Task”，授权按本计划实施；生命周期遵循
[Development Workflow](docs/development-workflow.md)。本任务不属于 Slice54，也不重新打开
已接受 Slice。B／Developer 分别阅读对应[角色经验](AGENTS.md#testing-and-roles)。

```text
Task ID: PATCH-20261113-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 31f4b56936831699f75590f5afd49d58d630ba9c
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-13 — 激活Task
```

规划前 `python3 scripts/check_governance.py` PASS。工作区 `/Users/songzhidong/mediaflow`，
分支 `main`，HEAD 为上述 Task Base；暂存区／工作区干净，工作区和 Git 可写。
只读调查覆盖源码、测试及 CURRENT 契约，未运行浏览器验收、未读取用户运行数据库、
私有配置或媒体。此次规划只改 `TASK.md`，不改产品／Slice／Roadmap／Progress。

激活前治理检查 PASS；分支 `main`，HEAD `866f6670be54f6fa137f483e83b3f53dd57b434b`，
暂存区／工作区干净。Task Base..该 HEAD 仅含本任务规划文档，无产品输入变化；保留原
Task ID／Base／Goal／Scope、Medium／T3 及测试分工。现为活动 `PLANNED` Task，
Developer 可按计划开始实施并转为 `IN PROGRESS`；本次激活仅更新任务文档，尚未实施。
此前独立修复的 B PASS 指针保留在本文末尾；Slice54／Roadmap／Progress 保持原接受身份。

## Goal

用户从任务中心打开准确任务弹卡，在“任务详情”查看文件证据，或切到“操作记录”
查找历史，能直接读懂当前结果、处理依据和实际下一步，不在多个区域反复阅读同一结论。
本任务中的“执行记录”指文件证据内的逐次执行历史；“操作记录”指弹卡现有页签。
不涉及自动化工作区的“执行记录”列表，也不删除后台执行对象或恢复已退役的独立执行页。

依据 CURRENT `V2-UX-005/006`、`V2-OPS-003–005/007/008/012/016`、
`V2-TASK-012–014`，保留[任务正文与文件证据](docs/task-center-page-spec.md#current--任务正文与文件证据)、
[任务与逐项恢复完整旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)及
[流程／文件结果分离](docs/product-experience.md#current--task-flow-status-and-automation-success-rate-slice48-pass--closed)。

现有缺口来自多个呈现区域分别展开同一记录：

- `RunDetailTabs.tsx` 的处理结果同时输出结论、状态／效果／尝试及 Result 列表；处理经过
  又遍历同一 Result 输出时间／完成步骤／清理结果，用户必须跨两份列表拼出一次执行。
- `TaskItemRecoveryPanel.tsx` 在无待处理操作时再次输出成功／失败／取消等结论；文件证据
  与恢复区各有技术诊断，阶段、效果、重试安全性及“服务下一步”重复或来源不清。
- 当前原因、Result 历史原因与恢复说明缺少层级；记录页重复页签标题，筛选／分页常驻
  API／服务器实现说明，条目未筛选时仍同时显示相等的匹配数和总数。

完整旅程：打开弹卡 → 概览区分流程与文件结果 → 展开准确文件 → 阅读当前结论、来源／
目标和处理依据 → 按需查看逐次历史／诊断，或完成现有合法恢复 → 刷新读回真实结果。
读取失败、历史缺失、未知效果、未知提交各自说明真实状态和既有下一步；筛选、分页、
切换／关闭、刷新及重新认证仍回到原合法上下文，不自动重提工作。

## Implementation Scope

1. **整理文件证据正文。** 当前结果保留一句清楚结论，异常的阶段、已知效果和必要下一步
   就近展示；删除紧邻的同义状态复述，将原始状态与非必要计数放入历史／诊断。
   来源／实际目标、识别／作品匹配、命名／分类依据继续直接可读。列表摘要与展开详情承担
   不同层级，不为消除重复而删除源文件表格的必要状态／目标；计划目标不冒充实际目标。
2. **合并同一次执行。** 将当前分散在“处理结果”和“处理经过”的 Result 内容组织成一份
   执行历史，每条包含原记录的时间、结果、操作、完成步骤、清理、附件和异常／未确认效果。
   同一 Result 只出现一份历史条目。多次尝试逐条保留，不按文案相同去重，不用数组下标推导
   真实尝试次数或合成新结果。单次执行无需穿过多层折叠才能看见实际结果和异常；多次历史
   可分层，但当前风险／阻塞不得藏入历史。无 Result 时保留检查点的已知步骤与缺失说明。
3. **收敛恢复与诊断呈现。** 在文件证据宿主内，无实际待处理动作时去掉重复的“审核与恢复”
   标题／无操作结论，不显示空区。保留恢复查询的加载、失败、未知请求核对及所有合法操作，
   不能因隐藏外壳而跳过读取、丢失会话或改变请求生命周期。当前原因与下一步集中呈现；
   原尝试的失败原因仍归属对应历史。一个文件使用一个可展开诊断入口，原始计划、日志、
   审计及恢复检查点按来源组织；同源同值只呈现一次，不同来源／不同值明确区分，不以文本
   去重覆盖冲突证据。独立／嵌套恢复消费者仍能完整查看其状态、诊断和下一步；手动整理
   `mode="decision"` 的原交互保持。
4. **精简记录及列表辅助文字。** “操作记录”页签下不再重复可见同名标题，保留区域可访问
   名称；默认选项简为“全部类型／全部状态”，去掉常驻“服务器筛选／分页、浏览器不合并”
   及 API 读取教程。条目无筛选时显示“共 N 条”，有筛选时“匹配 N／共 M 条”；记录页保留
   后端提供的匹配数及适用类型计数，不把跨类型计数错误相加成总量。保留有界翻页、截断／
   不完整事实、必要空态／错误与重新读取动作，未知总量不编造成零。
5. **保持既有交接并验证。** 主要修改 `RunDetailTabs.tsx`、`TaskItemRecoveryPanel.tsx` 及
   直接配套测试／样式；仅为上述宿主展示作必要的组件组合调整，不改领域模型、API、查询
   身份、后端恢复判定或命令协议。若需调整 `AttachmentResults`，验证全部直接消费者，
   不降低附件警告。交付时仅按最终事实协调 `docs/task-center-page-spec.md` 及直接对应的
   CURRENT 呈现文字；不重写已接受结果或扩展产品义务。

## Acceptance Criteria

- [ ] 打开任务详情，流程状态 → 处理进度 → 文件结果仍清楚；文件成功不能覆盖流程失败，
  completed 不代表文件成功。零／未知总量、未记录结果和未确认效果保持可辨。
- [ ] 单次成功文件只需读取一个当前结论及一份执行记录；没有重复的无操作恢复区。
  已取消／跳过／忽略／技术失败也没有空操作或通用重试指导，独有原因与诊断仍可查。
- [ ] 两次及以上尝试能逐条对照时间、结果、操作、完成步骤、附件和异常；相同状态的历史
  不被删除。当前结论、历史事实、计划与实际目标有明确分界，缺失证据不由当前配置补算。
- [ ] 主文件成功但附件失败／冲突／未执行仍明确；未知效果、失败且无 Result、仅有检查点
  步骤均展示真实事实，不提供成功／未知效果重放入口。
- [ ] 当前问题及下一步集中易找，四类决定 → 分析 → 精确摘要 → 明确确认仍完整；读取或
  提交未知先核对原请求，401／403、失效／变更拒绝保留原因与输入，不绕开后台权限。
- [ ] 文件诊断入口统一且内容完整；同一字段不同来源／值可分辨。读取失败不会被误报成
  “无待办”，嵌套恢复和整理弹窗不因呈现收敛丢失状态／诊断／操作。
- [ ] 操作记录没有重复可见标题或常驻服务器教程；筛选、前后页、计数、查看条目、JSON
  导出仍准确。同一次 Result 在文件历史和任务级记录流中各自承担不同用途，不删除记录流。
- [ ] 文件证据唯一、仍紧跟对应条目；筛选隐藏／跨页／加载／失败时独立位置与说明保持，
  迁回不丢同文件输入。任务／账号切换不串证据，关闭回焦、深链及认证续转保持。
- [ ] 桌面 1536×1024、390×844 和矮窗口中，成功、多次执行、附件警告、未知效果、四类
  处理及记录页可读可操作；检查完整弹卡及展开过程，不只数 heading 或局部截图。
- [ ] 打开、切换、展开／关闭、筛选、分页、刷新不发出新的执行／恢复写请求；已有显式
  动作的请求次数、原 Task／文件身份、已完成及未知效果非重放保持。

## Required Tests

测试分工遵循[工作流 §6](docs/development-workflow.md#6-test-levels)。T3 依据是记录、诊断和
共享恢复组件的呈现整合；命令／权限／持久化／调度行为冻结。若实施需要改变这些边界，
先交 B 重评范围和 Test Level，不以本 Task 授权该变更。不要求 Developer 跑全仓全量。

### Developer — affected tests

在 `web/` 执行：

```sh
npm run test -- run src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/AttachmentResults.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
```

新改测试验证完整可见结果：单／多次执行、成功／失败／附件警告、无 Result／未知效果、
诊断来源差异、加载／拒绝／读失败、未筛选／筛选／分页、证据迁移及恢复／未知提交保护。
更新仅固定旧重复文案／层级的断言，同时保留对应事实、权限、非重放与可达性断言；
不通过删断言、加重试或改超时掩盖失败。共享样式／组件若影响其他直接消费者，补跑对应
受影响测试。根目录执行 `python3 scripts/check_governance.py` 和 `git diff --check`。

### B — acceptance and regression

B 独立审查 Task Base..candidate，核实上述受影响结果并运行候选的真实 Python/API／
临时 SQLite 与 Local 根旅程。在 `web/` 使用新 `npm run build` 资产，以下每条独立启动
一套 harness，避免三个 spec 的共享数据污染：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
```

B 对缺少的多次执行／记录去重／诊断差异场景补充最小有意义的浏览器覆盖，复用现有隔离
假服务／临时 harness，不访问生产环境。实际检查上述三个视口及正常、展开、等待／错误
中间状态，保存同视口改前／改后完整弹卡截图；核对四类处理、未知提交原请求核对、
证据迁移／回焦／认证续转、日志／审计／JSON 信息完整，读取动作没有隐式写请求。
源码／自动化不能代替实际视觉验收。记录原始失败、结果和未运行限制，证据留于
`.git/validation-evidence/<candidate>/patch-20261113-1-b/`。

该 T3 不改 Python／schema／依赖／容器／安装路径，不机械运行 Python／Web 全量及
wheel／Docker 矩阵；发现具体共享影响时由 B 补充必要门禁或重新定级。Developer 不承担
B 原生／全量验收。只有实际完成验收后才可 PASS，按工作流恢复无活动 Task，不关闭 Slice。

## Non-goals

- 不改任务中心八视图、页面级筛选／统计、自动化执行记录列表或其他页面整体布局。
- 不删除后台 Result／执行历史／日志／审计／导出，不恢复独立“整理执行情况”页面。
- 不改五态 Task、四类待处理归属、执行／恢复许可、取消、固定快照、请求核对、调度、
  版本／围栏、Storage、附件恢复、成功／未知效果非重放；不添加通用技术失败重试。
- 不重构整套组件／数据层，不读写生产配置或媒体，不修改 SLICE／Roadmap／Progress，
  不启动其他代理，不推送／发布／部署。

## Developer Completion Report

已获实施授权，尚未开始实施。后续按模板记录实际 checkpoint、READY FOR B REVIEW、
变化／受影响测试结果与风险；B 验收保持独立。

## B Review Result

尚未产生实现候选或验收结论；Task 已激活，不构成产品 PASS。

---

## PATCH-20261112-2 — B PASS

Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Difficulty / Test Level: Medium / T3
Reviewer: B
Decision: PASS — 2026-11-13

完整审查范围：`dc2eec67d619bc2e06de5eca0900325a7906fbfd..114078829ed4f3820818cc219007c4b07af1ebdf`。
产品修正检查点：`1b7e23e72f45f4f8c02372cc120991009808f07a`；其后候选只更新 Task 报告。
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/f3bca4cf72a8cdaa15f5646f13d72f45ad954678/TASK.md#patch-20261112-2--b-pass)
保留实际结果、首次失败及限制；原计划、开发指导与返工见
[已审 Task](https://github.com/kentinya/mediaflow/blob/114078829ed4f3820818cc219007c4b07af1ebdf/TASK.md)。

独立“整理执行情况”页面、旧 Web 路由及专属入口已删除。用户继续在原任务详情／逐文件
证据查看结果；同任务恢复确认后刷新原详情，历史／意图／运行一次的相关入口进入准确
关联 Task。后台执行记录、历史和受理核对保留，旧地址使用普通未找到／认证边界。

实际验收：219 项受影响单元、50 项 Node 浏览器、61 项真实 Python 浏览器测试通过；
typecheck、lint、format、build、治理与 diff 检查通过，桌面／390px 结果可读。
首次三 spec 联跑因共享数据出现 3 项失败（24 通过、1 中断、33 未跑）；各 spec 使用
全新实例后全部通过。未改断言、重试或超时，原失败仍保留在固定验收记录中。
本机原始证据：`.git/validation-evidence/11407882/patch-2-b/`，不随 Git 推送。
完整验证范围统一见 [Release](docs/release.md#current-v2-validation-boundary)。

独立修复已完成，不规划下一 Task；生命周期遵循
[Development Workflow](docs/development-workflow.md)。Slice54 保持原 PASS / CLOSED，
下一大 Slice 由 A 另选。本轮文档治理不改变产品、Slice／Roadmap／Progress 或接受身份。
