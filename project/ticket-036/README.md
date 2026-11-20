# Ticket 036: Pass the push base to the governance test gate

- **ID**: ticket-036
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION covers reproducing the main CI failure,
passing the previous push SHA to the existing governance plugin, and
requesting protected publication. The PR check keeps its event-based base.

## Acceptance criteria

- [x] AC-01: Reproduce GOV-SYNC-001 on the exact merged commit in a fresh
  clone from GitHub and show the actual pytest command passes with the
  previous SHA from the push event.
- [x] AC-02: Supply the base in the workflow while keeping the managed
  pytest governance plugin enabled.

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
