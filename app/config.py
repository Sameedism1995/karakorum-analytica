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
        default="http://localhost:8501,http://127.0.0.1:8501,http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated CORS origins",
    )

    # Supabase — set SUPABASE_DB_URL (recommended) or URL + DB password
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket_name: str = ""
    supabase_db_url: str = ""
    supabase_db_password: str = ""

    scraper_api_key: str = ""
    proxy_urls: str = Field(
        default="",
        description="Comma-separated HTTP(S) proxy URLs for news fetching",
    )
    scraper_use_curl_cffi: bool = False
    scraper_respect_robots: bool = True
    scraper_request_delay_seconds: float = 1.5
    scraper_max_retries: int = 3
    scraper_user_agent: str = ""
    news_channel_feeds: str = Field(
        default="",
        description="Comma-separated Name|RSS_URL entries for open news channels",
    )

    reliefweb_appname: str = ""

    acled_email: str = ""
    acled_api_key: str = ""

    x_posting_enabled: bool = False
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_bearer_token: str = ""

    scweet_enabled: bool = False
    scweet_auth_token: str = ""
    scweet_email: str = ""
    scweet_password: str = ""
    scweet_username: str = ""
    scweet_cookies_file: str = ""
    scweet_db_path: str = "data/scweet_state.db"
    scweet_search_queries: str = Field(
        default="",
        description="Comma-separated X search queries for Scweet (default: Pakistan security query)",
    )
    scweet_limit: int = 50
    scweet_since_days: int = 7
    scweet_proxy: str = ""
    scweet_lang: str = "en"
    scweet_auto_login: bool = True
    scweet_login_headless: bool = True
    scweet_session_cache_path: str = "data/scweet_session.json"

    render_api_key: str = ""
    render_scweet_service_names: str = (
        "karakorum-analytica-api,karakorum-analytica-dashboard"
    )
    # Optional comma-separated Render service IDs (srv-...) — skips name lookup when set
    render_scweet_service_ids: str = ""

    # LLM newsroom (optional — placeholder templates used when unset)
    llm_provider: str = "placeholder"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    llm_dashboard_path: str = "llm-dashboard/dist"

    @property
    def render_scweet_service_names_list(self) -> list[str]:
        if not self.render_scweet_service_names.strip():
            return []
        return [
            name.strip()
            for name in self.render_scweet_service_names.replace("\n", ",").split(",")
            if name.strip()
        ]

    @property
    def render_scweet_service_ids_list(self) -> list[str]:
        if not self.render_scweet_service_ids.strip():
            return []
        return [
            sid.strip()
            for sid in self.render_scweet_service_ids.replace("\n", ",").split(",")
            if sid.strip()
        ]

    @property
    def scweet_search_queries_list(self) -> list[str]:
        if not self.scweet_search_queries.strip():
            return []
        return [q.strip() for q in self.scweet_search_queries.replace("\n", ",").split(",") if q.strip()]

    @property
    def scweet_configured(self) -> bool:
        if not self.scweet_enabled:
            return False
        if self.scweet_auth_token.strip() or self.scweet_cookies_file.strip():
            return True
        if self.scweet_password.strip() and (
            self.scweet_username.strip() or self.scweet_email.strip()
        ):
            return True
        from pathlib import Path

        return Path(self.scweet_db_path.strip() or "data/scweet_state.db").is_file()

    @property
    def x_oauth_configured(self) -> bool:
        """OAuth 1.0a user keys — required to post tweets."""
        return all(
            (
                self.x_api_key.strip(),
                self.x_api_secret.strip(),
                self.x_access_token.strip(),
                self.x_access_token_secret.strip(),
            )
        )

    @property
    def x_configured(self) -> bool:
        """Any X API credentials present (OAuth and/or bearer)."""
        return self.x_oauth_configured or bool(self.x_bearer_token.strip())

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
        return "supabase.co" in self.effective_database_url.lower()

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
