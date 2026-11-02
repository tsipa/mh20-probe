"""Extract unchanged ADC bytes from the full recordings; normally not needed for tests."""
from pathlib import Path
import argparse
import hashlib
import json
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, required=True, help='Directory with touches-full.cs8, background-full.cs8 and sweep-full.wav')
    args = p.parse_args()
    dest = ROOT/'fixtures'
    dest.mkdir(exist_ok=True)
    touch = 'touches-full.cs8'
    background = 'background-full.cs8'
    sweep = 'sweep-full.wav'
    specs = [
        ('background',background,2.00,.20,[],0),
        ('free',touch,2.00,.20,['free'],5),
        ('contact-on',touch,5.20,.45,['free','contact'],12),
        ('contact-off',touch,7.50,.45,['contact','free'],12),
        ('channel-hop',sweep,8.05,.45,['free'],12),
    ]
    hashes = {}
    entries = []
    for name, source, start, duration, states, minimum in specs:
        path = args.source_root/source
        if source not in hashes:
            with path.open('rb') as f:
                hashes[source] = hashlib.file_digest(f,'sha256').hexdigest()
        if path.suffix=='.wav':
            fs, data = wavfile.read(path, mmap=True)
            assert data.dtype.str=='<i2' and data.shape[1]==2
            assert fs==2000000
            first = round(start*fs)
            count = round(duration*fs)
            payload = data[first:first+count].tobytes()
            byte_offset = data.offset+first*4
            fmt = 'ci16'
            center = 433912004
        else:
            fs = 8000000
            byte_offset = round(start*fs)*2
            with path.open('rb') as f:
                f.seek(byte_offset)
                payload = f.read(round(duration*fs)*2)
            fmt = 'cs8'
            center = 434000000
        filename = name+'.'+fmt
        (dest/filename).write_bytes(payload)
        expected = {'confirmed_states':states, 'minimum_messages':minimum,
                    'transition_count':1 if len(states)==2 else 0,
                    'maximum_contact_messages':0 if 'contact' not in states else None}
        if name=='channel-hop':
            expected['frequencies_hz']=[433721391,433746355]
            expected['frequency_tolerance_hz']=1000
        if name=='contact-on':
            expected['transition_relative_seconds']=[.15,.35]
        if name=='contact-off':
            expected['transition_relative_seconds']=[.15,.35]
        entries.append({'name':name,'file':filename,'format':fmt,'sample_rate_hz':fs,'center_hz':center,
                        'iq_order':'I,Q','byte_order':'little' if fmt=='ci16' else 'not applicable',
                        'scale':32768 if fmt=='ci16' else 128,'bytes':len(payload),
                        'duration_seconds':duration,'sha256':hashlib.sha256(payload).hexdigest(),
                        'source':{'recording':source,'bytes':path.stat().st_size,
                                  'sha256':hashes[source],'start_seconds':start,'byte_offset':byte_offset},
                        'expected':expected})
    manifest = {'schema_version':1,'description':'Real recorded ADC samples, no filtering, synthesis or IQ resampling.',
                'label_basis':'Contact transitions from frames decoded in the full recording, matched to the touches made during recording; channel hop from sweep measurements. Counts are loose bounds, not snapshots of current test output.',
                'capture_setup_cs8':{'lna_gain_db':8,'vga_gain_db':10,'bandwidth_hz':5000000,'amplifier':False},
                'capture_setup_wav':'SDR++ baseband recording; gain not preserved in WAV header.',
                'cases':entries}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Extracted '+str(sum(e['bytes'] for e in entries))+' bytes of real IQ.')

if __name__=='__main__':
    main()
