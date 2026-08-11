"""admin 페이지 — 오버레이 병합 규칙 · 검증 · 렌더 계약 (2026-08-11).

이 파일의 핵심은 **파이썬과 JS 의 대조**다. `config._apply_overlay`(파이프라인이 실제로 쓰는
것)와 `static/admin_rules.js` 의 `applyOverlay`(admin 화면의 미리보기)는 같은 규칙의 두 구현
이고, 갈라지면 "화면에서는 지웠는데 계속 수집되는" 종류의 버그가 된다. 눈으로 맞춰 두는 건
한 번은 되지만 다음 세션에는 안 되므로, 같은 픽스처를 양쪽에 넣고 결과를 비교한다.

node 가 없는 환경에서는 대조만 스킵한다(CI ubuntu-latest 에는 있다).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

import config
import render

ROOT = Path(__file__).resolve().parent.parent
RULES_JS = ROOT / "static" / "admin_rules.js"
NODE = shutil.which("node")

# 양쪽에 그대로 먹이는 베이스. sources.yaml 을 읽지 않는다 — 그 파일이 바뀌면 테스트가
# 같이 흔들려서, 병합 규칙이 깨진 건지 소스 구성이 바뀐 건지 구분할 수 없게 된다.
BASE = [
    {"id": "openai", "name": "OpenAI News", "feed_url": "https://openai.com/rss.xml",
     "category": "model_releases", "parse": "easy", "status": "verified", "enabled": True,
     "full_text": False, "sitemap_paths": ["/news/"], "max_entries": None, "notes": "n1"},
    {"id": "arxiv_ai", "name": "arXiv cs.AI", "feed_url": "https://rss.arxiv.org/rss/cs.AI",
     "category": "research", "parse": "easy", "status": "verified", "enabled": True,
     "full_text": False, "sitemap_paths": ["/news/"], "max_entries": 25, "notes": ""},
    {"id": "hn_show", "name": "HN Show", "feed_url": "https://hn.example/show.rss",
     "category": "community_takes", "parse": "medium", "status": "verify", "enabled": False,
     "full_text": False, "sitemap_paths": ["/news/"], "max_entries": None, "notes": ""},
]

# (이름, 오버레이 entries) — 규칙의 각 분기를 하나씩 밟는다.
CASES = [
    ("empty", []),
    ("add_new", [{"id": "newsrc", "name": "New Source", "feed_url": "https://new.example/f.xml",
                  "category": "research", "parse": "medium", "status": "verify"}]),
    ("add_new_defaults", [{"id": "bare", "name": "Bare", "feed_url": "https://bare.example/f",
                           "category": "tools_products"}]),
    ("disable_curated", [{"id": "openai", "enabled": False}]),
    ("rename_curated", [{"id": "openai", "name": "OpenAI (renamed)"}]),
    ("delete_curated", [{"id": "openai", "deleted": True}]),
    ("delete_then_add_other", [{"id": "openai", "deleted": True},
                               {"id": "x1", "name": "X1", "feed_url": "https://x1.example/f",
                                "category": "model_releases"}]),
    ("move_category", [{"id": "arxiv_ai", "category": "policy_business"}]),
    ("max_entries_override", [{"id": "arxiv_ai", "max_entries": 5}]),
    ("max_entries_null", [{"id": "arxiv_ai", "max_entries": None}]),
    ("enable_disabled_one", [{"id": "hn_show", "enabled": True}]),
    ("full_text_on", [{"id": "openai", "full_text": True}]),
    ("sitemap_paths", [{"id": "openai", "parse": "sitemap", "sitemap_paths": ["/blog/", "/news/"]}]),
    # 아래는 전부 "조용히 버려야 하는" 입력이다.
    ("junk_no_id", [{"name": "No ID", "feed_url": "https://x/f", "category": "research"}]),
    ("junk_blank_id", [{"id": "   ", "name": "Blank", "feed_url": "https://x/f", "category": "research"}]),
    ("junk_new_without_name", [{"id": "nameless", "feed_url": "https://x/f", "category": "research"}]),
    ("junk_new_without_url", [{"id": "urlless", "name": "No URL", "category": "research"}]),
    ("junk_bad_category", [{"id": "badcat", "name": "Bad", "feed_url": "https://x/f",
                            "category": "not_a_category"}]),
    ("junk_empty_object", [{}]),
    ("junk_id_only_patch", [{"id": "openai"}]),
    ("junk_unknown_field", [{"id": "openai", "totally_unknown": 1}]),
    # id 변경 시도는 무시돼야 한다 — _OVERRIDABLE 에 id 가 없다.
    ("junk_id_rename_attempt", [{"id": "openai", "new_id": "other"}]),
    ("duplicate_entries", [{"id": "openai", "enabled": False}, {"id": "openai", "name": "Second"}]),
]


def _py_merge(entries: list[dict]) -> list[dict]:
    """파이썬 쪽 결과를 비교 가능한 dict 목록으로."""
    base_sources = [config._source_from_row(dict(r), r["category"]) for r in BASE]
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "o.json"
        p.write_text(json.dumps({"sources": entries}), encoding="utf-8")
        merged = config._apply_overlay(base_sources, p)
    return [config._row_of(s) for s in merged]


def _js_merge_all() -> list[list[dict]]:
    """node 로 모든 케이스를 한 번에 돌린다(프로세스를 케이스마다 띄우면 느리다)."""
    harness = textwrap.dedent("""
        const fs = require('fs');
        eval(fs.readFileSync(process.argv[2], 'utf8'));
        const payload = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
        const out = payload.cases.map(function (entries) {
          return AdminRules.applyOverlay(payload.base, entries, payload.order);
        });
        process.stdout.write(JSON.stringify(out));
    """)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "h.js"
        hp.write_text(harness, encoding="utf-8")
        pp = Path(td) / "p.json"
        pp.write_text(json.dumps({
            "base": BASE,
            "cases": [entries for _name, entries in CASES],
            "order": config.CATEGORY_ORDER,
        }), encoding="utf-8")
        proc = subprocess.run([NODE, str(hp), str(RULES_JS), str(pp)],
                              capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        pytest.fail(f"admin_rules.js 실행 실패:\n{proc.stderr}")
    return json.loads(proc.stdout)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS/파이썬 대조 스킵")
def test_the_two_overlay_implementations_agree():
    """`config._apply_overlay` 와 `admin_rules.applyOverlay` 가 같은 답을 내는지.

    이게 깨지면 admin 의 미리보기가 파이프라인의 실제 동작과 다르다는 뜻이다 — 화면에서
    지운 소스가 계속 수집되거나, 추가한 소스가 조용히 무시된다. 어느 쪽이든 화면이
    거짓말을 하는 것이므로 두 구현 중 **틀린 쪽을 고쳐야 하고**, 테스트를 느슨하게
    만들어서 넘기면 안 된다.
    """
    js_results = _js_merge_all()
    assert len(js_results) == len(CASES)
    for (name, entries), js_rows in zip(CASES, js_results):
        py_rows = _py_merge(entries)
        assert [r["id"] for r in js_rows] == [r["id"] for r in py_rows], \
            f"[{name}] 병합 결과의 소스 목록/순서가 다르다"
        for py_row, js_row in zip(py_rows, js_rows):
            for key in ("name", "feed_url", "category", "parse", "status", "enabled",
                        "full_text", "max_entries", "notes", "sitemap_paths"):
                assert js_row[key] == py_row[key], \
                    f"[{name}] {py_row['id']}.{key}: JS={js_row[key]!r} PY={py_row[key]!r}"


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_overridable_field_list_matches_python():
    """`_OVERRIDABLE` 두 벌이 같은지. 한쪽에만 필드가 추가되면 그 필드는 admin 에서 고쳐도
    파이프라인이 무시하거나(JS 에만 있음), 미리보기에 안 보이는데 적용된다(파이썬에만 있음)."""
    proc = subprocess.run(
        [NODE, "-e",
         f"eval(require('fs').readFileSync({str(RULES_JS)!r},'utf8'));"
         "process.stdout.write(JSON.stringify(AdminRules.OVERRIDABLE))"],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == list(config._OVERRIDABLE)


@pytest.mark.skipif(NODE is None, reason="node 없음")
def test_key_rule_matches_python_and_rejects_spaces():
    """소스 id · 토픽 key 규칙이 파이썬과 같은지. 공백이 통과하면 필터가 조용히 깨진다 —
    `data-topics` 가 공백 구분 목록이라 키 하나가 두 개의 가짜 토큰으로 쪼개진다."""
    samples = ["code", "my_topic", "a1", "my topic", "Code", "kebab-case", "", "  ", "tab\tkey",
               "한글", "under_score_ok", "trailing "]
    proc = subprocess.run(
        [NODE, "-e",
         f"eval(require('fs').readFileSync({str(RULES_JS)!r},'utf8'));"
         f"const s={json.dumps(samples)};"
         "process.stdout.write(JSON.stringify(s.map(x=>AdminRules.KEY_RE.test(x))))"],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    js_ok = json.loads(proc.stdout)
    py_ok = [bool(config._TOPIC_KEY_OK.match(s)) for s in samples]
    assert js_ok == py_ok, dict(zip(samples, zip(js_ok, py_ok)))
    # 특히 이 두 개는 반드시 거부돼야 한다.
    assert js_ok[samples.index("my topic")] is False
    assert js_ok[samples.index("Code")] is False


@pytest.mark.skipif(NODE is None, reason="node 없음")
@pytest.mark.parametrize("draft,is_new,expect_ok", [
    ({"id": "ok_one", "name": "N", "feed_url": "https://x/f", "parse": "easy"}, True, True),
    ({"id": "Bad ID", "name": "N", "feed_url": "https://x/f", "parse": "easy"}, True, False),
    ({"id": "ok_one", "name": "", "feed_url": "https://x/f", "parse": "easy"}, True, False),
    ({"id": "ok_one", "name": "N", "feed_url": "", "parse": "easy"}, True, False),
    # URL 이 아닌 feed_url 은 gnews 에서만 허용된다(그때는 검색어다).
    ({"id": "ok_one", "name": "N", "feed_url": "not-a-url", "parse": "easy"}, True, False),
    ({"id": "ok_one", "name": "N", "feed_url": "openai news", "parse": "gnews"}, True, True),
    ({"id": "openai", "name": "N", "feed_url": "https://x/f", "parse": "easy"}, True, False),
    ({"id": "openai", "name": "N", "feed_url": "https://x/f", "parse": "easy"}, False, True),
    ({"id": "ok_one", "name": "N", "feed_url": "https://x/f", "parse": "easy",
      "max_entries": 0}, True, False),
    ({"id": "ok_one", "name": "N", "feed_url": "https://x/f", "parse": "easy",
      "max_entries": 5}, True, True),
    ({"id": "ok_one", "name": "N", "feed_url": "https://x/f", "parse": "sitemap",
      "sitemap_paths": []}, True, False),
    ({"id": "ok_one", "name": "N", "feed_url": "https://x/f", "parse": "sitemap",
      "sitemap_paths": ["/news/"]}, True, True),
])
def test_source_validation(draft, is_new, expect_ok):
    """저장 전 검증. 통과 여부만 본다 — 문구는 UX 라 바뀔 수 있지만 판정은 계약이다."""
    proc = subprocess.run(
        [NODE, "-e",
         f"eval(require('fs').readFileSync({str(RULES_JS)!r},'utf8'));"
         f"const r=AdminRules.validateSource({json.dumps(draft)},{json.dumps(is_new)},"
         f"['openai','arxiv_ai']);"
         "process.stdout.write(JSON.stringify(r))"],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    problem = json.loads(proc.stdout)
    assert (problem is None) is expect_ok, f"draft={draft} -> {problem!r}"


# ── 렌더 계약 ────────────────────────────────────────────────────────────────

def test_admin_page_ships_no_credentials(tmp_path):
    """**가장 중요한 테스트.** 이 페이지는 공개 사이트에 올라가므로 토큰이 한 글자도 구워져
    있으면 안 된다. 사용자가 런타임에 넣고 그 브라우저에만 머무는 게 이 설계의 전제다
    (PROJECT_MEMO §10.5 — 키 노출 3회 이력).

    placeholder 의 `github_pat_…`(유니코드 줄임표)는 토큰 모양이 아니라 안 걸린다.
    """
    import re
    render.render_admin_page(tmp_path, repo="owner/name")
    page = (tmp_path / "admin.html").read_text(encoding="utf-8")
    forbidden = {
        "fine-grained PAT": r"github_pat_[A-Za-z0-9_]{20,}",
        "classic PAT": r"ghp_[A-Za-z0-9]{20,}",
        "OAuth token": r"gho_[A-Za-z0-9]{20,}",
        "Gemini key": r"AIza[A-Za-z0-9_\-]{20,}",
    }
    for label, pattern in forbidden.items():
        assert not re.search(pattern, page), f"{label} 모양의 문자열이 산출물에 들어갔다"


def test_admin_page_bakes_the_current_config(tmp_path):
    """토큰 없이 열어도 지금 설정이 보여야 한다(연결 전 미리보기). 구운 JSON 이 비면
    화면이 빈 목록으로 서고, 사용자는 설정이 날아간 줄 안다."""
    import re
    render.render_admin_page(tmp_path, repo="owner/name")
    page = (tmp_path / "admin.html").read_text(encoding="utf-8")
    baked = json.loads(re.search(
        r'<script id="adm-baked" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert baked["repo"] == "owner/name"
    assert len(baked["baseSources"]) == len(config.load(overlay=None).sources)
    assert [c["key"] for c in baked["categories"]] == config.CATEGORY_ORDER
    assert len(baked["topics"]) == len(config.TOPIC_ORDER)
    assert baked["paths"] == {"sources": config.CUSTOM_SOURCES_FILE.name,
                              "topics": config.TOPICS_FILE.name}
    # parse 종류는 fetch 의 분기와 맞아야 한다 — 없는 값을 고르면 조용히 RSS 로 떨어진다.
    fetch_src = (ROOT / "fetch.py").read_text(encoding="utf-8")
    for kind in baked["parseKinds"]:
        if kind["key"] in ("easy", "medium", "hard"):
            continue      # 셋은 기본 RSS 분기를 공유한다(별도 핸들러가 없다)
        assert f'"{kind["key"]}"' in fetch_src, f"parse: {kind['key']} 를 fetch 가 모른다"


def test_admin_rules_js_is_copied_next_to_the_css(tmp_path):
    """admin.html 이 `static/admin_rules.js` 를 불러오는데 파일이 안 따라가면 페이지가
    통째로 죽는다(RULES 가 undefined 라 첫 렌더에서 예외). write_assets 가 같이 쓴다."""
    render.render_admin_page(tmp_path, repo="owner/name")
    copied = tmp_path / "static" / "admin_rules.js"
    assert copied.exists(), "admin_rules.js 가 output/static 에 복사되지 않았다"
    assert copied.read_text(encoding="utf-8") == RULES_JS.read_text(encoding="utf-8")
    page = (tmp_path / "admin.html").read_text(encoding="utf-8")
    assert 'src="static/admin_rules.js"' in page


def test_admin_rules_js_stays_free_of_browser_globals():
    """이 파일은 node 에서 그대로 돌아야 한다(그래야 파이썬과 대조할 수 있다).
    DOM/fetch/localStorage 가 들어오면 대조 테스트가 조용히 스킵되기 시작한다.

    주석은 걷어내고 본다 — 주석에서 "localStorage 를 쓰지 말라"고 적는 것 자체는 위반이 아니다.
    """
    import re
    src = RULES_JS.read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)//.*$", "", code)
    for banned in ("document.", "window.", "localStorage", "fetch(", "XMLHttpRequest"):
        assert banned not in code, f"admin_rules.js 에 {banned!r} 가 들어왔다 — node 에서 못 돈다"


def test_every_display_rule_in_admin_css_pairs_with_hidden():
    """`display` 를 주는 저작자 규칙은 브라우저 기본 `[hidden]{display:none}` 을 이긴다 →
    JS 의 `.hidden = true` 가 조용히 아무 일도 안 하게 된다. 2026-08-07 에 필터 서랍이
    실제로 그렇게 계속 열려 있었고, admin 은 토글이 8개라 같은 사고가 나면 편집기가 늘
    펼쳐진 채로 선다. **JS 가 hidden 으로 토글하는 선택자**만 검사한다."""
    css = (ROOT / "static" / "digest.css").read_text(encoding="utf-8")
    toggled = [".adm-fields", ".adm-field", ".adm-btn", ".adm-dirty", ".adm-backfill",
               "[data-panel]"]
    for sel in toggled:
        assert f"{sel}[hidden]" in css, \
            f"{sel} 에 display 를 주면서 `{sel}[hidden] {{ display:none }}` 짝을 안 뒀다"
