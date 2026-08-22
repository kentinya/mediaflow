# 影视媒体资源自动整理系统需求规格说明书

**文档版本：V1.1（工程需求基线）**
**项目类型：影视媒体资源管理 / 自动整理系统**

> 当前实现状态与最终产品范围以根目录
> [《影视媒体资源自动整理系统需求规格说明书》](../影视媒体资源自动整理系统需求规格说明书.md)
> 为准；分阶段交付计划见 [roadmap.md](roadmap.md)。截至 2026-08-22，核心 CLI、持久任务、
> 目标冲突确认、元数据/分类复核、可选附件文件集合和全 Storage JSON Runtime 已完成；
> 服务 API 已具备 RBAC、审计、凭证运维护栏，以及复核与 Task/Job/Result 只读 Web UI；
> 大型运行历史支持稳定有界的双向游标分页，调度与通知具有严格有界的只读运维界面；
> 生产级身份源和 TLS 终止仍属于后续部署阶段。

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
