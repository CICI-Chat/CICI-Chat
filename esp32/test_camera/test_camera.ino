/*
 * ESP32-S3-CAM 纯摄像头测试
 * 低功耗设置，连你家 WiFi，浏览器看画面
 */
#include "esp_camera.h"
#include <WiFi.h>

const char* ssid = "HX2.4G";
const char* pass = "hx131659";

// ESP32-S3-CAM (GOOUUU) 引脚
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  15
#define SIOD_GPIO_NUM  4
#define SIOC_GPIO_NUM  5
#define Y9_GPIO_NUM    16
#define Y8_GPIO_NUM    17
#define Y7_GPIO_NUM    18
#define Y6_GPIO_NUM    12
#define Y5_GPIO_NUM    10
#define Y4_GPIO_NUM    8
#define Y3_GPIO_NUM    9
#define Y2_GPIO_NUM    11
#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM  7
#define PCLK_GPIO_NUM  13

WiFiServer server(80);
bool cam_ok = false;
esp_err_t cam_err = ESP_OK;

void setup() {
  Serial.begin(115200);

  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;   // 降频到 10MHz，减少发热
  config.frame_size = FRAMESIZE_QVGA;  // 320x240 低分辨率
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  config.jpeg_quality = 15;
  config.fb_count = 1;

  Serial.printf("PSRAM: %s\n", psramFound() ? "有" : "无");

  esp_err_t err = esp_camera_init(&config);
  cam_ok = (err == ESP_OK);
  Serial.printf("摄像头: %s (0x%x)\n", cam_ok ? "OK" : "FAIL", err);

  // 把错误码也存起来，网页上能看到
  cam_err = err;

  WiFi.mode(WIFI_STA);
  WiFi.config(IPAddress(192,168,1,222), IPAddress(192,168,1,1), IPAddress(255,255,255,0));
  WiFi.begin(ssid, pass);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  server.begin();
}

void loop() {
  WiFiClient c = server.available();
  if (!c) return;

  // 读取请求首行，判断访问的是首页还是视频流
  String req = c.readStringUntil('\n');
  while (c.available()) c.read();  // 清空剩余请求头

  if (!cam_ok) {
    c.println("HTTP/1.1 200 OK");
    c.println("Content-Type: text/plain; charset=utf-8\n");
    c.printf("Camera FAIL - 错误码: 0x%x\n", cam_err);
    c.stop();
    return;
  }

  // 访问 /stream 才推流，其他返回带 <img> 的网页
  if (req.indexOf("/stream") < 0) {
    c.println("HTTP/1.1 200 OK");
    c.println("Content-Type: text/html; charset=utf-8\n");
    c.println("<html><body style='margin:0;background:#000;text-align:center'>");
    c.println("<img src='/stream' style='width:100%;max-width:640px'>");
    c.println("</body></html>");
    c.stop();
    return;
  }

  // 推送 MJPEG 视频流
  c.println("HTTP/1.1 200 OK");
  c.println("Content-Type: multipart/x-mixed-replace; boundary=frame\n");
  while (c.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) continue;
    c.printf("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    c.write(fb->buf, fb->len);
    c.print("\r\n");
    esp_camera_fb_return(fb);
    delay(100);   // 每秒约 10 帧
  }
}
