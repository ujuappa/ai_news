# AI News Digest — 프로젝트 메모 (결정 로그)

> 이 파일은 아이디어 단계부터 쌓아온 결정과 제안을 버리지 않고 모아두는 곳.
> 프로젝트 끝날 때까지 계속 업데이트하면서 참조.
> 최종 수정: 2026-07-27

---

## 0. 목표 (한 줄)

매일 AI 뉴스를 자동 수집 → 중복제거 → 분류 → 요약 → 랭킹해서, **웹페이지에 데일리 다이제스트로 굽는** 완전자동 개인용 앱.

---

## 1. 확정된 스코프

| 항목 | 결정 |
|---|---|
| 완성도 | **완전 자동 데일리 앱** |
| 제작자 수준 | 개발 익숙 |
| 전달 방식 | **웹페이지** (정적 사이트) |

---

## 2. 아키텍처 (결정)

파이프라인 한 줄:
**수집 → 정규화·중복제거(상태 보유) → LLM(분류+요약+랭킹) → DB 저장 → 정적 페이지 재생성**

추천 스택 (서버리스, 저비용, 안 깨짐):
- Python 파이프라인
- SQLite (히스토리 + seen-store)
- 임베딩 (중복제거)
- 정적 생성 (Astro/11ty 또는 md→HTML)
- GitHub Actions 크론 (매일 실행)
- Vercel / Netlify / GitHub Pages 호스팅
- → 아카이브가 공짜로 딸려옴

---

## 3. 다이제스트 규칙 (원 프로젝트 프롬프트 + 리뷰에서 보강)

카테고리 5개:
1. Model releases
2. Research
3. Tools & products
4. Policy & business
5. Community takes  *(v1에서는 OFF)*

핵심 규칙:
- **중복제거**: 같은 사건 묶기. 날짜 넘는 dedup 필수(seen-store).
- **요약**: 항목당 2~3문장, 자기 말로. 단 **벤치마크·파라미터 등 숫자는 원문 그대로 보존**(할루시네이션 방지).
- **랭킹 rubric** (고정): 프런티어 모델 > 대형 펀딩/인수 > 벤치 신기록/역량 > 정책 전환 > 점진 연구 > 커뮤니티 반응.
- **signal > volume**: minor·중복은 스킵. 카테고리당 상한(기본 6개), 조용한 날엔 상한 무시.
- **상단 플래그**: 프런티어 모델 / 대형 딜 / 정책 전환은 맨 위에.
- **소스 신뢰도**: 확인된 뉴스 vs 추측 구분 (특히 forum/community).

---

## 4. v1 vs 나중 (스코프 크립 방지)

### v1 (목표: 이번 주말, 실작업 2~4일)
- 소스 **10개 안쪽**: 랩 블로그 4~5 + arXiv 2~3 + HN 필터 1 + Import AI
- 기본 dedup + LLM 스텝 + 정적 페이지 + 크론
- **Community takes 카테고리 OFF**
- 실제 출력 며칠 눈으로 보고 나서 튜닝 (임계값/랭킹)

### v2 (+1~2주)
- 임베딩 크로스데이 dedup 정교화
- 소스 확장 (Reddit/포럼, 유튜브 트랜스크립트, X/트위터)
- 페이지 다듬기, 랭킹 튜닝, 아카이브/검색

---

## 5. 파킹된 아이디어 (버리지 말 것 — 나중에 재검토)

- [ ] **어제 대비 "변경점(diff)" 뷰** ⭐ — 굴러가는 스토리 추적. DB 있으면 거의 공짜. "새 소식"보다 "어제 그거 어떻게 됐어"가 중요할 때 많음. **v2 1순위 후보.**
- [ ] **소스 헬스 모니터링** — 미러/생성 피드가 조용히 죽는 것 감지. "N일간 아이템 0개"면 다이제스트 하단에 `⚠️ 소스 이상` 배지. 코드 몇 줄, 가치 큼. **v1 막판~v2 초 후보.**
- [ ] **과거 다이제스트 아카이브 + 검색** — 정적 구조면 거의 자동.
- [ ] **다이제스트를 RSS로도 출력** — 나중에 리더/이메일 연동이 공짜가 됨.
- [ ] **취향 학습/개인화** — 관심 카테고리 가중치. 명시적 v1 제외, 한참 나중.
- [ ] **공식 피드 없는 블로그용 자체 파서** — Olshansk/rss-feeds 참고. 미러 의존 줄이면 안정성↑.
- [x] ~~**아카이브 재백필**~~ — 2026-07-29 실행 완료(400건/45 다이제스트, 변경로그 참고). 아래는 원래 메모:
  **다음 단계로 남은 것**: (1) 소스 확장(arXiv/TechCrunch/HN 포함) 재백필, (2) 아카이브 인덱스 범위를
  1~2년으로 확대(현재 최근 6개 + "+N 더보기" 정적 표기).
- [ ] **아카이브 재백필(소스 확장)** — 2026-07-28 사용자 확인: 현재 6개월 백필 아카이브는 블로그/랩
  발표 7개 소스만 사용(arXiv/TechCrunch/HN 은 볼륨 폭탄이라 당시 의도적으로 제외, §7/§9 참고) 라서
  아카이브 페이지에 소스가 사실상 하나만 보이는 것처럼 느껴짐. **지금 당장 손대지 않기로 결정** — 나중에
  (호출 가능한 API 소스가 더 확보되면) 소스를 더 모아서 지난 6개월 흐름을 다시 보는 용도로 재백필하기로 함.
  **실행 시 `python pipeline.py --purge-all` 선행 필수** — 소스 구성이 바뀌면 주간 클러스터링 결과가
  달라져서 옛 실행 아이템이 남아 아카이브가 섞임(2026-07-29 에 플래그 신설).

---

## 6. 시간 추정 (개발 익숙 기준)

- v1 엔드투엔드: **2~4일** (주말 하나~저녁 며칠)
- v2 정교화: **+1~2주**
- → 쓸 만한 건 이번 주말, 진짜 좋은 건 2~4주

---

## 7. 소스 리스트

→ 별도 파일 `sources.yaml` 참조. **피드 검증 완료: 2026-07-25.**

검증 결과 요약:
- **수정**: DeepMind → `https://deepmind.google/blog/rss.xml` (기존 `/discover/blog/` 는 틀림)
- **공식 피드 없음(no_feed)**: Anthropic(미러), Meta AI(RSSHub 경로/자체파서), Mistral(생성피드) → **source-health 감시 대상**
- **verified 승격**: OpenAI, DeepMind, arXiv(AI/LG/CL), Hugging Face, Import AI, Ahead of AI, TechCrunch, The Verge, HN, Reddit
- **still verify(v2)**: The Gradient, Simon Willison — 표준 형식이라 build 때 확인
- 주의: Import AI/Ahead of AI는 **저빈도**(주간·월간), TechCrunch는 **고볼륨+본문 발췌만**, HF 피드는 item `<link>` 누락 → guid로 URL 파싱

---

## 8. 첫 라이브 실행에서 발견한 것 (2026-07-27)

- ✅ `--dry-run` 성공: 키 없이 24개 수집·렌더 확인 (맥, 인터넷 열림 → 소스 라이브 수집).
- ✅ 진짜 실행(API 키): **LLM 요약 정상** — 2~3문장 재작성, 숫자 보존(예: "43%"), 심지어
  "홍보성 공지, 새 뉴스 아님" 같은 signal 판단까지 함. 분류·숫자보존 동작 확인.
- ⚠️ **진짜 실행이 2개만 나온 이유 = 버그 아님, seen-store 오염**: 앞선 `--dry-run` 이
  24개를 seen-store 에 커밋 → 진짜 실행 때 전부 "이미 다룸"으로 스킵됨. cross-day dedup 은
  제대로 작동한 것. **단, `--dry-run` 이 상태를 건드리면 안 됨 → P0 버그.**
- ⚠️ arXiv cs.AI 0건 (원인 확인 필요: 주말 미발행? http→https? 포맷?). Anthropic/Meta 0건은 예상됨(공식 피드 없음).
- ⚠️ 홍보/이벤트성 아이템(TechCrunch Disrupt 아젠다)이 통과됨 → min-significance 컷 필요.

## 9. 우선순위 TODO (현재 작업 목록)

**P0 — 지금 당장 (버그, 이번 실행에서 발견):**
- [x] `--dry-run` 부작용 제거: dry-run 이면 `save_items`/`commit_seen`/`purge_old_seen`/`record_digest` 건너뛰기 (pipeline.py) — 2026-07-27
- [x] seen-store 리셋 수단 + 문서화 (`--reset` 플래그, digest.db 삭제) — 2026-07-27. ※ 기존 DB는 아직 오염 상태 그대로 남아있음 — 깨끗한 실행하려면 `python pipeline.py --reset` 먼저 실행 필요

**P1 — 첫 "진짜" 다이제스트 제대로 뽑기:**
- [x] **min-significance 컷 추가** — 2026-07-27. 백필 412건 데이터로 분석: significance<0.25 가 36건(8.7%),
  대부분 고객사례/템플릿 페이지("Healthcare", "ChatGPT for marketing teams", "Claude for Financial Services" 등).
  `sources.yaml settings.min_significance: 0.25` 추가, `config.py Settings.min_significance` 필드 추가,
  `pipeline.py`/`backfill.py` 모두 LLM 엔리치 직후 `ranked_pool = [it for it in clustered if it["significance"] >= settings.min_significance]`
  로 랭킹/상한/저장 전에 드롭 (단 `commit_seen` 은 드롭된 것 포함 전체에 호출 — 내일 같은 저의미 스토리 재스코어 안 하려고).
  **참고**: 기존에 이미 생성된 6개월 백필 아카이브(27주)는 이 필터 적용 전 데이터라 0.25 미만 항목이 일부 남아있음 — 재실행은 안 함(비용), 다음 백필/일간 실행부터 적용됨.
- [x] **dedup 임계값(0.83) 검증** — 2026-07-27. 백필 원본 598건으로 로컬 재클러스터링(임베딩만, API 비용 없음)해서
  0.80/0.83/0.85/0.88 비교. **0.83 이 이미 적절함, 변경 안 함.** 근거: 0.80 으로 낮추면 "Claude Opus 4.5"↔"Claude Opus 4.6"
  (다른 모델), "$65B Series H"↔"$30B Series G"(다른 펀딩 라운드) 가 오탐 병합됨. 0.83 에서는 둘 다 정확히 분리.
- [ ] **카테고리 상한(6) 튜닝** — 보류. 백필(주간 버킷)로 확인해보니 바쁜 주(W28/W30)엔 4개 카테고리 중 3개가
  정확히 6건에서 꽉 참(캡이 실제로 컷하고 있음) — 그런데 이건 주간 집계라 일간 다이제스트보다 상대적으로 빡빡한 게
  당연해서 이 데이터로는 일간 캡 적정성을 판단 불가. **실제 며칠 라이브 실행 후 재평가하기로 결정.**
- [x] arXiv cs.AI 0건 원인 확인/수정 — 2026-07-27. 원인: `export.arxiv.org/rss/cs.AI` 가 빈 채널(`<item>` 0개) 반환.
  arxiv.org 자체 리스팅엔 최근 1111건 있고, 같은 export 호스트에서 cs.LG/cs.CL 은 정상(rss.arxiv.org 와 바이트 단위 동일) →
  cs.AI 카테고리에 한해 export.arxiv.org 쪽 캐시/렌더링 버그로 추정(arXiv 측 문제, 우리 코드 버그 아님).
  `rss.arxiv.org/rss/cs.AI` (arXiv 신규 표준 RSS 호스트)는 정상(223건) → `sources.yaml` feed_url 교체로 해결.
  dry-run 재확인: arxiv_ai 25건 정상 수집.
- [ ] min-significance 컷 추가 (예: 0.25 미만 드롭) — 홍보/이벤트성 필터
- [x] Anthropic/Meta `no_feed` 해결 — 2026-07-27. RSSHub 계열 미러(rsshub.app/bestblogs.dev) 전부 403/timeout 확인 후 폐기:
  - **Anthropic**: 공식 RSS 없음 → `sitemap.xml`(`/news/` 250건, lastmod 2024-05까지) + 기사 페이지 스크레이프로 대체
    (`fetch.py: fetch_sitemap_source`, `sources.yaml: parse: sitemap`). og:description 이 일부 페이지에서
    사이트 공통 문구(boilerplate)만 주는 것 발견 → `<main>` 첫 문단 우선 추출로 수정(안 그러면 Opus 4.5/4.7/5 가
    dedup 에서 뭉개질 뻔함 — 실제로 fix 전엔 240→233 클러스터, fix 후 240→237 로 늘어남, 4개 Opus 버전 모두 분리 확인).
  - **Meta**: `ai.meta.com/blog` 자체 RSS는 여전히 없음(RSSHub #16938) → 대신 Meta Newsroom(WordPress)의
    공식 `"ai"` 태그 피드(`about.fb.com/news/tag/ai/feed/`) 사용. 연구 블로그보다 범위가 넓어(하드웨어/PR 포함)
    카테고리·랭킹에서 걸러질 것으로 기대, 관찰 필요.
  - 부수적으로 `_clean()` 에 `html.unescape` 추가(엔티티 `&#x27;` 등 안 풀리던 버그, 전체 소스 공통 개선).
  - Mistral 은 여전히 no_feed (v1.5 비활성이라 보류, sitemap-0.xml 은 있지만 lastmod 없어서 더 손이 감).
- [ ] 실데이터 며칠 돌리며 dedup 임계값(0.83)·카테고리 상한(6) 튜닝

**P1~P2 — 자동화 ("완전 자동" 목표 완성):**
- [x] 개인 GitHub 레포 + `GEMINI_API_KEY` 시크릿 + Actions cron + Pages 켜기 — 2026-07-28 완료
  (private repo `ujuappa/ai_news`, 상세는 변경로그 참고)
- [x] `.gitignore` (.venv, __pycache__), `digest.db` 커밋 여부 결정 — 2026-07-28. `digest.db`는
  `.github/workflows/daily.yml`이 이미 `git add output/ digest.db`로 커밋하는 구조라 "커밋함"으로 확정.
  `.DS_Store`/`.claude/settings.local.json` 도 `.gitignore`에 추가(로컬 전용 파일이라 레포에 불필요).
- [x] cron 시간대(UTC) 확인 — 매일 14:00 UTC 그대로 유지, 모델은 `gemini-2.5-flash` 확정(비용 재검토는 라이브 며칠 관찰 후).

- [x] **1회성 6개월 백필** — 2026-07-27 완료. `backfill.py` 신규(블로그/랩 발표 7개 소스만:
  OpenAI/Anthropic/DeepMind/Meta/HuggingFace/Ahead of AI/Import AI, arXiv·TechCrunch·HN 은 볼륨
  폭탄이라 제외 — cs.AI 만 6개월 34,000건+). 598건 수집 → dedup 580 클러스터 → ISO 주 단위로
  버킷팅 → 주당 `archive/YYYY-Www.html` 다이제스트 27개 생성(Haiku 로 엔리치, 비용 절감).
  seen-store 는 건드리지 않음(commit_seen 미호출 — 14일 롤링 cross-day dedup 과 무관한 과거
  데이터라 의미 없음), 오늘자 `output/index.html` 도 미변경(`render.render_archive_digest` 로
  archive/ 에만 씀). 재사용 가능한 부산물: `fetch.py` 에 `fetch_sitemap_source`(sitemap.xml 스크레이프,
  no_feed 소스용, since 파라미터로 백필도 지원)와 `fetch_paginated_feed`(WordPress `?paged=`),
  `llm.enrich()` 에 `model` 파라미터 추가.

**v2 — 파킹 (섹션 5 참조):**
- [ ] 어제 대비 diff 뷰 (1순위) / 아카이브 검색 / RSS 출력 / 페이지 디자인
- [ ] 소스 확장(Reddit·YouTube·X) / 개인화 / cross-day "새 각도면 업데이트" 로직

---

## 10. v3 — 멀티유저 전환 (로드맵, 2026-07-28 논의)

> 목표 변경: **개인용 정적 사이트 → 개인화 + 멀티유저 + 사내 배포** 웹앱.
> 당장은 사용자 1인용이지만 회사 프로젝트로 넘어갈 가능성 있음. 규모 5~10배 커지는 것 감수하기로 함.
> **내일(2026-07-29~) 이어서 진행.** 아래는 방향 합의만 된 상태 — 코드 미착수.

### 10.1 핵심 아키텍처 결정 — "정적 사이트에 로그인 붙이기" 는 함정, 안 함
- **파이프라인(수집·dedup·LLM 엔리치·랭킹)은 그대로 유지** — 유저 수와 무관한 진짜 자산. 안 바뀜.
- **바뀌는 건 전달 계층뿐**: `파이프라인 → HTML 굽기` 를 `파이프라인 → 구조화 데이터(DB/API) → 유저별로 읽는 웹앱` 으로.
- 정적에 억지로 인증을 붙이면 정적의 장점이 다 사라짐 → 파이프라인을 **콘텐츠 백엔드**로 두고 그 위에 앱을 새로 얹는 그림.

### 10.2 지금 당장 (회사행 확정 안 됐어도 무조건 이득) ⭐
- [ ] **파이프라인 ↔ 렌더링 분리** — 렌더가 HTML 을 바로 굽지 말고, 엔리치된 항목을 깨끗한 DB 테이블(또는 JSON API)로 내보내고 정적 사이트는 그걸 읽어서 렌더. 개인용 사이트는 계속 돌면서, 나중에 앱이 **같은 데이터를 그대로** 소비. 리스크 낮고 레버리지 제일 큼.
- 저장소: 개인용까진 SQLite 충분 → 멀티유저 가면 **Postgres** 로.

### 10.3 인증 — Microsoft (Entra ID / Azure AD) SSO
- 회사 인증 = **Microsoft 365** 확인됨(2026-07-28). → 사내 도구는 회사 IdP 로 SSO 가 정답.
- **자체 로그인/비번 저장 절대 안 만듦** (보안 부채). Entra ID 직접 연동, 또는 관리형(WorkOS/Auth0/Clerk/Supabase Auth 등 엔터프라이즈 SSO 지원) 사용.
- ⚠️ 스택(호스팅·프레임워크)은 이 SSO 경로에 맞춰 내일 구체화.

### 10.4 개인화 — "학습형" 부터 만들지 말 것 (순서 고정)
1. **명시적 상태 먼저**: 읽음/안읽음, 저장(북마크), 카테고리·소스 팔로우/뮤트. 유저별 테이블이면 끝. 싸고 체감 큼.
2. **유저별 재랭킹**: §5 파킹의 "관심 카테고리 가중치" 를 significance 에 곱해 사람마다 순서 다르게.
3. **ML 취향 학습**: 한참 나중. 데이터 쌓여야 하고 지금 만들면 낭비.

### 10.5 보안 — 이제 "필수"
- 유저 계정 = 실제 PII(이메일 등) 취급 → 접근제어 / 데이터 보관·삭제 정책 / 시크릿 관리가 필수로 승격.
- ⚠️ **키 노출 3회 이력**(§ 변경로그: Anthropic·Gemini·평문 파일) — 개인용일 땐 재발급으로 끝났지만 **회사 프로젝트에선 사내 데이터·크레덴셜을 채팅/코드에 붙여넣는 게 훨씬 무거운 문제**. `.env`/시크릿 매니저로만 다루고, 공식화되면 회사 IT/보안 리뷰 1회 태우기.

### 10.6 현실 체크 & 단계
- 정적-개인용 → 멀티유저-회사앱 = 체감 복잡도 **5~10배**(인증, DB 마이그레이션, 유저별 상태, 서버 호스팅, 보안 리뷰). 한 번에 다 하지 말 것.
- **단계**: (1) 지금 = 파이프라인↔렌더 분리(데이터를 DB/API로), 개인용 계속 → (2) 회사행 확정 시 = 앱 골격(Entra SSO + 유저 테이블 + 명시적 개인화) → (3) 유저별 재랭킹 → (4, 한참 뒤) 학습형 개인화.

---

## 변경 로그
- 2026-07-25: 스코프 확정(완전자동/웹), 아키텍처·rubric·v1 소스 결정. config 초안 + 이 메모 생성.
- 2026-07-25: 피드 URL 전수 검증. DeepMind URL 수정, Meta/Mistral no_feed 확정, 나머지 verified 승격.
- 2026-07-25: v1 파이프라인 스켈레톤 완성(8개 모듈+워크플로+README). 합성데이터로 렌더/랭킹 검증.
- 2026-07-27: 초보용 lite 경로 추가(torch 없이 해싱 dedup 폴백). 맥 실행 가이드 README 반영.
- 2026-07-27: **첫 라이브 실행 성공** (맥). dry-run 24건 수집·렌더 확인 → 진짜 실행 LLM 요약 확인. dry-run seen-store 오염(P0), arXiv 0건, promo 누출 발견. 우선순위 TODO 작성.
- 2026-07-27: **P0 수정**: `pipeline.py` — dry-run 시 `save_items`/`commit_seen`/`purge_old_seen`/`record_digest` 스킵하도록 write 경로를 `if not dry_run:` 으로 가드. `--reset` 플래그 추가(digest.db 삭제). `--dry-run` 재실행으로 DB row count·md5 불변 확인(회귀 없음). README/CLAUDE.md 문서 반영. 사용자 확인 후 오염된 digest.db `--reset` 으로 초기화 완료.
- 2026-07-27: **P1 — arXiv cs.AI 0건 수정**: 원인은 `export.arxiv.org/rss/cs.AI` 가 빈 채널을 반환하는 arXiv 측 버그(cs.LG/cs.CL 은 같은 호스트에서 정상). `sources.yaml` 의 arxiv_ai feed_url 을 `rss.arxiv.org/rss/cs.AI` 로 교체 → dry-run 에서 25건 정상 수집 확인.
- 2026-07-27: **P1 — Anthropic/Meta no_feed 해결**: Anthropic 은 sitemap.xml+스크레이프(`fetch_sitemap_source` 신규), Meta 는 Newsroom "ai" 태그 공식 RSS 로 교체. 스크레이프 중 og:description boilerplate 문제 발견해 `<main>` 첫 문단 추출로 수정, `_clean()` html.unescape 추가. dry-run 에서 anthropic 25건/meta_ai 10건, Opus 4.5/4.6/4.7/5 모두 별개 클러스터로 분리 확인.
- 2026-07-27: **1회성 6개월 백필 실행**: `backfill.py` 작성, 사용자와 스코프 확정(블로그/랩 발표 7소스·6개월·Haiku·주간 아카이브) 후 실행 완료. 598건 → 580 클러스터 → 27주 다이제스트. seen-store/오늘자 index.html 미변경 확인. ⚠️ 이 과정에서 사용자가 ANTHROPIC_API_KEY 를 `!` prefix 대신 채팅에 직접 붙여넣어 대화 기록에 평문 노출됨 — 세션 종료 후 키 교체(rotate) 권고함.
- 2026-07-27: **P1 튜닝 3종 마무리**: 백필 데이터로 min-significance 컷(0.25) 데이터 기반 결정 후 코드 반영(`config.py`/`pipeline.py`/`backfill.py`). dedup 임계값(0.83)은 로컬 재클러스터링으로 검증만 하고 유지(0.80은 Opus 4.5/4.6, $65B/$30B 펀딩을 오병합하는 것 확인). 카테고리 상한(6)은 주간 백필 데이터로 일간 캡 적정성 판단이 안 돼서 보류, 라이브 며칠 후 재평가.
- 2026-07-28: **LLM 프로바이더 Anthropic → Gemini 전환**. Anthropic API 키 소진, Gemini Cloud 키로 교체.
  `llm.py`: `anthropic` SDK → `google-genai`(`genai.Client`/`generate_content`, `response_mime_type=application/json`
  로 JSON 강제) 로 교체. `config.py`: `ANTHROPIC_API_KEY`→`GEMINI_API_KEY`, `MODEL` 기본값
  `claude-sonnet-5`→`gemini-2.5-flash`. `backfill.py`: `BACKFILL_MODEL`(대량/저비용 티어)
  `claude-haiku-4-5`→`gemini-2.5-flash-lite`. `requirements.txt`: `anthropic`→`google-genai`.
  README/CLAUDE.md 의 env var·모델명 문서도 갱신. `sources.yaml`/`backfill.py` 의 `anthropic`
  뉴스 소스(Anthropic 블로그 스크레이프)는 LLM 프로바이더와 무관해서 손대지 않음.
  dry-run 재확인 완료(임포트/문법 정상, 227 클러스터 렌더). **모델명(`gemini-2.5-flash`,
  `gemini-2.5-flash-lite`)은 마이그레이션 시점 기준 추정값 — 실제 실행 전 Google AI Studio에서
  현재 유효한 모델명인지 재확인 필요.**
- 2026-07-28: **키 노출 재발 + `.env` 방식으로 전환**. Gemini 키 교체 과정에서 사용자가 `!` 접두사로
  `export GEMINI_API_KEY=...`를 실행했으나, `!` 는 실행 방식만 바꿀 뿐 명령어 텍스트 자체(키 값 포함)가
  대화 기록에 그대로 남는다는 걸 확인 — 노출 재발(1차는 2026-07-27 Anthropic 키). 게다가 export 한 값이
  내 Bash 툴 쉘에 반영도 안 됨(툴 호출 간 쉘 상태 비유지) 확인 → 노출만 되고 기능적 이득도 없었음.
  사용자에게 즉시 해당 Gemini 키 재발급 요청. 재발 방지로 `config.py` 에 `python-dotenv` 로딩 추가
  (`load_dotenv(ROOT / ".env")`), `.env`/`.venv`/`__pycache__` 를 `.gitignore` 에 추가(신규 생성),
  `requirements.txt` 에 `python-dotenv` 추가, README/CLAUDE.md 셋업 안내를 `export` 대신
  `echo "GEMINI_API_KEY=..." > .env`(별도 터미널에서 직접 작성) 방식으로 갱신. **앞으로 비밀값은
  채팅에 어떤 형태로도(`!` 포함) 붙여넣지 않고 `.env` 파일로만 주고받기로 함.**
- 2026-07-28: **Gemini 인증을 API 키 → Vertex AI 서비스 계정으로 전환**. 발급받은 키가
  Google Cloud 콘솔 키였는데 `403 API_KEY_SERVICE_BLOCKED`로 막힘(Generative Language API
  미활성/키 제한 추정) → 단순 API 키 대신 Vertex AI(GCP 프로젝트 `bcc-bon-innovation-ai`,
  리전 `us-central1`) 로 전환하기로 결정. `llm.py` 의 `genai.Client(api_key=...)` 를
  `genai.Client()`(인자 없음, `.env`의 `GOOGLE_GENAI_USE_VERTEXAI`/`GOOGLE_CLOUD_PROJECT`/
  `GOOGLE_CLOUD_LOCATION`/`GOOGLE_APPLICATION_CREDENTIALS` 로 자동 인증)로 교체.
  `config.py` 의 이제 안 쓰는 `GEMINI_API_KEY` 상수 제거. `.gitignore` 에 `service-account.json`
  추가. `.github/workflows/daily.yml` 도 Anthropic 기준으로 남아있던 걸 발견해서 같이 갱신
  (서비스 계정 JSON 시크릿을 파일로 써서 `GOOGLE_APPLICATION_CREDENTIALS` 로 지정하는 스텝 추가,
  `DIGEST_MODEL=gemini-2.5-flash`). README 셋업/배포 섹션도 반영. **서비스 계정 JSON 키 파일
  생성·로컬 배치는 사용자가 GCP 콘솔+터미널에서 직접 진행 중 — 완료되면 실제 파이프라인
  재테스트 필요.**
- 2026-07-28: **다시 일반 Gemini API 키(Developer API)로 복귀 + 실전 검증 완료**. Vertex AI 서비스
  계정 설정 대신 일반 API 키로 되돌림 — `genai.Client()` 를 인자 없이 호출하는 코드라 `.env` 에
  `GEMINI_API_KEY` 만 있으면 자동으로 Developer API 모드로 붙어서 코드 변경 없이 바로 동작.
  실제 실행(`python pipeline.py`) 중 `JSONDecodeError: Unterminated string` 발견 → 원인은
  Gemini 2.5 계열의 기본 활성화된 thinking(내부 추론) 토큰이 `max_output_tokens`(4000) 예산을
  다 소모해 실제 JSON 응답이 잘림. `llm.py` 의 `enrich()`/`generate_recap()` 양쪽에
  `thinking_config=types.ThinkingConfig(thinking_budget=0)` 추가(이 작업엔 추론 불필요)로
  끄고, `max_output_tokens` 도 여유 있게 상향(4000→16000, 1000→4000). 재실행으로 240건 수집→
  237 클러스터→엔리치 성공→저의미 17건 드롭→리캡 생성→렌더(24 items, 12 major) 전 구간 확인,
  요약 숫자 보존("$30 billion", "$380 billion", "1M-token" 등)도 정상 동작 확인.
  **Gemini 마이그레이션 사실상 완료** (남은 건 며칠 라이브 돌리며 품질/비용 관찰).
- 2026-07-28: **리드 스토리가 5개월 전 뉴스로 뜨는 버그 발견·수정**. 재실행한 다이제스트 홈페이지
  1등(significance 0.95) 항목이 실제로는 `2026-02-12` 발행(오늘 대비 5.5개월 전) 펀딩 뉴스였음.
  원인 2가지: (1) 랭킹이 `llm.py` rubric 상 significance 만으로 결정되고 최신성은 전혀 반영 안 함
  (의도된 고정 rubric), (2) `fetch.py: fetch_source`/`fetch_sitemap_source` 가 일간 파이프라인
  에서도 "최근 N일" 컷오프 없이 그냥 "피드의 최신 25개 항목"만 가져옴 — 업데이트 뜸한 소스
  (Anthropic sitemap 등)의 오래된 백로그가 그 25개 안에 남아있을 수 있음. 여기에 어제 `--reset`
  으로 seen-store 를 비운 직후의 첫 실행이라 그 오래된 항목이 "신규"로 잡혀 리드 자리를 차지.
  사용자와 상의해 **수집 단계에 신선도 컷오프 추가**로 결정(랭킹 rubric 자체는 안 건드림 —
  PROJECT_MEMO 3장에 고정으로 못박은 부분이라 별도 논의 필요). `sources.yaml settings.max_item_age_days: 7`
  신설, `config.py Settings.max_item_age_days` 필드 추가, `fetch.py fetch_source()/fetch_all()`
  에 `max_age_days` 옵션 파라미터 추가(발행일 파싱 실패 항목은 안전하게 통과시킴, backfill.py 는
  이 인자 없이 직접 호출해서 영향 없음), `pipeline.py` 에서 `settings.max_item_age_days` 전달.
  `--reset` 후 재실행으로 검증: DeepMind 25→2건, Ahead of AI 20→0건(월간 주기라 이번 주는 0건이
  맞음, source-health 배지로 정상 표시), 리드 스토리들 전부 `2026-07-22~07-28` 로 정상화 확인.
- 2026-07-27: **UI/UX 전면 개편 ("Modernist" 디자인, Claude Design 연동)**. 사용자가 claude.ai/design 프로젝트
  "AI-Digest UI Redesign"(캔버스 `AI Digest Redesign.dc.html`, 3턴 반복)에서 만든 디자인을 DesignSync MCP 로
  가져와 포팅. 이전 SIGNAL 디자인(시그널 미터/히어로 카드/JetBrains Mono)은 전부 폐기.
  - **비주얼**: Archivo 폰트 단일 사용, radius 0(완전 각짐). 카테고리별 섹션 그룹 대신 significance 기준
    플랫 랭킹 구조(리드 스토리 1건 + 3열 그리드 + 목록 + in-brief) + 사이드바(signal-index 히스토그램 +
    source-alert).
  - **팔레트**: Cream·Cobalt/Sage·Teal/Blush·Plum/Oat·Ember/Mist·Signal-red 5색 세트를 사용자가 "라이브
    피커 실제 구현"으로 선택 → `localStorage` 저장 + CSS 커스텀 프로퍼티로 즉시 전환되는 실제 기능 구현
    (캔버스의 팔레트 피커는 원래 React 기반 캔버스-툴 전용 데모였음 — 실제 vanilla JS+localStorage 로 재구현).
    기본값은 Mist·Signal-red(기존 사이트 정체성과 가장 가까움, styles.css 자체 기본값이기도 함) — 5개 중
    하나로 확정되지 않은 채 디자인 세션이 끝나서 임의로 정함, 필요하면 바꿀 수 있음.
  - **신규 페이지 타입**: 카테고리별 필터 페이지(오늘은 `{category}.html` 루트, 과거 주는
    `archive/{label}-{category}.html`) 추가 — 필터 pill(All/Major/최다소스), 랭킹순 플랫 리스트,
    "category cap 6 · min significance 0.25" 같은 실제 튜닝값을 푸터에 노출.
  - **검색**: "헤더에 인라인(디자인안)" 선택 — 검색창은 모든 페이지 헤더에 넣되, 실제 검색 결과는 여전히
    `search.html` 한 곳에서만 처리(412+건 전체를 모든 페이지에 중복 임베드하는 건 낭비라 판단, 시각적
    위치만 디자인 반영). `search.html` 자체는 3b 목업대로 `<mark>` 하이라이트 + 히트카운트 + significance
    점수 프리픽스로 재디자인.
  - **아카이브 인덱스**: 27주 전체 나열 대신 최근 6개 + "+21개 더보기"(정적 텍스트, 클릭 토글 아님 —
    디자인 원본에도 없던 기능이라 그대로 따름) + 주간 볼륨 미니바 차트로 개편.
  - **신규 LLM 콘텐츠**("추가한다" 선택): `llm.py` 에 `generate_recap()` 추가 — 주간 편집 헤드라인
    (예: "The week Anthropic shipped six models"), $ 집계(펀딩/투자만 대상, 신뢰 안 되면 null 반환하도록
    프롬프트에 명시 — "대략적 근사치"로 표시), 카테고리별 한 줄 요약을 한 번의 API 호출로 생성. `store.py`
    에 `recaps` 테이블 신설. **다만 헤드라인/$ 집계는 주간 아카이브 페이지(1f 디자인)에만 쓰이고,
    카테고리 one-liner 는 오늘/과거 카테고리 페이지 둘 다에 씀** — 일간 홈페이지(3a 디자인)엔 원래
    디자인에 없던 요소라 안 씀, 그래서 daily pipeline.py 도 recap 을 매일 한 번 생성은 하지만
    실제 화면엔 카테고리 one-liner 만 노출됨.
  - **라우팅 버그 발견·수정**: 기존에도 `render_digest` 가 `index.html`(루트)과 `archive/{date}.html`
    (하위 폴더)에 같은 HTML 을 복사만 해서 상대링크가 한쪽에서 깨지는 구조적 문제가 있었음 — 이번에
    루트/아카이브 버전을 각각 다시 렌더링하도록 고쳐서 근본 해결(재렌더 테스트로 확인).
  - **보안**: 기존 `render.py` 는 Jinja2 `Template()` 을 autoescape=False 로 썼던 잠재 리스크 있었음
    (RSS/스크레이프 콘텐츠에 `<`/`&` 등이 그대로 삽입될 수 있었음) — 이번에 `Environment(autoescape=True)`
    + `DictLoader` 매크로 구조로 전면 교체하며 같이 고침.
  - **미완료(사용자가 나중에 하기로 함)**: 기존 27주 백필 아카이브는 recap 기능 추가 전 데이터라 헤드라인/
    $ 집계 없음(폴백 텍스트 "Week N digest" + "—" 로 표시됨). `generate_recaps.py` 신규(소급 생성용, API
    키 필요) 작성 완료, 실행은 보류.
  - **부수 발견**: `store.list_digests()` 에 각 다이제스트의 최고-significance 항목 제목(top_title) 서브쿼리
    추가(아카이브 인덱스의 "Top story" 컬럼용). `rerender.py`/`pipeline.py`/`backfill.py` 모두 새 시그니처
    (`total_records`, 카테고리 페이지 호출, recap 저장/조회)에 맞춰 갱신.
- 2026-07-28: **"메인에 옛날 뉴스" 재발 — 진짜 원인 3개 찾아서 수정(런타임 증거 기반)**. 07-28 오전에
  `max_item_age_days: 7` 을 넣었는데도 리드가 5일 전 항목이었음. 코드 리뷰 + 실제 라이브 fetch 로 검증한 원인:
  - **(1) sitemap `<lastmod>` 는 발행일이 아님 (최대 296일 오차)**. Anthropic 은 공식 RSS 가 없어서
    sitemap 스크레이프를 쓰는데, `lastmod` 를 그대로 `published` 로 저장하고 있었음. 실제로는 사이트 리빌드
    타임스탬프여서 옛 글이 "이번 주 발행"으로 위장됨. 라이브 검증 결과: `claude-sonnet-4-5` lastmod 07-22 /
    실제 2025-09-29(296일), `skills` 07-22 / 2025-10-16(279일), `claude-opus-4-5` 07-23 / 2025-11-24(241일),
    `claude-opus-4-8` 07-22 / 2026-05-28(55일). 리빌드 흔적도 확인(07-22T01:13~01:28 사이에 4개 페이지가
    한꺼번에 갱신). 발견 단서는 **버전 역순** — Opus 4.5 가 4.6 보다 늦은 날짜로 찍혀 있었음(불가능).
    → `fetch.py` 에 `_article_published()` 신설: JSON-LD `datePublished` 우선, 없으면 `PostDetail` 헤드라인
    바로 아래 날짜 줄(`<div class="body-3 agate">`) 파싱, 둘 다 실패 시에만 lastmod 폴백.
    JSON-LD 를 먼저 보는 이유: Webflow 계열 페이지는 HTML 맨 앞에 `Last Published` 빌드 시각 주석이 있어서
    "문서의 첫 날짜"를 쓰면 그걸 집음. `_scrape_article_meta()` 반환값이 3-tuple 로 바뀜.
  - **(2) 랭킹 동점 처리가 카테고리 열거 순서로 결정됐음**. significance 0.80 에 4건이 동점이었고
    Python `sort` 가 stable 이라 `CATEGORY_ORDER` 첫 항목(`model_releases`)이 무조건 리드를 차지 —
    같은 0.80 인 당일 $410M 딜이 밀렸음. → `render._flatten_ranked` 정렬 키에 `published` 추가(동점 시 최신 우선).
    **랭킹 rubric(3장) 자체는 안 건드림** — 원래 정의가 없던 동점 처리만 결정론적으로 만든 것.
  - **(3) 모든 RSS 발행일이 머신 UTC 오프셋만큼 밀려 있었음**. `_published()` 가 `time.mktime()` 을 썼는데
    feedparser 의 `*_parsed` 는 이미 UTC struct 이고 `mktime` 은 struct 를 로컬시간으로 해석 → 로컬(UTC-6)에서
    +7h 밀림. (2) 를 고치자 "내일 발행" 항목이 3개 소스에서 튀어나와 발견. CI 는 `TZ=UTC` 라 오차 0 이어서
    안 보였던 로컬 전용 버그. 신선도 컷오프도 7시간 느슨했음. → `calendar.timegm()` 으로 교체.
  - 부수 수정: `_parse_dt()` 가 tz 없는 값(date-only lastmod 등)을 그대로 반환해서 aware cutoff 와 비교할 때
    `TypeError` 로 파이프라인이 죽던 문제 → UTC 로 정규화. (Python 3.9 의 `fromisoformat` 은 3.12 보다
    훨씬 엄격해서 로컬/CI 동작이 갈렸음 — 로컬 3.9.6 / CI 3.12 불일치도 별건으로 남아있음.)
  - **검증**: `--reset` 후 실제 실행(원래 버그가 터졌던 조건 그대로 재현). 결과 114건 수집 → 21건 게시,
    발행일 범위 `2026-07-22~07-28`, 리드 = 당일 "Recursive Superintelligence $410M" (significance 0.9),
    8~10개월 된 Anthropic 모델 글 6건 전부 사라짐. 남은 Anthropic 모델 글은 Opus 5(실제 07-24) 1건뿐.
- 2026-07-28: **코드 리뷰에서 나온 추가 버그 3건 수정**.
  - `rerender.py` 가 **과거 주간 다이제스트를 홈페이지로 발행**하던 문제. `digests.date` 한 컬럼에 일간
    `YYYY-MM-DD` 과 주간 `YYYY-Www` 라벨이 섞여 있고, 텍스트 정렬에서 `'W'`(0x57) > `'0'`(0x30) 이라
    주간 라벨이 모든 일간 날짜보다 위로 올라감 → `is_today = (i == 0)` 이 `2026-W31` 을 집어서
    `index.html` 에 씀. 실측 확인: 옛 정렬 `['2026-W31','2026-W30','2026-W27','2026-07-28']`.
    → `store.label_sort_key()` 신설(주간 라벨을 해당 주 월요일 날짜로 환산)해서 `list_digests()` 를
    시간순 정렬(아카이브 인덱스 순서/미니바도 같이 고쳐짐), `rerender.py` 는 위치가 아니라
    **일간 라벨 패턴으로 최신 일간을 명시 선택**. 일간이 하나도 없으면 `index.html` 은 건드리지 않음.
  - **조용한 날 어제 페이지가 그대로 남던 문제**: 신규 0건이면 `run()` 이 렌더 전에 `return` 해서
    `index.html` 이 어제 내용인데 헤더만 오늘 날짜인 상태로 남았음 → 빈 다이제스트로 렌더 + `record_digest(0)`
    + 아카이브 인덱스 갱신. 실측 검증(두 번째 실행이 자연히 신규 0건): "0 stories" 페이지 정상 렌더.
  - `.github/workflows/daily.yml` 이 **철회된 Vertex AI 서비스계정 인증을 그대로 쓰고 있어서 첫 cron 이
    실패할 상태**였음 → `GEMINI_API_KEY` 시크릿 방식으로 교체(`llm.py` 의 `genai.Client()` 가 자동 인식).
    `git push` 도 pull 없이 밀어서 충돌 위험이 있어 rebase 재시도로 감쌈.
  - ⚠️ 이 과정에서 `Untitled.py`(curl 스크래치 파일)에 **Gemini API 키가 평문으로** 있고 `.gitignore` 에도
    안 걸려 있는 걸 발견 — git init 하면 바로 유출될 상태였음. 사용자가 파일 삭제함(키 재발급 필요).
    이번이 3번째 키 노출(1차 Anthropic, 2차 Gemini, 3차 이 파일) → 비밀값은 `.env` 만 쓰기로 한 규칙 유지.
- **남은 리뷰 지적 사항** (2026-07-29 기준 갱신):
  - **미수정**: 27주 백필 아카이브가 `--reset` 으로 DB 에서 사라져 인덱스에서 접근 불가(HTML 은
    `output/archive/` 에 그대로. 재발 원인은 `--purge-all` 분리로 수정했지만 이미 잃은 데이터는 그대로) ·
    `settings.min_items_fallback` 과 `settings.flag_major_at_top` 이 파싱만 되고 미구현/무효.
  - **해결됨(추가)**: ~~로컬 3.9.6 / CI 3.12 파이썬 버전 불일치~~ ✅ 2026-07-29 로컬 3.12.9 전환 완료.
  - **부분 해결**: `--dry-run` 이 `output/` 을 덮어쓰는 건 여전하지만, DB 기반 렌더로 바뀌면서 이제
    "플레이스홀더 1~2건"이 아니라 "DB 의 오늘자 + 이번 실행분"을 그린다. 신규분 significance 가 0.5
    고정이라 미리보기일 뿐이므로 커밋 전 `git status` 확인은 계속 필요.
  - **해결됨**: ~~`llm.py` 가 `summary: null` 에 크래시하고 배치 하나 실패하면 앞선 배치 결과까지
    전부 날림~~ ✅ · ~~카테고리 상한(6)에 밀린 항목이 `commit_seen` 되어 영구 누락~~ ✅ (이제 seen 에서
    빠져 다음 실행에 재도전하고, `is_published=0`+`drop_reason` 으로 DB 에도 남음). 둘 다 변경로그 참고.
- 2026-07-28: **아카이브 소스 부족 관련 논의**. 사용자가 사이트 확인 중 아카이브에 소스가 하나만 보이는
  것 같다고 지적 → 원인은 버그가 아니라 §9 6개월 백필 당시의 의도된 스코프(블로그/랩 7소스만, arXiv/
  TechCrunch/HN 제외)였음을 재확인. 지금 재백필하지 않고, API 로 접근 가능한 소스가 더 늘어나면 그때
  소스를 확장해서 지난 6개월 아카이브를 다시 만들기로 결정(§5 파킹 아이디어에 추가). 지금은 진행 중인
  작업 없음 — 남은 할일은 §9/§5 참고.
- 2026-07-28: **GitHub 레포 생성 + Actions cron + Pages 자동화 완료**. private repo
  `github.com/ujuappa/ai_news` 생성 후 로컬 `git init` + 첫 커밋 + push(`.DS_Store`,
  `.claude/settings.local.json` 은 로컬 전용이라 `.gitignore` 추가 후 제외). HTTPS push 가 비밀번호
  인증 미지원으로 막혀서 `credential.helper=osxkeychain` 설정 후 사용자가 별도 터미널에서 PAT 로 직접
  인증(토큰은 채팅에 노출 안 시킴). `.github/workflows/daily.yml` 에 Pages 배포 잡 추가 —
  기존 주석은 "branch=main/folder=/output" 를 제안했지만 이건 실제로 불가능(GitHub Pages 브랜치 배포는
  `/root` 나 `/docs` 만 지원, 임의 폴더 불가) → `actions/upload-pages-artifact@v3`(path: output) +
  `actions/deploy-pages@v4` 잡으로 교체(레포 Settings > Pages > Source 도 "GitHub Actions" 로 변경 필요).
  **첫 수동 실행(`workflow_dispatch`) 실패 디버깅**: `ValueError: No API key was provided` —
  `GEMINI_API_KEY` 를 Repository secret 이 아니라 Pages 가 자동 생성한 `github-pages` **Environment**
  secret 으로 등록해서 `environment: github-pages` 를 선언 안 한 `build` 잡에서 안 보였던 것. Repository
  secret 으로 재등록 후 재실행 성공 확인(사용자 확인). (참고: 로그에 뜬 "Node.js 20 deprecated" 경고는
  무관한 러너 인프라 공지, 실패 원인 아니었음.)
- 2026-07-28: **v3(멀티유저 전환) 방향 합의**. 로그인 목적이 "남이 못 보게"가 아니라 **개인화+멀티유저+사내 배포**로 확인됨(회사 인증 = Microsoft 365/Entra ID). 정적 사이트에 인증 붙이는 건 함정으로 판단, 파이프라인을 콘텐츠 백엔드로 두고 앱을 새로 얹기로 결정. 상세는 §10. **지금 착수 항목은 파이프라인↔렌더 분리(데이터를 DB/API로) 하나** — 회사행 확정 전에도 이득이라 이것만 먼저. 코드 미착수, 2026-07-29 이어서.
- 2026-07-29: **첫 cron 자동 실행 성공 확인 + `llm.enrich()` 장애 내성 개편**. 오늘 14:00 UTC 스케줄 실행이
  정상 성공(`digest-bot` 커밋 `digest: 2026-07-29`, 15:51 UTC, 6분53초) — 손 안 대고 돌아간 첫 자동 다이제스트.
  이어서 §"남은 리뷰 지적 사항" 중 llm.py 항목을 처리:
  - **배치별 try/except 격리** — 기존엔 배치 하나가 죽으면 예외가 그대로 올라와서 **앞선 배치의 성공 결과까지
    전부 날아갔음**. 이제 실패 배치만 건너뛰고 해당 아이템은 원문 폴백.
  - **지수 백오프 재시도**(`_call_batch()` 신설) — 배치당 3회, 2s→4s. 레이트리밋/5xx/JSON 잘림 모두 재시도
    대상(잘린 JSON 은 재호출로 복구되는 경우가 많음 — 07-28 thinking_budget 이슈와 같은 계열).
  - **null 가드** — `summary: null` 에 `[:600]` 하다 `TypeError` 로 죽던 것(리뷰 지적 사항)을
    `or summary_raw or ""` 로, `significance` 는 `_as_float()` 신설로 None/문자열/NaN/범위밖 방어
    (`5` → `1.0` 클램프). LLM 이 rubric 범위를 벗어난 값을 주면 랭킹이 통째로 왜곡되므로 클램프까지 포함.
  - **비배열 응답 가드**(`_rows()` 신설) — 단일 객체나 `{"items": [...]}` 래핑은 언랩해서 살리고, 구제
    불가면 `ValueError` → 재시도. 행 중 dict 아닌 건 무시.
  - **`_enriched` 플래그** — 실제로 LLM 판단을 받은 아이템만 `True`.
  - **전량 실패 시 `RuntimeError` → exit 1** — 배치가 전부 죽으면 significance 0.0 짜리 빈 다이제스트가
    조용히 커밋되고 Actions 는 초록불이 됨. 이제 `Run pipeline` 스텝이 실패해서 뒤의 커밋/Pages 스텝이
    아예 안 돎(`if: always()` 없는 것 확인). **부분 실패는 의도적으로 통과** — 하루치를 통째로 버리는 것보다
    일부라도 발행하는 게 낫다고 판단.
  - **`pipeline.py`: `commit_seen` 에서 `_enriched=False` 제외** — 배치 격리를 넣자 새로 생기는 유실 경로.
    실패한 아이템은 significance 0.0 → `min_significance` 0.25 컷에 걸려 안 실리는데, seen-store 에는
    들어가서 **내일 재시도 대상에서 영영 빠짐**. `it.get("_enriched", True)` 로 기본값 `True` — dry-run/
    backfill 경로는 이 키가 없으므로 기존 동작 그대로. (카테고리 상한 6 에 밀린 항목이 `commit_seen` 되는
    건 별개 이슈로 여전히 남아 있음.)
  - **검증**: `genai.Client` 를 가짜로 교체한 시나리오 테스트 24건 전부 통과(정상/null/이상값/비배열/
    백오프 재시도/배치 격리/전량 실패/빈 입력/잘린 JSON). `--dry-run` 도 정상 완료.
    ⚠️ dry-run 이 오늘 cron 이 만든 `output/` 을 1건짜리 렌더로 덮어써서 `git checkout -- output/` 로
    복원함 — 위 "남은 리뷰 지적 사항"의 dry-run 항목이 실제로 물린 사례. 커밋 전 `git status` 확인 필수.
  - `.gitignore`: `boncom-ai-skills-main/`(사내 자료), `.cursor/` 추가.
- 2026-07-29: **`--reset` 을 "seen-store만 초기화"로 변경** (아카이브 히스토리 보존). 기존 `reset_db()` 는
  `digest.db` 파일을 통째로 `unlink()` 해서 `seen` 뿐 아니라 `items`/`digests`/`recaps` 까지 날렸고,
  실제로 그 때문에 27주 백필 아카이브가 인덱스에서 사라진 적이 있음(§"남은 리뷰 지적 사항"). dedup 백엔드를
  바꿨을 때 필요한 건 임베딩 무효화뿐인데 대가가 너무 컸음. → `store.py` 에 `clear_seen()` 신설
  (`DELETE FROM seen`, 지운 행 수 반환), `pipeline.reset_db()` 가 파일 삭제 대신 이걸 호출하고
  "N건 삭제 / 아카이브 M건 보존" 을 출력. DB 전체를 밀어야 하는 경우는 `rm digest.db` 로 안내(별도 플래그는
  안 만듦 — 쓸 일이 드물고 실수 여지만 늘어남). README/CLAUDE.md 의 `--reset` 설명도 갱신.
  **검증**: 실제 DB 를 건드리지 않으려고 `digest.db` 사본에 `config.DB_PATH` 를 물려서 테스트 —
  seen 146→0, `items`/`digests`/`recaps` 는 33/2/8 그대로 유지 확인. DB 파일이 없을 때 새로 만들지 않는 것,
  두 번 호출해도 안전한 것(멱등)도 확인. 실제 `digest.db` 무변경 확인.
- 2026-07-29: **DB 전체 삭제를 `--purge-all` 로 분리** (바로 위 항목에서 "별도 플래그는 안 만듦"이라고
  했던 판단을 뒤집음 — **재백필 때 반드시 필요한 선행 단계**라서 `rm digest.db` 구전 지식으로 두면 안 됨).
  `pipeline.purge_all()` 신설: 삭제 전에 `store.counts()`(신설)로 seen/items/digests/recaps 건수를 보여주고
  **정확히 `yes` 를 타이핑해야** 진행(빈 입력·`YES`·`y` 는 전부 취소 — 27주 아카이브를 날려본 이력이 있어
  기본값을 안전 쪽으로). 스크립트용 `--yes` 로 프롬프트 생략 가능. `--purge-all` 이 `--reset` 보다
  먼저 매칭되게 argv 분기 순서 조정.
  재백필 선행 조건은 세 군데에 박아둠: `backfill.py` 헤더(이유까지 — `save_items` 는 id 기준
  INSERT OR REPLACE 라 소스 구성이 바뀌면 옛 실행 아이템이 남아 아카이브가 섞임), §5 파킹 아이디어의
  재백필 항목, README/CLAUDE.md 실행 블록.
  **검증**: 사본 DB 로 7개 시나리오 — `--reset`(seen 만 0, 파일 유지) / `purge-all`+`yes`(삭제) /
  `no`·빈입력·`YES`·`y`·` yes please`(전부 취소, 데이터 무변경) / `--yes`(프롬프트 호출 자체가 없음을
  input 스텁으로 확인) / DB 부재 시 양쪽 다 파일 생성 없이 안전 종료. 실제 `digest.db` 무변경 확인.
- 2026-07-29: **탈락 아이템도 DB 에 보관 (`is_published`/`drop_reason` 신설)**. 지금까지 `save_items` 는
  게재분만 저장해서 "왜 안 실렸는지"가 어디에도 안 남았음 — §9 의 카테고리 상한(6) 튜닝이 "라이브 며칠
  보고 재평가" 상태로 멈춰 있던 것도 판단 근거 데이터가 없어서였음. 이제 컷에 걸린 아이템도 사유와 함께 저장.
  - **컬럼명 주의**: `items.published` 는 이미 **기사 발행일**(TEXT)로 쓰이고 있어서(fetch/render/backfill
    8곳이 소비, 특히 `render.py:802` 동점 처리 정렬은 07-28 버그수정 지점) 새 불리언은 **`is_published`**
    로 명명 — 같은 테이블 `is_major` 와 작명규칙도 맞음. 날짜 컬럼은 손대지 않음.
  - `store.py`: `SCHEMA` 에 `is_published INTEGER DEFAULT 1` / `drop_reason TEXT DEFAULT ''` 추가(신규 DB용)
    + `_migrate()` 신설(기존 DB용). `CREATE TABLE IF NOT EXISTS` 는 기존 테이블에 컬럼을 안 붙여주므로
    `PRAGMA table_info` 로 확인 후 없는 것만 `ALTER TABLE ADD COLUMN` — 매 `Store()` 마다 도는 멱등 방식.
    기존 행은 DEFAULT 1 로 채워지는데 예전엔 게재분만 저장했으니 의미상 정확함.
  - `save_items(items, digest_date, is_published=True, drop_reason="")` 로 확장. 게재분은 `drop_reason` 을
    강제로 빈 문자열 — `INSERT OR REPLACE` 라 탈락→게재 전이 시 옛 사유가 남는 걸 방지.
  - 읽기 API 는 전부 게재분만: `all_items()`(검색 인덱스 — 사이트에 없는 글이 검색에 뜨면 안 됨),
    `items_for_digest()`(재렌더가 원본과 달라지면 안 됨), **그리고 `list_digests()` 의 `top_title`
    서브쿼리도** — 안 고치면 다른 카테고리에서 상한에 밀린 고significance 항목이 아카이브 인덱스의
    "Top story" 로 뜰 수 있었음. 탈락분 조회는 `dropped_items(digest_date=None)` 별도 신설.
  - `pipeline.py`: `_drop_reasons()` 신설 — 파이프라인이 거른 순서대로 사유 판정
    (`enrich_failed` > `min_significance` > `category_off`(community_takes) > `category_cap`).
    저장은 사유별로 나눠 호출하고, 콘솔에도 "탈락 category_cap 3건, min_significance 5건" 식으로 출력.
  - **검증**: 18개 테스트 통과 — 마이그레이션(기존 33행 전부 `is_published=1`, 3회 재실행 멱등, 기존 컬럼
    보존) / 신규 DB / 세 읽기 API 필터 / `top_title` 이 sig 0.99 짜리 탈락분을 안 집는지 / 게재↔탈락 전이 시
    사유 비워짐 / 사유 판정 4종. 실제 `digest.db` 는 컬럼만 추가되고 33행·seen 146건 그대로.
- 2026-07-29: **`commit_seen` 범위를 "제대로 판정받고 끝난 것"으로 한정**. 직전까지는 `_enriched` 인 것
  전부를 seen 에 넣었는데, 그러면 카테고리 상한에 밀린 항목이 내일 재도전 기회를 못 받음(§"남은 리뷰
  지적 사항"의 그 항목). 이제 **게재분 + `min_significance` 드롭분만** seen 에 넣는다.
  - **넣는 이유**: 게재분은 내일 또 실으면 안 되고, `min_significance` 는 LLM 이 이미 보고 낮게 매긴
    거라 내일 재스코어해도 결과가 같아서 토큰만 낭비.
  - **빼는 이유(=내일 재시도)**: `category_cap` 은 컷을 넘겼는데 자리가 없었을 뿐이고,
    `enrich_failed` 는 판정 자체를 못 받았고, `category_off`(community_takes)는 v1 에서 통째로 꺼둔 것.
  - **비용 트레이드오프**: 캡 드롭분은 내일 다시 엔리치되므로 LLM 토큰을 한 번 더 쓴다. `max_item_age_days`
    7일 컷이 있어서 무한 반복은 아님(최대 7일). 자리가 나면 게재되고 그때 `INSERT OR REPLACE` 로
    `is_published=1` 로 갱신됨(전이 테스트 완료).
  - ⚠️ `category_off` 는 지금 community_takes 소스가 전부 비활성이라 0건이지만, 카테고리를 켜지 않은 채
    소스만 살리면 매일 재엔리치되며 토큰을 태운다. 그때 재검토할 것.
  - **검증**: `pipeline.run()` 을 실제로 태우는 테스트 7건 통과(fetch/dedup/LLM/render 만 스텁, 네트워크·
    API 미사용). 캡 2로 낮춰 category_cap 을 강제한 뒤 seen 에 게재분 2건 + 저의미 1건만 들어가고
    캡 드롭 2건·LLM 실패 1건·카테고리 OFF 1건은 빠지는 것, 그럼에도 탈락 5건 전부 `drop_reason` 과 함께
    `items` 에 남는 것 확인.
- 2026-07-29: **렌더를 DB 기반으로 전환 — "같은 날 재실행이 index.html 을 잘라먹는" 버그 근본 수정**.
  증상: 오늘 cron 이 11건짜리 페이지를 만든 뒤 같은 날 파이프라인을 다시 돌리면 index.html 이 1~2건짜리로
  덮였음. 원인은 렌더가 **그 실행분(`clustered`)만** 그렸기 때문 — cross-day dedup 이 오전에 이미 실은
  항목을 "본 것"으로 걸러내니 두 번째 실행의 `clustered` 는 신규 몇 건뿐이고, 그걸로 페이지를 통째로
  다시 씀. 세션 중 `--dry-run` 을 돌릴 때마다 `git checkout -- output/` 로 복원해야 했던 것도 이 버그.
  - **수정**: `_todays_pool()` 신설 — 오늘의 후보 풀 = DB 의 오늘자(게재분+탈락분) + 이번 실행분
    (id 충돌 시 이번 실행이 우선). **DB 를 하루치의 단일 진실**로 삼고 매 실행이 누적 전체를 다시 랭킹.
    부수 효과로 카테고리 상한이 실행 단위가 아니라 **하루 누적 기준**으로 정확히 적용됨(전에는 오전 6건 +
    오후 6건 = 12건이 될 수 있었음).
  - **조용한 날 별도 경로 제거**: 신규 0건일 때 빈 다이제스트를 렌더하던 early-return 을 없앰. 이제 같은
    경로를 타면서 DB 의 오늘자가 그대로 다시 나온다(예전엔 조용한 재실행이 페이지를 비웠음). 07-28 에
    "어제 페이지가 오늘인 척 남는" 문제로 넣었던 로직인데, DB 기반이 되면서 자연히 해결됨.
  - **중복 제거**: `pipeline._rank_and_cap` / `rerender._grouped` / **`backfill._rank_and_cap`**(세 번째
    사본, 주석에 "pipeline 과 동일 로직"이라고 적혀 있었음)을 `render.group_by_category(items, cap=None)`
    하나로 합침. 정렬 키에 `published` 동점 처리를 추가 — `render._flatten_ranked` 는 07-28 에 이미
    고쳤는데 이 셋은 significance 만 봐서 동점 시 캡에 누가 남는지가 리스트 순서에 좌우됐음.
  - **majors 를 게재분 기준으로 변경**: 전에는 `ranked_pool`(캡 적용 전)에서 뽑아서, 캡에 밀린 major 가
    상단 배너에만 뜨고 DB 는 `is_published=0` 인 불일치가 있었음(검색·rerender 결과와도 어긋남).
  - **`store.unsee()` 신설**: 오전에 실렸다가 오후 고득점에 밀린 항목은 이미 seen 에 있어서, 지워주지
    않으면 캡 드롭인데도 내일 재시도를 못 받음. 테스트로 실제 재현돼서 추가함.
    `commit_seen` 추가 대상은 이번 실행분으로 한정 — DB 에서 읽은 항목엔 `_emb` 가 없어서 넣으면
    임베딩 없는 seen 행이 되어 cross-day 유사도 비교가 죽는다.
  - **검증**: 회귀 테스트 9건 통과(fetch/LLM/render 만 스텁, dedup 은 진짜 로직 + 직교 원핫 임베딩).
    1회차 5건 → 2회차 신규 1건만 들어와도 6건 유지 → 3회차 신규 0건에도 6건 유지 → 4회차 고득점 2건
    추가 시 누적 기준 캡 6건 유지 + 밀린 2건 `category_cap` 기록 + seen 에서 제거. `rerender.py` 실DB
    사본으로 스모크(11+22=33건, index title 일치). 실제 `--dry-run` 결과가 **"1 items" → "13 items
    (신규 2 + DB 11)"** 로 바뀐 것 확인.
- 2026-07-29: **렌더 버그 4종 일괄 수정**.
  - **`_annotate` 멱등화**: `_source_line_name()` 이 접미사가 붙은 `source_name` 을 다시 입력으로 써서
    같은 dict 을 두 번 annotate 하면(홈에서 한 번, 카테고리 페이지에서 또) `TechCrunch (+1 more) (+2 more)`
    처럼 누적됐음. 숫자가 커지는 이유는 접미사 붙은 이름이 `cluster_sources` 의 어떤 값과도 안 맞아서
    자기 자신까지 others 에 세어졌기 때문. → 원본을 `_source_base` 에 보존하고 항상 거기서 계산.
    (멀티소스 클러스터가 아직 안 생겨서 눈에 안 띄었을 뿐, 호출 경로상 이미 매번 두 번씩 돌고 있었음.)
  - **`render_archive_index` 정렬**: 볼륨 미니바용 `ordered_asc` 가 `d["date"]` 텍스트 정렬이라
    주간 라벨이 뒤로 밀리고(같은 'W' > '0' 문제), 마지막 원소를 '최신'으로 강조하는 것도 엉뚱한 걸 집었음.
    → `store.label_sort_key` 사용(`list_digests` 와 동일 키). 검증에서 `2026-W31` 이 `2026-07-27` 로
    환산돼 `2026-07-28` 앞에 오는 것까지 확인(처음엔 내 기대값이 틀렸고 코드가 맞았음).
  - **조용한 날 카테고리/검색 페이지**: 별도 조치 불필요 — 직전 커밋에서 early-return 을 없앤 것으로
    이미 해결돼 있었음. 회귀 테스트로 확인만 함(신규 0건 실행 후 7개 페이지 전부 재생성 + 내용 동일).
  - **`majors` 죽은 파라미터 제거**: `render_digest`/`render_archive_digest` 가 받기만 하고 본문에서
    한 번도 안 썼음. SIGNAL 디자인의 '상단 major 배너'용이었는데 07-27 Modernist 개편에서 significance
    플랫 랭킹으로 바뀌며 배너가 사라진 뒤 잔재로 남은 것. 파라미터와 3개 호출부의 `majors` 계산을 삭제.
    **`is_major` 자체는 유지** — 항목별 `MAJOR` 태그로 실제 렌더되고 DB/LLM 출력에도 쓰임.
    부작용으로 `settings.flag_major_at_top` 이 완전히 무효가 됨 → §"남은 리뷰 지적 사항"의
    `min_items_fallback` 옆에 같이 기재(설정은 파싱만 되고 동작 없음).
  - 부수: `render_category_page` 정렬도 `(significance, published)` 로 통일 — 홈과 카테고리 페이지에서
    동점 항목 순서가 갈리던 것.
  - **검증**: 23건 통과(멱등화 5 · 아카이브 정렬 6 · majors 시그니처 3 · 조용한 날 9). 추가로 `rerender.py`
    실DB 사본 재렌더 후 전체 HTML 을 `more) (+` 로 스캔해 중복 접미사 0건 확인, 실제 `--dry-run`(14건)
    출력물도 동일 스캔 통과.
- 2026-07-29: **source-health 배지의 가짜 경고 제거 — `fetch_all` 이 소스별 `(fresh, raw)` 반환**.
  `health[src.id]` 가 **신선도 컷 통과 후** 개수였던 탓에, 월간 발행 소스(Ahead of AI)가 "이번 주 글
  없음"이라는 정상 상태로 매 실행 ⚠️ 배지를 달았음. 진짜 이상(피드 죽음/구조 변경)과 구분이 안 되니
  배지가 의미를 잃는 상태였음 — 07-28 메모에도 "월간 주기라 0건이 맞음"이라고 적어두고 넘어갔던 그 건.
  - `fetch.fetch_source_counted()` 신설: `(신선도 컷 통과분, 컷 이전 수집 개수)` 반환. 기존
    `fetch_source()` 는 리스트만 돌려주는 얇은 래퍼로 남김 — `backfill.py` 호출부 무변경.
  - `fetch_all()` 반환이 `{source_id: int}` → `{source_id: (fresh, raw)}`. 로그에도
    `ahead_of_ai 0 items (피드 20건 중 20건 기간 밖)` 처럼 컷에 걸린 수를 표시해서, 배지가 안 떠도
    무슨 일이 있었는지 보이게 함.
  - `pipeline._health_warnings()` 는 이제 **`raw == 0` 일 때만** 경고. 피드 파싱 실패·예외도 `(0, 0)`
    이라 그대로 경고 대상으로 남음.
  - **검증**: 11건 통과 — 경고 판정 5종(죽은 피드만 경고 / 월간 소스 제외 / 정상 제외 / 전부 정상 /
    전부 죽음), `fetch_source_counted` 의 fresh·raw 분리(합성 RSS 로 1·3·30·60일 전 4건 → raw 4,
    fresh 2), 컷 없을 때 fresh==raw, `fetch_source` 리스트 반환 유지, 빈 피드·예외 모두 `(0,0)`.
    실제 `--dry-run` 에서 **`⚠️ 소스 이상: Ahead of AI` 가 사라진 것** 확인.
- 2026-07-29: **Python 3.12 를 요구사항으로 명시 + `backfill.py` 에 하드 게이트**. 로컬 3.9.6 / CI 3.12
  불일치가 §"남은 리뷰 지적 사항"에 남아 있었는데, 재백필 계획이 있어서 먼저 정리. 3.9 에서 실제로 깨지는
  형식을 측정: `+0000`(콜론 없는 오프셋) · `.12`/`.123456789` 소수초 · `20260729T120000Z` 4종이
  `ValueError` (`Z` 접미사·공백 구분자·날짜만은 3.9 에서도 OK — 이미 `.replace("Z","+00:00")` 처리 중).
  - **영향이 백필에서 특히 나쁜 이유**: `_parse_dt` 가 None 을 주면 (1) `fetch_backfill_items` 의 since
    필터에서 아이템이 **통째로 드롭**되고, (2) 살아남아도 주 버킷이 `now()` 로 폴백돼 **엉뚱한 주**에
    들어간다. 조용히 망가진 아카이브가 나옴. 일간 파이프라인은 파싱 실패를 통과시켜서(`or cutoff`)
    영향이 작다.
  - `backfill.py._require_py312()` 신설 — 3.12 미만이면 네트워크 요청 전에 `sys.exit(1)`. 경고가 아니라
    하드 게이트로 둔 이유는 실패가 조용해서 사후에 알아채기 어렵기 때문. 3.9 에서 exit code 1 확인.
  - README 셋업을 `python3.12 -m venv .venv` + `python -V` 확인으로 갱신, CLAUDE.md 실행 블록도 동일.
  - **부수 발견**: README 셋업이 **07-28 에 철회된 Vertex AI 서비스계정 인증**을 그대로 안내하고 있었음
    (`GOOGLE_GENAI_USE_VERTEXAI`/`GOOGLE_APPLICATION_CREDENTIALS`). CLAUDE.md·변경로그와 모순 →
    `echo "GEMINI_API_KEY=..." > .env` 방식으로 수정.
  - **완료**: 사용자가 python.org 설치본으로 3.12.9 설치. `.venv` 재생성(기존은 `.venv.bak` 백업 후
    검증 완료하고 삭제) + `pip install -r requirements.txt` + `--dry-run` 통과. 3.9 에서 실패했던
    날짜 형식 4종이 3.12 에서 전부 OK, `_require_py312()` 게이트도 통과 확인.
- 2026-07-29: **3.12 전환에서 전 소스 0건 사고 — `feedparser.parse(url)` 을 requests 경유로 교체**.
  새 venv 로 첫 `--dry-run` 을 돌리자 11개 소스 중 10개가 0건. 유일하게 살아남은 `anthropic` 이
  `parse: sitemap`(=`requests.get`) 경로라는 게 단서였음. 원인은 feedparser 버전이 아니라
  **python.org macOS 설치본의 CA 인증서 미설치** — `feedparser.parse(url)` 은 urllib 으로 받아서
  파이썬 기본 SSL 컨텍스트를 쓰는데 CA 스토어가 비어 있어 전부 `CERTIFICATE_VERIFY_FAILED`.
  `requests` 는 certifi 를 쓰므로 영향 없었음.
  - 공식 해법인 `/Applications/Python 3.12/Install Certificates.command` 는 site-packages 가 root
    소유여서 sudo 없이는 실패(아무것도 변경 안 됨). 사용자와 상의해 **머신 설정 대신 코드를 고치는 쪽**
    선택 — 07-29 오전에 이미 권고했다가 "잘 돌고 있어서 보류"했던 그 수정.
  - `fetch._parse_feed()` 신설: `requests.get(url, headers=_UA, timeout=20)` 으로 받아 bytes 를
    `feedparser.parse()` 에 넘김. `fetch_source_counted` 와 `fetch_paginated_feed`(백필용) 양쪽 교체.
    지수 백오프 재시도 3회(2s→4s)도 함께. **한 번에 해결된 것 4가지**:
    (1) SSL — 머신 CA 설정에 의존하지 않음, (2) **타임아웃 부재** — urllib 기본 소켓 타임아웃이 None
    이라 서버가 응답을 안 주면 무한 대기(CI 는 job 한도까지 태움), (3) UA 불일치 — 이제 sitemap 경로와
    같은 `_UA`, (4) HTTP 에러 비가시성 — 403/429/404 가 예외로 드러남(전엔 빈 `entries` 라
    "새 글 없음"과 구분 불가).
  - **임베딩 호환성 확인**: sentence-transformers 5.1.2→5.6.1, torch 2.8→2.13, numpy 2.0→2.5 로
    크게 올라가서 `seen` 의 기존 임베딩 146건이 무효화될 위험을 점검. `.venv.bak`(구 환경)과 새 환경에서
    **동일 텍스트를 임베딩해 비교 → 코사인 1.000000**(4/4). 저장된 벡터 그대로 유효, dedup 임계값
    0.83 에 영향 없음. (첫 시도에서 0.53~0.89 가 나온 건 내 테스트 실수 — `seen` 에는 title 만 저장되는데
    `dedup_batch` 는 `title + summary_raw` 를 임베딩하므로 애초에 다른 입력을 비교했던 것.)
  - **검증**: `_parse_feed` 단위 8건(실제 피드 SSL 통과 / 타임아웃 3회 시도 6초 종료 / 404 가 HTTPError /
    실패 소스는 `([], 0)` 로 흡수돼 파이프라인 생존). `--dry-run` 은 11소스 109건 정상 수집으로 복구,
    가짜 배지 없음, cross-day 신규 8건 → 오늘 후보 19건(신규 8 + DB 11) 렌더.
- 2026-07-29: **6개월 아카이브 재생성 완료 (§5 재백필 항목 실행)**. `--reset` 으로 DB 에서 사라졌던
  27주 아카이브를 되살림. `--purge-all` 은 **하지 않음** — 아침에 "재백필 전 필수"로 문서화했지만 그건
  주간 라벨이 이미 DB 에 있을 때(옛 실행 잔재가 섞이는 경우) 이야기고, 지금은 주간 라벨이 전부 지워져
  섞일 대상이 없었음. 덕분에 오늘자 일간 다이제스트와 `seen` 146건을 보존한 채 진행.
  - **결과**: items 33→**400**, digests 2→**45**(주간 43 + 일간 2), recap 헤드라인 1→**45**,
    검색 인덱스 33→**400**건(요약 400/400), 고립 페이지 **132→6**개. `seen` 146건 무변경,
    **오늘 홈페이지 11건 무영향**(07-29 항목이 전부 techcrunch/arxiv/hn 이라 백필 7소스와 안 겹침).
    예측대로 07-28 일간만 22→15건으로 얇아짐(7건이 W31 주간으로 이동 — 소실 아니고 재배치).
  - ⚠️ **`gemini-2.5-flash-lite` 가 404 로 사라짐**("no longer available to new users"). 첫 시도가
    이걸로 실패했는데 **오늘 아침 넣은 전량 실패 `RuntimeError` 가 exit 1 로 막아서 DB 오염 0** —
    없었으면 43주치가 요약 없이 significance 0.0 으로 조용히 저장됐음. 안전장치가 실제로 값을 했음.
  - **`BACKFILL_MODEL` → `gemini-3.1-flash-lite`**. 후보를 `llm.enrich()` 실제 경로로 검증:
    `gemini-3.5-flash-lite`/`gemini-flash-lite-latest` 는 `thinking_budget=0` 을 400 으로 거부
    (**Gemini 3.5 계열은 thinking 비활성화 불가** — 일간 `gemini-2.5-flash` 는 아직 허용되지만
    2.5 가 같은 식으로 막히면 `llm.py` 의 `thinking_config` 를 조건부로 바꿔야 함. 미리 알아둘 것).
    변별력도 8건 샘플로 확인: 홍보성/채용 0.1~0.2 vs 주요뉴스 0.9~1.0, 표준편차 0.373(2.5-flash 0.352).
  - **`generate_recaps.py` 는 no-op** — `backfill.py` 가 주별로 `generate_recap()` 을 인라인 호출하므로
    (`backfill.py:110`) 45/45 가 이미 채워져 있었음. 이 스크립트는 recap 기능 추가 **전에** 만들어진
    아카이브용이라, 앞으로도 backfill 직후엔 돌릴 필요 없음.
  - **알려진 잔여 사항**: 6개월 창(2026-01-30) 밖 16주가 섞임(2023: 4주, 2024: 2주, 2025: 10주.
    2026 은 27주로 원본과 일치). 원인은 `fetch_backfill_items` 가 sitemap 소스를 `lastmod` 로 필터하는데
    07-28 에 고친 `_article_published` 가 **실제 발행일**(훨씬 오래됨)을 추출하기 때문. 날짜 자체는
    정확해서 **사용자 판단으로 그대로 둠** — 아카이브 인덱스 범위를 1~2년으로 늘릴 예정이라 무해.
    남은 고립 6개(`2026-07-27`, `2026-W05`+카테고리 4개)는 데이터가 사라진 옛 실행의 잔재.
  - **검증**: 크롤 13페이지 깨진 링크 0, 주간 헤드라인 정상(예: `2026-W24` "Anthropic Fable 5 pulled as
    OpenAI files for IPO" / $150M), 검색 인덱스 400건 파싱 확인(2023-W10~2026-W31).
    `--dry-run` 회귀 통과. 백필 전 `digest.db`/`output/` 은 스크래치패드에 백업.
- 2026-07-29: **`catch_missed_news`(Gemini Grounding) 가 매번 400 으로 죽고 있던 것 수정**.
  `d3afe61`("expanding news sources 1")에서 추가된 기능인데, 검증해보니 **한 번도 동작한 적이 없었음** —
  `tools=[{"google_search": {}}]` 와 `response_mime_type="application/json"` 을 함께 주면 API 가
  `400 Tool use with a response mime type: 'application/json' is unsupported` 로 거부한다.
  try/except 로 감싸여 있어 파이프라인은 안 죽고 **조용히 빈 리스트만 반환**하고 있었음.
  - `response_mime_type` 제거. JSON 강제를 못 쓰는 대신 프롬프트로 요구하고, 오늘 고친 `_parse` 가
    앞뒤 산문·코드펜스를 걷어낸다(실측 5/5 파싱 성공. 응답이 ```json 펜스로 오는 경우가 절반).
  - `_parse` 보강: 산문 안에 괄호가 있으면(`"(note: ...)"` 같은) 첫 시도가 실패하고 그대로 포기했음 →
    아직 건진 문서가 없으면 한 글자씩 밀며 계속 훑도록 수정.
  - **URL 검증 추가(`fetch.resolve_url`)**: grounding 이 주는 URL 이 두 가지로 망가져 있었음 —
    (1) `vertexaisearch.cloud.google.com/grounding-api-redirect/...` 불투명 리다이렉트,
    (2) **모델이 지어낸 404 URL**(실측으로 cbsnews.com 링크 하나가 404). 리다이렉트를 끝까지 따라가
    최종 주소로 바꾸고, 도달 불가면 아이템을 버린다. id 해시도 최종 URL 기준이라 cross-day 안정.
    HEAD 를 막는 사이트가 있어 GET(stream) 폴백.
  - 재시도 3회 추가(간헐적 빈 응답 관측). 실패해도 예외 대신 로그+빈 리스트 — 보조 경로라 하루치를
    통째로 날릴 이유가 없음.
  - 방어 보강: `category` 가 유효값이 아니면 `tools_products` 로, `summary_raw` 없으면 title 로 채움
    (`llm._payload` 가 두 키를 필수로 읽어서 없으면 `KeyError` 로 파이프라인이 죽음).
  - **검증 10건**: `resolve_url` 4종(정상/404/없는 도메인/비-URL) + 실제 grounding 호출에서
    리다이렉트 URL 0건·전 URL 도달 가능·`enrich` 통과. 실행 중 환각 URL 1건이 실제로 걸러짐.
  - **함께 확인한 것**: `gnews_ai` 소스는 코드 문제 없음 — 로컬에서만 실패하는데 원인은 gnews 가
    내부적으로 `feedparser.parse(url)` 을 써서 **python.org 파이썬의 CA 인증서 부재**에 걸리는 것
    (`object has no attribute 'status'`). `SSL_CERT_FILE` 을 certifi 로 지정하니 25건 정상 수집.
    CI(Linux)는 영향 없음. `trafilatura` 본문 추출도 정상(3000자).
    ⚠️ 다만 gnews 키워드가 넓어(`Artificial Intelligence OR Large Language Models`) 노이즈가 많음
    (예: "Academic Orthopaedic Surgeons Prefer Peer-Reviewed Guidelines"). 매일 25건을 LLM 에
    태우는 비용 대비 효용은 며칠 관찰 후 재평가할 것.

- 2026-07-30: **본문 추출 순서 수정 + `full_text` 옵트인 + 그라운딩을 비치명 경로로 격리**.
  어제 확장(`d3afe61`)에서 `_extract_full_text` 가 `fetch_source_counted` 의 엔트리 루프 안,
  즉 **신선도 컷 앞**에 있었음 → 소스 12개 x 25건이면 매 실행 최대 300건을 받아서 대부분 몇 초 뒤
  폐기. 실측으로 수집 단계만 **92초**였음.
  - `fetch.py` 를 수집 -> `_apply_cutoff` -> `_fill_full_text` 순으로 재배치. 컷 로직은
    `_apply_cutoff` 로 빼서 중복 제거. 추출 호출부가 4곳에 흩어져 있던 것을 한 곳으로 모음.
  - **`full_text` 플래그 신설**(`config.Source`, `sources.yaml`, 기본 false). 지금은
    `techcrunch_ai` 만 true — 피드가 앞 몇 문장만 잘라 주는 소스라 효용이 확실. arXiv 는 RSS 에
    초록 전문이 이미 있어 이득 없고, `hn_ai` 는 링크 대상이 임의의 외부 사이트라 결과가 들쭉날쭉.
    (부수 효과로 `summary_raw` 800->3000자 = LLM 입력 토큰 약 3.75배도 소스 1개로 한정됨)
  - `backfill.py` 는 `full_text=False` 고정 — `max_entries=1000` 이라 켜져 있으면 소스당 수천 건 요청.
  - **`_extract_full_text` -> `extract_full_text`(공개)**. `pipeline.py` 가 남의 모듈 private 함수를
    호출하고 있었음.
  - **그라운딩을 `_grounding_items()` 로 분리하고 전체를 try/except 로 감쌈**. 기존 코드는 보조
    경로인 grounding 아이템에 `llm.enrich` 를 그대로 재사용했는데, `enrich` 는 **전량 실패 시
    RuntimeError** 를 던지는 게 정상 동작이다(조용한 빈 다이제스트 방지). grounding 은 보통 2~3건
    = 배치 1개라, 그 배치 한 번 실패가 "본 강화는 이미 성공했는데 하루치 전체 실패"로 번질 수 있었음.
    본 경로의 시끄러운 실패는 그대로 두고 보조 경로만 격리.
  - **검증**: `--dry-run` 이 **26.2초**(수집 92초 -> 전체 26초), 수집 아이템 수는 111건으로 동일
    (재배치로 잃은 항목 없음). `git status` 는 소스 파일만 변경, `digest.db` 무변경.
  - **오늘 cron 실패 원인은 특정 못 함**: `gh` 미설치 + 프라이빗 레포라 Actions 로그를 못 봄.
    로컬에서 검증 가능한 것은 전부 정상이었음 — 의존성 해석(`pip check`), 수집 11소스 111건,
    API 키 헬스체크, `catch_missed_news` 실제 호출(2건 반환), 커밋 대상 경로(`digest.db`/`output/`)가
    tracked 이고 gitignore 에 안 걸림. 위 grounding 격리가 가장 유력한 후보였으므로 그것을 고쳤고,
    다음 실행이 또 실패하면 Actions 로그의 실패 스텝을 봐야 함.
- 2026-07-30: **`gnews_ai` 비활성 + 정리**. gnews 는 (1) RFC 822 날짜를 `_norm_date` 가 못 읽어
  `published=""` → 7일 컷을 통째로 우회, (2) `news.google.com` 리다이렉트 URL 이 그대로 저장되는
  두 버그가 남아 있어 `enabled: false`. 로컬 `NetworkError` 는 **gnews 버그가 아니라** CA 인증서
  문제였다는 07-29 결론을 `sources.yaml` 주석에 명시해 뒀음(오진 방지).
  - 삭제: `boncom-ai-skills-main/`(916K), `__pycache__/`(188K), `.DS_Store`,
    그리고 `digests` 행이 없는 고아 HTML 6개(`2026-07-27.html`, `2026-W05.html` + W05 카테고리 4개).
    아카이브 인덱스에서 도달 불가였던 파일들. 228 -> 222개.
  - **문서 드리프트 정리**: `requirements-lite.txt` 는 존재하지 않는데 README/CLAUDE.md 가 참조하고
    있었음. `dedup.embed()` 가 `sentence-transformers` 를 하드 의존해서 그 패키지만 빼면 임포트에서
    죽으므로, 파일을 만드는 대신 언급을 없애고 "코드를 먼저 갈아끼운 다음 의존성을 줄이는 순서"라고
    README '확장 포인트' 에 명시. README 배포 절차의 스테일 시크릿(`GCP_SERVICE_ACCOUNT_KEY` 등
    Vertex AI 방식)도 `GEMINI_API_KEY` 하나로 정정 — 워크플로는 이미 그것만 쓴다.
  - **계획서의 `digests.item_count` 오류 건은 실제로는 정상**이었음. 2026-07-28 은 이미
    `item_count=15` 이고 `items` 의 `is_published=1` 개수도 15. 45행 전수 대조에서 불일치 0건이라
    수정할 게 없었음(계획 작성 시점의 오측정으로 보임).

- 2026-07-30: **첫 성공 실행 후 라이브 점검 — 실제로 두 가지가 사이트에 나가 있었음**.
  수동 실행(`f974ea1`)은 성공했고 게재 20건. 탈락 사유 데이터도 **0건 -> 83건**(`category_cap` 66)
  으로 처음 쌓여서 캡 튜닝 근거가 생겼다(캡 6 기준 게재분의 3배를 버리는 중 — 며칠 더 보고 판단).
  - **[사고 1] 같은 스토리가 하루에 두 번 게재됨**. grounding 이 같은 사건을 제목만 다르게
    두 번 물어옴("More than 1,100 employees at OpenAI, Anthropic..." / "1,100 AI Workers Ask...").
    계획서의 "나중에 볼 것" 항목이 예상보다 빨리, 그리고 **cross-day 가 아니라 같은 날**
    터진 것 — 15:52 와 16:35 두 실행에서 각각 들어왔고, grounding 아이템은 `dedup_batch`
    **뒤에** 합류해서 `_emb` 가 없으니 seen 비교가 URL 완전일치로 퇴화해 못 걸렀다.
    (seen 에 임베딩 NULL 행 3개 = grounding 3건으로 확인)
  - **[사고 2] gnews 를 껐는데도 그날 아침 수집분 25건이 DB 에 남아 계속 재랭킹됨**. 그중 1건이
    실제 게재(블랭크 날짜 + `news.google.com/rss/articles/...` 불투명 URL). `_todays_pool` 이
    매 실행 DB 를 다시 읽는 구조라 "소스를 끈다"가 "이미 들어온 것도 사라진다"를 의미하지 않음.
  - **수정**: (a) `dedup.drop_similar_to()` 신설 — `drop_cross_day` 가 DB 를 상대한다면 이건
    같은 실행 안의 다른 리스트를 상대. `_grounding_items` 가 **enrich 앞에서** `dedup_batch` ->
    `drop_similar_to`(이번 실행분) -> `drop_cross_day`(최근 14일) 3단을 거치게 함. 중복이면
    LLM 호출도 아끼고, 무엇보다 `_emb` 가 생겨서 seen 에 제대로 쌓인다.
    (b) `_todays_pool(disabled_ids=...)` — sources.yaml 에서 꺼진 소스의 DB 잔여분은 풀에서 제외.
    sources.yaml 에 없는 id(`gemini_grounding`)는 판단 대상이 아니라 통과.
  - **임계값 비대칭 도입(`grounding_threshold: 0.78`)**. 실측해보니 문제의 두 건은
    **cos 0.8116** 이라 0.83 으로는 애초에 못 잡는다(제목만: 0.7900). 본 코퍼스 임계값을 낮추는 건
    07-29 에 "0.80 은 오병합" 으로 이미 기각했으므로, **grounding 신규성 판정에만** 0.78 적용.
    비대칭이 안전한 근거: 본 코퍼스에서 임계값을 낮추면 서로 다른 스토리가 병합되는 복구 불가
    오류지만, grounding 은 "있는 것 같으면 안 넣는다"라 최악이 보조 1건 누락.
    회귀 테스트로 확인 — 0.83 이면 사고 재현(통과 1건), 0.78 이면 차단(통과 0건).
  - **데이터 정리**(백업 후 수행): gnews 25건 삭제(items) + seen 11건, grounding 중복 1건 삭제,
    `digests.item_count` 재계산(07-30 20->18, W31 12->9), seen 의 NULL 임베딩 2건 소급 계산.
    `rerender.py` 로 재렌더 — 출력물에 `news.google.com` 0건, 중복 0건 확인.
  - W31 카운트가 어긋나 있던 건 `save_items` 의 `INSERT OR REPLACE` 때문. 과거 주간에 있던
    스토리가 오늘 다시 수집되면 같은 id 로 덮여 `digest_date` 가 오늘로 바뀌고 그 주 아카이브에서
    조용히 빠진다. 지금은 "최신 등장일로 이동"이라 치명적이진 않지만 알고 있을 것.
  - ⚠️ **남은 품질 이슈**: 이번 grounding 3건 중 2건의 출처가 `buildfastwithai.com`,
    `unrot.co` 같은 **뉴스 라운드업/콘텐츠팜**이었다(원 출처가 아님). 중복도 여기서 나왔다.
    임계값으로 풀 문제가 아니라 grounding 프롬프트에 1차 출처 선호를 넣거나 도메인 차단
    목록이 필요함. 다음 후보 작업.

## 11. 소스 확장 및 AI 그라운딩 (2026-07-29)

파이프라인의 뉴스 수집을 더욱 견고하게 만들기 위해 구조를 추가 확장함:

- **Full-Text Extraction**: 단순 RSS Snippet(TechCrunch 등)의 한계를 극복하기 위해 `trafilatura` 를 도입. `<description>` 대신 기사 본문 전체를 긁어와(3000자 제한) LLM이 더 풍부한 요약을 생성하도록 개선.
  → **2026-07-30 수정**: 전 소스 무조건 추출이 아니라 `full_text: true` 옵트인 + 신선도 컷 통과분 한정으로 바뀜(현재 `techcrunch_ai` 만). 위 변경로그 참고.
- **GNews 통합**: `gnews` 라이브러리를 추가하여, `sources.yaml` 에 `parse: gnews` 로 키워드(예: "Artificial Intelligence OR Large Language Models") 기반 뉴스 검색이 가능해짐.
  → **2026-07-30: `enabled: false`** (날짜 파싱/리다이렉트 URL 버그 2건 미해결). `sources.yaml` 주석에 재활성화 조건 기록.
- **Gemini Search Grounding**: `llm.py` 에 `catch_missed_news()` 를 추가, Gemini 의 네이티브 Google Search (Grounding) 도구를 사용해 기존 파이프라인이 놓친 주요 뉴스를 찾아와 보강함.

### Phase 2b: Expanded Curated Sources (보류됨)

당장 추가하지 않고 다음 단계로 파킹된 아이디어들:
- Substack 뉴스레터 자동화 (현재 `import_ai` 는 단일 피드로 동작 중이지만 더 확장)
- Reddit (`r/LocalLLaMA`, `r/MachineLearning`) 재활성화 및 트렌드 파악
- YouTube (`youtube-transcript-api`) 연동을 통한 기술 심층 분석 영상 요약
