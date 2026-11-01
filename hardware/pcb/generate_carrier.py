"""Generate the module carrier in KiCad. Run with KiCad's bundled Python."""
from pathlib import Path
import json, csv, os, sys, uuid, math
import pcbnew as pcb
ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'design.json').read_text())
LIB=Path(os.environ.get('KICAD10_FOOTPRINT_DIR',str(Path(sys.executable).parents[1]/'share/kicad/footprints')))
ORIGIN=(50,50)
LOCAL=ROOT/'Carrier.pretty'
LOCAL.mkdir(exist_ok=True)
def uid(): return str(uuid.uuid4())
def q(s): return json.dumps(str(s))
def v(x,y): return pcb.VECTOR2I(round(x*1000000),round(y*1000000))
def point(x,y): return v(x+ORIGIN[0],y+ORIGIN[1])
board=pcb.BOARD()
netnames=sorted({n for c in DATA['parts'] for n in c['pins'].values() if n})
nets={}
for name in netnames:
 net=pcb.NETINFO_ITEM(board,"/"+name);board.Add(net);nets[name]=net

def fp_line(fp,x1,y1,x2,y2,layer=pcb.F_Fab,width=.12):
 item=pcb.PCB_SHAPE(fp);item.SetShape(pcb.SHAPE_T_SEGMENT);item.SetStart(v(x1,y1));item.SetEnd(v(x2,y2));item.SetLayer(layer);item.SetWidth(pcb.FromMM(width));fp.Add(item)
def rect(fp,x1,y1,x2,y2,layer=pcb.F_Fab):
 for a,b,c,d in ((x1,y1,x2,y1),(x2,y1,x2,y2),(x2,y2,x1,y2),(x1,y2,x1,y1)):fp_line(fp,a,b,c,d,layer)
def pad(fp,number,x,y,diam=1.8,drill=1):
 p=pcb.PAD(fp);p.SetNumber(str(number));p.SetAttribute(pcb.PAD_ATTRIB_PTH);p.SetShape(pcb.PAD_SHAPE_RECT if str(number)=='1' else pcb.PAD_SHAPE_OVAL);p.SetPosition(v(x,y));p.SetSize(v(diam,diam));p.SetDrillSize(v(drill,drill));p.SetLayerSet(pcb.PAD.PTHMask());fp.Add(p)
def custom(c):
 f=pcb.FOOTPRINT(board);f.SetFPID(pcb.LIB_ID('Carrier',c['kind']));f.SetAttributes(pcb.FP_THROUGH_HOLE)
 if c['kind']=='esp32':
  for i in range(19):pad(f,i+1,-12.7,i*2.54);pad(f,i+20,12.7,i*2.54)
  rect(f,-13.97,-7.3,13.97,47.01);rect(f,-9,-7.3,9,-1.3,pcb.F_SilkS)
 elif c['kind']=='dcdc':
  for n,(x,y) in {1:(-10.16,-2.54),2:(-10.16,2.54),3:(10.16,10.16),4:(10.16,0),5:(10.16,-10.16),6:(-10.16,-10.16)}.items():pad(f,n,x,y,2.1,1.1)
  rect(f,-12.7,-12.7,12.7,12.7,pcb.F_SilkS)
 elif c['kind']=='lcd':
  for i in range(7):pad(f,i+1,-7.62+i*2.54,-17.78)
  rect(f,-14,-20,14,20);rect(f,-12,-13.5,12,10.5)
 else:raise ValueError(c['kind'])
 return f

footprints={}
for c in DATA['parts']:
 kind=c['kind']
 if kind in ('esp32','dcdc','lcd'):f=custom(c)
 else:
  names={'terminal':('TerminalBlock_Phoenix','TerminalBlock_Phoenix_MKDS-1,5-6-5.08_1x06_P5.08mm_Horizontal'),'rf':('Connector_PinHeader_2.54mm','PinHeader_2x04_P2.54mm_Vertical'),'control':('Connector_PinHeader_2.54mm','PinHeader_1x05_P2.54mm_Vertical'),'contacts':('Connector_PinHeader_2.54mm','PinHeader_1x04_P2.54mm_Vertical'),'jumper':('Connector_PinHeader_2.54mm','PinHeader_1x02_P2.54mm_Vertical')}
  lib,name=names[kind];f=pcb.FootprintLoad(str(LIB/(lib+'.pretty')),name)
  if not f:raise RuntimeError(name)
  f.SetFPID(pcb.LIB_ID(lib,name))
 f.SetReference(c['ref']);f.SetValue(c['value']);board.Add(f)
 if kind in ('esp32','dcdc','lcd'):pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(LOCAL),f)
 for p in f.Pads():
  name=c['pins'].get(p.GetNumber())
  if name:p.SetNet(nets[name])
 f.SetPosition(point(*c['xy']));f.SetOrientationDegrees(c.get('angle',0))
 if c['side']=='back':f.Flip(f.GetPosition(),False)
 f.Reference().SetVisible(False);f.Value().SetVisible(False)
 footprints[c['ref']]=f
 c['footprint_id']=str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName())

def draw_line(x1,y1,x2,y2,layer=pcb.Edge_Cuts,width=.1):
 item=pcb.PCB_SHAPE();item.SetShape(pcb.SHAPE_T_SEGMENT);item.SetStart(point(x1,y1));item.SetEnd(point(x2,y2));item.SetLayer(layer);item.SetWidth(pcb.FromMM(width));board.Add(item)
def text(value,x,y,layer=pcb.F_SilkS,size=1):
 t=pcb.PCB_TEXT(board);t.SetText(value);t.SetPosition(point(x,y));t.SetTextSize(v(size,size));t.SetTextThickness(pcb.FromMM(.15));t.SetLayer(layer);board.Add(t)
def hole(ref,x,y):
 f=pcb.FOOTPRINT(board);f.SetReference(ref);f.SetValue('M3');f.SetFPID(pcb.LIB_ID('Carrier','Mount_M3'));f.Reference().SetVisible(False);f.Value().SetVisible(False)
 p=pcb.PAD(f);p.SetAttribute(pcb.PAD_ATTRIB_NPTH);p.SetShape(pcb.PAD_SHAPE_CIRCLE);p.SetDrillSize(v(3.2,3.2));p.SetSize(v(3.2,3.2));p.SetLayerSet(pcb.PAD.PTHMask());p.SetPosition(v(0,0));f.Add(p);pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(LOCAL),f);f.SetPosition(point(x,y));board.Add(f)
for a,b,c,d in ((0,0,120,0),(120,0,120,100),(120,100,0,100),(0,100,0,0)):draw_line(a,b,c,d)
for i,(x,y) in enumerate(((5,5),(115,5),(115,95),(5,95))):hole('H'+str(i+1),x,y)
# Output module is bolted to a generic reserve area, with short labelled jumpers.
for a,b,c,d in ((12,8,67,8),(67,8,67,46),(67,46,12,46),(12,46,12,8)):draw_line(a,b,c,d,pcb.Dwgs_User,.2)
text('DC OUTPUT MODULE',38,24,pcb.Dwgs_User,1.6)
text('RESERVED 55 x 38 mm',38,28,pcb.Dwgs_User,1)
text('J4: 5V GND PROBE READY 3V3',63,8,pcb.F_SilkS,.8)
text('J5: PROBE A/B  READY A/B',34,7,pcb.F_SilkS,.8)
text('LCD CENTER',60,73,pcb.F_SilkS,1.2)
text('URB2405YMD-6WR3',25,65,pcb.F_SilkS,.9)
text('JP1 REMOVE FOR USB',55,86,pcb.F_SilkS,.9)
text('CC1101 / SMA TO EDGE',99,79,pcb.F_SilkS,.9)
text('M&H RECEIVER CARRIER',60,95,pcb.F_SilkS,1.4)
text('PROTOTYPE - OUTPUT MODULE TO VERIFY',60,98,pcb.F_SilkS,.8)
for i,label in enumerate(('24V','0V','P-A','P-B','R-A','R-B')):text(label,15,27+5.08*i,pcb.F_SilkS,.9)
# Copper-free margins around the external RF antenna and the ESP32 PCB antenna.
for x1,y1,x2,y2 in ((83,0,117,11),(85,83,116,100)):
 zone=pcb.ZONE(board);zone.SetIsRuleArea(True);zone.SetLayerSet(pcb.LSET.AllCuMask());zone.SetDoNotAllowZoneFills(True);zone.SetDoNotAllowTracks(True);zone.SetDoNotAllowVias(True);zone.SetDoNotAllowPads(False);zone.SetDoNotAllowFootprints(False)
 poly=zone.Outline();poly.NewOutline()
 for x,y in ((x1,y1),(x2,y1),(x2,y2),(x1,y2)):p=point(x,y);poly.Append(p.x,p.y)
 board.Add(zone)
# Labels indicate backside mounting; native flip preserves pad numbering.
text('ESP32 DIRECT SOLDER / BACK',100,65,pcb.Dwgs_User,.9)
if (ROOT/'routes.json').exists() and '--unrouted' not in sys.argv:
 for row in json.loads((ROOT/'routes.json').read_text()):
  t=pcb.PCB_VIA(board) if row['kind']=='via' else pcb.PCB_TRACK(board)
  t.SetNet(nets[row['net']]);t.SetWidth(pcb.FromMM(row['width']))
  if row['kind']=='via':t.SetPosition(point(*row['at']));t.SetDrill(pcb.FromMM(row['drill']));t.SetViaType(pcb.VIATYPE_THROUGH);t.SetLayerPair(pcb.F_Cu,pcb.B_Cu)
  else:t.SetStart(point(*row['start']));t.SetEnd(point(*row['end']));t.SetLayer(board.GetLayerID(row['layer']))
  board.Add(t)
pcb.SaveBoard(str(ROOT/'receiver_carrier.kicad_pcb'),board)
(ROOT/'receiver_carrier.kicad_pro').write_text(json.dumps({'meta':{'filename':'receiver_carrier.kicad_pro','version':1},'text_variables':{'DESIGN_STATUS':'PROTOTYPE'}},indent=2)+'\n')
# Schematic: labelled functional module symbols, including every header pin.
root_id=uid();defs=[];instances=[];wires=[];labels=[];ncs=[]
for c in DATA['parts']:
 ref=c['ref'];items=list(c['pins'].items());half=(len(items)+1)//2
 if c['kind']=='esp32':half=19
 sides=(items[:half],items[half:]);height=max(len(x) for x in sides)*2.54+2.54
 symname='Module_'+ref;libid='Carrier:'+symname
 body=f'(symbol {q(symname+"_0_1")} (rectangle (start -12.7 {height/2}) (end 12.7 {-height/2}) (stroke (width 0.254) (type default)) (fill (type background))))'
 pins=[];positions=[]
 for side,group in enumerate(sides):
  for i,(num,name) in enumerate(group):
   x=-17.78 if side==0 else 17.78;y=(len(group)-1)*1.27-i*2.54;angle=0 if side==0 else 180
   pinname=name or 'NC';pins.append(f'(pin passive line (at {x} {y} {angle}) (length 5.08) (name {q(pinname)} (effects (font (size 1.0 1.0)))) (number {q(num)} (effects (font (size 1.0 1.0)))))')
   positions.append((num,name,x,y,side))
 definition=f'(symbol {q(libid)} (pin_names (offset 0.5)) (in_bom yes) (on_board yes) (property "Reference" {q(ref)} (at 0 {height/2+2.54} 0) (effects (font (size 1.27 1.27)))) (property "Value" {q(c["value"])} (at 0 {-height/2-2.54} 0) (effects (font (size 1.0 1.0)))) {body} (symbol {q(symname+"_1_1")} {" ".join(pins)}))'
 defs.append(definition)
 x,y=c['sch'];sid=uid()
 instances.append(f'(symbol (lib_id {q(libid)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {sid}) (property "Reference" {q(ref)} (at {x} {y-height/2-2.54} 0) (effects (font (size 1.27 1.27)))) (property "Value" {q(c["value"])} (at {x} {y+height/2+2.54} 0) (effects (font (size 1.0 1.0)))) (property "Footprint" {q(c["footprint_id"])} (at {x} {y} 0) (effects (font (size 1.0 1.0)) hide)) '+ ' '.join(f'(pin {q(num)} (uuid {uid()}))' for num,_ in items)+f' (instances (project "receiver_carrier" (path "/{root_id}" (reference {q(ref)}) (unit 1)))))')
 for num,name,px,py,side in positions:
  ax=round(x+px,4);ay=round(y-py,4);endx=round(ax+(-5.08 if side==0 else 5.08),4)
  if not name:ncs.append(f'(no_connect (at {ax} {ay}) (uuid {uid()}))');continue
  wires.append(f'(wire (pts (xy {ax} {ay}) (xy {endx} {ay})) (stroke (width 0) (type default)) (uuid {uid()}))')
  labels.append(f'(label {q(name)} (at {endx} {ay} 0) (effects (font (size 1.0 1.0)) (justify {"right" if side==0 else "left"} bottom)) (uuid {uid()}))')
schematic=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {root_id}) (paper "A3") (title_block (title "m&h receiver - module carrier") (rev "P1") (comment 1 "Prototype: output module not yet qualified")) (lib_symbols '+ '\n'.join(defs)+')\n'+'\n'.join(wires+labels+ncs+instances)+'\n(sheet_instances (path "/" (page "1"))))\n'
for c,instance in zip(DATA['parts'],instances):
 import re
 sid=re.search(r'\(uuid ([^)]*)\)',instance).group(1)
 path=pcb.KIID_PATH();path.push_back(pcb.KIID(root_id));path.push_back(pcb.KIID(sid));footprints[c['ref']].SetPath(path)
pcb.SaveBoard(str(ROOT/'receiver_carrier.kicad_pcb'),board)
(ROOT/'receiver_carrier.kicad_sch').write_text(schematic,encoding='utf-8')
libdefs=[d.replace(q('Carrier:Module_'+c['ref']),q('Module_'+c['ref']),1) for c,d in zip(DATA['parts'],defs)]
(ROOT/'Carrier.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+ '\n'.join(libdefs)+')\n',encoding='utf-8')
with (ROOT/'bom.csv').open('w',newline='',encoding='utf-8') as out:
 w=csv.writer(out);w.writerow(['Reference','Item','Quantity','Notes'])
 for c in DATA['parts']:w.writerow([c['ref'],c['value'],1,'Direct solder' if c['kind']=='esp32' else ''])
 w.writerow(['EXT1','Two-channel DC photorelay module',1,'Not selected; must match interface requirements in README'])
 w.writerow(['H1-H4','M3 board mounting hardware',4,''])
# Store only relative coordinates, no machine paths or private workstation data.
report={'board_mm':DATA['board_mm'],'footprints':len(DATA['parts']),'nets':len(nets),'routed':bool(list(board.GetTracks())),'pads':[]}
for f in footprints.values():
 for p in f.Pads():
  pos=p.GetPosition();report['pads'].append({'ref':f.GetReference(),'pin':p.GetNumber(),'net':p.GetNetname(),'xy':[round(pos.x/1e6-50,4),round(pos.y/1e6-50,4)],'size':[p.GetSize().x/1e6,p.GetSize().y/1e6]})
(ROOT/'connectivity.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Generated native schematic, PCB, BOM and connectivity:',len(DATA['parts']),'footprints,',len(nets),'nets')
