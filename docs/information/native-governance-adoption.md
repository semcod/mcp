---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "native-governance-adoption",
  "kind": "information",
  "version": 1,
  "title": "MCP native governance adoption and immutable Compose boundary",
  "status": "draft",
  "owner": "semcod/mcp",
  "scope": "repository",
  "created": "2026-10-07",
  "updated": "2026-10-07",
  "review_after": "2026-11-07",
  "source_revision": "e1d2b0c48b825e18bc40f5ecabd5b299e1c7f2b0",
  "affected_repositories": [
    "semcod/mcp"
  ],
  "evidence": [
    "https://github.com/wellmanifest/new-project/releases/tag/v0.20.89",
    "https://github.com/wellmanifest/new-project/tree/2ddba8833d342b4b4201eada2d05c8b70ed4985e",
    "https://github.com/semcod/mcp/pull/24",
    "https://github.com/wellmanifest/docs/pull/15",
    "https://github.com/semcod/mcp/actions/runs/37543066609",
    "receipt:mcp013-accepted-handoff/sha256/29a74c5728d949048d29d8fabe409157ed9e66ff64076fdedb8ce6d98cb18d00"
  ]
}
---

# MCP native governance adoption

<!-- docs:section purpose -->
## Purpose

Complete the handed governance scope using the published native package while retaining MCP product validation and the authenticated OpenWebUI boundary.

<!-- docs:section scope -->
## Scope

Ticket-014 adopts new-project 0.20.89 from immutable revision `2ddba8833d342b4b4201eada2d05c8b70ed4985e` through Goal. Work takes place in its canonical relative linked checkout under an authoritative fenced integration lease. Target-owned integration paths cover the atomic package, Python packaging and Compose configuration; managed source files retain their published digests.

<!-- docs:section evidence -->
## Evidence

The original fourteen handed files were preserved byte-for-byte in private recovery storage. Their raw operational log and host connection configuration remain private. The ticket-013 token fallback is already present in merged PR #24; the existing `verify` run on base `e1d2b0c48b825e18bc40f5ecabd5b299e1c7f2b0` succeeded. Historical merge facts do not establish new-candidate approval.

<!-- docs:section content -->
## Installed contract and product boundary

The adoption installs native scope, allocation, Worktrees v5, continuity, host hooks and required-check enforcement. Python packaging declares the immutable standard and loads the managed governance pytest plugin. The existing `verify` workflow retains documentation validation, unit tests and Compose security checks. Its Docs source moves from 0.1.0 to the minimum compatible 0.5.0 revision `6f475fb223e7a259d514b5483fb0d62f0e80a46e`, independently merged by the Validator App in Docs PR #15. The policy hash and workflow pin agree. The verify job derives manual digests from a separate checkout of the immutable governance source, rather than trusting candidate-authored document metadata or inventories. Provider checkouts use the existing ignored `.subactor/cache/` boundary. The checker verifies immutable managed manuals without treating them as duplicate target-owned documents; failed metadata or digest verification remains an error. This prerequisite raises the final bounded delivery to class L with eleven implementation files, within the existing policy cap of fifteen. Required checks include `verify`, `governance / remote lifecycle` and `governance / enforce`.

Redis is pinned to its multi-platform index `sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499`; registry inspection identifies the amd64 image as 7.4.11-alpine. OpenWebUI retains its existing 0.11.0 digest as a literal image reference. `OPENWEBUI_IMAGE` cannot substitute an arbitrary mutable image. Compose supplies no shared development API key; operators must configure `WEBUI_API_KEY` for the authenticated gateway. Optional root seed aliases and the optional Git attributes seed are omitted. A regression renders Compose with untrusted override values and checks the authenticated, signup-disabled, loopback-bound frontend and gateway plus the read-only bearer secret mount. Both cases failed against the original configuration. Docker Compose is a required test dependency: an absent executable fails the security regression instead of bypassing it.

<!-- docs:section limitations -->
## Limitations

Installing files and passing local tests grant neither merge approval nor runtime deployment. No containers are deployed by this ticket. Private terminal receipts are clone-local activity facts, not independent approval and not portable CI evidence. A protected Validator profile must retain every declared check; missing profile coverage is a publication prerequisite, not grounds to waive checks. Original host connection settings are preserved without claiming deployment.

<!-- docs:section next_actions -->
## Verification and publication

Local validation passed the native gate with zero findings, all twelve MCP tests, the immutable Docs checker with three verified managed copies, and the actual retained Compose security script. A deliberately mismatched copy digest was rejected. These results cover the staged candidate and do not constitute review or merge approval. The exact three-check MCP profile was independently approved and merged in validator-agent PR #623. The first MCP review requested changes because the regression allowed a missing Docker executable to skip verification; the corrected test requires the executable. Publish only through the protected independent Validator with exact repository, ticket, PR, head and base bindings. Record actual approval and merge separately from local verification.
