#pragma once
#include <stdint.h>

// RSSI finds candidate regions; ONLY ProbeDecoder's validated link locks RX.
// A coarse sweep covers 433-435 MHz, then a fine sweep centers the FSK tones.
class ProbeSearch {
 public:
  enum Phase : uint8_t { Warm, Coarse, Fine, Locked };
  static constexpr uint32_t MIN_HZ = 433000000, MAX_HZ = 435000000;
  Phase phase = Warm;
  uint32_t frequency = 433994200, lockedAt = 0;
  bool checkedBand = false, bandRf = false;
  bool noiseValid = false;
  int noiseHalfDbm = 0; // Lower-quartile RSSI of last full scan, not in-channel SNR.

  void begin(uint32_t now, uint32_t previous) {
    phase = Warm; frequency = previous >= MIN_HZ && previous <= MAX_HZ ? previous : 433994200;
    at = now; checkedBand = bandRf = noiseValid = false; count = noiseCount = 0;
  }

  bool update(uint32_t now, bool link, uint32_t lastMessageAt, bool rssiValid, int halfDbm) {
    if (link) {
      if (phase != Locked) lockedAt = now;
      phase = Locked;
      return false;
    }
    if (phase == Locked) {
      if (uint32_t(now - lastMessageAt) < 250000) return false;
      coarse(now); return true;
    }
    const uint32_t dwell = phase == Warm ? 120000 : phase == Coarse ? 16000 : 50000;
    if (uint32_t(now - at) < dwell) return false;
    at = now;
    if (phase == Warm) { coarse(now); return true; }
    if (phase == Coarse) {
      if (rssiValid) {
        if (noiseCount < 101) noiseSamples[noiseCount++] = int16_t(halfDbm);
        currentRf = currentRf || halfDbm >= -180; // Energy only; never asserts link.
        if (halfDbm >= -208) offer(frequency, halfDbm); // Try weaker candidates too.
      }
      if (frequency < MAX_HZ) { frequency += 20000; return true; }
      checkedBand = true; bandRf = currentRf;
      if (noiseCount) {
        for (uint8_t i=1; i<noiseCount; ++i) {
          const int16_t value = noiseSamples[i]; uint8_t j = i;
          while (j && noiseSamples[j-1] > value) { noiseSamples[j] = noiseSamples[j-1]; --j; }
          noiseSamples[j] = value;
        }
        noiseHalfDbm = noiseSamples[(noiseCount-1)/4]; noiseValid = true;
      }
      if (!count) { coarse(now); return true; }
      candidate = 0; fineStep = 0; phase = Fine;
      frequency = peaks[0].hz; return true;
    }
    if (++fineStep >= 31) {
      fineStep = 0;
      if (++candidate >= count) { coarse(now); return true; }
    }
    const int offset = fineStep == 0 ? 0 : ((fineStep + 1) / 2) * (fineStep % 2 ? 2000 : -2000);
    int64_t target = int64_t(peaks[candidate].hz) + offset;
    if (target < MIN_HZ) target = MIN_HZ;
    if (target > MAX_HZ) target = MAX_HZ;
    frequency = uint32_t(target);
    return true;
  }

 private:
  struct Peak { uint32_t hz; int halfDbm; };
  Peak peaks[4] = {};
  uint32_t at = 0;
  uint8_t count = 0, candidate = 0, fineStep = 0;
  bool currentRf = false;
  int16_t noiseSamples[101] = {};
  uint8_t noiseCount = 0;

  void coarse(uint32_t now) {
    phase = Coarse; frequency = MIN_HZ; at = now; count = noiseCount = 0; currentRf = false;
  }
  static uint32_t distance(uint32_t a, uint32_t b) { return a > b ? a-b : b-a; }
  void offer(uint32_t hz, int halfDbm) {
    uint8_t slot = count;
    for (uint8_t i=0; i<count; ++i) {
      if (distance(hz, peaks[i].hz) < 40000) {
        if (halfDbm <= peaks[i].halfDbm) return;
        slot = i; break;
      }
    }
    if (slot == count) {
      if (count < 4) ++count;
      else { slot = 3; if (halfDbm <= peaks[slot].halfDbm) return; }
    }
    peaks[slot] = {hz, halfDbm};
    for (uint8_t i=slot; i>0 && peaks[i].halfDbm > peaks[i-1].halfDbm; --i) {
      const Peak temp = peaks[i-1]; peaks[i-1] = peaks[i]; peaks[i] = temp;
    }
  }
};
