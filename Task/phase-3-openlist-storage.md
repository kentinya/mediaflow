# TASK: Phase 3 — OpenList Storage Adapter

## Goal

实现 `OpenListStorage`，让系统可以通过统一 `Storage` 抽象访问 OpenList 中的文件与目录。

本阶段只实现 OpenList Storage。

不要开始：

- S3 / R2
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

然后检查：

```text
git status
git diff
```

确认以下阶段仍保持通过：

```text
Phase 1 LocalStorage
Phase 2 SMBStorage
```

不要破坏已有：

```text
Storage interface
StorageCapabilities
StorageError
LocalStorage
SMBStorage
```

---

# 2. Core Requirement

OpenList 必须实现为：

```text
Storage
   ↑
OpenListStorage
```

业务层不得知道：

```text
OpenList HTTP API
具体 URL 路径
HTTP Client
Token Header
OpenList Response DTO
```

这些只能存在于 infrastructure / adapter 层。

---

# 3. OpenList Configuration

实现 OpenList 配置模型，至少支持：

```text
Storage ID
Name

BaseURL

Authentication
Token / supported credential

RootPath

ReadOnly

ConnectTimeout
RequestTimeout

MaxConcurrency
```

可以根据当前 OpenList API 实际认证形式调整字段，但必须保持业务层与具体 API 解耦。

---

# 4. Verify Current OpenList API

实现前必须确认当前 OpenList 官方 API。

只使用：

- OpenList 官方文档
- OpenList 官方仓库中明确的 API 定义

不要根据模型记忆猜 API。

确认至少：

```text
认证方式
文件列表接口
文件信息接口
创建目录接口
重命名接口
移动接口
复制接口
删除接口
上传/写入接口
下载/读取接口
```

将实际使用的 API 和版本记录到：

```text
docs/architecture.md
```

不要把 API 细节泄漏到 domain。

---

# 5. Secret Safety

OpenList 认证信息属于敏感数据。

例如：

```text
Token
Authorization
Username
Password
```

要求：

- 不写入普通日志
- 不写入 Debug 日志
- 不出现在异常字符串中
- 不出现在最终 Task 报告中
- 默认序列化日志必须脱敏

建立测试：

```text
OpenList secret redaction
```

---

# 6. OpenList Client Abstraction

建议建立内部基础设施接口：

```text
OpenListClient
```

或等价抽象。

用于封装：

```text
Authenticate / PrepareAuth

List
Stat

OpenRead / Download
OpenWrite / Upload

CreateDirectory

Rename
Move
Copy
Delete
```

`OpenListStorage` 不应到处直接拼 HTTP 请求。

单元测试通过：

```text
FakeOpenListClient
MockOpenListClient
```

完成。

---

# 7. DTO Isolation

OpenList API 返回的数据必须转换成内部：

```text
StorageEntry
StorageStat
StorageError
```

禁止将：

```text
OpenList API DTO
HTTP response object
JSON response model
```

泄漏到 domain / application 层。

---

# 8. RootPath

OpenListStorage 必须支持：

```text
RootPath
```

例如：

```text
OpenList RootPath:
/Downloads
```

业务层：

```text
movies/a.mkv
```

最终映射为 OpenList 中：

```text
/Downloads/movies/a.mkv
```

业务层只使用相对 Storage 路径。

---

# 9. Path Normalization

OpenList 主要使用逻辑路径，因此必须统一处理：

```text
/
重复 /
.
..
URL encoding
Unicode
特殊字符
空格
```

统一内部 path representation。

不要让不同操作：

```text
List
Stat
Move
Copy
Delete
```

各自实现一套不同的路径拼接逻辑。

---

# 10. Path Traversal

必须阻止：

```text
../
../../
```

逃逸 RootPath。

测试：

```text
../outside
../../outside
folder/../../../outside
```

不得生成 RootPath 之外的 OpenList 路径。

即使 OpenList API 本身会拒绝，也必须在客户端本地先阻止。

---

# 11. Connection / Health Check

实现适合 OpenList 的连接测试能力。

至少能够验证：

```text
BaseURL 是否可达
认证是否有效
RootPath 是否存在/可访问
```

统一输出合理错误：

```text
ConnectionFailed
AuthenticationFailed
NotFound
PermissionDenied
Timeout
```

不要简单返回：

```text
false
```

隐藏真实原因。

---

# 12. List

实现：

```text
List(path)
```

要求：

- 获取指定目录内容
- 不递归
- 返回统一 `StorageEntry`
- 正确区分 file / directory
- 提取 size / modifiedAt（如 API 提供）
- 处理分页，如果 OpenList API 存在分页
- 不因为大目录一次把无限结果加载到内存

如果 API 是分页的：

必须实现完整分页或迭代式读取。

测试：

```text
empty directory
files
directories
multiple pages
missing path
permission denied
authentication failed
timeout
path traversal
```

---

# 13. Stat

实现：

```text
Stat(path)
```

输出统一：

```text
path
type
size
modifiedAt
```

如果 OpenList 没有专门 Stat API，而需要通过目录/文件详情接口实现，可以封装在 adapter 内。

业务层不关心实现方式。

测试：

```text
file
directory
missing
permission denied
invalid response
```

---

# 14. Exists

实现：

```text
Exists(path)
```

要求：

```text
exists -> true
not found -> false
```

但这些错误不能变成 false：

```text
authentication failure
connection failure
timeout
permission denied
invalid path
```

---

# 15. Read

实现：

```text
Read(path)
```

要求适合大型媒体。

优先：

```text
streaming response
download stream
```

禁止：

```text
download entire media into memory
```

需要考虑 OpenList 某些存储可能返回：

```text
raw URL
signed URL
redirect URL
proxy stream
```

将这些差异封装在 `OpenListClient` / adapter 内。

上层只获得统一 Read stream。

测试：

```text
success
missing
permission denied
redirect/raw-url behavior if applicable
timeout
connection failure
```

---

# 16. Write / Upload

实现：

```text
Write(path, stream/data)
```

适配 OpenList 当前上传 API。

要求：

- 支持流式上传
- ReadOnly 时本地直接拒绝
- Target 已存在默认不得静默覆盖
- 父目录不存在行为明确
- 上传失败转换为统一错误

如果 OpenList API 对 overwrite 有独立选项：

默认应：

```text
overwrite = false
```

除非调用明确要求覆盖。

---

# 17. Large Upload Safety

禁止：

```text
read whole local/media file into memory
then HTTP upload
```

必须使用：

```text
stream
multipart streaming
chunked upload
```

或当前 API 能支持的大文件上传机制。

如果 OpenList API 或当前 SDK 对大文件上传存在限制，必须在：

```text
docs/progress.md
```

明确记录。

---

# 18. CreateDirectory

实现：

```text
CreateDirectory(path)
```

测试：

```text
success
nested directory
already exists
file conflict
readonly
permission denied
timeout
```

尽量与 LocalStorage / SMBStorage 的统一语义一致。

---

# 19. Rename

如果统一 Storage interface 有独立 Rename：

实现 OpenList Rename。

如果目前统一接口只用 Move：

可将 Rename 作为 OpenList 内部实现能力使用。

要求：

```text
Target exists -> Conflict
ReadOnly -> error
```

不得静默覆盖。

---

# 20. Move

实现：

```text
Move(source, target)
```

优先使用 OpenList API 原生 Move 能力。

本阶段限定：

```text
同一个 OpenListStorage 配置范围内
```

不要实现跨 Storage Move。

如果 OpenList API 的 Move 有限制：

例如只能：

```text
同 provider
同 storage
同 directory tree
```

必须通过 capability / 明确错误表达。

不要在 Move 失败后未经策略允许自动：

```text
Copy + Delete
```

---

# 21. Copy

实现：

```text
Copy(source, target)
```

优先使用 OpenList 原生 Copy API。

如果实际 OpenList API 没有稳定 server-side Copy，允许 adapter 使用：

```text
Read stream
→ Write stream
```

但必须：

- 流式
- 不整文件进内存
- Target 不静默覆盖
- Source 保留

本阶段只处理同一 OpenListStorage 内 Copy。

---

# 22. Delete

实现：

```text
Delete(path)
```

要求：

```text
file -> delete
empty directory -> delete if API supports
non-empty directory -> no implicit recursive deletion
```

如果 OpenList API 的 Delete 对目录天然是递归：

Storage adapter 必须提供安全保护。

普通 `Delete(path)` 不得因为 API 默认行为而递归删掉整个未知目录树。

如无法安全实现：

对非空目录返回：

```text
UnsupportedOperation
```

或安全冲突错误。

---

# 23. HardLink

OpenListStorage 默认：

```text
CanHardLink = false
```

除非官方 API 明确提供统一且可靠的硬链接能力。

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

# 24. SoftLink

同样默认：

```text
CanSoftLink = false
```

调用返回：

```text
UnsupportedOperation
```

除非 OpenList 官方 API 对所有目标后端都能提供可依赖语义。

不要把具体挂载后端偶尔支持的行为当成 OpenListStorage 通用能力。

---

# 25. Capabilities

`OpenListStorage` 必须根据实际实现返回：

```text
CanMove
CanCopy
CanDelete
CanHardLink
CanSoftLink
```

Capabilities 必须和实际调用行为一致。

如果某能力受服务器版本影响：

应考虑：

```text
capability discovery
```

或至少保守声明。

原则：

```text
宁可声明不支持
也不要声明支持但运行时经常失败
```

---

# 26. ReadOnly

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
Move
Copy
Delete
HardLink
SoftLink
```

必须在发起 OpenList 写请求之前拒绝。

测试通过 Fake Client 断言：

```text
no remote mutation request was made
```

---

# 27. HTTP Error Mapping

所有 HTTP / OpenList 错误转换为现有：

```text
StorageError
```

至少覆盖：

```text
NotFound
PermissionDenied
Conflict

InvalidPath
PathTraversal

ReadOnly
UnsupportedOperation

AuthenticationFailed

ConnectionFailed
ConnectionLost
Timeout

RateLimited

IOError
Unknown
```

如果 StorageError 当前没有：

```text
RateLimited
```

可以合理增加。

但必须跑：

```text
LocalStorage regression
SMBStorage regression
```

确保兼容。

---

# 28. HTTP Status Handling

至少正确处理：

```text
2xx
400
401
403
404
409
429
5xx
```

如果 OpenList API 用：

```text
HTTP 200 + business error code
```

表达失败，也必须正确识别。

不能只判断 HTTP Status。

---

# 29. Retry Policy

只对临时错误重试。

例如：

```text
connection reset
timeout
429
selected 5xx
```

不要对以下无限重试：

```text
401
403
404
409
invalid path
```

---

# 30. Retry Safety

对于幂等操作：

```text
List
Stat
Exists
Read
```

可以相对安全地自动重试。

对于：

```text
Write
Move
Copy
Delete
CreateDirectory
```

必须谨慎。

如果无法确认远端第一次操作是否已经成功：

不能盲目重复造成：

```text
duplicate file
double move
unexpected delete
```

此时应返回：

```text
ambiguous operation failure
```

或当前项目等价错误，交由未来上层处理。

---

# 31. Rate Limit

如果遇到：

```text
429
```

支持：

```text
Retry-After
```

如服务返回。

否则使用受限指数退避。

不要无限重试。

---

# 32. Timeout

支持：

```text
ConnectTimeout
RequestTimeout
```

不得让 HTTP 请求无限挂起。

---

# 33. Concurrency

通过：

```text
MaxConcurrency
```

限制 OpenList 并发请求。

尤其：

```text
List
Stat
Read
Copy
```

可能在未来扫描大量文件时同时发生。

建议使用：

```text
semaphore
request limiter
```

或当前技术栈合理方案。

---

# 34. API Version / Compatibility

OpenList 可能随版本变化。

不要在多个文件里散落 API endpoint。

集中定义：

```text
OpenListApiRoutes
```

或 client 层。

如果存在 server version endpoint，可预留：

```text
ServerInfo
```

但本阶段不要过度实现兼容矩阵。

---

# 35. Unit Tests

不得依赖真实 OpenList。

使用：

```text
mock HTTP server
fake transport
FakeOpenListClient
```

至少覆盖：

## Authentication

```text
valid auth
invalid auth
secret redaction
```

## List

```text
empty
file
directory
pagination
not found
403
timeout
```

## Stat

```text
file
directory
missing
malformed response
```

## Exists

```text
true
false
auth error not converted to false
```

## Read

```text
success
streaming
missing
timeout
```

## Write

```text
success
readonly
target conflict
permission denied
```

## Directory

```text
create
already exists
file conflict
```

## Copy

```text
success
target conflict
source missing
readonly
```

## Move

```text
success
target conflict
source missing
readonly
```

## Delete

```text
file
empty dir
non-empty dir protected
readonly
```

## Errors

```text
401
403
404
409
429
5xx
business error with HTTP 200
```

## Security

```text
../ traversal
../../ traversal
root escape
secret redaction
```

## Capabilities

```text
declared == behavior
```

---

# 36. Pagination Test

如果列表 API 支持分页，必须建立专项测试：

服务器模拟：

```text
page1 -> 100 items
page2 -> 100 items
page3 -> 25 items
```

最终：

```text
225 items
```

不得：

```text
只返回第一页
```

也不得出现无限分页。

---

# 37. Large File Stream Test

无需使用 GB 文件。

使用测试流验证：

```text
Read
Write
Copy fallback
```

没有调用：

```text
readAll
toByteArray entire stream
```

可以设计一个会在过度 buffering 时失败的 fake stream。

---

# 38. Optional Real OpenList Integration Test

允许增加真实 OpenList Integration Test。

默认必须：

```text
SKIPPED
```

只有配置环境变量后运行。

例如：

```text
TEST_OPENLIST_URL
TEST_OPENLIST_TOKEN
TEST_OPENLIST_ROOT
```

不得：

- 硬编码真实服务
- 把 Token 写进测试源码
- 把 Token 打印到测试报告

---

# 39. Integration Test Directory

真实测试只能操作专用目录：

```text
/mediaflow-test/<unique-id>/
```

或者由：

```text
TEST_OPENLIST_ROOT
```

指定的安全测试 Root 下。

不得：

```text
扫描整个OpenList
删除现有文件
修改现有媒体
```

---

# 40. Integration Test Cases

如果真实 OpenList 测试开启，至少验证：

```text
connection
list
create directory
write small test file
read
copy
move
delete own test file
cleanup
```

不要用真实大媒体。

测试内容：

```text
mediaflow-openlist-test
```

即可。

---

# 41. Logging

允许记录：

```text
StorageID
BaseURL host
Operation
RelativePath
Duration
Status
```

避免记录：

```text
完整 signed URL
Token
Authorization
Cookie
敏感 query 参数
```

如 OpenList 返回带临时签名的下载 URL：

日志必须脱敏或不记录完整 URL。

---

# 42. Cache / Raw URL

如果 OpenList 返回：

```text
raw_url
signed_url
```

不要把它长期当作媒体永久地址持久化。

它可能：

```text
过期
变化
包含token
```

只在当前 Read 请求范围内使用。

---

# 43. LocalStorage Regression

运行全部 LocalStorage 测试。

要求：

```text
PASS
```

---

# 44. SMBStorage Regression

运行全部 SMBStorage 测试。

要求：

```text
PASS
```

确保：

```text
StorageError
StorageCapabilities
Storage interface
```

扩展没有破坏已有实现。

---

# 45. Planner / DryRun Regression

重新验证：

```text
Planner
DryRun
```

不会因为加入 OpenListStorage 而开始执行远端写操作。

DryRun 必须仍然：

```text
zero mutation
```

---

# 46. No FFprobe

全仓库检查：

```text
ffprobe
ffmpeg
```

不得新增 runtime 依赖。

---

# 47. Do Not Implement

本阶段禁止：

```text
S3Storage
R2Storage

ResourceLibrary scanner

FilenameParser

RecognitionRule

TMDB

Naming

Classification

Organizer

Web UI
```

不要借 OpenList API 实现“顺便扫描媒体”。

List 只是 Storage 能力。

Scanner 属于后续业务模块。

---

# 48. Documentation

完成后更新：

```text
docs/progress.md
```

标记：

```text
Phase 3 OpenListStorage
```

如果：

```text
StorageError
StorageCapabilities
Storage interface
```

有变化，更新：

```text
docs/architecture.md
```

同时记录：

```text
OpenList official API source
authentication strategy
path mapping
pagination behavior
read strategy
write/upload strategy
copy strategy
move strategy
delete safety
retry policy
capabilities
known limitations
```

---

# 49. Final Validation

根据技术栈运行全部适用：

```text
unit tests
storage regression tests
formatter
lint
typecheck
build
```

如果真实 OpenList Integration Test 未配置：

必须写：

```text
SKIPPED
Reason: no OpenList integration environment configured.
```

---

# 50. Completion Criteria

Phase 3 只有满足以下条件才完成：

- OpenListStorage 实现完成。
- 使用统一 Storage interface。
- OpenList DTO 没有泄漏到 domain。
- 认证信息不进入日志。
- RootPath 正常。
- Path Traversal 被阻止。
- List 正常。
- Pagination 正常。
- Stat 正常。
- Exists 正常。
- Read 支持流式。
- Write 支持适合大文件的方式。
- CreateDirectory 正常。
- Copy 行为明确。
- Move 行为明确。
- Delete 不会意外递归删除未知目录树。
- ReadOnly 正常。
- Target 不静默覆盖。
- HardLink unsupported 行为明确。
- SoftLink unsupported 行为明确。
- HTTP 错误映射正确。
- 429 处理正确。
- Retry 行为受限且安全。
- Timeout 正常。
- Capabilities 与实现一致。
- LocalStorage regression PASS。
- SMBStorage regression PASS。
- 所有本阶段测试通过。
- docs/progress.md 更新。
- 没有实现 Phase 4。

---

# 51. Final Report

完成后输出：

## Phase 3 Result

```text
PASS
```

或：

```text
FAIL
```

---

## OpenList API

说明实际依据的：

```text
Official documentation / repository
API version if known
Authentication method
```

不要输出认证秘密。

---

## Changed Files

列出全部新增/修改文件。

---

## Implementation

说明：

```text
OpenList client design
authentication
path resolution
pagination
stream read
upload/write
copy
move
delete
retry
timeout
concurrency
```

---

## Storage Capabilities

输出：

```text
CanMove =
CanCopy =
CanDelete =
CanHardLink =
CanSoftLink =
```

---

## Tests

真实输出：

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

未配置使用：

```text
N/A
```

---

## Security

逐项：

```text
Root isolation             PASS/FAIL
Path traversal            PASS/FAIL
Secret redaction          PASS/FAIL
No silent overwrite       PASS/FAIL
Safe directory delete     PASS/FAIL
ReadOnly enforcement      PASS/FAIL
Business Storage boundary PASS/FAIL
```

---

## Integration Test

如果没有环境：

```text
SKIPPED
Reason: no OpenList integration environment configured.
```

---

## Known Limitations

如实说明，例如：

```text
HardLink unsupported
SoftLink unsupported
server-side copy depends on OpenList/backend capability
move behavior depends on backend capability
signed raw URLs are ephemeral
```

---

## Final Recommendation

只有通过所有阻塞项后输出：

```text
Phase 3 accepted. Ready for S3/R2 Storage.
```

否则：

```text
Phase 3 not accepted. Blocking issues remain.
```

不要自动开始下一阶段。

最后更新：

`docs/progress.md`