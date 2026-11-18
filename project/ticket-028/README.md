# Ticket 028: Align mcp package versions with their declared releases

- **ID**: ticket-028
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-18

## Goal and scope

Fixes semcod/mcp#56. Static `__version__` values disagreed with the declared releases, so the
new-project 0.20.162 gate reports GOV-VERSION-001 and blocks the fleet standard adoption:
`gh2mcp` declared 0.0.7 against its `pyproject.toml` 0.1.4, and `semcod_mcp` declared 0.1.0
against `VERSION` 0.1.7. Align them and add a parity regression test. `env2mcp` has the same
defect but no owning workstream; it follows in separate governance and application tickets.

## Acceptance criteria

- [ ] AC-01: gh2mcp `__version__` = 0.1.4, semcod_mcp `__version__` = 0.1.7; `tests/test_version_parity.py` passes.
- [ ] AC-02: `project/governance-check.sh` passes.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
