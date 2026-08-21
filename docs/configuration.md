# Strategy recognition configuration

The same JSON document is now the Phase 13 runtime configuration. It includes `storages`,
`resourceLibraries`, `mediaLibraries`, policy catalogs, metadata settings, and `historyPath`.
Local and OpenList Storage definitions are constructed by the runtime loader. SMB/S3/R2 adapters
exist, but their current runtime configuration must be injected by an embedding application.
Passwords, tokens, and access keys remain environment-owned and never appear in strategy JSON.

```json
{
  "storages": [
    {"id": "source", "type": "local", "rootPath": "/media/incoming"},
    {"id": "target", "type": "local", "rootPath": "/media/organized"}
  ],
  "resourceLibraries": [
    {"id": "source-media", "storageId": "source", "storagePath": "",
     "displayRootPath": "/media/incoming"}
  ],
  "mediaLibraries": [
    {"id": "movies", "storageId": "target", "rootPath": "Movies"}
  ],
  "historyPath": ".mediaflow/history.jsonl"
}
```

Runtime configuration requires all six strategy catalogs: `recognitionRules`,
`recognitionTypePolicies`, `metadataPolicies`, `namingPolicies`, `classificationPolicies`, and
`organizePolicies`. Nothing is filled from a Python A/B/C default in production mode. The
development/smoke constructors remain test fixtures only. `config/strategy.example.json` is the
single canonical A/B/C runtime example.

Validate the entire reference graph without scanning, provider access, or Storage mutation:

```bash
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
mediaflow config validate
```

Configuration-driven discovery uses `ResourceLibrary.storagePath` as the path inside its Storage;
`displayRootPath` is only the optional local/display binding used by positional-path commands.
Legacy ResourceLibrary `rootPath` remains accepted as an alias:

```json
{"id":"movies","storageId":"source","storagePath":"Media/电影",
 "displayRootPath":"/mnt/HDD_2/Media/电影","enabled":true}
```

MediaLibrary roots are always Storage-relative:

```json
{"id":"Media","storageId":"target","rootPath":"Downloads"}
```

The standard no-path commands are:

```bash
mediaflow scan --limit 20
mediaflow preview --limit 20
mediaflow organize --limit 20
mediaflow organize --execute --limit 20
```

Only the last command authorizes mutation.

### Path model

The path fields have separate meanings:

- `Storage.rootPath`: adapter-owned root. Local roots may be absolute; OpenList roots are absolute
  OpenList API paths such as `/115网盘`.
- `ResourceLibrary.storagePath`: scan root relative to its Storage root, such as `Test_Source`.
- `ResourceLibrary.displayRootPath`: optional host-visible binding for positional-path commands.
  It does not affect no-path scanning. Legacy `rootPath` is read only as a compatibility alias.
- `MediaLibrary.rootPath`: destination root relative to its Storage root, such as `Test_Target`.

Do not repeat the Storage root inside `storagePath` or a MediaLibrary root. A cross-storage example:

```json
{
  "storages": [
    {"id":"openlist-a","type":"openlist","baseUrl":"https://a.example",
     "tokenEnv":"OPENLIST_A_TOKEN","rootPath":"/b"},
    {"id":"openlist-c","type":"openlist","baseUrl":"https://c.example",
     "tokenEnv":"OPENLIST_C_TOKEN","rootPath":"/分类"}
  ],
  "resourceLibraries": [
    {"id":"source","storageId":"openlist-a","storagePath":"",
     "displayRootPath":"/mnt/openlist-a/b"}
  ],
  "mediaLibraries": [
    {"id":"Media","storageId":"openlist-c","rootPath":"Movies"}
  ]
}
```

The plan retains `openlist-a:path` and `openlist-c:path`; a local mount path is never embedded in a
Storage-relative destination.

OpenList can be constructed by the runtime loader with non-secret settings in JSON and a token in
an environment variable:

```json
{"id":"openlist","name":"OpenList","type":"openlist",
 "baseUrl":"https://openlist.example.com","tokenEnv":"OPENLIST_TOKEN",
 "rootPath":"/Media","readOnly":false,"maxConcurrency":4,"maxRetries":2}
```

```bash
export OPENLIST_TOKEN="<token>"
```

ResourceLibrary and MediaLibrary paths referencing this Storage remain relative to `/Media`.
OpenList supports Move/Copy/Delete but not hard or symbolic links. Within one OpenList Storage, a
MOVE changing both parent and filename uses native server-side Move followed by Rename. Rename
failure triggers a best-effort Move back to the source. Cross-storage MOVE streams Copy, verifies
the destination size, and deletes the source only afterward. SMB and S3/R2 continue to use
externally injected adapters; their secrets are never part of strategy JSON.

The loader rejects malformed JSON models, duplicate IDs, missing references, unsafe/unknown naming
templates, unsupported classification conditions, unsafe classification paths, unknown
MediaLibrary references, and unsupported organize operations before a batch starts.

`strategy-test` accepts a user JSON file through either:

```bash
strategy-test --config /path/to/strategy.json ...
```

or:

```bash
export MEDIAFLOW_STRATEGY_CONFIG=/path/to/strategy.json
```

Start from [the repository example](../config/strategy.example.json). The configuration has four
required arrays:

- `resourceLibraries`: maps a real scan root to a stable ResourceLibrary ID.
- `recognitionTypes`: configured A/B/C (or other) identities.
- `recognitionRules`: ordered rules evaluated by the production RecognitionRuleEngine.
- `recognitionTypePolicies`: independent metadata/naming/classification/organize policy references.

Metadata policies fully describe their provider, query type/MediaType, locale, thresholds, and
bounded enrichment. Locale belongs here, not in TMDBProvider:

```json
"metadataPolicies": [
  {
    "id": "A",
    "providerId": "tmdb",
    "mediaType": "movie",
    "language": "zh-CN",
    "region": "CN",
    "maxCandidateEnrichments": 2,
    "maxProviderRequests": 6
  }
]
```

Supported keys include `providerId`, `mediaType`, `mediaQueryType`, `language`, `region`,
`automaticThreshold`, `confirmationThreshold`, `minimumScoreGap`, `maxProviderRequests`, and
`maxCandidateEnrichments`. The repository example explicitly configures A/B/C as `zh-CN` and `CN`.

Naming is entirely template-driven; provider display text such as `tmdbid-` belongs in the JSON:

```json
{"id":"A","directoryTemplate":"{title} ({year}) [tmdbid-{provider_id}]",
 "filenameTemplate":"{title} ({year}).{ext}","missingVariableStrategy":"omit_token"}
```

TV policies additionally accept `seriesDirectoryTemplate`, `seasonDirectoryTemplate`,
`episodeFilenameTemplate`, and `multiEpisodeFileTemplate`. Templates use only the safe variables
and numeric formatting supported by NamingEngine; they are not an expression language.

Classification rules use normalized `conditions` and `result` objects. Supported conditions are
`mediaType`, `genres`, `countries`, `languages`, `canonicalYear`/`yearMin`/`yearMax`, and
`keywords`. The result references a configured MediaLibrary and a safe relative path:

```json
{"id":"japanese-animation","priority":200,
 "conditions":{"mediaType":["movie"],"genres":["Animation"],"countries":["JP"]},
 "result":{"mediaLibraryId":"movies","library":"Movies","path":["Anime"]}}
```

Organize policies are independent catalog entries. Valid operations are `MOVE`, `COPY`,
`HARDLINK`, and `SYMLINK`; a missing policy never falls back to MOVE:

```json
{"id":"A","operation":"COPY","overwrite":false}
```

The example mapping is:

```text
/mnt/HDD_2/Media/电影   -> resourceLibraryId movies  -> RecognitionType A
/mnt/HDD_2/Media/电视剧 -> resourceLibraryId tv      -> RecognitionType B
/mnt/HDD_2/Media/C      -> resourceLibraryId special -> RecognitionType C
```

Rules match the stable ID rather than `/mnt/HDD_2`:

```json
{
  "id": "movie-library",
  "name": "Movie resource library",
  "priority": 100,
  "score": 100,
  "stopOnMatch": true,
  "condition": {
    "field": "resource_library_id",
    "operator": "equals",
    "value": "movies"
  },
  "outputRecognitionType": "A"
}
```

Atomic `field` and `operator` strings use the values defined by `ConditionField` and
`ConditionOperator`. Logical conditions use `operator` equal to `and`, `or`, `not`, or `always`
and a `children` array. An explicit low-priority catch-all, if wanted, is represented as:

```json
{
  "id": "explicit-default-movie",
  "name": "Explicit default movie",
  "priority": -100,
  "condition": {"operator": "always", "children": []},
  "outputRecognitionType": "A"
}
```

There is no implicit default. Without a matching enabled rule, the result is `Unrecognized`.

The C policy remains independent:

```json
{
  "id": "type-C",
  "recognitionType": "C",
  "metadataPolicy": "C",
  "namingPolicy": "A",
  "classificationPolicy": "A",
  "organizePolicy": "A"
}
```

This reuses downstream policy A without rewriting RecognitionType C.

For the real movie directory:

```bash
cp config/strategy.example.json config/strategy.json
# Edit resourceLibraries roots and rules in config/strategy.json.

export MEDIAFLOW_STRATEGY_CONFIG="$PWD/config/strategy.json"
export TMDB_ACCESS_TOKEN="<your-token>"

strategy-test --directory "/mnt/HDD_2/Media/电影" \
  --live-metadata \
  --show-naming \
  --limit 20
```

For a one-off override without a root binding, the development rules also permit:

```bash
strategy-test --directory "/mnt/HDD_2/Media/电影" \
  --resource-library movies \
  --live-metadata \
  --show-naming \
  --limit 20
```

Single-file mode uses the same configured root bindings. With
`MEDIAFLOW_STRATEGY_CONFIG` exported, this automatically resolves the file to `movies`:

```bash
strategy-test --live-metadata --show-naming \
  "/mnt/HDD_2/Media/电影/千与千寻 (2001)/千与千寻 (2001).mkv"
```

An explicit single-file override is also available (`--resource-library-id` is an equivalent
backward-compatible spelling):

```bash
strategy-test --resource-library movies --live-metadata --show-naming \
  "/mnt/HDD_2/Media/电影/千与千寻 (2001)/千与千寻 (2001).mkv"
```

Root matching chooses the most specific configured containing root. If neither a binding nor an
explicit ID is available, FileContext keeps an unmatched strategy context and normal rule
evaluation may return `Unrecognized`; it never defaults to A.

Smoke case files use a separate `/A/`, `/B/`, `/C/` fixture configuration. Those path rules are
not loaded by the normal directory CLI bootstrap.

## Developer strategy-test execution

`strategy-test` remains dry-run by default. `--execution-root` may be supplied with `--show-plan`
to display the fully resolved destination without mutation. A real single-file operation requires both
`--show-plan` and `--execute`, plus an existing local destination Storage root supplied by
`--execution-root` or `MEDIAFLOW_EXECUTION_ROOT`:

```bash
strategy-test --config config/strategy.json \
  --resource-library movies \
  --live-metadata --show-plan \
  "/path/to/source/Movie.2024.mkv"

strategy-test --config config/strategy.json \
  --resource-library movies \
  --live-metadata --show-plan --execute \
  --execution-root "/path/to/destination-storage" \
  "/path/to/source/Movie.2024.mkv"
```

The first command produces `ExecutionStatus.DRY_RUN` and never accesses a mutable Storage. The
second constructs LocalStorage adapters at the selected source ResourceLibrary root and explicit
destination root. This single-local-file restriction applies only to the developer inspector.

## Production workflow

```bash
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
mediaflow config validate       # configuration only; no Storage/provider access
mediaflow scan --limit 20       # read-only discovery
mediaflow preview --limit 20    # complete pipeline, DryRun
mediaflow organize --limit 20   # complete pipeline, still DryRun
mediaflow organize --execute --limit 20
```

Without a positional path, every enabled ResourceLibrary is scanned. Production execution resolves
source and destination Storage IDs from configuration and supports configured batches. Only
`organize --execute` grants mutation authority; overwrite, implicit operation fallback, and silent
delete remain prohibited.
