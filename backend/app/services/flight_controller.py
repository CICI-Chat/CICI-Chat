"""Betaflight 飞控桥接：把视觉输出转成 MSP 指令通过串口发给飞控。"""

import logging
from typing import Any

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False
    serial = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

MSP_SET_RAW_RC = 200


class BetaflightBridge:
    """通过 MSP 协议控制 Betaflight 飞控。

    用法:
        bridge = BetaflightBridge(port="COM3", baud=115200)
        bridge.connect()
        bridge.send_vision(dx=-0.1, dy=0.0, distance_m=5.2, danger=False)
        bridge.disconnect()
    """

    def __init__(self, port: str = "COM3", baud: int = 115200) -> None:
        self.port = port
        self.baud = baud
        self.ser: Any = None

    def connect(self) -> None:
        """打开串口连接飞控。"""
        if not HAS_SERIAL:
            logger.warning("pyserial 未安装，无法连接飞控。运行: uv add pyserial")
            return
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            logger.info("已连接飞控: %s @ %d baud", self.port, self.baud)
        except serial.SerialException as exc:
            logger.error("飞控连接失败: %s", exc)
            raise

    def disconnect(self) -> None:
        """关闭串口。"""
        if self.ser and HAS_SERIAL:
            try:
                self.ser.close()
                logger.info("飞控已断开")
            except Exception:
                pass

    def _msp_send(self, cmd: int, data: list[int] | None = None) -> None:
        """发送 MSP 指令。"""
        if not self.ser or not HAS_SERIAL:
            return
        data = data or []
        length = len(data)
        buf = b'$M<' + bytes([length & 0xFF, cmd & 0xFF])
        buf += bytes(data)
        buf += bytes([(length ^ cmd) & 0xFF])
        try:
            self.ser.write(buf)
        except Exception as exc:
            logger.warning("MSP 发送失败: %s", exc)

    def set_rc(
        self,
        roll: int = 1500,
        pitch: int = 1500,
        yaw: int = 1500,
        throttle: int = 1000,
    ) -> None:
        """设置遥控通道值（PWM: 1000-2000，中位 1500）。"""
        rc_data = []
        for v in [roll, pitch, yaw, throttle, 1500, 1500, 1500, 1500]:
            rc_data.extend([v & 0xFF, (v >> 8) & 0xFF])
        self._msp_send(MSP_SET_RAW_RC, rc_data)

    def send_vision(
        self,
        dx: float,
        dy: float,
        distance_m: float,
        danger: bool,
    ) -> None:
        """视觉输出转成飞控指令。

        Args:
            dx: 水平偏移（-1~1，正=右侧）
            dy: 垂直偏移（-1~1，正=下方）
            distance_m: 目标距离（米）
            danger: 是否有危险目标
        """
        if not self.ser or not HAS_SERIAL:
            return

        if danger:
            logger.info("危险目标！油门归零")
            self.set_rc(throttle=1000)
            return

        if distance_m < 3.0:
            logger.info("距离 %.1fm，减速悬停", distance_m)
            self.set_rc(pitch=1500, throttle=1200)
            return

        if abs(dx) > 0.05:
            yaw_value = 1500 + int(dx * 500)
            yaw_value = max(1000, min(2000, yaw_value))
            logger.info("转向: dx=%.2f → yaw=%d", dx, yaw_value)
            self.set_rc(yaw=yaw_value, throttle=1500)
        else:
            logger.info("目标居中，前进")
            self.set_rc(pitch=1550, throttle=1500)
