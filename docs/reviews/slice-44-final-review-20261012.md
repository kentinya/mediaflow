# Slice 44 — A Final Review / 2026-10-12

**Decision: FIX REQUIRED.** No P0 found; A44-14 is the remaining P1 blocker in RO-6.
A44-15 is P2 / NON-BLOCKING after the current-adapter reachability reassessment below.

| Authority | Value |
|---|---|
| Slice Base | `853973dbbf8289fa2ad40657033e94e870a690e4` |
| Reviewed Implementation Head | `5ec0f3fdfa81b28bc12384e65b595a0f917dc562` |
| Executable Head | `b4a14e0284b66597baf306a95224fc1dabf60033` |
| Contract checkpoint | `7e96ebf314e4eab22a72d98028a775f248118138` |
| Role | A — Slice Owner / Architect / Final Reviewer |

The complete Base..Head range contains 153 changed files. Report and executable Heads differ
only in `TASK.md`. This is Slice Final Review after B's Task 44.9 PASS, not another Task review.
The user-approved smaller exceptional-recovery promise is the acceptance authority. The required
correction needs no rescoping, new engine or stronger recovery promise. Prior Task PASS,
rejected reviews and the recovery-rescope decision remain historical facts.

## P1 / A44-14 — Mixed discovery freezes an associated Trailer as a primary

**Required outcome:** RO-6; acceptance 27/28; REQ-ATT-001/003. Existing main/attachment semantics
must survive folder and mixed selection, discovery counting and frozen intent admission.

With enabled published attachment policy, create this temporary ResourceLibrary content:

```text
Movies/
  Other/                       (empty directory)
  Film.2001.mkv
  Film.2001-trailer.mp4
```

Use the real managed Local/SQLite/API/discovery fixture in `tests/test_media_discovery.py`.
POST the discovery endpoint, let the runner settle, then Finalize its current expected version:

| Selection paths | Discovery status | Primary sources | Frozen intent items |
|---|---|---:|---:|
| `Movies` | completed | 1 | 1 |
| `Movies/Other`, `Movies/Film.2001.mkv`, `Movies/Film.2001-trailer.mp4` | completed | 2 | 2 |

The second intent contains the Trailer as an independent primary. All three entries are in the
same browsed directory, and the native Files batch handler submits this exact mixed shape when
any selected eligible entry is a directory
(`web/src/features/library/StorageFilesPage.tsx:3442`). No invalid scope or hypothetical UI action
is needed. Both cases make zero media mutations and create no execution Task.

**Cause:** `MediaDiscoveryService._advance` observes explicit `pending_files` separately
(`mediaflow/application/media_discovery.py:1184`); these observations do not populate the entries
used for attachment demotion. Walked file observations populate both association collections
(`mediaflow/application/media_discovery.py:1345`). Consequently the same policy/matcher corrects
walked Trailers but misses explicitly selected ones inside mixed discovery. Existing tests cover
folder/page association and orphan/disabled-policy cases; the 110-test module passes without this
mixed case.

**Consequence:** an ordinary supported selection freezes an incorrect primary set, loses
main/sidecar association at the discovery-to-intent boundary and can consume primary capacity
with attachments. No actual subsequent execution or data loss is claimed by this reproduction.

**Correction outcome:** explicit and walked files in the reviewed mixed scope retain the existing
association semantics and one primary authority for the main media. Discovery counts and the
frozen intent agree; orphan/disabled-policy behavior, bounded scope and separate exact Preview/
execution authority remain intact. This corrects the retained A44-12 obligation for a missed
selection entrance; it does not select a general Extras engine.

## P2 / A44-15 — Defensive exact-type check gap in the simulated Executor scenario

**Applicable contract:** RO-1; acceptance 2/4; exact supported type revalidation and observed-source
change safety on both library kinds. Optional fingerprints do not remove the type check.

Ground confirmed FILE evidence with no fingerprint, size 8 and a fixed modification time.
Have the fresh synthetic Storage `stat` return SYMLINK or OTHER with the same size/time.
Call the real `OrganizerExecutor.execute_direct_rename` or `execute_direct_delete`:

| Fresh observed type | Operation | Actual result | Mutating Storage call |
|---|---|---|---|
| SYMLINK | Rename | SUCCESS | invoked |
| SYMLINK | Delete | SUCCESS | invoked |
| OTHER | Rename | SUCCESS | invoked |
| OTHER | Delete | SUCCESS | invoked |

The probe Storage port records calls and rejects content reads. These are fake media effects,
not Local/remote mutations. This demonstrates the shared Executor behavior without asserting
that every current adapter produces the same metadata for each unsupported entry type.

**Cause:** `_direct_entry_version_mismatch` compares only whether each observation is DIRECTORY
(`mediaflow/application/organizer.py:2636`). FILE, SYMLINK and OTHER all compare as false;
without a fingerprint the remaining size/time comparisons pass. Both Delete's
`_direct_exists_preflight` and Rename's preflight consume this helper. Admission rejects
unsupported entry kinds, but their later observable change is not rejected here. The transfer
source preflight repeats the same directory/non-directory comparison
(`mediaflow/application/organizer.py:2795`); applicable consumers need consistent correction.

**Consequence:** an entry visibly different from the authorized supported FILE can reach a
Rename/Delete Storage mutation. This is an observable authority/type change, beyond the accepted
limitation that indistinguishable metadata cannot prove byte identity. No real data loss is
claimed, and no mandatory fingerprint or content hashing is requested.

### Actual likelihood and severity reassessment — 2026-10-12

The user asked whether this happens often in real use. A examined the current adapters:

| Current adapter | Relevant behavior | What it establishes |
|---|---|---|
| Local | Every stat entry supplies inode/ctime fingerprint (`local_storage.py:124`). | The original no-fingerprint scenario is not the normal Local observation; a changed fingerprint is rejected. |
| OpenList | Client/domain stat has a directory boolean and projects FILE/DIRECTORY (`openlist_storage.py:455`). | No SYMLINK/OTHER observation reaches this helper through the current projection. |
| S3/R2 | Object and prefix stat project FILE/DIRECTORY (`s3_storage.py:417`). | The original SYMLINK/OTHER combination is not reproduced by this adapter. |
| SMB | Production stat uses isdir to project FILE/DIRECTORY (`smb_storage.py:565`); listing can separately report SYMLINK. | The injected fresh SYMLINK/OTHER stat is not a demonstrated production-client observation. |

The four original cases prove the helper's behavior when those synthetic conditions are supplied.
They do not measure occurrence frequency or prove an actual supported-adapter mutation path.
No real-adapter reproduction or production incident is established. Other limitations in how an
adapter observes links would require their own grounded assessment; they are not proved by this
probe or selected for a speculative refactor here.

The original **P1 severity was insufficiently grounded**. A reclassifies A44-15 as **P2 /
NON-BLOCKING**, superseding the initial classification in
`58e3334ec71f6c26de1651770263b805bc1e55e3` while retaining the original reproduction and history.
It cannot independently prevent Slice PASS. A44-14 remains the sole confirmed P1 in this review.
No numerical probability is claimed and no current adapter is declared universally type-safe.

**Non-blocking recommendation:** require the exact supported type in the shared defensive check,
retaining optional fingerprints and metadata-only behavior. This does not require extra operator
confirmation, a new recovery mechanism or an adapter redesign. The existing safety Contract is
unchanged; a concrete current-adapter path/effect can justify later severity reassessment.

## Verification and handoff

- Fresh A discovery regression: **110 tests / OK**, 24.391 test seconds, zero skips/failures.
  Existing ResourceWarnings remain visible. The two additional probes exit 1 because their
  required-outcome assertions fail, with detailed JSON/log receipts; a reproduced defect is not
  a passing product gate.
- B's fresh full Python **2431 run / 7 skipped / OK**, full Web **74 files / 1106 passed**,
  native/Docker, migration, wheel and security evidence is readable. A checked the packet and
  original receipts/provenance; those green gates miss A44-14 and the simulated A44-15 gap. A did
  not independently repeat the remaining expensive gates after proving A44-14 (workflow §6).
  Corrected candidates still require the applicable final T4 gates before PASS.
- Seven external/endurance profiles remain SKIP/UNAVAILABLE. Existing P2 wording/assertion issues
  and the explicitly deferred exceptional-recovery enhancements do not independently block PASS.
- Local evidence: `.git/validation-evidence/5ec0f3fdfa81b28bc12384e65b595a0f917dc562/a-final-20261012/`.
  It includes exact commands/source SHA/exit codes, raw logs, JSON observations and initial input
  hashes. The mixed probe's first invocation expected the wrong admission HTTP status; that
  harness error is disclosed, then corrected to the documented 202 before reproducing the defect.
- Governance passes before the A status change. The existing checker rejects FIX REQUIRED with
  the truthful no-active-Task handoff, contrary to the workflow's required transition; the actual
  post-checkpoint failure is retained. A does not fabricate a Task or change the guard. This
  previously recorded governance inconsistency is separate from the product blocker.
- Only A review documentation is checkpointed. The pre-existing TASK edit, B Closure Packet and
  user images remain intact and unstaged. No implementation, closure reconciliation, CURRENT
  promotion, frozen Slice 43 change, next Slice or push occurs.

**NEXT ACTION: B PLANS ONE FOCUSED CORRECTION TASK.**
