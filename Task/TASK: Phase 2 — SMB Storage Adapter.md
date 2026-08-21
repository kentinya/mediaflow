# TASK: Phase 2 — SMB Storage Adapter

## Goal

实现 `SMBStorage`，让系统可以通过统一 `Storage` 抽象访问 SMB/CIFS 网络共享。

本阶段只实现 SMB Storage。

不要开始：

- OpenList
- S3 / R2
- Scanner
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

并检查：

```text
git status
git diff
```

确认 Phase 1 LocalStorage 当前测试仍然通过。

不要破坏已经稳定的：

```text
Storage interface
StorageCapabilities
StorageError
LocalStorage
```

---

# 2. Core Requirement

SMB 必须作为：

```text
Storage
   ↑
SMBStorage
```

的 Adapter 实现。

业务层不得知道：

```text
SMB协议细节
SMB客户端类型
Session
Share
Connection
具体SMB SDK
```

业务模块只能依赖统一 `Storage` interface。

---

# 3. SMB Configuration

实现 SMB 配置模型。

至少支持：

```text
Storage ID
Name

Host
Port

ShareName

Username
Password
Domain

RootPath

ReadOnly

ConnectTimeout
OperationTimeout

MaxConcurrency
```

其中：

```text
Port
```

默认可使用 SMB 标准端口。

不要把默认值散落在业务代码中。

---

# 4. Authentication

支持：

```text
用户名 + 密码
用户名 + 密码 + Domain
```

如果当前选择的 SMB 库支持匿名连接，可预留：

```text
Anonymous
```

但不要为了匿名支持大幅增加复杂度。

---

# 5. Secret Safety

以下字段属于敏感数据：

```text
Password
```

以及未来可能存在的认证信息。

要求：

- 不得在日志中输出明文。
- 不得在异常字符串中输出明文。
- `Debug` 日志也不得输出。
- 配置对象的默认 `toString` / serialize-for-log 不得泄漏密码。

测试至少覆盖：

```text
Password does not appear in logs/errors
```

---

# 6. SMB Client Abstraction

不要让 `SMBStorage` 的领域行为与某一个第三方 SMB SDK 强耦合。

建议内部再建立：

```text
SMBClient
```

或等价 infrastructure abstraction。

例如：

```text
Connect
Disconnect

List
Stat

OpenRead
OpenWrite

CreateDirectory

Rename
Move
Copy
Delete
```

这样单元测试可以使用：

```text
FakeSMBClient
MockSMBClient
```

而不需要真实 NAS。

---

# 7. Connection Lifecycle

需要明确 SMB 连接生命周期。

至少考虑：

```text
Connect
Session
Share
Reconnect
Close
```

要求：

- 不允许每个小操作无限创建连接而不释放。
- 不允许连接资源泄漏。
- 连接失败转换为统一 `StorageError`。
- Session/Share 断开时允许在合理条件下重新连接。
- Cancel / timeout 应能够结束挂起操作。

具体实现根据当前语言和 SMB SDK 决定。

---

# 8. Storage Capabilities

`SMBStorage` 必须返回自己的：

```text
StorageCapabilities
```

至少：

```text
CanMove
CanCopy
CanDelete
CanHardLink
CanSoftLink
```

不要简单复制 `LocalStorage` 能力。

SMB 是否支持某项操作，应基于：

```text
当前实现
当前协议库能力
已验证行为
```

进行声明。

如果本阶段未实现：

```text
HardLink
SoftLink
```

则：

```text
CanHardLink = false
CanSoftLink = false
```

并在调用时返回：

```text
UnsupportedOperation
```

不得伪装支持。

---

# 9. RootPath Isolation

SMBStorage 也必须拥有：

```text
RootPath
```

例如：

```text
Share = Media

RootPath = Downloads
```

则业务层路径：

```text
movies/a.mkv
```

映射为：

```text
\\server\Media\Downloads\movies\a.mkv
```

业务层不得直接处理 UNC 路径。

---

# 10. Path Safety

沿用 LocalStorage 的安全原则。

必须阻止：

```text
../
../../
```

逃逸 SMBStorage RootPath。

测试：

```text
../outside
../../outside
folder/../../../outside
```

全部必须失败。

注意处理：

```text
/
\

重复separator
Windows风格路径
Unix风格路径
绝对UNC路径
```

不要允许用户通过：

```text
\\server\other-share
```

绕过当前 Storage 配置访问其他 Share。

---

# 11. List

实现：

```text
List(path)
```

返回统一：

```text
StorageEntry
```

必须支持：

```text
文件
目录
```

测试：

```text
空目录
文件列表
目录列表
不存在目录
权限失败
连接失败
路径逃逸
```

不要将 SMB SDK 返回对象泄漏给 domain。

---

# 12. Stat

实现：

```text
Stat(path)
```

至少输出：

```text
path
type
size
modifiedAt
```

测试：

```text
普通文件
目录
不存在
权限失败
```

---

# 13. Exists

实现：

```text
Exists(path)
```

要求：

```text
存在 -> true
不存在 -> false
```

但：

```text
认证失败
连接失败
非法路径
```

不能简单返回 false。

必须返回对应错误。

---

# 14. Read

实现：

```text
Read(path)
```

必须适合大型影视文件。

优先：

```text
streaming
```

禁止：

```text
whole file -> memory
```

测试：

```text
正常读取
读取不存在
读取目录
连接中断
权限失败
```

单元测试使用 Fake/Mock。

---

# 15. Write

实现：

```text
Write(path, data)
```

要求：

- 支持流式写入。
- ReadOnly 时禁止。
- 权限失败映射到统一错误。
- 父目录不存在行为必须明确。
- 不得静默覆盖已有文件。

如果 Storage interface 当前支持 overwrite 参数，则严格按照显式参数执行。

否则：

```text
TargetExists
→ Conflict
```

---

# 16. CreateDirectory

实现：

```text
CreateDirectory(path)
```

要求：

```text
创建普通目录
创建多级目录
目录已存在
同名文件冲突
ReadOnly
权限错误
连接错误
```

目录已存在可以设计为幂等。

但必须和 LocalStorage 行为尽量一致。

---

# 17. Copy

实现：

```text
Copy(source, target)
```

本阶段只需要支持：

```text
同一个 SMBStorage / Share 内复制
```

不要实现跨 Storage Copy。

跨 Storage 将由未来 Organizer / Transfer 层负责。

要求：

- Source 不存在 -> NotFound
- Target 已存在 -> Conflict
- ReadOnly -> ReadOnly
- 复制成功后 Source 保留
- Target 内容一致

如果 SMB SDK 没有 server-side Copy：

可以使用：

```text
Read stream
→ Write stream
```

但必须流式执行。

不得整文件加载进内存。

---

# 18. Move

实现：

```text
Move(source, target)
```

本阶段限定：

```text
同一个 SMBStorage
同一个 Share
```

如果底层支持 Rename/Move：

优先使用原生能力。

禁止 SMBStorage 在失败后未经策略允许自动执行：

```text
Copy + Delete
```

如果 Move 无法原生完成：

返回明确错误。

未来由更高层决定 fallback。

---

# 19. Delete

实现：

```text
Delete(path)
```

要求和 LocalStorage 安全策略保持一致。

普通 Delete：

```text
删除文件
删除空目录
```

不得默认递归删除非空目录。

测试：

```text
删除文件
删除不存在文件
删除空目录
删除非空目录
ReadOnly
权限错误
```

---

# 20. HardLink

如果当前 SMB 实现不能稳定支持：

不要实现。

设置：

```text
CanHardLink = false
```

调用：

```text
HardLink()
```

返回：

```text
UnsupportedOperation
```

不得：

```text
fallback Copy
```

---

# 21. SoftLink

同样：

如果没有明确、稳定支持：

```text
CanSoftLink = false
```

并返回：

```text
UnsupportedOperation
```

---

# 22. ReadOnly Mode

SMBStorage 必须支持：

```text
ReadOnly = true
```

允许：

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

必须在执行远程 SMB 写操作之前就阻止。

不要先请求服务器然后才发现 ReadOnly。

---

# 23. Unified Error Mapping

SMB SDK 的异常不得直接泄漏到业务层。

映射到现有：

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

ConnectionFailed
ConnectionLost
Timeout

AuthenticationFailed

IOError
Unknown
```

如果现有 StorageError 尚无：

```text
ConnectionFailed
AuthenticationFailed
```

可以合理扩展 StorageError。

但必须：

- 更新 LocalStorage 相关代码兼容性。
- 更新 architecture 文档。
- 跑全部 Storage tests。

---

# 24. Reconnect

对于典型临时断开：

```text
ConnectionReset
SessionExpired
TransportClosed
```

SMB 层应提供有限的 reconnect 能力。

但是：

禁止无限重试。

建议：

```text
Operation
↓
connection lost
↓
reconnect once / configured retry
↓
retry idempotent operation
```

注意：

对于：

```text
Write
Move
Delete
```

等可能产生副作用的操作，不允许盲目重试造成重复操作。

如果无法确认安全：

返回错误给上层处理。

---

# 25. Timeout

支持：

```text
ConnectTimeout
OperationTimeout
```

超时统一转换成：

```text
StorageError.Timeout
```

不得让网络调用无限挂起。

---

# 26. Concurrency

支持：

```text
MaxConcurrency
```

至少在 SMBStorage 层提供并发控制基础。

例如：

```text
semaphore
connection pool
```

具体实现依据当前技术栈。

目的：

避免扫描大量文件时同时产生数百个 SMB 请求。

---

# 27. Large File Safety

影视文件可能：

```text
10GB
50GB
100GB+
```

因此：

```text
Read
Write
Copy
```

必须支持流式处理。

禁止：

```text
readAllBytes
buffer entire media file
```

测试不需要创建超大文件。

Fake SMB 测试验证 API 是 stream-oriented 即可。

---

# 28. Unit Tests

本阶段单元测试不得依赖真实 NAS。

使用：

```text
FakeSMBClient
MockSMBClient
```

至少覆盖：

### Connection

```text
connect success
connect failure
authentication failure
timeout
reconnect
```

### List

```text
empty
files
directories
missing
permission denied
```

### Stat

```text
file
directory
missing
```

### Exists

```text
true
false
connection error must not become false
```

### Read

```text
success
missing
permission denied
connection failure
```

### Write

```text
success
target conflict
readonly
permission denied
```

### CreateDirectory

```text
success
existing
file conflict
readonly
```

### Copy

```text
success
source preserved
target exists
source missing
readonly
```

### Move

```text
success
source removed
target exists
source missing
readonly
```

### Delete

```text
file
empty directory
non-empty directory denied
readonly
```

### Security

```text
../
../../
UNC escape
other share escape
```

### Capabilities

确保：

```text
declared capabilities == implemented behavior
```

---

# 29. Optional SMB Integration Test

如果项目环境允许，可以增加：

```text
SMB integration test
```

但是必须默认：

```text
SKIPPED
```

除非明确提供测试环境变量。

例如：

```text
TEST_SMB_HOST
TEST_SMB_SHARE
TEST_SMB_USERNAME
TEST_SMB_PASSWORD
```

没有这些变量：

```text
skip integration test
```

不得连接任何硬编码 SMB 地址。

---

# 30. Integration Test Safety

真实 SMB Integration Test 如果启用：

必须只操作：

```text
专用测试目录
```

例如：

```text
/mediaflow-test/<unique-id>/
```

测试结束清理自己创建的数据。

严禁：

```text
扫描整个共享
修改已有媒体
删除共享中的未知文件
```

---

# 31. Logging

记录必要信息：

```text
StorageID
Host
Share
Operation
RelativePath
Duration
Result
```

禁止：

```text
Password
Authentication token
完整凭证
```

用户名是否记录根据当前日志安全策略决定。

---

# 32. LocalStorage Regression

SMB 实现完成后必须重新运行：

```text
LocalStorage tests
```

确保没有因为扩展：

```text
StorageError
StorageCapabilities
Storage interface
```

而破坏 Phase 1。

---

# 33. DryRun Regression

重新运行 Planner / DryRun 安全测试。

确认加入 SMBStorage 后：

```text
Planner
```

仍然不会实际连接并执行写操作。

DryRun 不允许：

```text
Move
Copy
Delete
Write
CreateDirectory
```

---

# 34. No FFprobe Regression

搜索：

```text
ffprobe
ffmpeg
```

不得因为 SMB 功能新增任何 runtime dependency。

---

# 35. Do Not Implement

本阶段禁止实现：

```text
OpenListStorage

S3Storage
R2Storage

ResourceLibrary scanner

Filename parser

Recognition rule engine

TMDB

Naming

Classification

Organizer

Web UI
```

---

# 36. Documentation

完成后更新：

```text
docs/progress.md
```

加入：

```text
Phase 2 SMBStorage
```

如果 Storage abstraction / error model 发生变化：

同步更新：

```text
docs/architecture.md
```

至少记录：

```text
SMB connection lifecycle
Storage capabilities
SMB path mapping
error mapping
reconnect policy
```

---

# 37. Final Validation

根据当前项目技术栈运行全部适用：

```text
unit tests
storage tests
formatter
lint
typecheck
build
```

如果存在默认关闭的 SMB Integration Test：

报告：

```text
SKIPPED - no SMB test environment configured
```

不得把 Skip 写成 Pass。

---

# 38. Completion Criteria

Phase 2 只有满足以下条件才算完成：

- SMBStorage 已实现。
- 使用统一 Storage interface。
- 没有向业务层泄漏 SMB SDK 类型。
- List 正常。
- Stat 正常。
- Exists 正常。
- Read 正常。
- Write 正常。
- CreateDirectory 正常。
- Copy 正常。
- Move 正常。
- Delete 行为安全。
- ReadOnly 正常。
- RootPath 安全。
- Path Traversal 被拦截。
- 不允许逃逸到其他 SMB Share。
- Target 不静默覆盖。
- SMB 密码不出现在日志。
- 网络错误统一映射。
- Timeout 已处理。
- Reconnect 行为明确。
- Capabilities 与实际行为一致。
- 大文件接口支持流式处理。
- LocalStorage 回归测试通过。
- 全部相关单元测试通过。
- docs/progress.md 已更新。

---

# 39. Final Report

完成后输出：

## Phase 2 Result

```text
PASS
```

或：

```text
FAIL
```

---

## Changed Files

列出所有修改文件。

---

## SMB Implementation

说明：

```text
SMB library used
connection model
session model
path mapping
reconnect behavior
timeout behavior
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

---

## Tests

输出：

```text
Total:
Passed:
Failed:
Skipped:
```

---

## Quality Checks

输出真实：

```text
Build:
Lint:
Typecheck:
Formatter:
```

未配置写：

```text
N/A
```

---

## Security Checks

逐项报告：

```text
Root path isolation          PASS/FAIL
Path traversal              PASS/FAIL
Other-share escape          PASS/FAIL
ReadOnly enforcement        PASS/FAIL
No silent overwrite         PASS/FAIL
Safe directory delete       PASS/FAIL
Secret redaction            PASS/FAIL
Business Storage boundary   PASS/FAIL
```

---

## Integration Test

如果没有真实 SMB：

```text
SKIPPED
Reason:
No SMB integration environment configured.
```

如果有：

列出实际使用的测试目录和结果。

不得输出密码。

---

## Problems Found

列出开发过程中发现的问题。

---

## Known Limitations

如：

```text
HardLink unsupported
SoftLink unsupported
cross-share Move unsupported
server-side Copy unsupported
```

如实说明。

---

## Final Recommendation

只能输出：

```text
Phase 2 accepted. Ready for the next Storage adapter.
```

或者：

```text
Phase 2 not accepted. Blocking issues remain.
```

不要自动开始 OpenList 或 S3/R2。

最后更新：

`docs/progress.md`