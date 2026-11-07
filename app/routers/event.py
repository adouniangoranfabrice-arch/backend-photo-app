from datetime import datetime, timezone
from pathlib import Path
import secrets
from uuid import uuid4
from app.core.config import settings

from app.services.activity_logger import create_activity_log
from app.services.activity_actions import CREATE_EVENT, DELETE_EVENT

from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status
)

import cloudinary
import cloudinary.api
import app.core.cloudinary  # noqa: F401  (configure Cloudinary)

from app.core.database import (
    users_collection,
    events_collection,
    photos_collection,
    faces_collection
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

def event_to_response(event: dict) -> dict:

    public_token = event["public_token"]

    return {
        "id": str(event["_id"]),
        "user_id": event["user_id"],
        "name": event["name"],
        "description": event.get("description"),
        "event_type": event["event_type"],
        "event_date": event.get("event_date"),
        "location": event.get("location"),
        "cover_photo": event.get("cover_photo"),
        "public_token": public_token,
        "public_url": (f"{settings.FRONTEND_URL}public/galerie/{public_token}"),
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

    request: Request,

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

    user = users_collection.find_one({
        "_id": current_user["_id"]
    })

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    user_id = str(user["_id"])

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

        # Chemin enregistré dans MongoDB

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

        "user_id": user_id,

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

    # =====================================================
    # ENREGISTRER L'ACTIVITÉ
    # =====================================================

    create_activity_log(

        user_id=str(
            current_user["_id"]
        ),

        user_role=current_user.get(
            "role"
        ),

        action=CREATE_EVENT,

        resource="event",

        resource_id=str(
            result.inserted_id
        ),

        description=(
            "a créé l'événement"
        ),

        target=name,

        ip_address=(
            request.client.host
            if request.client
            else None
        ),

        user_agent=request.headers.get(
            "user-agent"
        ),

        metadata={
            "event_type": event_type,
            "location": location,
            "is_public": is_public,
            "has_cover_photo": (
                cover_photo_path is not None
            )
        }
    )

    # =====================================================
    # RÉPONSE
    # =====================================================

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
        require_role(UserRole.PHOTOGRAPHER.value)
    )
):
    # ID de l'utilisateur connecté
    user_id = str(current_user["_id"])

    # Récupérer les événements créés par cet utilisateur
    events = events_collection.find({
        "user_id": user_id
    }).sort(
        "created_at", -1
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
        require_role(UserRole.PHOTOGRAPHER.value)
    )
):
    # ID de l'utilisateur connecté
    user_id = str(current_user["_id"])

    # Vérifier la validité de l'ID de l'événement
    if not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )

    object_id = ObjectId(event_id)

    # Rechercher l'événement appartenant à cet utilisateur
    event = events_collection.find_one({
        "_id": object_id,
        "user_id": user_id
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable ou accès non autorisé"
        )

    return event_to_response(event)

# =========================================================
# MODIFIER UN ÉVÉNEMENT
# =========================================================
@router.get(
    "/{event_id}",
    response_model=EventResponse
)
def get_event(
    event_id: str,
    current_user=Depends(
        require_role(UserRole.PHOTOGRAPHER.value)
    )
):
    # ID de l'utilisateur connecté
    user_id = str(current_user["_id"])

    # Vérifier la validité de l'ID de l'événement
    if not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )

    object_id = ObjectId(event_id)

    # Rechercher l'événement appartenant à cet utilisateur
    event = events_collection.find_one({
        "_id": object_id,
        "user_id": user_id
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable ou accès non autorisé"
        )

    return event_to_response(event)


# =========================================================
# SUPPRIMER UN ÉVÉNEMENT ET SES PHOTOS
# =========================================================

# L'API Admin de Cloudinary accepte 100 public_id par appel
CLOUDINARY_BATCH_SIZE = 100


def delete_cloudinary_images(public_ids: list[str]) -> int:
    """
    Supprime des images Cloudinary par lots.
    Retourne le nombre d'images qui n'ont pas pu être supprimées.
    """

    failed = 0

    for start in range(0, len(public_ids), CLOUDINARY_BATCH_SIZE):
        batch = public_ids[start:start + CLOUDINARY_BATCH_SIZE]

        try:
            result = cloudinary.api.delete_resources(
                batch,
                resource_type="image",
                type="upload",
                invalidate=True,
            )

            deleted = result.get("deleted", {})
            failed += sum(
                1
                for public_id in batch
                if deleted.get(public_id) not in ("deleted", "not_found")
            )

        except Exception:
            failed += len(batch)

    return failed


@router.delete(
    "/{event_id}"
)
def delete_event(
    request: Request,
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

    # =====================================================
    # 1. VÉRIFIER L'ID ET LE PROPRIÉTAIRE
    # =====================================================

    if not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )

    object_id = ObjectId(event_id)

    event = events_collection.find_one({
        "_id": object_id,
        "user_id": user_id
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable ou accès non autorisé"
        )

    # =====================================================
    # 2. SUPPRIMER LES PHOTOS SUR CLOUDINARY
    # =====================================================

    photos = list(
        photos_collection.find(
            {"event_id": event_id},
            {"public_id": 1}
        )
    )

    public_ids = [
        photo["public_id"]
        for photo in photos
        if photo.get("public_id")
    ]

    failed_cloudinary = delete_cloudinary_images(public_ids)

    # Supprimer le dossier Cloudinary (vide) de l'événement
    try:
        cloudinary.api.delete_folder(
            f"photiva/events/{event_id}"
        )
    except Exception:
        # Dossier inexistant ou pas encore vide : sans gravité
        pass

    # =====================================================
    # 3. SUPPRIMER LES DONNÉES MONGODB
    # =====================================================

    faces_result = faces_collection.delete_many({
        "event_id": event_id
    })

    photos_result = photos_collection.delete_many({
        "event_id": event_id
    })

    # =====================================================
    # 4. SUPPRIMER LA PHOTO DE COUVERTURE LOCALE
    # =====================================================

    cover_photo = event.get("cover_photo")

    if cover_photo and not cover_photo.startswith("http"):
        file_path = UPLOAD_DIR / Path(cover_photo).name

        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

    # =====================================================
    # 5. SUPPRIMER L'ÉVÉNEMENT
    # =====================================================

    result = events_collection.delete_one({
        "_id": object_id,
        "user_id": user_id
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )

    # =====================================================
    # 6. ENREGISTRER L'ACTIVITÉ
    # =====================================================

    create_activity_log(
        user_id=user_id,
        photographer_id=user_id,
        user_role=current_user.get("role"),

        action=DELETE_EVENT,

        resource="event",
        resource_id=event_id,

        description="a supprimé l'événement",
        target=event.get("name"),

        ip_address=(
            request.client.host
            if request.client
            else None
        ),

        user_agent=request.headers.get(
            "user-agent"
        ),

        metadata={
            "deleted_photos": photos_result.deleted_count,
            "deleted_faces": faces_result.deleted_count,
            "cloudinary_failures": failed_cloudinary
        }
    )

    return {
        "message": "Événement supprimé avec succès",
        "deleted_photos": photos_result.deleted_count,
        "deleted_faces": faces_result.deleted_count,
        "cloudinary_failures": failed_cloudinary
    }
