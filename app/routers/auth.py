from datetime import datetime, timezone

from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
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

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(request: RegisterRequest):

    email = request.email.strip().lower()

    existing_user = users_collection.find_one({
        "email": email
    })

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Cette adresse email est déjà utilisée"
        )

    password_bytes = len(
        request.password.encode("utf-8")
    )

    if password_bytes > 72:
        raise HTTPException(
            status_code=400,
            detail="Le mot de passe ne doit pas dépasser 72 octets."
        )

    user = {
        "firstname": request.firstname.strip(),
        "lastname": request.lastname.strip(),
        "email": email,
        "password_hash": hash_password(request.password),
        "role": UserRole.PHOTOGRAPHER.value,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }

    result = users_collection.insert_one(user)

    response = {
        "id": str(result.inserted_id),
        "firstname": user["firstname"],
        "lastname": user["lastname"],
        "email": user["email"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"]
    }

    print("RESPONSE :", response)

    return response

# Login
@router.post(
    "/login",
    response_model=TokenResponse
)
def login(request: LoginRequest):

    user = users_collection.find_one({
        "email": request.email.lower()
    })

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    if not verify_password(
        request.password,
        user["password_hash"]
    ):

        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    if not user["is_active"]:

        raise HTTPException(
            status_code=403,
            detail="Votre compte est désactivé"
        )

    token = create_access_token(
        user_id=str(user["_id"]),
        role=user["role"]
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }