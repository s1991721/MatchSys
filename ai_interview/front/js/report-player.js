(() => {
  const icons = {
    play: '<path d="m9 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
    pause: '<path d="M8 5v14M16 5v14" stroke-width="4"/>',
    volume: '<path d="M11 5 6 9H3v6h3l5 4Z"/><path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    muted: '<path d="M11 5 6 9H3v6h3l5 4Z"/><path d="m16 9 6 6m0-6-6 6"/>',
    expand: '<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6"/>',
    collapse: '<path d="M3 9h6V3m12 6h-6V3M9 21v-6H3m12 6v-6h6"/>'
  };
  const icon = (button, name, label) => {
    button.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;
    button.className = 'report-player-icon'; button.title = label; button.setAttribute('aria-label', label);
  };
  const time = seconds => {
    const value = Math.max(0, Math.floor(seconds || 0));
    return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
  };
  window.createReportPlayer = (player, durationMs, chinese) => {
    const make = (tag, text) => {const element = document.createElement(tag); if (text) element.textContent = text; return element;};
    const wrapper = make('div'); wrapper.className = 'report-player';
    const controls = make('div'); controls.className = 'report-player-controls';
    const play = make('button'); play.type = 'button';
    const progress = make('input'); progress.type = 'range'; progress.min = '0'; progress.step = '0.1'; progress.value = '0';
    progress.setAttribute('aria-label', chinese ? '播放进度' : '再生位置');
    const clock = make('span'); clock.className = 'report-player-time';
    const rateLabel = make('label'), rate = make('select');
    rate.setAttribute('aria-label', chinese ? '播放速度' : '再生速度'); rate.title = chinese ? '播放速度' : '再生速度';
    for (const speed of [0.5, 0.75, 1, 1.25, 1.5, 2]) {
      const option = make('option', `${speed}×`); option.value = String(speed); rate.append(option);
    }
    rate.value = '1'; rateLabel.append(rate);
    const mute = make('button'); mute.type = 'button';
    const savedDuration = Number(durationMs) / 1000;
    const duration = () => Number.isFinite(savedDuration) && savedDuration > 0 ? savedDuration : Number.isFinite(player.duration) ? player.duration : 0;
    const update = () => {
      const total = duration(), current = Math.min(total || Infinity, player.currentTime || 0);
      progress.max = String(total); progress.disabled = !total; progress.value = String(current);
      progress.setAttribute('aria-valuetext', `${time(current)} / ${total ? time(total) : '--:--'}`);
      clock.textContent = `${time(current)} / ${total ? time(total) : '--:--'}`;
      icon(play, player.paused ? 'play' : 'pause', player.paused ? (chinese ? '播放' : '再生') : (chinese ? '暂停' : '一時停止'));
      icon(mute, player.muted ? 'muted' : 'volume', player.muted ? (chinese ? '取消静音' : 'ミュート解除') : (chinese ? '静音' : 'ミュート'));
      mute.setAttribute('aria-pressed', String(player.muted));
    };
    const error = make('p', chinese ? '媒体无法播放，请稍后重试。' : 'メディアを再生できません。後でもう一度お試しください。'); error.hidden = true;
    play.addEventListener('click', async () => {
      if (!player.paused) {player.pause(); return;}
      document.querySelectorAll('#reportMedia audio, #reportMedia video').forEach(other => {if (other !== player) other.pause();});
      try {await player.play(); error.hidden = true;} catch {error.hidden = false;}
    });
    progress.addEventListener('input', () => {
      try {player.currentTime = Number(progress.value); update();} catch {error.hidden = false;}
    });
    rate.addEventListener('change', () => {player.playbackRate = Number(rate.value);});
    player.addEventListener('ratechange', () => {rate.value = String(player.playbackRate);});
    mute.addEventListener('click', () => {player.muted = !player.muted; update();});
    for (const event of ['loadedmetadata', 'durationchange', 'timeupdate', 'play', 'pause', 'ended', 'volumechange']) player.addEventListener(event, update);
    player.addEventListener('error', () => {error.hidden = false;});
    player.controls = false; player.preload = 'metadata'; player.playsInline = true;
    controls.append(play, progress, clock, rateLabel, mute);
    if (player.tagName === 'VIDEO') {
      const fullscreen = make('button'); fullscreen.type = 'button';
      const isFullscreen = () => document.fullscreenElement === wrapper || document.webkitFullscreenElement === wrapper || player.webkitDisplayingFullscreen;
      const updateFullscreen = () => {
        const active = Boolean(isFullscreen());
        icon(fullscreen, active ? 'collapse' : 'expand', active ? (chinese ? '退出全屏' : '全画面を終了') : (chinese ? '全屏' : '全画面'));
        fullscreen.setAttribute('aria-pressed', String(active));
      };
      wrapper.addEventListener('fullscreenchange', updateFullscreen);
      wrapper.addEventListener('webkitfullscreenchange', updateFullscreen);
      player.addEventListener('webkitbeginfullscreen', updateFullscreen);
      player.addEventListener('webkitendfullscreen', updateFullscreen);
      fullscreen.addEventListener('click', async () => {
        try {
          if (isFullscreen()) {
            if (document.fullscreenElement) await document.exitFullscreen();
            else if (document.webkitFullscreenElement) document.webkitExitFullscreen?.();
            else player.webkitExitFullscreen?.();
          } else if (wrapper.requestFullscreen) await wrapper.requestFullscreen();
          else if (wrapper.webkitRequestFullscreen) wrapper.webkitRequestFullscreen();
          else player.webkitEnterFullscreen?.();
          updateFullscreen();
        } catch {}
      }); controls.append(fullscreen); updateFullscreen();
    }
    wrapper.append(player, controls, error); update(); return wrapper;
  };
})();
