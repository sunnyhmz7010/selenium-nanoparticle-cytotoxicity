# 结果网页

网页读取 `data/dashboard.json`，由 `scripts/build_manifest.py` 在实验结果生成后同步。浏览器需要通过静态 HTTP 服务访问。

```powershell
python -m http.server 8000 --directory web
```

打开 <http://localhost:8000> 查看当前结果。
