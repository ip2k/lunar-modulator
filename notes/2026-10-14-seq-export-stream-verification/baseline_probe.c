#include "fm1_seq.h"
#include <stdio.h>
#include <stdlib.h>
static char input[262144], output[262144];
int main(int argc,char **argv) {
 fm1_seq_limits_t lim; size_t n; FILE *f; void *mem; fm1_seq_t *s;
 if(argc!=3 || !(f=fopen(argv[1],"rb")))return 1;
 n=fread(input,1,sizeof input,f);fclose(f); if(n==sizeof input)return 2;
 fm1_seq_limits_default(&lim,8);lim.compat=(uint8_t)atoi(argv[2]);
 mem=calloc(1,fm1_seq_size(&lim));if(!mem)return 3;
 s=fm1_seq_create(mem,&lim,44118);if(!s||!fm1_seq_import_movy1(s,input,n))return 4;
 n=fm1_seq_export_movy1(s,output,sizeof output);if(n>=sizeof output)return 5;
 if(fwrite(output,1,n,stdout)!=n)return 6;
 free(mem);return 0;
}
