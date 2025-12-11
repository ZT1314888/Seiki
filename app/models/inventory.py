from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint

from .base import BaseModel


class InventoryFace(BaseModel):
    __tablename__ = "billboard"
    __table_args__ = (
        UniqueConstraint("organization_id", "face_id", name="uq_billboard_org_face_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    face_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    billboard_type = Column(String(100), nullable=False)
    billboard_type_source = Column(String(50), nullable=False, server_default="preset")
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
    avg_daily_gross_contacts = Column(Float, nullable=False, server_default="0")
    daily_frequency = Column(Float, nullable=False, server_default="2.15")
    h3_index = Column(String(20), nullable=True, index=True)


# Backward compatibility alias for legacy imports.
InventoryBillboard = InventoryFace
