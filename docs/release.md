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
