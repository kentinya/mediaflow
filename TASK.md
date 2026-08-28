# Phase 22.6-C — Managed OrganizePolicy Configuration and Exact-Revision Offline Organize Authority Explanation

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: 5e2da5c634f1fa72a40e5f50b035260418fe1a37
  (Phase 22.6-B PASS / CLOSED — 2026-08-28)
Earlier closed checkpoint: 30af69ac82b30f8a45ad66afbd3c9747597c8fe7
  (Phase 22.6-A PASS / CLOSED — 2026-08-28, includes the 22.6-A-F1 correction)
Preserved rejected checkpoints: 90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: NOT BLOCKING — Slice closure does not require a push, but
  5e2da5c634f1fa72a40e5f50b035260418fe1a37 and the docs record 279904c are not yet in
  origin/main; the phase-level Phase 22.6 closure requires an explicitly authorized push
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: managed OrganizePolicy editing + exact-revision offline organize authority explanation
```

## User Problem

Phase 22.6-A and 22.6-B made NamingPolicy and ClassificationPolicy editable inside a managed Draft
revision and explainable against that exact revision. OrganizePolicy — the object that decides
**what the executor is allowed to do to the operator's media**: move or copy or link, how a
destination conflict is handled, whether overwrite is permitted, whether attachments travel with the
file, whether source directories are cleaned up, and whether a failed batch rolls back — is still
outside the managed journey:

- `ConfigurationObjectService._SECTIONS` maps nine editable kinds
  (`mediaflow/application/configuration_objects.py:108-118`) and `organize_policy` is not one of
  them, so `mutate` refuses it with "this configuration object kind is not editable in the current
  slice" (`mediaflow/application/configuration_objects.py:2336`). The enum member
  `ConfigurationObjectKind.ORGANIZE_POLICY` already exists
  (`mediaflow/domain/configuration_management.py:25`) but nothing consumes it.
- `revision_detail` projects nine object sections
  (`mediaflow/application/configuration_objects.py:320-338`) and the Web guided editor mounts nine
  lists (`mediaflow/interfaces/operator_ui.py:951-959`); neither includes `organizePolicies`.
- `_references_for` (`mediaflow/application/configuration_objects.py:3145-3291`) has branches for
  MediaLibrary, NamingPolicy and ClassificationPolicy, but none for OrganizePolicy. In a managed
  document `_type_policy` requires `organizePolicy` to resolve
  (`mediaflow/infrastructure/strategy_user_configuration.py:491-504`), so removing a referenced
  OrganizePolicy makes the whole revision unloadable — today with no reference evidence and no
  delete protection.

The only way to change an organize operation or a conflict strategy today is a whole-document JSON
import: no per-object bounded validation, no reference evidence, no delete blocking, no Before/After
guided audit — for the one object class that carries destructive authority.

Second, the operator cannot answer the question that must be answered **before** activation: "for
this RecognitionType, in this exact revision, what will the organize stage be authorized to do?"
`RecognitionTypePolicyResolver.resolve` (`mediaflow/application/policies.py:13-88`) already resolves
RecognitionType → RecognitionTypePolicy → `organize_policy_id` deterministically with bounded
`PolicyResolutionErrorCode` outcomes (`mediaflow/domain/recognition.py:331-336`), but no managed
entry point consumes it, so operation, conflict strategy, overwrite authority, cleanup and rollback
stay unexplained until execution time.

## User Journey

```text
Configuration → open a Draft revision → see OrganizePolicy objects with their operation, conflict
   strategy, destructive markers, and which RecognitionTypePolicies reference them
→ create / edit / copy / delete one OrganizePolicy (delete blocked while referenced, naming the
   referencing RecognitionTypePolicy and field)
→ submit an invalid policy (unknown field, unsupported operation, a delete or create_directory
   operation, overwrite conflicting with the conflict strategy, out-of-range duplicate-detection or
   cleanup limits, unsafe ignore pattern, ignore patterns outside ignorable mode) and be told which
   bounded category failed, with the Draft untouched
→ correct it → run the exact-revision offline organize authority explanation for one RecognitionType
→ read which OrganizePolicy applies and why, the operation, the conflict strategy, whether overwrite
   or source cleanup or rollback authority is granted, the attachment scope, the duplicate-detection
   bounds, and which Storage capabilities the operation will require
→ Validate the revision
```

Entry point, permission model and revision authority are the existing managed ones: the same
Configuration revision detail view, the same `MANAGE_CONFIGURATION` permission, the same
Draft/Validated editability, the same optimistic `expectedVersion` / `expectedDigest` contract.

## User-visible Outcome

- The managed revision detail view lists `OrganizePolicies (n)` with, per policy, its ID, operation,
  conflict strategy, attachment enablement, duplicate-detection mode, source-cleanup mode, an
  explicit destructive marker when the conflict strategy is `overwrite` or cleanup is not `none`,
  and existing reference evidence.
- Add / Edit / Copy / Delete are available on a Draft or Validated revision through the same bounded
  JSON object editor used by MetadataPolicy, NamingPolicy and ClassificationPolicy; Delete is
  refused while a RecognitionTypePolicy references the policy, naming section, object and field.
- An invalid OrganizePolicy is refused with one bounded, secret-free category naming the offending
  field, and the Draft document, version, digest and any prior explanation evidence are unchanged.
- An offline organize authority explanation bound to the exact revision reports: the requested
  RecognitionType, the resolved RecognitionTypePolicy ID, the applied OrganizePolicy ID, the
  operation, the conflict strategy, `overwriteAuthorized`, `deleteAuthorized`, the attachment scope,
  the duplicate-detection mode with its bounds, the rollback settings, the source-cleanup settings,
  the required Storage capabilities implied by the operation, and bounded warnings for every
  destructive or fallback-sensitive setting.
- The explanation states explicitly that no fallback is implied: a HardLink or SoftLink operation
  never silently becomes Copy or Move, so an unsupported capability is a failure rather than a
  downgrade.
- RecognitionType C resolving OrganizePolicy A is reported as RecognitionType C: the explanation
  carries the resolved RecognitionType identity and never rewrites it to the policy owner's type.
- Explanation evidence carries the same current/stale semantics as the naming and classification
  previews: current only for the exact revision ID, version and digest it was produced from, and a
  stale row is labelled stale with the explicit rerun action.
- No Storage adapter, Provider client, media file, plan, or execution authority is involved at any
  point.

## Failure and Recovery

| Failure class | Visible state | Durable state / side effects | Retry safe | Recovery | If recovery also fails |
|---|---|---|---|---|---|
| Invalid OrganizePolicy submitted (unknown field, unsupported or forbidden operation, `overwrite: true` against a non-overwrite conflict strategy, out-of-range duplicate-detection or cleanup limit, unsafe or misplaced ignore pattern, non-object sub-object) | Bounded distinct category naming the offending field; API `400 invalid_request` | Draft document, version, digest and stored explanation evidence unchanged; nothing written | Yes | Correct the reported field and resubmit | Revision stays Draft and editable; a known-good policy can be copied as a starting point |
| Delete refused because referenced | Refusal naming `recognitionTypePolicies:<id>.organizePolicy` with the reference total | No document change; the policy still exists | Yes | Repoint or delete the referencing RecognitionTypePolicy first, then delete the policy | The policy remains intact and the revision stays loadable |
| Stale edit or stale explanation (version/digest moved) | Conflict stating the current version and digest with the reload action | Current Draft and prior explanation evidence preserved | Yes | Reload the revision, then reapply the edit or rerun the explanation | The Draft is never partially applied; the operator re-reads authoritative state |
| Requested RecognitionType has no enabled RecognitionTypePolicy, has two, is disabled, or points at an OrganizePolicy that does not exist in this revision | Failed explanation carrying the production `PolicyResolutionErrorCode` and the bounded message | Failure evidence stored for the exact revision; no document change | Yes | Add, enable, deduplicate or repoint the RecognitionTypePolicy in the same Draft, then rerun | Draft validation still refuses activation, so an unresolvable mapping cannot become Active |
| Policy grants destructive authority (`overwrite` conflict strategy, `ignorable` cleanup, rollback disabled for a Move) | Completed explanation with explicit destructive warnings naming each setting | Explanation evidence stored as completed-with-warning; no document change | Yes | Change the setting, or accept it deliberately and record the decision | The warning is durable and re-readable, so activation is a deliberate act |
| Explanation requested on a non-editable revision | Refusal stating a Draft or Validated revision is required | No evidence written | Yes | Open or create a Draft revision and rerun | Active configuration is untouched and remains the runtime snapshot |

Retry alone is never the recovery text: every row states what is durable, what is safe to repeat,
and the single explicit action that continues.

Batch per-item independence does not apply: this Task edits one configuration object per request and
explains one RecognitionType per request.

## UX Acceptance Criteria

- [ ] The revision detail view lists OrganizePolicies with operation, conflict strategy, destructive
      markers and reference evidence, and the list is reachable: a focused test fails if
      `renderGuidedObjectList(data, guided, 'organizePolicies', 'OrganizePolicies')` leaves the
      guided branch of `showConfigurationRevision`.
- [ ] The organize authority section is reachable: a focused test fails if its mount call leaves the
      guided branch, if the mount moves after the final `detail.hidden = false;`, or if the section's
      RecognitionType input, run control or heading stops being appended to `detailContent` inside
      the rendering function's own body.
- [ ] Both proofs are brace-matched and body-scoped, using the `_js_function_body(script, name)` and
      `_js_braced_body(script, opening)` helpers already in `tests/test_operator_ui.py`; a
      defined-but-unmounted section must not pass.
- [ ] Creating, editing, copying and deleting one OrganizePolicy through
      `ConfigurationObjectService.mutate` produces a new Draft version with the guided Before/After
      audit action recorded, exactly as the NamingPolicy and ClassificationPolicy slices do.
- [ ] Deleting an OrganizePolicy referenced by `recognitionTypePolicies[].organizePolicy` is refused
      with reference evidence naming section, object ID and field, and the document is unchanged;
      `references()` exposes the same evidence under the key `organize_policy:<id>`, which is the key
      the Web list looks up.
- [ ] Each invalid case — unknown top-level or sub-object field, unsupported operation, `delete` or
      `create_directory` operation, `overwrite: true` against a non-overwrite conflict strategy,
      out-of-range `fastSampleBytes` / `chunkSize` / `fullMaxFileSize`, out-of-range
      `maxParentDirectories` / `maxEntries`, unsafe ignore pattern, ignore patterns supplied outside
      `ignorable` mode, non-object sub-object, non-boolean attachment flag — is refused through the
      public service with a bounded distinct category, and the revision version, digest,
      `organizePolicies` content and stored explanation evidence are asserted unchanged.
- [ ] The same rejections are asserted through the authenticated API as `400 invalid_request` with
      bounded, secret-free messages.
- [ ] A normalization round-trip is proven semantically neutral: every example `organizePolicies`
      entry, after passing through the managed normalizer, loads through the production loader into a
      byte-equal domain `OrganizePolicy`, so a managed edit cannot silently change what runtime
      consumes.
- [ ] A successful explanation returns the resolved RecognitionTypePolicy ID, applied OrganizePolicy
      ID, operation, conflict strategy, overwrite/delete authority flags, attachment scope,
      duplicate-detection bounds, rollback, source-cleanup settings, required Storage capabilities
      and the destructive warnings; unresolvable mappings return the production
      `PolicyResolutionErrorCode` with its bounded message.
- [ ] RecognitionType C mapped to OrganizePolicy A and NamingPolicy A is explained as RecognitionType
      C, and the existing C-identity regressions stay green.
- [ ] An explanation submitted with a stale `expectedVersion` or `expectedDigest` is refused with the
      current version and digest, and the previously stored evidence is preserved unchanged.
- [ ] Explanation evidence is presented as current only for its exact revision ID, version and
      digest; after any further edit the same evidence is presented as stale with the rerun action.
- [ ] Anything shown as Active is still the exact immutable runtime snapshot; this Task changes no
      activation gate, no Active projection and no runtime schema marker.

## Technical Scope

Reuse the shipped organize domain and policy-resolution stack; do not fork or reimplement operation
parsing, bounds checking, conflict semantics or policy resolution.

```text
mediaflow/domain/configuration_management.py        → organize authority evidence type + status
mediaflow/application/configuration_objects.py      → section, normalization, references, explanation
mediaflow/infrastructure/sqlite_configuration_management.py → evidence table + schema marker 7 → 8
mediaflow/interfaces/service_api.py                 → POST .../organize-authority
mediaflow/interfaces/operator_ui.py                 → guided list mount + authority section mount
tests/*                                             → falsifiable Web, service, API, regression
docs/*                                              → CURRENT/TARGET and Phase gate records
```

- `_SECTIONS` gains `ConfigurationObjectKind.ORGANIZE_POLICY: "organizePolicies"`, and
  `revision_detail` projects the section the same optional way `namingPolicies` and
  `classificationPolicies` are projected (absent section renders as an empty list, never an error).
- `_normalize` gains an ORGANIZE_POLICY branch accepting exactly the canonical loader shape in
  `mediaflow/infrastructure/strategy_user_configuration.py:343-365` and
  `config/strategy.example.json`: `{id, operation, conflictStrategy?, overwrite?,
  duplicateDetection{mode, fastSampleBytes, fullMaxFileSize, chunkSize}?,
  rollback{enabled, cleanupCreatedDirectories}?,
  sourceDirectoryCleanup{mode, maxParentDirectories, ignorePatterns, maxEntries}?,
  attachments{enabled, subtitles, nfo, artwork, trailers, otherSameStem}?}`. Do **not** invent
  `name`, `enabled`, `priority` or `description` fields: the domain `OrganizePolicy`
  (`mediaflow/domain/organizer.py:181-190`) has none, and a managed field runtime ignores would make
  the editor lie about what Active means.
- Bounds and semantics must come from the domain, not from a second hand-written validator: build
  real `OrganizePolicy`, `AttachmentPolicy`, `HashPolicy`, `RollbackPolicy` and
  `DirectoryCleanupPolicy` objects (`mediaflow/domain/organizer.py:16-190`,
  `mediaflow/domain/duplicates.py:14-31`) and map their `ValueError` text into the bounded managed
  category, exactly as the ClassificationPolicy branch re-wraps `ClassificationError`. The managed
  branch owns only the unknown-field rejection, the bounded ID and the operation restriction below.
- Operation values follow the loader's accepted spellings (`MOVE`, `COPY`, `HARDLINK`, `HARD_LINK`,
  `SYMLINK`, `SOFTLINK`, `SOFT_LINK`, and the lowercase enum values) via
  `mediaflow/infrastructure/strategy_user_configuration.py:596-609`, but the managed editor accepts
  only Move, Copy, HardLink and SoftLink. `delete` and `create_directory` are valid
  `OrganizeOperationType` members and are therefore currently loadable as an organize policy
  operation; the managed editor must reject both with a bounded category. Do not change the loader in
  this Slice — record the loader's permissiveness as a follow-up observation.
- Preserve the loader's cross-field rule verbatim in meaning: `overwrite: true` with a
  `conflictStrategy` other than `overwrite` is refused, and an absent `conflictStrategy` with
  `overwrite: true` resolves to the `overwrite` strategy. The canonical output must re-load through
  the production loader into an identical domain `OrganizePolicy`.
- `organize_authority(revision_id, *, expected_version, expected_digest, actor, recognition_type)`
  mirrors `classification_preview` (`mediaflow/application/configuration_objects.py:744-867`):
  Draft/Validated only, exact version+digest or a conflict carrying `durable_state` and
  `next_action`, a bounded `recognition_type` (non-empty, ≤64 characters, NUL-free), and one current
  evidence row per revision.
- Resolution uses the production resolver: build `RecognitionType`, `RecognitionTypePolicy` and
  `OrganizePolicy` domain objects straight from `_canonical_objects(revision.document, section)` — as
  the naming and classification previews do — then call `RecognitionTypePolicyResolver.resolve`
  (`mediaflow/application/policies.py:41-87`) with `PolicyReference` catalogs so that
  `MISSING_TYPE_POLICY`, `DUPLICATE_TYPE_POLICY`, `RECOGNITION_TYPE_DISABLED`, `POLICY_DISABLED` and
  `INVALID_POLICY_REFERENCE` come from production code. Do **not** call
  `load_managed_runtime_configuration` and do not construct Storage, Provider, Parser, Planner or
  Executor objects on this path.
- Required Storage capabilities are **declared, not probed**: map the resolved operation to the
  `StorageCapabilities` field names it needs (`mediaflow/domain/storage.py:52-57`) — Move →
  `can_move`, Copy → `can_copy`, HardLink → `can_hard_link`, SoftLink → `can_soft_link`, plus
  `can_delete` only when the conflict strategy is `overwrite` or source cleanup is enabled. No
  Storage adapter is created, listed, stat-ed or written.
- Evidence: add `OrganizeAuthorityEvidence` and `ConfigurationOrganizeAuthorityStatus` alongside
  `ClassificationPreviewEvidence` and `NamingPreviewEvidence`
  (`mediaflow/domain/configuration_management.py:285-430`) with the same bounds, digest validation,
  size limit, `"sideEffects": "none"` and `"retrySafe": true` document keys; do not widen or
  repurpose either existing evidence type or its table. Persist through a new additive
  `managed_organize_authority_previews` table with a `(status, previewed_at)` index and a foreign key
  to `managed_configuration_revisions`, and bump `CONFIGURATION_SCHEMA_VERSION` from 7 to 8. The
  runtime schema marker must stay 22.
- API: `POST /api/v1/configuration/revisions/{id}/organize-authority` requiring
  `MANAGE_CONFIGURATION`, accepting exactly `{expectedVersion, expectedDigest, recognitionType}`,
  returning the evidence document, `503` when the service is absent, `400 invalid_request` for
  bounded validation failures and the existing conflict mapping for a stale revision — mirroring
  `mediaflow/interfaces/service_api.py:495-575`.
- Web: add the guided list mount and a `renderOrganizeAuthority(revision, guided)` mount inside the
  `if (guided) {` branch of `showConfigurationRevision`, after `renderClassificationPreview` and
  before the final `detail.hidden = false;`; add `organizePolicies` to the reference-kind map, the
  object-label handling and the guided-JSON editor set so reference evidence resolves under
  `organize_policy:<id>` and the editor opens as a bounded JSON object. Offer the same Copy
  affordance the NamingPolicy and ClassificationPolicy lists offer, since duplicating a working
  policy is the documented recovery path.
- Destructive settings must be visibly marked in both the list summary and the explanation warnings;
  overwrite must never be presented as an ordinary default.

## Non-goals

- No composed final destination path: `MediaLibrary.RootPath + ClassificationPolicy relativePath +
  NamingPolicy directory/filename` composition, and any display of a MediaLibrary `rootPath` inside
  evidence, remain deferred to the next Slice.
- No destination existence, target-collision, duplicate-media or capability **probing**; no Storage
  adapter construction, listing, stat, read or write of any kind. Required capabilities are declared
  from the operation only.
- No `OrganizePlanner`, `OrganizerExecutor`, conflict-resolution, rollback or cleanup behaviour
  change, and no execute authority: this Task creates no plan and no job.
- No loader change: the loader's tolerance of `delete` / `create_directory` operations, its
  `organizeOperation` inline alias and its lack of top-level unknown-field rejection for organize
  policies are recorded as observations, not fixed here.
- No change to Draft/Validate/Activate semantics, the checked activation gate, the Active projection,
  the immutable runtime snapshot, or the runtime SQLite schema marker 22.
- No change to the naming or classification preview contracts, their evidence keys, or their tables.
- No Provider, Metadata, scan, Task, Job, queue or media work; no Provider switching, generic Task
  resume, per-item Processing Checkpoint recovery, or manual organize journey.
- No new frontend framework, unrelated Web refactor, or JS test runner in CI.
- No rewrite of historical Phase evidence, including the preserved Phase 22.5-E and Phase 22.6-A
  `FIX REQUIRED` records and their rejected SHAs.
- Carried-forward P2 items stay out of scope and must not be silently fixed here: the naming engine
  separator/conversion message wording, legacy naming template aliases, the classification loader's
  flat-rule and `relativePath` aliases, whole-document policy normalization during preview, the
  path-mode sample field tolerance, the unclosed `sqlite3.connect` context managers in
  `tests/test_configuration_classification.py`, and first-object seeding into a document that omits
  an optional section.

## Safety and Architecture Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner and DryRun mutate nothing;
  this Task adds no execution path and grants no execute authority.
- Only OrganizerExecutor may mutate Storage. This Task describes authority; it never exercises it.
- No silent fallback: a HardLink or SoftLink policy must never be presented as degradable to Copy or
  Move, and the explanation must say so explicitly.
- Overwrite and delete authority stay explicit: the explanation must name them, and the editor must
  not let them appear by omission.
- RecognitionType C remains C even when its RecognitionTypePolicy references OrganizePolicy A,
  ClassificationPolicy A and NamingPolicy A; the existing regressions must stay green and must cover
  the newly editable section.
- Anything presented as Active remains the exact immutable snapshot consumed by runtime; a managed
  edit must not change runtime semantics through normalization.
- Credentials, endpoints, raw Provider responses, headers, cookies, exception text and private paths
  must not enter Web, API, evidence, logs, tests or commits. `config/alist.json` is never read.
- No FFmpeg or FFprobe dependency, invocation, or media-stream inspection.

## Required Tests

1. Falsifiable Web proof, established in this Slice rather than deferred to a correction: with the
   organize authority mount removed from `showConfigurationRevision` the focused UI test must fail;
   with the `organizePolicies` list mount removed it must fail; with the authority mount moved after
   the final `detail.hidden = false;` it must fail; with the section's controls or heading detached
   from `detailContent` it must fail; unmodified it must pass. Record each run and restore the file
   before committing.
2. Guided CRUD through `ConfigurationObjectService.mutate` on a real repository-backed Draft: create,
   update, copy-as-new and delete one OrganizePolicy, asserting the new version, the guided audit
   action, and the resulting document section.
3. Delete blocking: a policy referenced by `recognitionTypePolicies[].organizePolicy` cannot be
   deleted; the refusal carries reference evidence naming section, object and field; the document is
   unchanged; `references()` exposes the evidence under `organize_policy:<id>`; after repointing the
   referencing RecognitionTypePolicies the delete succeeds.
4. Service-boundary invalid input: every case listed in the UX acceptance criteria yields a bounded
   distinct category, with version, digest, section content and stored evidence asserted unchanged;
   the authenticated API returns `400 invalid_request` with a bounded, secret-free message for the
   same cases.
5. Normalization neutrality: each example organize policy, normalized and then loaded through the
   production loader, equals the domain `OrganizePolicy` loaded from the original document.
6. Explanation behaviour: a resolvable RecognitionType returns the expected type policy, applied
   policy, operation, conflict strategy, authority flags, attachment/duplicate/rollback/cleanup
   settings and required capabilities; an overwrite policy and an `ignorable` cleanup policy each add
   their destructive warning; a missing, duplicated, disabled and dangling mapping each return the
   matching `PolicyResolutionErrorCode`; RecognitionType C mapped to OrganizePolicy A reports
   RecognitionType C; a stale `expectedVersion`/`expectedDigest` is refused with the current version
   and digest while prior evidence is preserved; evidence is current only for its exact revision
   version and digest and becomes stale after a further edit.
7. Zero side effects: the explanation constructs no Storage adapter, Provider client, Planner or
   Executor, writes no file, and leaves the Draft document, version and digest unchanged — asserted,
   not assumed.
8. Compatibility: a revision document that omits the optional `organizePolicies` section still loads,
   renders and produces reference evidence; a configuration database created at marker 7 opens and
   upgrades to marker 8 with its existing revisions, naming preview evidence and classification
   preview evidence intact; the runtime schema marker stays 22.
9. Regression: Phase 22.6-A naming and Phase 22.6-B classification configuration tests, the
   operator-UI tests, Phase 22.3/22.4/22.5 configuration, Strategy Test, MetadataPolicy, correction
   and continuation regressions, the organizer/planner/executor tests, the RecognitionType C
   regressions, and the complete offline suite all pass with no weakened or removed assertion.

## Validation

Run the focused organize configuration/authority, classification, naming and operator UI tests, the
Phase 22.3/22.4/22.5 configuration and continuation regressions, the organizer and planner tests, the
RecognitionType C regressions, and the complete offline suite. Run Ruff lint/format, `compileall`,
`pip check`, both example configuration validations, wheel build plus the isolated installed-wheel
smoke test (reporting the runtime schema marker), documentation local-link validation,
`git diff --check`, the FFmpeg/FFprobe production audit, the business-filesystem mutation audit, and
the private configuration checks. Report the deliberate mount-removal falsification runs explicitly,
including restoration and a clean `git status`. No real Storage, Provider, or production data is used,
and `config/alist.json` is never read.

## Documentation

Update `docs/progress.md` with this Slice's implementation evidence beneath the closed Phase 22.6-B
records, and `docs/roadmap.md` with the resulting Phase 22.6-C gate row and 当前节点. Update the
CURRENT claims in `docs/architecture.md`, `docs/requirements.md` and `docs/product-experience.md`
only where managed OrganizePolicy editing and the offline organize authority explanation actually
change them. Keep the composed destination-path preview, destination conflict/capability/existence
prechecks, combined activation evidence, Provider switching, generic Task resume and broader per-item
recovery explicitly TARGET. Never rewrite historical Phase evidence, including the preserved
Phase 22.5-E and Phase 22.6-A `FIX REQUIRED` records and their rejected SHAs.

## Closure Checklist

- [x] Workspace preflight records worktree, `.git`, index, sandbox, and approval mode.
- [x] Capability mode is classified as Git-writable / Full Access or Git-read-only / workspace-write.
- [x] The preceding dependent Slice is `PASS / CLOSED` with its commit SHA recorded
      (`5e2da5c634f1fa72a40e5f50b035260418fe1a37`, Phase 22.6-B).
- [x] The preserved rejected checkpoints `90ce13a6c6c39912dd389f71a1189314ff24eb5d` and
      `08dfd4f921728755209b6d52347d28f221121c47` are not amended, squashed, or rewritten.
- [x] Implementation and all required focused/full quality gates pass with actual evidence,
      including the Web mount-removal falsifications and their restoration.
- [x] `git status` and the commit manifest contain every required file and no unrelated/private file.
- [x] Private runtime configuration remains ignored/untracked; no secret is staged or committed.
- [ ] A coherent, buildable commit has been created: `Commit SHA: ________________________________`.
- [ ] High Review inspected that exact SHA and returned: `High Audit: ___________________________`.
- [ ] `docs/progress.md` records Status / Commit SHA / High Audit.
- [ ] `docs/roadmap.md` records the resulting Phase gate.
- [ ] The next Slice has not started before every preceding gate is complete.
- [ ] Required major-closure/integration push is recorded, or push is explicitly not required.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- the exact falsification evidence for both Web mounts and for the authority section's controls,
  including the failing output with each mount removed and the pass after restoration;
- what the service and API tests prove about the unchanged Draft, absent evidence, and
  reference-blocked deletion, with the bounded categories actually asserted;
- the normalization-neutrality result for every example organize policy;
- the explanation outcomes proven: resolved authority with required capabilities, destructive
  warnings, each `PolicyResolutionErrorCode` failure, C-identity preservation, and stale-revision
  refusal with preserved prior evidence;
- confirmation that no Storage adapter, Provider client, Planner or Executor is constructed on the
  explanation path, and that the runtime schema marker, activation gate and Active projection are
  unchanged;
- the configuration schema marker transition 7 → 8 and its verified backward compatibility;
- CURRENT versus remaining TARGET for the Phase 22.6 journey and the exact next journey gap
  (expected: the composed destination-path preview plus destination conflict/capability/existence
  prechecks, then combined activation evidence).
