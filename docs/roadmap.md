# MediaFlow 总体实施计划

## Phase Gate

流程与关闭规则仅以 [development-workflow.md](development-workflow.md) 为准；本文件只记录
Phase gate，不复制测试日志或流程正文。

| Gate | Status | Commit SHA | High Audit / Next boundary |
|---|---|---|---|
| Phase 22.4 Recognition integration Slice | PASS / CLOSED | `d95ea2b64a6fce559341d7eb5824977e07794dff` | PASS；已推送 `origin/main`；允许 Phase 22.5 reconstruction |
| Phase 22.5 recovered integration checkpoint | PASS / CLOSED | `d68a19ddd4bb62bc27e77bab013edb20c9eb53e5` | PASS — SAFE TO INTEGRATE；已推送 `origin/main`；不扩大下文产品边界 |
| Development Workflow Git Capability Gate | PASS / CLOSED | `9777ee187972d53f02f6f30d7682535b03f2b447` | PASS；已推送 `origin/main`；不重新打开 |
| Phase 22.5-C Candidate Confirmation | PASS / CLOSED | `d68a19ddd4bb62bc27e77bab013edb20c9eb53e5` | PASS；允许 Phase 22.5-D same-Provider correction test |
| Phase 22.5-D Managed Live Metadata Correction Test | PASS / CLOSED | `55769be58a75596461879994560a0c58c3a7c9dc` | PASS；允许 Phase 22.5-E 单项 Metadata correction DryRun continuation；Provider switching 仍后置 |
| Phase 22.5-E Single-Item Metadata Correction DryRun Continuation | PASS / CLOSED | `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` | PASS — 2026-08-27，F1 correction checkpoint 独立复审通过；被拒 checkpoint `08dfd4f921728755209b6d52347d28f221121c47`（FIX REQUIRED）保留 |
| Phase 22.5 Metadata 配置与修正旅程（A/B/C/D/E） | PASS / CLOSED | `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` | PASS — 2026-08-27 phase-level Final Closure Audit；已推送 `origin/main`；允许 Phase 22.6 Naming/Classification/Organize 配置旅程 |
| Phase 22.6-A Managed NamingPolicy + Offline Naming Preview | PASS / CLOSED | `30af69ac82b30f8a45ad66afbd3c9747597c8fe7`；被拒 checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` 保留 | PASS — 2026-08-28 独立复审：五项 operator-UI 与两项 service-boundary 可证伪对照全部先失败后通过，生产树与被拒 checkpoint 逐字节相同；下一合法 Slice 为 Phase 22.6-B |
| Phase 22.6-B Managed ClassificationPolicy + Offline Classification Preview | 未开始 | — | 已在 `TASK.md` 定义：managed classificationPolicies CRUD、MediaLibrary 引用校验、RecognitionTypePolicy 引用阻断与 exact-revision 离线分类预览；不含 OrganizePolicy、组合目标路径、冲突/能力预检与 activation evidence 变更 |

## 当前节点

截至 2026-08-27，项目完成了安全优先的核心执行链、Phase 21 有界人工/文件管理基础、
Phase 22.1 内部 Storage 配置 CRUD 基础、Phase 22.2 whole-document Active authority，以及
Phase 22.3 Local Storage + Library guided journey。Phase 22.3 的全部 correction slices 和
phase-level Final Closure Audit 均为 **PASS / CLOSED**；Phase 22.4 Recognition Configuration +
Strategy Test 也已在 F2 恢复指导修复后独立验收 **PASS / CLOSED**。Phase 22.5 Metadata 配置与
修正旅程的全部 Slice（22.5-A offline resolution preview、22.5-B live Metadata test + F1、
22.5-C candidate confirmation + F1/F2、22.5-D same-Provider correction test 及其 correction、
22.5-E 单项 Metadata correction DryRun continuation + F1）均已独立 High PASS；其中 22.5-E 的
首个 checkpoint `08dfd4f921728755209b6d52347d28f221121c47` 曾被判定 **FIX REQUIRED**（Files
detail Web continuation section 未挂载到 DOM），该记录保留不改写，F1 correction checkpoint
`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已挂载该 section 并补齐可失效 Web 回归证据，于
2026-08-27 通过独立 High re-review。同日 phase-level Final Closure Audit 判定 Phase 22.5
**PASS / CLOSED**。下一合法边界是 Phase 22.6 Naming / Classification / Organize 配置与离线
预览旅程，起始 Slice 为 Phase 22.6-A；Provider switching、通用 Task resume 与更宽的逐项
checkpoint 恢复仍为 TARGET。`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 在显式
操作员授权下推送到 `origin/main`，Phase 22.5 的收口 push gate 已满足。
Phase 22.6-A 首个 checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` 已于 2026-08-27
独立审核判定 **FIX REQUIRED**：NamingPolicy Managed Draft CRUD、引用阻断、exact-revision 零变更
离线命名预览与零 Storage/Provider 证据均已验证通过，但 Web 端 `renderNamingPreview` 挂载缺少可
失效回归（删除挂载行后 810 项离线测试仍全绿），且 invalid template 仅通过私有 `_normalize`
验证，未在 service/API 边界证明 "Draft unchanged" 与"修正模板后预览成功"。该记录与被拒 SHA 保留
不改写。当前唯一合法 Slice 是 Phase 22.6-A-F1 correction（仅补测试与文档，不改产品行为）；
Phase 22.6 尚未关闭，Phase 22.6-B ClassificationPolicy 编辑与目标解析预览、目标冲突/能力预检和
activation evidence 不得提前开始。
Phase 22.6-A-F1 correction checkpoint `30af69ac82b30f8a45ad66afbd3c9747597c8fe7` 已于
2026-08-28 通过独立 High re-review，Phase 22.6-A 判定 **PASS / CLOSED**。复审独立复现了可证伪
性：删除 preview 挂载、删除 NamingPolicy list 挂载、把 preview 挂载移到 `detail.hidden = false;`
之后、把 preview 控件与标题从 `detailContent` 脱挂，五项 operator-UI 对照全部失败；`_normalize`
接受空模板与渲染器接受路径分隔符两项 service-boundary 对照亦全部失败，未改动树全部通过。
`git diff 90ce13a 30af69a` 仅触及测试与文档，`mediaflow/`、`scripts/`、`config/` 与
`pyproject.toml` 逐字节相同，产品行为、API 契约、evidence key、schema marker 与 activation
语义均未变化。Phase 22.6 尚未关闭：下一合法 Slice 是 **Phase 22.6-B**（managed
ClassificationPolicy 编辑 + exact-revision 离线分类预览）；OrganizePolicy 编辑、组合最终目标
路径预览、目标冲突/能力/存在性预检与 combined activation evidence 仍为 TARGET，不得提前开始。
本次 Product/UX Rebaseline 明确：内部模块完成不等于
最终产品完成，后续按 `docs/product-experience.md` 的纵向用户旅程验收。

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
| Recognition | 已完成当前配置旅程 | 引擎、Web 规则配置、优先级/引用校验、持久 Strategy Test 解释/恢复、C 身份保持、人工决策和重评请求 | 后续按真实样本扩展，不作为当前 blocker |
| Metadata | 部分完成（引擎成熟） | TMDB、缓存、候选评分、本地化标题、年份语义、持久人工候选/查询修正 | Provider 切换、配置激活、同页恢复闭环 |
| Naming | Phase 22.6-A PASS / CLOSED | 安全模板、Unicode、多集、Managed Draft 编辑、引用影响与 exact-revision 离线预览（含可证伪 Web 挂载回归） | Classification/Organize 联动和 activation evidence |
| Classification | 已完成 | 确定性规则、媒体库选择、持久人工规则选择/恢复 | 自由路径修正明确禁止；完整 UI 待做 |
| Planner/Executor | 部分完成 | 计划、冲突、附件、Hash 证据、同次调用 Rollback、空目录清理、DryRun、跨存储执行 | 历史/崩溃恢复、Hash 持久复用、逐项恢复体验 |
| Task/History | 部分完成 | 持久 Task/Item/Result/Job、Worker、取消、pause/resume、批量请求、claim fencing/心跳 | 统一 Processing Checkpoint 与 stage-aware recovery |
| API/UI/Scheduler | 部分完成 | API/RBAC/审计、操作台、Dashboard、Files 列表/筛选/详情/部分动作、Cron/通知 | 完整人工/配置/恢复旅程、登录/外部身份源 |
| Managed Configuration | Phase 22.3/22.4/22.5 与 Phase 22.6-A 均 PASS / CLOSED | 既有能力加 NamingPolicy CRUD、引用阻断与 exact-revision 离线命名预览 | ClassificationPolicy 编辑与离线分类预览（Phase 22.6-B，进行中边界）、OrganizePolicy、冲突/能力预检与 combined activation evidence；Provider switching/通用 Task resume 后置 |

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

## 规格差距评估（2026-08-24，基于 Phase 22.2R 与 Product/UX Rebaseline）

对照《影视媒体资源自动整理系统需求规格说明书》V1.1 全量章节逐项评估：

| 领域 | 当前状态 | 主要剩余缺口 |
|---|---|---|
| 核心引擎（§1–§79） | 引擎成熟、产品闭环部分完成 | 历史/崩溃恢复、Hash 持久复用、Provider 切换与完整人工整理旅程 |
| 存储层（§4–§10） | 有界发布矩阵 PASS | AWS/R2、第三方 driver、远端原子发布、Range Read/大对象服务端 Copy 仍未认证或未实现 |
| 任务与自动化（§62–§70、§98） | 持久基础成熟、恢复体验不完整 | 统一 Processing Checkpoint、stage-aware 逐项恢复、定时缓存/日志清理 |
| API 与 Web UI（§93–§96、§102） | 有界操作台/文件视图/部分动作已实现；配置快照恢复管理已接入 | 决策→继续→结果/逐项恢复闭环、对象级配置管理、手工整理和 Provider 切换 |
| 配置管理（§5、§86–§89） | Phase 22.2/22.2R whole-document Draft/Validated/Active 及恢复安全边界 | 对象级 Storage/Library/Policy CRUD、依赖影响、连通性测试、Secret Store、完整首次设置旅程 |
| 安全与审计（§99–§101） | RBAC/脱敏/执行审计成熟 | 用户/外部身份源决策、完整配置激活审计与逐项恢复审计 |

从本次重基线开始，不再用“模块百分比”作为产品完成度。MediaFlow 的核心媒体引擎接近完整，
但最终 V1 仍缺少配置、恢复和人工处理的完整 Web 用户旅程；内部仓储或命令通过不能提高这些
旅程的完成状态。

## 历史阶段完成状态

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

### 阶段 II：核心引擎收口（Phase 20.x，已完成有界范围）

- Phase 20.1 NFO Parser 已完成：Storage-only 有界读取、安全 XML、确定性证据合并和生产管线接入。
- Phase 20.2 Hash 重复检测已完成：不计算/快速/完整，默认不计算；证据只读且失败闭合。
- 有界整理 Rollback 已完成：只补偿同次调用记录且再次验证的效果，不触碰未知文件；历史/崩溃恢复不在该边界（§49、§69）。
- 任务暂停/继续语义（§66）与只读工作流有界自动重试（§79）已完成；变更操作和不确定结果明确不自动重试。
- Phase 20.6 空目录清理已完成：默认关闭、成功 MOVE 后、ResourceLibrary 根排他边界、未知内容失败闭合。
- 完成后可发布 CLI/API 完整版 v1.0。

### 阶段 III：人工处理基础（Phase 21.x，已完成有界范围）

- Phase 21.0 已完成：Unrecognized 条目持久等待、启用类型有界快照、显式 RecognitionType
  决策审计和 resume；无隐藏默认、不修改规则，C 身份保持。
- Phase 21.1 已完成：Metadata NOT_FOUND 条目持久等待，支持关键词、年份、Movie/TV、
  配置 Provider 的直接 ID 修正，保持决策审计 + 显式 resume 和 C 身份。
- Phase 21.2 已完成：Recognition/Metadata 人工等待项支持显式、持久、可审计的单项忽略；
  ignored 不计成功且不触碰媒体、索引、规则或未来扫描。
- Phase 21.3 已完成：Unrecognized 等待项可在外部规则更新后显式请求重新识别，再由独立
  Task resume 使用当前配置重跑真实引擎；无隐藏默认或规则写入。
- Phase 21.4 已完成：有界、可审计、可选的 Task 范围批量请求重新识别；pending Recognition
  Review 与匹配 WAITING_RECOGNITION 项在同一事务中最先到期优先处理，仍由独立 Task resume
  使用当前配置重跑真实引擎；无隐藏默认或规则写入。
- Phase 21.5 已完成：有界、可审计、可选的 Task 范围批量忽略；Recognition、Metadata 候选和
  Metadata NOT_FOUND 修正等待项在同一事务中最先到期优先标记为 IGNORED，仍不触碰媒体、索引、
  规则或未来扫描。
- Phase 21.6 已完成：有界、可审计、可选的 Task 范围批量人工 RecognitionType 决策；pending
  RecognitionReview 与匹配 WAITING_RECOGNITION 项在同一事务中最先到期优先以同一启用类型
  RESOLVED，仍由显式 resume 消费持久 selection；无隐藏默认、不修改规则，C 身份保持。
- Phase 21.7 已完成：有界、可审计、可选的 Task 范围批量 Metadata NOT_FOUND 修正；pending
  MetadataCorrectionReview 与匹配 WAITING_METADATA_CORRECTION 项在同一事务中最先到期优先以
  同一合法 query/year/movie-TV/provider-ID 输入 RESOLVED，仍由显式 resume 消费持久 correction；
  C 身份保持。
- Phase 21.8 已完成：有界、可审计、可选的 Task 范围批量 Metadata 候选选择；pending
  MetadataReview 与匹配 WAITING_METADATA 项在同一事务中最先到期优先以同一持久候选 rank
  RESOLVED，仍由显式 resume 消费持久 MetadataSelection；C 身份保持。
- Phase 21.9 已完成：有界只读 FileIndex 文件目录 CLI；可按 ResourceLibrary、Storage、
  scan status 与 path/filename 查询，稳定排序并显示单项索引记录；不构造 Storage/Provider/
  工作流，也不读取文件内容。
- Phase 21.10 已完成：同一文件目录支持稳定 keyset cursor 分页；`--after/--before` 配合
  `--cursor-file-id` 使用既有 `(updated_at DESC, file_id DESC)` 顺序，不使用 OFFSET。
- Phase 21.11 已完成：`files show` 为索引文件追加最新持久 Task Result 详情；缺失结果显式
  显示为空，不伪造历史，也不构造 Storage/Provider/工作流。
- Phase 21.12 已完成：`files list` 增加 RecognitionType、Provider、Provider ID、Title、
  Task ID 与 Year 的派生过滤；基于同一 source Storage/path 的最新 Task Result，且仍为只读
  有界 FileIndex 查询。
- Phase 21.13 已完成：FileIndex 文件目录基础过滤、cursor 和 limit 下沉到参数化仓储查询；
  应用层只保留最新 Task Result 派生过滤。
- Phase 21.14 已完成：最新 Task Result 派生过滤也已下沉为 FileIndex 与 TaskResult 的
  参数化 join，SQLite 路径不再逐文件查询最新结果。
- Phase 21.15 已完成：有界批量失败项重试请求；FAILED/PARTIAL TaskItem 可在同一事务中原子
  回到 PENDING，并由显式 `tasks resume` 执行真正的重试。
- Phase 21.16 已完成：`files stats` 提供有界只读 FileIndex 状态统计，可按 ResourceLibrary
  与 Storage 过滤；不构造 Storage/Provider/工作流。
- Phase 21.17 已完成：文件目录只读 Web UI；认证 API 提供 list/detail/stats，操作台 Files
  视图支持有界列表与详情查看，不提供写入或执行操作。
- Phase 21.18 已完成：Files 视图增加只读搜索/筛选控件，可组合 ResourceLibrary、Storage、
  scan status、path/filename、Recognition/Provider/Title/Task/Year 过滤。
- Phase 21.19 已完成：显式 `batch preview` / `batch organize` 命令复用无路径全
  ResourceLibrary 管线，明确批量 DryRun/整理入口。
- Phase 21.20 已完成：`files show`/Web 详情返回同一 source Storage/path 的关联
  Recognition/Metadata review 链接，操作员可跳转到对应 Task/复核队列；只读不修改。
- Phase 21.21 已完成：`files re-recognize` 为存在 pending RecognitionReview 的文件发起
  重新识别请求；真正重评仍由 `tasks resume` 执行。
- Phase 21.22 已完成：`files re-match` 为存在 pending MetadataCorrectionReview 的文件执行
  有界 Metadata 修正/重新匹配；真正 Provider 查找仍由 `tasks resume` 执行。
- Phase 21.23 已完成：`files re-plan` 为最新 FAILED/PARTIAL 结果的文件发起单项重试请求，
  原子返回 PENDING；真正重新规划/整理仍由 `tasks resume` 执行。
- Phase 21.24 已完成：Phase 21 收口 smoke test 与文档一致性核对；CLI/UI 只读边界和
  禁止依赖审计保持通过。
- Phase 21.25 已完成：Files 详情 Web UI/API 增加 re-recognize 与 re-plan 请求入口；仅在
  对应 pending review 或 FAILED/PARTIAL 状态显示，实际执行仍需显式 Task resume。
- Phase 21.26 已完成：补齐 file re-match 的 Web UI/API；Phase 21 已按当前有界范围收尾，
  下一阶段进入 Phase 22 配置管理系统。
- Phase 22.0 已完成：配置管理架构决策与领域骨架；JSON 作为运行时输入、SQLite 作为变更/
  审计存储、凭证保持环境或 Secret Store 归属，12+ 配置对象分类与引用/审计模型已建立。
- Phase 22.1 已完成：第一批 Storage 配置内部 CRUD/校验/乐观版本/Before-After 审计与
  SQLite 引用阻断；支持六类 Storage 形状并拒绝字面/嵌套 secret。该入口尚未接入运行时
  JSON、API/UI/CLI、Storage 构造或媒体工作流。
- Phase 22.3 已完成并通过 Final Closure Audit：在 Managed Draft 中接入 Local Storage、
  ResourceLibrary、MediaLibrary 的 Web/API 编辑、完整直接引用影响/阻断、远端脱敏只读、
  host-absolute/Storage-relative 路径边界、容量和超时受限的只读 Local setup check、持久失败/
  陈旧恢复、checked activation，以及行为可辨的 Preview Job → Worker → Task/Result immutable
  snapshot pin。远端 Storage 与策略对象不属于该已关闭 scope。

Phase 21 的上述条目是可复用的持久/API/Web 基础，不代表最终人工处理用户旅程已经完成。

## Product/UX 纵向实施路线（当前有效）

后续不再采用“先完成所有 Domain/Repository，再统一补 API/UI”的横向排期。一个配置切片在
适用时应包含：

```text
Domain
→ persistence
→ Application
→ API
→ Web UI
→ validation / test
→ activation
→ user acceptance tests
```

每个切片都必须明确用户目标、入口、可见状态、动作、成功、失败与恢复；若只完成其中一段，
报告必须明确仍是 CURRENT 基础而不是产品完成。

### 1. 架构纠正与引擎正确性

- Phase 22.2/22.2R 已建立 whole-document Managed Configuration 的 Draft → Validate → Activate →
  immutable Runtime Snapshot 单一权威链路，并补齐缺失/损坏 Active 的管理恢复与 fail-closed
  工作边界；后续切片必须沿用该 authority。
- Web/API 显示的 Active 必须与新 Task/Job 实际固定并消费的 snapshot ID/digest 一致；在途项目
  不被静默切换。
- JSON 只保留明确的 bootstrap/import/export/migration 角色；首次激活前标记 CURRENT
  `JSON_BOOTSTRAP`，激活后不得制造两个 Active source。
- 定义 TaskItem Processing Checkpoint 与 stage-aware Recovery 的兼容契约，但恢复旅程在第 6
  个切片实现，不在架构纠正中假装完成。

### 2. Storage + Library 配置用户旅程（Phase 22.3，PASS / CLOSED）

- 已修复独立复核确认的 P1：大段编辑不得截断丢失、Local root 必须是 host-absolute、
  Web 必须展示直接引用与陈旧/失败 check 恢复证据、setup check 必须容量受限且受
  fail-fast read-only guard 保护，并补齐 Active → Job → Worker Task/Result 同 pin 验收。
- 2026-08-25 phase-level Final Closure Audit 未发现组合 scope 内 P0/P1；远端 Storage 连通性与
  能力测试仍是后续范围。
- 复用 Phase 22.1 基础，不把“补齐 Library repository”单独作为产品完成。

### 3. Recognition 配置 + Strategy Test 用户旅程（Phase 22.4，PASS / CLOSED）

- 规则/类型/类型策略的编辑、优先级与引用校验、真实或合成路径的零变更 Strategy Test、解释、
  激活和 C 身份回归在同一切片交付。
- 2026-08-26 独立验收确认 matched/ambiguous/unrecognized 的持久证据、Web 解释和差异化恢复，
  以及 Local check + Strategy Test 双证据激活门；当前范围无 P0/P1。

### 4. Metadata 配置与修正用户旅程（Phase 22.5，PASS / CLOSED）

- Provider/MetadataPolicy 配置、语言/地区/阈值测试、候选解释、Provider 切换、人工修正、显式
  继续与新 Preview 形成闭环；凭证仍只来自批准的 Secret 边界。
- Phase 22.5-A 已完成 MetadataPolicy Managed CRUD、引用保护、精确 revision 的离线有效策略
  展示与 stale 恢复，并于 2026-08-26 独立验收 PASS/CLOSED。Phase 22.5-B 随后完成同一
  Validated revision 的有界 live Metadata 测试、候选/失败解释及 F1 修复，并已独立验收。
  Phase 22.5-C 已完成 persisted NeedConfirm/Ambiguous 候选确认及 F1/F2 durable CAS 修复并
  通过 final Integration Acceptance。Phase 22.5-D 的同 Provider query/year/Movie-TV/direct-ID
  correction test 已通过独立 High re-review 并 PASS/CLOSED；不包含 Provider switching、
  Files/Task continuation 或真实媒体变更。Phase 22.5-E 补齐一个已解决 correction 的显式单项
  DryRun continuation：Files detail 展示 source Task/TaskItem、correction 身份、固定 snapshot
  ID/digest、`Items selected: 1`、`Authority: DRY_RUN_ONLY`、`Storage mutation: NONE`，显式
  确认后生成一项不可执行 Job，并提供 queued/running/completed/failed/stale/cancelled 状态、
  有界失败/恢复文本、关联 Job 与 DryRun Task/Result、单项重试和显式 stale requeue。其首个
  checkpoint 因 Web section 未挂载被判定 FIX REQUIRED（记录保留），F1 correction checkpoint
  `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 独立复审通过。
- 2026-08-27 phase-level Final Closure Audit 判定 Phase 22.5 **PASS / CLOSED**，组合 scope 内
  无 P0/P1。Provider switching、通用 Task resume 与更宽的逐项 checkpoint 恢复仍为 TARGET，
  分别不在该已关闭 scope 内。

### 5. Naming / Classification / Organize 配置用户旅程（Phase 22.6，当前边界）

- 模板、分类规则、目标 MediaLibrary 与操作策略联动编辑；显示依赖影响，使用相同引擎预览，
  验证路径安全/冲突/能力后才允许激活。
- Phase 22.6 目标：把 NamingPolicy、ClassificationPolicy、OrganizePolicy 纳入既有 Managed
  Configuration 权威链路（Draft → Validate → checked Activate → immutable Runtime Snapshot），
  并对精确 revision 提供零变更的离线预览与可操作恢复。
- Phase 22.6 边界：沿用 whole-document revision authority、乐观版本、引用影响/阻断、
  Before/After 审计与 host-absolute/Storage-relative 路径规则；预览必须消费被指定的精确
  revision 而不是当前 Active，且不构造 Provider、不访问 Storage、不产生媒体变更。
- Phase 22.6 起始 Slice 22.6-A（managed NamingPolicy CRUD + 精确 revision 离线命名预览）已
  **PASS / CLOSED**（`30af69ac82b30f8a45ad66afbd3c9747597c8fe7`）。当前 Slice 是 22.6-B
  （managed ClassificationPolicy CRUD + 精确 revision 离线分类预览，含 MediaLibrary 引用校验与
  RecognitionTypePolicy 引用阻断）；OrganizePolicy 对象、组合最终目标路径、冲突与能力预检、
  激活门在后续 Slice 交付，均不授予 execute 权限。
- 明确不在 Phase 22.6 范围：Provider switching、通用 Task resume、逐项 Processing Checkpoint
  恢复（第 6 项）、手工整理旅程（第 7 项）、无人值守 `organize --execute`。

### 6. 批处理逐项恢复

- 建立 Task → TaskItem → Processing Checkpoint → stage-aware Recovery Strategy，并在 Web/API
  提供每项的已知效果、重试安全性和有效恢复动作；成功兄弟项永不重放。

### 7. Files / Media 详情与手工整理

- 在现有文件列表/筛选/详情基础上补齐端到端解释、历史、复核、手工 Preview/Organize 和恢复
  跳转；用户无需拼接内部 Task/Review 命令。

### 8. 自动化与最终生产加固

- 完善定时维护、Dashboard 指标、跨平台/多小时/云服务专项验收、静态类型检查与发布文档。
- 是否开放无人值守 `organize --execute` 必须另行完成权限、恢复、幂等和安全验收；当前仍禁止。

### 执行约束

1. 严格按上述优先顺序推进；不得跳回“所有 Repository 先做完、API/UI 最后补”的横向路线。
2. 每个 Phase 保持单一可验收用户切片和提交粒度，沿用 PASS/测试计数/审计证据风格。
3. User acceptance 必须覆盖成功、可操作失败、恢复、并发/陈旧状态及适用的零 mutation。
4. 实机验收遵循 `docs/storage-acceptance.md`，不得使用生产数据或凭证。
5. 持续安全基线与引擎边界不因 UX 工作而放宽。

## 下一步实施建议

Phase 22.2R-F1 独立验收曾给出 **FIX REQUIRED**；Phase 22.2R-F2 已于 2026-08-24 通过独立验收。
resident API 使用不可变 request-scoped binding 绑定 snapshot identity、队列/execute 准入和配置
派生视图；Worker 对缺失、不可读、digest 损坏、schema 不支持和 runtime-invalid 的 saved
revision 持久化可操作且脱敏的失败证据。独立复核的 11 项关键回归和 708 项完整离线
套件无失败，本 Task 范围内无 P0/P1 偏离。

Phase 22.3、Phase 22.4 与 Phase 22.5（A/B/C/D/E 及其全部 correction）的独立验收已全部通过。
Phase 22.5-E 的首个实现 checkpoint 曾被判定 **FIX REQUIRED**，该记录与被拒 SHA 保留不改写；
correction checkpoint `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 通过独立 High
re-review，同日 phase-level Final Closure Audit 判定 Phase 22.5 **PASS / CLOSED**。
Phase 22.6-A（含被拒 checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` 与其保留记录）已于
2026-08-28 在 correction checkpoint `30af69ac82b30f8a45ad66afbd3c9747597c8fe7` 通过独立 High
re-review，判定 **PASS / CLOSED**。下一正式 Task 是 **Phase 22.6-B — Managed ClassificationPolicy
Configuration + Offline Classification Preview**；`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`
已推送 `origin/main`，Phase 22.6 的实现不受 push gate 阻塞。不得借此提前开展 Provider switching、通用 Task resume、兄弟项重放、
逐项 Processing Checkpoint 恢复或
更宽的自动化。Interval/Cron 仍只允许 scan/preview；
无人值守定时 `organize --execute` 继续不支持。

## 持续安全基线

- 默认 DryRun；真实变更必须显式授权。
- 不覆盖已存在目标，不静默删除源或未知文件。
- 只有 OrganizerExecutor 可以调用 Storage mutation。
- 同存储操作优先原生能力；跨存储 Move 必须 Copy→校验→Delete。
- 任何回退必须由策略显式配置，不得改变操作语义。
- 凭证仅来自环境或未来 Secret Store，不进入配置导出、日志和历史。
- RecognitionType C 复用 A 下游策略时仍必须保持 C。
