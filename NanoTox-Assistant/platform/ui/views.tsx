import React from "react";
import { renderToStaticMarkup as markup } from "react-dom/server";
import { Button } from "./components/button";
import { Card,CardTitle,CardDescription } from "./components/card";
import { NativeSelect } from "./components/native-select";
import { Input } from "./components/input";
import { Table,TableHeader,TableBody,TableRow,TableCell,TableHead } from "./components/table";
const fields = [
  ["size","粒径 / nm",0.01,1000,"any"],["zeta","Zeta 电位 / mV",-200,200,"any"],
  ["dose","浓度 / μmol·L⁻¹ Se",0,512,"any"],["hours","暴露时长 / h",1,72,1]
] as const;
function Scenario(){return <Card className="formbox"><span className="tag">01　/　SCENARIO</span><CardTitle>设计暴露条件</CardTitle><CardDescription>选择材料原型，编辑 HUVEC 暴露参数。</CardDescription><form id="scenario"><div className="fields"><label className="wide">表面修饰材料<NativeSelect name="material"/></label>{fields.map(([name,label,min,max,step])=><label key={name}>{label}<Input name={name} type="number" required min={min} max={max} step={step}/></label>)}</div><Button className="primary" type="submit">运行预测　→</Button></form><div className="formula">冻结随机森林　·　单样本 Tree SHAP</div></Card>}
function Assistant(){return <Card className="agentbox"><div className="assistant-head"><div><span className="tag">02　/　ASSISTANT</span><CardTitle>实验解释助手</CardTitle></div></div><div className="report"><div><small>预测细胞存活率</small><br/><strong id="prediction">—</strong></div><small id="condition">等待运行</small></div><div className="chatlog" id="chat" aria-live="polite"/><div className="chips">{["为什么得到这个预测？","有对应实测吗？","和上次相比呢？"].map(q=><Button variant="outline" size="xs" type="button" key={q}>{q}</Button>)}</div><form className="composer"><Input aria-label="输入研究问题" placeholder="输入问题：例如，浓度贡献是多少？" maxLength={240}/><Button type="submit" className="primary">发送 ↑</Button></form><div className="formula">本机证据问答 · 回答引用本次推理结果</div></Card>}
export const templates=Object.fromEntries(Object.entries({
  assistant:<div className="studio"><Scenario/><Assistant/></div>,
  nav:<Button variant="ghost" data-tab="INDEX" className="STATE">CAPTION</Button>,
  kpi:<Card className="kpi"><small>LABEL</small><b>VALUE</b></Card>,
  card:<Card className="card"><small>LABEL</small>BODY</Card>,
  table:<Table><TableHeader><TableRow>HEAD</TableRow></TableHeader><TableBody>BODY</TableBody></Table>,
  row:<TableRow className="STATE">CELLS</TableRow>,cell:<TableCell>VALUE</TableCell>,head:<TableHead>VALUE</TableHead>,
  download:<Button variant="outline" id="download">↓　导出当前数据</Button>,
  filters:<div className="filters"><label>材料<NativeSelect id="mat"/></label><label>时间<NativeSelect id="hrs" defaultValue="72">{[24,48,72].map(v=><option key={v}>{v}</option>)}</NativeSelect> h</label><label>浓度<NativeSelect id="dose"/> μmol/L Se</label><span>RF　/　冻结模型</span></div>
}).map(([k,v])=>[k,markup(v)]));
