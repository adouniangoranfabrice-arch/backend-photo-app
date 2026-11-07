from fastapi import APIRouter
from app.core.database import database
router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


@router.get("/stats")
def get_stats():
    photographers_count = database["users"].count_documents({
        "role": "PHOTOGRAPHER"
    })

    events_count = database["events"].count_documents({})

    photos_count = database["photos"].count_documents({})

    return {
        "photographers": photographers_count,
        "events": events_count,
        "photos": photos_count
    }