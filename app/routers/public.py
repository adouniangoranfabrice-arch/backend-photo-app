# from fastapi import (
#     APIRouter,
#     HTTPException,
#     Request,
#     status
# )

# from app.core.database import events_collection


# router = APIRouter(
#     prefix="/public",
#     tags=["Public"]
# )


# @router.get(
#     "/events/{public_token}"
# )
# def get_public_event(
#     public_token: str,
#     request: Request
# ):

#     event = events_collection.find_one({
#         "public_token": public_token,
#         "is_public": True,
#         "status": "ACTIVE"
#     })


#     if not event:

#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Événement introuvable ou non public"
#         )


#     cover_photo_url = None


#     if event.get("cover_photo"):

#         cover_photo_url = (
#             str(request.base_url).rstrip("/")
#             + event["cover_photo"]
#         )


#     return {
#         "id": str(event["_id"]),

#         "name": event["name"],

#         "description": event.get(
#             "description"
#         ),

#         "event_type": event["event_type"],

#         "event_date": event.get(
#             "event_date"
#         ),

#         "location": event.get(
#             "location"
#         ),

#         "cover_photo": cover_photo_url,

#         "public_token": event["public_token"]
#     }

from fastapi import APIRouter, HTTPException, Request, status
from app.core.database import (
    events_collection,
    photos_collection
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
    }).sort(
        "created_at",
        -1
    )

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