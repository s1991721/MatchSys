(() => {
  const bridge = window.AIInterviewFrame;
  const model = window.AIInterviewList;
  const $ = selector => document.querySelector(selector);
  const copy = {
    'zh-CN': {
      title: '面试管理', create: '＋ 创建面试',
      all: '全部', waiting: '待参加', completed: '已完成', abnormal: '异常', expired: '已过期',
      search: '搜索候选人', searchPlaceholder: '姓名或邮箱', position: '岗位', createdDate: '创建日期', from: '创建日期 · 从', to: '至', reset: '重置',
      candidate: '候选人', status: '状态', created: '创建时间', relatedTime: '截止／完成时间', action: '操作',
      empty: '尚未创建面试，请点击「创建面试」开始。', noMatch: '没有符合条件的面试，请调整筛选条件。',
      pageSize: '每页', previous: '上一页', next: '下一页', total: '共 {total} 条 · 当前 {start}–{end} 条',
      deadline: '截止', finished: '完成', unknownError: '面试失败或中断', generating: '报告生成中', reportUnavailable: '报告功能准备中',
      copyLink: '复制邀请链接', copied: '邀请预览链接已复制', copyFallback: '请复制邀请预览链接', invalidRange: '开始日期不能晚于结束日期。'
    },
    ja: {
      title: '面接管理', create: '＋ 面接を作成',
      all: 'すべて', waiting: '参加待ち', completed: '完了', abnormal: '異常', expired: '期限切れ',
      search: '候補者を検索', searchPlaceholder: '氏名またはメール', position: '職種', createdDate: '作成日', from: '作成日 · 開始', to: '終了', reset: 'リセット',
      candidate: '候補者', status: 'ステータス', created: '作成日時', relatedTime: '有効期限／完了日時', action: '操作',
      empty: '面接はまだありません。「面接を作成」から始めましょう。', noMatch: '条件に一致する面接はありません。絞り込み条件を変更してください。',
      pageSize: '表示件数', previous: '前へ', next: '次へ', total: '全 {total} 件 · {start}–{end} 件を表示',
      deadline: '有効期限', finished: '完了', unknownError: '面接の失敗または中断', generating: 'レポート生成中', reportUnavailable: 'レポート機能は準備中',
      copyLink: '招待リンクをコピー', copied: '招待プレビューをコピーしました', copyFallback: '招待プレビューをコピーしてください', invalidRange: '開始日は終了日以前にしてください。'
    }
  };
  let records = [], selected = 'all', page = 1, toastTimer;
  const values = () => copy[bridge.lang];
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  function formatDate(value) {
    return Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat(bridge.lang, { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—';
  }
  async function copyLink(link) {
    try {
      await navigator.clipboard.writeText(link);
      $('#toast').textContent = values().copied;
      $('#toast').classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 2400);
    } catch { window.prompt(values().copyFallback, link); }
  }
  function render() {
    const c = values(), now = Date.now();
    $('#statusFilters').replaceChildren();
    for (const status of ['all', 'waiting', 'completed', 'abnormal', 'expired']) {
      const button = node('button', `interview-tab${selected === status ? ' selected' : ''}`);
      button.type = 'button';
      button.setAttribute('aria-pressed', String(selected === status));
      button.append(node('span', '', c[status]), node('span', 'tab-count', records.filter(record => status === 'all' || model.status(record, now) === status).length));
      button.addEventListener('click', () => { selected = status; page = 1; render(); $('#statusFilters').children[['all', 'waiting', 'completed', 'abnormal', 'expired'].indexOf(status)].focus(); });
      $('#statusFilters').append(button);
    }
    const from = $('#createdFrom').value, to = $('#createdTo').value;
    const invalid = Boolean(from && to && from > to);
    $('#filterError').hidden = !invalid;
    $('#filterError').textContent = c.invalidRange;
    const matches = invalid ? [] : model.filter(records, { status: selected, query: $('#candidateSearch').value, from, to }, now);
    const size = Number($('#pageSize').value), pages = Math.max(1, Math.ceil(matches.length / size));
    page = Math.min(page, pages);
    const start = (page - 1) * size;
    $('#interviewRows').replaceChildren();
    for (const record of matches.slice(start, start + size)) {
      const status = model.status(record, now), row = node('tr', '');
      const candidate = node('td', '');
      candidate.append(node('strong', 'interview-name', record.candidateName || '—'), node('span', 'interview-secondary', record.candidateEmail || '—'));
      const state = node('td', '');
      state.append(node('span', `interview-status ${status}`, c[status]));
      if (status === 'abnormal') state.append(node('span', 'interview-secondary', record.errorReason || c.unknownError));
      if (status === 'completed') state.append(node('span', 'interview-secondary', record.reportStatus === 'generating' ? c.generating : c.reportUnavailable));
      const time = node('td', '');
      time.append(node('span', 'interview-secondary', status === 'completed' ? c.finished : c.deadline), node('span', '', formatDate(status === 'completed' ? record.completedAt : record.expiresAt)));
      const action = node('td', '');
      if (status === 'waiting') {
        const button = node('button', 'outline-action', c.copyLink);
        button.type = 'button'; button.addEventListener('click', () => copyLink(record.link)); action.append(button);
      } else action.textContent = '—';
      row.append(candidate, node('td', '', record.position), state, node('td', '', formatDate(record.createdAt)), time, action);
      $('#interviewRows').append(row);
    }
    if (!matches.length) {
      const row = node('tr', ''), cell = node('td', 'interview-empty', records.length ? c.noMatch : c.empty);
      cell.colSpan = 6; row.append(cell); $('#interviewRows').append(row);
    }
    $('#resultCount').textContent = c.total.replace('{total}', matches.length).replace('{start}', matches.length ? start + 1 : 0).replace('{end}', Math.min(start + size, matches.length));
    $('#pageNumber').textContent = `${page} / ${pages}`;
    $('#previousPage').disabled = page === 1; $('#nextPage').disabled = page === pages;
  }
  function translate() {
    const c = values();
    document.title = `AOMERA AI面接官 — ${c.title}`;
    document.querySelectorAll('[data-ui]').forEach(element => { element.textContent = c[element.dataset.ui]; });
    $('#candidateSearch').placeholder = c.searchPlaceholder;
    $('#statusFilters').setAttribute('aria-label', c.status);
    render();
  }
  function load() { records = bridge.user ? bridge.records(bridge.user.id) : []; page = 1; translate(); }
  $('#createInterview').addEventListener('click', () => bridge.navigate('create'));
  $('#filters').addEventListener('submit', event => event.preventDefault());
  $('#filters').addEventListener('input', () => { page = 1; render(); });
  $('#resetFilters').addEventListener('click', () => { $('#filters').reset(); selected = 'all'; page = 1; render(); });
  $('#pageSize').addEventListener('change', () => { page = 1; render(); });
  $('#previousPage').addEventListener('click', () => { page--; render(); });
  $('#nextPage').addEventListener('click', () => { page++; render(); });
  window.addEventListener('aomera-language-change', translate);
  window.addEventListener('aomera-user-ready', load);
  window.addEventListener('storage', event => { if (event.key === null || event.key === `aomera-interview-demo:${bridge.user?.id}`) load(); });
  // Reclassify invitations at their deadline, including after a background tab resumes.
  setInterval(render, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
  load();
})();
