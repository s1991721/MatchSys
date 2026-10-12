const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
let instances=[],requests=[],failUpload=false,failures=[],transientFailures=0,httpStatus=200;
const cameraTrack={kind:'video',stop(){this.stopped=true;},addEventListener(){},clone(){return{kind:'video',stop(){this.stopped=true;},addEventListener(){}};}};
const mixedTrack={kind:'audio'};
class Stream{constructor(tracks){this.tracks=tracks;}getAudioTracks(){return this.tracks.filter(track=>track.kind==='audio');}getVideoTracks(){return this.tracks.filter(track=>track.kind==='video');}getTracks(){return this.tracks;}}
class Recorder{static isTypeSupported(value){return value.startsWith('video/webm');}constructor(stream,options){this.stream=stream;this.options=options;this.state='inactive';instances.push(this);}start(ms){this.state='recording';this.slice=ms;}stop(){this.state='inactive';this.ondataavailable({data:new Blob(['tail'],{type:'video/webm'})});this.onstop();}}
const window={MediaRecorder:Recorder,CandidateDevices:{camera:()=>new Stream([cameraTrack])}};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../../front/js/candidate-recording.js'),'utf8'),{window,MediaRecorder:Recorder,MediaStream:Stream,Blob,FormData,AbortController,performance:require('node:perf_hooks').performance,setTimeout,clearTimeout,
  fetch:async(url,options)=>{requests.push({url,options});if(failUpload||transientFailures-->0)throw new Error('offline');return{ok:httpStatus===200,status:httpStatus,json:async()=>({success:true,data:{interview:{status:'submitting'}}})};}});
(async()=>{
  const recording=new window.CandidateRecording({recordingStream:()=>new Stream([mixedTrack])},'http://localhost/api',()=>({code:'code',page_id:'page'}),(...args)=>failures.push(args),()=>{});
  await recording.prepare();recording.start();assert.equal(instances[0].slice,5000);
  assert.equal(instances[0].stream.getVideoTracks().length,1);assert.equal(instances[0].stream.getAudioTracks()[0],mixedTrack,'record AI + candidate audio mixer output');
  instances[0].ondataavailable({data:new Blob([new Uint8Array([26,69,223,163])],{type:'video/webm'})});
  await recording.stop(true);const chunks=requests.filter(request=>request.url.endsWith('/chunk'));
  assert.equal(chunks.length,2);assert.deepEqual(chunks.map(request=>request.options.body.get('index')),['0','1']);
  const seal=requests.find(request=>request.url.endsWith('/seal'));assert.equal(JSON.parse(seal.options.body).count,2);
  assert.equal(cameraTrack.stopped,undefined,'release cloned camera, not preparation preview');
  assert.ok(instances[0].stream.getVideoTracks()[0].stopped);
  transientFailures=1;
  const retryBody=new FormData();retryBody.append('index','0');
  const beforeRetry=requests.length,priorFailures=failures.length;
  await recording.request('chunk',retryBody);
  assert.equal(requests.length,beforeRetry+2);
  assert.equal(requests.at(-1).options.body,retryBody,'retry keeps original chunk and identity');
  assert.equal(failures.length,priorFailures);
  httpStatus=409;const beforeConflict=requests.length;
  await assert.rejects(()=>recording.request('chunk',retryBody));
  assert.equal(requests.length,beforeConflict+1,'conflicts must not be retried');httpStatus=200;
  failUpload=true;const failed=new window.CandidateRecording({recordingStream:()=>new Stream([mixedTrack])},'http://localhost/api',()=>({code:'code',page_id:'page'}),(...args)=>failures.push(args),()=>{});
  await failed.prepare();failed.start();const prior=requests.filter(request=>request.url.endsWith('/seal')).length;
  await assert.rejects(()=>failed.stop(true));assert.equal(failures.at(-1)[1],'upload_failed');assert.equal(requests.filter(request=>request.url.endsWith('/seal')).length,prior);
  failUpload=false;
  const broken=new window.CandidateRecording({recordingStream:()=>new Stream([mixedTrack])},'http://localhost/api',()=>({code:'code',page_id:'page'}),(...args)=>failures.push(args),()=>{});
  await broken.prepare();broken.start();
  broken.recorder.stop=()=>{throw new Error('recorder unavailable');};
  await assert.rejects(()=>broken.stop(true),/recorder unavailable/);
  assert.ok(broken.camera.getTracks()[0].stopped,'stop exceptions must release camera');
  console.log('Recording frontend passed: candidate video + mixed audio, chunk ordering, final tail, camera cleanup and upload failure.');
})().catch(error=>{console.error(error);process.exitCode=1;});
