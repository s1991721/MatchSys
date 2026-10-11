(() => {
  const bridge = window.AIInterviewFrame, api = window.AIInterview;
  const $ = selector => document.querySelector(selector);
  const copy = {
    'zh-CN': {title:'评估报告', detailTitle:'报告详情', candidate:'候选人', position:'岗位', time:'报告生成时间', reading:'阅读状态', action:'操作', all:'全部', unread:'未读', read:'已读', view:'查看报告', back:'← 返回报告列表', loading:'正在加载…', empty:'暂无已完成的报告。', noUnread:'暂无未读报告。', failed:'加载失败，请重试。', retry:'重试', audio:'面试录音', video:'面试视频', mediaError:'媒体无法播放，请稍后重试。'},
    ja: {title:'評価レポート', detailTitle:'レポート詳細', candidate:'候補者', position:'職種', time:'レポート生成日時', reading:'閲覧状態', action:'操作', all:'すべて', unread:'未読', read:'既読', view:'レポートを見る', back:'← 一覧に戻る', loading:'読み込み中…', empty:'完成したレポートはありません。', noUnread:'未読レポートはありません。', failed:'読み込みに失敗しました。', retry:'再試行', audio:'面接音声', video:'面接動画', mediaError:'メディアを再生できません。後でもう一度お試しください。'}
  };
  const c = () => copy[bridge.lang] || copy.ja;
  const text = (zh, ja) => bridge.lang === 'zh-CN' ? zh : ja;
  let records = [], selected = 'all', detail = null, scroll = 0, loading = true;
  let listError = null, detailError = null, readError = null, activeId = null;
  const initialQuery = new URLSearchParams(location.search);
  let interviewFilter = /^[1-9]\d*$/.test(initialQuery.get('interview') || '') ? initialQuery.get('interview') : '';
  let page = 1, total = 0, listSequence = 0, detailSequence = 0;
  const pageSize = 20;
  let listController = null, detailController = null;
  const readingRequests = new Map();
  let listLoaded = false;
  const pagination = document.createElement('div'); pagination.className = 'interview-pagination'; $('#reportList').append(pagination);
  const scores = document.createElement('section'); scores.className = 'report-scores'; $('#reportText').after(scores);
  const readStatus = document.createElement('div'); readStatus.setAttribute('role', 'status'); $('#reportMeta').after(readStatus);
  function node(tag, content, className = '') { const el = document.createElement(tag); el.className = className; if (content !== undefined) el.textContent = content; return el; }
  function button(content, action) { const el = node('button', content, 'outline-action'); el.type = 'button'; el.addEventListener('click', action); return el; }
  function date(value) { return value && Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat(bridge.lang, {timeZone:'Asia/Tokyo', dateStyle:'medium', timeStyle:'short'}).format(new Date(value)) : '—'; }
  function status(el, message, retry) { el.replaceChildren(node('p', message)); if (retry) el.append(button(c().retry, retry)); }
  function heading() { const title = activeId === null ? c().title : c().detailTitle; $('#reportPageTitle').textContent = title; document.title = `AOMERA — ${title}`; }
  function renderList() {
    $('#reportFilters').replaceChildren();
    for (const key of ['all','unread']) {
      const el = button(c()[key], () => {selected = key; page = 1; load();}); el.classList.toggle('selected', selected === key); el.setAttribute('aria-pressed', String(selected === key)); $('#reportFilters').append(el);
    }
    if (interviewFilter) $('#reportFilters').append(button(text('查看全部报告', 'すべてのレポートを見る'), () => {interviewFilter = ''; page = 1; load();}));
    $('#reportRows').replaceChildren(); pagination.replaceChildren();
    $('#listStatus').hidden = !loading && !listError;
    if (loading) status($('#listStatus'), c().loading);
    else if (listError) status($('#listStatus'), api.errorMessage(listError, bridge.lang), load);
    if (loading || listError) return;
    for (const report of records) {
      const row = node('tr'), action = node('td'); action.append(button(c().view, () => open(report.id)));
      row.append(node('td', report.candidate_name), node('td', report.position_name), node('td', date(report.generated_at)), node('td', c()[report.is_read ? 'read' : 'unread'], report.is_read ? '' : 'report-unread'), action); $('#reportRows').append(row);
    }
    if (!records.length) { const row = node('tr'), cell = node('td', c()[selected === 'unread' ? 'noUnread' : 'empty'], 'interview-empty'); cell.colSpan = 5; row.append(cell); $('#reportRows').append(row); }
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const previous = button(text('上一页', '前へ'), () => {page--; load();}); previous.disabled = page <= 1;
    const next = button(text('下一页', '次へ'), () => {page++; load();}); next.disabled = page >= pages;
    pagination.append(node('span', text(`共 ${total} 条`, `全 ${total} 件`)), previous, node('span', `${page} / ${pages}`), next);
  }
  function mediaUrl(value) {
    if (!value) return null;
    // 对象存储 key 不是 URL，仅播放后端明确提供的绝对签名地址。
    try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
  }
  function renderDetail() {
    $('#reportArticle').hidden = !detail; $('#detailStatus').hidden = Boolean(detail);
    if (!detail) {status($('#detailStatus'), detailError ? api.errorMessage(detailError, bridge.lang) : c().loading, detailError ? () => open(activeId, true) : null); return;}
    $('#reportCandidate').textContent = detail.candidate_name;
    $('#reportMeta').textContent = `${detail.position_name} · ${c().time} ${date(detail.generated_at)}`;
    $('#reportText').textContent = detail.report_text || '';
    scores.replaceChildren();
    const targets = new Map((detail.assessment_targets || []).map(target => [target.id, target.name]));
    for (const [index, score] of (detail.assessment_scores || []).entries()) {
      const name = targets.get(score.id) || text(`评价项目 ${index + 1}`, `評価項目 ${index + 1}`);
      const section = node('section'); section.append(node('h3', `${name} · ${score.score}/100`), node('p', score.evaluation)); scores.append(section);
    }
    renderReadStatus();
    $('#reportMedia').replaceChildren();
    for (const [key, storage, tag, label] of [['recording_url','recording_storage_key','audio','audio'], ['video_url','video_storage_key','video','video']]) {
      if (!detail[key] && !detail[storage]) continue;
      const section = node('section'); section.append(node('h3', c()[label])); const url = mediaUrl(detail[key]);
      if (url) {
        const player = node(tag); player.controls = true; player.preload = 'none'; player.src = url;
        const error = node('p', c().mediaError); error.hidden = true; player.addEventListener('error', () => {error.hidden = false;}); section.append(player, error);
      } else section.append(node('p', text('录制文件已保存，播放功能尚未开放。', '録画・録音は保存されています。再生機能は準備中です。')));
      $('#reportMedia').append(section);
    }
  }
  function renderReadStatus() {
    readStatus.replaceChildren();
    if (readError) status(readStatus, text('报告已加载，但阅读状态保存失败。', 'レポートは表示できましたが、閲覧状態を保存できませんでした。'), () => markRead(activeId));
  }
  async function load() {
    if (!bridge.user) return;
    listController?.abort(); listController = new AbortController();
    const current = ++listSequence; loading = true; listError = null; renderList();
    try {
      const response = await api.requestJson(api.query('/reports', {reading:selected, page, page_size:pageSize, interview_id:interviewFilter}), {signal:listController.signal});
      if (current !== listSequence) return;
      records = response.data.items; total = response.data.total; listLoaded = true;
      const lastPage = Math.max(1, Math.ceil(total / pageSize));
      if (page > lastPage) {page = lastPage; return load();}
    } catch (error) {if (current !== listSequence || error.name === 'AbortError') return; listError = error;}
    finally {if (current === listSequence) {loading = false; renderList();}}
  }
  async function markRead(id) {
    // 同一报告的阅读状态写入只保留一个进行中的请求。
    if (readingRequests.has(id)) return readingRequests.get(id);
    const request = saveRead(id).finally(() => readingRequests.delete(id));
    readingRequests.set(id, request);
    return request;
  }
  async function saveRead(id) {
    try {
      const response = await api.requestJson(`/reports/${id}/read`, {method:'POST'});
      const row = records.find(record => record.id === id); if (row) {row.is_read = true; row.read_at = response.data.read_at;}
      if (activeId === id && detail) {detail.is_read = true; detail.read_at = response.data.read_at; readError = null; readStatus.replaceChildren();}
      bridge.recordsUpdated();
    } catch (error) {if (activeId === id && detail) {readError = error; renderReadStatus();}}
  }
  async function open(id, retry = false) {
    if (!retry) scroll = window.scrollY;
    activeId = id; detail = null; detailError = null; readError = null;
    detailController?.abort(); detailController = new AbortController();
    const current = ++detailSequence;
    $('#reportMedia').replaceChildren(); $('#reportList').hidden = true; $('#reportDetail').hidden = false;
    heading(); renderDetail(); window.scrollTo(0,0); $('#backReports').focus();
    try {
      const response = await api.requestJson(`/reports/${id}`, {signal:detailController.signal});
      if (current !== detailSequence || activeId !== id) return;
      detail = response.data.report; renderDetail();
      // 正文成功显示后才写入已读，GET 失败不改变未读数。
      if (!detail.is_read) await markRead(id);
    } catch (error) {if (error.name !== 'AbortError' && current === detailSequence && activeId === id) {detailError = error; renderDetail();}}
  }
  $('#backReports').addEventListener('click', async () => {
    detailController?.abort();
    activeId = null; detail = null; detailSequence++;
    $('#reportMedia').replaceChildren(); $('#reportDetail').hidden = true; $('#reportList').hidden = false;
    heading(); await load(); if (activeId === null) window.scrollTo(0,scroll);
  });
  function translate() {heading(); document.querySelectorAll('[data-ui]').forEach(el => {el.textContent = c()[el.dataset.ui];}); $('#reportFilters').setAttribute('aria-label', c().reading); renderList(); if (activeId !== null) renderDetail();}
  window.addEventListener('aomera-language-change', translate);
  window.addEventListener('aomera-user-ready', async () => {
    const requested = initialQuery.get('report');
    // 直接查看详情时不先查询隐藏列表，返回列表后再加载。
    if (/^[1-9]\d*$/.test(requested || '') && !listLoaded) await open(Number(requested));
    else await load();
  });
  window.addEventListener('storage', event => {if (event.key === 'aomera-data-updated' && activeId === null) load();});
  document.addEventListener('visibilitychange', () => {if (!document.hidden && activeId === null) load();});
  window.addEventListener('pagehide', () => {listController?.abort(); detailController?.abort();});
  translate();
})();
