# Phase 22.6-E — Managed Exact-Revision Read-Only Destination Precheck (Local Storage)

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: TASK DEFINED / NOT STARTED
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: c7ec192b3b20f236cca5a70ed59cad43e0851242
  (Phase 22.6-D PASS / CLOSED — 2026-08-28)
Earlier closed checkpoints: 47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa (Phase 22.6-C),
  5e2da5c634f1fa72a40e5f50b035260418fe1a37 (Phase 22.6-B) and
  30af69ac82b30f8a45ad66afbd3c9747597c8fe7 (Phase 22.6-A, includes the 22.6-A-F1 correction)
Preserved rejected checkpoints: 90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: NOT BLOCKING — Slice closure does not require a push, but the closed 22.6-D checkpoint
  and its docs records are not yet in origin/main; the phase-level Phase 22.6 closure requires an
  explicitly authorized push
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: exact-revision read-only destination precheck against a Local destination Storage —
  destination-root and target existence, deepest existing ancestor, the conflict outcome projected
  by the configured ConflictStrategy, and declared-versus-actual Storage capability, all produced by
  the production planner and conflict resolver behind a read-only Storage guard
```

## User Problem

Phase 22.6-D closed the composition question: the operator can now read the exact Storage-relative
path a revision would produce, attributed contribution by contribution
(`mediaflow/application/configuration_objects.py:1036`). It answers *where* a file would go and
deliberately answers nothing about the destination itself — the Non-goals of that Slice forbade any
existence, collision or capability probe.

So the last question before activation is still unanswered, and today it is only answerable by
executing:

- Does the MediaLibrary root even exist on the destination Storage, and is it a directory? The
  guided Local setup check answers this for the *libraries* it selects
  (`mediaflow/application/configuration_objects.py:2591-2680`) but never for a composed destination.
- Does the composed target already exist? Nothing in the managed journey looks. The planner would
  observe it (`mediaflow/application/organizer.py:143-159`) only during a real organize run.
- What would the configured `conflictStrategy` actually do about it? Phase 22.6-C reports the
  configured strategy as a declared value (`configuration_objects.py:911-1034`); it never projects
  the outcome. `Skip` silently doing nothing, `Rename` producing `… (1).mkv`, `Overwrite` waiting
  for a high-risk confirmation and `Manual` blocking are four very different operator futures.
- Can the destination Storage perform the operation the OrganizePolicy demands? Phase 22.6-C reports
  `requiredStorageCapabilities` as *declared* (`configuration_objects.py:956-963`) and states
  explicitly that no probing happens. A `hardLink` policy pointed at a Storage that cannot hard-link
  is therefore configurable, activatable, and fails only at execution — where there is no fallback
  by design.

The operator's real question — "if I activate this revision, will the first organize run land, skip,
rename, block on a confirmation, or fail?" — currently has no safe answer. Answering it by running
an organize task is exactly the unsafe path this project forbids.

## User Journey

```text
Configuration → open a Draft revision → the composed destination preview already shows the exact
   Storage-relative path this revision produces
→ run the read-only destination precheck for the same RecognitionType and sample
→ read, bound to the exact revision: which destination Storage was probed and that it is Local,
   whether the MediaLibrary root exists and is a directory, which ancestor directories already
   exist and which would have to be created, whether the composed target already exists, what the
   configured ConflictStrategy would do about it (including the concrete rename candidate), and
   whether the destination Storage actually declares the capability the OrganizePolicy requires
→ if something is missing, unsupported, or would block, correct that object or path in the same
   Draft → rerun the precheck → Validate and activate
```

Entry point, permission model and revision authority are the existing managed ones: the same
Configuration revision detail view, the same `MANAGE_CONFIGURATION` permission, the same
Draft/Validated editability, the same optimistic `expectedVersion` / `expectedDigest` contract, and
the same current/stale evidence semantics as the naming, classification, organize-authority and
destination-preview explanations.

## User-visible Outcome

- A destination precheck section on the managed revision detail view accepts the same
  RecognitionType and sample shape as the destination preview and returns, bound to the exact
  revision, a read-only report about the real destination.
- The report names the destination Storage ID and type, states that the precheck is Local-only, and
  refuses any non-Local destination Storage with an explicit `unsupported_storage_type` outcome
  rather than a partial answer.
- The report states, in destination order: MediaLibrary root existence and whether it is a
  directory; the deepest already-existing ancestor of the composed target; the bounded list of
  directories that would have to be created; whether the composed target already exists.
- The report projects the configured conflict outcome — `ready`, `skip`, `rename` with the concrete
  proposed relative destination, `overwrite_requires_confirmation`, `manual_confirmation_required`,
  or `invalid` — and states in words that this precheck grants no overwrite, delete or execute
  authority.
- The report compares the capability the OrganizePolicy requires against the capability the
  destination Storage actually declares, names every missing capability, and repeats that there is
  no fallback: an unsupported capability is a failure, never a downgrade to Copy or Move.
- The report lists the bounded read operations it performed and is explicitly labelled
  `sideEffects: "none"` and `retrySafe: true`; the composed path stays Storage-relative and no
  Storage mount prefix, endpoint or credential is displayed.
- Every failure — unsupported Storage type, missing root, permission denied, unavailable Storage,
  capability gap, composition failure inherited from the preview stage, occupied check capacity,
  timeout — is a bounded, secret-free, durable per-revision explanation with the single action that
  continues.
- Precheck evidence is current only for the exact revision ID, version and digest it was produced
  from; after any further edit the stored evidence is presented as stale with the rerun action.
- Nothing is written, created, moved, copied, linked or deleted on the destination Storage, and no
  Task, Job, queue, plan record or execution authority is created.

## Failure and Recovery

| Failure class | Visible state | Durable state / side effects | Retry safe | Recovery | If recovery also fails |
|---|---|---|---|---|---|
| Invalid request (unknown sample field, `path` combined with synthetic fields, out-of-bounds RecognitionType, non-object body) | Bounded `invalid_input` category naming the offending field; API `400 invalid_request` | Draft document, version, digest and previously stored precheck/preview evidence unchanged; nothing probed, nothing written | Yes | Correct the reported field and rerun the precheck | The revision stays Draft and editable; the destination preview still answers the composition half |
| Composition stage fails (unresolvable RecognitionTypePolicy, naming failure, classification failure, unresolved MediaLibrary, unsafe composition) | Failed precheck carrying the *same* bounded category the destination preview would report for that sample | Failure evidence stored for the exact revision; no document change; no Storage adapter constructed | Yes | Fix the named object in the same Draft, rerun the destination preview to confirm the composition, then rerun the precheck | Activation still refuses an unresolvable mapping, and the planner still refuses an unsafe destination |
| Destination MediaLibrary Storage is not Local | Failed precheck stating the Storage ID and that this Slice prechecks Local destinations only | Failure evidence stored; no adapter constructed for the unsupported type | Yes | Point the MediaLibrary at a Local Storage for this check, or wait for remote destination prechecks (explicit TARGET) | The composition preview and organize authority explanation still answer their halves; nothing is silently approved |
| MediaLibrary root missing or not a directory | Failed precheck naming which condition failed, with the Storage-relative root it probed | Failure evidence stored; nothing created — the precheck never creates the root | Yes | Create the root out of band or correct `mediaLibraries[].rootPath` in this Draft, then rerun | Activation is still possible but the operator now knows the first run would fail; the report states this explicitly |
| Destination Storage unavailable, permission denied, timed out, or path rejected | Failed precheck with the mapped bounded category (`unavailable`, `permission_denied`, `timeout`, `invalid_path`) and no raw exception text | Failure evidence stored; partial reads leave nothing behind | Yes | Fix availability, credentials or the path, then rerun the precheck | Nothing has been changed on either Storage; the revision stays exactly as it was |
| Destination Storage lacks a required capability | Completed precheck with a `capability_gap` verdict naming each missing capability and the operation that requires it | Precheck evidence stored; nothing changed | Yes | Change the OrganizePolicy operation, or point the MediaLibrary at a Storage that supports it, then rerun | The report states there is no fallback, so the operator cannot mistake this for a downgrade path |
| Check capacity occupied by an in-flight check | Refusal with `capacity_unavailable` and the wait action | No evidence overwritten, no probe started | Yes | Wait for the in-flight check to finish, then rerun | The revision is untouched; the existing setup-check capacity semantics already behave this way |
| A guarded Storage mutation is attempted by any code on this path | Failed precheck with `read_only_violation` and a "do not activate; inspect the precheck implementation" action | Failure evidence stored; the guard rejected the call before it reached the adapter and counted it | No — this is a defect, not an operator error | Report the defect; do not activate on the strength of this precheck | The guard has already prevented the mutation; the counters prove which operation was attempted |
| Stale precheck (version/digest moved) | Conflict stating the current version and digest with the reload action | Current Draft and prior precheck/preview evidence preserved | Yes | Reload the revision, then rerun the precheck | The Draft is never partially applied; the operator re-reads authoritative state |
| Precheck requested on a non-editable revision | Refusal stating a Draft or Validated revision is required | No evidence written | Yes | Open or create a Draft revision and rerun | Active configuration is untouched and remains the runtime snapshot |

Retry alone is never the recovery text: every row states what is durable, what is safe to repeat,
and the single explicit action that continues.

Batch per-item independence does not apply: this Task prechecks one RecognitionType and one sample
per request. The existing naming, classification, organize-authority, destination-preview and
local-setup-check evidence rows must remain independent of the new one — a failed precheck must not
overwrite, hide or invalidate any of them.

## UX Acceptance Criteria

- [ ] The destination precheck section is reachable: a focused test fails if its mount call leaves
      the `if (guided) {` branch of `showConfigurationRevision`, if the mount moves after the final
      `detailContent.append(actions); detail.hidden = false;`
      (`mediaflow/interfaces/operator_ui.py:1139`), or if the section's heading, RecognitionType
      input, sample input or run control stops being appended to `detailContent` inside the
      rendering function's own body.
- [ ] The proof is brace-matched and body-scoped, using the `_js_function_body(script, name)` and
      `_js_braced_body(script, opening)` helpers already in `tests/test_operator_ui.py:37-60`; a
      defined-but-unmounted section must not pass.
- [ ] The section is read-only on a non-editable revision: the run control is not offered when
      `configurationRevisionEditable(revision)` is false, exactly as the destination preview
      behaves (`mediaflow/interfaces/operator_ui.py:657`).
- [ ] The rendered report shows, in destination order: destination Storage ID and type, MediaLibrary
      ID and Storage-relative rootPath, root existence and directory status, the deepest existing
      ancestor, the directories that would be created, target existence, the configured
      ConflictStrategy with its projected outcome (and the concrete rename candidate when the
      strategy is `rename`), required versus declared versus missing Storage capabilities, and the
      bounded list of read operations performed.
- [ ] The report states in words that the precheck grants no overwrite, delete or execute authority,
      and that an unsupported capability is a failure with no fallback to Copy or Move.
- [ ] A non-Local destination Storage renders an explicit `unsupported_storage_type` failure naming
      the Storage ID, never a partially populated report.
- [ ] Each failure class in the table above is asserted through the public service with a bounded
      distinct category, and the revision version, digest, document and the stored naming,
      classification, organize-authority, destination-preview and local-setup-check evidence rows
      are asserted unchanged.
- [ ] The same rejections are asserted through the authenticated API as `400 invalid_request` with
      bounded, secret-free messages, and a stale revision returns the existing conflict mapping.
- [ ] Precheck evidence is presented as current only for its exact revision ID, version and digest;
      after any further edit the same evidence is presented as stale with the rerun action.
- [ ] No Storage mount prefix, `storages[].rootPath`, absolute filesystem path, endpoint,
      credential, header, cookie, private user path or raw exception text appears in the evidence
      document, the API response, the Web section or the tests.
- [ ] Anything shown as Active is still the exact immutable runtime snapshot; this Task changes no
      activation gate, no Active projection and no runtime schema marker.

## Technical Scope

Reuse the shipped planner, conflict resolver, read-only Storage guard, composition helper, naming
engine, classification engine, policy-resolution stack and setup-check capacity machinery. Do not
fork, re-implement, or "simplify" any of them.

```text
mediaflow/domain/configuration_management.py                → precheck evidence type + status
mediaflow/application/configuration_objects.py              → shared composition helper +
                                                              destination_precheck
mediaflow/infrastructure/sqlite_configuration_management.py → evidence table + marker 9 → 10
mediaflow/interfaces/service_api.py                         → POST .../destination-precheck
mediaflow/interfaces/operator_ui.py                         → guided destination precheck mount
tests/*                                                     → falsifiable Web, service, API,
                                                              read-only and capability proofs
docs/*                                                      → CURRENT/TARGET and Phase gate records
```

- **One composition, shared — not a replayed preview and not a second composition.** The precheck
  needs the same composed destination the preview produces, but it must not read it back from stored
  preview evidence: `_naming_context` deliberately discards the operator-supplied path and persists
  only `{"mode": "path", "filename": ...}`
  (`mediaflow/application/configuration_objects.py:642-699`), so stored evidence cannot reproduce a
  path-mode composition. Therefore the request carries
  `recognitionType` and `sample` itself, and the composition portion of `destination_preview`
  (`mediaflow/application/configuration_objects.py:1036-1240`) — RecognitionType bounds, sample
  union validation and per-engine projection, resolver-driven policy selection, the production
  `NamingPreviewService` / `ClassificationPreviewService` stages, MediaLibrary resolution, and
  `compose_destination` with its unsafe-contribution attribution — is extracted into one private
  helper consumed by both `destination_preview` and `destination_precheck`. A current destination
  preview is a journey companion, never a stored prerequisite.
- **Extraction neutrality proof:** `tests/test_configuration_destination.py` must pass
  **byte-unmodified** after the extraction. No assertion may be edited, relaxed or deleted to
  accommodate
  the move, and the preview's evidence document, keys, categories and stored rows must stay
  byte-identical.
- `destination_precheck(revision_id, *, expected_version, expected_digest, actor, recognition_type,
  sample)` mirrors `destination_preview`: Draft or Validated only, exact version + digest or a
  `ConfigurationVersionConflict` carrying `durable_state` and `next_action`, a bounded
  `recognition_type` (non-empty, ≤64 characters, NUL-free), and one current evidence row per
  revision, independent of every other evidence row.
- **Destination Storage construction — ask exactly what runtime would get.** Resolve the composed
  MediaLibrary's `storageId` in this revision's `storages` section, refuse any `type` other than
  `local` with `unsupported_storage_type` before constructing anything (the precedent is
  `mediaflow/application/configuration_objects.py:2629-2632`), then build the adapter from the
  **unmodified** revision document — do **not** deep-copy and force `storage["readOnly"] = True` the
  way `_run_local_check` does (line 2632-2636). Forcing `readOnly` would make the capability half of
  this Slice meaningless: `LocalStorage.capabilities` computes `writable = not self._read_only`
  (`mediaflow/infrastructure/local_storage.py:27-75`), so a forced adapter reports every capability
  as False and the declared-versus-actual comparison would always report a total gap. Read
  `.capabilities` exactly once as a pure property read from the unwrapped adapter, then immediately
  wrap it in a `ReadOnlyStorageGuard` subclass and hand **only the guard** to every collaborator.
  `ReadOnlyStorageGuard.capabilities` returns an empty `StorageCapabilities()`
  (`mediaflow/application/read_only_storage.py:43-44`), so the guard must never be the capability
  source. A document that legitimately declares `readOnly: true` on the destination Storage must
  therefore surface as a capability gap, not as a crash.
- **The lost `readOnly` flag is compensated by proof, not by trust.** The guard subclass follows the
  `ReadOnlyStrategyStorage` precedent (`mediaflow/application/strategy_test.py:86-91`) and overrides
  `_mutation_error`; after every precheck the service asserts that all seven
  `guard.mutation_calls` counters are zero, exactly as the Strategy Test asserts
  (`mediaflow/application/strategy_test.py:662-663`), and a guarded mutation attempt maps to the
  `read_only_violation` category. Tests additionally take a byte-identity snapshot of the whole
  destination tree before and after the precheck.
- **Existence, ancestors and target come from the production planner, not from ad-hoc probing.**
  Call `OrganizePlanner.plan(...)` (`mediaflow/application/organizer.py:68-199`) with
  `target_storage=<guard>` so `DESTINATION_EXISTS` and `INVALID_DESTINATION` are the planner's own
  verdicts, and with `media_identity=None`, `claimed_destinations=None` and `known_media=None` so
  duplicate-media and cross-item collision detection stay out of scope. The synthetic source is a
  bounded sentinel and is excluded from evidence. The root probe reuses the setup check's two-probe
  shape at `mediaflow/application/configuration_objects.py:3958-3973` — `exists` then
  `stat().is_directory` — mapped to the bounded categories `missing_destination_root` and
  `destination_root_not_directory`. The ancestor walk descends the composed target's parent segments
  from the MediaLibrary root, bounded to at most 64 segments, and reports
  `deepestExistingAncestor` plus a bounded `directoriesToCreate` list; exceeding the bound is an
  `invalid_path` failure, never an unbounded walk.
- **The conflict outcome comes from the production resolver.** Pass the planner's plan and the
  resolved `OrganizePolicy` to `ConflictResolver.apply_configured(plan, policy,
  target_storage=<guard>)` (`mediaflow/application/conflict_resolution.py:36-48`) and project its
  result: no conflicts → `ready`; any `INVALID_DESTINATION` → `invalid`; `ConflictStrategy.SKIP`
  (`mediaflow/domain/organizer.py:138-142`) → `skip`; `RENAME` → `rename` with the resolver's own
  renamed relative destination as `proposedRelativeDestination`; `OVERWRITE` →
  `overwrite_requires_confirmation`; `MANUAL` → `manual_confirmation_required`. Never pass
  `confirmed=True`, never call `ConflictResolver.overwrite`, and never auto-authorize overwrite. The
  resolver's bounded rename probe (1..1000 `exists` candidates, `ConflictResolutionError` beyond
  that) is read-only and is reused as-is.
- **Capability comparison.** Reuse the required-capability derivation Phase 22.6-C already ships
  (`mediaflow/application/configuration_objects.py:956-963`) — `move → can_move`, `copy → can_copy`,
  `hardLink → can_hard_link`, `softLink → can_soft_link`, plus `can_delete` when overwrite or source
  cleanup is configured — and compare it against the capabilities read from the unwrapped adapter.
  Report `requiredStorageCapabilities`, `destinationStorageCapabilities`,
  `missingStorageCapabilities` and a literal `"fallback": "none; an unsupported capability is a
  failure"`. A non-empty missing set yields the overall `capability_gap` verdict while the rest of
  the report is still produced.
- **Verdict and outcome keys.** The evidence document reports `conflictProjection`
  (`configuredStrategy`, `plannerConflicts`, `projectedOutcome`, `proposedRelativeDestination`) and
  a top-level `verdict` that is `capability_gap` when any required capability is missing and the
  projected conflict outcome otherwise, together with `destinationStorageId`,
  `destinationStorageType`, `storageSupport: "local_only"`, `mediaLibraryId`,
  `mediaLibraryRootPath`, `relativeDestination`, `destinationPath`, `destinationRootExists`,
  `destinationRootIsDirectory`, `deepestExistingAncestor`, `directoriesToCreate`, `targetExists`,
  `probeOperations`, `authorityGranted: "none"`, `pathScope: "storage_relative"`,
  `sideEffects: "none"` and `retrySafe: true`.
- **Bounded real I/O reuses the shipped capacity machinery.** Because this path performs real Local
  reads from a request thread, run it through the existing single-slot machinery —
  `_acquire_setup_check` / `_release_setup_check`, the `_setup_check_capacity` bounded semaphore
  with `_SETUP_CHECK_CAPACITY = 1`, `_setup_check_executor`, `_SetupCheckLease` and
  `_setup_check_timeout_seconds` (`mediaflow/application/configuration_objects.py:144, 280-322,
  2481-2560, 4045-4100`) — yielding the `capacity_unavailable` refusal and the `timeout` category.
  Do not add a second concurrency primitive, a second executor, or a rename refactor of the existing
  one.
- Failure handling follows the destination-preview precedent: the composition stage's `except` arm
  covers `PolicyResolutionError` (a `LookupError`, `mediaflow/domain/recognition.py:339`) and
  `ValueError`, deriving the bounded category from the specific type first so a `NamingError` or
  `ClassificationError` never degrades into a generic `invalid_input`. The probe stage adds the
  `StorageError` → category mapping already used by the setup check
  (`mediaflow/application/configuration_objects.py:2698-2707`), `ReadOnlyStorageMutationError` →
  `read_only_violation`, and a generic `unavailable` arm that redacts details. No raw exception text
  is ever persisted or returned.
- Evidence: add `DestinationPrecheckEvidence` and `ConfigurationDestinationPrecheckStatus` alongside
  the existing evidence types (`mediaflow/domain/configuration_management.py:301-380`) with the same
  bounds, digest validation, size limit, bounded text and `sideEffects` / `retrySafe` / `pathScope`
  keys. Persist through a new additive `managed_destination_prechecks` table with a
  `(status, prechecked_at)` index and a foreign key to `managed_configuration_revisions`, and bump
  `CONFIGURATION_SCHEMA_VERSION` from 9 to 10
  (`mediaflow/infrastructure/sqlite_configuration_management.py:40`). The runtime schema marker must
  stay 22. Do not widen or repurpose the `managed_destination_previews` table.
- `revision_detail` gains `"destinationPrecheck": self._destination_precheck_document(revision)`
  beside the existing projections (`mediaflow/application/configuration_objects.py:360-382`), with
  the same current/stale computation as `_destination_preview_document`
  (`mediaflow/application/configuration_objects.py:2828-2840`).
- API: `POST /api/v1/configuration/revisions/{id}/destination-precheck` requiring
  `MANAGE_CONFIGURATION`, accepting exactly `{expectedVersion, expectedDigest, recognitionType,
  sample}`, returning the evidence document, `503` when the service is absent, `400 invalid_request`
  for bounded validation failures and the existing conflict mapping for a stale revision — mirroring
  `mediaflow/interfaces/service_api.py:608-651`.
- Web: add `renderDestinationPrecheck(revision, guided)` and mount it inside the `if (guided) {`
  branch of `showConfigurationRevision` immediately after `renderDestinationPreview(data, guided);`
  (`mediaflow/interfaces/operator_ui.py:1104`) and before
  `detailContent.append(actions); detail.hidden = false;` (line 1139). Follow the destination
  preview section's structure: bounded `field(...)` rows, a stale warning, `aria-label`-ed
  RecognitionType and sample inputs, and the editable-only run control.
- Missing, unsupported and blocking outcomes must be visibly marked, never rendered as an ordinary
  empty value: an absent root, an empty composed path or a missing capability must not be displayed
  as if the destination were ready.

## Non-goals

- No mutation probe of any kind. The precheck never writes, creates, moves, copies, links, deletes,
  touches or "test-writes" anything on either Storage, and it never attempts a capability probe by
  performing the operation. Capability is read from the adapter's declared `StorageCapabilities`
  only.
- No remote destination precheck: SMB, OpenList, S3 / R2 and every other non-Local destination
  Storage is refused with `unsupported_storage_type` and stays explicit TARGET. No remote adapter is
  constructed on this path.
- No duplicate-media detection, no cross-item `claimed_destinations` collision detection, no
  attachment (subtitle / NFO / poster / fanart / trailer) destination precheck, and no source-side
  probe: `media_identity`, `known_media` and `claimed_destinations` stay `None` and the source is a
  bounded synthetic sentinel.
- No Storage mount prefix, `storages[].rootPath`, endpoint, absolute filesystem path, or credential
  in evidence, API, Web or tests. Every reported path stays Storage-relative.
- No overwrite, delete or execute authority. `ConflictResolver.overwrite` is never called,
  `confirmed=True` is never passed, and a `rename` projection is a report, not a reservation.
- No `OrganizePlanner`, `ConflictResolver`, `OrganizerExecutor` or `ReadOnlyStorageGuard` behaviour
  change: they are consumed as shipped. No conflict resolution decision, rollback, cleanup, plan
  record, Task, Job, queue or execute authority is created.
- No change to the destination preview contract, its evidence keys, its document, its categories or
  its table beyond the behaviour-preserving composition-helper extraction, which
  `tests/test_configuration_destination.py` must prove byte-unmodified.
- No change to the naming, classification, organize-authority or local-setup-check contracts, their
  evidence keys, their documents or their tables. In particular, the checked-activation gate is not
  extended to require a destination precheck.
- No combined activation evidence: merging naming, classification, organize-authority, destination
  preview and destination precheck into a single activation-gate record stays deferred.
- No change to Draft/Validate/Activate semantics, the checked activation gate, the Active
  projection, the immutable runtime snapshot, or the runtime SQLite schema marker 22.
- No loader change: the loader's tolerance of `delete` / `create_directory` organize operations, its
  `organizeOperation` inline alias, and its lack of top-level unknown-field rejection for organize
  policies remain recorded observations.
- No new editable configuration object kind, no whole-document import change, and no new
  configuration section.
- No Provider, Metadata, scan, Task, Job, queue or media work; no Provider switching, generic Task
  resume, per-item Processing Checkpoint recovery, or manual organize journey.
- No new frontend framework, unrelated Web refactor, or JS test runner in CI.
- No rewrite of historical Phase evidence, including the preserved Phase 22.5-E and Phase 22.6-A
  `FIX REQUIRED` records and their rejected SHAs.
- Carried-forward P2 items stay out of scope and must not be silently fixed here: whole-document
  policy normalization during preview and the missing FAILED-evidence path in `organize_authority`;
  the organize-policy normalization-neutrality fixture that exercises only default sub-documents;
  the naming engine separator/conversion message wording and legacy template aliases; the
  classification loader's flat-rule and `relativePath` aliases; the path-mode sample field
  tolerance; the unclosed `sqlite3.connect` context managers in the configuration tests; and
  first-object seeding into a document that omits an optional section.

## Safety and Architecture Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner and DryRun mutate nothing.
  This Slice performs read-only Storage observation only and adds no execution path.
- Only OrganizerExecutor may mutate Storage. Every Storage call on this path goes through a
  `ReadOnlyStorageGuard` subclass whose counters are asserted zero after every precheck.
- The managed answer and the runtime answer must be the same answer: existence, conflict type and
  safety verdict come from `OrganizePlanner.plan`, the projected conflict outcome comes from
  `ConflictResolver.apply_configured`, and the composed path comes from the same helper the
  destination preview uses.
- Path safety is never weakened to make a precheck succeed: absolute, traversal and invalid
  components keep the planner's `INVALID_DESTINATION` / `PlanStatus.INVALID` verdict, and the
  ancestor walk is depth-bounded.
- No silent fallback and no silent overwrite: an unsupported capability is reported as a failure, an
  `overwrite` strategy is reported as requiring confirmation, and neither is ever presented as a
  path the precheck has already cleared.
- RecognitionType C remains C even when its RecognitionTypePolicy references NamingPolicy A,
  ClassificationPolicy A and OrganizePolicy A; the existing regressions must stay green.
- Anything presented as Active remains the exact immutable snapshot consumed by runtime; this Task
  changes no activation gate, no Active projection and no runtime marker.
- Credentials, endpoints, Storage root paths, raw Provider responses, headers, cookies, exception
  text and private user paths must not enter Web, API, evidence, logs, tests or commits.
  `config/alist.json` is never read.
- No FFmpeg or FFprobe dependency, invocation, or media-stream inspection.

## Required Tests

1. Falsifiable Web proof: with the destination precheck mount removed from the guided branch of
   `showConfigurationRevision` the focused UI test must fail; with the mount moved after the final
   `detailContent.append(actions); detail.hidden = false;` it must fail; with the section's heading,
   RecognitionType input, sample input or run control detached from `detailContent` it must fail;
   unmodified it must pass. Record each run and restore the file before committing.
2. Read-only proof, three independent ways: after a successful precheck every
   `guard.mutation_calls` counter is zero; a recursive snapshot of the destination tree (relative
   paths, sizes, contents and directory set) is byte-identical before and after; and a guard
   subclass that is asked to mutate raises `ReadOnlyStorageMutationError`, which the service maps to
   the `read_only_violation` category with the "do not activate" action.
3. Extraction neutrality: `tests/test_configuration_destination.py` passes **byte-unmodified** after
   the composition helper is extracted, and the destination preview's evidence document is asserted
   byte-identical to the pre-extraction expectation. The organizer, planner, executor, conflict
   resolution, Strategy Test and DryRun suites also pass unmodified.
4. Successful precheck against a real temporary Local destination tree: destination Storage ID
   and type, MediaLibrary ID and Storage-relative rootPath, `relativeDestination`,
   `destinationPath`, `destinationRootExists`, `destinationRootIsDirectory`,
   `deepestExistingAncestor`, `directoriesToCreate`, `targetExists`, `conflictProjection`,
   capability triple, `probeOperations`, `verdict`, `pathScope`, `sideEffects` and `retrySafe` are
   all asserted; both a fully missing subtree and a partially existing subtree are covered.
5. Conflict projection parity, one case per strategy, asserted against the production resolver: an
   absent target yields `ready`; an existing target yields `skip` under `ConflictStrategy.SKIP`,
   `rename` under `RENAME` with the resolver's own candidate as `proposedRelativeDestination` (and a
   second existing candidate proving the probe walks forward), `overwrite_requires_confirmation`
   under `OVERWRITE` with no overwrite performed and no confirmation implied, and
   `manual_confirmation_required` under `MANUAL`. An unsafe composition yields `invalid`.
6. Capability comparison: a `move` policy against a Local destination reports `can_move`
   satisfied and no gap; a `hardLink` policy against a Storage whose `_can_hard_link()` is patched
   False reports `capability_gap` naming `can_hard_link`, states the requiring operation, keeps the
   rest of the report populated, and repeats the no-fallback wording; an overwrite or source-cleanup
   policy additionally requires `can_delete`; and a document-declared `readOnly: true` destination
   Storage is reported as a capability gap rather than a crash — proving the adapter was **not**
   constructed with `readOnly` forced.
7. Failure behaviour, one bounded distinct category each: a non-Local destination Storage
   (`unsupported_storage_type`, asserting no adapter was constructed), a missing MediaLibrary root
   (`missing_destination_root`), a root that is a file (`destination_root_not_directory`), a
   `StorageError` mapped for `PERMISSION_DENIED`, `CONNECTION_FAILED`, `TIMEOUT` and `INVALID_PATH`,
   an over-deep ancestor walk (`invalid_path`), an invalid sample (unknown field against the union,
   `path` combined with synthetic fields, non-object body), every composition failure inherited from
   the preview stage with its production `PolicyResolutionErrorCode` / `NamingError` /
   `ClassificationError` code, an unresolved MediaLibrary, and the occupied-capacity refusal
   (`capacity_unavailable`) plus the timeout category. Every case asserts the revision version,
   digest, document, and the stored naming, classification, organize-authority, destination-preview
   and local-setup-check evidence rows unchanged.
8. C-identity: RecognitionType C mapped to NamingPolicy A, ClassificationPolicy A and OrganizePolicy
   A prechecks as RecognitionType C, and the probed destination is the one those A policies compose.
9. Exact-revision semantics: a stale `expectedVersion` / `expectedDigest` is refused with the
   current version and digest while prior evidence is preserved byte-for-byte; an Active revision is
   refused with `ConfigurationVersionConflict` and no evidence stored; evidence is current only for
   its exact revision version and digest and becomes stale after a further edit.
10. Zero authority and zero side effects beyond reads: the precheck creates no Task, Job, queue
    entry, plan record or execution authority, constructs no Provider client or Executor, writes no
    file on either Storage, emits no Storage `rootPath`, absolute path or private path into
    evidence, and leaves the Draft document, version and digest unchanged — asserted, not assumed.
11. Compatibility and regression: a revision document that omits the optional `organizePolicies`
    or `mediaLibraries` section still loads and renders; a configuration database created at marker
    9 opens and upgrades to marker 10 with its existing revisions and its naming, classification,
    organize-authority, destination-preview and local-setup-check evidence intact; a database
    created at marker 8 still upgrades; the runtime schema marker stays 22; the authenticated API
    returns `400 invalid_request`, `503` and the conflict mapping as specified; and the Phase
    22.3/22.4/22.5, 22.6-A/B/C/D configuration, Strategy Test, MetadataPolicy, correction and
    continuation regressions, the operator-UI tests, the RecognitionType C regressions and the
    complete offline suite all pass with no weakened or removed assertion.

## Validation

Run the focused destination-precheck, destination-preview, organize configuration/authority,
classification, naming, planner, organizer, executor, conflict-resolution and operator UI tests, the
Phase 22.3/22.4/22.5 configuration and continuation regressions, the RecognitionType C regressions,
and the complete offline suite. Run Ruff lint/format, `compileall`, `pip check`, both example
configuration validations, wheel build plus the isolated installed-wheel smoke test (reporting the
runtime schema marker), documentation local-link validation, `git diff --check`, the FFmpeg/FFprobe
production audit, the business-filesystem mutation audit, and the private configuration checks.
Report the deliberate mount-removal falsification runs explicitly, including restoration and a clean
`git status`. Report the read-only evidence explicitly: the zeroed guard counters, the
before/after destination-tree snapshot equality, and the `read_only_violation` mapping. Report the
extraction-neutrality evidence explicitly: that `tests/test_configuration_destination.py` and the
organizer/planner/executor/conflict-resolution suites were left byte-unchanged and pass. All Storage
I/O uses temporary directories; no real Storage, Provider, or production data is used, and
`config/alist.json` is never read.

## Documentation

Update `docs/progress.md` with this Slice's implementation evidence beneath the closed Phase 22.6-D
records, and `docs/roadmap.md` with the resulting Phase 22.6-E gate row and 当前节点. Update the CURRENT
claims in `docs/architecture.md`, `docs/requirements.md` and `docs/product-experience.md` only where
the read-only destination precheck actually changes them — including that the managed journey now
observes a real Local destination read-only, and that the projected conflict outcome and the
declared-versus-actual capability comparison are CURRENT for Local destinations only. Keep remote
destination prechecks, duplicate/cross-item collision detection, attachment prechecks,
mutation-based capability probing, absolute mounted-path display, combined activation evidence,
Provider switching, generic Task resume and broader per-item recovery explicitly TARGET. Never
rewrite historical Phase evidence, including the preserved Phase 22.5-E and Phase 22.6-A
`FIX REQUIRED` records and their rejected SHAs.

## Closure Checklist

- [ ] Workspace preflight records worktree, `.git`, index, sandbox, and approval mode.
- [ ] Capability mode is classified as Git-writable / Full Access or Git-read-only /
      workspace-write.
- [ ] The preceding dependent Slice is `PASS / CLOSED` with its commit SHA recorded
      (`c7ec192b3b20f236cca5a70ed59cad43e0851242`, Phase 22.6-D).
- [ ] The preserved rejected checkpoints `90ce13a6c6c39912dd389f71a1189314ff24eb5d` and
      `08dfd4f921728755209b6d52347d28f221121c47` are not amended, squashed, or rewritten.
- [ ] Implementation and all required focused/full quality gates pass with actual evidence,
      including the Web mount-removal falsifications, the three read-only proofs, the conflict
      projection parity cases, and the unmodified existing suites.
- [ ] `git status` and the commit manifest contain every required file and no unrelated/private
      file.
- [ ] Private runtime configuration remains ignored/untracked; no secret is staged or committed.
- [ ] A coherent, buildable commit has been created: `Commit SHA: ________________________________`.
- [ ] High Review inspected that exact SHA and returned: `High Audit: ___________________________`.
- [ ] `docs/progress.md` records Status / Commit SHA / High Audit.
- [ ] `docs/roadmap.md` records the resulting Phase gate.
- [ ] The next Slice has not started before every preceding gate is complete.
- [ ] Required major-closure/integration push is recorded, or push is explicitly not required.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- the exact falsification evidence for the Web mount and for the section's inputs and run control,
  including the failing output with each removal and the pass after restoration;
- the three read-only proofs: the zeroed `guard.mutation_calls` counters, the byte-identical
  destination-tree snapshot before and after, and the `ReadOnlyStorageMutationError` →
  `read_only_violation` mapping;
- the extraction-neutrality evidence: that `tests/test_configuration_destination.py` and the
  organizer/planner/executor/conflict-resolution test files were left byte-unchanged and pass, and
  that the destination preview's evidence document is byte-identical;
- the conflict projection parity evidence: which strategy produced which projected outcome, that the
  outcomes and the rename candidate came from `ConflictResolver.apply_configured` itself, and that
  `overwrite` was never confirmed or performed;
- the capability evidence: required versus declared versus missing capabilities per operation, the
  patched-`_can_hard_link` gap case, the `readOnly: true` document case proving the adapter was not
  constructed with `readOnly` forced, and the no-fallback wording actually rendered;
- what the service and API tests prove about the unchanged Draft and the preserved naming,
  classification, organize-authority, destination-preview and local-setup-check evidence rows, with
  the bounded categories actually asserted;
- confirmation that no remote Storage adapter, Provider client, Planner mutation, Executor, Task,
  Job, queue entry or plan record is created on this path, that no Storage `rootPath`, absolute path
  or private path enters evidence, and that the runtime schema marker, activation gate and Active
  projection are unchanged;
- the configuration schema marker transition 9 → 10 and its verified backward compatibility from
  both marker 9 and marker 8;
- CURRENT versus remaining TARGET for the Phase 22.6 journey and the exact next journey gap
  (expected: remote destination prechecks, then combined activation evidence for the checked
  activation gate).
