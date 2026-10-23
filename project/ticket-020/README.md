# Ticket 020: Cross-subproject dependency maintenance (mcp-docs, mcp-gateway, mcp-webui)

- **ID**: ticket-020
- **Owner**: agent:claude
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-23

## Goal and scope

Own the standing dependency-manifest maintenance across the three subproject
requirement files (`mcp-docs/requirements.txt`, `mcp-gateway/requirements.txt`,
`mcp-webui/requirements.txt`) so automated dependency PRs resolve to exactly
one active application ticket. Requires the `mcp-docs/**` and `mcp-webui/**`
workstream ownership declared by ticket-019.

## Acceptance criteria

- [x] AC-01: the three requirement manifests resolve to this ticket.
- [ ] AC-02: automated dependency PRs pass the governance gate on a current base.

## Tracking boundary

Requirement manifests only; no runtime code changes.
