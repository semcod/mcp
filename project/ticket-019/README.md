# Ticket 019: Adopt native governance managed seeds and declare mcp-docs/mcp-webui subproject ownership

- **ID**: ticket-019
- **Owner**: agent:claude
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-23

## Goal and scope

1. Land the native governance managed seeds produced by
   `goal governance adopt --source-revision 2ddba8833d342b4b4201eada2d05c8b70ed4985e`
   (`.gitattributes`, `project.bat`) after review of the prepared drift.
2. Declare the missing `application` workstream ownership for `mcp-docs/**`
   and `mcp-webui/**` in `.governance/manifest.json`, so dependency manifests
   inside those subprojects resolve to an owning workstream and ticket.

## Acceptance criteria

- [x] AC-01: managed seeds match the pinned standard revision exactly.
- [x] AC-02: `application` workstream owns `mcp-docs/**` and `mcp-webui/**`.
- [x] AC-03: governance gate passes for the landed delta and for a simulated
  cross-subproject dependency diff.

## Tracking boundary

Standard-managed payload and the adopter coordination declaration only.
