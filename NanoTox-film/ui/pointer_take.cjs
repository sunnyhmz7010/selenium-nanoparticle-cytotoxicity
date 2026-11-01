const {chromium}=require('C:/Program Files/nodejs/node_global/node_modules/jnu-cli/node_modules/playwright-core');
const {spawn}=require('node:child_process'),path=require('node:path'),fs=require('node:fs');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await chromium.launch({headless:false,executablePath:'C:/Program Files/Citro Labs/ego lite/Application/ego.exe',args:['--disable-gpu','--force-device-scale-factor=1.5','--start-maximized','--disable-backgrounding-occluded-windows','--disable-features=CalculateNativeWinOcclusion']});
let proc;
try{const p=await b.newPage({viewport:null});await p.goto('http://[::1]:18766/');await p.waitForSelector('#scenario');
const title='NanoTox Assistant · 纳米硒分析';await p.evaluate(t=>document.title=t,title);
await p.keyboard.press('Escape');await wait(1300);
proc=spawn(path.resolve('.venv/Scripts/python.exe'),[path.resolve('NanoTox-film/ui/capture_pointer.py')],{stdio:['pipe','pipe','inherit'],env:{...process.env,NANOTOX_TITLE:title+' - ego'}});
await new Promise((r,j)=>{proc.stdout.once('data',r);proc.once('exit',code=>j(Error('Recorder stopped '+code)))});
const input=await p.context().newCDPSession(p);const cues={};const start=Date.now();function mark(k){cues[k]=(Date.now()-start)/1000;console.log(k,cues[k])}
await p.evaluate(()=>{
 const cursor=document.createElement('div');cursor.id='capture-pointer';cursor.style.cssText='position:fixed;inset:0 auto auto 0;width:48px;height:48px;pointer-events:none;z-index:2147483647;opacity:0;transform:translate(-80px,-80px)';
 cursor.innerHTML='<svg viewBox="-14 -14 48 48" style="width:48px;height:48px;overflow:visible"><circle cx="0" cy="0" r="10" fill="#16ab90" fill-opacity=".19" stroke="#08765c" stroke-width="1.2"/><path d="M0 0 L3 23 L9 17 L15 27 L20 24 L14 14 L23 13 Z" fill="#102e29" stroke="white" stroke-width="2.2" stroke-linejoin="round"/></svg>';document.body.append(cursor);
 window.addEventListener('pointermove',e=>{cursor.style.transform='translate('+(e.clientX-14)+'px,'+(e.clientY-14)+'px)';cursor.style.opacity='1'},{capture:true});
 window.addEventListener('pointerdown',()=>cursor.querySelector('circle').animate([{r:'7px',opacity:1},{r:'19px',opacity:0}],{duration:450}),{capture:true});
});
async function click(sel){
 const l=p.locator(sel),box=await l.boundingBox();if(!box)throw Error(sel);
 const x=box.x+box.width*.5,y=box.y+box.height*.5;
 await p.evaluate(()=>document.querySelector('#capture-pointer').style.opacity='0');await wait(110);
 await input.send('Input.dispatchMouseEvent',{type:'mouseMoved',x,y});await wait(500);
 if(!await l.evaluate((el,{x,y})=>el.contains(document.elementFromPoint(x,y)),{x,y}))throw Error('Target mismatch '+sel);
 await input.send('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',clickCount:1});await input.send('Input.dispatchMouseEvent',{type:'mouseReleased',x,y,button:'left',clickCount:1});await wait(440);
}
await wait(1200);mark('baseline');await click('#scenario button');await p.waitForFunction(()=>prediction.textContent==='54.09%');await wait(1100);await click('.chips button:nth-child(2)');await wait(1600);mark('input');await click('[name=dose]');await p.keyboard.press('Control+a');await p.keyboard.type('320',{delay:135});await wait(350);await click('#scenario button');await p.waitForFunction(()=>prediction.textContent==='54.76%');await wait(1000);
mark('question');await click('.composer input');for(const ch of '浓度贡献是多少？'){await p.keyboard.insertText(ch);await wait(90)}await p.keyboard.press('Enter');await wait(2100);mark('compare');await click('.chips button:last-child');await wait(2200);
for(const i of [0,1,2,3,5]){mark('tab'+i);await click('[data-tab="'+i+'"]');await wait(2050)}
mark('return');await click('[data-tab="6"]');await wait(1800);fs.writeFileSync('NanoTox-film/ui/pointer-cues.json',JSON.stringify(cues));console.log(cues)
}finally{if(proc && proc.exitCode===null){let end=new Promise(r=>proc.once('exit',r));proc.stdin.end('stop\n');await end}await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
