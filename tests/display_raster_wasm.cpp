// Compile the actual installed Adafruit_GFX.cpp and firmware strip renderer.
#include "DisplayRaster.h"
unsigned heapCalls=0;
extern "C" {
void *malloc(size_t) { ++heapCalls; return nullptr; }
void free(void *) { }
int abs(int value) { return value<0?-value:value; }
void *memset(void *dst,int value,size_t n) {
  auto *p=static_cast<unsigned char *>(dst);for(size_t i=0;i<n;++i)p[i]=value;return dst;
}
void *memcpy(void *dst,const void *src,size_t n) {
  auto *d=static_cast<unsigned char *>(dst);auto *s=static_cast<const unsigned char *>(src);
  for(size_t i=0;i<n;++i)d[i]=s[i];return dst;
}
size_t strlen(const char *p) { size_t n=0;while(p[n])++n;return n; }
char *strncpy(char *dst,const char *src,size_t n) { size_t i=0;for(;i<n&&src[i];++i)dst[i]=src[i];for(;i<n;++i)dst[i]=0;return dst; }
int __cxa_atexit(void (*)(void *),void *,void *) { return 0; }
void __cxa_pure_virtual() { __builtin_trap(); }
}
void operator delete(void *) noexcept { }

class StaticFullCanvas : public GFXcanvas16 {
 public:
  StaticFullCanvas():GFXcanvas16(240,240,false) { buffer=pixels; }
 private:
  uint16_t pixels[240*240];
};
StaticFullCanvas reference;
struct Output {
  uint16_t pixels[240*240+32];
  unsigned writes=0,maxHeight=0,boundsErrors=0;
  void drawRGBBitmap(int x,int y,uint16_t *src,int w,int h) {
    ++writes;if(unsigned(h)>maxHeight)maxHeight=h;
    if(x!=0||w!=240||y<0||y+h>240) { ++boundsErrors;return; }
    memcpy(pixels+16+y*240,src,w*h*2);
  }
} output;
DisplayRaster::Lines lines;
void setLines(int state) {
  const char *values[]={"M&H 20.00 / RECEIVER",state==2?"TOUCH":state==1?"READY":"NO PROBE",
    state==2?"PROBE TRIGGERED":state==1?"VALID MESSAGES":"SEARCHING 433-435 MHz",
    "RX 434.134000 MHz","RSSI -55.5 dBm","Noise(scan) -99.5 dBm","Messages 61/s",
    "Lost 4  Touch 4","Msg 594 Age 4ms Ovf 0",state==1?"READY:1  LOOP:CLOSED":state==2?"READY:1  LOOP:OPEN":"READY:0  LOOP:OPEN"};
  for(unsigned i=0;i<10;++i)strncpy(lines[i],values[i],42);
}
unsigned compare(int state,uint16_t color) {
  reference.fillScreen(color);
  DisplayRaster::drawRows(reference,0,0,240,state,lines);
  unsigned different=0;
  for(unsigned i=0;i<240*240;++i)different+=output.pixels[i+16]!=reference.getBuffer()[i];
  for(unsigned i=0;i<16;++i)different+=output.pixels[i]!=0xD00D||output.pixels[240*240+16+i]!=0xD00D;
  return different+output.boundsErrors;
}
extern "C" {
unsigned render(unsigned state) {
  const uint16_t color=state==2?0x12B8:state==1?0x0408:0xC906;
  setLines(state);memset(output.pixels,0,sizeof(output.pixels));
  for(unsigned i=0;i<16;++i)output.pixels[i]=output.pixels[240*240+16+i]=0xD00D;
  output.writes=output.maxHeight=output.boundsErrors=0;
  reference.setTextWrap(false);DisplayRaster::strip.setTextWrap(false);
  DisplayRaster::paintRegion(output,0,240,color,state,lines);
  unsigned different=compare(state,color);
  // Replace long values by shorter ones; partial repaint must erase every old pixel.
  strncpy(lines[3],"RX -- MHz",42);strncpy(lines[4],"RSSI --",42);
  for(unsigned row=3;row<=4;++row)
    DisplayRaster::paintRegion(output,DisplayRaster::Y[row],DisplayRaster::H[row],color,state,lines);
  different+=compare(state,color);
  // Ten-pixel footer produces an 8+2 strip split.
  strncpy(lines[9],"READY:0  LOOP:OPEN",42);
  DisplayRaster::paintRegion(output,DisplayRaster::Y[9],DisplayRaster::H[9],color,state,lines);
  different+=compare(state,color);
  // Save a coherent example image after the partial-update checks.
  setLines(state);
  DisplayRaster::paintRegion(output,0,240,color,state,lines);
  return different+compare(state,color);
}
unsigned allocations() { return heapCalls; }
// Illustrative values; layout, font and colors are the actual firmware renderer.
void preview(unsigned state) {
  setLines(state);
  strncpy(lines[5],"Noise(scan) --",42);
  strncpy(lines[7],state?"Lost 1  Touch 23":"Lost 0  Touch 0",42);
  strncpy(lines[8],state?"Msg 864 Age 4ms Ovf 0":"Msg 0  Edge ovf 0",42);
  if (!state) {
    strncpy(lines[3],"RX 433.900000 MHz",42);
    strncpy(lines[4],"RSSI --",42);
    strncpy(lines[6],"Messages 0/s",42);
  }
  DisplayRaster::strip.setTextWrap(false);
  DisplayRaster::paintRegion(output,0,240,state==2?0x12B8:state==1?0x0408:0xC906,state,lines);
}
unsigned stripeBytes() { return DisplayRaster::PIXEL_BYTES; }
unsigned maxHeight() { return output.maxHeight; }
unsigned framebuffer() { return reinterpret_cast<unsigned>(output.pixels+16); }
}
