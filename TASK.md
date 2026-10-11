# Task 44.9 — Simplify bounded folder discovery and complete the Organize journey

This Task follows [the development workflow](docs/development-workflow.md) and
[Task/TEMPLATE.md](Task/TEMPLATE.md), and implements the checkpointed amended [Slice 44](SLICE.md).

```text
Task ID: 44.9
Parent Slice: 44
Status: PLANNED
Task Base: ab94ce53189b5a9f16e7614cd011480a42d91e79
Difficulty: High
Test Level: T4
Planner: A substituting for B under explicit user authorization on 2026-10-11
Reviewer: B — independent Task Reviewer
Contract Checkpoint: ab94ce53189b5a9f16e7614cd011480a42d91e79
```

## Goal

Complete the single RO-6 user journey from folder/file/mixed selection to a truthful bounded
source manifest, safe native continuation and separately confirmed exact Organize. Resolve all
current A44-6 through A44-13 P1s using the approved simpler discovery architecture, while keeping
prior manifest/confinement/control/fencing/atomic-Finalize fixes and the existing execution pipeline.
This Task covers Slice acceptance 27–32; it neither closes Slice 44 nor replaces RO-1 through RO-5.

## Why This Task Exists

The actual executable candidate remains `12fd1b3a75cf76743912b57d1f51d184acb10901`; submitted
Implementation Head is `7e2ab801eaef25b083640813375a49f536ae202f`. A's complete
[audit](docs/reviews/slice-44-folder-organize-audit.md) confirms eight P1 groups despite normal
regressions passing. Review/document successors through this Task Base changed no executable input.

The user explicitly authorized A to incorporate the simpler design and substitute for B planning.
A first checkpointed the architectural amendment as this Task Base. This is a disclosed one-time
planning exception under workflow §2, not delegated implementation or self-review. B reviews the
Developer's checkpoint independently; A later reviews the full immutable Slice Base..new Head.

### Planning reassessment and correction-loop boundary

At planning entry TASK.md contained NO ACTIVE IMPLEMENTATION TASK; Task 44.8 PASS was historical
and recoverable at `78826105093f594ed650405da539c80c159db1d1:TASK.md`; its Contract/Developer reports
remain at `7e2ab801eaef25b083640813375a49f536ae202f:TASK.md` and accepted B snapshot/evidence at
`.git/validation-evidence/7e2ab801eaef25b083640813375a49f536ae202f/b-review44-8-final/`.
It is not an unfinished Task that Developer can continue after the architecture amendment.
Decision: plan this one coherent 44.9 correction across Domain → Persistence →
Application/Worker → API → Web → Tests.

The repeated corrections across 44.6–44.8 already require architectural reassessment; assigning
44.9 does not reset that history. The primary issue is concentrated discovery responsibilities and
inconsistent contracts between layers. Reuse existing SQLite/Worker, pure filters, attachment
association and manual intent/Preview/Executor rather than add per-defect fallbacks or a framework.
The large-Slice sizing heuristic is not a quota: this is a user-authorized consolidation of the
same current capability's confirmed gaps, not eight new Tasks or an enlarged Slice. If an actual
Contract impossibility is found, stop dependent implementation and return it to A with evidence.

The initial read-only governance run fails because the existing guard rejects workflow-required
FIX REQUIRED plus no active correction Task. Preserve that actual FAIL. The workflow correction
transition and explicit user authorization permit planning the legitimate Task; recheck with this
PLANNED Task and the already committed FIX REQUIRED Slice/ACTIVE Roadmap. Do not change Slice
status/Base or implement a tooling workaround. Local planning evidence is retained under
`.git/validation-evidence/78826105093f594ed650405da539c80c159db1d1/a-contract-b-plan44-9/`.

## Implementation Scope

One complete bounded discovery/handoff capability, with the following connected responsibilities:

1. **Admission and request recovery.** Canonicalize safe exact scope sets, including parent/child/
   explicit-file overlap, without changing names. Atomically reconcile open actor/library/Storage/
   pin-bound work across concurrent connections and arbitrary history volume. Persist machine-held
   correlation for the actual request so response-loss readback recovers that admission despite a
   later activation/root change. Distinguish scope equivalence from request correlation; retain
   actor/binding isolation, deliberate terminal successors and no execution permission from reads.
2. **Bounded advancement and ownership.** Use small page/file steps with durable cursors, pending
   work, findings, observations and cumulative budgets. Count directories separately from pages.
   Give API control intent and Worker progress clear write ownership; repository transitions check
   current valid claims, operator concurrency, controls and terminal/frozen state. Storage calls
   happen outside write transactions. Preserve live-owner attempted work after control races and
   already durable refusals; lost owners cannot publish/release/settle over successors. Keep queued/
   in-flight cancellation, acknowledged Pause-before-Continue and atomic one-intent Finalize.
3. **Due-time stability and fair pickup.** Persist due observations and actual source evidence,
   respect required elapsed intervals and resume after restart. Recheck waiting candidates when due,
   without repeated whole-scope traversal for stability, busy polling, Worker sleeps or starvation
   of other discoveries/manual/transfer work. Bound the real work and keep consumed budgets/refusals;
   distinguish first traversal completeness from later source observations. Changed/missing/
   unreadable sources remain explicit; new sources never enlarge frozen or completed work.
   Pending control acknowledgement remains eligible independently of a future stability due time,
   so due-time filtering cannot strand accepted pause/cancel requests.
4. **Production configuration and source semantics.** Provide a bounded native configuration path
   through existing ResourceLibrary/Settings managed Web/API validation and atomic publication for
   the supported include/exclude and stability policy. Share its typed validation and actual
   runtime mapping; do not require a second editor or arbitrary JSON keys. Apply pinned policy and
   root-relative depth/exclusions equally to direct-selected files/folders and descendants. Reuse
   existing main/attachment matching so associated Trailer videos do not become independent primary
   items, including across page/order boundaries; no new generalized Extras engine or Provider call.
5. **Truthful native projection and item isolation.** Align supported exact path/name bounds across
   domain, manual identities, API and Web. Preserve legal 179-character names and 1222-character Local
   paths; bounded unsupported input has an actionable durable refusal, not truncation. Persist
   isolated item/Storage failures without stranding siblings. File and subtree failures both yield
   truthful incomplete findings and an explicit known-subset review. Derive discovery readiness
   from its actual command capability/schema/liveness and expose useful native next actions.
6. **Compatibility and exact handoff.** Preserve existing discovery records, old pins and historical
   file-only intents/Previews/results. Necessary schema/format changes are additive and include
   migration/restart of actual old database fixtures. Do not delete or silently merge old duplicate
   records, guess missing correlation, repin to current Active or invent authority. Ambiguous legacy
   work remains diagnosable with explicit safe native resolution. Freeze one exact bounded primary
   list atomically into the existing intent; use the original recognition path/C identity, Preview,
   permission/capability/conflict/source checks and separately confirmed execution unchanged.

Likely areas: existing media_discovery domain/service/Worker, scan_filters, managed configuration
validation/runtime mapping and native configuration controls, SQLite discovery transactions/migration,
resident Worker scheduling, service API/typed discovery client, ResourceLibrary Files/Operations
readback and directly related tests/proofs. Specific helper names/schema fields are Developer choices;
no file/class/line-count quota is an acceptance gate. Limit any shared-component change to this journey.

Frozen: Slice 43/preservation branch, unrelated RO-1 through RO-5 behavior/visuals, user images,
config/alist.json/private inputs and live deployment/media/services. Slice Contract, Roadmap and
closure ledger stay A-owned; Developer may add necessary factual architecture implementation notes
without declaring Slice closure or changing the target/Contract.

## Acceptance Criteria

| Criterion | Required observable result / defect mapping |
|---|---|
| AC1 — Exact durable admission | A44-6: concurrent same-scope requests, reordered/overlapping scope and a record beyond the recent-list window converge on one open admission under the same actor/library/Storage/pin. Actual Web response loss plus a later activated root recovers the original request/pin. Different binding/pin work and deliberate terminal successors stay distinct; no guessed recent-list association or automatic duplicate submission. |
| AC2 — Real pinned configuration | A44-7: supported native Web/API policy Save validates/publishes and the production loader/Worker consumes that exact immutable revision. Invalid publication preserves previous Active/input. Include/exclude/depth and nonzero stability work at every selection entrance; old admitted work stays on its old root/policy after new activation and restart. Direct-selected excluded/deep scope cannot bypass the root-relative rule. |
| AC3 — Safe scheduled stability | A44-8: genuine nonzero age/mtime/size requirements pass only with required actual observations. Before due time the waiting item is not repeatedly processed or exhausting budgets, other discovery/manual/transfer work advances, and due pickup/restart completes or explains a changed/unreadable source. Small steps retain cursor/work/budgets; no full-directory busy rewalk, fabricated interval or budget reset. |
| AC4 — Names and independent failure | A44-9/A44-10: native detail/list/intent handoff handles exact legal long and whitespace names/paths. A long-name or isolated malformed/failed item never leaves the whole batch indefinitely queued with failure=null. Gone/permission-denied selected files and denied subtrees preserve good siblings, show incomplete scope and actionable errors, and permit only an explicitly reviewed known subset. |
| AC5 — True limits and attachments | A44-11/A44-12: one valid 1001-page OpenList directory is counted as one directory within the existing page/entry/time budgets. 51 main videos plus 51 corresponding enabled Trailer attachments produces 51 primary items; a matched Trailer is not independently handed off as primary. Preserve bounded evidence/order/paging and existing attachment policy/suffix/conflict behavior. Exactly 100 true primaries works; 101 true primaries/material truncation refuses executable prefix. |
| AC6 — Native state and recovery | A44-13: scan-only live Worker is explicitly unsupported for discovery; missing/stale/schema-incompatible Worker and unavailable pin are actionable. Files list/grid and Operations complete folder/file/multiple/mixed journeys, retained return context, pause acknowledgement then Continue, cancellation and recovery without CLI/raw-token steps. API/Web share truthful phase, completeness, actions and readiness. |
| AC7 — Previous safety/compatibility | Earlier A44-1 through A44-5 fixes remain: exact confined deduplicated manifest, monotonic material refusal, stale-owner fencing, durable controls and concurrent atomic one-intent Finalize. Actual old-schema/interrupted work and historical file-only pins/Previews/results survive migration/restart without new scope/authority. Source changes stop the affected item; explicit successor and post-result index-sync do not replay completed/partial/uncertain media effects. Discovery has zero content/Provider/mutation calls; C remains C with A policies; only OrganizerExecutor mutates separately confirmed reviewed items. |
| AC8 — Coherent validated checkpoint | Approved bounded-step/ownership/due-time/shared-authority design is implemented, not only cosmetic function splitting. All eight P1 groups have persistent meaningful regressions and production-path evidence. Assigned T4 gates have actual logs/provenance/results, no weakened/deleted assertions or invented PASS. Preserve private/user/frozen files and submit one coherent correction checkpoint plus truthful report. |

P2 exact-equality budgets, safety-depth explanation, queued/paused copy, optional concurrent-Save
proof and Move wording remain non-blocking unless new evidence establishes a Required Outcome or
safety failure. They may be naturally resolved by an in-scope correction; they do not require a
separate Task or expanded proof matrix.

## Required Tests

### Development and correction feedback

First convert the audit's A44-6 through A44-13 scenarios into portable meaningful regressions,
retaining original receipts and labeling controlled faults. Exercise actual managed publication/
production loading, authenticated API, temporary Local/SQLite and actual Worker pickup. Earlier
injected-policy probes remain useful diagnostic evidence but cannot establish the real configuration
path now promised by AC2/AC3. Verify controls/refusals and all grouped defects together before
expensive final gates; do not repeatedly run full suites while known blockers remain.

Repository root, grouped by behavior:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest
.venv/bin/python -m unittest tests.test_runtime_strategy_configuration tests.test_configuration_objects tests.test_configuration_management tests.test_configuration_snapshot tests.test_configuration_package_exchange tests.test_scanner tests.test_attachments
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_migration_rehearsal
```

The first group covers atomic admission/correlation, actual pickup/checkpoints, due-time fairness,
long names/errors, paging, limits, controls and fencing. The second proves real policy roundtrip/
pin isolation and shared Scanner/attachment semantics. The third preserves the exact native handoff,
execution authority, Operations and genuine historical/restart compatibility. Run added/changed
modules too; use separate SQLite connections, controlled clocks and local OpenList HTTP pages.

From web/:

```bash
npm run test -- --run src/entities/operations/discovery.test.ts src/features/operations/OrganizeDiscoveryPage.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/operations/OperationsInventory.test.tsx
```

Add directly affected native configuration/typed-client tests when those files change. Exercise
unknown-response/new-pin recovery, long-path readback, truthful partial findings, pending/acknowledged
controls and command readiness. Build and run the real-Python native proof before expensive gates:

```bash
npm --prefix web run build
.venv/bin/python scripts/files_organize_discovery_browser_proof.py
```

Extend the existing bounded proof/fixtures as needed for AC1–AC6; do not replace actual Python/API/
Worker/built-Web behavior with mocked return values. Domain race tests can be deterministic without
forcing fragile browser timing. Include one genuine elapsed nonzero stability interval on temporary
media through actual published policy, alongside controlled-clock negative/change/restart checks.

### Final checkpoint gates

T4 is required by concurrency, managed Active configuration, persistence/schema and core source/
execution handoff. Full suites may cover the same focused cases without redundant final reruns;
identify that coverage. The submitted corrected executable candidate needs fresh complete gates.

Repository root:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
.venv/bin/python -m pip wheel . --no-deps -w dist/task44-9
.venv/bin/python scripts/wheel_smoke_test.py dist/task44-9/mediaflow-*.whl
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py
.venv/bin/python scripts/files_organize_discovery_browser_proof.py
.venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py
git diff --check
```

From web/:

```bash
npm run test -- --run
npm run format:check
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Build before real-Python/Docker browser runs. Docker git-archive proofs must use the actual committed
executable candidate, not a stale HEAD; record served assets/image/source hashes. Smoke-test exactly
one current wheel and retain its digest. Audit source/dependencies for forbidden FFmpeg/FFprobe and
staged/tracked files for secrets/private/frozen/unrelated changes. Use isolated Docker projects/
ports/volumes and daemon-visible binds (the known TMPDIR=/run/mf-docker-tmp adaptation where needed).
Do not change live deployments or use production media/services.

Migration proof must use actual pre-change schema-45 databases seeded by the prior implementation,
including queued/paused/waiting/partial/frozen discoveries, observations, legacy duplicate admissions
and historical file-only intents/Previews/results/pins. Verify old history, recovery and exact
execution authority after upgrade/reopen; no silent deletion/merging/repinning. Extend migration/
upgrade tests when formats evolve, preserving old assertions. Seeded newer-looking JSON alone is
insufficient. Preserve RO-1 direct commands/MediaLibrary isolation, RO-3 targets and RO-5 layout.

Actual failed available gates remain FAIL. Real external/endurance profiles keep honest
SKIP/UNAVAILABLE with reasons; fake/local evidence cannot claim production-service acceptance.
Missing material required evidence returns to B, not an invented PASS or a lower test level.

### B independent verification

Inspect the actual Task Base..submitted Head, amended Contract, all eight criteria and original
candidate inputs/logs. Independently exercise a representative production-path case for each group:
atomic concurrent/durable recovery; actual managed filtering plus nonzero stability; due-time pickup
and independent work; legal long-name/path plus isolated error; missing/denied-file partial review;
OpenList page/directory counts; 51 main + 51 Trailer association; scan-only Worker readiness.
Inspect native wrong-pin-response recovery and normal separately confirmed temporary execution
images/API/SQLite receipts, with exact served artifact identity. Recheck critical prior pause/
cancellation/takeover/refusal/atomic-Finalize behavior after the ownership change.

Other complete gates may use verified matching Developer/CI evidence under workflow reuse rules;
missing/incompatible/contradicted inputs require fresh affected runs. This user authorization covers
planning only: A does not perform or declare B PASS on this Task. After B PASS reevaluate all Slice
outcomes, run the current Slice-final gate and submit a new Closure Packet/READY FOR A REVIEW.
Keep A's rejection history and immutable Base; optional proof/P2 cleanup cannot generate another Task.

### Evidence and rerun rules

Retain one indexed candidate/run under
`.git/validation-evidence/<tested-full-sha>/task44-9/<run-id>/` or accessible CI through A's decision.
Record full tested/submitted source identity and any dirty-source manifest, commands/cwd/runtime/
locks/configuration/Worker/selection/clock identity, artifact hashes, actual exit/count/skip/
unavailable/duration, readable logs/images, first failures and repeats. Planning negative receipts
are defect evidence, not product PASS. Preserve original evidence before scripts overwrite outputs.
Changes to source/tests/harness/dependencies/configuration/served artifacts require fresh affected
runs; the T4 final candidate retains complete gates. Report-only successors may reuse runtime evidence
only after explicit input matching and rerunning document-consuming checks. No production or frozen
Slice 43 dependency may substitute for local fixtures.

## Non-goals

- Any new Slice, unbounded organization, automatic splitting beyond 100 primaries or MediaLibrary Organize.
- New queue/Scheduler/supervisor/workflow engine, broad Scanner/FileIndex rewrite, generic Extras matcher,
  new Provider, media hashing/content reads during discovery or a new manual execution pipeline.
- Unrelated configuration/editor redesign, Rules/direct-file/layout changes or optional P2/P3 polish.
- Contract/Base/Deferred changes, historical Task review rewriting, Slice closure, deployment or push.
- Repairing the governance guard merely to mask the no-active-Task transitional mismatch.

## Developer Completion Report

Pending implementation. No product fix, test PASS, changed schema or closed outcome is claimed.

### Changed Files

Pending.

### Implemented

Pending.

### Tests and Results

Pending actual candidate commands, logs/provenance and PASS/FAIL/SKIP/UNAVAILABLE results.

### Decisions

Pending implementation choices within the checkpointed Contract and this Task.

### Remaining In-Slice Work

A44-6 through A44-13 remain unresolved until implementation and independent B review.

### Risks / Deviations

High: admission/concurrency, due-time ownership, managed publication, shared identity and migration.
A's substitution for B planning is explicitly user-authorized; independent review remains B's role.

### Checkpoint

No implementation checkpoint yet. Developer updates the active status/report after assigned gates.

## B Review Result

```text
Reviewed: NOT SET
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: DEVELOPER IMPLEMENTS CURRENT TASK
```

NEXT ACTION: DEVELOPER IMPLEMENTS CURRENT TASK
