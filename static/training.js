'use strict';
// No credentials, frames or athlete records are written to browser storage.
(() => {
  const root=$('trainingRoot');
  const hub={athlete:null, entries:[], systems:[], team:{coaches:[],athletes:[]}, plan:null, page:'Progress', busy:false, footage:null};
  const disciplines=['MMA','Boxing','Muay Thai','Kickboxing','Brazilian Jiu-Jitsu','Wrestling','Taekwondo'];
  const message=(text,error=false)=>{const el=$('trainingStatus');el.textContent=text;el.hidden=!text;el.classList.toggle('error',error);};
  const post=(path,data)=>api('/api/v1/training'+path,{method:'POST',body:JSON.stringify(data)});
  const read=path=>api('/api/v1/training'+path);
  const remove=path=>api('/api/v1/training'+path,{method:'DELETE'});
  const section=(title,description)=>{const el=node('section',undefined,'panel hub-panel');el.append(node('h3',title));if(description)el.append(node('p',description,'field-hint'));return el;};
  const button=(text,action,kind='quiet')=>{const b=node('button',text,`button ${kind}`);b.type='button';b.addEventListener('click',()=>run(b,action));return b;};
  const link=(text,href)=>{const a=node('a',text,'text-button');a.href=href;return a;};
  const field=(form,label,name,options={})=>{
    const wrap=node('div',undefined,'hub-field'), id=`hub-${name}-${++field.sequence}`;
    const lab=node('label',label);lab.htmlFor=id;
    const input=node(options.choices?'select':options.lines?'textarea':'input');input.id=id;input.name=name;
    if(options.choices)options.choices.forEach(x=>input.append(new Option(typeof x==='string'?x:x.label,typeof x==='string'?x:x.value)));
    else if(options.lines)input.rows=options.lines;
    else input.type=options.type||'text';
    for(const key of ['required','minLength','maxLength','min','max','autocomplete','placeholder'])if(options[key]!==undefined)input[key]=options[key];
    if(options.value!==undefined)input.value=options.value;
    wrap.append(lab,input);form.append(wrap);return input;
  }; field.sequence=0;
  const submit=(form,label,action)=>{const b=node('button',label,'button primary');b.type='submit';form.append(b);form.addEventListener('submit',e=>{e.preventDefault();run(b,()=>action(Object.fromEntries(new FormData(form)),form));});return b;};
  const textField=(form,label,name,value='',length=600)=>field(form,label,name,{value,maxLength:length});
  const localDate=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
  const download=(data,name)=>{const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  async function run(control,fn){
    if(hub.busy)return;hub.busy=true;control.disabled=true;message('');
    try{await fn();}catch(error){const dialog=control.closest('dialog');if(dialog){let alert=dialog.querySelector('.hub-dialog-error');if(!alert){alert=node('p',undefined,'feedback error hub-dialog-error');alert.setAttribute('role','alert');dialog.prepend(alert);}alert.textContent=error.message;alert.scrollIntoView({block:'nearest'});}else{message(error.message,true);$('trainingStatus').scrollIntoView({block:'nearest'});}}
    finally{hub.busy=false;control.disabled=false;}
  }
  function showRecovery(code,note){
    const dialog=node('dialog');dialog.setAttribute('aria-label','Save your recovery code');
    dialog.append(node('h2','Keep your recovery code safe.'),node('p',note),node('p','There is no email reset. Anyone with this code and your username can reset your password. Save it in your password manager.'));
    const codeBox=node('textarea');codeBox.value=code;codeBox.readOnly=true;codeBox.setAttribute('aria-label','Recovery code');dialog.append(codeBox);
    const close=node('button','I have saved my code','button primary');close.type='button';close.addEventListener('click',()=>dialog.close());dialog.append(close);
    dialog.addEventListener('close',()=>{codeBox.value='';dialog.remove();});document.body.append(dialog);dialog.showModal();codeBox.focus();codeBox.select();
  }
  function authPanel(available=true){
    const panel=section('A private home for your training.','An athlete account saves chosen text reviews across devices. AI requests still use the beta invitation code.');
    if(!available){panel.append(node('p','Saved accounts are awaiting the persistent database connection. You can still use Footage Lab and AI Corner below.'),button('Check connection',refresh));return panel;}
    const form=node('form',undefined,'hub-form');
    const mode=field(form,'Account action','mode',{choices:[{label:'Sign in',value:'login'},{label:'Create account',value:'register'},{label:'Reset using recovery code',value:'recover'}]});
    field(form,'Username','handle',{required:true,minLength:3,maxLength:32,autocomplete:'username',placeholder:'Letters, numbers and underscores'});
    const pass=field(form,'Password (15–128 characters)','password',{type:'password',required:true,minLength:15,maxLength:128,autocomplete:'current-password'});
    const recovery=field(form,'Recovery code','recovery',{maxLength:100,autocomplete:'off'});recovery.parentElement.hidden=true;
    mode.addEventListener('change',()=>{recovery.parentElement.hidden=mode.value!=='recover';recovery.required=mode.value==='recover';pass.autocomplete=mode.value==='login'?'current-password':'new-password';});
    submit(form,'Continue',async data=>{
      if(data.mode==='register'&&!state.authenticated){openAccess();message('Unlock beta access, then submit this account form again.');return;}
      const payload={handle:data.handle,password:data.password};if(data.mode==='recover')payload.recovery=data.recovery;
      const result=await post('/'+data.mode,payload);pass.value='';recovery.value='';await refresh();
      if(result.recovery_code)showRecovery(result.recovery_code,result.message);else message('Welcome back. Your saved training is ready.');
    });
    panel.append(form,node('p','Choose a unique password and keep the recovery code. Accounts have no email address or email reset.','field-hint'));return panel;
  }
  async function refresh(){
    const me=await read('/me');hub.athlete=me.athlete;
    if(!me.athlete)document.dispatchEvent(new Event('fightiq:account-signed-out'));
    if(!me.athlete){hub.entries=[];hub.systems=[];hub.plan=null;hub.team={coaches:[],athletes:[]};root.replaceChildren(authPanel(me.available));message(me.available?'':'Saved accounts are not yet connected.');return;}
    const [journal,plan,systems,team]=await Promise.all([read('/entries'),read('/development'),read('/systems'),read('/coaches')]);
    hub.entries=journal.entries;hub.plan=plan;hub.systems=systems.systems;hub.team=team;render();message('');
  }
  function render(){
    root.replaceChildren();
    const bar=node('div',undefined,'hub-account-bar');bar.append(node('strong',hub.athlete.profile.display_name||hub.athlete.handle),node('span',`${hub.athlete.profile.discipline} · ${hub.athlete.profile.experience}`,'field-hint'),button('Sign out',async()=>{await post('/logout',{});await refresh();}));root.append(bar);
    const nav=node('nav',undefined,'hub-nav');nav.setAttribute('aria-label','Training hub');
    ['Progress','Journal','Tactics','Research','Gyms','Coaches','Profile'].forEach(page=>{const b=button(page,()=>{hub.page=page;render();});b.setAttribute('aria-pressed',String(hub.page===page));nav.append(b);});root.append(nav);
    ({Progress:renderProgress,Journal:renderJournal,Tactics:renderTactics,Research:renderResearch,Gyms:renderGyms,Coaches:renderCoaches,Profile:renderProfile})[hub.page]();
  }
  function renderProfile(){
    const panel=section('The athlete behind the footage.','Your profile stays private. Use “Apply to my next review” to place selected details in the visible coaching fields before sending them to AI.');
    const p=hub.athlete.profile, form=node('form',undefined,'hub-form');
    textField(form,'Display name (optional)','display_name',p.display_name,60);
    field(form,'Primary discipline','discipline',{choices:disciplines,value:p.discipline});
    field(form,'Experience','experience',{choices:['Beginner','Intermediate','Advanced'],value:p.experience});
    field(form,'Stance','stance',{choices:['Not specified','Orthodox','Southpaw','Switch'],value:p.stance});
    field(form,'Your development goal','goal',{lines:3,maxLength:600,value:p.goal});textField(form,'Style or preferences','style',p.style,200);
    field(form,'Practice sessions per week','sessions_per_week',{type:'number',min:1,max:7,required:true,value:p.sessions_per_week});
    field(form,'Practice minutes per session','practice_minutes',{type:'number',min:5,max:60,required:true,value:p.practice_minutes});
    field(form,'Advice allowed in my weekly plan','coaching_policy',{choices:[{value:'confirmed_advice',label:'Advice I confirmed, with coach objections held out'},{value:'coach_supported_only',label:'Only drills supported by a currently qualified coach'}],value:p.coaching_policy||'confirmed_advice'});
    submit(form,'Save athlete profile',async data=>{data.sessions_per_week=Number(data.sessions_per_week);data.practice_minutes=Number(data.practice_minutes);await post('/profile',data);await refresh();message('Profile saved.');});panel.append(form,button('Apply to my next review',applyProfile));
    panel.append(node('p','Taekwondo can be tracked in the journal and tactical library. Automated Taekwondo footage coaching is still pending discipline-specific validation.','field-hint'));root.append(panel);
    const privacy=section('Your records, under your control.','Exports include saved text reviews, profile, practice outcomes, tactical systems and comments. They do not include passwords, recovery codes, video or images.');
    privacy.append(button('Download my training archive',async()=>download(await read('/export'),'fight-iq-training-archive.json')),button('Delete my account',deleteAccount));root.append(privacy);
  }
  function applyProfile(){
    if(state.busy)throw new Error('Wait for the current coaching request to finish.');
    const p=hub.athlete.profile;
    if(p.discipline==='Taekwondo')throw new Error('Taekwondo is available for written journal entries and tactical systems. Footage coaching has not been validated for it yet.');
    const focus=hub.plan.tasks.map(t=>`${t.name} (${t.status}, ${t.outcome}; ${t.allocated_minutes} minutes): ${t.success_check}`).join('; ');
    if(($('context').value.trim()||$('videoGoal').value.trim())&&!window.confirm('Replace the current coaching context and video goal with your saved profile and practice priorities?'))return;
    ['discipline','videoDiscipline'].forEach(id=>{$(id).value=p.discipline;$(id).dispatchEvent(new Event('input',{bubbles:true}));});
    ['experience','videoExperience'].forEach(id=>{$(id).value=p.experience;$(id).dispatchEvent(new Event('input',{bubbles:true}));});
    $('context').value=[`Stance: ${p.stance}. Style/preferences: ${p.style}`,`Goal: ${p.goal}`,`Availability: ${p.sessions_per_week} sessions/week, ${p.practice_minutes} focused minutes/session. Outcomes are self-reported.`,focus?`Prior confirmed review practice tasks (not proof of current weakness): ${focus}`:''].join('\n').slice(0,1600);$('context').dispatchEvent(new Event('input'));
    $('videoGoal').value=[p.goal,`Stance: ${p.stance}`,focus?`Reassess these previously selected practice tasks: ${focus}`:''].join('\n').slice(0,600);$('videoGoal').dispatchEvent(new Event('input'));
    message('Profile and practice priorities are now visible in your review fields. Check them before requesting AI coaching.');
  }
  function renderProgress(){
    const plan=hub.plan, metrics=node('div',undefined,'hub-metrics');
    [['Saved reviews',plan.metrics.saved_reviews],['Confirmed reviews',plan.metrics.confirmed_reviews],['Tasks practiced',plan.metrics.practiced_tasks],['Tasks reassessed',plan.metrics.reassessed_tasks]].forEach(([label,value])=>{const card=node('div',undefined,'hub-metric');card.append(node('strong',String(value)),node('span',label));metrics.append(card);});root.append(metrics);
    const panel=section('Your next purposeful practice.',plan.goal||'Set a development goal in your profile, then save and confirm a review.');
    panel.append(node('p',`${plan.discipline} · ${plan.sessions_per_week} sessions per week · up to ${plan.practice_minutes} minutes of focused practice per session`,'eyebrow'));
    if(!plan.tasks.length)panel.append(node('p',plan.deferred_tasks?.length?'Some drills need a coach review or timing decision. Check the deferred drills below.':plan.improving_tasks?.length?'Your latest drill outcomes are marked improving. Review the linked evidence with your coach before choosing a new priority.':'No confirmed, unfinished drills yet. Save a footage or corner review, check the advice, and confirm it in your journal.'),link('Review footage →','#footage'));
    plan.tasks.forEach(task=>{const card=node('article',undefined,'hub-practice');card.append(node('h4',task.name),node('p',`${task.allocated_minutes} minutes · ${task.revisit?'Revisit after reassessment':task.status} · ${task.training_type||''}`,'field-hint'),node('p',task.instructions),node('strong','Check for: '+task.success_check));card.append(node('p',task.coach_review?.status==='coach_supported'?'Coach-supported drill · '+task.coach_review.reviews.map(r=>r.reviewer).join(', '):'Athlete-confirmed advice · no current coach support','field-hint'));if(task.priority_reason)card.append(node('p','Why this is selected: '+task.priority_reason));if(task.time_basis)card.append(node('p',task.time_basis,'field-hint'));if(task.next_step)card.append(node('p',task.next_step));if(task.notes)card.append(node('p','Your practice notes: '+task.notes));if(task.source_correction)card.append(node('p','Your source correction: '+task.source_correction));card.append(node('p',`From “${task.source_title}” · ${task.performed_on}`,'field-hint'),button('Record practice / reassess',()=>showEntry(hub.entries.find(e=>e.id===task.entry_id))));panel.append(card);});
    panel.append(node('p',plan.reason,'field-hint'),button('Apply profile & priorities to my next review',applyProfile));root.append(panel);
    renderWeeklyPlan(plan);
    const coverage=section('Progress needs comparable evidence.',`${plan.metrics.reported_improving} reassessed tasks are marked improving by you. These are self-reported outcomes, not a validated ability score.`);
    if(!plan.coverage.length)coverage.append(node('p','Your session coverage will appear here after you save a review.'));
    else{const wrap=node('div',undefined,'hub-table-wrap'),table=node('table',undefined,'hub-table');const head=node('thead'),row=node('tr');['Date / review','Setting','Coverage'].forEach(x=>row.append(node('th',x)));head.append(row);table.append(head);const body=node('tbody');plan.coverage.forEach(e=>{const tr=node('tr');tr.append(node('td',`${e.date} · ${e.title}`),node('td',e.setting),node('td',e.kind==='footage'?`${e.sampled_seconds.toFixed(1)} seconds sampled from ${e.minutes_logged} logged minutes`:e.pillars_reviewed!==null?`${e.pillars_reviewed}/6 pillars reviewed · ${e.minutes_logged} logged minutes`:`Written note · ${e.minutes_logged} logged minutes`));body.append(tr);});table.append(body);wrap.append(table);coverage.append(wrap);}
    coverage.append(node('p','Compare the same discipline, training setting and similar footage coverage. Longer logs or more observations do not automatically mean worse performance.','field-hint'));root.append(coverage);
  }
  function renderWeeklyPlan(plan){
    const week=plan.weekly_plan;if(!week)return;
    const panel=section('Your week, with a clear purpose.',week.note);
    if(week.sessions.length){
      panel.append(node('p',`${week.sessions.length} flexible sessions · ${week.minutes_per_session} focused minutes each · ${week.total_minutes} planned minutes in total`,'eyebrow'),node('p',`Suggested review date: ${week.suggested_review_on}. Choose session days around your usual training; this outline adds no intensity or extra drills.`));
      week.sessions.forEach(session=>{const card=node('details',undefined,'hub-practice');card.append(node('summary',`Session ${session.number} · ${session.focus} · ${session.minutes} minutes`));const list=node('ol');session.task_refs.forEach(ref=>{const task=plan.tasks.find(t=>t.entry_id===ref.entry_id&&t.id===ref.task_id);if(task)list.append(node('li',`${task.name} · ${task.allocated_minutes} minutes · Check: ${task.success_check}`));});card.append(list,node('p',session.check));panel.append(card);});
      panel.append(button('Download this weekly outline',()=>download({format:'fightiq-weekly-outline-v1',snapshot:true,...plan},'fight-iq-weekly-outline.json')),node('p','The live plan updates when you change feedback, outcomes or availability. A downloaded outline is a dated snapshot; check the live plan before using it.','field-hint'));
    }else panel.append(node('p','A weekly outline appears when at least one confirmed drill fits your time budget.'));
    if(plan.deferred_tasks?.length){const detail=node('details');detail.append(node('summary',`${plan.deferred_tasks.length} drills outside the current plan`));plan.deferred_tasks.forEach(task=>{const card=node('article',undefined,'hub-practice');card.append(node('h4',task.name),node('p',task.deferred_reason),node('p',task.allocated_minutes?`${task.allocated_minutes} minutes · ${task.time_basis}`:`Saved duration: ${task.duration||'Not specified'}`,'field-hint'),button('Open source review',()=>showEntry(hub.entries.find(e=>e.id===task.entry_id))));detail.append(card);});panel.append(detail);}
    if(plan.improving_tasks?.length){const detail=node('details');detail.append(node('summary',`${plan.improving_tasks.length} drills marked improving`));plan.improving_tasks.forEach(task=>{const card=node('article',undefined,'hub-practice');card.append(node('h4',task.name),node('p','Removed from active practice after your recorded reassessment. This is your reported outcome, not a verified ability score.'),node('p',task.notes));const later=hub.entries.find(e=>e.id===task.reassessment_entry);if(later)card.append(button('Open reassessment evidence',()=>showEntry(later)));detail.append(card);});panel.append(detail);}
    root.append(panel);
  }
  function saveDialog(snapshot=null){
    if(!hub.athlete){message('Sign in or create an athlete account in My development before saving.',true);$('training').scrollIntoView();return;}
    const dialog=node('dialog');dialog.className='hub-dialog';dialog.setAttribute('aria-label','Save to your journal');
    const form=node('form',undefined,'hub-form');form.append(node('h2',snapshot?'Save this review.':'Log a training note.'));
    field(form,'Title','title',{required:true,maxLength:100,value:snapshot?`${snapshot.discipline} ${snapshot.kind} review`:''});
    field(form,'Discipline','discipline',{choices:disciplines,value:snapshot?.discipline||hub.athlete.profile.discipline});
    field(form,'Purpose','purpose',{choices:[{label:'My own training',value:'self'},{label:'Opponent scouting (private)',value:'opponent'},{label:'Style study (private)',value:'style'}]});
    field(form,'Training setting','training_type',{choices:['drilling','sparring','competition','other']});
    field(form,'Session date','performed_on',{type:'date',required:true,value:localDate()});field(form,'Session duration in minutes (not AI coverage)','minutes',{type:'number',required:true,min:1,max:240,value:30});
    field(form,'Your notes / context','notes',{lines:3,maxLength:2000});textField(form,'Footage reference / source (optional)','source','',300);
    const consent=node('label',undefined,'consent-check'),check=node('input');check.type='checkbox';check.required=true;consent.append(check,node('span','Save this text review and notes to my account. Self-training entries are visible to any coaches I have granted access. Video and images are not saved.'));form.append(consent);
    submit(form,'Save to journal',async data=>{const payload={...data,minutes:Number(data.minutes),kind:snapshot?.kind||'note',report:snapshot?.report||{},receipt:snapshot?.receipt||''};await post('/entries',payload);dialog.close();hub.page='Journal';await refresh();message('Saved. Check the review and mark whether you agree before using its drills.');});
    const cancel=node('button','Cancel','button quiet');cancel.type='button';cancel.addEventListener('click',()=>dialog.close());form.append(cancel);dialog.append(form);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
  }
  function renderJournal(){
    const panel=section('A record of what you learned.','Self-training, opponent research and style studies stay separate. Only confirmed self-training reviews feed your practice plan.');
    panel.append(button('Add a written training / scouting note',()=>saveDialog()));
    const filters=node('div',undefined,'hub-form');const query=field(filters,'Search saved reviews','search',{type:'search',maxLength:100});const purpose=field(filters,'Show','filter',{choices:[{label:'All entries',value:'all'},{label:'My training',value:'self'},{label:'Opponent scouting',value:'opponent'},{label:'Style studies',value:'style'}]});const list=node('div',undefined,'hub-journal');
    const draw=()=>{list.replaceChildren();const matching=hub.entries.filter(e=>(purpose.value==='all'||e.purpose===purpose.value)&&`${e.title} ${e.discipline} ${e.notes}`.toLowerCase().includes(query.value.toLowerCase()));if(!matching.length)list.append(node('p','No saved reviews match. Save a review from Footage Lab or AI Corner, or add a written note.'));matching.forEach(e=>{const card=node('article',undefined,'hub-journal-row');card.append(node('div',undefined));card.firstChild.append(node('h4',e.title),node('p',`${e.performed_on} · ${e.discipline} · ${e.purpose} · ${e.feedback.verdict.replaceAll('_',' ')}`,'field-hint'));card.append(button('Open review',()=>showEntry(e)));list.append(card);});};query.addEventListener('input',draw);purpose.addEventListener('change',draw);draw();panel.append(filters,list);root.append(panel);
  }
  function renderReport(parent,entry){
    const r=entry.report,kind=entry.kind;
    if(kind==='footage'){
      parent.append(node('h3',r.summary),node('p',`${r.coverage.start}–${r.coverage.end} seconds · ${r.coverage.frames} sampled frames · ${r.visibility} visibility`,'field-hint'));
      r.limitations.forEach(x=>parent.append(node('p',x,'field-hint')));
      r.moments.forEach(m=>{const box=node('article',undefined,'hub-practice');box.append(node('h4',`${m.timestamp.toFixed(1)}s · ${m.title}`),node('p',m.evidence),node('p','Why it matters: '+m.why_it_matters),node('p','Adjustment: '+m.adjustment),node('small',`${m.kind} · ${m.confidence} AI confidence`));parent.append(box);});parent.append(node('h4','Priority'),node('p',r.priority),node('p',r.next_session_check));
      r.additions.forEach(a=>{parent.append(node('h4','Explore: '+a.skill),node('p',a.rationale),node('p','Prerequisite: '+a.prerequisite),node('p','First step: '+a.first_step));});
    }else if(kind==='corner'){
      const p=r.plan;parent.append(node('h3',p.priority.title),node('p',p.priority.explanation),node('p',p.priority.action));p.observations.forEach(o=>parent.append(node('p','Reported: '+o)));const list=node('ol');p.tactics.forEach(t=>list.append(node('li',t)));parent.append(list,node('blockquote',p.cue));
    }else if(kind==='session'){
      parent.append(node('h3','Manual observation review'),node('p',`${r.reviewed_count}/6 pillars reviewed · ${r.observation_count} logged observations`));r.mistakes.forEach(m=>parent.append(node('p',`${m.name||m.mistake_id} · ${m.count} times · ${m.severity}`)));parent.append(node('p',r.score_note,'field-hint'));
    }
  }
  async function showEntry(entry,shared=false){
    if(!entry)return;
    const dialog=node('dialog');dialog.className='hub-dialog';dialog.setAttribute('aria-label',entry.title);
    dialog.append(node('h2',entry.title),node('p',`${entry.performed_on} · ${entry.discipline} · ${entry.training_type} · ${entry.minutes} logged minutes`,'eyebrow'),node('p',entry.notes));if(entry.source)dialog.append(node('p','Source: '+entry.source,'field-hint'));renderReport(dialog,entry);
    dialog.append(node('p','Text archive only. Reopen your original video separately to verify timestamped evidence.','field-hint'));
    if(!shared){
      const form=node('form',undefined,'hub-form');form.append(node('h3','Check the advice.'));
      field(form,'My review of this record','verdict',{choices:[{label:'Not yet checked',value:'unreviewed'},{label:'I confirm this review',value:'confirmed'},{label:'Needs correction — exclude from my plan',value:'needs_correction'}],value:entry.feedback.verdict});
      field(form,'Correction / what I learned with my coach','correction',{lines:3,maxLength:2000,value:entry.feedback.correction});
      submit(form,'Save my feedback',async data=>{await post(`/entries/${entry.id}/feedback`,data);dialog.close();await refresh();message('Feedback saved. Your practice plan has been updated.');});dialog.append(form);
    }else dialog.append(node('p','Athlete review: '+entry.feedback.verdict),node('p',entry.feedback.correction));
    entry.tasks.forEach(task=>{
      const panel=section(task.name,task.instructions);panel.append(node('p','Success check: '+task.success_check),node('p',`Original duration: ${task.minutes?task.minutes+' minutes':task.duration||'Not specified'}`,'field-hint'));
      if(!shared){const form=node('form',undefined,'hub-form');field(form,'Practice status','status',{choices:['planned','practiced','reassessed'],value:task.status});field(form,'Observed outcome','outcome',{choices:['not_checked','improving','unchanged','needs_work'],value:task.outcome});
        const later=hub.entries.filter(e=>e.id!==entry.id&&e.created>entry.created&&e.performed_on>=entry.performed_on&&e.purpose==='self'&&e.discipline===entry.discipline&&e.training_type===entry.training_type&&e.feedback.verdict==='confirmed');
        field(form,'Later confirmed review for reassessment','reassessment_entry',{choices:[{label:'Not yet reassessed',value:''},...later.map(e=>({label:`${e.performed_on} · ${e.title}`,value:e.id}))],value:task.reassessment_entry});field(form,'Practice / reassessment notes','notes',{lines:2,maxLength:1000,value:task.notes});
        field(form,'Planned minutes agreed with your coach (optional)','planned_minutes',{type:'number',min:1,max:60,value:task.planned_minutes??''});form.append(node('p','Leave blank to use an exact duration from the saved review. This schedules time only; it does not change the drill instructions or record completed practice.','field-hint'));
        submit(form,'Save practice outcome',async data=>{data.planned_minutes=data.planned_minutes===''?null:Number(data.planned_minutes);await post(`/entries/${entry.id}/tasks/${task.id}`,data);dialog.close();await refresh();message('Practice saved.');});panel.append(form);
      }else panel.append(node('p',`${task.status} · ${task.outcome}`),node('p',task.notes));dialog.append(panel);
    });
    const human=section('Coach evidence review','Each decision applies to one finding or drill. Qualifications are checked by a gym owner, not independently certified by Fight IQ. Original footage must be reviewed separately; a saved text report alone does not validate the video.');dialog.append(human);
    async function loadHuman(){
      const data=await api('/api/v1/validation/entries/'+entry.id);human.replaceChildren(node('h3','Coach evidence review'),node('p','Item-specific human judgments. Gym-checked qualifications are not independent Fight IQ certification.','field-hint'));
      if(!data.reviews.length)human.append(node('p','No coach has reviewed these findings or drills yet. Athlete confirmation and AI confidence are separate.'));
      data.reviews.forEach(r=>{const card=node('details',undefined,'hub-practice');card.append(node('summary',`${r.item_kind} ${r.item_index+1} · ${r.verdict} · ${r.reviewer} · ${r.current?'current':'historical'}`),node('p','Evidence checked: '+r.evidence),node('p','Reason: '+r.explanation));if(r.correction)card.append(node('p','Coach correction: '+r.correction),node('p','Success check: '+r.success_check));card.append(node('p',`${r.credential.qualification} · verified by ${r.credential.verified_by} · review/expiry ${r.credential.expires_on}`,'field-hint'),node('p',r.scope,'field-hint'));human.append(card);});
      const items=[...(entry.report.moments||[]).map((m,i)=>({value:`moment:${i}`,label:`Finding ${i+1}: ${m.title}`})),...entry.tasks.map((t,i)=>({value:`drill:${i}`,label:`Drill ${i+1}: ${t.name}`}))];
      if(data.review_gyms.length&&items.length){const review=node('form',undefined,'hub-form');field(review,'Qualification checked by gym','gym_id',{choices:data.review_gyms.map(g=>({value:g.id,label:g.name}))});field(review,'Finding or drill to review','item',{choices:items});const verdict=field(review,'Coach decision','verdict',{choices:['supported','corrected','rejected','uncertain']});field(review,'What evidence did you check?','evidence',{required:true,minLength:3,maxLength:1000,lines:2});field(review,'Why this decision?','explanation',{required:true,minLength:3,maxLength:1000,lines:2});const correction=field(review,'Controlled practice correction','correction',{maxLength:1000,lines:2}),check=field(review,'Coach success check','success_check',{maxLength:500});verdict.addEventListener('change',()=>{correction.required=check.required=verdict.value==='corrected';});
        const attestation=node('label',undefined,'consent-check'),checked=node('input');checked.type='checkbox';checked.required=true;attestation.append(checked,node('span','I reviewed the original footage or observed the session, checked this specific item, and am reviewing within my coaching competence.'));review.append(attestation);
        submit(review,'Save attributed coach review',async values=>{const [item_kind,index]=values.item.split(':');delete values.item;await api('/api/v1/validation/entries/'+entry.id,{method:'POST',body:JSON.stringify({...values,item_kind,item_index:Number(index),source_reviewed:checked.checked,source_fingerprint:data.source_fingerprint})});await loadHuman();await refresh();message('Coach review saved. Corrections and disputed drills are held out of active practice.');});human.append(review);
      }else if(shared)human.append(node('p','Reviewing requires an active gym coaching role, a current qualification checked for this discipline, and the athlete’s gym sharing permission.'));
    }
    const discussion=section('Athlete & coach discussion','Comments retain their author. A coach comment does not automatically confirm an AI finding.');
    const comments=node('div');discussion.append(comments);const form=node('form',undefined,'hub-form');field(form,'Add a comment','body',{lines:2,maxLength:2000,required:true});
    submit(form,'Save comment',async data=>{await post(`/entries/${entry.id}/comments`,data);form.reset();await loadComments();});discussion.append(form);dialog.append(discussion);
    async function loadComments(){const data=await read(`/entries/${entry.id}/comments`);comments.replaceChildren();data.comments.forEach(c=>{const el=node('article',undefined,'hub-comment');el.append(node('strong',c.author),node('p',c.body));comments.append(el);});}
    if(!shared)dialog.append(button('Delete this review',async()=>{if(!window.confirm('Delete this saved review, its comments and research studies based on it? Linked reassessment outcomes will be reset.'))return;await remove('/entries/'+entry.id);dialog.close();await refresh();}));
    const close=node('button','Close review','button quiet');close.type='button';close.addEventListener('click',()=>dialog.close());dialog.append(close);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
    try{await loadComments();await loadHuman();}catch(error){human.append(node('p',error.message,'feedback error'));}
  }
  function renderCoaches(){
    const panel=section('Keep your coach in the loop.','Grant an existing username access to all your current and future self-training reviews, notes and practice outcomes. They can comment, but cannot change or delete your records. Your profile, scouting and style studies remain private.');
    const form=node('form',undefined,'hub-form');field(form,'Coach’s exact username','handle',{minLength:3,maxLength:32,required:true});
    submit(form,'Grant review access',async data=>{await post('/coaches',data);await refresh();message('Review access granted. No invitation message was sent.');});panel.append(form);
    hub.team.coaches.forEach(handle=>{const row=node('div',undefined,'hub-journal-row');row.append(node('strong',handle),button('Revoke access',async()=>{await remove('/coaches/'+encodeURIComponent(handle));await refresh();message('Access revoked. Existing comments remain in your reviews.');}));panel.append(row);});root.append(panel);
    const athletes=section('Athletes sharing with you.','Open a shared review to add feedback. Your account is not a verification of coaching credentials.');
    if(!hub.team.athletes.length)athletes.append(node('p','No athletes have granted you access yet. Give them your username: '+hub.athlete.handle));
    hub.team.athletes.forEach(a=>athletes.append(button('Review '+a.handle,async()=>{const data=await read(`/athletes/${a.id}/entries`);const list=section(a.handle+' — shared training');if(!data.entries.length)list.append(node('p','No self-training reviews saved yet.'));data.entries.forEach(e=>list.append(button(`${e.performed_on} · ${e.title}`,()=>showEntry(e,true))));athletes.querySelector('.shared-reviews')?.remove();list.classList.add('shared-reviews');athletes.append(list);})));root.append(athletes);
  }
  function renderResearch(){
    const panel=section('Study the evidence. Prepare with purpose.','Compare up to six confirmed footage reviews from one discipline. Choose opponent scouting or style study when saving those reviews, and include a footage reference. These private studies are AI drafts; they do not prove a fighter’s tendencies or predict outcomes.');
    const form=node('form',undefined,'hub-form');textField(form,'Study title','title','',100).required=true;
    const purpose=field(form,'Research purpose','purpose',{choices:[{label:'Opponent scouting',value:'opponent'},{label:'Style study',value:'style'}]});
    field(form,'What do you want to understand?','question',{lines:3,minLength:3,maxLength:600,required:true});
    const choices=node('fieldset',undefined,'bare-fieldset');choices.append(node('legend','Choose confirmed footage reviews'));const list=node('div');choices.append(list);form.append(choices);
    const draw=()=>{list.replaceChildren();const eligible=hub.entries.filter(e=>e.kind==='footage'&&e.purpose===purpose.value&&e.feedback.verdict==='confirmed'&&e.source.trim()&&e.report.athlete_match==='confirmed'&&e.report.visibility!=='unusable'&&e.report.moments.length);
      if(!eligible.length)list.append(node('p','No eligible reviews yet. Save footage with this purpose and a source reference, then check its evidence and confirm it in your journal.'));
      eligible.forEach(e=>{const label=node('label',undefined,'consent-check'),check=node('input');check.type='checkbox';check.name='source_entry';check.value=e.id;label.append(check,node('span',`${e.title} · ${e.discipline} · ${e.source}`));list.append(label);});};purpose.addEventListener('change',draw);draw();
    const consentLabel=node('label',undefined,'consent-check'),consent=node('input');consent.type='checkbox';consent.required=true;consentLabel.append(consent,node('span','I have permission to use these sources. Send the selected review text, source references, corrections and my question to OpenAI, then save the resulting study privately to my account.'));form.append(consentLabel);
    submit(form,'Generate cited study',async data=>{
      if(state.busy)throw new Error('Wait for the current AI request to finish.');
      if(!state.authenticated){openAccess();message('Unlock beta access, then submit this study again.');return;}
      const entry_ids=[...list.querySelectorAll('input:checked')].map(x=>x.value);if(!entry_ids.length||entry_ids.length>6)throw new Error('Choose between one and six source reviews.');
      state.busy=true;updateControls();message('Comparing your chosen evidence. This may take up to 80 seconds.');
      try{await api('/api/v1/research',{method:'POST',timeoutMs:85000,body:JSON.stringify({title:data.title,purpose:data.purpose,question:data.question,entry_ids,consent:consent.checked})});await loadStudies();message('Study saved as an AI draft. Check every citation with your coach.');}finally{state.busy=false;updateControls();}
    });panel.append(form,node('p','Uses the shared written-coaching allowance. There are no automatic retries. Source references are labels; this feature does not download third-party videos.','field-hint'));root.append(panel);
    const library=section('Your research library.','If a source review is corrected or unconfirmed, its studies are marked stale. Deleting a source also deletes studies derived from it.');const results=node('div');library.append(results,button('Refresh studies',loadStudies));root.append(library);
    async function loadStudies(){const data=await api('/api/v1/research');results.replaceChildren();if(!data.studies.length)results.append(node('p','No studies saved yet.'));
      data.studies.forEach(study=>{const card=node('article',undefined,'hub-practice');card.append(node('h4',study.title),node('p',`${study.discipline} · ${study.purpose} · ${study.status}`,'field-hint'));
        if(study.report){const r=study.report;card.append(node('p',r.summary));r.limitations.forEach(x=>card.append(node('p',x,'field-hint')));
          r.findings.forEach(f=>{const detail=node('details');detail.append(node('summary',f.title),node('p','Observed: '+f.observation),node('p','Possible interpretation: '+f.interpretation),node('p','Uncertainty: '+f.uncertainty),node('p','Practice option: '+f.training_option),node('p','Prerequisite: '+f.prerequisite),node('p','Success check: '+f.success_check));f.citations.forEach(c=>{const evidence=node('blockquote');evidence.append(node('p',`${c.title} · ${c.timestamp.toFixed(1)}–${c.end_timestamp.toFixed(1)}s · ${c.source}`),node('p',c.evidence));const entry=hub.entries.find(e=>e.id===c.entry_id);if(entry)evidence.append(button('Open cited review',()=>showEntry(entry)));detail.append(evidence);});card.append(detail);});card.append(node('p','Evidence to collect next: '+r.next_evidence),button('Download study',()=>download(study,'fight-iq-study.json')));
        }card.append(button('Delete study',async()=>{if(!window.confirm('Delete this private research study? Source reviews will remain.'))return;await api('/api/v1/research/'+study.id,{method:'DELETE'});await loadStudies();}));results.append(card);});
    }
    loadStudies().catch(e=>{results.textContent=e.message;});
  }
  function renderGyms(){
    const gymApi=(path='',options={})=>api('/api/v1/gyms'+path,options);
    const send=(path,data={})=>gymApi(path,{method:'POST',body:JSON.stringify(data)});
    const panel=section('Train together. Keep control of your records.','Joining a gym does not share your journal. You choose whether its current and future active coaches can read and comment on your self-training reviews. Profiles, opponent research and style studies stay private. Roles do not verify coaching qualifications.');
    const form=node('form',undefined,'hub-form');field(form,'New gym name','name',{required:true,minLength:2,maxLength:80});submit(form,'Create gym workspace',async data=>{await send('',data);form.reset();await loadGyms();});panel.append(form);
    const list=node('div');panel.append(list,button('Refresh my gyms',loadGyms));root.append(panel);const workspace=node('div');root.append(workspace);
    async function loadGyms(){const data=await gymApi();list.replaceChildren();if(!data.gyms.length)list.append(node('p','No gyms yet. Create a workspace, or ask its owner to invite your exact username: '+hub.athlete.handle));
      data.gyms.forEach(g=>{const card=node('article',undefined,'hub-practice');card.append(node('h4',g.name),node('p',`${g.role} · ${g.status}`,'field-hint'));
        if(g.status==='invited')card.append(button('Accept invitation',async()=>{await send('/'+g.id+'/accept');await loadGyms();await openGym(g.id);}),button('Decline invitation',async()=>{await gymApi(`/${g.id}/members/${hub.athlete.id}`,{method:'DELETE'});await loadGyms();}));
        else card.append(button('Open gym',()=>openGym(g.id)));list.append(card);});
    }
    async function openGym(id){const data=await gymApi('/'+id),g=data.gym;workspace.replaceChildren();const top=section(g.name,`${g.role} workspace · ${data.members.filter(m=>m.status==='active').length} active members`);
      top.append(node('p',g.sharing?'You are sharing current and future self-training reviews with this gym’s active owner and coaches.':'Your journal is not shared with this gym.'),button(g.sharing?'Stop sharing with this gym':'Share my self-training with this gym',async()=>{if(!g.sharing&&!window.confirm('Allow all current and future active coaches in this gym to read and comment on your current and future self-training reviews and notes? Your profile and research stay private.'))return;await send('/'+id+'/sharing',{sharing:!g.sharing});await openGym(id);}));
      top.append(node('p','Stopping gym sharing removes this access path. Separate direct coach grants still apply. Existing comments and any copies a coach already made remain.','field-hint'));
      if(g.role==='owner'){const invite=node('form',undefined,'hub-form');field(invite,'Invite exact username','handle',{required:true,minLength:3,maxLength:32});field(invite,'Gym role','role',{choices:['athlete','coach']});submit(invite,'Invite to gym',async values=>{await send('/'+id+'/members',values);await openGym(id);message('Invitation is visible in their Gyms tab. No external message was sent.');});top.append(invite);}
      const roster=section('Members','Sharing is controlled by each athlete. Removing a member also deletes plans assigned to them in this gym.');
      data.members.forEach(m=>{const row=node('article',undefined,'hub-practice');row.append(node('strong',m.handle),node('p',`${m.role} · ${m.status} · ${m.sharing?'training shared':'training private'}`,'field-hint'));
        if(['owner','coach'].includes(g.role)&&m.status==='active'&&m.sharing)row.append(button('Review '+m.handle,async()=>{const result=await gymApi(`/${id}/athletes/${m.id}/entries`);const reviews=section(m.handle+' — shared reviews');result.entries.forEach(e=>reviews.append(button(e.title,()=>showEntry(e,true))));if(!result.entries.length)reviews.append(node('p','No self-training records saved yet.'));workspace.append(reviews);}));
        if(g.role==='owner'&&m.id!==g.owner)row.append(button('Remove '+m.handle,async()=>{if(!window.confirm('Remove this membership and its assigned plans? Gym access ends immediately; separate coach grants are unchanged.'))return;await gymApi(`/${id}/members/${m.id}`,{method:'DELETE'});await openGym(id);}));roster.append(row);});
      workspace.append(top,roster);
      const qualifications=section('Coaching qualifications','The gym owner checks evidence for another active coach in each discipline. Verification is attributed to this gym; it is not an independent credential check by Fight IQ.');workspace.append(qualifications);
      const credentialData=await api('/api/v1/validation/gyms/'+id+'/credentials');credentialData.credentials.forEach(c=>{const card=node('article',undefined,'hub-practice');card.append(node('strong',`${c.handle} · ${c.discipline}`),node('p',c.qualification),node('p',`${c.current?'Current':'Inactive or expired'} · checked by ${c.verified_by} · review/expiry ${c.expires_on}`,'field-hint'));if(g.role==='owner'&&c.active)card.append(button('Revoke qualification',async()=>{await api(`/api/v1/validation/gyms/${id}/credentials/${c.coach_id}/${encodeURIComponent(c.discipline)}`,{method:'DELETE'});await openGym(id);}));qualifications.append(card);});
      const candidates=data.members.filter(m=>m.status==='active'&&['owner','coach'].includes(m.role)&&m.id!==hub.athlete.id);
      if(g.role==='owner'&&candidates.length){const credentialForm=node('form',undefined,'hub-form');field(credentialForm,'Coach whose evidence you checked','coach_id',{choices:candidates.map(m=>({label:m.handle,value:m.id}))});field(credentialForm,'Qualified discipline','discipline',{choices:disciplines});field(credentialForm,'Qualification / coaching experience checked','qualification',{required:true,minLength:3,maxLength:300});field(credentialForm,'Verification reference (no sensitive documents)','verification_reference',{required:true,minLength:3,maxLength:400});field(credentialForm,'Qualification expiry or next check','expires_on',{type:'date',required:true,min:localDate()});const label=node('label',undefined,'consent-check'),checked=node('input');checked.type='checkbox';checked.required=true;label.append(checked,node('span','I checked this coach’s qualification evidence for the selected discipline. A role or self-declaration alone is insufficient.'));credentialForm.append(label);submit(credentialForm,'Record qualification check',async values=>{await api('/api/v1/validation/gyms/'+id+'/credentials',{method:'POST',body:JSON.stringify({...values,checked_evidence:checked.checked})});await openGym(id);});qualifications.append(credentialForm);}
      if(['owner','coach'].includes(g.role)){
        const assign=section('Create a shared training plan.','Coach-authored plans describe controlled practice and a visible success check. The recipient records their own outcome.');const planForm=node('form',undefined,'hub-form');
        const recipient=field(planForm,'Plan recipient','recipient',{choices:data.members.filter(m=>m.status==='active').map(m=>({label:m.handle,value:m.id}))});
        field(planForm,'Plan title','title',{required:true,maxLength:100});field(planForm,'Plan discipline','discipline',{choices:disciplines});
        field(planForm,'Plan goal','goal',{required:true,lines:2,maxLength:600});field(planForm,'Controlled practice instructions','practice',{required:true,lines:3,maxLength:2000});field(planForm,'Plan success check','success_check',{required:true,lines:2,maxLength:500});field(planForm,'Review together on','review_date',{type:'date',required:true,value:localDate()});
        const source=field(planForm,'Link a shared review (optional)','entry_id',{choices:[{label:'No linked review',value:''}]});let sourceRevision=0;
        async function loadSources(){const revision=++sourceRevision;source.replaceChildren(new Option('No linked review',''));const selected=data.members.find(m=>m.id===recipient.value);if(!selected?.sharing)return;try{const result=await gymApi(`/${id}/athletes/${selected.id}/entries`);if(revision!==sourceRevision)return;result.entries.forEach(e=>source.append(new Option(e.title,e.id)));}catch(e){message(e.message,true);}}
        recipient.addEventListener('change',loadSources);loadSources();submit(planForm,'Assign shared plan',async values=>{await send('/'+id+'/plans',values);await openGym(id);});assign.append(planForm);workspace.append(assign);
      }
      const plans=section('Shared plans','Completion and feedback are self-reported. A completed plan is not proof of technical improvement.');if(!data.plans.length)plans.append(node('p','No plans assigned yet.'));
      data.plans.forEach(p=>{const card=node('article',undefined,'hub-practice');const recipient=data.members.find(m=>m.id===p.recipient);card.append(node('h4',p.title),node('p',`${p.discipline} · for ${recipient?.handle||'member'} · by ${p.author_handle} · ${p.status}`,'field-hint'),node('p','Goal: '+p.goal),node('p',p.practice),node('strong','Success check: '+p.success_check),node('p','Review date: '+p.review_date));if(p.notes)card.append(node('p','Athlete feedback: '+p.notes));
        if(p.recipient===hub.athlete.id){const feedback=node('form',undefined,'hub-form');field(feedback,'My plan status','status',{choices:['accepted','completed','needs_revision'],value:p.status==='assigned'?'accepted':p.status});field(feedback,'My plan feedback','notes',{lines:2,maxLength:1000,value:p.notes});submit(feedback,'Save plan feedback',async values=>{await send(`/${id}/plans/${p.id}/feedback`,values);await openGym(id);});card.append(feedback);}
        if(g.role==='owner'||(g.role==='coach'&&p.author_id===hub.athlete.id))card.append(button('Delete shared plan',async()=>{if(!window.confirm('Delete this shared plan and its feedback for everyone in the gym?'))return;await gymApi(`/${id}/plans/${p.id}`,{method:'DELETE'});await openGym(id);}));plans.append(card);});workspace.append(plans);
      const events=section('Access and activity','The latest 100 recorded actions. Owners see gym activity; other members see actions they performed or that concern their records.');data.audit.forEach(e=>events.append(node('p',`${new Date(e.created*1000).toLocaleString()} · ${e.actor} · ${e.action.replaceAll('_',' ')}${e.subject?' · '+e.subject:''}`,'field-hint')));workspace.append(events);
      workspace.append(button(g.role==='owner'?'Delete gym workspace':'Leave this gym',async()=>{if(!window.confirm(g.role==='owner'?'Permanently delete this gym, its memberships, shared plans and audit history? Personal journals remain.':'Leave this gym and remove its plans assigned to you? Gym access ends; separate coach grants are unchanged.'))return;await gymApi(g.role==='owner'?'/'+id:`/${id}/members/${hub.athlete.id}`,{method:'DELETE'});workspace.replaceChildren();await loadGyms();}));
    }
    loadGyms().catch(e=>{list.textContent=e.message;});
  }
  function renderTactics(){
    const panel=section('Build a system, not a collection of moves.','Describe a situation, choose an action, and map two possible responses with a defensive exit. These are athlete-authored training hypotheses; review them with your coach.');
    panel.append(button('Create a tactical system',()=>systemEditor()));
    if(!hub.systems.length)panel.append(node('p','Create your first system from a moment in your journal. Every branch needs a cue, follow-up and exit.'));
    hub.systems.forEach(s=>{const card=node('article',undefined,'hub-practice');card.append(node('h4',s.title),node('p',s.discipline+' · '+s.status,'field-hint'),button('Explore decisions',()=>exploreSystem(s)),button('Edit as a new version',()=>systemEditor(s)),button('Delete system',async()=>{if(!window.confirm('Delete this tactical system?'))return;await remove('/systems/'+s.id);await refresh();}));panel.append(card);});root.append(panel);
  }
  function systemEditor(original=null){
    const dialog=node('dialog');dialog.className='hub-dialog';dialog.setAttribute('aria-label','Create a tactical system');const f=node('form',undefined,'hub-form');f.append(node('h2','Map the next decision.'));
    field(f,'System title','title',{required:true,maxLength:100,value:original?.title||''});field(f,'Discipline','discipline',{choices:disciplines,value:original?.discipline||hub.athlete.profile.discipline});
    [['Situation / starting position','situation',400],['Visible cue to look for','cue',300],['Your initial action','action',400],['Skills / supervision needed first','prerequisite',300],['Controlled practice task','practice',500],['Observable success check','success_check',300]].forEach(([label,name,maxLength])=>field(f,label,name,{lines:2,required:true,maxLength,value:original?.[name]||''}));
    const sourceChoices=[{label:'No linked review',value:''},...hub.entries.map(e=>({label:e.title,value:e.id}))];field(f,'Link to a saved review','entry_id',{choices:sourceChoices,value:original?.entry_id||''});
    const count=original?.branches.length||2;
    for(let i=0;i<count;i++){f.append(node('h3',`Possible response ${i+1}`));[['Opponent reaction','reaction',200],['Your follow-up','response',400],['Defensive exit / reset','exit',300]].forEach(([label,name,maxLength])=>field(f,label,`${name}_${i}`,{required:true,maxLength,value:original?.branches[i]?.[name]||''}));}
    submit(f,original?'Save a new version':'Save tactical system',async data=>{const branches=[];for(let i=0;i<count;i++){const branch={};['reaction','response','exit'].forEach(k=>{branch[k]=data[`${k}_${i}`];delete data[`${k}_${i}`];});branches.push(branch);}await post('/systems',{...data,branches});dialog.close();await refresh();message('Tactical system saved. Review its assumptions with your coach.');});
    const cancel=node('button','Cancel','button quiet');cancel.type='button';cancel.addEventListener('click',()=>dialog.close());f.append(cancel);dialog.append(f);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
  }
  function exploreSystem(s){
    const dialog=node('dialog');dialog.className='hub-dialog';dialog.setAttribute('aria-label',s.title);
    dialog.append(node('p',s.discipline+' · athlete-authored','eyebrow'),node('h2',s.title),node('p','Prerequisite: '+s.prerequisite));
    const flow=node('div',undefined,'tactical-flow');[['Situation',s.situation],['Watch for',s.cue],['Your action',s.action]].forEach(([label,text])=>{const step=node('div',undefined,'tactical-step');step.append(node('strong',label),node('p',text));flow.append(step);});dialog.append(flow,node('h3','What might happen next?'));
    const outcome=node('div');outcome.setAttribute('aria-live','polite');const choices=node('div',undefined,'hub-nav');
    s.branches.forEach(b=>choices.append(button(b.reaction,()=>{outcome.replaceChildren(node('h3','Your follow-up'),node('p',b.response),node('h4','Exit / reset'),node('p',b.exit));})));dialog.append(choices,outcome,node('h3','Rehearse it'),node('p',s.practice),node('strong','Success check: '+s.success_check),node('p','These branches describe possibilities, not guaranteed opponent reactions.','field-hint'));
    if(s.entry_id){const entry=hub.entries.find(e=>e.id===s.entry_id);if(entry)dialog.append(node('p','Linked evidence: '+entry.title,'field-hint'));}
    const close=node('button','Close system','button quiet');close.type='button';close.addEventListener('click',()=>dialog.close());dialog.append(close);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
  }
  function deleteAccount(){
    const dialog=node('dialog');dialog.setAttribute('aria-label','Delete athlete account');const f=node('form',undefined,'hub-form');f.append(node('h2','Delete your athlete account?'),node('p','This permanently deletes your active profile, saved reviews, practice history, tactical systems, research, temporary round results, comments and sharing grants. Gyms you own and their shared plans are also deleted. Provider backups follow their retention policy. Download your archive first if you need it.'));
    field(f,'Your password','password',{type:'password',required:true,maxLength:128,autocomplete:'current-password'});field(f,'Type DELETE to confirm','confirmation',{required:true,maxLength:6});
    submit(f,'Permanently delete my account',async data=>{await post('/delete-account',data);f.reset();dialog.close();await refresh();message('Your athlete account and active records have been deleted.');});const cancel=node('button','Cancel','button quiet');cancel.type='button';cancel.addEventListener('click',()=>dialog.close());f.append(cancel);dialog.append(f);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
  }
  // Saving is a separate, explicit action after reviewing the generated output.
  $('videoResultTools').append(button('Save footage review',()=>{if(!hub.footage)throw new Error('Generate a footage review first.');saveDialog(structuredClone(hub.footage));}));
  $('planToolbar').append(button('Save corner plan',()=>{if(!state.plan||!state.planReceipt||state.demo||state.busy||state.loading)throw new Error('Build a plan from your own session before saving.');const {receipt,...assessment}=state.assessment;saveDialog({kind:'corner',discipline:$('discipline').value,report:{plan:structuredClone(state.plan),assessment},receipt:state.planReceipt});}));
  $('reviewStatus').insertAdjacentElement('afterend',button('Save session snapshot',()=>{if(!state.assessment?.reviewed_count||state.demo||state.loading||state.busy)throw new Error('Review your own session before saving a snapshot.');const {receipt,...report}=state.assessment;saveDialog({kind:'session',discipline:$('discipline').value,report,receipt});}));
  document.addEventListener('fightiq:footage',event=>{hub.footage={...structuredClone(event.detail),kind:'footage'};});
  document.addEventListener('fightiq:footage-clear',()=>{hub.footage=null;});
  document.addEventListener('fightiq:save-live',event=>{if(!hub.busy)saveDialog({...structuredClone(event.detail),kind:'footage'});});
  refresh().catch(error=>{message(error.message,true);root.replaceChildren(button('Retry loading my training',refresh));});
})();
