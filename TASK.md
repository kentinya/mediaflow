# Phase 22.0 — Configuration Management Architecture Decision and Domain Skeleton

## Goal

Establish the Phase 22 configuration-management foundation without implementing all CRUD. Decide
the storage/security boundaries and add a minimal domain/protocol skeleton for the 12 configuration
object kinds and reference-audit behavior.

## Scope

### 1. Architecture decision

- Document the selected configuration source of truth: keep JSON as validated runtime input,
  introduce SQLite as durable configuration-change/audit store, and keep credentials in external
  environment or future Secret Store.
- No literal secret in configuration JSON, audit records, logs, exports, or domain objects.

### 2. Domain skeleton

- Add `ConfigurationObjectKind` enum for the 12 managed object families.
- Add immutable `ConfigurationReferencePolicy` and `ConfigurationChangeAudit` models.
- Add a protocol for future CRUD/reference validation without implementing SQL/HTTP/Storage.

### 3. Safety

- No new Storage/Provider/Planner/OrganizerExecutor construction.
- No configuration write path is activated in this phase.

## Boundaries

- No full CRUD, import/export, UI, SQLite configuration schema, or Phase 22.1.
- Do not redesign runtime JSON loader, Storage adapters, policy engines or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Enum covers the 12 required configuration families.
- Reference policy rejects destructive deletion of referenced objects.
- Audit models redact secret-like fields and carry only safe bounded values.
- Full offline suite and all quality gates pass.

## Validation

Run Phase 22.0, full offline suite, Ruff, compile, dependency, both example configuration
validations, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 22.0 Result

PASS / FAIL

## Architecture Decision

## Domain Skeleton

## Safety

## Regression

## Final Recommendation
