"""토픽 필터(2026-08-04) 회귀 테스트.

홈 상단 필터가 카테고리 pill 에서 **토픽 pill** 로 바뀌었다. 카테고리 pill 은 상단
네비게이션과 똑같은 4개를 반복해서 자리값을 못 했고, 토픽은 "무엇에 관한 이야기인가"라는
카테고리와 직교하는 축이라 필터로서 실제로 쓸모가 있다.

여기서 고정하는 계약:
  1. 모델이 준 토픽은 **믿지 않는다** — 어휘 밖은 버리고, 중복 제거, 3개로 자른다.
  2. pill 은 그날 많이 나온 순 top-6. 실측상 하루에 8~9개가 붙는데 대부분 1~2건이라
     전부 내보내면 줄이 넘치고 한 건짜리 필터가 생긴다.
  3. 토픽이 없는 기사는 All 에서만 보인다(사라지지 않는다).
"""
import json

import pytest

import llm
import render
from config import MAX_TOPICS_PER_ITEM, TOPIC_ORDER
from store import Store


# ── 1. 어휘 검증 ──────────────────────────────────────────────────────────────

def test_known_topics_survive():
    assert llm.clean_topics(["music", "code"]) == ["code", "music"]


def test_invented_topics_are_dropped():
    """모델은 그럴듯한 값을 지어낸다. 어휘 밖 토픽은 어떤 pill 에도 안 걸리는 유령이 된다."""
    assert llm.clean_topics(["ai_safety", "code", "LLMs"]) == ["code"]


def test_case_and_duplicates_are_normalised():
    assert llm.clean_topics(["Music", "MUSIC", " music "]) == ["music"]


def test_topics_are_capped():
    """상한이 없으면 모든 pill 이 모든 기사를 담아 필터가 아무것도 구분하지 못한다."""
    got = llm.clean_topics(["video", "code", "money", "health", "art", "music"])
    assert len(got) == MAX_TOPICS_PER_ITEM


def test_output_order_follows_the_vocabulary():
    """저장 순서가 모델의 나열 순서를 따라가면 같은 아이템의 data-topics 가 실행마다 달라진다."""
    assert llm.clean_topics(["music", "code"]) == llm.clean_topics(["code", "music"])


@pytest.mark.parametrize("raw", [None, "code", 42, {"a": 1}, []])
def test_non_list_input_is_empty(raw):
    assert llm.clean_topics(raw) == []


def test_every_vocabulary_entry_has_a_prompt_gloss():
    """어휘에 토픽을 추가하고 설명을 빼먹으면 프롬프트 조립이 KeyError 로 죽는다."""
    assert set(llm._TOPIC_GLOSS) == set(TOPIC_ORDER)


def test_the_prompt_lists_every_topic():
    for topic in TOPIC_ORDER:
        assert topic in llm.SYSTEM


# ── 2. 저장 왕복 ──────────────────────────────────────────────────────────────

def _item(item_id="a1", topics=None, **kw):
    it = {
        "id": item_id, "source_id": "openai", "category": "model_releases",
        "title": "T", "headline": "T", "url": f"https://example.com/{item_id}",
        "summary": "s", "significance": 0.5, "is_major": False, "published": "",
        "cluster_sources": [], "cluster_size": 1, "topics": topics or [],
    }
    it.update(kw)
    return it


def test_topics_round_trip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item(topics=["code", "music"])], "2026-08-04")
    assert store.items_for_digest("2026-08-04")[0]["topics"] == ["code", "music"]
    store.close()


def test_item_without_topics_round_trips_as_empty(tmp_path):
    store = Store(tmp_path / "t.db")
    it = _item()
    del it["topics"]
    store.save_items([it], "2026-08-04")
    assert store.items_for_digest("2026-08-04")[0]["topics"] == []
    store.close()


def test_malformed_topics_degrade_to_empty(tmp_path):
    """손으로 고친 DB나 옛 행이 깨진 값을 갖고 있어도 렌더가 죽으면 안 된다."""
    store = Store(tmp_path / "t.db")
    store.save_items([_item()], "2026-08-04")
    store.conn.execute("UPDATE items SET topics='not json'")
    store.conn.commit()
    assert store.items_for_digest("2026-08-04")[0]["topics"] == []
    store.close()


def test_record_topics_updates_only_the_named_items(tmp_path):
    store = Store(tmp_path / "t.db")
    store.save_items([_item("a1"), _item("a2")], "2026-08-04")
    store.record_topics([("a1", ["code"])])
    got = {it["id"]: it["topics"] for it in store.items_for_digest("2026-08-04")}
    assert got == {"a1": ["code"], "a2": []}
    store.close()


def test_items_missing_topics_skips_already_tagged(tmp_path):
    """백필이 재개 가능하려면 이미 붙은 건 다시 집으면 안 된다."""
    store = Store(tmp_path / "t.db")
    store.save_items([_item("a1", ["code"]), _item("a2")], "2026-08-04")
    assert [r["id"] for r in store.items_missing_topics()] == ["a2"]
    store.close()


# ── 3. pill 구성 ──────────────────────────────────────────────────────────────

def _items(*topic_lists):
    return [{"topics": list(t)} for t in topic_lists]


def test_pills_are_ranked_by_count():
    pills = render._topic_filters(
        _items(["code"], ["code"], ["music"]), total=3)
    assert [p["key"] for p in pills] == ["all", "code", "music"]
    assert [p["count"] for p in pills] == [3, 2, 1]


def test_all_pill_counts_every_story_including_untagged():
    pills = render._topic_filters(_items(["code"], [], []), total=3)
    assert pills[0] == {"key": "all", "label": "All", "count": 3}


def test_every_topic_of_the_day_reaches_the_drawer():
    """상한이 없어야 한다 — 2026-08-06(캔버스 6a)에 pill 줄이 서랍으로 바뀌면서 뒤집힌 계약이다.

    예전엔 top-6 으로 잘랐다: 하루에 토픽이 8~9개 붙는데 pill 을 컨트롤 줄에 한 줄로
    늘어놓으니 줄이 넘쳐서였다. 6a 는 그 줄을 `Filters` 버튼 + 서랍으로 접었고 서랍은
    몇 개가 들어와도 넘치지 않는다 → 자르는 이유가 없어졌다. 자르면 1~2건짜리 토픽이
    **아예 고를 수 없는 토픽**이 된다(예전엔 그게 의도된 트레이드오프였다).

    `cap` 인자는 남아 있지만 기본값은 무제한이다."""
    many = _items(*[[t] for t in TOPIC_ORDER])
    pills = render._topic_filters(many, total=len(TOPIC_ORDER))
    assert len(pills) == len(TOPIC_ORDER) + 1  # +1 = All
    assert len(render._topic_filters(many, total=len(TOPIC_ORDER), cap=6)) == 7


def test_ties_break_on_vocabulary_order():
    """동점 순서가 흔들리면 같은 데이터로 재렌더할 때마다 pill 순서가 바뀐다."""
    a = render._topic_filters(_items(["music"], ["code"]), total=2)
    b = render._topic_filters(_items(["code"], ["music"]), total=2)
    assert [p["key"] for p in a] == [p["key"] for p in b] == ["all", "code", "music"]


def test_topics_nobody_used_get_no_pill():
    pills = render._topic_filters(_items(["code"]), total=1)
    assert [p["key"] for p in pills] == ["all", "code"]


def test_unknown_topic_gets_no_pill():
    assert [p["key"] for p in render._topic_filters(_items(["nonsense"]), total=1)] == ["all"]


# ── 4. 아이템 주석 + 렌더 ─────────────────────────────────────────────────────

def _full_item(topics):
    return {
        "title": "A story", "headline": "A story", "summary": "s",
        "url": "https://example.com/a", "source_id": "openai", "source_name": "OpenAI",
        "category": "model_releases", "significance": 0.5, "is_major": False,
        "digest_date": "2026-08-04", "cluster_size": 1, "cluster_sources": [],
        "thread_parent": None, "topics": list(topics),
    }


def test_annotate_builds_the_dom_attribute():
    it = _full_item(["music", "code"])
    render._annotate(it)
    assert it["topic_attr"] == "code music"


def test_annotate_drops_unknown_topics():
    it = _full_item(["code", "nonsense"])
    render._annotate(it)
    assert it["topics"] == ["code"] and it["topic_attr"] == "code"


def test_annotate_handles_a_missing_topics_key():
    it = _full_item([])
    del it["topics"]
    render._annotate(it)
    assert it["topic_attr"] == ""


def _render(items, tmp_path):
    groups = [("model_releases", items), ("research", []),
              ("tools_products", []), ("policy_business", [])]
    render.render_digest("2026-08-04", groups, [], tmp_path)
    return (tmp_path / "index.html").read_text(encoding="utf-8")


def test_page_shows_topic_pills_not_category_pills(tmp_path):
    html = _render([_full_item(["code"])], tmp_path)
    assert 'data-topic="code"' in html
    assert 'data-filter-btn data-cat=' not in html


def test_page_tags_items_with_their_topics(tmp_path):
    assert 'data-topics="code music"' in _render([_full_item(["code", "music"])], tmp_path)


def test_untagged_item_renders_an_empty_topic_attribute(tmp_path):
    """빈 문자열이라 어떤 토픽 pill 에도 안 걸리고 All 에만 남는다."""
    html = _render([_full_item([])], tmp_path)
    assert 'data-topics=""' in html


def test_topic_filter_script_matches_whole_tokens(tmp_path):
    """부분일치로 짜면 'art' 가 'chart' 에 걸린다. 공백을 덧대 토큰으로 비교해야 한다."""
    html = _render([_full_item(["art"])], tmp_path)
    assert "' '+topic+' '" in html


# ── 5. 아카이브 페이지도 같은 필터를 쓴다 ────────────────────────────────────
#
# 2026-08-04 이전엔 필터가 home.html 안에만 있어서 아카이브 251페이지에는 필터 줄이 아예
# 없었다(카테고리 시절부터). 설계 초안이 "아카이브도 home.html 을 공유한다"고 잘못 적었던
# 부분이라, 여기서 계약으로 못박는다.

def _render_archive(items, tmp_path):
    groups = [("model_releases", items), ("research", []),
              ("tools_products", []), ("policy_business", [])]
    render.render_archive_digest("2026-W31", groups, tmp_path)
    return (tmp_path / "archive" / "2026-W31.html").read_text(encoding="utf-8")


def test_archive_page_has_topic_pills(tmp_path):
    """'all' pill 은 2026-08-06(6a)에 없어졌다 — 다중선택이 되면서 "아무것도 안 고른 상태"가
    곧 All 이라 버튼이 필요 없다. 대신 그날 붙은 토픽 pill 이 서랍에 있어야 한다."""
    html = _render_archive([_full_item(["code"]), _full_item(["code"])], tmp_path)
    assert 'data-topic="code"' in html
    assert 'data-topic="all"' not in html
    assert "filter-drawer" in html


def test_archive_page_tags_lead_second_and_rest(tmp_path):
    """리드/2위/나머지가 전부 숨겨질 수 있어야 한다 — 하나라도 빠지면 필터가 새어 나온다."""
    html = _render_archive([_full_item(["code"]), _full_item(["music"]),
                            _full_item(["art"])], tmp_path)
    for topic in ("code", "music", "art"):
        assert f'data-topics="{topic}"' in html


def test_archive_page_ships_the_filter_script(tmp_path):
    html = _render_archive([_full_item(["code"])], tmp_path)
    assert "data-scope" in html and "data-filter-btn" in html


def test_home_and_archive_share_one_filter_script(tmp_path):
    """두 벌로 두면 갈라진다. 매크로 하나에서 나와야 한다."""
    home = _render([_full_item(["code"])], tmp_path / "h")
    archive = _render_archive([_full_item(["code"])], tmp_path / "a")
    body = "function has(el,topic)"
    assert body in home and body in archive


def test_the_filter_cannot_hide_its_own_undo_control(tmp_path):
    """컨트롤 줄은 `.panel-body`(data-section) **바깥**에 있어야 한다.

    2026-08-06 6a 포팅에서 리드와 Also today 가 한 장의 카드로 묶였다. 카드 속(.panel-body)은
    data-section 이라 살아남은 항목이 0이면 통째로 숨는데 — rank 9 이하에만 달린 토픽을 고르면
    실제로 그렇게 된다 — 컨트롤 줄이 그 안에 있으면 **필터를 걸자마자 필터가 사라져서 되돌릴
    수단이 없어진다.** (chip 도 pill 도 서랍도 같이 숨는다.)"""
    html = _render([_full_item(["code"]), _full_item(["music"])], tmp_path)
    line, body = html.find("control-line"), html.find('class="panel-body"')
    assert line != -1 and body != -1
    assert line < body, "컨트롤 줄이 panel-body 안으로 들어갔다 — 필터가 자기를 숨긴다"


def test_control_line_is_omitted_when_nothing_is_tagged(tmp_path):
    """고를 토픽이 없으면 컨트롤 줄도 서랍도 그리지 않는다 — 빈 서랍을 여는 `Filters` 버튼은
    누를 이유가 없는 죽은 UI 다(예전 'All 만 있는 필터 줄'과 같은 이유)."""
    html = _render([_full_item([])], tmp_path)
    assert "control-line" not in html and "filter-drawer" not in html


def test_backfill_payload_shape_matches_what_the_llm_expects(tmp_path):
    """`llm._payload` 가 요구하는 키가 빠지면 백필이 KeyError 로 죽는다."""
    import backfill_topics
    row = {"id": "a1", "title": "T", "headline": "H", "summary": "s",
           "category": "research"}
    payload = json.loads(llm._payload([backfill_topics._to_payload(row)]))
    assert payload[0]["id"] == "a1" and payload[0]["title"] == "H"
