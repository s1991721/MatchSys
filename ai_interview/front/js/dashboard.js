(() => {
  const copy = {
    ja: {
      productName: "AI面接官",
      abnormalInterviews: "面接の異常", expiringTime: "明日期限 · 未参加", viewInvitation: "招待を確認",
      title: "AOMERA AI面接官 — ホーム", navHome: "ホーム", navInterviews: "面接管理", navCandidates: "候補者", navReports: "評価レポート", navHelp: "ヘルプ", navSettings: "設定", planLabel: "今月の面接枠", planLink: "プランを確認", workspaceLabel: "ワークスペース", userName: "田中 悠介", userRole: "採用担当者", accountSettings: "アカウント設定", logout: "ログアウト", greeting: "おはようございます、", greetingName: "田中さん。", welcomeCopy: "今日も、候補者の可能性を見つけましょう。", pendingReports: "未確認レポート", waitingCandidates: "参加待ち", todayInterviews: "本日の面接", countUnit: "件", actionNeeded: "対応が必要です", startedToday: "本日開始", positionPm: "プロダクトマネージャー", positionBackend: "バックエンドエンジニア", positionUx: "UXデザイナー", statusReport: "新しいレポートが届いています", statusWaiting: "参加待ち", statusInterrupted: "面接が中断", reviewReport: "レポートを見る", viewDetails: "詳細を見る", demoAction: "この操作は次の画面で実装予定です。" },
    "zh-CN": {
      productName: "AI面试官",
      abnormalInterviews: "异常面试", expiringTime: "明天到期 · 尚未参加", viewInvitation: "查看邀请",
      title: "AOMERA AI面试官 — 首页", navHome: "首页", navInterviews: "面试管理", navCandidates: "候选人", navReports: "评估报告", navHelp: "帮助", navSettings: "设置", planLabel: "本月面试额度", planLink: "查看套餐", workspaceLabel: "工作空间", userName: "田中悠介", userRole: "招聘负责人", accountSettings: "账户设置", logout: "退出登录", greeting: "早上好，", greetingName: "田中先生。", welcomeCopy: "今天也一起发现候选人的潜力吧。", pendingReports: "待查看报告", waitingCandidates: "等待参加", todayInterviews: "今日面试", countUnit: "项", actionNeeded: "需要处理", startedToday: "今日开始", positionPm: "产品经理", positionBackend: "后端工程师", positionUx: "UX设计师", statusReport: "新报告待查看", statusWaiting: "等待参加", statusInterrupted: "面试已中断", reviewReport: "查看报告", viewDetails: "查看详情", demoAction: "此操作将在后续页面中实现。" }
  };

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
      button.addEventListener('click', () => item.local ? window.dispatchEvent(new CustomEvent('aomera-copy-record', { detail: item.id })) : showToast());
      row.append(node('div', 'candidate-avatar', firstCharacter(item.name)), info, status, button);
      container.append(row);
    });
  }
  document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => { selectedFilter = button.dataset.filter; renderFilteredInterviews(); }));
  window.addEventListener('aomera-records-change', (event) => { localRecords = event.detail; renderFilteredInterviews(); });

  const sidebar = document.querySelector("#sidebar");
  const scrim = document.querySelector("#sidebarScrim");
  const profileButton = document.querySelector("#profileButton");
  const profileMenu = document.querySelector("#profileMenu");
  const toast = document.querySelector("#toast");
  const companyMark = document.querySelector("#companyMark");
  const companyName = document.querySelector("#companyName");
  const userAvatar = document.querySelector("#userAvatar");
  const displayName = document.querySelector("#displayName");
  const greetingName = document.querySelector("#greetingName");
  let lang = localStorage.getItem("aomera-language") || "ja";
  let currentUser = null;
  let toastTimer;

  function firstCharacter(value, fallback = "—") {
    const character = Array.from(String(value || "").trim())[0];
    return character ? character.toLocaleUpperCase() : fallback;
  }

  function renderCurrentUser() {
    if (!currentUser) return;
    const name = currentUser.display_name || currentUser.user_name;
    const workspace = currentUser.company_name || "—";
    companyName.textContent = workspace;
    companyMark.textContent = firstCharacter(workspace);
    displayName.textContent = name;
    userAvatar.textContent = firstCharacter(name);
    greetingName.textContent = lang === "ja" ? `${name}さん。` : `${name}。`;
  }

  function applyLanguage(next) {
    lang = copy[next] ? next : "ja";
    const values = copy[lang];
    document.documentElement.lang = lang;
    document.title = values.title;
    document.querySelectorAll("[data-copy]").forEach((element) => {
      const value = values[element.dataset.copy];
      if (value !== undefined) element.textContent = value;
    });
    document.querySelectorAll("[data-lang]").forEach((button) => {
      const active = button.dataset.lang === lang;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    localStorage.setItem("aomera-language", lang);
    renderCurrentUser();
    renderFilteredInterviews();
    window.dispatchEvent(new CustomEvent("aomera-language-change", { detail: lang }));
  }

  async function loadCurrentUser() {
    try {
      const response = await window.AIInterview.requestJson("/me");
      currentUser = response.data.user;
      renderCurrentUser();
      window.dispatchEvent(new CustomEvent("aomera-user-ready", { detail: currentUser }));
    } catch (error) {
      if (error.status === 401) {
        window.location.replace(`login.html?lang=${encodeURIComponent(lang)}`);
        return;
      }
      companyName.textContent = "—";
      displayName.textContent = "—";
      greetingName.textContent = "";
      console.error("Failed to load the signed-in user.", error);
    }
  }

  function closeSidebar() { sidebar.classList.remove("open"); scrim.classList.remove("open"); }
  function showToast() {
    window.clearTimeout(toastTimer);
    toast.textContent = copy[lang].demoAction;
    toast.classList.add("show");
    toastTimer = window.setTimeout(() => toast.classList.remove("show"), 2400);
  }

  document.querySelector("#menuButton").addEventListener("click", () => { sidebar.classList.add("open"); scrim.classList.add("open"); });
  document.querySelector("#sidebarClose").addEventListener("click", closeSidebar);
  scrim.addEventListener("click", closeSidebar);
  profileButton.addEventListener("click", () => {
    const open = profileMenu.classList.toggle("open");
    profileButton.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (event) => {
    if (!profileButton.contains(event.target) && !profileMenu.contains(event.target)) {
      profileMenu.classList.remove("open");
      profileButton.setAttribute("aria-expanded", "false");
    }
  });
  document.querySelectorAll("[data-lang]").forEach((button) => button.addEventListener("click", () => applyLanguage(button.dataset.lang)));
  document.querySelectorAll("#notificationButton").forEach((button) => button.addEventListener("click", showToast));

  const now = new Date();
  document.querySelector("#today").textContent = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}`;
  applyLanguage(lang);
  loadCurrentUser();
})();
