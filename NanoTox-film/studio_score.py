import numpy as np,wave
def score(path,sec,beat=.48,music=True):
    sr=48000;arr=np.zeros((int(sec*sr),2));rng=np.random.default_rng(22)
    def put(at,w,pan=0):
        i=round(at*sr);n=min(len(w),len(arr)-i)
        if n>0:arr[i:i+n]+=w[:n,None]*np.array([np.sqrt((1-pan)/2),np.sqrt((1+pan)/2)])
    def T(d):return np.arange(int(sr*d))/sr
    for n in range(int(sec/beat)+1):
        at=n*beat;bar=n//4; accent=n%4;root=[130.81,103.83,155.56,116.54][(bar//2)%4]
        if n%8==0:
            t=T(.3);put(at,.13*np.exp(-t*14)*np.sin(2*np.pi*784*t)*np.minimum(1,t*250),.3)
        if not music:continue
        t=T(.29);put(at,.75*np.exp(-t*15)*np.sin(2*np.pi*(48*t+2.8*(1-np.exp(-t*45)))))
        if accent in (1,3):
            t=T(.18);noise=rng.normal(0,1,len(t));hp=np.diff(noise,prepend=0);put(at,.15*np.exp(-t*24)*hp+.13*np.sin(2*np.pi*177*t)*np.exp(-t*30),-.15)
        for k in range(2):
            t=T(.1 if k else .047);noise=rng.normal(size=len(t));put(at+k*beat/2,.055*np.diff(noise,prepend=0)*np.exp(-t*(44 if k else 80)),.38*(-1)**k)
        t=T(.19);f=root/2;put(at+.13,.26*np.tanh(2*np.sin(2*np.pi*f*t))*np.exp(-t*10)*np.minimum(1,t*170))
        if accent in (0,2):
            t=T(.27);w=sum(np.sin(2*np.pi*root*k*t)+.25*np.sin(4*np.pi*root*k*t) for k in (1,1.1892,1.4983))/3;put(at+.24,.18*w*np.exp(-t*8)*np.minimum(1,t*120),-.28)
        if bar%4>=2:
            t=T(.2);f=root*[2,2.3784,2.9966,3.5636][accent];put(at+.36,.12*np.sin(2*np.pi*f*t)*np.exp(-t*15)*np.minimum(1,t*200),.4)
    arr=np.tanh(arr*1.35)*.86;arr*=np.minimum(1,np.arange(len(arr))[::-1]/(sr*.6))[:,None]
    with wave.open(str(path),'wb') as f:f.setparams((2,2,sr,0,'NONE',''));f.writeframes((arr*32767).astype('<i2').tobytes())
