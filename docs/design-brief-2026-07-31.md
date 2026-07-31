# 디자인 개편 브리프 — T3.3 (2026-07-31)

> **용도**: Claude Design 캔버스를 만들 때 참고할 **실측 데이터**. 추측이 아니라 지금 DB/렌더
> 상태를 직접 센 값이다. 설계 스펙(`specs/2026-07-30-digest-expansion-and-quality-design.md`)
> Phase 6 의 "must accommodate" 목록이 **일부 사실과 달랐기 때문에** 이 문서를 따로 만들었다.
>
> 캔버스가 나오면 DesignSync 로 가져와 `static/digest.css` + `templates/` 에 통합한다
> (T3.1 에서 이미 분리해둠 — 파이썬 파일을 건드릴 필요 없다).

## 0. 지금 상태 요약

| 항목 | 값 |
|---|---|
| 페이지 종류 | 5 (home / category / search / archive_index / archive_week) |
| 배포 페이지 수 | 238 (일간 4 + 주간 43 + 카테고리 뷰 + 인덱스/검색) |
| 스타일 | `static/digest.css` 단일 파일, 206 규칙, 미디어쿼리 12개 |
| 팔레트 | 5색 라이브 스위처. **원본은 `render.PALETTES`(파이썬)** |
| 폰트 | Archivo 단일 (400~900) |
| radius | 0 (Modernist 컨셉) |

⚠️ **`:root` 팔레트 블록을 CSS 파일에 넣지 말 것.** `render.write_assets()` 가 `PALETTES` 에서
생성해 붙인다. export 된 CSS 에 `:root{--g:...}` 가 들어 있으면 **지우고** 파이썬 쪽을 고쳐야
한다(테마 JS·스위처 버튼이 같은 배열을 읽는다). `tests/test_render_assets.py` 가 이걸 잡는다.

## 1. 실제 크기 — "30건 넘는 다이제스트"는 아직 없다

설계 스펙은 "30+ 항목"을 전제로 밀도 개편을 하라고 했지만 **실측 최대는 26건**이다.

| 다이제스트 | 게시 항목 |
|---|---|
| 2026-07-30 | **26** (최대) |
| 2026-W20 | 23 |
| 2026-07-31 | 21 |
| 2026-W24 | 20 |

홈 레이아웃은 항목을 4구간으로 나눈다 — `lead` 1 + `grid3` 3 + `worth` 4 + **`brief` 나머지**.
26건이면 **brief 가 18건**이다. 즉 **밀도 문제는 전체가 아니라 in-brief 꼬리에 몰려 있다.**

## 2. 밀도 문제의 정확한 위치 — 꼬리에 긴 제목이 쌓인다

랭킹이 낮은 쪽이 arXiv 논문이고, **논문 제목이 가장 길다.** 그래서 "가장 좁게 보여줄 구간에
가장 긴 텍스트가 온다." 2026-07-30(26건)의 in-brief 꼬리 실측:

```
135자  Probing the Origins of Reasoning Performance: Repr...
117자  We're launching Lyria 3.5 in Google Flow Music, wi...
 94자  ClinLens: Towards Long-Horizon Coding Agents for L...
 90자  GuideSkill: Evolving Executable LLM Agent Skills f...
 88자  EvoPINN: Agentic Discovery of Executable Algorithm...
 35자  The Hugging Face break-in explained
```

**이게 T3.3 의 핵심 과제다.** 캔버스에서 in-brief 구간이 이 편차(35~135자)를 견뎌야 한다.

## 3. 제목 길이 분포 (게시분 444건)

| 길이 | 건수 |
|---|---|
| ≤40자 | 103 |
| 41–60자 | 164 |
| 61–90자 | 153 |
| **90자 초과** | **24** |

`headline`(LLM 이 만드는 60자 이하 표시용 제목)이 있으면 평균 **50.4자**(최소 37, 최대 61)로
안정적이다. 문제는 **커버리지**다:

| 다이제스트 | 게시 | headline 있음 |
|---|---|---|
| 2026-07-31 | 21 | **21 (100%)** |
| 2026-07-30 | 26 | 9 |
| 2026-07-29 | 11 | 0 |
| 그 이전(주간 백필 43개) | 388 | 0 |

→ **headline 은 2026-07-31 부터 100% 다. 긴 제목은 "줄어드는 레거시 데이터 문제"이지 상시
문제가 아니다.** 백필 414건 재엔리치는 유료 배치라 **하지 않기로 결정**(사용자, 2026-07-31),
대신 CSS 로 자른다. 캔버스는 **두 경우를 다 견뎌야 한다** — 짧은 headline 과 긴 원제목.

## 4. ⚠️ 스펙의 "must accommodate" 목록 정정

설계 스펙 Phase 6 은 네 가지를 수용하라고 했는데, 실제로는 이렇다:

| 스펙이 말한 것 | 실제 |
|---|---|
| `headline` | ✅ 있다. 위 3절 참고 |
| "Earlier: …" 스레드 링크 | ⚠️ **게시분 444건 중 2건만.** 실물이 거의 없다 |
| **"covered by N sources" 배지** | ❌ **그런 배지는 존재하지 않는다.** 아래 참고 |
| 30+ 항목 다이제스트 | ❌ 아직 없다(최대 26). 위 1절 |

### "covered by N sources" 배지의 실체

- 템플릿에 그 문구는 **없다.** 대신 소스 줄에 **`(+N more)` 접미사**로 나간다
  (`render._source_line_name`). 스펙과 구현이 다른 형태로 정착했다.
- 이 접미사는 `cluster_sources`(중복 소스 이름 집합)로 만든다. **`cluster_size` 컬럼은
  아무 템플릿도 읽지 않는다** — 저장만 되고 소비자가 없다.
  (그게 오히려 맞다: `cluster_size` 는 같은 소스가 두 번 올린 경우도 2로 세지만,
  `cluster_sources` 는 소스 이름 집합이라 "2개 소스가 다뤘다"가 참일 때만 붙는다.)
- **게시된 페이지에 아직 한 번도 나온 적이 없다.** 전체 602건 중 `cluster_size=2` 가 2건이고,
  그중 진짜 크로스소스는 1건 — **2026-07-31 의 Hugging Face 침해 기사(BBC + TechCrunch)**.
  그 1건이 `category_cap` 에 걸려 게시되지 않았다.
- 📈 **곧 나온다.** BBC·Guardian 을 07-31 에 넣었고(Stage 1), 그 첫날 바로 TechCrunch 와
  겹쳤다. 설계 스펙이 예측한 그대로다("Adding outlets removes that property").
  → **캔버스는 이 접미사 자리를 비워둬야 한다.** 실물이 없다고 빼면 며칠 뒤에 깨진다.

## 5. 반드시 살려야 하는 표시 요소

캔버스에서 빠지면 기능이 죽는 것들:

- **소스헬스 배지** — 피드가 조용히 죽는 걸 알리는 유일한 수단(`⚠️ 소스 이상`).
  홈에만 나오고, `warnings` 가 빌 때가 정상이다(그래서 디자인 시 눈에 안 띌 수 있음).
- **테마 스위처**(5색 스와치) + `localStorage` 복원. `[data-theme-btn]` 속성과
  `__aiDigestSetTheme(idx)` 호출 규약을 유지해야 JS 가 붙는다.
- **`records-chip`**(전체 레코드 수) · 카테고리 탭 카운트 · 아카이브 탭 카운트.
- **아카이브 인덱스의 연도 구분선**(2026-07-31 신설, sticky). 47행을 훑는 기준선.
- `significance` 밴드 미니 차트(`_signal_bands`), 볼륨 미니바(아카이브 인덱스).
- 카테고리 페이지 하단의 `category cap N · min significance M` 표기 — 튜닝 근거를 보는 자리.

## 6. 검증 방법 (통합 후 반드시)

```bash
python rerender.py          # 238페이지 재생성, API 비용 0
python -m pytest -q         # 169건 — 링크 경로·팔레트 드리프트·도달성 계약
```

⚠️ **`rerender.py` 는 커밋된 HTML 과 바이트 동일하지 않다** — 버그가 아니다.
(1) 전 페이지에 찍히는 전역 레코드 수가 DB 증가분만큼 바뀐다,
(2) `index.html` 의 source-alert 가 사라진다(어느 피드가 죽었는지는 fetch 시점 상태라 DB 에 없다).
**기준선을 뜨려면 통합 직전에 `rerender.py` 를 한 번 돌려서 그 출력을 스냅샷할 것.**
(T3.1 에서 이 방법으로 238페이지 body 바이트 동일을 확인했다.)

## 7. 손대지 말 것

- `templates/*.html` 의 Jinja 변수명·매크로 시그니처(`m.masthead(...)`, `m.head_scripts()`,
  `m.theme_picker()`, `m.site_footer(...)`). 마크업/클래스는 자유, **변수는 계약**이다.
- `asset_prefix` — CSS 경로 깊이용("" = 루트, "../" = archive/). 기존 `prefix` 와 의미가 다르다.
- `search.html` 의 인라인 JSON 인덱스(`file://` CORS 회피). 외부 파일로 바꾸면 로컬에서 깨진다.
