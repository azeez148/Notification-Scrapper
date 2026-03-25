# Notification-Scrapper

## Background

This repository currently focuses on scraping, normalizing, and storing Kerala PSC notification data.  
To make it production-ready for multi-user operation, this document defines a complete authentication and user management design that can be implemented alongside the existing scraper services.

---

## Requirements

### Core capabilities
- User onboarding (registration)
- JWT-based login (access + refresh tokens)
- RBAC with `admin`, `staff`, `customer`
- Secure password hashing and salting
- Forgot/reset password with expiring token links
- Logout with refresh token/session invalidation

### Non-functional requirements
- Strong input validation for all auth APIs
- Consistent error response format
- Auditability of security-sensitive actions
- Safe defaults for token and password security
- Optional horizontal scaling support (Redis-backed session controls)

---

## Method (Detailed architecture + diagrams)

### High-level architecture

```text
[Client/Web/Mobile]
        |
        v
[FastAPI Auth/API Layer] ----> [PostgreSQL]
        |                          |
        |                          +--> users, roles, permissions, sessions, reset_tokens, audit_logs
        |
        +--> [Redis] (optional: token blacklist, rate-limit counters)
        |
        +--> [Email Service] (password reset + verification)
```

### Component responsibilities
- **API server (FastAPI):** authentication endpoints, user profile, admin role management, RBAC guards
- **PostgreSQL:** system of record for users, roles, permissions, sessions, reset tokens
- **Redis (optional):** short-lived token denylist entries, rate limiting counters, OTP-like temporary data
- **Email service:** sends signed and expiring links for password reset (and optional verification)

### Sequence diagram: Login flow

```text
Client -> API: POST /api/v1/auth/login (email, password)
API -> DB: fetch user by email
DB --> API: user + password_hash + status
API -> API: verify password (Argon2id/bcrypt)
API -> DB: create refresh session row (jti hash, expiry, metadata)
API --> Client: 200 {access_token, refresh_token, expires_in, user}
```

### Sequence diagram: Refresh token flow

```text
Client -> API: POST /api/v1/auth/refresh (refresh_token)
API -> API: verify JWT signature + claims + token type=refresh
API -> DB: lookup session by jti hash and check revoked/expired
API -> DB: rotate refresh token (revoke old, issue new)
API --> Client: 200 {access_token, refresh_token}
```

### Sequence diagram: Forgot/reset password flow

```text
Client -> API: POST /api/v1/auth/forgot-password (email)
API -> DB: if user exists, create reset token hash + expiry
API -> Email: send reset URL with one-time token
API --> Client: 202 generic response (no account disclosure)

Client -> API: POST /api/v1/auth/reset-password (token, new_password)
API -> DB: validate token hash + expiry + unused flag
API -> DB: update user password_hash, mark token used, revoke sessions
API --> Client: 200 password reset successful
```

---

## Implementation

### Suggested stack (aligned with current repo)
- **Python 3.11+**
- **FastAPI** for REST APIs + OpenAPI docs
- **SQLAlchemy** (already used) + Alembic migrations
- **PostgreSQL** (already used)
- **PyJWT / python-jose** for JWT signing and verification
- **argon2-cffi** (preferred) or bcrypt for password hashing
- **Redis** (optional) for rate limiting and token denylist caching

### Suggested folder structure

```text
kerala_psc_scraper/
  api/
    routes/
      auth.py
      users.py
      admin_roles.py
    schemas/
      auth.py
      users.py
      common.py
    dependencies/
      auth.py
      rbac.py
  auth/
    jwt_service.py
    password_service.py
    token_service.py
  database/
    db.py
    repository.py
    user_repository.py
    session_repository.py
  models/
    user.py
    role.py
    permission.py
    session.py
    password_reset_token.py
  services/
    auth_service.py
    user_service.py
    email_service.py
  middleware/
    rate_limit.py
    request_id.py
```

### Environment variables
- `DATABASE_URL` (existing)
- `JWT_ACCESS_SECRET` (required, min 32 bytes)
- `JWT_REFRESH_SECRET` (required, min 32 bytes; separate from access secret)
- `JWT_ACCESS_TTL_SECONDS` (default: `900`)
- `JWT_REFRESH_TTL_SECONDS` (default: `2592000`)
- `PASSWORD_HASH_SCHEME` (default: `argon2id`)
- `PASSWORD_RESET_TTL_MINUTES` (default: `30`)
- `EMAIL_FROM`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `REDIS_URL` (optional)
- `RATE_LIMIT_LOGIN_PER_MINUTE` (default: `5`)
- `RATE_LIMIT_FORGOT_PASSWORD_PER_HOUR` (default: `5`)

### Middleware/guards design
- **`auth_required`**: verifies Bearer access token; loads user context
- **`roles_required(*roles)`**: checks user has any allowed role
- **`permissions_required(*perms)`**: optional fine-grained permission gate
- **Rate limit middleware**:
  - login: by IP + email key
  - forgot-password: by IP + account identifier key

---

## API Specifications

Base path: `/api/v1`

### Standard response envelope

```json
{
  "success": true,
  "data": {},
  "meta": {
    "request_id": "c6f1fcb1-5f2c-4d52-bf7c-4f77cb2a2f20"
  }
}
```

### Standard error format

```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email or password is incorrect",
    "details": [
      { "field": "email", "reason": "invalid_format" }
    ]
  },
  "meta": {
    "request_id": "c6f1fcb1-5f2c-4d52-bf7c-4f77cb2a2f20"
  }
}
```

### 1) Registration API
- **POST** `/auth/register`
- **Auth:** Public
- **Validation:**
  - `email`: required, RFC-compliant, lowercase, unique
  - `password`: required, 12-128 chars, must include upper/lower/number/symbol
  - `name`: required, 2-100 chars
  - `role`: optional, default `customer`; only admin can set non-customer in production flow

Request:
```json
{
  "email": "user@example.com",
  "password": "Str0ng#Password!",
  "name": "Alex User"
}
```

Response `201`:
```json
{
  "success": true,
  "data": {
    "id": "usr_123",
    "email": "user@example.com",
    "name": "Alex User",
    "role": "customer",
    "created_at": "2026-03-25T10:00:00Z"
  }
}
```

Errors: `400`, `409` (`EMAIL_ALREADY_EXISTS`), `429`

### 2) Login API
- **POST** `/auth/login`
- **Auth:** Public
- **Validation:** `email`, `password` required

Request:
```json
{
  "email": "user@example.com",
  "password": "Str0ng#Password!"
}
```

Response `200`:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR...",
    "token_type": "Bearer",
    "expires_in": 900,
    "user": {
      "id": "usr_123",
      "email": "user@example.com",
      "role": "customer"
    }
  }
}
```

Errors: `401` (`INVALID_CREDENTIALS`), `423` (`ACCOUNT_LOCKED`), `429`

### 3) Refresh token API
- **POST** `/auth/refresh`
- **Auth:** Public (refresh token body)

Request:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR..."
}
```

Response `200`:
```json
{
  "success": true,
  "data": {
    "access_token": "new_access_token",
    "refresh_token": "new_refresh_token",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

Errors: `401` (`INVALID_REFRESH_TOKEN`, `EXPIRED_REFRESH_TOKEN`)

### 4) Logout API
- **POST** `/auth/logout`
- **Auth:** Access token required
- **Behavior:** revoke current refresh session (or all sessions)

Request:
```json
{
  "logout_all_devices": false
}
```

Response `200`:
```json
{
  "success": true,
  "data": { "message": "Logged out successfully" }
}
```

### 5) Forgot password API
- **POST** `/auth/forgot-password`
- **Auth:** Public

Request:
```json
{
  "email": "user@example.com"
}
```

Response `202` (always generic):
```json
{
  "success": true,
  "data": {
    "message": "If an account exists, reset instructions have been sent."
  }
}
```

### 6) Reset password API
- **POST** `/auth/reset-password`
- **Auth:** Public

Request:
```json
{
  "token": "reset-token-from-email",
  "new_password": "N3w#StrongPassword!"
}
```

Response `200`:
```json
{
  "success": true,
  "data": { "message": "Password has been reset successfully" }
}
```

Errors: `400`, `401` (`INVALID_RESET_TOKEN`), `410` (`RESET_TOKEN_EXPIRED`)

### 7) Get current user profile API
- **GET** `/users/me`
- **Auth:** Access token required

Response `200`:
```json
{
  "success": true,
  "data": {
    "id": "usr_123",
    "email": "user@example.com",
    "name": "Alex User",
    "role": "customer",
    "created_at": "2026-03-25T10:00:00Z"
  }
}
```

### 8) Role management APIs (admin-only)
- **GET** `/admin/users` (list users + roles)
- **PATCH** `/admin/users/{user_id}/role`
- **GET** `/admin/roles`

Role update request:
```json
{
  "role": "staff"
}
```

Errors: `403` (`FORBIDDEN_ROLE_ASSIGNMENT`)

---

## Database Design

### Core tables (SQL-oriented schema)

#### `users`
- `id` UUID PK
- `email` VARCHAR(320) UNIQUE NOT NULL
- `password_hash` TEXT NOT NULL
- `full_name` VARCHAR(100) NOT NULL
- `is_active` BOOLEAN NOT NULL DEFAULT true
- `failed_login_attempts` INT NOT NULL DEFAULT 0
- `locked_until` TIMESTAMPTZ NULL
- `email_verified_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

#### `roles`
- `id` SMALLINT PK
- `name` VARCHAR(30) UNIQUE NOT NULL (`admin`, `staff`, `customer`)

#### `permissions`
- `id` SMALLINT PK
- `name` VARCHAR(60) UNIQUE NOT NULL (e.g. `users.read`, `users.role.update`)

#### `role_permissions`
- `role_id` FK -> `roles.id`
- `permission_id` FK -> `permissions.id`
- PK (`role_id`, `permission_id`)

#### `user_roles`
- `user_id` FK -> `users.id`
- `role_id` FK -> `roles.id`
- PK (`user_id`, `role_id`)
- Constraint: typically one active role for simple systems, many-to-many kept for flexibility

#### `auth_sessions` (refresh token/session tracking)
- `id` UUID PK
- `user_id` FK -> `users.id` NOT NULL
- `refresh_jti_hash` CHAR(64) UNIQUE NOT NULL
- `user_agent` TEXT NULL
- `ip_address` INET NULL
- `expires_at` TIMESTAMPTZ NOT NULL
- `revoked_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL

#### `password_reset_tokens`
- `id` UUID PK
- `user_id` FK -> `users.id` NOT NULL
- `token_hash` CHAR(64) UNIQUE NOT NULL
- `expires_at` TIMESTAMPTZ NOT NULL
- `used_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL

#### `audit_logs` (bonus)
- `id` UUID PK
- `actor_user_id` UUID NULL
- `action` VARCHAR(80) NOT NULL
- `target_type` VARCHAR(40) NOT NULL
- `target_id` VARCHAR(80) NULL
- `metadata` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ NOT NULL

---

## Authentication & Authorization Details

### JWT token structure

Access token claims:
- `sub` = user id
- `email`
- `roles` (array, e.g. `["customer"]`)
- `type` = `"access"`
- `jti` = unique token ID
- `iat`, `exp`, `iss`, `aud`

Refresh token claims:
- `sub` = user id
- `type` = `"refresh"`
- `jti` = session identifier (mapped by hash in DB)
- `iat`, `exp`, `iss`, `aud`

### Expiration strategy
- Access token: 15 minutes
- Refresh token: 30 days, rotated on every refresh
- Reset token: 30 minutes, one-time use

### Refresh flow safeguards
- Store only hash of refresh token `jti`
- Rotate refresh token on every `/auth/refresh`
- Revoke reused/compromised session chains
- Revoke all user sessions on password reset/change

### RBAC enforcement
- Roles stored in `user_roles`
- Permissions derived from `role_permissions`
- Route-level guards enforce role/permission checks
- Deny-by-default when role/permission missing

---

## Security Considerations

### Password handling
- Use **Argon2id** with strong memory/time cost (preferred) or bcrypt cost >= 12
- Never store plaintext passwords
- Enforce password policy and deny known breached passwords where possible

### Token security
- Sign access and refresh tokens with separate secrets
- Include `aud`/`iss` checks and strict `type` claim checks
- Support key rotation (`kid` header + active key set)
- Return tokens only over HTTPS

### Rate limiting and abuse prevention
- Login throttling by IP and account key
- Forgot-password throttling to prevent spam/user enumeration
- Progressive delay and lockout after repeated failed logins

### Attack prevention
- **Brute force:** rate limit + lockout + audit alerts
- **Token theft:** short access TTL + refresh rotation + session revocation + optional device binding
- **CSRF:** if using cookies, set `HttpOnly`, `Secure`, `SameSite=Lax/Strict` + CSRF token; if Authorization header bearer flow only, CSRF impact is reduced
- **Injection attacks:** ORM parameterization + strict schema validation + output encoding where needed

### Exception handling and status codes
- `400` validation failure
- `401` invalid/expired credentials or token
- `403` authenticated but not authorized
- `404` user/resource not found
- `409` duplicate email/constraint conflict
- `410` expired reset token
- `423` account locked
- `429` rate limit exceeded
- `500` internal error with sanitized message

---

## OpenAPI/Swagger-style documentation structure

```yaml
openapi: 3.0.3
info:
  title: Notification Scrapper Auth API
  version: 1.0.0
servers:
  - url: /api/v1
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
  schemas:
    ErrorResponse: {}
    RegisterRequest: {}
    LoginRequest: {}
    TokenResponse: {}
paths:
  /auth/register:
    post: {}
  /auth/login:
    post: {}
  /auth/refresh:
    post: {}
  /auth/logout:
    post: {}
  /auth/forgot-password:
    post: {}
  /auth/reset-password:
    post: {}
  /users/me:
    get: {}
  /admin/users/{user_id}/role:
    patch: {}
```

---

## Bonus capabilities

- **Email verification:** issue signed verification token at registration, block privileged operations until verified
- **Account locking:** lock account for N minutes after configurable failed login threshold
- **Audit logging:** track auth attempts, role changes, password changes, token revocations
- **Multi-device sessions:** one refresh session row per device; logout can revoke current session or all sessions
