# MediaFlow Development Workflow

This document is the sole authoritative source for environment capability checks, implementation,
Git checkpoints, independent review, closure, push gates, and next-slice sequencing. `AGENTS.md`
remains authoritative for permanent safety, architecture, role separation, and scope control;
product and engineering documents define what to build. If another document summarizes this
workflow, this document controls.

## Fixed workflow

Every Phase, Slice, Task, and correction follows this order without overlap:

```text
Environment Check → Implementation → Tests → Git Checkpoint → High Review
→ PASS → Record SHA / CLOSED → Next Slice
```

The corresponding status machine is:

```text
IN PROGRESS
→ READY FOR COMMIT
→ COMMITTED <SHA>
→ READY FOR HIGH REVIEW
→ PASS / CLOSED
→ NEXT TASK
```

A status may advance only when its preceding gate is complete. The implementation role reports
actual state; it does not skip states for convenience.

## Non-negotiable gates

### No Commit, No Close

A passing worktree, test report, completion report, patch, recovery snapshot, or review conversation
is not a checkpoint. A Phase, Slice, Task, or correction cannot be `CLOSED` until its complete,
coherent implementation has a Git commit.

The checkpoint SHA must identify a buildable, truthful snapshot containing every required tracked
file, including new files. A follow-up commit that merely supplies files accidentally omitted from a
claimed complete commit does not make the original checkpoint coherent.

### No High PASS, No Next Phase

High Review can inspect only an explicit commit SHA. It must not review a floating working tree,
staged index, patch without a checkpoint, branch name, or mutable `HEAD` reference as its subject.

The next Phase or Slice may start only after:

1. implementation and required tests are complete;
2. the complete change has a Git checkpoint;
3. High Review inspects that exact SHA and returns `PASS`;
4. `docs/progress.md` records Status, Commit SHA, and High Audit;
5. `docs/roadmap.md` records the resulting Phase gate.

If the preceding accepted Slice still has uncommitted changes, the next Slice is prohibited.
Multiple accepted Phases must not accumulate in one working tree.

## Environment Check

Run this preflight at the start of every new workspace or session, before editing:

```bash
pwd
git rev-parse --show-toplevel
git rev-parse --git-dir
git branch --show-current
git rev-parse HEAD
git status

test -w . && echo WORKTREE_WRITABLE || echo WORKTREE_READ_ONLY
test -w "$(git rev-parse --git-dir)" && echo GIT_WRITABLE || echo GIT_READ_ONLY
test -w "$(git rev-parse --git-path index)" && echo INDEX_WRITABLE || echo INDEX_READ_ONLY
```

Also record the platform-reported sandbox, filesystem, workspace permission, and approval mode when
available. Worktree access and Git metadata access are separate capabilities.

Classify the session as one of the following modes.

### Git-writable / Full Access

This mode requires both the Git directory and index to be writable. The current capable Agent owns
normal in-scope Git operations and may directly run `git add`, `git commit`, and `git push`
subject to the checkpoint and push rules below.

```text
Commit ownership is capability-based, not user-based.
```

Do not ask the user to perform a routine commit merely because an Agent implemented the change.
Full Access does not authorize force push, `git reset --hard`, rewriting accepted history, bypassing
branch protection, or including unrelated/private files.

### Git-read-only / workspace-write

This mode applies when the worktree is writable but the Git directory or index is not writable. The
Agent may implement and test the current Task, but may advance only to:

```text
READY FOR COMMIT
```

It must report the exact manifest and hand the unchanged worktree to a Git-capable environment.
There, a capable Agent creates the checkpoint. Only after a commit SHA exists may status advance to
`COMMITTED <SHA>` and `READY FOR HIGH REVIEW`.

Never bypass a read-only Git boundary with `chmod`, `chown`, `sudo`, remounting, alternate Git
metadata, or a hidden repository. Read-only Git is a capability boundary, not a Task failure.

## Task preparation

Before implementation:

1. read the files required by `AGENTS.md`, including this workflow;
2. verify the preceding dependent Slice is `PASS / CLOSED` with its checkpoint SHA recorded;
3. verify no preceding accepted implementation remains uncommitted or required-but-unpushed;
4. confirm `TASK.md` defines one bounded vertical journey, failure/recovery, acceptance criteria,
   tests, non-goals, and a closure checklist;
5. inspect the actual code and tests before editing.

Historical files under `Task/` are evidence and must not be rewritten merely to adopt a newer
template. `Task/TEMPLATE.md` governs new Task documents; the current `TASK.md` carries the active
closure gate.

This workflow applies immediately. Do not guess or fabricate SHAs for older historical narratives.
An older closure record without a proven SHA is legacy documentation debt and cannot unlock new
dependent work until an audited backfill identifies its exact commit.

## Implementation and tests

Implement only the current `TASK.md`. Preserve all architecture and safety invariants in
`AGENTS.md`. Add automated acceptance and regression coverage for success, invalid input, failure,
recovery, conflict/concurrency, and zero mutation where applicable.

Run focused tests first, then the complete applicable suite and repository quality gates. The
completion report lists commands, results, skips, limitations, changed files, and scope deviations.
Passing tests advances the Task only to `READY FOR COMMIT`.

## Git Checkpoint

Before committing:

1. inspect `git status`, `git diff`, `git diff --stat`, `git diff --name-status`, and
   `git diff --check`;
2. verify the manifest contains every required new and modified file;
3. verify unrelated and private files are absent;
4. verify the proposed commit is coherent and buildable on its parent;
5. create the commit when the current environment is Git-capable;
6. report the full 40-character SHA and advance through `COMMITTED <SHA>` to
   `READY FOR HIGH REVIEW`.

The checkpoint commit does not declare its own High result. Its SHA is recorded in the review
handoff. After High returns PASS, the factual closure record writes that reviewed implementation SHA
and High Audit to `docs/progress.md`; this avoids requiring a commit to contain its own SHA.

Do not amend or rewrite a commit that has already passed High Review.

## High Review and correction loop

High Review inspects the explicit checkpoint SHA, its parent, code, tests, documentation, and actual
repository state. It verifies the Task journey, failure/recovery, concurrency, safety boundaries,
test strength, commit coherence, secret exclusion, and documentation accuracy.

If High returns `FIX REQUIRED`, the mandatory loop is:

```text
Medium fix → new commit → High re-review
```

The next Phase remains blocked. The correction receives a new commit SHA and High reviews that new
SHA. Do not directly overwrite, amend, squash away, or otherwise rewrite a commit that already
passed High. Reconstruction of unaccepted history is allowed only when an explicit integration Task
authorizes it.

If High returns `PASS`, record the reviewed checkpoint SHA and audit result. Only then does status
become `PASS / CLOSED` and permit `NEXT TASK`.

## Push gate

A major Phase closure or integration completion must be pushed before it is recorded as fully closed
or safe for downstream integration. Verify that the reviewed commit is reachable from the intended
remote branch.

Do not allow multiple accepted but unpushed Phases to accumulate. A temporary unpushed checkpoint is
permitted only within the current review loop; it does not authorize a later major Phase. Force push
and rewriting accepted remote history are prohibited.

For ordinary non-closure Tasks, push timing follows the repository's branch policy. Git capability
permits the Agent to push, but does not require pushing an unreviewed checkpoint directly to a
protected or shared branch.

## Required records

`docs/progress.md` is the factual checkpoint ledger. Every accepted Phase/Slice entry contains:

```text
Status: PASS / CLOSED
Commit SHA: <full 40-character reviewed checkpoint SHA>
High Audit: PASS — <date and concise evidence reference>
Push: <remote branch containing the SHA, when required>
```

Before commit, pending work records `Status: READY FOR COMMIT` and `Commit SHA: PENDING`. After a
checkpoint exists, the review handoff reports `COMMITTED <SHA>` and
`READY FOR HIGH REVIEW`. A `FIX REQUIRED` record preserves the rejected SHA and correction
requirement rather than overwriting history.

`docs/roadmap.md` records only the Phase gate and next allowed boundary. It does not duplicate test
logs or this workflow. `TASK.md` records the active closure checklist. Stable requirements link
here instead of copying process rules.

## Private configuration and secrets

`config/alist.json` must remain untracked, unstaged, and ignored. Its committed companion is
`config/alist.example.json`, which contains only a non-routable example endpoint and an environment
variable name—not a token. The broader canonical examples remain
`config/strategy.example.json` and `config/mediaflow.phase13.2.example.json`.

Real tokens, private endpoints, credentials, cookies, authorization headers, and user paths must not
enter examples, tests, Task evidence, documentation, commits, or review output. Never inspect or
copy a private configuration merely to build an example.

Before every checkpoint, push, and High Review, verify:

```bash
git check-ignore config/alist.json
test -z "$(git ls-files -- config/alist.json)"
test -z "$(git diff --cached -- config/alist.json)"
```

If a private file is tracked or staged, stop the checkpoint and remove it from the proposed commit
without exposing its contents.
