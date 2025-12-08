from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import AuthBase
from app.models.user import User

http_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = AuthBase.verify_token(token, scope="client")
    if not payload:
        raise HTTPException(
            status_code=403,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    user_query = select(User).where(User.id == int(user_id))
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=403, detail="Invalid authentication credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user


async def get_current_client_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract current client user from Bearer token for client APIs.

    This variant uses the raw Authorization header instead of OAuth2PasswordBearer,
    which works better with plain Swagger header input.
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    value = authorization.strip()
    if not value.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = value.split(" ", 1)[1]
    payload = AuthBase.verify_token(token, scope="client")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not available",
        )

    return user