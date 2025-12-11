from sqlalchemy import Column, Integer, String, ForeignKey

from .base import BaseModel


class Organization(BaseModel):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    organization_type = Column(String(50), nullable=True)
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
