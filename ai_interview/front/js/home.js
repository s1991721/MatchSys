(() => {
  const bridge = window.AIInterviewFrame, api = window.AIInterview, copy = window.AIInterviewCopy;
  const $ = selector => document.querySelector(selector);
  const text = (zh, ja) => bridge.lang === 'zh-CN' ? zh : ja;
  const filterKeys = {reports:'pendingReports', abnormal:'abnormalInterviews', waiting:'waitingCandidates', today:'todayInterviews'};
  let selected = 'reports', stats = null, records = [], total = 0, page = 1, loading = true, failure = null, sequence = 0;
  let controller = null;
  const node = (tag, className, content) => { const el = document.createElement(tag); el.className = className; if (content !== undefined) el.textContent = content; return el; };
  const today = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Tokyo', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date());
  function render() {
    const values = copy[bridge.lang], counts = {reports:stats?.unread_reports, abnormal:stats ? stats.abnormal + stats.expired : null, waiting:stats?.waiting, today:stats?.today_created};
    document.querySelectorAll('[data-filter]').forEach(button => {
      button.classList.toggle('selected', button.dataset.filter === selected);
      button.setAttribute('aria-pressed', String(button.dataset.filter === selected));
      button.querySelector('.stat-count').textContent = counts[button.dataset.filter] ?? '—';
    });
    $('#actionsTitle').textContent = `${values[filterKeys[selected]]} · ${counts[selected] ?? '—'} ${values.countUnit}`;
    $('#filterNote').textContent = selected === 'today' ? text('今日创建的面试', '本日作成した面接') : selected === 'reports' ? text('按报告生成时间排序', 'レポート生成日時順') : '';
    const container = $('#filteredInterviews'); container.replaceChildren();
    if (loading || failure || !records.length) {
      container.append(node('p', 'empty-interviews', loading ? text('正在加载…', '読み込み中…') : failure ? api.errorMessage(failure, bridge.lang) : text('暂无此类记录。', '該当するデータはありません。')));
      if (failure) { const retry = node('button', 'outline-action', text('重试', '再試行')); retry.type = 'button'; retry.addEventListener('click', load); container.append(retry); }
      return;
    }
    for (const record of records) {
      const report = selected === 'reports', state = report ? 'reports' : record.status;
      const row = node('article', 'action-row'), info = node('div', 'candidate-info'), status = node('div', 'action-status');
      info.append(node('strong', '', record.candidate_name), node('span', '', record.position_name));
      const label = {reports:values.statusReport, waiting:values.statusWaiting, completed:text('已完成', '完了'), abnormal:values.statusInterrupted, expired:text('已过期', '期限切れ')}[state];
      const time = report ? record.generated_at : state === 'waiting' ? record.invite_expires_at : record.created_at;
      const prefix = report ? text('报告生成', 'レポート生成') : state === 'waiting' ? text('有效至', '有効期限') : text('创建于', '作成日時');
      status.append(node('span', `status ${['abnormal','expired'].includes(state) ? 'warning' : state === 'waiting' ? 'waiting' : 'report'}`, label), node('span', 'action-time', `${prefix} · ${new Intl.DateTimeFormat(bridge.lang, {timeZone:'Asia/Tokyo', dateStyle:'short', timeStyle:'short'}).format(new Date(time))}`));
      const action = node('button', 'row-action secondary', report || state === 'completed' ? text('查看报告', 'レポートを見る') : text('面试管理', '面接管理'));
      action.type = 'button'; action.addEventListener('click', () => bridge.navigate(report || state === 'completed' ? 'reports' : 'interviews', report ? {report:record.id} : state === 'completed' ? {interview:record.id} : {}));
      row.append(node('div', 'candidate-avatar', Array.from(record.candidate_name)[0] || '—'), info, status, action); container.append(row);
    }
    const pages = Math.max(1, Math.ceil(total / 10));
    if (pages > 1) {
      const nav = node('div', 'interview-pagination');
      for (const [label, step] of [[text('上一页','前へ'), -1], [text('下一页','次へ'), 1]]) {
        const button = node('button', 'outline-action', label); button.type = 'button'; button.disabled = step < 0 ? page <= 1 : page >= pages;
        button.addEventListener('click', () => {page += step; load();}); nav.append(button);
      }
      nav.append(node('span', '', `${page} / ${pages}`)); container.append(nav);
    }
  }
  async function load() {
    if (!bridge.user) return;
    controller?.abort(); controller = new AbortController();
    const current = ++sequence; loading = true; failure = null; render();
    const params = {page, page_size:10};
    let path;
    if (selected === 'reports') path = api.query('/reports', {...params, reading:'unread'});
    else if (selected === 'today') path = api.query('/interviews', {...params, from:today(), to:today()});
    else path = api.query('/interviews', {...params, status:selected === 'abnormal' ? 'attention' : selected});
    try {
      const [summary, list] = await Promise.all([api.requestSummary('/dashboard'), api.requestJson(path, {signal:controller.signal})]);
      if (current !== sequence) return;
      stats = summary.data; records = list.data.items; total = list.data.total;
      const lastPage = Math.max(1, Math.ceil(total / 10));
      if (page > lastPage) {page = lastPage; return load();}
    } catch (error) { if (current !== sequence || error.name === 'AbortError') return; failure = error; records = []; }
    finally { if (current === sequence) {loading = false; render();} }
  }
  function translate() {
    document.title = `AOMERA — ${copy[bridge.lang].navHome}`;
    document.querySelectorAll('[data-copy]').forEach(el => {el.textContent = copy[bridge.lang][el.dataset.copy] || '';});
    $('[data-ui="create"]').textContent = text('创建面试', '面接を作成');
    $('[data-ui="sampleData"]').hidden = true;
    $('[data-copy="startedToday"]').textContent = text('今日创建', '本日作成');
    $('#greetingName').textContent = bridge.user ? `${bridge.user.display_name || bridge.user.user_name}${text('。','さん。')}` : '';
    $('#today').textContent = today().replaceAll('-', '.'); render();
  }
  document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {selected = button.dataset.filter; page = 1; load();}));
  $('#createInterview').addEventListener('click', () => bridge.navigate('create'));
  window.addEventListener('aomera-language-change', translate);
  window.addEventListener('aomera-user-ready', () => {translate(); load();});
  window.addEventListener('storage', event => { if (event.key === 'aomera-data-updated') load(); });
  document.addEventListener('visibilitychange', () => {if (!document.hidden) load();});
  window.addEventListener('pagehide', () => controller?.abort());
  translate();
})();
