# CLAUDE.md — AI News Digest

Claude Code 는 세션 시작 시 이 파일을 자동으로 읽음.
**전체 결정·TODO·변경로그는 `PROJECT_MEMO.md` 참조 (작업 시작 전 먼저 읽을 것).**

## 프로젝트
매일 AI 뉴스를 자동 수집 → 중복제거 → 분류 → 요약 → 랭킹해서 정적 웹페이지로 굽는
개인용 데일리 다이제스트.
파이프라인: `fetch.py` → `dedup.py` → `llm.py` → `store.py`(SQLite) → `render.py`,
오케스트레이터 `pipeline.py`, 설정 `sources.yaml`. `backfill.py` 는 1회성 과거 데이터 백필용
(2026-07-27 에 6개월치 실행 완료 — 재실행은 보통 불필요, PROJECT_MEMO 참고).
`rerender.py` 는 DB 데이터로 전체 페이지를 API 비용 없이 재생성(디자인만 바꿨을 때 사용).
`generate_recaps.py` 는 recap(주간 헤드라인/$ 집계/카테고리 요약) 소급 생성용, 아직 미실행.
`linkcheck.py` 는 이미 게시된 링크의 link rot 점검(→ `items.link_status`, 죽은 링크는 렌더에서
href 가 떨어짐). 판정 기준과 "무엇을 죽었다고 부르지 않는지"는 PROJECT_MEMO 2026-08-04 참고.

## 디자인 (2026-07-27 전면 개편 → 08-03 2차 → 08-06 홈 상단 재편)
Claude Design(claude.ai/design) 프로젝트에서 만든 "Modernist" 디자인을 DesignSync MCP 로 가져옴
(Archivo 폰트, radius 0, 라이브 팔레트 피커, significance 플랫 랭킹).
마크업은 `templates/*.html`, 스타일은 `static/digest.css`, `render.py` 는 데이터 가공만 한다.

**2026-08-06 홈 상단 재편**(캔버스 "Home Top Organization" 6a): 마스트헤드가 한 줄로
(워드마크+빨간 점 · 검색 · pill 네비), 날짜/건수가 지면 머리(`.page-head`)로 내려가고,
리드+Also today 가 한 장의 카드(`.panel`)로 묶이면서 기간 세그먼트와 필터가 그 카드에 붙었다.
필터는 pill 줄 → **컨트롤 줄 + 서랍 + 제거 가능한 chip, 다중선택(OR)** 으로 바뀌었고
그날 붙은 토픽 전부가 서랍에 들어간다(top-6 상한 폐지). 팔레트는 6색(`Boncom · Maroon` 추가 —
6a 의 **색만** 들여왔다. 폰트/radius 는 전역이라 Archivo·radius 0 유지).
- **사인인 · Weekly · Monthly · Following · 코멘트/팔로우는 의도적으로 없다** (로그인+쓰기
  백엔드 미구현 → 죽은 버튼 방지). 6a 의 소셜 카드 3장을 붙일 자리는 `templates/home.html`
  끝 주석, 네비는 `templates/macros.html` 주석 참고. `test_render_assets.py` 가 새는 걸 막는다.
- **필터를 건드릴 때**: 컨트롤 줄은 `.panel-body`(data-section) **밖**에 둬야 한다 — 안에 두면
  필터가 자기를 숨겨서 되돌릴 수 없게 된다(`test_topics.py` 에 회귀 가드 있음).
- **이미지는 빈 슬롯이 자리만 잡고 있다.** `static/img/<source_id>.webp` 등을 넣으면 자동 반영 —
  `static/img/README.md` 참고.
- CSS 는 **팔레트 키(`--g --ink --acc --n1 --n2 …`)만** 쓸 수 있다. 캔버스의 `--color-*` 를
  들여오면 `tests/test_render_assets.py` 가 잡는다(매핑표는 digest.css 헤더 주석).

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
open output/index.html
```

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
