from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,subprocess,sys
from studio_score import score
P=Path(__file__).resolve().parent
D=P/'shadcn-edit';D.mkdir(exist_ok=True)
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
c=json.loads((P/'ui/cues.json').read_text())
W,H=1920,1080;fps=25;beat=12
# 实际画面占 84%，窄栏每镜仅解释一个判断。
seq=[
('brief',8,'01  /  RESEARCH QUESTION','改变剂量，预测会变多少？','固定材料与时间，只改变暴露浓度。',[('材料','壳聚糖修饰纳米硒'),('细胞与时间','HUVEC   /   72 h'),('比较方式','同一冻结模型 · 两次运行')]),
('baseline',8,'01  /  BASELINE','先建立基线','54.09%',['输入归档条件，','对照模型预测与','匹配的实测值。']),
('input',7,'02  /  INPUT','只改一个量','320 μmol/L',['把浓度从 512','改成 320。','粒径、电位和','暴露时长不变。']),
('question',8,'03  /  ASK','向助手追问','−14.30 pp',['输入研究问题。','当前浓度的贡献','使预测低于模型','基线。']),
('compare',6,'04  /  COMPARE','比较两次运行','+0.66 pp',['助手保留上次','预测，可直接','核对变化幅度。']),
('result',8,'02  /  RESULT','剂量变了，预测仅小幅上升。','两次预测之差按未舍入值计算。',[('512 μmol/L Se','54.09%'),('320 μmol/L Se','54.76%'),('预测差值','+0.66 个百分点')]),
('tab0',4,'05  /  CURVE','回查实验曲线','实测对照',['此处回到归档','条件。绿色为','预测，橙色为','实验存活率。']),
('tab1',4,'06  /  MATERIAL','横向比较材料','9 种材料',['固定剂量与时长，','查看不同材料的','实测与预测排序。']),
('tab2',4,'07  /  THRESHOLD','检查剂量阈值','IC50',['同时显示插值','括区和未达到','阈值的情况。']),
('tab3',4,'08  /  ATTRIBUTION','解释预测值','SHAP',['正负贡献加上','模型基线，可','还原当前预测。']),
('tab5',4,'09  /  RECORDS','回到原始记录','13 个剂量',['逐行核对单位、','实验值和预测值，','可导出当前表。']),
('summary',7,'03  /  INTERPRETATION','预测之后，还要问一句。','320 μmol/L Se 没有完全匹配的实验记录。',[('可报告','模型预测与特征贡献'),('需区分','预测变化 ≠ 实验效应'),('下一步','在该条件下补充实测')])]
ink='#142f2b';muted='#4d6a61';mint='#c0e8d1';paper='#f4f6f3'
def txt(d,x,y,s,n,col=ink,font='msyh.ttc'):d.text((x,y),s,font=ImageFont.truetype('C:/Windows/Fonts/'+font,n),fill=col,anchor='lt')
def plate(i,seqrow):
    k,beats,ey,title,num,lines=seqrow;card=k not in c
    im=Image.new('RGB',(W,H),ink if card else paper);d=ImageDraw.Draw(im)
    if card:
        txt(d,90,82,'NanoTox Assistant',39,'#fafcf5','georgia.ttf');txt(d,92,213,ey,27,mint,'bahnschrift.ttf')
        txt(d,86,312,title,74,'#fafcf5','msyhbd.ttc');txt(d,93,455,num,40,'#c9dfd4')
        for j,(label,v) in enumerate(lines):
            x=93+585*j;d.line((x,635,x+528,635),fill='#5d8877',width=2)
            txt(d,x,677,label,30,'#bbd5c7');txt(d,x,768,v,43,'#f4fff4','msyhbd.ttc')
    else:
        d.rectangle((1628,0,1919,1079),fill='#e9efeb');d.line((1628,62,1628,1018),fill='#bbccc1',width=2)
        txt(d,1650,164,ey,20,muted,'bahnschrift.ttf');txt(d,1648,249,title,34,ink,'msyhbd.ttc')
        d.rectangle((1650,324,1688,328),fill='#3a8868');txt(d,1648,383,num,32,'#207058','msyhbd.ttc')
        for j,line in enumerate(lines):txt(d,1651,486+50*j,line,28,ink)
        txt(d,1652,967,'NanoTox Assistant',23,muted,'georgia.ttf')
    path=D/f'plate-{i:02}.png';im.save(path);return path
def run(*a):subprocess.run([str(F),'-y','-loglevel','error',*map(str,a)],check=True)
keys=list(c)
for i,row in enumerate(seq):
    k,n,*_=row;frames=n*beat;dur=frames/fps;img=plate(i,row);args=['-loop','1','-framerate','25','-i',img]
    if k in c:
        a=c[k];b=c[keys[keys.index(k)+1]];start=a+.16;length=max(.5,b-start-.05)
        start,length={'baseline':(8.2,12.4),'input':(21.0,10.8),'question':(32.1,5.7),'compare':(38,4.4),'tab0':(45.4,2.2),'tab1':(51.0,2.2),'tab2':(56.8,2.1),'tab3':(61.8,2.1),'tab5':(67.4,2.6)}[k]
        args+=['-ss',start,'-t',length,'-i',P/'shadcn-source.mp4','-filter_complex',f'[1:v]setpts={dur/length:.8f}*(PTS-STARTPTS),fps=25,scale=1620:-2,setsar=1,tpad=stop_mode=clone:stop_duration=0.6[win];[0:v][win]overlay=0:(H-h)/2']
    else:args+=['-vf','fade=t=in:d=0.12']
    run(*args,'-frames:v',frames,'-an','-c:v','libx264','-crf','17','-preset','veryfast','-pix_fmt','yuv420p',D/f'cut-{i}.mp4')
(D/'cuts.txt').write_text(''.join(f"file 'cut-{i}.mp4'\n" for i in range(len(seq))),encoding='ascii')
duration=sum(r[1] for r in seq)*.48
for music,suffix in [(True,'比赛版'),(False,'无配乐版')]:
    a=D/(suffix+'.wav');score(a,duration,music=music)
    run('-f','concat','-safe','0','-i',D/'cuts.txt','-i',a,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',P/f'NanoTox-Assistant-新版-{suffix}.mp4')
print(duration)
