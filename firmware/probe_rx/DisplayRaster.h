#pragma once
#include <Adafruit_GFX.h>
#include <stdint.h>
#include <string.h>

namespace DisplayRaster {
constexpr int WIDTH=240, HEIGHT=240, STRIP_HEIGHT=8;
constexpr uint8_t ROWS=10, CHARS=42;
constexpr uint8_t Y[ROWS]={4,24,73,96,123,148,168,190,211,227};
constexpr uint8_t H[ROWS]={16,46,18,22,22,16,16,16,12,10};
using Lines=char[ROWS][CHARS];

// Library 1.13.0 supports a caller-owned buffer. No malloc and no full frame.
class StaticStripCanvas : public GFXcanvas16 {
 public:
  StaticStripCanvas():GFXcanvas16(DisplayRaster::WIDTH,DisplayRaster::STRIP_HEIGHT,false) { buffer=pixels; }
 private:
  uint16_t pixels[DisplayRaster::WIDTH*DisplayRaster::STRIP_HEIGHT];
};
StaticStripCanvas strip;
constexpr unsigned PIXEL_BYTES=WIDTH*STRIP_HEIGHT*sizeof(uint16_t);
static_assert(PIXEL_BYTES==3840,"Keep display pixel storage small and static");

void drawRows(Adafruit_GFX &canvas, int offsetY, int regionTop, int regionHeight,
              int visual, const Lines &lines) {
  for (uint8_t i=0;i<ROWS;++i) {
    if (int(Y[i])+H[i]<=regionTop || int(Y[i])>=regionTop+regionHeight) continue;
    const uint8_t size=i==1?(visual==1||visual==2?4:3):i==3||i==4?2:1;
    canvas.setTextSize(size); canvas.setTextColor(0xFFFF);
    const int textWidth=strlen(lines[i])*6*size;
    canvas.setCursor(i<=3?(WIDTH-textWidth)/2:12,int(Y[i])+(int(H[i])-8*size)/2-offsetY);
    canvas.print(lines[i]);
  }
}

template<class Output>
void paintRegion(Output &output, int top, int height, uint16_t color,
                  int visual, const Lines &lines) {
  const int end=top+height;
  for (int at=top;at<end;at+=STRIP_HEIGHT) {
    const int count=end-at<STRIP_HEIGHT?end-at:STRIP_HEIGHT;
    strip.fillScreen(color);
    drawRows(strip,at,at,count,visual,lines);
    output.drawRGBBitmap(0,at,strip.getBuffer(),WIDTH,count);
  }
}
} // namespace DisplayRaster
