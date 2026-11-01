"""在归档分析服务上增加单样本推理与 Tree SHAP 解释。"""
import sys
import json
import numpy as np
import shap as tree_shap
from lab_server import App, Loopback, HERE, RESEARCH, model, features, rows
sys.path.insert(0, str(RESEARCH / "scripts"))
from run_huvec_external import build_inputs, shap_groups
prep = model.named_steps["preprocess"]
explainer = tree_shap.TreeExplainer(model.named_steps["model"], feature_perturbation="tree_path_dependent")
groups = shap_groups(list(prep.get_feature_names_out()))
def predict(x):
    m=x["material"]
    if m not in rows.nanoparticle.values: raise ValueError("请选择已支持的材料")
    size,zeta,dose,h=(float(x[k]) for k in ("size","zeta","dose","hours"))
    if not (0<size<=1000 and -200<=zeta<=200 and 0<=dose<=512 and 1<=h<=72 and h.is_integer()): raise ValueError("输入值超出本工作台支持范围")
    frame=build_inputs([dict(nanoparticle=m,size_nm=size,zeta_mV=zeta,concentration_reported=dose,time_h=h,cell_type="HUVEC")],.078971,features)
    val=float(model.predict(frame)[0]); sv=np.asarray(explainer.shap_values(prep.transform(frame))).reshape(-1)
    base=float(np.ravel(explainer.expected_value)[0]);a={k:float(sv[idx].sum()) for k,idx in groups.items()}
    if not np.isclose(base+sum(a.values()),val,rtol=0,atol=1e-6):raise RuntimeError("SHAP 加和校验失败")
    match=rows[(rows.nanoparticle==m)&(rows.time_h==h)&(rows.concentration_reported==dose)&(rows.size_nm==size)&(rows.zeta_mV==zeta)]
    return dict(pred=val,base=base,attrs=a,obs=None if match.empty else float(match.iloc[0].viability_percent))
class Studio(App):
    def do_GET(self):
        assets={"/":"studio.html","/studio.css":"studio.css","/studio.js":"studio.js"}
        if self.path not in assets:return super().do_GET()
        p=HERE/assets[self.path];b=p.read_bytes();self.send_response(200);self.send_header("Content-Type",{".html":"text/html",".css":"text/css",".js":"text/javascript"}[p.suffix]+"; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_POST(self):
        if self.path!="/api/predict":return self.send_error(404)
        try:
            n=int(self.headers.get("Content-Length","0"))
            if not 0<n<4096:raise ValueError("请求长度无效")
            result=predict(json.loads(self.rfile.read(n)));status=200
        except (TypeError,KeyError,ValueError) as e:result={"error":str(e)};status=400
        b=json.dumps(result,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
if __name__=="__main__":Loopback(("::1",18766),Studio).serve_forever()
