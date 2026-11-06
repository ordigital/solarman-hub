#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace V5 {
constexpr size_t Maximum=4096;
inline uint16_t word(const uint8_t *p){return uint16_t(p[0])|(uint16_t(p[1])<<8);}
inline uint32_t serial(const uint8_t *p){return uint32_t(p[7])|(uint32_t(p[8])<<8)|(uint32_t(p[9])<<16)|(uint32_t(p[10])<<24);}
inline uint16_t response(uint16_t code){switch(code){case 0x4110:return 0x1110;case 0x4210:return 0x1210;case 0x4310:return 0x1310;case 0x4710:return 0x1710;case 0x4810:return 0x1810;default:return 0;}}
inline bool knownAck(uint16_t code){return code==0x1110||code==0x1210||code==0x1310||code==0x1710||code==0x1810;}
inline bool valid(const uint8_t *data,size_t n){if(n<13||n>Maximum||data[0]!=0xa5||data[n-1]!=0x15||size_t(word(data+1))+13!=n)return false;uint8_t checksum=0;for(size_t i=1;i<n-2;i++)checksum+=data[i];return checksum==data[n-2];}
inline size_t ack(const uint8_t *frame,uint8_t *out,uint8_t serverSequence,uint32_t epoch,int32_t offsetMinutes){
 if(!response(word(frame+3))||epoch<1700000000UL)return 0;
 memset(out,0,23);out[0]=0xa5;out[1]=10;uint16_t code=response(word(frame+3));out[3]=code&255;out[4]=code>>8;out[5]=serverSequence;out[6]=frame[6];memcpy(out+7,frame+7,4);out[11]=word(frame+1)?frame[11]:0;out[12]=1;
 for(size_t i=0;i<4;i++){out[13+i]=epoch>>(8*i);out[17+i]=uint32_t(offsetMinutes)>>(8*i);}for(size_t i=1;i<21;i++)out[21]+=out[i];out[22]=0x15;return 23;
}
struct Framer {
 uint8_t bytes[Maximum];size_t used=0;uint32_t invalid=0;
 template<class Callback>void feed(uint8_t byte,Callback callback){
  if(used==Maximum){memmove(bytes,bytes+1,--used);invalid++;}
  bytes[used++]=byte;
  while(used){if(bytes[0]!=0xa5){memmove(bytes,bytes+1,--used);invalid++;continue;}if(used<3)return;size_t n=word(bytes+1)+13;if(n>Maximum){memmove(bytes,bytes+1,--used);invalid++;continue;}if(used<n)return;
   if(!valid(bytes,n)){memmove(bytes,bytes+1,--used);invalid++;continue;}callback(bytes,n);if(used<n)return;used-=n;memmove(bytes,bytes+n,used);
  }
 }
 void clear(){used=0;invalid=0;}
};
}
