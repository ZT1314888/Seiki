from typing import List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryFace


class InventoryRepository:
    """Repository layer for inventory faces."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_existing_face_ids(
        self,
        face_ids: Sequence[str],
        organization_id: int,
    ) -> set[str]:
        if not face_ids:
            return set()
        stmt = (
            select(InventoryFace.face_id)
            .where(InventoryFace.organization_id == organization_id)
            .where(InventoryFace.face_id.in_(face_ids))
        )
        result = await self._db.execute(stmt)
        return {row[0] for row in result.all()}

    async def bulk_create_faces(
        self,
        faces_data: Sequence[dict],
        user_id: int,
        organization_id: int,
    ) -> List[InventoryFace]:
        faces = [
            InventoryFace(user_id=user_id, organization_id=organization_id, **data)
            for data in faces_data
        ]
        self._db.add_all(faces)
        await self._db.flush()
        return faces
