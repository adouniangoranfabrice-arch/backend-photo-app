from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
import cloudinary
import cloudinary.uploader
import app.core.cloudinary

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.core.database import (
    events_collection,
    photos_collection,
    photographers_collection,
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

def get_photographer_from_user(current_user: dict) -> dict:
    """
    Récupère le profil photographe associé
    à l'utilisateur actuellement connecté.
    """

    user_id = str(current_user["_id"])

    photographer = photographers_collection.find_one(
        {
            "user_id": user_id
        }
    )

    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable",
        )

    return photographer


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
    event_id: str,

    files: list[UploadFile] = File(...),

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
    # 2. VÉRIFIER QU'IL Y A DES FICHIERS
    # ========================================================

    if not files:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune photo envoyée",
        )

    # ========================================================
    # 3. RÉCUPÉRER LE PHOTOGRAPHE
    # ========================================================

    photographer = get_photographer_from_user(
        current_user
    )

    photographer_id = str(
        photographer["_id"]
    )

    # ========================================================
    # 4. VÉRIFIER QUE L'ÉVÉNEMENT APPARTIENT
    #    AU PHOTOGRAPHE
    # ========================================================

    event = events_collection.find_one(
        {
            "_id": ObjectId(event_id),

            "photographer_id": photographer_id,
        }
    )

    if not event:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Événement introuvable ou "
                "vous n'êtes pas le propriétaire"
            ),
        )

    # ========================================================
    # 5. LISTES DE CONTRÔLE
    # ========================================================

    created_photos = []

    uploaded_public_ids = []

    # ========================================================
    # 6. TRAITER CHAQUE PHOTO
    # ========================================================

    try:

        for file in files:

            # =================================================
            # 6.1 NOM DU FICHIER
            # =================================================

            if not file.filename:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nom de fichier invalide",
                )

            # =================================================
            # 6.2 EXTENSION
            # =================================================

            extension = Path(
                file.filename
            ).suffix.lower()

            if extension not in ALLOWED_EXTENSIONS:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Extension non autorisée pour "
                        f"{file.filename}. "
                        f"Extensions acceptées : "
                        f"{', '.join(ALLOWED_EXTENSIONS)}"
                    ),
                )

            # =================================================
            # 6.3 TYPE MIME
            # =================================================

            if file.content_type not in ALLOWED_CONTENT_TYPES:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Format non autorisé pour "
                        f"{file.filename}"
                    ),
                )

            # =================================================
            # 6.4 LIRE LE FICHIER
            # =================================================

            file_content = await file.read()

            # =================================================
            # 6.5 VÉRIFIER QUE LE FICHIER N'EST PAS VIDE
            # =================================================

            file_size = len(file_content)

            if file_size == 0:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Le fichier "
                        f"{file.filename} est vide"
                    ),
                )

            # =================================================
            # 6.6 VÉRIFIER LA TAILLE
            # =================================================

            if file_size > MAX_FILE_SIZE:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{file.filename} dépasse "
                        f"la limite de 10 MB"
                    ),
                )

            # =================================================
            # 6.7 UPLOAD CLOUDINARY
            # =================================================

            try:

                result = cloudinary.uploader.upload(
                    file_content,

                    folder=(
                        f"photiva/events/{event_id}"
                    ),

                    resource_type="image",

                    secure=True,

                    unique_filename=True,

                    overwrite=False,
                )

            except Exception as e:

                raise HTTPException(
                    status_code=(
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    ),
                    detail=(
                        f"Erreur Cloudinary pour "
                        f"{file.filename} : {str(e)}"
                    ),
                )

            # =================================================
            # 6.8 RÉCUPÉRER LES INFORMATIONS CLOUDINARY
            # =================================================

            public_id = result.get(
                "public_id"
            )

            file_url = result.get(
                "secure_url"
            )

            width = result.get(
                "width"
            )

            height = result.get(
                "height"
            )

            image_format = result.get(
                "format"
            )

            # =================================================
            # 6.9 VÉRIFIER LA RÉPONSE CLOUDINARY
            # =================================================

            if not public_id or not file_url:

                raise HTTPException(
                    status_code=(
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    ),
                    detail=(
                        "Cloudinary n'a pas retourné "
                        "les informations nécessaires"
                    ),
                )

            # =================================================
            # 6.10 AJOUTER LE PUBLIC_ID AU ROLLBACK
            # =================================================

            uploaded_public_ids.append(
                public_id
            )

            # =================================================
            # 6.11 CRÉER L'URL MINIATURE
            # =================================================

            thumbnail_url = (
                cloudinary.CloudinaryImage(
                    public_id
                ).build_url(
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

            # =================================================
            # 6.12 DATE
            # =================================================

            now = datetime.now(
                timezone.utc
            )

            # =================================================
            # 6.13 DOCUMENT MONGODB
            # =================================================

            photo = {

                "event_id": event_id,

                "photographer_id": photographer_id,

                "file_url": file_url,

                "thumbnail_url": thumbnail_url,

                "public_id": public_id,

                "original_name": file.filename,

                "file_size": file_size,

                "mime_type": file.content_type,

                "width": width,

                "height": height,

                "format": image_format,

                "status": "ACTIVE",

                "created_at": now,
            }

            # =================================================
            # 6.14 ENREGISTRER DANS MONGODB
            # =================================================

            insert_result = photos_collection.insert_one(
                photo
            )

            photo["_id"] = (
                insert_result.inserted_id
            )

            # =================================================
            # 6.15 AJOUTER À LA LISTE DE RÉPONSE
            # =================================================

            created_photos.append(
                photo
            )

    except HTTPException:

        # ====================================================
        # ROLLBACK CLOUDINARY
        # ====================================================

        cleanup_cloudinary_images(
            uploaded_public_ids
        )

        # Supprimer les documents MongoDB déjà créés
        # pendant cette opération

        for photo in created_photos:

            try:

                photos_collection.delete_one(
                    {
                        "_id": photo["_id"]
                    }
                )

            except Exception:
                pass

        raise

    except Exception as e:

        # ====================================================
        # ROLLBACK CLOUDINARY
        # ====================================================

        cleanup_cloudinary_images(
            uploaded_public_ids
        )

        # ====================================================
        # ROLLBACK MONGODB
        # ====================================================

        for photo in created_photos:

            try:

                photos_collection.delete_one(
                    {
                        "_id": photo["_id"]
                    }
                )

            except Exception:
                pass

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Une erreur est survenue "
                "pendant l'upload des photos"
            ),
        )

    # ========================================================
    # 7. RÉPONSE
    # ========================================================

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
    # 1. VÉRIFIER L'ID
    # ========================================================

    if not ObjectId.is_valid(event_id):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide",
        )

    # ========================================================
    # 2. PHOTOGRAPHE
    # ========================================================

    photographer = get_photographer_from_user(
        current_user
    )

    photographer_id = str(
        photographer["_id"]
    )

    # ========================================================
    # 3. VÉRIFIER L'ÉVÉNEMENT
    # ========================================================

    event = events_collection.find_one(
        {
            "_id": ObjectId(event_id),

            "photographer_id": photographer_id,
        }
    )

    if not event:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable",
        )

    # ========================================================
    # 4. RÉCUPÉRER LES PHOTOS
    # ========================================================

    photos = photos_collection.find(
        {
            "event_id": event_id,

            "photographer_id": photographer_id,

            "status": "ACTIVE",
        }
    ).sort(
        "created_at",
        -1,
    )

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

    current_user=Depends(
        require_role(
            UserRole.PHOTOGRAPHER.value
        )
    ),
):

    # ========================================================
    # 1. VÉRIFIER L'ID
    # ========================================================

    if not ObjectId.is_valid(photo_id):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID photo invalide",
        )

    # ========================================================
    # 2. RÉCUPÉRER LE PHOTOGRAPHE
    # ========================================================

    photographer = get_photographer_from_user(
        current_user
    )

    photographer_id = str(
        photographer["_id"]
    )

    # ========================================================
    # 3. RÉCUPÉRER LA PHOTO
    # ========================================================

    photo = photos_collection.find_one(
        {
            "_id": ObjectId(photo_id),

            "photographer_id": photographer_id,
        }
    )

    if not photo:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable",
        )

    # ========================================================
    # 4. SUPPRIMER DE CLOUDINARY
    # ========================================================

    public_id = photo.get(
        "public_id"
    )

    if public_id:

        try:

            result = cloudinary.uploader.destroy(
                public_id,

                resource_type="image",

                invalidate=True,
            )

            cloudinary_result = result.get(
                "result"
            )

            if cloudinary_result not in {
                "ok",
                "not found",
            }:

                raise HTTPException(
                    status_code=(
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    ),
                    detail=(
                        "Impossible de supprimer "
                        "la photo de Cloudinary"
                    ),
                )

        except HTTPException:

            raise

        except Exception as e:

            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    f"Erreur Cloudinary : {str(e)}"
                ),
            )

    # ========================================================
    # 5. SUPPRIMER DE MONGODB
    # ========================================================

    delete_result = photos_collection.delete_one(
        {
            "_id": ObjectId(photo_id),

            "photographer_id": photographer_id,
        }
    )

    if delete_result.deleted_count == 0:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La photo n'a pas pu être supprimée",
        )

    # 204 = aucune réponse
    return None