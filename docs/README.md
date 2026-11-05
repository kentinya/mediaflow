# 文档导航与职责

当前 [Slice50](../SLICE.md) 为 **ACTIVE**；用户已激活 [Task50.1](../TASK.md)，状态
**PLANNED（待实施）**，作为唯一活动实施 Task。本轮仅完成激活，尚未开始代码实施。
Slice49 的 PASS / CLOSED 保留。
最近独立自动化界面修正已由 B 验收 PASS，固定审查指针见 Slice Contract；大版本接受事实不变。
现行文档说明当前规则、用户旅程和架构；验收事实在关闭账本与对应 Git checkpoint，详细
开发过程留在 Git。`docs/history/` 是 LEGACY / READ ONLY，不作为当前指令，也不继续追加归档。

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
| 弹卡、可读性与切页目标（未实施） | [Slice50 Contract](../SLICE.md) / [原八项与自动化弹卡稳定性补充](v2-requirements.md#target--v2-dialog-readability-and-navigation-experience-slice50-active) / [完整目标旅程](product-experience.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)；目录树/抽屉替换、V2 侧栏主页面切换与自动化新建/编辑抖动修复均是 TARGET，保留既有业务与接受事实 |
| Task 流程、文件结果与自动化成功率 | [Slice48 已接受旅程](product-experience.md#current--task-flow-status-and-automation-success-rate-slice48-pass--closed)；Task 五态与文件结果独立，completed 不代表文件全部成功；定时/定义运行一次按 completed/(completed+failed) 统计，取消和未结束不入分母，手动整理/普通操作不参与 |
| 自动化创建、编辑与运行一次 | [Slice49 现行旅程](product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed) / [稳定要求](v2-requirements.md#automation-forms-and-direct-run-once--current-slice49-pass--closed)；列表直接运行或复制已保存定义，复制紧邻编辑并生成停用副本；创建/编辑共用中文卡片和紧凑启用开关，启停随创建/保存生效；未知结果核对原请求/发布，不重发 |
| 自动化执行记录 | [完整工作区旅程](product-experience.md#current--complete-native-automation-workspace-accepted43-amended46) / [现行要求](v2-requirements.md#automation-workspace-requirements--current-slice-43-pass--closed)；记录只读展示当前 Task 流程、原始实际时间、独立文件结果、失败原因和下一步；合法续作不改写原始时间/尝试/文件效果，不增加运行次数或恢复入口 |
| 三项系统运行设置 | [字段、保存与实际采用](configuration.md#current--three-system-runtime-settings-slice47-pass--closed)；系统设置是唯一常用入口，整理额度由各入口共享，Worker 空闲轮询覆盖共享异步工作，Scheduler 轮询只检查自动化到期；发布与实际采用分开呈现 |
| 已退役能力的现行边界 | [FileIndex](file-index-retirement-spec.md) / [Preview](preview-retirement-spec.md)；不恢复旧入口或兼容执行器 |
| 角色经验 / Task 模板 | [A](agent-experience/slice-owner-architect-final-reviewer.md)、[B](agent-experience/task-planner-reviewer.md)、[Developer](agent-experience/developer-implementation-role.md) / [Task Template](../Task/TEMPLATE.md) |

事实维护与验证等级遵循 Development Workflow。更新现行说明时保留稳定 ID、明确延期与已接受
Base/Head/关闭事实；不把历史日志、测试流水或可选改进重新写成实施要求。
