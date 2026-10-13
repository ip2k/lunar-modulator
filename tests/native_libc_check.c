// SPDX-License-Identifier: MIT
#include <math.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern float probe_sinf(float),probe_tanf(float),probe_expf(float),probe_exp2f(float),probe_logf(float),probe_log10f(float),probe_sqrtf(float),probe_ceilf(float),probe_floorf(float),probe_roundf(float),probe_fabsf(float),probe_powf(float,float);
extern double probe_sin(double),probe_log(double),probe_floor(double),probe_pow(double,double),probe_fmod(double,double);
extern long probe_lrintf(float);
extern int probe___fpclassifyf(float),probe_atoi(const char *),probe_isdigit(int),probe_isspace(int);
extern void *probe_memcpy(void *,const void *,size_t),*probe_memmove(void *,const void *,size_t),*probe_memset(void *,int,size_t);
static int closef(float a,float b){if(a==b)return a!=0 || signbit(a)==signbit(b);return (isnan(a)&&isnan(b)) || (isfinite(a)&&isfinite(b)&&fabsf(a-b)<=4e-6f*fmaxf(fabsf(b),1e-30f));}
static int closed(double a,double b){if(a==b)return a!=0 || signbit(a)==signbit(b);return (isnan(a)&&isnan(b)) || (isfinite(a)&&isfinite(b)&&fabs(a-b)<=4e-13*fmax(fabs(b),1e-300));}
#define CF(fn,x) do {float xx=(x),a=probe_##fn(xx),b=fn(xx); if(!closef(a,b)){fprintf(stderr,#fn " x=%g got=%g want=%g\n",(double)xx,(double)a,(double)b);return 1;}}while(0)
#define CD(fn,x) do {double xx=(x),a=probe_##fn(xx),b=fn(xx); if(!closed(a,b)){fprintf(stderr,#fn " x=%g got=%g want=%g\n",xx,a,b);return 1;}}while(0)
int main(int argc,char **argv){int shard=argc>1?atoi(argv[1]):0;unsigned count=0;
 for(int i=shard;i<16384;i+=16){float x=(i-8192)*0.03125f,p=(i+1)*0.03125f,e=(i-8192)*0.009f;
 CF(sinf,x);CF(tanf,x);CF(expf,e);CF(exp2f,e);CF(logf,p);CF(log10f,p);CF(sqrtf,p);CF(ceilf,x);CF(floorf,x);CF(roundf,x);CF(fabsf,x);CD(sin,(double)x);CD(log,(double)p);CD(floor,(double)x);
 if(probe_lrintf(x)!=lrintf(x)||!closef(probe_powf(p,0.375f),powf(p,0.375f))||!closed(probe_pow(p,0.375),pow(p,0.375))||!closed(probe_fmod(x,3.125),fmod(x,3.125)))return 2;count++;
 }
 for(unsigned exponent=0;exponent<256;exponent++)for(unsigned mantissa=shard;mantissa<256;mantissa+=16)for(unsigned sign=0;sign<2;sign++){
 uint32_t raw=(sign<<31)|(exponent<<23)|((mantissa*32897u)&0x7fffffu);float value;memcpy(&value,&raw,sizeof value);
 if(probe___fpclassifyf(value)!=fpclassify(value))return 6;
 }
 for(int c=-1;c<=255;c++)if(!!probe_isdigit(c)!=!!isdigit(c)||!!probe_isspace(c)!=!!isspace(c))return 8;
 for(int i=shard;i<4096;i+=16){char number[64];int value=(i-2048)*1048576;snprintf(number,sizeof number," \t%+d trailing",value);if(probe_atoi(number)!=atoi(number))return 9;}
 if(probe_atoi("-2147483648")!=(-2147483647-1)||probe_atoi("2147483647")!=2147483647)return 10;
 float edges[]={0.0f,-0.0f,INFINITY,-INFINITY,NAN,0x1p-149f,-0x1p-149f,0x1.fffffep127f,-0x1.fffffep127f};
 for(unsigned i=0;i<sizeof edges/sizeof *edges;i++){if(probe___fpclassifyf(edges[i])!=fpclassify(edges[i]))return 7;CF(sinf,edges[i]);CF(expf,edges[i]);CF(exp2f,edges[i]);CF(logf,edges[i]);CF(sqrtf,edges[i]);CF(floorf,edges[i]);CF(roundf,edges[i]);}
 for(unsigned n=shard;n<=512;n+=16)for(unsigned so=0;so<16;so++)for(unsigned d=0;d<16;d++){
 unsigned char source[544],a[544],b[544];for(unsigned j=0;j<544;j++)source[j]=(j*73u+n)&255u;
 memset(a,0xA5,sizeof a);memset(b,0xA5,sizeof b);probe_memcpy(a+d,source+so,n);memcpy(b+d,source+so,n);if(memcmp(a,b,sizeof a))return 3;
 probe_memset(a+d,0x34,n);memset(b+d,0x34,n);if(memcmp(a,b,sizeof a))return 4;
 memcpy(a,source,sizeof a);memcpy(b,source,sizeof b);probe_memmove(a+d,a+so,n);memmove(b+d,b+so,n);if(memcmp(a,b,sizeof a))return 5;
 }
 printf("shard %d: %u numerical rows and memory alignment/overlap checks passed\n",shard,count);return 0;}
