import secrets
import logging
from datetime import datetime, timedelta, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import AuthBase
from app.exceptions.http_exceptions import APIException
from app.models.invitation import Invitation
from app.models.user import User
from app.db.session import transaction
from app.schemas.client.auth import UserResponse, OrganizationType
from app.schemas.client.invitation import (
    InviteUserRequest,
    InvitationInfoResponse,
    RegisterFromInvitationRequest,
)
from app.services.common.email import email_service


INVITATION_TTL_DAYS = 7


class ClientInvitationService:
    @staticmethod
    async def invite(
        db: AsyncSession,
        current_user: User,
        payload: InviteUserRequest,
    ) -> str:
        """Create an invitation and send activation link to invitee.

        Owners and admins can invite operators/admins into their organization.
        """

        if current_user.role not in {"admin", "owner"}:
            raise APIException(status_code=403, message="Only admin or owner can invite users")

        # Generate raw invite token and its hash for storage
        raw_token = secrets.token_urlsafe(32)
        hashed_token = AuthBase.hash_token(raw_token)

        now = datetime.now(UTC)
        expires_at = now + timedelta(days=INVITATION_TTL_DAYS)

        async with transaction(db):
            invitation = Invitation(
                email=payload.email,
                organization_type=current_user.organization_type,
                company_name=current_user.company_name,
                role=payload.role,
                inviter_user_id=current_user.id,
                token=hashed_token,
                expires_at=expires_at,
                is_used=False,
            )
            db.add(invitation)
            await db.flush()

        # Return the raw token so the caller can expose it via API
        # responses or other channels during development.
        invitation._raw_token = raw_token  # type: ignore[attr-defined]
        inviter_name = " ".join(
            [name for name in [current_user.first_name, current_user.last_name] if name]
        ).strip() or current_user.email

        role_label = "Administrator" if payload.role == "admin" else "Operator"

        try:
            await email_service.send_invitation_email(
                invitee_email=payload.email,
                inviter_name=inviter_name,
                company_name=current_user.company_name or "",
                role_label=role_label,
                expires_at=expires_at,
                ttl_days=INVITATION_TTL_DAYS,
                support_email=settings.ADMIN_EMAIL,
            )
        except Exception as exc:  # pragma: no cover
            if settings.ENV.lower() == "development":
                logging.getLogger("client_invitation").warning(
                    "Invitation email failed to send, token=%s, error=%s",
                    raw_token,
                    exc,
                )
            else:
                raise

        return raw_token

    @staticmethod
    async def _get_valid_invitation(
        db: AsyncSession,
        raw_token: str,
    ) -> Invitation:
        """Internal helper to find a valid (not used, not expired) invitation."""

        # Fetch all not-used invitations and compare hash
        result = await db.execute(
            select(Invitation).where(Invitation.is_used.is_(False))
        )
        invitations = result.scalars().all()

        for inv in invitations:
            if not AuthBase.verify_token_hash(raw_token, inv.token):
                continue
            if inv.expires_at <= datetime.now(UTC):
                continue
            return inv

        raise APIException(status_code=400, message="Invalid or expired invitation token")

    @staticmethod
    async def resolve(db: AsyncSession, raw_token: str) -> InvitationInfoResponse:
        """Resolve an invitation token and return information for pre-filling form."""

        invitation = await ClientInvitationService._get_valid_invitation(db, raw_token)

        return InvitationInfoResponse(
            token=raw_token,
            email=invitation.email,
            organization_type=OrganizationType(invitation.organization_type)
            if invitation.organization_type
            else None,
            company_name=invitation.company_name,
            role=invitation.role,
            expires_at=invitation.expires_at,
        )

    @staticmethod
    async def register_from_invite(
        db: AsyncSession,
        payload: RegisterFromInvitationRequest,
    ) -> UserResponse:
        """Register a user from invitation token and activate the account immediately."""

        if payload.password != payload.confirm_password:
            raise APIException(status_code=400, message="Passwords do not match")

        invitation = await ClientInvitationService._get_valid_invitation(
            db, payload.invite_token
        )

        if payload.email.lower() != invitation.email.lower():
            raise APIException(status_code=400, message="Invite data mismatch: email")

        if payload.company_name and payload.company_name != invitation.company_name:
            raise APIException(status_code=400, message="Invite data mismatch: company")

        if payload.organization_type and invitation.organization_type:
            if payload.organization_type.value != invitation.organization_type:
                raise APIException(
                    status_code=400,
                    message="Invite data mismatch: organization_type",
                )

        async with transaction(db):
            # Check if user already exists and is active
            result = await db.execute(select(User).where(User.email == invitation.email))
            user = result.scalar_one_or_none()

            if user is not None and user.is_active:
                raise APIException(status_code=400, message="Email already registered")

            hashed_password = User.get_password_hash(payload.password)

            if user is None:
                user = User(
                    email=invitation.email,
                    hashed_password=hashed_password,
                    first_name=payload.first_name,
                    last_name=payload.last_name,
                    phone=payload.phone,
                    company_name=invitation.company_name,
                    organization_type=invitation.organization_type,
                    role=invitation.role,
                    is_active=True,
                    is_verified=True,
                )
                db.add(user)
            else:
                user.hashed_password = hashed_password
                user.first_name = payload.first_name
                user.last_name = payload.last_name
                user.phone = payload.phone
                user.company_name = invitation.company_name
                user.organization_type = invitation.organization_type
                user.role = invitation.role
                user.is_active = True
                user.is_verified = True

            # Mark invitation as used
            invitation.is_used = True
            invitation.used_at = datetime.now(UTC)

            await db.flush()

        org_type_enum = None
        if user.organization_type:
            org_type_enum = OrganizationType(user.organization_type)

        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            company_name=user.company_name,
            organization_type=org_type_enum,
        )


client_invitation_service = ClientInvitationService()
