"""HTML 렌더링: 오늘 다이제스트 + 카테고리 뷰 + 검색 + 아카이브(주간 리캡) + 아카이브 인덱스.

디자인: Claude Design(claude.ai/design) 프로젝트 "AI-Digest UI Redesign" 캔버스에서 포팅한
"Modernist" 컨셉 (2026-07-27 적용). Archivo 폰트 단일 사용, radius 0(완전히 각짐), 5색 팔레트
라이브 스위처(localStorage 저장). 카테고리별 섹션 대신 유의성 기준 플랫 랭킹(리드 스토리 1건 +
3열 그리드 + 목록 + in-brief) 구조. 이전 SIGNAL 디자인(시그널 미터/히어로 카드)은 폐기.
"""
from __future__ import annotations

import json
import re
from datetime import date as _date, timedelta as _timedelta
from pathlib import Path

from jinja2 import DictLoader, Environment

from config import CATEGORY_LABELS, CATEGORY_ORDER
from store import label_sort_key


def group_by_category(items: list[dict], cap: int | None = None) -> list[tuple[str, list[dict]]]:
    """카테고리별 유의성 내림차순 그룹. community_takes 는 v1 제외.

    cap 지정 시 카테고리당 상한 적용(pipeline: 아직 안 잘린 풀에 사용),
    None 이면 정렬만(rerender: DB 의 게재분은 이미 잘려 있음).
    pipeline._rank_and_cap 과 rerender._grouped 로 나뉘어 있던 걸 합친 것 — 따로 두니
    한쪽만 고쳐져서 두 경로의 정렬 결과가 갈릴 수 있었음."""
    groups: list[tuple[str, list[dict]]] = []
    for cat in CATEGORY_ORDER:
        if cat == "community_takes":
            continue
        picked = sorted(
            (it for it in items if it["category"] == cat),
            key=lambda it: (it["significance"], it.get("published") or ""),
            reverse=True,
        )
        groups.append((cat, picked[:cap] if cap else picked))
    return groups

# ---- 팔레트 (Claude Design 캔버스의 라이브 컬러피커에서 포팅) ----
PALETTES = [
    {"name": "White · Cobalt", "g": "#ffffff", "g2": "#eef1fb", "bar": "#16182b", "ink": "#1e1b16",
     "ink2": "#4a4436", "muted": "#6b6355", "n1": "#9a917c", "n2": "#bdb49d", "acc": "#2438d6",
     "accd": "#1b2aa0", "acclt": "#8f9bf0", "grgb": "255,255,255", "inkrgb": "30,27,22"},
    {"name": "White · Teal", "g": "#ffffff", "g2": "#eef6f3", "bar": "#14201d", "ink": "#1a1d18",
     "ink2": "#3d4438", "muted": "#646b5b", "n1": "#909683", "n2": "#b9bfa9", "acc": "#0e7c6b",
     "accd": "#095e50", "acclt": "#5bbfae", "grgb": "255,255,255", "inkrgb": "26,29,24"},
    {"name": "White · Raspberry", "g": "#ffffff", "g2": "#fbeef2", "bar": "#1f0f16", "ink": "#1f1518",
     "ink2": "#4a3238", "muted": "#6e5157", "n1": "#8f7a80", "n2": "#c7b3ba", "acc": "#c2185b",
     "accd": "#8f0f41", "acclt": "#e8779e", "grgb": "255,255,255", "inkrgb": "31,21,24"},
    {"name": "White · Ember", "g": "#ffffff", "g2": "#fbf1ea", "bar": "#1f1c17", "ink": "#201d16",
     "ink2": "#463f33", "muted": "#6b6255", "n1": "#98907f", "n2": "#c0b8a6", "acc": "#c2410c",
     "accd": "#8f2f08", "acclt": "#f0a273", "grgb": "255,255,255", "inkrgb": "32,29,22"},
    {"name": "Mist · Signal red", "g": "#f3f2f2", "g2": "#eae9e9", "bar": "#201e1d", "ink": "#201e1d",
     "ink2": "#444141", "muted": "#605d5d", "n1": "#7d7979", "n2": "#bab6b6", "acc": "#ec3013",
     "accd": "#ae1800", "acclt": "#ff9783", "grgb": "243,242,242", "inkrgb": "32,30,29"},
]
DEFAULT_THEME = 4  # Mist · Signal red — styles.css 자체 기본값 + 기존 사이트 정체성과 가장 가까움

_PALETTES_JSON = json.dumps(PALETTES, ensure_ascii=False)


def _root_vars_css(palette: dict) -> str:
    decls = "".join(f"--{k}:{v};" for k, v in palette.items() if k != "name")
    return ":root{" + decls + "}"


_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900'
    '&display=swap" rel="stylesheet">'
)

# 저장된 팔레트(localStorage) 즉시 적용(깜빡임 방지) + 스위처 버튼 동기화. <head> 초반에 배치.
_THEME_JS = (
    "<script>(function(){"
    "var PALETTES=" + _PALETTES_JSON + ";"
    "var KEY='ai-digest-theme';"
    "var stored=parseInt(localStorage.getItem(KEY),10);"
    "var i=(!isNaN(stored)&&stored>=0&&stored<PALETTES.length)?stored:" + str(DEFAULT_THEME) + ";"
    "function apply(idx){var t=PALETTES[idx],root=document.documentElement.style;"
    "for(var k in t){if(k!=='name')root.setProperty('--'+k,t[k]);}}"
    "apply(i);"
    "window.__aiDigestSetTheme=function(idx){localStorage.setItem(KEY,idx);apply(idx);sync(idx);};"
    "function sync(idx){var els=document.querySelectorAll('[data-theme-btn]');"
    "for(var j=0;j<els.length;j++){els[j].setAttribute('aria-pressed',"
    "(+els[j].getAttribute('data-theme-btn')===idx)?'true':'false');}}"
    "document.addEventListener('DOMContentLoaded',function(){sync(i);});"
    "})();</script>"
)

_BASE_CSS = """
* { box-sizing: border-box; }
body { margin:0; background:var(--g); color:var(--ink); font-family:Archivo,system-ui,sans-serif; }
a { color:var(--accd); }
a:hover { color:var(--acc); }
.wrap { max-width:1280px; margin:0 auto; background:var(--g);
        border-left:1px solid rgba(var(--inkrgb),.15); border-right:1px solid rgba(var(--inkrgb),.15); }
.masthead { background:var(--bar); padding:16px 44px 0; }
.masthead-row1 { display:flex; align-items:center; justify-content:space-between; gap:24px;
                 padding-bottom:14px; flex-wrap:wrap; }
.masthead-id { display:flex; align-items:baseline; gap:16px; flex-wrap:wrap; }
.wordmark { font:900 15px Archivo,sans-serif; letter-spacing:.26em; text-transform:uppercase;
            color:var(--g); text-decoration:none; }
.period-meta { font:500 12px Archivo,sans-serif; letter-spacing:.06em; color:rgba(var(--grgb),.55); }
.masthead-tools { display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
.search-form { display:flex; align-items:stretch; gap:0; min-width:260px; }
.search-field { display:flex; align-items:center; gap:10px; flex:1; border:1px solid rgba(var(--grgb),.35);
                padding:9px 12px; background:rgba(var(--grgb),.06); }
.search-field input { border:0; background:none; outline:0; flex:1; font:400 13px Archivo,sans-serif;
                       color:var(--g); min-width:0; }
.search-field input::placeholder { color:rgba(var(--grgb),.5); }
.records-chip { display:flex; align-items:center; background:var(--acc); color:var(--g);
                font:800 11px Archivo,sans-serif; letter-spacing:.1em; text-transform:uppercase;
                padding:0 14px; white-space:nowrap; }
.theme-picker { display:flex; gap:6px; align-items:center; }
.theme-swatch { display:flex; padding:2px; background:none; border:0; cursor:pointer;
                box-shadow:0 0 0 1px rgba(var(--grgb),.3); }
.theme-swatch[aria-pressed="true"] { box-shadow:0 0 0 2px var(--g); }
.theme-swatch span { width:10px; height:10px; display:block; }
.nav { display:flex; align-items:stretch; gap:0; border-top:1px solid rgba(var(--grgb),.18); flex-wrap:wrap; }
.nav a { display:flex; align-items:baseline; gap:7px; padding:14px 22px 12px 0; text-decoration:none;
         border-bottom:3px solid transparent; }
.nav a:not(:first-child) { padding-left:22px; }
.nav a.active { border-bottom-color:var(--acc); }
.nav a .tab-label { font:700 13px Archivo,sans-serif; letter-spacing:.1em; text-transform:uppercase;
                     color:rgba(var(--grgb),.65); }
.nav a.active .tab-label { font-weight:800; color:var(--g); }
.nav a .tab-count { font:700 11px Archivo,sans-serif; color:rgba(var(--grgb),.4); font-variant-numeric:tabular-nums; }
.nav a.active .tab-count { color:var(--acclt); }
.nav a.archive-link { margin-left:auto; padding:14px 0 12px 22px; }
.nav a.archive-link .tab-label { color:var(--acclt); }
.simple-header { background:var(--bar); padding:18px 36px; display:flex; align-items:baseline;
                 justify-content:space-between; flex-wrap:wrap; gap:10px; }
.simple-header-id { display:flex; align-items:baseline; gap:16px; }
.simple-header-sub { font:500 12px Archivo,sans-serif; color:rgba(var(--grgb),.5); }
.simple-header nav { display:flex; gap:18px; }
.simple-header nav a { font:700 11px Archivo,sans-serif; letter-spacing:.12em; text-transform:uppercase;
                        text-decoration:none; color:rgba(var(--grgb),.6); }
.simple-header nav a.accent { color:var(--acc); }
footer.site-footer { max-width:1280px; margin:0 auto; padding:20px 44px; border-top:1px solid rgba(var(--inkrgb),.2);
                      display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; }
.term-line { font-family:Archivo,sans-serif; font-size:.78rem; color:rgba(var(--inkrgb),.5); }
.term-line::before { content:'$ '; color:var(--accd); }
footer.site-footer nav a { color:rgba(var(--inkrgb),.6); font:700 11px Archivo,sans-serif; letter-spacing:.08em;
                            text-transform:uppercase; text-decoration:none; }
footer.site-footer nav a:hover { color:var(--ink); }
"""

_HOME_CSS = """
.body-grid { display:grid; grid-template-columns:1fr 300px; gap:0; }
@media (max-width:900px) { .body-grid { grid-template-columns:1fr; } }
.main-col { padding:34px 40px 40px; border-right:2px solid rgba(var(--inkrgb),.4); }
@media (max-width:900px) { .main-col { border-right:0; padding:28px 20px; } }
.kicker-row { display:flex; align-items:baseline; gap:14px; margin-bottom:16px; flex-wrap:wrap; }
.kicker { font:900 13px Archivo,sans-serif; letter-spacing:.16em; text-transform:uppercase; color:var(--accd); }
.kicker-sub { font:500 12px Archivo,sans-serif; letter-spacing:.06em; color:rgba(var(--inkrgb),.5); }
.lead-grid { display:grid; grid-template-columns:88px 1fr; gap:0; border-top:2px solid var(--acc); padding-top:18px; }
@media (max-width:600px) { .lead-grid { grid-template-columns:1fr; } .lead-num { display:none; } }
.lead-num { font:900 64px/0.85 Archivo,sans-serif; color:var(--acc); font-variant-numeric:tabular-nums;
            letter-spacing:-.04em; }
.tag-row { display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
.tag { font:800 10px Archivo,sans-serif; letter-spacing:.12em; padding:4px 8px; }
.tag-ink { background:var(--ink); color:var(--g); }
.tag-acc { background:var(--acc); color:var(--g); }
.lead-title { margin:0 0 16px; font:900 clamp(32px,5vw,62px)/0.94 Archivo,sans-serif; letter-spacing:-.038em;
              color:var(--ink); text-decoration:none; display:block; }
.lead-dek { margin:0 0 16px; font:400 19px/1.5 Archivo,sans-serif; color:var(--ink2); max-width:58ch; }
.byline-row { display:flex; gap:14px; align-items:center; flex-wrap:wrap; }
.byline-link { font:700 14px Archivo,sans-serif; color:var(--accd); text-decoration:none;
               border-bottom:2px solid var(--acc); padding-bottom:2px; }
.byline-source { font:700 11px Archivo,sans-serif; letter-spacing:.12em; text-transform:uppercase;
                 color:rgba(var(--inkrgb),.6); }
.hr2 { height:2px; background:rgba(var(--inkrgb),.4); margin:34px 0 26px; }
.grid3 { display:grid; grid-template-columns:repeat(3,1fr); gap:0; }
@media (max-width:700px) { .grid3 { grid-template-columns:1fr; gap:20px; } }
.grid3-col { padding:0 26px; }
.grid3-col:first-child { padding-left:0; }
.grid3-col:not(:last-child) { border-right:1px solid rgba(var(--inkrgb),.22); }
@media (max-width:700px) {
  .grid3-col:not(:last-child) { border-right:0; border-bottom:1px solid rgba(var(--inkrgb),.22); padding-bottom:20px; }
}
.rank-row { display:flex; align-items:baseline; gap:8px; margin-bottom:10px; }
.rank-num { font:900 20px Archivo,sans-serif; color:rgba(var(--inkrgb),.35); font-variant-numeric:tabular-nums; }
.rank-cat { font:700 10px Archivo,sans-serif; letter-spacing:.12em; text-transform:uppercase;
            color:rgba(var(--inkrgb),.55); }
.rank-cat.is-lead-cat { color:var(--accd); }
.item-h3 { margin:0 0 10px; font:800 25px/1.08 Archivo,sans-serif; letter-spacing:-.022em; color:var(--ink);
           text-decoration:none; display:block; }
.item-dek { margin:0 0 10px; font:400 14px/1.5 Archivo,sans-serif; color:var(--muted); }
.item-link { display:block; font:600 12px Archivo,sans-serif; color:var(--accd); text-decoration:none;
             margin-bottom:4px; }
.item-source { font:600 10px Archivo,sans-serif; letter-spacing:.1em; text-transform:uppercase;
               color:rgba(var(--inkrgb),.5); }
.split2 { display:grid; grid-template-columns:1fr 1fr; gap:0 40px; padding-top:20px; }
@media (max-width:700px) { .split2 { grid-template-columns:1fr; gap:28px; } }
.split2-h { font:900 12px Archivo,sans-serif; letter-spacing:.16em; text-transform:uppercase; color:var(--ink);
            margin-bottom:6px; }
.split2-h.dim { color:rgba(var(--inkrgb),.5); }
.wk-row { display:grid; grid-template-columns:26px 1fr; gap:10px; padding:12px 0;
          border-top:1px solid rgba(var(--inkrgb),.2); align-items:baseline; }
.wk-row:last-child { border-bottom:1px solid rgba(var(--inkrgb),.2); }
.wk-num { font:700 12px Archivo,sans-serif; color:rgba(var(--inkrgb),.4); font-variant-numeric:tabular-nums; }
.wk-cat { font:700 10px Archivo,sans-serif; letter-spacing:.12em; text-transform:uppercase;
          color:rgba(var(--inkrgb),.5); margin-bottom:3px; }
.wk-title { font:700 16px/1.25 Archivo,sans-serif; color:var(--ink); text-decoration:none; display:block; }
.wk-dek { font:400 13px/1.45 Archivo,sans-serif; color:var(--muted); margin-top:3px; }
.wk-link { display:inline-block; font:600 12px Archivo,sans-serif; color:var(--accd); text-decoration:none;
           margin-top:4px; }
.brief-row { display:grid; grid-template-columns:26px 1fr auto; gap:10px; padding:9px 0;
             border-top:1px solid rgba(var(--inkrgb),.14); text-decoration:none; align-items:baseline; }
.brief-row:last-child { border-bottom:1px solid rgba(var(--inkrgb),.14); }
.brief-num { font:600 11px Archivo,sans-serif; color:rgba(var(--inkrgb),.35); font-variant-numeric:tabular-nums; }
.brief-title { font:500 14px/1.3 Archivo,sans-serif; color:var(--ink2); display:block; }
.brief-link { font:500 11px Archivo,sans-serif; color:var(--accd); margin-top:2px; display:block; }
.brief-cat { font:600 9px Archivo,sans-serif; letter-spacing:.1em; text-transform:uppercase;
             color:rgba(var(--inkrgb),.4); white-space:nowrap; }
.empty-note { font:500 13px Archivo,sans-serif; color:rgba(var(--inkrgb),.5); padding:20px 0; }
.aside { padding:34px 26px 40px; background:var(--g2); }
.aside-h { font:900 11px Archivo,sans-serif; letter-spacing:.16em; text-transform:uppercase; color:var(--ink);
           margin-bottom:4px; }
.aside-sub { font:400 11px/1.45 Archivo,sans-serif; color:rgba(var(--inkrgb),.55); margin-bottom:14px; }
.band-row { margin-bottom:10px; }
.band-top { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:4px; }
.band-score { font:700 11px Archivo,sans-serif; color:var(--ink); font-variant-numeric:tabular-nums; }
.band-tier { font-weight:500; color:rgba(var(--inkrgb),.5); text-transform:uppercase; letter-spacing:.08em; }
.band-count { font:700 11px Archivo,sans-serif; color:var(--ink); font-variant-numeric:tabular-nums; }
.band-bar { height:12px; }
.source-alert { margin-top:22px; border:1px solid var(--acc); padding:12px 14px; }
.source-alert-h { font:800 10px Archivo,sans-serif; letter-spacing:.14em; text-transform:uppercase; color:var(--accd);
                   margin-bottom:6px; }
.source-alert-body { font:400 12px/1.45 Archivo,sans-serif; color:var(--ink); }
"""

_CATEGORY_CSS = """
.cat-body { background:var(--g); padding:32px 44px 40px; }
@media (max-width:700px) { .cat-body { padding:24px 20px 32px; } }
.cat-top { display:grid; grid-template-columns:1fr auto; gap:30px; align-items:end; padding-bottom:16px; }
@media (max-width:700px) { .cat-top { grid-template-columns:1fr; } }
.cat-title { margin:0 0 8px; font:900 clamp(30px,6vw,56px)/0.96 Archivo,sans-serif; letter-spacing:-.035em;
             color:var(--ink); }
.cat-dek { margin:0; font:400 16px/1.5 Archivo,sans-serif; color:var(--muted); max-width:60ch; }
.pill-row { display:flex; gap:8px; flex-wrap:wrap; }
.pill { border:1px solid rgba(var(--inkrgb),.35); color:var(--ink); font:700 11px Archivo,sans-serif;
        letter-spacing:.08em; text-transform:uppercase; padding:7px 12px; }
.pill.active { border-color:var(--acc); background:var(--acc); color:var(--g); }
.cat-row { display:grid; grid-template-columns:70px 1fr 220px; gap:0; padding:22px 0;
           border-bottom:1px solid rgba(var(--inkrgb),.18); text-decoration:none; align-items:start; }
@media (max-width:700px) { .cat-row { grid-template-columns:50px 1fr; } .cat-row-side { display:none; } }
.cat-score { font:900 22px Archivo,sans-serif; color:var(--acc); font-variant-numeric:tabular-nums; }
.cat-row-title { font:900 34px/1.04 Archivo,sans-serif; letter-spacing:-.03em; color:var(--ink); }
.cat-row-dek { font:400 15px/1.5 Archivo,sans-serif; color:var(--muted); margin-top:8px; max-width:66ch; }
.cat-row-link { font:600 13px Archivo,sans-serif; color:var(--accd); margin-top:8px; display:block; }
.cat-row-side .tag { margin-bottom:8px; }
.cat-row-side-source { font:600 11px/1.5 Archivo,sans-serif; letter-spacing:.08em; text-transform:uppercase;
                        color:rgba(var(--inkrgb),.6); }
.cat-footer { display:flex; justify-content:space-between; align-items:baseline; margin-top:26px; padding-top:14px;
              border-top:2px solid rgba(var(--inkrgb),.4); flex-wrap:wrap; gap:10px; }
.cat-footer-note { font:500 11px Archivo,sans-serif; letter-spacing:.08em; color:rgba(var(--inkrgb),.5); }
.cat-footer-link { font:700 11px Archivo,sans-serif; letter-spacing:.08em; text-transform:uppercase;
                    color:var(--accd); text-decoration:none; }
"""

_SEARCH_CSS = """
.search-page-body { max-width:720px; margin:0 auto; padding:0 0 40px; }
.search-hero { background:var(--bar); padding:14px 24px 0; }
.search-hero-row { display:flex; align-items:center; justify-content:space-between; gap:16px; padding-bottom:12px; }
.search-hero .wordmark { font-size:13px; }
.search-hero .search-field { max-width:340px; border-color:var(--acclt); }
.search-hero .search-field input { color:var(--g); }
#hitcount { margin-left:auto; font:700 10px Archivo,sans-serif; color:var(--acclt); white-space:nowrap; }
.results-body { padding:24px 24px 28px; }
.results-meta { font:600 12px Archivo,sans-serif; letter-spacing:.1em; text-transform:uppercase; color:var(--accd);
                margin-bottom:12px; }
.results-hr { height:2px; background:rgba(var(--inkrgb),.4); margin-bottom:0; }
.result-row { display:grid; grid-template-columns:56px 1fr; gap:0; padding:14px 0;
              border-bottom:1px solid rgba(var(--inkrgb),.18); text-decoration:none; align-items:start; }
.result-row.top-hit { background:rgba(var(--grgb),.5); padding:16px 0; }
.result-score { font:800 16px Archivo,sans-serif; color:var(--accd); font-variant-numeric:tabular-nums;
                 padding-left:10px; }
.result-row.top-hit .result-score { font-size:19px; font-weight:900; }
.result-title { font:700 19px/1.1 Archivo,sans-serif; letter-spacing:-.02em; color:var(--ink); }
.result-row.top-hit .result-title { font-size:24px; line-height:1.06; letter-spacing:-.024em; font-weight:800; }
.result-byline { font:500 11px Archivo,sans-serif; letter-spacing:.06em; text-transform:uppercase;
                  color:rgba(var(--inkrgb),.5); margin-top:4px; }
.result-row.top-hit .result-byline { font:600 12px Archivo,sans-serif; color:var(--accd); margin-top:6px; }
#results mark { background:color-mix(in srgb, var(--acc) 28%, var(--g)); color:var(--ink); }
.empty { font:500 13px Archivo,sans-serif; color:rgba(var(--inkrgb),.5); padding:16px 0; }
"""

_ARCHIVE_INDEX_CSS = """
.archive-body { background:var(--g); padding:30px 36px 36px; }
.archive-top { display:grid; grid-template-columns:1fr auto; gap:30px; align-items:end; padding-bottom:16px; }
.archive-title { grid-column:1/2; margin:0; font:900 clamp(28px,6vw,46px)/1 Archivo,sans-serif;
                  letter-spacing:-.032em; color:var(--ink); }
.archive-bars-label { grid-column:1/-1; order:3; font:500 11px Archivo,sans-serif; letter-spacing:.06em;
                       color:rgba(var(--inkrgb),.45); padding-top:8px; }
.archive-bars { grid-column:1/-1; order:4; display:flex; align-items:flex-end; gap:3px; height:74px;
                margin-top:6px; }
.archive-bars span { width:14px; }
.archive-table-head { display:grid; grid-template-columns:110px 90px 1fr 60px; gap:0; padding:12px 0;
                       border-bottom:1px solid rgba(var(--inkrgb),.3); font:800 10px Archivo,sans-serif;
                       letter-spacing:.14em; text-transform:uppercase; color:rgba(var(--inkrgb),.5); }
.archive-table-head span:last-child { text-align:right; }
.archive-row { display:grid; grid-template-columns:110px 90px 1fr 60px; gap:0; padding:14px 0;
               border-bottom:1px solid rgba(var(--inkrgb),.16); text-decoration:none; align-items:center; }
.archive-row.latest { background:var(--acclt2, rgba(var(--grgb),.6)); }
.archive-row-date { font:800 15px Archivo,sans-serif; color:var(--ink); font-variant-numeric:tabular-nums; }
.archive-row.latest .archive-row-date { color:var(--accd); }
.archive-row-bar { display:block; height:10px; }
.archive-row-top { font:700 16px/1.3 Archivo,sans-serif; color:var(--ink); padding-right:20px; }
.archive-row-count { font:700 14px Archivo,sans-serif; color:var(--ink); text-align:right; font-variant-numeric:tabular-nums; }
.archive-row.latest .archive-row-count { color:var(--accd); }
.archive-more { padding:16px 0 0; font:600 12px Archivo,sans-serif; letter-spacing:.06em; color:rgba(var(--inkrgb),.5); }
"""

_ARCHIVE_WEEK_CSS = """
.week-body { background:var(--g); padding:30px 36px 36px; }
.week-eyebrow { font:600 12px Archivo,sans-serif; letter-spacing:.14em; text-transform:uppercase;
                color:rgba(var(--inkrgb),.5); margin-bottom:8px; }
.week-headline { margin:0 0 20px; font:900 clamp(28px,6vw,54px)/0.96 Archivo,sans-serif; letter-spacing:-.035em;
                  color:var(--ink); }
.stat-band { display:flex; border-top:2px solid rgba(var(--inkrgb),.4); border-bottom:2px solid rgba(var(--inkrgb),.4);
             flex-wrap:wrap; }
.stat-col { flex:1 1 140px; padding:14px 18px; border-right:1px solid rgba(var(--inkrgb),.2); }
.stat-col:last-child { border-right:0; }
.stat-num { font:900 28px Archivo,sans-serif; color:var(--ink); font-variant-numeric:tabular-nums; }
.stat-num.accent { color:var(--acc); }
.stat-label { font:600 10px Archivo,sans-serif; letter-spacing:.12em; text-transform:uppercase;
              color:rgba(var(--inkrgb),.55); }
.week-split { display:grid; grid-template-columns:1.4fr 1fr; gap:0; padding-top:24px; }
@media (max-width:800px) { .week-split { grid-template-columns:1fr; } }
.week-lead-col { padding-right:32px; border-right:1px solid rgba(var(--inkrgb),.25); }
@media (max-width:800px) { .week-lead-col { padding-right:0; border-right:0; padding-bottom:28px; } }
.week-rest-col { padding-left:32px; }
@media (max-width:800px) { .week-rest-col { padding-left:0; } }
.week-lead-kicker { display:flex; align-items:baseline; gap:10px; margin-bottom:10px; }
.week-lead-kicker .rank-num { font:900 22px Archivo,sans-serif; color:var(--acc); }
.week-lead-kicker .kicker { font-size:10px; letter-spacing:.14em; }
.week-lead-title { margin:0 0 12px; font:900 34px/1.02 Archivo,sans-serif; letter-spacing:-.03em; color:var(--ink);
                    text-decoration:none; display:block; }
.week-lead-dek { margin:0 0 10px; font:400 16px/1.5 Archivo,sans-serif; color:var(--ink2); }
.week-lead-byline { font:600 11px Archivo,sans-serif; letter-spacing:.1em; text-transform:uppercase;
                     color:rgba(var(--inkrgb),.55); margin-bottom:22px; }
.week-sec-title { margin:0 0 8px; font:800 24px/1.1 Archivo,sans-serif; letter-spacing:-.022em; color:var(--ink);
                   text-decoration:none; display:block; }
.week-sec-dek { margin:0; font:400 14px/1.5 Archivo,sans-serif; color:var(--muted); }
.week-rest-h { font:900 11px Archivo,sans-serif; letter-spacing:.16em; text-transform:uppercase; color:var(--ink);
               margin-bottom:8px; }
.week-rest-row { display:grid; grid-template-columns:22px 1fr; gap:10px; padding:9px 0;
                  border-top:1px solid rgba(var(--inkrgb),.16); text-decoration:none; align-items:baseline; }
.week-rest-row:last-child { border-bottom:1px solid rgba(var(--inkrgb),.16); }
.week-rest-num { font:600 11px Archivo,sans-serif; color:rgba(var(--inkrgb),.4); font-variant-numeric:tabular-nums; }
.week-rest-title { font:600 14px/1.3 Archivo,sans-serif; color:var(--ink); }
"""

_MACROS = """
{% macro theme_picker() -%}
<div class="theme-picker">
  {% for p in palettes %}
  <button type="button" class="theme-swatch" data-theme-btn="{{ loop.index0 }}"
          aria-pressed="{{ 'true' if loop.index0 == default_theme else 'false' }}"
          onclick="__aiDigestSetTheme({{ loop.index0 }})" title="{{ p.name }}">
    <span style="background:{{ p.g }}"></span><span style="background:{{ p.acc }}"></span><span style="background:{{ p.bar }}"></span>
  </button>
  {% endfor %}
</div>
{%- endmacro %}

{% macro masthead(period_meta, total_records, nav_links, archive_link, search_href, show_search=true) -%}
<header class="masthead">
  <div class="masthead-row1">
    <div class="masthead-id">
      <a class="wordmark" href="{{ archive_link.home_href }}">AI Digest</a>
      <span class="period-meta">{{ period_meta }}</span>
    </div>
    <div class="masthead-tools">
      {% if show_search %}
      <form class="search-form" action="{{ search_href }}" method="get">
        <div class="search-field">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(var(--grgb),.6)" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>
          <input type="search" name="q" placeholder="Search by keyword — title, summary, source">
        </div>
      </form>
      <span class="records-chip">{{ total_records }} records</span>
      {% endif %}
      {{ theme_picker() }}
    </div>
  </div>
  <nav class="nav">
    {% for link in nav_links %}
    <a href="{{ link.href }}" class="{{ 'active' if link.active else '' }}">
      <span class="tab-label">{{ link.label }}</span><span class="tab-count">{{ link.count }}</span>
    </a>
    {% endfor %}
    <a href="{{ archive_link.href }}" class="archive-link">
      <span class="tab-label">Archive</span><span class="tab-count">{{ archive_link.count }}</span>
    </a>
  </nav>
</header>
{%- endmacro %}

{% macro site_footer(archive_href, total, status='ok') -%}
<footer class="site-footer">
  <span class="term-line">digest --items {{ total }} --status {{ status }}</span>
  <nav><a href="{{ archive_href }}">Archive index</a></nav>
</footer>
{%- endmacro %}
"""

_HOME_TMPL = """
{% import "macros.html" as m %}
<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + _THEME_JS + _FONTS + """
<title>AI Digest — {{ period_meta }}</title>
<style>""" + _root_vars_css(PALETTES[DEFAULT_THEME]) + _BASE_CSS + _HOME_CSS + """</style>
</head><body>
<div class="wrap">
{{ m.masthead(period_meta, total_records, nav_links, archive_link, search_href, true) }}
<div class="body-grid">
<div class="main-col">

{% if lead %}
<div class="kicker-row">
  <span class="kicker">Lead story</span><span class="kicker-sub">Highest significance of the {{ period_word }}</span>
</div>
<div class="lead-grid">
  <div class="lead-num">01</div>
  <div>
    <div class="tag-row">
      <span class="tag tag-ink">{{ labels[lead.category]|upper }}</span>
      {% if lead.is_major %}<span class="tag tag-acc">MAJOR · {{ '%.2f'|format(lead.significance) }}</span>{% endif %}
    </div>
    <a class="lead-title" href="{{ lead.url }}" title="{{ lead.title }}">{{ lead.display_title }}</a>
    <p class="lead-dek">{{ lead.summary }}</p>
    <div class="byline-row">
      <a class="byline-link" href="{{ lead.url }}">{{ lead.domain_path }} →</a>
      <span class="byline-source">{{ lead.source_name }}</span>
    </div>
  </div>
</div>
{% else %}
<p class="empty-note">오늘은 새 항목이 없습니다.</p>
{% endif %}

{% if grid3 %}
<div class="hr2"></div>
<div class="grid3">
  {% for it in grid3 %}
  <div class="grid3-col">
    <div class="rank-row"><span class="rank-num">{{ '%02d'|format(it.rank) }}</span>
      <span class="rank-cat {{ 'is-lead-cat' if loop.index == 1 else '' }}">{{ labels[it.category] }}</span></div>
    <a class="item-h3" href="{{ it.url }}" title="{{ it.title }}">{{ it.display_title }}</a>
    <p class="item-dek">{{ it.summary }}</p>
    <a class="item-link" href="{{ it.url }}">{{ it.domain_path }} →</a>
    <div class="item-source">{{ it.source_name }}</div>
  </div>
  {% endfor %}
</div>
{% endif %}

{% if worth or brief %}
<div class="hr2"></div>
<div class="split2">
  <div>
    <div class="split2-h">Worth knowing</div>
    {% for it in worth %}
    <div class="wk-row">
      <span class="wk-num">{{ '%02d'|format(it.rank) }}</span>
      <div>
        <div class="wk-cat">{{ labels[it.category] }}</div>
        <a class="wk-title" href="{{ it.url }}" title="{{ it.title }}">{{ it.display_title }}</a>
        <div class="wk-dek">{{ it.summary }}</div>
        <a class="wk-link" href="{{ it.url }}">{{ it.domain_path }} →</a>
      </div>
    </div>
    {% endfor %}
  </div>
  <div>
    <div class="split2-h dim">In brief{% if brief %} — {{ brief|length }} more{% endif %}</div>
    {% for it in brief %}
    <a class="brief-row" href="{{ it.url }}">
      <span class="brief-num">{{ '%02d'|format(it.rank) }}</span>
      <div><span class="brief-title" title="{{ it.title }}">{{ it.display_title }}</span><span class="brief-link">{{ it.domain_path }} →</span></div>
      <span class="brief-cat">{{ short_labels[it.category] }}</span>
    </a>
    {% endfor %}
  </div>
</div>
{% endif %}

</div>
<aside class="aside">
  <div class="aside-h">Signal index</div>
  <div class="aside-sub">All {{ total }} stories by significance band. 0.60 and up is major.</div>
  <div>
    {% for b in bands %}
    <div class="band-row">
      <div class="band-top">
        <span class="band-score">{{ b.score }} <span class="band-tier">{{ b.tier }}</span></span>
        <span class="band-count">{{ b.count }}</span>
      </div>
      <div class="band-bar" style="background:{{ b.color }};width:{{ b.pct }}%"></div>
    </div>
    {% endfor %}
  </div>
  {% if warnings %}
  <div class="source-alert">
    <div class="source-alert-h">Source alert</div>
    <div class="source-alert-body">No working feed for <b>{{ warnings|join(', ') }}</b> — 0 items collected.</div>
  </div>
  {% endif %}
</aside>
</div>
</div>
{{ m.site_footer(archive_link.href, total) }}
</body></html>
"""

_CATEGORY_TMPL = """
{% import "macros.html" as m %}
<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + _THEME_JS + _FONTS + """
<title>AI Digest — {{ labels[category] }} — {{ period_meta }}</title>
<style>""" + _root_vars_css(PALETTES[DEFAULT_THEME]) + _BASE_CSS + _CATEGORY_CSS + """</style>
</head><body>
<div class="wrap">
{{ m.masthead(period_meta, total_records, nav_links, archive_link, search_href, true) }}
<div class="cat-body">
<div class="cat-top">
  <div>
    <h1 class="cat-title">{{ labels[category] }}</h1>
    <p class="cat-dek">{{ one_liner }}</p>
  </div>
  <div class="pill-row">
    <span class="pill active">All {{ items|length }}</span>
    {% if major_count %}<span class="pill">Major {{ major_count }}</span>{% endif %}
    {% if top_source %}<span class="pill">{{ top_source.name }} {{ top_source.count }}</span>{% endif %}
  </div>
</div>
<div class="hr2" style="margin:0"></div>

{% if not items %}
<p class="empty-note">{{ period_word|capitalize }}엔 해당 카테고리 항목이 없습니다.</p>
{% endif %}
{% for it in items %}
<a class="cat-row" href="{{ it.url }}">
  <span class="cat-score" style="font-size:{{ it.row_size }}px">{{ '%.2f'|format(it.significance)|replace('0.', '.') }}</span>
  <div>
    <div class="cat-row-title" style="font-size:{{ it.row_size }}px" title="{{ it.title }}">{{ it.display_title }}</div>
    {% if it.show_dek %}<div class="cat-row-dek">{{ it.summary }}</div>{% endif %}
    <span class="cat-row-link">{{ it.domain_path }} →</span>
  </div>
  <div class="cat-row-side">
    {% if it.is_major %}<span class="tag tag-acc">MAJOR</span>{% endif %}
    <div class="cat-row-side-source">{{ it.source_name }}{% if not it.is_major %} · {{ it.tier_label }}{% endif %}</div>
  </div>
</a>
{% endfor %}

<div class="cat-footer">
  <span class="cat-footer-note">{{ items|length }} of {{ items|length }} shown · category cap {{ cap }} · min significance {{ min_sig }}</span>
  <a class="cat-footer-link" href="{{ archive_link.href }}">{{ labels[category] }} in earlier weeks →</a>
</div>
</div>
</div>
{{ m.site_footer(archive_link.href, items|length) }}
</body></html>
"""

_SEARCH_TMPL = """
{% import "macros.html" as m %}
<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + _THEME_JS + _FONTS + """
<title>AI Digest — Search</title>
<style>""" + _root_vars_css(PALETTES[DEFAULT_THEME]) + _BASE_CSS + _SEARCH_CSS + """</style>
</head><body>
<div class="wrap search-page-body">
<header class="search-hero">
  <div class="search-hero-row">
    <a class="wordmark" href="index.html">AI Digest</a>
    <form class="search-form" style="flex:1;max-width:340px" action="search.html" method="get">
      <div class="search-field">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--acclt)" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>
        <input id="q" type="search" placeholder="Search…" autofocus>
        <span id="hitcount"></span>
      </div>
    </form>
    {{ m.theme_picker() }}
  </div>
  <nav class="nav" style="border-top:1px solid rgba(var(--grgb),.18)">
    <a href="index.html"><span class="tab-label">Home</span></a>
  </nav>
</header>
<div class="results-body">
  <div class="results-meta" id="meta">{{ total }}건의 기록에서 검색 (제목·요약·소스)</div>
  <div class="results-hr"></div>
  <div id="results"></div>
</div>
</div>
<script id="search-data" type="application/json">{{ data_json|safe }}</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById('search-data').textContent);
  var input = document.getElementById('q');
  var results = document.getElementById('results');
  var meta = document.getElementById('meta');
  var hitcount = document.getElementById('hitcount');

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function highlight(text, q) {
    var idx = text.toLowerCase().indexOf(q);
    if (idx === -1) return esc(text);
    return esc(text.slice(0, idx)) + '<mark>' + esc(text.slice(idx, idx + q.length)) + '</mark>'
      + esc(text.slice(idx + q.length));
  }
  function render(raw) {
    var q = raw.trim().toLowerCase();
    if (!q) {
      hitcount.textContent = '';
      meta.textContent = '{{ total }}건의 기록에서 검색 (제목·요약·소스)';
      results.innerHTML = '';
      return;
    }
    var matches = DATA.filter(function (it) {
      return it.t.toLowerCase().indexOf(q) !== -1
        || it.sm.toLowerCase().indexOf(q) !== -1
        || it.s.toLowerCase().indexOf(q) !== -1;
    });
    matches.sort(function (a, b) { return b.sig - a.sig; });
    hitcount.textContent = matches.length + ' hits';
    meta.textContent = matches.length + ' results for "' + raw.trim() + '" · searched {{ total }} records';
    if (!matches.length) {
      results.innerHTML = '<p class="empty">결과 없음</p>';
      return;
    }
    results.innerHTML = matches.slice(0, 100).map(function (it, idx) {
      var topCls = idx === 0 ? ' top-hit' : '';
      return '<a class="result-row' + topCls + '" href="' + esc(it.u) + '">'
        + '<span class="result-score">' + it.sig.toFixed(2).replace(/^0\\./, '.') + '</span>'
        + '<div><div class="result-title">' + highlight(it.t, q) + '</div>'
        + '<div class="result-byline">' + esc(it.d) + ' · ' + esc(it.s) + '</div></div>'
        + '</a>';
    }).join('');
  }
  input.addEventListener('input', function () { render(input.value); });
  var initial = new URLSearchParams(location.search).get('q') || '';
  input.value = initial;
  render(initial);
})();
</script>
</body></html>
"""

_ARCHIVE_INDEX_TMPL = """
{% import "macros.html" as m %}
<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + _THEME_JS + _FONTS + """
<title>AI Digest — Archive</title>
<style>""" + _root_vars_css(PALETTES[DEFAULT_THEME]) + _BASE_CSS + _ARCHIVE_INDEX_CSS + """</style>
</head><body>
<div class="wrap">
<header class="simple-header">
  <div class="simple-header-id">
    <a class="wordmark" href="../index.html">AI Digest</a>
    <span class="simple-header-sub">Archive</span>
  </div>
  <div style="display:flex;align-items:center;gap:18px">
    {{ m.theme_picker() }}
    <a href="../index.html" class="accent" style="font:700 11px Archivo,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--acc);text-decoration:none">Latest →</a>
  </div>
</header>
<div class="archive-body">
<div class="archive-top">
  <h1 class="archive-title">{{ digests|length }} weeks<br>of signal</h1>
  <div class="archive-bars-label">Items per digest, oldest → newest</div>
  <div class="archive-bars">
    {% for b in bars %}<span style="height:{{ b.pct }}%;background:{{ b.color }}"></span>{% endfor %}
  </div>
</div>
<div class="archive-table-head"><span>Digest</span><span>Volume</span><span>Top story</span><span>Items</span></div>
{% for d in recent %}
<a class="archive-row {{ 'latest' if loop.index == 1 else '' }}" href="{{ d.date }}.html">
  <span class="archive-row-date">{{ d.date }}</span>
  <span class="archive-row-bar" style="width:{{ d.bar_px }}px;background:{{ d.bar_color }}"></span>
  <span class="archive-row-top">{{ d.top_title or '—' }}</span>
  <span class="archive-row-count">{{ d.item_count }}</span>
</a>
{% endfor %}
{% if more_count %}<div class="archive-more">+ {{ more_count }} earlier digests</div>{% endif %}
</div>
</div>
{{ m.site_footer('index.html', digests|length, status='archive') }}
</body></html>
"""

_ARCHIVE_WEEK_TMPL = """
{% import "macros.html" as m %}
<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + _THEME_JS + _FONTS + """
<title>AI Digest — {{ label }}</title>
<style>""" + _root_vars_css(PALETTES[DEFAULT_THEME]) + _BASE_CSS + _ARCHIVE_WEEK_CSS + """</style>
</head><body>
<div class="wrap">
<header class="simple-header">
  <div class="simple-header-id">
    <a class="wordmark" href="../index.html">AI Digest</a>
    <span class="simple-header-sub">Archive · {{ label }}</span>
  </div>
  <nav>
    {% if prev_label %}<a href="{{ prev_label }}.html">← {{ prev_label }}</a>{% endif %}
    {{ m.theme_picker() }}
    <a class="accent" href="index.html">All weeks</a>
  </nav>
</header>
<div class="week-body">
  <div class="week-eyebrow">{{ period_meta }} · archived digest</div>
  <h1 class="week-headline">{{ headline }}</h1>
  <div class="stat-band">
    <div class="stat-col"><div class="stat-num">{{ total }}</div><div class="stat-label">stories kept</div></div>
    <div class="stat-col"><div class="stat-num accent">{{ '%.2f'|format(peak_sig) }}</div><div class="stat-label">peak significance</div></div>
    <div class="stat-col"><div class="stat-num">{{ model_release_count }}</div><div class="stat-label">model releases</div></div>
    <div class="stat-col"><div class="stat-num">{{ dollar_committed or '—' }}</div><div class="stat-label">committed (approx.)</div></div>
  </div>
  {% if lead %}
  <div class="week-split">
    <div class="week-lead-col">
      <div class="week-lead-kicker"><span class="rank-num">01</span><span class="kicker">{{ labels[lead.category] }}{{ ' · major' if lead.is_major else '' }}</span></div>
      <a class="week-lead-title" href="{{ lead.url }}" title="{{ lead.title }}">{{ lead.display_title }}</a>
      <p class="week-lead-dek">{{ lead.summary }}</p>
      <div class="week-lead-byline">{{ lead.source_name }} · tier {{ lead.tier_label }}</div>
      {% if second %}
      <div class="hr2" style="margin:0 0 18px"></div>
      <div class="week-lead-kicker"><span class="rank-num" style="font-size:17px;color:rgba(var(--inkrgb),.4)">02</span><span class="kicker" style="color:rgba(var(--inkrgb),.5)">{{ labels[second.category] }}{{ ' · major' if second.is_major else '' }}</span></div>
      <a class="week-sec-title" href="{{ second.url }}" title="{{ second.title }}">{{ second.display_title }}</a>
      <p class="week-sec-dek">{{ second.summary }}</p>
      {% endif %}
    </div>
    <div class="week-rest-col">
      <div class="week-rest-h">Rest of the {{ period_word }}</div>
      {% for it in rest %}
      <a class="week-rest-row" href="{{ it.url }}" title="{{ it.title }}"><span class="week-rest-num">{{ '%02d'|format(it.rank) }}</span><span class="week-rest-title">{{ it.display_title }}</span></a>
      {% endfor %}
    </div>
  </div>
  {% else %}
  <p class="empty-note">이 기간엔 저장된 항목이 없습니다.</p>
  {% endif %}
</div>
</div>
{{ m.site_footer('index.html', total, status='archive') }}
</body></html>
"""

_env = Environment(loader=DictLoader({
    "macros.html": _MACROS,
    "home.html": _HOME_TMPL,
    "category.html": _CATEGORY_TMPL,
    "search.html": _SEARCH_TMPL,
    "archive_index.html": _ARCHIVE_INDEX_TMPL,
    "archive_week.html": _ARCHIVE_WEEK_TMPL,
}), autoescape=True)
_env.globals.update(palettes=PALETTES, default_theme=DEFAULT_THEME, labels=CATEGORY_LABELS)

_SHORT_LABELS = {
    "model_releases": "Model", "research": "Research", "tools_products": "Tools",
    "policy_business": "Policy", "community_takes": "Community",
}

_DOMAIN_RE = re.compile(r"^https?://(?:www\.)?([^/]+)(/.*)?$")


def _domain_path(url: str, max_len: int = 42) -> str:
    m = _DOMAIN_RE.match(url or "")
    if not m:
        return url or ""
    text = (m.group(1) or "") + (m.group(2) or "")
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def _tier(sig: float) -> str:
    if sig >= 0.6:
        return "major"
    if sig >= 0.4:
        return "high"
    if sig >= 0.3:
        return "mid"
    return "low"


def _source_line_name(it: dict) -> str:
    """멀티소스 클러스터면 '(+N more)' 를 붙인 표기.

    원본 이름을 `_source_base` 에 따로 보존한다. 같은 dict 이 홈과 카테고리 페이지에서 각각
    _annotate 되는데, 예전엔 접미사가 붙은 source_name 을 다시 입력으로 써서
    'TechCrunch (+1 more) (+2 more)' 처럼 누적됐다(접미사 붙은 이름은 cluster_sources 의
    어떤 값과도 안 맞아서 자기 자신까지 others 에 세어지는 바람에 숫자도 커졌음)."""
    base = it.setdefault("_source_base", it["source_name"])
    others = [s for s in it.get("cluster_sources", []) if s != base]
    return f"{base} (+{len(others)} more)" if others else base


def _annotate(it: dict, rank: int | None = None) -> None:
    it["domain_path"] = _domain_path(it["url"])
    it["tier_label"] = _tier(it.get("significance", 0.0))
    it["source_name"] = _source_line_name(it)
    # 표시용 제목은 headline 우선, 없으면 원제목. 한 군데서만 정하고 템플릿은 이것만 쓴다
    # (아카이브 415건은 headline 이 비어 있어서 그대로 원제목으로 나간다).
    it["display_title"] = (it.get("headline") or "").strip() or it["title"]
    if rank is not None:
        it["rank"] = rank


def _flatten_ranked(groups: list[tuple[str, list[dict]]]) -> list[dict]:
    # 동점(significance 같음)일 때는 최신 발행이 앞. 이 tiebreak 이 없으면 stable sort 때문에
    # CATEGORY_ORDER 열거 순서가 리드 스토리를 결정해버림(model_releases 가 항상 이김).
    flat = [it for _cat, items in groups for it in items]
    flat.sort(key=lambda it: (it["significance"], it.get("published") or ""), reverse=True)
    return flat


def _period_meta(label: str, total: int) -> tuple[str, str]:
    """(메타 텍스트, '주'/'일' 같은 기간 단어) 반환."""
    m = re.match(r"^(\d{4})-W(\d{2})$", label)
    if m:
        year, week = int(m.group(1)), int(m.group(2))
        monday = _date.fromisocalendar(year, week, 1)
        sunday = monday + _timedelta(days=6)
        if monday.month == sunday.month:
            rng = f"{monday.day}–{sunday.day} {sunday.strftime('%B %Y')}"
        else:
            rng = f"{monday.strftime('%d %b')} – {sunday.strftime('%d %b %Y')}"
        return f"Week {week} · {rng} · {total} stories", "week"
    try:
        d = _date.fromisoformat(label)
        return f"{d.strftime('%A')} · {d.day} {d.strftime('%B %Y')} · {total} stories", "day"
    except ValueError:
        return f"{label} · {total} stories", "period"


def _nav_links(groups: list[tuple[str, list[dict]]], active_key: str, home_href: str,
              category_href_fn) -> list[dict]:
    total = sum(len(items) for _c, items in groups)
    links = [{"key": "home", "label": "Home", "count": total, "href": home_href, "active": active_key == "home"}]
    for cat, items in groups:
        links.append({
            "key": cat, "label": CATEGORY_LABELS[cat], "count": len(items),
            "href": category_href_fn(cat), "active": active_key == cat,
        })
    return links


_BAND_DEFS = [(0.6, "major", "acc"), (0.5, "high", "ink"), (0.4, "high", "muted"), (0.3, "mid", "n2")]


def _signal_bands(flat: list[dict]) -> list[dict]:
    counts = []
    for lo, tier, color_key in _BAND_DEFS:
        n = sum(1 for it in flat if lo <= it["significance"] < lo + 0.1)
        counts.append((lo, tier, color_key, n))
    max_n = max((n for *_r, n in counts), default=1) or 1
    return [
        {"score": f"{lo:.2f}", "tier": tier, "count": n, "pct": max(4, round(n / max_n * 100)),
         "color": f"var(--{color_key})"}
        for lo, tier, color_key, n in counts
    ]


def render_digest(date: str, groups: list[tuple[str, list[dict]]],
                  warnings: list[str], output_dir: Path, total_records: int = 0) -> Path:
    """오늘자 다이제스트: index.html(루트) + archive/{date}.html 동일 내용, 상대경로만 다르게.

    majors 파라미터는 2026-07-29 에 제거 — SIGNAL 디자인의 '상단 major 배너'용이었는데
    07-27 Modernist 개편에서 significance 플랫 랭킹으로 바뀌며 배너가 없어졌고, 이후로는
    받기만 하고 쓰지 않았음. major 표시는 지금도 항목별 `it.is_major` 태그로 나감."""
    flat = _flatten_ranked(groups)
    total = len(flat)
    for i, it in enumerate(flat, start=1):
        _annotate(it, rank=i)
    period_meta_txt, period_word = _period_meta(date, total)
    bands = _signal_bands(flat)

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(exist_ok=True)

    tmpl = _env.get_template("home.html")
    for in_archive, out_path in ((False, output_dir / "index.html"), (True, archive_dir / f"{date}.html")):
        # 오늘자 카테고리 페이지는 항상 루트에만 생성되므로(render_category_page 호출부 참고),
        # 아카이브 사본에서도 카테고리/홈 링크는 루트를 가리켜야 함(../ 접두).
        prefix = "../" if in_archive else ""
        home_href = f"{prefix}index.html"
        cat_href_fn = lambda c, p=prefix: f"{p}{c}.html"  # noqa: E731
        nav_links = _nav_links(groups, "home", home_href, cat_href_fn)
        archive_link = {
            "href": "index.html" if in_archive else "archive/index.html",
            "home_href": home_href,
            "count": total_records,
        }
        html = tmpl.render(
            period_meta=period_meta_txt, period_word=period_word, total_records=total_records,
            total=total, nav_links=nav_links, archive_link=archive_link,
            search_href=("../search.html" if in_archive else "search.html"),
            lead=flat[0] if flat else None, grid3=flat[1:4], worth=flat[4:8], brief=flat[8:],
            short_labels=_SHORT_LABELS, bands=bands, warnings=warnings,
        )
        out_path.write_text(html, encoding="utf-8")
    return archive_dir / f"{date}.html"


def render_archive_digest(label: str, groups: list[tuple[str, list[dict]]],
                          output_dir: Path, recap: dict | None = None, total_records: int = 0) -> Path:
    """백필/재렌더용 주간 리캡 페이지: archive/{label}.html (1f 디자인 — 헤드라인+통계밴드)."""
    flat = _flatten_ranked(groups)
    total = len(flat)
    for i, it in enumerate(flat, start=1):
        _annotate(it, rank=i)
    period_meta_txt, period_word = _period_meta(label, total)
    recap = recap or {}
    headline = recap.get("headline") or f"{period_meta_txt.split(' · ')[0]} digest"
    peak_sig = max((it["significance"] for it in flat), default=0.0)
    model_release_count = sum(1 for it in flat if it["category"] == "model_releases")

    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    tmpl = _env.get_template("archive_week.html")
    html = tmpl.render(
        label=label, period_meta=period_meta_txt, period_word=period_word, headline=headline,
        total=total, peak_sig=peak_sig, model_release_count=model_release_count,
        dollar_committed=recap.get("dollar_committed"),
        lead=flat[0] if flat else None, second=flat[1] if len(flat) > 1 else None, rest=flat[2:],
        prev_label=None,
    )
    (archive_dir / f"{label}.html").write_text(html, encoding="utf-8")
    return archive_dir / f"{label}.html"


def render_category_page(period_label: str, category: str, groups: list[tuple[str, list[dict]]],
                         output_dir: Path, in_archive: bool, one_liner: str = "",
                         cap: int = 6, min_sig: float = 0.25, total_records: int = 0) -> Path:
    """카테고리 필터 뷰: 오늘은 {category}.html(루트), 과거 주는 archive/{label}-{category}.html."""
    items = next((its for c, its in groups if c == category), [])
    # 동점 처리는 group_by_category/_flatten_ranked 와 같은 키로 — 안 맞추면 홈과 카테고리
    # 페이지의 같은 점수 항목 순서가 갈린다.
    items = sorted(items, key=lambda it: (it["significance"], it.get("published") or ""), reverse=True)
    row_sizes = [34, 28, 22, 17, 15, 15]
    for i, it in enumerate(items):
        _annotate(it)
        it["row_size"] = row_sizes[i] if i < len(row_sizes) else row_sizes[-1]
        it["show_dek"] = i < 2

    total = sum(len(its) for _c, its in groups)
    period_meta_txt, period_word = _period_meta(period_label, total)
    major_count = sum(1 for it in items if it["is_major"])
    source_counts: dict[str, int] = {}
    for it in items:
        source_counts[it["source_name"]] = source_counts.get(it["source_name"], 0) + 1
    top_source = None
    if source_counts:
        name, cnt = max(source_counts.items(), key=lambda kv: kv[1])
        top_source = {"name": name, "count": cnt}

    home_href = (f"{period_label}.html" if in_archive else "index.html")
    cat_href_fn = (lambda c: f"{period_label}-{c}.html") if in_archive else (lambda c: f"{c}.html")
    nav_links = _nav_links(groups, category, home_href, cat_href_fn)
    archive_link = {
        "href": ("index.html" if in_archive else "archive/index.html"),
        "home_href": ("../index.html" if in_archive else "index.html"),
        "count": total_records,
    }

    if in_archive:
        out_path = output_dir / "archive" / f"{period_label}-{category}.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        search_href = "../search.html"
        archive_link["href"] = "index.html"
    else:
        out_path = output_dir / f"{category}.html"
        output_dir.mkdir(parents=True, exist_ok=True)
        search_href = "search.html"

    tmpl = _env.get_template("category.html")
    html = tmpl.render(
        category=category, one_liner=one_liner or f"{CATEGORY_LABELS[category]} this {period_word}.",
        items=items, major_count=major_count, top_source=top_source, cap=cap, min_sig=min_sig,
        period_meta=period_meta_txt, period_word=period_word, total_records=total_records,
        nav_links=nav_links, archive_link=archive_link, search_href=search_href,
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_search_page(items: list[dict], output_dir: Path):
    """전체 히스토리 검색 페이지(search.html). fetch() 는 file:// 로컬 실행 시 CORS 로 막히므로
    전체 인덱스를 <script type="application/json"> 로 인라인 임베드 — 로컬/호스팅 둘 다 동작."""
    data = [
        {
            "t": it["title"],
            "u": it["url"],
            "s": it.get("source_name", it.get("source_id", "")),
            "d": it.get("digest_date", ""),
            "sig": round(it.get("significance", 0.0), 2),
            "sm": (it.get("summary") or "")[:200],
        }
        for it in items
    ]
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    tmpl = _env.get_template("search.html")
    html = tmpl.render(total=len(data), data_json=data_json)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "search.html").write_text(html, encoding="utf-8")


def render_archive_index(digests: list[dict], output_dir: Path):
    # 볼륨 미니바는 시간순이어야 하는데 date 를 텍스트 정렬하면 주간 라벨('2026-W31')이
    # 'W'(0x57) > '0'(0x30) 때문에 모든 일간 날짜보다 뒤로 가서, 막대 순서도 틀리고
    # 마지막 원소를 '최신'으로 강조하는 것도 엉뚱한 걸 집는다. store 와 같은 키를 쓴다.
    ordered_asc = sorted(digests, key=lambda d: label_sort_key(d["date"]))
    max_count = max((d["item_count"] for d in digests), default=1) or 1
    bars = []
    for i, d in enumerate(ordered_asc):
        pct = max(6, round(d["item_count"] / max_count * 100))
        is_latest = i == len(ordered_asc) - 1
        color = "var(--acc)" if is_latest else ("var(--ink)" if pct >= 70 else
                ("var(--muted)" if pct >= 40 else "var(--n1)"))
        bars.append({"pct": pct, "color": color})

    recent = digests[:6]
    for i, d in enumerate(recent):
        d["bar_px"] = max(6, round(d["item_count"] / max_count * 68))
        d["bar_color"] = "var(--acc)" if i == 0 else "var(--muted)"
    more_count = max(0, len(digests) - len(recent))

    tmpl = _env.get_template("archive_index.html")
    html = tmpl.render(digests=digests, bars=bars, recent=recent, more_count=more_count)
    (output_dir / "archive").mkdir(parents=True, exist_ok=True)
    (output_dir / "archive" / "index.html").write_text(html, encoding="utf-8")
