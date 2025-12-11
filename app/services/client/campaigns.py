from __future__ import annotations

from math import ceil
from datetime import datetime
from decimal import Decimal
from random import Random
from typing import Dict, List, Sequence

from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.http_exceptions import APIException
from app.models.campaign import Campaign
from app.models.geo import GeoDivision
from app.models.inventory import InventoryBillboard
from app.models.user import User
from app.schemas.client.campaigns import (
    CampaignCreateRequest,
    CampaignKPIData,
    CampaignResponse,
    GeoFilterResponse,
    GeoDivisionResponse,
)

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class GeoFilterService:
    async def list_governorates(
        self,
        db: AsyncSession,
        country_code: str = "KSA",
        current_user: User | None = None,
    ) -> GeoFilterResponse:
        query = (
            select(GeoDivision)
            .where(GeoDivision.country_code == country_code)
            .order_by(GeoDivision.division_name_en.asc())
        )
        result = await db.execute(query)
        divisions: List[GeoDivision] = result.scalars().all()

        items = [GeoDivisionResponse.model_validate(obj) for obj in divisions]

        return GeoFilterResponse(
            items=items,
            total=len(items),
        )


_KPI_FIELDS = (
    "billboard_kpi_data",
    "kpi_full_data",
    "audience_breakdown",
)


class CampaignService:
    @staticmethod
    def _generate_kpi_summary(campaign: Campaign) -> Dict[str, float | int]:
        seed = f"{campaign.id}-{campaign.start_date.isoformat()}-{campaign.end_date.isoformat()}"
        rng = Random(seed)
        coverage = round(rng.uniform(35.0, 95.0), 2)
        frequency = round(rng.uniform(1.0, 5.0), 2)
        gross_contacts = rng.randint(50_000, 500_000)
        net_contacts = int(gross_contacts * rng.uniform(0.45, 0.85))
        return {
            "coverage_percent": coverage,
            "frequency": frequency,
            "gross_contacts": gross_contacts,
            "net_contacts": net_contacts,
        }

    def _build_response(self, campaign: Campaign) -> CampaignResponse:
        summary = self._generate_kpi_summary(campaign)
        response = CampaignResponse.model_validate(campaign)
        sanitized = response.model_copy(update={field: None for field in _KPI_FIELDS})
        return sanitized.model_copy(update={"kpi_data": CampaignKPIData(**summary)})

    @staticmethod
    def _ensure_future_datetime(target: datetime, now_beijing: datetime, field_name: str) -> None:
        target_local = target.astimezone(_BEIJING_TZ)
        if target_local < now_beijing:
            raise APIException(
                status_code=400,
                message=f"{field_name} must be today or a future time in Beijing timezone",
            )

    @staticmethod
    def _determine_status(payload: CampaignCreateRequest, now_beijing: datetime) -> str:
        start_local = payload.start_date.astimezone(_BEIJING_TZ)
        end_local = payload.end_date.astimezone(_BEIJING_TZ)
        if now_beijing < start_local:
            return "upcoming"
        if start_local <= now_beijing <= end_local:
            return "active"
        return "completed"

    async def _ensure_billboards_exist(
        self,
        db: AsyncSession,
        billboard_ids: Sequence[int],
    ) -> None:
        result = await db.execute(
            select(InventoryBillboard.id).where(InventoryBillboard.id.in_(billboard_ids))
        )
        existing_ids = {row[0] for row in result.all()}
        missing = set(billboard_ids) - existing_ids
        if missing:
            raise APIException(
                status_code=400,
                message=f"Billboard IDs not found: {sorted(missing)}",
            )

    async def _normalize_cities(
        self,
        db: AsyncSession,
        cities: List["CitySelection"],
    ) -> List[Dict[str, str]]:
        if not cities:
            return []
        requested_ids = [city.division_id for city in cities]
        result = await db.execute(
            select(GeoDivision).where(GeoDivision.division_id.in_(requested_ids))
        )
        divisions = result.scalars().all()
        division_map = {division.division_id: division for division in divisions}
        missing = [division_id for division_id in requested_ids if division_id not in division_map]
        if missing:
            raise APIException(
                status_code=400,
                message=f"Invalid city selections (not found in geo table): {missing}",
            )
        normalized = [
            {
                "division_id": city_id,
                "division_name_en": division_map[city_id].division_name_en,
            }
            for city_id in requested_ids
        ]
        return normalized

    async def _ensure_unique_campaign(
        self,
        db: AsyncSession,
        payload: CampaignCreateRequest,
        current_user: User,
    ) -> None:
        existing_stmt = select(Campaign.id).where(
            Campaign.user_id == current_user.id,
            Campaign.name == payload.name,
            Campaign.start_date == payload.start_date,
            Campaign.end_date == payload.end_date,
        )
        
        result = await db.execute(existing_stmt)
        exists = result.scalar_one_or_none()
        if exists:
            raise APIException(
                status_code=400,
                message="Campaign with the same name and schedule already exists",
            )

    async def create_campaign(
        self,
        db: AsyncSession,
        payload: CampaignCreateRequest,
        current_user: User,
    ) -> CampaignResponse:
        if current_user.role == "operator":
            raise APIException(status_code=403, message="Operators cannot create campaigns")

        if not payload.billboard_ids:
            raise APIException(status_code=400, message="At least one billboard must be selected")
        if not payload.inventory_ids:
            raise APIException(status_code=400, message="At least one inventory must be selected")

        await self._ensure_billboards_exist(db, payload.billboard_ids)
        await self._ensure_unique_campaign(db, payload, current_user)
        normalized_cities = await self._normalize_cities(db, payload.cities)

        now_beijing = datetime.now(_BEIJING_TZ)
        self._ensure_future_datetime(payload.start_date, now_beijing, "start_date")
        self._ensure_future_datetime(payload.end_date, now_beijing, "end_date")

        if payload.end_date < payload.start_date:
            raise APIException(status_code=400, message="end_date cannot be earlier than start_date")

        computed_status = self._determine_status(payload, now_beijing)

        campaign = Campaign(
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            name=payload.name,
            description=payload.description,
            budget=Decimal(str(payload.budget)),
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=computed_status,
            time_unit=payload.time_unit,
            week_1st=payload.week_1st,
            selected_dates=None,
            kpi_start_date=None,
            kpi_end_date=None,
            hour_range=payload.hour_range,
            countries=payload.countries,
            cities=normalized_cities,
            gender=payload.gender,
            age_groups=payload.age_groups,
            spc_category=payload.spc_category,
            mobility_modes=payload.mobility_modes,
            poi_categories=payload.poi_categories,
            billboard_ids=payload.billboard_ids,
            inventory_ids=payload.inventory_ids,
            billboards_tree=None,
            billboard_kpi_data=None,
            kpi_data=None,
            kpi_full_data=None,
            audience_breakdown=None,
            customize_kpis=None,
            operator_first_name=current_user.first_name,
            operator_last_name=current_user.last_name,
        )

        db.add(campaign)
        try:
            await db.flush()
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(campaign)

        return self._build_response(campaign)

    async def list_campaigns(
        self,
        db: AsyncSession,
        current_user: User,
        page: int = 1,
        per_page: int = 10,
        search: str | None = None,
        status_filter: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Dict[str, Any]:
        if page < 1 or per_page < 1:
            raise APIException(status_code=400, message="Invalid page or per_page parameter")

        query = select(Campaign).where(Campaign.organization_id == current_user.organization_id)
        if search:
            like_value = f"%{search}%"
            query = query.where(
                or_(
                    Campaign.name.ilike(like_value),
                    Campaign.description.ilike(like_value),
                )
            )
        if status_filter:
            allowed_status = {"upcoming", "active", "completed"}
            normalized_status = status_filter.lower()
            if normalized_status not in allowed_status:
                raise APIException(status_code=400, message="Invalid status filter")
            query = query.where(Campaign.status == normalized_status)
        if start_date:
            if start_date.tzinfo is None:
                raise APIException(status_code=400, message="start_date must include timezone info")
            query = query.where(Campaign.start_date >= start_date)
        if end_date:
            if end_date.tzinfo is None:
                raise APIException(status_code=400, message="end_date must include timezone info")
            query = query.where(Campaign.end_date <= end_date)
        if start_date and end_date and end_date < start_date:
            raise APIException(status_code=400, message="end_date cannot be earlier than start_date")

        total_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(total_query)
        last_page = ceil(total / per_page) if per_page > 0 else 0

        if last_page and page > last_page:
            raise APIException(status_code=404, message="Page not found")

        result = await db.execute(
            query.order_by(Campaign.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        )
        campaigns = result.scalars().all()
        items = [self._build_response(c) for c in campaigns]

        return {
            "items": items,
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": last_page,
            "has_more": page < last_page,
        }

    async def get_campaign_detail(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> CampaignResponse:
        query = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")

        return self._build_response(campaign)


geo_filter_service = GeoFilterService()
campaign_service = CampaignService()
