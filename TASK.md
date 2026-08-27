# Phase 22.6-A — Managed NamingPolicy Configuration + Exact-Revision Offline Naming Preview

This Task follows [the authoritative development workflow](docs/development-workflow.md).

```text
Status: READY FOR HIGH REVIEW
Commit SHA: PENDING
High Audit: PENDING
Preceding closed checkpoint: dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62
  (Phase 22.5-E and Phase 22.5 PASS / CLOSED — 2026-08-27)
Push gate: SATISFIED — dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62 is contained in origin/main
  (pushed 2026-08-27 with explicit operator authorization)
Phase: 22.6 Naming / Classification / Organize configuration journey (roadmap section 5)
```

## User Problem

An operator can now manage Storage, ResourceLibrary, MediaLibrary, Recognition objects and
MetadataPolicy objects inside a managed Draft revision, test them, and activate a checked snapshot.
Naming is not part of that experience. `namingPolicies` can only be changed by hand-editing the whole
managed document, nothing shows which RecognitionTypePolicy depends on a template, and no surface
answers the operator's actual question before activation: *what filename and directory will this
template produce?*

The consequence is that the first visible proof of a naming mistake is the destination path of a real
organize run. Naming decides the final media library layout, so the operator needs bounded per-object
editing plus an explainable, zero-mutation preview of the exact revision they are about to validate.

## User Journey

`docs/product-experience.md` journey A/B (configuration and policy setup) and roadmap section 5:

```text
Configuration → open a Draft revision → see its NamingPolicy objects and what references each one
→ create / edit / copy / delete one NamingPolicy (movie or TV templates, missing-variable strategy)
→ run an offline naming preview against that exact revision with one bounded sample
→ see the rendered directory and filename, sanitization, missing-variable handling and warnings
→ correct the template and re-preview, or Validate the revision
→ existing checked activation gate is unchanged
```

Entry points: managed Configuration Web UI and the equivalent authenticated API, sharing one
Application service. CLI keeps its existing read-only configuration inspection; no new CLI journey is
part of this slice.

Boundary: NamingPolicy objects and naming preview only. ClassificationPolicy and OrganizePolicy
editing, target-conflict and Storage-capability prechecks, and any activation-gate change belong to
later Phase 22.6 slices.

## User-visible Outcome

The operator can, entirely inside the managed Draft revision:

- list every NamingPolicy in the revision with its media-type mode, templates and
  missing-variable strategy;
- see, per policy, the exact objects that reference it and whether deletion is blocked;
- create, edit, copy, enable/disable-equivalent naming fields, and delete one policy at a time with
  optimistic version checking and a Before/After audit record;
- run an offline naming preview bound to that exact revision ID and version and read the rendered
  target directory, target filename, applied policy ID, sanitization changes, missing-variable
  decisions, and bounded warnings;
- distinguish a current preview from a stale one after the Draft changes, and rerun it.

The full V1 naming journey remains incomplete after this slice: classification target resolution,
Organize policy editing, conflict/capability prechecks and the combined
naming-plus-classification activation evidence are later Phase 22.6 work.

## Failure and Recovery

| Failure class | Visible state | Durable state / side effects | Retry safe | Recovery | If recovery also fails |
|---|---|---|---|---|---|
| Invalid template (unknown variable, unsafe separator/traversal, empty render, over-long component) | Bounded validation category naming the offending field and token | Draft unchanged; no preview evidence written | Yes | Correct the template field and resubmit | Revision stays Draft; operator may copy a known-good policy |
| Duplicate or missing object id | Bounded validation error identifying the id | Draft unchanged | Yes | Choose a unique id, or reload the revision | Draft remains editable |
| Delete a referenced policy | Blocked with the exact referencing objects listed | Draft unchanged | No, not as-is | Remove or repoint the reference first, then delete | Reference evidence stays visible; nothing is silently detached |
| Optimistic version conflict (concurrent Draft edit) | Bounded conflict showing the current version | One durable winner; the losing edit is not applied | Yes after reload | Reload the revision and reapply the change | Draft content is never merged silently |
| Preview render failure | Bounded failure category, message and next action | Persisted bounded preview evidence for that exact revision; no Storage or Provider work | Yes | Fix the reported field and rerun the preview | Evidence remains inspectable and clearly failed |
| Stale preview after the Draft changed | Preview is labelled stale with its original revision identity | Prior evidence retained, not silently reused as current | Yes | Rerun the preview against the current revision | The revision cannot present stale evidence as current |
| Missing naming variable under the configured strategy | Visible strategy outcome (token omitted, placeholder, or explicit failure) | Preview evidence records the decision | Yes | Change the template or the strategy and rerun | Behaviour stays deterministic and explained |

Retry alone is never the recovery text: each case states what is durable, what is safe to repeat, and
the single explicit action that continues.

## UX Acceptance Criteria

- [ ] The operator completes NamingPolicy editing and naming preview through the managed
      Configuration Web UI, not only through the API or by hand-editing JSON.
- [ ] Each policy's references and delete-blocked state are discoverable from the current revision
      view before any destructive action.
- [ ] Preview success, validation failure, render failure and stale states are visibly distinct and
      each carries one next action.
- [ ] The rendered directory/filename, applied policy, sanitization and missing-variable decisions
      are bounded, secret-free explanations of an automated decision.
- [ ] Preview evidence is bound to the exact revision ID and version it ran against; a changed Draft
      makes it stale rather than silently current.
- [ ] Anything presented as Active remains the immutable runtime-consumed snapshot; this slice
      changes no activation semantics.
- [ ] API and Web share the same Application service, permissions, validation and state vocabulary.
- [ ] Preview performs zero Storage, Provider, queue, Task and media work on every path, including
      failure paths.
- [ ] Acceptance tests cover success, invalid input, blocked delete, concurrent/stale edit, stale
      preview, and zero mutation.

Batch per-item independence does not apply: this slice edits one configuration object per request and
previews one sample per request.

## Technical Scope

Smallest coherent vertical slice, reusing existing components rather than adding new engines:

```text
ConfigurationObjectKind.NAMING_POLICY → managed document `namingPolicies` section
→ ConfigurationObjectService.mutate + reference evidence
→ new exact-revision offline naming preview in the same service
→ authenticated API route + managed Configuration Web section
→ persisted bounded preview evidence with revision identity
→ tests
```

- Add `NAMING_POLICY` to the editable section map with per-field validation for `mediaTypeMode`,
  movie/series/season/episode/multi-episode templates and `missingVariableStrategy`, matching the
  shapes already accepted by `config/strategy.example.json` and the runtime loader.
- Reuse `NamingPolicyRegistry`, `NamingEngine`, `SafeTemplateRenderer`, `NameSanitizer` and
  `NamingPreviewService`; do not fork template rendering or sanitization for the Web path.
- Extend reference evidence so RecognitionTypePolicy references to a naming policy are reported and
  block deletion exactly like existing reference-protected kinds.
- Store bounded preview evidence in the existing revision evidence structure with the same
  current/stale semantics as the Local setup check and Strategy Test evidence.
- Preview input is one bounded synthetic sample (title, optional year, optional season/episode(s),
  optional episode title, tags, extension) or one operator-supplied path string parsed by the
  existing local Parser. No Storage adapter is constructed on any path.
- No schema migration is expected; if one is required, keep it forward-only and record it.

## Non-goals

- No ClassificationPolicy or OrganizePolicy editing, and no MediaLibrary target resolution preview.
- No conflict-strategy, Storage-capability, or destination-existence precheck.
- No change to Draft/Validate/Activate semantics, the checked activation gate, or the immutable
  runtime snapshot contract.
- No Provider access, Metadata lookup, scan, Task, Job, Preview queueing, or media mutation.
- No Provider switching, generic Task resume, or broader per-item checkpoint recovery (later Phases).
- No frontend framework, unrelated Web refactor, remote Storage editing, or Secret Store work.
- No new CLI journey and no naming preview from production runtime Active configuration.

## Safety and Architecture Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner and DryRun mutate nothing;
  this slice touches only Naming configuration and a pure rendering preview.
- Only OrganizerExecutor may mutate Storage; this slice grants no execute authority.
- Naming only computes target directory and filename; it must not resolve MediaLibrary, decide
  classification, or perform any file operation.
- Rendered components stay path-safe: no separator injection, traversal, control characters, or
  silently truncated Unicode.
- RecognitionType C remains C even when its RecognitionTypePolicy references NamingPolicy A.
- Anything shown as Active remains the exact immutable snapshot consumed by runtime.
- Credentials, endpoints, raw Provider responses, headers, cookies, exception text and private paths
  must not enter Web, API, evidence, logs, tests or commits. `config/alist.json` is never read.

## Required Tests

Product acceptance first:

1. Web/API journey: create a NamingPolicy in a Draft revision, preview it, see the rendered
   directory/filename and explanation, correct an invalid template, and preview successfully.
2. Reference impact: a RecognitionTypePolicy reference is listed and blocks deletion; after the
   reference is removed the delete succeeds.
3. Stale/concurrent behavior: an optimistic version conflict yields one durable winner and one
   actionable conflict; editing the Draft after a preview marks that evidence stale and requires a
   rerun.
4. Failure/recovery: unknown variable, unsafe separator/traversal, empty render, over-long component,
   and each missing-variable strategy produce bounded distinct categories with a next action.
5. Movie, single-episode TV, and multi-episode TV previews render through the existing engine with
   the expected components.
6. Zero-mutation and isolation: no Storage adapter, Provider, queue, Task or Job is constructed on
   success or failure paths; the destination tree and the runtime Active snapshot are unchanged.
7. Regression: `RecognitionType C` with NamingPolicy A and ClassificationPolicy A still yields C;
   Phase 22.3/22.4/22.5 configuration, Strategy Test, MetadataPolicy, correction and continuation
   behavior remain unchanged; the complete offline suite has no weakened or removed assertion.

## Validation

Run the focused Naming configuration/preview tests, the Phase 22.3/22.4/22.5 configuration and
continuation regressions, the RecognitionType C regression, and the complete offline suite. Run Ruff
lint/format, `compileall`, `pip check`, both example configuration validations, wheel build plus the
isolated installed-wheel smoke test, documentation local-link validation, `git diff --check`, the
FFmpeg/FFprobe production audit, the business-filesystem mutation audit, and the private
configuration checks. No real Storage, Provider, or production data is used.

## Documentation

Update `docs/product-experience.md` (naming configuration journey CURRENT scope),
`docs/requirements.md` and `docs/architecture.md` (CURRENT versus TARGET for Naming configuration),
`docs/roadmap.md` (Phase 22.6 gate and remaining boundary) and `docs/progress.md` (implementation
evidence, then the closure record after High review). Keep ClassificationPolicy/OrganizePolicy
editing, conflict/capability prechecks, Provider switching, generic Task resume and broader per-item
recovery explicitly TARGET. Never rewrite historical Phase evidence, including the preserved
Phase 22.5-E `FIX REQUIRED` record and its rejected SHA.

## Closure Checklist

- [x] Workspace preflight records worktree, `.git`, index, sandbox, and approval mode.
- [x] Capability mode is classified as Git-writable / Full Access or Git-read-only / workspace-write.
- [x] The preceding dependent Phase is `PASS / CLOSED` with its commit SHA recorded
      (`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`, Phase 22.5).
- [x] The Phase 22.5 closure push gate is satisfied: `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` is
      reachable from `origin/main` before this implementation begins.
- [x] Implementation and all required focused/full quality gates pass with actual evidence.
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

- the user journey result on the Web surface, not only the API;
- the visible preview outcome for movie, single-episode and multi-episode samples;
- each failure category with its durable state and recovery action;
- reference-impact and delete-block evidence;
- stale-evidence and version-conflict evidence;
- zero-Storage, zero-Provider and no-execute-authority evidence;
- CURRENT versus remaining TARGET for the Phase 22.6 journey and the exact next journey gap.
