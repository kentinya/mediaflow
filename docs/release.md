# Release validation checklist

MediaFlow does not publish artifacts automatically. A maintainer must review and perform every
release explicitly.

## Quality gate

Run from a clean checkout with a supported Python version (3.11, 3.12, or 3.13):

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
python -m unittest discover -s tests
python -m compileall -q mediaflow tests scripts
python -m pip check
mediaflow --config config/strategy.example.json config validate
mediaflow --config config/mediaflow.phase13.2.example.json config validate
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
git diff --check
```

Build and validate the exact installable artifact in a new isolated environment:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-release.XXXXXX)
python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

The smoke validator checks wheel contents, installs without runtime extras in a new venv outside the
checkout, validates both canonical example configurations, and performs a temporary SQLite database
backup/verify round trip. It never reads configured production Storage or credentials.

## Maintainer review

- Review [Storage Acceptance Matrix](storage-acceptance.md). The bounded repository release profile
  is PASS for isolated Local, Samba, OpenList Local driver, and MinIO S3-compatible behavior. A green
  unit/CI suite alone remains insufficient, and a target deployment must not claim AWS/R2,
  third-party OpenList-driver, remote-atomic, multi-hour-soak, or power-loss certification without
  its own evidence. Any required target row marked `BLOCKED` or `FAIL` blocks that deployment claim.

- Confirm the worktree contains only intended release changes; never include local configuration,
  databases, caches, credentials, logs, or media.
- Review the version and release notes/changelog for the intended compatibility statement.
- Confirm all GitHub Actions matrix jobs and the isolated wheel job passed.
- Validate production configuration with the target version before deployment.
- Create and verify a new runtime database backup before upgrading a running deployment.
- Run the installed target artifact's read-only compatibility check before starting it:

  ```bash
  mediaflow --config /path/to/strategy.json upgrade check \
    --backup /safe/backups/mediaflow-before-upgrade.sqlite3
  mediaflow --config /path/to/strategy.json upgrade rehearse \
    --backup /safe/backups/mediaflow-before-upgrade.sqlite3
  ```

- Review schema compatibility and retain the previous application artifact and database backup.
- Publish/tag only through a separate explicit maintainer action. This repository has no automatic
  upload, deployment, restore, migration rollback, signing, or container publication workflow.

## CI boundary

The GitHub workflow receives read-only repository permission, has explicit timeouts, and uses no
production secrets. Network storage and TMDB tests remain optional/skipped. CI validates software and
example configuration only; it is not evidence that a particular SMB/OpenList/S3/TMDB deployment is
reachable or correctly authorized.

Upgrade preflight accepts only a configured runtime database and explicit local backup. It reports
`READY` for the current schema or `MIGRATION_REQUIRED` for an older mutually matching supported
schema, but performs no migration. A PASS does not stop running services or authorize restore.

Migration rehearsal copies the verified backup to a private temporary SQLite database and opens only
that copy through the artifact's real repository migration path. PASS confirms the tested copy reached
the current Schema with representative record counts preserved; it is not an automatic production
migration or rollback guarantee.

## Offline restore procedure

Restore is recovery-only and never overwrites:

1. Stop every MediaFlow CLI worker, scheduler, API, and notification process.
2. Verify the selected backup with `mediaflow database verify BACKUP`.
3. Manually preserve/move the configured runtime database and its `-wal`, `-shm`, and `-journal`
   sidecars. Do not delete them until recovery is independently confirmed.
4. Run `mediaflow database restore BACKUP --confirm-empty-destination`.
5. Verify the restored configured path, then start one MediaFlow process. If restore reported an old
   supported schema, the normal repository open may perform the existing forward migration.

The command refuses any occupied destination or sidecar and does not detect process liveness. Never
use it as an in-place replacement mechanism.

Automation Job claims are fenced in Runtime schema v14 and cooperative workflow boundaries refresh
their age. This prevents an old Worker from committing over a requeued/later claim, but it does not
prove that an in-flight provider or Storage operation stopped. Before `jobs requeue`, stop and inspect
the Worker, Job/Task history, source, and destination. Never infer safe replay solely from stale age.

On POSIX, every production runtime command holds a shared kernel advisory lease for its lifetime and
restore requires the exclusive lease. Contention is evidence that a cooperating MediaFlow process is
still active and restore fails before staging. This is an additional guard, not permission to skip the
stop-and-verify procedure; unrelated processes and direct library consumers do not participate.
