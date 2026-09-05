# AGENTS.md

# Project

This project is an automated media library organizer.

Before making any changes, read:

- AGENTS.md
- docs/development-workflow.md
- 影视媒体资源自动整理系统需求规格说明书.md (canonical product requirements)
- docs/product-experience.md
- docs/requirements.md
- docs/architecture.md if it exists
- docs/roadmap.md if it exists
- SLICE.md
- TASK.md when it contains an active implementation Task

Do not implement the whole project at once.

The current `SLICE.md` is the A-owned business-capability contract. An active `TASK.md` is a
B-owned implementation unit inside that contract. Developer work must satisfy both and may not
expand either one.

---

# Guidance Hierarchy

Use this hierarchy when interpreting future work:

1. `AGENTS.md` defines permanent safety, architecture, role, and scope-control rules.
2. `docs/development-workflow.md` is the sole authority for implementation, commit, review,
   closure, and next-slice sequencing.
3. The root Chinese product requirements specification defines canonical V1 product scope.
4. `docs/product-experience.md` defines canonical user journeys and product-completion semantics.
5. `docs/requirements.md` provides stable engineering/UX requirement IDs, while
   `docs/architecture.md` distinguishes CURRENT implementation from TARGET design.
6. `docs/roadmap.md` records only large Slice priority and status.
7. `SLICE.md` is the current A-owned Slice Contract: user goal, required outcomes, boundaries,
   safety invariants, deferrals, acceptance criteria, Base, and review state.
8. `TASK.md` is the current B-owned implementation Task inside `SLICE.md`, when a Task is active.

A lower document may refine or narrow a higher one but must not silently weaken its safety or user
outcome. A broad product requirement does not authorize implementation beyond `SLICE.md`; a Task
cannot expand the Slice or declare the Slice complete.

---

# Product and User Experience

Every operator-facing feature must be designed and accepted as a vertical user journey, not as an
isolated backend module. Before implementation, identify and document:

- user goal
- entry point
- visible state
- available action
- success outcome
- failure outcome
- recovery path

Domain models, repositories, application services, migrations, or internal tests alone never make
an operator-facing requirement product-complete. Completion requires the user-visible entry point,
state, action, outcome, error, and recovery promised by the applicable product requirement.

Permanent product rules:

1. Retry is not equivalent to recovery. Recovery must explain what failed, what state is durable,
   what is safe to repeat, and the explicit action that continues or resolves the item.
2. Batch workflows preserve independent per-item state, outcome, and recovery. One item must not
   hide, overwrite, or block the diagnosis and safe recovery of another item.
3. Configuration displayed as Active must be the exact immutable configuration snapshot consumed
   by runtime. A draft, database row, JSON file, or stale process snapshot must not be presented as
   Active merely because it exists.
4. Automated decisions affecting recognition, metadata identity, naming, classification,
   destination, conflict handling, or execution must expose bounded, secret-free explanations.
5. CLI-only completion does not satisfy a requirement whose final management surface is Web. CLI
   remains valuable for administration, debugging, migration, and automation.
6. API and Web capabilities for the same journey must use the same application behavior,
   permissions, validation, state, and safety rules.
7. Safety remains stronger than convenience: default DryRun, no silent overwrite/delete, explicit
   authority, zero-mutation analysis stages, and OrganizerExecutor-only mutation remain mandatory.

Read `docs/product-experience.md` before implementing any user-facing feature. `SLICE.md` must define
the user goal, journey outcome, failures/recovery and Slice acceptance. `TASK.md` must identify the
coherent part of that journey it implements and its Task-level acceptance before coding.

---

# Core Architecture

The system must keep these modules decoupled:

- Storage
- ResourceLibrary
- Scanner
- Parser
- Recognition
- Metadata
- Naming
- Classification
- Organizer
- Task
- Logging

The main processing pipeline is:

ResourceLibrary
-> Scan
-> Parse
-> RecognitionRule
-> RecognitionType
-> RecognitionTypePolicy
-> Metadata
-> Naming
-> Classification
-> OrganizePlan
-> OrganizerExecutor
-> Result

---

# Critical Domain Rules

## Recognition

RecognitionRule only determines RecognitionType.

Example:

A file -> RecognitionType A
B file -> RecognitionType B
C file -> RecognitionType C

Recognition MUST NOT:

- rename files
- move files
- copy files
- delete files
- determine final media library path
- directly execute Storage write operations

---

## RecognitionTypePolicy

RecognitionTypePolicy maps RecognitionType to:

- MetadataPolicy
- NamingPolicy
- ClassificationPolicy
- OrganizePolicy

Example:

A:
- MetadataPolicy = A
- NamingPolicy = A
- ClassificationPolicy = A
- OrganizePolicy = Move

B:
- MetadataPolicy = B
- NamingPolicy = B
- ClassificationPolicy = B
- OrganizePolicy = Move

C:
- MetadataPolicy = C
- NamingPolicy = A
- ClassificationPolicy = A
- OrganizePolicy = Move

IMPORTANT:

RecognitionType C MUST remain C.

Using NamingPolicy A or ClassificationPolicy A must NEVER change
RecognitionType C into RecognitionType A.

Add automated regression tests for this behavior.

---

# Metadata

Metadata providers identify the actual movie or TV show.

Initial provider:

- TMDB

Architecture must allow future providers.

Business code must depend on MetadataProvider interfaces, not directly
on TMDB HTTP APIs.

The metadata layer should support concepts equivalent to:

- SearchMovie
- GetMovie
- SearchTV
- GetTV
- GetSeason
- GetEpisode
- FindByExternalId

Provider response DTOs must not leak into domain entities.

Convert provider responses into internal types such as:

- MediaCandidate
- MediaIdentity

Metadata requests must support:

- timeout
- retry
- rate limit handling
- HTTP 429 handling
- caching
- language configuration
- region configuration
- optional proxy

Secrets must never appear in logs.

---

# FFprobe

DO NOT use FFprobe.

DO NOT add FFmpeg/FFprobe dependencies.

Media parsing is based on:

- filename
- path
- directory structure
- NFO when available
- metadata providers

Technical tags such as:

- 2160p
- 1080p
- WEB-DL
- BluRay
- H265
- HDR
- DV

are filename/path tags only.

They are NOT verified against the internal video stream.

---

# Storage

All file operations must go through Storage interfaces.

Business code must never directly call filesystem/network storage APIs.

Initial storage providers:

- Local
- SMB
- OpenList
- S3 / Cloudflare R2

Storage interface should cover concepts such as:

- List
- Stat
- Exists
- Read
- Write
- CreateDirectory
- Move
- Copy
- Delete
- HardLink
- SoftLink

Storage implementations must expose capabilities:

- CanMove
- CanCopy
- CanDelete
- CanHardLink
- CanSoftLink

Do not assume every provider supports every operation.

---

# Resource Library

ResourceLibrary defines where source media files are discovered.

It references:

- Storage
- RootPath
- scanning configuration
- include rules
- exclude rules
- file stability policy
- recognition rule set

Scanning must not modify files.

---

# Media Library

MediaLibrary defines the destination root.

It references:

- Storage
- RootPath

ClassificationPolicy decides which MediaLibrary and relative path
a media item belongs to.

---

# Parser

Parser works only with local information.

Parser input:

- file path
- filename
- parent directories
- extension

Parser output should include fields such as:

- titleCandidate
- year
- season
- episode
- episodes
- resolutionTag
- sourceTag
- videoCodecTag
- audioTag
- hdrTag
- versionTag
- releaseGroup

Support common episode formats:

- S01E01
- S1E1
- S01E01E02
- S01E01-E03
- 1x01
- EP01
- E01
- 第01集
- 第1集
- 第01话
- 第1话

Parser MUST NOT:

- access TMDB
- modify files
- classify media
- execute organizing operations

---

# Naming

NamingPolicy only calculates:

- target directory name
- target filename

NamingPolicy MUST NOT modify files.

Naming template variables may include:

- title
- original_title
- year
- season
- episode
- episodes
- episode_title
- provider
- provider_id
- resolution
- source
- video_codec
- audio
- hdr
- version
- release_group
- ext

---

# Classification

ClassificationPolicy determines:

- MediaLibrary
- relative target path

Classification may use:

- RecognitionType
- MediaType
- title
- year
- genre
- country
- language
- filename tags
- ResourceLibrary
- Provider
- ProviderID

Classification MUST NOT modify files.

---

# Organizer

Planner calculates OrganizePlan.

Planner MUST NEVER modify files.

Only OrganizerExecutor may execute:

- CreateDirectory
- Move
- Copy
- HardLink
- SoftLink
- Delete

DryRun must execute the complete planning pipeline but perform zero
filesystem/storage mutations.

---

# Final Target Path

Target path is calculated from:

MediaLibrary.RootPath
+ ClassificationPolicy.RelativePath
+ NamingPolicy.Directory
+ NamingPolicy.Filename

Example:

MediaLibrary:
/Media

Classification:
A

Naming:
The Matrix (1999)/The Matrix (1999).mkv

Result:

/Media/A/The Matrix (1999)/The Matrix (1999).mkv

---

# Conflict Handling

Supported strategies:

- Skip
- Overwrite
- Rename
- Manual

Overwrite is high risk.

Never silently overwrite user media.

Never silently delete source media.

---

# Organize Operations

Supported:

- Move
- Copy
- HardLink
- SoftLink

Do not silently fall back from HardLink to Copy or Move.

Fallback must be explicitly configured.

---

# Attachments

Media organization should support related files such as:

- subtitles
- NFO
- poster
- fanart
- trailer
- matching sidecar files

Subtitle examples:

- srt
- ass
- ssa
- vtt
- sub
- sup

Preserve language suffixes where possible.

---

# File Stability

Do not organize actively downloading/writing files.

Support concepts such as:

- minimum file age
- last modification threshold
- stable size duration

Temporary files should be ignored by configurable rules.

Examples:

- *.part
- *.tmp
- *.download
- *.!qB

---

# Task System

Long operations must use Tasks.

Suggested states:

- Pending
- Scanning
- Parsing
- Recognizing
- FetchingMetadata
- Planning
- WaitingConfirm
- Organizing
- Completed
- PartialSuccess
- Failed
- Cancelled

Support:

- pause
- resume
- cancel
- retry
- retry failed items

---

# Logging

Supported levels:

- TRACE
- DEBUG
- INFO
- WARN
- ERROR

Normal mode:

INFO

Debug mode should show useful processing details.

Never log:

- passwords
- API keys
- tokens
- secrets
- authorization headers
- cookies

---

# Result Records

Every organize task must persist results.

At minimum store:

- source
- recognitionType
- provider
- providerId
- namingPolicy
- classificationPolicy
- organizePolicy
- target
- status
- error if any

JSON export should be supported.

---

# Safety Rules

This project manages user media files.

Safety is more important than convenience.

Rules:

1. Scanning never modifies files.
2. Parsing never modifies files.
3. Recognition never modifies files.
4. Metadata lookup never modifies files.
5. Naming never modifies files.
6. Classification never modifies files.
7. Planner never modifies files.
8. DryRun never modifies files.
9. Only OrganizerExecutor may mutate storage.
10. Delete and Overwrite require explicit policy permission.

---

# Testing Rules

Every feature must include automated tests.

Tests must cover:

- success path
- invalid input
- conflicts
- failures
- important edge cases

Use temporary files/directories for filesystem tests.

Do not require production SMB/OpenList/S3/TMDB services for unit tests.

Use:

- mocks
- fakes
- local test servers

Important regression test:

RecognitionType C
-> NamingPolicy A
-> ClassificationPolicy A

must still produce:

RecognitionType == C

---


# Development Roles

MediaFlow has two formal management objects—Slice and Task—and three responsibilities. Detailed
lifecycle, status, testing, Git and review rules live only in `docs/development-workflow.md`.

## A — Slice Owner / Architect / Final Reviewer

A owns the large business-capability boundary in `SLICE.md`, its user outcome, required surfaces,
safety invariants, explicit deferrals and final acceptance. Only A may materially change the Slice
Contract, change Roadmap Slice boundaries, conduct the final Base..Head Slice review, or declare a
Slice `PASS / CLOSED`. A does not turn individual assertions, fields, labels or non-blocking test
ideas into new Slices.

## B — Task Planner / Task Reviewer

B reads `SLICE.md`, plans coherent implementation Tasks inside it, assigns Difficulty and Test
Level, and reviews each Task's actual checkpoint. Fixes normally remain in the same Task review
loop. After every Task PASS, B reevaluates all Slice Required Outcomes; once they are satisfied, B
must stop creating Tasks and prepare the Slice Closure Packet for A.

## Developer — Implementation Role

Developer implements only the active `TASK.md` within `SLICE.md`, preserves architecture and safety,
runs the assigned Test Level, creates a coherent checkpoint, and reports actual results and risks.
Developer does not define the next Task, modify the Slice boundary or Roadmap, or close a Slice.




# Development Workflow

Follow `docs/development-workflow.md`. It is the sole authority for Slice/Task lifecycle, planning,
review, testing levels, checkpoints, fixes, closure packets, final review, and legacy migration.
This file defines permanent principles only and does not define a competing state machine.

---

# Scope Control

Before Task planning or implementation, run `scripts/check_governance.py`. It uses committed
`HEAD:SLICE.md` as Slice authority and fails when the working-tree Contract is not checkpointed or
the active Task/Roadmap relationship is invalid. Preserve all pre-existing dirty files; never use
reset, restore, checkout, clean, or stash/drop to make unrelated work disappear. Detailed lifecycle
semantics remain solely in `docs/development-workflow.md`.

Do NOT implement work outside the active `SLICE.md` and `TASK.md`.

Do NOT perform large unrelated refactors.

Prefer small coherent changes.

If an architecture adjustment is necessary:

- keep backward compatibility where practical
- document the reason
- update architecture documentation
