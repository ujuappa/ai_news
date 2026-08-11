"""저장(북마크) · 토픽 팔로우 · 저장한 필터 (2026-08-11).

이 기능은 **브라우저 안에만** 산다(계정도 서버도 없는 정적 사이트). 그래서 파이썬이 검사할 수
있는 건 두 가지다:
  1. 렌더 계약 — 버튼이 지면에 나오고, 저장에 필요한 값을 다 들고 있고, HTML 이 유효한가
  2. follow.js 의 순수 로직 — node 로 돌려서 상태 전이를 확인 (localStorage 는 스텁)

특히 **`<a>` 안에 `<button>` 을 넣지 않았는지**를 검사한다. 그건 대화형 콘텐츠 중첩이라
HTML 위반이고, 브라우저가 파싱 단계에서 DOM 을 재배치해 버튼이 링크 밖으로 튀어나온다 —
그러면 클릭 대상이 조용히 어긋난다. 이 사이트는 원래 행 전체가 `<a>` 인 목록이 두 개
있었고(brief-row · cat-row), 저장 버튼을 넣으려고 2026-08-11 에 `<div>` 로 바꿨다.
그 변환이 되돌려지면 이 테스트가 잡는다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

import render

ROOT = Path(__file__).resolve().parent.parent
FOLLOW_JS = ROOT / "static" / "follow.js"
NODE = shutil.which("node")

ITEM = {
    "title": "Opus 5 ships with 2x throughput", "headline": "Opus 5 ships",
    "url": "https://www.anthropic.com/news/claude-opus-5", "summary": "A frontier release.",
    "source_id": "anthropic", "source_name": "Anthropic", "category": "model_releases",
    "significance": 0.9, "is_major": True, "digest_date": "2026-07-31",
    "cluster_size": 1, "cluster_sources": [], "thread_parent": None,
    "topics": ["chips", "money"],
}


def _items(n):
    out = []
    for i in range(n):
        it = dict(ITEM)
        it["title"] = it["headline"] = f"Story {i}"
        it["url"] = f"https://example.com/{i}"
        it["significance"] = 0.9 - i * 0.04
        out.append(it)
    return out


def _groups(items):
    return [("model_releases", items), ("research", []),
            ("tools_products", []), ("policy_business", [])]


# ── 렌더 계약 ────────────────────────────────────────────────────────────────

def test_save_button_reaches_every_tier_of_the_home_page(tmp_path):
    """리드 · Also today 카드 · Worth knowing 행 · In brief 행 **전부**에 저장 버튼이 있어야
    한다. 한 계층만 빠지면 "왜 이 기사는 저장이 안 되지"가 되고, 그 계층은 보통 랭킹이 낮은
    In brief 다(마크업이 `<a>` 라 가장 손이 많이 가는 곳이기도 하다)."""
    # 12건 = 리드 1 + 카드 3 + worth 4 + brief 4
    render.render_digest("2026-07-31", _groups(_items(12)), [], tmp_path, total_records=12)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    # `data-item-id=` 로 센다 — `data-save` 뒤에는 개행이 오므로 공백을 붙여 세면 0이 나온다.
    assert page.count("data-item-id=") == 12, "저장 버튼 수가 항목 수와 다르다"
    for tier_marker in ("lead-byline", "card-foot", "worth-foot", "brief-row"):
        block = page.split(tier_marker, 1)
        assert len(block) == 2, f"{tier_marker} 구획이 없다"
    # 각 계층 안에 실제로 버튼이 있는지 — 마커만 있고 버튼이 없으면 위 총계로는 못 잡는다.
    for cls in ("lead-byline", "card-foot", "worth-foot"):
        for chunk in re.findall(rf'class="{cls}"(.*?)</div>', page, re.S):
            assert "data-save" in chunk, f"{cls} 안에 저장 버튼이 없다"


def test_save_button_carries_everything_the_saved_page_needs(tmp_path):
    """저장 페이지는 정적 HTML 을 다시 읽을 수 없다(localStorage 만 본다) → 목록을 그릴 값이
    저장 시점에 버튼에 다 있어야 한다. 하나라도 빠지면 저장 목록이 빈칸으로 나온다."""
    items = _items(1)
    items[0]["id"] = "abc123"
    render.render_digest("2026-07-31", _groups(items), [], tmp_path, total_records=1)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    btn = re.search(r"<button[^>]*data-save\b[^>]*>", page).group(0)
    for attr, expect in [
        ("data-item-id", "abc123"),
        ("data-item-title", "Story 0"),
        ("data-item-url", "https://example.com/0"),
        ("data-item-date", "2026-07-31"),
        ("data-item-source", None),
        ("data-item-sig", "0.90"),
        # `TOPIC_ORDER` 순으로 정규화된 값이다(입력은 ['chips','money'] 였다) — money 가
        # 어휘에서 먼저다. 저장 시점에 그 순서를 그대로 들고 가야 저장 목록의 칩 순서가
        # 지면과 같다.
        ("data-item-topics", "money chips"),
    ]:
        assert attr in btn, f"{attr} 가 없다"
        if expect is not None:
            assert f'{attr}="{expect}"' in btn, f"{attr} 값이 {expect!r} 가 아니다: {btn}"


def test_a_missing_item_id_falls_back_to_the_url(tmp_path):
    """`id` 가 없는 항목이 섞여도 저장 키가 비면 안 된다 — 비면 저장한 기사 전부가 같은 키를
    공유해서 하나만 남는다(조용하고 찾기 어려운 고장). 합성 데이터·옛 행이 그런 경우다."""
    items = _items(1)
    items[0].pop("id", None)
    render.render_digest("2026-07-31", _groups(items), [], tmp_path, total_records=1)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'data-item-id=""' not in page, "저장 키가 비어 있다"
    assert 'data-item-id="https://example.com/0"' in page, "URL 폴백이 안 걸렸다"


@pytest.mark.parametrize("page_name,renderer", [
    ("index.html", "digest"),
    ("model_releases.html", "category"),
])
def test_no_button_is_nested_inside_a_link(tmp_path, page_name, renderer):
    """**`<a>` 안의 `<button>` 금지.** 대화형 콘텐츠 중첩은 HTML 위반이고, 브라우저가 DOM 을
    재배치해서 버튼이 링크 밖으로 튀어나온다 → 클릭 대상이 조용히 어긋난다.

    이 검사가 있는 이유: `brief-row` 와 `cat-row` 는 원래 **행 전체가 `<a>`** 였다.
    2026-08-11 에 저장 버튼을 넣으려고 `<div>` + 제목 링크로 바꿨는데, 되돌리기 쉬운 종류의
    변경이라(마크업이 더 짧아 보인다) 가드를 둔다.
    """
    items = _items(12)
    if renderer == "digest":
        render.render_digest("2026-07-31", _groups(items), [], tmp_path, total_records=12)
    else:
        render.render_category_page("2026-07-31", "model_releases", _groups(items), tmp_path,
                                    in_archive=False, one_liner="x", cap=10, min_sig=0.3,
                                    total_records=12)
    page = (tmp_path / page_name).read_text(encoding="utf-8")

    # <a ...> ... </a> 안에 <button 이 있으면 위반. 중첩 <a> 는 없으므로 비탐욕 매칭이면 충분.
    for anchor in re.findall(r"<a\b[^>]*>.*?</a>", page, re.S):
        assert "<button" not in anchor, f"<a> 안에 <button> 이 들어갔다:\n{anchor[:300]}"


def test_the_two_rows_that_used_to_be_links_are_no_longer_links(tmp_path):
    """brief-row · cat-row 가 `<div>` 이고 제목이 링크를 받는지. 위 중첩 검사와 짝이다 —
    이건 "왜 div 여야 하는가"를 기록하는 쪽이다."""
    items = _items(12)
    render.render_digest("2026-07-31", _groups(items), [], tmp_path, total_records=12)
    render.render_category_page("2026-07-31", "model_releases", _groups(items), tmp_path,
                                in_archive=False, one_liner="x", cap=10, min_sig=0.3,
                                total_records=12)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    cat = (tmp_path / "model_releases.html").read_text(encoding="utf-8")

    assert '<div class="brief-row"' in home
    assert '<a class="brief-row"' not in home, "brief-row 가 다시 <a> 가 됐다"
    assert '<a class="brief-title"' in home, "brief 제목이 링크가 아니다"

    assert '<div class="cat-row"' in cat
    assert '<a class="cat-row"' not in cat, "cat-row 가 다시 <a> 가 됐다"
    assert '<a class="cat-row-title"' in cat, "카테고리 행 제목이 링크가 아니다"


def test_follow_star_is_a_sibling_of_the_filter_pill_not_a_child(tmp_path):
    """`<button>` 안의 `<button>` 도 같은 위반이다. 팔로우 별은 토픽 pill 의 **형제**여야 한다."""
    render.render_digest("2026-07-31", _groups(_items(3)), [], tmp_path, total_records=3)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "follow-star" in page, "팔로우 별이 서랍에 없다"
    for btn in re.findall(r"<button\b[^>]*>.*?</button>", page, re.S):
        assert "<button" not in btn[1:], f"<button> 안에 <button> 이 있다:\n{btn[:300]}"
    # pill 과 별이 같은 묶음 안에 형제로 있는지
    pair = re.search(r'<span class="pill-pair">(.*?)</span>\s*</span>', page, re.S)
    assert pair is not None, "pill-pair 묶음이 없다"


def test_saved_page_renders_without_any_server_data(tmp_path):
    """저장 지면은 서버가 내용을 모른다 — 껍데기 + 토픽 라벨표만 굽는다. DB 도 config 의
    소스도 안 쓴다(그래서 rerender 마다 바이트가 같다)."""
    first = render.render_saved_page(tmp_path, total_records=7).read_text(encoding="utf-8")
    second = render.render_saved_page(tmp_path, total_records=7).read_text(encoding="utf-8")
    assert first == second, "같은 입력으로 저장 지면이 다르게 나온다"
    labels = json.loads(re.search(
        r'<script id="saved-topics" type="application/json">(.*?)</script>', first, re.S).group(1))
    import config
    assert labels == {t.key: t.label for t in config.TOPICS}
    # 세 구획이 다 있어야 한다 — 하나라도 빠지면 그 축을 관리할 방법이 없어진다.
    for marker in ("data-saved-list", "data-follow-grid", "data-preset-list", "data-preset-picker"):
        assert marker in first, f"{marker} 구획이 없다"
    # 범위 고지(브라우저 한정)를 반드시 적는다 — 안 적으면 기기를 바꿨을 때 사고가 된다.
    assert "this browser only" in first.lower()


def test_saved_page_lists_every_topic_in_the_preset_picker(tmp_path):
    """프리셋 편집기의 선택 목록은 **전체 어휘**여야 한다(그날 붙은 토픽이 아니라) —
    프리셋은 앞으로 읽을 방식이라 오늘 기사가 없는 토픽도 골라 둘 수 있어야 한다."""
    import config
    page = render.render_saved_page(tmp_path).read_text(encoding="utf-8")
    picker = re.search(r"data-preset-picker>(.*?)</div>\s*</div>", page, re.S).group(1)
    for topic in config.TOPICS:
        assert f'value="{topic.key}"' in picker, f"{topic.key} 가 선택 목록에 없다"


# ── follow.js 로직 (node) ────────────────────────────────────────────────────

_HARNESS = textwrap.dedent("""
    // localStorage · window · document 최소 스텁. follow.js 는 브라우저용이므로
    // node 에서 돌리려면 이만큼이 필요하다. DOM 조작 경로(paintAll)는 여기서 검사하지
    // 않는다 — 그건 렌더 계약 테스트와 브라우저에서 본다.
    const store = {};
    globalThis.localStorage = {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; }
    };
    const listeners = {};
    globalThis.window = {
      addEventListener: (n, f) => { (listeners[n] = listeners[n] || []).push(f); },
      dispatchEvent: () => true
    };
    globalThis.CustomEvent = class { constructor(n, o) { this.type = n; this.detail = o && o.detail; } };
    globalThis.document = {
      readyState: 'complete',
      querySelectorAll: () => [],
      querySelector: () => null,
      addEventListener: () => {},
      createEvent: () => ({ initEvent: () => {} })
    };
    require('fs');
    eval(require('fs').readFileSync(process.argv[2], 'utf8'));
    const F = globalThis.window.AIDigestFollow || globalThis.AIDigestFollow;
    const out = [];
    const log = (name, value) => out.push([name, value]);
    __BODY__
    process.stdout.write(JSON.stringify(out));
""")


def _run_js(body: str):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "h.js"
        hp.write_text(_HARNESS.replace("__BODY__", body), encoding="utf-8")
        proc = subprocess.run([NODE, str(hp), str(FOLLOW_JS)],
                              capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        pytest.fail(f"follow.js 실행 실패:\n{proc.stderr}")
    return dict(json.loads(proc.stdout))


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_saving_and_unsaving_round_trips():
    got = _run_js("""
      const rec = {id:'a1', title:'T', url:'u', date:'2026-08-11', source:'S', sig:0.7,
                   topics:['chips','money']};
      log('empty_at_start', Object.keys(F.read().items).length);
      log('toggle_on_returns', F.toggleSave(rec));
      log('is_saved', F.isSaved('a1'));
      log('stored_title', F.read().items.a1.t);
      log('stored_topics', F.read().items.a1.tp);
      log('toggle_off_returns', F.toggleSave(rec));
      log('is_saved_after', F.isSaved('a1'));
      log('empty_at_end', Object.keys(F.read().items).length);
    """)
    assert got["empty_at_start"] == 0
    assert got["toggle_on_returns"] is True
    assert got["is_saved"] is True
    assert got["stored_title"] == "T"
    assert got["stored_topics"] == ["chips", "money"]
    assert got["toggle_off_returns"] is False
    assert got["is_saved_after"] is False
    assert got["empty_at_end"] == 0


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_following_the_topics_of_a_saved_story():
    """사용자가 말한 "이 기사와 비슷한 주제를 따라가기"의 실제 동작. 이미 팔로우 중인 토픽은
    다시 넣지 않고(중복 금지), 저장 안 된 id 는 아무 일도 하지 않는다."""
    got = _run_js("""
      F.saveItem({id:'a1', title:'T', topics:['chips','money']});
      F.toggleFollow('chips');
      log('added', F.followTopicsOf('a1'));
      log('topics', F.read().topics);
      log('again_adds_nothing', F.followTopicsOf('a1'));
      log('unknown_id', F.followTopicsOf('nope'));
      log('topics_unchanged', F.read().topics);
    """)
    assert got["added"] == ["money"], "이미 팔로우한 chips 를 다시 넣었다"
    assert sorted(got["topics"]) == ["chips", "money"]
    assert got["again_adds_nothing"] == []
    assert got["unknown_id"] == []
    assert sorted(got["topics_unchanged"]) == ["chips", "money"]


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_presets_are_created_renamed_and_deleted():
    got = _run_js("""
      log('save_ok', F.savePreset('Money & chips', ['money','chips']));
      log('empty_name_refused', F.savePreset('   ', ['money']));
      log('empty_topics_refused', F.savePreset('X', []));
      log('count', F.read().presets.length);
      log('same_name_overwrites', (F.savePreset('money & CHIPS', ['code']),
                                   F.read().presets.length));
      log('topics_after_overwrite', F.read().presets[0].topics);
      F.savePreset('Second', ['health']);
      log('rename_ok', F.renamePreset('Second', 'Third'));
      log('rename_clash_refused', F.renamePreset('Third', 'money & CHIPS'));
      log('names', F.read().presets.map(p => p.name));
      F.deletePreset('Third');
      log('after_delete', F.read().presets.map(p => p.name));
    """)
    assert got["save_ok"] is True
    assert got["empty_name_refused"] is False
    assert got["empty_topics_refused"] is False
    assert got["count"] == 1
    # 이름이 같으면(대소문자 무시) 새로 만들지 않고 덮어쓴다 — 안 그러면 "Money"가 3개 생긴다.
    assert got["same_name_overwrites"] == 1
    assert got["topics_after_overwrite"] == ["code"]
    assert got["rename_ok"] is True
    assert got["rename_clash_refused"] is False
    assert got["after_delete"] == ["money & CHIPS"]


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_blocked_storage_does_not_throw():
    """저장소가 막힌 맥락(사이트 데이터 차단 · sandboxed iframe)에서는 `localStorage` 를
    **읽기만 해도** SecurityError 가 난다. 감싸지 않으면 스크립트가 통째로 죽어서 저장
    버튼 전부가 죽은 버튼이 된다 — 2026-08-06 에 테마 스크립트가 정확히 그렇게 죽었다."""
    got = _run_js("""
      globalThis.localStorage = {
        getItem: () => { throw new Error('SecurityError'); },
        setItem: () => { throw new Error('SecurityError'); },
        removeItem: () => { throw new Error('SecurityError'); }
      };
      log('read_survives', Object.keys(F.read().items).length);
      log('save_survives', (F.saveItem({id:'a1', title:'T', topics:[]}), true));
      log('follow_survives', (F.toggleFollow('chips'), true));
      log('still_empty', Object.keys(F.read().items).length);
    """)
    assert got["read_survives"] == 0
    assert got["save_survives"] is True
    assert got["follow_survives"] is True
    assert got["still_empty"] == 0


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_corrupt_or_old_storage_is_discarded_not_crashed():
    """손상된 JSON 이나 옛 형식(v 불일치)은 버리고 빈 상태로 시작한다. 옛 형식을 그대로
    읽으면 필드가 없는 레코드가 지면에 흘러들어 빈 줄로 나온다."""
    got = _run_js("""
      localStorage.setItem('ai-digest-follow', '{not json');
      log('corrupt', Object.keys(F.read().items).length);
      localStorage.setItem('ai-digest-follow', JSON.stringify({v:99, items:{a:{t:'x'}}}));
      log('wrong_version', Object.keys(F.read().items).length);
      localStorage.setItem('ai-digest-follow', JSON.stringify({v:1, items:'nope', topics:'nope'}));
      log('wrong_types_items', typeof F.read().items);
      log('wrong_types_topics', Array.isArray(F.read().topics));
    """)
    assert got["corrupt"] == 0
    assert got["wrong_version"] == 0
    assert got["wrong_types_items"] == "object"
    assert got["wrong_types_topics"] is True
