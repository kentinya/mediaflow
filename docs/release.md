# Release validation checklist

MediaFlow does not publish artifacts automatically. A maintainer must review and perform every
release explicitly.

## V1 Docker release target

The repository is not yet a Docker release. Slice 29 is the final V1 integration Slice and must
deliver one immutable MediaFlow image with Compose services for API, Worker, Scheduler and
Notification Worker. The services must retain independent process failure/restart boundaries while
sharing one local persistent `/data` volume. The current `wsgiref.simple_server` API listener remains
development/trusted-loopback only; production serving requires an explicitly selected production
WSGI server and a documented TLS/reverse-proxy or LAN boundary.

The Docker acceptance contract includes:

- fresh-volume bootstrap from only a database locator and environment-owned API-principal references;
- explicit media bind mounts and container-visible Local Storage paths;
- non-root UID/GID, ownership, permission and no-host-root/no-Docker-socket assertions;
- bounded liveness, readiness and business/runtime health checks with no Storage/Provider/mutation
  side effects;
- intended network-port exposure and secret/private-config/image scans;
- fresh-volume setup, image startup, Compose integration and `docker compose restart` persistence;
- old-image/new-image schema migration, migration failure fail-closed behavior and retained backup;
- no duplicate scheduled occurrence, no stale-owner overwrite and no automatic uncertain-mutation
  replay after restart.

This target does not claim direct Internet exposure, built-in user/password/OIDC identity, SQLite on
remote Storage, Docker Secrets-specific ingestion, Provider switching, additional Metadata Providers,
or external-service compatibility that the validation environment cannot run. Those boundaries remain
explicitly documented as unsupported, post-V1 or `SKIP / UNAVAILABLE` as applicable. The current
repository is still pre-Docker production release; the target is owned by Slice 29.

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

The current runtime and configuration-management compatibility markers are implementation facts,
not release labels: runtime SQLite schema `33`, configuration-management schema `10`, and managed
configuration document schema `1`. A release claim must be tied to the actual migration and upgrade
evidence for the target revision, not to an old migration number.

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

Automation Job claims are fenced by the current runtime persistence model and cooperative workflow
boundaries refresh their age. This prevents an old Worker from committing over a requeued/later claim,
but it does not prove that an in-flight provider or Storage operation stopped. Before `jobs requeue`,
stop and inspect the Worker, Job/Task history, source, and destination. Never infer safe replay solely
from stale age.

On POSIX, every production runtime command holds a shared kernel advisory lease for its lifetime and
restore requires the exclusive lease. Contention is evidence that a cooperating MediaFlow process is
still active and restore fails before staging. This is an additional guard, not permission to skip the
stop-and-verify procedure; unrelated processes and direct library consumers do not participate.
