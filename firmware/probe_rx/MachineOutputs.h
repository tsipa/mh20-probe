#pragma once
#include <stdint.h>
#ifdef ARDUINO
#include <soc/gpio_struct.h>
#endif

// These GPIOs control 3.3 V isolation/driver stages, NEVER a 24 V machine input.
// Close the normally-closed probe loop only while a validated probe is free.
namespace MachineOutputs {
constexpr int READY_PIN=33, PROBE_LOOP_PIN=25;
struct Levels { bool ready, loopClosed, trip; };
constexpr Levels levels(bool link, bool contact) {
  return {link, link && !contact, !link || contact};
}

// Output guard: a periodic hardware-timer ISR forces both outputs LOW when loop() has not
// re-evaluated them for 60-65 ms (below the 65 ms link timeout); the next loop() pass
// drives them again from fresh decoder state. The ISR only counts ticks, so it calls no
// function that could live in flash. loop() and the ISR run on the same core.
constexpr uint32_t GUARD_PERIOD_US=5000, GUARD_TICKS=12;
struct Guard {
  volatile uint32_t ticks=0;
  void refresh() { ticks=0; }
  // Called every GUARD_PERIOD_US; true while the outputs must be held LOW.
  __attribute__((always_inline)) bool tick() {
    uint32_t t=ticks;
    if (t<=GUARD_TICKS) ticks=++t;
    return t>GUARD_TICKS;
  }
  // Start-up check: the interrupt has counted since the last refresh. Attaching the
  // interrupt or setting the alarm only logs a failure, so a timer handle alone does not
  // prove that the guard runs.
  static constexpr uint32_t START_TICKS=2;
  bool running() const { return ticks>=START_TICKS; }
};

#ifdef ARDUINO
// Interrupt-safe: write-1-to-clear GPIO registers only, no driver calls or flash code.
__attribute__((always_inline)) inline void forceLow() {
  static_assert(PROBE_LOOP_PIN<32 && READY_PIN>=32 && READY_PIN<40, "register mapping below");
  GPIO.out_w1tc=1UL<<PROBE_LOOP_PIN;
  GPIO.out1_w1tc.val=1UL<<(READY_PIN-32);
}
#endif
}
