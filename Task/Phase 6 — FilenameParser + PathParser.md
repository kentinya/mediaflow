# TASK: Phase 6 — FilenameParser + PathParser

## Goal

实现媒体文件的本地解析层：

- `FilenameParser`
- `PathParser`
- `DirectoryParser`（如果现有架构适合独立存在）
- 统一 `ParseResult`

本阶段负责：

> 从文件名、路径、目录结构中提取“媒体识别候选信息”。

本阶段**不负责确认具体是哪部影视作品**。

核心流程：

```text
DiscoveredFile
    ↓
FilenameParser
    ↓
PathParser
    ↓
Directory Context
    ↓
ParseResult
```

例如：

```text
/Downloads/TV/The.Last.of.Us.2023/
└── The.Last.of.Us.S01E03.2160p.WEB-DL.DDP5.1.H.265.mkv
```

解析为：

```text
titleCandidate = The Last of Us
year = 2023

season = 1
episode = 3
episodes = [3]

resolutionTag = 2160p
sourceTag = WEB-DL
videoCodecTag = H265
audioTag = DDP5.1

extension = mkv
```

但本阶段不得输出：

```text
TMDB ID
IMDb ID
最终媒体身份
RecognitionType A/B/C
目标媒体库
最终文件名
```

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

确认 Phase 5 已完成并验收。

运行现有：

```text
Storage regression tests
Scanner tests
FileIndex tests
```

确保基线正常。

---

# 2. Scope

本阶段实现：

```text
Filename normalization
Filename tokenization

Movie-like filename parsing
Episode parsing
Multi-episode parsing

Year extraction

Release tag extraction

Title candidate extraction

Path context parsing
Directory context parsing

ParseResult merge

Parser evidence

Parser warnings

Automated tests
```

---

# 3. Strict Boundary

Parser 只允许：

```text
读取字符串
解析字符串
返回解析结果
```

Parser 不允许：

```text
调用 TMDB
调用其他 Metadata Provider

判断最终电影身份
判断最终电视剧身份

输出 RecognitionType A/B/C

Naming
Classification

访问 Storage 写接口

Move
Copy
Delete
Rename

修改数据库中的媒体身份

使用 FFprobe
使用 FFmpeg
```

---

# 4. Input

统一输入建议：

```text
FileContext
```

至少包含：

```text
storageId
resourceLibraryId

path
filename
extension

parentPath
directoryNames

size
modifiedAt
```

Parser 不需要重新访问 Storage 获取这些基础数据。

优先复用 Scanner / FileIndex 已经产生的数据。

---

# 5. ParseResult

实现统一：

```text
ParseResult
```

至少包含：

```text
originalFilename

normalizedFilename

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

hdrTag

versionTags

releaseGroup

languageTags

extension

rawTags

evidence

warnings
```

其中字段允许：

```text
null
[]
```

表示没有解析到。

不要为了填满结果而猜测。

---

# 6. Evidence

建议每个重要结果能够记录来源。

例如：

```text
titleCandidate:
    value = "The Last of Us"
    source = filename

year:
    value = 2023
    source = parentDirectory

season:
    value = 1
    source = filename

episode:
    value = 3
    source = filename
```

可实现：

```text
ParseEvidence
```

用于未来：

```text
Recognition
Metadata candidate scoring
Debug
```

---

# 7. Confidence

如果当前架构适合，可为单字段添加简单：

```text
confidence
```

例如：

```text
explicit S01E03
→ high confidence

directory contains "Season 1"
→ medium/high confidence

bare E03
→ lower confidence
```

但本阶段不要实现复杂媒体匹配评分系统。

最终 TMDB Candidate Score 属于后续阶段。

---

# 8. Filename Normalization

在正式解析之前建立统一：

```text
FilenameNormalizer
```

或者等价逻辑。

需要处理：

```text
.
_
空格

重复分隔符

[]
()
{}

Unicode空格

连续空格
```

例如：

```text
The.Last.of.Us.2023
```

基础规范化后可用于解析：

```text
The Last of Us 2023
```

但是：

必须同时保留：

```text
originalFilename
```

不要覆盖原始名称。

---

# 9. Extension Removal

解析前正确分离扩展名。

例如：

```text
Movie.2024.1080p.mkv
```

得到：

```text
basename = Movie.2024.1080p
extension = mkv
```

扩展名大小写标准化：

```text
MKV
MkV
mkv
```

统一输出：

```text
mkv
```

---

# 10. Title Candidate

需要从文件名中尽量提取：

```text
titleCandidate
```

例如：

```text
The.Matrix.1999.1080p.BluRay.x265.mkv
```

应得到：

```text
titleCandidate = The Matrix
```

不能包含：

```text
1999
1080p
BluRay
x265
```

---

# 11. Title Extraction Boundary

标题结束位置通常由以下强特征决定：

```text
year
season/episode marker
resolution
source
codec
HDR
audio
release tags
release group
```

例如：

```text
Dune.Part.Two.2024.2160p.WEB-DL.mkv
```

必须避免错误解析成：

```text
title = Dune
```

正确候选应尽量：

```text
Dune Part Two
```

---

# 12. Numbers Inside Titles

不得把标题中的所有数字都认为是年份或集数。

例如：

```text
2001.A.Space.Odyssey.1968.mkv
```

应允许：

```text
titleCandidate = 2001 A Space Odyssey
year = 1968
```

而不是：

```text
year = 2001
```

需要合理处理多个四位数字。

---

# 13. Year Extraction

支持典型影视年份：

```text
1900 - 当前合理未来范围
```

具体范围可以配置或用合理常量。

例如：

```text
The.Matrix.1999.mkv
→ 1999
```

```text
Dune.2021.2160p.mkv
→ 2021
```

---

# 14. Multiple Year Candidates

例如：

```text
Title.1999.Remastered.2024.mkv
```

不得无条件取最后一个年份。

建立明确策略。

可以：

```text
优先标题边界附近第一个合理年份
```

并把其他年份保留到：

```text
rawTags
warnings
```

如果存在歧义，不要强行做错误确定。

---

# 15. Episode Patterns

至少支持：

```text
S01E01
S1E1

S01.E01
S01-E01

S01E01E02
S01E01E02E03

S01E01-E03

1x01
01x01

EP01
Ep01
ep01

E01

第01集
第1集

第01话
第1话
```

---

# 16. Standard Season/Episode

例如：

```text
Show.Name.S01E03.1080p.mkv
```

输出：

```text
season = 1
episode = 3
episodes = [3]
```

---

# 17. Multi Episode

例如：

```text
Show.S01E01E02.mkv
```

输出：

```text
season = 1
episode = 1
episodes = [1, 2]
```

---

# 18. Episode Range

例如：

```text
Show.S01E01-E03.mkv
```

输出：

```text
season = 1
episodes = [1, 2, 3]
```

避免：

```text
episodes = [1, 3]
```

除非项目业务明确将范围只保存首尾。

优先展开合理的小范围。

---

# 19. Episode Range Safety

防止恶意/异常：

```text
S01E01-E999999
```

生成巨大数组。

必须设置：

```text
MaxEpisodeRangeExpansion
```

例如合理上限。

超出时：

```text
warning
```

并避免大量内存分配。

---

# 20. Bare Episode

例如：

```text
Show.Name.E03.mkv
```

可以解析：

```text
episode = 3
```

但：

```text
season = null
```

除非目录提供 Season 信息。

---

# 21. 1x01 Pattern

例如：

```text
Show.Name.1x03.mkv
```

输出：

```text
season = 1
episode = 3
episodes = [3]
```

---

# 22. Chinese Episode Pattern

例如：

```text
电视剧名称 第12集 1080p.mkv
```

输出：

```text
titleCandidate = 电视剧名称
episode = 12
```

例如：

```text
动画名称 第03话.mkv
```

输出：

```text
titleCandidate = 动画名称
episode = 3
```

---

# 23. Season Directory

PathParser 必须识别典型目录：

```text
Season 1
Season 01
S01
第1季
第一季
```

至少优先支持数字形式。

例如：

```text
/Show Name/Season 02/E03.mkv
```

可合并：

```text
season = 2
episode = 3
```

---

# 24. Parent Directory Title

例如：

```text
/The Last of Us (2023)/
└── Season 01/
    └── S01E03.mkv
```

FilenameParser 本身只能得到：

```text
season = 1
episode = 3
```

PathParser 应能够补充：

```text
titleCandidate = The Last of Us
year = 2023
```

---

# 25. Path Parsing

实现：

```text
PathParser
```

分析：

```text
parent directory
grandparent directory
relative path
```

但不要无限解析整个 Storage 路径。

建议只使用：

```text
ResourceLibrary root 以下的相对路径
```

作为上下文。

---

# 26. Path Context Priority

文件名和目录可能冲突。

例如：

```text
/ShowA/Season 01/ShowB.S01E03.mkv
```

此时不要静默覆盖。

ParseResult 应保留：

```text
filename candidate = ShowB
directory candidate = ShowA
```

并产生：

```text
warning: conflicting title candidates
```

最终由后续 Recognition / Metadata 决定。

---

# 27. Merge Strategy

建立明确：

```text
ParseResultMerger
```

或等价逻辑。

建议优先级：

### Season/Episode

```text
明确 filename SxxExx
>
明确 directory Season xx
>
弱推断
```

### Year

```text
明确 filename year
和
directory year
```

一致时提高可信度。

冲突时保留 evidence + warning。

### Title

不要简单使用一个固定优先级覆盖所有候选。

保留：

```text
titleCandidate
alternativeTitleCandidates
evidence
```

---

# 28. Release Tags

识别常见 Release 标签。

至少支持：

### Resolution

```text
2160p
1080p
1080i
720p
576p
480p
4K
UHD
```

统一输出建议：

```text
2160p
1080p
1080i
720p
576p
480p
```

如果：

```text
4K
UHD
```

映射到：

```text
2160p
```

必须保留原始 token 到：

```text
rawTags
```

---

# 29. Source Tags

至少识别：

```text
BluRay
Blu-Ray

REMUX
Remux

WEB-DL
WEBDL

WEBRip
WEB-Rip

HDTV

DVDRip
DVD

UHD BluRay

BDRip
BRRip
```

统一规范化输出，例如：

```text
BLURAY
REMUX
WEB-DL
WEBRIP
HDTV
DVD
```

具体 enum/string 风格按照现有项目规范。

---

# 30. Video Codec Tags

至少识别：

```text
H264
H.264
x264
AVC

H265
H.265
x265
HEVC

AV1
VP9
```

建议标准化：

```text
H264
H265
AV1
VP9
```

保留原始 token。

---

# 31. Audio Codec Tags

至少识别：

```text
AAC

AC3
DD
Dolby Digital

EAC3
E-AC3
DDP
DD+

DTS
DTS-HD
DTS-HD MA

TrueHD
TrueHD Atmos

FLAC
PCM
LPCM

Opus
```

不要要求本阶段理解所有复杂音轨组合。

先提取：

```text
audioCodecTag
```

和必要：

```text
rawTags
```

---

# 32. Audio Channels

至少识别：

```text
2.0
5.1
7.1
```

例如：

```text
DDP5.1
```

可以得到：

```text
audioCodecTag = EAC3 / DDP
audioChannelsTag = 5.1
```

---

# 33. HDR Tags

至少识别：

```text
HDR
HDR10
HDR10+
HDR10Plus

DV
DoVi
DolbyVision
Dolby Vision
```

统一输出可以采用：

```text
HDR
HDR10
HDR10+
DV
```

如果同时：

```text
DV HDR
```

允许：

```text
hdrTags = [DV, HDR]
```

如果现有数据模型只允许一个字段，应调整为可表达多个标签。

---

# 34. Version Tags

至少识别：

```text
Extended
Extended Cut

Director's Cut
Directors Cut

Theatrical

Unrated

IMAX

Remastered

Special Edition

Anniversary
```

建议：

```text
versionTags = []
```

因为一个媒体可能同时：

```text
IMAX
Extended
```

---

# 35. Release Group

支持常见：

```text
-GroupName
```

例如：

```text
Movie.2024.1080p.WEB-DL.x265-GROUP.mkv
```

可以：

```text
releaseGroup = GROUP
```

但不要把：

```text
Movie-Name
```

中的连字符误认为 release group。

优先只在文件名尾部、已出现 Release Tags 后识别。

---

# 36. Bracket Tags

支持：

```text
[1080p]
[WEB-DL]
[HEVC]
[GROUP]
```

不要简单删除所有 `[]` 中内容。

先尝试解析已知标签。

未知内容保留：

```text
rawTags
```

---

# 37. Parentheses

例如：

```text
Movie Name (2024)
```

需要识别：

```text
title = Movie Name
year = 2024
```

但：

```text
Movie Name (Director's Cut)
```

不应当被当成年份。

---

# 38. Language Tags

可以做基础解析：

```text
CHS
CHT

zh
zh-CN
zh-TW

ENG
EN

JPN
JA

KOR
KO
```

输出：

```text
languageTags
```

但不要在本阶段基于语言判断媒体类型。

---

# 39. Noise Tokens

识别并从 title candidate 中排除常见非标题 token：

```text
PROPER
REPACK
RERIP
INTERNAL

MULTI
DUAL

10bit
8bit

WEB
BluRay

AAC
DTS
```

但保留：

```text
rawTags
```

方便 Debug。

---

# 40. Unknown Tokens

不认识的 token 不应该全部丢失。

例如：

```text
Movie.2024.CustomEdition.XYZ.mkv
```

无法识别：

```text
XYZ
```

可以保留：

```text
rawTags
```

或者：

```text
unknownTags
```

避免 Parser 做不可逆信息删除。

---

# 41. Unicode

必须支持 Unicode 文件名：

```text
中文
日文
韩文
重音字符
Emoji（至少不能崩）
```

例如：

```text
流浪地球.2019.2160p.BluRay.mkv
```

应输出：

```text
titleCandidate = 流浪地球
year = 2019
resolutionTag = 2160p
sourceTag = BLURAY
```

---

# 42. Chinese Titles With Numbers

例如：

```text
你好，李焕英.2021.mkv
```

正确。

例如：

```text
三体.2023.S01E01.mkv
```

应尽量：

```text
titleCandidate = 三体
year = 2023
season = 1
episode = 1
```

---

# 43. Titles With Dots

文件名：

```text
Mr.Robot.S01E01.mkv
```

标题：

```text
Mr Robot
```

不要产生：

```text
Mr
```

---

# 44. Acronyms

例如：

```text
S.W.A.T.2017.S01E01.mkv
```

Parser 不应因为连续点分隔导致异常。

可以得到：

```text
S W A T
```

具体标准化是否恢复为：

```text
S.W.A.T.
```

可以留给 Metadata。

Parser 只需提供可靠候选。

---

# 45. Filenames Without Metadata

例如：

```text
video001.mkv
```

允许：

```text
titleCandidate = video001
```

或者低置信度。

不要返回 Parser Error。

缺少年份/季集是正常情况。

---

# 46. Completely Invalid Input

例如：

```text
filename = ""
```

或者 path 无 filename。

应该返回：

```text
InvalidInput
```

或等价 ParserError。

不得 panic / crash。

---

# 47. Parser Error Model

建立轻量统一：

```text
ParserError
```

区分：

```text
InvalidInput
InvalidPath
InternalParserError
```

普通“没有识别到年份”不算 Error。

应该只是：

```text
year = null
```

---

# 48. Parser Warning

建议支持：

```text
ParseWarning
```

例如：

```text
ConflictingYear

ConflictingTitle

AmbiguousEpisode

InvalidEpisodeRange

UnknownReleaseTag
```

Warning 不应让整个 Parser 失败。

---

# 49. Parser Must Be Deterministic

相同输入必须得到相同输出。

禁止依赖：

```text
network
current random state
filesystem state
TMDB
```

当前时间若用于年份合理范围判断：

应通过可注入：

```text
Clock
```

或固定可测试方式实现。

避免测试随着年份变化突然失败。

---

# 50. No Database Side Effects

Parser 本身不得：

```text
写 FileIndex
更新 Database
```

调用方可以选择保存 ParseResult。

Parser 必须尽可能是纯函数/纯服务。

---

# 51. Integration With FileIndex

允许定义：

```text
ParseResult
```

后续如何与 FileIndex 关联的接口。

但本阶段不要让 Parser 自动扫描所有 FileIndex。

调用模式应类似：

```text
DiscoveredFile
↓
ParserService.Parse(file)
↓
ParseResult
```

批处理由后续 Task / pipeline 控制。

---

# 52. Parser Service

可以建立：

```text
MediaParserService
```

负责：

```text
FilenameParser
+
PathParser
+
Merge
```

输入：

```text
FileContext
```

输出：

```text
ParseResult
```

这样后续 Recognition 只依赖：

```text
MediaParserService
```

或 ParseResult。

---

# 53. Parser Architecture

推荐：

```text
Parser
├── FilenameNormalizer
├── FilenameTokenizer
├── FilenameParser
├── EpisodeParser
├── ReleaseTagParser
├── PathParser
├── ParseResultMerger
└── MediaParserService
```

不强制按文件名完全一致。

如果当前代码架构已有更合理模式，沿用。

避免过度拆分。

---

# 54. Rule Tables

Release Tag 等规则优先集中管理。

不要出现：

```text
if filename contains "1080p"
```

散落在多个文件。

建议：

```text
ResolutionPatterns
SourcePatterns
CodecPatterns
HDRPatterns
AudioPatterns
VersionPatterns
```

方便未来扩展。

---

# 55. Parser Configuration

可以设计：

```text
ParserOptions
```

至少预留：

```text
episodeRangeLimit

yearMin
yearMaxOffset

enableChineseEpisodePatterns

knownResolutionTags
```

但不要把所有细节都变成用户配置。

稳定的行业规则可以保持代码定义。

---

# 56. Unit Test Strategy

FilenameParser 必须使用：

```text
table-driven
parameterized
```

测试。

不要每一个文件名写大量重复测试代码。

---

# 57. Minimum Filename Corpus

至少加入 **50 个不同输入场景**。

建议覆盖下面类别。

---

# 58. Movie Examples

至少：

```text
The.Matrix.1999.1080p.BluRay.x264.mkv

The.Matrix.1999.2160p.UHD.BluRay.REMUX.HEVC.DV.HDR.mkv

Dune.Part.Two.2024.2160p.WEB-DL.H265.mkv

2001.A.Space.Odyssey.1968.1080p.BluRay.mkv

Movie Name (2024).mkv

Movie.Name.2024.Extended.1080p.mkv
```

---

# 59. TV Examples

至少：

```text
The.Last.of.Us.S01E03.2023.2160p.WEB-DL.mkv

Breaking.Bad.S05E16.1080p.BluRay.mkv

Show.Name.S1E2.mkv

Show.Name.1x03.mkv

Show.Name.E03.mkv

Show.Name.S01E01E02.mkv

Show.Name.S01E01-E03.mkv
```

---

# 60. Chinese Examples

至少：

```text
流浪地球.2019.2160p.BluRay.mkv

流浪地球2.2023.2160p.WEB-DL.mkv

三体.2023.S01E01.2160p.mkv

漫长的季节.第01集.1080p.mkv

动画名称.第03话.1080p.mkv
```

---

# 61. Directory Context Examples

至少：

```text
/The Last of Us (2023)/Season 01/S01E03.mkv

/Breaking Bad/Season 05/Breaking.Bad.E16.mkv

/三体 (2023)/第1季/第01集.mkv
```

---

# 62. Release Tags Examples

至少组合：

```text
2160p
1080p

WEB-DL
BluRay
Remux

H264
x264
H265
x265
HEVC
AV1

HDR
HDR10+
DV

AAC
DDP5.1
DTS-HD.MA.7.1
TrueHD.Atmos
```

---

# 63. Noise Examples

至少：

```text
PROPER
REPACK
INTERNAL
MULTI
10bit
```

验证不会污染主要标题候选。

---

# 64. Group Examples

至少：

```text
Movie.2024.1080p.WEB-DL.x265-GROUP.mkv
```

验证：

```text
releaseGroup
```

同时增加一个带正常连字符标题的反例。

---

# 65. Malformed Examples

至少：

```text
Show.S01EXX.mkv

Show.SXXE01.mkv

Show.S01E01-E99999.mkv

....mkv

movie..2024...1080p.mkv

empty filename
```

Parser 不得 crash。

---

# 66. Conflict Tests

例如：

```text
/Movie (2023)/Movie.2024.mkv
```

应产生：

```text
filename year = 2024
directory year = 2023
warning
```

而不是静默选择后丢失另一个值。

---

# 67. Parser Purity Test

使用 fake/mocked dependencies。

执行 Parse 后验证：

```text
Storage mutation calls = 0

Metadata calls = 0

Database write calls = 0
```

---

# 68. No Network Test

Parser 测试应完全离线运行。

不得：

```text
调用 TMDB
DNS
HTTP
```

---

# 69. Performance Test

无需大型 benchmark。

但可以构造例如：

```text
10,000 filenames
```

批量解析。

目标：

- 不出现明显 O(n²) 字符串算法
- 不存在严重内存泄漏
- 正则表达式不存在明显 catastrophic backtracking

如果引入 regex，重点检查 ReDoS 风险。

---

# 70. Regex Safety

对于用户不可控媒体文件名，正则必须避免：

```text
catastrophic backtracking
```

尤其避免复杂：

```text
.*.*.*
```

形式。

如果支持用户自定义 Parser regex，不属于本阶段。

---

# 71. Scanner Regression

运行：

```text
ResourceLibrary tests
Scanner tests
FileIndex tests
```

确保 Parser 加入后没有让 Scanner 开始承担媒体解析职责。

Scanner 仍然只负责发现。

---

# 72. Storage Regression

运行：

```text
LocalStorage
SMBStorage
OpenListStorage
S3/R2Storage
```

相关回归测试。

---

# 73. DryRun Regression

已有：

```text
Planner / DryRun
```

zero-mutation 测试继续 PASS。

---

# 74. No FFprobe

全仓库检查：

```text
ffprobe
ffmpeg
```

除文档中的禁止说明外，不得存在运行时依赖。

---

# 75. Do Not Implement

本阶段严禁实现：

```text
RecognitionRule Engine

RecognitionType A/B/C resolution

RecognitionTypePolicy execution

TMDB Provider

Metadata candidate search

Metadata scoring

最终 Movie / TV 身份确认

Naming

Classification

Organizer

Web UI
```

特别注意：

输入：

```text
The.Matrix.1999.mkv
```

本阶段可以输出：

```text
titleCandidate = The Matrix
year = 1999
```

但不得输出：

```text
This is TMDB movie 603
```

---

# 76. Documentation

更新：

```text
docs/progress.md
```

标记：

```text
Phase 6 FilenameParser + PathParser
```

同时更新：

```text
docs/architecture.md
```

记录：

```text
Parser responsibility

FileContext

ParseResult

Filename normalization

Episode parsing

Path context

Merge strategy

Release tag normalization

Parser warnings

Parser evidence

No network boundary

No mutation boundary
```

---

# 77. Completion Criteria

Phase 6 只有满足以下条件才完成：

- FilenameParser 完成
- PathParser 完成
- ParseResult 完成
- Parser evidence 完成或已有等价机制
- Filename normalization 完成
- titleCandidate 提取正常
- year 提取正常
- Season/Episode 正常
- Multi Episode 正常
- Episode Range 正常且有安全上限
- 中文集/话基础格式正常
- Season directory 正常
- Parent directory title/year 补充正常
- Path/Filename 冲突不会静默丢失
- Resolution tags 正常
- Source tags 正常
- Video codec tags 正常
- Audio tags 正常
- HDR/DV tags 正常
- Version tags 正常
- Release Group 基础解析正常
- Unicode 正常
- malformed input 不 crash
- Parser deterministic
- Parser zero mutation
- Parser zero network
- 不使用 FFprobe
- 至少 50 个代表性文件名/路径测试
- Scanner regression PASS
- Storage regression PASS
- DryRun regression PASS
- docs/progress.md 更新
- docs/architecture.md 更新
- 未开始 Recognition / TMDB

---

# 78. Final Report

完成后输出：

## Phase 6 Result

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

## Parser Architecture

说明：

```text
Filename normalization

tokenization

title extraction

year parsing

episode parsing

path context parsing

release tag parsing

merge strategy

warning/evidence strategy
```

---

## Supported Episode Formats

明确列出实际已支持：

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
第1话
```

不要报告未测试的格式。

---

## Supported Release Tags

按类别输出实际支持情况：

```text
Resolution:
Source:
Video Codec:
Audio:
HDR:
Version:
Language:
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

说明测试语料数量：

```text
Filename/path parsing cases:
```

---

## Regression

输出：

```text
Scanner: PASS/FAIL
FileIndex: PASS/FAIL

LocalStorage: PASS/FAIL
SMBStorage: PASS/FAIL
OpenListStorage: PASS/FAIL
S3/R2Storage: PASS/FAIL

DryRun: PASS/FAIL
```

---

## Parser Safety

明确：

```text
Storage mutation calls: 0

Metadata/network calls: 0

Database write calls from parser: 0

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

没有配置：

```text
N/A
```

---

## Known Limitations

如实列出。

例如：

```text
Bare E01 cannot reliably infer season.

Unusual fansub naming may require future rules.

Parser provides candidates, not verified media identity.

Unknown release tags are preserved but not interpreted.

Directory and filename conflicts are deferred to Recognition/Metadata.
```

---

## Final Recommendation

全部阻塞项通过后：

```text
Phase 6 accepted. Ready for Recognition Rule Engine and RecognitionType resolution.
```

如果存在阻塞项：

```text
Phase 6 not accepted. Blocking issues remain.
```

不要自动开始 Phase 7。

最后更新：

`docs/progress.md`