# MediaFlow Canonical Product Requirements

本文档保存 MediaFlow 的 canonical V1 产品基线、明确授权的现行产品修订与稳定工程/UX 需求 ID。

- [完整产品定义](#完整产品定义)：范围、字段、格式、示例、约束和完整验收场景。
- [需求 ID 索引](#canonical-coverage-map)：用于 Slice / Task 追踪与验收；ID 不重新编号，含义仅能由明确授权的产品修订改变。
- [V2 Requirements](v2-requirements.md)：V2 的稳定扩展，保留冻结的 V1 基线。

需求 ID 表是完整定义的可引用索引，不能替代、缩小或扩大完整定义；未展开的细节以同文件的
完整定义为准。用户旅程由 [Product Experience](product-experience.md) 解释，
[Architecture](architecture.md) 区分 CURRENT / TARGET。当前开发范围与状态由
[SLICE.md](../SLICE.md)、[TASK.md](../TASK.md)、[Roadmap](roadmap.md) 和 [Progress](progress.md) 管理。

## Scope vocabulary

- **REQUIRED**：V1 产品或实现该产品要求所必需的工程约束。
- **OPTIONAL**：V1 允许提供，但不是所有部署或所有媒体项都必须启用的能力。
- **OUT OF V1**：完整产品定义明确放在后续阶段的产品能力。

“可配置”通常表示产品必须提供该配置能力，而不是 OPTIONAL；例如 Hash 模式可以由用户关闭，
但可选择的重复检测策略本身仍是 REQUIRED。实现是否完成不得改变 Scope。

## V2 requirements boundary

This file owns the complete V1 definition and stable `REQ-*`/`UX-*` IDs. Explicit user-approved
V2 amendments supersede only the listed meanings; all other scope and safety remain intact.
Detailed stable acceptance lives once in [V2 Requirements](v2-requirements.md); current Slice/Task
scope and delivery state remain in root contracts, [Roadmap](roadmap.md) and [Progress](progress.md).

| Authorized amendment | Superseded V1 meaning / retained boundary |
|---|---|
| 2026-10-13, `V2-AUTO-009` | Only automatic organization remains: remove scan-only/scan-and-plan values/aliases/defaults and exclusive branches, with no conversion or compatible executor. Unsupported values never grant organizing authority. |
| 2026-10-15, `V2-OPS-009–012` | Nine sibling Task/recovery lists and in-context exact summary followed by explicit selected execution/continuation replace mandatory independent Preview pages and standalone `REQ-SCAN-001` entry. Cross-Task recovery is selected; cross-Task bulk mutation stays deferred. Shared full planning/diagnostics and `UX-006` separate authority remain. |
| 2026-10-18, `V2-OPS-011` | Treat Scan as absent on first deployment, including definition modes: remove routes/aliases/help, work/schema/execution/recovery and dedicated retirement/history/migration layers. Ordinary authenticated not-found/argument/shared unsupported-type validation stops before discovery/admission/authority; no automatic conversion. Preserve shared filtering/real elapsed stability/planning, zero-mutation analysis (standalone Preview is separately superseded by V2-OPS-013), supported-work restart/pins/results/audit/permissions and completed/uncertain non-replay. No data/media clearing or V1-wide removal. |
| 2026-10-18, `V2-FILES-005/006` | Replace global `REQ-SCAN-004` indexing, `REQ-ORG-012` result sync and indexed `REQ-WEB-003`/`REQ-SAFE-009` exceptions with shared library/live-Storage CLI/Web lists and complete FileIndex exit. Browsing records no catalog/observations/work/authority or Provider/Hash/media effects; explicit work retains exact scoped evidence. No global stand-in, dual write, old FileID/API migration/compatibility or data clearing. `REQ-SCAN-006` source identity/safety remains. |
| 2026-10-18, `V2-OPS-013` | Retire the standalone Preview product with the same first-deployment standard as Scan: remove Web/API/CLI/Job/scheduled/definition-bound entry, execution/continuation, dedicated schema/composition and compatibility layers. Old inputs ordinarily fail before discovery/Provider/admission/authority, with no conversion, retirement page/410/guard, old-work migration/takeover/history or V1-parity obligation. `REQ-ORG-004/011` zero-mutation analysis, `REQ-SCHED-001` shared planning and `REQ-WEB-004` checks continue through organizing summaries/DryRun and shared Rules/configuration/authorization checks. Exact plans/pins/permissions/results and non-replay remain; no data/media clearing or unrelated Automation redesign. |
| 2026-10-24, `V2-UX-004`, `V2-OPS-014/015`, `V2-FILES-007` — TARGET / Slice46 | Make shared V2 actions readable; restrict Task Center to admitted organizing work and its recovery; remove center creation/global Worker/discovery/manual-operation blocks; start new file-selection-based manual organizing only from ResourceLibrary Files. Ordinary-file progress/results/recovery stay on the originating library page while durable Tasks, audit, pinned execution and safety remain. This narrows prior all-command center discoverability/entry, not task durability or command authority. Definition-bound Automation Run once and scheduled work retain their accepted semantics. |

These amendments define authorized scope; actual acceptance is recorded separately. Necessary
Slice43 Scan/index/standalone-Preview coupling cleanup was accepted within45, not the whole Automation
workspace. Separately resumed Slice43 is now PASS / CLOSED at reviewed implementation
`97316131946bdecc483b684f6e6f6ecb98c5594d`, preserving its original Base and the accepted45 amendments.
Accepted V1 facts
and original amendments remain in Git. `REQ-GEN-004` still requires fail-closed data integrity;
UX-first does not weaken safety or justify unnecessary CLI/internal-token ceremony.

Slice45 已整体验收为 PASS / CLOSED，交付上述 `V2-OPS-009–013` 与 `V2-FILES-005/006`。
该验收不改变冻结 V1 定义或原始接受事实；下面 CURRENT 修订及 Product Experience/Architecture
记录现行行为。Slice43 自动化工作区已单独整体验收为 PASS / CLOSED：原生定义生命周期、完整有界
运行一次、真实统计、只读执行记录及常驻进程实际采纳的引擎设置均为 CURRENT；不得恢复45已退役产品。

Slice46 的上述修订已获用户授权并选为 ACTIVE，但尚未实现或验收；稳定验收含义见
[V2 Requirements 的 TARGET 章节](v2-requirements.md#slice46-authorized-target--not-yet-delivered)。
用户随后明确将自动化详情“打开”/名称入口、保存后 Enabled 的旧版本误报两项修复纳入同一
Slice46，按既有 `V2-AUTO-001–003` 验收；仍是待交付修复，保留真实并发保护与授权边界。
以下 CURRENT 与历史 V1 定义保留接受基线；不得将新范围写成已交付，或以移除页面展示为由
取消耐久任务、文件操作恢复、权限、固定快照、审计和不确定效果非重放。

## Traceability and derivation rules

- `Canonical Source` 使用下方完整产品定义的章节标题；章节正文仍是最终解释来源。
- 标为 `Engineering derivation` 的条目不得增加新的用户能力，只能为 canonical 用户结果提供
  必需的一致性、安全、并发、隐私或恢复约束。
- 精确数据库版本、表名、函数名、内部 evidence key、字段顺序、样本数量上限、测试数量和特定
  反证方式属于实现或验收证据，不是稳定 Requirement。
- 当前 Slice 的局部延后不改变 V1 Scope；只有明确的 canonical 产品需求变更才能把能力归入 OUT OF V1。

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

The 2026-09-07 A architecture/roadmap reconciliation retains the 2026-09-02 scope decisions below,
keeps the closed manual-operations/file-lifecycle foundation and records the completed day-2
configuration/operations administration capability without weakening safety:

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

These decisions are represented by the closed Slices 26, 27, 28 and 29; current Slice status is
maintained in [`roadmap.md`](roadmap.md) and [`SLICE.md`](../SLICE.md). They do not create
implementation Tasks.

## General product requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-GEN-001 | REQUIRED | MediaFlow shall support the end-to-end chain from Storage and library configuration through scan, parse, recognition, metadata, naming, classification, plan, preview, execution, result and log. | §项目概述; §完整媒体处理流程; §最终核心原则 | A user can complete the promised chain without replacing a required stage with an internal-only shortcut. |
| REQ-GEN-002 | REQUIRED | Storage, libraries, scanning, parsing, recognition, metadata, naming, classification, organization, tasks and logging remain decoupled domain boundaries. | §核心设计原则; §推荐后端模块; §最终架构原则 | Reusing or replacing one policy/provider does not merge identities or move another stage's responsibility. |
| REQ-GEN-003 | REQUIRED | Recognition identity, media identity, name, destination and transfer operation are independent decisions. | §核心设计原则; §典型业务示例; §最终架构原则 | Each decision and its owning policy are independently visible and testable. |
| REQ-GEN-004 | REQUIRED | Failure must not create unknown data loss; safety takes precedence over convenience or automatic continuation. | §项目概述; §安全预览; §高风险文件操作保护 | Uncertain or destructive outcomes stop safely and expose known effects and a recovery action. |

## Operator experience requirements

These IDs remain stable references to the complete product definition below; Product Experience
supplies the journey-level interpretation.

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
| UX-009 | REQUIRED | Activation is an explicit backend authority boundary, atomic and fail-closed; a page-local Save may bundle the lifecycle steps without exposing separate activation controls. Failure preserves the previous Active snapshot and a correctable candidate. | §配置生命周期; §配置引用关系; §文件列表 | No partial activation or fallback to an untrusted competing authority is permitted, and ordinary page-local creation does not require internal lifecycle orchestration. |
| UX-010 | REQUIRED | Long-running work is pinned to the immutable configuration selected at its creation boundary. | Engineering derivation from §配置生命周期, §任务系统 and §定时任务 | Later activation cannot silently change queued or in-flight work. |

## Storage requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-STO-001 | REQUIRED | V1 supports Local, SMB, OpenList, Cloudflare R2 and S3-compatible Storage through one abstraction. | §存储管理; §第一阶段 MVP / Storage | Each required adapter can be configured and used without business-code backend branches. |
| REQ-STO-002 | REQUIRED | All list, stat, read and mutation operations pass through Storage ports; business code does not call filesystem, SMB, OpenList or object APIs directly. | §Storage 抽象; §OpenList 存储; §R2 / S3 存储 | Adapter substitution does not change domain or application behavior. |
| REQ-STO-003 | REQUIRED | Storage declares supported rename, move, copy, delete, hard-link and soft-link capabilities, and planning checks them before execution. | §Storage 抽象 | Unsupported operations fail explicitly unless an explicit policy authorizes a fallback. |
| REQ-STO-004 | REQUIRED | Storage configuration supports identity, name, type, enable/read-only state, root, timeout and concurrency plus create, edit, delete, copy, enable, disable and safe connection/read/write tests. | §存储配置; §配置操作 | The Web journey can manage and test a Storage without editing files or database rows. Storage has no notes field or notes search. |
| REQ-STO-005 | REQUIRED | Provider-specific settings and credentials are validated without disclosing secret values. | §本地存储; §SMB 存储; §OpenList 存储; §R2 / S3 存储; §安全要求 | Invalid paths/endpoints/auth fail clearly; credentials remain encrypted or referenced from an approved secret source. |
| REQ-STO-006 | REQUIRED | Domain plans identify locations by Storage ID plus Storage-relative path; host mount paths never become a remote logical path. | Engineering derivation from §资源库, §媒体库 and §最终路径生成 | The same plan remains portable across adapter implementations and cannot escape an adapter root. |
| REQ-STO-007 | REQUIRED | The Storage architecture permits additional adapters without changing business policy interfaces. | §存储管理 | Additional provider implementations are not V1 deliverables, but the extension boundary is present. |

## Library, scanning and index requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-LIB-001 | REQUIRED | ResourceLibrary binds a Storage and source path with enable state, scan mode/depth, include/exclude rules, stability policy and default recognition rules. | §资源库 | Discovery scope is explicit and does not contain naming, classification or mutation behavior. |
| REQ-LIB-002 | REQUIRED | MediaLibrary binds a destination Storage and root path, with enable state and directory-creation policy. | §媒体库 | Classification selects a configured destination; it does not invent a Storage or arbitrary root. |
| REQ-LIB-003 | REQUIRED | ResourceLibrary and MediaLibrary configuration is available through the final Web management journey and shares API validation/reference rules. | §最终管理界面; §配置管理; §第一阶段 MVP / UI | Users can configure both sides of the workflow without internal configuration knowledge. |
| REQ-LIB-004 | REQUIRED | Files provides a bounded ResourceLibrary creation journey whose final Save submits one complete candidate and lets the backend apply the current configuration validation and atomic activation flow. | §资源库; §文件列表; §配置管理 | A successful Save publishes a new immutable Active runtime; any validation, dependency, Storage-check, activation or runtime-load error rejects the Save and preserves the previous Active runtime. |
| REQ-LIB-005 | REQUIRED | Files and MediaLibrary provide focused page-local editing of an existing library's name, enable state, Storage binding and kind-specific relative root while keeping its stable ID immutable. | §资源库; §媒体库; §配置管理; §配置生命周期; §文件列表 | Edit is prefilled from an exact Active projection, preserves all fields outside the focused form, uses optimistic concurrency and the checked atomic-activation lifecycle, and never moves or deletes Storage contents; failure preserves the prior Active and correctable input. |
| REQ-SCAN-001 | REQUIRED | Scanning supports manual, full, incremental and scheduled modes and only discovers candidates. | §资源扫描; §增量扫描 | A scan never organizes or mutates media and proceeds to recognition/planning as separate stages. |
| REQ-SCAN-002 | REQUIRED | Filters cover extension, directory, name, size, glob and regex; extensions and ignore patterns are configurable. | §文件过滤; §默认忽略文件 | Temporary/download files and user exclusions are rejected predictably before processing. |
| REQ-SCAN-003 | REQUIRED | Stability checks exclude actively downloaded, copied or written files using configurable age, modification and stable-size rules. | §文件稳定性检测 | An unstable file cannot enter organization until it satisfies policy. |
| REQ-SCAN-004 | REQUIRED | V1 scanned files have a durable index and stable identity with New, Modified, Unchanged and Missing reconciliation; the explicit current V2 FileIndex-retirement amendment replaces this catalog obligation. | §数据索引; §增量扫描; §文件状态; V2-FILES-005/006 | V1 incremental meaning remains historical. Current V2 lists read live Storage without recording files; exact source/stability evidence is scoped to explicit work and incomplete discovery never authorizes execution. |
| REQ-SCAN-005 | REQUIRED | Scan concurrency, cancellation and per-library isolation are bounded. | Engineering derivation from §并发控制 and §任务操作 | Cancelling or failing one scope preserves already durable observations and does not mutate media. |
| REQ-SCAN-006 | REQUIRED | Discovery/stability evidence and media-processing outcomes are orthogonal, and an exact work source can be distinguished from a different file later appearing at the same Storage/path. | §数据索引; §文件状态; §整理结果记录; V2-FILES-006 | COPY/Skip may leave the physical source; MOVE may remove it. Task/Result outcomes remain independent. Prior results never permanently suppress a new occurrence at the same path. Current V2 uses explicit work-scoped evidence and live sources, with safe new organization/recovery rather than global catalog disposition or FileIndex Reprocess. |

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
| REQ-ORG-004 | REQUIRED | DryRun executes the complete decision/planning chain and shows source, parser, rule/type, metadata, policies, target, conflicts and warnings with zero mutation. | §Dry Run 整理预演; §策略测试工具 | Analysis and execution use the same production policy/planning semantics. V2-OPS-013 retains this capability in organizing DryRun/summaries and shared checks while retiring the standalone Preview product. |
| REQ-ORG-005 | REQUIRED | Automatic organization proceeds only after successful identity, naming, classification and target validation with no unresolved human conflict. | §自动整理 | Any unmet precondition routes the item to an explicit review/recovery state. |
| REQ-ORG-006 | REQUIRED | Duplicate detection considers target existence and may use provider/media/episode/size/hash evidence under a configurable no/fast/full hash policy. | §文件重复检测; §Hash 策略; §第一阶段 MVP / Organizer | Hash strength and uncertainty are visible; uncertainty never authorizes overwrite or delete. |
| REQ-ORG-007 | REQUIRED | Target conflicts support Skip, Overwrite, Rename and Manual outcomes. | §冲突策略 | Skip preserves source, Rename is deterministic, Manual waits, and Overwrite requires explicit configuration and confirmation. |
| REQ-ORG-008 | REQUIRED | Only OrganizerExecutor may perform Storage mutation and it executes only an explicitly authorized valid plan. | §安全预览; §最终核心原则 | All analysis stages and DryRun remain zero-mutation; execution effects are recorded. |
| REQ-ORG-009 | REQUIRED | Unsupported HardLink/SoftLink or transfer behavior fails unless a user-configured fallback explicitly permits another operation. | §HardLink / SoftLink; §高风险文件操作保护 | No silent fallback to Copy or Move is possible. |
| REQ-ORG-010 | REQUIRED | Optional source-directory cleanup is bounded, never removes unknown files and is disabled by default. | §空目录处理; §高风险文件操作保护 | Cleanup occurs only after verified eligible organization and cannot escape the source library boundary. |
| REQ-ORG-011 | REQUIRED | Zero-mutation organizing analysis records inspectable findings/plans without mandatory execution-blocker backlog; formal Conflict/Review/Recovery state belongs to explicit execution attempts. V2-OPS-013 supersedes the standalone Preview product form. | §安全预览; §Dry Run 整理预演; V2-OPS-013 | Same-page analysis/summaries and CLI organizing DryRun grant no execution authority and create no formal execution waiting/recovery backlog. Exact plans and evidence remain durable where needed; no old Preview history/migration compatibility is required by the prelaunch amendment. |
| REQ-ORG-012 | REQUIRED | Organize item outcomes remain durable and independent; V1 FileIndex synchronization is superseded in current V2 by the explicit complete-retirement amendment. | §整理结果记录; §文件状态; §文件列表; V2-FILES-006 | Persist Task/Result/step/effect and audit evidence without any FileIndex synchronization or repair. Failed persistence/display never authorizes replay of a completed or uncertain Storage mutation. |

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
| REQ-TASK-010 | REQUIRED | Admitted ResourceLibrary/MediaLibrary transfers execute by durable command/kind and immutable revision ID/digest independently of Worker startup Active; slow requests retain leases/fences and restart never replays completed or uncertain effects. | §已准入文件传输与 Worker 健康; Slice 39 authorized expansion | A Worker started before first activation executes later OpenList Move without restart; new B work uses B while admitted/in-flight A work stays A. Invalid pinned context or required secrets prevents new Storage mutation; missing current Active alone does not invalidate an intact admitted pin. |
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
| REQ-SCHED-001 | REQUIRED | ResourceLibrary Automation supports automatic organization as its sole mode under the explicit 2026-10-13 product amendment. | §自动整理 | No scan-only/scan-and-plan selection, aliases, conversion or compatible Automation execution path remains. Automatic execution satisfies identity, safety, conflict and authority gates. Shared discovery/analysis/planning remains; V2-OPS-011/013 retire standalone Scan/Preview products and preserve separate scoped authority. |
| REQ-SCHED-002 | REQUIRED | Schedules support periodic/Cron automatic organization, cache cleanup and log cleanup with configured timezone semantics; standalone scan scheduling is removed by the explicit 2026-10-13 Automation-mode amendment. | §定时任务 | The user manages applicable schedules through the same configuration and Web/API authority; cleanup remains outside the active Automation Slice. |
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
| REQ-CONFIG-005 | REQUIRED | Managed lifecycle is Draft to exact-version validation/test to explicit atomic activation to immutable runtime snapshot; a focused page-local Save may execute these backend steps as one user action. | §配置生命周期; §配置管理; §文件列表 | Editing never mutates Active; page-local Save success publishes only a fully validated Active snapshot, while failure keeps the prior Active and does not present the candidate as saved. |
| REQ-CONFIG-006 | REQUIRED | Configuration edits use optimistic concurrency and produce bounded, secret-free Before/After audit. | Engineering derivation from §配置引用关系 and §审计日志 | Stale writers cannot silently overwrite a newer Draft. |
| REQ-CONFIG-007 | REQUIRED | Validation and safe-test evidence binds to the exact revision and becomes stale after any edit. | Engineering derivation from §配置生命周期 and §策略测试工具 | Activation cannot reuse evidence from different content. |
| REQ-CONFIG-008 | REQUIRED | Runtime, API, workers, Jobs, Tasks and scheduled work resolve the same immutable Active or pinned snapshot identity and fail closed if unavailable or invalid. | Engineering derivation from §配置生命周期, §Provider 选择与切换, §Scheduler 责任边界 and §任务系统 | New activation affects only work created afterward; queued/in-flight work retains its pinned Provider and policy semantics, while revocable execution authority remains a separate live safety gate. |
| REQ-CONFIG-009 | REQUIRED | Validation and policy tests are zero-mutation; connectivity/read/write tests use the least authority necessary and clearly state their effects. | §策略测试工具; §存储配置; §安全预览 | A test cannot silently scan, organize or grant execution authority. |
| REQ-CONFIG-010 | REQUIRED | Credentials are stored encrypted or resolved through an approved external secret source and never returned in normal configuration payloads. | §TMDB 配置; §安全要求; §配置导入导出 | Copy, diff, export, audit and error paths remain secret-free. |
| REQ-CONFIG-011 | REQUIRED | System settings cover database/work/cache/log/export locations, default locale/timezone/log level and retention, concurrency and retry policy. | §系统设置 | Values are validated, permission-aware and consumed from the same configuration authority. |
| REQ-CONFIG-012 | REQUIRED | The primary Web configuration journey uses discoverable typed forms/cards; the general configuration surface exposes the Draft lifecycle, while a focused ResourceLibrary Save may bundle successor creation, validation and activation. Whole-document JSON remains an Advanced/import/export/support surface. | §配置生命周期; §配置操作; §配置导入导出; §最终管理界面; §文件列表 | Active remains immutable, ordinary object management does not feel JSON-only, and a page-local Save cannot publish an invalid or partially activated runtime. |

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
| REQ-DEPLOY-008 | REQUIRED | Expose separate liveness, registration/heartbeat/DB/schema readiness and command/pin work readiness; container health verifies actual Worker readiness, and transfer Web/API promptly explains waiting and safe recovery. | §已准入文件传输与 Worker 健康; REQ-TASK-009; REQ-DEPLOY-005 | Healthy never alone means a transfer can run. No/stale Worker, unsupported command, schema or pinned-context mismatch has a bounded reason, durable state and next action; reads create no work/provider calls. Docker proves startup before activation without Worker restart. |

## Web, API and security requirements

| ID | Scope | Requirement | Canonical Source | Acceptance Meaning |
|---|---|---|---|---|
| REQ-WEB-001 | REQUIRED | Web UI is the primary V1 management surface for setup, configuration, daily work, review, recovery and explicit execution. | §最终管理界面; §第一阶段 MVP / UI | Required journeys are discoverable and complete without CLI-only knowledge. |
| REQ-WEB-002 | REQUIRED | Dashboard shows bounded Storage/library, file, waiting/review, Task, success/failure and recent-error summaries. | §Dashboard | Counts link to the underlying actionable scope and do not expose secrets. |
| REQ-WEB-003 | REQUIRED | Files provide bounded live library-scoped entries and applicable actions; processing explanations/results remain on supported Task/Result surfaces. The current V2 amendment retires FileIndex catalog/detail and display feedback. | §文件列表; §搜索与筛选; §媒体详情; V2-FILES-005/006 | CLI and both library pages share live Storage reads without recording a file catalog. Users inspect processing outcomes through native task journeys; live membership never depends on recognition, metadata or historical results. |
| REQ-WEB-004 | REQUIRED | Web manages Storage, libraries, the V1 TMDB Provider reference/policy, RecognitionTypes/policies, Automation Task Definitions/schedules, Tasks, manual identity correction and zero-mutation analysis through organizing/Rules/configuration checks; V2-OPS-013 removes standalone Preview management. | §第一阶段 MVP / UI; §配置管理; §自动化对象与生命周期边界; V2-OPS-013 | Each management surface uses the same validation, permission, audit and safety contract as API; arbitrary Provider switching is not a V1 capability. |
| REQ-WEB-005 | REQUIRED | Task, review, conflict and recovery actions use explicit confirmation and never execute merely by viewing a page. | §任务操作; §人工元数据识别; §冲突策略; §人工整理 | Read paths are side-effect free and write actions show resulting durable state. |
| REQ-WEB-006 | REQUIRED | System/configuration status is bounded, permission-aware and secret-free, and distinguishes unavailable data from false success. | §Dashboard; §系统设置; §可操作错误与恢复 | Status views do not contact media services or expose paths/options beyond the user's authority. |
| REQ-WEB-007 | REQUIRED | **Files** browses bounded real directories/files from configured Storage and may show a bounded FileIndex business-status projection, while **FileIndex** presents MediaFlow discovery, processing disposition, history and available actions. | §存储管理; §数据索引; §文件列表; §媒体详情 | Users do not mistake the scan index for a file manager: Storage remains the physical listing/source authority, FileIndex feedback is display-only on Files, and both surfaces use Storage-relative identities without arbitrary host access. |
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
| REQ-SAFE-009 | REQUIRED | Current V2 retires the former FileIndex display/synchronization exceptions under the explicit amendment; source/plan/execution authority remains library/live-Storage and exact work evidence. | §文件列表; §安全预览; §整理结果记录; V2-FILES-005/006 | Browsing records no catalog; explicit work keeps confined exact sources, immutable pins and durable outcomes without an index or renamed stand-in. Result/display failure never replays media mutation. |

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

## 完整产品定义

以下完整定义从 Git `284faf1` 的根目录 V1.1 规格书迁入，仅调整标题层级、相对链接和冗余分隔，
并清理一处示例行末空白。
其范围、字段、示例、约束和验收含义保留；原有日期与 CURRENT 注记仍按其历史基线解释。
当前交付状态见 Product Experience / Architecture，迁移不宣告任何新能力完成。

### 影视媒体资源自动整理系统需求规格说明书

**文档版本：V1.1**
**项目类型：影视媒体资源管理 / 自动整理系统**

**需求基线日期：2026-08-26**
**V1 发布版本：1.0.0**

**V1 当前实现基线：截至 2026-09-08、Slice 29 Implementation Head `657f1a3697eec8e1537bee1335d45a06bec35c6f`，
Slice 26、27、28、29 均已由 A PASS / CLOSED。当前能力包括 Authenticated management-only fresh
bootstrap、首个 managed Draft、Local/SMB/OpenList/AWS S3/Cloudflare R2/通用 S3-compatible Storage
的引导配置与只读测试、Storage Browser/path selection、provider-neutral checked activation、真实
Storage Files 与 FileIndex 区分、current source lifecycle/disposition、统一 manual
Scan/Preview/Organize、Preview findings 与 execution blockers 分离、Conflict/Review 连续恢复、
Reprocess、processing Worker readiness/ownership、计划自动化与受限 unattended organization，以及
Slice 28 交付的 forms-first successor Draft/object lifecycle、完整 System Settings 对象旅程、
配置/结果版本化无 secret 导入导出、Webhook 定义/精确测试/逐项 delivery recovery，以及 Slice 29
交付的 Docker self-hosted release（不可变 image、四服务 Compose、production WSGI、/data 持久化、
健康/就绪、重启/升级恢复和 release-security 验证）。Provider switching、内置用户身份系统和完整
Secret Store 集成明确属于 V1.x / V2。该段只定义已发布 V1 基线；Slice 30–33 的 V2 实现事实由下方
治理元数据和 V2 权威文档单独记录。**

### **文档说明与状态定义**

本文档同时描述最终产品需求和当前实现基线。为避免把规划能力误认为已经交付，状态统一为：

```Plain Text
已完成：已有实现和自动化回归，可进入真实环境验证
部分完成：核心模型或适配器存在，但生产装配、持久化或交互尚不完整
未开始：仅保留需求，不属于当前已交付能力
```

### **用户体验优先原则**

MediaFlow 以用户体验为第一产品设计和验收原则。用户目标优先于内部实现；产品应提供最自然、
最直接、最低实际摩擦的完整旅程，并由系统在后台自动满足能够可靠判断的权限、安全、数据完整性
和架构约束。只有真正需要 human intent 的权限提升、意图歧义、mutation 结果不确定、人工冲突或
不可逆/破坏性边界，才应明显打断用户。

```Plain Text
User Goal
    ↓
最自然、最直接、最低摩擦的用户旅程
    ↓
系统自动满足权限 / 安全 / 数据完整性约束
    ↓
只有真正需要 Human Intent 时才打断用户
```

- Web UI 是普通 operator journey 的主要产品表面；CLI 保留用于 administration、debugging、
  migration、automation、support 和 emergency，但不能替代要求由 Web 完成的正常旅程。
- implementation-level token、grant、revision、checkpoint、claim 或 fencing identifier 默认不应
  成为普通用户步骤；后端机制不能反向定义操作员旅程。
- 系统不得要求用户重复输入已知信息、在没有新增 human intent 时重复确认，或根据后端 API
  协议自行推导下一步。错误必须提供有意义、可恢复的下一动作，而不是 raw technical exception。
- Preview 用于建立信心和解释预期结果，不是为了 ceremony 而设置的 ceremony。不可逆、破坏性、
  权限扩大或意图无法可靠判断的边界仍保留有意义的确认。
- RBAC、后端权威权限检查、明确 mutation intent、禁止静默覆盖/删除、有界作用域、审计、脱敏、
  Storage 路径约束、不可变快照 pinning、并发 fencing、不确定 mutation 禁止自动重放、只读/
  Preview 零 mutation 和 OrganizerExecutor-only mutation 均是不可削弱的 correctness / security /
  data-integrity invariants。UX-first 不表示降低安全性。

任何“部分完成”或“未开始”能力仍不得通过隐式默认、静默覆盖、静默删除或绕过 Storage 抽象实现。

### **当前发布线与 V2 开发状态（治理元数据）**

发布线见 [release.md](release.md)，大 Slice 顺序与状态见 [roadmap.md](roadmap.md)，
已审查的 Base/Head、日期、交付与延期见 [progress.md](progress.md)。当前范围、Task 状态和
下一步以 [SLICE.md](../SLICE.md)、[TASK.md](../TASK.md) 为准。V2 已交付用户旅程与架构事实分别见
[product-experience.md](product-experience.md)、[architecture.md](architecture.md)；
稳定 V2 要求见 [v2-requirements.md](v2-requirements.md)。本节不重复维护进度，不改变下方
冻结的 V1 产品需求或稳定 Requirement ID。

### **V1 最终范围与架构决策（A，2026-09-05 reconciliation）**

Slice 26、Slice 27、Slice 28 和 Slice 29 均已 PASS / CLOSED；状态与边界以
`docs/roadmap.md`、`docs/progress.md` 和 `SLICE.md` 为准：

```Plain Text
Slice 26 — Web-first Fresh Setup and Storage Completion（PASS / CLOSED）
    → Slice 27 — Manual Operations and File Lifecycle（PASS / CLOSED）
    → Slice 28 — Web-first Configuration and Operations Administration（PASS / CLOSED）
    → Slice 29 — Docker Production Self-hosted Release（PASS / CLOSED）
```

这不是 API、数据库、前端和 Dockerfile 的技术拆分，而是四个可以分别完成和验收的用户业务
能力。现有 Scanner、Parser、Recognition、Metadata core、Naming、Classification、OrganizePlan、
OrganizerExecutor、Task/TaskItem/Result、Processing Checkpoint、手工执行授权和 unattended
授权不因该规划重新设计。

V1 身份边界继续使用由部署环境提供的 API Principal Bearer Token 和现有 RBAC。Web 必须明确这是
API Token 认证，不得把它描述为内置用户名/密码登录、Cookie Session、OIDC 或反向代理身份系统。
内置用户管理、会话身份和 OIDC 属于 V1.x / V2。

V1 Metadata 继续使用现有 Provider 抽象和 TMDB production Provider。Provider switching、更多
production Provider 和任意 Provider 插件属于 V1.x / V2；TMDB 凭据或配置不可用时必须失败关闭，
不得静默切换到未授权 Provider。

现有签名 HTTPS Webhook Outbox 引擎保留为 V1 基础；Webhook 的 Web/API 配置、测试、状态和
死信恢复已由 Slice 28 完成。邮件、聊天专用 Provider 和媒体服务器刷新通知属于后续阶段。

环境变量引用加部署侧 secret injection 是 V1 的 Secret 边界。完整 Secret Store 和 Docker
Secrets 专用接入不属于 V1 blocker。

### **产品体验原则**

MediaFlow 的最终产品验收按完整用户旅程进行，而不是按内部模块数量进行。任何面向操作员的
需求必须同时定义并验证：用户目标、入口、可见状态、可用动作、成功结果、失败结果和恢复路径。
Domain、Repository、Application Service、数据库表或内部测试完成，不等于产品功能完成。

#### **最终管理界面**

- Web UI 是 V1 的主要管理界面，承担首次配置、日常整理、文件/媒体详情、人工修正、逐项恢复、
  配置测试与激活等最终用户旅程。
- CLI 用于管理、调试、自动化、迁移和紧急诊断；CLI 能力不能单独满足明确要求 Web 管理的功能。
- API 与 Web UI 必须复用同一 Application 行为、权限、校验、状态及安全边界；不得分别实现两套语义。

#### **可操作错误与恢复**

- 错误必须说明受影响对象或媒体项、失败阶段、已知持久状态、已发生的文件效果、是否可安全重试，
  以及明确的下一步恢复动作。
- “重试”不等于“恢复”。恢复必须从持久检查点和已知副作用出发；不确定的真实变更不得自动重放。
- 批处理必须保存每个 TaskItem 的独立状态、结果和恢复入口。一个项目的失败不得掩盖、覆盖或阻止
  其他项目的诊断与安全恢复。

#### **可解释决策**

影响 RecognitionType、MediaIdentity、名称、分类、目标路径、冲突和执行操作的自动决策，都必须
提供有界、脱敏、可审计的证据与理由。系统不得只显示最终结果或隐藏默认。

#### **配置生命周期**

Managed Configuration 的目标生命周期为：

```Plain Text
Draft
→ Validate / Test
→ Validated
→ Explicit Activate
→ Immutable Runtime Snapshot
→ Engine
```

- Draft 可编辑但不影响运行时。
- Validated 表示某个确定版本通过结构、引用和适用的安全测试；后续编辑会使其重新成为 Draft。
- Active 只能指已经显式激活、且正被运行时消费的不可变快照。界面必须显示版本/摘要和激活时间。
- 激活失败时旧 Active 保持有效，不允许部分激活。
- JSON 长期保留用于 bootstrap、导入导出、迁移和支持包；Managed Activation 实现后，JSON 不得与
  Managed Configuration 同时成为互相竞争的 Active source of truth。

#### **当前 Managed Configuration 产品边界（已实现）**

- 已实现 whole-document Draft/Validated/Active revision 的 SQLite 持久化、版本/digest、验证证据、
  原子激活和脱敏 Before/After 审计。
- 已接入受鉴权 API 与 Operator Web Configuration 视图，以及本地 `config status`、
  `config draft-import`、`config draft-validate` 和 `config activate` 管理命令。
- 新建 Task/Automation Job 记录其 configuration snapshot ID/digest；激活不启动扫描、Provider、
  Storage 或 Organizer，旧在途工作继续使用原快照。
- 运行时缺失/损坏场景会拒绝工作且不回退 JSON；F1 在完整 runtime 校验成功前不发布 identity，
  runtime-invalid Active 的重复 API 请求持续返回结构化 503 且不创建 Job。
- Active 缺失、损坏或运行时不兼容时，配置状态、整文档 Draft 替换、校验和显式恢复激活可从
  不可信工作流 JSON 中隔离；API 错误显示 last-known identity、持久状态、副作用、重试安全性和
  下一动作。F2 实现使每个新 API 请求只使用一个完整 old/new binding，新激活的上限与
  execute gate 与 Job pin 一致；这些行为已由当前代码和对应测试覆盖。
- `persistence.databasePath` 等 bootstrap 定位字段在 managed activation 中不可变；校验摘要在激活
  边界重新计算，导入/校验/编辑/激活状态与脱敏审计在同一事务中提交或回滚。
- 常驻 Scheduler 每次发出新 Job 时从同一 runtime revision 原子取得 schedule 内容、准入设置和
  identity；加载失败不发出 Job、不推进 due 状态。已持久化但未 pin 的旧工作在 managed authority
  建立后会拒绝继续。
- 当前 API/Web 已将配置状态、对象编辑、引用保护、精确 revision 预览、provider-neutral 目标只读预检、
  checked activation 和 immutable runtime binding 连接到同一 Application 行为；配置对象删除仅在
  仍有引用时安全阻止，合法未引用对象可删除。
- 当前 Active UI 身份来自实际用于运行时绑定的 Active revision。激活替换失败时保留原 Active 和
  候选 Draft；Active 缺失、损坏、schema 不兼容或运行时无效时，媒体工作 fail closed，不回退 JSON。
- Slice 26 已完成最小 bootstrap 首次设置、远程 Storage 引导配置/只读测试、Storage Browser、
  Storage-relative path selection 和 provider-neutral checked activation；Slice 28 已完成 System
  Settings 对象旅程、配置/结果导入导出和 Webhook 管理恢复。Docker production release 属于 Slice 29。

Files 页的 `+ 添加资源库` 是一个页面级的 ResourceLibrary 创建入口。它不要求操作员单独管理
Draft、Validate 和 Activate 三个内部步骤；最终点击 `保存` 后，后端以保存时的当前 Active
配置为基础，自动完成 ResourceLibrary 合并、完整配置校验、适用的 checked activation 和
运行时重新绑定。全部成功后才发布新的 immutable Active snapshot；任一字段、依赖、Storage
检查、激活或运行时加载错误都拒绝本次保存，并保留之前的 Active 配置不变。通用 Configuration
页面仍可保留显式的 Draft/Validate/Activate 管理旅程。

#### **V2 设置与空业务基线（CURRENT；Slice 40 PASS / CLOSED）**

首次激活允许业务区段完全为空。这取代此前必须先填写 Storage、库和策略的 V2 向导目标，以及
“无 Active 时各业务页保存 Draft”的提案；不改写已发布 V1 能力或 Slice 39 的历史验收。
设置页负责首个 Draft、显式激活、完整配置 JSON 查看/导出，以及其他页面未覆盖且后端明确支持
的高级配置，不要求用户在首次设置中填写媒体业务表单。

- 部署只提供应用配置文件、持久化位置和管理员 API 凭据。进入 V2 系统设置后，由管理员明确
  创建首个 Draft；进入、刷新、重连和返回恢复已有 Draft，不重复生成，不隐式激活。
- Draft/Active 的 Storage、ResourceLibrary、MediaLibrary、RecognitionType、规则、类型策略绑定、
  Metadata/Naming/Classification/Organize 策略、Automation 和 Webhook 可以全部没有业务对象。
  空业务图是合法配置状态，不是格式错误的文档，不填入开发示例或合成业务默认值。
- 用户可直接显式激活空 Draft。成功显示“配置已激活，媒体业务尚未配置”和各工作能力就绪状态。
  每个已填写对象仍通过结构、值、路径、唯一性和已声明依赖校验；非法引用不能借空区段绕过。
  仅对实际适用的启用库/Storage、Recognition 处理链和目标执行对应只读检查、策略测试或目标预检。
- Active 存在后，各业务页面沿用精确 Active successor、适用检查和原子激活；失败保留原 Active
  和可修正输入。Storage/库配置可先于媒体策略生效；不存在的能力报告未配置/未就绪，不能将
  “有 Active”或“库可浏览”误报为“可识别/整理”。提交和执行仍由后端按实际命令与作用域复核。
- JSON 默认查看运行时实际消费的 Active，明确标注 Active/Draft；无 Active 时显示 Draft 或无
  Draft，已有 Active 损坏时显示恢复状态，不能用 Draft、启动 JSON 或旧缓存冒充 Active。
  导出覆盖全部受支持的可移植受管配置且无秘密值，可保留安全环境变量引用，禁止 Token、密码、
  Secret 和 URL 凭据泄漏。数据库定位、API 身份/角色及实际 API Token 属于部署启动权威，不能
  通过受管编辑、激活或导出导入变更；可移植 JSON 排除这些权威，导入绑定接收环境。
- 高级编辑仅覆盖其他页面未支持且后端有实际消费者的配置，使用受限字段/schema 和相同 RBAC、
  校验、审计、并发与发布边界；不是任意 JSON 写入口。部署/重启才生效的项不得误报为已热生效。
- MediaFlow Worker 无 Active 或空 Active 时启动、注册并常驻，FileTransfer 消费能力保持存在。
  没有有效、已发布、获授权工作上下文时不处理媒体或变更 Storage；后续合法准入工作无需重启。
  保留精确 pin、摘要、租约、围栏和逐项恢复；旧准入任务不改绑新 Active，不自动重放不确定效果。
- Scheduler 无适用启用定义时常驻等待、不发 Job；配置失败时不使用旧缓存继续调度，不推进未发出
  的 occurrence。Notification Worker 无可用 Webhook 时不发送、不误领无目标投递；配置后无需
  重启，保留目标身份、投递租约及明确失败/不确定恢复，不静默转投。
- 健康分别显示进程存活、数据库/Schema/注册/心跳及按命令计算的工作就绪。等待首次配置是正常
  常驻状态，不能导致反复重启，也不能误报 Scheduler/通知工作就绪。Active/pin 缺失、损坏、
  摘要不匹配、数据库/Schema 故障和秘密缺失须分别说明原因，保持 fail closed 和可恢复状态。
- Compose 首次启动不要求媒体目录挂载；实际使用 Local Storage 时才要求显式安全挂载与权限。
  增加挂载仍是可能需重建容器的部署动作；仅配置激活不要求重启。配置页面和健康读取不启动
  媒体任务、发送通知或写入媒体。仅 OrganizerExecutor 可变更 Storage。

V2 设置必须可独立完成上述旅程，失败可保留输入并核实未知结果，返回业务页后刷新实际权威。
管理员/Viewer 的权限由后端决定。V1 `/ui` 保留至所有对应 V2 页面达到 parity 并独立通过 cutover
验收；本目标不要求同时迁移全部策略工作区或删除 V1。

#### **V2 整理规则工作区（CURRENT；Slice 41 PASS / CLOSED）**

`整理规则` 入口位于共享 V2 Shell，使用 `/ui-v2/rules`。概览、类型绑定、识别类型、识别规则、
元数据策略、命名策略、分类策略与整理策略均提供真实 Active 清单。各规则族默认全宽清单且不
打开表单；明确添加/复制操作打开候选抽屉，现有对象通过明确编辑操作进入可刷新、可深链的完整
编辑页。六张参考图仅定义结构与风格，其示例数据不是生产配置或验收 fixture。

普通编辑使用当前领域的 typed forms，包括嵌套识别条件、真实四策略绑定、Movie/TV 命名模板、
MediaLibrary 加安全相对路径的分类输出，以及整理操作、冲突、附件、重复检测、rollback 和源
清理设置。ID 在编辑时保持不变；启用/停用仅适用于真实支持该状态的对象，删除受引用保护且不
删除媒体、历史快照或 Result。一个识别类型只有一个启用绑定，C 复用 A 下游策略时身份仍为 C。

一次 `保存` 根据读取时的精确 Active 构造聚焦 successor，自动执行完整校验、适用证据、运行时
准备与 checked atomic activation。页面不要求另行保存 Draft、校验或激活；失败保留旧 Active、
可修正输入和已持久候选的明确状态，未知结果先读取实际 Active 核实，不自动重发。

明确测试/预览使用有界 non-Active 候选，提供识别策略、元数据、命名、分类和整理权限/目标解释。
结果逐项独立，编辑后显示过期。Offline 不调用 Provider；live 元数据访问仅在明确意图下通过
现有 TMDB 抽象执行。所有测试/预览零 Storage mutation、无执行授权；Save 和读/导航均不启动
媒体 Task、Job、自动化或通知。Settings 显示同一 Active 的规则族就绪信息并明确返回来源规则族。

当前旅程不要求原始整文档 JSON 或 V1 UI。V1 `/ui` 与既有 API/CLI 保留；Provider switching、
Review/Recovery 改造、Rules 页面媒体执行、批量导入/diff/rollback 和其他原 Contract 延后项均未
交付，不作为隐藏依赖。稳定 V1 产品需求及已发布基线不因上述 CURRENT 记录而改变。

#### **V2 操作与任务工作区（CURRENT；Slice 42 PASS / CLOSED）**

本节保留 A 于 2026-10-06 验收的基础事实；任务中心入口、独立 Preview 和 FileIndex 的
现行义务由下方 Slice45 CURRENT 修订替换，不改变冻结 V1 或此前 Slice 的验收事实。
该闭合 Slice 的原始参考图保留在其 Git 检查点；参考中的名称、数量、日期、路径、
海报、进度与剩余时间均不是实际数据或固定验收样本。稳定 V2 要求见 `V2-OPS-001` 至
`V2-OPS-008`；当前范围与验收以 `SLICE.md` 为准。

- 在共享 V2 Shell 的“操作与任务”提供统一列表、统计、搜索与状态/类型/时间筛选，选择任务后
  打开右侧“任务详情 / 操作记录”；默认无选中详情，窄屏、深链接和返回上下文完整。
- Job 表示准入/排队，Task 表示处理，TaskItem/Result 保留逐项结果。通过真实持久关联展示一次
  工作并去重，尚未生成 Task 的排队/失败仍可见；不同自动化运行与恢复续作保留独立关联历史。
  Job 完成不代表文件全部成功，不建立第二套任务或执行引擎。
- 搜索、过滤、统计和有界分页由后端统一计算。历史名称/范围来自准入证据或固定快照，不能随
  当前配置更名/删除而改变；旧记录缺证据时明确显示未知。阶段、完成度与成功率区分，未知总量
  不伪造百分比，等待/忽略/部分失败/不确定效果不计整理成功。
- “新建整理任务”复用资源库真实文件的单项/有界多选、精确 Preview 与明确执行意图，准入后
  返回选中任务查看进度。MediaLibrary 不成为新的整理源，FileIndex 不授权实际源文件。
- 暂停/取消使用后端当前允许动作并在安全边界协作生效，不声称在途调用立即中断或已完成效果
  回滚。已交付支持暂停的异步任务 Web 安全继续，复用 Worker、固定快照、检查点、锁/租约/围栏；
  消耗过的一次性授权、撤销的无人值守授权不能由继续动作重新获得。
- 在任务内完成识别类型、元数据、分类与冲突决策，以及单项/选定有界失败分析项恢复。保存决策
  不执行媒体；分析、精确预览与后续明确执行权限保持区分。批次逐项返回准入/拒绝原因，不重放
  成功、已忽略或效果不确定项。普通旅程不要求 V1/CLI 回退或复制内部 token。
- 操作记录以持久结果和逐步效果为准，关联有界日志/审计与无 secret JSON 导出。恢复链保留
  原项、决策、续作与新结果；读取/刷新/导出不创建任务、不调用 Provider、不变更 Storage。

Slice42 未交付全局 Review 收件箱；Slice45 另已交付五类跨任务问题列表。跨任务批量审核、任务历史删除/保留策略、无限整库手工整理、任意历史
Reprocess、自动化/通知页面重设计、通用回滚、V1 退役和不确定 mutation 自动重放仍未交付。
已退役的文件级重新识别、metadata rematch、re-plan 与 recognition retry-pending 接口不恢复。

#### **V2 任务中心重构（CURRENT；Slice45 PASS / CLOSED）**

用户确认 [任务中心最终方案](task-center-page-spec.md) 及其九张 `docs/pics/任务中心-标签名.png`
参考图。九个横向标签是全部任务、进行中、需要处理、已结束、识别恢复、元数据恢复、分类恢复、
冲突处理和失败恢复；各页独立查询真实授权总体，恢复页按任务聚合并显示本类型的待处理文件数。
同一任务可属于多个视图，不新建九套任务或恢复模型。

新建仅提供真实整理，在当前界面先显示来源、完整性、主文件/附件、就绪子集、操作、目标与
冲突/破坏性影响摘要，可展开逐项检查，然后明确确认精确范围。恢复流程也在当前处理界面
显示新摘要并确认继续；取消独立 Preview 产品页面与强制跳转，内部零变更分析、固定计划、
权限、版本和 OrganizerExecutor 边界不变。未就绪/未选择项状态独立，摘要本身不制造正式
执行阻塞待办，不把未知效果或未执行项算成功，不自动重放成功/忽略/不确定项。

Scan 产品按 2026-10-18 首次部署修订视为从未存在：独立入口及 scan-only/scan-and-plan 定义模式、
专属执行/重试/继续和退役兼容层删除，旧输入走普通 not-found/参数/不支持类型错误。必要共享
发现/过滤/真实稳定性/计划保留，原流程自行完成观察，不再要求先运行 Scan。
不建设旧 Scan/V1 parity、停止/接管、迁移或专用历史兼容；其他受支持工作的
历史意图、结果和审计保持。此修订不授权清空媒体或运行数据。用户随后将 FileIndex 完全退出
加入同一 Slice：CLI/两种库页共用只读 live Storage 列表，取消目录索引、专用接口/仓储/schema/
同步修复及全部运行依赖，见 V2-FILES-005/006 与退役设计；不建设旧索引生产兼容。
用户又将独立 Preview 产品完整退役纳入同一 Slice（V2-OPS-013/RO-8），方式与 Scan 相同：
独立 Web/API/CLI/Job/调度/执行/续跑、专用持久化和退役兼容层均按首次部署不存在处理。
旧输入普通报错，不自动转为整理；不建设旧 Preview/V1 parity、停止/接管、迁移或专用历史兼容。
整理内分析/固定计划/同页摘要、CLI organize 不执行模式及 Rules/配置/授权校验继续复用共享能力；
仅分析不制造正式执行待办或权限。范围见 [Preview 退役设计](preview-retirement-spec.md)。
零变更分析/DryRun 能力、Rules 测试与冻结 Slice43 的自动化业务工作区重设计不在删除范围。
这些明确授权的产品修订已通过整 Slice 验收；上方 Slice42 原始接受事实和下方冻结 V1 定义
不被倒改，未选择的能力不因本次关闭而被宣称交付。

#### **安全预览与直接文件命令**

媒体整理、目标路径计算、隐含覆盖以及其他需要解释复杂业务计划的操作，在变更前必须提供可解释
Preview/DryRun。Files 中边界明确的常用文件命令不强制套用完整整理 Preview、Recognition、
Metadata、Naming、Classification 或 execution-token ceremony：新建文件夹/文本文件、重命名、
复制、移动、删除、保存受支持文本、上传和下载，以明确选择的 ResourceLibrary 相对路径、目标和一次直接操作
意图提交。有界多选/目录操作显示轻量项目数/大小/目标或传输影响，不转化为媒体整理 Preview。
删除仍需一次有意义的确认；Replace 和文本 Save 是明确覆盖意图。ResourceLibrary 根、无界递归、
静默覆盖、隐式操作降级和任意二进制/音视频/图片内容编辑不属于该直接命令边界。

安全与数据完整性约束始终成立，但系统应以最低实际操作摩擦自动执行能够可靠判断的校验；后端
必须重新执行 RBAC、Active ResourceLibrary/Storage 绑定、路径 confinement、provider capability、
stale/conflict 校验和审计，默认不覆盖、不静默删除、不隐式降级，且只有 OrganizerExecutor 可执行
Storage mutation。普通用户无需理解或手工传递内部 token、grant、revision 或 checkpoint 才能
完成最终要求由 Web 提供的正常旅程；不可逆、破坏性、权限扩大或意图不明确的边界仍要求有意义
的确认。

当前 V2 按 V2-OPS-013 取消独立 Preview 产品；下文 V1 的 Preview/DryRun 描述保留分析和
权限分离含义，由整理自身分析/计划摘要及共享检查承接，不再要求独立创建/调度/历史服务。

Preview/DryRun 的产品语义是分析“会发生什么”。新 Preview 可以持久保存 findings、warnings 和
inspectable plan，但不得仅因分析发现 Recognition、Metadata、Classification 或 Conflict 问题就
制造用户必须处理的正式 WAITING_CONFIRM/Review backlog。只有明确 Organize 请求遇到真实 blocker
时，才进入 Attention/Conflict/Review/Recovery；保存 decision 本身不执行文件操作，必须经过
重新分析和显式 continuation authority 才能继续原 Organize。

V1 最终导航中，`Files` 浏览已配置 Storage 的真实目录/文件，`FileIndex` 展示 MediaFlow 扫描、
索引、识别、整理和恢复状态。Files 页面可以读取 FileIndex 提供的有界识别结果和业务状态
反馈，并在直接文件命令成功后进行展示状态 reconciliation，但 FileIndex 不得成为实时物理文件
列表、路径校验、直接命令 admission、Preview source identity 或执行权限来源。
`scan/discovery state` 与 `processing disposition` 正交；COPY 成功或 Conflict Skip 后源仍可保持
READY，而业务状态分别为 Organized 或 Skipped。同一路径后来出现的新文件必须可通过 source
occurrence/fingerprint 与旧结果区分，并保留显式 Reprocess。

每个 Organize item 进入终态并持久化 Result 后，系统自动把已知的整理结果/processing disposition
同步到 FileIndex。同步失败必须作为独立的索引同步错误保留，不能把已完成或不确定的 Storage
mutation 自动重放。除业务状态只读反馈和 Organize 终态同步外，Files 页浏览、选择、资源库
配置、Preview 和其他页面功能不得新增 FileIndex 依赖。跨 Storage Move 必须明确显示为
Copy→校验→删除源；校验失败不得删除源，部分结果必须逐项可见且不得自动重放。

规范化用户旅程及验收解释见 `docs/product-experience.md`。上述基线及下列 Slice 44 增量为已交付
CURRENT；未明确列出的后续目标不得描述为已实现。

#### **V2 已交付增量 — 现有页面改进（Slice 44）**

- ResourceLibrary / MediaLibrary 普通维护采用同一行为与各自库类型权限；指纹可选，但服务端已观察
  的指纹仍绑定。Rename / Delete 元数据校验不读取选中文件内容；批量/长 Delete 持久化独立结果，
  未知变更不自动重放。文本编辑保留有界内容摘要；跨 Storage Move 仍为 Copy→摘要验证→Delete。
- Rules 八区导航、当前区搜索、完整列表、显式 Add/copy 抽屉和专用 Edit 表单保留一次 checked Save。
  默认测试仅分析当前候选及必要依赖；Overview 单独完整流程检查。离线局部测试零 Provider / Storage
  I/O，结果不替代全图发布、完整规划或执行授权。
- 新分类使用 MediaLibrary + 安全 `path`，不追加库显示名/ID；旧 `library/path` 显式转换并保留原路径，
  历史快照、Preview、Task 和授权继续沿用其原语义。
- 两类库的 list/grid 长名称、空白和路径身份保持精确；完整名称可查看，面包屑有界滚动、工具栏重排。
- ResourceLibrary 文件夹/混合选择经有界后台发现、冻结主文件清单、既有 exact Preview 和单独确认执行；
  主文件/Trailer 关联、真实稳定观察、隔离读错、控制/归属 fence 和一次原子 Freeze 已交付。
  仍保留 100 主文件界限；特殊中断不能证明续跑时安全停止并显式新发现。任意崩溃/控制组合、旧记录和
  激活变化下的无缝恢复仍延期，不能猜新根/重新 pin 或自动重放。MediaLibrary Organize、Upload/Download、
  冻结的 Slice 43 和未选择页面不在此次交付范围。

这些事实不重写已发布 V1 基线或稳定 REQ/UX/V2 ID；范围、验证及延期索引见 `docs/progress.md`。

### **V1 当前实现基线（已发布）**

交付、部分完成和延期的历史明细保留于
`865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/requirements.md`，不在需求定义内重复进度台账。
现行发布事实见 [Release](release.md)，接受的 Base/Head 与范围见 [Progress](progress.md)，
完整用户旅程见 [Product Experience](product-experience.md)。下方产品要求、格式、字段、边界与
验收场景仍是完整定义；实现状态不能削弱需求，V2 仅按上方明确修订替换指定含义。

#### **当前发布验收边界**

截至 2026-08-23，可复现的有界发布 profile 为 PASS：

```Plain Text
Local / Samba / OpenList / MinIO
→ 生产 Storage Adapter
→ OrganizerExecutor
→ 128 个确定性批次对象
→ 128 MiB 流式对象与 SHA-256 校验
→ 确定性源流中断
→ MOVE 保源与目标状态检查
→ 新的显式重试
→ 白名单清理
```

该 PASS 只覆盖上述明确 profile。下列能力不得从中推断：

- AWS S3 或 Cloudflare R2 服务专项兼容性。
- 第三方 OpenList driver 行为。
- SMB/OpenList 远端原子发布；验收中 SMB 中断会暴露可识别的部分目标。
- 多小时 soak、服务进程终止、主机断电或分布式事务一致性。
- 生产 Hash 内容校验、自动清理部分目标、自动重试或 Rollback。

真实验收记录以 `docs/storage-acceptance.md` 为准；fake/mock 仅作为 UNIT PASS，不得替代
隔离真实服务证据。

#### **V1 Docker self-hosted 发布能力（CURRENT；Slice 29 PASS / CLOSED）**

最终发布采用一个不可变 MediaFlow image，由 Docker Compose 运行独立的 `api`、`worker`、
`scheduler` 和 `notification-worker` service；用户只需执行 `docker compose up -d`，内部仍
保持进程故障隔离，不把四个长期进程耦合进一个 Python event loop 或 shell supervisor。

`mediaflow api serve` 使用 `wsgiref.simple_server`，只属于 trusted loopback/development 边界；
生产 Compose 使用 `mediaflow api serve-production` 和 Waitress WSGI server，并已验证 request limit、
graceful shutdown、host binding 和 proxy-header trust 边界。
TLS、证书、反向代理和 direct Internet exposure policy 属于显式 deployment boundary，MediaFlow
不得静默兼任这些职责。

容器持久数据统一放在本地 filesystem volume 的 `/data`：

```Plain Text
/data/mediaflow.sqlite3
/data/history.jsonl
/data/logs/
/data/exports/
/data/backups/
```

SQLite、FileIndex、Managed Configuration、Automation Definition/grant/Job、Task/TaskItem/Result、
notification state、security/operation history 和 migration marker 均进入 `/data`。媒体目录是
独立的显式 bind mount；Local `rootPath` 表示容器内可见的绝对路径，例如宿主机
`/mnt/downloads` 映射为 `/media/downloads` 后，配置使用 `/media/downloads`。不支持直接把 SQLite
放在 SMB、NFS、OpenList、S3/R2，也不支持挂载宿主机 `/`、Docker socket 或任意未映射路径。

Liveness、readiness 和 business/runtime health 必须分开；healthcheck 不得扫描 Storage、调用
Provider、创建 Job/Task、发通知或执行媒体 mutation。重启不得自动重放 uncertain mutation，旧
Worker 不得覆盖后继 owner；升级必须经过 backup/preflight、schema migration 和 migration failure
的 fail-closed/recovery 路径。

#### **当前配置路径语义**

```Plain Text
Storage.rootPath
    Adapter 拥有的根；Local 可为绝对路径，OpenList 为服务端 API 根路径
ResourceLibrary.storagePath
    相对 Storage 根的扫描路径；这是无路径扫描真正使用的字段
ResourceLibrary.displayRootPath（可选）
    显式传入主机路径时用于关联 ResourceLibrary；旧 rootPath 作为兼容别名
MediaLibrary.rootPath
    相对目标 Storage 根的目标路径
```

OrganizePlan 中源和目标都必须保存：

```Plain Text
StorageID + Storage-relative Path
```

不得把主机挂载路径嵌入远端 Storage 的逻辑路径。

### **项目概述**

#### **1\.1 项目目标**

开发一套影视媒体资源自动整理系统，对本地、SMB、OpenList、R2/S3 等不同存储中的影视资源进行统一管理。

系统负责完成：

```Plain Text
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

### **核心设计原则**

整个系统按照以下能力进行解耦：

```Plain Text
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

```Plain Text
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

##### **识别规则**

只负责：

这个资源属于什么识别类型。

例如：

```Plain Text
文件 → Movie
```

##### **元数据服务**

负责：

这个资源具体是哪一部电影、电视剧、哪一季、哪一集。

例如：

```Plain Text
The.Matrix.1999.mkv
↓
TMDB
↓
The Matrix
1999
TMDB ID = xxxx
```

##### **命名规则**

只负责：

最终叫什么名字。

例如：

```Plain Text
The.Matrix.1999.1080p.mkv
↓
The Matrix (1999).mkv
```

##### **分类规则**

只负责：

最终放到哪里。

例如：

```Plain Text
/Media/Movies/
```

##### **整理规则**

只负责：

文件如何从资源库到达媒体库。

例如：

```Plain Text
Move
Copy
HardLink
SoftLink
```

### **典型业务示例**

系统存在：

```Plain Text
识别类型 Movie
识别类型 TV
识别类型 SP
```

配置：

```Plain Text
Movie
→ Movie 元数据策略
→ Movie 命名规则
→ Movie 分类规则
→ Move
TV
→ TV 元数据策略
→ TV 命名规则
→ TV 分类规则
→ Move
SP
→ SP 元数据策略
→ Movie 命名规则
→ Movie 分类规则
→ Move
```

注意：

```Plain Text
SP 仍然是 SP
```

只是 SP 在整理阶段复用了 Movie 的：

```Plain Text
命名规则
+
分类规则
```

#### **3\.1 Movie 类型示例**

源文件：

```Plain Text
/Downloads/Movie/The.Matrix.1999.1080p.BluRay.mkv
```

识别：

```Plain Text
RecognitionType = Movie
```

元数据识别：

```Plain Text
Title = The Matrix
Year = 1999
```

类型策略：

```Plain Text
Movie
→ Movie命名规则
→ Movie分类规则
```

最终：

```Plain Text
/Media/Movie/The Matrix (1999)/The Matrix (1999).mkv
```

#### **3\.2 TV 类型示例**

源文件：

```Plain Text
/Downloads/TV/The.Last.of.Us.S01E03.2023.mkv
```

识别：

```Plain Text
RecognitionType = TV
```

元数据：

```Plain Text
Title = The Last of Us
Season = 1
Episode = 3
```

策略：

```Plain Text
TV
→ TV命名规则
→ TV分类规则
```

最终：

```Plain Text
/Media/B/The Last of Us/
└── Season 01/
    └── The Last of Us - S01E03.mkv
```

#### **3\.3 SP 使用 Movie 规则示例**

源文件：

```Plain Text
/Downloads/SP/Special.C.2025.mkv
```

识别：

```Plain Text
RecognitionType = SP
```

SP 类型策略：

```Plain Text
SP
→ Movie命名规则
→ Movie分类规则
```

最终：

```Plain Text
/Media/Movie/Special C (2025)/Special C (2025).mkv
```

最终媒体库：

```Plain Text
/Media/
├── Movie/
│   ├── The Matrix (1999)/
│   │   └── The Matrix (1999).mkv
│   │
│   └── Special C (2025)/
│       └── Special C (2025).mkv
│
└── TV/
    └── The Last of Us/
        └── Season 01/
            └── The Last of Us - S01E03.mkv
```

### **存储管理**

#### **4\.1 功能要求**

系统支持配置多个存储。

首期支持：

```Plain Text
Local
SMB
OpenList
Cloudflare R2
S3 Compatible
```

架构必须允许后续增加：

```Plain Text
WebDAV
SFTP
FTP
OSS
COS
其他云存储
```

### **存储配置**

每个存储拥有：

```Plain Text
Storage ID
名称
类型
启用状态
只读状态
根目录
超时时间
并发限制
```

存储配置不包含备注字段，也不提供备注的输入、展示、保存或搜索。存储管理参考图中的
“搜索存储、路径或备注...”为错误文案，应使用“搜索存储、路径...”。

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

### **本地存储**

配置：

```Plain Text
名称
Root Path
```

例如：

```Plain Text
/data/download
/data/media
```

系统启动或保存配置时可以检测：

```Plain Text
路径是否存在
是否可读取
是否可写入
```

同时由 Storage Adapter 声明其支持的文件操作能力。

### **SMB 存储**

配置：

```Plain Text
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

```Plain Text
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

### **OpenList 存储**

配置：

```Plain Text
名称
OpenList URL
认证信息
Root Path
请求超时
```

通过独立 Storage Adapter 实现。

整理模块不得直接依赖 OpenList API。

Root Path 留空或填写 `/` 均表示 OpenList 服务端根目录，具体子目录遵循该适配器的路径规则。
Web 新增、编辑、保存后的列表回读和详情必须接受这种合法空根路径，并显示为“提供商根目录”，
不能因空字符串导致整个存储清单不可用，也不能悄悄丢弃该存储。这个约定不允许 Local 根路径
留空或访问宿主机 `/`，也不放宽其他提供商的路径校验。

### **R2 / S3 存储**

配置：

```Plain Text
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

```Plain Text
Move
```

如果目标后端不存在直接移动能力，适配器可以按照对应存储能力组合适当操作实现。

上层整理引擎不关心底层实现细节。

### **Storage 抽象**

建议统一接口：

```Plain Text
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

```Plain Text
CanRename
CanMove
CanCopy
CanDelete
CanHardLink
CanSoftLink
```

整理计划生成前必须进行能力检查。

### **资源库**

#### **11\.1 定义**

资源库表示：

系统从哪里发现需要整理的媒体。

资源库必须绑定：

```Plain Text
Storage
+
Path
```

例如：

```Plain Text
资源库：下载完成
Storage：NAS
Path：/Downloads
```

#### **11\.2 资源库配置**

配置：

```Plain Text
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

Files 页的 `+ 添加资源库` 使用上述 ResourceLibrary 定义，而不是创建 MediaLibrary。页面级流程
为：

```Plain Text
基本信息
→ 存储位置
→ 确认
→ 保存
→ 后端根据当前 Active 配置执行校验与激活
→ 新 ResourceLibrary 进入 Active runtime
```

`保存` 是一个完整的后端应用操作。成功时新资源库可立即被 Files 页选择；失败时拒绝保存、
保留之前的 Active runtime，并返回具体的可恢复错误。操作员不需要复制 revision、digest、
token 或其他内部执行标识。

### **资源扫描**

支持：

```Plain Text
手动扫描
全量扫描
增量扫描
定时扫描
```

扫描发现媒体候选文件以后，不直接执行整理。

必须先进入：

```Plain Text
识别
→ 生成整理计划
→ 整理
```

### **文件过滤**

支持：

```Plain Text
扩展名
目录
文件名称
文件大小
Glob
正则表达式
```

可以配置视频扩展名：

```Plain Text
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

#### **13\.1 默认忽略文件**

例如：

```Plain Text
*.tmp
*.part
*.download
*.!qB
```

允许用户配置。

### **文件稳定性检测**

防止处理正在：

```Plain Text
下载
复制
写入
```

的文件。

支持：

```Plain Text
最小文件年龄
最后更新时间阈值
文件大小稳定时间
```

例如：

```Plain Text
10分钟内文件大小没有变化
AND
最后修改超过5分钟
↓
允许进入识别
```

### **媒体文件解析**

系统首先对文件进行本地解析。

信息来源：

```Plain Text
文件名称
扩展名
父目录
上级目录
完整路径
NFO
已有整理信息
```

### **文件名解析**

需要解析：

```Plain Text
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

```Plain Text
The.Last.of.Us.S01E03.2023.2160p.WEB-DL.H265.mkv
```

解析：

```Plain Text
TitleCandidate = The Last of Us
Year = 2023
Season = 1
Episode = 3
ResolutionTag = 2160p
SourceTag = WEB-DL
VideoCodecTag = H265
```

这些技术信息均属于：

文件名标签。

系统不需要检查视频内部实际媒体流参数。

### **季集识别**

支持常见形式：

```Plain Text
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

```Plain Text
S01E01E02
```

转换：

```Plain Text
Season = 1
Episodes = [1, 2]
```

### **识别规则**

#### **18\.1 定义**

识别规则负责：

根据文件及目录特征判断资源属于哪个 RecognitionType。

识别规则本身不负责命名、分类和移动。

#### **18\.2 配置**

每个识别规则包含：

```Plain Text
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

#### **18\.3 条件关系**

支持：

```Plain Text
AND
OR
NOT
```

例如：

```Plain Text
Path Contains "/SP/"
AND
Extension IN ["mkv", "mp4"]
↓
RecognitionType = SP
```

### **识别规则优先级**

规则按照：

```Plain Text
Priority DESC
```

执行。

支持：

```Plain Text
命中后停止
命中后继续
```

如果存在多个候选类型，可使用：

```Plain Text
规则优先级
+
匹配分数
```

确定最终 RecognitionType。

### **识别类型**

系统允许创建任意识别类型。

例如：

```Plain Text
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

将一类资源绑定到特定的后续处理策略。

### **识别类型策略**

#### **21\.1 定义**

Recognition Type Policy 是系统核心配置。

负责定义：

一个文件被判断为某种识别类型后，接下来应该如何进行元数据识别、命名、分类和整理。

#### **21\.2 配置**

每个识别类型策略包含：

```Plain Text
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

#### **21\.3 示例**

```Plain Text
RecognitionType = Movie
MetadataPolicy = Movie-TMDB
NamingPolicy = Naming-Movie
ClassificationPolicy = Classification-Movie
OrganizePolicy = Move
```

B：

```Plain Text
RecognitionType = TV
MetadataPolicy = TV-TMDB
NamingPolicy = Naming-TV
ClassificationPolicy = Classification-TV
OrganizePolicy = Move
```

C：

```Plain Text
RecognitionType = SP
MetadataPolicy = Movie-TMDB
NamingPolicy = Naming-Movie
ClassificationPolicy = Classification-Movie
OrganizePolicy = Move
```

因此：

```Plain Text
Movie → Movie + Movie
TV → TV + TV
SP → Movie  + Movie
```

完全成立。

### **元数据服务**

#### **22\.1 功能定位**

Metadata Provider 用于：

根据本地解析得到的标题、年份、季、集等信息，识别对应的影视作品并补全标准元数据。

首期支持：

```Plain Text
TMDB
```

架构允许增加：

```Plain Text
其他公开影视元数据Provider
自定义Provider
```

### **元数据 Provider 抽象**

统一定义：

```Plain Text
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

### **TMDB 配置**

支持：

```Plain Text
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

TMDB 当前的应用级 API 认证支持 v3 `api_key` 或 Bearer Token；官方文档将 Bearer Token 作为默认认证方式之一。\([The Movie Database \(TMDB\)](https://developer.themoviedb.org/docs/authentication-application?utm_source=chatgpt.com)\)

敏感认证信息必须：

```Plain Text
加密保存
接口脱敏
日志脱敏
```

### **元数据策略**

元数据服务本身和元数据策略分离。

例如系统配置一个：

```Plain Text
TMDB Provider
```

然后可以建立：

```Plain Text
Movie-TMDB
TV-TMDB
Anime-TMDB
```

三个不同 Metadata Policy。

#### **25\.1 Metadata Policy 配置**

```Plain Text
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

#### **25.2 Provider 选择与切换（V1 scope decision）**

TMDB 是 V1 必须交付的生产 Metadata Provider。V1 保留 Provider 抽象和 MetadataPolicy
对 Provider 的间接引用，但不交付 Provider switching，也不要求为证明抽象而同时交付第二个
生产 Provider。A 于 2026-09-02 决定将 Provider switching、更多 production Provider 和任意
Provider 插件移入 V1.x / V2；这是一项明确的范围收窄，不是把未完成能力假设为已完成。

选择关系为：

```Plain Text
RecognitionType
    ↓
RecognitionTypePolicy
    ↓
MetadataPolicy
    ↓
MetadataProvider
```

MetadataPolicy 必须引用当前配置的 TMDB Provider。RecognitionTypePolicy 只通过
MetadataPolicy 间接选择 Metadata 行为，不直接硬编码 Provider。不同 RecognitionType 仍可
通过各自的 RecognitionTypePolicy 使用不同的 MetadataPolicy；V1 的这些策略最终解析到
TMDB，但保留未来 Provider 扩展所需的架构边界。

TMDB MetadataPolicy 修改必须经过正常的：

```Plain Text
Draft
  → Validate / Test
  → Activate
```

已创建的 Job / Task 继续使用创建时固定的不可变配置快照。TMDB 配置不可用、引用失效或
凭据失效时必须安全失败，不得默认切换到未授权的 Provider。未来重新纳入 Provider switching
时，仍必须遵守同一 Snapshot pinning 和 fail-closed 规则。

### **TMDB 电影识别**

文件：

```Plain Text
The.Matrix.1999.1080p.BluRay.mkv
```

本地解析：

```Plain Text
TitleCandidate = The Matrix
Year = 1999
```

Metadata Policy：

```Plain Text
Movie-TMDB
```

查询：

```Plain Text
TMDB Movie Search
```

TMDB 官方提供独立的电影文本搜索接口，搜索可以使用标题，并可结合上映年份等条件缩小候选结果。\(The Movie Database \(TMDB\)\)

返回候选后进入：

```Plain Text
Candidate Matcher
```

而不是直接选择第一条结果。

### **TMDB 电视剧识别**

例如：

```Plain Text
The.Last.of.Us.S01E03.2023.mkv
```

本地解析：

```Plain Text
TitleCandidate = The Last of Us
Year = 2023
Season = 1
Episode = 3
```

查询：

```Plain Text
TV Search
↓
TV Details
↓
Season
↓
Episode
```

TMDB 当前提供独立的 TV Search 以及 TV Series Details 接口，因此电影和电视剧应当在 Provider 层作为不同查询类型处理。\(The Movie Database \(TMDB\)\)

### **外部 ID 识别**

如果文件名、NFO 或已有数据库中存在：

```Plain Text
TMDB ID
IMDb ID
TVDB ID
其他支持的外部ID
```

应优先尝试 ID 定位。

TMDB 的 Find API 支持通过已有外部标识符寻找对应对象，因此 Metadata Provider 应保留 `FindByExternalId()` 能力。\([The Movie Database \(TMDB\)](https://developer.themoviedb.org/reference/find-by-id?utm_source=chatgpt.com)\)

### **元数据候选评分**

搜索结果不得默认直接使用第一项。

每一个结果需要评分。

评分因素：

```Plain Text
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

#### **29\.1 默认阈值**

例如：

```Plain Text
Score >= 90
→ 自动确认
Score 70 - 89
→ 待人工确认
Score < 70
→ 识别失败
```

阈值允许配置。

### **元数据识别结果**

统一转换为内部：

```Plain Text
MediaIdentity
```

建议结构：

```Plain Text
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

### **人工元数据识别**

当前实现：Task 跟踪的 Metadata NOT_FOUND 项持久进入
WAITING_METADATA_CORRECTION，可修正查询词、年份、Movie/TV，或输入当前配置 Provider 的
直接 ID；决策审计后必须显式 resume 才会通过真实 MetadataProvider 重试。不得切换到任意
Provider 或注入任意 MediaIdentity，RecognitionType C 始终保持 C。

当自动识别失败时支持：

```Plain Text
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

```Plain Text
MediaIdentity
```

然后继续正常整理流程。

### **元数据缓存**

Metadata 请求必须支持缓存。

缓存类型：

```Plain Text
Search Result
Movie Details
TV Details
Season
Episode
External ID
Images
```

配置：

```Plain Text
缓存有效期
自动刷新
强制刷新
清除缓存
```

防止资源库每次扫描都重新请求元数据网站。

### **Provider 请求控制**

必须支持：

```Plain Text
最大并发
请求节流
Timeout
Retry
指数退避
Proxy
429处理
```

TMDB 官方目前说明旧的固定限流机制已经停用，但仍存在保护服务的上限，并要求客户端正确处理 `429`；因此系统不能把某个固定 QPS 数值写死，应通过可配置节流和 `429` 重试机制实现。\([The Movie Database \(TMDB\)](https://developer.themoviedb.org/docs/rate-limiting?utm_source=chatgpt.com)\)

### **命名规则**

#### **34\.1 定义**

Naming Policy 只负责：

根据已经确定的 MediaIdentity 生成目录名和文件名。

命名规则独立存在，可以被多个 RecognitionType 复用。

### **命名规则配置**

包含：

```Plain Text
NamingPolicy ID
名称
目录模板
文件模板
字符清理规则
缺失变量处理
启用状态
```

### **命名变量**

基础变量：

```Plain Text
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

```Plain Text
resolution
source
video_codec
audio
hdr
version
release_group
```

来源于文件名及路径解析结果。

### **电影命名**

规则：

```Plain Text
目录：
{title} ({year})
文件：
{title} ({year}).{ext}
```

结果：

```Plain Text
The Matrix (1999)/
└── The Matrix (1999).mkv
```

也可以：

```Plain Text
{title} ({year}) [tmdbid={provider_id}]
```

产生：

```Plain Text
The Matrix (1999) [tmdbid=xxx]/
```

### **剧集命名**

目录：

```Plain Text
{title} ({year})/Season {season:02}
```

文件：

```Plain Text
{title} - S{season:02}E{episode:02} - {episode_title}.{ext}
```

结果：

```Plain Text
The Last of Us (2023)/
└── Season 01/
    └── The Last of Us - S01E03 - Long, Long Time.mkv
```

### **命名字段缺失处理**

例如模板存在：

```Plain Text
{episode_title}
```

但没有获取到 Episode Title。

可以配置：

```Plain Text
忽略变量
使用默认值
命名失败
转人工处理
```

### **文件名字符处理**

支持：

```Plain Text
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

### **分类规则**

#### **41\.1 定义**

Classification Policy 负责：

根据 MediaIdentity、RecognitionType 和本地解析标签确定目标媒体库及目标分类目录。

分类规则不负责重命名。

### **分类条件**

支持根据：

```Plain Text
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

### **分类动作**

分类规则命中后产生：

```Plain Text
MediaLibrary
+
SubPath
```

例如：

```Plain Text
MediaLibrary = MainMedia
SubPath = Movies
```

得到：

```Plain Text
/Media/Movies
```

### **分类示例**

A：

```Plain Text
Classification-动画电影
↓
MediaLibrary = Main
SubPath = 动画电影
```

结果：

```Plain Text
/Media/动画电影/
```

B：

```Plain Text
Classification-剧集
↓
MediaLibrary = Main
SubPath = 剧集
```

结果：

```Plain Text
/Media/剧集/
```

C 使用：

```Plain Text
Classification-动画电影
```

因此最终仍然：

```Plain Text
/Media/动画电影/
```

### **分类规则优先级**

支持：

```Plain Text
Priority
```

以及：

```Plain Text
命中停止
继续匹配
```

可以配置：

```Plain Text
默认分类
```

如果没有任何分类规则命中：

```Plain Text
使用默认目录
或者
停止整理
或者
进入人工处理
```

### **媒体库**

#### **46\.1 定义**

Media Library 表示：

整理后的资源存放在哪里。

绑定：

```Plain Text
Storage
+
Root Path
```

#### **46\.2 配置**

```Plain Text
MediaLibrary ID
名称
Storage
Root Path
启用状态
是否允许自动创建目录
备注
```

例如：

```Plain Text
名称：MainMedia
Storage：NAS
Root：/Media
```

#### **46.3 V2 媒体库文件管理页面（CURRENT；Slice 38 PASS / CLOSED）**

V2 媒体库页以 `docs/pics/媒体库页.png` 为视觉参考，管理已配置 MediaLibrary 根目录中的真实
文件。资源库文件页使用 `/ui-v2/resourcelib/files`，媒体库页使用
`/ui-v2/medialib/files`；原 `/ui-v2/library/files` 和 `/ui-v2/library` 弃用，
访问旧地址提供明确的新入口，不保留旧页面或自动跳转别名。上述地址是 Web 路由，后端继续使用
`/api/v1/*` 及同一应用权限、安全规则。

媒体库页提供库卡片、目录树、面包屑、刷新、列表/网格、有界选择与分页，以及
“基本信息 → 存储位置 → 确认”的添加媒体库抽屉。以实际 Storage 为文件列表来源，展示目录、
视频、字幕、NFO、图片等真实条目；不以 FileIndex、识别结果或历史整理记录限制可见文件。
路径精确字符包括前后空格必须保留；刷新必须移除失效目录/选择并提供真实读取失败的恢复路径。

按用户 2026-09-23 明确决定：**媒体库卡片不显示文件总量、容量统计或“未统计”等占位；文件
列表和网格不提供缩略图，统一使用文件类型图标。** 不为此统计全库、读取封面或生成缩略图。
单个文件大小、所选项数量/已知大小及有界操作影响/进度仍属于文件操作信息，继续保留。

常规操作对齐已交付文件页：新建文件夹/受支持文本、单项重命名、复制、移动、删除和受支持的
有界文本编辑；适用操作支持有界多选/目录处理。媒体库页不提供整理、批量整理、Scan/Preview、
识别/整理状态列或浏览器上传/下载。复制/移动可在同一或另一启用媒体库中选择目标，包括不同
已支持 Storage；资源库与媒体库之间的普通直接传输不属于本次范围。

添加媒体库的保存由后端完整执行配置校验、引用保护、适用只读检查、原子激活与运行时绑定。
仅成功后才显示为实际 Active；失败保留原 Active 和可修正输入。停用库从浏览卡片中隐藏，
通过既有 Web 配置入口重新启用。删除媒体库配置必须检查引用且不删除真实目录或文件，
不得与文件删除混淆。此页面不新增自动创建根目录或通用配置编辑规则。

MediaLibrary 与 ResourceLibrary 的库类型、根目录、权限、游标/证据、任务快照与恢复必须分别
校验；相同 ID 或重叠路径不能互换权限。所有写操作仍由 OrganizerExecutor 执行，保留明确的
删除/覆盖意图、逐项结果和禁止不确定变更自动重放等约束。共享界面与执行机制时，Slice37
文件页的已有功能、整理链路及返回目录上下文必须完整保留，只调整必要的地址和导航引用。

Slice 38 已交付上述媒体库文件管理、独立资源库文件路由、受限常用文件维护、配置新增/编辑/移除，
以及 ResourceLibrary/MediaLibrary 对称的页面级编辑与 checked atomic activation。实现范围、明确
延后能力和最终审查证据见 `SLICE.md`；用户旅程见 `docs/product-experience.md`，视觉解释见
`docs/media-library-page-visual-spec.md`。

### **最终路径生成**

最终目标路径：

```Plain Text
MediaLibrary Root
+
Classification Path
+
Naming Directory
+
Naming Filename
```

例如：

```Plain Text
媒体库：
/Media
分类：
电影
命名：
The Matrix (1999)/
The Matrix (1999).mkv
```

最终：

```Plain Text
/Media/电影/The Matrix (1999)/The Matrix (1999).mkv
```

### **整理规则**

Organize Policy 负责：

实际如何处理文件。

支持：

```Plain Text
Move
Copy
HardLink
SoftLink
```

### **整理规则配置**

```Plain Text
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

### **Move**

逻辑：

```Plain Text
Source
↓
Target
```

成功后源位置不再保留原文件。

必须在执行前确认：

```Plain Text
目标存储支持当前计划
目标路径合法
无禁止处理的冲突
```

### **Copy**

整理完成后：

```Plain Text
Source 保留
Target 创建副本
```

### **HardLink / SoftLink**

仅当当前 Storage Adapter 声明支持时允许选择。

如果实际执行时发现能力不满足，可以配置：

```Plain Text
失败
回退Copy
回退Move
```

默认建议：

```Plain Text
失败
```

避免用户未明确允许的文件行为。

### **附属文件整理**

主视频整理时，应识别同目录关联文件。

支持：

```Plain Text
字幕
NFO
Poster
Fanart
图片
Trailer
其他同名附件
```

### **字幕**

支持：

```Plain Text
srt
ass
ssa
vtt
sub
sup
```

例如：

```Plain Text
The.Matrix.1999.mkv
The.Matrix.1999.zh-CN.ass
The.Matrix.1999.en.srt
```

整理后：

```Plain Text
The Matrix (1999).mkv
The Matrix (1999).zh-CN.ass
The Matrix (1999).en.srt
```

优先保留：

```Plain Text
语言
简繁标签
Forced
SDH
其他已有字幕标签
```

### **Dry Run 整理预演**

这是必须实现的功能。

Dry Run：

完成识别、元数据匹配、命名、分类和目标路径计算，但不修改任何文件。

展示：

```Plain Text
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

#### **55\.1 示例**

```Plain Text
SOURCE
/Downloads/SP/The.Matrix.1999.mkv
识别规则
SP-Rule
识别类型
SP
元数据
TMDB / The Matrix / 1999
命名策略
Naming-Movie
分类策略
Classification-Movie
整理策略
Move
TARGET
/Media/A/The Matrix (1999)/The Matrix (1999).mkv
```

### **自动整理**

自动化只支持一种模式（2026-10-13 用户明确修订）：

```Plain Text
自动整理
```

自动整理必须满足：

```Plain Text
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

### **文件重复检测**

整理前检查：

```Plain Text
Target Exists
```

同时可以根据：

```Plain Text
Provider ID
Media Type
Season
Episode
文件大小
文件 Hash
```

辅助判断是否重复。

### **Hash 策略**

支持：

```Plain Text
不计算
快速Hash
完整Hash
```

不要求所有媒体默认进行完整 Hash。

可由：

```Plain Text
重复检测策略
```

决定是否计算。

### **冲突策略**

目标已经存在时支持：

```Plain Text
Skip
Overwrite
Rename
Manual
```

#### **59\.1 Skip**

保持源文件不动。

记录：

```Plain Text
Status = Skipped
Reason = TargetExists
```

#### **59\.2 Overwrite**

覆盖已有目标。

属于高风险操作。

必须：

```Plain Text
明确配置开启
+
记录审计日志
```

#### **59\.3 Rename**

例如：

```Plain Text
The Matrix (1999).mkv
The Matrix (1999) (1).mkv
```

#### **59\.4 Manual**

进入：

```Plain Text
NeedConfirm
```

等待人工决定。

### **主文件与附加内容识别**

同目录可能存在：

```Plain Text
正片
Sample
Trailer
Extra
Featurette
Behind The Scenes
```

可以根据：

```Plain Text
文件名称
关键词
目录位置
文件大小
```

判断。

相关关键词规则允许配置。

### **空目录处理**

媒体整理成功以后，可以配置：

```Plain Text
不处理
删除真正的空目录
删除仅包含允许忽略文件的目录
```

默认：

```Plain Text
不删除未知文件
```

当前实现：策略支持默认 `none`、`empty` 和 `ignorable`。仅显式执行且 MOVE
完整验证成功后，由 OrganizerExecutor 在 ResourceLibrary Storage-relative 根的排他边界内按
有界父目录数量处理；根本身永不删除。`empty` 即时复核为空后删除；`ignorable` 只处理完整
有界列表中匹配显式安全 basename pattern 的普通文件。未知内容、链接、子目录、超限、竞态或
访问失败会停止或返回 PARTIAL；COPY/LINK/DryRun/失败/Rollback 不清理。

### **任务系统**

所有扫描及整理行为均由 Task 执行。

#### **已准入文件传输与 Worker 健康（Slice 39 扩展，CURRENT）**

文件传输 Worker 的存在与启动时是否已有 Active 无关。Worker 可先启动，随后完成首次设置、
激活配置并提交 OpenList 移动，无需重启 Worker。当前 Active 只决定新任务准入；已准入任务依据
持久化 command、库类型、revision ID 和 digest 重建并固定执行上下文，完整验证后才进入
OrganizerExecutor。新 B 任务使用 B，已准入及执行中的 A 任务保持 A，不因配置切换而改绑。

当前 Active 缺失或不可用时禁止新任务准入，但不单独阻止完整可验证的历史任务快照执行。
任务固定快照缺失、损坏、digest 不匹配、未发布或必需密钥不可用时，必须在新存储变更前拒绝，
展示原因、持久状态与恢复动作。不得回退到当前 Active、Draft 或 JSON；已完成及结果不确定的
操作不得因重启、重试或配置切换而重复执行。OpenList 慢请求期间仍维持租约与 mutation fence。

健康信息分为：进程存活（liveness）；注册/心跳、数据库访问及 schema 匹配（readiness）；
当前 Active 可用性、实际支持命令及任务快照兼容性（work readiness）。容器健康检查须验证真实
Worker readiness，并说明其含义；healthy 不等于所有任务都可执行。Web/API 在提交前或提交后
立即说明“等待可用 Worker”、原因和下一步，任务进度及重新访问也显示该状态，不静默停在 pending。
健康查询不得扫描、调用提供商、产生任务或变更媒体。

回归必须覆盖先启动再激活、A/B 新旧任务隔离、移动途中切换、不可验证上下文零新变更、重启不重放、
慢请求租约/fence，以及真实 Docker 顺序“启动容器 → 首次激活 → 提交 OpenList 移动”。
已有文件命令和其他 Worker 职责保持兼容，不引入新传输模式或自动不确定重放。

### **任务类型**

```Plain Text
ScanTask
RecognitionTask
OrganizeTask
MetadataRefreshTask
```

也可以由一个父任务组合。

### **任务状态**

统一状态：

```Plain Text
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

### **任务信息**

记录：

```Plain Text
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

### **任务操作**

支持：

```Plain Text
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

### **并发控制**

系统配置：

```Plain Text
最大扫描任务数
最大识别并发
最大元数据请求并发
最大整理并发
```

Storage 可以单独配置：

```Plain Text
MaxConcurrency
```

Provider 可以单独配置：

```Plain Text
MaxConcurrency
```

### **文件锁**

同一个文件在同一时间只能存在一个有效整理操作。

防止：

```Plain Text
Task A Move File
Task B Copy File
```

同时发生。

建议锁标识至少包含：

```Plain Text
StorageID
+
Path
```

### **整理操作记录**

每个媒体建立：

```Plain Text
OrganizePlan
```

记录：

```Plain Text
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

```Plain Text
1 CreateDirectory
2 Move Video
3 Move Subtitle
4 Move NFO
```

### **操作状态**

每一步操作保存：

```Plain Text
Pending
Running
Success
Failed
Skipped
```

方便：

```Plain Text
故障定位
失败重试
任务恢复
```

### **日志系统**

支持日志等级：

```Plain Text
TRACE
DEBUG
INFO
WARN
ERROR
```

默认：

```Plain Text
INFO
```

可开启：

```Plain Text
DEBUG
```

### **普通整理日志**

例如：

```Plain Text
[INFO] 发现媒体文件
       /Downloads/SP/The.Matrix.1999.mkv
[INFO] 命中识别规则
       Rule=SP
[INFO] RecognitionType=SP
[INFO] 开始元数据识别
[INFO] Metadata Provider=TMDB
[INFO] 匹配媒体
       The Matrix (1999)
[INFO] NamingPolicy=Movie
[INFO] ClassificationPolicy=Movie
[INFO] 目标路径
       /Media/Movie/The Matrix (1999)/The Matrix (1999).mkv
[INFO] Operation=Move
[INFO] 整理成功
```

### **Debug 日志**

Debug 模式额外记录：

```Plain Text
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

### **日志脱敏**

严禁输出完整：

```Plain Text
Password
Token
API Key
AccessKey
SecretKey
Authorization
Cookie
```

可以输出：

```Plain Text
Token=******
```

### **整理结果记录**

每个 Task 完成后必须持久化整理结果。

每个 Organize item 的终态 Result 持久化后，必须自动同步对应 FileIndex 的业务状态。同步内容
至少包括已知的处理结论、整理 disposition、实际 effect 和需要的恢复信息。FileIndex 同步失败
不得覆盖 Result，也不得触发已完成或不确定 Storage mutation 的自动重放。

上段为冻结 V1 同步定义。当前 V2 按 2026-10-18 明确修订完全退役 FileIndex，同步及同步修复
不再执行；Task/Result、逐项已完成步骤、效果确定性和审计持久化义务保留，仍禁止错误重放。

支持：

```Plain Text
数据库记录
JSON导出
CSV导出
```

至少实现数据库 \+ JSON。

### **JSON 结果示例**

```JSON
{
  "taskId": "task_001",
  "status": "Completed",
  "total": 3,
  "success": 3,
  "failed": 0,
  "skipped": 0,
  "items": [
    {
      "source": "/Downloads/SP/The.Matrix.1999.mkv",
      "recognitionType": "SP",
      "provider": "TMDB",
      "providerId": "xxx",
      "title": "The Matrix",
      "year": 1999,
      "namingPolicy": "Movie",
      "classificationPolicy": "Movie",
      "organizePolicy": "Move",
      "target": "/Media/Movie/The Matrix (1999)/The Matrix (1999).mkv",
      "status": "Success"
    }
  ]
}
```

### **错误体系**

统一错误分类，例如：

```Plain Text
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

### **错误记录**

错误必须包含：

```Plain Text
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

### **自动重试**

适用于临时错误：

```Plain Text
网络超时
SMB断连
OpenList连接异常
对象存储暂时失败
TMDB请求超时
HTTP 429
HTTP 5xx
```

支持：

```Plain Text
最大次数
基础间隔
指数退避
```

不可恢复的配置错误不自动无限重试。

### **未识别媒体**

无法判断 RecognitionType：

```Plain Text
Status = Unrecognized
```

支持：

```Plain Text
重新识别
人工指定 RecognitionType
建立新的识别规则
忽略
```

当前实现：Task 跟踪的 Unrecognized 项进入持久 WAITING_RECOGNITION，保存启用
RecognitionType 的有界快照并释放源锁。CLI 显式选择快照中且当前仍启用的类型，原子记录
actor/note 审计，再由显式 resume 进入原有策略管线。没有隐藏 A 默认，不修改规则或配置；
选择 C 后 RecognitionType 仍为 C。建立规则留后续。

当前实现：Recognition 人工等待项可显式进入 IGNORED；review 与 TaskItem 原子更新并记录
actor/note。该动作不删除或隐藏媒体、不建立规则、不影响未来扫描；同样支持有界批量忽略。

当前实现：旧的 Recognition retry_requested 状态和
`recognition-reviews retry-pending` 批量请求入口已退役；Recognition 等待项仍可显式指定
启用类型或忽略，继续处理统一通过现有 Task resume/recovery 边界，不自动调用 Storage 或
Provider。

当前实现：上述 Recognition 等待项也支持有界批量忽略
`tasks ignore-pending --actor ... [--note ...] [--limit 1..100] [--task-id ...]`；最早到期的一组
pending 项与匹配 review 在同一事务中标记为 IGNORED。

当前实现：上述 pending RecognitionReview 也支持有界批量人工指定同一启用
RecognitionType：
`recognition-reviews resolve-pending --recognition-type TYPE --actor ... [--note ...]
[--limit 1..100] [--task-id ...]`。每一项仍必须包含在快照中，且整批原子 RESOLVED。

### **元数据识别失败**

已经确定 RecognitionType，但无法匹配影视作品：

```Plain Text
Status = MetadataNotFound
```

支持：

```Plain Text
修改关键词
修改年份
Movie / TV切换
使用当前配置的Provider
直接填写Provider ID
人工选择候选
忽略
```

当前实现：Metadata 候选等待与 MetadataNotFound 修正等待支持单项持久忽略。
Ignored 不计成功、不参与 resume/retry，且不调用 Storage 或 MetadataProvider。

当前实现：上述 Metadata 等待项同样支持有界批量忽略，范围、排序、原子性和
安全边界与 Recognition 批量忽略一致。

当前实现：Metadata NOT_FOUND 修正等待项也支持有界批量修正：
`metadata-corrections resolve-pending --media-type movie|tv [--query QUERY | --provider-id
PROVIDER_ID] [--year YEAR] --actor ... [--note ...] [--limit 1..100] [--task-id ...]`。
整批使用同一组合法修正输入原子 RESOLVED，仍由显式 tasks resume 调用真实 Provider。

当前实现：Metadata 候选等待项也支持有界批量候选选择：
`metadata-reviews resolve-pending --candidate-rank RANK --actor ... [--note ...]
[--limit 1..100] [--task-id ...]`。整批以同一持久候选 rank 原子 RESOLVED，仍由显式
tasks resume 消费持久 MetadataSelection。

### **人工整理**

支持用户选择单个或者多个文件。

可以手动设置：

```Plain Text
RecognitionType
Metadata Result
NamingPolicy
ClassificationPolicy
OrganizePolicy
```

系统实时生成：

```Plain Text
Target Preview
```

确认后执行。

### **批量操作**

支持：

```Plain Text
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

当前实现：已完成批量忽略（`tasks ignore-pending`）、批量设置 RecognitionType
（Recognition resolve-pending）、批量 Metadata 修正（Metadata resolve-pending）与批量
Metadata 候选选择（Metadata review resolve-pending）四项有界闭环；旧的 Recognition
retry-pending 入口已退役。批量 Dry Run/整理仍留后续，FAILED/PARTIAL TaskItem 的
`tasks retry-request` 仍通过显式 tasks resume 执行。

当前实现：新增 tasks retry-request，可对有界 FAILED/PARTIAL TaskItem 批量
原子回到 PENDING；真正的重试仍通过显式 tasks resume 执行。批量 Dry Run/整理仍留后续。

### **策略测试工具**

配置页面必须提供：

Test Policy

用户输入：

```Plain Text
Storage
File Path
```

系统运行到：

```Plain Text
Plan
```

但不实际操作文件。

### **策略测试结果**

显示：

```Plain Text
SOURCE
文件名解析
识别规则匹配：
Rule-SP
RecognitionType：
SP
Metadata Policy：
Movie-TMDB
Metadata：
The Matrix (1999)
Confidence：
98
Naming Policy：
Movie
Naming Result：
The Matrix (1999).mkv
Classification Policy：
Movie
Media Library：
Main
SubPath：
Movie/The Matrix (1999)
Organize Policy：
Move
TARGET：
/Media/Movie/The Matrix (1999)/The Matrix (1999).mkv
```

此功能对于调试规则必须作为核心功能实现。

### **配置管理**

系统需要管理：

```Plain Text
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

当前实现：whole-document Managed Configuration 通过 Draft → Validate/Test →
显式 Activate 发布 immutable Runtime Snapshot；Task/Job/Scheduler 在创建边界 pin 精确
revision/digest，快照缺失或损坏时 fail closed，不静默回退到 JSON。Web/API 在该
authority 下支持 Local Storage、ResourceLibrary、MediaLibrary、RecognitionType、
RecognitionRule、RecognitionTypePolicy、MetadataPolicy、NamingPolicy、ClassificationPolicy
和 OrganizePolicy 的当前有界对象编辑、引用保护、脱敏解释与 Before/After 审计。

Naming、Classification 和 Organize 旅程对精确 Draft/Validated revision 复用生产
policy resolver、Naming/Classification engine、Planner 共用的组合与路径安全语义，
持久显示应用策略、RecognitionType、MediaLibrary、Storage-relative 目标、Organize
权限边界、warning、current/stale 状态和恢复动作；复用 Naming/Classification 策略不会
改变原 RecognitionType。Provider-neutral destination precheck 支持一个 RecognitionType 下
1–8 个独立样本、单一目标 Storage、跨项目标碰撞、冲突投影、所需与声明能力差距、统一行证据
与有界恢复。
`capability_gap` 优先，否则运行结论取最严重的投影结果。预检全程经只读守卫，
不授予 overwrite/delete/execute 权限、不变更媒体、不在不支持能力时静默回退。
checked activation 对每个被 ResourceLibrary 或 MediaLibrary 引用且启用的 Storage 要求当前、passed
且绑定精确 revision/version/digest 的只读 Storage check evidence；同时要求当前 Recognition Strategy
Test 和 MediaLibrary destination 的 provider-neutral destination precheck。missing/stale/failed、
credential readiness 变化以及 `capability_gap` 均保留 Draft 与之前 Active，并 fail closed。

写入式能力探测、单次请求的多 RecognitionType/多目标 Storage、已知媒体
重复检测、附件预检、绝对 mounted-path 显示、通用 Task resume 和超出 Slice 24 有界边界的
更广手工整理仍是后续 TARGET，不属于上述 CURRENT 声明。Provider switching 已由 A 决策移入
V1.x / V2，不再作为最终 V1 blocker。Slice 25 的
计划自动化与受限 unattended organization 已在其独立 Slice 中交付；生产外部服务专项验收、
uncertain mutation 自动重放、跨运行补偿和历史 Rollback 仍不属于当前已交付声明。

### **配置操作**

全部配置应支持：

```Plain Text
新增
编辑
复制
启用
禁用
删除
测试
```

当前实现：Managed Draft 为 Local/SMB/OpenList/AWS S3/Cloudflare R2/通用 S3-compatible Storage、
ResourceLibrary/MediaLibrary、Recognition、MetadataPolicy、NamingPolicy、ClassificationPolicy 和
OrganizePolicy 提供 Web/API 有界新增、编辑、复制、删除、引用阻断、验证与适用的只读测试/预览。
Storage Browser/path selection、Storage check evidence、provider-neutral destination precheck 和
完整首次设置恢复已由 Slice 26 交付；System Settings 对象旅程、配置导入导出和 Webhook 管理恢复
已由 Slice 28 交付。Provider switching 不属于最终 V1。Automation Task Definition 的有界管理、验证、
精确 Preview、授权/撤销和运行历史已由 Slice 25 交付。

可复制规则方便：

```Plain Text
Movie规则
↓
复制
↓
修改为SP规则
```

### **配置引用关系**

配置不能无检查直接删除。

例如：

```Plain Text
Naming-Movie
```

被：

```Plain Text
RecognitionType Movie
RecognitionType SP
```

引用。

删除时系统必须提示：

```Plain Text
当前规则被2个识别类型策略引用。
```

默认禁止删除。

### **配置导入导出**

支持：

```Plain Text
导出配置
导入配置
备份
恢复
```

配置必须包含：

```Plain Text
ConfigVersion
```

用于未来版本升级。

敏感字段：

```Plain Text
默认不导出
```

或者：

```Plain Text
经过单独加密后导出
```

### **数据索引**

本节记录冻结 V1 定义。当前 V2 以 V2-FILES-005/006 与本文 FileIndex 退役修订取代：
不建立全局文件索引，列表只读 live Storage；显式工作自己的精确来源、观察、结果和审计继续持久化。

所有扫描过的文件建立索引。

建议：

```Plain Text
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

### **增量扫描**

以下全局 New/Modified/Unchanged/Missing 索引产品语义为 V1 历史；当前 V2 不维护该目录。
内部有界发现、真实稳定性、来源变化和任务去重/非重放安全继续按本次修订成立。

扫描时判断：

```Plain Text
New
Modified
Unchanged
Missing
```

只有：

```Plain Text
New
Modified
```

默认重新进入媒体识别。

避免每一次扫描都重新处理整个媒体库。

### **文件状态**

统一建议：

```Plain Text
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

### **Dashboard**

首页展示：

```Plain Text
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

### **文件列表**

支持显示：

```Plain Text
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

当前 V2（Slice45 PASS / CLOSED）：`mediaflow files list`、文件页和媒体库页共用所选库的
实时有界 Storage 列表，不记录文件目录；索引 CLI/API/页面/同步完全退役，详情见退役设计。
下面关于索引列表/游标/同步的文字保留其历史接受含义，已由 V2-FILES-005/006 替换，
不是当前产品入口或继续保留 FileIndex 的授权。

历史实现基线：认证 Web/API 的 **Files** 提供配置 Storage 的有界真实目录/文件浏览，**FileIndex**
CLI/Web/API 提供有界索引列表、单项详情和统计；两者都使用 Storage-relative identity，Files
不递归扫描、不接受任意主机路径。读取不构造 Provider，也不读取文件内容；列表和详情使用
稳定的 keyset cursor，`--after/--before` 配合 `--cursor-file-id` 使用
`(updated_at DESC, file_id DESC)` 顺序，不使用 OFFSET。

V2 Files 页面当前实现（Slice 37 PASS / CLOSED，2026-09-23）：实时物理条目仍由 Storage
提供，页面不渲染 `RecognitionType`、识别结果或整理状态反馈；这些业务信息不成为当前 Files
页的可见状态。FileIndex 的 `fileId`、occurrence、fingerprint、claim、plan hash 等内部标识
不能成为 Files 页的操作权限或 Preview authority。Exact Storage entry name/path identity,
including leading/trailing whitespace, survives the Web projection and navigation; boundary
whitespace is visibly disambiguated. At that acceptance FileIndex remained a separate indexed route
and bounded post-mutation reconciliation target; both are removed from CURRENT V2 by Slice45.
Files-originated 整理准备只提交 ResourceLibrary 和相对路径，由后端通过 Storage 生成 source
identity；CURRENT 结果保存在 Task/Result/checkpoint，不再同步 FileIndex。
Manual Organize Web choice editor 以 RecognitionType 作为操作员选择来源，按 pinned snapshot
自动投影 NamingPolicy、ClassificationPolicy 和 OrganizePolicy；RecognitionType C 的身份保持为
C，即使复用 A 的下游策略，映射不可用时 fail closed 并提供重新加载恢复。

V2 Files 常用文件管理要求（Slice 37 PASS / CLOSED，2026-09-23）：

- 当前 Slice 37 Files 页面提供新建文件夹/受支持文本文件、重命名、复制、移动、删除和受支持文本编辑；
  适用操作支持有界多选，长时间/批量 mutation 使用现有 Task 并逐项保留进度、成功、失败和恢复。
 直接浏览器 Upload/Download 控件、路由、服务和投影已从当前垂直旅程移除；通用 Storage Read/Write、
  provider transfer primitive 与 Copy/Move 能力仍保留给支持的后端流程。
- Rename 只提交合法 basename；Create/Rename/Copy/Move 的冲突默认不覆盖，可明确选择跳过、
  保留两者/重命名或 Replace，Replace 另行确认并复核精确目标。
- Copy/Move 使用明确选择的 Active source/destination ResourceLibrary。相同 Storage 使用 adapter
  声明的原生能力且不静默 fallback；跨 Storage Copy 是显式传输，跨 Storage Move 明确执行
  Copy→校验→删除源，校验失败保留源，后续失败显示 partial result。
- Delete 支持文件和有界目录/多选删除；非空目录先显示轻量项目数/大小影响并进行一次确认。
  ResourceLibrary 根和超出 item/depth/size 上限的递归删除始终拒绝。
- Edit 仅显式保存 allowlist 内、大小受限、可安全解码的文本文件（例如 NFO、字幕或普通文本）；
  不提供任意二进制、视频、音频或图片内容编辑。
- 这些直接命令不进入媒体整理的 Recognition、Metadata、Naming、Classification、Preview 或
  execution-token 流程，但后端仍检查 RBAC、Active source/destination 绑定、路径 confinement、
  capability、limits 和 stale/conflict；CreateDirectory/Copy/Move/Delete/Write mutation 只允许
  OrganizerExecutor 执行。未来若恢复浏览器传输能力，也必须保持同一边界。
- 成功后以 live Storage 刷新为准；Slice37 原有 FileIndex best-effort reconciliation 已在45退役。
  结果或展示失败仍禁止自动重放已完成或结果不确定的 Storage mutation。

V2 Files 与共享 Shell 视觉要求（Slice 37 PASS / CLOSED，2026-09-20）：`docs/pics/文件页.png` 是
`1536 x 1024` 成功态的唯一视觉权威。其浅色左侧导航栏和顶部栏必须作为统一共享 AppShell 替换
原 V2 深色横向顶部 Shell，并应用到所有支持的 V2 route；不得把参考图中的 Files 内容作为卡片
嵌入旧 Shell。非 Files 页的 route、认证、数据查询和业务交互保持不变，仅共享外层 chrome 按新
Shell 更新。Files 页的资源库摘要、目录树、文件表、选择操作栏、常用文件操作和打开状态的
`添加资源库` 抽屉按 `docs/file-page-visual-spec.md` 验收。

### **搜索与筛选**

支持：

```Plain Text
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

当前实现：CLI/Web/API 支持 ResourceLibrary、Storage、scan status、path/filename 子串筛选，以及
基于最新 Task Result 的 RecognitionType、Provider、Provider ID、Title、Task ID 和 Year
派生筛选；认证 Web/API 复用同一过滤、cursor、limit 和只读详情语义。时间范围筛选仍未提供，
Storage Browser/path picker 已由 Slice 26/27 提供并与 FileIndex 保持语义分离。V2 Files 页面只
允许为展示叠加有界 FileIndex 业务状态反馈，不得用其替代 Storage 文件事实或 Preview authority。

当前实现：生产 CLI 支持全 ResourceLibrary 的显式 batch scan/preview/organize，`organize`
默认 DryRun，只有显式 `--execute` 才可进入执行边界；Operator Web 支持多文件 manual Preview
与精确一次性执行。批量 review、ignore、Recognition/Metadata 决策和有界 checkpoint recovery
均保留每项独立状态，真正继续处理仍需显式 resume 或对应 recovery action。

当前实现：Files 详情 API/Web 保留单项 Metadata correction DryRun continuation 请求；旧的
re-recognize、re-match、re-plan 直达请求已退役。Continuation 请求本身不调用 Provider、
不构造 Storage，实际处理由受 pin 保护的 Worker continuation 执行。

当前实现：Managed Configuration 已成为受支持的 Draft/Validated/Active authority；JSON 保留
为 bootstrap、兼容、迁移和支持路径。Web/API 已覆盖配置状态、对象编辑、引用保护、精确
revision 预览、Storage-relative path selection、所有 V1 Storage 的只读 check、provider-neutral
destination precheck、checked activation、day-2 Configuration/Settings/Webhook 管理、System
Settings 对象旅程以及配置/结果导入导出。Slice 26 的首次设置闭环、Slice 27 的真实 Storage
Files/FileIndex、manual operations、processing disposition、recovery continuation 与 Worker
readiness 闭环以及 Slice 28 的 day-2 管理闭环均已完成。

V2 Files 页新增 ResourceLibrary 的页面级保存流程不改变 Active 的不可变性：后端根据当前
Active 配置构造候选、执行完整 config 校验和激活，成功才保存并发布；任何错误都拒绝保存并
保留旧 Active。该页面级流程不要求操作员显式执行内部 Validate/Activate，但仍必须复用同一
RBAC、引用校验、Storage 检查、审计和 fail-closed 约束。

### **媒体详情**

展示：

```Plain Text
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

当前实现：files show 在 FileIndex 字段之外追加同一 source Storage/path 的最新持久 Task Result；
缺失历史显式显示为空，不构造 Provider/Storage，也不读取文件内容。认证 Web/API 的有界
Files/Media 详情显示解析、识别、元数据、策略、
计划、冲突、附件、Result 历史和当前恢复动作；人工整理从持久选择到精确 Preview、显式一次性
执行和逐项结果均可沿同一旅程完成。详情读取保持零副作用，历史 Result 的不安全错误/效果文本
只在读取投影中脱敏，不回写历史行。Provider switching 和超出该有界旅程的能力仍未开始。

操作：

```Plain Text
重新识别
修改RecognitionType
重新匹配Metadata
重新生成Plan
重新整理
```

### **系统设置**

配置：

```Plain Text
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

### **定时任务**

支持：

```Plain Text
定时自动整理
定时清理缓存
定时清理日志
```

调度支持：

```Plain Text
固定周期
固定时间
Cron
```

例如：

```Plain Text
每30分钟自动整理新增文件
每天03:00自动整理指定范围
```

#### **98.1 自动化对象与生命周期边界**

定时自动整理使用现有 Task / TaskItem / Result 执行与记录模型，不建立一套平行的
媒体处理任务模型。需要明确区分以下对象：

```Plain Text
Automation Task Definition（长期自动化任务定义）
    ↓ Scheduler 在每个到期点发出
Automation Job（单次运行请求）
    ↓ Worker 通过现有应用链创建
Task（本次实际处理运行）
    ↓
TaskItem（每个媒体文件的独立状态）
    ↓
Result / Log（持久结果与可审计证据）
```

Automation Task Definition 是用户长期管理的业务定义，至少负责：

```Plain Text
名称与稳定身份
ResourceLibrary / source scope
可选的扫描子目录或范围
Schedule
Timezone
Enabled state
所属的受管配置权威
是否允许 unattended execution
受授权范围限制的运行边界
```

运行边界必须能限制源 ResourceLibrary / 子范围、允许的运行模式与必要的工作量。
它不代替 RecognitionTypePolicy，也不定义每个文件的 Metadata Provider、目标目录或整理动作。

Automation Job 只表示该定义的一次调度运行；Task / TaskItem 负责本次实际处理状态；
Result / Log 记录每个媒体项的决策、已知效果、错误和恢复信息。它们必须能通过稳定身份
相互追踪。

#### **98.2 Scheduler 责任边界**

Scheduler 只负责：

```Plain Text
判断哪个 Automation Task Definition 何时到期
根据已激活的受管配置发出一个 Automation Job
保证同一调度发生点不被非预期重复发出
```

Scheduler 不得：

```Plain Text
自行选择 Metadata Provider
自行选择 NamingPolicy
自行选择 ClassificationPolicy
自行选择 MediaLibrary 或 relative destination
自行选择 Move / Copy / HardLink / SoftLink
直接调用 Storage mutation
```

每个已创建 Job 必须固定创建边界上实际激活的不可变配置快照。后续 Draft 编辑或新版本
激活只影响之后创建的 Job；已创建的 Job / Task 不得静默改变 Provider、策略、目标或
整理动作。

#### **98.3 定时自动整理链路**

定时运行的每个文件必须继续使用系统的现有主链：

```Plain Text
Automation Task Definition 限定 ResourceLibrary / source scope
    ↓
Scan
    ↓
Parse
    ↓
Recognition
    ↓
RecognitionType
    ↓
RecognitionTypePolicy
    ↓
MetadataPolicy → MetadataProvider
    ↓
NamingPolicy
    ↓
ClassificationPolicy → MediaLibrary + relative destination
    ↓
OrganizePolicy → Move / Copy / HardLink / SoftLink
    ↓
Plan / Preview
    ↓
Execute
    ↓
Result / Log
```

同一 Automation Task Definition 的单次运行可以扫描到不同 RecognitionType。每个类型必须根据
自己的 RecognitionTypePolicy 分别解析 MetadataPolicy、NamingPolicy、ClassificationPolicy 和
OrganizePolicy。因此同一次定时任务中的不同文件可以使用不同 Metadata Provider、命名策略、
分类策略、目标 MediaLibrary 和整理动作。

最终 MediaLibrary 和相对目标目录必须由 ClassificationPolicy 决定；Automation Task Definition
不得硬编码每个媒体文件的最终目录。Move / Copy / HardLink / SoftLink 由对应的
OrganizePolicy 决定；Scheduler 和 Automation Task Definition 不复制该配置。

#### **98.4 V1 Scheduled Unattended Organization 授权**

Scheduled Unattended Organization 是 V1 REQUIRED。

自动化定义固定为自动整理，新建默认关闭且不带执行授权；不再提供“仅扫描”或“扫描并生成计划”
模式，也不保留旧模式执行兼容或转换入口。当前 V2 按 V2-OPS-013 将独立 Preview 产品
退役，零变更预演由共享整理分析/精确计划与授权前校验承接；它不是自动化运行模式，也不
授予执行权限。下方 V1 流程的 Preview / DryRun 表示这一分析/权限分离要求。
当用户显式授权自动整理时，可以向
该 Automation Task Definition 授予持久、可撤销、受范围限制的 unattended execution
authority。在该授权有效且本次运行通过全部安全校验时，到达调度时间后不需要用户再次
手工点击 Execute。

用户首次授予 unattended execution authority 的完整产品流程为：

```Plain Text
Configure
  → Validate / Test
  → Preview / DryRun
  → Explicitly Enable Unattended Execution
  → Scheduled Runs
```

系统必须始终提供与真实执行等价的 Preview / DryRun 能力，但后续每次 Scheduled Run
不要求用户再次手工点击 Preview 或 Execute。每次运行仍必须在后台使用正常策略链生成
OrganizePlan，并重新通过范围、冲突、Storage capability、当前授权和其他安全校验。
Automation Task Definition 的 source scope 或授权边界被扩大时，不得沿用旧授权静默获得
更大权限。

任务级持久授权与手工或远程真实执行使用的 one-shot execution ticket 是两种不同语义：

```Plain Text
Manual / remote execution
    → 保留一次性、可消耗的 execution ticket
Scheduled unattended execution
    → 使用绑定 Automation Task Definition 的持久、可撤销、受限授权
```

持久授权必须至少绑定：

```Plain Text
Automation Task Definition identity
ResourceLibrary / source scope
允许的执行模式
必要的工作量或运行边界
授权主体与审计记录
```

该授权只允许执行由已固定配置和正常策略链生成的合法计划，不会自动授予 Overwrite、
Delete、清理源目录或任何超出范围的文件操作。这些高风险能力仍必须同时满足独立策略和
安全权限。

自动执行必须 fail closed。以下任一条件失败时，不得调用媒体 mutation：

```Plain Text
已固定的 configuration revision 不可用或不匹配
引用的 ResourceLibrary / Storage / Policy / Provider / MediaLibrary 失效
Storage capability 不满足计划
持久授权已撤销、失效或当前权限不再满足
源路径或任何操作超出授权范围
识别、元数据、命名、分类、冲突、稳定性或其他安全条件未通过
```

已固定的 Provider 和处理策略不随后续配置修改而改变；授权是独立的动态安全门。授权撤销
必须阻止尚未发生的 mutation，但不得伪造或重写已完成的效果。失败项必须持久保存为可操作的
TaskItem / Result / Log 证据，并说明安全恢复操作。

### **安全要求**

所有敏感凭证：

```Plain Text
SMB Password
OpenList Token
TMDB Token / API Key
R2 AccessKey
R2 SecretKey
其他Provider认证信息
```

必须加密存储。

### **高风险文件操作保护**

高风险操作：

```Plain Text
Overwrite
Delete
Move后删除源
清理源目录
```

需要单独配置。

默认策略：

```Plain Text
不允许覆盖
不永久删除未知文件
```

### **审计日志**

记录重要操作：

```Plain Text
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

```Plain Text
User
Action
Object
Before
After
Timestamp
Result
```

### **API 设计要求**

核心能力必须提供 API，以便：

```Plain Text
Web UI
CLI
自动化程序
其他服务
```

调用。

建议：

```Plain Text
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

### **推荐后端模块**

```Plain Text
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

### **核心数据关系**

建议：

```Plain Text
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

### **完整媒体处理流程**

最终完整业务流程：

```Plain Text
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

### **第一阶段 MVP**

首期建议必须完成：

##### **Storage**

- Local
- SMB
- OpenList
- R2 / S3

##### **Library**

- Resource Library
- Media Library

##### **Recognition**

- 文件扫描
- 文件过滤
- 文件稳定检测
- 文件名解析
- 路径解析
- 季集解析
- Recognition Rule
- Recognition Type
- Recognition Type Policy

##### **Metadata**

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

##### **Policies**

- Naming Policy
- Classification Policy
- Organize Policy

##### **Organizer**

- Dry Run
- Move
- Copy
- HardLink
- SoftLink
- 字幕整理
- 冲突处理
- 重复检测

##### **Task**

- Task Queue
- 任务状态
- 暂停
- 继续
- 取消
- 重试

##### **Log**

- INFO
- DEBUG
- ERROR
- 单文件完整整理日志
- 整理结果 JSON

##### **UI**

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

### **第二阶段**

后续增加：

```Plain Text
更多Metadata Provider
Provider switching
更多Storage Provider
更多字幕处理能力
多版本媒体
质量优先级策略
自动媒体升级
海报及背景图下载
NFO生成
媒体服务器刷新通知
完整权限系统
Audit Log增强
完整Rollback
高级统计
邮件/聊天专用通知 Provider 与媒体服务器刷新通知
完整 Secret Store / Docker Secrets 集成
```

### **验收核心场景**

#### **场景一：Movie→ Movie**

输入：

```Plain Text
/Downloads/Movie/The.Matrix.1999.mkv
```

识别：

```Plain Text
Movie
```

处理：

```Plain Text
Movie Metadata
→ Movie Naming
→ Movie Classification
→ Move
```

结果：

```Plain Text
/Media/Movie/The Matrix (1999)/The Matrix (1999).mkv
```

验收通过。

#### **场景二：TV → TV**

输入：

```Plain Text
/Downloads/**TV**/The.Last.of.Us.S01E03.mkv
```

识别：

```Plain Text
**TV**
```

处理：

```Plain Text
**TV** Metadata
→ **TV** Naming
→ **TV** Classification
```

结果：

```Plain Text
/Media/B/The Last of Us/
└── Season 01/
    └── The Last of Us - S01E03.mkv
```

验收通过。

#### **场景三：SP → Movie**

输入：

```Plain Text
/Downloads/**SP**/Special.C.2025.mkv
```

识别：

```Plain Text
**SP**
```

类型不得改变。

处理：

```Plain Text
RecognitionType = **SP**
NamingPolicy = **Movie**
ClassificationPolicy = **Movie**
```

结果：

```Plain Text
/Media/**Movie**/Special C (2025)/Special C (2025).mkv
```

验收通过。

关键验收条件：

```Plain Text
RecognitionType仍然必须为C。
```

### **最终架构原则**

系统必须严格保持：

```Plain Text
识别是什么
≠
叫什么
≠
放在哪里
≠
怎么移动
```

对应：

```Plain Text
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

```Plain Text
A → A命名 + A分类
B → B命名 + B分类
C → A命名 + A分类
D → B命名 + A分类
E → A命名 + B分类
```

均属于正常合法配置。

### **最终核心原则**

系统的实际执行链必须始终为：

```Plain Text
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
