(() => {
  const embedded = window.parent !== window;
  let userId = null;
  const bridge = window.AIInterviewFrame = {
    user: null,
    lang: localStorage.getItem('aomera-language') === 'zh-CN' ? 'zh-CN' : 'ja',
    navigate(route, params = {}) {
      if (embedded) window.parent.postMessage({type:'aomera-navigate', route, params}, location.origin);
      else {
        const query = new URLSearchParams(params);
        location.href = `dashboard.html#${encodeURIComponent(route)}${query.size ? `?${query}` : ''}`;
      }
    },
    recordsUpdated() {
      if (embedded) window.parent.postMessage({type: 'aomera-records-updated'}, location.origin);
      window.dispatchEvent(new Event('aomera-data-updated'));
      // storage 只通知其他顶层标签页；当前工作空间已通过 postMessage 通知。
      // 时间戳由父页面写入，避免父页面同时收到消息和 iframe 的 storage 事件。
      if (!embedded) {
        try { localStorage.setItem('aomera-data-updated', String(Date.now())); } catch {}
      }
    }
  };
  function context(lang, user) {
    bridge.lang = lang === 'zh-CN' ? lang : 'ja'; bridge.user = user;
    document.documentElement.lang = bridge.lang;
    window.dispatchEvent(new CustomEvent('aomera-language-change', {detail: bridge.lang}));
    if (user && userId !== user.id) {
      userId = user.id;
      window.dispatchEvent(new CustomEvent('aomera-user-ready', {detail: user}));
    }
  }
  window.addEventListener('message', event => {
    if (!embedded || event.origin !== location.origin || event.source !== window.parent || event.data?.type !== 'aomera-context') return;
    context(event.data.lang, event.data.user);
  });
  let failureNotice = null;
  async function loadUser() {
    try {
      const response = await window.AIInterview.requestJson('/me');
      failureNotice?.remove(); failureNotice = null;
      context(bridge.lang, response.data.user);
    } catch (error) {
      if (error.status === 401) return;
      if (!failureNotice) {failureNotice = document.createElement('div'); failureNotice.className = 'form-error'; failureNotice.setAttribute('role', 'alert'); document.body.prepend(failureNotice);}
      failureNotice.replaceChildren(document.createTextNode(window.AIInterview.errorMessage(error, bridge.lang)));
      const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'outline-action'; retry.textContent = bridge.lang === 'zh-CN' ? '重试' : '再試行'; retry.addEventListener('click', loadUser); failureNotice.append(retry);
    }
  }
  // 等待功能页注册事件监听器，再发送用户与语言上下文。
  window.addEventListener('DOMContentLoaded', () => {
    if (embedded) window.parent.postMessage({type:'aomera-ready'}, location.origin);
    else loadUser();
  });
})();
