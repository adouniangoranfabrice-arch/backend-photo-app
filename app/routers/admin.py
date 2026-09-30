from fastapi import APIRouter, Depends

from app.dependencies.auth import require_role
from app.models.users import UserRole


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


@router.get("/dashboard")
def admin_dashboard(
    current_user=Depends(
        require_role(UserRole.ADMIN.value)
    )
):
    return {
        "message": "Bienvenue dans l'espace administration",
        "user_id": str(current_user["_id"]),
        "role": current_user["role"]
    }