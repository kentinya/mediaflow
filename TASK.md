# Phase 22.6-B — Managed ClassificationPolicy Configuration and Exact-Revision Offline Classification Preview

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: 30af69ac82b30f8a45ad66afbd3c9747597c8fe7
  (Phase 22.6-A PASS / CLOSED — 2026-08-28, includes the 22.6-A-F1 correction)
Preserved rejected checkpoint: 90ce13a6c6c39912dd389f71a1189314ff24eb5d
  (Phase 22.6-A FIX REQUIRED — 2026-08-27; never amended, squashed or rewritten)
Push gate: SATISFIED — 90ce13a, 81baec4, 30af69a and the closure record be38631 were pushed to
  origin/main on 2026-08-28 under explicit operator authorization; no accepted checkpoint is
  unpushed. This Slice's own checkpoint push follows the same rule at its closure.
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Slice scope: managed ClassificationPolicy editing + exact-revision offline classification preview
```

## User Problem

Phase 22.6-A made NamingPolicy objects editable inside a managed Draft revision and previewable
against that exact revision. ClassificationPolicy — the object that decides **which MediaLibrary**
and **which relative path** a media item lands in — is still outside the managed journey:

- `ConfigurationObjectService._SECTIONS` maps eight editable kinds
  (`mediaflow/application/configuration_objects.py:94-103`) and `classification_policy` is not one
  of them, so `mutate` rejects it with "this configuration object kind is not editable in the
  current slice" (`mediaflow/application/configuration_objects.py:2031-2035`).
- `revision_detail` projects eight object sections
  (`mediaflow/application/configuration_objects.py:247-265`) and the Web guided editor mounts eight
  lists (`mediaflow/interfaces/operator_ui.py:868-875`); neither includes `classificationPolicies`.
- `_references_for` blocks deleting a MediaLibrary that a classification rule points at
  (`mediaflow/application/configuration_objects.py:2588-2623`), but there is **no** branch for
  ClassificationPolicy itself, so a policy referenced by
  `recognitionTypePolicies[].classificationPolicy` has neither editing nor deletion protection.

The only way to change a classification rule today is a whole-document JSON import: no per-object
bounded validation, no reference evidence, no delete blocking, no Before/After guided audit.

Second, the operator cannot answer the question classification exists to answer — "given this
recognized item, which MediaLibrary and which relative path will this policy choose, and why?" —
without running a real Task. `ClassificationPreviewService`
(`mediaflow/application/classification.py:88-98`) already computes exactly that deterministically,
with zero mutation and no Storage or Provider construction, but no managed-configuration entry
point consumes it, so the decision stays unexplained until execution time.

## User Journey

```text
Configuration → open a Draft revision → see ClassificationPolicy objects, their rules, and which
   RecognitionTypePolicies reference them
→ create / edit / copy / delete one ClassificationPolicy (delete blocked while referenced, naming
   the referencing RecognitionTypePolicy and field)
→ submit an invalid rule (unknown condition field, unknown result field, unsafe or absolute
   relative path, missing MediaLibrary reference, duplicate rule ID, empty rule set) and be told
   which bounded category failed, with the Draft untouched
→ correct it → run the exact-revision offline classification preview on one sample item
→ read the chosen MediaLibrary, the relative path, the matched rule, the evidence for why it
   matched, and the explicit unclassified outcome when nothing matches
→ Validate the revision
```

Entry point, permission model and revision authority are the existing managed ones: the same
Configuration revision detail view, the same `MANAGE_CONFIGURATION` permission, the same
Draft/Validated editability, the same optimistic `expectedVersion` / `expectedDigest` contract.

## User-visible Outcome

- The managed revision detail view lists `ClassificationPolicies (n)` with, per policy, its ID,
  name, enabled state, priority, rule count, a bounded per-rule summary
  (`rule ID - priority - mediaLibraryId - relative path`), and existing reference evidence.
- Add / Edit / Copy / Delete are available on a Draft or Validated revision through the same
  bounded JSON object editor used by MetadataPolicy and NamingPolicy; Delete is refused while a
  RecognitionTypePolicy references the policy, naming section, object and field.
- An invalid ClassificationPolicy is refused with one bounded, secret-free category that names the
  offending field or rule where it is known, and the Draft document, version, digest and any prior
  preview evidence are unchanged.
- An offline classification preview bound to the exact revision reports: applied policy ID,
  RecognitionType, status (`classified` / `unclassified`), matched rule ID and name, chosen
  `mediaLibraryId` with whether that MediaLibrary resolves inside the same revision, the relative
  path, the match evidence (which condition matched with which value), and bounded warnings.
- Preview evidence carries the same current/stale semantics as the naming preview: it is presented
  as current only for the exact revision ID, version and digest it was produced from, and a stale
  row is labelled stale with the explicit rerun action.
- No Storage adapter, Provider client, media file or execution authority is involved at any point.

## Failure and Recovery

| Failure class | Visible state | Durable state / side effects | Retry safe | Recovery | If recovery also fails |
|---|---|---|---|---|---|
| Invalid ClassificationPolicy submitted (unknown condition/result field, unsafe or absolute path, duplicate rule ID, missing/oversized `mediaLibraryId`, empty rules) | Bounded distinct category naming the offending rule or field; API `400 invalid_request` | Draft document, version, digest and stored preview evidence unchanged; nothing written | Yes | Correct the reported rule or field and resubmit | Revision stays Draft and editable; a known-good policy can be copied as a starting point |
| Delete refused because referenced | Refusal naming `recognitionTypePolicies:<id>.classificationPolicy` with the reference total | No document change; the policy still exists | Yes | Repoint or delete the referencing RecognitionTypePolicy first, then delete the policy | The policy remains intact and the revision stays consistent |
| Stale edit or stale preview (version/digest moved) | Conflict stating the current version and digest with the reload action | Current Draft and prior preview evidence preserved | Yes | Reload the revision, then reapply the edit or rerun the preview | The Draft is never partially applied; the operator re-reads authoritative state |
| Preview refers to a MediaLibrary that does not exist in this revision | Completed preview marking the reference unresolved, plus a bounded warning naming the ID | Preview evidence stored as completed-with-warning; no document change | Yes | Add or correct the MediaLibrary in the same Draft, then rerun the preview | Draft validation still refuses activation, so an unresolved target cannot become Active |
| No rule matches the sample | `unclassified` status with the reason and the explicit next action | Preview evidence stored as completed with `unclassified` status | Yes | Adjust the rule conditions or the sample, then rerun the preview | Evidence stays inspectable and attributed to its exact revision |
| Preview requested on a non-editable revision | Refusal stating a Draft or Validated revision is required | No evidence written | Yes | Open or create a Draft revision and rerun | Active configuration is untouched and remains the runtime snapshot |

Retry alone is never the recovery text: every row states what is durable, what is safe to repeat,
and the single explicit action that continues.

Batch per-item independence does not apply: this Task edits one configuration object per request
and previews one sample per request.

## UX Acceptance Criteria

- [ ] The revision detail view lists ClassificationPolicies with rule summaries and reference
      evidence, and the list is reachable: a focused test fails if
      `renderGuidedObjectList(data, guided, 'classificationPolicies', 'ClassificationPolicies')`
      leaves the guided branch of `showConfigurationRevision`.
- [ ] The classification preview section is reachable: a focused test fails if its mount call leaves
      the guided branch, if the mount moves after the final `detail.hidden = false;`, or if the
      section's policy selector, sample input and run control stop being appended to
      `detailContent` inside the rendering function's own body.
- [ ] Both proofs are brace-matched and body-scoped, following the
      `_js_function_body(script, name)` pattern already used by
      `tests/test_operator_ui.py` and `tests/test_metadata_correction_continuation.py`; a
      defined-but-unmounted section must not pass.
- [ ] Creating, editing, copying and deleting one ClassificationPolicy through
      `ConfigurationObjectService.mutate` produces a new Draft version with the guided
      Before/After audit action recorded, exactly as the NamingPolicy slice does.
- [ ] Deleting a ClassificationPolicy referenced by `recognitionTypePolicies[].classificationPolicy`
      is refused with reference evidence naming section, object ID and field, and the document is
      unchanged; `references()` exposes the same evidence under the key
      `classification_policy:<id>`, which is the key the Web list looks up.
- [ ] Each invalid case — unknown condition field, unknown result field, absolute or traversing
      relative path, duplicate rule ID within a policy, missing or oversized `mediaLibraryId`,
      non-object rule, empty rule set — is refused through the public service with a bounded
      distinct category, and the revision version, digest, `classificationPolicies` content and
      stored preview evidence are asserted unchanged.
- [ ] The same rejections are asserted through the authenticated API as `400 invalid_request` with
      bounded, secret-free messages.
- [ ] A successful exact-revision preview returns the applied policy, matched rule, chosen
      `mediaLibraryId`, MediaLibrary resolution flag, relative path and match evidence; a
      no-rule-matched sample returns `unclassified` with its reason and next action; a preview whose
      rule points at an absent MediaLibrary completes with the unresolved-reference warning.
- [ ] A preview submitted with a stale `expectedVersion` or `expectedDigest` is refused with the
      current version and digest, and the previously stored evidence is preserved unchanged.
- [ ] Preview evidence is presented as current only for its exact revision ID, version and digest;
      after any further edit the same evidence is presented as stale with the rerun action.
- [ ] Anything shown as Active is still the exact immutable runtime snapshot; this Task changes no
      activation gate, no Active projection and no runtime schema marker.

## Technical Scope

Reuse the shipped classification stack; do not fork or reimplement matching, path safety or
priority ordering.

```text
mediaflow/domain/configuration_management.py        → classification preview evidence type + status
mediaflow/application/configuration_objects.py      → section, normalization, references, preview
mediaflow/infrastructure/sqlite_configuration_management.py → evidence table + schema marker 6 → 7
mediaflow/interfaces/service_api.py                 → POST .../classification-preview
mediaflow/interfaces/operator_ui.py                 → guided list mount + preview section mount
tests/*                                             → falsifiable Web, service, API, regression
docs/*                                              → CURRENT/TARGET and Phase gate records
```

- `_SECTIONS` gains `ConfigurationObjectKind.CLASSIFICATION_POLICY: "classificationPolicies"`, and
  `revision_detail` projects the section the same optional way `namingPolicies` is projected
  (absent section renders as an empty list, never as an error).
- `_normalize` gains a CLASSIFICATION_POLICY branch that accepts exactly the canonical loader shape
  in `mediaflow/infrastructure/strategy_user_configuration.py:160-230` and
  `config/strategy.example.json`: policy `{id, name, description?, enabled?, priority?, rules[]}`
  and nested rule `{id, name?, priority?, enabled?, conditions{mediaType|mediaTypes, genres,
  countries, languages, yearMin, yearMax, canonicalYear, keywords}, result{mediaLibraryId, library,
  path[]|path, category?, subcategory?}}`. Unknown fields, unbounded strings, non-object rules,
  duplicate rule IDs, absolute/traversing/backslash paths and empty rule sets are rejected with
  bounded messages that name the rule or field. Path and rule safety must come from the domain
  (`ClassificationRule` / `ClassificationPolicy` construction and `ClassificationError`), not from a
  second hand-written validator.
- Cross-object existence stays where the repository already puts it: `mediaLibraryId` is bounded and
  required at save time, while *resolution* against `mediaLibraries` is reported by the preview and
  enforced by Draft validation — matching the existing "references are checked when the Draft is
  validated" behaviour for recognition objects. Do not introduce a new save-time reference rule.
- `_references_for` gains a CLASSIFICATION_POLICY branch over
  `recognitionTypePolicies[].classificationPolicy`, mirroring the NAMING_POLICY branch
  (`mediaflow/application/configuration_objects.py:2671-2688`). The existing MEDIA_LIBRARY branch
  must keep working unchanged for documents with and without `classificationPolicies`.
- `classification_preview(revision_id, *, expected_version, expected_digest, actor, policy_id,
  sample)` mirrors `naming_preview` (`mediaflow/application/configuration_objects.py:399-506`):
  Draft/Validated only, exact version+digest or a conflict carrying `durable_state` and
  `next_action`, a bounded `_classification_sample`/`_classification_context` builder with an
  explicit allowed field set, `ClassificationPolicyRegistry` + `ClassificationPreviewService` from
  the revision document only, and one current evidence row per revision.
- Sample fields are bounded and limited to what `_matches`
  (`mediaflow/application/classification.py:128-160`) actually consumes: `path`, `title`,
  `originalTitle`, `mediaType`, `recognitionType`, `year`, `genres`, `countries`, `languages`,
  `keywords`, `overview`, plus the naming-side identity fields only if genuinely required. Reject
  unknown sample fields exactly as the naming sample does.
- Evidence: add `ClassificationPreviewEvidence` and its status enum alongside
  `NamingPreviewEvidence` (`mediaflow/domain/configuration_management.py:286-360`) with the same
  bounds, digest validation and size limit; do not widen or repurpose the naming evidence type or
  its `managed_naming_previews` table. Persist through a new additive
  `managed_classification_previews` table and bump `CONFIGURATION_SCHEMA_VERSION` from 6 to 7; the
  runtime schema marker must stay 22.
- API: `POST /api/v1/configuration/revisions/{id}/classification-preview` requiring
  `MANAGE_CONFIGURATION`, accepting exactly `{expectedVersion, expectedDigest, policyId, sample}`,
  returning the evidence document, `400 invalid_request` for bounded validation failures and the
  existing conflict mapping for a stale revision — mirroring
  `mediaflow/interfaces/service_api.py:495-531`.
- Web: add the guided list mount and a `renderClassificationPreview(data, guided)` mount inside the
  `if (guided) {` branch of `showConfigurationRevision`, before the final `detail.hidden = false;`;
  add `classificationPolicies` to the reference-kind map, the singular label map and the
  guided-JSON editor set (`mediaflow/interfaces/operator_ui.py:299-379`) so reference evidence
  resolves under `classification_policy:<id>` and the editor opens as a bounded JSON object.
- Add the same Copy affordance the NamingPolicy list offers, since duplicating a working policy is
  the documented recovery path.

## Non-goals

- No OrganizePolicy editing and no OrganizePolicy preview.
- No composed final destination path: `MediaLibrary.RootPath + relativePath + naming
  directory/filename` composition, and any display of a MediaLibrary `rootPath` inside preview
  evidence, are deferred to the next Slice.
- No target-existence, conflict-strategy, capability or overwrite precheck, and no Storage adapter
  construction, listing, stat or write of any kind.
- No change to `ClassificationEngine` matching, priority ordering, evidence wording, path
  sanitization, `ClassificationErrorCode` values, or `select_configured_rule`.
- No change to Draft/Validate/Activate semantics, the checked activation gate, the Active
  projection, the immutable runtime snapshot, or the runtime SQLite schema marker 22.
- No change to the naming preview contract, its evidence keys, or its table.
- No Provider, Metadata, scan, Task, Job, queue or media work; no Provider switching, generic Task
  resume, per-item Processing Checkpoint recovery, or manual organize journey.
- No new frontend framework, unrelated Web refactor, or JS test runner in CI.
- No rewrite of historical Phase evidence, including the preserved Phase 22.5-E and Phase 22.6-A
  `FIX REQUIRED` records and their rejected SHAs.
- Carried-forward P2 items stay out of scope and must not be silently fixed here: naming engine
  separator/conversion message wording, legacy naming template aliases, and first-object seeding
  into a document that omits an optional section.

## Safety and Architecture Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner and DryRun mutate nothing;
  this Task adds no execution path and grants no execute authority.
- Only OrganizerExecutor may mutate Storage. Classification still only decides MediaLibrary and
  relative path; it never touches files.
- RecognitionType C remains C even when its RecognitionTypePolicy references ClassificationPolicy A
  and NamingPolicy A; the existing regression must stay green and must cover the newly editable
  section.
- Anything presented as Active remains the exact immutable snapshot consumed by runtime.
- Credentials, endpoints, raw Provider responses, headers, cookies, exception text and private paths
  must not enter Web, API, evidence, logs, tests or commits. `config/alist.json` is never read.
- No FFmpeg or FFprobe dependency, invocation, or media-stream inspection.

## Required Tests

1. Falsifiable Web proof, established in this Slice rather than deferred to a correction: with the
   classification preview mount removed from `showConfigurationRevision` the focused UI test must
   fail; with the `classificationPolicies` list mount removed it must fail; with the preview mount
   moved after the final `detail.hidden = false;` it must fail; with the section's controls or
   heading detached from `detailContent` it must fail; unmodified it must pass. Record each run and
   restore the file before committing.
2. Guided CRUD through `ConfigurationObjectService.mutate` on a real repository-backed Draft:
   create, update, copy-as-new and delete one ClassificationPolicy, asserting the new version, the
   guided audit action, and the resulting document section.
3. Delete blocking: a policy referenced by `recognitionTypePolicies[].classificationPolicy` cannot
   be deleted; the refusal carries reference evidence naming section, object and field; the document
   is unchanged; `references()` exposes the evidence under `classification_policy:<id>`.
4. Service-boundary invalid input: unknown condition field, unknown result field, absolute or
   traversing path, duplicate rule ID, missing/oversized `mediaLibraryId`, non-object rule and empty
   rule set each yield a bounded distinct category, with version, digest, section content and stored
   preview evidence asserted unchanged; the authenticated API returns `400 invalid_request` with a
   bounded, secret-free message for the same cases.
5. Preview behaviour: a matching sample returns the expected `mediaLibraryId`, relative path,
   matched rule and match evidence; a non-matching sample returns `unclassified` with its reason and
   next action; a rule pointing at an absent MediaLibrary completes with the unresolved-reference
   warning; a stale `expectedVersion`/`expectedDigest` is refused with the current version and
   digest while prior evidence is preserved; evidence is current only for its exact revision
   version and digest and becomes stale after a further edit.
6. Zero side effects: the preview constructs no Storage adapter and no Provider client, writes no
   file, and leaves the Draft document, version and digest unchanged — asserted, not assumed.
7. Compatibility: a revision document that omits the optional `classificationPolicies` section still
   loads, renders and produces reference evidence; a configuration database created at marker 6
   opens and upgrades to marker 7 with its existing revisions and naming preview evidence intact;
   the runtime schema marker stays 22.
8. Regression: Phase 22.6-A naming configuration and operator-UI tests, Phase 22.3/22.4/22.5
   configuration, Strategy Test, MetadataPolicy, correction and continuation regressions, the
   existing classification and classification-review tests, the RecognitionType C regression, and
   the complete offline suite all pass with no weakened or removed assertion.

## Validation

Run the focused classification configuration/preview, naming configuration and operator UI tests,
the Phase 22.3/22.4/22.5 configuration and continuation regressions, the classification and
classification-review tests, the RecognitionType C regression, and the complete offline suite. Run
Ruff lint/format, `compileall`, `pip check`, both example configuration validations, wheel build plus
the isolated installed-wheel smoke test (reporting the runtime schema marker), documentation
local-link validation, `git diff --check`, the FFmpeg/FFprobe production audit, the
business-filesystem mutation audit, and the private configuration checks. Report the deliberate
mount-removal falsification runs explicitly, including restoration and a clean `git status`. No
real Storage, Provider, or production data is used, and `config/alist.json` is never read.

## Documentation

Update `docs/progress.md` with this Slice's implementation evidence beneath the closed Phase 22.6-A
records, and `docs/roadmap.md` with the resulting Phase 22.6-B gate row and 当前节点. Update the
CURRENT claims in `docs/architecture.md`, `docs/requirements.md` and `docs/product-experience.md`
only where managed ClassificationPolicy editing and offline classification preview actually change
them. Keep OrganizePolicy editing, composed destination-path preview, conflict/capability/existence
prechecks, combined activation evidence, Provider switching, generic Task resume and broader
per-item recovery explicitly TARGET. Never rewrite historical Phase evidence, including the
preserved Phase 22.5-E and Phase 22.6-A `FIX REQUIRED` records and their rejected SHAs.

## Closure Checklist

- [x] Workspace preflight records worktree, `.git`, index, sandbox, and approval mode.
- [x] Capability mode is classified as Git-writable / Full Access or Git-read-only / workspace-write.
- [x] The preceding dependent Slice is `PASS / CLOSED` with its commit SHA recorded
      (`30af69ac82b30f8a45ad66afbd3c9747597c8fe7`, Phase 22.6-A).
- [x] The preserved Phase 22.6-A rejected checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` is
      not amended, squashed, or rewritten.
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

- the exact falsification evidence for both Web mounts and for the preview section's controls,
  including the failing output with each mount removed and the pass after restoration;
- what the service and API tests prove about the unchanged Draft, absent preview evidence, and
  reference-blocked deletion, with the bounded categories actually asserted;
- the preview outcomes proven: classified, unclassified, unresolved MediaLibrary reference, and
  stale-revision refusal with preserved prior evidence;
- confirmation that no Storage adapter or Provider client is constructed on the preview path, and
  that the runtime schema marker, activation gate and Active projection are unchanged;
- the configuration schema marker transition 6 → 7 and its verified backward compatibility;
- CURRENT versus remaining TARGET for the Phase 22.6 journey and the exact next journey gap
  (expected: OrganizePolicy editing plus composed destination-path preview and its prechecks).
