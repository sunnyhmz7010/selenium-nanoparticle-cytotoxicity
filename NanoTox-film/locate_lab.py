import ctypes as c
from ctypes import wintypes as w
u=c.windll.user32;u.SetProcessDPIAware()
@c.WINFUNCTYPE(c.c_bool,w.HWND,w.LPARAM)
def enum(h,l):
 b=c.create_unicode_buffer(512);u.GetWindowTextW(h,b,512)
 if "NanoTox Assistant | 分析工作台" in b.value:
  cloak=w.DWORD();c.windll.dwmapi.DwmGetWindowAttribute(h,14,c.byref(cloak),4);r=w.RECT();u.GetWindowRect(h,c.byref(r));print(h,repr(b.value),u.IsWindowVisible(h),cloak.value,(r.left,r.top,r.right,r.bottom))
 return True
u.EnumWindows(enum,0)