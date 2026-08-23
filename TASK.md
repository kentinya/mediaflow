# Phase 22.1 — Durable Storage Configuration CRUD Foundation

## Goal

Implement the first bounded Phase 22 CRUD slice for Storage configuration objects. This task adds
validated domain/application behavior and a durable SQLite repository, but does not connect the new
write path to runtime configuration loading, API, Web UI, scheduler, Storage construction, or
scanning/organizing workflows.

## Scope

### 1. Storage configuration model

- Add an immutable managed Storage configuration model distinct from runtime `StorageDefinition`.
- Cover Local, SMB, OpenList, AWS S3, Cloudflare R2, and generic S3-compatible types.
- Validate bounded IDs/names/root paths/options and reject literal secret fields.
- Keep credentials referenced only through validated environment-variable names.

### 2. CRUD and audit service

- Support create, read, list, update, copy, enable, disable, and delete.
- Use optimistic version checking for updates.
- Preserve a Before/After audit record for every successful mutation.
- Delete must be transactionally blocked when Resource/Media Library references exist.
- Unsupported/invalid input must fail without partial writes or audits.

### 3. SQLite repository

- Add a reusable durable repository with configuration-object, reference, and audit tables.
- Keep reference checks and deletes in one transaction.
- Store only redacted audit JSON; never persist rejected literal secrets.
- Expose an internal reference-recording method for future Resource/Media Library CRUD only.

## Boundaries

- No HTTP endpoint, Web UI, CLI, import/export, or runtime JSON loader integration.
- No Resource/Media Library CRUD in this task.
- No Storage adapter construction, health check, network call, scan, plan, or organizer execution.
- No FFmpeg/FFprobe dependency.
- Do not change existing runtime SQLite behavior or migration semantics.

## Required Tests

- Model validation success paths for every Storage family.
- Invalid IDs, roots, options, secret literals, non-JSON values, duplicates, missing objects,
  optimistic-version conflicts, referenced deletes, disabled filtering, copy behavior, and audits.
- Repository transaction rollback/failure behavior.
- Confirm Storage CRUD never constructs a Storage provider and never touches media files.
- Full offline suite and standard quality gates pass.

## Validation

Run the new focused tests, full offline suite, Ruff, compile, dependency/configuration, and
forbidden-dependency/diff checks. Update architecture, configuration, requirements, roadmap,
README, and progress with exact implemented/non-claim boundaries.
