const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const destinations=[],track={enabled:true,clone(){return this;},addEventListener(){},stop(){this.stopped=true;}};
const microphone={getAudioTracks:()=>[track]};
function source(){return{connect(target){destinations.push(target);},disconnect(){}};}
class Context{constructor(){this.state='running';this.destination={speaker:true};}async resume(){}createMediaStreamDestination(){return{stream:{mixed:true}};}createMediaStreamSource(stream){destinations.push(stream);return source();}createGain(){return{...source(),gain:{value:1}};}async close(){this.closed=true;}}
class Stream{constructor(tracks){this.tracks=tracks;}getAudioTracks(){return this.tracks;}getTracks(){return this.tracks;}}
let blocked=false,playRejected=false;
const audio={remove(){this.removed=true;},setAttribute(){},async play(){this.plays=(this.plays||0)+1;if(playRejected)throw new Error('NotAllowedError');},pause(){this.paused=true;}};
const window={isSecureContext:true,RTCPeerConnection:class{},AudioContext:Context,CandidateDevices:{microphone:()=>microphone}};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../../front/js/candidate-live-audio.js'),'utf8'),{window,document:{createElement:()=>audio,body:{appendChild(element){assert.equal(element,audio);}}},navigator:{mediaDevices:{getUserMedia(){throw new Error('use checked device');}}},MediaStream:Stream});
(async()=>{
 const player=new window.CandidateLiveAudio(()=>{},()=>{},value=>{blocked=value;});assert.equal(await player.init(),true);assert.equal(track.enabled,false);
 player.enable(true);assert.equal(track.enabled,true);player.mute(true);assert.equal(track.enabled,false);player.mute(false);
 const remote={ai:true};player.attachRemote(remote);
 assert.ok(destinations.includes(remote));assert.ok(destinations.includes(player.recordingDestination),'AI audio enters recording mixer');
 await player.resumePlayback();assert.equal(audio.srcObject,remote);assert.ok(audio.plays>0,'remote audio is played through a media element');
 assert.ok(!destinations.includes(player.context.destination),'avoid duplicate speaker playback');
 playRejected=true;await player.resumePlayback();assert.equal(blocked,true);
 playRejected=false;await player.resumePlayback();assert.equal(blocked,false);
 player.silence();assert.equal(player.output.gain.value,0);assert.equal(audio.muted,true);player.close();assert.equal(track.stopped,true);assert.equal(audio.paused,true);assert.equal(audio.srcObject,null);
 console.log('WebRTC audio passed: checked microphone clone, remote audio mixing, mute and resource release.');
})().catch(error=>{console.error(error);process.exitCode=1;});
