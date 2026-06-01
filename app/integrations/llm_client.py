"""LLM inference client — placeholder templates with optional OpenAI hook."""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger

from app.config import get_settings


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


SENSATIONAL_WORDS = (
    "breaking",
    "shocking",
    "massacre",
    "bloodbath",
    "devastating",
    "horrific",
    "unconfirmed reports confirm",
    "sources say definitely",
    "confirmed dead",
    "officially confirmed",
)

PROPAGANDA_PATTERNS = (
    r"\b(enemy|traitor|infidel|crusade|jihad against)\b",
    r"\b(heroic victory|glorious defeat|total annihilation)\b",
)

CASUALTY_PATTERN = re.compile(
    r"\b(\d+)\s+(killed|dead|casualties|injured|wounded| martyrs?)\b",
    re.IGNORECASE,
)

GRADE_WEIGHT = {"A": 0, "B": 8, "C": 18, "D": 32, "E": 45}


class LLMClient:
    """Local placeholder inference; swap `complete()` for real LLM later."""

    def __init__(self) -> None:
        settings = get_settings()
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.api_key = settings.openai_api_key.strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and self.provider == "openai"

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult:
        if self.is_configured:
            return self._openai_complete(system_prompt, user_prompt)
        combined = f"{system_prompt.strip()}\n\n{user_prompt.strip()}".strip()
        return LLMResult(text=combined, provider="placeholder", model="template-v1")

    def _openai_complete(self, system_prompt: str, user_prompt: str) -> LLMResult:
        try:
            import httpx

            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
            return LLMResult(text=text, provider="openai", model=self.model)
        except Exception as exc:
            logger.warning(f"OpenAI call failed, falling back to placeholder: {exc}")
            combined = f"{system_prompt.strip()}\n\n{user_prompt.strip()}".strip()
            return LLMResult(text=combined, provider="placeholder", model="template-v1")


def normalize_grade(grade: str) -> str:
    g = (grade or "C").strip().upper()[:1]
    return g if g in GRADE_WEIGHT else "C"


def has_verified_incident_text(text: str) -> bool:
    cleaned = (text or "").strip()
    return len(cleaned) >= 40


def split_keywords(raw: str) -> list[str]:
    if not raw.strip():
        return []
    parts = re.split(r"[,;\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug[:80].strip("-") or "karakorum-analytica-update"


def detect_sensational(text: str) -> list[str]:
    lower = text.lower()
    return [word for word in SENSATIONAL_WORDS if word in lower]


def detect_propaganda(text: str) -> list[str]:
    found: list[str] = []
    for pattern in PROPAGANDA_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            found.append(match.group(0))
    return found


def detect_unsupported_claims(draft: str, source_info: str, raw_report: str) -> list[str]:
    claims: list[str] = []
    if CASUALTY_PATTERN.search(draft) and not CASUALTY_PATTERN.search(raw_report + source_info):
        claims.append("Casualty figures appear in draft but are not clearly supported by supplied source text.")
    if re.search(r"\b(confirmed|verified|official)\b", draft, re.IGNORECASE):
        if not re.search(r"\b(confirmed|verified|official)\b", raw_report + source_info, re.IGNORECASE):
            claims.append("Draft uses confirmation language not present in supplied source material.")
    if re.search(r"\b(arrested|killed|explosion|attack)\b", draft, re.IGNORECASE):
        if len((raw_report + source_info).strip()) < 30:
            claims.append("Specific incident claims lack sufficient supporting source detail.")
    return claims


def compute_risk_score(
    draft: str,
    source_grade: str,
    unsupported: list[str],
    sensational: list[str],
    propaganda: list[str],
) -> int:
    score = GRADE_WEIGHT.get(normalize_grade(source_grade), 18)
    score += min(len(unsupported) * 12, 36)
    score += min(len(sensational) * 8, 24)
    score += min(len(propaganda) * 10, 20)
    if CASUALTY_PATTERN.search(draft):
        score += 10
    return min(max(score, 0), 100)


def publish_status_from_score(score: int) -> tuple[str, str]:
    if score <= 25:
        return "safe_to_publish", "Safe to publish"
    if score <= 45:
        return "publish_with_caution", "Publish with caution"
    if score <= 70:
        return "needs_verification", "Needs verification"
    return "do_not_publish", "Do not publish as confirmed"
