"""Relative channel level and approximate in-band SNR, measured after channelization."""
import numpy as np


class SignalMeter:
    def __init__(self):
        self.width=4096
        self.history=np.empty(0,dtype=np.complex64)
        self.pending=0
        self.window=np.hanning(self.width)
        frequencies=np.fft.fftfreq(self.width,1/25000)
        # Both FSK tones and their nearby sidebands; a separate guard band estimates noise.
        self.band=(frequencies>=-8000)&(frequencies<=4000)
        self.guard=(frequencies>=8000)&(frequencies<=10000)
        self.scale=self.width*np.sum(self.window**2)
        self.level=None
        self.noise=None
        self.values={'channel_dbfs':None,'snr_db':None,'noise_dbfs':None}

    def process(self,iq):
        self.history=np.concatenate((self.history,iq))[-self.width:]
        self.pending+=len(iq)
        if len(self.history)<self.width or self.pending<2500:return self.values
        self.pending%=2500
        spectrum=np.abs(np.fft.fft(self.history*self.window))**2/self.scale
        level=float(spectrum[self.band].sum())
        # A complex-noise FFT bin has exponential power: median / ln(2) estimates its mean.
        noise=float(np.median(spectrum[self.guard])/np.log(2)*self.band.sum())
        alpha=1-np.exp(-.1/.4)
        self.level=level if self.level is None else self.level+alpha*(level-self.level)
        self.noise=noise if self.noise is None else self.noise+alpha*(noise-self.noise)
        signal=max(self.level-self.noise,0.)
        self.values={'channel_dbfs':float(10*np.log10(max(self.level,1e-15))),
                     'noise_dbfs':float(10*np.log10(max(self.noise,1e-15))),
                     'snr_db':float(10*np.log10(signal/self.noise)) if signal>0 and self.noise>1e-15 else None}
        return self.values
