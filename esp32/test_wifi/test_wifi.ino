#include <WiFi.h>

const char* ssid = "HX2.4G";
const char* pass = "hx131659";

WiFiServer server(80);
IPAddress fixed_ip(192, 168, 1, 222);

void setup() {
  WiFi.mode(WIFI_STA);
  WiFi.config(fixed_ip, IPAddress(192,168,1,1), IPAddress(255,255,255,0));
  WiFi.begin(ssid, pass);
  for (int i = 0; i < 30; i++) {
    delay(500);
    if (WiFi.status() == WL_CONNECTED) break;
  }
  server.begin();
}

void loop() {
  WiFiClient c = server.available();
  if (!c) return;
  c.println("HTTP/1.1 200 OK");
  c.println("Content-Type: text/plain\n");
  c.println("ESP32 OK");
  c.stop();
}
