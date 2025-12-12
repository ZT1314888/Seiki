import secrets
import logging
from datetime import datetime, timedelta, UTC

from sqlalchemy import select, or_
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
    CollaboratorItem,
    CollaboratorType,
    CollaboratorStatusUpdateRequest,
    CollaboratorRoleUpdateRequest,
)
from app.services.common.email import email_service


INVITATION_TTL_DAYS = 7
COLLABORATOR_STATUSES = {"pending", "active", "deactivated"}
COLLABORATOR_ROLE_TYPES = {"owner", "admin", "operator"}


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
                organization_id=current_user.organization_id,
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
                    organization_id=invitation.organization_id,
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
                user.organization_id = invitation.organization_id
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

    @staticmethod
    async def list_users(
        db: AsyncSession,
        current_user: User,
        email: str | None = None,
        status: str | None = None,
        role_type: str | None = None,
    ) -> list[CollaboratorItem]:
        if status and status not in COLLABORATOR_STATUSES:
            raise APIException(status_code=400, message="Invalid status filter")

        if role_type:
            normalized_role_type = role_type.lower()
            if normalized_role_type not in COLLABORATOR_ROLE_TYPES:
                raise APIException(status_code=400, message="Invalid role_type filter")
            role_type = normalized_role_type

        organization_id = current_user.organization_id

        user_query = select(User).where(User.organization_id == organization_id)
        invitation_query = None
        if status in (None, "pending"):
            invitation_query = (
                select(Invitation)
                .where(Invitation.organization_id == organization_id)
                .order_by(Invitation.created_at.desc())
            )

        if status == "active":
            user_query = user_query.where(User.is_active.is_(True))
        elif status == "deactivated":
            user_query = user_query.where(User.is_active.is_(False))
        elif status == "pending":
            user_query = None
            invitation_query = invitation_query.where(Invitation.is_used.is_(False))
        elif status is None:
            invitation_query = invitation_query.where(Invitation.is_used.is_(False))

        if email:
            like_value = f"%{email}%"
            if user_query is not None:
                user_query = user_query.where(User.email.ilike(like_value))
            if invitation_query is not None:
                invitation_query = invitation_query.where(Invitation.email.ilike(like_value))

        if role_type:
            if user_query is not None:
                user_query = user_query.where(User.role == role_type)
            if invitation_query is not None:
                invitation_query = invitation_query.where(Invitation.role == role_type)
            if role_type == "owner":
                invitation_query = None

        user_rows: list[User] = []
        invitation_rows: list[Invitation] = []

        if user_query is not None:
            user_result = await db.execute(user_query)
            user_rows = user_result.scalars().all()

        if invitation_query is not None:
            invitation_result = await db.execute(invitation_query)
            invitation_rows = invitation_result.scalars().all()

        owner_user_ids: set[int] = {user.id for user in user_rows if user.role == "owner"}

        collaborators: list[CollaboratorItem] = []

        for user in user_rows:
            collaborators.append(
                CollaboratorItem(
                    id=user.id,
                    unique_key=f"user:{user.id}",
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role_type="owner" if user.id in owner_user_ids else user.role,
                    is_active=bool(user.is_active),
                    status="active" if user.is_active else "deactivated",
                    created_at=user.created_at,
                    last_active_at=user.last_active_at,
                    type=CollaboratorType.USER,
                )
            )

        user_email_keys = {user.email.lower(): user for user in user_rows}

        for invitation in invitation_rows:
            invitation_email_key = invitation.email.lower()
            if invitation_email_key in user_email_keys:
                continue
            collaborators.append(
                CollaboratorItem(
                    id=invitation.id,
                    unique_key=f"invitation:{invitation.id}",
                    email=invitation.email,
                    first_name=None,
                    last_name=None,
                    role_type=invitation.role,
                    is_active=False,
                    status="pending" if not invitation.is_used else "deactivated",
                    created_at=invitation.created_at,
                    expires_at=invitation.expires_at,
                    type=CollaboratorType.INVITATION,
                )
            )

        preferred_type_rank = {
            CollaboratorType.USER: 0,
            CollaboratorType.INVITATION: 1,
        }
        collaborator_map: dict[str, CollaboratorItem] = {}

        for collaborator in collaborators:
            email_key = collaborator.email.lower()
            existing = collaborator_map.get(email_key)
            if existing is None:
                collaborator_map[email_key] = collaborator
                continue
            if preferred_type_rank[collaborator.type] < preferred_type_rank[existing.type]:
                collaborator_map[email_key] = collaborator

        return list(collaborator_map.values())

    @staticmethod
    async def update_collaborator_status(
        db: AsyncSession,
        current_user: User,
        collaborator_id: int,
        payload: CollaboratorStatusUpdateRequest,
    ) -> CollaboratorItem:
        if current_user.role not in {"admin", "owner"}:
            raise APIException(status_code=403, message="Only admin or owner can update collaborator status")

        result = await db.execute(
            select(User).where(
                User.id == collaborator_id,
                User.organization_id == current_user.organization_id,
            )
        )
        collaborator = result.scalar_one_or_none()
        if collaborator is None:
            raise APIException(status_code=404, message="Collaborator not found")

        if collaborator.role == "owner":
            raise APIException(status_code=400, message="Cannot change status of owner")

        desired_active = payload.is_active == "activate"
        if collaborator.is_active == desired_active:
            status_text = "active" if desired_active else "deactivated"
            raise APIException(status_code=400, message=f"Collaborator already {status_text}")

        async with transaction(db):
            collaborator.is_active = desired_active
            collaborator.last_active_at = datetime.now(UTC) if desired_active else collaborator.last_active_at
            await db.flush()

        return CollaboratorItem(
            id=collaborator.id,
            unique_key=f"user:{collaborator.id}",
            email=collaborator.email,
            first_name=collaborator.first_name,
            last_name=collaborator.last_name,
            role_type=collaborator.role,
            is_active=collaborator.is_active,
            status="active" if collaborator.is_active else "deactivated",
            created_at=collaborator.created_at,
            last_active_at=collaborator.last_active_at,
            type=CollaboratorType.USER,
        )

    @staticmethod
    async def update_collaborator_role(
        db: AsyncSession,
        current_user: User,
        collaborator_id: int,
        payload: CollaboratorRoleUpdateRequest,
    ) -> None:
        if current_user.role not in {"admin", "owner"}:
            raise APIException(status_code=403, message="Only admin or owner can update collaborator role")

        result = await db.execute(
            select(User).where(
                User.id == collaborator_id,
                User.organization_id == current_user.organization_id,
            )
        )
        collaborator = result.scalar_one_or_none()
        if collaborator is None:
            raise APIException(status_code=404, message="Collaborator not found")

        if collaborator.role == "owner":
            raise APIException(status_code=400, message="Cannot change role of owner")

        desired_role = payload.role_type
        if collaborator.role == desired_role:
            raise APIException(status_code=400, message="Collaborator already has this role")

        async with transaction(db):
            collaborator.role = desired_role
            await db.flush()

    @staticmethod
    async def resend_invitation(
        db: AsyncSession,
        current_user: User,
        invitation_id: int,
    ) -> None:
        result = await db.execute(
            select(Invitation).where(
                Invitation.id == invitation_id,
                Invitation.inviter_user_id == current_user.id,
            )
        )
        invitation = result.scalar_one_or_none()
        if invitation is None:
            raise APIException(status_code=404, message="Invitation not found")

        if invitation.is_used:
            raise APIException(status_code=400, message="Invitation already used")
        if invitation.expires_at <= datetime.now(UTC):
            raise APIException(status_code=400, message="Invitation already expired")

        inviter_name = " ".join(
            [name for name in [current_user.first_name, current_user.last_name] if name]
        ).strip() or current_user.email
        role_label = "Administrator" if invitation.role == "admin" else "Operator"

        await email_service.send_invitation_email(
            invitee_email=invitation.email,
            inviter_name=inviter_name,
            company_name=current_user.company_name or "",
            role_label=role_label,
            expires_at=invitation.expires_at,
            ttl_days=INVITATION_TTL_DAYS,
            support_email=settings.ADMIN_EMAIL,
        )


client_invitation_service = ClientInvitationService()
