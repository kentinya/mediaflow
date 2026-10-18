# MediaFlow Product Experience

This document owns operator journeys and completion semantics. Stable scope/IDs live in
[Requirements](requirements.md) and [V2 Requirements](v2-requirements.md); technical boundaries in
[Architecture](architecture.md). [Progress](progress.md) records accepted baselines and deferrals.
The committed [Slice](../SLICE.md) owns active changes. Slice45's B-reviewed implementation is not
A closure; its complete target specifications below remain the acceptance authority.
Detailed superseded delivery notes are retained at
`865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/product-experience.md`.

## Product Experience Priority

Choose the most direct complete Web journey that preserves correctness, security and data integrity.
Automate determinable scope/capability/permission/freshness checks; interrupt for meaningful intent,
authority escalation, ambiguity, conflict, uncertain effects or irreversible/destructive scope.
Internal tokens/grants/revisions/claims/fences remain backend mechanisms, not ordinary user chores.
CLI supports administration, automation and diagnosis; it cannot complete a required ordinary Web flow.

## Product completion contract

Every capability completes **goal → entry → visible state → action → success → failure → recovery**.
API and Web share application behavior. Active is the actual immutable runtime snapshot; admitted
work retains its legitimate pin. Analysis/Preview has zero media mutation and no execution authority.
Only OrganizerExecutor mutates Storage after explicit effect permission. No silent overwrite/delete,
link fallback, unsafe path, secret leakage, successful-sibling replay or automatic uncertain replay.

Show bounded decision explanations. On failure identify item/stage, durable state, known effects,
safe repeatability and the legal next action. Retry alone is not recovery. Unknown submission outcomes
are reconciled from durable identity before another explicit attempt; reads never replay work.

## Configuration lifecycle

- **Goal/entry:** change runtime behavior through Settings/Configuration or focused business forms.
- **State:** JSON_BOOTSTRAP versus MANAGED authority; Draft/Validated/Active/Superseded, exact version/
  digest, references, validation/current evidence and capability readiness. Unsaved input is not Active.
- **Action:** explicitly create/resume a Draft or successor, edit typed objects, inspect impact,
  validate/test and checked-activate. Advanced whole-document JSON/import/export is a labelled support
  path; imports create inactive Drafts. Business-page Save bundles shared validation and activation.
- **Success:** one immutable candidate becomes runtime Active atomically; old work keeps its pin.
  Publication starts no media Task/Job, scheduled occurrence, notification or Storage mutation.
- **Failure/recovery:** stale/concurrent or invalid reference/evidence/runtime, denied permission or
  unknown Save is actionable. Known rejection preserves prior Active and correctable input. Refresh
  stale authority, repair named blockers, rerun relevant checks; verify unknown publication before
  resubmitting. Corrupt Active stays explicit, never silently falls back to Draft/cache/JSON.

[Configuration](configuration.md) owns exact fields, lifecycle APIs, secret references and checked
publication. Reference-safe removal preserves media, Results and historical snapshots; it cannot
silently publish unrelated Draft changes.

## First-time setup

- **Goal/entry:** authenticate a management-only installation and open `系统设置`
  (`/ui-v2/configuration`) or a setup-required page. Viewers get read state and admin guidance.
- **State/action:** distinguish no Draft, resumable Draft, empty Active and broken prior Active.
  Explicitly create the first Draft, inspect/export labelled JSON and activate empty or populated
  configuration. No mandatory media forms or generated Storage/type/policy defaults.
- **Success:** show `配置已激活，媒体业务尚未配置` for empty Active. Validate populated objects and
  their declared references; require applicable library/Storage/recognition/destination evidence,
  without blocking unrelated empty families. Browsing/transfer need not require the media pipeline.
- **Failure/recovery:** retain saved Draft and input across reload/reconnect without duplicate
  initialization. Fix named mount/secret/reference/schema/permission blockers. Broken prior Active
  uses recovery, not automatic first setup. Return to the allowlisted originating page and refetch.

JSON defaults to actual Active; before activation label Draft/no-Draft. Portable exports retain safe
environment references and supported managed fields, excluding database/principal/token deployment
authority and unsafe URL credentials. Advanced edits are backend schema/field-allowlisted; restart-
only settings are never presented as already consumed.

Fresh Compose needs no media mount. Local roots must be explicit paths visible to the running
container/UID/GID; host `/`, Docker socket and arbitrary unmapped paths are unsupported. Correct a
missing/denied root by fixing the mount/ownership or Draft path, then retry the bounded read/check.
V1's complete-configuration setup remains a compatibility path, not the native empty-first requirement.

## Storage management and root recovery

- **Goal/entry:** inspect or maintain configured locations through `存储管理` (`/ui-v2/storage`).
- **State/action:** real provider/identity/root, enabled/read-only/readiness and library references;
  typed add/edit/copy/enable/disable/reference-safe removal, or explicit Connection/Read check.
  No secrets/private host paths or mutation-based capability probes.
- **Success:** checked successor publication or bounded read evidence; supported transfers keep their
  own library-kind/pin. No media work from configuration management.
- **Failure/recovery:** name unavailable root/provider, stale Active, blocked reference, missing setup,
  schema/secret/permission issues and the correction/refresh/setup action. Preserve prior Active.
  Worker waiting leads to readiness diagnosis, not request resubmission or unsafe replay.

OpenList `rootPath` may be empty or `/`: display `提供商根目录` and preserve the exact provider-valid
value through Save, inventory, detail and Edit. Other providers retain their own rules. A failed
list read after Save is a read/presentation failure, not proof of rollback: verify durable state,
never automatically Add again, reset the database or move media. Existing saved values remain readable.

## Recognition and rules

- **Goal/entry:** manage the RecognitionRule→RecognitionType→four-policy graph at `/ui-v2/rules`,
  or inspect recognition/metadata decisions from an explicit test, Preview or Task recovery.
- **State:** actual Active, object identity/enabled state/references/readiness and separate unsaved
  candidate. Overview, bindings, types, rules and Metadata/Naming/Classification/Organize inventories
  open full-width without a selected editor. Add/Copy opens a drawer; Edit is a full-page route.
- **Action:** typed lifecycle/reference impact, exact object test or policy preview and one `保存`.
  Search/filter/navigation are read-only and create no Draft, Provider call or work. Forms retain
  correctable tab-scoped input, not credentials or publication authority.
- **Success:** focused whole-graph checked publication becomes Active for every consumer. Real rule
  priority/score/ambiguity/stop-on-match remains authoritative; one enabled binding per type. C keeps
  C under A Naming/Classification/Organize reuse. Save starts no work or execution authority.
- **Failure/recovery:** show incompatible condition/operator, unsafe regex/template/path, duplicate
  binding, missing/disabled reference, denied/stale/invalid response or Provider/test failure on the
  affected object. Preserve input/Active; refresh stale authority, inspect/repoint references and
  rerun necessary evidence. An unknown Save needs state verification before another submission.

Reference images define hierarchy/style, not real names, counts, conditions or backend algorithms.
TMDB remains the configured Provider abstraction; no implicit fallback or V1 Provider switching.
Production identity selection explains parser/rule/policy/candidate score; unrecognized/ambiguous/
below-threshold/credential/timeout/malformed evidence cannot fabricate an identity.

### Object-scoped tests and complete-flow checks

`测试与预览` tests the edited candidate and relevant inputs; `完整流程检查` is a separate Rules
Overview action using the exact complete graph. Local success does not imply production competition,
whole-flow readiness, publication or execution permission. Save still validates its whole successor.

| Edited object | Local test and visible outcome |
|---|---|
| RecognitionType | Validate identity/name/description/enabled state without binding/sample. Optional associated-rule tests report real output; no rules shows `类型定义有效；暂无关联规则可供试识别`. Never force that type or resolve unrelated policies. |
| RecognitionRule | Parse the submitted synthetic path and show bounded condition/group expected/actual/truth for this rule alone. Missing downstream bindings cannot turn a real local match into failure. Exact context stays visible; library selection never silently prepends a root. |
| Binding | Check type, uniqueness and four references. |
| Metadata | Offline configuration validity is distinct from credential/live identity; live testing is separate explicit intent and applies the configured policy. |
| Naming | Typed identity/episode/tag sample renders the actual Movie/TV template family without other policies. |
| Classification | Test its rules and MediaLibrary/safe path without Naming or Storage probes. |
| Organize | Explain own effects, permissions and capabilities; destination/conflict/execution readiness stays `未检查` until contextual complete-flow analysis. |

Non-match/not-applicable/disabled are honest outcomes. Show only applicable fields and named input/
reference corrections, never raw PolicyResolutionError. Offline local tests call no Provider or media
Storage and create no executable work. Evidence binds non-Active candidate/purpose/sample/context and
goes stale after relevant edits. Full-flow analysis retains real competition/policy resolution and
planning, labels synthetic identity, exposes missing stages and uses bounded read-only destination
checks; explicit live Metadata is separate.

### Naming and classification destination

Inspect policy IDs, rendered names/directory, MediaLibrary/path, operation/capability/conflict and
destructive effects before authorizing media work. Unsafe/missing/stale policy or destination fails
the affected action; correct the named reference and rerun the exact preview. No silent fallback.

New Classification rules use MediaLibrary plus safe `path`: root + path + Naming directory/filename,
without a library name/ID prefix. Labelled legacy `library/path` preserves old semantics until explicit
checked conversion with destination-impact acknowledgement. Preserve path; do not silently add a
legacy label. Old snapshots/Previews/Tasks/grants retain their original meaning; failed conversion
keeps prior Active and correctable input.

## Real Storage Files

- **Goal/entry:** browse physical sources at `文件` (`/ui-v2/resourcelib/files`), Dashboard or a
  ResourceLibrary link; MediaLibrary has the separate destination journey below.
- **State:** enabled ResourceLibrary cards, exact relative root/breadcrumb, bounded deterministic live
  entries/list/grid, paging, selection and meaningful capability/error state. No FileIndex membership,
  FileID/occurrence/fingerprint authority, recognition-result or organize-status feedback.
- **Action:** navigate/refresh/select a bounded file/folder scope, use ordinary maintenance or explicitly
  prepare organization. Viewing is a bounded read, never recursive discovery, Provider lookup or work.
- **Success:** exact names/paths survive normalization, hover/focus, breadcrumbs and long-name toolbar
  reflow. Boundary whitespace is visibly/assistively distinguished; shortening never changes identity.
  Refresh reconciles directory-tree memory/selection and removes vanished entries without losing a
  still-valid selected library/path.
- **Failure/recovery:** explain missing/denied root, timeout/provider, invalid/stale cursor/path,
  capability/conflict or escape. Correct binding/path or retry the bounded read; absent paths never
  trigger alternate trimmed-path guesses. Preserve read-failure state when the current directory vanished.

Library cards show icon/name/selection/menu, no Storage/root/count/capacity. Selected context shows
enabled state and exact configured path only, not a repeated name. Disabled libraries are hidden
truthfully with an existing Web re-enable path. The immutable visual references and responsive/
keyboard states are in [Files specification](file-page-visual-spec.md) and
[MediaLibrary specification](media-library-page-visual-spec.md).

### Common file maintenance

Use toolbar/selection bar or an accessible entry context menu to create folder/text, rename one
entry, Copy/Move/Delete or edit allowlisted bounded text. Folders open on left click; no inline Open
button. No browser Upload/Download, arbitrary binary/media editing, host paths, root delete or
unbounded recursion. These commands do not run media recognition/metadata/naming/planning/Preview or
require raw execution tokens; backend confinement, capabilities, authority and audit still apply.

Show exact source/destination/library kind, operation, current evidence, bounded impact, per-item
progress/conflict/partial effects and explicit Delete/Replace/Save intent. Transfer byte totals are
impact/progress, not an admission ceiling; selection/entry/depth/path/manifest/control projections
remain bounded. Cross-Storage Move explicitly Copy→digest-verify→Delete-source; failed verification
preserves source. Same-Storage requires advertised native capability and no silent fallback.

Rename/Delete use kind/library/Storage/root/pin/path/type/size/mtime evidence without reading media
bytes; provider fingerprints are optional but remain binding once observed. Text Edit binds its own
loaded-content digest. External replacement/check-to-write windows remain provider observation
limits. Delete asks once after current bounded scope/impact. Long/batch commands persist independent
Task/results and cooperative controls; unknown admission is read back by exact request. Correct a
name/destination, refresh/reopen changed input or explicitly continue only known-safe remaining work.
Uncertain effects are investigated; index reconciliation failure never replays a mutation.

### Library Add/Edit/removal

Add ResourceLibrary from `+ 添加资源库`; edit either library kind through its selected-card menu.
The three-step drawer is `基本信息 → 存储位置 → 确认`, opened only by explicit intent. Edit loads exact
Active, keeps ID read-only and allows name/enabled/Storage/kind-relative root while preserving hidden
configuration. One Save/`保存并激活` composes shared structural/reference/applicable checks and atomic
runtime publication; no ordinary Draft/Validate/Activate ceremony.

Success makes an enabled library selectable. Storage/root changes return to that root; a name-only
edit preserves a valid directory. Disabled results remain labelled/recoverable. Changes are
configuration-only and never create/move/migrate/delete physical contents. Reference-protected
removal differs from Delete of interior entries. Invalid/duplicate/stale input, failed checks,
persistence or activation/runtime errors preserve prior Active and correctable fields; refresh
stale authority and explicitly resubmit only after unknown outcomes have been verified.

## CURRENT — MediaLibrary files and separate ResourceLibrary navigation

- **Goal/entry:** maintain destination files at `媒体库` (`/ui-v2/medialib/files`). Old `/ui-v2/library`
  and `/ui-v2/library/files` provide explicit recovery links without automatic work or redirect.
- **State/action:** the shared cards/tree/exact breadcrumbs/list-grid/selection/paging, ordinary
  maintenance and Add/Edit/removal above. No library-card statistics/placeholders/thumbnails or
  thumbnail collection. Per-file size, selected count/known size and bounded impact remain visible.
- **Success:** live entries are independent of prior organization/index membership, and enabled Save
  publishes actual Active. Copy/Move uses MediaLibrary endpoints for both sides on same/across Storage;
  equal IDs never exchange ResourceLibrary/MediaLibrary scope or evidence.
- **Failure/recovery:** missing Active/library, unavailable root, denied/unsupported action, conflict,
  stale input, partial or unknown effect stays per-item. Use Web configuration/re-enable, choose another
  library/root, refresh/revalidate or inspect durable Task/results. No replay on refresh/reconnect.

No MediaLibrary Organize/Scan/Preview, general cross-kind direct transfer, browser Upload/Download or
arbitrary media edit. Source Files retains its separate organization and return context.

## FileIndex and Media

FileIndex is still a separate baseline catalog/runtime dependency pending complete Slice45 RO-7
retirement. It is never physical listing or Files-originated execution authority. Do not present
retirement as delivered merely because Files already reads live Storage.

The baseline catalog distinguishes discovery/stability, processing disposition, current occurrence
and current/historical/unverified Results. Search/filter/detail explains parser/recognition/metadata,
policies/target/history, blockers/checkpoint and allowed next actions. Missing/truncated/unavailable
evidence stays labelled. Exact eligible Reprocess records intent only, never processing/mutation.
Retired direct re-recognition/re-match/re-plan/review-retry surfaces remain absent. Reads neither
rebuild plans nor contact Providers; use current legal review/Preview/Task recovery when needed.
Optional existing index sync is an independent recovery state, never permission to replay media.

## Manual organize

- **Goal/entry:** explicitly organize selected live ResourceLibrary files or bounded folders from
  Files/Operations. MediaLibrary is not a new source. Legacy indexed paths are separate and cannot
  authorize physical Files selection.
- **State/action:** exact source identities, durable intent, allowed recognition/metadata/classification
  choices, zero-mutation plan/attachments/conflicts/capabilities/effects and selected items. Review
  the plan and separately confirm exact execution plus any permitted overwrite/source cleanup.
- **Success:** server-held short-lived single-use authority binds authenticated principal, immutable
  plan/configuration/item subset/effect scope; atomic admission consumes it and returns durable work.
  Worker rechecks reviewed Storage/path/fingerprint directly and OrganizerExecutor executes only that
  scope. No CLI issuance, raw token transfer or FileIndex re-resolution for normal V2 work.
- **Failure/recovery:** source/plan change, stale permission/pin, conflict, capability or pre-mutation/
  partial/unknown effect explains durable state per item. Re-analyze the legal scope and obtain fresh
  intent when necessary; completed/ignored/uncertain siblings are not re-executed.

V1's explicit one-shot token remains an administration/API-automation/support mechanism, never a
replacement for the normal V2 journey. Source preparation cannot accept browser-provided raw Storage
paths, fingerprints, occurrences or IDs as execution authority. In-context summary/confirmation is
the active Task Center target below; separate Preview is no longer a required organizing-page action.

### CURRENT — Bounded folder organization with safe discovery restart

Explicit Files/Operations discovery shows pinned scope, progress/exclusions, real stability waiting
and read errors before freezing sources for exact planning/confirmation. At most 100 selected scopes
and 100 primaries; pinned filtering/depth and true elapsed stability apply to direct and walked files.
Matching enabled trailers attach to the retained main even in explicit mixed selection. Exact legal
long names survive handoff; first stat/old mtime/lost observation is not a stable-size interval.

Normal Pause/Continue/cancel is cooperative. If safe unfrozen continuation cannot be proved, retain
stage/findings/zero media effects, settle/fence the old attempt and offer visibly distinct explicit
new discovery. No automatic restart on read. Unknown admission recovers the proved original request
or stays unresolved with native inspection, never another root/pin or a guessed newer attempt.

Read errors preserve unaffected findings for an explicitly reviewed known subset. Material bounds
cannot expose an executable first-N prefix. Repeated/concurrent Freeze converges on one linked intent.
Seamless continuation across every old duplicate, activation/crash/control combination remains
explicitly deferred; exact pins, source checks, independent results and non-replay are mandatory.
Discovery controls/progress/readiness and return-to-Files remain visible in Operations.

## Tasks, results and per-item recovery

- **Goal/entry:** find one admitted run from Task Center, Files, Dashboard, Automation or a Task/Job
  deep link, then understand and safely resolve its actual files. Default list has no open detail.
- **State:** server-authorized search/filter/time/paging/counts and historical name/scope/trigger;
  queue/Task stage/item outcome/problem/effect certainty are distinct. Only durable Job→Task links
  deduplicate runs; pre-Task failures and independent occurrences/continuations remain visible.
  Task and file counts differ; attention overlaps and ordinary queued state is not a human blocker.
- **Action:** inspect detail, source/target/policies, completed primary/attachment steps, relevant
  audit/logs and bounded secret-free JSON; use backend-advertised pause/cancel/continue or enter the
  current task/type's recognition, Metadata, classification, conflict or failure handling.
- **Success:** durable per-file Results and linked recovery attempts survive reload/reconnect/restart.
  Queue completion cannot overwrite Task failure/partial/unknown state. Current Active cannot rename
  historical work or substitute its legitimate pinned context; unavailable totals never become zero.
- **Failure/recovery:** show missing/stale Worker, pin/dependency, denied/stale decision, source change,
  known partial or uncertain effects with legal next action. Retain input/successful siblings. Controls
  distinguish request from acknowledged effect; they do not interrupt an in-flight call or roll back.

Continue rechecks exact remaining safe scope, current authority and fences; consumed/revoked grants
are not reissued. Recognition selection/ignore, persisted Metadata candidate/correction/ignore,
classification and conflict use backend-offered legal inputs. Saving is non-executing. Bounded single/
batch failed-analysis recovery keeps independent admitted/refused items and linked original history.
Repair dependencies or save a legal decision, explicitly re-analyze, handle any new blocker, inspect
new summary/remaining steps and confirm the eligible subset. Admission/running is not resolution;
repeated failure supplies its new cause. Original pin unavailable means refusal/recovery guidance,
not silent repinning or arbitrary historical Reprocess. Unknown effects offer evidence/source-target
inspection/log-export only, never retry/force-replay/automatic rollback.

Primary verified success remains complete despite attachment failure/unexecuted/conflict warnings.
Retain each attachment's cause/source/target/completed steps and guidance from actual fixed
OrganizePolicy; human movement is only a policy-permitted example. Warnings remain visible, no
attachment-only automatic recovery or main-file replay. Preparation-only unready findings stay in
preparation and do not fabricate execution recovery work.

## Scheduled unattended organization

- **Goal/entry:** configure reusable bounded ResourceLibrary/schedule intent in Automation and inspect
  due occurrences, granted authority and linked results.
- **State/action:** enabled/published/readiness/grant/revocation are distinct; inspect interval/Cron/
  timezone/next due, run exact zero-mutation Preview and separately grant scoped revocable unattended
  authority. Valid due runs need no repeated per-run click. Enable alone is not authority.
- **Success:** Scheduler emits idempotent snapshot-pinned Jobs; existing Worker/Task/Result pipeline
  checks current authority/scope/capability/conflicts before each unperformed mutation.
- **Failure/recovery:** invalid pin/reference/secret/provider, instability, conflict or revoked grant
  stops affected work with next action. Correct/publish/Preview and regrant when scope changed;
  inspect independent checkpoints without replaying known/uncertain effects.

Automatic organization is the only supported definition mode in current code; removed Scan intents
cannot be reinterpreted as execution permission. Diagnostic/supported scheduled Preview stays separate.
This is the implementation baseline. Slice45's Preview-retirement TARGET below removes that independent
product and carries necessary analysis/authorization checks into shared organizing behavior.
The remaining native Automation workspace, Run once, metrics and engine-settings redesign is frozen
under 43; merged code presence and historical B PASS do not confer current acceptance or resume it.
[V2-AUTO requirements](v2-requirements.md#automation-workspace-requirements--target-slice-43) retain
complete targets including complete bounded discovery, manual/scheduled authority separation,
truthful historical metrics and actual resident settings consumption. Necessary45 coupling cleanup
need not preserve its old UI; future redesign requires a newly confirmed Contract.

## Operations administration

Configuration/Settings manages exact Active/successor and reference-safe object lifecycle; versioned
secret-free configuration/result exchange stays explicit. Notifications manages Webhook definition/
events/secret references, exact test, enable state, deliveries, leases/dead letters and recovery.
Actions share RBAC/audit/validation and preserve prior Active/correctable input on failed Save.

Delivery failure never changes media results. Retry/requeue is scoped to the delivery, with bounded
safe backoff and durable target identity; missing/changed target waits/refuses rather than silent
retargeting. Correct endpoint/secret/configuration then explicitly use its permitted recovery.
Payloads/secrets/raw exception details are not read-projection fields. Settings target publication
must not be confused with a resident consumer's actual adopted value.

## Docker self-hosted operation

Start/inspect/restart/backup/preflight/upgrade from [Deployment](deployment.md); verified non-overwriting
offline restore is in [Release](release.md#offline-restore-procedure). Four independent services,
local `/data`, explicit Local media mounts and non-root permissions retain process isolation.
TLS/certificates/proxy/public exposure and environment-secret injection are deployment-owned.

Worker/Scheduler/Notification Worker start and wait without Active/media mounts, then adopt eligible
configuration without routine restart. Scheduler never uses stale configuration; Notification Worker
never burns targetless claims or retargets durable deliveries. Older intact work pins remain usable
independently of new-admission Active; broken pins fail before mutation. Process liveness, DB/schema/
registration/heartbeat and command/pin readiness are separate; no-Active waiting is not a dead process.
Recoverable DB/config faults retain processes/work with bounded reasons. No API process supervision.
Adding mounts may recreate containers; publication alone does not. Schema/mount/permission/secret/
upgrade failures explain the fix, preserve backup/previous artifact and never replay uncertain media.

## V2 Operator Web migration

The shared responsive light shell provides persistent navigation, identity/connection controls,
safe deep links and bounded return context. Root opens Overview/Dashboard. Memory-only token auth
continues supported routes; reconnect never replays work. A 401 clears rejected authority/query state;
a 403 retains identity and offers legal navigation. Disconnect clears token/cache/intended route.
Show loading/empty/success/transport/malformed/unauthorized/forbidden/unavailable/not-found distinctly.
Dashboard/refresh/list/navigation are read-only, with no Provider/work/mutation. No independent Node
production service, replacement identity model or implicit V1 cutover is introduced.

### TARGET — 任务中心与分类恢复（Slice45）

The complete selected journey is [Task Center page specification](task-center-page-spec.md),
`V2-OPS-009–012` and the committed Slice: nine sibling task/recovery lists; bounded live selection;
zero-mutation preparation; same-interface exact plan summary followed by explicit ready-subset
confirmation; task/type-scoped native decision/re-analysis/recovery with independent results.
No ordinary separate Preview page/CLI/internal authorization-material burden. Global type lists
use current durable problems over the complete authorized population, not page-only filtering.

The specification defines all five recovery inputs, summary/attachment/effect warnings, new-blocker
transitions, precise confirmation and refresh/restart/unknown-response behavior. Scan products,
definition modes and dedicated retirement/compatibility layers are absent on first deployment;
old routes/commands/types ordinarily reject before discovery/admission/authority. Shared internal
filtering/real stability/planning/diagnostics and supported-work safety stay intact. No old Scan
migration/history/settlement obligation or existing media/runtime clearing. This target selection
and B Task PASS do not declare the whole Slice delivered.

### TARGET — FileIndex 退出与 CLI/两种库页实时列表（Slice45）

[FileIndex retirement design](file-index-retirement-spec.md) and `V2-FILES-005/006` define the complete
CLI/ResourceLibrary/MediaLibrary same-library live list journey and removal of all global-index
products/consumers/schema/sync/repair/stand-ins. Browse/refresh/page creates no catalog/observations/
work/authority, Provider/Hash or media effects; explicit work retains exact evidence/results/audit.
Old indexed inputs offer library browsing/Task Center guidance, no compatibility engine or data clear.
No-index real stability→summary→confirmation→execution→recovery/reopen is required before acceptance.

### TARGET — 独立 Preview 首次部署退出与分析统一（Slice45）

[Preview 退役设计](preview-retirement-spec.md)、`V2-OPS-013` 和 RO-8 将独立 Preview 产品按
Scan 相同的首次部署标准移除：独立 V1/V2 页面、CLI/API、Job/Task/定时/Worker/继续路径、
专用持久化和运行装配均不存在。旧输入普通 not-found/参数/不支持类型错误，无退役页/410/
提示/兼容执行器或自动转成整理；不建设旧 Preview 停止/接管、迁移、历史或 V1 parity 服务。

操作者在整理创建/Files 或原任务恢复界面显式分析，直接检查当前计划摘要和逐项原因，选择
合法就绪子集后明确确认。CLI organize 不带 --execute 继续显示完整零媒体变更分析。
未就绪或发现冲突留在准备界面，不制造正式执行待办或单次/无人值守权限；需要修正时在原
界面补充决定并重新分析。来源/计划变化需更新摘要和意图，成功/未知效果不得重放。

Rules、配置检查和 Automation 授权前校验复用共享分析/精确计划，并保持原候选配置/定义/
权限边界；无需用户管理独立 Preview Task。支持工作的计划/pin/结果/审计和正常重启恢复
保留，不清空媒体/运行库；只清理必要 Automation 耦合，不恢复冻结工作区重设计。
这是新增 TARGET，不把 Task45.4 Scan PASS 当成 Preview 退役验收。

## V1 and post-V1 boundary

V1 `/ui` and shared API authority remain until explicit cutover/parity acceptance. Current delivered
workspaces do not include cross-Task bulk mutation, arbitrary historical Reprocess, universal rollback,
automatic uncertain replay, Provider switching/new production Providers, built-in users/session/OIDC,
general Secret Store or specialized email/chat/media-server channels. Selected45 cross-Task problem
lists supersede earlier deferral of those lists only. Active/frozen scope and earlier accepted
exceptions are authoritative in Slice/Progress; documentation consolidation does not extend them.
