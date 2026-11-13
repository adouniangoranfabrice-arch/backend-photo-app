import certifi
from pymongo import MongoClient

from app.core.config import settings


client = MongoClient(
    settings.MONGODB_URL,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
)


database = client[settings.MONGODB_DATABASE]

users_collection = database["users"]
events_collection = database["events"]
photos_collection = database["photos"]
faces_collection = database["faces"]
activity_logs_collection = database["activity_logs"]
# Recherches par selfie et téléchargements effectués sur les galeries publiques
gallery_stats_collection = database["gallery_stats"]


activity_logs_collection.create_index(
    [("created_at", -1)]
)

activity_logs_collection.create_index(
    [("user_id", 1)]
)

activity_logs_collection.create_index(
    [("photographer_id", 1)]
)

activity_logs_collection.create_index(
    [("action", 1)]
)

activity_logs_collection.create_index(
    [("resource", 1)]
)

gallery_stats_collection.create_index(
    [("user_id", 1), ("type", 1), ("created_at", -1)]
)

photos_collection.create_index([("user_id", 1), ("created_at", -1)])
events_collection.create_index([("user_id", 1), ("created_at", -1)])
faces_collection.create_index([("event_id", 1)])


def get_database():
    return database