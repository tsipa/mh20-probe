"""Decode the observed four-pulse contact message, with no assumed byte/CRC format."""
from collections import deque
import numpy as np
from scipy import signal
from contact_dsp import Decimator, RAW_FS
from signal_meter import SignalMeter


class PulseMessageDecoder:
    """The same edge-timing algorithm can run on a microcontroller GPIO."""
    def __init__(self):
        self.pulses=deque(maxlen=4)
        self.pulse_start=None
        self.last_start=None
        self.cadence_count=0
        self.locked=False
        self.messages=0

    def edge(self, active, seconds):
        if active:
            self.pulse_start=seconds
            return None
        if self.pulse_start is None:return None
        start=self.pulse_start;self.pulse_start=None
        width=seconds-start
        if not .00012<=width<=.00040:
            self.pulses.clear()
            return None
        self.pulses.append((start,width))
        if len(self.pulses)!=4:return None
        offsets=np.array([p[0]-self.pulses[0][0] for p in self.pulses])
        if max(abs(offsets[1]-.00104),abs(offsets[2]-.00156))>.00012:return None
        targets=np.array([.00312,.00364])
        which=int(np.argmin(abs(targets-offsets[3])))
        if abs(targets[which]-offsets[3])>.00012:return None
        first=self.pulses[0][0]
        cadence=False
        if self.last_start is not None:
            interval=first-self.last_start
            periods=round(interval/.01625)
            cadence=1<=periods<=3 and abs(interval-periods*.01625)<.00030
        self.cadence_count=self.cadence_count+1 if cadence else 1
        self.locked=self.cadence_count>=2
        self.last_start=first
        self.messages+=1
        return {'seconds':seconds,'frame_start_seconds':first,'state':'contact' if which==0 else 'free','fourth_pulse_offset_us':float(offsets[3]*1e6),'pulse_widths_us':[float(p[1]*1e6) for p in self.pulses],'locked':self.locked,'message_number':self.messages}


class DecodedContactDetector:
    def __init__(self,profile):
        self.profile=profile
        # The first stage only needs to reject aliases; later filters select the narrow channel.
        self.first=Decimator(RAW_FS,40,taps_per_phase=8)
        self.second=Decimator(200000,8)
        self.sos=signal.butter(5,35000,fs=200000,output='sos')
        self.zi=np.zeros((len(self.sos),2),dtype=np.complex128)
        self.fm_zi=np.zeros(4)
        self.rotation=0.
        self.previous_iq=None
        self.previous_logic=False
        self.amplitude=np.empty(0)
        self.samples=0
        self.fm_samples=0
        self.decoder=PulseMessageDecoder()
        self.latest=None
        self.chunk_messages=[]
        self.meter=SignalMeter()

    def process(self,payload):
        raw=np.frombuffer(payload,dtype=np.int8).astype(np.float32).reshape(-1,2)
        iq=(raw[:,0]+1j*raw[:,1])/128; iq-=iq.mean()
        bb=self.first.process(iq)
        bb,self.zi=signal.sosfilt(self.sos,bb,zi=self.zi)
        turns=self.rotation+np.arange(len(bb))*self.profile['mix_offset_hz']/200000
        bb*=np.exp(2j*np.pi*turns)
        self.rotation=(self.rotation+len(bb)*self.profile['mix_offset_hz']/200000)%1
        narrow=self.second.process(bb)
        strength=self.meter.process(narrow)
        previous=narrow[0] if self.previous_iq is None else self.previous_iq
        fm=np.angle(narrow*np.conj(np.r_[previous,narrow[:-1]]))*25000/(2*np.pi)
        self.previous_iq=narrow[-1]
        fm,self.fm_zi=signal.lfilter(np.ones(5)/5,[1],fm,zi=self.fm_zi)
        self.amplitude=np.r_[self.amplitude,abs(narrow)**2][-1250:]
        power=float(self.amplitude.mean())
        self.samples+=len(raw);elapsed=self.samples/RAW_FS
        present=power>self.profile['signal_power_threshold']
        self.chunk_messages=[]
        if present and elapsed>=.1:
            logic=fm<-1800
            changes=np.flatnonzero(np.diff(np.r_[self.previous_logic,logic].astype(np.int8)))
            for i in changes:
                message=self.decoder.edge(bool(logic[i]),(self.fm_samples+i)/25000)
                if message is not None:
                    self.chunk_messages.append(message)
                    if message['locked']:self.latest=message
            self.previous_logic=bool(logic[-1])
        else:
            self.decoder=PulseMessageDecoder();self.latest=None;self.previous_logic=False
        self.fm_samples+=len(fm)
        recent=self.latest is not None and elapsed-self.latest['seconds']<.065
        state='waiting' if elapsed<.1 else 'no_signal' if not present else self.latest['state'] if recent else 'unknown'
        return {'state':state,'seconds':elapsed,'score_db':None,'narrow_power':power,'signal_present':present,'fourth_pulse_offset_us':self.latest['fourth_pulse_offset_us'] if recent else None,'message_number':self.decoder.messages,'decoder':'four-pulse timing',**strength}
