'use strict';
(() => {
  const video=$('liveVideo');
  const live={running:false,epoch:0,stream:null,url:null,session:null,deadline:null,cancelCapture:null,starting:false};
  const say=text=>{$('liveStatus').textContent=text;};
  function controls(){
    $('liveFields').disabled=live.running||live.starting||state.busy;
    $('stopLive').disabled=!live.running&&!live.starting;
  }
  function release(){
    live.stream?.getTracks().forEach(t=>t.stop());live.stream=null;video.pause();video.srcObject=null;
    video.removeAttribute('src');video.load();if(live.url)URL.revokeObjectURL(live.url);live.url=null;
  }
  async function stop(message='Live practice stopped. No more frames will be sent.'){
    const sid=live.session;live.session=null;live.running=false;live.starting=false;live.epoch++;
    const stoppedEpoch=live.epoch;
    clearTimeout(live.deadline);live.cancelCapture?.();live.cancelCapture=null;release();
    state.busy=false;updateControls();controls();say(message);
    if(sid)try{await api(`/api/v1/live/${sid}/stop`,{method:'POST',body:'{}',timeoutMs:10000});}catch{if(live.epoch===stoppedEpoch)say(message+' The server could not confirm the stop; the session expires automatically.');}
  }
  function capture(epoch,started){
    return new Promise((resolve,reject)=>{
      const canvas=document.createElement('canvas'),scale=Math.min(1,768/Math.max(video.videoWidth,video.videoHeight));
      canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
      const context=canvas.getContext('2d'),frames=[];let timer,lastSource=-1,lastCaptured=0;
      const finish=(error)=>{clearTimeout(timer);live.cancelCapture=null;canvas.width=canvas.height=0;error?reject(error):resolve(frames);};
      live.cancelCapture=()=>finish(new Error('Capture stopped.'));
      const tick=()=>{
        if(epoch!==live.epoch||document.hidden)return finish(new Error('Capture interrupted.'));
        const now=performance.now(),elapsed=(now-started)/1000;
        if(frames.length&&elapsed-frames[0].timestamp>=4){
          if(frames.length<10)return finish(new Error('Too few fresh frames. Improve lighting or camera performance.'));
          return finish();
        }
        if(video.ended||video.paused||video.readyState<2)return finish(new Error('The source stopped. Choose a longer playable clip or restart the camera.'));
        if(frames.length&&now-lastCaptured>600)return finish(new Error('Frame capture stalled. No partial window was submitted.'));
        if(now-lastCaptured>=200&&video.currentTime!==lastSource){
          let image;
          try{context.drawImage(video,0,0,canvas.width,canvas.height);image=canvas.toDataURL('image/jpeg',.65);}
          catch{return finish(new Error('The browser could not read this video frame. Try another playable clip.'));}
          if(image.length>120000)return finish(new Error('Frames are too detailed. Try a simpler background.'));
          frames.push({timestamp:Number(elapsed.toFixed(3)),image});lastCaptured=now;lastSource=video.currentTime;
        }
        timer=setTimeout(tick,35);
      };tick();
    });
  }
  function render(result,details,index){
    const card=node('article',undefined,'hub-practice'),r=result.review;
    card.append(node('h3',`Window ${index} · ${r.coverage.start.toFixed(1)}–${r.coverage.end.toFixed(1)}s`),node('p',`${r.coverage.frames} sampled frames · ${result.processing_seconds}s processing delay · AI draft, not coach reviewed`,'field-hint'),node('p',r.summary),node('p',r.priority));
    r.limitations.forEach(x=>card.append(node('p',x,'field-hint')));
    r.moments.forEach(m=>{const detail=node('details');detail.append(node('summary',`${m.timestamp.toFixed(1)}s · ${m.title}`),node('p',m.evidence),node('p','Why it matters: '+m.why_it_matters),node('p','Possible adjustment: '+m.adjustment));card.append(detail);});
    const save=node('button','Save this live window','button quiet');save.type='button';save.addEventListener('click',()=>document.dispatchEvent(new CustomEvent('fightiq:save-live',{detail:{report:r,receipt:result.receipt,discipline:details.discipline,source:'Live session window '+index,kind:'footage'}})));card.append(save);
    $('liveResults').prepend(card);
  }
  $('liveForm').addEventListener('submit',async event=>{
    event.preventDefault();if(live.running||live.starting||state.busy)return;
    if(!state.authenticated){openAccess();return;}
    if($('cameraPreview').srcObject){say('Close the recording camera before starting live practice.');return;}
    if(document.hidden)return;
    const details={discipline:$('liveDiscipline').value,experience:$('liveExperience').value,athlete:$('liveAthlete').value.trim(),goal:$('liveGoal').value.trim(),consent:$('liveConsent').checked};
    const source=$('liveSource').value,file=$('liveFile').files[0],count=Number($('liveWindows').value);
    if(source==='file'&&(!file||file.size>250*1024*1024)){say('Choose a playable video under 250 MB.');return;}
    live.starting=true;state.busy=true;const epoch=++live.epoch;updateControls();controls();
    try{
      const me=await api('/api/v1/training/me');if(!me.athlete)throw new Error('Sign in to an athlete account first.');
      if(epoch!==live.epoch)return;
      say(source==='camera'?'Waiting for your camera permission…':'Preparing local playback…');
      if(source==='camera'){
        const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:960},height:{ideal:540},facingMode:'environment'},audio:false});
        if(epoch!==live.epoch){stream.getTracks().forEach(t=>t.stop());return;}
        live.stream=stream;video.srcObject=stream;
        stream.getVideoTracks().forEach(track=>track.addEventListener('ended',()=>{if(live.running)stop('The camera disconnected. Capture stopped.');}));
      }else{live.url=URL.createObjectURL(file);video.src=live.url;}
      await video.play();if(epoch!==live.epoch)return;
      if(!video.videoWidth)throw new Error('The source has no readable video frames.');
      const session=await api('/api/v1/live/start',{method:'POST',body:JSON.stringify(details)});
      if(epoch!==live.epoch){await api(`/api/v1/live/${session.id}/stop`,{method:'POST',body:'{}'});return;}
      live.session=session.id;live.running=true;live.starting=false;controls();$('liveResults').replaceChildren();
      const started=performance.now();live.deadline=setTimeout(()=>stop('Three-minute live session limit reached.'),180000);
      for(let index=1;index<=count&&epoch===live.epoch;index++){
        say(`Capturing window ${index} of ${count}…`);const frames=await capture(epoch,started);
        if(epoch!==live.epoch)return;
        const start=frames[0].timestamp,end=Number((frames.at(-1).timestamp+.2).toFixed(3));
        say(`Reviewing window ${index}. Pause your drill to check the result. No other frames are captured while processing.`);
        const result=await api(`/api/v1/live/${session.id}/window`,{method:'POST',timeoutMs:90000,body:JSON.stringify({...details,start,end,frames})}).finally(()=>frames.splice(0));
        if(epoch!==live.epoch)return;
        render(result,details,index);$('liveTiming').textContent=`Latest capture ended at ${end.toFixed(1)}s; feedback took ${result.processing_seconds}s to process. Feedback describes that window, not the current pose.`;
        if(index<count){say('Feedback ready. Next fresh window begins in five seconds. Stop to take more time.');await new Promise(resolve=>setTimeout(resolve,5000));}
      }
      if(epoch===live.epoch)await stop('Selected live windows finished. Capture stopped; review or save the results below.');
    }catch(error){if(epoch===live.epoch)await stop(error.message+' No automatic retry was made.');}
  });
  $('stopLive').addEventListener('click',()=>stop());
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&(live.running||live.starting))stop('Tab hidden. Capture and new submissions stopped.');});
  window.addEventListener('pagehide',()=>{if(live.running||live.starting)stop('Page closed. Capture stopped.');});
  document.addEventListener('fightiq:account-signed-out',()=>{if(live.running||live.starting)stop('Account signed out. Live capture stopped.');});
  document.addEventListener('fightiq:access',controls);controls();
})();
