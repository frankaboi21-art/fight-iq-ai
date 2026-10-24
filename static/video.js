'use strict';
// Video stays in browser memory. Only explicitly selected JPEG frames are submitted.
(() => {
  const video = $('fightVideo');
  const MAX_FILE = 250 * 1024 * 1024;
  const lab = {url:null, duration:0, busy:false, stream:null, recorder:null,
    cameraPending:false, cameraEpoch:0, timer:null, recordedSeconds:0, frames:[], review:null, context:null, file:null, digest:null};
  let roundJob=null, roundPaused=false;
  const clock = seconds => {
    const tenths=Math.round(seconds*10);
    return `${Math.floor(tenths/600)}:${((tenths%600)/10).toFixed(1).padStart(4,'0')}`;
  };
  const message = (text, error=false) => {
    $('videoStatus').hidden=!text;
    $('videoStatus').textContent=text;
    $('videoStatus').classList.toggle('error',error);
  };
  function controls() {
    const cameraActive=Boolean(lab.stream)||lab.cameraPending;
    const recording=lab.recorder?.state==='recording';
    $('videoReviewFields').disabled=lab.busy||state.busy||cameraActive;
    $('reviewVideo').disabled=!lab.url||lab.busy||state.busy||cameraActive;
    $('reviewVideo').textContent=lab.busy?'Review in progress…':state.authenticated?'Review this section ↗':'Unlock footage review ↗';
    $('videoFile').disabled=lab.busy||state.busy||cameraActive;
    $('openCamera').disabled=lab.busy||state.busy||cameraActive;
    $('startRecording').disabled=recording||!lab.stream;
    $('stopRecording').disabled=!recording;
    for(const id of ['clipStart','clipLength','startHere','nextSection','clearVideo','previousFrame','nextFrame']) {
      $(id).disabled=lab.busy||state.busy||!lab.url||cameraActive;
    }
    $('closeCamera').disabled=recording;
    $('prepareRound').disabled=lab.busy||state.busy||cameraActive||!lab.url;
    $('loadRounds').disabled=lab.busy||state.busy||cameraActive;
    $('roundLength').disabled=lab.busy||state.busy;
    $('roundConsent').disabled=lab.busy||state.busy;
  }
  document.addEventListener('fightiq:access',controls);
  function discardReview() {
    document.dispatchEvent(new Event('fightiq:footage-clear'));
    lab.review=null;lab.frames=[];lab.context=null;
    message('');
    $('videoResults').replaceChildren();$('videoResults').hidden=true;
    $('frameStrip').replaceChildren();$('frameStrip').hidden=true;
    $('videoResultTools').hidden=true;$('videoCopyStatus').textContent='';
  }
  function clip() {
    const start=Number($('clipStart').value);
    if(!Number.isFinite(start)||start<0||start>lab.duration-1)throw new Error('Choose a start with at least one second of footage remaining.');
    const end=Math.min(lab.duration,start+Number($('clipLength').value));
    return {start,end,count:Math.min(50,Math.floor((end-start)*5+0.001))};
  }
  function clipChanged() {
    discardReview();
    try {const c=clip();$('clipSummary').textContent=`${clock(c.start)} – ${clock(c.end)} · ${c.count} frames at 5 fps`;} catch(error){$('clipSummary').textContent=error.message;}
  }
  function releaseVideo() {
    video.pause();video.removeAttribute('src');video.load();
    if(lab.url)URL.revokeObjectURL(lab.url);
    lab.url=null;lab.duration=0;lab.recordedSeconds=0;lab.file=null;lab.digest=null;
    roundJob=null;$('roundResults').replaceChildren();$('roundStatus').textContent='';$('roundProgress').hidden=true;
    $('saveRecording').removeAttribute('href');$('saveRecording').hidden=true;
    $('videoControls').hidden=true;video.hidden=true;$('videoEmpty').hidden=false;
    $('footageName').textContent='Record here or choose a video from your device.';
    discardReview();controls();
  }
  function loadVideo(file, recordedSeconds=0) {
    if(!file||file.size===0){message('That recording is empty. Please try again.',true);return;}
    if(file.size>MAX_FILE){message('Choose a video under 250 MB. Trim or compress it on your device first.',true);return;}
    if(file.type&&!file.type.startsWith('video/')){message('Choose a video file such as MP4, MOV or WebM.',true);return;}
    releaseVideo();lab.file=file;lab.recordedSeconds=recordedSeconds;lab.url=URL.createObjectURL(file);
    video.src=lab.url;video.hidden=false;$('videoEmpty').hidden=true;
    $('footageName').textContent=file.name||'Your camera recording';
    if(recordedSeconds){$('saveRecording').href=lab.url;$('saveRecording').download=file.type.includes('mp4')?'fight-iq-recording.mp4':'fight-iq-recording.webm';$('saveRecording').hidden=false;}
    message('Loading your private preview…');
  }
  video.addEventListener('loadedmetadata',()=>{
    const duration=Number.isFinite(video.duration)?video.duration:lab.recordedSeconds;
    if(!duration||duration<1||duration>14400){releaseVideo();message('Use footage between 1 second and 4 hours with readable timing. Try exporting as MP4.',true);return;}
    lab.duration=duration;$('clipStart').value=0;$('clipStart').max=Math.max(0,duration-1).toFixed(1);
    $('videoControls').hidden=false;clipChanged();controls();
    message('Preview ready. Select a section and describe your athlete. Nothing has been sent yet.');
  });
  video.addEventListener('error',()=>{if(lab.url){releaseVideo();message('This browser cannot play the file. Export it as MP4 (H.264), or try another supported video.',true);}});
  $('videoFile').addEventListener('change',event=>{if(!lab.busy&&!state.busy)loadVideo(event.target.files[0]);event.target.value='';});
  $('clearVideo').addEventListener('click',()=>{releaseVideo();message('Footage and review removed from this tab.');});
  ['clipStart','clipLength'].forEach(id=>$(id).addEventListener('input',clipChanged));
  ['videoDiscipline','videoExperience','videoAthlete','videoGoal'].forEach(id=>$(id).addEventListener('input',discardReview));
  $('startHere').addEventListener('click',()=>{$('clipStart').value=Math.min(video.currentTime,lab.duration-1).toFixed(2);clipChanged();});
  $('nextSection').addEventListener('click',()=>{
    try {const c=clip();if(lab.duration-c.end<1){message('You have reached the end of this video.');return;}$('clipStart').value=c.end.toFixed(2);video.currentTime=c.end;clipChanged();}catch(error){message(error.message,true);}
  });
  for(const [id,direction] of [['previousFrame',-1],['nextFrame',1]]){
    $(id).addEventListener('click',()=>{video.pause();video.currentTime=Math.max(0,Math.min(lab.duration-0.001,video.currentTime+direction/Number($('stepFps').value)));});
  }
  $('playbackSpeed').addEventListener('change',()=>{video.playbackRate=Number($('playbackSpeed').value);});

  function closeCamera() {
    lab.cameraEpoch++;lab.cameraPending=false;
    if(lab.stream)lab.stream.getTracks().forEach(track=>track.stop());
    lab.stream=null;$('cameraPreview').srcObject=null;$('cameraPreview').hidden=true;
    $('cameraControls').hidden=true;video.hidden=!lab.url;$('videoEmpty').hidden=Boolean(lab.url);
    clearInterval(lab.timer);controls();
  }
  $('openCamera').addEventListener('click',async()=>{
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){message('Recording is unavailable in this browser. Record with your device camera and choose the saved video.',true);return;}
    const epoch=++lab.cameraEpoch;lab.cameraPending=true;controls();message('Waiting for camera permission…');
    try {
      const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment',width:{ideal:1280},height:{ideal:720}},audio:false});
      if(epoch!==lab.cameraEpoch){stream.getTracks().forEach(track=>track.stop());return;}
      lab.stream=stream;lab.cameraPending=false;video.pause();video.hidden=true;$('videoEmpty').hidden=true;
      $('cameraPreview').srcObject=stream;$('cameraPreview').hidden=false;$('cameraControls').hidden=false;
      $('recordingStatus').textContent='Camera ready. Recording has not started.';
      await $('cameraPreview').play();message('Camera ready. Start recording when you are ready.');controls();
    } catch(error){closeCamera();message(error.name==='NotAllowedError'?'Camera access was declined. You can still choose a saved video.':'The camera could not be opened. Check whether another app is using it, or choose saved footage.',true);}
  });
  $('closeCamera').addEventListener('click',closeCamera);
  $('startRecording').addEventListener('click',()=>{
    if(!lab.stream||lab.recorder?.state==='recording')return;
    const mime=['video/webm;codecs=vp8','video/webm','video/mp4'].find(type=>MediaRecorder.isTypeSupported(type));
    let chunks=[],bytes=0;const started=performance.now();let failed=false;
    try {
      lab.recorder=new MediaRecorder(lab.stream,{...(mime?{mimeType:mime}:{}),videoBitsPerSecond:3000000});
      lab.recorder.addEventListener('dataavailable',event=>{
        if(event.data.size){chunks.push(event.data);bytes+=event.data.size;}
        if(bytes>=200*1024*1024&&lab.recorder.state==='recording')lab.recorder.stop();
      });
      lab.recorder.addEventListener('error',()=>{failed=true;message('The recording stopped unexpectedly. Please try again.',true);});
      lab.recorder.addEventListener('stop',()=>{
        const elapsed=(performance.now()-started)/1000;
        const blob=new Blob(chunks,{type:lab.recorder.mimeType||mime||'video/webm'});chunks=[];
        closeCamera();lab.recorder=null;
        if(!failed)loadVideo(blob,elapsed);
      },{once:true});
      lab.recorder.start(1000);
      lab.timer=setInterval(()=>{
        const seconds=(performance.now()-started)/1000;
        $('recordingStatus').textContent=`Recording · ${clock(seconds)} / 3:00`;
        if(seconds>=180&&lab.recorder?.state==='recording')lab.recorder.stop();
      },250);
      $('recordingStatus').textContent='Recording · 0:00';message('Recording locally. No footage is being sent.');controls();
    }catch {closeCamera();message('This browser could not start recording. Use your device camera and choose its saved video.',true);}
  });
  $('stopRecording').addEventListener('click',()=>{if(lab.recorder?.state==='recording')lab.recorder.stop();});
  window.addEventListener('pagehide',()=>{if(lab.recorder?.state==='recording')lab.recorder.stop();closeCamera();});

  function waitEvent(target,event,action,timeout=12000) {
    return new Promise((resolve,reject)=>{
      const cleanup=()=>{clearTimeout(timer);target.removeEventListener(event,done);target.removeEventListener('error',fail);};
      const done=()=>{cleanup();resolve();};const fail=()=>{cleanup();reject(new Error('The video could not be decoded at this point. Try another section or export it as MP4.'));};
      const timer=setTimeout(fail,timeout);
      target.addEventListener(event,done,{once:true});target.addEventListener('error',fail,{once:true});
      try {action();} catch(error){cleanup();reject(error);}
    });
  }
  async function extractFrames(selection) {
    const decoder=document.createElement('video');decoder.muted=true;decoder.playsInline=true;decoder.preload='auto';
    const canvas=document.createElement('canvas');const context=canvas.getContext('2d',{alpha:false});
    if(!context)throw new Error('Frame extraction is unavailable in this browser.');
    const frames=[];
    try {
      await waitEvent(decoder,'loadeddata',()=>{decoder.src=lab.url;decoder.load();});
      const scale=Math.min(1,768/Math.max(decoder.videoWidth,decoder.videoHeight));
      canvas.width=Math.round(decoder.videoWidth*scale);canvas.height=Math.round(decoder.videoHeight*scale);
      if(canvas.width<32||canvas.height<32)throw new Error('This video is too small to review. Choose a clearer recording.');
      $('videoProgress').max=selection.count;$('videoProgress').value=0;$('videoProgress').hidden=false;
      for(let index=0;index<selection.count;index++){
        const timestamp=Number((selection.start+index/5).toFixed(3));
        if(Math.abs(decoder.currentTime-timestamp)>0.0001)await waitEvent(decoder,'seeked',()=>{decoder.currentTime=timestamp;});
        context.drawImage(decoder,0,0,canvas.width,canvas.height);
        let jpeg=canvas.toDataURL('image/jpeg',0.72);
        if(jpeg.length>120000)jpeg=canvas.toDataURL('image/jpeg',0.48);
        if(jpeg.length>120000)jpeg=canvas.toDataURL('image/jpeg',0.28);
        if(jpeg.length>120000)throw new Error('This section has too much image detail. Try a lower-resolution video.');
        frames.push({timestamp,image:jpeg});$('videoProgress').value=index+1;
        message(`Preparing frame ${index+1} of ${selection.count}. Your original video stays on this device.`);
      }
      return frames;
    }finally {decoder.removeAttribute('src');decoder.load();canvas.width=0;canvas.height=0;}
  }
  function seekEvidence(timestamp) {video.pause();video.currentTime=timestamp;video.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});}
  function renderFrames() {
    const strip=$('frameStrip');strip.replaceChildren();strip.hidden=false;
    lab.frames.forEach((frame,index)=>{
      const button=node('button',undefined,'frame-thumb');button.type='button';button.setAttribute('aria-label',`View sampled frame ${index+1} at ${clock(frame.timestamp)}`);
      const img=node('img');img.src=frame.image;img.alt=`Sample ${index+1}`;img.loading='lazy';
      button.append(img,node('span',clock(frame.timestamp)));button.addEventListener('click',()=>seekEvidence(frame.timestamp));strip.append(button);
    });
  }
  function renderReview() {
    const r=lab.review,target=$('videoResults');target.replaceChildren();target.hidden=false;
    const summary=node('section',undefined,'panel footage-summary');
    summary.append(node('p',`${lab.context.discipline} · ${clock(r.coverage.start)} – ${clock(r.coverage.end)} · ${r.coverage.frames} sampled frames`,'eyebrow'),node('h3',r.summary));
    summary.append(node('p',`Visibility: ${r.visibility}. Athlete match: ${r.athlete_match}.`,'field-hint'));
    r.limitations.forEach(text=>summary.append(node('p',text,'field-hint')));target.append(summary);
    if(r.moments.length){
      target.append(node('h3','Moments that matter','video-result-heading'));
      const timeline=node('div',undefined,'moment-grid');
      r.moments.forEach(moment=>{
        const card=node('article',undefined,'plan-card moment-card');
        const jump=node('button',`${clock(moment.timestamp)} ↗`,'moment-time');jump.type='button';jump.addEventListener('click',()=>seekEvidence(moment.timestamp));
        card.append(jump,node('p',`${moment.kind} · ${moment.phase} · ${moment.confidence} AI confidence`,'eyebrow'),node('h3',moment.title));
        const frame=lab.frames[moment.frame_numbers[0]-1];if(frame){const img=node('img');img.src=frame.image;img.alt=`Evidence for ${moment.title}`;card.append(img);}
        card.append(node('h4','Visible evidence'),node('p',moment.evidence),node('h4','Why it matters'),node('p',moment.why_it_matters),node('h4','Try this adjustment'),node('p',moment.adjustment));timeline.append(card);
      });target.append(timeline);
    }
    const priority=node('section',undefined,'priority-box footage-priority');priority.append(node('p','YOUR NEXT FOCUS','eyebrow'),node('h3',r.priority),node('p',r.next_session_check));target.append(priority);
    if(r.additions.length){target.append(node('h3','Add to your game','video-result-heading'));const grid=node('div',undefined,'addition-grid');r.additions.forEach(item=>{const card=node('article',undefined,'plan-card');card.append(node('h3',item.skill),node('p',item.rationale),node('h4','Build the foundation'),node('p',item.prerequisite),node('h4','First step'),node('p',item.first_step));grid.append(card);});target.append(grid);}
    if(r.practice.length){target.append(node('h3','Take it into practice','video-result-heading'));const grid=node('div',undefined,'addition-grid');r.practice.forEach(item=>{const card=node('article',undefined,'plan-card');card.append(node('p',`${item.minutes} MINUTES · CONTROLLED PRACTICE`,'eyebrow'),node('h3',item.name),node('p',item.instructions),node('h4','What success looks like'),node('p',item.success_check));grid.append(card);});target.append(grid);}
    $('videoResultTools').hidden=false;
  }
  $('videoReviewForm').addEventListener('submit',async event=>{
    event.preventDefault();if(lab.busy||state.busy||!lab.url)return;
    if(!state.authenticated){openAccess();return;}
    if(!state.coachAvailable){message('AI review is temporarily unavailable. You can still inspect the footage locally.',true);return;}
    let selection;try{selection=clip();}catch(error){message(error.message,true);return;}
    discardReview();lab.busy=true;state.busy=true;updateControls();
    const details={discipline:$('videoDiscipline').value,experience:$('videoExperience').value,athlete:$('videoAthlete').value.trim(),goal:$('videoGoal').value.trim()};
    try {
      // No automatic retry: every submitted review can consume an allowance.
      lab.frames=await extractFrames(selection);renderFrames();
      message(`Reviewing ${lab.frames.length} sampled frames. This may take up to 90 seconds.`);
      const response=await api('/api/v1/video/review',{method:'POST',timeoutMs:95000,body:JSON.stringify({...details,start:selection.start,end:selection.end,consent:$('videoConsent').checked,frames:lab.frames})});
      lab.review=response.review;lab.context=details;renderReview();
      document.dispatchEvent(new CustomEvent('fightiq:footage',{detail:{report:response.review,receipt:response.receipt,discipline:details.discipline}}));
      message(lab.review.visibility==='unusable'||lab.review.athlete_match==='uncertain'?'The footage could not support a confident athlete review. See the limitations below.':'Your footage review is ready. Check the cited moments before applying the advice.');
    }catch(error){if(error.status===401){state.authenticated=false;message('Your beta access expired. Unlock AI Corner, then try again.',true);}else message(error.message,true);}
    finally {lab.busy=false;state.busy=false;$('videoProgress').hidden=true;updateControls();}
  });
  function exportText() {
    const r=lab.review;if(!r)return '';
    return ['FIGHT IQ AI — FOOTAGE REVIEW',`${lab.context.discipline} | ${lab.context.experience}`,`Section ${clock(r.coverage.start)}–${clock(r.coverage.end)}; ${r.coverage.frames} frames at 5 fps`,'',r.summary,...r.limitations,'',...r.moments.flatMap(m=>[`${clock(m.timestamp)} — ${m.title} (${m.confidence} confidence)`,`Evidence: ${m.evidence}`,`Why: ${m.why_it_matters}`,`Adjustment: ${m.adjustment}`,'']),'PRIORITY',r.priority,r.next_session_check,'','ADD TO YOUR GAME',...r.additions.flatMap(a=>[a.skill,a.rationale,`Prerequisite: ${a.prerequisite}`,`First step: ${a.first_step}`,'']),'PRACTICE',...r.practice.flatMap(p=>[`${p.name} — ${p.minutes} minutes`,p.instructions,`Success check: ${p.success_check}`,'']),'AI review of sampled frames can miss fast transitions. Review with a qualified coach.'].join('\n');
  }
  $('downloadVideoReview').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([exportText()],{type:'text/plain;charset=utf-8'}));const anchor=node('a');anchor.href=url;anchor.download='fight-iq-footage-review.txt';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  $('copyVideoReview').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(exportText());$('videoCopyStatus').textContent='Review copied.';}catch{$('videoCopyStatus').textContent='Copy unavailable. Download the review instead.';}});

  const roundApi=(path='',options={})=>api('/api/v1/rounds'+path,options);
  const roundMessage=text=>{$('roundStatus').textContent=text;};
  const roundButton=(text,action)=>{const b=node('button',text,'button quiet');b.type='button';b.addEventListener('click',async()=>{if(lab.busy||state.busy)return;b.disabled=true;try{await action();}catch(e){roundMessage(e.message);}finally{b.disabled=false;}});return b;};
  async function sourceDigest(){
    if(!lab.file)throw new Error('Choose the original video first.');
    if(!lab.digest){const hash=await crypto.subtle.digest('SHA-256',await lab.file.arrayBuffer());lab.digest=[...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('');}
    return lab.digest;
  }
  function showRound(job){
    roundJob=job;
    $('roundProgress').hidden=false;$('roundProgress').max=job.windows.length;$('roundProgress').value=job.completed_sections;
    const target=$('roundResults');target.replaceChildren();
    target.append(node('h4',`${job.context.source_name} · ${job.completed_sections}/${job.windows.length} sections · ${job.status}`),node('p',`${job.attempts} ${job.attempts===1?'request':'requests'} started. Temporary results expire ${new Date(job.expires*1000).toLocaleDateString()}.`,'field-hint'));
    if(job.error)target.append(node('p',job.error,'field-hint'));
    job.sections.forEach((report,index)=>{const detail=node('details'),label=node('summary',`Section ${index+1} · ${clock(report.coverage.start)}–${clock(report.coverage.end)} · ${report.visibility}`);detail.append(label,node('p',report.summary));report.limitations.forEach(t=>detail.append(node('p',t,'field-hint')));report.moments.forEach(m=>detail.append(roundButton(`${clock(m.timestamp)} · ${m.title}`,async()=>{if(await sourceDigest()!==job.context.source_digest)throw new Error('Choose the original file to open this evidence timestamp.');seekEvidence(m.timestamp);}),node('p',m.evidence),node('p',m.adjustment)));target.append(detail);});
    if(job.status==='complete')target.append(roundButton('Open completed round index',()=>openRoundIndex(job)));
  }
  async function openRoundIndex(job){
    if(await sourceDigest()!==job.context.source_digest)throw new Error('Choose the original video to open its index and evidence timestamps.');
    discardReview();lab.review=job.report;lab.context=job.context;renderReview();
    document.dispatchEvent(new CustomEvent('fightiq:footage',{detail:{report:job.report,receipt:job.receipt,discipline:job.context.discipline}}));
    message('Round index ready. Review the individual section findings above; this is a sampled review, not continuous motion tracking.');
  }
  async function runRound(job){
    if(lab.busy||state.busy)return;
    if(!state.authenticated){openAccess();return;}
    if(!lab.file)throw new Error('Choose the same original video to continue.');
    lab.busy=true;state.busy=true;roundPaused=false;updateControls();
    $('pauseRound').hidden=false;$('cancelRound').hidden=false;
    try{
      if(await sourceDigest()!==job.context.source_digest)throw new Error('This is a different video. Choose the original file before continuing this round.');
      if(!$('videoConsent').checked||!$('roundConsent').checked)throw new Error('Confirm footage permission and temporary result storage before continuing.');
      discardReview();showRound(job);
      while(!roundPaused&&!['complete','cancelled'].includes(job.status)){
        if(job.status!=='running'){
          const index=job.completed_sections, window=job.windows[index];
          const frames=await extractFrames({...window,count:Math.min(50,Math.floor((window.end-window.start)*5+0.001))});
          if(roundPaused)break;
          roundMessage(`Submitting section ${index+1} of ${job.windows.length}. You can pause or cancel.`);
          const {discipline,experience,athlete,goal}=job.context;
          job=await roundApi(`/${job.id}/sections/${index}`,{method:'POST',body:JSON.stringify({discipline,experience,athlete,goal,...window,frames,consent:true,retry:['failed','interrupted'].includes(job.status)})});
          frames.length=0;showRound(job);
        }
        while(job.status==='running'){
          await new Promise(resolve=>setTimeout(resolve,1500));
          job=await roundApi('/'+job.id);showRound(job);
          roundMessage(`Reviewed ${job.completed_sections} of ${job.windows.length} sections. ${roundPaused?'Pausing after the current section.':'Processing the current section…'}`);
        }
        if(['failed','interrupted'].includes(job.status))throw new Error(job.error);
      }
      if(job.status==='complete'){await openRoundIndex(job);roundMessage('Round review complete. Inspect the sections, then save the index if useful.');}
      else roundMessage(job.status==='cancelled'?'Round review cancelled. Completed sections remain available for seven days.':'Paused. Use “My recent round reviews” to continue with the same file.');
    }catch(e){roundMessage(e.message+' No section will be retried automatically.');}
    finally{lab.busy=false;state.busy=false;$('videoProgress').hidden=true;$('pauseRound').hidden=true;$('cancelRound').hidden=true;updateControls();}
  }
  $('pauseRound').addEventListener('click',()=>{roundPaused=true;roundMessage('Pause requested. Any already submitted section will finish; no new section will be sent.');});
  $('cancelRound').addEventListener('click',async()=>{
    if(!roundJob)return;
    roundPaused=true;$('cancelRound').disabled=true;
    try{showRound(await roundApi('/'+roundJob.id+'/cancel',{method:'POST',body:'{}'}));roundMessage('Cancelled. An already started provider request may still consume an allowance.');}catch(e){roundMessage('Paused locally, but cancellation could not be confirmed: '+e.message);}finally{$('cancelRound').disabled=false;}
  });
  $('prepareRound').addEventListener('click',async()=>{
    if(lab.busy||state.busy||!lab.url)return;
    if(!state.authenticated){openAccess();return;}
    if(!$('videoReviewForm').reportValidity())return;
    if(!$('roundConsent').checked){roundMessage('Confirm temporary text storage before preparing this round.');return;}
    const start=Number($('clipStart').value),length=Number($('roundLength').value),end=Math.min(lab.duration,start+length);
    if(!Number.isFinite(start)||!Number.isFinite(length)||start<0||length<1||length>300||end-start<1){roundMessage('Choose a valid start and a round length from 1 to 300 seconds.');return;}
    const count=Math.ceil((end-start)/10);
    const dialog=node('dialog');dialog.setAttribute('aria-label','Confirm round review');
    dialog.append(node('h2','Review this round?'),node('p',`${clock(start)}–${clock(end)} · ${count} ${count===1?'section':'consecutive sections'} · up to ${count} provider ${count===1?'request':'requests'} at 5 sampled frames per second. Requests count toward shared service allowances, including failures. This is not a guaranteed price or an instant result.`),node('p','Only the file name, coaching context and text results are stored privately for seven days. Images are discarded after each section.'));
    const begin=roundButton('Start round review',async()=>{
      begin.disabled=true;
      try{
        const digest=await sourceDigest();
        const job=await roundApi('',{method:'POST',body:JSON.stringify({discipline:$('videoDiscipline').value,experience:$('videoExperience').value,athlete:$('videoAthlete').value.trim(),goal:$('videoGoal').value.trim(),start,end,source_name:($('footageName').textContent||'Recording').slice(0,160),source_digest:digest,consent:true})});
        dialog.close();await runRound(job);
      }catch(e){let error=dialog.querySelector('.error');if(!error){error=node('p',undefined,'error');error.setAttribute('role','alert');dialog.append(error);}error.textContent=e.message;}
    });
    dialog.append(begin,roundButton('Go back',()=>dialog.close()));dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
  });
  $('loadRounds').addEventListener('click',async()=>{
    if(lab.busy||state.busy)return;
    try{const {jobs}=await roundApi();const target=$('roundJobs');target.replaceChildren();if(!jobs.length)target.append(node('p','No temporary round reviews. Prepare one with a video above.'));
      jobs.forEach(job=>{const card=node('article',undefined,'hub-practice');card.append(node('h4',job.context.source_name),node('p',`${job.completed_sections}/${job.windows.length} sections · ${job.status} · ${job.context.discipline}`),roundButton('Inspect results',async()=>{showRound(await roundApi('/'+job.id));}));
        if(!['complete','cancelled'].includes(job.status))card.append(roundButton('Continue / retry round',async()=>runRound(await roundApi('/'+job.id))),roundButton('Cancel this round',async()=>{showRound(await roundApi('/'+job.id+'/cancel',{method:'POST',body:'{}'}));card.remove();}));
        card.append(roundButton('Delete temporary review',async()=>{if(!window.confirm('Delete this temporary round review and its section results? Any index already saved to your journal is kept.'))return;await roundApi('/'+job.id,{method:'DELETE'});card.remove();if(roundJob?.id===job.id){roundJob=null;$('roundResults').replaceChildren();$('roundProgress').hidden=true;}roundMessage('Temporary review deleted.');}));
        target.append(card);
      });
    }catch(e){roundMessage(e.message);}
  });
  controls();
})();
