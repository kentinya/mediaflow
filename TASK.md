# Task 45.4 — 独立 Scan 完整退役与整理内部稳定性连续性

遵循 [Development Workflow](docs/development-workflow.md)，从属于已提交的
[Slice45 Contract](SLICE.md)。规划/审查读取 [B 经验](docs/agent-experience/task-planner-reviewer.md)，
实现读取 [Developer 经验](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.4
Parent Slice: 45
Status: READY FOR B REVIEW
Task Base: f02443917bcd5b3ef645a32c432b191dc4f12aa3
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Next Action: B REVIEWS TASK45.4 CHECKPOINT; RO-7 REMAINS DEFERRED
```

## Goal

操作者直接在整理工作流中完成发现、必要的真实稳定性观察、同页摘要及明确确认；不再存在
可创建、执行、重试或继续的独立 Scan 产品。旧入口明确说明退役并指向新建整理；移除 Scan
专用代码，保留整理所需的共享 Scanner/过滤/真实稳定性能力及其他受支持任务的结果和固定配置。
服务尚未上线，不建设旧独立 Scan 的停止/接管、升级迁移或专用历史读取/取消/导出兼容。

完成 **RO-5 / S-7**，以及该退役所必需的 **RO-4 / S-5 其他受支持工作的历史/控制连续性**、
**RO-6 / S-6 共享 API/Worker/Persistence 集成**。不改变 RO-1/2/3 已验收旅程、附件修订或冻结
Slice43 的定义绑定 Automation 模式边界。
适用要求：V2-OPS-009–012、V2-UX-001–003、V2-AUTH-001–003、V2-SAFE-001、
V2-MIG-001–003、REQ-SCAN-002–006、REQ-TASK-*、REQ-RECOVERY-*、REQ-SAFE-*、UX-001–010。
REQ-SCAN-001 的独立入口按已授权 V2 修订退役，内部发现与稳定性义务不降低。
FileIndex 完全退出及 CLI/两种库页实时列表统一现属同一 Slice 的 RO-7，留给本 Task PASS
后的一个连贯 Task；本 Task 不承担 RO-7 验收，不得在 Scan 退役后将 Slice 记为完成。

## Previous Task Review / Why This Task Exists

### Task45.3 B Review 10 — PASS，2026-10-18

- Reviewed Range：`8f5cf4e284766bcc8894817d7640231e85050fb2..f02443917bcd5b3ef645a32c432b191dc4f12aa3`。
  Executable Head：`1bd67c7e5cbf37a4523af89bf73089beedadf61f`；其后仅 TASK.md 报告变化。
- A 的附件修订/策略动作澄清已提交，Task45.3 继续合法，Review7–9 阻塞已解决。
  主文件先执行并验证，附件分别保留失败/未执行/冲突原因、来源/目标、步骤、确定性和固定策略动作。
  主文件完成伴附件警告显示部分成功；未知效果只核查，不新增附件-only 执行或主文件重放。
- B 独立相关 Python **275 tests / 25.770s / OK**；production build PASS；完整真实
  Python/API/SQLite/Worker 浏览器 **37 passed / 1.2m**（workers1/retries0/trace on）。
  五类输入、新阻塞转类、再次失败/成功、少选子集、未知响应、暂停重新授权、重开和 C 身份均覆盖。
- B 另用 fresh fixture 经真实 API/Worker 复现主文件 MOVE 完成、字幕冲突，核对持久结果及重开，
  原项未提供主文件 retry；实际 Task Base schema45→47、合法旧 pin/许可保留及两处 ALTER 故障回滚 PASS。
  实看独立桌面/窄屏新阻塞、摘要和附件告警；主目标和附件目标可换行，操作可达。
- 核对实际 raw logs、匹配源码/依赖/产物后复用最终 T4：Python **2517 / 7 skipped / OK**，
  Vitest **1133**、fake E2E **246**、real Unicode **1**、visual **2**、质量/安全、wheel/安装 consumer、
  Docker 恢复和 release-security。7 skips 是未提供的隔离 endurance/真实外部 Storage 环境，非 PASS。
  独立从实际镜像核对 **163 Python / 4 Web** 文件，wheel163文件与候选逐字节一致。
- B 原始日志、可重跑 probe、截图、迁移、SHA/产物核对及复用限制：
  `.git/validation-evidence/1bd67c7e5cbf37a4523af89bf73089beedadf61f/b-review10-20261018/INDEX.md`。
  Developer 原报告及此前审查保留于本 Task Base 的 TASK.md；没有独立 review commit 或 push。

### 每次 PASS 后的 Slice 全部结果复核

| Required Outcome / Surface | 当前事实 |
|---|---|
| RO-1 / S-1 | Task45.1 PASS：九标签、完整授权总体查询/计数和任务/类型文件定位 |
| RO-2 / S-2 | Task45.2 PASS：创建/Files 同页准备、摘要、精确子集确认和真实 Worker |
| RO-3 / S-3、S-4 | Task45.3 PASS：五类原生输入、安全分析、新阻塞、同页摘要确认、批次独立结果和附件按策略指引 |
| RO-4 / S-5 | 其他受支持工作的详情/记录/导出/协作控制及恢复连续性保留；按 A 修订取消旧独立 Scan 历史/停止兼容 |
| RO-5 / S-7 | **未完成**：仍有独立 Scan Web/API/CLI/Job/恢复分支与“先 Scan”依赖，本 Task 完成 |
| RO-6 / S-6 | 已有统一权威及 Task 证据；仍需退役集成和之后 B 的 Slice-final 验证 |
| RO-7 / S-8、S-9 | **未完成**：后续 A 修订加入同 Slice；FileIndex 仍有完整运行依赖，CLI 仍读索引。45.4 PASS 后规划一个完整退出与列表统一 Task |

**All Required Outcomes satisfied: NO → NEXT TASK。** 不提交 Closure Packet，不宣布 Slice 关闭。
本表已反映随后 A 新增的 RO-7，不将其倒记为 Task45.3 当时已交付的结果。
规划前 `python3 scripts/check_governance.py` PASS；HEAD:SLICE.md 与工作树一致，Slice45/Roadmap ACTIVE。
Task Base 固定为上述规划前 HEAD，不随规划、实现或修正提交移动。

### A 修订后的 B 范围复核 — 2026-10-18

```text
Contract Checkpoint: 90cc8897e6f8e43eb9c215c5bf4a48b7b8f88a71
Decision: TASK45.4 CONTINUES WITH LEGAL SCOPE ADJUSTMENT
Task ID / Base: UNCHANGED
Difficulty / Test Level: High / T4 — UNCHANGED
Implementation Review: NOT PERFORMED; NO PASS CLAIM
```

用户明确授权 A 按未上线现状取消旧 Scan 的生产升级/在途停止与专用历史兼容义务；A 已同步
提交 Slice、稳定 V2 修订、TARGET 设计/旅程与当前范围指针。B 在该已提交 Contract 上复核：
当前 Goal 仍是同一个独立 Scan 退役业务单元，**同 Task 合法调整后继续，不重新规划或移动 Base**。
本文旧 AC-2/AC-3、开发步骤5及 Required Tests 中的旧 Scan 停止/迁移/历史兼容矩阵被下方
新范围取代；不是将对应能力记为已实现，也不是豁免仍适用的安全与 T4 门禁。

Developer 已有未提交的代码和新测试，不能 reset/restore/clean 掉。实际读取的部分改动：

| 已有改动 | 同 Task 后续指导 |
|---|---|
| `automation.py` 未绑定 Definition 的 Scan submit 拒绝 | 保留并继续验证；其他提交方式和 Worker 后门仍需逐项检查 |
| `final_cli.py` 的 Scan 提前拒绝、原直接执行/部分继续分支删除 | 保留有效删除/拒绝；退役指引改为实际新建整理，不承诺专用 Scan 历史入口 |
| `service_api.py` 部分 Scan POST/alias 在绑定 runtime 前返回410 | 保留 RBAC/零新工作拒绝；删除仅为 Scan 历史兼容增加的装配/路由/投影 |
| 新 `ManualScanHistoryService` 和 `SQLiteTaskRepository.retire_manual_scan` | 仅服务已取消的旧 Scan 历史/停止目标，应清理它们及专用调用；不另写替代停用/迁移框架 |
| `tests/test_scan_retirement.py` 的 submit/alias/CLI 拒绝反例 | 保留必需退役/RBAC/零工作断言，随最终实现扩展；尚未作为本轮通过证据 |

普通 Task/Result/pin/权限/审计、当前有效工作重连/重启、未知效果非重放继续受保护；不执行
数据库清空或媒体删除。FileIndex 完全退出不属于本 Task，后续同 Slice 的 RO-7 承担。
无其他消费者的 Scan 专用模型/读写/取消代码可删除；仍由共享 Scanner 或冻结定义绑定流程
消费的部分必须保留。
A 的8个文档修改在完整 Task Base..Head 中按上述 SHA 单独归属，Developer 不得将其当自己的
实现或再改范围；冻结文档对照此 A checkpoint，Task/code 仍对照原 Task Base。

### FileIndex 纳入 Slice 后的 B 范围复核 — 2026-10-18

```text
Contract Checkpoint: 0237b7d366bd24e9182797a72cb4939b528602ba
Decision: TASK45.4 CONTINUES; RO-7 REQUIRES ONE NEXT COHERENT TASK AFTER PASS
Task ID / Base / Goal: UNCHANGED
Difficulty / Test Level: High / T4 — UNCHANGED
Implementation Review: NOT PERFORMED; NO PASS CLAIM
```

B 在 A 提交后运行 `python3 scripts/check_governance.py`，结果 PASS；已提交 Slice45/Roadmap
为 ACTIVE，Contract 与工作树一致，原 Slice/Task Base 保持。核对当前未提交代码、现有测试
及三个列表入口：CLI 使用 FileCatalog/SQLiteFileIndex；两种库页已共用 RuntimeFilesBrowserService；
Scanner、整理/恢复、Result 同步和 Automation 基础仍有索引消费者。此前未提交实现均保留。

当前 Scan 退役目标和已开发部分仍合法，继续同 Task；不把新增 RO-7 塞入已在开发的范围，
也不创建第二个活动 Task。45.4 PASS 后 B 必须重新核对全部 Outcome，再按
[退役设计](docs/file-index-retirement-spec.md) 规划一个完整 FileIndex 退出与 CLI 统一 Task，
覆盖所有运行消费者/新库/生产装配及真实无索引整理恢复，不能仅改 list 或按模块拆碎。

给当前 Developer 的边界：

1. 继续下方 Scan 入口/执行路径删除、内部真实稳定性和 T4，不实施 FileIndex 仓储/schema/
   统计/reprocess 的整套退出，也不提前改变 `files list` 接口。
2. 为移除“先 Scan”前置复用现有 live Storage 和工作内观察；不要新增索引补偿、兼容服务、
   no-op 仓储或双写。现有仍被消费的索引暂由后续 RO-7 单元统一移除，不是最终交付例外。
3. 不建设旧 Scan/FileIndex 生产迁移、历史兼容或接管框架，不清空数据库/媒体；现有普通
   Task/Result/pin/权限/未知效果非重放与共享稳定性不回归。
4. A 本次10个文档的变更归属上述 Contract checkpoint；连同先前 A 修订从实际 Base..Head
   中单列，不当作 Developer 实现。冻结文档以本 checkpoint 对照，代码仍对照原 Task Base。
5. 完成报告明确列 RO-7 尚待后续 Task。B 不能因本 Task PASS 提交 Closure Packet 或宣布关闭。

### 实际代码与复用边界

- **Task Base 的情况：** `manual_scan.py` 的 ManualScanService 可准入/启动独立线程；`service_api.py` 的
  `/api/v1/operations/scans`、`/api/v1/scans`、`manual-scan(s)` aliases 仍连接它。
- `final_cli.py` 在 Task Base 有 `scan` 执行段和 paused scan resume/continue 分支；
  `AutomationJobService.submit` 仍接收未绑定 Definition 的 SCAN，不能只删新建页面。
- `ScanNewPage`、`ScanDetailPage`、router/destination-model、typed API/query 与 V1
  `operator_ui.py` 仍有产品入口/命令；readiness、文件操作矩阵和部分恢复提示仍会提供 Scan。
- `MediaDiscoveryService/MediaDiscoveryWorker` 已有有界发现、持久 observation、
  `waiting_stability`、claim/lease、自动准备分析与精确 pin；`scan_filters.py` 已有共享过滤和
  `stability_decision/verdict/wait_seconds`；`StorageScanner/ResourceLibraryScanner` 被整理和
  Automation 内部使用。优先接这些能力，不另建扫描/观察队列或放宽稳定性规则。
- `manual_organize_preview.py` 的部分 FileIndex 兼容来源校验仍提示 bounded/complete Scan；
  后结果 FileIndex reconciliation 也有 rescan 指引。要检查可达依赖并给出可实际使用的下一步，
  不能只把文字改成“重试”而留下不可完成的前置条件。
- 不为 `manual_scan_tasks/items`、Scan 专用投影/页面/API 保留兼容服务或增加迁移机制。
  先检查消费者再删除无用代码；不清空开发库，不删除仍支撑共享 Scanner/其他受支持工作的数据或能力。
- **重要区别：** 定义绑定的 Automation 模式退役归冻结 Slice43。不可按 `command == scan`
  全局删除共享 enum/Scanner 或破坏其定义绑定路径；同时也不能以冻结为理由保留独立 Scan。
  使用已持久的真实 Definition/occurrence/Job/Task/continuation 关联判定来源，不能信任请求伪造的
  definitionId、名称、时间或单个布尔值。发现无法分开之处交 B/A，不私自改 Contract。

## User Journey

| 环节 | 本 Task 验收结果 |
|---|---|
| 目标 | 直接整理安全、稳定的所选媒体，产品不再提供独立扫描 |
| 入口 | 任务中心/Files 新建整理；被移除的 Scan 深链/API/CLI 仅作退役拒绝 |
| 可见状态 | 整理内部发现和真实稳定性等待、未就绪原因/安全下一步；旧入口提供退役说明 |
| 动作 | 在原整理范围内等待/显式重新检查或合法继续；检查新摘要后明确确认；旧入口指向新建整理 |
| 成功 | 无需独立 Scan 即可证明稳定并准备摘要；确认前零 mutation/零执行权限；确认后只有精确所选范围执行 |
| 失败 | 仍在写入、超时/边界不足、缺 pin、权限不足等有对象和阶段说明，不转成假成功 |
| 恢复 | 保留整理原 pin/范围/观察和结果，按现有许可重新检查；不自动 repin、不自动重试提交或重放已完成/未知效果 |

## Implementation Scope / 逐步开发指导

以下是同一 Task 的开发顺序，不能拆成仅删按钮、仅删命令或仅补测试的独立 Task。
每步先跑新增/受影响反馈；修好已知阻塞后再冻结最终候选做 T4。无需逐步申请许可。

### 1. 先列出并验证所有独立 Scan 可达路径

- 读上方实际文件及其调用方，列 Web(V2/V1)、API aliases、CLI、legacy Job、Task retry/resume、
  scope/recovery continuation、Worker dispatch 和建议动作的入口清单；找出仅为 Scan 历史兼容保留的代码。
- 顺着 Definition/occurrence/Job/Task 的真实持久关系区分冻结范围；继续使用既有 pin/权限校验。
- 在报告草稿写一张紧凑清单：每类入口拒绝或删除，哪些函数仍是整理/冻结定义绑定流程的共享依赖。
  不建立新管理对象、框架或一批逐文件 Task。

### 2. 先建立退役反例与稳定性 fixture

- 在现有测试 fixture 中用临时 Local Storage/SQLite/fake Provider 记录 list/stat/read、Provider、
  工作准入、权限和媒体 mutation 次数；复用已新增的 `tests/test_scan_retirement.py`。
- 覆盖直接 Scan、别名、未定义绑定的 Job(scan)、Task retry/resume/continue 和实际 dispatch。
  可构造最小不支持命令记录证明不会执行，但无需建立旧版本生产库、全状态停止/迁移/历史矩阵。
- 建立无预先手动扫描的新目录：一个已满足年龄的文件仍需 stable-size 区间；另一个改变大小/
  修改时间/指纹，另有临时文件和无关兄弟项。使用可控时钟证明判断，不能靠放大 sleep 碰运气。

### 3. 关闭应用层独立准入，再接 API/CLI 拒绝

- 退役判断集中在适用的共享 application admission/dispatch 边界，Web/API/CLI 得到同一含义。
  删除 ManualScanService 的独立创建/执行功能及仅它使用的编排，不留下 diagnostic/legacy 别名。
- 旧 POST/CLI 命令给出稳定退役类别、未创建工作/未执行的真实状态和“新建整理”指引；
  API 用一致的明确拒绝状态（如410），不能改成真正 Organize，也不能先产生 Task 后才拒绝。
- `/api/v1/jobs` 等通用提交不能绕过；客户端传 definitionId 不能冒充定义绑定工作。
  CLI 旧命令可有仅返回退役说明的薄拒绝入口，不保留能执行 Scan 的参数、service 或 runner。
- 即使未配置 Active、Provider 不可用或 Worker 未启动，也不为了拒绝旧 Scan 而构造 Provider/
  遍历 Storage。RBAC 不降低，权限拒绝与已退役的说明均需有界脱敏。

### 4. 封住旧 Worker、重试和继续的执行后门

- 检查 `final_cli.py`、Job consumer、scope/recovery admission/consumer、Task retry/resume。
  在创建 StorageScanner、构造新 Task 或重用来源范围之前拒绝独立 Scan。
- 删除只为独立 Scan 服务的 `_continue_paused_scope` / `_continue_scope_from_admission` 等分支；
  有共享/定义绑定部分则按真实来源保留最小必要行为，不保留独立 Scan 兼容执行器。
- 任意可达的独立 Scan dispatch 必须在遍历/准入前拒绝，不得通过不支持的 command、retry 或
  continuation 绕过。仅证明不可执行，不新增旧 Scan 状态接管、停止确认或启动清退机制。
- 沿用既有 claim/lease/fence、版本和取消语义，不新建队列或额外执行引擎。

### 5. 清理已写的 Scan 专用兼容代码，不重做有效退役改动

- 先检查新 `ManualScanHistoryService` 的调用者，将 Scan 专用 GET/detail/cancel/export 及装配
  删除或收敛为薄退役拒绝；不要为开发记录维护完整历史服务。按实际调用需要保留最小安全错误类型。
- 删除仅为旧 Scan 安全停止新增的 `retire_manual_scan` 及其调用、状态补偿和对应专用测试。
  不另写 startup drain、跨旧进程 fencing、旧生产库迁移/停止框架来替代它。
- 继续删除已无消费者的 Scan 专用 domain/repository/UI 代码；共享 Scanner/过滤/稳定性、
  其他受支持工作的通用 Task/Result/pin/审计及冻结定义绑定消费者保留。不要全局搜索替换 `scan`。
- 不直接清空/删除数据库或媒体，不为“卸载 Scan”做破坏性数据清理。无 schema 变更就提供实际
  diff；确需改变共享 schema 时仍验证受影响数据保留、升级失败原子性和重开，不制造无必要新状态。

### 6. 让普通整理自行完成稳定性观察

- 先复用 `MediaDiscoveryService/Worker` 和 `scan_filters` 已有 observation/waiting_stability。
  任务中心和 Files 单项、多项、目录继续走同一准备链，不借 FileIndex 作为物理来源权威。
- 需要 stable-size 时，第一次观察不等于稳定；第二次 stat 必须跨真实配置区间且可证明未变。
  变化重置观察区间。保留 minimum age、modified threshold、temporary/include/exclude/depth/
  item/entry/time budget、来源版本和精确 pin；不能把很旧的 mtime 当作持续观察证明。
- 显示可解释的等待/未就绪状态和实际允许的等待、重新检查或原范围继续，不提示先启动 Scan。
  长等待/检查由既有持久 Worker 推进，不在 HTTP、浏览器循环或长写事务里等待。
- 重开/Worker 接替只沿用合法观察及原 pin；当前 Active B 不替换原 A，旧 owner 不能发布。
  观察失败或超出界限保留原因，不悄悄执行前 N 项，不制造正式执行恢复待办。

### 7. 修复可达兼容/恢复链的“先 Scan”依赖

- 检查 `manual_organize_preview.py` 的 source/index 校验、恢复/继续、FileIndex reconcile 指引，
  以及普通整理/Automation 内部共用的 Scanner。真正缺少观察时由原工作流有界补足；
  原 pin 不可用/历史身份不足时明确拒绝并指向既有合法的新准备或只读核查。
- 不能只替换文案后仍永远要求一个已不可能生成的 Scan Task/READY 记录；也不能把 FileIndex
  旧记录、年龄或“无错误”当作新的 live source/stable-size 证明。
- 不为这些过渡路径新增 FileIndex 同步修复/兼容机制；完整索引退出按 RO-7 的后续同 Slice
  Task 一次收敛，当前只修复 Scan 退役直接造成的不可达前置。
- 定义绑定模式、配置/调度/Run once 保持冻结边界；只修该 Contract 明确要求的共享稳定性依赖。
  不能导入冻结 Slice43 的未接受实现来满足本 Task。

### 8. 删除 V2/V1 独立创建/执行页面和动作

- 删除 `ScanNewPage` 及创建专用 typed model/query/submit API；移除 router/destination-model、
  Dashboard/Operations/Files/action matrix/readiness 和 V1 `operator_ui.py` 的可执行 Scan 按钮。
- 旧 new/detail URL 均可显示同一简短退役说明与新建整理链接，不自动 POST、不带旧 scope 执行，
  不要求还原 Scan 专用历史详情或取消入口；保留正常认证/合法返回行为。
- 任务中心仍正确展示其他受支持工作及其结果/历史，不为旧 Scan 专设 findings/分页/导出兼容。
  共享内部模块/冻结定义绑定流程使用的 `scan` 字段可保留，不删除或改写其数据来掩盖回归。
- 更新 strict typed 数据、按钮来源及 error/recovery 映射；不用 `any`、假available或404绕过拒绝。
  窄屏、键盘、深链/重连、无权限/无Active/Worker等待均有可达下一步。

### 9. 清理真正无消费者的实现并保住测试含义

- 入口全部收敛后再删除仅供独立 Scan 使用的线程/runner、读写/admit/取消接口、客户端请求和
  死代码；共享 Scanner/filter/stability 及有其他真实消费者的模型/解码不删除。
- 将“创建并执行独立 Scan”的测试改为退役拒绝及零工作证明；取消 Scan 专用历史/在途停止/
  迁移兼容测试义务。通用历史测试改用受支持工作 fixture，不能重新开放 Scan 准入准备数据。
- `operations_inventory_harness.py`、wheel/Docker/security/upgrade helper 当前可能借独立 SCAN
  播种或驱动 Worker。改用现有允许的工作/历史 fixture，移除只为旧 Scan 兼容构造的额外矩阵。
  不能删掉未授权执行、未知效果、source identity 或持久化断言来减少测试范围。

### 10. 跑通原生与生产产物，再冻结最终候选

- 新增完整真实 Python 浏览器案例：旧链接→退役说明；fresh新建整理→真实稳定等待→摘要→
  精确子集确认→真实 Worker；变化来源重置区间，未稳定项无权限/无媒体变更。
- 实际改变的共享发现/观察/claim 并发仍用两个 connection/event/barrier 验证；不再要求旧 Scan
  取消/接管/迟到发布矩阵。保留首次失败与精确复跑，不加 retries/skip 或用 mock 替代实际消费。
- 最终候选按下方 T4 完整验证、源码/产物身份比对、manifest/冻结范围/私密文件检查，提交连贯
  checkpoint 和 Completion Report。Developer 不做 Slice-final、下一 Task 或 A 最终审查。

## Acceptance Criteria

- [ ] **AC-1 全入口退役：** V2/V1 无独立 Scan 创建/执行产品；API/CLI/aliases/legacy Job 及
  Task retry/resume/continue/Worker 不能独立执行，旧请求明确拒绝且指向新建整理；不暗中转 Organize。
- [ ] **AC-2 专用能力删除：** Scan 专用创建/执行/历史/取消装配和无其他消费者的代码删除，
  不以新历史服务、启动清退或旧任务迁移框架替代。任意不支持的独立 Scan 命令在发现前拒绝。
- [ ] **AC-3 其他工作完整：** 其他受支持工作的 Task/Result/历史/导出、pin、权限和审计正常，
  未授权和退役请求零新工作/零发现/零媒体变更；只读不创建工作或调用 Provider。本次不清空运行数据。
- [ ] **AC-4 稳定性不降级：** 未预先手动扫描的新来源可在原整理内完成有界真实观察与新摘要；
  stable-size 必需区间、年龄、变化重置、临时/排除规则及现有限制均保留。未稳定/不完整项不可执行，
  确认前零媒体变更/零执行许可；不再依赖或建议调用退役 Scan。
- [ ] **AC-5 共享权威与冻结边界：** 不增加队列/配置/观察/恢复/执行引擎；真来源身份、原 pin、
  RBAC、claim/fence/原子准入、OrganizerExecutor-only、C→A 身份与已完成/未知效果非重放不回归。
  定义绑定 Automation 的模式/发布/调度/页面仍归冻结 Slice43，不导入或宣称完成其实现。
- [ ] **AC-6 原生旅程：** 新整理、旧入口退役说明及其他受支持工作在桌面/380px/键盘/深链/
  返回/重连可用；Worker、稳定性、权限、缺 pin、未知请求均有真实下一步，无CLI回退或内部材料处理。
- [ ] **AC-7 T4/交付真实性：** 聚焦/全量/真实Python/迁移适用边界及wheel/Docker最终证据匹配
  精确候选；预存脏文件和已提交A-owned文档保持；删代码不清空运行数据/媒体，不改稳定需求或CURRENT声明。

## Required Tests

High/T4 来自入口/权限、共享核心发现/来源身份和持久 Worker；不再来自假定的生产旧 Scan 迁移。按 workflow
先修聚焦失败，再完成最终候选；完整 suite 包含 focused 时记录覆盖，不重复机械跑同一测试。
主工作区 ignored runtime DB 属用户环境；全量在精确候选干净隔离 checkout 跑，禁读/改用户库。

### Development and correction feedback

1. 退役边界：先跑新增的 Web/API/CLI/legacy Job/Task continuation 反例，再跑
   `.venv/bin/python -m unittest tests.test_scan_retirement tests.test_manual_operations_contract
   tests.test_manual_operations tests.test_automation_api tests.test_automation_admission
   tests.test_batch_cli tests.test_task_retry tests.test_task_pause_resume tests.test_scope_continuation`。
   覆盖 aliases、未认证/无权限、未配置Active、伪造definition关联和不支持命令的dispatch；
   所有拒绝核对零新工作/观察。删除纯旧 Scan 兼容测试无需补等价历史/迁移测试；仍适用的
   RBAC、零变更、共享消费者断言要映射到现有或新测试，不删除它们造绿。
2. 共享发现/稳定性与准入：
   `.venv/bin/python -m unittest tests.test_scanner tests.test_media_discovery
   tests.test_media_discovery_provider_manifest tests.test_organize_preparation
   tests.test_manual_organize_preview tests.test_manual_organize_execution
   tests.test_recovery_continuation tests.test_task_persistence tests.test_organizer_mutation_authority`。
   fresh观察→未满间隔拒绝→满间隔就绪、大小/mtime/指纹变化重置、重开/旧owner、pinA→ActiveB、
   缺pin、目录/多项/单项和临时文件；分析零mutation、执行子集精确和附件告警回归。
3. 冻结定义绑定路径及历史/计数：
   `.venv/bin/python -m unittest tests.test_automation_definition_execution
   tests.test_automation_definition_occurrence tests.test_operations_task_center
   tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_processing_checkpoint`。
   不把定义绑定模式顺手退役；独立scan不接受，其他受支持工作的结果/历史正确且读取无副作用。
4. `web/`：`npm run test -- run src/features/operations src/entities/operations
   src/shared/api src/shared/navigation src/routes`。覆盖退役深链、Scan专用请求代码消失、其他工作详情和
   auth/返回、当前命令可用性；受影响Dashboard/Files/Settings测试按实际diff加入。
5. 扩展真实Python harness/spec 的上述原生旅程；不为移除的旧Scan兼容重建生产升级fixture。
   控制时钟的单元证明不替代原生生产Worker真实跨短配置间隔观察；不得以旧mtime造稳定。

### Final checkpoint gates

最终 executable candidate 完整满足下列门禁。修正后不复用旧 executable 候选的最终全量结果。

- 根目录：`.venv/bin/python scripts/check_governance.py`、`.venv/bin/ruff format --check .`、
  `.venv/bin/ruff check .`、`.venv/bin/python -m unittest discover -s tests`、
  `.venv/bin/python -m compileall -q mediaflow tests scripts`、`.venv/bin/python -m pip check`。
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` 和
  `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（预期exit1）。
  对照新增依赖和本Task移除清单，搜索所有 Scan 调用及建议动作；逐项说明共享/定义绑定保留理由，
  不要求 `scan` 全仓零匹配。Type C计划/真实结果回归包括在full/native。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run test -- run`、
  `npm run build`、`npm run test:e2e`。共享路由/导航/typed API/readiness涉及全部普通入口。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`；
  `npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts`；
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts`。
  顺序fixture用完整spec；新增独立probe须自包含。若退休案例另放新spec，报告精确命令并执行它。
- production build 实看1536×1024与380×720：九标签、退役旧new/detail链接、内部稳定等待/
  变化重置、同页摘要/确认及Files返回；保留截图/trace、键盘可达和遮挡检查。
- `.venv/bin/python -m pip wheel . --no-deps -w dist`；
  `.venv/bin/python scripts/wheel_smoke_test.py <本候选确切wheel路径>`；
  从安装wheel的site-packages实际验证旧CLI退役拒绝、共享内部发现与摘要/确认消费者。
  不只测试import或“missing item”拒绝，不能在源码目录误导入本地包。
- 扩展既有Docker task-center proof或增加小型退役proof，提供可直接运行的精确命令：
  同一候选 production image 的API/常驻Worker拒绝独立Scan/不支持dispatch，且不依赖手动
  Scan的新来源经过真实稳定观察→同页摘要→确认→实际Worker结果。临时Local/fakeProvider；
  未确认零mutation/零许可、变动来源不就绪、重启不重放，核对实际served assets。
- `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45.4-security`。
  可与上项共用经内容证明的同一image；记录完整imageID和实际源码/served-assets manifest，不用标签/
  打印SHA代替内容证明。不得为适配退役删掉secret/RBAC/非重放断言。Docker不可用如实报告。
- **持久化条件门禁：** 不再要求 Task Base 旧 Scan 库、全状态停止、升级迁移或专用历史矩阵。
  若实际改变共享 schema，使用实际 Task Base 旧代码构建含受影响的普通整理/Result/pin/许可/
  恢复关联的临时库，验证升级、重开、失败回滚和非重放；无 schema 变更则提供实际 diff。
  删除旧 Scan 兼容代码不免除真实共享 schema/持久化风险的验证。
- `git diff --check`；完整Task Base..Head manifest/name-status/stat/diff、冻结文档和私密文件检查。
  所有代码/测试/harness/产物变更必须有匹配的最终T4；文档successor按workflow显式diff后复用。

### B independent verification

B 审查全部实际退役可达路径与共享依赖，检查匹配候选的原始证据。独立使用真实Python/SQLite/
Worker与production build：Scan API/CLI/Job/continue/dispatch均拒绝且未开始发现，无专用历史/
停止/迁移服务；没有手动扫描的新来源等待真实stable-size区间、变化重置、同页摘要精确确认后才执行。
核对原pin/成功/未知兄弟项不回归，实看桌面/窄屏/键盘与旧深链。缺失/不匹配证据才重跑相关门禁，
不因换审查者无理由重复全部Docker/full矩阵；有确定P0/P1可提前拒绝，PASS前满足全部本Task门禁。

### Evidence and preservation

按workflow将source/checkpoint SHA、cwd/命令/runtime/依赖/fixture、时钟/真实等待、Worker/selection/
retry配置、exit/counts/skips/duration、首次失败/复跑、日志/截图/trace、wheel/image/served-asset摘要
保存到 `.git/validation-evidence/<full-source-sha>/<run-id>/INDEX.md` 或CI artifact；/tmp不能是唯一交接。

保留本次开始已有的 `docs/pics/操作与任务.png` 删除意图、两张未跟踪自动化页图、各处`.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/`。不纳入checkpoint，不用reset/restore/clean/stash隐藏。
`config/alist.json` ignored/untracked/unstaged；不打开用户运行DB或生产媒体。证据不进入普通源码提交。

## Non-goals

- 修改 SLICE.md、Roadmap、Progress、稳定需求、CURRENT交付声明；不改变Slice Base/范围或关闭Slice。
- 冻结Slice43的模式退役、页面/定义发布/调度/Run once/统计/全局设置消费；不导入未接受代码。
- 通用DryRun/Rules测试退役、V1整体cutover、删除历史/用户媒体、MediaLibrary Organize、新Provider。
- 旧独立Scan的停止/接管、升级迁移、专用历史读取/取消/导出兼容；FileIndex完整退出和CLI列表
  统一属于本Slice的RO-7，待本Task PASS后另一个连贯Task完成，不属于本Task范围。
- 新队列/Scanner/观察/恢复/执行引擎、扩大有界限制、任意历史Reprocess、自动repin、
  附件-only执行、补偿/回滚引擎、主文件/已完成/不确定effects重放。
- 已验收创建/恢复界面整体重做、额外可选证明或P2清理、Developer规划下一Task或做A最终审查。

## Developer Completion Report

### Checkpoint / Scope

- **Status: READY FOR B REVIEW**；Developer 不自判 PASS、不关闭 Slice、不规划下一 Task，未 push。
- Task Base：`f02443917bcd5b3ef645a32c432b191dc4f12aa3`。
- 最终 executable checkpoint：`cb5ebd834d6532bdc2b6354073d32d3dc6dd0ddd`。
  本报告为其 TASK.md-only successor；完整报告提交 SHA 写入下方证据的
  `report-checkpoint.log`，`report-only.diff`证明无源码/测试/harness/依赖/配置变化。
- 耐久证据：`.git/validation-evidence/cb5ebd834d6532bdc2b6354073d32d3dc6dd0ddd/final-20261018/INDEX.md`。
  精确 cwd/command/exit/count/duration、runtime、manifest、首次失败、trace/截图、wheel/image摘要
  均留存；本地路径不声称远程可达。开发反馈及起始脏文件快照保留于
  `.git/validation-evidence/task45.4-development-20261018/`。

### Changed Files / Implemented

- 完整 Task Base..Head name-status/stat/diff 见证据；A 已提交的范围文档单列归属，不算 Developer
  实现。本轮未修改 SLICE/Roadmap/Progress/稳定需求/CURRENT；原有用户图像删除、未跟踪图像、
  .DS_Store/zip/旧浏览器输出均保留且未纳入提交；私密 alist 仍 ignored/untracked/unstaged。
- Application/API/CLI/Worker：独立 Scan submit、所有 aliases、旧详情/取消入口、通用 Job(scan)、
  forged-definition dispatch、retry/resume/continue 明确退役拒绝；拒绝在配置/Provider/Storage发现
  前完成，不创建新 Task/观察/许可，不暗转 Organize，保留 RBAC。CLI 旧 flags 仅返回薄拒绝。
- 删除独立 ManualScan runner/domain/repository/history/cancel/UI 装配；只留有界错误类型与退役
  说明。V1/V2 创建/执行动作删除，旧new/detail链接认证后指向新建整理与任务中心，不回放旧scope。
  readiness/action matrix 不再广告可执行Scan；其他任务历史/结果/导出与控制保持。
- 复用未改动的 MediaDiscovery Worker/过滤/真实稳定性观察：fresh目录/单项/多项无预扫描即可
  等待真实区间、源变化重置、同页摘要并精确子集确认后才由真实 Worker 执行。旧mtime不是观察。
  修正可达恢复指引，不要求不可能的独立Scan；不新增队列/观察/恢复引擎或索引补偿服务。
- 定义Preview复用同pin/同definition内的持久来源观察；变化重置、新pin不能借旧区间，Provider
  DTO/秘密/指纹不泄露。冻结定义绑定Automation模式/发布/调度保留；C→NamingA/ClassA仍是C。
- 通用历史/取消/pin等原Scan fixtures迁为受支持Preview，保留原安全断言；更新真实Python/
  Docker/release-security夹具。新增退役反例、fresh观察/变更/pin和原生完整链测试。

### Tests And Results — Final T4

以下全部来自上述最终 executable SHA 的完整历史隔离clone，不读用户ignored运行库。
修正后的全部门禁重新执行，没有用旧候选最终全量结果代替。

| 门禁 | 实际结果 |
|---|---|
| Python full unittest discover | **PASS 2500 tests /249.410s /7 skipped** |
| governance、ruff format/check、compileall、pip check | **PASS** |
| 两个批准example config validate、禁止FFprobe/FFmpeg搜索 | **PASS**；搜索无匹配预期exit1 |
| Web typecheck/lint/format/build | **PASS** |
| Vitest full | **PASS 76 files /1112 tests** |
| Fake浏览器全量 | **PASS 240**，workers1/retries0/trace on |
| 完整真实Python inventory spec | **PASS 38**，精确剩余scope/稳定性/确认/真实Worker/重连非重放 |
| Unicode principal / 九视图及创建visual spec | **PASS 1 /2**；实际查看桌面1536×1024/380×720截图 |
| wheel build / wheel_smoke_test | **PASS**；清除PYTHONPATH，真正安装而非源码误导入 |
| 安装wheel消费者 | **PASS 29**；site-packages实际CLI退役、内部观察/摘要/确认/Worker |
| production Docker退役/真实稳定性/同页确认/Worker/restart | **PASS**；无确认零许可/零变更，变化重置 |
| Docker release-security完整门禁 | **PASS**；secret/RBAC/权限/非重放等原断言保留 |
| 完整manifest、冻结文档、私密文件、git diff --check | **PASS** |

- 7个 **SKIP而非PASS**：独立真实OpenList/SMB/S3验收环境3项、Local/SMB/OpenList/S3 endurance
  隔离profile4项未提供；精确名称/原因见 `skip-reasons.log`。未新增skip/重试或削弱断言。
  raw日志中的 ResourceWarning 保留，未掩盖或自行认定既有豁免。
- wheel SHA256：`2dd97025ce001ddf0bd300ad62e925c3ad4221840ebebd6ef3289d19d0e65beb`；
  162 Python模块逐字节匹配候选。最终release-security重建的实际imageID：
  `sha256:6a0a857e83fd41d514b5ec32b7449a637814bd78b3610570cec974bf883327f5`。
  重建后再次完整运行production proof，核对162 Python/4 Web文件与实际served assets字节摘要。
- shared schema条件门禁：60个共享CREATE TABLE语句不变，schema47不变；仅移除两个Scan专用
  fresh CREATE，不新增DROP/delete/ALTER/迁移。实际diff与shared-schema-comparison.json留证；
  fresh/reopen共享pin、全量既有迁移与wheel backup/rehearsal通过，不建设旧Scan迁移矩阵。
- 开发期首败均保留：无.git归档环境、Preview夹具scope/Provider/识别、fake旧Scan预期、Colima
  临时挂载、wheel PYTHONPATH污染、release夹具构造无关OpenList、退役链接视觉对比度；逐项定位
  修正后先跑受影响用例，最终候选完整T4。未把产品失败标为既有或自行豁免。

### Decisions / Risks / Remaining Work

- 完整FileIndex退出和CLI/两种库页实时列表统一是 **RO-7待后续B规划**；本Task不交付它，
  不因此宣称Slice全部Outcome完成。共享Scanner/enum/定义绑定Scan与有限历史标签保留原因见索引。
- 无数据库清空/媒体删除；只在隔离Local fixtures执行显式确认操作，生产路径仍仅OrganizerExecutor
  变更媒体。定义/普通pin、未知效果非重放、权限及源范围不降级。
- 已实际审阅九视图、旧new/detail、稳定等待、同页摘要与确认、键盘/窄屏/返回证据；长摘要需要
  纵向滚动但没有页面横向溢出。现存部分共享英文指引保持，不进行范围外整页重做。
- 可复用经验：容器exec不继承entrypoint加载的秘密环境；测试fixture仅构造所需Local适配器，
  不因无关Provider/Storage造成假失败。wheel消费者清除PYTHONPATH并断言site-packages真实来源。


## B Review Result

```text
Contract Recheck: 0237b7d366bd24e9182797a72cb4939b528602ba
Scope Decision: TASK45.4 CONTINUES; RO-7 IS NEXT AFTER PASS
Implementation Reviewed: NOT REVIEWED
Implementation Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: DEVELOPER CONTINUES TASK45.4; B PLANS RO-7 AFTER PASS
```

Task45.3 PASS记录见上方；本节只属于新Task45.4，不是其预先验收或Slice最终结论。
