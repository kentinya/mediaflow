# Slice 37 — Files Page and ResourceLibrary Workflow

This is the A-owned Slice Contract for the focused Files page and ResourceLibrary workflow. Slice
33 remains `PASS / CLOSED` in Git and Progress history. The previously planned Slice 34, Slice 35
and Slice 36 boundaries are retired from the current Roadmap on 2026-09-14; their historical
mentions remain historical facts and are not current commitments.

~~~
Slice ID: 37
Name: Files Page and ResourceLibrary Workflow
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Implementation Head: NOT SET
~~~

The Base is the committed `main` checkpoint immediately before this Contract replan. No production
implementation is included in this Contract checkpoint. B must plan an implementation Task only
after this Contract is checkpointed, and Developer work must remain inside this Contract.

## Scope decision

The current Roadmap has one active focus: the V2 Files page and its bounded ResourceLibrary workflow,
represented by [`docs/pics/文件页.png`](docs/pics/文件页.png). This Slice does not revive, rename or
absorb the retired future Slices. It does not redesign unrelated pages, replace the existing backend
authority, or introduce a new security model.

The detailed visual source of truth is
[`docs/file-page-visual-spec.md`](docs/file-page-visual-spec.md). The image is authoritative for
visual detail; this Contract controls product scope, authority and safety.

## User goal and vertical journey

**Goal:** an authorized operator can open the V2 Files page, understand the active ResourceLibrary,
browse its directories, see live files plus bounded business-status feedback, add a ResourceLibrary,
select a bounded file set and continue through safe organization without interpreting backend
implementation details.

**Entry:** select `文件` in the V2 shell or open `/ui-v2/library/files` (router path
`/library/files`) with the existing memory-only API-principal authentication boundary.

**Visible state:** at the reference `1536 x 1024` viewport the page shows the MediaFlow shell,
active Files navigation, search bar, ResourceLibrary summary, information banner, directory tree,
breadcrumb, file table, selected row, selection footer, pagination and the open `添加资源库`
three-step drawer. File rows may include bounded FileIndex-derived recognition and business-status
feedback; raw FileIndex authority fields are not shown.

**Action:** browse a ResourceLibrary-relative directory, refresh, switch list/grid presentation,
select or clear files, open folders, use the `添加资源库` drawer, save the candidate through the
backend validation/activation flow, and open the existing server-authoritative Preview/intent
journey.

**Success:** the operator sees the approved Files composition, can identify the selected file and
next action, a saved ResourceLibrary becomes part of the Active runtime, and terminal Organize
results synchronize their known business outcome to FileIndex.

**Failure:** missing Active configuration, unavailable Storage, invalid ResourceLibrary-relative
path, unauthorized or forbidden access, malformed response, empty directory, invalid
ResourceLibrary candidate, activation failure, Organize failure or FileIndex synchronization
failure is shown as a bounded state with no fabricated success rows, unsafe mutation or uncertain
replay.

**Recovery:** retry the bounded read, return to the ResourceLibrary root, select another enabled
ResourceLibrary, correct and resubmit a failed ResourceLibrary save, clear the selection, inspect
the durable Organize result or repair the bounded FileIndex synchronization state. A failed save
preserves the previous Active configuration. No error state automatically replays uncertain
Storage mutation or navigates to an unrelated page.

## Required Outcomes

| ID | Outcome | Acceptance state |
|---|---|---|
| RO-1 | **Reference fidelity.** | A controlled `1536 x 1024` screenshot of the Files success state matches `docs/pics/文件页.png` pixel for pixel after fonts and assets are loaded. |
| RO-2 | **Exact Files composition.** | The shell, page header, banner, ResourceLibrary summary, directory tree, breadcrumb, toolbar, table, row values, status/actions, selection footer and pagination appear in the exact order and visual hierarchy defined by the reference. |
| RO-3 | **ResourceLibrary drawer.** | The right drawer, three-step indicator, form labels/placeholders/help text, toggle and footer controls match the reference; the drawer creates a ResourceLibrary and remains local to Files. |
| RO-4 | **Save and activation.** | Final `保存` submits one complete ResourceLibrary candidate; the backend uses the current Active configuration, runs validation and activation atomically, and exposes the new ResourceLibrary only on success. Any error rejects the save and preserves the previous Active. |
| RO-5 | **Files data and status.** | Physical entries come from live Storage. Files may show bounded FileIndex recognition/business-status feedback, but FileIndex does not provide physical listing, source identity, path, Preview or execution authority. |
| RO-6 | **Organize workflow.** | Files-originated Preview remains ResourceLibrary-scoped and Storage-relative, derives SourceIdentity from live Storage, continues through the existing Preview/intent/OrganizerExecutor authority and synchronizes each terminal Organize outcome to FileIndex. |
| RO-7 | **Actionable recovery.** | Loading, empty, unauthorized, forbidden, unavailable, invalid-path, malformed, Storage-error, activation-error and index-sync-error states preserve page context and provide a safe next action without fabricated rows or automatic uncertain replay. |
| RO-8 | **Other pages frozen.** | Dashboard, Operations, Review, Configuration, Notifications, Settings, V1 `/ui`, shared route semantics and unrelated backend authority do not change as part of Files-page work. |
| RO-9 | **Test reconciliation.** | When an existing test asserts behavior that conflicts with this Slice Contract, the conflicting old test is deleted and replaced by a test for this Contract. No contradictory compatibility assertion is retained merely to preserve historical behavior. |
| RO-10 | **Security model continuity.** | This Slice introduces no new authentication, identity, session, RBAC, secret, execution-token or security model. It reuses the existing API-principal, permission, audit, immutable Active snapshot, explicit intent and OrganizerExecutor boundaries. |

## Required Surface

Only this surface is in scope:

- V2 Files page: `/ui-v2/library/files`;
- the Files page-local `添加资源库` drawer;
- bounded ResourceLibrary browsing, status feedback, selection and organize continuation;
- backend/application behavior strictly necessary for ResourceLibrary Save/activation and terminal
  Organize-result synchronization.

The visual screenshot includes the shared shell for context, but shared shell behavior is frozen.
Any future code change must prove that frozen pages retain their previous screenshots and journeys.

## Product and UX Constraints

- Treat the reference image as a product acceptance artifact, not an inspiration board.
- Preserve `Goal -> Entry -> Visible state -> Action -> Success -> Failure -> Recovery`.
- Keep the primary Files action visible and direct: browse, select, then continue with the bounded
  page-local action.
- Do not expose raw tokens, internal claims, fingerprints, provider payloads, absolute host paths
  or implementation-only identifiers in the page.
- Do not introduce a new security model. Reuse the existing authentication, RBAC, permission,
  audit, immutable Active snapshot, explicit mutation intent, execution authority and
  OrganizerExecutor boundaries.
- Do not use a generic error, hidden selection or disabled control as a substitute for explaining
  the affected ResourceLibrary/file state and next safe action.
- Do not add an alternate Files shell or a second navigation vocabulary.
- Keep the exact reference success state deterministic and preserve bounded responsive behavior.

## Safety and Authority Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation.
- Files reads, refreshes, directory navigation, selection and view switching do not mutate Storage
  or create Tasks, Jobs, Provider requests or organize work.
- All file operations remain behind Storage and ResourceLibrary boundaries; arbitrary host paths are
  rejected.
- Files-originated organize Preview and its continuation do not use FileIndex for physical source
  identity or execution authority. The browser submits only ResourceLibrary identity and relative
  path; backend admission derives SourceIdentity from live Storage.
- Only `OrganizerExecutor` may mutate Storage. Files-page controls never grant mutation authority.
- Overwrite, source cleanup/delete and unsupported operation fallback remain explicit and fail closed.
- FileIndex membership, fingerprints, occurrence IDs, claim tokens and plan hashes are not ordinary
  Files-page display authority. A bounded recognition/business-status projection is allowed for
  display, and terminal Organize results synchronize to FileIndex after Result persistence.
- The final ResourceLibrary `保存` action is backend-atomic: it uses the current Active
  configuration, performs validation and activation, and exposes the new ResourceLibrary only after
  success. Any error rejects the save and preserves the prior Active configuration.
- FileIndex-backed compatibility and legacy operation routes may remain elsewhere, but outside the
  bounded display feedback and terminal-result synchronization they are not an allowed dependency
  of the ResourceLibrary Files page or organize path.
- No FFprobe/FFmpeg dependency, content probing, provider switch or new security model is introduced.
- No schema migration or persistence rewrite is introduced by this Slice. Any focused persistence or
  API change required for terminal FileIndex synchronization must preserve the existing schema and
  authority boundaries unless separately approved by A.
- Existing V1 `/ui`, V2 non-Files routes, API/RBAC behavior and production serving remain intact.

## Test and Compatibility Policy

- Every implemented behavior must have automated coverage for success, invalid input, conflict,
  failure and important edge cases at the appropriate test level.
- Tests must prove that ResourceLibrary Save rejects invalid or conflicting candidates and preserves
  the previous Active configuration.
- Tests must prove that Files physical entries remain Storage-authoritative while FileIndex status
  feedback is display-only.
- Tests must prove that Preview does not use FileIndex for source identity or execution authority.
- Tests must prove that terminal Organize results synchronize per item and that index-sync failure
  does not replay completed or uncertain Storage mutation.
- If an existing test conflicts with this Contract, delete the conflicting test and build its
  replacement in the same implementation Task. Do not weaken the Contract to satisfy obsolete tests.
- Do not add tests that require production SMB/OpenList/S3/TMDB services; use fakes, mocks or local
  test servers.

## Explicitly Deferred

- General Configuration/Settings administration, revision comparison, import/export and separate
  explicit lifecycle controls outside the Files-page ResourceLibrary Save flow.
- Dashboard, Operations, Tasks, Jobs, Automation, Notifications and their visual redesign.
- Review, conflict resolution, checkpoint continuation, Reprocess and failed-item/batch recovery as
  a separate page journey, except for bounded post-Organize FileIndex synchronization recovery.
- V2 parity/cutover, accessibility-wide audit and V1 UI retirement as separate program work.
- New providers, new Storage capabilities, upload/download/content preview/edit/delete and arbitrary
  host filesystem browsing.
- Any new authentication, identity, session, RBAC, secret, execution-token or security model.

## Slice Acceptance Criteria

- [ ] `docs/pics/文件页.png` remains unchanged and is linked as the sole visual reference.
- [ ] The future implementation reproduces the exact `1536 x 1024` success screenshot with zero
      unexplained pixel difference in the controlled comparison environment.
- [ ] All exact labels, values, row order, selection states, drawer steps and controls from the
      visual spec are present.
- [ ] `+ 添加资源库` creates a ResourceLibrary and final `保存` performs backend validation and
      activation as one user action; any error rejects the save and preserves the previous Active.
- [ ] Files physical listing remains Storage/ResourceLibrary-authoritative, while bounded
      FileIndex business status is display-only.
- [ ] Every terminal Organize item synchronizes its known result to FileIndex independently, and
      synchronization failure never replays completed or uncertain Storage mutation.
- [ ] Files-originated Preview remains FileIndex-independent for source identity and execution
      authority.
- [ ] Failure and recovery states are bounded, actionable and do not fabricate reference data.
- [ ] Old conflicting tests are removed and replaced with Contract-aligned tests.
- [ ] No new security model is introduced.
- [ ] Other page screenshots, routes, API behavior, authorization and Storage mutation boundaries
      remain unchanged.
- [ ] The Slice implementation checkpoint contains only Files-page work and necessary focused
      evidence.

## Final Validation Expectations

The eventual Slice review must include:

- a deterministic browser screenshot at `1536 x 1024` compared directly with the canonical image;
- focused interaction evidence for navigation, directory selection, file selection, refresh,
  list/grid controls, drawer open/close, ResourceLibrary Save success/failure and bounded recovery;
- a route smoke check demonstrating unchanged behavior for frozen pages;
- exact request/mutation evidence showing reads and selection are zero-side-effect, Preview does not
  use FileIndex authority, and Organize result synchronization is per-item and non-replaying;
- test evidence showing conflicting old tests were removed/replaced where applicable;
- proof that the existing security model was reused without adding a new one;
- `git diff --check`, scope inspection and confirmation that the reference image and private
  configuration remain untouched.

This is an A-owned Contract replan. It does not claim implementation completion or test completion.

## Review State

~~~
Slice Status: ACTIVE
Implementation Head: NOT SET
P0/P1 Defects: None known in this Contract replan.
Next Action: checkpoint this Contract, then B plans one coherent implementation Task
~~~
