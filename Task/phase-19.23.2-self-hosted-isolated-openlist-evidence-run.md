# Phase 19.23.2 — Self-hosted Isolated OpenList Evidence Run

## Goal

Use the operator-authorized, locally self-hosted OpenList service to execute the
Phase 19.23 production-adapter matrix and retain non-secret evidence. Close the
self-hosted OpenList row only if every operation and cleanup assertion passes.

## Scope

### 1. Isolated deployment

- Use the current official stable OpenList container image pinned by version.
- Bind HTTP only to host loopback on an ephemeral/non-public port.
- Generate a unique administrator credential for this run and never persist it
  in Git, shell output, documentation, logs, or reports.
- Store container state and backend files only in a new temporary directory.
- Configure one OpenList Local storage rooted inside that temporary directory.
- Do not mount repository, user configuration, or media directories.

### 2. Acceptance root and token

- Create a dedicated empty `mediaflow-acceptance-*` root through deployment
  setup, separate from all user libraries.
- Obtain a run-scoped API token from the isolated service.
- Supply all Phase 19.23.1 gate variables explicitly, including a new report.
- Do not use or inspect `config/alist.json`.

### 3. Execute real matrix

Run the production `OpenListStorage` and `OrganizerExecutor` acceptance suite,
covering adapter lifecycle, no-overwrite, Local↔OpenList COPY/MOVE,
OpenList↔OpenList COPY/MOVE, content/size/source verification, and cleanup.

### 4. Evidence and cleanup

- Retain the generated non-secret JSON report outside Git unless explicitly
  normalized into documentation.
- Record pinned OpenList version, date, matrix result, and cleanup status in the
  authoritative acceptance document.
- Stop and remove the isolated container after validation.
- Remove only run-created temporary deployment data after evidence inspection.
- A cleanup failure is a FAIL, not PASS.

### 5. Regression

After the real run, execute focused OpenList/Organizer/Storage regressions, full
offline tests, formatter, lint, compile, dependency/config validation,
FFmpeg/FFprobe audit, and isolated wheel smoke.

## Boundaries

Do not alter production adapter semantics during an acceptance run. If the real
matrix exposes a product defect, record FAIL and create a separate repair task.
Do not begin SMB/S3/R2, long-duration testing, UI, or strategy engine work.

## Completion Report

Finish with:

## Phase 19.23.2 Result

PASS / BLOCKED / FAIL

## Deployment

## Real Matrix

## Evidence

## Cleanup

## Safety

## Regression

## Changed Files

## Remaining Work

## Risks

## Final Recommendation
