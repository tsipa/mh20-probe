#pragma once
#include <stdint.h>

// Observed active-state pulse timing. No claim of device-address or CRC validation.
//
// Frame: lower-tone pulses starting at 0, 1040 and 1560 us, and a fourth pulse at
// 3120 us (CONTACT) or 3640 us (FREE), each +-120 us. A frame is decided only after
// its FREE slot has closed (start + 3760 us, and after any pulse still in progress has
// ended): exactly one pulse in each of the 1040/1560 slots, exactly one in the CONTACT
// or the FREE slot and no other pulse inside the frame. Anything else discards the
// frame, so one noise pulse in the CONTACT slot of a FREE frame cannot report CONTACT.
// A pulse outside the width window, a pulse start while the previous pulse has not
// ended (missed falling edge), or an inactive level while no pulse is open (missed
// rising edge) discards every open frame: a mis-sliced CONTACT pulse cannot leave the
// other three pulses to pair with a later pulse in the FREE slot. The edge interrupt
// reports the line level, not the edge direction, so a pulse shorter than the interrupt
// latency, or one whose interrupt was held off until it had ended, arrives as a single
// inactive event, and chatter at either edge arrives as two events with the same level.
// A repeated inactive event up to BOUNCE_US after the falling edge, or a repeated active
// event up to BOUNCE_US after the rising edge, is treated as bounce and ignored; the
// pulse keeps the time of its first edge. A valid pulse is at least MIN_WIDTH_US wide,
// so a pulse start after a missed falling edge comes more than BOUNCE_US after the
// previous rising edge and still discards the open frames.
// The decision is committed by the next edge after the deadline or by poll(), which
// loop() calls on every pass. CONTACT is reported ~0.4 ms later than the end of its
// fourth pulse, plus at most one loop pass.
//
// Acceptance: initial acquisition and every FREE frame need cadence with the previous
// timing-valid frame (1-3 x 16250 us, +-300 us). While the link is up, a CONTACT frame
// is accepted immediately even off-cadence (the probe sends one as soon as it is
// touched) and becomes the new cadence reference. Opening the probe loop is easy,
// closing it again is hard.
//
// Times are micros() values; unsigned differences handle rollover.
class ProbeDecoder {
 public:
  enum State : uint8_t { Unknown, Free, Contact };

  // Pulse width window. The recorded fixtures through the reference demodulator measure
  // 200-280 us (25 kHz, 40 us steps; 348 in-frame pulses). Interpolated widths span
  // 171-352 us when the slicer threshold moves by +-800 Hz, i.e. the width follows the
  // residual carrier offset. CC1101 GDO0 widths are unmeasured (FOC off, 2 kHz fine
  // search steps), so the data does not justify narrowing 120-400 us.
  static constexpr uint32_t MIN_WIDTH_US = 120, MAX_WIDTH_US = 400;
  static constexpr uint32_t BOUNCE_US = 40;  // Repeated level this soon after its edge: bounce.
  static constexpr uint32_t SLOT_US = 120;
  static constexpr uint32_t CONTACT_US = 3120, FREE_US = 3640;
  static constexpr uint32_t FRAME_US = FREE_US + SLOT_US;  // Decision deadline after the first pulse.
  static constexpr uint32_t PERIOD_US = 16250, PERIOD_TOLERANCE_US = 300;
  static constexpr uint32_t LINK_TIMEOUT_US = 65000;

  State state = Unknown;
  uint32_t lastMessageAt = 0;  // Completion time of the last accepted frame.
  uint32_t fourthOffsetUs = 0;
  uint32_t messageCount = 0;   // Timing-valid frames, accepted or not.
  bool acquired = false;       // The last timing-valid frame was accepted.

  // edge() and poll() return true when a frame was accepted during the call.
  bool edge(bool pulseActive, uint32_t now) {
    const bool accepted = settle(now);  // Frames that closed before this edge.
    if (pulseActive) {
      if (insidePulse) {
        if (uint32_t(now - pulseStart) <= BOUNCE_US) return accepted;  // Rising-edge bounce.
        count = 0;  // Missed falling edge: distrust the open frames.
      }
      pulseStart = now; insidePulse = true;
      return accepted;
    }
    if (!insidePulse) {
      if (uint32_t(now - pulseEnd) > BOUNCE_US) count = 0;  // Missed rising edge.
      return accepted;
    }
    insidePulse = false; pulseEnd = now;
    const uint32_t width = now - pulseStart;
    if (width < MIN_WIDTH_US || width > MAX_WIDTH_US) { count = 0; return accepted; }
    // A full buffer means the oldest open frame already holds too many pulses.
    if (count == CAPACITY) drop(1);
    starts[count] = pulseStart; ends[count] = now; ++count;
    return settle(now) || accepted;
  }

  // Call with a time at or after every edge already queued for edge().
  bool poll(uint32_t now) { return settle(now); }

  bool link(uint32_t now) const {
    return linkUp && uint32_t(now - lastMessageAt) < LINK_TIMEOUT_US;
  }

 private:
  static constexpr uint8_t CAPACITY = 8;
  uint32_t starts[CAPACITY] = {}, ends[CAPACITY] = {};
  uint32_t pulseStart = 0, pulseEnd = 0, previousStart = 0, clock = 0;
  uint8_t count = 0;
  bool insidePulse = false, havePrevious = false, clockSet = false, linkUp = false;

  static bool near(uint32_t value, uint32_t target, uint32_t tolerance = SLOT_US) {
    return value >= target - tolerance && value <= target + tolerance;
  }

  void drop(uint8_t n) {
    if (n >= count) { count = 0; return; }
    for (uint8_t i = n; i < count; ++i) { starts[i - n] = starts[i]; ends[i - n] = ends[i]; }
    count -= n;
  }

  bool settle(uint32_t now) {
    if (clockSet && int32_t(now - clock) < 0) return false;  // Older than an event already handled.
    clock = now; clockSet = true;
    bool accepted = false;
    while (count) {
      const uint32_t first = starts[0];
      if (uint32_t(now - first) <= FRAME_US) break;  // FREE slot still open.
      if (insidePulse && uint32_t(pulseStart - first) <= FRAME_US) {
        if (uint32_t(now - pulseStart) <= MAX_WIDTH_US) break;  // Wait for the pulse to end.
        count = 0; break;  // Already too wide: every open frame contains it.
      }
      uint8_t inFrame = 1;
      while (inFrame < count && uint32_t(starts[inFrame] - first) <= FRAME_US) ++inFrame;
      const State candidate = inFrame == 4 ? classify() : Unknown;
      if (candidate == Unknown) { drop(1); continue; }  // A later pulse may still start a frame.
      accepted = commit(candidate) || accepted;
      drop(4);
    }
    if (linkUp && uint32_t(now - lastMessageAt) >= LINK_TIMEOUT_US) linkUp = false;
    return accepted;
  }

  State classify() const {
    const uint32_t first = starts[0], fourth = starts[3] - first;
    if (!near(starts[1] - first, 1040) || !near(starts[2] - first, 1560)) return Unknown;
    return near(fourth, CONTACT_US) ? Contact : near(fourth, FREE_US) ? Free : Unknown;
  }

  bool commit(State candidate) {
    const uint32_t first = starts[0], deadline = first + FRAME_US;
    const uint32_t doneAt = int32_t(ends[3] - deadline) > 0 ? ends[3] : deadline;
    bool cadence = false;
    if (havePrevious) {
      const uint32_t interval = first - previousStart;
      const uint32_t periods = (interval + PERIOD_US / 2) / PERIOD_US;
      cadence = periods >= 1 && periods <= 3 && near(interval, periods * PERIOD_US, PERIOD_TOLERANCE_US);
    }
    const bool linked = linkUp && uint32_t(doneAt - lastMessageAt) < LINK_TIMEOUT_US;
    previousStart = first; havePrevious = true;  // Every timing-valid frame re-anchors the cadence.
    ++messageCount;
    acquired = cadence || (linked && candidate == Contact);
    if (!acquired) return false;
    state = candidate; lastMessageAt = doneAt; fourthOffsetUs = starts[3] - first; linkUp = true;
    return true;
  }
};
