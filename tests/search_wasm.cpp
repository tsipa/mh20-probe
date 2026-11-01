#include "ProbeSearch.h"
static ProbeSearch search;
extern "C" {
void reset(unsigned at, unsigned previous) { search = ProbeSearch(); search.begin(at, previous); }
unsigned frequency() { return search.frequency; }
unsigned phase() { return search.phase; }
unsigned checked() { return search.checkedBand; }
unsigned rf() { return search.bandRf; }
unsigned noiseValid() { return search.noiseValid; }
int noiseHalfDbm() { return search.noiseHalfDbm; }
unsigned feed(unsigned at, unsigned link, unsigned lastMessage, unsigned valid, int halfDbm) {
  return search.update(at, link, lastMessage, valid, halfDbm);
}
}
