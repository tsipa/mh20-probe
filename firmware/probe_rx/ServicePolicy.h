#pragma once
#include <stdint.h>

// Only a reboot can clear the probe-seen latch or leave update mode.
class ServicePolicy {
 public:
  bool probeSeen = false;
  bool maintenance = false;
  bool networkAllowed() const { return !probeSeen; }
  void observeProbe() { if (!maintenance) probeSeen = true; }
  bool beginUpdate() {
    if (probeSeen) return false;
    maintenance = true;
    return true;
  }
  bool recoveryAllowed(bool apActive, uint32_t now, uint32_t lastConnected) const {
    return networkAllowed() && !apActive && uint32_t(now - lastConnected) >= 15000;
  }
  bool outputsAllowed() const { return probeSeen && !maintenance; }
};
