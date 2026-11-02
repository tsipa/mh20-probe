"""Find RF candidates across the band; confirm probe presence by pulse timing."""
import numpy as np
from collections import deque
from scipy import fft, signal
from contact_dsp import Decimator, RAW_FS
from protocol_dsp import PulseMessageDecoder
from signal_meter import SignalMeter


class AutoProbeDetector:
    def __init__(self, profile, sample_rate=RAW_FS, center_hz=None):
        self.fs = sample_rate
        self.receiver_center_hz = center_hz if center_hz is not None else profile.get('auto_receiver_center_hz',434012500)
        self.minimum = profile.get('search_min_hz',433000000)
        self.maximum = profile.get('search_max_hz',435000000)
        if self.fs % 200000: raise ValueError('Sample rate must be a multiple of 200 kHz.')
        self.nfft = 2**round(np.log2(self.fs/500))
        self.window = signal.windows.hann(self.nfft,sym=False).astype(np.float32)
        f = fft.fftfreq(self.nfft,1/self.fs)
        self.frequencies = f+self.receiver_center_hz
        self.allowed = ((self.frequencies>=self.minimum)&(self.frequencies<=self.maximum)&
                        (abs(f)>self.fs/self.nfft*1.5)&(abs(f)<self.fs*.48))
        self.samples = 0
        self.tuned_hz = None
        self.latest = None
        self.last_frequency_hz = None
        self.chunk_messages = []
        self.message_count = 0
        self.recent_messages = deque()
        self.last_message_at = None
        self.scan_at = -1.
        self.trial_at = 0.
        self.rf_at = -1.
        self.seen_frequency = None
        self.seen_count = 0
        self.trial_frequency = None
        self.trial_count = 0
        self.blocked = []
        self.meter = SignalMeter()

    def _peaks(self, iq):
        z = iq[:self.nfft]
        spectrum = abs(fft.fft((z-z.mean())*self.window))**2
        floor = max(float(np.median(spectrum[self.allowed]))/np.log(2),1e-20)
        peaks,_ = signal.find_peaks(spectrum,distance=8)
        peaks = peaks[self.allowed[peaks]]
        peaks = peaks[np.argsort(spectrum[peaks])[-8:]][::-1]
        candidates = []
        for k in peaks:
            snr = 10*np.log10(max(float(spectrum[k]),1e-20)/floor)
            if snr<14: continue
            values = np.log(np.maximum(spectrum[np.array([k-1,k,k+1])%self.nfft],1e-20))
            denominator = values[0]-2*values[1]+values[2]
            delta = np.clip(.5*(values[0]-values[2])/denominator,-.5,.5) if denominator else 0.
            hz = float(self.frequencies[k]+delta*self.fs/self.nfft)
            candidates.append((hz,float(snr)))
        return candidates

    def _tune(self, hz, elapsed):
        self.tuned_hz = hz
        self.trial_at = elapsed
        self.first = Decimator(self.fs,self.fs//200000,taps_per_phase=8)
        self.second = Decimator(200000,8)
        self.decoder = PulseMessageDecoder()
        self.latest = None
        self.previous_iq = None
        self.previous_logic = False
        self.fm_zi = np.zeros(4)
        self.meter = SignalMeter()
        self.oscillator = None
        self.rotation = 1.+0j

    def process(self,payload):
        raw = np.frombuffer(payload,dtype=np.int8).astype(np.float32).reshape(-1,2)
        return self.process_iq((raw[:,0]+1j*raw[:,1])/128)

    def process_iq(self,iq):
        if len(iq)<self.nfft or len(iq)%(self.fs//25000):
            raise ValueError('Use blocks of at least one FFT and a multiple of the 25 kHz decimation factor.')
        start = self.samples/self.fs
        self.samples += len(iq)
        elapsed = self.samples/self.fs
        self.chunk_messages = []
        recent = self.latest is not None and elapsed-self.latest['seconds']<.065
        if elapsed-self.scan_at >= (.05 if recent else .009):
            self.scan_at = elapsed
            peaks = self._peaks(iq)
            self.blocked = [(hz,until) for hz,until in self.blocked if until>elapsed]
            if not recent and self.tuned_hz is not None and elapsed-self.trial_at>.10:
                self.blocked.append((self.tuned_hz,elapsed+.30))
                self.tuned_hz = None
                self.latest = None
            available = [p for p in peaks if not any(abs(p[0]-hz)<2000 for hz,until in self.blocked)]
            best = available[0][0] if available else None
            strongest = peaks[0][0] if peaks else None
            if strongest is not None:
                self.seen_count = self.seen_count+1 if self.seen_frequency is not None and abs(strongest-self.seen_frequency)<1500 else 1
                self.seen_frequency = strongest
                if self.seen_count>=2:
                    self.rf_at = elapsed
            else:
                self.seen_frequency = None; self.seen_count = 0
            if best is not None:
                self.trial_count = self.trial_count+1 if self.trial_frequency is not None and abs(best-self.trial_frequency)<1500 else 1
                self.trial_frequency = best
                if self.trial_count>=2 and not recent and (self.tuned_hz is None or abs(best-self.tuned_hz)>6000):
                    self._tune(best,elapsed)
            else:
                self.trial_frequency = None; self.trial_count = 0
        strength = self.meter.values if self.tuned_hz is not None else {'channel_dbfs':None,'snr_db':None,'noise_dbfs':None}
        if self.tuned_hz is not None:
            if self.oscillator is None or len(self.oscillator)!=len(iq):
                offset = self.tuned_hz-self.receiver_center_hz
                self.oscillator = np.exp(-2j*np.pi*offset*np.arange(len(iq))/self.fs).astype(np.complex64)
                self.advance = complex(np.exp(-2j*np.pi*offset*len(iq)/self.fs))
            # Raw HackRF IQ has a large DC offset. Remove it before moving a
            # nearby probe channel to baseband, otherwise it masks the FSK tones.
            mixed = (iq-iq.mean())*self.oscillator*self.rotation
            self.rotation *= self.advance
            self.rotation /= abs(self.rotation)
            narrow = self.second.process(self.first.process(mixed))
            strength = self.meter.process(narrow)
            previous = narrow[0] if self.previous_iq is None else self.previous_iq
            fm = np.angle(narrow*np.conj(np.r_[previous,narrow[:-1]]))*25000/(2*np.pi)
            self.previous_iq = narrow[-1]
            fm,self.fm_zi = signal.lfilter(np.ones(5)/5,[1],fm,zi=self.fm_zi)
            logic = fm<-1800
            changes = np.flatnonzero(np.diff(np.r_[self.previous_logic,logic].astype(np.int8)))
            found = [self.decoder.edge(bool(logic[i]),start+i/25000) for i in changes]
            # Like the firmware loop: after the edges, commit a frame whose FREE slot has closed.
            found.append(self.decoder.poll(elapsed))
            for message in found:
                if message is not None:
                    message['frequency_hz'] = self.tuned_hz
                    self.chunk_messages.append(message)
                    if message['locked']:
                        self.latest = message
                        self.last_frequency_hz = self.tuned_hz
                        self.message_count += 1
                        self.recent_messages.append(message['seconds'])
                        self.last_message_at = message['seconds']
                        self.trial_at = elapsed
            self.previous_logic = bool(logic[-1])
        recent = self.latest is not None and elapsed-self.latest['seconds']<.065
        rf = elapsed-self.rf_at<.15
        while self.recent_messages and elapsed-self.recent_messages[0]>1:
            self.recent_messages.popleft()
        state = self.latest['state'] if recent else 'waiting' if elapsed<.08 else 'rf_only' if rf else 'no_signal'
        return {'state':state,'seconds':elapsed,'score_db':None,'probe_present':recent,
                'signal_present':rf,'frequency_hz':self.tuned_hz if recent else None,
                'candidate_frequency_hz':self.seen_frequency,'last_frequency_hz':self.last_frequency_hz,
                'fourth_pulse_offset_us':self.latest['fourth_pulse_offset_us'] if recent else None,
                'message_number':self.message_count,'decoder':'automatic frequency + four-pulse timing',
                'messages_per_second':len(self.recent_messages),
                'last_message_age_ms':(elapsed-self.last_message_at)*1000 if self.last_message_at is not None else None,
                'search_min_hz':self.minimum,'search_max_hz':self.maximum,**strength}
