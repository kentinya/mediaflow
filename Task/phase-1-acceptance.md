# TASK: Phase 1 Acceptance — LocalStorage

## Goal

对已经完成的 Phase 1 LocalStorage 进行验收。

本任务只做：

- 检查
- 测试
- 修复本阶段问题
- 输出验收结论

不要开发任何下一阶段功能。

---

## 1. Read Project Context

先阅读：

- `AGENTS.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/progress.md`

然后检查：

- `git status`
- `git diff`
- 当前 Storage 实现
- 当前测试
- 当前构建配置

不要覆盖已有有效代码。

---

# 2. Acceptance Scope

本阶段必须验收：

```text
Storage abstraction
LocalStorage
StorageCapabilities
StorageError
Path safety
ReadOnly
List
Stat
Exists
Read
Write
CreateDirectory
Copy
Move
Delete
HardLink
SoftLink
Large file safety
Business layer boundary
```

---

# 3. Run Existing Quality Checks

根据项目实际技术栈识别并运行：

- unit tests
- integration tests
- formatter check
- linter
- typecheck
- build

不要猜命令。

先检查项目配置文件，再运行正确命令。

最终所有当前 Phase 1 相关检查必须通过。

---

# 4. Storage Interface Acceptance

检查 Storage interface 是否能完整表达：

```text
List
Stat
Exists
Read
Write
CreateDirectory
Copy
Move
Delete
HardLink
SoftLink
```

检查：

- 是否存在重复 Storage abstraction
- 是否存在 LocalStorage 专属类型泄漏到 domain
- 是否存在业务层依赖 OS filesystem API
- 是否存在不必要的实现耦合

结果记录为：

PASS / FAIL

---

# 5. LocalStorage Root Boundary

创建临时测试目录，例如：

```text
temp-root/
├── allowed/
└── outside/
```

LocalStorage Root 设置为：

```text
temp-root/allowed
```

验证绝不能访问：

```text
../outside
../../outside
绝对路径 outside
嵌套 traversal
```

至少测试：

```text
../file.txt
../../file.txt
foo/../../../file.txt
```

必须失败。

---

# 6. Symlink Escape Test

如果当前平台支持 symlink：

在 Storage Root 内建立一个 symlink，指向 Root 外目录。

例如：

```text
allowed/
└── escape -> ../outside
```

然后尝试：

```text
escape/secret.txt
```

必须确认不能通过 symlink 绕过 RootPath。

如果当前平台无法测试：

- 明确记录原因
- 不允许假装通过
- 标记为平台限制

---

# 7. ReadOnly Acceptance

创建：

```text
LocalStorage(ReadOnly=true)
```

以下必须成功：

```text
List
Stat
Exists
Read
```

以下必须失败：

```text
Write
CreateDirectory
Copy
Move
Delete
HardLink
SoftLink
```

所有失败必须使用统一的：

```text
ReadOnly StorageError
```

或项目等价错误类型。

---

# 8. List Acceptance

测试：

### Empty Directory

```text
root/
```

List 返回空列表。

### File + Directory

```text
root/
├── movie.mkv
└── folder/
```

返回两个 StorageEntry。

验证：

- name
- path
- type
- size（文件）
- modifiedAt

### Missing Directory

返回统一 NotFound。

### File Used As Directory

调用：

```text
List("movie.mkv")
```

必须返回合理错误。

---

# 9. Stat Acceptance

验证：

```text
普通文件
目录
不存在路径
```

至少检查：

```text
type
size
modifiedAt
```

不存在路径不能泄漏不可控的 OS exception。

---

# 10. Exists Acceptance

验证：

```text
existing -> true
missing -> false
```

不存在路径不得抛 NotFound。

但是：

```text
../outside
```

仍必须返回非法路径错误，而不是 false。

---

# 11. Read / Write Acceptance

使用小型测试文件即可。

写入：

```text
test-media-content
```

验证：

```text
Write
↓
Read
↓
内容完全一致
```

同时测试：

```text
Read missing file
Write to ReadOnly
Write conflict behavior
```

如果 Write 默认允许覆盖，确认该行为是否符合当前 Storage 设计。

禁止出现“无规则静默覆盖媒体文件”的设计。

---

# 12. Large File Safety Review

检查实现代码。

不得存在明显模式：

```text
read entire file into memory
then write entire file
```

用于 Copy 或常规大文件操作。

LocalStorage 设计必须适合大型影视文件。

可以通过：

- streaming
- filesystem native copy
- buffered IO

实现。

不需要创建几十 GB 测试文件。

但请做一个较大的临时文件测试，例如：

```text
16MB - 64MB
```

验证 Copy 正常完成并保持内容一致。

测试不能显著拖慢正常 test suite。

---

# 13. Copy Acceptance

准备：

```text
source/movie.mkv
target/
```

执行：

```text
Copy(source/movie.mkv, target/movie.mkv)
```

验证：

```text
source/movie.mkv exists == true
target/movie.mkv exists == true
source content == target content
```

再次 Copy 到同一个目标：

必须发生明确：

```text
Conflict
```

不得静默覆盖。

另外测试：

- missing source
- ReadOnly
- invalid target path

---

# 14. Move Acceptance

准备：

```text
source/movie.mkv
```

执行 Move。

验证：

```text
source exists == false
target exists == true
content preserved
```

再次测试 Target 已存在：

必须返回 Conflict。

不得静默覆盖。

测试：

- missing source
- ReadOnly
- invalid path

---

# 15. Delete Acceptance

验证普通文件删除。

同时重点测试：

```text
non-empty-directory/
├── a.mkv
└── b.srt
```

普通 Delete 不得在没有明确设计的情况下递归删除整个目录树。

如果项目规定：

```text
Delete(non-empty-directory)
```

失败，则测试必须锁定这个行为。

目标是避免误删整个媒体目录。

---

# 16. HardLink Acceptance

如果当前平台支持：

执行：

```text
HardLink(source, target)
```

验证：

- source 存在
- target 存在
- 内容一致
- target 已存在时报 Conflict

如果可以可靠检查 inode / file identity，也可以验证硬链接确实不是普通复制。

如果平台不支持：

必须返回：

```text
UnsupportedOperation
```

或等价统一错误。

不得自动 Copy。

不得自动 Move。

---

# 17. SoftLink Acceptance

如果平台支持：

验证：

```text
SoftLink(source, target)
```

确实建立 symlink。

测试：

- existing target
- missing source（按当前设计）
- ReadOnly

如果平台不支持：

返回 UnsupportedOperation。

不得 fallback。

---

# 18. StorageCapabilities Acceptance

检查 LocalStorage 返回的：

```text
CanMove
CanCopy
CanDelete
CanHardLink
CanSoftLink
```

必须和实际行为一致。

例如：

```text
CanHardLink = false
```

则调用 HardLink 不得成功。

Capabilities 不允许只是展示信息而与实际实现矛盾。

---

# 19. Error Model Acceptance

至少验证以下场景转换成统一错误：

```text
NotFound
PermissionDenied
Conflict
InvalidPath
PathTraversal
ReadOnly
UnsupportedOperation
IOError
```

检查业务层是否需要解析：

```text
ENOENT
EACCES
EPERM
EEXIST
```

等原生 OS 错误。

如果需要，说明 Storage abstraction 泄漏，应修复。

---

# 20. Business Boundary Audit

全仓库搜索底层 filesystem mutation。

根据语言检查类似：

```text
rename
copy
move
unlink
remove
delete
mkdir
writeFile
```

允许存在的位置：

```text
Storage infrastructure
Storage tests
```

业务模块不得绕过 Storage interface。

特别检查：

```text
Recognition
Metadata
Naming
Classification
Planner
```

这些模块不应执行文件写操作。

---

# 21. Dry Run Regression

重新运行 Phase 0 的 Dry Run / Planner 安全测试。

确保 Phase 1 加入 LocalStorage 后，没有破坏原来的原则：

```text
Planner
↓
OrganizePlan
```

不会调用 LocalStorage：

```text
Move
Copy
Delete
Write
CreateDirectory
```

Dry Run 前后文件系统必须保持一致。

---

# 22. FFprobe Regression Check

全仓库搜索：

```text
ffprobe
ffmpeg
```

除文档中的“不使用”描述外，不得存在：

- dependency
- runtime invocation
- executable configuration
- parser integration

---

# 23. Required Acceptance Scenario

建立临时目录：

```text
root/
├── source/
│   ├── movie.mkv
│   └── movie.zh-CN.srt
└── library/
```

只测试 Storage，不测试 Organizer。

### COPY

执行：

```text
Copy(
  "source/movie.mkv",
  "library/movie.mkv"
)
```

预期：

```text
source/movie.mkv       EXISTS
library/movie.mkv      EXISTS
```

内容一致。

### MOVE

重新初始化：

执行：

```text
Move(
  "source/movie.mkv",
  "library/movie.mkv"
)
```

预期：

```text
source/movie.mkv       MISSING
library/movie.mkv      EXISTS
```

内容一致。

---

# 24. Test Isolation

确认测试：

- 只使用临时目录
- 不访问真实媒体目录
- 不依赖真实 SMB
- 不依赖真实 OpenList
- 不依赖真实 R2/S3
- 不依赖 TMDB
- 测试结束后清理资源

---

# 25. Fix Phase 1 Problems

如果发现 Phase 1 范围内问题：

直接修复。

包括：

- Storage bugs
- path traversal
- ReadOnly bug
- conflict bug
- unsafe Delete
- wrong capabilities
- error mapping
- missing tests

不要因为“这是验收任务”而只报告明显 bug 不修。

但是严禁借机实现 Phase 2。

---

# 26. Do Not Implement

本次验收禁止实现：

```text
SMBStorage
OpenListStorage
S3/R2Storage

ResourceLibrary Scanner

FilenameParser

Recognition Engine

TMDB

Naming

Classification

Organizer

Web UI
```

---

# 27. Final Quality Run

修复完成后重新运行全部适用：

```text
tests
formatter
lint
typecheck
build
```

不得只运行刚修改的单个测试。

---

# 28. Acceptance Result

最终输出以下格式：

## Phase 1 Acceptance

```text
PASS
```

或：

```text
FAIL
```

只有所有关键安全项通过才能 PASS。

---

## Automated Tests

输出真实数据：

```text
Total:
Passed:
Failed:
Skipped:
```

平台能力导致 HardLink / Symlink 测试 skipped 必须说明。

---

## Quality Checks

```text
Build:
Lint:
Typecheck:
Formatter:
```

没有配置的项目写：

```text
N/A
```

不要伪造 PASS。

---

## Functional Acceptance

逐项：

```text
Storage abstraction        PASS/FAIL
LocalStorage               PASS/FAIL

List                       PASS/FAIL
Stat                       PASS/FAIL
Exists                     PASS/FAIL

Read                       PASS/FAIL
Write                      PASS/FAIL
CreateDirectory            PASS/FAIL

Copy                       PASS/FAIL
Move                       PASS/FAIL
Delete                     PASS/FAIL

HardLink                   PASS/FAIL/N/A
SoftLink                   PASS/FAIL/N/A

ReadOnly                   PASS/FAIL
Capabilities               PASS/FAIL
Unified Errors             PASS/FAIL
```

---

## Security Acceptance

必须逐项：

```text
Path traversal             PASS/FAIL
Symlink escape             PASS/FAIL/N/A
No silent overwrite        PASS/FAIL
Safe directory delete      PASS/FAIL
ReadOnly enforcement       PASS/FAIL
DryRun zero mutation       PASS/FAIL
Business Storage boundary  PASS/FAIL
No FFprobe runtime         PASS/FAIL
```

---

## Problems Found

列出实际发现的问题。

如果没有：

```text
None
```

---

## Fixes Applied

列出验收过程中修复的问题。

---

## Known Limitations

例如：

```text
Cross-filesystem Move not supported
Windows symlink requires privileges
Atomic writes not implemented
```

必须如实列出。

---

## Changed Files

列出验收期间修改的所有文件。

---

## Commands Run

列出真实执行过的命令。

---

## Final Recommendation

只允许以下之一：

```text
Phase 1 accepted. Ready for Phase 2.
```

或者：

```text
Phase 1 not accepted. Blocking issues remain.
```

不要在验收任务中自动开始 Phase 2。

最后更新：

`docs/progress.md`
