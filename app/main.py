from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth,
    users,
    admin,
    photographer,
    event,
    photo,
    face,
    stats_admin,
    stats_liste_users,
    admin_logs,
    public
)


app = FastAPI(
    title="Photiva API",
    description="API de la plateforme Photiva",
    version="1.0.0"
)

# =========================
# CORS
# =========================

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# DOSSIER DES FICHIERS
# =========================================================

app.mount(
    "/uploads",
    StaticFiles(
        directory="uploads"
    ),
    name="uploads"
)



app.include_router(
    auth.router,
    prefix="/api"
)

app.include_router(
    users.router,
    prefix="/api"
)

app.include_router(
    admin.router,
    prefix="/api"
)

# app.include_router(
#     photographer.router,
#     prefix="/api"
# )

app.include_router(
    event.router,
    prefix="/api"
)

app.include_router(
    event.router,
    prefix="/api"
)

app.include_router(
    photo.router,
    prefix="/api"
)

app.include_router(
    face.router,
    prefix="/api"
)

app.include_router(
    admin_logs.router,
    prefix="/api"
)

app.include_router(
    stats_admin.router,
    prefix="/api"
)

app.include_router(
    stats_liste_users.router,
    prefix="/api"
)

app.include_router(
    public.router,
    prefix="/api"
)
