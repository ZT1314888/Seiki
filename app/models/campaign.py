from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    JSON,
    ForeignKey,
    TIMESTAMP,
)

from .base import BaseModel


class Campaign(BaseModel):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    budget = Column(Numeric(18, 2), nullable=False)
    start_date = Column(TIMESTAMP(timezone=True), nullable=False)
    end_date = Column(TIMESTAMP(timezone=True), nullable=False)
    status = Column(String(50), nullable=False, default="draft")
    time_unit = Column(String(20), nullable=False, default="day")
    week_1st = Column(String(50), nullable=True)
    selected_dates = Column(JSON, nullable=True)
    kpi_start_date = Column(TIMESTAMP(timezone=True), nullable=True)
    kpi_end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    hour_range = Column(JSON, nullable=False, default=list)
    countries = Column(JSON, nullable=False, default=list)
    cities = Column(JSON, nullable=False, default=list)
    gender = Column(String(50), nullable=True)
    age_groups = Column(JSON, nullable=False, default=list)
    spc_category = Column(String(50), nullable=True)
    mobility_modes = Column(JSON, nullable=False, default=list)
    poi_categories = Column(JSON, nullable=False, default=list)
    billboard_ids = Column(JSON, nullable=False)
    inventory_ids = Column(JSON, nullable=False)
    billboards_tree = Column(JSON, nullable=True)
    billboard_kpi_data = Column(JSON, nullable=True)
    kpi_data = Column(JSON, nullable=True)
    kpi_full_data = Column(JSON, nullable=True)
    audience_breakdown = Column(JSON, nullable=True)
    customize_kpis = Column(JSON, nullable=True)
    operator_first_name = Column(String(100), nullable=True)
    operator_last_name = Column(String(100), nullable=True)
