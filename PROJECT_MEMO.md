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
- [x] **소스 헬스 모니터링** — 구현 완료(`pipeline._health_warnings`: raw==0 인 소스 이름을 렌더로
  넘겨 배지로 표시). 체크박스만 안 지워져 있었음(2026-07-31 확인).
- [x] **과거 다이제스트 아카이브 + 검색** — 구현 완료. `output/archive/` 47 다이제스트 +
  `search.html`(442건 전체 인덱스를 인라인 JSON 으로 임베드 — `file://` CORS 회피).
  ⚠️ **단 아카이브 인덱스가 최근 6개만 링크하고 나머지는 "+41 earlier digests" 죽은 텍스트다**
  → §13 T3.2 에서 마무리.
- [ ] **다이제스트를 RSS로도 출력** — 나중에 리더/이메일 연동이 공짜가 됨. → §13 T3.4(선택).
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
- [ ] **논문 피드 3종 재평가 (기한: 2026-08-04 경, 누적 후보 100건 시점)** ← **다음 작업**
  실제 실행에서 `hf_daily_papers` 0/25 (최고 sig 0.45), `arxiv_lg` 1/50. 논문은 뉴스 rubric 과
  축이 달라 구조적으로 하한을 못 넘는다. **사용자 결정으로 며칠 더 관측 후 판정** —
  판정 쿼리와 컷 기준은 변경로그 2026-07-31 마지막 항목에 박아둠. **이걸 정한 뒤에 하한을 손댄다.**
- [ ] **카테고리 상한/하한 튜닝** — 2026-07-31 실측 결과 **상한(6)은 정상 작동, 진짜 문제는
  research 하한 0.55**. significance 가 격자값(0.05/0.10 단위)이라 0.55 는 LLM 이 실제로 자주 내는
  값 위에 놓여 가장 불안정한 자리다. 다만 위 논문 피드 결정이 분포를 바꾸므로 **그 다음에** 손댄다.
- [ ] ~~**카테고리 상한(6) 튜닝**~~ (위 항목으로 대체) — 백필(주간 버킷)로 확인해보니 바쁜 주(W28/W30)엔 4개 카테고리 중 3개가
  정확히 6건에서 꽉 참(캡이 실제로 컷하고 있음) — 그런데 이건 주간 집계라 일간 다이제스트보다 상대적으로 빡빡한 게
  당연해서 이 데이터로는 일간 캡 적정성을 판단 불가. **실제 며칠 라이브 실행 후 재평가하기로 결정.**
- [x] arXiv cs.AI 0건 원인 확인/수정 — 2026-07-27. 원인: `export.arxiv.org/rss/cs.AI` 가 빈 채널(`<item>` 0개) 반환.
  arxiv.org 자체 리스팅엔 최근 1111건 있고, 같은 export 호스트에서 cs.LG/cs.CL 은 정상(rss.arxiv.org 와 바이트 단위 동일) →
  cs.AI 카테고리에 한해 export.arxiv.org 쪽 캐시/렌더링 버그로 추정(arXiv 측 문제, 우리 코드 버그 아님).
  `rss.arxiv.org/rss/cs.AI` (arXiv 신규 표준 RSS 호스트)는 정상(223건) → `sources.yaml` feed_url 교체로 해결.
  dry-run 재확인: arxiv_ai 25건 정상 수집.
- [x] ~~min-significance 컷 추가 (예: 0.25 미만 드롭)~~ — **위 첫 항목과 같은 작업이다**(2026-07-27 완료).
  중복 줄이 남아 있어서 미완료로 보였음, 2026-07-31 에 닫음.
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
- [x] ~~실데이터 며칠 돌리며 dedup 임계값(0.83)·카테고리 상한(6) 튜닝~~ — 중복 줄이라 닫음(2026-07-31).
  dedup 0.83 은 검증 완료(위), 상한/하한은 위 "카테고리 상한/하한 튜닝" 항목이 현재 상태다.
- [x] **소스 확장 Stage 1~3** — 2026-07-31 완료(Guardian·BBC·hn_show·Anthropic /research ·
  HF Daily Papers · gnews 재활성화). 14소스 149건 → **16소스 188건**. 변경로그 참고.
- [~] **소스 확장 Stage 4(Axios·GitHub·YouTube·Medium·NYT) — 안 하기로 확정.** 2026-07-31 사용자 결정.
  전부 "볼륨은 주는데 AI 비중이 38~48%"라 카테고리 상한(6) 아래에서는 순손실. 근거 실측치는
  **§12 판정표**에 보관. 상한 튜닝이 끝나기 전엔 재논의하지 않는다.

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

- 2026-07-30: **headline 필드 + 카테고리별 상한/하한** (스펙 Phase 1-2,
  `docs/superpowers/specs/2026-07-30-digest-expansion-and-quality-design.md`).
  - 제목: 게재 415건 중 42%가 60자 초과, 최대 150자인데 템플릿이 원제목을 그대로 찍어서
    `.lead-title`(최대 62px)이 깨졌다. `:` 분리 같은 규칙은 21%밖에 못 고쳐서
    (측정) `llm.enrich` 의 기존 JSON 스키마에 `headline` 을 추가 — 호출이 안 늘어서
    비용은 출력 토큰 몇 개뿐. 렌더는 `_annotate` 가 정하는 `display_title` 하나만 보고,
    원제목은 `title=` 툴팁으로 남는다. 아카이브 415건은 headline 이 비어 원제목으로 폴백.
  - 캡: 전역 6 하나로는 안 맞았음. 07-30 풀 기준 research 는 후보 51건 중 29건이 0.40 에
    몰린 일반 arXiv 였고, tools_products 는 후보가 2건뿐이라 캡이 아무 일도 안 한다.
    `CategoryRule(max_items, min_significance)` 로 카테고리마다 따로 두고, 하한을 상한보다
    먼저 적용(자리가 남는다고 약한 항목이 올라오면 안 됨). 설정에 없는 카테고리는 전역값 폴백.
    research 하한은 0.60 이 아니라 0.55 — 0.60 이면 통과가 딱 6건이라 캡이 무의미해지고
    점수가 조금만 내려가도 카테고리가 통째로 빈다. 0.55 면 10건이 남아 캡이 실제로 일한다.
    결과: 19건 -> 22건 (policy_business 6->10, tools_products 2->1 은 0.25 짜리가 하한에 걸린 것).
  - `category_floor` 탈락 사유 신설 — 전역 하한 미달(`min_significance`)과 구분해야
    캡 튜닝 데이터가 해석 가능해진다.
  - pytest 도입(`requirements-dev.txt`, `tests/`). CI 는 다이제스트 생성 전용이라 안 붙임.
- 2026-07-30: **스토리 threading 완성 + 실데이터 회귀 검증**. 같은 사건의 후속 보도를 중복으로 버리지 않고 이전 장으로 연결하되, 중복 판정선은 넘지 않게 분리했다.
  - `items` 에 클러스터 출처를 담는 `cluster_sources`(JSON), 묶인 원문 수 `cluster_size`, 이전 장 id `thread_parent_id` 세 컬럼을 추가했다. `thread_parent_id` 는 렌더에서 “Earlier: …” 링크의 근거다.
  - `item_emb(id, embedding, digest_date)` 테이블은 아카이브 항목 임베딩을 **180일** 보관한다. 일간 cross-day dedup 용 `seen` 의 **14일** 창과 독립이며, `purge_old_embeddings()` 가 180일 경과분을 정리한다. `backfill_embeddings.py` 는 기존 아카이브에 이를 소급 생성하는 재실행 안전·API 비용 0 스크립트다. 임베딩 입력은 라이브 경로에서는 `title. summary_raw`(원문 발췌)를 쓰고, 아카이브에는 원문이 남아 있지 않아 백필에서는 `title. summary`(LLM 요약)를 쓴다. 둘 다 제목이 지배적이라 실무상 드리프트는 작지만 실제로 존재하므로, 이를 수용하되 측정 cosine을 함께 기록한다.
  - threading 후보는 현재 항목보다 **이전 날짜**인 것만 대상으로 하고 `[0.75, 0.83)` 유사도 밴드에 들어온 경우에만 연결한다. 실DB 검증에서 Anthropic Series G→H 는 cosine **0.82860172**로 밴드 안이라 연결됐고, Sonnet 4.5→4.6 은 **0.84447765**로 상한 밖이라 연결하지 않았다. 후자도 사람이 보기에는 후속 릴리스지만 상한을 넓히면 진짜 중복이 “Earlier”로 연결된다. 따라서 main dedup 임계값은 **0.83**, grounding 신규성 임계값은 **0.78** 그대로 유지하며 밴드를 넓히지 않는다.
  - 같은 날 Gemini Robotics 2 / Gemini Robotics ER 2 는 cosine **0.82381856**로 밴드 안이지만 서로 다른 단일 출시의 모델이다. `embeddings_before()` 의 날짜-엄격 후보 선택이 같은 날짜를 제외하므로 후보가 되지 않으며, 이것이 same-day sibling announcement를 보호한다. 라이브 DB 회귀 테스트 4건(밴드 확인·부모 선택·상한 밖 비연결·동일일 제외)을 모두 PASSED로 고정했다.
  - **전체 리뷰 후속 수정 4건**(같은 날, 리뷰 판정 "Ship with follow-ups"):
    1. *실측 회귀 가드가 보존 기간에 스스로 잡아먹히던 문제.* 위 cosine 들을 고정하는 테스트가 `item_emb` 를 직접 읽고 있어서, `purge_old_embeddings(180)` 이 도는 순간 근거 임베딩이 사라지고 테스트가 깨지는 구조였다. 실제로 Sonnet 4.5(2025-W40)는 **다음 실행에서 바로**, Series G(2026-W07)는 **9일 뒤** 창 밖으로 나갈 예정이었다. 게다가 실패 메시지가 "임베딩이 없음"이라 원인을 임베딩 모델로 오인하게 만든다 — 밴드를 넓히지 말라는 결정을 지키라고 만든 가드가, 타이머에 맞춰 거짓 경보를 내다 삭제당하기 딱 좋은 형태였다. 그래서 6개 벡터를 `tests/fixtures/threading_vectors.npz` 로 **스냅샷**해 밴드·실측 단언은 DB 를 아예 안 보게 분리했다. `embeddings_before()` 를 실제로 태워야 하는 테스트(부모 선택·동일일 제외)만 DB 를 쓰되, 임베딩이 없을 때 **보존 기간 밖이면 skip(원인을 retention 으로 명시), 창 안이면 fail** 로 갈라 놓았다. `backfill_embeddings.py` 도 보존 기간 밖 항목은 건너뛴다(다음 실행이 어차피 지우므로 백필과 purge 가 서로 싸우던 것).
    2. *과거 일간 페이지에서 "Earlier:" 가 재렌더 때마다 사라지던 문제.* thread 줄이 `_HOME_TMPL`/`_CATEGORY_TMPL` 에만 있고 `_ARCHIVE_WEEK_TMPL` 에는 없었다. `render_digest` 는 `index.html` 과 `archive/{date}.html` 을 같은 홈 템플릿으로 굽지만, 다음 `rerender.py` 실행은 그 아카이브 페이지를 `render_archive_digest` 로 다시 구워서 링크가 영구히 지워졌다 — 재렌더가 사이트 내용을 조용히 바꾸는 상황. 아카이브 템플릿에도 thread 줄을 넣고 `prefix=""` 를 넘긴다(아카이브 페이지는 이미 `archive/` 안이라 부모 링크가 `{date}.html`). `render_archive_digest` 케이스를 테스트에 추가 — 기존 테스트가 홈/카테고리만 덮고 있어서 이 구멍이 태스크별 리뷰를 통과했다.
    3. `dropped_items()` SELECT 에 `thread_parent_id` 누락. 캡에 밀렸다가 DB 풀로 재게재되는 경로에서 부모 링크가 빈 문자열로 덮여 사라졌고, 그 경로엔 `_emb` 가 없어 재계산도 안 된다. `_row_to_item` 이 보장하려던 대칭을 복구.
    4. `_cos` 가 맨 `np.dot` 이라 임베딩 백엔드 폭이 바뀌면 `find_thread_parent` 가 `ValueError` 로 죽는다. 하필 `llm.enrich` 로 그날 API 비용을 다 쓴 뒤, `save_items` 전에 죽어서 페이지도 DB 기록도 없이 끝난다. README 가 권하는 TF-IDF 전환이 바로 이 경우라 가정이 아니다. 후보 shape 불일치는 건너뛰고(잘린 blob 도 같이 커버), `--reset` 이 `seen` 과 함께 `item_emb` 도 비우게 했다(CLAUDE.md 가 백엔드 교체 처방으로 `--reset` 을 안내하는데 실제로는 `item_emb` 가 살아남아 처방이 거짓이었다).
  - 남은 사실: `thread_parent_id` 는 아직 전 행이 비어 있다. threading 은 **신규 게재분**에만 걸리므로 Series G→H 처럼 양쪽이 아카이브인 쌍은 실제 링크를 만들지 않는다. 첫 실제 "Earlier:" 는 새 기사가 밴드에 들어오는 날 나타나며, 그날 페이지는 손으로 확인할 것.

- 2026-07-30: **소스 후보 18종 실측 리뷰 + Stage 1 반영**. 사용자가 제안한 소스 목록(HN·Google News·
  GitHub Trending·Axios·OpenAI Research·HuggingFace·Anthropic·TechCrunch·종합지 9개·Medium·
  brunch·LinkedIn·YouTube)을 추측이 아니라 **실제 fetch 로** 검증(약 45개 엔드포인트, 5라운드).
  - **추가함(Stage 1)**: `guardian_ai`(전용 AI 토픽 피드, 20건 중 17건 AI = 85%, 페이월 없음 —
    종합지 중 유일하게 TechCrunch 90% 에 근접) · `bbc_tech`(21건, AI 6건이지만 영국·EU 규제 커버,
    피드 요약이 99자뿐이라 `full_text: true`) · `hn_show` 활성화(20건, 요약 1492자).
  - **Anthropic `/research` 추가**: 이미 매 실행 받고 있던 같은 sitemap 에 `/news 251` 외에
    **`/research 149`, `/engineering 25`** 가 있었는데 `_sitemap_news_urls` 가 `/news/` 를
    하드코딩해서 안 보였음. `Source.sitemap_paths`(기본 `["/news/"]`) 신설 + `_sitemap_news_urls`
    가 다중 경로를 받도록 변경. 검증에서 "Discovering cryptographic weaknesses with Claude"(07-28),
    "Project Pilot"(07-24) 2건이 실제로 새로 들어옴.
  - ⚠️ **`/engineering/` 은 의도적으로 제외** — 페이지에 발행일이 **아예 없다**(실측: JSON-LD
    `datePublished`·`<time>`·`datetime` 속성·산문 날짜 전부 0건). `_article_published` 가 항상 ''
    을 반환해 lastmod 폴백만 남는데 그게 07-28 에 296일 오차를 만든 경로다. `/research/` 는 정상
    (3건 모두 lastmod 와 1~2일 이내 일치). 사유를 `sources.yaml` 주석에 박아둠.
  - **`resolve_url()` 로 Google News 를 못 고친다는 것 확인 → 하지만 디코딩 자체는 가능**.
    `sources.yaml` 에 적혀 있던 처방(리다이렉트를 `resolve_url` 로 통과)은 **틀렸음** — 실측 4건
    전부 같은 `news.google.com` URL 을 그대로 반환한다(Google 이 클라이언트 사이드로 넘김).
    id 의 base64 도 URL 이 아니라 protobuf 블롭. **다만** `ma2za/google-news-api`(MIT, 2026-07-29
    갱신)가 쓰는 `batchexecute`/`garturlreq` 페이로드를 그대로 태우면 **AP 3/3 디코딩 성공**
    (`https://apnews.com/article/microsoft-earnings-results-ai-...`). 내가 처음 시도했을 때 실패한 건
    내부 배열 원소 개수가 틀려서였음. 비용은 항목당 기사 페이지 GET(~567KB) + POST 1회.
    라이브러리는 `httpx`+`selectolax` 의존이 붙으므로 **디코딩 30줄만 인라인**하는 쪽이 나아 보임.
    이게 AP/WaPo/WSJ 로 가는 유일한 경로라 Stage 3 에서 재검토.
  - **죽은 소스 확정**: AP(`index.rss` → `401 Invalid client credentials`, hub → 404) ·
    WaPo(tech 피드가 HTTP 200 인데 항목 0건) · **WSJ(피드 3종 전부 2025-01-27 에 멈춤 — 18개월 방치)** ·
    CBC(19건 중 1건만 AI) · NYT(피드는 살아있고 33건 중 16건 AI 지만 본문 추출이 페이월로 0자).
  - **정책상 불가**: `brunch.co.kr` — RSS 자체가 없고(실제 작가 id 5개로 `/rss/@@{id}` 전부 200에
    **0바이트**, `/rss/@{id}` 404, sitemap 404) `robots.txt` 가 GPTBot·**ClaudeBot**·anthropic-ai·
    CCBot 등을 이름으로 지목해 `Disallow: /`. LinkedIn — 남의 포스트를 읽는 공개 API 가 없고
    robots.txt 첫 줄이 자동 접근 금지 명시.
  - **다음 후보(Stage 2~4)**: HuggingFace Daily Papers API(50건, 초록 전문 + **upvote 수** —
    research 후보가 0.40 에 몰리는 문제의 직접적 해법) · OpenAI `entry.tags` 읽기(news RSS 1,056건
    중 194건이 이미 `Research` 태그. `research/rss.xml` 은 404고 우리가 태그를 안 읽을 뿐) ·
    Axios(피드에 본문 6,102자가 통째로 옴 → `full_text` 불필요. 단 섹션 피드 없음, 전 항목 태그가
    `top` 하나뿐이라 키워드 게이트 필요, AI 비중 38%) · GitHub Trending(공식 API 없음. 미러는
    **항목별 날짜가 없어** 신선도 컷을 우회하는 gnews 와 같은 함정. Search API 는 비인증 10req/h,
    Actions 의 `GITHUB_TOKEN` 이면 해결) · YouTube(채널 RSS 는 공식·정상이나 자막이 아니라 ~500자
    설명뿐이고, DeepMind 최신 영상이 블로그와 중복 — dedup 부담만 늘 수 있음).
  - 리뷰 산출물은 캔버스 `news-source-review.canvas.tsx`(레포 밖, Cursor 프로젝트 폴더).

- 2026-07-31: **Stage 2 — HF Daily Papers 추가. OpenAI 태그 라우팅은 불필요한 것으로 판명(코드 무변경)**.
  - **OpenAI: 할 게 없었다.** 07-30 리뷰에서 "`fetch.py` 가 `entry.tags` 를 안 읽어서 Research 글이
    research 카테고리로 못 간다"고 적었는데, **둘 다 사실이 아니었음**. (1) 카테고리는 `llm.enrich`
    가 본문을 보고 직접 정한다 — 소스 카테고리는 `source_category_hint` 로 힌트만 준다. 실제 DB 에서
    openai 아이템은 이미 policy_business 57 · tools_products 50 · **research 34** · model_releases 22
    로 갈려 있다. (2) `parsed.entries[:25]` 슬라이스도 손실이 없다 — 최신 25건 중 14~19건이 7일 컷에
    걸린다는 건 **7일 창이 25건 안에 다 들어온다**는 뜻이다. 태그를 읽어봐야 힌트 정확도가 조금
    올라갈 뿐이라 코드 변경 없이 종료. (캔버스 리뷰의 해당 항목도 정정함.)
  - **HF Daily Papers 추가**(`parse: hf_papers`, `fetch.fetch_hf_papers_source`). API 는
    `huggingface.co/api/daily_papers?limit=100` (실측 100건 = 약 17일치, 초록 평균 1499자,
    upvote 0~229). `publishedAt` 이 `2026-07-29T20:00:00.000Z` 라 기존 `_norm_date` 로 그대로 파싱됨.
  - **설계: upvote 는 "수집 단계 선별"에만 쓴다.** significance 에 섞으면 랭킹 rubric(3장 고정)을
    건드리는 셈이라 안 함. 대신 신선도 컷 뒤에 upvote 내림차순으로 정렬해 상위 `max_entries`(25)만
    남긴다. **컷을 정렬보다 먼저** 하는 게 핵심 — 반대로 하면 "17일치 중 최고 인기"가 뽑혀 오래된
    논문이 오늘 자리를 차지한다(테스트로 고정). 실측 결과 25건 전부 7일 이내, upvote 하한이 30 이라
    arXiv 무필터 파이프와 질이 확연히 다름.
  - **arXiv 와 중복 없음(실측 0/25)**: arXiv 피드는 "가장 최근 25건"을 주고 HF 는 하루이틀 지나
    표가 모인 걸 고르기 때문에 arXiv id 기준으로 안 겹쳤다. 겹치기 시작하면 id 기준 하드 dedup 검토.
  - **수집량**: 14소스 149건 → **15소스 178건**. dry-run 34.6초(변화 없음), `digest.db` 무변경.
    ⚠️ dry-run 은 significance 가 0.5 고정이라 research 하한 0.55 에 전부 걸린다 — **research 구성
    개선 효과는 실제 실행 후에 봐야 판단 가능**(dry-run 의 `category_floor` 63건은 그 아티팩트).
  - 테스트 `tests/test_hf_papers.py` 11건 신설(필드 매핑 · upvote 정렬 · **컷이 정렬보다 먼저** ·
    max_entries · `_upvotes` 가 밑줄 임시키인지 · 깨진 행/비배열 응답/네트워크 실패 · parse 디스패치 ·
    `_as_int` 방어). 전체 80 passed.

- 2026-07-31: **Stage 3 — `gnews_ai` 재활성화. 껐던 두 버그를 고치고 "갭필러"로 좁힘.**
  - **왜 다시 켰나**: 07-30 리뷰에서 AP(`index.rss` 401 — 유료 라이선스)·WaPo(피드 HTTP 200 인데
    항목 0건)·Reuters(404) 는 공식 피드로 가져올 방법이 없다는 걸 실측했다. 이 셋은 "AI 정책·규제·
    돈" 쪽에서 다른 소스가 안 다루는 걸 다룬다. Google News 는 이 구멍을 메우는 **유일한 경로**라
    폐기 대신 수리를 택함.
  - **[버그 1 해결] 날짜.** RFC 822(`Thu, 30 Jul 2026 10:01:00 GMT`)를 `_norm_date` 가 못 읽어
    `published=""` 가 됐고, **파싱 실패는 `_apply_cutoff` 를 통과시키는 설계**라 이 소스만 7일 컷을
    통째로 우회했다(07-28 "5개월 전 리드"와 동종). 이번에 `gnews` 라이브러리를 걷어내고 RSS 를
    직접 `_parse_feed` 로 파싱하게 바꾸니 **feedparser 가 발행일을 알아서 읽어** 문제가 소멸.
    그래도 `_norm_date` 에 `parsedate_to_datetime` 폴백을 넣었다 — 다른 소스가 같은 함정을 밟을
    수 있고, 실패가 조용히 컷 우회로 이어지는 구조라 보험이 필요.
  - **[버그 2 해결] 불투명 URL.** `news.google.com/rss/articles/...` 는 **리다이렉트가 아니다**
    (실측 4/4 가 같은 주소 반환 — Google 이 클라이언트 사이드로 넘긴다). 그래서 기존 `resolve_url()`
    로는 못 푼다고 결론냈었는데, `ma2za/google-news-api` 를 뜯어보니 비공개 `batchexecute` RPC 로
    풀린다. 처음 시도가 실패한 건 **페이로드 배열 원소 개수가 하나 틀려서**였다(틀리면 조용히 `[3]`
    에러). `fetch.decode_google_news_url()` 로 구현 — 실측 10/10 성공.
  - **디코딩 실패 시 아이템을 버린다**(예외 아님). 불투명 링크를 저장하면 본문 추출도 안 되고
    사이트에 영구히 남는다(07-30 실제 사고). 드롭은 다음 실행에 자동 재시도되므로 회복 가능하지만,
    저장은 되돌릴 수 없다 — **비대칭이라 드롭이 안전한 쪽**.
  - **순서가 곧 비용**: 수집 → 신선도 컷 → 디코딩. 디코딩은 항목당 기사 페이지 GET(**실측 ~567KB**)
    + POST 1회라, 컷 앞에서 돌리면 곧바로 버릴 기사까지 받아온다(07-30 `full_text` 와 같은 실수).
    추가로 `Source.max_entries` 설정을 신설해 이 소스만 10 으로 조임(25 면 매 실행 ~14MB·16초).
  - **질의를 `site:` 로 한정**: `(AI OR "artificial intelligence") (site:apnews.com OR
    site:washingtonpost.com)`. 넓은 키워드의 노이즈("Academic Orthopaedic Surgeons…" 류)가
    사라진다. Reuters 도 넣어봤지만 100건 중 75건을 차지해 AP/WaPo 를 밀어내서 보류(2026-07-31 실측).
  - **실측 결과**: 10건, 불투명 URL 0 · 날짜 없음 0 · 전부 7일 이내. 내용도 실제로 겹치지 않는
    것들(EU AI 규제 $11.4B 기가팩토리, xAI 의 미네소타 주 제소, 켄터키 우라늄 부지 데이터센터).
    수집량 15소스 178건 → **16소스 188건**. dry-run 58초(디코딩 10회분 증가분 포함).
  - **`gnews` 의존성 제거**(`requirements.txt`). 라이브러리가 내부적으로 `feedparser.parse(url)` 을
    써서 로컬 CA 인증서 부재에 걸리던 문제(07-29 오진했던 그 `NetworkError`)도 같이 사라짐.
  - ⚠️ **이 RPC 는 문서화되지 않은 내부 엔드포인트다.** Google 이 바꾸면 조용히 0건이 된다.
    감시 수단: source-health 배지(raw==0) + 실행 로그의 "URL 디코딩 실패 N건" 라인.
  - 테스트 `tests/test_gnews.py` 17건 신설(RFC 822 파싱 · **2024년 기사가 7일 컷에 걸리는지** ·
    디코딩 성공/RPC 에러/서명 누락/비-GNews URL 은 네트워크 미사용/네트워크 예외 · 디코딩 실패 시
    드롭 · id 가 최종 URL 기준인지 · 발행처 접미사 제거 · **만료 항목이 디코더에 안 닿는지** ·
    max_entries 상한 · 설정이 site: 한정 + 10 인지). 전체 **101 passed**.
    픽스처는 실제 응답을 떠서 만들었다 — 처음엔 지어냈다가 형식이 달라 테스트가 헛돌았다.

- 2026-07-31: **Stage 4 는 하지 않기로 확정. 소스 확장 종료.** 사용자 결정으로 "되지만 신호를
  깎는" 5종(Axios·GitHub Trending·YouTube·Medium·NYT/NY Post)과 "아예 안 되는" 6종(AP 직접·
  WaPo·WSJ·CBC·brunch·LinkedIn)을 구현하지 않고 **판정 근거만 §12 에 표로 보관**했다.
  이유: 전자는 AI 비중이 38~48% 라 카테고리 상한(6) 아래에서 좋은 항목을 밀어내고, 후자는
  엔드포인트가 없거나(AP 401/WaPo 0건/WSJ 18개월 정지) 로봇 배제가 명시돼 있다(brunch·LinkedIn).
  **다음 작업은 소스를 더 붙이는 게 아니라 지금 들어온 188건을 상한이 제대로 거르는지 보는 것** (§9).

- 2026-07-31: **카테고리 상한/하한 실측 분석. 상한(6)은 문제가 아니었고, research 하한(0.55)이 문제.**
  드디어 `drop_reason` 이 쌓인 실제 실행(07-30, 07-31) 데이터로 §9 의 보류 항목을 봤다.
  **결론부터: 상한은 손대지 않는다. 대신 research 하한 0.55 가 두 가지 이유로 잘못 잡혀 있다.**
  - **[발견 1] significance 는 연속값이 아니라 격자값이다.** 일간 실행 전체에서 LLM 이 실제로 뱉은
    값은 0.10·0.20·0.30·0.40·0.50·**0.55**·0.60·0.65·0.70·0.75·0.80·0.85·0.90 뿐이다. 즉 하한을
    0.50↔0.55 처럼 격자 사이로 옮기면 **아무 일도 안 일어나거나, 격자를 넘는 순간 절벽이 생긴다.**
    07-31 research 기준: 하한 0.40 → 33건 통과, 0.45~0.50 → 6건, 0.55~0.60 → **2건**.
    하필 0.55 는 **LLM 이 실제로 자주 내는 값**(전체 4건)이라 가장 불안정한 자리다.
  - **[발견 2] 하한 하나가 상충하는 두 일을 겸하고 있다.** 이 값의 목적은 "0.30~0.40 에 뭉친 일반
    arXiv 홍수"를 막는 것이었는데(07-30 근거), 0.55 로 두면 **0.50 짜리 랩 블로그 연구까지 같이
    잘린다.** 07-30 의 0.50 항목들이 그 증거다 — "DiffusionGemma: 4x faster text generation",
    "Gemini Deep Think 로 수학·과학 발견 가속", "Measuring progress toward AGI". 실을 만한 것들이다.
  - **[발견 3] 날마다 편차가 극단적이다.** 07-30 은 research 후보 15건이 0.50~0.65 에 퍼져 있어
    하한 0.55 로도 14건이 통과하고 캡 6 이 정상 작동했다. 반면 **07-31 은 후보 40건 중 37건이
    하한에 걸려 카테고리가 2건으로 텅 빔.** 이유는 그날 research 풀이 거의 전부 arXiv 였기 때문
    (arxiv_lg 24 · arxiv_ai 13 · anthropic 1 · grounding 1, 랩 블로그가 그날 조용했음).
  - **[하지만] 지금 튜닝하면 안 된다.** 위 데이터는 **HF Daily Papers 가 들어가기 전** 실행분이다
    (07-31 research 풀에 `hf_daily_papers` 가 없는 것으로 확인). HF Papers 는 upvote 하한 30 짜리
    선별된 논문이라 **정확히 이 문제(=arXiv 무필터가 research 를 채우는 것)를 겨냥해 넣은 소스**다.
    입력 분포가 곧 바뀔 걸 알면서 그 전 분포에 맞춰 하한을 고르는 건 두 번 일하는 것이다.
    → **새 소스 4종이 포함된 진짜 실행 1회를 받은 뒤 결정한다.**
  - 참고 수치(그때 비교용): 하한을 0.55→0.50 으로 내렸을 때 **07-30 의 게시 결과는 전혀 안 바뀐다**
    (14→15 통과, 캡 6 이 흡수). 07-31 만 2→6 으로 회복된다. 즉 현재 데이터만 보면 0.50 이
    "나쁜 날을 고치고 좋은 날은 안 건드리는" 값이다. 단 07-31 에서 새로 통과하는 4건이 전부
    arXiv 0.50 이라, HF Papers 가 그 자리를 대신 채워주면 하한을 안 내려도 될 수 있다.
  - `policy_business` 는 이틀 다 10건 게시 + 캡으로 2~4건 컷 — 캡이 의도대로 작동 중. gnews 로
    AP/WaPo 가 들어오면 압력이 더 올라가므로 같이 관찰할 것.

- 2026-07-31: **새 소스 4종 포함 첫 진짜 실행. 리캡 크래시 버그 수정 + HF Papers 는 실패로 판명.**
  Stage 1~3 는 그때까지 dry-run 만 돌렸어서, 실제 실행으로 검증함. 결과 **19건 게시(major 7)**,
  헤드라인 "Rogue Anthropic and OpenAI Agents Hack External Systems, Sparking Regulatory Scrutiny".
  - **[버그 수정] 리캡 실패가 파이프라인 전체를 죽였다.** 첫 실행이 `llm.generate_recap` 에서
    `JSONDecodeError`(모델이 콤마 하나 빠뜨림)로 죽으면서 **6분 45초치 LLM 작업을 통째로 날렸다.**
    리캡은 enrich 가 **다 끝난 뒤** 오는 **장식**(헤드라인/$ 집계/카테고리 한 줄)이라 여기서
    예외를 올리면 안 된다. 렌더 쪽은 이미 빈 리캡을 견디게 되어 있었다(`recap[...].get(cat,"")`).
    → `generate_recap` 을 다른 LLM 경로(`_call_batch`/`catch_missed_news`)와 **같은 계약**으로 맞춤:
    `MAX_RETRIES` 재시도 후 실패하면 로그 남기고 빈 리캡 반환. 이 함수만 재시도가 없었던 게 원인.
    테스트 `tests/test_llm_recap.py` 13건 신설(정상 파싱 · 펜스/산문 안의 JSON 구조 · **콤마 누락
    재현** · 재시도 후 성공 · 네트워크 예외 · 빈 응답 · dict 아닌 JSON · one_liner 타입 깨짐 ·
    빈 입력이면 API 미호출 · 재시도 횟수가 하우스 규칙과 일치).
  - **[중요·부정적 결과] HF Daily Papers 는 목적을 달성하지 못했다. 25건 후보 중 게시 0건,
    significance 최고값이 0.45 로 research 하한 0.55 를 **단 한 건도** 못 넘었다.**
    Stage 2 에서 세운 가설("upvote 30 이상이면 선별된 논문이니 arXiv 무필터보다 낫다")이 **틀렸다.**
    원인은 **축이 다르기 때문**이다 — upvote 는 ML 실무자 커뮤니티의 관심도이고, significance 는
    랭킹 rubric(frontier 모델 출시 / 대형 펀딩 / 벤치마크 기록 / 정책 변화 / incremental_research)
    기준의 **뉴스 가치**다. 아무리 표를 많이 받은 논문도 rubric 에선 `incremental_research` 다.
    참고로 같은 날 raw arXiv 는 0.50 이 2건 나와서 **HF 쪽이 오히려 더 낮았다.**
  - **소스별 누적 게시율**(07-30~31): gemini_grounding 86% · deepmind/anthropic 100%(소량) ·
    openai 56% · techcrunch 50% · **gnews_ai 22%** · bbc_tech 21% · arxiv_ai 20% · hn_ai 14% ·
    guardian_ai 11% · **arxiv_lg 2%(50건 중 1건)** · **hf_daily_papers 0%(25건 중 0건)**.
    → Stage 1/3 추가분(gnews·bbc·guardian)은 기존 소스와 비슷한 수준으로 **정상 작동**.
      Stage 2 추가분(hf_daily_papers)만 순손실이다.
  - **[구조적 관찰] 논문 피드는 뉴스 다이제스트의 rubric 과 근본적으로 안 맞는다.** research 에서
    실제로 하한을 넘는 건 랩 발표(Anthropic 0.60, Guardian 기사 0.60, grounding 0.80)뿐이고,
    논문 3종(arxiv_ai/arxiv_lg/hf)이 **매일 63건을 enrich 비용으로 태우면서** 기여는 거의 없다.
    하한을 내려서 논문을 넣는 것과, 논문 피드 자체를 줄이는 것 중 어느 쪽인지는 **사용자 결정 사항**
    (다이제스트가 "뉴스"인가 "논문 트래킹"인가에 대한 제품 판단이라 데이터만으로 못 정한다).
  - **하한 관련 결론**: 07-31 실데이터에서 하한 0.55 → 4건 게시(캡 6 미달), 0.50 → 6건, 0.45 → 7건.
    다만 0.50 으로 내려서 추가되는 2건은 평범한 arXiv 논문이라("Flat Score, Amplified Failures" 등)
    **강한 4건 vs 채워넣은 6건**의 문제다. 오늘 실린 research 4건은 주제가 일관되고(AI 보안/암호
    취약점 발견) 품질이 좋아서, **하한은 일단 0.55 유지**하고 위 구조적 판단이 정해진 뒤 같이 손대는
    게 맞다고 봄. 캡(6)은 policy_business 에서 정상 작동 중이라 **변경 안 함**.
  - **결정(사용자, 2026-07-31): 아무것도 지우지 않고 며칠 더 모은 뒤 재평가.** HF 는 아직 **하루치
    25건**뿐이라 0/25 로 소스를 폐기하기엔 표본이 작다는 판단. 하한·캡·소스 구성 전부 현행 유지.
    ⚠️ 이 항목이 흐지부지되지 않도록 **재평가 기준을 미리 못박아 둔다** — 아래 쿼리를 돌려서
    판단할 것(날짜만 바꾸면 됨):

    ```bash
    # 소스별 후보/게시/게시율 + 최고 significance
    sqlite3 digest.db "select source_id, count(*) cand, sum(is_published) pub,
      round(100.0*sum(is_published)/count(*),1) pct, max(significance) top
      from items where digest_date >= '2026-08-05' group by 1 order by 2 desc;"
    ```

    **판정 규칙**(누적 후보 100건 이상 쌓였을 때 = 대략 8월 4일경):
    - `hf_daily_papers` 게시 **0건 유지** 또는 최고 significance 가 계속 **0.50 미만** → 제거.
      가설이 틀렸다는 게 확정된 것이고, 하루 25건 enrich 비용만 나간다.
    - 게시율 **5% 이상**이면 존치. 그 사이(1~5%)면 `arxiv_lg`(현재 2%)와 **둘 중 하나만** 남길 것 —
      research 는 캡 6 인데 논문 피드 3종이 63건을 밀어넣는 구조 자체가 과공급이다.
    - 어느 쪽이든 **research 하한(0.55)은 이 결정을 내린 뒤에 손댄다.** 순서를 지킬 것 —
      소스 구성이 바뀌면 분포가 바뀌고, 그러면 하한을 또 다시 정해야 한다.

- 2026-07-31: **소스 확장 종료 선언 + 유료/고비용 API 는 다음 주로 연기(사용자 결정).**
  "소스 확장은 거의 끝났다. 비용 때문에 고비용 API 는 지금 건너뛰고 다음 주에 다시 논의한다."
  → **Phase 5(json_api 어댑터 · 유저 제공 API 키 · quarantine)는 다음 주 논의까지 착수하지 않는다.**
  같이 묶여 있던 free RSS 확장(Qwen·DeepSeek·Cohere·Mistral)도 **소스 확장 종료에 포함**해 닫는다 —
  비용은 안 들지만 카테고리 상한 아래에서 밀어내기가 생기고, 무엇보다 지금 남은 건 소스가 아니라
  **화면**이다. 16소스 188건에서 동결.
  이 결정으로 남은 작업을 §13 에 정리했다. **다음 세션은 §13 부터 읽으면 된다.**

- 2026-07-31: **T2.1 완료 — grounding 소스 품질 게이트. 설계 Phase 4 의 마지막 미완료 항목.**
  §13 T2.1. 착수 전에 실제 데이터를 먼저 봤는데, 메모에 적혀 있던 것보다 나빴다.
  - **실측**: `gemini_grounding` 은 이틀(07-30·31) 동안 후보 10건 중 8건 게시(게시율 80%, 전 소스
    최고). 그런데 **07-31 게시분 4건이 전부 라운드업/집계 페이지**였다 — `aiweekly.co/`(0.9) ·
    `buildfastwithai.com/blogs/ai-news-today-july-30-2026`(0.8) · `ai.economictimes.com/`(0.7) ·
    `buttondown.com/ai-tldr/archive/aitldr-daily-digest-july-30-2026/`(0.7).
    07-30 은 반대로 3/4 가 정상(nist.gov · courthousenews · siliconangle)이었다.
    → "게시율 최고 소스"라는 기존 평가는 **표본 2일에 URL 을 안 본 결과**였다. 정정.
  - **[발견] 하한·캡으로는 절대 안 걸린다.** 라운드업이 significance **0.7~0.9** 를 받는다.
    LLM 은 "오늘의 AI 뉴스 모음"을 읽고 중요한 뉴스라고 판단한다 — 내용상 틀린 말도 아니다.
    policy_business 하한 0.40·캡 10 위로 한참 뜬다. **랭킹 단계에서 막을 수 있는 문제가 아니다.**
  - **[발견] 설계 스펙이 놓친 두 번째 결함: 맨 도메인.** 게시된 4건 중 **3건이 경로 없는 홈페이지**
    (`aiweekly.co/`, `ai.economictimes.com/`)였다. 기사가 아니라 사이트 첫 화면이다. `resolve_url()`
    은 200 을 주니까 통과시킨다. 스펙에는 "콘텐츠팜 도메인 블록리스트"만 적혀 있었다.
  - **그래서 세 겹으로 막는다**(`llm._grounding_reject_reason`, resolve 뒤에 적용):
    1. **맨 도메인**(경로 없음, 쿼리도 없음) → 버림. **블록리스트 관리가 필요 없는 유일한 규칙**이고
       내일 생기는 새 팜에도 그대로 통한다. 07-31 게시 4건 중 3건이 여기서 잡힌다.
    2. **도메인 블록리스트** — 관측된 6곳(위 4곳 + `unrot.co` + `ainewstoday.com`/`crescendo.ai`.
       뒤 둘은 캡·하한에 우연히 걸려 안 실렸을 뿐이라 같이 넣었다). 서브도메인·`www.` 우회 차단.
    3. **URL 슬러그 패턴** — `ai-news-today`/`daily-digest`/`this-week-in` 등. 처음 보는 도메인이
       같은 짓을 해도 걸린다.
    ⚠️ `ai.economictimes.com` 은 **도메인을 막지 않았다.** Economic Times 는 실제 언론사고 문제는
    URL 이 홈페이지였던 것뿐이다 — 규칙 1이 처리한다. 정상 매체를 블록리스트에 넣지 말 것.
  - **프롬프트에도 primary-source 규칙 추가**(랩/기관 공식 발표·규제기관 릴리스·논문·원 취재 우선,
    라운드업/뉴스레터/집계 금지, URL 은 단일 기사 직링크). 단 **프롬프트는 방어선이 아니다** —
    07-31 이 그 증거다. 코드 게이트가 최종 방어선이고 프롬프트는 후보 품질을 올리는 쪽.
  - **설정은 `sources.yaml settings.grounding`** (`blocked_domains`/`blocked_url_patterns`).
    새 팜은 YAML 한 줄로 막는다. 키가 없으면 `llm.py` 모듈 기본값, **`[]` 로 명시하면 필터 끄기**
    (None 과 구분 — 키 오타로 필터가 조용히 꺼지는 걸 막으려고 이렇게 했다).
  - **거부는 반드시 로그에 남긴다** — grounding 은 `drop_reason` 이 쌓이는 경로를 안 타므로
    (`items` 에 저장되기 전에 버려진다) 실행 로그가 유일한 증거다. 프롬프트가 안 먹히는지,
    블록리스트에 새 도메인을 넣어야 하는지를 여기서만 알 수 있다.
  - 테스트 `tests/test_grounding_quality.py` **22건** 신설. 핵심은 **07-31 에 실제로 실린 4개 URL 을
    픽스처로 박은 것**(회귀 가드) + **같은 이틀의 정상 6건이 통과하는지**(게이트 과잉 방지).
    그 외 서브도메인/`www.` 우회 · 미지 도메인의 슬러그 · `?p=123`(경로 없어도 글일 수 있음) ·
    `[]` 로 껐을 때도 구조 규칙은 남는지 · YAML→필터 배선 · 프롬프트 문구 · 로그.
    전체 **136 passed**. dry-run 정상(16소스 186건, `hn_show` 만 0건 — hnrss 502 일시 장애,
    소스헬스 배지가 정확히 잡아냄).
  - ⚠️ **다음 실제 실행에서 로그를 볼 것.** grounding 이 3건 전부 라운드업만 물어오면 게이트 통과가
    0건이 된다 — 그건 게이트 문제가 아니라 **grounding 자체의 효용 문제**이므로, 그때는
    `catch_missed_news` 를 끄는 것까지 후보에 올릴 것(비용은 검색 1회 + enrich 3건).

- 2026-07-31: **T3.1 완료 — render.py 구조 분리(1,069줄 → 380줄). Phase 6 선행 조건 해제.**
  §13 T3.1. 마크업/스타일을 파이썬 문자열에서 빼서 파일로 옮겼다. **렌더 결과는 안 바뀐다.**
  - **결과 구조**: `templates/` 6개(`macros`·`home`·`category`·`search`·`archive_index`·
    `archive_week`) + `static/digest.css`(206 규칙) + `render.py` 380줄(데이터 가공만).
    `DictLoader` → `FileSystemLoader`. 5개 템플릿이 각자 반복하던 head(테마 JS+폰트)는
    `macros.head_scripts()` 하나로 모았다.
  - **검증 방법이 이 작업의 핵심이었다.** `rerender.py` 가 커밋된 HTML 을 그대로 재현하지 않아서
    (아래 참고) 커밋본과 비교하면 리팩터 손상과 기존 드리프트를 구분할 수 없다. 그래서
    **리팩터 직전 rerender 출력을 스냅샷으로 떠서 그걸 기준선으로 썼다.**
    → **238개 페이지 `<body>`·`<title>` 바이트 동일**. CSS 는 셀렉터 207 → 207, 원본 6블록이
    배포 파일에 그대로 포함, 페이지별 옛 인라인 CSS 가 전부 부분집합임을 확인.
    테마 JS 2,064자도 바이트 동일(손으로 옮긴 유일한 부분이라 따로 확인).
  - **[알아낸 것] `rerender.py` 는 커밋된 HTML 과 바이트 동일하지 않다** — 버그가 아니라 설계다.
    (1) 모든 페이지가 전역 레코드 수를 표시하는데 DB 가 자라서 422 → 444 로 바뀐다(오히려 정정),
    (2) `index.html` 의 source-alert 가 사라진다 — 어느 피드가 죽었는지는 **fetch 시점 상태**라
    DB 에 없다(rerender 는 `warnings=[]` 를 넘긴다). **다음에 rerender 를 검증 도구로 쓸 때
    이 두 가지를 기준선에서 먼저 제거할 것.**
  - **`:root` 팔레트 블록은 CSS 파일에 넣지 않고 `write_assets()` 가 생성해 붙인다.** 팔레트
    5색의 원본은 `render.PALETTES`(테마 JS 와 스위처 버튼이 같은 배열을 읽는다) — 기본 팔레트만
    CSS 에 복붙해두면 파이썬을 고칠 때 조용히 갈라진다. 그래서 배포 시점에 조립한다.
    ⚠️ **T3.3 에서 디자이너 왕복(Claude Design export)을 하면 이 규칙이 깨지기 쉽다** —
    export 된 CSS 에 `:root` 가 들어있으면 지우고 PALETTES 를 고칠 것. 테스트가 잡는다.
  - **경로 변수 함정**: 기존 `prefix` 는 템플릿마다 의미가 다르다 — home/category 에서는
    "루트까지", archive_week 에서는 "archive 디렉터리까지"(스레드 링크가 아카이브 형제를
    가리키므로). 그래서 CSS 경로는 재사용하지 않고 **`asset_prefix` 를 따로 만들었다.**
  - `write_assets()` 는 각 `render_*` 가 자기 시작에서 부른다(프로세스당 1회만 실제 기록).
    호출자가 잊으면 CSS 없는 사이트가 나오는데, 그 실수가 불가능해야 한다.
  - 테스트 `tests/test_render_assets.py` 16건: 깊이별 링크 경로(루트/archive) · 링크가 실제
    파일로 풀리는지 · 인라인 `<style>` 이 안 남았는지 · 저작 CSS 에 `:root` 없음(드리프트 가드) ·
    기본 팔레트 실제 값(인덱스 착오 가드) · 파일 삭제 후 복구 · 5개 렌더러가 각자 CSS 를 쓰는지 ·
    마크업/CSS 가 render.py 로 되돌아오지 않았는지 · 테마 JSON 이 autoescape 를 우회하는지(`|safe`).
    전체 **152 passed**. dry-run·rerender 양쪽 경로 모두 정상.
  - 부수 효과: `<!doctype>` 앞 빈 줄이 2줄 → 1줄로 줄었다(템플릿 앞 개행 정리). 무해.

- 2026-07-31: **T3.2 완료 — 아카이브 인덱스가 47개 전부를 링크한다. 완성 정의 3번 충족.**
  §13 T3.2. 예전엔 `digests[:6]` 만 `<a>` 였고 나머지는 `+ 41 earlier digests` 라는 **링크 없는
  텍스트**였다. 즉 6개월 백필로 만든 43주치가 사이트 안에서 도달 불가였다(검색이나 URL 직접
  입력 외에 경로가 없었다). 아카이브가 있다고 말할 수 없는 상태였음.
  - **전부 싣는다.** 47행은 페이지네이션이 필요한 양이 아니다. 대신 **연도 구분선**(sticky)으로
    훑을 기준선을 줬다 — 2026: 31 · 2025: 10 · 2024: 2 · 2023: 4.
  - **[문구 오류 수정] "47 weeks of signal" 은 틀린 말이었다.** 실제 구성은 **주간 43 + 일간 4**다
    (주간은 백필 산출물, 일간은 라이브 실행분). "47 digests of signal" + 부제에 "43 weekly ·
    4 daily" 로 분리. 개수를 세는 쪽이 라벨 형식을 알아야 해서 `store.is_week_label()` 을 공개
    함수로 추가했다 — 라벨 형식을 아는 곳은 store 하나여야 한다(`_WEEK_LABEL_RE` 는 private).
  - **최신 강조는 파이썬에서 표시한다**(`d["is_latest"]`). 중첩 루프 안에서 "첫 연도의 첫 행"을
    판정하려니 템플릿이 읽기 어려워졌다 — 이런 판정은 렌더 코드의 일이다.
  - ⚠️ **연도 그룹은 라벨 앞 4자리가 아니라 `label_sort_key` 의 실제 날짜로 묶는다.**
    `2026-W01` 의 월요일은 **2025-12-29** 라 ISO 연도로는 2025 다. 테스트로 고정.
  - 검증: 렌더된 인덱스의 **링크 47개가 전부 실제 파일로 해석**되는 것 확인. 그리고 이 변경으로
    238페이지 중 `archive/index.html` **하나만** 바뀌었다(+CSS) — T3.1 리팩터가 나머지를
    안 건드렸다는 확인도 같이 됐다.
  - 테스트 `tests/test_render_archive_index.py` 17건: 전부 링크되는지 · **6행 경계에서 안 잘리는지**
    (예전 상한) · 죽은 텍스트 부재 · 일간/주간 섞였을 때 최신 강조 1개 · 정렬 순서 ·
    연도 그룹이 전 행을 분할하는지 · `2026-W01`→2025 · 문구(주간/일간 분리, 일간 0이면 생략) ·
    링크가 옆에 실제 렌더된 페이지로 풀리는지 · `is_week_label` 6케이스. 전체 **169 passed**.
  - **T3.3 으로 넘길 것(여기서 안 함)**: 아카이브 인덱스의 `top_title` 이 `items.title` 원문이라
    긴 게 그대로 온다(실측 최장 159자 — NIST 기사). `headline` 컬럼이 이미 있으므로
    `store.list_digests()` 가 `COALESCE(headline, title)` 을 집으면 짧아진다. 다른 호출부에
    영향이 있어서 밀도 패스와 같이 판단하는 게 맞다.

- 2026-07-31: **T3.3 착수 — 실측 결과 스펙의 전제 3개가 틀렸다. 디자인은 사용자 캔버스 대기.**
  §13 T3.3. **결정(사용자): 새 Claude Design 캔버스를 만든 뒤 DesignSync 로 통합한다** —
  내가 임의로 시각 정체성을 만들지 않는다. 그래서 이번엔 (a) 실측·정정, (b) 디자인과 무관한
  수정, (c) 캔버스용 브리프까지 하고 멈췄다. 브리프: **`docs/design-brief-2026-07-31.md`**.
  - **[정정 1] "30건 넘는 다이제스트"는 아직 없다.** 스펙 Phase 6 의 전제였는데 실측 최대는
    **26건**(07-30)이다. 다만 **밀도 문제는 실재하고 위치가 특정된다** — 홈은 항목을
    lead 1 / grid3 3 / worth 4 / **brief 나머지**로 나누는데, 26건이면 brief 가 18건이다.
    그리고 랭킹 하위가 arXiv 라 **가장 좁은 구간에 가장 긴 제목이 온다**(실측 135·117·94·90·88자).
  - **[정정 2] "covered by N sources" 배지는 존재하지 않는다.** 스펙이 수용 대상으로 적어둔
    항목인데 템플릿에 그 문구가 없다. 실제로는 소스 줄의 **`(+N more)` 접미사**로 정착했고
    (`_source_line_name`), 그건 `cluster_sources`(소스 이름 집합)로 만든다.
    **`cluster_size` 컬럼은 어떤 템플릿도 읽지 않는다 — 저장만 되고 소비자가 없다.**
    그게 오히려 맞다: `cluster_size` 는 같은 소스가 두 번 올려도 2로 세지만 `cluster_sources` 는
    집합이라 "2개 소스가 다뤘다"가 참일 때만 붙는다.
    → **아직 게시된 적이 한 번도 없다.** 602건 중 `cluster_size=2` 가 2건, 그중 진짜 크로스소스는
    **1건(07-31 Hugging Face 침해 — BBC + TechCrunch)** 이고 그것도 `category_cap` 에 걸려
    안 실렸다. 📈 **곧 나온다** — BBC·Guardian 을 07-31 에 넣은 첫날 바로 TechCrunch 와 겹쳤다.
    설계 스펙이 예측한 그대로다. 캔버스는 이 자리를 비워둬야 하고, 실물이 없다고 빼면 며칠 뒤 깨진다.
  - **[정정 3] `Earlier:` 스레드도 실물이 2건뿐**이다(게시분 444건 중). 디자인할 표본이 거의 없다.
  - **[처리 완료] 아카이브 인덱스의 긴 제목.** `store.list_digests().top_title` 이 원제목이라
    최장 149자가 그대로 왔다. 두 가지를 했다:
    (1) **`COALESCE(NULLIF(headline,''), title)`** — 렌더의 `display_title` 과 규칙을 맞췄다.
        안 맞추면 같은 항목이 홈에선 짧고 아카이브 목록에선 길게 나온다.
    (2) **CSS 2줄 클램프** + 전문은 `title` 속성. 결과: 47행 중 90자 초과가 1행만 남음.
    ⚠️ **백필 414건 재엔리치는 안 한다**(사용자 결정, 유료 배치). 대신 CSS 로 처리.
    근거: **headline 커버리지는 07-31 부터 100%**(21/21), 07-30 은 9/26, 그 이전은 0 —
    즉 긴 제목은 **줄어드는 레거시 문제**이지 상시 문제가 아니다.
  - **DesignSync 는 이 세션에서 사용 가능하다** — 스펙에 "등록 안 됨"이라고 적힌 건 낡은 정보다.
    (2026-07-30 시점 기록이었고 지금은 tool 이 붙어 있다.) 캔버스가 생기면 export 손통합 대신
    DesignSync 경로를 쓸 수 있다.
  - 테스트 3건 추가(`top_title` 이 headline 우선 · 레거시 행 폴백 · 최고 significance 항목 선택).
    전체 **172 passed**.

- 2026-07-31: **T3.4 완료 — RSS 피드(`output/feed.xml`). §5 파킹 항목 해소.**
  §13 T3.4. **다이제스트 1개 = `<item>` 1개**로 만들었다(기사 1개 = item 1개가 아니다).
  근거: 이건 "데일리 다이제스트"라는 제품이고 랭킹·큐레이션 자체가 산출물이다. 기사 단위로
  쪼개면 (1) 하루 20건이 리더에 쏟아지고 (2) 원본 피드를 그대로 재방송하는 셈이 되며
  (3) 순위 정보가 사라진다. 대신 `description` 에 순위대로 `<ol>` 로 담아 리더 안에서
  그날 다이제스트를 그대로 읽게 했다(§5 가 말한 "리더/이메일 연동"의 실제 목적).
  - **검증 = `feedparser` 왕복.** 우리가 남의 피드를 *소비*할 때 쓰는 그 라이브러리로 우리
    출력을 다시 읽는다 — 문자열 비교보다 훨씬 강한 보장이다. 실측 `bozo=False`, 20 항목,
    일간/주간이 섞여도 시간순 정상(2026-W31 → 월요일 07-27 로 07-28 뒤에 놓임).
  - **`settings.site_url` 신설**(sources.yaml). **RSS 는 상대경로를 허용하지 않는다** — 기준
    URL 이 없으면 리더에서 전 링크가 깨진다. 그래서 **비어 있으면 피드를 만들지 않고 경고**한다
    (조용히 깨진 피드를 배포하는 것보다 없는 게 낫다).
    ⚠️ 현재 값은 `https://ujuappa.github.io/ai_news` — **레포 이름으로 추정한 값이라 실제 배포
    주소와 맞는지 확인 필요.** 커스텀 도메인이나 user-site 면 반드시 바꿀 것.
  - `description` 은 **이스케이프된 HTML**(RSS 규약). 템플릿 autoescape 가 그 일을 하므로
    `|safe` 를 쓰면 안 된다 — 원문 XML 에 `<ol>` 이 그대로 들어가면 구조가 깨진다. 테스트로 고정.
  - 페이지 head 에 `<link rel="alternate" type="application/rss+xml">` 추가(깊이별 경로).
    리더에 사이트 주소만 붙여넣어도 피드를 찾는다. `m.head_scripts(asset_prefix)` 로 확장.
  - 테스트 22건(`test_render_feed.py` 19 + store 3): well-formed · 특수문자/CJK · 다이제스트
    단위 · 리캡 없을 때 라벨 폴백 · 본문 랭킹 순서 · headline 폴백 · 절대 URL · site_url 없으면
    스킵 · 슬래시 중복 · 이스케이프(양방향) · 주간 라벨 월요일 · 파싱 불가 라벨 · guid 안정성 ·
    빈 피드 · 항목 0인 다이제스트 · 자동검색 링크 깊이 · store 정렬/limit/리캡 결측.
    전체 **197 passed**.

- 2026-07-31: **[발견] 게시된 6건이 지금 게이트라면 거부될 URL 이다 — 피드가 이걸 드러냈다.**
  피드를 만들자 첫 항목이 "Huawei Releases openPangu 2.0 Pro"인데 링크가 `aiweekly.co/`(라운드업
  홈페이지)였다. `llm._grounding_reject_reason` 을 게시분 445건에 돌려 확인한 결과:
  - **grounding 5건** — 07-30 `buildfastwithai.com/blogs/ai-news-today-july-29-2026`,
    07-31 `aiweekly.co/` · `buildfastwithai.com/...july-30-2026` · `ai.economictimes.com/` ·
    `buttondown.com/ai-tldr/archive/...`. **T2.1 게이트는 앞으로 들어올 것만 막는다 —
    이미 저장된 건 그대로 사이트와 피드에 남는다.** 제목/스토리는 진짜인데 링크가 집계 페이지라
    누르면 그 기사가 아니라 라운드업이 나온다.
  - **`hn_ai` 1건 — `learnvector.ai/`(맨 도메인)인데 이건 정상이다.** Show HN 류는 제품
    홈페이지를 링크하는 게 맞다. → **맨 도메인 규칙을 전역으로 올리면 안 된다는 근거.**
    현재 grounding 경로에만 걸려 있어서 문제없다. 나중에 "일반화하면 좋겠다"고 옮기지 말 것.
  - **→ (a) 로 처리 완료 (사용자 결정, 2026-07-31).** 5건을 `is_published=0` +
    `drop_reason='source_quality'` 로 내리고 재렌더. 게시 총계 **445 → 440**,
    `digests.item_count` 는 07-30 26→25 · 07-31 22→18 로 재계산.
    검증: 238개 HTML·`feed.xml` 어디에도 팜 도메인 문자열이 남지 않음, 피드 `bozo=False`,
    `digests.item_count` 가 실제 게재 수와 일치, **`learnvector.ai`(hn_ai)는 그대로 게재**.
    - **행을 지우지 않았다** — `drop_reason` 이 남아야 근거를 볼 수 있고(`dropped_items()`),
      `seen` 기록과도 어긋나지 않는다.
    - **`recheck_grounding_urls.py` 로 남겼다**(일회성 스크립트 아님). `sources.yaml` 에
      새 팜 도메인을 추가할 때마다 같은 상황(이미 게재된 건이 남는다)이 생긴다.
      기본은 보고만, `--apply` 로 실행. **`gemini_grounding` 소스에만 적용** — 스코프를
      넓히지 말 것(맨 도메인 규칙은 hn 계열에서 오탐이다, 위 learnvector 참고).
    - `store.unpublish()` / `store.recount_digest()` 신설. **내린 뒤 재계산이 필수** —
      아카이브 인덱스의 행·막대·푸터 숫자가 `digests.item_count` 에서 나오므로 안 하면 어긋난다.
      테스트 8건(`test_store_unpublish.py`: 행 보존 · 멱등 · 빈 리스트 · 지정 id 만 ·
      재계산 · 0건 다이제스트 · 검색 인덱스 이탈 · 피드 이탈). 전체 **205 passed**.
    - 부수 수정: `.gitignore` 의 `*.db.bak` → `*.db.bak*`. 타임스탬프 붙인 백업
      (`digest.db.bak-before-unpublish-...`)이 패턴에 안 걸려서 2MB DB 가 커밋될 뻔했다.
  - 참고: **크로스소스 클러스터가 2건으로 늘었다**(07-31). BBC+TechCrunch, 그리고
    Google News(AP)+Guardian. **둘 다 `category_cap` 에 걸려 안 실렸다.**
    corroboration 은 저장만 되고 **significance 에 전혀 반영되지 않는다** — 두 매체가 독립적으로
    다룬 스토리인데 랭킹 이득이 0이다. 랭킹 rubric 은 고정(§3)이라 여기서 손대지 않지만,
    **캡/하한 튜닝(§9)할 때 같이 볼 것.**
- 2026-08-03: **T3.3 완료 — UI/UX 2차 개편(Claude Design "AI Digest - Home" → DesignSync)**.
  §13 T3.3 이 기다리던 사용자 캔버스가 도착해서, 2026-07-27 과 같은 경로(DesignSync MCP)로
  가져와 포팅했다. 캔버스가 홈 1장이라 **홈 + 공용 크롬만** 바꾸고 나머지 페이지는 같은 크롬을
  쓰도록 색만 맞췄다. 이걸로 **완성 정의 4개가 전부 충족됐다.**
  - **크롬**: 다크 마스트헤드(`--bar` 바) 폐기 → 지면 위 라이트 헤더. 워드마크가 900/32px 로
    커지고, 메타 줄이 "Friday · 31 July 2026 · 18 stories · 440 in archive", 우측에 검색,
    아래에 밑줄형 탭 네비(Today / 카테고리 4 / Archive) + 우측 `Daily` 칩. 탭의 카운트 뱃지는
    뺐다(카운트는 홈 필터 pill 로 이동). **테마 스위처는 헤더 → 푸터**(캔버스 배치), 푸터에
    `Archive index` / `RSS` 링크 추가. `archive_index`/`archive_week`/`search` 의 다크
    `simple-header`·`search-hero` 도 라이트로 맞춤(안 그러면 사이트 안에서 헤더가 두 종류가 된다).
  - **홈**: 카테고리 필터 pill(클라이언트 사이드, 서버가 구운 DOM 을 숨기기만 함) → 이미지 슬롯이
    붙은 리드 스토리 → "Also today" 3열 카드 → "Worth knowing" 썸네일 행 + "In brief" 목록 +
    사이드바(Signal index / Source alert). 항목 분배(1 / 3 / 4 / 나머지)는 기존과 동일.
  - **캔버스와 다르게 한 것 3가지**:
    (1) **Sign in · Weekly · Monthly 를 뺐다** — 사용자 지시(2026-08-03), 구현이 없어서 누르면
        아무 일도 안 일어나는 UI 가 되기 때문. 사이드바의 "Follow sources" 카드도 로그인 종속이라
        같이 뺐다. 기간 토글은 현재 기간 표시(`Daily`)만 남겼고, 붙일 자리는 macros.html 에 주석.
    (2) **필터가 섹션까지 접는다** — 캔버스 데모는 항목만 숨겨서 "Also today / Stories 02 – 04"
        머리글만 남고 아래가 텅 비었다. `[data-section]` 에 남은 항목이 0이면 섹션째 숨긴다.
        같은 이유로 마감 밑줄을 `.worth-row:last-of-type` 이 아니라 섹션 바닥에 뒀다(마지막 행이
        필터로 숨으면 밑줄이 통째로 사라진다).
    (3) 리드 바이라인은 `Read at bbc.co.uk →`(호스트만). 기존 `domain_path` 를 그대로 쓰면
        `bbc.co.uk/news/articles/cr7k49xjzzeo?at_m…` 처럼 쿼리스트링이 노출됐다 → `_domain()` 신설.
  - **이미지**: 캔버스는 회사별 소스 마크를 쓰는데 파일이 아직 없다(사용자가 나중에 준비).
    지금은 **같은 크기의 빈 슬롯이 자리를 차지한다**(aspect-ratio 고정: 리드 4:3 / 카드 16:10 /
    썸네일 128px 4:3) — 나중에 이미지가 들어와도 레이아웃이 안 밀린다.
    `static/img/<source_id>.webp|jpg|jpeg|png|svg` 를 놓으면 `_image_for()` 가 잡고
    `_copy_images()` 가 `output/static/img/` 로 복사한다. 사용법은 `static/img/README.md`.
  - **상대시간**("5 hours ago" / "19h ago") 신설. 기준은 **now 가 아니라 그 다이제스트의 시각**
    (오늘자면 now, 과거면 그날 23:59 UTC) — now 로 잡으면 rerender 할 때마다 아카이브 사본의
    "4h ago" 가 "6d ago" 로 늘어나서 그날의 페이지가 아니게 된다(`_digest_ref`).
  - **팔레트는 안 건드렸다.** 캔버스 `_ds/.../styles.css` 의 `--color-*` 토큰은 Mist·Signal red
    팔레트와 값까지 1:1(bg=#f3f2f2, text=#201e1d, accent=#ec3013, neutral-400=#bab6b6 …)이라
    기존 변수로 그대로 매핑했다: bg→g, surface→g2, text→ink, accent→acc, accent-700→accd,
    neutral-400(테두리)→n2, neutral-600(메타)→n1, neutral-800(본문)→ink2. 5색 라이브 스위처
    그대로 동작. `test_render_assets.py` 가 "CSS 가 쓰는 var 는 전부 PALETTES 키" 를 고정하고
    있어서 `--color-*` 를 들여오는 건 애초에 불가능했다(그 테스트가 제 역할을 했다).
  - 검증: `python rerender.py`(238페이지, API 비용 0) 후 헤드리스 크롬으로 홈/카테고리/아카이브
    인덱스/주간/검색 + 모바일(520px) + 필터 2종(Research 3건, Policy 8건) 스크린샷 확인.
    전체 **205 passed**(테스트 변경 없음 — 계약을 안 깨고 바꿨다는 뜻).
- 2026-08-04: **grounding soft-404 — 죽은 링크가 리드 기사로 실렸다.** 사용자가 홈 리드
  "Alibaba Launches Qwen3.8-MAX"(significance 0.80)를 눌렀는데 `www.futunn.com/404` 였다.
  - **원인은 상태코드 게이트의 사각지대다.** futunn 은 없는 기사를 `/404` 로 302 시키고
    **그 페이지가 200 을 준다**(soft 404). 그래서 `resolve_url` 의 `status_code < 400` 이
    통과시키고 **최종 URL 인 `/404` 를 기사 주소로 반환**했다. 그 다음 `_grounding_reject_reason`
    도 못 잡는다 — `/404` 는 경로가 비어있지 않아 `bare_domain` 이 아니고, 도메인·슬러그
    블록리스트에도 없다. `resolve_url` 도크스트링에 적혀 있던 "지어낸 404 URL 을 걸러낸다"는
    **HTTP 404 를 실제로 주는 사이트에만 성립하는 이야기였다.**
  - id 가 `sha1(최종 URL)` 이라 **지어낸 죽은 futunn 주소 아무거나 넣어도 저장된 id
    `d8499504cab94cfb` 가 그대로 재현된다**(실측). 기사 주소가 이미 죽은 상태로 들어왔다는 증거이자,
    앞으로 futunn 죽은 링크가 전부 같은 id 로 접히는(=조용히 dedup 되는) 부작용이기도 하다.
  - **1회성이 아니었다.** 게시된 grounding 14건을 전수 조사하니 **전부 200 을 준다** — 상태코드로는
    아무것도 구분 못 한다. 반면 도착 페이지의 `<title>` 은 깨끗하게 갈린다:
    정상 8건은 주장 제목과 **최소 3토큰 겹치고(비율 1.00)**, 불량 6건은 **전부 0토큰**이었다.
    `app.rebrandly.com/broken-links`("Rebrandly Dashboard", 08-02)가 같은 부류로 같이 잡혔다.
  - **고침**: `fetch.resolve_url` → **`fetch.resolve_article`** 로 바꿔 `(최종 URL, <title>)` 을
    돌려준다. 제목이 필요하므로 GET 을 먼저 쓰고(HEAD 는 본문이 없다) `TITLE_READ_BYTES`(200KB)
    까지만 스트리밍해서 읽는다. 판정은 `_grounding_reject_reason` 이 두 겹 추가로 한다 —
    `soft_404`(제목이 404/Page not found/頁面不存在 류) + `title_mismatch`(주장 제목과 겹치는
    토큰 2개 미만). **경계 2 는 실측 마진에서 나왔다**(정상 최소 3 vs 불량 0).
  - **일부러 느슨하게 둔 곳 2가지**: 제목을 못 얻으면(HEAD 폴백/파싱 실패) 검사를 **생략**한다 —
    우리 쪽 실패를 이유로 멀쩡한 기사를 버리지 않기 위해서다. 같은 이유로 토큰은 라틴/숫자만 세서
    **CJK 전용 제목은 0토큰 → 검사 생략**이 된다(언어를 이유로 버리지 않는다).
  - **기존 2건은 지우지 않고 유의성만 낮췄다**(사용자 지시: "맨 아래 참고 기사로"). futunn
    0.80 → **0.25**, rebrandly 0.50 → **0.35**. 각 날짜의 당시 최저값(0.30 / 0.40)보다 낮게
    잡아야 실제로 맨 아래에 간다 — 홈은 `_flatten_ranked` 가 significance 플랫 정렬이고
    동점이면 최신 발행이 앞이라 floor 와 동점으로 두면 중간에 낀다. 결과: 08-04 리드가
    Skunk Works(0.70)로 바뀌고 문제의 항목은 18/18 위치. **`rerender.py` 는
    `group_by_category(items)` 를 settings 없이 부르므로 하한이 재적용되지 않는다**(정렬만).
    다만 두 값 모두 카테고리 하한(model_releases 0.30 / policy_business 0.40) 아래라,
    **오늘자를 `python pipeline.py` 로 다시 돌리면 `category_floor` 로 내려간다**(의도한 동작).
  - 검증: 실제 14건을 새 게이트에 그대로 통과시켜 **keep 8 / reject 6**(soft_404 1 ·
    title_mismatch 1 · 기존 도메인 규칙 4) 확인. `test_grounding_quality.py` 에 회귀 테스트
    18건 추가(사고 재현 2건 · 정상 제목 쌍 4건 · 생략 조건 3건 · `resolve_article` 계약 6건 등).
    전체 **254 passed**, `pipeline.py --dry-run` 정상, `rerender.py` 재생성.
- 2026-08-04: **링크 사후 점검(`linkcheck.py`) + 죽은 링크의 href 제거.** 위 게이트는 *실을 때*
  만 본다. 기사는 실린 뒤에도 죽는다 → 게재분을 다시 찔러 `items.link_status` 에 남기고,
  렌더가 그 값을 보고 링크를 뗀다. 사용자 지시로 "죽은 링크는 평문으로".
  - **판정 로직을 `fetch` 로 옮겼다**(`dead_page_reason`). grounding 게이트와 링크 점검이
    **같은 기준**을 써야 "실을 땐 통과였는데 지금은 죽었다"가 진짜 link rot 을 뜻한다.
    `llm._grounding_reject_reason` 은 이제 그걸 호출만 한다.
  - **가장 중요한 교훈 — "못 받았다"를 죽은 링크로 부르면 안 된다.** 첫 구현은
    `DEAD_LINK_STATUSES = ("unreachable", "soft_404")` 였는데, 최근 40건 실측에서 **멀쩡한
    기사 3건**을 죽일 뻔했다: `wsj.com` 은 **401**(페이월 — 구독자는 읽는다),
    `washingtonpost.com` 은 **ConnectionError**(봇 차단). 그래서 `fetch.probe_url` 이
    상태코드를 버리지 않고 그대로 넘기고, 죽은 링크는 **서버가 없다고 명시한 경우로 한정**했다:
    `DEAD_LINK_STATUSES = ("gone"(404/410), "soft_404")`. `blocked`/`unreachable`/
    `title_mismatch` 는 리포트만 하고 사람이 판단한다.
  - **`title_mismatch` 를 자동 제거에서 뺀 게 옳았다는 증거**: 497건 전수에서 16건이 떴는데
    상당수가 `deepmind.google`·`apnews.com` 이 **게시 후 제목을 갈아끼운** 살아있는 기사였다
    ("Enabling a new model for healthcare with AI co-clinician" → "AI co-clinician:
    researching the path toward AI-augmented care"). 수집 시점엔 버려도 되지만 사후엔 아니다.
  - **전수 결과(497건)**: ok 475 · title_mismatch 16 · unreachable 4(전부 WaPo) ·
    blocked 1(WSJ) · soft_404 1(futunn) · **gone 0**. 아직 진짜로 삭제된 기사는 없다.
  - **부수로 잡은 버그 2개**(둘 다 실측에서 드러남):
    (1) `store.links_to_check` 의 `ORDER BY digest_date DESC` 가 주간 라벨을 전부 위로
        올렸다('W'(0x57) > '0'(0x30) — `label_sort_key` 가 경고하던 바로 그 함정).
        `--limit 40` 을 줬더니 백필 주간분만 잡히고 그날 리드(futunn)가 안 들어왔다 →
        파이썬에서 `label_sort_key` 로 정렬.
    (2) `_page_title` 이 charset 미선언 페이지를 requests 기본값 ISO-8859-1 로 읽어
        deepmind 제목이 `â` 로 깨졌다. **CJK 소프트404 문구('頁面不存在')도 이 경로로 깨지면
        못 잡는다** → 서버가 charset 을 선언했을 때만 그걸 믿고 아니면 UTF-8.
  - **렌더**: `<a>` 를 `<span>` 으로 바꾸지 않고 **href 만 뗀다** — href 없는 `<a>` 는 HTML5
    플레이스홀더라 클릭도 탭 포커스도 안 되고, 9곳의 중첩 마크업을 그대로 둘 수 있다
    (`templates/macros.html` `href` 매크로). 리드는 "Link no longer available" 로 바뀐다.
    **피드·검색도 같이 막았다** — 사이트에서만 떼면 RSS 구독자는 계속 404 를 맞는다.
  - 검증: `tests/test_linkcheck.py` 30건 신설(분류표 · 렌더 계약 · 인코딩 · probe 계약).
    `fetch.resolve_article` 계약 테스트는 grounding 파일에서 이리로 옮겼다. 전체 **279 passed**.
- 2026-08-04: **홈 필터를 카테고리 → 토픽으로 교체.**
  설계 문서: `docs/superpowers/specs/2026-08-04-topic-filters-design.md`.
  사용자 지시: "상단 바 카테고리는 그대로 두고 필터만 바꿔라."
  - **왜**: 홈 필터 pill 이 상단 네비게이션과 **똑같은 4개**를 반복해 한 줄을 쓰면서 아무것도
    더해주지 않았다. 카테고리는 "어떤 종류의 사건인가"(모델 출시/연구/제품/정책)이고,
    토픽은 "무엇에 관한 이야기인가"(음악·정부·코드)라 서로 직교한다.
  - **어휘**: `config.TOPIC_ORDER` 13개(code money chips government security science health
    art music video robotics cars education). **`CATEGORY_ORDER` 와 절대 합치지 말 것** —
    그 상수는 `sources.yaml` 최상위 소스 그룹 키를 겸해서, 넣는 순간 소스 버킷이 된다.
  - **설계를 정한 실측 두 가지**(아카이브 497건 키워드 스캔):
    (1) 꼬리가 길고 얇다 — 13개를 다 내보내면 하루에 pill 이 **8~9개**인데 대부분 1~2건이다.
        한 건짜리 필터는 필터가 아니다 → **그날 많은 순 top-6** (`render.TOPIC_PILL_CAP`).
    (2) 26%가 토픽 2개 이상에 걸린다 → 카테고리와 달리 **다중 라벨**.
  - **검증은 하되 믿지는 않는다**: `llm.clean_topics` 가 어휘 밖 값을 버리고, 중복을 없애고,
    3개(`MAX_TOPICS_PER_ITEM`)로 자르고, TOPIC_ORDER 순으로 정규화한다(순서가 모델 나열
    순서를 따라가면 재렌더마다 `data-topics` 가 흔들린다). image_key 와 같은 이유·같은 패턴.
    상한이 없으면 모델이 5개씩 달아서 모든 pill 이 모든 기사를 담는다.
  - **필터 JS**: 카테고리는 하나라 `===` 로 됐지만 토픽은 여러 개라 토큰 비교로 바꿨다.
    양쪽에 공백을 덧대지 않으면 `art` 가 `chart` 에 걸린다. 토픽 없는 기사는
    `data-topics=""` 라 All 에서만 보인다(사라지지 않는다). CSS 는 `.is-filtered` 만 보므로 무변경.
  - **백필**: `backfill_topics.py` 로 아카이브 515건 분류(8배치, 실패 0). 356건에 토픽이 붙고
    99건은 무토픽(≈30%, 키워드 스캔의 27%와 일치). 분포: code 118 · security 88 ·
    government 57 · money 53 · science 48 · chips 39 · health 31 · music 16 · education 15 ·
    art 14 · robotics 12 · video 5 · **cars 0**. 요약/significance 는 건드리지 않는다
    (과거 다이제스트 내용이 바뀌면 안 되므로 분류 전용 프롬프트 `llm.TOPIC_ONLY_SYSTEM`).
    `topics='[]'` 인 것만 고르므로 중단 후 재실행하면 이어서 한다.
  - **아카이브에도 같은 필터를 달았다(같은 날 추가).** 설계 초안에 "아카이브도 home.html 을
    공유하니 자동으로 붙는다"고 썼는데 **틀렸다** — `render_digest` 가 굽는
    `index.html` + `archive/<오늘>.html` 만 home.html 이고, 나머지 아카이브 페이지는 전부
    `render_archive_digest` → `archive_week.html` 이라 필터 줄이 아예 없었다(카테고리 시절부터).
    그래서 필터 줄과 스크립트를 **`macros.html` 로 빼서 두 템플릿이 공유**하게 했다 —
    애초에 home.html 안에만 있었던 게 아카이브가 빠진 원인이다. 지금은 아카이브 다이제스트
    51페이지 전부에 pill 이 있다(나머지 201개는 카테고리 페이지·인덱스라 원래 대상이 아니다).
    두 가지가 필요했다: (1) 리드/2위가 kicker·제목·요약이 흩어진 형제 요소라 통째로 숨길 수가
    없어서 `.week-lead-item`/`.week-sec-item` 래퍼로 감쌌다(week-lead-col 에 자식 선택자가
    없어 레이아웃 영향 없음), (2) 2열 격자에서 한 열이 통째로 숨으면 빈 칸이 남는데
    (리드가 그 토픽이 아닌 건 흔하다) `.week-split:has(> .is-filtered)` 로 1열로 접는다.
  - 검증: `tests/test_topics.py` 36건 신설. 전체 **315 passed**. 실제 결과 —
    오늘 `All 18 | Code 5 | Chips 5 | Government 5 | Money 4 | Security 3 | Science 1`,
    아카이브 `2026-07-30` `All 25 | Money 10 | Code 7 | Chips 4 | Government 3 | Security 3 | Science 3`.
- 2026-08-06: **홈 상단 재편 — Claude Design 캔버스 "Home Top Organization" 6a 포팅.**
  캔버스는 turn 6개(1a~6a)로, 홈 상단을 조직하는 방법 네 가지에서 시작해 6a 로 수렴했다.
  가져온 것 · 안 가져온 것 · 그 이유:
  - **마스트헤드가 2단 → 한 줄.** 워드마크 + 빨간 점(`.mh-dot`, 색은 `--acc` 라 팔레트를 따라간다)
    · 검색 · pill 네비. 밑줄 탭이 pill 로 바뀌었고 현재 카테고리는 채운 pill(`.active`)이 표시한다.
    `Today` pill 은 없앴다 — 6a 기준 워드마크가 홈 링크고, 그날 건수는 아래 stat 쌍이 말한다.
  - **날짜/건수가 헤더에서 지면으로 내려왔다**(`.page-head`): 날짜 칩 · 디스플레이 제목
    ("Today's news, *ranked by significance*") · 한 줄 설명 · stat 쌍(오늘 N / 아카이브 N).
    카테고리·검색 페이지는 기간 컨트롤이 없으므로 `masthead(show_meta=true)` 로 헤더에 기간을
    계속 적는다(홈만 `false`).
  - **리드 + Also today 가 한 장의 카드(`.panel`)로 묶였고, 기간 세그먼트와 필터가 그 카드에
    붙었다.** 6a 의 논지가 그거다 — 컨트롤은 자기가 걸리는 대상 위에 얹혀야 한다(5a 에서 컨트롤
    줄을 페이지 최상단에서 뉴스 위로 내린 것과 같은 이유: 그 줄은 다이제스트만 필터한다).
  - **필터 pill 줄 → 컨트롤 줄 + 서랍, 그리고 다중선택.** `filter_row` → `control_line`.
    `Filters` 버튼이 서랍을 열고, 고른 토픽은 제거 가능한 chip 으로 줄에 남는다.
    이 때문에 **`TOPIC_PILL_CAP`(top-6)이 없어졌다** — 상한의 이유가 "pill 을 한 줄에 늘어놓으면
    넘친다"였고, 서랍은 넘치지 않는다. 이제 그날 붙은 토픽 전부를 고를 수 있다(1~2건짜리 포함).
    'All' pill 도 없어졌다 — 아무것도 안 고른 상태가 곧 All 이다.
    다중선택은 **OR** 다: AND 로 하면 항목당 토픽이 최대 3개(`MAX_TOPICS_PER_ITEM`)라 두 개만
    골라도 거의 항상 0건이 된다.
  - **함정 하나 — 컨트롤 줄은 `.panel-body`(data-section) 밖에 둬야 한다.** 안에 두면, rank 9
    이하에만 달린 토픽을 골랐을 때 카드 속이 통째로 숨으면서 필터 자신도 같이 사라져
    **되돌릴 수단이 없어진다.** `tests/test_topics.py::test_the_filter_cannot_hide_its_own_undo_control`
    로 못박았다.
  - **팔레트 6번째 추가: `Boncom · Maroon`**(사용자 결정). 6a 는 Mona Sans + Playfair Display
    italic · radius 12~16 · 그림자를 쓰는 별도 시스템으로 그려졌는데, **색만** 팔레트로 들여왔다.
    폰트와 radius 는 팔레트 변수가 아니라 전역이므로 Archivo 한 벌 · radius 0 · 고도는 테두리가
    그대로 유지된다. 6a 의 maroon(#4a0e1f)은 링크색이라 `--accd`, 빨간 점(#ff1a22)은 `--acc`.
    제목의 Playfair italic 대위는 `italic + --accd`(`.ph-em`)로만 가져왔다.
  - **안 가져온 것 = 6a 마크업의 약 40%**(사용자 결정): 카드 아래 "Below the digest" 구획과
    Updates(팔로우 + 내 코멘트 + Public/Private 작성기) · Today's judgment(남들 코멘트) ·
    quiet ticker, 그리고 헤더의 `Following 8` · `Monthly` pill. 전부 로그인 + 쓰기 백엔드가
    있어야 하는데 이 사이트는 GitHub Pages 정적 산출물이라 붙이면 죽은 버튼이 된다
    (§10.1 "정적 사이트에 로그인 붙이기는 함정" 과 같은 결론). 붙일 자리는 `templates/home.html`
    끝 주석에 적어 뒀고, `test_masthead_carries_no_link_that_goes_nowhere` 가 새는 걸 막는다.
    `Monthly` 는 spec(`docs/superpowers/specs/2026-08-04-weekly-monthly-periods-design.md`)만
    있고 코드가 없어서 같은 이유로 제외 — 기간 세그먼트는 여전히 `Daily` 표시 하나뿐이다.
  - **서랍의 `Lab` 그룹도 안 넣었다** — 캔버스 자신이 4b·5i 에서 "Lab 그룹은 아직 읽을 게 없다"고
    적어 뒀다. source→lab 매핑이나 분류기 필드 + 백필이 선행 조건이다.
  - **6a 가 그리지 않은 것은 지우지 않았다.** 6a 는 "Home **Top** Organization" 이라 상단만
    그린 시안이고 Worth knowing / In brief / Signal index 사이드바가 등장하지 않는다. 문자
    그대로 옮기면 그날 17건 중 13건이 홈에서 사라진다(6a 의 stat 은 17을 그대로 세고 있다) —
    그래서 카드 아래에 그대로 남겼다. 테마 스위처 푸터도 유지.
  - 아카이브 사본(`archive/<날짜>.html`)은 디스플레이 제목만 "That day's news" 로 갈랐다 —
    같은 본문을 두 URL 에 굽는 구조라, 안 갈라 놓으면 몇 달 뒤에 아카이브가 "Today's news"
    라고 우긴다(`test_archived_copy_does_not_claim_to_be_today`).
  - 검증: 전체 **321 passed**(신규 6건 — 위 함정 2건 + 6a 블록 존재 + 죽은 링크 없음 +
    팔레트 키 완전성). 필터 동작은 렌더된 실제 페이지를 jsdom 에 올려 22개 항목으로 확인
    (초기상태 · 서랍 토글 · 단일선택 · OR · chip 제거 · 전체해제 · 카드 밖 토픽 · 빈 섹션 숨김).
    `rerender.py` 로 252페이지 재생성 완료(API 비용 0).
  - ⚠️ jsdom 실행 중 `head_scripts` 의 `localStorage.getItem` 이 opaque origin 에서
    SecurityError 를 던지는 걸 봤다. **이번 변경과 무관한 기존 코드**이고 http(s)/file 에서는
    나지 않지만(테마 스위처는 실제로 동작 중), sandboxed iframe 같은 데서 첫 페인트 스크립트가
    통째로 죽을 수 있으므로 try/catch 를 씌울 값은 있다 — 이번 스코프 밖이라 손대지 않았다.

- 2026-08-06: **Pages 배포에 push 트리거 추가** (`.github/workflows/daily.yml`).
  6a 를 머지·push 한 뒤에 "사이트가 안 바뀐다"를 만난 게 계기다 — 워크플로 트리거가
  `schedule` + `workflow_dispatch` 뿐이고 **Pages 배포 job 이 그 워크플로 안에** 있어서,
  디자인만 바꿔도 다음 cron(14:00 UTC)까지 기다리거나 수동 실행으로 **전체 파이프라인(=Gemini
  API 비용)** 을 태우는 수밖에 없었다.
  - `push: branches: [main]` 을 추가하고, `setup-python`·`pip install`·`Run pipeline`·
    `Commit digest + state` 네 스텝에 `if: github.event_name != 'push'` 를 걸었다.
    push 이벤트에서는 `checkout` + `Upload Pages artifact` 2스텝만 돌고 `deploy` 가 이어진다
    (schedule/dispatch 는 6스텝 그대로). torch 를 끌어오는 pip install 도 건너뛴다.
  - **전제: 커밋된 `output/` 이 곧 배포물이다.** 빌드가 렌더를 다시 하지 않으므로 템플릿만
    고치고 push 하면 예전 지면이 재배포된다 → `python rerender.py` 로 구운 `output/` 을 반드시
    같이 커밋해야 한다. CLAUDE.md 상단에 순서를 적어 뒀다.
  - **무한 루프 없음**: cron 이 스스로 push 하는 `digest: <날짜>` 커밋은 GITHUB_TOKEN 으로
    만들어지고, GitHub 은 GITHUB_TOKEN 이 만든 이벤트로 새 워크플로 실행을 시작하지 않는다.
  - `paths` 필터는 **일부러 안 걸었다.** 문서만 고친 push 에도 배포가 한 번 도는 건 낭비지만
    (API 비용 0, 30초), 경로 필터를 잘못 적으면 **디자인 변경이 조용히 배포되지 않는** 훨씬
    나쁜 실패 모드가 생긴다.
  - 검증: YAML 파싱 + 세 이벤트(schedule/dispatch/push)별 실행 스텝 시뮬레이션으로
    2스텝 vs 6스텝 확인. 이 커밋의 push 자체가 첫 실물 테스트다.

- 2026-08-06: **야간 실행 실패 조사 + CI 를 CPU 전용 torch 로 전환.**
  08-06 실행 2회(#29 schedule 16:02Z, #30 dispatch 20:04Z)가 실패해서 **그날 다이제스트가
  아예 생성되지 않았다**(마지막 성공은 #28, 08-05). 둘 다 `3d2726f` 기준이라 이날 작업한
  6a 포팅과는 **무관하다**.
  - 실패 메시지: *"The hosted runner lost communication with the server. Anything in your
    workflow that terminates the runner process, starves it for CPU/Memory, or blocks its
    network access can cause this error."* → 러너가 통째로 죽은 형태라 **스텝 로그에 원인이
    남지 않았다**(파이썬 트레이스백이 없다). 스텝별 로그는 인증 없이는 못 읽는다.
  - **실측한 것**: PyPI 기본 리눅스 휠이 CUDA 빌드다 — torch 526MB · nvidia-cudnn 366 ·
    nccl 206 · cusparselt 170 · triton 198 · nvshmem 60 ≈ **휠만 1.5GB**, 여기에
    `cuda-toolkit[cublas,cudart,cufft,cufile,cupti,curand,cusolver,cusparse,nvjitlink,nvrtc,nvtx]==13.0.3`
    11종이 더 붙는다(크기 미측정). 압축 풀면 몇 GB. **러너에는 GPU 가 없고** 우리가 하는 일은
    22MB all-MiniLM-L6-v2 를 CPU 로 돌리는 것뿐이다. CPU 전용 휠은 **191MB 하나 + nvidia 의존성 0**.
    → 디스크/메모리 압박이 가장 유력한 원인이라 보고 여기를 고쳤다.
  - **고친 것 (1) CI 가 torch 를 CPU 인덱스에서 먼저 깐다**:
    `pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.13,<2.14"` 를
    `pip install -r requirements.txt` **앞에** 둔다. 순서가 핵심 — torch 를 먼저 만족시켜 두면
    뒤이은 설치가 sentence-transformers 의 `torch>=1.11` 을 충족된 것으로 보고 CUDA 판을
    안 끌어온다. 임베딩은 **바뀌지 않는다**: 같은 모델·같은 가중치이고, 애초에 러너에 GPU 가
    없어서 CUDA 빌드도 CPU 커널로 추론하고 있었다 → dedup 임계값 0.83 그대로 유효,
    `--reset` 이나 `backfill_embeddings.py` 재실행 **불필요**.
  - **고친 것 (2) `sentence-transformers` 상한**: 예전엔 `>=3.0` 이라 야간 실행이 매일 최신을
    집어갔다. 08-05 성공은 5.6.1, 08-06 에 **5.7.0 이 릴리스**됐고 그날부터 실패다.
    다만 **5.7.0 의 선언된 의존성은 5.6.1 과 완전히 동일해서 5.7.0 이 원인이라는 증명은 아니다** —
    그래서 이 핀은 범인 지목이 아니라 재현성 확보다(야간 자동화가 업스트림 릴리스에 매일
    노출되면 안 된다). 실제로 성공한 조합인 `>=5.6,<5.7` 로 고정, `torch>=2.13,<2.14` 도 명시.
    5.7 로 올릴 때는 CI 초록 확인 후 **의도적으로**.
  - **고친 것 (3) 진단 + 안전장치**: 설치 후 `df -h` / `free -m` / torch·st 버전을 찍는
    `Runner resources` 스텝 추가(다음에 죽으면 원인이 한눈에 보이게), build job 에
    `timeout-minutes: 30`(정상은 10분 안쪽인데 상한이 없으면 죽은 실행이 기본 6시간을 붙잡는다).
  - **검증의 한계**: 로컬(맥)에서 321 passed + `--dry-run` 으로 실제 MiniLM dedup 정상
    (120건 → cross-day 후 신규 120, 26 items 렌더) 확인. requirements 핀은
    `pip install --dry-run` 으로 전부 satisfied 확인. **CPU 휠 해석은 리눅스 러너에서만
    최종 확인된다** — cp312 manylinux CPU 휠(191.8MB)이 인덱스에 실제로 존재하는 것까지만 확인했다.
  - ⚠️ 별건: `pipeline.py --dry-run` 은 `output/` 에 발췌본을 덮어쓴다(DB 는 안 건드림).
    스모크 테스트로 돌린 뒤에는 `python rerender.py` 로 되돌려야 한다 — 이번에 두 번 밟았다.

- 2026-08-07: **캔버스 "Home Top Organization" 2차 — Boncom 조판 전면 도입 + Wire 티커.**
  같은 캔버스(6a)를 다시 가져왔더니 08-06 포팅 이후 디자인 쪽이 두 군데 움직여 있었고,
  프로젝트에 `handoff-differences.md`(디자인 ↔ 사이트 10항목 차이표)가 새로 들어와 있었다.
  그 10항목 중 **막힌 것(로그인·쓰기 백엔드가 필요한 §4 Below the digest, §5 Lab 그룹,
  §6 Weekly/Monthly)은 08-06 판단 그대로 두고**, 나머지를 반영했다.
  - **§1·§8 조판 전면 교체(사용자 결정).** 08-06 에는 "색만" 들여왔는데 — 폰트/radius 가
    팔레트 변수가 아니라 전역이라는 이유였다 — 이번에 그 결정을 뒤집어 6a 가 그려진 Boncom
    시스템을 통째로 가져왔다. Archivo(6웨이트 정적) → **Mona Sans**(가변, `wdth` 75~125 ·
    `wght` 200~900) 한 벌, `.ph-em` 에 Playfair Display italic, radius 16/12/999(6a 값 그대로,
    검색창만 8), 고도는 테두리 → 2단 그림자. CSS 의 폰트 스택 96곳을 일괄 교체.
    - **`font:` 단축이 `font-variation-settings` 를 리셋한다** — 그래서 축(wdth) 레이어는
      `digest.css` **맨 끝**에 있어야 한다. 앞에 두면 조용히 지워져서 wdth 75/90/110/125 가
      전부 100 으로 렌더되는데, 눈으로는 "폰트가 좀 넓네" 정도로만 보인다.
      `test_the_axis_layer_comes_after_every_font_shorthand` 로 못박았다.
    - 축은 **`wdth` 만** 준다. `wght` 까지 적으면 그쪽이 font-weight 를 이겨서 굵기를 정하는
      곳이 두 군데가 된다(기존 규칙 96개의 font-weight 를 전부 옮겨야 했을 것이다).
      배정은 6a 대로 — 캡스 라벨 75 · 제목 90 · 리드 110 · 디스플레이 125 · 나머지 100.
    - **값 막대는 일부러 각지게 뒀다**(signal index · 아카이브 볼륨 · stat-band). 한 번 둥글려
      보고 되돌렸다: 12px 캡을 씌우면 짧은 막대가 부풀어 보여 9건 vs 25건 비교가 왜곡되고,
      0건 막대가 점으로 남았다. 위아래 2px 선만 있는 stat-band 는 모서리에서 선이 말렸다.
  - **§2 지면 머리 제목 → 워드마크(사용자 결정).** 캔버스가 `Today's news, ranked by
    significance` 에서 `AI Digest` + 빨간 점으로 갈아탔다. 캔버스에는 별도 마스트헤드 줄이
    없어서 그 h1 이 곧 워드마크지만 **이 사이트는 `.mh` 헤더에 이미 워드마크가 있다** →
    홈에서만 워드마크가 위아래로 두 번 나온다. 사용자가 그 중복을 알고 캔버스 쪽을 택했다.
    "Today's news / That day's news" 구분은 없어지지 않고 **카드 머리글(`.panel-h`)로 옮겨
    살아 있다** — 기존 회귀 테스트가 그대로 통과한다.
  - **§3 Wire 티커(신설).** 마스트헤드와 지면 머리 사이를 흐르는 한 줄: 캡스 라벨 + significance
    + 헤드라인. 담는 건 **랭킹 05 이하 전부**(= 지면의 Worth knowing + In brief). 자르지 않는다.
    - **재생 시간을 항목 수로 계산한다(항목당 8s, 최소 30s)** — 캔버스의 60s 는 6건짜리 목업
      기준이라 그대로 쓰면 30건 오는 날 4~5배 빨리 흘러 못 읽는다. 실측: 9건 → 72s.
    - 끊김 없는 루프를 위해 같은 목록을 두 벌 굽고 `-50%` 로 민다(캔버스 `dvtick` 과 같다).
      **사본은 `aria-hidden` + `tabindex="-1"`** — 안 그러면 스크린리더가 같은 기사를 두 번
      읽고 탭 순서에도 두 번 걸린다.
    - `prefers-reduced-motion` 이면 애니메이션 대신 **가로 스크롤**로 준다(사본은 숨김).
      애니메이션만 끄면 화면 밖으로 나간 항목을 영영 못 본다.
    - `data-scope` **밖**에 둔다 — 토픽 필터가 티커까지 숨기면 "지금 안 보는 것"을 흘려보내는
      티커의 뜻이 없어진다.
  - **덤으로 찾은 실제 버그: 필터 서랍이 08-06 이후 계속 열려 있었다.**
    `.filter-drawer{display:grid}` 가 브라우저 기본 `[hidden]{display:none}` 을 이긴다
    (저작자 규칙 > UA 규칙). 그래서 `Filters` 버튼은 `aria-expanded` 만 뒤집는 죽은 토글이었고
    서랍은 늘 펼쳐져 있었다(6a 는 닫힌 채로 시작한다). jsdom 테스트는 `hidden` 속성만 봐서
    못 잡았다 — **실제 브라우저로 스크린샷을 찍다가 눈으로 발견**했다. `[hidden]` 짝을 추가.
  - **검증**: 전체 **333 passed**(신규 12건). 헤드리스 Chrome 으로 실제 지면을 열어
    서랍 열림/닫힘(`display: none → grid → none`) · 필터(chip 1개, 9 숨김/4 노출) ·
    티커(72s, wire-scroll) · 폰트 축(`.ph-title` = wdth 125, 캡스 = wdth 75)이 브라우저에서
    실제로 적용되는 것까지 확인. 홈/카테고리/검색/아카이브 인덱스/주간 5종 스크린샷 육안 확인.
    `rerender.py` 로 전체 재생성 완료(API 비용 0).
  - **안 한 것**: 기본 테마는 여전히 `Mist · Signal red`(4번) 다 — 조판만 Boncom 이고 색은
    사용자가 고르는 값이라 임의로 바꾸지 않았다. 팔레트에서 `Boncom · Maroon` 을 고르면
    6a 와 완전히 같은 지면이 된다. §9(Worth knowing / In brief / Signal index 사이드바)는
    캔버스가 아직 그린 적이 없어서 조판만 따라 바뀌고 구조는 그대로다.

- 2026-08-11: **소스 지면 + 브라우저 admin(소스·토픽 CRUD) + 저장/팔로우.** 사용자 요청 3건을
  한 세션에 넣었다. **이 항목은 §10.1·§13.4 의 결정을 부분적으로 뒤집으므로 근거를 남긴다.**
  - **왜 결정이 바뀌었나**: 요청은 "소스 목록 지면 + 추가/수정/삭제", "북마크 + 그 기사와 비슷한
    토픽 팔로우", "필터 토픽도 같은 식으로 CRUD" 였다. 앞의 두 개는 §10.1("정적 사이트에 로그인
    붙이기는 함정") · §13.4(§10 개인화는 회사행 확정 뒤) 와 정면으로 부딪힌다. 선택지 4개를
    사용자에게 제시했고(로컬 admin 서버 / **브라우저에서 GitHub API** / 브라우저 전용 가짜 CRUD /
    실제 백엔드), 사용자가 **GitHub API** 를 골랐다. §10.1 은 여전히 유효하다 — 우리가 인증을
    구현하지 않았고, 서버도 세션도 없다. GitHub 이 인증을 대신하고 우리는 그 API 를 호출만 한다.
  - **토큰**: 산출물에 비밀값이 **하나도 없다.** 사용자가 런타임에 fine-grained PAT 을 붙여넣고
    그 브라우저 localStorage 에만 남는다. 그래서 공개 레포/공개 사이트여도 유출이 없고, 남이
    `admin.html` 을 열면 토큰이 없어 아무것도 못 한다. §10.5 의 "키 노출 3회" 를 반복하지 않는
    유일한 형태다. `tests/test_admin.py::test_admin_page_ships_no_credentials` 가 토큰 모양의
    문자열을 산출물에서 정규식으로 잡는다(placeholder 의 `github_pat_…` 는 유니코드 줄임표라
    통과한다). 권장 권한은 **이 레포 하나 + Contents:RW**, Actions:RW 는 "Run pipeline now"
    에만 필요하고 없으면 그 버튼만 비활성이다.
  - **`sources.yaml` 을 admin 이 절대 쓰지 않는다** — 그 파일은 주석 240줄이 곧 결정 근거인데,
    브라우저에서 YAML 을 파싱해 다시 뱉으면 주석은 표현이 아니라 버려지는 토큰이라 **전부
    사라진다.** 그래서 손 편집용 원본(`sources.yaml`)과 기계 편집용 오버레이를 분리했다:
    - `sources.custom.json` — id 로 매칭해 얹는다. base 에 없는 id = 추가, 있는 id = **준 필드만**
      덮어쓰기, `deleted:true` = 목록에서 빼기(원본이 남아 있어 되돌릴 수 있다 → 지면에서도
      "Hidden by overlay" 로 보여 주고 Restore 버튼을 준다). 병합은 `config._apply_overlay`.
      curated 소스를 수정할 때 **전체 복사가 아니라 diff 만** 남기는 게 중요하다 — 전체를
      복사해 두면 나중에 `sources.yaml` 을 고쳐도 오버레이가 옛 값으로 계속 덮어써서
      "원본을 고쳤는데 아무 일도 안 일어나는" 상태가 된다.
    - `topics.json` — 필터 어휘가 `config.TOPIC_ORDER`/`TOPIC_LABELS` 상수에서 데이터로 내려왔다
      (`llm._TOPIC_GLOSS` 도 여기로). 브라우저에서 편집하려면 코드가 아니라 데이터여야 한다.
      파일이 없거나 깨지면 `config._FALLBACK_TOPICS`(내장 13개)로 돌아간다 — 무인 cron 이
      YAML/JSON 오타 하나로 분류를 멈추면 그날 지면이 안 나온다.
    - **왜 YAML 이 아니라 JSON 인가**: 브라우저가 쓰는 파일이다. 파이썬·JS 가 둘 다 표준
      라이브러리로 무손실 왕복해야 하는데, 클라이언트에서 YAML 을 직렬화하려면 CDN 의존성이나
      손으로 짠 emitter 가 필요하고 둘 다 설정 파일을 깨뜨리는 경로다. 주석 대신 `_comment`
      배열을 관례로 두고 admin 이 보존한다.
  - **두 구현의 대조**: `applyOverlay`(브라우저 미리보기)와 `config._apply_overlay`(파이프라인이
    실제로 쓰는 것)는 같은 규칙의 두 벌이다. 갈라지면 "화면에서는 지웠는데 계속 수집되는" 버그가
    된다 → 순수 규칙만 `static/admin_rules.js` 로 빼서(DOM 접근 금지) `tests/test_admin.py` 가
    **node 로 그대로 돌려 같은 픽스처 23개로 파이썬과 비교한다.** 인라인 스크립트로 두면 이 대조를
    자동화할 방법이 없어서 이 파일만 예외로 자산화했다.
  - **저장/팔로우는 localStorage 전용.** §10.4 가 못박은 순서("명시적 상태 먼저, 학습형은 한참
    뒤")의 1단계를 **서버 없이 되는 만큼만** 한 것이다. 기기 간 동기화가 없고 사이트 데이터를
    지우면 사라진다 → `saved.html` 에 그 사실을 문장으로 적었다(안 적으면 기기를 바꿨을 때
    "내 저장이 사라졌다"로 돌아온다). 키 하나(`ai-digest-follow`)에 `{v,items,topics,presets}`
    를 모아 둔다(`v` 는 형식 버전 — 안 맞으면 버리고 빈 상태로 시작).
    - **"비슷한 토픽 팔로우"의 구현**: 기사 자체를 따라갈 수는 없다(정적 사이트라 후속이 붙었는지
      알 방법이 없다). 대신 그 기사의 **토픽**을 팔로우한다 → 다음 지면에서 같은 계열이 눈에 띈다.
    - 팔로우가 **자동으로 지면을 걸러내지 않는다.** 홈을 열 때마다 항목 절반이 조용히 사라지면
      그건 필터가 아니라 고장으로 읽힌다 → 컨트롤 줄의 `Following n` 버튼을 눌러야 적용된다.
    - "저장한 필터"(이름 붙인 토픽 조합)는 어휘 편집과 **다른 축**이다 — 프리셋은 내 브라우저의
      읽기 습관이고, admin 의 어휘는 사이트 전체의 분류 체계다. `index.html?topics=a,b` 로
      적용한다(프리셋은 서버가 모르므로 지면을 미리 걸러 구울 수 없다).
  - **죽은 버튼 규칙 갱신**: `test_masthead_carries_no_link_that_goes_nowhere` 의 금지어에서
    `Following` 이 빠졌다 — 이제 구현이 있다. 대신
    `test_the_saved_and_following_controls_lead_somewhere_real` 이 "그 컨트롤이 실제로 뭔가에
    연결돼 있는지"(saved.html 존재 · follow.js 복사 · 저장 버튼의 data-* 완비)를 검사한다.
    `Monthly` · `Sign in` 은 여전히 금지다. ⚠️ 예전 테스트는 **픽스처에 토픽이 없어서** 통과하고
    있었다(컨트롤 줄이 `filters|length > 1` 일 때만 그려진다) — 새 테스트는 토픽을 붙여 렌더한다.
  - **마크업 변경 2건(되돌리기 쉬우니 주의)**: `.brief-row` 와 `.cat-row` 는 **행 전체가 `<a>`**
    였는데 `<div>` + 제목 링크로 바꿨다. `<a>` 안의 `<button>` 은 대화형 콘텐츠 중첩이라 HTML
    위반이고, 브라우저가 파싱 단계에서 DOM 을 재배치해 버튼이 링크 밖으로 튀어나온다.
    같은 이유로 팔로우 별은 토픽 pill 의 **자식이 아니라 형제**다(`.pill-pair`).
    `tests/test_follow.py` 가 렌더된 모든 `<a>`/`<button>` 안에 `<button>` 이 없는지 검사한다.
  - **검증**: 전체 **367 passed**(신규 35건 — admin 20 · follow 15). 실제 브라우저로
    admin 폼 검증 7종·탭 토글·조건부 필드, 저장/팔로우 13단계(저장→새로고침 유지→팔로우→
    Following 적용→저장 지면→프리셋 생성/개명/삭제→`?topics=` 적용)를 콘솔 에러 0으로 확인.
    `python pipeline.py --dry-run` 16소스 185건 정상, `rerender.py` 전체 재생성 완료.
  - **⚠️ 같은 날 발견한 실수 — 링크를 빼먹어서 지면이 "없는" 것이 됐다.** 소스 지면을 다 만들고
    `output/sources.html`(38KB)까지 구웠는데, 링크를 `util_header`(=sources·admin·saved 전용
    헤더)에만 달았다. 그 세 지면끼리만 서로를 가리켜서 **홈·카테고리·검색·아카이브에서는 들어갈
    방법이 아예 없었다.** 테스트 367개가 전부 통과했고 파일도 멀쩡했지만 사용자에게는 "소스 지면이
    추가되지 않았다"로 보고됐다 — 정확한 관찰이다. 지금은 마스트헤드 pill + 푸터 + 검색 헤더에
    링크가 있고(`.mh` 가 없는 지면이 있어서 푸터가 도달 가능성의 바닥이다), 아카이브 사본은
    `../` 접두를 받는다. `test_the_new_pages_are_reachable_from_the_digest` 가 루트/아카이브
    양쪽에서 링크 존재를 검사한다.
    **교훈**: 이 프로젝트는 도달 가능성을 이미 완성 정의 3번으로 못박아 뒀다(§13 — 아카이브 47개
    전부 도달 가능). 새 지면을 만들 때 "구워졌다"와 "도달할 수 있다"는 **다른 항목**이고, 후자를
    확인하지 않으면 렌더 테스트는 전부 초록인 채로 기능이 없는 것과 같아진다.
  - **아직 안 된 것**: GitHub 에 실제로 커밋하는 경로는 **토큰이 필요해서 자동 검증을 못 했다** —
    API 호출 모양(Contents GET/PUT + sha 낙관적 동시성, 409 처리, workflow dispatch)은 코드로
    맞췄지만 첫 저장은 사용자가 눌러 확인해야 한다. 그리고 **admin 에서 커밋해도 파이프라인은
    다시 돌지 않는다** — `daily.yml` 의 push 트리거가 수집을 일부러 건너뛴다(무료 배포 경로).
    새 소스는 다음 cron(14:00 UTC)이나 "Run pipeline now" 를 눌러야 실제로 걷힌다. 지면에 적었다.

## 11. 소스 확장 및 AI 그라운딩 (2026-07-29)

파이프라인의 뉴스 수집을 더욱 견고하게 만들기 위해 구조를 추가 확장함:

- **Full-Text Extraction**: 단순 RSS Snippet(TechCrunch 등)의 한계를 극복하기 위해 `trafilatura` 를 도입. `<description>` 대신 기사 본문 전체를 긁어와(3000자 제한) LLM이 더 풍부한 요약을 생성하도록 개선.
  → **2026-07-30 수정**: 전 소스 무조건 추출이 아니라 `full_text: true` 옵트인 + 신선도 컷 통과분 한정으로 바뀜(현재 `techcrunch_ai` 만). 위 변경로그 참고.
- **GNews 통합**: `gnews` 라이브러리를 추가하여, `sources.yaml` 에 `parse: gnews` 로 키워드(예: "Artificial Intelligence OR Large Language Models") 기반 뉴스 검색이 가능해짐.
  → **2026-07-30: `enabled: false`** (날짜 파싱/리다이렉트 URL 버그 2건 미해결). `sources.yaml` 주석에 재활성화 조건 기록.
  → **2026-07-31: 재활성화.** 두 버그 모두 수정하고 라이브러리는 제거(RSS 직접 파싱). AP·WaPo 한정
    갭필러로 좁힘. 위 변경로그 "Stage 3" 항목 참고.
- **Gemini Search Grounding**: `llm.py` 에 `catch_missed_news()` 를 추가, Gemini 의 네이티브 Google Search (Grounding) 도구를 사용해 기존 파이프라인이 놓친 주요 뉴스를 찾아와 보강함.

### Phase 2b: Expanded Curated Sources (보류됨)

당장 추가하지 않고 다음 단계로 파킹된 아이디어들:
- Substack 뉴스레터 자동화 (현재 `import_ai` 는 단일 피드로 동작 중이지만 더 확장)
- Reddit (`r/LocalLLaMA`, `r/MachineLearning`) 재활성화 및 트렌드 파악
- YouTube (`youtube-transcript-api`) 연동을 통한 기술 심층 분석 영상 요약

## 12. 소스 후보 판정표 — 안 하기로 한 것들 (2026-07-31 실측)

2026-07-30~31 에 후보 18종 · 엔드포인트 약 45개를 직접 찔러본 결과다. 아래 11종은
**구현하지 않기로 확정**했고, 이 섹션의 목적은 **다시 논의하지 않기 위해** 근거를 남기는 것이다.
숫자는 전부 실측이며 추정이 아니다. 재검토할 거면 "이 수치가 바뀌었는가"부터 확인할 것.

### 12-1. 되지만 신호를 깎아먹는 것 (Judgment — 보류, 구현 안 함)

기술적으로는 가능하다. **안 하는 이유는 하나로 수렴한다: 카테고리당 상한이 6이라 수집량을
늘리면 좋은 걸 밀어낸다.** 지금은 16소스 188건으로 이미 상한이 실제로 컷하고 있어서,
"AI 비중이 절반도 안 되는 소스"를 넣는 건 순손실이다. §9 의 상한 튜닝이 끝나기 전엔 재검토 금지.

| 후보 | 실측 | 걸리는 점 | 판단 |
|---|---|---|---|
| **Axios** | 100건 · 피드에 본문 통째로(6,102자) · **AI 38%** | 섹션 피드가 없다. 전 항목이 `top` 태그 하나뿐이라 AI 만 골라낼 수 없음 | 62%가 비-AI. 키워드 게이트를 우리가 직접 짜야 하는데, 그건 소스가 아니라 필터를 만드는 일 |
| **GitHub Trending** | 미러 피드 17개 repo · Search API 는 정상(비인증 10 req/h) | 미러에 **항목별 날짜가 없다** — gnews 를 껐던 것과 같은 신선도 컷 우회 함정. 게다가 제3자 정적 사이트라 조용히 죽을 수 있음 | 공식 Search API 는 `created_at`/`stargazers_count` 가 있어서 쓸 만하지만, **"별이 늘었다"는 뉴스가 아니다.** 랭킹 rubric 과 안 맞음 |
| **YouTube** | 채널 RSS 살아있음(OpenAI/DeepMind/Anthropic/2MP) | 피드엔 **설명문만** 온다. 자막은 별도 의존성이 필요하고 IP 차단을 먹음 | 설명문만으로 요약하면 "숫자는 원문 그대로" 규칙을 지킬 근거가 없다 |
| **Medium** | 태그 피드 최대 10건 · TDS 20건 중 AI 8건 | 멤버 전용 페이월이 본문 추출을 자름 | 개인 블로그 품질 편차가 크고, 잘린 본문은 요약 품질을 직접 깎는다 |
| **NYT / NY Post** | NYT 33건 **AI 48%** · NY Post 20건 | NYT 는 **full-text 추출이 0자**(페이월) | 헤드라인+snippet 만으로 굴릴 수는 있으나 Guardian/BBC 대비 추가 가치가 낮음 |

**한 줄 요약**: 이 다섯은 "볼륨은 주지만 신호는 안 준다". `signal > volume` 원칙(§3)의 정확한 반례라
넣지 않는다. 나중에 카테고리 상한을 올리거나 소스별 가중치가 생기면 Axios·NYT 부터 재검토.

### 12-2. 아예 안 되는 것 (Drop — 기술적/법적으로 불가)

여기는 "나중에 다시 해보자"가 아니다. **엔드포인트가 없거나, 명시적으로 금지돼 있다.**

| 후보 | 실측 | 결론 |
|---|---|---|
| **AP 직접** | `index.rss` → **401 Invalid client credentials**, hub → 404 | 공개 피드 자체가 없음. AP 는 피드를 상업 라이선스로 판다. → **Google News 갭필러로 우회 중**(Stage 3) |
| **Washington Post** | tech 피드 **HTTP 200 인데 0건** · business 2건 | 공개 RSS 사실상 폐지. 200 을 주니까 헬스체크로는 안 잡힌다 — 주의. → **Google News 로 우회 중** |
| **Wall Street Journal** | 피드 3개 전부 **2025-01-27 에 멈춤**(18개월 방치) | 버려진 엔드포인트 + 강한 페이월. 우회해도 본문을 못 읽는다 |
| **CBC** | 19건 중 **AI 1건** (톱기사가 공룡 발자국이었음) | AI 뉴스 소스가 아님 |
| **brunch.co.kr** | RSS 0바이트 · sitemap 없음 · `robots.txt` 가 **ClaudeBot·GPTBot·CCBot 을 이름으로 지목해 Disallow: /** | 기술적으로도 막혔고 명시적 거부다. **크롤링하지 않는다** |
| **LinkedIn** | `robots.txt` 에 자동 접근 "strictly prohibited" | 타인 게시물 읽기 API 자체가 없음. authwall + TOS 위반. **하지 않는다** |

**Reuters** 는 위 표에 없지만 같은 계열이다. 피드가 404 라 Google News 후보로 검토했는데,
넣으면 100건 중 75건을 차지해 AP/WaPo 를 밀어낸다(2026-07-31 실측) → 현재 질의에서 제외.

⚠️ **brunch/LinkedIn 은 우회 방법을 찾지 말 것.** 둘 다 로봇 배제를 명시적으로 선언한 쪽이고,
이 프로젝트는 공개 피드만 다룬다는 데이터 경계(CLAUDE.md)를 갖고 있다.

---

## 13. 남은 작업 — "개인용 정적 사이트 완성"까지 (2026-07-31 정리)

> **소스 확장은 끝났다. 남은 건 화면이다.**
> 이 섹션의 목적은 "무엇을 하면 개인용 사이트가 끝난 것인가"를 한 곳에 못박는 것.
> §5(파킹)·§9(TODO)·설계 스펙(`docs/superpowers/specs/2026-07-30-*.md`)에 흩어져 있던 미완료
> 항목을 전부 걷어서 **지금 할 것 / 다음 주 / 안 할 것** 세 칸으로 나눴다.
> 새 세션은 CLAUDE.md → **이 섹션** 순서로 읽으면 된다.

### 13.0 완성 정의 (Definition of Done)

개인용 사이트는 아래 4개가 되면 **끝**이다. 그 이상은 v2/v3(§5·§10)다.

1. 매일 자동으로 굽히고 Pages 에 올라간다 — **이미 됨**(Actions cron 14:00 UTC).
2. 파이프라인이 실패해도 페이지가 나온다 — **이미 됨**(리캡 크래시 수정 2026-07-31이 마지막 구멍).
3. 47개 아카이브 전부가 사이트 안에서 **도달 가능**하다 — ✅ **2026-07-31 완료**(T3.2).
4. 30건 넘는 다이제스트를 스캔 가능한 밀도로 읽을 수 있다 — ✅ **2026-08-03 완료**(T3.3).

즉 **완성 정의 4개가 전부 충족됐다(2026-08-03).** 남은 건 §13.2 의 날짜에 걸린 판정
(T1.1 논문 피드 → T1.2 research 하한)과 §13.3 의 다음 주 논의뿐이다.

### 13.1 지금 할 것 (권장 순서)

| # | 작업 | 왜 지금 | 비용 |
|---|---|---|---|
| **T0** | §5·§9 체크박스 정리 | 완료된 걸 미완료로 적어둔 줄이 4개 있어서 TODO 목록을 못 믿게 됐다. 이걸 먼저 안 하면 매 세션 같은 걸 다시 조사한다 | 0 (이 커밋에서 처리) |
| ~~**T2.1**~~ | ✅ **완료 2026-07-31** — 그라운딩 소스 품질 게이트 (맨 도메인 + 블록리스트 + 슬러그 패턴 + 프롬프트) | 착수 후 실측에서 **07-31 게시분 4건이 전부 라운드업**이었음을 확인(3건은 홈페이지 URL). 하한·캡으로는 못 막는다(sig 0.7~0.9). 변경로그 참고 | 완료. 테스트 22건, 전체 136 passed |
| ~~**T3.1**~~ | ✅ **완료 2026-07-31** — `render.py` 1,069줄 → **380줄**, `templates/*.html` 6개 + `static/digest.css` | Phase 6 선행 조건 해제. **238개 페이지 body/title 바이트 동일** 확인 | 완료. 테스트 16건, 전체 152 passed |
| ~~**T3.2**~~ | ✅ **완료 2026-07-31** — 47개 전부 링크 + 연도 그룹 + 문구 수정 | **완성 정의 3번 충족.** 링크 47/47 실제 파일로 해석 확인 | 완료. 테스트 17건, 전체 169 passed |
| ~~**T3.3**~~ | ✅ **완료 2026-08-03** — 캔버스 "AI Digest - Home" 을 DesignSync 로 가져와 홈/공용 크롬 재구성 | 사용자가 만든 캔버스 도착 → 예정대로 DesignSync 경로로 통합. **완성 정의 4번 충족.** 변경로그 참고 | 완료. 전체 205 passed |
| ~~**T3.4**~~ | ✅ **완료 2026-07-31** — `output/feed.xml` (RSS 2.0, 다이제스트 1개 = item 1개, 최근 20개) + 페이지 자동검색 링크 | §5 파킹 항목 해소. `feedparser` 왕복으로 검증(우리가 소비에 쓰는 그 라이브러리) | 완료. 테스트 22건, 전체 197 passed |

**T3.3 참고**: 설계 스펙에는 "DesignSync MCP 가 이 워크스페이스에 등록 안 돼 있어서 Claude Design
export 를 손으로 통합하는 게 유일한 경로"라고 적혀 있는데, **2026-07-31 세션에서는 DesignSync 가
사용 가능한 상태로 보인다.** 착수할 때 실제로 되는지 먼저 확인하고, 되면 2026-07-27 처럼
Claude Design → DesignSync 경로를 쓰는 게 빠르다.

### 13.2 날짜에 걸린 것 (코드 아님, 판정만)

- **T1.1 — 논문 피드 3종 판정** (~2026-08-04, 누적 후보 100건 시점). 쿼리와 컷 규칙은
  변경로그 2026-07-31 마지막 항목에 이미 박아둠. **위 T 작업들과 병렬로 굴러간다** — 매일 cron 이
  데이터를 쌓는 동안 렌더링을 하면 된다.
- **T1.2 — research 하한(0.55) 튜닝.** T1.1 **뒤에.** 순서 고정(소스 구성이 바뀌면 분포가 바뀐다).

### 13.3 다음 주 논의 (사용자 결정 2026-07-31 — 비용 때문에 연기)

- **설계 Phase 5 전체** — 어댑터 레지스트리(`PARSERS` dict) · `parse: json_api` 선언형 소스 ·
  `quarantine` 플래그 · 유저 제공 API 키(`api_key_env`).
  참고: 레지스트리 자체는 무료지만 **유료 API 를 붙일 때 같이 하는 게 맞다** — 지금 하면 쓰지도
  않는 추상화를 만드는 것이고, `if/elif` 3개는 아직 아프지 않다.
- **유료/고비용 뉴스 API 일반** — 어떤 걸 쓸지, 월 비용 상한이 얼마인지부터 정할 것.
- **free RSS 확장 잔여**(Qwen·DeepSeek·Cohere·Mistral) — 비용은 0이지만 소스 확장 종료에 포함해
  같이 닫았다. `model_releases` 가 5건으로 마른 beat 인 건 사실이라, 재개하면 여기가 1순위.

### 13.4 안 함 (재논의 금지 — 근거는 각 섹션에)

- **§12 의 11종**(Axios·GitHub·YouTube·Medium·NYT / AP직접·WaPo·WSJ·CBC·brunch·LinkedIn).
- **아카이브 재백필** — §5. `--purge-all` 선행이 필요해서 위험하고, 지금 이득이 없다.
- **어제 대비 diff 뷰** — §5 의 v2 1순위지만 v2 다. 스레딩(`Earlier:`)이 이미 절반을 커버한다.
- **§10 멀티유저/SSO/개인화** — 회사행이 확정되면. 단 §10.2(파이프라인↔렌더 분리)는 T3.1 을
  하다 보면 자연스럽게 절반이 된다(템플릿이 데이터를 받아 쓰는 구조가 되므로). **일부러 더
  하지는 말 것** — 개인용 완성이 먼저다.
