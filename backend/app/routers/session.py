from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import errors as pg_errors

from app.auth import (
    check_rate_limit,
    create_access_token,
    get_current_user,
    log_activity,
    pwd_context,
    validate_password,
    validate_registration_input,
)
from app.db import get_connection
from app.schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse, response_model_exclude_none=True)
async def login(login_data: LoginRequest) -> LoginResponse:
    check_rate_limit(f"login:{login_data.username}")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, password_hash, role, status, must_change_password, artist_id
                FROM users
                WHERE username = %s
                """,
                (login_data.username,),
            )
            user = cursor.fetchone()

    if user is None:
        return LoginResponse(success=False, message="Invalid username or password")
    if not pwd_context.verify(login_data.password, user["password_hash"]):
        return LoginResponse(success=False, message="Invalid username or password")
    if user["status"] != "approved":
        return LoginResponse(success=False, message="Account is not approved")

    with get_connection() as connection:
        log_activity(connection, user["id"], user["username"], "login", "Login page")
        connection.commit()

    return LoginResponse(
        success=True,
        message="Login successful",
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        access_token=create_access_token(
            {
                "sub": str(user["id"]),
                "username": user["username"],
                "role": user["role"],
            }
        ),
        must_change_password=user["must_change_password"],
        artist_id=user["artist_id"],
    )


@router.post("/register", response_model=RegisterResponse, response_model_exclude_none=True)
async def register(register_data: RegisterRequest) -> RegisterResponse:
    check_rate_limit(f"register:{register_data.email}", max_attempts=3, window_seconds=300)

    if register_data.password != register_data.password_confirm:
        return RegisterResponse(success=False, message="Passwords do not match")

    validation_error = validate_registration_input(register_data)
    if validation_error:
        return RegisterResponse(success=False, message=validation_error)

    has_existing_artist = register_data.artist_id is not None
    has_new_artist_name = bool(register_data.new_artist_name and register_data.new_artist_name.strip())
    if has_existing_artist == has_new_artist_name:
        return RegisterResponse(
            success=False,
            message="Select an existing artist profile or create a new artist profile",
        )

    clean_new_artist_name = register_data.new_artist_name.strip() if register_data.new_artist_name else None
    clean_instagram_url = register_data.instagram_url.strip()
    if clean_new_artist_name is not None and len(clean_new_artist_name) < 2:
        return RegisterResponse(success=False, message="Artist name must be at least 2 characters")
    if clean_new_artist_name is not None and len(clean_new_artist_name) > 100:
        return RegisterResponse(success=False, message="Artist name is too long")

    with get_connection() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pg_advisory_xact_lock(hashtext(LOWER(BTRIM(%s))))
                    """,
                    (clean_instagram_url,),
                )
                if has_existing_artist:
                    cursor.execute(
                        """
                        SELECT pg_advisory_xact_lock(%s)
                        """,
                        (register_data.artist_id,),
                    )

                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE username = %s OR email = %s
                    """,
                    (register_data.username, register_data.email),
                )
                existing_user = cursor.fetchone()

                if existing_user is not None:
                    return RegisterResponse(success=False, message="Username or email already exists")

                selected_artist = None
                if has_existing_artist:
                    cursor.execute(
                        """
                        SELECT id, name
                        FROM artists
                        WHERE id = %s
                        """,
                        (register_data.artist_id,),
                    )
                    selected_artist = cursor.fetchone()
                    if selected_artist is None:
                        return RegisterResponse(success=False, message="Selected artist profile does not exist")

                    cursor.execute(
                        """
                        SELECT id, username
                        FROM users
                        WHERE artist_id = %s
                          AND status IN ('pending', 'approved')
                        LIMIT 1
                        """,
                        (register_data.artist_id,),
                    )
                    assigned_user = cursor.fetchone()
                    if assigned_user is not None:
                        return RegisterResponse(success=False, message="This artist profile is already assigned")

                    cursor.execute(
                        """
                        SELECT id
                        FROM artist_claims
                        WHERE artist_id = %s
                          AND status IN ('pending', 'approved')
                        LIMIT 1
                        """,
                        (register_data.artist_id,),
                    )
                    active_claim = cursor.fetchone()
                    if active_claim is not None:
                        return RegisterResponse(success=False, message="This artist profile already has a registration in progress")
                else:
                    cursor.execute(
                        """
                        INSERT INTO artists (name, ra_artist_id, content_url)
                        VALUES (%s, NULL, NULL)
                        RETURNING id, name
                        """,
                        (clean_new_artist_name,),
                    )
                    selected_artist = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT id
                    FROM artist_claims
                    WHERE LOWER(BTRIM(instagram_url)) = LOWER(BTRIM(%s))
                      AND status IN ('pending', 'approved')
                    LIMIT 1
                    """,
                    (clean_instagram_url,),
                )
                existing_claim = cursor.fetchone()
                if existing_claim is not None:
                    return RegisterResponse(
                        success=False,
                        message="This Instagram URL is already used by another registration",
                    )

                hashed_password = pwd_context.hash(register_data.password)
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        register_data.username,
                        register_data.email,
                        hashed_password,
                        "artist",
                        "pending",
                    ),
                )
                created_user = cursor.fetchone()

                if selected_artist is not None:
                    cursor.execute(
                        """
                        INSERT INTO artist_claims (user_id, artist_id, instagram_url, reason)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            created_user["id"],
                            selected_artist["id"],
                            clean_instagram_url,
                            "Requested during registration",
                        ),
                    )

                log_activity(
                    connection,
                    created_user["id"],
                    register_data.username,
                    "registration",
                    selected_artist["name"] if selected_artist is not None else "User account",
                    commit=False,
                )
                connection.commit()
        except pg_errors.UniqueViolation as exc:
            connection.rollback()
            constraint_name = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint_name == "artist_claims_active_artist_unique_idx":
                return RegisterResponse(success=False, message="This artist profile already has a registration in progress")
            if constraint_name == "artist_claims_active_instagram_unique_idx":
                return RegisterResponse(success=False, message="This Instagram URL is already used by another registration")
            if constraint_name == "users_username_key":
                return RegisterResponse(success=False, message="Username already exists")
            if constraint_name == "users_email_key":
                return RegisterResponse(success=False, message="Email already exists")
            raise

    return RegisterResponse(
        success=True,
        message="Registration successful",
        user_id=created_user["id"],
    )


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
) -> ChangePasswordResponse:
    if password_data.new_password != password_data.new_password_confirm:
        return ChangePasswordResponse(success=False, message="New passwords do not match")

    password_error = validate_password(password_data.new_password)
    if password_error:
        return ChangePasswordResponse(success=False, message=password_error)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, password_hash, status
                FROM users
                WHERE username = %s
                """,
                (password_data.username,),
            )
            user = cursor.fetchone()

        if user is None:
            return ChangePasswordResponse(success=False, message="Invalid username or password")
        if user["status"] != "approved":
            return ChangePasswordResponse(success=False, message="Account is not approved")
        if not pwd_context.verify(password_data.current_password, user["password_hash"]):
            return ChangePasswordResponse(success=False, message="Invalid username or password")
        if pwd_context.verify(password_data.new_password, user["password_hash"]):
            return ChangePasswordResponse(
                success=False,
                message="New password must be different from current password",
            )

        new_hashed_password = pwd_context.hash(password_data.new_password)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    must_change_password = FALSE
                WHERE id = %s
                """,
                (new_hashed_password, user["id"]),
            )
            log_activity(connection, user["id"], user["username"], "password change", "Own account")
            connection.commit()

    return ChangePasswordResponse(success=True, message="Password changed successfully")


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as connection:
        log_activity(connection, current_user["id"], current_user["username"], "logout", "Frontend logout")
        connection.commit()
    return {"success": True, "message": "Logout logged"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    artist_name = None
    if current_user["artist_id"] is not None:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM artists WHERE id = %s",
                    (current_user["artist_id"],),
                )
                artist_row = cursor.fetchone()
        artist_name = artist_row["name"] if artist_row else None

    return {
        "success": True,
        "user_id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "artist_id": current_user["artist_id"],
        "artist_name": artist_name,
    }
