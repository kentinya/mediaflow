# Phase X.Y — [Vertical User Journey Slice]

## User Problem

Describe the operator's problem in product language. State why the current experience is incomplete;
do not describe only a missing repository, model, endpoint, or screen.

## User Journey

Identify the journey in `docs/product-experience.md` and describe this slice:

```text
Starting point → visible state → user action → outcome → next safe action
```

List the entry points covered (Web/API/CLI where applicable) and the exact boundary of the slice.

## User-visible Outcome

State what the operator can see and accomplish after this task. Include status, explanations,
confirmation, and audit visibility. Say explicitly if the full V1 journey remains incomplete.

## Failure and Recovery

For each expected failure class, define:

- visible error/category
- durable state and known side effects
- whether retry is safe
- explicit recovery action
- behavior when recovery also fails

Do not use “can retry” as the complete recovery design.

## UX Acceptance Criteria

- [ ] User goal can be completed through the promised final surface.
- [ ] Entry point and available actions are discoverable from current state.
- [ ] Success, partial, waiting, ignored, conflict, and failure states are distinguishable where relevant.
- [ ] Automated decisions expose bounded secret-free explanations.
- [ ] Batch items retain independent state and recovery where relevant.
- [ ] Active configuration shown to the user is the runtime-consumed immutable snapshot.
- [ ] API/Web behavior and permissions are consistent where both apply.
- [ ] Preview/DryRun and explicit mutation authority preserve safety boundaries.
- [ ] User acceptance tests cover success, failure, recovery, stale/concurrent state, and zero mutation.

Remove criteria that genuinely do not apply and explain why; do not leave them silently unchecked.

## Technical Scope

Describe the smallest coherent vertical implementation, normally including as applicable:

```text
Domain → persistence → Application → API → Web UI → validation/test → activation → acceptance
```

Reuse existing services and engines. List migrations, compatibility boundaries, and observable
evidence. Technical scope follows UX acceptance; it does not define product completion by itself.

## Non-goals

List adjacent journeys, future phases, framework/style decisions, and unsafe shortcuts explicitly
excluded from this task.

## Safety and Architecture Invariants

- Scanner/Parser/Recognition/Metadata/Naming/Classification/Planner/DryRun do not mutate Storage.
- Only OrganizerExecutor mutates Storage.
- No silent overwrite/delete or implicit operation fallback.
- RecognitionType C remains C while reusing configured policies.
- Credentials do not enter configuration output, logs, audit, or test fixtures.
- Add journey-specific invariants.

## Required Tests

List product acceptance tests first, then unit/integration/regression tests. Include failure and
recovery, per-item batch state when applicable, stale/concurrent decisions, CURRENT/TARGET claims,
and zero-mutation evidence.

## Validation

Run focused and full regressions plus formatter, lint, typecheck if configured, compile, dependency,
configuration, forbidden-dependency, build, and diff checks. Real service evidence follows
`docs/storage-acceptance.md` and never uses production data.

## Documentation

Update product-experience, canonical requirements/status, architecture CURRENT/TARGET, roadmap,
configuration guidance, progress, and README only where facts or user instructions changed. Never
rewrite historical Phase evidence.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

- user journey result
- visible outcomes
- failures and recovery
- safety evidence
- CURRENT versus remaining TARGET
- exact next journey gap
