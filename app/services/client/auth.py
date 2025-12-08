import secrets
from datetime import datetime, timedelta, UTC

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthBase
from app.core.config import settings
from app.db.session import transaction
from app.exceptions.http_exceptions import APIException
from app.models.user import User
from app.models.token import Token
from app.schemas.client.auth import (
    RegisterRequest,
    UserResponse,
    OrganizationType,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LogoutRequest,
    UserInfoResponse,
)
from app.services.common.redis import redis_client
from app.services.common.email import email_service


class ClientAuthService(AuthBase):
    PHONE_COUNTRY_CODE_PREFIX = "+"

    @staticmethod
    async def register(db: AsyncSession, payload: RegisterRequest) -> UserResponse:
        """Self-service registration for MO/MA/BA users.

        - Validates password confirmation
        - Creates or updates an inactive user record
        - Generates and sends an email verification code
        """

        if payload.password != payload.confirm_password:
            raise APIException(status_code=400, message="Passwords do not match")

        # Create or update a pending (inactive) user
        async with transaction(db):
            existing_query = select(User).where(User.email == payload.email)
            result = await db.execute(existing_query)
            user = result.scalar_one_or_none()

            # If already verified, do not allow re-registration
            if user is not None and user.is_verified:
                raise APIException(status_code=400, message="Email already registered")

            hashed_password = User.get_password_hash(payload.password)

            if user is None:
                user = User(
                    email=payload.email,
                    hashed_password=hashed_password,
                    first_name=payload.first_name,
                    last_name=payload.last_name,
                    is_active=False,
                    is_verified=False,
                    phone=payload.phone,
                    company_name=payload.company_name,
                    organization_type=payload.organization_type.value,
                    role="owner",
                )
                db.add(user)
            else:
                # Update existing unverified user info and reset password
                user.hashed_password = hashed_password
                user.first_name = payload.first_name
                user.last_name = payload.last_name
                user.phone = payload.phone
                user.company_name = payload.company_name
                user.organization_type = payload.organization_type.value
                user.is_active = False
                user.is_verified = False
                user.role = "owner"

            await db.flush()

        # Generate verification code and send email (after DB transaction commits)
        verification_code = f"{secrets.randbelow(1_000_000):06d}"
        redis_key = f"email_verification:{user.email}"
        await redis_client.set_with_ttl(redis_key, verification_code, 30 * 60)
        # Use SMTP-based email service configured via MAIL_* settings
        await email_service.send_verification_email(
            email=user.email,
            first_name=user.first_name or "",
            verification_code=verification_code,
        )

        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            company_name=user.company_name,
            organization_type=payload.organization_type,
        )

    @staticmethod
    async def verify_email(db: AsyncSession, email: str, code: str) -> UserResponse:
        """Verify email with code and activate user account."""

        redis_key = f"email_verification:{email}"
        stored_code = await redis_client.get(redis_key)
        if not stored_code or stored_code != code:
            raise APIException(status_code=400, message="Invalid or expired verification code")

        async with transaction(db):
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is None:
                raise APIException(status_code=404, message="User not found")

            user.is_active = True
            user.is_verified = True
            await db.flush()

        # Cleanup verification code after successful verification
        await redis_client.delete(redis_key)

    @staticmethod
    async def logout(db: AsyncSession, payload: LogoutRequest) -> None:
        """Invalidate the current refresh token for the user."""

        payload_data = AuthBase.verify_token(payload.refresh_token, scope="refresh")
        if payload_data is None:
            raise APIException(status_code=401, message="Invalid or expired refresh token")

        user_id = payload_data.get("sub")
        if user_id is None:
            raise APIException(status_code=401, message="Invalid refresh token payload")

        result = await db.execute(
            select(Token).where(
                (Token.user_id == int(user_id)) & (Token.is_active == True)
            )
        )
        stored_token = result.scalar_one_or_none()
        if stored_token is None or not AuthBase.verify_token_hash(
            payload.refresh_token, stored_token.token
        ):
            raise APIException(status_code=401, message="Refresh token mismatch")

        async with transaction(db):
            stored_token.is_active = False
            await db.flush()

    @staticmethod
    def _split_phone(phone: str | None) -> tuple[str | None, str | None]:
        if not phone:
            return None, None

        sanitized = phone.strip()
        if not sanitized:
            return None, None

        if " " in sanitized:
            first, rest = sanitized.split(" ", 1)
            if first.startswith(ClientAuthService.PHONE_COUNTRY_CODE_PREFIX):
                return first, rest.strip()
            return None, sanitized

        # No whitespace separator, try to detect prefix like +966123...
        if sanitized.startswith(ClientAuthService.PHONE_COUNTRY_CODE_PREFIX):
            # Heuristic: country code up to 4 chars
            for idx in range(2, min(5, len(sanitized))):
                if sanitized[idx].isdigit() is False:
                    continue
            return sanitized[:4], sanitized[4:]

        return None, sanitized

    @staticmethod
    def get_user_info_payload(user: User) -> UserInfoResponse:
        country_code, phone_number = ClientAuthService._split_phone(user.phone)

        full_phone = None
        if country_code and phone_number:
            full_phone = f"{country_code} {phone_number}".strip()
        elif user.phone:
            full_phone = user.phone.strip()

        full_name = " ".join(filter(None, [user.first_name, user.last_name])) or None

        org_map = {
            "media-owner": "mo",
            "media-agency": "ma",
            "brand-advertiser": "ba",
        }
        user_type = org_map.get(user.organization_type or "", user.organization_type)

        email_verified_at = user.updated_at if user.is_verified else None

        return UserInfoResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            country_code=country_code,
            phone_number=phone_number or user.phone,
            company_name=user.company_name,
            user_type=user_type,
            role_type=user.role,
            full_name=full_name,
            full_phone=full_phone,
            is_verified=bool(user.is_verified),
            email_verified_at=email_verified_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    async def login(db: AsyncSession, payload: LoginRequest) -> TokenResponse:
        """Authenticate client user and issue JWT access token.

        - Validates email/password
        - Ensures user is active and verified
        - Returns a signed JWT access token for client scope
        """

        result = await db.execute(select(User).where(User.email == payload.email))
        user = result.scalar_one_or_none()

        if user is None:
            raise APIException(status_code=400, message="Invalid email or password")

        if not user.verify_password(payload.password):
            raise APIException(status_code=400, message="Invalid email or password")

        if not user.is_active or not user.is_verified:
            raise APIException(status_code=403, message="Account is not activated")

        access_token = AuthBase.create_access_token(subject=str(user.id), scope="client")
        refresh_token = AuthBase.create_refresh_token(subject=str(user.id))

        async with transaction(db):
            await db.execute(
                update(Token)
                .where((Token.user_id == user.id) & (Token.is_active == True))
                .values(is_active=False)
            )

            hashed_token = AuthBase.hash_token(refresh_token)
            token_entry = Token(
                user_id=user.id,
                token=hashed_token,
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                is_active=True,
            )
            db.add(token_entry)
            await db.flush()

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    @staticmethod
    async def refresh_token(db: AsyncSession, payload: RefreshTokenRequest) -> TokenResponse:
        """Refresh access token using a valid refresh token."""

        payload_data = AuthBase.verify_token(payload.refresh_token, scope="refresh")
        if payload_data is None:
            raise APIException(status_code=401, message="Invalid or expired refresh token")

        user_id = payload_data.get("sub")
        if user_id is None:
            raise APIException(status_code=401, message="Invalid refresh token payload")

        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active or not user.is_verified:
            raise APIException(status_code=403, message="Account is not available")

        result = await db.execute(
            select(Token).where(
                (Token.user_id == user.id) & (Token.is_active == True)
            )
        )
        stored_token = result.scalar_one_or_none()
        if stored_token is None or not AuthBase.verify_token_hash(
            payload.refresh_token, stored_token.token
        ):
            raise APIException(status_code=401, message="Invalid or expired refresh token")

        new_access_token = AuthBase.create_access_token(subject=str(user.id), scope="client")
        new_refresh_token = AuthBase.create_refresh_token(subject=str(user.id))

        async with transaction(db):
            stored_token.is_active = False

            hashed_token = AuthBase.hash_token(new_refresh_token)
            new_token_entry = Token(
                user_id=user.id,
                token=hashed_token,
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                is_active=True,
            )
            db.add(new_token_entry)
            await db.flush()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

    @staticmethod
    async def forgot_password(db: AsyncSession, payload: ForgotPasswordRequest) -> None:
        """Send verification code for password reset to user's email."""

        result = await db.execute(select(User).where(User.email == payload.email))
        user = result.scalar_one_or_none()
        if user is None:
            raise APIException(status_code=404, message="User not found")

        if not user.is_active or not user.is_verified:
            raise APIException(status_code=403, message="Account is not activated")

        verification_code = f"{secrets.randbelow(1_000_000):06d}"
        redis_key = f"password_reset:{user.email}"
        await redis_client.set_with_ttl(redis_key, verification_code, 30 * 60)

        await email_service.send_verification_email(
            email=user.email,
            first_name=user.first_name or "",
            verification_code=verification_code,
        )

    @staticmethod
    async def reset_password(db: AsyncSession, payload: ResetPasswordRequest) -> None:
        """Reset user password after verifying email code."""

        if payload.new_password != payload.confirm_password:
            raise APIException(status_code=400, message="Passwords do not match")

        redis_key = f"password_reset:{payload.email}"
        stored_code = await redis_client.get(redis_key)
        if not stored_code or stored_code != payload.code:
            raise APIException(status_code=400, message="Invalid or expired verification code")

        async with transaction(db):
            result = await db.execute(select(User).where(User.email == payload.email))
            user = result.scalar_one_or_none()
            if user is None:
                raise APIException(status_code=404, message="User not found")

            user.hashed_password = User.get_password_hash(payload.new_password)
            await db.flush()

        await redis_client.delete(redis_key)


client_auth_service = ClientAuthService()
