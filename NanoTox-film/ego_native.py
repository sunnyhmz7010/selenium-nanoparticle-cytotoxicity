from ego_window import *
from ctypes.wintypes import RECT
from PIL import Image
g=ctypes.windll.gdi32
def native():
    r=RECT();u.GetWindowRect(h,ctypes.byref(r));w=r.right-r.left;v=r.bottom-r.top
    dc=u.GetWindowDC(h);m=g.CreateCompatibleDC(dc);b=g.CreateCompatibleBitmap(dc,w,v);old=g.SelectObject(m,b)
    try:
        if not u.PrintWindow(h,m,2):raise RuntimeError('Window capture failed')
        buf=ctypes.create_string_buffer(w*v*4);g.GetBitmapBits(b,len(buf),buf)
        return Image.frombytes('RGB',(w,v),buf.raw,'raw','BGRX').crop((10,2,w-10,v-10))
    finally:
        g.SelectObject(m,old);g.DeleteObject(b);g.DeleteDC(m);u.ReleaseDC(h,dc)
if __name__=='__main__':
    im=native();im.thumbnail((1000,720));im.save(P/'ego-native.jpg')
