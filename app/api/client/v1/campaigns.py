from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.db.session import get_db
from app.exceptions.http_exceptions import APIException
from app.models.user import User
from app.schemas.client.campaigns import CampaignCreateRequest
from app.schemas.response import ApiResponse
from app.services.client.campaigns import campaign_service, geo_filter_service

router = APIRouter()


@router.get("/geo-filter-data")
async def get_geo_filter_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await geo_filter_service.list_governorates(db=db, current_user=current_user)
    return ApiResponse.success(
        message="Geo filter data retrieved successfully",
        data=data,
    )


@router.post("/create")
async def create_campaign(
    payload: CampaignCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "operator":
        raise APIException(status_code=403, message="Operators cannot create campaigns")

    campaign = await campaign_service.create_campaign(db=db, payload=payload, current_user=current_user)
    return ApiResponse.success(
        message="Campaign created successfully",
        data=campaign,
    )


@router.put("/{campaign_id}")
async def edit_campaign(
    campaign_id: int,
    payload: CampaignCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "operator":
        raise APIException(status_code=403, message="Operators cannot edit campaigns")

    campaign = await campaign_service.edit_campaign(
        db=db,
        campaign_id=campaign_id,
        payload=payload,
        current_user=current_user,
    )
    return ApiResponse.success(
        message="Campaign updated successfully",
        data=campaign,
    )


@router.delete("/{campaign_id}/delete")
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "operator":
        raise APIException(status_code=403, message="Operators cannot delete campaigns")

    await campaign_service.delete_campaign(
        db=db,
        campaign_id=campaign_id,
        current_user=current_user,
    )
    return ApiResponse.success(message="Campaign deleted successfully")


@router.get("/{campaign_id}/detail")
async def get_campaign_detail(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = await campaign_service.get_campaign_detail(db=db, campaign_id=campaign_id, current_user=current_user)
    return ApiResponse.success(
        message="Campaign detail retrieved successfully",
        data=campaign,
    )


@router.get("/{campaign_id}/export/pdf")
async def export_campaign_pdf(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "operator":
        raise APIException(status_code=403, message="Operators cannot export campaigns")

    export = await campaign_service.export_campaign_pdf(
        db=db,
        campaign_id=campaign_id,
        current_user=current_user,
    )
    background_tasks.add_task(export.cleanup)
    return FileResponse(
        path=export.path,
        filename=export.filename,
        media_type="application/pdf",
    )


@router.get("/{campaign_id}/export/csv")
async def export_campaign_csv(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "operator":
        raise APIException(status_code=403, message="Operators cannot export campaigns")

    export = await campaign_service.export_campaign_csv(
        db=db,
        campaign_id=campaign_id,
        current_user=current_user,
    )
    background_tasks.add_task(export.cleanup)
    return FileResponse(
        path=export.path,
        filename=export.filename,
        media_type="text/csv",
    )


@router.get("/faces")
async def list_campaign_faces(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1),
    status_filter: str | None = Query(default=None, description="Filter by status: upcoming/active/completed"),
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

    data = await campaign_service.list_campaigns(
        db=db,
        current_user=current_user,
        page=page,
        per_page=per_page,
        search=search,
        status_filter=status_filter,
        start_date=start_dt,
        end_date=end_dt,
    )
    return ApiResponse.success(
        message="Campaign faces retrieved successfully",
        data=data,
    )
