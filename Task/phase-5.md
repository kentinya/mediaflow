# TASK: Phase 5 — ResourceLibrary & Scanner

## Goal

实现资源库 `ResourceLibrary` 和统一扫描器 `Scanner`。

本阶段目标：

> 从 Local / SMB / OpenList / S3-R2 等已经完成的 Storage 中发现待处理文件，并建立统一文件索引。

扫描阶段只能读取 Storage。

扫描不得：

- 重命名文件
- 移动文件
- 复制文件
- 删除文件
- 调用 TMDB
- 解析影视作品身份
- 执行 Naming
- 执行 Classification
- 执行 Organizer

核心流程：

```text
ResourceLibrary
    ↓
Storage
    ↓
Scanner
    ↓
Filter
    ↓
File Stability Check
    ↓
File Discovery
    ↓
File Index
```

---

# 1. Before Starting

开始前必须阅读：

- `AGENTS.md`
- `TASK.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/progress.md`

检查：

```text
git status
git diff
```

确认已经验收通过：

```text
Phase 1 LocalStorage
Phase 2 SMBStorage
Phase 3 OpenListStorage
Phase 4 S3/R2 Storage
```

运行现有 Storage regression tests。

不得破坏现有 Storage abstraction。

---

# 2. ResourceLibrary Domain Model

实现：

```text
ResourceLibrary
```

至少包含：

```text
id
name

storageId

rootPath

enabled

scanMode

maxDepth

includeRules
excludeRules

fileExtensions

stabilityPolicy

createdAt
updatedAt
```

可以根据当前项目语言调整字段类型。

---

# 3. ResourceLibrary Responsibility

ResourceLibrary 只描述：

> 从哪个 Storage 的哪个范围发现资源。

例如：

```text
ResourceLibrary:
    name = Downloads
    storageId = nas-01
    rootPath = /Downloads
```

ResourceLibrary 不负责：

```text
Movie / TV识别
TMDB
Naming
Classification
Organize
```

---

# 4. Storage Boundary

Scanner 必须通过：

```text
Storage
```

interface 访问文件。

禁止 Scanner 根据 Storage 类型写类似：

```text
if LocalStorage ...
if SMBStorage ...
if OpenListStorage ...
if S3Storage ...
```

Scanner 不应该知道底层 Storage 类型。

统一使用：

```text
List
Stat
Exists
```

等 Storage abstraction。

---

# 5. Scanner Interface

设计统一：

```text
Scanner
```

建议输入：

```text
ResourceLibrary
ScanOptions
```

输出：

```text
ScanResult
```

或通过 streaming / iterator / callback 输出发现文件。

不要要求把大型媒体库所有文件一次性加载到内存。

---

# 6. ScanResult

至少记录：

```text
scanId

resourceLibraryId

startedAt
completedAt

directoriesVisited
filesVisited

mediaCandidates

ignored

unstable

errors
```

如果使用流式扫描，可以在任务结束后汇总这些统计数据。

---

# 7. File Discovery Model

扫描发现的每个文件转换为统一：

```text
DiscoveredFile
```

建议包含：

```text
storageId
resourceLibraryId

path
filename
extension

size
modifiedAt

discoveredAt

status
```

这里不要加入：

```text
title
year
season
episode
tmdbId
```

这些属于后续 Parser / Recognition / Metadata 阶段。

---

# 8. Supported File Extensions

资源库可以配置需要扫描的媒体扩展名。

默认可以支持：

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

扩展名：

- 大小写不敏感
- 用户可以增加
- 用户可以删除
- 不写死在 Scanner 核心逻辑中

例如：

```text
Movie.MKV
```

应该能够匹配：

```text
mkv
```

---

# 9. Include / Exclude Rules

实现扫描过滤规则。

至少支持：

```text
path
filename
extension
directory
glob
regex
```

规则可以分：

```text
Include
Exclude
```

---

# 10. Exclude Priority

Exclude 应优先用于阻止无意义目录继续扫描。

例如：

```text
**/.git/**
**/@eaDir/**
**/#recycle/**
**/.Trash/**
```

如果目录本身命中排除规则：

```text
不要继续递归该目录
```

避免浪费 Storage 请求。

---

# 11. Default Temporary File Rules

默认可忽略：

```text
*.part
*.tmp
*.download
*.crdownload
*.!qB
```

这些默认规则必须可配置。

不要把它们散落成硬编码判断。

---

# 12. Directory Traversal

Scanner 从：

```text
ResourceLibrary.rootPath
```

开始递归调用：

```text
Storage.List()
```

必须支持：

```text
maxDepth
```

例如：

```text
maxDepth = 0
```

只扫描根目录。

```text
maxDepth = 1
```

扫描：

```text
root
root/*
```

具体定义必须清晰并建立测试。

---

# 13. Unlimited Depth

如果允许：

```text
maxDepth = null
```

或：

```text
-1
```

表示无限深度：

必须仍然考虑：

- 防止无限递归
- 异常目录结构
- symlink cycle（对支持 symlink 的 Storage）

---

# 14. Symlink Handling

对于支持 symlink 的 Storage：

默认建议：

```text
不跟随目录 symlink
```

避免：

```text
A -> B
B -> A
```

造成无限扫描。

如果未来允许 FollowSymlink：

必须单独配置。

本阶段优先安全。

---

# 15. Scanner Memory Safety

禁止：

```text
recursive list entire storage
→ store millions of entries in one array
```

扫描必须适合：

```text
100,000+
1,000,000+
```

文件规模。

优先：

```text
streaming
iterator
queue
batched processing
```

---

# 16. Scanner Concurrency

支持配置：

```text
MaxScanConcurrency
```

用于控制多个目录：

```text
List
Stat
```

请求。

必须考虑远程 Storage：

```text
SMB
OpenList
S3
```

不能一次发出无限并发。

---

# 17. Per-Storage Concurrency

Scanner 同时必须尊重：

```text
Storage.MaxConcurrency
```

不得因为 Scanner 自己设置：

```text
100
```

而绕过：

```text
SMB MaxConcurrency = 5
```

Storage 本身仍是最终保护层。

---

# 18. Cancellation

Scanner 必须支持取消。

例如：

```text
CancelToken
Context
AbortSignal
```

根据技术栈选择。

取消后：

- 停止产生新的 List 请求
- 尽快结束当前任务
- 已经发现的结果允许保留
- Scan 状态为 Cancelled

---

# 19. File Stability Policy

实现：

```text
FileStabilityPolicy
```

用于防止正在下载/复制中的文件提前进入后续流程。

至少支持：

```text
minFileAge
minStableDuration
```

---

# 20. Minimum File Age

例如：

```text
minFileAge = 5 minutes
```

如果：

```text
now - modifiedAt < 5 minutes
```

则：

```text
status = Unstable
```

本次不进入待处理文件集合。

---

# 21. Stable Size Detection

如果启用：

```text
minStableDuration
```

需要能够判断：

> 文件在指定时间范围内大小未变化。

由于一次扫描无法凭空知道历史大小，因此应该通过：

```text
FileIndex
```

保存：

```text
previousSize
previousModifiedAt
lastSeenAt
stableSince
```

不要使用：

```text
sleep 10 minutes
然后重新 Stat
```

阻塞整个 Scanner。

---

# 22. Stability Across Scans

例如第一次扫描：

```text
movie.mkv
size = 10GB
```

记录：

```text
stableSince = null
```

第二次扫描：

```text
size = 10GB
modifiedAt unchanged
```

可以更新：

```text
stableSince
```

直到：

```text
now - stableSince >= minStableDuration
```

才认为稳定。

---

# 23. File Index

实现持久化：

```text
FileIndex
```

用于记录 Scanner 发现的文件。

至少保存：

```text
id

storageId
resourceLibraryId

path

filename
extension

size
modifiedAt

firstSeenAt
lastSeenAt

stableSince

scanStatus

createdAt
updatedAt
```

---

# 24. Unique Identity

文件索引不能只用：

```text
filename
```

唯一判断。

至少采用：

```text
storageId
+
resourceLibraryId
+
path
```

作为逻辑唯一键。

如架构已有更合理 FileID 设计，沿用。

---

# 25. Scan States

文件扫描状态建议：

```text
Discovered
Unstable
Ready
Ignored
Missing
Error
```

不要在本阶段加入：

```text
Recognized
Identified
Organized
```

这些属于后续阶段。

如果项目已有统一更大的 FileStatus enum，可合理复用，但不要产生混乱职责。

---

# 26. Full Scan

实现：

```text
Full Scan
```

行为：

```text
从 ResourceLibrary.rootPath
完整遍历允许范围
```

扫描结束后：

以前存在但这次没有发现的文件标记：

```text
Missing
```

不要立即从数据库删除。

---

# 27. Missing File Handling

例如数据库存在：

```text
A.mkv
```

本次完整扫描没发现：

```text
status = Missing
```

保存：

```text
missingSince
```

如果模型允许。

不要：

```text
DELETE FROM file_index
```

直接丢失历史。

---

# 28. Incremental Scan

实现基础：

```text
Incremental Scan
```

主要利用：

```text
path
size
modifiedAt
```

判断：

```text
New
Modified
Unchanged
```

---

# 29. Incremental Result

至少区分：

```text
New
Modified
Unchanged
Missing
```

后续阶段可以只让：

```text
New
Modified
```

进入 Parser。

---

# 30. Do Not Hash Every File

本阶段禁止为了判断变化：

```text
给所有影视文件计算完整 Hash
```

因为媒体文件可能几十 GB。

默认使用：

```text
size
modifiedAt
```

File Hash 属于未来重复检测等场景。

---

# 31. S3 Consideration

S3/R2：

```text
modifiedAt
size
object key
```

应通过统一 StorageEntry 提供。

Scanner 不允许直接依赖：

```text
ETag
S3 Object
Bucket
Prefix API
```

如果未来需要 ETag，可扩展 Storage metadata，但本阶段不要让 Scanner 与 S3 绑定。

---

# 32. Directory Errors

扫描某一个目录失败时：

例如：

```text
PermissionDenied
Timeout
ConnectionLost
```

默认不应该让整个大型资源库完全丢失结果。

应：

```text
记录 ScanError
继续处理其他可以扫描的目录
```

但：

```text
AuthenticationFailed
RootPath inaccessible
```

等根级错误可以导致 Task Failed。

定义合理 error severity。

---

# 33. ScanError

统一：

```text
ScanError
```

至少保存：

```text
path
operation
storageError
timestamp
```

不得吞掉错误。

---

# 34. Root Path Failure

如果：

```text
ResourceLibrary.rootPath
```

本身：

```text
NotFound
PermissionDenied
AuthenticationFailed
```

整个 Scan 应：

```text
Failed
```

而不是：

```text
Completed with 0 files
```

避免错误误导。

---

# 35. ResourceLibrary Validation

保存资源库配置时需要验证：

```text
storage exists
storage enabled

root path exists
root path is directory

extensions valid

regex valid
glob valid

maxDepth valid

stability values >= 0
```

---

# 36. ReadOnly Storage

ResourceLibrary 可以绑定：

```text
ReadOnly Storage
```

因为扫描只需要读取。

这是合法场景。

Scanner 不应该要求 Storage 可写。

---

# 37. Scanner Zero Mutation Rule

这是本阶段最重要验收条件之一。

Scanner 只能使用类似：

```text
List
Stat
Exists
Read metadata if required
```

绝对不能调用：

```text
Write
CreateDirectory
Move
Copy
Delete
HardLink
SoftLink
```

建立自动化测试锁定。

---

# 38. Fake Storage

建议建立：

```text
FakeStorage
```

用于 Scanner 单元测试。

可以模拟：

```text
directories
files
errors
latency
pagination if abstraction exposes it
```

不要用真实 NAS 作为单元测试。

---

# 39. LocalStorage Integration Tests

使用临时目录建立：

```text
root/
├── Movies/
│   ├── A.mkv
│   ├── B.mp4
│   └── downloading.mkv.part
├── TV/
│   └── Show.S01E01.mkv
├── Ignore/
│   └── C.mkv
└── readme.txt
```

配置：

```text
extensions:
mkv
mp4

exclude:
Ignore/**
*.part
```

预期发现：

```text
Movies/A.mkv
Movies/B.mp4
TV/Show.S01E01.mkv
```

不得发现：

```text
downloading.mkv.part
Ignore/C.mkv
readme.txt
```

---

# 40. Max Depth Tests

例如：

```text
root/
├── a.mkv
└── one/
    ├── b.mkv
    └── two/
        └── c.mkv
```

必须建立明确测试：

```text
maxDepth=0
maxDepth=1
maxDepth=2
unlimited
```

确保定义不会之后反复变化。

---

# 41. Include Tests

例如 Include：

```text
Movies/**
```

则：

```text
TV/**
```

不得进入结果。

---

# 42. Exclude Tests

例如：

```text
**/sample/**
*.tmp
```

确保目录级排除能够阻止继续递归。

---

# 43. Extension Tests

至少测试：

```text
movie.mkv
movie.MKV
movie.MkV
```

均正确。

测试：

```text
movie.txt
```

被忽略。

---

# 44. Stability Tests

至少覆盖：

```text
new recent file -> Unstable

old file -> Ready

same size across scans
→ stable timer progresses

size changed
→ stable timer resets

modifiedAt changed
→ stable timer resets

stable duration reached
→ Ready
```

---

# 45. Incremental Scan Tests

第一次：

```text
A.mkv
B.mkv
```

结果：

```text
A New
B New
```

第二次无变化：

```text
A Unchanged
B Unchanged
```

修改 A：

```text
A Modified
B Unchanged
```

删除 B：

在 Full Scan 情况：

```text
B Missing
```

---

# 46. Duplicate Scan Safety

同一个 ResourceLibrary 不应同时运行两个 Full Scan。

至少提供：

```text
scan lock
resource library lock
```

防止：

```text
Scan A
Scan B
```

同时修改 FileIndex 状态。

如果当前 Task 系统尚未完整实现，可提供最小锁机制和测试。

---

# 47. Multiple ResourceLibraries

允许：

```text
ResourceLibrary A
ResourceLibrary B
```

绑定同一个 Storage 的不同 RootPath。

FileIndex 必须能够正确区分。

---

# 48. Overlapping Libraries

例如：

```text
Library A = /Downloads
Library B = /Downloads/Movies
```

这是可能产生重复发现的危险配置。

至少：

- 检测并警告
- 或明确允许但按不同 ResourceLibrary 建立不同索引

不要静默假定它们不存在重叠。

记录设计决定到 architecture。

---

# 49. Scan Task

将扫描接入当前 Task 基础设施。

任务类型：

```text
ScanTask
```

至少包含：

```text
taskId
resourceLibraryId
mode

status

startedAt
completedAt

progress

statistics
errors
```

---

# 50. Scan Task Status

至少：

```text
Pending
Scanning
Completed
PartialSuccess
Failed
Cancelled
```

不要在本阶段引入 Recognition 状态。

---

# 51. Progress

Scanner 应能够报告：

```text
directoriesVisited
filesVisited
candidatesFound
ignored
unstable
errors
```

不要承诺无法可靠计算的：

```text
exact percentage
```

如果扫描前不知道目录总量。

可以使用：

```text
indeterminate progress
+
counts
```

---

# 52. Logging

INFO 级别记录：

```text
Scan started
ResourceLibrary
StorageID
RootPath

Scan completed

directories
files
candidates
ignored
unstable
errors
duration
```

---

# 53. Debug Logging

DEBUG 可记录：

```text
directory visited

file included
file excluded

rule matched

file unstable reason

FileIndex transition

Storage error
```

避免默认 INFO 对数十万文件逐文件打印。

---

# 54. Logging Volume

大媒体库扫描时：

```text
100,000 files
```

不能在 INFO 输出：

```text
100,000 lines
```

逐文件日志只允许：

```text
DEBUG / TRACE
```

---

# 55. Metrics

如果项目已有 metrics abstraction，可记录：

```text
scan directories/sec
scan files/sec

storage list duration

scan error count
```

如果没有，不要为了本阶段引入大型 observability 框架。

---

# 56. Persistence

FileIndex 应通过 repository abstraction 持久化。

例如：

```text
FileIndexRepository
```

支持：

```text
FindByPath
Upsert
MarkMissing
ListByResourceLibrary
```

Scanner 不应直接到处写 SQL。

---

# 57. Batch Persistence

为了支持大型资源库：

不要：

```text
每发现一个文件
→ 一个独立数据库 transaction
```

如果当前数据库设计允许，使用：

```text
batch upsert
transaction batches
```

避免明显性能问题。

测试不要求做极限 benchmark，但架构需要支持。

---

# 58. Transaction Safety

Full Scan 的 Missing 标记需要避免：

```text
扫描失败一半
→ 把后半部分全部标记 Missing
```

只有扫描达到足够完整状态后，才能安全执行全量 Missing reconciliation。

如果 Scan：

```text
Failed
Cancelled
```

默认不得把未访问文件标记 Missing。

这是高优先级安全规则。

---

# 59. PartialSuccess Missing Behavior

如果只有某些子目录扫描失败：

必须谨慎处理这些失败目录下旧索引。

不要把：

```text
PermissionDenied目录
```

下所有旧文件错误标记 Missing。

可以：

```text
保留旧状态
+
记录scan error
```

---

# 60. Acceptance: No Mutation

使用：

```text
FakeStorage
```

统计方法调用次数。

执行完整 Scan 后必须：

```text
Write calls = 0
CreateDirectory calls = 0
Move calls = 0
Copy calls = 0
Delete calls = 0
HardLink calls = 0
SoftLink calls = 0
```

---

# 61. Storage Regression

重新运行：

```text
LocalStorage
SMBStorage
OpenListStorage
S3/R2Storage
```

全部测试。

要求：

```text
PASS
```

---

# 62. DryRun Regression

重新运行已有：

```text
Planner / DryRun
```

安全测试。

要求：

```text
zero mutation PASS
```

---

# 63. No FFprobe

搜索：

```text
ffprobe
ffmpeg
```

不得新增 runtime dependency。

Scanner 不需要检查视频内部参数。

---

# 64. Do Not Implement

本阶段严禁开始：

```text
FilenameParser

PathParser media parsing

RecognitionRule

RecognitionType resolution

Metadata Provider

TMDB

Candidate matching

Naming

Classification

OrganizePlanner业务完善

OrganizerExecutor

媒体文件实际整理

Web UI
```

特别注意：

```text
Scanner发现：
The.Matrix.1999.mkv
```

本阶段只输出：

```text
filename = The.Matrix.1999.mkv
```

不得输出：

```text
title = The Matrix
year = 1999
```

这属于下一阶段。

---

# 65. Documentation

更新：

```text
docs/progress.md
```

标记：

```text
Phase 5 ResourceLibrary & Scanner
```

同时更新：

```text
docs/architecture.md
```

至少记录：

```text
ResourceLibrary responsibility

Scanner responsibility

Storage boundary

Full scan

Incremental scan

FileIndex

Stability detection

Missing reconciliation

Cancellation

Concurrency

No-mutation guarantee
```

---

# 66. Completion Criteria

Phase 5 只有满足以下条件才完成：

- ResourceLibrary domain model 完成
- ResourceLibrary validation 完成
- Scanner abstraction 完成
- Scanner 可通过统一 Storage 工作
- 不依赖具体 Storage 类型
- 文件扩展名过滤正常
- Include rules 正常
- Exclude rules 正常
- Directory pruning 正常
- maxDepth 正常
- symlink cycle 有安全策略
- File Stability 基础完成
- Stability 跨扫描工作
- FileIndex 持久化完成
- Full Scan 完成
- Incremental Scan 完成
- New / Modified / Unchanged 正常
- Missing reconciliation 安全
- Failed/Cancelled Scan 不误标 Missing
- Partial directory failure 不误标 Missing
- Scanner 支持 cancellation
- Scanner 并发受控
- 大目录扫描架构不是全量内存加载
- ScanTask 完成
- Scanner zero mutation 测试通过
- Storage regressions 全部 PASS
- DryRun regression PASS
- 不存在 FFprobe runtime
- docs/progress.md 更新
- docs/architecture.md 更新
- 未开始 Parser / Recognition

---

# 67. Final Report

完成后必须输出：

## Phase 5 Result

```text
PASS
```

或：

```text
FAIL
```

---

## Changed Files

列出：

```text
Added
Modified
Deleted
```

---

## ResourceLibrary

说明：

```text
domain model
validation
storage binding
filter configuration
stability policy
```

---

## Scanner

说明：

```text
traversal model
concurrency
cancellation
maxDepth
include/exclude
extension filtering
```

---

## FileIndex

说明：

```text
unique identity
persistence
batching
state transitions
missing detection
```

---

## Stability

说明：

```text
minFileAge
stable duration
size/modified time comparison
state reset behavior
```

---

## Tests

输出真实：

```text
Total:
Passed:
Failed:
Skipped:
```

---

## Regression

输出：

```text
LocalStorage: PASS/FAIL
SMBStorage: PASS/FAIL
OpenListStorage: PASS/FAIL
S3/R2Storage: PASS/FAIL
DryRun: PASS/FAIL
```

---

## Scanner Safety

必须输出：

```text
Write calls: 0
CreateDirectory calls: 0
Move calls: 0
Copy calls: 0
Delete calls: 0
HardLink calls: 0
SoftLink calls: 0
```

---

## Quality

输出：

```text
Build:
Lint:
Typecheck:
Formatter:
```

不存在则：

```text
N/A
```

---

## Known Limitations

如实说明。

例如：

```text
No filesystem watcher yet

Incremental scan is metadata-based

No hashing

No media identity parsing

No TMDB

Directory symlinks are not followed
```

---

## Final Recommendation

所有阻塞项通过后输出：

```text
Phase 5 accepted. Ready for media filename/path parsing.
```

否则：

```text
Phase 5 not accepted. Blocking issues remain.
```

不要自动开始下一阶段。

最后更新：

`docs/progress.md`