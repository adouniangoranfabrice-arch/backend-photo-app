from datetime import datetime, timezone

from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request
)

from app.core.database import users_collection
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)

from app.models.users import UserRole

from app.schemas.users import UserResponse

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
)

from app.services.activity_logger import create_activity_log

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    request: RegisterRequest,
    http_request: Request
):

    email = request.email.strip().lower()

    # Vérifier si l'email existe déjà
    existing_user = users_collection.find_one({
        "email": email
    })

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Cette adresse email est déjà utilisée"
        )

    # Vérifier la longueur du mot de passe
    password_bytes = len(
        request.password.encode("utf-8")
    )

    if password_bytes > 72:
        raise HTTPException(
            status_code=400,
            detail="Le mot de passe ne doit pas dépasser 72 octets."
        )

    # Création de l'utilisateur
    user = {
        "firstname": request.firstname.strip(),
        "lastname": request.lastname.strip(),
        "email": email,
        "password_hash": hash_password(request.password),
        "role": UserRole.PHOTOGRAPHER.value,
        "business_name": request.business_name,
        "is_active": True,
        "bio": request.bio,
        "city": request.city,
        "phone": request.phone,
        "website": request.website,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = users_collection.insert_one(user)

    # Informations de la requête HTTP
    client_ip = (
        http_request.client.host
        if http_request.client
        else None
    )

    user_agent = http_request.headers.get(
        "user-agent"
    )

    # Journalisation
    create_activity_log(
        user_id=str(result.inserted_id),

        user_role="PHOTOGRAPHER",

        action="REGISTER",

        resource="user",
        resource_id=str(result.inserted_id),

        description="s'est inscrit",

        target="Photiva",

        ip_address=client_ip,

        user_agent=user_agent
    )

    # Réponse
    response = {
        "id": str(result.inserted_id),
        "firstname": user["firstname"],
        "lastname": user["lastname"],
        "email": user["email"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
        "updated_at": datetime.now(timezone.utc)
        
    }

    return response

# Login
@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    request: Request,
    data: LoginRequest
):

    # =========================
    # 1. Rechercher l'utilisateur
    # =========================

    user = users_collection.find_one({
        "email": data.email.lower()
    })

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    # =========================
    # 2. Vérifier le mot de passe
    # =========================

    if not verify_password(
        data.password,
        user["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    # =========================
    # 3. Vérifier si le compte est actif
    # =========================

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=403,
            detail="Votre compte est désactivé"
        )

    # =========================
    # 4. Générer le JWT
    # =========================

    token = create_access_token(
        user_id=str(user["_id"]),
        role=user["role"]
    )

    # =========================
    # 5. Enregistrer l'activité
    # =========================

    create_activity_log(
        user_id=str(user["_id"]),
        user_role=user.get("role"),

        action="LOGIN",

        resource="user",
        resource_id=str(user["_id"]),

        description="s'est connecté",

        ip_address=(
            request.client.host
            if request.client
            else None
        ),

        user_agent=request.headers.get(
            "user-agent"
        )
    )

    # =========================
    # 6. Retourner le token
    # =========================

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"]
    }