// Receive-only CC1101 + classic ESP32 DevKit prototype. Radio settings await hardware validation.
#include <Arduino.h>
#include <SPI.h>
#include "ProbeDecoder.h"
#include "RfPresence.h"
#include "ProbeSearch.h"
#include "MachineOutputs.h"
#include "DisplayPanel.h"
#include "ServiceWeb.h"

constexpr int PIN_SCK = 18, PIN_MISO = 19, PIN_MOSI = 23, PIN_CS = 5;
constexpr int PIN_DATA = 26;
constexpr bool PULSE_IS_HIGH = false; // Lower-frequency excursions normally decode as logic 0.
constexpr uint32_t TARGET_HZ = 433994200; // Midpoint of measured tones, approximate HackRF reference.
constexpr uint32_t XTAL_HZ = 26000000;    // Check the crystal fitted to the CC1101 module.

struct Edge { uint32_t at; bool active; };
constexpr uint32_t QUEUE_SIZE = 1024;
Edge edges[QUEUE_SIZE];
volatile uint32_t head = 0, tail = 0;
volatile bool overflowed = false;
portMUX_TYPE queueLock = portMUX_INITIALIZER_UNLOCKED;
ProbeDecoder decoder;
RfPresence rf;
ProbeSearch search;
bool rawRssiValid = false;
int rawRssiHalfDbm = 0;
uint32_t rssiAt = 0, rfGateAt = 0, lastRssiGoodAt = 0;
uint32_t tunedHz = TARGET_HZ, totalMessages = 0, totalTouches = 0;
uint32_t totalLosses=0, totalOverflows=0, lastTouchMs=0, lastMessageAt=0;
uint32_t rateAt=0, rateMessages=0;
uint16_t messagesPerSecond=0;
bool previousLink=false;
ProbeDecoder::State lastConfirmed = ProbeDecoder::Unknown;

void IRAM_ATTR dataEdge() {
  const uint32_t now = micros();
  const bool active = bool(digitalRead(PIN_DATA)) == PULSE_IS_HIGH;
  portENTER_CRITICAL_ISR(&queueLock);
  if (head - tail < QUEUE_SIZE) edges[(head++) & (QUEUE_SIZE - 1)] = {now, active};
  else overflowed = true;
  portEXIT_CRITICAL_ISR(&queueLock);
}

bool chipReady(uint32_t timeoutUs) {
  const uint32_t start = micros();
  while (digitalRead(PIN_MISO)) if (uint32_t(micros() - start) > timeoutUs) return false;
  return true;
}

uint8_t accessChip(uint8_t address, uint8_t value, bool read) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_CS, LOW);
  if (!chipReady(100000)) {
    digitalWrite(PIN_CS, HIGH); SPI.endTransaction();
    return 0xFF;
  }
  SPI.transfer(read ? address | 0xC0 : address);
  const uint8_t result = SPI.transfer(value);
  digitalWrite(PIN_CS, HIGH); SPI.endTransaction();
  return result;
}

void writeReg(uint8_t address, uint8_t value) { accessChip(address, value, false); }
// Separate success from the data byte: 0xFF is also a legitimate RSSI value.
// Bound periodic polling so disconnected SPI cannot stall contact updates for 100 ms.
bool readStatus(uint8_t address, uint8_t &value) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_CS, LOW);
  const bool ready = chipReady(1000);
  if (ready) { SPI.transfer(address | 0xC0); value = SPI.transfer(0); }
  digitalWrite(PIN_CS, HIGH); SPI.endTransaction();
  return ready;
}
void strobe(uint8_t command) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_CS, LOW);
  if (chipReady(100000)) SPI.transfer(command);
  digitalWrite(PIN_CS, HIGH); SPI.endTransaction();
}

void driveMachine(bool link, bool contact) {
  const auto out=MachineOutputs::levels(link && ServiceWeb::policy.outputsAllowed(),contact);
  if (!out.loopClosed) digitalWrite(MachineOutputs::PROBE_LOOP_PIN,LOW);
  digitalWrite(MachineOutputs::READY_PIN,out.ready?HIGH:LOW);
  if (out.loopClosed) digitalWrite(MachineOutputs::PROBE_LOOP_PIN,HIGH);
}

void safeServiceOutputs() { driveMachine(false, false); }

void publishPanel(int state) {
  DisplayPanel::Snapshot s;
  strncpy(s.wifiStatus,ServiceWeb::displayStatus(),sizeof(s.wifiStatus)-1);
  s.state=state; s.frequency=tunedHz; s.messages=totalMessages; s.touches=totalTouches;
  s.losses=totalLosses; s.overflows=totalOverflows; s.lastMessageAt=lastMessageAt;
  s.lastTouchMs=lastTouchMs; s.messagesPerSecond=messagesPerSecond;
  s.rssiValid=rawRssiValid; s.rssiHalfDbm=rawRssiHalfDbm;
  s.noiseValid=search.noiseValid; s.noiseHalfDbm=search.noiseHalfDbm;
  DisplayPanel::publish(s);
}

void tune(uint32_t hz) {
  driveMachine(false,false); // Open the probe loop before any SPI operation.
  tunedHz = hz;
  strobe(0x36); // SIDLE. This program never issues STX.
  const uint32_t word = (uint64_t(hz) * 65536 + XTAL_HZ / 2) / XTAL_HZ;
  writeReg(0x0D, word >> 16); writeReg(0x0E, word >> 8); writeReg(0x0F, word);
  strobe(0x33); delay(2); // SCAL
  portENTER_CRITICAL(&queueLock);
  tail = head; overflowed = false;
  portEXIT_CRITICAL(&queueLock);
  decoder = ProbeDecoder();
  rf.reset();
  rawRssiValid = false;
  strobe(0x34); // SRX
  rssiAt = rfGateAt = micros(); // First RSSI sample after 10 ms allows RX/AGC to settle.
  publishPanel(5);
  Serial.printf("RX %lu Hz\n", static_cast<unsigned long>(hz));
}

void setup() {
  Serial.begin(115200);
  Serial.println("MH RECEIVER");
  digitalWrite(MachineOutputs::READY_PIN,LOW); digitalWrite(MachineOutputs::PROBE_LOOP_PIN,LOW);
  pinMode(MachineOutputs::READY_PIN,OUTPUT); pinMode(MachineOutputs::PROBE_LOOP_PIN,OUTPUT);
  driveMachine(false,false);
  ServiceWeb::begin(safeServiceOutputs);
  DisplayPanel::begin();
  pinMode(PIN_CS, OUTPUT); digitalWrite(PIN_CS, HIGH);
  pinMode(PIN_DATA, INPUT);
  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_CS);
  delay(10); digitalWrite(PIN_CS, LOW); delayMicroseconds(10);
  digitalWrite(PIN_CS, HIGH); delayMicroseconds(40); strobe(0x30); delay(2); // SRES
  const uint8_t version = accessChip(0x31, 0, true);
  if (version == 0 || version == 0xFF) {
    Serial.println("CC1101 not responding; check power/SPI wiring.");
    publishPanel(-1);
    while (true) { ServiceWeb::poll(tunedHz, false, 0, 0, 0, 0); publishPanel(-1); delay(1); }
  }
  Serial.printf("CC1101 OK VERSION=0x%02X\n",version);
  const uint8_t registers[][2] = {
    {0x00, 0x2E}, // GDO2 high impedance (optional, unused)
    {0x01, 0x2E}, // GDO1 high impedance when CS high
    {0x02, 0x0D}, // GDO0 asynchronous serial data output
    {0x07, 0x00}, {0x08, 0x30}, // No address/CRC/whitening, async serial
    {0x0A, 0x00}, {0x0B, 0x06}, {0x0C, 0x00},
    {0x10, 0xF7}, {0x11, 0x36}, // BW 58.0 kHz, nominal chip rate 3843/s
    {0x12, 0x00}, {0x13, 0x00}, {0x14, 0x00}, // 2-FSK, no Manchester/sync/FEC
    {0x15, 0x03}, // Expected deviation +/-2182 Hz (tone separation 4364 Hz)
    {0x16, 0x07}, {0x17, 0x0C}, {0x18, 0x18}, // Continuous RX
    {0x19, 0x00}, // Frequency-offset compensation disabled: long idle tone is asymmetric
    {0x1A, 0x00}, {0x1B, 0x43}, {0x1C, 0x40}, {0x1D, 0x91},
    {0x21, 0x56}, {0x23, 0xE9}, {0x24, 0x2A}, {0x25, 0x00}, {0x26, 0x1F},
    {0x2C, 0x81}, {0x2D, 0x35}, {0x2E, 0x09}
  };
  for (const auto &r : registers) writeReg(r[0], r[1]);
  attachInterrupt(digitalPinToInterrupt(PIN_DATA), dataEdge, CHANGE);
  lastRssiGoodAt = micros();
  search.begin(lastRssiGoodAt, TARGET_HZ);
  tune(search.frequency);
}

void loop() {
  if (ServiceWeb::policy.maintenance) {
    driveMachine(false, false);
    ServiceWeb::poll(tunedHz, rawRssiValid, rawRssiHalfDbm, totalMessages, totalTouches, totalLosses);
    publishPanel(-3);
    delay(1);
    return;
  }
  bool overflow;
  portENTER_CRITICAL(&queueLock);
  overflow = overflowed; overflowed = false;
  if (overflow) tail = head;
  portEXIT_CRITICAL(&queueLock);
  if (overflow) { ++totalOverflows; decoder = ProbeDecoder(); Serial.println("EDGE QUEUE OVERFLOW"); }
  for (;;) {
    Edge e; bool available;
    portENTER_CRITICAL(&queueLock);
    available = tail != head;
    if (available) e = edges[(tail++) & (QUEUE_SIZE - 1)];
    portEXIT_CRITICAL(&queueLock);
    if (!available) break;
    if (decoder.edge(e.active, e.at)) {
      ServiceWeb::observeProbe();
      ++totalMessages;
      ++rateMessages; lastMessageAt=e.at;
      if (decoder.state==ProbeDecoder::Contact) lastTouchMs=millis();
      if (decoder.state == ProbeDecoder::Contact && lastConfirmed != ProbeDecoder::Contact) ++totalTouches;
      lastConfirmed = decoder.state;
      driveMachine(decoder.link(micros()),decoder.state==ProbeDecoder::Contact);
    }
  }
  const uint32_t now = micros();
  const bool link = decoder.link(now);
  if (previousLink && !link) ++totalLosses;
  previousLink=link;
  driveMachine(link,decoder.state==ProbeDecoder::Contact);
  if (uint32_t(now-rateAt)>=1000000) {
    const uint32_t interval=now-rateAt;
    messagesPerSecond=uint16_t((uint64_t(rateMessages)*1000000)/interval);
    rateMessages=0; rateAt=now;
  }
  if (uint32_t(now - rssiAt) >= 10000) {
    rssiAt = now;
    uint8_t marcState = 0, rawRssi = 0;
    rawRssiValid = readStatus(0x35, marcState) && (marcState & 0x1F) == 0x0D && readStatus(0x34, rawRssi);
    if (rawRssiValid) {
      lastRssiGoodAt = now;
      rawRssiHalfDbm = RfPresence::convert(rawRssi);
      if (uint32_t(now - rfGateAt) >= 20000) { rf.sample(rawRssi); rfGateAt = now; }
    } else rf.reset();
  }
  ServiceWeb::poll(tunedHz, rawRssiValid, rawRssiHalfDbm, totalMessages, totalTouches, totalLosses);
  if (ServiceWeb::policy.maintenance) { driveMachine(false, false); return; }
  if (search.update(micros(), link, decoder.lastMessageAt, rawRssiValid, rawRssiHalfDbm)) {
    tune(search.frequency);
    return;
  }
  // Valid probe messages have priority even when RSSI is below our uncalibrated gate.
  const int current = link ? int(decoder.state) : uint32_t(now-lastRssiGoodAt)>200000 ? 4 :
                      search.phase == ProbeSearch::Locked ? (rf.present ? 3 : 5) :
                      !search.checkedBand ? 5 : search.bandRf ? 3 : 0;
  publishPanel(current);
  static int reported = -1;
  static uint32_t reportAt = 0;
  if (current != reported || uint32_t(now - reportAt) >= 1000000) {
    const char *label = current == 2 ? "CONTACT" : current == 1 ? "FREE" :
                        current == 3 ? "RF_ONLY" : current == 5 ? "SEARCH" : current == 4 ? "RF_WAIT" : "NO_SIGNAL";
    Serial.printf("%s RX=%lu Hz RSSI=", label, static_cast<unsigned long>(tunedHz));
    if (rawRssiValid) Serial.printf("%s%d.%d dBm", rawRssiHalfDbm < 0 ? "-" : "",
                                    abs(rawRssiHalfDbm) / 2, abs(rawRssiHalfDbm) % 2 ? 5 : 0);
    else Serial.print("unavailable");
    Serial.printf(" MSG=%lu TOUCH=%lu LOST=%lu OVF=%lu\n",static_cast<unsigned long>(totalMessages),
                  static_cast<unsigned long>(totalTouches),static_cast<unsigned long>(totalLosses),
                  static_cast<unsigned long>(totalOverflows));
    reported = current;
    reportAt = now;
  }
}
