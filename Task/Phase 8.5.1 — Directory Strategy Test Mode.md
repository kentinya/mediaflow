Phase 8 has been completed and accepted.

Before starting Phase 9, implement an intermediate validation phase:

Phase 8.5 — Strategy Test CLI / End-to-End Recognition Smoke Test

Read and follow:

- AGENTS.md
- docs/requirements.md
- docs/architecture.md
- docs/progress.md

Inspect the current repository, existing CLI structure, application services,
Parser, Recognition, RecognitionTypePolicy, MetadataProvider, TMDBProvider,
CandidateMatcher, Scanner, and Storage abstractions before changing code.

Do NOT start Phase 9.
Do NOT implement NamingPolicy or NamingEngine.

Goal:

Create a developer-facing command-line strategy testing tool that allows us to
run the existing recognition pipeline against real or synthetic media paths and
inspect every decision made by the system.

The pipeline must reuse the real application components:

File/Path Input
→ FilenameParser + PathParser
→ ParseResult
→ RecognitionRuleEngine
→ RecognitionType
→ RecognitionTypePolicyResolver
→ MetadataPolicy
→ MetadataProvider / TMDB
→ CandidateMatcher
→ MediaIdentity

Do NOT duplicate the production parsing, recognition, policy resolution,
candidate matching, or metadata logic inside the CLI.

The CLI is only a test/debug harness around the existing application pipeline.

==================================================
MODES
==================================================

Implement at least these modes:

1. Single file/path mode

Example:

strategy-test "/downloads/C/The.Matrix.1999.2160p.WEB-DL.x265.mkv"

The physical file does not need to exist if the existing parser can operate
from a synthetic FileContext/path.

2. Offline mode

Example:

strategy-test --offline "/downloads/C/The.Matrix.1999.mkv"

Offline mode runs only:

Parser
→ Recognition
→ RecognitionTypePolicy resolution

It MUST NOT make TMDB or any network request.

3. Live metadata mode

Example:

strategy-test --live-metadata "/downloads/C/The.Matrix.1999.mkv"

This may use the configured MetadataProvider/TMDB integration.

Never hardcode TMDB credentials.

Use the existing provider/configuration system.

4. Case-file mode

Example:

strategy-test --cases testdata/strategy/cases.json

This mode loads expected strategy results and compares actual results against
them.

The case file should support fields such as:

{
  "path": "/C/The.Matrix.1999.2160p.WEB-DL.mkv",
  "expect": {
    "recognitionType": "C",
    "metadataPolicy": "C",
    "namingPolicy": "A",
    "classificationPolicy": "A",
    "organizePolicy": "A",
    "title": "The Matrix",
    "year": 1999
  }
}

Not every expectation field must be mandatory.

==================================================
OUTPUT
==================================================

Single-item output must clearly show each stage.

Example structure:

==================================================
Strategy Test
==================================================

INPUT

Path:
...

--------------------------------------------------
PARSER
--------------------------------------------------

titleCandidate:
year:
season:
episode:
episodes:
resolution:
source:
videoCodec:
audio:
hdr:
version:
releaseGroup:

Parser warnings:
Parser evidence:

--------------------------------------------------
RECOGNITION
--------------------------------------------------

Recognition status:
RecognitionType:

Matched rules:
Rule priorities:
Score:
Evidence:
Warnings:

--------------------------------------------------
RECOGNITION TYPE POLICY
--------------------------------------------------

RecognitionType:

MetadataPolicy:
NamingPolicy:
ClassificationPolicy:
OrganizePolicy:

RecognitionType preserved:
YES / NO

--------------------------------------------------
METADATA
--------------------------------------------------

Provider:
Query type:
Query:
Year:

Cache hit/miss:

--------------------------------------------------
CANDIDATES
--------------------------------------------------

For every relevant candidate print:

Provider ID
Title
Original title
Year
Total score

Score breakdown:
- title
- year
- original/alternative title
- media type
- season/episode
- other

Reasons / warnings

--------------------------------------------------
MATCH RESULT
--------------------------------------------------

Status:
Confidence:
Selected provider:
Selected provider ID:
Selected title:
Selected year:

--------------------------------------------------
FINAL
--------------------------------------------------

RecognitionType:
MediaIdentity:
MetadataPolicy:
NamingPolicy:
ClassificationPolicy:
OrganizePolicy:

Storage mutations:
0
==================================================

Do not only print the final answer.
The purpose of this tool is to inspect WHY a strategy decision happened.

==================================================
CRITICAL C REGRESSION
==================================================

The existing core project rule MUST remain true:

A
→ Metadata A
→ Naming A
→ Classification A
→ Organize A

B
→ Metadata B
→ Naming B
→ Classification B
→ Organize B

C
→ Metadata C
→ Naming A
→ Classification A
→ Organize A

When RecognitionType is C:

RecognitionType MUST remain C.

The CLI must explicitly display:

RecognitionType = C

MetadataPolicy = C
NamingPolicy = A
ClassificationPolicy = A
OrganizePolicy = A

RecognitionType preserved = YES

Never rewrite RecognitionType C to A.

Add a permanent automated regression test for this behavior.

==================================================
ZERO MUTATION SAFETY
==================================================

This tool will eventually be run against real media libraries.

Therefore it must have a hard zero-mutation guarantee.

Strategy Test CLI MUST NOT call:

Write
CreateDirectory
Move
Copy
Delete
HardLink
SoftLink

Prefer implementing a StrategyTest/ReadOnly safety guard around Storage
dependencies.

If any mutation method is invoked while strategy test mode is active:

FAIL immediately with a clear error.

Do not silently ignore the mutation.

Add automated tests asserting:

Write calls = 0
CreateDirectory calls = 0
Move calls = 0
Copy calls = 0
Delete calls = 0
HardLink calls = 0
SoftLink calls = 0

==================================================
NO FUTURE PHASE EXECUTION
==================================================

The CLI may DISPLAY the resolved:

NamingPolicy ID
ClassificationPolicy ID
OrganizePolicy ID

but MUST NOT execute them.

Do not generate final media names.
Do not calculate final destination paths.
Do not organize files.

Phase 9 has not started.

==================================================
CASE TESTING
==================================================

Create a small starter strategy regression dataset.

Include cases for at least:

- A recognition
- B recognition
- C recognition
- C -> Metadata C / Naming A / Classification A / Organize A
- Movie exact metadata match
- wrong first metadata candidate / correct later candidate
- low confidence candidate
- ambiguous candidate
- no metadata result
- TV S01E01
- multi-episode S01E01E02
- Unicode / Chinese title
- filename/directory conflict

The case runner should print:

Total
Passed
Failed
Skipped

For failures show:

Expected
Actual

and enough rule/matcher evidence to diagnose the difference.

==================================================
DIRECTORY MODE
==================================================

If it can be implemented cleanly using the existing Scanner abstraction,
also add:

strategy-test --directory <path>

This mode should produce a compact summary like:

Total:
Matched:
NeedConfirm:
Ambiguous:
NotFound:
Errors:

and then one compact row per file.

However:

- reuse Scanner
- do not duplicate traversal logic
- zero mutation still applies
- respect existing Storage concurrency limits
- do not make directory mode a blocker if current architecture makes it
  disproportionately large

==================================================
SECURITY
==================================================

Never print:

TMDB token
API key
Authorization header
Storage passwords
signed URLs
other secrets

Reuse the existing secret-redaction infrastructure.

==================================================
ARCHITECTURE
==================================================

Keep this as a developer/testing entry point.

Do not place strategy-test specific behavior inside:

FilenameParser
RecognitionRuleEngine
CandidateMatcher
TMDBProvider

The CLI should orchestrate existing services instead of changing their domain
semantics.

==================================================
TESTS
==================================================

Add tests for:

- offline pipeline
- live metadata pipeline with fake MetadataProvider
- C RecognitionType preservation
- policy mapping visibility
- wrong first candidate regression
- ambiguous candidate
- no-result candidate
- case-file runner
- expectation mismatch reporting
- zero mutation
- no metadata calls in --offline mode
- secret redaction

Unit tests must not require Internet access.

Real TMDB calls must remain optional and use existing configuration.

==================================================
VALIDATION
==================================================

After implementation:

1. Run strategy CLI tests.
2. Run Phase 8 metadata regressions.
3. Run Phase 7 recognition regressions.
4. Run Phase 6 parser regressions.
5. Run Scanner/FileIndex regressions.
6. Run Storage regressions.
7. Run DryRun zero-mutation regression.
8. Run formatter/lint/typecheck/build if configured.
9. Fix all failures within Phase 8.5 scope.
10. Update docs/progress.md.
11. Update docs/architecture.md if necessary.

Do not begin Phase 9.

==================================================
FINAL REPORT
==================================================

Finish with:

## Phase 8.5 Result

PASS / FAIL

## CLI Usage

Show the actual commands supported.

## Example Output

Show one representative example without secrets.

## Strategy Cases

Total:
Passed:
Failed:
Skipped:

## C Policy Regression

RecognitionType = C
MetadataPolicy =
NamingPolicy =
ClassificationPolicy =
OrganizePolicy =

RecognitionType remained C: PASS/FAIL

## Safety

Storage Write calls:
CreateDirectory calls:
Move calls:
Copy calls:
Delete calls:
HardLink calls:
SoftLink calls:

Offline Metadata calls:

## Regression

Metadata:
Recognition:
Parser:
Scanner/FileIndex:
LocalStorage:
SMBStorage:
OpenListStorage:
S3/R2Storage:
DryRun:

## Quality

Build:
Lint:
Typecheck:
Formatter:

## Known Limitations

List actual limitations.

## Final Recommendation

If accepted:

Phase 8.5 accepted. Strategy pipeline is ready for real-world validation before Phase 9.

Otherwise:

Phase 8.5 not accepted. Blocking issues remain.

Do not start Phase 9 automatically.