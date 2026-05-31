from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "karakorum-analytica"
    app_display_name: str = "Karakorum Analytica"
    app_env: str = "development"
    environment: str = ""
    debug: bool = True

    database_url: str = "sqlite:///./local.db"
    collection_interval_minutes: int = 15
    scheduler_enabled: bool = True
    run_collection_on_startup: bool = False

    allowed_origins: str = Field(
        default="http://localhost:8501,http://127.0.0.1:8501",
        description="Comma-separated CORS origins",
    )

    # Supabase — set SUPABASE_DB_URL (recommended) or URL + DB password
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket_name: str = ""
    supabase_db_url: str = ""
    supabase_db_password: str = ""

    scraper_api_key: str = ""

    reliefweb_appname: str = ""

    acled_email: str = ""
    acled_api_key: str = ""

    x_posting_enabled: bool = False
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_bearer_token: str = ""

    @property
    def runtime_environment(self) -> str:
        return (self.environment or self.app_env or "development").strip()

    @property
    def is_production(self) -> bool:
        return self.runtime_environment.lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        raw = self.allowed_origins.strip()
        if not raw:
            return ["http://localhost:8501", "http://127.0.0.1:8501"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def acled_configured(self) -> bool:
        return bool(self.acled_email and self.acled_api_key)

    @property
    def supabase_project_ref(self) -> str:
        if not self.supabase_url:
            return ""
        host = self.supabase_url.replace("https://", "").replace("http://", "").strip("/")
        return host.split(".")[0]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def using_supabase(self) -> bool:
        url = self.effective_database_url.lower()
        return "supabase.co" in url or (
            url.startswith("postgresql") and self.supabase_configured
        )

    @property
    def database_backend(self) -> str:
        url = self.effective_database_url.lower()
        if "supabase.co" in url:
            return "supabase"
        if url.startswith("postgresql"):
            return "postgresql"
        return "sqlite"

    @property
    def effective_database_url(self) -> str:
        """Resolve DB URL: explicit Supabase/Postgres URL, built URL, or SQLite fallback."""
        if self.supabase_db_url.strip():
            return self._normalize_postgres_url(self.supabase_db_url.strip())

        if self.database_url.strip() and not self.database_url.startswith("sqlite"):
            return self._normalize_postgres_url(self.database_url.strip())

        if self.supabase_url and self.supabase_db_password:
            ref = self.supabase_project_ref
            if ref:
                password = quote_plus(self.supabase_db_password)
                return (
                    f"postgresql+psycopg://postgres:{password}"
                    f"@db.{ref}.supabase.co:5432/postgres"
                )

        return self.database_url

    @staticmethod
    def _normalize_postgres_url(url: str) -> str:
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


# Equal weight per API source (Phase 1)
SOURCE_WEIGHT = 33.33
SOURCE_NAMES = ("GDELT", "ReliefWeb", "ACLED")

PAKISTAN_AREAS = [
    "balochistan",
    "khyber pakhtunkhwa",
    "punjab",
    "sindh",
    "islamabad",
    "pakistan-afghanistan border",
    "waziristan",
    "khyber",
    "quetta",
    "peshawar",
    "gwadar",
    "karachi",
    "lahore",
    "pakistan",
]

TARGET_KEYWORDS = [
    "blast",
    "explosion",
    "ied",
    "firing",
    "attack",
    "clash",
    "militant",
    "terrorism",
    "arrest",
    "operation",
    "protest",
    "border",
    "afghanistan",
    "balochistan",
    "kp",
    "quetta",
    "peshawar",
    "waziristan",
    "khyber",
    "gwadar",
    "karachi",
    "police",
    "ctd",
    "security forces",
    "checkpoint",
    "grenade",
    "suicide attack",
    "target killing",
    "abduction",
    "kidnapping",
]

PROVINCE_MAP = {
    "balochistan": "Balochistan",
    "quetta": "Balochistan",
    "gwadar": "Balochistan",
    "khyber pakhtunkhwa": "Khyber Pakhtunkhwa",
    "kp": "Khyber Pakhtunkhwa",
    "peshawar": "Khyber Pakhtunkhwa",
    "waziristan": "Khyber Pakhtunkhwa",
    "khyber": "Khyber Pakhtunkhwa",
    "punjab": "Punjab",
    "lahore": "Punjab",
    "sindh": "Sindh",
    "karachi": "Sindh",
    "islamabad": "Islamabad",
    "pakistan-afghanistan border": "Border",
}


@lru_cache
def get_settings() -> Settings:
    return Settings()
