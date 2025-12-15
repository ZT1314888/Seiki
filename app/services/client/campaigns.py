from __future__ import annotations

from math import ceil
from datetime import datetime
from decimal import Decimal
from random import Random
from typing import Any, Dict, List, Sequence, TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
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
from app.services.client.campaigns_export import campaign_export_service

if TYPE_CHECKING:
    from app.services.client.campaigns_export import CampaignCSVExport, CampaignPDFExport

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
    def _compute_status_from_datetimes(
        start_date: datetime,
        end_date: datetime,
        now_beijing: datetime,
    ) -> str:
        start_local = start_date.astimezone(_BEIJING_TZ)
        end_local = end_date.astimezone(_BEIJING_TZ)
        if now_beijing < start_local:
            return "upcoming"
        if start_local <= now_beijing <= end_local:
            return "active"
        return "completed"

    def _determine_status(self, payload: CampaignCreateRequest, now_beijing: datetime) -> str:
        return self._compute_status_from_datetimes(payload.start_date, payload.end_date, now_beijing)

    async def _ensure_billboards_belong_to_org(
        self,
        db: AsyncSession,
        billboard_ids: Sequence[int],
        organization_id: int,
    ) -> None:
        if not billboard_ids:
            return
        result = await db.execute(
            select(InventoryBillboard.id, InventoryBillboard.organization_id).where(
                InventoryBillboard.id.in_(billboard_ids)
            )
        )
        rows = result.all()
        existing_ids = {row[0] for row in rows}
        missing = set(billboard_ids) - existing_ids
        if missing:
            raise APIException(
                status_code=400,
                message=f"Billboard IDs not found: {sorted(missing)}",
            )

        unauthorized = sorted([row[0] for row in rows if row[1] != organization_id])
        if unauthorized:
            raise APIException(
                status_code=403,
                message=f"Billboard IDs do not belong to your organization: {unauthorized}",
            )

    async def refresh_campaign_statuses_for_org(
        self,
        db: AsyncSession,
        organization_id: int,
    ) -> int:
        now_beijing = datetime.now(_BEIJING_TZ)
        result = await db.execute(
            select(Campaign).where(
                Campaign.organization_id == organization_id,
                Campaign.status != "draft",
            )
        )
        campaigns = result.scalars().all()
        updated = 0
        for campaign in campaigns:
            next_status = self._compute_status_from_datetimes(
                campaign.start_date,
                campaign.end_date,
                now_beijing,
            )
            if next_status != campaign.status:
                campaign.status = next_status
                updated += 1
        if updated:
            try:
                await db.flush()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        return updated

    async def refresh_all_campaign_statuses(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(Campaign.organization_id)
            .where(Campaign.status != "draft")
            .distinct()
        )
        org_ids = [row[0] for row in result.all()]
        total = 0
        for org_id in org_ids:
            total += await self.refresh_campaign_statuses_for_org(db, org_id)
        return total


    async def export_campaign_pdf(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> CampaignPDFExport:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")
        if campaign.status != "completed":
            raise APIException(status_code=400, message="Only completed campaigns can be exported")

        return await campaign_export_service.export_campaign_pdf(campaign)

    async def export_campaign_csv(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> CampaignCSVExport:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")
        if campaign.status != "completed":
            raise APIException(status_code=400, message="Only completed campaigns can be exported")

        return await campaign_export_service.export_campaign_csv(campaign)

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
        exclude_campaign_id: int | None = None,
    ) -> None:
        existing_stmt = select(Campaign.id).where(
            Campaign.user_id == current_user.id,
            Campaign.name == payload.name,
            Campaign.start_date == payload.start_date,
            Campaign.end_date == payload.end_date,
            Campaign.status != "draft",
        )
        if exclude_campaign_id is not None:
            existing_stmt = existing_stmt.where(Campaign.id != exclude_campaign_id)

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

        is_draft = payload.save_as_draft

        if not payload.inventory_ids:
            raise APIException(status_code=400, message="At least one inventory must be selected")

        if not is_draft and not payload.billboard_ids:
            raise APIException(status_code=400, message="At least one billboard must be selected")

        if payload.billboard_ids:
            await self._ensure_billboards_belong_to_org(
                db,
                payload.billboard_ids,
                current_user.organization_id,
            )

        if not is_draft:
            await self._ensure_unique_campaign(db, payload, current_user)
        normalized_cities = await self._normalize_cities(db, payload.cities)

        now_beijing = datetime.now(_BEIJING_TZ)
        self._ensure_future_datetime(payload.start_date, now_beijing, "start_date")
        self._ensure_future_datetime(payload.end_date, now_beijing, "end_date")

        if payload.end_date < payload.start_date:
            raise APIException(status_code=400, message="end_date cannot be earlier than start_date")

        computed_status = "draft" if is_draft else self._determine_status(payload, now_beijing)

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

    async def delete_campaign(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> None:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")

        if campaign.status != "draft":
            raise APIException(status_code=400, message="Only draft campaigns can be deleted")

        try:
            await db.delete(campaign)
            await db.flush()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    async def edit_campaign(
        self,
        db: AsyncSession,
        campaign_id: int,
        payload: CampaignCreateRequest,
        current_user: User,
    ) -> CampaignResponse:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")

        if campaign.status != "draft":
            raise APIException(status_code=400, message="Only draft campaigns can be edited")

        is_draft = payload.save_as_draft

        if not payload.inventory_ids:
            raise APIException(status_code=400, message="At least one inventory must be selected")
        if not is_draft and not payload.billboard_ids:
            raise APIException(status_code=400, message="At least one billboard must be selected")

        if payload.billboard_ids:
            await self._ensure_billboards_belong_to_org(
                db,
                payload.billboard_ids,
                current_user.organization_id,
            )

        normalized_cities = await self._normalize_cities(db, payload.cities)
        now_beijing = datetime.now(_BEIJING_TZ)

        if not is_draft:
            await self._ensure_unique_campaign(db, payload, current_user, exclude_campaign_id=campaign.id)
            self._ensure_future_datetime(payload.start_date, now_beijing, "start_date")
            self._ensure_future_datetime(payload.end_date, now_beijing, "end_date")
            if payload.end_date < payload.start_date:
                raise APIException(status_code=400, message="end_date cannot be earlier than start_date")
            next_status = self._determine_status(payload, now_beijing)
        else:
            next_status = "draft"

        campaign.name = payload.name
        campaign.description = payload.description
        campaign.budget = Decimal(str(payload.budget))
        campaign.start_date = payload.start_date
        campaign.end_date = payload.end_date
        campaign.status = next_status
        campaign.time_unit = payload.time_unit
        campaign.week_1st = payload.week_1st
        campaign.selected_dates = None
        campaign.kpi_start_date = None
        campaign.kpi_end_date = None
        campaign.hour_range = payload.hour_range
        campaign.countries = payload.countries
        campaign.cities = normalized_cities
        campaign.gender = payload.gender
        campaign.age_groups = payload.age_groups
        campaign.spc_category = payload.spc_category
        campaign.mobility_modes = payload.mobility_modes
        campaign.poi_categories = payload.poi_categories
        campaign.billboard_ids = payload.billboard_ids
        campaign.inventory_ids = payload.inventory_ids
        campaign.billboards_tree = None
        campaign.billboard_kpi_data = None
        campaign.kpi_data = None
        campaign.kpi_full_data = None
        campaign.audience_breakdown = None
        campaign.customize_kpis = None
        campaign.operator_first_name = current_user.first_name
        campaign.operator_last_name = current_user.last_name

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

        await self.refresh_campaign_statuses_for_org(db, current_user.organization_id)

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
        await self.refresh_campaign_statuses_for_org(db, current_user.organization_id)

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
