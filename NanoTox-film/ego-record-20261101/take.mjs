const fs=await import('node:fs/promises');
const path=await import('node:path');
const out=path.dirname((await import('node:url')).fileURLToPath(import.meta.url));
const task=await taskSpace(3),p=task.page('p1');
await p.reload();
await p.waitForFunction(()=>document.querySelector('#num').textContent.includes('%'));
const start=Date.now(), frames=[];let running=true;
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function capture(){
  while(running){
    const shot=await p.cdp('Page.captureScreenshot',{format:'jpeg',quality:88,fromSurface:true});
    const name='live-'+String(frames.length).padStart(4,'0')+'.jpg';
    const ts=(Date.now()-start)/1000;
    await fs.writeFile(path.join(out,name),Buffer.from(shot.data,'base64'));
    frames.push({name,ts});await wait(55);
  }
}
const recording=capture();
try{
  await wait(2600);await p.selectOption('#hours','72');
  await p.waitForFunction(()=>document.querySelector('#num').textContent==='92.97%');
  await wait(1800);
  const r=await p.evaluate(()=>{let a=document.querySelector('#dose').getBoundingClientRect();return {x:a.x,y:a.y+a.height/2,w:a.width}});
  await p.mouse.move(r.x+8,r.y,{label:'选择暴露浓度'});await p.mouse.down();
  for(let i=1;i<=24;i++){await p.mouse.move(r.x+8+(r.w-16)*i/24,r.y,{label:'调整暴露浓度'});await wait(100)}
  await p.mouse.up();await p.waitForFunction(()=>document.querySelector('#num').textContent==='54.09%');
  await wait(2500);await p.click('text="因素解释"',{label:'查看因素贡献'});await wait(3500);
  await p.click('text="解释助手"',{label:'打开解释助手'});await wait(1200);
  await p.click('#ask',{label:'询问模型侧 IC50'});await wait(5500);
  console.log(await p.snapshot());
}finally{running=false;await recording;
  await fs.writeFile(path.join(out,'frames.txt'),frames.map((f,i)=>"file '"+f.name+"'\nduration "+((frames[i+1]?.ts??f.ts+.1)-f.ts).toFixed(3)).join('\n')+"\nfile '"+frames.at(-1).name+"'\n");
}
