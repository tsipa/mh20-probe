#include "ServicePolicy.h"
#include "ProbeDecoder.h"
#include "MachineOutputs.h"
static ServicePolicy policy;
static ProbeDecoder decoder;
extern "C" {
void reset() { policy=ServicePolicy(); decoder=ProbeDecoder(); }
// Like loop(): edges and poll() are ignored in maintenance; an accepted frame latches the probe.
void edge(unsigned active,unsigned now) {
  if (!policy.maintenance && decoder.edge(active,now)) policy.observeProbe();
}
void poll(unsigned now) {
  if (!policy.maintenance && decoder.poll(now)) policy.observeProbe();
}
unsigned recovery(unsigned ap,unsigned now,unsigned last) { return policy.recoveryAllowed(ap,now,last); }
unsigned network() { return policy.networkAllowed(); }
unsigned update() { return policy.beginUpdate(); }
unsigned outputs(unsigned now) {
  poll(now);
  const auto out=MachineOutputs::levels(decoder.link(now) && policy.outputsAllowed(), decoder.state==ProbeDecoder::Contact);
  return out.ready | (out.loopClosed<<1) | (out.trip<<2);
}
}
