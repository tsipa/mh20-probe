#include "RfPresence.h"
static RfPresence rf;
extern "C" {
void reset() { rf.reset(); }
int convert(unsigned raw) { return RfPresence::convert(raw); }
int feed(unsigned raw) { rf.sample(raw); return rf.present; }
int valid() { return rf.valid; }
}
