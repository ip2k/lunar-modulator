// SPDX-License-Identifier: MIT
#include <stddef.h>
char *__stpcpy(char *,const char *);
char *__stpncpy(char *,const char *,size_t);
char *__strchrnul(const char *,int);

#define LUNAR_STRING_1(x) #x
#define LUNAR_STRING(x) LUNAR_STRING_1(x)
#define weak_alias(old,new) extern __typeof(old) new __attribute__((weak,alias(LUNAR_STRING(old))))
