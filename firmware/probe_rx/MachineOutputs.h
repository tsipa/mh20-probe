#pragma once
#include <stdint.h>

// These GPIOs control 3.3 V isolation/driver stages, NEVER a 24 V machine input.
// Close the normally-closed probe loop only while a validated probe is free.
namespace MachineOutputs {
constexpr int READY_PIN=33, PROBE_LOOP_PIN=25;
struct Levels { bool ready, loopClosed, trip; };
constexpr Levels levels(bool link, bool contact) {
  return {link, link && !contact, !link || contact};
}
}
