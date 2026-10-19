'use strict';
const $ = id => document.getElementById(id);
const state = {catalog:[], pillars:[], logs:[], reviewed:[], assessment:null, authenticated:false, accessAvailable:false, coachAvailable:false, busy:false, demo:false, plan:null, revision:0, loading:false};
const friendly = value => value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const node = (tag, text, className) => {const el=document.createElement(tag); if(text!==undefined)el.textContent=text; if(className)el.className=className; return el;};

async function api(path, options={}) {
  const {timeoutMs=65000, ...fetchOptions}=options;
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),timeoutMs);
  try {
    const response=await fetch(path,{...fetchOptions,credentials:'same-origin',signal:controller.signal,headers:{'Content-Type':'application/json','X-FightIQ-Client':'web',...options.headers}});
    let data; try {data=await response.json();} catch {throw new Error('The service is waking up or temporarily unavailable. Please try again shortly.');}
    if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:'Please check your input and try again.');error.status=response.status;const wait=Number(response.headers.get('Retry-After'));if(wait>0)error.message+=` Try again in about ${Math.ceil(wait/60)} minute(s).`;throw error;}
    return data;
  } catch(error) {if(error.name==='AbortError')throw new Error('This request took too long. Please try again.');if(error instanceof TypeError)throw new Error('Connection lost. Check your connection and try again.');throw error;} finally {clearTimeout(timer);}
}
const assessmentPayload = () => ({mistakes:state.logs.map(({mistake_id,severity,round,count})=>({mistake_id,severity,round,count})),reviewed_pillars:state.reviewed});
function feedback(message, error=false){$('coachFeedback').hidden=!message;$('coachFeedback').textContent=message;$('coachFeedback').classList.toggle('error',error);}
function clearPlan(){state.plan=null;state.planReceipt=null;$('coachingPlan').hidden=true;$('coachingPlan').replaceChildren();$('planToolbar').hidden=true;$('planPlaceholder').hidden=false;$('copyStatus').textContent='';feedback('');}
function updateControls(){
  document.dispatchEvent(new Event('fightiq:access'));
  $('coachButton').disabled=state.busy||state.loading||!state.assessment?.reviewed_count;
  $('coachButton').textContent=state.busy?'Building your planâ€¦':state.authenticated?'Build my corner plan â†—':'Unlock AI Corner â†—';
  $('observationFields').disabled=state.busy||state.loading||!state.catalog.length;
  $('contextFields').disabled=state.busy;
  $('loadDemo').disabled=state.busy||state.loading||!state.catalog.length;
  $('clearSession').disabled=state.busy||state.loading||(!state.logs.length&&!state.reviewed.length);
  $('accessButton').disabled=state.busy;
  $('accessButton').textContent=state.authenticated?'Lock AI Corner':'Unlock AI Corner â†—';
  $('cornerAccess').textContent=state.authenticated?'CORNER UNLOCKED':'BETA ACCESS';
  $('allowanceNote').textContent=state.authenticated?'3 requests per 15 minutes Â· Shared limits also apply':'Beta access required Â· 3 requests per 15 minutes';
  document.querySelectorAll('.remove-observation').forEach(button=>button.disabled=state.busy||state.loading);
  document.querySelectorAll('.pillar-check input').forEach(input=>input.disabled=state.busy||state.loading||state.logs.some(log=>state.catalog.find(item=>item.id===log.mistake_id)?.pillar===input.value));
}
function renderLogs(){
  const target=$('observationList');target.replaceChildren();
  $('logCount').textContent=state.logs.reduce((n,x)=>n+x.count,0);
  $('sessionTag').textContent=state.demo?'Sample session':'Your session';
  if(!state.logs.length){const empty=node('div',undefined,'empty-log');empty.append(node('span','ï¼‹','empty-symbol'),node('p','Start with one honest observation.'),node('small','Choose a moment from training, or try a sample session below.'));target.append(empty);}
  state.logs.forEach((log,index)=>{const item=state.catalog.find(x=>x.id===log.mistake_id);const row=node('article',undefined,'observation');const copy=node('div');copy.append(node('h4',item?.name||log.mistake_id),node('p',`Round ${log.round} Â· ${friendly(log.severity)} Â· ${log.count} ${log.count===1?'time':'times'}`));const remove=node('button','Ã—','icon-button remove-observation');remove.type='button';remove.setAttribute('aria-label',`Remove ${item?.name||'observation'} from round ${log.round}`);remove.addEventListener('click',()=>{state.logs.splice(index,1);renderLogs();refreshAssessment();});row.append(copy,remove);target.append(row);});
  updateControls();
}
function renderAssessment(data){
  $('overallScore').textContent=data.overall_score===null?'â€”':data.overall_score;
  $('scoreLabel').textContent=data.assessment_status==='complete'?'Session estimate / 100':data.assessment_status==='partial'?'Partial assessment':'Not assessed';
  $('scoreCaption').textContent=data.assessment_status==='complete'?'Based on reviewed pillars and logged mistakes.':data.assessment_status==='partial'?'Review all six pillars to see an overall estimate.':'An empty log is not a perfect score.';
  $('assessmentSubtitle').textContent=data.reviewed_count?`${data.observation_count} observations Â· ${data.reviewed_count} pillars reviewed`:'Start with an observation or a pillar review.';
  $('coverageText').textContent=`${data.reviewed_count} / 6 pillars`;$('coverage').value=data.reviewed_count;
  const target=$('pillarList');const focusedValue=document.activeElement?.closest('.pillar-check')?.querySelector('input')?.value;target.replaceChildren();
  Object.entries(data.pillar_scores).forEach(([key,pillar])=>{const item=node('div',undefined,'pillar');const top=node('div',undefined,'pillar-top');top.append(node('h4',friendly(key)));const score=node('p',pillar.score===null?'Not assessed':`${pillar.score} / 100`,'pillar-score');score.classList.toggle('unassessed',pillar.score===null);const label=node('label',undefined,'pillar-check');const check=node('input');check.type='checkbox';check.value=key;check.checked=pillar.assessed;check.setAttribute('aria-label',`${friendly(key)} reviewed`);const auto=state.logs.some(log=>state.catalog.find(x=>x.id===log.mistake_id)?.pillar===key);check.disabled=auto||state.busy;check.addEventListener('change',()=>{state.reviewed=check.checked?[...new Set([...state.reviewed,key])]:state.reviewed.filter(x=>x!==key);refreshAssessment();});label.append(check,node('span',auto?'From observations':'Reviewed'));item.append(top,score,label);target.append(item);if(focusedValue===key)check.focus();});
  $('priorityTitle').textContent=data.priority_fix?.name||(data.reviewed_count?'Keep observing.':'Let the observations lead.');
  $('priorityText').textContent=data.priority_fix?.coaching_cue||(data.reviewed_count?'No mistakes are logged for the reviewed skills. That is limited evidence, not proof of perfect performance.':'Your highest-impact correction will appear here.');
}
async function refreshAssessment(){
  const revision=++state.revision;state.loading=true;clearPlan();updateControls();$('reviewStatus').textContent='Updating your assessmentâ€¦';
  try{const data=await api('/api/v1/analysis',{method:'POST',body:JSON.stringify(assessmentPayload())});if(revision!==state.revision)return;state.assessment=data;renderAssessment(data);$('reviewStatus').textContent='';}
  catch(error){if(revision!==state.revision)return;state.assessment=null;$('reviewStatus').textContent=error.message;const retry=node('button','Retry assessment','text-button');retry.type='button';retry.addEventListener('click',refreshAssessment);$('reviewStatus').append(' ',retry);}
  finally{if(revision===state.revision){state.loading=false;updateControls();}}
}
function openAccess(){if(!state.accessAvailable){feedback('AI Corner is being set up. You can review and score your session now.',true);return;}$('accessError').textContent='';$('accessCode').value='';$('accessDialog').showModal();$('accessCode').focus();}
function planCard(label,title){const card=node('section',undefined,'plan-card');card.append(node('p',label,'eyebrow'),node('h3',title));return card;}
function renderPlan(plan){
  const target=$('coachingPlan');target.replaceChildren();
  const observations=node('div',undefined,'plan-observations');observations.append(node('strong',state.demo?'From the sample session':'From your observations'));plan.observations.forEach(value=>observations.append(node('p',value)));target.append(observations);
  const grid=node('div',undefined,'plan-grid');
  const priority=planCard('01 / PRIORITY CORRECTION',plan.priority.title);priority.append(node('p',plan.priority.explanation),node('p',plan.priority.action,'action-line'));
  const tactics=planCard('02 / TACTICAL PLAN','Three steps for your next round.');const steps=node('ol');plan.tactics.forEach(value=>steps.append(node('li',value)));tactics.append(steps);
  const drills=planCard('03 / PURPOSEFUL PRACTICE','Build the habit.');plan.drills.forEach(value=>{const drill=node('div',undefined,'drill');drill.append(node('h4',value.name),node('small',value.duration),node('p',value.instructions));drills.append(drill);});
  const cue=node('section',undefined,'plan-card cue-card');cue.append(node('p','04 / TAKE THIS INTO YOUR NEXT ROUND','eyebrow'),node('blockquote',plan.cue),node('p','A simple cue to come back to under pressure.'));
  grid.append(priority,tactics,drills,cue);target.append(grid);target.hidden=false;$('planPlaceholder').hidden=true;$('planToolbar').hidden=false;
}
function planText(){const p=state.plan;if(!p)return '';return ['FIGHT IQ AI â€” CORNER PLAN',state.demo?'Sample session':'Your session','', 'REPORTED OBSERVATIONS',...p.observations,'','PRIORITY CORRECTION',p.priority.title,p.priority.explanation,p.priority.action,'','TACTICAL PLAN',...p.tactics.map((x,i)=>`${i+1}. ${x}`),'','DRILLS',...p.drills.map(x=>`${x.name} (${x.duration})\n${x.instructions}`),'','CORNER CUE',p.cue,'','Generated from manually logged observations. Review with a qualified coach.'].join('\n');}
async function requestCoaching(){
  if(state.busy||state.loading)return;if(!state.authenticated){openAccess();return;}if(!state.assessment?.reviewed_count){feedback('Review your session first.',true);return;}
  if(!state.coachAvailable){feedback('AI Corner is temporarily unavailable. Your assessment is still available.',true);return;}
  state.busy=true;clearPlan();updateControls();feedback('Your corner is reviewing the session. This can take up to a minute.');
  try{const context=[`Discipline: ${$('discipline').value}`,`Experience: ${$('experience').value||'not specified'}`,$('context').value.trim()].join('\n');const data=await api('/api/v1/ai/coach',{method:'POST',body:JSON.stringify({...assessmentPayload(),context})});state.plan=data.plan;state.planReceipt=data.receipt;renderPlan(data.plan);feedback('Your plan is ready. Review it with your coach before trying the drills.');}
  catch(error){if(error.status===401){state.authenticated=false;feedback('Your access expired. Unlock AI Corner and try again.',true);}else feedback(error.message,true);}
  finally{state.busy=false;updateControls();}
}
$('observationForm').addEventListener('submit',event=>{event.preventDefault();if(state.busy)return;if(state.logs.length>=100){$('reviewStatus').textContent='This session has reached 100 entries. Start a new session to log more.';return;}state.logs.push({mistake_id:$('mistake').value,severity:$('severity').value,round:Number($('round').value),count:Number($('count').value)});renderLogs();refreshAssessment();});
$('loadDemo').addEventListener('click',async()=>{if(state.busy||state.loading)return;state.loading=true;updateControls();try{const data=await api('/api/v1/analysis/demo');state.logs=data.mistakes.map(x=>({mistake_id:x.mistake_id,severity:x.severity,round:x.round,count:x.count}));state.reviewed=data.reviewed_pillars;state.demo=true;renderLogs();await refreshAssessment();}catch(error){$('reviewStatus').textContent=error.message;}finally{state.loading=false;updateControls();}});
$('clearSession').addEventListener('click',()=>{if(state.busy)return;state.logs=[];state.reviewed=[];state.demo=false;renderLogs();refreshAssessment();});
$('coachButton').addEventListener('click',requestCoaching);
$('accessButton').addEventListener('click',async()=>{if(!state.authenticated){openAccess();return;}try{await api('/api/v1/session',{method:'DELETE'});state.authenticated=false;updateControls();feedback('AI Corner is locked on this browser.');}catch(error){feedback(error.message,true);}});
$('closeAccess').addEventListener('click',()=>$('accessDialog').close());
$('accessForm').addEventListener('submit',async event=>{event.preventDefault();$('unlockButton').disabled=true;$('accessError').textContent='';try{await api('/api/v1/session',{method:'POST',body:JSON.stringify({code:$('accessCode').value})});state.authenticated=true;$('accessCode').value='';$('accessDialog').close();updateControls();feedback('Your corner is unlocked. Build your plan when you are ready.');}catch(error){$('accessError').textContent=error.message;}finally{$('unlockButton').disabled=false;}});
$('accessDialog').addEventListener('close',()=>{$('accessCode').value='';});
['discipline','experience','context'].forEach(id=>$(id).addEventListener('input',()=>{if(!state.busy)clearPlan();}));
$('copyPlan').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(planText());$('copyStatus').textContent='Plan copied.';}catch{$('copyStatus').textContent='Copy is unavailable. Download your notes instead.';}});
$('downloadPlan').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([planText()],{type:'text/plain;charset=utf-8'}));const anchor=node('a');anchor.href=url;anchor.download='fight-iq-corner-plan.txt';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
async function initialize(){
  renderLogs();
  const results=await Promise.allSettled([api('/api/v1/mistakes'),api('/api/v1/session'),api('/api/v1/health')]);
  if(results[0].status==='fulfilled'){const data=results[0].value;state.catalog=data.mistakes;state.pillars=data.pillars;$('mistake').replaceChildren(new Option('Choose an observationâ€¦',''));data.mistakes.forEach(item=>$('mistake').add(new Option(item.name,item.id)));$('addObservation').disabled=false;}
  else{$('mistake').replaceChildren(new Option('Could not load observations',''));$('reviewStatus').textContent=results[0].reason.message;const retry=node('button','Retry loading','text-button');retry.type='button';retry.addEventListener('click',initialize);$('reviewStatus').append(' ',retry);}
  if(results[1].status==='fulfilled'){state.authenticated=results[1].value.authenticated;state.accessAvailable=results[1].value.access_available;}
  if(results[2].status==='fulfilled')state.coachAvailable=results[2].value.coach_available;
  updateControls();if(state.catalog.length)await refreshAssessment();
}
initialize();
