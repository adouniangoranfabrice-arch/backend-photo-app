from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.database import (
    events_collection,
    photos_collection,
    faces_collection,
    gallery_stats_collection,
)
from app.services.face_service import (
    find_matching_photos,
    largest_face_embedding,
)

router = APIRouter(
    prefix="/public",
    tags=["Public"]
)


@router.get("/events/{public_token}")
def get_public_event(
    public_token: str,
    request: Request
):
    # ==============================
    # 1. Rechercher l'événement
    # ==============================

    event = events_collection.find_one({
        "public_token": public_token,
        "is_public": True,
        "status": "ACTIVE"
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable ou non public"
        )

    event_id = str(event["_id"])

    # ==============================
    # 2. URL de la photo de couverture
    # ==============================

    cover_photo_url = None

    if event.get("cover_photo"):

        # Si cover_photo est déjà une URL Cloudinary
        if event["cover_photo"].startswith("http"):
            cover_photo_url = event["cover_photo"]

        # Si elle est encore stockée localement
        else:
            cover_photo_url = (
                str(request.base_url).rstrip("/")
                + event["cover_photo"]
            )

    # ==============================
    # 3. Récupérer les photos
    # ==============================

    photos_cursor = photos_collection.find({
        "event_id": event_id,
        "status": "ACTIVE"
    }).sort([
        # De la première photo importée à la dernière
        ("created_at", 1),
        ("_id", 1),
    ])

    photos = []

    for photo in photos_cursor:

        photos.append({
            "id": str(photo["_id"]),
            "file_url": photo.get("file_url"),
            "thumbnail_url": photo.get("thumbnail_url"),
            "original_name": photo.get("original_name"),
            "width": photo.get("width"),
            "height": photo.get("height"),
            "created_at": photo.get("created_at")
        })

    # ==============================
    # 4. Réponse publique
    # ==============================

    return {
        "id": event_id,
        "name": event["name"],
        "description": event.get("description"),
        "event_type": event["event_type"],
        "event_date": event.get("event_date"),
        "location": event.get("location"),
        "cover_photo": cover_photo_url,
        "public_token": event["public_token"],
        "photos": photos,
        "photos_count": len(photos)
    }


# ============================================================
# RETROUVER SES PHOTOS GRÂCE À UN SELFIE
# ============================================================
#
# Le selfie est analysé en mémoire puis oublié :
# il n'est jamais enregistré (ni sur disque, ni en base, ni sur Cloudinary).
#

SELFIE_MAX_SIZE = 8 * 1024 * 1024  # 8 Mo

SELFIE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


@router.post("/events/{public_token}/face-search")
async def face_search(
    public_token: str,
    selfie: UploadFile = File(...),
):
    # 1. Vérifier l'événement public
    event = events_collection.find_one(
        {
            "public_token": public_token,
            "is_public": True,
            "status": "ACTIVE",
        },
        {"_id": 1, "user_id": 1},
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable ou non public",
        )

    event_id = str(event["_id"])

    # 2. Vérifier le selfie
    if selfie.content_type not in SELFIE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format non autorisé. Utilisez JPG, PNG ou WEBP.",
        )

    content = await selfie.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image vide.",
        )

    if len(content) > SELFIE_MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'image ne doit pas dépasser 8 Mo.",
        )

    # 3. Extraire le visage du selfie (dans un thread : calcul lourd)
    try:
        embedding = await run_in_threadpool(largest_face_embedding, content)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de lire l'image.",
        )

    if embedding is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Aucun visage détecté. Placez votre visage bien en face, "
                "dans un endroit éclairé, puis réessayez."
            ),
        )

    # 4. Comparer avec les visages de l'événement
    matches = await run_in_threadpool(
        find_matching_photos,
        faces_collection=faces_collection,
        event_id=event_id,
        query_embedding=embedding,
    )

    indexed_photos = photos_collection.count_documents({
        "event_id": event_id,
        "status": "ACTIVE",
        "faces_indexed": {"$exists": True},
    })

    # 5. Réponse (uniquement des identifiants de photos, aucun embedding)
    results = sorted(
        (
            {"photo_id": photo_id, "similarity": round(score, 3)}
            for photo_id, score in matches.items()
        ),
        key=lambda item: item["similarity"],
        reverse=True,
    )

    # 6. Statistiques du photographe (aucune donnée du selfie n'est conservée)
    record_gallery_stat(
        event=event,
        stat_type="FACE_SEARCH",
        count=1,
        matches=len(results),
    )

    return {
        "matches": results,
        "count": len(results),
        "indexed_photos": indexed_photos,
    }


def record_gallery_stat(*, event: dict, stat_type: str, count: int, **extra):
    """Enregistre une recherche ou un téléchargement, sans jamais bloquer l'invité."""

    try:
        gallery_stats_collection.insert_one({
            "event_id": str(event["_id"]),
            "user_id": event.get("user_id"),
            "type": stat_type,
            "count": count,
            "created_at": datetime.now(timezone.utc),
            **extra,
        })
    except Exception as exc:  # les statistiques ne doivent jamais casser la galerie
        print(f"[stats] Enregistrement impossible : {exc}", flush=True)


class DownloadStat(BaseModel):
    count: int = Field(ge=1, le=5000)


@router.post(
    "/events/{public_token}/downloads",
    status_code=status.HTTP_204_NO_CONTENT,
)
def track_download(public_token: str, data: DownloadStat):
    """Appelé par la galerie quand un invité télécharge des photos."""

    event = events_collection.find_one(
        {"public_token": public_token, "is_public": True, "status": "ACTIVE"},
        {"_id": 1, "user_id": 1},
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable ou non public",
        )

    record_gallery_stat(event=event, stat_type="DOWNLOAD", count=data.count)
