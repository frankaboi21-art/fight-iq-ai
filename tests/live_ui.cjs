// Synthetic media API checks: never opens a camera or makes a network request.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
async function main(){
  const root=path.resolve(__dirname,'..'),dom=new JSDOM(fs.readFileSync(path.join(root,'static/index.html'),'utf8'),{runScripts:'outside-only',url:'https://fightiq.test'});
  const w=dom.window,d=w.document,context=dom.getInternalVMContext(),video=d.getElementById('liveVideo');
  let clock=1000,playing=false,hidden=false,cameraRequests=0,windowResolve,cameraResolve,stoppedTracks=0,session=0;
  const calls=[];
  Object.defineProperty(w.performance,'now',{value:()=>clock});
  Object.defineProperty(d,'hidden',{get:()=>hidden});
  for(const [key,get] of Object.entries({videoWidth:()=>640,videoHeight:()=>360,readyState:()=>4,ended:()=>false,paused:()=>!playing,currentTime:()=>clock/1000}))Object.defineProperty(video,key,{get});
  video.play=async()=>{playing=true;};video.pause=()=>{playing=false;};video.load=()=>{};
  w.HTMLCanvasElement.prototype.getContext=()=>({drawImage(){}});w.HTMLCanvasElement.prototype.toDataURL=()=>('data:image/jpeg;base64,'+'a'.repeat(100));
  w.URL.createObjectURL=()=> 'blob:synthetic';w.URL.revokeObjectURL=()=>{};
  Object.defineProperty(d.getElementById('liveFile'),'files',{value:[{size:100,type:'video/mp4'}]});
  Object.defineProperty(w.navigator,'mediaDevices',{value:{getUserMedia:()=>{cameraRequests++;return new Promise(resolve=>{cameraResolve=resolve;});}}});
  const timers=new Set();w.setTimeout=(fn,ms)=>{const t=setTimeout(()=>{timers.delete(t);clock+=ms;fn();},ms===180000?100000:Math.min(ms,5));timers.add(t);return t;};w.clearTimeout=t=>{clearTimeout(t);timers.delete(t);};
  w.mockAPI=async(url,options={})=>{calls.push({url,body:options.body?JSON.parse(options.body):null});if(url.endsWith('/me'))return {athlete:{id:'synthetic'}};if(url.endsWith('/start'))return {id:'session-'+(++session)};if(url.endsWith('/stop'))return {stopped:true};if(url.endsWith('/window'))return new Promise(resolve=>{windowResolve=resolve;});throw new Error('Unexpected '+url);};
  vm.runInContext("const $=id=>document.getElementById(id);const state={busy:false,authenticated:true};const api=window.mockAPI;const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};const updateControls=()=>document.dispatchEvent(new Event('fightiq:access'));const openAccess=()=>{};",context);
  vm.runInContext(fs.readFileSync(path.join(root,'static/live.js'),'utf8'),context);
  d.getElementById('liveAthlete').value='Synthetic athlete';d.getElementById('liveConsent').checked=true;d.getElementById('liveWindows').value='1';
  const submit=()=>d.getElementById('liveForm').dispatchEvent(new w.Event('submit',{cancelable:true}));
  const until=async predicate=>{for(let i=0;i<400&&!predicate();i++)await new Promise(resolve=>setTimeout(resolve,5));assert.ok(predicate(),'Timed out waiting for synthetic state');};
  submit();await until(()=>Boolean(windowResolve));
  assert.equal(cameraRequests,0);assert.equal(calls.filter(c=>c.url.endsWith('/window')).length,1);
  const sent=calls.find(c=>c.url.endsWith('/window')).body;assert.ok(sent.frames.length>=10&&sent.frames.length<=25);assert.ok(sent.end-sent.start>=2);
  d.getElementById('stopLive').click();await until(()=>calls.some(c=>c.url.endsWith('/stop')));
  const stale=windowResolve;windowResolve=null;stale({review:{summary:'Late result must not render'}});await new Promise(resolve=>setTimeout(resolve,30));
  assert.equal(d.getElementById('liveResults').children.length,0);assert.equal(playing,false);assert.equal(d.getElementById('stopLive').disabled,true);
  // Hidden tab stops capture before a request is queued.
  submit();await until(()=>d.getElementById('liveStatus').textContent.startsWith('Capturing'));
  hidden=true;d.dispatchEvent(new w.Event('visibilitychange'));await new Promise(resolve=>setTimeout(resolve,30));
  assert.equal(calls.filter(c=>c.url.endsWith('/window')).length,1);assert.match(d.getElementById('liveStatus').textContent,/Tab hidden/);hidden=false;
  // A camera permission response arriving after Stop must immediately release its tracks.
  d.getElementById('liveSource').value='camera';submit();await until(()=>Boolean(cameraResolve));d.getElementById('stopLive').click();
  cameraResolve({getTracks:()=>[{stop:()=>stoppedTracks++}]});await new Promise(resolve=>setTimeout(resolve,30));assert.equal(stoppedTracks,1);assert.equal(calls.filter(c=>c.url.endsWith('/start')).length,2);
  // A decoder/canvas failure must release capture immediately, without sending partial frames.
  d.getElementById('liveSource').value='file';w.HTMLCanvasElement.prototype.toDataURL=()=>{throw new Error('Synthetic decoder failure');};
  submit();await until(()=>d.getElementById('liveStatus').textContent.includes('could not read this video frame'));
  assert.equal(playing,false);assert.equal(d.getElementById('stopLive').disabled,true);assert.equal(calls.filter(c=>c.url.endsWith('/window')).length,1);
  timers.forEach(clearTimeout);dom.window.close();console.log('Live UI checks passed: bounded synthetic capture, no camera use for files, late-result discard, hidden-tab stop, late-permission cleanup.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
