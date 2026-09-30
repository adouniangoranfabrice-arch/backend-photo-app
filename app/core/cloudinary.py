import cloudinary
import cloudinary.uploader

from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

def upload_image(
    file,
    folder: str = "photiva",
):
    """
    Upload une image vers Cloudinary.
    """

    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type="image",
    )

    return {
        "url": result.get("secure_url"),
        "public_id": result.get("public_id"),
        "width": result.get("width"),
        "height": result.get("height"),
        "format": result.get("format"),
        "bytes": result.get("bytes"),
    }


def delete_image(public_id: str):
    """
    Supprime une image Cloudinary.
    """

    return cloudinary.uploader.destroy(
        public_id,
        resource_type="image",
    )