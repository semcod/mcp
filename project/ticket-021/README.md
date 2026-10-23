# Ticket 021: Dependency maintenance: llm-agent and mcp-skills requirement manifests

- **ID**: ticket-021
- **Owner**: agent:claude
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-23

## Goal and scope

Own the automated dependency updates for `llm-agent/requirements.txt` and
`mcp-skills/requirements.txt` (requires the `llm-agent/**` and
`mcp-skills/**` application ownership declared by ticket-019).

## Acceptance criteria

- [ ] AC-01: the mcp requirement bump resolves to this ticket and passes
  the governance gate on a current base.

## Tracking boundary

Requirement manifests only; no runtime code changes.
