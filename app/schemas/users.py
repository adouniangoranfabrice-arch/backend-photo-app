from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.users import UserRole

class UserResponse(BaseModel):
    id: str
    firstname: str
    lastname: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime