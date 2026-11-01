from PIL import ImageGrab
import ctypes
from pathlib import Path
u=ctypes.windll.user32
u.SetProcessDPIAware()
h=u.FindWindowW(None,'NanoTox Assistant · 分析工作台 - ego')
if not h:raise RuntimeError('NanoTox window missing')
P=Path(__file__).resolve().parent
if __name__=='__main__':
    u.ShowWindow(h,9);u.SetWindowPos(h,0,20,20,1330,920,0x40);u.SetForegroundWindow(h)
    import time;time.sleep(.6)
    from ctypes.wintypes import RECT; r=RECT();u.GetWindowRect(h,ctypes.byref(r));print(r.left,r.top,r.right,r.bottom,u.GetForegroundWindow()==h); im=ImageGrab.grab(bbox=(r.left+10,r.top+2,r.right-10,r.bottom-10),all_screens=True);print(im.size);im.thumbnail((1000,720));im.save(P/'ego-inspect.jpg')
