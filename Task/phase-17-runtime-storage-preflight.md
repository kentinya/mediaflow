# Phase 17 — Runtime Storage Adapters + Read-only Preflight

## Goal

Complete production JSON runtime construction for the already-implemented SMB and S3/R2 Storage
adapters, and add a safe read-only preflight command. Do not redesign Storage adapters or begin
service/API/UI work.

## 1. Runtime configuration

Support Storage `type` values: `local`, `openlist`, `smb`, `s3`, `r2`, and `s3-compatible`.
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

Add `mediaflow storage list` and `mediaflow storage check [STORAGE_ID]`. Listing is static; checking
uses only existing health/connect/list reads, isolates failures, and never mutates Storage.

## 5. Configuration examples

Document complete Local/OpenList/SMB/AWS S3/Cloudflare R2/generic S3-compatible definitions and
required environment variables. Examples contain placeholders only, never working credentials.

## Safety

- Zero Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls.
- Existing DryRun, conflict, attachment, and explicit execute boundaries remain unchanged.
- Do not implement scheduler, API, Web UI, background workers, NFO, or Phase 18.

## Required tests

- Runtime construction for SMB, AWS S3, R2, and generic S3-compatible definitions using fakes.
- Environment secret resolution, missing environment values, and redaction.
- Invalid configuration cases and mutation-free list/check commands.
- Optional real integration tests remain environment-gated; run the complete regression suite.

## Documentation and validation

Update all current docs/examples. Run all tests, formatter, linter, compile check, dependency check,
wheel build, configuration validation, FFprobe/FFmpeg audit, and diff check.

## Final report

Phase result, runtime adapters, preflight, security, regression, changed files, decisions,
remaining work, risks, and recommendation.
