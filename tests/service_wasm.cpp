#include "ServicePolicy.h"
#include "ProbeDecoder.h"
#include "MachineOutputs.h"
static ServicePolicy policy;
static ProbeDecoder decoder;
extern "C" {
void reset() { policy=ServicePolicy(); decoder=ProbeDecoder(); }
void edge(unsigned active,unsigned now) {
  if (!policy.maintenance && decoder.edge(active,now)) policy.observeProbe();
}
unsigned network() { return policy.networkAllowed(); }
unsigned update() { return policy.beginUpdate(); }
unsigned outputs(unsigned now) {
  const auto out=MachineOutputs::levels(decoder.link(now) && policy.outputsAllowed(), decoder.state==ProbeDecoder::Contact);
  return out.ready | (out.loopClosed<<1) | (out.trip<<2);
}
}
