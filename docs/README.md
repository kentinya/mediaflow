# 文档导航与职责

Slice 56 已通过独立终审。Web 入口为 `/`，API 使用 `/api/*`。既有任务可在新地址继续查看。
大版本状态、验收记录及当前实施状态见 [Roadmap](roadmap.md)、[Progress](progress.md) 和 [TASK.md](../TASK.md)。

现行文档记录规则、用户旅程与架构。详细验收和独立修正记录以固定 Git 检查点为准。
旧设计图和以往修正索引可分别查看 [原设计图](https://github.com/kentinya/mediaflow/tree/31f31031ac9e65a16f5d7e5b50ae85f1c21ad761/docs/pics)
和 [历史修正索引](https://github.com/kentinya/mediaflow/blob/f1a0b10e29ec6fdbdad67fd97345065113f45626/docs/README.md#文档导航与职责)。
`docs/history/` 为只读历史记录。

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
| 当前支持范围与发布验证 | [Release](release.md#current-v2-validation-boundary) / [Storage Acceptance](storage-acceptance.md) |
| 正式 Web 与 API 入口（CURRENT） | [稳定要求](v2-requirements.md#current--canonical-web-and-api-routes-slice56-pass--closed) / [用户旅程](product-experience.md#current--canonical-entry-journey-slice56-pass--closed) / [架构](architecture.md#current--root-web-and-unversioned-api-slice56-pass--closed) / [换址指南](../README.md#v2-development-status) |
| V1 与旧迁移路径退役（CURRENT） | [稳定要求](v2-requirements.md#current--complete-v1-and-migration-residue-retirement-slice55-pass--closed) / [用户旅程](product-experience.md#current--complete-v1-and-migration-residue-retirement-slice55-pass--closed) / [架构](architecture.md#current--complete-v1-and-migration-residue-retirement-slice55-pass--closed) |
| 页面组成与交互 | [Files](file-page-visual-spec.md)、[MediaLibrary](media-library-page-visual-spec.md)、[Task Center](task-center-page-spec.md)；现行文字约定及实际界面为依据，旧设计图仅在 Git 保留历史 |
| 整理规则弹窗与可读性（CURRENT） | [Slice54 Contract/A 终审](https://github.com/kentinya/mediaflow/blob/05b51268f60f8cc932f6c71d9cfa1efac1227b3e/SLICE.md#a-final-review--pass--closed) / [现行要求](v2-requirements.md#current--organizing-rules-dialogs-and-readability-slice54-pass--closed) / [完整旅程](product-experience.md#current--organizing-rules-dialogs-and-readability-slice54-pass--closed) / [架构](architecture.md#current--organizing-rules-dialogs-and-readability-slice54-pass--closed)；七类添加／复制／编辑统一弹窗，设置与单项测试分区；完整流程只在概览检查已发布 Active，准确发布、草稿配对及未知核对不重发保持 |
| 逐文件整理与任务交接（CURRENT） | [Slice53 Contract/A 终审](https://github.com/kentinya/mediaflow/blob/8bc3ef905a76b96ef8ec327154b92e9b9972ea05/SLICE.md#closure-packet-and-a-final-review) / [现行要求](v2-requirements.md#current--manual-organize-dialog-slice53-pass--closed) / [完整旅程](product-experience.md#current--manual-organize-dialog-slice53-pass--closed)；Files 单项／批量／有界文件夹在弹窗逐项复核、保存分析并一次确认；未知响应核对原请求后打开准确任务，进度／结果／四类恢复保持，入口和文件证据按 [任务中心现行约定](task-center-page-spec.md) 呈现；角色例外与测试限制见 Contract |
| 七项体验修整（CURRENT） | [Slice52 Contract](https://github.com/kentinya/mediaflow/blob/19a458eb6c1a6afb8693d2757755487a58213a4f/SLICE.md) / [现行要求](v2-requirements.md#current--slice52-experience-refinement-slice52-pass--closed) / [现行旅程](product-experience.md#current--slice52-experience-refinement-slice52-pass--closed) / [现行架构](architecture.md#current--slice52-experience-refinement-slice52-pass--closed)；探索整页美观／详情滚动／浏览长度可控，全部九个主页面切换及读取接入没有突兀闪烁／非预期抖动（含两种库刷新提示），允许正常目标页布局差异与稳定加载反馈；自动化旧打开链路退出，普通分页与动效参数为实现方案，已独立验收；失败与证据限制见 Contract |
| 探索首页（CURRENT） | [Slice51 Contract](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md) / [稳定要求](v2-requirements.md#current--v2-explore-homepage-slice51-pass--closed) / [完整旅程](product-experience.md#current--v2-explore-homepage-slice51-pass--closed) / [架构](architecture.md#current--v2-explore-homepage-slice51-pass--closed)；TMDB 电影／剧集、筛选／搜索、详情和准确返回，Dashboard Web／API／CLI 及专属实现全退出，无兼容；已接受，证据限制见 Contract |
| 弹卡、可读性与主页面切换（CURRENT） | [Slice50 Contract](https://github.com/kentinya/mediaflow/blob/214b69b1e64b24fc22068c2e1760cd1b0c6ac787/SLICE.md) / [原八项与自动化弹卡稳定性补充](v2-requirements.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed) / [完整现行旅程](product-experience.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)；目录树/抽屉替换、V2 侧栏主页面切换与自动化新建/编辑抖动修复均已接受，保留既有业务与接受事实 |
| Task 流程、文件结果与自动化成功率 | [Slice48 已接受旅程](product-experience.md#current--task-flow-status-and-automation-success-rate-slice48-pass--closed)；Task 五态与文件结果独立，completed 不代表文件全部成功；定时/定义运行一次按 completed/(completed+failed) 统计，取消和未结束不入分母，手动整理/普通操作不参与 |
| 自动化创建、编辑与运行一次 | [Slice49 现行旅程](product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed) / [稳定要求](v2-requirements.md#automation-forms-and-direct-run-once--current-slice49-pass--closed)；列表直接运行或复制已保存定义，复制紧邻编辑并生成停用副本；创建/编辑共用中文卡片和紧凑启用开关，启停随创建/保存生效；未知结果核对原请求/发布，不重发 |
| 自动化执行记录 | [完整工作区旅程](product-experience.md#current--complete-native-automation-workspace-accepted43-amended46) / [现行要求](v2-requirements.md#automation-workspace-requirements--current-slice-43-pass--closed)；记录只读展示当前 Task 流程、原始实际时间、独立文件结果、失败原因和下一步；合法续作不改写原始时间/尝试/文件效果，不增加运行次数或恢复入口 |
| 系统设置与实际采用 | [页面操作与高级分组](configuration.md#system-settings-web) / [三项运行字段、保存与实际采用](configuration.md#current--three-system-runtime-settings-slice47-pass--closed)；系统设置是唯一常用入口，运行字段一次保存发布，高级分组保存草稿后验证／检查／显式激活；发布与实际采用分开呈现 |
| OpenList 属性查询与内容读取 | [配置说明](configuration.md#openlist-metadata-and-content-reads) / [Storage 架构](architecture.md#storage-abstraction)；属性使用缓存目录列表，内容按实际需求读取，原生移动／重命名保留前后核验 |
| 已退役能力的现行边界 | [FileIndex](file-index-retirement-spec.md) / [Preview](preview-retirement-spec.md)；不恢复旧入口或兼容执行器 |
| 角色经验 / Task 模板 | [A](agent-experience/slice-owner-architect-final-reviewer.md)、[B](agent-experience/task-planner-reviewer.md)、[Developer](agent-experience/developer-implementation-role.md) / [Task Template](../Task/TEMPLATE.md) |

事实维护与验证等级遵循 Development Workflow。更新现行说明时保留稳定 ID、明确延期与已接受
Base/Head/关闭事实；不把历史日志、测试流水或可选改进重新写成实施要求。
