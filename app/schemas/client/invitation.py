from datetime import datetime

from pydantic import EmailStr, Field

from ..base import BaseSchema
from .auth import OrganizationType


class InviteUserRequest(BaseSchema):
    """Admin invites a user into current organization."""

    email: EmailStr
    role: str = Field(..., pattern="^(admin|operator)$")


class InvitationInfoResponse(BaseSchema):
    """Info returned when resolving an invitation token."""

    token: str
    email: EmailStr
    role: str
    company_name: str | None = None
    organization_type: OrganizationType | None = None
    expires_at: datetime


class RegisterFromInvitationRequest(BaseSchema):
    """Complete registration using an invitation token."""

    invite_token: str
    email: EmailStr
    organization_type: OrganizationType | None = None
    company_name: str | None = None
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
