# Ticket 035: Read the adopted standard when checking managed documentation

- **ID**: ticket-035
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION covers resolving the verification
regression blocking PRs #60 and #61 and requesting independent publication.
The documentation validator will use the published governance revision of
the checkout under test to verify managed documents against upstream bytes.

## Acceptance criteria

- [x] AC-01: Reproduce the documentation failure on main and both dependent
  PR heads. Each passes the same documentation gate with its adopted revision.
- [x] AC-02: Reject a mutable revision in the adoption lock.
- [x] AC-03: Pass the repository unit tests and OpenWebUI configuration checks.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 48/100 |
| Complexity | M |
| Estimated effort | 44 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
