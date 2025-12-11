from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import (
    get_billboard_csv_service,
    get_current_user,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.client.inventory import (
    FaceCreateRequest,
    FaceStatus,
    FaceType,
    FaceUpdateRequest,
)
from app.schemas.response import ApiResponse
from app.services.client.inventory import client_inventory_service
from app.services.client.inventory_csv import BillboardCSVService
from app.exceptions.http_exceptions import APIException

router = APIRouter()


def _ensure_not_operator(current_user: User) -> None:
    if current_user.role == "operator":
        raise APIException(status_code=403, message="Operators cannot perform this action")


@router.post("/faces")
async def create_inventory(
    payload: FaceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a face entry in the inventory."""

    _ensure_not_operator(current_user)

    face = await client_inventory_service.create_face(db, payload, current_user)
    return ApiResponse.success(
        message="Face created successfully",
        data=face,
    )


@router.delete("/faces/{face_id}")
async def delete_inventory(
    face_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a face entry by id."""

    _ensure_not_operator(current_user)

    await client_inventory_service.delete_face(db, face_id, current_user)
    return ApiResponse.success(message="Face deleted successfully", data=None)


@router.get("/faces/{face_id}")
async def get_inventory_detail(
    face_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full details for a single face."""

    face = await client_inventory_service.get_face(db, face_id, current_user)
    return ApiResponse.success(
        message="Face detail retrieved successfully",
        data=face,
    )


@router.post("/faces/upload-csv")
async def upload_billboard_csv(
    file: UploadFile = File(...),
    service: BillboardCSVService = Depends(get_billboard_csv_service),
    current_user: User = Depends(get_current_user),
):
    """Bulk create billboards via CSV upload."""

    _ensure_not_operator(current_user)

    result = await service.import_csv(file, current_user)
    return ApiResponse.success(
        message="Billboard CSV processed successfully",
        data=result,
    )


@router.get("/faces")
async def list_inventory(
    page: int = 1,
    per_page: int = 10,
    media_owner_name: str | None = None,
    network_name: str | None = None,
    face_id: str | None = None,
    billboard_type: str | None = None,
    status: FaceStatus | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List faces with optional filters and search."""

    data = await client_inventory_service.list_faces(
        db=db,
        current_user=current_user,
        page=page,
        per_page=per_page,
        media_owner_name=media_owner_name,
        network_name=network_name,
        face_id=face_id,
        billboard_type=billboard_type,
        status=status.value if status else None,
        search=search,
    )
    return ApiResponse.success(
        message="Faces list retrieved successfully",
        data=data,
    )


@router.put("/faces/{face_id}")
async def update_inventory(
    face_id: str,
    payload: FaceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit face details while keeping immutable fields locked."""

    _ensure_not_operator(current_user)

    face = await client_inventory_service.update_face(db, face_id, payload, current_user)
    return ApiResponse.success(
        message="Face updated successfully",
        data=face,
    )


@router.get("/tree")
async def get_all_inventory(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return hierarchical inventory tree grouped by media owner and network."""

    tree = await client_inventory_service.get_inventory_tree(db, current_user)
    return ApiResponse.success(
        message="Inventory tree retrieved successfully",
        data=tree,
    )
