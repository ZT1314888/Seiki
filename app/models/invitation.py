from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func

from .base import BaseModel


class Invitation(BaseModel):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), nullable=False, index=True)
    organization_type = Column(String(50), nullable=True)
    company_name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False)  # "admin" or "operator"
    inviter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)  # store hashed invite token
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_used = Column(Boolean, nullable=False, default=False)
