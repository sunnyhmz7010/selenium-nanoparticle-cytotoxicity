from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,math
from studio_score import score
P=Path(__file__).resolve().parent;D=P/'studio-master';D.mkdir(exist_ok=True)
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
fps=25;beat=12;W,H=1798,1080
def ff(*args):subprocess.run([str(F),'-y','-loglevel','error',*map(str,args)],check=True)
# 每拍 12 帧。操作镜头保留浏览器采集的全幅。
seq=[('title',0,4),(.3,2.6,5),(3,2.25,4),('dose',0,2),(5.25,2.65,5),(7.90,3.50,7),(11.40,2.65,6),('archive',0,2),(14.1,2.05,4),(16.8,1.98,4),(19.35,1.96,4),(22.0,2.0,4),(24.9,2,4),(28.25,1.52,3),('end',0,4)]
def font(sz,f):return ImageFont.truetype('C:/Windows/Fonts/'+f,sz)
def title_frame(kind,i,n):
    im=Image.new('RGB',(W,H),'#112d35');d=ImageDraw.Draw(im);lift=round(26*(1-min(1,i/6))**2)
    def text(x,y,s,z,f='msyhbd.ttc',color='#e9f4eb'):d.text((x,y+lift),s,font=font(z,f),fill=color,anchor='lt')
    ey,main,sub={'title':('01    /    SCENARIO','NanoTox Assistant','改变一个实验条件，预测会变多少？'),'dose':('02    /    NEW DOSE','512   →   320','μmol/L Se     ·     72 h'),'archive':('03    /    EVIDENCE','回到实测。','剂量曲线   /   材料对比   /   IC50   /   模型解释'),'end':('NANOTOX    /    ASSISTANT','输入 · 预测 · 追问','纳米硒细胞毒性分析工作台')}[kind]
    text(98,98,ey,30,'bahnschrift.ttf','#9dcebd');d.line((100,170,1695,170),fill='#32665f',width=2)
    text(86,347,main,125,'georgia.ttf' if kind in ('title','dose') else 'msyhbd.ttc')
    text(99,565,sub,47,'msyh.ttc','#a8ebc9')
    for j in range(56):
        x=100+j*29;height=(14+54*abs(math.sin(j*.19+i*.09))*abs(math.cos(j*.12)))*(1 if j*2<i+38 else .4)
        d.rectangle((x,878-height,x+6,878),fill='#528d81' if j%4 else '#a8ebc9')
    return im
for i,(start,length,beats) in enumerate(seq):
    n=beats*beat;out=D/f'{i:02}.mp4';opts=['-frames:v',str(n),'-an','-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p',str(out)]
    if isinstance(start,str):
        enc=subprocess.Popen([str(F),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-video_size',f'{W}x{H}','-framerate','25','-i','-',*opts],stdin=subprocess.PIPE)
        for j in range(n):enc.stdin.write(title_frame(start,j,n).tobytes())
        enc.stdin.close()
        if enc.wait():raise RuntimeError('title encoding failed')
    else:ff('-ss',start,'-t',length,'-i',P/'studio-source.mp4','-vf',f'setpts={n/(fps*length):.9f}*(PTS-STARTPTS),fps=25,tpad=stop_mode=clone:stop_duration=0.5,setsar=1',*opts)
(D/'clips.txt').write_text(''.join(f"file '{i:02}.mp4'\n" for i in range(len(seq))),encoding='ascii')
duration=sum(x[2] for x in seq)*.48
for mus,suffix in [(True,'节奏版'),(False,'无配乐版')]:
    a=D/('score.wav' if mus else 'cues.wav');score(a,duration,music=mus)
    ff('-f','concat','-safe','0','-i',D/'clips.txt','-i',a,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',P/('NanoTox-Studio-'+suffix+'.mp4'))
print(duration)
