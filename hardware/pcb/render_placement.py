"""Draw the module placement plan; dimensions marked approximate need measurement."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent
im=Image.new('RGB',(1440,1160),'#f5f3ee');d=ImageDraw.Draw(im)
font=ImageFont.truetype('arial.ttf',21);small=ImageFont.truetype('arial.ttf',17);title=ImageFont.truetype('arial.ttf',29)
def box(coords,fill,outline='#263c3e',width=3):d.rounded_rectangle(tuple(70+x*10 for x in coords),radius=7,fill=fill,outline=outline,width=width)
def label(x,y,text,fill='#203237',f=font):d.multiline_text((70+x*10,70+y*10),text,font=f,fill=fill,spacing=5)
d.text((70,20),'Module carrier — 120 × 100 mm',font=title,fill='#203237')
box((0,0,120,100),'#3f7160')
# Back-mounted assemblies are shown as translucent-looking outlined areas in the front view.
box((12,8,67,46),'#567a69',outline='#c8d7c1',width=2)
label(16,9,'2 × POLOLU 5420 / BACK','#ecf2df',small)
box((18,17,38.3,25.1),'#29483c')
box((18,32,38.3,40.1),'#29483c')
label(20,19,'PROBE','#ecf2df',small)
label(20,34,'READY','#ecf2df',small)
box((86,5.7,114,60),'#566b64',outline='#c8d7c1',width=2)
label(89,18,'ESP32\nBACK\n38 pins','#ecf2df')
label(88,8,'ANTENNA','#dbe9c5',small)
box((46,30,74,70),'#376dae')
box((48,36.5,72,60.5),'#132731',outline='#91b3c9',width=2)
label(50,46,'ST7789\n240 × 240','#c6e1e9')
label(48,64,'DISPLAY','#f4f6e8',small)
box((12.3,68.3,37.7,93.7),'#283034')
label(14,74,'ISOLATED\n24 V → 5 V\nURB2405','#f3efe5')
box((87,65,107,95),'#376dae')
label(89,72,'CC1101\nRF','#e5eaf1')
label(86,96,'SMA TO EDGE','#ebeddb',small)
box((2,24.4,12,55.4),'#6ca36a')
for i,t in enumerate(('+24V','0V','P-A','P-B','R-A','R-B')):
 d.ellipse((70+5*10,70+(27+i*5.08)*10-9,70+5*10+18,70+(27+i*5.08)*10+9),fill='#c8d3cf')
 label(13,26+i*5.08,t,'#f9f7e8',small)
for x,y,count in ((68,14,5),(23,12,4),(48,81,2)):
 for i in range(count):
  px=x+(i*2.54 if y!=81 else 0);py=y+(i*2.54 if y==81 else 0)
  d.rectangle((70+px*10-5,70+py*10-5,70+px*10+5,70+py*10+5),fill='#edc56c')
label(42,86,'JP1: remove\nfor USB','#f6f5e8',small)
for x,y in ((5,5),(115,5),(115,95),(5,95)):
 d.ellipse((70+x*10-16,70+y*10-16,70+x*10+16,70+y*10+16),fill='#f5f3ee')
d.text((70,1090),'Placement plan · front view · module bodies approximate · Pololu 5420 outputs selected; machine timing unverified',font=small,fill='#203237')
(ROOT/'preview').mkdir(exist_ok=True)
im.save(ROOT/'preview/assembly-plan.png')
