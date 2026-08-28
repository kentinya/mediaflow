# Phase 22.6-A-F1 — Falsifiable Web Reachability and Service-Boundary Validation Evidence for Managed NamingPolicy

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Rejected checkpoint under correction: 90ce13a6c6c39912dd389f71a1189314ff24eb5d
  (Phase 22.6-A FIX REQUIRED — 2026-08-27; preserved, never amended, squashed or rewritten)
Preceding closed checkpoint: dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62
  (Phase 22.5-E and Phase 22.5 PASS / CLOSED — 2026-08-27)
Push gate: SATISFIED — dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62 is contained in origin/main
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
Correction scope: evidence only — tests and documentation, no product behaviour change
```

## User Problem

The Phase 22.6-A checkpoint ships a working managed NamingPolicy journey, but nothing proves the Web
half of it stays reachable. Deleting the single `renderNamingPreview(data, guided);` mount line from
`showConfigurationRevision` in `mediaflow/interfaces/operator_ui.py` leaves the complete offline
suite green — 810 tests, 0 failures — and `renderNamingPreview` appears in no test file. The existing
assertions only match substrings that live inside the function definition, so a defined-but-unmounted
section is indistinguishable from a working one.

That is exactly the defect class that made the Phase 22.5-E checkpoint
`08dfd4f921728755209b6d52347d28f221121c47` `FIX REQUIRED`, and whose 22.5-E-F1 correction established
the `_js_function_body` brace-matched proof. The operator consequence is unchanged today, but the
next edit to that file can silently remove the whole naming preview journey with every gate green.

Separately, `test_invalid_templates_are_rejected_without_changing_draft` calls the private
`ConfigurationObjectService._normalize` classmethod, asserts only bare `ValueError`, and never builds
a revision. The durable state promised for an invalid template — "Draft unchanged; no preview
evidence written" — and the journey step "correct an invalid template, and preview successfully" are
therefore unproven at the service and API boundary the operator actually uses.

## User Journey

Unchanged from Phase 22.6-A; this Task only makes the already-shipped journey provable:

```text
Configuration → open a Draft revision → see NamingPolicy objects and their references
→ create / edit / copy / delete one NamingPolicy → submit an invalid template and be told which
   bounded category failed, with the Draft untouched → correct it → run the exact-revision offline
   naming preview → read directory, filename, sanitization and missing-variable decisions
→ Validate the revision
```

No new entry point, request, permission, field, evidence key, or state is introduced.

## User-visible Outcome

The operator-visible behaviour is identical to `90ce13a6c6c39912dd389f71a1189314ff24eb5d`. What
changes is durable protection of that behaviour:

- the NamingPolicy editor list and the offline naming preview section are provably mounted into the
  managed revision detail view, so removing either mount fails the suite;
- an invalid template submitted through the Application service is provably rejected with a bounded
  distinct category while the Draft revision, its version and its preview evidence stay unchanged;
- correcting that template and previewing successfully is proven end to end through the service and
  the authenticated API rather than through a private helper.

## Failure and Recovery

| Failure class | Visible state | Durable state / side effects | Retry safe | Recovery | If recovery also fails |
|---|---|---|---|---|---|
| Web mount regression (a future edit unmounts the preview or the policy list) | Focused UI test fails naming the missing mount and its caller | No product change; nothing shipped unmounted | Yes | Restore the mount call in `showConfigurationRevision` and rerun the focused UI test | The suite keeps failing; the section cannot ship unreachable |
| Invalid template submitted through the service or API | Bounded validation category with the offending field where the field is known, plus 400 `invalid_request` on the API | Draft document, version and prior preview evidence unchanged; no preview evidence written | Yes | Correct the reported template field and resubmit, then rerun the preview | Revision stays Draft and editable; a known-good policy can be copied |
| Preview rerun after correction | Completed evidence bound to the exact current revision version and digest | One current evidence row per revision; prior failed evidence replaced by the current one | Yes | Rerun the preview against the reloaded revision | Evidence remains inspectable and clearly attributed to its revision |

Retry alone is never the recovery text: each row states what is durable, what is safe to repeat, and
the single explicit action that continues.

## UX Acceptance Criteria

- [ ] A focused test fails if `renderNamingPreview(data, guided);` is removed from
      `showConfigurationRevision`, and fails if
      `renderGuidedObjectList(data, guided, 'namingPolicies', 'NamingPolicies')` is removed.
- [ ] A focused test fails if `renderNamingPreview` stops appending its section to `detailContent`,
      or if its policy selector, sample input and `Run offline naming preview` control leave that
      function body.
- [ ] The preview mount is asserted to happen inside the guided branch, before the revision detail
      becomes visible, so the section cannot be mounted after the view is presented.
- [ ] Submitting an invalid template through `ConfigurationObjectService.mutate` on a real Draft
      revision yields a bounded distinct category, and the revision version, `namingPolicies`
      content and stored preview evidence are asserted unchanged.
- [ ] The same rejection is asserted through the authenticated API as `400 invalid_request` with a
      bounded, secret-free message.
- [ ] After correcting the template, the same test previews successfully against the exact revision
      and reads the rendered directory and filename.
- [ ] No product behaviour, API contract, evidence key, schema marker, or activation semantic
      changes in this Task.

Batch per-item independence does not apply: this Task edits one configuration object per request and
previews one sample per request.

## Technical Scope

Evidence only, reusing the proof pattern the repository already established:

```text
tests/test_operator_ui.py        → falsifiable brace-matched mount proof for the naming section
tests/test_configuration_naming.py → service/API invalid-template rejection + unchanged-Draft proof
docs/*                            → correction record and accurate CURRENT claims
```

- Reuse the `_js_function_body(script, name)` brace-matching helper pattern from
  `tests/test_metadata_correction_continuation.py` (line ~1155). Add it where needed rather than
  importing across unrelated test modules, matching how that file introduced it.
- Scope the existing naming UI substring assertions to the correct function bodies:
  `showConfigurationRevision` must contain both mount calls; `renderNamingPreview` must contain the
  `detailContent.append(...)` mounts, the `/naming-preview` POST with `expectedVersion` and
  `expectedDigest`, and the operator controls.
- Extend `test_invalid_templates_are_rejected_without_changing_draft` (or add one focused test) to
  drive `ConfigurationObjectService.mutate` and the authenticated API on a real Draft revision for
  at least the unknown-variable, path-separator and empty-template cases, asserting the bounded
  category, unchanged version/document, absent preview evidence, then a successful preview after
  correction.
- Keep the private-helper cases if they still add value, but the promised durable state must be
  proven through the public service and API boundary.
- No production source file is expected to change. If making the mount provably reachable requires a
  production change, keep it to the minimal mount or ordering fix, and report it explicitly.

## Non-goals

- No ClassificationPolicy or OrganizePolicy editing, and no MediaLibrary target resolution preview.
- No new naming field, alias, template variable, evidence key, or API parameter.
- No change to the reused rendering, sanitization, validation, or missing-variable behaviour.
- No change to Draft/Validate/Activate semantics, the checked activation gate, the immutable runtime
  snapshot, or the SQLite schema markers.
- No Provider, Metadata, scan, Task, Job, queue, or media work; no Storage adapter construction.
- No frontend framework, unrelated Web refactor, or JS test runner in CI.
- No rewrite of the Phase 22.6-A implementation-evidence record or the rejected SHA.
- No improvement of the reused engine's separator/traversal message wording, no legacy template
  aliases, and no first-object seeding for an absent optional section — all recorded as later work.

## Safety and Architecture Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner and DryRun mutate nothing;
  this Task adds no new execution path at all.
- Only OrganizerExecutor may mutate Storage; this Task grants no execute authority.
- Naming still only computes target directory and filename.
- RecognitionType C remains C even when its RecognitionTypePolicy references NamingPolicy A.
- Anything shown as Active remains the exact immutable snapshot consumed by runtime.
- Credentials, endpoints, raw Provider responses, headers, cookies, exception text and private paths
  must not enter Web, API, evidence, logs, tests or commits. `config/alist.json` is never read.

## Required Tests

1. Falsifiable Web proof: with `renderNamingPreview(data, guided);` deleted from
   `showConfigurationRevision`, the focused UI test must fail; with the mount restored it must pass.
   Record both runs as evidence, and restore the file before committing.
2. The same falsification must hold for the `namingPolicies` guided list mount.
3. Body-scoped proof: the preview controls and the `/naming-preview` request with `expectedVersion`
   and `expectedDigest` are asserted inside `renderNamingPreview`, and the mount is asserted to
   precede the revision detail becoming visible.
4. Service-boundary invalid template: `mutate` rejects unknown variable, path separator and empty
   template with bounded distinct categories; the revision version, `namingPolicies` content and
   stored preview evidence are unchanged; the authenticated API returns `400 invalid_request`.
5. Correction path: after fixing the template the same test creates the policy and previews
   successfully against the exact revision, reading the rendered directory and filename.
6. Regression: the Phase 22.6-A naming tests, Phase 22.3/22.4/22.5 configuration, Strategy Test,
   MetadataPolicy, correction and continuation regressions, the RecognitionType C regression, and the
   complete offline suite all pass with no weakened or removed assertion.

## Validation

Run the focused Naming configuration/preview and operator UI tests, the Phase 22.3/22.4/22.5
configuration and continuation regressions, the RecognitionType C regression, and the complete
offline suite. Run Ruff lint/format, `compileall`, `pip check`, both example configuration
validations, wheel build plus the isolated installed-wheel smoke test, documentation local-link
validation, `git diff --check`, the FFmpeg/FFprobe production audit, the business-filesystem
mutation audit, and the private configuration checks. Report the deliberate mount-removal
falsification runs explicitly, including the restoration and a clean `git status`. No real Storage,
Provider, or production data is used.

## Documentation

Update `docs/progress.md` with the correction implementation evidence beneath the preserved
Phase 22.6-A `FIX REQUIRED` record, and correct the Phase 22.6-A claim that "reachable Web controls"
were covered by adding what now actually proves it. Update `docs/roadmap.md` with the resulting
Phase 22.6-A gate. Keep `docs/product-experience.md`, `docs/requirements.md` and
`docs/architecture.md` CURRENT claims accurate; they need changes only where they overstate existing
test coverage. Keep ClassificationPolicy/OrganizePolicy editing, conflict/capability prechecks,
Provider switching, generic Task resume and broader per-item recovery explicitly TARGET. Never
rewrite historical Phase evidence, including the preserved Phase 22.5-E and Phase 22.6-A
`FIX REQUIRED` records and their rejected SHAs.

## Closure Checklist

- [x] Workspace preflight records worktree, `.git`, index, sandbox, and approval mode.
- [x] Capability mode is classified as Git-writable / Full Access or Git-read-only / workspace-write.
- [x] The preceding dependent Phase is `PASS / CLOSED` with its commit SHA recorded
      (`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`, Phase 22.5).
- [x] The rejected Phase 22.6-A checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` is preserved
      and not amended, squashed, or rewritten.
- [x] Implementation and all required focused/full quality gates pass with actual evidence,
      including the mount-removal falsification and its restoration.
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

- the exact falsification evidence: the test failure with the mount removed and the pass with it
  restored, for both the preview section and the guided policy list;
- what the new service/API invalid-template test proves about the unchanged Draft and absent preview
  evidence, and the successful preview after correction;
- confirmation that no production behaviour, API contract, evidence key, or schema marker changed,
  or the exact minimal production change if one proved necessary;
- CURRENT versus remaining TARGET for the Phase 22.6 journey and the exact next journey gap.
