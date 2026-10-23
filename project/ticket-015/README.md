# Ticket 015: Remediate PERF-AUDIT findings and adopt Wellmanifest standards

- **ID**: ticket-015
- **Owner**: tom
- **Status**: DONE
- **Workflow state**: EDIT
- **Created**: 2026-10-17

## Goal and scope

Remediate all 16 `PERF-AUDIT-*` static performance and Compose healthcheck findings across `semcod/mcp` and complete `wellmanifest/wellman` baseline standard-adoption bindings in `.governance/standard-adoption.json`.

- **SESSION_EXECUTION_AUTHORIZATION**: Explicit user request in active session to fix all `PERF-AUDIT-*` findings and adopt `wellmanifest/wellman` standards across `semcod` repositories.

## Acceptance criteria

- [x] AC-01: `audit_repository` from `wellmanifest/performance` reports `0` findings across `semcod/mcp`.
- [x] AC-02: `.governance/standard-adoption.json` satisfies `python3 .governance/standard_pack_check.py --root .` with `findings=0`.
- [x] AC-03: Existing test suites and `./project/governance-check.sh` pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

## Completion

Retired 2026-10-23 with landing evidence: docker-compose.yml present; PERF-AUDIT remediation acceptance checked in ticket README. Governance reservation released; the delivered work is verifiably present on main.
