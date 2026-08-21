# TASK: Phase 4 — S3 / Cloudflare R2 Storage Adapter

## Goal

实现 `S3Storage` / `R2Storage`，让系统可以通过统一 `Storage` 抽象访问：

- Amazon S3
- Cloudflare R2
- 其他 S3 Compatible Object Storage

本阶段只实现 S3 / R2 Storage Adapter。

不要开始：

- ResourceLibrary Scanner
- Recognition
- TMDB
- Naming
- Classification
- Organizer
- Web UI

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

确认以下阶段仍然通过：

```text
Phase 1 LocalStorage
Phase 2 SMBStorage
Phase 3 OpenListStorage
```

不得破坏已有：

```text
Storage interface
StorageCapabilities
StorageError

LocalStorage
SMBStorage
OpenListStorage
```

---

# 2. Core Requirement

S3/R2 必须作为统一 Storage Adapter：

```text
Storage
   ↑
S3Storage
   ↑
R2 compatible configuration
```

如果当前技术栈允许，优先采用：

```text
一个 S3Storage 实现
+
不同 Endpoint / Provider 配置
```

支持：

```text
AWS S3
Cloudflare R2
Generic S3 Compatible
```

不要因为 R2 单独复制一套几乎相同的 Storage 实现。

---

# 3. Important Object Storage Difference

必须明确：

S3 / R2 是对象存储，不是传统文件系统。

不要假设存在真实：

```text
Directory
Rename
HardLink
SoftLink
Atomic Move
```

系统应在 Adapter 内统一对象存储语义。

业务层仍然看到：

```text
Storage path
StorageEntry
StorageStat
```

但 infrastructure 层必须正确处理对象存储特性。

---

# 4. Configuration

实现配置模型，至少支持：

```text
Storage ID
Name

Provider
    AWS_S3
    CLOUDFLARE_R2
    S3_COMPATIBLE

Endpoint
Bucket
Region

AccessKey
SecretKey

RootPrefix

ReadOnly

ConnectTimeout
RequestTimeout

MaxConcurrency

MultipartThreshold
MultipartPartSize

ForcePathStyle if required
```

根据当前 SDK 实际需要调整。

不要将 AWS SDK / R2 SDK 类型泄漏到 domain。

---

# 5. Cloudflare R2 Support

R2 使用 S3-compatible API。

R2 配置应允许：

```text
Endpoint
Bucket
AccessKey
SecretKey
```

不要将 AWS Region 等假设硬编码到 R2。

如果 SDK 要求 region：

使用 adapter 内部兼容处理。

---

# 6. Generic S3-Compatible Support

架构必须允许类似：

```text
MinIO
Ceph
其他 S3 Compatible
```

通过自定义：

```text
Endpoint
Region
ForcePathStyle
```

工作。

不要为每一种 S3-compatible 服务建立新的业务模块。

---

# 7. Secret Safety

以下必须视为敏感信息：

```text
AccessKey
SecretKey
SessionToken if supported
Authorization
Signed URL
Presigned URL
```

要求：

- 不输出到 INFO 日志
- 不输出到 DEBUG 日志
- 不包含在异常文本
- 不出现在最终报告
- 默认配置序列化用于日志时必须脱敏

测试必须覆盖：

```text
AccessKey / SecretKey redaction
```

---

# 8. S3 Client Abstraction

建议基础设施内部建立：

```text
S3ClientAdapter
```

或等价 abstraction。

封装：

```text
ListObjects

HeadObject

GetObject
PutObject

CreateMultipartUpload
UploadPart
CompleteMultipartUpload
AbortMultipartUpload

CopyObject

DeleteObject

DeleteObjects if safely required
```

单元测试应能够使用：

```text
FakeS3Client
MockS3Client
```

避免依赖真实云账户。

---

# 9. DTO Isolation

AWS SDK / S3 SDK 返回对象：

```text
Object
HeadObjectResponse
GetObjectResponse
ListObjectsResponse
```

等不得泄漏到 domain。

统一转换：

```text
StorageEntry
StorageStat
StorageError
```

---

# 10. RootPrefix

S3Storage 必须支持：

```text
RootPrefix
```

例如：

```text
Bucket:
media

RootPrefix:
downloads/
```

业务层路径：

```text
movies/a.mkv
```

映射到：

```text
downloads/movies/a.mkv
```

业务层不得知道 Bucket Key 的完整结构。

---

# 11. Key Normalization

建立统一 Key Resolver。

处理：

```text
/
重复 /
.
..

leading slash
trailing slash

unicode
spaces
special characters
```

业务层使用 Storage-relative path。

内部统一生成 S3 object key。

---

# 12. Path Traversal

虽然 S3 key 理论上允许：

```text
..
```

但 MediaFlow 的 Storage abstraction 不允许借此逃逸 RootPrefix。

必须拒绝：

```text
../outside.mkv
../../outside.mkv
folder/../../../outside.mkv
```

不能生成 RootPrefix 外的 object key。

建立专项测试。

---

# 13. Directory Semantics

S3 没有真实目录。

统一使用：

```text
Prefix
+
Delimiter "/"
```

模拟目录。

系统内部仍然可以返回：

```text
StorageEntry(type=directory)
```

但必须明确这是逻辑目录。

---

# 14. Directory Marker Objects

某些 S3-compatible 服务可能存在：

```text
folder/
```

形式的 zero-byte directory marker object。

实现必须正确处理：

```text
marker object
prefix-only directory
```

不要在 List 中产生重复目录。

---

# 15. List

实现：

```text
List(path)
```

要求：

- 非递归列出
- 返回当前层文件
- 返回当前层逻辑目录
- 使用 delimiter
- 正确处理 pagination
- 不一次性假定只有第一页

返回：

```text
StorageEntry
```

测试：

```text
empty prefix
files
subdirectories
directory markers
pagination
missing logical directory
permission denied
authentication failure
timeout
```

---

# 16. Pagination

必须完整处理 S3 pagination。

模拟：

```text
page 1
page 2
page 3
```

最终结果必须完整。

不得：

```text
只读取第一页
```

也不得产生无限循环。

---

# 17. Stat

实现：

```text
Stat(path)
```

文件：

使用类似：

```text
HeadObject
```

获取：

```text
size
modifiedAt
etag if useful
contentType if useful
```

目录：

需要根据：

```text
Prefix existence
Directory marker
```

判断逻辑目录是否存在。

返回统一 StorageStat。

---

# 18. Exists

实现：

```text
Exists(path)
```

要求：

```text
file exists -> true
logical directory exists -> true
missing -> false
```

但以下错误：

```text
authentication failure
permission denied
connection failure
timeout
invalid path
```

不得转换为 false。

---

# 19. Read

实现：

```text
Read(path)
```

通过：

```text
GetObject streaming body
```

返回流。

禁止：

```text
entire object -> memory
```

影视资源可能超过：

```text
10GB
50GB
100GB
```

因此必须保持 streaming。

测试：

```text
success
streaming
not found
permission denied
timeout
connection failure
```

---

# 20. Range Read

如果当前 Storage interface 支持：

```text
Range Read
```

或随机读取能力，可以实现 S3 Range 请求。

如果当前接口没有，不要在本阶段为了 Range Read 大幅重构。

可以：

```text
预留 capability / future work
```

并在 progress 中说明。

---

# 21. Write / PutObject

实现：

```text
Write(path, stream)
```

小文件可以：

```text
PutObject
```

大文件必须支持：

```text
Multipart Upload
```

不得整文件加载到内存。

---

# 22. Multipart Upload

支持：

```text
MultipartThreshold
MultipartPartSize
```

例如：

```text
small object
→ PutObject

large object
→ Multipart Upload
```

实现：

```text
CreateMultipartUpload
↓
UploadPart...
↓
CompleteMultipartUpload
```

失败时：

```text
AbortMultipartUpload
```

不得遗留无意义未完成 multipart upload。

---

# 23. Multipart Tests

Fake / Mock 测试至少覆盖：

```text
small file uses PutObject

large file uses Multipart

multipart success

part failure
→ AbortMultipartUpload

complete failure
→ appropriate cleanup/error

readonly
```

不需要真实上传 GB 级文件。

使用可控测试 stream。

---

# 24. Target Conflict

所有写操作默认：

```text
Target exists
→ Conflict
```

不得因为：

```text
PutObject
```

天然可以覆盖而静默覆盖现有对象。

在写入前执行必要冲突检测。

未来是否允许 Overwrite：

由：

```text
OrganizePolicy
```

显式决定。

---

# 25. CreateDirectory

由于 S3 没有真实目录，需要定义统一行为。

推荐：

```text
CreateDirectory(path)
```

创建逻辑目录 marker：

```text
path/
```

zero-byte object

或者：

如果当前架构允许：

```text
no-op logical directory creation
```

但行为必须在 architecture 中明确。

优先保持：

```text
Local / SMB / OpenList / S3
```

上层语义一致。

---

# 26. Directory Create Requirements

如果采用 marker：

```text
CreateDirectory("Movies")
```

创建：

```text
Movies/
```

测试：

```text
create
already exists
file conflict
readonly
```

注意：

```text
Movies
```

文件与：

```text
Movies/
```

目录之间的冲突语义需要明确。

---

# 27. Copy

实现：

```text
Copy(source, target)
```

优先使用：

```text
server-side CopyObject
```

优势：

- 不下载到客户端
- 不占用本机大量流量
- 适合大型对象

要求：

```text
source missing -> NotFound
target exists -> Conflict
readonly -> error
```

Source 保留。

---

# 28. Large Object Server-Side Copy

部分 S3 服务对单次 CopyObject 大小存在限制。

如果当前 SDK / 服务需要：

```text
multipart copy
```

对于大对象实现或预留：

```text
UploadPartCopy
```

如果本阶段不完整支持超大 server-side copy：

必须：

- 明确记录限制
- 不静默 fallback 到内存 copy
- 返回明确 Unsupported / limitation error

不要虚假声明完整支持。

---

# 29. Move

S3 没有真正原子 Rename / Move。

因此逻辑：

```text
Move
=
Copy
+
Delete
```

但是必须非常谨慎。

这是本阶段最重要的语义差异之一。

---

# 30. Move Atomicity

必须明确：

```text
S3 Move is NOT atomic.
```

执行过程：

```text
Copy source -> target
↓
verify target
↓
Delete source
```

只有目标 Copy 成功以后才允许删除 Source。

如果 Copy 失败：

```text
Source 保持
Target 不应被认为成功
```

如果 Delete 失败：

```text
Source 和 Target 可能同时存在
```

必须返回：

```text
PartialSuccess / ambiguous move
```

或项目现有等价错误。

不得把这种情况返回普通 Success。

---

# 31. Move Target Verification

完成 Copy 后，在删除 source 之前至少验证：

```text
target exists
```

如果可以低成本获得：

```text
size
etag
checksum
```

可做进一步验证。

但不要假设所有 ETag 都是内容 MD5：

multipart upload 的 ETag 语义不同。

---

# 32. Move Conflict

Target 已存在：

```text
Move
→ Conflict
```

不得执行：

```text
Delete Source
```

---

# 33. Move Failure Tests

必须覆盖：

```text
copy success + delete success
→ success

copy failure
→ source preserved

copy success + delete failure
→ partial failure
→ source preserved
→ target exists

target conflict
→ source preserved

readonly
```

这是高优先级测试。

---

# 34. Rename

如果统一 Storage Interface 存在：

```text
Rename
```

S3 adapter 可以内部将其实现为：

```text
Move
```

但必须保持：

```text
non-atomic
```

语义记录。

不要让业务层误以为对象存储 Rename 是原子操作。

---

# 35. Delete

实现：

```text
Delete(path)
```

文件：

```text
DeleteObject
```

逻辑目录：

必须特别安全。

普通：

```text
Delete("Movies/")
```

不得自动：

```text
Delete every object under Movies/
```

除非存在明确：

```text
RecursiveDelete
```

接口和上层授权。

---

# 36. Directory Delete Safety

默认行为：

```text
empty logical directory
→ 可以删除 marker

non-empty prefix
→ Conflict / DirectoryNotEmpty
```

不得使用：

```text
List prefix
→ batch delete all
```

作为普通 Delete。

这是重要安全要求。

---

# 37. HardLink

对象存储不支持 filesystem HardLink。

因此：

```text
CanHardLink = false
```

调用：

```text
HardLink
```

返回：

```text
UnsupportedOperation
```

绝不 fallback。

---

# 38. SoftLink

同样：

```text
CanSoftLink = false
```

调用返回：

```text
UnsupportedOperation
```

不要用：

```text
redirect object
metadata
shortcut
```

伪装 SoftLink。

---

# 39. Capabilities

S3/R2 应根据实现输出：

```text
CanMove
CanCopy
CanDelete
CanHardLink
CanSoftLink
```

注意：

```text
CanMove = true
```

如果表示：

```text
logical Move supported
```

必须在 architecture 中记录：

```text
implemented as Copy + Delete
non-atomic
```

如果当前 capability model 无法表达：

```text
AtomicMove = false
```

建议增加更精确能力，例如：

```text
MoveSemantics
    NativeAtomic
    NativeNonAtomic
    Emulated
    Unsupported
```

或者：

```text
CanAtomicMove
```

但不要为了这一点做无意义大重构。

如果扩展 capability：

必须同步所有 Storage Adapter 和测试。

---

# 40. ReadOnly

`ReadOnly = true` 时允许：

```text
List
Stat
Exists
Read
```

禁止：

```text
Write
CreateDirectory
Copy
Move
Delete
HardLink
SoftLink
```

必须在发送远程 mutation 请求之前拒绝。

测试需要验证：

```text
FakeS3Client mutation call count == 0
```

---

# 41. Authentication Error Mapping

统一转换：

```text
invalid credentials
missing credentials
expired credentials
signature mismatch
```

到：

```text
AuthenticationFailed
```

或当前项目等价 StorageError。

不得泄漏 SecretKey。

---

# 42. S3 Error Mapping

至少处理：

```text
NoSuchKey
NoSuchBucket

AccessDenied

InvalidAccessKeyId
SignatureDoesNotMatch

PreconditionFailed
Conflict

SlowDown
RequestTimeout

ServiceUnavailable
InternalError

NetworkFailure
```

转换为统一 StorageError。

---

# 43. HTTP / SDK Error Handling

不要只根据异常字符串判断。

优先使用：

```text
SDK error type
status code
service error code
```

集中在：

```text
S3ErrorMapper
```

或等价模块。

---

# 44. Retry

对安全的读操作：

```text
List
Stat
Exists
Read
```

可以执行受限自动重试。

适用于：

```text
timeout
connection reset
429
SlowDown
selected 5xx
```

---

# 45. Mutation Retry Safety

对：

```text
Write
Copy
Move
Delete
```

不能盲目重试。

例如：

```text
Delete request timeout
```

客户端不知道：

```text
服务器到底删没删
```

需要：

- 根据具体操作的幂等性设计
- 使用 SDK 安全 retry 能力
- 或重新确认状态

不得产生：

```text
重复上传
错误删除
错误 Move
```

---

# 46. Rate Limiting / SlowDown

支持：

```text
429
503 SlowDown
```

使用：

```text
Retry-After
```

如果存在。

否则指数退避。

限制最大重试次数。

---

# 47. Timeout

支持：

```text
ConnectTimeout
RequestTimeout
```

以及根据 SDK 能力：

```text
ReadTimeout
WriteTimeout
```

避免大对象上传因为不合理 timeout 失败。

需要区分：

```text
connection establishment timeout
```

和：

```text
large stream duration
```

不要给 100GB 上传设置不合理的整体短超时。

---

# 48. Concurrency

支持：

```text
MaxConcurrency
```

限制：

```text
List
Head
Get
Put
Copy
Multipart part upload
```

的并发。

Multipart 并发需要受：

```text
MaxConcurrency
```

或专门：

```text
MultipartConcurrency
```

限制。

---

# 49. Memory Safety

大对象操作必须避免：

```text
object -> byte[]
```

整个读入内存。

检查：

```text
Read
Write
Copy fallback
Multipart upload
```

代码路径。

单元测试可以通过：

```text
guarded stream
```

验证没有执行完整 materialization。

---

# 50. Health Check

实现适合 S3 的测试连接能力。

至少确认：

```text
Endpoint reachable
credentials valid
Bucket reachable
RootPrefix accessible if applicable
```

可以使用低成本请求：

```text
HeadBucket
ListObjects MaxKeys=1
```

根据服务兼容性选择。

错误必须明确区分：

```text
AuthFailed
BucketNotFound
PermissionDenied
Timeout
ConnectionFailed
```

---

# 51. Bucket Safety

Storage 配置固定：

```text
Bucket
+
RootPrefix
```

业务层不得：

```text
切换其他 Bucket
```

也不得通过 path 输入：

```text
s3://other-bucket/...
```

访问其他 Bucket。

测试：

```text
bucket escape attempt
```

必须被拒绝。

---

# 52. Presigned URL

如果未来为了 Read 使用 presigned URL：

本阶段只能作为 infrastructure 内部临时机制。

不得：

```text
持久化为永久文件地址
日志输出完整签名 URL
```

当前若无需 presigned URL，不要额外实现。

---

# 53. Metadata / Content-Type

S3 对象可能具有：

```text
ContentType
Metadata
```

本阶段只保留必要字段。

不要开始做影视 Metadata 逻辑。

S3 object metadata：

```text
≠
TMDB media metadata
```

两者必须保持完全独立。

---

# 54. Unit Tests

所有单元测试使用：

```text
FakeS3Client
MockS3Client
fake HTTP transport
```

不得依赖真实 AWS/R2。

至少覆盖以下。

---

# 55. Configuration Tests

测试：

```text
AWS config

R2 config

generic S3 config

missing bucket

invalid endpoint

secret redaction
```

---

# 56. Root / Path Tests

测试：

```text
RootPrefix resolution

normal relative path

../ traversal

../../ traversal

leading slash

duplicate slash

bucket escape

s3:// URL rejection
```

---

# 57. List Tests

```text
empty prefix

files

subdirectories

directory marker

pagination

permission denied

auth failed

timeout
```

---

# 58. Stat Tests

```text
file

logical directory

missing

permission denied

invalid response
```

---

# 59. Exists Tests

```text
file true

directory true

missing false

auth failure != false

timeout != false
```

---

# 60. Read Tests

```text
stream success

missing

permission denied

network interruption

large-stream behavior
```

---

# 61. Write Tests

```text
small file PutObject

large file Multipart

target conflict

readonly

part failure aborts multipart

complete failure handled

secret not logged
```

---

# 62. CreateDirectory Tests

根据实现：

```text
marker create

already exists

file conflict

readonly
```

---

# 63. Copy Tests

```text
server-side copy success

source preserved

source missing

target conflict

readonly

copy service failure
```

如果实现 multipart copy：

增加对应测试。

---

# 64. Move Tests

必须覆盖：

```text
copy + delete success

copy failure
→ source preserved

delete failure
→ source preserved
→ target exists
→ partial failure

target exists
→ conflict
→ no source delete

readonly
```

这是本阶段最关键测试组之一。

---

# 65. Delete Tests

```text
file delete

missing behavior

empty marker directory

non-empty logical directory protected

readonly

permission denied
```

---

# 66. Capability Tests

验证：

```text
CanHardLink == false
CanSoftLink == false
```

以及其他 capability 与实际实现一致。

如果增加：

```text
CanAtomicMove
```

S3/R2 必须为：

```text
false
```

---

# 67. Optional MinIO Integration Test

推荐允许使用：

```text
MinIO
```

作为本地 S3-compatible Integration Test。

但默认测试环境没有 MinIO 时应：

```text
SKIP
```

不要硬编码服务。

例如通过：

```text
TEST_S3_ENDPOINT
TEST_S3_BUCKET
TEST_S3_ACCESS_KEY
TEST_S3_SECRET_KEY
```

启用。

---

# 68. Optional Real R2 Integration Test

允许使用：

```text
TEST_R2_ENDPOINT
TEST_R2_BUCKET
TEST_R2_ACCESS_KEY
TEST_R2_SECRET_KEY
```

开启真实 R2 集成测试。

默认：

```text
SKIPPED
```

不得把真实凭证写进源码。

---

# 69. Integration Test Safety

所有真实 S3/R2 测试只能操作：

```text
RootPrefix/mediaflow-test/<unique-id>/
```

测试过程中只允许：

```text
create own test objects
read own test objects
copy own test objects
move own test objects
delete own test objects
```

严禁：

```text
列出整个生产 Bucket
删除已有 Prefix
修改未知对象
```

---

# 70. Integration Test Cases

启用环境时至少测试：

```text
health check

list

create logical directory

upload small test file

read

copy

move

delete

cleanup
```

测试内容可以是：

```text
mediaflow-s3-test
```

不需要真实媒体。

---

# 71. Regression Tests

必须重新运行：

```text
LocalStorage tests
SMBStorage tests
OpenListStorage tests
```

全部保持 PASS。

---

# 72. Storage Contract Tests

如果当前项目还没有：

建议建立统一：

```text
StorageContractTests
```

用于验证所有 Adapter 的共同语义，例如：

```text
Exists
Conflict
ReadOnly
Path traversal
List
Stat
```

但不要为了本阶段重构整个测试体系。

如果容易实现，可将：

```text
Local
SMB
OpenList
S3
```

共同部分抽成 contract tests。

---

# 73. DryRun Regression

确认：

```text
Planner
DryRun
```

没有因为新增 S3/R2 adapter 而执行：

```text
PutObject
CopyObject
DeleteObject
CreateDirectory
```

DryRun 必须仍为：

```text
zero mutation
```

---

# 74. No FFprobe

全仓库搜索：

```text
ffprobe
ffmpeg
```

不得新增 runtime dependency。

---

# 75. Do Not Implement

本阶段禁止：

```text
ResourceLibrary Scanner

File Stability Detector

FilenameParser

RecognitionRule

RecognitionType Engine

TMDB

Naming

Classification

Organizer

Web UI
```

S3 的：

```text
ListObjects
```

只是 Storage 功能。

不要借此开始做媒体 Scanner。

---

# 76. Documentation

完成后更新：

```text
docs/progress.md
```

标记：

```text
Phase 4 S3/R2 Storage — Completed
```

更新：

```text
docs/architecture.md
```

至少记录：

```text
S3/R2 architecture

RootPrefix mapping

logical directory semantics

multipart upload

server-side copy

Move = Copy + Delete

Move is non-atomic

directory delete safety

retry policy

capabilities

R2 compatibility

known limitations
```

---

# 77. Important Architecture Note

必须在 architecture 中明确写出：

```text
S3/R2 Move is an emulated operation.

Move(source, target):

1. Verify target does not exist.
2. Copy source to target.
3. Verify target.
4. Delete source.

The operation is not atomic.

If step 4 fails, both source and target may exist.

This must be surfaced as a partial/ambiguous failure,
not as success.
```

这个原则必须长期保留。

---

# 78. Final Validation

根据项目技术栈运行全部适用：

```text
unit tests

storage regression tests

formatter

lint

typecheck

build
```

可选 integration 未配置时：

```text
SKIPPED
```

并注明原因。

---

# 79. Completion Criteria

Phase 4 只有满足以下条件才完成：

- S3Storage 实现完成。
- Cloudflare R2 配置可以通过 S3-compatible adapter 表达。
- Generic S3-compatible 可配置。
- SDK 类型未泄漏到 domain。
- Secret 不出现在日志。
- Bucket 固定。
- RootPrefix 正确。
- Path traversal 被阻止。
- List 正常。
- Pagination 正常。
- Logical Directory 行为明确。
- Stat 正常。
- Exists 正常。
- Read streaming。
- Write streaming。
- Multipart Upload 正常。
- Multipart failure 会 Abort。
- Target 不静默覆盖。
- Copy 优先 server-side。
- Move 使用安全 Copy + Verify + Delete。
- Move 非原子语义被记录。
- Delete 不会递归误删整个 prefix。
- HardLink 明确 unsupported。
- SoftLink 明确 unsupported。
- ReadOnly enforcement 正常。
- Error mapping 正常。
- Timeout 正常。
- Retry 有边界。
- Capabilities 与实际行为一致。
- LocalStorage regression PASS。
- SMBStorage regression PASS。
- OpenListStorage regression PASS。
- DryRun zero mutation PASS。
- docs/progress.md 已更新。
- docs/architecture.md 已更新。
- 未开始下一阶段。

---

# 80. Final Report

完成后必须输出以下内容。

## Phase 4 Result

```text
PASS
```

或：

```text
FAIL
```

---

## Changed Files

列出所有：

```text
Added
Modified
Deleted
```

文件。

---

## S3/R2 Implementation

说明：

```text
SDK/library used

AWS S3 configuration

Cloudflare R2 configuration

generic S3-compatible configuration

RootPrefix handling

directory semantics

read strategy

write strategy

multipart strategy

copy strategy

move strategy

delete safety
```

---

## Storage Capabilities

输出实际：

```text
CanMove =
CanCopy =
CanDelete =
CanHardLink =
CanSoftLink =
```

如果增加：

```text
CanAtomicMove =
```

也需要输出。

---

## Move Semantics

明确报告：

```text
Native / Emulated

Atomic / Non-atomic
```

并说明 Delete failure 后的行为。

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

```text
LocalStorage: PASS/FAIL
SMBStorage: PASS/FAIL
OpenListStorage: PASS/FAIL
DryRun: PASS/FAIL
```

---

## Quality

```text
Build:
Lint:
Typecheck:
Formatter:
```

没有配置则：

```text
N/A
```

---

## Security

逐项：

```text
Bucket isolation              PASS/FAIL
RootPrefix isolation          PASS/FAIL
Path traversal               PASS/FAIL
Secret redaction             PASS/FAIL
No silent overwrite          PASS/FAIL
Safe prefix delete           PASS/FAIL
ReadOnly enforcement         PASS/FAIL
Multipart cleanup            PASS/FAIL
Move source safety           PASS/FAIL
Business Storage boundary    PASS/FAIL
```

---

## Integration Tests

如果没有测试环境：

```text
MinIO: SKIPPED
R2: SKIPPED
Reason: integration environment not configured.
```

不得将 SKIPPED 写为 PASS。

---

## Known Limitations

如实说明，例如：

```text
S3 Move is non-atomic

HardLink unsupported

SoftLink unsupported

Large server-side Copy may require multipart copy

ETag is not treated as universal content hash

Logical directories are prefix based
```

---

## Final Recommendation

全部阻塞项通过后，只输出：

```text
Phase 4 accepted. Storage foundation is ready for ResourceLibrary and Scanner.
```

如果存在阻塞项：

```text
Phase 4 not accepted. Blocking issues remain.
```

不要自动开始 ResourceLibrary / Scanner。

最后更新：

`docs/progress.md`