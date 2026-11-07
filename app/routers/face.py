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
    events_collection
)

from app.dependencies.auth import get_current_user
from app.schemas.face import FaceResponse
from app.models.face import FaceModel


router = APIRouter(
    prefix="/faces",
    tags=["Faces"]
)


# ============================================================
# Conversion MongoDB → Response
# ============================================================

def face_to_response(face: dict) -> dict:
    return {
        "id": str(face["_id"]),

        "photo_id": face["photo_id"],
        "event_id": face["event_id"],

        "person_id": face.get("person_id"),

        "x": face["x"],
        "y": face["y"],
        "width": face["width"],
        "height": face["height"],

        "confidence": face["confidence"],

        "embedding": face.get("embedding"),

        "created_at": face["created_at"]
    }


# ============================================================
# CRÉER UNE FACE
# ============================================================

@router.post(
    "",
    response_model=FaceResponse,
    status_code=status.HTTP_201_CREATED
)
def create_face(
    face: FaceModel,
    current_user=Depends(get_current_user)
):

    # --------------------------------------------------------
    # Vérifier l'ID de la photo
    # --------------------------------------------------------

    if not ObjectId.is_valid(face.photo_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID photo invalide"
        )

    # --------------------------------------------------------
    # Vérifier l'ID de l'événement
    # --------------------------------------------------------

    if not ObjectId.is_valid(face.event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )

    # --------------------------------------------------------
    # Vérifier que la photo existe
    # --------------------------------------------------------

    photo = photos_collection.find_one({
        "_id": ObjectId(face.photo_id)
    })

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable"
        )

    # --------------------------------------------------------
    # Vérifier que l'événement existe
    # --------------------------------------------------------

    event = events_collection.find_one({
        "_id": ObjectId(face.event_id)
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )

    # --------------------------------------------------------
    # Vérifier que la photo appartient à l'événement
    # --------------------------------------------------------

    if photo.get("event_id") != face.event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La photo n'appartient pas à cet événement"
        )

    # --------------------------------------------------------
    # Vérifier que l'événement appartient au photographe
    # --------------------------------------------------------
    #
    # La face n'a PAS de photographer_id.
    # On vérifie donc le propriétaire via l'événement.
    #

    user_id = str(current_user["_id"])

    if event.get("photographer_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cet événement"
        )

    # --------------------------------------------------------
    # Création du document
    # --------------------------------------------------------

    face_data = face.model_dump()

    result = faces_collection.insert_one(face_data)

    face_data["_id"] = result.inserted_id

    return face_to_response(face_data)


# ============================================================
# RÉCUPÉRER LES FACES D'UNE PHOTO
# ============================================================

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

    # --------------------------------------------------------
    # Récupérer la photo
    # --------------------------------------------------------

    photo = photos_collection.find_one({
        "_id": ObjectId(photo_id)
    })

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable"
        )

    event_id = photo.get("event_id")

    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette photo n'est associée à aucun événement"
        )

    # --------------------------------------------------------
    # Récupérer l'événement
    # --------------------------------------------------------

    if not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID événement invalide"
        )

    event = events_collection.find_one({
        "_id": ObjectId(event_id)
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )

    # --------------------------------------------------------
    # Vérifier le propriétaire
    # --------------------------------------------------------

    user_id = str(current_user["_id"])

    if event.get("photographer_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cette photo"
        )

    # --------------------------------------------------------
    # Récupérer les faces
    # --------------------------------------------------------

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


# ============================================================
# RÉCUPÉRER TOUTES LES FACES D'UN ÉVÉNEMENT
# ============================================================

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

    # --------------------------------------------------------
    # Récupérer l'événement
    # --------------------------------------------------------

    event = events_collection.find_one({
        "_id": ObjectId(event_id)
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )

    # --------------------------------------------------------
    # Vérifier le propriétaire
    # --------------------------------------------------------

    user_id = str(current_user["_id"])

    if event.get("photographer_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cet événement"
        )

    # --------------------------------------------------------
    # Récupérer les faces
    # --------------------------------------------------------

    faces = faces_collection.find({
        "event_id": event_id
    }).sort(
        "created_at",
        -1
    )

    return [
        face_to_response(face)
        for face in faces
    ]


# ============================================================
# RÉCUPÉRER UNE FACE PAR SON ID
# ============================================================

@router.get(
    "/{face_id}",
    response_model=FaceResponse
)
def get_face(
    face_id: str,
    current_user=Depends(get_current_user)
):

    if not ObjectId.is_valid(face_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID face invalide"
        )

    # --------------------------------------------------------
    # Récupérer la face
    # --------------------------------------------------------

    face = faces_collection.find_one({
        "_id": ObjectId(face_id)
    })

    if not face:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Face introuvable"
        )

    # --------------------------------------------------------
    # Vérifier l'événement
    # --------------------------------------------------------

    event_id = face.get("event_id")

    if not event_id or not ObjectId.is_valid(event_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Événement associé invalide"
        )

    event = events_collection.find_one({
        "_id": ObjectId(event_id)
    })

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Événement introuvable"
        )

    # --------------------------------------------------------
    # Vérifier le propriétaire
    # --------------------------------------------------------

    user_id = str(current_user["_id"])

    if event.get("photographer_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cette face"
        )

    return face_to_response(face)