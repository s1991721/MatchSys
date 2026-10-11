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
  let unreadReportCount = 0;
  const reportNoticeCopy = {
    'zh-CN': { unread: '你有未查看的评估报告', empty: '暂无未查看的评估报告' },
    ja: { unread: '未閲覧の評価レポートがあります', empty: '未閲覧の評価レポートはありません' }
  };
  function reportNotice() {
    return reportNoticeCopy[lang][unreadReportCount > 0 ? 'unread' : 'empty'];
  }
  function renderReportNotice() {
    const button = document.querySelector('#notificationButton');
    button.querySelector('i').hidden = unreadReportCount === 0;
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
    sendContext();
    window.dispatchEvent(new CustomEvent("aomera-language-change", { detail: lang }));
  }

  async function loadCurrentUser() {
    try {
      const response = await window.AIInterview.requestJson("/me");
      currentUser = response.data.user;
      renderCurrentUser();
      sendContext();
      updateCounts();
      loadReportCount();
    } catch (error) {
      if (error.status === 401) {
        window.location.replace(`login.html?lang=${encodeURIComponent(lang)}`);
        return;
      }
      companyName.textContent = "—";
      displayName.textContent = "—";

      console.error("Failed to load the signed-in user.", error);
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
  let route;
  function sendContext() {
    frame.contentWindow?.postMessage({type:'aomera-context', lang, user:currentUser}, location.origin);
    if (route) { frame.title = copy[lang][titles[route]]; document.title = `${copy[lang].productName} — ${frame.title}`; }
  }
  function updateCounts() {
    let records = [];
    try { records = JSON.parse(localStorage.getItem(`aomera-interview-demo:${currentUser?.id}`) || '[]'); } catch {}
    document.querySelector('.main-nav a[href="#interviews"] b').textContent = Array.isArray(records) ? records.length : 0;
  }
  function setReportCount(value) {
    unreadReportCount = value;
    renderReportNotice();
    const badge = document.querySelector('.main-nav a[href="#reports"] em');
    badge.textContent = value;
    badge.hidden = value === 0;
  }
  function loadReportCount() {
    setReportCount(window.AIInterviewReportDemo.unreadCount(currentUser?.id));
  }
  window.addEventListener('storage', event => {
    if (event.key === null || event.key === window.AIInterviewReportDemo.storageKey(currentUser?.id)) loadReportCount();
  });
  function navigate() {
    const next = location.hash.slice(1);
    if (!Object.hasOwn(routes, next)) { location.replace('#home'); return; }
    if (route !== next) { route = next; frame.contentWindow.location.replace(`${routes[route]}.html`); }
    document.querySelectorAll('.sidebar a[href^="#"]').forEach(link => {
      const active = link.hash === `#${route === 'create' ? 'interviews' : route}`;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
    });
    closeSidebar(); profileMenu.classList.remove('open'); profileButton.setAttribute('aria-expanded','false'); sendContext();
  }
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
    if (event.data?.type === 'aomera-ready') sendContext();
    if (event.data?.type === 'aomera-navigate' && Object.hasOwn(routes, event.data.route)) location.hash = event.data.route;
    if (event.data?.type === 'aomera-account-updated') loadCurrentUser();
    if (event.data?.type === 'aomera-records-updated') updateCounts();
    if (event.data?.type === 'aomera-reports-updated' && Number.isInteger(event.data.unreadCount) && event.data.unreadCount >= 0) setReportCount(event.data.unreadCount);
  });
  window.addEventListener('hashchange', navigate);
  frame.addEventListener('load', sendContext);
  applyLanguage(lang); navigate(); loadReportCount(); loadCurrentUser();
})();
