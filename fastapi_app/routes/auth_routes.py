"""
Authentication API routes for user registration, login, and token management.
"""

import logging

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select, or_

from fastapi_app.auth_dependencies import (
    CurrentUser,
    CurrentActiveUser,
)
from fastapi_app.postgres_models import User
from fastapi_app.api_models import (
    UserCreate,
    UserPublic,
    Token,
    LoginRequest,
    RefreshTokenRequest,
    PasswordChangeRequest,
    UserUpdate,
)
from fastapi_app.auth_utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_token_type,
)
from fastapi_app.dependencies import DBSession

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger("ragapp")


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate,
    database_session: DBSession,
) -> UserPublic:
    """
    Register a new user.

    Args:
        user_data: User registration data
        database_session: Database session

    Returns:
        Created user public data

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if user already exists
    result = await database_session.execute(
        select(User).where(
            or_(User.email == user_data.email, User.username == user_data.username)
        )
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
            )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False,
    )

    database_session.add(new_user)
    await database_session.commit()
    await database_session.refresh(new_user)

    logger.info(f"New user registered: {new_user.username} ({new_user.email})")

    return UserPublic.model_validate(new_user)


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    database_session: DBSession,
) -> Token:
    """
    Authenticate user and return JWT tokens.

    Args:
        login_data: Login credentials (username/email and password)
        database_session: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by username or email
    result = await database_session.execute(
        select(User).where(
            or_(User.username == login_data.username, User.email == login_data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    # Create tokens
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"User logged in: {user.username}")

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="bearer"
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_request: RefreshTokenRequest,
    database_session: DBSession,
) -> Token:
    """
    Refresh access token using refresh token.

    Args:
        token_request: Refresh token
        database_session: Database session

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    # Decode and validate refresh token
    payload = decode_token(token_request.refresh_token)
    validate_token_type(payload, "refresh")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify user still exists and is active
    result = await database_session.execute(select(User).where(User.id == user_id_str))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new tokens
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    logger.info(f"Token refreshed for user: {user.username}")

    return Token(
        access_token=access_token, refresh_token=new_refresh_token, token_type="bearer"
    )


@router.get("/me", response_model=UserPublic)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserPublic:
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user from token

    Returns:
        Current user public data
    """
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_current_user(
    user_update: UserUpdate,
    current_user: CurrentActiveUser,
    database_session: DBSession,
) -> UserPublic:
    """
    Update current user profile.

    Args:
        user_update: User update data
        current_user: Current authenticated user
        database_session: Database session

    Returns:
        Updated user public data

    Raises:
        HTTPException: If username or email is already taken
    """
    # Check if username is being changed and is available
    if user_update.username and user_update.username != current_user.username:
        result = await database_session.execute(
            select(User).where(User.username == user_update.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
            )
        current_user.username = user_update.username

    # Check if email is being changed and is available
    if user_update.email and user_update.email != current_user.email:
        result = await database_session.execute(
            select(User).where(User.email == user_update.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        current_user.email = user_update.email

    # Update other fields
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    if user_update.password:
        current_user.hashed_password = get_password_hash(user_update.password)

    await database_session.commit()
    await database_session.refresh(current_user)

    logger.info(f"User profile updated: {current_user.username}")

    return UserPublic.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: CurrentActiveUser,
    database_session: DBSession,
) -> dict[str, str]:
    """
    Change user password.

    Args:
        password_data: Current and new password
        current_user: Current authenticated user
        database_session: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If current password is incorrect
    """
    # Verify current password
    if not verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await database_session.commit()

    logger.info(f"Password changed for user: {current_user.username}")

    return {"message": "Password changed successfully"}
