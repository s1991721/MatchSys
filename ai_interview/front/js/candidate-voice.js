(() => {
  const base=(window.AI_INTERVIEW_API_BASE||(['localhost','127.0.0.1'].includes(location.hostname)?`${location.protocol}//${location.hostname}:8001/api`:'/ai_interview/api')).replace(/\/$/,'');
  const el=id=>document.getElementById(id);
  const set=(id,text)=>window.AIInterviewI18n.set(el(id),text);
  let stage=null,player=null,recording=null,peer=null,channel=null,prepared=false,ready=false,finishing=false,failed=false,expectedClose=false;
  let deadline=null,offset=0,timer=null,ping=null,connectTimer=null,finishTimer=null,stopPromise=null,muted=false,run=0;
  let reportConfig=null,activeResponse=null,reportResponse=null,reportAttempts=0,reportRequested=false,reportSaved=false;
  let stopAcknowledged=false,speechActive=false,commitPending=false,heartbeatBusy=false;
  let reportItems=new Map();
  function buttons(){el('muteMicrophone').disabled=!ready||finishing;el('endPreview').disabled=!ready||finishing;}
  function playbackStatus(){if(ready&&!finishing)set('interviewerStatus',player?.speaking()?'面试官正在说话，可以直接开口打断。':muted?'麦克风已静音':'正在聆听，你可以直接回答。');}
  function send(value){if(channel?.readyState==='open')channel.send(JSON.stringify(value));}
  async function request(action,extra={},owner=window.CandidateFlow.identity()){
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch(base+'/candidate/'+action,{method:'POST',credentials:'omit',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({...owner,...extra}),signal:controller.signal});
      const result=await response.json();
      if(!response.ok||!result.success){const error=new Error(result.error?.message||'面试服务连接失败。');error.status=response.status;error.code=result.error?.code;throw error;}
      return result.data;
    }finally{clearTimeout(timeout);}
  }
  function closeTransport(){
    clearTimeout(connectTimer);clearTimeout(finishTimer);clearInterval(ping);clearInterval(timer);
    ready=false;expectedClose=true;
    if(channel){channel.onopen=channel.onmessage=channel.onclose=channel.onerror=null;channel.close();channel=null;}
    if(peer){peer.ontrack=peer.onconnectionstatechange=null;peer.close();peer=null;}buttons();
  }
  function dispose(){run++;closeTransport();recording?.close();recording=null;player?.close();player=null;prepared=false;}
  async function abort(reason){try{await fetch(base+'/candidate/abort',{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json'},body:JSON.stringify({...window.CandidateFlow.identity(),reason}),keepalive:true});}catch{}}
  function fail(message='本次面试已异常中断，请联系邀请方重新安排。',reason='connection_lost',code=reason){
    if(failed||['entry','prepare','complete','abnormal'].includes(stage))return;
    failed=true;el('voiceHelp').hidden=false;set('voiceHelp',message);closeTransport();
    const failedPlayer=player;recording?.stop(false).catch(()=>{}).finally(()=>failedPlayer?.close());
    abort(reason).finally(()=>window.CandidateFlow.verify());window.CandidateFlow.interrupted(message,reason,code);
  }
  async function prepare(){
    dispose();el('enableInterviewerAudio').hidden=true;el('enableInterviewerAudio').disabled=false;failed=false;finishing=false;stopPromise=null;expectedClose=false;muted=false;heartbeatBusy=false;
    reportConfig=null;activeResponse=reportResponse=null;reportAttempts=0;reportRequested=reportSaved=false;
    stopAcknowledged=speechActive=commitPending=false;
    reportItems=new Map();
    set('microphoneLabel','静音麦克风');el('muteMicrophone').setAttribute('aria-pressed','false');
    const generation=run,owner=window.CandidateFlow.identity();
    const currentFail=(...args)=>{if(generation===run)fail(...args);};
    player=new window.CandidateLiveAudio(playbackStatus,message=>currentFail(message,'recording_failed'),blocked=>{
      if(generation!==run)return;el('enableInterviewerAudio').hidden=!blocked||finishing;el('enableInterviewerAudio').disabled=finishing;
      el('voiceHelp').hidden=!blocked;
      if(blocked)set('voiceHelp','浏览器未允许播放声音，请点击“播放面试官声音”。');
    });
    try{
      if(!await player.init())throw new Error('请点击开始面试以启用麦克风和声音。');
      recording=new window.CandidateRecording(player,base,()=>({...owner}),currentFail,text=>{if(generation===run){set('recordingStatus',text==='正在录制音视频'?'录制中':text==='正在保存完整录制'?'保存中':text);el('recordingStatus').setAttribute('data-recording',text==='正在录制音视频'?'active':'idle');}});
      await recording.prepare();prepared=true;
    }catch(error){dispose();throw error;}
  }
  function tick(){
    if(!deadline)return;const seconds=Math.max(0,Math.ceil((deadline-Date.now()-offset)/1000));
    el('sessionDuration').textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
    if(!seconds&&ready&&!finishing)end();
  }
  function terminal(data){
    if(data.interview.status==='abnormal'){fail();return true;}
    if(data.interview.status==='completed'){closeTransport();window.CandidateFlow.verify();return true;}return false;
  }
  async function heartbeat(generation,owner){
    if(heartbeatBusy||expectedClose||generation!==run)return;heartbeatBusy=true;
    try{const data=await request('heartbeat',{},owner);if(generation!==run)return;if(!terminal(data)&&data.interview.status==='submitting'&&!finishing)end();}
    catch(error){if(generation===run)fail(error.message);}finally{if(generation===run)heartbeatBusy=false;}
  }
  function stopAndSeal(){
    if(stopPromise)return stopPromise;
    const generation=run,activeRecording=recording;
    stopPromise=activeRecording.stop(true).then(data=>{
      if(generation!==run)return;set('recordingStatus','音视频已保存');if(data)terminal(data);
    }).catch(()=>{if(generation===run)fail('音视频上传失败，面试已异常中断。','upload_failed');});
    return stopPromise;
  }
  function requestReport(){
    if(!finishing||failed||!stopAcknowledged||activeResponse||commitPending||reportRequested||reportSaved)return;
    reportRequested=true;reportAttempts++;reportItems.clear();send({type:'response.create',response:reportConfig});
  }
  async function provider(data,generation,owner){
    if(generation!==run||failed)return;
    const kind=data.type;
    if(kind==='error'){
      const code=data.error?.code;
      if(code==='response_cancel_not_active')return;
      if(code==='input_audio_buffer_commit_empty'){commitPending=false;requestReport();return;}
      fail(data.error?.message||'AI 面试服务中断，请联系邀请方。','provider_failed',code||'provider_failed');return;
    }
    if(kind==='session.updated'&&finishing){stopAcknowledged=true;requestReport();}
    else if(kind==='response.created'){
      activeResponse=data.response.id;
      if(data.response.metadata?.stage==='final_evaluation')reportResponse=activeResponse;
      else if(finishing)send({type:'response.cancel',response_id:activeResponse});
    }else if(kind==='response.output_item.done'&&data.response_id===reportResponse){
      if(data.item?.type==='function_call')reportItems.set(data.item.id,data.item);
    }else if(kind==='response.function_call_arguments.done'&&data.response_id===reportResponse){
      const item=reportItems.get(data.item_id)||{};
      reportItems.set(data.item_id,{...item,id:data.item_id,type:'function_call',name:data.name||item.name,arguments:data.arguments});
    }else if(kind==='input_audio_buffer.speech_started'){
      speechActive=true;if(!finishing)player.setSpeaking(false);
    }else if(kind==='input_audio_buffer.speech_stopped'){
      speechActive=false;if(!finishing)set('interviewerStatus','正在思考下一问…');
    }else if(kind==='input_audio_buffer.committed'){speechActive=false;commitPending=false;requestReport();}
    else if(kind==='output_audio_buffer.started'&&!finishing)player.setSpeaking(true);
    else if(['output_audio_buffer.stopped','output_audio_buffer.cleared'].includes(kind))player.setSpeaking(false);
    else if(kind==='response.done'){
      const response=data.response;if(activeResponse===response.id)activeResponse=null;
      if(response.id===reportResponse&&!reportSaved){
        try{
          const output=response.output||[];
          const finalCalls=output.filter(row=>row.type==='function_call');
          const calls=(finalCalls.length?finalCalls:[...reportItems.values()]).filter(row=>row.name==='submit_interview_report');
          if(response.status!=='completed'||calls.length!==1){const error=new Error(`最终评价未完成（${response.status||'unknown'}，${response.status_details?.error?.message||response.status_details?.reason||'评价工具调用数量：'+calls.length+'；输出类型：'+(output.map(row=>row.type).join(', ')||'empty')}）。`);error.code=response.status_details?.error?.code||response.status_details?.reason||'invalid_evaluation_response';throw error;}
          const evaluation=JSON.parse(calls[0].arguments);
          let result;
          try{result=await request('evaluation',{evaluation},owner);}
          catch(error){
            // 上传响应丢失时重试同一评价，不重新生成不同评分。
            if(error.code==='ai_invalid_output'||(error.status&&error.status<500))throw error;
            if(generation!==run)return;
            result=await request('evaluation',{evaluation},owner);
          }
          if(generation!==run)return;reportSaved=true;set('evaluationStatus','评价已提交，正在确认音视频保存…');terminal(result);
        }catch(error){
          if(generation!==run)return;
          if(reportAttempts<2&&(!error.status||error.status===400||error.code==='ai_invalid_output')){reportRequested=false;reportResponse=null;requestReport();}
          else fail(error.message||'本次面试评价未能完成。','evaluation_failed',error.code||(error.status?`http_${error.status}`:error.name));
        }
      }else if(response.status==='failed'){fail('AI 面试服务中断。','provider_failed');}
      requestReport();
    }
    // 不显示、记录或上传模型返回的逐句对话文本。
  }
  async function connect(){
    if(!prepared||peer||failed){fail();return;}
    const generation=run,owner=window.CandidateFlow.identity();expectedClose=false;
    set('interviewerStatus','正在连接…');buttons();
    connectTimer=setTimeout(()=>{if(generation===run&&!ready)fail('AI 连接超时，面试已异常中断。','provider_failed');},30000);
    try{
      const data=await request('client-secret',{},owner);if(generation!==run)return;
      reportConfig=data.evaluation_response;deadline=Date.parse(data.interview.deadline_at);offset=Date.parse(data.interview.server_time)-Date.now();
      // 心跳独立于音频连接，覆盖 SDP 协商和最终上传阶段。
      ping=setInterval(()=>heartbeat(generation,owner),5000);
      const currentPeer=peer=new RTCPeerConnection();
      currentPeer.ontrack=event=>{if(generation===run)player.attachRemote(event.streams[0]||new MediaStream([event.track]));};
      player.microphoneStream().getTracks().forEach(track=>currentPeer.addTrack(track,player.microphoneStream()));
      currentPeer.onconnectionstatechange=()=>{if(generation===run&&!expectedClose&&['failed','disconnected','closed'].includes(currentPeer.connectionState))fail();};
      const currentChannel=channel=currentPeer.createDataChannel('oai-events');
      currentChannel.onopen=()=>{
        if(generation!==run)return;clearTimeout(connectTimer);ready=true;recording.start();player.enable(true);
        timer=setInterval(tick,1000);tick();el('voiceHelp').hidden=true;playbackStatus();buttons();
        send({type:'response.create'});
      };
      currentChannel.onmessage=event=>{try{provider(JSON.parse(event.data),generation,owner).catch(()=>{if(generation===run)fail();});}catch{if(generation===run)fail();}};
      currentChannel.onerror=currentChannel.onclose=()=>{if(generation===run&&!expectedClose)fail();};
      const offer=await currentPeer.createOffer();await currentPeer.setLocalDescription(offer);
      const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
      try{
        const response=await fetch('https://api.openai.com/v1/realtime/calls',{method:'POST',headers:{Authorization:'Bearer '+data.client_secret.value,'Content-Type':'application/sdp'},body:offer.sdp,signal:controller.signal});
        if(!response.ok)throw new Error('无法建立 AI 语音连接。');
        const sdp=await response.text();if(generation!==run)return;await currentPeer.setRemoteDescription({type:'answer',sdp});
      }finally{clearTimeout(timeout);}
    }catch(error){if(generation===run)fail(error.message,'provider_failed');}
  }
  async function end(){
    if(!ready||finishing||failed)return;
    const generation=run,owner=window.CandidateFlow.identity();finishing=true;buttons();player.enable(false);
    set('evaluationStatus','AI 正在本次语音会话中生成评价…');
    finishTimer=setTimeout(()=>{if(generation===run&&!expectedClose)fail('评价或录制保存超时。','finish_timeout');},110000);
    try{
      const data=await request('finish',{},owner);if(generation!==run||terminal(data))return;
      await window.CandidateFlow.verify();if(generation!==run)return;
      // 等服务端确认停止自动轮次，并等待取消中的回答结束，再生成最终评价。
      send({type:'session.update',session:{type:'realtime',audio:{input:{turn_detection:null}},
        tools:reportConfig.tools,tool_choice:reportConfig.tool_choice,instructions:reportConfig.instructions,
        output_modalities:reportConfig.output_modalities,max_output_tokens:reportConfig.max_output_tokens}});
      if(activeResponse)send({type:'response.cancel',response_id:activeResponse});
      // 主动结束时立即静音本地播放。response.cancel 已负责停止当前回答，
      // 不再无条件清空服务端音频缓冲区：没有正在播放的音频时该命令会报错，
      // 被通用 error 处理误判为面试异常。
      player.silence();
      if(speechActive){commitPending=true;send({type:'input_audio_buffer.commit'});}
      stopAndSeal();requestReport();
    }catch(error){if(generation===run)fail(error.message,'evaluation_failed',error.code||(error.status?`http_${error.status}`:error.name));}
  }
  window.CandidateVoice={prepare,cancelPreparation:dispose,end};
  window.addEventListener('candidate-stage',event=>{
    const next=event.detail.stage;if(next===stage)return;stage=next;
    if(next==='session')connect();
    else if(next==='submitting'){if(!peer||failed){fail();return;}if(!finishing)end();}
    else if(['entry','prepare','complete','abnormal'].includes(next))dispose();
  });
  el('enableInterviewerAudio').addEventListener('click',()=>player?.resumePlayback());
  el('muteMicrophone').addEventListener('click',()=>{if(ready&&!finishing){muted=!muted;player.mute(muted);set('microphoneLabel',muted?'开启麦克风':'静音麦克风');el('muteMicrophone').setAttribute('aria-pressed',String(muted));playbackStatus();}});
  window.addEventListener('offline',()=>fail('网络中断，面试已异常结束。'));
  window.addEventListener('pagehide',()=>{
    if(['session','submitting'].includes(stage)&&!expectedClose)navigator.sendBeacon?.(base+'/candidate/abort',new Blob([JSON.stringify({...window.CandidateFlow.identity(),reason:'page_closed'})],{type:'application/json'}));
    dispose();
  });
})();
