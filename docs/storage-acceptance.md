# Storage Acceptance Matrix

This document is the authoritative Phase 19 Storage acceptance record. Unit tests with fake clients
prove adapter logic but are not evidence that a real service, account, network, filesystem, or
permission set works. The bounded Phase 19 repository profile is accepted only because every row in
that explicitly defined Local/Samba/OpenList-Local-driver/MinIO profile has real isolated evidence.
A target deployment with different services or drivers needs its own required-row evidence before
claiming equivalent production acceptance.

## Status vocabulary

- `ISOLATED PASS`: exercised through the production adapter against an isolated real filesystem or service.
- `UNIT PASS`: automated fake/mock coverage only.
- `BLOCKED`: isolated endpoint, credentials, or destructive test root not supplied.
- `FAIL`: acceptance was executed and a required assertion failed.
- `NOT APPLICABLE`: provider capability intentionally does not support the operation.

## Adapter matrix (2026-08-23)

| Adapter | Read/list/stat | Write/copy/move | Fault injection | Atomic publication | Real acceptance |
|---|---|---|---|---|---|
| Local | ISOLATED PASS | ISOLATED PASS | ISOLATED PASS | ISOLATED PASS for write/copy target visibility | ISOLATED PASS on temporary host filesystem |
| SMB | ISOLATED PASS | ISOLATED PASS | ISOLATED PASS: interrupted source | Not certified; partial target observed | Samba 4.20.6 endurance PASS |
| OpenList | ISOLATED PASS | ISOLATED PASS | ISOLATED PASS: interrupted source | Not certified | ISOLATED PASS: self-hosted v4.2.2 Local driver |
| S3/R2 | ISOLATED PASS for MinIO | ISOLATED PASS for MinIO | ISOLATED PASS: interrupted multipart | MinIO incomplete multipart cleanup PASS | MinIO PASS; AWS/R2 not certified |

Local `write` and `copy` stage in the target directory and publish atomically. A reader sees the old
complete target or the new complete target, not the operation-owned stage. This does not certify
power-loss durability, multi-file transactions, or source+target atomicity.

## Transfer matrix

| Source → destination | COPY | MOVE | Current evidence |
|---|---|---|---|
| Local → Local | ISOLATED PASS | ISOLATED PASS | Temporary real filesystem |
| Local → SMB/OpenList/S3-R2 | ISOLATED PASS | ISOLATED PASS | Samba/OpenList/MinIO isolated matrices |
| SMB/OpenList/S3-R2 → Local | ISOLATED PASS | ISOLATED PASS | Samba/OpenList/MinIO isolated matrices |
| SMB → SMB | ISOLATED PASS | ISOLATED PASS | Samba 4.20.6 production adapter + OrganizerExecutor |
| OpenList → OpenList | ISOLATED PASS | ISOLATED PASS | Self-hosted v4.2.2 with Local driver |
| S3/R2 → S3/R2 | ISOLATED PASS | ISOLATED PASS | MinIO S3-compatible only; AWS/R2 BLOCKED |
| Any cross-storage LINK | NOT APPLICABLE | NOT APPLICABLE | Explicitly rejected |

Cross-storage MOVE is streamed copy, verified by size, then source delete. A write or size failure
preserves the source. A delete failure reports `PARTIAL` and leaves source plus destination. This is
not a distributed transaction and content-hash verification remains future work.

## Real remote acceptance prerequisites

For each SMB, OpenList, or S3/R2 deployment, provide all of the following before running mutations:

1. Dedicated non-production credentials with no access outside the test scope.
2. A dedicated empty share directory, OpenList path, or bucket prefix whose contents may be deleted.
3. Explicit operator confirmation of the exact Storage ID and test root.
4. Permission to create, read, move/copy, and delete generated test objects.
5. A retained report containing adapter/version, operations, failures, cleanup result, and time.

Never use a ResourceLibrary or MediaLibrary root and never run destructive acceptance automatically.
`config/alist.json` and user media remain outside the test boundary unless the operator later supplies
a distinct approved test root.

### OpenList Phase 19.23 command

The acceptance root has no default and its final component must start with
`mediaflow-acceptance-`. Run only after creating and verifying that dedicated empty root:

```bash
TEST_OPENLIST_URL='https://openlist.test.example' \
TEST_OPENLIST_TOKEN='<dedicated-test-token>' \
TEST_OPENLIST_ROOT='/qa/mediaflow-acceptance-openlist' \
TEST_OPENLIST_DESTRUCTIVE_CONFIRM='DELETE_ONLY_GENERATED_MEDIAFLOW_ACCEPTANCE_DATA' \
TEST_OPENLIST_REPORT='/var/tmp/mediaflow-openlist-acceptance.json' \
.venv/bin/python -m unittest tests.test_openlist_real_acceptance
```

Before mutation, the suite requires the production adapter to prove the approved root is a directory
with zero listed items. It then creates one random `run-*` child, rejects pre-existence, deletes only
its allowlisted generated names, and fails cleanup if any unknown object appears. The report target
must be a new absolute local `.json` path in an existing directory; publication never overwrites and
contains no endpoint or credential. The matrix covers production-adapter lifecycle plus
Local→OpenList, OpenList→Local, and OpenList→OpenList COPY/MOVE.

### OpenList Phase 19.23.2 isolated result

On 2026-08-22 the suite was run against a loopback-only official
`openlistteam/openlist:v4.2.2` container with a generated credential and a Local driver rooted in a
new temporary directory. Health and root stat succeeded. The empty-root list returned the real v4.2.2
shape `data.content = null` with `data.total = 0`; production `HttpOpenListClient.list_page` requires
`content` to be a list and therefore reported `INVALID_RESPONSE` / `StorageErrorCode.IO_ERROR`.

Result: `FAIL`. The fail-closed preflight created no remote object, cleanup required no remote deletion,
and Local↔OpenList/OpenList↔OpenList mutation rows were not run. The container, credential, token, and
temporary backend were removed. The non-secret report remains outside Git at
`/tmp/mediaflow-openlist-v4.2.2-acceptance-20260822.json`. This failure must be repaired in a separate
task and the complete matrix rerun; it is not OpenList acceptance.

### OpenList Phase 19.23.3 repair and rerun

The infrastructure mapper now accepts the exact empty-directory pair `content: null, total: 0` as an
empty page while rejecting null with inconsistent totals, bool/negative/missing totals, and other
malformed content. A new loopback-only official `openlistteam/openlist:v4.2.2` instance then passed
the full production-adapter matrix: empty-root preflight, lifecycle/no-overwrite, same-service
copy/move, Local→OpenList COPY/MOVE, OpenList→Local COPY/MOVE, OpenList→OpenList Organizer COPY/MOVE,
content/size/source assertions, and allowlisted cleanup.

Result: `ISOLATED PASS` for the self-hosted OpenList service using its Local driver. The container,
credential, token, and temporary backend were removed. The non-secret PASS record is retained outside
Git at `/tmp/mediaflow-openlist-v4.2.2-acceptance-pass-20260822.json`. This does not certify individual
third-party OpenList drivers or remote atomic publication semantics.

### Samba and MinIO Phase 19.24 command contract

Real suites use `TEST_REAL_SMB_*` and `TEST_REAL_S3_*` variables. Each requires explicit endpoint,
credentials, Share/Bucket, a relative `mediaflow-acceptance-*` root, the exact destructive confirmation
`DELETE_ONLY_GENERATED_MEDIAFLOW_ACCEPTANCE_DATA`, and a new absolute `.json` report path. Partial
configuration fails closed; no configured media library is consulted. The former Endpoint-only S3/R2
test with a default `mediaflow-test` prefix has been removed.

### Phase 19.24 isolated result

On 2026-08-22, pinned `servercontainers/samba:smbd-only-a3.21.3-s4.20.6-r1` and official
`quay.io/minio/minio:RELEASE.2025-07-23T15-54-02Z` containers were bound to host loopback with
generated credentials and temporary data.

MinIO passed lifecycle/no-overwrite, Local↔S3 COPY/MOVE, S3↔S3 Organizer COPY/MOVE, content/size/source
assertions, and allowlisted cleanup. This is `ISOLATED PASS` for generic S3-compatible behavior, not
AWS S3 or Cloudflare R2 service acceptance. Its report is retained outside Git at
`/tmp/mediaflow-minio-2025-07-23-acceptance-pass-20260822.json`.

Samba passed connection, empty-root preflight, write/read/stat, then failed no-overwrite error
classification: real `SMBOSError` carried `errno=EEXIST (17)` but `SmbProtocolClient._convert_error`
mapped it to `IO_ERROR`, not `ALREADY_EXISTS`. The fail-fast matrix did not run SMB transfers, and
adapter cleanup also failed, so the temporary backend was removed only with the isolated deployment.
Result is `FAIL`; report: `/tmp/mediaflow-samba-4.20.6-acceptance-fail-20260822.json`. A separate repair
and complete rerun are required before Phase 19.24 can pass.

### Phase 19.24.1 Samba repair and rerun

The SMB client now maps standard errno values structurally, including real Samba `EEXIST` as
`ALREADY_EXISTS`. Directory enumeration consumes metadata already returned by `scandir` instead of
issuing an implicit follow-up stat on default port 445. This keeps loopback/non-default-port
deployments on the configured endpoint and avoids an extra request per directory entry.

A fresh empty root on the pinned Samba 4.20.6 container passed empty-root preflight,
lifecycle/no-overwrite, Local↔SMB COPY/MOVE, SMB↔SMB Organizer COPY/MOVE, content/size/source
verification, and allowlisted cleanup. Result: `ISOLATED PASS`. The non-secret report is retained at
`/tmp/mediaflow-samba-4.20.6-acceptance-pass-phase-19.24.1-20260822.json`; the container, generated
objects, temporary share, and credential were destroyed. Together with the retained MinIO PASS,
Phase 19.24 is PASS for self-hosted Samba and generic S3-compatible MinIO. AWS S3, Cloudflare R2,
provider-specific fault injection, and remote atomic publication are not certified by this result.

### Phase 19.25 endurance and interrupted-transfer result

On 2026-08-23, new isolated Local, Samba 4.20.6, OpenList v4.2.2 with a Local driver, and MinIO
instances ran the same production-adapter profile. Each profile copied 128 deterministic objects and
one 128 MiB object, verified sizes and SHA-256 content, injected a source-stream failure during a
cross-storage MOVE, proved the source remained complete, inspected the destination, then performed a
new explicit retry and allowlisted cleanup. S3 used a 5 MiB multipart part size and the observed
maximum source read was 5 MiB; Local, SMB, and OpenList reads were at most 1 MiB.

All four profiles are `ISOLATED PASS`. Local, OpenList, and MinIO exposed no incomplete destination.
Samba exposed a target smaller than the source; the harness did not treat it as success, deleted only
that generated allowlisted partial target, and then retried explicitly. This records real current SMB
semantics and does not claim remote atomic publication or add production automatic cleanup.

MinIO cleanup left zero objects and zero multipart uploads. All run roots were empty after cleanup;
containers, temporary backends, and credentials were destroyed. Secret-free reports remain outside
Git:

- `/tmp/mediaflow-phase-19.25-local-128x128m-pass-20260823.json`
- `/tmp/mediaflow-phase-19.25-smb-128x128m-pass-20260823.json`
- `/tmp/mediaflow-phase-19.25-openlist-128x128m-pass-20260823.json`
- `/tmp/mediaflow-phase-19.25-minio-128x128m-pass-20260823.json`

This closes the bounded Phase 19 release profile. It is not evidence for multi-hour soak behavior,
service-process termination, host power loss, AWS S3, Cloudflare R2, third-party OpenList drivers,
or content-hash policy in production.

## Deployment-specific limitations (not Phase 19 profile claims)

- AWS S3 and Cloudflare R2 provider-specific real-service matrices.
- Service-process termination, reconnect/rate-limit injection, and multi-hour soak tests.
- Power-loss durability and content-hash verification policy.
