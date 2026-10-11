(() => {
  const stages = ['entry', 'prepare', 'session', 'submitting', 'complete'];
  // 面试码与链接映射到邀请 ID；进度按邀请隔离，正式状态应由后端返回。
  const invitations = [
    { id: 'demo-a', code: 'K7MP9X2D', token: 'demo-invitation' },
    { id: 'demo-b', code: 'R4NT6W8C', token: 'demo-invitation-b' },
  ];
  let invitation = null;
  let stage = 'entry';
  const storageKey = () => invitation ? `aomera-candidate-demo-v2:${invitation.id}` : null;
  const error = document.getElementById('flowError');

  function readStage() {
    if (!invitation) return 'entry';
    const saved = localStorage.getItem(storageKey());
    return stages.includes(saved) ? saved : 'entry';
  }
  function render() {
    stages.forEach(id => { document.getElementById(id).hidden = id !== stage; });
    document.getElementById(`${stage}Title`).focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'auto' });
  }
  function advance(next) {
    try {
      // 每次操作重新读取，避免其他标签页推进后由旧页面写回。
      if (!invitation) return;
      const current = readStage();
      if (stages.indexOf(current) > stages.indexOf(stage)) {
        stage = current;
        render();
        return;
      }
      if (stages.indexOf(next) !== stages.indexOf(stage) + 1) return;
      localStorage.setItem(storageKey(), next);
      stage = next;
      error.hidden = true;
      render();
    } catch {
      window.AIInterviewI18n.set(error, '无法保存当前阶段，请允许此站点使用浏览器存储后重试。');
      error.hidden = false;
    }
  }
  function restore() {
    const token = new URLSearchParams(location.search).get('token');
    invitation = invitations.find(item => item.token === token) || null;
    const invalidLink = token !== null && !invitation;
    document.getElementById('codeForm').hidden = invalidLink;
    document.getElementById('entryHelp').hidden = invalidLink;
    const notice = document.getElementById('verificationStatus');
    notice.hidden = !invalidLink;
    window.AIInterviewI18n.set(notice, invalidLink ? '此邀请链接无法验证。请确认链接完整或联系邀请方。' : '');
    error.hidden = true;
    try {
      stage = readStage();
      if (invitation && stage === 'entry') {
        localStorage.setItem(storageKey(), 'prepare');
        stage = 'prepare';
      }
    } catch {
      stage = 'entry';
      window.AIInterviewI18n.set(error, '浏览器存储不可用，无法恢复当前阶段。');
      error.hidden = false;
    }
    document.getElementById('consent').checked = false;
    document.getElementById('startPreview').disabled = true;
    document.getElementById('endPreview').disabled = false;
    render();
  }

  document.getElementById('codeForm').addEventListener('submit', event => {
    event.preventDefault();
    const entryError = document.getElementById('entryError');
    const code = document.getElementById('interviewCode').value.toUpperCase().replace(/[\s-]/g, '');
    const matched = invitations.find(item => item.code === code);
    if (!matched) {
      window.AIInterviewI18n.set(entryError, '面试码无效。请检查后重新输入。');
      entryError.hidden = false;
      return;
    }
    entryError.hidden = true;
    // 用 replace 更新当前入口，刷新能恢复邀请，不创建可回退的阶段历史。
    const url = new URL(location.href);
    url.searchParams.set('token', matched.token);
    history.replaceState(null, '', url);
    restore();
  });
  document.getElementById('consent').addEventListener('change', event => {
    document.getElementById('startPreview').disabled = !event.target.checked;
  });
  document.getElementById('startPreview').addEventListener('click', () => {
    if (document.getElementById('consent').checked) advance('session');
  });
  document.getElementById('endPreview').addEventListener('click', () => {
    document.getElementById('endPreview').disabled = true;
    advance('submitting');
    document.getElementById('endPreview').disabled = stage !== 'session';
  });

  window.addEventListener('pageshow', restore);
  window.addEventListener('popstate', restore);
  window.addEventListener('storage', event => {
    if (invitation && (event.key === storageKey() || event.key === null)) restore();
  });
  document.getElementById('otherInterview').addEventListener('click', () => {
    const url = new URL(location.href);
    url.searchParams.delete('token');
    history.replaceState(null, '', url);
    document.getElementById('interviewCode').value = '';
    document.getElementById('entryError').hidden = true;
    restore();
  });
  restore();
})();
