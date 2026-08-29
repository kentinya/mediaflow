# Claude Code Instructions

@AGENTS.md

`AGENTS.md` is the authoritative permanent repository policy. Detailed Slice/Task workflow is owned
only by `docs/development-workflow.md`; current scope is `SLICE.md` plus an active `TASK.md`.

## Execution Behavior

For an already approved Task inside the current Slice, proceed autonomously through all clearly
required in-scope steps.

Do not stop to ask whether to:
- continue with the next obvious implementation step;
- run tests;
- fix issues required to satisfy the current task;
- complete remaining acceptance criteria.

If the next step is clearly required by the current task, continue automatically.

Only ask when:
- a material requirement is genuinely ambiguous;
- the operation is destructive or difficult to reverse;
- credentials or external authorization are required;
- continuing may overwrite or discard unrelated user work.

## Git

Ordinary local commits may be created without asking.

Do not perform:
- git push
- force push
- git reset --hard
- destructive git clean
- history rewriting

unless explicitly authorized.
