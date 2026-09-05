# MediaFlow Engineering Requirements Index

本文档把根目录
[《影视媒体资源自动整理系统需求规格说明书》](../影视媒体资源自动整理系统需求规格说明书.md)
中的 V1 产品范围整理为稳定、可引用的工程需求 ID。中文规格书负责完整产品定义；本文档只负责
工程索引、必要的安全推导和验收含义，不替代或缩小中文规格书。

权威关系为：

```text
中文规格书
→ docs/requirements.md
→ SLICE.md
→ TASK.md
```

[product-experience.md](product-experience.md) 解释完整用户旅程，
[architecture.md](architecture.md) 区分实际架构与目标架构，
[SLICE.md](../SLICE.md) 定义当前 A-owned 业务范围。实现进度、审核记录、开发顺序和工作流状态
不属于本文档。

## Scope vocabulary

- **REQUIRED**：V1 产品或实现该产品要求所必需的工程约束。
- **OPTIONAL**：V1 允许提供，但不是所有部署或所有媒体项都必须启用的能力。
- **OUT OF V1**：中文规格书明确放在后续阶段的产品能力。

“可配置”通常表示产品必须提供该配置能力，而不是 OPTIONAL；例如 Hash 模式可以由用户关闭，
但可选择的重复检测策略本身仍是 REQUIRED。实现是否完成不得改变 Scope。

## Traceability and derivation rules

- `Canonical Source` 使用中文规格书的章节标题；章节正文仍是最终解释来源。
- 标为 `Engineering derivation` 的条目不得增加新的用户能力，只能为 canonical 用户结果提供
  必需的一致性、安全、并发、隐私或恢复约束。
- 精确数据库版本、表名、函数名、内部 evidence key、字段顺序、样本数量上限、测试数量和特定
  反证方式属于实现或验收证据，不是稳定 Requirement。
- 当前 Slice 的局部延后不改变 V1 Scope；只有中文规格书才能把产品能力归入 OUT OF V1。

## Canonical coverage map

| Canonical group | Requirement IDs | V1 interpretation |
|---|---|---|
| General and operator experience | `REQ-GEN-*`, `UX-*` | REQUIRED vertical Web journey and explainable, recoverable behavior |
| Storage | `REQ-STO-*` | Local, SMB, OpenList and S3/R2 REQUIRED; future adapter kinds extensible |
| ResourceLibrary and MediaLibrary | `REQ-LIB-*` | REQUIRED source and destination configuration |
| Scanner, filtering, stability and index | `REQ-SCAN-*` | REQUIRED manual, incremental and scheduled discovery without mutation |
| Parser and NFO input | `REQ-PARSE-*` | REQUIRED local parsing; no media-stream inspection |
| Recognition and type policy | `REQ-REC-*` | REQUIRED and independent from downstream policies |
| Metadata | `REQ-META-*` | TMDB REQUIRED through the Provider abstraction; correction is V1, Provider switching is V1.x/post-V1 |
| Naming | `REQ-NAME-*` | REQUIRED pure and reusable policy |
| Classification and MediaLibrary selection | `REQ-CLASS-*` | REQUIRED pure and reusable policy |
| Planning, Preview and organization | `REQ-ORG-*` | REQUIRED explicit plan, safety decision and supported operation |
| Attachments | `REQ-ATT-*` | Existing sidecar organization REQUIRED; generation/download is OUT OF V1 |
| Task, automation and recovery | `REQ-TASK-*`, `REQ-SCHED-*`, `REQ-RECOVERY-*` | REQUIRED durable per-item operation and scheduled automation |
| Logging and results | `REQ-LOG-*`, `REQ-RESULT-*` | REQUIRED persistent, redacted and exportable evidence |
| Configuration | `REQ-CONFIG-*` | REQUIRED managed lifecycle for all canonical configuration families |
| Web, API and security | `REQ-WEB-*`, `REQ-API-*`, `REQ-SAFE-*` | REQUIRED shared application behavior and safety boundary |
| Notifications | `REQ-NOTIFY-*` | Existing signed HTTPS Webhook management and recovery are V1; specialized channels remain post-V1 |
| Deployment and self-hosting | `REQ-DEPLOY-*` | Docker Compose production runtime and durable lifecycle are V1 release requirements |

## V1 final scope decisions

The 2026-09-03 A architecture/roadmap reconciliation retains the 2026-09-02 scope decisions below
and adds the missing manual-operations/file-lifecycle capability without weakening safety or the
closed processing foundations:

- V1 retains the `MetadataProvider` abstraction and the current TMDB production Provider. Provider
  switching, additional production Providers and arbitrary Provider plugins move to V1.x/post-V1;
  `REQ-META-011` is therefore explicitly OUT OF V1. V1 Metadata correction uses the configured TMDB
  Provider and never performs an implicit Provider fallback.
- V1 authentication retains environment-owned API-principal Bearer tokens and the existing RBAC
  boundary. A built-in user/session database, OIDC and reverse-proxy identity integration are
  post-V1. This is a documented self-hosted deployment boundary, not a claim of username/password
  login.
- The existing signed HTTPS Webhook Outbox is a V1 product journey even though specialized email,
  chat and media-server refresh channels remain post-V1. Web/API must manage the existing Webhook
  definition and its safe delivery recovery; the delivery engine is not reimplemented.
- Environment-variable references plus deployment-owned secret injection are the V1 secret boundary.
  Full Secret Store and Docker Secrets-specific ingestion are post-V1 unless separately approved.

These decisions are represented by the closed Slices 26 and 27 and the planned Slices 28 and 29; they
do not create implementation Tasks.

## General product requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-GEN-001 | REQUIRED | MediaFlow shall support the end-to-end chain from Storage and library configuration through scan, parse, recognition, metadata, naming, classification, plan, preview, execution, result and log. | §项目概述; §完整媒体处理流程; §最终核心原则 | A user can complete the promised chain without replacing a required stage with an internal-only shortcut. |
| REQ-GEN-002 | REQUIRED | Storage, libraries, scanning, parsing, recognition, metadata, naming, classification, organization, tasks and logging remain decoupled domain boundaries. | §核心设计原则; §推荐后端模块; §最终架构原则 | Reusing or replacing one policy/provider does not merge identities or move another stage's responsibility. |
| REQ-GEN-003 | REQUIRED | Recognition identity, media identity, name, destination and transfer operation are independent decisions. | §核心设计原则; §典型业务示例; §最终架构原则 | Each decision and its owning policy are independently visible and testable. |
| REQ-GEN-004 | REQUIRED | Failure must not create unknown data loss; safety takes precedence over convenience or automatic continuation. | §项目概述; §安全预览; §高风险文件操作保护 | Uncertain or destructive outcomes stop safely and expose known effects and a recovery action. |

## Operator experience requirements

These IDs are retained because they are already stable references. Their canonical product source is
the Chinese specification; Product Experience supplies the journey-level interpretation.

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| UX-001 | REQUIRED | Every operator-facing capability covers goal, entry, visible state, action, success, failure and recovery. | §产品体验原则; §最终管理界面 | Domain, persistence, API or CLI alone cannot satisfy a Web-facing user requirement. |
| UX-002 | REQUIRED | Failure identifies the affected object/item and stage, durable state, known side effects, retry safety and the next recovery action. | §可操作错误与恢复; §错误体系; §错误记录 | Raw exceptions or a generic Retry control are insufficient. |
| UX-003 | REQUIRED | Batch items retain independent state, result and recovery; one item cannot hide or rewrite another. | §可操作错误与恢复; §批量操作; §操作状态 | Successful siblings are not replayed and every failed/partial item remains diagnosable. |
| UX-004 | REQUIRED | Active configuration is the immutable snapshot actually consumed by runtime. | §配置生命周期; §配置管理 | Draft, validated and active state cannot be confused or silently diverge. |
| UX-005 | REQUIRED | Automated recognition, identity, naming, classification, destination, conflict and execution decisions expose bounded, secret-free explanations. | §可解释决策; §Dry Run 整理预演; §策略测试结果 | The user sees why a result occurred, not only the final value. |
| UX-006 | REQUIRED | Any possible media mutation has an equivalent Preview/DryRun capability and requires explicit execution authority that is separate from Preview. | §安全预览; §Dry Run 整理预演; §高风险文件操作保护; §V1 Scheduled Unattended Organization 授权 | Preview performs zero mutation and cannot itself grant authority. Manual work uses a one-shot decision; scheduled work may use a previously granted valid, explicit, scoped and revocable Automation Task Definition authority without another per-run Preview or Execute click. |
| UX-007 | REQUIRED | Web and API use the same application behavior, permissions, validation, state, audit and safety rules. | §最终管理界面; §API 设计要求; §第一阶段 MVP / UI | A CLI-only or independently reimplemented API journey does not complete a Web management requirement. |
| UX-008 | REQUIRED | Configuration lifecycle state, version/digest, validation evidence and activation identity are visible without exposing secrets. | §配置生命周期; §配置管理; §配置导入导出 | The operator can distinguish editable, tested and runtime-consumed configuration. |
| UX-009 | REQUIRED | Activation is explicit, atomic and fail-closed; failure preserves the previous Active snapshot and a correctable Draft. | §配置生命周期; §配置引用关系 | No partial activation or fallback to an untrusted competing authority is permitted. |
| UX-010 | REQUIRED | Long-running work is pinned to the immutable configuration selected at its creation boundary. | Engineering derivation from §配置生命周期, §任务系统 and §定时任务 | Later activation cannot silently change queued or in-flight work. |

## Storage requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-STO-001 | REQUIRED | V1 supports Local, SMB, OpenList, Cloudflare R2 and S3-compatible Storage through one abstraction. | §存储管理; §第一阶段 MVP / Storage | Each required adapter can be configured and used without business-code backend branches. |
| REQ-STO-002 | REQUIRED | All list, stat, read and mutation operations pass through Storage ports; business code does not call filesystem, SMB, OpenList or object APIs directly. | §Storage 抽象; §OpenList 存储; §R2 / S3 存储 | Adapter substitution does not change domain or application behavior. |
| REQ-STO-003 | REQUIRED | Storage declares supported rename, move, copy, delete, hard-link and soft-link capabilities, and planning checks them before execution. | §Storage 抽象 | Unsupported operations fail explicitly unless an explicit policy authorizes a fallback. |
| REQ-STO-004 | REQUIRED | Storage configuration supports identity, name, type, enable/read-only state, root, timeout, concurrency and notes plus create, edit, delete, copy, enable, disable and safe connection/read/write tests. | §存储配置; §配置操作 | The Web journey can manage and test a Storage without editing files or database rows. |
| REQ-STO-005 | REQUIRED | Provider-specific settings and credentials are validated without disclosing secret values. | §本地存储; §SMB 存储; §OpenList 存储; §R2 / S3 存储; §安全要求 | Invalid paths/endpoints/auth fail clearly; credentials remain encrypted or referenced from an approved secret source. |
| REQ-STO-006 | REQUIRED | Domain plans identify locations by Storage ID plus Storage-relative path; host mount paths never become a remote logical path. | Engineering derivation from §资源库, §媒体库 and §最终路径生成 | The same plan remains portable across adapter implementations and cannot escape an adapter root. |
| REQ-STO-007 | REQUIRED | The Storage architecture permits additional adapters without changing business policy interfaces. | §存储管理 | Additional provider implementations are not V1 deliverables, but the extension boundary is present. |

## Library, scanning and index requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-LIB-001 | REQUIRED | ResourceLibrary binds a Storage and source path with enable state, scan mode/depth, include/exclude rules, stability policy and default recognition rules. | §资源库 | Discovery scope is explicit and does not contain naming, classification or mutation behavior. |
| REQ-LIB-002 | REQUIRED | MediaLibrary binds a destination Storage and root path, with enable state and directory-creation policy. | §媒体库 | Classification selects a configured destination; it does not invent a Storage or arbitrary root. |
| REQ-LIB-003 | REQUIRED | ResourceLibrary and MediaLibrary configuration is available through the final Web management journey and shares API validation/reference rules. | §最终管理界面; §配置管理; §第一阶段 MVP / UI | Users can configure both sides of the workflow without internal configuration knowledge. |
| REQ-SCAN-001 | REQUIRED | Scanning supports manual, full, incremental and scheduled modes and only discovers candidates. | §资源扫描; §增量扫描 | A scan never organizes or mutates media and proceeds to recognition/planning as separate stages. |
| REQ-SCAN-002 | REQUIRED | Filters cover extension, directory, name, size, glob and regex; extensions and ignore patterns are configurable. | §文件过滤; §默认忽略文件 | Temporary/download files and user exclusions are rejected predictably before processing. |
| REQ-SCAN-003 | REQUIRED | Stability checks exclude actively downloaded, copied or written files using configurable age, modification and stable-size rules. | §文件稳定性检测 | An unstable file cannot enter organization until it satisfies policy. |
| REQ-SCAN-004 | REQUIRED | Scanned files have a durable index and stable identity with New, Modified, Unchanged and Missing reconciliation. | §数据索引; §增量扫描; §文件状态 | Incremental scans reprocess only appropriate files and do not fabricate deletion from an incomplete scan. |
| REQ-SCAN-005 | REQUIRED | Scan concurrency, cancellation and per-library isolation are bounded. | Engineering derivation from §并发控制 and §任务操作 | Cancelling or failing one scope preserves already durable observations and does not mutate media. |
| REQ-SCAN-006 | REQUIRED | Scan/discovery state and media-processing disposition are orthogonal, and a current source occurrence can be distinguished from a different file later appearing at the same Storage/path. | §数据索引; §文件状态; §整理结果记录; Engineering derivation from §增量扫描 | COPY or Skip may leave a READY source with an organized/skipped disposition; MOVE may make it Missing. Prior results do not permanently suppress a new file at the same path, and explicit Reprocess remains possible. |

## Parser requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-PARSE-001 | REQUIRED | Parsing uses only filename, extension, parent paths/directories, NFO and existing local organization information. | §媒体文件解析 | Parser performs no Provider call, classification or mutation. |
| REQ-PARSE-002 | REQUIRED | Parser extracts title/year, season/episode sets and filename/path technical, language, version and release tags. | §文件名解析 | Extracted technical tags are evidence from names/paths, not verified media-stream properties. |
| REQ-PARSE-003 | REQUIRED | Common single- and multi-episode forms, including Latin and Chinese forms listed by the canonical specification, are supported. | §季集识别 | Equivalent forms produce normalized season and episode values. |
| REQ-PARSE-004 | REQUIRED | NFO is accepted as bounded, safe local input and cannot inject unsafe XML behavior or bypass identity evidence. | §媒体文件解析; Engineering derivation from §安全要求 | NFO parsing is read-only, bounded and reconciled with other local evidence. |

## Recognition requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-REC-001 | REQUIRED | RecognitionRule evaluates configured filename/path/directory/extension/keyword/regex/exclusion conditions and returns only a RecognitionType. | §识别规则 | Recognition neither resolves metadata nor names, classifies, plans or mutates media. |
| REQ-REC-002 | REQUIRED | AND, OR and NOT conditions plus deterministic priority, stop/continue and ambiguity evidence are supported. | §识别规则条件关系; §识别规则优先级 | Competing matches have an explained deterministic or review-required outcome. |
| REQ-REC-003 | REQUIRED | Users can define enabled custom RecognitionTypes. | §识别类型; §配置管理 | Types are stable identities referenced by rules and policies. |
| REQ-REC-004 | REQUIRED | RecognitionTypePolicy independently maps a type to Metadata, Naming, Classification and Organize policies. Reusing downstream policies never changes the RecognitionType. | §识别类型策略; §典型业务示例; §验收核心场景 | Type C remains C while using A naming/classification/organize policies. |
| REQ-REC-005 | REQUIRED | Unrecognized or ambiguous items provide Web-visible evidence and explicit choose, reevaluate, rule-edit/test or ignore recovery. | §未识别媒体; §产品体验原则 | No hidden default type is applied and downstream execution waits for an explicit valid decision. |

## Metadata requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-META-001 | REQUIRED | Metadata is accessed through a Provider abstraction; TMDB is the first required V1 production Provider and business code does not depend on TMDB DTOs or HTTP APIs. | §元数据服务; §元数据 Provider 抽象; §Provider 选择与切换; §第一阶段 MVP / Metadata | Provider responses are converted into internal candidates and identities; a second production Provider is not required solely to prove the abstraction. |
| REQ-META-002 | REQUIRED | The provider boundary supports movie/TV search and detail, season, episode, external-ID lookup and image metadata concepts. | §元数据 Provider 抽象 | Movie and TV queries remain distinct and future providers can implement the same contract. |
| REQ-META-003 | REQUIRED | Provider configuration supports credential reference, language, region, proxy, timeouts, concurrency, retry and cache settings. | §TMDB 配置; §Provider 请求控制 | Runtime behavior follows validated configuration without exposing credential values. |
| REQ-META-004 | REQUIRED | MetadataPolicy references the configured V1 TMDB Provider and defines query type, locale, matching thresholds, search behavior and cache controls. | §元数据策略; §Provider 选择与切换 | RecognitionTypePolicy selects Metadata behavior indirectly through MetadataPolicy; no hidden Provider default or implicit fallback overrides the configured reference. |
| REQ-META-005 | REQUIRED | Search results are scored using bounded title, alias, original title, year, type, episode and context evidence; the first result is never silently accepted. | §元数据候选评分 | Thresholds distinguish automatic acceptance, human confirmation and failure. |
| REQ-META-006 | REQUIRED | Existing TMDB, IMDb, TVDB or supported external IDs are tried through the provider lookup boundary. | §外部 ID 识别 | Direct-ID evidence is validated and normalized rather than injected as arbitrary identity. |
| REQ-META-007 | REQUIRED | A normalized MediaIdentity contains provider identity, media type, titles, dates, episodic data, locale/classification metadata, artwork references, RecognitionType and confidence evidence. | §元数据识别结果 | Provider-specific DTOs do not leak into naming, classification or result models. |
| REQ-META-008 | REQUIRED | Metadata failure correction supports query/year changes, Movie/TV choice, candidate selection, direct TMDB Provider ID, retry and ignore through Web/API. | §人工元数据识别; §元数据识别失败; §第一阶段 MVP / UI | The corrected identity is explained, RecognitionType is preserved and continuation returns through Preview before execution; an unavailable TMDB reference fails closed. |
| REQ-META-009 | REQUIRED | Search, detail, season, episode, external-ID and image metadata responses support configurable caching, refresh and clear operations. | §元数据缓存 | Repeated scans do not require unnecessary Provider calls and stale cache can be explicitly refreshed. |
| REQ-META-010 | REQUIRED | Provider calls enforce bounded concurrency, throttling, timeout, retry/backoff, proxy and HTTP 429/temporary 5xx handling. | §Provider 请求控制; §自动重试 | Permanent/configuration failures do not loop indefinitely and secrets never appear in errors or logs. |
| REQ-META-011 | OUT OF V1 | V1.x may support selecting and switching the Provider referenced by MetadataPolicy through managed Draft, Validate/Test and Activate lifecycle. | §Provider 选择与切换; A planning decision 2026-09-02 | When delivered, new work will use the newly Active reference; already pinned Jobs/Tasks must retain their Provider and policy snapshot, and an unavailable selected Provider must fail safely instead of triggering an unauthorized implicit switch. |

## Naming requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-NAME-001 | REQUIRED | NamingPolicy is a reusable pure calculation from resolved identity and parser evidence to directory name and filename. | §命名规则; §最终架构原则 | Naming performs no Storage access, classification or mutation. |
| REQ-NAME-002 | REQUIRED | Naming configuration includes stable identity/name, movie and episodic templates, sanitization, missing-variable behavior and enable state. | §命名规则配置 | Invalid or referenced policy edits fail through managed configuration validation. |
| REQ-NAME-003 | REQUIRED | Canonical title, date, episode, provider and filename-tag variables are available to templates. | §命名变量 | Template expansion is deterministic and missing values follow explicit policy. |
| REQ-NAME-004 | REQUIRED | Movie, TV season, single-episode and multi-episode names can be represented. | §电影命名; §剧集命名 | Preview shows the exact rendered directory segments and filename. |
| REQ-NAME-005 | REQUIRED | Missing fields and unsafe characters/spacing/Unicode/path length are handled by explicit bounded rules. | §命名字段缺失处理; §文件名字符处理 | Unsafe output cannot silently become a target path; failure or manual recovery is actionable. |

## Classification and MediaLibrary requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-CLASS-001 | REQUIRED | ClassificationPolicy is a reusable pure decision from RecognitionType, MediaIdentity, parser evidence and source context to MediaLibrary plus relative path. | §分类规则; §最终架构原则 | Classification performs no naming, Storage call or mutation. |
| REQ-CLASS-002 | REQUIRED | Conditions cover the canonical type, title/year, genre/country/language, technical tags, Provider, ResourceLibrary and original source fields. | §分类条件 | Match evidence identifies the conditions that selected or rejected a rule. |
| REQ-CLASS-003 | REQUIRED | A classification result identifies a configured MediaLibrary and safe relative subpath. | §分类动作; §媒体库 | Missing/disabled destinations fail or enter explicit recovery rather than inventing a target. |
| REQ-CLASS-004 | REQUIRED | Rule priority, stop/continue behavior and explicit default, stop or manual fallback are configurable. | §分类规则优先级 | Unclassified outcomes are visible and never silently routed. |
| REQ-CLASS-005 | REQUIRED | Reusing a ClassificationPolicy preserves the original RecognitionType. | §分类示例; §验收核心场景 | Type C may select A's destination rules while its result identity remains C. |

## Planning, Preview and organization requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-ORG-001 | REQUIRED | Final target is composed from MediaLibrary root, classification relative path, naming directory and filename. | §最终路径生成 | Each contribution is attributable and the composed Storage-relative path is safe. |
| REQ-ORG-002 | REQUIRED | OrganizePolicy selects Move, Copy, HardLink or SoftLink plus conflict, duplicate, attachment, cleanup, failure and explicit fallback policies. | §整理规则; §整理规则配置 | Operation semantics cannot be changed by an adapter or hidden default. |
| REQ-ORG-003 | REQUIRED | Planner creates an immutable OrganizePlan, validates path, destination, capabilities and conflicts, and performs no mutation. | §Move; §Storage 抽象; §整理操作记录; §最终核心原则 | An unsafe, unresolved or unsupported plan is rejected before execution with an actionable reason. |
| REQ-ORG-004 | REQUIRED | DryRun executes the complete decision/planning chain and shows source, parser, rule/type, metadata, policies, target, conflicts and warnings with zero mutation. | §Dry Run 整理预演; §策略测试工具 | Preview and execution use the same production policy/planning semantics. |
| REQ-ORG-005 | REQUIRED | Automatic organization proceeds only after successful identity, naming, classification and target validation with no unresolved human conflict. | §自动整理 | Any unmet precondition routes the item to an explicit review/recovery state. |
| REQ-ORG-006 | REQUIRED | Duplicate detection considers target existence and may use provider/media/episode/size/hash evidence under a configurable no/fast/full hash policy. | §文件重复检测; §Hash 策略; §第一阶段 MVP / Organizer | Hash strength and uncertainty are visible; uncertainty never authorizes overwrite or delete. |
| REQ-ORG-007 | REQUIRED | Target conflicts support Skip, Overwrite, Rename and Manual outcomes. | §冲突策略 | Skip preserves source, Rename is deterministic, Manual waits, and Overwrite requires explicit configuration and confirmation. |
| REQ-ORG-008 | REQUIRED | Only OrganizerExecutor may perform Storage mutation and it executes only an explicitly authorized valid plan. | §安全预览; §最终核心原则 | All analysis stages and DryRun remain zero-mutation; execution effects are recorded. |
| REQ-ORG-009 | REQUIRED | Unsupported HardLink/SoftLink or transfer behavior fails unless a user-configured fallback explicitly permits another operation. | §HardLink / SoftLink; §高风险文件操作保护 | No silent fallback to Copy or Move is possible. |
| REQ-ORG-010 | REQUIRED | Optional source-directory cleanup is bounded, never removes unknown files and is disabled by default. | §空目录处理; §高风险文件操作保护 | Cleanup occurs only after verified eligible organization and cannot escape the source library boundary. |
| REQ-ORG-011 | REQUIRED | Preview/DryRun records inspectable findings and plans but does not create a mandatory execution-blocker backlog; formal Conflict/Review/Recovery state is created only by an explicit Organize attempt. | §安全预览; §Dry Run 整理预演; Engineering derivation from §任务状态 | Preview answers what would happen with zero mutation and no execution authority. Historical Preview-created blockers remain auditable, but new Preview behavior does not require the user to resolve them. |

## Attachment requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-ATT-001 | REQUIRED | Organization discovers and plans related subtitles, NFO, poster, fanart, images, trailers and matching sidecars with the primary media. | §附属文件整理; §第一阶段 MVP / Organizer | Sidecars remain associated with the primary plan and share its conflict/safety decisions. |
| REQ-ATT-002 | REQUIRED | Subtitle language, script, Forced, SDH and other existing suffixes are preserved where possible. | §字幕 | Renaming retains meaningful subtitle identity and does not silently collide. |
| REQ-ATT-003 | REQUIRED | Main media is distinguished from sample, trailer, extra, featurette and behind-the-scenes content using configurable evidence. | §主文件与附加内容识别 | Additional content is not mistaken for the primary item without explanation. |

## Task and recovery requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-TASK-001 | REQUIRED | Scan, recognition, metadata refresh and organization are represented as durable Tasks or composed child work. | §任务系统; §任务类型 | Long work is observable and not hidden inside an HTTP request or UI page. |
| REQ-TASK-002 | REQUIRED | Task state covers pending, pipeline stages, waiting confirmation, organizing and completed/partial/failed/cancelled outcomes. | §任务状态; §文件状态 | State transitions identify the current stage and do not call partial work successful. |
| REQ-TASK-003 | REQUIRED | Task information includes scope, times, totals, success/failure/skip counts and progress. | §任务信息 | Summary totals reconcile with item states and durable results. |
| REQ-TASK-004 | REQUIRED | Start, pause, resume, cancel, retry, failed-item retry, detail and history deletion are supported. | §任务操作; §第一阶段 MVP / Task | History deletion never changes media; resume/retry cannot silently gain execution authority. |
| REQ-TASK-005 | REQUIRED | Global, Storage and Provider concurrency are bounded and the same Storage-relative source has one effective operation lock. | §并发控制; §文件锁 | Concurrent workers cannot perform conflicting operations on one source. |
| REQ-TASK-006 | REQUIRED | Each item stores its plan and per-operation pending/running/success/failed/skipped state. | §整理操作记录; §操作状态 | Recovery can distinguish completed, failed and not-started effects. |
| REQ-TASK-007 | REQUIRED | Queue admission and work ownership are atomic and bounded; stale ownership cannot overwrite a newer worker's result. | Engineering derivation from §任务系统, §并发控制 and §定时任务 | Capacity or worker races do not duplicate work, consume authority incorrectly or corrupt durable state. |
| REQ-TASK-008 | REQUIRED | A long-lived Automation Task Definition, each Scheduler-emitted Automation Job, the actual Task/TaskItems and their Results are distinct but traceable objects. | §自动化对象与生命周期边界 | The definition stores reusable intent, a Job represents one occurrence, existing Task/TaskItem semantics track actual work, and Result/Log records per-item outcome without creating a parallel execution model. |
| REQ-TASK-009 | REQUIRED | Queued work exposes bounded processing-Worker liveness/readiness evidence independently from API process health, and the API never supervises or silently starts Worker subprocesses. | §任务系统; §系统设置; Engineering derivation from §可操作错误与恢复 | A long-Pending Job explains whether a Worker is currently available; production process supervision remains a deployment responsibility. |
| REQ-RECOVERY-001 | REQUIRED | Errors use stable categories for Storage, file, parse, recognition, metadata, naming, classification, transfer, timeout and unknown failures. | §错误体系 | UI/API can render recovery without parsing exception text. |
| REQ-RECOVERY-002 | REQUIRED | Error evidence contains code/message, Task and item context, source/Storage, stage, time, retryability and bounded debug detail. | §错误记录; §可操作错误与恢复 | Evidence is actionable and secret-free. |
| REQ-RECOVERY-003 | REQUIRED | Temporary network/provider/storage errors may use bounded retry with configurable maximum, delay and backoff; permanent configuration errors do not retry indefinitely. | §自动重试 | Automatic retry never replays uncertain media mutation. |
| REQ-RECOVERY-004 | REQUIRED | Unrecognized media supports reevaluation, explicit type selection, rule creation/testing and ignore. | §未识别媒体 | Decisions are durable, audited and continue only through the normal pipeline. |
| REQ-RECOVERY-005 | REQUIRED | Metadata failure supports correction through the configured V1 TMDB Provider, direct ID/candidate selection, retry and ignore. | §元数据识别失败 | Correction preserves user input/evidence, keeps the configured Provider boundary and does not inject arbitrary identity. |
| REQ-RECOVERY-006 | REQUIRED | Per-item checkpoints record the last durable stage, completed/verified/uncertain effects, blocking decision, retry safety and permitted actions. | Engineering derivation from §操作状态, §可操作错误与恢复 and §任务操作 | Successful siblings are not replayed and uncertain execution is investigated instead of automatically repeated. |
| REQ-RECOVERY-007 | REQUIRED | Manual organization lets a user select permitted type/identity/policies, regenerate Preview, resolve conflicts and explicitly authorize the exact reviewed plan. | §人工整理; §策略测试工具 | Arbitrary unsafe target paths or hidden execution are rejected. |
| REQ-RECOVERY-008 | REQUIRED | Bounded batch operations include rescan, recognition, type assignment, metadata, DryRun, organization, retry and ignore while preserving item independence. | §批量操作; §可操作错误与恢复 | One batch action cannot overwrite another item's decision or conceal its recovery. |
| REQ-RECOVERY-009 | REQUIRED | A saved Conflict/Review decision is non-executing and leads through re-analysis plus explicit continuation authorization back to the blocked Organize item. | §冲突策略; §任务操作; §可操作错误与恢复 | Destructive decisions do not execute on save, successful siblings remain terminal, and uncertain mutation is never replayed automatically. |

## Scheduler and automation requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-SCHED-001 | REQUIRED | ResourceLibrary supports scan-only, scan-and-plan and automatic-organization modes. | §自动整理 | Automatic execution still satisfies identity, safety, conflict and authority gates. |
| REQ-SCHED-002 | REQUIRED | Schedules support periodic/Cron timed scan, automatic organization, cache cleanup and log cleanup with configured timezone semantics. | §定时任务 | The user can manage schedules through the same configuration and Web/API authority. |
| REQ-SCHED-003 | REQUIRED | Scheduler only decides when a configured Automation Task Definition is due and durably emits an idempotent Automation Job; it never chooses media policies or invokes Storage mutation. | §Scheduler 责任边界; Engineering derivation from §任务系统 | Restart/concurrency cannot duplicate an occurrence, and Scheduler cannot bypass the normal policy, Preview or execution-authority chain. |
| REQ-SCHED-004 | REQUIRED | An Automation Task Definition identifies the ResourceLibrary/source scope and optional sub-scope, schedule/timezone, enabled state, managed configuration authority, execution mode/authority and bounded run limits. | §自动化对象与生命周期边界 | The user can define what source is eligible and when it runs without embedding a per-file Provider, final destination or transfer operation. |
| REQ-SCHED-005 | REQUIRED | Every scheduled media item follows Scan, Parse, Recognition, RecognitionType, RecognitionTypePolicy, MetadataPolicy, NamingPolicy, ClassificationPolicy, OrganizePolicy, Plan/Preview, Execute and Result/Log. | §定时自动整理链路 | Different RecognitionTypes in one occurrence may select different Providers, naming/classification policies, MediaLibraries and operations; ClassificationPolicy owns destination and OrganizePolicy owns operation. |
| REQ-SCHED-006 | REQUIRED | V1 scheduled automatic organization supports an explicit, persistent, revocable and scope-bounded unattended execution grant on the Automation Task Definition. | §V1 Scheduled Unattended Organization 授权 | While the grant remains valid and all safety gates pass, a due occurrence executes without another manual Execute click; manual/remote real execution retains its separate one-shot ticket semantics. |
| REQ-SCHED-007 | REQUIRED | Scheduled execution fails closed before mutation when its pinned configuration/references, Storage capabilities, current permissions, unattended grant, source scope or any recognition/planning/conflict safety condition is invalid. | §V1 Scheduled Unattended Organization 授权 | Revocation blocks not-yet-performed mutation, out-of-scope work never executes, and each blocked item retains actionable TaskItem/Result/Log evidence. |

## Logging and result requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-LOG-001 | REQUIRED | Logging supports TRACE, DEBUG, INFO, WARN and ERROR with INFO default and useful DEBUG diagnostics. | §日志系统; §Debug 日志 | Operators can diagnose each pipeline stage without enabling unsafe data disclosure. |
| REQ-LOG-002 | REQUIRED | Per-item logs explain discovery, rule/type, metadata, naming, classification, target, operation, retry and outcome. | §普通整理日志; §Debug 日志; §可解释决策 | Logs supplement durable item/result state rather than serving as its only source. |
| REQ-LOG-003 | REQUIRED | Passwords, tokens, API keys, access keys, authorization headers, cookies and equivalent secrets are redacted. | §日志脱敏; §安全要求 | No normal/debug/audit/error path emits a recoverable secret. |
| REQ-RESULT-001 | REQUIRED | Every organization Task persists item results in the database and supports JSON export; CSV export is OPTIONAL. | §整理结果记录 | Result history survives process exit and can be exported without reading media. |

## Notification requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-NOTIFY-001 | REQUIRED | V1 Web/API manages the existing signed HTTPS Webhook subscription: create, edit, enable, disable, secret environment-variable reference, event selection and bounded read-only connection/test semantics. | §配置管理; §自动整理; §日志系统 | The operator can make the existing Outbox useful without editing JSON or database rows; tests never expose or persist the secret value. |
| REQ-NOTIFY-002 | REQUIRED | V1 Web/API exposes delivery status and safe recovery for retryable, expired-lease and dead-letter deliveries without changing completed media work. | §自动整理; §可操作错误与恢复 | Delivery failure remains independently visible, retry/requeue is explicit, at-least-once semantics are documented and payloads/secrets remain hidden. |
| REQ-RESULT-002 | REQUIRED | Result items include source, RecognitionType, Provider identity, policy identities, target, status and error plus enough identity/effect evidence for recovery. | §JSON 结果示例; §整理操作记录 | A user can determine what was decided and what happened for each item. |
| REQ-RESULT-003 | REQUIRED | Result, TaskItem, plan, operations, reviews/conflicts and logs remain linkable by stable identifiers. | Engineering derivation from §任务信息, §整理操作记录 and §媒体详情 | Web/API can traverse history without manual database joins. |

## Configuration requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-CONFIG-001 | REQUIRED | Managed configuration covers Storage, ResourceLibrary, MediaLibrary, Metadata Provider/Policy, Recognition Rule/Type/TypePolicy, Naming, Classification, Organize, Schedule and system settings. | §配置管理 | Every canonical family participates in one validated dependency graph. |
| REQ-CONFIG-002 | REQUIRED | Configuration objects support create, edit, copy, enable, disable, delete and applicable safe test actions through Web/API. | §配置操作; §最终管理界面 | Object management does not require direct JSON or database editing. |
| REQ-CONFIG-003 | REQUIRED | References/dependents are visible and referenced deletion is blocked by default. | §配置引用关系 | The user sees impact and must repoint/remove references explicitly. |
| REQ-CONFIG-004 | REQUIRED | Configuration supports versioned import/export, backup and recovery; secrets are excluded or separately protected. | §配置导入导出 | Imported data is validated and cannot become Active merely by existing. |
| REQ-CONFIG-005 | REQUIRED | Managed lifecycle is Draft to exact-version validation/test to explicit atomic activation to immutable runtime snapshot. | §配置生命周期; §配置管理 | Editing never mutates Active; failure keeps the prior Active and a correctable Draft. |
| REQ-CONFIG-006 | REQUIRED | Configuration edits use optimistic concurrency and produce bounded, secret-free Before/After audit. | Engineering derivation from §配置引用关系 and §审计日志 | Stale writers cannot silently overwrite a newer Draft. |
| REQ-CONFIG-007 | REQUIRED | Validation and safe-test evidence binds to the exact revision and becomes stale after any edit. | Engineering derivation from §配置生命周期 and §策略测试工具 | Activation cannot reuse evidence from different content. |
| REQ-CONFIG-008 | REQUIRED | Runtime, API, workers, Jobs, Tasks and scheduled work resolve the same immutable Active or pinned snapshot identity and fail closed if unavailable or invalid. | Engineering derivation from §配置生命周期, §Provider 选择与切换, §Scheduler 责任边界 and §任务系统 | New activation affects only work created afterward; queued/in-flight work retains its pinned Provider and policy semantics, while revocable execution authority remains a separate live safety gate. |
| REQ-CONFIG-009 | REQUIRED | Validation and policy tests are zero-mutation; connectivity/read/write tests use the least authority necessary and clearly state their effects. | §策略测试工具; §存储配置; §安全预览 | A test cannot silently scan, organize or grant execution authority. |
| REQ-CONFIG-010 | REQUIRED | Credentials are stored encrypted or resolved through an approved external secret source and never returned in normal configuration payloads. | §TMDB 配置; §安全要求; §配置导入导出 | Copy, diff, export, audit and error paths remain secret-free. |
| REQ-CONFIG-011 | REQUIRED | System settings cover database/work/cache/log/export locations, default locale/timezone/log level and retention, concurrency and retry policy. | §系统设置 | Values are validated, permission-aware and consumed from the same configuration authority. |
| REQ-CONFIG-012 | REQUIRED | The primary Web configuration journey uses discoverable typed forms/cards; editing Active explicitly creates a successor Draft, while whole-document JSON is an Advanced/import/export/support surface. | §配置生命周期; §配置操作; §配置导入导出; §最终管理界面 | Active remains immutable, ordinary object management does not feel JSON-only, and Advanced JSON cannot silently become runtime authority. |

## Deployment and self-hosting requirements

These requirements are engineering derivations from the final self-hosted product goal. They define
the release contract, not a new media-processing engine.

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-DEPLOY-001 | REQUIRED | V1 ships one immutable MediaFlow image and a Docker Compose topology with independent API, Worker, Scheduler and Notification Worker services. | Final self-hosted product goal; §推荐后端模块 | `docker compose up -d` starts the product while preserving process failure isolation and the existing application boundaries. |
| REQ-DEPLOY-002 | REQUIRED | Production HTTP serving uses a production WSGI server behind an explicit TLS/reverse-proxy or LAN boundary; the development `wsgiref.simple_server` listener is not the production server. | Engineering derivation from §最终管理界面 and §安全要求 | Worker/process model, request limits, graceful shutdown, host binding, proxy trust and direct-Internet support are documented and tested. |
| REQ-DEPLOY-003 | REQUIRED | `/data` is the single local persistent MediaFlow volume for SQLite, operation history, durable logs, managed configuration/evidence, Automation state, Task/Result state, notification state, audit and migration markers. | Final self-hosted product goal; §系统设置 | `mediaflow.sqlite3` stays on a persistent local filesystem volume; SQLite on SMB/NFS/OpenList/S3/R2 is unsupported without dedicated proof. |
| REQ-DEPLOY-004 | REQUIRED | Media Storage is a separate explicit bind-mount/configuration boundary. Local `rootPath` means a container-visible absolute path, and the product documents read-only/read-write mounts, UID/GID, ownership and permission recovery. | §本地存储; final self-hosted product goal | Unmounted host paths, host `/`, Docker socket and arbitrary host filesystem access are rejected or unsupported; Storage root confinement remains enforced. |
| REQ-DEPLOY-005 | REQUIRED | Liveness, readiness and business/runtime health are distinct bounded signals; health checks do not scan Storage, call Providers, create work, send notifications or mutate media. | Engineering derivation from §系统设置 and §安全要求 | API/bootstrap readiness can be healthy while no Active runtime exists; process failures and business blockers remain distinguishable. |
| REQ-DEPLOY-006 | REQUIRED | Restart and upgrade preserve durable state and fail closed around stale ownership, uncertain mutation and migration failure. | §配置生命周期; §任务系统; §可操作错误与恢复 | Compose restart creates no duplicate occurrence or mutation, never silently replays uncertain work, and schema migration has a verified preflight/recovery path. |
| REQ-DEPLOY-007 | REQUIRED | Deployment secrets are injected by the environment/deployment and never enter the image, managed configuration, SQLite evidence, logs, API, Web or exported configuration. | §日志脱敏; §安全要求; §配置导入导出 | Secret rotation is documented as a controlled deployment/process lifecycle; full Secret Store integration is not required for V1. |

## Web, API and security requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-WEB-001 | REQUIRED | Web UI is the primary V1 management surface for setup, configuration, daily work, review, recovery and explicit execution. | §最终管理界面; §第一阶段 MVP / UI | Required journeys are discoverable and complete without CLI-only knowledge. |
| REQ-WEB-002 | REQUIRED | Dashboard shows bounded Storage/library, file, waiting/review, Task, success/failure and recent-error summaries. | §Dashboard | Counts link to the underlying actionable scope and do not expose secrets. |
| REQ-WEB-003 | REQUIRED | Files support bounded list, search/filter and detail including source/library, recognition, metadata, policies, target, result/history, errors and available actions. | §文件列表; §搜索与筛选; §媒体详情 | Users can answer what, why, outcome and next action without manual joins or raw logs. |
| REQ-WEB-004 | REQUIRED | Web manages Storage, libraries, the V1 TMDB Provider reference/policy, RecognitionTypes/policies, Automation Task Definitions/schedules, Tasks, manual identity correction and DryRun. | §第一阶段 MVP / UI; §配置管理; §自动化对象与生命周期边界 | Each management surface uses the same validation, permission, audit and safety contract as API; arbitrary Provider switching is not a V1 capability. |
| REQ-WEB-005 | REQUIRED | Task, review, conflict and recovery actions use explicit confirmation and never execute merely by viewing a page. | §任务操作; §人工元数据识别; §冲突策略; §人工整理 | Read paths are side-effect free and write actions show resulting durable state. |
| REQ-WEB-006 | REQUIRED | System/configuration status is bounded, permission-aware and secret-free, and distinguishes unavailable data from false success. | §Dashboard; §系统设置; §可操作错误与恢复 | Status views do not contact media services or expose paths/options beyond the user's authority. |
| REQ-WEB-007 | REQUIRED | **Files** browses bounded real directories/files from configured Storage, while **FileIndex** presents MediaFlow discovery, processing disposition, history and available actions. | §存储管理; §数据索引; §文件列表; §媒体详情 | Users do not mistake the scan index for a file manager, and both surfaces use Storage-relative identities without arbitrary host access. |
| REQ-API-001 | REQUIRED | Core Storage, libraries, metadata, recognition, policies, files/media, Tasks, logs and settings capabilities have versioned API surfaces. | §API 设计要求 | Web, CLI and automation can invoke shared application use cases. |
| REQ-API-002 | REQUIRED | API validation, concurrency, permissions, state transitions, errors, audit and safety are identical to Web behavior. | §最终管理界面; §API 设计要求 | No alternate endpoint bypasses configuration, conflict or execution gates. |
| REQ-API-003 | REQUIRED | Collections and evidence are bounded and deterministically ordered; errors have stable safe categories. | Engineering derivation from §搜索与筛选, §错误记录 and §安全要求 | Large histories cannot create unbounded responses or secret-bearing raw exceptions. |
| REQ-SAFE-001 | REQUIRED | Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner are zero-mutation stages. | §最终核心原则 | Any mutation call from these stages is a safety defect. |
| REQ-SAFE-002 | REQUIRED | DryRun and policy/configuration preview perform zero media mutation. | §安全预览; §Dry Run 整理预演 | DryRun follows the full calculation chain but never invokes execution. |
| REQ-SAFE-003 | REQUIRED | OrganizerExecutor is the only application boundary allowed to call mutating Storage operations. | §最终核心原则 | Mutation authority is explicit, narrow and auditable. |
| REQ-SAFE-004 | REQUIRED | Overwrite, delete, source removal and directory cleanup require explicit policy and user/system authority; defaults deny them. | §高风险文件操作保护; §冲突策略 | No silent overwrite/delete or authority escalation is possible. |
| REQ-SAFE-005 | REQUIRED | Authentication and least-privilege authorization protect management, audit and execution surfaces. | Engineering derivation from §安全要求, §审计日志 and §API 设计要求 | Read, edit, cancel and execute permissions remain separable; a viewer cannot mutate state. |
| REQ-SAFE-006 | REQUIRED | Security audit records important configuration, manual decision, overwrite/delete and cancellation actions with actor, before/after, time and result. | §审计日志 | Audit is durable, bounded and secret-free. |
| REQ-SAFE-007 | REQUIRED | Automated tests and isolated acceptance use fakes/local services or explicit dedicated test roots and never production media or credentials. | Engineering derivation from §安全要求 and §高风险文件操作保护 | Verification cannot mutate an unapproved user library or leak private configuration. |
| REQ-SAFE-008 | REQUIRED | Persistent scheduled execution authority is bound to one Automation Task Definition and its permitted source/run scope, is independently revocable and does not imply Overwrite, Delete, cleanup or broader file authority. | §V1 Scheduled Unattended Organization 授权; §高风险文件操作保护 | OrganizerExecutor validates current authority and the pinned valid plan before every not-yet-performed mutation; invalid or excessive authority fails closed and is audited. |

## Explicit post-V1 product scope

These entries preserve the canonical second-stage boundary. Existing technical experiments or reusable
infrastructure do not promote them into V1 acceptance requirements.

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| FUTURE-STO-001 | OUT OF V1 | Additional Storage providers such as WebDAV, SFTP, FTP, OSS and COS. | §存储管理; §第二阶段 | Storage extension architecture remains required, but these adapters are not V1 closure criteria. |
| FUTURE-META-001 | OUT OF V1 | Additional public/custom Metadata Providers beyond TMDB as product integrations. | §元数据服务; §第二阶段 | Provider abstraction is V1; additional integrations are later product scope. |
| FUTURE-META-002 | OUT OF V1 | Metadata Provider selection and switching through managed policy lifecycle. | §Provider 选择与切换; A planning decision 2026-09-02 | Existing V1 Jobs/Tasks remain snapshot-pinned; a future switch must fail closed when the selected Provider is unavailable and must never silently fall back. |
| FUTURE-MEDIA-001 | OUT OF V1 | Multi-version media, quality-priority policy and automatic media upgrades. | §第二阶段 | These capabilities cannot be inferred from duplicate or naming support. |
| FUTURE-ASSET-001 | OUT OF V1 | Poster/background download and NFO generation. | §第二阶段 | Organizing existing sidecars remains V1; creating/downloading new assets does not. |
| FUTURE-NOTIFY-001 | OUT OF V1 | Specialized notification channels such as email/chat providers and media-server refresh notifications. | §第二阶段; A planning decision 2026-09-02 | The existing signed HTTPS Webhook management and delivery recovery are V1; specialized channels remain later product scope. |
| FUTURE-ROLLBACK-001 | OUT OF V1 | Complete historical/crash recovery Rollback. | §第二阶段 | V1 still requires known-effect reporting and safe per-item recovery; it does not promise universal rollback. |
| FUTURE-SEC-001 | OUT OF V1 | A complete user/identity administration system and advanced audit features. | §第二阶段 | V1 still requires authenticated least-privilege access; a full identity product is later scope. |
| FUTURE-UI-001 | OUT OF V1 | Advanced statistics beyond the required Dashboard and bounded operational views. | §第二阶段 | Core status, results and recovery views remain V1 requirements. |

## Canonical acceptance scenarios

| Scenario | Stable requirements | Acceptance Meaning |
|---|---|---|
| Movie uses Movie policies | `REQ-REC-004`, `REQ-META-*`, `REQ-NAME-*`, `REQ-CLASS-*`, `REQ-ORG-*` | A movie is identified, named, classified, previewed and safely organized into the configured movie library. |
| TV uses TV policies | `REQ-PARSE-003`, `REQ-META-*`, `REQ-NAME-004`, `REQ-CLASS-*`, `REQ-ORG-*` | Season/episode identity produces the configured TV directory and episode name without losing episodic evidence. |
| Type C reuses A policies | `REQ-REC-004`, `REQ-CLASS-005`, `REQ-ORG-001` | RecognitionType remains C while A Naming/Classification policies determine the reusable output behavior. |
| Scheduled automatic organization | `REQ-SCHED-*`, `REQ-TASK-*`, `UX-006`, `REQ-SAFE-*` | A managed Automation Task Definition emits snapshot-pinned bounded work; a valid explicit scoped unattended grant permits due execution without another click, while every item still satisfies the normal policy, Preview, conflict and fail-closed mutation gates. |
| Failure inside a batch | `UX-002`, `UX-003`, `REQ-RECOVERY-*`, `REQ-RESULT-*` | Successful items remain complete while the affected item retains known effects and an explicit safe recovery path. |

## Requirement acceptance rule

A Requirement is satisfied only when its canonical user outcome and Acceptance Meaning are met across
all required surfaces. Internal implementation, a test in isolation, or a currently deferred Slice does
not weaken the Requirement. Conversely, a Slice-specific evidence shape or proof technique does not
become a permanent Requirement unless it is necessary to preserve one of the stable semantics above.
