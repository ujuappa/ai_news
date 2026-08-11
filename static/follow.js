/* 저장(북마크) · 토픽 팔로우 · 저장한 필터 — **브라우저 안에서만** 산다 (2026-08-11).
 *
 * ── 왜 localStorage 인가 ─────────────────────────────────────────────────────
 * 이 사이트는 GitHub Pages 정적 산출물이고 계정도 서버도 없다. 그래서 저장/팔로우는
 * **이 브라우저 하나에만** 남는다 — 기기 간 동기화가 없고, 시크릿 창이나 사이트 데이터를
 * 지우면 사라진다. 지면에 그 사실을 적어 둔다(saved.html). "로그인 없이 동기화되는 것처럼"
 * 보이게 만들면 그게 곧 죽은 약속이다.
 *
 * PROJECT_MEMO §10.4 가 개인화 순서를 "명시적 상태(읽음·저장·팔로우) 먼저, 학습형은 한참
 * 뒤"로 못박아 뒀다. 이건 그 1단계를 서버 없이 할 수 있는 만큼만 한 것이다.
 *
 * ── 저장 형식 ────────────────────────────────────────────────────────────────
 * 키 하나(`ai-digest-follow`)에 전부 넣는다. 여러 키로 쪼개면 부분만 남은 상태가 생기고,
 * 마이그레이션할 때 세 곳을 따로 봐야 한다.
 *   { v, items: {id: {t,u,d,s,sig,tp,at}}, topics: [key], presets: [{name,topics}] }
 * `v` 는 형식 버전 — 나중에 모양을 바꿀 때 옛 데이터를 알아보고 버리거나 옮기기 위한 것이다.
 * 필드명이 짧은 이유: 이 값은 매 저장마다 통째로 직렬화되고 localStorage 는 보통 5MB 다.
 *
 * ── 읽기만 해도 죽는 저장소 ──────────────────────────────────────────────────
 * sandboxed iframe · 사이트 데이터 차단 · 일부 웹뷰에서는 `localStorage` 를 **읽기만 해도**
 * SecurityError 가 난다. 전부 try/catch 로 감싼다 — 2026-08-06 에 테마 스크립트가 정확히
 * 이것 때문에 통째로 죽어서 스위처 6개가 죽은 버튼이 된 적이 있다(macros.html 주석).
 * 여기서도 감싸 두면 그 세션 동안은 동작하고 유지만 안 된다.
 */
(function () {
  'use strict';

  var KEY = 'ai-digest-follow';
  var VERSION = 1;
  var EMPTY = { v: VERSION, items: {}, topics: [], presets: [] };

  function read() {
    var raw = null;
    try { raw = localStorage.getItem(KEY); } catch (e) { return clone(EMPTY); }
    if (!raw) return clone(EMPTY);
    var data;
    try { data = JSON.parse(raw); } catch (e) { return clone(EMPTY); }
    if (!data || typeof data !== 'object' || data.v !== VERSION) return clone(EMPTY);
    return {
      v: VERSION,
      items: (data.items && typeof data.items === 'object') ? data.items : {},
      topics: Array.isArray(data.topics) ? data.topics : [],
      presets: Array.isArray(data.presets) ? data.presets : []
    };
  }

  function write(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* 유지만 포기 */ }
    // 같은 탭의 다른 위젯(네비 카운트 · 지면 버튼)이 같이 갱신되도록. storage 이벤트는
    // **다른** 탭에만 가므로 자기 탭용 신호가 따로 필요하다.
    try {
      window.dispatchEvent(new CustomEvent('ai-digest-follow-change', { detail: state }));
    } catch (e) {
      var ev = document.createEvent('Event');
      ev.initEvent('ai-digest-follow-change', true, true);
      window.dispatchEvent(ev);
    }
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  // ── 저장(북마크) ──────────────────────────────────────────────────────────
  function isSaved(id) { return !!read().items[id]; }

  function saveItem(rec) {
    if (!rec || !rec.id) return;
    var s = read();
    s.items[rec.id] = {
      t: rec.title || '', u: rec.url || '', d: rec.date || '', s: rec.source || '',
      sig: rec.sig || 0, tp: rec.topics || [], at: Date.now()
    };
    write(s);
  }

  function unsaveItem(id) {
    var s = read();
    delete s.items[id];
    write(s);
  }

  function toggleSave(rec) {
    if (isSaved(rec.id)) { unsaveItem(rec.id); return false; }
    saveItem(rec);
    return true;
  }

  // ── 토픽 팔로우 ───────────────────────────────────────────────────────────
  function isFollowing(topic) { return read().topics.indexOf(topic) >= 0; }

  function toggleFollow(topic) {
    var s = read();
    var at = s.topics.indexOf(topic);
    if (at >= 0) s.topics.splice(at, 1); else s.topics.push(topic);
    write(s);
    return at < 0;
  }

  /* 저장한 기사의 토픽을 한 번에 팔로우한다 = 사용자가 말한 "이 기사와 비슷한 주제를 따라가기".
   * 기사 자체를 따라갈 수는 없다(정적 사이트라 그 기사에 후속이 붙었는지 알 방법이 없다) —
   * 대신 그 기사가 달고 있던 토픽을 따라가면 다음 지면에서 같은 계열이 눈에 띈다. */
  function followTopicsOf(id) {
    var s = read();
    var rec = s.items[id];
    if (!rec) return [];
    var added = [];
    (rec.tp || []).forEach(function (t) {
      if (t && s.topics.indexOf(t) < 0) { s.topics.push(t); added.push(t); }
    });
    if (added.length) write(s);
    return added;
  }

  // ── 저장한 필터(프리셋) ───────────────────────────────────────────────────
  // 이름 붙인 토픽 조합. 필터 어휘 자체를 고치는 것(admin)과 **다른 축**이다 —
  // 프리셋은 내 브라우저의 읽기 습관이고, 어휘는 사이트 전체의 분류 체계다.
  function savePreset(name, topics) {
    name = String(name || '').trim();
    if (!name || !topics || !topics.length) return false;
    var s = read();
    var at = -1;
    for (var i = 0; i < s.presets.length; i++) {
      if (s.presets[i].name.toLowerCase() === name.toLowerCase()) { at = i; break; }
    }
    var rec = { name: name, topics: topics.slice() };
    if (at >= 0) s.presets[at] = rec; else s.presets.push(rec);
    write(s);
    return true;
  }

  function deletePreset(name) {
    var s = read();
    s.presets = s.presets.filter(function (p) { return p.name !== name; });
    write(s);
  }

  function renamePreset(oldName, newName) {
    newName = String(newName || '').trim();
    if (!newName) return false;
    var s = read();
    var clash = s.presets.some(function (p) {
      return p.name !== oldName && p.name.toLowerCase() === newName.toLowerCase();
    });
    if (clash) return false;
    s.presets.forEach(function (p) { if (p.name === oldName) p.name = newName; });
    write(s);
    return true;
  }

  // ── 지면의 저장 버튼 ──────────────────────────────────────────────────────
  // 버튼은 서버가 굽는다(필터 서랍과 같은 방식). 마크업이 이미 있으니 여기서는 상태만 칠한다.
  function recordFrom(btn) {
    var topics = (btn.getAttribute('data-item-topics') || '')
      .split(' ').filter(function (x) { return x; });
    return {
      id: btn.getAttribute('data-item-id'),
      title: btn.getAttribute('data-item-title'),
      url: btn.getAttribute('data-item-url'),
      date: btn.getAttribute('data-item-date'),
      source: btn.getAttribute('data-item-source'),
      sig: parseFloat(btn.getAttribute('data-item-sig')) || 0,
      topics: topics
    };
  }

  function paintSaveButton(btn) {
    var on = isSaved(btn.getAttribute('data-item-id'));
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.classList.toggle('is-on', on);
    var label = btn.querySelector('[data-save-label]');
    if (label) label.textContent = on ? 'Saved' : 'Save';
    // 제목이 아니라 동작을 적는다 — 스크린리더에서 "Save" 버튼이 20개 나오면 구분이 안 된다.
    var title = btn.getAttribute('data-item-title') || 'this story';
    btn.setAttribute('aria-label', (on ? 'Remove from saved: ' : 'Save for later: ') + title);
  }

  function paintAll() {
    var btns = document.querySelectorAll('[data-save]');
    for (var i = 0; i < btns.length; i++) paintSaveButton(btns[i]);
    var followBtns = document.querySelectorAll('[data-follow-btn]');
    for (var j = 0; j < followBtns.length; j++) {
      var t = followBtns[j].getAttribute('data-follow-topic');
      var on = isFollowing(t);
      followBtns[j].setAttribute('aria-pressed', on ? 'true' : 'false');
      followBtns[j].classList.toggle('is-on', on);
      followBtns[j].setAttribute('aria-label',
        (on ? 'Unfollow topic: ' : 'Follow topic: ') + t);
    }
    var counts = document.querySelectorAll('[data-saved-count]');
    var n = Object.keys(read().items).length;
    for (var k = 0; k < counts.length; k++) {
      counts[k].textContent = n ? String(n) : '';
    }
    var followApply = document.querySelector('[data-follow-apply]');
    if (followApply) {
      var fn = read().topics.length;
      followApply.hidden = fn === 0;
      var fl = followApply.querySelector('[data-follow-apply-n]');
      if (fl) fl.textContent = String(fn);
    }
  }

  function wire() {
    document.addEventListener('click', function (e) {
      var save = e.target.closest ? e.target.closest('[data-save]') : null;
      if (save) {
        e.preventDefault();
        toggleSave(recordFrom(save));
        return;
      }
      var follow = e.target.closest ? e.target.closest('[data-follow-btn]') : null;
      if (follow) {
        e.preventDefault();
        e.stopPropagation();   // 팔로우 별은 필터 pill 안에 있다 — 누르면 필터까지 켜지면 안 된다
        toggleFollow(follow.getAttribute('data-follow-topic'));
      }
    });
    window.addEventListener('ai-digest-follow-change', paintAll);
    // 다른 탭에서 바꾼 것도 반영한다(같은 사이트를 두 탭에 열어 두는 건 흔하다).
    window.addEventListener('storage', function (e) {
      if (!e.key || e.key === KEY) paintAll();
    });
  }

  window.AIDigestFollow = {
    read: read, write: write,
    isSaved: isSaved, saveItem: saveItem, unsaveItem: unsaveItem, toggleSave: toggleSave,
    isFollowing: isFollowing, toggleFollow: toggleFollow, followTopicsOf: followTopicsOf,
    savePreset: savePreset, deletePreset: deletePreset, renamePreset: renamePreset,
    paintAll: paintAll
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { wire(); paintAll(); });
  } else {
    wire();
    paintAll();
  }
})();
