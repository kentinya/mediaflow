# Phase 19.23.3 — OpenList v4 Empty-Directory DTO Repair and Rerun

## Goal

Repair only the real OpenList v4.2.2 empty-directory response incompatibility
found in Phase 19.23.2, then redeploy the isolated official service and rerun the
complete production-adapter matrix.

## Scope

### 1. Strict DTO compatibility

- Normalize `content: null` to an empty sequence only when `total == 0`.
- Preserve normal non-empty list mapping.
- Reject `content: null` with non-zero/negative/bool/missing total.
- Reject non-list, non-null content and malformed entry DTOs.
- Keep all OpenList HTTP DTO behavior inside the infrastructure adapter.

### 2. Regression tests

- Add the exact v4.2.2 empty response regression.
- Add inconsistent-null, malformed-content, and invalid-total cases.
- Preserve authentication, error mapping, pagination, no-overwrite, retry, and
  secret-redaction behavior.

### 3. Real isolated rerun

- Reuse the Phase 19.23.2 loopback-only, pinned official container pattern with
  new temporary credentials/data and an empty `mediaflow-acceptance-*` root.
- Execute the full adapter lifecycle and Local↔OpenList/OpenList↔OpenList matrix.
- Retain a new non-secret JSON report and destroy container/secrets/backend.
- If another production defect appears, record FAIL and do not repair it in the
  same acceptance run.

### 4. Status

- Mark OpenList self-hosted acceptance PASS only if every matrix and cleanup
  assertion passes.
- Self-hosted Local-driver evidence does not certify third-party cloud drivers.
- Do not begin Samba/MinIO until this OpenList repair/rerun concludes.

## Boundaries

Do not change Parser, Scanner, Recognition, Metadata, Naming, Classification,
Planner, Organizer policy semantics, UI, API, or user configuration. Do not use
`config/alist.json`. Do not broadly loosen response validation or thresholds.

## Validation

Run focused OpenList contract/storage/Organizer tests, full offline tests,
formatter, lint, compile, dependency/configuration checks, FFmpeg/FFprobe audit,
isolated wheel smoke, and the explicit real OpenList matrix.

## Completion Report

Finish with:

## Phase 19.23.3 Result

PASS / FAIL

## DTO Repair

## Real Matrix

## Evidence

## Cleanup

## Safety

## Regression

## Changed Files

## Remaining Work

## Risks

## Final Recommendation
