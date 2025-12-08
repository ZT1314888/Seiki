from datetime import datetime
from enum import Enum

from pydantic import EmailStr, Field

from ..base import BaseSchema


class OrganizationType(str, Enum):
    """Self-service onboarding organization types.

    Values follow kebab-case naming as per global enum label guidelines.
    """

    MEDIA_OWNER = "media-owner"
    MEDIA_AGENCY = "media-agency"
    BRAND_ADVERTISER = "brand-advertiser"


class RegisterRequest(BaseSchema):
    """Client self-service registration payload for Seiki."""

    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: EmailStr
    phone: str = Field(..., min_length=3)
    organization_type: OrganizationType
    company_name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class VerifyEmailRequest(BaseSchema):
    """Request payload to verify email with a code sent to the inbox."""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=10)


class UserResponse(BaseSchema):
    """Minimal user info returned after registration."""

    id: int
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    organization_type: OrganizationType | None = None


class LoginRequest(BaseSchema):
    """Client login payload using email and password."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class TokenResponse(BaseSchema):
    """JWT access token response for client login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseSchema):
    """Request payload to refresh an access token using a refresh token."""

    refresh_token: str


class ForgotPasswordRequest(BaseSchema):
    """Trigger password reset by sending a verification code to email."""

    email: EmailStr


class ResetPasswordRequest(BaseSchema):
    """Reset password using email + verification code."""

    email: EmailStr
    code: str = Field(..., min_length=4, max_length=10)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class LogoutRequest(BaseSchema):
    """Sign out by invalidating the current refresh token."""

    refresh_token: str


class UserInfoResponse(BaseSchema):
    """Detailed profile payload returned by /auth/me."""

    id: int
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    country_code: str | None = None
    phone_number: str | None = None
    company_name: str | None = None
    user_type: str | None = None
    role_type: str | None = None
    full_name: str | None = None
    full_phone: str | None = None
    is_verified: bool
    email_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
