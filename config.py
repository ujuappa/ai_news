"""설정 로딩: sources.yaml 를 읽어 settings 와 활성 소스 목록을 제공."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent
SOURCES_FILE = ROOT / "sources.yaml"
# admin 페이지가 GitHub Contents API 로 덮어쓰는 두 파일. sources.yaml 은 **손 편집 전용**으로
# 남는다 — 주석 240줄이 결정 근거라서, 브라우저에서 YAML 을 다시 뱉으면 통째로 날아간다.
# 그래서 기계가 쓰는 소스 변경은 sources.yaml 을 고치지 않고 이 오버레이에 쌓는다.
#
# **YAML 이 아니라 JSON 인 이유**: 이 두 파일은 브라우저가 쓴다. 파이썬과 JS 가 둘 다
# 표준 라이브러리로 무손실 왕복할 수 있어야 하는데, 클라이언트에서 YAML 을 직렬화하려면
# 외부 의존성을 CDN 에서 끌어오거나 손으로 emitter 를 짜야 하고, 둘 다 설정 파일을 깨뜨리는
# 경로다. 대신 주석을 못 쓰므로 `_comment` 배열을 관례로 둔다(admin 이 보존한다).
TOPICS_FILE = ROOT / "topics.json"
CUSTOM_SOURCES_FILE = ROOT / "sources.custom.json"

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

# 토픽 = 카테고리와 **직교하는 두 번째 축**. 카테고리가 "어떤 종류의 사건인가"(모델 출시 ·
# 연구 · 제품 · 정책)라면 토픽은 "무엇에 관한 이야기인가"(음악 · 정부 · 코드)다.
# "AI 음악 스타트업이 5천만 달러를 유치" 는 policy_business 사건이면서 music 토픽이다.
#
# **CATEGORY_ORDER 와 절대 합치지 말 것.** 그 상수는 `sources.yaml` 의 최상위 소스 그룹 키를
# 겸하고 있어서(config.load 참고), 여기에 토픽을 넣으면 곧바로 소스 버킷이 되어버린다.
#
# 홈 필터 pill 전용이다(2026-08-04, 사용자 지시: "상단 카테고리는 두고 필터만 교체").
# 순서는 pill 동점일 때의 tie-break 로도 쓰이므로 아카이브 실측 빈도순으로 둔다.
#
# **2026-08-11: 어휘가 `topics.yaml` 로 나갔다**(admin 페이지가 브라우저에서 편집하려면
# 코드가 아니라 데이터여야 한다). 아래 세 상수는 그 파일에서 파생된 값이고, 이름은 그대로
# 남긴다 — llm.py·render.py·테스트가 이미 이 이름으로 임포트하고 있다.

# 파일이 없거나 깨졌을 때 쓰는 내장 폴백. 파이프라인은 매일 자동으로 도는데, YAML 오타
# 하나로 분류가 통째로 멈추면 그날 지면이 안 나온다 → 어휘가 사라지는 것보다 예전 어휘로
# 도는 게 낫다. `topics.yaml` 을 지우면 여기로 돌아온다.
_FALLBACK_TOPICS: list[tuple[str, str, str]] = [
    ("code", "Code", "software engineering, developer tools, programming"),
    ("money", "Money & markets", "funding, valuations, IPOs, acquisitions, stock moves"),
    ("chips", "Chips & datacenters", "semiconductors, GPUs, datacenters, compute infrastructure"),
    ("government", "Government & law", "regulation, legislation, courts, defense, the public sector"),
    ("security", "Security", "cyberattacks, vulnerabilities, fraud, model misuse"),
    ("science", "Science", "physics, chemistry, biology, mathematics, climate research"),
    ("health", "Health", "medicine, clinical care, drug discovery, patients"),
    ("art", "Art & images", "image generation, design, visual artists"),
    ("music", "Music & audio", "music generation, audio, voice"),
    ("video", "Video & film", "video generation, film, animation"),
    ("robotics", "Robotics", "robots, drones, embodied AI"),
    ("cars", "Cars & driving", "autonomous driving, vehicles"),
    ("education", "Education", "schools, students, teaching, training people"),
]

# 토픽 키에 허용되는 문자. 공백을 막는 게 핵심이다 — `data-topics` 가 공백으로 구분된
# 목록이고 필터 매칭이 `' '+key+' '` 라서, 키에 공백이 있으면 하나의 토픽이 두 개의 가짜
# 토큰으로 쪼개져 필터가 조용히 어긋난다. 대문자도 막는다(llm.clean_topics 가 lower() 로
# 비교해서, 대문자 키는 절대 매칭되지 않는 죽은 pill 이 된다).
_TOPIC_KEY_OK = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class Topic:
    """필터 토픽 하나. gloss 는 화면에 안 나가고 LLM 프롬프트에만 쓰인다."""
    key: str
    label: str
    gloss: str


def load_topics(path: Path | None = None) -> tuple[list[Topic], int]:
    """`topics.json` → (토픽 목록, 항목당 상한). 읽을 수 없으면 내장 폴백.

    조용히 버리는 것들(전부 필터를 깨뜨리는 값이다):
      - key 가 없거나 `[a-z0-9_]` 밖인 항목
      - 같은 key 의 두 번째 등장(먼저 온 것이 이긴다)
    label 이 없으면 key 를, gloss 가 없으면 label 을 쓴다 — gloss 누락으로 llm.py 가
    임포트 시점에 KeyError 로 죽는 걸 막는다.
    """
    fallback = ([Topic(k, l, g) for k, l, g in _FALLBACK_TOPICS], 3)
    path = path or TOPICS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback
    if not isinstance(data, dict):
        return fallback

    topics: list[Topic] = []
    seen: set[str] = set()
    for row in data.get("topics") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        if not _TOPIC_KEY_OK.match(key) or key in seen:
            continue
        seen.add(key)
        label = str(row.get("label") or key).strip() or key
        topics.append(Topic(key, label, str(row.get("gloss") or label).strip()))
    if not topics:
        return fallback   # 빈 어휘는 필터를 통째로 없애는 것과 같다 → 사고로 취급한다

    try:
        cap = int(data.get("max_per_item", 3))
    except (TypeError, ValueError):
        cap = 3
    return topics, max(1, cap)


TOPICS, MAX_TOPICS_PER_ITEM = load_topics()
TOPIC_ORDER = [t.key for t in TOPICS]
TOPIC_LABELS = {t.key: t.label for t in TOPICS}
# LLM 프롬프트에 넣는 경계 설명. llm.py 가 이걸로 SYSTEM 을 조립한다.
TOPIC_GLOSS = {t.key: t.gloss for t in TOPICS}


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
    # admin 페이지가 커밋할 대상 레포(`owner/name`). 비밀값이 아니다 — 쓰기 권한은 사용자가
    # 브라우저에 넣는 PAT 이 갖고, 그 토큰은 이 설정에도 산출물에도 들어가지 않는다.
    github_repo: str = ""
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


def load(path: Path = SOURCES_FILE,
         overlay: Path | None = CUSTOM_SOURCES_FILE) -> Config:
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
        github_repo=str(s.get("github_repo") or "").strip().strip("/"),
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
            sources.append(_source_from_row(row, category))
    return Config(settings=settings, sources=_apply_overlay(sources, overlay))


def _source_from_row(row: dict, category: str) -> Source:
    return Source(
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


# 오버레이에서 부분 수정으로 받을 수 있는 필드. 여기 없는 키는 무시한다 — `id` 를 바꾸는
# 수정은 특히 막아야 한다(그건 수정이 아니라 다른 소스이고, items.source_id 와의 연결이
# 끊어져서 소스 페이지의 과거 집계가 통째로 미아가 된다).
_OVERRIDABLE = ("name", "feed_url", "category", "parse", "status", "enabled",
                "full_text", "sitemap_paths", "max_entries", "notes")


def _apply_overlay(base: list[Source], path: Path | None) -> list[Source]:
    """`sources.custom.json` 을 base 위에 얹는다. 파일이 없으면 base 그대로.

    admin 페이지(브라우저)가 쓰는 파일이라 **sources.yaml 은 건드리지 않는다** — 그 파일은
    주석 240줄이 결정 근거이고, 클라이언트에서 YAML 을 파싱해 다시 뱉으면 전부 사라진다.

    항목 의미(모두 `id` 로 매칭):
      - base 에 없는 id  → 새 소스 추가(name·feed_url·category 필요)
      - base 에 있는 id  → 준 필드만 덮어씀(예: `enabled: false` 하나만)
      - `deleted: true`  → 목록에서 아예 뺀다. sources.yaml 은 그대로라 되돌릴 수 있다
                           (오버레이에서 그 항목을 지우면 원래대로 돌아온다)

    깨진 항목은 조용히 건너뛴다. 이 파일은 브라우저가 쓰는데 파이프라인은 무인으로 도니까,
    항목 하나의 오타로 그날 수집이 통째로 죽는 것보다 그 항목만 빠지는 게 낫다.
    """
    if path is None or not path.exists():
        return base
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return base
    if not isinstance(data, dict):
        return base

    by_id = {s.id: s for s in base}
    order = [s.id for s in base]
    for row in data.get("sources") or []:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue

        if row.get("deleted"):
            by_id.pop(sid, None)
            continue

        if sid in by_id:
            patch = {k: row[k] for k in _OVERRIDABLE if k in row}
            if not patch:
                continue
            merged = {**_row_of(by_id[sid]), **patch}
            category = str(merged.get("category") or by_id[sid].category)
            try:
                by_id[sid] = _source_from_row(merged, category)
            except (KeyError, TypeError, ValueError):
                continue
            continue

        # 새 소스. 세 필드가 없으면 fetch 가 어차피 못 쓴다 → 여기서 버린다.
        if not (row.get("name") and row.get("feed_url")):
            continue
        category = str(row.get("category") or "").strip()
        if category not in CATEGORY_ORDER:
            continue
        try:
            by_id[sid] = _source_from_row(row, category)
        except (KeyError, TypeError, ValueError):
            continue
        order.append(sid)

    merged_list = [by_id[i] for i in order if i in by_id]
    # 카테고리 그룹을 유지한다(새 소스는 자기 카테고리 끝으로). 소스 페이지와 파이프라인이
    # 둘 다 이 순서를 그대로 쓰므로, 추가한 소스가 남의 카테고리 사이에 끼면 지면이 흐트러진다.
    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    return sorted(merged_list, key=lambda s: rank.get(s.category, len(rank)))


def _row_of(src: Source) -> dict:
    """Source → sources.yaml 행 모양. 오버레이 부분수정을 병합할 때만 쓴다."""
    return {
        "id": src.id, "name": src.name, "feed_url": src.feed_url,
        "category": src.category, "parse": src.parse, "status": src.status,
        "enabled": src.enabled, "full_text": src.full_text,
        "sitemap_paths": list(src.sitemap_paths), "max_entries": src.max_entries,
        "notes": src.notes,
    }


# 환경변수
# 인증은 genai.Client() 가 .env 의 GOOGLE_GENAI_USE_VERTEXAI/GOOGLE_CLOUD_PROJECT/
# GOOGLE_CLOUD_LOCATION/GOOGLE_APPLICATION_CREDENTIALS 로 자동 처리 (Vertex AI 모드)
MODEL = os.environ.get("DIGEST_MODEL", "gemini-3.1-pro-preview")  # thinking 기본 ON. 비용 부담되면 gemini-2.5-flash
OUTPUT_DIR = ROOT / "output"
DB_PATH = ROOT / "digest.db"

def github_repo() -> str:
    """admin 페이지가 커밋할 레포(`owner/name`). 없으면 "" — admin 이 직접 입력받는다.

    원본은 `sources.yaml` 의 `settings.github_repo` 이고 `DIGEST_GITHUB_REPO` 로 덮어쓸 수
    있다(포크에서 굽거나 테스트할 때). **비밀값이 아니다** — 공개 레포 주소이고, 쓰기 권한은
    사용자가 브라우저에 넣는 PAT 이 갖는다.

    모듈 상수가 아니라 함수인 이유: 상수로 두면 `import config` 마다 sources.yaml 을 한 번 더
    파싱한다(대부분의 모듈은 이 값을 쓰지 않는다).
    """
    env = os.environ.get("DIGEST_GITHUB_REPO")
    if env:
        return env.strip().strip("/")
    try:
        return load().settings.github_repo
    except (OSError, yaml.YAMLError, KeyError):
        return ""
