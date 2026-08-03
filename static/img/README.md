# static/img — 소스 마크 이미지

캔버스 디자인(2026-08-03 "AI Digest - Home")은 리드 스토리 / Also today 카드 /
Worth knowing 행에 회사별 이미지를 쓴다. **아직 이미지가 없어서 지금은 같은 크기의 빈
플레이스홀더가 자리를 지킨다** — 나중에 파일을 넣으면 레이아웃 변화 없이 채워진다.

## 넣는 법

파일명을 `sources.yaml` 의 소스 id 와 같게 해서 이 폴더에 두면 끝이다.

```
static/img/openai.webp
static/img/anthropic.png
static/img/techcrunch.jpg
```

- 인식하는 확장자(우선순위 순): `.webp` `.jpg` `.jpeg` `.png` `.svg`
- 다음 렌더(`python rerender.py` 또는 `python pipeline.py`)에서 `output/static/img/` 로 복사된다.
- 표시는 `object-fit: cover` + 그레이스케일 필터. 슬롯 비율은 리드 4:3(좁은 화면 16:9),
  카드 16:10, 썸네일 4:3(128px).
- 파일이 없는 소스는 계속 플레이스홀더로 나온다 — 전부 채울 필요 없다.

구현: `render._image_for()` / `render._copy_images()`, 마크업은 `templates/macros.html`
의 `image_slot` 매크로, 크기는 `static/digest.css` 의 `.imgslot-*`.

⚠️ 공개 뉴스 소스의 브랜드 마크만 둘 것. 사내 자산·PII 는 이 레포에 올리지 않는다.
