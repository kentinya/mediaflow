# 影视媒体资源自动整理系统需求规格说明书

**文档版本：V1.1（工程需求基线）**
**项目类型：影视媒体资源管理 / 自动整理系统**

> 当前实现状态与最终产品范围以根目录
> [《影视媒体资源自动整理系统需求规格说明书》](../影视媒体资源自动整理系统需求规格说明书.md)
> 为准；规范化用户旅程见 [product-experience.md](product-experience.md)，分阶段交付计划见
> [roadmap.md](roadmap.md)，当前大 Slice Contract 见 [SLICE.md](../SLICE.md)。Slice/Task 生命周期、
> A/B/Developer、测试分级、commit、review 与关闭规则仅以
> [development-workflow.md](development-workflow.md) 为准，本需求文档不定义流程。
> 截至 2026-08-24，核心 CLI、持久任务、
> 目标冲突确认、元数据/分类复核、可选附件文件集合和全 Storage JSON Runtime 已完成；
> 服务 API 已具备 RBAC、审计、凭证运维护栏；Web 已覆盖操作台、文件列表/筛选/详情、
> 复核与 Task/Job/Result 只读视图，以及 re-recognize/re-match/re-plan 等有界请求入口；
> 大型运行历史、调度审计与通知投递支持稳定有界的双向游标分页；运行日志具备默认关闭、
> 结构化脱敏持久化、显式保留清理，以及本地/API/Web 双向游标有界查询；
> SQLite Runtime 支持不覆盖的在线一致性备份与只读完整性/Schema 校验；安装 wheel 已由
> Python 3.11–3.13 只读 CI 和隔离产物冒烟验证保护；生产级身份源、TLS 终止、发布和部署
> 仍属于后续显式运维阶段。
> 升级前可对配置的 Runtime 数据库和显式新备份执行只读兼容性预检；预检不迁移、不恢复、
> 不替换数据库，也不能替代停机和回滚流程。
> 离线恢复仅能向不存在的配置 Runtime 路径原子创建已验证备份；任何已有数据库、目录、
> 符号链接或 SQLite sidecar 都会拒绝，旧数据必须由停机后的操作员手工保留。
> POSIX 生产命令通过 Runtime 路径派生的共享/独占内核锁协作；恢复遇到任一参与中的进程会
> 立即拒绝，但该机制不检测绕过生产 CLI 的程序，也不替代人工停机确认。
> 新版本可在显式备份的私有临时副本上演练真实 Schema 前向迁移并核对核心记录数量；演练
> 不打开或迁移生产 Runtime，也不等同于生产迁移和失败回滚。
> 操作台可读取 API 启动时生成的有界配置接线摘要；该摘要只显示安全 ID、类型、状态、计数及
> 策略引用，不显示路径、规则值、模板、端点、环境变量、凭证或任意适配器选项，也不提供编辑。
> 操作台对 Automation Job 的取消必须复用既有权限、审计和协作取消语义，并经过“请求取消”
> 与“确认取消”两个独立动作；取消不授予执行权限、不回滚已完成媒体操作，也不控制 Task。
> 操作台提交 Automation Job 只能选择 scan/preview，并经过打开、审核、确认三个阶段；请求只能
> 包含 command 和可选有界 limit，必须明确显示 DRY_RUN，不能携带 organize/execute 权限。
> Pending/Running Automation Job 总量必须由配置的持久原子准入上限约束；手工提交、Scheduler
> 和受保护 organize 共用容量，队列满不得消费执行票据、推进调度状态或删除现有 Job。
> Phase 19 有界生产发布 profile 已通过隔离 Local、Samba 4.20.6、OpenList v4.2.2 Local
> driver 和 MinIO S3-compatible 验收，包括 128 文件、128 MiB 流式对象与中断恢复。该结论
> 不认证 AWS S3、Cloudflare R2、第三方 OpenList driver、远端原子发布、多小时 soak、进程终止
> 或主机断电；精确证据与非声明边界见 [storage-acceptance.md](storage-acceptance.md)。随后完成的
> Phase 20.1 NFO Parser 通过 Storage 只读有界读取，安全 XML 解析后作为本地证据
> 合并，不生成 MediaIdentity、不访问网络且不修改 Storage。Phase 20.2 Hash 重复策略也已完成：
> 默认 NONE 零读取，FAST 为有界前缀证据，FULL 为受大小限制的完整流式证据；任何不确定结果
> 都进入冲突且不执行变更。Phase 20.3 已增加默认关闭、仅限同次调用已记录效果的有界
> Organizer Rollback。Phase 20.4 已增加持久、协作式 Task pause/resume；Phase 20.5 已增加
> 默认关闭、仅限执行前只读阶段规范化暂时错误的有界重试，且绝不自动重放 Organizer 变更或
> 不确定结果。Phase 20.6 已完成默认关闭、有界且未知内容失败闭合的安全源目录清理；Phase 21
> 已完成其有界人工复核、批量请求、文件目录与部分 Web 动作范围。Phase 22.1 已完成内部 Storage
> Managed Configuration CRUD 基础。Phase 22.2/22.2R-F2 已建立 whole-document Draft/Validated/Active
> Snapshot 的 API/Web/CLI 生命周期、原子激活、Task/Job 身份字段、fail-closed 运行时刷新、结构化
> 冲突和恢复基础。F2 将 API identity/admission/gate/status 收敛到同一不可变 binding，并为已保存
> Job revision 不可用提供可操作证据。2026-08-24 独立验收已 PASS/CLOSED。Phase 22.3 的
> Local Storage + ResourceLibrary + MediaLibrary Draft/API/Web、引用影响、只读 setup check、
> 失败恢复、checked activation 与行为可辨的 Preview Job → Worker → Task/Result immutable-pin
> 组合旅程，在逐项 correction 独立验收后于 2026-08-25 通过 Final Closure Audit，结论为
> **PASS / CLOSED**。先前的截断丢失、Local 绝对路径、Web 引用/陈旧失败证据、check
> 容量/异常安全和组合 pin P1 均已关闭。Phase 22.4 Recognition Configuration + Strategy Test
> 已于 2026-08-26 独立验收 PASS/CLOSED；Phase 22.5-A MetadataPolicy Managed Configuration +
> Offline Resolution Preview 随后也已独立验收 PASS/CLOSED。Phase 22.5-B Managed Live
> Metadata Test + Candidate Explanation 及 F1 修复也已独立验收；Phase 22.5-C candidate
> confirmation 及 F1/F2 durable CAS 修复已通过 final Integration Acceptance。Phase 22.5-D
> same-Provider managed live Metadata correction test 已于 2026-08-26 通过独立 High re-review
> 并 PASS/CLOSED。Phase 22.5-E 一个 resolved File correction 的显式 pinned DryRun continuation
> 的首个 checkpoint `08dfd4f921728755209b6d52347d28f221121c47` 曾被判定 FIX REQUIRED（Files
> detail Web section 未挂载），F1 correction checkpoint
> `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 通过独立 High re-review 并
> PASS/CLOSED；同日 phase-level Final Closure Audit 判定 Phase 22.5（A/B/C/D/E）
> **PASS / CLOSED**。远端 Storage、Provider switching 和通用 Task resume 仍为后续工作。
> Phase 22.6-A 至 22.6-N 的实现/证据 Slice 已分别通过独立 High Review；Phase 22.6 本身仍保持
> open，等待 CURRENT 文档同步 Slice 通过 High Review 后执行单独的 Final Closure Audit。

---

# UX 需求基线

以下稳定 ID 约束所有面向操作员的需求。详细旅程及 CURRENT/TARGET 解释由
`docs/product-experience.md` 统一定义，本节不复制其全文。

## UX-001 纵向用户完成

每个用户功能必须覆盖用户目标、入口、可见状态、可用动作、成功、失败和恢复。仅完成 Domain、
Repository、Application、迁移或内部测试不得标记操作员功能完成。

## UX-002 可操作失败

失败必须显示受影响项、阶段、稳定错误类别、已知副作用、重试安全性和明确恢复动作。仅提供
“Retry”按钮或原始异常文本不满足恢复要求。

## UX-003 逐项恢复

批处理必须为每个 TaskItem 保留独立状态、检查点、结果、已完成操作和恢复路径。成功项不得重放，
一个项目的决策不得改变另一个项目，未知真实执行结果不得自动重试。

## UX-004 运行时与配置一致性

界面显示 Active 的配置必须是运行时实际消费的不可变快照，并可识别其版本/摘要和激活时间。
Draft/Validated/Active 状态不得混淆；激活必须原子，失败时保留旧 Active。

## UX-005 可解释决策

Recognition、Metadata、Naming、Classification、Plan、冲突和执行决策必须提供有界、脱敏、
可审计的输入证据、匹配规则/评分和结果原因，不得仅展示最终值或隐藏默认。

## UX-006 变更前安全预览

任何可能修改媒体的操作必须先提供与实际计划一致的 Preview/DryRun，默认不覆盖、不删除、不
隐式回退；真实执行需要独立明确授权，且仅 OrganizerExecutor 可调用 Storage mutation。

## UX-007 Web/API 能力一致性

Web 是 V1 最终主要管理面。Web 与 API 对同一旅程必须复用相同 Application 行为、权限、校验、
并发控制、状态和审计。CLI-only 不能满足最终 Web 管理需求，但可继续承担管理、调试和自动化。

## UX-008 配置生命周期可见性

Web/API 必须显示 `JSON_BOOTSTRAP` 或 `MANAGED` authority，以及 Draft/Validated/Active revision
的版本、digest、验证/激活时间和有界错误。Active 只能表示已显式发布且运行时实际消费的快照。

## UX-009 配置激活安全性

导入、验证和激活不得访问媒体 Storage 或 Metadata Provider。激活必须原子、审计、并发安全，
陈旧或失效验证不得发布，失败保留旧 Active 和可修正 Draft；快照缺失/损坏必须 fail closed。

## UX-010 工作固定快照

新 Task/Job 必须记录创建边界解析出的 configuration snapshot ID/digest；在途工作不得因后续
激活而静默切换。DryRun/Preview 必须显示同一 pin，队列执行按该身份恢复。

---

# 1. 项目概述

## 1.1 项目目标

开发一套影视媒体资源自动整理系统，对本地、SMB、OpenList、R2/S3 等不同存储中的影视资源进行统一管理。

系统负责完成：

```text
配置存储
→ 配置资源库
→ 扫描资源
→ 解析文件名及路径
→ 判断识别类型
→ 根据识别类型策略连接 TMDB 等元数据服务
→ 确认影视作品
→ 根据命名规则生成标准名称
→ 根据分类规则确定目标媒体库及目录
→ 根据整理规则执行重命名、移动、复制或链接
→ 输出完整日志
→ 保存整理结果
```

系统应重点解决以下问题：

- 不同来源存储统一访问。
- 不同资源格式使用不同识别方式。
- 不同识别类型可以复用相同的命名规则。
- 不同识别类型可以复用相同的分类规则。
- 自动连接 TMDB 等网站确认影视作品。
- 自动规范文件及目录名称。
- 自动移动至正确的媒体库目录。
- 整理过程可预览、可追踪、可重试。
- 整理失败不得造成未知的数据丢失。

---

# 2. 核心设计原则

整个系统按照以下能力进行解耦：

```text
Storage
存储

Resource Library
资源库

Recognition Rule
识别规则

Recognition Type
识别类型

Recognition Type Policy
识别类型策略

Metadata Provider
元数据服务

Naming Policy
命名规则

Classification Policy
分类规则

Organize Policy
整理规则

Media Library
媒体库

Task
整理任务
```

核心关系：

```text
资源库中的文件
      ↓
本地解析
      ↓
识别规则
      ↓
识别类型
      ↓
识别类型策略
      ├── 元数据策略
      ├── 命名规则
      ├── 分类规则
      └── 整理规则
               ↓
          目标媒体库
```

其中必须遵循：

### 识别规则

只负责：

> 这个资源属于什么识别类型。

例如：

```text
文件 → C
```

---

### 元数据服务

负责：

> 这个资源具体是哪一部电影、电视剧、哪一季、哪一集。

例如：

```text
The.Matrix.1999.mkv
↓
TMDB
↓
The Matrix
1999
TMDB ID = xxxx
```

---

### 命名规则

只负责：

> 最终叫什么名字。

例如：

```text
The.Matrix.1999.1080p.mkv

↓

The Matrix (1999).mkv
```

---

### 分类规则

只负责：

> 最终放到哪里。

例如：

```text
/Media/Movies/
```

---

### 整理规则

只负责：

> 文件如何从资源库到达媒体库。

例如：

```text
Move
Copy
HardLink
SoftLink
```

---

# 3. 典型业务示例

系统存在：

```text
识别类型 A
识别类型 B
识别类型 C
```

配置：

```text
A
→ A 元数据策略
→ A 命名规则
→ A 分类规则
→ Move

B
→ B 元数据策略
→ B 命名规则
→ B 分类规则
→ Move

C
→ C 元数据策略
→ A 命名规则
→ A 分类规则
→ Move
```

注意：

```text
C 仍然是 C
```

只是 C 在整理阶段复用了 A 的：

```text
命名规则
+
分类规则
```

---

## 3.1 A 类型示例

源文件：

```text
/Downloads/A/The.Matrix.1999.1080p.BluRay.mkv
```

识别：

```text
RecognitionType = A
```

元数据识别：

```text
Title = The Matrix
Year = 1999
```

类型策略：

```text
A
→ A命名规则
→ A分类规则
```

最终：

```text
/Media/A/The Matrix (1999)/The Matrix (1999).mkv
```

---

## 3.2 B 类型示例

源文件：

```text
/Downloads/B/The.Last.of.Us.S01E03.2023.mkv
```

识别：

```text
RecognitionType = B
```

元数据：

```text
Title = The Last of Us
Season = 1
Episode = 3
```

策略：

```text
B
→ B命名规则
→ B分类规则
```

最终：

```text
/Media/B/The Last of Us/
└── Season 01/
    └── The Last of Us - S01E03.mkv
```

---

## 3.3 C 使用 A 规则示例

源文件：

```text
/Downloads/C/Special.C.2025.mkv
```

识别：

```text
RecognitionType = C
```

C 类型策略：

```text
C
→ A命名规则
→ A分类规则
```

最终：

```text
/Media/A/Special C (2025)/Special C (2025).mkv
```

最终媒体库：

```text
/Media/
├── A/
│   ├── The Matrix (1999)/
│   │   └── The Matrix (1999).mkv
│   │
│   └── Special C (2025)/
│       └── Special C (2025).mkv
│
└── B/
    └── The Last of Us/
        └── Season 01/
            └── The Last of Us - S01E03.mkv
```

---

# 4. 存储管理

## 4.1 功能要求

系统支持配置多个存储。

首期支持：

```text
Local
SMB
OpenList
Cloudflare R2
S3 Compatible
```

架构必须允许后续增加：

```text
WebDAV
SFTP
FTP
OSS
COS
其他云存储
```

---

# 5. 存储配置

每个存储拥有：

```text
Storage ID
名称
类型
启用状态
只读状态
根目录
超时时间
并发限制
备注
```

支持：

- 新增。
- 修改。
- 删除。
- 复制配置。
- 启用。
- 禁用。
- 测试连接。
- 测试读取。
- 测试写入。
- 查看连接状态。

---

# 6. 本地存储

配置：

```text
名称
Root Path
```

例如：

```text
/data/download
/data/media
```

系统启动或保存配置时可以检测：

```text
路径是否存在
是否可读取
是否可写入
```

同时由 Storage Adapter 声明其支持的文件操作能力。

---

# 7. SMB 存储

配置：

```text
名称
服务器
端口
共享目录
用户名
密码
Domain
Root Path
连接超时
```

支持：

```text
连接
目录扫描
读取
写入
创建目录
重命名
移动
复制
删除
```

认证信息必须加密保存。

日志不得输出明文密码。

---

# 8. OpenList 存储

配置：

```text
名称
OpenList URL
认证信息
Root Path
请求超时
```

通过独立 Storage Adapter 实现。

整理模块不得直接依赖 OpenList API。

---

# 9. R2 / S3 存储

配置：

```text
名称
Endpoint
Bucket
Region
AccessKey
SecretKey
Root Prefix
```

对象操作全部由 Storage Adapter 实现。

例如逻辑上的：

```text
Move
```

如果目标后端不存在直接移动能力，适配器可以按照对应存储能力组合适当操作实现。

上层整理引擎不关心底层实现细节。

---

# 10. Storage 抽象

建议统一接口：

```text
List()
Stat()
Exists()

Read()
Write()

CreateDirectory()

Rename()
Move()
Copy()
Delete()

HardLink()
SoftLink()
```

同时提供能力声明：

```text
CanRename
CanMove
CanCopy
CanDelete
CanHardLink
CanSoftLink
```

整理计划生成前必须进行能力检查。

---

# 11. 资源库

## 11.1 定义

资源库表示：

> 系统从哪里发现需要整理的媒体。

资源库必须绑定：

```text
Storage
+
Path
```

例如：

```text
资源库：下载完成
Storage：NAS
Path：/Downloads
```

---

## 11.2 资源库配置

配置：

```text
ResourceLibrary ID
名称
存储
根目录
启用状态

扫描方式
扫描深度

包含规则
排除规则

文件稳定策略

默认识别规则集合

备注
```

---

# 12. 资源扫描

支持：

```text
手动扫描
全量扫描
增量扫描
定时扫描
```

扫描发现媒体候选文件以后，不直接执行整理。

必须先进入：

```text
识别
→ 生成整理计划
→ 整理
```

---

# 13. 文件过滤

支持：

```text
扩展名
目录
文件名称
文件大小
Glob
正则表达式
```

可以配置视频扩展名：

```text
mkv
mp4
avi
mov
wmv
ts
m2ts
webm
iso
```

扩展名列表允许修改。

---

## 13.1 默认忽略文件

例如：

```text
*.tmp
*.part
*.download
*.!qB
```

允许用户配置。

---

# 14. 文件稳定性检测

防止处理正在：

```text
下载
复制
写入
```

的文件。

支持：

```text
最小文件年龄
最后更新时间阈值
文件大小稳定时间
```

例如：

```text
10分钟内文件大小没有变化
AND
最后修改超过5分钟

↓

允许进入识别
```

---

# 15. 媒体文件解析

系统首先对文件进行本地解析。

信息来源：

```text
文件名称
扩展名
父目录
上级目录
完整路径
NFO
已有整理信息
```

---

# 16. 文件名解析

需要解析：

```text
标题
原标题候选
年份

Season
Episode
Episodes

分辨率标签
来源标签
编码标签
音频标签

HDR标签
Dolby Vision标签

版本标签
发布组

语言标签
其他Release标签
```

例如：

```text
The.Last.of.Us.S01E03.2023.2160p.WEB-DL.H265.mkv
```

解析：

```text
TitleCandidate = The Last of Us
Year = 2023

Season = 1
Episode = 3

ResolutionTag = 2160p
SourceTag = WEB-DL
VideoCodecTag = H265
```

这些技术信息均属于：

> 文件名标签。

系统不需要检查视频内部实际媒体流参数。

---

# 17. 季集识别

支持常见形式：

```text
S01E01
S1E1
S01E01E02
S01E01-E03
1x01
EP01
E01
第01集
第1集
第01话
```

例如：

```text
S01E01E02
```

转换：

```text
Season = 1
Episodes = [1, 2]
```

---

# 18. 识别规则

## 18.1 定义

识别规则负责：

> 根据文件及目录特征判断资源属于哪个 RecognitionType。

识别规则本身不负责命名、分类和移动。

---

## 18.2 配置

每个识别规则包含：

```text
Rule ID
规则名称

启用状态
优先级

文件名条件
路径条件
目录条件
扩展名条件
关键词条件
正则条件
排除条件

输出 RecognitionType
```

---

## 18.3 条件关系

支持：

```text
AND
OR
NOT
```

例如：

```text
Path Contains "/C/"
AND
Extension IN ["mkv", "mp4"]

↓

RecognitionType = C
```

---

# 19. 识别规则优先级

规则按照：

```text
Priority DESC
```

执行。

支持：

```text
命中后停止
命中后继续
```

如果存在多个候选类型，可使用：

```text
规则优先级
+
匹配分数
```

确定最终 RecognitionType。

---

# 20. 识别类型

系统允许创建任意识别类型。

例如：

```text
A
B
C

Movie
TV
Anime
Documentary

自定义类型
```

识别类型主要用于：

> 将一类资源绑定到特定的后续处理策略。

---

# 21. 识别类型策略

## 21.1 定义

Recognition Type Policy 是系统核心配置。

负责定义：

> 一个文件被判断为某种识别类型后，接下来应该如何进行元数据识别、命名、分类和整理。

---

## 21.2 配置

每个识别类型策略包含：

```text
Policy ID
名称

RecognitionType

Metadata Policy
Naming Policy
Classification Policy
Organize Policy

启用状态
优先级
```

---

## 21.3 示例

```text
RecognitionType = A

MetadataPolicy = Movie-TMDB
NamingPolicy = Naming-A
ClassificationPolicy = Classification-A
OrganizePolicy = Move
```

B：

```text
RecognitionType = B

MetadataPolicy = TV-TMDB
NamingPolicy = Naming-B
ClassificationPolicy = Classification-B
OrganizePolicy = Move
```

C：

```text
RecognitionType = C

MetadataPolicy = Movie-TMDB
NamingPolicy = Naming-A
ClassificationPolicy = Classification-A
OrganizePolicy = Move
```

因此：

```text
A → A + A
B → B + B
C → A + A
```

完全成立。

---

# 22. 元数据服务

## 22.1 功能定位

Metadata Provider 用于：

> 根据本地解析得到的标题、年份、季、集等信息，识别对应的影视作品并补全标准元数据。

首期支持：

```text
TMDB
```

架构允许增加：

```text
其他公开影视元数据Provider
自定义Provider
```

---

# 23. 元数据 Provider 抽象

统一定义：

```text
SearchMovie()
GetMovie()

SearchTV()
GetTV()

GetSeason()
GetEpisode()

FindByExternalId()

GetImages()
```

不同 Provider 通过 Adapter 实现。

Media Identifier 不直接调用具体网站 API。

---

# 24. TMDB 配置

支持：

```text
名称
API认证信息

语言
地区

代理

连接超时
请求超时

并发数量

重试次数
重试间隔

缓存时间

启用状态
```

TMDB 当前的应用级 API 认证支持 v3 `api_key` 或 Bearer Token；官方文档将 Bearer Token 作为默认认证方式之一。citeturn441534search0

敏感认证信息必须：

```text
加密保存
接口脱敏
日志脱敏
```

---

# 25. 元数据策略

元数据服务本身和元数据策略分离。

例如系统配置一个：

```text
TMDB Provider
```

然后可以建立：

```text
Movie-TMDB
TV-TMDB
Anime-TMDB
```

三个不同 Metadata Policy。

---

## 25.1 Metadata Policy 配置

```text
名称

Provider

媒体查询类型
    Movie
    TV
    Auto
    None

语言
地区

搜索策略

自动匹配分数阈值
人工确认分数阈值

备用Provider
缓存策略
```

---

# 26. TMDB 电影识别

文件：

```text
The.Matrix.1999.1080p.BluRay.mkv
```

本地解析：

```text
TitleCandidate = The Matrix
Year = 1999
```

Metadata Policy：

```text
Movie-TMDB
```

查询：

```text
TMDB Movie Search
```

TMDB 官方提供独立的电影文本搜索接口，搜索可以使用标题，并可结合上映年份等条件缩小候选结果。citeturn441534search1turn441534search8

返回候选后进入：

```text
Candidate Matcher
```

而不是直接选择第一条结果。

---

# 27. TMDB 电视剧识别

例如：

```text
The.Last.of.Us.S01E03.2023.mkv
```

本地解析：

```text
TitleCandidate = The Last of Us
Year = 2023

Season = 1
Episode = 3
```

查询：

```text
TV Search
↓
TV Details
↓
Season
↓
Episode
```

TMDB 当前提供独立的 TV Search 以及 TV Series Details 接口，因此电影和电视剧应当在 Provider 层作为不同查询类型处理。citeturn441534search5turn441534search14

---

# 28. 外部 ID 识别

如果文件名、NFO 或已有数据库中存在：

```text
TMDB ID
IMDb ID
TVDB ID
其他支持的外部ID
```

应优先尝试 ID 定位。

TMDB 的 Find API 支持通过已有外部标识符寻找对应对象，因此 Metadata Provider 应保留 `FindByExternalId()` 能力。citeturn441534search3turn441534search9

---

# 29. 元数据候选评分

搜索结果不得默认直接使用第一项。

每一个结果需要评分。

评分因素：

```text
标题相似度
原标题相似度
别名相似度

年份匹配

Movie / TV 类型匹配

Season匹配
Episode匹配

路径信息
识别类型上下文
```

---

## 29.1 默认阈值

例如：

```text
Score >= 90
→ 自动确认

Score 70 - 89
→ 待人工确认

Score < 70
→ 识别失败
```

阈值允许配置。

---

# 30. 元数据识别结果

统一转换为内部：

```text
MediaIdentity
```

建议结构：

```text
Provider
ProviderID

MediaType

Title
OriginalTitle
AlternativeTitles

Year
ReleaseDate

Season
Episode
Episodes
EpisodeTitle

Overview

Genres
Countries
Languages

ExternalIDs

Poster
Backdrop

RecognitionType

Confidence
MatchedBy
```

---

# 31. 人工元数据识别

> 当前实现（Phase 21.1）：Task 跟踪的 Metadata `NOT_FOUND` 项进入持久
> `WAITING_METADATA_CORRECTION`，可审计地修正查询词、年份、Movie/TV，或输入当前配置
> Provider 的直接 ID；只有显式 Task resume 才重跑真实 Provider 流程。该实现不允许任意
> Provider 切换或注入 MediaIdentity，且保持 RecognitionType（包括 C）不变。

> 当前实现（Phase 22.5-E；已于 2026-08-27 通过独立 High re-review，PASS / CLOSED）：Files
> detail 可对一个已 `RESOLVED` 的
> Metadata correction 显示 source Task/TaskItem、correction version 与精确 snapshot ID/digest，
> 通过 API/Web 共用入口显式继续为单项 DryRun。该入口原子创建 continuation 与不可执行 Job；
> Worker 只重跑该 File 的 Parser → Recognition → TypePolicy → Metadata → Naming →
> Classification → Planner，并持久化新的 DryRun Task/Item/Result。Web 侧同时呈现
> queued/running/completed/failed/stale/cancelled 状态与下一步动作、有界失败与恢复文本、
> 关联 Job 与 DryRun Task/Result 入口、单项重试和显式 stale requeue。源文件、源 review、源
> Task 及兄弟项不变；Provider switching、通用 Task resume、执行和自动 continuation retry
> 仍未实现。

当自动识别失败时支持：

```text
修改搜索关键词
修改年份

切换 Movie / TV

重新搜索

查看候选结果

手动选择结果

直接输入 TMDB ID

重新识别
```

人工确认后保存：

```text
MediaIdentity
```

然后继续正常整理流程。

---

# 32. 元数据缓存

Metadata 请求必须支持缓存。

缓存类型：

```text
Search Result

Movie Details
TV Details

Season
Episode

External ID

Images
```

配置：

```text
缓存有效期
自动刷新
强制刷新
清除缓存
```

防止资源库每次扫描都重新请求元数据网站。

---

# 33. Provider 请求控制

必须支持：

```text
最大并发
请求节流

Timeout

Retry
指数退避

Proxy

429处理
```

TMDB 官方目前说明旧的固定限流机制已经停用，但仍存在保护服务的上限，并要求客户端正确处理 `429`；因此系统不能把某个固定 QPS 数值写死，应通过可配置节流和 `429` 重试机制实现。citeturn441534search2

---

# 34. 命名规则

## 34.1 定义

Naming Policy 只负责：

> 根据已经确定的 MediaIdentity 生成目录名和文件名。

命名规则独立存在，可以被多个 RecognitionType 复用。

---

# 35. 命名规则配置

包含：

```text
NamingPolicy ID
名称

目录模板
文件模板

字符清理规则

缺失变量处理

启用状态
```

> 当前实现（Phase 22.6-A 至 22.6-N 均已独立 PASS；Phase 级 Final Closure Audit 待执行）：NamingPolicy 已接入现有 Managed Draft 的
> Web/API 对象编辑、乐观版本、Before/After 审计和 RecognitionTypePolicy 引用阻断。操作员可对
> 精确 revision ID/version/digest 提交一个有界合成样本或由既有 Parser 解析的路径，并通过既有
> NamingPolicyRegistry/NamingPreviewService/安全 renderer/sanitizer 得到持久离线命名证据；证据
> 显示目录、文件名、应用策略、RecognitionType、清理、缺失变量决策、warning、失败类别和恢复
> 动作，Draft 变化后明确为 stale。该路径不构造 Storage/Provider/Task/Job 且零媒体变更。
> ClassificationPolicy 也已接入相同 Web/API 对象编辑、引用阻断和 exact-revision 离线预览；证据
> 显示 classified/unclassified、matched rule、匹配解释、MediaLibrary ID/解析状态、安全相对路径、
> warning、current/stale 和恢复动作。预览复用既有 ClassificationPolicyRegistry/
> ClassificationPreviewService，不构造 Storage/Provider 且不授予执行权限。OrganizePolicy 也已接入
> 相同 Web/API 对象编辑、`organize_policy:<id>` 引用阻断与仅接受 Move/Copy/HardLink/SoftLink 的
> 编辑限制（拒绝 `delete` 与 `create_directory`），其边界与 overwrite/conflictStrategy 交叉规则由
> 生产 loader 与 OrganizePolicy domain 拥有，因此 managed 编辑与 Active 快照不会产生分歧；操作员
> 可对精确 revision 指定一个 RecognitionType，经生产 `RecognitionTypePolicyResolver` 得到持久、
> 无秘密的组织授权解释（RecognitionTypePolicy/OrganizePolicy、操作、冲突策略、overwrite 与源目录
> delete 授权、附件/重复检测/rollback/源目录清理、所需 Storage 能力"声明而非探测"、显式"能力不支持
> 即失败、绝不静默回退"、破坏性告警、current/stale 与恢复动作），五类 policy resolution 失败均为可
> 操作解释；Phase 22.6-D 进一步以生产 resolver、Naming/Classification engine 和 Planner 共用的
> composition/path-safety helper 输出 exact-revision 组合目标及每项 owner，路径明确为 Storage-relative，
> C 身份保持，失败持久且可恢复。该路径不构造 Storage/Provider/Planner/Executor 且零媒体变更。
> Phase 22.6-E 在此之上新增仅限 Local 目标 Storage 的只读目标预检：目标 Storage adapter 由未经修改
> 的 revision document 构造，能力在包装前读取，全部探测经 `ReadOnlyStorageGuard` 子类执行并复用生产
> `OrganizePlanner.plan` 与 `ConflictResolver.apply_configured`，报告目标根存在性/是否目录、最深已
> 存在祖先、需创建目录列表、目标是否已存在、按配置 ConflictStrategy 的冲突投影，以及 declared-vs-
> required 能力比对（缺失即 `capability_gap`，显式无回退）。证据绑定精确 version/digest，记录
> `pathScope: storage_relative`、`sideEffects: none`、全零 mutation 计数与有界读操作，且不授予
> overwrite/delete/执行权限；Storage 错误、容量占用与超时均为有界类别加显式恢复动作。
> Phase 22.6-H 在同一只读预检中接受一个 RecognitionType 下的 1-8 个样本：每一样本独立校验与
> 组成并保留行级状态，全部样本必须路由到同一目标 Storage；复用生产 `OrganizePlanner.plan` 的
> `claimed_destinations` 检测跨样本目标碰撞（失败类别 `duplicate_destination`，碰撞行列出目标
> 与样本索引），样本路由到多个目标 Storage 时以 `multiple_destination_storages` 在任何探测前
> 拒绝；completed 证据聚合各样本最严重投影结果并新增 `sampleCount`、`items` 与 `collisions`，
> `capability_gap` 对 run-level verdict 具有优先级，否则选择最严重的非空投影结果；全部行均为
> ready 时 run-level verdict 为 `ready`，即使其他行均 ready，只要任一行缺少所需能力则为
> `capability_gap`。每行保留独立的目标、冲突、结果、失败与恢复证据，单样本请求与既有 evidence
> 不变。该双向 verdict 与统一行契约由 Phase 22.6-N checkpoint
> `5884905c2105cf8ff78ff10d1b872875045769d7` 验收固定。
> Phase 22.6 仍不包括远端 SMB/OpenList/S3 目标预检、写入式能力探测、一次请求内多个
> RecognitionType 或多个目标 Storage、`ConflictType.DUPLICATE_MEDIA`/已知媒体检测、附件预检、
> 绝对挂载路径展示与执行；Provider switching、通用 Task resume、逐项 Processing Checkpoint
> 恢复和无人值守 execute 同样仍为后续 TARGET。
> Phase 22.6-F 已把当前、completed 且非 `capability_gap` 的
> Local 目标预检证据纳入 checked activation；missing/stale/failed/capability-gap 均拒绝且给出恢复，
> remote-only 或无 MediaLibrary 文档明确为不适用，unchecked activation 不变。

---

# 36. 命名变量

基础变量：

```text
{title}
{original_title}

{year}

{season}
{episode}
{episodes}
{episode_title}

{provider}
{provider_id}

{resolution}
{source}
{video_codec}
{audio}
{hdr}
{version}
{release_group}

{ext}
```

其中：

```text
resolution
source
video_codec
audio
hdr
version
release_group
```

来源于文件名及路径解析结果。

---

# 37. 电影命名

规则：

```text
目录：
{title} ({year})

文件：
{title} ({year}).{ext}
```

结果：

```text
The Matrix (1999)/
└── The Matrix (1999).mkv
```

也可以：

```text
{title} ({year}) [tmdbid={provider_id}]
```

产生：

```text
The Matrix (1999) [tmdbid=xxx]/
```

---

# 38. 剧集命名

目录：

```text
{title} ({year})/Season {season:02}
```

文件：

```text
{title} - S{season:02}E{episode:02} - {episode_title}.{ext}
```

结果：

```text
The Last of Us (2023)/
└── Season 01/
    └── The Last of Us - S01E03 - Long, Long Time.mkv
```

---

# 39. 命名字段缺失处理

例如模板存在：

```text
{episode_title}
```

但没有获取到 Episode Title。

可以配置：

```text
忽略变量
使用默认值
命名失败
转人工处理
```

---

# 40. 文件名字符处理

支持：

```text
非法字符删除
非法字符替换

多个空格合并
前后空格删除

中英文标点转换

Unicode标准化

最大文件名长度
最大路径长度策略

自定义替换表
```

---

# 41. 分类规则

## 41.1 定义

Classification Policy 负责：

> 根据 MediaIdentity、RecognitionType 和本地解析标签确定目标媒体库及目标分类目录。

分类规则不负责重命名。

---

# 42. 分类条件

支持根据：

```text
RecognitionType

MediaType

Title
Year

Genre
Country
Language

ResolutionTag
SourceTag
VersionTag

Provider
ProviderID

ResourceLibrary

原始路径
原始文件名
```

判断。

---

# 43. 分类动作

分类规则命中后产生：

```text
MediaLibrary
+
SubPath
```

例如：

```text
MediaLibrary = MainMedia
SubPath = Movies
```

得到：

```text
/Media/Movies
```

---

# 44. 分类示例

A：

```text
Classification-A

↓

MediaLibrary = Main
SubPath = A
```

结果：

```text
/Media/A/
```

B：

```text
Classification-B

↓

MediaLibrary = Main
SubPath = B
```

结果：

```text
/Media/B/
```

C 使用：

```text
Classification-A
```

因此最终仍然：

```text
/Media/A/
```

---

# 45. 分类规则优先级

支持：

```text
Priority
```

以及：

```text
命中停止
继续匹配
```

可以配置：

```text
默认分类
```

如果没有任何分类规则命中：

```text
使用默认目录
或者
停止整理
或者
进入人工处理
```

---

# 46. 媒体库

## 46.1 定义

Media Library 表示：

> 整理后的资源存放在哪里。

绑定：

```text
Storage
+
Root Path
```

---

## 46.2 配置

```text
MediaLibrary ID

名称

Storage

Root Path

启用状态

是否允许自动创建目录

备注
```

例如：

```text
名称：MainMedia
Storage：NAS
Root：/Media
```

---

# 47. 最终路径生成

最终目标路径：

```text
MediaLibrary Root
+
Classification Path
+
Naming Directory
+
Naming Filename
```

例如：

```text
媒体库：
/Media

分类：
A

命名：
The Matrix (1999)/
The Matrix (1999).mkv
```

最终：

```text
/Media/A/The Matrix (1999)/The Matrix (1999).mkv
```

---

# 48. 整理规则

Organize Policy 负责：

> 实际如何处理文件。

支持：

```text
Move
Copy
HardLink
SoftLink
```

---

# 49. 整理规则配置

```text
OrganizePolicy ID
名称

Operation

冲突策略
重复策略

附件策略

源目录清理策略

失败策略

回退策略

启用状态
```

---

# 50. Move

逻辑：

```text
Source
↓
Target
```

成功后源位置不再保留原文件。

必须在执行前确认：

```text
目标存储支持当前计划
目标路径合法
无禁止处理的冲突
```

---

# 51. Copy

整理完成后：

```text
Source 保留
Target 创建副本
```

---

# 52. HardLink / SoftLink

仅当当前 Storage Adapter 声明支持时允许选择。

如果实际执行时发现能力不满足，可以配置：

```text
失败
回退Copy
回退Move
```

默认建议：

```text
失败
```

避免用户未明确允许的文件行为。

---

# 53. 附属文件整理

主视频整理时，应识别同目录关联文件。

支持：

```text
字幕
NFO

Poster
Fanart

图片

Trailer

其他同名附件
```

---

# 54. 字幕

支持：

```text
srt
ass
ssa
vtt
sub
sup
```

例如：

```text
The.Matrix.1999.mkv
The.Matrix.1999.zh-CN.ass
The.Matrix.1999.en.srt
```

整理后：

```text
The Matrix (1999).mkv
The Matrix (1999).zh-CN.ass
The Matrix (1999).en.srt
```

优先保留：

```text
语言
简繁标签
Forced
SDH
其他已有字幕标签
```

---

# 55. Dry Run 整理预演

这是必须实现的功能。

Dry Run：

> 完成识别、元数据匹配、命名、分类和目标路径计算，但不修改任何文件。

展示：

```text
Source

Filename Parse Result

Matched Recognition Rule
RecognitionType

Metadata Policy
Metadata Result
Confidence

Naming Policy
New Name

Classification Policy
Media Library
Classification Path

Organize Policy

Target

Conflict

Warning
```

---

## 55.1 示例

```text
SOURCE
/Downloads/C/The.Matrix.1999.mkv

识别规则
C-Rule

识别类型
C

元数据
TMDB / The Matrix / 1999

命名策略
Naming-A

分类策略
Classification-A

整理策略
Move

TARGET
/Media/A/The Matrix (1999)/The Matrix (1999).mkv
```

---

# 56. 自动整理

允许资源库配置：

```text
仅扫描
扫描并生成计划
自动整理
```

自动整理必须满足：

```text
识别成功
+
Metadata Confidence 达标
+
分类成功
+
命名成功
+
目标路径通过校验
+
不存在需要人工处理的冲突
```

否则进入人工处理队列。

---

# 57. 文件重复检测

整理前检查：

```text
Target Exists
```

同时可以根据：

```text
Provider ID
Media Type
Season
Episode
文件大小
文件 Hash
```

辅助判断是否重复。

---

# 58. Hash 策略

支持：

```text
不计算
快速Hash
完整Hash
```

不要求所有媒体默认进行完整 Hash。

可由：

```text
重复检测策略
```

决定是否计算。

---

# 59. 冲突策略

目标已经存在时支持：

```text
Skip
Overwrite
Rename
Manual
```

---

## 59.1 Skip

保持源文件不动。

记录：

```text
Status = Skipped
Reason = TargetExists
```

---

## 59.2 Overwrite

覆盖已有目标。

属于高风险操作。

必须：

```text
明确配置开启
+
记录审计日志
```

---

## 59.3 Rename

例如：

```text
The Matrix (1999).mkv
The Matrix (1999) (1).mkv
```

---

## 59.4 Manual

进入：

```text
NeedConfirm
```

等待人工决定。

---

# 60. 主文件与附加内容识别

同目录可能存在：

```text
正片
Sample
Trailer
Extra
Featurette
Behind The Scenes
```

可以根据：

```text
文件名称
关键词
目录位置
文件大小
```

判断。

相关关键词规则允许配置。

---

# 61. 空目录处理

媒体整理成功以后，可以配置：

```text
不处理

删除真正的空目录

删除仅包含允许忽略文件的目录
```

默认：

```text
不删除未知文件
```

> 当前实现（Phase 20.6）：OrganizePolicy 可配置 `none`（默认）、`empty` 或 `ignorable`。
> 仅显式 execute 且主文件与附件 MOVE 全部验证成功后，由 OrganizerExecutor 在
> ResourceLibrary `storagePath` 排他边界内按最大层数处理。`empty` 只删除即时复核为空的目录；
> `ignorable` 只删除完整有界列表中匹配显式安全 basename pattern 的普通文件。未知文件、链接、
> 子目录、竞态、超限和访问失败均停止或 PARTIAL；COPY/LINK/DryRun/失败/Rollback 零清理。

---

# 62. 任务系统

所有扫描及整理行为均由 Task 执行。

---

# 63. 任务类型

```text
ScanTask
RecognitionTask
OrganizeTask
MetadataRefreshTask
```

也可以由一个父任务组合。

---

# 64. 任务状态

统一状态：

```text
Pending

Scanning

Parsing

Recognizing

FetchingMetadata

Planning

WaitingConfirm

Organizing

Completed

PartialSuccess

Failed

Cancelled
```

---

# 65. 任务信息

记录：

```text
Task ID

Task Type

ResourceLibrary

创建时间
开始时间
完成时间

总文件数

识别成功
识别失败

整理成功
整理失败
跳过

当前进度
```

---

# 66. 任务操作

支持：

```text
开始

暂停
继续

取消

重试

仅重试失败项

查看详情

删除历史记录
```

删除任务历史不得影响实际媒体文件。

---

# 67. 并发控制

系统配置：

```text
最大扫描任务数
最大识别并发
最大元数据请求并发
最大整理并发
```

Storage 可以单独配置：

```text
MaxConcurrency
```

Provider 可以单独配置：

```text
MaxConcurrency
```

---

# 68. 文件锁

同一个文件在同一时间只能存在一个有效整理操作。

防止：

```text
Task A Move File
Task B Copy File
```

同时发生。

建议锁标识至少包含：

```text
StorageID
+
Path
```

---

# 69. 整理操作记录

每个媒体建立：

```text
OrganizePlan
```

记录：

```text
Source

Target

RecognitionType

MediaIdentity

NamingPolicy

ClassificationPolicy

OrganizePolicy

Operations
```

Operations 例如：

```text
1 CreateDirectory
2 Move Video
3 Move Subtitle
4 Move NFO
```

---

# 70. 操作状态

每一步操作保存：

```text
Pending
Running
Success
Failed
Skipped
```

方便：

```text
故障定位
失败重试
任务恢复
```

---

# 71. 日志系统

支持日志等级：

```text
TRACE
DEBUG
INFO
WARN
ERROR
```

默认：

```text
INFO
```

可开启：

```text
DEBUG
```

---

# 72. 普通整理日志

例如：

```text
[INFO] 发现媒体文件
       /Downloads/C/The.Matrix.1999.mkv

[INFO] 命中识别规则
       Rule=C

[INFO] RecognitionType=C

[INFO] 开始元数据识别

[INFO] Metadata Provider=TMDB

[INFO] 匹配媒体
       The Matrix (1999)

[INFO] NamingPolicy=A

[INFO] ClassificationPolicy=A

[INFO] 目标路径
       /Media/A/The Matrix (1999)/The Matrix (1999).mkv

[INFO] Operation=Move

[INFO] 整理成功
```

---

# 73. Debug 日志

Debug 模式额外记录：

```text
原始路径

原始文件名

文件名预处理结果

Token解析结果

正则匹配过程

识别规则匹配过程

RecognitionType选择过程

Metadata搜索参数

Metadata候选结果摘要

候选评分详情

最终MediaIdentity

Naming模板

Naming模板展开过程

Classification规则判断过程

最终Target计算过程

Storage操作过程

Retry过程

异常Stack Trace
```

---

# 74. 日志脱敏

严禁输出完整：

```text
Password
Token
API Key
AccessKey
SecretKey
Authorization
Cookie
```

可以输出：

```text
Token=******
```

---

# 75. 整理结果记录

每个 Task 完成后必须持久化整理结果。

支持：

```text
数据库记录
JSON导出
CSV导出
```

至少实现数据库 + JSON。

---

# 76. JSON 结果示例

```json
{
  "taskId": "task_001",
  "status": "Completed",
  "total": 3,
  "success": 3,
  "failed": 0,
  "skipped": 0,
  "items": [
    {
      "source": "/Downloads/C/The.Matrix.1999.mkv",
      "recognitionType": "C",
      "provider": "TMDB",
      "providerId": "xxx",
      "title": "The Matrix",
      "year": 1999,
      "namingPolicy": "A",
      "classificationPolicy": "A",
      "organizePolicy": "Move",
      "target": "/Media/A/The Matrix (1999)/The Matrix (1999).mkv",
      "status": "Success"
    }
  ]
}
```

---

# 77. 错误体系

统一错误分类，例如：

```text
StorageConnectionError
StoragePermissionError

FileNotFoundError
FileLockedError
FileConflictError

ParseError
RecognitionError

MetadataConnectionError
MetadataRateLimitError
MetadataNotFoundError
MetadataMatchError

NamingError
ClassificationError

MoveError
CopyError
LinkError
DeleteError

TimeoutError

UnknownError
```

---

# 78. 错误记录

错误必须包含：

```text
ErrorCode

Message

TaskID

StorageID

Source

Stage

Timestamp

Retryable

DebugDetails
```

---

# 79. 自动重试

适用于临时错误：

```text
网络超时
SMB断连
OpenList连接异常
对象存储暂时失败
TMDB请求超时
HTTP 429
HTTP 5xx
```

支持：

```text
最大次数
基础间隔
指数退避
```

不可恢复的配置错误不自动无限重试。

---

# 80. 未识别媒体

无法判断 RecognitionType：

```text
Status = Unrecognized
```

支持：

```text
重新识别

人工指定 RecognitionType

建立新的识别规则

忽略
```

> 当前实现（Phase 21.0）：被 Task 跟踪的 `Unrecognized` 条目持久进入
> `WAITING_RECOGNITION`，保存启用 RecognitionType 的有界快照并释放源锁。CLI 可显式选择
> 快照中且当前仍启用的类型，原子记录 actor/note 审计，再通过新的显式 resume 进入正常策略
> 管线；没有隐藏 A 默认、没有规则/配置修改。C 仍为 C。建规则留后续。

> 当前实现（Phase 21.2）：上述 Recognition 人工等待项可由操作员显式标记为 `IGNORED`，
> 同一事务更新 review/TaskItem 并记录 actor/note 审计。该动作不删除或隐藏媒体、不建立规则，
> 也不影响未来扫描；批量忽略见 Phase 21.5。

> 当前实现（Phase 21.3）：可对 pending RecognitionReview 显式记录 `retry_requested`，把
> WAITING_RECOGNITION 项原子送回 PENDING，再由独立 `tasks resume` 使用当前外部配置和原
> ResourceLibrary 上下文重跑真实 RecognitionRuleEngine。不注入类型、不默认 A、不写规则。

> 当前实现（Phase 21.4）：上述 `retry_requested` 也可通过有界批量命令
> `recognition-reviews retry-pending --actor ... [--note ...] [--limit 1..100] [--task-id ...]`
> 对最早到期的一组 pending 等待项在同一事务中请求重新识别；仍必须显式 `tasks resume`。

> 当前实现（Phase 21.5）：上述 Recognition 等待项也支持有界批量忽略
> `tasks ignore-pending --actor ... [--note ...] [--limit 1..100] [--task-id ...]`；最早到期的一组
> pending 项与匹配 review 在同一事务中标记为 `IGNORED`。

> 当前实现（Phase 21.6）：上述 pending RecognitionReview 也支持有界批量人工指定同一启用
> RecognitionType：
> `recognition-reviews resolve-pending --recognition-type TYPE --actor ... [--note ...]
> [--limit 1..100] [--task-id ...]`。每一项仍必须包含在快照中，且整批原子 RESOLVED。

---

# 81. 元数据识别失败

已经确定 RecognitionType，但无法匹配影视作品：

```text
Status = MetadataNotFound
```

支持：

```text
修改关键词

修改年份

Movie / TV切换

更换Provider

直接填写Provider ID

人工选择候选

忽略
```

> 当前实现（Phase 21.2）：Metadata 候选等待与 MetadataNotFound 修正等待均支持相同的
> 单项持久忽略语义。Ignored 不计成功、不会 resume/retry，也不执行 Storage 或 Provider。

> 当前实现（Phase 21.5）：上述 Metadata 等待项同样支持有界批量忽略，范围、排序、原子性和
> 安全边界与 Recognition 批量忽略一致。

> 当前实现（Phase 21.8）：Metadata 候选等待项也支持有界批量候选选择：
> `metadata-reviews resolve-pending --candidate-rank RANK --actor ... [--note ...]
> [--limit 1..100] [--task-id ...]`。整批以同一持久候选 rank 原子 RESOLVED，仍由显式
> `tasks resume` 消费持久 MetadataSelection。

> 当前实现（Phase 21.7）：Metadata NOT_FOUND 修正等待项也支持有界批量修正：
> `metadata-corrections resolve-pending --media-type movie|tv [--query QUERY | --provider-id
> PROVIDER_ID] [--year YEAR] --actor ... [--note ...] [--limit 1..100] [--task-id ...]`。
> 整批使用同一组合法修正输入原子 RESOLVED，仍由显式 `tasks resume` 调用真实 Provider。

---

# 82. 人工整理

支持用户选择单个或者多个文件。

可以手动设置：

```text
RecognitionType

Metadata Result

NamingPolicy

ClassificationPolicy

OrganizePolicy
```

系统实时生成：

```text
Target Preview
```

确认后执行。

---

# 83. 批量操作

支持：

```text
批量重新扫描

批量识别

批量重新识别

批量设置RecognitionType

批量Metadata识别

批量Dry Run

批量整理

批量重试

批量忽略
```

> 当前实现（Phase 21.8）：已完成批量重新识别（Recognition retry-pending）、批量忽略
> （`tasks ignore-pending`）、批量设置 RecognitionType（Recognition resolve-pending）、批量
> Metadata 修正（Metadata resolve-pending）与批量 Metadata 候选选择（Metadata review
> resolve-pending）五项有界闭环。这些命令不构造 Storage/Provider/工作流、不修改规则或配置、
> 不改变执行授权；批量 Dry Run/整理及批量重试仍留后续。

---

# 84. 策略测试工具

配置页面必须提供：

> Test Policy

用户输入：

```text
Storage
File Path
```

系统运行到：

```text
Plan
```

但不实际操作文件。

---

# 85. 策略测试结果

显示：

```text
SOURCE

文件名解析

识别规则匹配：
Rule-C

RecognitionType：
C

Metadata Policy：
Movie-TMDB

Metadata：
The Matrix (1999)

Confidence：
98

Naming Policy：
A

Naming Result：
The Matrix (1999).mkv

Classification Policy：
A

Media Library：
Main

SubPath：
A/The Matrix (1999)

Organize Policy：
Move

TARGET：
/Media/A/The Matrix (1999)/The Matrix (1999).mkv
```

此功能对于调试规则必须作为核心功能实现。

---

# 86. 配置管理

系统需要管理：

```text
Storage

Resource Library

Media Library

Metadata Provider
Metadata Policy

Recognition Rule
Recognition Type
Recognition Type Policy

Naming Policy

Classification Policy

Organize Policy

Schedule

System Settings
```

> 当前实现（Phase 22.0）：已完成配置管理架构决策与领域骨架；JSON 仍为首次激活前的运行时
> bootstrap 输入，SQLite 承载 managed revision 变更/审计，凭证保持环境或 Secret Store 归属。
> 当前实现（Phase 22.1）：新增内部 durable Storage 配置模型、校验、CRUD 服务与 SQLite
> 变更/引用/审计存储；支持 Local/SMB/OpenList/S3/R2/S3-compatible，凭证仅允许环境变量名，
> 字面与嵌套 secret 字段被拒绝。该对象级写入口仍未接入运行时配置编辑旅程；whole-document
> Managed Configuration 的 API/Web/CLI 生命周期由 Phase 22.2/22.2R 提供基础。2026-08-24
> 的独立验收曾发现 pre-F1 implementation 的 repeated-request fail-open、Scheduler 内容/identity
> 不一致及陈旧编辑恢复缺口；F1 已修复这些具体缺口，但后续独立验收又发现 resident API 在激活
> 后只更新 snapshot identity、未原子更新准入/execute 行为，以及旧 Job revision 失败不可操作。
> Phase 22.2R-F2 聚焦修复已经独立验收 PASS/CLOSED；Phase 22.3 也已于 2026-08-25 通过
> phase-level Final Closure Audit。Phase 22.4 与 Phase 22.5-A 也已于 2026-08-26 独立验收
> PASS/CLOSED；Phase 22.5-B/F1 随后也已独立验收，Phase 22.5-C 及 F1/F2 已通过
> final Integration Acceptance。Phase 22.5-D same-Provider managed live Metadata correction test
> 已通过独立 High re-review 并 PASS/CLOSED；Phase 22.5-E 单项 correction DryRun continuation
> 的 F1 correction checkpoint `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 通过
> 独立 High re-review，其被拒 checkpoint `08dfd4f921728755209b6d52347d28f221121c47` 的
> FIX REQUIRED 记录保留；同日 phase-level Final Closure Audit 判定 Phase 22.5 PASS / CLOSED。
> Phase 22.6-A 至 22.6-N 的有界 Naming/Classification/Organize 配置旅程 Slice 已分别通过独立
> High Review；Phase 22.6 尚未关闭，仍须先完成 CURRENT 文档同步的独立 High Review，再执行
> 单独的 Final Closure Audit。
>
> 当前实现覆盖：Files detail 中 exact resolved correction/version、source Task/TaskItem 与 snapshot
> ID/digest 的可见性；API/Web 共用的原子单项 admission；以及 pinned Worker 对新 DryRun
> Task/Item/Result 的创建与结果门。队列、运行、完成、失败、陈旧、取消和重复/陈旧身份均有
> 有界状态或恢复提示，源文件、源 review、源 Task 和兄弟项不变。
>
> 当前实现（Phase 22.2/22.2R-F2 whole-document 与 Phase 22.3 Local slice 已验收）：Managed Configuration
> 已经经过 Draft → Validate/Test → Validated → 显式 Activate，持久化生成不可变 Runtime Snapshot；
> resident API 现在按请求获取一个完整不可变 binding，identity、准入、execute gate、schedule/status 和
> MetadataPolicy 参考不会跨 revision 混用。现有 authority、digest、审计和缺失/损坏/运行时不可消费 Active 的恢复
> 约束已接入 API/Web/CLI。F1 修复了重复请求 fail-closed、同快照 Scheduler 消费、Pinned
> Worker 和陈旧 Draft 冲突；F2 进一步修复 API 原子运行时绑定、旧快照 Job 可操作失败并补齐强制
> 并发/execute pin/零 I/O 证据。Phase 22.3 的 Local Storage/Library 对象编辑、引用影响、
> 有界 setup check、失败/陈旧恢复、checked activation 与行为可辨 Worker pin 已完成组合
> closure；Phase 22.4 在同一 authority 上完成 Recognition 配置与 Strategy Test，未重新定义
> Active source of truth；远端 Storage、Provider 测试和 Secret Store 仍是目标架构。
>
> 目标架构（尚未实现）：Managed Activation 建立后，JSON 仅用于 bootstrap、导入导出和迁移，
> 不再是竞争性的 Active source of truth，并继续扩展为完整配置对象纵向旅程。

---

# 87. 配置操作

全部配置应支持：

```text
新增
编辑
复制
启用
禁用
删除
测试
```

可复制规则方便：

```text
A规则
↓
复制
↓
修改为C规则
```

> 当前实现（Phase 22.1）：Storage 配置在内部服务/SQLite 仓库层支持新增、读取、列表、编辑、
> 复制、启用、禁用与删除，并使用乐观版本与 Before/After 审计。`测试` 与操作界面/导入导出
> 仍是后续范围。

---

# 88. 配置引用关系

配置不能无检查直接删除。

例如：

```text
Naming-A
```

被：

```text
RecognitionType A
RecognitionType C
```

引用。

删除时系统必须提示：

```text
当前规则被2个识别类型策略引用。
```

默认禁止删除。

> 当前实现（Phase 22.1）：Storage 删除与引用计数在同一 SQLite 写事务内执行；存在
> Resource/Media Library 引用时默认阻断并保留原对象与审计状态。后续配置族的引用删除提示、
> 引用清理与完整引用详情仍未实现。

---

# 89. 配置导入导出

支持：

```text
导出配置
导入配置

备份
恢复
```

配置必须包含：

```text
ConfigVersion
```

用于未来版本升级。

敏感字段：

```text
默认不导出
```

或者：

```text
经过单独加密后导出
```

---

# 90. 数据索引

所有扫描过的文件建立索引。

建议：

```text
FileID

StorageID
ResourceLibraryID

Path
Filename
Extension

Size
ModifiedTime

FastHash
FullHash

ParseResult

RecognitionType
RecognitionStatus

Provider
ProviderID

OrganizeStatus
TargetPath

LastTaskID

CreatedAt
UpdatedAt
```

---

# 91. 增量扫描

扫描时判断：

```text
New
Modified
Unchanged
Missing
```

只有：

```text
New
Modified
```

默认重新进入媒体识别。

避免每一次扫描都重新处理整个媒体库。

---

# 92. 文件状态

统一建议：

```text
Discovered

Pending

Parsing

Recognizing

Recognized

MetadataMatching

Identified

NeedConfirm

Planning

Ready

Organizing

Organized

Skipped

Ignored

Failed

Missing
```

---

# 93. Dashboard

首页展示：

```text
Storage状态

资源库数量
媒体库数量

媒体文件总数

待识别
识别失败

待确认

待整理

今日整理成功
今日整理失败

运行中任务

最近错误
```

---

# 94. 文件列表

支持显示：

```text
文件名

路径

资源库

RecognitionType

识别结果

TMDB等Provider信息

整理状态

目标路径

最近更新时间
```

> 当前实现（Phase 21.9）：提供只读 FileIndex CLI 文件列表与单项详情；暂不包含 Recognition/
> Provider/目标路径等 Pipeline 派生字段，也不读取文件内容。

> 当前实现（Phase 21.10）：文件列表支持稳定 keyset cursor 分页；`--after/--before` 配合
> `--cursor-file-id` 使用 `(updated_at DESC, file_id DESC)` 顺序，不使用 OFFSET。

---

# 95. 搜索与筛选

支持：

```text
文件名
路径
Title
Provider ID

RecognitionType

Resource Library
Media Library

识别状态
整理状态

年份

Task ID

时间范围
```

> 当前实现（Phase 21.9）：CLI 支持 ResourceLibrary、Storage、scan status 与 path/filename
> 子串筛选；时间范围筛选仍留后续。

> 当前实现（Phase 21.12）：CLI 进一步支持基于最新 Task Result 的 RecognitionType、Provider、
> Provider ID、Title、Task ID 与 Year 派生筛选。

> 当前实现（Phase 21.13）：FileIndex 基础过滤/cursor/limit 已下沉到参数化仓储查询，应用层只
> 处理最新 Task Result 派生筛选。

> 当前实现（Phase 21.14）：SQLite 路径的派生筛选也已下沉为 FileIndex 与最新 Task Result 的
> 参数化 join，不再逐文件查询最新结果。

> 当前实现（Phase 21.16）：`files stats` 提供 FileIndex 总数与 scan status 分组统计，可按
> ResourceLibrary/Storage 过滤；不读取文件内容，不构造 Storage/Provider。

> 当前实现（Phase 21.17）：已有 Operator Web UI 新增只读 Files 视图；认证 API 提供
> list/detail/stats，页面只读，不提供写入或执行操作。

> 当前实现（Phase 21.18）：Files 视图增加只读搜索/筛选控件，可组合 ResourceLibrary、
> Storage、scan status、path/filename、RecognitionType、Provider、Provider ID、Title、
> Task ID 与 Year 过滤。

> 当前实现（Phase 21.19）：新增显式 `batch preview` 与 `batch organize` 命令，复用无路径全
> ResourceLibrary 管线；`batch organize` 默认 DryRun，只有显式 `--execute` 才可进入执行边界。

> 当前实现（Phase 21.20）：File detail/API/Web UI 增加同一 source Storage/path 的关联
> Recognition/Metadata review 链接；只读导航，不修改 review、不调用 Provider。

> 当前实现（Phase 21.21）：`files re-recognize` 可为存在 pending RecognitionReview 的文件发起
> 重新识别请求；真正重评仍由 `tasks resume` 执行。

> 当前实现（Phase 21.22）：`files re-match` 可为存在 pending MetadataCorrectionReview 的文件
> 执行有界 Metadata 修正/重新匹配；真正 Provider 查找仍由 `tasks resume` 执行。

> 当前实现（Phase 21.23）：`files re-plan` 可为最新 FAILED/PARTIAL 结果的文件发起单项重试
> 请求，原子返回 PENDING；真正重新规划/整理仍由 `tasks resume` 执行。

> 当前实现（Phase 21.24）：Phase 21 收口 smoke test 与文档一致性核对完成；CLI/UI 只读边界
> 和禁止依赖审计保持通过。

> 当前实现（Phase 21.25）：Files 详情 Web UI/API 增加 re-recognize 与 re-plan 请求入口；仅在
> 对应 pending review 或 FAILED/PARTIAL 状态显示，实际执行仍需显式 Task resume。

> 当前实现（Phase 21.26）：补齐 file re-match 的 Web UI/API；Phase 21 已按当前有界范围收尾，
> 下一阶段进入 Phase 22 配置管理系统。

> 当前实现（Phase 21.15）：新增 `tasks retry-request`，可对有界 FAILED/PARTIAL TaskItem
> 批量原子回到 PENDING；真正的重试仍通过显式 `tasks resume` 执行。

---

# 96. 媒体详情

展示：

```text
原始文件信息

文件名解析结果

RecognitionType

命中的Recognition Rule

元数据

Provider
Provider ID

Naming Policy

Classification Policy

Organize Policy

Target

历史整理记录

错误记录
```

> 当前实现（Phase 21.11）：`files show` 在 FileIndex 字段之外追加同一 source Storage/path 的
> 最新持久 Task Result；缺失历史显式显示为空，不构造 Provider/Storage，也不读取文件内容。

操作：

```text
重新识别

修改RecognitionType

重新匹配Metadata

重新生成Plan

重新整理
```

---

# 97. 系统设置

配置：

```text
数据库目录

工作目录
缓存目录

日志目录
结果导出目录

默认语言
默认时区

默认日志等级

日志保留时间

最大扫描并发
最大识别并发
最大整理并发

默认Retry策略
```

---

# 98. 定时任务

支持：

```text
定时扫描资源库
定时自动整理
定时清理缓存
定时清理日志
```

调度支持：

```text
固定周期
固定时间
Cron
```

例如：

```text
每30分钟增量扫描

每天03:00全量检查
```

---

# 99. 安全要求

所有敏感凭证：

```text
SMB Password

OpenList Token

TMDB Token / API Key

R2 AccessKey
R2 SecretKey

其他Provider认证信息
```

必须加密存储。

---

# 100. 高风险文件操作保护

高风险操作：

```text
Overwrite
Delete
Move后删除源
清理源目录
```

需要单独配置。

默认策略：

```text
不允许覆盖
不永久删除未知文件
```

---

# 101. 审计日志

记录重要操作：

```text
修改Storage

修改Recognition Rule

修改RecognitionTypePolicy

修改Naming Policy

修改Classification Policy

修改Organize Policy

人工修改RecognitionType

人工修改Metadata结果

Overwrite

Delete

取消任务
```

记录：

```text
User

Action

Object

Before

After

Timestamp

Result
```

---

# 102. API 设计要求

核心能力必须提供 API，以便：

```text
Web UI
CLI
自动化程序
其他服务
```

调用。

建议：

```text
/api/storages

/api/resource-libraries

/api/media-libraries

/api/metadata-providers
/api/metadata-policies

/api/recognition-rules
/api/recognition-types
/api/recognition-type-policies

/api/naming-policies

/api/classification-policies

/api/organize-policies

/api/files
/api/media

/api/tasks

/api/logs

/api/settings
```

---

# 103. 推荐后端模块

```text
Storage
├── LocalStorage
├── SMBStorage
├── OpenListStorage
└── S3Storage

Scanner

Parser
├── FilenameParser
├── PathParser
├── DirectoryParser
└── NfoParser

Recognition
├── RuleEngine
├── RecognitionTypeResolver
└── RecognitionTypePolicyResolver

Metadata
├── MetadataProvider
├── TMDBProvider
├── MetadataMatcher
└── MetadataCache

Naming
└── NamingEngine

Classification
└── ClassificationEngine

Organizer
├── Planner
├── ConflictResolver
├── Executor
└── AttachmentOrganizer

Task
├── Scheduler
├── Queue
└── Worker

Database

Logger

API

WebUI
```

---

# 104. 核心数据关系

建议：

```text
Storage
   ↑
   │
ResourceLibrary


RecognitionRule
      ↓
RecognitionType
      ↓
RecognitionTypePolicy
      ├──────── MetadataPolicy
      │              ↓
      │       MetadataProvider
      │
      ├──────── NamingPolicy
      │
      ├──────── ClassificationPolicy
      │                 ↓
      │            MediaLibrary
      │                 ↓
      │              Storage
      │
      └──────── OrganizePolicy
```

---

# 105. 完整媒体处理流程

最终完整业务流程：

```text
资源库
   ↓
扫描
   ↓
发现文件
   ↓
过滤
   ↓
文件稳定性检测
   ↓
本地文件解析
├── 文件名
├── 路径
├── 目录
└── NFO
   ↓
识别规则引擎
   ↓
RecognitionType
   ↓
RecognitionTypePolicy
   ↓
MetadataPolicy
   ↓
TMDB / 其他Provider
   ↓
搜索候选
   ↓
候选评分
   ↓
MediaIdentity
   ↓
置信度判断
├── 高 → 自动继续
├── 中 → 人工确认
└── 低 → 识别失败
   ↓
NamingPolicy
   ↓
生成标准目录名及文件名
   ↓
ClassificationPolicy
   ↓
选择MediaLibrary
   ↓
生成分类目录
   ↓
组合Target
   ↓
冲突检测
   ↓
生成OrganizePlan
   ↓
Dry Run
   ↓
OrganizePolicy
   ↓
Move / Copy / HardLink / SoftLink
   ↓
整理字幕及附件
   ↓
更新文件索引
   ↓
保存整理结果
   ↓
输出日志
```

---

# 106. 第一阶段 MVP

首期建议必须完成：

### Storage

- Local
- SMB
- OpenList
- R2 / S3

### Library

- Resource Library
- Media Library

### Recognition

- 文件扫描
- 文件过滤
- 文件稳定检测
- 文件名解析
- 路径解析
- 季集解析
- Recognition Rule
- Recognition Type
- Recognition Type Policy

### Metadata

- TMDB Provider
- Movie Search
- TV Search
- Movie/TV Details
- Season/Episode
- 候选评分
- 人工选择
- Metadata Cache
- Provider 重试
- 429 处理

### Policies

- Naming Policy
- Classification Policy
- Organize Policy

### Organizer

- Dry Run
- Move
- Copy
- HardLink
- SoftLink
- 字幕整理
- 冲突处理
- 重复检测

### Task

- Task Queue
- 任务状态
- 暂停
- 继续
- 取消
- 重试

### Log

- INFO
- DEBUG
- ERROR
- 单文件完整整理日志
- 整理结果 JSON

### UI

- Dashboard
- Storage 管理
- 资源库管理
- 媒体库管理
- Metadata Provider 管理
- Recognition Type 管理
- Policy 管理
- Task 管理
- 文件列表
- 人工识别
- Dry Run

---

# 107. 第二阶段

后续增加：

```text
更多Metadata Provider

更多Storage Provider

更多字幕处理能力

多版本媒体

质量优先级策略

自动媒体升级

海报及背景图下载

NFO生成

媒体服务器刷新通知

Webhook

完整权限系统

Audit Log增强

完整Rollback

高级统计

通知系统
```

---

# 108. 验收核心场景

## 场景一：A → A

输入：

```text
/Downloads/A/The.Matrix.1999.mkv
```

识别：

```text
A
```

处理：

```text
A Metadata
→ A Naming
→ A Classification
→ Move
```

结果：

```text
/Media/A/The Matrix (1999)/The Matrix (1999).mkv
```

验收通过。

---

## 场景二：B → B

输入：

```text
/Downloads/B/The.Last.of.Us.S01E03.mkv
```

识别：

```text
B
```

处理：

```text
B Metadata
→ B Naming
→ B Classification
```

结果：

```text
/Media/B/The Last of Us/
└── Season 01/
    └── The Last of Us - S01E03.mkv
```

验收通过。

---

## 场景三：C → A

输入：

```text
/Downloads/C/Special.C.2025.mkv
```

识别：

```text
C
```

类型不得改变。

处理：

```text
RecognitionType = C

NamingPolicy = A
ClassificationPolicy = A
```

结果：

```text
/Media/A/Special C (2025)/Special C (2025).mkv
```

验收通过。

关键验收条件：

```text
RecognitionType仍然必须为C。
```

---

# 109. 最终架构原则

系统必须严格保持：

```text
识别是什么
≠
叫什么
≠
放在哪里
≠
怎么移动
```

对应：

```text
Recognition
      ↓
RecognitionType
      ↓
RecognitionTypePolicy
      ↓
┌────────────────────────────┐
│ Metadata    确定是哪部影视 │
│ Naming      决定叫什么     │
│ Classification 决定放哪里 │
│ Organize    决定怎么过去   │
└────────────────────────────┘
```

因此：

```text
A → A命名 + A分类
B → B命名 + B分类
C → A命名 + A分类
D → B命名 + A分类
E → A命名 + B分类
```

均属于正常合法配置。

---

## 109.1 只读系统与配置状态

生产 API 应在已归一化配置验证完成后生成一次不可变状态快照。具有只读权限的操作员可检查
Python/Schema 兼容性、Storage/资源库/媒体库标识及 A/B/C 下游策略引用。每类目录必须有固定
上限和确定性排序；请求不得重新读取配置、连接 Storage 或元数据服务。

该能力不是配置导出。必须从数据模型上排除根路径、展示路径、规则条件值、命名模板、分类
路径、URL/端点、环境变量名和值、Webhook、凭证和任意 options。UI 只能用文本节点展示并
提供显式刷新，不得提供编辑、应用、连通性测试、扫描、任务或执行按钮。

## 109.2 Automation Job 协作取消界面

只有具有 `cancel_job` 权限的操作员才能取消 Automation Job。UI 仅可在 Pending 或 Running
详情中显示入口，且一次点击不得产生状态变更；必须显示独立的确认与保留选项。请求正文和
查询参数必须为空，禁止由客户端提交 actor、状态、命令、路径、Task 或 execute 字段。

Pending 取消立即终止；Running 取消只在批次协作边界生效，正在进行的读取或单项操作可能完成。
系统不得将取消描述为回滚，不得删除或逆转已完成媒体操作，也不得因此获得新的执行权限。

## 109.3 DryRun Automation Job 提交界面

操作台只能提交 `scan` 或 `preview`，可选 limit 必须为 1–10000 的整数。必须依次经过打开表单、
审核不可变摘要和确认入队；返回或保留操作不产生请求。最终 JSON 只允许 command 和 limit，
Query 及 path、Task、actor、policy、Storage、Scheduler、overwrite、delete、organize、execute 等
字段必须在创建 Job 前拒绝。

Viewer/Auditor 保持只读，Operator/Executor/Admin 继续使用 `submit_dry_run` 权限。入队本身只
写持久 Job 与安全审计，不得构造 Storage、Provider、Scanner 或 Executor；后续 Worker 仍按
既有边界处理，并且 preview 永远不获得媒体变更权限。

## 109.4 Automation Job 持久准入容量

`automation.maximumActiveJobs` 必须为 1–10000 的整数，默认 100。容量只统计 Pending 和
Running；Completed、Failed、Cancelled 保留历史但释放容量。所有生产入队来源必须共享该
上限，禁止按 API、CLI、Scheduler 或 organize 建立不一致的隐藏容量。

SQLite 必须在一个写事务内完成活动数量判断和插入，跨进程并发不得超额。满队列返回稳定冲突，
不创建 Job、不删除/取消旧 Job。Scheduler 不推进 occurrence 或写发出审计；一次性执行授权不
消费也不撤销。准入只操作持久状态，不得构造 Storage、Provider、Scanner 或 Executor。

## 109.5 陈旧 Running Job 只读观察

`automation.staleJobAgeSeconds` 必须为 60–604800 的整数，默认 3600。系统可按该阈值只读列出
更新时间更早且仍为 Running 的 Job；查询必须稳定排序并在 SQL 层限制为最多 100 条。API 只返回
安全的 Job 标识、命令、状态、时间、Task/调度关联、取消请求和执行授权标记，不返回输入、路径、
错误或秘密。

“陈旧”只代表年龄观察，不证明 Worker 已死亡。UI 不得提供自动重排、重试、强制取消或执行；尤其
对已授权真实变更的 organize Job，必须提示人工调查不确定执行结果。本观察路径不得调用媒体工作流
或 Storage。

后续恢复能力的前置条件是持久化 claim fencing：Worker 的心跳与终态提交必须携带当前 claim 的
不可伪造随机标识，并由数据库按 Running 状态与标识共同校验。旧 Worker 在 Job 被重排或重新领取后
不得刷新年龄、覆盖终态或影响新 Worker。心跳只能表示最近一次协作边界仍活跃，不能承诺正在进行的
外部网络或 Storage 调用可被中断。

实现采用内部随机 token；每次 Pending→Running 都必须生成新值，重排与终态清除该值。终态通知
只能在带 token 的条件提交成功后发布。token 属于内部执行权限，不得进入 API、UI、CLI、日志、
通知、审计、配置快照或错误信息。该 fencing 只保护 Runtime 状态所有权，不提供外部 Storage
exactly-once 或回滚语义。

## 109.7 Phase 19 Storage 验收门

子阶段单元测试 PASS 不等于 Phase 19 生产验收。必须分别记录 Local、SMB、OpenList、S3/R2
以及同存储/跨存储 COPY、MOVE 的证据类型。Fake client、mock HTTP 和内存 Storage 只能标记为
UNIT PASS；只有生产 Adapter 在明确隔离的真实文件系统或服务测试根执行才可标记 ISOLATED PASS。

LocalStorage write/copy 必须先在目标同目录完成私有 stage，再原子发布。任何读取、复制或发布失败
不得暴露不完整目标；存在旧目标时必须保持旧内容，并清理操作自身 stage。该保证仅针对命名空间
可见性，不宣称断电持久性或多文件事务。

跨存储 MOVE 必须在删除源之前至少验证目标存在且大小一致。写入失败或大小不一致必须保留源；
删除失败必须报告 PARTIAL 并明确两边文件状态，不得报告 SUCCESS。真实远端破坏性验收必须要求
专用凭证、明确空测试根和操作员确认，禁止自动使用 ResourceLibrary、MediaLibrary 或用户配置路径。

OpenList 实机验收必须同时显式提供测试 URL、专用 Token、无默认值的绝对测试根和固定破坏性确认
短语。测试根末级名称必须以 `mediaflow-acceptance-` 开头。每次只创建随机 run 子目录，清理仅允许
预先列举的生成对象；发现未知对象必须停止并将验收记为 FAIL/BLOCKED，不得递归清理。

OpenList 破坏性验收在首次写入前必须通过生产 Storage 只读接口证明测试根存在、为目录且为空；
非空、不可读或类型错误均不得尝试自动清理。启用真实矩阵还必须指定一个绝对、尚不存在的本地
JSON 报告文件，原子非覆盖发布脱敏验收证据，不得记录 URL、Token、Header 或原始远端响应。

OpenList v4 对空目录允许返回 `content: null, total: 0`，基础设施 DTO mapper 应将该严格组合
归一化为空列表；`null` 配合非零/负数/布尔/缺失 total 或其他非列表 content 必须继续拒绝，
不得把不一致响应伪装为空目录。

SMB 与 S3/R2 实机验收必须与 OpenList 使用同等级别的 fail-closed 门禁：显式端点/端口、专用
凭证、Share/Bucket、无默认验收根或 Prefix、固定破坏性确认和新建本地 JSON 报告。旧式仅凭
Endpoint 即启用且默认 `mediaflow-test` 的测试不得保留。验收根必须为空，清理只能处理白名单
生成对象；fake/mock 仍只计 UNIT PASS。

SMB 基础设施适配器必须按结构化 errno 映射常见服务端错误，至少包括 `ENOENT`、`EEXIST`、
`EACCES`/`EPERM`、超时和连接错误；不得依赖可能包含服务端文本的错误消息。目录枚举应复用
服务端已返回的条目元数据，且所有请求必须保持配置端口，避免隐式回退到 445。

Phase 19 持续与中断验收必须使用生产 Storage Adapter 和 OrganizerExecutor，在隔离空根执行
参数化批次、跨 S3 multipart 门槛的大对象流式传输、确定性源流中断、MOVE 保源、目标状态检查
和新的显式重试。报告必须记录批次数、对象字节数、实际最大单次读取、耗时、是否观察到部分
目标及清理结果。该验收不得引入生产自动重试、自动删除部分目标或 Rollback。

# 110. 最终核心原则

系统的实际执行链必须始终为：

```text
扫描
→ 解析
→ 识别类型
→ 元数据匹配
→ 确认媒体身份
→ 命名
→ 分类
→ 生成整理计划
→ 预演
→ 执行
→ 记录
```

其中：

**扫描不修改媒体。**

**识别不修改媒体。**

**元数据查询不修改媒体。**

**命名规则仅计算名称，不直接修改媒体。**

**分类规则仅计算目标位置，不直接移动媒体。**

**Planner 只生成整理计划，不修改媒体。**

**只有 Organizer Executor 可以执行实际文件操作。**

这一原则必须贯穿整个系统设计，以确保识别、规则配置、预演与实际文件操作完全分离，降低错误整理以及数据损坏风险。
