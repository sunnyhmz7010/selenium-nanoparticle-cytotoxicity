from studio_native import *
from ctypes import wintypes as wt
import json
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
class K(C.Structure):_fields_=[('vk',wt.WORD),('scan',wt.WORD),('flags',wt.DWORD),('tm',wt.DWORD),('extra',C.c_size_t)]
class M(C.Structure):_fields_=[('x',wt.LONG),('y',wt.LONG),('data',wt.DWORD),('flags',wt.DWORD),('tm',wt.DWORD),('extra',C.c_size_t)]
class U(C.Union):_fields_=[('key',K),('mouse',M)]
class I(C.Structure):_fields_=[('type',wt.DWORD),('u',U)]
def type_text(text):
    for c in text:
        guard()
        for flags in (4,6):
            item=I(1,U(key=K(0,ord(c),flags,0,0)))
            if u.SendInput(1,C.byref(item),C.sizeof(item))!=1:raise RuntimeError('Input failed')
        time.sleep(.055)
proc=None
try:
    guard();go(314,427);time.sleep(.3)
    proc=subprocess.Popen([str(F),'-y','-loglevel','error','-f','gdigrab','-framerate','25','-draw_mouse','1','-offset_x',str(box[0]),'-offset_y',str(box[1]),'-video_size',f'{w}x{height}','-i','desktop','-vf',f'drawbox=x=0:y={round(51*w/1100)}:w=iw:h={round(23*w/1100)}:color=0xfafafa:t=fill,scale=-2:1080','-c:v','h264_nvenc','-b:v','8M','-pix_fmt','yuv420p','-movflags','+faststart',str(P/'studio-source.mp4')],stdin=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    def rest(t):time.sleep(t);guard()
    rest(1.4);click(315,427);rest(1.3);click(647,424);rest(2)
    click(225,389);chord(17,65);type_text('320');click(317,426);rest(1.1)
    click(641,454);type_text('浓度贡献是多少？');key(13);rest(2.4)
    click(752,424);rest(2)
    for y in [200,236,272,307,379]:
        click(75,y);rest(2.4)
    click(60,152);rest(1.9)
finally:
    if proc:proc.communicate(b'q',timeout=25)
    u.SetWindowPos(h,-2,0,0,0,0,3)
