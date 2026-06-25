import numpy as np
import pytest


@pytest.fixture
def kf():
    from app.services.kalman_filter import KalmanFilter1D
    return KalmanFilter1D(dt=0.2, process_noise=0.4, observation_noise=1.0)


def test_converges_to_constant_distance(kf):
    """恒定距离 5.0m，连续观测后 distance 应收敛到接近 5.0。"""
    for _ in range(20):
        kf.update(5.0)
    state = kf.get_state()
    assert state["distance"] == pytest.approx(5.0, abs=0.5)
    assert abs(state["velocity"]) < 0.3


def test_tracks_constant_velocity(kf):
    """匀速靠近（每帧距离减少 0.3m）应跟踪出速度约 1.5m/s（dt=0.2）。"""
    obs = [5.0, 4.7, 4.4, 4.1, 3.8, 3.5, 3.2, 2.9, 2.6, 2.3]
    for z in obs:
        kf.update(z)
    state = kf.get_state()
    assert state["velocity"] == pytest.approx(1.5, abs=0.5)


def test_empty_observation_does_not_crash(kf):
    """update(None) 应只做预测，不崩溃。"""
    kf.update(5.0)
    kf.update(None)
    state = kf.get_state()
    assert "distance" in state
    assert "velocity" in state


def test_reset_clears_state(kf):
    """reset() 应将状态清零。"""
    kf.update(5.0)
    kf.reset()
    state = kf.get_state()
    assert state["distance"] == 0.0
    assert state["velocity"] == 0.0
