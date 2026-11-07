from fastapi import APIRouter
from app.core.database import database

router = APIRouter(
    prefix="/stats_list_users",
    tags=["Admin"]
)


@router.get("/photographers")
def get_photographers():

    photographers = list(
        database["users"].find(
            {"role": "PHOTOGRAPHER"},
            {
                "_id": 1,
                "firstname": 1,
                "lastname": 1,
                "email": 1,
                "phone": 1,
                "is_active": 1,
                "created_at": 1
            }
        )
    )

    result = []

    for photographer in photographers:

        # ID du user
        user_id = str(photographer["_id"])

        # Profil photographe
        photographer_profile = database["photographers"].find_one({
            "user_id": user_id
        })

        # ID réellement utilisé dans events et photos
        photographer_id = (
            photographer_profile["user_id"]
            if photographer_profile
            else user_id
        )

        # Nombre d'événements
        events_count = database["events"].count_documents({
            "photographer_id": photographer_id
        })

        # Nombre de photos
        photos_count = database["photos"].count_documents({
            "photographer_id": photographer_id
        })

        result.append({
            "id": user_id,

            "firstname": photographer.get("firstname"),
            "lastname": photographer.get("lastname"),
            "email": photographer.get("email"),
            "phone": photographer.get("phone"),
            "is_active": photographer.get("is_active"),

            "business_name": (
                photographer_profile.get("business_name")
                if photographer_profile
                else None
            ),

            "profile_photo": (
                photographer_profile.get("profile_photo")
                if photographer_profile
                else None
            ),

            "city": (
                photographer_profile.get("city")
                if photographer_profile
                else None
            ),

            "is_verified": (
                photographer_profile.get("is_verified", False)
                if photographer_profile
                else False
            ),

            "events_count": events_count,
            "photos_count": photos_count,

            "created_at": photographer.get("created_at")
        })

    return {
        "total": len(result),
        "photographers": result
    }