# Slice 32 — Library & Files Experience

This is the A-owned Slice Contract for the next independently reviewable V2 capability after
Slice 31. Slice 31 remains `PASS / CLOSED` in Git, Roadmap and Progress history and is not reopened.

~~~
Slice ID: 32
Name: Library & Files Experience
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 76de3f60e223131a8b7db97a566d0ceaadd9b2a0
Implementation Head: NOT SET
~~~

The Base is the actual committed `main` checkpoint immediately before Slice 32 activation and
implementation. It must not move when B plans Tasks or Developer work begins. This Contract and its
Roadmap activation commit follow the Base and are governance changes, not Slice implementation.

## V2 program boundary

V2 remains a sequence of independently accepted user capabilities:

~~~
Slice 30 — V2 Frontend Platform & Architecture — PASS / CLOSED
Slice 31 — Operator Shell & Information Architecture — PASS / CLOSED
Slice 32 — Library & Files Experience — ACTIVE
Slice 33 — Operations Workspace — PLANNED
Slice 34 — Review & Recovery Workspace — PLANNED
Slice 35 — Configuration Administration — PLANNED
Slice 36 — V2 Parity, Accessibility & Legacy UI Retirement — PLANNED
~~~

This Contract owns the V2 read-oriented Library experience: bounded browsing of real configured
Storage, FileIndex discovery/list/detail, and truthful navigation between physical and indexed
context. It does not absorb work admission, execution, review/recovery or configuration journeys
assigned to Slices 33–35.

## User goal and vertical journey

**User goal:** within the current API-principal Bearer authentication architecture, an operator can
open Library in V2, browse what currently exists in a configured Active Storage, distinguish that
physical view from the durable FileIndex, search and filter indexed records, inspect one record's
current discovery/processing meaning and bounded history, and choose a safe next destination without
using CLI, exposing host paths or accidentally starting work.

**Entry:** open `/ui-v2/library` or a supported Library deep link from the shared V2 shell, Dashboard
or browser refresh. An unauthenticated entry uses Slice 31's memory-only connection continuation and
returns to the intended safe Library route. Library first presents operator language and explicit
choices for **Storage files** and **FileIndex** rather than treating them as one dataset.

**Visible state:** Storage files shows the configured Active runtime identity needed to establish
freshness, an operator-meaningful Storage selector, Storage-relative breadcrumb, immediate directory
entries, bounded pagination and each file's FileIndex membership where available. FileIndex shows
bounded indexed records, search/filter state, discovery/stability separately from processing
disposition, current-source occurrence evidence, and stable paging. File detail explains the source,
ResourceLibrary, discovery/stability, current versus legacy occurrence, parsing/recognition/metadata
and policy/result evidence when present, target/outcome, relevant history and currently available
next destination without fabricating unavailable evidence.

**Action:** choose an Active Storage, navigate a directory or breadcrumb, change a bounded page,
refresh or retry a failed read, open a matching FileIndex record, search/filter/reset the index,
inspect a record and return without losing useful context, or follow an explicit current V1 Web
handoff for an operational action not yet migrated. Opening or interacting with these V2 Library
surfaces does not submit Scan, Preview, Organize, Reprocess, review continuation or any other work.

**Success:** the operator can answer both “what is physically present now?” and “what does MediaFlow
currently know and conclude about this source?”, understand why the two answers may differ, move
between available physical/indexed context, and identify the honest next step while all reads remain
bounded and zero-side-effect.

**Failure:** no valid Active runtime, no configured Storage, a missing/disabled ResourceLibrary,
invalid or out-of-root path, stale/invalid page cursor, provider permission/timeout/read failure,
empty results, missing/ambiguous source linkage, stale/deleted indexed record, malformed API response,
401/403 or unavailable service is shown as a bounded operator-facing state. It does not leak raw
credentials, absolute host paths, provider payloads or exceptions and does not imply that a retry
will start or resume work.

**Recovery:** retry the failed read, return to the last valid breadcrumb/list/Library landing, reset
or narrow filters, select another configured Storage, reconnect through the shared auth boundary, or
follow an explicit V1 Configuration/Operations continuation when the fix belongs outside this
Slice. Recovery preserves safe navigation context where practical and never replays unknown work.

## Product Experience / UX constraints

- **Storage files** means a fresh, lazy, immediate and read-only view through the configured Active
  Storage adapter. **FileIndex** means durable discovery records. Labels, routes, state and empty
  results must never conflate the two or imply that one is a synchronized copy of the other.
- The default Library experience starts from operator choices. It must not require a raw Storage ID,
  ResourceLibrary ID, File ID, occurrence ID, fingerprint or cursor to discover the first useful
  page. Bounded identifiers may appear secondarily when useful for diagnosis or support.
- Paths shown or accepted by the browser are Storage-relative and breadcrumb-oriented. Absolute host
  paths, adapter roots, private endpoints, signed URLs, credentials and source contents are not a
  V2 Library display or navigation contract.
- Discovery/stability state and processing disposition are orthogonal. A missing/changed physical
  source, a historical Result and an unverified legacy occurrence are not rendered as a current
  successful processing outcome.
- Automated recognition, metadata, naming, classification, destination and Result facts expose
  bounded, secret-free explanations when evidence exists. Missing or legacy evidence is described
  as unavailable/unverified rather than reconstructed or guessed.
- Search, filters, breadcrumbs and page movement remain deterministic and bounded. Safe, allowlisted
  view state may be represented in the route so refresh/back navigation remains useful; tokens,
  secrets and internal execution authority must never enter the URL.
- Controls are never deceptive. Read actions work in V2; operational actions outside this Contract
  are visibly unavailable or provide an explicit current V1 Web continuation with no token transfer
  or claim of V2 completion. No ordinary journey is redirected to CLI.
- Loading, empty, partial, unavailable, malformed, unauthorized and forbidden states remain inside
  the shared shell, retain orientation, and give the smallest valid next action.
- The surfaces are keyboard-usable and responsive at narrow and wide viewports using the accessible
  shell foundation from Slice 31. Slice 36 remains responsible for final cross-feature parity,
  accessibility evidence and legacy UI retirement.

## Required Outcomes

| ID | Required Outcome | Gap at Base |
|---|---|---|
| RO-1 | **Library information architecture and route ownership.** `/ui-v2/library` becomes a real V2 Library landing with typed, refresh-safe child/detail routes that clearly separate Storage files from FileIndex and remain integrated with the shared shell, route metadata and auth continuation. | The Library destination is a truthful migration placeholder and has no feature routes or model. |
| RO-2 | **Active Storage files journey.** An operator can select an available configured Active Storage without supplying a raw identifier, browse its root and immediate directories through Storage-relative breadcrumbs and bounded pages, refresh/retry safely, and see FileIndex membership for file entries when available. | The V1 UI and Python application/API support the journey; V2 has no Storage browser. |
| RO-3 | **FileIndex discovery journey.** An operator can list, search and filter durable FileIndex records with bounded stable navigation while visibly keeping scan/discovery status, stability/change evidence and current processing disposition distinct. | The V1/API projection exists; V2 has no catalog list or filters. |
| RO-4 | **File detail and explanation journey.** A refresh-safe detail route presents the selected record's bounded source/library identity, current occurrence and fingerprint state, discovery evidence, processing disposition, parser/recognition/metadata/policy/target/result evidence, current versus historical relevance, reviews/checkpoints and next-action explanation when those facts exist, without fabricating legacy or unavailable evidence. | Rich redacted API detail exists but is not modeled or rendered in V2. |
| RO-5 | **Physical/indexed context linkage.** A real file can open its unique indexed record when membership is available; the detail/list can lead the operator back to the relevant physical Storage context when it can be expressed safely; missing, ambiguous, truncated or unavailable linkage is explicit and non-destructive. | V1/API expose membership and by-source semantics, but V2 has no composed journey. |
| RO-6 | **Honest next-action and recovery states.** Empty, invalid, stale, not-found, malformed, unavailable, provider-read, 401 and 403 outcomes preserve useful Library context and offer a safe retry/back/reset/reconnect or current V1 Web continuation. Operational actions are explained or handed off, never silently submitted by Library navigation. | Only shared shell-level states exist in V2; Library-specific failures and action boundaries do not. |
| RO-7 | **Reusable typed read boundary.** Storage status/options, Files pages, FileIndex pages and detail documents are normalized and validated through centralized feature/entity API-query boundaries. UI components do not reinterpret backend authority, leak protocol exceptions or duplicate raw fetch/RBAC logic. | Slice 30/31 established the pattern only for Dashboard and shared shell concerns. |
| RO-8 | **Zero-side-effect, coexistence and proof.** The complete V2 Library journey is responsive, keyboard-usable, regression-covered, read-only and compatible with V1 `/ui`, `/api/v1/*`, Python authority, memory-only Bearer handling and Python-served production assets. | Existing backend/V1 coverage proves the service boundary; V2 Library behavior and browser evidence are absent. |

## Required Surfaces

1. **Library route surface.** A real `/ui-v2/library` landing plus supported Storage files,
   FileIndex list and FileIndex detail routes use centralized typed route metadata, titles, active
   navigation and safe deep-link/auth continuation.
2. **Storage files surface.** Active runtime/Storage selection, read-only explanatory context,
   Storage-relative breadcrumb, immediate directory/file entries, bounded previous/next behavior,
   membership state and refresh/retry/empty presentation are complete.
3. **FileIndex catalog surface.** Bounded list, meaningful text search and applicable
   ResourceLibrary/Storage/discovery/processing/identity filters expose submitted filter state,
   reset behavior, deterministic page movement and clear empty results.
4. **File detail/explanation surface.** Source identity, discovery/stability, current occurrence,
   processing disposition, recognition/metadata/policy/target/Result evidence, relevance/history,
   related review/checkpoint state and available next destinations are grouped in operator language
   and honestly degrade when absent, legacy, stale or truncated.
5. **Cross-surface and migration surface.** FileIndex membership/by-source linkage composes physical
   and indexed context. Non-migrated Scan/Preview/Organize/Reprocess/review/configuration actions are
   clearly distinguished and may hand off to the current V1 Web UI without token or authority
   transfer and without promising an unsupported deep link.
6. **State, auth and responsive surface.** Shared shell connection/401/403 behavior combines with
   Library-specific loading, empty, invalid-path/cursor, not-found, malformed and unavailable states;
   keyboard focus/order and narrow/wide layouts remain usable.
7. **Application/API authority surface.** Existing system-status, runtime Storage files, FileIndex
   list/by-source/detail and their RBAC/redaction/root-confinement contracts remain authoritative.
   Only a minimal backward-compatible read projection may be added if a required V2 view cannot be
   expressed; no frontend-owned business decision, mutation or parallel API authority is allowed.
8. **Test and documentation surface.** Entity/query/component/router tests and a built-artifact
   browser journey cover the promised paths; relevant CURRENT Product Experience, Architecture and
   operator documentation are reconciled only to implementation evidence.

## Safety Invariants

- Python Application/Domain services and `/api/v1/*` remain authoritative. Frontend filtering,
  routing, labels or control visibility never grant RBAC permission, infer Active state, determine
  current-source identity or override processing/result relevance.
- The selected Storage and ResourceLibraries come from the exact immutable managed Active runtime
  consumed by the backend. Drafts, stale frontend snapshots, local configuration files and merely
  existing database rows are never presented as Active.
- Real Storage browsing uses only Storage read ports/adapters, is confined to the selected configured
  Storage root, accepts only normalized Storage-relative paths, bounds each page and remains lazy.
  It does not expose or traverse arbitrary host paths, escape through symlinks, read media contents
  or assume unsupported provider capabilities.
- V2 Library GETs, rendering, prefetching, retry, navigation, search and detail reads create no Job,
  Task, Provider request, authorization/grant, Reprocess request, review continuation, audit mutation
  or Storage mutation. No hidden POST/PUT/PATCH/DELETE request is used to make a read surface work.
- FileIndex discovery state and processing disposition remain independent and tied to the current
  source occurrence/fingerprint semantics. Historical or unverified Results never become a current
  outcome or authorize an action merely because a path or File ID matches.
- Explanations are bounded and secret-free. Raw provider payloads, authorization headers, API keys,
  cookies, passwords, proxy credentials, private endpoints, absolute adapter roots and unredacted
  exceptions never enter the DOM, route, logs, screenshots or test artifacts.
- The API-principal Bearer token remains runtime-memory-only and absent from localStorage,
  sessionStorage, IndexedDB, cookies, URLs and handoff links. Disconnect clears authenticated query
  state, including cached Library documents.
- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation;
  only OrganizerExecutor may invoke mutating Storage operations. RecognitionType C remains C when it
  selects NamingPolicy A and ClassificationPolicy A. No silent overwrite/delete or operation
  fallback is introduced.
- No FFprobe/FFmpeg dependency or content probing is introduced. File technical tags remain
  filename/path-derived evidence only.
- V1 `/ui`, existing API compatibility routes, static CSP/cache/security behavior and Python-only
  production serving remain intact. No Node production server, SSR, BFF, second HTTP service or CDN
  runtime dependency is introduced.
- `config/alist.json`, production credentials, private endpoints, operator media and local runtime
  state remain ignored/untracked and absent from checkpoints/tests.

## Explicitly Deferred

- Slice 33 Operations Workspace: expanded Dashboard, Tasks, Jobs, schedules, Automation,
  Notifications and the complete Web-native interactive Scan/Preview/Organize and execution-
  authorization journey. Slice 32 may explain or hand off to these existing V1 actions but does not
  invoke them in V2.
- Slice 34 Review & Recovery Workspace: Recognition/Metadata/Classification review, conflict,
  checkpoint action submission, Reprocess and per-item/bounded-batch recovery. Slice 32 may display
  bounded related state and available destinations but does not resolve or mutate them.
- Slice 35 Configuration Administration: Storage/ResourceLibrary setup or correction, Configuration,
  Settings, revision/test evidence, activation and managed object editing in V2.
- Slice 36 final parity, comprehensive cross-feature accessibility evidence, supported `/ui` cutover
  and V1 UI retirement.
- File upload/download/content preview, file edit/rename/delete, arbitrary Storage mutation, recursive
  tree loading, media streaming, thumbnails/posters/artwork fetch and general host-filesystem browsing.
- New Storage or Metadata providers, FileIndex/domain/schema lifecycle redesign, background indexing,
  full-text search infrastructure, Provider calls during reads or changes to recognition, naming,
  classification, planning, organization, conflict or recovery semantics.
- Built-in username/password identity, session/cookie authority, OIDC, reverse-proxy identity,
  token persistence/refresh/rotation or redesign of the current API-principal authentication model.
- SSR, React Server Components, Node production serving, micro-frontends, CDN runtime dependencies,
  native mobile clients, global search/command palette, localization and complete visual-theme work.

## Slice Acceptance Criteria

1. An authenticated operator can enter or refresh each documented Library route, and an
   unauthenticated deep entry returns through the memory-only connection boundary to the intended
   safe route without leaking a token or losing the selected read context.
2. Library clearly presents Storage files and FileIndex as different concepts. The first useful
   Storage page can be reached by selecting an Active configured Storage without typing an internal
   ID, while FileIndex opens as durable discovery state rather than live Storage contents.
3. The operator can navigate Storage-relative directories/breadcrumbs and bounded pages, distinguish
   directories/files, see useful file facts and membership, and recover from empty, path/cursor,
   provider-read, configuration-unavailable and permission failures without a mutation or CLI step.
4. The operator can submit, reset and revisit meaningful FileIndex search/filters, traverse stable
   bounded results, and read discovery/stability separately from processing disposition and current
   occurrence state.
5. A selected indexed record has a refresh-safe detail view that renders available current and
   historical explanation evidence, Result relevance and related state accurately, labels missing,
   legacy/stale/truncated evidence truthfully, and does not expose secrets or raw protocol failures.
6. Physical/indexed links work when uniquely and safely available. Missing, ambiguous, unavailable
   or truncated membership does not navigate to the wrong record or synthesize certainty, and the
   operator can return to a valid prior/parent Library context.
7. Every operational or configuration next step outside the Slice is unavailable or uses an honest
   current V1 Web continuation. Merely viewing, searching, retrying, refreshing, paging or navigating
   V2 Library sends no work-admission/mutation request and creates no side effect.
8. Loading, empty, malformed, 401, 403, not-found and unavailable states remain within the shell,
   preserve useful context where safe, and offer a concrete retry/back/reset/reconnect/handoff path.
9. Library data passes through centralized typed validation and query ownership; feature UI does not
   duplicate auth/fetch/error policy, infer backend authority or introduce a second runtime/API.
10. Automated unit/component/router/browser evidence covers the full read journey and key failures
    at narrow and wide viewports, while focused Python and full regression gates prove existing API,
    RBAC, root confinement, redaction, V1 coexistence and zero-mutation invariants remain intact.

## Final Validation Expectations

- `python3 scripts/check_governance.py` passes against the committed Slice 32 Contract and ACTIVE
  Roadmap row, with no active Task before B planning and Base SHA `76de3f60…` unchanged.
- Frontend lockfile/tooling gates pass: `npm --prefix web ci`, format check, TypeScript typecheck,
  ESLint, Vitest/React Testing Library, production Vite build and Playwright browser tests.
- Focused built-artifact browser evidence covers Library landing and direct authenticated/
  unauthenticated deep entry; Active Storage selection; root/directory/breadcrumb and bounded paging;
  FileIndex search/filter/reset/list/detail/back; physical/indexed linkage; refresh-safe state; narrow
  and wide keyboard use; empty/malformed/401/403/not-found/configuration/provider/path/cursor failures;
  and an honest V1 continuation for deferred actions.
- Browser/network evidence proves Library reads issue only the intended authenticated GET requests,
  create no work or mutation, and keep tokens/secrets/private paths out of URLs, rendered output,
  persistent browser stores, console output and captured artifacts.
- Focused Python tests cover system-status Storage options, runtime Files browsing, FileIndex catalog,
  by-source/detail/lifecycle projections, RBAC, Active-snapshot binding, root confinement, paging,
  redaction, read-only side effects and malformed/unsupported query failures.
- Existing Python API/security, Storage, FileIndex, RecognitionType C, zero-mutation pipeline, V1 UI,
  static-serving and release-security regressions pass. The Docker release-security smoke test is run
  at Slice Final when Docker is available and reported `UNAVAILABLE` rather than inferred when not.
- Normal quality gates pass: frontend formatting/type/lint/tests/build, Ruff format/check, full
  unittest discovery, compileall and `git diff --check`. Existing root-CWD private runtime state must
  not be deleted to make tests pass; use an isolated clean checkout when required and report both
  results truthfully.
- Tests use local fakes and temporary state only; no production SMB/OpenList/S3/TMDB service,
  credentials, user media or Internet access is required.
- Before Slice Final, B inspects the full Base..Head diff, test deletions/skips/assertion weakening,
  unrelated files and tracked/private configuration. Final Closure evidence records actual totals,
  skips and unavailable gates without inference.

## Closure Packet

Pending B submission after all Required Outcomes are satisfied and Slice-final validation passes.

## A Final Review

Pending B Closure Packet.
