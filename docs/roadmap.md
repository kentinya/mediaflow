# MediaFlow 总体实施计划

## 当前节点

截至 2026-08-21，项目完成了安全优先的核心纵向链路：

```text
Runtime Configuration
→ ResourceLibrary Scan
→ Parser
→ Recognition
→ Metadata / CandidateMatcher
→ Naming
→ Classification
→ MediaLibrary Resolution
→ OrganizePlan
→ OrganizerExecutor
→ Execution History
```

当前可通过 CLI 扫描配置中的资源库、预览确定性计划，并在显式 `--execute` 时执行。
计划携带源/目标 Storage 身份，可处理本地与 OpenList 组合。默认不覆盖、不静默删除，DryRun
零变更。该节点应定义为“核心执行链完成”，而不是“完整产品完成”。

## 能力矩阵

| 领域 | 状态 | 当前能力 | 主要缺口 |
|---|---|---|---|
| Storage | 已完成 | Local、SMB、OpenList、S3/R2 Adapter | SMB/S3/R2 JSON Runtime 装配、更多实机验证 |
| Scanner/FileIndex | 已完成 | 扫描、稳定性、全量/增量、生产 SQLite FileIndex | 后续管理/清理工具 |
| Parser | 已完成 | 文件名/路径、电影/剧集、多集、标签 | NFO Parser |
| Recognition | 已完成 | 配置规则、优先级、证据、C 身份保持 | 人工修正流程 |
| Metadata | 部分完成 | TMDB、缓存、候选评分、本地化标题、年份语义 | 人工候选确认、持久共享缓存管理 |
| Naming | 已完成 | 安全模板、Unicode、多集、预览 | 用户界面配置体验 |
| Classification | 已完成 | 确定性规则和媒体库选择 | 人工分类确认 |
| Planner/Executor | 部分完成 | 计划、冲突保护、DryRun、真实执行、跨存储 | 完整冲突策略、附件、Rollback |
| Task/History | 部分完成 | 持久 Task/Item/Result、恢复重试、锁、JSONL 历史 | 后台队列、实时暂停/控制 |
| API/UI/Scheduler | 未开始 | 需求和模块边界 | API、Web UI、调度、权限、通知 |

## 总体阶段计划

### Phase 14：持久化与可恢复任务基础（已完成）

- 将 CLI Scanner 从 InMemoryFileIndexRepository 切换到配置化 SQLite FileIndex。
- 定义持久 Task、TaskItem、ResultRecord 仓储和数据库版本迁移。
- 保存每个阶段状态、错误、计划 ID、重试次数和时间信息。
- 实现同一 `StorageID + Path` 的任务互斥。
- 支持取消、恢复中断任务、仅重试失败项；重启后不得重复成功的变更操作。
- 保持 Scanner/Parser/Recognition/Metadata/Naming/Classification/Planner 零变更边界。

验收结果：生产 CLI 已接入持久 FileIndex；Task/TaskItem/Result/Lock 使用版本化 SQLite；
显式 resume/retry 排除成功终态并重新要求执行授权；DryRun 仍零 mutation。

### Phase 15：冲突与人工确认（已完成）

- 完整实现 Skip、Rename、Manual；Overwrite 仅在显式高风险策略和确认后允许。
- 建立目标冲突 NeedConfirm 队列；元数据候选和分类人工选择留给后续交互层。
- 加入 Provider ID、媒体类型和季集范围的重复检测身份；Hash 读取仍保持关闭。
- 不把冲突解决逻辑放入 Naming、Classification 或 Storage Adapter。

验收范围：目标冲突的 Skip/Rename/Manual/Overwrite 决策、SQLite NeedConfirm 与审计、显式
高风险覆盖授权和剧集范围重复身份已经实现。元数据候选与分类人工选择留给后续交互层。

### Phase 16：附件与媒体集合（下一步）

- 字幕、NFO、Poster、Fanart、Trailer 和同名附件发现。
- 主文件与附件形成一个原子计划集合，保留字幕语言/Forced/SDH 后缀。
- 部分失败必须可恢复，不删除未知文件，默认不清理源目录。

### Phase 17：运行时适配器与运维完善

- 为 SMB、S3/R2 增加环境变量持有密钥的 JSON Runtime 配置构造。
- 增加连接测试、只读验证、能力预检和专用实机验收套件。
- 配置导入导出、版本迁移、日志轮转和缓存维护。

### Phase 18：服务化与自动化

- REST API、Task Worker、Scheduler、Cron、Webhook 和通知。
- API 复用 Application Service，不复制策略引擎或绕过 OrganizerExecutor。
- 先提供只读查询和 DryRun API，再开放受保护的执行 API。

### Phase 19：Web UI 与生产发布

- Dashboard、Storage/Library/Policy 管理、候选确认、冲突处理、任务和历史页面。
- 权限、审计、备份恢复、升级指南、可观测性和发布流水线。
- 完成跨平台、长时间批处理、故障注入和真实存储矩阵验收。

## 下一步实施建议

下一任务应限定为 Phase 16，不同时启动 API 或 UI。优先顺序：

1. 定义主媒体与字幕/NFO/图片/Trailer 的附件集合模型。
2. 通过 Storage 只读发现同名附件并保留语言、Forced、SDH 后缀。
3. 生成原子计划集合并为部分失败提供可恢复记录。
4. 默认不清理源目录，不删除未知文件。
5. 保持 Phase 15 冲突确认和执行授权边界不变。

Scheduler 尚未实现；当前不支持无人值守定时 `organize --execute`。

## 持续安全基线

- 默认 DryRun；真实变更必须显式授权。
- 不覆盖已存在目标，不静默删除源或未知文件。
- 只有 OrganizerExecutor 可以调用 Storage mutation。
- 同存储操作优先原生能力；跨存储 Move 必须 Copy→校验→Delete。
- 任何回退必须由策略显式配置，不得改变操作语义。
- 凭证仅来自环境或未来 Secret Store，不进入配置导出、日志和历史。
- RecognitionType C 复用 A 下游策略时仍必须保持 C。
