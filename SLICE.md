# Slice 43 — V2 Automation Workspace and Engine Settings

```text
Slice ID: 43
Name: V2 Automation Workspace and Engine Settings
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 24a7a519844dd953a01a43d4a80b8ea999ada812
Implementation Head: acc5c567788410cde68ed24b4fee12a84ee47ef2
Working Branch: main
Development Authorization: USER-AUTHORIZED RESUMPTION — 2026-10-23; ACCEPTED — 2026-10-24
Risk: High
Final Test Level: T4
Next Action: A SELECTS THE NEXT LARGE SLICE
```

## Git history attribution update

On 2026-10-24 the user authorized Git identity normalization and removal of assistant coauthor
trailers. The machine-readable Base and Implementation Head above use the corresponding commits
on rewritten `main`. Every mapped commit has the exact original file tree; the underlying Slice
start, reviewed implementation, outcomes and acceptance remain fixed.

Historical review paragraphs, the closure ledger and evidence-directory names retain their
original commit IDs. Original commits and frozen/preservation refs remain in owner-local backups.
Use these equivalents for current-lineage navigation and governance:

| Reference | Original review ID | Equivalent on current main |
|---|---|---|
| Slice43 Base | `853973dbbf8289fa2ad40657033e94e870a690e4` | `24a7a519844dd953a01a43d4a80b8ea999ada812` |
| Reviewed implementation | `97316131946bdecc483b684f6e6f6ecb98c5594d` | `acc5c567788410cde68ed24b4fee12a84ee47ef2` |
| B report | `0822e58fd687e402551e3224073cc8e8522192a0` | `473af50a7cb0a61f665db3b3fdb94a47bf2af6b4` |
| Original Task43.3 Base | `78ec108d4473e8c140174c1356d0e88a1ae42b34` | `e0765da38c20c60f8fd74a2a7bdccaba7b86d670` |
| Accepted Slice45 Base | `a72252091d5d46edf3e2114b994036ae21b08e2e` | `e13fa03f87151c5f763ce64d6cca08897c57356d` |
| Accepted Slice45 implementation | `4fcb0028f987f8746f0a8aa7b309e360b07c598e` | `d59d48f349bddf67562c1d5e81f2fb78e82b13a0` |
| Accepted Slice45 closure | `13ecfc0e75fc34ff0ae489e655124a178943cba4` | `3947fbe00963a17744570a2f7a95ac0146991d53` |

The independent frozen Contract stays on its original branch. Complete rewrite maps and checks
remain locally under `.git/author-rewrite/`, `.git/identity-rewrite/` and
`.git/coauthor-cleanup/20261024T131020Z/`.

## User-authorized resumption and authority

用户于 2026-10-23 明确要求继续自动化页开发。A 恢复同一 Slice43，不另起 Slice、不改原 Base，
在已由用户授权整合的 main 上，承接已关闭 Slice45 后的实际代码。解除的是当前开发冻结；
`frozen/slice-43-2026-10-15` 作为不可变历史保留，不移动其指针。
原恢复 checkpoint 只恢复范围与交接；本次完整实现及修正的 A 最终审查为 PASS / CLOSED，见文末。

[AGENTS.md](AGENTS.md) 和 [Development Workflow](docs/development-workflow.md) 为现行权威。
原用户结果、RO-1..RO-7、设置实际消费义务与 T4 门槛保留；只将旧合同中的 Scan、独立 Preview、
FileIndex 形式及旧产品迁移/兼容义务对齐用户后来明确授权、已被 Slice45 验收的退役边界。
不恢复旧执行器、不另建索引/分析队列、不以恢复43撤销45，也不把必要适配变成新的产品模式。
文内历史 `Preview` 只指共享零变更分析/精确计划能力，不能授权独立产品入口。

| Preserved / current fact | Immutable reference and meaning |
|---|---|
| Original Slice43 Base | `853973dbbf8289fa2ad40657033e94e870a690e4` — preserved review reference; [current-lineage equivalent](#git-history-attribution-update) above |
| Frozen Contract / branch | `ed974e0df8b263f631bfe48b524da461013d8780:SLICE.md`; `frozen/slice-43-2026-10-15` |
| Original pre-hold Task43.3 | `c539429c2c3aaeaab4842b87d3c858e77106fed1:TASK.md` — PLANNED, not started |
| Original Task43.3 Base | `78ec108d4473e8c140174c1356d0e88a1ae42b34` — retained on its preservation branch; [current-lineage equivalent](#git-history-attribution-update) above |
| Task43.3 Goal / Scope | Automation Inventory, Execution Records and Truthful Statistics; RO-1 inventory/statistics + consolidated RO-5 + related RO-7 query/navigation/failure surfaces; RO-6 settings remains a separate coherent unit |
| Historical43 implementation / report | `727317168cc62f859f19db1b54b8175cb08449de` / `78ec108d4473e8c140174c1356d0e88a1ae42b34:TASK.md`; 43.1/43.2 are historical B PASS only |
| Integrated preservation refs | `preserved/main-before-slice45-merge-20261018`; `preserved/slice45-before-main-merge-20261018` — unchanged |
| Accepted Slice45 | Base `a72252091d5d46edf3e2114b994036ae21b08e2e`, implementation `4fcb0028f987f8746f0a8aa7b309e360b07c598e`, closure `13ecfc0e75fc34ff0ae489e655124a178943cba4:SLICE.md` — PASS / CLOSED unchanged |
| Resumption source checkpoint | `13ecfc0e75fc34ff0ae489e655124a178943cba4` — docs-only successor of the Implementation Head; not Slice43 acceptance |

### User-authorized execution-record boundary

On 2026-10-23 the user refined the design: Automation keeps its own read-only execution records,
reporting results, failure stage, reasons and repair guidance; it does not embed file recovery.
Before formal organizing starts, guide repair and an explicit safe retry through existing supported
commands. After durable organizing-task handoff, all execution controls and per-item recovery belong
to Task Center. This does not select the earlier proposed replacement of the records page with a
Task Center filtered list. RO-5/AC-8 below define the boundary and non-replay requirements; original
Base/outcomes/T4 and accepted45 behavior remain. B's subsequent43.3 reassessment and implementation
followed this material revision; its historical Task identity/Base remain unchanged.

### Accepted implementation and B handoff

B explicitly reassessed the preserved Task43.3, retained its original Base, and accepted inventory,
records and statistics at `8ff9b173972c15a46afc9c8f8aaa8c5584c127e2`; its report is retained at
`f18d2444f548b81b5892536498a1b4cdd4400be8:TASK.md`. Task43.4 then delivered focused engine-settings
publication and resident adoption from that checkpoint. The refreshed B packet is in
`0822e58fd687e402551e3224073cc8e8522192a0:TASK.md`, reviewing corrected implementation
`97316131946bdecc483b684f6e6f6ecb98c5594d`. The seven extra frozen43 native failures
were not accepted during45; current lifecycle/Run-once/workspace/settings evidence is assessed now
under the accepted45 amendments, without restoring retired products.

A's prior rejection and A43-01 are retained at `00096fb2996776ed386a09904ecb0005a9105c6d:SLICE.md`.
The correction remains within Task43.4 and its original Base. A independently reviewed the whole
original Slice range and verified the corrected restart journey before closure. Original Base, outcomes, acceptance, deferrals
and preserved refs are unchanged; the final review below records the accepted facts and limits.

## User Goal and Journey

An operator can configure when a bounded ResourceLibrary source is automatically organized, understand
what will happen, deliberately permit unattended execution, run the published definition once,
find each run and resolve its affected items, and adjust the engine without confusing saved values
with parameters actually used by resident processes.

- **Entry:** shared-shell `自动化`, an existing definition/occurrence deep link, or the Automation
  settings section reached from System Settings. Preserve existing compatible links and return context.
- **Visible state:** definition inventory, automatic-organization scope/schedule/limit,
  enabled versus authorized versus running state, next scheduled run, real summary
  statistics, independent run outcomes, and published
  versus process-consumed settings. Internal IDs remain optional diagnostic details.
- **Action:** create/copy/edit/enable/disable/reference-safe remove; one checked Save; exact shared analysis/plan summary;
  grant/revoke; Run once; read filtered execution results/reasons and follow repair or Task Center links;
  save global settings.
- **Success:** the published definition and current authority govern newly admitted bounded work;
  scheduled occurrences do not require another per-run click; manual real execution retains its
  one-shot intent. Runs and outcomes survive refresh/restart. Settings changes are visibly adopted
  by the actual eligible consumers without routine process restart.
- **Failure:** invalid/stale configuration, missing dependency, unavailable Worker/Scheduler,
  insufficient/revoked permission, capacity, conflict, changed source, invalid pin or uncertain media
  effects are attached to the affected definition/run/item/consumer with durable-state explanation.
- **Recovery:** correct and Save, re-analyze/regrant where required, reconcile an unknown submission,
  restore consumer readiness, or follow the linked native task decision/continuation path. No generic
  Retry may replay successful or uncertain effects, and no failure erases sibling outcomes.

## Original Base Audit and Reuse Boundary

The Base already has immutable managed configuration, typed Automation definitions with all three
historical modes, ResourceLibrary sub-scope and item limit, interval/Cron timezone scheduling, durable due state
and occurrences, exact Preview, scoped revocable unattended grants, pinned Worker processing and
TaskItem/Result/checkpoint recovery. V2 has definition/list/editor/Preview/occurrence pages; Slice 42
provides the shared Operations run inventory and native task-linked controls/recovery.

At the original Base, the list is a bounded card projection with a truncation marker, not the
reference table with cross-definition metrics/history. Its editor exposes separate
Draft/save/validate/activate steps.
No complete definition-bound Run-once journey is advertised at that Base.

All four engine fields exist. `maximumActiveJobs` counts pending plus running Jobs in the shared
AutomationJob admission pool, not execution parallelism. `staleJobAgeSeconds` is a stale-update
observation threshold, not a task timeout or automatic replay instruction. Settings metadata labels
polling values hot-consumed, but the Base resident Worker/Scheduler capture their poll interval at
startup and `ResidentLoop` retains that value. API configuration binding alone is not evidence that
those processes changed cadence. This Slice must close that original-Base consumption gap for its four
fields; it is not authorization to rewrite the queue or general deployment administration.

## Required Outcomes

### RO-1 — Reference-aligned inventory and truthful statistics

Deliver one native Automation workspace with `任务列表 / 执行记录 / 全局设置`. The header's settings
shortcut opens that same settings surface. Reuse the existing shared light shell, typography,
icons, blue primary actions, light borders and status badges; no alternate shell.

The list has name, scheduling enabled state, source ResourceLibrary/scope, readable schedule
and timezone, item limit, next scheduled run, latest processing outcome/time and available actions.
Its secondary text may derive from scope; a new free-form description field is not required.
New/Edit/analysis/detail open only by explicit navigation. Provide real empty/setup/dependency/error,
loading and denied states, responsive layout, keyboard use and refresh-safe deep links.

Backend-authoritative bounded search, enabled/source filters, stable sorting and pagination
must keep every authorized definition reachable. Supported Draft-only definitions remain labelled and
reachable for configuration correction, never counted or toggled as published. This does not add
retired-mode inventory/conversion or an executable compatibility path. New definitions start disabled;
copy creates a new identity, disabled schedule and no copied execution authority.

Provide published definition/enabled counts, month-to-date admitted run count, mode-aware run success
rate, and clearly labelled run-count comparison with the previous month's equivalent elapsed local
calendar period (clamped to that month's end). Return the actual timezone/window and metric basis.
Use the configured system timezone for these cards, separately from each Cron timezone; no timezone
editor is added here. Scheduled and manual definition-linked runs count once by durable admission;
Job/Task/execution links must not double count. Analysis/grant-preflight evidence,
discovery alone, grant attempts and rejected admissions are not runs. Supported historical runs
retain their admitted context and original outcome meaning, never
being relabelled as successful organization. Retired Scan/standalone Preview products gain no
migration/history/compatibility obligation; the accepted Slice45 first-deployment boundary applies.
The success denominator is terminal runs in that admitted cohort, including failed,
partial, cancelled and terminal-uncertain outcomes; active/waiting runs are separately visible and
excluded. A successful no-work completion is labelled as such; skipped files are not organized files.
No denominator or comparable prior count means `暂无可比数据`, not invented percentages. Unavailable
queries are not zero. Cards query the full authorized population, never just the current page;
state clearly which filters apply and maintain a consistent server read basis.

### RO-2 — Native definition lifecycle with one checked Save

Provide typed create/edit/copy, enable/disable and reference-safe removal of a definition, using the
existing ResourceLibrary IDs, safe relative sub-scope, fixed automatic-organization intent, item
bound and exactly one of interval or Cron with required IANA timezone. Daily/weekly convenience controls compile to the same
supported Cron semantics; advanced Cron remains available. Preview upcoming times and invalid/DST
behavior through the same backend schedule calculation, without emitting work.

The intent is fixed to `自动整理`; create/edit/copy has no mode selector. Backend configuration,
publication, import and admission reject both removed modes and their aliases through ordinary
shared validation. There is no dedicated retirement, legacy inventory/conversion/history/migration
or compatible running mode. Existing configuration errors remain correctable without media changes.
New/copy starts disabled without authority. Removing invalid definition
configuration does not remove media, historical pins, grants/audits or recorded outcomes.

Save and lifecycle commands compose a focused successor from the exact published Active, validate
the whole candidate and applicable evidence, then atomically publish it. The operator does not
manually orchestrate Draft/Validate/Activate. No unrelated open Draft edits or sibling definition
changes ride along. Stale/failed publication preserves the previous Active and correctable input;
unknown submission is read back before deliberate resubmission. Reads never create Drafts.

Published, enabled, authorized and execution-ready remain distinct. Saving an enabled definition
makes it eligible for future Scheduler evaluation but never synchronously emits a Job or grants
execution authority. Show missing grant/readiness as a blocker, not a working green switch alone.
Disabling stops future scheduled emission at the checked boundary; it is not cancellation or grant
revocation and does not silently rewrite already admitted work. Separate existing cancel/revoke
controls explain their effects. Removal enforces the existing configuration/revocation permissions,
stops future scheduling and revokes future unattended
mutation authority without erasing grants/audits, historical pins, occurrences or linked results;
in-flight effects remain subject to existing safe-boundary semantics. Reference conflicts return
bounded repair guidance. Retained history remains readable even after the definition leaves Active.

### RO-3 — Exact shared analysis and scoped unattended execution

Native forms complete shared zero-media-mutation organizing analysis, its exact same-page plan
summary and the explicit grant/revoke journey. No independent Preview product/page/task is restored.
The summary shows source bound, RecognitionType/policies, identity, destination, operation, conflicts,
capabilities, expected effects, ineligible items and next actions. Long analysis uses durable work.
Evidence identifies the exact tested candidate/published definition and becomes stale when its
required binding changes; Draft analysis is never shown as Active or as execution authority.

Initial unattended grant requires exact valid analysis/plan evidence and explicit review of scope, limits,
organizing intent and permitted effects. Keep existing grant validity/revocation rules authoritative; saving, copying,
enabling or broadening a definition cannot silently create or expand authority. Valid scheduled
authority permits future due runs without per-run analysis/Execute clicks, while normal per-item
planning and current mutation checks still apply. Blocked items remain independently recoverable.

Scheduler remains an idempotent due-occurrence emitter, preserving existing interval coalescing,
Cron/timezone/DST and restart behavior. It cannot choose policies or mutate media. Existing locks,
claims and fences protect overlapping manual/scheduled work; no new overlap/backfill policy is added.

### RO-4 — Deliberate Run once with unchanged schedule

`运行一次` uses the exact published automatic-organization definition, source scope and item limit. A disabled
schedule may be run manually with current command permissions; this does not enable the schedule,
revive a grant or bypass execution gates. Draft-only work must first be published.

Run once automatically discovers eligible live sources within the saved definition scope and
freezes the exact bounded manifest, then shows the exact same-page organizing plan summary and
requests separate one-shot execution intent. The normal journey requires no file picker or
hand-selected subset. Reuse the existing discovery, shared organizing analysis and execution authority
through the shared application behavior;
do not turn a persistent scheduled grant into manual execution permission or execute a changing
whole-library scope. The effective primary-file bound is the smaller of the definition's item
ceiling and the existing 100-primary manual/discovery bound. Show both limits and the frozen
manifest's eligibility/exclusion evidence. If discovery exceeds the effective bound or cannot
prove a complete bounded manifest, refuse execution and explain how to narrow the definition
scope, publish and rediscover/re-analyze; never silently take the first N files. Empty discovery
has a truthful no-work outcome. Preparation corrections stay in the existing preparation journey;
admitted-item recovery belongs to Task Center. Changed scope or sources require fresh evidence and
execution intent. Expensive discovery/analysis is
durable and cancellable at existing safe boundaries. A preflight is not counted as an admitted
media execution.

Pin configuration/definition context at creation, refuse stale admission without silently repinning,
and preserve the historical origin through the linked Job/Task or existing manual execution record.
Use existing corresponding admission/Worker services; do not create a dummy Job or parallel engine
merely to satisfy a display model. A durable manual trigger link distinguishes it from scheduled
occurrences and makes it visible in both Automation history and Operations without double counting.

Atomic request reconciliation prevents double-click, concurrent or ambiguous-network resubmission
from creating duplicate work or consuming authority twice. Preserve principal isolation across
reload/reconnect, including Unicode identities. Manual runs do not advance/reset next due time or
consume a scheduled occurrence. Capacity, authorization, missing pin and readiness failures return
safe next actions; success immediately links to the selected durable run and back to its definition.

### RO-5 — Read-only execution records, pre-start repair and Task Center recovery

Provide bounded server-filtered history by definition, trigger, outcome and time, including
scheduled occurrences and manually admitted runs. Pending/pre-Task failures remain visible. Keep
scheduler blocked-emission diagnostics distinct from actual admitted runs and processing outcomes.
Latest-result projection and statistics must respect linked Task/items, not interpret Job completion
as successful organization. History preserves name/scope/mode/version at admission or labels missing
legacy evidence; current rename/remove cannot rewrite it.

Automation retains the reference execution-record surface, rather than replacing it with a Task Center
list. It reports status/results, start/end, counts, reached item bound, failure stage/reason, known effects
and concrete repair guidance. Reached bound does not prove scope exhaustion. Reading a record or
opening its reason never starts work. Records may link to the relevant definition, settings, service
readiness or exact Task Center run/problem; they contain no local file-decision forms, re-analysis,
pause/continue/cancel or execution-recovery commands. Reuse existing result/export and Task Center
behavior, not a second result store, queue or recovery engine.

Before formal organizing starts, explain the failed prerequisite and guide the operator to repair it,
then explicitly retry using the existing supported occurrence/admission or Run-once journey. Retry is
allowed only when backend durable evidence proves no organizing execution/media effects started and
the prior attempt is settled/fenced against later execution. A queued/claimed attempt is not another
retry candidate. Revalidate current permissions, exact scope/configuration/pins and applicable analysis/
authority; a changed definition is not silently substituted into an old admitted attempt. If retrying
the old context is not supported, explain the reason and offer an explicitly distinct new Run once or
the next scheduled evaluation, retaining the original record and not advancing/replaying an occurrence
implicitly. Reconcile unknown submissions before another command; no automatic or blanket start-again
retry of a run. Existing supported in-pipeline retry policies are unchanged.

The user-facing boundary is durable handoff to a formal organizing Task/execution, identified from the
existing authoritative run/origin links and checkpoints, not the first Move/Copy or a frontend status.
Preparation-only discovery/analysis is not formal execution. Once formal execution exists, including
its scanning/recognition/metadata/planning failure before any media mutation, all controls and recovery
go to the exact native Task Center run/problem. A missing Task link alone does not prove pre-start:
an ambiguous handoff or uncertain effects require reconciliation/investigation and cannot offer
start-again retry. Do not invent a Task/Job solely to route the page.

Task Center owns legal per-item decisions, safe re-analysis/summary/explicit continuation and controls.
Successful siblings and uncertain effects are never retried as ordinary failures. Preserve list/filter/
definition return context, original outcomes and independently linked recovery attempts across restart;
later recovery does not overwrite the original result or count as another scheduled trigger.

### RO-6 — Global settings with actual consumer adoption

Provide the reference-style form, help panel and schedule/timezone explanation. Its four fields are:

| Field | Operator meaning and authority |
|---|---|
| `automation.maximumActiveJobs` | Maximum pending + running Jobs in the shared admission pool, not number of threads/workers or media-file concurrency. Lowering it blocks new admissions until capacity becomes available; existing work is not killed. |
| `automation.staleJobAgeSeconds` | Age since last durable running-Job update used for stale observation. It neither limits total runtime nor authorizes cancellation/requeue/replay. |
| `automation.workerPollSeconds` | Actual resident processing Worker polling cadence, separate from heartbeat/lease and from per-Job pipeline policy. |
| `automation.schedulerPollSeconds` | Actual resident Scheduler due-check cadence, separate from each definition's schedule and timezone. |

Use backend validation and units, including finite positive numeric checks and existing integer
bounds; reference example values/ranges are not new defaults or validation authority. Unsupported or
unknown settings fail before publication. Optional Advanced JSON shows only the safe supported subset.

One Save performs exact focused managed publication for these fields; no unrelated Draft changes,
secret values, deployment changes or media work. System Settings and Automation share this authority
and consistent links/readback rather than maintaining duplicate settings stores.

For the supported resident deployment, actual Worker/Scheduler loops adopt new configured polling
values at a safe loop boundary without routine restart, including idle and busy transitions and
startup before first Active. A bounded configuration recheck must also handle a previously long wait;
settings adoption must not depend on work arriving. Keep heartbeats/leases alive and preserve pins
and authority of admitted/in-flight work. API/admission/Scheduler capacity and stale observations use
the appropriate current settings without rewriting an old Job's media pipeline configuration.

Expose published target and actual consumed values/version with freshness per relevant live consumer.
A process report is evidence only after that consumer adopts the values. Missing/stale/stopped or
mixed-version consumers show pending/unavailable with a next action, never collective success inferred
from an API-loaded snapshot. Explicit CLI/deployment poll overrides retain precedence and are clearly
shown as overrides; Web Save cannot rewrite them or claim adoption. Invalid/unavailable Active stops
new unsafe admission/emission, leaves actionable waiting state and does not silently use cached
business authority. Intact admitted pins remain governed by their existing execution boundary.

### RO-7 — Shared authority, compatibility and complete failure journeys

Web/API use the same validation, applicability, permissions, publication, admission, grants, query and
recovery services. Supported V1/API/CLI configuration and Automation/Task/Job links remain compatible
or resolve through a truthful contextual route. Slice45's retired Scan/Preview/FileIndex routes,
commands, modes and dedicated compatibility/migration/history layers stay absent; direct requests
cannot bypass ordinary not-found/argument/shared unsupported-type validation. No conversion path or
retired executor is introduced. Supported work retains its legitimate pins/results/recovery.
Empty Active is valid and offers dependency guidance;
absence of Active leads to Settings, while broken prior Active offers recovery rather than new setup.

Permission loss, stale forms/evidence, conflicts, missing secret/pin, storage/provider faults,
malformed responses, 401/403 and unknown submissions preserve independent durable state and operator
input where safe. Neither browsing nor polling invokes Provider/Storage mutation, creates work or
implicitly grants authority. Redact credentials and private host roots. Preserve C identity under
NamingPolicy A and ClassificationPolicy A. Cross-page Settings, Rules, Files, Operations, admitted
transfers and resident service behavior remain protected.

## Required Surfaces

- Shared-shell V2 Automation inventory, typed lifecycle/shared-analysis/authority journey, records and settings.
- Typed authenticated API read/command projections over shared Python application authority.
- Existing managed configuration, scheduled occurrence and manual admission/Worker/persistence paths.
- Real resident Worker/Scheduler settings adoption and fresh per-consumer readback.
- Read-only Automation execution records with prerequisite-repair guidance and exact native Task Center
  detail/recovery links; System Settings/ResourceLibrary/Rules return links.
- Compatible supported routes and additive durable migration for necessary supported links/consumer evidence.

## Safety Invariants and UX Constraints

All permanent invariants apply: Storage-only file access, OrganizerExecutor-only mutation,
zero-media-mutation discovery/Parse/Recognition/Metadata/Naming/Classification/Planner/analysis,
explicit overwrite/delete policy and intent, capability checks without silent operation fallback,
source confinement and stability, bounded work, current RBAC, audit/redaction, exact immutable pins,
atomic admission/publication, locks/claims/leases/fences and no automatic uncertain-effect replay.

ResourceLibrary is the organizing source. Definition and Scheduler never select per-file Provider,
Naming/Classification policies, final MediaLibrary path or transfer action; the existing
RecognitionType policy chain does. Old scan/plan records and standalone analysis cannot acquire
mutation capability. Grant/revoke is separate from analysis, schedule enablement and manual one-shot
authority. Long work is durable;
controls operate at safe boundaries and do not promise rollback or immediate interruption.

The two PNGs define business relationships, composition and visual style only. Names, counts,
dates, paths, timing values and suggested ranges are illustrative. Preserve originals, do not add
sample business configuration or reproduce fixture data. Use real backend actions and bounded
explanations; no raw token/identifier ceremony. Reference checksums at activation:

- `docs/pics/自动化页.png` (historical name `自动化.png`): `d2f759ead56a30dce344ccce97e7c119e144ca728a31b3af8e9a355eefa6ba34`
- `docs/pics/自动化页-全局设置.png` (historical name `自动化-全局设置.png`): `68d91070e859dd363d3e45dd2d21e38783e0cfbef0867ce28c3f42eac7d6c7b9`

The two original user-supplied files remain pre-existing untracked workspace artifacts; both exact
digests were verified and both opened on 2026-10-23. Preserve all unrelated reference files/deletions;
do not stage/recompress the images as part of this activation. Missing
reference availability must be reported rather than replacing the originals with approximations.

## Explicitly Deferred

- New pipeline modes, scheduled cache/log cleanup, backfill/catch-up controls, overlapping-run policy,
  priority/reordering, queue replacement, distributed workers or new concurrency/throughput controls.
- New Providers/Storage operations, per-definition policy/destination overrides, MediaLibrary as
  organizing source, unbounded whole-library manual execution or file uploads/downloads.
- Notifications/Dashboard/global System Settings redesign beyond necessary Automation integration;
  identity/Secret Store/deployment editing, changing CLI override authority or auto-restarting services.
- New cross-task bulk review, arbitrary historical Reprocess, new recovery semantics,
  history deletion/retention/archiving, universal rollback or automatic uncertain-mutation replay.
- New metadata acquisition, media thumbnails/posters, free-form definition descriptions, pixel-exact
  reference fixtures, image edits, fabricated statistics/ETA or mandatory streaming infrastructure.
- V1 retirement, other V1 requirement changes and changes to accepted historical Slice boundaries.
  The explicit V2 single-mode amendment above is in scope; it does not rewrite V1 history.

## Slice Acceptance Criteria

| ID | Acceptance |
|---|---|
| AC-1 | Reference-aligned list/records/settings use real data, shared shell, refresh-safe navigation, responsive/keyboard behavior and actionable empty/error/denied states. |
| AC-2 | Server search/filter/sort/page and full-population metrics remain consistent, authorized and truthful across pages, month/timezone boundaries, zero denominators and unavailable data. |
| AC-3 | Automatic-organization-only typed lifecycle and one checked Save publish only the intended change; stale/concurrent/failed/unknown publication preserves prior authority and recovery without sibling Draft activation. Removed modes/aliases cannot validate, publish, import or execute; ordinary shared rejection and no conversion/compatibility branch remain. No retired-product migration/history layer or user-data clear is introduced. |
| AC-4 | Schedule, scope, limits and next times use existing semantics; exact shared analysis/grant/revoke complete natively, copies gain no authority, broadened scope cannot reuse insufficient authority. |
| AC-5 | Due occurrences remain unique across concurrency/restart/DST; scheduled valid grants execute without per-run clicks while current scope/capability/conflict/revocation gates remain enforced. |
| AC-6 | Automatic-organization Run once automatically discovers and freezes the complete bounded live-source manifest without normal file picking, then completes exact same-page analysis/summary, explicit one-shot execution, duplicate/unknown-admission reconciliation and no schedule advancement. Overflow or incomplete discovery blocks execution with scope-narrowing/re-analysis recovery; no silent first-N truncation. No removed mode or standalone Scan/Preview/FileIndex product is restored through any surface or compatibility path. |
| AC-7 | Definition, manual/scheduled run, Job/Task/execution and per-item results retain durable links without double count; pre-Task failures and removed-definition history remain reachable. |
| AC-8 | Automation records expose truthful results/stages/reasons/known effects and actionable links, without embedding file recovery or execution controls. Proven pre-start failures guide repair and explicit safe retry only after the old attempt is settled/fenced and authority/context revalidated. Durable formal organizing-task handoff, not first media mutation, moves all execution recovery to Task Center, including analysis-stage failure. Unknown handoff/effects forbid start-again retry; original/continuation/sibling outcomes and return context remain independent, with no false success or replay. |
| AC-9 | Settings Save validates/publishes the exact four-field scope; capacity and stale observation retain their real semantics and no setting grants media authority. |
| AC-10 | Real running Worker/Scheduler adopt new polling values without restart or work arrival; fresh per-consumer evidence distinguishes target/adopted/pending/override/stale state and retains old work pins. |
| AC-11 | Web/API RBAC, Active/Draft separation, redaction, zero-side-effect reads, C identity and compatible Settings/Rules/Files/Operations/V1 journeys are maintained. |
| AC-12 | T4 final regression, real Python/Worker/Scheduler browser/process paths, affected upgrade/packaging and reference/private-file checks establish the promised outcomes without expanding deferrals. |

## Final Validation Expectations

Task test assignment and execution stages follow [the current workflow](docs/development-workflow.md#6-test-levels).
This high-risk Slice retains T4 final acceptance. Development/correction feedback does not replace
the complete corrected-candidate gates or Slice Final; the concrete risk coverage below remains required.

- Exercise existing Automation definitions, occurrence/Cron/DST, shared analysis/grant/execution, admission/
  fencing, settings/configuration and resident suites plus Operations/manual-organize/recovery/RBAC.
- Cover success, invalid/finite/boundary input, missing dependencies, stale/concurrent publication,
  unknown admission, Unicode principal isolation, capacity reduction, revocation during work,
  missing pin/secret, source change, mixed outcomes, current Active A-to-B isolation and restart.
- Through existing Automation entrances, distinguish provable settled pre-start failure, queued/claimed
  work, formal Task failure before first media mutation and ambiguous handoff. Verify repair/retry
  revalidation and request reconciliation, read-only record behavior, exact Task Center handoff/return,
  retained original results and non-replay of successful or uncertain effects. Do not invent routes
  or treat an absent Task link as proof that retry is safe.
- Query fixtures exceed page limits and include scheduled/manual links, pre-Task failure, partial/
  waiting/cancelled/uncertain/no-work runs, removed definitions, legacy missing evidence and calendar
  boundaries. Validate database-level query/metric behavior, not only frontend fixtures.
- Native Web tests cover form dependencies, check/save/grant separation, polling, return routes,
  denied/stale/unknown states and settings consumption. Real Python/SQLite/Storage/Provider/Worker/
  Scheduler browser paths prove fixed-mode create -> Save -> shared analysis/summary -> grant -> scheduled result,
  automatic-organization Run once -> Operations and an affected item's existing native recovery.
  Removed-mode/alias configuration, publication/import and direct admission refuse safely before
  discovery/Provider/admission/authority. Supported recorded outcomes/pins/history survive current
  supported upgrade/reopen; retired-product migration/history/takeover is not recreated. No conversion,
  compatibility executor, data/media clear or automatic replay is added.
- Actual resident subprocess tests change settings while processes are idle/busy, start before Active,
  observe adopted cadence independently of HTTP echoes, and cover long waits, override, loss of
  consumer, DB/config failure and restart. Assert process identities persist when no restart is needed,
  and admitted old work stays pinned. Use controlled clocks/fakes where appropriate for DST/metrics.
- Slice Final normally runs full Python/Web regression, affected browser/process suites, Python
  format/lint/compile, Web typecheck/lint/format/build, governance/whitespace and exact Base..Head
  manifest/private-file audits. If schema changes, rehearse the current supported-schema transition
  with preserved supported rows/pins/authorities; do not rebuild the old FileIndex/Scan/Preview
  migration matrix superseded by Slice45. Include wheel/static serving and supported Compose lifecycle
  checks material to resident changes. Record actual failures/skips/unavailable gates honestly.
- Instrument reads, publication and shared analysis for zero media mutation; passive reads call no Provider.
  Retain C-with-A/A regression. Use temporary storage/fake/local services, never production media or
  private credentials. Verify both reference checksums; do not weaken tests to turn missing evidence
  into PASS. No FFmpeg/FFprobe.

## Factual updates and review authority

Only A materially changes the Contract, Base, Required Outcomes, safety, acceptance or deferrals.
B/Developer may update factual Implementation Head, Task progress and evidence within their roles.
Task planning/review, correction loops, stop rules, Closure Packet and final review follow
[the current workflow](docs/development-workflow.md). This document does not define a separate lifecycle.

## Closure Packet

B accepted corrected Task43.4 and submitted SLICE READY FOR A REVIEW at
`0822e58fd687e402551e3224073cc8e8522192a0:TASK.md`, reviewing
`97316131946bdecc483b684f6e6f6ecb98c5594d` (executable correction `97f3cebc86e54d8dda80b49ecb739e8935a4f447`).
RO-1..RO-7 and all Required Surfaces are complete within the unchanged acceptance and deferrals.
The original43.1/43.2 chain,43.3 and43.4 including A43-01 are complete. No next Task is needed.

B freshly ran the final candidate's T4 gates. Full logs, timing, manifests, artifact identities and
visuals remain locally under
`.git/validation-evidence/97316131946bdecc483b684f6e6f6ecb98c5594d/b-review/`.
They are not remotely accessible CI evidence. The full packet above retains command/result details.

| Final gate | Actual corrected-candidate result |
|---|---|
| Python | 2805 run, OK, 7 skipped; Ruff format/check, compileall, pip check and both example validations PASS. |
| Web | Typecheck/lint/format/build PASS; 84 files / 1221 unit tests and 242 default E2E passed. Existing chunk-size warning remains. |
| Real Python production assets | Settings12, workspace8, lifecycle11, Run once4, Operations41 and Unicode principal1 passed in isolated harness invocations. |
| Packaging / persistence | Exact wheel smoke and installed actual Scheduler cadence proof PASS; genuine Task-Base49→50 upgrade preserves all73 prior tables/rows and supported pins/authority/results, leaving the rehearsal source unchanged. |
| Production / safety | Media-free and optional-media Compose, restart/fault and release-security proofs PASS; explicit authorized Organize and both library Copy paths checked. No-execute Organize400 retains accepted45 intent semantics. |
| Scope / visual | Complete manifests, desktop/narrow captures, original reference hashes and preserved refs verified. Private files and pre-existing unrelated changes excluded. |

Seven skipped real OpenList/SMB/S3 and endurance profiles lack their dedicated isolated environments;
they remain unavailable, not passed. No new provider/endurance capability is accepted. B's earlier
reported test-time deviation remains at `b1098329115dd53625ff08c4b616ecc80da89c1d:TASK.md`; the refreshed
packet records404.23s of automated-gate interval union but lacks a timestamped full-round denominator,
so the requested below50% ratio cannot be certified. Product closure does not certify or waive that
process requirement, and it is not transferred to Developer.

## A Final Review

Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..97316131946bdecc483b684f6e6f6ecb98c5594d
Reporting Successor: 0822e58fd687e402551e3224073cc8e8522192a0 (TASK.md only)
Decision: PASS / CLOSED — 2026-10-24
P0/P1 Blockers: NONE ESTABLISHED
Prior Finding: A43-01 RESOLVED
Closure Reconciliation: Slice/Task/Roadmap/Progress and applicable CURRENT/operator documents

### Whole-Slice assessment

A reviewed the complete457-file original Base..Head manifest and the changed application/domain,
API/SQLite, real resident commands and Web boundaries, including definition checked publication,
Run-once bounded freeze/authority, record/metric projections and settings adoption. The range includes
explicitly integrated44/45; their accepted boundaries and immutable closure facts remain unchanged.
The previous A review at `00096fb2996776ed386a09904ecb0005a9105c6d:SLICE.md` remains a rejected-candidate
review, not retrospectively PASS. A reviewed the subsequent correction across production, API/Web
projections, tests and harness, and B's refreshed raw evidence; Task labels alone do not establish acceptance.

| Outcome | Accepted behavior and material evidence |
|---|---|
| RO-1 | Native inventory/records/settings, authoritative search/filter/sort/page and full-population local-calendar metrics; unavailable/empty/denominator semantics and responsive captures reviewed. |
| RO-2 | Typed fixed-intent lifecycle, exact focused checked Save, disabled/unauthorized copies, stale/unknown recovery, reference-safe removal and retained history over shared managed authority. |
| RO-3 | Shared zero-mutation exact analysis/summary with separate scoped grant/revoke and existing Scheduler/Worker/OrganizerExecutor checks; retired products remain absent. |
| RO-4 | Complete bounded live discovery, frozen manifest, separate one-shot intent and reconciled admission without schedule advancement; current four-case native proof, overflow tests and restart/security evidence support the result. |
| RO-5 | Read-only records retain original outcomes/effects and independent handling state. Proven pre-start repair, ambiguous-handoff refusal and exact Task Center ownership preserve successful/uncertain non-replay and return context. |
| RO-6 | Four-field publication preserves other state; real loops adopt without routine restart. Current membership follows fresh registrations, every live replica must prove adoption, and stopped/stale history cannot veto or certify it. A independently verified restart, later publication and live override. |
| RO-7 | Shared Web/API authority, Active/pins, RBAC/redaction, C-with-A/A identity and neighboring supported journeys remain protected by inspected boundaries and current T4/native/packaging evidence. |

All Required Surfaces and AC-1..AC-12 are satisfied within the recorded evidence limits. The original
Base remains the true Slice start; no repinning, new feature boundary, retired compatibility layer,
process supervision or new execution authority is introduced by closure.

### Independent A checks

Entry was main/`0822e58fd687e402551e3224073cc8e8522192a0`; workspace and Git were writable. The only
candidate→entry change is B's TASK.md report. Entry governance exposed the disclosed B→A transition
(`FIX REQUIRED` plus no active Task); closure synchronizes the lifecycle rather than altering the guard.

A ran on the reviewed executable inputs:

- `.venv/bin/python -m unittest tests.test_automation_settings_management`:54 passed,2.858s.
- `npm run build` in `web/`:PASS, existing chunk-size warning.
- Existing real-Python settings spec, filtered to graceful resident restart and System Settings
  entrance:2 passed,2.2s, using rebuilt production assets and unchanged assertions.
- `PYTHONPATH=. .venv/bin/python .git/validation-evidence/97316131946bdecc483b684f6e6f6ecb98c5594d/slice43-a-final/supported_restart_review.py`:
  PASS. Actual `worker run`/`scheduler run`, normal SIGTERM stop→replacement for each role, existing
  settings GET/PUT, fresh post-replacement publication with unchanged process identities, simultaneous
  live CLI override refusing collective success, and stop of that override restoring success. Both
  stopped intervals refuse success, every predecessor remains diagnostic history, and zero Jobs exist.
- Original Base..Head whitespace PASS. Both original PNG hashes and all frozen/preservation refs match.
  A opened both originals and actual wide/narrow workspace/settings/history captures; diagnostic tables
  scroll within their container. Unrelated tracked deletion/untracked/private files remain preserved.

A scripts, traces, logs and complete manifest remain locally under
`.git/validation-evidence/97316131946bdecc483b684f6e6f6ecb98c5594d/slice43-a-final/`.
A did not mechanically rerun B's full suites. Closure-only document/governance checks are recorded in
the closure handoff; they do not change the already-reviewed Implementation Head.

### Remaining limits and reconciliation

Bounded history is sorted by identity although its truncation copy says “recent”; some diagnostics
remain English and the build retains a chunk-size warning. These are non-blocking quality issues,
not new Tasks or a reason to reopen this Slice. All Explicitly Deferred items above remain deferred.

A reviewed all three role-experience guides; no additional reusable lesson is needed. CURRENT
requirements/journey/architecture and operator guidance now describe accepted behavior. V1 cutover,
new providers/identity systems, unbounded work, cross-Task bulk mutation, automatic uncertain replay
and the other Contract deferrals remain outside closure. No next large Slice is selected here.
