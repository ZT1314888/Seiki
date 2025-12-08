from enum import Enum
from datetime import datetime
from typing import List

from pydantic import Field

from ..base import BaseSchema


class FaceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class IndoorOption(str, Enum):
    YES = "Yes"
    NO = "No"


class BillboardType(str, Enum):
    DIGITAL_BRIDGES = "digital-bridges"
    MAXI_BILLBOARDS = "maxi-billboards"
    DIGITAL_SCREENS = "digital-screens"


class FaceCreateRequest(BaseSchema):
    face_id: str = Field(..., min_length=1)
    billboard_type: BillboardType
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


class FaceUpdateRequest(BaseSchema):
    billboard_type: BillboardType
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


class FaceResponse(BaseSchema):
    id: int
    face_id: str
    billboard_type: str
    is_indoor: IndoorOption
    latitude: float
    longitude: float
    address: str | None = None
    height_from_ground: float | None = None
    azimuth_from_north: float
    width: float
    height: float
    status: FaceStatus
    network_name: str
    media_owner_name: str
    loop_timing: int | None = None
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


InventoryTreeNode.model_rebuild()
