# Slice 45 — Scope Pending

```text
Slice ID: 45
Name: Scope Pending
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: a72252091d5d46edf3e2114b994036ae21b08e2e
Implementation Head: NOT SET
Working Branch: slice/45-scope-pending
Development Authorization: NONE — CONTENT PENDING
Risk: NOT ASSIGNED
Final Test Level: NOT ASSIGNED
Next Action: USER DEFINES THE NEW SLICE; A COMPLETES AND CHECKPOINTS ITS CONTRACT
```

## Authority and baseline

On 2026-10-15 the user explicitly authorized this agent to act as A, freeze Automation-page
development and open a new Slice without specifying development content. This is the
[user-authorized scheduling exception](docs/development-workflow.md#user-authorized-development-hold-and-priority-change),
not a final review or acceptance of Slice43. Slice45 is reserved only; PLANNED authorizes neither
B implementation-Task planning nor Developer work.

This isolated branch starts from accepted Slice44 closure
`a72252091d5d46edf3e2114b994036ae21b08e2e` (accepted Implementation Head
`8be263ea778df08aa374e9433f138a218c1d4af9`). It carries no unaccepted Slice43 executable changes.
Existing user-approved stable requirement amendments and explicitly TARGET Automation journey/
architecture documentation are retained; retaining requirements is not claiming implementation.

## Suspended work preservation

- Slice43 original Base: `853973dbbf8289fa2ad40657033e94e870a690e4`.
- Latest executable candidate: `727317168cc62f859f19db1b54b8175cb08449de`.
- Latest Developer report checkpoint: `78ec108d4473e8c140174c1356d0e88a1ae42b34:TASK.md`.
- Exact pre-hold Contract and Task43.3 plan/B decision snapshot:
  `c539429c2c3aaeaab4842b87d3c858e77106fed1:SLICE.md` / `c539429c2c3aaeaab4842b87d3c858e77106fed1:TASK.md`.
- Frozen Contract checkpoint: `ed974e0df8b263f631bfe48b524da461013d8780`.
- Preservation branch: `frozen/slice-43-2026-10-15`.
- Slice43 status: PLANNED; Development Hold: FROZEN BY USER. Task43.1/43.2 are B PASS only;
  Task43.3 remains PLANNED / NOT STARTED and suspended in the exact snapshot.
- Inventory/statistics, consolidated history and actual engine-settings adoption remain incomplete.
  Slice43 has no final validation, Closure Packet or A PASS / CLOSED.

The same agent previously performed B review and is now explicitly authorized by the user for
A's hold/reservation action. No A final review of its own prior B decisions is performed here.
Git history and locally retained evidence remain available; nothing is pushed or claimed remotely
reachable. Resuming Slice43 requires explicit A reactivation and reassessment of intervening changes.

## User Goal

The user selected a complete redesign of the Operations and Tasks page on 2026-10-15 and asked
for a current-state assessment and design proposal first. The user broadly accepts the generated
task-center homepage layout, with the confirmed changes below. Its example data is not runtime or
acceptance authority. The complete Contract remains pending; remaining proposal details are not
implicitly approved implementation scope.

### Confirmed direction — organization-only task creation

On 2026-10-15 the user explicitly directed that new task creation remove Scan and Preview and
retain only actual organization, following the organization-only direction already selected for
Automation (`V2-AUTO-009`). This constrains the future Slice45 Contract as follows:

- The task center's new-task journey offers only organization. Remove independent Scan and Preview
  creation choices and their ordinary task-center entry points, including secondary menus and
  legacy create-page links; renaming or hiding them behind another task-center action is insufficient.
- The user further clarified that standalone Scan itself must be completely retired, not merely
  hidden in V2. Remove its Web pages/actions, API/CLI admission and executable scan-only/repeat-run
  paths, standalone runtime orchestration and code used exclusively by that feature. A diagnostic
  label, legacy entry or compatible executor must not preserve standalone Scan. Keep only code
  actually shared with internal organization or needed to read recorded historical evidence.
- Discovery/scanning, parsing, recognition, metadata lookup, planning and zero-mutation exact Preview
  remain stages of the organization journey. Preview does not grant execution authority; actual
  organization still requires applicable explicit intent and all existing execution safety checks.
- Internal scanning dependencies are not a reason to retain the standalone Scan feature. Any
  organization/Automation stability or recovery path that currently instructs the operator to run
  a separate Scan must instead complete the required observation within its own bounded workflow;
  do not bypass stability checks or leave a recovery action pointing to a retired feature.
- Historical Scan/Preview records retain their recorded identity, outcomes and audit visibility;
  history is not a new-creation or repeat-run entry and must never be relabelled as real organization.
- Existing file-maintenance/transfer results remain distinct recorded work. This creation decision
  does not turn them into new-task choices or silently remove their existing Files-page journeys.
- The current concept image's standalone Scan example does not define the target creation model.
  Layout, naming and detail-page decisions not confirmed below still await a complete Slice Contract.
- Automation's existing organization-only product amendment remains in force. This decision does
  not resume frozen Slice43, import its unaccepted implementation or claim its target is delivered.

Standalone Scan retirement does not remove shared internal discovery, filtering, stability checks,
Rules tests, diagnostic Preview/DryRun capabilities outside the selected organization journey, or
immutable planning/authorization boundaries. General DryRun retirement remains undecided.
Historical Scan data remains read-only evidence; retirement never deletes user media or recorded
results and does not add an executable compatibility path.
The complete surface and acceptance contract must be checkpointed as ACTIVE before B plans a Task.

### Confirmed direction — integrated organization and recovery pages by type

- Remove the independent Preview page/action from the organization-task journey, including its
  recovery journey. Plan computation, exact source/configuration binding, target/conflict/effect
  explanation and applicable explicit execution intent remain within the relevant creation or
  recovery experience; operators do not launch or navigate a separate Preview to continue.
  Reading or saving a decision still cannot authorize media mutation by itself.
- Add sibling recovery-list pages on the same horizontal navigation row as `全部任务`. Each type
  is directly reachable without first selecting a Task; the selected tab displays that type's own
  pending-work list. This is part of the task center's existing navigation area, not a new sidebar
  workspace or merely a task-detail link to a recovery form.
- Each recovery page lists the accessible Tasks that currently have unresolved work of its type,
  across Tasks. A row represents one Task in that type and shows its affected-item count, bounded
  problem summary and contextual action. File/item processing remains independent inside the Task;
  multiple files do not create duplicate Task rows. A Task with different outstanding problem types
  may appear on each applicable page, with the relevant per-type scope preserved.
- Cover the existing Recognition, Metadata candidate/correction, Classification, conflict and
  safely recoverable failure journeys with type-specific lists and appropriate processing forms.
  Proposed tab labels are `识别恢复`, `元数据恢复`, `分类恢复`, `冲突处理`, and `失败恢复`.
  These extend the broadly accepted all/running/attention/ended list composition.
- Queries, pending membership, Task/item counts, filtering and paging are backend authoritative
  over the full authorized population, not browser filtering of the currently loaded Task page.
  Distinguish Task counts from affected-file counts. Viewing, refreshing or switching pages admits
  no work, calls no Metadata Provider and mutates no Storage.
- A processing action retains the exact original Task/item/blocker, legal backend actions and
  current version. Resolving one item updates its durable state and the affected list/counts;
  other items and Tasks remain independent. Preserve the selected type, filters and bounded page
  when returning or reconnecting, and explain stale, denied, unavailable and uncertain outcomes.
- Cross-Task discovery by type is explicitly selected for Slice45; it is no longer covered by
  Slice42's deferred global-review-inbox boundary. This does not authorize cross-Task bulk mutation,
  a new recovery engine, automatic uncertain-effect replay or arbitrary historical reprocessing.
  Uncertain effects retain investigation-only handling and cannot become a generic retry action.

## Required Outcomes and Required Surfaces

Pending the complete redesign Contract, subject to the confirmed creation constraints above.
No implementation Task or executable change is authorized by this planning note.

## Product Experience / UX Constraints

The journey, entry, visible state, actions, success, failures and recovery are pending the selected
goal. Existing AGENTS.md and Product Experience invariants remain mandatory.

## Safety Invariants

All existing architecture, RBAC, audit/redaction, Storage confinement, immutable configuration,
concurrency fencing, explicit destructive intent, zero-mutation analysis and OrganizerExecutor-only
mutation rules remain in force. No behavior, permission, migration or runtime change is authorized.
Preserve unrelated user files, reference images and private ignored configuration.

## Explicitly Deferred

All unspecified development is outside this placeholder. Suspended Slice43 work is not transferred,
waived or counted as delivered, and is not silently included in Slice45.

## Slice Acceptance Criteria

Pending definition after the user supplies the goal and scope; no product acceptance is claimed.

## Final Validation Expectations

Pending actual scope/risk assessment. Governance, document consistency, whitespace and exact
baseline/private-file checks validate this reservation only; they are not product validation.

## Closure Packet

Not submitted. No implementation Task exists.

## A Final Review

Not performed. This planning reservation is not a product review or closure.
