const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
function element(tag) {
  return {tagName:tag.toUpperCase(),children:[],handlers:{},attributes:{},paused:true,currentTime:0,duration:Infinity,playbackRate:1,
    append(...items){this.children.push(...items);},setAttribute(key,value){this.attributes[key]=value;},addEventListener(event, handler){this.handlers[event]=handler;},
    pause(){this.paused=true;this.handlers.pause?.();},async play(){this.paused=false;this.handlers.play?.();}};
}
const window={}, document={createElement:element,querySelectorAll:()=>[]};
vm.runInNewContext(fs.readFileSync(require('node:path').resolve(__dirname,'../../front/js/report-player.js'),'utf8'),{window,document});
const player=element('video'), wrapper=window.createReportPlayer(player,54000,true);
const [play,progress,clock,label,mute]=wrapper.children[1].children;
assert.equal(progress.max,'54');assert.equal(clock.textContent,'0:00 / 0:54');
player.currentTime=10;player.handlers.timeupdate();assert.equal(progress.value,'10');assert.equal(clock.textContent,'0:10 / 0:54');
progress.value='27';progress.handlers.input();assert.equal(player.currentTime,27);
const rate=label.children[0];rate.value='2';rate.handlers.change();assert.equal(player.playbackRate,2);
player.playbackRate=1.5;player.handlers.ratechange();assert.equal(rate.value,'1.5');
mute.handlers.click();assert.equal(player.muted,true);
const audio=element('audio');audio.duration=42;
const fallback=window.createReportPlayer(audio,null,false);assert.equal(fallback.children[1].children[1].max,'42');
assert.ok(play.innerHTML.includes('<svg'));assert.equal(play.attributes['aria-label'],'播放');
assert.equal(mute.attributes['aria-label'],'取消静音');
(async () => {
  const fullscreen=wrapper.children[1].children[5];
  wrapper.requestFullscreen=async()=>{document.fullscreenElement=wrapper;wrapper.handlers.fullscreenchange();};
  document.exitFullscreen=async()=>{document.fullscreenElement=null;wrapper.handlers.fullscreenchange();};
  await fullscreen.handlers.click();assert.equal(document.fullscreenElement,wrapper);
  assert.equal(fullscreen.attributes['aria-label'],'退出全屏');
  await fullscreen.handlers.click();assert.equal(document.fullscreenElement,null);
  assert.equal(fullscreen.attributes['aria-label'],'全屏');
  await fullscreen.handlers.click();await document.exitFullscreen();
  assert.equal(fullscreen.attributes['aria-pressed'],'false','Escape/external exit updates the icon');
  console.log('Report player passed: duration, seeking, speed, icons, fullscreen toggle and external exit.');
})().catch(error=>{console.error(error);process.exitCode=1;});
