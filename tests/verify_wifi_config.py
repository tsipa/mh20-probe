"""Check UART framing, credential validation and corrupted stored settings."""
from pathlib import Path
import wasmtime
engine=wasmtime.Engine(); store=wasmtime.Store(engine)
p=Path(__file__).resolve().parents[1]/'build/tests/wifi_config.wasm'
e=wasmtime.Instance(store,wasmtime.Module.from_file(engine,str(p)),[]).exports(store)
def call(name,*args): return e[name](store,*args)
def line(text,ending='\n'):
    results=[call('feed',b) for b in (text+ending).encode()]
    return results[-1]
def value(kind):
    return bytes(call(kind+'Byte',i) for i in range(call(kind+'Length'))).decode()
call('reset'); assert call('mode')==1 and call('valid')==1
assert line('wifi mode sta')==2; assert call('mode')==2 and call('valid')==0
assert line('wifi ssid Workshop 2.4 GHz','\r\n')==2
assert value('ssid')=='Workshop 2.4 GHz'; assert call('valid')==1
assert line('wifi password abcd1234')==2; assert value('password')=='abcd1234'
assert line('wifi password short')==2; assert call('valid')==0
assert line('wifi password')==2; assert call('passwordLength')==0 and call('valid')==1
assert line('wifi mode apsta')==2; assert call('mode')==3
assert line('wifi mode bad')==3; assert call('mode')==3
assert line('wifi ssid '+'x'*33)==3; assert value('ssid')=='Workshop 2.4 GHz'
assert line('wifi ssid '+'x'*32)==2; assert call('ssidLength')==32
assert line('wifi password '+'a'*63)==2; assert call('valid')==1
assert line('wifi password '+'A1'*32)==2; assert call('valid')==1
assert line('wifi password '+'z'*64)==2; assert call('valid')==0
assert line('wifi password '+'a'*65)==3; assert call('passwordLength')==64
assert line('wifi password '+'a'*8)==2
assert line('wifi ssid quote" and slash\\')==2
assert value('ssid')=='quote" and slash\\'
assert line('wifi ssid '+'x'*250)==99
assert value('ssid')=='quote" and slash\\'
assert line('wifi ssid bad\x00text')==99
assert line('wifi status')==5
assert line('wifi save')==6
assert line('wifi reset')==7
assert line('wifi reboot')==8
assert line('wifi access')==9
assert line('wifi help')==4
assert line('unknown')==1
for kind in range(4): assert call('badStorage',kind)==0
call('reset'); assert call('mode')==1 and call('passwordLength')==0
print('PASS: UART settings, boundaries, CRLF, oversized lines, controls and corrupt storage.')

for flags,label in ((0,'WiFi OFF'),(2,'WiFi OFF'),(3,'WiFi AP'),(5,'WiFi CLIENT NOT CONNECTED'),(13,'WiFi CLIENT CONNECTED'),(7,'WiFi AP+CLIENT NOT CONNECTED'),(15,'WiFi AP+CLIENT CONNECTED')):
    actual=bytes(call('displayByte',flags,i) for i in range(len(label))).decode()
    assert actual==label
print('PASS: AP/client/connected/off display labels.')
