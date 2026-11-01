from pathlib import Path
import subprocess,json,math,csv,wave
import numpy as np
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parent
O=P/'assistant-edit';O.mkdir(exist_ok=True)
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
def run(*args):subprocess.run([str(F),'-y','-loglevel','error',*map(str,args)],check=True)
paper='#f2f1e8'; dark='#10392f';green='#297150';muted='#577565';orange='#b86139';cream='#fcf8e9'
def font(size,k):return ImageFont.truetype('C:/Windows/Fonts/'+dict(c='msyh.ttc',b='msyhbd.ttc',e='georgia.ttf',i='georgiai.ttf',m='bahnschrift.ttf')[k],size)
def drawtext(d,x,y,s,n,k='c',col=dark):d.text((x,y),s,font=font(n,k),fill=col,anchor='lt')
rows=list(csv.DictReader((P.parent/'research/results/huvec_external_20261013_umol_se/experimental_data.csv').open()))
obs=[float(r['viability_percent']) for r in rows if r['nanoparticle']=='TW80-SeNPs' and r['time_h']=='72' and float(r['concentration_reported'])>0]
def art(idx,typ,ey,title,number,lines):
    full=typ=='card';im=Image.new('RGB',(1920,1080),dark if full else paper);d=ImageDraw.Draw(im)
    if full:
        drawtext(d,90,75,'NanoTox Assistant',40,'e',cream);drawtext(d,1430,82,'RESEARCH  /  FILM     01',25,'m','#b0cdb8');d.line((90,150,1830,150),fill='#68917b')
        drawtext(d,91,251,ey,28,'m','#9bd2af');drawtext(d,85,345,title,78,'b',cream)
        drawtext(d,91,510,number,67,'e','#b5dec4')
        for j,l in enumerate(lines):drawtext(d,93,670+j*68,l,39,'c',cream)
        # 实测点构成右侧实验曲线纹样，底边留出署名。
        coords=[(1180+i*55,820-v*3.75) for i,v in enumerate(obs)]
        for y in (400,550,700,850):d.line((1160,y,1800,y),fill='#36604d')
        d.line(coords,fill='#b8dbbe',width=4)
        for x,y in coords:d.ellipse((x-6,y-6,x+6,y+6),fill='#e6a57e')
        drawtext(d,1190,885,'TW80-SeNPs    /    HUVEC    /    72 h',23,'m','#abcdba')
    else:
        drawtext(d,35,27,'NanoTox Assistant',31,'e');drawtext(d,1490,32,'APPLICATION FILM    /    01',21,'m',muted);d.line((32,75,1888,75),fill='#a4b6a5')
        x=1471;drawtext(d,x,166,ey,24,'m',green);drawtext(d,x,247,title,45,'b');d.rectangle((x,340,x+58,345),fill=orange)
        drawtext(d,x,395,number,43,'e',green)
        for j,l in enumerate(lines):drawtext(d,x,500+j*59,l,29,'c',dark)
        drawtext(d,x,912,'EGO  /  实际操作',23,'m',muted)
    path=O/f'plate-{idx}.png';im.save(path);return path
# 时间段映射至此次原生窗口录屏。
seq=[
('card',0,4.8,'FIELD NOTE   /   01','模型与实验，相差多少？','NanoTox Assistant',['从一组纳米硒细胞实验开始。']),
('live',0,8.56,'01   /   DOSE RESPONSE','对照两条曲线','72 h',['选择材料与剂量。','绿色为预测值，','橙色为实测值。']),
('live',8.56,4.44,'02   /   COMPARISON','放在一起比较','256 μmol/L',['固定时间与浓度，','比较九种材料的','预测与实验排序。']),
('card',0,4.8,'FIELD NOTE   /   02','这处偏差有多大？','56.03%   /   28.33%',['TW80-SeNPs 的模型预测比实测值','高出 27.70 个百分点。']),
('live',13,4.40,'03   /   THRESHOLD','检查半抑制浓度','14.30 μmol/L',['72 小时实验曲线','可插值得到 IC50。','模型侧仍为 >512。']),
('live',17.40,4.44,'04   /   ATTRIBUTION','解释模型输出','−16.49 pp',['该条件下，浓度','让预测值相对基线','降低 16.49 个百分点。']),
('live',21.84,4.84,'05   /   QUESTIONS','按条件追问','IC50',['点击问题，查看','由当前实验条件','生成的规则回答。']),
('live',26.68,3.44,'06   /   EVIDENCE','回到配对记录','13 doses',['逐行核对浓度、','观测值和预测值。','当前数据可导出。']),
('card',0,3.8,'END NOTE   /   03','从预测，回到实验。','NanoTox Assistant',['纳米硒细胞毒性分析工作台']) ]
def render():
    for i,(typ,start,dur,*words) in enumerate(seq):
        bg=art(i,typ,*words);n=round(dur*25);dst=O/f'clip-{i}.mp4'
        args=['-loop','1','-framerate','25','-i',bg]
        if typ=='live':
            args+=['-ss',start,'-i',P/'assistant-take.mp4','-filter_complex','[1:v]fps=25,scale=1400:940:force_original_aspect_ratio=decrease,setsar=1,tpad=stop_mode=clone:stop_duration=1[screen];[0:v][screen]overlay=32:100']
        else:args+=['-vf',f'fade=t=in:st=0:d=0.24,fade=t=out:st={dur-.22}:d=0.22']
        run(*args,'-frames:v',n,'-an','-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p',dst)
    (O/'cuts.txt').write_text(''.join("file 'clip-%d.mp4'\n"%i for i in range(len(seq))),encoding='ascii')
    dur=sum(round(s[2]*25)/25 for s in seq);sr=32000;t=np.arange(round(dur*sr))/sr;sfx=np.zeros_like(t);pos=0
    for i,s in enumerate(seq):
        tt=t-pos;mask=(tt>=0)&(tt<.75);a=tt[mask];sfx[mask]+=.07*np.sin(2*np.pi*(392 if s[0]=='live' else 261.6)*a)*np.exp(-a*8)*np.minimum(a*180,1);pos+=round(s[2]*25)/25
    with wave.open(str(O/'cues.wav'),'wb') as f:f.setparams((1,2,sr,0,'NONE',''));f.writeframes((sfx*32767).astype('<i2').tobytes())
    for music,suffix in [(True,'比赛版'),(False,'无配乐版')]:
        args=['-f','concat','-safe','0','-i',O/'cuts.txt','-i',O/'cues.wav']
        if music: args+=['-i',P/'NanoTox.mp4','-filter_complex',f'[2:a]atrim=duration={dur},afade=t=out:st={dur-2}:d=2[bg];[bg][1:a]amix=inputs=2:normalize=0[a]','-map','[a]']
        else:args+=['-map','1:a']
        run(*args,'-map','0:v','-c:v','copy','-c:a','aac','-b:a','160k','-movflags','+faststart',P/f'NanoTox-Assistant-{suffix}.mp4')
if __name__=='__main__':render()
