# from fastapi import APIRouter, Depends

# from app.dependencies.auth import require_role
# from app.models.users import UserRole


# router = APIRouter(
#     prefix="/photographers",
#     tags=["Photographers"]
# )


# @router.get("/dashboard")
# def photographer_dashboard(
#     current_user=Depends(
#         require_role(UserRole.PHOTOGRAPHER.value)
#     )
# ):
#     return {
#         "message": "Bienvenue dans votre espace photographe",
#         "user_id": str(current_user["_id"]),
#         "role": current_user["role"]
#     }

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import photographers_collection
from app.dependencies.auth import require_role
from app.models.users import UserRole
from app.schemas.photographer import (
    PhotographerCreate,
    PhotographerUpdate,
    PhotographerResponse,
)


router = APIRouter(
    prefix="/photographers",
    tags=["Photographers"]
)

# Créer profil
@router.post(
    "/profile",
    response_model=PhotographerResponse,
    status_code=status.HTTP_201_CREATED
)
def create_photographer_profile(
    data: PhotographerCreate,
    current_user=Depends(
        require_role(UserRole.PHOTOGRAPHER.value)
    )
):

    user_id = str(current_user["_id"])

    # Vérifier si le profil existe déjà
    existing_profile = photographers_collection.find_one({
        "user_id": user_id
    })

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous avez déjà un profil photographe"
        )

    now = datetime.now(timezone.utc)

    photographer = {
        "user_id": user_id,
        "business_name": data.business_name,
        "bio": data.bio,
        "profile_photo": None,
        "city": data.city,
        "phone": data.phone,
        "website": data.website,
        "is_verified": False,
        "created_at": now,
        "updated_at": now
    }

    result = photographers_collection.insert_one(
        photographer
    )

    return {
        "id": str(result.inserted_id),
        "user_id": user_id,
        "business_name": photographer["business_name"],
        "bio": photographer["bio"],
        "profile_photo": photographer["profile_photo"],
        "city": photographer["city"],
        "phone": photographer["phone"],
        "website": photographer["website"],
        "is_verified": photographer["is_verified"],
        "created_at": photographer["created_at"],
        "updated_at": photographer["updated_at"]
    }

# Récupérer profil
@router.get(
    "/me",
    response_model=PhotographerResponse
)
def get_my_photographer_profile(
    current_user=Depends(
        require_role(UserRole.PHOTOGRAPHER.value)
    )
):

    user_id = str(current_user["_id"])

    photographer = photographers_collection.find_one({
        "user_id": user_id
    })

    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )

    return {
        "id": str(photographer["_id"]),
        "user_id": photographer["user_id"],
        "business_name": photographer.get("business_name"),
        "bio": photographer.get("bio"),
        "profile_photo": photographer.get("profile_photo"),
        "city": photographer.get("city"),
        "phone": photographer.get("phone"),
        "website": photographer.get("website"),
        "is_verified": photographer.get("is_verified", False),
        "created_at": photographer["created_at"],
        "updated_at": photographer["updated_at"]
    }

# Modifier
@router.put(
    "/me",
    response_model=PhotographerResponse
)
def update_my_photographer_profile(
    data: PhotographerUpdate,
    current_user=Depends(
        require_role(UserRole.PHOTOGRAPHER.value)
    )
):

    user_id = str(current_user["_id"])

    photographer = photographers_collection.find_one({
        "user_id": user_id
    })

    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )

    update_data = {
        "business_name": data.business_name,
        "bio": data.bio,
        "city": data.city,
        "phone": data.phone,
        "website": data.website,
        "updated_at": datetime.now(timezone.utc)
    }

    photographers_collection.update_one(
        {
            "_id": photographer["_id"]
        },
        {
            "$set": update_data
        }
    )

    updated = photographers_collection.find_one({
        "_id": photographer["_id"]
    })

    return {
        "id": str(updated["_id"]),
        "user_id": updated["user_id"],
        "business_name": updated.get("business_name"),
        "bio": updated.get("bio"),
        "profile_photo": updated.get("profile_photo"),
        "city": updated.get("city"),
        "phone": updated.get("phone"),
        "website": updated.get("website"),
        "is_verified": updated.get("is_verified", False),
        "created_at": updated["created_at"],
        "updated_at": updated["updated_at"]
    }

# Supprimer
@router.delete(
    "/me",
    status_code=status.HTTP_200_OK
)
def delete_my_photographer_profile(
    current_user=Depends(
        require_role(UserRole.PHOTOGRAPHER.value)
    )
):

    user_id = str(current_user["_id"])

    result = photographers_collection.delete_one({
        "user_id": user_id
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )

    return {
        "message": "Profil photographe supprimé avec succès"
    }