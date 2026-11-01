#pragma once
#include <WiFi.h>
#include <WebServer.h>
#include <Update.h>
#include <Preferences.h>
#include <esp_system.h>
#include "ServicePolicy.h"
#include "WifiConfig.h"

namespace ServiceWeb {
ServicePolicy policy;
WebServer server(80);
bool online = false, uploaded = false, started = false, failed = false;
uint32_t rebootAt = 0;
String token, servicePassword;
WifiConfig::Config activeConfig, pendingConfig;
WifiConfig::LineReader serialLine;
bool apActive = false, stationReported = false;
uint32_t stationAt = 0;

String status = "{}";
void (*safeOutputs)() = nullptr;

const char PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="en"><head><title>m&amp;h probe receiver</title>
<style>body{font:17px system-ui;max-width:700px;margin:40px auto;padding:0 20px;background:#18202e;color:#eef2f8}section{background:#253044;padding:22px;border-radius:12px;margin:20px 0}button,input{font:inherit;margin:10px 0}button{padding:10px 18px}pre{white-space:pre-wrap}a{color:#9ed5ff}</style></head><body>
<h1>m&amp;h probe receiver</h1>
<p>Wi-Fi switches off when the receiver finds the probe. Restart the receiver to reconnect.</p>
<section><h2>Receiver</h2><pre id="status">Loading...</pre></section>
<section><h2>Wi-Fi settings</h2><pre id="network">Loading...</pre>
<form id="wifi"><label>Mode <select id="mode"><option value="ap">Access point</option><option value="sta">Connect to router</option><option value="apsta">Router + access point</option></select></label><br>
<label>Router SSID <input id="ssid" maxlength="32" autocomplete="off"></label><br>
<label>Router password <input id="password" type="password" maxlength="64" autocomplete="new-password"></label><br>
<label><input id="replace" type="checkbox"> Replace saved password (leave blank for an open network)</label><br>
<button>Save settings</button></form><p id="wifi-result">Changes take effect after restart. If the router is unavailable, the service access point starts after 15 seconds.</p></section>
<section><h2>Firmware update</h2><p>Switch the probe off before updating. Select the application .bin from the build folder, not a merged image or bootloader.</p>
<form id="update"><input id="image" type="file" accept=".bin" required><br><button>Upload firmware</button></form>
<p id="result">The receiver cannot be used for probing during an update.</p></section>
<button id="restart">Restart receiver</button>
<script>
const token='TOKEN_VALUE';let uploading=false;
async function refresh(){if(uploading)return;try{const r=await fetch('/status',{cache:'no-store'});const s=await r.json();document.getElementById('status').textContent=`State: ${s.state}\nFrequency: ${(s.frequency/1e6).toFixed(6)} MHz\nRSSI: ${s.rssi===null?'unavailable':s.rssi+' dBm'}\nMessages: ${s.messages}\nContacts: ${s.touches}\nLink losses: ${s.losses}`;}catch(e){document.getElementById('status').textContent='Disconnected. Wi-Fi switches off after the probe is detected.';}}
setInterval(refresh,1000);refresh();
async function loadWifi(){try{const r=await fetch('/wifi',{cache:'no-store'});if(!r.ok)throw Error('Cannot read Wi-Fi settings');const s=await r.json();document.getElementById('mode').value=s.mode;document.getElementById('ssid').value=s.ssid;document.getElementById('password').placeholder=s.hasPassword?'Saved password (unchanged if left alone)':'No saved password';document.getElementById('network').textContent=`Client: ${s.connected?'connected at '+s.ip:'not connected'}\nAccess point: ${s.ap?'192.168.4.1':'off'}`;}catch(e){document.getElementById('network').textContent=e.message;}}
loadWifi();
document.getElementById('password').oninput=()=>{document.getElementById('replace').checked=true;};
document.getElementById('wifi').onsubmit=async e=>{e.preventDefault();if(uploading)return;const result=document.getElementById('wifi-result');const body=new URLSearchParams({mode:document.getElementById('mode').value,ssid:document.getElementById('ssid').value,password:document.getElementById('password').value,replace:document.getElementById('replace').checked?'1':'0'});try{const r=await fetch('/wifi',{method:'POST',headers:{'X-Update-Token':token},body});result.textContent=await r.text();if(r.ok){document.getElementById('password').value='';document.getElementById('replace').checked=false;loadWifi();}}catch(e){result.textContent='Connection lost. Reconnect to check the saved settings.';}};
document.getElementById('update').onsubmit=async e=>{e.preventDefault();if(uploading)return;uploading=true;const result=document.getElementById('result');result.textContent='Uploading. Keep the receiver powered.';const data=new FormData();data.append('firmware',document.getElementById('image').files[0]);try{const r=await fetch('/update',{method:'POST',headers:{'X-Update-Token':token},body:data});result.textContent=await r.text();}catch(e){result.textContent='Connection lost. Reconnect and check the receiver before retrying.';}finally{uploading=false;}};
document.getElementById('restart').onclick=async()=>{if(uploading)return;try{await fetch('/restart',{method:'POST',headers:{'X-Update-Token':token}});}catch(e){}};
</script></body></html>)HTML";

bool authenticated() { return server.authenticate("admin", servicePassword.c_str()); }
bool requireLogin() {
  if (authenticated()) return true;
  server.requestAuthentication(); return false;
}
bool authorized() { return authenticated() && server.header("X-Update-Token") == token; }
String jsonText(const char *text) {
  String value = "\"";
  while (*text) { if (*text == '"' || *text == '\\') value += '\\'; value += *text++; }
  return value + "\"";
}
void configurationMode() {
  // Configuration writes may arrive over UART after the probe has been seen.
  // Inhibit outputs before flash access, but never clear the Wi-Fi shutdown latch.
  policy.maintenance = true;
  safeOutputs();
}
bool saveConfig(const WifiConfig::Config &config) {
  if (!WifiConfig::valid(config)) return false;
  configurationMode();
  Preferences prefs;
  if (!prefs.begin("probe-service", false)) return false;
  const bool ok = prefs.putBytes("network", &config, sizeof(config)) == sizeof(config);
  prefs.end();
  if (ok) pendingConfig = config;
  return ok;
}
bool resetConfig() {
  return saveConfig(WifiConfig::Config());
}
void startAP() {
  if (!policy.networkAllowed() || apActive) return;
  WiFi.mode(activeConfig.mode == WifiConfig::AP ? WIFI_AP : WIFI_AP_STA);
  apActive = WiFi.softAP("MH-Probe-Service", servicePassword.c_str(), 1, false, 1);
  Serial.println(apActive ? "Service access point: http://192.168.4.1/" : "Service access point failed to start.");
}
void pollNetwork() {
  if (!online || !policy.networkAllowed() || activeConfig.mode == WifiConfig::AP) return;
  if (WiFi.status() == WL_CONNECTED) {
    if (!stationReported) Serial.printf("Service client URL: http://%s/\n", WiFi.localIP().toString().c_str());
    stationReported = true;
    stationAt = millis();
  } else {
    stationReported = false;
    if (policy.recoveryAllowed(apActive, millis(), stationAt)) startAP();
  }
}
void pollSerial() {
  for (unsigned count = 0; count < 32 && Serial.available(); ++count) {
    const int complete = serialLine.feed(char(Serial.read()));
    if (!complete) continue;
    if (complete < 0) { Serial.println("Wi-Fi command rejected: line too long or invalid control character."); continue; }
    if (!serialLine.line[0]) continue;
    const auto command = WifiConfig::command(pendingConfig, serialLine.line);
    // Clear credentials from the input buffer as soon as parsing is done.
    memset(serialLine.line, 0, sizeof(serialLine.line));
    if (Update.isRunning() && (command == WifiConfig::Save || command == WifiConfig::Reset || command == WifiConfig::Reboot)) {
      Serial.println("Firmware upload in progress. Retry after it finishes."); continue;
    }
    switch (command) {
      case WifiConfig::Changed: Serial.println("Wi-Fi setting staged. Use wifi save, then wifi reboot."); break;
      case WifiConfig::Help:
        Serial.println("wifi status | wifi mode ap|sta|apsta | wifi ssid <name> | wifi password <value>");
        Serial.println("wifi password (clear password) | wifi save | wifi reset | wifi access | wifi reboot"); break;
      case WifiConfig::Status:
        Serial.printf("Staged mode: %s; SSID: %s; router password: %s; Wi-Fi: %s\n", WifiConfig::modeName(pendingConfig.mode), pendingConfig.ssid, pendingConfig.password[0] ? "set" : "empty", policy.networkAllowed() ? "enabled" : "off until reboot");
        if (online && WiFi.status() == WL_CONNECTED) Serial.printf("Client URL: http://%s/\n", WiFi.localIP().toString().c_str());
        break;
      case WifiConfig::Access:
        Serial.printf("Service login: admin  password: %s\n", servicePassword.c_str()); break;
      case WifiConfig::Save:
        if (!WifiConfig::valid(pendingConfig)) Serial.println("Invalid settings: SSID is required for client mode; password must be empty, 8-63 bytes or a 64-digit hex key.");
        else Serial.println(saveConfig(pendingConfig) ? "Wi-Fi settings saved. Probing is disabled until restart. Use wifi reboot." : "Could not save Wi-Fi settings. Check storage and retry.");
        break;
      case WifiConfig::Reset:
        Serial.println(resetConfig() ? "Access-point defaults saved. Use wifi reboot." : "Could not reset Wi-Fi settings."); break;
      case WifiConfig::Reboot:
        configurationMode(); rebootAt = millis() + 750; Serial.println("Restarting receiver."); break;
      default: Serial.println("Invalid command. Use wifi help."); break;
    }
  }
}
void begin(void (*safe)()) {
  safeOutputs = safe;
  Preferences prefs;
  prefs.begin("probe-service", false);
  String password = prefs.getString("password", "");
  WifiConfig::Config stored;
  if (prefs.getBytesLength("network") == sizeof(stored) &&
      prefs.getBytes("network", &stored, sizeof(stored)) == sizeof(stored) && WifiConfig::valid(stored)) activeConfig = stored;
  pendingConfig = activeConfig;
  if (password.length() < 12) {
    char generated[17];
    snprintf(generated, sizeof(generated), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
    password = generated;
    prefs.putString("password", password);
  }
  prefs.end();
  servicePassword = password;
  char secret[17];
  snprintf(secret, sizeof(secret), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
  token = secret;
  WiFi.persistent(false);
  if (activeConfig.mode == WifiConfig::AP) startAP();
  else {
    WiFi.mode(activeConfig.mode == WifiConfig::AP_STA ? WIFI_AP_STA : WIFI_STA);
    WiFi.setAutoReconnect(true);
    if (activeConfig.mode == WifiConfig::AP_STA) startAP();
    WiFi.begin(activeConfig.ssid, activeConfig.password);
    stationAt = millis();
    Serial.printf("Connecting service Wi-Fi to SSID: %s\n", activeConfig.ssid);
  }
  const char *headers[] = {"X-Update-Token"};
  server.collectHeaders(headers, 1);
  server.on("/", HTTP_GET, []() {
    if (!requireLogin()) return;
    String page = FPSTR(PAGE);
    page.replace("TOKEN_VALUE", token);
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/html", page);
  });
  server.on("/status", HTTP_GET, []() {
    if (!requireLogin()) return;
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", status);
  });
  server.on("/wifi", HTTP_GET, []() {
    if (!requireLogin()) return;
    server.sendHeader("Cache-Control", "no-store");
    const String body = String("{\"mode\":\"") + WifiConfig::modeName(pendingConfig.mode) + "\",\"ssid\":" + jsonText(pendingConfig.ssid) +
      ",\"hasPassword\":" + (pendingConfig.password[0] ? "true" : "false") + ",\"connected\":" + (WiFi.status() == WL_CONNECTED ? "true" : "false") +
      ",\"ip\":\"" + WiFi.localIP().toString() + "\",\"ap\":" + (apActive ? "true" : "false") + "}";
    server.send(200, "application/json", body);
  });
  server.on("/wifi", HTTP_POST, []() {
    if (!authorized()) { server.send(403, "text/plain", "Reload the page and retry."); return; }
    if (Update.isRunning() || rebootAt) { server.send(409, "text/plain", "An update or restart is in progress."); return; }
    WifiConfig::Config next = pendingConfig;
    if (!server.hasArg("mode") || !server.hasArg("ssid") || !server.hasArg("replace") ||
        !WifiConfig::parseMode(server.arg("mode").c_str(), next.mode) ||
        !WifiConfig::text(next.ssid, sizeof(next.ssid), server.arg("ssid").c_str()) ||
        (server.arg("replace") != "0" && server.arg("replace") != "1") ||
        (server.arg("replace") == "1" && (!server.hasArg("password") || !WifiConfig::text(next.password, sizeof(next.password), server.arg("password").c_str()))) ||
        !WifiConfig::valid(next)) {
      server.send(400, "text/plain", "Invalid settings. Client mode needs an SSID (up to 32 bytes). Use an empty password, 8-63 bytes, or a 64-digit hex key."); return;
    }
    if (!saveConfig(next)) { server.send(500, "text/plain", "Could not save settings. Check storage and retry."); return; }
    server.send(200, "text/plain", "Settings saved. Probing is disabled until restart. Use Restart receiver to apply them.");
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
  Serial.printf("Service login: admin  password: %s\n", servicePassword.c_str());
  Serial.println("UART Wi-Fi commands: wifi help");
}
const char *displayStatus() {
  return WifiConfig::displayStatus(online, apActive, activeConfig.mode != WifiConfig::AP, stationReported);
}
void observeProbe() {
  policy.observeProbe();
  if (online && !policy.networkAllowed()) {
    online = false;
    server.stop(); WiFi.setAutoReconnect(false); WiFi.disconnect(false, false);
    WiFi.softAPdisconnect(false); WiFi.mode(WIFI_OFF); apActive = false;
    Serial.println("Probe found. Service Wi-Fi is off until reboot.");
  }
}
void poll(uint32_t frequency, bool rssiValid, int rssiHalfDbm, uint32_t messages, uint32_t touches, uint32_t losses) {
  pollSerial();
  if (rebootAt && int32_t(millis() - rebootAt) >= 0) ESP.restart();
  if (!online) return;
  pollNetwork();
  const String rssi = rssiValid ? String(rssiHalfDbm / 2.0f, 1) : String("null");
  status = String("{\"state\":\"") + (policy.maintenance ? "maintenance" : "searching") +
    "\",\"frequency\":" + String(frequency) + ",\"rssi\":" + rssi +
    ",\"messages\":" + String(messages) + ",\"touches\":" + String(touches) + ",\"losses\":" + String(losses) + "}";
  server.handleClient();
  if (rebootAt && int32_t(millis() - rebootAt) >= 0) ESP.restart();
}
}
