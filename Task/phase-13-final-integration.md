# Phase 13 — Final Integration & Production Readiness

## Goal

Integrate all completed modules into a production-ready media organizer.

Current completed pipeline:

Scanner

↓

Parser

↓

Recognition

↓

Metadata Provider

↓

Candidate Matcher

↓

MediaIdentity

↓

Naming

↓

Classification

↓

OrganizePlan

↓

OrganizerExecutor


Phase 13 goal:

Provide complete workflow execution,
configuration management,
batch processing,
logging,
and final validation.


---

# Scope

Implement:


- Application Orchestrator
- Batch Organizer
- Configuration Loader
- Task Execution Record
- Operation History
- Final CLI workflow
- Production validation


---

# Architecture


Final pipeline:


Media Source

↓

Scanner

↓

Media Processing Pipeline

↓

OrganizePlan

↓

DryRun Preview

↓

Explicit Execute

↓

Execution Result

↓

History Record



---

# 1. Application Orchestrator


Implement:


MediaOrganizerService


Responsibilities:


- coordinate all components
- process single media
- process multiple media
- collect results


Must NOT contain:

- parser logic
- metadata logic
- classification rules
- storage implementation


Only orchestration.



---

# 2. Batch Processing


Support directory workflow.


Example:


mediaflow organize:

/mnt/HDD_2/Media/电影



Process:


scan files

↓

parse each file

↓

identify

↓

plan

↓

preview or execute



Support:


- recursive scan
- extension filtering
- ignore rules
- max workers(optional)



---

# 3. Configuration System


Move runtime configuration into files.


Support:


config.yaml


Example:


```yaml
storage:

  source:
    type: local
    path: /mnt/HDD_2/Media


libraries:

  movies:

    destination:
      type: local
      path: /mnt/HDD_2/Movies


    naming:
      policy: A


    classification:
      policy: A


metadata:

  provider:
    tmdb:

      language: zh-CN

      region: CN


execution:

  default_mode:
    dry_run: true