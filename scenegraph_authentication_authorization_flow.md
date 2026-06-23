# Authentication and Authorization Flow in SceneGraph

This document explains the complete authentication and authorization flow implemented in SceneGraph. The goal is to clarify what happens from the moment a user registers until the backend decides whether a request is allowed.

## 1. Authentication vs Authorization

These concepts are related but different.

### Authentication

Authentication answers:

```text
Who are you?
```

Example:

```text
Username: aaron
Password: secret123
```

If the credentials are correct, the backend knows the identity of the user.

### Authorization

Authorization answers:

```text
What are you allowed to do?
```

Examples:

```text
Artist → edit own biography
Agent → manage own account
Admin → approve users
Admin → approve artist claims
```

A user can be authenticated but still not authorized for a particular action.

## 2. Registration Flow

The registration process is intentionally separated from login.

Flow:

```text
User fills registration form
        ↓
POST /api/register
        ↓
User stored in database
status = pending
        ↓
Admin reviews request
        ↓
Approve or Reject
```

A newly registered user does not immediately receive access to protected parts of the application.

The admin dashboard is responsible for approving or rejecting registrations.

## 3. Login Flow

Once approved, a user can log in.

Flow:

```text
Username + Password
        ↓
POST /api/login
        ↓
Backend validates credentials
        ↓
JWT token generated
        ↓
Token returned to frontend
        ↓
Frontend stores token
```

Example response:

```json
{
  "success": true,
  "access_token": "eyJhbGc..."
}
```

The JWT becomes the user's proof of identity.


## 3.5 Bootstrap Admin Flow

One special case in the authentication system is the first admin account.

This is needed because of a chicken-and-egg problem:

```text
Admin users approve registrations
        ↓
But initially there is no admin user
        ↓
So the system needs a bootstrap admin
```

The bootstrap admin is created from environment variables.

Typical `.env` values:

```text
BOOTSTRAP_ADMIN_USERNAME=admin-a
BOOTSTRAP_ADMIN_EMAIL=scenegraph_team@gmail.com
BOOTSTRAP_ADMIN_PASSWORD=...
```

At backend startup, the application checks whether the bootstrap admin already exists.

If it does not exist:

```text
Create admin user
role = admin
status = approved
must_change_password = true
```

This means the bootstrap admin can log in, but should immediately be forced to change the initial password.

## 3.6 Forced Password Change

The bootstrap password is not intended to remain the long-term admin password.

Therefore the user has:

```text
must_change_password = true
```

Login still succeeds, because the user must be authenticated before changing the password.

But the frontend checks the login response:

```text
must_change_password: true
```

and redirects to:

```text
/change-password?forced=true
```

In this forced mode:

```text
User cannot continue normally
        ↓
User must enter current bootstrap password
        ↓
User sets a new valid password
        ↓
Backend updates password hash
        ↓
must_change_password = false
        ↓
User can continue to dashboard
```

This was an important detail: `must_change_password = true` should not block login completely. It should allow login only enough to reach the password-change page.

## 3.7 Why Bootstrap Is Different From Normal Registration

Normal users follow this flow:

```text
Register
        ↓
status = pending
        ↓
Admin approves
        ↓
User can log in
```

The bootstrap admin follows this flow:

```text
Created automatically from .env
        ↓
status = approved
role = admin
must_change_password = true
        ↓
First login redirects to forced password change
        ↓
After password change, normal admin use
```

The bootstrap admin therefore bypasses the registration approval queue, because it is needed to create the first working administrator.

## 3.8 Password Hashing

Passwords are never stored directly in the database.

Instead the backend stores:

```text
password_hash
```

The hash is generated with the backend password hashing context.

Login works by comparing:

```text
entered password
        ↓
verify against password_hash
```

Important practical note:

If a developer manually updates `password_hash` in the database, the value must be a real bcrypt/passlib-compatible hash. Plain text will break login and can produce errors such as:

```text
UnknownHashError: hash could not be identified
```

So bootstrap passwords should either be created by the application logic or replaced with a correctly generated hash.


## 4. JWT Token Contents

A JWT is not random text.

It contains information about the logged-in user.

Typical payload:

```json
{
  "sub": "2",
  "username": "newartist",
  "role": "artist",
  "exp": 1782167857
}
```

Important fields:

```text
sub      → user id
username → username
role     → artist / agent / admin
exp      → expiration time
```

The backend signs the token using a secret key.

Because of the signature, users cannot simply modify the role to become admin.

## 5. Frontend Authentication Flow

After login:

```text
Frontend receives JWT
        ↓
Stores token
        ↓
Future requests include token
```

Request example:

```http
Authorization: Bearer eyJhbGc...
```

The frontend API wrapper automatically attaches the token.

Therefore most components do not need to manually manage authentication headers.

## 6. Backend Authentication Flow

Protected endpoints use:

```python
current_user: dict = Depends(get_current_user)
```

Example:

```python
@router.get("/profile")
async def get_profile(
    current_user: dict = Depends(get_current_user)
):
    ...
```

FastAPI executes:

```text
get_current_user()
        ↓
Read Authorization header
        ↓
Extract token
        ↓
Validate signature
        ↓
Validate expiration
        ↓
Return current user
```

If validation fails:

```text
401 Unauthorized
```

is returned automatically.

## 7. Authorization Using Roles

Authentication only proves identity.

Authorization uses the role stored in the token.

Example roles:

```text
artist
agent
admin
```

The backend checks permissions before executing sensitive actions.

Examples:

### Artist

Allowed:

```text
View own profile
Edit own biography
Create artist claim
```

Not allowed:

```text
Approve users
Deactivate users
Approve claims
```

### Agent

Allowed:

```text
Normal authenticated functionality
```

Not allowed:

```text
Admin functions
```

### Admin

Allowed:

```text
Approve registrations
Reject registrations
Activate users
Deactivate users
Change roles
Review activity logs
Approve artist claims
Reject artist claims
```

## 8. Admin Authorization

Admin-only endpoints usually use:

```python
admin: dict = Depends(require_admin)
```

Flow:

```text
Validate JWT
        ↓
Read role from token
        ↓
Check role == admin
        ↓
Allow request
```

Otherwise:

```text
403 Forbidden
```

is returned.

Difference:

```text
401 = not authenticated
403 = authenticated but not authorized
```

## 9. Artist Biography Ownership

A good example of authorization beyond roles.

Being an artist is not enough.

The backend also checks ownership.

Database:

```text
users.artist_id
```

Example:

```text
user id = 2
artist_id = 2
```

When updating a biography:

```text
PATCH /artists/2/biography
```

Backend verifies:

```text
current_user.artist_id == requested artist id
```

If not:

```text
403 Forbidden
```

This prevents artists from editing each other's biographies.

Admins may optionally bypass this restriction.

## 10. Artist Claim Workflow

Purpose:

```text
Link a registered artist account
to an existing artist profile.
```

Flow:

```text
Artist finds profile
        ↓
Claim request submitted
        ↓
Reason provided
        ↓
Stored in artist_claims
        ↓
Admin reviews claim
        ↓
Approve or Reject
```

Approval:

```text
users.artist_id updated
        ↓
Artist becomes owner
        ↓
Biography editing allowed
```

Rejection:

```text
Claim denied
        ↓
No ownership granted
```

## 11. Activity Logging

Important security-related actions are logged.

Examples:

```text
Login
Logout
Registration
Approval
Rejection
Activation
Deactivation
Role changes
```

This allows admins to review who performed important actions.

The activity log is separate from authentication itself, but it supports auditing and traceability.

## 12. Complete Request Lifecycle

Example:

```text
Artist clicks Save Biography
        ↓
Frontend sends PATCH request
        ↓
JWT attached automatically
        ↓
Backend validates token
        ↓
Backend identifies user
        ↓
Backend checks artist ownership
        ↓
Database updated
        ↓
Response returned
        ↓
Frontend refreshes view
```

## 13. Summary

SceneGraph security is built on three layers:

```text
Layer 1
Authentication
(JWT token)

Layer 2
Role-based authorization
(artist / agent / admin)

Layer 3
Resource ownership checks
(e.g. artist_id matches biography owner)
```

A request is allowed only if all required layers succeed.

This separation keeps the implementation simple while providing meaningful protection for administrative functions and artist-owned content.
