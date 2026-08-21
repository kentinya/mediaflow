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
| Scanner/FileIndex | 部分完成 | 扫描、稳定性、全量/增量、SQLite Adapter | CLI 接通持久 FileIndex、跨进程增量状态 |
| Parser | 已完成 | 文件名/路径、电影/剧集、多集、标签 | NFO Parser |
| Recognition | 已完成 | 配置规则、优先级、证据、C 身份保持 | 人工修正流程 |
| Metadata | 部分完成 | TMDB、缓存、候选评分、本地化标题、年份语义 | 人工候选确认、持久共享缓存管理 |
| Naming | 已完成 | 安全模板、Unicode、多集、预览 | 用户界面配置体验 |
| Classification | 已完成 | 确定性规则和媒体库选择 | 人工分类确认 |
| Planner/Executor | 部分完成 | 计划、冲突保护、DryRun、真实执行、跨存储 | 完整冲突策略、附件、Rollback |
| Task/History | 部分完成 | 状态模型、取消、JSONL 执行历史 | 持久队列、暂停/恢复、失败项重试、锁 |
| API/UI/Scheduler | 未开始 | 需求和模块边界 | API、Web UI、调度、权限、通知 |

## 总体阶段计划

### Phase 14：持久化与可恢复任务基础（下一步）

- 将 CLI Scanner 从 InMemoryFileIndexRepository 切换到配置化 SQLite FileIndex。
- 定义持久 Task、TaskItem、ResultRecord 仓储和数据库版本迁移。
- 保存每个阶段状态、错误、计划 ID、重试次数和时间信息。
- 实现同一 `StorageID + Path` 的任务互斥。
- 支持取消、恢复中断任务、仅重试失败项；重启后不得重复成功的变更操作。
- 保持 Scanner/Parser/Recognition/Metadata/Naming/Classification/Planner 零变更边界。

验收门槛：进程重启后增量扫描状态仍存在；失败批次可安全恢复；DryRun 仍零 mutation；
执行操作具有幂等保护和可审计结果。

### Phase 15：冲突与人工确认

- 完整实现 Skip、Rename、Manual；Overwrite 仅在显式高风险策略和确认后允许。
- 建立 NeedConfirm 队列，支持元数据候选、分类、目标冲突的人工选择。
- 加入 Provider ID、季集和可选 Hash 的重复检测策略。
- 不把冲突解决逻辑放入 Naming、Classification 或 Storage Adapter。

### Phase 16：附件与媒体集合

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

下一任务应限定为 Phase 14，不同时启动附件、API 或 UI。优先顺序：

1. 设计 SQLite schema/version 和 Repository ports。
2. 将生产 CLI 的 FileIndex 从内存实现切换为配置化持久实现。
3. 建立 Task/TaskItem/ResultRecord 状态机与恢复规则。
4. 增加单文件互斥、重复执行保护和仅重试失败项。
5. 添加崩溃恢复、取消、部分成功、跨进程增量扫描和零 mutation 回归。
6. 更新配置模板，提供数据库路径、保留期和迁移命令。

在 Phase 14 验收前，不建议开启无人值守定时 `organize --execute`。

## 持续安全基线

- 默认 DryRun；真实变更必须显式授权。
- 不覆盖已存在目标，不静默删除源或未知文件。
- 只有 OrganizerExecutor 可以调用 Storage mutation。
- 同存储操作优先原生能力；跨存储 Move 必须 Copy→校验→Delete。
- 任何回退必须由策略显式配置，不得改变操作语义。
- 凭证仅来自环境或未来 Secret Store，不进入配置导出、日志和历史。
- RecognitionType C 复用 A 下游策略时仍必须保持 C。
