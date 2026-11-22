# 文档导航

从 `/` 登录 Web，在「任务中心」查看本版本的任务和结果。脚本使用从「系统设置」签发的分权限令牌访问 `/api/*`。[登录与恢复](product-experience.md#current--single-web-administrator-and-scoped-api-tokens-slice57-pass--closed) · [脚本令牌](deployment.md#script-api-tokens)

共享顶栏只提供账户入口。通过侧栏「通知」管理 Webhook 和查看投递记录，通过「存储管理」的类型卡片和分页查找存储。[使用说明](product-experience.md#v2-operator-web) · [存储管理](product-experience.md#storage-management-and-root-recovery)

在「系统设置」初始化空配置或直接应用修改。部署支持纯净初始化和同版本重启。启动遇到不支持的数据库时，保留原库并使用新的空数据目录。只有通过数据库适用性检查且报告 `DATA_SWITCH_REQUIRED` 的 schema 11 配置库才走显式切换。[系统设置](configuration.md#system-settings-web) · [部署边界](deployment.md#boundary) · [配置数据切换](configuration.md#previous-store-data-switch)

## 使用和部署

| 文档 | 内容 |
| --- | --- |
| [快速开始](../README.md#-快速开始) | Docker Compose 和本地源码运行。 |
| [配置说明](configuration.md) | 凭据、校验、直接发布和规则。 |
| [部署指南](deployment.md) | 媒体挂载、健康检查、重启和备份。 |
| [用户操作](product-experience.md) · [任务中心](task-center-page-spec.md) | 日常文件操作、整理、自动化及恢复。 |
| [文件页](file-page-visual-spec.md) · [媒体库](media-library-page-visual-spec.md) | 两类库的页面行为。 |
| [发布验证](release.md) · [存储验收](storage-acceptance.md) | 制品门禁、实际验证和支持范围。 |

## 维护和开发

| 文档 | 内容 |
| --- | --- |
| [开发约束](../AGENTS.md) · [开发流程](development-workflow.md) | 职责、范围、测试、审查和关闭。 |
| [需求与稳定 ID](requirements.md) · [现行要求修订](v2-requirements.md) · [架构](architecture.md) | 产品范围、现行契约与组件边界。 |
| [路线图](roadmap.md) · [验收账本](progress.md) | 大版本优先级、已接受范围及固定验收记录。 |
| [当前 Slice](../SLICE.md) · [当前 Task](../TASK.md) · [Task 模板](../Task/TEMPLATE.md) | 开发范围和当前状态。 |

近期整理修复的验收记录可通过固定提交查阅。[整理确认自动核对](https://github.com/kentinya/mediaflow/blob/455ad4f70c645b1a2e65f4af61378101a25435d8/TASK.md#patch-20261120-3--b-验收-pass) · [主文件超限后的任务收尾](https://github.com/kentinya/mediaflow/blob/e5fd939f17bf43fcff55d0fed66ec13d644868a6/TASK.md#patch-20261120-2--b-验收-pass) · [后续季匹配及修正](https://github.com/kentinya/mediaflow/blob/66e1e799b5bc5ada7b8ea81bd15052969c40b38a/TASK.md#patch-20261120-1--b-验收-pass)

此前的顶栏修复也有固定验收记录。[删除顶栏搜索框](https://github.com/kentinya/mediaflow/blob/c8039f1f3d7bdfdb7fd927c75f99df0cb8a9e523/TASK.md#patch-20261119-2--b-验收-pass) · [删除顶栏占位铃铛](https://github.com/kentinya/mediaflow/blob/ace169f4ee14feb4a101b7b2da2e917fe1c7c145/TASK.md#patch-20261119-1--b-验收-pass)

旧设计图、既往独立修正和只读归档可在对应检查点查阅。[原设计图](https://github.com/kentinya/mediaflow/tree/31f31031ac9e65a16f5d7e5b50ae85f1c21ad761/docs/pics) · [历次修正](https://github.com/kentinya/mediaflow/blob/f1a0b10e29ec6fdbdad67fd97345065113f45626/docs/README.md#文档导航与职责) · [历史文档](history/)
