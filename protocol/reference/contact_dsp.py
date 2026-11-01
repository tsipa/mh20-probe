"""Receive-only streaming DSP for the empirically identified contact signal."""
import numpy as np
from scipy import signal
from signal_meter import SignalMeter

RAW_FS = 8000000
RAW_CHUNK_BYTES = int(.005*RAW_FS)*2


class Decimator:
    def __init__(self, fs, factor, taps_per_phase=20):
        self.factor = factor
        self.taps = signal.firwin(taps_per_phase*factor+1, fs/(2*factor), fs=fs, window=('kaiser',5)).astype(np.float32)
        self.history = None

    def process(self, values):
        if len(values)%self.factor:
            raise ValueError('Chunk must contain a multiple of the decimation factor')
        count = len(self.taps)-1
        if self.history is None:
            self.history = np.zeros(count, dtype=values.dtype)
        extended = np.concatenate([self.history, values])
        filtered = signal.upfirdn(self.taps, extended, down=self.factor)
        start = count//self.factor
        output = filtered[start:start+len(values)//self.factor]
        self.history = extended[-count:].copy()
        return output


class ContactState:
    """Short, exact-frequency projections: no FFT bin rounding at short windows."""
    def __init__(self, profile):
        self.profile = profile
        self.width = round(profile['window_seconds']*5000)
        self.history = np.empty(0)
        frequencies = np.array([10,13])*profile['frame_rate_hz']
        self.kernels = np.exp(-2j*np.pi*frequencies[:,None]*np.arange(self.width)/5000)*np.hanning(self.width)
        self.state = 'waiting'
        self.pending_state = None
        self.pending_count = 0

    def process(self, fm, power, elapsed):
        self.history = np.r_[self.history,fm][-self.width:]
        if len(self.history)<self.width or elapsed<.1:
            return {'state':'waiting','seconds':elapsed,'score_db':None,'narrow_power':power}
        block = self.history-self.history.mean()
        p10,p13 = np.abs(self.kernels@block)**2
        score = float(10*np.log10((p10+1e-10)/(p13+1e-10)))
        present = power>self.profile.get('signal_power_threshold',0)
        margin = self.profile['direction']*(score-self.profile['threshold_db'])
        if not present:
            candidate = 'no_signal'
        elif abs(margin)<1 and self.state in ('contact','free'):
            candidate = self.state
        else:
            candidate = 'contact' if margin>0 else 'free'
        if candidate == self.pending_state:
            self.pending_count += 1
        else:
            self.pending_state,self.pending_count = candidate,1
        if self.pending_count>=self.profile.get('confirmation_updates',2):
            self.state = candidate
        return {'state':self.state,'seconds':elapsed,'score_db':score,'narrow_power':power,'signal_present':present,'margin_db':margin}


class ContactDetector:
    def __init__(self, profile):
        self.profile = profile
        self.iq_decimator = Decimator(RAW_FS,40)
        self.narrow_decimator = Decimator(200000,8)
        self.fm_decimator = Decimator(25000,5)
        self.sos = signal.butter(5,35000,fs=200000,output='sos')
        self.filter_state = np.zeros((len(self.sos),2),dtype=np.complex128)
        self.rotation = 0.
        self.previous_iq = None
        self.amplitude_history = np.empty(0)
        self.samples = 0
        self.contact_state = ContactState(profile)
        self.meter = SignalMeter()

    def process(self, payload):
        raw = np.frombuffer(payload,dtype=np.int8).astype(np.float32).reshape(-1,2)
        iq = (raw[:,0]+1j*raw[:,1])/128
        iq -= iq.mean()
        bb = self.iq_decimator.process(iq)
        bb,self.filter_state = signal.sosfilt(self.sos,bb,zi=self.filter_state)
        turns = self.rotation+np.arange(len(bb))*self.profile['mix_offset_hz']/200000
        bb *= np.exp(2j*np.pi*turns)
        self.rotation = (self.rotation+len(bb)*self.profile['mix_offset_hz']/200000)%1
        narrow = self.narrow_decimator.process(bb)
        strength = self.meter.process(narrow)
        previous = narrow[0] if self.previous_iq is None else self.previous_iq
        fm = np.angle(narrow*np.conj(np.r_[previous,narrow[:-1]]))*25000/(2*np.pi)
        self.previous_iq = narrow[-1]
        fm = self.fm_decimator.process(fm)
        self.amplitude_history = np.r_[self.amplitude_history,np.abs(narrow)**2][-1250:]
        self.samples += len(raw)
        elapsed = self.samples/RAW_FS
        power = float(self.amplitude_history.mean())
        return {**self.contact_state.process(fm,power,elapsed),**strength}
