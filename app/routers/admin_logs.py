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

from math import ceil

from fastapi import APIRouter, Depends, Query
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


# Champs réellement utilisés : on évite de transférer le reste
ACTIVITY_FIELDS = {
    "user_id": 1,
    "photographer_id": 1,
    "action": 1,
    "resource": 1,
    "resource_id": 1,
    "description": 1,
    "target": 1,
    "metadata": 1,
    "created_at": 1,
}


def get_user_names(user_ids: set[str]) -> dict[str, str]:
    """Récupère les noms de plusieurs utilisateurs en UNE seule requête."""

    object_ids = []
    for user_id in user_ids:
        try:
            object_ids.append(ObjectId(user_id))
        except (InvalidId, TypeError):
            continue

    if not object_ids:
        return {}

    users = users_collection.find(
        {"_id": {"$in": object_ids}},
        {"firstname": 1, "lastname": 1},
    )

    names = {}
    for user in users:
        full_name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
        names[str(user["_id"])] = full_name or "Utilisateur"

    return names


def activity_to_response(activity: dict, names: dict[str, str]) -> dict:
    """Transforme une activité MongoDB en réponse JSON."""

    user_id = activity.get("user_id")

    return {
        "id": str(activity["_id"]),
        "user_id": user_id,
        "photographer_id": activity.get("photographer_id"),
        "user_name": names.get(user_id, "Utilisateur") if user_id else "Système",
        "action": activity.get("action"),
        "resource": activity.get("resource"),
        "resource_id": activity.get("resource_id"),
        "description": activity.get("description"),
        "target": activity.get("target"),
        "metadata": activity.get("metadata") or {},
        "created_at": activity.get("created_at"),
    }


@router.get("/recent")
def get_recent_activities(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    current_user=Depends(
        require_role(UserRole.ADMIN.value)
    ),
):
    """
    Activités de la plateforme, de la plus récente à la plus ancienne,
    paginées côté serveur. Réservé aux administrateurs.
    """

    total = activity_logs_collection.estimated_document_count()

    activities = list(
        activity_logs_collection
        .find({}, ACTIVITY_FIELDS)
        .sort("created_at", -1)   # utilise l'index created_at
        .skip((page - 1) * limit)
        .limit(limit)
    )

    names = get_user_names({
        a["user_id"] for a in activities if a.get("user_id")
    })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, ceil(total / limit)),
        "activities": [
            activity_to_response(activity, names)
            for activity in activities
        ],
    }
