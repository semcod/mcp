# Ticket 030: Own env2mcp under application and align its version

- **ID**: ticket-030
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-19

## Goal and scope

Fixes semcod/mcp#56 (completes #57). `env2mcp/env2mcp/__init__.py` declared 0.0.7 against its
`pyproject.toml` 0.1.4, so the new-project 0.20.162 gate reports GOV-VERSION-001. `env2mcp/**` had no
owning workstream, which is why #57 could not fix it. Assign it to `application` like `gh2mcp/**`,
align the version and extend the parity test to cover it.

## Acceptance criteria

- [ ] AC-01: `env2mcp/**` is owned by `application`; env2mcp `__version__` = 0.1.4; `tests/test_version_parity.py` passes.
- [ ] AC-02: `project/governance-check.sh` passes.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
