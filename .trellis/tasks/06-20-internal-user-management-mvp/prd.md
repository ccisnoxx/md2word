# Internal User Management MVP

## Goal

Add a minimal internal user management capability so administrators can create users, disable users, reset passwords, and operators can change their own passwords without editing deployment configuration files.

The current authentication system can log in configured internal users and return current-user claims, but the user source is read from `AUTH_INTERNAL_USERS_FILE` / `AUTH_INTERNAL_USERS_JSON` at startup. That means day-to-day operations cannot add an operator, rotate a password, disable a leaving user, or recover an account from the application itself.

This task should turn internal users into a managed product capability while keeping the scope deliberately small. It is not a full IAM, SSO, organization, or custom permission system.

## Product Positioning

This system is used by Chinese-speaking operations staff and administrators.

Design priorities:

- safe account lifecycle for a small internal team
- admin-only user management
- user self-service password change
- auditability for account operations
- no exposed passwords or password hashes
- no broad IAM redesign
- Chinese-first visible frontend copy
- minimal operational migration risk from the existing configured-user source

## Current Context

- `app/api/v1/routers/auth.py` exposes only:
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
- `app/services/auth/service.py` currently:
  - loads users from `AUTH_INTERNAL_USERS_FILE` or `AUTH_INTERNAL_USERS_JSON`
  - hashes passwords with PBKDF2-SHA256
  - issues and validates HS256 JWT tokens
  - rejects disabled users only because configured users carry `status`
- `app/services/auth/models.py` currently defines `InternalUser` with:
  - `id`
  - `username`
  - `password_hash`
  - `role`: `admin` or `operator`
  - `tenant_id`
  - `company_id`
  - `status`: `active` or `disabled`
  - `display_name`
- `app/services/auth/permissions.py` derives permissions from the role.
- `app/api/dependencies.py` already has `require_current_user` and `require_admin_user`.
- `AuditService` already records successful user-significant actions.
- Metadata persistence supports `file`, `database` (sqlite), and `mysql` adapters; new metadata repository behavior must keep backend parity.
- Frontend auth currently has only login/me wrappers in `frontend/src/api/auth.ts`.
- Frontend route/navigation already filters by role and permissions.
- Existing visible UI copy for operator-facing pages should stay Chinese-first.

## Problems And Recommended Choices

| Problem | Options | Recommended Choice |
|---|---|---|
| Whether to add user management | 1. keep editing JSON/env; 2. add internal user management MVP; 3. integrate external IAM now | Choose 2 |
| Scope size | 1. password change only; 2. create/disable/reset + self change password; 3. full IAM | Choose 2 |
| User source | 1. keep config as source of truth; 2. use managed repository as source of truth with config bootstrap; 3. external provider | Choose 2 |
| Storage | 1. sqlite/mysql only; 2. repository parity across file/sqlite/mysql; 3. frontend local storage | Choose 2 |
| Permissions | 1. custom per-user permissions; 2. keep `admin`/`operator` role-derived permissions; 3. group hierarchy | Choose 2 |
| Admin password operation | 1. reveal current password; 2. reset to new temporary password; 3. email delivery | Choose 2 |
| Self password operation | 1. admin only; 2. current user can change with current password; 3. passwordless | Choose 2 |
| Session invalidation | 1. wait for token expiry; 2. invalidate tokens after password reset/change and disable; 3. central session store | Choose 2 |
| Frontend placement | 1. login page; 2. `系统运维` / `用户管理` admin page plus account password dialog; 3. full settings product | Choose 2 |
| First release migration | 1. manual database edits; 2. seed repository from existing configured users when empty; 3. forced new setup wizard | Choose 2 |

## Requirements

### R1. Managed Internal User Repository

Add a managed internal user repository as the source of truth for runtime authentication.

Required behavior:

- Support `file`, `database` (sqlite), and `mysql` metadata backends.
- Add a domain-owned repository protocol for internal users.
- Add concrete adapters for:
  - local file backend
  - sqlite backend
  - MySQL backend
- Use parameterized SQL for sqlite/MySQL.
- Keep file/sqlite/MySQL behavior aligned.
- Store password hashes only on the backend; never return them through API responses.

Recommended model fields:

- `id`
- `username`
- `normalized_username`
- `password_hash`
- `role`: `admin` or `operator`
- `tenant_id`
- `company_id`
- `status`: `active` or `disabled`
- `display_name`
- `token_version` or equivalent token invalidation value
- `created_at`
- `updated_at`
- `created_by`
- `updated_by`

Database schema guidance:

- sqlite table: `internal_users`
- MySQL table: `internal_users`
- Include a unique index on normalized username.
- Use the existing serialized payload pattern where appropriate, but keep normalized username and status/role searchable enough for list and login lookup.

### R2. Config Bootstrap Without Dual Source Of Truth

Preserve the existing configured-user path as a bootstrap/migration path, not as the ongoing source of truth.

Required behavior:

- If the managed user repository is empty and `AUTH_INTERNAL_USERS_FILE` or `AUTH_INTERNAL_USERS_JSON` is configured, import those users into the repository at startup.
- If the repository already has users, do not merge config users into it automatically.
- Avoid silent fallback from repository to config after managed users exist.
- Keep startup/auth errors explicit when no users are configured and the repository is empty.
- Document or test the bootstrap behavior so deployment can migrate safely.

Rules:

- Do not keep two live sources of user truth.
- Do not overwrite managed users from config after bootstrap.
- Do not log password hashes or raw configured password data.

### R3. Authentication Service Update

Update `AuthService` to authenticate against the managed repository.

Required behavior:

- Login finds users by normalized username.
- Disabled users cannot log in.
- Disabled users' existing bearer tokens become invalid because token validation reloads the user record.
- Password changes and admin resets invalidate existing tokens for that user.
- JWTs include enough data to validate token freshness, such as `token_version`.
- Existing role-derived permissions remain stable.
- `GET /api/v1/auth/me` continues to return the current user shape, with any compatible additions only if needed.

Rules:

- Keep `hash_password` and `verify_password` or a compatible replacement.
- Do not return password hashes.
- Do not add silent compatibility paths that make invalid user state look valid.

### R4. Admin User Management API

Add admin-only user management endpoints.

Recommended endpoints:

- `GET /api/v1/users`
- `POST /api/v1/users`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/users/{user_id}/reset-password`

Required capabilities:

- List users with filters for role, status, and keyword.
- Create an `admin` or `operator` user with username, display name, role, status, and initial password.
- Update display name, role, and status.
- Reset a user's password to a provided temporary password.
- Return safe user responses without password hashes.

Validation and safety:

- Only admin users can call these endpoints.
- Username must be unique case-insensitively.
- Username cannot be blank.
- Password cannot be blank and should meet a minimal strength rule.
- Role must be `admin` or `operator`.
- Status must be `active` or `disabled`.
- Prevent disabling or downgrading the last active admin.
- Prevent deleting users in this MVP; use `disabled` instead.
- Do not allow admin operations to expose current passwords.

### R5. Self-Service Password Change API

Add a current-user password change endpoint.

Recommended endpoint:

- `POST /api/v1/auth/change-password`

Required behavior:

- Requires current Bearer JWT.
- Requires the current password.
- Requires a new password.
- Rejects incorrect current password.
- Rejects blank or weak new password.
- Changes the password hash.
- Invalidates existing tokens for the user, including the token used for the request after the response completes.
- Records an audit event.

Rules:

- Do not allow changing another user's password through this endpoint.
- Do not return password hashes or password strength details that leak policy internals unnecessarily.

### R6. Audit Events

Record successful account lifecycle operations through `AuditService`.

Required audit actions:

- `auth.login`
- `auth.change_password`
- `users.create`
- `users.update`
- `users.disable`
- `users.enable`
- `users.reset_password`

Required details:

- actor id and role
- target user id
- changed safe fields such as role/status/display name
- trace id

Rules:

- Never include passwords, password hashes, JWTs, or bearer tokens in audit details.
- For password reset/change, record that the operation happened, not the password content.

### R7. Frontend User Management Page

Add an admin-only frontend page for user management.

Recommended placement:

- Navigation group: `系统运维`
- Item label: `用户管理`
- Route: `/system-status/users` or another route consistent with current system routes.
- Permission: admin-only plus a role-derived permission such as `users:manage`.

Required UI:

- Dense user table with:
  - username
  - display name
  - role
  - status
  - updated time
  - row actions
- Filters:
  - keyword
  - role
  - status
- Actions:
  - create user
  - edit display name / role / status
  - enable / disable
  - reset password
- Use Chinese-first visible copy.
- Keep password fields masked.
- Provide clear success/error feedback.
- Do not display password hashes.
- Do not put cards inside cards.
- Keep table wrappers mobile-safe per frontend layout guidelines.

### R8. Current User Password Change UI

Add a small self-service password change entry.

Recommended placement:

- Current user area in the topbar or account menu.

Required UI:

- `修改密码` dialog.
- Fields:
  - current password
  - new password
  - confirm new password
- Client-side confirmation check for the two new-password entries.
- Chinese validation and success/error copy.
- After success, log the user out or require re-login if token invalidation makes the current token stale.

Rules:

- Do not expose this as a full account profile product.
- Do not add email, phone, avatar, or notification preferences in this MVP.

### R9. Role And Permission Boundary

Keep the role model small.

Required behavior:

- Keep `admin` and `operator` as the only roles.
- Add `users:manage` to admin permissions if a permission string is needed for frontend route/navigation consistency.
- Keep permissions derived from roles.
- Do not add custom per-user permission editing.
- Do not add teams, groups, organizations, or multi-tenant admin scope in this MVP.

### R10. API Contracts And Documentation

Update API schemas and docs when contracts change.

Required work:

- Add request/response schemas for user management and password change.
- Update `docs/api/openapi.json` after backend API changes.
- Update frontend API types/wrappers.
- Keep stable error response shape.

Recommended error cases:

- `401 unauthorized` for missing/invalid bearer token.
- `403 role_forbidden` for non-admin user management access.
- `400 invalid_request` for invalid role/status/password/username.
- `409 user_conflict` or another stable conflict code for duplicate username.
- `404 not_found` for unknown user id.
- `409 last_admin_conflict` or another stable conflict code for disabling/downgrading the last active admin.

If new error codes are introduced, add them to `app/core/errors.py`.

## Acceptance Criteria

- [ ] Admin can create an operator from the UI and the new user can log in.
- [ ] Admin can create another admin.
- [ ] Admin cannot create duplicate usernames case-insensitively.
- [ ] Admin can disable a user and that user can no longer log in.
- [ ] Disabling a user invalidates existing tokens for that user.
- [ ] Admin can reset a user's password without seeing the old password.
- [ ] A user can change their own password after providing the current password.
- [ ] Password reset/change invalidates existing tokens for that user.
- [ ] The system prevents disabling or downgrading the last active admin.
- [ ] User management APIs are admin-only.
- [ ] User responses never include password hashes.
- [ ] Successful user lifecycle operations are audited without secrets.
- [ ] Existing login and `/auth/me` behavior remains compatible for existing frontend flows.
- [ ] Configured users can seed the managed repository when it is empty.
- [ ] File, sqlite, and MySQL persistence adapters support the new internal user repository consistently.
- [ ] Frontend visible copy for user management and password change is Chinese-first.
- [ ] `frontend/` build passes after frontend changes.
- [ ] Backend targeted tests and release/API contract checks pass.

## Definition Of Done

- Read backend specs for directory structure, database, error handling, logging, and quality before implementation.
- Read frontend layout guidelines before adding user management pages.
- Add backend tests for auth service, repository adapters, user management API, password change API, audit behavior, token invalidation, and bootstrap behavior.
- Add frontend tests or smoke coverage for admin user management and password change where practical.
- Update OpenAPI artifacts and frontend API types when API contracts change.
- Run targeted backend tests first.
- Run the backend release gate because this changes API contracts and persistence.
- Run `npm run build` in `frontend/`.
- Verify that no secrets, password hashes, JWTs, or raw passwords are logged, returned, audited, or committed.

## Technical Approach

1. Add internal user domain models, repository protocol, service methods, and validation rules.
2. Add file/sqlite/MySQL repository adapters and idempotent schema bootstrap.
3. Wire the user repository into `PersistenceAdapters`, `AppRuntime`, and `AuthService`.
4. Preserve config-user bootstrap only when the repository is empty.
5. Add admin user management and self password-change endpoints.
6. Add audit events for successful account lifecycle operations.
7. Add frontend API wrappers, types, route, navigation item, admin page, and password-change dialog.
8. Add focused tests and update OpenAPI docs.

## Decision (ADR-lite)

**Context**: The project already has JWT auth, role-derived permissions, and internal user records, but users are loaded from static config. This blocks normal operational lifecycle work: onboarding, password rotation, disabling users, and account recovery.

**Decision**: Build an internal user management MVP backed by the existing metadata persistence architecture. Keep config users only as an initial bootstrap path. Keep roles limited to `admin` and `operator`.

**Consequences**: This adds cross-layer persistence and API work, so it needs careful tests and API artifact updates. It avoids the larger cost of external IAM/SSO and custom permissions while solving the immediate operational gap.

## Out Of Scope

- External IAM, SSO, OAuth, SAML, LDAP, or OIDC.
- User self-registration.
- Email or SMS password reset delivery.
- Password reset links or email verification.
- MFA.
- Custom per-user permissions.
- Teams, groups, departments, or organization hierarchy.
- Deleting users.
- Session management UI or central session store.
- Password history, account lockout, rate limiting, and forced password change after reset unless implementation finds they are already easy and low risk.
- Full profile management, avatars, phone numbers, notification preferences, or locale settings.
- Multi-tenant admin delegation.

## Technical Notes

Relevant files inspected:

- `app/api/v1/routers/auth.py`
- `app/api/v1/routers/auth_schemas.py`
- `app/services/auth/service.py`
- `app/services/auth/models.py`
- `app/services/auth/permissions.py`
- `app/api/dependencies.py`
- `app/core/config.py`
- `app/core/runtime.py`
- `app/infrastructure/persistence/factory.py`
- `app/infrastructure/persistence/sqlite/schema.py`
- `app/infrastructure/persistence/mysql/schema.py`
- `app/domains/audit/service.py`
- `frontend/src/api/auth.ts`
- `frontend/src/api/types.ts`
- `frontend/src/router/index.ts`
- `frontend/src/navigation/appShell.ts`

Relevant specs:

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/spec/backend/error-handling.md`
- `.trellis/spec/backend/logging-guidelines.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `.trellis/spec/frontend/index.md`
- `.trellis/spec/frontend/layout-guidelines.md`
