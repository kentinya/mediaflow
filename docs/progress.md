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

- Phase 19.8 persistent redacted operational log foundation: PASS
- Phase 19.9 read-only operational log API and UI: PASS
- Phase 19.10 safe runtime database backup and verification: PASS
- Phase 19.11 reproducible release validation and CI baseline: PASS
- Phase 19.12 read-only upgrade preflight and compatibility report: PASS
- Phase 19.13 non-overwriting offline runtime database restore: PASS
- Phase 19.14 cooperative runtime maintenance lock: PASS
- Phase 19.15 isolated runtime schema migration rehearsal: PASS
- Phase 19.16 read-only configuration and system status API/UI: PASS
- Phase 19.17 explicit Automation Job cancellation UI: PASS
- Phase 19.18 explicit DryRun Automation Job submission UI: PASS
- Phase 19.19 durable active Automation Job admission control: PASS
- Phase 19.20 read-only stale Running Automation Job visibility: PASS
- Phase 19.21 fenced cooperative Automation Job heartbeats: PASS
- Phase 19 overall production acceptance: BLOCKED on real remote Storage matrix, cross-provider
  fault injection, and long-duration validation

## Planned

- Phase 19: Web UI and production release hardening
- Later: database-managed identities/OIDC, credential rotation, and optional scheduled execution

## Known Issues

- Cross-storage links are unsupported; cross-storage COPY/MOVE use bounded streaming transfer
- LocalStorage link capabilities still depend on the host filesystem
- No static type checker is configured; typed source receives compile validation only
- LocalStorage write/copy use same-directory atomic target publication, but power-loss durability and
  multi-file/source+target transactions are not certified. Remote adapter atomic publication remains
  unverified against real services.
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

Phase 15 conflict decisions and persistent NeedConfirm (2026-08-22): IMPLEMENTED

- Added configuration-driven Skip/Rename/Manual/Overwrite conflict strategies; default remains
  Manual and legacy overwrite configuration is validated for contradictions
- Added a mutation-free ConflictResolver with bounded deterministic Rename and explicit high-risk
  Overwrite authorization; invalid destinations remain non-overridable
- Upgraded runtime SQLite schema to v2 with persistent confirmation records and append-only decision
  audits; conflicted task items now enter `waiting_confirm` and are excluded from blind retry
- Added `mediaflow confirmations list|show|resolve` commands; all confirmation operations are
  persistence-only and never access media Storage
- Duplicate identity now includes provider, media type, season, and normalized episode set
- Full suite: 277 tests, 274 passed, 0 failed, 3 optional external integrations skipped
- Ruff lint/format, compileall, dependency check, isolated wheel build, configuration validation,
  FFmpeg/FFprobe runtime audit, and diff checks passed

Phase 16 attachments and atomic media file sets (2026-08-22): PASS

- Added opt-in AttachmentPolicy plus immutable MediaFileSet, MediaAttachment, and AttachmentPlan
  models without changing Parser, Recognition, Metadata, Naming, or Classification semantics
- Added one-directory, Storage-only discovery for subtitles, NFO, poster/fanart, related images,
  trailers, and explicitly enabled other same-stem files; unknown files remain untouched
- Attachment planning derives safe named destinations, preserves subtitle language/Forced/SDH/HI
  suffixes, detects destination conflicts, and remains read-only
- OrganizerExecutor preflights the complete file set, executes attachments before the primary, and
  records exact completed steps on PARTIAL outcomes with no operation fallback
- Runtime SQLite schema v3 persists completed operations and attachment count for recovery evidence
- Full suite: 287 tests, 284 passed, 0 failed, 3 optional external integrations skipped
- Ruff lint/format, compileall, dependency check, isolated wheel build, configuration validation,
  FFmpeg/FFprobe runtime audit, and diff checks passed

Phase 16 example configuration synchronization (2026-08-22): PASS

- Reformatted the safe starter OrganizePolicies so every attachment field is directly editable
- Expanded the exhaustive MOVE/COPY/HARDLINK/SYMLINK catalog with current attachment controls
- Kept starter attachment execution disabled by default and documented which example is safe versus
  exhaustive

Phase 17 runtime Storage adapters and read-only preflight (2026-08-22): PASS

- Added JSON Runtime construction for existing SMBStorage and AWS S3/Cloudflare R2/generic
  S3-compatible adapters without changing adapter or business semantics
- Credentials resolve only from validated environment-variable names; literal secret fields are
  rejected and configuration validation needs neither secret values nor network access
- Added `mediaflow storage list|check`; listing constructs nothing, checks use only existing
  health/connect/list operations, isolate failures, and perform zero mutation
- Expanded the exhaustive configuration catalog with Local/OpenList/SMB/S3/R2 examples
- Full suite: 295 tests, 292 passed, 0 failed, 3 optional real integrations skipped
- Ruff lint/format, compileall, dependency check, isolated wheel build, configuration validation,
  FFmpeg/FFprobe runtime audit, and diff checks passed

Phase 18.1 read-only REST API and persistent DryRun worker (2026-08-22): PASS

- Added durable scan/preview AutomationJobs and atomic oldest-first SQLite schema-v4 claiming
- Added pending-only cancellation and a one-job Worker that delegates to the existing production
  workflows rather than duplicating Scanner, strategy, planning, or DryRun behavior
- Added authenticated Task/Job/Confirmation queries and scan/preview submission plus public health;
  unsupported commands and every remote execute-related field are rejected
- API validation needs no secret value, startup resolves its bearer token from the named environment
  variable, persisted failures are redacted, and API queries construct no Storage adapters
- Added `mediaflow jobs ...`, `mediaflow worker run-next`, and loopback development API commands
- Full suite: 307 tests, 304 passed, 0 failed, 3 optional real integrations skipped

Phase 18.2 resident Worker, cooperative cancellation, and interval Scheduler (2026-08-22): PASS

- Upgraded SQLite runtime schema to v5 with durable cancellation requests, schedule provenance,
  and idempotent next-run state
- Running cancellation propagates through Worker into ResourceLibrary scan/batch orchestration and
  stops before another item begins; pending cancellation remains immediate
- Added bounded resident Worker/Scheduler loops with graceful SIGINT/SIGTERM shutdown and isolated
  job failures; preview remains DryRun
- Added explicit age-guarded stale inspection/requeue with no automatic recovery of uncertain work
- Added configuration-driven scan/preview interval schedules, CLI controls, and authenticated
  read-only schedule API output; organize/execute schedule configuration is rejected
- Full suite: 318 tests, 315 passed, 0 failed, 3 optional real integrations skipped

Phase 18.3 Cron/time-zone Scheduler and immutable schedule audit (2026-08-22): PASS

- Added a bounded five-field numeric Cron parser with wildcard/list/range/step validation and
  explicit day-of-month/day-of-week OR semantics
- Added IANA zoneinfo evaluation, UTC persistence, leap/month/year handling, nonexistent DST-time
  skipping, and deterministic single emission for ambiguous wall times
- Generalized Runtime schedules to exactly one interval or Cron timing mode while preserving
  interval configuration and state compatibility
- Upgraded SQLite runtime schema to v6 with append-only schedule occurrence audit; conditional state
  advancement prevents duplicate concurrent/restart emission and missed occurrences coalesce
- Added CLI/API schedule audit and UTC/local schedule visibility with zero Storage/provider access
- Full suite: 329 tests, 326 passed, 0 failed, 3 optional real integrations skipped

Phase 18.4 durable notification Outbox and signed Webhooks (2026-08-22): PASS

- Added SQLite v7 durable, idempotent per-target deliveries with atomic due claiming, bounded retry
  state, dead-letter, and explicit dead-letter requeue
- Added environment-secret HMAC-SHA256 Webhook delivery over validated HTTPS URLs; exact canonical
  UTF-8 bodies are signed and redirects are not followed
- Automation terminal states and durable Scheduler emissions publish subscribed events without
  changing successful Job/Schedule state when notification publication or delivery fails
- Added independent notification Worker, redacted CLI listing/requeue, and authenticated read-only
  API visibility; no notification path can call Storage or OrganizerExecutor
- Canonical and exhaustive examples include a disabled safe Webhook template
- Full suite: 339 tests, 336 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe audit,
  and diff check passed

Phase 18.4.1 notification delivery lease and crash recovery (2026-08-22): PASS

- Added configurable bounded delivery leases with automatic reclaim only after expiry
- Reclaimed deliveries preserve stable delivery/event/body identity and increment attempts; fresh
  claims remain exclusive and exhausted failures enter the existing dead-letter flow
- Added read-only stale-claim inspection and documented at-least-once receiver deduplication
- Full suite: 342 tests, 339 passed, 0 failed, 3 optional real integrations skipped; formatter,
  lint, compile, dependency, build, configuration, FFmpeg/FFprobe, and diff checks passed

Phase 18.5 one-time remote execute authorization and audit (2026-08-22): PASS

- Added disabled-by-default, locally issued short-lived single-use execution authorizations;
  SQLite stores only token SHA-256 digests, constraints, status, consumption, and audit
- SQLite v8 atomically consumes one ticket and creates one execute-authorized organize Job, including
  concurrent replay protection and compatible Job authority migration
- API requires ordinary Bearer plus a separate header token, explicit execute=true, and bounded
  limit; it cannot issue/manage tickets or bypass overwrite/delete/conflict safety
- Worker passes --execute only from persisted organize authority; Scheduler remains scan/preview-only
- Full suite: 353 tests, 350 passed, 0 failed, 3 optional real integrations skipped
- Ruff format/lint, compileall, dependency check, isolated-free wheel build, both example config
  validations, FFmpeg/FFprobe runtime audit, and diff check passed

Phase 18.6 API principals, RBAC, and security audit (2026-08-22): PASS

- Replaced the single runtime API identity with configuration-driven principals and fixed
  least-privilege viewer/operator/executor/auditor/admin roles; legacy `api.tokenEnv` remains a
  non-mixable admin compatibility form
- Added route-level 401/403 authorization while preserving the independent Phase 18.5 one-time
  authorization requirement for every remote real organize Job
- Upgraded runtime SQLite to v9 with redacted normalized API security audit records and fail-closed
  pre-dispatch persistence before Job mutation
- Added auditor/admin API visibility and a local zero-Storage `security-audit list` command
- Full suite: 361 tests, 358 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 18.7 operational Dashboard read model (2026-08-22): PASS

- Added immutable provider-neutral dashboard counts and bounded categorical recent-failure records
- Added aggregate SQLite reads for FileIndex, Tasks, Jobs, pending confirmations, and notification
  dead letters without enumerating large libraries or creating a missing FileIndex table
- Added zero-Storage `mediaflow dashboard` and viewer-readable `/api/v1/dashboard`; API access is
  included in the existing normalized security audit
- Full suite: 365 tests, 362 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 18.8 conflict confirmation service API (2026-08-22): PASS

- Added bounded pending/resolved/all confirmation list, show, and immutable decision-audit API reads
- Added explicit `resolve_confirmation` permission for operator/executor/admin and remote Skip/Rename
  decisions with authenticated principal identity; viewer/auditor remain read-only
- Confirmation, decision audit, and waiting TaskItem transition now commit atomically for CLI/API;
  concurrency and injected persistence failure fail safely
- Remote Manual/Overwrite, destination editing, actor injection, Job creation, automatic retry, and
  all Storage/Organizer execution remain forbidden
- Full suite: 371 tests, 368 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 18.9 persistent metadata review queue (2026-08-22): PASS

- Added bounded provider-neutral NeedConfirm/Ambiguous snapshots with one durable review per
  TaskItem and preserved RecognitionType context
- Added SQLite v10 atomic review/candidate creation plus `waiting_metadata` TaskItem transition;
  waiting items release their source lock and are excluded from blind retry
- Added zero-Storage/provider CLI and authenticated API list/show visibility plus Dashboard pending
  count; no candidate selection, Job creation, automatic resume, or execution is permitted
- Full suite: 377 tests, 374 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 18.10 explicit metadata review resolution and recovery (2026-08-22): PASS

- Added rank-only metadata candidate decisions, immutable audit, and atomic resolved-review plus
  waiting-to-pending TaskItem transition in SQLite v11
- Added operator/executor/admin CLI/API resolution while viewer/auditor remain read-only; selection
  performs zero Storage/provider calls and never creates or resumes a Task/Job
- Explicit Task resume validates RecognitionType/policy/provider/media type and uses the existing
  provider-ID details flow; C remains C and execution authority cannot be widened
- Full suite: 385 tests, 382 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 18.11 classification review queue and explicit rule selection (2026-08-22): PASS

- Added bounded configured-rule snapshots for unclassified items, source-lock release, and
  `waiting_classification` Task semantics
- Added SQLite v12 atomic review creation/resolution and immutable decision audit with concurrent
  single-commit behavior
- Added operator/executor/admin CLI/API resolution and Dashboard count; arbitrary destination input,
  automatic resume, Storage/provider construction, Job creation, and execution remain forbidden
- Explicit resume revalidates current RecognitionType/policy/rule/library/path; C remains C
- Full suite: 394 tests, 391 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.1 minimal secure operator Web UI (2026-08-22): PASS

- Added a dependency-free same-origin `/ui/` shell to the existing WSGI service with strict CSP,
  no-store caching, no external assets, and in-memory-only bearer credentials
- Added Dashboard and bounded conflict/metadata/classification review list/detail views using only
  existing authenticated APIs
- Restricted UI decisions to conflict Skip/Rename and persisted candidate/choice ranks; Task/Job,
  execute, Overwrite, arbitrary identifiers/paths, and automatic resume remain unavailable
- Added static-route zero-repository tests plus credential, rendering, request-bound and payload
  safety regressions
- Full suite: 398 tests, 395 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.2 API credential lifecycle and HTTP deployment guardrails (2026-08-22): PASS

- Added cryptographic one-time stdout Token generation with bounded 32–128 byte entropy selection
- Added redacted config-only Principal credential status with enabled SET/UNSET failure semantics
- Added loopback-by-default listener validation and explicit warning acknowledgement for non-loopback
  unencrypted HTTP
- Hardened JSON responses and bounded Bearer parsing without changing RBAC or execute authorization
- Added focused generation/status/host/header/authentication safety regressions
- Full suite: 404 tests, 401 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.3 read-only Task, Job, and Result observability UI (2026-08-22): PASS

- Added bounded Task/Job collection queries and independently bounded TaskItem/Result detail reads
- SQLite uses limit+1 deterministic queries to report truncation without loading whole batches
- Added read-only Task/Job UI tabs, linked navigation, item/result tables, and truncation notices
- Added API query validation, SQL-bound verification, UI safety, and no-control regressions
- Full suite: 407 tests, 404 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.4 stable cursor pagination for operational history (2026-08-22): PASS

- Added strict resource-scoped URL-safe operational cursors containing only timestamp and stable ID
- Added composite keyset pagination for Task/Job newest-first and TaskItem/Result oldest-first reads
- Added independent UI Next controls for collections and Task detail while preserving first-page
  refresh and all read-only boundaries
- Added same-timestamp, concurrent insertion, end-page, SQL-bound, malformed/cross-kind, audit, and
  no-write regressions
- Full suite: 411 tests, 408 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.5 bidirectional stable cursor pagination (2026-08-22): PASS

- Added strict directional v2 cursors while retaining Phase 19.4 v1 forward compatibility
- Added reverse keyset queries for Task, Job, TaskItem, and Result with canonical ordering restored
  after bounded `limit + 1` reads; no OFFSET, total query, or prior-row enumeration is used
- Added Previous/Next collection controls and independent Previous/Next TaskItem/Result controls
- Verified same-timestamp first/middle/last round trips, independent detail cursors, malformed cursor
  rejection, read-only UI boundaries, and existing operational regressions
- Full suite: 414 tests, 411 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.6 read-only Scheduler and Notification operations UI (2026-08-22): PASS

- Added strict 1–100 schedule-audit and notification limits plus existing-status notification filters;
  malformed, blank, duplicate, unknown, and injected query fields fail before repository reads
- Added safe Scheduler definition/state and bounded occurrence-audit views to the operator UI
- Added explicit-refresh Notification delivery visibility without URL, body, signature, headers,
  response body, raw exception, media path, credentials, requeue, delivery, or worker controls
- Preserved RBAC/security audit, text-node rendering, no polling, and zero Storage/provider/workflow/
  Scheduler-tick/notification-worker/Organizer construction boundaries
- Full suite: 417 tests, 414 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.7 bidirectional Notification and Schedule Audit pagination (2026-08-22): PASS

- Extended strict v2 directional cursors to NotificationDelivery and per-schedule ScheduleAudit
- Bound opaque cursor scope to notification status (including `all`) or schedule ID, preventing safe
  cursor reuse across filters/schedules without exposing those configured values
- Added newest-first forward/reverse composite-key SQLite queries with bounded `limit + 1`, canonical
  order restoration, and no OFFSET, total scan, or prior-row enumeration
- Added Previous/Next UI navigation that preserves notification status and schedule detail context;
  explicit refresh/status changes reset to the first page and no polling or controls were added
- Full suite: 420 tests, 417 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.8 persistent redacted operational log foundation (2026-08-22): PASS

- Added immutable structured OperationalLog records and SQLite v13 persistence with bounded
  newest-first reads, minimum-level filtering, deterministic ordering, and reopen/migration coverage
- Added a closed-event Logger adapter that persists only validated Task/Job/Plan/status identifiers;
  paths, titles, raw errors, provider/HTTP values, arbitrary context, and credentials are discarded
- Added default-disabled runtime configuration and explicit age plus maximum-row retention pruning
  isolated to the operational log table
- Wired one logger into production Scanner, MediaOrganizerService, and OrganizerExecutor; added local
  bounded `logs list` and explicit `logs prune` commands without Storage/provider/workflow construction
- Full suite: 424 tests, 421 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.9 read-only operational log API and UI (2026-08-22): PASS

- Added scoped v2 bidirectional cursors for newest-first OperationalLog reads, bound to `all` or the
  selected minimum level with bounded forward/reverse SQLite `limit + 1` keysets
- Added authenticated `GET /api/v1/logs` with strict query validation, explicit safe-field allowlist,
  existing READ RBAC, and normalized audit that excludes query/cursor/record data
- Added a text-node-only Logs UI with level selector, explicit first-page refresh, and Previous/Next;
  no prune, write, search, live tail, Task/Job, or execution controls are exposed
- Full suite: 426 tests, 423 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.10 safe runtime database backup and verification (2026-08-22): PASS

- Added a local infrastructure-only backup service using SQLite's online backup API, including WAL
  snapshot coverage, read-only integrity/schema verification, SHA-256, byte size, and UTC results
- Added private same-directory staging and atomic no-overwrite publication; invalid source/target,
  malformed/newer databases, and simulated publication failures fail without changing source/target
- Added local `database backup` and `database verify` commands that use only configured persistence,
  construct no media Storage/provider/workflow, and expose no configuration secrets
- Verified representative Task, Result, security audit, and operational log records in a reopened
  snapshot; restore, scheduling, retention deletion, upload, and encryption remain explicitly absent
- Full suite: 429 tests, 426 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.11 reproducible release validation and CI baseline (2026-08-22): PASS

- Added a read-only, timeout-bounded GitHub Actions matrix for explicitly supported Python 3.11,
  3.12, and 3.13 with formatter, lint, offline tests, compile, dependency, configuration, and
  forbidden-runtime-dependency gates
- Added a separate wheel gate that rejects packaged tests/user configuration/databases/caches, then
  installs the artifact into a fresh environment outside the checkout
- The installed artifact validates its console entry point, both canonical configurations, and a
  temporary SQLite online backup/verify round trip without production Storage, providers, or secrets
- Added an explicit maintainer release checklist; artifact upload, tagging, deployment, restore,
  signing, containers, and live provider/storage CI remain absent
- Full suite: 432 tests, 429 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.12 read-only upgrade preflight and compatibility report (2026-08-22): PASS

- Added a local preflight service that reuses the database backup verifier for configured runtime and
  explicit backup integrity/schema checks without constructing a migration-capable repository
- Added Python/application/schema compatibility, matching older-schema migration-required reporting,
  bounded backup freshness, size, SHA-256, and deterministic READY/MIGRATION_REQUIRED results
- Added `upgrade check --backup ...` with a bounded age override; mismatched/newer/malformed/stale/
  future/same-file inputs fail closed and output contains no configuration or media/provider data
- Proved source and backup hash/mtime/size and sidecar state remain unchanged; no Storage/provider/
  workflow construction occurs, and the isolated installed-wheel smoke test exercises preflight
- Full suite: 436 tests, 433 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.13 non-overwriting offline runtime database restore (2026-08-22): PASS

- Added a local restore service that verifies an explicit backup, stages through SQLite, verifies and
  fsyncs the stage, then atomically creates an owner-only configured runtime file
- Restore requires explicit `--confirm-empty-destination` and refuses any existing runtime file,
  directory, symlink, SQLite sidecar, same path, invalid parent, malformed backup, or newer schema
- Older supported backups remain unmigrated and report migration-required; backup bytes/mtime are
  preserved, publish races never overwrite, and failures remove only service-owned temporary files
- Added the stop/preserve/restore/verify/start procedure and exercised a second missing runtime through
  the isolated installed wheel without constructing media Storage/provider/workflow services
- Full suite: 441 tests, 438 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.14 cooperative runtime maintenance lock (2026-08-22): PASS

- Added a stable empty owner-only POSIX advisory lease derived from the configured runtime database;
  shared runtime holders coexist while exclusive maintenance conflicts fail immediately
- Production runtime commands hold shared leases for their full operation and confirmed restore takes
  exclusive ownership before validation/staging; every return/error/cancellation path releases in finally
- Config validation, token generation, credential status, and Storage list/preflight remain lock-free;
  first-run shared commands preserve existing parent creation while restore remains fail-closed
- Verified exception and subprocess-crash release, symlink/non-regular rejection, secret-free lock
  content, restore contention zero-publication, and installed-wheel cross-process exclusion
- Full suite: 445 tests, 442 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.15 isolated runtime schema migration rehearsal (2026-08-22): PASS

- Added a local rehearsal service that verifies/copies an explicit backup and opens only its private
  owner-only temporary copy through the production SQLite repository migration path
- Current-schema copies complete as verified no-op rehearsals; older supported copies reach current
  Schema with Task/Result/security-audit/operational-log counts preserved
- Copy/migration/validation failures preserve backup and configured Runtime and remove rehearsal-owned
  database plus WAL/SHM/journal sidecars; no production Runtime repository is opened
- Added `upgrade rehearse --backup ...`, release procedure integration, and installed-wheel rehearsal
  without constructing Storage/provider/scanner/workflow/executor services
- Full suite: 449 tests, 446 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.16 read-only configuration and system status API/UI (2026-08-22): PASS

- Added one immutable, deterministic API-bootstrap snapshot of normalized Runtime configuration with
  runtime compatibility plus bounded Storage, Library, Recognition, and downstream policy catalogs
- Added authenticated `GET /api/v1/system/status` and a text-node-only System UI with explicit refresh;
  wrong methods and all query parameters fail before snapshot/repository reads
- Structurally excluded paths, rule operands, templates, classification destinations, endpoints,
  environment variables, credentials, Webhook data, and arbitrary Storage options; hostile-config
  regression confirms none enter the snapshot or API response
- RecognitionType C continues to expose Metadata C with Naming/Classification/Organize A; no Storage,
  provider, scanner, workflow, worker, planner, executor, backup, restore, or migration object is built
- Full suite: 454 tests, 451 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.17 explicit Automation Job cancellation UI (2026-08-22): PASS

- Reused the existing cancellation endpoint, application service, persisted pending/running semantics,
  `cancel_job` RBAC, worker observation, and normalized security audit without duplicating domain logic
- Added a Pending/Running-only Job-detail control requiring Request then Confirm; Keep performs no
  request or mutation, terminal Jobs show no control, and API state reloads after a confirmed request
- Tightened cancellation transport to POST with an empty query and body; client-controlled actor,
  status, command, Task, path, execute, or arbitrary fields cannot enter the cancellation service
- Added no Job submission, Task control, retry/resume, remote execution, rollback, media workflow, or
  Storage mutation behavior; running cancellation remains explicitly cooperative between items
- Full suite: 457 tests, 454 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.18 explicit DryRun Automation Job submission UI (2026-08-22): PASS

- Reused the existing durable Job service, `submit_dry_run` RBAC, Worker boundary, cancellation flow,
  and normalized audit; no alternate workflow or execution path was added
- Added an Open → Review → Confirm Jobs UI limited to scan/preview and an optional 1–10000 item limit;
  Back/Keep sends no request and successful queueing reloads API state
- Tightened DryRun POST to exact command/optional-limit documents with no query; malformed/unknown or
  authority/path/Task/policy/Storage/Scheduler/overwrite/delete fields create no Job
- Remote organize remains separately gated and absent from UI; queueing constructs no media services,
  performs no Storage mutation, and grants no execute authority
- Full suite: 460 tests, 457 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.19 durable active Automation Job admission control (2026-08-22): PASS

- Added validated `automation.maximumActiveJobs` (default 100, range 1–10000) and exposed only that
  configured numeric operational limit through the immutable System snapshot
- Added SQLite `BEGIN IMMEDIATE` active count plus insert admission shared by manual scan/preview,
  Scheduler emission, and protected remote organize; concurrent connections cannot exceed capacity
- Pending/Running consume capacity while terminal history releases it; no old Job is cancelled, deleted,
  reprioritized, or silently purged
- Full Scheduler admission rolls back occurrence advance/Job/audit, and full protected organize leaves
  its one-time execution authorization active for a later atomic consume
- API returns audited 409 `queue_full`; submission UI shows the existing safe error path and has no force,
  purge, bypass, retry, Scheduler, execute, or Task control
- Full suite: 466 tests, 463 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.20 read-only stale Running Automation Job visibility (2026-08-22): PASS

- Added validated `automation.staleJobAgeSeconds` (default 3600, range 60–604800) and exposed only
  its numeric value in the redacted System snapshot
- Added deterministic SQLite-bounded stale Running query and authenticated
  `GET /api/v1/jobs/stale?limit=100` with strict query parsing and an explicit safe-field allowlist
- Added an explicitly loaded Jobs UI view explaining that age is not liveness proof and marking
  execute-authorized organize Jobs as manual-recovery-only
- Added no recovery, retry, requeue, force-cancel, Worker, workflow, provider, or Storage operation;
  existing security-audit persistence remains the only API-side write
- Full suite: 471 tests, 468 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Production-readiness assessment recorded after Phase 19.20:

- The complete media pipeline and read-only stale visibility are accepted; UI recovery remains closed.
- The highest-priority runtime risk was unfenced Job ownership: a stale Worker could race a manual
  requeue and long workflows did not refresh Job age. This selected Phase 19.21 below; remote and
  automatic recovery remain excluded after fencing.
- OIDC/Secret Store, advanced scheduling, live progress, and recovery UI remain later work.

Phase 19.21 fenced cooperative Automation Job heartbeats (2026-08-22): PASS

- Migrated Runtime schema to v14 with an internal opaque claim token; every claim receives a new
  cryptographically random token and stale requeue atomically clears ownership
- Added repository-fenced heartbeat and terminal commit using Running status plus token; old Workers
  cannot update a later claim or publish its terminal notification
- Worker heartbeats reuse the existing cancellation callback before/between workflow items and after
  handler return, with no background thread and no change to media or Storage behavior
- Claim tokens are absent from API/UI/CLI/log/notification/configuration output; stale observation
  remains conservative during blocking external calls and no recovery control was added
- Full suite: 477 tests, 474 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.22 Local Storage atomic publication and fault-injection baseline (2026-08-22): PASS

- Corrected project status: Phase 19 overall production acceptance is BLOCKED, and fake/mock Storage
  tests are no longer described as real-service evidence
- Added the authoritative Local/SMB/OpenList/S3-R2 and transfer acceptance matrix; remote rows remain
  BLOCKED until dedicated credentials and explicitly approved empty destructive roots are supplied
- LocalStorage write/copy now stage in the target directory and atomically publish with no-overwrite
  race protection; injected stream/copy/publish failures preserve old targets and leave no owned stage
- Cross-storage MOVE now verifies destination existence and size before source delete; truncated target
  reports PARTIAL and preserves the complete source, while delete failure retains both copies
- Full suite: 485 tests, 482 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23 isolated real OpenList acceptance matrix (2026-08-22): BLOCKED

- Replaced the unsafe URL+Token-only optional integration with a four-part destructive gate requiring
  an explicit non-root `mediaflow-acceptance-*` path and exact operator confirmation; no default exists
- Added a production OpenListStorage/OrganizerExecutor matrix for lifecycle, no-overwrite, same-
  OpenList operations, Local↔OpenList COPY/MOVE, content/size/source checks, and allowlisted cleanup
- Gate validation and all fake fault regressions pass without network access; acceptance never imports
  runtime/user configuration and `config/alist.json` remains outside its boundary
- Actual isolated execution is NOT RUN because TEST_OPENLIST_URL/TOKEN/ROOT/confirmation are absent;
  OpenList rows and Phase 19 overall remain BLOCKED and no real Storage mutation occurred
- Full offline suite: 486 tests, 483 passed, 0 failed, 3 real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23.1 OpenList empty-root preflight and evidence record (2026-08-22): BLOCKED

- Added a production-Storage read-only preflight requiring the approved OpenList root to exist, be a
  directory, and contain zero listed objects before the first generated directory or file is created
- Enabled real runs now require an explicit new absolute local JSON report path; evidence publication
  is atomic/no-overwrite and excludes endpoint, credential, header, raw response, and arbitrary errors
- Unit regressions prove non-empty, non-directory, unreadable, incomplete gate, unsafe report path,
  report collision, and secret-bearing report data fail closed with zero Storage mutation
- Actual isolated matrix remains NOT RUN because all five dedicated prerequisites are absent; Phase
  19.23.1, Phase 19.23, and Phase 19 overall remain BLOCKED
- Full offline suite: 488 tests, 485 passed, 0 failed, 3 real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23.2 self-hosted isolated OpenList evidence run (2026-08-22): FAIL

- Deployed the official pinned `openlistteam/openlist:v4.2.2` image on a host-loopback-only ephemeral
  port with a generated credential, temporary container data, and a Local driver isolated from all
  repository configuration and media paths
- Production OpenListStorage health and root stat reached the real service, but v4.2.2 represented an
  empty directory as `content: null, total: 0`; the current mapper requires list content and raised
  `INVALID_RESPONSE` / `io_error`
- Fail-closed empty-root preflight stopped before creating any remote object, so adapter mutation and
  Local↔OpenList/OpenList↔OpenList rows are NOT RUN rather than PASS
- A non-secret FAIL report was retained at `/tmp/mediaflow-openlist-v4.2.2-acceptance-20260822.json`;
  the container, temporary administrator credential, API token, and backend data were removed
- Phase 19.23 is now FAIL rather than BLOCKED; production adapter repair and a complete isolated rerun
  are required in a separate task before Phase 19.24
- Post-run offline suite: 488 tests, 485 passed, 0 failed, 3 real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23.3 OpenList v4 empty-directory DTO repair and rerun (2026-08-22): PASS

- Normalized only the real v4.2.2 empty response `content: null, total: 0` to an empty page; null with
  inconsistent totals, bool/negative/missing totals, and other malformed content remain rejected
- Redeployed the official v4.2.2 image on loopback with new temporary credentials/data and executed
  the full production OpenListStorage/OrganizerExecutor lifecycle and transfer matrix
- Empty-root/no-overwrite, same-service copy/move, Local↔OpenList COPY/MOVE, OpenList↔OpenList
  Organizer COPY/MOVE, content/size/source assertions, and allowlisted cleanup all passed
- The PASS report is retained at `/tmp/mediaflow-openlist-v4.2.2-acceptance-pass-20260822.json`; the
  container, administrator credential, API token, and temporary backend were removed
- Evidence is ISOLATED PASS for self-hosted OpenList with Local driver only; third-party drivers and
  remote atomic publication remain uncertified, while Phase 19 overall remains BLOCKED on SMB/S3-R2
- Full suite: 490 tests, 487 passed, 0 failed, 3 real integrations skipped; Ruff, compile, dependency,
  both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed
