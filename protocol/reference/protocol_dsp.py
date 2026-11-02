"""Decode the observed four-pulse contact message, with no assumed byte/CRC format."""
import numpy as np
from scipy import signal
from contact_dsp import Decimator, RAW_FS
from signal_meter import SignalMeter


class PulseMessageDecoder:
    """Edge timing decoder; same rules and integer-microsecond arithmetic as firmware ProbeDecoder.h.

    A frame is decided only after its FREE slot has closed: exactly one pulse in the
    1040 and 1560 us slots, exactly one in the CONTACT (3120 us) or FREE (3640 us) slot
    and no other pulse in the frame. Initial acquisition and FREE frames need cadence
    with the previous timing-valid frame; while the link is up a CONTACT frame is
    accepted immediately even off-cadence. A pulse outside the width window, a pulse
    start while the previous pulse has not ended (more than BOUNCE_US after its rising
    edge), or an inactive level while no pulse is open (more than BOUNCE_US after the
    previous falling edge) discards every open frame. A repeated level within BOUNCE_US
    of its edge is bounce and ignored; the pulse keeps the time of its first edge.
    Every timing-valid frame is returned as a message; 'locked' is True when it was accepted.
    tests/verify_decoder.py replays the same edge streams through both decoders.
    """
    MIN_WIDTH_US, MAX_WIDTH_US = 120, 400
    BOUNCE_US = 40
    SLOT_US = 120
    CONTACT_US, FREE_US = 3120, 3640
    FRAME_US = FREE_US+SLOT_US
    PERIOD_US, PERIOD_TOLERANCE_US = 16250, 300
    LINK_TIMEOUT_US = 65000
    CAPACITY = 8

    def __init__(self):
        self.pulses=[]  # (start_us, end_us) of valid-width pulses in open frames
        self.pulse_start=None
        self.pulse_end=None
        self.last_start=None
        self.clock=None
        self.link_up=False
        self.last_message_us=0
        self.state=None  # 'free' or 'contact' after the first accepted frame
        self.locked=False
        self.messages=0

    def edge(self, active, seconds):
        now=round(seconds*1e6)
        message=self._settle(now)
        if active:
            if self.pulse_start is not None:
                if 0<=now-self.pulse_start<=self.BOUNCE_US:return message  # Rising-edge bounce.
                self.pulses.clear()  # Missed falling edge.
            self.pulse_start=now
            return message
        if self.pulse_start is None:
            # Missed rising edge, unless it is bounce just after the previous falling edge.
            if self.pulse_end is None or not 0<=now-self.pulse_end<=self.BOUNCE_US:self.pulses.clear()
            return message
        start=self.pulse_start;self.pulse_start=None;self.pulse_end=now
        if not self.MIN_WIDTH_US<=now-start<=self.MAX_WIDTH_US:
            self.pulses.clear()
            return message
        if len(self.pulses)==self.CAPACITY:del self.pulses[0]
        self.pulses.append((start,now))
        return self._settle(now) or message

    def poll(self, seconds):
        """Commit a frame whose FREE slot has closed; call after all edges up to `seconds`."""
        return self._settle(round(seconds*1e6))

    def link(self, seconds):
        return self.link_up and round(seconds*1e6)-self.last_message_us<self.LINK_TIMEOUT_US

    def _settle(self, now):
        if self.clock is not None and now<self.clock:return None
        self.clock=now
        message=None
        while self.pulses:
            first=self.pulses[0][0]
            if now-first<=self.FRAME_US:break
            if self.pulse_start is not None and self.pulse_start-first<=self.FRAME_US:
                if now-self.pulse_start<=self.MAX_WIDTH_US:break
                self.pulses.clear();break
            frame=[p for p in self.pulses if p[0]-first<=self.FRAME_US]
            state=self._classify(frame)
            if state is None:
                del self.pulses[0];continue
            message=self._commit(state,frame)
            del self.pulses[:4]
        if self.link_up and now-self.last_message_us>=self.LINK_TIMEOUT_US:self.link_up=False
        return message

    def _classify(self, frame):
        if len(frame)!=4:return None
        offsets=[p[0]-frame[0][0] for p in frame]
        if abs(offsets[1]-1040)>self.SLOT_US or abs(offsets[2]-1560)>self.SLOT_US:return None
        if abs(offsets[3]-self.CONTACT_US)<=self.SLOT_US:return 'contact'
        if abs(offsets[3]-self.FREE_US)<=self.SLOT_US:return 'free'
        return None

    def _commit(self, state, frame):
        first=frame[0][0]
        done=max(first+self.FRAME_US,frame[3][1])
        cadence=False
        if self.last_start is not None:
            interval=first-self.last_start
            periods=(interval+self.PERIOD_US//2)//self.PERIOD_US
            cadence=1<=periods<=3 and abs(interval-periods*self.PERIOD_US)<=self.PERIOD_TOLERANCE_US
        linked=self.link_up and done-self.last_message_us<self.LINK_TIMEOUT_US
        self.last_start=first
        self.messages+=1
        self.locked=cadence or (linked and state=='contact')
        if self.locked:
            self.link_up=True;self.last_message_us=done;self.state=state
        return {'seconds':done/1e6,'frame_start_seconds':first/1e6,'state':state,
                'fourth_pulse_offset_us':float(frame[3][0]-first),
                'pulse_widths_us':[float(e-s) for s,e in frame],'locked':self.locked,
                'message_number':self.messages}


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
            found=[self.decoder.edge(bool(logic[i]),(self.fm_samples+i)/25000) for i in changes]
            found.append(self.decoder.poll((self.fm_samples+len(fm))/25000))
            for message in found:
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
