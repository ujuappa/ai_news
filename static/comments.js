/* 댓글 레일 — 이 브라우저 안에서만 산다 (2026-08-12).
 *
 * GitHub Pages 정적 산출물이라 댓글 서버가 없다. 스레드는 localStorage 키
 * `ai-digest-comments` 에만 남는다(저장/팔로우와 같은 한계: 기기 간 동기화 없음,
 * 시크릿/데이터 삭제면 사라짐). 공개/비공개는 이 브라우저의 작성자 이름 기준이다.
 *
 * parent_id 는 null 이거나 **최상위** 댓글 id 만. 답글의 답글은 저장 시점에 거절한다
 * (UI 가 아니라 데이터 규칙). 스펙의 "server-side constraint" 를 이 저장소가 맡는다.
 *
 * 건수는 countsByStory() 한 번으로 칠한다 — 행마다 다시 읽지 않는다.
 */
(function () {
  'use strict';

  var KEY = 'ai-digest-comments';
  var VERSION = 1;
  var EMPTY = { v: VERSION, author: 'You', comments: [] };
  var MAX_THREADS = 50;
  var _clock = 0;
  var currentId = '';
  var lastRow = null;
  var vis = 'public';

  function stamp() {
    var t = Date.now();
    if (t <= _clock) t = _clock + 1;
    _clock = t;
    return t;
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function read() {
    var raw = null;
    try { raw = localStorage.getItem(KEY); } catch (e) { return clone(EMPTY); }
    if (!raw) return clone(EMPTY);
    var data;
    try { data = JSON.parse(raw); } catch (e) { return clone(EMPTY); }
    if (!data || typeof data !== 'object' || data.v !== VERSION) return clone(EMPTY);
    return {
      v: VERSION,
      author: typeof data.author === 'string' && data.author.trim() ? data.author.trim() : 'You',
      comments: Array.isArray(data.comments) ? data.comments : []
    };
  }

  function write(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* 유지만 포기 */ }
    try {
      window.dispatchEvent(new CustomEvent('ai-digest-comments-change', { detail: state }));
    } catch (e) {
      var ev = document.createEvent('Event');
      ev.initEvent('ai-digest-comments-change', true, true);
      window.dispatchEvent(ev);
    }
  }

  function setAuthor(name) {
    var s = read();
    s.author = String(name || '').trim() || 'You';
    write(s);
    return s.author;
  }

  function visibleOf(list, me) {
    me = me || read().author;
    return list.filter(function (c) {
      return c.visibility !== 'private' || c.author === me;
    });
  }

  function addComment(rec) {
    var body = String((rec && rec.body) || '').trim();
    var storyId = rec && rec.story_id;
    if (!body || !storyId) return null;
    var s = read();
    var parentId = rec.parent_id || null;
    if (parentId) {
      var parent = null;
      for (var i = 0; i < s.comments.length; i++) {
        if (s.comments[i].id === parentId) { parent = s.comments[i]; break; }
      }
      if (!parent || parent.parent_id || parent.story_id !== storyId) return null;
    }
    var t = stamp();
    var row = {
      id: 'c-' + t.toString(36) + Math.random().toString(36).slice(2, 6),
      story_id: storyId,
      parent_id: parentId,
      author: s.author,
      body: body,
      visibility: rec.visibility === 'private' ? 'private' : 'public',
      created_at: t,
      edited_at: null
    };
    s.comments.push(row);
    write(s);
    return row;
  }

  function countsByStory() {
    var s = read();
    var vis = visibleOf(s.comments, s.author);
    var out = {};
    for (var i = 0; i < vis.length; i++) {
      var id = vis[i].story_id;
      out[id] = (out[id] || 0) + 1;
    }
    return out;
  }

  function threadsFor(storyId) {
    var s = read();
    var all = visibleOf(s.comments, s.author).filter(function (c) {
      return c.story_id === storyId;
    });
    var tops = [];
    var byParent = {};
    for (var i = 0; i < all.length; i++) {
      var c = all[i];
      if (c.parent_id) {
        (byParent[c.parent_id] = byParent[c.parent_id] || []).push(c);
      } else {
        tops.push(c);
      }
    }
    var threads = tops.map(function (t) {
      var reps = (byParent[t.id] || []).slice().sort(function (a, b) {
        return a.created_at - b.created_at;
      });
      var activity = t.created_at;
      for (var r = 0; r < reps.length; r++) {
        if (reps[r].created_at > activity) activity = reps[r].created_at;
      }
      var thread = {
        id: t.id, story_id: t.story_id, parent_id: t.parent_id, author: t.author,
        body: t.body, visibility: t.visibility, created_at: t.created_at,
        edited_at: t.edited_at, replies: reps, activity: activity
      };
      return thread;
    });
    threads.sort(function (a, b) { return b.activity - a.activity; });
    return threads.slice(0, MAX_THREADS);
  }

  function relTime(ts) {
    var s = Math.max(0, (Date.now() - ts) / 1000);
    if (s < 45) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    var d = Math.floor(s / 86400);
    return d + 'd ago';
  }

  function initials(name) {
    var p = String(name || 'You').trim().split(/\s+/);
    var a = (p[0] || 'Y').charAt(0);
    var b = p.length > 1 ? p[1].charAt(0) : '';
    return (a + b).toUpperCase();
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function rail() { return document.querySelector('[data-comment-rail]'); }
  function shell() { return document.querySelector('[data-digest-shell]'); }

  function storyParam() {
    try { return new URLSearchParams(location.search).get('story') || ''; }
    catch (e) { return ''; }
  }

  function pushStory(id) {
    try {
      var url = new URL(location.href);
      if (id) url.searchParams.set('story', id);
      else url.searchParams.delete('story');
      history.pushState({ story: id || '' }, '', url);
    } catch (e) { /* file: URL 등 */ }
  }

  function replaceStory(id) {
    try {
      var url = new URL(location.href);
      if (id) url.searchParams.set('story', id);
      else url.searchParams.delete('story');
      history.replaceState({ story: id || '' }, '', url);
    } catch (e) { /* ignore */ }
  }

  function rowFor(id) {
    return document.querySelector('[data-story][data-story-id="' + id + '"]');
  }

  function recordFromRow(row) {
    if (!row) return null;
    var btn = row.querySelector('[data-save]');
    var topics = btn ? (btn.getAttribute('data-item-topics') || '').split(' ').filter(Boolean) : [];
    return {
      id: row.getAttribute('data-story-id'),
      title: row.getAttribute('data-story-title') || (btn && btn.getAttribute('data-item-title')) || '',
      url: btn ? btn.getAttribute('data-item-url') : '',
      date: btn ? btn.getAttribute('data-item-date') : '',
      source: row.getAttribute('data-story-source') || (btn && btn.getAttribute('data-item-source')) || '',
      sig: btn ? parseFloat(btn.getAttribute('data-item-sig')) || 0 : 0,
      topics: topics
    };
  }

  function autoSave(row) {
    var F = window.AIDigestFollow;
    var rec = recordFromRow(row);
    if (!F || !rec || !rec.id || F.isSaved(rec.id)) return;
    F.saveItem(rec);
  }

  function paintCounts() {
    var counts = countsByStory();
    var els = document.querySelectorAll('[data-comment-count]');
    for (var i = 0; i < els.length; i++) {
      var id = els[i].getAttribute('data-story-id');
      var n = counts[id] || 0;
      els[i].textContent = n ? (n + ' comment' + (n === 1 ? '' : 's')) : 'Add the first comment';
    }
  }

  function paintFollow() {
    var btn = document.querySelector('[data-rail-follow]');
    var F = window.AIDigestFollow;
    if (!btn) return;
    var on = !!(F && currentId && F.isSaved(currentId));
    btn.textContent = on ? 'Following' : 'Follow';
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.classList.toggle('is-on', on);
  }

  function avatar(name, reply) {
    var me = read().author;
    var a = el('span', 'cmt-avatar' + (reply ? ' cmt-avatar-reply' : '') +
      (name === me ? ' is-me' : ''));
    a.textContent = initials(name);
    a.setAttribute('aria-hidden', 'true');
    return a;
  }

  function commentNode(c, reply) {
    var row = el('div', reply ? 'cmt cmt-reply' : 'cmt');
    row.appendChild(avatar(c.author, reply));
    var body = el('div', 'cmt-main');
    var who = el('div', 'cmt-who');
    who.appendChild(el('span', 'cmt-name', c.author));
    who.appendChild(el('span', 'cmt-time', relTime(c.created_at)));
    if (c.visibility === 'private') who.appendChild(el('span', 'cmt-priv', 'Private'));
    body.appendChild(who);
    body.appendChild(el('p', reply ? 'cmt-body cmt-body-reply' : 'cmt-body', c.body));
    row.appendChild(body);
    return row;
  }

  function replyBox(threadId) {
    var wrap = el('form', 'cmt-reply-form');
    wrap.setAttribute('hidden', '');
    wrap.setAttribute('data-reply-for', threadId);
    var ta = el('textarea');
    ta.rows = 2;
    ta.setAttribute('data-reply-input', '');
    ta.setAttribute('placeholder', 'Write a reply…');
    wrap.appendChild(ta);
    var post = el('button', 'cmt-reply-post', 'Reply');
    post.type = 'submit';
    wrap.appendChild(post);
    wrap.addEventListener('submit', function (e) {
      e.preventDefault();
      var text = ta.value;
      var row = addComment({
        story_id: currentId, parent_id: threadId, body: text, visibility: vis
      });
      if (!row) return;
      ta.value = '';
      autoSave(lastRow);
      paintRail();
      paintCounts();
    });
    return wrap;
  }

  function threadNode(t) {
    var box = el('div', 'cmt-thread');
    box.appendChild(commentNode(t, false));
    for (var i = 0; i < t.replies.length; i++) {
      box.appendChild(commentNode(t.replies[i], true));
    }
    var form = replyBox(t.id);
    var action = el('button', 'cmt-reply-btn',
      t.replies.length ? 'Reply to thread' : 'Reply');
    action.type = 'button';
    action.addEventListener('click', function () {
      if (form.hasAttribute('hidden')) form.removeAttribute('hidden');
      else form.setAttribute('hidden', '');
      var input = form.querySelector('textarea');
      if (input && !form.hasAttribute('hidden')) input.focus();
    });
    box.appendChild(action);
    box.appendChild(form);
    return box;
  }

  function paintRail() {
    var r = rail();
    if (!r || !currentId) return;
    var row = rowFor(currentId) || lastRow;
    var title = r.querySelector('[data-rail-title]');
    var source = r.querySelector('[data-rail-source]');
    var time = r.querySelector('[data-rail-time]');
    var count = r.querySelector('[data-rail-count]');
    var empty = r.querySelector('[data-rail-empty]');
    var list = r.querySelector('[data-rail-threads]');
    if (row) {
      if (title) title.textContent = row.getAttribute('data-story-title') || '';
      if (source) source.textContent = row.getAttribute('data-story-source') || '';
      if (time) time.textContent = row.getAttribute('data-story-time') || '';
    }
    var threads = threadsFor(currentId);
    var n = 0;
    for (var i = 0; i < threads.length; i++) n += 1 + threads[i].replies.length;
    if (count) count.textContent = n ? (n + ' comment' + (n === 1 ? '' : 's')) : 'No comments';
    if (list) {
      while (list.firstChild) list.removeChild(list.firstChild);
      for (var t = 0; t < threads.length; t++) list.appendChild(threadNode(threads[t]));
    }
    if (empty) {
      if (threads.length) empty.setAttribute('hidden', '');
      else empty.removeAttribute('hidden');
    }
    paintFollow();
  }

  function openRail(id, fromPop) {
    if (!id) return;
    var r = rail();
    var sh = shell();
    var row = rowFor(id);
    if (row) lastRow = row;
    currentId = id;
    if (r) r.removeAttribute('hidden');
    if (sh) sh.classList.add('is-rail-open');
    paintRail();
    if (!fromPop && storyParam() !== id) {
      if (storyParam()) replaceStory(id);
      else pushStory(id);
    }
    var input = r && r.querySelector('[data-rail-input]');
    if (input && !fromPop) input.focus();
  }

  function closeRail(fromPop) {
    var r = rail();
    var sh = shell();
    if (r) r.setAttribute('hidden', '');
    if (sh) sh.classList.remove('is-rail-open');
    var focusRow = lastRow;
    currentId = '';
    if (!fromPop && storyParam()) {
      if (history.state && history.state.story) {
        history.back();
        return;
      }
      replaceStory('');
    }
    if (focusRow && focusRow.focus) {
      try { focusRow.focus(); } catch (e) { /* ignore */ }
    }
  }

  function onRowActivate(row) {
    var id = row.getAttribute('data-story-id');
    if (!id) return;
    if (currentId === id) return;
    lastRow = row;
    openRail(id, false);
  }

  function wireHeadlines() {
    var heads = document.querySelectorAll('.story-headline');
    for (var i = 0; i < heads.length; i++) {
      heads[i].addEventListener('click', function (e) { e.stopPropagation(); });
    }
  }

  function wire() {
    var r = rail();
    if (!r) return;
    wireHeadlines();

    document.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest('.story-headline')) return;
      if (t.closest('a, button, textarea, input, select, label')) {
        return;
      }
      var row = t.closest('[data-story]');
      if (row) onRowActivate(row);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && currentId) {
        e.preventDefault();
        closeRail(false);
        return;
      }
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest('a, button, textarea, input')) return;
      var row = t.closest('[data-story]');
      if (!row || (t !== row && !row.contains(t))) return;
      if (t !== row) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onRowActivate(row);
      }
    });

    var closeBtn = r.querySelector('[data-rail-close]');
    if (closeBtn) closeBtn.addEventListener('click', function () { closeRail(false); });

    var followBtn = r.querySelector('[data-rail-follow]');
    if (followBtn) followBtn.addEventListener('click', function () {
      var F = window.AIDigestFollow;
      var rec = recordFromRow(lastRow || rowFor(currentId));
      if (!F || !rec) return;
      F.toggleSave(rec);
      paintFollow();
    });

    var visBtns = r.querySelectorAll('[data-vis]');
    for (var v = 0; v < visBtns.length; v++) {
      visBtns[v].addEventListener('click', function (ev) {
        vis = ev.currentTarget.getAttribute('data-vis') === 'private' ? 'private' : 'public';
        for (var j = 0; j < visBtns.length; j++) {
          var on = visBtns[j].getAttribute('data-vis') === vis;
          visBtns[j].classList.toggle('is-on', on);
          visBtns[j].setAttribute('aria-pressed', on ? 'true' : 'false');
        }
      });
    }

    var form = r.querySelector('[data-rail-composer]');
    if (form) form.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = r.querySelector('[data-rail-input]');
      if (!input || !currentId) return;
      var row = addComment({
        story_id: currentId, body: input.value, visibility: vis
      });
      if (!row) return;
      input.value = '';
      autoSave(lastRow || rowFor(currentId));
      paintRail();
      paintCounts();
    });

    window.addEventListener('popstate', function () {
      var id = storyParam();
      if (id) openRail(id, true);
      else closeRail(true);
    });
    window.addEventListener('ai-digest-comments-change', function () {
      paintCounts();
      if (currentId) paintRail();
    });
    window.addEventListener('ai-digest-follow-change', paintFollow);

    var initial = storyParam();
    if (initial && rowFor(initial)) openRail(initial, true);
  }

  window.AIDigestComments = {
    read: read, write: write, setAuthor: setAuthor,
    addComment: addComment, threadsFor: threadsFor, countsByStory: countsByStory,
    openRail: openRail, closeRail: closeRail
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { wire(); paintCounts(); });
  } else {
    wire();
    paintCounts();
  }
})();
