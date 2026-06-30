/*
 * 无人机稳定器 - ESP32-S3
 *
 * 功能：
 * 1. 读取 VL53L5X TOF → 计算离地高度
 * 2. 读取 PMW3901 光流 → 计算水平位移
 * 3. 通过 MSP 协议发送给飞控 → 自动悬停/定高
 *
 * 接线：
 *   VL53L5X: SDA→21, SCL→22, VIN→3.3V, LPN→3.3V
 *   PMW3901: CLK→18, MOSI→23, MISO→19, CS→5, VCC→3.3V, VRE→3.3V, RST→3.3V
 *   飞控: TX→1(RX), RX→2(TX), GND→GND
 */

#include <Wire.h>
#include <SPI.h>

// ====== 引脚定义 ======
#define PIN_LED        13    // ESP32-S3 内置 LED
#define PIN_CS         5     // PMW3901 片选
#define PIN_CLK        18    // PMW3901 时钟
#define PIN_MOSI       23    // PMW3901 数据输入
#define PIN_MISO       19    // PMW3901 数据输出

// ====== 飞控 UART ======
// 用 UART1（GPIO1=TX, GPIO2=RX）接飞控
#define FC_BAUD        115200

// ====== MSP 协议常量 ======
#define MSP_SET_RAW_RC 200

// ====== 全局变量 ======
int16_t target_throttle = 1500;  // 目标油门（中位 1500）
int16_t target_roll     = 1500;  // 目标横滚
int16_t target_pitch    = 1500;  // 目标俯仰
int16_t target_yaw      = 1500;  // 目标偏航

float current_altitude  = 0.0;   // 当前高度（米）
float target_altitude   = 1.0;   // 目标高度（1 米悬停）
int16_t flow_x          = 0;     // 光流 X 位移
int16_t flow_y          = 0;     // 光流 Y 位移

unsigned long last_time = 0;

// ====== PMW3901 操作 ======
void PMW3901_write(uint8_t reg, uint8_t val) {
  digitalWrite(PIN_CS, LOW);
  SPI.transfer(reg & 0x7F);  // 写操作
  SPI.transfer(val);
  digitalWrite(PIN_CS, HIGH);
}

uint8_t PMW3901_read(uint8_t reg) {
  digitalWrite(PIN_CS, LOW);
  SPI.transfer(reg | 0x80);  // 读操作
  uint8_t val = SPI.transfer(0x00);
  digitalWrite(PIN_CS, HIGH);
  return val;
}

bool PMW3901_begin() {
  pinMode(PIN_CS, OUTPUT);
  digitalWrite(PIN_CS, HIGH);

  SPI.begin(PIN_CLK, PIN_MISO, PIN_MOSI, PIN_CS);
  SPI.setDataMode(SPI_MODE3);
  SPI.setFrequency(2000000);

  delay(10);

  // 读取芯片 ID（PMW3901 的 Product_ID 应为 0x42）
  uint8_t pid = PMW3901_read(0x00);
  if (pid != 0x42) {
    Serial.println("PMW3901 未检测到！");
    return false;
  }

  // 初始化序列
  PMW3901_write(0x32, 0x00);
  PMW3901_write(0x03, 0x00);
  PMW3901_write(0x11, 0x02);
  delay(5);

  Serial.println("PMW3901 初始化成功");
  return true;
}

void PMW3901_readMotion(int16_t *dx, int16_t *dy) {
  // 读取运动数据
  uint8_t motion = PMW3901_read(0x02);

  if (motion & 0x80) {  // 有新的运动数据
    *dx = (int16_t)((int8_t)PMW3901_read(0x04)) +
          ((int16_t)((int8_t)PMW3901_read(0x05)) << 8);
    *dy = (int16_t)((int8_t)PMW3901_read(0x06)) +
          ((int16_t)((int8_t)PMW3901_read(0x07)) << 8);
  } else {
    *dx = 0;
    *dy = 0;
  }
}

// ====== VL53L5X 操作（简化 I2C） ======
bool VL53L5X_begin() {
  Wire.begin(21, 22, 400000);  // SDA=21, SCL=22, 400kHz
  delay(100);

  // 检查设备是否存在
  Wire.beginTransmission(0x29);  // VL53L5X 默认地址
  if (Wire.endTransmission() != 0) {
    Serial.println("VL53L5X 未检测到！");
    return false;
  }

  Serial.println("VL53L5X 已检测到");
  return true;
}

float VL53L5X_readAltitude() {
  // VL53L5X 是 8x8 多区 TOF
  // 这里用简化读取，实际需要完整 I2C 通信库
  // 返回模拟值用于测试
  return 1.0;  // 占位，后续补充完整驱动
}

// ====== MSP 协议发送 ======
void msp_send_raw_rc(int16_t roll, int16_t pitch, int16_t yaw, int16_t throttle) {
  uint8_t data[16];

  // 8 个通道，每个 2 字节（小端）
  int16_t channels[8] = {roll, pitch, yaw, throttle, 1500, 1500, 1500, 1500};
  for (int i = 0; i < 8; i++) {
    data[i*2]     = channels[i] & 0xFF;
    data[i*2 + 1] = (channels[i] >> 8) & 0xFF;
  }

  // 组装 MSP 帧: $M< length cmd data checksum
  uint8_t buf[21];
  buf[0] = '$';
  buf[1] = 'M';
  buf[2] = '<';
  buf[3] = 16;           // 长度
  buf[4] = MSP_SET_RAW_RC;  // 命令
  memcpy(&buf[5], data, 16);

  // 校验和 = length ^ cmd ^ data[0] ^ data[1] ^ ...
  uint8_t cksum = 16 ^ MSP_SET_RAW_RC;
  for (int i = 0; i < 16; i++) cksum ^= data[i];
  buf[21] = cksum;

  Serial1.write(buf, 22);
}

// ====== 稳定控制算法 ======
void stabilize() {
  // ===== 定高控制（基于 TOF）=====
  float error = current_altitude - target_altitude;
  // 简单 P 控制：误差 × 系数
  int16_t throttle_adjust = (int16_t)(error * 50);
  target_throttle = 1500 - throttle_adjust;
  target_throttle = constrain(target_throttle, 1350, 1600);

  // ===== 水平控制（基于光流）=====
  // 如果检测到漂移，反向修正
  int16_t roll_adjust  = constrain(flow_x / -10, -100, 100);
  int16_t pitch_adjust = constrain(flow_y / -10, -100, 100);

  target_roll  = 1500 + roll_adjust;
  target_pitch = 1500 + pitch_adjust;
}

// ====== 初始化 ======
void setup() {
  Serial.begin(115200);     // USB 调试
  Serial1.begin(FC_BAUD);   // UART1 → 飞控

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  Serial.println("无人机稳定器启动...");

  // 初始化传感器
  VL53L5X_begin();
  PMW3901_begin();

  // LED 亮表示初始化完成
  digitalWrite(PIN_LED, HIGH);

  last_time = millis();
  Serial.println("初始化完成，等待起飞...");
}

// ====== 主循环 ======
void loop() {
  unsigned long now = millis();

  // 每 20ms 执行一次（50Hz 控制频率）
  if (now - last_time < 20) return;
  last_time = now;

  // 1. 读 TOF 高度
  current_altitude = VL53L5X_readAltitude();

  // 2. 读光流位移
  PMW3901_readMotion(&flow_x, &flow_y);

  // 3. 稳定控制
  stabilize();

  // 4. 通过 MSP 发给飞控
  msp_send_raw_rc(target_roll, target_pitch, target_yaw, target_throttle);

  // 5. 调试输出（通过 USB 串口查看）
  static int count = 0;
  if (++count % 50 == 0) {  // 每秒打印一次
    Serial.print("高度:");
    Serial.print(current_altitude);
    Serial.print("m 光流:");
    Serial.print(flow_x);
    Serial.print(",");
    Serial.print(flow_y);
    Serial.print(" 油门:");
    Serial.print(target_throttle);
    Serial.print(" 横滚:");
    Serial.println(target_roll);
  }
}
