# Slice 42 — V2 Operations and Tasks Workspace

This A-owned Contract delivers one daily operator journey: start bounded manual organization,
follow one visible run from queue admission through per-item results, and safely control or recover
that work from the native V2 task center.

```text
Slice ID: 42
Name: V2 Operations and Tasks Workspace
Owner: A — Slice Owner / Architect / Final Reviewer
Status: READY FOR A REVIEW
Base SHA: ffee77348cebcb05e356c8111c5861ed64ca0388
Implementation Head: ce3fc2a3e70d40279fa725b5d7dc838d11123980
Contract Revision: 2026-09-30 — A activation from the operations/tasks reference analysis
Risk: High
Final Test Level: T4
Next Action: A FINAL REVIEW
```

## Authority and sequencing

The user requested analysis of `docs/pics/操作与任务.png`, specifying business logic and visual style
rather than actual data, then requested Slice planning. This activation implements that planning
request, not product code. Slice 41 remains PASS / CLOSED; its Contract, Closure Packet and A review
remain reachable at this Slice's Base. Its immutable Base and accepted Implementation Head are not
changed. Retired Slices 34–36 are not reactivated.

A owns this Contract, its TARGET journey/architecture and stable V2 requirements. Root `TASK.md`
remains a no-active-Task notice. B sizes coherent implementation Tasks only after the Contract and
Roadmap are committed. The sole lifecycle authority is `docs/development-workflow.md`.

## User Goal

An operator opens `操作与任务`, finds current or historical work by business name, scope, type and
time, understands whether it is queued, progressing, waiting for a decision or finished, and sees
what happened to every selected file. They can start an exact bounded organize journey, request
supported pause/cancel, continue safely paused work, resolve a linked decision or retry eligible
failed analysis without replaying successful siblings or uncertain mutations. Normal completion
requires neither CLI commands nor V1 handoffs nor manual execution-token handling.

## Reference interpretation

- Use `docs/pics/操作与任务.png` unchanged. Original SHA-256:
  `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`.
- Adopt the existing light AppShell, blue primary action, summary cards, compact filter bar, task
  table, selected row and right detail panel with `任务详情` / `操作记录`. No second shell.
  Default entry is a full-width list with no selected run; explicit selection opens detail. A
  supported detail link opens that run. Narrow layouts provide complete full-screen detail and
  accessible return to the same list context.
- Counts, names, paths, dates, progress, ETA, posters and administrator identity in the image are
  not production truth or fixed fixtures. Type icons suffice; poster fetching is excluded.
  Pixel-identical comparison is not acceptance.
- `媒体库` / `单个文件` describe example scope, not domain command. Distinguish operation kind,
  source scope and trigger. ResourceLibrary is the ordinary organize source; MediaLibrary remains
  the classified destination and a separate direct-file-management scope.
- Preserve queued, paused, partial success and waiting-decision states. The sample cards cannot
  justify dropping states or claiming queue completion/partial results are success.
- Server cursor paging is acceptable; fabricated totals/page jumps are not. Cancellation is a
  request and never claims to roll back completed effects.

## Baseline and applicable requirements

At Base, code/tests provide persistent Job/Task/TaskItem/Result, bounded status/command queries,
backend lifecycle projections, checkpoints, review/correction/conflict services, recovery admission
and continuations, result export/logs, Worker readiness, immutable pins and fenced OrganizerExecutor
execution. V2 has separate Operations, Tasks, Jobs and detail pages, Scan/Preview and manual Organize.
Files supports bounded selected live ResourceLibrary files and exact Preview; `OrganizeNewPage`
currently directs the ordinary journey to Files rather than creating an intent from FileIndex.

Gaps, not delivered claims: unified inventory/metrics; text/time/scope queries; business labels and
historical scope summaries; complete progress facets; task-scoped native V2 recovery; and general
queued Web continuation of safely paused operator workflows. Files transfers already have safe
continuation, but that does not establish generic Task resume. `completed_items` is not a universal
organize-success count; some failure counts include scan errors. Paged items cannot supply totals.

Compose these foundations without replacing the task engine, resolver, configuration authority or
queue. Applicable requirements: `UX-001`–`UX-010`, `REQ-TASK-*`, `REQ-RECOVERY-*`, `REQ-LOG-*`,
`REQ-RESULT-*`, relevant `REQ-ORG-*`, `REQ-SCAN-*`, `REQ-SCHED-*`, `REQ-API-*`, `REQ-WEB-*`,
`REQ-SAFE-*`, `V2-UX-*`, `V2-AUTH-*`, `V2-MIG-*`, `V2-SAFE-001`, `V2-FILES-*`, `V2-MEDIALIB-*`
and new `V2-OPS-001`–`V2-OPS-008`. Explicit deferrals narrow delivery, not stable product requirements.

## Operator journey and Required Surfaces

| Stage | Required experience |
|---|---|
| Entry | Shared-shell `操作与任务` at `/ui-v2/operations`, existing Task/Job links, Files completion or a linked Automation run. Opening creates no work. |
| Visible state | Bounded searchable runs, trustworthy counts, operation/scope/trigger, queue/Worker conditions, stages, per-item outcomes, known effects and safe next actions. |
| Action | Inspect detail/records/export; start selected-file organization through live Files selection and exact Preview; request permitted pause/cancel; safely continue or resolve an item and reanalyze/re-authorize where required. |
| Success | Admission promptly yields a durable visible run; items survive refresh/restart; progress reflects known outcomes; continuation links to the original item and preserves siblings. |
| Failure | No ready Worker, missing pin, changed source, stale decision, permission denial, Provider/Storage failure, partial/unknown effect or unknown submission outcome retains durable state and a meaningful next action. |
| Recovery | Refresh actual state after uncertain admission; fix the named prerequisite; retain input; resolve the exact item, rerun bounded analysis and confirm the reviewed plan if mutation is needed. Unknown effects stay investigation-only. |

Required surfaces: native V2 list/detail/records and task-linked recovery; typed API read/command
boundaries; shared Python projection/admission/Worker behavior; durable historical links/evidence;
Files/Preview/execution return context; compatible `/api/v1/*`, V1, Task/Job and Automation links.
Automation definitions and Notifications keep their own pages.

## Required Outcomes

### RO-1 — Unified, reference-aligned task center

- Replace the Operations hub with the real inventory, summary cards, text search, status/operation-
  kind/time filters, refresh and bounded paging. Distinguish no work, no matches, unavailable data,
  stale data and insufficient permission.
- Selection opens the detail panel; close restores the list. Supported detail URLs, browser history,
  refresh and authentication continuation preserve bounded context. Existing Task/Job links remain
  meaningful after a Job acquires a Task.
- Chinese business labels describe operation/state. Internal IDs, commands, pins and fences are not
  mandatory steps; bounded diagnostic identity is available when useful.
- Keep existing Scan/Preview discoverable. Automation and Notifications remain separate; their
  configuration/delivery journeys are not redesigned.
- Keyboard, narrow-screen, loading, empty, 401/403, malformed-response and reconnect paths work.
  Poll bounded reads for active work, back off on failure, pause hidden-page polling and settle on
  terminal state. Refresh/reconnect never replays a command.

### RO-2 — One truthful run projection and server-side queries

- Compose explicit durable Job/Task/manual-execution links into one visible run. Pre-Task pending
  or failed admissions and standalone Tasks remain visible. Never join by filename/time/labels.
  Queue completion cannot override the linked Task's partial or failed result.
- Count linked admission/processing once. Different Automation occurrences, retries and recovery
  continuations remain traceable attempts; continuation does not erase original results. All
  existing command families, including both library kinds' direct-file operations/transfers, are
  discoverable; unfamiliar legacy commands get safe labels rather than disappearing.
- Search business label/safe scope and filter status, operation kind and creation-time range on
  the server. Deterministic bounded paging binds cursors to filters and authorization context.
  The browser cannot filter/merge independently truncated collections.
- Cards and filtered totals use the same authorized population and consistent read basis. Status
  counts partition it; `待处理` is a labelled overlapping attention facet, not another mutually
  exclusive terminal state. Card click applies its filter. Label count scope; no page-only totals
  or unavailable-as-zero. Concrete card grouping may follow this semantics without fixing sample counts.
- Supply stable business name, operation kind, trigger and historical source/target scope from
  durable admission evidence or the pinned snapshot. New work retains necessary display context;
  legacy missing evidence is explicitly unavailable. Current Active rename/delete/root changes
  cannot rewrite history. Names/paths/search/errors/export cannot expose host roots or secrets.
- Necessary projections/indexes/additive persistence are allowed with compatible migration and
  bounded query cost. They are not a second execution authority.

### RO-3 — Truthful progress, detail and operation records

- Aggregate state, pipeline stage and item disposition remain distinct. Show readiness blockers and
  pause/cancel request versus acknowledgement without claiming instantaneous interruption. Concurrent
  work may show active item count/list rather than inventing one uniquely current file.
- Use durable task-kind-specific progress. Unknown discovery totals are indeterminate. Known totals
  reconcile mutually exclusive pending/active/waiting/success/skipped/failed-partial/ignored/cancelled
  item counts as applicable. Analysis completion is not Storage success; scan errors and attachment
  steps stay separate from primary-item counts. Waiting/ignored/uncertain never means success;
  completion percentage is not success percentage. ETA can be omitted/unknown; prediction is not required.
- Detail shows scope, trigger, times, progress and independently paged/filterable items.
  `操作记录` shows durable item plan/result/steps and bounded related control/recovery audit/log
  evidence. Result truth does not depend on logs; missing legacy detail is not invented.
- Explain recognition identity, policies, target, conflict, completed steps, cleanup and effect
  certainty where applicable. Fetch task-linked logs on the server, not the entire global log.
  Export eligible results through existing secret-free JSON packages, labelling bounded/truncated
  export instead of implying completeness.

### RO-4 — New organize entry completes the live-file journey

- `新建整理任务` starts native bounded ResourceLibrary file selection using existing Files authority
  and return context. Reusing the Files route is acceptable; a generic explanation/link page alone
  is insufficient.
- Single or bounded multiple eligible live files enter the existing intent/Preview/confirm flow.
  Server resolves SourceIdentity, RecognitionType-bound policies and immutable plan; FileIndex
  cannot authorize physical selection or execution.
- Preview explains targets, operations, attachments, conflicts and destructive implications.
  Explicit execution submits the exact reviewed selection with server-held authority, no CLI/token
  handling. Known admission returns to the task center with that run selected, including Worker waiting.
- Missing setup/policies/permissions, stale file/Preview, conflicts and unknown admission preserve
  selection/input or durable work and offer a safe next action. No repeated admission/fallback.
  Files-originated Organize and existing bounded Scan/Preview remain usable.

### RO-5 — Backend-authoritative controls and safe Web continuation

- Render backend-advertised actions; revalidate permission, state, ownership and optimistic version
  on submission, with duplicate/concurrent protection. Explain actual unavailable actions; frontend
  state never grants authority.
- Cancellation targets the actual queue/execution owner. Pause/cancel is cooperative, preserves
  completed effects and explains in-flight calls. Request acceptance and observed stopping stay
  distinct; no force-kill, implicit rollback or media deletion.
- Safely paused asynchronous operator workflows that offer Pause must provide native Web Continue
  for the exact remaining admitted scope. Extend durable queued continuation where needed using
  existing Worker/checkpoint/admission/fencing, not long synchronous HTTP or shelling out to CLI.
  Preserve existing safe Files transfer continuation.
- Continue preserves pin and excludes completed/ignored/uncertain effects, rechecks source,
  capability/current permissions and applies the execution path's authority rules. A stored
  `execute_authorized` flag cannot reissue consumed one-shot authority or override a revoked
  unattended grant. Changed plans or insufficient authority require native Preview/explicit intent.
- Legacy/synchronous work that cannot safely continue explains missing evidence/unsupported path.
  This exception cannot omit Continue for new supported pauseable async work or make CLI the
  ordinary recovery path.

### RO-6 — Task-scoped native recovery without replay

- Every failed/waiting/partial item exposes stage, blocker, durable state, known operations, effect
  certainty, retry safety and allowed actions. Success stays terminal and visible. Unknown media
  effects offer investigation/evidence/export, not Retry/Execute.
- Complete task-linked Recognition selection/ignore, Metadata candidate/correction/ignore,
  Classification decision and conflict-resolution through existing services and legal choices.
  Typed forms preserve input and reject stale checkpoints. Saved review decisions do not execute
  media or grant overwrite/delete permission.
- An explicit continuation may compose safe decision persistence and bounded analysis admission
  while keeping exact Preview/mutation authorization separate. Only meaningful intent, ambiguity
  or authority needs operator interaction. No raw checkpoint/revision/token entry, V1 or CLI fallback
  for the ordinary task-linked recovery journey.
- Support single eligible failed analysis and explicitly selected bounded failed-item batches
  through existing recovery gates. Revalidate each selection: mixed eligible/stale/successful/unknown
  items have independent accepted/refused outcomes. No resetting all failed statuses, automatically
  including future failures or replaying siblings.
- Link original item, decision, continuation, new Preview/execution and outcome. Preserve original
  history after failure/restart. Missing pins refuse safely; fixing Active does not repin history.
  Configuration editing stays in Settings/Rules with safe return/refreshed eligibility.
- Retired file-level re-recognition, metadata rematch, file re-plan and recognition retry-pending
  endpoints stay retired. Use retained Task/checkpoint/decision boundaries.

### RO-7 — Integration, privacy and failure recovery

- History, controls and admitted continuations survive restart/Active changes with pins and fences.
  Missing/stale Worker, schema mismatch, unsupported command and missing pinned dependency explain
  waiting/refusal and the next action.
- Web/API share application behavior. Existing Files, MediaLibrary, Rules, Automation, Notifications
  and V1 remain functional, with links returning to the affected run/item.
- Read/detail/filter/refresh/export creates no work, invokes no Provider and mutates no Storage.
  Explicit eligible correction/search/analysis uses the bounded Provider abstraction. Failed reads
  are not empty/success and cannot authorize resubmission.
- Backend redacts secrets, endpoints, host paths and adapter exceptions. Reconcile unknown command
  outcome from durable identity before another explicit action. Forms/selections/cache do not leak
  across principals after authentication changes.

## Safety Invariants

1. Storage ports confine media I/O; only OrganizerExecutor mutates. Scanner, Parser, Recognition,
   Metadata, Naming, Classification, Planner and DryRun remain zero-mutation.
2. Job, Task, item, Result and Automation Definition stay distinct. Run projection grants no authority
   and creates no parallel queue/task state machine.
3. RBAC, exact scope, live source identity, capability, immutable pin, locks/leases/fences, audit and
   optimistic admission remain backend-authoritative at every applicable boundary.
4. Preview/decision persistence grants no execution. Delete/Overwrite/cleanup require explicit policy
   and authority. No silent operation fallback or scope expansion.
5. Continue/retry does not replay success, ignored terminal items or unknown effects; partial known
   effects continue only where the safety gate proves the specific next operation safe.
6. New Active governs new admission, not historical repinning. RecognitionType C remains C under
   A Naming/Classification/Organize reuse.
7. Pause/cancel is cooperative and does not undo effects. Worker ownership/command readiness, not
   API liveness or UI state, governs execution availability.
8. Memory-only principal authentication, bounded redacted evidence and no FFmpeg/FFprobe remain.

## Explicitly Deferred / Excluded

- Unbounded whole-library manual organize, MediaLibrary as new organize source, new pipeline modes,
  file operations/providers, media uploads/downloads or automatic scheduling from this page.
- Automation definition/global-settings redesign, notification or dashboard redesign, standalone
  global Review inbox, cross-task bulk review, arbitrary historical Reprocess and V1 retirement.
- History deletion/retention/archival, task rename/edit, priority/reordering, queue replacement,
  distributed workers, hard interruption and universal rollback. REQ-TASK-004's broader history
  management remains a product requirement outside this delivery boundary.
- Automatic uncertain-effect reconciliation/replay, new destructive authority, failed-batch automatic
  execution and new Provider switching/identity/secret-store systems.
- Poster acquisition, fabricated ETA/byte-speed, required ETA prediction, WebSocket/SSE infrastructure,
  exact numbered-page jumps, pixel-identical fixtures and image changes/recompression.
- New policy semantics or restoration of retired direct file retry/re-recognition/rematch/re-plan APIs.

## Slice Acceptance Criteria

| ID | Acceptance |
|---|---|
| AC-1 | Native shared-shell inventory/detail/records follows reference structure/style with real data, closed detail on entry, selected detail/deep links, narrow/keyboard use and preserved context. |
| AC-2 | Run remains visible before/after Task creation without double count; direct Tasks/all existing command families remain visible; continuations retain linked independent history. |
| AC-3 | Server text/status/kind/time filters, bound cursors, totals and status/attention counts stay authorized and truthful across pages, changed filters, concurrent work and empty/failure states. |
| AC-4 | Historical name/scope is durable/pinned or explicitly unavailable; Active rename/delete never rewrites history; library kinds and privacy remain distinct. |
| AC-5 | Unknown totals, queue/wait/pause/partial/ignored/unknown effects, concurrent stages and scan errors yield reconcilable progress; Preview is not organize success and ETA is not invented. |
| AC-6 | Detail/records provide independent paged items/steps/results, explanations, task-linked logs/audit and scoped JSON export without hiding siblings or relying on logs as sole truth. |
| AC-7 | New-task and Files-selected-file journeys reach exact Preview, explicit authorized execution and the selected durable run; stale/unknown admission never duplicates work or changes source authority. |
| AC-8 | Backend pause/cancel and native Continue work at safe async boundaries; duplicate/stale controls, in-flight calls, lost Worker and insufficient/revoked authority remain safe/actionable. |
| AC-9 | Task-linked recognition/metadata/classification/conflict decisions and single/bounded failed-analysis recovery complete in V2 through exact checkpoints, analysis and separately authorized mutation. |
| AC-10 | Mixed recovery preserves per-item admitted/refused state; successful/ignored/unknown effects are not replayed; original and continuation history survive restart. |
| AC-11 | Reads/refresh/export are side-effect free; malformed/401/403/unknown outcomes/missing pins preserve evidence and privacy; Active changes cannot rewrite admitted work or C identity. |
| AC-12 | Focused/full validation, real Python/Worker browser journeys, compatible affected migrations/packaging and unchanged reference satisfy final T4 evidence; deferrals stay excluded. |

## Final Validation Expectations

- B assigns Task levels by actual risk. Lifecycle/continuation, execution authority, pins, migrations
  and fencing require T4; isolated presentation/projection may justify T2/T3. This activation is
  documentation planning, not a product-test pass or implementation claim.
- Build focused Python evidence on Operations workspace, Task persistence/pause/retry, recovery
  admission/single/batch continuation, recognition/metadata/classification/conflict, manual Organize,
  Files transfers, Worker, logs/export and API security suites.
- Exercise repository queries across pages and Job-to-Task transition, consistent counts, legacy
  missing evidence, command families, concurrent changes and redaction; not only field assertions
  or frontend fixtures.
- Prove success, invalid input, conflict, stale/duplicate admission, permission denial, lost Worker,
  missing pin/secret, changed source, partial/unknown effects, sibling exclusion, Active A-to-B
  isolation and restart/fencing with temporary storage and fake/local services.
- Web model/query/component tests cover navigation, filters, polling, control reconciliation, stale
  forms and mixed recovery. Real Python/Worker browser paths cover selected-file organize, queue
  visibility, pause/continue/cancel, decision-to-result recovery and investigation-only unknown effects.
- Slice Final normally runs full Python/Web regressions; affected browser tests; frontend typecheck,
  lint/format/build; Python format/lint/compile; governance, whitespace and Base..Head manifest/private
  file audit; package/static serving and schema/upgrade rehearsal if persistence changes. Prove
  resident continuation after restart in the supported deployment boundary, not only mocked HTTP.
- Instrument no media mutation on reads/Preview/decision-only actions, no Provider on page reads,
  redaction and C identity. Verify original reference checksum. Production TMDB/SMB/OpenList/S3/R2
  or user media is not required for unit tests; unavailable real-service gates are not PASS.

## Delegated factual updates and stop rule

After activation checkpoint, B owns Task sizing/review. Delegation covers only factual Implementation
Head, Task progress, Closure Packet and test evidence. Material outcomes, deferrals, Base, safety or
acceptance changes return to A. Normally plan roughly 3–7 coherent vertical Tasks; more than 8 needs
workflow complexity reassessment. Do not plan one Task per tab/field/endpoint/test.

After every Task PASS, reevaluate RO-1 through RO-7. Once outcomes are met, run Slice Final, emit one
Closure Packet with `SLICE READY FOR A REVIEW`, set `READY FOR A REVIEW` and stop. Only A reviews
Base..Implementation Head and declares PASS / CLOSED; P2 polish is not a new Task.

## Closure Packet

```text
Slice: 42 — V2 Operations and Tasks Workspace
Base SHA: ffee77348cebcb05e356c8111c5861ed64ca0388
Head SHA: ce3fc2a3e70d40279fa725b5d7dc838d11123980
Developer report: f2ac5f84d0cd0c44c78fc547ad44f9c5b9e17903
```

Required Outcomes:

- RO-1 COMPLETE — unified reference-aligned inventory, selection, filters, paging, polling,
  deep links/authentication continuation and bounded error/empty/narrow/keyboard states.
- RO-2 COMPLETE — explicit Job/Task/execution links, authorized server queries and consistent
  counts, durable public scope labels and independently traceable continuations.
- RO-3 COMPLETE — task-kind-specific progress, uncertainty, paged items/records, exact result/
  step evidence, related logs/audit and bounded redacted JSON export.
- RO-4 COMPLETE — new organize -> live ResourceLibrary Files selection -> exact Preview ->
  explicit execution -> selected durable run, with safe stale/unknown admission recovery.
- RO-5 COMPLETE — cooperative owner-aware controls and real queued remaining-scope continuation,
  original scope/pin/budget/fences, native exact Preview when renewed authority is needed.
- RO-6 COMPLETE — native Recognition/Metadata/correction/Classification/conflict/ignore decisions,
  safe single and mixed selected batch analysis, separate reviewed execution and linked outcomes.
- RO-7 COMPLETE — shared API/Web application gates, restart/Active isolation, zero-side-effect
  reads, redaction, exact principal/session isolation and legal Unicode identity recovery.

Required Surfaces:

- Native V2 list/detail/records and task-linked recovery: COMPLETE.
- Typed API read/command boundaries: COMPLETE.
- Shared Python projection/admission/resident Worker behavior: COMPLETE.
- Durable historical links/evidence: COMPLETE.
- Files/Preview/execution return context: COMPLETE.
- Compatible /api/v1/*, V1 and Task/Job links: COMPLETE.
- Automation run links with independent Automation/Notifications pages: COMPLETE.

Implemented:

- Shared authoritative run queries/projection/history and native task-center presentation.
- Exact live-file organize entry, cooperative lifecycle controls and durable fenced continuation.
- Native task-item decisions and bounded safe analysis, explicit mutation authority and per-item links.
- Additive runtime schema39->44 migration, durable scope/display context and compatible reads.

Tasks completed:

- 42.1 — Unified run inventory/query/navigation — ac5a43ed89d5d782809569ce5e58aedb8f2b03cb.
- 42.2 — Run detail/progress/records/export — faabf20dc034c4c8da310928b3f39b0512616da6.
- 42.3 — Native new organize/admission/return — c0559eba2585fc6cd5650e21e24b3125f7526e01.
- 42.4 — Native controls and safe queued continuation — 73b171254f626f40364d910fe15583dd896e6da1.
- 42.5 — Native task-item decisions/failed-analysis recovery — ce3fc2a3e70d40279fa725b5d7dc838d11123980.

Final Tests:

- `.venv/bin/python -m unittest discover -s tests`: final serial PASS,2184 total/2177 passed/
  7 explicit skips,386.617s. First concurrent attempt FAIL,1 Rules race failure/7 skips,604.979s;
  unchanged `tests.test_v2_rules_workspace_commands` rerun41/41 PASS. No assertion/timeout/skip edits.
- `web/: npm run test -- --run`: final serial PASS,65 files/1005 tests,0 skips,370.33s. First attempt FAIL,1004 passed/1 failed
  of1005; unchanged AutomationRouter module rerun11/11 PASS. No failure relabelled PASS.
- Five required focused Python groups combined:507/507 PASS,173.637s. Release/security/
  migration/upgrade four modules:19/19 PASS. Full Web covers the required affected modules.
  Exact module lists/commands are retained at `git show f2ac5f84d0cd0c44c78fc547ad44f9c5b9e17903:TASK.md`
  under Required Tests and in `/tmp/mediaflow-b42-final/review-evidence.md`.
- `web/: npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`:
  21/21 PASS,1.9m,actual Python/API/SQLite/Storage/Provider/Worker.
- `web/: npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts`:
  1/1 PASS,16.9s,production-config Chinese principal and exact post-reload reconciliation/resend.
- `web/: npm run test:e2e -- tests/e2e/library-files.spec.ts`:40/40 PASS,49.6s.
- Affected Operations/manual-organize/manual-operations/deep-link specs:66 PASS/2 FAIL,2.2m.
  Same two failures independently reproduced on unchanged original Slice Base with
  `tests/e2e/deep-link.spec.ts --grep 'an explicit route choice at the boundary|V1 handoff does not leak'`.
  Marked FAIL/PRE-EXISTING/UNRELATED, never PASS or hidden skip.
- Ruff format339/check,compileall,pip check,both example config validations; Web typecheck/
  lint/format/build; governance/whitespace/reference/private-file and exact manifest audits:PASS.
- `pip wheel . --no-deps --no-build-isolation` and `scripts/wheel_smoke_test.py`:
  PASS,isolated installed CLI/database/backup/restore/upgrade and lease-contention checks.
- Real original Slice Base39 API/Preview/Worker fixture -> current44:PASS,every old column/row,
  pins,consumed one-shot authority,plans,Tasks,Results,audits preserved; idempotent second reopen.
- `scripts/docker_release_security_smoke_test.py`:attempts1/2 build/image/Compose inspection PASS,
  then health wait FAIL; actual unchanged3s probe timeout evidence retained. Serial rebuild attempt3
  UNAVAILABLE at external setuptools>=68 download. Verified reuse of the exact already-built image
  `sha256:b189638532fc73e27984a5bd0edd684f61e09187fe7713abcb60d4b755bbc4d8`
  matches all158 Python files and4 built Web assets. Unmodified runtime/security/host-boundary
  assertions PASS via transparent `/tmp/mediaflow-b42-final/docker_verified_image.py` build reuse.
  Four services healthy; resident Worker completion,static serving,RBAC,privacy checks PASS.
- Optional dedicated real SMB/S3/OpenList acceptance and Local/SMB/OpenList/S3 endurance profiles:
  7 explicitly SKIPPED/UNAVAILABLE; their gate-validation subset6 PASS. No production service claimed.
- Exact attempts/logs/reproduction/manifest evidence: `/tmp/mediaflow-b42-final/review-evidence.md`.

Safety Evidence:

- Read/refresh/export/Preview/decision paths perform no media mutation; passive reads invoke no
  Provider. Real recovery analysis and later explicit OrganizerExecutor mutation remain distinct.
- RBAC,exact SourceIdentity/selection/checkpoint,pin,one-shot/grant authority,claims/locks/fences and
  audit remain backend-authoritative. Success/ignored/uncertain siblings are not replayed.
- Original history survives restart/Active changes; new Active never repins prior work; C with A/A
  policies stays C. Unknown admission is reconciled before deliberate repeat; tokens remain memory-only.
- No removed/weakened tests,hidden skips,silent operation fallback,private config or real credentials.
  Reference SHA256 unchanged:a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86.
  `config/alist.json` ignored/untracked/unstaged and not read. No FFmpeg/FFprobe. User PNGs preserved.

Known Non-blocking Issues:

- P2: two pre-existing Deep-link tests expect the retired Review link/Configuration handoff;
  same failures on original Slice Base,current required native recovery/settings journeys work.
- P3: existing bundle-size advisory,SQLite ResourceWarnings and jsdom navigation notices remain.
- Validation variability: failed initial concurrent regressions/health checks and external dependency
  download attempt remain recorded separately from passing unchanged serial/runtime validations.

Explicitly Deferred:

- Unbounded whole-library manual organize, MediaLibrary as new organize source, new pipeline modes,
  file operations/providers, media uploads/downloads or automatic scheduling from this page.
- Automation definition/global-settings redesign, notification or dashboard redesign, standalone
  global Review inbox, cross-task bulk review, arbitrary historical Reprocess and V1 retirement.
- History deletion/retention/archival, task rename/edit, priority/reordering, queue replacement,
  distributed workers, hard interruption and universal rollback. REQ-TASK-004's broader history
  management remains a product requirement outside this delivery boundary.
- Automatic uncertain-effect reconciliation/replay, new destructive authority, failed-batch automatic
  execution and new Provider switching/identity/secret-store systems.
- Poster acquisition, fabricated ETA/byte-speed, required ETA prediction, WebSocket/SSE infrastructure,
  exact numbered-page jumps, pixel-identical fixtures and image changes/recompression.
- New policy semantics or restoration of retired direct file retry/re-recognition/rematch/re-plan APIs.

Documentation Reconciliation Needed:

- A reconciles Slice42 TARGET to accepted CURRENT in the Chinese canonical specification,
  docs/product-experience.md,docs/v2-requirements.md and docs/architecture.md,including native
  recovery replacing ordinary V1 handoff and actual runtime schema44/shared continuation boundaries.
- A reconciles Roadmap/Progress status once after its Final Review; B has not closed the Slice.

Decision: SLICE READY FOR A REVIEW

## A Final Review

Not conducted. ACTIVE is planning authority, not product completion or test acceptance.
