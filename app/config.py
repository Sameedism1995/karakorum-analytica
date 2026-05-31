from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "pakistan-osint-news-mvp"
    app_env: str = "development"
    debug: bool = True

    database_url: str = "sqlite:///./local.db"
    collection_interval_minutes: int = 15

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
    def acled_configured(self) -> bool:
        return bool(self.acled_email and self.acled_api_key)


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
