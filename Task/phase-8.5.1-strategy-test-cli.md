Phase 8.5 has been accepted.

Do not start Phase 9.

Implement the previously deferred directory mode for strategy-test.

Required command:

strategy-test --directory "/path/to/media"

Requirements:

1. Reuse the existing Scanner abstraction.
2. Do not duplicate filesystem traversal logic inside the CLI.
3. Reuse the production Parser, Recognition, policy resolver, MetadataProvider,
   and CandidateMatcher pipeline.
4. Directory mode must remain strictly read-only.
5. Storage mutations must remain zero.
6. Default directory mode should be offline unless --live-metadata is explicitly supplied.
7. Support a configurable or CLI limit for testing, for example:
   --limit 20
8. Support common media extension filtering through existing ResourceLibrary/Scanner behavior.
9. Print one compact result per file:
   status | RecognitionType | parsed title/year | metadata result/confidence
10. Print summary:
    Total
    Matched
    NeedConfirm
    Ambiguous
    NotFound
    Unrecognized
    Errors
11. Do not output secrets.
12. Do not execute Naming, Classification, or Organize policies.
13. Add zero-mutation tests.
14. Run all Phase 8.5 and existing regressions.
15. Update docs/progress.md.

Prefer integrating Scanner by constructing the minimum required read-only
ResourceLibrary/FileIndex context rather than implementing another directory walker.

If the current Scanner architecture prevents this cleanly, make the smallest
architectural improvement necessary without starting Phase 9.

Finish by showing the exact working commands, including:

strategy-test --directory "/path"
strategy-test --directory "/path" --limit 20
strategy-test --directory "/path" --live-metadata --limit 20