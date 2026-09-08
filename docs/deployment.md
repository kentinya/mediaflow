# MediaFlow Docker deployment

This document covers the Task 29.2 deployment boundary: one installable image,
four independent Compose services, production WSGI serving, a persistent local
`/data` volume, and explicit container-visible media mounts.

The Slice's full health/readiness model, restart fault matrix, backup/upgrade
migration rehearsal, and release-security acceptance are separate later Tasks.
This runbook does not claim them.

## Boundary

- One image runs the installed `mediaflow` package. The image runs as UID/GID
  `10001:10001` by default and never needs root.
- `compose.yaml` defines exactly `api`, `worker`, `scheduler`, and
  `notification-worker`. Each service runs one MediaFlow command. No service
  starts another service and no long-lived supervisor is embedded.
- The API command is `mediaflow api serve-production --host 0.0.0.0 --port 8080`,
  which uses Waitress. The standard-library `wsgiref.simple_server` path remains
  `api serve` and is development/trusted-loopback only.
- A local named volume is mounted at `/data`. SQLite, history, managed
  configuration evidence, Task/Job/Result state, notifications, audit and logs
  must be configured under `/data`.
- Media Storage roots are separate bind mounts at `/media/incoming`
  (read-only) and `/media/organized` (read-write). Host `/`, the Docker socket,
  `/data`, and arbitrary unmapped paths are unsupported.
- Deployment secrets are values in a host-owned environment file mounted at
  `/run/mediaflow/deployment.env`. Compose source and rendered Compose output
  contain only the file path and variable references, never secret values.

## Prerequisites

- Docker Engine with Compose v2.
- A deployment configuration produced from the canonical example:

```bash
python3 scripts/make_deployment_config.py --output config/mediaflow.json
```

Edit `config/mediaflow.json` if your library layout differs. The generated file
uses `/data/mediaflow.sqlite3`, `/data/history.jsonl`, `/media/incoming`, and
`/media/organized`. `config/mediaflow.json` is Git-ignored.

- A deployment-owned environment file. Copy
  [deploy/mediaflow.env.example](deploy/mediaflow.env.example) to
  `.env.mediaflow`, replace the placeholder, and make the file readable by the
  container UID/GID:

```bash
cp deploy/mediaflow.env.example .env.mediaflow
# Replace MEDIAFLOW_API_TOKEN with a generated token, then:
chown 10001:10001 .env.mediaflow
chmod 0440 .env.mediaflow
```

The API token should be generated with `mediaflow api token generate` or another
cryptographic random source. Optional `TMDB_ACCESS_TOKEN` and
`MEDIAFLOW_WEBHOOK_SECRET` references are only needed when the corresponding
capability is enabled in configuration.

- Explicit media directories:

```bash
mkdir -p media/incoming media/organized
chown 10001:10001 media/incoming media/organized
chmod 0750 media/incoming media/organized
```

Media roots must exist before `docker compose up`; the Compose bind mount uses
`create_host_path: false`, so a missing mount is a bounded error instead of a
silently created empty directory.

## Build and start

```bash
docker compose build
docker compose up -d
docker compose ps
```

`MEDIAFLOW_IMAGE`, `MEDIAFLOW_CONFIG_FILE`, `MEDIAFLOW_ENV_FILE`,
`MEDIAFLOW_SOURCE_MEDIA_ROOT`, `MEDIAFLOW_TARGET_MEDIA_ROOT`,
`MEDIAFLOW_API_BIND`, `MEDIAFLOW_API_PORT`, `MEDIAFLOW_UID`, and
`MEDIAFLOW_GID` are optional overrides. Defaults are shown in `compose.yaml`.
The default host API bind is `127.0.0.1`; set `MEDIAFLOW_API_BIND=0.0.0.0` only
when the host network is a trusted LAN or the port is behind an HTTPS reverse
proxy. MediaFlow does not provide TLS.

The container entrypoint performs a bounded preflight before each command: it
verifies the config file and `/data` are present and writable, checks that every
configured Local Storage root is a mounted directory with the intended
read-only/read-write access, rejects host-root and Docker-socket paths, and only
for the API command verifies that the referenced API token environment value is
present. Preflight never scans media, calls a Provider, creates a Job or Task,
sends a notification, or mutates Storage.

## Verify

```bash
curl -i http://127.0.0.1:8080/health
curl -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  http://127.0.0.1:8080/api/v1/jobs
```

Open `http://127.0.0.1:8080/ui/` in a browser and enter the API token in the
Operator console.

Restart one service without replacing state:

```bash
docker compose restart api
docker compose ps
```

The named `/data` volume survives service restarts. Jobs, Tasks, configuration
revisions, notification rows, audit and operational state remain durable.

## Failure and recovery

- **Missing config or environment file:** Compose reports the bind source path
  before starting the container. Create the file and retry.
- **Missing media root:** Compose/container preflight reports the missing mount
  path. Mount the intended directory or correct the variable, then retry.
- **Inaccessible `/data` or media path:** preflight reports the exact directory
  and whether it must be readable or writable. Fix UID/GID ownership or mount
  authority and retry; MediaFlow never falls back to root, another path, or the
  Docker socket.
- **Missing API token:** the API preflight names the referenced environment
  variable and tells you to provide it in the mounted deployment environment
  file. Secret values are never echoed.

## Secret and output hygiene

Never commit `.env.mediaflow`, `config/mediaflow.json`, host media paths,
databases, logs, caches, or private deployment material. When sharing rendered
Compose output, use `docker compose config --no-interpolate`; values from the
mounted environment file are never part of Compose rendering.

## Isolated smoke acceptance

The smoke harness builds the exact image and runs an isolated project with
temporary media and a throwaway named volume:

```bash
python3 scripts/docker_smoke_test.py
```

It verifies four services, authenticated API/Web reachability, a durable job
after an API restart, non-root execution, secret-free output, and a missing
media-mount failure. If no Docker engine is present it prints `SKIP`.
