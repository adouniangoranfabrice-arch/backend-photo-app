from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import (
    auth,
    users,
    admin,
    photographer,
    event,
    photo,
    face,
    public
)


app = FastAPI(
    title="Photiva API",
    description="API de la plateforme Photiva",
    version="1.0.0"
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

app.include_router(
    photographer.router,
    prefix="/api"
)

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
    public.router,
    prefix="/api"
)
