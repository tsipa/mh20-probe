"""Compare exact firmware strip painting with full-canvas Adafruit rendering."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
import wasmtime

ROOT=Path(__file__).resolve().parents[1]/'build/tests'
engine=wasmtime.Engine();store=wasmtime.Store(engine)
e=wasmtime.Instance(store,wasmtime.Module.from_file(engine,str(ROOT/'display_raster.wasm')),[]).exports(store)
e['__wasm_call_ctors'](store)
previews=[]
for state in (0,1,2):
    assert e['render'](store,state)==0,'Strip clipping or partial update differs from full frame'
    assert e['allocations'](store)==0,'Display must not call malloc, even for its strip buffer'
    assert e['stripeBytes'](store)==3840 and e['maxHeight'](store)<=8
    address=e['framebuffer'](store)
    raw=e['memory'].read(store,address,address+240*240*2)
    pixels=np.frombuffer(raw,dtype='<u2').reshape(240,240)
    assert (pixels==65535).sum()>500,'Text disappeared'
    rgb=np.stack(((pixels>>11)*255//31,((pixels>>5)&63)*255//63,(pixels&31)*255//31),axis=-1).astype('uint8')
    previews.append(Image.fromarray(rgb))
preview=Image.new('RGB',(240*3,240))
for i,picture in enumerate(previews):preview.paste(picture,(i*240,0))
folder=ROOT/'display-validation';folder.mkdir(exist_ok=True)
preview.save(folder/'strip-preview.png')
result={'passed':True,'pixel_buffer_bytes':3840,'heap_allocations':0,'cases':['red/green/blue','exact Adafruit font clipping across strips','partial updates erase old longer text','8+2 pixel footer','framebuffer bounds guards'],
        'scope':'Actual DisplayRaster.h and installed Adafruit_GFX.cpp in WASM; this test does not exercise physical SPI/display timing.'}
(folder/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS: exact Adafruit pixels, partial repaint, 8-row strips, bounds and zero heap allocations.')
