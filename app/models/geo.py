from sqlalchemy import Column, Integer, String

from .base import BaseModel


class GeoDivision(BaseModel):
    __tablename__ = "geo_filter_data"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    division_id = Column(String(36), nullable=False, unique=True, index=True)
    division_name_en = Column(String(255), nullable=False)
    country_code = Column(String(10), nullable=False, index=True)
