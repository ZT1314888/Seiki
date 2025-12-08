from sqlalchemy import Column, Float, Integer, String

from .base import BaseModel


class InventoryFace(BaseModel):
    __tablename__ = "faces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    face_id = Column(String(100), nullable=False, unique=True, index=True)
    billboard_type = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    height_from_ground = Column(Float, nullable=True)
    loop_timing = Column(Integer, nullable=True)
    address = Column(String(255), nullable=True)
    is_indoor = Column(String(10), nullable=False)
    azimuth_from_north = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    media_owner_name = Column(String(255), nullable=False)
    network_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
