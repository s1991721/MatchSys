(() => {
  class CandidateLiveAudio {
    constructor(changed, failed, playbackBlocked=()=>{}) {
      this.changed=changed;this.failed=failed;this.playbackBlocked=playbackBlocked;this.closed=false;this.active=false;this.muted=false;this.talking=false;
    }
    async init() {
      if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia||!window.RTCPeerConnection)
        throw new Error('实时语音需要 HTTPS 和支持 WebRTC 的浏览器。');
      const AudioContext=window.AudioContext||window.webkitAudioContext;
      this.audio=document.createElement('audio');this.audio.autoplay=true;this.audio.muted=false;this.audio.volume=1;this.audio.hidden=true;this.audio.setAttribute('playsinline','');
      document.body.appendChild(this.audio);
      this.context=new AudioContext();await this.context.resume();
      if(this.context.state!=='running')throw new Error('请点击开始面试以启用声音。');
      const shared=window.CandidateDevices?.microphone();
      this.stream=shared?new MediaStream([shared.getAudioTracks()[0].clone()]):await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if(this.closed){this.stream.getTracks().forEach(track=>track.stop());return false;}
      this.stream.getAudioTracks()[0].enabled=false;
      this.stream.getAudioTracks()[0].addEventListener('ended',()=>{if(!this.closed)this.failed('麦克风断开，面试已异常中断。');});
      this.recordingDestination=this.context.createMediaStreamDestination();
      this.input=this.context.createMediaStreamSource(this.stream);this.input.connect(this.recordingDestination);
      this.drawWave();
      return true;
    }
    microphoneStream(){return this.stream;}
    recordingStream(){return this.recordingDestination.stream;}
    attachRemote(stream){
      if(this.closed)return;
      this.remote?.disconnect();this.output?.disconnect();this.analyser?.disconnect();
      this.remote=this.context.createMediaStreamSource(stream);this.output=this.context.createGain();
      this.remote.connect(this.output);this.output.connect(this.recordingDestination);
      if(this.context.createAnalyser){
        this.analyser=this.context.createAnalyser();this.analyser.fftSize=256;
        this.remote.connect(this.analyser);this.waveSamples=new Uint8Array(this.analyser.frequencyBinCount);
      }
      // Play WebRTC through a media element; Web Audio separately mixes the recording.
      this.audio.srcObject=stream;this.resumePlayback();
    }
    async resumePlayback(){
      if(this.closed)return;
      try{
        this.audio.muted=false;this.audio.volume=1;
        await Promise.all([this.context.resume(),this.audio.play()]);
        if(!this.closed)this.playbackBlocked(false);
      }catch{if(!this.closed)this.playbackBlocked(true);}
    }
    drawWave(){
      window.CandidateOrb?.audio(this);
    }

    enable(active){this.active=active;this.stream?.getAudioTracks().forEach(track=>{track.enabled=active&&!this.muted;});}
    mute(muted){this.muted=muted;this.enable(this.active);}
    speaking(){return this.talking;}
    setSpeaking(value){this.talking=value;this.changed();}
    silence(){if(this.audio)this.audio.muted=true;if(this.output)this.output.gain.value=0;this.setSpeaking(false);}
    close(){
      this.closed=true;window.CandidateOrb?.release(this);if(this.waveFrame)window.cancelAnimationFrame(this.waveFrame);this.analyser?.disconnect();this.audio?.pause();if(this.audio)this.audio.srcObject=null;this.audio?.remove();this.enable(false);this.input?.disconnect();this.remote?.disconnect();this.output?.disconnect();
      this.stream?.getTracks().forEach(track=>track.stop());this.context?.close().catch(()=>{});
    }
  }
  window.CandidateLiveAudio=CandidateLiveAudio;
})();
