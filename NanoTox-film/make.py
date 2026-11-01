from pathlib import Path
import csv,json,math,subprocess,wave,functools
import numpy as np
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parent
R=P.parent/'research/results/huvec_external_20261013_umol_se'
rows=list(csv.DictReader((R/'model_predictions.csv').open()))
case=[r for r in rows if r['nanoparticle']=='CS-SeNPs' and r['time_h']=='72' and float(r['concentration_reported'])>0]
dose=[float(r['concentration_reported']) for r in case]
vals=[float(r['predicted_viability_percent']) for r in case]
W,H=1280,720
ink='#132f30'; jade='#007d74'; paper='#f5f2e9'; soft='#506764'; orange='#b34d27'; dark='#102e30'; cream='#faf6e9'
@functools.lru_cache(None)
def font(size,kind):
    return ImageFont.truetype('C:/Windows/Fonts/'+{'c':'msyh.ttc','b':'msyhbd.ttc','s':'georgia.ttf','i':'georgiai.ttf','m':'bahnschrift.ttf'}[kind],size)
def txt(d,x,y,s,n=24,color=ink,k='c'):
    d.text((x,y),str(s),font=font(n,k),fill=color,anchor='lt')
def ease(t):
    t=min(max(t,0),1);return t*t*(3-2*t)
def lerp(a,b,t):return a+(b-a)*t
def sphere(d,cx,cy,r,t,light):
    pts=[]
    for j in range(340):
        y=1-2*(j+.5)/340; a=j*2.399963+t*.16; rad=math.sqrt(1-y*y);x=rad*math.cos(a);z=rad*math.sin(a)
        xx=x*.94-y*.33;yy=y*.94+x*.33
        pts.append((z,cx+r*xx,cy+r*yy))
    for z,x,y in sorted(pts):
        f=(z+1)/2; col=tuple(int(lerp(a,b,f**1.5)) for a,b in zip((25,63,61) if light else (198,210,195),(169,238,202) if light else (14,104,89)));q=1+f*2.5
        d.ellipse((x-q,y-q,x+q,y+q),fill=col)
cuts=[0,9,20,38,51,69,78]
subs=['一条剂量曲线，能告诉我们什么？','选择壳聚糖修饰纳米硒，观察人脐静脉内皮细胞。','固定暴露时间，沿正浓度梯度读取模型预测。','在最高测试浓度下，暴露浓度是主要负向贡献项。','助手依据当前曲线作答，保留模型判断的边界。','NanoTox Assistant   ·   纳米硒毒性预测与解释']
def frame(t):
    i=min(5,next((j for j in range(6) if t<cuts[j+1]),5));u=t-cuts[i];night=i in (0,3,5); fg=cream if night else ink; dim='#a7bfb4' if night else soft
    im=Image.new('RGB',(W,H),dark if night else paper);d=ImageDraw.Draw(im)
    txt(d,54,35,'N / T',25,fg,'s');txt(d,146,42,'NANOTOX   /   RESEARCH SERIES',15,dim,'m');txt(d,984,39,'交互原型演示     /     '+str(i+1).zfill(2),17,dim)
    d.line((54,79,1226,79),fill=dim)
    if i in (0,5):
        sphere(d,935,354,187+10*ease(u/5),t,True)
        txt(d,63,162,'SELENIUM   /   PARTICLE STUDIES',21,'#8dd7bd','m')
        txt(d,58,225,'NanoTox',107,cream,'s');txt(d,69,349,'Assistant',67,'#9cdcc2','i')
        txt(d,67,473,'从一个样本开始' if i==0 else '让预测保留边界',35,cream)
        txt(d,67,533,'SeNPs    /    HUVEC    /    72 h',21,dim,'m')
    if i==1:
        txt(d,58,113,'01    /    SPECIMEN',20,jade,'m');txt(d,56,163,'选择实验条件',51,ink,'b')
        sphere(d,324,425,135,t,False)
        d.rounded_rectangle((576,170,1208,590),18,fill='#fffdf6',outline='#c4cdc1',width=2)
        txt(d,611,204,'样本档案',27);txt(d,610,266,'CS-SeNPs',55,ink,'s')
        for j,(a,b) in enumerate([('表面修饰','壳聚糖'),('细胞类型','HUVEC'),('暴露时间','72 h')]):
            y=354+j*53;d.line((610,y-12,1164,y-12),fill='#d6ded2');txt(d,611,y,a,19,soft);txt(d,909,y,b,22)
        d.rounded_rectangle((610,524,1165,568),8,fill=jade);txt(d,796,533,'查看浓度扫描  →',21,'white')
        if u>4:
            p=ease((u-4)/2);x=lerp(1130,984,p);y=lerp(600,546,p)
            if 6<u<6.7:
                rad=8+27*(u-6);d.ellipse((x-rad,y-rad,x+rad,y+rad),outline='#d9fff0',width=2)
            d.polygon([(x,y),(x+4,y+23),(x+10,y+16),(x+18,y+16)],fill='white',outline=ink)
    if i==2:
        p=ease((u-1)/11); idx=p*11;j=min(10,int(idx));v=lerp(vals[j],vals[j+1],idx-j)
        txt(d,58,110,'02    /    DOSE RESPONSE',20,jade,'m');txt(d,58,155,'浓度与存活率',47,ink,'b')
        txt(d,62,290,f'{v:.2f}',79,jade,'m');txt(d,65,387,'预测存活率（%）',21)
        txt(d,65,472,'CS-SeNPs   /   72 h',20,soft,'m')
        x0,x1=471,1176
        Y=lambda v:529-(v-45)*5.7
        for level in [50,70,90]:
            y=Y(level);d.line((x0,y,x1,y),fill=orange if level==50 else '#cbd5c9',width=1);txt(d,422,y-9,level,17,soft,'m')
        pts=[(x0+(x1-x0)*k/11,Y(vals[k])) for k in range(j+1)]+[(x0+(x1-x0)*idx/11,Y(v))]
        d.line(pts,fill=jade,width=5)
        for x,y in pts:d.ellipse((x-4,y-4,x+4,y+4),fill=jade)
        x,y=pts[-1];d.ellipse((x-7,y-7,x+7,y+7),fill=orange)
        for k in [0,3,6,9,11]:txt(d,x0+(x1-x0)*k/11-13,548,format(dose[k],'g'),17,ink,'m')
        txt(d,662,582,'浓度（μmol/L Se，对数刻度）',18,soft)
    if i==3:
        txt(d,58,112,'03    /    FEATURE ATTRIBUTION',20,'#92d6b8','m');txt(d,57,165,'哪些因素拉低了预测值？',47,cream,'b');txt(d,61,244,'512 μmol/L Se    ·    72 h    ·    局部 SHAP 贡献',22,dim)
        for k,(name,v) in enumerate([('暴露浓度',-14.78),('暴露时间',-1.48),('Zeta 电位',-.88)]):
            y=330+k*76;txt(d,62,y,name,24,cream);extent=515*abs(v)/14.78*ease((u-k*.36)/2)
            d.rectangle((876-extent,y,878,y+25),fill='#89cfb3');txt(d,925,y,f'{v:+.2f} 个百分点',22,cream)
        txt(d,62,570,'选列三项负向贡献   /   解释模型输出，不推断因果',18,dim)
    if i==4:
        txt(d,59,108,'04    /    ASSISTANT',20,jade,'m');txt(d,58,152,'读懂曲线的边界',47,ink,'b')
        d.rounded_rectangle((63,248,1180,324),15,fill='#deebe1');txt(d,90,270,'研究员     在这个案例里，能给出一个精确的 IC50 吗？',25)
        if u>2:
            d.rounded_rectangle((63,350,1180,591),15,fill='#fffdf7',outline='#c8d4c8');txt(d,90,377,'NanoTox Assistant   /   示例回复',21,jade)
            for k,line in enumerate(['最高测试浓度为 512 μmol/L Se，预测存活率为 54.09%。','测试范围内，曲线尚未达到 50%。','据此只能报告模型侧 IC50 > 512 μmol/L Se。']):
                if u>3+k*2.2:txt(d,91,432+k*46,line,25,ink)
    d.line((54,632,1226,632),fill=dim);txt(d,59,651,subs[i],38,fg)
    d.rectangle((0,715,int(W*t/78),719),fill='#56ad92')
    fade=min(1,.35+.65*min(u/.45,(cuts[i+1]-t)/.45));return Image.blend(Image.new('RGB',im.size,dark if night else paper),im,max(0,fade)) if fade<1 else im
F=next(Path('C:/Program Files/JianyingPro').glob('10.9*/ffmpeg.exe'))
fps=24
def render():
    proc=subprocess.Popen([str(F),'-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24','-video_size','1280x720','-framerate',str(fps),'-i','-','-c:v','h264_nvenc','-b:v','5M','-pix_fmt','yuv420p',str(P/'picture.mp4')],stdin=subprocess.PIPE)
    for n in range(78*fps):
        im=frame(n/fps)
        if n in [5*fps,15*fps,36*fps,47*fps,64*fps,74*fps]:im.save(P/f'frame-{n}.jpg',quality=92)
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    if proc.wait():raise RuntimeError('picture encoding failed')
def audio():
    sr=32000;t=np.arange(sr*78)/sr
    def tone(f,t):return np.sin(2*np.pi*f*t)
    score=np.zeros_like(t);sfx=np.zeros_like(t)
    for j in range(13):
        tt=t-j*6;env=np.clip(tt/1.2,0,1)*np.clip((6.7-tt)/1.2,0,1)
        root=[146.83,116.54,130.81,98][j%4]
        for mul in (1,1.5,2.378):score+=env*(.035*tone(root*mul,t)+.022*tone(root*mul*1.001,t))
        for k in range(6):
            dt=tt-k*.92; score+=.06*np.where(dt>=0,np.exp(-np.maximum(dt,0)*2.8),0)*tone(root*[2,3,3.56,4,3,2.378][k],dt)
    for pos in [1,9,20,33,38,51,54,69]:
        dt=t-pos;sfx+=np.where(dt>=0,np.exp(-np.maximum(dt,0)*5),0)*(.11*tone(587.33,dt)+.06*tone(880,dt))
    for name,signal in [('NanoTox',score+sfx),('NanoTox-no-music',sfx)]:
        with wave.open(str(P/'mix.wav'),'wb') as w:
            w.setparams((1,2,sr,0,'NONE',''));w.writeframes((signal*np.clip((78-t)/2,0,1)*32767).astype('<i2').tobytes())
        subprocess.run([str(F),'-y','-loglevel','error','-i',str(P/'picture.mp4'),'-i',str(P/'mix.wav'),'-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart',str(P/(name+'.mp4'))],check=True)
if __name__=='__main__':render();audio()
