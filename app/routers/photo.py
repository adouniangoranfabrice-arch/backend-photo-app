from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
import cloudinary
import cloudinary.uploader
import app.core.cloudinary

from app.services.activity_logger import create_activity_log
from app.services.activity_actions import DELETE_PHOTO

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    Request,
    status,
    Response
)

from app.core.database import (
    events_collection,
    photos_collection,
    users_collection,
)

from app.dependencies.auth import require_role
from app.models.users import UserRole
from app.schemas.photo import PhotoResponse


router = APIRouter(
    prefix="/photos",
    tags=["Photos"],
)


# ============================================================
# CONFIGURATION
# ============================================================

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

MAX_FILE_SIZE = 30 * 1024 * 1024  # 10 MB


# ============================================================
# UTILITAIRE : RÉCUPÉRER LE PHOTOGRAPHE CONNECTÉ
# ============================================================


def get_photographer_from_user(current_user: dict) -> str:
    """
    Récupère l'identifiant MongoDB de l'utilisateur connecté.
    """

    user = users_collection.find_one({
        "_id": current_user["_id"]
    })

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    return str(user["_id"])


# ============================================================
# UTILITAIRE : CONVERTIR UNE PHOTO POUR LA RÉPONSE API
# ============================================================

def photo_to_response(photo: dict) -> dict:

    return {
        "id": str(photo["_id"]),

        "event_id": photo["event_id"],

        "photographer_id": photo["photographer_id"],

        "file_url": photo["file_url"],

        "thumbnail_url": photo.get(
            "thumbnail_url"
        ),

        "public_id": photo.get(
            "public_id"
        ),

        "original_name": photo.get(
            "original_name"
        ),

        "file_size": photo.get(
            "file_size"
        ),

        "mime_type": photo.get(
            "mime_type"
        ),

        "width": photo.get(
            "width"
        ),

        "height": photo.get(
            "height"
        ),

        "format": photo.get(
            "format"
        ),

        "status": photo.get(
            "status",
            "ACTIVE"
        ),

        "created_at": photo["created_at"],
    }


# ============================================================
# UTILITAIRE : SUPPRIMER DES IMAGES CLOUDINARY
# ============================================================

def cleanup_cloudinary_images(
    public_ids: list[str],
) -> None:
    """
    Supprime les images Cloudinary déjà uploadées
    lorsqu'une erreur survient pendant le traitement.
    """

    for public_id in public_ids:

        try:

            cloudinary.uploader.destroy(
                public_id,
                resource_type="image",
                invalidate=True,
            )

        except Exception:
            # On ne masque pas l'erreur principale.
            pass


# ============================================================
# UPLOAD MULTIPLE PHOTOS
# ============================================================


@router.post(
    "/events/{event_id}/upload",
    response_model=list[PhotoResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_photos(
    request: Request,
    event_id: str,
    files: list[UploadFile] = File(...),
    current_user=Depends(
        require_role(UserRole.PHOTOGRAPHER.value)
    ),
):
    # 1. Vérifier l'identifiant de l'événement
    if not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide",
        )

    # 2. Vérifier les fichiers
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune photo envoyée",
        )

    # 3. Récupérer l'utilisateur connecté
    user_id = str(current_user["_id"])

    user = users_collection.find_one({
        "_id": current_user["_id"]
    })

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    # Récupérer le profil photographe
    photographer = get_photographer_from_user(current_user)

    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable",
        )

    # Identifiant utilisé pour les statistiques photographe
    photographer_id = user_id

    # 4. Vérifier que l'événement appartient à l'utilisateur
    event = events_collection.find_one({
        "_id": ObjectId(event_id),
        "user_id": user_id,
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Événement introuvable ou "
                "vous n'êtes pas le propriétaire"
            ),
        )

    created_photos = []
    uploaded_public_ids = []

    try:
        # 5. Traiter chaque photo
        for file in files:
            if not file.filename:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nom de fichier invalide",
                )

            # Vérifier l'extension
            extension = Path(file.filename).suffix.lower()

            if extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Extension non autorisée pour {file.filename}. "
                        f"Extensions acceptées : "
                        f"{', '.join(ALLOWED_EXTENSIONS)}"
                    ),
                )

            # Vérifier le type MIME
            if file.content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Format non autorisé pour {file.filename}",
                )

            # Lire le fichier
            file_content = await file.read()
            file_size = len(file_content)

            if file_size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Le fichier {file.filename} est vide",
                )

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{file.filename} dépasse la limite de 10 MB",
                )

            # 6. Envoyer la photo vers Cloudinary
            try:
                result = cloudinary.uploader.upload(
                    file_content,
                    folder=f"photiva/events/{event_id}",
                    resource_type="image",
                    secure=True,
                    unique_filename=True,
                    overwrite=False,
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Erreur Cloudinary pour {file.filename}",
                )

            public_id = result.get("public_id")
            file_url = result.get("secure_url")

            if not public_id or not file_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Cloudinary n'a pas retourné "
                        "les informations nécessaires"
                    ),
                )

            uploaded_public_ids.append(public_id)

            # 7. Générer la miniature
            thumbnail_url = (
                cloudinary.CloudinaryImage(public_id).build_url(
                    transformation=[
                        {
                            "width": 400,
                            "height": 300,
                            "crop": "fill",
                            "quality": "auto",
                            "fetch_format": "auto",
                        }
                    ],
                    secure=True,
                )
            )

            now = datetime.now(timezone.utc)

            # 8. Créer le document photo
            photo = {
                # Relation avec users
                "user_id": user_id,

                # Relation avec events
                "event_id": event_id,

                # Identifiant pour les statistiques photographe
                "photographer_id": photographer_id,

                "file_url": file_url,
                "thumbnail_url": thumbnail_url,
                "public_id": public_id,
                "original_name": file.filename,
                "file_size": file_size,
                "mime_type": file.content_type,
                "width": result.get("width"),
                "height": result.get("height"),
                "format": result.get("format"),
                "status": "ACTIVE",
                "created_at": now,
            }

            # 9. Enregistrer dans MongoDB
            insert_result = photos_collection.insert_one(photo)
            photo["_id"] = insert_result.inserted_id

            created_photos.append(photo)

    except Exception as e:
        # 10. Annuler les documents MongoDB créés
        for photo in created_photos:
            try:
                photos_collection.delete_one({
                    "_id": photo["_id"]
                })
            except Exception:
                pass

        # Supprimer les images envoyées vers Cloudinary
        cleanup_cloudinary_images(uploaded_public_ids)

        if isinstance(e, HTTPException):
            raise

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur est survenue pendant l'upload des photos",
        )

    # 11. Enregistrer l'activité
    photo_count = len(created_photos)

    photo_ids = [
        str(photo["_id"])
        for photo in created_photos
    ]

    create_activity_log(
        user_id=user_id,
        photographer_id=photographer_id,
        user_role=current_user.get("role"),
        action="UPLOAD_PHOTO",
        resource="photo",
        description=f"a importé {photo_count} photos",
        target=event.get("name"),
        ip_address=(
            request.client.host
            if request.client
            else None
        ),
        user_agent=request.headers.get("user-agent"),
        metadata={
            "event_id": event_id,
            "photo_count": photo_count,
            "photo_ids": photo_ids,
        },
    )

    # 12. Retourner les photos créées
    return [
        photo_to_response(photo)
        for photo in created_photos
    ]

# ============================================================
# RÉCUPÉRER LES PHOTOS D'UN ÉVÉNEMENT
# ============================================================


@router.get(
    "/events/{event_id}",
    response_model=list[PhotoResponse],
)
def get_event_photos(
    event_id: str,

    current_user=Depends(
        require_role(
            UserRole.PHOTOGRAPHER.value
        )
    ),
):
    # ========================================================
    # 1. VÉRIFIER L'ID DE L'ÉVÉNEMENT
    # ========================================================

    if not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide",
        )

    # ========================================================
    # 2. RÉCUPÉRER L'ID DE L'UTILISATEUR CONNECTÉ
    # ========================================================

    user_id = get_photographer_from_user(
        current_user
    )

    # Dans ton application, l'identifiant photographe
    # correspond à l'identifiant du compte utilisateur.
    photographer_id = user_id

    # ========================================================
    # 3. VÉRIFIER QUE L'ÉVÉNEMENT APPARTIENT À L'UTILISATEUR
    # ========================================================

    event = events_collection.find_one({
        "_id": ObjectId(event_id),
        "user_id": user_id,
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable ou accès non autorisé",
        )

    # ========================================================
    # 4. RÉCUPÉRER LES PHOTOS DE CET ÉVÉNEMENT
    # ========================================================

    photos = photos_collection.find({
        "event_id": event_id,
        "user_id": user_id,
        "status": "ACTIVE",
    }).sort([
        # De la première photo importée à la dernière
        ("created_at", 1),
        ("_id", 1),
    ])

    # ========================================================
    # 5. RETOURNER LES PHOTOS
    # ========================================================

    return [
        photo_to_response(photo)
        for photo in photos
    ]

# ============================================================
# SUPPRIMER UNE PHOTO
# ============================================================

@router.delete(
    "/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_photo(
    photo_id: str,
    request: Request,
    current_user=Depends(
        require_role(UserRole.PHOTOGRAPHER.value)
    ),
):
    # =====================================================
    # 1. VÉRIFIER L'ID DE LA PHOTO
    # =====================================================

    if not ObjectId.is_valid(photo_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de photo invalide.",
        )

    # =====================================================
    # 2. RÉCUPÉRER L'UTILISATEUR CONNECTÉ
    # =====================================================

    user = users_collection.find_one({
        "_id": current_user["_id"]
    })

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    user_id = str(user["_id"])

    # Dans ton application, le photographe utilise
    # l'identifiant de son compte utilisateur.
    photographer_id = user_id

    # =====================================================
    # 3. RÉCUPÉRER LA PHOTO ET VÉRIFIER SON PROPRIÉTAIRE
    # =====================================================

    photo = photos_collection.find_one({
        "_id": ObjectId(photo_id),
        "user_id": user_id,
    })

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable ou accès non autorisé.",
        )

    # =====================================================
    # 4. RÉCUPÉRER LES INFORMATIONS POUR LE LOG
    # =====================================================

    photo_name = photo.get(
        "original_name",
        "Photo sans nom",
    )

    event_id = photo.get("event_id")
    public_id = photo.get("public_id")

    # =====================================================
    # 5. SUPPRIMER L'IMAGE DE CLOUDINARY
    # =====================================================

    if public_id:
        try:
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type="image",
                invalidate=True,
            )

            if result.get("result") not in ("ok", "not found"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Impossible de supprimer "
                        "l'image de Cloudinary."
                    ),
                )

        except HTTPException:
            raise

        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Erreur lors de la suppression "
                    "de l'image sur Cloudinary."
                ),
            )

    # =====================================================
    # 6. SUPPRIMER LA PHOTO DE MONGODB
    # =====================================================

    delete_result = photos_collection.delete_one({
        "_id": ObjectId(photo_id),
        "user_id": user_id,
    })

    if delete_result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable.",
        )

    # =====================================================
    # 7. ENREGISTRER L'ACTIVITÉ
    # =====================================================

    try:
        create_activity_log(
            user_id=user_id,
            photographer_id=photographer_id,
            user_role=current_user.get("role"),
            action=DELETE_PHOTO,
            resource="photo",
            resource_id=photo_id,
            description="a supprimé la photo",
            target=photo_name,
            ip_address=(
                request.client.host
                if request.client
                else None
            ),
            user_agent=request.headers.get("user-agent"),
            metadata={
                "event_id": event_id,
                "photo_name": photo_name,
                "public_id": public_id,
            },
        )
    except Exception:
        # La photo a déjà été supprimée.
        # Une erreur de journalisation ne doit pas
        # faire croire que la suppression a échoué.
        pass

    # HTTP 204 : aucune réponse
    return Response(status_code=status.HTTP_204_NO_CONTENT)