#include "companion.h"
#include "web_ui.h"
#include <Preferences.h>
#include <LittleFS.h>
#include <Update.h>
#include <ESPmDNS.h>
#include <esp_wifi.h>
#include <esp_ota_ops.h>
#include <sys/time.h>
#include <math.h>

BoundedWebServer web(80);
String mode,ssid,wifiPassword,apBssid,loggerMac,upstreamHost;
bool pinAP=false,upstreamEnabled=false;
uint16_t upstreamPort=10000,upstreamTimeout=30;
uint32_t allowedSerial=0;
int32_t timezoneMinutes=0;
static Preferences preferences;
static String adminKey,setupKey,setupSSID,csrf,serialLine;
static bool portal=false,mdns=false,filesystemReady=false,uploadAuthorized=false,uploadStarted=false,uploadReady=false,uploadFailed=false;
static uint32_t restartAt=0,disconnectedAt=0,uploadBytes=0,uploadFiles=0;
static size_t markerMatched=0;
static bool markerFound=false,uploadPaused=false,otaCommitted=false;
static const char PRODUCT_MARKER[]="SOLARMAN_COMPANION_FW_V0";
static const char VERSION[]="0.2.1";
static String randomKey(){char value[33];snprintf(value,sizeof(value),"%08lx%08lx%08lx%08lx",(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random());return value;}
bool clockValid(){return time(nullptr)>=1700000000UL;}
static void error(int code,const String &text){DynamicJsonDocument doc(512);doc["error"]=text;String value;serializeJson(doc,value);web.send(code,"application/json",value);}
static bool auth(){if(web.authenticate("admin",adminKey.c_str()))return true;web.requestAuthentication(BASIC_AUTH,"Solarman Companion","Administrator password required");return false;}
static bool mutationAuth(){
 if(!auth())return false;
 if(web.header("X-Companion-Token")!=csrf){error(403,"Missing or invalid request token");return false;}
 String origin=web.header("Origin");if(!origin.isEmpty()&&origin!="http://"+web.hostHeader()){error(403,"Invalid request origin");return false;}return true;
}
static void jsonResponse(JsonDocument &document){String text;serializeJson(document,text);web.sendHeader("Cache-Control","no-store");web.send(200,"application/json",text);}
static bool mac(const String &text,uint8_t *out){
 if(text.length()!=17)return false;uint8_t bytes[6];
 for(int i=0;i<6;i++){int pos=i*3;if(!isxdigit(text[pos])||!isxdigit(text[pos+1])||(i<5&&text[pos+2]!=':'))return false;bytes[i]=strtoul(text.substring(pos,pos+2).c_str(),nullptr,16);}
 if(bytes[0]&1)return false;bool nonzero=false;for(uint8_t byte:bytes)nonzero|=byte!=0;if(!nonzero)return false;if(out)memcpy(out,bytes,6);return true;
}
static void configDocument(JsonDocument &doc){doc["mode"]=mode;doc["ssid"]=ssid;doc["password_set"]=!wifiPassword.isEmpty();doc["logger_mac"]=loggerMac;doc["allowed_serial"]=allowedSerial;doc["bssid"]=apBssid;doc["pin_ap"]=pinAP;doc["upstream_enabled"]=upstreamEnabled;doc["upstream_host"]=upstreamHost;doc["upstream_port"]=upstreamPort;doc["upstream_timeout"]=upstreamTimeout;doc["timezone_minutes"]=timezoneMinutes;}
static bool saveConfig(JsonDocument &doc){
 String nextMode=doc["mode"]|mode,nextSsid=doc["ssid"]|ssid,nextMac=doc["logger_mac"]|loggerMac,nextBssid=doc["bssid"]|apBssid,nextHost=doc["upstream_host"]|upstreamHost;
 String nextPassword=doc["password"]|"";if(nextPassword.isEmpty())nextPassword=wifiPassword;if(doc["clear_password"]==true)nextPassword="";
 uint64_t serial=doc["allowed_serial"]|uint64_t(allowedSerial);int timeout=doc["upstream_timeout"]|int(upstreamTimeout);int port=doc["upstream_port"]|int(upstreamPort),offset=doc["timezone_minutes"]|int(timezoneMinutes);
 bool nextPin=doc["pin_ap"]|pinAP,nextUpstream=doc["upstream_enabled"]|upstreamEnabled;
 if((nextMode!="receiver"&&nextMode!="passive")||nextSsid.length()>32||nextPassword.length()>63||(!nextPassword.isEmpty()&&nextPassword.length()<8)||serial>0xffffffffULL||port<1||port>65535||timeout<10||timeout>120||offset< -720||offset>840||nextHost.length()>253||nextHost.isEmpty())return false;
 if((!nextMac.isEmpty()&&!mac(nextMac,nullptr))||(!nextBssid.isEmpty()&&!mac(nextBssid,nullptr))||(nextPin&&nextBssid.isEmpty())||(nextMode=="passive"&&nextMac.isEmpty()))return false;
 DynamicJsonDocument stored(2048);stored["mode"]=nextMode;stored["ssid"]=nextSsid;stored["password"]=nextPassword;stored["logger_mac"]=nextMac;stored["allowed_serial"]=serial;stored["bssid"]=nextBssid;stored["pin_ap"]=nextPin;stored["upstream_enabled"]=nextUpstream;stored["upstream_host"]=nextHost;stored["upstream_port"]=port;stored["upstream_timeout"]=timeout;stored["timezone_minutes"]=offset;
 String output;serializeJson(stored,output);return preferences.putString("config",output)==output.length();
}
static void portalStart(){if(portal)return;uint8_t channel=1;wifi_second_chan_t second;esp_wifi_get_channel(&channel,&second);if(channel<1||channel>13)channel=1;WiFi.mode(WIFI_AP_STA);portal=WiFi.softAP(setupSSID.c_str(),setupKey.c_str(),channel);if(portal)Serial.printf("SETUP URL: http://192.168.4.1/\n");}
static bool profileValid(JsonDocument &doc){
 String id=doc["id"]|"";if(id.isEmpty()||id.length()>64||!isLowerCase(id[0]))return false;for(char c:id)if(!isLowerCase(c)&&!isDigit(c)&&c!='-')return false;
 JsonArray fields=doc["fields"].as<JsonArray>();size_t length=doc["match"]["length"]|0;uint32_t code=doc["match"]["code"]|0xffffffffUL;
 if(length<13||length>4096||code>65535||fields.size()<1||fields.size()>128)return false;
 for(JsonObject field:fields){String name=field["id"]|"";if(name.isEmpty()||name.length()>64||!isLowerCase(name[0]))return false;for(char c:name)if(!isLowerCase(c)&&!isDigit(c)&&c!='_')return false;size_t offset=field["offset"]|size_t(65536),size=field["size"]|size_t(2);if((size!=1&&size!=2&&size!=4&&size!=8)||offset+size>length-2)return false;if(field.containsKey("scale")&&(!field["scale"].is<double>()||!isfinite(field["scale"].as<double>())))return false;}
 return true;
}
static String chosenProfile(){String type=web.arg("template");if(type=="custom"){if(!filesystemReady||!LittleFS.exists("/profile.json"))return "";File file=LittleFS.open("/profile.json","r");return file.readString();}return profileDefinition(type);}
static void cancelUpload(){
 if(uploadStarted)Update.abort();
 uploadAuthorized=uploadStarted=uploadReady=uploadFailed=false;
 uploadBytes=uploadFiles=0;markerMatched=0;markerFound=false;
 if(uploadPaused){capturePause(false);if(mode=="receiver")receiverResume();uploadPaused=false;}
}
static bool requestPreflight(){
 if(!auth())return false;
 if(web.method()==HTTP_GET)return true;
 if(restartAt){error(503,"ESP32 is restarting");return false;}
 if(!mutationAuth())return false;
 String uri=web.uri(),type=web.header("Content-Type");int semicolon=type.indexOf(';');String mime=semicolon<0?type:type.substring(0,semicolon);mime.trim();
 int length=web.clientContentLength();
 if(uri=="/update"){
  const esp_partition_t *slot=esp_ota_get_next_update_partition(nullptr);
  if(mime!="multipart/form-data"||!slot||length<=0||size_t(length)>slot->size+4096){error(413,"Invalid firmware upload size or type");return false;}
 }else{
  int maximum=uri=="/api/config"?2048:uri=="/api/profile"?16384:uri=="/api/time"?128:0;
  if(!maximum){error(404,"Unknown write endpoint");return false;}
  if(mime!="application/json"){error(415,"Expected application/json");return false;}
  if(length<=0||length>maximum){error(413,"Request body too large or empty");return false;}
 }
 return true;
}
static void upload(){
 HTTPUpload &part=web.upload();
 if(part.status==UPLOAD_FILE_START){
  uploadFiles++;uploadAuthorized=web.authenticate("admin",adminKey.c_str())&&web.header("X-Companion-Token")==csrf;
  String origin=web.header("Origin");if(!origin.isEmpty()&&origin!="http://"+web.hostHeader())uploadAuthorized=false;
  if(uploadFiles>1){uploadFailed=true;Update.abort();return;}
  uploadBytes=0;uploadReady=false;uploadFailed=!uploadAuthorized;uploadStarted=false;markerMatched=0;markerFound=false;
  if(!uploadAuthorized)return;
  capturePause(true);receiverPause();uploadPaused=true;
 }else if(part.status==UPLOAD_FILE_WRITE){
  if(!uploadAuthorized||uploadFailed)return;
  if(!uploadStarted){
   if(part.currentSize<24||part.buf[0]!=0xe9||part.buf[12]!=0||part.buf[13]!=0){uploadFailed=true;return;}
   uploadStarted=Update.begin(UPDATE_SIZE_UNKNOWN,U_FLASH);if(!uploadStarted){uploadFailed=true;return;}
  }
  uploadBytes+=part.currentSize;
  const esp_partition_t *slot=esp_ota_get_next_update_partition(nullptr);
  if(!slot||uploadBytes>slot->size){uploadFailed=true;Update.abort();return;}
  for(size_t i=0;i<part.currentSize;i++){
   char c=part.buf[i];if(c==PRODUCT_MARKER[markerMatched]){markerMatched++;if(markerMatched==strlen(PRODUCT_MARKER)){markerFound=true;markerMatched=0;}}
   else markerMatched=c==PRODUCT_MARKER[0]?1:0;
  }
  if(Update.write(part.buf,part.currentSize)!=part.currentSize){uploadFailed=true;Update.abort();}
 }else if(part.status==UPLOAD_FILE_END){uploadReady=uploadAuthorized&&uploadStarted&&!uploadFailed&&markerFound;}
 else if(part.status==UPLOAD_FILE_ABORTED){cancelUpload();}
}
static void serialCommands(){
 while(Serial.available()){
  char c=Serial.read();if(c=='\r')continue;
  if(c=='\n'){
   DynamicJsonDocument doc(2048);
   if(!deserializeJson(doc,serialLine)&&doc["command"]=="status"){Serial.printf("Wi-Fi status %u, configured SSID bytes %u, key bytes %u, IP %s\n",WiFi.status(),ssid.length(),wifiPassword.length(),WiFi.localIP().toString().c_str());}
   else if(doc["command"]=="wifi"){
    doc["mode"]=mode;if(saveConfig(doc)){Serial.println("Wi-Fi configuration saved; restarting");restartAt=millis()+500;}else Serial.println("Invalid Wi-Fi configuration");
   }
   serialLine="";
  }else if(serialLine.length()<1024)serialLine+=c;else serialLine="";
 }
}
void setup(){
 Serial.begin(115200);delay(500);WiFi.persistent(false);WiFi.mode(WIFI_STA);preferences.begin("solarman-tool",false);
 adminKey=preferences.getString("admin","");if(adminKey.length()<24){adminKey=randomKey();preferences.putString("admin",adminKey);}setupKey=preferences.getString("setup","");if(setupKey.length()<16){setupKey=randomKey().substring(0,16);preferences.putString("setup",setupKey);}csrf=randomKey();
 DynamicJsonDocument doc(2048);deserializeJson(doc,preferences.getString("config","{}"));
 mode=doc["mode"]|"receiver";ssid=doc["ssid"]|"";wifiPassword=doc["password"]|"";loggerMac=doc["logger_mac"]|"";apBssid=doc["bssid"]|"";pinAP=doc["pin_ap"]|false;allowedSerial=doc["allowed_serial"]|uint32_t(0);upstreamHost=doc["upstream_host"]|"access3.solarmanpv.com";upstreamPort=doc["upstream_port"]|10000;upstreamTimeout=doc["upstream_timeout"]|30;upstreamEnabled=doc["upstream_enabled"]|false;timezoneMinutes=doc["timezone_minutes"]|0;
 filesystemReady=LittleFS.begin(true);
 WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info){if(event==ARDUINO_EVENT_WIFI_STA_DISCONNECTED)Serial.printf("Wi-Fi disconnected, reason %u\n",info.wifi_sta_disconnected.reason);});
 WiFi.persistent(false);WiFi.setAutoReconnect(true);WiFi.mode(WIFI_STA);WiFi.setHostname("solarman-companion");WiFi.setSleep(false);
 String suffix=WiFi.macAddress();suffix.replace(":","");setupSSID="SolarmanCompanion-"+suffix.substring(6);
 Serial.printf("\n%s %s\nSETUP SSID: %s\nSETUP password: %s\nADMIN user: admin\nADMIN password: %s\n",PRODUCT_MARKER,VERSION,setupSSID.c_str(),setupKey.c_str(),adminKey.c_str());
 if(ssid.isEmpty())portalStart();else{uint8_t bssid[6];if(pinAP&&mac(apBssid,bssid))WiFi.begin(ssid.c_str(),wifiPassword.c_str(),0,bssid,true);else WiFi.begin(ssid.c_str(),wifiPassword.c_str());}
 configTime(0,0,"pool.ntp.org","time.cloudflare.com");disconnectedAt=millis();
 const char *headers[]={"X-Companion-Token","Origin","Content-Type"};web.collectHeaders(headers,3);
 web.onPreflight(requestPreflight);web.onFinished([]{if(!otaCommitted)cancelUpload();});
 web.on("/",HTTP_GET,[]{if(!auth())return;web.sendHeader("Cache-Control","no-store");web.send_P(200,"text/html; charset=utf-8",COMPANION_PAGE);});
 web.on("/api/status",HTTP_GET,[]{if(!auth())return;DynamicJsonDocument data(4096);data["firmware"]=VERSION;data["product"]=PRODUCT_MARKER;data["mode"]=mode;data["connected"]=WiFi.status()==WL_CONNECTED;data["ip"]=WiFi.localIP().toString();data["csrf"]=csrf;data["channel"]=WiFi.channel();data["heap"]=ESP.getFreeHeap();data["uptime_ms"]=millis();data["clock_valid"]=clockValid();data["filesystem_ready"]=filesystemReady;if(mode=="receiver")receiverStatus(data.as<JsonObject>());else captureStatus(data.as<JsonObject>());jsonResponse(data);});
 web.on("/api/config",HTTP_GET,[]{if(!auth())return;DynamicJsonDocument data(2048);configDocument(data);web.sendHeader("Content-Disposition","attachment; filename=companion-config.json");jsonResponse(data);});
 web.on("/api/config",HTTP_POST,[]{if(!mutationAuth())return;DynamicJsonDocument data(2048);if(web.arg("plain").length()>2048||deserializeJson(data,web.arg("plain"))||!saveConfig(data)){error(400,"Invalid configuration");return;}web.send(200,"application/json","{\"ok\":true}");restartAt=millis()+1500;});
 web.on("/api/time",HTTP_POST,[]{if(!mutationAuth())return;DynamicJsonDocument data(128);if(deserializeJson(data,web.arg("plain"))||!data["unix"].is<uint32_t>()){error(400,"Invalid timestamp");return;}uint32_t epoch=data["unix"];if(epoch<1700000000UL||epoch>4102444800UL){error(400,"Invalid timestamp");return;}timeval value{time_t(epoch),0};if(!clockValid())settimeofday(&value,nullptr);web.send(200,"application/json","{\"ok\":true}");});
 web.on("/api/profile",HTTP_GET,[]{if(!auth())return;String value=chosenProfile();if(value.isEmpty()){error(409,"No matching report or saved profile; receive a report first");return;}web.sendHeader("Content-Disposition","attachment; filename=solarman-profile.json");web.send(200,"application/json",value);});
 web.on("/api/profile",HTTP_POST,[]{if(!mutationAuth())return;if(!filesystemReady){error(503,"Filesystem unavailable");return;}String body=web.arg("plain");if(body.length()>16384){error(413,"Profile too large");return;}DynamicJsonDocument request(32768);if(deserializeJson(request,body)){error(400,"Invalid JSON");return;}DynamicJsonDocument profile(24576);profile.set(request["profile"]);if(!profileValid(profile)){error(400,"Invalid profile fields or frame bounds");return;}String value;serializeJson(profile,value);if(value.length()>12288){error(413,"Profile exceeds 12 KiB storage limit");return;}File file=LittleFS.open("/profile.tmp","w");if(!file||file.print(value)!=value.length()){if(file)file.close();error(507,"Profile storage failed");return;}file.close();if(!LittleFS.rename("/profile.tmp","/profile.json")){error(507,"Profile rename failed");return;}web.send(200,"application/json","{\"ok\":true}");});
 web.on("/api/bundle",HTTP_GET,[]{if(!auth())return;DynamicJsonDocument data(49152);String type=web.arg("template");if(!buildBundle(data,type=="custom"?"draft":type,web.arg("sample")=="1")){error(409,"No captured report for this profile");return;}if(type=="custom"){String value=chosenProfile();DynamicJsonDocument profile(24576);if(value.isEmpty()||deserializeJson(profile,value)){error(409,"No saved custom profile");return;}data["profile"].set(profile.as<JsonObject>());data["logger"]["profile"]=profile["id"];data["verification"]="unverified";}if(data.overflowed()){error(507,"Not enough memory for export");return;}web.sendHeader("Content-Disposition","attachment; filename=solarman-bundle.json");jsonResponse(data);});
 web.on("/capture.pcap",HTTP_GET,[]{if(!auth())return;if(mode!="passive"){error(409,"Switch to passive mode first");return;}captureDownload();});
 web.on("/update",HTTP_POST,[]{
  if(!mutationAuth()){cancelUpload();return;}
  if(uploadFiles!=1||!uploadReady||uploadFailed||!Update.end(true)){cancelUpload();error(400,"Firmware rejected; current application kept");return;}
  otaCommitted=true;uploadFiles=0;web.send(200,"application/json","{\"ok\":true,\"restarting\":true}");restartAt=millis()+1500;
 },upload);
 web.onNotFound([]{if(!auth())return;error(404,"Not found");});web.begin();
 if(mode=="receiver")receiverBegin();else captureBegin();
}
void loop(){
 web.handleClient();serialCommands();if(mode=="receiver")receiverLoop();
 if(restartAt&&int32_t(millis()-restartAt)>=0)ESP.restart();
 static bool previous=false;bool connected=WiFi.status()==WL_CONNECTED;
 if(connected&&!previous){Serial.printf("LAN URL: http://%s/\n",WiFi.localIP().toString().c_str());if(portal){WiFi.softAPdisconnect(true);portal=false;}if(!mdns){mdns=MDNS.begin("solarman-companion");if(mdns)MDNS.addService("http","tcp",80);}}
 if(!connected&&previous)disconnectedAt=millis();if(!connected&&!portal&&millis()-disconnectedAt>30000)portalStart();previous=connected;delay(1);
}
