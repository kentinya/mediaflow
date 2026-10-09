# Task 44.5 — Exact long-path browsing and usable toolbars on both library pages

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
current [`SLICE.md`](SLICE.md).

```text
Task ID: 44.5
Parent Slice: 44
Status: FIX REQUIRED
Task Base: c04870ca33f81d393c8a1be3b2e3840ef892b4f8
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Complete Slice 44 RO-5 as one native browsing journey on ResourceLibrary Files and MediaLibrary
Files: operators identify the exact current directory, reveal full long names by pointer or
keyboard, reach root/ancestors, refresh and switch list/grid while controls, entries, read recovery
and the footer remain usable at the real available pane width. This Task advances Slice AC23–26.

## Why This Task Exists

At the real committed Base, both `StorageFilesPage.tsx` and `MediaLibraryFilesPage.tsx` render
unbounded breadcrumb buttons directly beside the toolbar controls. `styles.css` makes the toolbar
wrap but later fixes its height at 52px; breadcrumbs themselves wrap. Long segments or a narrow pane
can therefore grow beyond the reserved toolbar space. Ordinary segments have no complete-name
hover/focus disclosure; existing edge-whitespace markers preserve identity but do not solve long
names. RO-5 requires a complete shared presentation boundary, including actual production Docker
serving. Splitting the two pages, ellipsis, tooltips or browser evidence into separate Tasks would
leave the selected journey incomplete. RO-6 folder discovery is a separate source/admission boundary.

### Preceding Task review and all-outcome recheck

Task44.4 correction `810264416c55dd72ec88fa3690055857f6aa0dd9` is accepted after its first
correction round. Actual HEAD `c04870ca33f81d393c8a1be3b2e3840ef892b4f8` adds only completion
report updates and is the legitimate Base of44.5. Task44.4 Base and Slice Base were never moved.

```text
Reviewed: 2222b6c3619631296e20db7bfaa489eb45e597e3..c04870ca33f81d393c8a1be3b2e3840ef892b4f8
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

B inspected actual diff and real production-shaped Python/SQLite/Local/current Chromium assets.
All three original blockers are resolved: visible collapsed Classification refusal/correction and
successful checked Save/readback in Add/copy/Edit, correct switch/required-label geometry, and the
selected header/description/navigation hierarchy. All8Acceptance Criteria pass. No weaker tests,
removed production capability, silent fallback or protected/private/user-file change was found.

Independent final results: Python337PASS; release-policy6PASS; Web focused7files/118PASS and
full69files/1058PASS; Rules E2E17PASS; default E2E239PASS with normal2workers and0failed/skipped/
flaky; real-Python Operations21PASS/DirectFiles10PASS; five native Rules/Storage/destination proofs
PASS. Governance/Ruff/compileall/Webformat/lint/type/build/diff checks PASS. Seven reference hashes
remain PRESERVED,13workspace screenshots inspected, read-only presentation creates no mutation,
activation or executable work. B actual118/1058correct Developer's117/1057count typo.

First incomplete/failing B runs are preserved, not labelled green: tool-interrupted full units;
the Configuration return-case failure also reproduced at unmodified committed Task Base; initial
parallel browser runs collided in their shared trace directory, and initial real Operations18/21
also exposed one refused stale Preview and dependent count checks. Complete serial reruns passed
without changing tests, retries, timeouts or workers. Developer extra fullPython/Docker evidence
was not independently rerun for this T3 presentation review; final Slice validation remains T4.
Accepted Task snapshot: `/tmp/mediaflow-task44-4-correction-pass-TASK.md`; B review:
`/tmp/mediaflow-task44-4-correction-b-review.md`; evidence/log/receipt index:
`/tmp/b44-4-correction-evidence-index.json`; visuals:
`/tmp/mediaflow-b44-4-correction-workspace/`.

| Required Outcome | Current result | Rechecked basis |
| --- | --- | --- |
| RO-1 | COMPLETE | Accepted44.1 shared direct commands; both-kind Web/real Worker recovery retained |
| RO-2 | COMPLETE | Reviewed44.4 native Rules workspace/forms/testing/Save presentation and recovery |
| RO-3 | COMPLETE | Accepted44.2 canonical/legacy destinations; C identity/current real readback retained |
| RO-4 | COMPLETE | Accepted44.3 exact local analysis/separate complete flow/freshness; production proofs pass |
| RO-5 | INCOMPLETE | Actual fixed52px/wrapping toolbar and missing bounded full-name access on both pages |
| RO-6 | INCOMPLETE | Folder Organize excluded; production directory admission returns `source_not_file` |

Slice44 remains ACTIVE. The expected remaining units are this complete RO-5 Task and one coherent
RO-6 discovery/admission/Preview/execution integration Task, for six major Tasks overall. No
additional field/test/wording Task or Contract/rescope/closure action is created.

## Implementation Scope

Existing exact Files route/model state → shared/scoped breadcrumb and toolbar presentation → both
native page integrations → real read/failure recovery → integration/browser/Docker evidence.
Reuse current domain/application/API/Storage authority; this presentation Task needs no schema or
new backend operation. A small shared presentation component is appropriate if it keeps both pages
consistent; avoid a new navigation framework or broad page refactor.

1. At normal desktop width preserve path-left/control-right composition and short-name density.
   Let the bounded path region shrink before controls; retain complete Create Folder/Text File,
   Refresh and view-toggle labels/targets. At narrow available pane widths reflow rows deliberately
   and reserve actual toolbar height. Entry, empty/loading/error/recovery content must start below
   the whole toolbar. Keep entries scrolling in their own existing bounded viewport and the
   toolbar/footer outside it; measure actual pane width after shell and directory tree.
2. Keep breadcrumb segments on one line within their own bounded region. Visually elide an
   overlong individual segment and provide local horizontal access for a combined long path.
   Bring the current segment into view on navigation, preserve visible current-directory context
   and make every ancestor/root reachable with pointer and keyboard. Overflow stays in the path
   region and does not push controls or create page-wide horizontal scrolling.
3. Reveal the full exact segment/name on hover AND keyboard focus through an accessible usable
   disclosure. Preserve meaningful full accessible names and visible/assistive leading/trailing
   whitespace disambiguation; include same-prefix distinct names. Visual labels never replace raw
   Storage identity: do not trim, normalize, rename or submit an abbreviation in route state,
   tree/selection, API read paths or existing command intent. Escape/render names as text.
4. Integrate the same behavior in both `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files`, valid
   deep links and list/grid. Preserve root/ancestor navigation, refresh/tree/selection reconciliation,
   paging, control disabled semantics, create dialogs, direct-file command dialogs/results and the
   existing ResourceLibrary Organize entry. A denied/unavailable/stale directory keeps its correct
   scoped context and actionable read recovery; never show a failed read as empty success. Viewing
   names, focusing, resizing or toggling view starts no media work or mutation.
5. Scope styles/components to the two Files workspaces. Preserve accepted RO-1/RO-3/RO-4, Rules
   header/forms/drawers, Storage, Settings, Operations and Automation. Preserve current path
   validation, library-kind isolation, auth/read permissions and no uncertain replay. No new
   Domain/Persistence, mutation, Active-publication or source-admission behavior is authorized.
6. Extend committed automated coverage and produce saved measured/screenshot evidence on both
   routes in list/grid at 1536×1024, 1024×900, 760×900 and 390×844. Cover short names, long Chinese,
   English/mixed/unbroken names, multilevel paths, common prefixes and boundary whitespace; actual
   path/control/entry/error/footer geometry and scrolling; full-name hover/focus; keyboard ancestors,
   current-segment visibility, root return, refresh success and read-error recovery. Check exact
   browser routes and API paths, and no unexpected write/analysis/Provider/work requests.
7. Use current-candidate production-built assets in a fresh isolated Docker acceptance instance
   through real Python HTTP/static serving and Chromium. Reuse existing Docker/Compose isolation
   helpers, temporary configuration/SQLite/Local roots, generated non-production credentials and
   controlled synthetic names/entries. Record candidate SHA, served JS/CSS identities, viewport,
   geometry, interactions and screenshots. Do not certify source/jsdom-only changes or an old
   image. Prefer a dedicated candidate tag and isolated project/ports/volumes; never alter or stop
   the user's existing live deployment. Verify temporary bind paths are visible to this Docker
   daemon (the existing harness may need a daemon-visible `TMPDIR`), and clean only task resources.

Frozen: Slice Contract/User Goal/Required Outcomes/Required Surfaces/Safety Invariants/Base,
Roadmap/closure documents, frozen Slice 43, user image originals and all pre-existing untracked
assets. `config/alist.json` remains ignored/untracked/unstaged. Never expose/stage production tokens,
credentials, private endpoints or unrelated files. Return a concrete authority/schema dependency to
B before crossing the authorized presentation boundary.

## Acceptance Criteria

- [ ] AC1 — Both routes retain complete visible/usable navigation, Create Folder/Text File,
      Refresh and list/grid controls for all Scope 6 name/path cases and four viewports. Wrapped
      rows remain inside their actual-height toolbar; entries and read recovery start below it.
      Short desktop paths retain the existing path-left/control-right density; no page overflow.
- [ ] AC2 — Breadcrumbs occupy a bounded single-line region with individual elision and local
      horizontal access when needed. Current segment is visible after navigation; every ancestor
      and root is reachable with pointer and keyboard. Hover and focus reveal full exact names,
      accessible identities remain meaningful, and edge whitespace/same-prefix siblings stay distinct.
- [ ] AC3 — Navigation/deep-link/root/refresh/API reads and existing command intent retain exact
      raw path identity. There is no trim/normalization/abbreviation fallback. Both kinds keep
      their own authority, tree/selection reconciliation, paging, disabled semantics and truthful
      unavailable/denied/stale read recovery; view/focus/resize starts no write or media work.
- [ ] AC4 — List/grid entries retain bounded scrolling with usable toolbar/footer; create/direct
      command dialogs and ResourceLibrary Organize remain reachable. Files styling does not regress
      Rules or unrelated native shell/page surfaces; accepted RO-1/RO-3/RO-4 safety behavior remains.
- [ ] AC5 — Saved automated browser evidence covers Scope 6 matrix and geometry/interactions;
      current production-built candidate is demonstrated through isolated Docker HTTP and Chromium
      on both routes. Record real results and artifacts; unavailable Docker proof is not PASS.
- [ ] AC6 — Required T3 focused/integration/affected regression/quality gates pass with real results.
      No removed tests, weaker assertions, hidden skip/retry/timeouts or fallback; the checkpoint
      contains only this complete RO-5 boundary and preserves frozen/private/user files.

## Required Tests

### Plan and risk basis

2026-10-09: B applies the user-authorized project workflow/template update to this existing plan.
Task ID/Base/Goal/Scope/Acceptance Criteria remain unchanged. This changes test scheduling and
verifiable evidence handoff; every previously assigned checkpoint command and RO-5 proof remains.

T3 is selected for shared Web presentation, route/model/accessibility integration and real Docker
static serving with unchanged backend/mutation/persistence behavior. Full Web units/default E2E
are final checkpoint gates because both library page bodies and shared Files CSS are broadly
reachable. Full Python/security/upgrade gates remain Slice-final requirements; the task-specific
isolated Docker presentation proof is mandatory under RO-5/AC26. No backend/schema change is
licensed by this plan. Increased authority risk returns to B for level reassessment.

### Development and correction feedback

Start with the tests for the changed component/model, adding the related Files/shared-style cases
below as affected. On a correction, reproduce the failing case and its direct regressions first.
Use the targeted browser command when navigation, geometry or interaction changes; it requires
current built assets. Resolve known blockers before launching the final broad suites.

From repository root:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_storage_browser tests.test_media_library_browser tests.test_release_security
```

From `web/`:

```bash
npm run test -- --run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/entities/library/storage-files.test.ts src/entities/library/media-library-files.test.ts src/entities/library/direct-files.test.ts src/shared/ui/AppShell.test.tsx src/shared/ui/rules-form-styles.test.ts src/shared/navigation/destination-model.test.ts
npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts tests/e2e/medialib-transfers.spec.ts tests/e2e/library-file-detail.spec.ts tests/e2e/rules-readiness.spec.ts
```

### Final checkpoint gates

Run the root governance/Python modules above on the final candidate, or identify a verified matching
run. The complete Web unit/default E2E commands below cover the listed focused cases under their
normal configurations; use their recorded selection/results to avoid rerunning those same cases
solely for submission. Earlier focused feedback on changed source is not final evidence. Keep the
separate real-Python and Docker proof gates; a mocked suite does not replace them.

From repository root:

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
git diff --check
```

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

Extend existing test seams and committed coverage without dropping their safety assertions. Add one
coherent real-Python/Chromium long-path acceptance harness and its isolated Docker invocation, for
example these exact root commands (record any justified equivalent replacement in the checkpoint):

```bash
.venv/bin/python scripts/files_toolbar_browser_proof.py
.venv/bin/python scripts/docker_files_toolbar_browser_proof.py
```

Those proofs must automate the two-route × list/grid × four-viewport acceptance and save
screenshots/bounds/interaction/raw-path/no-side-effect evidence outside `docs/pics`. The Docker
proof must identify current committed candidate and served built assets; scoped fake/local services
may control failures, without weakening real production capability or authority. Report actual
skips/unavailable; neither source screenshots nor a production deployment substitutes for isolation.

Retain the release-policy command index required by `tests.test_release_security`; these remain
Slice-final T4 gates rather than extra mandatory full Python/security gates for this unchanged
backend T3 presentation Task:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/docker_release_security_smoke_test.py
```

No full upgrade/migration rehearsal is newly required because no schema or persistence change is
authorized. Slice44 final validation still requires its complete T4 Contract gate.

### B independent verification

B inspects the actual Task Base..Head diff and independently reproduces the real-Python long-path
journey on both routes: exact whitespace/common-prefix paths, full-name hover/focus, keyboard
ancestor/root navigation and read-error recovery; inspect list/grid geometry at desktop/narrow
widths and no unintended write/work. Use the committed proof or a focused equivalent against the
actual production assembly, and inspect real screenshots/bounds rather than trusting generated
alignment labels. Verify isolated Docker served-artifact identity and its actual measured/browser
results; rerun an unverifiable or contradicted Docker claim in the isolated harness.

B verifies other gate logs/coverage and candidate/environment/artifact identity under workflow
reuse rules. B does not mechanically repeat all full suites; missing/incompatible evidence requires
the relevant gate to run again. A rejecting review may stop once an actual blocker is established,
recording unrun gates; PASS still requires all assigned final evidence and AC1–AC6.

### Evidence and rerun rules

Keep a secret-free index and original logs/screenshots/measurements in a stable ignored location,
for example `.git/validation-evidence/<source-sha>/task44-5/<run-id>/`, or in accessible CI artifacts.
Retain them through A Final Review; `/tmp` may be scratch space but cannot be the only handoff.
Record tested source SHA/dirty content, submitted SHA, commands/environment/lockfiles/fixtures,
normal workers/selection/retries, served JS/CSS/build identities, exits/counts/durations, first
failures and exact repeats. The report points to readable artifacts and explicitly records reuse
or missing evidence. A document-only successor requires verified unchanged runtime inputs and
fresh checks that consume those documents, including governance/release-policy checks.

Run browser suites sequentially or with genuinely isolated output directories; they otherwise
share `web/test-results`. Preserve normal worker counts and existing timeouts/retries. Never hide
a first failure or reuse a stale built artifact; prove a pre-existing/unrelated failure at actual
Base before excluding it. Use only controlled local/fake services, not production media/credentials.
Changes to source/tests/harnesses/dependencies/configuration/artifacts require fresh affected
validation; unchanged source is established by inspected evidence, not a report assertion.

## Non-goals

- RO-6 folder/mixed-selection discovery, folder Organize admission, background processing or new
  budgets; these form the next independent coherent Task after RO-5 passes.
- MediaLibrary Organize, a new whole-library/root Organize entry, changed direct-file mutation or
  optional-fingerprint authority, Upload/Download or new Storage/provider operations.
- General long-text/table/tree redesign outside the bounded Files breadcrumb/toolbar journey,
  global navigation, unrelated styling, metadata/manual-review changes or schema evolution.
- Changed Rules/classification/local-test behavior, frozen Slice 43 resumption, Contract/RESCOPE,
  A-owned CURRENT documentation reconciliation, live deployment or Git push.
- Optional cleanup, extra proof, wording or work outside current Slice 44 Contract.

## Developer Completion Report

### Changed Files

Implementation commit `8a0bb54` (product source and tests):

- `web/src/shared/ui/files-path.tsx` (new) — shared Files path presentation: exact-identity
  label/accessible name with boundary-whitespace disambiguation, bounded single-line breadcrumb
  region, current-segment reveal, and the portalled complete-name disclosure.
- `web/src/shared/ui/files-path.test.tsx` (new) — 9 focused behavior tests for that module.
- `web/src/shared/ui/files-toolbar-styles.test.ts` (new) — 5 structural CSS guards for the toolbar
  height, bounded path region, local elision and disclosure layering.
- `web/src/shared/ui/styles.css` — `.mf-files-toolbar` reserves actual height (`min-height`), the
  breadcrumb region is a bounded non-wrapping flex child with its own scrolling track, one segment
  elides at `min(22ch, 100%)`, and the portal disclosure style is added. Scoped to the Files
  workspaces.
- `web/src/features/library/StorageFilesPage.tsx`,
  `web/src/features/library/MediaLibraryFilesPage.tsx` — both pages now render the shared
  breadcrumbs and import the shared identity helpers instead of their duplicated local copies.
- `scripts/files_toolbar_browser_proof.py` (new) — real-Python/Chromium RO-5 proof.
- `scripts/docker_files_toolbar_browser_proof.py` (new) — isolated Docker production-asset proof.

Follow-up harness commits (no product source change): `35d0973`, `e9a25a9`, `c3e697a`, `6a6159d`.

`TASK.md` is the report document itself. The four pre-existing untracked `docs/pics/*.png` user
assets were preserved untouched and are not staged.

Correction round 1 (`df0bf7b`, B P1; `234dbe2` records B's review result):

- `web/src/shared/ui/files-path.tsx` — `placeDisclosure` is extracted and exported; the disclosure's
  vertical placement now uses its real rendered height (measure + `ResizeObserver`) instead of a
  fixed 48/34px reserve.
- `web/src/shared/ui/files-path.test.tsx` — 6 new focused placement tests (20 total in the file).
- `scripts/files_toolbar_browser_proof.py`,
  `scripts/docker_files_toolbar_browser_proof.py` — both seed the legal 240-byte `-Tail007` basename
  and assert the disclosure's vertical bounds and that it does not clip its own complete name on
  both routes in list and grid at 390×844; a screenshot is now taken while the name is disclosed.

### Implemented

RO-5 delivered as one shared presentation boundary used by both `/ui-v2/resourcelib/files` and
`/ui-v2/medialib/files`.

1. The toolbar no longer fixes its height at 52px. `min-height` keeps the accepted short-path
   desktop density while the wrapper reserves the height of its real rows, so a deliberately
   reflowed control row can never extend below the toolbar into the entry viewport. Entries and the
   read state start below the whole toolbar and the row viewport keeps its own bounded scroll.
2. The path region is a bounded, non-wrapping flex child that shrinks before the control group. One
   overlong segment elides locally at `min(22ch, 100%)`; the combined path scrolls inside its own
   track; the current segment is revealed with a local scroll on navigation. Path overflow never
   moves the controls and never introduces page-wide horizontal scrolling.
3. Complete exact names are disclosed on hover **and** keyboard focus through one portalled element
   above every clipping ancestor, so the bounded region can never clip the name it discloses. Each
   link also keeps an explicit accessible name that preserves boundary-whitespace disambiguation.
   The disclosure is placed against its anchor using its **real rendered height**: it prefers the
   space below the anchor, flips above when the whole disclosure does not fit there, and is finally
   clamped inside the viewport, so a legal long Storage name (up to 255 bytes) stays completely
   readable instead of losing its distinguishing suffix below the viewport bottom.
4. Every ancestor and the root remain reachable with pointer and keyboard. Navigation still hands
   back the exact raw relative Storage path — no trim, normalization or abbreviation — so
   same-visible-prefix siblings (`SSH` vs `SSH `) stay distinct and the API is asked for the exact
   value. The current segment is marked with `aria-current="location"`.
5. Read failures keep their scoped context and real recovery (重试 / 返回…根目录) and are never
   rendered as an empty successful directory.

No backend, schema, permission, mutation, Active-publication or source-admission behavior changed.
Recognitions/Planner/Executor boundaries, DryRun zero-mutation and the OrganizerExecutor-only
mutation rule are untouched. Viewing, focusing, resizing and view toggling start no media work.

### Tests and Results

Correction round 1 evidence index:
`.git/validation-evidence/df0bf7b1a7920b1d70e180a5d7528298c8ceba14/task44-5-correction/run-1/`
(`index.json`, `matrix.json`, `evidence.json`, 48 PNG screenshots per proof, `served-assets.json`,
`tested-sha.txt`, `repro-p1-before.log`, `repro-p1-after.log`; Docker set under `docker/`).
Tested/submitted candidate `df0bf7b1a7920b1d70e180a5d7528298c8ceba14`.

B's P1 reproduction (the failing case is fixed, first run retained):

- `.venv/bin/python
  .git/validation-evidence/5def630f.../b44-5-review/full-name-tail-probe.py` at the Task Base
  product source → exit 1, 8 failing viewport assertions, ResourceLibrary disclosure
  y=755/h=130/bottom=885 and MediaLibrary y=732/h=130/bottom=862 against viewport bottom 844
  (`repro-p1-before.log`).
- The same unchanged probe on this candidate → exit 0, 8/8 `fullNameVisible` true,
  ResourceLibrary bottom 721 and MediaLibrary bottom 698 (`repro-p1-after.log`).

Development and focused gates (all PASS unless noted):

- `web/`: `npm run test -- --run src/shared/ui/files-path.test.tsx
  src/shared/ui/files-toolbar-styles.test.ts src/features/library/StorageFilesPage.test.tsx
  src/features/library/MediaLibraryFilesPage.test.tsx` → 4 files / 75 PASS (includes the 6 new
  placement tests; `files-path.test.tsx` is now 15 tests).
- `web/`: the Task's full focused unit selection (`StorageFilesPage`, `MediaLibraryFilesPage`,
  `storage-files`, `media-library-files`, `direct-files`, `AppShell`, `rules-form-styles`,
  `destination-model`) → 8 files / 133 PASS.
- `web/`: `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts
  tests/e2e/medialib-commands.spec.ts tests/e2e/medialib-transfers.spec.ts
  tests/e2e/library-file-detail.spec.ts tests/e2e/rules-readiness.spec.ts` → 93 PASS.
- New committed coverage: `files-path.test.tsx` 15 PASS and `files-toolbar-styles.test.ts` 5 PASS
  (both included in the full run below).

Final checkpoint gates on this candidate:

- `.venv/bin/python scripts/check_governance.py` → PASS.
- `.venv/bin/python -m unittest tests.test_storage_browser tests.test_media_library_browser
  tests.test_release_security` → 23 PASS.
- `.venv/bin/ruff format --check .` → 350 files already formatted; `.venv/bin/ruff check .` → PASS;
  `.venv/bin/python -m compileall -q mediaflow tests scripts` → PASS; `git diff --check` → clean.
- `web/`: `npm run test -- --run` → 71 files / 1078 PASS (was 1072; the 6 new placement tests).
- `web/`: `npm run format:check` → PASS; `npm run lint` → PASS (0 errors, 0 warnings);
  `npm run typecheck` → PASS; `npm run build` → PASS (one pre-existing chunk-size advisory).
- `web/`: `npm run test:e2e` → 239 PASS / 0 failed / 0 skipped (normal config).
- `web/`: `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts` → 21 PASS.
- `web/`: `npm run test:e2e -- --config=playwright.direct-files.python.config.ts
  tests/e2e/direct-files.python.spec.ts` → 10 PASS.
- `.venv/bin/python scripts/files_toolbar_browser_proof.py` → PASS, 22 measured passes / 48
  screenshots (was 18/22), both routes × list/grid × 1536×1024, 1024×900, 760×900, 390×844 plus the
  short-name, boundary-whitespace and new legal-240-byte cases; `served index 58425c415e95`; zero
  mutating requests; Active revision/digest/activation count/executable work unchanged.
- `TMPDIR=/run/mf-docker-tmp .venv/bin/python scripts/docker_files_toolbar_browser_proof.py` →
  PASS, 22 measured passes / 48 screenshots against real production-served assets from a **fresh**
  candidate image `mediaflow:task44-5-files-toolbar-df0bf7b1a792` built by `git archive HEAD`;
  `builtFromCurrentCandidate: true`, `sameExecutableCandidate: true`, served `index.html`
  `58425c415e95…` equal to the local candidate.

Correction-round measured behavior (identical on both proofs). For the legal 240-byte segment at
390×844: ResourceLibrary disclosure y=591/h=130/bottom=721, MediaLibrary y=568/h=130/bottom=698,
both inside the 844 viewport with `scrollHeight == clientHeight` (128), and the saved screenshots
show the distinguishing `-Tail007` suffix. The previously recorded desktop/narrow geometry is
unchanged: desktop 1536 pane 1070 px, toolbar 52 px, path 611 px, controls 417 px; desktop 1024 pane
558, path 99, controls 417; narrow 760 pane 732, path 273, controls 417; mobile 390 pane 362,
toolbar 119 (two deliberate rows). Page scroll width never exceeds the viewport.

First failures and repeats (retained, not hidden):

- The first run of the new `placeDisclosure` test asserted the below-anchor placement for the
  130px-tall disclosure at anchor y=727. The real behavior correctly flips it above (727−6−130=591)
  so the complete name fits; the assertion was corrected to assert the actually delivered
  relationship (complete disclosure inside the viewport, flipped above). No assertion was weakened
  or removed.
- `npx vitest run` on `files-toolbar-styles.test.ts` alone failed with `No such built-in module:
  node:` because that file needs the project vitest configuration; the documented
  `npm run test -- --run <files>` invocation runs it green. This is an invocation detail, not a
  test defect.
- The first `npm run format:check` after the fix reported `files-path.tsx` unformatted and
  `npm run lint` reported one `react-hooks/exhaustive-deps` warning for the two-effect height
  measurement. The measurement was folded into the single placement effect with a `ResizeObserver`
  and reformatted; both gates now pass clean.
- Round-0 history (retained): the first full unit run after the round-0 CSS change failed
  `files-toolbar-styles.test.ts` on stale `max-width: 22ch` / `flex: 0 0 auto` expectations, and the
  round-0 proof-harness iterations failed for the seed/reveal/overflow/focus/read-error reasons
  recorded in the previous revision of this report. Those were fixed in the harness or the
  presentation, never by relaxing an assertion.

Reuse disclosure: the round-0 evidence under
`.git/validation-evidence/6a6159d396021a68e58be0c0f5c45f0421540236/task44-5/run-1/` remains the
historical record for the first checkpoint. It is **not** reused for this correction: the product
source changed, so every gate above was rerun on `df0bf7b`.

Unavailable gate: none. The earlier round-0 npm/Docker Hub network outage had cleared, so the
Docker proof built a fresh candidate image from the exact committed checkout and no image reuse was
needed (`builtFromCurrentCandidate: true`). The Slice-final T4 gates
(`unittest discover -s tests`, `docker_release_security_smoke_test.py`) remain Slice-level
requirements and were not run here, per the Task plan.

### Decisions

- One shared `web/src/shared/ui/files-path.tsx` module instead of duplicating the behavior in both
  pages: RO-5 explicitly requires consistent presentation on both workspaces, and the two pages had
  already drifted into byte-identical local copies of the identity helpers.
- The toolbar reserves height with `min-height` rather than a computed height or a second wrapper,
  so normal short-path desktop density is unchanged while wrapped rows are always inside the
  toolbar.
- Elision is local to one segment (`min(22ch, 100%)`) with the combined path scrolling in its own
  track, rather than truncating the whole path: this keeps every ancestor individually identifiable
  and reachable, as the Contract requires.
- The complete-name disclosure is a real portalled element rather than relying on the native
  `title` alone: `title` is not a usable keyboard disclosure and can be clipped by the bounded
  region. `title` is retained as an additional hint.
- The shared component still passes the exact raw `crumb.path` to the navigation callback; the
  visual layer never participates in route state, API paths or command intent.
- The Docker candidate tag is derived from the committed SHA and the harness asserts served-vs-local
  artifact identity, so evidence reuse is provable rather than assumed.
- Correction: placement is computed from the disclosure's **real rendered height** rather than a
  fixed reserve. The pure `placeDisclosure` helper is exported and unit-tested, while the component
  measures with `offsetHeight` plus a `ResizeObserver` (the viewport-aware max width can change the
  wrapped line count) and reuses the existing `anchor`/`value`-scoped effect. This keeps the
  behavior deterministic, avoids a render loop and needs no new dependency.

### Remaining In-Slice Work

RO-5 is this Task. RO-6 remains pending; B reevaluates every Required Outcome after Task PASS.

### Risks / Deviations

- Correction round 1: no gate is unavailable. The earlier round-0 npm/Docker Hub outage had cleared,
  so the Docker proof built a fresh candidate image from the exact committed checkout
  (`builtFromCurrentCandidate: true`) and no image reuse was needed.
- The Docker proof requires a daemon-visible temporary root in this environment
  (`TMPDIR=/run/mf-docker-tmp`); without it the harness fails loudly with
  `bind source path does not exist` and never silently mounts an empty directory.
- `web/dist` is git-ignored, so the served-artifact identity is recorded as hashes in the evidence
  rather than committed. The Docker proof requires `npm run build` first and fails fast otherwise.
- The pre-existing build chunk-size advisory (large single JS chunk) is unrelated to this Task and
  was not changed.
- The disclosure now clamps itself inside the viewport. For a pathologically tall disclosure (taller
  than the viewport) the top is clamped and the name remains available by keyboard focus and its
  accessible name; the legal 255-byte Local maximum is far below that and measured readable.
- No pre-existing/unrelated test failure was observed; no test was removed, weakened, skipped,
  retried or given a longer timeout.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: df0bf7b1a7920b1d70e180a5d7528298c8ceba14
```

Review range: Task Base `c04870ca33f81d393c8a1be3b2e3840ef892b4f8`..branch HEAD.

Correction checkpoint (the SHA above, validated by every gate in this report): `234dbe2` records
B's round-0 `FIX REQUIRED` result verbatim, then `df0bf7b` is the correction implementation
(product source, focused tests and both proof harnesses).

Round-0 executable checkpoint (previously reviewed):
`0184f63` (pre-existing user-authorized governance/template commit, already at Task Base + 1 and
explicitly referenced by this Task plan) → `8a0bb54` Task 44.5 implementation → `35d0973`,
`e9a25a9`, `c3e697a`, `6a6159d` proof-harness-only follow-ups, then the two docs-only successors
`f406e8a`/`5def630`.

The commit that carries this report is a docs-only successor of the SHA above.

## B Independent Review Evidence — 2026-10-09

Reviewed actual Task Base `c04870ca33f81d393c8a1be3b2e3840ef892b4f8` through
`5def630f7722fb6b3a68c8a481c8dfd484ed2728`. The reported executable checkpoint is
`6a6159d396021a68e58be0c0f5c45f0421540236`; its two successors change only `TASK.md`.
The preceding `0184f63` workflow/template change is the already-authorized governance update.
Production changes are confined to the shared Files presentation and its two page integrations;
no backend/configuration/schema or existing test was removed or weakened. The four untracked
user images are preserved; `config/alist.json` remains ignored, untracked and unstaged.

Independent evidence and reproducible probe:
`.git/validation-evidence/5def630f7722fb6b3a68c8a481c8dfd484ed2728/b44-5-review/`.
See `review-index.json` for commands, exits, candidate/assets and limitations. B rebuilt the
current committed Web assets and ran the committed real-Python proof (18 matrix cases / 22
screenshots, exit 0). B also inspected the supplied desktop/narrow Docker screenshots and
served-asset hashes; those hashes match the fresh local build. This rejecting review does not
certify all Docker provenance or checkpoint gates.

The additional legal-Local-name probe uses the same production Python API, authenticated
configuration, Storage capabilities and built assets; it only extends the temporary fixture to
a 240-byte ASCII directory name ending in `-Tail007`. Both routes × list/grid × hover/focus
produce eight clipped disclosures. `full-name-tail-probe.py` exits 1 on the viewport assertion;
its `full-name-tail/evidence.json`, screenshots and raw log retain the actual geometry. The
inherited harness phrase "8 measured passes" means eight collected measurements in this
diagnostic; all eight `fullNameVisible` assertions are false, not eight accepted cases.

Other independent results: governance PASS; Python browser/release modules 23 PASS; shared
component/CSS tests 2 files / 14 PASS; build and range `git diff --check` PASS. The broader
four-file focused Web run printed 69 PASS but its process returned 143, so it is not an accepted
gate. Full Web units/default E2E, real-Python Operations/DirectFiles, remaining quality gates and
a fresh isolated Docker proof were not rerun: review stopped after the evidenced P1. No
pre-existing/unrelated failure exclusion is claimed. This is B correction round 1 for Task 44.5;
retain the existing Task ID, Base, Goal, Scope, acceptance and test plan.

## B Review Result

```text
Reviewed: c04870ca33f81d393c8a1be3b2e3840ef892b4f8..5def630f7722fb6b3a68c8a481c8dfd484ed2728
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Full exact-name disclosure is clipped at narrow height (AC2; Scope 3/6;
  Slice RO-5 / AC24).** In `web/src/shared/ui/files-path.tsx:137–153`, vertical placement
  reserves fixed 48/34px rather than the disclosure's actual wrapped height. On both production
  Files routes, at 390×844, navigate to the temporary Local path consisting of the existing long
  Chinese segment, mixed English segment, and `"A" * 232 + "-Tail007"` (240 ASCII bytes,
  valid Local basename). Hover or keyboard-focus the current crumb in list or grid. The
  ResourceLibrary disclosure is y=755/h=130/bottom=885; MediaLibrary is
  y=732/h=130/bottom=862. Both exceed viewport bottom 844 and hide the distinguishing suffix;
  screenshots confirm the user cannot read the full name through the promised disclosure.
  Reproduce with `.venv/bin/python
  .git/validation-evidence/5def630f7722fb6b3a68c8a481c8dfd484ed2728/b44-5-review/full-name-tail-probe.py`
  (exit 1, eight failing viewport assertions). Position/clamp the disclosure using its real
  rendered dimensions so the complete name is available by hover and keyboard focus; preserve
  exact path identity and existing toolbar behavior. Extend both browser proofs to inspect the
  disclosure's vertical bounds and actual full-name visibility for this legal long-name case,
  retaining existing assertions and matrix coverage, then satisfy the unchanged checkpoint plan
  on the corrected candidate.
