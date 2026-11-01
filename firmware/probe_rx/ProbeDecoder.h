#pragma once
#include <stdint.h>

// Observed active-state pulse timing. No claim of device-address or CRC validation.
class ProbeDecoder {
 public:
  enum State : uint8_t { Unknown, Free, Contact };
  State state = Unknown;
  uint32_t lastMessageAt = 0;
  uint32_t fourthOffsetUs = 0;
  uint32_t messageCount = 0;
  bool acquired = false;

  bool edge(bool pulseActive, uint32_t now) {
    if (pulseActive) { pulseStart = now; insidePulse = true; return false; }
    if (!insidePulse) return false;
    insidePulse = false;
    const uint32_t width = now - pulseStart; // Unsigned differences handle micros() rollover.
    if (width < 120 || width > 400) { count = 0; return false; }
    if (count == 4) {
      for (uint8_t i = 0; i < 3; ++i) starts[i] = starts[i + 1];
      count = 3;
    }
    starts[count++] = pulseStart;
    if (count != 4) return false;
    if (!near(starts[1] - starts[0], 1040, 120) ||
        !near(starts[2] - starts[0], 1560, 120)) return false;
    const uint32_t offset = starts[3] - starts[0];
    State candidate = Unknown;
    if (near(offset, 3120, 120)) candidate = Contact;
    else if (near(offset, 3640, 120)) candidate = Free;
    else return false;
    bool cadence = false;
    if (havePrevious) {
      const uint32_t interval = starts[0] - previousStart;
      const uint32_t periods = (interval + 8125) / 16250;
      cadence = periods >= 1 && periods <= 3 && near(interval, periods * 16250, 300);
    }
    goodFrames = cadence ? 2 : 1;
    previousStart = starts[0]; havePrevious = true;
    ++messageCount;
    acquired = goodFrames >= 2;
    if (!acquired) return false;
    state = candidate; lastMessageAt = now; fourthOffsetUs = offset;
    return true;
  }

  bool link(uint32_t now) const {
    return state != Unknown && uint32_t(now - lastMessageAt) < 65000;
  }

 private:
  uint32_t starts[4] = {}, pulseStart = 0, previousStart = 0;
  uint8_t count = 0, goodFrames = 0;
  bool insidePulse = false, havePrevious = false;
  static bool near(uint32_t value, uint32_t target, uint32_t tolerance) {
    return value >= target - tolerance && value <= target + tolerance;
  }
};
