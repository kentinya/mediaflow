# Phase 19.2 — API Credential Lifecycle and HTTP Deployment Guardrails

## Goal

Make environment-owned API bearer credentials easier to generate, inspect, and rotate safely, and
prevent accidental public exposure of the development HTTP server. Preserve the existing Principal,
RBAC, audit, one-time execute authorization, and operator UI behavior.

## 1. Credential operations

- Add `mediaflow api token generate [--bytes N]` using the operating-system cryptographic random
  source. Default to at least 256 bits; enforce a bounded safe range.
- Print the new token exactly once to stdout. Do not load configuration, write a file/database,
  mutate environment state, log the token, or construct Storage/Provider/application services.
- Add `mediaflow api credentials check` to list configured enabled/disabled principals, roles,
  environment-variable names, and SET/UNSET state without displaying values, lengths, hashes, or
  other secret-derived material.
- Credential check must perform zero Storage/provider/database/network calls and return nonzero when
  an enabled credential is missing.
- Document zero-downtime rotation using two separately named principals/environment variables; do
  not add a secret store or persist bearer credentials.

## 2. HTTP deployment guardrails

- Continue defaulting `api serve` to loopback.
- Reject a non-loopback bind unless the operator supplies an explicit
  `--allow-insecure-remote-http` acknowledgement.
- Treat IPv4/IPv6 loopback names and addresses deterministically; reject malformed bind hosts before
  constructing repositories or starting the server.
- Clearly warn when the explicit insecure remote acknowledgement is used. Do not claim that the
  standard-library WSGI server supplies TLS or production hardening.
- Add no-store, nosniff, referrer, and frame-denial headers to JSON API responses while preserving
  the stricter UI CSP. Add a standards-compatible Bearer challenge on 401 responses.

## 3. Authentication robustness

- Bound and validate the presented Authorization header before comparison to avoid accepting
  malformed schemes or unbounded credentials.
- Preserve comparison against every configured credential and existing constant-time comparison.
- Never include presented/configured tokens in errors, audit, response bodies, CLI status, or docs.
- Do not weaken RBAC or the independent one-time authorization required for remote real execution.

## Required tests

- Token generation entropy source, default/custom bounds, single stdout disclosure, and no config or
  adapter access.
- Credential status for enabled/disabled and SET/UNSET principals, exit status, redaction, legacy
  compatibility, and zero database/Storage/provider/network access.
- Loopback IPv4/IPv6/localhost accepted; wildcard/LAN/public hosts rejected without explicit flag;
  invalid hosts rejected; explicit acknowledgement warns.
- API JSON security headers and Bearer challenge on 401; UI headers remain unchanged.
- Missing, wrong scheme, empty, whitespace-bearing, oversized, and valid credentials.
- Existing RBAC, audit, remote execution double gate, operator UI, and review workflows regress.
- Full suite plus formatter, lint, compile, dependency/build/configuration and FFprobe audits.

## Documentation

Update README, requirements status, configuration, architecture, progress, and roadmap with token
generation, credential checks, rotation, loopback/TLS boundary, and reverse-proxy guidance.

## Out of scope

TLS termination, reverse-proxy implementation, database users, password login, sessions/cookies,
OIDC/OAuth, automatic secret rotation, secret stores, certificate management, trusting forwarded
headers, policy editing, task controls, and any expansion of remote execution.

## Final report

## Phase 19.2 Result

PASS / FAIL

## Credential Operations

## HTTP Guardrails

## Authentication and Security

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
