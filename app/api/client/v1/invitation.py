from fastapi import APIRouter, Depends, Header
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
