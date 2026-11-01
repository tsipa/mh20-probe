#pragma once
#include <WiFi.h>
#include <WebServer.h>
#include <Update.h>
#include <Preferences.h>
#include <esp_system.h>
#include "ServicePolicy.h"

namespace ServiceWeb {
ServicePolicy policy;
WebServer server(80);
bool online = false, uploaded = false, started = false, failed = false;
uint32_t rebootAt = 0;
String token;
String status = "{}";
void (*safeOutputs)() = nullptr;

const char PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="en"><head><title>m&amp;h probe receiver</title>
<style>body{font:17px system-ui;max-width:700px;margin:40px auto;padding:0 20px;background:#18202e;color:#eef2f8}section{background:#253044;padding:22px;border-radius:12px;margin:20px 0}button,input{font:inherit;margin:10px 0}button{padding:10px 18px}pre{white-space:pre-wrap}a{color:#9ed5ff}</style></head><body>
<h1>m&amp;h probe receiver</h1>
<p>Wi-Fi switches off when the receiver finds the probe. Restart the receiver to reconnect.</p>
<section><h2>Receiver</h2><pre id="status">Loading...</pre></section>
<section><h2>Firmware update</h2><p>Switch the probe off before updating. Select the application .bin from the build folder, not a merged image or bootloader.</p>
<form id="update"><input id="image" type="file" accept=".bin" required><br><button>Upload firmware</button></form>
<p id="result">The receiver cannot be used for probing during an update.</p></section>
<button id="restart">Restart receiver</button>
<script>
const token='TOKEN_VALUE';let uploading=false;
async function refresh(){if(uploading)return;try{const r=await fetch('/status',{cache:'no-store'});const s=await r.json();document.getElementById('status').textContent=`State: ${s.state}\nFrequency: ${(s.frequency/1e6).toFixed(6)} MHz\nRSSI: ${s.rssi===null?'unavailable':s.rssi+' dBm'}\nMessages: ${s.messages}\nContacts: ${s.touches}\nLink losses: ${s.losses}`;}catch(e){document.getElementById('status').textContent='Disconnected. Wi-Fi switches off after the probe is detected.';}}
setInterval(refresh,1000);refresh();
document.getElementById('update').onsubmit=async e=>{e.preventDefault();if(uploading)return;uploading=true;const result=document.getElementById('result');result.textContent='Uploading. Keep the receiver powered.';const data=new FormData();data.append('firmware',document.getElementById('image').files[0]);try{const r=await fetch('/update',{method:'POST',headers:{'X-Update-Token':token},body:data});result.textContent=await r.text();}catch(e){result.textContent='Connection lost. Reconnect and check the receiver before retrying.';}finally{uploading=false;}};
document.getElementById('restart').onclick=async()=>{if(uploading)return;try{await fetch('/restart',{method:'POST',headers:{'X-Update-Token':token}});}catch(e){}};
</script></body></html>)HTML";

bool authorized() { return server.header("X-Update-Token") == token; }
void begin(void (*safe)()) {
  safeOutputs = safe;
  Preferences prefs;
  prefs.begin("probe-service", false);
  String password = prefs.getString("password", "");
  if (password.length() < 12) {
    char generated[17];
    snprintf(generated, sizeof(generated), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
    password = generated;
    prefs.putString("password", password);
  }
  prefs.end();
  char secret[17];
  snprintf(secret, sizeof(secret), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
  token = secret;
  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP("MH-Probe-Service", password.c_str(), 1, false, 1)) {
    WiFi.mode(WIFI_OFF);
    Serial.println("Service Wi-Fi failed to start.");
    return;
  }
  const char *headers[] = {"X-Update-Token"};
  server.collectHeaders(headers, 1);
  server.on("/", HTTP_GET, []() {
    String page = FPSTR(PAGE);
    page.replace("TOKEN_VALUE", token);
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/html", page);
  });
  server.on("/status", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", status);
  });
  server.on("/restart", HTTP_POST, []() {
    if (!authorized()) { server.send(403, "text/plain", "Reload the page and retry."); return; }
    policy.beginUpdate(); safeOutputs();
    server.send(200, "text/plain", "Restarting receiver.");
    rebootAt = millis() + 750;
  });
  server.on("/update", HTTP_POST, []() {
    if (!authorized()) { server.send(403, "text/plain", "Reload the page and retry."); return; }
    const bool ok = started && uploaded && !failed && !Update.hasError() && Update.end(true);
    server.sendHeader("Connection", "close");
    server.send(ok ? 200 : 400, "text/plain", ok ? "Update complete. Restarting receiver." : "Update failed. Probing remains disabled. Retry or restart the receiver.");
    if (ok) rebootAt = millis() + 750;
    else if (Update.isRunning()) Update.abort();
    started = uploaded = false;
  }, []() {
    if (!authorized()) return;
    HTTPUpload &upload = server.upload();
    if (upload.status == UPLOAD_FILE_START) {
      // Reject multiple files in one request, including a previous failed file.
      if (started) { failed = true; if (Update.isRunning()) Update.abort(); return; }
      started = true; uploaded = false; failed = false;
      if (!policy.beginUpdate()) { failed = true; return; }
      safeOutputs();
      if (!upload.filename.endsWith(".bin") || !Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH)) failed = true;
    } else if (upload.status == UPLOAD_FILE_WRITE) {
      if (started && !failed && Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
        failed = true; Update.abort();
      }
    } else if (upload.status == UPLOAD_FILE_END) {
      if (started && !failed) {
        uploaded = upload.totalSize > 0;
        failed = !uploaded;
      }
    } else if (upload.status == UPLOAD_FILE_ABORTED) {
      failed = true; uploaded = false; started = false;
      if (Update.isRunning()) Update.abort();
    }
  });
  server.begin(); online = true;
  Serial.printf("Service Wi-Fi: MH-Probe-Service  password: %s  URL: http://%s/\n", password.c_str(), WiFi.softAPIP().toString().c_str());
}
void observeProbe() {
  policy.observeProbe();
  if (online && !policy.networkAllowed()) {
    server.stop(); WiFi.softAPdisconnect(true); WiFi.mode(WIFI_OFF); online = false;
    Serial.println("Probe found. Service Wi-Fi is off until reboot.");
  }
}
void poll(uint32_t frequency, bool rssiValid, int rssiHalfDbm, uint32_t messages, uint32_t touches, uint32_t losses) {
  if (!online) return;
  const String rssi = rssiValid ? String(rssiHalfDbm / 2.0f, 1) : String("null");
  status = String("{\"state\":\"") + (policy.maintenance ? "maintenance" : "searching") +
    "\",\"frequency\":" + String(frequency) + ",\"rssi\":" + rssi +
    ",\"messages\":" + String(messages) + ",\"touches\":" + String(touches) + ",\"losses\":" + String(losses) + "}";
  server.handleClient();
  if (rebootAt && int32_t(millis() - rebootAt) >= 0) ESP.restart();
}
}
