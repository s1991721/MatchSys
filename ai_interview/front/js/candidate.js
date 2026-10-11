(() => {
  const copy = window.AIInterviewI18n;
  const local = ['localhost', '127.0.0.1'].includes(location.hostname);
  const base = (window.AI_INTERVIEW_API_BASE || (local ? `${location.protocol}//${location.hostname}:8001/api` : '/ai_interview/api')).replace(/\/$/, '');
  const stages = ['entry', 'prepare', 'session', 'submitting', 'complete'];
  const mapping = {waiting:'prepare', running:'session', submitting:'submitting', completed:'complete'};
  const messages = {invalid_invitation:'面试码或链接无效，请检查后重试。', invitation_expired:'邀请已过期，请联系邀请方。', interview_abnormal:'面试已中断，请联系邀请方。', rate_limited:'尝试过于频繁，请稍后重试。', preparation_required:'请完成设备检查并确认准备就绪。'};
  let credential = null, stage = 'entry', busy = false, generation = 0, restoreQueued = false;
  const error = document.getElementById('flowError');
  function show(next) {
    stage = next;
    stages.forEach(id => { document.getElementById(id).hidden = id !== next; });
    document.getElementById(`${next}Title`).focus({preventScroll:true});
  }
  function ready() {
    document.getElementById('startPreview').disabled = busy || !window.CandidateDevices?.ready() || !document.getElementById('consent').checked;
  }
  async function request(action, extra = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(`${base}/candidate/${action}`, {method:'POST', credentials:'omit', cache:'no-store', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...credential,...extra}), signal:controller.signal});
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(messages[result.error?.code] || '无法连接面试服务，请稍后重试。');
      return result.data.interview;
    } finally { clearTimeout(timeout); }
  }
  function display(item) {
    document.querySelectorAll('[data-position]').forEach(element => { element.textContent = item.position_name; });
    document.getElementById('positionDescription').textContent = item.work_description;
    document.querySelectorAll('[data-duration]').forEach(element => copy.set(element, `${item.duration_minutes} 分钟`));
    document.querySelectorAll('[data-summary]').forEach(element => copy.set(element, `日语 · ${item.duration_minutes} 分钟`));
    document.getElementById('sessionDuration').textContent = `${String(item.duration_minutes).padStart(2,'0')}:00`;
    const tags = document.querySelector('.skill-tags'); tags.replaceChildren();
    item.skills.forEach(skill => { const span = document.createElement('span'); span.textContent = skill.name; tags.append(span); });
    const next = mapping[item.status];
    if (!next) throw new Error('无法连接面试服务，请稍后重试。');
    show(next);
  }
  async function perform(action, extra) {
    if (busy || !credential) return;
    busy = true; ready();
    const run = generation;
    document.getElementById('verifyCode').disabled = true;
    document.getElementById('endPreview').disabled = true;
    error.hidden = true;
    try { const item = await request(action, extra); if (run === generation) display(item); }
    catch (failure) { if (run === generation) { copy.set(error, messages[ failure.message ] || (Object.values(messages).includes(failure.message) ? failure.message : '无法连接面试服务，请稍后重试。')); error.hidden = false; } }
    finally { busy = false; ready(); document.getElementById('verifyCode').disabled = false; document.getElementById('endPreview').disabled = false; if (restoreQueued) { restoreQueued = false; restore(); } }
  }
  function restore() {
    if (busy) { restoreQueued = true; generation++; return; }
    generation++;
    const url = new URL(location.href);
    const pathCode = /\/interview\/([^/]+)\/?$/.exec(url.pathname)?.[1];
    const code = url.searchParams.get('code') || pathCode;
    credential = code ? {code} : null;
    if (!credential) show('entry');
    else perform('verify');
  }
  document.getElementById('codeForm').addEventListener('submit', event => {
    event.preventDefault();
    const code = document.getElementById('interviewCode').value.trim();
    if (!code || busy) return;
    credential = {code};
    const url = new URL(location.href); url.searchParams.delete('token'); url.searchParams.set('code',code);
    history.replaceState(null,'',url); perform('verify');
  });
  document.getElementById('consent').addEventListener('change',ready);
  window.addEventListener('candidate-devices',ready);
  document.getElementById('startPreview').addEventListener('click', () => { if (window.CandidateDevices?.ready() && document.getElementById('consent').checked) perform('start', {devices_ready:true,consent:true}); });
  document.getElementById('endPreview').addEventListener('click', () => perform('submit'));
  document.getElementById('otherInterview').addEventListener('click', () => { location.href = new URL('candidate.html', location.href).href; });
  document.getElementById('retryCandidate').addEventListener('click', () => perform('verify'));
  window.addEventListener('popstate',restore);
  window.addEventListener('pageshow',event => { if (event.persisted) restore(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && credential && !busy) perform('verify'); });
  setInterval(() => { if (!document.hidden && credential && stage !== 'entry') perform('verify'); },30000);
  restore();
})();
