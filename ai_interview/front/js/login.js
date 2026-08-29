(() => {
  const translations = {
    ja: {
      title: "AOMERA AI面接官 — ログイン",
      productName: "AI面接官",
      heroTitle: "AIが見抜く。<br />可能性を、確信に変える。",
      heroCopy: "対話から人材の思考と行動を理解し、<br />次の選考につながる評価へ。",
      loginTitle: "ログイン",
      loginCopy: "AOMERA AI面接官へログインしてください。",
      accountLabel: "アカウント",
      accountPlaceholder: "アカウント名を入力",
      passwordLabel: "パスワード",
      passwordPlaceholder: "パスワードを入力",
      showPassword: "表示",
      hidePassword: "隠す",
      showPasswordLabel: "パスワードを表示",
      hidePasswordLabel: "パスワードを隠す",
      submitLabel: "ログインする",
      submittingLabel: "ログイン中…",
      invalidCredentials: "アカウントまたはパスワードが正しくありません。",
      invalidRequest: "入力内容を確認してください。",
      loginFailed: "ログインに失敗しました。しばらくしてからもう一度お試しください。",
      networkError: "サーバーに接続できませんでした。通信環境を確認してください。",
      backLink: "AI面接官の紹介に戻る",
    },
    "zh-CN": {
      title: "AOMERA AI面试官 — 登录",
      productName: "AI面试官",
      heroTitle: "AI洞察。<br />让潜力化为确信。",
      heroCopy: "从对话中理解候选人的思考与行动，<br />形成能够支持下一轮选考的评价。",
      loginTitle: "登录",
      loginCopy: "请登录 AOMERA AI面试官。",
      accountLabel: "账号",
      accountPlaceholder: "请输入账号",
      passwordLabel: "密码",
      passwordPlaceholder: "请输入密码",
      showPassword: "显示",
      hidePassword: "隐藏",
      showPasswordLabel: "显示密码",
      hidePasswordLabel: "隐藏密码",
      submitLabel: "登录",
      submittingLabel: "登录中…",
      invalidCredentials: "账号或密码错误。",
      invalidRequest: "请检查输入内容。",
      loginFailed: "登录失败，请稍后重试。",
      networkError: "无法连接服务器，请检查网络连接。",
      backLink: "返回AI面试官介绍页",
    },
  };

  const languageButtons = [...document.querySelectorAll("[data-lang]")];
  const form = document.querySelector("#loginForm");
  const userName = document.querySelector("#userName");
  const password = document.querySelector("#password");
  const passwordToggle = document.querySelector("#passwordToggle");
  const submitButton = document.querySelector("#submitBtn");
  const submitLabel = submitButton.querySelector(".submit-label");
  const loginError = document.querySelector("#loginError");
  let currentLanguage = "ja";
  let isSubmitting = false;

  function initialLanguage() {
    const queryLanguage = new URLSearchParams(location.search).get("lang");
    if (translations[queryLanguage]) return queryLanguage;
    return "ja";
  }

  function applyLanguage(language) {
    currentLanguage = translations[language] ? language : "ja";
    const copy = translations[currentLanguage];
    document.documentElement.lang = currentLanguage;
    document.title = copy.title;
    document.querySelectorAll("[data-copy]").forEach((element) => {
      const value = copy[element.dataset.copy];
      if (value === undefined) return;
      if (["heroTitle", "heroCopy"].includes(element.dataset.copy)) element.innerHTML = value;
      else element.textContent = value;
    });
    document.querySelectorAll("[data-placeholder]").forEach((element) => {
      element.placeholder = copy[element.dataset.placeholder] || "";
    });
    syncPasswordToggle();
    if (!isSubmitting) submitLabel.textContent = copy.submitLabel;
    languageButtons.forEach((button) => {
      const active = button.dataset.lang === currentLanguage;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function syncPasswordToggle() {
    const copy = translations[currentLanguage];
    const visible = password.type === "text";
    passwordToggle.textContent = visible ? copy.hidePassword : copy.showPassword;
    passwordToggle.setAttribute("aria-label", visible ? copy.hidePasswordLabel : copy.showPasswordLabel);
  }

  function updateSubmitState() {
    submitButton.disabled = isSubmitting || !userName.value.trim() || !password.value;
  }

  function setError(message = "") {
    loginError.textContent = message;
    loginError.hidden = !message;
  }

  function finishSubmitting() {
    isSubmitting = false;
    form.removeAttribute("aria-busy");
    submitButton.classList.remove("loading");
    submitLabel.textContent = translations[currentLanguage].submitLabel;
    updateSubmitState();
  }

  languageButtons.forEach((button) => button.addEventListener("click", () => applyLanguage(button.dataset.lang)));
  [userName, password].forEach((input) => input.addEventListener("input", () => {
    setError();
    updateSubmitState();
  }));
  passwordToggle.addEventListener("click", () => {
    password.type = password.type === "password" ? "text" : "password";
    syncPasswordToggle();
    password.focus({ preventScroll: true });
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitButton.disabled) return;
    setError();
    isSubmitting = true;
    form.setAttribute("aria-busy", "true");
    submitButton.classList.add("loading");
    submitLabel.textContent = translations[currentLanguage].submittingLabel;
    updateSubmitState();

    try {
      await window.AIInterview.requestJson("/login", {
        method: "POST",
        body: JSON.stringify({
          user_name: userName.value.trim(),
          password: password.value,
        }),
      });

      form.dispatchEvent(new CustomEvent("aomera:login-submit", { bubbles: true, detail: { userName: userName.value.trim() } }));
      window.location.href = "dashboard.html";
    } catch (error) {
      const copy = translations[currentLanguage];
      if (error.code === "invalid_credentials") setError(copy.invalidCredentials);
      else if (error.status === 400) setError(copy.invalidRequest);
      else if (error.isNetworkError) setError(copy.networkError);
      else setError(copy.loginFailed);
    } finally {
      finishSubmitting();
    }
  });

  applyLanguage(initialLanguage());
  updateSubmitState();
})();
