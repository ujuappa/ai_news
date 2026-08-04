"""소스/주체 마크 카탈로그: `static/img/` 의 파일 목록 -> LLM 후보 키 -> 렌더 경로.

**render.py 가 아니라 별도 모듈인 이유**: 같은 카탈로그를 두 방향에서 쓴다.
  - `llm.enrich` 는 "고를 수 있는 키 목록"이 프롬프트에 들어가야 하고(pipeline 이 넘긴다),
  - `render` 는 저장된 키를 파일 경로로 되돌려야 한다.
render 가 LLM 을 알거나 llm 이 렌더를 import 하는 걸 피하려고 가운데로 뺐다.

카탈로그의 원본은 **디스크의 파일 이름**이다(설정 파일이 아니라). 키 = 확장자 뺀 파일명:
`static/img/openai.svg` -> `openai`. 파일을 넣으면 다음 실행부터 LLM 후보에 자동으로 들어가고,
빼면 자동으로 빠진다 — 목록을 두 군데 관리하다 어긋나는 걸 막는다.
사람이 읽는 이름(LLM 프롬프트용)만 선택적으로 `static/img/catalog.yaml` 에 적는다.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

STATIC_DIR = Path(__file__).parent / "static"
IMG_DIR = STATIC_DIR / "img"
CATALOG_FILE = IMG_DIR / "catalog.yaml"

# 확장자 우선순위 = 이 순서(먼저 찾은 게 이긴다). svg 가 맨 앞인 이유: 여기 들어오는 건
# 사진이 아니라 로고이고, 슬롯이 리드 4:3 처럼 크게 잡혀서 래스터는 확대되면 뭉갠다.
IMG_EXTS = (".svg", ".avif", ".webp", ".png", ".jpg", ".jpeg")

# 슬롯 안에서 이미지를 어떻게 맞출지. "contain" = 로고 전체를 보여준다(잘리지 않음, 원색 유지),
# "cover" = 슬롯을 꽉 채우고 그레이스케일(사진용 원래 처리). CSS 의 `.fit-contain`/`.fit-cover`
# 와 짝이며 **여기만 바꾸면 전체가 바뀐다** — 지금은 로고뿐이라 contain.
IMAGE_FIT = "contain"

# 주체를 특정할 수 없는 스토리용 폴백. `generic_<카테고리>` 파일이 있으면 쓴다.
GENERIC_PREFIX = "generic_"

# 파일명이 곧 LLM 에 노출되는 키라서, 프롬프트/HTML 에 그대로 넣어도 안전한 문자만 받는다.
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

_catalog_cache: dict[str, str] | None = None
_labels_cache: dict[str, str] | None = None


def reset_cache() -> None:
    """카탈로그 캐시를 비운다. 한 프로세스 안에서 `static/img/` 가 바뀔 일은 없지만,
    테스트가 IMG_DIR 을 tmp_path 로 갈아끼울 때 필요하다."""
    global _catalog_cache, _labels_cache
    _catalog_cache = None
    _labels_cache = None


def catalog() -> dict[str, str]:
    """{키: 루트 기준 상대경로}. 파일이 없으면 빈 dict — 호출부는 그걸 정상으로 다뤄야 한다
    (이미지를 아직 안 올린 상태에서도 파이프라인은 그대로 돌아야 하므로)."""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    found: dict[str, str] = {}
    if IMG_DIR.is_dir():
        # 확장자 우선순위대로 훑고 먼저 잡힌 키는 덮어쓰지 않는다 -> openai.svg 가 openai.png 를 이긴다
        for ext in IMG_EXTS:
            for f in sorted(IMG_DIR.glob(f"*{ext}")):
                key = f.stem.lower()
                if key not in found and _KEY_RE.match(key):
                    found[key] = f"static/img/{f.name}"
    _catalog_cache = found
    return found


def labels() -> dict[str, str]:
    """{키: 사람이 읽는 이름}. LLM 프롬프트에 후보를 설명할 때 쓴다.

    `catalog.yaml` 은 선택 사항이고, 거기 없는 키는 키 자체를 이름으로 쓴다 — 파일만 떨어뜨려도
    동작해야 하기 때문. 반대로 yaml 에만 있고 파일이 없는 키는 **버린다**(고를 수 없는 후보를
    프롬프트에 넣으면 모델이 그걸 고르고 우리는 폴백으로 되돌린다 = 토큰만 낭비)."""
    global _labels_cache
    if _labels_cache is not None:
        return _labels_cache
    described: dict[str, str] = {}
    if CATALOG_FILE.is_file():
        try:
            loaded = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:  # 장식용 메타데이터라 파이프라인을 죽이지 않는다
            print(f"      [!] {CATALOG_FILE.name} 파싱 실패, 키 이름으로 폴백: {e}")
            loaded = {}
        if isinstance(loaded, dict):
            described = {str(k).lower(): str(v) for k, v in loaded.items() if v}
    _labels_cache = {key: described.get(key, key) for key in catalog()}
    return _labels_cache


def path_for(key: str) -> str | None:
    """키 하나를 경로로. 없으면 None."""
    return catalog().get((key or "").strip().lower())


def resolve(image_key: str = "", source_id: str = "", category: str = "") -> str | None:
    """아이템 하나가 쓸 이미지 경로. 없으면 None -> 템플릿이 기존 텍스트 플레이스홀더를 그린다.

    폴백 사슬(위에서부터): LLM 이 고른 주체 마크 -> 수집 소스 마크 -> 카테고리 제네릭 -> 없음.
    **이 사슬이 아카이브를 공짜로 만든다**: 415건은 image_key 가 빈 문자열이라 두 번째/세 번째
    단계로 떨어진다 -> 재엔리치(유료) 없이도 마크가 붙는다(2026-07-31 결정과 일관)."""
    for key in (image_key, source_id, f"{GENERIC_PREFIX}{category}" if category else ""):
        hit = path_for(key)
        if hit:
            return hit
    return None


def copy_to(static_out: Path) -> None:
    """`static/img/` 의 이미지들을 `output/static/img/` 로 복사. 폴더가 없으면 아무것도 안 한다.
    카탈로그에 잡힌 파일만 복사한다 -> README.md·catalog.yaml 은 배포되지 않는다."""
    files = [IMG_DIR / Path(rel).name for rel in catalog().values()]
    if not files:
        return
    dest = static_out / "img"
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copyfile(f, dest / f.name)
