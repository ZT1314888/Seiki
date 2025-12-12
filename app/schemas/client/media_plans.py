from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseResponseSchema, BaseSchema
from app.schemas.client.campaigns import CampaignResponse


class MediaPlanCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255, description="Media Plan Name")
    description: Optional[str] = Field(default=None, description="Media Plan description")
    budget: Decimal = Field(..., gt=0, description="Budget amount")
    action: str = Field(default="publish", description="Action to perform (default publish)")
    campaign_id: int = Field(..., ge=1, description="Campaign ID this media plan is based on")


class MediaPlanResponse(BaseResponseSchema):
    name: str
    description: Optional[str] = None
    budget: Decimal
    action: str
    user_id: int
    organization_id: int
    campaign_id: int
    campaign_start_date: datetime
    campaign_end_date: datetime
    campaign: CampaignResponse | None = None
