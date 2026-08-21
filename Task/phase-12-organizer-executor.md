# Phase 12 — OrganizerExecutor + ExecutionResult

## Goal

Implement execution layer.

Convert:

OrganizePlan

into:

ExecutionResult


Pipeline:


Parser

↓

Recognition

↓

Metadata

↓

Naming

↓

Classification

↓

OrganizePlan

↓

OrganizerExecutor

↓

ExecutionResult



---

# Strict Boundary


Phase 12 introduces filesystem mutations.


However execution MUST be controlled.


Support:


- dry-run
- real execution


Default mode MUST be dry-run.



---

# Components


Implement:


## OrganizerExecutor


Responsibilities:


- execute OrganizePlan
- call Storage abstraction
- handle filesystem operations
- produce ExecutionResult



---


## ExecutionResult


Fields:


status

operation

source

destination

createdDirectories

movedFiles

copiedFiles

linkedFiles

warnings

errors

duration



Statuses:


SUCCESS

DRY_RUN

FAILED

SKIPPED

PARTIAL



---

# DryRun Mode


DryRun must:


NOT:

- create directory
- move
- copy
- delete
- rename


Return:


ExecutionResult:


status:

DRY_RUN


Example:


Operation:

MOVE


Source:

old/file.mkv


Destination:

new/file.mkv


Result:

DRY_RUN



---

# Real Execution


Support:


MOVE


Flow:


1.

validate plan


2.

check source exists


3.

create destination directory


4.

execute move


5.

verify destination


6.

record result



---


COPY


Flow:


1.

create destination


2.

copy file


3.

verify size/hash(optional)


4.

record result



---


LINK


Support:


- hardlink
- symlink


according to policy.



---

# Storage Abstraction


OrganizerExecutor MUST NOT directly call:


os.rename

shutil.move

open


Use:


Storage interface


Existing:


LocalStorage

SMBStorage

OpenListStorage

S3/R2Storage



---

# Safety


Before execution:


validate:


source

destination

conflicts


Reject:


- traversal
- invalid path
- missing source
- existing conflict without policy



---

# Failure Handling


Example:


Directory creation succeeds

Move fails


Result:


PARTIAL


Include:


created directories

completed operations

error message



---

# Logging


Every execution must produce:


timestamp

plan id

operation

source

destination

result



Example:


EXECUTION


Plan:

abc123


MOVE


source:

old.mkv


destination:

Movies/movie.mkv


Result:

SUCCESS



---

# CLI


Extend:


strategy-test


Add:


--execute


Example:


DryRun(default):


strategy-test \
 --show-plan \
 "/path/file.mkv"



Execute:


strategy-test \
 --show-plan \
 --execute \
 "/path/file.mkv"



Required output:


EXECUTION RESULT


Mode:

DRY_RUN / EXECUTE


Operation:

MOVE


Source:

...


Destination:

...


Status:

...



---

# Safety Confirmation


Real execution must require explicit flag:


--execute


No implicit execution.


No config default execution.



---

# Tests


Required:


## DryRun


- move dryrun
- copy dryrun
- link dryrun


Expected:

No filesystem mutation.



## Execute


- local move
- local copy
- local link


## Failure


- missing source
- invalid destination
- permission error
- conflict exists



## Recovery


Partial execution reporting.



## Storage


Test through:


LocalStorage


SMBStorage


OpenListStorage


S3/R2Storage


where supported.



## Regression


Ensure:


RecognitionType C preserved

Naming unchanged

Classification unchanged

Plan unchanged



---

# Safety Audit


DryRun:

Storage mutations:

0



Real execution:

All mutations recorded.



---

# Documentation


Update:


docs/progress.md

docs/architecture.md



Document:


- executor lifecycle
- dry-run
- execute flag
- failure model
- logging



---

# Completion Criteria


Phase 12 accepted when:


- OrganizerExecutor implemented
- DryRun works
- Execute requires explicit flag
- Storage abstraction used
- ExecutionResult implemented
- Logs produced
- Tests pass



Do not start Phase 13.


Final report:


## Phase 12 Result

PASS / FAIL


## DryRun Examples


## Execute Examples


## Safety


## Regression


## Final Recommendation


Phase 12 accepted. Ready for Final Integration.
