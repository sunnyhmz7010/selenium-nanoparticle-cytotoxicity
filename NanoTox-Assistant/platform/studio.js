let current=null,previous=null,requestId=0,conversation=[],draft=null;
function initial(){const r=selection().r;return {material:r.nanoparticle,dose:r.concentration_reported,hours:r.time_h,size:r.size_nm,zeta:r.zeta_mV}}
function studioView(){const x=draft||initial();
panel.innerHTML=UI.assistant;
const f=document.querySelector('#scenario');f.elements.material.innerHTML=[...new Set(data.rows.map(i=>i.nanoparticle))].map(m=>'<option>'+m+'</option>').join('');for(const [k,v] of Object.entries(x))f.elements[k].value=v;
function dirty(){requestId++;draft=Object.fromEntries(new FormData(f));if(current)previous=current;current=null;conversation=[];paintChat()}
f.oninput=e=>{if(e.target.name==='material'){const row=data.rows.find(r=>r.nanoparticle===e.target.value);f.elements.size.value=row.size_nm;f.elements.zeta.value=row.zeta_mV}dirty()};
f.onsubmit=async e=>{e.preventDefault();const x=Object.fromEntries(new FormData(f));const id=++requestId;if(current)previous=current;draft=x;current=null;conversation=[];paintChat();prediction.textContent='计算中';try{const resp=await fetch('/api/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(x)});const v=await resp.json();if(!resp.ok)throw Error(v.error||'推理失败');if(id!==requestId)return;current={...v,x};conversation=[['assistant','已计算 '+x.material+' 的预测。可以询问贡献、实测、浓度换算，或比较上一次运行。']]}catch(err){if(id!==requestId)return;conversation=[['assistant','计算失败：'+err.message]]}if(tab===6)paintChat()};
const form=panel.querySelector('.composer');form.onsubmit=e=>{e.preventDefault();ask(form.querySelector('input').value.trim());form.reset()};panel.querySelectorAll('.chips button').forEach(b=>b.onclick=()=>ask(b.textContent));paintChat()}
function paintChat(){const num=document.querySelector('#prediction');if(!num)return;num.textContent=current?fmt(current.pred)+'%':'—';condition.textContent=current?current.x.hours+' h　/　'+current.x.dose+' μmol/L Se':'等待运行';chat.replaceChildren();for(const [role,text] of conversation.length?conversation:[['assistant','先运行一个实验条件，再问我这个结果意味着什么。']]){const b=document.createElement('div');b.className='bubble '+role;b.textContent=(role==='user'?'你　':'Assistant　')+text;chat.append(b)}chat.scrollTop=chat.scrollHeight}
function ask(q){if(!q)return;let answer;if(!current)answer='请先运行预测，我会依据这个样本回答。';else{const c=current,x=c.x,a=Object.entries(c.attrs).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1]));const name=k=>cn[names.indexOf(k)]||k;
if(/上次|上一次|前一次|相比|两次/.test(q))answer=previous?'上次为 '+fmt(previous.pred)+'%，本次为 '+fmt(c.pred)+'%，变化 '+sg(c.pred-previous.pred)+' 个百分点。':'目前只有一次运行。修改条件再运行后即可比较。';
else if(/实测|实验值|误差|验证/.test(q))answer=c.obs===null?'归档中没有材料、粒径、电位、剂量和时长完全匹配的实测记录，因此当前结果不能计算实验误差。':'完全匹配的实测存活率为 '+fmt(c.obs)+'%，预测为 '+fmt(c.pred)+'%，差值 '+sg(c.pred-c.obs)+' 个百分点。';
else if(/换算|质量浓度|单位/.test(q))answer=x.dose+' μmol/L Se × 0.078971 = '+fmt(x.dose*.078971,4)+' μg/mL，这是模型使用的质量浓度。';
else if(/ic\s*50|半抑制/i.test(q))answer='单个剂量的预测无法定位 IC50。可在左侧「IC50 分析」查看归档实验的完整剂量曲线与插值括区。';
else if(/贡献|解释|为什么|因素|影响|浓度|粒径|电位|shap/i.test(q)){let k=/浓度/.test(q)?'Concentration':/粒径/.test(q)?'Particle size':/电位/.test(q)?'Zeta potential':a[0][0];answer='模型基线为 '+fmt(c.base)+'%。'+name(k)+'的 SHAP 贡献为 '+sg(c.attrs[k])+' 个百分点；加上其他特征后得到 '+fmt(c.pred)+'%。贡献描述模型输出。'}
else if(/存活|预测|结果/.test(q))answer='本次输入 '+x.size+' nm、'+x.zeta+' mV、'+x.dose+' μmol/L Se、'+x.hours+' h，预测存活率为 '+fmt(c.pred)+'%。';
else answer='这条问题暂时无法从当前记录回答。你可以追问实测误差、某项 SHAP 贡献、剂量单位换算或与上次预测的差异。'}
conversation.push(['user',q],['assistant',answer]);paintChat()}
