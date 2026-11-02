"""Generate actual firmware LCD pixels and wiring graphics from wiring.json."""
from pathlib import Path
from html import escape
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import wasmtime

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT/'docs/images'

def lcd_images():
    engine=wasmtime.Engine();store=wasmtime.Store(engine)
    e=wasmtime.Instance(store,wasmtime.Module.from_file(engine,str(ROOT/'build/tests/display_raster.wasm')),[]).exports(store)
    e['__wasm_call_ctors'](store)
    frames=[]
    for state,name in enumerate(('no-probe','ready','touch')):
        e['preview'](store,state)
        assert e['allocations'](store)==0
        address=e['framebuffer'](store)
        pixels=np.frombuffer(e['memory'].read(store,address,address+240*240*2),dtype='<u2').reshape(240,240)
        rgb=np.stack(((pixels>>11)*255//31,((pixels>>5)&63)*255//63,(pixels&31)*255//31),axis=-1).astype('uint8')
        frame=Image.fromarray(rgb)
        frame.save(IMAGES/(name+'.png'))
        frames.append(frame)
    overview=Image.new('RGB',(744,264),'#18202e')
    for i,frame in enumerate(frames):overview.paste(frame,(12+i*240,12))
    overview.resize((1488,528),Image.Resampling.NEAREST).save(IMAGES/'display-overview.png')

class Diagram:
    """The same geometry writes SVG and PNG; no browser or third-party render service."""
    def __init__(self):
        self.image=Image.new('RGB',(1280,750),'#f4f7fb')
        self.draw=ImageDraw.Draw(self.image)
        self.svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="750" viewBox="0 0 1280 750">',
                  '<rect width="1280" height="750" fill="#f4f7fb"/>']
    def font(self,size,bold):
        options=[Path('C:/Windows/Fonts')/('segoeuib.ttf' if bold else 'segoeui.ttf'),
                 Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                 Path('/usr/share/fonts/dejavu-sans-fonts')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
        for path in options:
            if path.is_file():return ImageFont.truetype(str(path),size)
        return ImageFont.load_default(size=size)
    def text(self,x,y,value,size=18,color='#19263d',bold=False,anchor='left'):
        self.draw.text((x,y),value,fill=color,font=self.font(size,bold),anchor='rm' if anchor=='right' else 'lm')
        self.svg.append(f'<text x="{x}" y="{y}" dominant-baseline="middle" text-anchor="{"end" if anchor=="right" else "start"}" font-family="Segoe UI,DejaVu Sans,Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')
    def rect(self,x,y,w,h,fill='#ffffff',stroke='#d3dce9'):
        self.draw.rounded_rectangle((x,y,x+w,y+h),radius=14,fill=fill,outline=stroke,width=2)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    def line(self,points,color):
        self.draw.line(points,fill=color,width=4)
        self.svg.append(f'<polyline points="{" ".join(str(x)+","+str(y) for x,y in points)}" fill="none" stroke="{color}" stroke-width="4"/>')
    def dot(self,x,y,color):
        self.draw.ellipse((x-5,y-5,x+5,y+5),fill=color)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"/>')
    def save(self):
        self.image.save(IMAGES/'wiring.png')
        (IMAGES/'wiring.svg').write_text('\n'.join(self.svg+['</svg>'])+'\n',encoding='utf-8',newline='\n')

def wiring():
    data=json.loads((ROOT/'hardware/wiring.json').read_text(encoding='utf-8'))
    d=Diagram()
    d.text(36,35,'m&h 20.00 receiver — ESP32 / CC1101 / ST7789',28,bold=True)
    d.text(36,72,'Signal connections; ESP32 header positions depend on the DevKit. All peripheral signals: 3.3 V.',18)
    d.rect(36,112,292,430);d.rect(470,112,340,430);d.rect(948,112,296,430)
    d.text(56,143,'CC1101 / 433 MHz',23,bold=True)
    d.text(56,177,'VSPI • module pin numbers',17)
    d.text(490,143,'ESP32-WROOM',23,bold=True)
    d.text(490,177,'Classic ESP32 Dev Module',17)
    d.text(968,143,'IPS 240×240',23,bold=True)
    d.text(968,177,'ST7789 • HSPI • MODE3',17)
    colors={'GND':'#344054','VCC':'#e53b49','GDO0':'#cd3187','CSN':'#bd840b',
            'SCK':'#2a65cc','MOSI':'#209b55','MISO/GDO1':'#8547c4',
            'SCL/SCK':'#2a65cc','SDA/MOSI':'#209b55','RES':'#e37c23','DC':'#139ea9','BLK':'#e53b49'}
    for i,pin in enumerate(data['cc1101']['pins']):
        y=218+i*40
        label=str(pin['pin'])+'  '+pin['signal']
        color=colors.get(pin['signal'],'#8a95a8')
        d.text(56,y,label,19,bold=True)
        if pin.get('esp32')=='NC':
            d.text(312,y,'unused',16,color,anchor='right')
            continue
        target='GPIO'+str(pin['gpio']) if 'gpio' in pin else pin['esp32']
        d.text(490,y,target,18)
        d.line([(328,y),(470,y)],color);d.dot(328,y,color);d.dot(470,y,color)
    ys=[218,258,298,338,378,418,458]
    for pin,y in zip(data['display']['pins'],ys):
        color=colors[pin['signal']]
        target='GPIO'+str(pin['gpio']) if 'gpio' in pin else pin['esp32']
        d.text(968,y,pin['signal'],19,bold=True)
        if pin['signal']=='BLK':
            d.line([(880,258),(880,y),(948,y)],color);d.dot(880,258,color)
        else:
            d.text(790,y,target,18,anchor='right')
            d.line([(810,y),(948,y)],color);d.dot(810,y,color)
        d.dot(948,y,color)
    d.text(968,503,'No CS pin; BLK = backlight',16)
    d.rect(36,564,1208,148,fill='#e8eef7')
    d.text(56,593,'Machine outputs: GPIO → 150 ohm → AQY212EH PhotoMOS → J1 (never wire 24 V to a GPIO)',20,bold=True)
    d.text(56,627,'     '.join('GPIO'+str(pin['gpio'])+' '+pin['signal'] for pin in data['machine_reserved']),19)
    d.text(56,660,'Power: 24 V → DD4012SA 5 V buck (not isolated) → JP1 → ESP32 5V; ESP32 3V3 feeds radio and display.',18)
    d.text(56,687,'Machine 0 V = logic GND. With JP1 fitted, do not connect USB to a PC on machine 24 V. See docs/power.md.',17)
    d.save()

if __name__=='__main__':
    IMAGES.mkdir(parents=True,exist_ok=True)
    lcd_images()
    wiring()
    print('Generated three exact firmware LCD examples, overview, wiring.svg and wiring.png.')
