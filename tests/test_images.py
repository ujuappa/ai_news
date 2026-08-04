"""마크 카탈로그와 폴백 사슬 (`images.py`) + LLM 이 고른 키의 검증.

여기서 고정하는 계약:
  1. 카탈로그의 원본은 디스크의 파일 이름이다 — 설정 파일이 아니라.
  2. 폴백 사슬은 LLM 키 -> 소스 -> 카테고리 제네릭 -> None 순이고, **중간이 비어도 건너뛴다**.
     이 사슬이 아카이브 415건(image_key 없음)을 재엔리치 없이 살리는 유일한 장치다.
  3. 카탈로그에 없는 키는 저장 전에 버린다 — 모델은 그럴듯한 키를 지어낸다.
"""
import pytest

import images
import llm


@pytest.fixture
def img_dir(tmp_path, monkeypatch):
    """IMG_DIR 을 tmp 로 갈아끼우고 캐시를 비운다. 캐시를 안 비우면 실제 static/img/ 가 샌다."""
    d = tmp_path / "img"
    d.mkdir()
    monkeypatch.setattr(images, "IMG_DIR", d)
    monkeypatch.setattr(images, "CATALOG_FILE", d / "catalog.yaml")
    images.reset_cache()
    yield d
    images.reset_cache()


def _put(d, name, body="<svg/>"):
    (d / name).write_text(body, encoding="utf-8")


# ── 계약 1: 카탈로그 = 파일 목록 ────────────────────────────────────────────────

def test_catalog_keys_come_from_filenames(img_dir):
    _put(img_dir, "openai.svg")
    _put(img_dir, "generic_research.png")
    assert images.catalog() == {
        "openai": "static/img/openai.svg",
        "generic_research": "static/img/generic_research.png",
    }


def test_catalog_is_empty_when_no_images_are_uploaded(img_dir):
    """이미지를 하나도 안 올린 상태에서도 파이프라인은 그대로 돌아야 한다."""
    assert images.catalog() == {}
    assert images.resolve("openai", "techcrunch_ai", "research") is None


def test_svg_wins_over_raster_for_the_same_key(img_dir):
    """로고는 리드 슬롯(4:3 전폭)까지 확대되므로 벡터가 이겨야 한다."""
    _put(img_dir, "openai.png")
    _put(img_dir, "openai.svg")
    assert images.catalog()["openai"] == "static/img/openai.svg"


def test_non_image_files_are_ignored(img_dir):
    _put(img_dir, "README.md", "docs")
    _put(img_dir, "catalog.yaml", "openai: OpenAI")
    assert images.catalog() == {}


def test_unsafe_filenames_are_skipped(img_dir):
    """키는 프롬프트와 HTML 에 그대로 들어간다 — 이상한 파일명은 후보가 되면 안 된다."""
    _put(img_dir, "Open AI Logo (1).svg")
    _put(img_dir, "openai.svg")
    assert sorted(images.catalog()) == ["openai"]


# ── 계약 2: 폴백 사슬 ───────────────────────────────────────────────────────────

def test_llm_key_wins_over_the_source_mark(img_dir):
    """이 기능의 요점: TechCrunch 가 쓴 OpenAI 기사는 OpenAI 마크를 단다."""
    _put(img_dir, "openai.svg")
    _put(img_dir, "techcrunch_ai.svg")
    assert images.resolve("openai", "techcrunch_ai", "model_releases") == "static/img/openai.svg"


def test_falls_back_to_the_source_mark_without_an_llm_key(img_dir):
    _put(img_dir, "techcrunch_ai.svg")
    assert images.resolve("", "techcrunch_ai", "policy_business") == "static/img/techcrunch_ai.svg"


def test_falls_back_to_the_category_generic(img_dir):
    _put(img_dir, "generic_policy_business.svg")
    assert (images.resolve("", "techcrunch_ai", "policy_business")
            == "static/img/generic_policy_business.svg")


def test_a_missing_middle_step_is_skipped_not_fatal(img_dir):
    """LLM 키가 카탈로그에 없고 소스 마크도 없으면 제네릭까지 내려가야 한다 —
    중간에서 멈추면 아카이브가 통째로 빈 슬롯이 된다."""
    _put(img_dir, "generic_research.svg")
    assert images.resolve("nvidia", "arxiv_lg", "research") == "static/img/generic_research.svg"


def test_resolve_returns_none_when_nothing_matches(img_dir):
    _put(img_dir, "openai.svg")
    assert images.resolve("", "bbc_tech", "policy_business") is None


def test_resolve_is_case_insensitive_on_keys(img_dir):
    _put(img_dir, "openai.svg")
    assert images.resolve("OpenAI", "", "") == "static/img/openai.svg"


def test_resolve_with_no_arguments_is_safe(img_dir):
    """아카이브 행은 image_key/category 가 비어 있을 수 있다."""
    assert images.resolve() is None


# ── 라벨 (LLM 프롬프트에 들어가는 설명) ─────────────────────────────────────────

def test_labels_fall_back_to_the_key_itself(img_dir):
    """catalog.yaml 은 선택 사항 — 파일만 떨어뜨려도 후보가 되어야 한다."""
    _put(img_dir, "openai.svg")
    assert images.labels() == {"openai": "openai"}


def test_labels_use_catalog_yaml_when_present(img_dir):
    _put(img_dir, "openai.svg")
    (img_dir / "catalog.yaml").write_text("openai: OpenAI — GPT models\n", encoding="utf-8")
    assert images.labels()["openai"] == "OpenAI — GPT models"


def test_labels_drop_keys_with_no_file(img_dir):
    """고를 수 없는 후보를 프롬프트에 넣으면 모델이 그걸 고르고 우리는 폴백으로 되돌린다."""
    _put(img_dir, "openai.svg")
    (img_dir / "catalog.yaml").write_text("openai: OpenAI\nnvidia: Nvidia\n", encoding="utf-8")
    assert sorted(images.labels()) == ["openai"]


def test_broken_catalog_yaml_does_not_kill_the_run(img_dir):
    _put(img_dir, "openai.svg")
    (img_dir / "catalog.yaml").write_text("openai: [unclosed\n", encoding="utf-8")
    assert images.labels() == {"openai": "openai"}


# ── 배포 복사 ───────────────────────────────────────────────────────────────────

def test_copy_to_ships_images_but_not_docs(img_dir, tmp_path):
    _put(img_dir, "openai.svg")
    _put(img_dir, "README.md", "docs")
    (img_dir / "catalog.yaml").write_text("openai: OpenAI\n", encoding="utf-8")
    images.copy_to(tmp_path / "static")
    assert (tmp_path / "static" / "img" / "openai.svg").exists()
    assert not (tmp_path / "static" / "img" / "README.md").exists()
    assert not (tmp_path / "static" / "img" / "catalog.yaml").exists()


def test_copy_to_is_a_noop_with_an_empty_catalog(img_dir, tmp_path):
    images.copy_to(tmp_path / "static")
    assert not (tmp_path / "static" / "img").exists()


# ── 계약 3: LLM 이 고른 키의 검증 ───────────────────────────────────────────────

CATALOG = {"openai": "OpenAI", "generic_research": "A paper"}


def _row(**over):
    row = {"id": "a", "category": "research", "summary": "s", "significance": 0.5,
           "is_major": False, "headline": "H"}
    row.update(over)
    return row


def _item():
    return {"id": "a", "category": "research", "summary_raw": "raw", "title": "Original title"}


def test_merge_row_keeps_a_key_that_is_in_the_catalog():
    it = _item()
    llm._merge_row(it, _row(image_key="openai"), CATALOG)
    assert it["image_key"] == "openai"


def test_merge_row_drops_an_invented_key():
    """모델은 그럴듯한 키를 지어낸다("anthropic_ai"). 저장하면 렌더가 매번 없는 파일을 찾는다."""
    it = _item()
    llm._merge_row(it, _row(image_key="anthropic_ai"), CATALOG)
    assert it["image_key"] == ""


def test_merge_row_handles_a_null_or_odd_image_key():
    for bad in (None, 123, [], "   "):
        it = _item()
        llm._merge_row(it, _row(image_key=bad), CATALOG)
        assert it["image_key"] == ""


def test_merge_row_without_a_catalog_stores_nothing():
    """기존 호출부(backfill 등)는 카탈로그를 안 넘긴다 — 그때는 이미지 선택 자체가 없다."""
    it = _item()
    llm._merge_row(it, _row(image_key="openai"))
    assert it["image_key"] == ""


# ── 프롬프트 조립 ───────────────────────────────────────────────────────────────

def test_system_instruction_is_unchanged_without_a_catalog():
    """고를 수 있는 게 없는데 image_key 를 요구하면 모델이 키를 지어낸다."""
    assert llm._system_instruction(None) == llm.SYSTEM
    assert llm._system_instruction({}) == llm.SYSTEM


def test_system_instruction_lists_every_catalog_key():
    out = llm._system_instruction(CATALOG)
    assert out.startswith(llm.SYSTEM)
    for key, label in CATALOG.items():
        assert f"- {key} — {label}" in out
    assert "image_key" in out
    # 이 규칙이 기능의 핵심이다 — 발행처가 아니라 주체를 고르게 하는 문장
    assert "not the" in out and "publisher" in out
