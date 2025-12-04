from ..base import BaseSchema, BaseResponseSchema, add_padded_id
from pydantic import EmailStr, Field, BaseModel
from typing import Optional


class AdminBase(BaseSchema):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None

class AdminCreate(AdminBase):
    password: str


class AdminUpdate(BaseSchema):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None

@add_padded_id()
class AdminResponse(BaseResponseSchema, AdminBase):
    is_active: bool
    padded_id: Optional[str] = None

    @classmethod
    def model_validate(cls, admin):
        return super().model_validate(admin)


class AdminChangePassword(BaseSchema):
    current_password: str
    new_password: str = Field(..., min_length=8)

class ResetPassword(BaseSchema):
    password: str = Field(..., min_length=8)


class AdminFilter(BaseSchema):
    email: Optional[str] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None


class AdminDetailResponse(BaseModel):
    id: int
    role: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    is_active: bool

    class Config:
        from_attributes = True  # 允许从 SQLAlchemy 模型转换