from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.db.session import get_db
from app.exceptions.http_exceptions import APIException
from app.models.user import User
from app.schemas.client.media_plans import MediaPlanCreateRequest
from app.schemas.response import ApiResponse
from app.services.client.media_plans import media_plan_service

router = APIRouter()


@router.post("/create")
async def create_media_plan(
    payload: MediaPlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"owner", "admin"}:
        raise APIException(status_code=403, message="Only owners and admins can create media plans")

    media_plan = await media_plan_service.create_media_plan(
        db=db,
        payload=payload,
        current_user=current_user,
    )
    return ApiResponse.success(
        message="Media plan created successfully",
        data=media_plan,
    )


@router.get("/faces")
async def list_media_plan_faces(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1),
    status: str | None = Query(
        default=None,
        description="Filter by action status: draft/active/deactive/upcoming",
    ),
    start_date: str | None = Query(default=None, description="ISO datetime with timezone"),
    end_date: str | None = Query(default=None, description="ISO datetime with timezone"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise APIException(status_code=400, message=f"{field_name} must be ISO datetime") from exc
        if parsed.tzinfo is None:
            raise APIException(status_code=400, message=f"{field_name} must include timezone info")
        return parsed

    start_dt = _parse_datetime(start_date, "start_date")
    end_dt = _parse_datetime(end_date, "end_date")

    data = await media_plan_service.list_media_plans(
        db=db,
        current_user=current_user,
        page=page,
        per_page=per_page,
        search=search,
        status_filter=status,
        start_date=start_dt,
        end_date=end_dt,
    )
    return ApiResponse.success(
        message="Media plans retrieved successfully",
        data=data,
    )


@router.get("/{media_plan_id}/detail")
async def get_media_plan_detail(
    media_plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media_plan = await media_plan_service.get_media_plan_detail(
        db=db,
        media_plan_id=media_plan_id,
        current_user=current_user,
    )
    return ApiResponse.success(
        message="Media plan detail retrieved successfully",
        data=media_plan,
    )
