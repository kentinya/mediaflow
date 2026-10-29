# Claude Code Instructions

@AGENTS.md

Follow [AGENTS.md](AGENTS.md) and the sole [Development Workflow](docs/development-workflow.md).
Committed `SLICE.md` plus the active `TASK.md` define Slice implementation scope. Independent
minor bugs use the user-authorized standalone Task under the workflow, with B owning completion.
Role assignment alone does not authorize sub-agent creation or implementation of a planning-only request.

Proceed autonomously through authorized in-scope work, affected tests, necessary fixes and handoff.
Developer runs new/changed/directly affected tests; B runs full regression and acceptance. Do not
ask whether to continue an obvious authorized step or run the assigned tests.

Ask only for material ambiguity, missing external authority/credentials, destructive effects or
risk of overwriting unrelated work. Before planning/implementation run `scripts/check_governance.py`
and preserve all pre-existing dirty/private files. Ordinary local checkpoints are allowed;
push, destructive Git and history rewriting require explicit authorization.
