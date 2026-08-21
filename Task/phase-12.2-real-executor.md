# Phase 12.2 — Real Organizer Executor

## Goal

Enable real filesystem execution from OrganizePlan.

DryRun remains default.

Real execution requires explicit confirmation flag.

---

# Pipeline

OrganizePlan

↓

OrganizerExecutor

↓

Storage Adapter

↓

ExecutionResult


---

# Execution Modes


## DryRun

Default.

No mutation.


## Execute

Requires:

--execute


---

# Supported Operations


## MOVE


Steps:

1. validate plan

2. verify source exists

3. verify destination

4. create destination directory

5. move through Storage

6. verify destination

7. record result


---


## COPY


Steps:

1. create destination

2. copy

3. verify

4. record


---


## HARDLINK

If supported:

create link

verify


---


## SYMLINK

If supported:

create link

verify


---

# Destination Root


OrganizePlan currently returns:

relative destination:


Movies/Anime/movie/file.mkv


Executor must combine:


MediaLibrary.root


+

relative destination


Example:


MediaLibrary:

/mnt/HDD_2/整理库


Plan:

Movies/Anime/movie.mkv


Final:


/mnt/HDD_2/整理库/Movies/Anime/movie.mkv



---

# Safety


Before execution reject:


- missing source

- invalid destination

- traversal

- absolute relative path

- unresolved conflict

- overwrite without policy


---

# Conflict Handling


Default:

NO overwrite.


If destination exists:


Result:

FAILED


Conflict:

DESTINATION_EXISTS


---

# ExecutionResult


Fields:


status

operation

source

destination

startedAt

finishedAt

duration

createdDirectories

completedOperations

warnings

errors


Status:


SUCCESS

FAILED

PARTIAL

SKIPPED



---

# Logging


Each execution writes:


ExecutionLog:


timestamp

planId

operation

source

destination

result

error


---

# CLI


Add:


--execute


Example:


DryRun:


strategy-test \
 --show-plan \
 file.mkv



Execute:


strategy-test \
 --show-plan \
 --execute \
 file.mkv



Output:


EXECUTION RESULT


Mode:

EXECUTE


Operation:

MOVE


Source:

...


Destination:

...


Status:

SUCCESS



---

# Tests


## Execute


- local move success

- local copy success

- hardlink

- symlink


## Failure


- source missing

- destination exists

- invalid path

- permission error


## Safety


- dryrun mutation zero

- execute requires flag

- no overwrite


## Integration


Test:


LocalStorage

SMBStorage

OpenListStorage

S3/R2Storage


where supported.



# Regression


Verify:


Parser

Recognition

Metadata

Naming

Classification

OrganizePlan


unchanged.



# Completion Criteria


Phase 12.2 accepted when:


- execute flag works

- move works

- copy works

- conflicts protected

- logs generated

- rollback/error handling works

- tests pass


Do not start Phase 13.


Final:


## Phase 12.2 Result

PASS / FAIL


## Execute Examples


## Safety


## Logs


## Regression


## Final Recommendation
