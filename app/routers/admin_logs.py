# from fastapi import APIRouter, Depends, Query

# from app.core.database import (
#     activity_logs_collection,
#     users_collection,
#     users_collection,
#     events_collection,
#     photos_collection
# )

# from app.dependencies.auth import require_role
# from app.models.users import UserRole


# router = APIRouter(
#     prefix="/admin/activities",
#     tags=["Admin"]
# )


# def get_user_name(user_id: str | None):

#     if not user_id:
#         return "Système"

#     user = users_collection.find_one({
#         "_id": __import__("bson").ObjectId(user_id)
#     })

#     if not user:
#         return "Utilisateur"

#     firstname = user.get("firstname", "")
#     lastname = user.get("lastname", "")

#     return f"{firstname} {lastname}".strip()


# def activity_to_response(activity: dict):

#     user_name = get_user_name(
#         activity.get("user_id")
#     )

#     return {
#         "id": str(activity["_id"]),

#         "user_id": activity.get("user_id"),

#         "photographer_id": activity.get(
#             "photographer_id"
#         ),

#         "user_name": user_name,

#         "action": activity.get("action"),

#         "resource": activity.get("resource"),

#         "resource_id": activity.get(
#             "resource_id"
#         ),

#         "description": activity.get(
#             "description"
#         ),

#         "target": activity.get(
#             "target"
#         ),

#         "metadata": activity.get(
#             "metadata",
#             {}
#         ),

#         "created_at": activity.get(
#             "created_at"
#         )
#     }


# @router.get("/recent")
# def get_recent_activities(
#     limit: int = Query(
#         default=10,
#         ge=1,
#         le=50
#     ),

#     current_user=Depends(
#         require_role(UserRole.ADMIN.value)
#     )
# ):

#     activities = (
#         activity_logs_collection
#         .find({})
#         .sort("created_at", -1)
#         .limit(limit)
#     )

#     return {
#         "activities": [
#             activity_to_response(activity)
#             for activity in activities
#         ]
#     }

from fastapi import APIRouter, Depends
from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import (
    activity_logs_collection,
    users_collection,
)
from app.dependencies.auth import require_role
from app.models.users import UserRole


router = APIRouter(
    prefix="/admin/activities",
    tags=["Admin"],
)


def get_user_name(user_id: str | None) -> str:
    """Récupère le nom de l'utilisateur associé à une activité."""

    if not user_id:
        return "Système"

    try:
        object_id = ObjectId(user_id)
    except (InvalidId, TypeError):
        return "Utilisateur"

    user = users_collection.find_one({
        "_id": object_id
    })

    if not user:
        return "Utilisateur"

    firstname = user.get("firstname", "")
    lastname = user.get("lastname", "")

    full_name = f"{firstname} {lastname}".strip()

    return full_name or "Utilisateur"


def activity_to_response(activity: dict) -> dict:
    """Transforme une activité MongoDB en réponse JSON."""

    return {
        "id": str(activity["_id"]),
        "user_id": activity.get("user_id"),
        "photographer_id": activity.get("photographer_id"),
        "user_name": get_user_name(activity.get("user_id")),
        "action": activity.get("action"),
        "resource": activity.get("resource"),
        "resource_id": activity.get("resource_id"),
        "description": activity.get("description"),
        "target": activity.get("target"),
        "metadata": activity.get("metadata") or {},
        "created_at": activity.get("created_at"),
    }


@router.get("/recent")
def get_all_activities(
    current_user=Depends(
        require_role(UserRole.ADMIN.value)
    ),
):
    """
    Retourne toutes les activités enregistrées,
    de la plus récente à la plus ancienne.
    Réservé aux administrateurs.
    """

    activities = (
        activity_logs_collection
        .find({})
        .sort("created_at", -1)
    )

    return {
        "total": activity_logs_collection.count_documents({}),
        "activities": [
            activity_to_response(activity)
            for activity in activities
        ],
    }