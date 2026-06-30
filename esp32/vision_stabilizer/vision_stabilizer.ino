/*
 * 无人机视觉稳定器 - ESP32-S3 二合一
 *
 * 核 0：摄像头 + WiFi 图传 → 给电脑 PicMind 识别
 * 核 1：TOF + 光流 + MSP  → 断网也能自动悬停
 *
 * 接线表：
 *
 *  摄像头（ESP32S3-EYE 标准引脚，板载已焊好）
 *  无需额外接线
 *
 *  VL53L5X TOF（I2C）
 *   引脚   → ESP32
 *   VIN   → 3.3V
 *   LPN   → 3.3V（拉高）
 *   SDA   → GPIO21
 *   SCL   → GPIO22
 *   GND   → GND
 *
 *  PMW3901 光流（SPI）
 *   引脚   → ESP32
 *   VCC   → 3.3V
 *   VRE   → 3.3V（拉高）
 *   RST   → 3.3V（拉高）
 *   CLK   → GPIO36
 *   MOSI  → GPIO37
 *   MISO  → GPIO35
 *   CS    → GPIO38
 *   GND   → GND
 *
 *  飞控（UART）
 *   ESP32 TX(GPIO1) → 飞控 RX
 *   ESP32 RX(GPIO2) → 飞控 TX
 *   GND → 飞控 GND
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <Wire.h>
#include <SPI.h>

// ======================== 用户配置 ========================
const char* ssid     = "你的WiFi名";
const char* password = "你的WiFi密码";

#define MSP_SET_RAW_RC 200

// ======================== 引脚定义 ========================
// 摄像头：ESP32S3-EYE 标准
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     15
#define SIOD_GPIO_NUM     4
#define SIOC_GPIO_NUM     5
#define Y9_GPIO_NUM       16
#define Y8_GPIO_NUM       17
#define Y7_GPIO_NUM       3
#define Y6_GPIO_NUM       12
#define Y5_GPIO_NUM       18
#define Y4_GPIO_NUM       8
#define Y3_GPIO_NUM       10
#define Y2_GPIO_NUM       11
#define VSYNC_GPIO_NUM    6
#define HREF_GPIO_NUM     7
#define PCLK_GPIO_NUM     13

// TOF：I2C
#define PIN_SDA    21
#define PIN_SCL    22

// 光流：SPI（用不冲突的引脚）
#define PIN_CLK    36
#define PIN_MOSI   37
#define PIN_MISO   35
#define PIN_CS     38

// ======================== 全局 ========================
float altitude = 1.0;
int16_t flow_x = 0, flow_y = 0;
int16_t throttle = 1500, roll = 1500, pitch = 1500, yaw = 1500;

// ======================== 摄像头 ========================
bool init_camera() {
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
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_VGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  return esp_camera_init(&config) == ESP_OK;
}

// ======================== WiFi 图传 ========================
WiFiServer cam_server(81);

void init_wifi() {
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  cam_server.begin();
}

void stream_camera() {
  WiFiClient c = cam_server.available();
  if (!c) return;
  c.println("HTTP/1.1 200 OK");
  c.println("Content-Type: multipart/x-mixed-replace; boundary=frame\n");
  while (c.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) continue;
    c.printf("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    c.write(fb->buf, fb->len);
    c.print("\r\n");
    esp_camera_fb_return(fb);
  }
}

// ======================== PMW3901 光流 ========================
bool init_flow() {
  pinMode(PIN_CS, OUTPUT);
  digitalWrite(PIN_CS, HIGH);
  SPI.begin(PIN_CLK, PIN_MISO, PIN_MOSI, PIN_CS);
  SPI.setDataMode(SPI_MODE3);
  SPI.setFrequency(2000000);
  delay(10);

  digitalWrite(PIN_CS, LOW);
  SPI.transfer(0x80);
  uint8_t pid = SPI.transfer(0);
  digitalWrite(PIN_CS, HIGH);

  if (pid != 0x42) return false;

  // 初始化
  digitalWrite(PIN_CS, LOW);
  SPI.transfer(0x32 & 0x7F); SPI.transfer(0);
  SPI.transfer(0x03 & 0x7F); SPI.transfer(0);
  SPI.transfer(0x11 & 0x7F); SPI.transfer(2);
  digitalWrite(PIN_CS, HIGH);
  return true;
}

void read_flow() {
  digitalWrite(PIN_CS, LOW);
  SPI.transfer(0x82);
  uint8_t mot = SPI.transfer(0);
  if (mot & 0x80) {
    flow_x = (int8_t)SPI.transfer(0) + ((int8_t)SPI.transfer(0) << 8);
    flow_y = (int8_t)SPI.transfer(0) + ((int8_t)SPI.transfer(0) << 8);
  }
  digitalWrite(PIN_CS, HIGH);
}

// ======================== VL53L5X TOF ========================
bool init_tof() {
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  delay(100);
  Wire.beginTransmission(0x29);
  return Wire.endTransmission() == 0;
}

// ======================== MSP 飞控 ========================
void msp_send() {
  uint8_t d[16];
  int16_t ch[8] = {roll, pitch, yaw, throttle, 1500, 1500, 1500, 1500};
  for (int i = 0; i < 8; i++) { d[i*2]=ch[i]&0xFF; d[i*2+1]=(ch[i]>>8)&0xFF; }

  uint8_t buf[22];
  buf[0]='$'; buf[1]='M'; buf[2]='<'; buf[3]=16; buf[4]=MSP_SET_RAW_RC;
  memcpy(&buf[5], d, 16);
  uint8_t cs = 16 ^ MSP_SET_RAW_RC;
  for (int i = 0; i < 16; i++) cs ^= d[i];
  buf[21] = cs;
  Serial1.write(buf, 22);
}

// ======================== 稳定任务（核 1） ========================
void stabilizer(void*) {
  Serial1.begin(115200);
  init_flow();
  init_tof();

  while (true) {
    read_flow();
    float err = altitude - 1.0;  // 目标 1 米悬停
    throttle = constrain(1500 - err * 50, 1350, 1600);
    roll  = constrain(1500 + flow_x / -10, 1400, 1600);
    pitch = constrain(1500 + flow_y / -10, 1400, 1600);
    msp_send();
    delay(20);
  }
}

// ======================== 启动 ========================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n=== 无人机视觉稳定器 ===");

  if (init_camera()) Serial.println("摄像头 OK");
  else Serial.println("摄像头 FAIL");

  init_wifi();
  Serial.print("IP: http://");
  Serial.println(WiFi.localIP());

  xTaskCreatePinnedToCore(stabilizer, "稳定器", 10000, NULL, 1, NULL, 1);

  Serial.println("系统就绪");
}

void loop() {
  stream_camera();
  delay(10);
}
