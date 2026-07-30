"""설정 로딩: sources.yaml 를 읽어 settings 와 활성 소스 목록을 제공."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent
SOURCES_FILE = ROOT / "sources.yaml"

load_dotenv(ROOT / ".env")  # GEMINI_API_KEY 등 비밀값은 .env(gitignored)에만 둠, 채팅에 붙여넣지 말 것

# v1 카테고리 (community_takes 는 sources.yaml 에서 전부 enabled:false 로 꺼둠)
CATEGORY_ORDER = [
    "model_releases",
    "research",
    "tools_products",
    "policy_business",
    "community_takes",
]
CATEGORY_LABELS = {
    "model_releases": "Model releases",
    "research": "Research",
    "tools_products": "Tools & products",
    "policy_business": "Policy & business",
    "community_takes": "Community takes",
}


@dataclass
class Source:
    id: str
    name: str
    feed_url: str
    category: str
    parse: str = "easy"
    status: str = "verify"
    enabled: bool = True
    full_text: bool = False   # 기사 본문 추출(trafilatura) 여부. 기본 off — 비용/시간이 붙는다
    notes: str = ""


@dataclass
class Settings:
    max_items_per_category: int = 6
    min_items_fallback: bool = True
    flag_major_at_top: bool = True
    preserve_key_numbers_verbatim: bool = True
    min_significance: float = 0.25
    max_item_age_days: int = 7
    dedup_threshold: float = 0.83
    dedup_cross_day: bool = True
    seen_store_retention_days: int = 14
    ranking_rubric: list[str] = field(default_factory=list)


@dataclass
class Config:
    settings: Settings
    sources: list[Source]

    def enabled_sources(self) -> list[Source]:
        return [s for s in self.sources if s.enabled]


def load(path: Path = SOURCES_FILE) -> Config:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    s = data.get("settings", {})
    dedup = s.get("dedup", {})
    settings = Settings(
        max_items_per_category=s.get("max_items_per_category", 6),
        min_items_fallback=s.get("min_items_fallback", True),
        flag_major_at_top=s.get("flag_major_at_top", True),
        preserve_key_numbers_verbatim=s.get("preserve_key_numbers_verbatim", True),
        min_significance=s.get("min_significance", 0.25),
        max_item_age_days=s.get("max_item_age_days", 7),
        dedup_threshold=dedup.get("threshold", 0.83),
        dedup_cross_day=dedup.get("cross_day", True),
        seen_store_retention_days=dedup.get("seen_store_retention_days", 14),
        ranking_rubric=s.get("ranking_rubric", []),
    )

    sources: list[Source] = []
    for category in CATEGORY_ORDER:
        for row in data.get(category, []) or []:
            sources.append(
                Source(
                    id=row["id"],
                    name=row["name"],
                    feed_url=row["feed_url"],
                    category=category,
                    parse=row.get("parse", "easy"),
                    status=row.get("status", "verify"),
                    enabled=bool(row.get("enabled", True)),
                    full_text=bool(row.get("full_text", False)),
                    notes=row.get("notes", ""),
                )
            )
    return Config(settings=settings, sources=sources)


# 환경변수
# 인증은 genai.Client() 가 .env 의 GOOGLE_GENAI_USE_VERTEXAI/GOOGLE_CLOUD_PROJECT/
# GOOGLE_CLOUD_LOCATION/GOOGLE_APPLICATION_CREDENTIALS 로 자동 처리 (Vertex AI 모드)
MODEL = os.environ.get("DIGEST_MODEL", "gemini-2.5-flash")  # 고볼륨이면 gemini-2.5-flash-lite 로 비용 절감
OUTPUT_DIR = ROOT / "output"
DB_PATH = ROOT / "digest.db"
