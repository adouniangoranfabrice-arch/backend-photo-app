from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PhotoModel(BaseModel):

    # Événement auquel appartient la photo
    event_id: str

    # Photographe propriétaire
    photographer_id: str

    # URL de l'image originale Cloudinary
    file_url: str

    # URL de la miniature
    thumbnail_url: str | None = None

    # Identifiant Cloudinary
    # Nécessaire pour supprimer ou modifier l'image
    public_id: str | None = None

    # Nom original du fichier envoyé
    original_name: str | None = Field(
        default=None,
        max_length=255
    )

    # Taille du fichier en octets
    file_size: int | None = None

    # Type MIME
    # Exemple : image/jpeg
    mime_type: str | None = None

    # Dimensions de l'image
    width: int | None = None
    height: int | None = None

    # Statut de la photo
    status: str = "ACTIVE"

    # Date de création
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )