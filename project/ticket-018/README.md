# Ticket 018: Governance repair: subproject ownership, manifest lock sync, retire landed tickets

- **ID**: ticket-018
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-23

## Goal and scope

Retire the seven landed tickets (009, 011-016) whose work is verifiably
present on main, releasing stale IN_PROGRESS reservations that made the
intent, workstream and scope-overlap checks fail on unrelated diffs.

The managed-seed adoption and the `mcp-docs/**` / `mcp-webui/**` ownership
declaration moved to ticket-019 (integration); the cross-subproject
dependency-manifest ownership is ticket-020 (application).

## Acceptance criteria

- [x] AC-01: tickets 009, 011, 012, 013, 014, 015, 016 marked DONE with
  landing evidence recorded in each README.
- [x] AC-02: governance gate passes for the landed delta.

Repair the repository governance debt that blocks every cross-subproject
change (including Dependabot dependency PRs):

1. `.governance/manifest.json`: declare the missing `mcp-docs/**` and
   `mcp-webui/**` ownership in the `application` workstream, so requirement
   manifests inside those subprojects have an owner.
2. Retire the seven landed tickets (009, 011-016) whose work is verifiably
   present on main, removing stale IN_PROGRESS reservations that make the
   intent, workstream and scope-overlap checks fail on unrelated diffs.

## Acceptance criteria

- [x] AC-01: `application` workstream owns `mcp-docs/**` and `mcp-webui/**`.
- [x] AC-02: tickets 009, 011, 012, 013, 014, 015, 016 marked DONE with
  landing evidence recorded in each README.
- [x] AC-03: governance gate passes for a simulated dependency diff
  (`mcp-docs/requirements.txt`, `mcp-gateway/requirements.txt`,
  `mcp-webui/requirements.txt`) once the follow-up maintenance ticket owns it.

## Acceptance criteria

- [ ] AC-01: Scope is approved by a human owner.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
