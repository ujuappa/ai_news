# CLAUDE.md — AI News Digest

Claude Code 는 세션 시작 시 이 파일을 자동으로 읽음.
**전체 결정·TODO·변경로그는 `PROJECT_MEMO.md` 참조 (작업 시작 전 먼저 읽을 것).**

## 프로젝트
매일 AI 뉴스를 자동 수집 → 중복제거 → 분류 → 요약 → 랭킹해서 정적 웹페이지로 굽는
개인용 데일리 다이제스트.
파이프라인: `fetch.py` → `dedup.py` → `llm.py` → `store.py`(SQLite) → `render.py`,
오케스트레이터 `pipeline.py`, 설정 `sources.yaml` + `topics.json` + `sources.custom.json`
(뒤 둘은 **기계 소유** — 아래 "소스·토픽 편집" 참고). `backfill.py` 는 1회성 과거 데이터 백필용
(2026-07-27 에 6개월치 실행 완료 — 재실행은 보통 불필요, PROJECT_MEMO 참고).
`rerender.py` 는 DB 데이터로 전체 페이지를 API 비용 없이 재생성(디자인만 바꿨을 때 사용).
**디자인 변경 배포 순서(2026-08-06부터)**: 템플릿/CSS 고침 → `python rerender.py` → `output/` 까지
같이 커밋 → main 에 push. push 트리거가 파이프라인을 건너뛰고 커밋된 `output/` 만 Pages 에 올린다
(API 비용 0). **`rerender.py` 를 빼먹으면 예전 지면이 그대로 재배포된다** — 빌드는 렌더를 안 한다.
`generate_recaps.py` 는 recap(주간 헤드라인/$ 집계/카테고리 요약) 소급 생성용, 아직 미실행.
`linkcheck.py` 는 이미 게시된 링크의 link rot 점검(→ `items.link_status`, 죽은 링크는 렌더에서
href 가 떨어짐). 판정 기준과 "무엇을 죽었다고 부르지 않는지"는 PROJECT_MEMO 2026-08-04 참고.

## 소스·토픽 편집 + 저장/팔로우 (2026-08-11 신설)

지면 3개가 늘었다: `sources.html`(소스 디렉터리, **읽기 전용**) · `admin.html`(소스·토픽 CRUD) ·
`saved.html`(저장한 기사 · 팔로우한 토픽 · 저장한 필터).

**admin 은 브라우저에서 GitHub Contents API 로 직접 커밋한다**(사용자 결정 — 로컬 admin 서버가
아니라 이 경로). 산출물에 **비밀값이 하나도 없다**: fine-grained PAT 을 사용자가 런타임에 넣고
그 브라우저 localStorage 에만 남는다. 권장 권한은 이 레포 하나 + Contents:RW
(Actions:RW 는 "Run pipeline now" 에만 필요, 없으면 그 버튼만 비활성).
`tests/test_admin.py` 가 산출물에 토큰 모양 문자열이 없는지 검사한다 — **거기에 토큰을 굽지 말 것.**

- **`sources.yaml` 은 admin 이 절대 쓰지 않는다.** 주석 240줄이 결정 근거인데 클라이언트가 YAML 을
 다시 뱉으면 전부 사라진다 → 기계 편집은 `sources.custom.json` 오버레이에 쌓인다
 (id 로 매칭: 없는 id=추가 · 있는 id=**준 필드만** 덮어쓰기 · `deleted:true`=숨김, 되돌릴 수 있다).
 curated 소스 수정은 **diff 만** 남긴다 — 전체를 복사하면 나중에 `sources.yaml` 을 고쳐도
 오버레이가 옛 값으로 덮어써서 "원본을 고쳤는데 아무 일도 안 일어난다".
- **필터 어휘는 `topics.json`** 이다(예전 `config.TOPIC_ORDER`/`TOPIC_LABELS`/`llm._TOPIC_GLOSS`).
 `gloss` 는 화면에 안 나가고 LLM 프롬프트에만 쓰인다 — 새 토픽에는 꼭 쓸 것, 분류 품질을 정한다.
 키는 `[a-z0-9_]` 만(공백이 들어가면 `data-topics` 가 쪼개져 필터가 조용히 깨진다).
 파일이 깨지면 `config._FALLBACK_TOPICS` 로 돌아간다. **토픽을 추가해도 과거 기사엔 안 붙는다** —
 소급은 `python backfill_topics.py`(유료).
- ⚠️ **`static/admin_rules.js` 의 `applyOverlay` 는 `config._apply_overlay` 의 사본이다.**
 한쪽을 고치면 다른 쪽도 고칠 것 — `tests/test_admin.py` 가 node 로 돌려 같은 픽스처로 대조한다.
 그래서 이 파일에는 DOM/fetch/localStorage 를 넣으면 안 된다(node 에서 못 돈다).
- **저장/팔로우는 localStorage 전용**(`static/follow.js`, 키 `ai-digest-follow`). 기기 간 동기화
 없음 — 그 사실을 `saved.html` 에 적어 뒀으니 지우지 말 것. 팔로우는 **자동으로 지면을 걸러내지
 않는다**(컨트롤 줄의 `Following n` 을 눌러야 적용). 기사 자체가 아니라 그 기사의 토픽을 따라간다.
- ⚠️ **`<a>`/`<button>` 안에 `<button>` 을 넣지 말 것.** 그래서 `.brief-row` · `.cat-row` 가
 2026-08-11 에 `<a>` → `<div>` + 제목 링크로 바뀌었고, 팔로우 별은 토픽 pill 의 형제다.
 되돌리기 쉬운 변경이라 `tests/test_follow.py` 에 가드가 있다.
- **admin 에서 커밋해도 파이프라인은 다시 돌지 않는다** — push 트리거는 수집을 건너뛴다.
 새 소스는 다음 cron 이나 "Run pipeline now"(workflow_dispatch) 뒤에 걷힌다.

## 디자인 (2026-07-27 전면 개편 → 08-03 2차 → 08-06 홈 상단 재편 → 08-07 Boncom 조판)
Claude Design(claude.ai/design) 프로젝트에서 만든 "Modernist" 디자인을 DesignSync MCP 로 가져옴
(라이브 팔레트 피커, significance 플랫 랭킹).
마크업은 `templates/*.html`, 스타일은 `static/digest.css`, `render.py` 는 데이터 가공만 한다.

**2026-08-07 조판 교체**: 6a 가 그려진 Boncom 시스템을 색 말고 나머지까지 들여왔다(사용자 결정) —
**Mona Sans**(가변, `wdth` 75~125) 한 벌 + `.ph-em` 전용 Playfair Display italic, radius
16(카드)/12(컨트롤·슬롯)/999(pill), 고도는 2단 그림자. Archivo·radius 0 은 폐기됐다.
선언은 `digest.css` **맨 끝** "Boncom 시스템" 블록에 모여 있고 **거기 있어야 한다** —
`font:` 단축이 `font-variation-settings` 를 리셋해서, 축 선언이 앞서면 조용히 지워진다
(`test_the_axis_layer_comes_after_every_font_shorthand`). 축은 `wdth` 만 준다(굵기는 각
규칙의 font-weight 담당). 값 막대(signal index·아카이브 볼륨)와 stat-band 는 **일부러 각지게**
뒀다 — 막대 끝을 둥글리면 짧은 막대가 부풀어 보인다.
같은 날 **Wire 티커**(마스트헤드 아래 흐르는 줄 = 랭킹 05 이하 전부)와 지면 머리 제목의
워드마크화도 들어왔다. 그 과정에서 **필터 서랍이 계속 열려 있던 버그**를 찾아 고쳤다
(`.filter-drawer{display:grid}` 가 `[hidden]` 을 이기고 있었다 → `[hidden]` 짝 추가).

**2026-08-06 홈 상단 재편**(캔버스 "Home Top Organization" 6a): 마스트헤드가 한 줄로
(워드마크+빨간 점 · 검색 · pill 네비), 날짜가 지면 머리(`.page-head`)로 내려가고,
리드+Also today 가 한 장의 카드(`.panel`)로 묶이면서 필터가 그 카드에 붙었다.
필터는 pill 줄 → **컨트롤 줄 + 서랍 + 제거 가능한 chip, 다중선택(OR)** 으로 바뀌었고
그날 붙은 토픽 전부가 서랍에 들어간다(top-6 상한 폐지). 팔레트는 6색(`Boncom · Maroon` 추가.
08-06 에는 6a 에서 색만 들여왔지만 **08-07 에 조판까지 들여왔다** — 위 항목 참고).
**2026-08-12**: 지면 머리의 큰 "AI Digest." · 건수 stat · Daily 칩 · 랭크 라벨 · 티커 점수는
뗐다. 남는 건 날짜 칩 + Filters. 사이트명은 마스트헤드가 이미 말한다.
- **사인인 · Weekly · Monthly 는 의도적으로 없다** (로그인+쓰기 백엔드 미구현 →
 죽은 버튼 방지). **댓글은 2026-08-12 에 있다** — 다이제스트 오른쪽 레일, 이 브라우저
 localStorage 전용(서버 없음 · 공개 스레드가 아님). 6a 의 소셜 카드 3장을 붙일 자리는
 `templates/home.html` 끝 주석, 네비는 `templates/macros.html` 주석 참고.
 **단 `Following`/`Saved` 는 2026-08-11 에 실제로 구현됐다**(localStorage) — 금지어에서 빠졌고,
 대신 "그 컨트롤이 실제로 연결돼 있는지"를 검사하는 테스트가 생겼다. 위 "소스·토픽 편집" 참고.
- **필터를 건드릴 때**: 컨트롤 줄은 `.panel-body`(data-section) **밖**에 둬야 한다 — 안에 두면
  필터가 자기를 숨겨서 되돌릴 수 없게 된다(`test_topics.py` 에 회귀 가드 있음).
- **이미지는 빈 슬롯이 자리만 잡고 있다.** `static/img/<source_id>.webp` 등을 넣으면 자동 반영 —
  `static/img/README.md` 참고.
- CSS 는 **팔레트 키(`--g --ink --acc --n1 --n2 …`)만** 쓸 수 있다. 캔버스의 `--color-*` 를
  들여오면 `tests/test_render_assets.py` 가 잡는다(매핑표는 digest.css 헤더 주석).
  조판/radius/그림자는 팔레트가 아니라 전역이라 **var 가 아니라 리터럴**로 쓴다 — 그래서
  팔레트를 바꿔도 조판은 안 바뀐다.
- **`display` 를 주는 규칙에는 `[hidden]` 짝을 같이 둘 것.** 저작자 규칙이 브라우저 기본
  `[hidden]{display:none}` 을 이겨서, 토글이 조용히 죽는다(2026-08-07 필터 서랍 실제 사례).

자세한 내용은 PROJECT_MEMO 변경로그 2026-08-03 · 2026-08-06 항목 참고.

## 실행
```bash
# Python 3.12 필요 (CI 도 3.12). 3.9 는 fromisoformat 이 엄격해서 일부 날짜 형식을
# 조용히 버림 → backfill 은 아이템 드롭/오분류. 백필·재백필은 반드시 3.12 에서.
python3.12 -m venv .venv && source .venv/bin/activate && python -V
pip install -r requirements.txt          # torch 포함(무거움). 가벼운 경로는 README '확장 포인트'
echo "GEMINI_API_KEY=..." > .env         # 개인 키 (aistudio.google.com). .env 는 .gitignore 처리, 채팅에 붙여넣지 말 것
python pipeline.py --dry-run             # LLM 없이 수집/dedup (DB 미변경)
python pipeline.py                       # 전체
python pipeline.py --reset               # seen + item_emb 비움 (items/digests/recaps 보존)
python pipeline.py --purge-all           # digest.db 통째 삭제. 재백필 전 선행 (--yes 로 확인 생략)
python linkcheck.py --dry-run            # 게시된 링크 점검(리포트만). 반영은 --dry-run 빼고 → rerender.py
python backfill_topics.py                # topics.json 에 토픽 추가 후 과거 기사에 소급(Gemini = 유료)
open output/index.html
```

⚠️ **`--dry-run` 은 `output/` 을 원문 발췌로 덮어쓴다**(LLM 을 안 부르므로 요약이 발췌다).
dry-run 뒤에는 `python rerender.py` 로 DB 내용으로 되돌린 다음 커밋할 것 — 안 그러면 발췌
텍스트가 그대로 배포된다.

## 지금 우선순위 → **PROJECT_MEMO §13 을 먼저 읽을 것** (2026-07-31 정리)

**소스 확장은 종료됐다(16소스 188건에서 동결). 고비용/유료 API 는 다음 주 논의로 연기.
렌더링(T3.x)도 2026-08-03 에 끝났다 — §13 "완성 정의 4개" 전부 충족.**
남은 건 §13.2 의 날짜에 걸린 판정 두 개뿐이다: **T1.1 논문 피드 3종 판정(~2026-08-04)
→ 그 다음에 T1.2 research 하한(0.55) 튜닝.** 순서 고정. 아래는 그 이전 히스토리(대부분 완료).

<details><summary>이전 P0/P1 기록</summary>

- **P0**: ✅ 완료 — `--dry-run` 은 이제 `save_items`/`commit_seen`/`purge_old_seen`/`record_digest` 를 스킵(DB 미변경).
  `--reset` 은 2026-07-29 부터 `seen` 테이블만 비움(아카이브 히스토리 보존), DB 전체 삭제는 `--purge-all`
  로 분리. 오염됐던 기존 DB도 초기화 완료.
- **P1**: ~~arXiv cs.AI 0건~~ ✅ · ~~Anthropic/Meta no_feed~~ ✅ · ~~6개월 백필~~ ✅(`backfill.py`) ·
  ~~min-significance 컷~~ ✅ 0.25 로 반영(`sources.yaml settings.min_significance`) ·
  ~~dedup 임계값(0.83)~~ ✅ 검증 완료, 변경 없음(0.80은 오병합 확인됨) ·
  카테고리 상한(6) 튜닝 — 보류(라이브 며칠 실행 후 재평가, PROJECT_MEMO §9 참고).
  2026-07-29 부터 탈락 아이템이 `items.is_published=0` + `drop_reason` 으로 쌓이므로
  `store.dropped_items()` 로 근거 데이터를 볼 수 있음.
- **자동화**: 개인 GitHub 레포 + Actions cron + Pages.
</details>

## 규칙 · 주의
- 요약은 2~3문장 자기 말로. **단 숫자(벤치·파라미터·금액·%)는 원문 그대로 보존.**
- signal > volume: 카테고리당 상한(기본 6). `community_takes` 는 v1 에서 OFF.
- cross-day dedup 은 seen-store(최근 14일 임베딩) 기반. 백엔드 바꾸면 `--reset` 으로
  seen-store와 item_emb를 함께 비운 뒤 `backfill_embeddings.py`로 장기 임베딩을 재생성할 것.
- `sources.yaml` 의 `status: verify` 는 첫 fetch 때 검증 필요. Mistral 만 아직 `no_feed`(v1.5 비활성이라 보류).
  Anthropic(sitemap 스크레이프)·Meta(Newsroom 태그 피드)는 대체 완료했지만 여전히 사이트 구조/피드
  변경에 죽을 수 있음 → source-health 배지로 계속 감시.

## ⚠️ 데이터 경계 (중요)
회사 내부 정보 · PII(개인식별정보) · 사내 독점 데이터는 이 프로젝트에 **절대 넣지 말 것.**
공개 AI 뉴스 피드만 다룸.

## 작업 방식
여러 파일 고치면 곧바로 `python pipeline.py --dry-run` 으로 돌려보고 에러 확인 후 다음 수정.
큰 변경은 한 번에 쌓지 말고 편집→테스트→커밋 루프로.
