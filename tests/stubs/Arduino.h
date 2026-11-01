#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#define PROGMEM
#define PI 3.14159265358979323846
inline float radians(float degrees) { return degrees*(PI/180.0); }
class __FlashStringHelper;
class String {
 public:
  size_t length() const { return strlen(text); }
  const char *c_str() const { return text; }
 private:
  const char *text="";
};
