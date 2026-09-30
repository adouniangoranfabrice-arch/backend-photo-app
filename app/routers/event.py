from datetime import datetime, timezone
from pathlib import Path
import secrets
from uuid import uuid4
from app.core.config import settings

from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status
)

from app.core.database import (
    photographers_collection,
    events_collection
)

from app.dependencies.auth import require_role
from app.models.users import UserRole

from app.schemas.event import (
    EventResponse,
    EventUpdate
)


router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


UPLOAD_DIR = Path("uploads/events")

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp"
}

MAX_FILE_SIZE = 10 * 1024 * 1024

def event_to_response(event: dict):

    public_token = event["public_token"]

    return {
        "id": str(event["_id"]),
        "photographer_id": event["photographer_id"],
        "name": event["name"],
        "description": event.get("description"),
        "event_type": event["event_type"],
        "event_date": event.get("event_date"),
        "location": event.get("location"),
        "cover_photo": event.get("cover_photo"),
        "public_token": public_token,
        "public_url": (f"{settings.FRONTEND_URL}/e/{public_token}"),
        "is_public": event.get("is_public", True),
        "status": event.get("status", "ACTIVE"),
        "created_at": event["created_at"],
        "updated_at": event["updated_at"]
    }


# =========================================================
# CRÉER UN ÉVÉNEMENT
# =========================================================

@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_event(

    name: str = Form(...),

    description: str | None = Form(None),

    event_type: str = Form(...),

    event_date: datetime | None = Form(None),

    location: str | None = Form(None),

    is_public: bool = Form(True),

    cover_photo: UploadFile | None = File(None),

    current_user=Depends(
        require_role(
            UserRole.PHOTOGRAPHER.value
        )
    )
):

    # =====================================================
    # RÉCUPÉRER LE PHOTOGRAPHE
    # =====================================================

    user_id = str(
        current_user["_id"]
    )

    photographer = photographers_collection.find_one({
        "user_id": user_id
    })

    if not photographer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )

    photographer_id = str(
        photographer["_id"]
    )

    # =====================================================
    # GESTION DE LA COVER PHOTO
    # =====================================================

    cover_photo_path = None

    if cover_photo:

        # Vérifier le type MIME

        if cover_photo.content_type not in ALLOWED_CONTENT_TYPES:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Format d'image non autorisé. "
                    "Utilisez JPG, JPEG, PNG ou WEBP."
                )
            )

        # Vérifier l'extension

        extension = Path(
            cover_photo.filename or ""
        ).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Extension d'image non autorisée."
            )

        # Lire le fichier

        file_content = await cover_photo.read()

        # Vérifier la taille

        if len(file_content) > MAX_FILE_SIZE:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L'image ne doit pas dépasser 10 MB."
            )

        # Générer un nom unique

        filename = (
            f"{uuid4().hex}"
            f"{extension}"
        )

        # Chemin physique

        file_path = (
            UPLOAD_DIR / filename
        )

        # Sauvegarder l'image

        with open(
            file_path,
            "wb"
        ) as buffer:

            buffer.write(
                file_content
            )

        # Chemin qui sera enregistré dans MongoDB

        cover_photo_path = (
            f"/uploads/events/{filename}"
        )

    # =====================================================
    # TOKEN PUBLIC
    # =====================================================

    public_token = secrets.token_urlsafe(100)

    # =====================================================
    # DATES
    # =====================================================

    now = datetime.now(timezone.utc)

    # =====================================================
    # CRÉER L'ÉVÉNEMENT
    # =====================================================

    event = {

        "photographer_id": photographer_id,

        "name": name,

        "description": description,

        "event_type": event_type,

        "event_date": event_date,

        "location": location,

        "cover_photo": cover_photo_path,

        "public_token": public_token,

        "is_public": is_public,

        "status": "ACTIVE",

        "created_at": now,

        "updated_at": now
    }

    # =====================================================
    # ENREGISTRER DANS MONGODB
    # =====================================================

    result = events_collection.insert_one(
        event
    )

    event["_id"] = result.inserted_id

    return event_to_response(
        event
    )

# =========================================================
# MES ÉVÉNEMENTS
# =========================================================

@router.get(
    "/me",
    response_model=list[EventResponse]
)
def get_my_events(

    current_user=Depends(
        require_role(
            UserRole.PHOTOGRAPHER.value
        )
    )
):

    user_id = str(
        current_user["_id"]
    )


    photographer = photographers_collection.find_one(
        {
            "user_id": user_id
        }
    )


    if not photographer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )


    photographer_id = str(
        photographer["_id"]
    )


    events = events_collection.find(
        {
            "photographer_id": photographer_id
        }
    ).sort(
        "created_at",
        -1
    )


    return [
        event_to_response(event)
        for event in events
    ]


# =========================================================
# RÉCUPÉRER UN ÉVÉNEMENT
# =========================================================

@router.get(
    "/{event_id}",
    response_model=EventResponse
)
def get_event(

    event_id: str,

    current_user=Depends(
        require_role(
            UserRole.PHOTOGRAPHER.value
        )
    )
):

    user_id = str(
        current_user["_id"]
    )


    photographer = photographers_collection.find_one(
        {
            "user_id": user_id
        }
    )


    if not photographer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )


    photographer_id = str(
        photographer["_id"]
    )


    # Vérifier ObjectId

    try:

        object_id = ObjectId(
            event_id
        )

    except Exception:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )


    event = events_collection.find_one(
        {
            "_id": object_id,
            "photographer_id": photographer_id
        }
    )


    if not event:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )


    return event_to_response(
        event
    )


# =========================================================
# MODIFIER UN ÉVÉNEMENT
# =========================================================

@router.put(
    "/{event_id}",
    response_model=EventResponse
)
def update_event(

    event_id: str,

    data: EventUpdate,

    current_user=Depends(
        require_role(
            UserRole.PHOTOGRAPHER.value
        )
    )
):

    user_id = str(
        current_user["_id"]
    )


    photographer = photographers_collection.find_one(
        {
            "user_id": user_id
        }
    )


    if not photographer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )


    photographer_id = str(
        photographer["_id"]
    )


    try:

        object_id = ObjectId(
            event_id
        )

    except Exception:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )


    event = events_collection.find_one(
        {
            "_id": object_id,
            "photographer_id": photographer_id
        }
    )


    if not event:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )


    update_data = data.model_dump(
        exclude_unset=True
    )


    update_data["updated_at"] = (
        datetime.now(timezone.utc)
    )


    events_collection.update_one(
        {
            "_id": object_id,
            "photographer_id": photographer_id
        },
        {
            "$set": update_data
        }
    )


    updated_event = events_collection.find_one(
        {
            "_id": object_id
        }
    )


    return event_to_response(
        updated_event
    )


# =========================================================
# SUPPRIMER UN ÉVÉNEMENT
# =========================================================

@router.delete(
    "/{event_id}"
)
def delete_event(

    event_id: str,

    current_user=Depends(
        require_role(
            UserRole.PHOTOGRAPHER.value
        )
    )
):

    user_id = str(
        current_user["_id"]
    )


    photographer = photographers_collection.find_one(
        {
            "user_id": user_id
        }
    )


    if not photographer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )


    photographer_id = str(
        photographer["_id"]
    )


    try:

        object_id = ObjectId(
            event_id
        )

    except Exception:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )


    # Récupérer l'événement avant suppression

    event = events_collection.find_one(
        {
            "_id": object_id,
            "photographer_id": photographer_id
        }
    )


    if not event:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )


    # Supprimer l'image

    cover_photo = event.get(
        "cover_photo"
    )


    if cover_photo:

        filename = Path(
            cover_photo
        ).name

        file_path = (
            UPLOAD_DIR / filename
        )

        if file_path.exists():

            file_path.unlink()


    # Supprimer l'événement

    result = events_collection.delete_one(
        {
            "_id": object_id,
            "photographer_id": photographer_id
        }
    )


    if result.deleted_count == 0:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )


    return {
        "message": "Événement supprimé avec succès"
    }