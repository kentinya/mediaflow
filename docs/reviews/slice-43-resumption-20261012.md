# Slice 43 — A Resumption and Integration Assessment / 2026-10-12

**Decision: RESUME ACTIVE; hand recovered Task 43.1 to B for reassessment.** This is the
user-authorized end of the development hold, not Task acceptance or Slice Final Review.

## Authority and preserved lineage

| Record | Immutable authority |
|---|---|
| Original Slice 43 Base | `853973dbbf8289fa2ad40657033e94e870a690e4` |
| Original Task 43.1 Base | `79544d9aba697036405b06054c0c56a740281bab` |
| Last suspended implementation | `b364a04d1c916ed327e3e8f470dc05e413ad80e6` — unaccepted |
| Latest Task/B review snapshot | `a447e3129be89bd20f6a24831b2be122d4fdf955:TASK.md` — FIX REQUIRED |
| Preserved freeze parent | `8a41e131f3a668388381ab51c8876668108871d8` on `frozen/slice-43-2026-10-07` |
| Accepted Slice 44 closure parent | `a72252091d5d46edf3e2114b994036ae21b08e2e` on `slice/44-page-improvements` |
| Slice 44 accepted product range | `853973dbbf8289fa2ad40657033e94e870a690e4..8be263ea778df08aa374e9433f138a218c1d4af9` |
| Working integration branch | `slice/43-resumed-after-44` |

The user explicitly requested A recovery, compatibility assessment/integration, a committed ACTIVE
Contract/Roadmap and B reassessment. A created the new branch from accepted Slice 44 and merges the
preserved Slice 43 parent without rebase, repinning, history rewriting or changing either source
branch. Both original Bases remain ancestors. Carrying the unfinished implementation continues its
FIX REQUIRED correction loop; it does not merge a PASS claim into accepted history.

## Integration assessment

The read-only merge preview found no executable-source text conflict. The ten shared executable
paths are configuration objects, SQLite runtime, service API, Operations harness, Playwright default
configuration, frontend normalizers, router, API transport and navigation model/test. Their integrated
diffs against accepted Slice 44 retain the original Slice 43 addition/removal counts; A also inspects
the changed authority paths and runs affected behavior checks. Counts alone are not acceptance.

- Configuration combines focused Automation publication/removal with the accepted Rules local-test
  and MediaLibrary-plus-path semantics. Whole-candidate validation, checked activation, applicable
  evidence and immutable admitted pins remain shared authority. No legacy classification prefix is
  silently restored and no historical snapshot is rewritten.
- SQLite retains accepted runtime schema 45 and all discovery/transfer/history migrations. The
  recovered Automation changes add existing audit/query and due-state behavior; resumption adds no
  schema or new origin/consumer-evidence storage.
- API/harness/transport/routes combine both lines: recovered lifecycle/readback/history routes and
  accepted direct-file, Rules and bounded folder/mixed Organize surfaces. Preview/grant, scheduled
  authority and manual one-shot execution remain distinct; this merge adds no Run-once behavior.
- Documentation conflicts retain the complete accepted closure ledger. Root Contract is the
  recovered Slice 43 with an explicit resumption section; root Task is the exact latest preserved
  snapshot plus an A recovery note. TARGET Automation architecture/experience and V2-AUTO-001
  through V2-AUTO-008 are restored alongside Slice 44's CURRENT delivery and stable requirements.
  The legacy root requirements duplicate remains deleted, preserving the canonical docs authority.
- Byte comparisons establish unchanged frozen Required Outcomes/surfaces, safety/UX, deferrals,
  acceptance and final-validation text; unchanged original Task except its recovery note; unchanged
  entire accepted closure ledger; and unchanged recovered Automation command implementation.
  The four pre-existing user PNGs remain untracked, unstaged and byte-identical.

## Unresolved Task blocker and remaining outcomes

The latest B P1 remains: after ordinary subsequent publications, a removed definition's detail,
occurrences and grant/history routes can return 404 despite intact durable occurrence, exact pinned
revision and publication proof, also after restart. The preserved command service still scans 200
recent revisions, 500 recent activation audits and a separate 200-audit ever-published window.
Its source is byte-identical to the rejected implementation; A does not claim this defect repaired.

B's preserved complexity assessment remains binding: use the existing exact durable occurrence
revision and its publication evidence, or a complete targeted/cursor read when no pin exists.
Distinguish unavailable/incomplete evidence from absence and unpublished Draft. Do not enlarge
window constants, add another cache/compensation/recovery engine or require definition recreation.
The fix belongs to the same Task 43.1, AC-T5/T6 and RO-2; ID/Base/Goal/Scope/acceptance and High/T4
stay unchanged. B reassesses the actual merged candidate before Developer proceeds.

RO-1 inventory/metrics, RO-4 definition-bound Run once/manual origin, RO-5 cross-definition records,
RO-6 four-field settings/actual resident adoption and completion of RO-3/RO-7 remain subject to B's
outcome assessment after Task PASS. No new Task is selected by A and no outcome is declared complete.

## Validation and handoff

Integration baseline validation is recorded separately from Task candidate and Slice-final gates.
The retained local evidence directory is
`.git/validation-evidence/a72252091d5d46edf3e2114b994036ae21b08e2e/a-resume43-20261012/`.
It contains initial branch/status/image hashes, the exact source/test/harness/frontend manifest,
commands, exit codes, durations and original logs. Dirty-merge runs are matched to the committed
source before reuse. Historical /tmp-only reports remain preserved claims, not fresh gate evidence.

Fresh integration checks on the exact recovered executable inputs:

| Check | Actual result |
|---|---|
| 17 Python modules: Automation publication/lifecycle, configuration, runtime strategy, classification destination, Rules, discovery/manifest, execution/grant/admission/fencing and migration/preflight | PASS — 442 tests, no failures/skips; 178.986 test seconds |
| Automation entities/forms/router and shared navigation | PASS — 5 files, 80 tests |
| Accepted both-library Files, Rules object tests/classification form and shared API transport | PASS — 7 files, 119 tests |
| Built V2 against real Python/API/SQLite, isolated Automation lifecycle browser journey | PASS — 10 tests; 70.312 process seconds |
| Python format/lint/compile; Web typecheck/lint/format/build | PASS — original logs retained |
| Frozen authority/Task/closure-ledger/image byte checks; staging/private-config/reference checks; whitespace | PASS — original Bases and both source branches preserved; four user images excluded |

Unclosed SQLite ResourceWarnings, jsdom `scrollTo` notices and the existing Vite bundle-size advisory
remain visible. These passing tests cover compatible integration, not the preserved P1 beyond the
historical windows. The complete T4 candidate/final gates, fresh P1 production reproduction and any
affected upgrade/deployment checks remain required by the recovered Task/Contract; A does not repeat
those expensive completion gates while the known Task blocker is unresolved. No Task PASS follows
from this table. The HEAD-authoritative governance guard runs after the activation commit, before B
reassessment. No push, deployment, production-service certification or Slice closure is claimed.
