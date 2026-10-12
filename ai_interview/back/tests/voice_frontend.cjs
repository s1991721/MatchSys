const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const nodes=new Map(),events={},timers=new Map(),peers=[],players=[],recorders=[];
let seq=0,verify=0,requests=[],status='running',sealResolve,rejectEvaluation=false;
const node=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',disabled:false,setAttribute(){},addEventListener(type,fn){this[type]=fn;}});return nodes.get(id);};
class Channel{constructor(){this.readyState='connecting';this.sent=[];}open(){this.readyState='open';this.onopen?.();}message(data){this.onmessage?.({data:JSON.stringify(data)});}send(value){this.sent.push(JSON.parse(value));}close(){this.readyState='closed';this.onclose?.();}}
class Peer{constructor(){peers.push(this);this.connectionState='new';}addTrack(){}createDataChannel(){return this.channel=new Channel();}async createOffer(){return{sdp:'offer'};}async setLocalDescription(){}async setRemoteDescription(){this.channel.open();}close(){this.closed=true;}}
class Audio{constructor(changed){this.changed=changed;players.push(this);}async init(){return true;}microphoneStream(){return{getTracks:()=>[{}]};}attachRemote(stream){this.remote=stream;}enable(value){this.active=value;}mute(value){this.muted=value;}speaking(){return this.talking;}setSpeaking(value){this.talking=value;this.changed();}silence(){this.silent=true;}close(){this.closed=true;}}
class Recording{constructor(){recorders.push(this);this.stops=[];}async prepare(){}start(){this.started=true;}async stop(seal){this.stops.push(seal);if(seal)return new Promise(resolve=>{sealResolve=resolve;});}close(){this.closed=true;}}
const window={CandidateLiveAudio:Audio,CandidateRecording:Recording,AIInterviewI18n:{set(element,text){element.textContent=text;}},
  CandidateFlow:{identity:()=>({code:'code',page_id:'a'.repeat(32)}),async verify(){verify++;},interrupted(){events['candidate-stage']({detail:{stage:'abnormal'}});}},addEventListener(type,fn){events[type]=fn;}};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../../front/js/candidate-voice.js'),'utf8'),{window,RTCPeerConnection:Peer,AbortController,MediaStream:class{},Blob,location:{hostname:'localhost',protocol:'http:'},
  document:{getElementById:node},navigator:{sendBeacon(){}},setTimeout(fn,ms){timers.set(++seq,{fn,ms});return seq;},clearTimeout(id){timers.delete(id);},setInterval(fn,ms){timers.set(++seq,{fn,ms});return seq;},clearInterval(id){timers.delete(id);},
  fetch:async(url,options)=>{
    requests.push({url,body:url.includes('api.openai.com')?options.body:JSON.parse(options.body),headers:options.headers});
    if(url.includes('api.openai.com'))return{ok:true,text:async()=> 'answer'};
    if(url.endsWith('/evaluation')&&rejectEvaluation){rejectEvaluation=false;return{ok:false,status:502,json:async()=>({success:false,error:{code:'ai_invalid_output',message:'评价目标不完整。'}})};}
    if(url.endsWith('/finish'))status='submitting';
    return{ok:true,json:async()=>({success:true,data:{interview:{status,deadline_at:new Date(Date.now()+60000).toISOString(),server_time:new Date().toISOString()},client_secret:{value:'ek_short'},evaluation_response:{metadata:{stage:'final_evaluation'},tools:[{name:'submit_interview_report'}]}}})};
  }});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function begin(){status='running';events['candidate-stage']({detail:{stage:'prepare'}});await window.CandidateVoice.prepare();events['candidate-stage']({detail:{stage:'session'}});await settle();return peers.at(-1).channel;}
(async()=>{
  const channel=await begin(),player=players.at(-1),recorder=recorders.at(-1);
  assert.equal(recorder.started,true);assert.equal(player.active,true);
  const sdp=requests.find(row=>row.url.includes('api.openai.com'));assert.equal(sdp.headers.Authorization,'Bearer ek_short');
  assert.ok(requests.every(row=>!row.url.includes('/candidate/live')));
  node('muteMicrophone').click();assert.equal(player.muted,true);node('muteMicrophone').click();assert.equal(player.muted,false);
  channel.message({type:'response.created',response:{id:'question'}});
  channel.message({type:'output_audio_buffer.started'});assert.equal(player.talking,true);
  channel.message({type:'input_audio_buffer.speech_started'});assert.equal(player.talking,false,'candidate speech automatically updates interruption state');
  channel.message({type:'response.done',response:{id:'question',status:'cancelled'}});
  channel.message({type:'response.output_audio_transcript.delta',delta:'SECRET_DIALOG'});
  assert.ok([...nodes.values()].every(value=>!value.textContent.includes('SECRET_DIALOG')));
  channel.message({type:'input_audio_buffer.speech_started'});
  channel.message({type:'response.created',response:{id:'last-question'}});
  const abortsBeforeEnd=requests.filter(row=>row.url.endsWith('/abort')).length;
  await window.CandidateVoice.end();events['candidate-stage']({detail:{stage:'submitting'}});
  assert.deepEqual(recorder.stops,[true]);assert.equal(player.active,false);
  assert.equal(player.silent,true);
  assert.ok(channel.sent.some(event=>event.type==='response.cancel'&&event.response_id==='last-question'));
  assert.ok(!channel.sent.some(event=>event.type==='output_audio_buffer.clear'),'manual end must not clear an inactive server audio buffer');
  assert.equal(channel.sent.find(event=>event.type==='session.update').session.tools[0].name,'submit_interview_report');
  channel.message({type:'session.updated'});
  assert.equal(channel.sent.filter(event=>event.type==='response.create').length,1,'wait for final input commit');
  channel.message({type:'input_audio_buffer.committed'});
  channel.message({type:'error',error:{code:'response_cancel_not_active'}});
  channel.message({type:'response.done',response:{id:'last-question',status:'cancelled'}});
  assert.equal(channel.sent.at(-1).response.metadata.stage,'final_evaluation');
  channel.message({type:'response.created',response:{id:'report',metadata:{stage:'final_evaluation'}}});
  const evaluation={summary:'概要',conclusion:'確認',scores:[]};
  channel.message({type:'response.done',response:{id:'report',status:'completed',output:[{type:'function_call',name:'submit_interview_report',arguments:JSON.stringify(evaluation)}]}});
  await settle();
  assert.deepEqual(requests.find(row=>row.url.endsWith('/evaluation')).body.evaluation,evaluation);
  assert.equal(channel.readyState,'open','evaluation alone must not end before media is sealed');
  sealResolve({interview:{status:'completed'}});await settle();assert.equal(channel.readyState,'closed');assert.ok(verify);
  assert.equal(requests.filter(row=>row.url.endsWith('/abort')).length,abortsBeforeEnd,'manual end completes without abnormal abort');
  // A rejected assessment must be regenerated, not uploaded unchanged again.
  const retry=await begin();await window.CandidateVoice.end();retry.message({type:'session.updated'});
  retry.message({type:'response.created',response:{id:'invalid-report',metadata:{stage:'final_evaluation'}}});
  const evaluationsBefore=requests.filter(row=>row.url.endsWith('/evaluation')).length;
  rejectEvaluation=true;
  retry.message({type:'response.done',response:{id:'invalid-report',status:'completed',output:[{type:'function_call',name:'submit_interview_report',arguments:JSON.stringify(evaluation)}]}});
  await settle();
  assert.equal(requests.filter(row=>row.url.endsWith('/evaluation')).length,evaluationsBefore+1,'do not retry an invalid assessment unchanged');
  assert.equal(retry.sent.filter(event=>event.type==='response.create'&&event.response?.metadata?.stage==='final_evaluation').length,2);
  assert.equal(retry.readyState,'open');
  retry.message({type:'response.created',response:{id:'corrected-report',metadata:{stage:'final_evaluation'}}});
  retry.message({type:'response.output_item.done',response_id:'stale-report',item:{id:'stale',type:'function_call',name:'submit_interview_report',arguments:'invalid'}});
  retry.message({type:'response.output_item.done',response_id:'corrected-report',item:{id:'report-item',type:'function_call',name:'submit_interview_report',arguments:JSON.stringify(evaluation)}});
  retry.message({type:'response.function_call_arguments.done',response_id:'corrected-report',item_id:'report-item',name:'submit_interview_report',arguments:JSON.stringify(evaluation)});
  retry.message({type:'response.done',response:{id:'corrected-report',status:'completed',output:[]}});
  await settle();sealResolve({interview:{status:'completed'}});await settle();
  assert.equal(retry.readyState,'closed');
  assert.equal(requests.filter(row=>row.url.endsWith('/evaluation')).length,evaluationsBefore+2,'read completed tool events when response.done has no output');
  assert.equal(requests.filter(row=>row.url.endsWith('/abort')).length,abortsBeforeEnd);
  events['candidate-stage']({detail:{stage:'complete'}});
  const next=await begin(),count=peers.length;events.offline();await settle();
  assert.equal(peers.length,count,'never reconnect failed interview');assert.equal(next.readyState,'closed');
  assert.ok(requests.some(row=>row.url.endsWith('/abort')));
  assert.ok(recorders.at(-1).stops.includes(false));
  // A delayed seal from an old interview cannot close the next interview.
  const old=await begin();await window.CandidateVoice.end();const oldSeal=sealResolve;
  const fresh=await begin();oldSeal({interview:{status:'completed'}});await settle();
  assert.equal(fresh.readyState,'open');assert.equal(old.readyState,'closed');
  events.pagehide();assert.equal(timers.size,0);
  console.log('WebRTC frontend passed: direct credentials, same-session evaluation, mixed recording finalization, no transcript upload, no reconnect and stale completion isolation.');
})().catch(error=>{console.error(error);process.exitCode=1;});
