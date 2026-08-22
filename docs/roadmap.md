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
| Storage | 已完成 | Local、SMB、OpenList、S3/R2 Adapter 与 JSON Runtime | 更多实机验证 |
| Scanner/FileIndex | 已完成 | 扫描、稳定性、全量/增量、生产 SQLite FileIndex | 后续管理/清理工具 |
| Parser | 已完成 | 文件名/路径、电影/剧集、多集、标签 | NFO Parser |
| Recognition | 已完成 | 配置规则、优先级、证据、C 身份保持 | 人工修正流程 |
| Metadata | 部分完成 | TMDB、缓存、候选评分、本地化标题、年份语义 | 人工候选确认、持久共享缓存管理 |
| Naming | 已完成 | 安全模板、Unicode、多集、预览 | 用户界面配置体验 |
| Classification | 已完成 | 确定性规则和媒体库选择 | 人工分类确认 |
| Planner/Executor | 部分完成 | 计划、冲突保护、DryRun、真实执行、跨存储 | 完整冲突策略、附件、Rollback |
| Task/History | 部分完成 | 持久 Task/Item/Result/Job、Worker、协作取消、锁、JSONL 历史 | 强制中断、自动恢复 |
| API/UI/Scheduler | 部分完成 | 只读/DryRun API、interval/Cron 调度、签名 Webhook 通知 | 执行 API、Web UI、权限 |

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

### Phase 16：附件与媒体集合（已完成）

- 字幕、NFO、Poster、Fanart、Trailer 和同名附件发现。
- 主文件与附件形成一个原子计划集合，保留字幕语言/Forced/SDH 后缀。
- 部分失败必须可恢复，不删除未知文件，默认不清理源目录。

验收范围：附件策略默认关闭；启用后通过 Storage 只读发现同目录关联文件，生成安全的文件
集合计划并由 OrganizerExecutor 统一执行。部分结果保存已完成步骤，不清理未知文件。

### Phase 17：运行时适配器与运维完善（已完成）

- 为 SMB、S3/R2 增加环境变量持有密钥的 JSON Runtime 配置构造。
- 增加连接测试、只读验证、能力预检和专用实机验收套件。
- 配置导入导出、版本迁移、日志轮转和缓存维护。

验收范围：SMB/S3/R2 JSON Runtime 装配、环境变量密钥、配置校验和只读 Storage 预检已
完成。持久缓存管理和文件日志轮转将在相应持久后端引入时实现，不提供空操作命令。

### Phase 18：服务化与自动化（进行中）

- REST API、Task Worker、Scheduler、Cron、Webhook 和通知。
- API 复用 Application Service，不复制策略引擎或绕过 OrganizerExecutor。
- 先提供只读查询和 DryRun API，再开放受保护的执行 API。

Phase 18.1 已完成持久 scan/preview 队列、单作业原子领取 Worker、只读 Task/Job/
Confirmation REST 查询，以及只允许 DryRun 工作的受鉴权提交接口。远程真实执行未开放。

Phase 18.2 已完成常驻 Worker、跨扫描/批处理边界的协作取消、显式陈旧作业恢复和持久
interval 调度。调度仅允许 scan/preview；Cron 日历表达式与远程真实执行仍未开放。

Phase 18.3 已完成五字段 Cron、IANA 时区、DST 确定性语义和不可变调度发出审计。Cron 与
interval 都只允许 scan/preview；远程真实执行仍未开放。

Phase 18.4 已完成持久通知 Outbox、HMAC 签名 Webhook、受限重试/死信、独立投递 Worker
和只读通知查询。通知失败不改变作业终态，也不触发任何 Storage 或媒体操作。

### Phase 19：Web UI 与生产发布

- Dashboard、Storage/Library/Policy 管理、候选确认、冲突处理、任务和历史页面。
- 权限、审计、备份恢复、升级指南、可观测性和发布流水线。
- 完成跨平台、长时间批处理、故障注入和真实存储矩阵验收。

## 下一步实施建议

下一任务应限定为 Phase 18，不同时启动 Web UI。优先顺序：

1. 设计独立、可审计的远程 organize execute 授权，不复用普通 API Token。
2. 增加用户、权限和更完整的审计边界。
3. 评估节假日日历等高级调度需求，避免扩大 Cron 核心。
4. 保持 Storage 预检、附件、冲突确认和显式执行授权不变。

Interval/Cron Scheduler 已实现但只允许 scan/preview；仍不支持无人值守定时
`organize --execute`。

## 持续安全基线

- 默认 DryRun；真实变更必须显式授权。
- 不覆盖已存在目标，不静默删除源或未知文件。
- 只有 OrganizerExecutor 可以调用 Storage mutation。
- 同存储操作优先原生能力；跨存储 Move 必须 Copy→校验→Delete。
- 任何回退必须由策略显式配置，不得改变操作语义。
- 凭证仅来自环境或未来 Secret Store，不进入配置导出、日志和历史。
- RecognitionType C 复用 A 下游策略时仍必须保持 C。
