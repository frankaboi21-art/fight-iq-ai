// DOM logic checks only: no browser, camera, network or layout rendering.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {JSDOM} = require('jsdom');

async function main(){
  const root=path.resolve(__dirname,'..');
  const dom=new JSDOM(fs.readFileSync(path.join(root,'static/index.html'),'utf8'),{url:'https://fightiq.test',runScripts:'outside-only'});
  const w=dom.window, doc=w.document, context=dom.getInternalVMContext();
  w.HTMLElement.prototype.scrollIntoView=function(){};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  w.matchMedia=()=>({matches:false});w.confirm=()=>true;w.structuredClone=structuredClone;
  const calls=[];
  let athlete={id:'test-athlete',handle:'test_athlete',profile:{display_name:'',discipline:'MMA',experience:'Beginner',stance:'Orthodox',goal:'Balanced exits',style:'',sessions_per_week:3,practice_minutes:15}};
  let entries=[],systems=[],weeklyFixture=null;
  const plan=()=>weeklyFixture||({goal:athlete.profile.goal,discipline:athlete.profile.discipline,tasks:[],sessions_per_week:3,practice_minutes:15,reason:'Rules-based organizer.',metrics:{saved_reviews:entries.length,confirmed_reviews:0,practiced_tasks:0,reassessed_tasks:0,reported_improving:0},coverage:[]});
  w.fetch=async(url,options={})=>{
    const method=options.method||'GET',data=options.body?JSON.parse(options.body):null;calls.push({url,method,data});
    let result;
    if(url==='/api/v1/health')result={coach_available:true};
    else if(url==='/api/v1/session')result={authenticated:true,access_available:true};
    else if(url==='/api/v1/mistakes')result={mistakes:[],pillars:[]};
    else if(url.endsWith('/me'))result={available:true,athlete};
    else if(url.endsWith('/development'))result=plan();
    else if(url.endsWith('/coaches'))result={coaches:[],athletes:[]};
    else if(url.endsWith('/profile')){athlete.profile=data;result={profile:data};}
    else if(url.includes('/tasks/')&&method==='POST'){const e=entries.find(e=>url.includes('/'+e.id+'/'));Object.assign(e.tasks[0],data);result={entry:e};}
    else if(url.endsWith('/entries')&&method==='POST'){const e={...data,id:'entry-'+entries.length,created:Date.now(),feedback:{verdict:'unreviewed',correction:''},tasks:[]};entries.unshift(e);result={entry:e};}
    else if(url.endsWith('/entries'))result={entries};
    else if(url.endsWith('/systems')&&method==='POST'){const s={...data,id:'system-1',status:'athlete-authored'};systems.push(s);result={system:s};}
    else if(url.endsWith('/systems'))result={systems};
    else if(url.endsWith('/comments'))result={comments:[]};
    else if(url.startsWith('/api/v1/validation/entries/'))result={reviews:[],review_gyms:[],source_fingerprint:'a'.repeat(64)};
    else throw new Error('Unexpected mocked request: '+url);
    return {ok:true,status:200,json:async()=>result,headers:{get:()=>null}};
  };
  for(const file of ['app.js','video.js','training.js'])vm.runInContext(fs.readFileSync(path.join(root,'static',file),'utf8'),context,{filename:file});
  const settle=()=>new Promise(resolve=>setTimeout(resolve,20));
  const btn=text=>{const found=[...doc.querySelectorAll('button')].find(x=>x.textContent===text);assert.ok(found,'Missing control: '+text);return found;};
  const click=async text=>{btn(text).click();await settle();};
  const submit=async form=>{form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await settle();};
  await settle();
  assert.match(doc.getElementById('trainingRoot').textContent,/Your next purposeful practice/);
  await click('Profile');
  let form=doc.querySelector('form:has([name=display_name])');
  form.elements.display_name.value='<img src=x onerror=alert(1)>';
  form.elements.discipline.value='Boxing';
  form.elements.sessions_per_week.value='4';
  await submit(form);
  assert.equal(athlete.profile.sessions_per_week,4);
  assert.equal(doc.querySelector('#trainingRoot img'),null,'Profile text must not become HTML');
  await click('Apply to my next review');
  assert.equal(doc.getElementById('videoDiscipline').value,'Boxing');
  assert.match(doc.getElementById('context').value,/Balanced exits/);
  assert.equal(calls.filter(c=>c.url.includes('/ai/')||c.url.includes('/video/review')).length,0,'Applying a profile must not send it to AI');
  // A snapshot save sends the signed report unchanged and separates its receipt.
  vm.runInContext("state.assessment={reviewed_count:1,receipt:'test-receipt',overall_score:null};state.loading=false;state.demo=false;state.busy=false",context);
  await click('Save session snapshot');
  let dialog=doc.querySelector('dialog[open]');assert.ok(dialog);
  form=dialog.querySelector('form');form.elements.title.value='A saved session';form.querySelector('input[type=checkbox]').checked=true;
  await submit(form);
  const saved=calls.find(c=>c.method==='POST'&&c.url.endsWith('/entries')).data;
  assert.equal(saved.receipt,'test-receipt');assert.equal(saved.report.receipt,undefined);assert.equal(saved.kind,'session');assert.equal(typeof saved.minutes,'number');
  assert.match(doc.getElementById('trainingRoot').textContent,/A saved session/);
  await click('Tactics');await click('Create a tactical system');
  dialog=doc.querySelector('dialog[open]');form=dialog.querySelector('form');
  for(const input of form.querySelectorAll('input[required],textarea[required]'))input.value=input.name;
  form.elements.title.value='Entry decision';
  await submit(form);
  assert.equal(systems.length,1);assert.equal(systems[0].branches.length,2);
  assert.equal(systems[0].branches[0].reaction,'reaction_0');assert.equal(systems[0].reaction_0,undefined);
  await click('Explore decisions');await click('reaction_0');
  assert.match(doc.querySelector('dialog[open]').textContent,/response_0/);
  doc.querySelector('dialog[open]').close();
  // Invalidated footage cannot be accidentally archived from the previous review.
  w.document.dispatchEvent(new w.CustomEvent('fightiq:footage',{detail:{report:{summary:'old'},receipt:'old',discipline:'MMA'}}));
  w.document.dispatchEvent(new w.Event('fightiq:footage-clear'));
  await click('Save footage review');
  assert.match(doc.getElementById('trainingStatus').textContent,/Generate a footage review first/);
  assert.equal(doc.querySelector('dialog[open]'),null);
  // Weekly scheduling is a read-only outline until the athlete explicitly saves practice.
  const practice={id:'0',name:'<img src=x> drill',instructions:'Controlled fixture instructions.',minutes:5,status:'planned',outcome:'not_checked',notes:'',reassessment_entry:'',success_check:'A visible check.',entry_id:'weekly-source',source_title:'Weekly source',performed_on:'2026-10-25',allocated_minutes:5,priority_reason:'Unfinished confirmed drill.',time_basis:'Time from the saved review',training_type:'drilling'};
  entries.push({id:'weekly-source',title:'Weekly source',discipline:'MMA',purpose:'self',kind:'note',notes:'UI fixture',report:{},performed_on:'2026-10-25',created:1,minutes:20,training_type:'drilling',feedback:{verdict:'confirmed',correction:''},tasks:[practice]});
  weeklyFixture={...plan(),tasks:[practice],deferred_tasks:[],improving_tasks:[],weekly_plan:{note:'Flexible sessions.',suggested_review_on:'2026-11-01',generated_on:'2026-10-25',minutes_per_session:5,total_minutes:5,sessions:[{number:1,focus:'Check practice',minutes:5,task_refs:[{entry_id:'weekly-source',task_id:'0'}],check:'Compare later evidence.'}]}};
  // Switching profile saves refreshes the hub from the API fixture.
  await click('Profile');await submit(doc.querySelector('form:has([name=display_name])'));await click('Progress');
  assert.match(doc.getElementById('trainingRoot').textContent,/Your week, with a clear purpose/);
  assert.match(doc.getElementById('trainingRoot').textContent,/Compare later evidence/);
  assert.equal(doc.querySelector('#trainingRoot img'),null);
  let exportedBlob,exportedName;
  w.URL.createObjectURL=blob=>{exportedBlob=blob;return 'blob:weekly-test';};w.URL.revokeObjectURL=()=>{};
  w.HTMLAnchorElement.prototype.click=function(){exportedName=this.download;};
  await click('Download this weekly outline');
  const exportedText=await new Promise((resolve,reject)=>{const reader=new w.FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsText(exportedBlob);});
  const exported=JSON.parse(exportedText);assert.equal(exportedName,'fight-iq-weekly-outline.json');assert.equal(exported.snapshot,true);assert.equal(exported.weekly_plan.total_minutes,5);assert.equal(exported.tasks[0].entry_id,'weekly-source');
  assert.equal(calls.filter(c=>c.url.includes('/tasks/')).length,0,'Exporting a schedule must not record practice');
  await click('Record practice / reassess');dialog=doc.querySelector('dialog[open]');form=dialog.querySelector('form:has([name=planned_minutes])');
  form.elements.planned_minutes.value='7';await submit(form);
  const timing=calls.find(c=>c.url.includes('/tasks/')).data;assert.equal(timing.planned_minutes,7);assert.equal(timing.status,'planned');assert.equal(timing.outcome,'not_checked');
  dom.window.close();
  console.log('Training UI logic checks passed: profile/XSS, explicit AI context, signed snapshots, tactical branches, stale-footage protection, weekly outline/export and explicit planning time.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
