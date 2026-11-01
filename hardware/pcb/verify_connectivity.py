"""Compare a KiCad XML schematic netlist against the generated PCB pad report."""
from pathlib import Path
import json,sys,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parent
netlist=ET.parse(sys.argv[1]).getroot()
actual={(n.attrib['ref'],n.attrib['pin']):net.attrib['name'].lstrip('/') for net in netlist.findall('./nets/net') for n in net.findall('node')}
data=json.loads((root/'connectivity.json').read_text())
expected={(p['ref'],p['pin']):p['net'].lstrip('/') for p in data['pads'] if p['net']}
connected={k:v for k,v in actual.items() if not v.startswith('unconnected-')}
assert connected==expected,[(k,expected.get(k),connected.get(k)) for k in expected.keys()|connected.keys() if expected.get(k)!=connected.get(k)]
assert all(0<=p['xy'][0]<=data['board_mm'][0] and 0<=p['xy'][1]<=data['board_mm'][1] for p in data['pads'])
print(f'{len(expected)} connected pads match; all pads inside the board outline.')
