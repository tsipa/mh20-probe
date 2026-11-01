#pragma once
#include <stddef.h>
extern "C" void *memset(void *,int,size_t);
extern "C" void *memcpy(void *,const void *,size_t);
extern "C" size_t strlen(const char *);
extern "C" char *strncpy(char *,const char *,size_t);
