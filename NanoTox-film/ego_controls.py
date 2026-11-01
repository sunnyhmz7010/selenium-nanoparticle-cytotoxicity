from ego_window import *
from ctypes.wintypes import RECT
import time
r=RECT();u.GetWindowRect(h,ctypes.byref(r))
box=(r.left+10,r.top+2,r.right-10,r.bottom-10)
def guard():
    if u.GetForegroundWindow()!=h: raise RuntimeError("Ego lost foreground; capture stopped")
def move(x,y):
    guard();u.SetCursorPos(round(box[0]+x*(box[2]-box[0])/1000),round(box[1]+y*(box[2]-box[0])/1000))
def click(x,y):
    move(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
def key(code):
    guard();u.keybd_event(code,0,0,0);u.keybd_event(code,0,2,0)
def zoom(code):
    guard();u.keybd_event(17,0,0,0);key(code);u.keybd_event(17,0,2,0)
def snap():
    guard();return ImageGrab.grab(bbox=box,all_screens=True)
if __name__=='__main__':
    u.ShowWindow(h,9);u.SetWindowPos(h,0,20,20,1330,920,0x40);u.SetForegroundWindow(h);time.sleep(.4)
    im=snap();im.thumbnail((1000,720));im.save(P/'ego-now.jpg')