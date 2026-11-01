from pathlib import Path
from functools import lru_cache
import subprocess, csv, math, json
from PIL import Image, ImageDraw, ImageFont
from studio_score import score
P=Path(__file__).resolve().parent; O=P/'motion-master'; O.mkdir(exist_ok=True)
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
E=P/'evidence-edit'; W,H=1920,1080
bg='#0c2527';ink='#112f31';white='#f3f8ef';mint='#9ce6c1';coral='#ffb381';sub='#a2c1b6';rule='#345651'
@lru_cache(None)
def font(n,k):return ImageFont.truetype('C:/Windows/Fonts/'+{'cn':'msyh.ttc','b':'msyhbd.ttc','m':'bahnschrift.ttf','s':'georgia.ttf','i':'georgiai.ttf'}[k],n)
def text(d,x,y,s,n=32,k='cn',color=white):
    d.text((round(x),round(y)),s,font=font(n,k),fill=color,anchor='lt')
def clamp(t):return min(1,max(0,t))
def ease(t):t=clamp(t);return t*t*(3-2*t)
def phase(t,start,length):return ease((t-start)/length)
def line(d,a,b,p,col,width=3):
    d.line((a,(a[0]+(b[0]-a[0])*p,a[1]+(b[1]-a[1])*p)),fill=col,width=width)
def dot(d,x,y,r,c):d.ellipse((x-r,y-r,x+r,y+r),fill=c)
def rise(d,x,y,s,n,k,col,p):
    if p>.01:text(d,x,y+(1-p)*28,s,n,k,col)
def shell(d,num,label,t):
    text(d,86,56,'NanoTox Assistant',34,'s');text(d,1460,63,label,23,'m',sub)
    line(d,(88,119),(1830,119),phase(t,0,.55),rule,2);text(d,89,171,'FIELD STUDY    /    '+num,24,'m',mint)
def foot(d,msg,t,delay):
    rise(d,90,975,msg,29,'cn',sub,phase(t,delay,.4))
def mol(d,x,y,r,t):
    pts=[]
    for j in range(260):
        v=1-2*(j+.5)/260;a=2.399963*j+t*.33;c=math.sqrt(1-v*v);xx=c*math.cos(a);z=c*math.sin(a)
        pts.append((z,x+r*(.94*xx-.33*v),y+r*(.94*v+.33*xx)))
    for z,x,y in sorted(pts):
        l=(z+1)/2;dot(d,x,y,1.8+3.6*l,tuple(round(a+(b-a)*l*l) for a,b in zip((29,61,58),(172,239,196))))
base=P.parent/'research/results/huvec_external_20261013_umol_se'
def vals(file,k):
    with (base/file).open() as f:return [float(r[k]) for r in csv.DictReader(f) if r['nanoparticle']=='CS-SeNPs' and r['time_h']=='72' and float(r['concentration_reported'])>0]
obs=vals('experimental_data.csv','viability_percent');pred=vals('model_predictions.csv','predicted_viability_percent')
def path(d,pts,p,color):
    q=p*(len(pts)-1);j=min(len(pts)-2,int(q));a,b=pts[j:j+2];h=(a[0]+(b[0]-a[0])*(q-j),a[1]+(b[1]-a[1])*(q-j))
    d.line(pts[:j+1]+[h],fill=color,width=6);dot(d,*h,9,color)
def scene(i,t):
    im=Image.new('RGB',(W,H),bg);d=ImageDraw.Draw(im)
    if i==0:
        shell(d,'01','SPECIMEN   /   SELENIUM',t);mol(d,1430,525,230+22*phase(t,.1,2.5),t)
        rise(d,80,270,'一次只改变剂量。',88,'b',white,phase(t,0,.55))
        text(d,92,434,'CS-SeNPs',66,'s',mint)
        for j,s in enumerate(['114.72 nm　粒径','+33.36 mV　Zeta 电位','HUVEC　 ·　72 小时']):
            rise(d,95,577+j*67,s,35,'cn',white,phase(t,.35+.23*j,.45))
        foot(d,'用同一个冻结模型运行两次，观察预测存活率如何变化。',t,1.35)
    elif i==2:
        shell(d,'02','MODEL   /   OBSERVATION',t);text(d,84,246,'先量出已有的偏差',70,'b');text(d,90,355,'512 μmol/L Se   ·   72 h',35,'m',sub)
        X=lambda v:320+v*21
        for j,(name,v,col) in enumerate([('实测',31.25353,coral),('预测',54.0929,mint)]):
            y=560+j*155;u=phase(t,.22+j*.27,1.35);text(d,91,y-20,name,43,'b')
            d.line((320,y,1590,y),fill=rule,width=2);line(d,(320,y),(X(v),y),u,col,16);x=X(v*u);dot(d,x,y,13,col)
            if u>.98:text(d,x+28,y-23,f'{v:.2f}%',44,'m',col)
        q=phase(t,1.8,.68);line(d,(X(31.25353),833),(X(54.0929),833),q,white,3)
        if q>.6:rise(d,990,855,'+22.84 个百分点',42,'b',white,q)
        foot(d,'同一条件下模型高估了存活率。这个偏差是随后比较新条件的参照。',t,2.4)
    elif i==5:
        shell(d,'03','TREE SHAP   /   DECOMPOSITION',t);text(d,84,225,'从基线走到本次预测',65,'b')
        X=lambda v:100+(v-48)*55; y=550
        for n in (50,55,60,65,70):x=X(n);d.line((x,465,x,755),fill=rule,width=1);text(d,x-22,786,str(n)+'%',24,'m',sub)
        a,b,c=69.6104,55.3138,54.7552
        p=phase(t,.65,1.4);q=phase(t,2.2,.7);cur=a+(b-a)*p+(c-b)*q
        dot(d,X(a),y,12,white);text(d,X(a)-95,385,'基线 69.61%',31,'cn',white)
        line(d,(X(a),y),(X(b),y),p,coral,19);line(d,(X(b),y),(X(b),687),phase(t,1.86,.3),sub,2);line(d,(X(b),687),(X(c),687),q,mint,17)
        if p>.4:rise(d,660,590,'浓度贡献　−14.30 pp',36,'b',coral,p)
        if q>.25:rise(d,125,710,'其余贡献合计　−0.56 pp',28,'cn',mint,q)
        text(d,1455,507,f'{cur:.2f}%',66,'m',mint);text(d,1460,600,'模型输出',30,'cn',sub)
        foot(d,'pp 为百分点。贡献解释模型本次输出，不代表实验因果效应。',t,2.7)
    elif i==7:
        shell(d,'04','TWO RUNS   /   PAIRED CHANGE',t);text(d,86,243,'剂量下调，预测变化有多大？',64,'b')
        p=phase(t,.62,1.45);x=340+930*p;d.line((340,590,1270,590),fill=rule,width=6);line(d,(340,590),(1270,590),p,mint,7)
        for xx,v in [(340,'512'),(1270,'320')]:dot(d,xx,590,11,white);text(d,xx-46,656,v,52,'m',white)
        dot(d,x,590,18,mint);text(d,92,443,'输入浓度  /  μmol/L Se',30,'cn',sub)
        if p>.98:text(d,1375,520,'+0.66',88,'m',mint);text(d,1385,624,'个百分点',32,'cn',mint)
        rise(d,220,756,'预测 54.09%',39,'b',white,phase(t,.12,.4));rise(d,1110,756,'预测 54.76%',39,'b',white,phase(t,1.6,.5))
        foot(d,'差值按未舍入的两次预测计算。320 μmol/L Se 仍缺少完全匹配的实测记录。',t,2.0)
    elif i==11:
        shell(d,'05','THRESHOLD   /   DOSE RESPONSE',t);text(d,84,213,'让曲线自己穿过阈值',65,'b')
        X=lambda j:120+j*97;Y=lambda v:853-v*4.05
        for v in (0,50,100):
            y=Y(v);d.line((120,y,1200,y),fill='#8eaba0' if v==50 else rule,width=2);text(d,50,y-14,str(v),25,'m',sub)
        u=phase(t,.35,2.5)
        for a,col in [(pred,mint),(obs,coral)]:path(d,[(X(j),Y(v)) for j,v in enumerate(a)],u,col)
        ix=X(math.log2(11.942644/.25));y=Y(50)
        if u>(math.log2(11.942644/.25)/11):
            d.ellipse((ix-14,y-14,ix+14,y+14),outline=white,width=3);line(d,(ix,y),(ix,852),phase(t,1.5,.45),white,2)
            rise(d,1280,492,'实验 IC50',31,'cn',coral,phase(t,1.45,.45));rise(d,1277,548,'11.94 μmol/L',55,'m',coral,phase(t,1.55,.45))
        if u>.97:rise(d,1280,674,'模型未达到 50%',31,'cn',mint,phase(t,2.65,.45));rise(d,1277,730,'>512 μmol/L',52,'m',mint,phase(t,2.7,.45))
        for j in (0,3,6,9,11):text(d,X(j)-14,873,format(.25*2**j,'g'),25,'m',sub)
        foot(d,'横轴为正剂量对数刻度（μmol/L Se）。实验 IC50 在 8 与 16 之间插值。',t,2.5)
    else:
        shell(d,'06','EVIDENCE   /   NEXT EXPERIMENT',t);rise(d,87,242,'把下一次实验放在哪里？',67,'b',white,phase(t,.05,.5))
        x0,x1=175,1675;y=565;line(d,(x0,y),(x1,y),phase(t,.15,.85),rule,5)
        for j in range(12):
            x=x0+(x1-x0)*j/11;p=phase(t,.28+.065*j,.22)
            if p:dot(d,x,y,7*p,mint)
        for j in [0,6,10,11]:text(d,x0+(x1-x0)*j/11-22,615,format(.25*2**j,'g'),26,'m',sub)
        x=x0+(x1-x0)*math.log2(320/.25)/11;p=phase(t,1.25,.72);line(d,(x,392),(x,540),p,coral,3)
        if p>.1:rise(d,x-166,340,'320 μmol/L Se',37,'m',coral,p)
        if p>.88:d.ellipse((x-13,y-13,x+13,y+13),outline=coral,width=4)
        rise(d,92,760,'已有实验点之间，补一次实测。',52,'b',white,phase(t,1.7,.6))
        foot(d,'保留材料与培养条件，测量 320 μmol/L Se 的实际存活率，再核对 54.76% 的预测。',t,2.15)
    return im
beat=12
cards={0:10,2:10,5:12,7:10,11:12,14:10}
beats=[10,8,10,7,8,12,6,10,5,5,5,12,5,5,10]
def sidebar(i,t,dur,src):
    sw=292;im=Image.new('RGB',(sw,H),'#e9efeb');d=ImageDraw.Draw(im)
    for a,b,start in [(135,200,0),(222,305,.12),(367,451,.28),(460,735,.41),(940,1010,.56)]:
        p=phase(t,start,.32)
        if p:
            patch=src.crop((0,a,sw,b));solid=Image.new('RGB',patch.size,'#e9efeb');im.paste(Image.blend(solid,patch,p),(0,round(a+18*(1-p))))
    d.rectangle((22,324,22+round(65*phase(t,.18,.36)),328),fill='#35886e')
    for j in range(12):d.rectangle((22+j*18,877,33+j*18,880),fill='#347c66' if j<12*clamp(t/dur) else '#c5d4c9')
    d.line((0,55,0,1020),fill='#bacdc2',width=2)
    return im
def run(*args):subprocess.run([str(F),'-y','-loglevel','error',*map(str,args)],check=True)
for i,b in enumerate(beats):
    n=b*beat;full=i in cards;width=W if full else 292;out=O/f'{i:02}.mp4'
    args=['-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{H}','-framerate','25','-i','-']
    if not full:
        src=Image.open(E/f'plate-{i:02}.png').convert('RGB').crop((1628,0,W,H))
        args+=['-i',str(E/f'cut-{i}.mp4'),'-filter_complex','[1:v][0:v]overlay=1628:0:shortest=1']
    proc=subprocess.Popen([str(F),'-y','-loglevel','error',*args,'-frames:v',str(n),'-an','-c:v','libx264','-crf','17','-preset','veryfast','-pix_fmt','yuv420p',str(out)],stdin=subprocess.PIPE)
    for j in range(n):
        t=j/25;im=scene(i,t) if full else sidebar(i,t,n/25,src);proc.stdin.write(im.tobytes())
    proc.stdin.close()
    if proc.wait():raise RuntimeError(f'Failed at shot {i}')
(O/'cuts.txt').write_text(''.join(f"file '{i:02}.mp4'\n" for i in range(len(beats))),encoding='ascii')
duration=sum(beats)*.48
for music,name in [(True,'比赛版'),(False,'无配乐版')]:
    run('-f','concat','-safe','0','-i',O/'cuts.txt','-i',E/(name+'.wav'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',P/f'NanoTox-Assistant-动态演示-{name}.mp4')
print(duration)
