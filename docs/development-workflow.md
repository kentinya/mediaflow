# MediaFlow Development Workflow

This is the sole authority for Slice/Task lifecycle, testing, Git, review and closure. Permanent
product/safety rules live in [AGENTS.md](../AGENTS.md). Current rules stay here; detailed history
stays in Git. The user-authorized 2026-10-18 testing allocation below replaces earlier instructions
that assigned full regression to Developer; coverage and accepted historical decisions are unchanged.

## 1. Formal management objects

- **Slice:** one complete large-version business capability, owned by A in root `SLICE.md`.
- **Task:** one coherent implementation unit planned/reviewed by B in `TASK.md`, either inside a
  committed Slice or an independent minor bug under the explicit scope in §3.1.

Fix rounds, old phase/letter names and rejected checkpoints are history, not additional objects.
Do not create fix ladders or archive directories of completed Task documents.

## 2. Roles

| Role | Owns |
|---|---|
| A — Slice Owner / Architect / Final Reviewer | Large-version Slice outcomes, surfaces, scope/deferrals/invariants, immutable Base, Contract/Roadmap boundaries, final Base..Head review and closure; no required involvement in independent minor bugs |
| B — Task Planner / Task Reviewer | Actual-code gap analysis, coherent Task plan, Difficulty/Test Level, acceptance, full regression, critical reproduction, Task PASS/FIX REQUIRED; Slice Closure Packet or independent minor-bug completion |
| Developer — Implementation Role | Active Task implementation, new/changed/directly affected tests, coherent checkpoint and concise handoff |

Developer cannot approve its own Task; B cannot conduct A Final Review of the same Slice. Explicit
user-authorized role exceptions must be disclosed. A scope/document action does not constitute
final review or acceptance. Read the corresponding [role experience](../AGENTS.md#testing-and-roles).

Roles assign responsibilities; they do not authorize spawning sub-agents or automatically starting
another role's work. Follow the user's explicit delegation and current work boundary. A request to
plan ends with the plan; implementation, push and deployment require their respective authorization.

## 3. State machines

```text
Task:  PLANNED → IN PROGRESS → READY FOR B REVIEW → PASS
Fix:   READY FOR B REVIEW → FIX REQUIRED → IN PROGRESS → READY FOR B REVIEW
Slice: PLANNED → ACTIVE → READY FOR A REVIEW → PASS / CLOSED
Fix:   READY FOR A REVIEW → FIX REQUIRED → B correction Task → READY FOR A REVIEW
```

After a Slice Task PASS choose NEXT TASK or SLICE READY FOR A REVIEW. Task has no CLOSED state;
only A closes a Slice. Independent minor bugs finish through B under §3.1.
`READY FOR B READINESS CHECK` is legacy-only and resolves on its first assessment
to ACTIVE with a real blocker/Task, or READY FOR A REVIEW with a Closure Packet.

A regression in already accepted behavior may use the independent minor-bug path, including a
P0/P1 correction; severity controls urgency and test risk, not automatic reopening of an old Slice.
Corrections required to accept an unclosed Slice stay in that Slice's current Task/fix loop.
New capabilities or changes to accepted outcome/architecture/safety boundaries require A's Slice
scope decision; never label them minor bugs to bypass that decision or reduce required testing.

Only explicit user instruction permits suspending an unclosed Slice for another priority. A must:

1. Preserve exact Slice/Task/review checkpoints on a named branch, original Base and implementation
   Head, and unrelated dirty/private files. Never rewrite history or stash/reset work away.
2. Set the suspended Slice/Roadmap to PLANNED with `Development Hold: FROZEN BY USER`; root Task
   becomes `NO ACTIVE IMPLEMENTATION TASK`. A reserved but unspecified Slice also stays PLANNED.
3. Start intervening work on an isolated accepted baseline unless the user explicitly authorizes
   integration. Large-version work needs a checkpointed ACTIVE Contract before B plans;
   independent minor bugs use §3.1 instead.
4. On resumption explicitly reactivate, recover the same Task ID/Base/Goal/Scope and reassess
   intervening changes. No silent repinning, blocker reset or conversion of rejected work to PASS.

### 3.1 Independent minor bugs

For a bounded correction to existing behavior, B directly plans one Task, Developer implements it,
and B independently reviews the entire Task Base..candidate, runs the assigned acceptance and
returns PASS or FIX REQUIRED. A does not create/reactivate/close a Slice for this path. The same
Task state machine, immutable Base, failure loop, safety and test ownership apply; small scope does
not imply a lower Test Level when permissions, mutations, schema or concurrency are affected.

Use these explicit fields in the root `TASK.md`:

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: <full existing ancestor commit SHA>
```

The Task records the user-authorized bug scope, observed existing entry, actual behavior/root cause,
fix boundaries, acceptance, Difficulty/Test Level and Developer/B test plans. Related accepted
Slices are references, not parents; preserve their Base/accepted Head/review/closure and keep
SLICE/Roadmap/Progress unchanged. No synthetic Slice, temporary governance exception or ignored
guard failure is needed.

An independent Task may coexist with a retained PASS / CLOSED or PLANNED Slice and its matching
Roadmap. It cannot silently replace ACTIVE, FIX REQUIRED or READY FOR A REVIEW work: keep an
in-Slice correction in its Task, or follow the explicit user-priority suspension procedure above.

After PASS, B records the exact reviewed Base..Head, actual results and remaining limitations,
then restores `# NO ACTIVE IMPLEMENTATION TASK` with a compact decision/checkpoint pointer.
Do not declare Slice CLOSED or add a minor-bug closure to the large-Slice ledger. Do not plan
additional work beyond the authorized correction. A planning-only draft may remain below the
no-active-implementation notice, clearly marked as a draft that does not authorize implementation;
replace that notice with the real Task metadata only when implementation work is authorized.

## 4. Slice Contract

`SLICE.md` contains ID/name/owner/status, immutable Base and Implementation Head, user goal,
applicable requirements/journey, Required Outcomes/Surfaces, boundaries, safety invariants, explicit
deferrals, acceptance, final validation, Closure Packet and A Final Review.

Base is the checkpoint immediately before Slice implementation, not the latest planning commit.
A factual clarification preserves acceptance meaning. A material change to outcomes, surfaces,
invariants or Task boundaries must be checkpointed by A; B then explicitly continues, legally
adjusts or replans the Task before implementation. B/Developer only update delegated factual fields.

On PARTIAL / RESCOPE, record the problem, still-valid facts and replacement Contract. Keep the
original Base when it remains the true start; otherwise create a new Slice ID from current HEAD
and retain the partial record. Never declare partial delivery PASS.

## 4.1 Repository governance preflight

Before planning or implementation run `python3 scripts/check_governance.py`. It reads committed
`HEAD:SLICE.md` and Roadmap, rejects an uncheckpointed working Contract, mismatched parent/status or
invalid/non-ancestor Bases, and never changes files. Slice Tasks require an ACTIVE/FIX REQUIRED
Slice, matching numeric Parent Slice and ACTIVE Roadmap. A PLANNED Slice cannot authorize a Slice
Task. Explicit `STANDALONE MINOR BUG` Tasks require `Parent Slice: NONE`, a valid Task status and
full existing ancestor Base; they retain the no-active-Slice/Roadmap checks described in §3.1.
Omitting Task Type keeps the existing SLICE behavior; NONE alone never selects standalone scope.

Record repository/branch/HEAD, status and workspace/Git writability. Preserve every pre-existing
change, including A-owned files, B Task state, reference-image deletions and private files. Do not
reset, restore, checkout over, clean, stash/drop or silently commit unrelated changes.

## 5. Task planning and sizing

B starts from the committed Contract or the user-authorized independent bug scope and actual
code/tests. Choose the largest reasonable coherent user behavior or architectural unit, across
necessary layers. Reuse existing capabilities; do not
split by field, assertion, internal module, UI label or optional proof.

A normal Slice usually needs roughly 3–7 Tasks, not a quota. More than 8 requires reassessing
fragmentation/boundaries with A. Fixes stay in the same Task unless the goal is genuinely independent.

Use [Task/TEMPLATE.md](../Task/TEMPLATE.md). Each plan identifies Goal/Required Outcome, immutable
Task Base, Difficulty (Low/Medium/High), Test Level, complete journey, scope, concrete acceptance,
simple ordered implementation steps, Developer affected tests, B acceptance tests and non-goals.
Use exact commands and explain covered risks; reference shared gates instead of copying them.

In the planning response, explain a real usage scenario and assess complexity/new states/races;
keep those assessments outside Task. For FIX REQUIRED, explain cause, introducing commit/time and
user trigger outside Task; put precise actionable corrections inside the same Task.

## 6. Test levels

Test Level describes acceptance coverage and risk, **not Developer's suite size**.

| Level | Use | Acceptance coverage owned by B |
|---|---|---|
| T0 — DOC | Factual docs/process maintenance without product, architecture, safety or Slice-scope changes | Relevant text/links/doc consumers and `git diff --check`; no full regression |
| T1 — TEST ONLY | Automation for unchanged production behavior | Changed and directly affected tests plus relevant static checks |
| T2 — LOCAL | Low-risk behavior within one boundary | Focused/module regression and relevant static checks |
| T3 — INTEGRATION | Application/API/Web/Persistence or comparable cross-layer behavior | Affected integration/native journeys and normal applicable quality gates; full suite only for a concrete shared-impact reason |
| T4 — FULL / HIGH RISK | Mutation, Storage, destructive effects, permissions, Active config, schema/migrations, concurrency, core pipeline/safety | Focused/integration coverage, full regression and all applicable safety/packaging/native gates |

Product/architecture/safety/scope changes are not ordinary T0. New risk returns to B for level
reassessment. Slice/Task select applicable coverage; they do not transfer full-suite ownership
back to Developer. Earlier unexecuted Developer-full-suite assignments are now B assignments.

### Test plans and execution stages

| Stage | Responsible execution |
|---|---|
| Development / fixes | **Developer:** new/modified tests, known failing cases, directly affected regressions/integration and relevant changed-file checks. No full Python/Web/E2E or release matrix. |
| Developer handoff | Freeze a coherent candidate after affected tests; record actual commands/results and known failures. Submit READY FOR B REVIEW without waiting for full regression. |
| B Review | **B:** inspect implementation against Task, reproduce critical behavior, and run the assigned acceptance gates on the submitted candidate. T4 includes full regression before PASS. |
| Slice Final | **B:** ensure the current Slice candidate has complete Contract-level regression/safety/packaging/native validation and record it in the Closure Packet. |
| A Final Review | Review entire Slice Base..Head and results; independently check material uncertainties, without mechanically repeating B's full suites. |

Do not relabel whole-repository suites as “affected” and give them back to Developer. Developer
need not prepare a full-suite evidence dossier. B owns full runs/logs; Developer's missing full
results are not a product defect or reason to return implementation work.

A proven Task blocker permits early FIX REQUIRED before expensive gates. Developer fixes it and
runs the failing/affected tests; B runs the required acceptance on the corrected candidate. Actual
failures stay visible; never delete assertions, hide skips, add retries or weaken timeouts to pass.
Unavailable required gates remain pending/disclosed, not PASS; environment/evidence work stays with
B unless actual Task implementation must change. Only explicit authorized exceptions waive gates.

### Shared full regression commands

B uses these for applicable T4/SLICE FINAL coverage. A pure governance/document change runs only
its affected checks. Task/Slice add risk-specific commands instead of duplicating this list.

| Area | Commands / required behavior |
|---|---|
| Python quality | `.venv/bin/python scripts/check_governance.py`; `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`; `.venv/bin/python -m unittest discover -s tests`; `.venv/bin/python -m compileall -q mediaflow tests scripts`; `.venv/bin/python -m pip check` |
| Examples / forbidden dependencies | `.venv/bin/mediaflow --config config/strategy.example.json config validate`; `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`; `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` must have no match (exit 1) |
| Web (cwd `web/`) | `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run test -- run`; `npm run build`; `npm run test:e2e` |
| Real application / visual | Slice-specific real Python/API/SQLite/Worker browser journeys against production assets; inspect actual desktop/narrow screenshots and interaction where required |
| Packaging / production | `.venv/bin/python -m pip wheel . --no-deps -w dist`; `.venv/bin/python scripts/wheel_smoke_test.py <exact-wheel>`; installed consumers outside source; applicable Docker/restart proofs; `.venv/bin/python scripts/docker_release_security_smoke_test.py --image <candidate-image>` |
| Persistence / safety | Applicable fresh/reopen/migration/failure-atomicity, RBAC, pins/fences, zero-mutation analysis, explicit authority, C→A identity and completed/uncertain non-replay checks; `git diff --check` |

### Verifiable evidence and reuse

Keep reports concise: candidate SHA/range, command/cwd, actual result/counts/skips, known failure and
raw-log/CI reference. Add configuration/dependency/fixture/worker/artifact identity only where it
matters to reproducibility. B retains full-run logs and required screenshots/artifact digests in
CI or stable ignored storage such as `.git/validation-evidence/<sha>/<run>/`; never expose secrets
or treat a /tmp-only path as durable handoff. Local artifacts are not claimed remotely reachable.

B may use CI runs it triggers/checks, and reuse its own matching acceptance runs. Reuse requires the
same source/tests/harness/dependencies/config and artifacts; report-only successors need an explicit
diff proving execution inputs unchanged plus affected doc checks. Changed executable inputs require
fresh assigned acceptance; T4 still needs its full coverage. Full runs containing focused cases do
not require duplicate focused runs. Matching last-Task validation can also satisfy Slice-final gates
when it covers every final requirement; otherwise B runs the missing coverage on the final candidate.
Do not accept PASS labels without actual results or invent Base failures without reproducing them.

## 7. Task execution and review

1. B checks governance and plans one Task in committed Slice scope or the independent minor-bug scope.
2. Developer implements, runs affected tests, checks scope/private files and hands off an immutable
   checkpoint with a compact report: changes, behavior, commands/results, remaining work and risks.
3. B reviews explicit SHA/Base..Head, verifies actual behavior and performs its acceptance plan.
4. FIX REQUIRED lists only Task blockers with simple fix steps; correction remains in that Task.
5. For a Slice Task, PASS reevaluates **all** Slice outcomes/surfaces. If incomplete, next coherent
   Task; if complete, stop planning, finish Slice-final validation and submit SLICE READY FOR A REVIEW.
   For an independent minor bug, PASS completes the authorized correction and B finishes under §3.1.

Task PASS does not close a Slice or update Roadmap/Progress. B results may be in review output;
there is no mandatory standalone `docs(review)` commit. When no next Task is requested, root Task
may become `# NO ACTIVE IMPLEMENTATION TASK` with a compact reviewed-SHA/decision pointer; the old
Task stays in Git. A terminal PASS is not an active implementation Task for the governance guard.

## 8. Git and checkpoint strategy

One Task normally yields a coherent implementation checkpoint; fixes add checkpoints, never amend
reviewed history. Inspect complete diff/manifest, status, whitespace, frozen scopes and private
files before committing. Ordinary authorized local checkpoints need no separate approval; push,
destructive Git and history changes require explicit user authorization. No force push or rewriting
accepted/rejected history. Preserve reachability branches required by a Contract or user hold.

## 9. B stop rule and Closure Packet

Stop creating Tasks once Slice Required Outcomes/Surfaces or the independent bug's acceptance
are satisfied. Optional tests, labels, P2 cleanup and out-of-scope ideas cannot block completion
or create another Task. P0 means credible
data loss/destruction/security/secret/authority or whole-journey outage; P1 means an unmet required
outcome/surface/recovery or architecture/safety invariant; P2 means non-blocking quality/improvement.
Do not downgrade safety or required outcomes.

For a Slice, submit one compact packet (independent minor bugs use §3.1's B completion instead):

```text
Slice / Base SHA / Implementation Head:
Required Outcomes and Surfaces: complete / incomplete
Implemented / Tasks completed:
Final Tests and Safety Evidence: actual results, reuse, skips/unavailable
Known Non-blocking Issues / Explicitly Deferred:
Documentation Reconciliation Needed:
Reusable Lesson Candidates: optional, 1–3 per role
Decision: SLICE READY FOR A REVIEW
```

A genuine P0/P1 discovered during final preparation receives one focused correction Task in the
same Slice. Legacy names never create an additional fix lifecycle.

## 10. A Final Review and closure

A reviews entire Base..Implementation Head for outcomes/journey, integration, safety, failure and
recovery, actual validation and document truth. Decide PASS, FIX REQUIRED (only in-Slice P0/P1 or
unmet outcomes), or PARTIAL / RESCOPE (Contract problem). Record reviewed range and blockers in
SLICE; FIX REQUIRED does not fill closure reconciliation or erase prior facts.

After PASS, reconcile CURRENT docs, Slice/Roadmap/Progress, requirements, journey/architecture and
operator guidance in one coherent closure checkpoint. Record already-reviewed Implementation Head,
`PASS / CLOSED`, and `TASK.md` as NO ACTIVE IMPLEMENTATION TASK with next action A SELECTS THE NEXT
LARGE SLICE. Do not hide new product/scope changes in factual reconciliation. A selects the next
large Slice only after closure; selecting it is a separate action.

At closure, review [A](agent-experience/slice-owner-architect-final-reviewer.md),
[B](agent-experience/task-planner-reviewer.md) and
[Developer](agent-experience/developer-implementation-role.md) experiences: keep short reusable
problem→approach→applicability lessons, merge duplicates, add at most 1–3 only when useful.

## 11. Document responsibilities

| Document | Keep |
|---|---|
| AGENTS | Permanent product/architecture/safety and scope principles |
| This workflow | Lifecycle/testing/Git/review/closure rules, once |
| SLICE / TASK | Current contract/unit and compact decisions; detailed revisions in Git |
| Task/TEMPLATE / role experience / CLAUDE | Thin workflow-linked templates/guidance, no competing rules |
| Roadmap / Progress | Large-Slice priority/status / accepted closure ledger; short current pointer |
| Requirements / V2 Requirements | Complete stable product scope/IDs and explicit authorized amendments |
| Product Experience / Architecture | Journeys / CURRENT vs TARGET contracts, not development diaries |

Reference rules rather than copying them. Do not append each command/run/fix to scope documents.
Superseded current prose may be removed after its checkpoint is reachable; retain stable IDs,
accepted Base/Head/closure facts, current obligations and explicit deferrals. `docs/history/` stays
LEGACY / READ ONLY; no rewrite, new Task archive or mechanical renumbering of old phases/fixes.

## 12. Workspace and private configuration

Never read/change user runtime databases, production media or secrets for routine validation.
Use approved example configs and isolated temporary/fake/local fixtures unless a dedicated plan
explicitly authorizes an external test environment. `config/alist.json` stays ignored, untracked
and unstaged. Do not expose tokens, private endpoints, authorization headers, cookies or private paths.

## 13. Legacy migration

Historical accepted/rejected commits, original partial/hold/closure snapshots and preserved
`docs/history/` remain immutable and reachable. Completed Task text may leave the working tree when
no active boundary/tool/link depends on it; Git is the detailed history. Omission from compact
current documents never weakens required product, architecture, safety or active Contract scope.
