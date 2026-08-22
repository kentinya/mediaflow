# Storage Acceptance Matrix

This document is the authoritative Phase 19 Storage acceptance record. Unit tests with fake clients
prove adapter logic but are not evidence that a real service, account, network, filesystem, or
permission set works. Phase 19 is not production-accepted until every required deployment row has
real isolated evidence.

## Status vocabulary

- `ISOLATED PASS`: exercised through the production adapter against an isolated real filesystem or service.
- `UNIT PASS`: automated fake/mock coverage only.
- `BLOCKED`: isolated endpoint, credentials, or destructive test root not supplied.
- `FAIL`: acceptance was executed and a required assertion failed.
- `NOT APPLICABLE`: provider capability intentionally does not support the operation.

## Adapter matrix (2026-08-22)

| Adapter | Read/list/stat | Write/copy/move | Fault injection | Atomic publication | Real acceptance |
|---|---|---|---|---|---|
| Local | ISOLATED PASS | ISOLATED PASS | ISOLATED PASS | ISOLATED PASS for write/copy target visibility | ISOLATED PASS on temporary host filesystem |
| SMB | UNIT PASS | UNIT PASS | UNIT PASS | Not certified | BLOCKED: no isolated real share |
| OpenList | UNIT PASS; ISOLATED FAIL | UNIT PASS; real rows NOT RUN | UNIT PASS | Not certified | FAIL: v4.2.2 empty-directory DTO rejected by production adapter |
| S3/R2 | UNIT PASS | UNIT PASS | UNIT PASS | Not certified | BLOCKED: no isolated bucket/prefix |

Local `write` and `copy` stage in the target directory and publish atomically. A reader sees the old
complete target or the new complete target, not the operation-owned stage. This does not certify
power-loss durability, multi-file transactions, or source+target atomicity.

## Transfer matrix

| Source → destination | COPY | MOVE | Current evidence |
|---|---|---|---|
| Local → Local | ISOLATED PASS | ISOLATED PASS | Temporary real filesystem |
| Local → SMB/OpenList/S3-R2 | UNIT PASS | UNIT PASS | OpenList NOT RUN after preflight FAIL; others BLOCKED |
| SMB/OpenList/S3-R2 → Local | UNIT PASS | UNIT PASS | OpenList NOT RUN after preflight FAIL; others BLOCKED |
| SMB → SMB | UNIT PASS | UNIT PASS | BLOCKED real share |
| OpenList → OpenList | UNIT PASS | UNIT PASS | NOT RUN after isolated preflight FAIL |
| S3/R2 → S3/R2 | UNIT PASS | UNIT PASS | BLOCKED real bucket/prefix |
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

## Remaining blocking gates

- Real SMB, OpenList, and S3/R2 adapter matrices.
- Cross-provider transfer matrix using isolated endpoints.
- Provider-specific interrupted upload/copy/move and reconnect/rate-limit injection.
- Long-duration and large-object testing.
- Power-loss durability and content-hash verification policy.
