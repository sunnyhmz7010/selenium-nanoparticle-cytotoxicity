from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
import json,re,joblib,pandas as pd
P=Path(__file__).resolve().parent
R=P.parent/"research"
inputs=pd.read_csv(R/"results/huvec_external_20261013_umol_se/model_inputs.csv")
shap=pd.read_csv(R/"results/huvec_external_20261013_umol_se/shap_grouped_values.csv")
model=joblib.load(R/"models/improved_434/baseline_random_forest.joblib")
features=json.loads((R/"models/improved_434/metadata.json").read_text())["baseline_random_forest"]["selected_features"]
html=(P/"workspace.html").read_text(encoding="utf-8")
html=re.sub(r"const data=\[.*?\];let row","let data=[];let row",html,count=1)
html=html.replace("hours.onchange=dose.oninput=draw","async function load(){const time=hours.value;const r=await fetch('/api/predict?h='+time);if(!r.ok)throw Error('预测请求失败');const rows=await r.json();if(hours.value===time){data=rows;draw()}} hours.onchange=()=>load().catch(e=>num.textContent=e.message);dose.oninput=()=>{if(data.some(r=>r.h===+hours.value))draw()}").replace(";draw()</script>",";load().catch(e=>num.textContent=e.message)</script>").replace("查看各剂量的归档预测","查看模型的剂量扫描结果").replace("冻结随机森林归档输出","本机随机森林推理 · SHAP 来自对应归档").replace("交互原型","本地模型服务")
class App(BaseHTTPRequestHandler):
    def do_GET(self):
        uri=urlsplit(self.path)
        if uri.path=="/":
            content=html.encode();mime="text/html; charset=utf-8"
        elif uri.path=="/api/predict" and parse_qs(uri.query).get("h") in (["24"],["72"]):
            hour=int(parse_qs(uri.query)["h"][0]);keys=["nanoparticle","time_h","concentration_reported"]
            selected=inputs[(inputs.nanoparticle=="CS-SeNPs")&(inputs.time_h==hour)&(inputs.concentration_reported>0)].sort_values(keys)
            vals=model.predict(selected[features])
            contributions=selected[keys].merge(shap,on=keys,validate="one_to_one")
            content=json.dumps([dict(d=d,h=hour,v=v,a=a) for d,v,a in zip(selected.concentration_reported,vals,contributions[["Concentration","Time","Zeta potential"]].values.tolist())]).encode();mime="application/json"
        else:
            self.send_error(404);return
        self.send_response(200);self.send_header("Content-Type",mime);self.send_header("Content-Length",str(len(content)));self.end_headers();self.wfile.write(content)
import socket
class LocalServer(ThreadingHTTPServer):
    address_family=socket.AF_INET6
LocalServer(('::1',18764),App).serve_forever()
