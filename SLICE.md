# Slice 41 — V2 Organizing Rules Workspace

This A-owned Contract delivers one complete operator journey: understand, edit, test and publish the
rule chain that turns a discovered source into an explained recognition identity and downstream
metadata, naming, classification and organize-policy selection, without raw JSON authoring or V1 UI
fallback for the ordinary journey.

```text
Slice ID: 41
Name: V2 Organizing Rules Workspace
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 8a6a15597bab2fd10673db84d73a5bbc1d455ad8
Implementation Head: 8433319168272ecf7ccde017afc36525e8c62ea0
Contract Revision: 2026-09-28 — A default-page/create-drawer correction authorized by the user
Risk: High
Final Test Level: T4
Next Action: A SELECTS THE NEXT LARGE SLICE
```

## Authority and sequencing

The user explicitly granted A authority to turn the reviewed rule-workspace proposal into the next
Slice and update the related product/requirements/architecture documents. Slice 40 is `PASS /
CLOSED`; its Base, Implementation Head and A Final Review remain immutable history. This Slice starts
from the repository `HEAD` immediately after that closure and does not reopen Slice 22.4, 22.5, 22.6,
37 or 40.

The user's subsequent direction—`点击保存后自动完成验证和激活`—materially replaces the initial
two-step Draft-save/publication interaction. The managed Draft/Validated states remain backend
lifecycle and recovery mechanisms, but the ordinary rule editor exposes one Save intent that
automatically validates and activates on success.

The user's latest direction also replaces the reference screenshots' always-open split editor as
the default state: each rule-family route opens as one complete full-width inventory page with no
selected object, form or drawer. Only an explicit `添加xx` action opens the create drawer. Row
selection, search, filtering, tab navigation and refresh never open it. Existing-object Edit remains
an explicit action and uses a dedicated full-page edit state/route rather than the Add drawer.

A owns this Contract, stable V2 requirement additions, TARGET product journey and TARGET
architecture. B owns coherent Task sizing after the Contract and Roadmap are committed. No
implementation Task is created by this A activation; root `TASK.md` remains a no-active-Task notice.
B and Developer may update only factual Implementation Head, Task/Closure Packet and validation
evidence explicitly delegated below. They may not change the Base, outcomes, reference
interpretation, acceptance criteria or deferrals. Follow `docs/development-workflow.md`.

## User Goal

An administrator opens `整理规则`, understands the complete active processing-policy graph, edits
the required rule and policy objects with purpose-built forms, runs bounded zero-mutation
tests/previews, and clicks `保存`. The backend then composes a successor, automatically validates
it, runs applicable checks and atomically activates the exact immutable revision. They can see why a
sample matches a RecognitionType, which downstream policies that type selects, what name and
destination would result, which organize authority would apply, why Save was blocked, and the exact
safe action that continues the journey.

The ordinary operator never has to hand-edit whole-document JSON, move between V1 and V2 for these
objects, copy revision IDs/digests, or treat implementation tokens as workflow steps. Advanced JSON
and V1 remain support/compatibility surfaces during migration, not the completion path promised here.

## Reference interpretation

The following user-supplied images are the business-logic and visual-style references for this
Slice and must remain unchanged:

- `docs/pics/策略绑定.png`
- `docs/pics/识别类型.png`
- `docs/pics/识别规则.png`
- `docs/pics/元数据类型.png`
- `docs/pics/命名规则.png`
- `docs/pics/分类规则.png`

They establish the shared light-shell context, `整理规则` information architecture, horizontal
rule-family navigation, restrained white/light-gray surfaces, blue primary actions, green enabled
state, searchable inventories and clear form hierarchy. The screenshots' right-side editor panels
describe field grouping and form style only; they are not the page-load state. They do not define
actual IDs, names, descriptions, counts, priorities, scores, conditions, templates, media types,
target paths, status values or sample data. They are not pixel-identical screenshot fixtures.

Where a reference conflicts with current domain semantics, stable requirements or safety, the
domain and safety rules win. In particular:

- `保存` is the explicit operator intent for this page: it submits the current object candidate,
  automatically composes a successor from the exact Active snapshot, validates the whole candidate,
  runs applicable checks and atomically publishes Active. There is no ordinary user step for
  `保存草稿`, `校验` or `激活` after this Save. A failed Save may retain a labelled recoverable
  candidate, but it never replaces the previous Active.
- Default entry is a full-width inventory with no drawer or form. `添加识别类型`, `添加规则`,
  `添加元数据策略`, `添加命名规则`, `添加分类规则`, `添加整理策略` and the equivalent binding action
  are the only controls that open a create drawer. Row selection never opens a drawer; existing
  object Edit is an explicit full-page edit state/route.
- Recognition rules are resolved using the production priority/score/ambiguity/`stopOnMatch`
  semantics. Visual row order or drag handles must not imply a different first-match algorithm.
- One enabled RecognitionType policy binding is allowed per RecognitionType. Binding priority is not
  presented as a competing-winner mechanism.
- Classification output is a `MediaLibrary` identity plus a safe relative path. A combined label such
  as `movies/外国电影` is presentation only and cannot replace those separate authorities.
- Movie and TV naming use their actual distinct template sets. A Movie-only example does not narrow
  the supported NamingPolicy model.

Organize Policy has no supplied page image. It must use the same full-width inventory, create-drawer,
full-page edit interaction language and design system because a type binding is not a complete usable
graph without it. Its fields and behavior come from the existing domain and stable requirements,
not invented reference data. `元数据类型.png` supplies the Metadata Policy field/style reference;
its example TMDB values remain illustrative.

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
| Visible state | Show exact Active identity and capability readiness on a complete full-width inventory page. Entry has no selected object, editor or drawer. Within the workspace expose Overview, Type Bindings, Recognition Types, Recognition Rules, Metadata Policies, Naming Policies, Classification Policies and Organize Policies. Lists show stable identity, bounded description/summary, enabled state and reference/impact state without presenting unsaved or failed candidates as Active. |
| Action | Search/filter/select the inventory without opening an editor; click an explicit `添加xx` action to open a create drawer; use an explicit Edit action for an existing object in its full-page edit state; run exact-revision tests/previews; click `保存` once for the backend to persist the candidate, validate the whole graph, run applicable checks and atomically activate it. |
| Success | One immutable checked revision becomes actual Active runtime authority immediately after Save. Lists and readiness refetch from it; previews and explanations identify the exact revision tested. Save/activation creates no scan, Task, Job, schedule occurrence, Provider call or Storage mutation. |
| Failure | Invalid field/operator/template/path, duplicate identity, dangling/disabled reference, duplicate enabled type binding, unsafe regex/path, missing secret, Provider/test failure, stale Active/Save candidate, failed evidence, activation/runtime-load or persistence failure identifies the object/stage, durable state and safe next action. Previous Active remains in use. |
| Recovery | Preserve correctable form input and any labelled recoverable candidate; refresh stale authority before reapplying intended changes; follow reference impact to repoint dependents; rerun only the explicit test/check whose evidence is missing or stale; verify actual Active after an unknown Save outcome before retry. |

Required product surfaces:

- one native V2 `/ui-v2/rules` route inside the shared shell and one discoverable `整理规则`
  navigation destination;
- default full-width inventory pages derived from the references, with accessible narrow layouts;
  no editor or drawer is open on entry and the list remains usable while an explicit create drawer
  is open;
- typed frontend entities/query/mutation boundaries for the exact managed revision and all eight
  rule/policy families;
- shared authenticated API/application behavior for inventory/detail, object lifecycle, reference
  impact, previews/tests and one page-level Save-and-Activate command that composes successor
  creation, validation, applicable checks and checked activation;
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
- Every rule-family entry defaults to a complete full-width inventory: no row is selected, no edit
  form is mounted and no drawer is open. A visible `添加xx` command is the only create-drawer entry;
  search, filter, row selection, tab changes and refresh do not open it. Existing-object Edit is a
  separate explicit full-page edit state/route.
- The supplied images govern structure and style only. Production lists use actual Active objects,
  explicitly labelled recovery candidates, actual references and actual readiness; no example ID,
  count, condition or target is hard-coded as product truth or acceptance data.
- Wide layout uses a searchable full-width list; narrow/keyboard operation remains complete. Create
  drawers and explicit full-page Edit states do not discard unsaved input on search, filter,
  navigation, reconnect or stale-authority recovery without warning.
- Overview explains the processing relationship rather than merely counting rows:

  ```text
  RecognitionRule -> RecognitionType -> RecognitionTypePolicy
                  -> MetadataPolicy / NamingPolicy / ClassificationPolicy / OrganizePolicy
  ```

  It also shows capability gaps and links to the affected family without presenting unsaved or
  failed-Save state as runtime-consumed.

### RO-2 — Page-level Save with automatic validation and activation

- Read, search, filter and select have zero configuration side effects. An explicit Test/Preview may
  stage one bounded, page-scoped non-Active candidate/evidence revision, but it never activates it.
  Only an explicit `保存` submits publication intent; page entry never creates a successor.
- Every Save uses the exact Active version/digest as its optimistic-concurrency base, composes the
  focused candidate into a successor, and executes whole-document validation, applicable evidence
  checks and checked activation in one backend command. ID is immutable on edit; create/copy uses a
  new stable ID.
- The ordinary editor has no separate `保存草稿`, `校验` or `激活` action. A successful Save is the
  complete publication outcome and visibly reports the new Active. A failed Save may retain a
  labelled recoverable candidate for correction, but that candidate is never shown as Active.
- List-level enable/disable/delete and copy completion use an equivalent explicit confirm/final Save
  and the same validation-plus-activation composition; no configuration mutation is left in a hidden
  unpublished Draft merely because it did not originate in the detail form.
- Active identity, dirty/unsaved state, test/evidence staleness and Save/publication result are
  visible without requiring the operator to enter raw version/digest values.
- Known failure preserves previous Active and correctable input/candidate. Unknown outcomes are
  verified from current managed state and never automatically resubmitted. Audit records actor,
  action, object, bounded before/after and result without secrets.
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
- Exact-candidate Strategy Test accepts a bounded synthetic path/context and returns parse evidence,
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
- Copy opens a new candidate that defaults disabled where the underlying object kind supports enable
  state; its Save follows the same automatic validation and activation flow. Enable/disable and
  delete expose exact reference impact; deletion is reference-protected and never deletes media,
  Storage contents, historical snapshots, results or audit records.

### RO-6 — Exact-revision previews and bounded explanations

- Naming Preview uses an explicit bounded sample and the exact candidate revision. It returns selected
  media type, rendered directory segments/filename, variables, missing-variable warnings and
  sanitization/truncation changes. It never renames a file.
- Classification Preview uses an explicit bounded sample and exact candidate revision. It returns the
  matched rule/evidence, preserved RecognitionType, MediaLibrary ID and safe relative path. It never
  creates directories or moves files.
- Metadata Policy test is explicit. Offline validation performs no Provider call; an explicitly
  selected live test may call only the configured provider through the existing abstraction, applies
  timeout/retry/rate-limit/redaction, creates no Task and performs no Storage mutation. Candidate
  correction remains the existing review/correction journey and is not reimplemented here.
- Organize authority explanation and optional whole-chain Preview show operation, conflict/risk,
  required capabilities, source/target composition and why execution would be allowed or blocked.
  They perform zero Storage mutation, issue no execution authority and do not claim that a Preview
  result remains current after the candidate changes.
- Test results are bound to revision/version/digest internally, become visibly stale after relevant
  edits, and expose bounded secret-free reasons plus a meaningful next action. One failed sample does
  not overwrite another sample's result.

### RO-7 — Automatic checked activation, readiness and cross-surface consistency

- Whole-document validation covers field schemas, uniqueness, condition/template/path safety,
  enabled references, one-binding-per-type and every populated graph. Applicable exact-revision
  Storage/strategy/destination/provider evidence follows the shared Slice 40 applicability decision;
  unrelated empty families do not require fabricated checks.
- Every successful page-level Save automatically publishes only the exact validated candidate in
  one atomic activation. It refreshes runtime capability state but starts no scan, Task, Job, scheduled
  occurrence, notification or media mutation. Failed validation/evidence/runtime binding keeps
  prior Active and a correctable candidate when durable persistence succeeded.
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
  reference, recoverable failed Save, malformed API response, denied permission, failed test, invalid
  graph, automatic-activation conflict and unavailable runtime each have distinct bounded states.
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
5. Page entry, read, search, filter, selection, navigation, refresh and candidate inspection create
   no Draft, Provider call, Task, Job, schedule occurrence or notification. Explicit Test/Preview may
   persist only bounded non-Active candidate/evidence; live Provider access requires explicit intent.
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
- Pixel-identical reproduction of the six reference images or acceptance of their example data as
  production fixtures. Controlled visual comparison is diagnostic only.
- Editing, recompressing or regenerating the six supplied images. They are consumed unchanged as
  reference assets.
- Unrelated Storage, Files, MediaLibrary, Dashboard, Operations, Automation, Notifications or
  deployment redesign.

## Slice Acceptance Criteria

| ID | Acceptance |
|---|---|
| AC-1 | `/ui-v2/rules` is a discoverable, authenticated shared-shell workspace with all eight required sections and complete narrow/keyboard operation. Each rule-family route opens as a complete full-width inventory with no selected object, editor or drawer. Only its explicit `添加xx` action opens the create drawer; row selection/search/filter/tab/refresh never does. Existing Edit is an explicit full-page state. Reference example data is not hard-coded. |
| AC-2 | Active, unsaved input, automatic Save/validation/activation progress, and any recoverable failed-Save candidate remain visibly distinct. Reads create no Draft/work; only explicit Save submits a successor candidate. |
| AC-3 | All seven managed object families in scope support typed create/copy/edit/enable-disable where applicable/reference-safe delete using exact-version backend authority, audit and actionable stale/reference recovery. |
| AC-4 | RecognitionType and nested RecognitionRule editing enforce actual field/operator/value semantics, priority/score/stop behavior, ambiguity evidence and safe regex bounds. |
| AC-5 | Type Bindings enforce one enabled mapping per RecognitionType, validate all four downstream references and visibly preserve RecognitionType C through A naming/classification/organize reuse. |
| AC-6 | Metadata, Naming, Classification and Organize editors expose current domain fields without inventing provider switching, fallback or execution authority. Movie/TV templates and MediaLibrary-plus-relative-path output are represented truthfully. |
| AC-7 | Exact-candidate Recognition Strategy Test, Metadata test, Naming Preview, Classification Preview and Organize authority/whole-chain explanation are bounded, secret-free and zero Storage mutation. Results become stale after relevant edits. |
| AC-8 | Page-level Save automatically uses the shared managed lifecycle/applicability gates to validate and atomically activate the exact candidate, start no work and preserve previous Active/correctable input or recovery candidate on failure. |
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
- explicit RegressionType-C matrices through direct resolver, exact-candidate Strategy Test, published
  runtime, Files manual Organize Preview and Automation admission where applicable;
- focused Web typed-model/API/query/component tests for every family, default full-width inventory,
  closed drawer on entry/row selection/search/filter/tab/refresh, Add-only create-drawer opening,
  explicit full-page Edit, Active/candidate state, unsaved protection, accessibility, responsive
  layout, malformed/401/403/stale/reference/error recovery and no retry/resubmit on refresh;
- browser journeys for empty Active onboarding, dependency-ordered object Saves, tests/previews,
  automatic validation/activation failure recovery, successful Save and post-Save policy consumption;
- full Python and Web regressions, frontend typecheck/lint/format/build, Python format/lint/compile,
  `scripts/check_governance.py`, `git diff --check`, Base..Head manifest/scope audit and package tests;
- instrumentation proving read/navigation has no Draft/Task/Job/Provider/Storage side effect; explicit
  live Provider tests are bounded and redact failures; all previews/tests have zero Storage mutation;
- audit that no FFmpeg/FFprobe dependency, raw secret, private configuration, example-reference data
  authority or alternate Storage mutator entered the range;
- checksum or exact-byte comparison showing the six supplied reference images were not modified.

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

Slice: 41 — V2 Organizing Rules Workspace
Base SHA: 8a6a15597bab2fd10673db84d73a5bbc1d455ad8
Head SHA: 8433319168272ecf7ccde017afc36525e8c62ea0

Required Outcomes:
- RO-1 COMPLETE — Shared-shell Rules destination, eight sections, reference-aligned full-width
  inventories, Add-only create drawers, explicit full-page Edit, narrow/keyboard operation and
  identity-preserving deep-link/refresh/reconnect.
- RO-2 COMPLETE — Exact-Active one-Save successor composition, automatic validation/checks/atomic
  activation, distinct unsaved/failed candidates, explicit lifecycle commands and unknown-outcome
  verification without automatic replay.
- RO-3 COMPLETE — Typed RecognitionType and nested RecognitionRule authoring, backend resolution
  semantics, real references and bounded exact-candidate Strategy Test evidence.
- RO-4 COMPLETE — One enabled type binding with four validated downstream references; direct
  resolver, published runtime, Strategy Test, bound previews, Files and Automation retain C under
  A Naming/Classification/Organize reuse.
- RO-5 COMPLETE — Current Metadata, Movie/TV Naming, Classification and Organize fields are
  exposed through typed forms; copy, applicable state changes and reference-protected removal
  publish checked successors without media effects.
- RO-6 COMPLETE — Exact-candidate Strategy/Metadata tests, Naming/Classification previews and
  Organize authority/destination explanation; independent result rows, visible staleness, bounded
  errors, explicit live-test intent and zero Storage mutation/execution authority.
- RO-7 COMPLETE — Shared managed normalization, applicability, RBAC, concurrency, audit and
  checked activation remain Python authority; runtime consumers and Settings use the same Active
  semantics and originating-family handoff. V1 compatibility remains available.
- RO-8 COMPLETE — Empty/partial guidance, distinct invalid/unavailable/stale/permission/reference
  states, preserved correctable input, explicit verification/reread/refresh and truthful failed
  impact reads without fabricated references or delete requests.

Required Surfaces:
- COMPLETE — Native /ui-v2/rules in the shared shell and discoverable 整理规则 destination.
- COMPLETE — Full-width inventories, accessible narrow layouts, Add-only drawers and full-page Edit.
- COMPLETE — Typed entity/query/mutation boundaries for exact revision and all eight sections.
- COMPLETE — Shared authenticated inventory/detail/lifecycle/impact/test/preview behavior and
  page-level Save-and-Activate composition for all seven managed object families.
- COMPLETE — Settings readiness, empty/unconfigured handoff and safe originating-family return.
- COMPLETE — V1 compatibility; the ordinary completed Rules journey requires neither V1 nor
  whole-document JSON authoring.

Implemented:
- Native typed Rules management and the complete recognition-to-policy graph journey over the
  existing managed configuration and policy engines.
- Exact-candidate analysis, checked one-Save publication, actionable recovery and Settings handoff.
- Backend-legal object identity across lifecycle/API/Web/static entry, including file-like dotted
  IDs; truthful unavailable reference evidence during concurrent management.
- Complexity reassessment after the earlier multi-round corrections: the six coherent Tasks reuse
  one managed publication boundary and the existing engines. No second resolver, executor,
  configuration authority or broader architecture change is needed for the completed journey.

Tasks completed:
- 41.1 — Read-only workspace and actionable inventories (59ce2b1).
- 41.2 — Typed foundations and checked one-Save publication (6075bb0).
- 41.3 — RecognitionRule and type-binding graph authoring (4115e3b).
- 41.4 — Exact-candidate tests/previews and preserved C identity (5b542cb).
- 41.5 — Readiness and Settings return journey (4ad2a21).
- 41.6 — Object identity and truthful impact recovery (8433319; B PASS).

Final Tests:
- B independently ran the following against the corrected implementation on 2026-09-30; no
  production code changed during verification. Python 3.13.5. Packaging checkout
  3cf39346d2aa4a55d829137f9efc1487b3575696 differs from the Implementation Head only in TASK.md.
- .venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py
  tests/test_v2_rules_workspace_commands.py tests/test_v2_rules_workspace_previews.py
  tests/test_v2_ui.py tests/test_api_security.py — PASS: 126 tests, 114 subtests, 0 skips.
- .venv/bin/python -m unittest discover -s tests — PASS: 2015 tests, 7 skips, 370.621 seconds.
  The seven skips are the dedicated real OpenList/SMB/S3 matrices and isolated Local/OpenList/SMB/S3
  endurance profiles; those environments/confirmations are absent. They are unavailable acceptance
  runs, not PASS. Offline/local regression includes configuration, recognition, metadata,
  naming/classification, activation/reference/security, Files/Automation C-identity and migration.
- npm --prefix web test -- --run — PASS: 55 files, 825 tests, 0 skips. Includes the focused model,
  API, form, inventory/Edit, navigation, Settings and recovery regressions.
- npm --prefix web run test:e2e -- tests/e2e/rules-readiness.spec.ts
  tests/e2e/rules-identity.spec.ts — PASS: 14 tests, 0 skips (10 readiness, 4 identity).
- python3 scripts/rules_identity_browser_proof.py — PASS against real Python API/static serving
  with temporary legal Local/SQLite: identity journey ok, four browser mutation requests, static
  boundary ok; accepted character/suffix refresh and concurrent-remove impact recovery included.
- python3 /tmp/mediaflow-b-slice41-preview-proof.py — PASS: additional real built-artifact browser
  proof, using the committed identity harness plus B's bounded binding-preview assertions. All
  five strategy/metadata/naming/classification/organize requests returned HTTP 200/completed;
  previews left Active unchanged, C selected A Naming/Classification, edit made every result stale,
  and binding Save returned 200 and published a successor. Offline Provider mode only.
- npm --prefix web run typecheck; npm --prefix web run lint; npm --prefix web run format:check;
  npm --prefix web run build — all PASS.
- .venv/bin/python -m compileall -q mediaflow tests scripts;
  .venv/bin/ruff format --check .; .venv/bin/ruff check . — all PASS (329 formatted files).
- .venv/bin/python -m pip check; .venv/bin/mediaflow --config config/strategy.example.json config
  validate; .venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate —
  all PASS. Forbidden runtime dependency audit of mediaflow/ and pyproject.toml — PASS.
- .venv/bin/python -m pip wheel . --no-deps -w /tmp/mediaflow-b-slice41-wheel;
  .venv/bin/python scripts/wheel_smoke_test.py
  /tmp/mediaflow-b-slice41-wheel/mediaflow-2.0.0.dev0-py3-none-any.whl — PASS: isolated installed-wheel
  configuration/CLI, backup, lease-protected restore, verification and migration rehearsal;
  current schema 39, no migration required.
- python3 scripts/docker_release_security_smoke_test.py — PASS from the clean committed checkout:
  candidate image/Compose, four services, non-root/mounts, V1/V2 serving and headers, RBAC denial,
  checked Active, resident Worker manual Organize, export/log/SQLite secret-canary scans and
  unsupported-host refusal. TMPDIR used an isolated repository-local directory visible to Docker;
  the harness was unchanged and temporary resources were cleaned.
- python3 scripts/check_governance.py; git diff --check;
  git diff --check 77f4d93..8433319 — PASS. Full Slice Base..Head manifest: 55 files; correction
  range/private-file/frozen-scope audit — PASS.
- git diff --exit-code 5c8aeb4..8433319 -- the six Contract reference-image paths — PASS. Exact-byte
  SHA-256 comparisons against each image's original admission commit and the working tree — PASS.

Safety Evidence:
- Existing/new API regressions prove read/navigation/copy/impact has no Draft/Provider/Task/Job/
  Storage mutation; bounded Test/Preview stages non-Active evidence only. The production browser
  proves refresh/reconnect does not replay Save and failed impact/reread does not issue Delete.
- Publication/permission/concurrency/reference/failed and unknown outcome suites preserve one
  backend authority, immutable Active, historical pins, previous Active and no uncertain replay.
- Explicit C-identity matrices pass through resolver, published runtime, exact-candidate analysis,
  Files manual Organize and Automation. The real browser independently shows C with A policies.
- Analysis does not grant execution authority; OrganizerExecutor remains the only Storage mutator.
  Organize capabilities, overwrite/delete/cleanup permission and no silent link fallback remain
  enforced by the existing engines and their full regressions.
- No dependency files or private configuration entered implementation. config/alist.json remains
  ignored/untracked/unstaged; Docker canary scans pass for image/API/Web/export/log/durable evidence.
- All six supplied reference images were admitted before implementation and remain exact-byte
  unchanged. Four pre-existing untracked user images were preserved and not included.

Known Non-blocking Issues:
- P2 — Advisory production main chunk size: 993.83 kB (249.88 kB gzip); build succeeds.
- P3 — Passing test runs emit existing SQLite ResourceWarning and jsdom scrollTo notices. No
  assertion was removed, weakened or skipped to conceal these notices.

Explicitly Deferred:
- UNCHANGED — Every item in the Contract's Explicitly Deferred / Excluded section remains deferred;
  no Provider switching/new providers/secret store, Review/Recovery redesign, media execution from
  Rules, new rule operators/naming/classification domains, bulk/diff/rollback, V1 retirement/auth
  redesign, reference regeneration or unrelated workspace/deployment work was added.

Documentation Reconciliation Needed:
- A to reconcile Slice 41's Rules sections from TARGET to CURRENT in docs/product-experience.md and
  docs/architecture.md, and factual delivery/traceability wording in docs/v2-requirements.md.
- A to reconcile the Chinese specification's stale current-development metadata and applicable
  README/configuration guidance to the delivered native Rules journey, preserving V1 scope.
- Only after A Final Review PASS: reconcile docs/roadmap.md and docs/progress.md with Slice closure.
  This packet does not close the Slice, alter Roadmap status or select the next Slice.

Decision: SLICE READY FOR A REVIEW

## A Final Review

```text
Reviewed Range: 8a6a15597bab2fd10673db84d73a5bbc1d455ad8..8433319168272ecf7ccde017afc36525e8c62ea0
Decision: PASS
P0/P1 Blockers: None
Closure Reconciliation: COMPLETE — 2026-09-30
Next Action: A SELECTS THE NEXT LARGE SLICE
```

Review authority: the user explicitly reassigned the reviewing agent from B to A for this final
review. This is the disclosed exception to the normal A/B separation in
`docs/development-workflow.md` §2. The implementation was authored by Developer; this review
reexamined the complete Slice range and actual production boundaries rather than accepting Task PASS.

Required Outcomes and surfaces:
- RO-1 / workspace surfaces — COMPLETE: shared-shell entry and all eight sections, full-width
  inventories, explicit Add/Copy candidates and full-page Edit; typed forms, bounded narrow/keyboard
  operation, exact identity deep links, authenticated refresh and correctable input.
- RO-2 / publication surface — COMPLETE: focused exact-Active successor, whole-document validation,
  applicable evidence, pre-publication runtime preparation and atomic checked activation; explicit
  lifecycle intent, prior Active on rejection and state verification without uncertain replay.
- RO-3 / recognition surface — COMPLETE: production nested condition/value validation and existing
  priority/score/stop/ambiguity semantics, actual references and exact-candidate Strategy Test.
- RO-4 / binding surface — COMPLETE: one enabled binding, four validated downstream references and
  independent C identity under A policy reuse in resolver/runtime, Files/Automation and previews.
- RO-5 / downstream surfaces — COMPLETE: current Metadata, Movie/TV Naming, Classification and
  Organize fields, copy/applicable enable state and reference-protected removal. Configuration
  removal changes no media or historical pins; policy editing grants no execution authority.
- RO-6 / analysis surfaces — COMPLETE: exact non-Active candidate Strategy/Metadata tests and
  Naming/Classification/Organize explanations, independent result rows, visible edit staleness,
  bounded provider intent/failures and zero Storage mutation.
- RO-7 / integration surfaces — COMPLETE: shared Python normalization, permissions, concurrency,
  applicability, audit and publication; native Settings handoff/readiness, V1/API/CLI coexistence
  and immutable Active/pinned runtime consumers.
- RO-8 / recovery surfaces — COMPLETE: intentional empty/partial guidance, named invalid,
  unavailable, stale, permission and reference states; failed impact reads never fabricate counts
  or permit Delete, and preserved input plus explicit verification/reread completes recovery.

Safety and architecture:
- The 55-file Base..Head manifest introduces the Rules presentation/composition boundary over the
  existing managed authority and policy engines. No second resolver, configuration authority,
  scheduler, executor, new Provider or Deferred dependency was introduced.
- Existing Scanner/Parser/Recognition/Metadata/Naming/Classification/Planner and execution code
  remain analysis/mutation separated. Runtime preparation happens before the Active pointer change;
  backend permissions, checked evidence, exact optimistic fencing and historical pins remain intact.
- Read/navigation creates no Draft, Provider request or work. Explicit previews persist non-Active
  evidence only, issue no execution authority and use read-only Storage guards where needed.
- No silent overwrite/delete/link fallback, FFmpeg/FFprobe dependency or private configuration
  entered the range. `config/alist.json` remains ignored and untracked. All six reference images
  match their original admitted bytes; four unrelated untracked images remain outside checkpoints.

Validation assessment:
- B's actual retained full-run logs agree with its packet: Python 2015 tests with 7 explicitly
  unavailable external/endurance profiles; Web 825 tests; Wheel/schema-39 rehearsal and Docker
  release-security PASS. Post-Implementation-Head commits change only handoff documentation.
- A reran the six focused Python suites named below: first run 136 passed / 1 failed / 114 subtests
  passed; unchanged confirmation run 137 passed / 114 subtests passed, no skips. The initial failure
  is retained below and is not relabelled PASS.
  Command: `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py
  tests/test_v2_rules_workspace_commands.py tests/test_v2_rules_workspace_previews.py
  tests/test_v2_settings_rule_readiness.py tests/test_v2_ui.py tests/test_api_security.py`.
- A reran focused Rules/Settings/navigation Web tests: 8 files, 105 tests PASS, no skips, using
  `npm --prefix web test -- --run src/entities/rules src/features/rules
  src/shared/api/rules-workspace-api.test.ts src/features/configuration/ConfigurationPage.test.tsx
  src/shared/navigation`.
- A reran `npm --prefix web run test:e2e -- tests/e2e/rules-readiness.spec.ts
  tests/e2e/rules-identity.spec.ts`: 14 PASS, no skips.
- A reran `python3 scripts/rules_identity_browser_proof.py`: real Python-served identity/lifecycle,
  suffix-bearing refresh and failed-impact recovery PASS. A also reran the retained B preview probe:
  all five requests HTTP 200/completed, C stays C with A Naming/Classification, Active unchanged
  during analysis, every result stale after edit, binding Save publishes a successor.
- Governance, complete-range whitespace/private/dependency/manifest and unchanged-image checks
  PASS. Full regression/packaging evidence was inspected, not redundantly rerun after doc-only edits.

Known Non-blocking Issues:
- P2 — The direct-service concurrency test intermittently rejects the safe losing outcome
  `rules_destination_check_failed` because its allowed-error assertion omits that category.
  In the observed failure, the immutable-successor, published-count and Active assertions passed;
  the failure occurred only at the allowed-error assertion. The shared bounded read-only gate can
  refuse overlapping checks, while the production API serializes Rules publication under its
  runtime-binding lock. The unchanged isolated rerun, 8 observer-only repetitions and full focused
  confirmation passed. No lost update, mixed publication or current user-journey failure was shown;
  the initial run did not record the underlying destination failure category. No test was edited,
  assertion relaxed or skip added. This test-quality issue does not create another Task or Slice.
- Existing advisory main-chunk size and passing SQLite/jsdom notices remain non-blocking as listed
  in the Closure Packet. Real external services/endurance remain UNAVAILABLE, not accepted by proxy.

Closure Reconciliation:
- `SLICE.md` records PASS / CLOSED with the same Base and Implementation Head; the B Closure Packet
  remains historical evidence. `TASK.md` has no active Task and hands next selection to A.
- `docs/roadmap.md` closes Slice 41; `docs/progress.md` records one compact Base/Head/date/delivery/
  deferral ledger entry and updates its current pointer.
- `docs/product-experience.md` and `docs/architecture.md` reconcile native Rules from TARGET to
  CURRENT, actual shared command/static/runtime boundaries and current coexistence.
- `docs/v2-requirements.md` and the Chinese specification reconcile current development facts;
  stable requirement IDs/meanings and the released V1 baseline are unchanged.
- README and configuration guidance identify the delivered Rules route, typed editing, one Save,
  exact-candidate analysis and recovery. Every original Explicitly Deferred item remains excluded.

No next Slice is selected in this closure action.
