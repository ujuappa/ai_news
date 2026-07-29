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

## 디자인 (2026-07-27 전면 개편)
Claude Design(claude.ai/design) 프로젝트에서 만든 "Modernist" 디자인을 DesignSync MCP 로 가져와
`render.py` 에 적용함(Archivo 폰트, radius 0, 5색 라이브 팔레트 피커, 카테고리 필터 페이지 신설,
significance 플랫 랭킹 구조). 이전 "SIGNAL" 디자인은 폐기. 자세한 내용/미완료 항목(recap 소급 생성)은
PROJECT_MEMO 변경로그 최신 항목 참고.

## 실행
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # torch 포함. 가벼운 건 requirements-lite.txt
echo "GEMINI_API_KEY=..." > .env         # 개인 키 (aistudio.google.com). .env 는 .gitignore 처리, 채팅에 붙여넣지 말 것
python pipeline.py --dry-run             # LLM 없이 수집/dedup (DB 미변경)
python pipeline.py                       # 전체
python pipeline.py --reset               # seen-store(cross-day dedup 기록)만 초기화, 아카이브 보존
open output/index.html
```

## 지금 우선순위 (자세한 건 PROJECT_MEMO 섹션 9)
- **P0**: ✅ 완료 — `--dry-run` 은 이제 `save_items`/`commit_seen`/`purge_old_seen`/`record_digest` 를 스킵(DB 미변경).
  `--reset` 플래그로 seen-store 초기화 가능(2026-07-29 부터 `seen` 테이블만 비움 — 아카이브 히스토리 보존.
  DB 전체를 밀어야 하면 `rm digest.db`). 오염됐던 기존 DB도 초기화 완료.
- **P1**: ~~arXiv cs.AI 0건~~ ✅ · ~~Anthropic/Meta no_feed~~ ✅ · ~~6개월 백필~~ ✅(`backfill.py`) ·
  ~~min-significance 컷~~ ✅ 0.25 로 반영(`sources.yaml settings.min_significance`) ·
  ~~dedup 임계값(0.83)~~ ✅ 검증 완료, 변경 없음(0.80은 오병합 확인됨) ·
  카테고리 상한(6) 튜닝 — 보류(라이브 며칠 실행 후 재평가, PROJECT_MEMO §9 참고).
- **자동화**: 개인 GitHub 레포 + Actions cron + Pages.

## 규칙 · 주의
- 요약은 2~3문장 자기 말로. **단 숫자(벤치·파라미터·금액·%)는 원문 그대로 보존.**
- signal > volume: 카테고리당 상한(기본 6). `community_takes` 는 v1 에서 OFF.
- cross-day dedup 은 seen-store(최근 14일 임베딩) 기반. 백엔드 바꾸면 `--reset` 으로 seen-store 초기화 필요.
- `sources.yaml` 의 `status: verify` 는 첫 fetch 때 검증 필요. Mistral 만 아직 `no_feed`(v1.5 비활성이라 보류).
  Anthropic(sitemap 스크레이프)·Meta(Newsroom 태그 피드)는 대체 완료했지만 여전히 사이트 구조/피드
  변경에 죽을 수 있음 → source-health 배지로 계속 감시.

## ⚠️ 데이터 경계 (중요)
회사 내부 정보 · PII(개인식별정보) · 사내 독점 데이터는 이 프로젝트에 **절대 넣지 말 것.**
공개 AI 뉴스 피드만 다룸.

## 작업 방식
여러 파일 고치면 곧바로 `python pipeline.py --dry-run` 으로 돌려보고 에러 확인 후 다음 수정.
큰 변경은 한 번에 쌓지 말고 편집→테스트→커밋 루프로.
