#pragma once
#include <WebServer.h>
#include <vector>
#include <errno.h>
#include <lwip/sockets.h>

// Keep Arduino's routing/authentication/response API, but never enter its
// blocking request parser. Parsing below advances only while bytes are ready.
namespace BoundedHTTP {
// Arduino 2.0.17 connected() reads stale errno after a zero-length recv.
// Check actual EOF instead, including bytes already held by WiFiClient.
inline bool connected(WiFiClient &client){
 if(client.fd()<0)return false;
 if(client.available()>0)return true;
 uint8_t byte;int result=::recv(client.fd(),&byte,1,MSG_PEEK|MSG_DONTWAIT);
 return result>0||(result<0&&(errno==EAGAIN||errno==EWOULDBLOCK));
}
inline size_t write(WiFiClient &client,const uint8_t *bytes,size_t length,uint32_t deadline){
 size_t done=0;
 while(done<length&&client.fd()>=0&&int32_t(millis()-deadline)<0){
  int count=::send(client.fd(),bytes+done,min(length-done,size_t(1436)),MSG_DONTWAIT);
  if(count>0)done+=count;
  else if(count<0&&errno!=EAGAIN&&errno!=EWOULDBLOCK)break;
  else delay(1);
 }
 if(done<length)client.stop();
 return done;
}
}

class BoundedWebServer:public WebServer {
 enum Phase {Headers,JsonBody,PartHeaders,FileData,FileEnd};
 Phase phase=Headers;
 bool active=false,uploadActive=false;
 uint32_t started=0,lastByte=0;
 size_t received=0,lineSize=0;
 String input,body,boundary,marker,endBytes;
 std::vector<uint8_t> held;
 std::function<bool()> guard;
 std::function<void()> finished;

 void reset(){
  phase=Headers;received=lineSize=0;input="";body="";boundary="";endBytes="";held.clear();uploadActive=false;
  _currentUpload.reset();_currentRaw.reset();_currentUri="";_hostHeader="";_responseHeaders="";
  _currentVersion=1;_chunked=false;_clientContentLength=0;_contentLength=CONTENT_LENGTH_NOT_SET;_currentHandler=nullptr;
  for(int i=0;i<_headerKeysCount;i++)_currentHeaders[i].value="";
  _parseArguments("");started=lastByte=millis();
 }
 void finish(bool okay){
  if(uploadActive&&!okay&&_currentUpload&&_currentHandler){
   _currentUpload->status=UPLOAD_FILE_ABORTED;_currentHandler->upload(*this,_currentUri,*_currentUpload);
  }
  if(finished)finished();
  _currentClient.stop();_currentClient=WiFiClient();active=false;
  _currentUpload.reset();uploadActive=false;
 }
 void reject(int code,const char *message){send(code,"application/json",String("{\"error\":\"")+message+"\"}");finish(false);}
 void dispatch(){_handleRequest();finish(true);}
 bool parseHeaders(){
  int end=input.indexOf("\r\n"),first=input.indexOf(' '),second=input.indexOf(' ',first+1);
  if(end<0||first<1||second<first||second>=end||end>512){reject(400,"Invalid request line");return false;}
  String method=input.substring(0,first),target=input.substring(first+1,second),version=input.substring(second+1,end);
  if((method!="GET"&&method!="POST")||!target.startsWith("/")||(version!="HTTP/1.1"&&version!="HTTP/1.0")){reject(400,"Unsupported HTTP request");return false;}
  _currentVersion=version=="HTTP/1.0"?0:1;_currentMethod=method=="GET"?HTTP_GET:HTTP_POST;
  int query=target.indexOf('?');_currentUri=query<0?target:target.substring(0,query);_parseArguments(query<0?"":target.substring(query+1));
  bool lengthSeen=false,hostSeen=false,typeSeen=false,authSeen=false,originSeen=false,tokenSeen=false;String contentType;
  while(end+2<int(input.length())){
   int begin=end+2;end=input.indexOf("\r\n",begin);if(end==begin)break;
   int colon=input.indexOf(':',begin);if(end<0||colon<=begin||colon>=end){reject(400,"Invalid header");return false;}
   String key=input.substring(begin,colon),value=input.substring(colon+1,end);value.trim();
   if(key.equalsIgnoreCase("Transfer-Encoding")){reject(400,"Transfer-Encoding is unsupported");return false;}
   if(key.equalsIgnoreCase("Content-Length")){
    if(lengthSeen||value.isEmpty()){reject(400,"Invalid Content-Length");return false;}lengthSeen=true;
    uint32_t length=0;for(char c:value){if(c<'0'||c>'9'||length>209715||length*10+uint32_t(c-'0')>2097152){reject(413,"Request body too large");return false;}length=length*10+c-'0';}
    _clientContentLength=length;
   }
   if(key.equalsIgnoreCase("Host")){if(hostSeen){reject(400,"Duplicate Host");return false;}hostSeen=true;_hostHeader=value;}
   if(key.equalsIgnoreCase("Content-Type")){if(typeSeen){reject(400,"Duplicate Content-Type");return false;}typeSeen=true;contentType=value;}
   bool *seen=key.equalsIgnoreCase("Authorization")?&authSeen:key.equalsIgnoreCase("Origin")?&originSeen:key.equalsIgnoreCase("X-Companion-Token")?&tokenSeen:nullptr;
   if(seen){if(*seen){reject(400,"Duplicate authorization header");return false;}*seen=true;}
   _collectHeader(key.c_str(),value.c_str());
  }
  for(RequestHandler *handler=_firstHandler;handler;handler=handler->next())if(handler->canHandle(_currentMethod,_currentUri)){_currentHandler=handler;break;}
  // Authentication, origin, route, MIME and route-specific size before body.
  if(guard&&!guard()){finish(false);return false;}
  if(_currentMethod==HTTP_GET){if(_clientContentLength){reject(400,"GET body is unsupported");return false;}dispatch();return false;}
  if(!lengthSeen){reject(411,"Content-Length is required");return false;}
  input="";started=lastByte=millis();
  if(contentType.startsWith("multipart/form-data")){
   int boundaryIndex=contentType.indexOf("boundary=");if(boundaryIndex<0){reject(400,"Missing multipart boundary");return false;}
   boundary=contentType.substring(boundaryIndex+9);boundary.trim();if(boundary.startsWith("\"")&&boundary.endsWith("\""))boundary=boundary.substring(1,boundary.length()-1);
   if(boundary.isEmpty()||boundary.length()>70){reject(400,"Invalid multipart boundary");return false;}
   for(char c:boundary)if(c<33||c>126||c=='"'){reject(400,"Invalid multipart boundary");return false;}
   phase=PartHeaders;marker="\r\n--"+boundary;held.reserve(marker.length());
  }else{phase=JsonBody;if(!body.reserve(_clientContentLength)){reject(503,"Insufficient memory");return false;}}
  if(!_clientContentLength)completeBody();
  return active;
 }
 void uploadChunk(){
  if(_currentUpload->currentSize){_currentUpload->status=UPLOAD_FILE_WRITE;_currentHandler->upload(*this,_currentUri,*_currentUpload);_currentUpload->totalSize+=_currentUpload->currentSize;_currentUpload->currentSize=0;}
 }
 void fileByte(uint8_t byte){
  _currentUpload->buf[_currentUpload->currentSize++]=byte;
  if(_currentUpload->currentSize==HTTP_UPLOAD_BUFLEN)uploadChunk();
 }
 void partHeaders(){
  if(!input.startsWith("--"+boundary+"\r\n")||!_currentHandler||!_currentHandler->canUpload(_currentUri)){reject(400,"Invalid upload");return;}
  int begin=input.indexOf("\r\n")+2;bool disposition=false;String filename;
  while(begin<int(input.length())-2){
   int end=input.indexOf("\r\n",begin);String line=input.substring(begin,end);int colon=line.indexOf(':');
   if(colon<1){reject(400,"Invalid multipart header");return;}
   String key=line.substring(0,colon),value=line.substring(colon+1);value.trim();
   if(key.equalsIgnoreCase("Content-Disposition")){
    int name=value.indexOf("; name=\""),file=value.indexOf("; filename=\"");
    if(disposition||!value.startsWith("form-data")||name<0||file<0||value.substring(name+8,value.indexOf('"',name+8))!="firmware"){reject(400,"Expected one firmware file");return;}
    disposition=true;filename=value.substring(file+12,value.indexOf('"',file+12));
   }else if(!key.equalsIgnoreCase("Content-Type")){reject(400,"Unsupported multipart header");return;}
   begin=end+2;
  }
  if(!disposition){reject(400,"Missing firmware file");return;}
  _currentUpload.reset(new HTTPUpload());_currentUpload->name="firmware";_currentUpload->filename=filename;_currentUpload->type="application/octet-stream";
  _currentUpload->totalSize=_currentUpload->currentSize=0;_currentUpload->status=UPLOAD_FILE_START;uploadActive=true;
  _currentHandler->upload(*this,_currentUri,*_currentUpload);input="";phase=FileData;
 }
 void consumeBody(uint8_t byte){
  received++;
  if(phase==JsonBody){if(!body.concat(char(byte))){reject(503,"Insufficient memory");return;}}
  else if(phase==PartHeaders){
   if(input.length()>=2048||!input.concat(char(byte))){reject(413,"Multipart headers too large");return;}
   if(input.endsWith("\r\n\r\n"))partHeaders();
  }else if(phase==FileData){
   held.push_back(byte);
   while(!held.empty()&&memcmp(held.data(),marker.c_str(),held.size())!=0){fileByte(held.front());held.erase(held.begin());}
   if(held.size()==marker.length()){held.clear();uploadChunk();phase=FileEnd;}
  }else if(phase==FileEnd){
   static const char ending[]="--\r\n";
   if(endBytes.length()>=4||byte!=uint8_t(ending[endBytes.length()])){reject(400,"Only one multipart file is allowed");return;}
   endBytes+=char(byte);
   if(endBytes.length()==4&&received!=size_t(_clientContentLength)){reject(400,"Unexpected multipart epilogue");return;}
  }
  if(active&&received==size_t(_clientContentLength))completeBody();
 }
 void completeBody(){
  if(phase==JsonBody){
   auto *arguments=new RequestArgument[_currentArgCount+1];for(int i=0;i<_currentArgCount;i++)arguments[i]=_currentArgs[i];
   delete[] _currentArgs;_currentArgs=arguments;_currentArgs[_currentArgCount].key="plain";_currentArgs[_currentArgCount++].value=body;dispatch();
  }else if(phase==FileEnd&&(endBytes=="--"||endBytes=="--\r\n")){
   _currentUpload->status=UPLOAD_FILE_END;_currentHandler->upload(*this,_currentUri,*_currentUpload);dispatch();
  }else reject(400,"Incomplete request body");
 }
protected:
 size_t _currentClientWrite(const char *bytes,size_t length) override{return BoundedHTTP::write(_currentClient,reinterpret_cast<const uint8_t*>(bytes),length,millis()+2000);}
 size_t _currentClientWrite_P(PGM_P bytes,size_t length) override{return _currentClientWrite(bytes,length);}
public:
 explicit BoundedWebServer(int port):WebServer(port){}
 void onPreflight(std::function<bool()> callback){guard=callback;}
 void onFinished(std::function<void()> callback){finished=callback;}
 void handleClient() override{
  if(!active){_currentClient=_server.available();if(_currentClient.fd()<0)return;active=true;reset();_currentClient.setNoDelay(true);}
  const bool upload=phase==PartHeaders||phase==FileData||phase==FileEnd;
  uint32_t now=millis(),total=phase==Headers?2000:upload?120000:3000,idle=phase==Headers?500:upload?3000:1000;
  if(now-started>=total||now-lastByte>=idle){reject(408,"Request timeout");return;}
  size_t budget=4096;
  while(active&&_currentClient.available()&&budget){
   uint8_t chunk[1024];
   int count=_currentClient.read(chunk,min(size_t(_currentClient.available()),min(budget,sizeof(chunk))));
   if(count<=0)break;budget-=count;lastByte=millis();
   for(int index=0;active&&index<count;index++){
   int value=chunk[index];
   if(phase==Headers){
    if(input.length()>=4096||++lineSize>1024||((value<32&&value!='\r'&&value!='\n'&&value!='\t'))||!input.concat(char(value))){reject(431,"Request headers too large or invalid");return;}
    if(value=='\n')lineSize=0;
    if(input.endsWith("\r\n\r\n"))parseHeaders();
   }else consumeBody(uint8_t(value));
   }
  }
  if(active&&!BoundedHTTP::connected(_currentClient)&&!_currentClient.available())finish(false);
 }
};
