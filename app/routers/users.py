from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get("/me")
def get_my_profile(
    current_user=Depends(get_current_user)
):
    return {
        "id": str(current_user["_id"]),
        "firstname": current_user["firstname"],
        "lastname": current_user["lastname"],
        "email": current_user["email"],
        "role": current_user["role"],
    }