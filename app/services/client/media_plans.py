from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import APIException
from app.models.campaign import Campaign
from app.models.media_plan import MediaPlan
from app.models.user import User
from app.schemas.client.campaigns import CampaignResponse
from app.schemas.client.media_plans import MediaPlanCreateRequest, MediaPlanResponse

ALLOWED_MEDIA_PLAN_STATUSES = {"publish", "draft", "active", "deactive", "upcoming"}


class MediaPlanService:
    async def create_media_plan(
        self,
        db: AsyncSession,
        payload: MediaPlanCreateRequest,
        current_user: User,
    ) -> MediaPlanResponse:
        if current_user.role not in {"owner", "admin"}:
            raise APIException(status_code=403, message="Only owners and admins can create media plans")
        if payload.action and payload.action.lower() not in ALLOWED_MEDIA_PLAN_STATUSES:
            raise APIException(status_code=400, message="Invalid media plan status")

        campaign = await self._fetch_campaign(
            db,
            campaign_id=payload.campaign_id,
            organization_id=current_user.organization_id,
        )

        media_plan = MediaPlan(
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            campaign_id=campaign.id,
            name=payload.name,
            description=payload.description,
            budget=Decimal(str(payload.budget)),
            action=payload.action or "publish",
        )

        db.add(media_plan)
        try:
            await db.flush()
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(media_plan)

        return self._build_response(media_plan, campaign)

    def _build_response(
        self,
        media_plan: MediaPlan,
        campaign: Campaign | None = None,
    ) -> MediaPlanResponse:
        campaign_data = None
        if campaign is not None:
            campaign_data = CampaignResponse.model_validate(campaign)

        return MediaPlanResponse(
            id=media_plan.id,
            name=media_plan.name,
            description=media_plan.description,
            budget=media_plan.budget,
            action=media_plan.action,
            user_id=media_plan.user_id,
            organization_id=media_plan.organization_id,
            campaign_id=media_plan.campaign_id,
            campaign_start_date=(campaign.start_date if campaign else None),
            campaign_end_date=(campaign.end_date if campaign else None),
            campaign=campaign_data,
            created_at=media_plan.created_at,
            updated_at=media_plan.updated_at,
        )

    async def list_media_plans(
        self,
        db: AsyncSession,
        current_user: User,
        page: int = 1,
        per_page: int = 10,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if page < 1 or per_page < 1:
            raise APIException(status_code=400, message="Invalid page or per_page parameter")

        query = select(MediaPlan).where(MediaPlan.organization_id == current_user.organization_id)

        if search:
            like_value = f"%{search}%"
            query = query.where(
                or_(
                    MediaPlan.name.ilike(like_value),
                    MediaPlan.description.ilike(like_value),
                )
            )

        if status_filter:
            normalized_status = status_filter.lower()
            if normalized_status not in ALLOWED_MEDIA_PLAN_STATUSES:
                raise APIException(status_code=400, message="Invalid status filter")
            query = query.where(MediaPlan.action == normalized_status)

        if start_date:
            if start_date.tzinfo is None:
                raise APIException(status_code=400, message="start_date must include timezone info")
            query = query.where(MediaPlan.created_at >= start_date)

        if end_date:
            if end_date.tzinfo is None:
                raise APIException(status_code=400, message="end_date must include timezone info")
            query = query.where(MediaPlan.created_at <= end_date)

        if start_date and end_date and end_date < start_date:
            raise APIException(status_code=400, message="end_date cannot be earlier than start_date")

        total_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(total_query)
        last_page = ceil(total / per_page) if per_page > 0 else 0

        if last_page and page > last_page:
            raise APIException(status_code=404, message="Page not found")

        result = await db.execute(
            query.order_by(MediaPlan.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        )
        media_plans: List[MediaPlan] = result.scalars().all()

        campaign_map: Dict[int, Campaign] = {}
        if media_plans:
            campaign_ids = {plan.campaign_id for plan in media_plans}
            campaign_result = await db.execute(
                select(Campaign).where(
                    Campaign.id.in_(campaign_ids),
                    Campaign.organization_id == current_user.organization_id,
                )
            )
            for campaign in campaign_result.scalars().all():
                campaign_map[campaign.id] = campaign

        items = [self._build_response(plan, campaign_map.get(plan.campaign_id)) for plan in media_plans]

        return {
            "items": items,
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": last_page,
            "has_more": page < last_page,
        }

    async def _fetch_campaign(
        self,
        db: AsyncSession,
        campaign_id: int,
        organization_id: int,
    ) -> Campaign:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found or not accessible")
        return campaign


media_plan_service = MediaPlanService()
