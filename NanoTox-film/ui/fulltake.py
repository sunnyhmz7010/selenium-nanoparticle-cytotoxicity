import ctypes as C,os,sys
from pathlib import Path
p=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(p))
h=C.windll.user32.FindWindowW(None,os.environ['NANOTOX_TITLE']);print('Window',h,flush=True)
if not h:raise RuntimeError('Dedicated window missing')
os.environ['NANOTOX_HWND']=str(h)
from studio_native import *
try:preview()
finally:u.SetWindowPos(h,-2,0,0,0,0,3)
