# Slice 33 — Operations Workspace

This is the A-owned Slice Contract for the next independently reviewed V2 capability after Slice
32. Slice 32 remains `PASS / CLOSED` in Git, Roadmap and Progress history and is not reopened.

~~~
Slice ID: 33
Name: Operations Workspace
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 827c36b410687e41b1da53ba6475d8c03a47dbfd
Implementation Head:
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
Slice 33 — Operations Workspace — ACTIVE
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

## Closure Packet

Pending implementation and B Slice Final validation.

## Review State

~~~
Slice Status: ACTIVE
Implementation Head: Pending
P0/P1 Defects: Unknown until implementation review
Next Action: B PLANS FIRST TASK
~~~

## A Final Review

Pending B Closure Packet and `READY FOR A REVIEW` status.
