const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../../front/js/candidate.js'),'utf8');
let status='waiting',owner=null,requests=[],order=[];
function page(href='http://localhost:63342/candidate.html') {
  const nodes=new Map(),handlers={};let devicesReady=false;
  const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,checked:false,disabled:false,value:'',textContent:'',focus(){},replaceChildren(){},append(){},addEventListener(type,fn){this[type]=fn;}});return nodes.get(id);};
  const parsed=new URL(href),location={href,hostname:parsed.hostname,protocol:parsed.protocol};
  const window={AIInterviewI18n:{set(element,text){element.textContent=text;}},CandidateDevices:{ready:()=>devicesReady},
    CandidateVoice:{async prepare(){order.push('prepare');},cancelPreparation(){},end(){status='submitting';window.CandidateFlow.verify();}},
    addEventListener(type,fn){handlers[type]=fn;},dispatchEvent(){}};
  vm.runInNewContext(source,{window,location,URL,crypto:require('node:crypto').webcrypto,AbortController,setTimeout,clearTimeout,setInterval(){},
    CustomEvent:class{constructor(type,init){this.type=type;this.detail=init.detail;}},history:{replaceState(a,b,url){location.href=String(url);}},
    document:{hidden:false,getElementById:node,querySelectorAll:()=>[],querySelector:()=>node('tags'),createElement:()=>({}),addEventListener(){}},
    fetch:async(url,options)=>{const body=JSON.parse(options.body);requests.push({url,body});
      if(url.endsWith('/start')){order.push('start');owner=body.page_id;status='running';}
      if(['running','submitting'].includes(status)&&owner!==body.page_id)status='abnormal';
      return{ok:true,json:async()=>({success:true,data:{interview:{id:1,status,position_name:'Real',work_description:'Work',duration_minutes:15,skills:[]}}})};}});
  return{node,window,location,handlers,setDevices(value){devicesReady=value;}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  const first=page();assert.equal(requests.length,0);
  first.node('interviewCode').value='ABCD-1234-5678-EF90';first.node('codeForm').submit({preventDefault(){}});await settle();
  assert.equal(first.node('prepare').hidden,false);assert.equal(first.node('startPreview').disabled,true);
  first.node('consent').checked=true;first.node('consent').change();first.node('startPreview').click();await settle();assert.equal(requests.length,1);
  first.setDevices(true);first.handlers['candidate-devices']();await first.node('startPreview').click();await settle();
  assert.deepEqual(order,['prepare','start'],'recording devices must be ready before starting the run');
  assert.equal(first.node('session').hidden,false);assert.equal(requests[0].body.page_id,owner);
  first.node('endPreview').click();await settle();assert.equal(first.node('submitting').hidden,false);
  assert.ok(requests.every(request=>!request.url.endsWith('/evaluate')&&!request.url.endsWith('/submit')),'no secondary evaluation or HTTP finish');
  const refreshed=page(first.location.href);await settle();
  assert.equal(status,'abnormal');assert.equal(refreshed.node('abnormal').hidden,false);
  assert.notEqual(requests.at(-1).body.page_id,owner,'fresh page has a new in-memory identity');
  assert.ok(!first.location.href.includes('page_id'),'page ownership is not put in the URL');
  first.window.CandidateFlow.interrupted('Unknown parameter: response.example','evaluation_failed','unknown_parameter');
  assert.equal(first.node('abnormalMessage').textContent,'Unknown parameter: response.example');
  assert.equal(first.node('abnormalCode').textContent,'unknown_parameter');
  await first.window.CandidateFlow.verify();
  assert.equal(first.node('abnormalMessage').textContent,'Unknown parameter: response.example','verification retains the detailed local error');
  console.log('Candidate frontend passed: preflight recording, ephemeral owner, refresh abnormal, no secondary evaluation.');
})().catch(error=>{console.error(error);process.exitCode=1;});
