# Phase 14 — Persistent FileIndex + Recoverable Task Foundation

## Goal

Make the existing configuration-driven organizer durable across process restarts without
redesigning any accepted strategy engine. This phase covers persistence, recovery, retry selection,
and per-file execution locking only.

## Existing pipeline

```text
ResourceLibrary Scanner → Parser → Recognition → Metadata → Naming → Classification
→ OrganizePlan → OrganizerExecutor → Result
```

Do not move business decisions into Task orchestration or repositories.

## Required implementation

### 1. Runtime persistence configuration

Support:

```json
"persistence": {"databasePath": ".mediaflow/mediaflow.sqlite3"}
```

- Use the documented safe application-local default when omitted.
- Configuration validation validates the value without creating files/directories.
- Runtime processing may create the database parent when opening persistent state.
- Never persist secrets.

### 2. Persistent FileIndex wiring

- Reuse `SQLiteFileIndexRepository`; do not duplicate FileIndex models or Scanner logic.
- Production `mediaflow scan`, `preview`, and `organize` use the configured persistent index.
- Developer `strategy-test` may retain its isolated in-memory index.
- Separate process runs retain New/Modified/Unchanged/Missing and stability evidence.
- Failed/cancelled/limited scans preserve Missing-reconciliation safety.

### 3. Durable task and item model

Add domain records and repository ports for:

- Task: ID, command/mode, status, execute flag, timestamps, totals, error.
- TaskItem: Task ID, Storage ID, ResourceLibrary ID, source path, stage/status, attempts,
  plan ID, destination Storage/path, execution status, error, timestamps.
- ResultRecord: stable identity, RecognitionType, provider/provider ID, policy IDs, operation,
  source/destination, final status, error.

Use one SQLite infrastructure adapter with an explicit schema version/migration table.

### 4. State and recovery rules

- Persist task/item state at meaningful orchestration boundaries.
- Batch failure does not stop later items.
- Active tasks left by process termination are discoverable and recoverable.
- Recovery never blindly repeats a successful Storage mutation.
- Terminal success/skipped/dry-run items are not retried.
- Partial/failed items require explicit retry/resume.
- Cancellation stops new items and persists Cancelled/PartialSuccess accurately.

### 5. File operation lock

- Identity is `StorageID + normalized Storage-relative source path`.
- Prevent two active tasks from organizing the same source concurrently.
- Acquire/release through a domain port and persist atomically.
- Reclaim stale locks only through explicit recovery rules.
- Lock failure produces zero Storage mutation.

### 6. CLI

Keep existing commands and default DryRun behavior. Add:

```text
mediaflow tasks list
mediaflow tasks show TASK_ID
mediaflow tasks resume TASK_ID [--execute]
mediaflow tasks retry-failed TASK_ID [--execute]
```

- Resume/retry remains DryRun unless the original task was execute-authorized and the user again
  supplies `--execute`.
- Stored state never grants implicit future mutation authority.
- Print stable task/item summaries and clear recovery errors.

### 7. History compatibility

- Preserve `OperationHistoryRepository` and JSONL compatibility.
- Do not migrate or delete user history silently.
- Persistent Task/Result storage may coexist with JSONL history in this phase.

## Safety

- Scanner through Planner remain read-only; only OrganizerExecutor mutates Storage.
- DryRun and configuration validation produce zero Storage mutation.
- No overwrite, silent delete, or implicit operation fallback.
- Recovery/retry requires an explicit command and fresh `--execute` authorization.
- RecognitionType C remains C while reusing downstream A policies.

## Required tests

### Persistence

- Default/custom database path; config validation creates no database.
- SQLite schema version initialization and reopen.
- FileIndex and cross-scan stability/Missing semantics survive reopen.

### Tasks and results

- Task/TaskItem lifecycle and Unicode ResultRecord persistence.
- Partial batch continues and persists later items.
- Interrupted active task is discoverable/recoverable.
- Completed items are never retried; retry-failed selects only failed/partial items.
- Resume/retry without fresh `--execute` performs DryRun.

### Locks

- Same Storage/path cannot be acquired twice.
- Different Storage IDs or paths do not conflict.
- Release and explicit stale-lock recovery.
- Lock conflict causes zero Storage mutation.

### Regression

Run Parser, Recognition/C, Metadata/CandidateMatcher, Naming, Classification, Planner, Executor,
Strategy CLI, Scanner/FileIndex, all Storage adapters, and DryRun regressions.

## Documentation

Update README, configuration, architecture, progress, roadmap, and config examples. Document
database ownership, schema versioning, recovery semantics, CLI commands, and limitations.

## Out of scope

Do not implement conflict UI/overwrite approval, attachments, NFO, SMB/S3 JSON runtime construction,
Scheduler, REST API, Web UI, or any Phase 15+ behavior.

## Validation

Run all tests, formatter, linter, compile check, dependency check, build, configuration validation,
FFprobe/FFmpeg audit, and diff check. Fix every Phase 14 failure before reporting PASS.

## Final report

## Phase 14 Result

PASS / FAIL

## Persistence

## Recovery

## Locking

## CLI

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
