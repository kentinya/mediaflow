# Slice 26 — Web-first Fresh Setup and Storage Completion

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 26
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 3c660d5a1512b5b221b0284bcff9ae6dd00bbf23
Implementation Head: NOT SET
```

The Base is the Slice 25 closure documentation commit and repository HEAD inspected by A when this
Contract was activated. B may plan implementation Tasks only inside this Contract. B records the
real product Implementation Head only when preparing the Slice Closure Packet.

## User Goal

On a fresh self-hosted instance, an authenticated operator can open MediaFlow without first writing a
complete runtime JSON document, see that no runtime configuration is Active, create the first managed
Draft, configure and safely test Local, SMB, OpenList and S3/R2 Storage, choose bounded source and
destination directories, bind ResourceLibrary and MediaLibrary, complete the existing Recognition,
TMDB Metadata, Naming, Classification and Organize configuration journey, Validate/Test, and
explicitly checked-activate the exact immutable runtime snapshot.

This Slice ends when that first Active runtime is usable by the existing scan/Preview/Automation
pipeline. It does not package or deploy Docker itself.

## Vertical Journey

```text
minimal management bootstrap + fresh database
→ authenticated Web reports no Active runtime
→ create first managed Draft from a supported safe starting point
→ configure Storage and deployment-owned secret references
→ read-only connection/root test
→ bounded lazy directory browse and path selection
→ bind ResourceLibrary and MediaLibrary
→ configure existing Recognition/TMDB Metadata/Naming/Classification/Organize policies
→ Validate and run applicable safe tests/previews
→ inspect exact revision, references, warnings and blockers
→ explicitly checked Activate
→ runtime/API/Worker resolve that immutable Active snapshot
```

Failure preserves the Draft and the prior Active snapshot, if any. The affected object, failed stage,
durable evidence, side-effect statement, retry safety and exact recovery action remain visible after
reload.

## Current Foundation

- `ManagementBootstrapConfiguration` already isolates the database locator and environment-owned API
  principal definitions from workflow configuration.
- Whole-document managed Draft/Validated/Active revisions, optimistic versions, immutable digests,
  validation, activation, recovery and pinned runtime resolution are CURRENT.
- Guided Web/API management already covers Local Storage, ResourceLibrary, MediaLibrary,
  RecognitionType/Rule/TypePolicy, MetadataPolicy, NamingPolicy, ClassificationPolicy,
  OrganizePolicy and Automation Task Definition objects.
- Local setup checks, Strategy Test, live TMDB test, naming/classification/destination previews,
  Local destination precheck and checked activation already provide exact-revision evidence.
- Local, SMB, OpenList and S3/R2 adapters, environment-reference secrets, capabilities and read-only
  health/list/stat operations already exist behind the Storage abstraction.
- The existing pipeline, FileIndex, Organizer, Task/TaskItem/Result, manual execution authority and
  unattended execution authority are closed foundations and are not redesigned here.

## Current Gap

- With no managed Active revision, `api serve` falls through to the complete runtime loader; a truly
  minimal bootstrap document therefore cannot currently start the management-only API on a fresh
  database.
- The Web can import or paste a complete JSON document, but cannot construct the first complete
  runtime Draft through a supported guided fresh-instance flow.
- Remote Storage objects are redacted and `json_import_only`; guided normalization explicitly accepts
  Local Storage only.
- There is no live Storage Browser/Path Picker. File Catalog answers what MediaFlow indexed and cannot
  substitute for browsing a configured Storage.
- Local `rootPath` copy still describes a host-absolute path. In a future container it must mean an
  absolute path visible inside the MediaFlow execution environment; an unmapped host path is invalid.
- Remote Storage/library root checks, credential-reference readiness and actionable setup recovery are
  not product-complete, and checked activation evidence is Local-specific.

## Required Outcomes

| ID | Required Outcome | Initial State |
|---|---|---|
| RO-1 | The API can start in an authenticated management-only state from a minimal bootstrap containing only the immutable local database locator and API-principal environment references, even when `/data` is fresh and no Active revision exists; `/health`, management readiness and configuration status distinguish process health, management readiness and missing business runtime without trusting incomplete workflow JSON | NOT STARTED |
| RO-2 | The Web/API can create the first complete managed Draft from a versioned, schema-valid, secret-free setup starting point and then build the required runtime object graph without editing SQLite or hand-authoring a whole runtime JSON file; no generated default becomes Active, starts work or grants execution authority | NOT STARTED |
| RO-3 | Guided managed Storage lifecycle covers Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible definitions, including create/copy/edit/enable/disable/delete, reference protection, provider-specific bounded fields, environment-variable secret references and SET/UNSET-style readiness without ever returning secret values | NOT STARTED |
| RO-4 | Every configured Storage has an explicit read-only connection/root test and declared capability summary with bounded timeout, failure category, completed operations, `sideEffects=none`, retry safety and recovery; tests do not create, write, rename, move, copy, link or delete media and do not convert unavailable real-service acceptance into a fake PASS | NOT STARTED |
| RO-5 | Authenticated Web/API provide a read-only, directory-level, lazy Storage Browser with root confinement, breadcrumb navigation, bounded deterministic listings and cursor/pagination when required; it uses only the configured Storage abstraction, never recursively scans a Storage, never accepts arbitrary host paths, never exposes credentials and remains semantically separate from File Catalog | NOT STARTED |
| RO-6 | ResourceLibrary and MediaLibrary guided setup can select a configured Storage and a Storage-relative directory from the browser or validated text input. Local Storage `rootPath` is explicitly an execution-environment-visible absolute path; product guidance explains future Docker bind mounts, read-only/read-write intent, ownership/permission failures and that unmapped host paths, host `/`, Docker socket and arbitrary host filesystem access are unsupported | NOT STARTED |
| RO-7 | From the first Draft, the operator can complete the existing Recognition, TMDB Metadata, Naming, Classification and Organize setup, run the applicable exact-revision tests/previews, inspect dependency impact and failures, and checked-activate only the exact revision whose required evidence is current; a prior Active remains unchanged on every failure | NOT STARTED |
| RO-8 | API and Web use the same application services, RBAC, validation, optimistic concurrency, evidence, audit and recovery rules. Reads create no Job/Task, contact no Provider unless the operator explicitly starts the existing live Metadata test, and perform no Storage mutation | NOT STARTED |

## Required Surfaces

- **Operator Web**: fresh-state landing/progress, Draft creation, all V1 Storage forms, credential
  readiness, read-only tests, Storage Browser/path selection, library binding, existing policy setup,
  exact evidence, checked activation and actionable recovery.
- **API**: the same management-only startup, typed Storage lifecycle, test/browser endpoints, bounded
  errors and first-Draft/activation behavior used by Web.
- **Application**: one provider-neutral setup/test/browser behavior; no UI-specific Storage calls.
- **Infrastructure**: existing Storage adapters only, with secret resolution at adapter boundaries.
- **Persistence**: existing managed revision/evidence authority and immutable bootstrap database
  locator; no second configuration source of truth.
- **Documentation/tests**: self-hosted path semantics, fake/local-service coverage and explicit
  `SKIP / UNAVAILABLE` reporting for unavailable production services.

CLI may expose equivalent administration or diagnosis, but CLI-only completion does not satisfy any
Web Required Outcome.

## Safety Invariants

1. Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation.
2. Only OrganizerExecutor may mutate media Storage; setup tests and Storage Browser are read-only.
3. No connection or capability test may use a mutation probe in this Slice.
4. Storage Browser is confined to one configured Storage root and never browses the host filesystem
   directly.
5. Local symlink/path escape protections and every adapter's Storage-relative path rules remain
   authoritative.
6. An absent Active runtime is a valid fresh setup state, not authorization to use an incomplete
   Draft or silently fall back after a managed Active has existed.
7. Active means the exact immutable snapshot consumed by runtime. Editing creates a Draft and never
   mutates Active in place.
8. Secrets remain deployment-owned values referenced by environment-variable name. Values never
   enter managed configuration, SQLite evidence, logs, API, Web, exports or tests.
9. Read-only views and reloads create no Job, Task, grant, Provider request or Storage mutation.
10. RecognitionType identity and independent policy ownership remain unchanged, including C using A
    Naming/Classification while remaining C.
11. Overwrite, Delete, cleanup, rollback, operation fallback, manual execution and unattended
    execution authority are not widened.
12. Batch/item failure remains isolated and does not hide or overwrite sibling state.

## Explicitly Deferred

- The current Files/File Catalog rename and redesign, a real Storage-backed Files entry point,
  processing disposition/source-occurrence identity, duplicate-organize admission and explicit
  Reprocess, repository-level manual Scan/Preview/Organize, Preview-finding versus execution-blocker
  separation, conflict/review-to-recovery continuation, processing-Worker readiness and Attention
  navigation convergence belong to planned Slice 27. Slice 26's provider-neutral Storage Browser
  may supply reusable application/UI primitives, but its only accepted journey here is setup and
  bounded path selection.
- Complete day-2 configuration IA beyond the first-setup journey—including the natural
  Active-to-new-Draft edit flow, consistent object lifecycle discoverability and forms-first versus
  Advanced JSON placement—plus System Settings, configuration/result export and Webhook
  management/recovery belong to planned Slice 28. Slice 26 still owns every first-Draft and Storage
  form/action needed by its Required Outcomes.
- Dockerfile, Compose, production WSGI serving, `/data` packaging, container UID/GID, container
  healthchecks, restart and image-upgrade E2E belong to planned Slice 29.
- Metadata Provider switching, additional production Metadata Providers and arbitrary Provider
  plugins are post-V1. V1 keeps the current Provider abstraction and TMDB production integration.
- Built-in username/password storage, cookie sessions, OIDC and reverse-proxy identity are post-V1.
  V1 retains environment-owned API-principal bearer authentication.
- Full Secret Store integration and Docker Secrets-specific ingestion are post-V1; environment
  references plus deployment secret injection are the V1 boundary.
- Mutation-based Storage write/capability probes, whole-Storage recursive browsing, File Catalog
  redesign and arbitrary host path browsing are not part of this Slice.
- Remote destructive acceptance against unavailable SMB/OpenList/AWS/R2 services, distributed
  workers, automatic uncertain-mutation replay, universal compensation, historical rollback,
  media streaming, poster download, NFO generation, media-server refresh and visual redesign are
  not part of this Slice.
- No refactor of Scanner, Parser, Recognition, Metadata core, Naming, Classification, OrganizePlan,
  OrganizerExecutor, Task/TaskItem/Result or existing execution authorities is authorized absent a
  proven in-Slice P0/P1 defect.

## Dependencies

- Slice 25 is `PASS / CLOSED`.
- Base `3c660d5a1512b5b221b0284bcff9ae6dd00bbf23` and its runtime schema 31/configuration
  schema 10 are the starting facts.
- Existing Storage adapters and managed configuration services remain the implementation foundation.
- Slice 27 depends on the first-runtime, provider-neutral Storage Browser and Storage-relative path
  contracts becoming stable here.
- Slice 28 depends on the first-runtime and managed-configuration authority becoming stable here;
  it does not expand this Slice's first-setup outcome.
- Slice 29 depends on the complete setup, manual-operations/file-lifecycle and day-2 administration
  journeys; this Slice must not implement their packaging.

## Acceptance Criteria

1. A fresh temporary local database plus a minimal bootstrap starts the authenticated API/Web in
   management-ready, runtime-not-configured state without requiring Storage/provider/policy content.
2. Through Web, an operator creates a first complete Draft, configures at least one Local source and
   destination, selects their Storage-relative paths, completes the existing policy graph, validates,
   tests/previews and checked-activates it.
3. The same first-Draft journey has automated provider-neutral coverage for SMB, OpenList, AWS S3,
   Cloudflare R2 and generic S3-compatible forms, secret references, validation and read-only test
   outcomes using fakes/local test services.
4. Storage Browser tests cover bounded listing, breadcrumb/root behavior, empty directories,
   pagination/cursor boundaries, permission/auth/timeout/not-found failures, hostile names, symlinks
   where applicable and path-escape rejection without recursive scan or mutation.
5. An unmapped/nonexistent Local execution-environment path produces actionable permission/path
   recovery; documentation and UI never claim access to arbitrary host paths.
6. A failed test, stale evidence, changed Draft, missing secret reference, broken dependency or
   concurrent edit cannot checked-activate and preserves the Draft plus any prior Active.
7. Activation starts no scan, Job, Task, Automation occurrence or media mutation. A separately
   requested existing DryRun Preview uses the exact new Active snapshot.
8. API and Web acceptance prove matching permissions, validation, evidence, redaction and audit.
9. No secret value appears in managed documents, SQLite evidence, API/Web payloads, logs, fixtures,
   Git diff or test output.
10. RecognitionType C regression, OrganizerExecutor-only mutation and all closed-Slice safety gates
    remain green.
11. Real external-service checks unavailable to the validation environment remain explicitly
    `SKIP / UNAVAILABLE`; test doubles prove software behavior only.

## Final Validation Expectations

- Full offline Python regression suite, Ruff format/lint, compileall, pip check and both canonical
  configuration validations.
- Focused fresh-bootstrap, managed-configuration, Storage-form, read-only test, Storage Browser,
  path confinement, RBAC, redaction, exact activation and immutable snapshot regressions.
- Temporary Local filesystem tests plus fake/local SMB/OpenList/S3-compatible services; no production
  credentials or user media.
- Schema/migration regression proving fresh and current databases preserve all existing state.
- Wheel build and isolated installed-wheel smoke.
- Forbidden FFprobe/FFmpeg scan, private-config/secret scan, Markdown link check, `git diff --check`
  and clean-worktree/archive verification required by the workflow.
- Production SMB/OpenList/AWS S3/Cloudflare R2 and destructive Storage acceptance remain
  `SKIP / UNAVAILABLE` unless an explicitly isolated environment exists.

## Independent Business Capability

This Slice is independently acceptable because it ends with a complete operator outcome: a fresh
instance can become a tested, immutable Active MediaFlow runtime through Web, including every V1
Storage kind and safe path selection. It is not a database/API/frontend decomposition.

It does not implement later Slices early. Day-2 settings/export/notification administration has a
different user goal and recovery lifecycle. Manual operations/file lifecycle must later reuse this
Slice's Storage Browser without changing its setup acceptance, while Docker production release must
integrate already stable setup, daily-operation and administration semantics rather than defining
them during packaging.

## Review State

```text
Slice Status: ACTIVE
Implementation Head: NOT SET
P0/P1 Defects: NOT YET REVIEWED
Decision: B MUST PLAN THE FIRST IMPLEMENTATION TASK
```
