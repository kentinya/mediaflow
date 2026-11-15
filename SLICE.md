# Slice 55 — V1 与迁移残留完全退役

```text
Slice ID: 55
Name: Complete V1 and Migration Residue Retirement
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: 2b2e7c1824fa5681864455714d0f97b26555c7dc
Implementation Head: NOT SET
Working Branch: main
Development Authorization: PLANNING ONLY — IMPLEMENTATION NOT AUTHORIZED
Risk: High
Accepted Test Level: T4
Next Action: USER ACTIVATES SLICE; B THEN PLANS THE FIRST TASK
```

## Authority and baseline

用户先要求调查 V1 遗留，明确“V1版本的完全彻底的退役不做兼容，也不隐藏”，随后限定
“先调查不改文档和代码”，并补充调查迁移残留。两轮只读调查后，用户现要求“规划一个Slice”。
本合同统一规划 V1 产品及早期 V2 迁移兼容的完整退出；仅授权文档规划与本地检查点，
不激活、不实施、不规划 B Task、不分派代理、不推送、不部署。
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
本 Slice 不重开旧验收，不删除 Git 历史、release/v1、标签或 docs/history，不建设旧版本迁移。

## User outcome and completion meaning

用户安装本 Slice 产物后，只使用当前 V2 完成首次设置、配置／规则管理、实时库浏览、
手工整理、自动化、任务内四类恢复、普通文件维护和通知。源代码、安装包、镜像和新库中
均无 V1 或早期迁移兼容产品。旧入口、旧字段、旧事件、旧会话、旧执行记录不被自动
转换、接管或重新解释，也没有隐藏开关、备用执行器、别名、跳转或专用退休说明页。

支持范围为本 Slice 新规范的首次初始化 → 新工作 → 同版本重开／重启 → 原工作读取及
安全恢复。先前 V1／V2 数据库、配置包、工作 pin 或浏览器记录不获兼容承诺；不迁移、
不导入旧任务、不改写旧 digest，不自动清库／替换／修复存量数据。当前规范输入与真正
未配置／损坏／不支持输入各自有准确状态和安全下一步。

V2 共用的 Python 应用、Storage／Provider 分层、零变更分析、RBAC、精确计划／授权、
Task 调度、结果／审计和同版本非重放继续完整。`/api/v1/*` 是当前 API 版本，`/ui-v2/*`
是当前 Web 根；保留二者作为唯一当前命名，不建设第二套 API 或全站改地址工程。

## Requirement and journey mapping

TARGET 稳定范围见 [V2-RETIRE-001–010](docs/v2-requirements.md#target--complete-v1-and-migration-residue-retirement-slice55-planned)，
[目标旅程](docs/product-experience.md#target--complete-v1-and-migration-residue-retirement-slice55-planned) 与
[目标架构](docs/architecture.md#target--complete-v1-and-migration-residue-retirement-slice55-planned)。
当前合同尚未实现；下列修订只在本 Slice 验收后成为 CURRENT：

| 被修订的当前边界 | 本 Slice 目标 | 保留的义务 |
|---|---|---|
| V2-MIG-001/002、REQ-WEB-001/004、V1 /ui 共存／回退 | 仅当前 V2；退出 V1 专用入口及迁移承接 | 原生完整旅程、共享后端与 RBAC，不新建身份系统 |
| REQ-SCHED-003/006–007、REQ-SAFE-008 的旧实现；V2-AUTO-003/010/011 | 删除旧 schedules、远程票据和独立 grant 产品 | 当前定义 Enabled／Run once 意图、权限／作用域／逐效果核对 |
| REQ-CONFIG-*、V2-CONFIG-001–004、V2-RULES-005 | 只接受唯一当前配置，取消旧格式与分类转换 | Draft／精确 Active、typed Save、检查／原子发布、无默认业务注入 |
| V2-TASK-003–007/011–014、V2-OPS-007/008/011/013/016/017 | 清除暂停、旧恢复链、非内核整理执行和历史输入兼容 | 五态 flow、逐项结果、同 Task 四类恢复、取消及不确定非重放 |
| V2-AUTO-001/007/008、V2-UX-* 的迁移地址／会话义务 | 无旧地址与旧会话格式承接；采用当前 Task 用语 | 当前深链、请求核对、同版本输入保留、真实消费者采用 |

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

旧写法拒绝，不做优先级合并、规范化转换或静默忽略：Storage 顶层连接参数、资源库 rootPath
显示别名、automation.taskDefinitions、notifications.webhooks、分类 library 与 category/subcategory
代 path、MetadataPolicy.mediaType、OrganizePolicy.overwrite、staleJobAgeSeconds，以及同类旧
命名模板／模式／事件／包结构别名。根级 automationTaskDefinitions／webhooks、Storage.options、
资源库 displayRootPath、分类 mediaLibraryId＋path、mediaQueryType／conflictStrategy 为当前
唯一表达。Storage.rootPath／MediaLibrary.rootPath、候选自身 movie/TV 类型和分类条件
mediaType 有当前职责，不能按字段同名删除。旧分类转换 UI 与运行时旧前缀分支一起退出。

Task 容量唯一键改为 automation.maximumActiveTasks；取消权限唯一名为 CANCEL_TASK／
cancel_task，旧 maximumActiveJobs／CANCEL_JOB／cancel_job 不作别名接受。仅规范当前
Task 用语，三项设置的容量 1–10000、全入口原子额度、Worker／Scheduler 采用与 override
规则不变，不新增参数／设置平台。当前 /api/v1 与 /ui-v2 命名保持。
删除 job.*→task.* 事件兼容，事件仅 task.* 与当前 schedule.emitted；调度发布权限能力保持。
兼容导出名／Phase bootstrap 类／旧 Task/ScanTask 模型／strategy-test 旧 console runner
及默认策略接线退出；纯分析、解析、规则测试等现行引擎由当前模型／检查入口使用。

### RO-4 — 当前 schema 与五态 Task，彻底清除旧迁移及历史执行形态

建立完整、唯一的当前 runtime／configuration／managed-document 支持身份和新建结构；
当前必需列／索引／Task 调度／首次执行证据直接完整初始化，不靠历史补列／表重建顺带创建。
删除旧 schema ALTER／回填／migrate55 等重建、旧 lock-owner、跨版本接管／转换和 upgrade
check/rehearse 工具及专用脚本。新规范身份在实施时统一更新；不固定要求某个数字。

旧／畸形／混合版本的既有库在任何 DDL、版本标记写入、回填、claim 或业务执行前拒绝，
保留原文件与数据；必要只读格式检查不是兼容读取。明确告知不支持的阶段、未执行的业务
和使用独立新实例的下一步；没有自动重建、导入旧任务、指针改写、删表／清库或 media 操作。
不以加上新版本号但继续接受旧字段／旧工作实现退出。

新库没有旧 schedules、execution tickets、independent grants、旧恢复子 Task／批次／scope
链的专用表／索引／列；清除它们在查询、checkpoint、统计、来源历史、证据导出中的兼容关系。
保持同一 Task 内合法版本化 item／attempt／请求／结果与当前恢复关系，不新造替代迁移链。
Task flow 仅 pending/running/completed/failed/cancelled；清除历史 paused/partial_success flow
解析、Pause 控制、队列暂停／恢复、pause_requested 及生产者／reader／测试，文件级 partial／
主附件结果、human/stability waiting、真实未结束工作及取消语义保持独立。

### RO-5 — 前后端只消费当前数据，当前未知结果恢复仍安全

删除旧 Run once／Copy 编辑页 session 格式读取／合并／标志、旧设置缺 baseline 格式适配、
规则旧 key 迁移清理、旧协议 action／统计／Storage 列表／模式／可选字段回落，以及已无
当前生产者的 continuation 卡／请求函数／批量模型。清理已不存在类的注释、未用导出／导入
别名、假服务旧分支及夹具，不以隐藏 UI 保留可触发行为。

当前 session 格式有明确身份，旧形状普通拒绝且不转换；读取旧 session 不成为新命令意图。
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
- 新规范下合法旧 pin（相对当前 Active 而言）和同版本历史保持原样；跨旧版本数据不获转换
  承诺，但永不改写／删除原文件。不能从当前 Active、名称、时间或缺失字段猜授权。
- 不新增 API v2、改 Web 根、身份／OIDC／Secret Store、Provider／Storage、命名算法、恢复
  类型、跨 Task 批量、MediaLibrary 整理、上传下载、分布式队列、并行度／超时监督或回滚。
- 不重设计当前九页、Task 详情或改变 flow／文件结果／自动化成功率；删除迁移卡和无生产者
  分支所必需的布局修正需可读、键盘／窄屏可用，当前规则 Edit 深链仍是正式当前入口。
- 不操作用户数据、停止／迁移现有部署、发布／推送、删除 release/v1／tag 或 Git 历史。
  不建设旧数据导入、迁移、暂停恢复、旧请求接管、历史事件重投或旧会话核对界面。

## Acceptance Criteria

- [ ] AC-01 / RO-1：所有指定旧 Web 入口注销；带查询、直达／刷新／重连均使用普通 not-found／
      auth，无遮蔽开关、V1 资源、跳转、说明壳或旧地址到当前意图的自动转换。
- [ ] AC-02 / RO-2：正常当前配置／合法权限下，旧 API 为通用 unknown route；旧 CLI 从 help／
      parser 注销。不能用401/403、无配置503或非零退出冒充删除；无额外工作／Provider／
      Storage 效果，正常解析／认证／脱敏审计允许。无旧票据、调度、grant 专用读写／接线。
- [ ] AC-03 / RO-3：唯一当前 bootstrap／文档／字段／事件／权限／模式有效；覆盖各旧形式
      单独、与新形式混合、旧包导入和任意 JSON 路径拒绝；零发布／Task／媒体效果。
- [ ] AC-04 / RO-2/4：新手工／due／Run once 和四类恢复只走同 Task 内核，保留人等／稳定等、
      原子额度、源归属和并发fence；无非内核整理领取、旧子 Task 链、Pause／resume 实现。
- [ ] AC-05 / RO-4：新库完整 schema 无旧专属结构；同版本 reopen／进程 restart／备份及明确
      非覆盖 restore 保留当前 work。旧／混合／畸形库拒绝前后文件／schema／行不变，
      无隐式DDL／回填、claim、自动清库／重建或媒体效果，不给不兼容部署假 ready。
- [ ] AC-06 / RO-4/5：Task 五态、文件 partial／unknown／缺 Result、取消与真实未完成各自准确；
      旧 flow／命令／事件／session／响应形状不会被映射、展示为当前或产生执行资格。
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

风险 High，产品实施与最终验收 T4。B 在激活后按完整行为规划连贯 Task、实际 Base、
Difficulty／Test Level 与精确 affected／acceptance 命令；本文件不预建 Task 或执行步骤配额。
Developer 仅跑新增／修改／直接受影响测试及必要当前原生链路，按工作流交不可变检查点；
B 独立完成每 Task 必需验收、[shared full gates](docs/development-workflow.md#shared-full-regression-commands)
和最终全部 RO 门禁；A 独立审查整个 Base..Implementation Head，不自审通过。

最终必须提供：退休入口注册与正常输入反证；旧格式拒绝；新库完整结构／不兼容库零变更／
同版本复开；真实 Python/API/SQLite/常驻 Worker+Scheduler+Notification 的上述旅程、
并发／丢响应／权限／pin／不确定故障；当前前端构建与截图；干净来源 wheel／安装目录／
候选 Docker 镜像身份、四服务空初始化及安全／restart proofs。外部 SMB/OpenList/S3/TMDB
用 fake／本地服务器与临时根，既有可选真实外部测试需披露，不拿用户媒体作证明。
证据存稳定忽略目录或 CI；已删除的旧测试／脚本必须逐项对应退出义务或保留的当前断言。

本次规划只检查文档一致性／链接、治理及受影响文档测试和 whitespace；不把这些结果
当作产品 T4、已退役或 Slice PASS。实际规划命令／结果在本地检查点交接中报告。

## Closure Packet and A Final Review

尚未实施，Implementation Head NOT SET。Required Outcomes／最终测试／Closure Packet／
A Final Review 均未完成；Status 保持 PLANNED。用户激活 Slice、B 规划／激活 Task 后才可实施。
历史接受事实不被本规划替代；通过后再统一将 TARGET 协调为 CURRENT，不提前声明退役。
