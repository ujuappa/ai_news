/* admin 페이지의 **순수 규칙**: 오버레이 병합 + 입력 검증. DOM 을 건드리지 않는다.
 *
 * 왜 admin.html 안이 아니라 별도 파일인가: 이 안의 `applyOverlay` 는 `config._apply_overlay`
 * 의 사본이다. 두 구현이 갈라지면 admin 의 미리보기가 파이프라인의 실제 동작과 달라지고,
 * 그건 "화면에서는 지웠는데 계속 수집되는" 종류의 버그가 된다. 파일로 빼 두면
 * `tests/test_admin.py` 가 node 로 이 파일을 그대로 돌려서 파이썬과 **같은 픽스처로 비교**할
 * 수 있다 — 템플릿 안에 인라인으로 두면 그 대조를 자동화할 방법이 없다.
 *
 * 그래서 이 파일에는 DOM·fetch·localStorage 가 없어야 한다. 하나라도 들어오면 node 에서
 * 못 돌고 대조 테스트가 조용히 스킵된다.
 *
 * ⚠️ `config._apply_overlay` / `config._OVERRIDABLE` / `config._TOPIC_KEY_OK` 를 고치면
 *    여기도 같이 고칠 것. 테스트가 잡지만, 잡히는 시점이 커밋 뒤면 이미 늦다.
 */
(function (root) {
  'use strict';

  // 소스 id · 토픽 key 공통 규칙. 파이썬은 config._TOPIC_KEY_OK.
  // 공백을 막는 게 핵심이다 — `data-topics` 가 공백 구분 목록이고 필터 매칭이 `' '+key+' '`
  // 라서, 키에 공백이 있으면 하나가 두 개의 가짜 토큰으로 쪼개져 필터가 조용히 어긋난다.
  // 대문자도 막는다(llm.clean_topics 가 lower() 로 비교해서 절대 매칭되지 않는 죽은 pill 이
  // 된다). 소스 id 는 여기에 더해 `static/img/<id>.webp` 파일명도 겸한다.
  var KEY_RE = /^[a-z0-9_]+$/;

  // 오버레이가 부분 수정으로 받을 수 있는 필드 = 파이썬 config._OVERRIDABLE.
  // `id` 가 빠져 있는 게 중요하다 — id 를 바꾸는 건 수정이 아니라 다른 소스이고,
  // items.source_id 와의 연결이 끊어져 과거 집계가 통째로 미아가 된다.
  var OVERRIDABLE = ['name', 'feed_url', 'category', 'parse', 'status', 'enabled',
                     'full_text', 'sitemap_paths', 'max_entries', 'notes'];

  /* config._apply_overlay 의 사본. 항목 의미:
   *   base 에 없는 id  -> 새 소스(name·feed_url·유효한 category 필요)
   *   base 에 있는 id  -> 준 필드만 덮어씀
   *   deleted: true    -> 목록에서 빼기
   * 깨진 항목은 조용히 건너뛴다(파이썬도 같다 — 무인 파이프라인이 항목 하나의 오타로
   * 죽는 것보다 그 항목만 빠지는 게 낫다).
   */
  function applyOverlay(base, entries, categoryOrder) {
    var byId = {}, order = [];
    (base || []).forEach(function (s) {
      byId[s.id] = JSON.parse(JSON.stringify(s));
      order.push(s.id);
    });

    (entries || []).forEach(function (row) {
      if (!row || typeof row !== 'object' || Array.isArray(row)) return;
      var id = String(row.id == null ? '' : row.id).trim();
      if (!id) return;

      if (row.deleted) { delete byId[id]; return; }

      if (byId[id]) {
        var touched = false;
        OVERRIDABLE.forEach(function (k) {
          if (Object.prototype.hasOwnProperty.call(row, k)) {
            byId[id][k] = row[k];
            touched = true;
          }
        });
        if (touched && !isCategory(byId[id].category, categoryOrder)) {
          // 카테고리를 알 수 없는 값으로 바꾼 부분수정은 파이썬에서도 원래 값을 유지한다
          // (`_source_from_row` 가 기존 category 로 폴백한다).
          byId[id].category = base.filter(function (b) { return b.id === id; })[0].category;
        }
        return;
      }

      if (!row.name || !row.feed_url) return;
      var cat = String(row.category == null ? '' : row.category);
      if (!isCategory(cat, categoryOrder)) return;
      byId[id] = {
        id: id,
        name: row.name,
        feed_url: row.feed_url,
        category: cat,
        parse: row.parse || 'easy',
        status: row.status || 'verify',
        enabled: row.enabled !== false,
        full_text: !!row.full_text,
        sitemap_paths: (row.sitemap_paths && row.sitemap_paths.length)
          ? row.sitemap_paths : ['/news/'],
        max_entries: row.max_entries == null ? null : row.max_entries,
        notes: row.notes || ''
      };
      order.push(id);
    });

    // 카테고리 그룹 유지(새 소스는 자기 카테고리 끝으로). 파이썬은 stable sort 를 쓴다 —
    // Array.prototype.sort 도 ES2019 부터 stable 이라 같은 결과가 나온다.
    var rank = {};
    (categoryOrder || []).forEach(function (c, i) { rank[c] = i; });
    return order
      .filter(function (id) { return byId[id]; })
      .map(function (id) { return byId[id]; })
      .sort(function (a, b) {
        var ra = rank[a.category] == null ? (categoryOrder || []).length : rank[a.category];
        var rb = rank[b.category] == null ? (categoryOrder || []).length : rank[b.category];
        return ra - rb;
      });
  }

  function isCategory(cat, categoryOrder) {
    return (categoryOrder || []).indexOf(cat) >= 0;
  }

  /* 저장 전 검증. 통과하면 null, 아니면 사람이 읽는 이유 한 문장.
   * `taken` = 이미 쓰이고 있는 id 집합(base + 오버레이). 새로 추가할 때만 본다. */
  function validateSource(d, isNew, taken) {
    if (!KEY_RE.test(String(d.id || ''))) {
      return 'ID must be lowercase letters, numbers and underscores. It becomes the source_id in '
        + 'the database and the image filename, so it has to be safe in both.';
    }
    if (isNew && (taken || []).indexOf(d.id) >= 0) {
      return 'A source with the ID "' + d.id + '" already exists.';
    }
    if (!String(d.name || '').trim()) {
      return 'Name is required — it is the byline shown on every story.';
    }
    if (!String(d.feed_url || '').trim()) {
      return 'Feed URL is required.';
    }
    // parse: gnews 는 feed_url 이 URL 이 아니라 검색어다(fetch.fetch_gnews_source).
    if (d.parse !== 'gnews' && !/^https?:\/\//.test(d.feed_url)) {
      return 'Feed URL must start with http:// or https://. (Only parse: gnews takes a search '
        + 'query instead of a URL.)';
    }
    if (d.max_entries != null && d.max_entries !== ''
        && (!isFinite(d.max_entries) || Number(d.max_entries) < 1
            || Number(d.max_entries) !== Math.floor(Number(d.max_entries)))) {
      return 'Max entries must be a whole number of 1 or more, or blank for the default of 25.';
    }
    if (d.parse === 'sitemap' && !(d.sitemap_paths || []).length) {
      return 'parse: sitemap needs at least one path to scrape, for example /news/.';
    }
    return null;
  }

  /* 토픽 검증. `at` = 수정 중인 인덱스(-1 = 새로 추가) — 자기 자신과의 중복은 무시해야 한다. */
  function validateTopic(d, topics, at) {
    if (!KEY_RE.test(String(d.key || ''))) {
      return 'Key must be lowercase letters, numbers and underscores — no spaces. The key goes '
        + 'into a space separated data-topics attribute, so a space would split it into two '
        + 'tokens and the filter would quietly stop matching.';
    }
    var clash = (topics || []).some(function (x, i) { return x.key === d.key && i !== at; });
    if (clash) return 'That key is already in the list.';
    if (!String(d.label || '').trim()) {
      return 'Label is required — it is the text on the pill.';
    }
    return null;
  }

  root.AdminRules = {
    KEY_RE: KEY_RE,
    OVERRIDABLE: OVERRIDABLE,
    applyOverlay: applyOverlay,
    validateSource: validateSource,
    validateTopic: validateTopic
  };
})(typeof globalThis !== 'undefined' ? globalThis : this);
