from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.client.deps import get_current_user
from app.models.user import User
from app.schemas.client.auth import (
    RegisterRequest,
    VerifyEmailRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LogoutRequest,
    UserInfoResponse,
)
from app.schemas.response import ApiResponse
from app.services.client.auth import client_auth_service

router = APIRouter()


@router.post("/register")
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Client self-service registration endpoint.

    Creates or updates an inactive user and sends an email verification code.
    """

    user = await client_auth_service.register(db, payload)
    return ApiResponse.success(data=user)


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email using the code sent to the user's inbox."""

    user = await client_auth_service.verify_email(db, payload.email, payload.code)
    return ApiResponse.success(data=user)


@router.post("/login")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Client login endpoint using email and password.

    Returns a JWT access token if credentials are valid and the account is active.
    """

    token = await client_auth_service.login(db, payload)
    return ApiResponse.success(data=token)


@router.post("/refresh-token")
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh the access token for a logged-in client using refresh_token."""

    token = await client_auth_service.refresh_token(db, payload)
    return ApiResponse.success(data=token)


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sign out the user by invalidating current refresh token."""

    await client_auth_service.logout(db, payload)
    return ApiResponse.success()


@router.get("/me", response_model=None)
async def get_user_detail(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile information."""

    user_info: UserInfoResponse = client_auth_service.get_user_info_payload(current_user)
    return ApiResponse.success(
        message="User information retrieved successfully",
        data=user_info,
    )


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send verification code to email for password reset."""

    await client_auth_service.forgot_password(db, payload)
    return ApiResponse.success()


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using email + verification code + new password."""

    await client_auth_service.reset_password(db, payload)
    return ApiResponse.success()
