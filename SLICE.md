# Slice 53 — 手动／批量整理逐文件弹窗与任务中心交接

```text
Slice ID: 53
Name: Manual Organize Dialog and Task Center Handoff
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 95c24cd0a3cc51acd6143e37e72371445cb15a72
Implementation Head: NOT SET
Working Branch: main
Development Authorization: USER-AUTHORIZED TASK ACTIVATION; NO IMPLEMENTATION STARTED IN THIS TURN
Risk: High
Accepted Test Level: T4
Next Action: B FORMALIZES TASK53.1 WITHIN THIS COMMITTED CONTRACT
```

## Authority and accepted baseline

用户先要求只调查，随后要求规划 Task，并逐项明确：每页一个文件、候选确认流程、
统一确认整理后在任务中心看结果、本 Task 不更改任务中心任务详情弹窗。
2026-11-09 用户明确“把这些在Task明确后激活Task”。本轮按该授权依次完成 A 的新
Slice 范围 checkpoint 和 B 的正式 Task 规划／激活，不启动 Developer 实现，不推送／部署。
同一规划执行者完成范围设置及 Task 正式化，只是规划，不构成 B 独立验收或 A 终审；
后续验收必须保持与实现独立，B 不代行同一 Slice 的 A Final Review。

这是已接受整理旅程的呈现／交接重设计，不能借独立 minor bug 扩大已关闭 Slice。
Base 固定为调查／规划前 `95c24cd0a3cc51acd6143e37e72371445cb15a72`，后续规划提交不重设。
Slice52 的原 Base／已审 Head／PASS 保留于
[固定关闭记录](https://github.com/kentinya/mediaflow/blob/19a458eb6c1a6afb8693d2757755487a58213a4f/SLICE.md)，
此前独立修正保留于
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/379c3746de2c4cd31ed8a1f558f42c3d2175c2dd/TASK.md#b-final-review--pass)。
所有旧接受、延期和证据限制保持，不重开、不追改。生命周期以
[Development Workflow](docs/development-workflow.md) 为唯一依据。

规划前治理检查 PASS；main／HEAD 如上述 Base，暂存区为空，仓库与 Git 可写。
预存 `TASK.md` 是本次上一轮草案；`mediaflow/.DS_Store` 以及未跟踪系统元数据、
调查脚本／日志、`15`、`output/` 材料均保留，不纳入本 Slice checkpoint。
调查使用代码及隔离假服务；未读取用户运行数据库、私有配置、凭据或生产媒体。
假计划的文件数不等于所选数量，不能当成生产数量缺陷；自动化表单仅核对现有卡片实现／
外壳，不把假服务加载状态当成生产验收。调查不替代后续真实 Python 旅程验收。

## User goal and requirement mapping

从资源库 Files 的单项／批量／有界文件夹整理进入协调、清晰、可读的居中弹窗，
逐文件复核与修正，最后一次确认准确就绪子集；执行受理后进入原任务中心对应任务详情。
默认信息以用户理解作品、来源、目标、操作、附件和下一步为主，技术诊断展开可查。
参考现有文件页新建媒体库／资源库和自动化新建任务卡片的样式与交互，不复制其业务命令。

| Required Outcome            | 验收旅程                                                                       | 需求                                                           |
| --------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| RO-1 逐文件整理弹窗         | Files 背景保留，立即打开准备状态，一页一个主文件及附件，清晰可读并可前后浏览   | `V2-OPS-018`、`V2-UX-005/006/011/013`                          |
| RO-2 当前文件修正与集中确认 | 候选／四类合法决定就近保存并重新分析，逐项状态独立，最后核对精确子集及危险影响 | `V2-OPS-018`、`V2-OPS-010/012/015–017`、`REQ-RECOVERY-004–009` |
| RO-3 精确任务中心交接       | 正常受理及未知响应核对成功均关闭弹窗并打开准确 Task，沿用既有详情／结果／恢复  | `V2-OPS-019`、`REQ-WEB-005`                                    |

新合同是 **TARGET，未交付**；见 [V2 TARGET](docs/v2-requirements.md#target--manual-organize-dialog-slice53-active)、
[完整 TARGET 旅程](docs/product-experience.md#target--manual-organize-dialog-slice53-active) 和
[架构 TARGET](docs/architecture.md#target--manual-organize-dialog-slice53-active)。
CURRENT 的早期耐久准入、来源占用、五态／独立结果和准确确认语义保持；TARGET 只替换
本次 Files 准备／复核的旧整页呈现及确认后默认执行页交接，不宣称已修改运行行为。

## Required outcomes and surfaces

**RO-1：** 单项、批量、文件夹／混选复用同一弹窗，点击后即显示实际准入／发现／稳定／
分析状态。一个页面是一个主文件及其关联附件；显示文件名、相对路径、`第 i / N 个`、
就绪状态及当前问题。同名异路径不串项。文件夹在冻结前显示真实发现／排除原因。
默认可读方案保留精确来源／目标路径；技术 ID、原始理由和检查证据置于展开诊断。
使用可用的真实可读库名称，不猜测历史 pin。桌面、390px、矮视口都可读可操作；
正文内部滚动，标题／关闭／底栏稳定可达，键盘、回焦、背景锁滚及 reduced-motion 可用。
Files 的库／目录／选择／滚动保持，不先跳页回顶再恢复。

**RO-2：** 按准确 itemId／准备／摘要身份保持逐文件草稿、候选、纳入选择及结果。
前后翻页只浏览，不保存、不分析、不执行；离开未保存项可返回继续。明确
“保存并重新分析”是一次用户动作，其内部依次保存合法决定、重新分析、显示新精确方案，
失败分别说明已保存什么与如何继续。更换文件不丢兄弟输入，不继承过期授权。

10 个文件均需确认候选时，用户从 `第 1 / 10 个` 开始，每项选择候选，点击
“保存并重新分析”，查看该文件新方案后切下一项；共 10 次候选选择、10 次保存／分析动作，
没有逐文件执行确认。全部就绪且纳入后，在紧凑整批复核区核对 10 项范围／目标／操作／
实际危险影响，只点击一次“确认整理 10 项”。允许核对并确认更小的就绪子集；
尚未就绪项解释阻塞，不悄悄忽略或持久标记忽略。覆盖／清理仍需原有明确授权。

**RO-3：** 最终确认提交中显示“正在提交…”，阻止重复提交；受理只代表执行已接入，
不显示“10 项整理成功”。后端证明受理成功后关闭整理弹窗，导航任务中心，并通过既有
选中 Task 的路由自动打开返回的准确 Task 详情。响应丢失时保留原请求核对，不自动重提；
核对证明受理后走同一交接。Task 关联暂时不可读时保留已知准确身份并允许重读，
不能改选最新任务、把详情读取失败当成提交失败或猜测成功。

任务中心现有“继续整理”／“查看只读摘要”链接仍打开准确准备；刷新、重认证及返回
保持原上下文。结束工作只读，合法未结束兄弟可继续；关闭弹窗不取消工作。
**任务中心任务详情弹窗的布局、内容、进度、结果及恢复 UI 全部冻结，不在本 Slice 改造。**
执行进度例子只解释既有能力。新交接只使用既有任务选择／详情打开机制；共享整理逻辑
如需拆出，保持任务中心消费者的呈现及操作行为不变。

必需表面：资源库 Files 整理入口、准备／意图／摘要／原请求核对的弹窗内容、精确路由
及深链、必要公共 modal／共享逻辑、直接受影响测试和交付时 CURRENT 文档协调。
已有历史执行地址继续合法读取；不全面退役整理后端、旧历史或任务中心产品。

## Safety invariants and explicit deferrals

- 准入仍在业务就绪前；不等到最终确认才创建 Task。分析／翻页／保存／关闭零媒体变更，
  只有 OrganizerExecutor 按确认的精确摘要／子集／效果边界执行。
- 保持后端 RBAC、immutable pins、来源占用、并发 fencing、Storage confinement、审计脱敏，
  已完成／不确定效果及未选兄弟不重放，来源／摘要变化需新复核与危险授权。
- 五态与文件效果独立；不得把流程 completed 当作文件成功。RecognitionType C 使用
  命名／分类 A 后仍是 C；保留自动化／普通文件的原有操作与结果归属。
- 不新增 Provider、Storage 操作、schema、任务引擎、权限或恢复模型，不允许任意身份／
  目标注入；不新增 FFmpeg／FFprobe。测试限临时库／本地假 Provider／Storage。

延期：任务中心详情／列表／四类恢复 UI 重设计、自动化／库配置改造、媒体库整理、
跨任务批量恢复、任意历史重处理、全站样式／路由／API 清理、新结果中心、历史执行产品
全面退出、自动忽略／重试／取消／覆盖／清理／回滚、生产服务验证、推送／发布／部署。

## Acceptance and final validation

B 将上述完整旅程作为一个连贯 Task 规划，不按 UI 字段或技术层碎分。必需验收：

1. Files 单项／批量／有界文件夹的完整弹窗旅程及原背景恢复，真实等待／失败可辨。
2. 10 个候选确认的逐项动作、新摘要、草稿保存、返回复核与唯一最终执行确认。
3. 可读／美观的同视口改前改后与真实操作证据：桌面、390px、矮视口、长路径、多附件。
4. 正常及未知受理核对后的准确 Task 交接；详情 UI 不改，执行／结果沿用已有机制。
5. 迟到响应、失效摘要、未知提交、混合兄弟、权限、刷新／重认证、只读历史及非重放。
6. modal／深链／路由的直接影响回归和上述安全约束。

T4 因精确执行确认、子集及未知提交交接而选择。Developer 运行新改及直接受影响测试；
B 独立审查固定 Base..candidate，承担真实 Python／SQLite／Worker 浏览器旅程、视觉／
操作验收及 [共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)。
打包／wheel smoke 与适用安全／重启证明归 B；若无容器执行路径影响，Docker 广域发布
矩阵非本 Slice 必需，仍需说明影响依据。所有实际失败／未运行／不可用保持披露。

## Closure Packet and A Final Review

尚无实现、B 验收或 A 终审。Implementation Head 保持 NOT SET；Slice ACTIVE 不表示交付。
完成全部结果后按工作流提供 B Closure Packet，再由独立 A 审查整个 Base..Head；
本轮没有 PASS／CLOSED 结论。
