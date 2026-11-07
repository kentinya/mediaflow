# Release validation checklist

MediaFlow does not publish artifacts automatically. A maintainer must review and perform every
release explicitly.

## Release lines

`v1.0.0` is the historical released V1 baseline at `6386e704fa90a1ae3bf90f7d6a3ef62d4e5d2752`, retained on
`release/v1`. The `main` branch is the V2 development trunk and carries package version
`2.0.0.dev0`. Its V2 frontend implementation is active and substantial across the current
Explore, Library and Operations journeys, but this development line is not a V1 release and has
not been released as V2.

The user-authorized 2026-10-24 Git attribution update maps the original release commit
`9562b0c9b09b9b2ac9f34b2187c86469a9ab1782` to the current baseline above with an identical file
tree. The original annotated tag and release history remain in owner-local backups; release
version, code and artifacts retain their existing meaning.

## Current V2 validation boundary

Slice50 is PASS / CLOSED; [Progress](progress.md) retains its original Base, accepted implementation
Head and validation limits, alongside earlier closures. The accepted presentation includes readable
Task details, Storage/library cards and menus, both library pages without page-local trees, nine
main-page transitions, consistent library loading and stable Automation create/edit. These Web-only
changes add no backend, schema or deployment capability. Accepted49 Automation intent and accepted48
flow/rate semantics remain: saved definitions run with confined sources, Task flow is independent
of file results, and execution records read that same durable Task. Closure evidence is not a new
container, external-service or production validation claim.
This is development acceptance, not a V2 release. Current support is fresh initialization
→ submit new work → same-version reopen/restart and permitted safe continuation. Old-task/Job
migration or takeover, cross-version upgrade/rollback, mixed-version writers and V1 support are
excluded. Readable immutable configuration containing retired fields does not add an upgrade promise.

Use [Deployment](deployment.md) for current executable startup, health, backup and same-version
recovery. Earlier V1 upgrade acceptance below remains historical; it is not a current `main` gate
or permission to run an old database with a different artifact. Git push does not publish an image,
tag, GitHub Release or deployment.

## V1 Docker release — historical acceptance

Release version: `1.0.0`.

Slice 29 is the final V1 integration Slice. It ships the repository's first installable
Docker image, `compose.yaml`, and Waitress-backed `api serve-production` command for the four
independent API/Worker/Scheduler/Notification Worker services. The services retain independent
process failure/restart boundaries while sharing one local persistent `/data` volume. The
`wsgiref.simple_server` API listener remains development/trusted-loopback only; production Compose
serving uses the explicitly selected Waitress adapter with a documented TLS/reverse-proxy or LAN
boundary. The Slice health/readiness, restart/fault and upgrade/backup/migration
recovery Tasks and the Task 29.6 release-security/artifact validation were complete at the
accepted Slice29 implementation Head retained in Progress. A Final Review marked Slice 29 `PASS / CLOSED` on 2026-09-08.
This document is not a publication claim; publication, signing and direct deployment remain
explicit maintainer actions.

See [docs/deployment.md](deployment.md) for the current executable image/Compose journey.

The historical V1 Docker acceptance contract included:

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

That historical release did not claim direct Internet exposure, built-in user/password/OIDC identity, SQLite on
remote Storage, Docker Secrets-specific ingestion, Provider switching, additional Metadata Providers,
or external-service compatibility that the validation environment cannot run. Those boundaries remain
explicitly documented as unsupported, post-V1 or `SKIP / UNAVAILABLE` as applicable. That
release was validated for its documented isolated Docker journey; publication, signing and direct
production deployment remain explicit maintainer actions.

## Quality gate

Use a clean checkout with a supported Python version (3.11, 3.12, or 3.13) and install the declared
runtime/development dependencies. [Development Workflow §6](development-workflow.md#6-test-levels)
owns the shared regression commands, applicable Web/native/package/safety gates, execution ownership
and evidence-reuse rules. A release requires the gates appropriate to its exact target source and
artifacts; older Slice acceptance is not a new release run.

Compatibility markers belong to the target artifact and release line. Released V1 `v1.0.0` /
`release/v1` retains runtime schema `33`. For unreleased `main`, the source authorities are
[`SCHEMA_VERSION`](../mediaflow/infrastructure/sqlite_runtime.py),
[`CONFIGURATION_SCHEMA_VERSION`](../mediaflow/infrastructure/sqlite_configuration_management.py)
and the [managed document validator](../mediaflow/application/configuration_snapshot.py).
Read compatibility markers from the installed target rather than copying a mutable development
schema number into a release claim. Current `main` acceptance covers fresh and same-version work;
read-only compatibility tooling does not establish support for older task/schema conversion.

Build and validate the exact installable artifact in a new isolated environment:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-release.XXXXXX)
python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

The smoke validator checks wheel contents, installs without runtime extras in a new venv outside the
checkout, validates both canonical example configurations, and performs a temporary SQLite database
backup/verify round trip. It never reads configured production Storage or credentials.

Current Docker artifact validation includes fresh/security and same-version restart/fault journeys:

```bash
python3 scripts/docker_restart_fault_smoke_test.py
python3 scripts/docker_release_security_smoke_test.py
```

Each harness builds local images only, uses temporary media and a throwaway named
volume, injects only harmless canary/private material, and records `SKIP` when no
Docker engine is available.

The old-image/new-image `scripts/docker_upgrade_recovery_smoke_test.py` belongs to historical V1
upgrade evidence. It is not a required or accepted current V2 gate under the boundary above.

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
- Create and verify a database backup before maintenance; use the same artifact version for
  supported restore/restart and retain the existing database and artifact until verification ends.
- Review the target's schema/readiness and the supported persistence boundary. An unavailable or
  incompatible database does not authorize work or data clearing. Cross-version deployment is
  outside current support; historical upgrade commands are not the recovery path for `main`.
- Publish/tag only through a separate explicit maintainer action. This repository has no automatic
  upload, deployment, restore, migration rollback, signing, or container publication workflow.

## CI boundary

The GitHub workflow receives read-only repository permission, has explicit timeouts, and uses no
production secrets. Network storage and TMDB tests remain optional/skipped. CI validates software and
example configuration only; it is not evidence that a particular SMB/OpenList/S3/TMDB deployment is
reachable or correctly authorized.

Compatibility and rehearsal tools are read-only with respect to the live database. Their reports
do not stop running services, authorize restore or expand current version support. Historical V1
preflight/rehearsal details and successful image-to-image migration evidence remain in Git.

## Offline restore procedure

Current restore is same-version recovery-only and never overwrites:

1. Stop every MediaFlow CLI worker, scheduler, API, and notification process.
2. Verify the selected backup with `mediaflow database verify BACKUP`.
3. Manually preserve/move the configured runtime database and its `-wal`, `-shm`, and `-journal`
   sidecars. Do not delete them until recovery is independently confirmed.
4. Run `mediaflow database restore BACKUP --confirm-empty-destination`.
5. Verify the restored configured path, then start one process using the same artifact version that
   created the supported backup. Other versions/schemas are outside current support; do not rely
   on historical forward-migration examples or clear state to bypass readiness failures.

The command refuses any occupied destination or sidecar and does not detect process liveness. Never
use it as an in-place replacement mechanism.

Task claims and per-effect boundaries remain fenced. Heartbeat freshness, lease expiry, a timeout
or restart never proves an in-flight Provider/Storage operation stopped or had no effects. Inspect
the original Task/item/results and source/target; preserve completed/uncertain evidence. Only the
existing permitted safe continuation can run remaining work. No Job requeue entrance remains.

On POSIX, every production runtime command holds a shared kernel advisory lease for its lifetime and
restore requires the exclusive lease. Contention is evidence that a cooperating MediaFlow process is
still active and restore fails before staging. This is an additional guard, not permission to skip the
stop-and-verify procedure; unrelated processes and direct library consumers do not participate.
