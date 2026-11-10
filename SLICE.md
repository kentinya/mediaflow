# Slice 53 — 手动／批量整理逐文件弹窗与任务中心交接

```text
Slice ID: 53
Name: Manual Organize Dialog and Task Center Handoff
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 95c24cd0a3cc51acd6143e37e72371445cb15a72
Implementation Head: 8c1b2b1e262d483b594e99a06ad67e747b13bfa4
Reviewed Head: 8482d77d3d7db5b89edbaca4022c1bf6f154ca5e
Working Branch: main
Development Authorization: IMPLEMENTATION COMPLETE — NO ACTIVE IMPLEMENTATION
Final Review Authorization: USER AUTHORIZED THE B REVIEWER TO PERFORM A FINAL REVIEW ON 2026-11-10
Risk: High
Accepted Test Level: T4
Next Action: A SELECTS THE NEXT LARGE SLICE
```

## Authority and accepted baseline

用户于 2026-11-09 激活本 Slice：Files 单项／批量／有界文件夹复用居中弹窗，每页一个
主文件及附件，逐项修正后一次确认就绪子集，受理后在任务中心查看原任务；任务详情 UI 冻结。
Base 固定为 `95c24cd0a3cc51acd6143e37e72371445cb15a72`；后续规划、修正和文档提交均不重设。
Slice52 的 [固定关闭记录](https://github.com/kentinya/mediaflow/blob/19a458eb6c1a6afb8693d2757755487a58213a4f/SLICE.md)
及此前 [独立修正验收](https://github.com/kentinya/mediaflow/blob/379c3746de2c4cd31ed8a1f558f42c3d2175c2dd/TASK.md#b-final-review--pass)
保留原接受身份、范围与延期。

原 A53-01 退回在同一 Task53.1 修正并由 B 复核。用户随后明确“给你A的权限审查”，授权
同一执行者由 B 转任最终 A；该角色例外、原退回和最终证据见下方审查记录及
[固定关闭检查点](https://github.com/kentinya/mediaflow/blob/8bc3ef905a76b96ef8ec327154b92e9b9972ea05/SLICE.md#closure-packet-and-a-final-review)。
完整计划／开发指导在 [固定 Task](https://github.com/kentinya/mediaflow/blob/8482d77d3d7db5b89edbaca4022c1bf6f154ca5e/TASK.md)；详细过程在 Git，
生命周期以 [Development Workflow](docs/development-workflow.md) 为唯一依据。
原预存脏文件保持；验证使用隔离临时库和本地假服务，原环境限制保留。

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

本合同已接受为 **CURRENT**；见 [V2 要求](docs/v2-requirements.md#current--manual-organize-dialog-slice53-pass--closed)、
[完整旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed) 和
[架构](docs/architecture.md#current--manual-organize-dialog-slice53-pass--closed)。
早期耐久准入、来源占用、五态／独立结果和准确确认语义保持；本次交付替换 Files 准备／
复核的旧整页呈现及确认后的默认执行页交接。

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
全面退出、自动忽略／重试／取消／覆盖／清理／回滚、生产服务验证、发布／部署。
用户本次单独授权 GitHub 推送，不代表授权生产部署。

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

### Prior A review — A53-01 / FIX REQUIRED（历史）

独立 A 于 2026-11-10 对原 Base → `8a468b7685d5750bcd7607fc291a61ae70b7000c`
作出 FIX REQUIRED：真实 Files 只确认一个文件、丢失响应、Worker 已完成移动后，用户
修改未选兄弟并重分析；核对错误读取新摘要，否认了原受理及真实效果。
引入提交 `99328d5d22e3110eb2f97415af436c76e5545a3a`；未证明重复执行或数据丢失。
原完整结论保留在 [固定退回记录](https://github.com/kentinya/mediaflow/blob/fded2cff4e3f9c131dce3416c916117bd72babd1/SLICE.md#a-final-review--fix-required)；原本机证据
`.git/validation-evidence/9d845aed/a53-review/` 保留。该次失败未追改为通过。

### B Closure Packet — Task53.1 PASS

- **范围：** 固定 Base `95c24cd0a3cc51acd6143e37e72371445cb15a72` →
  Implementation Head `8c1b2b1e262d483b594e99a06ad67e747b13bfa4`；B 完整 reviewed Head
  `8482d77d3d7db5b89edbaca4022c1bf6f154ca5e`，39 文件。测试候选为
  `415a2d4356666310880e8227a4600fc00350fac4`；之后仅修正 Task 的验收章节标题，
  产品／测试／夹具／配置／依赖未变。
- **全部结果／表面完成：** RO-1 Files 单项／批量／有界文件夹的逐文件弹窗；RO-2 四类
  合法决定、逐项草稿与一次精确子集确认；RO-3 正常及未知原请求核对后的准确 Task 交接。
  Files／准备／意图／摘要／原请求核对／深链与公共呈现均覆盖，任务详情 UI 保持原样。
  原 AC-1–12 与 FIX-AC-1–6 满足；Task53.1 PASS，停止新增 Task。
- **B 实际验收：** Python 全量 2678 tests，7 skipped，唯一失败为 Task 章节标题消费者；
  `8482d77d` 修正该标题后，release-security／governance 28 tests 通过。未声称重跑第二次
  Python 全量。Web 99 files／1495 passed；Node E2E 268 passed；真实 Python dialog 8、
  inventory／source-history 46、automation-settings 15、task-center-visual 2、
  本地 OpenList metadata 1、Unicode principal 1 均通过。
- **其余证据：** typecheck、ESLint、Prettier、build、compileall、pip check、两份示例配置、
  禁用依赖扫描和 whitespace 检查通过。根目录 Ruff 仍被预存未跟踪
  `.explore_adapter_block.py:8` 语法错误阻断；tracked Python lint／format 355 files 通过。
  3 项专用外部服务与 4 项 endurance 环境未配置，7 skips 和原 warnings 保留。
- **打包：** 工作区首次 wheel 混入旧 build 输出，保留原日志；从精确候选的 Git 源码隔离
  构建，170 个 Python 文件与现源码一致；源码外安装消费者、准备／恢复及备份／恢复 smoke
  通过。接受的 wheel SHA-256 为
  `f988f8cf61e8394b8a270f65278fcbbff1911eae702caeb3554dcff6968b9518`。
  Docker／依赖／容器权限及执行路径无变化，广域 Docker 发布矩阵不适用。
- **本机证据：** `.git/validation-evidence/415a2d43/b53-review/` 的 `review.md`、命令 JSON／
  原日志、原请求及文件效果证明、三种视口截图和精确 fresh wheel；材料仅本机可达。
  原桌面／390px／矮窗口、长路径、多附件与键盘证据经呈现源码比对后复用。

### A Final Review — PASS / CLOSED

日期：2026-11-10。用户明确授权前轮 B 执行者代行本次 A 终审；角色例外已披露。

审查固定 Base `95c24cd0a3cc51acd6143e37e72371445cb15a72` → Implementation Head
`8c1b2b1e262d483b594e99a06ad67e747b13bfa4` 的完整产品／测试／文档改动，并核对至
`8482d77d3d7db5b89edbaca4022c1bf6f154ca5e` 的报告／文档增量。逐项复核结果、入口、
保存／分析、精确确认、交接、失败／恢复及任务中心冻结边界；未发现剩余 P0／P1 阻塞。

A53-01 已解除：确认时捕获完整原 previewId／复制的 itemIds／intentVersion／两项效果授权，
Execute、未知状态与每次核对共用该身份。当前复核摘要和未选兄弟的新决定独立推进。
真实旅程再次证明：选两项只确认一项、响应丢失、原 Worker 已移动文件后，修改兄弟并
生成新摘要，再核对仍读取原提交、打开 Worker 返回的原 Task；一次 Execute，兄弟保持
未执行。10 项候选各保存分析后一次确认、真实冲突／无候选纠正、取消后退及刷新重认证
同样可用。受理与文件结果保持独立，原任务详情布局／进度／结果／恢复 UI 未改造。

**A 本轮验证：** production build 通过，真实 Python／SQLite／Local Storage／Worker
浏览器旅程 **8 passed（49.9s）**。核对 B 原始全量／原生／安装日志及文档修正差异；
重新核验接受 wheel 的摘要及全部 170 个 Python 源文件。查看桌面、390px、矮窗口的
逐项候选／附件／未知核对／原任务交接证据；匹配的旧视觉输入沿用。原始失败、7 skips、
Ruff 工作区限制与打包初次污染均如实保留。A 未机械重复 B 全量。
本轮本机证据 `.git/validation-evidence/8482d77d/a53-review/`，包含 build／dialog 日志、
wheel 核验、审查与最终文档检查；材料仅本机可达。
关闭检查点 `8bc3ef90` 提交后，治理检查 PASS，文档消费者 28 tests 通过（6.409s）。

**决定：PASS / CLOSED。** RO-1／RO-2／RO-3 和全部必需表面已完成；CURRENT 要求、
旅程、架构及操作指导随本关闭提交协调，Roadmap／Progress 记录本接受，Task 置为
NO ACTIVE IMPLEMENTATION TASK。原 Base、已审 Implementation Head、旧失败与全部延期
保持。下一步由 A 另行选择大版本 Slice；GitHub 同步依据用户单独授权执行，发布／部署保持延期。
