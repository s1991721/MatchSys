const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../../front/js/candidate.js'), 'utf8');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {hidden:false, checked:false, disabled:false, value:'', textContent:'', focus(){}, replaceChildren(){}, append(){}, addEventListener(type,fn){this[type]=fn;}});
  return nodes.get(id);
};
let devicesReady = false, requests = [], status = 'waiting';
const handlers = {};
const location = {href:'http://localhost:63342/candidate.html',hostname:'localhost',protocol:'http:',get search(){return new URL(this.href).search;}};
const window = {AIInterviewI18n:{set(element,text){element.textContent=text;}},CandidateDevices:{ready:()=>devicesReady},addEventListener(type,fn){handlers[type]=fn;}};
vm.runInNewContext(source, {
  window, location, URL, AbortController, setTimeout, clearTimeout, setInterval(){},
  history:{replaceState(a,b,url){location.href=String(url);}},
  document:{hidden:false,getElementById:node,querySelectorAll:()=>[],querySelector:()=>node('tags'),createElement:()=>({}),addEventListener(){}},
  fetch:async (url, options) => {
    requests.push({url,body:JSON.parse(options.body)});
    if (url.endsWith('/start')) status='running';
    if (url.endsWith('/submit')) status='submitting';
    return {ok:true,json:async()=>({success:true,data:{interview:{id:1,status,position_name:'Real position',work_description:'Real work',duration_minutes:22,skills:[]}}})};
  },
});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  assert.equal(requests.length,0); assert.equal(node('entry').hidden,false);
  node('interviewCode').value='ABCD-1234-5678-EF90';node('codeForm').submit({preventDefault(){}});await settle();
  assert.equal(requests[0].body.code,'ABCD-1234-5678-EF90');
  assert.equal(node('prepare').hidden,false);assert.equal(node('positionDescription').textContent,'Real work');
  assert.equal(node('startPreview').disabled,true);
  node('consent').checked=true;node('consent').change();assert.equal(node('startPreview').disabled,true);
  node('startPreview').click();await settle();assert.equal(requests.length,1);
  devicesReady=true;handlers['candidate-devices']();assert.equal(node('startPreview').disabled,false);
  node('startPreview').click();await settle();assert.equal(node('session').hidden,false);
  assert.equal(requests[1].body.devices_ready,true);assert.equal(requests[1].body.consent,true);
  node('endPreview').click();await settle();assert.equal(node('submitting').hidden,false);
  handlers.popstate();await settle();assert.equal(node('submitting').hidden,false);
  console.log('Frontend passed: real data, credential restoration, readiness gating and server state.');
})().catch(error=>{console.error(error);process.exitCode=1;});
