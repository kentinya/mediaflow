# AGENTS.md

MediaFlow is an automated media library organizer. Implement only the current Task inside the
committed Slice; do not implement the whole project or make unrelated refactors.

## Read before work

Read this file, [Development Workflow](docs/development-workflow.md), committed `HEAD:SLICE.md`,
the active `TASK.md` if any, and the experience for your role. Check the current pointers in
[Roadmap](docs/roadmap.md) and [Progress](docs/progress.md).

Read the applicable sections and referenced requirement IDs in [Requirements](docs/requirements.md),
[V2 Requirements](docs/v2-requirements.md), [Product Experience](docs/product-experience.md) and
[Architecture](docs/architecture.md). User-facing work must read its complete applicable journey;
architecture changes must read the affected CURRENT/TARGET contract. Follow references needed to
understand the work; unrelated historical sections need not be reread on every turn.

## Authority

1. This file: permanent safety, architecture, roles and scope control.
2. `docs/development-workflow.md`: sole lifecycle, testing, Git, review and closure authority.
3. Requirements: complete canonical V1 scope and stable engineering/UX IDs.
4. Product Experience: user journeys and completion semantics.
5. V2 Requirements and Architecture: V2 extensions and CURRENT/TARGET design.
6. Roadmap: large-Slice priority/status; Progress: accepted closure ledger.
7. `SLICE.md`: A-owned user outcome, surfaces, boundaries, invariants, deferrals and acceptance.
8. `TASK.md`: B-owned coherent implementation unit within that Slice, or no-active-Task notice.

Lower documents may narrow work but cannot weaken higher safety or user outcomes. Broad product
scope does not authorize work outside the Slice; a Task cannot expand or close its parent Slice.
Current documents retain current rules and decisions; detailed development history belongs in Git.

## Product and experience invariants

- Every operator-facing feature must complete goal → entry → visible state → action → success →
  failure → recovery. Domain/repository/API/CLI alone cannot complete an ordinary Web journey.
- User experience is the primary design criterion. Choose the most direct journey that preserves
  correctness, security, authority and data integrity. API/Web share application behavior and rules.
- Explain failure stage, durable state, known effects, safe repeatability and the explicit next
  action. Raw exceptions and a generic Retry button do not constitute recovery.
- Batch items keep independent state, results and recovery; successful siblings are not replayed.
- Active means the exact immutable snapshot consumed by runtime. Draft/database/file/stale process
  state cannot be presented as Active. Admitted work retains its legitimate pinned context.
- Recognition, identity, naming, classification, destination, conflict and execution decisions expose
  bounded, secret-free explanations.
- Automate determinable constraints. Interrupt only for meaningful intent, authority escalation,
  ambiguity, uncertain mutation or irreversible/destructive effects. Internal tokens, revisions,
  grants, claims, checkpoints and fences are not ordinary user chores; show them only for diagnosis.
- Preserve RBAC, backend-authoritative permissions, explicit mutation intent, bounded scope, audit,
  redaction, Storage confinement, immutable pins, concurrency fencing and uncertain-effect non-replay.
  These invariants do not justify avoidable operator friction.

## Architecture and domain contracts

Keep Storage, ResourceLibrary, Scanner, Parser, Recognition, Metadata, Naming, Classification,
Organizer, Task and Logging decoupled. The processing pipeline is:

```text
ResourceLibrary → Scan/Discovery → Parse → RecognitionRule → RecognitionType
→ RecognitionTypePolicy → Metadata → Naming → Classification → OrganizePlan
→ OrganizerExecutor → Result
```

### Recognition and policy identity

RecognitionRule determines only RecognitionType. It never renames/moves/copies/deletes, determines
final library paths or writes Storage. RecognitionTypePolicy maps the unchanged RecognitionType to
MetadataPolicy, NamingPolicy, ClassificationPolicy and OrganizePolicy.

**Regression invariant:** RecognitionType C using NamingPolicy A and ClassificationPolicy A must
still produce RecognitionType C. Cover this in automated tests.

### Metadata and parsing

- Business code depends on MetadataProvider interfaces; TMDB is the initial provider and future
  providers remain possible. Convert provider DTOs to internal MediaCandidate/MediaIdentity types.
- Provider concepts include SearchMovie/GetMovie, SearchTV/GetTV, GetSeason/GetEpisode and
  FindByExternalId. Support timeout, retry, rate limits/429, caching, language, region and optional
  proxy. Never log secrets.
- **Do not use FFprobe or add FFmpeg/FFprobe dependencies.** Parse filename/path/directory/NFO and
  provider evidence. Resolution/source/codec/audio/HDR/DV tags are filename/path tags, not verified
  internal stream facts.
- Parser uses local path, filename, directories and extension only; it never queries TMDB, mutates
  files, classifies or organizes. Output includes titleCandidate, year, season/episode/episodes,
  resolutionTag, sourceTag, videoCodecTag, audioTag, hdrTag, versionTag and releaseGroup.
- Support S01E01, S1E1, S01E01E02, S01E01-E03, 1x01, EP01, E01, 第01集/第1集 and 第01话/第1话.

### Storage and libraries

- All media file operations go through Storage interfaces; business code never directly calls
  filesystem/network storage APIs. Initial providers: Local, SMB, OpenList, S3/Cloudflare R2.
- Storage covers List, Stat, Exists, Read, Write, CreateDirectory, Move, Copy, Delete, HardLink and
  SoftLink. Advertise CanMove/CanCopy/CanDelete/CanHardLink/CanSoftLink; never assume capabilities.
- ResourceLibrary binds Storage/root, scan configuration, include/exclude rules, stability policy
  and recognition rules. Discovery is read-only. MediaLibrary binds destination Storage/root.
- Exclude actively downloading/writing files through minimum age, modification threshold and stable
  size duration. Configurable temporary exclusions include *.part, *.tmp, *.download and *.!qB.

### Naming, classification and organizing

- NamingPolicy calculates directory and filename only. Variables may include title, original_title,
  year, season, episode, episodes, episode_title, provider, provider_id, resolution, source,
  video_codec, audio, hdr, version, release_group and ext.
- ClassificationPolicy selects MediaLibrary and relative path using RecognitionType, MediaType,
  title/year/genre/country/language, filename tags, ResourceLibrary and Provider/ProviderID.
- Target = MediaLibrary.RootPath + Classification.RelativePath + Naming.Directory + Naming.Filename.
  For example `/Media` + `A` + `The Matrix (1999)/The Matrix (1999).mkv`.
- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner never mutate Storage.
  DryRun runs the complete planning pipeline with zero mutations.
- **Only OrganizerExecutor may mutate Storage**, including CreateDirectory, Move, Copy, HardLink,
  SoftLink and Delete. Delete/Overwrite require explicit policy permission and authority. Never
  silently overwrite or delete source media. Conflict strategies: Skip, Overwrite, Rename, Manual.
- Organize operations: Move, Copy, HardLink, SoftLink. No silent link→copy/move fallback; any fallback
  must be explicitly configured.
- Include related subtitles, NFO, poster, fanart, trailer and matching sidecars. Preserve subtitle
  language suffixes where possible; support srt/ass/ssa/vtt/sub/sup.

### Tasks, logs and results

- Long operations use durable Tasks with observable stages: Pending, Scanning, Parsing, Recognizing,
  FetchingMetadata, Planning, WaitingConfirm, Organizing, Completed, PartialSuccess, Failed, Cancelled.
  Support pause/resume/cancel/retry/failed-item retry with independent outcomes and safe recovery.
- Persist each organize result: source, recognitionType, provider/providerId, namingPolicy,
  classificationPolicy, organizePolicy, target, status and error. Support JSON export.
- Log levels: TRACE/DEBUG/INFO/WARN/ERROR; normal mode INFO, debug mode useful processing details.
  Never log passwords, API keys, tokens, secrets, authorization headers or cookies.

## Testing and roles

Every feature includes automated success, invalid-input, conflict, failure and important-edge-case
coverage. Filesystem tests use temporary roots; unit tests use mocks/fakes/local servers rather
than production SMB/OpenList/S3/TMDB or user media. Test ownership and levels live only in the
[workflow](docs/development-workflow.md#6-test-levels): Developer runs new/changed and directly
affected tests; B owns full regression and acceptance gates.

- **A — Slice Owner / Architect / Final Reviewer:** owns Slice outcomes/boundaries, Roadmap
  boundaries and final Base..Head acceptance; only A declares `PASS / CLOSED`.
  Read [A experience](docs/agent-experience/slice-owner-architect-final-reviewer.md).
- **B — Task Planner / Task Reviewer:** plans coherent Tasks, Difficulty/Test Level and detailed
  actionable steps; reviews actual checkpoints; keeps fixes in the same Task. After PASS, reevaluate
  all Slice outcomes and stop planning when they are satisfied.
  Read [B experience](docs/agent-experience/task-planner-reviewer.md).
- **Developer — Implementation Role:** implements only the active Task, preserves safety, runs its
  affected-test plan and hands off a coherent checkpoint with actual results/risks. Does not plan
  the next Task, change Slice/Roadmap boundaries, self-approve or close a Slice.
  Read [Developer experience](docs/agent-experience/developer-implementation-role.md).

## Scope and workspace control

Before Task planning or implementation run `python3 scripts/check_governance.py`. Committed
`HEAD:SLICE.md` is the scope authority; an uncheckpointed Contract is a draft. Record branch/HEAD and
pre-existing dirty files, and preserve them. Never reset/restore/checkout/clean/stash-drop unrelated
work or silently include it in a checkpoint. Keep private configuration ignored/untracked/unstaged.

No work outside the active Slice/Task, no large unrelated refactors, no history rewriting or
unauthorized push. Necessary architecture changes preserve compatibility where practical and
explain/update the architecture contract. Lifecycle and checkpoint details belong to the workflow.
