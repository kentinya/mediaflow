# Phase 11 — OrganizePlan + Conflict Detection + DryRun

## Goal

Implement the planning layer before actual file operations.

OrganizePlan decides:

WHAT operation should happen.

It does NOT execute operations.

Pipeline:

ClassificationResult
+
NamingResult
+
MediaLibrary
+
Storage context

        ↓

OrganizePlanner

        ↓

OrganizePlan


---

# Strict Boundary

Phase 11 MUST NOT:

- move files
- rename files
- create directories
- delete files
- copy files
- call Storage write APIs
- execute Organizer


Only generate plans.


---

# OrganizePlan


Implement:

OrganizePlan


Suggested fields:


id

operation

source

destination

mediaIdentity

namingResult

classificationResult

warnings

conflicts

status


Operations:


MOVE

COPY

LINK

NOOP

SKIP


---

# OrganizePlanner


Implement:

OrganizePlanner


Input:


SourceFile

MediaIdentity

NamingResult

ClassificationResult

MediaLibrary


Output:


OrganizePlan



---

# Destination Calculation


Combine:


MediaLibrary root

+

Classification category path

+

Naming result


Example:


MediaLibrary:

Movies


Classification:

Animation


Naming:

千与千寻 (2001)


Result:


Movies/

Animation/

千与千寻 (2001)/

千与千寻 (2001).mkv



---

# Relative Path Safety


Planner must reject:


absolute paths

..

path traversal

invalid components


No unsafe destination should be generated.


---

# Conflict Detection


Implement detection only.


Do NOT resolve automatically.


Possible conflicts:


## Destination Exists


Example:


source:

A/movie.mkv


destination:

Movies/movie.mkv


Result:


Conflict:

DESTINATION_EXISTS



---

## Same Source Destination


Result:


NOOP


---

## Duplicate Media


Example:


same provider ID

same destination


Result:


DUPLICATE_MEDIA


---

## Different Files Same Target


Result:


TARGET_COLLISION



---

# Conflict Model


Implement:


Conflict


fields:


type

source

destination

details



Types:


DESTINATION_EXISTS

TARGET_COLLISION

DUPLICATE_MEDIA

INVALID_DESTINATION

UNKNOWN


---

# DryRun


Extend existing DryRun output.


Example:


ORGANIZE PLAN


Operation:

MOVE


Source:

old/path/file.mkv


Destination:

Movies/Animation/movie.mkv



Conflict:

none


Execution:

NOT EXECUTED


---

# Strategy CLI


Add:


--show-plan



Example:


strategy-test \
 --live-metadata \
 --show-naming \
 --show-classification \
 --show-plan \
 "/path/file.mkv"



Output:


NAMING

...


CLASSIFICATION

...


ORGANIZE PLAN


Operation:

MOVE


Destination:

...


Storage mutation:

0



---

# Safety


After complete pipeline:


Parser

Recognition

Metadata

Naming

Classification

Planning



Verify:


Storage writes = 0

Move = 0

Copy = 0

Delete = 0

CreateDirectory = 0



---

# Tests


Required:


1.

Movie plan generation


2.

TV plan generation


3.

Classification path included


4.

Naming path included


5.

Same source destination -> NOOP


6.

Existing destination conflict


7.

Collision detection


8.

Duplicate media detection


9.

Invalid destination rejection


10.

C remains C


11.

Zero mutation


---

# Regression


Run:


Parser

Recognition

Metadata

CandidateMatcher

Naming

Classification

Planner

Strategy CLI

Scanner/FileIndex

Storage

DryRun



---

# Completion


Phase 11 accepted when:


- OrganizePlanner implemented
- OrganizePlan implemented
- Conflict detection implemented
- DryRun preview works
- No filesystem mutation
- Tests pass


Do not start Phase 12.


Final report:


## Phase 11 Result

PASS / FAIL


## Plan Examples


## Conflicts


## Safety


## Regression


## Final Recommendation


Phase 11 accepted. Ready for OrganizerExecutor.
