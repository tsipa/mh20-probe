#include "ProbeDecoder.h"
static ProbeDecoder decoder;
extern "C" {
void reset() { decoder=ProbeDecoder(); }
unsigned edge(unsigned active,unsigned now) { return decoder.edge(active,now); }
unsigned poll(unsigned now) { return decoder.poll(now); }
unsigned state() { return decoder.state; }
unsigned link(unsigned now) { return decoder.link(now); }
unsigned lastMessageAt() { return decoder.lastMessageAt; }
}
