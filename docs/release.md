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

[Slice54](https://github.com/kentinya/mediaflow/blob/05b51268f60f8cc932f6c71d9cfa1efac1227b3e/SLICE.md#a-final-review--pass--closed) is the latest accepted development Slice,
**PASS / CLOSED** on 2026-11-11. Original Base
`e43a40674eb14aa12615a440a348fe675cd50c4e` through accepted implementation
`aef044e51dc91655372bf5fe39c6116da976c3b4` delivers the seven Rules families' Add/Copy/Edit
cards, readable settings/object-local tests and Overview-only complete-flow checking. The A-for-B
exception covered first-Task planning only; B review and A Final Review were independent.

The [fixed B report](https://github.com/kentinya/mediaflow/blob/9220f34420bc4807d4c0bbbe98cf7dece5f100dd/TASK.md#b-final-task-review) records Python 2678 tests OK
(7 optional external-service/endurance skips), 1516 Web unit tests and 268 default browser tests
passing, plus real-Python Rules/recovery/consumer journeys, quality checks, fresh Web assets and
wheel/installed-consumer smoke. Wheel SHA-256:
`778d2ab258f0d4eaa7b7964eb5cff49c7342e5bad6ddfc7858d461bdd9dce338`.
A independently repeated real-Python/temporary-SQLite Rules and recovery journeys, including a
real published Save with its response lost: refresh retained the original request and exactly one
PUT was sent. Desktop/narrow/short-window visual evidence was reviewed.

Root Ruff's pre-existing untracked-script error remains beside passing tracked-source checks.
Automation's first 34-pass/one-failure run stopped on list/authority reread timing before its
intended second request; the original trace, isolated passing case and final 35-pass run remain
recorded. No test assertion, timeout or retry setting was weakened. Raw evidence remains local at
`.git/validation-evidence/aef044e5/task54-1-b/` and
`.git/validation-evidence/aef044e5/slice54-a/`; it is not remote CI. No broad Docker matrix was
applicable to this Rules frontend change; no production external-service validation or V2 release
is claimed. Later documentation-only reconciliation changes no executable validation inputs.

The [Task Center in-place continuation correction](https://github.com/kentinya/mediaflow/blob/b199b2dd4ba76a5f804cea0d2280b2707f54d357/TASK.md#patch-20261113-3--b-pass)
passed independent B T4 review on 2026-11-14: Base
`1c625220b9552bd1e75bfd351a54ddb524ff3e65` through reviewed Head
`218e6bf6213fbec538056e9271a95734d784c1d4`. Continue opens the shared organizer above the
preserved Task Center list/detail, using the exact Task's backend preparation association.
The standalone receiving page/route is removed. Background Task-detail read failure retains the
opened card, unsaved choices and original Execute reconciliation. Close, keyboard/focus,
Back/Forward, reload/re-authentication and exact admission handoff were verified.

Acceptance recorded Python 2686 tests: 2678 passed, 7 optional external-service/endurance skips
and 1 failure reproduced at Base. Web unit tests passed 99 files/1561 tests; default Node browser
tests recorded 273 passes and 3 failures, all reproduced at Base. The Python failure is an existing
scheduling-kernel consumer whitelist omission; Node failures are the existing exact file-name
column-header locator and two Python-only year-search tests included by the Node configuration.
The four required real-Python browser specs passed 56 cases; the two year-search cases passed
under their existing Python configuration. Critical continuation, normal/reduced-motion keyboard
and retained-background checks, three viewport reviews, quality/configuration/build checks and
fresh wheel/outside-source installation smoke passed. The full suites are not all green; no
assertions were weakened. Detailed failures, commands and artifact identities remain in the fixed
report. Raw evidence is local at `.git/validation-evidence/218e6bf6/patch-20261113-3-b/`, not remote
CI. No container path changed, so the broad Docker matrix was not applicable. The existing skips,
production-service limits and remaining non-blocking read-error copy issue remain disclosed.
This standalone acceptance preserves Slice54's closure and makes no V2 release claim;
documentation-only successors change no executable validation inputs.

The [Files/MediaLibrary browse-interaction correction](https://github.com/kentinya/mediaflow/blob/53bcc0a3d6e6506bec23dfa92aa35e27cc1864f5/TASK.md#patch-20261113-2--b-pass)
passed independent B T3 review on 2026-11-13: Base
`9811df4559d94db5b648f6152476f39035a12ae5`, reviewed Head
`14da49b8489e511a8ea588a40f7a10a869522c05`, product checkpoint
`a2effc4b0ed4503d230ff9b684d3d1e869793e95`. It removes the Files fixed blue notice,
adds list/grid interaction and selection feedback, current-page name/size sorting and accurate
pointer/keyboard column widths. Directory changes, paging and read retries retain session settings;
full page reload restores defaults. No backend, permission or Storage protocol changed.

Acceptance passed 106 affected Web unit tests, 71 Node browser tests, 6 real-Python live-list tests
and 4 real-Python rename/delete tests, plus Web type/lint/format/build and governance checks.
Desktop, 390px and short-window interactions and reduced-motion were inspected. Initial concurrent
browser runs had trace-artifact ENOENT failures (Node: 69 passed/2 failed; direct: 3 passed/1 failed);
unchanged tests passed with isolated output directories (71 and 4). The fixed review retains the
prior two product blockers, their corrections and both initial/repeated results. Raw logs/screenshots
remain local at `.git/validation-evidence/14da49b8/patch-20261113-2-b/`. These T3 checks add no
whole-repository, wheel, Docker or production-service validation. Documentation-only successors
change no executable inputs; this is development acceptance.

The [per-file decision and reanalysis correction](https://github.com/kentinya/mediaflow/blob/56a84e9e171400e77595678e6b77700bfe3cc9ee/TASK.md#patch-20261112-1--b-pass)
passed independent B T3 review on 2026-11-12, from Base
`32bb37262777ae945deb8af4a51d9109876ca804` through reviewed Head
`598bd9726adcf1058a9e8736c582b8c62db0d21c`. Files and Task recovery use one save/reanalysis
action; a saved decision refused analysis retries analysis only, accepted work waits, and the
adopted plan precedes optional correction. Acceptance passed 88 affected Web unit tests,
28 Python integration tests and 26 distinct real-Python browser cases, plus affected quality/build
checks and desktop/narrow/short-window review. The real queue-full → reload/re-authenticate →
analysis-only continuation → lost-response reconciliation → explicit confirmation → Worker result
journey preserved the successful sibling. B updated browser actions for the new disclosures/state
and one exact table-cell locator; original assertions of effects and non-replay remain. Initial
stale-action, fixture-order and locator failures remain in the fixed report and local evidence at
`.git/validation-evidence/c940519b/patch-20261112-1/`.

The [duplicate Organize execution-page removal](https://github.com/kentinya/mediaflow/blob/f3bca4cf72a8cdaa15f5646f13d72f45ad954678/TASK.md#patch-20261112-2--b-pass)
passed independent B T3 review on 2026-11-13, from Base
`dc2eec67d619bc2e06de5eca0900325a7906fbfd` through reviewed Head
`114078829ed4f3820818cc219007c4b07af1ebdf`; product checkpoint
`1b7e23e72f45f4f8c02372cc120991009808f07a`. Results use existing Task detail/file evidence,
same-Task confirmation refreshes it, and former execution-page links open the exact linked Task.
Acceptance passed 219 affected Web unit tests, 50 Node browser tests and 61 real-Python browser
tests on fresh per-spec instances, plus Web quality/build and desktop/390px review. The initial
combined Python-browser command had 24 passed, 3 failed, 1 interrupted and 33 not run because
earlier specs changed the shared fixture population/source context. The unchanged specs then
passed separately, including all three failed cases; the combined run remains a failed result.
Its logs/traces and final runs remain local at
`.git/validation-evidence/11407882/patch-2-b/`.

The [Task evidence and record deduplication](https://github.com/kentinya/mediaflow/blob/e8d7d33ff2a3d421cabbab952e15bcfc1a78ca19/TASK.md#patch-20261113-1--b-pass)
passed independent B T3 review on 2026-11-13, from Base
`31f4b56936831699f75590f5afd49d58d630ba9c` through reviewed Head
`5e809ac85a700762379950b8b076d27e58d66fa4`; product correction
`ce09e116c82db577611443e0141aa5ba25409190`. File evidence keeps one current conclusion,
one history entry per Result and one technical disclosure; identical failure/checkpoint next
steps appear once, distinct values retain their source. Four-type recovery and record/export access
remain. Acceptance passed 123 affected unit tests, 42 distinct Node browser cases and 56 real-Python
browser cases on fresh per-spec instances, plus Web quality/build and three-viewport review.
The Node first run had 41 passes and one B-authored stale-label assertion failure; after correcting
that assertion, both added cases passed. The native mixed-task unknown-effect fixture returns
inconsistent Result fields and shows the same unavailable boundary at Base and candidate;
unverified-effect presentation was checked with the existing Node case. Equal-status history and
different-next-step cases use fake responses through existing reads. Original failures, exact
commands and limits remain in the fixed report; raw evidence stays local at
`.git/validation-evidence/b9d9fc03/patch-20261113-1-b/`.

These three corrections used temporary SQLite/Local media and fake Providers. Their T3 acceptance adds
no full-repository, wheel, Docker or production-service validation; earlier Slice acceptance
identities and release status remain unchanged. Subsequent documentation-only reconciliation
preserves the tested executable inputs. Local evidence paths are not GitHub downloads.

The [metadata correction search-year fix](https://github.com/kentinya/mediaflow/blob/d1631be651eefc5ed9c0b1bb80dcb195cf921cda/TASK.md)
passed B T3 review on 2026-11-11, from Base
`e9241d484e33ccb0b1a8def2ab81c17cb1a3d577` through reviewed Head
`09f55d4be864410a28d22bea125ef4432aceb88c`. Files and Task Center correction searches use
the current year, including an explicitly cleared year; invalid years show a direct correction
action. Acceptance passed 142 Python tests, 41 affected Web unit tests and 55 real-Python browser
tests, plus affected Python quality, Web type/lint/format and fresh production-asset build checks.
B applied only mechanical formatting after Developer's business fix and verified unchanged syntax
trees. The fixed report retains the original formatting failures, corrected command and earlier
inconclusive supplementary probe. Raw evidence remains local at
`.git/validation-evidence/09f55d4b/patch-20261111-1-b/`. Browser journeys used temporary
SQLite/Local roots and a fake Provider; TV search and continuation were checked through the real
API/Worker rather than a separate TV browser journey. This T3 acceptance adds no new full-suite,
wheel, Docker or production-service validation. Subsequent documentation changes preserve these
execution inputs and the earlier Slice acceptance identities.

The [Task preparation-entry and status-spacing correction](https://github.com/kentinya/mediaflow/blob/eced270336a93e93c128fbf274eb0537effbaed2/TASK.md#b-final-review--patch-20261111-5-pass)
passed independent B T3 review on 2026-11-11, from Base
`436117e0588d30794dc3ee17d4fc1d0988a79442` through reviewed implementation
`408b5303cdabad202188ed252ceaa741159cdeaa`. Ended Task details show results and inline evidence
without the preparation section or summary/restart buttons. Eligible continuation and existing exact
historical addresses still open the shared organizer, with readable status-text spacing.
Acceptance passed 120 affected Web unit tests, 40 Node browser tests and 18 real-Python browser
tests, plus Web type/lint/format/build checks. The actual Files → leave → Task Center → continue →
one confirmation → Worker completion journey and a historical address captured from that journey
were verified; desktop, narrow and short-window views were inspected. The fixed review retains
commands, non-failure output and local evidence at
`.git/validation-evidence/408b5303/patch-20261111-5/`. These isolated local checks add no full-repository,
wheel, Docker or production-service validation. Later documentation reconciliation changes no
product source, tests or build inputs; Git push does not constitute a V2 release.

Prior [Slice53 acceptance](https://github.com/kentinya/mediaflow/blob/8bc3ef905a76b96ef8ec327154b92e9b9972ea05/SLICE.md#closure-packet-and-a-final-review) remains unchanged,
**PASS / CLOSED** on 2026-11-10. Its original Base is
`95c24cd0a3cc51acd6143e37e72371445cb15a72`, accepted implementation
`8c1b2b1e262d483b594e99a06ad67e747b13bfa4`, reviewed through
`8482d77d3d7db5b89edbaca4022c1bf6f154ca5e`. Files uses per-file review/correction and one exact
subset confirmation, then opens the exact Task detail. Original unknown-request reconciliation
remains fixed while an unselected sibling is reanalyzed. The user authorized the B reviewer to
perform final A review; the role exception is explicit in the Contract.

B ran Python full regression (2678 tests / 7 skips / one Task-heading documentation failure), then
corrected that heading and passed all 28 document-consumer checks; Web unit 1495 and Node E2E 268
passed. Required real-Python journeys and A's fresh eight-test dialog run passed. Root Ruff's
pre-existing untracked script error remains disclosed beside passing tracked-source checks.
The accepted isolated wheel matches all 170 Python source files; installed-consumer smoke passed.
Initial stale build output and its rejected artifact remain in the local evidence record. These
results retain the exact-source and local-environment limits in the Contract; they are development
acceptance, separate from a V2 release or container/production validation.

Prior [Slice52 acceptance](https://github.com/kentinya/mediaflow/blob/19a458eb6c1a6afb8693d2757755487a58213a4f/SLICE.md#closure-packet-and-a-final-review), **PASS / CLOSED** on 2026-11-08, remains unchanged.
Its original Base is `9aa6054e0a2f624b9fb5c0e0fa8d70b232a6cfa8`, with reviewed implementation
`f5409da41191c6e4bbf238bb7def601229fc59dc`. It refines Explore layout/detail/pagination and
all nine main-page read transitions, including both library refresh cases, and retires the old
Automation Open Web journey. Current create/edit/Copy/Run once, shared API/CLI and history remain.
[Progress](progress.md) retains original acceptance identities, deferrals and fixed A/B reports;
those reports disclose actual failures, reuse and local-only evidence rather than a whole-suite claim.

The subsequent [standalone Explore correction](https://github.com/kentinya/mediaflow/blob/6220e369b4f8b7830a8a67ae9c8a6a3fd6e81134/TASK.md)
passed B review at implementation `e2bb72d8c191d34586a90ff49577680107b0295c`: labelled filters,
compact TMDB detail action, centralized attribution and stable detail background position.
Its fixed review records 1455 passing Web unit tests, 20 passing real-Python Explore browser tests,
and 24 passing navigation/deep-link tests with one existing 403 locator failure reproduced at its
original Base. These are development acceptance results with local-only raw evidence; Slice52's
original closure, release version and packaging validation remain unchanged.

Accepted Slice51 Explore/Dashboard retirement, Slice50 presentation/loading/cards, Slice49 confined
Automation intent and Slice48 independent Task flow/file outcomes remain. Slice52's Web presentation
and existing read-API validation do not establish a new package, container, external-service or
production release. Packaging evidence applies only to its recorded source; the later standalone
corrections below state which package gates were run. An actual release still requires its own
exact-source container, external-service and release validation.

This is development acceptance, not a V2 release. Current support is fresh initialization
→ submit new work → same-version reopen/restart and permitted safe continuation. Old-task/Job
migration or takeover, cross-version upgrade/rollback, mixed-version writers and V1 support are
excluded. Readable immutable configuration containing retired fields does not add an upgrade promise.

The standalone [OpenList correction](https://github.com/kentinya/mediaflow/blob/d65e938dba698d46fc934992a7b2cd3746ceea7b/TASK.md) was accepted by B on 2026-11-08,
from Base `6db3647c7e77d54f3a49b6725c804f0794fc7fbb` through implementation
`cf680df6e24725ba40ada378e158d6a0e44710e5`. Its final candidate validation is:

| Gate | Result |
|---|---|
| Python 3.11 / 3.12 / 3.13 full regression | Each: 2651 passed, 7 skipped, 2658 total |
| Web unit / default browser E2E | 1459 passed / 264 passed |
| All 16 real-Python browser specs | 190 passed, 2 intermittent script failures; the two isolated cases passed |
| Quality, examples, dependencies and Web build | PASS |
| Wheel and external installed consumers | PASS |
| Docker native transfer lifecycle / release security | PASS / PASS |

The two script failures concern Copy's post-publication list/authority synchronization and a delayed
route callback during edit. Product checks showed the existing refusal/refresh feedback and correct
saved values; their full-run failures remain in the fixed review. The seven skips require dedicated
external-service or endurance environments. The OpenList 405 proof used local HTTP fixtures and
verified native Move／Rename, zero download-link/content requests and `refresh: false` throughout.
Raw evidence is stored locally at `.git/validation-evidence/cf680df6/b-final/`.

The [Files preparation-return correction](https://github.com/kentinya/mediaflow/blob/886c320db6916a1f0c3f5c2f2e38b599d14418a5/TASK.md)
passed independent B review on 2026-11-09, from Base
`45674526b04d3366f533b86e864b3c8d179736ed` through reviewed Head
`df565d058acaaf8078ddcb7b20ffa7c89079ac76`, with accepted implementation
`c1ff542f071dce6829ed497dfe9911df8ad0c3a2`. Files no longer displays organizing history;
the original Task detail reopens its exact preparation/summary after leaving or re-authentication.
T3 acceptance passed: 175 component tests, 26 Python Task Center tests, 77 default browser cases,
6 real-Python Files/history cases and the real-Python Task Center preparation-return case, plus
Web quality/build and affected Python checks. Independent real-stack browsing confirmed one execute
submission, zero history reads during ordinary browsing, source removal, target presence and the
original Task's result. Desktop/narrow loading, ready and continuation views were inspected.
The fixed report retains exact commands and local evidence location. These local temporary-Storage/
fake-Provider checks do not extend the earlier OpenList full regression, wheel or Docker results to
this later source. No production external-service or full release matrix was run for this correction.

The [query-type and candidate-continuation correction](https://github.com/kentinya/mediaflow/blob/da47f9dd1af56cc281d6e42323ae4892caed5f83/TASK.md#b-final-review--pass)
passed independent B T4 review on 2026-11-09: Base
`233f6a25769856087d10cb4483c0f1a621a76546`, reviewed Head
`fbabe7f80614dd35faa096dcb55198d183784501`, implementation
`86d9b7618acd88d640563ffc90f5e9d98c7e8b74`. Its acceptance includes:

- Python: 2671 tests, 7 skipped for dedicated external-service/endurance environments; Web unit: 1469 passed.
- Default browser: 266 passed initially; two artifact-file failures from concurrent suites sharing the
  output directory passed when rerun with isolated output. All 268 cases have passing results on the
  candidate; the initial failures remain recorded. Five targeted real-Python browser cases passed.
- Local real-stack TV journeys verified new-request recognition, saved intent candidates, same-Task
  confirmation to summary, correct TV detail and no Provider call during summary generation.
- Quality, examples, Web build, wheel and installed consumers outside the source tree passed.
  Wheel SHA-256: `07024680022cafd24e38506ad42a76781f364c1fe1f61bdb6a21863469028814`.

The fixed report retains exact commands, fixture limits and local evidence at
`.git/validation-evidence/fbabe7f8/b-final-review/`. This is development acceptance on temporary
Storage/fake Providers; it adds no Docker, production-service, deployment or cross-version claim.
Schema and historical records remain unchanged. Subsequent documentation-only reconciliation does
not change the validated executable inputs.

The [failed-file ownership and summary-continuation correction](https://github.com/kentinya/mediaflow/blob/379c3746de2c4cd31ed8a1f558f42c3d2175c2dd/TASK.md#b-final-review--pass)
passed independent B T4 review on 2026-11-09: Base
`fe3bd99b1cf6046ac716052e5c8ee63851c80f15`, reviewed Head
`9d05396b02f5f1375819f630a4e7d5a5a7c2c77a`, implementation
`7abfca505d13239b1030fee94327c18437858d48`. Python ran 2678 tests (OK, seven existing
external/endurance skips); Web unit tests had 1476 passed and default browser E2E 268 passed.
Real Python/SQLite/Worker journeys verified failed-file new admission, mixed-batch independent
confirmation and actual moves, ended-summary read recovery, desktop/390px and same-version restart.
Wheel/installed consumers passed; the exact Docker image built and ran 71 relevant installed-package
tests successfully. No table, column, migration or state enum was added.

Two broad checks were not green: the three assigned real-Python specs had 48 passed/one row-selector
failure; the Docker release-security smoke stopped before execution on its metadata fixture's
`400 metadata_unverified`. Each failure was reproduced at the immutable Task Base with the same
cause. The current task-flow spec passed all three cases in isolation. Docker startup, static/RBAC
and Active-snapshot Worker-restart stages passed, but later release-smoke stages were not completed.
These limits remain in the fixed review with artifact digests and local evidence at
`.git/validation-evidence/9d05396b02f5f1375819f630a4e7d5a5a7c2c77a/b-review/`.
This acceptance supplies no all-green release, production-service or cross-version claim.
The subsequent documentation reconciliation changes no executable inputs.

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
