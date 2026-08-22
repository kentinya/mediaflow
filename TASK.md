# Phase 16 — Attachments + Atomic Media File Sets

## Goal

Discover safe sidecar files through Storage, group them with one already-identified primary media
file, plan their destinations, and execute the group only through OrganizerExecutor. Do not parse
or generate NFO content and do not redesign accepted strategy engines.

## 1. Domain model

Add provider-neutral immutable models for:

- AttachmentType: subtitle, nfo, poster, fanart, trailer, image, other.
- MediaAttachment: source StorageLocation, type, suffix/language/flags, size.
- MediaFileSet: primary StorageLocation plus ordered attachments.
- AttachmentPlan: source/destination StorageLocation, type, operation and status/error evidence.

`OrganizePlan` may contain an ordered attachment-plan tuple while retaining backward compatibility.

## 2. Configuration

Add an optional attachment policy under each OrganizePolicy:

```json
"attachments": {
  "enabled": true,
  "subtitles": true,
  "nfo": true,
  "artwork": true,
  "trailers": true,
  "otherSameStem": false
}
```

- Default is disabled for backward compatibility.
- Validate types at startup without accessing Storage.
- Unknown files and disabled attachment kinds are never included or deleted.

## 3. Read-only discovery

- Use only `Storage.list`/read-only metadata; never direct filesystem APIs.
- Inspect only the primary file's containing directory; do not add another recursive scanner.
- Recognize subtitle extensions: srt, ass, ssa, vtt, sub, sup.
- Recognize same-stem NFO, conventional poster/fanart artwork, and same-stem trailer files.
- Preserve subtitle language and Forced/SDH/HI suffix evidence.
- Deterministic ordering and case-insensitive extension matching.
- Do not read file contents, call metadata providers, or mutate Storage.

## 4. Planning

- Main destination remains Classification path + Naming directory/file.
- Attachment destinations remain in the same named media directory.
- Subtitle output uses the named primary stem plus its preserved safe suffix and original extension.
- NFO uses the named primary stem; poster/fanart keep conventional safe names; trailer identity is
  preserved.
- Reject traversal, absolute, duplicate, or colliding attachment destinations.
- A file set with a conflict is not implicitly partially executed.

## 5. Execution and recovery evidence

- Default remains DryRun with zero mutations for main and attachments.
- Explicit execution processes only the immutable plan through OrganizerExecutor.
- Use the existing operation semantics for every file; no fallback and no overwrite by default.
- Record each completed attachment operation. If a later operation fails, return PARTIAL with exact
  completed/pending evidence so explicit task retry can recover safely.
- Never delete unknown files or recursively clean the source directory.

## 6. CLI output

Preview/organize summaries expose attachment count and, in detailed plan output where available,
the source/type/destination list. No separate attachment scanner command is required.

## Safety

- Scanner through attachment planning remain read-only.
- Only OrganizerExecutor mutates Storage.
- DryRun, configuration validation, and discovery have zero mutation calls.
- RecognitionType C remains C.
- Do not implement NFO parsing/generation, image downloading, rollback, API, UI, scheduler, or
  Phase 17 work.

## Required tests

- Subtitle extension/language/forced/SDH preservation.
- NFO, poster, fanart, trailer and disabled/unknown files.
- Same-stem boundaries, Unicode and case-insensitive extensions.
- Deterministic ordering and no content reads.
- Safe target naming and collision/traversal rejection.
- DryRun zero mutation for the complete file set.
- Local MOVE/COPY/LINK attachment execution.
- Cross-storage attachment COPY/MOVE using existing Storage behavior.
- Partial execution records completed attachment steps and preserves unknown files.
- Configuration validation/default-disabled behavior.
- RecognitionType C and all existing Phase 15 regressions.

## Documentation

Update README, configuration examples, architecture, progress, and roadmap. Document supported
attachment forms, opt-in behavior, execution ordering, partial recovery, and limitations.

## Validation

Run all tests, formatter, linter, compile check, dependency check, wheel build, configuration
validation, FFprobe/FFmpeg audit, and diff check. Fix every Phase 16 failure before PASS.

## Final report

## Phase 16 Result

PASS / FAIL

## Attachment Discovery

## Planning and Execution

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
