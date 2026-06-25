"""1D 卡尔曼滤波器，用于平滑距离并估算速度。

状态: [distance, velocity]^T
  distance  : 目标距离（米）
  velocity  : 目标速度（米/帧，正=靠近）

观测: distance_m（标量）
"""

import numpy as np


class KalmanFilter1D:
    def __init__(
        self,
        dt: float = 0.2,
        process_noise: float = 0.1,
        observation_noise: float = 1.0,
    ) -> None:
        self.dt = dt
        self.F = np.array([[1.0, dt], [0.0, 1.0]], dtype=np.float64)
        self.H = np.array([[1.0, 0.0]], dtype=np.float64)
        # 离散白噪声加速度（DWNA）模型
        # process_noise：每帧速度变化方差
        # 非对角元使位置观测更新能影响速度估计
        self.Q = process_noise * np.array(
            [[dt**2 / 3, dt / 2], [dt / 2, 1.0]], dtype=np.float64
        )
        self.R = np.eye(1, dtype=np.float64) * observation_noise
        self.x = np.zeros((2, 1), dtype=np.float64)
        self.P = np.eye(2, dtype=np.float64)

    def predict(self) -> None:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, z: float | None) -> None:
        if z is not None:
            self.predict()
            z_arr = np.array([[z]], dtype=np.float64)
            y = z_arr - self.H @ self.x
            S = self.H @ self.P @ self.H.T + self.R
            K = self.P @ self.H.T @ np.linalg.inv(S)
            self.x += K @ y
            self.P = (np.eye(2) - K @ self.H) @ self.P
        else:
            self.predict()

    def get_state(self) -> dict:
        return {
            "distance": round(float(self.x[0, 0]), 1),
            "velocity": round(-float(self.x[1, 0]), 2),
        }

    def reset(self) -> None:
        self.x = np.zeros((2, 1), dtype=np.float64)
        self.P = np.eye(2, dtype=np.float64)
