from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthBase
from app.db.session import get_db
from app.models.user import User
from app.repositories.inventory import InventoryRepository
from app.services.client.inventory_csv import BillboardCSVService

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


async def get_inventory_repository(
    db: AsyncSession = Depends(get_db),
) -> InventoryRepository:
    return InventoryRepository(db)


async def get_billboard_csv_service(
    repository: InventoryRepository = Depends(get_inventory_repository),
    db: AsyncSession = Depends(get_db),
) -> BillboardCSVService:
    return BillboardCSVService(repository=repository, db=db)


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