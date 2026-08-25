# Phase 22.2R-F2 — Atomic API Runtime Binding and Pinned-Job Recovery

## User Problem

Independent review of Phase 22.2R-F1 found that a green suite still permits Active configuration
identity and actual API behavior to diverge.

The production API refresh validates the newly Active document and updates the snapshot ID/digest,
but it keeps constructor-time workflow settings inside existing services. This is reproducible:

```text
Active A: automation.maximumActiveJobs = 1
activate B: automation.maximumActiveJobs = 2
first Job under B: accepted and pinned to B
second Job under B: rejected using A's limit of 1
```

The reverse transition can retain a less restrictive old admission limit. The same identity-only
refresh pattern affects protected remote-execution settings and config-derived API read state. An
operator can therefore see B as Active while the resident API still applies parts of A. This
violates the permanent rule that configuration shown as Active is the configuration consumed by
runtime and is a safety issue for execute admission.

The review also reproduced a queued Job pinned to a deleted/corrupt published revision. The Worker
correctly avoided switching to the newer Active revision, but persisted only
`workflow failed (RuntimeError)`. The operator cannot see the failed configuration category,
durable state, side-effect status, retry safety, or valid recovery action.

Finally, several tests explicitly required by Phase 22.2R-F1 are absent: true concurrent managed
configuration lifecycle coverage, missing/corrupt saved-revision Worker coverage, protected execute
Job pin coverage, and complete lifecycle zero-I/O evidence.

These are correction defects inside Phase 22.2. Do not begin Phase 22.3.

## User Journey

Close the existing whole-document configuration journey without adding object-level configuration
editors:

```text
Web Configuration
→ inspect Active A
→ import/edit/validate B
→ inspect redacted diff
→ activate B
→ submit DryRun Preview or explicitly authorized organize request
→ API applies B's admission and safety settings
→ Job is pinned to B
→ Worker creates Task/Result from B
```

For already queued work:

```text
Job pinned to A
→ Worker claims Job using only the immutable database locator
→ load exact published A
→ run from A, even if B is now Active
```

If A is missing or corrupt, the Job fails before workflow construction. Web/API Job detail must
explain which saved snapshot failed, that no media side effect occurred, whether retry is safe, and
the concrete recovery action. It must never switch the Job to B.

## User-visible Outcome

- After activation, a new API request uses one coherent runtime binding: snapshot identity,
  DryRun queue admission, protected-execute gate/admission, and config-derived API status all come
  from the same validated Active revision.
- A stricter Active setting takes effect immediately for new requests; an older, more permissive
  in-memory setting cannot authorize work under the new snapshot label.
- Web/API continue to expose configuration recovery while Active is unhealthy, and media work
  remains fail-closed.
- A Job whose saved published revision is missing, corrupt, unsupported, or runtime-invalid shows a
  bounded, secret-free, actionable configuration failure rather than generic `RuntimeError`.
- Existing valid pinned work remains on its saved revision.
- Configuration lifecycle operations still construct no Storage adapter or Metadata Provider and
  perform no media I/O.

## Failure and Recovery

- **API refresh fails:** publish none of the candidate runtime binding. Keep the previously valid
  in-memory binding only for already admitted/in-flight work; every new media-work request fails
  against the unhealthy current authority. No Job, authorization consumption, Task, schedule
  emission, or Result is created. Recovery remains replacement Draft → validate → activate.
- **Activation succeeds but runtime binding cannot be committed:** return a structured unavailable
  response and admit no new work. Do not label old settings with the new identity. The operator sees
  that the durable Active changed but resident runtime is unavailable and can restart/recover safely.
- **Stale Draft lifecycle operation:** preserve Draft/Active and return structured `409` with current
  identity and refresh/revalidate guidance.
- **Saved Job revision missing/corrupt/unsupported/runtime-invalid:** fail before Storage/Provider or
  Task construction, persist a safe failure category and saved identity, state `sideEffects=none`,
  and state whether retry is safe. Recovery must say to restore the immutable published revision or
  explicitly create new work under the current Active; blind retry is not recovery.
- **Concurrent activation/request:** each request observes either the complete old binding or the
  complete new binding, never a mixed identity/settings pair.
- **Protected execute disabled by new Active:** deny new organize submissions even if the old process
  was started with execution enabled. Do not consume the one-time authorization on denial.

## UX Acceptance Criteria

- [ ] The Web/API import/edit/validate/diff/activate → Preview → Worker Task/Result journey uses one
      revision ID/digest and the admission settings from that revision.
- [ ] Web configuration status and system/admission state never present a new Active identity beside
      behavior retained from the prior Active.
- [ ] Increasing and decreasing `maximumActiveJobs` both take effect for new API Job submissions
      under the same snapshot pin shown on those Jobs.
- [ ] Disabling protected remote execution in a newly Active revision blocks new execute Job
      submission before authorization consumption or media side effects.
- [ ] Missing/corrupt saved Job revisions are distinguishable from media failures and show saved
      identity, durable state, side effects, retry safety, and next action in API/Web Job detail.
- [ ] Valid older pinned work still runs from its saved published revision; it never switches to the
      current Active.
- [ ] Repeated requests under unhealthy Active remain fail-closed and management recovery remains
      available.
- [ ] Configuration lifecycle/recovery performs zero Storage and zero Provider I/O.
- [ ] DryRun performs zero Storage mutation and no execute authority is inferred.

## Technical Acceptance Criteria

- [ ] Replace identity-only API refresh with a coherent immutable/request-scoped runtime binding (or
      an equivalently atomic design). Fully validate and normalize the candidate before publishing
      any part of the binding.
- [ ] The binding used by a workflow-creation request includes at least snapshot ID/digest,
      `maximumActiveJobs`, remote-execution enabled/TTL/admission settings, schedules exposed by the
      resident API, system-status snapshot, and config-derived metadata policy references used by
      existing API actions.
- [ ] A request captures one binding and uses it through admission and persistence; concurrent
      refresh cannot combine B's identity with A's settings.
- [ ] Protected execute authorization consumption and Job creation are checked against the same
      current binding that supplies the persisted Job pin. A newly disabled gate wins safely.
- [ ] Scheduler behavior from F1 remains atomic: schedule content, emission admission, and pin come
      from one loaded revision; reload failure emits nothing and advances no due state.
- [ ] Worker still claims from the immutable locator before loading workflow content and resolves
      only the Job's saved published revision.
- [ ] Trusted configuration-resolution failures cross the nested CLI/Worker boundary as bounded
      structured safe data. Arbitrary external exception messages remain redacted.
- [ ] Persisted/API-visible Job failure evidence is sufficient for Web to render category, saved
      snapshot identity, durable state, side-effect status, retry safety, and next action.
- [ ] Missing/corrupt saved revisions create no Task/Result and do not switch to current Active.
- [ ] Direct Task, API DryRun Job, protected execute Job, Worker Task, and resident Scheduler Job pin
      their exact required revision ID/digest.
- [ ] True concurrent import/edit/activate tests prove unique revision sequences, one optimistic edit
      winner, exactly one Active winner, atomic audit, and preservation of prior Active on failure.
- [ ] Audit before/after evidence remains bounded and secret-free.
- [ ] No core media engine or Storage adapter semantics change.

## Technical Scope

Make the smallest coherent correction in these existing seams:

```text
Managed Active revision
→ fully normalized immutable API runtime binding
→ request-scoped admission/gates/status/pin
→ durable Job

claimed Job pin
→ exact saved revision resolution
→ safe structured Worker failure or pinned Task/Result
```

- Refactor `MediaFlowApi` refresh/publication only as needed to prevent partial state updates and
  stale admission behavior. Do not introduce a general framework.
- Reuse the normalized `RuntimeConfiguration`; do not duplicate configuration parsing in API code.
- Keep recovery bootstrap limited to the immutable database locator and approved environment-owned
  principals. Do not construct Storage/Provider while Active is unavailable.
- Preserve atomic queue admission and one-time execution-authorization consumption.
- Add the minimum trusted Worker failure contract/schema needed for actionable snapshot failures;
  keep arbitrary exception details redacted.
- Extend the existing Web Job/error rendering instead of building a new UI.
- Add the missing permanent concurrency, pin, recovery, zero-I/O, and cross-layer tests.

## Non-goals

- No Phase 22.3 Storage/ResourceLibrary/MediaLibrary CRUD, connectivity test, or first-time setup.
- No object-level policy editor, dependency graph, Secret Store, user database, OIDC, or TLS work.
- No generic hot-reload plugin framework, in-flight work migration, checkpoint redesign, or stage-aware
  recovery implementation.
- No change to Parser, Recognition, Metadata matching, Naming, Classification, Planner,
  OrganizerExecutor, or Storage adapter semantics.
- No automatic rebinding of already queued/running work to a newer Active revision.
- No real Storage/TMDB access and no unattended execute.

## Required Tests

Add permanent regressions for all of the following:

1. Activate A with `maximumActiveJobs=1`, then B with `maximumActiveJobs=2`; two new Jobs pinned to B
   are admitted. Reverse the values and prove the stricter B limit rejects the excess Job.
2. Activate A with remote execute enabled, then B disabled; a new protected organize submission under
   B is denied before token consumption and creates no Job/Task/Result. Re-enable via a validated C
   revision and prove the accepted Job pin/settings are both C.
3. Concurrent activation and API submission proves every accepted/rejected request observes a
   complete old or new binding, never a mixed identity/admission pair.
4. API schedule/status/config-derived policy views after activation correspond to the same revision
   used for new Job pins. Recovery-started API can publish the healthy binding after replacement.
5. True multi-connection concurrent Draft imports produce unique monotonic revision sequences and
   one audit per successful import.
6. Two concurrent edits of one version produce exactly one success and one structured optimistic
   conflict; payload, version, and audit remain atomic.
7. Two concurrent activation attempts based on one Active produce exactly one new Active; the loser
   preserves its Validated Draft and the prior/new Active state is consistent.
8. Queue under A, activate B, then separately delete A, corrupt A's digest/payload, change A's
   schema, and make A runtime-invalid. Each Job fails explicitly with its A identity, no Task/Result,
   no switch to B, no Storage/Provider construction, and actionable recovery evidence.
9. Valid older A still completes after B becomes unhealthy, preserving A across Job, Task, and
   Result traceability.
10. Direct Task, API DryRun Job, protected execute Job, Worker Task, and Scheduler Job exact-pin
    regressions.
11. Actual `/ui/` and `/ui/app.js` serving plus API action-shape and production entry-point journey:
    invalid Draft → edit → validate → diff → activate → Preview → Worker → Task/Result.
12. Lifecycle I/O spies cover import, edit, validate, diff/detail, activate, unavailable recovery,
    API binding refresh, and accepted DryRun. Configuration operations perform zero Storage/Provider
    I/O; DryRun performs zero mutation.
13. Audit evidence remains bounded/redacted and no literal secret reaches response, Job error, audit,
    log, or test output.

## Validation

Run focused configuration snapshot/runtime-binding tests, API/Web tests, Scheduler/Worker/Task/Job
tests, execution-authorization safety tests, DryRun regressions, and the complete offline suite. Also
run Ruff lint/format, compileall, `pip check`, configured wheel/smoke build, documentation link checks,
`git diff --check`, FFmpeg/FFprobe audit, and business-filesystem boundary audit. Report actual
collected/passed/failed/skipped counts. Real external services are neither required nor allowed.

## Documentation

After the repair is proven, update CURRENT statements in the canonical Chinese specification,
`docs/product-experience.md`, `docs/requirements.md`, `docs/architecture.md`,
`docs/configuration.md`, `docs/roadmap.md`, `docs/progress.md`, and README only where they are
factually changed. Do not mark Phase 22.2 accepted or begin Phase 22.3; independent review remains
required.

## Completion Report

<!-- Archived after independent review: PASS/CLOSED, 2026-08-24. -->

Use the AGENTS.md Implementation Role report format. Explicitly report atomic API binding evidence,
stricter execute/admission behavior after activation, actionable missing/corrupt pinned-revision
failure, true concurrent lifecycle evidence, Web → Worker → Task/Result pin consistency, zero-I/O
evidence, exact test totals, and all deviations/risks. Do not declare the Phase closed.
