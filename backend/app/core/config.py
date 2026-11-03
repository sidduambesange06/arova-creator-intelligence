from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Arova Creator Intelligence"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver"

    # Optional local authentication token. When unset (None), local desktop access is unauthenticated.
    API_AUTH_TOKEN: str | None = None
    ADMIN_AUTH_TOKEN: str | None = None

    DATA_DIR: str = "./data"
    SQLITE_DB_PATH: str = "./data/app.db"
    CHROMA_PERSIST_DIR: str = "./data/vectors"
    MEDIA_STORAGE_DIR: str = "./data/media"
    # Safe default: restrict probing strictly to the project's media storage dir.
    # Production / multi-directory setups configure via ALLOWED_MEDIA_ROOTS env var.
    ALLOWED_MEDIA_ROOTS: str = "./data/media"

    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # External AI configuration — remote egress requires explicit user consent
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    AI_REMOTE_CONSENT: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip().lower() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @model_validator(mode="after")
    def validate_network_binding_security(self) -> "Settings":
        loopback_hosts = {"127.0.0.1", "localhost", "::1"}
        host = self.API_HOST.strip().lower()
        if host not in loopback_hosts:
            if not self.API_AUTH_TOKEN or not self.API_AUTH_TOKEN.strip():
                raise RuntimeError(
                    f"Unsafe network binding: Server configured to bind to non-loopback host '{self.API_HOST}' "
                    "without API_AUTH_TOKEN. Network-exposed instances must require authentication."
                )
        return self


settings = Settings()
