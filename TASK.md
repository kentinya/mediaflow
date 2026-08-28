# Phase 22.6-D — Managed Exact-Revision Offline Composed Destination Preview

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR COMMIT (pre-checkpoint)
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: 47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa
  (Phase 22.6-C PASS / CLOSED — 2026-08-28)
Earlier closed checkpoints: 5e2da5c634f1fa72a40e5f50b035260418fe1a37 (Phase 22.6-B) and
  30af69ac82b30f8a45ad66afbd3c9747597c8fe7 (Phase 22.6-A, includes the 22.6-A-F1 correction)
Preserved rejected checkpoints: 90ce13a6c6c39912dd389f71a1189314ff24eb5d (Phase 22.6-A) and
  08dfd4f921728755209b6d52347d28f221121c47 (Phase 22.5-E); never amended, squashed or rewritten
Push gate: NOT BLOCKING — Slice closure does not require a push, but the closed 22.6-C checkpoint
  and its docs records are not yet in origin/main; the phase-level Phase 22.6 closure requires an
  explicitly authorized push
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: exact-revision offline composed destination preview
  (MediaLibrary rootPath + ClassificationPolicy relativePath + NamingPolicy directory/filename),
  reusing the production planner composition and path-safety rules
```

## User Problem

Phase 22.6-A, 22.6-B and 22.6-C made NamingPolicy, ClassificationPolicy and OrganizePolicy editable
inside a managed Draft revision and explainable against that exact revision. Every explanation is
still **partial**, and the one question the operator actually asks before activating a revision —
"where will this file end up?" — has no answer anywhere in the managed journey:

- `naming_preview` (`mediaflow/application/configuration_objects.py:499-772`) reports
  `directorySegments` and `filename` for one NamingPolicy, but never the library root or the
  classification-relative path, so it describes the tail of the destination only.
- `classification_preview` (`mediaflow/application/configuration_objects.py:774-895`) reports
  `mediaLibraryId`, `mediaLibraryResolved` and `relativePath`
  (`mediaflow/application/configuration_objects.py:833-835`), but deliberately never reads the
  MediaLibrary `rootPath` and never joins its own `relativePath` with anything.
- `organize_authority` (`mediaflow/application/configuration_objects.py:897-1072`) explains what the
  executor may **do**, never **where**.
- The production composition and the whole path-safety decision live in one place the managed
  journey does not call: `OrganizePlanner.plan` (`mediaflow/application/organizer.py:91-124`)
  computes `root = _safe_root(media_library.root_path)`, rejects an absolute/traversal/invalid
  component with `ConflictType.INVALID_DESTINATION` and `PlanStatus.INVALID`, then composes
  `relative_destination = posixpath.join(classification.relative_path, *naming.directory_segments,
  naming.filename)` and `target = posixpath.join(root, relative_destination)`.

So today the operator must mentally join three separate previews, guess the MediaLibrary root, and
discover an unsafe or traversal-producing combination only when a plan is produced against real
media. Three individually valid objects can still compose an invalid destination — an unsafe
`relativePath`, a traversal segment from a naming template, a filename containing `/` — and nothing
in the managed journey says so before activation.

The second, sharper risk is a **forked composition**. Any managed preview that re-implements the
join or the safety predicates would answer a different question from the one runtime answers, while
claiming to describe it. The one legitimate way to add this preview is to make the managed path call
the same composition and the same safety rules the planner uses.

## User Journey

```text
Configuration → open a Draft revision → NamingPolicies, ClassificationPolicies, OrganizePolicies and
   the organize authority explanation are already visible
→ enter one RecognitionType and one sample (a path, or synthetic fields) in the destination preview
→ read the exact composed destination for this revision: which RecognitionTypePolicy resolved, which
   NamingPolicy and ClassificationPolicy applied, which MediaLibrary was selected and its rootPath,
   the classification relative path, the naming directory segments and filename, and the single
   composed destination path they produce
→ if the composition is unsafe, read which contribution was unsafe and which object owns it
→ correct that object in the same Draft → rerun the preview → Validate the revision
```

Entry point, permission model and revision authority are the existing managed ones: the same
Configuration revision detail view, the same `MANAGE_CONFIGURATION` permission, the same
Draft/Validated editability, the same optimistic `expectedVersion` / `expectedDigest` contract, and
the same current/stale evidence semantics as the naming, classification and organize-authority
explanations.

## User-visible Outcome

- A destination preview section on the managed revision detail view accepts one RecognitionType and
  one sample and returns, bound to the exact revision, a single composed destination path.
- The result names every contribution and the object that owns it, in composition order:
  MediaLibrary `rootPath` (with its ID and whether it resolved in this revision),
  ClassificationPolicy `relativePath` (with the applied policy ID and matched rule), NamingPolicy
  directory segments and filename (with the applied policy ID).
- The composed path is explicitly labelled **Storage-relative**: it is the MediaLibrary-rooted path
  the planner composes (`plan.media_library_root` + `plan.relative_destination`), not a
  filesystem-absolute path. The Storage mount prefix is not applied, not read, and not displayed.
- RecognitionType C resolving NamingPolicy A and ClassificationPolicy A is reported as
  RecognitionType C; the preview carries the resolved RecognitionType identity and never rewrites it
  to the policy owner's type.
- An unsafe composition is reported as a failed preview naming the unsafe contribution and its
  owning object, using the same rule the planner applies — so the managed answer and the runtime
  answer cannot disagree.
- An unresolvable RecognitionType, a naming failure, a classification failure, an unresolved
  MediaLibrary and an invalid sample each produce a bounded, secret-free, durable failure
  explanation with the explicit action that continues.
- Preview evidence is current only for the exact revision ID, version and digest it was produced
  from; after any further edit the stored evidence is presented as stale with the rerun action.
- No Storage adapter, Provider client, media file, plan, job or execution authority is involved at
  any point, and no destination existence, collision or capability check is performed or implied.

## Failure and Recovery

| Failure class | Visible state | Durable state / side effects | Retry safe | Recovery | If recovery also fails |
|---|---|---|---|---|---|
| Invalid sample (unknown field, `path` combined with synthetic fields, out-of-bounds value, non-object body) | Bounded `invalid_input` category naming the offending field; API `400 invalid_request` | Draft document, version, digest and previously stored destination evidence unchanged; nothing written | Yes | Correct the reported field and rerun the preview | The revision stays Draft and editable; the naming and classification previews still answer their own halves |
| Requested RecognitionType has no enabled RecognitionTypePolicy, has two, is disabled, or points at a policy missing from this revision | Failed preview carrying the production `PolicyResolutionErrorCode` and its bounded message | Failure evidence stored for the exact revision; no document change | Yes | Add, enable, deduplicate or repoint the RecognitionTypePolicy in the same Draft, then rerun | Draft validation still refuses activation, so an unresolvable mapping cannot become Active |
| Naming or classification stage fails for this sample (missing variable under a strict strategy, no matching rule, policy error) | Failed preview carrying the production `NamingError` / `ClassificationError` code, naming the applied policy | Failure evidence stored; no document change | Yes | Correct that policy or the sample in the same Draft, then rerun | The single-policy naming and classification previews isolate which stage is wrong |
| Classification selected a MediaLibrary that does not exist in this revision | Failed preview naming the unresolved MediaLibrary ID | Failure evidence stored; no document change | Yes | Add or correct the MediaLibrary in this Draft, then rerun | Activation still cannot consume an unresolvable reference |
| The composed destination is unsafe (absolute, traversal, or invalid component, or an unsafe MediaLibrary rootPath) | Failed preview naming the unsafe contribution and its owning object, matching the planner's `INVALID_DESTINATION` rule | Failure evidence stored; no document change, no plan, no execution | Yes | Fix the named object's path, segment or filename in the same Draft, then rerun | The planner would refuse the same composition at execution time, so nothing unsafe becomes reachable |
| Stale preview (version/digest moved) | Conflict stating the current version and digest with the reload action | Current Draft and prior destination evidence preserved | Yes | Reload the revision, then rerun the preview | The Draft is never partially applied; the operator re-reads authoritative state |
| Preview requested on a non-editable revision | Refusal stating a Draft or Validated revision is required | No evidence written | Yes | Open or create a Draft revision and rerun | Active configuration is untouched and remains the runtime snapshot |

Retry alone is never the recovery text: every row states what is durable, what is safe to repeat,
and the single explicit action that continues.

Batch per-item independence does not apply: this Task previews one RecognitionType and one sample
per request. The existing naming, classification and organize-authority evidence rows must remain
independent of the new one — a failed destination preview must not overwrite, hide or invalidate
them.

## UX Acceptance Criteria

- [ ] The destination preview section is reachable: a focused test fails if its mount call leaves
      the `if (guided) {` branch of `showConfigurationRevision`, if the mount moves after the final
      `detail.hidden = false;`, or if the section's RecognitionType input, sample input, run control
      or heading stops being appended to `detailContent` inside the rendering function's own body.
- [ ] The proof is brace-matched and body-scoped, using the `_js_function_body(script, name)` and
      `_js_braced_body(script, opening)` helpers already in `tests/test_operator_ui.py:37-60`; a
      defined-but-unmounted section must not pass.
- [ ] The rendered result shows the composed destination path together with every contribution and
      its owning object ID, in composition order, and labels the path as Storage-relative.
- [ ] The section is read-only on a non-editable revision: the run control is not offered when
      `configurationRevisionEditable(revision)` is false, exactly as the organize authority section
      behaves (`mediaflow/interfaces/operator_ui.py:602`).
- [ ] A successful preview returns the resolved RecognitionType, RecognitionTypePolicy ID, applied
      NamingPolicy ID, applied ClassificationPolicy ID, MediaLibrary ID, MediaLibrary rootPath,
      classification relative path, naming directory segments, filename, the root-relative
      destination and the composed Storage-relative destination path.
- [ ] The composed path is byte-equal to what `OrganizePlanner.plan` produces from the same
      MediaLibrary root, `ClassificationResult` and `NamingResult` — asserted against the real
      planner in the same test, not against a re-implementation of the join.
- [ ] Every unsafe composition the planner rejects is rejected by the preview with the same verdict,
      and the preview names the unsafe contribution: unsafe MediaLibrary rootPath, absolute or
      traversal classification `relativePath`, traversal naming directory segment, and a filename
      containing `/` or a traversal name.
- [ ] RecognitionType C mapped to NamingPolicy A and ClassificationPolicy A previews as
      RecognitionType C, and the existing C-identity regressions stay green.
- [ ] Each failure class in the table above is asserted through the public service with a bounded
      distinct category, and the revision version, digest, document, and the stored naming,
      classification and organize-authority evidence rows are asserted unchanged.
- [ ] The same rejections are asserted through the authenticated API as `400 invalid_request` with
      bounded, secret-free messages, and a stale revision returns the existing conflict mapping.
- [ ] Preview evidence is presented as current only for its exact revision ID, version and digest;
      after any further edit the same evidence is presented as stale with the rerun action.
- [ ] No Storage `rootPath`, endpoint, credential, header, cookie or private user path appears in
      the evidence document, the API response, the Web section or the tests.
- [ ] Anything shown as Active is still the exact immutable runtime snapshot; this Task changes no
      activation gate, no Active projection and no runtime schema marker.

## Technical Scope

Reuse the shipped planner composition, path-safety rules, naming engine, classification engine and
policy-resolution stack. Do not fork, re-implement, or "simplify" any of them.

```text
mediaflow/domain/organizer.py                               → shared composition + path safety
mediaflow/application/organizer.py                          → delegate to the shared helpers
mediaflow/domain/configuration_management.py                → destination evidence type + status
mediaflow/application/configuration_objects.py              → destination_preview + shared catalog
mediaflow/infrastructure/sqlite_configuration_management.py → evidence table + marker 8 → 9
mediaflow/interfaces/service_api.py                         → POST .../destination-preview
mediaflow/interfaces/operator_ui.py                         → guided destination preview mount
tests/*                                                     → falsifiable Web, service, API, parity
docs/*                                                      → CURRENT/TARGET and Phase gate records
```

- **Shared composition, not a second one.** Extract the destination composition and the three path
  predicates from `mediaflow/application/organizer.py` — `_safe_root` (line 288),
  `_unsafe_relative_path` (line 304), `_unsafe_filename` (line 314) and the join at lines 121-124 —
  into public, dependency-free helpers in `mediaflow/domain/organizer.py`, and have the application
  module delegate to them. The extraction must be behaviour-preserving for **all five** existing
  call sites (lines 91-97, 256, 261, 265, 1037-1038): identical accept/reject decisions, identical
  strings, identical `OrganizePlan` fields. `OrganizePlanner.plan` must keep composing
  `posixpath.join(classification.relative_path, *naming.directory_segments, naming.filename)` under
  `posixpath.join(root, ...)` with the same `ConflictType.INVALID_DESTINATION` /
  `PlanStatus.INVALID` outcome. Proof is the unmodified organizer, planner and executor test suites
  plus the parity test below — no organizer test may be edited to accommodate the move.
- **Shared resolver catalog, not a second one.** The RecognitionType → RecognitionTypePolicy catalog
  construction currently inline in `organize_authority`
  (`mediaflow/application/configuration_objects.py:935-989`) is needed again here. Extract it into
  one private helper used by both, keeping `organize_authority`'s observable behaviour and evidence
  byte-identical, including the dangling-organizePolicy substitution that yields
  `INVALID_POLICY_REFERENCE` (line 959). The Phase 22.6-C organize-authority tests must pass
  unmodified.
- `destination_preview(revision_id, *, expected_version, expected_digest, actor, recognition_type,
  sample)` mirrors `organize_authority` (`mediaflow/application/configuration_objects.py:897-1072`):
  Draft/Validated only, exact version+digest or a `ConfigurationVersionConflict` carrying
  `durable_state` and `next_action`, a bounded `recognition_type` (non-empty, ≤64 characters,
  NUL-free), and one current evidence row per revision.
- Policy selection comes from the resolver, never from operator-supplied policy IDs: resolve the
  RecognitionType, then use `resolved.naming_policy_id` and `resolved.classification_policy_id`.
  This is what makes the preview describe the same route runtime takes and is what preserves
  C-identity.
- The sample is one document validated against the union of `_NAMING_SAMPLE_FIELDS`
  (`mediaflow/application/configuration_objects.py:187-208`) and `_CLASSIFICATION_SAMPLE_FIELDS`
  (lines 245-257), then **projected** into each engine's allowed subset and passed through the
  existing `_naming_context` (line 628) and `_classification_context` (line 1120). Do not add a
  third sample validator: path mode stays exactly `{"path": ...}` for both engines, and the existing
  bounds, defaults and unknown-field rejections keep owning their fields. Reject an unknown field
  against the union with one bounded category.
- The naming and classification stages run through the production preview services exactly as the
  single-policy previews construct them — `NamingPreviewService(NamingPolicyRegistry(policies))`
  (line 538) and `ClassificationPreviewService(ClassificationPolicyRegistry(policies))` (line 813) —
  consuming `_canonical_objects(revision.document, section)`. Do not call
  `load_managed_runtime_configuration`, and do not construct Storage, Provider, Parser, Planner or
  Executor objects on this path.
- The MediaLibrary is resolved from this revision's `mediaLibraries` section by the
  `ClassificationResult.media_library_id`, reusing the resolution check already in
  `classification_preview` (lines 817-826). Its `rootPath` — the Storage-relative
  `mediaLibraries[].rootPath` (`config/strategy.example.json:45-48`) — enters the evidence for the
  first time in this Slice. `storages[].rootPath` and every other Storage field except the
  `storageId` label stay unread and undisplayed: the composed path is Storage-relative and must be
  labelled so.
- Failure handling follows the naming/classification precedent, not the organize-authority gap: the
  `except` arm must cover `PolicyResolutionError` (a `LookupError`,
  `mediaflow/domain/recognition.py:339`) **and** `ValueError`, which already subsumes `NamingError`
  (`mediaflow/domain/naming.py:42`) and `ClassificationError`
  (`mediaflow/domain/classification.py:26`). Because both engine errors are `ValueError` subclasses,
  the bounded category must be derived by checking the specific type first — exactly as
  `classification_preview` derives `error.code.value if isinstance(error, ClassificationError) else
  "invalid_input"` (`mediaflow/application/configuration_objects.py:872-875`) — so a policy-engine
  failure never degrades into a generic `invalid_input`. A loader-valid-but-managed-invalid document
  must therefore produce persisted FAILED evidence with a bounded category instead of a bare `400`.
  This specifies the new path only; it does not retroactively change `organize_authority`, which
  stays a recorded carried-forward P2.
- Evidence: add `DestinationPreviewEvidence` and `ConfigurationDestinationPreviewStatus` alongside
  the three existing evidence types (`mediaflow/domain/configuration_management.py:285-430`) with
  the same bounds, digest validation, size limit, `"sideEffects": "none"` and `"retrySafe": true`
  document keys, plus an explicit `"pathScope": "storage_relative"` key. Do not widen or repurpose
  an existing evidence type or table. Persist through a new additive `managed_destination_previews`
  table with a `(status, previewed_at)` index and a foreign key to
  `managed_configuration_revisions`, and bump `CONFIGURATION_SCHEMA_VERSION` from 8 to 9
  (`mediaflow/infrastructure/sqlite_configuration_management.py:38`). The runtime schema marker must
  stay 22.
- `revision_detail` gains `"destinationPreview": self._destination_preview_document(revision)`
  beside the three existing projections (`mediaflow/application/configuration_objects.py:366-368`),
  with the same current/stale computation.
- API: `POST /api/v1/configuration/revisions/{id}/destination-preview` requiring
  `MANAGE_CONFIGURATION`, accepting exactly `{expectedVersion, expectedDigest, recognitionType,
  sample}`, returning the evidence document, `503` when the service is absent, `400 invalid_request`
  for bounded validation failures and the existing conflict mapping for a stale revision — mirroring
  `mediaflow/interfaces/service_api.py:576-606`.
- Web: add `renderDestinationPreview(revision, guided)` and mount it inside the `if (guided) {`
  branch of `showConfigurationRevision`, after `renderOrganizeAuthority(data, guided);`
  (`mediaflow/interfaces/operator_ui.py:1043`) and before `detailContent.append(actions);` and the
  final `detail.hidden = false;` (line 1078). Follow the organize-authority section's structure:
  bounded `field(...)` rows, a stale warning, an `aria-label`-ed RecognitionType input and sample
  input, and the editable-only run control.
- Unsafe and unresolved outcomes must be visibly marked, never rendered as an ordinary empty value:
  an empty composed path must not be displayed as if it were a valid destination.

## Non-goals

- No destination existence, target-collision, duplicate-media, or attachment-collision detection,
  and no Storage capability **probing**: no Storage adapter is constructed, listed, stat-ed, read or
  written on this path. Required capabilities remain the declared set Phase 22.6-C already reports.
- No Storage mount prefix, `storages[].rootPath`, endpoint, absolute filesystem path, or credential
  in evidence, API, Web or tests. The composed path is Storage-relative in this Slice.
- No `OrganizePlanner` or `OrganizerExecutor` **behaviour** change: the only permitted planner
  change is the behaviour-preserving extraction of the composition and path predicates it already
  uses, with the existing tests unmodified as the proof. No conflict resolution, rollback, cleanup,
  attachment destination composition, plan creation, job, or execute authority.
- No combined activation evidence: merging naming, classification, organize-authority and
  destination evidence into a single activation-gate record stays deferred.
- No change to Draft/Validate/Activate semantics, the checked activation gate, the Active
  projection, the immutable runtime snapshot, or the runtime SQLite schema marker 22.
- No change to the naming, classification or organize-authority contracts, their evidence keys,
  their documents, or their tables beyond the shared-helper extraction described above.
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

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner and DryRun mutate nothing;
  this Task adds no execution path and grants no execute authority.
- Only OrganizerExecutor may mutate Storage. This Task computes a path; it never touches one.
- The managed answer and the runtime answer must be the same answer: the composed destination and
  its safety verdict come from the same code `OrganizePlanner.plan` uses, and a parity test proves
  it.
- Path safety is never weakened to make a preview succeed: absolute, traversal and invalid
  components stay rejected with the planner's existing verdict.
- No silent fallback: this preview reports where a file would go, never that an unsupported
  operation could be downgraded to reach it.
- RecognitionType C remains C even when its RecognitionTypePolicy references NamingPolicy A,
  ClassificationPolicy A and OrganizePolicy A; the existing regressions must stay green.
- Anything presented as Active remains the exact immutable snapshot consumed by runtime; this Task
  changes no activation gate, no Active projection and no runtime marker.
- Credentials, endpoints, Storage root paths, raw Provider responses, headers, cookies, exception
  text and private user paths must not enter Web, API, evidence, logs, tests or commits.
  `config/alist.json` is never read.
- No FFmpeg or FFprobe dependency, invocation, or media-stream inspection.

## Required Tests

1. Falsifiable Web proof, established in this Slice rather than deferred to a correction: with the
   destination preview mount removed from the guided branch of `showConfigurationRevision` the
   focused UI test must fail; with the mount moved after the final `detail.hidden = false;` it must
   fail; with the section's heading, RecognitionType input, sample input or run control detached
   from `detailContent` it must fail; unmodified it must pass. Record each run and restore the file
   before committing.
2. Planner parity, asserted against the real planner rather than a re-implementation: for a set of
   MediaLibrary roots, `ClassificationResult.relative_path` values,
   `NamingResult.directory_segments` and filenames — safe and unsafe — the shared helper's composed
   path and safety verdict equal `OrganizePlanner.plan`'s `media_library_root`,
   `relative_destination`, `target` and `INVALID_DESTINATION` / `PlanStatus.INVALID` outcome.
   Include an absolute root, a traversal `relativePath`, a traversal directory segment, a
   `/`-containing filename and a `..` filename.
3. Extraction neutrality: the organizer, planner, executor, Strategy Test and DryRun test suites
   pass **unmodified** after the extraction, and the Phase 22.6-C organize-authority tests pass
   unmodified after the resolver-catalog extraction. No existing assertion may be edited, relaxed or
   deleted.
4. Successful preview through a real repository-backed Draft: the resolved RecognitionType,
   RecognitionTypePolicy ID, applied NamingPolicy and ClassificationPolicy IDs, MediaLibrary ID and
   rootPath, classification relative path, naming directory segments, filename, root-relative
   destination, composed Storage-relative destination, `pathScope`, `sideEffects` and `retrySafe`
   are all asserted; path-mode and synthetic-field samples both work.
5. Failure behaviour, one bounded distinct category each: invalid sample (unknown field against the
   union, `path` combined with synthetic fields, non-object body), missing / duplicated / disabled /
   dangling RecognitionTypePolicy mapping returning the production `PolicyResolutionErrorCode`, a
   naming failure returning the production `NamingError` code, a classification failure returning
   the production `ClassificationError` code, an unresolved MediaLibrary, and each unsafe
   composition. Every case asserts the revision version, digest, document, and the stored naming,
   classification and organize-authority evidence rows unchanged.
6. C-identity: RecognitionType C mapped to NamingPolicy A and ClassificationPolicy A previews as
   RecognitionType C, and the composed path is the one those A policies produce.
7. Exact-revision semantics: a stale `expectedVersion` / `expectedDigest` is refused with the
   current version and digest while prior evidence is preserved byte-for-byte; an Active revision is
   refused with `ConfigurationVersionConflict` and no evidence stored; evidence is current only for
   its exact revision version and digest and becomes stale after a further edit.
8. Zero side effects: the preview constructs no Storage adapter, Provider client, Planner or
   Executor, writes no file, emits no Storage `rootPath` or private path into evidence, and leaves
   the Draft document, version and digest unchanged — asserted, not assumed.
9. Compatibility and regression: a revision document that omits the optional `organizePolicies` or
   `mediaLibraries` section still loads and renders; a configuration database created at marker 8
   opens and upgrades to marker 9 with its existing revisions and its naming, classification and
   organize-authority evidence intact; the runtime schema marker stays 22; the authenticated API
   returns `400 invalid_request`, `503` and the conflict mapping as specified; and the Phase
   22.3/22.4/22.5, 22.6-A/B/C configuration, Strategy Test, MetadataPolicy, correction and
   continuation regressions, the operator-UI tests, the RecognitionType C regressions and the
   complete offline suite all pass with no weakened or removed assertion.

## Validation

Run the focused destination-preview, organize configuration/authority, classification, naming,
planner, organizer, executor and operator UI tests, the Phase 22.3/22.4/22.5 configuration and
continuation regressions, the RecognitionType C regressions, and the complete offline suite. Run
Ruff lint/format, `compileall`, `pip check`, both example configuration validations, wheel build
plus the isolated installed-wheel smoke test (reporting the runtime schema marker), documentation
local-link validation, `git diff --check`, the FFmpeg/FFprobe production audit, the
business-filesystem mutation audit, and the private configuration checks. Report the deliberate
mount-removal falsification runs explicitly, including restoration and a clean `git status`. Report
the extraction-neutrality evidence explicitly: which existing test files were left untouched and
that they pass. No real Storage, Provider, or production data is used, and `config/alist.json` is
never read.

## Documentation

Update `docs/progress.md` with this Slice's implementation evidence beneath the closed Phase 22.6-C
records, and `docs/roadmap.md` with the resulting Phase 22.6-D gate row and 当前节点. Update the CURRENT
claims in `docs/architecture.md`, `docs/requirements.md` and `docs/product-experience.md` only where
the composed destination preview and the shared planner composition actually change them — including
the fact that the composition and path-safety rules now have one owner. Keep destination existence /
conflict / capability prechecks, the Storage mount prefix and absolute destination display, combined
activation evidence, Provider switching, generic Task resume and broader per-item recovery
explicitly TARGET. Never rewrite historical Phase evidence, including the preserved Phase 22.5-E and
Phase 22.6-A `FIX REQUIRED` records and their rejected SHAs.

## Closure Checklist

- [x] Workspace preflight records worktree, `.git`, index, sandbox, and approval mode.
- [x] Capability mode is classified as Git-writable / Full Access or Git-read-only /
      workspace-write.
- [x] The preceding dependent Slice is `PASS / CLOSED` with its commit SHA recorded
      (`47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa`, Phase 22.6-C).
- [x] The preserved rejected checkpoints `90ce13a6c6c39912dd389f71a1189314ff24eb5d` and
      `08dfd4f921728755209b6d52347d28f221121c47` are not amended, squashed, or rewritten.
- [x] Implementation and all required focused/full quality gates pass with actual evidence,
      including the Web mount-removal falsifications, the planner parity test, and the unmodified
      existing suites.
- [x] `git status` and the commit manifest contain every required file and no unrelated/private
      file.
- [x] Private runtime configuration remains ignored/untracked; no secret is staged or committed.
- [ ] A coherent, buildable commit has been created: `Commit SHA: ________________________________`.
- [ ] High Review inspected that exact SHA and returned: `High Audit: ___________________________`.
- [ ] `docs/progress.md` records Status / Commit SHA / High Audit.
- [x] `docs/roadmap.md` records the resulting Phase gate.
- [x] The next Slice has not started before every preceding gate is complete.
- [x] Required major-closure/integration push is recorded, or push is explicitly not required.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- the exact falsification evidence for the Web mount and for the section's inputs and run control,
  including the failing output with each removal and the pass after restoration;
- the planner parity evidence: the safe and unsafe cases compared, and the assertion that the
  composed path and safety verdict came from `OrganizePlanner.plan` itself;
- the extraction-neutrality evidence: which existing organizer/planner/executor and Phase 22.6-C
  test files were left byte-unchanged, and that they pass;
- what the service and API tests prove about the unchanged Draft and the preserved naming,
  classification and organize-authority evidence rows, with the bounded categories actually
  asserted;
- the preview outcomes proven: successful composition with every contribution attributed, each
  failure class with its production error code, C-identity preservation, and stale-revision refusal
  with preserved prior evidence;
- confirmation that no Storage adapter, Provider client, Planner or Executor is constructed on the
  preview path, that no Storage `rootPath` or private path enters evidence, and that the runtime
  schema marker, activation gate and Active projection are unchanged;
- the configuration schema marker transition 8 → 9 and its verified backward compatibility;
- CURRENT versus remaining TARGET for the Phase 22.6 journey and the exact next journey gap
  (expected: destination conflict / capability / existence prechecks against a real Storage, then
  combined activation evidence).
