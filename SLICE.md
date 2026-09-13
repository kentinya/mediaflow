# Slice 33 — Operations Workspace

This is the A-owned Slice Contract for the next independently reviewed V2 capability after Slice
32. Slice 32 remains `PASS / CLOSED` in Git, Roadmap and Progress history and is not reopened.

~~~
Slice ID: 33
Name: Operations Workspace
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 827c36b410687e41b1da53ba6475d8c03a47dbfd
Implementation Head: 437135dbe36e63d733eb994cda8edb23fcf671bc
Historical Closure Checkpoint: dcc2f34c38975662ddbc78e160bbbc2d423ae702
~~~

The Base is the actual committed `main` checkpoint immediately before Slice 33 activation and
implementation. It must not move when B plans Tasks or Developer work begins. This Contract and its
Roadmap activation commit follow the Base and are governance changes, not Slice implementation.

## V2 program boundary

V2 remains a sequence of independently accepted user capabilities:

~~~
Slice 30 — V2 Frontend Platform & Architecture — PASS / CLOSED
Slice 31 — Operator Shell & Information Architecture — PASS / CLOSED
Slice 32 — Library & Files Experience — PASS / CLOSED
Slice 33 — Operations Workspace — ACTIVE (POST-CLOSURE P1 CORRECTION)
Slice 34 — Review & Recovery Workspace — PLANNED
Slice 35 — Configuration Administration — PLANNED
Slice 36 — V2 Parity, Accessibility & Legacy UI Retirement — PLANNED
~~~

This Contract owns the V2 daily-operations journey: actionable Dashboard entry, bounded manual
Scan/Preview/Organize, durable Task and Job observation, scheduled Automation operation and
Notification delivery operation. It may reuse the narrow managed-revision/object validation and
checked-activation lifecycle needed to publish Automation Task Definitions and Webhook Definitions,
but it does not absorb general Configuration administration or media review/recovery journeys
assigned to Slices 34 and 35.

## Post-closure correction activation

The 2026-09-13 Closure Packet and A Final Review below remain immutable historical facts for the
accepted range `827c36b410687e41b1da53ba6475d8c03a47dbfd..8a0048008057beabada1a36c53d5fdc3153e8e7b`.
After that closure, A confirmed a P1 regression in the V2 Manual Organize Preview journey: the
bounded backend plan publishes RecognitionType, operation and destructive implications, but the
typed frontend projection/page boundary does not consistently retain and consume those facts. The
page can therefore render an exact plan as though those fields were absent and can omit the
separate overwrite/source-cleanup confirmations. Backend admission independently rejects missing
destructive authority before mutation, so the inspected defect does not establish unauthorized
Storage mutation; it still breaks RO-4, the Manual Organize required surface and the explicit
destructive-intent Safety Invariants.

This correction is confined to restoring the already-promised exact Preview and fail-closed Web
confirmation journey. Acceptance requires the typed operator model to represent and validate the
three bounded plan facts, the page to display them without bypassing the type boundary, destructive
requirements to gate only the exact selected plans and malformed/missing safety projection to offer
no execution, with focused regression coverage preserving the independent backend admission checks.
Slice 34 remains limited to review decisions, conflict resolution, Reprocess, checkpoint
continuation and failed-item/batch recovery; it does not own this Slice 33 regression.

The Slice Base and historical accepted Implementation Head do not move during activation. B owns
the focused correction Task and its Difficulty/Test Level; because the defect crosses the typed Web
projection and destructive-confirmation safety boundary, B must assess T4 rather than treat it as a
cosmetic-only label fix.

## User goal and vertical journey

**User goal:** within the current API-principal Bearer authentication architecture, an authorized
operator can use V2 as the daily command center to start a bounded Scan or zero-mutation Preview,
review and execute an exact manual organization without issuing or copying a CLI execution token,
observe each durable Task/Job and item outcome, operate reviewed schedules and Webhook delivery, and
understand the next safe action when work cannot proceed.

**Entry:** open `/ui-v2/operations`, follow an actionable Dashboard status/count, or continue from a
current V2 Library file, FileIndex record or ResourceLibrary scope. Supported operation detail links
remain refresh-safe. An unauthenticated deep entry uses the shared memory-only connection flow and
returns only to the intended safe route; authority-bearing values never enter the URL.

**Visible state:** the workspace separates requests, queue/admission records, processing Tasks,
per-item outcomes and schedules instead of presenting them as one generic status. It shows Worker
readiness, exact source scope, Active/pinned configuration identity, operation mode, progress,
warnings, conflicts/capabilities, manual intent and Preview versions, execution-authority state,
Automation definition/schedule/grant/occurrence state, Notification definition/delivery state, and
bounded failure/recovery guidance without exposing secrets or raw backend payloads.

**Action:** submit a bounded current-source or ResourceLibrary Scan; create and inspect a complete
zero-mutation Preview; create/update a durable manual intent and permitted item choices; select exact
Preview items, explicitly authorize and submit their organization; inspect/filter/page Task, Job and
item detail; request a currently valid cooperative pause/resume/cancel control; manage and preview a
bounded Automation definition and publish it through checked activation, explicitly grant/revoke
unattended authority and inspect schedules and occurrences; or manage/test and checked-activate a
Webhook and explicitly recover one eligible delivery. Each action is permission-gated and only
controls the exact durable object shown.

**Success:** admitted long work immediately has a durable identity and can be followed without
holding a browser request open. Preview changes no Storage. Manual execution consumes backend-bound,
short-lived one-shot authority for exactly the reviewed items, and only OrganizerExecutor performs
the resulting Storage mutation. Scheduled occurrences pin their runtime snapshot and remain tied to
their definition/grant. Every item/delivery records an independent result that links back to the
relevant operation and source when safe.

**Failure:** missing or unhealthy Worker, queue limits, stale/changed source, stale Preview or
configuration version, invalid scope, unsupported capability, conflict, insufficient permission,
expired/consumed/revoked authority, concurrent update, unavailable Active runtime, schedule/grant
ineligibility, delivery lease/dead-letter failure, malformed API response, 401/403 or backend
unavailability is attributed to the affected request/object/item. No failure is rendered as success,
no completed sibling is hidden, and no uncertain Storage effect is presented as safe to retry.

**Recovery:** retry a known-safe read, correct and resubmit an unadmitted request, refresh the exact
durable state, restore Worker/configuration readiness, cancel work cooperatively, rerun Preview after
a stale change, reauthorize an exact reviewed operation, repair/repreview/regrant an Automation
definition, or use the delivery-specific retry/requeue action. Repair of dependent general
configuration may hand off to the current V1 Web Configuration journey until Slice 35. Media review
decisions, checkpoint continuation, Reprocess and failed-item/batch recovery lead honestly to the
current V1 Web journey or the V2 Review & Recovery destination owned by Slice 34; they are never
simulated inside Operations.

## Product Experience / UX constraints

- **Operations is state-oriented, not endpoint-oriented.** The UI distinguishes a submission from a
  Job, a Job from its Task, and aggregate Task status from independent TaskItem/Result outcomes.
- **Routine manual organization is Web-native.** The operator does not run a CLI command, receive a
  raw execution secret or copy an execution token. The backend binds one-shot authority to the
  authenticated principal, exact Preview/configuration/item set, allowed effects, expiry and audit.
- Scan and Preview are plainly labelled analysis actions. Preview runs the complete applicable
  pipeline and presents its findings, but both remain zero Storage mutation and do not imply that an
  Organize was authorized.
- The manual flow starts from operator-recognizable files or a ResourceLibrary scope. Raw File,
  occurrence, fingerprint, intent, Preview, grant, Task or Job identifiers are not mandatory entry
  inputs and appear only secondarily when useful for support.
- Organize has a separate explicit confirmation at the meaningful mutation boundary. Overwrite and
  source cleanup/destruction are separately explained and permitted; they are never inferred from a
  generic Execute click. Unsupported HardLink/SoftLink never silently falls back.
- Task/Job controls appear only when the backend says the transition is currently available and the
  principal has permission. Pause/cancel are cooperative and do not claim to interrupt an in-flight
  Provider/Storage call or undo completed effects. Slice 34 owns media retry/recovery semantics.
- Automation clearly separates an editable Draft definition from the immutable Active snapshot
  actually consumed by Scheduler/Worker. Enabling a schedule is not unattended execution authority;
  Preview eligibility and a separate persistent, scoped, revocable grant remain explicit.
- The narrow Automation/Webhook editor composes existing managed Draft, validation/test and checked-
  activation behavior only for those owned object types. It must not recreate configuration
  authority, label an unactivated Draft Active, or become a hidden general Configuration editor.
- Notification testing is an explicit read-only test of the selected exact revision. Delivery
  retry/requeue/expired-lease resolution changes only the exact delivery state and never reexecutes,
  rewrites or rolls back completed media work.
- Dashboard and cross-links preserve useful bounded context and lead to exact Operations, Library or
  later Review routes. Counts are navigation aids, not permission or authority.
- Loading, empty, partial, queued-without-worker, stale, malformed, unavailable, unauthorized and
  forbidden states remain inside the shared shell and provide the smallest valid next action.
- The workspace remains keyboard-usable and responsive at narrow and wide viewports. Slice 36 owns
  final cross-feature parity, comprehensive accessibility evidence and supported V1 UI retirement.

## Required Outcomes

| ID | Required Outcome | Gap at Base |
|---|---|---|
| RO-1 | **Operations information architecture and actionable Dashboard.** `/ui-v2/operations` becomes a real V2 workspace with typed, refresh-safe task-oriented routes; Dashboard health/counts lead to the relevant bounded Operations views and show truthful permission/readiness state. | Dashboard is a read-only proving page and Operations is a migration placeholder. |
| RO-2 | **Durable Task/Job observation and lifecycle control.** Operators can list/filter/page Tasks and Jobs, inspect linked request/Task/TaskItem/Result and Worker/readiness evidence, follow relevant Library context, and invoke only backend-advertised cooperative pause/resume/cancel controls. | Python API/V1 expose durable processing state and selected controls; V2 has no operational list/detail journey. |
| RO-3 | **Bounded manual Scan and zero-mutation Preview.** From V2 Library or Operations, an authorized operator can choose an exact current file or ResourceLibrary-relative scope, understand readiness/limits, submit Scan or complete Preview, and inspect durable per-item findings and failures. | The authoritative application/API journey exists, but V2 Library only hands operational actions to V1. |
| RO-4 | **Complete Web-native manual Organize.** Operators can create a durable intent, make permitted item choices, review an exact immutable Preview, select exact items, explicitly authorize and admit execution, then follow durable per-item outcomes without CLI issuance, raw execution-token transfer or arbitrary request-supplied paths/plans. | V1 manual services provide exact intent/Preview and server-side one-shot authorization, while V2 has no flow and the general remote Organize Job still exposes a CLI-token mechanism. |
| RO-5 | **Scheduled Automation operation.** Operators can discover, create/copy/edit, validate, preview and enable/disable bounded Automation Task Definitions; checked-activate the owned change while distinguishing Draft from Active; grant/revoke scoped unattended authority; and inspect schedule state, occurrence history and linked work/results. | The current application/API/V1 surface is complete but absent from V2 and its managed-revision semantics are not composed in the V2 shell. |
| RO-6 | **Notification operation.** Operators can discover and manage Webhook Definitions without seeing secret values, run an explicit exact-revision read-only test, checked-activate the owned change, inspect bounded delivery/detail state, and invoke only eligible per-delivery retry/requeue/stale-lease actions with concurrency protection. | Slice 28 delivered authoritative API/V1 behavior; V2 has no Notification journey. |
| RO-7 | **Actionable failure and boundary handoff.** Missing Worker/Active state, queue pressure, stale/concurrent versions, invalid scope, conflict/capability/authority denial, partial/uncertain outcomes, schedule/grant failures, notification failures, malformed data, 401/403 and service errors preserve durable truth and give a safe retry, correction, cancellation, re-preview, reauthorization, V1 Configuration handoff or Slice 34 Review/Recovery destination. | Shared shell errors exist, but Operations-specific recovery and deferred-boundary guidance do not. |
| RO-8 | **Shared authority, coexistence and proof.** Central typed feature/entity/query boundaries use existing Python Application and `/api/v1/*` behavior, add only backward-compatible projections/admission needed by this journey, preserve V1 `/ui`, and prove exact request methods, RBAC, audit, limits, redaction, persistence and mutation invariants. | Slice 30–32 prove the architecture for read journeys; V2 operational admission and high-risk execution evidence are absent. |

## Required Surfaces

1. **Operations route and Dashboard surface.** A real `/ui-v2/operations` landing plus supported
   Task, Job, manual-operation, Automation/schedule and Notification list/detail routes use central
   route metadata, active navigation, safe deep-link/auth continuation and actionable Dashboard
   links without placing authority-bearing values in URLs.
2. **Task, Job and Worker surface.** Bounded list/filter/page and detail views distinguish admission,
   processing and per-item/result state, expose readiness and pinned configuration evidence, link
   exact related work/source context, and offer only authoritative cooperative controls.
3. **Manual Scan/Preview surface.** Current Library selections and explicit ResourceLibrary-relative
   scope compose into bounded admission, progress/detail and per-item findings. Scan semantics remain
   source discovery/indexing; Preview is visibly full-pipeline DryRun with zero Storage mutation.
4. **Manual Organize surface.** Durable intent and choice editing, exact Preview/detail/item
   selection, separate explicit server-bound one-shot authorization, execution admission, progress,
   per-item Result/effect certainty and truthful blocked/expired/stale outcomes form one Web journey.
5. **Automation and schedule surface.** Definition list/detail/editor/copy/enable state, Active versus
   Draft identity, validation, exact Preview/items, object-scoped checked activation, grant
   eligibility/grant/revoke/audit, schedule state/audit, occurrence history and linked
   Job/Task/Result context are operable without exposing raw grants or silently activating a Draft.
6. **Notification surface.** Webhook list/detail/editor/enable state, secret-reference-only handling,
   exact-revision test evidence, object-scoped checked activation, delivery list/filter/detail,
   attempt/lease/dead-letter state and eligible retry/requeue/stale resolution are complete and
   isolated from media execution.
7. **State, auth and cross-surface surface.** Loading/empty/partial/queued/stale/conflict/unsupported/
   uncertain/malformed/unavailable/401/403 states preserve context and offer valid recovery; Library,
   Dashboard, Operations and deferred Review/Configuration destinations link truthfully.
8. **Application/API authority and test surface.** Existing services remain authoritative for
   scopes, transitions, Active snapshots, execution/grant admission, delivery recovery and audit.
   Minimal API/application changes are allowed only when the required V2 journey cannot safely use
   the current projection; automated and built-artifact evidence covers all required paths.

## Safety Invariants

- Python Application/Domain services and `/api/v1/*` remain authoritative. Frontend state, labels,
  hidden controls, cached previews or route parameters never grant RBAC permission, select an Active
  configuration, validate a source, decide a policy/plan or authorize Storage mutation.
- The API-principal Bearer token remains runtime-memory-only and absent from localStorage,
  sessionStorage, IndexedDB, cookies, URLs and handoff links. Disconnect clears authenticated query
  and mutation state, including any unsubmitted manual choices.
- Routine V2 manual execution never asks for, returns to the browser or persists a raw remote
  execution token/secret. Backend authority is short-lived, one-shot, principal/permission-bound,
  exact-Preview/configuration/item/effect-scoped, auditable and atomically consumed or rejected at
  durable admission. Existing CLI/API token support may remain for compatibility but is not the V2
  journey.
- Manual execution rechecks intent/Preview/item versions, Active/pinned configuration identity,
  source occurrence/fingerprint, current conflicts, capabilities, limits and authority before
  acquiring locks or mutation. Request bodies cannot supply arbitrary source/target paths,
  operations, policy identities or provider payloads.
- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation.
  Preview/DryRun runs the complete applicable pipeline with zero Storage mutation. Only
  OrganizerExecutor may call mutating Storage operations.
- RecognitionType C remains C when it selects NamingPolicy A or ClassificationPolicy A. No route,
  intent choice, Preview projection or execution reconstruction changes that identity.
- Overwrite and source cleanup/delete require explicit policy, authority and operator intent; they
  are never inferred or silent. HardLink/SoftLink never silently falls back to Copy or Move.
- Source/destination/attachment locks, immutable snapshot pinning, queue/item limits, idempotency,
  stale/concurrent fencing and per-item durable Results remain backend-enforced. Successful siblings
  stay terminal, and partial or uncertain Storage effects are never automatically replayed.
- Pause/cancel/resume is cooperative at supported boundaries. It never claims to interrupt an
  in-flight Provider/Storage call, undo completed effects or convert uncertain mutation into safe
  retry. Media recovery actions remain owned by Slice 34.
- Automation Draft state is not Active runtime. Schedule enablement is separate from unattended
  authority; grants are persistent, scoped, independently revocable and rechecked at every mutation
  boundary. Revocation prevents future mutation without rewriting completed effects.
- Webhook definitions contain deployment-owned secret references, never secret values. Tests are
  explicit and read-only. Delivery recovery is exact-record, concurrency-fenced and cannot submit or
  replay media work.
- Reads, rendering, prefetch, refresh and navigation remain zero-side-effect. Mutations use explicit
  methods and named user intent; malformed/401/403 handling does not retry a mutation automatically.
- Explanations, logs, DOM, routes and test artifacts remain bounded and redacted. Credentials,
  authorization headers, cookies, raw provider payloads/exceptions, private endpoints and absolute
  host/adapter roots are not exposed.
- No FFprobe/FFmpeg dependency or content probing is introduced. Technical tags remain
  filename/path-derived evidence only.
- V1 `/ui`, existing API compatibility routes, CSP/cache/security behavior and Python-only
  production serving remain intact. No Node production server, SSR, BFF, second HTTP service or CDN
  runtime dependency is introduced.
- `config/alist.json`, production credentials, private endpoints, operator media and local runtime
  state remain ignored/untracked and absent from checkpoints/tests.

## Explicitly Deferred

- Slice 34 Review & Recovery Workspace: Recognition/Metadata/Classification review decisions,
  conflict resolution, explicit Reprocess, checkpoint action submission/continuation, failed-stage
  retry, manual recovery continuation, ignored-item transitions and per-item/bounded-batch media
  recovery. Operations may show/link their state but does not perform these actions.
- Slice 35 Configuration Administration: general managed Configuration/Settings navigation, object
  lifecycle outside Automation Task Definitions and Webhook Definitions, revision comparison and
  evidence administration, import/export and activation workflows outside the two object-scoped
  checked activations owned here. Slice 33 may hand repair of dependent general configuration to the
  current V1 Web surface.
- Slice 36 final V1/V2 surface parity, global Logs/security/configuration-audit migration,
  comprehensive cross-feature accessibility evidence, supported `/ui` cutover and V1 UI retirement.
- Automatic retry/replay of uncertain media effects, rollback/undo of completed Storage operations,
  mutation-history deletion, arbitrary bulk execution, a generic workflow designer and distributed
  scheduling/Workers.
- New Storage/Metadata/Notification providers, provider switching, email/chat/media-server native
  notification transports, general Secret Store integration, mutation-based capability probes and
  changes to recognition, metadata, naming, classification, planning or conflict semantics.
- File upload/download/content preview, file edit/rename/delete, arbitrary Storage mutation, media
  streaming, thumbnails/posters/artwork fetch and arbitrary host-filesystem browsing.
- Built-in username/password identity, session/cookie authority, OIDC, reverse-proxy identity,
  token persistence/refresh/rotation or redesign of the current API-principal authentication model.
- SSR, React Server Components, Node production serving, micro-frontends, CDN runtime dependencies,
  native mobile clients, global search/command palette, localization and complete visual-theme work.

## Slice Acceptance Criteria

1. An authenticated operator can enter or refresh each documented Operations route from the shell,
   Dashboard or Library; an unauthenticated deep entry returns through the memory-only connection
   boundary without leaking a credential or replaying an action.
2. Dashboard and Operations distinguish Worker/readiness, pending/admitted Job, processing Task and
   per-item/result state. Bounded lists/details and cross-links remain truthful under empty, partial,
   stale, malformed, 401/403 and unavailable responses.
3. An authorized operator can submit an exact current-file or ResourceLibrary-relative Scan and a
   complete Preview, follow their durable progress/findings, cancel when backend-eligible and prove
   that Preview/analysis invokes no mutating Storage operation.
4. Starting from recognizable V2 Library context, the operator can create/update a durable manual
   intent, inspect and select exact immutable Preview items, understand targets/attachments/
   conflicts/capabilities/destructive implications, and recover from stale choices or source state
   by producing a fresh Preview rather than silently reusing old evidence.
5. The operator can explicitly authorize and submit the selected manual operation entirely in Web,
   receives a durable work identity promptly, follows independent item outcomes, and never issues,
   sees, copies or persists a raw execution token. Backend tests prove exact binding, one-shot/
   expiry/concurrency behavior, RBAC, limits, audit and rejection before mutation when stale.
6. Only OrganizerExecutor executes reviewed Storage effects. Overwrite/delete/source cleanup require
   explicit permission and intent; link capability failure has no implicit fallback; partial or
   uncertain effects stay item-scoped and are never automatically retried.
7. Automation Definitions can be operated through their complete bounded lifecycle with honest
   Draft/Active state, validation, exact Preview, object-scoped checked activation, schedule/timezone
   state, separate grant/revocation, occurrence history and linked work. An unactivated Draft,
   enabled schedule or stale Preview alone never gains unattended mutation authority.
8. Webhook Definitions, exact-revision tests, object-scoped checked activation and delivery state are
   usable in V2 without exposing secret values. Retry/requeue/stale-lease actions require an eligible
   exact delivery/version and do not alter definitions, sibling deliveries or completed media work.
9. Task/Job and operation failures explain durable state, known effects and the concrete next valid
   action. Cooperative lifecycle controls do not claim undo; Slice 34 media review/recovery actions
   and Slice 35 general configuration repair are explicitly linked/handed off rather than imitated.
10. Central typed API/query/mutation boundaries, component/router/browser tests, focused Python
    integration/security tests and full regression/release gates prove V1 coexistence, exact request
    methods, no automatic mutation replay, redaction, persistence and all Safety Invariants.

## Final Validation Expectations

- `python3 scripts/check_governance.py` passes against the committed Slice 33 Contract and ACTIVE
  Roadmap row, with no active Task before B planning and Base SHA `827c36b4…` unchanged.
- Frontend lockfile/tooling gates pass: `npm --prefix web ci`, format check, TypeScript typecheck,
  ESLint, Vitest/React Testing Library, production Vite build and Playwright browser tests.
- Built-artifact browser evidence covers Operations landing and authenticated/unauthenticated deep
  entry; actionable Dashboard links; Task/Job/Worker lists, details, paging and eligible lifecycle
  controls; Library-to-Scan/Preview/Organize context; exact manual intent/Preview/authorization/
  admission/result; Automation Draft/Active/preview/grant/schedule/occurrence state; Notification
  definition/test/delivery recovery; narrow/wide keyboard use; and all specified failure states.
- Browser/network evidence proves each action sends only the intended authenticated method/body,
  never automatically repeats a mutation, and keeps Bearer credentials, raw execution authority,
  secret values, private paths and provider payloads out of URLs, persistent stores, DOM, console and
  captured artifacts.
- Focused Python tests cover Dashboard/readiness, Task/Job/Scan/Preview/manual-intent projections,
  Web-native one-shot execution admission and persistence, RBAC/limits/audit/stale fencing,
  OrganizerExecutor-only mutation, Automation definition/Preview/grant/schedule/occurrence behavior,
  Webhook definition/test/delivery recovery, redaction and backward-compatible API/V1 behavior.
- Safety regressions explicitly cover Preview/DryRun zero mutation, exact source/snapshot/item
  binding, conflict/capability checks, explicit overwrite/delete/source-cleanup authority, no link
  fallback, one-shot expiry/concurrency, cooperative cancellation, no uncertain replay,
  RecognitionType C preservation and notification/media isolation.
- Any schema migration is forward-only, fail-closed and restart-tested against temporary copied
  fixtures. Persisted admitted work, Task/Job/item outcomes, execution authority, Automation grants/
  occurrences and delivery state survive the applicable API/Worker/Scheduler/Notification Worker
  restart boundary without duplicate admission or mutation replay.
- Existing Python API/security, Storage, FileIndex, recovery, V1 UI, static-serving and release-
  security regressions pass. Docker release-security smoke is run at Slice Final when Docker is
  available and reported `UNAVAILABLE` rather than inferred when not.
- Normal quality gates pass: frontend formatting/type/lint/tests/build, Ruff format/check, full
  unittest discovery, compileall and `git diff --check`. Existing root-CWD private runtime state must
  not be deleted to make tests pass; use an isolated clean checkout when required and report both
  results truthfully.
- Tests use local fakes, local HTTP servers and temporary Storage/runtime/configuration state only;
  no production SMB/OpenList/S3/TMDB/Webhook service, credentials, user media or Internet access is
  required.
- Before Slice Final, B inspects the full Base..Head diff, test deletions/skips/assertion weakening,
  unrelated files and tracked/private configuration. Final Closure evidence records actual totals,
  skips and unavailable gates without inference.

## Historical Closure Packet — 2026-09-13

~~~
Slice: 33 — Operations Workspace
Base SHA: 827c36b410687e41b1da53ba6475d8c03a47dbfd
Head SHA: 8a0048008057beabada1a36c53d5fdc3153e8e7b

Required Outcomes:
- RO-1 — COMPLETE: `/ui-v2/operations` is a typed, refresh-safe command center, and actionable
  Dashboard and Library links lead to bounded Operations routes with truthful readiness and
  permission state.
- RO-2 — COMPLETE: operators can filter/page durable Tasks and Jobs, inspect linked item/result and
  Worker evidence, and invoke only exact backend-advertised cooperative lifecycle controls.
- RO-3 — COMPLETE: V2 admits bounded current-file or ResourceLibrary-relative Scan and complete
  zero-mutation Preview journeys with durable per-item findings, failures and eligible cancellation.
- RO-4 — COMPLETE: V2 provides the complete durable intent, exact Preview/item selection,
  server-bound one-shot authorization, admission and per-item outcome journey without exposing a
  raw execution token or accepting request-supplied plans and paths.
- RO-5 — COMPLETE: Automation definitions have bounded create/copy/edit/validation/Preview,
  Draft-versus-Active, object-scoped checked activation, grant/revoke, schedule, occurrence and
  linked-work journeys.
- RO-6 — COMPLETE: Webhook definitions have secret-reference-only create/copy/edit/test and checked
  activation, while delivery list/detail and exact eligible recovery remain concurrency-fenced and
  isolated from media execution.
- RO-7 — COMPLETE: operation-specific missing/readiness, stale/concurrent, malformed, permission,
  unavailable, partial and uncertain states preserve durable truth and offer only safe recovery or
  truthful Slice 34/Slice 35 handoff.
- RO-8 — COMPLETE: central typed entity/query/action boundaries compose existing Python
  Application and `/api/v1/*` authority, preserve V1 `/ui`, and prove RBAC, audit, redaction,
  persistence, bounded requests and mutation invariants.

Required Surfaces:
- Operations route and Dashboard surface — COMPLETE.
- Task, Job and Worker surface — COMPLETE.
- Manual Scan/Preview surface — COMPLETE.
- Manual Organize surface — COMPLETE.
- Automation and schedule surface — COMPLETE.
- Notification surface — COMPLETE.
- State, auth and cross-surface surface — COMPLETE.
- Application/API authority and test surface — COMPLETE for implementation and proof; A-owned
  factual documentation reconciliation is listed below.

Implemented:
- A real V2 Operations landing, Dashboard/Library cross-links, strict dynamic route metadata and
  memory-only-auth continuation across Task, Job, Scan, Preview, Organize, Automation and
  Notification routes.
- Bounded Task/Job/Worker projections, filters, paging, linked durable state and exact cooperative
  pause/resume/cancel behavior with backend-authoritative permissions and optimistic fences.
- Manual Scan and zero-mutation full-pipeline Preview admissions plus a complete Web-native manual
  Organize flow using durable intents, immutable evidence, exact selections and one-shot
  server-retained execution authority.
- Automation definition, Preview, checked activation, unattended grant, schedule, occurrence and
  linked-work surfaces composed over the existing managed configuration authority.
- Webhook definition, exact signed test, checked activation and durable delivery/recovery surfaces
  with strict identity/revision binding, redaction and no uncertain mutation replay.
- Backward-compatible Python application/API projections, persistence fences and deterministic
  unit, integration and built-artifact browser fakes proving the complete journey.

Tasks completed:
- Task 33.1 — Operations command center and durable work control — PASS at
  `461b11e0957da40cdd3461e0d8bccfc486c462c3`.
- Task 33.2 — Bounded manual Scan and zero-mutation Preview — PASS at
  `ee58054c67e60186e3dc8d84ac15f618cc25d8eb`.
- Task 33.3 — Web-native exact manual Organize admission and outcome journey — PASS at
  `11555c648dbd1b032b03d09fdef39f94dbec5257`.
- Task 33.4 — V2 scheduled Automation definition and occurrence journey — PASS at
  `e7f29164dcfe7eb286952af17b2bf30bedcd6e9a`.
- Task 33.5 — V2 Notification definition, test, activation and delivery recovery journey — PASS at
  `8a0048008057beabada1a36c53d5fdc3153e8e7b`.

Final Tests:
- `python3 scripts/check_governance.py` — PASS.
- `env -u NODE_ENV npm --prefix web ci` — PASS; 254 packages installed, 255 audited, 0
  vulnerabilities.
- Frontend format/type/lint — PASS; Vitest/React Testing Library 440/440 in 34 files; production
  Vite build — PASS.
- Task 33.5 focused evidence — PASS: Python Notification integration 25/25, typed/component
  Notification evidence 81/81 and built-artifact Notification/Operations/deep-link evidence 56/56.
- Slice-focused Python Operations/Scan/Preview/Organize/Automation/Notification modules — PASS,
  119/119.
- Full Playwright Chromium built-artifact regression — PASS, 118/118.
- Ruff format/check — PASS; 309 files already formatted; compileall and `pip check` — PASS.
- Both example configuration validations — PASS.
- Root-CWD full unittest discovery — FAIL, 1539 run, 6 failures and 7 skips. The six failures read
  ignored local `.mediaflow` runtime/configuration state instead of fixture defaults; that private
  state was preserved and no private value is reproduced in this packet.
- Full unittest discovery from a clean detached worktree at the exact Implementation Head — PASS,
  1539 tests with 7 environment-gated skips. This proves the root-CWD failures are unrelated local
  runtime-state effects rather than Slice regressions.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS with Docker available: clean
  candidate image, four-service topology, non-root runtime, V1/V2 coexistence, safe headers,
  authentication/RBAC, exact Active snapshot, restart, durable projections and zero-side-effect
  denial.
- `git diff --check` — PASS for Base..Implementation Head and the B closure edits.

Safety Evidence:
- Base..Implementation Head inspection found no deleted tests, hidden skips, assertion weakening,
  tracked private configuration, credentials, binary/build artifacts or unrelated feature scope.
- Backend tests prove bounded request bodies, RBAC, audit, queue/item limits, exact source/snapshot/
  item/version binding, one-shot/expiry/concurrency fences, restart persistence and rejection before
  mutation when evidence is stale.
- Preview/DryRun and all analysis stages remain zero-mutation; only OrganizerExecutor performs
  reviewed Storage effects. Explicit overwrite/delete/source-cleanup authority, link capability
  failure without fallback, RecognitionType C preservation and no uncertain replay remain covered.
- Automation Drafts never become Active or gain unattended authority implicitly; grants remain
  separate and revocable. Webhook tests are explicit and read-only, and exact delivery recovery
  changes no definition, sibling delivery or completed media work.
- Browser request capture and hostile fakes prove exact authenticated methods/bodies, no automatic
  mutation replay, memory-only Bearer handling and exclusion of raw execution authority, secret
  values, private paths and provider payloads from URLs, persistent stores, DOM and artifacts.
- Tests use local fakes, local servers, temporary state and an isolated clean worktree.
  `config/alist.json`, ignored private runtime configuration, production credentials, private
  endpoints and operator media are absent from Base..Implementation Head.

Known Non-blocking Issues:
- P2: pre-existing root-CWD test isolation permits six Python tests to consume ignored local
  runtime/configuration state. The exact Implementation Head passes all 1539 tests in a clean Git
  worktree; Slice 33 neither changes nor conceals that unrelated environment behavior.
- P3: existing sqlite `ResourceWarning` diagnostics, 7 environment-gated unittest skips and
  non-failing jsdom `Window.scrollTo()` diagnostics remain. Vite also reports the existing
  non-blocking large-chunk advisory for the production bundle.

Explicitly Deferred:
- Slice 34 Review & Recovery Workspace: recognition/metadata/classification review, conflicts,
  Reprocess, checkpoint continuation, failed-stage retry and per-item/bounded-batch media recovery.
- Slice 35 Configuration Administration: general managed configuration/settings navigation,
  lifecycle, revision evidence, import/export and activation outside the two object-scoped flows.
- Slice 36 final V1/V2 parity, global Logs/security/configuration-audit migration, comprehensive
  cross-feature accessibility proof, supported `/ui` cutover and V1 UI retirement.
- Automatic replay of uncertain media effects, rollback/undo, history deletion, arbitrary bulk
  execution, generic workflow design and distributed scheduling/Workers.
- New Storage/Metadata/Notification providers, provider switching, new notification channels,
  general Secret Store integration, mutation-based probes and processing-policy semantic changes.
- File upload/download/content preview/edit/rename/delete, streaming/artwork and arbitrary Storage
  or host-filesystem mutation/browsing.
- Built-in identity/session/OIDC/reverse-proxy identity, credential persistence/refresh/rotation and
  redesign of the current API-principal authentication model.
- SSR, React Server Components, Node production serving, micro-frontends, CDN runtime dependencies,
  native clients, global search, localization and complete visual-theme work.

Documentation Reconciliation Needed:
- If A's final review returns PASS, reconcile `README.md`, `docs/v2-requirements.md`,
  `docs/progress.md` and `docs/roadmap.md`; they still identify Slice 32 as the latest closed Slice,
  no active large Slice, or Slice 33 as ACTIVE.
- Reconcile CURRENT Operations facts in `docs/product-experience.md` and `docs/architecture.md` to
  describe the delivered V2 command center and preserve the Slice 34–36 deferrals. A should verify
  whether the canonical Chinese specification needs the same factual program-status update without
  changing stable product requirements.

Decision: SLICE READY FOR A REVIEW
~~~

## Closure Packet — 2026-09-13 Post-closure P1 correction

~~~
Slice: 33 — Operations Workspace
Base SHA: 827c36b410687e41b1da53ba6475d8c03a47dbfd
Head SHA: 437135dbe36e63d733eb994cda8edb23fcf671bc

Required Outcomes:
- RO-1 — COMPLETE.
- RO-2 — COMPLETE.
- RO-3 — COMPLETE.
- RO-4 — COMPLETE: the typed V2 Manual Organize Preview now preserves and renders
  RecognitionType, operation and destructive implications, validates exact executable candidates,
  and gates overwrite/source-cleanup intent on the exact current selection.
- RO-5 — COMPLETE.
- RO-6 — COMPLETE.
- RO-7 — COMPLETE.
- RO-8 — COMPLETE.

Required Surfaces:
- Operations route and Dashboard surface — COMPLETE.
- Task, Job and Worker surface — COMPLETE.
- Manual Scan/Preview surface — COMPLETE.
- Manual Organize surface — COMPLETE, including the corrected exact Preview safety projection and
  separate destructive confirmations.
- Automation and schedule surface — COMPLETE.
- Notification surface — COMPLETE.
- State, auth and cross-surface surface — COMPLETE.
- Application/API authority and test surface — COMPLETE for implementation and proof.

Implemented:
- Restored the bounded frontend Preview model for operation and structured destructive implications
  beside RecognitionType, with strict closed-vocabulary/boolean/text normalization.
- Made malformed, missing, duplicated or contradictory execution-candidate safety evidence fail
  closed before the Web surface can offer Execute, while preserving legitimate blocked/no-plan
  evidence as visible non-executable state.
- Removed the production raw-plan type escape, rendered exact plan facts from the typed model,
  bound destructive confirmations to the exact selected item set, and submitted both effect
  booleans explicitly.
- Corrected component and built-artifact fixtures to bind durable selections to their exact
  execution candidates.

Tasks completed:
- Task 33.1 — Operations command center and durable work control — PASS.
- Task 33.2 — Bounded manual Scan and zero-mutation Preview — PASS.
- Task 33.3 — Web-native exact manual Organize admission and outcome journey — PASS.
- Task 33.4 — V2 scheduled Automation definition and occurrence journey — PASS.
- Task 33.5 — V2 Notification definition, test, activation and delivery recovery journey — PASS.
- Task 33.6 — Restore the typed Manual Organize Preview safety projection — PASS at
  `437135dbe36e63d733eb994cda8edb23fcf671bc`.

Final Tests:
- `python3 scripts/check_governance.py` — PASS before closure edits.
- `env -u NODE_ENV npm --prefix web ci` — PASS; 254 packages installed, 255 audited, 0
  vulnerabilities.
- Frontend format check, TypeScript typecheck and ESLint — PASS.
- Focused frontend regression — PASS, 6 files and 75 tests.
- Full Vitest/React Testing Library regression — PASS, 34 files and 452 tests.
- Production Vite build — PASS; existing non-blocking large-chunk advisory, largest chunk 706.88 kB.
- Full Playwright built-artifact regression — PASS, 119/119.
- Focused Python Operations/Preview/Organize safety suites — PASS, 73/73.
- `.venv/bin/ruff format --check .` and `.venv/bin/ruff check .` — PASS; 309 files formatted and
  all checks passed. System `ruff` was unavailable.
- Python and `.venv` compileall — PASS. `.venv/bin/python -m pip check` — PASS; system `pip` was
  unavailable.
- `.venv/bin/mediaflow` example and phase13.2 configuration validation — PASS; system `mediaflow`
  executable was unavailable.
- FFprobe/FFmpeg dependency scan — PASS.
- Full Python unittest discovery — root interpreter: 1539 run, 6 failures, 1 error, 7 skips;
  `.venv`: 1539 run, 6 failures, 7 skips. The failures are pre-existing ignored private runtime/
  configuration expectations; the root error is the system environment's missing optional OpenList
  `httpx`. No backend/Python production code changed in this correction.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS with Docker available.
- `git diff --check` — PASS for the implementation and review changes.

Safety Evidence:
- The correction diff contains only the typed frontend Preview boundary, Manual Organize page/API
  behavior, related tests and bounded fake-server fixture updates; no backend mutation path,
  OrganizerExecutor, Storage, persisted schema, credential, `config/alist.json` or A-owned
  Contract surface was changed.
- Execution candidates require one exact current selected item with complete typed RecognitionType,
  operation and destructive safety facts; malformed evidence exposes no Execute control.
- RecognitionType C remains C independently from NamingPolicy A and ClassificationPolicy A.
- Preview remains zero-mutation, execution remains server-authoritative and one-shot, overwrite and
  source cleanup remain separately explicit, and no automatic mutation retry or silent fallback was
  introduced.
- Focused Python safety tests, browser request evidence, full E2E and Docker release-security smoke
  preserve RBAC, redaction, exact binding, OrganizerExecutor-only mutation, V1 coexistence and
  memory-only authority handling.

Known Non-blocking Issues:
- P2: existing root-CWD private runtime/configuration state causes six full-unittest failures;
  those failures are reproduced independently of this frontend correction and were not removed.
- P2: the system interpreter lacks optional OpenList `httpx`; the equivalent `.venv` gates and all
  focused safety tests pass.
- P3: existing sqlite ResourceWarnings, jsdom `window.scrollTo()` diagnostics, 7 environment-gated
  Python skips and the Vite large-chunk advisory remain.

Explicitly Deferred:
- Unchanged; maintain the Contract's Explicitly Deferred list above. No deferred capability was
  pulled into this correction.

Documentation Reconciliation Needed:
- A should reconcile README, `docs/v2-requirements.md`, `docs/progress.md`, `docs/roadmap.md`,
  `docs/product-experience.md` and `docs/architecture.md` to record the post-closure correction
  and current Operations Workspace facts, while preserving the Slice 34–36 boundaries. A should
  decide whether the canonical Chinese specification needs the same factual program-status update
  without changing stable product requirements.

Decision: SLICE READY FOR A REVIEW
~~~

## Review State

~~~
Slice Status: PASS / CLOSED
Implementation Head: 437135dbe36e63d733eb994cda8edb23fcf671bc
Historical Closure: PASS / CLOSED at dcc2f34c38975662ddbc78e160bbbc2d423ae702
P0/P1 Defects:
- None after Task 33.6 correction.
Next Action: A SELECTS THE NEXT LARGE SLICE
~~~

## A Final Review — 2026-09-13 Post-closure correction

~~~
Reviewed Range: 827c36b410687e41b1da53ba6475d8c03a47dbfd..437135dbe36e63d733eb994cda8edb23fcf671bc
Decision: PASS
P0/P1 Blockers:
- None.

Closure Reconciliation:
- All RO-1 through RO-8 and all eight Required Surfaces are complete. The post-closure P1
  correction restores the typed Manual Organize Preview projection, truthful RecognitionType/
  operation/destructive evidence, exact candidate validation and separate destructive confirmations.
- The complete daily Operations journey remains Web-native: Dashboard entry, durable Task/Job
  observation, bounded Scan/Preview, exact manual Organize admission/outcomes, Automation operation
  and Notification delivery operation all use shared Python `/api/v1/*` authority.
- The reviewed range preserves zero-mutation analysis, OrganizerExecutor-only Storage mutation,
  backend RBAC/audit/limits/fencing, immutable snapshot and item binding, RecognitionType C
  preservation, explicit overwrite/source-cleanup intent, no silent fallback and no uncertain
  mutation replay.
- Final validation evidence is recorded in the post-closure Closure Packet. The six private
  root-CWD unittest failures, one system-interpreter OpenList dependency error, warnings, skips and
  bundle advisory are non-blocking P2/P3 issues and do not arise from this correction.
- Documentation facts are reconciled in `docs/roadmap.md`, `docs/progress.md`,
  `docs/v2-requirements.md`, `docs/architecture.md` and the canonical product specification.
  `docs/product-experience.md` already described the delivered Operations journey accurately.
- Slice 34 Review & Recovery, Slice 35 Configuration Administration, Slice 36 parity/accessibility/
  cutover and all other Contract deferrals remain deferred; no hidden dependency was introduced.

Reviewed: 2026-09-13
~~~

## Historical A Final Review — 2026-09-13

~~~
Reviewed Range: 827c36b410687e41b1da53ba6475d8c03a47dbfd..8a0048008057beabada1a36c53d5fdc3153e8e7b
Decision: PASS
P0/P1 Blockers:
- None.

Closure Reconciliation:
- All RO-1 through RO-8 and all eight Required Surfaces are complete. The V2 Operations workspace
  now provides actionable Dashboard entry, durable Task/Job state and valid controls, bounded
  Scan/Preview, Web-native exact manual Organize, Automation definition/schedule/grant/occurrence
  operation, Webhook definition/test/activation/delivery recovery, and explicit failure handoffs.
- The delivered Web routes continue through the shared Python `/api/v1/*` application authority.
  Manual execution uses server-held, short-lived, single-use authority bound to the authenticated
  principal, exact Preview/configuration/item set and effects; admission and consumption are
  atomic, execution is claimed by the resident Worker, and only OrganizerExecutor mutates Storage.
- A reviewed the complete Base..Implementation Head range and independently confirmed the closure
  evidence: 1539 Python tests passed with 7 environment-gated skips in a detached worktree at the
  exact Implementation Head; 440 Vitest tests and 118 Playwright tests passed; frontend format,
  typecheck, lint and production build passed. The disclosed root-CWD local-state failures,
  ResourceWarnings, jsdom diagnostics and bundle-size advisory are non-blocking P2/P3 evidence.
- RecognitionType preservation, zero-mutation analysis/Preview, explicit overwrite/source-cleanup
  intent, no link fallback, immutable snapshot binding, fencing, no automatic uncertain-mutation
  replay, redaction and `config/alist.json` exclusion remain intact.
- Review/Recovery, general Configuration administration, final parity/accessibility and V1 UI
  retirement, plus every other item under Explicitly Deferred, remain owned by later Slices and are
  not hidden dependencies of the delivered Operations journey.

Reviewed: 2026-09-13
~~~
