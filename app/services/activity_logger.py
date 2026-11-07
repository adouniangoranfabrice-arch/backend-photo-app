from datetime import datetime, timezone

from app.core.database import activity_logs_collection


def create_activity_log(
    *,
    user_id: str | None = None,
    photographer_id: str | None = None,
    user_role: str | None = None,

    action: str,

    resource: str | None = None,
    resource_id: str | None = None,

    description: str | None = None,
    target: str | None = None,

    ip_address: str | None = None,
    user_agent: str | None = None,

    metadata: dict | None = None
):
    """
    Enregistre une activité dans MongoDB.
    """

    activity = {
        "user_id": user_id,
        "photographer_id": photographer_id,
        "user_role": user_role,

        "action": action,

        "resource": resource,
        "resource_id": resource_id,

        "description": description,
        "target": target,

        "ip_address": ip_address,
        "user_agent": user_agent,

        "metadata": metadata or {},

        "created_at": datetime.now(timezone.utc)
    }

    result = activity_logs_collection.insert_one(activity)

    activity["_id"] = result.inserted_id

    return activity