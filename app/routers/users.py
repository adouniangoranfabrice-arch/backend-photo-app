from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.core.database import (
    events_collection,
    faces_collection,
    gallery_stats_collection,
    photos_collection,
)
from app.dependencies.auth import get_current_user


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get("/me")
def get_my_profile(
    current_user=Depends(get_current_user)
):
    """Profil de l'utilisateur connecté (sans le mot de passe)."""

    created_at = current_user.get("created_at")

    return {
        "id": str(current_user["_id"]),
        "firstname": current_user.get("firstname"),
        "lastname": current_user.get("lastname"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
        "business_name": current_user.get("business_name"),
        "phone": current_user.get("phone"),
        "city": current_user.get("city"),
        "website": current_user.get("website"),
        "bio": current_user.get("bio"),
        "is_active": current_user.get("is_active", True),
        "created_at": created_at.isoformat() if created_at else None,
    }


def _sum_counts(match: dict) -> int:
    result = list(gallery_stats_collection.aggregate([
        {"$match": match},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}},
    ]))
    return int(result[0]["total"]) if result else 0


@router.get("/me/stats")
def get_my_stats(
    current_user=Depends(get_current_user)
):
    """Statistiques réelles du photographe connecté (tableau de bord)."""

    user_id = str(current_user["_id"])

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    # Événements
    events_total = events_collection.count_documents({"user_id": user_id})
    events_month = events_collection.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": month_start},
    })
    event_ids = [
        str(e["_id"])
        for e in events_collection.find({"user_id": user_id}, {"_id": 1})
    ]

    # Photos + espace utilisé
    photo_filter = {"user_id": user_id, "status": "ACTIVE"}
    photos_total = photos_collection.count_documents(photo_filter)
    photos_week = photos_collection.count_documents({
        **photo_filter,
        "created_at": {"$gte": week_start},
    })
    storage = list(photos_collection.aggregate([
        {"$match": photo_filter},
        {"$group": {"_id": None, "bytes": {"$sum": {"$ifNull": ["$file_size", 0]}}}},
    ]))
    storage_bytes = int(storage[0]["bytes"]) if storage else 0

    # Visages détectés
    faces_total = (
        faces_collection.count_documents({"event_id": {"$in": event_ids}})
        if event_ids else 0
    )

    # Recherches par selfie et téléchargements des invités
    searches = {"user_id": user_id, "type": "FACE_SEARCH"}
    downloads = {"user_id": user_id, "type": "DOWNLOAD"}

    return {
        "events": {"total": events_total, "this_month": events_month},
        "photos": {"total": photos_total, "this_week": photos_week},
        "storage_bytes": storage_bytes,
        "faces": {"total": faces_total},
        "searches": {
            "total": gallery_stats_collection.count_documents(searches),
            "this_month": gallery_stats_collection.count_documents({
                **searches, "created_at": {"$gte": month_start},
            }),
        },
        "downloads": {
            "total": _sum_counts(downloads),
            "this_month": _sum_counts({**downloads, "created_at": {"$gte": month_start}}),
        },
        "generated_at": now.isoformat(),
    }
