# Development Workflow Rules Update

This Task follows [the authoritative development workflow](docs/development-workflow.md).

## User Problem

The repository previously allowed tested and reviewed Phase work to accumulate in a writable working
tree while Git metadata was read-only. Documentation could then say `PASS / CLOSED` without a
durable commit checkpoint, and later recovery had to reconstruct semantic history. Contributors need
one enforceable workflow that distinguishes implementation evidence from committed, independently
accepted work.

## Required Outcome

- `docs/development-workflow.md` is the sole authoritative implementation/checkpoint/review flow.
- Environment capability, commit-before-close, and High-PASS-before-next-Phase gates are explicit.
- Every accepted Phase/Slice records Status, full Commit SHA, and High Audit.
- Git-writable Agents own the checkpoint; Git-read-only Agents stop at `READY FOR COMMIT`.
- New workspaces inspect worktree, `.git`, index, sandbox, and approval state before editing.
- Current/future Task documents carry a closure checklist; historical Task archives remain unchanged.
- Private `config/alist.json` remains ignored/untracked and has a secret-free
  `config/alist.example.json` companion.

## Scope

- Add `docs/development-workflow.md`.
- Minimally synchronize `AGENTS.md`, `docs/roadmap.md`, `docs/progress.md`,
  `docs/requirements.md`, this `TASK.md`, `Task/TEMPLATE.md`, and `.gitignore`.
- Add the bounded secret-free `config/alist.example.json` template without reading private config.
- Record the already accepted Phase 22.4 and recovered Phase 22.5 integration checkpoint SHAs.
- Do not modify product code, tests, historical Task archives, or Git history.

## Acceptance Criteria

- [x] The fixed sequence is documented exactly as `Environment Check → Implementation → Tests →
      Git Checkpoint → High Review → PASS → Record SHA / CLOSED → Next Slice`.
- [x] The state machine is `IN PROGRESS → READY FOR COMMIT → COMMITTED <SHA> → READY FOR HIGH
      REVIEW → PASS / CLOSED → NEXT TASK`.
- [x] “No Commit, No Close” and “No High PASS, No Next Phase” are mandatory gates.
- [x] `FIX REQUIRED` mandates correction, a new checkpoint, and a new High Review.
- [x] Commit ownership is capability-based rather than user-based.
- [x] Major closure/integration push gates prohibit accepted-but-unpushed Phase accumulation.
- [x] Uncommitted accepted work blocks the next Phase and cannot accumulate across Phases.
- [x] Roadmap contains only a concise Phase gate reference/state.
- [x] Progress contains Status / Commit SHA / High Audit records.
- [x] Requirements references the workflow without duplicating it.
- [x] The Task template and this Task contain closure checklists.
- [x] Documentation links and `git diff --check` pass.
- [x] `config/alist.json` is ignored, untracked, unstaged, unread, and absent from the patch.
- [x] `config/alist.example.json` contains no token or private endpoint.

## Closure Gate

- [x] Workspace preflight completed.
- [x] Preceding integration state passed final acceptance.
- [x] Documentation implementation and validation complete.
- [ ] Commit created and full SHA recorded.
- [ ] High Review inspected the committed SHA and returned PASS.
- [ ] Progress and roadmap record this Task's final checkpoint.
- [ ] Next Slice authorized.

Current checkpoint state:

```text
Status: READY FOR COMMIT
Commit SHA: PENDING
High Audit: PENDING
```

Current capability mode is Git-writable / Full Access: worktree, `.git`, and index are writable;
sandbox filesystem access is unrestricted and approval mode is `never`. The capable Agent will
create the checkpoint after validation. This is not a major Phase closure, so push is not required
before High Review.

## Non-goals

- No product behavior, schema, API, UI, test, or dependency changes.
- No rewriting historical Task archives or historical audit narratives.
- No force push, `reset --hard`, accepted-history rewrite, unrelated push, permission change, or
  sandbox bypass.

## Validation

Run JSON parsing for the example, documentation local-link validation, targeted terminology/conflict
searches, `git diff --check`, and final Git/sensitive-file status inspection.

## Completion Report

Report changed files, new gates, conflicts found/resolved, validation, checkpoint limitation, and
whether any later human decision is required.
