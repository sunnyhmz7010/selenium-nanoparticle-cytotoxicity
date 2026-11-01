from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
P=Path(__file__).resolve().parent
def make_window():
    base=Image.new('RGB',(1280,720),'#dce6df')
    shade=Image.new('RGBA',base.size);pen=ImageDraw.Draw(shade)
    pen.rounded_rectangle((66,15,1215,712),radius=13,fill=(12,47,39,95))
    base.paste(shade.filter(ImageFilter.GaussianBlur(9)),mask=shade.filter(ImageFilter.GaussianBlur(9)).getchannel('A'))
    d=ImageDraw.Draw(base)
    def label(x,y,s,size,col='#294b40'):
        d.text((x,y),s,fill=col,font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',size),anchor='lm')
    d.rounded_rectangle((62,5,1217,711),radius=13,fill='#f5f8f4',outline='#698777',width=2)
    for x,col in [(84,'#ca6857'),(102,'#d9aa55'),(120,'#6ba586')]:d.ellipse((x-5,20,x+5,30),fill=col)
    label(147,25,'NanoTox Assistant   /   本地工作台',17)
    d.rounded_rectangle((451,12,818,39),radius=10,fill='#e6ede6')
    label(468,25,'本地文件   /   workspace.html',15)
    label(1010,25,'●   平台操作实录',19,'#006c51')
    d.rectangle((64,45,1215,46),fill='#b2c4b7')
    base.save(P/'browser-window.png')
