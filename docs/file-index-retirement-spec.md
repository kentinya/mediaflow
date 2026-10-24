# FileIndex 完全退役与实时文件列表统一 — Slice45（CURRENT / PASS / CLOSED）

本文件保留 Slice45 已验收的 CURRENT 退役合同；稳定要求为
[V2-FILES-005/006](v2-requirements.md)。完整 Contract 与验收证据见
`13ecfc0e75fc34ff0ae489e655124a178943cba4:SLICE.md`，当前状态见 [Progress](progress.md)。
后续 TARGET 修订以当前 [SLICE.md](../SLICE.md) 为准，不撤销 FileIndex 退役及其安全边界。

## 1. 用户旅程与范围

| 环节 | 必需结果 |
|---|---|
| 目标 | 查看所选资源库/媒体库此刻真实存在的目录和文件，不维护另一份文件目录数据库 |
| 入口 | CLI `mediaflow files list`；V2 文件页；V2 媒体库页；对应库级实时浏览 API |
| 可见状态 | 明确的库种类/名称、相对目录、真实文件名/类型/大小/修改时间、有界分页与可用状态 |
| 动作 | 选择一个库、打开目录、翻页、刷新；浏览动作不准备整理或保存文件观察 |
| 成功 | 三种入口对同一库和目录使用同一应用浏览行为，显示相同 Storage 条目与边界 |
| 失败 | 缺少/无效/停用库、无 Active、路径越界、权限、Storage 不可用、过期游标明确拒绝，不回退索引或空列表 |
| 恢复 | 修复相应配置/权限/连接，重新读取当前目录；过期分页从首页重新列举，不自动提交工作 |

“只列表不记录”约束列举、导航、刷新和分页：不创建或更新 FileIndex/文件目录记录、扫描/
观察任务、Job、Result、业务处置或执行许可，不调用 Metadata Provider，不读取文件内容作 Hash，
不修改媒体。可读取配置以解析库和 Storage。普通服务访问日志不构成文件目录索引。

操作者随后明确发起的整理、文件维护、决定或恢复仍按其原规则持久化 Task/TaskItem、
精确来源/计划、Result 和审计；不能用“列表不记录”删除执行安全所需证据。
文件页和媒体库页已有维护动作继续存在，媒体库仍不是整理来源。

## 2. 三入口的共享应用行为

复用现有 `RuntimeFilesBrowserService` 的库级实时浏览，CLI 直接调用同一应用行为；
不复制一套 CLI 遍历器，不通过 shell/浏览器绕行，不以 FileIndex/Result 决定条目是否存在。

统一输入为库种类、稳定库 ID、库根下相对目录及现有有界分页参数。
应用解析精确 Active 的 Storage/root，所有 list/stat 均通过 Storage 接口。
ResourceLibrary 与 MediaLibrary 的同名 ID、同 Storage/root 仍是不同作用域。
游标沿用服务端已有的库种类/ID、配置和目录绑定规则，不跨种类、目录或配置使用。
游标是无状态的并带认证密钥，因此同一部署内的 CLI/API 进程必须共享同一内部密钥：该密钥由
受支持的初始化在托管配置存储中原子 create-if-absent 生成一次，只读列表只读取它、不建库/
不升级/不覆盖；缺失或损坏明确拒绝并指向正常初始化，而不是每次读取临时生成一个进程密钥。
密钥属于内部元数据，不是业务配置、不属于 Active 文档、不导出、不呈现给操作者。

列表保留所有被现有浏览规则支持的真实文件/目录类型，不套用媒体整理的扩展名、识别、稳定性
或已整理状态过滤。名字、Unicode、边界空白和相对路径不 trim 或改写；路径限制和 symlink
行为沿用已有浏览/Storage 安全规则。不为了得到“总量”遍历未请求的整库。
有界结果、截断、下一页及未知总量真实表达；Storage 故障不显示为零。
实时目录变化可能使后续分页失效，不承诺未建立快照的跨请求完整快照一致性。

## 3. CLI 的 CURRENT 使用方式

```bash
mediaflow files list --resource-library SOURCE_ID --path "relative/directory" --limit 100
mediaflow files list --media-library MEDIA_ID --path "relative/directory" --limit 100
mediaflow files list --resource-library SOURCE_ID --path "relative/directory" --limit 100 --cursor CURSOR
```

两种库选择互斥且必须明确；路径默认库根，使用库相对路径。缺少/冲突选择给出可操作用法，
不默认为全部库递归、不把 `--storage` 加任意路径作为库约束绕过。CLI 与 Web 解析同一 Managed
Active；不为列举自动创建业务配置、任务、文件目录数据库或触发 schema 初始化/升级。
尚无 Active 时给出已有设置路径，不把旧 JSON 中的竞争快照当作 Web 当前 Active。

输出为当前目录的真实条目和分页信息，不带 FileIndex ID、scanStatus、识别/Provider/整理状态。
旧的 `--scan-status`、`--cursor-file-id`、metadata/Task 派生筛选和索引时间游标不再受理；
不把旧参数静默解释为另一种查询。若保留纯名称展示筛选，必须说明其有界目录范围，
不能宣称它搜索整个文件索引。`files show FILE_ID`、索引 `files stats` 及 FileIndex 专用 API/
页面/Deep link 一并退役，只需简短退役说明与库级浏览/任务中心指引，不保留兼容查询引擎。

## 4. “完全退役”的完成含义

不是只删除 CLI 列表或将 FileIndex 隐藏。最终候选不再有 FileIndex 的产品入口、运行装配、
接口/模型/仓储实现、后台读写、内存替代索引、全局 occurrence/disposition 目录、专用 schema
及无消费者代码；新建运行数据库不创建 FileIndex 专用表/索引。不能把同一长期文件目录改名
为缓存、观察服务或把旧仓储改成 no-op 来宣称退役。

原运行依赖已在同一个完整退出业务单元中收敛：

下表列的是已移除的旧依赖及当前替代边界。独立 Preview 产品另按同 Slice RO-8 的
[Preview 退役设计](preview-retirement-spec.md) 完整退出；RO-7 不为它新建索引兼容或修复服务。
需要保留的是整理/恢复/配置/授权校验的共享分析和精确计划证据，不是独立 Preview 生命周期。

| 已退出的依赖 | CURRENT 行为 |
|---|---|
| `files list` → FileCatalog → SQLiteFileIndex；show/stats 和 `/files`、`/file-index` 索引接口 | list 改为共享库级 live browse；索引产品接口/命令删除或薄拒绝 |
| StorageScanner/ResourceLibraryScanner 的全局索引写入、New/Modified/Unchanged/Missing 对账 | 保留内部发现/过滤/稳定性；不再维护全局文件目录或 Missing 对账产品 |
| Manual intent/Preview 的 FileID/索引来源解析与“先扫描”恢复 | 统一为库/精确 live Storage 来源；合法 pin、来源变化和计划确认保持 |
| Worker/API/CLI、Automation Preview/执行对 FileIndex 的强制装配或准入条件 | 必要共享依赖替换为现有 Storage/工作内来源证据，缺 Index 不再成为运行条件 |
| Result 自动同步、FileIndex reconcile/reprocess 服务/路由/状态/按钮/导出字段 | 删除索引同步/修复路径；正式结果与安全恢复仍以 Task/Result/checkpoint 为准 |
| Files/direct commands 的可选索引反馈与同步 | 完成后直接读 live Storage；维护结果正常持久，不调用索引 |
| Dashboard/CLI/API 的索引统计、FileIndex 链接、测试/安装/容器启动装配 | 去除索引专属能力与依赖；其他真实 Task 指标/详情不回归，不扫描整库制造新统计 |

来源身份与全局索引是不同概念：Task/计划自己的库种类/ID、Storage、精确相对路径、
metadata/fingerprint、版本、pin 和已完成效果仍可保存并用于准入、并发和恢复。
这些事实只能服务该显式工作的范围/关联，不能回填成 browse 的文件目录。
不因仅路径相同或旧成功结果，永久压住同路径后来出现的新文件；现有锁、原子准入、
精确请求去重、目标冲突和成功/未知效果非重放继续成立。

## 5. 整理、稳定性及 Automation 边界

列举仅回答当前目录有什么；显式整理准备才开始现有有界发现和稳定性观察。
优先复用 `MediaDiscoveryService/Worker`、`scan_filters` 与工作自己的持久 scope/观察。
stable-size 必须跨真实配置区间的未变观察；大小/mtime/有效指纹变化重置区间，
不能把旧 mtime、第一次 stat 或一个空内存索引当作稳定证明。
长工作沿用现有 Task/Worker 和 lease/fence，配置 pin、范围/时间/条目限制保留；
无 FileIndex 仍能新建→分析→同页摘要→明确确认→执行，并从 Task/checkpoint 完成恢复。

Automation 的共享发现、来源验证和运行装配不再依赖 FileIndex。受支持流程的定义授权、
scope、Provider、冲突、执行安全及 Task/Result/pin 保持；退役不产生额外执行权限。
Automation 的验收状态见 [Progress](progress.md)，当前修订见 [SLICE.md](../SLICE.md)。
本合同不要求旧产品兼容或迁移，也不授权扩展其他业务。

## 6. 服务未上线的交付边界

不存在生产旧 FileIndex/Scan 数据兼容义务：不建设旧索引库升级、双读双写、数据搬迁、
历史 FileID/API 兼容、在途接管或索引同步修复机制。以新建环境和受支持工作为验收基础。
无需为开发 fixture 保留已退役代码；fixture 应使用 live Storage 和显式 Task/Result。

删除源码中的废弃 schema/装配不等于授权操作当前数据库或媒体。本次退役不清空、drop、
重建任何用户/开发运行库，不通过启动自动清库来绕过旧版本。遇到不支持的开发旧 schema，
明确报错并说明使用隔离新数据目录；不新增复杂生产迁移旅程。
当前支持版本的普通 Task/Result/pin/许可及其重开/重启/故障原子性仍受正常安全规则保护。

## 7. 必需验证与收尾

- 临时 Storage 中同一批混合条目：CLI/文件页/媒体库页在对应库/目录上逐项一致，
  翻页、长名/空白、同名跨种类库、越界/非法游标、403/无Active/连接失败可解释。
- 多次 list/刷新/翻页前后无文件目录写入、新 Task/Job/观察/权限或媒体 mutation，Provider 调用为零；
  没有 FileIndex 模块/表或仓储实例仍可完成三入口读取，拒绝不偷偷建库。
- 新来源无预扫描完成真实稳定观察→摘要→选定子集确认→Worker/OrganizerExecutor 结果；
  有 pin 变化、来源替换、重复/丢响应、同任务混合结果与未知效果非重放反例。
- 其他受支持工作的控制/恢复/历史、附件按策略结果、普通维护和已接受 Automation 基础消费者
  在没有 FileIndex 装配时可运行；零 mutation 分析、安全锁与旧 owner fencing 保持。
- 新建数据库与包/镜像不再包含/创建可运行 FileIndex；wheel/生产 Docker 实际验证 live CLI/
  API/常驻 Worker，不使用“未配置文件索引”拒绝、空结果或 no-op mock 代替完成。
- 通过完整 T4、实际三入口原生检查及依赖/死代码清单审查；不要求旧 FileIndex 生产迁移矩阵。

RO-7 已随整个 Slice45 通过验收。实际三入口原生结果、wheel/安装消费者、生产 Docker/
Worker/recovery/restart、输入复用和外部环境 skips 见 Closure Packet；不宣称旧索引生产迁移。
