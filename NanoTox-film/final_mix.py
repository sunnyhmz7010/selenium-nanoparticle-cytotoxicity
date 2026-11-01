from pathlib import Path
import subprocess, numpy as np
from scipy import signal
P=Path(__file__).resolve().parent;F=next(Path('C:/Users/Sunny/AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'));music=Path('C:/Users/Sunny/.agents/skills/video-shotcraft/assets/audio/bgm/cat-walk.mp3')
def rhythm():
    sr=12000
    a=np.frombuffer(subprocess.check_output([str(F),'-loglevel','error','-i',str(music),'-t','90','-ac','1','-ar',str(sr),'-f','f32le','-']),np.float32)
    low=signal.sosfilt(signal.butter(3,[38,125],fs=sr,btype='band',output='sos'),a)
    env=np.sqrt(np.mean(low[:len(low)//60*60].reshape(-1,60)**2,1));on=np.maximum(0,env-np.roll(env,3))
    time=np.arange(len(on))/200;mask=(time>8)&(time<78);best=(0,0,0)
    for bpm in np.arange(123,135,.01):
        z=np.sum(on[mask]*np.exp(2j*np.pi*time[mask]*bpm/60))
        if abs(z)>best[0]:best=(abs(z),bpm,(np.angle(z)/(2*np.pi)%1)*60/bpm)
    return best[1:]
if __name__=='__main__':print(rhythm())
from PIL import Image,ImageDraw,ImageFont
import wave
def run(*args):
    subprocess.run([str(F),'-y','-loglevel','error',*map(str,args)],check=True)
def build():
    out=P/'send-final';out.mkdir(exist_ok=True);master=P/'motion-master'
    # 回车后的完整对话保留至下一条问题开始前，最后一帧延长用于阅读。
    panels=[]
    for i in range(2):
        im=Image.new('RGB',(292,1080),'#e9efeb');d=ImageDraw.Draw(im)
        def text(x,y,s,n,b=False,col='#142f2b'):d.text((x,y),s,font=ImageFont.truetype('C:/Windows/Fonts/'+('msyhbd.ttc' if b else 'msyh.ttc'),n),fill=col,anchor='lt')
        text(20,165,'03   /   ASK',22);text(20,250,['向助手提问','助手已回复'][i],34,True)
        d.rectangle((20,324,80,328),fill='#35886e')
        lines=[['浓度贡献','是多少？','按回车发送'],['−14.30 pp','浓度使模型输出','低于基线。','本次预测 54.76%。']][i]
        for j,s in enumerate(lines):text(20,402+j*62,s,30 if j==0 else 26,j==0)
        text(20,961,'NanoTox Assistant',20);fp=out/f'panel-{i}.png';im.save(fp);panels.append(fp)
    # 两段拼接均取自同一条真实录屏：输入过程，随后回车提交并显示问题及答案。
    run('-i',P/'pointer-source.mp4','-loop','1','-framerate','25','-i',panels[0],'-loop','1','-framerate','25','-i',panels[1],'-filter_complex',
        "[0:v]trim=start=17.45:end=20.98,setpts=0.83*(PTS-STARTPTS),fps=25[a];[0:v]trim=start=20.98:end=23.05,setpts=PTS-STARTPTS,fps=25,tpad=stop_mode=clone:stop_duration=3[b];[a][b]concat=n=2:v=1:a=0,scale=1620:-2,setsar=1,pad=1920:1080:0:(oh-ih)/2:color=0xf4f6f3[v];[v][1:v]overlay=1628:0[p];[p][2:v]overlay=1628:0:enable='gte(t,3.32)'",
        '-frames:v','180','-an','-c:v','libx264','-crf','17','-preset','veryfast','-pix_fmt','yuv420p',out/'sent.mp4')
    cuts=[out/'sent.mp4' if i==4 else master/f'{i:02}.mp4' for i in range(15)]
    (out/'cuts.txt').write_text(''.join("file '"+v.as_posix()+"'\n" for v in cuts),encoding='utf8')
    dur=56.64-3.84+7.2
    bpm,phase=rhythm();offset=phase+32*60/bpm
    from studio_score import score
    score(out/'sfx.wav',dur,music=False)
    for bg,name in [(True,'比赛版'),(False,'无配乐版')]:
        args=['-f','concat','-safe','0','-i',out/'cuts.txt','-i',out/'sfx.wav']
        if bg:args+=['-ss',offset,'-i',music,'-filter_complex',f'[2:a]atempo={125/bpm:.8f},volume=-4.5dB,atrim=duration={dur},afade=t=in:d=0.12,afade=t=out:st={dur-1.2}:d=1.2[m];[m][1:a]amix=inputs=2:normalize=0:duration=shortest,alimiter=limit=0.95[a]','-map','0:v','-map','[a]']
        else:args+=['-map','0:v','-map','1:a']
        run(*args,'-t',dur,'-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',P/f'NanoTox-Assistant-问答完整版-{name}.mp4')
    print(dur)
if __name__=='__main__':build()
