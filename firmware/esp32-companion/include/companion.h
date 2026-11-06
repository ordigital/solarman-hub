#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include "bounded_web_server.h"
extern BoundedWebServer web;
extern String mode,ssid,wifiPassword,apBssid,loggerMac,upstreamHost;
extern bool pinAP,upstreamEnabled;
extern uint16_t upstreamPort,upstreamTimeout;
extern uint32_t allowedSerial;
extern int32_t timezoneMinutes;
extern bool clockValid();
void captureBegin();
void capturePause(bool paused);
void captureStatus(JsonObject object);
void captureDownload();
void receiverBegin();
void receiverLoop();
void receiverPause();
void receiverResume();
void receiverStatus(JsonObject object);
String profileDefinition(const String &type);
bool buildBundle(JsonDocument &document,const String &type,bool includeSample);
