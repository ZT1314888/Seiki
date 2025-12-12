from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


class GeoDivisionResponse(BaseSchema):
    division_id: str
    division_name_en: str


class GeoFilterResponse(BaseSchema):
    items: List[GeoDivisionResponse]
    total: int


class CitySelection(BaseSchema):
    division_id: str
    division_name_en: str


class GenderOption(str, Enum):
    ALL = "All"
    MALE = "Male"
    FEMALE = "Female"


class SPCOption(str, Enum):
    CSP_PLUS = "CSP+"
    CSP_MINUS = "CSP-"
    OTHER = "Other"


class MobilityMode(str, Enum):
    DRIVING = "Driving"
    PUBLIC_TRANSIT = "Public Transit"
    WALKING = "Walking"
    CYCLING = "Cycling"


class PoiCategory(str, Enum):
    RETAIL = "Retail"
    FNB = "F&B"
    TRANSIT = "Transit"
    EDUCATION = "Education"
    HEALTHCARE = "Healthcare"


class CampaignCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1)
    description: str | None = None
    budget: float = Field(..., gt=0)
    start_date: datetime
    end_date: datetime
    time_unit: str = Field(default="day")
    week_1st: str | None = None
    hour_range: List[int] = Field(..., min_length=2, max_length=2)
    countries: List[str] = Field(
        default_factory=list,
        description="Country codes or names included in campaign reach",
    )
    cities: List[CitySelection] = Field(
        default_factory=list,
        description="Select governorates returned by GET /api/v1/campaigns/geo-filter-data",
    )
    gender: GenderOption | None = Field(
        default=None,
        description="Audience gender filter (dropdown)",
    )
    age_groups: List[str] = Field(default_factory=list)
    spc_category: SPCOption | None = Field(
        default=None,
        description="Socio-Professional Category (dropdown)",
    )
    mobility_modes: List[MobilityMode] = Field(
        default_factory=list,
        description="Mobility & Mode multi-select",
    )
    poi_categories: List[PoiCategory] = Field(
        default_factory=list,
        description="POI categories multi-select",
    )
    billboard_ids: List[int] = Field(default_factory=list)
    inventory_ids: List[str] = Field(..., min_length=1)
    save_as_draft: bool = Field(default=False, description="When true, campaign is saved as draft")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def ensure_datetime(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    @field_validator("start_date", "end_date")
    @classmethod
    def ensure_timezone(cls, value: datetime | None):
        if value is not None and value.tzinfo is None:
            raise ValueError("Datetime fields must include timezone information")
        return value

    @field_validator("hour_range")
    @classmethod
    def validate_hour_range(cls, value: List[int]):
        if len(value) != 2:
            raise ValueError("hour_range must include [start_hour, end_hour]")
        start, end = value
        if not (0 <= start < 24 and 0 < end <= 24 and start < end):
            raise ValueError("hour_range values must be within 0-24 and start < end")
        return value


class CampaignKPIData(BaseSchema):
    coverage_percent: float
    frequency: float
    gross_contacts: int
    net_contacts: int


class CampaignResponse(BaseSchema):
    id: int
    name: str
    description: str | None = None
    budget: float
    start_date: datetime
    end_date: datetime
    status: str
    time_unit: str
    week_1st: str | None = None
    selected_dates: List[str] | None = None
    kpi_start_date: datetime | None = None
    kpi_end_date: datetime | None = None
    hour_range: List[int]
    countries: List[str]
    cities: List[CitySelection]
    gender: str | None = None
    age_groups: List[str]
    spc_category: str | None = None
    mobility_modes: List[str]
    poi_categories: List[str]
    billboard_ids: List[int]
    inventory_ids: List[str]
    billboards_tree: Dict[str, Any] | List[Any] | None = None
    billboard_kpi_data: List[Dict[str, Any]] | None = None
    kpi_data: CampaignKPIData | None = None
    kpi_full_data: Dict[str, Any] | None = None
    audience_breakdown: Dict[str, Any] | None = None
    customize_kpis: List[str] | None = None
    operator_first_name: str | None = None
    operator_last_name: str | None = None
    created_at: datetime
    updated_at: datetime

