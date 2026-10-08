# ticket-014: Complete MCP native governance adoption

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Owner**: agent:codex

## Authorization and preparation boundary

SESSION_EXECUTION_AUTHORIZATION: preserve and complete the handed MCP ticket-013 scope. Native allocator reserved ticket-014. The preparatory coordination lease was cancelled and released. The real controller granted a final integration lease bound to the complete delivery intent before native package and product changes. The missing checkout was reconstructed from the allocator receipt and exact preserved intent; no new identity, historical approval or completion is inferred.

## Acceptance criteria

- [x] AC-01: Adopt the immutable published standard in the canonical worktree.
- [x] AC-02: Preserve product validation, pin Compose images and verify the OpenWebUI security boundary.
- [ ] AC-03: Require exact-head independent approval before protected merge.

Canonical result: [native governance adoption](../../docs/information/native-governance-adoption.md).

Local validation: native gate passes with zero findings; all 12 MCP tests pass, including two failing-before/fixed-after mutable-image regressions. Protected profile migration is independently merged in Validator PR #623; exact-head independent MCP publication remains pending.

Discovered prerequisite: Docs 0.1.0 rejects native managed manuals. The accepted final scope adds the Docs adoption and retained verify workflow pins, using independently merged Docs 0.5.0; class L stays within the unchanged policy cap.

Validation receipt: `receipt:mcp014-complete-local-checks-oct7`. Native governance and documentation pass with zero findings; all twelve tests and the retained Compose security script pass. Deliberately mismatched managed-copy digest is rejected. Protected Validator registry coverage is independently merged in PR #623. Independent exact-head MCP merge remains pending.

Independent review remediation: the initial review rejected the optional Docker test skip. The security regression now requires Docker Compose and fails when its dependency is absent. The existing accepted test and documentation scope covers this correction; required checks and protected policy remain unchanged.
