#include "MachineOutputs.h"
#include "ProbeDecoder.h"
static ProbeDecoder decoder;
extern "C" {
unsigned levels(unsigned link, unsigned contact) {
  const auto out=MachineOutputs::levels(link,contact);
  return out.ready | (out.loopClosed<<1) | (out.trip<<2);
}
void reset() { decoder=ProbeDecoder(); }
void edge(unsigned active,unsigned now) { decoder.edge(active,now); }
unsigned outputs(unsigned now) {
  return levels(decoder.link(now),decoder.state==ProbeDecoder::Contact);
}
}
