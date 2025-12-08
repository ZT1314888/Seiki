from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.client.invitation import (
    InviteUserRequest,
    InvitationInfoResponse,
    RegisterFromInvitationRequest,
)
from app.schemas.response import ApiResponse
from app.services.client.invitation import client_invitation_service
from app.api.client.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/send")
async def invite_user(
    payload: InviteUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Invite a user into the current organization (admin only)."""

    token = await client_invitation_service.invite(db, current_user, payload)
    return ApiResponse.success(data={"token": token})


@router.get("/resolve")
async def resolve_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Resolve invitation token and return pre-filled registration info."""

    info = await client_invitation_service.resolve(db, token)
    return ApiResponse.success(data=info)


@router.post("/register-from-invite")
async def register_from_invite(
    payload: RegisterFromInvitationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete registration flow using an invitation token."""

    user = await client_invitation_service.register_from_invite(db, payload)
    return ApiResponse.success(data=user)


@router.get("/collaborators")
async def list_users(
    email: str | None = None,
    status: Literal["pending", "active", "deactivated"] | None = None,
    role_type: Literal["owner", "admin", "operator"] | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return users and invitations filtered by email for current owner."""

    collaborators = await client_invitation_service.list_users(
        db,
        current_user=current_user,
        email=email,
        status=status,
        role_type=role_type,
    )
    return ApiResponse.success(data=collaborators)


@router.post("/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resend invitation email by user ID for current owner."""

    await client_invitation_service.resend_invitation(
        db,
        current_user=current_user,
        invitation_id=invitation_id,
    )
    return ApiResponse.success_without_data()
