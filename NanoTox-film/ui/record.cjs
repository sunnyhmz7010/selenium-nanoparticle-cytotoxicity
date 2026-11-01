const {chromium}=require('C:/Program Files/nodejs/node_global/node_modules/jnu-cli/node_modules/playwright-core');
const {spawn}=require('node:child_process'),path=require('node:path'),fs=require('node:fs');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await chromium.launch({headless:false,executablePath:'C:/Program Files/Citro Labs/ego lite/Application/ego.exe',args:['--disable-gpu','--force-device-scale-factor=1.5','--start-maximized','--disable-backgrounding-occluded-windows','--disable-features=CalculateNativeWinOcclusion']});
let proc;
try{const p=await b.newPage({viewport:null});await p.goto('http://[::1]:18766/');await p.waitForSelector('#scenario');
const title='NanoTox Assistant · 研究与预测';await p.evaluate(t=>document.title=t,title);
await p.keyboard.press('Escape');await wait(1300);
proc=spawn(path.resolve('.venv/Scripts/python.exe'),[path.resolve('NanoTox-film/ui/window_capture.py')],{stdio:['pipe','pipe','inherit'],env:{...process.env,NANOTOX_TITLE:title+' - ego'}});
await new Promise((r,j)=>{proc.stdout.once('data',r);proc.once('exit',code=>j(Error('Recorder stopped '+code)))});
let prev=[120,140];const cues={};const start=Date.now();function mark(k){cues[k]=(Date.now()-start)/1000}
async function click(sel){const l=p.locator(sel),a=await l.boundingBox();if(!a)throw Error(sel);const xy=[a.x+a.width*.5,a.y+a.height*.5];
const g=await p.evaluate(()=>({x:screenX+(outerWidth-innerWidth)/2,y:screenY+outerHeight-innerHeight,d:devicePixelRatio}));
for(let i=1;i<=14;i++){const t=i/14;let x=prev[0]+(xy[0]-prev[0])*t,y=prev[1]+(xy[1]-prev[1])*t;proc.stdin.write(((x+g.x)*g.d)+' '+((y+g.y)*g.d)+'\n');await p.mouse.move(x,y);await wait(12)}
prev=xy;await p.mouse.click(...xy)}
await wait(1200);mark('baseline');await click('#scenario button');await p.waitForFunction(()=>prediction.textContent==='54.09%');await wait(1100);await click('.chips button:nth-child(2)');await wait(1600);mark('input');await click('[name=dose]');await p.keyboard.press('Control+a');await p.keyboard.type('320',{delay:135});await wait(350);await click('#scenario button');await p.waitForFunction(()=>prediction.textContent==='54.76%');await wait(1000);
mark('question');await click('.composer input');for(const ch of '浓度贡献是多少？'){await p.keyboard.insertText(ch);await wait(90)}await p.keyboard.press('Enter');await wait(2100);mark('compare');await click('.chips button:last-child');await wait(2200);
for(const i of [0,1,2,3,5]){mark('tab'+i);await click('[data-tab="'+i+'"]');await wait(2050)}
mark('return');await click('[data-tab="6"]');await wait(1800);fs.writeFileSync('NanoTox-film/ui/cues.json',JSON.stringify(cues));console.log(cues)
}finally{if(proc && proc.exitCode===null){let end=new Promise(r=>proc.once('exit',r));proc.stdin.end('stop\n');await end}await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
