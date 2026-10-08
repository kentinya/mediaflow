# Task 44.2 — Classification destinations and explicit legacy conversion

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
[`SLICE.md`](SLICE.md). It completes RO-3 and Slice Acceptance Criteria 13–16 as one destination,
publication and historical-authority boundary.

```text
Task ID: 44.2
Parent Slice: 44
Status: FIX REQUIRED
Task Base: 78cddf8b4090e8da86c6e69ffd237c67959b70c7
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An operator creates or edits a classification destination using only a selected MediaLibrary and
one safe relative `path`, previews its actual target and publishes through the existing checked
Save. New work uses MediaLibrary root + classification path + naming contribution consistently
across Web/API/CLI/manual/scheduled consumers. Legacy destinations convert only through explicit,
explained successor publication; old snapshots, admitted pins, effects and execution authority keep
their original meaning.

## Why This Task Exists

Actual code at Task Base still has RO-3's original gaps:

- `ClassificationRule` requires `library` and `category`.
- `strategy_user_configuration._classification_rule` requires the legacy field and can infer a
  MediaLibrary ID from its name; it also has overlapping path/category normalization.
- `compose_destination` prefixes classification `library`, and formal Planner passes that prefix.
- `RulesObjectForm` fills `library` from the MediaLibrary display name and exposes category and
  subcategory destination fields alongside path.

Removing a form field alone would leave different runtime targets or change historical snapshot
meaning. The largest independently acceptable next unit is the complete classification destination
contract, its ordinary editing/conversion journey, common consumers and compatible authority.
RO-2 workspace presentation and RO-4 object-test separation can subsequently reuse this boundary.

### Preceding Task review

Task 44.1 B review: **PASS** for
`f57715c042ffa22c07d92950cc3de222946ed9b2..a3a0eaebf99874f5f91d5bc96547b6c0d8486c62`.
RO-1 is complete; Slice Required Outcomes all satisfied: **NO**; next: **NEXT TASK**.
The current committed HEAD includes the legitimate completion-report commit after that source
checkpoint; this Task Base records that actual HEAD, not a repin of Task 44.1 or Slice Base.

B independently verified Python full regression (2,195 total, 7 skipped, OK), Web full unit
regression (66 files / 1,011 passed), both-kind real-Python Files browser journeys (10 passed),
real-Python Operations browser acceptance (complete repeat: 21 passed), required quality/config
checks, actual Base-era state compatibility, wheel smoke, complete Docker release-security and
transfer-lifecycle acceptance. Actual range/diff, production OpenList local-server coverage,
metadata refusals and same-ID unknown-response recovery were inspected. The HTTP Delete blocker is
resolved on both kinds without weakening scope or non-replay. Full evidence/review snapshot:
`/tmp/mediaflow-task44-1-b-pass-review.md`; test logs use `/tmp/mediaflow-b44-r2-*`.

Known non-blocking validation facts carried forward, without claiming a green default E2E suite:

- Full default E2E: 203 passed / 32 failed. Twenty-eight Storage failures match actual committed
  Task 44.1 Base failure contexts and unchanged Storage tests/source; three old placeholder/route
  failures were independently rerun at that Base and failed identically. One Copy case waits for
  Movies after a prior Delete removed it from shared Node fake state; no Copy POST is sent. The
  unchanged Copy case passes with fresh fixture state. This is a P2 test-isolation issue with no
  supported-production user defect, not a P1 or a separate implementation Task.
- The unchanged Docker transfer-impact preparation fails with KeyError resourceLibraries at
  actual Base and candidate; the unchanged generic Docker upgrade harness expects schema 39
  although actual Base/candidate schema is 44. Actual schema-44 state, wheel migration/recovery
  and the complete security/lifecycle gates passed. Do not label either failing harness PASS.
- Initial Rules concurrency, Web unit, Operations timing and Docker health failures remain in
  the recorded reports/logs. B's subsequent complete runs passed without removing tests, hiding
  skips or relaxing checks. Production SMB/S3/TMDB endpoints were not certified by local/fake
  tests; built JS retains its existing >500 KB advisory.

Recheck all six Required Outcomes after this Task PASS. RO-2, RO-4, RO-5 and RO-6 remain separate
outstanding coherent outcomes; this Task neither implements them nor closes the Slice.

## Implementation Scope

```text
Classification domain/normalization → immutable snapshot and compatible persistence semantics
→ common destination composer/Planner → configuration and processing application services
→ authenticated Rules/configuration/preview APIs + CLI/scheduled consumers
→ native classification forms/conversion/recovery → Tests and historical-state rehearsal
```

1. Define the revised result with explicit `mediaLibraryId` and `path`. Use one backend safe-relative
   normalization for supported string/segment-list paths; the library ID/name never contributes a
   path segment. Derive category display from path where needed. Preserve condition semantics,
   identity, priority, enabled state, confidence, no-match/manual handling and C identity.
2. Carry the revised semantics through managed/bootstrap/import/export normalization, classification
   decisions and manual configured-rule recovery, common composition, formal Planner, exact-
   candidate classification/destination/complete-flow previews, API/CLI and existing scheduled
   processing. Web renders backend results and does not calculate an alternate authoritative path.
3. In existing Rules Add/copy/Edit classification forms, expose the destination selector and one
   safe path; remove `library` and redundant editable category/subcategory output for revised
   authoring. Preserve the remaining supported fields, typed conditions and normal checked Save.
   Show selected root, classification and naming contributions, actual target and relevant errors.
4. Deliver explicit legacy conversion through the same native editing/publication journey. Read
   legacy configuration and diagnostics without silently converting it. Show the old and proposed
   destination contributions before the operator deliberately saves the revised successor. Remove
   the prefix, preserve the existing explicit path, and never automatically prepend the old prefix.
   Missing/ambiguous library references or explicit paths require visible correction, not name/slug
   guessing. An unrelated object's cosmetic Save cannot switch a legacy destination contract.
5. Choose the smallest compatible format/runtime strategy that distinguishes a legacy pinned
   contract from a revised publication. Preserve old revision bytes/digests, previews/plans/results,
   Task/Job pins, completed/partial/uncertain effects and previously organized files. Add compatible
   persistence evolution only if required; do not create a second policy store or execution engine.
   Already authorized legacy work continues only under provable original semantics/authority;
   otherwise refuse new mutation and provide native diagnosis and current-preview recovery.
6. Preserve evidence purpose and authority. Old-target previews/checks/grants cannot authorize a
   revised target. Affected new work obtains exact current preview/authorization through existing
   journeys. Preserve unrelated valid authority and provably unchanged pinned continuation; avoid
   blanket invalidation or replaying completed/uncertain effects. Checked activation remains atomic
   and fails closed; failed/unknown publication preserves input and supports actual readback.
7. Keep classification/Planner/analysis pure and OrganizerExecutor the sole mutator. Preserve live
   permissions, Storage/root confinement, capabilities, conflicts, source identity, locks/fences and
   destructive intent. Maintain RO-1's direct maintenance and both-kind recovery as regressions.
   Document only necessary implemented compatibility/architecture facts in `docs/architecture.md`;
   authoritative product/roadmap reconciliation remains A's closure responsibility.

### Operator journey

- **Goal/entry:** open Classification Policies in `/ui-v2/rules`, explicitly Add/copy or use the
  existing Edit route, and choose a destination for the current rule.
- **Visible state:** the selected configured MediaLibrary/root, one classification path, naming
  contribution and exact candidate target; legacy conversion additionally shows old/new routing.
- **Action:** edit destination/conditions, explicitly preview, correct relevant findings, and publish
  with the existing one checked Save. Meaningful legacy target change is explicit; ordinary editing
  requires no CLI, raw revisions/tokens or extra generic Validate/Activate ceremony.
- **Success:** the published Active inventory and newly admitted work agree on the canonical target;
  a display-name change does not alter a revised destination.
- **Failure:** invalid path/reference, missing/disabled library, stale candidate/authority, denied
  Save, unavailable context, target conflict or failed check names the affected rule/stage.
- **Recovery:** preserve correctable form/old Active, resolve the named field/reference, repreview
  and Save; read back an unknown publication. Historical work retains its original durable state
  and offers safe existing continuation or explicit current-preview recovery without replay.

### Frozen scope

Do not modify Slice User Goal, Required Outcomes/Surfaces, Safety Invariants or Slice Base;
`docs/roadmap.md`, `docs/progress.md`, the canonical Chinese specification, stable product/requirements
contracts, reference images and frozen Slice 43 history remain outside implementation scope. Preserve
all pre-existing untracked images and other user work. Never include `config/alist.json`, real
configuration/credentials or production data.

## Acceptance Criteria

- [ ] **AC-1 — Revised authoring.** New classification results require explicit MediaLibrary ID and
  safe path only, through one backend string/segment-list normalization. Both existing Add/copy
  drawers and Edit support this form, without library/category/subcategory destination inputs or
  name-derived routing. Preserve all actual condition/identity/priority/enable behavior.
- [ ] **AC-2 — Target parity.** For root `/Media`, path `电影/华语` and naming
  `影片目录/影片.mkv`, every revised consumer produces `/Media/电影/华语/影片目录/影片.mkv`.
  Keeping a Movies prefix requires Movies explicitly in path. Library display-name/ID changes do
  not implicitly add a segment. Web/API/CLI previews, formal Planner, manual decisions and existing
  scheduled processing agree; C remains C when reusing A policies.
- [ ] **AC-3 — Native success/error/recovery.** Form and exact-candidate evidence explain selected
  root/path/naming/target, matched rule and relevant failure. Missing/disabled/unresolved libraries,
  unsafe paths and no-match remain truthful outcomes. Checked Save succeeds atomically or preserves
  input/old Active; stale/unknown Save uses existing repreview/readback without automatic replay.
- [ ] **AC-4 — Explicit legacy publication.** Legacy read/bootstrap/import/export and diagnostics
  remain supported. Conversion shows old/new contributions, removes library while preserving the
  explicit path, and publishes only through deliberate checked successor Save. Missing ID/path
  requires visible correction; no name guess, startup conversion, read-side publication or implicit
  conversion through another object's Save. Full-document and page-local consumers agree.
- [ ] **AC-5 — Historical contract integrity.** Actual Task-Base-created immutable documents,
  digests, plans/previews/results and admitted Task/Job pins remain readable and unchanged across
  candidate restart/upgrade. The runtime distinguishes legacy from revised target meaning. Legacy
  continuation either proves and uses its original contract/authority or refuses new mutation with
  native recovery. It never substitutes current Active or replays completed/uncertain effects.
- [ ] **AC-6 — Exact authorization.** Old-target evidence/grants cannot authorize revised targets.
  Affected current work has exact new preview/authority through existing manual/scheduled journeys;
  unrelated authority and provably unchanged pinned work remain valid. Stale/revoked permission,
  changed source, conflict and unsupported Storage capability remain enforced at execution.
- [ ] **AC-7 — Safety/regression.** Classification/composition/Planner/analysis cause zero Storage
  mutation. Only OrganizerExecutor executes authorized work; no silent overwrite/delete, new
  fallback or relocation of prior files. Preserve pipeline separation, C identity, snapshot pinning,
  fences, independently recoverable effects and RO-1's ordinary file operations on both kinds.
- [ ] **AC-8 — Complete evidence/checkpoint.** Assigned T4 focused/integration/full/quality/safety/
  packaging gates have truthful commands, totals, skips and actual candidate identities. Native
  authenticated real-Python browser/API proof covers revised authoring, checked legacy conversion,
  publication failure/readback and affected recovery. Real Base-era compatibility is rehearsed, not
  replaced by fixtures authored in the new format. Any pre-existing/unrelated failure has actual
  Base evidence; the scoped checkpoint contains no private/unrelated or frozen work.

## Required Tests

Use `.venv/bin/python` from repository root. Keep unchanged safety assertions and report every skip,
failure and unavailable gate. Replace old target expectations only where the selected revised
contract applies; retain explicit legacy-target and pin-integrity assertions. Do not use production
media, credentials or remote endpoints for these gates.

### Focused domain/configuration/publication integration

```bash
.venv/bin/python -m unittest tests.test_classification tests.test_strategy_configuration tests.test_runtime_strategy_configuration tests.test_configuration_classification tests.test_configuration_destination tests.test_configuration_destination_activation tests.test_configuration_package_exchange tests.test_v2_rules_workspace_previews tests.test_v2_rules_workspace_commands
.venv/bin/python -m unittest tests.test_organizer tests.test_classification_review tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_resource_library_pipeline tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_configuration_snapshot tests.test_migration_rehearsal tests.test_release_security
```

Add focused tests in the relevant existing modules or a coherent compatibility test module and
record its exact command. Cover safe/nested/string/segment-list and invalid paths, name changes,
missing/disabled/ambiguous references, conditions/no-match/manual decisions, pure calculations and
zero-mutation spies, formal/scheduled parity, C→A-policy identity, stale/failed/unknown publication,
old/new targets and grants, pin reconstruction/denial, restart and independent partial/uncertain
state. Tests must use the actual production engines, not an alternate preview path calculator.

### Full regression and quality/safety

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
git diff --check
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

Forbidden-dependency audit requires no matches (rg exit 1). Inspect complete Task Base..Head and
staged manifest for scope, frozen files and private data. Legacy examples must remain meaningful
compatibility inputs; do not erase coverage to make revised normalization pass.

### Web and real-Python acceptance

From `web/`:

```bash
npm run test -- --run
npm run format:check
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Run/add focused native Classification Add/copy/Edit/preview/publication/conversion checks and record
exact invocations. Supply real-Python API/SQLite/runtime/browser journeys using temporary roots,
actual checked configuration application behavior and built candidate assets. Reuse a suitable
existing harness or add a narrow isolated Rules harness; exclude its real-Python spec from default
fake-server runs. Cover legacy old/new visibility, preserved path, revised new work, stale/denied/
unknown Save, historical recovery and no replay. Existing fake previews or direct-file browser
proof alone cannot certify the destination contract. Keep evidence purpose/local-versus-complete
analysis unchanged; RO-4 separation remains outside this Task.

Run browser configs sequentially or use independent output directories so unrelated trace cleanup
cannot invalidate results. Assess carried-forward failures against actual Task Base and current
production reachability/impact; disclose them without inventing P1s or claiming failed suites green.

### Compatibility, packaging and Docker

```bash
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-task44-2-wheel
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-task44-2-wheel/mediaflow-*.whl
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task44-2-security
.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task44-2-lifecycle
```

Rehearse actual Task Base→candidate legacy configuration and admitted-work compatibility. Seed
legacy documents, immutable revisions/digests, target previews/plans/evidence/grants and pending/
completed/partial/uncertain work using actual Base code. Verify candidate restart/readback,
provable old-target continuation or zero-mutation refusal, explicit successor conversion, revised
new work and protection against old grants authorizing new targets. Report exact commands and
state/artifact identity. An invented new-format fixture or generic schema-only rehearsal is
insufficient. If persistence/format changes, run applicable upgrade/migration gates including
`.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py`; document its actual Base-existing
schema expectation failure if still unchanged, alongside the real compatibility rehearsal.

Use fresh Task-owned artifacts/isolated Compose projects, synthetic media and generated test
credentials. Preserve the live deployment. Record unavailable Docker/services honestly, never PASS.

## Non-goals

- RO-2 shared header/navigation/reference styling or wholesale Rules form redesign; RO-4 object-
  scoped tests/complete-flow separation; RO-5 toolbar repair; RO-6 folder discovery/organization.
- Frozen Slice 43 integration, dependency on its rejected implementation or alteration of its
  Task/history; Slice/Task scope changes, A's reconciliation and Slice PASS/CLOSED.
- Automatic legacy conversion/relocation, broad policy stores/migrations, blanket authority
  revocation, replay/rollback of completed or uncertain media, or weakening source/ownership gates.
- New providers/Storage operations, Upload/Download, transfer Replace, MediaLibrary Organize,
  recognition algorithms, global search, unrelated cleanup or separate P2/test-only Tasks.

## Developer Completion Report

### Changed Files

Correction round (this checkpoint) — the original implementation checkpoint `4c70dbe` is unchanged
and is not amended:

- `mediaflow/application/rules_workspace_commands.py` — one shared `_prepare_candidate` preparation
  now runs before the strict normalizer on **both** Save (`_publish`) and `stage_preview_candidate`
  (preview). It drops the read-only `destinationContract` projection key for every rule, including
  new/copied rules with no stored predecessor, and applies the unchanged legacy-prefix intent
  semantics (absent key = carry the historical prefix forward; explicit `null` = deliberate
  conversion). `_classification_rule_projection` now always carries the explicit `path` a rule
  really means, recovering it from a legacy `category`/`subcategory`-only document. The previous
  helper `_preserve_unsubmitted_legacy_destinations` is renamed to `_prepare_candidate`; it was
  never referenced by tests or scripts.
- `tests/test_classification_destination_contract.py` — new `ProjectionRoundTripTests` (3 tests)
  covering B's required regressions.
- `scripts/classification_destination_browser_proof.py` — the committed real-Python harness now
  drives the native reopened Edit journey and the native legacy conversion journey through real
  Chromium, and re-authenticates after a deep link because the token is deliberately memory-only.

Original implementation checkpoint `4c70dbe` (reviewed range
`78cddf8b4090e8da86c6e69ffd237c67959b70c7..4c70dbe46acc81bbd1f5d20d21e94aa012a89ef3`, unchanged):
domain/classification, domain/organizer, application/{classification,configuration_objects,
rules_workspace_commands,evidence_capture,organizer,strategy_test}, cli, infrastructure
strategy configuration, the Rules Web form/entity/fixtures/styles, the focused test modules and
`docs/architecture.md`.

### Implemented

**B P1 root cause and correction.** The backend's own edit/copy projection adds a read-only
`rules[*].result.destinationContract` key so the form can display which contract a rule has, and the
normal frontend candidate builder submits the projection it rendered. Only Save had a preparation
step that removed that key, and only for rules with a stored legacy predecessor; preview had none,
and the removal happened on a temporary dict that was discarded for revised/new rules. The result was
HTTP 400 `rules_invalid_field` for a revised reopen→Save, for every exact-candidate preview, and for
legacy previews — exactly B's reproduction.

The correction makes candidate preparation identical on both publication paths. `_prepare_candidate`
runs before `_normalize_or_reject` in `_publish` (Save) and in `stage_preview_candidate` (Preview),
so:
- the read-only `destinationContract` explanation is dropped for **every** rule, so a projection the
  backend itself produced round-trips through Save and Preview for new, copied, legacy and revised
  rules, and the key is never persisted and never added to the runtime allowlist;
- absent-prefix intent versus explicit `null` conversion is unchanged: an unsubmitted legacy prefix
  is carried forward (an unrelated cosmetic Save still cannot switch the contract), and an explicit
  `null` publishes the revised successor with the explicit path preserved rather than prefixed.

While reproducing, I found and fixed one directly adjacent break of the same class introduced by the
original checkpoint: a Base-era document that stored only `category`/`subcategory` was projected
without any `path`, so reopening and saving it failed with
`rules[0].result.path is required` and would have lost the destination. The projection now derives
the explicit `path` the normalizer has always resolved from that form, so the historical destination
is preserved. This is the same read-only-projection round-trip root cause B named, not a new scope.

Classification/composition/Planner/preview purity is unchanged, no Storage mutation was added, no
fallback/overwrite/delete/replay behavior was added or weakened, and no persistence or schema change
was made (schema 44 / configuration schema 10 unchanged).

### Tests and Results

B's reported reproduction, rerun against this checkpoint (production services, real SQLite, real
Local adapters, real production engines):

- `.venv/bin/python scripts/classification_destination_browser_proof.py` — **PASS**. The committed
  real-Python harness now additionally drives: native reopen of a revised policy → `预览分类` →
  description Save → readback (no legacy prefix, `destinationContract` is
  `media_library_path`, explicit path preserved) with the real configuration export proving the
  read-only key was **not** persisted; native legacy reopen → legacy notice showing the old prefix →
  `预览分类` without conversion (stored prefix unchanged) → explicit
  `移除规则 N 的旧版目标前缀` → Save → readback with the prefix removed and the explicit path
  preserved → reopen → preview → Save again. Output:
  `PASS: classification destination contract through the real Python boundary`.
- Falsification: with only the reviewed candidate's `rules_workspace_commands.py` restored in a
  separate worktree (same new tests and same new harness), the harness fails with
  `ExpectError: ... getByRole('heading', { name: '分类结果' })` because the native preview returns
  HTTP 400, and the three new focused tests error with
  `ClassificationPolicy rules[0].result contains unsupported field 'destinationContract'`. The
  correction is therefore causally responsible for the pass.
- A separate scratch probe of the production command service drives B's exact five-step sequence
  (legacy unchanged preview, conversion preview, explicit conversion Save, revised second Save,
  revised preview). At the reviewed candidate it reproduces B's recorded outcome exactly — four
  rejections with `contains unsupported field 'destinationContract'` and the intervening conversion
  Save succeeding — and at this checkpoint all five succeed.

Focused domain/configuration/publication integration (T4):
- `.venv/bin/python -m unittest tests.test_classification tests.test_strategy_configuration tests.test_runtime_strategy_configuration tests.test_configuration_classification tests.test_configuration_destination tests.test_configuration_destination_activation tests.test_configuration_package_exchange tests.test_v2_rules_workspace_previews tests.test_v2_rules_workspace_commands` — **PASS** (157 tests, OK)
- `.venv/bin/python -m unittest tests.test_organizer tests.test_classification_review tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_resource_library_pipeline tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_configuration_snapshot tests.test_migration_rehearsal tests.test_release_security` — **PASS** (174 tests, OK)
- `.venv/bin/python -m unittest tests.test_classification_destination_contract` — **PASS** (27 tests, OK; 24 previous + 3 new `ProjectionRoundTripTests`)

Full regression and quality/safety:
- `.venv/bin/python -m unittest discover -s tests` — **PASS** (2222 tests, OK, 7 skipped)
- `.venv/bin/python scripts/check_governance.py` — **PASS**
- `.venv/bin/ruff format --check .` — **PASS** (343 files already formatted)
- `.venv/bin/ruff check .` — **PASS** (All checks passed)
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — **PASS**
- `.venv/bin/python -m pip check` — **PASS** (No broken requirements found)
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` — **PASS**
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — **PASS**
- `git diff --check` — **PASS**
- `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` — **PASS / no matches** (`rg` is not installed in
  this environment; `grep -rn -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml` returned exit 1, no matches)

Web:
- `npm run test -- --run` — **PASS** (67 files / 1014 tests passed)
- `npm run format:check` — **PASS**; `npm run lint` — **PASS**; `npm run typecheck` — **PASS**
- `npm run build` — **PASS** (existing >500 KB chunk advisory unchanged)
- `npm run test:e2e` — 203 passed / 32 failed; identical totals to the recorded Task 44.1 baseline
  (see Risks). Two consecutive full runs both reported 203 passed / 32 failed.
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` — **PASS** (21 passed)
- `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` — **PASS** (10 passed)

Compatibility, packaging and Docker:
- `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-task44-2-wheel` — **PASS**
- `.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-task44-2-wheel/mediaflow-*.whl` — **PASS** (schema 44)
- `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task44-2-security` — **FAIL / UNAVAILABLE (environment)**
- `.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task44-2-lifecycle` — **FAIL / UNAVAILABLE (environment)**
- `.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py` — **NOT RUN** (no persistence/format change)

This round the Docker daemon *was* reachable, so I re-verified the earlier environmental claim
directly instead of repeating it. Both gates still fail while creating the isolated stack with
`invalid mount config for type "bind": bind source path does not exist` for a host `/tmp` path the
script had just created. The real cause is a mount-namespace mismatch, now proven:
`docker run --rm -v /tmp:/hosttmp alpine ls /hosttmp/<fresh temp dir>` reports
`No such file or directory`, `docker run --rm -v /tmp:/hosttmp alpine ls /hosttmp` shows an
unrelated `/tmp`, and the same bind of a workspace path (`/root/mediaflow/...`) succeeds. Docker
Compose short syntax silently auto-creates the missing path as a directory, which is why a naive
probe appears to work. Neither Compose file, the Dockerfile nor either smoke script is modified by
this Task. Both gates are recorded as FAIL/UNAVAILABLE, not PASS.

### Decisions

1. **One shared preparation, applied by both commands.** Rather than duplicating the cleanup in
   Preview, `_prepare_candidate` is called from both `_publish` and `stage_preview_candidate` before
   `_normalize_or_reject`. This is the smallest change that makes the two paths agree by
   construction, and it keeps the strict runtime allowlist authoritative.
2. **Do not add `destinationContract` to the runtime allowlist.** The key is a projection
   explanation, not stored state; accepting it at runtime would persist a derived display value and
   make the form's read-only key a real field, which B explicitly forbade. The export-based check
   proves it is not persisted.
3. **Project the explicit `path` for category-only legacy documents.** The normalizer already
   resolved that form to a relative path, so exposing it in the projection changes no runtime
   meaning; omitting it made a legal historical document unsaveable. This is the same root cause,
   not a new behavior.
4. **No persistence or schema change.** Schema 44, configuration schema 10 and the managed document
   schema remain unchanged, so historical revision bytes/digests, pins and effects keep their exact
   meaning and no migration gate is required.

### Remaining In-Slice Work

RO-2 (reference-aligned Rules workspace presentation and purpose-built forms), RO-4 (object-scoped
Rules tests with a separate complete-flow check), RO-5 (long-name breadcrumbs/toolbars) and RO-6
(ResourceLibrary folder/mixed-selection organization) remain outstanding. This Task did not
implement those outcomes and does not close the Slice.

### Risks / Deviations

- **Docker gates unavailable in this environment** (both required gates), with the mount-namespace
  cause directly reproduced this round (see above). Neither is labelled PASS. The security and
  transfer-lifecycle guarantees they cover were not certified by this Task.
- **Default E2E is not green and was not made green**: 203 passed / 32 failed in two consecutive
  full runs, matching the recorded Task 44.1 counts and failure contexts. I did not remove tests,
  hide skips or relax assertions.
- **Pre-existing failure, unrelated to this Task.** `set_enabled(..., enabled=False)` on a
  classification policy fails with `the required read-only destination check did not pass`. I
  reproduced the **identical** failure at Task Base `78cddf8` with the reviewed candidate's
  `rules_workspace_commands.py` restored, so it is not introduced here; the same call with
  `enabled=True` passes. Not fixed, because it is outside B's named blocker list and the evidence
  attributes it to the Base-era destination check rather than to this correction. I do not claim it
  is harmless; B should judge whether it belongs to this Task or a separate item.
- **Pre-existing flaky test (not caused by this Task).** The Task 44.1 report records
  `tests.test_v2_rules_workspace_commands.RulesWorkspaceCommandTests.test_simultaneous_saves_never_publish_a_mixed_or_lost_successor`
  failing intermittently with an allowed-loser-code set that omits the bounded
  `rules_destination_check_failed` code. All full-regression runs in this round were green
  (2222 tests, 7 skipped); I did not widen that assertion.
- Production SMB/S3/TMDB endpoints were not certified by local/fake tests; built JS retains its
  existing >500 KB advisory.
- `docs/architecture.md` is unchanged this round. `SLICE.md`, `docs/roadmap.md`, `docs/progress.md`,
  the canonical Chinese specification, reference images and frozen Slice 43 history were not
  modified.
- `config/alist.json` was never created, read, staged or committed; no real credentials, production
  data or private paths are present in the checkpoint. The four pre-existing untracked
  `docs/pics/*.png` files were preserved untouched and are not staged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 79862d9ebba5f3547f2e9b4e709d0d09824cf357
```

## B Review Result

```text
Reviewed: 78cddf8b4090e8da86c6e69ffd237c67959b70c7..4c70dbe46acc81bbd1f5d20d21e94aa012a89ef3
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Classification form projections cannot round-trip through revised Save or existing
  exact-candidate Preview.**

  1. **Current production reachability:** the real Python API, temporary SQLite, real Local
     adapters and newly built V2 assets reproduce this with the normal authenticated Rules
     Add/Edit journey. No unsupported configuration, future adapter, mixed software version or
     weakened Storage/activation substitute is involved. The backend adds
     `rules[*].result.destinationContract` to both legacy and revised edit/copy projections
     (`rules_workspace_commands.py:1454–1491`); the normal frontend candidate builder preserves
     the nested `rules` data (`rules-form.ts:1046–1055`).
  2. **Current user impact:** create a revised classification policy, reopen its native Edit page,
     change its description and click Save: HTTP 400 `rules_invalid_field`, with the visible
     `保存未生效` state. Clicking `预览分类` also returns HTTP 400. A legacy policy's unchanged
     projection and the same projection after explicitly removing its prefix cannot be staged for
     preview either. Reloading and correcting valid business fields cannot remove this
     backend-generated read-only key, so normal maintenance and target verification are blocked.
  3. **Current Contract violation:** Task AC-1 requires revised Add/copy/Edit authoring; AC-3
     requires usable exact-candidate preview, checked Save and native correction; AC-4 requires
     explained legacy conversion through that journey. Slice RO-3 and Acceptance Criteria 13–15
     require these Web/API authoring and preview surfaces. This finding concerns the existing
     Task-owned preview path, not the deferred RO-4 analysis split.
  4. **Repeatable evidence:**
     `PYTHONPATH=/root/mediaflow .venv/bin/python /tmp/mediaflow-b44-2-candidate-repro.py`
     records rejection of legacy unchanged preview, conversion preview, revised second Save and
     revised preview, all with `contains unsupported field 'destinationContract'`; the intervening
     explicit conversion Save succeeds. Log: `/tmp/mediaflow-b44-2-candidate-repro.log`.
     `.venv/bin/python /tmp/mediaflow-b44-2-browser-repro.py` extends the committed real-Python
     harness with native create → reopen Edit → description change → Save and Preview actions;
     both return HTTP 400 through the actual API, and Save displays `保存未生效`.
     Log: `/tmp/mediaflow-b44-2-browser-repro.log`. The probe exits zero when it reproduces the
     expected defect; its inherited harness PASS line does **not** certify this extended journey.
     Actual Base..Head cause: `_preserve_unsubmitted_legacy_destinations` removes the projection
     key only from a temporary dict, then `continue` skips writing it back for revised/new rules
     (`rules_workspace_commands.py:1533–1553`); `stage_preview_candidate` never applies this
     candidate preparation before normalization (`:443–444`).
  5. **Severity:** P1. Legal current production assembly, a broken required operator journey,
     explicit current Contract clauses and repeatable production evidence all hold.

  **Required correction:** make read-only projection cleanup and the deliberate legacy-prefix
  intent semantics consistent across Save and Preview for new, copied, legacy and revised rules.
  Keep absent-prefix intent versus explicit `null` conversion, exact path preservation, strict
  runtime field validation, checked publication and historical authority intact. Add regressions
  for new policy → reopen → preview → Save and legacy → preview → explicit conversion → Save →
  reopen → preview → Save, through real backend behavior and native Web/API. Do not persist the
  display key or relax runtime allowlists to accept it. Complete the existing Task's required
  evidence and submit a correction checkpoint in Task 44.2; ID, Base, Goal and Scope remain fixed.
