# Authentication and Public API Access in SceneGraph

This note explains the difference between open endpoints, JWT-protected app endpoints, admin-only endpoints, and API-key-protected public API endpoints in our project.

## 1. Why we have different access mechanisms

SceneGraph has different types of endpoints with different purposes:

| Category | Example | Access mechanism | Purpose |
|---|---|---|---|
| Open app endpoints | `/api/login`, `/api/register`, `/health` | No token, no API key | Needed before a user is authenticated |
| JWT-protected app endpoints | `/api/change-password`, profile-related actions, biography editing | `Authorization: Bearer <JWT>` | Actions done by logged-in users |
| Admin endpoints | `/api/admin/users`, `/api/admin/activity`, `/api/admin/artist-claims` | `Authorization: Bearer <JWT>` + admin role check | Administrative actions |
| Public API endpoints | `/api/public/artists`, `/api/public/events`, `/api/public/venues`, etc. | `X-API-Key: <public-api-key>` | External/client access to selected public data |

The important point is that JWT tokens and API keys are not the same thing. They solve different problems.

## 2. Open endpoints

Some endpoints must be callable without authentication, otherwise users could not enter the system.

Examples:

```text
POST /api/login
POST /api/register
GET /health
```

These are "open" endpoints. They are public in the technical sense that anyone can call them, but they are not the same as our "Public API" feature.

`/api/login` returns a JWT if the credentials are valid. `/api/register` creates a pending account. `/health` is for container/service checks.

## 3. JWT token authentication

JWT tokens are used for normal logged-in app users.

The flow is:

```text
User logs in with username/password
→ backend validates credentials
→ backend returns access_token
→ frontend stores token
→ frontend sends token in later requests
→ backend checks token and role
```

The frontend sends the token with:

```http
Authorization: Bearer <token>
```

In the frontend, this is handled centrally in `frontend/src/api/client.ts`. Any API call using the shared `api.get`, `api.post`, `api.patch`, or `api.delete` wrapper should automatically send the token from `localStorage`.

However, sending the token is only half of the protection. The backend must also check it.

Backend protection is done with dependencies such as:

```python
current_user: dict = Depends(get_current_user)
```

or, for admin-only endpoints:

```python
admin: dict = Depends(require_admin)
```

If an endpoint does not use `Depends(get_current_user)` or `Depends(require_admin)`, the backend will not enforce JWT authentication even if the frontend sends a token.

## 4. Admin-only endpoints

Admin endpoints are protected by role checks.

Example pattern:

```python
@app.get("/api/admin/users")
async def list_users(
    admin: dict = Depends(require_admin),
    connection: Connection = Depends(get_db),
):
    ...
```

`require_admin` first validates the JWT and then checks whether the logged-in user has role `admin`.

Examples of admin-only actions:

```text
GET  /api/admin/users
GET  /api/admin/users/pending
POST /api/admin/users/{user_id}/approve
POST /api/admin/users/{user_id}/reject
POST /api/admin/users/{user_id}/activate
POST /api/admin/users/{user_id}/deactivate
POST /api/admin/users/{user_id}/role
GET  /api/admin/activity
GET  /api/admin/activity/export
GET  /api/admin/artist-claims
POST /api/admin/artist-claims/{claim_id}/approve
POST /api/admin/artist-claims/{claim_id}/reject
```

These endpoints should not use the public API key. They belong to the logged-in admin application.

## 5. Public API key authentication

The Public API is for external clients, scripts, integrations, or other systems that want to access selected SceneGraph data without being logged into the web app as a user.

These requests do not use username/password login and do not receive a JWT.

Instead, they send:

```http
X-API-Key: <public-api-key>
```

Example:

```bash
curl -k -H "X-API-Key: abc123" https://localhost:8443/api/public/artists
```

Backend protection uses:

```python
_: None = Depends(require_public_api_key)
```

Example:

```python
@app.get("/api/public/artists")
async def get_public_artists(
    _: None = Depends(require_public_api_key),
    connection: Connection = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> dict:
    ...
```

The `_` variable means: we do not need the return value of `require_public_api_key`; we only want FastAPI to execute the dependency and reject the request if the key is missing or wrong.

## 6. Why API keys exist even on websites with user accounts

This caused confusion because some external platforms show an API key inside a logged-in user account.

That does not mean the website itself uses the API key for normal browser sessions.

Usually the distinction is:

```text
Browser user session:
username/password → login → session token/JWT/cookie

External API access:
generated API key → script/integration/client calls API
```

A user may log into a website with a normal account and then generate or view an API key in settings. That API key is meant for programmatic access, not for clicking around the web UI.

For example:

```text
Human using the dashboard:
login form → JWT/session cookie

Python script or external client:
X-API-Key header → public/external API endpoint
```

So it is normal for a platform to have both user accounts and API keys. They are used in different contexts.

## 7. Practical local tests

### Login and get JWT

Because local HTTPS uses a self-signed certificate, use `-k` with curl:

```bash
curl -k -X POST https://localhost:8443/api/login \
-H "Content-Type: application/json" \
-d '{
  "username":"admin-a",
  "password":"YOUR_PASSWORD"
}'
```

### Call a JWT-protected endpoint

```bash
curl -k https://localhost:8443/api/admin/activity \
-H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Call a public API endpoint

```bash
curl -k https://localhost:8443/api/public/artists \
-H "X-API-Key: abc123"
```

### Wrong examples

This is wrong for admin endpoints:

```http
X-API-Key: abc123
```

Admin endpoints need JWT + admin role.

This is wrong for public API endpoints:

```http
Authorization: Bearer <JWT>
```

Public API endpoints need `X-API-Key`.

## 8. Summary

Use JWT when the request is made by a logged-in SceneGraph user.

Use `require_admin` when the request must be made by an admin.

Use `X-API-Key` only for the external Public API.

Leave login, register, and health open because they must be accessible before authentication.
