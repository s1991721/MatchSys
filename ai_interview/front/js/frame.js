(() => {
  const embedded = window.parent !== window;
  let userId = null;
  const bridge = window.AIInterviewFrame = {
    user: null,
    lang: localStorage.getItem('aomera-language') === 'zh-CN' ? 'zh-CN' : 'ja',
    navigate(route) {
      if (embedded) window.parent.postMessage({type: 'aomera-navigate', route}, location.origin);
      else location.href = `dashboard.html#${encodeURIComponent(route)}`;
    },
    records(id) {
      try {
        const saved = JSON.parse(localStorage.getItem(`aomera-interview-demo:${id}`) || '[]');
        return Array.isArray(saved) ? saved.filter(item => item && typeof item.id === 'string' && typeof item.position === 'string' && typeof item.link === 'string' && item.link.startsWith('https://aomera.example/interview/') && ['ja','zh-CN','en'].includes(item.language) && Number.isFinite(item.duration) && Number.isFinite(Date.parse(item.expiresAt))) : [];
      } catch { return []; }
    },
    recordsUpdated() {
      if (embedded) window.parent.postMessage({type: 'aomera-records-updated'}, location.origin);
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
  // Wait until the page's own scripts have registered their listeners.
  window.addEventListener('DOMContentLoaded', async () => {
    if (embedded) window.parent.postMessage({type:'aomera-ready'}, location.origin);
    else {
      try { const response = await window.AIInterview.requestJson('/me'); context(bridge.lang, response.data.user); }
      catch (error) { if (error.status === 401) location.replace(`login.html?lang=${encodeURIComponent(bridge.lang)}`); }
    }
  });
})();
