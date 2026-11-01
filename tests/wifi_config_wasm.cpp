#include "WifiConfig.h"
static WifiConfig::Config config;
static WifiConfig::LineReader reader;
extern "C" {
void reset() { config=WifiConfig::Config(); reader=WifiConfig::LineReader(); }
unsigned feed(unsigned ch) {
  const int result=reader.feed(char(ch));
  if (result<0) return 99;
  return result ? unsigned(WifiConfig::command(config,reader.line))+1 : 0;
}
unsigned valid() { return WifiConfig::valid(config); }
unsigned mode() { return config.mode; }
unsigned ssidLength() { return WifiConfig::length(config.ssid,sizeof(config.ssid)); }
unsigned passwordLength() { return WifiConfig::length(config.password,sizeof(config.password)); }
unsigned ssidByte(unsigned index) { return index<sizeof(config.ssid) ? (uint8_t)config.ssid[index] : 0; }
unsigned passwordByte(unsigned index) { return index<sizeof(config.password) ? (uint8_t)config.password[index] : 0; }
unsigned displayByte(unsigned flags,unsigned index) {
  const char *label=WifiConfig::displayStatus(flags&1,flags&2,flags&4,flags&8);
  return index<WifiConfig::length(label,40) ? label[index] : 0;
}
unsigned badStorage(unsigned kind) {
  auto bad=config;
  if (kind==0) bad.version=0;
  if (kind==1) bad.mode=WifiConfig::Mode(0);
  if (kind==2) for (auto &ch:bad.ssid) ch='a';
  if (kind==3) for (auto &ch:bad.password) ch='b';
  return WifiConfig::valid(bad);
}
}
