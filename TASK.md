# Phase 17 — Runtime Storage Adapters + Read-only Preflight

## Goal

Complete production JSON runtime construction for the already-implemented SMB and S3/R2 Storage
adapters, and add a safe read-only preflight command. Do not redesign Storage adapters or begin
service/API/UI work.

## 1. Runtime configuration

Support Storage `type` values:

- `local`
- `openlist`
- `smb`
- `s3`
- `r2`
- `s3-compatible`

Normalize them into existing LocalStorage, OpenListStorage, SMBStorage, and S3Storage adapters.

## 2. Secret ownership

- SMB username/password and S3 access/secret/session credentials come from named environment
  variables, never literal JSON secret values.
- OpenList continues using `tokenEnv`.
- Fail clearly when a required environment variable name or value is missing.
- Never include secret values in repr, CLI output, errors, logs, examples, or persisted records.

## 3. Validation

- `mediaflow config validate` validates all non-secret fields without constructing adapters,
  accessing network/storage, or requiring secret values to be present.
- Validate provider names, endpoint rules, bucket/share/host, ports, timeouts, concurrency,
  multipart sizes, page sizes, retries, root paths, and environment-variable names.
- Duplicate/unknown Storage definitions still fail before processing.

## 4. Read-only Storage preflight

Add:

```text
mediaflow storage list
mediaflow storage check [STORAGE_ID]
```

- `list` prints configured type, root, read-only state, and declared capabilities without network
  access or secret requirements.
- `check` constructs selected adapters, invokes existing adapter health checks where available, and
  performs no Storage mutation.
- Check all configured Storages when ID is omitted; failures are isolated and summarized.
- Local preflight verifies the configured root through read-only queries only.
- Output distinguishes configuration, dependency, authentication, permission, connection, and
  unsupported errors without exposing secrets.

## 5. Configuration examples

Document complete Local/OpenList/SMB/AWS S3/Cloudflare R2/generic S3-compatible definitions and
required environment variables. Examples contain placeholders only, never working credentials.

## Safety

- Preflight may call only health/list/stat/exists-style read operations.
- Zero Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls.
- Existing DryRun, conflict, attachment, and explicit execute boundaries remain unchanged.
- Do not implement scheduler, API, Web UI, background workers, NFO, or Phase 18.

## Required tests

- Runtime construction for SMB, AWS S3, R2, and generic S3-compatible definitions using fakes.
- Environment secret resolution, missing environment values, and redaction.
- Invalid provider/endpoint/bucket/share/port/timeout/concurrency/multipart/env-name cases.
- Config validation requires no secret values and makes zero Storage/network calls.
- Storage list makes zero adapter/network calls.
- Storage check success/failure isolation, capability output, unknown ID, and zero mutation.
- Optional real SMB/S3/R2 tests remain environment-gated.
- All Parser through Phase 16, Storage, Task, conflict, attachment, and DryRun regressions.

## Documentation

Update README, configuration examples, architecture, progress, roadmap, and product status.

## Validation

Run all tests, formatter, linter, compile check, dependency check, wheel build, configuration
validation, FFprobe/FFmpeg audit, and diff check. Fix every Phase 17 failure before PASS.

## Final report

## Phase 17 Result

PASS / FAIL

## Runtime Adapters

## Storage Preflight

## Security

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
