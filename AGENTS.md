# AGENTS.md

# Project

This project is an automated media library organizer.

Before making any changes, read:

- AGENTS.md
- docs/requirements.md
- docs/architecture.md if it exists
- docs/progress.md if it exists

Do not implement the whole project at once.

Always implement only the scope specified by the current TASK.md.

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

# Development Workflow

For every TASK.md:

1. Read AGENTS.md.
2. Read docs/requirements.md.
3. Read docs/architecture.md if present.
4. Read docs/progress.md if present.
5. Inspect existing code before editing.
6. Implement only the current task.
7. Add/update tests.
8. Run tests.
9. Run formatter/linter/type checker where applicable.
10. Fix failures.
11. Update docs/progress.md.
12. Report results.

---

# Scope Control

Do NOT implement unrelated future modules.

Do NOT perform large unrelated refactors.

Prefer small coherent changes.

If an architecture adjustment is necessary:

- keep backward compatibility where practical
- document the reason
- update architecture documentation

---

# Completion Report

At the end of every task report:

## Changed Files

List files added/modified.

## Implemented

Summarize completed behavior.

## Tests

List commands executed.

## Test Results

Report pass/fail.

## Decisions

Explain important design decisions.

## Remaining Work

List items intentionally left for future tasks.

## Risks

List assumptions, technical debt, or safety concerns.
