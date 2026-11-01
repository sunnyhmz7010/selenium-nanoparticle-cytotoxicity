from record_lab import *
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
proc=None
try:
    guard();go(227,251)
    # 屏幕采集原生指针；仅遮盖个人书签文本所在的一行。
    mask_y=round(99*w/1100);mask_h=round(38*w/1100)
    proc=subprocess.Popen([str(F),'-y','-loglevel','error','-f','gdigrab','-framerate','24','-draw_mouse','1','-offset_x',str(box[0]),'-offset_y',str(box[1]),'-video_size',f'{w}x{height}','-i','desktop','-vf',f'drawbox=x=0:y={mask_y}:w=iw:h={mask_h}:color=0xfafafa:t=fill','-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(P/'assistant-take.mp4')],stdin=subprocess.PIPE)
    def hold(t):
        for i in range(round(t*10)):
            guard()
            if proc.poll() is not None:raise RuntimeError('Capture stopped')
            time.sleep(.1)
    hold(2);click(355,317);key(35);key(13);hold(2)
    click(565,317);key(38);key(13);hold(2)
    go(614,638);hold(1);click(90,293);hold(4)
    click(90,345);hold(4);click(90,395);hold(4)
    click(92,447);hold(1);click(468,567);hold(3)
    click(93,499);hold(3);click(91,242);hold(2)
finally:
    if proc:
        proc.communicate(b'q',timeout=25)
        if proc.returncode:raise RuntimeError('FFmpeg capture failed')
    u.SetWindowPos(h,-2,0,0,0,0,3)
