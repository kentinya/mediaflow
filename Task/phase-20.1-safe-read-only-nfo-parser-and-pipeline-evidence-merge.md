# Phase 20.1 — Safe Read-Only NFO Parser and Pipeline Evidence Merge

## Goal

Add NFO as a bounded local parsing information source and feed its normalized evidence into the
existing Parser → Recognition → Metadata pipeline without changing downstream engine semantics.

## Scope

### 1. Provider-neutral NFO domain model

- Add immutable NFO parse result, warning/error, media-type hint, provider-ID and external-ID
  evidence models under the Parser boundary.
- Keep TMDB/Kodi/Jellyfin XML details out of Recognition and CandidateMatcher.
- RecognitionType remains selected only by RecognitionRuleEngine.

### 2. Safe XML parser

- Parse common movie, TV show and episode NFO roots and bounded fields: title, original title,
  year/premiered date, season, episode(s), provider unique IDs and external IDs.
- Support common `<uniqueid type="tmdb" default="true">`, `<tmdbid>`, `<imdbid>`, `<id>`,
  `<season>`, `<episode>` and repeated episode forms deterministically.
- Reject DTD/entity declarations, malformed XML, excessive input, excessive nesting, unsafe or
  invalid values, and unsupported roots with typed diagnostics. Never resolve external entities.
- Normalize Unicode/whitespace and bound all retained text and collection counts.

### 3. Deterministic ParseResult merge

- Merge NFO title/year/season/episode evidence with existing filename/path ParseResult.
- Valid explicit NFO evidence takes precedence for semantic identity hints; conflicting filename
  or path evidence remains observable as alternatives and structured warnings.
- Filename-derived technical/release tags remain unchanged.
- Preserve provider IDs as evidence for later metadata lookup without manufacturing MediaIdentity.

### 4. Storage-only read integration

- Discover only deterministic same-directory NFO candidates through Storage list/read; do not use
  `os`, `pathlib` writes, or concrete Local/SMB/OpenList/S3 implementation details.
- Prefer the primary media stem NFO, then conventional `movie.nfo`/`tvshow.nfo`; never recursively
  search and never read more than a configured maximum.
- Missing NFO is a normal no-op. Permission/read/malformed failures are explicit bounded warnings
  and do not mutate Storage.
- Integrate the enriched ParseResult into production Strategy Test and MediaOrganizer flows where
  a configured Storage-relative source is available. Synthetic/offline paths without Storage keep
  existing filename/path behavior.

### 5. Safety and compatibility

- NFO parsing performs zero Storage mutations and zero network/MetadataProvider calls.
- Do not generate or rewrite NFO, download images, call FFmpeg/FFprobe, implement Hash/Rollback,
  or begin Phase 20.2.
- Preserve all A/B/C policy mappings and specifically RecognitionType C identity.

## Required Tests

- Movie, TV show, episode, multi-episode, Unicode and whitespace normalization.
- Default and non-default provider IDs, IMDb/external IDs, date/year handling.
- Filename/NFO conflicts, deterministic precedence, missing fields and missing NFO.
- Malformed XML, DTD/entity rejection, excessive size/depth/text/count and invalid numeric values.
- Exact-stem/conventional discovery order, bounded reads, Storage errors and no recursive discovery.
- Full Strategy/organizer integration using fake/read-only Storage.
- RecognitionType C remains C after NFO enrichment.
- Read calls are bounded; Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls are zero.

## Validation

Run Phase 20.1 tests, Parser, Recognition, Metadata, Strategy CLI, Scanner/FileIndex, Storage,
Organizer and DryRun regressions, then the full offline suite. Run formatter, lint, compile,
configuration validation, dependency/build checks, FFmpeg/FFprobe audit and diff check.

Update `docs/architecture.md`, `docs/progress.md`, `docs/roadmap.md`, and the requirements status
without claiming NFO generation or future Phase 20 capabilities.

## Completion Report

Finish with the AGENTS.md completion structure and additionally report:

## Phase 20.1 Result

PASS / FAIL

## NFO Coverage

## Merge Semantics

## Safety

## Regression

## Final Recommendation
