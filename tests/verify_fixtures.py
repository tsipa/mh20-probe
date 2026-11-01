"""Replay real IQ through the reference demodulator and actual C++ firmware edge decoder."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import wasmtime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'protocol/reference'))
from auto_probe_dsp import AutoProbeDetector
from protocol_dsp import PulseMessageDecoder

engine = wasmtime.Engine()
store = wasmtime.Store(engine)
e = wasmtime.Instance(store,wasmtime.Module.from_file(engine,str(ROOT/'build/tests/outputs.wasm')),[]).exports(store)

def call(name,*args):
    return e[name](store,*args)

def micros(seconds):
    return round(seconds*1000000)%2**32

class TappedDecoder(PulseMessageDecoder):
    def edge(self,active,seconds):
        # Forward measured FM threshold crossings, not reconstructed ideal frames.
        call('edge',int(active),micros(seconds))
        return super().edge(active,seconds)

class InstrumentedDetector(AutoProbeDetector):
    def _tune(self,hz,elapsed):
        super()._tune(hz,elapsed)
        call('reset')
        self.decoder = TappedDecoder()

def compact(values):
    result=[]
    for value in values:
        if not result or result[-1]!=value:
            result.append(value)
    return result

def blocks(case):
    payload = (ROOT/'fixtures'/case['file']).read_bytes()
    assert len(payload)==case['bytes']
    assert hashlib.sha256(payload).hexdigest()==case['sha256'],case['file']+' checksum mismatch'
    dtype = np.int8 if case['format']=='cs8' else np.dtype('<i2')
    raw = np.frombuffer(payload,dtype=dtype).reshape(-1,2).astype(np.float32)
    iq = (raw[:,0]+1j*raw[:,1])/case['scale']
    size = case['sample_rate_hz']//100
    assert len(iq)%size==0
    for start in range(0,len(iq),size):
        yield iq[start:start+size]

def main():
    manifest = json.loads((ROOT/'fixtures/manifest.json').read_text(encoding='utf-8'))
    cases = {c['name']:c for c in manifest['cases']}
    results=[]
    for case in manifest['cases']:
        call('reset')
        detector = InstrumentedDetector({},sample_rate=case['sample_rate_hz'],center_hz=case['center_hz'])
        messages=[];states=[];cpp=[];transitions=[]
        for iq in blocks(case):
            state = detector.process_iq(iq)
            messages.extend(m for m in detector.chunk_messages if m['locked'])
            mask = call('outputs',micros(state['seconds']))
            if mask in (3,5):cpp.append('free' if mask==3 else 'contact')
            if state['probe_present']:
                if not states or state['state']!=states[-1]:
                    transitions.append(state['seconds'])
                states.append(state['state'])
            else:
                assert state['frequency_hz'] is None,'Stale frequency exposed as current probe'
        expected = case['expected']
        assert compact(states)==expected['confirmed_states'],(case['name'],compact(states))
        assert compact(cpp)==expected['confirmed_states'],(case['name'],'C++',compact(cpp))
        assert len(messages)>=expected['minimum_messages'],(case['name'],len(messages))
        if not expected['confirmed_states']:
            assert not messages and not cpp,'Background must not assert READY or contact'
        if expected['maximum_contact_messages']==0:
            assert not any(m['state']=='contact' for m in messages),'False contact'
        assert len(transitions)==len(expected['confirmed_states'])
        if 'transition_relative_seconds' in expected:
            low,high=expected['transition_relative_seconds']
            assert low<=transitions[1]<=high,(case['name'],transitions)
        frequencies=[m['frequency_hz'] for m in messages]
        if 'frequencies_hz' in expected:
            targets=expected['frequencies_hz'];tol=expected['frequency_tolerance_hz']
            nearest=[min(range(len(targets)),key=lambda i:abs(f-targets[i])) for f in frequencies]
            assert compact(nearest)==[0,1],nearest
            assert all(abs(f-targets[i])<tol for f,i in zip(frequencies,nearest)),frequencies
        results.append({'case':case['name'],'accepted_messages':len(messages),'confirmed_states':compact(states),
                        'firmware_states':compact(cpp),'transitions_seconds':transitions,
                        'frequencies_hz':sorted(set(round(f) for f in frequencies))})

    # Same stream: recorded free probe followed by recorded background. Both
    # implementations must deassert READY; no synthetic pulse or silent samples.
    free = cases['free'];quiet=cases['background']
    call('reset')
    detector=InstrumentedDetector({},sample_rate=free['sample_rate_hz'],center_hz=free['center_hz'])
    for iq in blocks(free):state=detector.process_iq(iq)
    assert state['probe_present'] and call('outputs',micros(state['seconds']))==3
    last = detector.last_message_at
    first_loss=None;first_cpp_loss=None
    for iq in blocks(quiet):
        state=detector.process_iq(iq)
        mask=call('outputs',micros(state['seconds']))
        assert mask!=5,'RF loss must trip the loop without declaring a contact message'
        if not state['probe_present'] and first_loss is None:
            first_loss=state['seconds']
            assert state['frequency_hz'] is None
        if mask==4 and first_cpp_loss is None:first_cpp_loss=state['seconds']
    assert first_loss is not None and first_cpp_loss is not None
    for loss in (first_loss,first_cpp_loss):
        assert .060<=loss-last<=.075,(last,loss)
    results.append({'case':'recorded-free-then-background','last_message_seconds':last,
                    'python_loss_seconds':first_loss,'firmware_loss_seconds':first_cpp_loss})
    result={'passed':True,'fixture_bytes':sum(c['bytes'] for c in manifest['cases']),
            'cases':results,'scope':'Recorded ADC IQ -> Python FM demodulation -> measured edges -> actual ProbeDecoder.h and MachineOutputs.h. Does not model CC1101 slicer, physical GPIO, display SPI or 24V circuitry.'}
    (ROOT/'build/tests/fixtures-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS: real background, FREE, contact/release, frequency hop and 65ms link loss; actual C++ decoder.')

if __name__=='__main__':
    main()
