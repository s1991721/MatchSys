(() => {
  class CandidateRecording {
    constructor(audio,base,identity,failed,progress) {
      // 固定邀请和页面身份，防止迟到上传混入之后打开的另一场面试。
      const owner=identity();
      this.audio=audio;this.base=base;this.identity=()=>({...owner});this.failed=failed;this.progress=progress;
      this.recorder=null;this.camera=null;this.index=0;this.pendingBytes=0;this.queue=Promise.resolve();
      this.error=null;this.stopping=false;this.started=false;this.closed=false;this.stopResolve=null;
    }
    async prepare() {
      if (!window.MediaRecorder) throw new Error('当前浏览器不支持音视频录制，请更换浏览器。');
      const mime=['video/webm;codecs=vp8,opus','video/webm','video/mp4'].find(value=>MediaRecorder.isTypeSupported(value));
      if (!mime) throw new Error('当前浏览器不支持所需录制格式。');
      const shared=window.CandidateDevices?.camera();
      this.camera=shared ? new MediaStream([shared.getVideoTracks()[0].clone()]) : await navigator.mediaDevices.getUserMedia({video:true});
      if (this.closed) { this.camera.getTracks().forEach(track=>track.stop()); return; }
      this.camera.getVideoTracks()[0].addEventListener('ended',()=>{if(!this.closed&&!this.stopping)this.failed('摄像头断开，面试已异常中断。','recording_failed');});
      // 视频来自候选人摄像头；音轨来自包含麦克风与 AI 播放声音的混音流。
      const mixed=this.audio.recordingStream();
      const stream=new MediaStream([...this.camera.getVideoTracks(),...mixed.getAudioTracks()]);
      this.mime=mime.split(';')[0];
      this.recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:650000,audioBitsPerSecond:64000});
      this.recorder.ondataavailable=event=>{if(event.data.size)this.append(event.data);};
      this.recorder.onerror=()=>this.failed('音视频录制失败，面试已异常中断。','recording_failed');
      this.recorder.onstop=()=>this.stopResolve?.();
    }
    start() { this.started=true;this.startedAt=performance.now();this.recorder.start(5000);this.progress('正在录制音视频'); }
    async request(path,body,headers={}) {
      // 分片和封存均为幂等操作；响应丢失时重试同一请求，不改变编号或内容。
      for(let attempt=0;attempt<2;attempt++) {
        const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),20000);
        try {
          const response=await fetch(this.base+'/candidate/recording/'+path,{method:'POST',credentials:'omit',cache:'no-store',body,headers,signal:controller.signal});
          if(!response.ok) {
            const error=new Error('音视频上传失败，面试已异常中断。');error.status=response.status;throw error;
          }
          const result=await response.json();
          if(!result.success){const error=new Error('音视频上传失败，面试已异常中断。');error.status=response.status;throw error;}
          return result.data;
        } catch(error) {
          if(attempt===1||(error.status&&error.status<500))throw error;
        } finally {clearTimeout(timer);}
      }
    }
    append(blob) {
      const index=this.index++;this.pendingBytes+=blob.size;
      if(blob.size>8*1024*1024||index>=256||this.pendingBytes>16*1024*1024) {
        this.error=new Error('录制上传无法跟上，面试已异常中断。');this.failed(this.error.message,'upload_failed');return;
      }
      // 串行上传保留分片顺序，并让 stop 等待所有尾片保存后再封存。
      this.queue=this.queue.then(async()=>{
        if(this.error)return;
        const identity=this.identity();const form=new FormData();
        Object.entries(identity).forEach(([key,value])=>form.append(key,value));
        form.append('index',String(index));form.append('mime',this.mime);form.append('chunk',blob,'recording.part');
        await this.request('chunk',form);this.pendingBytes-=blob.size;this.progress('音视频分片已保存');
      }).catch(error=>{if(!this.error){this.error=error;this.failed('音视频上传失败，面试已异常中断。','upload_failed');}});
    }
    async stop(seal=true) {
      if(this.stopPromise)return this.stopPromise;
      this.stopping=true;this.stoppedAt=performance.now();
      this.stopPromise=(async()=>{
        if(this.recorder?.state!=='inactive'&&this.started) {
          try {
            await new Promise((resolve,reject)=>{
              // 某些浏览器失败后不触发 onstop，超时后仍须释放摄像头。
              const timer=setTimeout(()=>reject(new Error('音视频录制未能正常停止。')),5000);
              this.stopResolve=()=>{clearTimeout(timer);resolve();};
              try {this.recorder.stop();} catch(error) {clearTimeout(timer);reject(error);}
            });
          } catch(error) {this.error=this.error||error;}
          finally {this.stopResolve=null;}
        }
        this.closed=true;this.camera?.getTracks().forEach(track=>track.stop());
        await this.queue;
        if(this.error)throw this.error;
        if(seal&&this.started) {
          this.progress('正在保存完整录制');
          return this.request('seal',JSON.stringify({...this.identity(),count:this.index,
            duration_ms:Math.max(1,Math.round(this.stoppedAt-this.startedAt))}),{'Content-Type':'application/json'});
        }
      })();
      return this.stopPromise;
    }
    close() { this.stop(false).catch(()=>{}); }
  }
  window.CandidateRecording=CandidateRecording;
})();
