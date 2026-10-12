(() => {
  const copy=window.AIInterviewI18n;
  const local=['localhost','127.0.0.1'].includes(location.hostname);
  const base=(window.AI_INTERVIEW_API_BASE||(local?`${location.protocol}//${location.hostname}:8001/api`:'/ai_interview/api')).replace(/\/$/,'');
  const pageId=crypto.randomUUID(); // Deliberately never persisted: refresh is an abnormal run.
  const stages=['entry','prepare','session','submitting','complete','abnormal'];
  const mapping={waiting:'prepare',running:'session',submitting:'submitting',completed:'complete',abnormal:'abnormal'};
  const errors={invalid_invitation:'面试码或链接无效，请检查后重试。',invitation_expired:'邀请已过期，请联系邀请方。',
    rate_limited:'尝试过于频繁，请稍后重试。',preparation_required:'请完成设备检查并确认准备就绪。',ai_unavailable:'AI 服务尚未配置或暂时不可用，请联系邀请方或稍后重试。'};
  let credential=null,stage='entry',busy=false,generation=0,locallyAbnormal=false,lastInterview=null,verifyQueued=false,interruption=null;
  const abnormalMessages={evaluation_failed:'最终评价生成或提交失败。',provider_failed:'AI 面试服务发生错误。',upload_failed:'音视频上传失败。',recording_failed:'音视频设备或录制失败。',finish_timeout:'评价或录制保存超时。',connection_lost:'面试连接已断开。',connection_timeout:'面试连接超时。',page_closed:'面试页面已关闭。',page_reloaded:'面试页面被刷新或由其他页面打开。',server_shutdown:'面试服务已停止。'};
  const error=document.getElementById('flowError');
  function show(next) {const changed=stage!==next;stage=next;document.body?.classList?.toggle('in-session',next==='session');stages.forEach(id=>{document.getElementById(id).hidden=id!==next;});if(changed&&next!=='session')document.getElementById(next+'Title').focus({preventScroll:true});}
  function ready() {
    document.getElementById('startPreview').disabled=busy||!window.CandidateDevices?.ready()||!document.getElementById('consent').checked;
  }
  function display(item) {
    lastInterview=item;
    document.querySelectorAll('[data-position]').forEach(element=>{element.textContent=item.position_name;});
    document.getElementById('positionDescription').textContent=item.work_description;
    document.querySelectorAll('[data-duration]').forEach(element=>copy.set(element,`${item.duration_minutes} 分钟`));
    document.querySelectorAll('[data-summary]').forEach(element=>copy.set(element,`日语 · ${item.duration_minutes} 分钟`));
    const tags=document.querySelector('.skill-tags');tags.replaceChildren();item.skills.forEach(skill=>{const span=document.createElement('span');span.textContent=skill.name;tags.append(span);});
    const next=locallyAbnormal&&['running','submitting'].includes(item.status)?'abnormal':mapping[item.status];
    if(next==='abnormal'){
      const reason=interruption?.reason||item.abnormal_reason;
      copy.set(document.getElementById('abnormalMessage'),interruption?.message||abnormalMessages[reason]||'本次面试已异常中断，请联系邀请方重新安排。');
      document.getElementById('abnormalCode').textContent=interruption?.code||reason||'unknown';
    }
    if(!next)throw new Error('无法连接面试服务，请稍后重试。');
    if(stage!==next)show(next);
    window.dispatchEvent(new CustomEvent('candidate-stage',{detail:{stage:next,interview:item,credential:{...credential},pageId}}));
  }
  async function request(action,extra={}) {
    const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);
    try {
      const response=await fetch(`${base}/candidate/${action}`,{method:'POST',credentials:'omit',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({...credential,...extra,page_id:pageId}),signal:controller.signal});
      const result=await response.json();if(!response.ok||!result.success)throw new Error(errors[result.error?.code]||'无法连接面试服务，请稍后重试。');
      return result.data.interview;
    } finally {clearTimeout(timeout);}
  }
  // 页面状态请求串行执行，代数校验避免过期响应覆盖当前邀请的界面。
  async function perform(action,extra) {
    if(busy||!credential)return null;
    busy=true;ready();error.hidden=true;const run=generation;
    try {const item=await request(action,extra);if(run===generation)display(item);return item;}
    catch(failure){if(run===generation){copy.set(error,failure.message||'无法连接面试服务，请稍后重试。');error.hidden=false;}return null;}
    finally{busy=false;ready();if(verifyQueued){verifyQueued=false;perform('verify');}}
  }
  function interrupted(message,reason,code) {locallyAbnormal=true;interruption={message,reason,code};if(lastInterview)display({...lastInterview,status:'abnormal'});}
  window.CandidateFlow=Object.freeze({verify:()=>{if(busy){verifyQueued=true;return Promise.resolve(null);}return perform('verify');},identity:()=>({...credential,page_id:pageId}),interrupted});
  async function restore() {
    if(busy)return;
    generation++;
    const url=new URL(location.href);const code=url.searchParams.get('code')||/\/interview\/([^/]+)\/?$/.exec(url.pathname)?.[1];
    credential=code?{code}:null;
    if(credential)await perform('verify');else{show('entry');window.dispatchEvent(new CustomEvent('candidate-stage',{detail:{stage:'entry'}}));}
  }
  document.getElementById('codeForm').addEventListener('submit',event=>{
    event.preventDefault();if(busy)return;const code=document.getElementById('interviewCode').value.trim();if(!code)return;
    locallyAbnormal=false;interruption=null;credential={code};const url=new URL(location.href);url.searchParams.delete('token');url.searchParams.set('code',code);history.replaceState(null,'',url);perform('verify');
  });
  document.getElementById('consent').addEventListener('change',ready);window.addEventListener('candidate-devices',ready);
  document.getElementById('startPreview').addEventListener('click',async()=>{
    if(busy||!window.CandidateDevices?.ready()||!document.getElementById('consent').checked)return;
    // 先申请设备权限并准备录制，再将服务端面试状态置为 running。
    busy=true;ready();
    try{if(window.CandidateVoice)await window.CandidateVoice.prepare();}
    catch(failure){copy.set(error,failure.message||'无法准备音视频设备。');error.hidden=false;busy=false;ready();return;}
    busy=false;
    const result=await perform('start',{devices_ready:true,consent:true});
    if(!result)window.CandidateVoice?.cancelPreparation();
  });
  document.getElementById('endPreview').addEventListener('click',()=>{
    window.CandidateVoice?.end();
  });
  document.querySelectorAll('[data-other-interview]').forEach(button=>button.addEventListener('click',()=>{location.href=new URL('candidate.html',location.href).href;}));
  window.addEventListener('popstate',restore);
  window.addEventListener('pageshow',event=>{if(event.persisted)perform('verify');});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&credential&&!busy)perform('verify');});
  setInterval(()=>{if(!document.hidden&&credential&&stage!=='entry')perform('verify');},30000);
  restore();
})();
