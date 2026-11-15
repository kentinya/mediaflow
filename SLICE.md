# Slice 55 — V1 与迁移残留完全退役

```text
Slice ID: 55
Name: Complete V1 and Migration Residue Retirement
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 2b2e7c1824fa5681864455714d0f97b26555c7dc
Implementation Head: NOT SET
Working Branch: main
Development Authorization: TASK55.1 IMPLEMENTATION AUTHORIZED
Risk: High
Accepted Test Level: T4
Next Action: DEVELOPER STARTS TASK55.1 IMPLEMENTATION
```

## Authority and baseline

用户先要求调查 V1 遗留，明确“V1版本的完全彻底的退役不做兼容，也不隐藏”，随后限定
“先调查不改文档和代码”，并补充调查迁移残留。两轮只读调查后，用户现要求“规划一个Slice”。
本合同统一规划 V1 产品及早期 V2 迁移兼容的完整退出。用户现要求“激活Slice并代替B规划
第一个Task”，据此激活本 Slice，并授权 A 代 B 规划首个 Task 及提交本地检查点。角色
例外仅限首个 Task 规划；后续 Developer 实施、B 独立验收和 A 终审继续按工作流进行。
用户随后要求“激活Task”，据此将已规划的 Task55.1 激活为正式实施 Task，按其原有范围执行。
用户补充要求保留稳定 V2 的正式配置键／权限名及现有有效数据；本合同据此取消无关改名，
将现有 V2 配置、合法任务、结果及原 pins 的继续使用列为必需结果。
生命周期、测试分工及 Git 规则只以 [Development Workflow](docs/development-workflow.md) 为准。

规划前治理检查 PASS。仓库 `/Users/songzhidong/mediaflow`，分支 main，HEAD 为上述 Base，
暂存／工作区干净，文档与 Git 可写；没有读取私有配置、运行数据库、秘密或用户媒体。
Base 是本 Slice 产品实施前的真实检查点；规划／激活文档提交不重设 Base。如实施前出现
介入产品变更，A 需先核对合法集成与范围，不静默换基线。

Slice54 的 PASS / CLOSED、原 Base `e43a40674eb14aa12615a440a348fe675cd50c4e`、已接受实现
`aef044e51dc91655372bf5fe39c6116da976c3b4`、角色例外及验证限制保留于
[规划前固定合同](https://github.com/kentinya/mediaflow/blob/2b2e7c1824fa5681864455714d0f97b26555c7dc/SLICE.md)
和 [Progress](docs/progress.md)。独立修复 PATCH-20261115-1 已由 B PASS，固定报告见
[Task 接受检查点](https://github.com/kentinya/mediaflow/blob/8c09f276409be2cf969ccd8d037bf083312c2d32/TASK.md#patch-20261115-1--b-pass)。
本 Slice 不重开旧验收，不删除 Git 历史、release/v1、标签或 docs/history，不建设 V1／
已废弃版本的通用迁移工具。

## User outcome and completion meaning

本合同的“旧／迁移／兼容”退出对象仅指 V1 或已废弃迁移的专属用途；当前正式 V2 契约、
有效数据与继续使用所需的读取按当前职责保留，命名或实现年代不作为删除依据。

用户安装本 Slice 产物后，只使用当前 V2 完成首次设置、配置／规则管理、实时库浏览、
手工整理、自动化、任务内四类恢复、普通文件维护和通知。源代码、安装包、镜像和新库中
均无 V1 或早期迁移兼容产品。旧入口、旧字段、旧事件、旧会话、旧执行记录不被自动
转换、接管或重新解释，也没有隐藏开关、备用执行器、别名、跳转或专用退休说明页。

支持范围包括首次初始化，以及本 Slice Base 已接受的稳定 V2 数据继续使用：现有 Storage、
两种库、规则、设置、自动化／通知定义、Draft／Active、合法任务／请求／结果／审计和原 pins
在本 Slice 产物中继续有效。当前业务行为、正式接口／配置契约及目标路径语义保持；
不要求重新初始化、重建配置或重新发起已准入工作，不改写原 digest，不重放完成／未知效果。
新工作和保留的 V2 工作均支持同版本重开／重启后的读取与安全恢复。仅属 V1／废弃迁移
形态的数据不提供转换或接管；未配置／损坏／本来不支持的输入仍有准确状态和安全下一步。

V2 共用的 Python 应用、Storage／Provider 分层、零变更分析、RBAC、精确计划／授权、
Task 调度、结果／审计和同版本非重放继续完整。`/api/v1/*` 是当前 API 版本，`/ui-v2/*`
是当前 Web 根；保留二者作为唯一当前命名，不建设第二套 API 或全站改地址工程。

## Requirement and journey mapping

TARGET 稳定范围见 [V2-RETIRE-001–010](docs/v2-requirements.md#target--complete-v1-and-migration-residue-retirement-slice55-active)，
[目标旅程](docs/product-experience.md#target--complete-v1-and-migration-residue-retirement-slice55-active) 与
[目标架构](docs/architecture.md#target--complete-v1-and-migration-residue-retirement-slice55-active)。
当前合同尚未实现；下列修订只在本 Slice 验收后成为 CURRENT：

| 被修订的当前边界 | 本 Slice 目标 | 保留的义务 |
|---|---|---|
| V2-MIG-001/002、REQ-WEB-001/004、V1 /ui 共存／回退 | 仅当前 V2；退出 V1 专用入口及迁移承接 | 原生完整旅程、共享后端与 RBAC，不新建身份系统 |
| REQ-SCHED-003/006–007、REQ-SAFE-008 的旧实现；V2-AUTO-003/010/011 | 删除旧 schedules、远程票据和独立 grant 产品 | 当前定义 Enabled／Run once 意图、权限／作用域／逐效果核对 |
| REQ-CONFIG-*、V2-CONFIG-001–004、V2-RULES-005 | 只接受唯一当前配置，取消旧格式与分类转换 | Draft／精确 Active、typed Save、检查／原子发布、无默认业务注入 |
| V2-TASK-003–007/011–014、V2-OPS-007/008/011/013/016/017 | 清除暂停、旧恢复链、非内核整理执行和历史输入兼容 | 五态 flow、逐项结果、同 Task 四类恢复、取消及不确定非重放 |
| V2-AUTO-001/007/008、V2-UX-* 的迁移地址／会话义务 | 无旧地址与纯迁移格式承接 | 当前正式配置键／权限名、深链、现有 V2 数据／原请求核对和真实消费者采用 |

未明确修订的 REQ-STO/PARSE/REC/META/NAME/CLASS/ORG/ATT、REQ-SAFE-* 和当前原生
旅程继续适用；RecognitionType C 复用 A Naming／Classification 后仍为 C。

## Investigation facts and coverage boundary

Base 源码调查证明 /ui 四项静态资源实际返回 200；其内嵌文件 3910 行，至少 19 个 Python
测试文件直接引用旧 UI。CLI help 仍注册 execution-authorizations、旧 scheduler 查询和
upgrade。旧 schedules 与远程票据已接入统一 Task，但入口／专用表尚在；旧 grant 授予／
撤销 API 也仍注册。七条旧 V2 路由、自动化 settings 跳转、历史状态／事件别名、非内核
领取、旧恢复链、会话兼容及初始化迁移逻辑均存在。运行库已拒绝 schema <58，仍有历史
补列／重建；部分当前建表依赖 migrate helper，不能直接删整段。

这些是源码及无数据库入口探测事实，不等于当前部署身份、浏览器验收或产品门禁通过。
清单为必需下限；B 必须根据完整调用／注册／持久化依赖核对同类残留，不能因某项没有
单独写函数名而留兼容入口。真实当前业务用途迁到唯一当前契约，纯兼容部分完整删除。

## Required Outcomes and surfaces

### RO-1 — 只有当前 Web 入口，没有迁移承接

删除 operator_ui.py 及服务注入／CSP 专用差异／静态资源、/review 迁移页、v1Path／migration
模型及其文案。退出旧 /library、/library/files、/operations/tasks[/:id]、/operations/jobs[/:id]、
/operations/automation/new，取消 tab=settings 的专用跳转、旧筛选／书签转换及已退役
definition/editor/execution/new-organize 等残余接线；不得另设重定向、别名或“已迁移”页面。
当前自动化新建入口为 /operations/automation/lifecycle；保留当前编辑、规则对象 Edit、
Task Center run＋hosted-card、通知／两种库等真实现行深链，不把当前地址因出现“旧”注释删除。

旧 Web 使用普通未知路由／认证边界；前端 SPA 返回通用入口文档时，必须证明 Router 未注册
旧页并实际呈现通用 not-found，不能仅凭 HTTP 200／非200 判定。当前九页导航、刷新／
重认证、弹窗关闭与原来源返回可用，无返回 V1、旧壳或兼容入口。

### RO-2 — 只有当前业务受理与执行，没有旧调度／票据／grant／全局恢复入口

删除 automation.schedules 的 IntervalSchedule／CronSchedule 产品、到期／执行分支、
/api/v1/schedules 与旧 scheduler list／audit 等专属查询。Scheduler run／必要当前检查
继续服务当前 Automation 定义；Cron／间隔算法保留，不构造替代旧调度列表。
删除 execution-authorizations CLI、X-MediaFlow-Execution-Token 受理、远程票据 POST
/api/v1/tasks、api.remoteExecution 设置及专用服务／模型／权限／持久化。
删除独立 unattended grant 的查询／授予／撤销／别名／审计 API、模型及当前定义管理里的
旧 grant 读取／撤销耦合；当前 Enabled 发布证据与真实执行权限检查由当前权威承担。

退出仅为 V1 存在的全局 recognition/metadata/classification/conflict 队列、manual-* 别名和
独立授权分步入口、旧恢复 API／批次／Pause/resume／remaining-scope 等专用 409/410
退休处理与枚举广告。当前 API／CLI 需要的审核、分析、精确摘要、执行及日志／系统／审计／
导出使用唯一当前行为；按真实调用拆开旧传输表面和共享应用服务。删除旧 Task／Worker
返回格式分支，不保留旧字段投影；当前直接 /tasks 恢复／取消请求按当前契约保留。

所有新整理与合法续作由 Task 内核受理／claim／fence；删除常驻 Worker 的非内核 discovery／
manual execution 轮询、领取、无调度记录回落和专用旧恢复执行。共享 discovery／execution
服务继续供 Task Worker 调用；普通 Copy／Move／Delete 的现有独立职责不被改成整理队列。

### RO-3 — 唯一严格的当前配置与领域契约

部署只通过最小 bootstrap 定位当前库和 api.principals；去掉完整 JSON 直接业务运行权威、
api.tokenEnv→legacy-admin、单 bearer 构造器管理员回落、开发默认策略／部分文档补业务对象。
保留当前规范文档的 Draft 导入／校验／激活、设置 JSON 查看／脱敏包导出及恢复，不因退出
JSON_BOOTSTRAP 而删除当前 V2 高级配置能力。只读／导航不能建草稿或工作。

下列退出清单针对仅属 V1／废弃迁移的输入；现有稳定 V2 正式契约、有效配置和合法 pins
有当前业务用途的字段／值继续按原语义使用，不能凭名称年代或出现在旧文档中判为废弃。
此约束同样适用于 RO-2 的接口／持久化、RO-4 的状态／结构和 RO-5 的响应／session 清理。
纯迁移旧写法拒绝，不做优先级合并、规范化转换或静默忽略：Storage 顶层连接参数、资源库 rootPath
显示别名、automation.taskDefinitions、notifications.webhooks、分类 library 与 category/subcategory
代 path、MetadataPolicy.mediaType、OrganizePolicy.overwrite、staleJobAgeSeconds，以及同类旧
命名模板／模式／事件／包结构别名。根级 automationTaskDefinitions／webhooks、Storage.options、
资源库 displayRootPath、分类 mediaLibraryId＋path、mediaQueryType／conflictStrategy 为当前
唯一表达。Storage.rootPath／MediaLibrary.rootPath、候选自身 movie/TV 类型和分类条件
mediaType 有当前职责，不能按字段同名删除。迁移专用分类转换 UI／入口退出；现有正常 V2
规则及 pin 的目标路径保持原意，不得删前缀、改目录或失效来满足退役。其必需读取属于
当前领域职责，不能作为 V1 残留一并删掉。

当前正式容量键 automation.maximumActiveJobs 和取消权限 CANCEL_JOB／cancel_job 保持。
它们的现有名称就是当前 V2 契约，本 Slice 不改名、不新增替代键／权限或别名。三项设置的
容量 1–10000、全入口原子额度、Worker／Scheduler 采用与 override 规则不变，不新增
参数／设置平台。当前 /api/v1 与 /ui-v2 命名保持。
删除 job.*→task.* 事件兼容，事件仅 task.* 与当前 schedule.emitted；调度发布权限能力保持。
兼容导出名／Phase bootstrap 类／旧 Task/ScanTask 模型／strategy-test 旧 console runner
及默认策略接线退出；纯分析、解析、规则测试等现行引擎由当前模型／检查入口使用。

### RO-4 — 当前 schema 与五态 Task，彻底清除旧迁移及历史执行形态

新建库直接完整创建当前 runtime／configuration／managed-document 必需结构，包括列／索引／
Task 调度／首次执行证据。清除仅服务已废弃版本的补列／重建／回填、旧 lock-owner 和
upgrade check/rehearse 等通用旧版本工具及专用脚本。

现有稳定 V2 库继续使用，不能以“旧库”、重设 schema 身份或删除迁移代码为由拒绝启动、
要求新建实例、丢弃配置／历史或让合法任务失效。确需结构收敛时，仅做本 Slice 必需的
最小调整，完整保留有效业务数据、ID／关系、快照 digest／pin、原状态／结果／效果和当前
任务继续运行的条件，具有失败原子性；不建设通用旧版本迁移／接管系统。

原本不支持的 V1／废弃格式库、畸形或不支持的混合库，在修改或业务执行前准确拒绝且
保留原文件。当前 V2 的正常使用流程保持原入口；错误说明实际阶段、已知耐久状态和
适用下一步。不自动清库／重建、重置 Active、重命名媒体或重新准入已存在的任务。

新库没有旧 schedules、execution tickets、independent grants、旧恢复子 Task／批次／scope
链的专用表／索引／列；现有 V2 库的清理以保留有效业务记录为前提，不为删除残留表／列
而自动删除历史。清除纯兼容查询关系，当前 checkpoint／统计／来源历史／证据导出继续完整。
保持同一 Task 内合法版本化 item／attempt／请求／结果与当前恢复关系，不新造替代迁移链。
Task flow 仅 pending/running/completed/failed/cancelled；清除历史 paused/partial_success flow
解析、Pause 控制、队列暂停／恢复、pause_requested 及生产者／reader／测试，文件级 partial／
主附件结果、human/stability waiting、真实未结束工作及取消语义保持独立。

### RO-5 — 前后端只消费当前数据，当前未知结果恢复仍安全

删除旧 Run once／Copy 编辑页 session 格式读取／合并／标志、旧设置缺 baseline 格式适配、
规则旧 key 迁移清理、旧协议 action／统计／Storage 列表／模式／可选字段回落，以及已无
当前生产者的 continuation 卡／请求函数／批量模型。清理已不存在类的注释、未用导出／导入
别名、假服务旧分支及夹具，不以隐藏 UI 保留可触发行为。

当前 session 格式有明确身份，纯迁移形状普通拒绝且不转换；现有稳定 V2 的有效输入和
未知提交上下文继续可核对，不能因来自 Slice Base 就作废。读取 session 不成为新命令意图。
同版本未知 Save／Execute／Run once／Copy／通知恢复保留原请求核对和防重复提交；规则／
设置／通知当前未保存输入与权限隔离、焦点／返回不回退。不能通过删掉所有会话记录或
把 unknown 当失败可重试来实现退役。未知／缺失来源证据的保守拒绝、脱敏、无 fingerprint
Storage 的现有合法行为仍是当前安全职责，不当成迁移回落删除。

### RO-6 — 源码、测试、包、镜像、示例和当前说明一致

移除旧正向支持测试、兼容升级脚本／假服务／fixture 和产物清单要求；保留、改接真实当前
V2 安全／功能断言，并新增退休不存在和当前旅程的真实证据。示例配置、部署生成器、四服务
Compose、健康／安全／重启 smoke、wheel／源码外安装不再生成、包含或要求旧机制。
只保留当前 bootstrap 和当前规范配置样例；替换旧文件引用需在同一结果内更新 CI／命令。

当前 README／配置／部署／发布／Requirements／旅程／架构准确说明唯一支持边界；原始
REQ/UX/V2 ID、历史关闭事实及 docs/history 保留。不能把残留移到新 archive、动态导入、
环境开关或 no-op 服务。全仓关键词搜索只是证据一部分，不要求删除合法历史文档或否定测试
中的单词；每个当前源码残留需证明真实职责或完成删除，不能用改名掩盖同一兼容行为。

## Safety invariants and explicit deferrals

- 当前原生完整旅程和失败／恢复保持；不以曾属于 V1 为由删除当前设置、审核服务、分析、
  计划、日志、结果导出、通知或全部 CLI。仅为当前调用收敛所必需的请求／投影调整在范围内。
- 认证、后端 RBAC、部署权限、精确 Active／原子发布／引用保护／审计、source ownership、
  claim/lease/fence、已完成／不确定非重放、唯一 OrganizerExecutor 及 C→A 身份不变量保持。
- Base 已接受的稳定 V2 正式契约、有效数据和合法工作是保留基线；相对当前 Active 的原
  pins、版本／ID、历史及效果保持原样。仅废弃 V1／迁移形态无接管承诺；不能从当前 Active、
  名称、时间或缺失字段猜授权。配置键／权限名的无关改名不在范围内。
- 不新增 API v2、改 Web 根、身份／OIDC／Secret Store、Provider／Storage、命名算法、恢复
  类型、跨 Task 批量、MediaLibrary 整理、上传下载、分布式队列、并行度／超时监督或回滚。
- 不重设计当前九页、Task 详情或改变 flow／文件结果／自动化成功率；删除迁移卡和无生产者
  分支所必需的布局修正需可读、键盘／窄屏可用，当前规则 Edit 深链仍是正式当前入口。
- 不操作用户数据、停止／迁移现有部署、发布／推送、删除 release/v1／tag 或 Git 历史。
  不建设 V1／废弃迁移形态导入、暂停恢复、旧请求接管、历史事件重投或专用旧会话界面。
  现有稳定 V2 数据继续使用所必需的读取和最小结构调整属于本 Slice 的保留职责。

## Acceptance Criteria

- [ ] AC-01 / RO-1：所有指定旧 Web 入口注销；带查询、直达／刷新／重连均使用普通 not-found／
      auth，无遮蔽开关、V1 资源、跳转、说明壳或旧地址到当前意图的自动转换。
- [ ] AC-02 / RO-2：正常当前配置／合法权限下，旧 API 为通用 unknown route；旧 CLI 从 help／
      parser 注销。不能用401/403、无配置503或非零退出冒充删除；无额外工作／Provider／
      Storage 效果，正常解析／认证／脱敏审计允许。无旧票据、调度、grant 专用读写／接线。
- [ ] AC-03 / RO-3：当前正式 bootstrap／配置／接口／权限契约保持；maximumActiveJobs 和
      CANCEL_JOB/cancel_job 无改名／替代键。纯 V1／迁移输入单独、混合、旧包导入和任意
      JSON 路径拒绝，零发布／Task／媒体效果；现有正常 V2 配置和合法 pins 仍有效。
- [ ] AC-04 / RO-2/4：新手工／due／Run once 和四类恢复只走同 Task 内核，保留人等／稳定等、
      原子额度、源归属和并发fence；无非内核整理领取、旧子 Task 链、Pause／resume 实现。
- [ ] AC-05 / RO-4：新库完整结构；用 Base 真实代码在隔离环境建立正常 V2 配置／任务／结果
      后，由候选继续打开使用，保留 IDs／关系、Draft／Active／digest／pins、状态／独立效果、
      审计和未知请求核对，不要求重建配置或重发任务。同版本 reopen／restart／备份及明确
      非覆盖 restore 通过；必要结构调整失败原子、有效业务记录不丢。原本不支持／畸形库
      拒绝前后文件／schema／行不变，无自动清库／重建／claim 或媒体效果。
- [ ] AC-06 / RO-4/5：Task 五态、文件 partial／unknown／缺 Result、取消与真实未完成各自准确；
      纯废弃 flow／命令／事件／session／响应形状无兼容转换或执行资格；现有稳定 V2 的
      有效数据／请求／正式响应保持原业务语义和安全恢复。
- [ ] AC-07 / RO-5：新格式输入与同版本 unknown 写入跨关闭／刷新／重新认证／双管理员并发
      保留准确请求与核对；迟到读取／写响应不串身份／版本／兄弟项，不自动重提或假失败。
- [ ] AC-08 / RO-1/3/6：从无媒体挂载的四服务空实例，经 V2 首次 Draft／空 Active、typed
      Storage／两种库／七类规则、设置高级草稿检查与激活、自动化及通知配置完成；无 V1／
      手写整份业务 JSON／旧 runner 回退，C 使用 A 命名分类仍为 C。
- [ ] AC-09 / RO-2/4/5：真实 Files 单项／批量／有界文件夹 → per-file 决策 → 精确选中摘要
      → 显式确认 → 同 Task，及 due／禁用定义 Run once → 四类问题 → 同 Task 续作通过。
      各项／附件独立，成功和不确定效果不重放，当前来源失败历史门禁／自动化统计保持。
- [ ] AC-10 / RO-2/6：两种库普通维护／异步 Copy/Move/Delete、当前页耐久结果／恢复、通知
      投递／死信恢复、权限变化、满额、坏 Active／pin、丢响应均保持实际安全边界和下一步。
- [ ] AC-11 / RO-6：新构建浏览器、wheel／源码外安装和候选 Docker 四服务镜像证明无旧
      产物／入口；当前安全头、健康、无 Active 常驻、设置采用和重启恢复保持。桌面／390px／
      矮窗口检查移除迁移内容后的可读／键盘／返回，不要求全站重设计。
- [ ] AC-12 / RO-6：源／注册／schema／消费者反向清单、CI／示例／脚本／当前说明完整；
      无把旧断言直接删弱的通过。全部 Required Outcomes 和安全／原生／包门禁有精确候选
      实证，未执行项不记为 PASS；无旧版兼容例外待补而声称“完全退役”。

## Validation ownership and final validation

风险 High，产品实施与最终验收 T4。首个 Task55.1 已由 A 按用户授权代 B 规划，见
[TASK.md](TASK.md)。后续 B 按完整行为规划连贯 Task、实际 Base、Difficulty／Test Level
与精确 affected／acceptance 命令；本文件不预建后续 Task 或执行步骤配额。
Developer 仅跑新增／修改／直接受影响测试及必要当前原生链路，按工作流交不可变检查点；
B 独立完成每 Task 必需验收、[shared full gates](docs/development-workflow.md#shared-full-regression-commands)
和最终全部 RO 门禁；A 独立审查整个 Base..Implementation Head，不自审通过。

最终必须提供：退休入口注册与正常输入反证；纯废弃格式拒绝；新库完整结构／Base 稳定 V2
数据由候选继续使用／必要调整失败原子／原本不支持库零变更／同版本复开；真实
Python/API/SQLite/常驻 Worker+Scheduler+Notification 的上述旅程、
并发／丢响应／权限／pin／不确定故障；当前前端构建与截图；干净来源 wheel／安装目录／
候选 Docker 镜像身份、四服务空初始化及安全／restart proofs。外部 SMB/OpenList/S3/TMDB
用 fake／本地服务器与临时根，既有可选真实外部测试需披露，不拿用户媒体作证明。
证据存稳定忽略目录或 CI；已删除的旧测试／脚本必须逐项对应退出义务或保留的当前断言。

本次规划只检查文档一致性／链接、治理及受影响文档测试和 whitespace；不把这些结果
当作产品 T4、已退役或 Slice PASS。实际规划命令／结果在本地检查点交接中报告。

## Closure Packet and A Final Review

尚未实施，Implementation Head NOT SET。Required Outcomes／最终测试／Closure Packet／
A Final Review 均未完成；Status 为 ACTIVE。Task55.1 已获实施授权，下一步由 Developer
按正式 Task 实施。
历史接受事实不被本规划替代；通过后再统一将 TARGET 协调为 CURRENT，不提前声明退役。
