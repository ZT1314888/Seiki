from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text

from .base import BaseModel


class MediaPlan(BaseModel):
    __tablename__ = "media_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    budget = Column(Numeric(18, 2), nullable=False)
    action = Column(String(50), nullable=False, default="publish")
