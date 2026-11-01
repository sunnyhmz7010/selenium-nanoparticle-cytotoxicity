import ctypes as C,time,subprocess,sys,math
from ctypes.wintypes import RECT,POINT
from pathlib import Path
from PIL import ImageGrab
P=Path(__file__).resolve().parent
u=C.windll.user32
u.SetProcessDPIAware()
h=u.FindWindowW(None,"NanoTox Assistant · 预测与解释 - ego")
import os
h=int(os.environ.get('NANOTOX_HWND',h))
if not h:raise RuntimeError("Missing NanoTox Assistant native window")
u.ShowWindow(h,3)
W=min(1660,u.GetSystemMetrics(0)-32);H=min(1020,u.GetSystemMetrics(1)-48)
u.SetWindowPos(h,-1,0,0,0,0,0x43)
fg=u.GetForegroundWindow();tid=u.GetWindowThreadProcessId(fg,None);self_tid=C.windll.kernel32.GetCurrentThreadId();linked=u.AttachThreadInput(self_tid,tid,True) if tid!=self_tid else False
u.BringWindowToTop(h);u.SetForegroundWindow(h)
if linked:u.AttachThreadInput(self_tid,tid,False)
time.sleep(2.0)
r=RECT();u.GetWindowRect(h,C.byref(r));box=(max(0,r.left),max(0,r.top),min(u.GetSystemMetrics(0),r.right),min(u.GetSystemMetrics(1),r.bottom))
w=(box[2]-box[0])//2*2;height=(box[3]-box[1])//2*2
def preview():
    im=ImageGrab.grab(bbox=box,all_screens=True);im.thumbnail((1100,900));im.save(P/'studio-controls.jpg');print(box,w,height,im.size)
def pos(x,y):return round(box[0]+x*w/1100), round(box[1]+y*w/1100)
def guard():
    if u.GetForegroundWindow()!=h:raise RuntimeError("Recording interrupted: foreground changed")
def go(x,y):
    guard();a,b=pos(x,y);pt=POINT();u.GetCursorPos(C.byref(pt))
    for i in range(1,17):
        t=(1-math.cos(math.pi*i/16))/2;u.SetCursorPos(round(pt.x+(a-pt.x)*t),round(pt.y+(b-pt.y)*t));time.sleep(.018)
def click(x,y):
    go(x,y);u.mouse_event(2,0,0,0,0);time.sleep(.10);u.mouse_event(4,0,0,0,0)
def key(k):guard();u.keybd_event(k,0,0,0);u.keybd_event(k,0,2,0)
def chord(ctrl,k):guard();u.keybd_event(ctrl,0,0,0);key(k);u.keybd_event(ctrl,0,2,0)
if __name__=='__main__':
    try:preview()
    finally:u.SetWindowPos(h,-2,0,0,0,0,3)
