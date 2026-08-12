"""Comment rail (2026-08-12).

이 사이트는 GitHub Pages 정적 산출물이라 댓글 서버가 없다. 스레드는 이 브라우저의
localStorage 에만 산다(저장/팔로우와 같은 한계). 검사는 두 층이다:

  1. 렌더 계약 — 행이 레일을 열 수 있는 마크업인지, 헤드라인은 원문 링크인지,
     레일 껍데기·comments.js 가 나가는지, `<a>` 안에 `<button>` 이 없는지
  2. comments.js 순수 로직 — node 로 돌려 깊이 1 제한 · 공개/비공개 · 정렬 · 건수 집계

레일 DOM(열기/Esc/히스토리)은 브라우저에서 보고, 여기서는 계약과 저장 규칙을 못박는다.
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
COMMENTS_JS = ROOT / "static" / "comments.js"
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
        it["id"] = f"id-{i}"
        it["title"] = it["headline"] = f"Story {i}"
        it["url"] = f"https://example.com/{i}"
        it["significance"] = 0.9 - i * 0.04
        out.append(it)
    return out


def _groups(items):
    return [("model_releases", items), ("research", []),
            ("tools_products", []), ("policy_business", [])]


def _digest(tmp_path, n=12):
    render.render_digest("2026-07-31", _groups(_items(n)), [], tmp_path, total_records=n)
    return (tmp_path / "index.html").read_text(encoding="utf-8")


def _css():
    return re.sub(r"/\*.*?\*/", "", (ROOT / "static" / "digest.css").read_text(encoding="utf-8"),
                  flags=re.S)


# ── 렌더 계약 ────────────────────────────────────────────────────────────────

def test_every_home_story_is_a_row_that_can_open_the_rail(tmp_path):
    """행 전체가 레일을 여는 버튼이고, 제목만 원문 `<a>` 다. 행을 `<a>` 로 감싸면
    제목과 레일 열기가 같은 클릭이 된다."""
    page = _digest(tmp_path, 12)
    assert page.count('data-story ') + page.count("data-story>") >= 12 or \
        page.count("data-story=") >= 12 or page.count("data-story ") >= 12
    assert page.count('data-story-id=') >= 12
    assert page.count('role="button"') >= 12
    assert page.count('tabindex="0"') >= 12
    for cls in ("lead-title", "card-title", "worth-title", "brief-title"):
        assert f'class="{cls} story-headline"' in page, f"{cls} 가 story-headline 이 아니다"


def test_story_rows_are_not_wrapped_in_a_link(tmp_path):
    page = _digest(tmp_path, 4)
    for tag in ("article class=\"lead\"", "article class=\"also-card\"",
                "div class=\"worth-row\"", "div class=\"brief-row\""):
        # 행 태그가 <a 로 시작하지 않는다
        assert f"<a {tag}" not in page
    assert "<a class=\"lead\"" not in page
    assert "<a class=\"also-card\"" not in page
    assert "<a class=\"brief-row\"" not in page


def test_each_row_ships_a_comment_count_slot(tmp_path):
    """건수는 JS 가 한 번에 칠한다. 슬롯이 없으면 집계를 붙여 넣을 곳이 없다."""
    page = _digest(tmp_path, 12)
    assert page.count("data-comment-count") == 12
    assert "Add the first comment" in page


def test_the_rail_shell_is_on_the_digest_and_starts_closed(tmp_path):
    page = _digest(tmp_path, 4)
    assert 'data-comment-rail' in page
    assert 'data-rail-close' in page
    assert 'data-rail-follow' in page
    assert 'data-rail-input' in page
    assert 'Post thread' in page
    assert 'No comments yet' in page
    assert 'Start the first thread below.' in page
    assert 'data-vis="public"' in page and 'data-vis="private"' in page
    # hidden 으로 시작한다 — 없으면 빈 레일이 400px 를 항상 차지한다
    assert re.search(r'data-comment-rail[^>]*\bhidden\b', page)


def test_comments_js_is_copied_and_linked(tmp_path):
    _digest(tmp_path, 1)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'src="static/comments.js"' in page
    assert (tmp_path / "static" / "comments.js").exists()


def test_category_page_also_gets_the_rail(tmp_path):
    items = _items(3)
    render.render_category_page("2026-07-31", "model_releases", _groups(items), tmp_path,
                                in_archive=False, one_liner="x", cap=10, min_sig=0.3,
                                total_records=3)
    page = (tmp_path / "model_releases.html").read_text(encoding="utf-8")
    assert 'data-comment-rail' in page
    assert page.count("data-comment-count") == 3
    assert page.count('role="button"') >= 3
    assert 'src="static/comments.js"' in page


def test_rail_css_is_a_400px_side_panel_that_can_hide(tmp_path):
    css = _css()
    assert re.search(r"\.comment-rail\s*\{[^}]*width:\s*400px", css)
    assert ".comment-rail[hidden]" in css and "display:none" in re.search(
        r"\.comment-rail\[hidden\]\s*\{([^}]*)\}", css).group(1).replace(" ", "")
    assert "1100px" in css


def test_open_rail_compacts_digest_type_and_logos():
    """레일이 열리면 제목 clamp 와 로고 슬롯이 뷰포트/고정폭을 그대로 써서 기사가
    세로로만 길어진다. 열린 동안에만 글자·슬롯을 줄인다."""
    css = _css()
    compact = ".digest-shell.is-rail-open"
    for sel in (".lead-title", ".card-title", ".worth-title", ".imgslot-lead",
                ".imgslot-thumb", ".imgslot-card"):
        assert f"{compact} {sel}" in css, f"레일 열림에 {sel} 축소가 없다"
    lead = re.search(r"\.digest-shell\.is-rail-open \.lead-title\s*\{([^}]*)\}", css)
    assert lead and "24px" in lead.group(1)
    thumb = re.search(r"\.digest-shell\.is-rail-open \.imgslot-thumb\s*\{([^}]*)\}", css)
    assert thumb and "72px" in thumb.group(1)


def test_comment_css_does_not_bring_archivo_back():
    """조판은 Mona Sans 다. 스펙이 Archivo 를 말해도 그 폰트는 2026-08-07 에 폐기됐다."""
    css = _css()
    assert "Archivo" not in css
    assert "Mona Sans" in css


# ── comments.js 로직 (node) ──────────────────────────────────────────────────

_HARNESS = textwrap.dedent("""
    const store = {};
    globalThis.localStorage = {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; }
    };
    globalThis.window = {
      addEventListener: () => {},
      dispatchEvent: () => true,
      AIDigestFollow: {
        saveItem: () => {},
        isSaved: () => false,
        toggleSave: () => true
      }
    };
    globalThis.CustomEvent = class { constructor(n, o) { this.type = n; this.detail = o && o.detail; } };
    globalThis.document = {
      readyState: 'complete',
      querySelectorAll: () => [],
      querySelector: () => null,
      addEventListener: () => {},
      createEvent: () => ({ initEvent: () => {} })
    };
    eval(require('fs').readFileSync(process.argv[2], 'utf8'));
    const C = globalThis.window.AIDigestComments || globalThis.AIDigestComments;
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
        proc = subprocess.run([NODE, str(hp), str(COMMENTS_JS)],
                              capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        pytest.fail(f"comments.js 실행 실패:\n{proc.stderr}\n{proc.stdout}")
    return dict(json.loads(proc.stdout))


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_posting_a_thread_and_a_reply_round_trips():
    got = _run_js("""
      const top = C.addComment({story_id:'s1', body:'hello', visibility:'public'});
      log('top_ok', !!(top && top.id && top.parent_id == null));
      const reply = C.addComment({story_id:'s1', parent_id: top.id, body:'re', visibility:'public'});
      log('reply_parent', reply.parent_id === top.id);
      const threads = C.threadsFor('s1');
      log('thread_count', threads.length);
      log('reply_count', threads[0].replies.length);
      log('reply_body', threads[0].replies[0].body);
    """)
    assert got["top_ok"] is True
    assert got["reply_parent"] is True
    assert got["thread_count"] == 1
    assert got["reply_count"] == 1
    assert got["reply_body"] == "re"


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_a_reply_to_a_reply_is_rejected():
    """한 단만. parent 가 이미 답글이면 거절 — UI 가 아니라 저장 규칙이다."""
    got = _run_js("""
      const top = C.addComment({story_id:'s1', body:'hello', visibility:'public'});
      const reply = C.addComment({story_id:'s1', parent_id: top.id, body:'re', visibility:'public'});
      const deep = C.addComment({story_id:'s1', parent_id: reply.id, body:'too deep', visibility:'public'});
      log('rejected', deep == null);
      log('still_one_reply', C.threadsFor('s1')[0].replies.length);
    """)
    assert got["rejected"] is True
    assert got["still_one_reply"] == 1


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_private_comments_are_visible_only_to_their_author():
    got = _run_js("""
      C.setAuthor('Ada');
      C.addComment({story_id:'s1', body:'secret', visibility:'private'});
      C.addComment({story_id:'s1', body:'open', visibility:'public'});
      log('ada_sees', C.threadsFor('s1').length);
      C.setAuthor('Bea');
      const bea = C.threadsFor('s1');
      log('bea_sees', bea.length);
      log('bea_body', bea[0].body);
    """)
    assert got["ada_sees"] == 2
    assert got["bea_sees"] == 1
    assert got["bea_body"] == "open"


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_counts_come_from_one_aggregate_not_per_story():
    got = _run_js("""
      C.addComment({story_id:'a', body:'1', visibility:'public'});
      C.addComment({story_id:'a', body:'2', visibility:'public'});
      C.addComment({story_id:'b', body:'3', visibility:'public'});
      const counts = C.countsByStory();
      log('a', counts.a);
      log('b', counts.b);
      log('keys', Object.keys(counts).sort().join(','));
    """)
    assert got["a"] == 2
    assert got["b"] == 1
    assert got["keys"] == "a,b"


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_threads_sort_by_latest_activity_replies_oldest_first():
    got = _run_js("""
      const t1 = C.addComment({story_id:'s', body:'old thread', visibility:'public'});
      const t2 = C.addComment({story_id:'s', body:'new thread', visibility:'public'});
      C.addComment({story_id:'s', parent_id: t1.id, body:'r1', visibility:'public'});
      C.addComment({story_id:'s', parent_id: t1.id, body:'r2', visibility:'public'});
      const threads = C.threadsFor('s');
      // t1 이 답글 때문에 더 최근 활동 → 앞
      log('first_body', threads[0].body);
      log('reply0', threads[0].replies[0].body);
      log('reply1', threads[0].replies[1].body);
      log('second_body', threads[1].body);
    """)
    assert got["first_body"] == "old thread"
    assert got["reply0"] == "r1"
    assert got["reply1"] == "r2"
    assert got["second_body"] == "new thread"


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_blank_bodies_are_rejected():
    got = _run_js("""
      log('empty', C.addComment({story_id:'s', body:'   ', visibility:'public'}) == null);
      log('stored', C.threadsFor('s').length);
    """)
    assert got["empty"] is True
    assert got["stored"] == 0
