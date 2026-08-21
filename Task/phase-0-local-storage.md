# TASK: Phase 1 — LocalStorage Implementation

## Goal

完成 Storage 层第一阶段实现：**LocalStorage**。

本阶段只实现本地文件系统存储适配器，并验证 Storage 抽象是否足够支撑后续 Organizer。

不要开始实现 SMB、OpenList、S3/R2、TMDB、Scanner、Recognition 或 Web UI。

---

# 1. Before Starting

开始前必须阅读：

- `AGENTS.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/progress.md`

然后检查：

- 当前 Storage 接口
- 当前领域模型
- 当前测试
- 当前 git status
- 当前未提交修改

不得覆盖或删除已有有效实现。

如果 Phase 0 已经存在部分 LocalStorage 骨架，应在现有代码基础上补全，而不是重新建立第二套实现。

---

# 2. Scope

本阶段需要完成：

```text id="l5hy96"
Storage abstraction
        ↓
LocalStorage
        ↓
完整本地文件操作
        ↓
Storage capabilities
        ↓
统一错误处理
        ↓
路径安全
        ↓
完整自动化测试
```

---

# 3. Storage Interface

检查现有 Storage Interface。

至少应能够表达以下能力：

```text id="5tb1kj"
List
Stat
Exists

Read
Write

CreateDirectory

Move
Copy

Delete

HardLink
SoftLink
```

如果已有接口名称不同，但语义一致，可以保留。

不要仅为了名称一致进行无意义重构。

如果发现现有接口确实无法满足需求，可以调整，但必须：

1. 尽量保持兼容。
2. 更新相关测试。
3. 在最终报告中说明原因。
4. 更新 `docs/architecture.md`。

---

# 4. Storage Capabilities

实现或完善：

```text id="d0chyr"
StorageCapabilities
```

至少包含：

```text id="dqd5jo"
CanMove
CanCopy
CanDelete
CanHardLink
CanSoftLink
```

LocalStorage 应根据当前操作系统和实现能力正确声明。

不要假设所有平台能力完全相同。

---

# 5. Storage Entry / Stat Model

统一定义目录列表及文件信息模型。

建议至少包含：

```text id="0106i0"
StorageEntry

name
path

type
    file
    directory
    symlink
    other

size

modifiedAt
```

Stat 至少支持：

```text id="qfb4f6"
path
exists
type
size
modifiedAt
```

如项目已有模型，优先复用。

不要重复定义相同领域对象。

---

# 6. LocalStorage Configuration

LocalStorage 至少配置：

```text id="hghkx4"
Storage ID
Name
RootPath
ReadOnly
```

所有相对路径必须在：

```text id="v3195i"
RootPath
```

之下解析。

业务层不应该传入或依赖真实操作系统绝对路径。

---

# 7. Path Safety

这是本阶段重点。

必须防止路径逃逸。

例如：

```text id="0o6ekr"
../
../../
```

不得使操作越过 LocalStorage RootPath。

以下输入必须被拒绝或安全规范化：

```text id="qkz595"
../secret.txt

../../etc/passwd

folder/../../../outside

绝对路径指向RootPath之外
```

需要考虑：

```text id="9r16kc"
.
..

重复分隔符

绝对路径

相对路径

符号链接导致的路径逃逸
```

不得允许用户通过恶意路径访问 Storage Root 之外的数据。

为路径安全建立专项测试。

---

# 8. List

实现：

```text id="3r5l7j"
List(path)
```

要求：

- 列出指定目录。
- 返回文件和目录。
- 不递归。
- 返回统一 `StorageEntry`。
- 目录不存在返回统一 StorageError。
- 输入是文件而不是目录时返回合理错误。
- 不允许访问 Root 之外。

测试：

```text id="g7f6my"
空目录
包含文件
包含子目录
目录不存在
传入文件路径
路径逃逸
```

---

# 9. Stat

实现：

```text id="jm4zcz"
Stat(path)
```

返回至少：

```text id="teh6we"
文件/目录类型
文件大小
修改时间
```

测试：

```text id="ohz87l"
普通文件
目录
不存在路径
软链接（如果平台支持）
```

---

# 10. Exists

实现：

```text id="mlzntb"
Exists(path)
```

要求：

```text id="rrd2lt"
存在 → true
不存在 → false
```

不存在不应作为异常抛出。

但非法路径、路径逃逸等仍应报错。

---

# 11. Read

实现：

```text id="idvdwq"
Read(path)
```

根据当前项目语言和架构选择：

```text id="a7suf7"
stream
reader
bytes
```

中的合理形式。

要求：

- 可以读取普通文件。
- 不应把大型媒体文件无条件一次加载到内存。
- 优先采用流式读取接口。
- 读取目录时报错。
- 不存在时报统一错误。
- Root 外路径禁止读取。

---

# 12. Write

实现：

```text id="a16ixd"
Write(path, data)
```

要求：

- 支持创建文件。
- 支持写入内容。
- ReadOnly Storage 禁止写入。
- 父目录不存在时，行为必须明确。

建议：

默认不隐式创建多级父目录。

目录创建由：

```text id="1qpbky"
CreateDirectory
```

负责。

如果项目现有设计已经规定自动创建父目录，则沿用现有设计并测试。

---

# 13. CreateDirectory

实现：

```text id="f85dq9"
CreateDirectory(path)
```

要求：

- 创建目录。
- 支持必要的递归目录创建。
- 已存在目录时行为明确且幂等。
- 同名文件存在时报冲突。
- ReadOnly 时禁止创建。

测试：

```text id="e974qv"
创建一级目录
创建多级目录
重复创建
同名文件冲突
ReadOnly
路径逃逸
```

---

# 14. Copy

实现：

```text id="93plu6"
Copy(source, target)
```

要求：

- 默认复制文件。
- Source 必须存在。
- Target 已存在时不得静默覆盖。
- 默认返回 Conflict。
- 是否允许覆盖由未来 Organizer Policy 决定。

LocalStorage 自身不应该擅自执行：

```text id="syet85"
Overwrite
Rename
```

策略。

Storage Adapter 只执行明确指定的底层操作。

测试：

```text id="yo3t43"
正常复制
Source不存在
Target已存在
ReadOnly
复制到子目录
内容一致
```

---

# 15. Move

实现：

```text id="s9lysi"
Move(source, target)
```

要求：

- 正常移动。
- Source 不存在时报错。
- Target 已存在时不得静默覆盖。
- 移动后 Source 不存在。
- Target 内容与原文件一致。
- ReadOnly 时禁止执行。

如果底层文件系统 rename/move 失败，例如跨文件系统场景：

本阶段不要擅自：

```text id="ugz161"
Copy + Delete
```

除非 Storage Interface 已明确规定这种行为。

LocalStorage 的 Move 应保持行为可预测。

未来由 OrganizePolicy / Storage Adapter 能力决定是否允许 fallback。

---

# 16. Delete

实现：

```text id="98ta9c"
Delete(path)
```

必须注意：

Storage 层可以提供 Delete 能力，

但业务层默认策略仍然：

```text id="8b49w3"
禁止直接删除用户媒体
```

本阶段 Delete 只作为底层接口实现和测试。

要求：

- 删除指定文件。
- ReadOnly 禁止。
- 不存在时返回明确错误或幂等行为。

行为必须统一并写测试。

目录删除行为需要明确。

建议：

```text id="806s05"
默认只允许删除空目录
```

不得默认递归删除未知目录树。

如果需要递归删除，应使用独立、明确的接口，不能由普通 Delete 隐式实现。

---

# 17. HardLink

实现：

```text id="pbfkd5"
HardLink(source, target)
```

要求：

- 仅当系统/文件系统支持时。
- Source 必须存在。
- Target 不得已存在。
- 不得自动 fallback 到 Copy。
- 不得自动 fallback 到 Move。

如果不支持：

返回统一：

```text id="srrnlo"
UnsupportedOperation
```

或项目已有等价错误。

测试需要根据运行平台能力进行条件处理。

不要因为 CI 平台不支持某项能力导致所有测试不可运行。

---

# 18. SoftLink

实现：

```text id="7ystfw"
SoftLink(source, target)
```

要求同 HardLink：

- 支持则创建。
- 不支持则返回明确能力错误。
- 不得自动 fallback。
- Target 已存在时报冲突。

测试需要兼容不同 OS / CI 权限环境。

---

# 19. ReadOnly Mode

LocalStorage 必须支持：

```text id="zdtlsn"
ReadOnly = true
```

ReadOnly 下允许：

```text id="lk3amb"
List
Stat
Exists
Read
```

禁止：

```text id="am4oyj"
Write
CreateDirectory
Move
Copy
Delete
HardLink
SoftLink
```

所有禁止行为必须返回统一错误类型。

建立专项测试。

---

# 20. Unified Storage Errors

Storage 层不得向领域层直接泄漏大量 OS 原始异常。

建立统一错误模型。

至少区分：

```text id="b1zohs"
NotFound
PermissionDenied
AlreadyExists / Conflict
InvalidPath
PathTraversal
ReadOnly
UnsupportedOperation
IOError
Unknown
```

保留原始异常作为：

```text id="whqbo5"
cause
```

或内部 Debug 信息可以接受。

但上层应依赖统一 StorageError。

---

# 21. Error Logging

错误日志可以包含：

```text id="487m2u"
StorageID
Operation
Path
ErrorCode
```

不得包含：

```text id="8fhnga"
敏感凭证
用户文件内容
不必要的完整文件数据
```

LocalStorage 当前没有密码，但仍遵循整个项目统一日志规范。

---

# 22. Atomicity / Partial Files

对于 Write / Copy 等操作，考虑失败产生半写入目标文件的问题。

如果当前技术栈合理，建议采用：

```text id="xybkeg"
写入临时文件
↓
完成
↓
atomic rename
```

或者其他安全实现。

但不要为了这一点过度复杂化。

如果本阶段不实现原子写入，应：

- 明确记录到 `docs/progress.md`
- 标记为后续 Organizer 安全增强项

不要假装已经保证原子性。

---

# 23. Large File Safety

本项目目标文件主要是大型影视媒体。

因此禁止明显存在以下实现：

```text id="ph5t9r"
read entire 80GB file into RAM

copy by loading whole file into memory
```

Copy / Read / Write 必须使用适合大文件的流式机制。

测试不需要真正创建超大文件，但代码设计必须支持大文件。

---

# 24. Business Layer Boundary Check

完成 LocalStorage 后，全仓库检查：

除：

```text id="kbj0q3"
Storage infrastructure
tests
```

以外，业务模块不得直接使用底层文件系统写操作。

例如根据语言检查：

```text id="bsaa1l"
fs.rename
fs.copyFile
fs.unlink

os.rename
os.remove

shutil.copy
shutil.move

Path.unlink
Path.rename

File.Move
File.Copy
File.Delete
```

任何实际文件操作必须通过 Storage abstraction。

如果发现 Phase 0 已有违规代码：

在本阶段范围内修复。

---

# 25. Tests

所有测试只能使用：

```text id="w7p2y7"
temporary directory
```

严禁：

```text id="tivdmz"
访问真实下载目录
访问真实媒体库
访问 /Media
访问用户Home中的真实文件
```

---

## 25.1 Required Test Cases

至少覆盖：

### Basic

```text id="0cpyqx"
List empty directory
List files
List directories

Stat file
Stat directory

Exists true
Exists false
```

### Read / Write

```text id="1w6w4z"
Write file
Read file
Write + Read consistency
Read nonexistent file
Write readonly storage
```

### Directory

```text id="m0xm8j"
CreateDirectory
Create nested directory
Create existing directory
Directory/file conflict
```

### Copy

```text id="sbv2ub"
Copy file
Source preserved
Target content matches
Missing source
Existing target
ReadOnly
```

### Move

```text id="wfkmw1"
Move file
Source removed
Target exists
Content preserved
Missing source
Existing target
ReadOnly
```

### Delete

```text id="3uyip9"
Delete file
Delete missing file behavior
Delete readonly
Non-empty directory safety
```

### HardLink

```text id="bsheos"
HardLink when supported
Existing target conflict
Unsupported behavior
```

### SoftLink

```text id="cif52q"
SoftLink when supported
Existing target conflict
Unsupported behavior
```

### Security

```text id="oincko"
../ traversal
../../ traversal
absolute path outside root
nested traversal
symlink escape if applicable
```

### Capabilities

```text id="7n3uej"
LocalStorage returns correct capabilities
```

---

# 26. Integration-Style Safety Test

建立一个临时结构：

```text id="qdo13l"
temp/
├── source/
│   └── movie.mkv
└── target/
```

文件内容可以只是：

```text id="wr442h"
test-media-content
```

不需要真实媒体。

测试：

```text id="jh4gbv"
Copy
```

之后：

```text id="ahhjxb"
source/movie.mkv 存在
target/movie.mkv 存在
内容相同
```

然后重新初始化测试环境测试：

```text id="u77o6u"
Move
```

之后：

```text id="sed840"
source/movie.mkv 不存在
target/movie.mkv 存在
内容相同
```

---

# 27. Do Not Implement

本阶段严禁开始实现：

```text id="n48wd4"
SMBStorage

OpenListStorage

S3Storage
R2Storage

ResourceLibrary Scanner

FilenameParser

RecognitionRule

RecognitionType engine

TMDB

Naming engine

Classification engine

OrganizerExecutor

Web UI
```

可以保留已有接口或 placeholder，但不要扩展这些模块。

---

# 28. Documentation

完成后更新：

```text id="9w40rg"
docs/progress.md
```

标记：

```text id="g9ukns"
Phase 1 LocalStorage
```

完成情况。

如 Storage interface 有调整，同时更新：

```text id="a48a4j"
docs/architecture.md
```

说明：

- Storage 接口。
- LocalStorage 行为。
- Path 安全规则。
- ReadOnly 规则。
- Conflict 行为。
- Unsupported Operation 行为。

---

# 29. Validation

完成实现后，根据项目实际技术栈自动识别并运行：

```text id="l4qnrf"
tests
formatter check
linter
typecheck
build
```

不要猜命令。

先查看：

```text id="m4cqlz"
package.json
pyproject.toml
Cargo.toml
go.mod
pom.xml
build.gradle
或项目实际配置
```

再运行正确命令。

---

# 30. Fix Failures

如果：

```text id="xl5baa"
tests fail
lint fails
typecheck fails
build fails
```

必须在当前任务范围内修复。

不得留下：

```text id="c8bcbz"
"以后再修"
```

形式的本阶段错误。

---

# 31. Completion Criteria

只有同时满足以下条件才算 Phase 1 完成：

- Storage abstraction 可以正常工作。
- LocalStorage 已实现。
- List 正常。
- Stat 正常。
- Exists 正常。
- Read 正常。
- Write 正常。
- CreateDirectory 正常。
- Copy 正常。
- Move 正常。
- Delete 行为明确且安全。
- HardLink 有明确支持/不支持行为。
- SoftLink 有明确支持/不支持行为。
- ReadOnly 正常。
- StorageCapabilities 正常。
- Path Traversal 被阻止。
- Target Conflict 不会静默覆盖。
- 不存在自动 HardLink fallback。
- 大文件操作不依赖整文件加载到内存。
- 自动化测试通过。
- lint/typecheck/build 通过（如项目配置）。
- `docs/progress.md` 已更新。
- 没有开始开发下一阶段。

---

# 32. Final Report

完成后输出：

## Phase 1 Result

```text id="zkne7n"
PASS
```

或者：

```text id="nqqf31"
FAIL
```

---

## Changed Files

列出所有：

```text id="lqyj4b"
新增
修改
删除
```

的文件。

---

## Implemented

说明已实现：

```text id="2g1s6b"
Storage interface
LocalStorage
Capabilities
Errors
Path safety
ReadOnly
具体文件操作
```

---

## Tests

列出实际执行的测试命令。

---

## Test Results

例如：

```text id="5cmhsz"
Tests: 42 passed, 0 failed
Lint: PASS
Typecheck: PASS
Build: PASS
```

必须输出真实结果，不得虚构。

---

## Security Checks

明确说明：

```text id="zjdmli"
Path traversal protection
Overwrite behavior
ReadOnly behavior
Delete safety
Business layer Storage boundary
```

是否通过。

---

## Decisions

说明重要设计决策，例如：

```text id="h7dgbg"
路径如何解析
Target存在时如何处理
Delete目录行为
HardLink不支持时如何处理
```

---

## Remaining Work

只列后续阶段，例如：

```text id="hb7fux"
SMB
OpenList
S3/R2
```

不要在本任务中实现。

---

## Risks / Known Limitations

如存在：

```text id="b3y1gd"
跨文件系统Move
Windows Symlink权限
Atomic Write
平台差异
```

必须明确说明。

---

# Critical Reminder

本阶段的目标不是“做出完整影视整理系统”。

本阶段的目标是：

```text id="zmzt6j"
把所有未来媒体文件操作依赖的 LocalStorage 基础设施
做到安全、稳定、可测试。
```

在 LocalStorage 没有验收通过之前，不开始远程 Storage。
