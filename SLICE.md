# Slice 37 — Files Page Visual Fidelity

This is the A-owned Slice Contract for the focused Files page effort. Slice 33 remains
`PASS / CLOSED` in Git and Progress history. The previously planned Slice 34, Slice 35 and Slice 36
boundaries are retired from the current Roadmap on 2026-09-14; their historical mentions remain
historical facts and are not current commitments.

~~~
Slice ID: 37
Name: Files Page Visual Fidelity
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: b507edba167f5af3af8c53bfcf1417ba4fefddf4
Implementation Head: NOT SET
~~~

The Base is the current committed `main` checkpoint immediately before this documentation-only
activation. No production implementation is included in this activation. B must plan an
implementation Task only after this Contract is checkpointed, and Developer work must remain inside
this Contract.

## Scope decision

The current Roadmap has one active focus: the Files page represented by
[`docs/pics/文件页.png`](docs/pics/文件页.png). This Slice does not revive, rename or absorb the
retired future Slices. It also does not change the V1 product requirements, the backend authority,
the processing pipeline or any page other than Files.

The detailed visual source of truth is
[`docs/file-page-visual-spec.md`](docs/file-page-visual-spec.md). If this Contract and the image
appear to disagree about visual detail, the image is authoritative and the Contract controls
product scope and safety.

## User goal and vertical journey

**Goal:** an authorized operator can open the V2 Files page, understand the active ResourceLibrary,
browse its directories, select a bounded file set and see the exact approved Files-page composition
without being redirected to a different page or asked to interpret backend implementation details.

**Entry:** select `文件` in the V2 shell or open `/ui-v2/library/files` (router path
`/library/files`) with the existing memory-only API-principal authentication boundary.

**Visible state:** at the reference `1536 x 1024` viewport the page shows the MediaFlow shell,
active Files navigation, search bar, ResourceLibrary summary, information banner, directory tree,
breadcrumb, file table, selected row, selection footer, pagination and the open `添加媒体库`
three-step drawer exactly as specified in the visual document.

**Action:** browse a ResourceLibrary-relative directory, refresh, switch list/grid presentation,
select or clear files, open folders, open a bounded local file action and use the drawer controls.
Any organize continuation remains the existing server-authoritative Preview/intent journey.

**Success:** the operator sees the same layout, copy, hierarchy, values, selected states and
controls as the reference image, can identify the selected file and next action, and does not
change Storage merely by reading or selecting.

**Failure:** missing Active configuration, unavailable Storage, invalid ResourceLibrary-relative
path, unauthorized access, forbidden access, malformed response or an empty directory is shown in
the Files page as a bounded state with no fabricated success rows and no unsafe mutation.

**Recovery:** retry the bounded read, return to the ResourceLibrary root, select another enabled
ResourceLibrary, clear the selection or leave the Files page. No error state automatically starts
Scan, Preview, Organize, Provider work or navigation to an unrelated page.

## Required Outcomes

| ID | Outcome | Acceptance state |
|---|---|---|
| RO-1 | **Reference fidelity.** | A controlled `1536 x 1024` screenshot of the Files success state matches `docs/pics/文件页.png` pixel for pixel after fonts and assets are loaded. |
| RO-2 | **Exact Files composition.** | The shell, page header, banner, ResourceLibrary summary, directory tree, breadcrumb, toolbar, table, row values, status/actions, selection footer and pagination appear in the exact order and visual hierarchy defined by the reference. |
| RO-3 | **Exact add-library drawer.** | The right drawer, three-step indicator, step-1 form labels/placeholders/help text, toggle and footer controls match the reference; the drawer remains local to Files and does not redefine Configuration authority. |
| RO-4 | **ResourceLibrary journey.** | Files browsing remains ResourceLibrary-scoped and Storage-relative. Reads, selection, refresh and presentation changes remain bounded and zero-mutation; FileIndex is not required for ordinary Files-page display. |
| RO-5 | **Actionable state and recovery.** | Loading, empty, unauthorized, forbidden, unavailable, invalid-path, malformed and Storage-error states preserve page context and provide a safe next action without fabricated rows or automatic mutation. |
| RO-6 | **Other pages frozen.** | Dashboard, Operations, Review, Configuration, Notifications, Settings, V1 `/ui`, shared route semantics and shared backend authority do not change as part of Files-page work. |
| RO-7 | **Evidence and scope discipline.** | The visual spec remains linked to the unchanged reference image, implementation evidence is browser-based, and no code, test, schema, provider, Storage or persistence change is included in this documentation-only activation. |

## Required Surface

Only this surface is in scope:

- V2 Files page: `/ui-v2/library/files`;
- the Files page-local `添加媒体库` drawer shown in the reference;
- the existing bounded ResourceLibrary browsing and selection continuation from that page.

The visual screenshot includes the shared shell for context, but shared shell behavior is frozen.
Any future code change must prove that frozen pages retain their previous screenshots and journeys.

## Product and UX Constraints

- Treat the reference image as a product acceptance artifact, not an inspiration board.
- Preserve the journey contract `Goal -> Entry -> Visible state -> Action -> Success -> Failure ->
  Recovery`.
- Keep the primary Files action visible and direct: browse, select, then continue with the bounded
  page-local action.
- Do not expose raw tokens, internal claims, fingerprints, provider payloads, absolute host paths
  or implementation-only identifiers in the page.
- Do not use a generic error, hidden selection or disabled control as a substitute for explaining
  the affected ResourceLibrary/file state and next safe action.
- Do not add an alternate Files shell or a second navigation vocabulary.
- Keep the exact reference success state deterministic so visual comparison is meaningful.
- Preserve accessible names, keyboard operation, focus visibility and bounded responsive behavior;
  the reference viewport is the pixel-fidelity gate, not permission to regress other viewports.

## Safety Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation.
- Files reads, refreshes, directory navigation, selection and view switching do not mutate Storage
  or create Tasks, Jobs, Provider requests or organize work.
- All file operations remain behind Storage and ResourceLibrary boundaries; arbitrary host paths are
  rejected.
- Only `OrganizerExecutor` may mutate Storage. Files-page controls never grant mutation authority.
- Any future organize continuation reuses the existing Preview, explicit intent, conflict,
  capability, source revalidation, configuration snapshot and OrganizerExecutor checks.
- Overwrite, source cleanup/delete and unsupported operation fallback remain explicit and fail
  closed.
- The browser does not persist the API-principal Bearer token or receive raw execution authority.
- FileIndex membership, fingerprints, occurrence IDs, claim tokens and plan hashes are not ordinary
  Files-page display authority.
- No FFprobe/FFmpeg dependency, content probing, provider switch, schema migration or persistence
  rewrite is introduced by this Slice.
- Existing V1 `/ui`, V2 non-Files routes, API/RBAC behavior and production serving remain intact.

## Explicitly Deferred

- Review, conflict resolution, checkpoint continuation, Reprocess and failed-item/batch recovery
  as a separate page journey.
- General Configuration/Settings administration, revision comparison, import/export and activation
  outside the visual drawer state shown on Files.
- Dashboard, Operations, Tasks, Jobs, Automation, Notifications and their visual redesign.
- V2 parity/cutover, accessibility-wide audit and V1 UI retirement as separate program work.
- New backend endpoints, database/schema changes, Storage adapters, Metadata Providers, identity
  systems, Secret Store integration, upload/download/content preview/edit/delete and arbitrary host
  filesystem browsing.
- Mobile-specific redesign, alternate themes, global navigation rewrite and any unrelated visual
  polish.

## Slice Acceptance Criteria

- [ ] `docs/pics/文件页.png` remains unchanged and is linked as the sole visual reference.
- [ ] The future implementation reproduces the exact `1536 x 1024` success screenshot with zero
      unexplained pixel difference in the controlled comparison environment.
- [ ] All exact labels, values, row order, selection states, drawer steps and controls from the
      visual spec are present.
- [ ] Files remains a ResourceLibrary-scoped, Storage-relative, read-only browsing/selection
      surface until an explicit existing organize continuation is chosen.
- [ ] Failure and recovery states are bounded, actionable and do not fabricate the reference data.
- [ ] Other page screenshots, routes, API behavior, authorization and Storage mutation boundaries
      remain unchanged.
- [ ] The Slice implementation checkpoint contains only Files-page work and its necessary focused
      evidence.

## Final Validation Expectations

The eventual Slice review must include:

- a deterministic browser screenshot at `1536 x 1024` compared directly with the canonical image;
- focused interaction evidence for navigation, directory selection, file selection, refresh,
  list/grid controls, drawer open/close and bounded recovery states;
- a route smoke check demonstrating unchanged behavior for frozen pages;
- exact request/mutation evidence showing reads and selection are zero-side-effect and any organize
  continuation remains backend-authoritative;
- `git diff --check`, scope inspection and confirmation that the reference image and private
  configuration remain untouched.

This activation itself is documentation-only. No implementation test is claimed in this Contract.

## Review State

~~~
Slice Status: ACTIVE
Implementation Head: NOT SET
P0/P1 Defects: None known in this documentation-only activation.
Next Action: B PLANS ONE COHERENT FILES-PAGE IMPLEMENTATION TASK AFTER CONTRACT CHECKPOINT
~~~
