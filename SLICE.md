# Slice 44 — Existing V2 Pages Functional Improvements

This is an A-owned planning Contract for one Slice covering functional improvements across
already implemented pages. The user has selected consistent ordinary file-operation behavior for
ResourceLibrary Files and MediaLibrary Files, reference-aligned organizing-rules presentation, and
classification destinations defined by MediaLibrary plus `path`. Other page contents remain
unspecified; this document does not yet constitute an ACTIVE implementation Contract.

```text
Slice ID: 44
Name: Existing V2 Pages Functional Improvements
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: 853973dbbf8289fa2ad40657033e94e870a690e4
Implementation Head: NOT SET
Contract Revision: 2026-10-07 — A incorporates Rules presentation and classification path correction
Working Branch: slice/44-page-improvements
Risk: High for selected Storage mutations and classification/configuration compatibility
Final Test Level: T4 for selected outcomes; reassess complete boundary before activation
Next Action: A COMPLETES AND ACTIVATES THE CONTRACT AFTER REMAINING SCOPE IS SET
```

## Authority and sequencing

The user explicitly authorized A to freeze Slice 43, preserve its related implementation, and
reserve one new Slice for improvements across multiple previously implemented pages. The user
then specified that Slice contents will be added later. This is the user-authorized priority
exception in [the development workflow](docs/development-workflow.md), not acceptance of Slice 43
or reopening of an accepted historical Slice.

The user subsequently granted A authority to incorporate the organizing-rules workspace visual
correction into this existing Slice 44, then answered yes to including the earlier classification
`library/path` behavior correction as well. RO-2 and RO-3 record that authorization. This selects
one coherent Rules improvement alongside RO-1; it does not activate the Slice, create a Task,
resume frozen Slice 43, or retrospectively change the accepted Slice 37/41 closure records.

This branch starts from `853973dbbf8289fa2ad40657033e94e870a690e4`, the factual closure checkpoint
of accepted Slice 42 and the original Slice 43 Base. It therefore includes the accepted existing
pages and excludes the unaccepted Slice 43 implementation. Only the explicit development-hold /
PLANNED governance support is carried across. No application code has been changed for Slice 44.
The existing product, architecture and permanent safety requirements remain authoritative.

The user subsequently accepted the existing same-Storage Move rules as the ordinary-file-operation
baseline, requested other operations follow those rules, reviewed the operation-by-operation plan,
and explicitly authorized A to incorporate it into Slice 44. This revision selects that outcome;
it is not activation, B Task planning, implementation, or approval of unselected page work.

This is an explicit TARGET change to the current technical fingerprint gate, not a claim that the
baseline code already implements it. The CURRENT description in `docs/architecture.md` remains
factual until implementation and acceptance. Its mandatory-fingerprint behavior for direct Rename,
Delete and cross-Storage source removal must not be promoted back into acceptance criteria for this
selected outcome. This decision does not weaken permanent permission, intent, confinement,
snapshot, ownership, conflict, audit or non-replay invariants, and does not revise media Organize
Preview/source-authority rules or accepted historical closure records.

Applicable guidance includes canonical Storage management/abstraction, direct file commands,
MediaLibrary file management and file-list journeys; UX-001 through UX-010; REQ-STO-001/002/003/006,
REQ-TASK-002/003/005/006/007, REQ-API-002/003 and REQ-SAFE-001 through REQ-SAFE-007/009; and
V2-UX-001/002/003, V2-FILES-001/002/003, V2-AUTH-001/002/003 and V2-SAFE-001. Broader stable targets
such as browser Upload/Download do not expand this selected Slice outcome.

Rules improvements additionally apply V2-RULES-001 through V2-RULES-008, V2-SHELL-001,
REQ-REC-004, REQ-CLASS-001/003/005, REQ-ORG-001/003/004 and the existing configuration, preview,
Task/recovery and unattended-authorization invariants. RO-3 restores the canonical final-path
formula; CURRENT descriptions of the older `library/path` prefix remain factual until delivery
and acceptance. Reference layout does not authorize a different matching algorithm or mutation
authority.

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

An operator can also find, search and maintain the complete organizing-rule graph through the
reference-aligned workspace, and configure a destination using the selected MediaLibrary and one
safe classification path, without a media-library display name becoming an extra directory.

The following direct-file journey belongs to RO-1; Rules presentation and destination journeys
are defined separately under RO-2 and RO-3 so each has its own state, outcome and recovery.

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

Other existing-page improvements may be supplied within this Slice before activation; unspecified
requests are not Required Outcomes. A single operation or page is not automatically another Slice.

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

## Required Outcomes

### RO-1 — Consistent ordinary file maintenance on supported Storage

Deliver the User Goal above on both library pages through shared backend behavior and native Web
actions. The following operation semantics are one business-capability outcome, not a pre-split
Task list. Preserve existing capability and library-kind boundaries; absence of a fingerprint is
not absence of a supported Storage operation.

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
- **Action:** navigate/search/filter/refresh; explicitly Add/copy/Edit; use the existing backend-
  authorized lifecycle and tests/previews; publish with one checked Save.
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

Other existing-page contents remain unselected. A will incorporate them and assess the complete
boundary before activation; B must not invent additional outcomes or field/operation-sized Task
ladders. RO-2 and RO-3 are outcomes, not pre-created implementation Tasks.

## Required Surfaces

- ResourceLibrary Files and MediaLibrary Files: existing entry menus, selection actions, dialogs,
  text editor, live refresh/tree/selection and native operation failure/recovery.
- Their typed authenticated APIs and shared application/domain/Storage/OrganizerExecutor behavior;
  both library kinds and existing API compatibility must use the same rules.
- Existing Task/Worker/Operations: admission, pinned scope, ownership, durable per-item transfer/
  Delete checkpoints and readback/continuation affected by optional fingerprints.
- Existing provider adapters and bounded fake/local-service verification. No new provider or
  unrelated-page redesign is selected.
- Rules workspace: all eight navigation sections, full-width inventories, Add/copy drawers,
  existing Edit routes, purpose-built forms, exact previews and native publication recovery.
- Shared V2 shell/header and control styling only as necessary for Rules composition; preserve
  ResourceLibrary/MediaLibrary Files, Storage, Settings, Operations and existing Automation routes.
- Shared classification/configuration/Planner/API/CLI and existing scheduled/pinned consumers,
  including legacy document/preview/plan/result readback and affected authority recovery.

B determines coherent implementation units and Task Test Levels after A activation; A does not
pre-plan a page-by-page implementation ladder or introduce simultaneous active Tasks here.

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
- Implementation of any Slice 44 feature before A checkpoints its complete ACTIVE Contract.
- Features, pages or redesigns not selected in the eventual user-approved boundary.
- General browser Upload/Download, binary/media editing, unbounded work, cross-library-kind direct
  transfers, transfer Replace, new HardLink/SoftLink UI, universal rollback and new Storage providers.
- Provider-generation/conditional-operation redesign, full-media hashing to prove Rename/Delete
  identity, and universal detection of externally concurrent metadata-indistinguishable replacement.
- Cross-family/global Rules search, a new shell/navigation system, global unrelated-page styling,
  permanent auto-open rule editors, rule-engine redesign, new Metadata Providers, Rules media
  execution, bulk rule import/diff/rollback or V1 retirement.
- Automatic relocation of previously organized media, in-place historical configuration/result/pin
  rewriting, and automatic replay/regrant/republication during classification conversion.

## Slice Acceptance Criteria

The selected RO-1 is accepted only when:

1. Both native library pages and APIs complete the operations above under backend authority; an
   OpenList/SMB-like provider lacking fingerprints can Rename files/directories, confirm and Delete
   bounded files/directories, and finish the source-removal stage of a verified cross-Storage Move.
   Provider capability/permission failures remain distinct from absent fingerprint.
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

Additional-page acceptance is pending selection. RO-1 through RO-3 are not marked complete by
this revision, and these acceptance groups are not a predetermined Task list.

## Final Validation Expectations

RO-1 and RO-3 affect Storage mutation boundaries, core planning, immutable configuration, Worker
recovery and compatibility: the selected Slice final gate is T4. RO-2 normally requires T3 Web/
shared-shell integration evidence; B assigns Task levels from actual risk after activation rather
than assuming all presentation changes are local CSS. This planning change does not stand in for
product validation or create an implementation Task.

Require focused domain/application/Executor/API tests with provider-neutral absent/present/changing
fingerprint fakes; Local temporary directories; bounded OpenList/SMB/S3 semantics through fakes/local
servers; Web interaction and real-Python browser integration on both library kinds; restart,
ownership, historical evidence and partial/unknown effect recovery; applicable full regression,
lint/type/build, packaging and migration gates. Include no-content-read spies, conflict/denied/path/
scope failures, unchanged and changed observations, OpenList multi-stage Move and source-removal
success/partial cases. Production media/services are not test prerequisites. Unavailable isolated
real-service evidence must be reported honestly, never inferred from a fake.

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

Reassess the complete Slice's final validation when remaining page contents are selected. Before
activation, validate and checkpoint this planning Contract/Roadmap relationship with governance
and diff checks; no runtime acceptance is claimed from those checks.

## Closure Packet

Not submitted. No Slice 44 implementation Task exists, and no Required Outcome is marked complete.

## A Final Review

Not performed. This is a PLANNED Contract with RO-1 through RO-3 selected; no Slice acceptance or
closure is claimed.
