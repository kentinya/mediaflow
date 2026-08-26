# Phase 22.5-D — Managed Live Metadata Correction Test

This Task follows [the authoritative development workflow](docs/development-workflow.md).

## User Problem

The managed live Metadata test can show `NotFound`, `NeedConfirm`, or `Ambiguous` evidence and can
confirm one projected candidate, but an operator cannot correct the query, year, Movie/TV choice,
or enter a direct Provider ID from the same Configuration Web journey. The production
`MetadataCorrectionSelection` and Strategy runner already support those correction paths, yet using
them still requires internal composition outside the managed revision UI/API.

This slice makes correction testable against the exact Validated revision and the same effective
MetadataPolicy/provider. It does not implement Provider switching or resume a media Task.

## User Journey

This advances `docs/product-experience.md` journey D and the configuration-test segment of journey F:

```text
Configuration Web revision
→ inspect current live NotFound / NeedConfirm / Ambiguous evidence
→ enter corrected query/year/Movie-TV or one direct Provider ID
→ explicitly run the correction test
→ production Parser → Recognition → TypePolicy → MetadataPolicy → Provider path runs
→ inspect corrected identity/candidates or actionable failure evidence
→ confirm a resulting candidate through the existing Phase 22.5-C action when needed
→ correct again or explicitly activate only when existing activation evidence permits
```

Entry points:

- authenticated managed Configuration API;
- existing vanilla Configuration Web revision detail.

The full V1 Metadata failure-correction journey remains incomplete: actual Files/Task continuation
and Provider switching are later slices.

## User-visible Outcome

- Current live `not_found`, `need_confirm`, or `ambiguous` evidence exposes a bounded correction
  form in Web.
- The operator may choose exactly one correction mode:
  - corrected query with optional year and required Movie/TV choice; or
  - direct Provider ID with required Movie/TV choice.
- The Provider is not client-selectable in this slice. It is derived from the exact effective
  MetadataPolicy in the current Validated revision.
- Success evidence shows the correction input, resulting MediaIdentity, match method, candidates,
  scores, locale/policy identity, revision identity, side effects, retry safety, and next action.
- A corrected search that still yields `NeedConfirm` or `Ambiguous` remains compatible with the
  existing persisted candidate-confirmation action.
- No correction action automatically validates, activates, scans, resumes a Task, queues Preview,
  or executes media operations.

## Failure and Recovery

- Draft, Active, stale revision/digest, stale `testedAt`, offline evidence, non-correctable outcome,
  disabled/missing policy, wrong RecognitionType/policy/provider, or malformed correction fails
  closed before Provider access.
- Query and direct-ID modes are mutually exclusive. Hidden ignored fields are rejected.
- Invalid query/year/media type/direct ID returns bounded field guidance and preserves the current
  evidence.
- Provider not found, bad direct ID, authentication, rate limit, timeout, unavailable service, and
  malformed response remain distinct bounded categories. Failure evidence retains the submitted
  correction context, `sideEffects=none`, retry safety, and an explicit correction/rerun action.
- Concurrent correction submissions or an in-flight revision/evidence change use the existing
  durable revision-plus-evidence CAS: at most one result replaces the prior evidence; losers reload
  and review the durable current outcome.
- Recovery is explicit: review the persisted input/outcome, adjust the correction or provider
  environment as indicated, then run the correction test again. Provider switching is not offered
  as a hidden fallback.

## UX Acceptance Criteria

- [ ] Web exposes the correction form only for current, exact, live `not_found`, `need_confirm`, or
      `ambiguous` evidence on a Validated revision.
- [ ] Corrected query/year/Movie-TV runs the production search/matcher path using the exact effective
      MetadataPolicy and provider from the revision.
- [ ] Direct Provider ID runs the existing production direct-details path and records
      `manual_provider_id` or equivalent bounded explanation.
- [ ] Correction success, unresolved candidates, Provider failure, stale state, and invalid input
      are visibly distinct and have explicit recovery.
- [ ] Correction input and outcome are durable, bounded, secret-free, and reloadable.
- [ ] Existing candidate confirmation can act on corrected `NeedConfirm`/`Ambiguous` evidence
      without another search.
- [ ] API and Web use the same Application behavior, permission, validation, CAS, and evidence.
- [ ] RecognitionType C remains C and its configured MetadataPolicy/downstream policy references
      remain unchanged.
- [ ] No Provider request occurs while merely editing the form or reloading evidence.
- [ ] All paths perform zero Storage/media mutation and grant no execute authority.

## Technical Scope

1. Add one bounded Metadata-correction request shape carrying:
   - expected revision version/digest;
   - expected evidence `testedAt`;
   - `mediaType`;
   - either corrected `query` with optional `year`, or direct `providerId`.
2. Extend `ConfigurationObjectService` with one exact-revision correction action that:
   - reloads and validates current evidence;
   - derives RecognitionType, MetadataPolicy, Provider, ResourceLibrary, and synthetic path from
     persisted evidence/current revision;
   - constructs `MetadataCorrectionSelection`;
   - invokes the existing production Strategy runner with `live_metadata=True`;
   - persists bounded correction context on success and failure through the existing
     revision-plus-evidence CAS.
3. Add an authenticated API endpoint under the existing revision Strategy Test resource using
   `MANAGE_CONFIGURATION`.
4. Add the minimal Web correction form and outcome/recovery rendering using text-only DOM helpers.
5. Reuse the Phase 22.5-B service-lifetime Provider registry/cache and per-request policy controls.
6. Reuse Phase 22.5-C candidate confirmation when corrected search evidence remains reviewable.
7. No database migration is expected unless the existing bounded evidence JSON cannot truthfully
   represent correction context; do not add a second store.

## Non-goals

- No Provider switching, MetadataProvider CRUD, credential UI, Secret Store, arbitrary Provider
  injection, or implicit Provider fallback.
- No Files/Task correction continuation, Task resume API, new Job command, Preview queue, Naming,
  Classification, Plan, activation change, or media execution.
- No free-form destination/path correction, cache redesign, Provider telemetry redesign, frontend
  framework, or unrelated refactor.
- Do not begin Naming/Classification/Organize configuration or Phase 22.6.

## Safety and Architecture Invariants

- Parser, Recognition, Metadata lookup, correction testing, and evidence persistence do not mutate
  Storage.
- No Storage adapter is constructed by this correction test.
- Only the Provider referenced by the exact effective MetadataPolicy may be used.
- RecognitionType and downstream policy identity are not rewritten by correction input.
- Direct ID selects identity only; it does not accept arbitrary Provider or policy IDs.
- Credentials, endpoints, raw Provider DTOs/responses, headers, cookies, and exception text do not
  enter evidence, API, Web, audit, logs, tests, or commits.
- Existing checked-activation requirements are unchanged; correction never activates automatically.

## Required Tests

Product acceptance:

1. Current live `NotFound` → corrected query/year/Movie succeeds, persists/reloads the matched
   identity and correction context, with zero Storage construction.
2. Current live result → direct Provider ID succeeds through the direct-details path, preserves C,
   and performs no repeated search.
3. Corrected search remains `NeedConfirm`/`Ambiguous`; persisted corrected candidates can be
   confirmed by the existing Phase 22.5-C action without another search.
4. Provider timeout/rate-limit/auth/not-found/malformed response persists bounded correction
   context and actionable recovery without secrets.
5. Draft/stale/offline/wrong-outcome/invalid-mode/unprojected or malformed correction is rejected
   before Provider access and leaves evidence unchanged.
6. Two concurrent corrections from one evidence timestamp produce one durable winner and one
   actionable `409`; an in-flight Draft edit also fails closed.
7. Web action visibility, payload, immediate message, reload evidence, and recovery text match API
   semantics and do not auto-submit or retry.

Regression:

- Phase 22.5-B live Provider/cache/request-control/evidence-bound tests.
- Phase 22.5-C candidate confirmation F1/F2 concurrency and recovery tests.
- Phase 22.5-A MetadataPolicy CRUD/offline resolution and Phase 22.4 C-identity tests.
- Existing Phase 21 durable MetadataCorrection and Task-resume behavior remains unchanged.
- Complete offline suite and zero-mutation/forbidden-dependency audits.

## Validation

Run focused correction/Application/API/Web/persistence tests, related Phase 21/22.4/22.5
regressions, and the complete offline suite. Run Ruff lint/format, compileall, `pip check`, both
example configuration validations, wheel build/smoke, documentation local-link validation,
`git diff --check`, FFmpeg/FFprobe production audit, business-filesystem mutation audit, and private
configuration checks.

## Documentation

Update product-experience, requirements/status, architecture CURRENT/TARGET, roadmap, progress, and
configuration guidance only for behavior actually implemented. Preserve historical audit
narratives. Keep Provider switching and Files/Task continuation explicitly TARGET.

## Closure Checklist

- [ ] Implementation workspace/session preflight records worktree, `.git`, index, sandbox, and
      approval mode.
- [ ] Implementation capability mode is classified according to the authoritative workflow.
- [x] Preceding Phase 22.5-C candidate-confirmation Slice is `PASS / CLOSED`.
- [x] Reviewed checkpoint `d68a19ddd4bb62bc27e77bab013edb20c9eb53e5` is reachable from
      `origin/main`.
- [ ] Implementation and required focused/full quality gates pass with actual evidence.
- [ ] Commit manifest contains every required file and no unrelated/private file.
- [ ] `config/alist.json` remains ignored, untracked, unstaged, unread, and uncommitted.
- [ ] Coherent implementation checkpoint created: `Commit SHA: ________________________________`.
- [ ] High Review inspected that exact SHA: `High Audit: _________________________________`.
- [ ] Progress and roadmap record final Status / Commit SHA / High Audit.
- [ ] Next Slice has not started before every gate above is complete.
- [ ] Required push state is recorded.

Current checkpoint state:

```text
Status: IN PROGRESS
Commit SHA: PENDING
High Audit: PENDING
```

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- correction modes and exact request shape;
- visible success/failure/recovery outcomes;
- Provider call/search/detail counts;
- durable evidence/CAS behavior;
- C-identity and zero-mutation evidence;
- CURRENT correction-test capability versus remaining Provider switching and Task continuation.
