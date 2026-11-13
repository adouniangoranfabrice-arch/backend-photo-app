"""
Reconnaissance faciale (InsightFace / ArcFace).

- Le modèle est chargé à la première utilisation (et non au démarrage),
  pour que l'API démarre vite et n'utilise pas de mémoire inutilement.
- Les embeddings sont normalisés (norme = 1) : la similarité entre deux
  visages est donc un simple produit scalaire (similarité cosinus).
"""

import os
import threading
from datetime import datetime, timezone

import cv2
import numpy as np

# Modèle InsightFace : "buffalo_l" (précis, ~300 Mo) ou "buffalo_s" (léger)
FACE_MODEL_NAME = os.getenv("FACE_MODEL", "buffalo_l")

# Seuil de similarité cosinus pour considérer que c'est la même personne.
# ArcFace : ~0.30 permissif, ~0.40 équilibré, ~0.50 strict.
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.40"))

# Taille max de l'image analysée (accélère fortement la détection)
MAX_ANALYSIS_SIDE = 1600

# Score minimal de détection pour garder un visage
MIN_DETECTION_SCORE = 0.5

_face_app = None
_lock = threading.Lock()


def get_face_app():
    """Charge le modèle une seule fois (thread-safe)."""

    global _face_app

    if _face_app is None:
        with _lock:
            if _face_app is None:
                from insightface.app import FaceAnalysis

                app = FaceAnalysis(
                    name=FACE_MODEL_NAME,
                    # Seulement détection + reconnaissance : moins de RAM
                    allowed_modules=["detection", "recognition"],
                    providers=["CPUExecutionProvider"],
                )
                app.prepare(ctx_id=-1, det_size=(640, 640))
                _face_app = app

    return _face_app


def _decode_image(image_bytes: bytes) -> np.ndarray:
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Impossible de lire l'image")

    # Réduire les très grandes images
    height, width = image.shape[:2]
    scale = MAX_ANALYSIS_SIDE / max(height, width)

    if scale < 1:
        image = cv2.resize(
            image,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    return image


def detect_faces(image_bytes: bytes) -> list[dict]:
    """
    Détecte les visages d'une image.
    Retourne pour chaque visage sa position (en % de l'image),
    son score de détection et son embedding normalisé.
    """

    image = _decode_image(image_bytes)
    height, width = image.shape[:2]

    faces = get_face_app().get(image)

    results = []

    for face in faces:
        if float(face.det_score) < MIN_DETECTION_SCORE:
            continue

        x1, y1, x2, y2 = face.bbox.astype(float)

        results.append({
            # Coordonnées relatives (indépendantes de la taille de l'image)
            "x": max(0.0, x1 / width),
            "y": max(0.0, y1 / height),
            "width": (x2 - x1) / width,
            "height": (y2 - y1) / height,
            "confidence": float(face.det_score),
            "embedding": face.normed_embedding.astype(float).tolist(),
        })

    return results


def largest_face_embedding(image_bytes: bytes) -> np.ndarray | None:
    """Embedding du plus grand visage de l'image (pour un selfie)."""

    faces = detect_faces(image_bytes)

    if not faces:
        return None

    biggest = max(faces, key=lambda f: f["width"] * f["height"])

    return np.asarray(biggest["embedding"], dtype=np.float32)


def index_photo_faces(
    *,
    faces_collection,
    photos_collection,
    photo_id: str,
    event_id: str,
    image_bytes: bytes,
) -> int:
    """
    Détecte les visages d'une photo, les enregistre dans `faces`
    et marque la photo comme indexée. Retourne le nombre de visages.
    """

    from bson import ObjectId

    faces = detect_faces(image_bytes)
    now = datetime.now(timezone.utc)

    # Ré-indexation : on remplace les anciens visages de la photo
    faces_collection.delete_many({"photo_id": photo_id})

    if faces:
        faces_collection.insert_many([
            {
                "photo_id": photo_id,
                "event_id": event_id,
                "person_id": None,
                "model": FACE_MODEL_NAME,
                "created_at": now,
                **face,
            }
            for face in faces
        ])

    photos_collection.update_one(
        {"_id": ObjectId(photo_id)},
        {"$set": {
            "faces_indexed": FACE_MODEL_NAME,
            "faces_count": len(faces),
        }},
    )

    return len(faces)


def find_matching_photos(
    *,
    faces_collection,
    event_id: str,
    query_embedding: np.ndarray,
    threshold: float = FACE_MATCH_THRESHOLD,
) -> dict[str, float]:
    """
    Compare un visage à tous les visages d'un événement.
    Retourne {photo_id: meilleure_similarité} pour les photos au-dessus du seuil.
    """

    faces = list(faces_collection.find(
        {"event_id": event_id, "model": FACE_MODEL_NAME},
        {"photo_id": 1, "embedding": 1},
    ))

    if not faces:
        return {}

    matrix = np.asarray(
        [face["embedding"] for face in faces],
        dtype=np.float32,
    )

    # Similarité cosinus (embeddings déjà normalisés)
    similarities = matrix @ query_embedding

    matches: dict[str, float] = {}

    for face, score in zip(faces, similarities):
        score = float(score)

        if score < threshold:
            continue

        photo_id = face["photo_id"]

        if score > matches.get(photo_id, -1):
            matches[photo_id] = score

    return matches
