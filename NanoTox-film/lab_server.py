"""本地 HUVEC 工作台。以材料、时间、报告浓度配对每条实验记录。"""
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent / "research"
DATA = RESEARCH / "results/huvec_external_20261013_umol_se"
MODELS = RESEARCH / "models/improved_434"
KEY = ["nanoparticle", "time_h", "concentration_reported"]
inputs = pd.read_csv(DATA / "model_inputs.csv")
features = json.loads((MODELS / "metadata.json").read_text())["baseline_random_forest"]["selected_features"]
model = joblib.load(MODELS / "baseline_random_forest.joblib")
rows = pd.read_csv(DATA / "experimental_data.csv")
rows = rows.merge(inputs[KEY].assign(pred=model.predict(inputs[features])), on=KEY, validate="one_to_one")
shap = pd.read_csv(DATA / "shap_grouped_values.csv")
cols = [c for c in shap if c not in KEY]
rows = rows.merge(shap, on=KEY, validate="one_to_one").merge(pd.read_csv(DATA / "shap_additivity_check.csv")[KEY+["base_value"]], on=KEY, validate="one_to_one")
archive = pd.read_csv(DATA / "model_predictions.csv")
audit = rows.merge(archive, on=KEY, validate="one_to_one")
if len(audit)!=351 or not np.allclose(audit.pred, audit.predicted_viability_percent,atol=1e-8,rtol=0) or not np.allclose(rows.pred,rows.base_value+rows[cols].sum(axis=1),atol=1e-8,rtol=0):
    raise ValueError("预测或解释配对校验失败")
ic = pd.read_csv(DATA / "experimental_ic50.csv").merge(pd.read_csv(DATA / "model_ic50.csv")[KEY[:2]+["ic50_display"]],on=KEY[:2],suffixes=("", "_model"),validate="one_to_one")
payload = json.dumps(dict(rows=json.loads(rows.to_json(orient="records")), ic=json.loads(ic.to_json(orient="records")),features=cols), allow_nan=False).encode()
class App(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=="/": content=(HERE/"lab.html").read_bytes(); mime="text/html; charset=utf-8"
        elif self.path=="/api/analysis": content=payload; mime="application/json"
        else: self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type",mime);self.send_header("Content-Length",str(len(content)));self.end_headers();self.wfile.write(content)
class Loopback(ThreadingHTTPServer):
    address_family=socket.AF_INET6
if __name__=="__main__": Loopback(("::1",18765),App).serve_forever()
