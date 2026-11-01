#pragma once

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
  bool outputsAllowed() const { return probeSeen && !maintenance; }
};
