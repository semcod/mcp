# Ticket 009: Documentation placement and validation

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Issue**: https://github.com/semcod/mcp/issues/9

SESSION_EXECUTION_AUTHORIZATION: user requested updating all repositories so durable reports and plans are stored correctly and continuing versioned publication. Add immutable wellmanifest/docs 0.1.0 adoption, root agent guidance, a documentation index and checker wiring in the existing verify job. Preserve runtime, historical documents and private recovery data.

Identity comes from GitHub issue #9; this repository has no managed new-project allocator or manifest. This gap is recorded, not presented as full governance adoption.

- AC-01: Reports, plans and information resolve to canonical repository paths before writing.
- AC-02: The published checker accepts the tracked pin and index; existing verify checks remain.
- AC-03: Existing tests and applicable configuration checks pass before independent exact-head Validator approval.

Validation: published docs checker passes (tracked adoption and index; no migrated profile documents); pytest, shell syntax and Compose validation pass. Existing CI checks remain. The private standard checkout uses the existing organization-provided ORG_SYNC_PAT only for the fixed reviewed repository/revision, with credential persistence disabled; no secret contents were accessed. Full managed new-project governance is absent in this legacy repository.
