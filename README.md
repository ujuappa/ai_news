# AI News Digest — v1 skeleton

매일 AI 뉴스를 자동 수집 → 중복제거 → 분류·요약·랭킹 → 웹페이지로 굽는 개인용 파이프라인.

## 구조

```
sources.yaml   소스 목록 + 설정 (검증 완료 2026-07-25)
config.py      sources.yaml 로드, settings/모델/경로
fetch.py       feedparser 수집 + 정규화 (HF <link> 누락 → guid 폴백)
dedup.py       임베딩 코사인: 배치 내 클러스터링 + cross-day 중복 스킵
llm.py         Gemini API: 분류/요약(2-3문장, 숫자 보존)/유의성/major 플래그
store.py       SQLite: 아이템 히스토리 + seen-store + 다이제스트 기록
render.py      Jinja2 → index.html + 날짜별 아카이브 + 아카이브 인덱스
pipeline.py    오케스트레이터 (엔트리포인트)
.github/workflows/daily.yml   매일 크론 실행 + 커밋
```

파이프라인: **수집 → dedup → LLM → 랭킹/상한 → SQLite → HTML**

## 셋업

```bash
pip install -r requirements.txt
# Gemini는 Vertex AI 모드로 인증 (GCP 서비스 계정). .env는 .gitignore 처리됨:
cat > .env <<'EOF'
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=<프로젝트ID>
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/절대/경로/service-account.json
EOF
python pipeline.py            # 정상 실행
python pipeline.py --dry-run  # LLM 없이 수집/dedup 까지만 확인 (DB 미변경)
python pipeline.py --reset    # seen-store/히스토리 초기화 (digest.db 삭제)
```

첫 실행 시 `sentence-transformers` 가 임베딩 모델(all-MiniLM-L6-v2)을 내려받음.
결과는 `output/index.html`.

## 배포 (GitHub Pages)

1. 저장소 Settings → Secrets 에 `GCP_SERVICE_ACCOUNT_KEY`(서비스 계정 JSON 파일 전체 내용),
   `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` 추가 (`daily.yml` 이 이 시크릿을
   파일로 써서 `GOOGLE_APPLICATION_CREDENTIALS` 로 가리키게 이미 구성돼 있음)
2. Settings → Pages → branch=main, folder=`/output`
3. `.github/workflows/daily.yml` 이 매일 돌면서 `output/` 를 커밋 → Pages 갱신
   (cron 시각 `0 14 * * *` UTC 는 취향대로 조정)

## 설계 메모 (반영된 것)

- **cross-day dedup**: `seen` 테이블에 최근 N일 임베딩 저장, 이미 다룬 스토리 스킵
- **signal > volume**: 카테고리당 `max_items_per_category` 상한, 유의성 내림차순
- **상단 major 플래그**: 프런티어 모델/대형 딜/정책 전환만 `is_major`
- **숫자 보존**: 요약 시 벤치마크·파라미터·금액은 원문 그대로 (프롬프트에 명시)
- **community_takes**: v1 에서 OFF (`_rank_and_cap` 에서 제외 + sources.yaml enabled:false)
- **source-health**: 수집 0건 소스는 다이제스트 하단에 ⚠️ 배지

## 확장 포인트

- **가벼운 dedup**: torch 가 부담이면 `dedup.embed()` 를 `TfidfVectorizer` 로 교체 (그 외 코드 불변)
- **모델 비용**: 고볼륨이면 `DIGEST_MODEL=gemini-2.5-flash-lite` 로
- **no_feed 소스**(Anthropic/Meta/Mistral): RSSHub 경로나 자체 파서를 `fetch.py` 에 추가

## 다음 스텝 (PROJECT_MEMO 파킹 아이디어)

- [ ] `verify` 소스(The Gradient, Simon Willison) build-time 확인
- [ ] **어제 대비 diff 뷰** — seen-store 활용, "굴러가는 스토리" 추적 (v2 1순위)
- [ ] 아카이브 검색, RSS 출력, 페이지 디자인 다듬기
- [ ] cross-day "새 각도면 업데이트" 로직 (지금은 스킵만)
