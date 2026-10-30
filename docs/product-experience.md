# MediaFlow Product Experience

This document owns operator journeys and completion semantics. Stable scope/IDs live in
[Requirements](requirements.md) and [V2 Requirements](v2-requirements.md); technical boundaries in
[Architecture](architecture.md). [Progress](progress.md) records accepted baselines and deferrals.
The committed [Slice](../SLICE.md) owns current scope. Accepted live-list/retirement and Automation
workspace/settings foundations remain; current journeys include the accepted46 entry, readability,
work-ownership and execution-intent amendments.
Detailed superseded delivery notes are retained at
`865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/product-experience.md`.

## Current journey boundary

Current journeys below incorporate accepted Slice46 amendments: `V2-UX-004`, `V2-OPS-014–017`,
`V2-FILES-007` and `V2-AUTO-010/011`. Historical43/45/46 acceptance facts and original deferrals
remain in [Progress](progress.md) and their Git Contracts; they are not additional operator steps.
Files owns new manual selection and ordinary-file progress; Task Center owns admitted organizing
progress and four business recovery types; Automation owns saved-definition scheduled/one-run intent.

## Readable actions and Entry

Open Entry or a V2 page/dialog → distinguish text, availability and focus → submit the permitted
action → read success or bounded failure/recovery. Shared primary/secondary/danger/link/icon actions
and directly related Entry fields stay legible in normal, hover, focus, selected, busy and disabled
states. Enabled text meets AA contrast; keyboard names/focus and duplicate-submit guards remain.
Authentication continuation and memory-only credentials are unchanged; reconnect never replays a
command. This is the shared light theme, without a new identity or theme-customization product.

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
- **Presentation:** the workspace content header contains one `整理规则` title, a short description
  and `刷新`, following the Task Center header hierarchy. The shared topbar keeps account/notification
  controls. The eight category cards and seven inventory layouts retain their design. Overview
  shows Chinese relationship labels, real total/enabled counts, conditional gaps/dependency guidance
  and the separate complete-flow check at the bottom; it has no inventory search. Each family keeps
  one local search and its existing state filter.
- **Action:** typed lifecycle/reference impact, exact object test or policy preview and one `保存`.
  Search/filter/navigation/refresh are read-only and create no Draft, Provider call or work. A
  successful refresh retains the current family, keyword, state filter and unsaved input; changing
  family clears the keyword. Busy refresh is visibly unavailable. Forms retain correctable
  tab-scoped input, not credentials or publication authority.
- **Success:** focused whole-graph checked publication becomes Active for every consumer. Real rule
  priority/score/ambiguity/stop-on-match remains authoritative; one enabled binding per type. C keeps
  C under A Naming/Classification/Organize reuse. Save starts no work or execution authority.
- **Failure/recovery:** show incompatible condition/operator, unsafe regex/template/path, duplicate
  binding, missing/disabled reference, denied/stale/invalid response or Provider/test failure on the
  affected object. Preserve input/Active; refresh stale authority, inspect/repoint references and
  rerun necessary evidence. An unknown Save needs state verification before another submission.
  Authentication/read failures use the shared boundary without presenting stale data as refreshed
  or resubmitting commands. No Active remains distinct from an empty Active graph and offers Settings
  recovery with the originating family preserved. The normal workspace omits the sequence/Settings
  utility row; Settings retains version/digest diagnostics and ordinary sidebar access.

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
  submit organization into its durable task. Viewing is a bounded read, never recursive discovery,
  Provider lookup or work.
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
Uncertain effects are investigated; result persistence or display failure never replays a mutation.

“当前页面操作状态” sits immediately left of 添加资源库 / 添加媒体库 with the same button style.
It opens a centered modal for that library kind/source's multiple ordinary operations, progress,
independent item results and existing backend-permitted controls/recovery. Close/reload/reconnect/
service restart can reopen durable work; browser memory or one overwritable hint is not the only
index. Hints remain principal-isolated and non-authoritative. Missing/removed/pin-restricted history
explains its restriction instead of rebinding to current Active. Empty/loading/read-error states and
keyboard dismissal stay usable; closing neither cancels nor replays. Unknown effects stay inspection-
only, success refreshes live Storage without discarding unaffected selection/siblings, and no global
ordinary-operation center or new retry/undo authority is introduced.

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

## CURRENT — Live lists without FileIndex

CLI `mediaflow files list`, ResourceLibrary Files and MediaLibrary share the same bounded live
Storage browse. Select exactly one library kind/ID and relative directory; preserve exact names,
kind-bound pagination and unknown totals. Missing Active/library, confinement, stale cursor,
permission and Storage failures explain the next safe read/configuration action, never an empty
index fallback. Listing creates no catalog/observation/work/result/authority or Provider/Hash/media
effects and does not initialize or upgrade a database.

FileIndex products, global catalogs, repositories, schema and sync/reprocess/repair dependencies
are removed. Old indexed inputs provide library-browse/Task Center guidance without a compatibility
engine. Explicit organizing/maintenance/recovery retains work-scoped source evidence, plans, pins,
results and audit; no existing runtime data or media is cleared.

## Manual organize

- **Goal/entry:** explicitly organize selected live ResourceLibrary files or bounded folders from
  Files only. Task Center continues existing admitted work. MediaLibrary is not a source, and
  indexed paths provide no admission.
- **State/action:** exact source identities, durable intent, allowed recognition/metadata/classification
  choices, zero-mutation plan/attachments/conflicts/capabilities/effects and selected items. The
  Files command admits its durable pinned task before business readiness; rule/metadata/target/
  conflict resolution then happens inside that work. Review
  the plan and separately confirm exact execution plus any permitted overwrite/source cleanup.
- **Success:** server-held short-lived single-use authority binds authenticated principal, immutable
  plan/configuration/item subset/effect scope; atomic execution admission consumes it inside the
  already admitted organizing work.
  Worker rechecks reviewed Storage/path/fingerprint directly and OrganizerExecutor executes only that
  scope. No CLI issuance, raw token transfer or FileIndex re-resolution for normal V2 work.
- **Failure/recovery:** source/plan change, stale permission/pin, conflict, capability or pre-mutation/
  partial/unknown effect explains durable state per item. Re-analyze the legal scope and obtain fresh
  intent when necessary; completed/ignored/uncertain siblings are not re-executed.

V1's explicit one-shot token remains an administration/API-automation/support mechanism, never a
replacement for the normal V2 journey. Source preparation cannot accept browser-provided raw Storage
paths, fingerprints, occurrences or IDs as execution authority. In-context summary/confirmation
belongs to the admitted task and its exact preparation; no independent Preview product remains.
Files keeps bounded task/preparation history and exact unknown-request reconciliation after close/
reload/reconnect, without the former center discovery list or guessed request/library. Generic new
URLs guide to Files without work; valid prepared-work links keep their legitimate exact context.
Browsing/separate analysis creates no organizing task or execute intent; admission/decision Save
does not authorize media effects. Four business blockers stay native to the admitted task.

### CURRENT — Bounded folder organization with safe discovery restart

Explicit Files-originated discovery inside the admitted task shows pinned scope, progress/exclusions,
real stability waiting and read errors before freezing sources for exact planning/confirmation.
At most 100 selected scopes and 100 primaries; confinement, pinned depth/budgets and real stability
apply to direct and walked files. Direct file business checks are same-source unfinished work and
explicit extension exclusion; a merely unlisted suffix or automatic include/rule miss cannot veto it.
Selected folders retain configured primary-media extensions, defaulting to video, and existing
attachment settings: pictures/subtitles/NFO are not standalone primaries/problems, artwork-off does
not promote them, other-same-stem remains effective, and unassociated files stay at source.
The folder task exists before traversal; concrete discovered sources are atomically reserved at
item admission across manual/Automation/continuation work. Equal names are not source identity,
eligible siblings remain independent and a finished history row is not a perpetual entry lock.
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
Discovery controls/progress/readiness and return-to-Files remain in the exact admitted task/
preparation context, with no global discovery block.

## Tasks, results and per-item recovery

Use All/Running/Attention/Ended plus Recognition/Metadata/Classification/Conflict over the same
backend-authorized organizing population, before counts/paging/options/detail. Ordinary-file,
notification and separate analysis-only work stay outside; no center new-task picker/global Worker/
discovery/manual-operation blocks or their exclusive landing reads remain. Normal manual initial
WaitingConfirm stays unfinished in Running/All with exact summary access, outside Attention.
Attention/pending tasks are the distinct four-type union; type/file counts stay distinct. Required
human decision→analysis→summary/confirmation steps retain their four-type lineage, while plain
queued/running follow-ups do not invent a human blocker. Real resolution clears the problem; a new
business blocker changes type, a solely technical follow-up failure becomes factual All/Ended history.
Only verified exact linked success for every necessary item permits Completed/recovered display,
without rewriting attempts or double-counting recovery. Mixed technical/ignored/uncertain siblings
never become all-success just because the business problems cleared. Provider transport failures are
not Metadata decisions, and other terminal failures have no separate failure statistics or generic
center recovery guidance/actions. Administrative API/CLI recovery remains outside this V2 UX.

- **Goal/entry:** find one admitted run from Task Center, Files, Dashboard, Automation or a Task/Job
  deep link, then understand and safely resolve its actual files. Default list has no open detail.
- **State:** All eight views expose only creation-date range selection and clear; clearing restores
  the current view's complete authorized population. This applies to the page-level task list;
  detail and problem-handling inputs retain their own scope. Time, valid paging and counts use
  the complete server-authorized population, alongside historical name/scope/trigger;
  queue/Task stage/item outcome/problem/effect certainty are distinct. Only durable Job→Task links
  deduplicate runs; pre-Task failures and independent occurrences/continuations remain visible.
  Task and file counts differ; attention overlaps and ordinary queued state is not a human blocker.
- **Action:** inspect detail, source/target/policies, completed primary/attachment steps, relevant
  audit/logs and bounded secret-free JSON; use backend-advertised pause/cancel/continue or enter the
  current task/type's recognition, Metadata, classification or conflict handling. Other technical/
  uncertain failures remain factual read-only All/Ended history, with no generic center recovery.
- **Success:** durable per-file Results and linked recovery attempts survive reload/reconnect/restart.
  Queue completion cannot overwrite Task failure/partial/unknown state. Current Active cannot rename
  historical work or substitute its legitimate pinned context; unavailable totals never become zero.
- **Failure/recovery:** show missing/stale Worker, pin/dependency, denied/stale decision, source change,
  known partial or uncertain effects as factual history. Four-type decisions and supported live
  controls retain legal next actions; no generic terminal-failure recovery is added. Keep input and
  successful siblings. Controls
  distinguish request from acknowledged effect; they do not interrupt an in-flight call or roll back.

Continue rechecks exact remaining safe scope, current authority and fences; consumed one-shot
permission is not reissued and withdrawn scheduled intent is not bypassed. Recognition selection/
ignore, persisted Metadata candidate/correction/ignore,
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

- **Goal/entry:** save bounded ResourceLibrary/scope/schedule intent in Automation, review its source,
  limits and policy effects, then explicitly enable or save an enabled successor.
- **State/action:** disabled-first create/copy; checked publication validates current execution and
  configuration permissions. Enabled supplies scheduled intent without an independent grant or
  mandatory pre-analysis. Enablement creates no immediate work; due occurrences need no per-run click.
- **Success:** Scheduler emits one immutable pinned Job; Worker/Task/Result and OrganizerExecutor
  perform full planning/source/capability/conflict/authority checks and preserve independent results.
- **Failure/recovery:** disable/removal/current permission loss stops future admission and remaining
  scheduled effects at safe boundaries, with no rollback or historical replay. Four business problems
  use Task Center decision→analysis→summary→explicit continuation; other failures retain truthful history.
  Healthy empty is no-work; unstable/unreadable/incomplete is never fabricated empty success.

Run once is a separate explicit execution of the saved scope, even while disabled, without changing
its schedule or requiring another initial confirmation. Full bounded traversal and real stability
precede effects. Old grants/revocations and analysis records remain history; they cannot override
Enabled or execute an old preparation. Only automatic organization remains; Scan/Preview/FileIndex
products remain absent. Run once retains min(definition itemLimit,100) and complete traversal budgets.
Both automatic entries retain real age/size stability: age uses the larger configured minimum-age/
modified threshold; nonzero stable-size requires unchanged observations separated by real elapsed
duration, never old-mtime inference. If no files are ready and unstable candidates
remain, perform at most one wait/re-scan when the shortest remaining interval is in (0,60] seconds.
Ready siblings proceed without waiting; longer intervals do not synchronously wait. Remaining unstable
files fail unmodified, with Failed/PartialSuccess reflecting real outcomes outside Attention. Later
normal runs use normal scope/checks; no failed-item selection or cross-run observation mechanism.

### CURRENT — Complete native Automation workspace (accepted43, amended46)

- **Entry/state:** shared-shell `自动化` opens the real definition inventory; name/打开/direct links
  read saved definitions before/after enablement, including truthful disabled/unavailable states.
  Malformed/denied/not-found/read errors remain bounded; no grant-eligibility dependency returns.
  Inventory provides `任务列表 / 执行记录 /
  全局设置`, population metrics, source/scope/schedule/timezone/limit, next/latest outcome and distinct
  published/enabled/execution-readiness states. No editor opens automatically or sample data appears.
- **Configure/authorize:** New/copy starts disabled without authority. One focused checked Save
  publishes only the intended definition. Checked enable/enabled-successor Save supplies scoped
  scheduled intent with current execution permission and audit; there is no independent grant or
  mandatory grant analysis. Confirmed Save reconciles the same editor's values/publication identity
  so another Enabled edit/Save works, preserving later typing. Peer conflicts preserve input. Unknown
  Save/toggle uses “核对本次发布” to read exact principal/action/candidate/base/activation evidence
  without reposting; unknown Run once reconciles only its own principal/request identity.
- **Scheduled success:** each valid due occurrence creates one linked pinned run and executes through
  the existing Worker/OrganizerExecutor without another per-run click, with independent item results.
- **Run once:** use the published definition's saved scope to discover/freeze a complete bounded
  manifest without asking the user to pick files again. One explicit command admits the organizing
  Task before readiness and executes ready items without a second initial confirmation. Four-type
  recovery still needs explicit continuation; no schedule advancement or old grant consumption.
  Overflow/incomplete scope refuses execution and explains narrowing/re-analysis, not first-N success.
- **Execution records:** keep the Automation records page read-only, showing status/results, failure
  stage/reason, known effects and repair/Task Center links; no local file decisions, re-analysis or
  execution controls. Bounded authoritative queries reach every authorized row; actual admitted runs
  count once, unavailable/unknown data are not zero/success, and bound reached is not scope exhaustion.
- **Before organizing starts:** explain the failed prerequisite and link its correction. Proven
  pre-start failure rows remain visible alongside normal/no-work records, including existing history;
  absent per-item results/media effects do not mean the history is unreadable. Refresh is the same
  read-only query, not another attempt. After repair,
  explicitly retry through existing supported commands only if durable evidence proves no formal
  execution/media effects and the old attempt is settled/fenced, with current permissions/context/
  authority rechecked. Do not duplicate queued work or silently repin a changed definition; unsupported
  old-context retry instead explains an explicit new Run once or next scheduled evaluation. Unknown
  submission/handoff reconciles first, never blindly retries.
- **After organizing starts:** durable formal organizing-task handoff, not the first media mutation,
  routes organizing history/controls to the exact Task Center run. Four business problems retain
  native recovery; technical/uncertain outcomes stay factual read-only history, including failures
  before moving any file. A missing link does not prove pre-start;
  uncertain effects permit investigation only. Preserve return context, successful siblings and
  independently linked recovery attempts; recovery never rewrites the original run result.
- **Read/save safety:** stale/failed Save retains Active/input; reads/refresh/paging create no work or
  Provider/media effects. Preparation-only findings remain distinct from execution failures.
- **Settings:** one four-field Save preserves unrelated Draft/configuration. Capacity is pending+
  running Job count, stale age is no-update observation, and Worker/Scheduler polling must be
  adopted by actual resident loops without routine restart. Published/adopted/pending/override/
  stale or unavailable consumers have truthful readback and concrete repair guidance.
  Each fresh live instance must prove its own adoption. Stopped/expired predecessors remain folded
  diagnostic history with a bounded display and real total; they neither veto nor prove current
  adoption. A healthy replacement restores completion, while missing services, unreadable evidence
  and any real live pending/overridden replica still refuse collective success.

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

### Task Center integration

[Tasks, results and per-item recovery](#tasks-results-and-per-item-recovery) owns the organizing
journey; [Task Center specification](task-center-page-spec.md) owns eight-view interactions, exact
summary/confirmation and native four-type forms. Supported legacy Task/Job links resolve into that
exact organizing context or the proven ordinary-operation library page; missing/denied/unavailable
identity stays a bounded read-only explanation, with no generic failure recovery or guessed work.

The center has one page title, with content boundaries and spacing coordinated with MediaLibrary.
The shared shell keyword input is not shown there. The selected tab supplies current-view context;
no duplicate view heading or generic description appears between the tabs and filters. All eight
views share a compact 创建日期 group with independently named native 开始日期/结束日期 controls,
apply either or both sides without a search submission, and clear back to the current view’s
complete authorized population. The toolbar's low-emphasis 清除 appears when a date is set;
existing empty/read-error recovery entries remain available in their applicable states.
The summary's routine population/pagination/Job-Task explanation is omitted, as are the 本地时区
label and 时区说明 control/content. Local-calendar filtering, full end-day inclusion, explicit
list/detail time offsets and authoritative statistics/deduplication retain their existing behavior.
Filters and table align, and controls wrap without clipped text
or page overflow when narrow or when the selected detail reduces available space.
Manual refresh shows 刷新 / 刷新中…
without layout jumps; background polling updates quietly. Normal same-query refresh preserves
visible lists/details and valid context; real changes and read/permission failures remain visible.
Management-API consumers outside that control keep their existing filter semantics.
Long names/scopes retain readable status/progress columns and complete mouse/keyboard-accessible
identity. Using the shared Files sidebar entry opens ordinary ResourceLibrary browsing without a
task-center return button, including when leaving a Files visit that already carried one. Explicit
task/preparation/organizing links retain their own exact return context through reconnect; ordinary
page navigation does not start a new organizing journey or discard durable work.

### CURRENT — FileIndex 退出与 CLI/两种库页实时列表（Slice45）

[FileIndex retirement design](file-index-retirement-spec.md) and `V2-FILES-005/006` define the complete
CLI/ResourceLibrary/MediaLibrary same-library live list journey and removal of all global-index
products/consumers/schema/sync/repair/stand-ins. Browse/refresh/page creates no catalog/observations/
work/authority, Provider/Hash or media effects; explicit work retains exact evidence/results/audit.
Old indexed inputs offer library browsing/Task Center guidance, no compatibility engine or data clear.
No-index real stability→summary→confirmation→execution→recovery/reopen is covered by acceptance.

### CURRENT — 独立 Preview 首次部署退出与分析统一（Slice45）

[Preview 退役设计](preview-retirement-spec.md)、`V2-OPS-013` 和 RO-8 将独立 Preview 产品按
Scan 相同的首次部署标准移除：独立 V1/V2 页面、CLI/API、Job/Task/定时/Worker/继续路径、
专用持久化和运行装配均不存在。旧输入普通 not-found/参数/不支持类型错误，无退役页/410/
提示/兼容执行器或自动转成整理；不建设旧 Preview 停止/接管、迁移、历史或 V1 parity 服务。

操作者在整理创建/Files 或原任务恢复界面显式分析，直接检查当前计划摘要和逐项原因，选择
合法就绪子集后明确确认。CLI organize 不带 --execute 继续显示完整零媒体变更分析。
独立分析的未就绪或冲突留在准备上下文，不产生正式执行待办或权限；明确 Files 整理或
Automation Run once 已受理的任务则在四类原生恢复中补充决定、重新分析并明确继续。
来源/计划变化需更新摘要和意图，成功/未知效果不得重放。

Rules、配置检查和整理执行前的内部校验复用共享分析/精确计划，并保持原候选配置/定义/
权限边界；无需用户管理独立 Preview Task。支持工作的计划/pin/结果/审计和正常重启恢复
保留，不清空媒体/运行库。Automation 的现行工作区、Enabled/运行一次行为按上文，
不由退役要求另行产生权限或功能范围。
这是整 Slice 验收后的 CURRENT；没有把 Task45.4 Scan PASS 代替 Preview 退役验收。

## V1 and post-V1 boundary

V1 `/ui` and shared API authority remain until explicit cutover/parity acceptance. Current delivered
workspaces do not include cross-Task bulk mutation, arbitrary historical Reprocess, universal rollback,
automatic uncertain replay, Provider switching/new production Providers, built-in users/session/OIDC,
general Secret Store or specialized email/chat/media-server channels. Selected45 cross-Task problem
lists supersede earlier deferral of those lists only. Active/frozen scope and earlier accepted
exceptions are authoritative in Slice/Progress; documentation consolidation does not extend them.
