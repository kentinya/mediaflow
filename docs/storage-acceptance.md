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

### Isolated lifecycle results and corrections

These are historical results, not new validation. Original diagnosis/run notes remain at
`865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/storage-acceptance.md`.

| Run | Actual result and scope | Retained non-secret report |
|---|---|---|
| OpenList 19.23.2, 2026-08-22 | FAIL on official loopback v4.2.2 Local driver: empty `content:null,total:0` mapped to INVALID_RESPONSE/IO_ERROR. Preflight created no object; mutation matrix did not run. Isolated container/credential/backend removed. | `/tmp/mediaflow-openlist-v4.2.2-acceptance-20260822.json` |
| OpenList 19.23.3 rerun | ISOLATED PASS after accepting only the consistent empty pair and rejecting malformed totals/content. Fresh v4.2.2 Local driver passed empty-root/lifecycle/no-overwrite/same-service and Local↔OpenList/Organizer Copy/Move/content/size/source/allowlisted cleanup. No third-party-driver or remote atomic certification; fixture destroyed. | `/tmp/mediaflow-openlist-v4.2.2-acceptance-pass-20260822.json` |
| MinIO 19.24, 2026-08-22 | ISOLATED PASS on official loopback `quay.io/minio/minio:RELEASE.2025-07-23T15-54-02Z`: lifecycle/no-overwrite, Local↔S3/S3↔S3 Organizer Copy/Move/content/size/source/cleanup. Generic S3 evidence only, not AWS/R2. | `/tmp/mediaflow-minio-2025-07-23-acceptance-pass-20260822.json` |
| Samba 19.24, 2026-08-22 | FAIL on `servercontainers/samba:smbd-only-a3.21.3-s4.20.6-r1`: real errno EEXIST(17) mapped to IO_ERROR. Transfers did not run and adapter cleanup failed; isolated deployment/backend removed. | `/tmp/mediaflow-samba-4.20.6-acceptance-fail-20260822.json` |
| Samba 19.24.1 rerun | ISOLATED PASS on fresh Samba 4.20.6 root after structural errno mapping and enumeration metadata removed implicit default-port 445 stat. Empty preflight/lifecycle/no-overwrite/Local↔SMB/SMB↔SMB Organizer Copy/Move/content/size/source/cleanup passed. Generated objects/container/share/credential destroyed. Together with MinIO this bounded 19.24 profile passed; no AWS/R2/fault/atomic certification. | `/tmp/mediaflow-samba-4.20.6-acceptance-pass-phase-19.24.1-20260822.json` |

### Samba and MinIO Phase 19.24 command contract

`TEST_REAL_SMB_*` / `TEST_REAL_S3_*` require explicit endpoint, dedicated credentials, Share/Bucket,
relative `mediaflow-acceptance-*` root, exact `DELETE_ONLY_GENERATED_MEDIAFLOW_ACCEPTANCE_DATA`
confirmation and a new absolute `.json` report path. Partial configuration fails closed; no default
prefix or configured media library is consulted. Suites never derive consent from runtime config.

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
