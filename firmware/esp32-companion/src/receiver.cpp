#include "companion.h"
#include "v5_protocol.h"
#include "builtin_profile.h"
#include <deque>
#include <vector>
#include <time.h>
static WiFiServer listener(10000);
static WiFiClient logger,cloud;
static V5::Framer loggerFrames,cloudFrames;
static std::deque<std::vector<uint8_t>> pending;
static std::vector<uint8_t> handshake,report;
static uint32_t serialNumber=0,received=0,cloudAcks=0,localAcks=0,lastActivity=0,deadline=0;
static uint16_t expected=0;
static uint8_t expectedSequence=0,serverSequence=0;
static bool waiting=false,bootstrap=false,paused=false;
static String lastError;
// DNS can block inside the Arduino network stack for tens of seconds. Keep it
// off the receiver loop; only one lookup and one result may be outstanding.
static QueueHandle_t dnsResults=nullptr;
static TaskHandle_t dnsTask=nullptr;
static bool dnsBusy=false;
static IPAddress cachedIP;
static uint32_t dnsExpires=0,dnsRetry=0,dnsWaitStarted=0;
static void resolveTask(void*){
 while(true){
  ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
  IPAddress address;uint32_t result=WiFi.hostByName(upstreamHost.c_str(),address)==1?uint32_t(address):0;
  xQueueOverwrite(dnsResults,&result);
 }
}
static bool upstreamAddress(IPAddress &address){
 if(address.fromString(upstreamHost))return true;
 uint32_t result=0;
 if(dnsResults&&xQueueReceive(dnsResults,&result,0)==pdTRUE){dnsBusy=false;cachedIP=IPAddress(result);dnsExpires=millis()+300000;dnsRetry=millis()+30000;}
 if(uint32_t(cachedIP)&&int32_t(millis()-dnsExpires)<0){address=cachedIP;return true;}
 if(dnsTask&&!dnsBusy&&WiFi.status()==WL_CONNECTED&&int32_t(millis()-dnsRetry)>=0){dnsBusy=true;xTaskNotifyGive(dnsTask);}
 return false;
}
static void closeCloud(){cloud.stop();cloudFrames.clear();waiting=false;bootstrap=false;}
static bool send(WiFiClient &target,const uint8_t *bytes,size_t n){return target.fd()>=0&&target.write(bytes,n)==n;}
static void stopSession(){dnsWaitStarted=0;closeCloud();logger.stop();loggerFrames.clear();pending.clear();handshake.clear();}
static void localResponse(){
 if(pending.empty())return;
 uint8_t bytes[23];size_t n=V5::ack(pending.front().data(),bytes,++serverSequence,time(nullptr),timezoneMinutes);
 if(!n){lastError="Clock unavailable: set browser time or wait for NTP before local ACK";stopSession();return;}
 if(send(logger,bytes,n))localAcks++;else logger.stop();pending.pop_front();waiting=false;dnsWaitStarted=0;
}
static void fromLogger(const uint8_t *bytes,size_t n){
 uint32_t found=V5::serial(bytes);
 if(!found||(allowedSerial&&found!=allowedSerial)||(serialNumber&&found!=serialNumber)){lastError="Logger serial rejected";logger.stop();return;}
 if(!report.empty()&&V5::serial(report.data())!=found)report.clear();
 serialNumber=found;received++;lastActivity=millis();uint16_t code=V5::word(bytes+3);
 if(code==0x4110)handshake.assign(bytes,bytes+n);
 if(code==0x4210||report.empty())report.assign(bytes,bytes+n);
 if(V5::response(code)){
  if(pending.size()>=4){lastError="Upload queue full";logger.stop();return;}
  pending.emplace_back(bytes,bytes+n);
 }else if(BoundedHTTP::connected(cloud)&&!send(cloud,bytes,n))closeCloud();
}
static void fromCloud(const uint8_t *bytes,size_t n){
 if(V5::serial(bytes)!=serialNumber){lastError="Upstream serial mismatch";closeCloud();return;}
 uint16_t code=V5::word(bytes+3);
 if(V5::knownAck(code)){
  if(!waiting||code!=expected||bytes[6]!=expectedSequence)return;
  serverSequence=bytes[5];
  if(bootstrap){waiting=false;bootstrap=false;return;}
  if(send(logger,bytes,n))cloudAcks++;else logger.stop();
  if(!pending.empty())pending.pop_front();waiting=false;dnsWaitStarted=0;
 }else send(logger,bytes,n);
}
void receiverBegin(){
 listener.begin();listener.setNoDelay(true);lastActivity=millis();
 IPAddress numeric;
 if(upstreamEnabled&&!numeric.fromString(upstreamHost)){
  dnsResults=xQueueCreate(1,sizeof(uint32_t));
  if(!dnsResults||xTaskCreate(resolveTask,"upstream-dns",4096,nullptr,1,&dnsTask)!=pdPASS){
   if(dnsResults){vQueueDelete(dnsResults);dnsResults=nullptr;}dnsTask=nullptr;lastError="DNS worker unavailable";
  }
 }
}
void receiverResume(){paused=false;listener.begin();listener.setNoDelay(true);}
void receiverPause(){paused=true;stopSession();listener.stop();}
void receiverLoop(){
 if(paused)return;
 if(upstreamEnabled&&dnsTask&&WiFi.status()==WL_CONNECTED){IPAddress unused;upstreamAddress(unused);}
 WiFiClient incoming=listener.available();
 if(incoming.fd()>=0){if(BoundedHTTP::connected(logger))incoming.stop();else{stopSession();logger=incoming;logger.setTimeout(2);lastActivity=millis();serialNumber=0;}}
 if(!BoundedHTTP::connected(logger)){if(waiting||!pending.empty()||BoundedHTTP::connected(cloud))stopSession();return;}
 size_t budget=8192;
 while(logger.available()&&budget--){uint8_t byte=logger.read();loggerFrames.feed(byte,fromLogger);}
 if(loggerFrames.invalid>4096||millis()-lastActivity>400000){lastError="Session idle or malformed";stopSession();return;}
 budget=8192;while(cloud.available()&&budget--){uint8_t byte=cloud.read();cloudFrames.feed(byte,fromCloud);}
 if(waiting&&(!BoundedHTTP::connected(cloud)||int32_t(millis()-deadline)>=0)){lastError="Upstream timeout: local ACK";closeCloud();localResponse();return;}
 if(waiting||pending.empty())return;
 if(!upstreamEnabled){localResponse();return;}
 if(!BoundedHTTP::connected(cloud)){
  cloud.stop();cloudFrames.clear();
  IPAddress address;
  if(!upstreamAddress(address)){
   if(dnsBusy){if(!dnsWaitStarted)dnsWaitStarted=millis();if(millis()-dnsWaitStarted<3000)return;}
   lastError="Upstream DNS unavailable or timed out: local ACK";localResponse();return;
  }
  dnsWaitStarted=0;
  if(!cloud.connect(address,upstreamPort,3000)){cachedIP=IPAddress();dnsRetry=millis()+30000;lastError="Upstream unavailable: local ACK";localResponse();return;}
  cloud.setTimeout(2);
  if(!handshake.empty()&&V5::word(pending.front().data()+3)!=0x4110){
   if(!send(cloud,handshake.data(),handshake.size())){closeCloud();localResponse();return;}
   expected=0x1110;expectedSequence=handshake[6];waiting=true;bootstrap=true;deadline=millis()+uint32_t(upstreamTimeout)*1000;return;
  }
 }
 auto &frame=pending.front();
 if(!send(cloud,frame.data(),frame.size())){closeCloud();localResponse();return;}
 expected=V5::response(V5::word(frame.data()+3));expectedSequence=frame[6];waiting=true;deadline=millis()+uint32_t(upstreamTimeout)*1000;
}
void receiverStatus(JsonObject object){object["logger_connected"]=BoundedHTTP::connected(logger);object["upstream_connected"]=BoundedHTTP::connected(cloud);object["logger_serial"]=serialNumber;object["frames"]=received;object["cloud_acks"]=cloudAcks;object["local_acks"]=localAcks;object["last_error"]=lastError;object["queue"]=pending.size();object["dns_pending"]=dnsBusy;object["frame_length"]=report.size();object["frame_code"]=report.empty()?0:V5::word(report.data()+3);}
String profileDefinition(const String &type){
 if(type=="known"){
  if(report.size()!=2115||V5::word(report.data()+3)!=0x4210)return "";
  DynamicJsonDocument document(24576);deserializeJson(document,FPSTR(BUILTIN_PROFILE));document["id"]="companion-sofar-hyd-g3-2115";document["description"]="Known Sofar HYD G3 map. Code and length matched; compare readings independently before using with another model.";
  String output;serializeJson(document,output);return output;
 }
 if(type!="draft"||report.size()<15)return "";
 DynamicJsonDocument document(24576);document["schema_version"]=1;document["id"]="companion-v5-draft";document["name"]="Unverified V5 raw fields";document["description"]="UNVERIFIED raw words: names, units, scaling and meaning must be established with independent measurements. Do not use as energy sensors.";document["manufacturer"]="";document["model"]="";document["match"]["code"]=V5::word(report.data()+3);document["match"]["length"]=report.size();document["timestamp"]=nullptr;
 JsonArray fields=document.createNestedArray("fields");
 for(size_t offset=11;offset+2<=report.size()-2&&fields.size()<64;offset+=2){JsonObject field=fields.createNestedObject();char id[24];snprintf(id,sizeof(id),"raw_%04u",unsigned(offset));field["id"]=id;field["name"]=String("Raw word at offset ")+offset;field["offset"]=offset;field["size"]=2;field["endian"]="big";field["signed"]=false;field["scale"]=1;field["unit"]="";field["device_class"]=nullptr;field["state_class"]=nullptr;field["register"]=nullptr;}
 String output;serializeJson(document,output);return output;
}
bool buildBundle(JsonDocument &document,const String &type,bool includeSample){
 if(report.empty()||!serialNumber)return false;
 String profile=profileDefinition(type);if(profile.isEmpty())return false;
 document["bundle_version"]=1;document["verification"]=type=="known"?"known-map":"unverified";
 DynamicJsonDocument parsed(24576);if(deserializeJson(parsed,profile))return false;document["profile"].set(parsed.as<JsonObject>());
 document["logger"]["serial"]=V5::serial(report.data());document["logger"]["name"]="Captured logger";document["logger"]["profile"]=document["profile"]["id"];
 if(includeSample){String hex;hex.reserve(report.size()*2);for(uint8_t byte:report){char pair[3];snprintf(pair,3,"%02x",byte);hex+=pair;}document["sample_hex"]=hex;}
 return !document.overflowed();
}
