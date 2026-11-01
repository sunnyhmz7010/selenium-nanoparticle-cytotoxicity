from pathlib import Path
import subprocess,json
P=Path(__file__).resolve().parent
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
probe=F.with_name('ffprobe.exe')
rec=P/'browser-recording.webm'
def duration(path):
    return float(subprocess.check_output([str(probe),'-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)]))
from window_frame import make_window
make_window()
end=duration(rec)
vf='[0:v]trim=start=1:end=5,setpts=PTS-STARTPTS,fps=24,setsar=1[a];[1:v]trim=start=0.35,setpts=PTS-STARTPTS,fps=24,scale=1152:648,setsar=1[screen];[2:v][screen]overlay=64:48:shortest=1,fps=24,setsar=1[b];[0:v]trim=start=72:end=76,setpts=PTS-STARTPTS,fps=24,setsar=1[c];[a][b][c]concat=n=3:v=1:a=0[v]'
for src,name in [('NanoTox','NanoTox-Window'),('NanoTox-no-music','NanoTox-Window-no-music')]:
    dur=end-.35+8
    subprocess.run([str(F),'-y','-loglevel','error','-i',str(P/(src+'.mp4')),'-i',str(rec),'-loop','1','-framerate','24','-i',str(P/'browser-window.png'),'-filter_complex',vf,'-map','[v]','-map','0:a','-af',f'atrim=duration={dur},afade=t=out:st={dur-2}:d=2','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(P/(name+'.mp4'))],check=True)
    print(name,duration(P/(name+'.mp4')))
