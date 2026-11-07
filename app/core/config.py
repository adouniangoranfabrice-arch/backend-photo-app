from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # MongoDB
    MONGODB_URL: str
    MONGODB_DATABASE: str
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # FRONTEND URL
    FRONTEND_URL: str

    # CORS : origines supplémentaires autorisées, séparées par des virgules
    # ex. "https://photiva.vercel.app,https://www.photiva.ci"
    CORS_ORIGINS: str = ""

    # CORS : expression régulière optionnelle (ex. previews Vercel)
    # ex. "https://front-end-app-photo.*\.vercel\.app"
    CORS_ORIGIN_REGEX: str | None = None

    @staticmethod
    def _clean_origin(value: str) -> str:
        # Retire espaces, guillemets et "/" final : "https://x.app/" -> https://x.app
        return value.strip().strip('"').strip("'").strip().rstrip("/")

    @property
    def cors_origins(self) -> list[str]:
        origins = {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            self._clean_origin(self.FRONTEND_URL),
        }
        origins.update(
            self._clean_origin(origin)
            for origin in self.CORS_ORIGINS.split(",")
        )
        return sorted(o for o in origins if o)

    @property
    def cors_origin_regex(self) -> str | None:
        if not self.CORS_ORIGIN_REGEX:
            return None
        return self._clean_origin(self.CORS_ORIGIN_REGEX) or None

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()