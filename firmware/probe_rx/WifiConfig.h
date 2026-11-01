#pragma once
#include <stdint.h>
#include <stddef.h>

namespace WifiConfig {
enum Mode : uint8_t { AP = 1, STA = 2, AP_STA = 3 };
struct Config {
  uint32_t version = 1;
  Mode mode = AP;
  char ssid[33] = {};
  char password[65] = {};
};
inline size_t length(const char *s, size_t max) {
  size_t n = 0; while (n < max && s[n]) ++n; return n;
}
inline bool equals(const char *a, const char *b) {
  while (*a && *a == *b) { ++a; ++b; } return *a == *b;
}
inline bool starts(const char *s, const char *prefix) {
  while (*prefix) if (*s++ != *prefix++) return false;
  return true;
}
inline const char *modeName(Mode mode) { return mode == STA ? "sta" : mode == AP_STA ? "apsta" : "ap"; }
inline bool parseMode(const char *s, Mode &mode) {
  if (equals(s,"ap")) mode = AP;
  else if (equals(s,"sta")) mode = STA;
  else if (equals(s,"apsta")) mode = AP_STA;
  else return false;
  return true;
}
inline bool text(char *dest, size_t capacity, const char *source) {
  const size_t n = length(source, capacity);
  if (n >= capacity) return false;
  for (size_t i = 0; i < n; ++i) if ((uint8_t)source[i] < 32 || source[i] == 127) return false;
  for (size_t i = 0; i < capacity; ++i) dest[i] = i < n ? source[i] : 0;
  return true;
}
inline bool valid(const Config &c) {
  if (c.version != 1 || c.mode < AP || c.mode > AP_STA) return false;
  const size_t n = length(c.ssid, sizeof(c.ssid)), p = length(c.password, sizeof(c.password));
  if (n == sizeof(c.ssid) || p == sizeof(c.password)) return false;
  if (c.mode != AP && !n) return false;
  if (p && p < 8) return false;
  for (size_t i = 0; i < n; ++i) if ((uint8_t)c.ssid[i] < 32 || c.ssid[i] == 127) return false;
  for (size_t i = 0; i < p; ++i) {
    const char ch = c.password[i];
    if ((uint8_t)ch < 32 || ch == 127) return false;
    if (p == 64 && !((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') || (ch >= 'A' && ch <= 'F'))) return false;
  }
  return true;
}
inline const char *displayStatus(bool enabled, bool ap, bool client, bool connected) {
  if (!enabled) return "WiFi OFF";
  if (ap && client) return connected ? "WiFi AP+CLIENT CONNECTED" : "WiFi AP+CLIENT NOT CONNECTED";
  if (client) return connected ? "WiFi CLIENT CONNECTED" : "WiFi CLIENT NOT CONNECTED";
  return ap ? "WiFi AP" : "WiFi NOT CONNECTED";
}
enum Command { Unknown, Changed, Invalid, Help, Status, Save, Reset, Reboot, Access };
inline Command command(Config &c, const char *line) {
  if (equals(line,"wifi") || equals(line,"wifi help")) return Help;
  if (equals(line,"wifi status")) return Status;
  if (equals(line,"wifi save")) return Save;
  if (equals(line,"wifi reset")) return Reset;
  if (equals(line,"wifi reboot")) return Reboot;
  if (equals(line,"wifi access")) return Access;
  if (starts(line,"wifi mode ")) return parseMode(line+10,c.mode) ? Changed : Invalid;
  if (starts(line,"wifi ssid ")) return text(c.ssid,sizeof(c.ssid),line+10) ? Changed : Invalid;
  if (equals(line,"wifi password")) { text(c.password,sizeof(c.password),""); return Changed; }
  if (starts(line,"wifi password ")) return text(c.password,sizeof(c.password),line+14) ? Changed : Invalid;
  return Unknown;
}
// No waiting for a complete UART line; oversized lines are discarded in full.
class LineReader {
 public:
  char line[192] = {};
  size_t size = 0;
  bool overflow = false;
  int feed(char ch) {
    if (ch == '\r') return 0;
    if (ch == '\n') {
      const bool bad = overflow;
      line[size] = 0; size = 0; overflow = false;
      return bad ? -1 : 1;
    }
    if ((uint8_t)ch < 32 || ch == 127) { overflow = true; return 0; }
    if (size + 1 < sizeof(line)) line[size++] = ch;
    else overflow = true;
    return 0;
  }
};
}
