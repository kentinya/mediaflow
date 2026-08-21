# Phase 13.2 — ResourceLibrary Driven Organization Pipeline


## Goal

Change the workflow from manual file input to configuration-driven media organization.


Current behavior:

User provides:

file path

↓

strategy-test

↓

analyze one file


Target behavior:

Configuration defines:

ResourceLibraries

and

MediaLibraries


Application automatically:

scan ResourceLibraries

↓

process media

↓

classify

↓

resolve MediaLibrary

↓

generate OrganizePlan

↓

execute or dry-run



---

# Core Requirement


The user should NOT need to specify individual media paths.

The system should discover media from configured ResourceLibraries.


Example:


config:

resourceLibrary:

source


storage:

HDD_2


path:

Media



Command:


mediaflow preview



The system should automatically scan:


HDD_2:/Media


and generate plans.



---

# Pipeline


Implement:


ResourceLibrary

        ↓

Scanner

        ↓

Media Processing Pipeline

        ↓

Recognition

        ↓

Metadata

        ↓

Naming

        ↓

Classification

        ↓

MediaLibrary Resolver

        ↓

OrganizePlan

        ↓

OrganizerExecutor



---

# ResourceLibrary Scanner


Add application service:


ResourceLibraryScanner


Responsibilities:


- load enabled resourceLibraries
- obtain Storage from StorageFactory
- recursively scan files
- filter supported extensions
- create media processing tasks


Must work with:

LocalStorage

OpenListStorage

SMBStorage

S3/R2Storage



Do not assume local filesystem paths.



---

# MediaLibrary Resolver


Implement:


MediaLibraryResolver


Input:


ClassificationResult


Example:


{
 mediaLibraryId:"Media",
 path:["Anime"]
}



Resolve:


MediaLibrary config

+

Storage config



Output:


destination storage

destination root

relative path



Example:


MediaLibrary:

storageId:

HDD_2


rootPath:

Downloads/Media



Classification:

Anime



Final:


HDD_2:

Downloads/Media/Movies/Anime/xxx



---

# OrganizePlan Update


Ensure plan contains:


source:

{
 storageId,
 path
}


destination:

{
 storageId,
 path
}



Do not store only absolute local paths.



Example:


source:

{
 storageId:"HDD_2",
 path:"Media/电影/test.mkv"
}



destination:

{
 storageId:"HDD_2",
 path:"Downloads/Media/Movies/Anime/test.mkv"
}



---

# CLI


Change final workflow.



Add:


mediaflow scan


Example:


mediaflow scan



Output:


ResourceLibrary:

source


Storage:

HDD_2


Found:

1000 files



---


Add:


mediaflow preview


No path required.



Output:


Summary:


Total:

1000


Matched:

950


Unmatched:

50



Plans:


source -> destination



---


Add:


mediaflow organize --execute



Execution requires explicit flag.



Default:

dry-run



---

# Storage Support


The same pipeline must support:


Local -> Local

Local -> OpenList

OpenList -> Local

OpenList -> OpenList


Do not hardcode storage type.



---

# Safety


Maintain:


- preview has zero mutation
- execute requires --execute
- no overwrite
- conflicts reported
- failed files do not stop batch



---

# Configuration


Use existing:


resourceLibraries

mediaLibraries

classificationPolicies

organizePolicies



Do not introduce manual source/destination config.



---

# Tests


Add:


ResourceLibrary scan test


- local resource scan

- mock OpenList scan


MediaLibrary resolver:


- movie classification resolves target

- TV classification resolves target



Pipeline:


- one movie end-to-end


- one TV episode end-to-end



Storage combinations:


- Local -> Local

- Local -> OpenList mock

- OpenList mock -> Local



Safety:


- preview mutation = 0

- execute required



---

# Regression


Keep:


Parser

Recognition

Metadata

Naming

Classification

Planner

Executor


unchanged.



---

# Documentation


Update:


README.md

docs/configuration.md

docs/architecture.md

docs/progress.md



Document:


- ResourceLibrary concept

- MediaLibrary concept

- automatic workflow

- preview

- organize --execute



Final response:


## Phase 13.2 Result

PASS / FAIL


## Resource Scan


## Pipeline Example


## Storage Flow


## Safety


## Regression


## Final Recommendation