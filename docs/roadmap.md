# MediaFlow 总体实施计划

## 当前节点

截至 2026-08-23，项目完成了安全优先的核心纵向链路、Phase 18 服务化基础，以及
Phase 19 有界生产发布验收：

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
计划携带源/目标 Storage 身份，可处理 Local、SMB、OpenList、S3-compatible 的同存储与
跨存储组合。默认不覆盖、不静默删除，DryRun 零变更。隔离 Local/Samba/OpenList/MinIO 已完成
生命周期、传输、128 文件、128 MiB 流式对象和中断恢复 profile。该节点定义为“核心执行链与
有界发布硬门完成”，而不是“完整产品完成”。

## 能力矩阵

| 领域 | 状态 | 当前能力 | 主要缺口 |
|---|---|---|---|
| Storage | 已完成（有界验收） | Local、SMB、OpenList、S3/R2 Adapter、JSON Runtime、隔离 Samba/OpenList/MinIO 矩阵 | AWS/R2、第三方 driver、远端原子与多小时专项验收 |
| Scanner/FileIndex | 已完成 | 扫描、稳定性、全量/增量、生产 SQLite FileIndex | 后续管理/清理工具 |
| Parser | 已完成 | 文件名/路径/NFO、电影/剧集、多集、标签、受限 XML 与冲突证据合并 | NFO 生成不属于 Parser；更多格式按样本扩展 |
| Recognition | 已完成 | 配置规则、优先级、证据、C 身份保持 | 人工修正流程 |
| Metadata | 部分完成 | TMDB、缓存、候选评分、本地化标题、年份语义、持久人工候选选择/恢复 | 持久共享缓存管理、自由输入修正交互 |
| Naming | 已完成 | 安全模板、Unicode、多集、预览 | 用户界面配置体验 |
| Classification | 已完成 | 确定性规则、媒体库选择、持久人工规则选择/恢复 | 自由路径修正明确禁止；完整 UI 待做 |
| Planner/Executor | 部分完成 | 计划、完整冲突策略、附件、可配置 Hash 重复证据、有界同次执行 Rollback、DryRun、真实执行、跨存储 | 历史/崩溃恢复、空目录清理、Hash 持久复用 |
| Task/History | 部分完成 | 持久 Task/Item/Result/Job、Worker、取消、协作 pause/resume、claim fencing/心跳、锁、JSONL 历史 | 统一重试、不确定执行恢复 |
| API/UI/Scheduler | 部分完成 | API/RBAC/审计、最小安全操作台、Dashboard、Cron、通知、一次性授权执行 | 文件管理 UI、配置管理、登录/外部身份源 |

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

### Phase 18：服务化与自动化（已完成当前范围）

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

### Phase 19：最小安全操作台与生产发布硬门（已完成有界范围）

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

Phase 19.9 已为同一安全日志模型加入只读 API/Web 双向 keyset 浏览，游标绑定最低级别
过滤器；Web 不提供 prune、全文搜索、实时 tail 或任何工作流控制。

Phase 19.10 已实现 SQLite Runtime 在线一致性备份和只读校验：目标必须是新的本地文件，
完整性/Schema 校验通过后原子发布，绝不覆盖；破坏性的 Restore 仍明确不提供。

Phase 19.11 已建立可复现发布验证基线：Python 3.11–3.13 只读 CI 重复执行离线质量门，独立
wheel 作业检查包内容并在仓库外的新虚拟环境验证 CLI、示例配置和数据库备份。流水线不持有
生产密钥、不访问真实媒体存储，也不自动发布或部署。

Phase 19.12 已加入只读升级预检：对配置 Runtime 数据库与操作员显式提供的新备份复用相同
完整性/Schema 校验，报告 Python/应用/Schema 兼容性、迁移需求和备份时效。预检不打开可迁移
Repository、不访问媒体 Storage，也不执行升级、恢复或替换。

Phase 19.13 已加入非覆盖式离线恢复：已验证本地备份只能原子创建到完全空缺的配置 Runtime
路径；现有数据库、目录、符号链接和 SQLite sidecar 一律拒绝。系统不移动/删除旧库、不检测
进程存活，停机和旧数据保留仍是明确的人工步骤。

Phase 19.14 已加入 POSIX 协作式 Runtime 维护锁：普通生产命令持共享锁，确认恢复在服务调用
前必须取得独占锁，冲突立即失败且崩溃由内核释放。稳定空锁文件不删除；该机制不覆盖绕过
生产 CLI 的程序、分布式主机或尚未实现等价独占语义的平台。

Phase 19.15 已加入隔离式 Schema 迁移演练：显式备份被复制到私有临时 SQLite，只有副本通过
真实 Repository 前向迁移，再验证当前 Schema 和 Task/Result/审计/日志计数后清理。配置
Runtime 与备份不改变；生产迁移、自动回滚和服务编排仍未实现。

Phase 19.16 已加入只读系统与配置状态：生产 API 启动时从已验证的归一化配置生成有界不可变
快照，Web System 页只显示兼容性以及 Storage/Library/Policy 安全接线。路径、规则值、模板、
分类目录、端点、环境变量和凭证结构性排除；没有编辑、连通性检查、轮询或工作流控制。

Phase 19.17 已将既有 Automation Job 协作取消安全接入操作台：Pending/Running 详情需要请求
与确认两步，Operator/Executor/Admin 继续由 `cancel_job` RBAC 和审计约束。取消不提交新 Job、
不控制 Task、不授予执行权限、不回滚已完成操作，也不构造任何媒体或 Storage 服务。

Phase 19.18 已将既有 scan/preview DryRun Job 提交接入操作台：表单、审核、确认三步生成仅含
command/可选有界 limit 的请求，Operator/Executor/Admin 仍由 `submit_dry_run` 权限约束。
入队不构造工作流或 Storage，UI 不提供 organize、execute、Scheduler 或 Task 控制。

Phase 19.19 已加入持久活动 Job 准入：配置化上限原子约束 Pending+Running，手工 DryRun、
Scheduler 和受保护 organize 共用容量。满队列不创建 Job、不推进调度状态/审计、不消费一次性
票据，也不清理现有队列；API 返回受审计的 409，System 页只显示配置上限。

Phase 19.20 已加入陈旧 Running Job 的只读运维可见性：统一配置年龄阈值，SQLite 稳定有界
查询，认证 API 与显式加载 UI 只显示安全状态字段。真实执行授权 Job 会被标记为仅人工恢复；
系统不推断 Worker 死亡，也不提供自动重排、强制取消、重试或执行操作。

Phase 19.21 已加入 Automation Job claim fencing 与协作心跳：每次领取生成新的不透明随机 token，
心跳和终态按 Running+token 原子校验，重排清除旧 token。旧 Worker 无法覆盖新 claim 或发布其终态
通知；token 不进入 API/UI/CLI/日志。阻塞中的外部调用仍无后台心跳，也不提供自动恢复。

Phase 19 总体验收仍为 BLOCKED：此前子阶段 PASS 只代表各自范围通过，不代表真实 SMB/OpenList/
S3-R2、跨存储矩阵、长时间批处理与故障注入完成。Phase 19.22 开始纠偏，先建立权威矩阵并完成
LocalStorage 原子目标发布及跨存储 MOVE 大小不一致保源回归。

Phase 19.23 的隔离 OpenList 验收工具与四重破坏性门禁已实现，但当前环境未提供专用 URL、Token、
`mediaflow-acceptance-*` 空测试根和确认值，因此实机矩阵状态为 BLOCKED/NOT RUN。不得因工具和
fake 回归通过而推进 Phase 19.24；应先提供隔离环境并执行、留存 19.23 证据。

Phase 19.23.1 补齐验收工具自身的空根只读证明和原子非覆盖 JSON 证据记录：真实运行还必须显式
指定新报告文件，预检非空/不可读/非目录时零远端 mutation。当前仍未提供五项专用前提，因此
结果继续为 BLOCKED/NOT RUN；这不是推进 Phase 19.24 的依据。

Phase 19.23.2 已获授权自建回环隔离 OpenList v4.2.2 并实际执行。真实空目录响应使用
`content: null`，现有生产 HTTP mapper 只接受数组，空根预检以 `io_error` 失败；任何 mutation
前即停止，容器与临时秘密均已销毁。19.23 状态由 BLOCKED 转为 FAIL，下一任务必须单独修复该
DTO 兼容性并重跑完整矩阵，仍禁止推进 Phase 19.24。

Phase 19.23.3 已严格兼容 `content: null, total: 0` 并拒绝不一致组合；重新部署官方 v4.2.2 后，
OpenList 生命周期、Local↔OpenList、OpenList↔OpenList COPY/MOVE、内容/大小/源状态和白名单清理
全部实机通过。自建 Local driver 范围记为 ISOLATED PASS，不代表第三方云盘驱动或远端原子发布
认证。OpenList 硬门已关闭，下一任务可进入 Phase 19.24 的隔离 Samba 与 MinIO/S3-R2 矩阵。

Phase 19.24 已部署回环隔离 Samba 4.20.6 与 MinIO RELEASE.2025-07-23。MinIO 完整矩阵及清理
ISOLATED PASS；Samba 在真实 EEXIST 错误映射阶段失败并且适配器清理未完成，传输行按 fail-fast
未执行。Phase 19.24 当前 FAIL，下一任务只能单独修复 SMB EEXIST/清理语义并完整重跑 Samba，
不得提前进入 Phase 19.25。

Phase 19.24.1 已按结构化 errno 修复 Samba `EEXIST` 等错误分类，并消除目录枚举在非默认端口上
隐式回退 445 的二次 stat。新空根完整通过生命周期、Local↔SMB、SMB↔SMB、内容/源状态验证和
白名单清理。结合 19.24 的 MinIO PASS，Phase 19.24 在自建 Samba 与通用 S3-compatible MinIO
范围内关闭；AWS/R2 服务特性与远端原子发布仍未认证。下一任务进入 Phase 19.25 长时间批处理、
大文件、中断恢复与一致性验证，Phase 19 总体仍为 BLOCKED。

Phase 19.25 已用生产 Adapter 与 OrganizerExecutor 在全新隔离 Local、Samba、OpenList 和 MinIO
上完成统一的 128 文件批次、128 MiB 流式对象、确定性源流中断、MOVE 保源、目标状态检查、显式
重试和白名单清理。四个 profile 均 ISOLATED PASS，MinIO 无遗留 multipart；SMB 暴露的部分目标
被明确识别且未被当作成功。Phase 19 的可复现有界发布硬门关闭，整体记为 PASS。多小时 soak、
进程/主机断电、AWS/R2 服务特性和远端原子发布仍是部署专项限制，不作已认证声明。下一阶段按
计划进入 Phase 20 核心引擎收口，不继续扩展 Phase 19 操作台。

## 规格差距评估（2026-08-23，基于 Phase 19.25 后状态）

对照《影视媒体资源自动整理系统需求规格说明书》V1.1 全量章节逐项评估：

| 领域 | 完成度 | 主要剩余缺口 |
|---|---|---|
| 核心引擎（§1–§79） | ~97% | 空目录清理；历史 Rollback 与 Hash 持久复用留后续 |
| 存储层（§4–§10） | ~94% | 有界 Local/Samba/OpenList/MinIO 实机矩阵已通过；AWS/R2、第三方 driver、远端原子发布、Range Read/大对象服务端 Copy 未认证或未实现 |
| 任务与自动化（§62–§70、§98） | ~88% | 定时缓存/日志清理未实现；claim fencing/心跳已完成 |
| API 与 Web UI（§93–§96、§102） | ~35% | 仅只读运维操作台；文件列表、搜索筛选、媒体详情、人工修正交互均未实现 |
| 配置管理（§5、§86–§89） | ~30% | 12 类配置对象 CRUD、引用关系检查、导入导出、凭证加密存储均未实现 |
| 安全与审计（§99–§101） | ~70% | RBAC/脱敏/安全审计完成；用户体系、配置修改 Before/After 审计未实现 |

整体完成度约 75–78%。规格书本质是两份产品：媒体整理引擎（接近完成）+
配置与运维管理系统（刚起步，约占剩余工作量一半）。

## 剩余实施计划

### 阶段 I：发布硬门（Phase 19.23–19.25，已完成有界范围）

本阶段已由 Phase 19.25 关闭；历史执行期间 Phase 19 整体不得提前 PASS，且暂停了一切操作台
横向增强、OIDC 和高级调度。

- Phase 19.23：隔离真实 OpenList 验收矩阵 + Local↔OpenList / OpenList↔OpenList
  故障注入（roadmap 现行第 1 条）。
- Phase 19.24：隔离真实 SMB 与 S3/R2 验收矩阵，形成可复现验收报告
  （roadmap 现行第 2 条）。
- Phase 19.25：长时间批处理、大文件、中断恢复与一致性验证
  （roadmap 现行第 3 条）。
- 验收证据规则沿用 docs/storage-acceptance.md：fake/mock 只计 UNIT PASS，
  真实隔离环境才计 ISOLATED PASS；远端破坏性验收必须专用凭证 + 空测试根 +
  显式操作员确认。

### 阶段 II：核心引擎收口（Phase 20.x）

- Phase 20.1 NFO Parser 已完成：Storage-only 有界读取、安全 XML、确定性证据合并和生产管线接入。
- Phase 20.2 Hash 重复检测已完成：不计算/快速/完整，默认不计算；证据只读且失败闭合。
- 有界整理 Rollback 已完成：只补偿同次调用记录且再次验证的效果，不触碰未知文件；历史/崩溃恢复不在该边界（§49、§69）。
- 任务暂停/继续语义（§66）与只读工作流有界自动重试（§79）已完成；变更操作和不确定结果明确不自动重试。
- 空目录清理策略（§61）。
- 完成后可发布 CLI/API 完整版 v1.0。

### 阶段 III：人工处理闭环（Phase 21.x）

- 人工元数据修正全流程（§31、§81）：修改关键词、年份、Movie/TV 切换、
  直接输入 Provider ID；保持决策持久化 + 显式 resume 语义。
- 未识别媒体人工指定 RecognitionType（§80）。
- 批量操作体系（§83）。
- 文件列表/搜索筛选/媒体详情页（§94–§96），含重新识别/重新匹配/重新生成 Plan。

### 阶段 IV：配置管理系统（Phase 22.x，剩余最大块）

- Phase 22.0 前置架构决策（必须先做）：配置存储选型（JSON vs SQLite）、
  凭证加密存储方案（§99）、外部 Secret Store 边界、用户体系/OIDC 评估
  （不在核心自建弱认证）。
- 12 类配置对象 CRUD（§86–§87）分批实现。
- 配置引用关系检查（§88）与导入导出（§89）。
- 存储管理界面（§5）与策略测试工具 Web 化（§84–§85）。
- 配置修改 Before/After 审计（§101）。

### 阶段 V：系统完善与正式发布（Phase 23.x）

- 系统设置界面（§97）、定时缓存/日志清理（§98）、Dashboard 完整指标（§93）。
- 静态类型检查引入、跨平台最终验收、发布文档。

### 执行约束

1. 严格按阶段顺序：阶段 I 有界硬门已关闭；现在先完成阶段 II，再进入阶段 III/IV。
2. 每个 Phase 单一提交粒度，沿用既有验收记录风格（PASS/测试计数/审计）。
3. 实机验收发现的问题只记录，不在验收 Phase 同一提交中修复。
4. 持续安全基线不变：默认 DryRun、不覆盖、不静默删除、仅 OrganizerExecutor
   执行变更、凭证只来自环境或未来 Secret Store、RecognitionType C 身份保持。
5. 无人值守定时 organize --execute 仍不支持。

## 下一步实施建议

后续任务仍应保持小步推进。优先顺序：

1. 进入 Phase 20.6，实现默认关闭、严格有界的安全空目录清理。
2. 保持历史/崩溃恢复与 Hash 持久复用为后续独立边界。
3. AWS S3/Cloudflare R2、多小时 soak、服务/主机终止仍作为部署专项验收，不阻塞有界 Phase 19 profile。
4. Phase 20 收口前不启动 Phase 21/22 的 UI 与配置管理扩展。

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
