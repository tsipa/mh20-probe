#pragma once
#include <stddef.h>
#include <stdint.h>
class Print {
 public:
  virtual size_t write(uint8_t)=0;
  size_t write(const uint8_t *p,size_t n) { size_t count=0;while(n--)count+=write(*p++);return count; }
  size_t print(const char *p) { size_t n=0;while(*p)n+=write(uint8_t(*p++));return n; }
};
