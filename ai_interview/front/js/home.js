(() => {
  const copy = window.AIInterviewCopy;
  let lang = localStorage.getItem("aomera-language") || "ja";
  const firstCharacter = (value) => Array.from(String(value || "").trim())[0] || "—";
  const showToast = () => { document.querySelector("#toast").textContent = copy[lang].demoAction; document.querySelector("#toast").classList.add("show"); setTimeout(() => document.querySelector("#toast").classList.remove("show"), 2400); };


  const filterKeys = { reports: 'pendingReports', abnormal: 'abnormalInterviews', waiting: 'waitingCandidates', today: 'todayInterviews' };
  let selectedFilter = 'reports';
  let localRecords = [];
  const samples = [
    { name: '山田 太郎', position: 'positionPm', state: 'reports', today: true, time: '12:42' },
    { name: '鈴木 花子', position: 'positionBackend', state: 'reports', today: true, time: '11:30' },
    { name: '王 芳', position: 'positionUx', state: 'reports', today: true, time: '10:15' },
    { name: '佐藤 美咲', position: 'positionUx', state: 'abnormal', today: true, time: '09:18' },
    { name: '李 明', position: 'positionBackend', state: 'waiting', time: 'expiringTime' },
    { name: '高橋 健', position: 'positionPm', state: 'waiting', time: 'invitationValid' },
    { name: '田中 葵', position: 'positionBackend', state: 'running', today: true, time: '13:00' },
    { name: '陳 晨', position: 'positionUx', state: 'completed', today: true, time: '08:45' }
  ];
  const filterCopy = {
    ja: { latestFirst: '完了日時の新しい順', todayScope: '本日開始した面接・状態は他の分類と重複します', emptyFilter: '該当する面接はありません。', invitationValid: '招待リンクは有効です', running: '面接中', completed: 'レポート確認済み', copyLink: 'リンクをコピー', expired: '招待の期限切れ', completedAt: '面接完了 · 今日', startedAt: '面接開始 · 今日', interruptedAt: '中断 · 今日', localPreview: 'ブラウザ保存のプレビュー・有効期限' },
    'zh-CN': { latestFirst: '按完成时间从新到旧', todayScope: '今日开始的面试，与其他分类可能重叠', emptyFilter: '暂无此类面试。', invitationValid: '邀请链接有效', running: '面试中', completed: '报告已查看', copyLink: '复制链接', expired: '邀请已过期', completedAt: '面试完成 · 今天', startedAt: '面试开始 · 今天', interruptedAt: '面试中断 · 今天', localPreview: '浏览器保存的预览 · 有效至' }
  };
  function renderFilteredInterviews() {
    const values = { ...copy[lang], ...filterCopy[lang] };
    const data = [...samples, ...localRecords.map((record) => ({ ...record, name: record.candidateName || '—', state: new Date(record.expiresAt) <= new Date() ? 'expired' : 'waiting', local: true }))];
    const matches = (item, filter) => filter === 'today' ? item.today === true : filter === 'abnormal' ? ['abnormal', 'expired'].includes(item.state) : item.state === filter;
    document.querySelectorAll('[data-filter]').forEach((button) => {
      const active = button.dataset.filter === selectedFilter;
      button.classList.toggle('selected', active);
      button.setAttribute('aria-pressed', String(active));
      button.querySelector('.stat-count').textContent = data.filter((item) => matches(item, button.dataset.filter)).length;
    });
    const list = data.filter((item) => matches(item, selectedFilter));
    document.querySelector('#actionsTitle').textContent = `${values[filterKeys[selectedFilter]]} · ${list.length} ${values.countUnit}`;
    document.querySelector('#filterNote').textContent = selectedFilter === 'today' ? values.todayScope : selectedFilter === 'reports' ? values.latestFirst : '';
    const container = document.querySelector('#filteredInterviews');
    container.replaceChildren();
    const node = (tag, className, text) => { const el = document.createElement(tag); el.className = className; if (text !== undefined) el.textContent = text; return el; };
    if (!list.length) container.append(node('p', 'empty-interviews', values.emptyFilter));
    list.forEach((item) => {
      const row = node('article', 'action-row');
      const info = node('div', 'candidate-info');
      info.append(node('strong', '', item.name), node('span', '', item.local ? item.position : values[item.position]));
      const status = node('div', 'action-status');
      const statusKey = { reports: 'statusReport', abnormal: 'statusInterrupted', waiting: 'statusWaiting', expired: 'expired', running: 'running', completed: 'completed' }[item.state];
      const statusClass = ['abnormal', 'expired'].includes(item.state) ? 'warning' : item.state === 'waiting' ? 'waiting' : 'report';
      status.append(node('span', `status ${statusClass}`, values[statusKey]));
      const prefix = item.state === 'abnormal' ? values.interruptedAt : item.state === 'running' ? values.startedAt : values.completedAt;
      status.append(node('span', 'action-time', item.local ? `${values.localPreview} ${new Intl.DateTimeFormat(lang, { timeZone: 'Asia/Tokyo', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(item.expiresAt))}` : values[item.time] || `${prefix} ${item.time}`));
      const actionKey = item.local ? 'copyLink' : ['reports', 'completed'].includes(item.state) ? 'reviewReport' : item.state === 'waiting' ? 'viewInvitation' : 'viewDetails';
      const button = node('button', `row-action ${item.state === 'reports' ? '' : 'secondary'}`, values[actionKey]);
      button.type = 'button';
      button.addEventListener('click', () => item.local ? copyInvitation(item.link) : showToast());
      row.append(node('div', 'candidate-avatar', firstCharacter(item.name)), info, status, button);
      container.append(row);
    });
  }
  document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => { selectedFilter = button.dataset.filter; renderFilteredInterviews(); }));


  async function copyInvitation(link) {
    try { await navigator.clipboard.writeText(link); }
    catch { window.prompt(lang === 'ja' ? 'リンクをコピー' : '复制链接', link); }
  }
  function applyLanguage(next) {
    lang = copy[next] ? next : 'ja';
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-copy]').forEach(node => { node.textContent = copy[lang][node.dataset.copy] || ''; });
    document.querySelector('[data-ui="create"]').textContent = lang === 'ja' ? '面接を作成' : '创建面试';
    document.querySelector('[data-ui="sampleData"]').textContent = lang === 'ja' ? '一覧にはサンプルデータが含まれます。作成した招待プレビューはこのブラウザに保存されます。' : '列表包含示例数据；创建的邀请预览仅保存在当前浏览器。';
    const user = window.AIInterviewFrame.user;
    document.querySelector('#greetingName').textContent = user ? `${user.display_name || user.user_name}${lang === 'ja' ? 'さん。' : '。'}` : '';
    renderFilteredInterviews();
  }
  window.addEventListener('aomera-language-change', event => applyLanguage(event.detail));
  window.addEventListener('aomera-user-ready', event => {
    localRecords = window.AIInterviewFrame.records(event.detail.id);
    applyLanguage(window.AIInterviewFrame.lang);
  });
  document.querySelector('#createInterview').addEventListener('click', () => window.AIInterviewFrame.navigate('create'));
  document.querySelector('#today').textContent = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Tokyo'}).format(new Date()).replaceAll('-', '.');
  applyLanguage(lang);
})();
