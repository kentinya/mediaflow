# Phase 10 — ClassificationPolicy + ClassificationEngine

## Goal

Implement media classification.

Classification decides WHERE media belongs.

It does NOT execute filesystem operations.

Pipeline:

Recognition
    +
MediaIdentity
    +
ClassificationPolicy
        |
        v
ClassificationEngine
        |
        v
ClassificationResult


---

# Scope

Implement:

- ClassificationPolicy
- ClassificationRule
- ClassificationContext
- ClassificationEngine
- ClassificationResult
- rule matching
- priority handling
- category resolution
- dry-run output


---

# Strict Boundary

Classification MUST NOT:

- create directory
- rename file
- move file
- copy file
- delete file
- call Organizer
- call Storage write API


Classification only returns:

"where this media should go"


---

# Architecture

Responsibilities:

Recognition:

What is this?

Example:

Movie / TV / C


Metadata:

What media is this?

Example:

Title:
千与千寻

Genre:
Animation


Naming:

How should it be named?

Example:

千与千寻 (2001)


Classification:

Where should it belong?

Example:

Movies/Animation


Organizer:

How should files be changed?


Do not mix responsibilities.


---

# ClassificationPolicy


Implement:

ClassificationPolicy


Suggested fields:


id

name

description

enabled

priority

mediaTypeRules

genreRules

countryRules

languageRules

yearRules

keywordRules

defaultCategory


Adjust according to existing architecture.


---

# ClassificationRule


Implement explicit rules.


Example:


Rule:

Animation Movies


conditions:

mediaType = movie

genre contains Animation


result:

category = Animation


Priority:

100


---

# ClassificationContext


Input:


RecognitionType

MediaIdentity

Metadata

ParseResult

NamingResult(optional)


Must not require Storage.


---

# ClassificationResult


Return:


policyId

matchedRule

library

category

subcategory

relativeCategoryPath

confidence

warnings


Example:


ClassificationResult:


library:

Movies


category:

Animation


path:

Animation


---

# Rule Matching


Rules must support:


## Media Type


movie

tv

anime


Example:


movie -> Movies


---

## Genre


Example:


TMDB genre:

Animation


match:


Animation


---

## Country


Example:


Japan


---

## Language


Example:


ja


---

## Year


Example:


year >= 2020


---

## Keywords


Example:


title contains:

Marvel


---

# Priority


Rules must be deterministic.


Example:


Rule A:

Animation

priority 100


Rule B:

Japanese Animation

priority 200


Result:

Japanese Animation


Higher priority wins.


---

# No Hidden Defaults


Do not:

unknown -> Movies


Do not:

failed classification -> first category


If no rule matches:


ClassificationResult:

status = unclassified


---

# RecognitionType C Regression


Existing:


C

→ Metadata C

→ Naming A

→ Classification A

→ Organize A


Important:


RecognitionType must remain C.


ClassificationPolicy A can be reused.


Do not convert:

C -> A


---

# Example Cases


## Movie


Input:


title:

千与千寻


type:

Movie


genre:

Animation


Expected:


library:

Movies


category:

Animation



---

## Normal Movie


Input:

The Matrix


genre:

Action


Expected:


Movies/Action



---

## TV


Input:

The Last of Us


type:

TV


Expected:


TV Shows



---

## Anime


Input:


Your Name


country:

Japan


genre:

Animation


Expected:


Anime



---

# Classification Preview


Extend strategy-test.


Example:


CLASSIFICATION PREVIEW


RecognitionType:

A


ClassificationPolicy:

A


Matched Rule:

animation-movie


Library:

Movies


Category:

Animation


Path:

Animation



Storage mutations:

0


---

# Safety


After:


Parser

Recognition

Metadata

Naming

Classification


Verify:


Storage writes:

0


CreateDirectory:

0


Move:

0


Copy:

0


Delete:

0


HardLink:

0


SoftLink:

0


Organizer execution:

0



---

# Tests


Add tests:


1.

Movie animation classification


2.

Movie action classification


3.

TV classification


4.

Anime classification


5.

Priority rules


6.

No matching rule


7.

Disabled policy


8.

C uses Classification A


9.

Classification does not access Storage


10.

Deterministic result



---

# Strategy CLI


Required command:


strategy-test \
 --live-metadata \
 --show-naming \
 --show-classification \
 "/path/file.mkv"



Output:


NAMING PREVIEW


...


CLASSIFICATION PREVIEW


Library:

Movies


Category:

Animation



---

# Regression


Run:


Parser

Recognition

Metadata

CandidateMatcher

Naming

Classification

Strategy CLI

Scanner/FileIndex

Storage

DryRun



---

# Documentation


Update:


docs/progress.md


docs/architecture.md



Document:


Classification responsibility

ClassificationPolicy

ClassificationEngine

Rule priority

No storage mutation boundary



---

# Completion Criteria


Phase 10 accepted when:


- ClassificationPolicy implemented
- ClassificationEngine implemented
- Rules deterministic
- Priority works
- Movie classification works
- TV classification works
- Anime classification works
- C remains C
- No filesystem mutation
- Strategy CLI preview works
- Tests pass


Do not start Phase 11.

Final output:


## Phase 10 Result

PASS / FAIL


## Classification Examples


## Safety


## Regression


## Final Recommendation


Phase 10 accepted. Ready for OrganizePlan.