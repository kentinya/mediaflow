# Phase 19.14 — Cooperative Runtime Maintenance Lock

## Goal

Prevent a confirmed offline restore from running concurrently with other cooperating MediaFlow CLI,
API, Worker, Scheduler, or maintenance processes that use the same configured runtime database.
Introduce a process-lifetime shared/exclusive lock without changing database or media behavior.

## 1. Runtime lease adapter

- Add a local infrastructure lease derived deterministically from `persistence.databasePath`.
- Normal runtime commands acquire a non-blocking shared lease for their complete process operation.
- `database restore` acquires a non-blocking exclusive maintenance lease before backup validation or
  destination staging and holds it through publication/verification output.
- Multiple shared holders are allowed; an exclusive holder conflicts with every shared/exclusive holder.
- Lock contention fails immediately with a clear message and never waits indefinitely.
- Use kernel-released advisory locks so crashes release ownership. Keep one stable owner-only empty lock
  file and never delete it during ordinary release, avoiding inode split races.

## 2. CLI integration

- Apply shared leases to commands that access the runtime database or long-lived runtime services.
- Keep `config validate`, token generation, credential status, and Storage preflight free of runtime
  lease/file creation because they do not use the runtime database.
- Validate restore confirmation before acquiring/creating a lease.
- Release leases in `finally` on success, validation error, exception, cancellation, and service exit.
- Do not place lock behavior inside Parser, strategy engines, SQLite repositories, or media Storage.

## 3. Platform and safety

- Implement safe POSIX advisory locking first; on unsupported platforms fail restore clearly rather
  than pretending exclusivity. Normal read-only/non-restore compatibility must remain documented.
- Refuse symlink/non-regular lock paths and invalid/missing/symlink parents; never follow a lock symlink.
- Lock files contain no PID, path, token, configuration, or secret data and use owner-only permissions.
- Locking performs zero media Storage mutation and never changes Runtime records or backup files.
- This is cooperative MediaFlow process detection, not arbitrary OS-process detection.

## Required tests

- Multiple shared leases coexist; exclusive versus shared and exclusive versus exclusive fail fast.
- Leases release after normal close, exception, cancellation-equivalent unwinding, and subprocess exit.
- Lock path/mode/content, symlink/non-regular/parent rejection, and crash-release behavior.
- Runtime CLI command holds a shared lease for its operation; restore holds exclusive before service call.
- Restore contention creates no destination/temp file and leaves backup/Runtime unchanged.
- Missing restore confirmation and exempt config/token/credential/storage commands create no lock file.
- Errors/output contain no secrets; media Storage/provider/workflow behavior remains unchanged.
- Installed-wheel smoke validates shared/exclusive contention and successful restore after release.
- Full existing regression and quality gates pass.

## Documentation

Update README, requirements, architecture, progress, roadmap, release checklist, and configuration
operations documentation with cooperative-lock semantics and platform limitations.

## Out of scope

Killing processes, distributed/network locks, Windows-equivalent exclusive restore support, automatic
maintenance mode, replacing existing databases, rollback, service orchestration, API/UI restore,
remote restore, deployment, and media Storage locking.

## Final report

## Phase 19.14 Result

PASS / FAIL

## Runtime Lease

## Restore Exclusion

## CLI Integration

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
