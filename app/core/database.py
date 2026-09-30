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
photographers_collection = database["photographers"]
events_collection = database["events"]
photos_collection = database["photos"]
faces_collection = database["faces"]

def get_database():
    return database