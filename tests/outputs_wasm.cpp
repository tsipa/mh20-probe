#include "MachineOutputs.h"
#include "ProbeDecoder.h"
static ProbeDecoder decoder;
static MachineOutputs::Guard guard;
extern "C" {
unsigned levels(unsigned link, unsigned contact) {
  const auto out=MachineOutputs::levels(link,contact);
  return out.ready | (out.loopClosed<<1) | (out.trip<<2);
}
void reset() { decoder=ProbeDecoder(); }
void edge(unsigned active,unsigned now) { decoder.edge(active,now); }
// Mirrors loop(): poll() commits a decided frame before the link check.
unsigned outputs(unsigned now) {
  decoder.poll(now);
  return levels(decoder.link(now),decoder.state==ProbeDecoder::Contact);
}
void guardRefresh() { guard.refresh(); }
unsigned guardTick() { return guard.tick(); }
unsigned guardRunning() { return guard.running(); }
}
