# Development Progress

## Completed

- Dependency-free Python bootstrap and quality configuration
- Domain models and interfaces for every module in the bootstrap task
- Storage abstraction, capabilities, and root-confined LocalStorage adapter
- Policy registry preserving recognition identity across reused policies
- Pure OrganizePlanner and explicit OrganizerExecutor mutation boundary
- Architecture documentation and regression/safety tests
- Phase 1 LocalStorage: complete local operations, unified errors, path safety, read-only mode,
  platform-aware capabilities, and integration-style tests
- Phase 2 SMBStorage: smbprotocol adapter, injectable client boundary, streaming operations,
  connection lifecycle, bounded concurrency, timeout/reconnect policy, and network error mapping
- Phase 3 OpenListStorage: verified OpenList v4 HTTP adapter, client/DTO isolation, pagination,
  root-confined paths, streaming download/upload, safe mutations, and unified HTTP errors
- Phase 4 S3/R2 Storage: unified AWS/R2/S3-compatible adapter, logical directories, pagination,
  streaming and multipart writes, server-side copy, and verified non-atomic move safety
- Phase 5 ResourceLibrary and Scanner: filterable read-only traversal, bounded concurrency,
  cancellation, cross-scan stability, durable FileIndex, and safe full/incremental reconciliation
- Phase 6 FilenameParser and PathParser: pure local candidate extraction, evidence/warnings,
  bounded episode ranges, path-context merging, and release-tag normalization
- Phase 7 Recognition Rule Engine and RecognitionTypePolicy: composable conditions, deterministic
  priority/score conflict resolution, explainable results, and independently reusable policy IDs
- Phase 8 Metadata Provider and TMDB: provider registry, deterministic candidate matching,
  normalized metadata cache, bounded HTTP behavior, and movie/TV/episode identification
- Phase 8.5 Strategy Test CLI: offline/live single-path and Scanner-backed local directory
  inspection, JSON case regression runner, explainable output, secret redaction, and hard
  zero-mutation Storage guard
- Phase 9 NamingPolicy and NamingEngine: safe templates, movie/TV/multi-episode naming, Unicode and
  path-safe components, missing-variable strategies, deterministic preview, and zero I/O
- Phase 9.1 Naming Preview CLI: live single-path/directory preview, compact summaries, nested case
  expectations, explicit offline unavailability, and downstream zero-execution safety
- Real-world Recognition bootstrap: separate smoke/development/user rule sources, JSON loader,
  ResourceLibrary root bindings, Scanner context propagation, and explicit unmatched behavior
- Single-file ResourceLibrary resolution: configured-root auto-detection plus explicit
  `--resource-library` context, shared with directory-mode rule evaluation

## Current

- Phase 13.3 Storage identity audit and OpenList native Move→Rename completion: PASS
- Phase 14 persistent FileIndex and recoverable task foundation: implementation complete,
  validation pending

## Planned

- Phase 15: conflict/manual confirmation and explicit safe resolution
- Later: attachments, runtime SMB/S3 config, scheduler/API, and UI

## Known Issues

- Cross-storage links are unsupported; cross-storage COPY/MOVE use bounded streaming transfer
- LocalStorage link capabilities still depend on the host filesystem
- No static type checker is configured; typed source receives compile validation only
- Write operations are streamed but not transactionally atomic; a failed write can leave a partial
  target. Atomic temporary-file replacement is deferred to Organizer safety hardening.
- Path checks minimize symlink escape risk, but filesystem-level time-of-check/time-of-use races
  require OS-specific directory-handle APIs for complete hardening.
- SMB HardLink and SoftLink are unsupported and never fall back to another operation.
- SMB Copy uses client-side streaming because server-side copy support varies by server.
- No live SMB integration environment is configured; production connectivity remains environment
  dependent and was not exercised against a real share.
- OpenList Copy to a new basename uses a streaming fallback. A same-OpenList Move that changes both
  directory and basename uses native server-side Move then Rename, with best-effort rollback if
  Rename fails. Cross-storage Move remains streamed Copy + verification + source Delete.
- OpenList upload is streamed with HTTP chunked transfer. Actual maximum object size, direct-upload
  behavior, and backend-specific limits remain dependent on the configured OpenList driver.
- No live OpenList integration environment is configured; the opt-in test requires
  `TEST_OPENLIST_URL`, `TEST_OPENLIST_TOKEN`, and optionally a dedicated `TEST_OPENLIST_ROOT`.
- S3/R2 Move is Copy + target size verification + Delete and is not atomic. Delete failure returns
  an explicit partial error and can leave both objects.
- Server-side copy above the configured single-copy limit is unsupported. Multipart UploadPartCopy
  is deferred; the adapter never silently downloads a large object as a fallback.
- S3 logical directories without marker objects can be listed and statted, but an empty implicit
  directory has no remote object to delete. Range Read is deferred because Storage has no range API.
- No MinIO/S3 or R2 integration environment is configured; opt-in tests only use a unique child
  under `TEST_S3_ROOT` or `TEST_R2_ROOT` (default `mediaflow-test`).
- Scanner incremental detection is metadata-based (path, size, and modification time); hashing and
  filesystem watchers are intentionally deferred.
- Directory symlinks are not followed. FileIndex has SQLite and in-memory adapters, but database
  migrations beyond this Phase 5 table are deferred to the future persistence layer.
- Bare episode forms such as E01 cannot infer a season without directory evidence. Unusual fansub
  conventions and unknown release tags remain uninterpreted candidates for later rule expansion.
- Parser output is deliberately unverified; conflicting filename/directory candidates remain as
  warnings and alternatives for the future Recognition/Metadata stages.
- Python's standard regex engine has no execution timeout. Recognition rule regexes therefore use
  conservative pattern/input limits and reject common catastrophic constructs; this intentionally
  excludes some advanced backreference and nested-quantifier expressions.
- Ambiguous recognition results require a future manual-confirmation workflow. Recognition selects
  configured types only and does not confirm actual movie or TV identity.
- TMDB availability and current response data remain external dependencies. Unit tests use fake
  transports; no live TMDB integration test runs without explicitly configured credentials.
- Metadata matching is heuristic. Ambiguous/confirmation results need a future manual UI. Poster
  and backdrop paths are references only; images are not downloaded and NFO files are not created.
- The strategy CLI's built-in A/B/C rules are isolated smoke-test fixtures. Production strategy
  content is loaded from configured JSON catalogs and validated before scanning.

## Last Validation

Phase 0 acceptance (2026-08-19): PASS

- Isolated editable install with development dependencies: passed
- Wheel build: passed
- `ruff format --check mediaflow tests`: passed
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 10 passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Architecture/storage-boundary audit: passed
- FFmpeg/FFprobe code and dependency audit: passed

Phase 0 fixes:

- Added complete A/B/C recognition policy matrix coverage
- Strengthened dry-run assertions for source content and absent target paths
- Added core model and default Storage capability coverage
- Made bootstrap executor reject overwrite and delete operations by default
- Fixed Ruff findings and declared Ruff as a reproducible development dependency

Phase 1 LocalStorage validation (2026-08-19): PASS

- `ruff format mediaflow tests`: passed, 23 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 24 passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Business-layer filesystem boundary audit: passed
- FFmpeg/FFprobe code and dependency audit: passed

Phase 1 acceptance (2026-08-19): PASS

- `ruff format --check mediaflow tests`: passed, 23 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 26 passed, 0 failed, 0 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- 16 MiB native copy and streaming digest verification: passed
- Path traversal and symlink escape tests: passed on this platform
- Read-only, conflict, safe delete, unified error, and capability tests: passed
- Dry-run zero-mutation regression: passed
- Business-layer filesystem and FFmpeg/FFprobe audits: passed

Acceptance fixes:

- Added large-file copy coverage without whole-file reads
- Added explicit permission-denied error mapping coverage
- Locked path traversal, absolute path, invalid Copy/Move target, link identity, and entry metadata
  assertions
- Replaced `lexists` checks with `lstat` handling so access errors are not silently reported as
  missing paths

Phase 2 SMBStorage validation (2026-08-19): PASS

- Optional `smbprotocol 1.17.0` production dependency installed and API signatures verified
- `ruff format --check mediaflow tests`: passed
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 44 passed, 0 failed, 0 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- LocalStorage and DryRun regressions: passed
- Business-layer filesystem and FFmpeg/FFprobe audits: passed
- Live SMB integration: skipped because no TEST_SMB_* environment was configured

Phase 3 OpenListStorage validation (2026-08-19): PASS

- Official OpenList v4 API and token authentication verified against current official sources
- Optional `httpx 0.28.1` dependency installed and editable package installation passed
- `ruff format --check mediaflow tests`: passed, 27 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 64 tests, 63 passed, 0 failed, 1 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- LocalStorage, SMBStorage, policy identity, and DryRun regressions: passed
- Business-layer filesystem and FFmpeg/FFprobe audits: passed
- Live OpenList integration: skipped because no OpenList integration environment was configured

Phase 4 S3/R2 Storage validation (2026-08-19): PASS

- Optional `boto3 1.43.74` production dependency installed; R2 region/path-style/timeout SDK
  configuration verified without contacting a real bucket
- `ruff format --check mediaflow tests`: passed, 29 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 90 tests, 87 passed, 0 failed, 3 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- LocalStorage, SMBStorage, OpenListStorage, policy identity, and DryRun regressions: passed
- Business-layer filesystem, SDK-boundary, secret, and FFmpeg/FFprobe audits: passed
- MinIO/S3 integration: skipped because no S3 integration environment was configured
- Cloudflare R2 integration: skipped because no R2 integration environment was configured
- OpenList integration: skipped because no OpenList integration environment was configured

Phase 5 ResourceLibrary and Scanner validation (2026-08-19): PASS

- `ruff format --check mediaflow tests`: passed, 34 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 114 tests, 111 passed, 0 failed, 3 skipped
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Complete FakeStorage scan mutation counts: Write/CreateDirectory/Move/Copy/Delete/HardLink/
  SoftLink were all zero
- Concrete Storage dependency, media parsing/metadata, filesystem mutation, and FFmpeg/FFprobe
  boundary audits: passed

Phase 6 FilenameParser and PathParser validation (2026-08-19): PASS

- Parser suite: 6 test methods with 77 table-driven filename/path cases passed
- Full suite: 120 tests, 117 passed, 0 failed, 3 skipped
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- `ruff format --check mediaflow tests`: passed, 36 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Parser Storage mutations, Metadata/network calls, and database writes: zero by construction
- Parser/Storage boundary and FFmpeg/FFprobe runtime dependency audits: passed

Phase 7 Recognition Rule Engine and RecognitionTypePolicy validation (2026-08-19): PASS

- Recognition suite: 15 passed
- Full suite: 135 tests, 132 passed, 0 failed, 3 skipped
- Parser suite: 6 passed with 77 table-driven filename/path cases
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- A, B, and C recognition identity tests: passed
- C policy mapping to Metadata C / Naming A / Classification A / Organize A: passed; identity C
  remained unchanged
- Nested conditions, stable ordering, priority/score conflicts, Ambiguous, Unrecognized,
  stop-on-match, disabled configuration, evidence, and regex validation tests: passed
- `ruff format --check mediaflow tests`: passed, 38 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Recognition Storage mutations, Metadata/network calls, and database writes: zero
- Recognition/Storage boundary and FFmpeg/FFprobe runtime dependency audits: passed

Phase 8 Metadata Provider, TMDB, and Candidate Matcher validation (2026-08-19): PASS

- TMDB behavior verified against current official authentication, search, details, season,
  episode, external-ID, and rate-limit documentation
- Metadata/TMDB suite: 21 passed using fake HTTP transports; no real TMDB credentials required
- Full suite: 156 tests, 153 passed, 0 failed, 3 skipped
- Recognition suite: 15 passed
- Parser suite: 6 passed with 77 table-driven filename/path cases
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- Wrong-first/later-correct candidate regression: passed
- RecognitionType C before and after metadata identification: C; passed
- Movie/TV search/details, season/episode, multi-episode, external ID, pagination, malformed
  response, cache/TTL/force refresh, timeout/retry/429, concurrency, request budget, and secret
  redaction tests: passed
- `ruff format --check mediaflow tests`: passed, 41 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Metadata Storage/Naming/Classification/Organizer calls: zero
- FFmpeg/FFprobe runtime dependency audit: passed

Phase 8.5 Strategy Test CLI validation (2026-08-19): PASS

- Installed `strategy-test` entry point supports positional/offline, live metadata, and JSON
  case-file modes
- Strategy CLI suite: 9 passed; no Internet access required
- Starter strategy dataset: 13 passed, 0 failed, 0 skipped
- Full suite: 165 tests, 162 passed, 0 failed, 3 skipped
- Metadata suite: 21 passed
- Recognition suite: 15 passed
- Parser suite: 6 passed with 77 table-driven filename/path cases
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- C policy mapping displayed as Metadata C / Naming A / Classification A / Organize A;
  RecognitionType remained C
- Wrong-first/later-correct, low-confidence, ambiguous, no-result, TV episode,
  multi-episode, Unicode, and path/filename conflict strategy cases passed
- Read-only strategy guard Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink counts:
  all zero for a complete pipeline; direct mutation attempts fail immediately
- Offline metadata provider calls: zero
- Secret-redaction tests passed; live credentials are loaded only from environment-backed TMDB
  configuration and are not printed
- `ruff format --check mediaflow tests`: passed, 44 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel and editable entry-point builds through the configured setuptools backend: passed
- FFmpeg/FFprobe and future Naming/Classification/Organizer execution audits: passed
- Directory traversal remained intentionally absent from the CLI at this validation point and was
  added in the follow-up validation below using the production Scanner

Phase 8.5 Strategy Test directory mode validation (2026-08-19): PASS

- `strategy-test --directory PATH [--limit N] [--live-metadata]` verified through the installed
  console entry point
- Directory mode constructs a read-only LocalStorage guard, minimal ResourceLibrary, production
  StorageScanner, and in-memory FileIndex; the CLI contains no traversal implementation
- Existing ResourceLibrary media extensions and exclusion rules filter Scanner discoveries
- Offline is the default; fake-provider live metadata regression passed without Internet access
- Strategy CLI suite: 11 passed
- Full suite: 167 tests, 164 passed, 0 failed, 3 skipped
- Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls: all zero

Phase 8.5.1 Strategy configuration integration validation (2026-08-19): PASS

- Added an explicit development strategy bootstrap outside domain logic with MetadataPolicy A/B/C
  and optional TMDB language/region configuration
- Added `MetadataPolicyRegistry`; RecognitionTypePolicy metadata references now resolve through the
  configured application catalog instead of an ad hoc runner dictionary
- Directory mode validates all type-policy → metadata-policy references before Scanner starts and
  validates provider references before a live scan
- Missing policy/provider links are startup `ConfigurationError` failures, not per-file media errors
- Offline mode requires neither a TMDB provider nor `TMDB_ACCESS_TOKEN`
- Live fake-provider regression resolved the actual MetadataPolicy C and preserved RecognitionType C
- A/B/C policy mappings and C → Metadata C / Naming A / Classification A / Organize A passed
- Strategy CLI/configuration suite: 16 passed
- Full suite: 172 tests, 169 passed, 0 failed, 3 skipped
- Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls: all zero

Phase 9 NamingPolicy and NamingEngine validation (2026-08-19): PASS

- Added immutable NamingTemplate, NamingPolicy, NamingContext, NamingResult, and unified NamingError
  models plus NamingPolicyRegistry, SafeTemplateRenderer, NameSanitizer, NamingEngine, and
  NamingPreviewService
- Safe DSL supports all required variables, `{season:02}`/`{episode:02}` numeric formatting, and no
  arbitrary expressions, conversions, code execution, or path separators in template literals
- Movie, TV, season/episode zero, contiguous/non-contiguous multi-episode, provider-ID, release-tag,
  missing-variable, Unicode, reserved-name, traversal, absolute-path, and long-component cases passed
- Naming table: 50 representative title cases plus focused policy/format/integration cases passed
- C resolved NamingPolicy A while RecognitionType remained C through naming preview
- Parse → Recognition → Metadata → Naming integration produced only relative naming components;
  Naming added zero MetadataProvider calls and all Storage mutation counters remained zero
- Naming suite: 11 test methods passed
- Full suite: 183 tests, 180 passed, 0 failed, 3 skipped
- Strategy CLI: 16 passed; Metadata: 21 passed; Recognition: 15 passed; Parser: 6 passed;
  Scanner/FileIndex: 24 passed; DryRun: 3 passed
- Storage regression: 83 tests, 80 passed, 0 failed, 3 skipped
- `ruff format --check mediaflow tests`: passed, 47 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Naming Storage/network/Classification/Organizer and unsafe-template audits: passed
- FFmpeg/FFprobe runtime dependency audit: passed

Phase 9.1 Naming Preview CLI validation (2026-08-19): PASS

- Added `--show-naming` to existing single-path, directory, offline, live metadata, and case-file
  strategy-test flows; no second parser/recognition/metadata/naming implementation was introduced
- Live preview resolves the configured NamingPolicy and calls production NamingPreviewService;
  offline preview explicitly skips naming when no MediaIdentity exists
- Detailed output includes parser, recognition, metadata, exact NamingResult strings/variables/
  sanitization/warnings, C identity preservation, and safety counters
- Directory output includes compact PASS/WARN/ERROR rows plus Naming OK, warnings, metadata
  confirmation/not-found, naming-error, and other-error totals; `--limit` remains Scanner cancellation
- Starter strategy corpus: 14 passed, 0 failed, 0 skipped, including movie/TV/multi-episode/Unicode/
  provider-ID naming expectations
- Provider-specific `哈姆奈特 (2025) [tmdbid-858024]` preview passed using an injected NamingPolicy
  template; the prefix is not present in NamingEngine
- Naming Preview CLI suite: 6 passed; Strategy CLI suite: 16 passed; Naming suite: 11 passed
- Full suite: 189 tests, 186 passed, 0 failed, 3 skipped
- Metadata: 21 passed; Recognition: 15 passed; Parser: 6 passed; Scanner/FileIndex: 24 passed;
  DryRun: 3 passed
- Storage regression: 83 tests, 80 passed, 0 failed, 3 skipped
- Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink: zero; Classification and Organizer
  executions: zero
- `ruff format --check mediaflow tests`: passed, 48 files compliant
- `ruff check mediaflow tests`, `compileall`, `pip check`, and wheel build: passed
- FFmpeg/FFprobe, downstream execution, unsafe-template, and diff checks: passed

Phase 9.1 real-world Recognition configuration validation (2026-08-19): PASS

- Split `/A/` `/B/` `/C/` smoke fixtures from ResourceLibrary-based development rules and
  JSON-backed user configuration
- Added `--config`, `MEDIAFLOW_STRATEGY_CONFIG`, and explicit `--resource-library-id` support
- User JSON loads RecognitionTypes, RecognitionRules, nested/atomic conditions,
  RecognitionTypePolicies, and scan-root → ResourceLibrary bindings into production domain models
- Directory Scanner now propagates configured ResourceLibrary/storage identity into FileContext;
  CLI traversal remains delegated entirely to StorageScanner
- Real movie library → A, TV library → B, special rule → C, and unmatched → Unrecognized passed;
  no implicit default A exists
- C continued to resolve Metadata C / Naming A / Classification A / Organize A and remained C
- Configuration integration suite: 6 passed
- Full suite: 195 tests, 192 passed, 0 failed, 3 skipped
- Complete configured directory scan Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink: zero
- Installed CLI recognized the documented real Hamnet path as A using explicit
  `resourceLibraryId=movies`; matched rule was `movie-library`
- `ruff format --check mediaflow tests`: passed, 50 files compliant
- `ruff check`, `compileall`, `pip check`, wheel build, FFmpeg/FFprobe, hidden-default, CLI traversal,
  and diff audits: passed

Phase 9.1 single-file ResourceLibrary context validation (2026-08-19): PASS

- Single-file mode now resolves the most specific configured ResourceLibrary root through the same
  resolver used by directory mode and passes its ID into FileContext/RecognitionContext
- Added preferred `--resource-library ID` with backward-compatible `--resource-library-id ID`
- Same real movie file in directory and single-file modes resolved `movie-library → A`
- Explicit movies → A and special → C passed; C retained Metadata C / Naming A / Classification A /
  Organize A and remained C
- Unbound path remained Unrecognized with no hidden default A
- Configuration/context suite: 7 passed
- Full suite: 196 tests, 193 passed, 0 failed, 3 skipped
- Single-file and configured directory Storage mutation counts: zero

Phase 9.1 localized CandidateMatcher validation (2026-08-19): PASS

- CandidateMatcher now scores every parser primary/alternative title against provider display,
  original, and alternative/localized titles and exposes the winning pair/source in CLI evidence
- Added bounded two-stage enrichment: at most two plausible search candidates by default receive
  cached detail lookup; the per-identification provider request budget remains authoritative
- TMDB detail enrichment reuses the existing documented `append_to_response` request for
  alternative titles and external IDs; no per-result unbounded request fan-out was introduced
- `哈姆奈特` → `Hamnet` with provider alternative title `哈姆奈特` and `千与千寻` localized-title
  regressions passed; same-year unrelated titles remain `not_found`
- Wrong-first/correct-later, ambiguous alias, English title, original title, explicit provider-ID,
  and RecognitionType C preservation regressions passed
- Strategy CLI displays matched provider title and `alternative/localized title` source; Naming is
  still preview-only and Storage mutations remain zero
- Metadata suite: 26 passed; full suite: 202 tests, 199 passed, 0 failed, 3 skipped
- `ruff check mediaflow tests` and `ruff format --check mediaflow tests`: passed
- `compileall`, `pip check`, setuptools wheel build, FFmpeg/FFprobe runtime audit, and
  `git diff --check`: passed

Phase 9.1 TMDB translation pipeline completion (2026-08-19): PASS

- Confirmed the incomplete path: TMDB search matched translated titles but did not expose the
  matching string, and the previous detail request included alternatives but not translations
- MetadataPolicy A previously had `language=None` unless `TMDB_LANGUAGE` was set, yielding the
  TMDB `en-US` fallback; defaults now state `en-US` and JSON supports per-policy locale/budgets
- Repository A/B/C policies now use `language=zh-CN`, `region=CN`, and two bounded enrichments; CLI
  prints the effective query language and region
- Cached details append `translations,alternative_titles,external_ids` once and map translation
  titles into provider-neutral domain evidence
- Exact `哈姆奈特` translation evidence scores title 65 plus year 20 and media type 5; same-year
  candidates lacking provider title evidence remain `not_found`
- zh-CN request propagation, cache reuse, `千与千寻`, English/original/alternative titles,
  ambiguity, wrong-first, direct provider ID, C preservation, and CLI evidence regressions passed
- Full suite: 203 tests, 200 passed, 0 failed, 3 skipped

Phase 9.1 canonical/regional movie-year validation (2026-08-19): PASS

- Traced the incorrect 2019 value to `search/movie` response `release_date`; it did not originate
  from movie details. TMDB region support documents this as regional presentation data
- Added provider-neutral canonical and regional release-date semantics; CandidateMatcher scores
  only canonical year and displays regional year as zero-point informational evidence
- Region-aware movie search no longer maps its displayed release date into canonical `year`;
  bounded cached detail enrichment supplies the canonical details year before final matching
- `千与千寻 (2001)` selects TMDB 129 over 535075 with exact title and canonical-year evidence while
  preserving regional year 2019 for audit output
- Strict `primary_release_year` search remains first; an empty strict movie search performs one
  bounded relaxed pass without the year filter
- Same-title remakes, regional filename year, missing local year, provider ID, TV first-air year,
  RecognitionType C, zero mutation, and preview-only regressions remain covered
- Full suite: 211 tests, 208 passed, 0 failed, 3 skipped

Phase 10 ClassificationPolicy and ClassificationEngine validation (2026-08-20): PASS

- Added immutable ClassificationPolicy, ClassificationRule, ClassificationContext,
  ClassificationResult/status/error models and application registry/engine/preview service
- Rules support media type, genre, country, language, canonical year ranges, and keywords; fields
  combine with AND and alternatives within a field combine with OR
- Higher priority wins; equal priority uses stable rule ID ordering and remains deterministic when
  input rule order is reversed
- Explicit movie animation/action, TV, and higher-priority Japanese animation examples passed
- No match returns `unclassified` with no selected MediaLibrary/path; disabled or missing policies
  fail explicitly and unsafe relative category paths are rejected
- Strategy CLI supports `--show-classification`, including detailed and directory preview output;
  classification is executed only after a MediaIdentity exists
- C resolved Metadata C / Naming A / Classification A / Organize A, used Classification A, and
  remained RecognitionType C
- Classification has no Storage or Organizer dependency; preview mutation counters remained zero
- Classification suite: 10 passed; full suite: 221 tests, 218 passed, 0 failed, 3 skipped
- Parser, Recognition, CandidateMatcher/Metadata/TMDB, Naming, Strategy CLI, Scanner/FileIndex,
  Local/SMB/OpenList/S3/R2 Storage, and Planner/DryRun regressions all passed
- `ruff check`, `ruff format --check`, `compileall`, `pip check`, setuptools wheel build,
  FFmpeg/FFprobe runtime audit, and `git diff --check`: passed

Phase 11 OrganizePlan and conflict detection validation (2026-08-20): PASS

- Extended the immutable OrganizePlan with MOVE/COPY/LINK/NOOP/SKIP operation, status, warnings,
  domain inputs, and typed conflict records while retaining the Phase 0 compatibility fields
- Destination construction includes MediaLibrary root, Classification relative path, all Naming
  directory segments, and filename; traversal, absolute downstream paths, NULs, and invalid
  components yield SKIP/INVALID_DESTINATION without an unsafe destination
- Same-storage same-path plans become NOOP; optional read-only observations detect
  DESTINATION_EXISTS, TARGET_COLLISION, and provider-ID DUPLICATE_MEDIA independently
- Conflicts remain unresolved and Phase 11 plans contain no executable mutation command list
- Strategy CLI supports `--show-plan` and reports operation/source/destination/conflicts plus
  `Execution: NOT EXECUTED`; Naming and Classification are reused without downstream execution
- C continued to use Metadata C / Naming A / Classification A / Organize A and remained C
- Planner/DryRun suite: 9 passed; Strategy CLI suite: 19 passed
- Full suite: 228 tests, 225 passed, 0 failed, 3 optional integration tests skipped
- Storage Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink and Organizer executions: zero
- `ruff check`, `ruff format --check`, `compileall`, `pip check`, and isolated-free wheel build:
  passed

Phase 10 real-world classification metadata wiring fix (2026-08-20): PASS

- Verified ClassificationPolicyRegistry and strategy-test bootstrap load development policies A/B
  and pass the final MediaIdentity unchanged into ClassificationContext
- Root cause was TMDB-localized genre display names: `language=zh-CN` may return `动画` for stable
  genre ID 16 while the provider-neutral development rule uses `Animation`
- TMDB infrastructure now normalizes known stable genre IDs before creating MediaIdentity; country
  evidence remains stable ISO codes such as JP, which policy A already accepts
- Added a real-shaped TMDB details regression proving movie + Animation + JP selects Movies/Anime
- Strategy output now exposes selected genres and countries for configuration diagnosis
- ClassificationEngine behavior was not changed; Storage mutations remained zero
- Targeted Metadata/Classification/Strategy suite: 63 passed; full suite: 229 tests, 226 passed,
  0 failed, 3 optional integrations skipped; lint, formatter, compile, dependency, wheel build, and
  diff checks passed

Phase 11 absolute MediaLibrary-root safety validation (2026-08-20): PASS

- Separated configured destination-root validation from strict downstream relative-path validation
- Absolute MediaLibrary roots such as `/media/Movies` are accepted and normalized; trailing
  separators no longer cause a false INVALID_DESTINATION
- Classification paths, Naming directory segments, and filenames remain strictly relative;
  absolute and traversal inputs produce SKIP/INVALID_DESTINATION with no target
- Added absolute-root acceptance, absolute Classification rejection, and Naming traversal tests;
  planning still emits no executable operations and Storage mutations remain zero
- Planner suite: 12 passed; full suite: 232 tests, 229 passed, 0 failed, 3 optional integrations
  skipped; lint, formatter, compile, dependency, wheel build, and diff checks passed

Phase 12 OrganizerExecutor and ExecutionResult validation (2026-08-20): PASS

- Added immutable SUCCESS/DRY_RUN/FAILED/PARTIAL/SKIPPED ExecutionResult with stable plan ID,
  timestamps, duration, created directories, completed operations, warnings, and errors
- OrganizerExecutor defaults to dry-run and does not access Storage unless `execute=True` is
  explicitly supplied
- MOVE/COPY/HARD_LINK/SOFT_LINK use Storage only; same-storage operations use adapter primitives
  and cross-storage MOVE copies, verifies, then deletes the source
- Real execution rejects invalid destinations, missing sources, existing targets, unresolved
  conflicts, NOOP/SKIP plans, missing Storage registrations, and unsupported cross-storage links
- The Phase 12 developer Strategy CLI adds `--execute` for one explicit file and requires
  `--show-plan` plus an existing `--execution-root` or `MEDIAFLOW_EXECUTION_ROOT`; its directory
  execution remains disabled (the later production `mediaflow` batch CLI supports it)
- Execution preview/result output includes mode, status, paths, completed work, errors, and duration
- Dry-run MOVE/COPY/LINK mutation count remained zero; LocalStorage move/copy/link and partial
  execution regressions passed
- Cross-storage MOVE delete failure records the verified target copy as completed, preserves the
  source, and returns PARTIAL rather than incorrectly reporting a pre-mutation failure
- Executor/Planner suite: 18 passed; full suite: 239 tests, 236 passed, 0 failed, 3 optional
  integrations skipped; lint, formatter, compile, dependency, wheel build, FFmpeg/FFprobe, and
  diff checks passed

Phase 12.2 real OrganizerExecutor validation (2026-08-20): PASS

- OrganizePlan now preserves both the configured MediaLibrary root and the strictly relative
  destination while retaining its backward-compatible combined target
- OrganizerExecutor independently recombines root + relative destination and rejects a tampered or
  inconsistent target before accessing Storage
- Explicit real MOVE, COPY, hard-link, and soft-link paths remain Storage-only; no filesystem API
  was introduced in application/domain code
- Added permission-denied and target-tampering regressions alongside missing source, existing
  destination, invalid path, conflict, partial execution, and explicit CLI execution coverage
- Final execution logs include completed mutation operations and errors in addition to timestamp,
  plan ID, operation, source, destination, and result
- Executor/Planner suite: 20 passed; full suite: 241 tests, 238 passed, 0 failed, 3 optional
  integrations skipped; lint, formatter, compile, dependency, wheel build, FFmpeg/FFprobe, and
  diff checks passed

Phase 12.2 absolute-source execution wiring fix (2026-08-20): PASS

- OrganizePlan now remains the audit/portability boundary: source preserves the original absolute
  input, destination remains relative to the execution Storage root, and execution-root is absent
  from the plan
- CLI no longer rewrites `OrganizePlan.source` to a Storage-relative path; it passes the adapter's
  logical source path separately to OrganizerExecutor
- ExecutionResult adds `resolved_destination`, showing execution-root + portable destination for
  both DryRun and Execute output
- `--execution-root` is now permitted with `--show-plan` without `--execute`, enabling full target
  validation while retaining zero Storage access/mutation
- Added absolute source preservation, relative destination, resolved DryRun destination, real
  source discovery/execution, and missing-source regression coverage
- Full suite: 242 tests, 239 passed, 0 failed, 3 optional integrations skipped; lint, formatter,
  compile, dependency, wheel build, and diff checks passed

Phase 13 final integration and production-readiness validation (2026-08-20): PASS

- Added MediaOrganizerService for single-file and Scanner-backed batch orchestration without
  duplicating stage business logic
- Batch extension/ignore/recursive behavior remains owned by Scanner; item failures are isolated,
  progress is reported, and summary totals include matched/conflicts/moved/failed
- Added JSON Lines operation history domain port/adapter with Unicode-safe persistent records
- Added runtime configuration for Storage definitions, ResourceLibrary/MediaLibrary bindings,
  Metadata, Naming, Classification, history, and environment-owned provider secrets
- Added `mediaflow analyze`, `preview`, and `organize`; all default to read-only analysis/DryRun and
  only `organize --execute` passes real mutation authority
- Added final movie/TV/anime/Unicode/unknown/ambiguous-conflict regression data and end-to-end
  LocalStorage batch tests
- Final dataset: 7 passed, 0 failed; integration/history/logging suite: 4 passed
- Full suite: 246 tests, 243 passed, 0 failed, 3 optional external integrations skipped
- `ruff check`, `ruff format --check`, compileall, dependency check, wheel build, FFmpeg/FFprobe
  runtime audit, and diff checks passed

Runtime strategy configuration production-readiness (2026-08-20): PASS

- Runtime loading now requires and normalizes all six strategy catalogs from `MEDIAFLOW_CONFIG`;
  production no longer inherits A/B/C content from Python development defaults
- Added independent OrganizePolicy loading with MOVE/COPY/HARDLINK/SYMLINK validation and no
  implicit MOVE fallback
- Naming templates and nested Classification conditions/results are externally configurable and
  validated by existing engine safety boundaries
- Startup now validates every policy, MediaLibrary, Storage, RecognitionType, and rule reference
  before scanning; `mediaflow config validate` performs this path with zero Storage mutation
- `config/strategy.example.json` is the canonical A/B/C source and preserves C -> Metadata C plus
  Naming/Classification/Organize A without changing RecognitionType C

Phase 13.2 ResourceLibrary-driven organization pipeline (2026-08-20): PASS

- Added ResourceLibraryScanner to scan every enabled configured library through the existing
  Storage-neutral Scanner without accumulating the complete library
- Added MediaLibraryResolver for ClassificationResult -> MediaLibrary -> Storage resolution
- OrganizePlan now carries storage-aware source/destination locations while preserving legacy
  display fields; Executor consumes relative Storage paths
- Added no-path `mediaflow scan`, `preview`, and `organize`; execution remains explicitly gated by
  `organize --execute`
- Runtime Storage factory now supports OpenList non-secret JSON settings with environment-owned
  tokens; Local/OpenList direction combinations use the same pipeline
- Local scan, mock OpenList scan, MediaLibrary resolution, Local/OpenList four-direction transfer,
  zero-mutation DryRun, and no-path CLI scan regressions passed

OpenList combined directory/name MOVE completion (2026-08-21): PASS

- Completed same-OpenList MOVE when organization changes both parent directory and filename using
  native server-side Move followed by Rename, without streaming media through MediaFlow
- Rename failure triggers a best-effort server-side move back to the source path; rollback failure
  reports an explicit I/O error and leaves the file at the known intermediate destination
- OrganizerExecutor and OrganizePlan were unchanged
- OpenList/Organizer/ResourceLibrary targeted suite: 47 passed, 1 optional integration skipped;
  full suite: 258 tests, 255 passed, 0 failed, 3 optional integrations skipped
- Ruff lint/format, compileall, dependency check, FFmpeg/FFprobe audit, and diff check passed

Documentation and examples synchronization (2026-08-21): PASS

- Updated README and configuration/architecture documentation for the current no-path production
  workflow, portable StorageLocation model, path-field semantics, and explicit execution boundary
- Updated the canonical A/B/C strategy example to use one ResourceLibrary with path/extension
  recognition rules, including foreign/other movie classification fallbacks
- Expanded the comprehensive Phase 13.2 template with cross-storage identity and current OpenList
  native Move→Rename semantics; example JSON and both runtime examples validate successfully
- ResourceLibrary `displayRootPath` is optional; legacy `rootPath` remains a compatibility alias,
  while no-path discovery depends only on `storageId` plus `storagePath`

Requirements baseline and roadmap review (2026-08-21): PASS

- Promoted the product specification to V1.1 with explicit completed/partial/unstarted status,
  current path/Storage identity semantics, and a verified implementation baseline
- Added `docs/roadmap.md` with the current-node analysis, capability matrix, Phases 14–19, Phase 14
  acceptance direction, and continuous safety baseline
- Identified persistent FileIndex/task/result state and restart-safe recovery as the next blocking
  production-readiness milestone; no strategy engine redesign is planned

Phase 14 persistent FileIndex and recoverable task foundation (2026-08-21): PASS

- Production `mediaflow scan`, `preview`, and `organize` now share the configured SQLite FileIndex;
  cross-process New/Unchanged and stability evidence persist while Scanner semantics remain intact
- Added versioned SQLite Task, TaskItem, ResultRecord, and file-lock persistence behind domain ports
- Added `mediaflow tasks list|show|resume|retry-failed`; retries create a new auditable task and
  require both original execute authorization and a fresh `--execute` for mutation
- Result-before-terminal persistence plus successful-result filtering prevents a crash window from
  blindly repeating an already successful Storage operation
- Atomic `StorageID + normalized relative path` locks reject concurrent source processing; explicit
  stale-task recovery and cancellation reclaim only the selected task's locks
- Existing JSONL history remains compatible and is never silently migrated or deleted
- Full suite: 268 tests, 265 passed, 0 failed, 3 optional integrations skipped
- Ruff lint/format, compileall, dependency check, wheel build, config validation,
  FFmpeg/FFprobe audit, and diff check passed
