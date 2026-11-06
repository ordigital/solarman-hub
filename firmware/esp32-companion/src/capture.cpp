#include "companion.h"
#include <esp_wifi.h>
#include <esp_timer.h>
#include <sys/time.h>
static uint8_t LOGGER[6]={},AP[6]={};
static constexpr size_t MAX_FRAME=4096,POOL_SIZE=8,RING_SIZE=32*1024;
static bool clockSynced=false,captureReady=false;
static String captureError;
static TaskHandle_t captureTask=nullptr;
static int64_t clockOffset=0;
struct Frame {
    int64_t us;
    uint16_t len, original;
    int8_t rssi;
    uint8_t channel;
    uint8_t data[MAX_FRAME];
};
struct __attribute__((packed)) Record { uint32_t sec, usec, included, original; };
static_assert(sizeof(Record) == 16, "PCAP record size");

struct Stats {
    uint32_t seen=0, selected=0, queued=0, dropped=0, malformed=0, truncated=0;
    uint32_t loggerTx=0, loggerRx=0, beacons=0, protectedFrames=0, eapol=0;
    int rssiLogger=-127, rssiAP=-127;
};
static Stats stats;
static portMUX_TYPE statsLock = portMUX_INITIALIZER_UNLOCKED;
static QueueHandle_t freeFrames, readyFrames;
static Frame *pool;
static uint8_t *ringData;
static uint8_t *snapshotData;
static SemaphoreHandle_t ringMutex;
static size_t ringHead=0, ringUsed=0;
static uint32_t ringPackets=0, evicted=0;
static bool parseBSSID(const String &text,uint8_t *dest) {
    if (text.length()!=17) return false;
    uint8_t result[6];
    for (size_t i=0;i<6;++i) {
        size_t p=i*3;
        if (!isxdigit(text[p]) || !isxdigit(text[p+1]) || (i<5 && text[p+2]!=':')) return false;
        result[i]=strtoul(text.substring(p,p+2).c_str(),nullptr,16);
    }
    if ((result[0]&1) || memcmp(result,"\0\0\0\0\0\0",6)==0) return false;
    memcpy(dest,result,6); return true;
}

static bool same(const uint8_t *a, const uint8_t *b) { return memcmp(a,b,6)==0; }
static bool isEapol(const uint8_t *f, size_t n, uint16_t fc) {
    if ((fc & 0x4000) || ((fc>>2)&3)!=2) return false;
    size_t header=24;
    if ((fc & 0x0300)==0x0300) header+=6;
    if (fc & 0x0080) header+=2;
    if ((fc & 0x0080) && (fc & 0x8000)) header+=4;
    const uint8_t llc[] = {0xaa,0xaa,3,0,0,0,0x88,0x8e};
    return n>=header+sizeof(llc) && memcmp(f+header,llc,sizeof(llc))==0;
}

static void onFrame(void *buf, wifi_promiscuous_pkt_type_t type) {
    if (type!=WIFI_PKT_MGMT && type!=WIFI_PKT_DATA) return;
    auto *pkt=static_cast<wifi_promiscuous_pkt_t*>(buf);
    const uint8_t *f=pkt->payload;
    size_t n=pkt->rx_ctrl.sig_len;
    portENTER_CRITICAL(&statsLock); ++stats.seen; portEXIT_CRITICAL(&statsLock);
    if (pkt->rx_ctrl.rx_state!=0 || n<28) {
        portENTER_CRITICAL(&statsLock); ++stats.malformed; portEXIT_CRITICAL(&statsLock);
        return;
    }
    n-=4; // ESP-IDF sig_len includes FCS. Store frames without FCS.
    uint16_t fc=f[0] | (uint16_t(f[1])<<8);
    bool tx=same(f+10,LOGGER), rx=same(f+4,LOGGER);
    bool beacon=((fc&0x00fc)==0x0080) && same(f+16,AP);
    if (!tx && !rx && !beacon) return;
    portENTER_CRITICAL(&statsLock);
    ++stats.selected;
    if (tx) { ++stats.loggerTx; stats.rssiLogger=pkt->rx_ctrl.rssi; }
    if (rx) ++stats.loggerRx;
    if (beacon) { ++stats.beacons; stats.rssiAP=pkt->rx_ctrl.rssi; }
    if (fc&0x4000) ++stats.protectedFrames;
    if (isEapol(f,n,fc)) ++stats.eapol;
    if (n>MAX_FRAME) ++stats.truncated;
    portEXIT_CRITICAL(&statsLock);
    int64_t now=esp_timer_get_time();
    static int64_t lastBeacon=0;
    // Count every AP beacon, but retain at most one per second. Preserve all
    // selected logger data and EAPOL, which matter for offline analysis.
    if (beacon) {
        if (lastBeacon && now-lastBeacon<1000000) return;
        lastBeacon=now;
    }
    Frame *dest=nullptr;
    if (xQueueReceive(freeFrames,&dest,0)!=pdTRUE) {
        portENTER_CRITICAL(&statsLock); ++stats.dropped; portEXIT_CRITICAL(&statsLock);
        return;
    }
    dest->us=now; dest->original=n; dest->len=min(n,MAX_FRAME);
    dest->rssi=pkt->rx_ctrl.rssi; dest->channel=pkt->rx_ctrl.channel;
    memcpy(dest->data,f,dest->len);
    if (xQueueSend(readyFrames,&dest,0)!=pdTRUE) {
        xQueueSend(freeFrames,&dest,0);
        portENTER_CRITICAL(&statsLock); ++stats.dropped; portEXIT_CRITICAL(&statsLock);
    } else {
        portENTER_CRITICAL(&statsLock); ++stats.queued; portEXIT_CRITICAL(&statsLock);
    }
}

static void ringRead(size_t offset, void *dest, size_t n) {
    size_t start=(ringHead+offset)%RING_SIZE;
    size_t first=min(n,RING_SIZE-start);
    memcpy(dest,ringData+start,first);
    if (first<n) memcpy(static_cast<uint8_t*>(dest)+first,ringData,n-first);
}
static void ringWrite(const void *src,size_t n) {
    size_t start=(ringHead+ringUsed)%RING_SIZE;
    size_t first=min(n,RING_SIZE-start);
    memcpy(ringData+start,src,first);
    if (first<n) memcpy(ringData,static_cast<const uint8_t*>(src)+first,n-first);
    ringUsed+=n;
}
static void storeFrame(Frame *f) {
    uint16_t freq=f->channel==14 ? 2484 : 2407+5*f->channel;
    // Radiotap: flags (FCS stripped), channel and dBm antenna signal.
    uint8_t rt[15]={0,0,15,0,0x2a,0,0,0,0,0,uint8_t(freq),uint8_t(freq>>8),0x80,0,uint8_t(f->rssi)};
    Record rec{uint32_t(f->us/1000000),uint32_t(f->us%1000000),uint32_t(sizeof(rt)+f->len),uint32_t(sizeof(rt)+f->original)};
    size_t needed=sizeof(rec)+rec.included;
    while (ringUsed+needed>RING_SIZE) {
        Record old; ringRead(0,&old,sizeof(old));
        size_t discard=sizeof(old)+old.included;
        ringHead=(ringHead+discard)%RING_SIZE; ringUsed-=discard;
        --ringPackets; ++evicted;
    }
    ringWrite(&rec,sizeof(rec)); ringWrite(rt,sizeof(rt)); ringWrite(f->data,f->len);
    ++ringPackets;
}

static void storeTask(void*) {
    Frame *f=nullptr;
    while (true) {
        if (xQueueReceive(readyFrames,&f,portMAX_DELAY)==pdTRUE) {
            xSemaphoreTake(ringMutex,portMAX_DELAY);
            storeFrame(f);
            xSemaphoreGive(ringMutex);
            xQueueSend(freeFrames,&f,0);
        }
    }
}

static bool sendAll(WiFiClient &client,const uint8_t *data,size_t n,uint32_t deadline) {
    uint32_t lastProgress=millis();
    while (n && client.fd()>=0) {
        if (int32_t(millis()-deadline)>=0) return false;
        size_t sent=BoundedHTTP::write(client,data,min(n,size_t(1024)),deadline);
        if (sent) { data+=sent; n-=sent; lastProgress=millis(); }
        else if (millis()-lastProgress>3000) return false;
        delay(1);
    }
    return n==0;
}
static void downloadPcap() {
    // Copy a bounded snapshot under a short lock. A dedicated consumer keeps
    // draining the RX queue while HTTP sends the snapshot to a slow client.
    static const uint8_t header[]={0xd4,0xc3,0xb2,0xa1,2,0,4,0,0,0,0,0,0,0,0,0,0,0x20,0,0,127,0,0,0};
    xSemaphoreTake(ringMutex,portMAX_DELAY);
    size_t snapshotSize=ringUsed;
    ringRead(0,snapshotData,snapshotSize);
    xSemaphoreGive(ringMutex);
    size_t pos=0;
    while (pos<snapshotSize) {
        Record rec; memcpy(&rec,snapshotData+pos,sizeof(rec));
        if (clockSynced) {
            int64_t us=int64_t(rec.sec)*1000000+rec.usec+clockOffset;
            rec.sec=us/1000000; rec.usec=us%1000000;
            memcpy(snapshotData+pos,&rec,sizeof(rec));
        }
        pos+=sizeof(rec)+rec.included;
    }
    web.sendHeader("Content-Disposition","attachment; filename=solarman-companion.pcap");
    web.sendHeader("Cache-Control","no-store");
    web.setContentLength(sizeof(header)+snapshotSize);
    web.send(200,"application/vnd.tcpdump.pcap","");
    WiFiClient client=web.client();
    client.setTimeout(2);
    uint32_t deadline=millis()+8000;
    if (!sendAll(client,header,sizeof(header),deadline) ||
        !sendAll(client,snapshotData,snapshotSize,deadline)) client.stop();
}


static void captureCleanup(){
 esp_wifi_set_promiscuous(false);esp_wifi_set_promiscuous_rx_cb(nullptr);captureReady=false;
 if(captureTask){vTaskDelete(captureTask);captureTask=nullptr;}
 if(freeFrames){vQueueDelete(freeFrames);freeFrames=nullptr;}
 if(readyFrames){vQueueDelete(readyFrames);readyFrames=nullptr;}
 if(ringMutex){vSemaphoreDelete(ringMutex);ringMutex=nullptr;}
 free(ringData);free(snapshotData);free(pool);ringData=snapshotData=nullptr;pool=nullptr;
}
void captureBegin(){
 if(!parseBSSID(loggerMac,LOGGER)){captureError="Configure a valid logger MAC";return;}
 parseBSSID(apBssid,AP);
 ringData=static_cast<uint8_t*>(malloc(RING_SIZE));snapshotData=static_cast<uint8_t*>(malloc(RING_SIZE));
 pool=static_cast<Frame*>(malloc(sizeof(Frame)*POOL_SIZE));ringMutex=xSemaphoreCreateMutex();
 freeFrames=xQueueCreate(POOL_SIZE,sizeof(Frame*));readyFrames=xQueueCreate(POOL_SIZE,sizeof(Frame*));
 if(!ringData||!snapshotData||!pool||!ringMutex||!freeFrames||!readyFrames){captureError="Insufficient capture memory";captureCleanup();return;}
 for(size_t i=0;i<POOL_SIZE;i++){Frame *frame=pool+i;xQueueSend(freeFrames,&frame,0);}
 if(xTaskCreatePinnedToCore(storeTask,"capture-store",4096,nullptr,1,&captureTask,1)!=pdPASS){captureError="Capture worker unavailable";captureCleanup();return;}
 wifi_promiscuous_filter_t filter{};filter.filter_mask=WIFI_PROMIS_FILTER_MASK_MGMT|WIFI_PROMIS_FILTER_MASK_DATA;
 if(esp_wifi_set_promiscuous_filter(&filter)!=ESP_OK||esp_wifi_set_promiscuous_rx_cb(onFrame)!=ESP_OK||esp_wifi_set_promiscuous(true)!=ESP_OK){captureError="Wi-Fi capture initialization failed";captureCleanup();return;}
 captureReady=true;captureError="";
}
void capturePause(bool paused){if(captureReady)esp_wifi_set_promiscuous(!paused);}
void captureStatus(JsonObject object){
 Stats current;portENTER_CRITICAL(&statsLock);current=stats;portEXIT_CRITICAL(&statsLock);
 object["seen"]=current.seen;object["selected"]=current.selected;object["dropped"]=current.dropped;object["eapol"]=current.eapol;
 object["protected"]=current.protectedFrames;object["logger_tx"]=current.loggerTx;object["logger_rx"]=current.loggerRx;
 if(ringMutex){xSemaphoreTake(ringMutex,portMAX_DELAY);object["stored"]=ringPackets;object["evicted"]=evicted;object["buffer_bytes"]=ringUsed;xSemaphoreGive(ringMutex);}
 object["buffer_limit"]=RING_SIZE;object["logger_rssi"]=current.rssiLogger;object["capture_ready"]=captureReady;object["capture_error"]=captureError;
}
void captureDownload(){
 if(!captureReady){web.send(409,"text/plain","Capture is not configured");return;}
 if(clockValid()&&!clockSynced){timeval now;gettimeofday(&now,nullptr);clockOffset=int64_t(now.tv_sec)*1000000+now.tv_usec-esp_timer_get_time();clockSynced=true;}
 downloadPcap();
}
