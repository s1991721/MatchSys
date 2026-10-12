(() => {
  const $ = selector => document.querySelector(selector);
  const copies = {
    'zh-CN': {title:'账户设置', intro:'查看所属工作空间，管理您的显示名和登录密码。', workspace:'工作空间', workspaceCode:'工作空间编号', username:'登录账号', profile:'显示名', displayName:'账号显示名', saveName:'保存显示名', password:'修改密码', currentPassword:'当前密码', newPassword:'新密码', confirmPassword:'确认新密码', passwordHint:'新密码需为8–128个字符，且不能与当前密码相同。', savePassword:'更新密码', saving:'正在保存…', saved:'显示名已更新。', passwordSaved:'密码已更新，下次登录请使用新密码。', loadError:'账号信息加载失败，请刷新页面重试。', authentication_required:'登录状态已失效，请重新登录。', invalid_display_name:'显示名需为1至100个字符。', incorrect_password:'当前密码错误。', invalid_password:'新密码需为8至128个字符。', password_mismatch:'两次新密码不一致。', password_unchanged:'新密码不能与当前密码相同。', failed:'保存失败，请稍后重试。'},
    ja: {title:'アカウント設定', intro:'所属ワークスペースを確認し、表示名とログインパスワードを管理します。', workspace:'ワークスペース', workspaceCode:'ワークスペース番号', username:'ログインアカウント', profile:'表示名', displayName:'アカウント表示名', saveName:'表示名を保存', password:'パスワード変更', currentPassword:'現在のパスワード', newPassword:'新しいパスワード', confirmPassword:'新しいパスワード（確認）', passwordHint:'8〜128文字で、現在のパスワードと異なるものを設定してください。', savePassword:'パスワードを更新', saving:'保存中…', saved:'表示名を更新しました。', passwordSaved:'パスワードを更新しました。次回ログイン時は新しいパスワードをご利用ください。', loadError:'アカウント情報を取得できませんでした。ページを再読み込みしてください。', authentication_required:'ログインの有効期限が切れました。再度ログインしてください。', invalid_display_name:'表示名は1〜100文字で入力してください。', incorrect_password:'現在のパスワードが正しくありません。', invalid_password:'新しいパスワードは8〜128文字で入力してください。', password_mismatch:'新しいパスワードが一致しません。', password_unchanged:'現在と異なるパスワードを設定してください。', failed:'保存できませんでした。しばらくしてから再度お試しください。'}
  };
  const busy = new Set();
  const statuses = new Map();
  const copy = () => copies[window.AIInterviewFrame.lang] || copies.ja;
  function status(selector, key, error = false) {
    statuses.set(selector, key);
    $(selector).textContent = copy()[key] || copy().failed;
    $(selector).classList.toggle('form-error', error);
  }
  function renderLanguage() {
    document.title = `AOMERA — ${copy().title}`;
    document.querySelectorAll('[data-account-copy]').forEach(el => { el.textContent = copy()[el.dataset.accountCopy]; });
    statuses.forEach((key, selector) => { $(selector).textContent = copy()[key] || copy().failed; });
    busy.forEach(form => { form.querySelector('button').textContent = copy().saving; });
  }
  function renderUser(user, updateInput = true) {
    $('#accountWorkspace').textContent = user.company_name || '—';
    $('#accountWorkspaceCode').textContent = user.company_code || '—';
    $('#accountUsername').textContent = user.user_name || '—';
    if (updateInput) $('#accountDisplayName').value = user.display_name || user.user_name || '';
  }
  async function submit(event, action) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!window.AIInterviewFrame.user || busy.has(form)) return;
    const target = action === 'display_name' ? '#profileStatus' : '#passwordStatus';
    const data = Object.fromEntries(new FormData(form));
    if (action === 'display_name') {
      data.display_name = data.display_name.trim();
      if (!data.display_name || Array.from(data.display_name).length > 100) return status(target, 'invalid_display_name', true);
    } else {
      if (data.new_password !== data.confirm_password) return status(target, 'password_mismatch', true);
      if (data.new_password === data.current_password) return status(target, 'password_unchanged', true);
    }
    const button = form.querySelector('button'); busy.add(form); button.disabled = true; button.textContent = copy().saving; status(target, 'saving');
    try {
      const response = await window.AIInterview.requestJson('/account', {method:'POST', body:JSON.stringify({action, ...data})});
      window.AIInterviewFrame.user = response.data.user;
      renderUser(response.data.user, action === 'display_name');
      if (action === 'password') form.reset();
      status(target, action === 'password' ? 'passwordSaved' : 'saved');
      if (window.parent !== window) window.parent.postMessage({type:'aomera-account-updated'}, location.origin);
    } catch (error) { status(target, error.code || (error.status === 401 ? 'authentication_required' : 'failed'), true); }
    finally { busy.delete(form); button.disabled = false; renderLanguage(); }
  }
  $('#profileForm').addEventListener('submit', event => submit(event, 'display_name'));
  $('#passwordForm').addEventListener('submit', event => submit(event, 'password'));
  window.addEventListener('aomera-language-change', renderLanguage);
  // 身份由 frame 统一加载；CSRF 由请求层获取，账户页不再重复调用 /me。
  window.addEventListener('aomera-user-ready', event => {
    renderUser(event.detail);
    document.querySelectorAll('.account-form button').forEach(button => { button.disabled = false; });
  });
  renderLanguage();
})();
