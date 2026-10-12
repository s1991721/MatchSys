(() => {
  let streams = [], context = null, frame = null, generation = 0;
  const checks = {camera:false, microphone:false, network:false};
  function notify() { window.dispatchEvent(new Event('candidate-devices')); }
  window.CandidateDevices = {ready: () => Object.values(checks).every(Boolean), microphone: () => streams.find(stream => stream.getAudioTracks().some(track => track.readyState === 'live')), camera: () => streams.find(stream => stream.getVideoTracks().some(track => track.readyState === 'live'))};
  const button = document.getElementById('checkDevices');
  const help = document.getElementById('deviceHelp');
  const state = (id, value) => { window.AIInterviewI18n.set(document.getElementById(id), value); };
  function stop() {
    generation++;
    checks.camera = checks.microphone = checks.network = false; notify();
    if (frame) cancelAnimationFrame(frame);
    frame = null;
    streams.forEach(stream => stream.getTracks().forEach(track => track.stop()));
    streams = [];
    if (context) context.close().catch(() => {});
    context = null;
    document.querySelectorAll('.device-video').forEach(video => { video.srcObject = null; video.hidden = true; });
    document.querySelectorAll('.camera-placeholder > :not(video)').forEach(item => { item.hidden = false; });
    document.getElementById('microphoneLevel').value = 0;
  }
  function describe(error) {
    return ({NotAllowedError: '未获授权，请在浏览器中允许访问后重试', NotFoundError: '未找到设备', NotReadableError: '设备无法读取，可能被其他应用占用', SecurityError: '浏览器禁止访问设备'})[error.name] || '检测失败，请重试';
  }
  async function check() {
    stop();
    const run = generation;
    button.disabled = true;
    window.AIInterviewI18n.set(button, '正在检查…');
    window.AIInterviewI18n.set(help, '请允许摄像头和麦克风访问，并说一句话观察音量。');
    ['cameraState', 'microphoneState', 'networkState'].forEach(id => state(id, '检测中'));
    const results = await Promise.allSettled([
      (async () => {
        if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('需要 HTTPS 或 localhost 才能访问摄像头');
        const stream = await navigator.mediaDevices.getUserMedia({video:true});
        if (run !== generation) { stream.getTracks().forEach(track => track.stop()); return; }
        streams.push(stream);
        document.querySelectorAll('.device-video').forEach(video => { video.srcObject = stream; video.hidden = false; video.play().catch(() => {}); });
        document.querySelectorAll('.camera-placeholder > :not(video)').forEach(item => { item.hidden = true; });
        stream.getVideoTracks()[0].addEventListener('ended', () => { checks.camera = false; notify(); state('cameraState', '摄像头已断开'); });
        checks.camera = true; notify(); state('cameraState', '已连接');
      })(),
      (async () => {
        if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('需要 HTTPS 或 localhost 才能访问麦克风');
        const stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
        if (run !== generation) { stream.getTracks().forEach(track => track.stop()); return; }
        streams.push(stream);
        context = new (window.AudioContext || window.webkitAudioContext)();
        await context.resume();
        if (run !== generation) return;
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        context.createMediaStreamSource(stream).connect(analyser);
        const data = new Uint8Array(analyser.fftSize);
        function update() {
          if (run !== generation) return;
          analyser.getByteTimeDomainData(data);
          const rms = Math.sqrt(data.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / data.length);
          document.getElementById('microphoneLevel').value = Math.min(1, rms * 4);
          frame = requestAnimationFrame(update);
        }
        update();
        stream.getAudioTracks()[0].addEventListener('ended', () => { checks.microphone = false; notify(); state('microphoneState', '麦克风已断开'); });
        checks.microphone = true; notify(); state('microphoneState', '已连接，请试说话');
      })(),
      (async () => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        try {
          if (!navigator.onLine) throw new Error('网络离线');
          const start = performance.now();
          const response = await fetch(new URL((window.AI_INTERVIEW_API_BASE || (['localhost','127.0.0.1'].includes(location.hostname) ? `${location.protocol}//${location.hostname}:8001/api` : '/ai_interview/api')) + '/candidate/health', location.origin), {method:'HEAD', cache:'no-store', signal:controller.signal});
          if (!response.ok) throw new Error('页面服务器不可达');
          if (run === generation) { checks.network = true; notify(); state('networkState', `可达 · ${Math.round(performance.now() - start)} ms`); }
        } finally { clearTimeout(timeout); }
      })(),
    ]);
    if (run !== generation) return;
    results.forEach((result, index) => {
      if (result.status === 'rejected') state(['cameraState','microphoneState','networkState'][index], result.reason.message?.startsWith('需要 HTTPS') ? result.reason.message : index === 2 ? '连接失败，请检查网络' : describe(result.reason));
    });
    button.disabled = false;
    window.AIInterviewI18n.set(button, '重新检查设备');
    window.AIInterviewI18n.set(help, '请确认画面清晰，讲话时音量条有变化。网络结果仅表示面试服务可达。');
  }
  window.addEventListener('offline', () => { checks.network = false; notify(); state('networkState', '连接失败，请检查网络'); });
  button.addEventListener('click', check);
  window.addEventListener('pagehide', stop);
  new MutationObserver(() => {
    if ((streams.length || context || frame) && !['prepare','session'].some(id => !document.getElementById(id).hidden)) stop();
  }).observe(document.querySelector('main'), {subtree:true, attributes:true, attributeFilter:['hidden']});
})();
