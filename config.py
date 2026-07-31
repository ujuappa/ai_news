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
    # parse: sitemap 전용. sitemap.xml 에서 긁어올 경로들. 기본은 뉴스만.
    sitemap_paths: list[str] = field(default_factory=lambda: ["/news/"])
    # 소스별 수집 상한. None 이면 fetch 기본값(25). 항목당 비용이 유별난 소스를 따로 조인다
    # (gnews 는 URL 디코딩에 항목당 ~567KB 가 붙어서 25 로 두면 매 실행 14MB·16초).
    max_entries: int | None = None
    notes: str = ""


@dataclass
class CategoryRule:
    """카테고리별 게재 규칙. max_items 는 상한, min_significance 는 하한.

    전역 하나로는 안 되는 이유: research 는 arXiv 때문에 후보가 50건씩 쌓이는데 7위 아래는
    일반 논문이고, tools_products 는 애초에 2건이라 캡이 의미가 없다(2026-07-30 측정)."""
    max_items: int
    min_significance: float


@dataclass
class Settings:
    max_items_per_category: int = 6
    min_items_fallback: bool = True
    flag_major_at_top: bool = True
    preserve_key_numbers_verbatim: bool = True
    min_significance: float = 0.25
    max_item_age_days: int = 7
    dedup_threshold: float = 0.83
    grounding_dedup_threshold: float = 0.78   # grounding 전용(더 엄격한 신규성 기준)
    dedup_cross_day: bool = True
    seen_store_retention_days: int = 14
    thread_min_similarity: float = 0.75       # 이 아래는 남남
    thread_max_similarity: float = 0.83       # 이 위는 중복(=dedup 이 합칠 것)
    embedding_retention_days: int = 180
    # RSS 피드용 사이트 기준 URL. RSS 는 상대경로를 허용하지 않아서 이게 없으면 피드를 만들 수
    # 없다(리더가 링크를 못 따라간다). 비어 있으면 render_feed 가 경고하고 건너뛴다.
    site_url: str = ""
    feed_max_digests: int = 20
    ranking_rubric: list[str] = field(default_factory=list)
    category_rules: dict[str, CategoryRule] = field(default_factory=dict)
    # grounding 소스 품질 게이트. None = llm.py 모듈 기본값 사용, [] = 필터 끄기.
    # (YAML 에 키가 없을 때 조용히 필터가 꺼지면 안 되므로 None 이 기본값이다)
    grounding_blocked_domains: list[str] | None = None
    grounding_blocked_url_patterns: list[str] | None = None

    def rule_for(self, category: str) -> CategoryRule:
        """설정에 없는 카테고리는 전역값으로 폴백 — 새 카테고리를 추가해도 안 죽는다."""
        return self.category_rules.get(
            category,
            CategoryRule(self.max_items_per_category, self.min_significance),
        )


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
    grounding = s.get("grounding") or {}
    rules = {
        cat: CategoryRule(
            max_items=int(row.get("max_items", s.get("max_items_per_category", 6))),
            min_significance=float(row.get("min_significance", s.get("min_significance", 0.25))),
        )
        for cat, row in (s.get("categories") or {}).items()
    }
    settings = Settings(
        max_items_per_category=s.get("max_items_per_category", 6),
        min_items_fallback=s.get("min_items_fallback", True),
        flag_major_at_top=s.get("flag_major_at_top", True),
        preserve_key_numbers_verbatim=s.get("preserve_key_numbers_verbatim", True),
        min_significance=s.get("min_significance", 0.25),
        max_item_age_days=s.get("max_item_age_days", 7),
        dedup_threshold=dedup.get("threshold", 0.83),
        grounding_dedup_threshold=dedup.get("grounding_threshold", 0.78),
        dedup_cross_day=dedup.get("cross_day", True),
        seen_store_retention_days=dedup.get("seen_store_retention_days", 14),
        thread_min_similarity=dedup.get("thread_min", 0.75),
        thread_max_similarity=dedup.get("thread_max", 0.83),
        embedding_retention_days=dedup.get("embedding_retention_days", 180),
        site_url=str(s.get("site_url") or "").strip(),
        feed_max_digests=int(s.get("feed_max_digests", 20)),
        ranking_rubric=s.get("ranking_rubric", []),
        category_rules=rules,
        # 키가 아예 없으면 None(=모듈 기본값). 빈 리스트로 명시하면 "필터 끄기"로 존중한다.
        grounding_blocked_domains=(list(grounding["blocked_domains"])
                                   if "blocked_domains" in grounding else None),
        grounding_blocked_url_patterns=(list(grounding["blocked_url_patterns"])
                                        if "blocked_url_patterns" in grounding else None),
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
                    sitemap_paths=list(row.get("sitemap_paths") or ["/news/"]),
                    max_entries=(int(row["max_entries"])
                                 if row.get("max_entries") is not None else None),
                    notes=row.get("notes", ""),
                )
            )
    return Config(settings=settings, sources=sources)


# 환경변수
# 인증은 genai.Client() 가 .env 의 GOOGLE_GENAI_USE_VERTEXAI/GOOGLE_CLOUD_PROJECT/
# GOOGLE_CLOUD_LOCATION/GOOGLE_APPLICATION_CREDENTIALS 로 자동 처리 (Vertex AI 모드)
MODEL = os.environ.get("DIGEST_MODEL", "gemini-3.1-pro-preview")  # thinking 기본 ON. 비용 부담되면 gemini-2.5-flash
OUTPUT_DIR = ROOT / "output"
DB_PATH = ROOT / "digest.db"
