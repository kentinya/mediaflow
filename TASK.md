# Task 38.5 — Slice 38 集成验证与 Closure Packet

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.5
Parent Slice: 38
Status: PLANNED
Task Base: a3a1dcc431c9875c56c71ea28508a816e0109a15
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Produce the Slice 38 integration evidence needed to demonstrate the complete MediaLibrary Files
journey, preserved ResourceLibrary Files continuity, safety boundaries and reference-aligned
presentation, then prepare a factual Closure Packet for A. This advances RO-8 and verifies that
RO-1 through RO-7 remain satisfied after the completed implementation Tasks.

## Why This Task Exists

Tasks 38.1 through 38.4 delivered the route separation, live browsing, configuration lifecycle,
bounded direct commands and MediaLibrary Copy/Move recovery. The remaining Contract work is a
single Slice-level proof boundary: run the complete required regression and release gates, capture
the mandated desktop/narrow screenshots, inspect the full Base..Head manifest and record every
Required Outcome, Required Surface, safety result, deferral and residual issue truthfully. This is
the largest coherent final-validation unit; it does not add another product capability.

## Implementation Scope

```text
Slice Base..Head audit
  → full Python/Web/browser/quality/security validation
  → controlled MediaLibrary screenshots and evidence inspection
  → factual Closure Packet and Task handoff to A
```

- Run the Slice-final validation from `SLICE.md`, including full Python and Web regression,
  affected ResourceLibrary and MediaLibrary browser journeys, typecheck/lint/format/build,
  governance, Python quality/dependency checks, configuration validation, FFmpeg/FFprobe
  exclusion and Docker release-security smoke.
- Capture controlled `1536 x 1024` MediaLibrary screenshots with the Add drawer closed and Step 1
  open, plus supported narrow-screen evidence. Confirm the hierarchy, library cards, directory
  tree, breadcrumbs, list/grid, commands and drawer while confirming the authorized omissions:
  no card statistics/capacity placeholders, thumbnails, Organize controls or browser upload.
- Inspect the complete immutable Slice Base..Implementation Head manifest, current Task history,
  private/credential files, ignored `config/alist.json` and both reference images. Preserve the
  pre-existing dirty `docs/pics/文件页.png` byte-for-byte.
- Reconcile the Closure Packet facts in `SLICE.md` only as delegated factual progress/closure
  evidence; do not change User Goal, Required Outcomes, Required Surfaces, Safety Invariants,
  Slice Base, Explicitly Deferred scope or A Final Review decisions. Set no Slice PASS/CLOSED
  status; B's handoff decision must be `SLICE READY FOR A REVIEW`.

## Acceptance Criteria

- [ ] Slice-final Python, Web, browser, quality, configuration, security and packaging gates run
      with actual totals, skips and unavailable gates recorded; failures are either fixed in this
      Task or proven pre-existing/unrelated without hiding, deleting or weakening tests.
- [ ] RO-1 through RO-7 are rechecked against the production implementation and legal Active
      configuration: route continuity, presentation, live scoped browsing, configuration save/
      removal, all bounded commands, durable transfer/recovery and independent library authority.
- [ ] RO-8 is evidenced by application/API/Web/browser coverage for success, failure, recovery,
      zero-mutation reads, stale/conflict/capability cases, cross-Storage verification and
      ResourceLibrary compatibility.
- [ ] Controlled desktop screenshots show Add closed and Step 1 open; supported narrow-screen
      evidence is captured. The screenshots demonstrate the Contract's hierarchy and omissions
      without introducing card statistics, thumbnails or Organize controls.
- [ ] The complete Base..Head manifest contains only Slice work plus the already-preserved dirty
      reference image; no credentials, private files, `config/alist.json`, SQLite files or build
      artifacts are committed. `git diff --check` and governance checks pass.
- [ ] A factual Closure Packet lists every Required Outcome and Surface as COMPLETE only when
      supported by evidence, records safety evidence, known non-blocking issues, Explicitly
      Deferred items and documentation reconciliation needs, and ends with `SLICE READY FOR A
      REVIEW` for A.

## Required Tests

Run from the repository root unless a `web/` prefix is shown. Use local fakes and temporary
Storage only; never use production services, credentials or user media.

- `python3 scripts/check_governance.py`
- `.venv/bin/python -m unittest discover -s tests`
- `npm --prefix web run test -- --run`
- `npm --prefix web run test:e2e`
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run format:check`
- `npm --prefix web run build`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- Confirm the FFmpeg/FFprobe exclusion with the repository-available grep command.
- `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py`
- Capture `1536 x 1024` MediaLibrary Add-closed and Add-Step-1-open screenshots and supported
  narrow-screen evidence using the repository browser harness or an equivalent reproducible
  local-fake command. Inspect screenshot dimensions and visible hierarchy.
- Inspect `git diff --check`, `git diff --name-status <Slice Base>..HEAD`, private files,
  `config/alist.json` ignore/untracked state and both reference image hashes.

## Non-goals

- New MediaLibrary behavior, new Storage providers, cross-kind transfers, transfer Replace mode,
  Organize/Scan/Preview, thumbnails/statistics, Upload/Download or arbitrary media editing.
- Changes to the A-owned User Goal, Required Outcomes, Required Surfaces, Safety Invariants,
  Slice Base, Explicitly Deferred scope, Roadmap or A Final Review.
- P2 wording/cleanup, optional proof beyond the Contract, or declaring the Slice PASS/CLOSED.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
