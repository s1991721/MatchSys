(() => {
  const bridge = window.AIInterviewFrame;
  const api = window.AIInterview;
  const $ = selector => document.querySelector(selector);
  const copy = {
    'zh-CN': {
      title: '面试管理', create: '＋ 创建面试',
      all: '全部', waiting: '待参加', completed: '已完成', abnormal: '异常', expired: '已过期',
      search: '搜索候选人', searchPlaceholder: '姓名或邮箱', position: '岗位', createdDate: '创建日期', from: '创建日期 · 从', to: '至', reset: '重置',
      candidate: '候选人', status: '状态', created: '创建时间', relatedTime: '邀请截止时间', action: '操作',
      empty: '尚未创建面试，请点击「创建面试」开始。', noMatch: '没有符合条件的面试，请调整筛选条件。',
      pageSize: '每页', previous: '上一页', next: '下一页', total: '共 {total} 条 · 当前 {start}–{end} 条',
      deadline: '截止', finished: '完成', unknownError: '面试失败或中断', generating: '报告生成中', reportUnavailable: '报告功能准备中',
      copyLink: '复制邀请链接', copied: '邀请链接已复制', copyFallback: '请复制邀请链接', invalidRange: '开始日期不能晚于结束日期。'
    },
    ja: {
      title: '面接管理', create: '＋ 面接を作成',
      all: 'すべて', waiting: '参加待ち', completed: '完了', abnormal: '異常', expired: '期限切れ',
      search: '候補者を検索', searchPlaceholder: '氏名またはメール', position: '職種', createdDate: '作成日', from: '作成日 · 開始', to: '終了', reset: 'リセット',
      candidate: '候補者', status: 'ステータス', created: '作成日時', relatedTime: '招待の有効期限', action: '操作',
      empty: '面接はまだありません。「面接を作成」から始めましょう。', noMatch: '条件に一致する面接はありません。絞り込み条件を変更してください。',
      pageSize: '表示件数', previous: '前へ', next: '次へ', total: '全 {total} 件 · {start}–{end} 件を表示',
      deadline: '有効期限', finished: '完了', unknownError: '面接の失敗または中断', generating: 'レポート生成中', reportUnavailable: 'レポート機能は準備中',
      copyLink: '招待リンクをコピー', copied: '招待リンクをコピーしました', copyFallback: '招待リンクをコピーしてください', invalidRange: '開始日は終了日以前にしてください。'
    }
  };
  let records = [], selected = 'all', page = 1, total = 0, counts = null;
  let loading = true, failure = null, sequence = 0, controller = null, debounce, toastTimer;
  const values = () => copy[bridge.lang] || copy.ja;
  const text = (zh, ja) => bridge.lang === 'zh-CN' ? zh : ja;
  const node = (tag, className, content) => {
    const element = document.createElement(tag); element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  };
  function formatDate(value) {
    return Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat(bridge.lang, {timeZone:'Asia/Tokyo', dateStyle:'short', timeStyle:'short'}).format(new Date(value)) : '—';
  }
  function toast(message) {
    $('#toast').textContent = message; $('#toast').classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 3000);
  }
  async function copyLink(record, button) {
    button.disabled = true;
    try { if (await api.copyInvitation(bridge.user.id, record.id, bridge.lang)) toast(values().copied); }
    catch (error) { toast(api.errorMessage(error, bridge.lang)); }
    finally { button.disabled = false; }
  }
  function render() {
    const c = values(), size = Number($('#pageSize').value), pages = Math.max(1, Math.ceil(total / size));
    $('#statusFilters').replaceChildren();
    for (const status of ['all', 'waiting', 'completed', 'abnormal', 'expired']) {
      const button = node('button', `interview-tab${selected === status ? ' selected' : ''}`);
      button.type = 'button'; button.setAttribute('aria-pressed', String(selected === status));
      button.append(node('span', '', c[status]), node('span', 'tab-count', counts?.[status === 'all' ? 'total_interviews' : status] ?? '—'));
      button.addEventListener('click', () => { selected = status; page = 1; load(); });
      $('#statusFilters').append(button);
    }
    const invalid = Boolean($('#createdFrom').value && $('#createdTo').value && $('#createdFrom').value > $('#createdTo').value);
    $('#filterError').hidden = !invalid;
    $('#filterError').textContent = c.invalidRange;
    $('#interviewRows').replaceChildren();
    if (loading || failure || invalid || !records.length) {
      const row = node('tr', ''), cell = node('td', 'interview-empty', invalid ? c.invalidRange : loading ? text('正在加载…', '読み込み中…') : failure ? api.errorMessage(failure, bridge.lang) : ($('#candidateSearch').value || selected !== 'all' || $('#createdFrom').value || $('#createdTo').value) ? c.noMatch : c.empty);
      cell.colSpan = 6;
      if (failure) {
        const retry = node('button', 'outline-action', text('重试', '再試行'));
        retry.type = 'button'; retry.addEventListener('click', () => load()); cell.append(retry);
      }
      row.append(cell); $('#interviewRows').append(row);
    } else for (const record of records) {
      const row = node('tr', ''), candidate = node('td', ''), state = node('td', ''), action = node('td', '');
      candidate.append(node('strong', 'interview-name', record.candidate_name), node('span', 'interview-secondary', record.candidate_email));
      state.append(node('span', `interview-status ${record.status}`, c[record.status]));
      if (record.status === 'waiting') {
        const cached = api.cachedInvitation(bridge.user.id, record.id);
        const button = node('button', 'outline-action', cached ? c.copyLink : text('重新生成邀请链接', '招待リンクを再発行'));
        button.type = 'button'; button.addEventListener('click', () => copyLink(record, button)); action.append(button);
      } else if (record.status === 'completed') {
        const button = node('button', 'outline-action', text('查看报告', 'レポートを見る'));
        button.type = 'button'; button.addEventListener('click', () => bridge.navigate('reports', {interview:record.id})); action.append(button);
      } else action.textContent = '—';
      row.append(candidate, node('td', '', record.position_name), state, node('td', '', formatDate(record.created_at)), node('td', '', formatDate(record.invite_expires_at)), action);
      $('#interviewRows').append(row);
    }
    const start = (page - 1) * size;
    $('#resultCount').textContent = loading || failure ? '—' : c.total.replace('{total}', total).replace('{start}', total ? start + 1 : 0).replace('{end}', Math.min(start + size, total));
    $('#pageNumber').textContent = `${page} / ${pages}`;
    $('#previousPage').disabled = loading || page <= 1;
    $('#nextPage').disabled = loading || page >= pages;
  }
  async function load() {
    clearTimeout(debounce);
    if (!bridge.user) return;
    controller?.abort(); controller = new AbortController();
    const current = ++sequence;
    if ($('#createdFrom').value && $('#createdTo').value && $('#createdFrom').value > $('#createdTo').value) {
      loading = false; failure = null; records = []; total = 0; render(); return;
    }
    loading = true; failure = null; render();
    try {
      const [response, stats] = await Promise.all([
        api.requestJson(api.query('/interviews', {page, page_size:Number($('#pageSize').value), status:selected, query:$('#candidateSearch').value.trim(), from:$('#createdFrom').value, to:$('#createdTo').value}), {signal:controller.signal}),
        api.requestSummary('/dashboard').catch(error => { if (error.name === 'AbortError') throw error; return null; })
      ]);
      // 搜索输入和翻页可同时产生请求，只展示最后一次请求的结果。
      if (current !== sequence) return;
      records = response.data.items; total = response.data.total; counts = stats?.data || null;
      const lastPage = Math.max(1, Math.ceil(total / Number($('#pageSize').value)));
      if (page > lastPage) { page = lastPage; return load(); }
    } catch (error) { if (current !== sequence || error.name === 'AbortError') return; failure = error; records = []; }
    finally { if (current === sequence) { loading = false; render(); } }
  }
  function translate() {
    const c = values(); document.title = `AOMERA — ${c.title}`;
    document.querySelectorAll('[data-ui]').forEach(element => { element.textContent = c[element.dataset.ui]; });
    $('#candidateSearch').placeholder = c.searchPlaceholder;
    $('#statusFilters').setAttribute('aria-label', c.status); render();
  }
  $('#createInterview').addEventListener('click', () => bridge.navigate('create'));
  $('#filters').addEventListener('submit', event => { event.preventDefault(); page = 1; load(); });
  $('#filters').addEventListener('input', () => { page = 1; clearTimeout(debounce); debounce = setTimeout(load, 300); });
  $('#resetFilters').addEventListener('click', () => { $('#filters').reset(); selected = 'all'; page = 1; load(); });
  $('#pageSize').addEventListener('change', () => { page = 1; load(); });
  $('#previousPage').addEventListener('click', () => { page--; load(); });
  $('#nextPage').addEventListener('click', () => { page++; load(); });
  window.addEventListener('aomera-language-change', translate);
  window.addEventListener('aomera-user-ready', load);
  window.addEventListener('storage', event => { if (event.key === 'aomera-data-updated') load(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
  setInterval(() => { if (!document.hidden && !loading) load(); }, 30000);
  window.addEventListener('pagehide', () => {clearTimeout(debounce); controller?.abort();});
  translate();
})();
