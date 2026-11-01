from pathlib import Path
import subprocess, json, math
import numpy as np
from scipy import signal
from scipy.io import wavfile
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parent; D=P/'ab-edit'
F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
def run(*args):subprocess.run([str(F),'-y','-loglevel','error',*map(str,args)],check=True)
def analyse(fp):
    sr,x=wavfile.read(fp);x=x.astype(float).mean(axis=1)/32768
    bands=[]
    for lo,hi in [(35,140),(150,1800),(3500,11000)]:
        y=signal.sosfilt(signal.butter(3,[lo,hi],fs=sr,btype='bandpass',output='sos'),x)
        w=sr//200;e=np.sqrt((y[:len(y)//w*w].reshape(-1,w)**2).mean(axis=1))
        o=np.maximum(0,e-np.r_[np.repeat(e[0],3),e[:-3]]);bands.append(np.minimum(5,o/(np.percentile(o,93)+1e-8)))
    low,mid,high=bands;on=.65*low+.25*mid+.1*high;t=np.arange(len(on))/200
    sel=(t>1)&(t<74);best=(0,0,0)
    for bpm in np.arange(78,162,.025):
        z=np.sum(on[sel]*np.exp(2j*np.pi*t[sel]*bpm/60))
        if abs(z)>best[0]:best=(abs(z),bpm,float(np.angle(z)/(2*np.pi)%1)*60/bpm)
    _,bpm,phase=best;period=60/bpm
    peaks=signal.find_peaks(on,distance=12,prominence=.22)[0]
    def snap(target):
        idx=peaks[abs(t[peaks]-target)<.085]
        return float(t[idx[np.argmax(on[idx]*np.exp(-abs(t[idx]-target)/.09))]]) if len(idx) else target
    print(fp.name,round(bpm,3),round(phase,3),flush=True)
    return period,phase,snap
if __name__=='__main__':
    music=Path('C:/Users/Sunny/.agents/skills/video-shotcraft/assets/audio/bgm/cat-walk.mp3')
    run('-ss',.436643+32*60/129.73,'-i',music,'-t',85,'-af','atempo=0.9635782','-ar','48000','-ac',2,D/'B.wav')
    for k in 'AB':analyse(D/(k+'.wav'))
FPS=25
# 开场与问答独立占时，其他镜头沿用已验收的动画和原生窗口。
lengths=[5.8,4.8,3.8,4.8,3.4,10.5,5.7,2.9,4.8,2.4,2.4,2.4,5.7,2.4,2.4,4.8]
counts=[10,8,10,7,15,12,6,10,5,5,5,12,5,5,10]
motion={0:[.55,1.35],2:[1.8,2.48],5:[.65,2.2,2.9],7:[.62,2.07],11:[.35,1.55,2.85],14:[1.25,2.15]}
from functools import lru_cache
@lru_cache(None)
def font(n,k):return ImageFont.truetype('C:/Windows/Fonts/'+{'c':'msyh.ttc','b':'msyhbd.ttc','s':'georgia.ttf','m':'bahnschrift.ttf'}[k],n)
def title_movie(out,n,accents):
    proc=subprocess.Popen([str(F),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-framerate','25','-i','-','-frames:v',str(n),'-an','-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p',str(out)],stdin=subprocess.PIPE)
    for j in range(n):
        t=j/25;im=Image.new('RGB',(1920,1080),'#102d2c');d=ImageDraw.Draw(im)
        def tx(x,y,s,z,k='c',color='#eaf6ed'):d.text((x,y),s,font=font(z,k),fill=color,anchor='lt')
        tx(90,81,'软件演示     /     PRODUCT DEMO',32,'c','#9ad8b8');d.line((91,157,1820,157),fill='#416558',width=2)
        tx(81,248,'NanoTox Assistant',119,'s');tx(92,433,'纳米硒细胞毒性预测与交互解释工作台',59,'b')
        tx(94,565,'输入暴露条件，预测细胞存活率，并追问模型为何给出这个结果。',38,'c','#c4dcd1')
        for i,(a,b) in enumerate([('01','输入条件'),('02','运行预测'),('03','追问与核对')]):
            p=max(0,min(1,(t-accents[i])/.32));p=p*p*(3-2*p)
            if p:
                x=96+i*579;d.rectangle((x,769,x+round(488*p),773),fill='#88cbb0')
                tx(x,813+int((1-p)*15),a,34,'m','#9ad8b8');tx(x+79,807+int((1-p)*15),b,43,'b')
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    if proc.wait():raise RuntimeError('片头渲染失败')
def build(k):
    period,phase,snap=analyse(D/(k+'.wav'));origin=snap(phase)
    def local(b):return snap(phase+b*period)-origin
    bounds=[0];beatidx=[0];offset=0.
    for ix,dt in enumerate(lengths):
        offset+=dt;b=round(offset/period);beatidx.append(b);bounds.append(round(25*local(b)))
    folder=D/k;folder.mkdir(exist_ok=True);markers=[]
    for ix,(lo,hi) in enumerate(zip(bounds,bounds[1:])):
        out=folder/f'{ix:02}.mp4';n=hi-lo;L=n/FPS
        if ix==0:
            title_movie(out,n,[local(v) for v in [1,2,3]]);continue
        m=ix-1;src=P/'send-final/sent.mp4' if m==4 else P/f'motion-master/{m:02}.mp4'
        duration=7.2 if m==4 else counts[m]*.48
        if m==4:
            # 使用完整发送镜头，回复可读后将真实末帧保留到下一个切点。
            run('-i',src,'-vf',f'fps=25,tpad=stop_mode=clone:stop_duration={L}', '-frames:v',n,'-an','-c:v','libx264','-preset','veryfast','-crf',17,'-pix_fmt','yuv420p',out)
            continue
        pts=[(0.,0)]
        for s in motion.get(m,[]):
            dest=lo/FPS+L*s/duration;b=round(dest/period)
            at=round(25*local(b))-lo
            if pts[-1][1]+3<at<n-3:
                pts.append((s,at));markers.append((m,s,(lo+at)/25))
        pts.append((duration,n));parts=[]
        for i,((a,x),(b,y)) in enumerate(zip(pts,pts[1:])):
            r=(y-x)/25/(b-a)
            parts.append(f'[0:v]trim=start={a}:end={b},setpts={r:.8f}*(PTS-STARTPTS),fps=25,tpad=stop_mode=clone:stop_duration=0.12,trim=end_frame={y-x},setpts=PTS-STARTPTS[v{i}]')
        f=';'.join(parts)+';'+''.join('[v%d]'%i for i in range(len(parts)))+f'concat=n={len(parts)}:v=1:a=0[v]'
        run('-i',src,'-filter_complex',f,'-map','[v]','-frames:v',n,'-an','-c:v','libx264','-preset','veryfast','-crf',17,'-pix_fmt','yuv420p',out)
    (folder/'shots.txt').write_text(''.join(f"file '{i:02}.mp4'\n" for i in range(len(lengths))),encoding='ascii')
    duration=bounds[-1]/25
    # 将轻提示音放在各版本自己的操作切点，音乐保持前次选择的音色和速度。
    sr=48000;sfx=np.zeros(int(duration*sr))
    for ix in (2,4,5,7,9,10,11,13,14):
        i=round(bounds[ix]/25*sr);t=np.arange(int(.17*sr))/sr;sfx[i:i+len(t)]+=.035*np.sin(2*np.pi*(660 if ix%2 else 440)*t)*np.minimum(1,t*350)*np.exp(-t*24)
    wavfile.write(folder/'cue.wav',sr,(sfx*32767).astype('<i2'))
    name='若如初见-原速' if k=='A' else 'Cat-Walk'
    dst=P/f'NanoTox-Assistant-{k}版-{name}.mp4'
    run('-f','concat','-safe',0,'-i',folder/'shots.txt','-ss',origin,'-i',D/(k+'.wav'),'-i',folder/'cue.wav','-filter_complex',f'[1:a]atrim=duration={duration},asetpts=PTS-STARTPTS,volume=-4dB,afade=t=in:d=0.12,afade=t=out:st={duration-1.2}:d=1.2[m];[m][2:a]amix=inputs=2:normalize=0:duration=shortest,alimiter=limit=0.95:level=false:latency=true[a]','-map','0:v','-map','[a]','-t',duration,'-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',dst)
    info=dict(bpm=60/period,origin=origin,duration=duration,bounds=[x/25 for x in bounds],answer=[bounds[5]/25+3.32,bounds[6]/25],motion=markers)
    (folder/'timing.json').write_text(json.dumps(info,indent=2));print(k,info['duration'],info['answer'],flush=True)
if __name__=='__main__':
    for key in 'AB':build(key)
