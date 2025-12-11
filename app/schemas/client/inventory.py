from datetime import datetime
from enum import Enum
from typing import List

from pydantic import Field, field_validator

from ..base import BaseSchema


class FaceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class IndoorOption(str, Enum):
    YES = "Yes"
    NO = "No"


class FaceType(str, Enum):
    DIGITAL_BRIDGES = "digital-bridges"
    MAXI_BILLBOARDS = "maxi-billboards"
    DIGITAL_SCREENS = "digital-screens"


class FaceTypeSource(str, Enum):
    PRESET = "preset"
    OTHER = "other"


class FaceCreateRequest(BaseSchema):
    face_id: str = Field(..., min_length=1)
    billboard_type: FaceType
    billboard_type_source: FaceTypeSource = FaceTypeSource.PRESET
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    height_from_ground: float | None = Field(default=None, ge=0)
    loop_timing: int | None = Field(default=None, ge=0)
    address: str | None = None
    is_indoor: IndoorOption
    azimuth_from_north: float = Field(..., ge=0)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    media_owner_name: str = Field(..., min_length=1)
    network_name: str = Field(..., min_length=1)
    status: FaceStatus = FaceStatus.ACTIVE
    avg_daily_gross_contacts: float = Field(default=0, ge=0)
    daily_frequency: float = Field(default=2.15, ge=0)


class FaceUpdateRequest(BaseSchema):
    billboard_type: FaceType
    billboard_type_source: FaceTypeSource = FaceTypeSource.PRESET
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    height_from_ground: float | None = Field(default=None, ge=0)
    loop_timing: int | None = Field(default=None, ge=0)
    address: str | None = None
    is_indoor: IndoorOption
    azimuth_from_north: float = Field(..., ge=0)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    network_name: str = Field(..., min_length=1)
    status: FaceStatus = FaceStatus.ACTIVE
    avg_daily_gross_contacts: float = Field(default=0, ge=0)
    daily_frequency: float = Field(default=2.15, ge=0)


class FaceResponse(BaseSchema):
    id: int
    face_id: str
    billboard_type: str
    billboard_type_source: str
    is_indoor: IndoorOption
    latitude: float
    longitude: float
    h3_index: str | None = None
    address: str | None = None
    height_from_ground: float | None = None
    azimuth_from_north: float
    width: float
    height: float
    status: FaceStatus
    network_name: str
    media_owner_name: str
    loop_timing: int | None = None
    avg_daily_gross_contacts: float
    daily_frequency: float
    created_at: datetime
    updated_at: datetime


class InventoryNodeType(str, Enum):
    MEDIA_OWNER = "media_owner"
    NETWORK = "network"
    BILLBOARD = "billboard"


class InventoryTreeNode(BaseSchema):
    id: str
    name: str
    type: InventoryNodeType
    billboard_id: int | None = None
    face_id: str | None = None
    count: int
    media_owner_name: str | None = None
    network_name: str | None = None
    children: List["InventoryTreeNode"] = Field(default_factory=list)
    billboard_data: FaceResponse | None = None


class InventoryTreeResponse(BaseSchema):
    tree: List[InventoryTreeNode]
    total_count: int


class BillboardCSVRow(BaseSchema):
    face_id: str
    billboard_type: str
    is_indoor: str
    latitude: float
    longitude: float
    address: str | None = None
    height_from_ground: float | None = None
    azimuth_from_north: float
    width: float
    height: float
    network_name: str
    media_owner_name: str

    @field_validator(
        "face_id",
        "billboard_type",
        "is_indoor",
        "network_name",
        "media_owner_name",
        mode="before",
    )
    @classmethod
    def strip_required(cls, value: str | None):
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @field_validator("address", mode="before")
    @classmethod
    def strip_optional(cls, value: str | None):
        if value is None:
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("height_from_ground", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class BillboardCSVUploadResult(BaseSchema):
    total_rows: int
    created_count: int
    skipped_count: int
    errors: List[str] = Field(default_factory=list)


InventoryTreeNode.model_rebuild()
