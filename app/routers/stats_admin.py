from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Query

from app.core.database import (
    database,
    events_collection,
    faces_collection,
    gallery_stats_collection,
    photos_collection,
    users_collection,
)
from app.dependencies.auth import require_role
from app.models.users import UserRole


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

admin_only = Depends(require_role(UserRole.ADMIN.value))

MONTHS_FR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]

EVENT_TYPE_LABELS = {
    "WEDDING": "Mariage",
    "BIRTHDAY": "Anniversaire",
    "BAPTISM": "Baptême",
    "CONCERT": "Concert",
    "CONFERENCE": "Conférence",
    "CORPORATE": "Entreprise",
    "GRADUATION": "Remise de diplômes",
    "SPORT": "Sport",
    "OTHER": "Autre",
}


@router.get("/stats")
def get_stats(current_user=admin_only):
    photographers_count = database["users"].count_documents({
        "role": "PHOTOGRAPHER"
    })

    events_count = database["events"].count_documents({})

    photos_count = database["photos"].count_documents({})

    return {
        "photographers": photographers_count,
        "events": events_count,
        "photos": photos_count
    }


# ---------------------------------------------------------------------
# Rapports
# ---------------------------------------------------------------------

def _month_start(now: datetime, months_back: int) -> datetime:
    """Premier jour du mois, `months_back` mois avant le mois courant."""
    year, month = now.year, now.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _monthly_counts(collection, since: datetime, match: dict | None = None) -> dict:
    """{(année, mois): nombre} pour les documents créés depuis `since`."""
    rows = collection.aggregate([
        {"$match": {**(match or {}), "created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"y": {"$year": "$created_at"}, "m": {"$month": "$created_at"}},
            "n": {"$sum": 1},
        }},
    ])
    return {(r["_id"]["y"], r["_id"]["m"]): r["n"] for r in rows}


def _sum_count(match: dict) -> int:
    rows = list(gallery_stats_collection.aggregate([
        {"$match": match},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}},
    ]))
    return int(rows[0]["total"]) if rows else 0


@router.get("/reports")
def get_reports(
    months: int = Query(default=12, ge=3, le=24),
    current_user=admin_only,
):
    """Rapport global de la plateforme (données réelles). Réservé aux administrateurs."""

    now = datetime.now(timezone.utc)
    month_start = _month_start(now, 0)
    since = _month_start(now, months - 1)

    photographer = {"role": UserRole.PHOTOGRAPHER.value}

    # --- Indicateurs clés -------------------------------------------
    photographers_total = users_collection.count_documents(photographer)
    photographers_active = users_collection.count_documents({**photographer, "is_active": True})
    photographers_month = users_collection.count_documents({**photographer, "created_at": {"$gte": month_start}})

    events_total = events_collection.count_documents({})
    events_month = events_collection.count_documents({"created_at": {"$gte": month_start}})
    events_public = events_collection.count_documents({"is_public": True})

    photo_filter = {"status": "ACTIVE"}
    photos_total = photos_collection.count_documents(photo_filter)
    photos_month = photos_collection.count_documents({**photo_filter, "created_at": {"$gte": month_start}})
    storage = list(photos_collection.aggregate([
        {"$match": photo_filter},
        {"$group": {"_id": None, "bytes": {"$sum": {"$ifNull": ["$file_size", 0]}}}},
    ]))
    storage_bytes = int(storage[0]["bytes"]) if storage else 0

    faces_total = faces_collection.estimated_document_count()

    searches_total = gallery_stats_collection.count_documents({"type": "FACE_SEARCH"})
    searches_month = gallery_stats_collection.count_documents({"type": "FACE_SEARCH", "created_at": {"$gte": month_start}})
    downloads_total = _sum_count({"type": "DOWNLOAD"})
    downloads_month = _sum_count({"type": "DOWNLOAD", "created_at": {"$gte": month_start}})

    # --- Croissance mensuelle ---------------------------------------
    users_by_month = _monthly_counts(users_collection, since, photographer)
    events_by_month = _monthly_counts(events_collection, since)
    photos_by_month = _monthly_counts(photos_collection, since, photo_filter)

    growth = []
    for back in range(months - 1, -1, -1):
        start = _month_start(now, back)
        key = (start.year, start.month)
        growth.append({
            "label": MONTHS_FR[start.month - 1],
            "year": start.year,
            "month": start.month,
            "photographers": users_by_month.get(key, 0),
            "events": events_by_month.get(key, 0),
            "photos": photos_by_month.get(key, 0),
        })

    # --- Types d'événements -----------------------------------------
    event_types = [
        {
            "type": row["_id"] or "OTHER",
            "label": EVENT_TYPE_LABELS.get(str(row["_id"] or "OTHER").upper(), str(row["_id"] or "Autre").capitalize()),
            "count": row["n"],
        }
        for row in events_collection.aggregate([
            {"$group": {"_id": "$event_type", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
        ])
    ]

    # --- Photographes les plus actifs (par nombre de photos) ---------
    top_rows = list(photos_collection.aggregate([
        {"$match": photo_filter},
        {"$group": {
            "_id": "$user_id",
            "photos": {"$sum": 1},
            "bytes": {"$sum": {"$ifNull": ["$file_size", 0]}},
            "events": {"$addToSet": "$event_id"},
        }},
        {"$sort": {"photos": -1}},
        {"$limit": 5},
    ]))

    object_ids = []
    for row in top_rows:
        try:
            object_ids.append(ObjectId(row["_id"]))
        except (InvalidId, TypeError):
            pass

    names = {
        str(u["_id"]): (
            f"{u.get('firstname', '')} {u.get('lastname', '')}".strip()
            or u.get("email", "Photographe")
        )
        for u in users_collection.find(
            {"_id": {"$in": object_ids}},
            {"firstname": 1, "lastname": 1, "email": 1},
        )
    }

    top_photographers = [
        {
            "user_id": row["_id"],
            "name": names.get(str(row["_id"]), "Compte supprimé"),
            "photos": row["photos"],
            "events": len(row["events"]),
            "storage_bytes": int(row["bytes"]),
        }
        for row in top_rows
    ]

    return {
        "kpis": {
            "photographers": {"total": photographers_total, "active": photographers_active, "this_month": photographers_month},
            "events": {"total": events_total, "public": events_public, "this_month": events_month},
            "photos": {"total": photos_total, "this_month": photos_month},
            "storage_bytes": storage_bytes,
            "faces": {"total": faces_total},
            "searches": {"total": searches_total, "this_month": searches_month},
            "downloads": {"total": downloads_total, "this_month": downloads_month},
        },
        "growth": growth,
        "event_types": event_types,
        "top_photographers": top_photographers,
        "generated_at": now.isoformat(),
    }


# ---------------------------------------------------------------------
# Gestion des événements (toute la plateforme)
# ---------------------------------------------------------------------

def _count_by_event(collection, event_ids: list[str], match: dict | None = None, field: str | None = None) -> dict:
    """{event_id: total} en une seule requête (somme de `field` ou nombre de documents)."""
    if not event_ids:
        return {}
    rows = collection.aggregate([
        {"$match": {**(match or {}), "event_id": {"$in": event_ids}}},
        {"$group": {"_id": "$event_id", "n": {"$sum": f"${field}" if field else 1}}},
    ])
    return {r["_id"]: int(r["n"]) for r in rows}


@router.get("/events")
def list_all_events(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    search: str = Query(default="", max_length=100),
    visibility: str = Query(default="all", pattern="^(all|public|private)$"),
    current_user=admin_only,
):
    """Liste paginée de tous les événements, avec photographe et statistiques."""

    import re

    from app.core.config import settings

    query: dict = {}

    if visibility == "public":
        query["is_public"] = True
    elif visibility == "private":
        query["is_public"] = False

    term = search.strip()
    if term:
        pattern = {"$regex": re.escape(term), "$options": "i"}
        # Photographes dont le nom ou l'e-mail correspond
        matching_users = [
            str(u["_id"])
            for u in users_collection.find(
                {"$or": [{"firstname": pattern}, {"lastname": pattern}, {"email": pattern}, {"business_name": pattern}]},
                {"_id": 1},
            )
        ]
        query["$or"] = [
            {"name": pattern},
            {"location": pattern},
            {"event_type": pattern},
            {"user_id": {"$in": matching_users}},
        ]

    total = events_collection.count_documents(query)

    events = list(
        events_collection
        .find(query, {
            "user_id": 1, "name": 1, "event_type": 1, "event_date": 1, "location": 1,
            "cover_photo": 1, "public_token": 1, "is_public": 1, "status": 1, "created_at": 1,
        })
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    event_ids = [str(e["_id"]) for e in events]

    photos = _count_by_event(photos_collection, event_ids, {"status": "ACTIVE"})
    faces = _count_by_event(faces_collection, event_ids)
    searches = _count_by_event(gallery_stats_collection, event_ids, {"type": "FACE_SEARCH"})
    downloads = _count_by_event(gallery_stats_collection, event_ids, {"type": "DOWNLOAD"}, field="count")

    # Noms des photographes en une requête
    owner_ids = []
    for e in events:
        try:
            owner_ids.append(ObjectId(e.get("user_id")))
        except (InvalidId, TypeError):
            pass
    owners = {
        str(u["_id"]): {
            "name": f"{u.get('firstname', '')} {u.get('lastname', '')}".strip() or u.get("email", ""),
            "email": u.get("email"),
        }
        for u in users_collection.find({"_id": {"$in": owner_ids}}, {"firstname": 1, "lastname": 1, "email": 1})
    }

    def to_iso(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    items = []
    for e in events:
        event_id = str(e["_id"])
        owner = owners.get(str(e.get("user_id")), {"name": "Compte supprimé", "email": None})
        items.append({
            "id": event_id,
            "name": e.get("name"),
            "event_type": e.get("event_type"),
            "event_date": to_iso(e.get("event_date")),
            "location": e.get("location"),
            "cover_photo": e.get("cover_photo"),
            "is_public": e.get("is_public", True),
            "status": e.get("status", "ACTIVE"),
            "created_at": to_iso(e.get("created_at")),
            "public_url": f"{settings.frontend_base_url}/public/galerie/{e['public_token']}" if e.get("public_token") else None,
            "photographer": {"id": e.get("user_id"), **owner},
            "photos": photos.get(event_id, 0),
            "faces": faces.get(event_id, 0),
            "searches": searches.get(event_id, 0),
            "downloads": downloads.get(event_id, 0),
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
        "events": items,
    }
