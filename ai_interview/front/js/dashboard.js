(() => {
  const copy = {
    ja: {
      productName: "AI面接官",
      title: "AOMERA AI面接官 — ホーム", navHome: "ホーム", navPositions: "職種管理", navInterviews: "面接管理", navCandidates: "候補者", navReports: "評価レポート", navHelp: "ヘルプ", navSettings: "設定", planLabel: "今月の面接枠", planLink: "プランを確認", workspaceLabel: "ワークスペース", userName: "田中 悠介", userRole: "採用担当者", accountSettings: "アカウント設定", logout: "ログアウト", greeting: "おはようございます、", greetingName: "田中さん。", welcomeCopy: "今日も、候補者の可能性を見つけましょう。", createPosition: "新しい職種を作成", pendingReports: "確認待ちレポート", waitingCandidates: "参加待ち", inProgress: "面接中", monthCompleted: "今月の完了", countUnit: "件", actionNeeded: "対応が必要です", thisWeek: "今週の予定", nowRunning: "現在進行中", lastMonth: "先月比", needsAction: "対応が必要です", viewAll: "すべて見る", positionPm: "プロダクトマネージャー", positionBackend: "バックエンドエンジニア", positionUx: "UXデザイナー", positionSales: "セールスマネージャー", statusReport: "レポート確認待ち", statusWaiting: "参加待ち", statusInterrupted: "面接が中断", reviewReport: "レポートを確認", resend: "再招待する", viewDetails: "詳細を見る", invited: "招待済み", progress: "進捗", todayStatus: "本日の状況", interviewsUnit: "面接", completed: "完了", processing: "進行中", scheduled: "予定", nextInterview: "次の面接", activePositions: "募集中の職種", positionManagement: "職種管理へ", candidates: "候補者", completionRate: "完了率", averageScore: "平均スコア", demoAction: "この操作は次の画面で実装予定です。" },
    "zh-CN": {
      productName: "AI面试官",
      title: "AOMERA AI面试官 — 首页", navHome: "首页", navPositions: "职位管理", navInterviews: "面试管理", navCandidates: "候选人", navReports: "评估报告", navHelp: "帮助", navSettings: "设置", planLabel: "本月面试额度", planLink: "查看套餐", workspaceLabel: "工作空间", userName: "田中悠介", userRole: "招聘负责人", accountSettings: "账户设置", logout: "退出登录", greeting: "早上好，", greetingName: "田中先生。", welcomeCopy: "今天也一起发现候选人的潜力吧。", createPosition: "创建新职位", pendingReports: "待确认报告", waitingCandidates: "等待参加", inProgress: "面试中", monthCompleted: "本月完成", countUnit: "项", actionNeeded: "需要处理", thisWeek: "本周安排", nowRunning: "正在进行", lastMonth: "较上月", needsAction: "需要处理", viewAll: "查看全部", positionPm: "产品经理", positionBackend: "后端工程师", positionUx: "UX设计师", positionSales: "销售经理", statusReport: "报告待确认", statusWaiting: "等待参加", statusInterrupted: "面试已中断", reviewReport: "确认报告", resend: "再次邀请", viewDetails: "查看详情", invited: "已邀请", progress: "进度", todayStatus: "今日状况", interviewsUnit: "场面试", completed: "已完成", processing: "进行中", scheduled: "待开始", nextInterview: "下一场面试", activePositions: "招聘中的职位", positionManagement: "进入职位管理", candidates: "候选人", completionRate: "完成率", averageScore: "平均分", demoAction: "此操作将在后续页面中实现。" }
  };

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
  }

  async function loadCurrentUser() {
    try {
      const response = await window.AIInterview.requestJson("/me");
      currentUser = response.data.user;
      renderCurrentUser();
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
  document.querySelectorAll(".row-action, #createPosition, #notificationButton, .next-interview button, .position-row > button").forEach((button) => button.addEventListener("click", showToast));

  const now = new Date();
  document.querySelector("#today").textContent = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}`;
  applyLanguage(lang);
  loadCurrentUser();
})();
