from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from bson import ObjectId

from app.core.database import (
    faces_collection,
    photos_collection,
    events_collection,
    photographers_collection
)

from app.dependencies.auth import get_current_user
from app.models.users import UserRole
from app.schemas.face import FaceResponse
from app.models.face import FaceModel


router = APIRouter(
    prefix="/faces",
    tags=["Faces"]
)

# Ajouter
def face_to_response(face: dict):
    return {
        "id": str(face["_id"]),

        "photo_id": face["photo_id"],
        "event_id": face["event_id"],
        "photographer_id": face["photographer_id"],

        "person_id": face.get("person_id"),

        "x": face["x"],
        "y": face["y"],
        "width": face["width"],
        "height": face["height"],

        "confidence": face["confidence"],

        "embedding": face.get("embedding"),

        "created_at": face["created_at"]
    }

@router.post(
    "",
    response_model=FaceResponse,
    status_code=status.HTTP_201_CREATED
)
def create_face(
    face: FaceModel,
    current_user=Depends(get_current_user)
):
    # Vérifier que l'utilisateur est photographe
    if current_user.get("role") != UserRole.PHOTOGRAPHER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux photographes"
        )

    user_id = str(current_user["_id"])

    # Vérifier le profil photographe
    photographer = photographers_collection.find_one({
        "user_id": user_id
    })

    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )

    photographer_id = str(photographer["_id"])

    # Vérifier que la face appartient bien
    # au photographe connecté
    if face.photographer_id != photographer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette face n'appartient pas à votre compte"
        )

    # Vérifier la photo
    photo = photos_collection.find_one({
        "_id": ObjectId(face.photo_id)
    })

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable"
        )

    # Vérifier que la photo appartient au bon photographe
    if photo["photographer_id"] != photographer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette photo ne vous appartient pas"
        )

    # Vérifier l'événement
    event = events_collection.find_one({
        "_id": ObjectId(face.event_id)
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )

    # Vérifier la cohérence photo / événement
    if photo["event_id"] != face.event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La photo n'appartient pas à cet événement"
        )

    # Création du document MongoDB
    face_data = face.model_dump()

    result = faces_collection.insert_one(
        face_data
    )

    face_data["_id"] = result.inserted_id

    return face_to_response(face_data)

# Récupérer une photo
@router.get(
    "/photo/{photo_id}",
    response_model=list[FaceResponse]
)
def get_faces_by_photo(
    photo_id: str,
    current_user=Depends(get_current_user)
):
    if not ObjectId.is_valid(photo_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID photo invalide"
        )

    user_id = str(current_user["_id"])

    photographer = photographers_collection.find_one({
        "user_id": user_id
    })

    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )

    photographer_id = str(photographer["_id"])

    photo = photos_collection.find_one({
        "_id": ObjectId(photo_id),
        "photographer_id": photographer_id
    })

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable"
        )

    faces = faces_collection.find({
        "photo_id": photo_id
    }).sort(
        "created_at",
        -1
    )

    return [
        face_to_response(face)
        for face in faces
    ]

# Récupérer toutes les faces d'un événement
@router.get(
    "/event/{event_id}",
    response_model=list[FaceResponse]
)
def get_faces_by_event(
    event_id: str,
    current_user=Depends(get_current_user)
):
    if not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )

    user_id = str(current_user["_id"])

    photographer = photographers_collection.find_one({
        "user_id": user_id
    })

    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil photographe introuvable"
        )

    photographer_id = str(photographer["_id"])

    event = events_collection.find_one({
        "_id": ObjectId(event_id),
        "photographer_id": photographer_id
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )

    faces = faces_collection.find({
        "event_id": event_id,
        "photographer_id": photographer_id
    }).sort(
        "created_at",
        -1
    )

    return [
        face_to_response(face)
        for face in faces
    ]

