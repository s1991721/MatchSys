(() => {
  const canvas=document.getElementById('interviewerWave'),ctx=canvas?.getContext('2d');
  if(!ctx)return;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let player=null,energy=0,frame=null;
  window.CandidateOrb={audio(value){player=value;wake();},release(value){if(player===value)player=null;}};
  function draw(now) {
    frame=null;
    if(document.hidden||document.getElementById('session').hidden)return;
    const width=canvas.clientWidth,height=canvas.clientHeight;
    if(!width||!height)return;
    const ratio=Math.min(window.devicePixelRatio||1,2);
    if(canvas.width!==Math.round(width*ratio)||canvas.height!==Math.round(height*ratio)){
      canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    }
    ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,width,height);
    let target=0;
    if(player?.analyser&&player.waveSamples){
      player.analyser.getByteFrequencyData(player.waveSamples);
      target=player.waveSamples.reduce((sum,value)=>sum+value,0)/(player.waveSamples.length*150);
    }
    energy+=(Math.min(1,target)-energy)*.12;
    const time=reduced.matches?0:now*.00028;
    const pulse=reduced.matches?0:energy;
    const radius=Math.min(width*.32,height*.34)*(1+pulse*.045),cx=width/2,cy=height/2;
    ctx.save();ctx.translate(cx,cy);
    const halo=ctx.createRadialGradient(0,0,radius*.25,0,0,radius*1.5);
    halo.addColorStop(0,'rgba(13,36,74,.2)');halo.addColorStop(.56,'rgba(24,112,206,.13)');halo.addColorStop(.72,'rgba(56,160,255,.10)');halo.addColorStop(1,'rgba(25,80,150,0)');
    ctx.fillStyle=halo;ctx.fillRect(-width/2,-height/2,width,height);
    // Tilted, expanding rings surround the luminous surface.
    for(let ring=0;ring<5;ring++){
      const phase=(time*.5+ring/5)%1;
      ctx.beginPath();ctx.ellipse(0,0,radius*(1.06+phase*.38),radius*(.86+phase*.38),Math.sin(time+ring)*.25,0,Math.PI*2);
      ctx.strokeStyle=`rgba(72,153,255,${(1-phase)*(.12+pulse*.24)})`;ctx.lineWidth=1;ctx.stroke();
    }
    const core=ctx.createRadialGradient(-radius*.3,-radius*.35,0,0,0,radius);
    core.addColorStop(0,'rgba(25,77,117,.45)');core.addColorStop(.8,'rgba(4,18,42,.8)');core.addColorStop(1,'rgba(39,144,218,.3)');
    ctx.beginPath();ctx.arc(0,0,radius,0,Math.PI*2);ctx.fillStyle=core;ctx.fill();
    // Latitude filaments wrap a rotating sphere; displacement grows with audio energy.
    for(let band=0;band<62;band++){
      const latitude=-Math.PI/2+(band+.5)*Math.PI/62;
      ctx.beginPath();
      for(let step=0;step<=140;step++){
        const longitude=step/140*Math.PI*2;
        const wave=Math.sin(longitude*4+latitude*6+time*3)*Math.cos(latitude)*(.085+pulse*.12);
        const lat=latitude+wave;
        const spin=longitude+time+.2*Math.sin(latitude*5+longitude*2+time);
        const x=Math.cos(lat)*Math.cos(spin),z=Math.cos(lat)*Math.sin(spin),y=Math.sin(lat);
        const tilt=.28;
        const py=y*Math.cos(tilt)-z*Math.sin(tilt),depth=y*Math.sin(tilt)+z*Math.cos(tilt);
        const scale=1+wave*.45;
        const px=x*radius*scale,sy=py*radius*scale;
        if(step===0||depth<-.12)ctx.moveTo(px,sy);else ctx.lineTo(px,sy);
      }
      const violet=(Math.sin(latitude*7+time*2)+1)/2;
      ctx.strokeStyle=`rgba(${Math.round(65+violet*76)},${Math.round(204-violet*77)},255,${.54+pulse*.4})`;
      ctx.lineWidth=.7+pulse*.55;ctx.shadowColor=violet>.6?'#9469ff':'#38cfff';ctx.shadowBlur=6+pulse*10;ctx.stroke();
    }
    ctx.shadowBlur=0;
    for(let dot=0;dot<160;dot++){
      const angle=dot*Math.PI*2/160+time*.2;
      const orbit=radius*(1.21+.035*Math.sin(angle*5+time));
      ctx.fillStyle=`rgba(87,181,255,${.16+.34*Math.pow(Math.sin(angle*3+time),2)})`;
      ctx.beginPath();ctx.arc(Math.cos(angle)*orbit,Math.sin(angle)*orbit,.65+pulse*.5,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
    if(!reduced.matches||player)frame=requestAnimationFrame(draw);
  }
  function wake(){if(frame===null)frame=requestAnimationFrame(draw);}
  new MutationObserver(wake).observe(document.getElementById('session'),{attributes:true,attributeFilter:['hidden']});
  document.addEventListener('visibilitychange',wake);window.addEventListener('resize',wake);
  reduced.addEventListener('change',wake);
  window.addEventListener('pagehide',()=>{if(frame!==null)cancelAnimationFrame(frame);frame=null;});
  window.addEventListener('pageshow',wake);wake();
})();
