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
| API/UI/Scheduler | 部分完成 | API 主体/RBAC/审计、运营 Dashboard、Cron、通知、一次性授权执行 | Web UI、登录/外部身份源 |

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

Phase 18.4.1 已完成通知投递租约与进程崩溃后的过期领取恢复；稳定 Delivery ID 支持接收端
在 at-least-once 语义下去重，自动恢复不会重置尝试次数。

Phase 18.5 已完成默认关闭的本机一次性远程执行票据、摘要持久化、原子消费/Job 创建和审计。
普通 API Token 不能单独授权变更，Scheduler 仍禁止 organize。

Phase 18.6 已完成配置化 API Principal、最小权限角色、401/403 路由授权和 SQLite v9 脱敏
安全审计。Executor 角色仍必须另外消费 Phase 18.5 一次性票据。

Phase 18.7 已完成面向 CLI/API/未来 Web UI 的只读运营 Dashboard Read Model；通过 SQLite
聚合 FileIndex、Task、Job、待确认和通知状态，不访问 Storage 或网络，也不暴露原始错误路径。

Phase 18.8 已完成受 RBAC 保护的冲突确认列表/详情/审计和 Skip/Rename 决策 API。确认、审计
与 TaskItem 转换原子提交；远程 Overwrite 和自动重试/执行仍被禁止。

Phase 18.9 已完成持久元数据复核队列：NeedConfirm/Ambiguous 候选以受限、Provider-neutral
快照持久化，TaskItem 原子进入 `waiting_metadata` 并释放源锁；CLI/API/Dashboard 只提供
脱敏可见性，不选择候选、不访问 Provider、不自动恢复或执行。

Phase 18.10 已完成显式元数据候选选择与恢复接线：仅允许选择持久快照 rank，决策/审计/
TaskItem 状态原子提交；选择本身零网络、零 Storage、零 Job，只有后续显式 `tasks resume`
才校验策略并通过现有 Provider-ID 详情流程继续处理。

Phase 18.11 已完成分类复核队列与显式配置规则选择：未分类项目持久保存当前策略的启用规则
选择，决策/审计/TaskItem 原子提交；不允许任意媒体库或路径，显式 resume 会重新校验当前
规则后才进入 Planner。

### Phase 19：Web UI 与生产发布

- Dashboard、Storage/Library/Policy 管理、候选确认、冲突处理、任务和历史页面。
- 权限、审计、备份恢复、升级指南、可观测性和发布流水线。
- 完成跨平台、长时间批处理、故障注入和真实存储矩阵验收。

Phase 19.1 已实现最小安全操作台：同一 WSGI 进程提供无依赖 Dashboard 和三类复核界面，
Token 仅存于页面内存，受控决策继续通过现有 RBAC/审计 API。任务控制、真实执行、Overwrite、
配置编辑、用户数据库/OIDC 和 TLS 发布仍未开放。

Phase 19.2 已实现 API 凭证生命周期与 HTTP 部署护栏：提供系统随机 Token 生成和脱敏环境
状态检查，记录双 Principal 手工轮换流程；开发服务器默认只允许回环监听，非回环明文 HTTP
必须显式危险确认。TLS 终止、OIDC 与 Secret Store 仍不在应用内实现。

Phase 19.3 已实现 Task/Job/Result 只读操作台：列表和 TaskItem/Result 详情均受 1–100 上限
约束，SQLite 使用 limit+1 判断截断；UI 不提供提交、取消、恢复、重试、授权或执行操作。

Phase 19.4 已消除大型历史只能查看首页的风险；Phase 19.5 进一步为 Task/Job 与
TaskItem/Result 提供稳定复合键双向 keyset 游标，不使用 OFFSET。操作台提供显式
Previous/Next，仍无任意页跳转、总数扫描或任何任务控制权限。

Phase 19.6 已补齐 Scheduler 与 Notification 的只读运维可见性：调度定义/状态、限定条数的
发生审计，以及按状态过滤的限定条数投递记录均进入现有安全操作台。Webhook 地址/正文/
签名和原始异常不暴露，也没有 tick、编辑、投递或重排控制。

Phase 19.7 已将相同的双向稳定 keyset 游标扩展到通知投递与单个调度发生审计。通知游标
绑定状态过滤器，调度游标绑定调度 ID，跨 scope 复用会失败；不使用 OFFSET 或总数扫描。

Phase 19.8 已建立默认关闭的结构化脱敏运行日志：SQLite v13 仅保存固定事件和安全标识，
提供本地有界查询及显式年龄/条数保留清理，不保存路径、原始错误或任意上下文。

## 下一步实施建议

Phase 19.1 完成后，后续任务仍应保持小步推进。优先顺序：

1. 在现有脱敏日志模型上评估只读 Web/API 游标检索，不开放任务执行控制。
2. 评估数据库用户/OIDC 与外部 Secret Store 集成，不在核心中自建弱认证系统。
3. 评估节假日日历等高级调度需求，避免扩大 Cron 核心。
4. 保持 Storage 预检、附件、冲突确认和一次性执行授权不变。

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
