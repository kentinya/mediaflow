# Slice 44 — Existing V2 Pages Functional Improvements

This is the A-owned Contract for one Slice covering functional improvements across
already implemented pages. The user has selected consistent ordinary file-operation behavior for
ResourceLibrary Files and MediaLibrary Files, reference-aligned organizing-rules presentation, and
classification destinations defined by MediaLibrary plus `path`, plus object-scoped Rules tests
with a separate complete-flow check, usable long-name breadcrumbs/toolbars on both library pages,
and bounded ResourceLibrary folder/mixed-selection organization. These six Required Outcomes
define the activated boundary; unspecified improvements remain outside this Contract.

```text
Slice ID: 44
Name: Existing V2 Pages Functional Improvements
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 853973dbbf8289fa2ad40657033e94e870a690e4
Implementation Head: 8be263ea778df08aa374e9433f138a218c1d4af9
Contract Revision: 2026-10-11 — PARTIAL / RESCOPE: user-approved discovery recovery reduction; safety and original Base retained
Working Branch: slice/44-page-improvements
Risk: High for Storage mutations, folder admission/recovery, classification compatibility and configuration/evidence authority
Final Test Level: T4 for the complete RO-1 through RO-6 boundary
Next Action: A SELECTS THE NEXT LARGE SLICE
```

Closure Date: 2026-10-12. The six-outcome Contract, its original Base and the user-approved recovery
rescope are retained. The authority/activation/baseline notes and prior review sections below
record their historical states; the final A Review and Closure Reconciliation at the end govern
current acceptance. No next Slice is selected in this checkpoint.

## Authority and sequencing

The user explicitly authorized A to freeze Slice 43, preserve its related implementation, and
reserve one new Slice for improvements across multiple previously implemented pages. The user
then specified that Slice contents will be added later. This is the user-authorized priority
exception in [the development workflow](docs/development-workflow.md), not acceptance of Slice 43
or reopening of an accepted historical Slice.

The user subsequently granted A authority to incorporate the organizing-rules workspace visual
correction into this existing Slice 44, then answered yes to including the earlier classification
`library/path` behavior correction as well. RO-2 and RO-3 record that authorization. That amendment
selected one coherent Rules improvement alongside RO-1; it did not activate the Slice, create a
Task, resume frozen Slice 43, or change the accepted Slice 37/41 closure records.

The user subsequently granted A authority to incorporate the reviewed page-local offline-test
proposal into current Slice 44. RO-4 records that authorization: each editor tests its current
object and necessary inputs, while complete-flow checks have an explicit separate entry. This
was a PLANNED scope amendment preceding this activation; implementation still requires B's
active Task. It preserves the distinction between RecognitionType definition and RecognitionRule
conditions, and does not weaken checked publication or runtime/execution prerequisites.

This branch starts from `853973dbbf8289fa2ad40657033e94e870a690e4`, the factual closure checkpoint
of accepted Slice 42 and the original Slice 43 Base. It therefore includes the accepted existing
pages and excludes the unaccepted Slice 43 implementation. Only the explicit development-hold /
PLANNED governance support is carried across. No application code has been changed for Slice 44.
The existing product, architecture and permanent safety requirements remain authoritative.

The user subsequently accepted the existing same-Storage Move rules as the ordinary-file-operation
baseline, requested other operations follow those rules, reviewed the operation-by-operation plan,
and explicitly authorized A to incorporate it into Slice 44. That amendment selected the outcome;
it did not itself authorize activation, B Task planning, implementation or unselected page work.

The user further confirmed that every applicable common file-operation policy must apply to the
MediaLibrary page as well. RO-1's MediaLibrary behavior is a required delivered surface, not only
a regression check or optional follow-up after ResourceLibrary Files is completed.

This is an explicit TARGET change to the current technical fingerprint gate, not a claim that the
baseline code already implements it. The CURRENT description in `docs/architecture.md` remains
factual until implementation and acceptance. Its mandatory-fingerprint behavior for direct Rename,
Delete and cross-Storage source removal must not be promoted back into acceptance criteria for this
selected outcome. This decision does not weaken permanent permission, intent, confinement,
snapshot, ownership, conflict, audit or non-replay invariants, and does not revise media Organize
Preview/source-authority rules or accepted historical closure records.

The user subsequently reviewed the long-name toolbar repair proposal and explicitly authorized A
to incorporate it into Slice 44. RO-5 selects that browsing/layout outcome on both library pages,
including the reported Docker-served presentation. That scope amendment did not activate the
Slice, create an implementation Task or authorize deployment. That amendment selected layout only;
earlier metadata-score/manual-review questions and mixed file/directory Organize behavior remained
outside it.

The user subsequently reviewed the ResourceLibrary folder/mixed-selection organizing proposal and
explicitly granted A authority to incorporate it into Slice 44. RO-6 selects recursive bounded
discovery, mixed-selection deduplication, configured filtering/stability, background progress and
safe continuation into the existing exact manual Preview/execution journey. The first delivery
retains the existing 100-primary-media bound per organizing intent. That was a PLANNED scope
amendment; it did not itself authorize activation, B Task planning, implementation or deployment.
MediaLibrary remains a destination/file-management surface, not an organizing source. RO-6 is
separate from RO-1's direct-file optional-fingerprint policy and RO-5's presentation repair.

The user has now explicitly requested activation of Slice 44 under A's granted authority. A
activates the complete RO-1 through RO-6 Contract and its T4 final gate without changing the Base,
required behavior, acceptance criteria or frozen Slice 43. Once this ACTIVE Contract and Roadmap
are checkpointed, B may plan one coherent implementation Task. Activation creates no Task, claims
no implemented outcome and grants no deployment or Slice 43 resumption authority. Any additional
material scope change returns to A through the development workflow.

Applicable guidance includes canonical Storage management/abstraction, direct file commands,
MediaLibrary file management and file-list journeys; UX-001 through UX-010; REQ-STO-001/002/003/006,
REQ-TASK-002/003/005/006/007, REQ-API-002/003 and REQ-SAFE-001 through REQ-SAFE-007/009; and
V2-UX-001/002/003, V2-FILES-001/002/003, V2-AUTH-001/002/003 and V2-SAFE-001. Broader stable targets
such as browser Upload/Download do not expand this selected Slice outcome.

Rules improvements additionally apply V2-RULES-001 through V2-RULES-009, V2-SHELL-001,
REQ-REC-001/002/003/004, REQ-CONFIG-002/007/009, REQ-CLASS-001/003/005, REQ-ORG-001/003/004
and the existing configuration, preview, Task/recovery and unattended-authorization invariants.
RO-3 restores the canonical final-path
formula; CURRENT descriptions of the older `library/path` prefix remain factual until delivery
and acceptance. Reference layout does not authorize a different matching algorithm or mutation
authority.

Folder organization additionally applies REQ-LIB-001, REQ-SCAN-002/003/005,
REQ-ATT-001/002/003, REQ-CONFIG-008, REQ-TASK-001 through REQ-TASK-007/009,
REQ-RECOVERY-001/002/006/007/008/009, REQ-ORG-001/003/004/007/008/009/010/011/012,
REQ-REC-004, REQ-WEB-001/005/007 and the existing API, redaction and mutation-safety requirements.
Folder selection does not itself authorize execution, overwrite, source removal or directory cleanup.

### Prior architecture amendment and planning exception — 2026-10-11

The following records the earlier amendment and planning checkpoint. Its seamless-discovery
recovery obligations are superseded by the user-approved PARTIAL / RESCOPE below; the audit and
unimplemented defects remain historical evidence, not accepted fixes.

After A's complete folder-journey audit, the user explicitly requested incorporating the simpler
discovery design into this Slice and asked A to substitute for B in Task planning. This amendment
changes the implementation architecture Contract and requires fresh planning; it is not factual
wording cleanup or permission for Developer to continue an old Task. A exercises the authorized
planning exception once. B retains independent Task review, and A retains Slice Final Review;
neither role may treat this planning decision as implementation acceptance.

The same business boundary remains: RO-1 through RO-6, their required surfaces, Safety Invariants,
acceptance 1–32, Deferred and the original Base. The reviewed implementation still requires all
eight P1 corrections A44-6 through A44-13; the A Final Review below remains FIX REQUIRED and the
previous Closure Packet/Task 44.8 PASS remain historical. No outcome is removed or added, no
business rescope/new Slice is needed, and no CURRENT delivery or closure is declared. Checkpoint
this A amendment before planning the replacement correction Task. A's authorized planning must
explicitly reassess the current no-active-Task state against this amended Contract.

That reassessment is now recorded in `TASK.md`: Task 44.8 remains historically PASS and no old
implementation Task was active; user-authorized A planning selects one new focused correction,
Task 44.9, High / T4, inside the checkpointed amendment. Its PLANNED handoff supersedes the older
review's planning next action only. All eight blockers remain unresolved and no B PASS is issued.

### Current user-approved recovery rescope and planning authority — 2026-10-11

After questioning the complexity and likelihood of exceptional discovery conditions, the user
explicitly requested updating Slice and Task to the proposed smaller delivery. This is a Material
Contract Change to RO-6 recovery and acceptance 30, not wording cleanup: interruption may end an
unfrozen discovery with an actionable durable record and explicit new discovery, instead of
guaranteed cursor-perfect continuation through every crash/control/version combination.

Lost-response readback must never guess another admission, root or pin or automatically resubmit.
If the original admission can be proved, recover it; otherwise show unresolved admission with a
native Operations inspection/resolution action. Automatic original-request recovery through a
simultaneous activation/root change, automatic repair/resumption of every legacy duplicate or
interrupted discovery, and seamless preservation of unpublished work through arbitrary control
races are explicitly deferred. These are reduced recovery promises, not repaired defects.

RO-1 through RO-5, all required Web/API surfaces, normal cooperative discovery controls, genuine
stability, truthful partial findings, the 100-primary bound and every Safety Invariant remain.
Ordinary configuration, long-name, read-failure, paging, attachment and Worker-readiness defects
still require correction; atomic same-scope admission and wrong-pin prevention remain required.

The original Base still represents this same Slice's start, so retain Slice 44 and its Base and
reactivate the amended Contract as ACTIVE. Preserve the earlier FIX REQUIRED reviews/Closure
Packets without declaring PASS. Checkpoint this amendment before Task planning. Task 44.9 is
PLANNED with no implementation checkpoint; return it for explicit reassessment rather than letting
Developer continue its superseded plan. The user's authorization for A to substitute for B planning
remains in force; B independently reviews implementation and A later reviews the full Slice.

Reassessment after A Contract checkpoint `7e96ebf314e4eab22a72d98028a775f248118138`: governance
passed with ACTIVE Slice and no active Task, then again with the legally adjusted PLANNED Task
44.9. Authorized A planning retains its ID/original Task Base and High/T4 gates, replaces its
exceptional-recovery obligations with this smaller Contract, and hands it to Developer. The prior
plan is preserved in Git; B review is PENDING. No implementation or product PASS is claimed.

## Frozen Slice 43 preservation and resumption

- Preservation branch: `frozen/slice-43-2026-10-07`.
- Freeze checkpoint: `8a41e131f3a668388381ab51c8876668108871d8`.
- Complete Task 43.1 and latest B review snapshot: `a447e3129be89bd20f6a24831b2be122d4fdf955:TASK.md`.
- Latest implementation checkpoint: `b364a04d1c916ed327e3e8f470dc05e413ad80e6` (unaccepted).
- Original Slice 43 Base: `853973dbbf8289fa2ad40657033e94e870a690e4` (unchanged).
- Task 43.1 remains FIX REQUIRED; its removed-definition-history P1 and complexity reassessment
  are retained in the review snapshot. No closure, completed outcome or resolved blocker is claimed.

Resuming Slice 43 requires explicit A activation of its preserved Contract and recovery of the same
Task ID/Base/Goal/Scope and B blockers. A must assess any intervening accepted improvements before
integration. Neither this placeholder nor a later Slice 44 activation grants permission to continue
Slice 43, silently repin its Task, merge its rejected code or rewrite its review history.

## User Goal and Journey

An operator can maintain real files through the existing ResourceLibrary and MediaLibrary pages
using the actual operations supported by Local, SMB, OpenList and S3/R2, without a missing provider
fingerprint alone disabling a supported ordinary command.
When names or paths are long, the operator can still identify the current directory, navigate its
ancestors, refresh and change view without toolbar controls overlapping or being clipped by entries.
From ResourceLibrary Files, the operator can also select folders and files together, review the
bounded discovered media and exclusions, and organize the exact reviewed items without opening
every subdirectory and selecting each media file separately.

An operator can also find, search and maintain the complete organizing-rule graph through the
reference-aligned workspace, and configure a destination using the selected MediaLibrary and one
safe classification path, without a media-library display name becoming an extra directory.
While adding, copying or editing an individual rule or policy, they can also test that exact
object without first completing unrelated downstream configuration, understand why its sample
matched or did not match, and deliberately check the complete flow when needed.

The following direct-file journey belongs to RO-1; Rules presentation, destination and testing
journeys are defined separately under RO-2, RO-3 and RO-4, long-name browsing under RO-5, and
ResourceLibrary folder/mixed-selection organization under RO-6, with their own state, outcome and
recovery.

- **Entry:** existing `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files`, their row/selection
  actions, text editor, transfer dialog and linked Task/Operations recovery.
- **Visible state:** live entries, current name/type/size/time, intended destination, bounded delete
  or transfer impact, per-item progress and known successful/retained/partial/uncertain effects.
- **Action:** browse/refresh, Create Folder/Text File, Rename, Delete, same/cross-Storage Copy/Move,
  and bounded text Open/Edit/Save through existing native Web journeys.
- **Success:** supported commands complete under a consistent observable-metadata rule, results
  remain durable, and live refresh updates the list, tree, selection and path context.
- **Failure:** invalid input/scope, permission/read-only/capability denial, conflict, observed source
  change, changed delete scope, transfer verification failure or uncertain mutation explains the
  affected item and its durable state; no sibling result is concealed.
- **Recovery:** retain correctable input, refresh/reobserve/reconfirm where needed, resolve the
  current conflict, or use backend-advertised per-item continuation after reconciling effects.
  A timeout is not proof of failure and never triggers automatic mutation resubmission.

Unspecified existing-page improvements are outside the activated RO-1 through RO-6 boundary;
material additions require A's Contract amendment. A single operation or page is not automatically
another Slice.

## CURRENT Audit and TARGET Rule

The accepted baseline already shares direct-file application/API/Executor behavior across both
library kinds. Local publishes `inode + ctime` fingerprints; OpenList publishes entry type, size
and modification time without a fingerprint. Direct Rename/Delete currently reject missing
fingerprints. Same-Storage Move allows absent fingerprints and revalidates observable metadata;
cross-Storage Move can verify a destination and then return partial solely because deleting its
source requires a fingerprint. Bounded text Save uses its separate content-digest fence.

The TARGET is one shared observable-state policy for ordinary direct operations:

1. Bind server-observed evidence to the exact library kind/ID, Storage/root, relative path and
   applicable immutable configuration context. Fingerprint becomes optional; the observation,
   command intent and scope evidence do not. Preserve exact names, including boundary whitespace.
2. Every source revalidation checks existence and supported entry type. Files compare size and
   modification time, plus a provider fingerprint when observed. Directories compare available
   stable identity, otherwise existence/type; directory Delete additionally binds the enumerated
   effect and requires an empty directory at its final removal boundary. Do not compare a Local
   directory ctime that legitimately changes as its confirmed children are removed.
3. A fingerprint present in the observation remains binding: changed or missing current evidence
   is stale, not permission to downgrade. Do not fabricate identifiers from path/size/time or
   pretend metadata equality proves exact object/content identity.
4. Revalidate at submission and the last safe mutation boundary. Missing fingerprints alone must
   not disable supported Rename/Delete or the source-removal stage of cross-Storage Move.
5. Rename/Delete observation and validation read metadata only: no media-content sampling, full
   read, content hashing or duplicate-detection FULL Hash. Keep bounded text-edit digest checks
   and actual cross-Storage transfer byte/digest verification for their existing purposes.
6. The user-authorized rule accepts that a replacement with indistinguishable metadata, directory
   inode reuse, or external mutation between final checking and execution may escape detection.
   Backend ownership fencing remains mandatory. Describe observable-state checks truthfully;
   universal exact-version/atomic-condition guarantees are not required for this direct journey.
   This residual limitation does not permit an unconfirmed scope expansion, known stale mutation,
   deliberate silent overwrite/delete, or automatic replay of an uncertain effect.

### CURRENT Rules audit and selected TARGET

The accepted Rules page already has full-width inventories, explicit Add/copy drawers, full-page
Edit, typed forms, exact-candidate previews and focused checked publication. Its current shared
shell puts an unrelated, read-only Files search above the Rules title; family navigation is plain
text buttons. One wrapping toolbar combines the inventory heading, search, state filter and Add
button, placing Add last. Forms largely stack generic inputs, use a single-line description and
checkbox enable state, and reuse Files drawer styles. These are the structural and styling gaps
selected by the user's annotated `整理规则需修复.png` and original six Rules references.

Classification currently requires `library` alongside `mediaLibraryId` and `path`; Web fills
`library` from the destination library's display name. The shared destination composer prefixes
that value before the classification path in formal Planner and destination previews. The TARGET
removes that prefix for the revised configuration contract while preserving the explicit library
reference, safe relative path, naming contribution and exact historical snapshot semantics.

The current shared Rules test panel routes RecognitionType and RecognitionRule tests through
`preview_strategy` / `recognition_strategy_test`. Candidate staging validates a composed document,
and strategy analysis loads a runtime, parses the synthetic path, runs configured recognition and
resolves the winning type's downstream binding. A matched rule with no type binding therefore
fails with `PolicyResolutionError`; a path without the required directory can complete as
unrecognized. The shared sample form also exposes title/type fields that the strategy request
does not consume. These are CURRENT coupling and explanation gaps, not evidence that recognition
itself failed. RO-4 separates object analysis from complete-flow readiness without changing the
production recognition algorithm or publication checks.

### CURRENT long-name library-page audit and selected TARGET

Both library pages use the same Files toolbar/breadcrumb/control classes. The current shared CSS
allows toolbar and breadcrumb wrapping while a later rule fixes the toolbar height at 52 px.
Ordinary long breadcrumb names lack a sufficient shrinking/overflow boundary. A wrapped control
row can therefore extend below the toolbar into the file viewport; an unbroken name can also exceed
the pane width. Read-only browser reconstruction using the deployed Docker CSS reproduced the
overlap on both page compositions with long mixed-language and unbroken synthetic names.

RO-5 selects bounded breadcrumb overflow, usable controls and toolbar height that accommodates its
actual rows. This is a frontend layout defect; the audit does not establish a Docker-only cause or
a Storage/refresh failure. No corrected application code or Docker artifact is claimed here.

### CURRENT folder-organize audit and selected TARGET

ResourceLibrary Files currently publishes `organizeEligible` only for ordinary files. Its folder
entry menu offers Open without Organize; the batch button counts only eligible files and filters
directories out of the submitted selection. A folder-only selection therefore cannot proceed.
The Files admission application independently rejects directory paths with `source_not_file`.
The current projection and admission tests explicitly assert these restrictions; existing directory
walks elsewhere do not constitute a native folder-organize journey.

RO-6 selects a bounded background discovery stage before the existing immutable manual intent,
exact Preview, explicit execution admission and OrganizerExecutor. Backend Storage observations
remain source authority. Neither enabling the button alone nor reusing a whole-library/indexed
scan completes this outcome. No folder-organize implementation is claimed by this planning revision.

## Required Outcomes

### RO-1 — Consistent ordinary file maintenance on supported Storage

Deliver the User Goal above on both library pages through shared backend behavior and native Web
actions. The following operation semantics are one business-capability outcome, not a pre-split
Task list. Preserve existing capability and library-kind boundaries; absence of a fingerprint is
not absence of a supported Storage operation.

#### Mandatory parity across ResourceLibrary and MediaLibrary pages

Every operation below applies to both `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files` where
the existing surface supports it: browsing, Create Folder/Text File, file/directory Rename, single/
batch/directory Delete, same/cross-Storage Copy/Move and bounded text Open/Edit/Save. Both share the
same observable-metadata/optional-fingerprint policy, permission/capability/conflict checks,
confirmation semantics, known/partial/uncertain results and safe recovery through application/API,
Executor and Task/Worker behavior. Page-specific wiring must not retain a separate mandatory
fingerprint gate or disable OpenList commands after the common backend supports them.

Retain each page's own library-kind identity, roots, selection/return context and allowed actions;
MediaLibrary transfers select MediaLibrary destinations, and ResourceLibrary transfers retain
their existing destination rules. Shared logic does not grant cross-kind direct transfer or add
Organize to MediaLibrary. B's Tasks and acceptance evidence must cover each affected surface before
RO-1 is complete; a ResourceLibrary-only fix or shared-service test alone cannot satisfy it.

#### Browsing and entry information

Validate read permission and relative-path confinement, then use bounded live Storage list/stat.
Keep paging, exact name/path identity and directory context. FileIndex/cache cannot authorize a
mutation or replace live observations. Reads/refresh do not create Tasks, Drafts or mutations;
unavailable data is an actionable read failure, not an empty successful directory.

#### Create Folder

Validate one basename, writable parent and provider capability. Check the parent still exists as a
directory and the target is absent before creating through OrganizerExecutor. An existing same-name
file/directory is a conflict, not a newly created success. Verify the resulting directory and refresh
selection/tree. After an unknown submission, presence alone cannot establish this command created
the entry; reconcile or report uncertainty before a deliberate new attempt.

#### Create Text File

Validate the existing allowlisted extension, UTF-8 and 512 KiB limit, writable parent and absent
target. Write without replacement through OrganizerExecutor/Storage, using the adapter's existing
publication mechanism; do not claim Local atomic publication for OpenList uploads. Verify bounded
text results, retain input on failure and reconcile unknown creation before resubmission. This is
not restoration of general browser Upload.

#### Rename one file or directory

Observe the entry when opening the dialog; automatically carry server evidence through submission.
Reject library root, unsupported links/types, invalid/unchanged basename, observed source change and
occupied target. Apply the TARGET Rule at admission and immediately before native same-Storage
rename, with no content read and no Copy/Delete fallback. Verify old-path absence and new-path
presence before reporting known success; remap list/tree/selection. Retain entered name on refusal.
After an interrupted command, reconcile both paths without treating name/size equality as ownership
proof or automatically replaying the rename.

#### Delete one file

Show its bounded effect and obtain one meaningful confirmation bound to the observed entry/context.
Revalidate at confirmation and immediately before Executor deletion using the TARGET Rule, even
without fingerprint. Verify absence, persist the result and refresh. Changed or missing confirmation
is refused; timeout/delete ambiguity is uncertain and requires reconciliation, not automatic retry.
Selecting Delete supplies explicit intent only for that confirmed item under current permission.

#### Delete directories or a bounded selection

Normalize and deduplicate overlapping selections; enumerate the complete affected tree under the
existing Delete item/depth/size limits, never silently truncating an authorized effect. Show counts/
known bytes and confirm once. Re-enumerate before admission: added/removed/type-changed or observably
changed entries invalidate the scope. Use durable Tasks and independent item results for long/batch
work, delete children before parents, and revalidate each item at execution. Before removing a parent,
check it is empty; unexpected/unconfirmed content stops that removal. Preserve per-item outcomes and
remaining contents when siblings fail or the task pauses/cancels. Completed effects stay completed;
remaining/rejected scope needs current observation and explicit safe continuation/reconfirmation.
OpenList list-empty then remove is not an atomic conditional delete; acknowledge that adapter window
without treating a known non-empty directory as eligible for recursive removal.

#### Same-Storage Copy

Resolve the permitted source/destination libraries and a bounded manifest, check scope/alias/self/
descendant restrictions and revalidate source/target at execution. Preserve native provider capability
and existing conflict choices: Skip, keep both with an available new name, or manual decision.
Create/Rename keep their no-replace contract, and this outcome does not introduce transfer Replace.
Use Local staging/native copying; OpenList's existing adapter uses server-side Copy for an unchanged
basename and streaming upload when a new basename requires it. Do not add a hidden alternate
operation when capability fails. Verify destination type/size and known native result, retain source,
and report verification/unknown-write failures independently. No new same-Storage media hashing is
required. Transfer known byte totals remain informational; selection/entry/depth/path/control-plane
bounds remain enforced, without reintroducing a total-media-byte admission ceiling.

#### Same-Storage Move

Retain its current absent-fingerprint admission behavior and apply the shared TARGET Rule. Recheck
conflict, capability and bounded manifest, use native move without application Copy/Delete fallback,
then verify source absence and target presence. OpenList directory-and-basename changes use native
Move then Rename: protect the intermediate name separately and never extend final-target permission
to an unrelated intermediate entry. Attempt compensation only when effects and destination conflicts
are sufficiently known to make it safe; failed/unknown compensation exposes the actual or uncertain
location. Interrupted native Move is not automatically complete from equal size or blindly replayable.

#### Cross-Storage Copy

Revalidate source/target, stream in bounded chunks through Executor-owned Storage write, and verify
destination byte count/content digest before success. Content reads serve the requested transfer,
not Rename/Delete admission. Leave source intact on every outcome; failed/truncated/unverified
targets retain truthful effect status and checkpoints. Cleanup/replacement of a partial target
requires attribution to this operation and applicable explicit authority; do not remove another
entry merely because it has the expected name. Preserve independent batch state and bounded scope.

#### Cross-Storage Move

Persist Copy-written, destination-verified and source-deleted checkpoints for the explicit compound
journey. After verified Copy, freshly revalidate the source under the TARGET Rule and current live
delete authority, then delete and verify absence. Lack of fingerprint alone does not block this
step. Changed source, authority loss, deletion refusal or unknown deletion after verified Copy yields
partial/uncertain effects with the verified destination and source's known state explained. Resume
only from attributable, revalidated durable checkpoints: do not automatically copy again or delete
again, and never infer completed Move from weak metadata alone. This applies to each file and final
empty source directory in existing supported directory transfers.

#### Bounded text Open/Edit/Save

Keep allowlisted regular text, UTF-8 and the 512 KiB limit. Open observes content and its digest;
Save compares the loaded size/digest at admission and the last safe write boundary, independent of
provider fingerprint availability. Reject changed/missing files without converting Save into Create;
retain unsaved input and offer reload/correction. Write via the adapter's existing mechanism and
verify the bounded text outcome before advancing the editor baseline. Unknown Save reconciles
without automatic replacement. The content fence is appropriate for the bounded document being
edited and must not reintroduce media-content scans into Rename/Delete.

### RO-2 — Reference-aligned organizing-rules workspace and purpose-built forms

Deliver the complete presentation and management journey across Overview, Type Bindings,
Recognition Types, Recognition Rules, Metadata Policies, Naming Policies, Classification Policies
and Organize Policies. This is one workspace outcome, not a separate Task for each tab, input,
search position or border style.

- **Goal/entry:** open existing `/ui-v2/rules`, a supported family deep link, Settings return link,
  or existing Edit route to find and maintain the intended rule through the native Web surface.
- **Visible state:** active family, real inventory/references/enable state, current keyword/filter,
  published versus unsaved input, and exact-candidate test/preview freshness. Routine presentation
  uses business labels; revision/identity diagnostics remain available without dominating the page.
- **Action:** navigate/search/filter/refresh; explicitly Add/copy/Edit; use backend-authorized
  lifecycle and the object-scoped tests/previews in RO-4; publish with one checked Save.
- **Success:** the reference-aligned controls occupy consistent positions, entered values remain
  legible and correctable, and successful publication refreshes the actual Active inventory.
- **Failure/recovery:** empty/partial/unavailable/denied states offer the existing dependency or
  access recovery; invalid fields are identified inline; stale or failed Save preserves input and
  the previous Active when known; unknown Save requires readback before another submission.
  Reopening the proper family restores its own correctable draft, never another family's input.

#### Shared header and family navigation

Match the annotated top region: title at left and functional Rules search plus existing account/
notification controls at right on the same desktop row, followed by one business-description line
and the family navigation. Use the existing shared shell with a route-aware header composition;
do not create a second shell or redesign other pages. Align header, navigation and inventory-card
edges and remove redundant Rules headings/context or unnecessary inset whitespace.

The eight navigation cards have an icon, a business name and a short description. Preserve their
reference order; use light-blue background and blue icon/text for the active card, white surfaces
and fine borders for the others. Display names may follow the references (`类型策略`, `命名规则`,
`分类规则`) while underlying policy families, routes and IDs retain their existing meanings.
Keyboard focus/current state and URL Back/Forward, refresh and authentication return must agree.

#### Inventory title and action/search row

Use a separate title/description row, then an action row with the blue `+ 添加xx` button at left
and icon-bearing keyword search/state filter at right, then the full-width table. Do not put the
title, all filters and Add in one wrapping row. Keyword inputs use contextual placeholders and
accessible labels; a visible extra `搜索` label above the input is unnecessary. Header and local
search share the current family's existing keyword state and filtering scope; typing/clearing
either must keep both truthful. Overview must explain or disable an inapplicable family search,
not advertise a fabricated global search. Cross-family search is not selected.

Retain truthful count/empty/filtered-empty/loading/failure states, real per-family columns and
reference/lifecycle controls. Reference sample IDs, rows, totals or statuses are not production
data. Narrow layouts deliberately wrap the action row and scroll wide tables without losing Add,
filters or a usable action; ordinary desktop placement must remain stable.

#### Add/copy drawers and Edit form presentation

Default family entry remains a full-width inventory with no automatically opened editor. Explicit
Add/copy opens the right drawer; existing Edit remains the supported full-page state. The reference
right panel defines form style, not permission to permanently split the initial page or open a
form merely by selecting a row. Apply the same form language to creation, copy and Edit.

Use labels above controls, backend-derived required markers and constraints, white controls with
fine light borders and small radii, a multiline description, and an accessible labelled enable
switch only for families that support it. Reference control heights of about 36–40 px and field
spacing of about 20–24 px guide the desktop density; do not replace actual limits with image
examples. Field hints/errors follow their own input. Keep current domain fields available through
purpose-built sections or appropriate Advanced controls instead of dropping them to fit the image.

- Recognition Types: ID, name, multiline description and enable state in a simple vertical form.
- Type Bindings: recognition type and four downstream policy selectors, with current references
  and available enable state; retain all required identity/compatibility fields.
- Recognition Rules: basic information, paired priority/score controls, output type, typed nested
  condition groups and explanation; AND/OR/NOT, ambiguity and stop behavior remain backend-owned.
- Metadata: basic information, Provider/type controls, paired language/region and existing bounded
  candidate/request/timeout/retry/matching settings; no Provider switching is introduced.
- Naming: basic information, the actual Movie/TV directory/filename template sections and existing
  missing-variable/length behavior; reference examples never collapse the real template families.
- Classification: basic information and a compact internal-rule list with priority, ID/name,
  condition summary, selected destination and actions. Its own `添加规则` sits at that list's upper
  right and is distinct from the outer `添加分类规则`. Rule create/edit exposes the full supported
  conditions and the RO-3 destination fields; ordered presentation does not change priority rules.
- Organize: purpose-built operation/conflict/attachment/duplicate/rollback/cleanup sections;
  preserve every applicable explicit high-risk permission and capability/fallback constraint.

Keep drawer title/footer visible while its body scrolls; footer actions align right in `取消`,
`保存` order. Simple desktop drawers can use approximately 500–560 px; complex conditions may
need more width, and narrow viewports use the available width. Rules styles must have clear scope
so Files drawer CSS cannot change their positioning/layout, and Rules fixes cannot alter other
pages' drawers. Retain focus management, keyboard operation and correctable close behavior.
Ordinary copy explains the user outcome; internal publication mechanics belong in diagnostics.

### RO-3 — Classification destination uses MediaLibrary and path only

- **Goal/entry:** create/edit a classification rule in the Rules workspace, inspect its exact-
  candidate preview and publish it through the existing checked Save.
- **Visible state:** selected MediaLibrary, its actual root, the one classification-relative path,
  matched-rule evidence, naming contribution and composed target. For legacy conversion, show
  the old and proposed target contributions before publication.
- **Action/success:** choose a configured MediaLibrary, enter one safe relative `path`, inspect
  the explanation and Save; new work admitted under that published contract uses the same target
  in Web/API/CLI/manual/scheduled processing without a name-derived extra directory.
- **Failure/recovery:** missing/disabled library, invalid path, stale configuration or preview,
  conflict/capability failure and ambiguous legacy references identify the affected rule. Preserve
  input/old Active, correct or explicitly select the destination, then repreview and Save. Unknown
  publication requires actual readback; affected execution authority is resolved separately.

Newly authored classification results contain `mediaLibraryId` and `path`. `mediaLibraryId` selects
the configured Storage/root and is not a path component; display name and ID never implicitly add
a directory. Remove `library` and redundant editable `category`/`subcategory` destination fields
from the revised rule form. Derive any category display from `path`; conditions, IDs, enabled state,
priority and other rule behavior retain their domain meanings. Keep bounded string/segment-list
compatibility for `path` through one backend normalization and the existing safe-relative rules.

The selected formula is:

```text
MediaLibrary.RootPath + Classification.path + Naming.Directory + Naming.Filename
```

For root `/Media`, legacy `library = Movies`, path `电影/华语`, and naming
`影片目录/影片.mkv`, the revised target is `/Media/电影/华语/影片目录/影片.mkv`, instead of
`/Media/Movies/电影/华语/影片目录/影片.mkv`. Keeping a `Movies` directory requires explicitly
placing it in `path`. Changing only the MediaLibrary display name does not change revised targets.

Carry this contract through domain classification, managed/bootstrap/import/export normalization,
manual configured-rule selection/recovery, common destination composition, formal Planner, exact-
candidate classification/destination/whole-chain previews, API/CLI and existing scheduled consumers.
No alternate Web path calculator or frontend-resolved policy authority is permitted. Classification
and Planner remain pure calculations; actual media changes remain OrganizerExecutor-owned.

#### Legacy configuration and admitted-work compatibility

Convert legacy rules through an explicit checked successor publication: remove `library`, preserve
the existing explicit `path` rather than automatically prepending the old prefix, and explain the
target change. A legacy rule without a resolvable library ID or explicit path needs visible
correction; do not silently guess a library from its name. Support readable legacy documents and
diagnostics without continuing to require the legacy field for newly authored rules. No read,
upgrade startup or cosmetic Save of another object silently republishes legacy destinations.

Do not edit old immutable revisions/digests, stored previews/plans/results, admitted Task/Job pins
or previously organized files. The runtime must distinguish the legacy pinned destination contract
from the revised published one rather than changing what an unchanged historical snapshot means.
Already authorized legacy work can continue only with its original provable plan/authority; if
that contract cannot be reconstructed safely, refuse new mutation and provide native recovery.
Preserve completed/partial/uncertain effects and never replay them during conversion.

Evidence or unattended grants for an old target cannot authorize the revised target. New affected
work needs current exact preview/authorization through existing journeys; unrelated valid authority
and provably unchanged pinned continuation are preserved. B must assess the compatible format/
runtime-version strategy and any necessary additive persistence evolution, restart behavior and
upgrade rehearsal inside RO-3, rather than prescribing a second policy store or broad migration.

### RO-4 — Object-scoped Rules tests with a separate complete-flow check

- **Goal/entry:** from an Add/copy drawer or Edit page, verify the current unsaved object through
  its own `测试与预览` section; use a separately labelled `完整流程检查` entry from Rules Overview
  when checking the combined processing graph.
- **Visible state:** identify the tested object, submitted candidate and sample, test purpose,
  relevant parsed/input fields, condition/reference evidence, result and freshness. Separate the
  current object's conclusion from downstream or complete-flow readiness.
- **Action:** explicitly run the current object's test with only necessary inputs, correct that
  object/sample and rerun; optionally test a type's existing associated rules or deliberately run
  complete-flow analysis. Opening a page or changing fields does not submit a test.
- **Success:** local analysis returns a valid definition, genuine rule match, binding resolution,
  rendered name, classification decision or policy explanation appropriate to the current family.
  Missing unrelated families cannot turn that local result into a failure or a complete-flow pass.
- **Failure:** invalid current fields/references/sample, denied access, stale candidate, unavailable
  analysis or an explicit live Provider failure identifies the relevant stage and corrective action.
  A normal non-match or an inapplicable associated-rule test is not a technical failure.
- **Recovery:** retain editor/sample input and known candidate/evidence state; correct the named
  field/context, refresh changed authority or configure the relevant dependency, then explicitly
  rerun the affected test. Do not require raw revision/token input or replay a test on reconnect.

#### Family-specific scope and inputs

| Editor | Default local test | Conclusion and boundary |
|---|---|---|
| RecognitionType | Validate ID, name, description and enable state against the exact candidate; optionally test its associated RecognitionRules with a sample. | A valid definition does not require a type binding or any downstream policy. No associated rule means `类型定义有效；暂无关联规则可供试识别`. Conditions remain on RecognitionRule; never force the selected type into a fabricated match. |
| RecognitionRule | Parse a synthetic path and evaluate only the current submitted rule using the production condition engine and its actual output type. Source ResourceLibrary context is supplied when relevant to predicates. | Show match/non-match, output type, relevant parsed fields and each bounded condition's expected/actual values and truth, including nested AND/OR/NOT. Missing type binding, Metadata, Naming, Classification or Organize cannot fail this test. Invalid/missing/disabled output type remains a relevant error. |
| Type binding | Check the selected RecognitionType, enabled-binding uniqueness and all four explicit policy references; explain resolved policy identities. | Missing/disabled references or duplicate enabled bindings are relevant failures. No file recognition, Provider search, naming/classification execution or destination probe is required to test the binding itself; C remains C. |
| MetadataPolicy | Validate its own Provider reference, query/type, locale and bounded request/matching configuration and show effective settings. | Offline success proves local configuration only, not credentials/connectivity or an identified movie/show. Credential availability is separate readiness; an explicit live test uses this candidate policy directly with bounded query/path input, without requiring rule recognition or a type binding. |
| NamingPolicy | Apply this candidate policy to a typed movie/TV sample containing the identity, episode and filename-tag fields it consumes. | Show directory/filename, variables and missing/unsafe-value explanations. No recognition rule, type binding, Classification, Organize, Provider or physical source file is required. |
| ClassificationPolicy | Evaluate this candidate's internal rules against relevant typed identity, RecognitionType and source fields. | Show match/fallback/manual/no-match evidence, selected MediaLibrary and safe relative path under RO-3. Referenced destination libraries are necessary dependencies; Naming, Organize, Provider calls and Storage probes are not. |
| OrganizePolicy | Validate and explain its operation, conflict, attachment, duplicate, rollback, cleanup, fallback and explicit high-risk permissions. | Explain intended effects and required capabilities without executing. Actual source/destination capability, conflict or execution readiness is `未检查` until a contextual complete-flow check; absent bindings or destinations cannot fail the policy's own definition check or yield a false execution-ready verdict. |

Use fields appropriate to that test, with business labels and examples rather than one generic form
for every family. RecognitionRule tests use the submitted path/context, not hidden title/type values
that are silently ignored. A synthetic file need not exist. Show the exact tested path and relevant
context; do not silently prepend a ResourceLibrary root or claim its selection changes the path.
Require source context only when needed and never access Storage to fill a synthetic sample.

An associated-rule test on RecognitionType evaluates the bounded set of rules targeting that type
under the exact candidate context, preserves disabled/inapplicable state and explains each rule's
result. It does not resolve downstream policies or claim victory over competing types. A local
single-rule match is labelled accordingly; priority/score/stop/ambiguity across the configured rule
set belongs to complete-flow analysis. Local and complete checks reuse the same Python semantics,
not a browser evaluator or a changed runtime rule-selection algorithm.

#### Result, evidence and complete-flow boundaries

Distinguish valid definition, matched, not matched, configuration/sample invalid, test execution
failed and not applicable; enabled/runtime eligibility is a separate fact. Non-match identifies
the unsatisfied conditions, not just `NO_RULE_MATCH`. Relevant failure copy names the missing
reference or invalid field and the next action instead of raw protocol/exception names. A separate
readiness message may say `该类型尚未配置下游绑定，完整整理流程暂不可用` without changing a valid
RecognitionType or matched RecognitionRule result. Do not claim untested downstream readiness.

Every explicit test uses the submitted unsaved candidate and minimal relevant dependencies from
one exact configuration context. Its evidence binds internally to purpose/object/candidate/sample
and context, is visibly non-Active and becomes stale after relevant edits, sample changes or Active
changes. Candidate/evidence persistence may reuse existing managed storage but must not require a
whole-runtime validation/load or downstream resolver merely to analyze an independent object.
Other families' unsaved drafts cannot enter the test. Permission, field/reference validation,
bounded evidence, redaction and stale-authority checks remain backend-owned and shared by Web/API.

`完整流程检查` reuses existing complete Strategy Test/DryRun/Planner behavior through a native
separate entry. It covers configured rule competition, resulting RecognitionType, its downstream
binding, applicable Metadata/Naming/Classification/Organize behavior and composed plan/target. It
reports missing prerequisites as complete-flow blockers. Default offline analysis calls no Provider;
any supplied identity is explicitly synthetic and cannot be reported as a verified TMDB match.
Live Metadata testing is separately explicit. Necessary destination observations use existing
bounded read-only Storage ports; no complete check grants execution or starts executable work.
Do not relabel a limited recognition check as complete planning or remove the canonical full-chain
Test Policy capability. Unsupported/incomplete stages stay visible rather than fabricating success.

Local pass evidence is not interchangeable with complete-flow or publication evidence. Save still
performs full successor-document validation, applicable exact-revision checks and atomic activation;
the changed test boundary cannot activate a broken declared graph. Existing public Strategy Test,
DryRun and execution/authority semantics remain compatible. Existing historical evidence stays
readable with its original scope; never reinterpret an old strategy result as a new object-only
result, alter stored pins or let a local test authorize media mutation.

### RO-5 — Usable long-name paths and toolbars on both library pages

- **Goal/entry:** browse `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files`, including valid
  directory deep links, with long names or many path segments while keeping navigation and controls
  usable in list and grid views.
- **Visible state:** exact current-directory context, bounded breadcrumbs, complete-name access,
  normal control availability, live entries and existing loading/read-error state.
- **Action:** inspect a full name by pointer or keyboard focus, navigate to root/ancestors, refresh,
  and switch list/grid through visible, reachable controls.
- **Success:** long names do not push controls over entries or outside the pane; the list starts
  below the actual toolbar, and every breadcrumb still navigates to its exact original path.
- **Failure:** an unavailable/denied/stale directory remains an actionable read failure with its
  recovery controls visible. Visual shortening cannot make two distinct paths share an identity
  or turn failed reads into an empty successful directory.
- **Recovery:** reveal the complete name, reach an ancestor/root, or deliberately refresh the
  bounded read through the existing journey. Preserve correct path/selection reconciliation and
  existing per-item recovery; inspecting names, resizing or changing view starts no media work.

The toolbar must accommodate its actual contents. At normal desktop width, preserve the existing
path-left/control-right composition and short-name visual density. Let the path region shrink while
controls retain complete labels and usable targets. When the pane becomes too narrow for one row,
allow rows to reflow and reserve their actual height; a fixed-height wrapper must not conceal or
overlap a wrapped row. Keep entries scrolling in their existing bounded viewport with the toolbar
and footer usable outside that scroll.

Keep breadcrumbs on one line within their own bounded region. Visually shorten an overlong single
segment; provide local horizontal access when the combined path still exceeds the available width,
with the current segment visible on navigation and all ancestors reachable. Path overflow must not
move the control group or introduce page-wide horizontal scrolling. Full exact names must be
available on hover and keyboard focus, with meaningful accessible names and preserved boundary
whitespace disambiguation. Visual elision never changes raw names, route state, API paths or command
intent; do not trim, normalize, rename or substitute a displayed abbreviation for Storage identity.

Deliver the same behavior on both pages through consistent Files-workspace presentation, scoped
so shared styles do not change Rules or unrelated page composition. Preserve root/ancestor links,
refresh semantics, control disabled states, create actions, view toggles, tree/selection, paging,
dialogs and existing ResourceLibrary Organize entry. This outcome adds no backend operation,
Storage mutation, MediaLibrary Organize entry or new global navigation design.

### RO-6 — Bounded ResourceLibrary folder and mixed-selection organization

- **Goal/entry:** select one or more folders, ordinary files, or a mixture on
  `/ui-v2/resourcelib/files`; use a folder's explicit Organize menu action or the batch organizing
  action. The Operations `新建整理任务` handoff uses this same journey and retains its return context.
- **Visible state:** exact selected relative scopes, recursive-discovery progress, discovered media,
  exclusions/unstable items/read failures and whether discovery is complete; then the existing
  per-item choices, exact source/target/attachments, plan findings, conflicts and durable outcomes.
- **Action:** deliberately start bounded discovery, pause/continue/cancel at safe boundaries,
  inspect eligible items and explanations, generate exact Preview, select the reviewed items and
  explicitly confirm execution through the existing native Web flow.
- **Success:** every selected eligible source is admitted at most once; the reviewed items complete
  through the normal policy/Planner/Executor chain, retain independent results and recovery, and
  return to the correct live ResourceLibrary directory or linked Operations run.
- **Failure:** empty scope, all-excluded content, unstable files, denied/inaccessible subtrees,
  missing/changed sources, invalid scope, exceeded bounds, missing Worker/pin, policy/Metadata
  blockers, conflicts and partial/uncertain effects remain distinguishable and actionable.
- **Recovery:** retain selection, admitted context and durable findings; narrow oversized scope,
  correct access/configuration or continue supported paused discovery. If discovery is interrupted
  and continuation cannot be proved safe, explain the durable state and zero media effects, settle
  the old unfrozen attempt, then offer explicit new discovery. Waiting stability is re-observed only
  after the required interval. Completed and uncertain media effects are never replayed.

#### Selection, discovery and filtering

The Web sends the selected ResourceLibrary ID and exact ResourceLibrary-relative paths. Python
resolves actual entry types, the enabled library/Storage binding, permissions and all limits.
Malformed or unsafe submitted scope is rejected before durable admission; it cannot acquire a
partial valid scope by silently dropping the invalid input.
Directory selection means recursive discovery by default; opening a folder, selecting a checkbox,
refreshing or switching views still performs no recursive discovery or organizing work. List and
grid expose the same supported actions, with backend-authoritative availability and useful reasons.

Normalize safe scope structure without trimming names or changing Storage identity. Deduplicate
repeated paths and overlaps between selected parents, descendants and explicitly selected files;
each ordinary source appears at most once in the resulting intent. Use Storage paging and confined
list/stat observations, reject escapes and unsafe provider entries, never follow symbolic links,
and do not let discovery leave the selected subtree or ResourceLibrary root.

Apply the pinned ResourceLibrary media extensions, include/exclude rules, configured depth and
file stability policy. Conditions and downstream Parser/Recognition retain the original
ResourceLibrary-relative path and parent directories; selecting a folder must not rebase away a
path component such as `电影` or `SP`. Temporary/download files and unsupported/non-media entries
receive bounded exclusion explanations rather than becoming independent primary-media items.
Existing subtitle/NFO/image/trailer attachment and main-versus-extra policy semantics remain intact;
folder discovery does not independently execute sidecars or invent a new attachment matcher.

Minimum age and modification threshold do not prove a required stable-size duration. When repeated
observations are required, use bounded durable observations of the actual Storage source under
this discovery context and expose waiting/not-yet-proven stability with a safe next action. Do not
require FileIndex membership, use an index row as source/stability authority, fabricate elapsed
stability, or add content reads/full-media hashing just to expand a folder.

#### Bounds and truthful partial discovery

Retain at most 100 primary media per organizing intent for this delivery. Also enforce backend
bounds for submitted scopes, visited entries/directories, depth, paging and work duration; B must
specify the concrete compatible budgets in the active Task. A candidate beyond the item bound,
exhausted traversal budget, repeated/cyclic cursor or safety-depth truncation cannot silently produce
an executable first-N subset or claim complete discovery. Show the limit and a native action to
select a smaller scope; automatic splitting into arbitrarily many intents is not selected.
Configured depth exclusions are explained as policy exclusions, distinct from exhausted safety budgets.

An ordinary item/subtree read failure preserves independent findings for unaffected sources.
Show the unavailable scope and incomplete-discovery state; known eligible sources may proceed only
as an explicitly reviewed bounded subset, never as proof the entire folder was processed. An empty
folder, all-excluded scope, unstable-only scope and unreadable scope remain different outcomes.
Unknown totals stay unknown until discovery establishes them. Exclusions and errors do not count
as successfully organized media and their bounded projection cannot hide an incomplete traversal.

#### Background ownership, exact pins and Preview

Long discovery uses existing durable Task/Job/Worker and Operations readback/control boundaries.
HTTP returns durable admission promptly rather than recursively enumerating or calling Providers
inside a long request. Show missing/stale/unsupported Worker and unavailable pinned-context reasons
with a meaningful next action; API process health alone never implies discovery can run. No new
queue, Scheduler, supervisor or parallel Task lifecycle is introduced.

Capture the exact immutable Active snapshot at admission. Discovery, filtering, stability,
source-identity creation and later manual analysis use that admitted pin, even after a new Active
is published. An unavailable/corrupt/unpublished pin fails closed without falling back to current
Active, Draft, JSON or FileIndex. Any historical-pin handoff must prove the durable admission and
published revision; the browser cannot choose an arbitrary historical configuration as authority.

Persist admitted scope/pin, durable findings, observations, state and ownership evidence for
truthful readback and normal cooperative pause/continue/cancel. An interrupted unfrozen discovery
may become an actionable stopped/failed attempt instead of resuming the precise traversal cursor.
Before explicit new discovery, settle or refuse continuation of the old attempt under its ownership
fence; preserve its history, known findings and material refusal. New discovery is a distinct,
visible attempt with its own declared scope/pin and bounds, never an in-place budget reset or a
rewrite of frozen work. A current owner cannot publish over cancelled, superseded or frozen work.

Unknown admission must be read back only when its original actor/binding/pin can be proved. If that
proof is unavailable, show unresolved admission and native Operations inspection/resolution, retain
request context and block guessed readback or automatic submission. A later Active/root must not
be selected as the lost request. Ordinary equivalent open scopes still reconcile atomically under
the same actor/library/Storage/pin independently of recent-list order or window. Cooperative
cancellation preserves durable findings, creates no execution permission and does not promise
immediate interruption of a provider call. Read-only refresh never starts replacement discovery.

Once discovery is finalized, freeze the exact source list and Storage-built source identities in
the existing manual organizing journey. A completed walk is not an atomic provider snapshot;
later directory changes cannot enlarge the frozen source list. The production
Recognition/TypePolicy/Metadata/Naming/
Classification/Organize/Planner behavior remains authoritative, including RO-3's applicable target
contract and C retaining C when reusing A policies. Discovery itself performs only metadata reads
and no Provider calls; later explicit analysis may read bounded NFO/attachments or call the
configured MetadataProvider as the existing pipeline requires. All analysis remains zero mutation.

Execute only the explicitly selected exact Preview items, under current permissions, normal
capability/conflict/source revalidation, locks/fences and separate one-shot execution intent.
Folder selection does not authorize moving a directory wholesale, silently overwriting targets,
deleting excluded files or enabling source cleanup. New primary files after the source list was
frozen are not automatically included; attachments remain bound to the exact reviewed Preview.
Missing/changed sources stop the affected item. Recovery that discovers new sources creates
explicit successor work and never rewrites a frozen list, historical pin, completed result or
consumed execution authority. FileIndex synchronization remains post-result and its failure cannot
trigger another media mutation.

#### Required RO-6 implementation boundary — smaller first delivery

Keep one journey: selection → bounded background discovery → reviewed frozen primary manifest →
existing manual intent/Preview → separately confirmed execution. Reuse the resident Worker,
SQLite discovery record, pure filters and attachment association. Add no queue, Scheduler,
supervisor, general workflow framework, FileIndex admission dependency or execution pipeline.

1. **Ordinary admission and bounded work.** Canonicalize exact scopes and atomically reconcile
   equivalent open actor/library/Storage/pin-bound work. Count directories, pages, entries and active
   time by their distinct meanings. Keep Storage calls outside write transactions and preserve
   confinement, source deduplication, durable material refusals and the 100-primary gate.
2. **Actual configured policy.** Existing native managed Web/API Save, validation, publication and
   production loading must agree on supported include/exclude/depth/stability policy. Every selection
   entrance uses the admitted pin and root-relative rules. Associated Trailer videos remain
   attachments rather than independent primaries, including across pages; keep original names/path
   context and use the existing matcher. Discovery reads no content and calls no MetadataProvider.
3. **Genuine stability without a busy loop.** Retain actual bounded source observations. Do not admit
   a file before its configured age/mtime/size interval is proven. Waiting work cannot be immediately
   reclaimed repeatedly, consume traversal budgets while idle or starve other resident commands.
   Bounded re-observation when eligible is required; a precise persistent per-page cursor, dedicated
   scheduling framework or guarantee of uninterrupted observation across every restart is not.
   If observations are lost or invalid, wait again or stop with an explicit safe next action.
4. **Simple controls and interruption recovery.** Support normal acknowledged Pause/Continue and
   cancellation at safe boundaries. On crash, incompatible old discovery or a control race, keep
   durable evidence and prevent stale-owner publication/Finalize. Safely stopping the unfrozen attempt
   and offering explicit new discovery is acceptable when continuation cannot be proved. Retaining
   every unpublished observation through arbitrary races is not required. A stopped/incomplete
   attempt cannot become complete or freeze a materially refused prefix. Exact atomic one-intent
   Finalize and all media execution/checkpoint/uncertainty safety remain unchanged.
5. **Truthful shared state.** API/Web agree on phase, completeness, independent item errors,
   command-specific readiness, supported exact names/paths and permitted next actions. Legal long
   names cannot strand the batch or make list/detail unreadable. File/subtree read failures preserve
   unaffected findings and require explicit known-subset review. Resolve a lost response only with
   proved original identity; otherwise offer native inspection, without guessing another pin/root
   or automatically resubmitting. No raw token handling or redundant ordinary confirmation is added.

Existing history, frozen manifests, file-only intents/Previews/results/pins and execution authority
remain readable and unchanged. If persistence changes, prove actual old-schema migration/reopen,
including a representative interrupted discovery and frozen/file-only work. Unsupported unfinished
legacy discovery may stop with a native explanation and explicit new-discovery action; automatic
repair/resumption of every duplicate or historical cursor is deferred. Never delete/guess-merge
history, silently repin old work or grant new execution rights. Keep existing useful code rather
than rewrite it merely to match a preferred state-machine shape. Specific fields, helper count and
checkpoint granularity are implementation choices; optional proof/P2 cleanup cannot block acceptance.

RO-1 through RO-6 define the complete activated boundary. Other existing-page contents remain
unselected and deferred; B must not invent additional outcomes or field/operation-sized Task
ladders. Required Outcomes are not pre-created implementation Tasks.

## Required Surfaces

- ResourceLibrary Files and MediaLibrary Files: existing entry menus, selection actions, dialogs,
  text editor, live refresh/tree/selection, native operation failure/recovery, and usable long-name
  breadcrumbs/toolbars in list/grid, including production-built Docker-served presentation.
- Their typed authenticated APIs and shared application/domain/Storage/OrganizerExecutor behavior;
  both library kinds and existing API compatibility must use the same rules.
- Existing Task/Worker/Operations: admission, pinned scope, ownership, durable per-item transfer/
  Delete checkpoints and readback/continuation affected by optional fingerprints.
- ResourceLibrary folder/mixed-selection actions and scoped authenticated admission/readback APIs;
  existing Task/Worker/Operations discovery progress, normal pause/continue/cancel, interrupted/
  unresolved admission inspection and explicit new discovery, manual choices, exact Preview/
  execution, per-item outcomes/recovery and Files/task-center return context.
  MediaLibrary receives no Organize entry or source authority from this outcome.
- Existing provider adapters and bounded fake/local-service verification. No new provider or
  unrelated-page redesign is selected.
- Rules workspace: all eight navigation sections, full-width inventories, Add/copy drawers,
  existing Edit routes, purpose-built forms, exact previews and native publication recovery.
- Shared V2 shell/header and control styling only as necessary for Rules composition and scoped
  Files-workspace toolbar recovery; preserve Storage, Settings, Operations and Automation routes
  and the existing ResourceLibrary/MediaLibrary commands.
- Shared classification/configuration/Planner/API/CLI and existing scheduled/pinned consumers,
  including legacy document/preview/plan/result readback and affected authority recovery.
- Rules family-specific test controls/results and Overview complete-flow entry; shared typed API,
  backend candidate/analysis/evidence behavior, actionable dependency guidance and historical
  complete Strategy Test/DryRun compatibility. Tests do not become a second publication authority.

B determines coherent implementation units and Task Test Levels within this checkpointed ACTIVE
Contract; A does not pre-plan a page-by-page implementation ladder or introduce simultaneous
active Tasks here.

## Safety Invariants and UX Constraints

All permanent AGENTS.md, product-experience and applicable stable requirement invariants remain
mandatory. Scope is not permission to weaken RBAC, explicit mutation intent, no silent overwrite/
delete, Storage confinement, immutable runtime snapshots, zero-mutation analysis, per-item durable
outcomes/recovery, no uncertain-effect replay or OrganizerExecutor-only Storage mutation.

Rules reads/navigation/search/refresh remain zero-side-effect. Save uses backend-authoritative
validation and exact checked atomic activation without an extra ordinary Validate/Activate flow;
Save never starts media work. Tests/previews stay bounded, secret-free and zero Storage mutation;
only explicit live Metadata testing may call its configured Provider. RecognitionType C remains C
when reusing A Naming/Classification policies. Style, display labels and list ordering do not alter
condition/priority resolution, permissions, references, conflict policy or execution authority.
RO-4 local tests perform no Provider or media Storage I/O and cannot publish/activate configuration,
create executable Task/Job work or grant mutation authority. Only explicitly requested live
Metadata testing or bounded complete-flow read checks use the corresponding external ports.
Evidence purpose is preserved: local validity cannot substitute for whole-graph publication,
complete planning, capability checks or execution permission. A rule match must come from actual
condition evaluation, not forced RecognitionType input.

The optional-fingerprint decision applies only to the selected ordinary direct-file journey. Keep
media Organize Preview/execution, RecognitionType/policy identity, unattended grants, configuration
publication and other exact-snapshot/ownership checks intact. Root deletion, unsupported links,
known stale scope and unsupported operations remain refused. No recurring operator "unsafe mode"
switch, CLI workaround, raw-evidence handling or redundant per-entry confirmation is added merely
because a provider lacks fingerprints.

Historical completed work is immutable. Never rewrite old results/pins or infer new deletion
authority for an old partial/uncertain operation from this planning decision. Existing stored evidence
must remain readable and recoverable under an explicit, attributable rule/context; B must account for
any required compatible evidence/persistence evolution and restart behavior rather than silently
downgrading old strong evidence or automatically replaying previously refused destructive steps.

RO-3 is an explicitly selected destination change, separate from RO-1's optional-fingerprint rule.
It never substitutes current configuration for historical pins or silently extends an old grant to
a new destination. Known path conflicts, unsafe relative components and missing/disabled libraries
remain refused; no name-derived routing, silent overwrite or automatic relocation is introduced.

RO-5 changes presentation only. Exact names/paths, whitespace disambiguation, backend authority,
library-kind isolation and read/refresh behavior remain binding. Truncation, focus, horizontal path
scrolling and responsive reflow must not submit commands, grant authority or automatically replay
work. Full-name disclosure remains confined to the operator's existing authorized path context.

RO-6 changes selected organizing-source discovery, not execution authority. Metadata-only folder
discovery and all analysis remain zero media mutation; directory selection never supplies deletion,
overwrite or unattended authority. Exact source identities, immutable admitted snapshots, live
permission/capability gates, OrganizerExecutor-only mutation and per-item non-replay remain binding.
RO-1's absent-provider-fingerprint rule for direct maintenance cannot substitute weaker source
evidence for a media Preview or execution. Discovery/stability cannot acquire FileIndex authority,
and neither bounds nor recoveries may silently extend the reviewed source/item set.

### Rules visual references and preservation

`整理规则需修复.png` marks the shared header/navigation repair region in the Recognition Types
reference. Its black rectangle is an annotation, not product chrome. The original six images define
the shared visual language and family-specific forms; they must be assessed together. The reference
desktop viewport is 1536 × 1024. Match composition, alignment, hierarchy, control placement and form
density; pixel-identical example data and permanent open reference editors are not acceptance goals.
Overview/Organize follow the same language without inventing missing reference data or behavior.

| Reference under `docs/pics/` | SHA-256 at this planning revision |
|---|---|
| `整理规则需修复.png` | `d85abb7e2aa5f67f6d1346d35983416eb47e55ae4b5617d07e81df2ba961c3c2` |
| `识别类型.png` | `24a6058da017af381fa095304607c34d286d11e8e45b12ff00672d4711c16101` |
| `识别规则.png` | `28e6337b5f1b2671d79f8dfd41ddd7081a94bed384975ec67389c05f014635ef` |
| `策略绑定.png` | `b959159e67e51abb3b5ea96645feedcaee8e4b459ae405086c200f7fc0c236f3` |
| `元数据类型.png` | `5401aa47aa3f43b7901ecfbbdc9f3b6dcd8bb59db25f58350fcbd4d9b79159a3` |
| `命名规则.png` | `93dbd8071adb11fed1bfcbf75cc7815c637d19d8aacdc828ef1c2e2888b0a98f` |
| `分类规则.png` | `befb3c60dc3abf39b0c56bf837ab26d182fa5bc58434a4a01aa57d0e3d262e03` |

Preserve these originals, including pre-existing untracked `整理规则需修复.png`, `媒体库.png` and
the two Automation PNGs. Do not stage, edit or recompress user assets as part of this planning
checkpoint. Missing references are reported, not replaced with generated approximations.

## Explicitly Deferred

- Slice 43 implementation and its outstanding fix loop while the development hold is in effect.
- Implementation before this ACTIVE Contract is checkpointed and B creates an active Task inside it.
- Features, pages or redesigns outside the activated RO-1 through RO-6 boundary.
- General browser Upload/Download, binary/media editing, unbounded work, cross-library-kind direct
  transfers, transfer Replace, new HardLink/SoftLink UI, universal rollback and new Storage providers.
- Provider-generation/conditional-operation redesign, full-media hashing to prove Rename/Delete
  identity, and universal detection of externally concurrent metadata-indistinguishable replacement.
- Cross-family/global Rules search, a new shell/navigation system, global unrelated-page styling,
  permanent auto-open rule editors, rule-engine redesign, new Metadata Providers, Rules media
  execution, bulk rule import/diff/rollback or V1 retirement.
- Automatic relocation of previously organized media, in-place historical configuration/result/pin
  rewriting, and automatic replay/regrant/republication during classification conversion.
- General long-text redesign outside the two Files workspaces, metadata-score/manual-review
  redesign, and changing the user's live Docker deployment for this amendment.
- MediaLibrary organization, a new whole-library/root Organize entry, automatic large-folder
  multi-intent splitting, increasing the existing 100-primary-media intent bound, a second
  discovery/processing engine, and source cleanup merely because a folder was selected.
- Explicit user-approved RO-6 recovery reduction on 2026-10-11: guaranteed automatic recovery of a
  lost discovery response through simultaneous activation/root changes; automatic repair/resumption
  of every legacy duplicate/interrupted discovery; precise cursor/unpublished-work continuity through
  arbitrary crash/control/version combinations. Safe stopping, original-context inspection and
  deliberate new discovery are required now. This local deferral does not remove stable product
  recovery targets, weaken media mutation safety or defer the confirmed ordinary-function defects.

## Slice Acceptance Criteria

The selected RO-1 is accepted only when:

1. Both native library pages and APIs complete the operations above under backend authority; an
   OpenList/SMB-like provider lacking fingerprints can Rename files/directories, confirm and Delete
   bounded files/directories, and finish the source-removal stage of a verified cross-Storage Move.
   Provider capability/permission failures remain distinct from absent fingerprint.
   Each applicable operation must complete from the MediaLibrary page and media-scoped API as well
   as ResourceLibrary Files; shared backend success or resource-scoped coverage alone is insufficient.
2. Observable file size/time/type changes and present-fingerprint changes/disappearance refuse
   stale operations; changed Delete scope and known non-empty final directories remain protected.
   Missing fingerprint alone is not a refusal. Deterministic identical-metadata/no-fingerprint
   scenarios document the accepted limitation instead of requiring invented exact identity.
3. Rename/Delete evidence issuance, admission, confirmation and Executor checks perform zero file
   content reads and zero duplicate FULL Hash. Actual transfer verification and bounded text Save
   keep their respective digest semantics.
4. Conflicts never intentionally overwrite existing entries without applicable explicit intent;
   roots, escape/alias/self/descendant paths, unsupported links/types and denied/read-only operations
   remain refused. Capability failure never silently changes the requested operation.
5. Delete and transfer batches preserve per-item progress/effects, partial/uncertain distinctions,
   pause/cancel semantics and useful next actions. No refresh/reconnect/restart/unknown response
   automatically replays completed or uncertain mutations, or claims ownership from name/size alone.
6. Valid existing evidence, old historical results and exact admitted snapshots remain readable;
   stored/in-flight work cannot silently gain destructive permission. Recovery revalidates actual
   effect/checkpoint authority rather than substituting current configuration or weaker old evidence.
7. Web success updates exact list/tree/selection/path context; refusals retain correctable input;
   unknown creations/saves/native move stages can be inspected through native readback/recovery.
8. Local, SMB/OpenList-like and S3/R2 file/prefix semantics are tested without claiming universal
   conditional mutation. Existing Organize, configuration, Storage binding, Task ownership and
   library-kind isolation behavior remains intact. Final CURRENT reconciliation states the delivered
   observable-metadata rule and its actual limitations, rather than marking TARGET as already shipped.

The selected RO-2 is accepted only when:

9. At the reference desktop viewport, the shared title/search/account row, description and eight
   icon/name/description navigation cards follow the reference hierarchy and alignment; active
   state and family deep-link/Back/Forward behavior are consistent. A Rules keyword input is
   functional rather than an unrelated read-only Files field, and search/navigation cause no writes.
10. Every inventory separates its title/description, left Add and right search/filter row, and
    full-width table. Header/local keyword state agrees. Empty, filtered-empty, partial, denied and
    failed reads remain truthful and recoverable. Selecting a row/tab never opens an editor.
11. Add/copy and full-page Edit expose the purpose-built sections and real supported fields above,
    with consistent labels, required/error/hint treatment, multiline descriptions, applicable
    accessible switches, reference density and visible right-aligned Cancel/Save. Narrow/keyboard
    use and unsaved/stale/failed/unknown publication recovery remain complete.
12. Browser evidence covers all eight navigation sections and each family's applicable inventory,
    create/copy/Edit and test/preview states. Layout is compared to the six originals and annotated
    header region; structural mismatches are blockers, while minor pixel variance alone is not.
    Shared header/CSS changes preserve existing non-Rules pages and RO-1 dialogs/actions.

The selected RO-3 is accepted only when:

13. Newly authored destinations need only `mediaLibraryId` and safe `path`; the rule form has no
    `library` or redundant editable category/subcategory output. The selected root, classification
    path and naming contributions produce the canonical target in every revised consumer. Library
    display-name changes do not change it; no match, invalid path and unresolved/disabled library
    remain explicit failures rather than default routing.
14. Web/API/CLI previews, formal Planner, manual rule decisions and existing scheduled processing
    agree on the revised path, preserve C identity, and prove zero Storage mutation in analysis.
    Composed target conflicts, capabilities and execution permissions are still enforced.
15. A legacy rule converts by explicit successor publication with a visible old/new target; its
    path is preserved without automatically inserting the old prefix. Legacy imports/bootstrap,
    exports/readback and ambiguous/missing fields have compatible, actionable handling. Startup,
    reads and unrelated-object Saves cannot silently switch an old destination contract.
16. Existing immutable snapshots/digests, historical plans/previews/results, admitted pins and
    per-item effects remain intact and readable across restart/upgrade. Legacy pinned execution
    either retains its provable original semantics or stops with native recovery and zero new
    mutation. Old target evidence/grants never authorize revised destinations; current preview/
    authority recovery works without replaying completed or uncertain effects.

The selected RO-4 is accepted only when:

17. Add/copy/Edit offer the family-specific tests above against the exact submitted unsaved object.
    A valid unbound RecognitionType passes its definition check; no associated rules is explicitly
    inapplicable. A genuine associated-rule match outputs that type without forcing it or requiring
    downstream policies. Disabled candidates remain visibly excluded from runtime matching.
18. A RecognitionRule requiring path `电影` matches `电影/Example.Movie.2024.mkv` and does not
    match `Example.Movie.2024.mkv`, with per-condition/group expected/actual/truth evidence. Empty
    type bindings and downstream families do not fail the matched local test. Changing the current
    unsaved rule changes the tested result; invalid conditions/output types remain relevant errors.
19. Binding, Metadata, Naming, Classification and Organize tests enforce only their relevant
    dependencies and yield their documented results. Offline Metadata does not require live
    credentials or claim Provider success; explicit live testing honors this policy directly.
    No unrelated invalid or missing policy can break an independent local test. All local tests
    prove zero Provider and Storage calls when offline, not merely zero mutations.
20. Results distinguish non-match, invalid configuration/input, technical failure and not applicable;
    readiness warnings remain separate. Relevant missing/stale/denied/unavailable errors offer
    native correction with input retained. Candidate/sample/context changes mark old results stale,
    and reads/refresh/reconnect do not repeat tests or publish candidates.
21. The native separately labelled complete-flow entry retains actual rule competition, policy
    resolution and complete-plan semantics with truthful missing-stage/graph blockers and explicit
    synthetic/live Metadata status. Web/API agree; C using A policies remains C. Local single-rule
    success cannot imply it wins configured competition or that complete organizing is ready.
22. Local evidence cannot satisfy required complete-flow/publication/execution gates. A local pass
    followed by invalid successor Save preserves prior Active and input; denied/stale/unknown
    publication recovery stays intact. Existing full Strategy Test/DryRun, historical evidence and
    pinned work keep their scope and authority across compatible readback/restart; zero mutation,
    no executable work and no automatic replay hold for every analysis path.

The selected RO-5 is accepted only when:

23. Both routes keep root/ancestor navigation, refresh, create controls and list/grid toggles visible
    and usable with short names, long Chinese/English/mixed names, unbroken names and multilevel
    paths. Toolbar rows stay inside the toolbar; entries and error/recovery states start below it
    without overlap or clipping. Narrow pane reflow does not introduce page-wide horizontal overflow.
24. Individual elision and local breadcrumb scrolling retain complete-name access by pointer and
    keyboard, visible current-directory context and reachable ancestors. Boundary whitespace remains
    distinguishable. Navigation, refresh and existing commands use the exact raw path, including
    distinct names with the same visible prefix; no trimmed or abbreviated sibling is addressed.
25. List/grid, directory changes, root return, refresh success and read-error recovery preserve their
    existing state and behavior. Toolbar/footer and bounded entry scrolling remain usable. Files
    dialogs/Organize and unrelated Rules/shared-shell pages have no affected-layout regressions.
26. Real-browser geometry/interaction evidence covers both routes and the long-name/narrow-pane
    cases, and confirms the corrected production-built assets through isolated Docker HTTP serving.
    DOM-only rendering or a source-CSS change alone cannot prove the reported overlap is resolved.

The selected RO-6 is accepted only when:

27. ResourceLibrary list/grid folder menus and the batch action complete folder-only, file-only,
    multiple-folder and mixed selections through native discovery, exact Preview and confirmed
    execution. Parent/child/explicit-file overlaps produce one intent item per ordinary source.
    Operations creation/return and original-directory context work without CLI or raw-token steps;
    MediaLibrary has no new Organize source/entry.
28. Pinned filtering, configured depth and genuine stability observations exclude temporary,
    unsupported and actively written files with bounded explanations. Original paths/parents
    reach Recognition unchanged, C remains C with A policies, and attachments retain existing
    association/suffix/conflict semantics. No FileIndex lookup admits sources or proves stability.
29. Pagination, source confinement and traversal budgets are enforced on the backend. Exactly 100
    primary items are supported; 101, safety-depth/entry/time limits and cyclic cursors cannot yield
    a silent executable prefix. Empty/all-excluded/unstable/unreadable scopes and partial discovery
    remain distinct; unaffected known sources have independent reviewed outcomes and safe recovery.
30. Long discovery is durably observable with truthful Worker waiting, progress and normal
    cooperative pause/continue/cancel. Equivalent open scopes reconcile atomically. Interruption
    either safely continues or stops with preserved durable findings/reason and an explicit
    new-discovery action after fencing/settling the old attempt; precise cursor resumption is not
    required. Unknown admission recovers only a proved original actor/binding/pin, otherwise remains
    unresolved with native inspection and no guessed association or automatic submission. New
    activation never repins admitted work; discovery/reads never grant execution authority.
31. Frozen source lists and exact Preview identities retain normal policy, permission, capability,
    conflict, source and ownership gates. Added files are not implicitly executed; changed/missing
    files stop their own item. Corrupt/unavailable pins fail closed; successor discovery/recovery
    never rewrites old plans/results or replays completed/uncertain effects.
32. Discovery uses metadata-only Storage observations and zero Provider calls; analysis/Preview
    perform zero media mutation. Only OrganizerExecutor executes explicitly authorized reviewed
    items. Overwrite/source removal/cleanup remain independently permitted, no silent operation
    fallback occurs, and FileIndex sync failure cannot replay media work. Web/API agree throughout.

No additional-page acceptance is required outside RO-1 through RO-6. Activation does not mark any
Required Outcome complete, and these acceptance groups are not a predetermined Task list.

## Final Validation Expectations

RO-1 and RO-3 affect Storage mutation boundaries, core planning, immutable configuration, Worker
recovery and compatibility: the selected Slice final gate is T4. RO-2 normally requires T3 Web/
shared-shell integration evidence; B assigns Task levels from actual risk within this Contract
rather than assuming all presentation changes are local CSS. Activation does not stand in for
product validation or create an implementation Task.
RO-4 needs Application/API/Web integration evidence; changes touching candidate validation,
publication evidence or historical compatibility receive T4 validation at those authority
boundaries. A local test split is not permission to reduce the Slice's final T4 gate.
RO-6 affects core source admission, immutable pins, Worker ownership, persistence and execution
handoff: its affected authority boundaries require T4 validation. Activation assigns no formal
Task Difficulty or Task list; B plans coherent units and assigns their levels within this Contract.

Require focused domain/application/Executor/API tests with provider-neutral absent/present/changing
fingerprint fakes; Local temporary directories; bounded OpenList/SMB/S3 semantics through fakes/local
servers; Web interaction and real-Python browser integration on both library kinds; restart,
ownership, historical evidence and partial/unknown effect recovery; applicable full regression,
lint/type/build, packaging and migration gates. Include no-content-read spies, conflict/denied/path/
scope failures, unchanged and changed observations, OpenList multi-stage Move and source-removal
success/partial cases. Production media/services are not test prerequisites. Unavailable isolated
real-service evidence must be reported honestly, never inferred from a fake.

RO-1 evidence must map the affected operation cases to both native routes and their separately
scoped APIs, including absent/present/changing fingerprint, no-content-read Rename/Delete,
confirmed directory/batch Delete, cross-Storage source removal, conflict/denied/root refusal,
partial/unknown outcomes, retained input and refreshed tree/selection/return context. Test
MediaLibrary Task/Worker readback and continuation explicitly, and preserve equal-ID cross-kind
evidence rejection. Shared tests may reuse fixtures, but must demonstrate both library-kind
bindings; marking MediaLibrary merely "unaffected" or deferred does not meet RO-1 acceptance.

For RO-2, require automated navigation/search/drawer/form/publication-recovery checks, Web build/
type/lint gates, real-Python browser journeys and saved visual-review evidence at 1536 × 1024 and
a representative narrow viewport. Inspect each rule family with controlled real test data, not
production or hard-coded image fixtures. Cover retained input, stale/denied/failed/unknown Save,
non-Active/stale preview explanations and keyboard/focus/scroll behavior. Include shared-shell/
Files/MediaLibrary/Storage/Settings/Operations/existing Automation regressions where affected.

For RO-3, require classification/normalization/common-composition/Planner/API/CLI and scheduled
consumer tests; safe/unsafe/nested paths, library rename and invalid references, destination
conflicts, zero-mutation spies and C-to-A-policy regression; legacy bootstrap/import/export and
explicit checked conversion; exact snapshots/preview/grants and pending/completed/partial/uncertain
work across restart. If persistence or compatibility format changes, run applicable upgrade/
migration rehearsal preserving real historical pins/results/evidence. A fake newer-format document
alone cannot prove legacy compatibility. Frozen Slice 43 code is not a dependency or test baseline.

For RO-4, require production-engine object tests and authenticated API/native Web journeys for
every family: unbound/new/disabled types, absent associated rules, genuine match/non-match with
nested groups, current unsaved candidates, missing downstream graph, unrelated invalid objects,
invalid relevant references/inputs, local Metadata without secrets, and explicit live success/
failure through fake Providers. Test rule competition/ambiguity/stop behavior separately from
local results, type C policy reuse, synthetic identity labelling and complete-flow blockers.
Use Provider/Storage spies to prove no calls from local offline tests, and prove no mutation/work/
activation/authority from any test. Verify freshness/input retention, stale/denied/unavailable
responses, separate readiness and unknown-result recovery, native complete-plan entry, local-pass/
failed-Save isolation, evidence-purpose separation and old complete-test readback across restart.
Affected publication/runtime/Strategy Test/DryRun regressions and compatibility/migration gates
remain required; no real credentials, production service or production media is needed.

For RO-5, require automated real-browser layout and interaction checks on both native routes in
list/grid at 1536 × 1024, 1024 × 900, 760 × 900 and 390 × 844, including actual pane width after the
existing shell/tree layout. Cover short names, long Chinese/English/mixed and unbroken names,
multilevel paths, shared visible prefixes and leading/trailing whitespace. Check bounding geometry
for controls within toolbar, entry/error content below toolbar, and no page-wide horizontal overflow;
then exercise complete-name hover/focus, keyboard ancestor navigation, current-segment visibility,
root return, refresh and read-error recovery. Preserve row-viewport scrolling, footer, disabled-state
semantics and exact route/API paths. Use controlled synthetic entries and read-only browsing fixtures,
not production-media mutations or user-private paths. Include affected shared-style regressions and
Web lint/type/build gates. Validate built assets via an isolated production Docker instance and
record served-artifact/browser evidence; unavailable isolated evidence must be reported explicitly.
B assigns the coherent Task's Test Level within this Contract; RO-5 does not reduce the final T4 gate.

For RO-6, require application/authenticated API and real-Python native browser journeys for folder-
only, file-only, multiple-folder and mixed selections in list/grid, plus Operations creation/return.
Cover duplicate/overlapping parents/children/files, original recognition path context, subtitles/NFO
and extras, exact whitespace names, empty/all-excluded/unstable scopes, independent subtree/read
failures, unsafe/out-of-root provider entries and links. Exercise paging, 100/101 primary items,
directory/entry/depth/time bounds, cyclic cursors and non-truncated completeness reporting.
Use live-observation fakes and controlled clocks to prove age/mtime alone cannot satisfy a required
stable-size duration; no FileIndex row is required or trusted for source admission/stability.

Verify metadata-only/no-Provider discovery and zero-mutation analysis spies; normal movie/TV and
C-to-A-policy planning; inter-item target conflicts, unsupported capabilities and denied execution;
no Worker/stale Worker/unsupported command/pin readiness; exact old/new activation isolation;
normal pause/continue/cancel, representative crash/restart and ownership fencing. Prove that an
unresumable discovery stops truthfully with an explicit new-discovery path, and a lost response
plus changed Active/root either recovers its proved original admission or remains unresolved with
native inspection and no guessed readback/automatic submission. Test source additions/removal/
replacement after discovery, frozen-manifest readback, explicit successor recovery,
completed/partial/uncertain execution and
post-result index-sync failures without media replay. Use Local temporary roots and SMB/OpenList/
S3-prefix fakes/local servers, no production credentials/media or frozen Slice 43 implementation.
Any persistence evolution requires compatible legacy file-only intents/previews/results/pins and
an actual migration/restart rehearsal; old work cannot gain directory scope or new authority.
Include affected full regression, safety, packaging/migration and Web lint/type/build gates;
existing direct commands, MediaLibrary isolation, RO-3 destinations and RO-5 toolbar remain covered.

The complete activated boundary requires final T4 validation. Any future material Contract change
requires A to reassess that gate. Validate and checkpoint the ACTIVE Contract/Roadmap relationship
with governance and diff checks; those checks do not establish runtime acceptance.

The smaller RO-6 delivery requires production-path proof of atomic equivalent-scope admission,
managed filter/stability publication and exact-pin consumption, root-relative policy parity, actual
nonzero stability without busy pickup/starvation, long-name/path handling, isolated file errors,
true paging units, existing Trailer association and command readiness. Retain critical control/
ownership/refusal/atomic-Finalize/exact-execution regressions. Crash/control tests may prove safe
stop plus explicit new discovery instead of seamless cursor/work continuation; old-schema tests
must preserve history/authority rather than resume every legacy combination. Unresolved admission
must remain truthful and safe. Domain injection alone cannot prove real managed policy consumption.
The revised Task defines staged T4 gates; deferred seamless-recovery cases are not closure blockers
unless they reveal a still-required outcome or safety failure. No code-size/test-count target is added.

## Prior Closure Packet — Task 44.8 / 2026-10-11

This is the correction-loop handoff after Task 44.8 PASS on 2026-10-11. Prior submission/rejection
records remain in Git, retained evidence and A's reviews below. This returns the corrected candidate
to A; B does not conduct another A Final Review or declare Slice PASS/CLOSED. The unchanged
RO-1 through RO-5 implementation/surface facts carry forward with current regressions; RO-6's
required correction is now verified. Contract outcomes/surfaces/safety/acceptance/deferrals/Base stay fixed.

```text
Slice: 44 — Existing V2 Pages Functional Improvements
Base SHA: 853973dbbf8289fa2ad40657033e94e870a690e4
Head SHA: 7e2ab801eaef25b083640813375a49f536ae202f

Required Outcomes:
- RO-1 — COMPLETE: consistent ordinary file maintenance on both library surfaces; retained implementation and current full/native regressions.
- RO-2 — COMPLETE: reference-aligned Rules workspace/forms; retained implementation and current full Web/E2E regressions.
- RO-3 — COMPLETE: MediaLibrary/path destination semantics and explicit legacy compatibility; retained implementation and current Python/upgrade regressions.
- RO-4 — COMPLETE: object-scoped Rules tests and separate complete flow; retained implementation and current Python/Web regressions.
- RO-5 — COMPLETE: exact long-name paths/toolbars on both routes/list/grid; retained layout and current browser/Docker assets.
- RO-6 — COMPLETE: exact bounded manifest, confined observations, durable refusals, usable cancellation/pause/Continue, fenced ownership, atomic intent and native separately confirmed Preview/execution.

Required Surfaces:
- COMPLETE — Both Files routes, menus/selections/dialogs/text editor, context/recovery and long-name browsing.
- COMPLETE — Scoped authenticated APIs and shared application/domain/Storage/OrganizerExecutor behavior.
- COMPLETE — Existing Task/Worker/Operations admission, pins, claims, per-item transfer/Delete checkpoints and continuation.
- COMPLETE — ResourceLibrary discovery selection/progress/control, manual choices, exact Preview/execution/results and Files/Operations return; MediaLibrary has no Organize authority.
- COMPLETE — Existing Local/SMB/OpenList/S3-R2 adapter boundaries and bounded fake/local-service verification.
- COMPLETE — Eight Rules navigation families, inventories, Add/copy drawers, Edit forms, previews and publication recovery.
- COMPLETE — Scoped shared V2 shell/header/controls and retained Storage/Settings/Operations/Automation routes.
- COMPLETE — Classification/configuration/Planner/API/CLI/scheduled and historical pinned consumers.
- COMPLETE — Family-specific Rules controls/results, Overview complete flow, bounded evidence and historical readback.

Implemented:
- Prior 44.1–44.7 implementation retained: exact deduplicated/confined manifests, monotonic material refusals and one atomic linked intent.
- Operator controls preserve current ownership; Worker publications/observations and settlements are atomically fenced by exact persisted claims. Lost owners stop without changing successors.
- Accepted cancellation settles terminal state and claim release atomically, preserving durable findings and allowing explicit successor selection without execution authority.
- Same-owner pause acknowledgement preserves bounded work/observations/refusals and releases the claim atomically. Pending Pause explains waiting and refuses premature Continue without a durable change; acknowledged native Continue resumes the same pinned scope.
- Existing Worker/SQLite/statuses suffice; no schema change, extra engine/queue or new authority. Discovery/analysis/Preview stay zero mutation; execution needs separate exact confirmation.

Tasks completed:
- 44.1 — Consistent ordinary file maintenance and recovery.
- 44.2 — Classification destination semantics and compatibility.
- 44.3 — Object-scoped Rules tests and separate complete flow.
- 44.4 — Reference-aligned Rules workspace and forms.
- 44.5 — Both-library long-name paths and toolbars.
- 44.6 — Bounded folder and mixed-selection discovery through native manual Organize.
- 44.7 — Exact bounded manifest, confinement, durable refusal and atomic one-intent handoff.
- 44.8 — Complete discovery controls under durable Worker ownership.

Final Tests:
- .venv/bin/python -m unittest discover -s tests — PASS: 2384 tests, 7 original skips, zero failures/errors; 451.632 seconds including process overhead. Assigned affected/focused modules included; independently focused discovery/provider run also PASS 71.
- web/: npm run test -- --run — PASS: 73 files / 1088 tests, zero failed/skipped; 399.674 seconds including process overhead. B's prior incomplete exit-143 run is retained as INTERRUPTED, not PASS.
- web/: npm run format:check, lint, typecheck, build — PASS. npm run test:e2e — PASS 246; real-Python Operations config/spec — PASS 21; real-Python direct-files config/spec — PASS 10; original screenshots retained before shared-output overwrite.
- Governance, Ruff format/check (358 files), compileall, pip check, both example config validations and reviewed-range git diff --check — PASS. Document-consuming governance/diff are rechecked after the handoff checkpoint.
- Fresh single wheel build/smoke — PASS, schema 45; SHA-256 c94d6ac15898460567a7640d1abaf1daefe9ac3494f5a56cb5c8ca8333f55820; all 163 packaged Python sources match the candidate. Smoke backup SHA-256 260ed838a4feaa6278534bc678243b0e8f3f09f5f9df177275e8c702407503e9.
- Native discovery browser proof — PASS 11, including four selections, refusals/reconciliation and exact separately confirmed Move/non-replay; additional native Pause/wait/acknowledged Continue/completion journey — PASS, zero source changes/execution work.
- B current managed Local/SQLite/API/actual-Worker controls — PASS 4/4; pause-settlement premature-refusal/acknowledged-Continue probe — PASS 3/3. Claim takeover remains fenced; 101 visited / 100 sources / primary_limit survives Pause and legal shrink, with Finalize 409.
- Docker release-security smoke — PASS: current committed-source image mediaflow:b-task44-8-7e2ab801eaef. Docker discovery browser proof — PASS 7 with actual resident Worker exact Move/non-replay. Genuine archived schema-38 (360e59e0791c60635f050a0444b1a2d0b4458ea4) to schema-45 upgrade/recovery — PASS: backup/preflight/rehearsal/injected failure/restore/historical state/new discovery durability.
- Submitted Developer evidence is not used to infer missing gate passes: its retained clean Web log is 1086 (old candidate), its 1088 log has one Rules timeout, and several reported final logs are absent. Additional reported earlier runs/pre-correction-image failure lack readable original artifacts here; no PASS is inferred. Fresh current B gates above establish acceptance; submitted logs and prior negative reviews remain intact.
- SKIP/UNAVAILABLE: seven unchanged dedicated real SMB/S3/OpenList and Local/remote endurance profiles. Isolated Docker is available; no production-service/media/live-deployment certification is claimed.

Safety Evidence:
- Actual immutable Task Base..Head reviewed; executable 12fd1b3 to tested/report Head differs only in TASK.md. All candidate inputs and image/dependency/configuration identities are indexed.
- Metadata-only discovery/current control probes make zero content-read/Provider/mutation calls and create zero execution Tasks. Only separately authorized OrganizerExecutor work produces the verified synthetic Move; completed effects refuse replay.
- Claims, immutable actor/library/Storage/scope/pins, bounded manifests/refusals and one-shot intent/execution authority remain binding. Read/analysis/control cannot repin to current Active or grant overwrite/delete/fallback authority. C remains C with A policies.
- Both tested current Docker images match all 163 runtime Python sources and 4 built assets. Native pending/acknowledged/Preview and Docker visible states/receipts are inspected; built-input-identities.json records exact image IDs and served-file digests.
- No deleted tests or weakened safety assertions, new hidden skips, forbidden dependency, private config/real credentials, unrelated files, frozen Slice 43 or user-image changes. Control regressions retain bounds/refusals/ownership checks under the authorized pending-Continue refusal semantics. Four original PNG hashes preserved; config/alist.json ignored/untracked/unstaged.

Known Non-blocking Issues:
- P2 — Existing Rules concurrent-Save allowed-code assertion; prior original failures/genuine Base proofs remain retained. This fresh Python/Web full run excludes no failure.
- P2 — Queued/paused progress can say “已完整遍历所选范围” while its main lifecycle is queued/paused. Current native images retain this wording; no Finalize/authority is fabricated.
- P2 — Existing Move Preview impact summary says source media is retained while its operation row correctly says Move. Prior genuine Base evidence/current image retain the copy inconsistency; exact target, separate confirmation and verified effect remain visible.

Explicitly Deferred:
- Exactly the unchanged Contract's Explicitly Deferred list above; no item added, removed or made a hidden dependency.

Documentation Reconciliation Needed:
- A to review the complete immutable Slice Base..current Head, reconcile CURRENT product/architecture/requirements and Roadmap/Progress only after its decision, and retain the frozen Slice 43 boundary.
- Distinguish current managed ResourceLibrary controls from labelled injected policy/Storage-port/legacy-shape tests; do not infer current production reachability from those tests alone.
- Evidence is local/not pushed, retained through A review: .git/validation-evidence/7e2ab801eaef25b083640813375a49f536ae202f/b-review44-8-final/ (review-index.json, input/environment/build/artifact hashes, exact commands/raw logs, original failures/interruption, API receipts, browser images and accepted Task snapshot). Prior B/A records remain intact.

Decision: SLICE READY FOR A REVIEW
```

The Head above is the tested/report candidate; the implementation is 12fd1b3. This handoff changes
only SLICE.md/TASK.md. It returns A's correction loop for the full-range final decision; B declares
neither Slice PASS/CLOSED nor another independently final-accepted Slice.

## Prior Closure Packet — superseded by the correction handoff

```text
Slice: 44 — Existing V2 Pages Functional Improvements
Base SHA: 853973dbbf8289fa2ad40657033e94e870a690e4
Head SHA: 9637e7b766fdba5287a68b1f708a7fc1f76f4a68

Required Outcomes:
- RO-1 — COMPLETE: consistent ordinary file maintenance on both supported library surfaces.
- RO-2 — COMPLETE: reference-aligned Rules workspace and purpose-built forms.
- RO-3 — COMPLETE: classification destinations use MediaLibrary plus explicit path; legacy contracts remain readable.
- RO-4 — COMPLETE: object-scoped Rules tests and separate complete-flow checks.
- RO-5 — COMPLETE: usable exact long-name paths/toolbars on both Files routes, list/grid and production-built Docker assets.
- RO-6 — COMPLETE: bounded folder/file/mixed discovery, durable control/readback, pinned manifest and existing exact confirmed Organize journey.

Required Surfaces:
- COMPLETE — ResourceLibrary Files and MediaLibrary Files menus, selection/dialogs/text editor, live context, recovery and long-name browsing.
- COMPLETE — Both scoped typed/authenticated APIs and shared application/domain/Storage/OrganizerExecutor behavior.
- COMPLETE — Existing Task/Worker/Operations transfer/Delete admission, pins, claims, per-item checkpoints and continuation.
- COMPLETE — ResourceLibrary discovery APIs/native selection/progress/control, manual choices, Preview/execution, per-item recovery and Files/Operations return; MediaLibrary remains file management.
- COMPLETE — Existing Local/SMB/OpenList/S3-R2 adapter boundaries and bounded fake/local-service regressions; no new provider.
- COMPLETE — Eight Rules navigation sections, inventories, Add/copy drawers, Edit forms, previews and publication recovery.
- COMPLETE — Scoped shared V2 shell/header/controls; existing Storage/Settings/Operations/Automation routes retained.
- COMPLETE — Classification/configuration/Planner/API/CLI/scheduled and historical pinned consumers.
- COMPLETE — Family-specific Rules tests/results, Overview complete-flow, bounded candidate/evidence behavior and historical complete-test readback.

Implemented:
- Provider-neutral metadata fences, ordinary commands on both library kinds and durable per-item Delete/transfer recovery.
- Canonical MediaLibrary/path destinations with explicit checked legacy conversion and unchanged historical pins/results.
- Local object analysis, separate complete-flow/evidence purpose, reference-aligned Rules layout/forms and retained-input Save recovery.
- Bounded exact breadcrumbs, measured complete-name disclosure and usable toolbar controls across four viewports/list/grid/both routes.
- Metadata-only bounded discovery inside the existing resident Worker, additive schema 45 persistence, scope/library/Storage/actor/pin binding, limits, observations, claims and cooperative control.
- Immutable deduplicated source handoff, original path context, C identity, exact zero-mutation Preview, separate confirmed Executor work and non-replay recovery.

Tasks completed:
- 44.1 — Consistent ordinary file maintenance and recovery.
- 44.2 — Classification destination semantics and compatibility.
- 44.3 — Object-scoped Rules tests and separate complete flow.
- 44.4 — Reference-aligned Rules workspace and forms.
- 44.5 — Both-library long-name paths and toolbars.
- 44.6 — Bounded folder and mixed-selection discovery through native manual Organize.

Final Tests:
- .venv/bin/python -m unittest discover -s tests — PASS: 2352 tests, 7 skipped, 0 failures/errors, 554.317 seconds. Unfiltered fresh Slice Final after Task PASS.
- First independent full Python run — 2352 tests / 7 skipped / 1 failure: unchanged Rules simultaneous-Save allowed-code assertion. Current isolated test PASS; genuine Task Base reproduces the same failure on original repetition 4, genuine Slice Base on repetition 3. Original failures/repetitions retained; no assertion/selection/timeout/retry/skip changes. Final full command above passes unchanged.
- .venv/bin/python scripts/check_governance.py; .venv/bin/ruff format --check .; .venv/bin/ruff check .; .venv/bin/python -m compileall -q mediaflow tests scripts; .venv/bin/python -m pip check; git diff --check — PASS. Governance/diff are rechecked on the documentation-only closure checkpoint.
- .venv/bin/mediaflow --config config/strategy.example.json config validate; corresponding config/mediaflow.phase13.2.example.json validation — PASS, both examples.
- .venv/bin/python -m pip wheel . --no-deps -w dist; .venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-2.0.0.dev0-py3-none-any.whl — PASS; one freshly built wheel, schema-45 backup verified, SHA-256 17cb08b398f95899ccb44471bd45b9ad5dc02eccc4e20c2a18d1b59902ab99ee.
- web/: npm run test -- --run — PASS: 72 files / 1083 tests / 0 skipped or failed; npm run format:check, lint, typecheck and build — PASS.
- web/: npm run test:e2e — PASS: 246 tests / 0 skipped or failed, original 2 workers and retries 0; Python Operations config/spec — PASS 21; Python DirectFiles config/spec — PASS 10.
- Real Python discovery proof — PASS: 11 browser passes, four selections, limit refusals, reconciliation, one exact confirmed completed effect and successor isolation. B separate native mixed journey — PASS: overlap dedup, changed Active/old pin, native freeze/C choice/two-item exact Preview/confirmation/completion and no replay. Actual API restart/pause/resume and real Local missing subtree/explicit subset freeze — PASS. Full regression includes controlled-clock size-stability/reset and stale-owner/uncertain/index-sync non-replay cases.
- scripts/files_toolbar_browser_proof.py — PASS: 22 passes / 48 screenshots, both routes/four viewports/list-grid, exact paths, no work or activation.
- scripts/rules_workspace_browser_proof.py, rules_object_analysis_browser_proof.py, classification_destination_browser_proof.py, rules_identity_browser_proof.py, storage_settings_browser_proof.py — all PASS on current Python/built assets; Rules includes 13 current screenshots, preserved reference hashes, measured layout/refused-Save retention and zero unintended work.
- scripts/docker_release_security_smoke_test.py --image mediaflow:b-slice44-final-9637e7b766fd — PASS: fresh committed-source image, RBAC/redaction/build-context/log/SQLite/export and unsupported-host-access gates.
- scripts/docker_files_organize_discovery_browser_proof.py --image same candidate — PASS: 7 browser passes, four selections, real resident Worker exact completed Move and no replay.
- scripts/docker_files_toolbar_browser_proof.py --image same candidate — PASS: 22 passes, current served index/JS/CSS matches local build.
- scripts/docker_health_smoke_test.py --image mediaflow:b-slice44-health-9637e7b766fd — PASS: health/readiness, stopped Worker and repaired secret-reference/mount conditions.
- scripts/docker_upgrade_recovery_smoke_test.py — PASS: genuine archived schema-38 application (360e59e0791c60635f050a0444b1a2d0b4458ea4) to schema 45, verified backup/preflight/rehearsal/injected failure/restore, old-code manual intents/Previews/authorizations/admitted/completed/partial/uncertain state and new discovery persistence. Schema44-to45 unit fixture is explicitly a schema-shape fixture, not prior-artifact evidence.
- Unavailable: 7 original dedicated real SMB/S3/OpenList and Local/remote endurance profiles; skips are unchanged and reported. Isolated Docker is available. No production service, user media or live deployment is certified or changed.

Safety Evidence:
- B inspected actual Task Base..Head and correction diff; no removed/weakened tests, added skips, silent fallback, dependency expansion, config/alist.json, real credentials, unrelated user files or frozen Slice 43 changes.
- Admission/discovery/analysis/Preview remain metadata-only or their explicitly permitted bounded reads, with zero media mutation and no discovery execution authority. Only separately confirmed existing OrganizerExecutor work produces tested effects.
- Actual two-library equal-relative-path API/native test freezes the correct second-library sources; actual lost-response recovery/reconnect preserves one original discovery and return context. Whole invalid scopes and primary/safety limits cannot authorize a prefix.
- Actual changed Active retains old discovery/intent/Preview/execution pins; C stays C with A policies. Paused scope survives actual API restart; actual missing subtree preserves independent findings. Completed effects refuse replay; existing full/upgrade gates retain partial/uncertain/historical facts.
- Current root/packaging/Docker gates protect RBAC, confinement, capabilities/conflicts, explicit mutation/destructive authority, attribution, redaction and claims. Existing remote fake/local-server coverage is not presented as a real-service run or universal conditional identity guarantee.
- Local and Docker served index SHA-256 ce9351ee0bfaab0a5d66c5a2fc6066b15a86646754cf95d0d507bc1c02fbe705; JS 25f90668d49b971f309ce365b2a0e8e163b70e9c2996b4b84e50d55432aebb77; CSS abd3206d693af6f937f159cd238bfd6c1df97d065d8b64d9ed882a1d582e5f3b. Tested Docker image ID sha256:4a604e4fdcad753c767ca765e6b2ae3a4116fde0e39e1e39afd280dc3bebac5e.

Known Non-blocking Issues:
- P2 — Pre-existing simultaneous Rules Save test omits the safe refused-destination-check code from its allowed set. Genuine Task/Slice Base reproductions and first failure remain visible; final unchanged full suite passes. Publication consistency/Active preservation assertions pass. No test-only Task or relaxed assertion is introduced.
- P2 — Discovery queued/paused progress can display “已完整遍历所选范围” while the main status correctly says queued/paused. Actual native screenshot/receipt records this wording inconsistency; finalize remains unavailable, no sources/authority are fabricated, and limit/incomplete states retain their refusal. This is non-blocking copy, not completion authority.

Explicitly Deferred:
- Unchanged: all items in the Contract's Explicitly Deferred section above, including frozen Slice 43, unselected pages/features, Upload/Download, unbounded/cross-kind/Replace/universal rollback/new providers, conditional-generation redesign, full-media Rename/Delete hashing/universal identical-metadata replacement detection, global Rules search/new shell/rule-engine redesign, historical rewrite/replay/automatic relocation, live deployment changes, MediaLibrary/root organization, automatic splitting/higher primary bound/second engine and selection-implied cleanup.

Documentation Reconciliation Needed:
- A to reconcile Roadmap/Progress/current development pointer only after A's final decision; B has not changed them or declared Slice PASS/CLOSED.
- A to reconcile CURRENT architecture/product/requirement descriptions for canonical versus historical destination behavior, object-test versus complete/physical readiness, Rules/Files presentation, schema-45 bounded discovery/pins/claims/native control and exact confirmed handoff; distinguish actual managed ResourceLibrary controls from policy-model test coverage.
- Evidence is local and retained through A review, not pushed: .git/validation-evidence/9637e7b766fdba5287a68b1f708a7fc1f76f4a68/b-review-final/ (review-index.json, original logs/receipts/helpers, Base reproductions, accepted Task snapshot and current visuals). Matching Developer Task evidence at bf0e00e9a7253ef93684265589e3849e568369be/task44-6-correction2 was verified; it does not substitute for this fresh Slice Final.

Decision: SLICE READY FOR A REVIEW
```

`Head SHA` is the tested implementation/report checkpoint. The closure checkpoint changes only
SLICE.md/TASK.md documentation; runtime, tests, dependencies, configuration, harnesses and built
artifacts remain those identified above. Task 44.6's accepted review is retained in TASK.md and
`task44-6-pass-TASK.md`. This packet is a handoff to A, not a Slice acceptance or closure decision.

## Prior A Final Review — 2026-10-10 / 9637e7b766fd

```text
Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..9637e7b766fdba5287a68b1f708a7fc1f76f4a68
Decision: FIX REQUIRED
Review Date: 2026-10-10
Reviewer: A — Slice Owner / Architect / Final Reviewer
P0/P1 Blockers:
- P1 / A44-1 — RO-6, acceptance 27/28/30: repeated stability observations duplicate
  an already eligible source and break the required discovery-to-intent journey.
  With two media files and a 60-second stable-size policy, observe both, advance
  120 seconds while changing B, then advance another 120 seconds without changes.
  The completed discovery contains [A, A, B] for two physical files. Finalize
  returns HTTP 201 with status failed / failure duplicate_source and no intent.
  Evidence: mediaflow/application/media_discovery.py:549-570 and :686-691 carry
  forward sources and append each stable observation again; independent receipt
  mixedStability reproduces the authenticated API failure with real temporary
  Local Storage, SQLite and a controlled clock. Minimum correction: keep one
  source per exact admitted Storage/library/path through repeated observations,
  retain valid identity/stability evidence, and count unique sources for limits
  and handoff. Verify mixed stable/unstable files over multiple passes and restart;
  the operator must reach one exact intent without duplicate_source or false limits.
- P1 / A44-2 — RO-6 selection confinement, acceptance 29/31/32 and the Safety
  Invariants: provider entries can expand discovery outside the selected subtree.
  Submit paths=[Selected], then make that directory's list_page return an actual
  ordinary file Outside/B.2002.mkv within the same ResourceLibrary. Discovery
  reports completed, advertises Finalize, and freezes an intent containing that
  unselected source. Evidence: mediaflow/application/media_discovery.py:761-771
  checks only ResourceLibrary-root membership; :1429-1440 accepts the sibling.
  Independent receipt escapedSelection preserves the exact submitted scope,
  authenticated readback and resulting intent. Minimum correction: validate every
  provider entry's safe path/name/type and membership in the exact requested
  directory and admitted selection before counting, queueing, observing or
  freezing it. Unsafe/out-of-scope entries must remain excluded and visibly
  incomplete where required, never enlarge the frozen source list. Verify sibling,
  ancestor, traversal, absolute and inconsistent provider paths with confined fakes.
- P1 / A44-3 — RO-6 bounded truthful discovery, acceptance 29/31: a later ordinary
  read failure erases an earlier cyclic-cursor refusal and allows a truncated
  source prefix to become an intent. Select Loop and Locked; Loop returns one
  primary source followed by a repeated cursor, then Locked denies listing.
  The durable reasons retain repeated_provider_cursor, but incompleteReason is
  overwritten with read_failure. Finalize becomes available and creates an intent
  for Loop/A.2001.mkv. Evidence: mediaflow/application/media_discovery.py:832-844
  records CURSOR_REPEATED, :743-758 replaces it, and :441 checks only the final
  reason. Independent receipt maskedCursorLimit reproduces the API handoff.
  Minimum correction: preserve all material incomplete/safety facts, or an
  equivalent durable strongest refusal, across scopes, passes and restart.
  Any budget/safety/cursor refusal must prevent Finalize even when another subtree
  later has an ordinary read failure. Preserve the separately legal explicitly
  reviewed read-failure-only subset journey and verify both event orders.
```

These are unmet outcomes and a selected-source safety regression inside the existing RO-6
Contract, not a Contract impossibility or a scope change. Base, Implementation Head, Required
Outcomes, Required Surfaces, Safety Invariants, acceptance and Explicitly Deferred remain unchanged.
The Closure Packet above remains B's submission record; its RO-6 COMPLETE conclusion is contradicted
by A's independent reproductions. No Slice acceptance or factual closure reconciliation occurs.
B owns the next focused correction Task; A creates no Task and changes no implementation code.

### Validation and evidence

- A independently ran the unchanged full Python suite on the reviewed executable candidate:
  `.venv/bin/python -m unittest discover -s tests` — **PASS**, 2352 tests, 7 skipped,
  0 failures/errors, 408.520 seconds. Ruff format/check and pip dependency checks also passed.
  The new negative reproductions confirm three defects outside that suite's current coverage;
  the suite's PASS does not satisfy the affected RO-6 criteria.
- The reviewed Implementation Head and workspace HEAD `786dc81f27ecd764048c190a4bc5dc929225fc32`
  differ only in SLICE.md/TASK.md. No source, tests, dependencies, runtime configuration,
  harnesses or built artifacts changed during A's review. A verified all 237 B-indexed artifact
  hashes and all input/build/wheel digests against the workspace, read original full/Web/Docker/
  packaging/migration logs and Base concurrency reproductions, and inspected actual saved Rules,
  Docker narrow-toolbar and native Preview images. The supplied seven external-service/endurance
  skips remain SKIPPED/UNAVAILABLE; no production-service certification is inferred.
- Independent probes use temporary synthetic Local files, the existing SQLite/application/API
  fixture, a controlled clock and deliberately bounded provider responses. All three record zero
  Storage mutation/content-read calls; no Preview execution or execution authority is requested.
  Original helper errors and the final harness/receipts are retained. No product source or tests
  were edited to reproduce the defects.
- Additional independent Web/browser/Docker/packaging/migration reruns are **NOT RUN** after the
  proven P1 blockers. The verified matching B Slice Final evidence remains available for review;
  this rejecting decision does not certify complete final acceptance of the other outcomes.
- Evidence is local and retained at
  `.git/validation-evidence/9637e7b766fdba5287a68b1f708a7fc1f76f4a68/a-final-review/`, including
  `review-index.json`, `root-runs.json`, `discovery-probes.py`, `discovery-probe-receipts.json`
  and original logs. B's `b-review-final/` evidence remains intact. No push or deployment occurred.
- The pre-decision governance check and complete reviewed-range diff check passed.
  The existing guard at `scripts/check_governance.py:161-162` rejects the workflow's required
  `FIX REQUIRED` plus `NO ACTIVE IMPLEMENTATION TASK` handoff with
  `Slice FIX REQUIRED cannot have NO ACTIVE IMPLEMENTATION TASK`. This is an existing tooling
  mismatch, not evidence that A may fabricate a B-owned Task, revert the decision to ACTIVE,
  move Base or change the Contract. Post-decision governance failure is recorded honestly;
  B must account for this handoff mismatch in its planning preflight.
- The four pre-existing untracked user PNGs are preserved and excluded from the checkpoint;
  `config/alist.json` remains ignored, untracked and unstaged. The reported P2 concurrent-Save
  allowed-code assertion and discovery progress wording are not closure blockers.

NEXT ACTION: B PLANS ONE FOCUSED CORRECTION TASK

## Prior A Final Review — 2026-10-10 / fd52b0332c4b

```text
Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..fd52b0332c4baed3dd5417bf18799a91dd74d028
Decision: FIX REQUIRED
Review Date: 2026-10-10
Reviewer: A — Slice Owner / Architect / Final Reviewer
P0/P1 Blockers:
- P1 / A44-4 — RO-6 cooperative cancellation and recovery, acceptance 30:
  an accepted cancellation can permanently strand the discovery. Cancel a queued
  discovery before Worker pickup: POST returns 200 with cancelRequested=true,
  but three actual MediaDiscoveryWorker.run_next calls, each after advancing the
  controlled clock by 600 seconds, return no work; readback remains queued.
  Repeating the same Files selection reconciles to that stranded discovery.
  Cancel during a blocked list_page call: the returning Worker reads the old
  control/version snapshot, its progress CAS fails, and all later pickups exclude
  the cancellation request. Again the discovery never reaches cancelled.
  Evidence: mediaflow/application/media_discovery.py:960-964 checks the originally
  loaded flags; :1556-1572 only persists a cancel request. The production claimant
  at mediaflow/infrastructure/sqlite_runtime.py:10095-10113 excludes every row
  with cancel_requested=1. Authenticated API and actual Worker receipts
  queuedCancel/runningCancel reproduce both cases with temporary Local/SQLite.
  Minimum correction: ensure queued, paused/waiting and in-flight cancellation
  can reach a durable terminal acknowledgement at a safe boundary, including
  after process restart or lease loss. Reconcile concurrent control/version
  changes without losing known findings, resetting bounds, leaving unclaimable
  open work or trapping deliberate successor selection. Preserve zero mutation
  and no execution authority; verify actual Worker pickup rather than only
  calling run_claimed manually after a pre-established claim.
- P1 / A44-5 — RO-6 restart/ownership/recovery, acceptance 30/31 and the
  concurrency-fencing Safety Invariant: a stale Worker can clear the successor's
  valid claim and leave an unrecoverable paused discovery. Block old Worker's
  list_page; advance the clock beyond its lease; let successor Worker acquire
  the discovery; release the old call. Its heartbeat correctly detects claim
  loss, but _publish_paused writes status=paused and clears the successor claim.
  Readback has pauseRequested=false and resume.available=false; no Worker can
  claim paused work, and the same selection returns this stranded record.
  Evidence: mediaflow/application/media_discovery.py:771-773 and :1483-1502;
  mediaflow/infrastructure/sqlite_runtime.py:10109-10128 replaces claim ownership
  without advancing the version, while :10271-10307 writes Worker progress using
  only discovery ID/version and overwrites claim/control fields. The staleOwner
  receipt records the real successor claim before the old Worker removes it.
  Minimum correction: fence every Worker-owned progress/state/observation write
  atomically by its current valid claim, distinguish control writes from Worker
  publication, and let a lost owner stop without changing successor state.
  Any retained paused/waiting state needs a valid native continuation. Verify
  overlapping owners, lease expiry/restart and concurrent pause/cancel while
  retaining the exact scope/pin/manifest and monotonic limits/refusals.
```

Both blockers are inside the existing RO-6 Contract. No Contract impossibility or material scope
change is established. Base, Implementation Head, Required Outcomes, Required Surfaces, Safety
Invariants, acceptance and Explicitly Deferred remain unchanged. The current Closure Packet stays
as B's submission record; its complete RO-6 conclusion is contradicted by these independent
reproductions. A creates no Task, changes no implementation and performs no closure reconciliation.
B owns one focused correction Task and its normal review loop.

### Validation and evidence

- Independent unchanged full Python regression: `.venv/bin/python -m unittest discover -s tests`
  — **PASS**, 2374 tests, 7 skipped, 0 failures/errors, 422.303 seconds. Ruff format/check,
  dependency check and complete Base..Head diff check also passed. A green suite does not satisfy
  the two uncovered control/ownership criteria above.
- A repeated the original A44-1/A44-2/A44-3 negative scenarios on the current candidate: mixed
  stability freezes exactly A/B once each; sibling escape freezes no source and returns 409;
  cyclic-cursor refusal survives the later read failure and Finalize returns 409. The accepted
  correction remains valid on these scenarios. Independent managed Local/SQLite/authenticated
  concurrent Finalize also passes 10/10: 201/409, one linked intent, intact source and no execution
  Task. These facts do not certify the remaining control/ownership boundary.
- Reviewed Head and workspace HEAD `4e73fafac846027ca0e0efabe72efbc78913c29a` differ only in
  SLICE.md/TASK.md. A verified all 589 indexed candidate inputs, all 99 current B-indexed artifact
  hashes and all four preserved user PNG hashes without mismatch, and checked original final
  regression/security/upgrade logs. B's first Web timeout and Docker health-wait failures remain
  failures with exact subsequent passing runs; no source/assertion/timeout/retry/skip change is
  used to hide them. Seven original real-service/endurance profiles remain SKIPPED/UNAVAILABLE.
- The new probes use authenticated API, real temporary Local/SQLite, actual MediaDiscoveryWorker
  and controlled clock/event coordination. They record zero Storage content-read/mutation calls
  and zero execution Tasks. No production service, media, live deployment or frozen Slice 43 code
  is changed. Additional independent Web/browser/Docker/wheel/migration reruns are **NOT RUN**
  after the proven P1 blockers; verified B evidence is provenance, not A acceptance of other RO.
- Evidence is local/not pushed and retained at
  `.git/validation-evidence/fd52b0332c4baed3dd5417bf18799a91dd74d028/a-final-review2/`, including
  `review-index.json`, original full log, `control-probes.py`, `control-probe-receipts.json`,
  original-scenario and concurrent-Finalize receipts. The first adapted original-scenario helper
  had an incorrect HTTP expectation; its error log and corrected harness/run remain preserved.
  No application source or repository tests changed during reproduction.
- Governance passed before the decision. The existing guard still rejects `FIX REQUIRED` plus
  `NO ACTIVE IMPLEMENTATION TASK` with `Slice FIX REQUIRED cannot have NO ACTIVE IMPLEMENTATION
  TASK`; the post-decision failure is a tooling mismatch already recorded by the prior review.
  A does not fabricate a B-owned Task, revert to ACTIVE, move Base or edit guard implementation
  to avoid it. B must account for the handoff mismatch in its planning preflight.
- Four pre-existing untracked user PNGs remain preserved and outside the checkpoint;
  config/alist.json remains ignored, untracked and unstaged. Known P2 wording/assertion issues
  are not blockers. Roadmap, Progress and other CURRENT documents receive no closure update.

NEXT ACTION: B PLANS ONE FOCUSED CORRECTION TASK

## Prior A Final Review — 2026-10-11 / initial review of 7e2ab801eaef

```text
Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..7e2ab801eaef25b083640813375a49f536ae202f
Decision: FIX REQUIRED
Review Date: 2026-10-11
Reviewer: A — Slice Owner / Architect / Final Reviewer
P0/P1 Blockers:
- P1 / A44-6 — RO-6 duplicate-free durable admission/recovery, acceptance 30:
  two concurrent authenticated submissions by the same actor, ResourceLibrary,
  canonical paths=[Movies] and immutable pin both return HTTP 202 with different
  discovery IDs. Real SQLite retains two queued walks for the same admission.
  The independent concurrentAdmission receipt coordinates only the boundary
  before the unchanged repository insert, after both requests have completed
  their reconciliation reads; it changes no Storage response or product behavior.
  Evidence: mediaflow/application/media_discovery.py:233-244 checks recent work
  before generating a fresh UUID; :288-291 inserts separately. The repository at
  mediaflow/infrastructure/sqlite_runtime.py:9953-9970 protects only that new UUID,
  not the actor/library/Storage/canonical-scope/pin admission identity. Minimum
  correction: reconcile and admit that exact open-work identity atomically in
  durable authority so overlapping requests converge on one record across
  connections/restart; retain separate terminal/successor work and different
  actor/library/scope/pin isolation. Verify actual concurrent authenticated
  admission, overlapping unknown-response recovery and ordinary readback, with
  one durable walk and no implicit execution authority. A process-local lock or
  a best-effort search of only the most recent records is not durable uniqueness.
- P1 / A44-7 — RO-6 pinned configurable filtering/stability, acceptance 28/30
  and its required native configuration/runtime surface: include/exclude and
  stability behavior exists only for directly constructed/injected domain objects,
  not the production managed ResourceLibrary journey. The actual runtime loader
  at mediaflow/infrastructure/runtime_configuration.py:332-341 consumes only
  extensions/maxDepth beyond the basic binding; it never loads include/exclude or
  FileStabilityPolicy. The typed ResourceLibrary allowlist at
  mediaflow/application/configuration_objects.py:338-348 exposes none of them.
  Consequently all production-loaded stability durations are zero. Tests at
  tests/test_media_discovery.py:438-463 replace the loaded library's policy rather
  than proving the published configuration reaches the Worker.
  Independent managed-policy-receipt uses an imported, validated, activated exact
  revision and the unchanged production managed-runtime loader, with no injected
  filter/stability policy. Supplied includeRules/excludeRules/stabilityPolicy remain
  in the revision but runtime ignores them: the specifically excluded movie is
  accepted immediately, status=completed, one primary source, Finalize available,
  and all three stability durations zero. These probe key names are evidence of
  missing mapping, not a prescribed new schema. Minimum correction: make the
  promised bounded library filtering/stability configuration Web/API-completable
  through the shared managed validation/publication authority and consume it from
  the exact immutable admission pin in real discovery/Worker composition. Preserve
  old documents/defaults and focused edits, expose invalid settings/recovery, and
  prove configured exclusions and a nonzero genuine stable-size interval through
  actual publication, restart and old/new pin isolation without replacing the
  runtime library in the test. Do not defer this promised outcome or use domain-only
  tests as completion of the required surface.
```

These are unmet RO-6 outcomes inside the unchanged Contract, not evidence that the Contract is
impossible. Base, Implementation Head, Required Outcomes, Required Surfaces, Safety Invariants,
acceptance and Explicitly Deferred stay unchanged. Task 44.8's accepted B review remains historical;
A does not conduct another Task review. The current Closure Packet remains B's submission record,
but its RO-6 COMPLETE conclusion is contradicted by these independent observations. No closure
reconciliation occurs and no next Slice is selected. B owns focused correction planning and its
normal implementation/review loop; A changes no implementation and creates no Task.

### Validation and evidence

- Independent unchanged full Python regression: `.venv/bin/python -m unittest discover -s tests`
  — **PASS**, 2384 tests, 7 skipped, 0 failures/errors, 420.213 seconds. Ruff format/check, pip
  dependency check and complete Base..Head diff check also pass. A green suite does not satisfy
  the uncovered admission/configuration outcomes above.
- Fresh reruns retain the earlier corrections: mixed stability freezes exactly A/B once each;
  sibling escape and cyclic-cursor-then-read-failure refuse Finalize with 409; queued/in-flight
  cancellation settles and permits deliberate successor work; a stale Worker cannot change a
  successor claim. Same-owner pause preserves 101 visited / 100 sources / primary_limit, and
  the later legal shrink cannot authorize that prefix. Three pending-Pause cases refuse early
  Continue without a durable change, then acknowledged Continue completes the same scope.
  Concurrent Finalize passes 10/10 with 201/409 and one linked intent. Original adapted helpers,
  fresh receipts and logs are retained; these checks do not excuse the new admission race.
- A verified all 625 B-indexed candidate inputs (excluding the two documented handoff files),
  all 178 B-indexed artifacts, current built Web digests and the four preserved user PNG hashes,
  with no mismatch. Reviewed Head and workspace HEAD
  e30da30f15b8d6760ddb7d97a3c83366ce689b11 differ only in SLICE.md/TASK.md. Source, tests,
  dependencies, runtime configuration, harnesses and built artifacts match the tested candidate.
  Original B Python/Web/E2E/native/Docker/wheel/upgrade logs and first failures/interruption
  remain intact. Seven unchanged external-service/endurance profiles remain SKIPPED/UNAVAILABLE;
  no production-service or live-deployment acceptance is inferred.
- Additional independent Web/browser/Docker/wheel/migration reruns are NOT RUN after the proven
  P1 blockers. Matching B evidence establishes provenance, not A final acceptance of the remaining
  surfaces. P2 concurrent-Save assertion, queued/paused progress wording and Move-summary copy
  remain non-blocking; none alone caused this decision.
- New probes use temporary synthetic Local files, real SQLite, authenticated API and actual
  Worker pickup. They record zero Storage content-read/mutation calls and zero execution Tasks.
  The policy probe reloads the actual published revision through the production loader instead
  of using the fixture's injected library policy. Test coordination wraps only the unchanged
  insert boundary. No product source/tests, production media/services, live deployment or frozen
  Slice 43 code changed. config/alist.json remains ignored, untracked and unstaged; all four
  pre-existing untracked PNGs remain preserved outside the checkpoint.
- Evidence is local/not pushed at
  .git/validation-evidence/7e2ab801eaef25b083640813375a49f536ae202f/a-final-review3/,
  including review-index.json, full-python.log, admission-probes.py,
  admission-probe-receipts.json, managed-policy-probe.py, managed-policy-receipt.json and the
  rerun correction/control/Finalize receipts. All earlier A/B evidence remains unchanged.
- Pre-decision governance passes. The existing guard at scripts/check_governance.py:161-162
  still rejects the workflow-required FIX REQUIRED plus NO ACTIVE IMPLEMENTATION TASK handoff
  with `Slice FIX REQUIRED cannot have NO ACTIVE IMPLEMENTATION TASK`. Record the post-decision
  failure honestly; A does not fabricate B's Task, revert to ACTIVE, move Base or change guard
  implementation to hide this known tooling mismatch. B must account for it in planning preflight.
  Roadmap, Progress and other CURRENT documents receive no closure update.

NEXT ACTION: B PLANS ONE FOCUSED CORRECTION TASK

## Prior A Final Review — full folder audit before recovery rescope

```text
Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..7e2ab801eaef25b083640813375a49f536ae202f
Decision: FIX REQUIRED
Review Date: 2026-10-11
Reviewer: A — Slice Owner / Architect / Final Reviewer
Review Scope: complete RO-6 folder/mixed-selection journey sweep, not a Task review
P0/P1 Blockers:
- P1 / A44-6 — RO-6 durable admission/recovery, acceptance 30/31:
  retain the original confirmed concurrent duplicate admission. Further actual
  API probes create duplicate open work when the same two scopes change order
  or the original record falls outside the last-50 reconciliation window.
  Actual production-built Web unknown-response recovery selects another pin's
  discovery after a new activation changes the ResourceLibrary root; real
  SQLite proves the original and selected admissions have different pins.
  Minimum correction: atomically reconcile the exact durable admission identity,
  canonicalize scope-set identity, and correlate unknown responses to the actual
  request while preserving actor/library/Storage/scope/pin isolation and explicit
  terminal successors. A path-only match or recent-record search is insufficient.
- P1 / A44-7 — RO-6 pinned filtering/stability/depth, acceptance 28/30:
  retain the original production configuration/runtime omission. Actual managed
  maxDepth=1 excludes Movies/Sub/Two.mkv when selecting Movies, but direct
  selection of Movies/Sub accepts it. A supported domain DIRECTORY exclusion
  also applies only while walking the parent, not when selecting that directory.
  Minimum correction: complete bounded Web/API configuration through the shared
  managed validation/publication authority and consume the exact pin; enforce
  the same root-relative filters/depth at all selection/observation entrances.
  Preserve legacy defaults, focused edits, invalid-input recovery and pin isolation.
- P1 / A44-8 — RO-6 genuine stability and safe background progress,
  acceptance 28/29/30 and independent-work recovery:
  waiting_stability is immediately reclaimable as the oldest record. Twelve
  actual Worker calls pick the same waiting item while the next stays queued;
  the resident short-circuit leaves later manual/transfer runners uncalled.
  In a nonzero 60-second policy probe, with clock deliberately before due time,
  100 quick passes over 100 files exhaust 10000 entries and become a permanent
  entry_limit refusal instead of waiting. This probe transparently injects the
  domain policy because A44-7 currently blocks production configuration.
  Minimum correction: persist and honour meaningful observation timing and let
  independent work advance without busy polling, fabricated elapsed stability,
  resetting cumulative bounds, weakening fences or freezing a truncated prefix.
- P1 / A44-9 — RO-6 exact names, required native Web/API, acceptance 27/29/30:
  a real legal 1222-character Local path returns API 200/completed but the actual
  built Web refuses its 1024-limited discovery model and cannot read/recover the
  record. A legal 179-character Local filename reaches the 128-character manual
  identity limit; two real Worker pickups separated by lease expiry both return
  None and leave the entire batch queued/failure=null, attempts=2.
  Minimum correction: align supported identity/name/path bounds across admission,
  discovery, manual handoff and Web, preserve exact names, and persist/isolate
  actionable item failures instead of swallowing exceptions and re-leasing forever.
- P1 / A44-10 — RO-6 truthful partial findings and recovery, acceptance 29/31:
  one explicit file disappears or stat returns permission denied after admission
  in a mixed file/folder selection. API reports completed, errorEntries=1,
  incomplete=false and whole-scope completion; Finalize 201 silently holds only
  the readable source without the partial-discovery gate/message used for directory
  failures. Minimum correction: consistently represent per-file unknown/read
  failure and per-subtree failure, retain independent known sources/errors and
  permit only an explicitly reviewed bounded subset rather than false completeness.
- P1 / A44-11 — RO-6 bounded Storage paging, acceptance 29:
  production managed OpenList HTTP/Worker accesses one distinct directory, but
  every page increments visitedDirectories. A legal 1001-page repeated-basename
  walk with one deduplicated primary stops at page 1000 for directory_limit while
  page/entry/time bounds remain available. Minimum correction: count directories,
  pages and entries by their actual durable units and enforce the correct bounds,
  without raising limits or permitting an executable truncated prefix.
- P1 / A44-12 — RO-6 main/attachment semantics and primary bound,
  acceptance 27/28/29/31:
  under actually published enabled attachment policy, One.2001-trailer.mp4 is
  both a Trailer recognised by existing AttachmentDiscovery and an independent
  frozen intent primary item. 51 main videos plus 51 matching Trailer sidecars
  consequently stop at primary_limit despite only 51 main media.
  Minimum correction: preserve existing main/attachment association through
  discovery-to-intent, count primary media once and prevent duplicate primary
  authority for a sidecar. Reuse the existing matcher/policy semantics; do not
  build a new general Extras engine or broaden deferred functionality.
- P1 / A44-13 — RO-6 truthful Worker readiness/recovery, acceptance 30
  and required unsupported-command validation:
  actual current-schema live Worker registration with commands=(scan,) yields
  discovery.worker.ready=true, while that same service's command-readiness for
  media_discovery correctly says unsupported. Minimum correction: project the
  actual discovery command capability/compatibility and its meaningful recovery
  instead of borrowing a live/schema-only manual readiness result; retain the
  separate existing execution/transfer readiness behavior.
```

The consolidated [full folder-journey audit](docs/reviews/slice-44-folder-organize-audit.md)
contains each reproduction, source locations, minimal correction direction, severity, coverage
and actual evidence. A44-6/A44-7 retain and extend the earlier confirmed findings; A44-8 through
A44-13 are six additional groups. All are inside the unchanged RO-6 Contract. There is no Contract
impossibility, Material Contract Change or PARTIAL/RESCOPE: Base, Implementation Head, RO/Surfaces,
Safety Invariants, acceptance, 100-primary bound and Deferred remain unchanged. Prior Task 44.8
PASS and B's Closure Packet remain historical, not A acceptance. No closure reconciliation occurs.

### Validation and evidence

- Fresh focused Python: PASS, 127 tests, 22.215 seconds, zero failures/errors/skips;
  focused Web: PASS, 3 files / 53 tests, 35.03 seconds. Fresh actual built-Web/native proof:
  PASS, 11 browser cases, four selection kinds, acknowledged pause/Continue, limits/readback,
  exact separately confirmed temporary Local Move and non-replay.
- Twenty additional negative scenarios reproduce the grouped P1s and independent P2s; their
  REPRODUCED receipts certify defects, not product PASS. Two actual native negative journeys
  prove wrong-pin/root unknown-response recovery and the long-path read failure. Screenshots
  were inspected. The 179-character filename and per-file denial cases use actual Worker
  pickup/API/SQLite, with bounded fault injection explicitly identified where used.
- Mixed/stable manifest dedup, confinement/cursor refusal, atomic Finalize, earlier cancellation,
  same-owner controls, stale-owner fencing, original path/C identity, source change and normal
  exact-execution gates remain passing in the current regressions. No missing evidence was
  converted into acceptance; the green suites miss the cross-boundary cases above.
- Revalidated all 625 B-indexed candidate inputs except the documented review/handoff files,
  and all 178 B-indexed artifacts: no mismatch. Same-candidate independent full Python from
  a-final-review3 stays PASS, 2384 tests, 7 skipped, 420.213 seconds. Source/tests/dependencies/
  configuration/built Web did not change; a duplicate full run is unnecessary for this audit.
  Existing B Web/E2E/Docker/wheel/upgrade/security evidence is reused with provenance; additional
  independent reruns of those full gates are NOT RUN this sweep. Seven external/endurance
  profiles retain actual SKIP/UNAVAILABLE. No production-service acceptance is inferred.
- P2 exact equality budget cases, safety-depth explanation/anchor mismatch, queued/paused progress
  wording, concurrent-Save optional assertion and Move-summary copy do not independently block PASS.
  B must use the complete grouped list rather than treat a green direct-object test as delivery
  of a required real Web/API/configuration/Worker journey.
- Durable local evidence is in
  .git/validation-evidence/7e2ab801eaef25b083640813375a49f536ae202f/a-folder-sweep/;
  original prior probes remain in a-final-review3/ and all earlier A/B evidence stays retained.
  Probe setup failures are preserved separately; corrected probe harnesses changed no product
  implementation or assertions. New negative probes performed zero Storage content/mutation
  and created zero execution Tasks. The positive native proof's only media effect was an
  expressly confirmed exact Move in its temporary root. No live deployment/media/services or
  frozen Slice 43 implementation changed. config/alist.json remains ignored/untracked/unstaged;
  all four pre-existing user PNGs remain untouched outside this checkpoint.
- The existing governance guard still rejects workflow-required FIX REQUIRED plus NO ACTIVE
  IMPLEMENTATION TASK. Its actual failure is recorded separately and is not a product blocker;
  A does not fabricate B's Task, alter Base/status to hide it or implement a guard change.
  This checkpoint contains only A review/handoff documentation; Roadmap, Progress and other
  CURRENT documents receive no closure update. No next Slice is selected and no push occurs.

NEXT ACTION: B PLANS ONE FOCUSED CORRECTION TASK

## Prior A Final Review — 2026-10-11 / user-approved recovery rescope

```text
Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..7e2ab801eaef25b083640813375a49f536ae202f
Decision: PARTIAL / RESCOPE
Decision Date: 2026-10-11
Reviewer: A — Slice Owner / Architect / Final Reviewer
Contract Problem: the earlier RO-6 required seamless discovery continuation/correlation through
  exceptional crash/control/activation/legacy combinations. The user authorized a smaller first
  delivery with truthful safe stopping, native inspection and explicit new discovery instead.
Valid implementation facts: existing bounded metadata-only discovery, native selection/progress,
  frozen-manifest manual Preview handoff and earlier safety corrections remain useful. The last
  implementation has not changed; prior test PASS and Task 44.8 review are historical evidence.
Superseded obligations: guaranteed original-request recovery across simultaneous activation/root
  change; every old duplicate/interrupted discovery automatically repaired/resumed; exact cursor
  and unpublished-work continuity through arbitrary races. No claim that these were delivered.
New Contract: current RO-6, required native recovery surfaces, acceptance 27–32 and explicit
  recovery deferral above. Ordinary correctness and all Safety Invariants still apply.
Base Decision: retain Slice 44 and 853973dbbf8289fa2ad40657033e94e870a690e4; it is still the true
  start of this folder-organizing capability within the six-outcome Slice. Status is ACTIVE.
Task Reassessment: Task 44.9 was PLANNED without implementation. After committed amendment
  7e96ebf314e4eab22a72d98028a775f248118138, authorized A planning legally adjusted the same
  Task ID/original Base to this Contract; it remains PLANNED and B implementation review PENDING.
Closure: none; this is neither PASS nor acceptance of the remaining defects.
```

The consolidated audit is preserved under its original Contract. Apply its evidence to the smaller
Contract as follows; a changed recovery expectation is not a fixed implementation:

| Audit group | Current required correction / reduced recovery expectation |
|---|---|
| A44-6 | Atomic equivalent-scope admission and no recent-window dependence remain required. Wrong-root/pin association is still forbidden; proved recovery or truthful unresolved native inspection satisfies the reduced lost-response promise. |
| A44-7 | Real managed include/exclude/depth/stability mapping and root-relative parity remain required. |
| A44-8 | Genuine stability, no idle busy loop/budget exhaustion/starvation remain required; interruption may safely stop instead of precisely resuming observations/cursors. |
| A44-9 / A44-10 | Exact legal long names/paths, durable isolated errors and truthful partial/known-subset review remain required. |
| A44-11 / A44-12 | Correct directory/page accounting and existing main/Trailer attachment semantics remain required. |
| A44-13 | Discovery-command-specific Worker readiness and useful next actions remain required. |

RO-1 through RO-5 and frozen Slice 43 are unchanged. No implementation, new runtime validation,
B review, Closure Reconciliation or next-Slice selection occurs in this Contract decision.

## Prior Closure Packet — after Task 44.9

B's [then-current Closure Packet](docs/reviews/slice-44-closure-packet-20261012.md) follows Task 44.9
PASS and submits the complete Slice range for A. Its report Head is
`5ec0f3fdfa81b28bc12384e65b595a0f917dc562`; executable Head is
`b4a14e0284b66597baf306a95224fc1dabf60033`. Their only difference is `TASK.md`.
The packet and B's subsequent no-active-Task handoff were already present in the working tree
when A started; A preserves them without silently including them in this review checkpoint.
B's COMPLETE assessments are readiness claims, superseded for acceptance by the decision below.
Earlier Closure Packets and reviews remain historical evidence.

## Prior A Final Review — after Task 44.9

```text
Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..5ec0f3fdfa81b28bc12384e65b595a0f917dc562
Decision: FIX REQUIRED
Decision Date: 2026-10-12
Reviewer: A — Slice Owner / Architect / Final Reviewer
Review Scope: complete Slice RO-1 through RO-6 under the checkpointed recovery rescope
P0 Blockers: none found
P1 Blockers:
- A44-14 — RO-6 mixed-selection attachment association, acceptance 27/28:
  with the published attachment policy enabled, selecting Movies freezes one
  primary Film.2001.mkv and associates Film.2001-trailer.mp4. Selecting the same
  directory's empty Other folder plus those two files instead completes with
  two primaries and Finalize creates two independent intent items, including the
  Trailer. This is the native batch selection shape, not an unsupported API scope.
  Required correction: preserve the existing main/attachment semantics for
  explicit files inside mixed discovery as well as walked files; the reviewed
  manifest, primary count and frozen intent must agree without duplicate sidecar
  primary authority. Keep orphan/disabled-policy semantics, confinement and bounds.
```

The [review report](docs/reviews/slice-44-final-review-20261012.md) records reproductions,
source locations, evidence limits and the correction outcome. A44-14 is a confirmed ordinary
correctness defect inside the existing Contract. No Material Contract Change or additional
recovery promise is selected.
Retain the original Base, RO/Surfaces, Safety Invariants, acceptance, bounds and Explicitly Deferred.
The user-approved safe-stop/new-discovery alternative remains sufficient for deferred exceptional
recovery; prior P2 copy/assertion issues do not independently prevent PASS.

### Severity reassessment — A44-15 / 2026-10-12

After the user asked about actual occurrence probability, A checked all four current Storage
adapters. The simulated Executor defect remains reproducible, but its current production
reachability is not demonstrated: Local supplies an inode/ctime fingerprint; OpenList and S3
stat project FILE/DIRECTORY; the production SMB stat also projects FILE/DIRECTORY even though
its listing can report SYMLINK. The original no-fingerprint SYMLINK/OTHER observation came from
an injected Storage port. It proves a defensive-check gap, not a current native incident or a
high-frequency failure. There are no operational statistics or real-adapter reproductions here.

A44-15 is therefore **P2 / NON-BLOCKING**, superseding its original P1 classification in
`58e3334ec71f6c26de1651770263b805bc1e55e3`. A may reassess severity if a concrete current
adapter path/effect is demonstrated; no adapter redesign or extra recovery mechanism is selected
preemptively. A simple exact-type defensive check is a recommendation, not a required correction
Task outcome. Existing exact-type safety requirements are unchanged. The Slice remains
FIX REQUIRED because of A44-14 alone; B must not turn this P2 into an acceptance blocker.

### Validation and evidence

- A independently inspected the complete Base..Head changed-file inventory (153 files), required
  journeys and cross-module behavior, and checked the current B handoff against the executable.
  RO-6 is blocked by A44-14; no additional current P1 is asserted for RO-1 through RO-5.
  B Task PASS is retained as history, not substituted for Slice acceptance.
- Fresh unchanged discovery regressions: PASS, 110 tests, 24.391 test seconds, no skips or
  failures. Both additional negative probes reproduce defects and exit 1 on the required safety/
  association assertion; they are not product PASS. Mixed discovery uses real managed
  configuration, Local Storage, SQLite, authenticated API and the discovery runner, and creates
  zero media effects/execution Tasks. Entry-type probes use the real OrganizerExecutor and an
  explicitly synthetic Storage port; the four recorded effects are fake calls, not real media.
- B's readable fresh full Python (2431 run / 7 skipped / OK), full Web (74 files / 1106 passed),
  native/Docker, wheel, migration and security records were inspected with their provenance and
  disclosed failures. Their green results do not cover or refute the two new cases. A did not
  rerun the remaining full suites, browser/Docker, packaging or migration gates after proving
  A44-14; workflow §6 permits a rejecting review at this point. Required final gates must
  cover the corrected candidate before PASS. Seven dedicated external/endurance profiles remain
  SKIP/UNAVAILABLE; no production-service acceptance is inferred.
- Local raw evidence, exact commands/exit codes/source SHA and initial input hashes are retained
  in .git/validation-evidence/5ec0f3fdfa81b28bc12384e65b595a0f917dc562/a-final-20261012/.
  The mixed-probe's initial HTTP-status harness mistake is disclosed separately; the corrected
  probe expects the documented 202 and changes no product code or existing assertions.
- Governance passed on the submitted ACTIVE/no-active-Task handoff. As in the previous A review,
  the existing guard rejects the workflow-required FIX REQUIRED/no-active-Task transition.
  Its post-checkpoint result is retained explicitly; A does not invent B's Task, hide the review
  status or implement a guard change. This is a known governance inconsistency, not another
  product blocker. B owns the focused correction Task and its legal handoff.
- This checkpoint changes only A review/handoff documentation. Existing TASK changes, B's
  untracked Closure Packet and user images remain preserved and unstaged. There is no closure
  reconciliation, CURRENT delivery promotion, Roadmap/Progress closure, frozen Slice 43 change,
  implementation, next-Slice selection or push.

NEXT ACTION: B PLANS ONE FOCUSED CORRECTION TASK

## Closure Packet — after Task 44.10

B's [current Closure Packet](docs/reviews/slice-44-closure-packet-20261012-task44-10.md) submits
report Head `8be263ea778df08aa374e9433f138a218c1d4af9`, executable
`fa91a231ff58b99a496f608757fccaffedb0f74c`, under committed Contract authority
`78d43114b475c9f82a1bae88654cb1fc2277e391:SLICE.md`. The report successor changes only TASK.md.
A preserves B's completed review/no-active handoff and both pre-existing packets as history in this
closure checkpoint. User PNGs remain outside it. B readiness is supported by A's review below.

## A Final Review

```text
Reviewed Range: 853973dbbf8289fa2ad40657033e94e870a690e4..8be263ea778df08aa374e9433f138a218c1d4af9
Decision: PASS
Decision Date: 2026-10-12
Reviewer: A — Slice Owner / Architect / Final Reviewer
Review Scope: complete Slice RO-1 through RO-6 and all nine Required Surfaces
Contract: user-approved 2026-10-11 recovery rescope; original Base retained
P0 Blockers: none found
P1 Blockers: none found
```

The [final report](docs/reviews/slice-44-final-review-20261012-task44-10.md) records the whole-range
assessment, independent reproduction/negative tests, original readable evidence and artifact/input
identity. A44-14 is resolved: folder and mixed discovery each freeze one main, the exact Preview
associates its Trailer, and separately confirmed Worker execution verifies both reviewed effects
once. Disabled/orphan/other-policy/removed/excluded-owner semantics remain covered. A44-15 retains
its current-adapter P2 reassessment; no concrete native incident was added. Prior P2 wording and
optional assertions do not block acceptance. No Material Contract Change is made at closure.

- A audited the 154-file original Base..Head inventory and cross-module requirements, journeys,
  authority, configuration compatibility, discovery controls/atomic handoff and mutation boundaries.
  The prior whole-range review remains applicable outside the five-file Task 44.10 correction.
- Fresh A original mixed probe and six negative-policy/owner cases PASS with zero media effects.
  Fresh focused Python PASS: 403 tests, 79.429 test seconds. Fresh native browser proof PASS:
  15 stages/four discovery cases plus exact main/Trailer Preview, separate Worker effects and
  replay refusal. Its discovery Worker is driven by the real CLI; resident service proof is Docker.
- Fresh B full Python 2432 run / 7 skips / OK and full Web 74 files / 1106 passed were inspected.
  Original static/build, default E2E 246, Direct Files 10 and Operations 21 are reused only with
  verified unchanged inputs/readable logs. Production Docker discovery/security, old-schema/reopen
  and both-library four-viewport evidence retain their audited identities and limits.
- A independently byte-compared the clean source archive and exact 163-module wheel, and read-only
  hashed both distinct Docker images: exactly 163 current modules/four assets each. Developer's
  stale-module wheel is rejected; only B's clean replacement is accepted. A's first audit used the
  removed Docker source directory and failed equality; corrected installed-module lookup passes.
- Seven dedicated external-service/endurance profiles remain SKIP/UNAVAILABLE. Existing warnings,
  first harness/resource failures, bounded provider uncertainty and exceptional-recovery deferrals
  remain disclosed; no production-service certification, push or release is inferred.

Local A evidence is retained in
.git/validation-evidence/8be263ea778df08aa374e9433f138a218c1d4af9/a-final44-10-20261012/;
B's indexed original evidence remains at the sibling b-review44-10/ directory. The report records
which evidence is fresh, reused, failed or unavailable rather than inferring PASS from totals.

## Closure Reconciliation

Status: **PASS / CLOSED**. All six Required Outcomes and all nine Required Surfaces are complete
within this Contract. The reviewed product range stops at the Implementation Head above; this
checkpoint records facts and history only, with no application/test/provider/configuration change.

- Roadmap marks 44 closed; Progress adds one compact closure-ledger row with original Base/Head and
  deferrals. Accepted prior closures and frozen Slice 43 remain unchanged.
- Requirements/V2 stable IDs and frozen V1 meanings are preserved. Product Experience/Architecture,
  README and configuration guidance describe delivered local analysis, Rules/forms, classification
  compatibility, optional metadata fences, durable Delete, long paths and bounded discovery; runtime
  schema is correctly recorded as 45. Deferred seamless recovery is not promoted to delivery.
- TASK.md is NO ACTIVE IMPLEMENTATION TASK. B's prior review content and both packets are retained;
  role experience receives brief reusable lessons without new scope or lifecycle rules.
- The known FIX REQUIRED/no-active-Task checker conflict was recorded at entry; the factual
  PASS / CLOSED transition is checkpointed before the unchanged HEAD-authoritative governance check.
  Exact manifest/diff, stable IDs, source hashes, private-config exclusion, user PNGs and frozen
  Slice 43 are checked at closure. Evidence/results are local; no push, deployment or next Slice.

NEXT ACTION: A SELECTS THE NEXT LARGE SLICE
