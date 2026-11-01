const t=await taskSpace(5),p=t.page('p1');
await p.goto('http://[::1]:18765/');
await p.waitForFunction(()=>document.querySelectorAll('#mat option').length===9);
const checks=await p.evaluate(()=>{
  const errors=[];
  for(const m of mat.options)for(const h of hrs.options)for(const d of dose.options){
    mat.value=m.value;hrs.value=h.value;dose.value=d.value;render();
    if(!kpis.textContent.includes('%')||kpis.textContent.includes('NaN'))errors.push([m.value,h.value,d.value]);
  }
  const panels=[];
  for(let i=0;i<6;i++){document.querySelector('[data-tab="'+i+'"]').click();panels.push(document.querySelector('#panel h2').textContent)}
  return {conditions:mat.length*hrs.length*dose.length,panels,errors};
});
console.log(checks);
const download=p.waitForEvent('download',{timeout:10000});
await p.click('#download');
const item=await download;
const output=(await import('node:url')).fileURLToPath(new URL('./export-check.csv',import.meta.url));
await item.saveAs(output);
console.log('export lines',(await (await import('node:fs/promises')).readFile(output,'utf8')).trim().split(/\r?\n/).length);
await t.finish({keep:[]});
