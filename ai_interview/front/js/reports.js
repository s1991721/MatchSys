(() => {
  const bridge = window.AIInterviewFrame, demo = window.AIInterviewReportDemo;
  const $ = selector => document.querySelector(selector);
  const copy = {
    'zh-CN': {title:'评估报告', detailTitle:'报告详情', mediaDemo:'以下为播放演示素材，并非候选人的录音或视频。', candidate:'候选人', position:'岗位', time:'面试时间', reading:'阅读状态', action:'操作', all:'全部', unread:'未读', read:'已读', view:'查看报告', back:'← 返回报告列表', loading:'正在加载…', empty:'暂无已完成的报告。', noUnread:'暂无未读报告。', failed:'加载失败，请重试。', retry:'重试', audio:'面试录音', video:'面试视频', mediaError:'媒体无法播放，请稍后重试。'},
    ja: {title:'評価レポート', detailTitle:'レポート詳細', mediaDemo:'再生デモ用の素材です。候補者の音声・動画ではありません。', candidate:'候補者', position:'職種', time:'面接日時', reading:'閲覧状態', action:'操作', all:'すべて', unread:'未読', read:'既読', view:'レポートを見る', back:'← 一覧に戻る', loading:'読み込み中…', empty:'完成したレポートはありません。', noUnread:'未読レポートはありません。', failed:'読み込みに失敗しました。', retry:'再試行', audio:'面接音声', video:'面接動画', mediaError:'メディアを再生できません。後でもう一度お試しください。'}
  };
  const c = () => copy[bridge.lang] || copy.ja;
  let records = [], selected = 'all', detail = null, scroll = 0, loading = true, listFailed = false, detailFailed = false, activeId = null;
  function node(tag, text, className = '') {
    const el = document.createElement(tag); el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function button(text, action) {
    const el = node('button', text, 'outline-action'); el.type = 'button'; el.addEventListener('click', action); return el;
  }
  function date(value) {
    return value && Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat(bridge.lang, {timeZone:'Asia/Tokyo', dateStyle:'medium', timeStyle:'short'}).format(new Date(value)) : '—';
  }
  function status(el, message, retry) {
    el.replaceChildren(node('p', message));
    if (retry) el.append(button(c().retry, retry));
  }
  function count(value) {
    if (window.parent !== window) window.parent.postMessage({type:'aomera-reports-updated', unreadCount:value}, location.origin);
  }
  function renderHeading() {
    const title = activeId === null ? c().title : c().detailTitle;
    $('#reportPageTitle').textContent = title;
    document.title = `AOMERA — ${title}`;
  }
  function renderList() {
    $('#reportFilters').replaceChildren();
    for (const key of ['all','unread']) {
      const el = button(c()[key], () => {selected = key; renderList(); $('#reportFilters').children[key === 'all' ? 0 : 1].focus();});
      el.classList.toggle('selected', selected === key); el.setAttribute('aria-pressed', String(selected === key)); $('#reportFilters').append(el);
    }
    $('#reportRows').replaceChildren();
    $('#listStatus').hidden = !loading && !listFailed;
    if (loading) status($('#listStatus'), c().loading);
    else if (listFailed) status($('#listStatus'), c().failed, load);
    if (loading || listFailed) return;
    const matches = records.filter(r => selected === 'all' || !r.is_read);
    for (const r of matches) {
      const row = node('tr');
      const action = node('td'); action.append(button(c().view, () => open(r.id)));
      row.append(node('td', r.candidate_name), node('td', r.position), node('td', date(r.completed_at)), node('td', c()[r.is_read ? 'read' : 'unread'], r.is_read ? '' : 'report-unread'), action);
      $('#reportRows').append(row);
    }
    if (!matches.length) {const row = node('tr'), cell = node('td', c()[selected === 'unread' ? 'noUnread' : 'empty'], 'interview-empty'); cell.colSpan = 5; row.append(cell); $('#reportRows').append(row);}
  }
  function mediaUrl(value) {
    if (!value) return null;
    try {const url = new URL(value, location.href); return ['https:', 'http:'].includes(url.protocol) ? url.href : null;} catch {return null;}
  }
  function renderDetail() {
    $('#reportArticle').hidden = !detail;
    $('#detailStatus').hidden = Boolean(detail);
    if (!detail) {status($('#detailStatus'), detailFailed ? c().failed : c().loading, detailFailed ? () => open(activeId, true) : null); return;}
    $('#reportCandidate').textContent = detail.candidate_name;
    $('#reportMeta').textContent = `${detail.position} · ${date(detail.completed_at)}`;
    $('#reportText').textContent = detail.report_text;
    $('#reportMedia').replaceChildren();
    if (detail.recording_url || detail.video_url) $('#reportMedia').append(node('p', c().mediaDemo, 'report-meta'));
    for (const [key, tag, label] of [['recording_url','audio','audio'], ['video_url','video','video']]) {
      if (!detail[key]) continue;
      const section = node('section'), heading = node('h3', c()[label]), url = mediaUrl(detail[key]); section.append(heading);
      if (url) {
        const player = node(tag); player.controls = true; player.preload = 'none'; player.src = url;
        const error = node('p', c().mediaError); error.hidden = true;
        player.addEventListener('error', () => {error.hidden = false;}); section.append(player, error);
      } else section.append(node('p', c().mediaError));
      $('#reportMedia').append(section);
    }
  }
  function load() {
    records = demo.list(bridge.user?.id);
    loading = false; listFailed = false;
    count(records.filter(record => !record.is_read).length);
    renderList();
  }
  function open(id, retry = false) {
    if (!retry) scroll = window.scrollY;
    activeId = id;
    detail = records.find(record => record.id === id) || null;
    detailFailed = !detail;
    $('#reportList').hidden = true; $('#reportDetail').hidden = false;
    renderHeading(); renderDetail(); window.scrollTo(0,0); $('#backReports').focus();
    if (detail) {
      detail.is_read = true;
      demo.markRead(bridge.user?.id, id);
      count(records.filter(record => !record.is_read).length);
    }
  }
  $('#backReports').addEventListener('click', () => {
    activeId = null; detail = null;
    $('#reportMedia').replaceChildren(); $('#reportDetail').hidden = true; $('#reportList').hidden = false;
    renderHeading(); renderList(); window.scrollTo(0,scroll);
  });
  function translate() {
    renderHeading();
    document.querySelectorAll('[data-ui]').forEach(el => {el.textContent = c()[el.dataset.ui];});
    $('#reportFilters').setAttribute('aria-label', c().reading); renderList(); if (activeId !== null) renderDetail();
  }
  window.addEventListener('aomera-language-change', translate);
  window.addEventListener('aomera-user-ready', load);
  load();
  translate();
})();
