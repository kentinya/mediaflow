# 文档导航与职责

[Slice54](https://github.com/kentinya/mediaflow/blob/05b51268f60f8cc932f6c71d9cfa1efac1227b3e/SLICE.md#a-final-review--pass--closed) — 整理规则统一弹窗与可读性 —
已于 2026-11-11 **PASS / CLOSED**；原 Base
`e43a40674eb14aa12615a440a348fe675cd50c4e` 至已审实现
`aef044e51dc91655372bf5fe39c6116da976c3b4`。七类 Add／Copy／Edit 居中卡片、设置／单项
测试可读性及仅概览完整流程检查为 CURRENT；[TASK.md](../TASK.md) 无活动实施 Task，
下一步由 A 另选大版本。首个 Task 规划的 A 代行 B 例外、独立 B／A 验收、原失败和
验证限制见固定 Contract 与 [B 终审](https://github.com/kentinya/mediaflow/blob/9220f34420bc4807d4c0bbbe98cf7dece5f100dd/TASK.md#b-final-task-review)。
Slice53 及更早接受身份、延期保持；开发关闭与发布事实分别记录。

现行文档说明当前规则、用户旅程和架构；验收事实在关闭账本与对应 Git checkpoint，详细
开发过程留在 Git。`docs/history/` 是 LEGACY / READ ONLY，不作为当前指令，也不继续追加归档。

最近的独立修正已由 B 验收 PASS。固定记录保留完整审查范围、实际验证、既有失败与证据限制；
不改写原 Slice 接受身份。发布验证范围统一见 [Release](release.md#current-v2-validation-boundary)。

| 已接受修正 | 当前结果与固定验收 |
|---|---|
| 元数据修正搜索年份 | [PATCH-20261111-1](https://github.com/kentinya/mediaflow/blob/d1631be651eefc5ed9c0b1bb80dcb195cf921cda/TASK.md)：文件页整理弹窗和任务元数据恢复均按当前标题／类型／年份搜索，清空年份不限制年份；修改条件清除旧候选，年份错误可纠正后直接重搜。T3 验收及原失败／限制见固定记录与 [发布验证边界](release.md#current-v2-validation-boundary) |
| 失败文件释放与摘要入口 | [PATCH-20261109-3](https://github.com/kentinya/mediaflow/blob/379c3746de2c4cd31ed8a1f558f42c3d2175c2dd/TASK.md#b-final-review--pass)：失败文件从 Files 重新发起；正常兄弟保留原摘要确认；已结束工作只读查看原计划，历史读取失败可页内重读。未新增表、迁移或状态枚举；T4 结果及两项 Base 同因测试失败见固定验收与 [发布验证边界](release.md#current-v2-validation-boundary) |
| TMDB 查询类型与候选续接 | [PATCH-20261109-2](https://github.com/kentinya/mediaflow/blob/da47f9dd1af56cc281d6e42323ae4892caed5f83/TASK.md#b-final-review--pass)：策略只保留查询类型；新整理重新识别；当前任务保存候选后继续摘要，意图页可明确选择已有候选；完整 T4 结果及补跑限制见固定验收，现行字段见 [配置说明](configuration.md#metadata-query-type-and-saved-identity) |
| 文件页与原整理摘要 | [PATCH-20261109-1](https://github.com/kentinya/mediaflow/blob/886c320db6916a1f0c3f5c2f2e38b599d14418a5/TASK.md)：文件页直接呈现目录读取／列表／错误；选择文件生成摘要后离开，可从任务中心原任务“继续整理”返回同一摘要，刷新／重认证后仍可继续，确认后查看原任务结果 |
| OpenList 属性与原生操作 | [PATCH-20261108-3](https://github.com/kentinya/mediaflow/blob/d65e938dba698d46fc934992a7b2cd3746ceea7b/TASK.md)：属性使用缓存目录列表，内容单独获取下载链接；原生移动／重命名及逐项核验，Python 3.11 启动修正 |
| 探索筛选与详情 | [PATCH-20261108-1](https://github.com/kentinya/mediaflow/blob/6220e369b4f8b7830a8a67ae9c8a6a3fd6e81134/TASK.md)：带标签筛选行、紧凑 TMDB 外链、集中鸣谢、详情背景原位；[PATCH-20261108-2](https://github.com/kentinya/mediaflow/blob/2ed492b10a87e2d4a7de7279bb35fa740ba85d43/TASK.md)：删除页面标题、统一内容边界、详情主要信息与简介开头首屏可读 |
| 可读性与导航 | [独立修正](https://github.com/kentinya/mediaflow/blob/db54158dbb5ee9df3b67c26f38999ba87ea6281a/TASK.md)：任务流程／进度／文件结果分层、处理经过可读、切页加载衔接、自动化页头刷新删除 |

| 需要了解 | 入口与职责 |
|---|---|
| 项目与本地使用 | [根 README](../README.md) |
| 永久安全、角色和范围 | [AGENTS.md](../AGENTS.md) |
| 生命周期、测试分工、Git、审查与关闭 | [Development Workflow](development-workflow.md)，唯一流程权威 |
| 当前 Slice / Task 与独立修复 | [SLICE.md](../SLICE.md) 保留大版本合同；[TASK.md](../TASK.md) 记录当前实施状态或最近 B 审查指针。大版本依据已提交 Contract，独立小版本 bug 依据用户授权范围及 B 的 Task；规划草案不授权实施 |
| 大版本优先级 / 关闭事实 | [Roadmap](roadmap.md) / [Progress](progress.md) |
| 完整产品定义与稳定需求 ID | [Requirements](requirements.md) 的 V1 基线与明确修订；[V2 Requirements](v2-requirements.md) 的现行 V2 定义 |
| 完整用户旅程 | [Product Experience](product-experience.md) |
| 组件、数据流与运行边界 | [Architecture](architecture.md) |
| 配置操作 / 自托管部署 | [Configuration](configuration.md) / [Deployment](deployment.md) |
| 发布与验证边界 | [Release](release.md) / [Storage Acceptance](storage-acceptance.md)；当前支持 fresh 新工作及同版本恢复，旧任务迁移/跨版本升级和 V1 不在支持范围；开发关闭和 Git 推送不等于发布 |
| 页面组成与交互 | [Files](file-page-visual-spec.md)、[MediaLibrary](media-library-page-visual-spec.md)、[Task Center](task-center-page-spec.md)；图片是视觉参考，不是运行数据或权限 |
| 整理规则弹窗与可读性（CURRENT） | [Slice54 Contract/A 终审](https://github.com/kentinya/mediaflow/blob/05b51268f60f8cc932f6c71d9cfa1efac1227b3e/SLICE.md#a-final-review--pass--closed) / [现行要求](v2-requirements.md#current--organizing-rules-dialogs-and-readability-slice54-pass--closed) / [完整旅程](product-experience.md#current--organizing-rules-dialogs-and-readability-slice54-pass--closed) / [架构](architecture.md#current--organizing-rules-dialogs-and-readability-slice54-pass--closed)；七类添加／复制／编辑统一弹窗，设置与单项测试分区；完整流程只在概览检查已发布 Active，准确发布、草稿配对及未知核对不重发保持 |
| 逐文件整理与任务交接（CURRENT） | [Slice53 Contract/A 终审](https://github.com/kentinya/mediaflow/blob/8bc3ef905a76b96ef8ec327154b92e9b9972ea05/SLICE.md#closure-packet-and-a-final-review) / [现行要求](v2-requirements.md#current--manual-organize-dialog-slice53-pass--closed) / [完整旅程](product-experience.md#current--manual-organize-dialog-slice53-pass--closed)；Files 单项／批量／有界文件夹在弹窗逐项复核、保存分析并一次确认；未知响应核对原请求后打开准确任务，原任务详情保持；角色例外与测试限制见 Contract |
| 七项体验修整（CURRENT） | [Slice52 Contract](https://github.com/kentinya/mediaflow/blob/19a458eb6c1a6afb8693d2757755487a58213a4f/SLICE.md) / [现行要求](v2-requirements.md#current--slice52-experience-refinement-slice52-pass--closed) / [现行旅程](product-experience.md#current--slice52-experience-refinement-slice52-pass--closed) / [现行架构](architecture.md#current--slice52-experience-refinement-slice52-pass--closed)；探索整页美观／详情滚动／浏览长度可控，全部九个主页面切换及读取接入没有突兀闪烁／非预期抖动（含两种库刷新提示），允许正常目标页布局差异与稳定加载反馈；自动化旧打开链路退出，普通分页与动效参数为实现方案，已独立验收；失败与证据限制见 Contract |
| 探索首页（CURRENT） | [Slice51 Contract](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md) / [稳定要求](v2-requirements.md#current--v2-explore-homepage-slice51-pass--closed) / [完整旅程](product-experience.md#current--v2-explore-homepage-slice51-pass--closed) / [架构](architecture.md#current--v2-explore-homepage-slice51-pass--closed)；TMDB 电影／剧集、筛选／搜索、详情和准确返回，Dashboard Web／API／CLI 及专属实现全退出，无兼容；已接受，证据限制见 Contract |
| 弹卡、可读性与主页面切换（CURRENT） | [Slice50 Contract](https://github.com/kentinya/mediaflow/blob/214b69b1e64b24fc22068c2e1760cd1b0c6ac787/SLICE.md) / [原八项与自动化弹卡稳定性补充](v2-requirements.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed) / [完整现行旅程](product-experience.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)；目录树/抽屉替换、V2 侧栏主页面切换与自动化新建/编辑抖动修复均已接受，保留既有业务与接受事实 |
| Task 流程、文件结果与自动化成功率 | [Slice48 已接受旅程](product-experience.md#current--task-flow-status-and-automation-success-rate-slice48-pass--closed)；Task 五态与文件结果独立，completed 不代表文件全部成功；定时/定义运行一次按 completed/(completed+failed) 统计，取消和未结束不入分母，手动整理/普通操作不参与 |
| 自动化创建、编辑与运行一次 | [Slice49 现行旅程](product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed) / [稳定要求](v2-requirements.md#automation-forms-and-direct-run-once--current-slice49-pass--closed)；列表直接运行或复制已保存定义，复制紧邻编辑并生成停用副本；创建/编辑共用中文卡片和紧凑启用开关，启停随创建/保存生效；未知结果核对原请求/发布，不重发 |
| 自动化执行记录 | [完整工作区旅程](product-experience.md#current--complete-native-automation-workspace-accepted43-amended46) / [现行要求](v2-requirements.md#automation-workspace-requirements--current-slice-43-pass--closed)；记录只读展示当前 Task 流程、原始实际时间、独立文件结果、失败原因和下一步；合法续作不改写原始时间/尝试/文件效果，不增加运行次数或恢复入口 |
| 三项系统运行设置 | [字段、保存与实际采用](configuration.md#current--three-system-runtime-settings-slice47-pass--closed)；系统设置是唯一常用入口，整理额度由各入口共享，Worker 空闲轮询覆盖共享异步工作，Scheduler 轮询只检查自动化到期；发布与实际采用分开呈现 |
| OpenList 属性查询与内容读取 | [配置说明](configuration.md#openlist-metadata-and-content-reads) / [Storage 架构](architecture.md#storage-abstraction)；属性使用缓存目录列表，内容按实际需求读取，原生移动／重命名保留前后核验 |
| 已退役能力的现行边界 | [FileIndex](file-index-retirement-spec.md) / [Preview](preview-retirement-spec.md)；不恢复旧入口或兼容执行器 |
| 角色经验 / Task 模板 | [A](agent-experience/slice-owner-architect-final-reviewer.md)、[B](agent-experience/task-planner-reviewer.md)、[Developer](agent-experience/developer-implementation-role.md) / [Task Template](../Task/TEMPLATE.md) |

事实维护与验证等级遵循 Development Workflow。更新现行说明时保留稳定 ID、明确延期与已接受
Base/Head/关闭事实；不把历史日志、测试流水或可选改进重新写成实施要求。
