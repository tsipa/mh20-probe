#pragma once
#include <stdint.h>

// CC1101 RSSI is signed, half-dB steps; the typical 433 MHz offset is 74 dB.
// This gate detects RF energy in the tuned receive filter, not probe identity.
class RfPresence {
 public:
  static constexpr int ON_HALF_DBM = -180;  // -90 dBm: adjust after an off/on comparison.
  static constexpr int OFF_HALF_DBM = -188; // -94 dBm: hysteresis against fluctuating RSSI.
  bool valid = false, present = false;
  int halfDbm = 0;

  static int convert(uint8_t raw) {
    return (raw >= 128 ? int(raw) - 256 : int(raw)) - 148;
  }

  void reset() { valid = present = false; highCount = lowCount = 0; }

  void sample(uint8_t raw) {
    halfDbm = convert(raw); valid = true;
    if (!present) {
      lowCount = 0;
      highCount = halfDbm >= ON_HALF_DBM ? highCount + 1 : 0;
      if (highCount >= 2) { present = true; highCount = 0; }
    } else {
      highCount = 0;
      lowCount = halfDbm <= OFF_HALF_DBM ? lowCount + 1 : 0;
      if (lowCount >= 4) { present = false; lowCount = 0; }
    }
  }

 private:
  uint8_t highCount = 0, lowCount = 0;
};
