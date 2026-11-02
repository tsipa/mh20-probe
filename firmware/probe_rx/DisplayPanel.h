#pragma once
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <string.h>
#include "DisplayRaster.h"

// Seven-pin ST7789 without CS: own HSPI bus, SCK14 MOSI13 RES27 DC32.
namespace DisplayPanel {
constexpr int SCK_PIN=14, MOSI_PIN=13, RESET_PIN=27, DC_PIN=32;
constexpr uint32_t DRAW_HZ=20000000; // If long wires corrupt pixels, try 10000000.
SPIClass bus(HSPI);
class SlowST7789 : public Adafruit_ST7789 {
 public:
  using Adafruit_ST7789::Adafruit_ST7789;
  void begin(uint32_t frequency=0) override { Adafruit_ST77xx::begin(1000000); }
};
SlowST7789 screen(&bus,-1,DC_PIN,RESET_PIN);
portMUX_TYPE lock=portMUX_INITIALIZER_UNLOCKED;
struct Snapshot {
  int state=-2; // Only 1/2 mean a validated probe. All other states are red; -4 = output guard fault.
  uint32_t frequency=433994200, messages=0, touches=0, losses=0, overflows=0;
  uint32_t lastMessageAt=0, lastTouchMs=0;
  uint16_t messagesPerSecond=0;
  bool rssiValid=false, noiseValid=false;
  char wifiStatus[32]="WiFi OFF";
  int rssiHalfDbm=0, noiseHalfDbm=0;
};
Snapshot latest;

void publish(const Snapshot &value) {
  portENTER_CRITICAL(&lock); latest=value; portEXIT_CRITICAL(&lock);
}
constexpr uint16_t background(int state) {
  return state==2 ? 0x12B8 : state==1 ? 0x0408 : 0xC906;
}
void signedHalf(char *out, size_t size, int half) {
  snprintf(out,size,"%s%d.%d",half<0?"-":"",abs(half)/2,abs(half)%2?5:0);
}
void task(void *) {
  bus.begin(SCK_PIN,-1,MOSI_PIN,-1);
  screen.init(240,240,SPI_MODE3); screen.setSPISpeed(DRAW_HZ); screen.setRotation(0);
  DisplayRaster::strip.setTextWrap(false);
  Serial.printf("DISPLAY READY MODE3 20MHz STATIC_STRIP=%u bytes\n",DisplayRaster::PIXEL_BYTES);
  constexpr uint8_t ROWS=DisplayRaster::ROWS;
  DisplayRaster::Lines previous={};
  uint16_t previousColor=0;
  uint32_t metricsAt=0;
  bool initialized=false;
  for (;;) {
    Snapshot s;
    portENTER_CRITICAL(&lock); s=latest; portEXIT_CRITICAL(&lock);
    if ((s.state==1||s.state==2) && uint32_t(micros()-s.lastMessageAt)>=65000) s.state=5;
    // Short blue indication is visual only. Red link loss always overrides it.
    const bool flash=s.state==1 && s.touches && uint32_t(millis()-s.lastTouchMs)<100;
    const int visual=flash ? 2 : s.state;
    const uint16_t color=background(visual);
    const bool repaint=!initialized || color!=previousColor;
    if (repaint || uint32_t(millis()-metricsAt)>=50) {
      metricsAt=millis();
      DisplayRaster::Lines lines={};
      strncpy(lines[0],s.wifiStatus,sizeof(lines[0])-1);
      strcpy(lines[1],visual==2?"TOUCH":visual==1?"READY":s.state==-4?"FAULT":"NO PROBE");
      const char *detail=flash?"SHORT TOUCH":s.state==2?"PROBE TRIGGERED":s.state==1?"VALID MESSAGES":
        s.state==-4?"OUTPUT GUARD FAULT":s.state==-3?"SERVICE MODE":s.state==-1?"RADIO NOT CONNECTED":s.state==3?"RF WITHOUT PROBE MESSAGES":
        s.state==4?"RADIO STATUS UNAVAILABLE":s.state==5?"SEARCHING 433-435 MHz":s.state==-2?"STARTING":"NO VALID PROBE SIGNAL";
      strncpy(lines[2],detail,sizeof(lines[2])-1);
      if (s.state==-1||s.state==-2) strcpy(lines[3],"RX -- MHz");
      else snprintf(lines[3],sizeof(lines[3]),"RX %lu.%06lu MHz",static_cast<unsigned long>(s.frequency/1000000),static_cast<unsigned long>(s.frequency%1000000));
      char rssi[12],noise[12]; signedHalf(rssi,sizeof(rssi),s.rssiHalfDbm); signedHalf(noise,sizeof(noise),s.noiseHalfDbm);
      if (s.rssiValid) snprintf(lines[4],sizeof(lines[4]),"RSSI %s dBm",rssi);
      else strcpy(lines[4],"RSSI --");
      if (s.noiseValid) snprintf(lines[5],sizeof(lines[5]),"Noise(scan) %s dBm",noise);
      else strcpy(lines[5],"Noise(scan) --");
      snprintf(lines[6],sizeof(lines[6]),"Messages %u/s",s.messagesPerSecond);
      snprintf(lines[7],sizeof(lines[7]),"Lost %lu  Touch %lu",static_cast<unsigned long>(s.losses),static_cast<unsigned long>(s.touches));
      if (s.messages) snprintf(lines[8],sizeof(lines[8]),"Msg %lu Age %lums Ovf %lu",static_cast<unsigned long>(s.messages),static_cast<unsigned long>((micros()-s.lastMessageAt)/1000),static_cast<unsigned long>(s.overflows));
      else snprintf(lines[8],sizeof(lines[8]),"Msg 0  Edge ovf %lu",static_cast<unsigned long>(s.overflows));
      snprintf(lines[9],sizeof(lines[9]),"READY:%d  LOOP:%s",s.state==1||s.state==2,s.state==1?"CLOSED":"OPEN");
      if (repaint) DisplayRaster::paintRegion(screen,0,240,color,visual,lines);
      for (uint8_t i=0;i<ROWS;++i) {
        if (!repaint && !strcmp(lines[i],previous[i])) continue;
        if (!repaint) DisplayRaster::paintRegion(screen,DisplayRaster::Y[i],DisplayRaster::H[i],color,visual,lines);
        strncpy(previous[i],lines[i],sizeof(previous[i])-1);
      }
      previousColor=color; initialized=true;
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
void begin() {
  if (xTaskCreatePinnedToCore(task,"probe_display",4096,nullptr,1,nullptr,0)!=pdPASS)
    Serial.println("Display task allocation failed");
}
} // namespace DisplayPanel
