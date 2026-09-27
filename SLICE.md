# Slice 40 — V2 Settings and Empty-Baseline Startup

This A-owned Contract delivers one installation journey: start management services without media
business configuration, explicitly activate a valid empty baseline in V2 Settings, then configure
individual capabilities and use them without restarting resident services.

```text
Slice ID: 40
Name: V2 Settings and Empty-Baseline Startup
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: d814b7c1c6819e79271245a1126f53aca6aeaf69
Implementation Head: NOT SET
Contract Revision: 2026-09-27 — A selection after Slice 39 closure
Risk: High
Final Test Level: T4
Next Action: B PLANS THE FIRST IMPLEMENTATION TASK
```

## Authority and sequencing

The user's direction replaces the earlier proposal where business pages saved Drafts before Active
existed. Settings owns explicit first-Draft creation and empty-baseline activation; business pages
retain their Active-successor publication behavior.

The request's statement that Slice 39 awaited A review is superseded by committed repository facts:
Slice 39 is PASS / CLOSED after A's 2026-09-27 review of
`d02539e49d5c99c3e3c0c70de5e994e42824a18e..f458646d3dac280b118a511c60ec53a5d3075d67`.
Its Contract, Closure Packet and A Final Review remain reachable at this Slice's Base. That
acceptance is not reopened or rewritten.

A checkpoints this Contract and Roadmap before B plans. No implementation Task is created here;
`TASK.md` remains a no-active-Task notice. B owns coherent Task sizing and Test Levels; changes to
Active authority, permissions or service lifecycle require T4. B/Developer may update Implementation
Head and factual progress/Closure Packet fields, but not Base, outcomes, acceptance or deferrals.
Follow `docs/development-workflow.md`.

## User Goal

An administrator deploys only the application bootstrap file, durable data location and
environment-owned API credentials. In V2 Settings they explicitly create, inspect, export and
activate the first Draft with no media business objects. They then configure Storage, libraries,
policies, Automation and Notifications through appropriate supported surfaces. The application
explains which capabilities are available and which still need configuration. Worker, Scheduler
and Notification Worker remain running and adopt eligible configuration without restart.

## Baseline and applicable requirements

At Base, management-only bootstrap, first-Draft persistence, immutable revisions, checked activation,
System Settings and redacted package exchange exist. `/ui-v2/configuration` is a migration landing.
Slice 39 already provides resident ResourceLibrary/MediaLibrary transfer consumption and Worker
command readiness. Remaining gaps verified by A:

- `build_first_setup_starter_document` in `mediaflow/application/configuration_snapshot.py` creates
  empty business collections, but runtime loading rejects them. A read-only probe of the actual
  starter fails with `strategy configuration 'recognitionTypes' must not be empty`.
- `mediaflow/infrastructure/strategy_user_configuration.py` requires nonempty core lists, and
  `runtime_configuration.py` constructs the complete strategy. Absence must become explicit
  capability state without loading development/example defaults.
- `ConfigurationObjectService.activate_checked` and successor evidence generation in
  `configuration_objects.py` assume the existing complete workflow; checks need shared applicability.
- `mediaflow/final_cli.py` bootstraps Worker from management authority, but Scheduler/Notification
  Worker enter through workflow configuration; Notification targets are constructed at startup.
- `compose.yaml` requires source and target media bind mounts even for a fresh installation.

Applicable requirements: `V2-SETUP-001/002`, `V2-CONFIG-001` through `V2-CONFIG-004`,
`V2-RUNTIME-001/002`, `V2-DEPLOY-002`, `V2-UX-*`, `V2-AUTH-*`, `V2-MIG-*`, existing `UX-*`,
`REQ-CONFIG-*`, `REQ-TASK-009/010`, `REQ-SCHED-*`, `REQ-NOTIFY-*`, `REQ-DEPLOY-*` and `REQ-SAFE-*`.
Accompanying V2 TARGET updates describe intended work, not delivered CURRENT behavior. Frozen V1
requirements and historical acceptances remain unchanged.

## Operator journey and Required Surfaces

| Stage | Required experience |
|---|---|
| Entry | Authenticate through existing memory-only API-principal authority; open `系统设置` at `/ui-v2/configuration`. No-Active business states offer Settings and a safe return. |
| Visible state | Distinguish never initialized, existing first Draft, valid empty Active, partially configured Active, command-ready capabilities and unavailable/corrupt authority. Show Active and Draft separately with bounded reasons and next actions. |
| Action | Explicitly create/resume the first Draft, view/export JSON, edit supported uncovered settings and explicitly activate; then continue to business configuration pages. |
| Success | Exact immutable configuration is published and loaded. Empty activation says `配置已激活，媒体业务尚未配置` and creates no media work. Later page saves publish exact successors and refresh capability state. |
| Failure | Invalid object/reference, denied authority, stale revision, failed applicable check, missing secret/mount, persistence/schema fault or unknown outcome identifies durable state without secrets/raw exceptions. |
| Recovery | Preserve Draft/correctable input and previous Active on known publication failure. Correct named blockers, refresh, resume saved state or verify unknown results before another explicit attempt. Previously activated but broken Active is recovery, not first setup. |

Required surfaces: native V2 Settings and shared navigation/auth/deep links; matching authenticated
configuration/readiness APIs; existing business-page empty/readiness/save states; actual resident
CLI/container processes and health projections. Reuse the light V2 shell with accessible desktop and
narrow layouts; no new screenshot reference or unrelated page redesign. Settings must complete in
V2 without mandatory V1/CLI JSON authoring. Other not-yet-migrated business pages retain honest
supported handoffs; this does not require all policy workspaces to migrate.

## Required Outcomes

### RO-1 — Explicit, resumable V2 Settings lifecycle

- Settings owns `创建首个 Draft`, resume, state, JSON view/export and explicit activation. Entry,
  refresh, reconnect and return never create a Draft, run checks or activate.
- Repeated/concurrent creation recovers the existing durable first Draft or an actionable conflict;
  no duplicate setup roots. Reload resumes saved state; unsaved edits are not claimed durable.
- Admin can directly activate an empty Draft through normal validation and atomic runtime binding.
  No Storage/library/RecognitionType/policy forms or generated business defaults are mandatory.
- After activation show exact Active and per-capability status. Safe return refetches authority;
  Viewer receives permitted read-only state and administrator guidance. Backend enforces permissions.

### RO-2 — Legal empty configuration and conditional validation

Storage, ResourceLibrary, MediaLibrary, RecognitionType, rules/type bindings, Metadata/Naming/
Classification/Organize policies, Automation definitions/schedules and Webhooks may all contain zero
business objects in the supported schema. This is valid configuration, not an incomplete document.
No development strategy, synthetic type/provider/destination or business default fills the gaps.
Existing bounded operational/polling defaults remain infrastructure settings, not business objects.

Every populated object still passes its schema, values, uniqueness, paths and declared-reference
validation. Wrong collection types, malformed objects, dangling references and invalid enabled
relations remain errors. Objects can be added in dependency order: an undeclared capability is
unconfigured; a declared broken dependency is invalid. Storage and browseable libraries must not
need invented media-processing policies.

| Check | Applicability |
|---|---|
| Schema/object/reference validation | Always, including the supported empty envelope and every populated object. |
| Runtime construction | Always before publication; absent capabilities load explicitly and dependent commands return bounded `未配置/未就绪` results. |
| Read-only Storage evidence | Applicable enabled library/Storage bindings and explicit Storage diagnostics under existing page-save rules; no imaginary check for empty collections. |
| Offline Recognition Strategy Test | An enabled applicable source and declared recognition processing configuration make the check applicable; absence reports unconfigured. Broken declared relations cannot be relabelled inapplicable. |
| Destination precheck | An enabled applicable destination and declared naming/classification/organize chain; a browse-only MediaLibrary does not need invented Recognition or policy objects. |
| Automation/Webhook validation and authority | Configured enabled operations and actual dependencies; empty families need no fabricated test/Preview/grant. Publication never grants execution by implication. |

One backend applicability decision serves explicit activation and all successor paths. `Not
applicable` is distinct from passed, missing, stale and failed. Required evidence remains bound to
exact revision/version/digest and invalidates on edit. B documents and tests populated/empty
combinations for the relevant Task; it may not restore an unconditional complete-media-graph gate.

### RO-3 — Truthful JSON and bounded advanced editing

- JSON view defaults to actual runtime-consumed Active. With no prior Active, display the existing
  Draft as Draft or no-Draft state. Broken Active is an explicit failure; do not silently substitute
  Draft, bootstrap JSON or cached Active. Explicit Draft selection remains visibly labelled.
- View/export covers all supported managed configuration, including families edited elsewhere.
  Versioned portable export preserves permitted environment references, excludes secret values and
  credentials embedded in unsafe URLs, and never resolves secrets into the document.
- Database location, API principals/roles and actual API tokens remain deployment startup authority.
  Managed editing/activation cannot repoint them. Portable JSON excludes deployment authority;
  import/recovery binds to the receiving deployment and cannot import identity/database authority.
  Optional read-only deployment status is separate and secret-free.
- Advanced editing is schema/field-allowlisted and only covers backend-supported configuration not
  covered by other management pages. No unrestricted JSON write bypass or duplicate mandatory media
  forms. B inventories supported fields and actual runtime consumers, including applicable existing
  locale/timezone, logging, retry and concurrency controls; unknown/unconsumed fields are not
  advertised as effective. No new setting family/consumer is invented solely for this editor.
- Edits use the same RBAC, validation, audit, optimistic concurrency and activation boundary. Draft
  edits never change Active in place. Deployment/restart-only settings retain truthful labels and
  cannot appear hot-applied when their consumer still uses an earlier value.

### RO-4 — Incremental business configuration and command readiness

- Storage and both library pages publish valid objects from empty Active while unrelated families
  remain empty. Preserve page-local `保存并激活 successor`, exact Active base, field-preserving merge,
  applicable checks and atomic publication. Successful Save must not become Draft-only persistence.
- Policy, Automation and Notification surfaces share the same authority/applicability; retain their
  existing explicit test, activation and execution/grant decisions. Full native policy migration is
  outside scope.
- Backend readiness is specific to command/scope: management, Storage access, library browse/direct
  transfer, scan, Recognition/Preview/Organize, scheduling and delivery have different dependencies.
  Missing Metadata does not disable an otherwise permitted direct transfer; Storage alone does not
  make Organize ready. API/Web name missing/disabled/unavailable/unauthorized prerequisites and the
  recovery destination. Admission and execution revalidate; UI readiness is not a permission grant.
- Stale/concurrent publication, validation/evidence and runtime/persistence failures preserve prior
  Active and correctable input. Unknown outcomes require state verification, never automatic replay.

### RO-5 — Resident MediaFlow Worker across setup and activation

Worker starts, registers and heartbeats without Active and with empty Active. FileTransfer consumers
remain installed, preserving Slice 39 command/library-kind identity and pinned reconstruction.
Without valid authorized published work context, no media processing or Storage mutation occurs.
Later eligible admitted Scan/Preview/Organize and ResourceLibrary/MediaLibrary transfers are consumed
without Worker restart for its supported command families.

Current Active governs new admission; admitted/in-flight work keeps its published revision/digest.
Missing current Active alone does not invalidate an intact older admitted pin. Missing/corrupt/
unpublished/mismatched pins, incompatible schema, revoked authority or unavailable required secrets
block affected work before new mutation. No replacement with current Active, Draft, startup JSON or
cache. Preserve leases, heartbeat, fences, independent item checkpoints and uncertainty recovery
through configuration switches, slow calls and restart.

### RO-6 — Resident Scheduler and Notification Worker

| Service | No Active / empty business Active | Applicable configuration published |
|---|---|---|
| Scheduler | Starts and waits; without enabled eligible definitions emits no Job. Unavailable Active cannot reuse stale schedules or advance an unissued occurrence. | Resolves one current valid snapshot at each new admission without restart; emits idempotent pinned work through existing scope/permission rules. Configuration read failure keeps the process alive with a bounded waiting reason. |
| Notification Worker | Starts and waits; without usable Webhooks sends nothing and does not claim deliveries lacking a valid target. | Reads current valid delivery configuration without restart while preserving durable target identity, leases, retry/dead-letter and uncertainty semantics. Missing/changed target, secret or configuration never silently retargets a delivery or reports success. |

Safe polling/reconnection may resume when prerequisites return; it cannot replay uncertain media
mutation or conceal uncertain delivery. Keep documented notification at-least-once semantics and
independent recovery. Activation itself creates no delivery, sends no notification and grants no
execution authority.

### RO-7 — Deployment, health and recoverable faults

- Default supported Compose starts API and all three resident services with management bootstrap,
  admin credentials and durable local data only. No media bind mount is mandatory. Actual Local
  Storage still needs explicit confined mounts/permissions. Adding a mount is a deployment change
  and may recreate containers; configuration-only activation must not require process restart.
- Separate process liveness; DB/schema and actual service registration/heartbeat readiness; and
  command/scope work readiness with current/pinned-context reasons. Compose checks documented
  infrastructure readiness, not media completeness. Waiting for initial configuration is normal;
  Scheduler/notification work must still be shown as unconfigured, not ready.
- Active absence/corruption, pin mismatch, DB outage, incompatible schema and missing secrets have
  distinct bounded reasons and recovery. Running services safely wait through recoverable faults;
  no cache fallback or unauthorized work. Unsupported schema is not ready and cannot silently
  migrate; retain explicit upgrade/recovery. Invalid deployment inputs remain real startup errors.
- Status/health is read-only and bounded: no Storage traversal, Provider calls, Webhook sends,
  configuration writes or work admission. API never supervises resident subprocesses.

## Safety Invariants

1. One Python authority; Active is the exact validated immutable runtime snapshot, not row existence,
   Draft or stale cache. All entry points share validation, applicability, concurrency and audit.
2. Bootstrap database/principal authority is immutable through managed edits/imports. Bearer remains
   memory-only; no secrets in JSON, URLs, logs, errors, audit or export.
3. Reads, first-Draft creation and activation start no scan, media Job/Task, live Metadata request,
   notification or Storage mutation. Applicable explicit diagnostics preserve zero-mutation scope.
4. OrganizerExecutor alone mutates Storage under explicit intent, confinement, capability and
   destructive policy permission. No silent overwrite/delete/fallback or automatic uncertain replay.
5. RecognitionType C remains C while reusing A's Naming/Classification. No synthetic business
   defaults, FFmpeg/FFprobe or new processing engine.
6. Published task pins, current revocable permissions, leases/fences and per-item durable recovery
   remain authoritative. Completed effects are terminal; uncertainty is never rewritten as success.

## Explicitly Deferred

- Full migration/redesign of policy, Recognition, Review/Recovery or other non-Settings workspaces;
  new business objects/settings, Providers, Storage adapters or processing commands.
- V1 UI deletion or `/ui` cutover before independent parity/accessibility/migration acceptance.
- Mandatory media-business onboarding wizard, generated business defaults, or first-setup Draft
  management on business pages before empty-baseline activation.
- New identity/session/OIDC, full Secret Store, live deployment-secret rotation, database relocation
  or automatic host mount provisioning.
- Scheduler/queue platform redesign, distributed workers, new schedule types/notification channels,
  mutation-based Storage probes, universal rollback and automatic uncertain-mutation replay.

## Slice Acceptance Criteria

| ID | Observable acceptance |
|---|---|
| AC-1 | Fresh Compose with no media mounts/business objects serves Settings and keeps all services running; infrastructure health and unavailable work readiness are distinct. |
| AC-2 | Admin explicitly creates one first Draft, reloads/reconnects/resumes, views labelled Draft JSON and exports. Repeated/concurrent creation produces no duplicate; read/navigation has no write side effect. |
| AC-3 | All-empty business Draft validates and activates without business forms/defaults; runtime reload/API agree on exact Active and show `配置已激活，媒体业务尚未配置`. No media work/notification starts. |
| AC-4 | Valid Storage-only, source-library-only, destination-library-only and policy additions succeed in dependency order with unrelated empty families. Malformed objects/dangling references fail; applicable exact checks cannot be bypassed or replaced with stale evidence. |
| AC-5 | Readiness distinguishes browse/transfer/scan from Recognition/Preview/Organize, scheduling and notifications. Missing capability gives bounded recovery, not exit, accidental work or defaults. |
| AC-6 | Business-page Save publishes exact successor and preserves hidden/unrelated configuration. Stale/concurrent writers, evidence/validation/runtime failure never publish wrong Active; unknown outcomes are verified without replay. |
| AC-7 | Active/Draft JSON identity is truthful; empty and populated exports preserve all portable supported fields and exclude deployment authority/secrets. Round-trip through supported validated import/recovery uses another deployment's own database/principal authority. |
| AC-8 | Advanced edits cover inventoried supported fields absent elsewhere and use the common lifecycle; API rejects unknown/unconsumed fields, deployment database/principal/token changes and unsafe values. Effective settings match consumers. |
| AC-9 | Start processes without Active, activate empty baseline, then usable capabilities without restart. Prove transfer and supported media work, eligible scheduled occurrence and controlled Webhook delivery with unchanged resident process identities. |
| AC-10 | A→B activation pins new work to B and keeps admitted/in-flight A work on A. Missing/corrupt current Active blocks new admission/scheduling but not an intact admitted transfer pin. Bad pin/secret/permission prevents affected new mutation through slow calls and restart. |
| AC-11 | Inject missing/corrupt/mismatched Active/pins, DB/schema failures and missing secrets; distinct reasons, durable state and safe repair recovery remain. No stale-cache fallback, targetless claim, silent retargeting or uncertain replay. |
| AC-12 | Admin/Viewer, 401/403, deep links/reload/return, narrow-width keyboard flow, JSON/audit/error redaction, V1 coexistence and existing business regressions pass on real application surfaces. |

## Final Validation Expectations

Core runtime validity and configuration/service authority make this High / T4. This planning
checkpoint only receives textual/governance checks; no implementation acceptance is claimed.

- Focused model/runtime, configuration/activation/applicability, settings/package, permission,
  successor/admission and resident lifecycle tests: success, invalid input, conflicts, failures,
  empty/populated/dependency edges and RecognitionType C regression.
- Full Python regression and complete quality/safety gates; full Web unit/component suite,
  typecheck/lint/format/build; real SQLite and confined Local integration. Use local controlled
  Provider/Webhook services and fake credentials, never production media or secrets.
- V2 browser first-Draft→empty Active→module-successor journey, JSON/export/advanced edits,
  permissions, concurrency/unknown outcomes and recovery, including a real Python-served path.
  Mocked HTTP alone cannot prove runtime binding or process adoption.
- Actual Compose no-Active/no-media-mount startup and unchanged process identities through empty
  and populated activation; subsequent scheduled work and controlled notification delivery;
  existing transfer lifecycle/slow-call/fencing/non-replay regression.
- Material Docker health, restart/fault and release-security gates; packaging/build and migration/
  upgrade gates if persistence/schema changes. Record commands, totals, skips and unavailable gates;
  fakes do not prove production-provider compatibility.
- Manifest/private-file audit, governance, local Markdown links and `git diff --check`. Preserve
  pre-existing untracked `docs/pics/*.png` and ignored private configuration.

## Closure Packet

Not submitted. Implementation has not started. After each Task PASS B reevaluates all Required
Outcomes; once complete, B runs the Slice-final gate and returns one compact Closure Packet to A.

## A Final Review

Not performed. A reviews the entire immutable Base..Implementation Head against this Contract and
alone reconciles delivered CURRENT facts and declares PASS / CLOSED.
