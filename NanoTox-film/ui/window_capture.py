import ctypes as C,sys,time,subprocess,os
from pathlib import Path
from ctypes.wintypes import RECT,POINT
P=Path(__file__).resolve().parents[1]
u=C.windll.user32;u.SetProcessDPIAware()
h=u.FindWindowW(None,os.environ["NANOTOX_TITLE"])
if not h:raise RuntimeError("Missing dedicated window")
u.ShowWindow(h,3);u.SetWindowPos(h,-1,0,0,0,0,0x43);u.SetForegroundWindow(h)
f=next(Path("C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages").glob("Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe"))
proc=subprocess.Popen([str(f),"-y","-loglevel","error","-filter_complex",f"gfxcapture=hwnd={h}:capture_cursor=1:max_framerate=25,hwdownload,format=bgra,scale=-2:1080,fps=25","-c:v","h264_nvenc","-b:v","8M","-pix_fmt","yuv420p","-movflags","+faststart",str(P/"shadcn-source.mp4")],stdin=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
print("READY",flush=True)
try:
    for cmd in sys.stdin:
        if cmd.strip()=="stop":break
        x,y=map(float,cmd.split());u.SetCursorPos(round(x),round(y))
finally:
    proc.communicate(b"q",timeout=20);u.SetWindowPos(h,-2,0,0,0,0,3)
    if proc.returncode:raise RuntimeError('Capture failed')
