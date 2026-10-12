(() => {
  const api = window.AIInterview = window.AIInterview || {};
  const localHosts = new Set(['localhost', '127.0.0.1']);
  const normalize = value => String(value || '').trim().replace(/\/+$/, '');
  // 同源 iframe 继承工作空间的接口配置，单独打开页面时也可自行覆盖。
  let inheritedBase;
  try { if (window.parent !== window) inheritedBase = window.parent.AIInterview?.getApiBase(); } catch {}
  const apiBase = normalize(window.AI_INTERVIEW_API_BASE || inheritedBase ||
    (localHosts.has(location.hostname) ? `http://${location.hostname}:8001/api` : '/ai_interview/api'));
  let csrfToken = null, csrfRequest = null, redirecting = false;
  api.getApiBase = () => apiBase;
  api.buildApiUrl = (path = '') => `${apiBase}/${String(path).replace(/^\/+/, '')}`;
  api.loginRequired = () => {
    const owner = summaryOwner();
    if (owner !== api) return owner.loginRequired();
    if (redirecting) return;
    redirecting = true;
    const lang = localStorage.getItem('aomera-language') === 'zh-CN' ? 'zh-CN' : 'ja';
    // 功能页在 iframe 内时退出整个工作空间，避免登录页嵌在内容区。
    const target = window.parent !== window ? window.parent : window;
    target.location.replace(new URL(`login.html?lang=${lang}`, location.href).href);
  };
  async function csrf() {
    const owner = summaryOwner();
    if (owner !== api) return owner.getCsrfToken();
    if (csrfToken) return csrfToken;
    if (!csrfRequest) csrfRequest = api.requestJson('/csrf').then(response => {
      csrfToken = response.data.csrf_token;
      if (!csrfToken) throw new Error('Missing CSRF token');
      return csrfToken;
    }).finally(() => { csrfRequest = null; });
    return csrfRequest;
  }
  // 同源功能页复用父页面的 CSRF token 和进行中的获取请求。
  api.getCsrfToken = csrf;
  api.clearCsrfToken = () => {
    csrfToken = null;
    const owner = summaryOwner();
    if (owner !== api) owner.clearCsrfToken();
  };
  api.requestJson = async (path, options = {}) => {
    const {headers: suppliedHeaders, ...requestOptions} = options;
    const headers = new Headers(suppliedHeaders);
    const method = (requestOptions.method || 'GET').toUpperCase();
    const route = String(path).split('?')[0].replace(/^\/+|\/+$/g, '');
    headers.set('Content-Type', 'application/json');
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && route !== 'login') {
      headers.set('X-CSRFToken', await csrf());
    }
    let response;
    try {
      response = await fetch(api.buildApiUrl(path), {...requestOptions, method, credentials:'include', headers});
    } catch (cause) {
      if (cause.name === 'AbortError') throw cause;
      const error = new Error('Network request failed', {cause});
      error.isNetworkError = true; throw error;
    }
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.success) {
      const error = new Error(payload?.error?.message || `HTTP ${response.status}`);
      Object.assign(error, {status:response.status, code:payload?.error?.code, payload});
      if (response.status === 401 && route !== 'login') api.loginRequired();
      // 不自动重试修改请求，避免创建、扣费或凭证轮换被重复执行。
      if (error.code === 'csrf_failed') api.clearCsrfToken();
      throw error;
    }
    if (payload.data?.csrf_token) csrfToken = payload.data.csrf_token;
    if (route === 'login' || route === 'logout') api.clearCsrfToken();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && route !== 'account') {
      // 报告已读、删除等操作只影响统计，不必重新查询面试额度。
      api.invalidateSummary(route.startsWith('reports/') ? ['/dashboard'] : undefined);
    }
    return payload;
  };
  // 统计和额度由同源工作空间共享：合并并发请求，30 秒内复用成功结果。
  // 列表、详情及修改请求保持原有行为，避免缓存筛选结果或重复执行写入。
  const summaries = new Map();
  function summaryOwner() {
    try {
      const parentApi = window.parent !== window && window.parent.AIInterview;
      if (parentApi?.getApiBase() === apiBase) return parentApi;
    } catch {}
    return api;
  }
  api.invalidateSummary = (paths = ['/dashboard', '/quota']) => {
    const owner = summaryOwner();
    if (owner !== api) return owner.invalidateSummary(paths);
    paths.forEach(path => summaries.delete(path));
  };
  api.requestSummary = path => {
    if (!['/dashboard', '/quota'].includes(path)) throw new Error('Unsupported summary endpoint');
    const owner = summaryOwner();
    if (owner !== api) return owner.requestSummary(path);
    const cached = summaries.get(path);
    if (cached && (cached.pending || Date.now() - cached.loadedAt < 30000)) return cached.promise;
    const entry = {pending:true, loadedAt:0};
    entry.promise = api.requestJson(path).then(response => {
      entry.pending = false; entry.loadedAt = Date.now();
      return response;
    }).catch(error => {
      if (summaries.get(path) === entry) summaries.delete(path);
      throw error;
    });
    summaries.set(path, entry);
    return entry.promise;
  };
  // 跨标签页的数据变更先清除缓存，再由页面的监听器刷新。
  window.addEventListener('storage', event => {
    if (event.key === 'aomera-data-updated' && summaryOwner() === api) api.invalidateSummary();
  });
  api.query = (path, params) => {
    const query = new URLSearchParams(Object.entries(params).filter(([,value]) => value !== '' && value != null));
    return `${path}?${query}`;
  };
  api.errorMessage = (error, lang = 'ja') => {
    const zh = lang === 'zh-CN';
    const messages = {
      quota_exhausted: zh ? '面试额度不足，请联系管理员。' : '面接枠が不足しています。管理者へお問い合わせください。',
      quota_unavailable: zh ? '尚未配置面试额度，请联系管理员。' : '面接枠が設定されていません。管理者へお問い合わせください。',
      duplicate_request: zh ? '此面试已创建，请在面试列表中查看，勿重复创建。' : '作成済みの面接です。面接一覧でご確認ください。',
      csrf_failed: zh ? '安全验证已失效，请再次操作。' : 'セキュリティ確認の有効期限が切れました。再度お試しください。',
      authentication_required: zh ? '登录已失效，请重新登录。' : '再度ログインしてください。',
      not_found: zh ? '记录不存在或已被删除。' : 'データが存在しないか、削除されています。',
      interview_not_editable: zh ? '此邀请已过期或面试已经结束。' : '招待が期限切れ、または面接が終了しています。'
    };
    return messages[error.code] || (error.isNetworkError ?
      (zh ? '无法连接服务器，请检查网络后重试。' : 'サーバーに接続できません。通信環境をご確認ください。') :
      (zh ? '请求失败，请重试。' : '処理に失敗しました。再度お試しください。'));
  };
  const invitationKey = (owner, id) => `aomera-invitation:${owner}:${id}`;
  api.cacheInvitation = (owner, id, url) => {
    try { sessionStorage.setItem(invitationKey(owner, id), url); } catch {}
  };
  api.cachedInvitation = (owner, id) => {
    try { return sessionStorage.getItem(invitationKey(owner, id)); } catch { return null; }
  };
  api.copyInvitation = async (owner, id, lang) => {
    let url = api.cachedInvitation(owner, id);
    if (!url) {
      // 后端不保存原始凭证，重新生成前明确告知旧链接会失效。
      if (!window.confirm(lang === 'zh-CN' ? '重新生成邀请链接后，旧链接将失效。是否继续？' : '招待リンクを再発行すると、以前のリンクは無効になります。続けますか？')) return false;
      const response = await api.requestJson(`/interviews/${id}/invitation`, {method:'POST'});
      url = response.data.invitation_url;
      api.cacheInvitation(owner, id, url);
    }
    try { await navigator.clipboard.writeText(url); }
    catch { window.prompt(lang === 'zh-CN' ? '请复制邀请链接' : '招待リンクをコピーしてください', url); }
    return true;
  };
})();
