# ticket-013: Fix CI verify workflow token fallback for public standard and Dependabot PRs

- **Status**: IN_PROGRESS
- **Workflow state**: EDIT

SESSION_EXECUTION_AUTHORIZATION: On 2026-09-25 user requested continuing overdue tasks and PRs across repositories. In `semcod/mcp`, Dependabot PRs #21, #22, #23 fail because `secrets.ORG_SYNC_PAT` is not provided to PRs from outside or Dependabot, causing checkout of public standard repo `wellmanifest/docs` to fail with "Input required and not supplied: token".

AC-01: `.github/workflows/verify.yml` uses `${{ secrets.ORG_SYNC_PAT || github.token }}` for checking out `wellmanifest/docs`.
AC-02: Local verification passes.
AC-03: No changes to package runtime logic or dependencies.
