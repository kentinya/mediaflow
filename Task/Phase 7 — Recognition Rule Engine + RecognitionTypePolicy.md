# TASK: Phase 7 — Recognition Rule Engine + RecognitionTypePolicy

## Goal

实现：

- `RecognitionRule`
- `RecognitionRuleEngine`
- `RecognitionType`
- `RecognitionResult`
- `RecognitionTypePolicy`
- `RecognitionTypePolicyResolver`

本阶段负责：

> 根据 `FileContext + ParseResult` 判断当前资源属于哪个“识别类型”，并根据识别类型解析后续应该使用哪些策略。

核心流程：

```text
DiscoveredFile
    ↓
ParseResult
    ↓
RecognitionRuleEngine
    ↓
RecognitionType
    ↓
RecognitionTypePolicyResolver
    ↓
MetadataPolicy
NamingPolicy
ClassificationPolicy
OrganizePolicy
```

本阶段最重要的业务规则：

```text
A
→ Metadata A
→ Naming A
→ Classification A
→ Organize A

B
→ Metadata B
→ Naming B
→ Classification B
→ Organize B

C
→ Metadata C
→ Naming A
→ Classification A
→ Organize A
```

**RecognitionType C 必须始终保持为 C。**

复用 A 的命名、分类或整理策略，不得把 C 改写成 A。

---

# 1. Before Starting

开始前阅读：

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

确认 Phase 6 已完成并验收。

运行现有：

```text
Parser tests
Scanner/FileIndex tests
Storage regression tests
DryRun regression tests
```

确保基线正常。

---

# 2. Strict Scope

本阶段只实现：

```text
RecognitionType

RecognitionRule
RecognitionCondition

RecognitionRuleEngine

RecognitionResult

RecognitionTypePolicy

RecognitionTypePolicyResolver

rule priority

AND / OR / NOT

rule evidence

rule scoring

conflict resolution

policy mapping

validation

tests
```

---

# 3. Do Not Implement

本阶段不要实现：

```text
TMDB Provider

Metadata HTTP requests

Movie/TV candidate matching

Naming Engine

Classification Engine

Organizer execution

Web UI

FFprobe
FFmpeg
```

RecognitionTypePolicy 本阶段只解析：

> 后续该用哪个 Policy ID。

不得真正执行这些 Policy。

---

# 4. RecognitionType

实现：

```text
RecognitionType
```

RecognitionType 不应硬编码只能：

```text
Movie
TV
Anime
```

必须支持用户自定义类型，例如：

```text
A
B
C
Movie
TV
Anime
Documentary
Variety
Custom-X
```

建议至少包含：

```text
id
name
description
enabled
createdAt
updatedAt
```

根据现有架构调整。

---

# 5. RecognitionType Identity

RecognitionType 的业务身份必须使用：

```text
RecognitionType ID
```

而不是仅依赖显示名称。

例如：

```text
id = rec-type-c
name = C
```

后续改名：

```text
C
→ Special
```

不应破坏 Policy 引用。

---

# 6. RecognitionRule

每条 RecognitionRule 至少包含：

```text
id
name

enabled

priority

condition

outputRecognitionTypeId

score

stopOnMatch

description
```

---

# 7. RecognitionRule Responsibility

RecognitionRule 只能回答：

> 当前资源符合哪个 RecognitionType。

RecognitionRule 不允许：

```text
调用 MetadataProvider

调用 TMDB

生成目标文件名

确定目标媒体库

Move / Copy / Delete

执行 OrganizePolicy
```

---

# 8. Recognition Input

RecognitionRuleEngine 输入：

```text
RecognitionContext
```

建议包含：

```text
FileContext
ParseResult
ResourceLibrary context
```

至少允许规则访问：

```text
filename
extension

path
parent directories

titleCandidate
alternativeTitleCandidates

year

season
episode
episodes

resolutionTag
sourceTag
videoCodecTag
audioCodecTag
audioChannelsTag
hdrTags
versionTags
releaseGroup
languageTags

resourceLibraryId
```

不要在本阶段加入 TMDB 字段。

---

# 9. RecognitionCondition

建立可组合条件模型。

至少支持：

```text
AND
OR
NOT
```

以及原子条件。

示例：

```text
AND
├── path contains "/C/"
└── extension in ["mkv", "mp4"]
```

---

# 10. Atomic Conditions

至少支持以下字段：

```text
filename
path
directory
extension

titleCandidate

year
season
episode

resolutionTag
sourceTag
videoCodecTag
audioCodecTag
hdrTag
versionTag
releaseGroup
languageTag

resourceLibraryId
```

---

# 11. Operators

根据字段类型支持合理操作符。

字符串：

```text
equals
notEquals

contains
notContains

startsWith
endsWith

in
notIn

regex
```

数值：

```text
equals
notEquals

greaterThan
greaterThanOrEqual

lessThan
lessThanOrEqual

between

in
```

集合字段：

```text
contains
containsAny
containsAll
notContains
```

---

# 12. Case Sensitivity

默认字符串匹配建议：

```text
case-insensitive
```

尤其：

```text
extension
source tags
codec tags
```

如果规则支持：

```text
caseSensitive
```

可以作为条件选项。

但默认行为必须清晰。

---

# 13. Extension Matching

以下应该等价：

```text
mkv
MKV
MkV
```

规则：

```text
extension == mkv
```

应全部匹配。

---

# 14. Path Matching

Path 条件必须基于：

```text
ResourceLibrary relative path
```

或统一规范化 Storage-relative path。

不要让规则依赖：

```text
真实 OS 绝对路径
UNC path
S3 bucket key implementation detail
```

---

# 15. Directory Matching

例如：

```text
directory contains "Anime"
```

应检查：

```text
parent directory names
```

而不是把整个路径字符串随意模糊匹配。

---

# 16. Regex

支持规则 regex。

必须：

- 编译失败时配置校验失败
- 不得运行时 silently ignore
- 注意 ReDoS 风险
- 如当前语言支持 regex timeout，应设置合理限制

用户可控规则不得导致无限正则计算。

---

# 17. AND Semantics

例如：

```text
AND
├── extension == mkv
├── path contains /A/
└── sourceTag == WEB-DL
```

只有全部匹配才算规则命中。

---

# 18. OR Semantics

例如：

```text
OR
├── path contains /Anime/
├── filename contains [ANIME]
└── resourceLibraryId == anime-downloads
```

任一匹配则命中。

---

# 19. NOT Semantics

例如：

```text
AND
├── path contains /Movie/
└── NOT filename contains sample
```

必须正确。

---

# 20. Nested Conditions

条件必须允许嵌套，例如：

```text
AND
├── extension IN [mkv, mp4]
├── OR
│   ├── path contains /A/
│   └── filename startsWith A-
└── NOT
    └── filename contains sample
```

建立专项测试。

---

# 21. Rule Priority

规则支持：

```text
priority
```

建议：

```text
数值越大优先级越高
```

例如：

```text
Rule C-special = 100
Rule Generic = 10
```

按：

```text
priority DESC
```

处理。

---

# 22. Stable Ordering

如果两个规则 priority 相同：

必须有稳定顺序。

例如：

```text
createdAt
ruleId
explicit order
```

不要依赖：

```text
数据库无序返回
hash map iteration
```

导致结果随机变化。

---

# 23. Rule Score

支持每条规则提供：

```text
score
```

例如：

```text
path strong match = 80
filename generic match = 20
```

最终 RecognitionResult 可以累计：

```text
score
```

但不要在本阶段过度实现复杂机器学习评分。

规则评分应保持可解释。

---

# 24. stopOnMatch

如果规则：

```text
stopOnMatch = true
```

且命中：

可以停止后续较低优先级规则。

但必须明确：

```text
规则按 priority 顺序处理
```

不要因为内部并发导致 stopOnMatch 失效。

---

# 25. Multiple Rules Same Type

例如：

```text
Rule A1 -> A
Rule A2 -> A
```

都命中时：

最终：

```text
RecognitionType = A
```

可以合并：

```text
matchedRules
score
evidence
```

---

# 26. Multiple Types Conflict

例如同时命中：

```text
Rule A -> A
Rule C -> C
```

必须有明确冲突解决策略。

建议：

1. 最高 priority 优先
2. priority 相同时比较 aggregate score
3. 仍然相同时进入 Ambiguous

不要随机选择。

---

# 27. Ambiguous Result

实现：

```text
RecognitionStatus
```

至少：

```text
Matched
Unrecognized
Ambiguous
```

如已有统一状态模型，可复用。

---

# 28. RecognitionResult

至少包含：

```text
status

recognitionTypeId
recognitionType

matchedRules

score

evidence

reasons

warnings

alternatives
```

对于 Ambiguous：

```text
recognitionTypeId = null
```

或者明确表示 unresolved。

不要假装识别成功。

---

# 29. Recognition Evidence

例如：

```text
Rule C matched:
- path contains "/C/"
- extension == mkv
```

RecognitionResult 应能提供：

```text
evidence
```

用于：

- Debug
- 人工确认
- 后续 UI
- 测试

---

# 30. Recognition Reason

建议生成机器可读 + 可读原因。

例如：

```text
code = RULE_MATCH
message = "Matched rule C-by-path"
```

不要只输出不可解析字符串。

---

# 31. No Match

没有任何规则命中：

```text
status = Unrecognized
```

不得：

```text
自动默认 A
```

除非配置了明确 Default Recognition Rule。

---

# 32. Default Rule

如果需要默认类型：

必须通过显式规则，例如：

```text
condition = TRUE
priority = -1000
output = Other
```

不要在 Engine 里隐藏 hardcoded default。

---

# 33. Disabled Rule

```text
enabled = false
```

必须完全忽略。

测试：

```text
Disabled C Rule
```

不能产生 C。

---

# 34. Disabled RecognitionType

如果 Rule 指向：

```text
disabled RecognitionType
```

配置应被视为无效。

建议：

```text
validation error
```

而不是运行时继续使用。

---

# 35. Recognition Rule Validation

保存 / 加载规则时至少验证：

```text
id exists
name valid

outputRecognitionType exists
outputRecognitionType enabled

condition valid

operator compatible with field

regex valid

priority valid
score valid
```

---

# 36. RecognitionTypePolicy

实现：

```text
RecognitionTypePolicy
```

定义：

> 某 RecognitionType 识别成功以后，后续使用哪些 Policy。

至少包含：

```text
id
name

recognitionTypeId

metadataPolicyId

namingPolicyId

classificationPolicyId

organizePolicyId

enabled

priority

createdAt
updatedAt
```

---

# 37. Policy Mapping

必须支持：

```text
RecognitionType A
→ Metadata A
→ Naming A
→ Classification A
→ Organize A

RecognitionType B
→ Metadata B
→ Naming B
→ Classification B
→ Organize B

RecognitionType C
→ Metadata C
→ Naming A
→ Classification A
→ Organize A
```

---

# 38. Critical C Rule

这是整个项目核心回归条件。

当：

```text
RecognitionResult.recognitionType = C
```

经过：

```text
RecognitionTypePolicyResolver
```

结果必须：

```text
recognitionType = C

metadataPolicy = C

namingPolicy = A

classificationPolicy = A

organizePolicy = A
```

绝对禁止：

```text
recognitionType = A
```

---

# 39. RecognitionTypePolicyResolver

实现：

```text
RecognitionTypePolicyResolver
```

输入：

```text
RecognitionType ID
```

输出：

```text
ResolvedRecognitionPolicy
```

建议包含：

```text
recognitionTypeId

metadataPolicyId
namingPolicyId
classificationPolicyId
organizePolicyId
```

---

# 40. Resolver Does Not Execute Policies

Resolver 只能：

```text
解析引用
返回映射
```

不得：

```text
调用 TMDB
生成文件名
运行 Classification
Move 文件
```

---

# 41. Policy Reuse

多个 RecognitionType 可以复用同一策略。

例如：

```text
A -> Naming A
C -> Naming A
D -> Naming A
```

系统必须支持。

禁止在 NamingPolicy 上建立：

```text
唯一 RecognitionType 外键
```

导致不能复用。

---

# 42. Policy Independence

必须支持未来：

```text
D
→ Metadata B
→ Naming A
→ Classification C
→ Organize Copy
```

即四类 Policy 引用彼此独立。

不要将其封装成不可拆的：

```text
A Policy Bundle
```

只能整体复用。

---

# 43. Missing Policy Reference

RecognitionTypePolicy 引用了不存在的：

```text
NamingPolicy
```

等情况：

必须：

```text
validation failure
```

或 Resolver 返回明确：

```text
InvalidPolicyReference
```

不得 silent fallback。

---

# 44. Disabled Policy

如果引用的 Policy 被禁用：

Resolver 不得继续正常成功。

返回：

```text
PolicyDisabled
```

或项目等价错误。

---

# 45. Multiple Policies For Same RecognitionType

如果允许：

```text
RecognitionType C
```

存在多个 TypePolicy：

必须用：

```text
priority
```

明确选择。

如果不允许多个：

数据库/领域验证必须保证唯一。

建议 MVP：

```text
一个 enabled RecognitionType
对应一个 active RecognitionTypePolicy
```

更简单可靠。

如采用这一策略：

建立唯一约束。

---

# 46. Repository Abstractions

如当前项目采用 repository pattern：

实现：

```text
RecognitionTypeRepository
RecognitionRuleRepository
RecognitionTypePolicyRepository
```

Scanner/Parser 不应直接写 SQL。

---

# 47. No Recognition DB Side Effects

RecognitionRuleEngine 本身应尽量：

```text
pure / deterministic
```

输入：

```text
RecognitionContext + Rules
```

输出：

```text
RecognitionResult
```

不要由 Engine 自己：

```text
写 FileIndex
写 Task
```

调用方决定持久化结果。

---

# 48. Determinism

相同：

```text
input
rules
types
```

必须产生相同：

```text
RecognitionResult
```

不得依赖：

```text
random
network
unordered map iteration
```

---

# 49. Performance

规则数量未来可能：

```text
10
100
1000+
```

避免明显：

```text
每个规则重新解析文件名
```

Parser 已经完成。

Recognition 只消费：

```text
ParseResult
```

---

# 50. Precompiled Regex

如果规则经常执行：

建议在规则加载 / 编译阶段：

```text
compile regex
```

而不是每个文件每条规则重复编译。

如实现 RuleCompiler：

```text
RecognitionRule
↓
CompiledRecognitionRule
```

可以。

不要过度复杂化。

---

# 51. Rule Compilation Errors

非法 regex / operator：

应在：

```text
RuleCompiler / validation
```

阶段发现。

不要等扫描 10 万文件后才报错。

---

# 52. Recognition Rule Test Matrix

至少覆盖：

```text
filename equals
filename contains

path contains

directory match

extension in

year compare

season compare

resolution tag

source tag

codec tag

HDR tag

language tag

resourceLibrary ID
```

---

# 53. AND Tests

至少多个嵌套条件。

---

# 54. OR Tests

至少多个嵌套条件。

---

# 55. NOT Tests

至少：

```text
Movie path
AND NOT sample
```

---

# 56. Regex Tests

至少：

```text
valid regex match
valid regex no match
invalid regex validation failure
```

---

# 57. Priority Tests

例如：

```text
Rule Generic:
priority = 10
→ A

Rule Special:
priority = 100
→ C
```

同时命中：

```text
C
```

必须胜出。

---

# 58. Same Priority Score Tests

例如：

```text
A priority 100 score 50
C priority 100 score 80
```

如果采用 score tie breaker：

```text
C
```

胜出。

---

# 59. Ambiguous Tests

例如：

```text
A priority 100 score 80
C priority 100 score 80
```

如果没有其他决胜条件：

必须：

```text
Ambiguous
```

或使用明确稳定规则。

不要随机。

---

# 60. stopOnMatch Tests

确保高优先级：

```text
stopOnMatch=true
```

后低优先级不会影响结果。

---

# 61. Disabled Rule Tests

确认完全忽略。

---

# 62. No Match Tests

输出：

```text
Unrecognized
```

---

# 63. A/B/C Core Tests

必须有清晰测试：

```text
Input A-like
→ RecognitionType A

Input B-like
→ RecognitionType B

Input C-like
→ RecognitionType C
```

---

# 64. C Policy Regression Test

至少有类似断言：

```text
result.recognitionType.id == "C"

resolved.metadataPolicyId == "C"
resolved.namingPolicyId == "A"
resolved.classificationPolicyId == "A"
resolved.organizePolicyId == "A"

result.recognitionType.id != "A"
```

这是永久回归测试。

---

# 65. Policy Reuse Tests

例如：

```text
A -> Naming A
C -> Naming A
```

确认同一个 NamingPolicy 可以被多个 TypePolicy 引用。

---

# 66. Missing Reference Tests

测试：

```text
C -> NamingPolicy DOES_NOT_EXIST
```

Resolver 必须失败。

---

# 67. Disabled Reference Tests

测试：

```text
C -> NamingPolicy A(disabled)
```

Resolver 必须明确失败。

---

# 68. Rule Explanation Test

对于命中：

```text
path contains /C/
extension = mkv
```

RecognitionResult 应包含可检查 evidence。

---

# 69. Parser Integration Test

使用真实 Phase 6 Parser：

输入：

```text
/C/The.Matrix.1999.1080p.WEB-DL.mkv
```

Parser：

```text
titleCandidate = The Matrix
year = 1999
sourceTag = WEB-DL
```

Recognition Rule：

```text
path contains /C/
```

结果：

```text
RecognitionType C
```

不要调用 TMDB。

---

# 70. ResourceLibrary Rule Test

例如：

```text
resourceLibraryId = anime-downloads
```

规则：

```text
→ RecognitionType Anime
```

确认可以使用 ResourceLibrary Context。

---

# 71. Zero Mutation Test

使用 FakeStorage / mutation counter。

完整：

```text
Parse
→ Recognition
→ RecognitionTypePolicy resolution
```

之后必须：

```text
Write = 0
CreateDirectory = 0
Move = 0
Copy = 0
Delete = 0
HardLink = 0
SoftLink = 0
```

---

# 72. Zero Network Test

Recognition 本阶段：

```text
HTTP calls = 0
Metadata calls = 0
```

---

# 73. No TMDB Test Dependency

单元测试不得要求：

```text
TMDB token
Internet
DNS
```

---

# 74. Scanner Regression

运行：

```text
ResourceLibrary
Scanner
FileIndex
```

测试。

确保 Scanner 仍然不负责 Recognition。

---

# 75. Parser Regression

运行全部 Phase 6 Parser tests。

确保 Recognition 没有向 Parser 塞业务策略逻辑。

---

# 76. Storage Regression

运行：

```text
LocalStorage
SMBStorage
OpenListStorage
S3/R2Storage
```

---

# 77. DryRun Regression

继续要求：

```text
zero mutation PASS
```

---

# 78. No FFprobe

全仓库检查：

```text
ffprobe
ffmpeg
```

除文档禁止说明外，不得存在 runtime dependency。

---

# 79. Documentation

更新：

```text
docs/progress.md
```

记录：

```text
Phase 7 Recognition Rule Engine + RecognitionTypePolicy
```

更新：

```text
docs/architecture.md
```

至少记录：

```text
RecognitionRule responsibility

RecognitionContext

condition tree

operators

rule priority

score/conflict behavior

RecognitionResult

Unrecognized

Ambiguous

RecognitionType

RecognitionTypePolicy

C -> A/A policy reuse rule

zero network boundary

zero storage mutation boundary
```

---

# 80. Completion Criteria

Phase 7 必须满足：

- RecognitionType 完成
- RecognitionRule 完成
- RecognitionCondition 完成
- AND 完成
- OR 完成
- NOT 完成
- Regex 完成且有校验
- priority 完成
- stable ordering 完成
- score/conflict 逻辑明确
- stopOnMatch 完成
- Unrecognized 完成
- Ambiguous 完成或有明确替代策略
- RecognitionResult evidence 完成
- RecognitionTypePolicy 完成
- PolicyResolver 完成
- Policy 引用校验完成
- Policy reuse 完成
- C 保持 C
- C 可以使用 A Naming
- C 可以使用 A Classification
- C 可以使用 A Organize
- Recognition zero mutation
- Recognition zero network
- Parser regression PASS
- Scanner regression PASS
- Storage regressions PASS
- DryRun PASS
- 无 FFprobe runtime
- docs/progress.md 更新
- docs/architecture.md 更新
- 未开始 TMDB

---

# 81. Final Report

完成后输出：

## Phase 7 Result

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

## Recognition Architecture

说明：

```text
RecognitionContext
RecognitionCondition
RecognitionRule
RecognitionRuleEngine
RecognitionResult
conflict resolution
rule ordering
evidence
```

---

## Supported Operators

列出实际实现：

```text
String:
Numeric:
Collection:
Logical:
```

---

## Recognition Statuses

列出：

```text
Matched
Unrecognized
Ambiguous
```

或实际等价状态。

---

## A/B/C Verification

必须输出：

```text
A -> A: PASS/FAIL
B -> B: PASS/FAIL
C -> C: PASS/FAIL
```

---

## C Policy Mapping

明确：

```text
RecognitionType = C

MetadataPolicy =
NamingPolicy =
ClassificationPolicy =
OrganizePolicy =
```

并明确：

```text
RecognitionType remained C: PASS/FAIL
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
Parser: PASS/FAIL
Scanner: PASS/FAIL
FileIndex: PASS/FAIL

LocalStorage: PASS/FAIL
SMBStorage: PASS/FAIL
OpenListStorage: PASS/FAIL
S3/R2Storage: PASS/FAIL

DryRun: PASS/FAIL
```

---

## Safety

输出：

```text
Storage mutation calls: 0

Metadata/network calls: 0

FFprobe runtime dependency: NONE
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

无配置写：

```text
N/A
```

---

## Known Limitations

如实说明，例如：

```text
Recognition identifies configured types only.

Recognition does not confirm the actual movie/TV identity.

TMDB metadata lookup is intentionally not implemented.

Ambiguous matches require future manual-confirmation workflow.
```

---

## Final Recommendation

全部阻塞项通过后：

```text
Phase 7 accepted. Ready for Metadata Provider architecture and TMDB integration.
```

存在阻塞项：

```text
Phase 7 not accepted. Blocking issues remain.
```

不要自动开始 Phase 8。

最后更新：

`docs/progress.md`