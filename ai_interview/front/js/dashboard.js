(() => {
  const copy = window.AIInterviewCopy;
  const sidebar = document.querySelector("#sidebar");
  const scrim = document.querySelector("#sidebarScrim");
  const profileButton = document.querySelector("#profileButton");
  const profileMenu = document.querySelector("#profileMenu");
  const notificationButton = document.querySelector("#notificationButton");
  const notificationPopover = document.querySelector("#notificationPopover");
  const companyMark = document.querySelector("#companyMark");
  const companyName = document.querySelector("#companyName");
  const userAvatar = document.querySelector("#userAvatar");
  const displayName = document.querySelector("#displayName");
  let lang = localStorage.getItem("aomera-language") || "ja";
  let currentUser = null;
  let unreadReportCount = null;
  const monthlyQuota = 30;
  let quotaData = null, quotaError = null, accountError = null, summarySequence = 0;
  let loggingOut = false;
  const reportNoticeCopy = {
    'zh-CN': { unread: '你有未查看的评估报告', empty: '暂无未查看的评估报告' },
    ja: { unread: '未閲覧の評価レポートがあります', empty: '未閲覧の評価レポートはありません' }
  };
  function reportNotice() {
    if (unreadReportCount === null) return lang === 'zh-CN' ? '报告状态尚未加载' : 'レポート状態を取得できていません';
    return reportNoticeCopy[lang][unreadReportCount > 0 ? 'unread' : 'empty'];
  }
  function renderReportNotice() {
    const button = document.querySelector('#notificationButton');
    button.querySelector('i').hidden = !(unreadReportCount > 0);
    button.setAttribute('aria-label', reportNotice());
    notificationPopover.textContent = reportNotice();
  }

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
    renderReportNotice();
    renderQuota(); renderAccountStatus();
    sendContext();
    window.dispatchEvent(new CustomEvent("aomera-language-change", { detail: lang }));
  }

  async function loadCurrentUser() {
    try {
      const response = await window.AIInterview.requestJson("/me");
      currentUser = response.data.user;
      renderCurrentUser();
      sendContext();
      accountError = null; renderAccountStatus();
      loadSummary();
    } catch (error) {
      if (error.status === 401) {
        window.location.replace(`login.html?lang=${encodeURIComponent(lang)}`);
        return;
      }
      companyName.textContent = "—";
      displayName.textContent = "—";

      accountError = error; renderAccountStatus();
    }
  }

  function closeSidebar() { sidebar.classList.remove("open"); scrim.classList.remove("open"); }
  function closeNotification() {
    notificationPopover.hidden = true;
    notificationButton.setAttribute('aria-expanded', 'false');
  }
  function toggleNotification() {
    const open = notificationPopover.hidden;
    notificationPopover.hidden = !open;
    notificationButton.setAttribute('aria-expanded', String(open));
  }

  document.querySelector("#menuButton").addEventListener("click", () => { sidebar.classList.add("open"); scrim.classList.add("open"); });
  document.querySelector("#sidebarClose").addEventListener("click", closeSidebar);
  scrim.addEventListener("click", closeSidebar);
  profileButton.addEventListener("click", () => {
    const open = profileMenu.classList.toggle("open");
    profileButton.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (event) => {
    if (!notificationButton.contains(event.target) && !notificationPopover.contains(event.target)) closeNotification();
    if (!profileButton.contains(event.target) && !profileMenu.contains(event.target)) {
      profileMenu.classList.remove("open");
      profileButton.setAttribute("aria-expanded", "false");
    }
  });
  document.querySelectorAll("[data-lang]").forEach((button) => button.addEventListener("click", () => applyLanguage(button.dataset.lang)));
  notificationButton.addEventListener('click', toggleNotification);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !notificationPopover.hidden) {
      closeNotification();
      notificationButton.focus();
    }
  });
  window.addEventListener('blur', closeNotification);


  const frame = document.querySelector('#workspaceFrame');
  const routes = { home: 'home', create: 'interview-create', interviews: 'interviews', reports: 'reports', help: 'help', settings: 'settings', plan: 'plan', account: 'account' };
  const titles = {home:'navHome', create:'navInterviews', interviews:'navInterviews', reports:'navReports', help:'navHelp', settings:'navSettings', plan:'planLink', account:'accountSettings'};
  let route, routeHash;
  function sendContext() {
    frame.contentWindow?.postMessage({type:'aomera-context', lang, user:currentUser}, location.origin);
    if (route) { frame.title = copy[lang][titles[route]]; document.title = `${copy[lang].productName} — ${frame.title}`; }
  }
  function setReportCount(value) {
    unreadReportCount = value; renderReportNotice();
    const badge = document.querySelector('.main-nav a[href="#reports"] em');
    badge.textContent = value ?? '—'; badge.hidden = !(value > 0);
  }
  function renderQuota() {
    document.querySelector('#remainingQuota').textContent = `${quotaData?.remaining_count ?? '—'} / ${monthlyQuota}`;
    const progress = document.querySelector('#quotaProgress');
    const remaining = Number(quotaData?.remaining_count);
    progress.hidden = !!quotaError || !quotaData?.configured || !Number.isFinite(remaining);
    const progressValue = Math.max(0, Math.min(monthlyQuota, remaining || 0));
    progress.querySelector('i').style.width = `${progressValue / monthlyQuota * 100}%`;
    progress.setAttribute('aria-valuenow', String(progressValue));
    progress.setAttribute('aria-label', lang === 'zh-CN' ? '本月剩余面试额度' : '今月の残りの面接枠');
    const status = document.querySelector('#quotaStatus'); status.replaceChildren();
    if (quotaError) {
      status.append(document.createTextNode(lang === 'zh-CN' ? '额度加载失败。' : '面接枠を取得できません。'));
      const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'outline-action'; retry.textContent = lang === 'zh-CN' ? '重试' : '再試行'; retry.addEventListener('click', loadSummary); status.append(retry);
    } else if (quotaData && !quotaData.configured) status.textContent = lang === 'zh-CN' ? '请联系管理员配置额度。' : '管理者へ面接枠の設定をご依頼ください。';
    status.hidden = !status.hasChildNodes();
  }
  function renderAccountStatus() {
    const status = document.querySelector('#workspaceStatus'); status.hidden = !accountError; status.replaceChildren();
    if (!accountError) return;
    status.append(document.createTextNode(window.AIInterview.errorMessage(accountError, lang)));
    const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'outline-action'; retry.textContent = lang === 'zh-CN' ? '重试' : '再試行'; retry.addEventListener('click', loadCurrentUser); status.append(retry);
  }
  async function loadSummary() {
    if (!currentUser) return;
    const current = ++summarySequence;
    const [stats, quota] = await Promise.allSettled([window.AIInterview.requestSummary('/dashboard'), window.AIInterview.requestSummary('/quota')]);
    if (current !== summarySequence) return;
    const count = document.querySelector('.main-nav a[href="#interviews"] b');
    if (stats.status === 'fulfilled') {count.textContent = stats.value.data.total_interviews; setReportCount(stats.value.data.unread_reports);}
    else {count.textContent = '—'; setReportCount(null);}
    quotaData = quota.status === 'fulfilled' ? quota.value.data : null;
    quotaError = quota.status === 'rejected' ? quota.reason : null; renderQuota();
  }
  window.addEventListener('storage', event => {if (event.key === 'aomera-data-updated') loadSummary();});
  document.addEventListener('visibilitychange', () => {if (!document.hidden) loadSummary();});
  document.querySelector('#logout').addEventListener('click', async event => {
    event.preventDefault(); if (loggingOut) return; loggingOut = true;
    try {
      await window.AIInterview.requestJson('/logout', {method:'POST'});
      location.replace(`login.html?lang=${encodeURIComponent(lang)}`);
    } catch (error) {window.alert(window.AIInterview.errorMessage(error, lang));}
    finally {loggingOut = false;}
  });
  function navigate() {
    const hash = location.hash.slice(1), [next, rawQuery = ''] = hash.split('?');
    if (!Object.hasOwn(routes, next)) { location.replace('#home'); return; }
    const query = new URLSearchParams();
    if (next === 'reports') {
      const input = new URLSearchParams(rawQuery);
      for (const key of ['report', 'interview']) if (/^[1-9]\d*$/.test(input.get(key) || '')) query.set(key, input.get(key));
    }
    if (routeHash !== hash) {
      route = next; routeHash = hash;
      frame.contentWindow.location.replace(`${routes[route]}.html${query.size ? `?${query}` : ''}`);
    }
    document.querySelectorAll('.sidebar a[href^="#"]').forEach(link => {
      const active = link.hash === `#${route === 'create' ? 'interviews' : route}`;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
    });
    // 路由切换只加载功能页；侧栏统计由首次登录、数据变更和可见性事件刷新。
    closeSidebar(); profileMenu.classList.remove('open'); profileButton.setAttribute('aria-expanded','false'); sendContext();
  }
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
    if (event.data?.type === 'aomera-ready') sendContext();
    if (event.data?.type === 'aomera-navigate' && Object.hasOwn(routes, event.data.route)) {
      const query = new URLSearchParams();
      if (event.data.route === 'reports') for (const key of ['report', 'interview']) {
        const value = String(event.data.params?.[key] || '');
        if (/^[1-9]\d*$/.test(value)) query.set(key, value);
      }
      location.hash = `${event.data.route}${query.size ? `?${query}` : ''}`;
    }
    if (event.data?.type === 'aomera-account-updated') loadCurrentUser();
    if (['aomera-records-updated', 'aomera-reports-updated'].includes(event.data?.type)) {
      try { localStorage.setItem('aomera-data-updated', String(Date.now())); } catch {}
      loadSummary();
    }
  });
  window.addEventListener('hashchange', navigate);
  frame.addEventListener('load', sendContext);
  applyLanguage(lang); navigate(); loadCurrentUser();
})();
