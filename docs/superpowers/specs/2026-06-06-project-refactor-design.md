# Project Refactor Design

## Goal

Refactor the photo-monitor project with a phased, low-risk approach that improves code health, security boundaries, testability, and maintainability without turning the work into a single large rewrite.

## Chosen Approach

Use phased comprehensive governance.

1. Stop quality gate failures first.
2. Harden backend security boundaries.
3. Split frontend responsibilities into focused modules.
4. Clean stale files and document the operational workflow.

This approach keeps each phase small enough to verify and commit independently while still addressing the full project health problem.

## User Constraints

- Automatically create git commits after meaningful phases.
- Avoid excessive local manual testing.
- Run only focused local quality gates needed to confirm each phase.
- Generate five server-side test scenarios as part of the refactor.
- Preserve user changes already present in the working tree.

## Current Problems

### Quality Gate Failure

The frontend linter fails because `EmployeeManagerPage.jsx` calls `syncDefaultStructurePermission` after the helper was removed from staged changes. This is a hard pre-refactor blocker because it prevents lint from serving as a reliable gate.

### Backend Security Boundary Gaps

The backend stores passwords in plaintext, compares them directly, returns sensitive passwords to admin endpoints, and uses a hard-coded JWT secret. Photo files are exposed through a static mount, so list endpoints are permission-protected while resource files can still be reached directly if the path is known.

### Frontend Responsibility Concentration

`src/App.jsx` owns routing, auth recovery, permissions, WebSocket setup, photo feed state, employee management wiring, office upload pages, structure display, and dashboard rendering. The file is too broad and duplicates office upload workflows for company files, study articles, and ledgers.

### Stale Code

The root-level `photo-monitor/pages/home.jsx` and `photo-monitor/hooks/*` files appear to belong to an older app shape and are not imported by the current `src/main.jsx` entry. They create confusion and include outdated WebSocket behavior.

### Test and Tooling Friction

Backend tests pass only when `PYTHONPATH=.` is set manually. The repository does not encode this in test configuration, so local and CI execution can drift.

## Target Architecture

### Backend

- Move JWT secret and related auth settings to environment-driven configuration with safe development defaults.
- Add password hashing for new and changed passwords.
- Support legacy plaintext password verification long enough to migrate existing users when they authenticate or change password.
- Stop returning raw passwords from public or admin list/detail payloads.
- Add explicit admin password reset behavior instead of exposing stored passwords for editing.
- Replace raw `/static` photo exposure with authenticated file-serving routes for photos and thumbnails.
- Centralize repeated token extraction and matrix permission checks so upload, photo, WebSocket, and dependency code share the same behavior.
- Add `pytest.ini` so `pytest -q` runs from `photo-backend` without manual path setup.

### Frontend

- Keep `src/App.jsx` as the top-level app shell and page router only.
- Move dashboard UI into `src/pages/DashboardPage.jsx`.
- Move monitor/photo feed UI into `src/pages/MonitorPage.jsx`.
- Move structure UI into `src/pages/StructurePage.jsx`.
- Move repeated office upload UI into `src/pages/OfficeUploadPage.jsx`, configured for company files, study articles, and ledgers.
- Move auth/session state into `src/hooks/useAuth.js`.
- Move photo feed, pagination, dedupe, and WebSocket refresh behavior into `src/hooks/usePhotoFeed.js`.
- Move office upload listing/upload/delete behavior into `src/hooks/useOfficeUploads.js`.
- Move permission parsing and checks into `src/permissions.js`.
- Keep API functions in `src/api.js`, but centralize authorized view/download URL generation.
- Remove stale root-level `pages` and `hooks` after their behavior is either replaced or confirmed unused.

## Server-Side Test Scenarios

The refactor will include five backend test scenarios:

1. Password hashes are not exposed in admin employee list or detail responses.
2. Legacy plaintext password users can still log in and are migrated to hashed storage.
3. JWT tokens are signed and verified using the configured environment secret.
4. Photo resource access requires a valid user with matching photo read permission.
5. Upload view/download/delete access respects matrix department and action permissions.

## Verification Strategy

Use focused verification instead of broad manual testing.

- After quality-gate changes: run `npm run lint`, `npm run build`, and `pytest -q`.
- After backend security changes: run backend auth/resource/upload tests.
- After frontend decomposition: run `npm run lint` and `npm run build`.
- After cleanup: run final `npm run lint`, `npm run build`, and `pytest -q`.

Manual browser testing is not required unless automated checks or code review reveal UI uncertainty.

## Commit Strategy

Create automatic commits after coherent phases:

1. Fix quality gates and backend test configuration.
2. Harden backend auth and resource access.
3. Split frontend app responsibilities.
4. Clean stale files and documentation.
5. Add or update server-side test scenarios.

Commits must not revert unrelated user changes. If a file has existing user changes, integrate with them carefully.

## Out of Scope

- Full UI redesign.
- Database migration away from JSON storage.
- New deployment platform.
- Full end-to-end browser automation suite.
- Replacing the permission matrix model.

## Risks

- Password hashing must preserve existing login behavior during migration.
- Removing `/static` can break existing image URLs unless frontend API paths are updated together.
- Splitting `App.jsx` can accidentally change page state lifetimes, so extraction should be behavior-preserving.
- Existing staged changes in `EmployeeManagerPage.jsx` must be respected.
