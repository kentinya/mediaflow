# Slice 43 — V2 Automation Workspace and Engine Settings

This A-owned Contract delivers the complete Automation journey: manage bounded definitions,
preview and authorize scheduled work, start one deliberate run, follow independent outcomes and
recovery, and publish engine settings whose actual runtime consumption is visible.

```text
Slice ID: 43
Name: V2 Automation Workspace and Engine Settings
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 853973dbbf8289fa2ad40657033e94e870a690e4
Implementation Head: 7b9bc83fd2f14271f594924895b976ca3a02af0e
Development Hold: LIFTED BY USER — 2026-10-12
Contract Revision: 2026-10-13 — user-approved single-mode Automation; original Slice Base retained
Working Branch: main
Risk: High
Final Test Level: T4
Next Action: DEVELOPER IMPLEMENTS PLANNED TASK 43.2 WHEN DIRECTED
```

## Authority and current state

The user explicitly authorized A to resume Slice 43 after accepted Slice 44, integrate its accepted
changes, retain the original Base and unresolved Task blocker, and hand Task 43.1 to B. The user's
subsequent direction makes the Slice 44-era current documents and Slice/Task rules authoritative.
[AGENTS.md](AGENTS.md) owns permanent invariants; [the development workflow](docs/development-workflow.md)
is the sole lifecycle authority. The current [Task template](Task/TEMPLATE.md) and role guidance
remain those from accepted Slice 44. Frozen snapshots supply the original business commitments,
lineage and review evidence; their old document layout, historical statuses and governance wording
do not override these current rules.

Applicable requirements are UX-001 through UX-010, REQ-SCHED-001 through REQ-SCHED-007,
REQ-TASK-001/002/003/005/006/007/008/009, REQ-RECOVERY-002/006/009, REQ-SAFE-008 and the existing
Storage, execution and configuration invariants. V2-AUTO-001 through V2-AUTO-009 govern this journey.
V2-AUTO-009 is the user's explicit single-mode V2 product amendment; frozen V1 historical meaning
and execution authority/safety invariants remain intact. Only the business capability below is resumed;
accepted closures and deferrals remain historical facts.

| Preserved record | Immutable reference |
|---|---|
| Original Slice Base | `853973dbbf8289fa2ad40657033e94e870a690e4` |
| Original Task 43.1 Base | `79544d9aba697036405b06054c0c56a740281bab` |
| Resumption Developer checkpoint | `b364a04d1c916ed327e3e8f470dc05e413ad80e6` — unaccepted at resumption |
| Frozen Contract and Task/B evidence | `8a41e131f3a668388381ab51c8876668108871d8:SLICE.md`; `a447e3129be89bd20f6a24831b2be122d4fdf955:TASK.md` |
| Accepted Slice 44 closure | `a72252091d5d46edf3e2114b994036ae21b08e2e` |
| Integrated source / A activation | `28eb41997e1bac1cffef13896bc769ba7ffcfd6d` |
| Resumption B reassessment | `39a6a40e4a66de508a331c2d83d17d65578c08cc:TASK.md` — FIX REQUIRED at resumption |
| Current Developer candidate / report | `7b9bc83fd2f14271f594924895b976ca3a02af0e` / `6da94ad8627b27363c210b224ae175d3cf1d8c33:TASK.md` |

At the user's request, local `main` now contains accepted Slice 44 and the resumed unfinished Slice 43.
The source and preservation branches remain available. The Implementation Head field identifies
the current product candidate, passed by B at Task level; no A Slice acceptance is implied. The integrated source retains runtime schema 45, canonical
MediaLibrary-plus-path classification and explicit legacy conversion, page-local Rules tests and
separate complete-flow checks, both-library file operations/navigation, and bounded ResourceLibrary
folder/mixed Organize. The resumption checkpoint adds no Run-once behavior and changes no recovery
promise.
The [resumption assessment](docs/reviews/slice-43-resumption-20261012.md) records integration checks
and their limits.

Task 43.1 is PASS under B's review of `7b9bc83fd2f14271f594924895b976ca3a02af0e`. The retained-history
window and corrupt-evidence blockers were corrected; independent application/API, 505-publication/
reopen and native-browser evidence is indexed locally at
`.git/validation-evidence/7b9bc83fd2f14271f594924895b976ca3a02af0e/b-review43.1-20261013/INDEX.md`.
That Task's checked-publication/history facts remain valid. Its three-mode lifecycle surface does
not yet satisfy the new single-mode requirement. Prior reports/review rounds remain in Git;
local evidence is not claimed remotely reachable. Slice readiness and A Final Review are not claimed.

### User-approved Contract change — 2026-10-13

The user explicitly authorized A to retain only `自动整理` and update the related documents.
This is a material product/Contract change, not a wording clarification: three-mode selection,
new scan-only/scan-and-plan scheduled admissions and their Run-once branches are superseded.
Keep Slice 43 ACTIVE and its original Base; the organizing workspace, settings, safety and recovery
boundaries remain the same business capability. Standalone Scan, Preview and DryRun are unchanged.

New/create/copy/converted definitions use `automatic-organization` without a selectable mode.
All definition-bound new admissions share that restriction, including API/CLI compatibility paths.
Legacy scan/plan definitions remain readable/exportable with their real mode and actionable legacy
status; they cannot emit new scheduled or manual work after the change is implemented. Explicit
conversion reviews changed effects, publishes a disabled automatic-organization successor and
invalidates/revokes prior future authority. Fresh exact Preview and explicit applicable grant or
one-shot intent are required before execution. No import, Save, enable, copy or upgrade silently
turns non-mutating intent into mutation; unrelated legacy objects are preserved by focused Save.
Previously admitted work retains its exact original mode/pin and existing safe-boundary semantics,
never acquires organizing authority and is never relabelled or replayed as automatic organization.

A checkpoints this Contract before B replans the unstarted Task 43.2. That Task keeps the coherent
durable exact Preview/manual Run-once journey, removes the two new-run branches and includes the
native fixed-mode lifecycle/legacy transition needed for a usable single-mode product. The change
is TARGET until implemented and reviewed; it does not close this Slice or reopen accepted Slices.

## User Goal and Journey

An operator can configure when a bounded ResourceLibrary source is automatically organized, understand
what will happen, deliberately permit unattended execution, run the published definition once,
find each run and resolve its affected items, and adjust the engine without confusing saved values
with parameters actually used by resident processes.

- **Entry:** shared-shell `自动化`, an existing definition/occurrence deep link, or the Automation
  settings section reached from System Settings. Preserve existing compatible links and return context.
- **Visible state:** definition inventory, automatic-organization scope/schedule/limit, labelled
  legacy modes, enabled versus authorized versus running state, next scheduled run, real summary
  statistics, independent run outcomes, and published
  versus process-consumed settings. Internal IDs remain optional diagnostic details.
- **Action:** create/copy/edit/enable/disable/reference-safe remove; one checked Save; exact Preview;
  grant/revoke; Run once; inspect filtered history and task-linked recovery; save global settings.
- **Success:** the published definition and current authority govern newly admitted bounded work;
  scheduled occurrences do not require another per-run click; manual real execution retains its
  one-shot intent. Runs and outcomes survive refresh/restart. Settings changes are visibly adopted
  by the actual eligible consumers without routine process restart.
- **Failure:** invalid/stale configuration, missing dependency, unavailable Worker/Scheduler,
  insufficient/revoked permission, capacity, conflict, changed source, invalid pin or uncertain media
  effects are attached to the affected definition/run/item/consumer with durable-state explanation.
- **Recovery:** correct and Save, repreview/regrant where required, reconcile an unknown submission,
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

The list has name, scheduling enabled state, mode, source ResourceLibrary/scope, readable schedule
and timezone, item limit, next scheduled run, latest processing outcome/time and available actions.
Its secondary text may derive from scope/mode; a new free-form description field is not required.
New/Edit/Preview/detail open only by explicit navigation. Provide real empty/setup/dependency/error,
loading and denied states, responsive layout, keyboard use and refresh-safe deep links.

Backend-authoritative bounded search, enabled/source and legacy-status filters, stable sorting and pagination
must keep every authorized definition reachable. Draft-only legacy definitions remain labelled and
reachable for recovery, never counted or toggled as published. New definitions start disabled;
copy creates a new identity, disabled schedule and no copied execution authority.

Provide published definition/enabled counts, month-to-date admitted run count, mode-aware run success
rate, and clearly labelled run-count comparison with the previous month's equivalent elapsed local
calendar period (clamped to that month's end). Return the actual timezone/window and metric basis.
Use the configured system timezone for these cards, separately from each Cron timezone; no timezone
editor is added here. Scheduled and manual definition-linked runs count once by durable admission;
Job/Task/execution links must not double count. Standalone diagnostic/grant-preflight Preview,
discovery alone, grant attempts and rejected admissions are not runs. Previously admitted scan/plan
runs retain their historical mode, count once and use that mode's success meaning, never organization
success. The success denominator is terminal runs in that admitted cohort, including failed,
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

The mode is fixed to `自动整理`; create/edit/copy has no selector for scan-only or scan-and-plan.
Legacy definitions show their original intent and a dedicated conversion/history action. Conversion
or copying a legacy definition into a new automatic one explicitly reviews the changed effects,
starts disabled and carries no old authority. Backend publication/admission rejects attempts to
create, re-enable or run a removed mode; unchanged legacy objects must not block unrelated focused
publication or be silently dropped from the successor. Import retains legacy data for recovery,
never enables new legacy scheduling or automatically converts it to organizing work.

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

### RO-3 — Exact Preview and scoped unattended execution

Native forms complete the existing zero-media-mutation Preview and explicit grant/revoke journey.
Preview shows source bound, RecognitionType/policies, identity, destination, operation, conflicts,
capabilities, expected effects, ineligible items and next actions. Long analysis uses durable work.
Evidence identifies the exact tested candidate/published definition and becomes stale when its
required binding changes; a draft Preview is never shown as Active or as execution authority.

Initial unattended grant requires exact valid Preview and explicit review of scope, limits,
organizing intent and permitted effects. Keep existing grant validity/revocation rules authoritative; saving, copying,
enabling or broadening a definition cannot silently create or expand authority. Valid scheduled
authority permits future due runs without per-run Preview/Execute clicks, while normal per-item
planning and current mutation checks still apply. Blocked items remain independently recoverable.

Scheduler remains an idempotent due-occurrence emitter, preserving existing interval coalescing,
Cron/timezone/DST and restart behavior. It cannot choose policies or mutate media. Existing locks,
claims and fences protect overlapping manual/scheduled work; no new overlap/backfill policy is added.

### RO-4 — Deliberate Run once with unchanged schedule

`运行一次` uses the exact published automatic-organization definition, source scope and item limit. A disabled
schedule may be run manually with current command permissions; this does not enable the schedule,
revive a grant or bypass execution gates. Draft-only work must first be published.

Run once enters the existing manual exact Preview and explicit
one-shot execution journey: discover/select a bounded live source set within the definition scope,
show the reviewed effects, then execute exactly that selection. Reuse existing selection/Preview/
execution authority; do not turn a persistent scheduled grant into manual execution permission or
execute a changing whole-library scope. Expensive discovery/analysis is durable and cancellable at
existing safe boundaries. A preflight is not counted as an admitted media execution.

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

### RO-5 — Cross-definition history, results and native recovery

Provide bounded server-filtered history by definition, mode, trigger, outcome and time, including
scheduled occurrences and manually admitted runs. Pending/pre-Task failures remain visible. Keep
scheduler blocked-emission diagnostics distinct from actual admitted runs and processing outcomes.
Latest-result projection and statistics must respect linked Task/items, not interpret Job completion
as successful organization. History preserves name/scope/mode/version at admission or labels missing
legacy evidence; current rename/remove cannot rewrite it.

Expose start/end, counts, reached item bound, failure/effect certainty and concrete next action.
Reached bound does not prove scope exhaustion. Reuse native Operations detail, records/export,
cooperative controls and per-item decision/analysis/continuation instead of another recovery engine.
Preserve list/filter/definition context when returning. Original, continuation and sibling results
remain independently traceable across restart; uncertain effects stay investigation-only.

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
recovery services. Existing V1/API/CLI configuration and old Automation/Task/Job links remain compatible
or resolve through a truthful contextual route, with the explicit single-mode exception above for new
definition publication/admission. A removed mode submitted directly cannot bypass the Web restriction.
Legacy definitions offer conversion/history, not a hidden Run-once branch or silent reinterpretation.
Empty Active is valid and offers dependency guidance;
absence of Active leads to Settings, while broken prior Active offers recovery rather than new setup.

Permission loss, stale forms/evidence, conflicts, missing secret/pin, storage/provider faults,
malformed responses, 401/403 and unknown submissions preserve independent durable state and operator
input where safe. Neither browsing nor polling invokes Provider/Storage mutation, creates work or
implicitly grants authority. Redact credentials and private host roots. Preserve C identity under
NamingPolicy A and ClassificationPolicy A. Cross-page Settings, Rules, Files, Operations, admitted
transfers and resident service behavior remain protected.

## Required Surfaces

- Shared-shell V2 Automation inventory, typed lifecycle/Preview/authority journey, records and settings.
- Typed authenticated API read/command projections over shared Python application authority.
- Existing managed configuration, scheduled occurrence and manual admission/Worker/persistence paths.
- Real resident Worker/Scheduler settings adoption and fresh per-consumer readback.
- Native Operations detail/recovery and System Settings/ResourceLibrary/Rules return links.
- Compatible existing routes and additive durable migration for any necessary links/consumer evidence.

## Safety Invariants and UX Constraints

All permanent invariants apply: Storage-only file access, OrganizerExecutor-only mutation,
zero-media-mutation Scan/Parse/Recognition/Metadata/Naming/Classification/Planner/Preview,
explicit overwrite/delete policy and intent, capability checks without silent operation fallback,
source confinement and stability, bounded work, current RBAC, audit/redaction, exact immutable pins,
atomic admission/publication, locks/claims/leases/fences and no automatic uncertain-effect replay.

ResourceLibrary is the organizing source. Definition and Scheduler never select per-file Provider,
Naming/Classification policies, final MediaLibrary path or transfer action; the existing
RecognitionType policy chain does. Legacy scan/plan pins and standalone analysis cannot acquire
mutation capability. Grant/revoke is separate from Preview, schedule enablement and manual one-shot
authority. Long work is durable;
controls operate at safe boundaries and do not promise rollback or immediate interruption.

The two PNGs define business relationships, composition and visual style only. Names, counts,
dates, paths, timing values and suggested ranges are illustrative. Preserve originals, do not add
sample business configuration or reproduce fixture data. Use real backend actions and bounded
explanations; no raw token/identifier ceremony. Reference checksums at activation:

- `docs/pics/自动化.png`: `d2f759ead56a30dce344ccce97e7c119e144ca728a31b3af8e9a355eefa6ba34`
- `docs/pics/自动化-全局设置.png`: `68d91070e859dd363d3e45dd2d21e38783e0cfbef0867ce28c3f42eac7d6c7b9`

These user-supplied files are pre-existing untracked workspace artifacts at Base. Preserve them and
the unrelated `docs/pics/媒体库.png`; do not stage/recompress them as part of this activation. Missing
reference availability must be reported rather than replacing the originals with approximations.

## Explicitly Deferred

- New pipeline modes, scheduled cache/log cleanup, backfill/catch-up controls, overlapping-run policy,
  priority/reordering, queue replacement, distributed workers or new concurrency/throughput controls.
- New Providers/Storage operations, per-definition policy/destination overrides, MediaLibrary as
  organizing source, unbounded whole-library manual execution or file uploads/downloads.
- Notifications/Dashboard/global System Settings redesign beyond necessary Automation integration;
  identity/Secret Store/deployment editing, changing CLI override authority or auto-restarting services.
- Global Review inbox, cross-task bulk review, arbitrary historical Reprocess, new recovery semantics,
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
| AC-3 | Fixed-mode typed lifecycle and one checked Save publish only the intended change; stale/concurrent/failed/unknown publication preserves prior authority and recovery without sibling Draft activation. Legacy conversion is explicit, disabled, fresh-authority-bound and never changes old pins/history. |
| AC-4 | Schedule, scope, limits and next times use existing semantics; exact Preview/grant/revoke complete natively, copies gain no authority, broadened scope cannot reuse insufficient authority. |
| AC-5 | Due occurrences remain unique across concurrency/restart/DST; scheduled valid grants execute without per-run clicks while current scope/capability/conflict/revocation gates remain enforced. |
| AC-6 | Automatic-organization Run once completes bounded live-source discovery/selection, exact Preview, explicit one-shot execution, duplicate/unknown-admission reconciliation and no schedule advancement. Removed modes cannot start new definition-bound runs through any surface. |
| AC-7 | Definition, manual/scheduled run, Job/Task/execution and per-item results retain durable links without double count; pre-Task failures and removed-definition history remain reachable. |
| AC-8 | Latest outcomes/progress/bounds and native task-linked recovery preserve independent results; waiting/partial/unknown effects are not false success or replay candidates. |
| AC-9 | Settings Save validates/publishes the exact four-field scope; capacity and stale observation retain their real semantics and no setting grants media authority. |
| AC-10 | Real running Worker/Scheduler adopt new polling values without restart or work arrival; fresh per-consumer evidence distinguishes target/adopted/pending/override/stale state and retains old work pins. |
| AC-11 | Web/API RBAC, Active/Draft separation, redaction, zero-side-effect reads, C identity and compatible Settings/Rules/Files/Operations/V1 journeys are maintained. |
| AC-12 | T4 final regression, real Python/Worker/Scheduler browser/process paths, affected upgrade/packaging and reference/private-file checks establish the promised outcomes without expanding deferrals. |

## Final Validation Expectations

Task test assignment and execution stages follow [the current workflow](docs/development-workflow.md#6-test-levels).
This high-risk Slice retains T4 final acceptance. Development/correction feedback does not replace
the complete corrected-candidate gates or Slice Final; the concrete risk coverage below remains required.

- Exercise existing Automation definitions, occurrence/Cron/DST, Preview/grant/execution, admission/
  fencing, settings/configuration and resident suites plus Operations/manual-organize/recovery/RBAC.
- Cover success, invalid/finite/boundary input, missing dependencies, stale/concurrent publication,
  unknown admission, Unicode principal isolation, capacity reduction, revocation during work,
  missing pin/secret, source change, mixed outcomes, current Active A-to-B isolation and restart.
- Query fixtures exceed page limits and include scheduled/manual links, pre-Task failure, partial/
  waiting/cancelled/uncertain/no-work runs, removed definitions, legacy missing evidence and calendar
  boundaries. Validate database-level query/metric behavior, not only frontend fixtures.
- Native Web tests cover form dependencies, check/save/grant separation, polling, return routes,
  denied/stale/unknown states and settings consumption. Real Python/SQLite/Storage/Provider/Worker/
  Scheduler browser paths prove fixed-mode create -> Save -> Preview -> grant -> scheduled result,
  automatic-organization Run once -> Operations, explicit legacy conversion and an affected item's
  existing native recovery. Direct legacy-mode publication/admission refuses safely; old admitted
  pins/history survive upgrade and unrelated focused Save without gaining mutation authority.
- Actual resident subprocess tests change settings while processes are idle/busy, start before Active,
  observe adopted cadence independently of HTTP echoes, and cover long waits, override, loss of
  consumer, DB/config failure and restart. Assert process identities persist when no restart is needed,
  and admitted old work stays pinned. Use controlled clocks/fakes where appropriate for DST/metrics.
- Slice Final normally runs full Python/Web regression, affected browser/process suites, Python
  format/lint/compile, Web typecheck/lint/format/build, governance/whitespace and exact Base..Head
  manifest/private-file audits. Rehearse Base schema44 -> final migration and preserved historical
  rows/pins/authorities if schema changes; include wheel/static serving and supported Compose lifecycle
  checks material to resident changes. Record actual failures/skips/unavailable gates honestly.
- Instrument reads, publication and Preview for zero media mutation; passive reads call no Provider.
  Retain C-with-A/A regression. Use temporary storage/fake/local services, never production media or
  private credentials. Verify both reference checksums; do not weaken tests to turn missing evidence
  into PASS. No FFmpeg/FFprobe.

## Factual updates and review authority

Only A materially changes the Contract, Base, Required Outcomes, safety, acceptance or deferrals.
B/Developer may update factual Implementation Head, Task progress and evidence within their roles.
Task planning/review, correction loops, stop rules, Closure Packet and final review follow
[the current workflow](docs/development-workflow.md). This document does not define a separate lifecycle.

## Closure Packet

Not submitted. Task 43.1 is B PASS; Task 43.2 is replanned and PLANNED against the single-mode
Contract checkpoint `dfd64505fd4344d4d99d1b0ad0a3e07d92fbca33`. Its implementation has not started.
The single-mode transition and other Required Outcomes remain unfinished.
No Slice readiness or closure is claimed.

## A Final Review

Not performed. The resumption and document-format reconciliation are not product acceptance.
Final review will cover the original immutable Base through the submitted Implementation Head.
