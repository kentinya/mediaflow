# Slice 41 — V2 Organizing Rules Workspace

This A-owned Contract delivers one complete operator journey: understand, edit, test and publish the
rule chain that turns a discovered source into an explained recognition identity and downstream
metadata, naming, classification and organize-policy selection, without raw JSON authoring or V1 UI
fallback for the ordinary journey.

```text
Slice ID: 41
Name: V2 Organizing Rules Workspace
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 8a6a15597bab2fd10673db84d73a5bbc1d455ad8
Implementation Head: NOT SET
Contract Revision: 2026-09-28 — A selection authorized by the user
Risk: High
Final Test Level: T4
Next Action: B PLANS THE FIRST COHERENT IMPLEMENTATION TASK AFTER THIS CONTRACT CHECKPOINT
```

## Authority and sequencing

The user explicitly granted A authority to turn the reviewed rule-workspace proposal into the next
Slice and update the related product/requirements/architecture documents. Slice 40 is `PASS /
CLOSED`; its Base, Implementation Head and A Final Review remain immutable history. This Slice starts
from the repository `HEAD` immediately after that closure and does not reopen Slice 22.4, 22.5, 22.6,
37 or 40.

A owns this Contract, stable V2 requirement additions, TARGET product journey and TARGET
architecture. B owns coherent Task sizing after the Contract and Roadmap are committed. No
implementation Task is created by this A activation; root `TASK.md` remains a no-active-Task notice.
B and Developer may update only factual Implementation Head, Task/Closure Packet and validation
evidence explicitly delegated below. They may not change the Base, outcomes, reference
interpretation, acceptance criteria or deferrals. Follow `docs/development-workflow.md`.

## User Goal

An administrator opens `整理规则`, understands the complete active processing-policy graph, creates
or resumes one successor Draft, edits the required rule and policy objects with purpose-built forms,
runs bounded zero-mutation tests/previews, and explicitly publishes one checked immutable Active
revision. They can see why a sample matches a RecognitionType, which downstream policies that type
selects, what name and destination would result, which organize authority would apply, why
publication is blocked, and the exact safe action that continues the journey.

The ordinary operator never has to hand-edit whole-document JSON, move between V1 and V2 for these
objects, copy revision IDs/digests, or treat implementation tokens as workflow steps. Advanced JSON
and V1 remain support/compatibility surfaces during migration, not the completion path promised here.

## Reference interpretation

The following user-supplied images are the business-logic and visual-style references for this
Slice and must remain unchanged:

- `docs/pics/策略绑定.png`
- `docs/pics/识别类型.png`
- `docs/pics/识别规则.png`
- `docs/pics/命名规则.png`
- `docs/pics/分类规则.png`

They establish the shared light-shell context, `整理规则` information architecture, horizontal
rule-family navigation, list/detail editor composition, restrained white/light-gray surfaces, blue
primary actions, green enabled state, searchable inventories and clear form hierarchy. They do not
define actual IDs, names, descriptions, counts, priorities, scores, conditions, templates, media
types, target paths, status values or sample data. They are not pixel-identical screenshot fixtures.

Where a reference conflicts with current domain semantics, stable requirements or safety, the
domain and safety rules win. In particular:

- `保存` saves the current object into the labelled successor Draft; it does not silently make that
  object Active. Publication is a separate explicit whole-revision action, which may compose
  validation and checked activation in one operator command.
- Recognition rules are resolved using the production priority/score/ambiguity/`stopOnMatch`
  semantics. Visual row order or drag handles must not imply a different first-match algorithm.
- One enabled RecognitionType policy binding is allowed per RecognitionType. Binding priority is not
  presented as a competing-winner mechanism.
- Classification output is a `MediaLibrary` identity plus a safe relative path. A combined label such
  as `movies/外国电影` is presentation only and cannot replace those separate authorities.
- Movie and TV naming use their actual distinct template sets. A Movie-only example does not narrow
  the supported NamingPolicy model.

Metadata Policy and Organize Policy have no supplied page image. They must use the same workspace
layout, interaction language and design system because a type binding is not a complete usable graph
without them. Their fields and behavior come from the existing domain and stable requirements, not
invented reference data.

## Baseline and applicable requirements

At Base, the Python domain/application/API already provide:

- managed whole-document Draft, Validated, Active and Superseded revisions with optimistic
  concurrency, audit, reference protection, redaction and checked atomic activation;
- generic managed object CRUD/copy/enable/disable/delete for RecognitionType, RecognitionRule,
  RecognitionTypePolicy, MetadataPolicy, NamingPolicy, ClassificationPolicy and OrganizePolicy;
- production RecognitionRuleEngine and RecognitionTypePolicyResolver semantics, including the
  RecognitionType-C identity invariant;
- exact-revision Recognition Strategy Test, MetadataPolicy testing/candidate behavior, Naming
  Preview, Classification Preview, Organize authority explanation and destination precheck;
- legal empty-business Active configuration and incremental capability readiness from Slice 40;
- the shared V2 shell, typed API boundary, memory-only principal authentication and `/api/v1/*`
  Python authority.

The V1 configuration UI exposes forms-first generic management, but V2 `/configuration` owns
Settings rather than this rule workspace and V2 has no dedicated rule-management route. The main
implementation gap is therefore a complete typed V2 journey and any narrowly necessary backend
projection/command composition—not a new rule engine, second configuration authority or processing
pipeline.

Applicable stable requirements include `REQ-GEN-001` through `REQ-GEN-004`, `UX-001` through
`UX-010`, `REQ-REC-*`, `REQ-META-*`, `REQ-NAME-*`, `REQ-CLASS-*`, applicable `REQ-ORG-*`,
`REQ-CONFIG-*`, `REQ-WEB-*`, `REQ-API-*`, `REQ-SAFE-*`, all applicable `V2-UX-*`, `V2-WEB-001`,
`V2-CONFIG-*`, `V2-AUTH-*`, `V2-MIG-*`, `V2-SAFE-001`, `V2-SHELL-001` and the new
`V2-RULES-*` requirements activated with this Contract.

## Operator journey and Required Surfaces

| Stage | Required experience |
|---|---|
| Goal | Safely maintain and understand the complete recognition-to-policy rule graph consumed by runtime. |
| Entry | Choose `整理规则` in the shared V2 shell or open `/ui-v2/rules` through normal authenticated deep-link continuation. Settings capability/readiness states may link here; a read-only visit creates no Draft or work. |
| Visible state | Show exact Active identity and capability readiness separately from an existing/unsaved successor Draft. Within the workspace expose Overview, Type Bindings, Recognition Types, Recognition Rules, Metadata Policies, Naming Policies, Classification Policies and Organize Policies. Lists show stable identity, bounded description/summary, enabled state, reference/impact state and Draft changes without pretending Draft is Active. |
| Action | Explicitly begin/resume a successor Draft; add, copy, edit, enable/disable or reference-safe delete objects; run exact-Draft tests/previews; save form changes to Draft; validate and explicitly publish the complete candidate. |
| Success | One immutable checked revision becomes actual Active runtime authority. Lists and readiness refetch from it; previews and explanations identify the exact revision tested. Activation alone creates no scan, Task, Job, schedule occurrence, Provider call or Storage mutation. |
| Failure | Invalid field/operator/template/path, duplicate identity, dangling/disabled reference, duplicate enabled type binding, unsafe regex/path, missing secret, Provider/test failure, stale Draft/Active, failed evidence, activation/runtime-load or persistence failure identifies the object/stage, durable state and safe next action. Previous Active remains in use. |
| Recovery | Preserve the Draft and correctable form input; refresh stale authority before reapplying intended changes; follow reference impact to repoint dependents; rerun only the explicit test/check whose evidence is missing or stale; verify actual Active after an unknown publication outcome before retry. |

Required product surfaces:

- one native V2 `/ui-v2/rules` route inside the shared shell and one discoverable `整理规则`
  navigation destination;
- desktop list/editor composition derived from the references, plus accessible narrow layouts that
  use stacked views or a drawer without losing list context and unsaved-state protection;
- typed frontend entities/query/mutation boundaries for the exact managed revision and all eight
  rule/policy families;
- shared authenticated API/application behavior for inventory/detail, Draft creation/resume, object
  lifecycle, reference impact, previews/tests, validation and checked activation;
- Settings/capability handoff for empty/unconfigured state and safe return to the originating rules
  location;
- V1 compatibility without making V1 or whole-document JSON mandatory for the completed journey.

## Required Outcomes

### RO-1 — Reference-aligned V2 organizing-rules workspace

- `/ui-v2/rules` uses the existing light AppShell and adds one active `整理规则` destination without
  creating a second shell or navigation authority.
- The page provides one coherent workspace with Overview, Type Bindings, Recognition Types,
  Recognition Rules, Metadata Policies, Naming Policies, Classification Policies and Organize
  Policies. Tabs/routes are refresh-safe and deep-linkable where useful.
- The supplied images govern structure and style only. Production lists use actual Active/Draft
  objects, actual references and actual readiness; no example ID, count, condition or target is
  hard-coded as product truth or acceptance data.
- Wide layout uses searchable list plus selected-object editor; narrow/keyboard operation remains
  complete. Editors default closed or safely unselected when no object is chosen and do not discard
  unsaved input on search, filter, navigation, reconnect or stale-authority recovery without warning.
- Overview explains the processing relationship rather than merely counting rows:

  ```text
  RecognitionRule -> RecognitionType -> RecognitionTypePolicy
                  -> MetadataPolicy / NamingPolicy / ClassificationPolicy / OrganizePolicy
  ```

  It also shows capability gaps and links to the affected family without presenting a Draft as
  runtime-consumed.

### RO-2 — Exact Active/successor-Draft lifecycle with low-friction publication

- Read, search, filter, select and preview of current state have zero configuration side effects.
  A successor Draft is created only by explicit edit intent and an existing successor is resumed.
- Every object editor saves through the shared managed configuration authority with exact revision
  version fencing and backend RBAC. ID is immutable on edit; create/copy uses a new stable ID.
- `保存草稿` changes only the labelled Draft. A whole-workspace `校验并启用` or equivalent explicit
  action may compose validation and checked activation but must show that it publishes all Draft
  changes, not only the selected editor.
- Active/Draft identities, dirty/saved state, test/evidence staleness and publication result are
  visible without requiring the operator to enter raw version/digest values.
- Known failure preserves previous Active and correctable Draft/input. Unknown outcomes are verified
  from current managed state and never automatically resubmitted. Audit records actor, action,
  object, bounded before/after and result without secrets.
- Empty Active is a normal starting point. Valid independent objects may publish incrementally;
  incomplete declared references and broken enabled graphs may not be relabelled as merely
  unconfigured.

### RO-3 — RecognitionType and RecognitionRule management with truthful resolution

- RecognitionType supports stable ID, name, bounded description and enabled state. Lists show both
  incoming rule references and type-policy binding state. Disable/delete explains affected rules,
  bindings and command readiness; referenced deletion is blocked.
- RecognitionRule supports stable ID/name/description, output RecognitionType, enabled state,
  integer priority, bounded non-negative score and `stopOnMatch`.
- The form provides a typed nested condition builder for the production `AtomicCondition` and
  `LogicalCondition` model. Field/operator choices are compatible; collection/numeric/string values
  use appropriate controls; unsafe/oversized regex is rejected by backend validation. An Advanced
  JSON representation may exist as an optional bounded support view, not the ordinary editor.
- Rule lists and explanations reflect actual evaluation: rules are considered by priority and
  deterministic tie order, matches for a type contribute score, `stopOnMatch` stops evaluation, and
  equal winning priority/score across types is ambiguous rather than silently selected.
- Exact-Draft Strategy Test accepts a bounded synthetic path/context and returns parse evidence,
  matched rules, expected/actual condition evidence, alternatives, reasons, warnings and resulting
  RecognitionType. Entry or save alone performs no scan, Provider call, Task/Job creation or
  Storage mutation.

### RO-4 — RecognitionTypePolicy binding preserves independent identity

- Type Bindings manage the mapping from one RecognitionType to exactly one MetadataPolicy,
  NamingPolicy, ClassificationPolicy and OrganizePolicy, plus name/enabled state. Ordinary UI does
  not present binding priority as a winner-selection mechanism.
- Selectors show actual available objects, stable IDs, enabled state and relevant compatibility;
  absent/disabled references are visible blockers rather than silently substituted defaults.
- More than one enabled binding for a RecognitionType is invalid. A type without an enabled binding
  is unconfigured and cannot enter the downstream processing chain.
- Downstream reuse never rewrites RecognitionType. The required regression is explicit:

  ```text
  RecognitionType C
    -> MetadataPolicy C
    -> NamingPolicy A
    -> ClassificationPolicy A
    -> OrganizePolicy A
  result: RecognitionType == C
  ```

- Binding detail and Strategy Test explanations show the selected policy IDs and the preserved
  recognition identity. Editing bindings starts no media work and grants no execution authority.

### RO-5 — Complete typed downstream policy editors

- Metadata Policy exposes existing provider reference, media/query type, language/region, confidence
  thresholds, score gap, timeout/retry and bounded request/candidate settings, enabled state and
  current secret readiness without ever returning a credential value. Provider switching or adding
  a new provider implementation is not introduced.
- Naming Policy exposes stable ID/name/description/enabled state, media-type mode, missing-variable
  behavior, maximum component length and the actual Movie/TV template families. Supported variables
  and numeric formatting are discoverable; unknown variables, path separators, absolute paths,
  unsafe components and unsupported formatting fail clearly.
- Classification Policy exposes stable ID/name/description/enabled/priority and ordered rules.
  Rules use the current supported conditions—media type, genres, countries, languages, year bounds
  and keywords—and a separate MediaLibrary ID plus safe relative destination path. Rule order is
  explained as priority then stable ID; an unmatched item remains unclassified.
- Organize Policy exposes the actual Move/Copy/HardLink/SoftLink operation, conflict strategy,
  attachment handling, duplicate detection, rollback and source-directory cleanup settings.
  Unsupported fallback is never implied. Overwrite/delete/cleanup consequences receive explicit
  risk presentation, but configuring a policy still does not itself grant a Task or Automation
  execution authority.
- Copy creates a new disabled Draft object where the underlying object kind supports enable state.
  Enable/disable and delete expose exact reference impact; deletion is reference-protected and
  never deletes media, Storage contents, historical snapshots, results or audit records.

### RO-6 — Exact-revision previews and bounded explanations

- Naming Preview uses an explicit bounded sample and the exact Draft revision. It returns selected
  media type, rendered directory segments/filename, variables, missing-variable warnings and
  sanitization/truncation changes. It never renames a file.
- Classification Preview uses an explicit bounded sample and exact Draft revision. It returns the
  matched rule/evidence, preserved RecognitionType, MediaLibrary ID and safe relative path. It never
  creates directories or moves files.
- Metadata Policy test is explicit. Offline validation performs no Provider call; an explicitly
  selected live test may call only the configured provider through the existing abstraction, applies
  timeout/retry/rate-limit/redaction, creates no Task and performs no Storage mutation. Candidate
  correction remains the existing review/correction journey and is not reimplemented here.
- Organize authority explanation and optional whole-chain Preview show operation, conflict/risk,
  required capabilities, source/target composition and why execution would be allowed or blocked.
  They perform zero Storage mutation, issue no execution authority and do not claim that a Preview
  result remains current after the Draft changes.
- Test results are bound to revision/version/digest internally, become visibly stale after relevant
  edits, and expose bounded secret-free reasons plus a meaningful next action. One failed sample does
  not overwrite another sample's result.

### RO-7 — Checked activation, readiness and cross-surface consistency

- Whole-document validation covers field schemas, uniqueness, condition/template/path safety,
  enabled references, one-binding-per-type and every populated graph. Applicable exact-revision
  Storage/strategy/destination/provider evidence follows the shared Slice 40 applicability decision;
  unrelated empty families do not require fabricated checks.
- Checked activation atomically publishes only the exact validated candidate. It refreshes runtime
  capability state but starts no scan, Task, Job, scheduled occurrence, notification or media
  mutation. Failed validation/evidence/runtime binding keeps prior Active.
- Files manual Organize, Automation, CLI and API resolve policies from the same immutable Active
  runtime and retain the same RecognitionType identity. The V2 workspace does not create a frontend
  policy resolver or a second cache presented as Active.
- Existing generic `/api/v1/configuration/*` behavior remains authoritative. Narrow new projection or
  composition endpoints are allowed when they reduce browser protocol leakage, but they must reuse
  the same application service, permission, validation, audit and concurrency boundaries.
- Settings truthfully reports readiness after publication and links back to the affected rule family.
  V1 configuration remains usable during migration, with no silent schema or semantic divergence.

### RO-8 — Actionable empty, error and recovery states

- Empty Active shows an intentional onboarding sequence and dependency guidance without generating
  default business objects. The UI helps the administrator add independent objects in a legal order
  but does not automate human choices such as media identity, naming convention, destination or
  operation policy.
- No selection, empty search, no match, disabled object, unavailable provider/secret, blocked
  reference, stale Draft, malformed API response, denied permission, failed test, invalid graph,
  activation conflict and unavailable runtime each have distinct bounded states.
- Recovery controls describe what is durable, whether Active changed, which input remains, what is
  safe to repeat and the explicit next action. Generic `Retry` without that information is
  insufficient.
- Batch-like rule/policy test samples and reference impact retain independent outcomes. A failing
  object/sample cannot hide or overwrite successful siblings.

## Safety and correctness invariants

1. RecognitionRule determines only RecognitionType. Recognition never calls Metadata, names,
   classifies, plans, mutates Storage or determines a final media path.
2. RecognitionType identity is immutable across Metadata/Naming/Classification/Organize policy
   reuse. Type C remains C when it uses policies named or originally designed for type A.
3. Metadata lookup, Naming, Classification and Planner remain zero-mutation analysis boundaries.
   Preview/Test never issues execution authority.
4. Only OrganizerExecutor may mutate Storage. This workspace performs no Storage mutation and adds
   no alternate executor, direct filesystem call or provider mutation path.
5. Page entry, read, search, filter, selection, navigation, refresh and Draft inspection create no
   Draft, Provider call, Task, Job, schedule occurrence or notification. Live provider tests require
   an explicit test action.
6. Active means the exact immutable revision consumed by runtime. Draft, saved object, validated
   candidate, preview result or stale process projection may never be labelled Active.
7. Validation and checked activation are backend-authoritative, RBAC-protected, optimistic-concurrent,
   audited, redacted and fail closed. Previous Active remains authoritative on known failure.
8. Secrets remain deployment-owned references/readiness. API, Web, audit, tests, logs and errors
   never expose secret values, authorization headers, cookies or provider credentials.
9. Classification selects a configured MediaLibrary and safe relative path. Naming returns safe
   relative components. Neither can escape Storage/MediaLibrary confinement.
10. Overwrite, Delete and cleanup remain independently permissioned/high-risk effects. Policy
    configuration does not silently grant manual or scheduled execution authority.
11. HardLink/SoftLink do not fall back to Copy/Move. Unsupported capabilities remain explicit.
12. No FFmpeg/FFprobe dependency, media-stream inspection or technical-tag verification is added.
13. Existing admitted work retains its pinned immutable configuration. New activation cannot rewrite
    queued/running Task, Job, Preview, Result or historical explanation identity.
14. API and Web use the same application behavior and safety. Frontend state never becomes policy,
    Active configuration, permission or execution authority.

## Explicitly Deferred / Excluded

- New Metadata Providers, runtime Provider switching, arbitrary Provider plugins or a new secret
  store. This Slice manages existing MetadataPolicy references and current provider semantics.
- Metadata candidate review/correction redesign, Review/Recovery workspace migration, historical
  Result editing or automatic recognition correction.
- Starting Scan, Organize, file operations, scheduled execution or notification delivery from this
  workspace. Tests/previews are analysis-only; execution remains in Operations/Files/Automation.
- New recognition fields/operators, a user-supplied programming/expression language, AI-generated
  rules, automatic policy generation or a change to the current priority/score/ambiguity semantics.
- New naming variables, new classification condition domains, filesystem-derived stream metadata,
  FFmpeg/FFprobe or arbitrary destination expressions.
- Bulk multi-object editing/import, visual graph authoring, object/version diff, rollback/cherry-pick,
  cross-deployment merge or replacement of Settings package exchange.
- V1 `/ui` retirement, authentication/session redesign, OIDC, a new API version, distributed config
  service or frontend-owned business authority.
- Pixel-identical reproduction of the five reference images or acceptance of their example data as
  production fixtures. Controlled visual comparison is diagnostic only.
- Editing, recompressing or regenerating the five supplied images. They are consumed unchanged as
  reference assets.
- Unrelated Storage, Files, MediaLibrary, Dashboard, Operations, Automation, Notifications or
  deployment redesign.

## Slice Acceptance Criteria

| ID | Acceptance |
|---|---|
| AC-1 | `/ui-v2/rules` is a discoverable, authenticated shared-shell workspace with all eight required sections, reference-aligned list/editor composition and complete narrow/keyboard operation. Reference example data is not hard-coded. |
| AC-2 | Active, successor Draft, unsaved input, saved Draft, validation/evidence state and publication outcome remain visibly distinct. Reads create no Draft/work; explicit editing resumes or creates one successor. |
| AC-3 | All seven managed object families in scope support typed create/copy/edit/enable-disable where applicable/reference-safe delete using exact-version backend authority, audit and actionable stale/reference recovery. |
| AC-4 | RecognitionType and nested RecognitionRule editing enforce actual field/operator/value semantics, priority/score/stop behavior, ambiguity evidence and safe regex bounds. |
| AC-5 | Type Bindings enforce one enabled mapping per RecognitionType, validate all four downstream references and visibly preserve RecognitionType C through A naming/classification/organize reuse. |
| AC-6 | Metadata, Naming, Classification and Organize editors expose current domain fields without inventing provider switching, fallback or execution authority. Movie/TV templates and MediaLibrary-plus-relative-path output are represented truthfully. |
| AC-7 | Exact-Draft Recognition Strategy Test, Metadata test, Naming Preview, Classification Preview and Organize authority/whole-chain explanation are bounded, secret-free and zero Storage mutation. Results become stale after relevant edits. |
| AC-8 | Whole-workspace validation and checked activation use the shared managed lifecycle/applicability gates, atomically publish the exact candidate, start no work and preserve previous Active/correctable Draft on failure. |
| AC-9 | Empty and partially configured Active states provide legal onboarding/readiness without generated defaults; malformed or broken declared graphs fail rather than masquerading as unconfigured. |
| AC-10 | V2 Web, V1 compatibility, API, CLI, Files manual Organize and Automation consume the same Active policy semantics. No frontend resolver/cache or schema divergence becomes authority. |
| AC-11 | Permission, malformed response, reference conflict, stale revision, missing secret/provider, invalid test, activation failure and unknown outcome each expose durable state and safe recovery without secret leakage or automatic replay. |
| AC-12 | Existing rule/configuration regressions, full product tests, build/static analysis, security/redaction, FFmpeg/FFprobe exclusion and unchanged reference-image checks pass at the assigned Slice-final level. |

## Final validation expectations

This Slice crosses Active configuration, RBAC, provider access, core recognition/policy semantics,
API/Web parity and runtime binding, so implementation Tasks touching those boundaries require T4 or
the strongest lower level B can justify for a genuinely isolated unit. Slice Final normally includes:

- focused Python suites for recognition, policy mapping, configuration objects, metadata/naming/
  classification/organize configuration, exact strategy tests, snapshot applicability, audit,
  reference protection and activation conflict/recovery;
- explicit RegressionType-C matrices through direct resolver, exact-Draft Strategy Test, published
  runtime, Files manual Organize Preview and Automation admission where applicable;
- focused Web typed-model/API/query/component tests for every family, Active/Draft state, unsaved
  protection, accessibility, responsive layout, malformed/401/403/stale/reference/error recovery and
  no retry/resubmit on refresh;
- browser journeys for empty Active onboarding, multi-object Draft editing, tests/previews,
  validation failure recovery, successful activation and post-activation policy consumption;
- full Python and Web regressions, frontend typecheck/lint/format/build, Python format/lint/compile,
  `scripts/check_governance.py`, `git diff --check`, Base..Head manifest/scope audit and package tests;
- instrumentation proving read/navigation has no Draft/Task/Job/Provider/Storage side effect; explicit
  live Provider tests are bounded and redact failures; all previews/tests have zero Storage mutation;
- audit that no FFmpeg/FFprobe dependency, raw secret, private configuration, example-reference data
  authority or alternate Storage mutator entered the range;
- checksum or exact-byte comparison showing the five supplied reference images were not modified.

External/provider tests that cannot run must be reported with the actual reason and may not be
converted into PASS. Production TMDB, SMB, OpenList, S3/R2 or user media are not required for unit
tests; use fakes, mocks, temporary roots and controlled local services.

## Delegated factual updates and stop rule

After this Contract, Roadmap and stable TARGET documents are checkpointed, B may replace the
no-active notice with the first coherent Task. B may update only factual Task/Implementation Head,
Closure Packet and test-result sections. B must not create a Task per tab, field, button, assertion
or screenshot detail; normal sizing remains roughly 3–7 major coherent Tasks for the whole Slice.

After every Task PASS, B reevaluates RO-1 through RO-8. Once all outcomes and acceptance criteria are
satisfied, B runs Slice Final, writes one Closure Packet, sets `READY FOR A REVIEW` and stops. Test
polish, optional visual tuning, extra sample data or P2 cleanup is not a reason for another Task.

## Closure Packet

Not yet prepared. B owns this section after all Required Outcomes are satisfied.

## A Final Review

Not yet conducted. A will review the complete immutable range
`8a6a15597bab2fd10673db84d73a5bbc1d455ad8..Implementation Head`, Required Outcomes, operator
journey, reference interpretation, failures/recovery, architecture/safety and Slice-final evidence
before deciding `PASS`, `FIX REQUIRED` or `PARTIAL / RESCOPE`.
