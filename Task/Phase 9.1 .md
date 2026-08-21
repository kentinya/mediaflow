During Phase 9.1 real-world validation we found another metadata matching issue.

Do not start Phase 10.

The localized-title fix now works, but movie year semantics are incorrect.

Real input:

/mnt/HDD_2/Media/电影/千与千寻 (2001)/千与千寻 (2001).mkv

Parser:

titleCandidate = 千与千寻
year = 2001

Metadata configuration:

language = zh-CN
region = CN

TMDB candidates currently include:

Candidate 535075:
title = 千与千寻诞生秘话
year = 2001
score = 68.333

Candidate 129:
title = 千与千寻
originalTitle = 千と千尋の神隠し
year = 2019
title score = 65 exact
year score = -15
total = 65

The correct candidate is TMDB 129.

The title matching is now correct.

The problem is that the matcher is treating a REGION-SPECIFIC release year
as the canonical identity year.

TMDB region configuration can cause regional release-date information to be
returned/displayed.

For media identity matching, the canonical/original/primary movie release year
must be distinguished from regional release dates.

==================================================
1. INSPECT CURRENT YEAR MAPPING
==================================================

Inspect:

TMDB search request
TMDB search response mapper
TMDBProvider
MediaCandidate
CandidateMatcher

Determine exactly where candidate.year = 2019 is coming from.

Report whether it is:

- regional search release_date
- primary release date
- movie details release_date
- another derived value

Do not guess.

==================================================
2. SEPARATE YEAR SEMANTICS
==================================================

Do not treat all release years as the same field.

Introduce provider-neutral semantics such as:

canonicalReleaseDate
canonicalYear

regionalReleaseDate
regionalYear

if appropriate for the existing domain model.

The exact field names may differ, but the distinction must exist.

CandidateMatcher should use the canonical movie identity year for normal
filename year matching.

Regional release dates must not replace the canonical year.

==================================================
3. MATCHING YEAR
==================================================

For normal media filenames:

千与千寻 (2001)

the expected identity year is the movie's canonical/primary release year.

Therefore TMDB 129 should match year 2001 even if the configured region CN has
a later regional release date.

Expected CandidateMatcher evidence:

title:
exact match
千与千寻 == 千与千寻

canonical year:
2001 == 2001

regional release year:
2019
informational only

The regional year must not generate a -15 mismatch penalty.

==================================================
4. PRESERVE REGION CONFIGURATION
==================================================

Do NOT solve this simply by deleting region support globally.

MetadataPolicy must still be allowed to configure:

language = zh-CN
region = CN

Region can remain useful for localized/regional metadata.

Instead fix the domain semantics so regional presentation data does not corrupt
identity matching.

==================================================
5. SEARCH VS DETAILS
==================================================

If TMDB search results do not provide a reliable canonical release year when
region is specified, use a bounded two-stage identification flow.

For example:

SearchMovie
→ preliminary candidates
→ select small plausible candidate set
→ GetMovie(candidateId)
→ obtain canonical movie details
→ enrich candidate
→ final CandidateMatcher scoring

Do NOT issue GetMovie for every search result.

Reuse the existing bounded enrichment/request-budget/cache architecture.

==================================================
6. PRIMARY RELEASE YEAR QUERY
==================================================

Inspect whether the existing movie search request already uses the parsed year
as TMDB's primary_release_year parameter.

For:

titleCandidate = 千与千寻
year = 2001

the search request should use the parsed year appropriately when doing so is
compatible with the existing fallback strategy.

Do not rely only on region-adjusted returned release_date for year matching.

Keep the existing relaxed search fallback when strict title+year search returns
nothing.

==================================================
7. MEDIA CANDIDATE MODEL
==================================================

MediaCandidate should expose enough normalized information for CandidateMatcher
to distinguish:

identity/canonical year

from:

regional release year

Do not leak TMDB-specific release-date DTOs into CandidateMatcher.

==================================================
8. SCORE EXPLANATION
==================================================

Extend strategy-test candidate output.

For movie candidates show something like:

Canonical year: 2001
Regional year: 2019

Score breakdown:

- title: 65 — exact localized title match
- year: 20 — canonical year difference is 0
- media_type: 5
- parse_evidence: 10

If a regional year differs, display it as informational evidence rather than
using it as the canonical mismatch penalty.

==================================================
9. EXACT REGRESSION
==================================================

Add this permanent regression:

Input:

titleCandidate = 千与千寻
year = 2001

Metadata policy:

language = zh-CN
region = CN

Candidates include:

TMDB 535075
title = 千与千寻诞生秘话
canonicalYear = 2001

TMDB 129
title = 千与千寻
originalTitle = 千と千尋の神隠し
canonicalYear = 2001
regionalYear = 2019

Expected:

TMDB 129 receives:
- exact title evidence
- exact canonical year evidence

TMDB 129 must outrank 535075 by a sufficient score gap.

Result:
Matched

Selected provider ID:
129

==================================================
10. OTHER YEAR REGRESSIONS
==================================================

Add tests for:

A. Same title, different remake years

Input:
Movie X (2024)

Candidates:
Movie X 1999
Movie X 2024

Expected:
2024 wins.

B. Regional re-release

Canonical:
2001

Regional:
2019

Filename:
2001

Expected:
canonical 2001 matches.

C. Filename uses regional release year

If local filename is 2019 while canonical year is 2001:

do not silently redefine canonical identity.

Use the existing confidence/NeedConfirm mechanism unless a future policy
explicitly allows regional-year matching.

D. Missing local year

Do not penalize merely because candidate has canonical/regional dates.

E. Exact provider ID

Explicit [tmdbid-*] behavior remains higher priority.

==================================================
11. TV YEAR SEMANTICS
==================================================

Audit TV matching for the same class of bug.

TV identity year should be based on the provider-normalized series identity
date semantics, normally the canonical first-air date/year.

Do not accidentally reuse movie regional-release logic for TV.

Do not redesign TV unnecessarily if current behavior is already correct.

==================================================
12. DO NOT FAKE THE FIX
==================================================

Do NOT:

- hardcode TMDB 129
- hardcode 千与千寻
- lower thresholds
- remove year scoring
- choose exact-title result regardless of year
- choose results[0]
- use popularity as decisive evidence
- globally disable region configuration

Fix the date semantics.

==================================================
13. STRATEGY CLI EXPECTED OUTPUT
==================================================

After the fix, running:

strategy-test \
  --live-metadata \
  --show-naming \
  "/mnt/HDD_2/Media/电影/千与千寻 (2001)/千与千寻 (2001).mkv"

should show approximately:

Provider ID: 129
Title: 千与千寻
Original title: 千と千尋の神隠し
Matched provider title: 千与千寻
Matched title source: title/localized

Canonical year: 2001
Regional year: 2019

Score:
high-confidence exact title + canonical year match

MATCH RESULT:

Status: matched
Selected provider: tmdb
Selected provider ID: 129
Selected title: 千与千寻
Selected year: 2001

NAMING PREVIEW:

Status: success

Storage mutations:
0

==================================================
14. REGRESSIONS
==================================================

Run:

Metadata
CandidateMatcher
TMDBProvider
Strategy CLI
Naming
Recognition
Parser
Scanner/FileIndex
Storage
DryRun

Preserve:

RecognitionType C remains C
zero storage mutation
no Classification execution
no Organizer execution

Update:

docs/architecture.md
docs/progress.md

Document:

- canonical movie year semantics
- regional release date semantics
- year scoring behavior
- bounded candidate detail enrichment

Do not start Phase 10.