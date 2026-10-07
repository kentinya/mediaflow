# Slice 44 — Existing V2 Pages Functional Improvements

This is an A-owned planning Contract for one Slice covering functional improvements across
already implemented pages. The user has selected consistent ordinary file-operation behavior for
ResourceLibrary Files and MediaLibrary Files as its first outcome. Other page contents remain
unspecified; this document does not yet constitute an ACTIVE implementation Contract.

```text
Slice ID: 44
Name: Existing V2 Pages Functional Improvements
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: 853973dbbf8289fa2ad40657033e94e870a690e4
Implementation Head: NOT SET
Contract Revision: 2026-10-07 — A incorporates user-authorized ordinary file-operation consistency
Working Branch: slice/44-page-improvements
Risk: High for selected Storage mutation/destructive outcome; other page contents pending
Final Test Level: T4 for selected outcome; reassess complete boundary before activation
Next Action: A COMPLETES AND ACTIVATES THE CONTRACT AFTER REMAINING SCOPE IS SET
```

## Authority and sequencing

The user explicitly authorized A to freeze Slice 43, preserve its related implementation, and
reserve one new Slice for improvements across multiple previously implemented pages. The user
then specified that Slice contents will be added later. This is the user-authorized priority
exception in [the development workflow](docs/development-workflow.md), not acceptance of Slice 43
or reopening of an accepted historical Slice.

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

Other existing-page contents remain unselected. A will incorporate them and assess the complete
boundary before activation; B must not invent additional outcomes or operation-sized Task ladders.

## Required Surfaces

- ResourceLibrary Files and MediaLibrary Files: existing entry menus, selection actions, dialogs,
  text editor, live refresh/tree/selection and native operation failure/recovery.
- Their typed authenticated APIs and shared application/domain/Storage/OrganizerExecutor behavior;
  both library kinds and existing API compatibility must use the same rules.
- Existing Task/Worker/Operations: admission, pinned scope, ownership, durable per-item transfer/
  Delete checkpoints and readback/continuation affected by optional fingerprints.
- Existing provider adapters and bounded fake/local-service verification. No new provider or global
  page redesign is selected. B determines coherent implementation units after A activation.

## Safety Invariants and UX Constraints

All permanent AGENTS.md, product-experience and applicable stable requirement invariants remain
mandatory. Scope is not permission to weaken RBAC, explicit mutation intent, no silent overwrite/
delete, Storage confinement, immutable runtime snapshots, zero-mutation analysis, per-item durable
outcomes/recovery, no uncertain-effect replay or OrganizerExecutor-only Storage mutation.

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

## Explicitly Deferred

- Slice 43 implementation and its outstanding fix loop while the development hold is in effect.
- Implementation of any Slice 44 feature before A checkpoints its complete ACTIVE Contract.
- Features, pages or redesigns not selected in the eventual user-approved boundary.
- General browser Upload/Download, binary/media editing, unbounded work, cross-library-kind direct
  transfers, transfer Replace, new HardLink/SoftLink UI, universal rollback and new Storage providers.
- Provider-generation/conditional-operation redesign, full-media hashing to prove Rename/Delete
  identity, and universal detection of externally concurrent metadata-indistinguishable replacement.

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

Additional-page acceptance is pending selection. No outcome is marked complete by this revision.

## Final Validation Expectations

RO-1 affects Storage mutations, destruction, Worker recovery and compatibility: its final gate is
T4. B assigns implementation Task levels from the actual risk after activation; this planning change
does not stand in for product validation or create an implementation Task.

Require focused domain/application/Executor/API tests with provider-neutral absent/present/changing
fingerprint fakes; Local temporary directories; bounded OpenList/SMB/S3 semantics through fakes/local
servers; Web interaction and real-Python browser integration on both library kinds; restart,
ownership, historical evidence and partial/unknown effect recovery; applicable full regression,
lint/type/build, packaging and migration gates. Include no-content-read spies, conflict/denied/path/
scope failures, unchanged and changed observations, OpenList multi-stage Move and source-removal
success/partial cases. Production media/services are not test prerequisites. Unavailable isolated
real-service evidence must be reported honestly, never inferred from a fake.

Reassess the complete Slice's final validation when remaining page contents are selected. Before
activation, validate and checkpoint this planning Contract/Roadmap relationship with governance
and diff checks; no runtime acceptance is claimed from those checks.

## Closure Packet

Not submitted. No Slice 44 implementation Task exists, and no Required Outcome is marked complete.

## A Final Review

Not performed. This is a PLANNED Contract with RO-1 selected; no Slice acceptance or closure is claimed.
