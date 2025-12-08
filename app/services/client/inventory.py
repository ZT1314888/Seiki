from collections import defaultdict
from math import ceil
from typing import Dict, List

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import transaction
from app.exceptions.http_exceptions import APIException
from app.models.inventory import InventoryFace
from app.models.user import User
from app.schemas.client.inventory import (
    FaceCreateRequest,
    FaceResponse,
    FaceUpdateRequest,
    InventoryTreeResponse,
    InventoryTreeNode,
    InventoryNodeType,
)


class ClientInventoryService:
    @staticmethod
    async def create_face(
        db: AsyncSession,
        payload: FaceCreateRequest,
        current_user: User | None = None,
    ) -> FaceResponse:
        existing_query = select(InventoryFace).where(InventoryFace.face_id == payload.face_id)
        result = await db.execute(existing_query)
        if result.scalar_one_or_none() is not None:
            raise APIException(status_code=400, message="Face ID already exists")

        async with transaction(db):
            face = InventoryFace(
                face_id=payload.face_id,
                billboard_type=payload.billboard_type,
                latitude=payload.latitude,
                longitude=payload.longitude,
                height_from_ground=payload.height_from_ground,
                loop_timing=payload.loop_timing,
                address=payload.address,
                is_indoor=payload.is_indoor.value,
                azimuth_from_north=payload.azimuth_from_north,
                width=payload.width,
                height=payload.height,
                media_owner_name=payload.media_owner_name,
                network_name=payload.network_name,
                status=payload.status.value,
            )
            db.add(face)
            await db.flush()
            await db.refresh(face)

        return FaceResponse.model_validate(face)

    @staticmethod
    async def delete_face(
        db: AsyncSession,
        face_id: int,
        current_user: User | None = None,
    ) -> None:
        result = await db.execute(
            select(InventoryFace).where(InventoryFace.id == face_id)
        )
        face = result.scalar_one_or_none()
        if face is None:
            raise APIException(status_code=404, message="Face not found")

        async with transaction(db):
            await db.delete(face)
            await db.flush()

    @staticmethod
    async def update_face(
        db: AsyncSession,
        face_id: int,
        payload: FaceUpdateRequest,
        current_user: User | None = None,
    ) -> FaceResponse:
        result = await db.execute(
            select(InventoryFace).where(InventoryFace.id == face_id)
        )
        face = result.scalar_one_or_none()
        if face is None:
            raise APIException(status_code=404, message="Face not found")

        async with transaction(db):
            face.billboard_type = payload.billboard_type.value
            face.latitude = payload.latitude
            face.longitude = payload.longitude
            face.height_from_ground = payload.height_from_ground
            face.loop_timing = payload.loop_timing
            face.address = payload.address
            face.is_indoor = payload.is_indoor.value
            face.azimuth_from_north = payload.azimuth_from_north
            face.width = payload.width
            face.height = payload.height
            face.network_name = payload.network_name
            face.status = payload.status.value
            await db.flush()
            await db.refresh(face)

        return FaceResponse.model_validate(face)

    @staticmethod
    async def get_face(
        db: AsyncSession,
        face_id: int,
    ) -> FaceResponse:
        result = await db.execute(
            select(InventoryFace).where(InventoryFace.id == face_id)
        )
        face = result.scalar_one_or_none()
        if face is None:
            raise APIException(status_code=404, message="Face not found")

        return FaceResponse.model_validate(face)

    @staticmethod
    async def get_inventory_tree(db: AsyncSession) -> InventoryTreeResponse:
        result = await db.execute(select(InventoryFace))
        faces: List[InventoryFace] = result.scalars().all()

        media_owner_groups: Dict[str, List[InventoryFace]] = defaultdict(list)
        for face in faces:
            media_owner_groups[face.media_owner_name].append(face)

        tree_nodes: List[InventoryTreeNode] = []

        for media_owner, faces_under_owner in media_owner_groups.items():
            network_groups: Dict[str, List[InventoryFace]] = defaultdict(list)
            for face in faces_under_owner:
                network_groups[face.network_name].append(face)

            network_nodes: List[InventoryTreeNode] = []
            for network_name, faces_under_network in network_groups.items():
                billboard_children: List[InventoryTreeNode] = []
                for face in faces_under_network:
                    billboard_children.append(
                        InventoryTreeNode(
                            id=f"billboard-{face.id}",
                            name=face.face_id,
                            type=InventoryNodeType.BILLBOARD,
                            billboard_id=face.id,
                            face_id=face.face_id,
                            count=0,
                            media_owner_name=face.media_owner_name,
                            network_name=face.network_name,
                            children=[],
                            billboard_data=FaceResponse.model_validate(face),
                        )
                    )

                network_nodes.append(
                    InventoryTreeNode(
                        id=f"network-{media_owner}-{network_name}",
                        name=network_name,
                        type=InventoryNodeType.NETWORK,
                        billboard_id=None,
                        face_id=None,
                        count=len(billboard_children),
                        media_owner_name=media_owner,
                        network_name=network_name,
                        children=billboard_children,
                        billboard_data=None,
                    )
                )

            tree_nodes.append(
                InventoryTreeNode(
                    id=f"media-owner-{media_owner}",
                    name=media_owner,
                    type=InventoryNodeType.MEDIA_OWNER,
                    billboard_id=None,
                    face_id=None,
                    count=sum(node.count for node in network_nodes) or len(network_nodes),
                    media_owner_name=None,
                    network_name=None,
                    children=network_nodes,
                    billboard_data=None,
                )
            )

        return InventoryTreeResponse(tree=tree_nodes, total_count=len(faces))

    @staticmethod
    async def list_faces(
        db: AsyncSession,
        page: int = 1,
        per_page: int = 10,
        media_owner_name: str | None = None,
        network_name: str | None = None,
        face_id: str | None = None,
        billboard_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> Dict:
        if page < 1 or per_page < 1:
            raise APIException(status_code=400, message="Invalid page or per_page parameter")

        query = select(InventoryFace)

        if media_owner_name:
            query = query.where(InventoryFace.media_owner_name == media_owner_name)
        if network_name:
            query = query.where(InventoryFace.network_name == network_name)
        if face_id:
            query = query.where(InventoryFace.face_id == face_id)
        if billboard_type:
            query = query.where(InventoryFace.billboard_type == billboard_type)
        if status:
            query = query.where(InventoryFace.status == status)

        if search:
            like_value = f"%{search}%"
            query = query.where(
                or_(
                    InventoryFace.face_id.ilike(like_value),
                    InventoryFace.media_owner_name.ilike(like_value),
                    InventoryFace.network_name.ilike(like_value),
                )
            )

        total_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(total_query)

        last_page = ceil(total / per_page) if per_page > 0 else 0
        if last_page and page > last_page:
            raise APIException(status_code=404, message="Page not found")

        result = await db.execute(
            query.offset((page - 1) * per_page).limit(per_page)
        )
        faces = result.scalars().all()
        items = [FaceResponse.model_validate(face) for face in faces]

        return {
            "items": items,
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": last_page,
            "has_more": page < last_page,
        }


client_inventory_service = ClientInventoryService()
