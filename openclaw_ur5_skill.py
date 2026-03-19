from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

from ur5_rtde_control import UR5Interface, init_ur5


Units = Literal["m", "mm"]
Axis = Literal["x", "y", "z", "rx", "ry", "rz"]

CODE_OK = "ok"
CODE_CONNECT_READY = "connect_ready"
CODE_CALIBRATE_OK = "calibrate_ok"
CODE_CALIBRATE_FAILED = "calibrate_failed"
CODE_RECOVER_OK = "recover_ok"
CODE_RECOVER_FAILED = "recover_failed"
CODE_PICK_AND_PLACE_OK = "pick_and_place_ok"
CODE_PICK_AND_PLACE_FAILED = "pick_and_place_failed"

# Soft-fence defaults are intentionally wide. They only reject clearly absurd values.
SOFT_FENCE_MM = {
    "x_min": -2000.0,
    "x_max": 2000.0,
    "y_min": -2000.0,
    "y_max": 2000.0,
    "z_min": -500.0,
    "z_max": 2500.0,
    "speed_max": 3000.0,  # mm/s
}
SOFT_FENCE_M = {
    "x_min": -2.0,
    "x_max": 2.0,
    "y_min": -2.0,
    "y_max": 2.0,
    "z_min": -0.5,
    "z_max": 2.5,
    "speed_max": 3.0,  # m/s
}
SOFT_FENCE_ROTATION = {
    "angle_abs_max_deg": 360.0,
}


def _safe_float(v: Any, default: float) -> float:
    try:
        f = float(v)
        if math.isfinite(f):
            return f
    except Exception:
        pass
    return float(default)


def _load_soft_fence_from_skill_json() -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """
    Load soft-fence from local skill.json if available.
    Falls back to module defaults on any parse/validation issue.
    """
    mm = dict(SOFT_FENCE_MM)
    m = dict(SOFT_FENCE_M)
    rot = dict(SOFT_FENCE_ROTATION)

    try:
        cfg_path = Path(__file__).with_name("skill.json")
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        soft = data.get("softFence", {})

        mm_cfg = soft.get("mm", {})
        for k in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max", "speed_max"):
            mm[k] = _safe_float(mm_cfg.get(k, mm[k]), mm[k])

        m_cfg = soft.get("m", {})
        for k in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max", "speed_max"):
            m[k] = _safe_float(m_cfg.get(k, m[k]), m[k])

        rot_cfg = soft.get("rotation", {})
        rot["angle_abs_max_deg"] = _safe_float(rot_cfg.get("angle_abs_max_deg", rot["angle_abs_max_deg"]), rot["angle_abs_max_deg"])
    except Exception:
        pass

    return mm, m, rot


SOFT_FENCE_MM_CONFIG, SOFT_FENCE_M_CONFIG, SOFT_FENCE_ROTATION_CONFIG = _load_soft_fence_from_skill_json()


@dataclass(frozen=True)
class OpenClawUR5Config:
    """
    OpenClaw-style configuration for a UR5 backend.

    - host: UR controller/URSim host (e.g. "127.0.0.1" for Docker-mapped URSim)
    - units: units for move_to() x/y/z inputs ("mm" matches many OpenClaw examples)
    - tool_do_pin: tool digital output used as a simple gripper open/close mapping
    - gripper_mode:
        - "tool_digital_out": grab/release toggle a tool DO pin
        - "none": grab/release are no-ops (useful if you don't have a gripper yet)
    """

    host: str = "127.0.0.1"
    units: Units = "mm"
    tool_do_pin: int = 0
    gripper_mode: Literal["tool_digital_out", "none"] = "tool_digital_out"


class OpenClawUR5:
    """
    Adapter that matches the OpenClaw skill interface shape:
      - init_claw() / get_claw()
      - grab(force, duration)
      - release(speed)
      - move_to(x,y,z,speed)
      - rotate(angle, axis, speed)

    Implementation notes:
      - move_to preserves current orientation and moves TCP linearly (moveL).
      - rotate applies an incremental rotation-vector delta along a chosen base axis.
      - force/speed are mapped onto basic IO + speed defaults (UR itself is not a gripper).
    """

    def __init__(self, ur: UR5Interface, cfg: OpenClawUR5Config):
        self._ur = ur
        self._cfg = cfg
        self._connected = True
        self._last_validation_error = ""

    @property
    def connected(self) -> bool:
        # If init succeeded, assume connected unless an explicit disconnect was requested.
        return self._connected

    def _result(
        self,
        *,
        ok: bool,
        procedure: str,
        code: str = "ok",
        message: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ok": bool(ok),
            "procedure": procedure,
            "code": code,
            "message": message,
            "timestamp": time.time(),
            "telemetry": {
                "connected": self.connected,
            },
        }
        if extra:
            out.update(extra)
        return out

    def _safe_status_snapshot(self) -> Dict[str, Any]:
        try:
            pose = self._ur.get_tcp_pose()
        except Exception as exc:
            pose = f"unavailable: {exc}"
        try:
            q = self._ur.get_joint_positions()
        except Exception as exc:
            q = f"unavailable: {exc}"
        return {"connected": self.connected, "tcp_pose": pose, "q": q}

    def _fence(self) -> Dict[str, float]:
        return SOFT_FENCE_MM_CONFIG if self._cfg.units == "mm" else SOFT_FENCE_M_CONFIG

    @staticmethod
    def _is_finite(v: float) -> bool:
        return math.isfinite(float(v))

    def _validate_move_inputs(self, x: float, y: float, z: float, speed: float) -> Tuple[bool, str]:
        for name, value in (("x", x), ("y", y), ("z", z), ("speed", speed)):
            if not self._is_finite(value):
                return False, f"{name} must be finite"

        fence = self._fence()
        if not (fence["x_min"] <= float(x) <= fence["x_max"]):
            return False, f"x out of soft-fence range [{fence['x_min']}, {fence['x_max']}]"
        if not (fence["y_min"] <= float(y) <= fence["y_max"]):
            return False, f"y out of soft-fence range [{fence['y_min']}, {fence['y_max']}]"
        if not (fence["z_min"] <= float(z) <= fence["z_max"]):
            return False, f"z out of soft-fence range [{fence['z_min']}, {fence['z_max']}]"
        if float(speed) <= 0.0:
            return False, "speed must be > 0"
        if float(speed) > fence["speed_max"]:
            return False, f"speed out of soft-fence range (max {fence['speed_max']})"
        return True, ""

    # ---------- RoboClaw-style procedures ----------

    def connect(self) -> Dict[str, Any]:
        """
        Keep compatibility with stacks that model connection as an explicit procedure.
        """
        self._connected = True
        return self._result(
            ok=True,
            procedure="connect",
            code=CODE_CONNECT_READY,
            message="UR5 RTDE session is ready.",
        )

    def calibrate(self) -> Dict[str, Any]:
        """
        For UR5 RTDE this is a lightweight preflight (state read + basic health probe).
        """
        try:
            status = self.get_status()
            return self._result(
                ok=True,
                procedure="calibrate",
                code=CODE_CALIBRATE_OK,
                message="Calibration preflight passed.",
                extra={"status": status},
            )
        except Exception as exc:
            return self._result(
                ok=False,
                procedure="calibrate",
                code=CODE_CALIBRATE_FAILED,
                message=f"Calibration preflight failed: {exc}",
                extra={"status": self._safe_status_snapshot()},
            )

    def recover(self, *, safe_z: Optional[float] = None, speed: float = 150.0) -> Dict[str, Any]:
        """
        Recovery path:
        1) stop current motion
        2) optionally move TCP upward to a safer Z
        """
        try:
            self.stop()
            moved = None
            if safe_z is not None:
                cur = self._ur.get_tcp_pose()
                x, y = cur[0], cur[1]
                z = float(safe_z)
                if self._cfg.units == "mm":
                    x, y, _ = x * 1000.0, y * 1000.0, cur[2] * 1000.0
                moved = self.move_to(x=x, y=y, z=z, speed=speed)
            return self._result(
                ok=True,
                procedure="recover",
                code=CODE_RECOVER_OK,
                message="Recovery sequence completed.",
                extra={"moved_to_safe_z": moved, "status": self._safe_status_snapshot()},
            )
        except Exception as exc:
            return self._result(
                ok=False,
                procedure="recover",
                code=CODE_RECOVER_FAILED,
                message=f"Recovery failed: {exc}",
                extra={"status": self._safe_status_snapshot()},
            )

    def pick_and_place(
        self,
        *,
        pick: Tuple[float, float, float],
        place: Tuple[float, float, float],
        approach_offset: float = 80.0,
        speed: float = 200.0,
    ) -> Dict[str, Any]:
        """
        High-level procedure for quick embodied tests:
        approach pick -> pick -> lift -> approach place -> place -> retreat.
        """
        try:
            px, py, pz = pick
            tx, ty, tz = place
            # Approach and pick
            self.move_to(px, py, pz + approach_offset, speed=speed)
            self.move_to(px, py, pz, speed=max(80.0, speed * 0.5))
            self.grab()
            self.move_to(px, py, pz + approach_offset, speed=speed)
            # Move and place
            self.move_to(tx, ty, tz + approach_offset, speed=speed)
            self.move_to(tx, ty, tz, speed=max(80.0, speed * 0.5))
            self.release()
            self.move_to(tx, ty, tz + approach_offset, speed=speed)
            return self._result(
                ok=True,
                procedure="pick_and_place",
                code=CODE_PICK_AND_PLACE_OK,
                message="Pick-and-place sequence completed.",
                extra={"status": self._safe_status_snapshot()},
            )
        except Exception as exc:
            self.stop()
            detail = str(exc)
            if self._last_validation_error:
                detail = f"{detail}; validation={self._last_validation_error}"
            return self._result(
                ok=False,
                procedure="pick_and_place",
                code=CODE_PICK_AND_PLACE_FAILED,
                message=f"Pick-and-place failed: {detail}",
                extra={"status": self._safe_status_snapshot()},
            )

    def grab(self, force: float = 50.0, duration: float = 0.5) -> bool:
        if self._cfg.gripper_mode == "none":
            return True
        # For now, map "grab" to DO high. (force/duration left for future gripper drivers)
        ok = self._ur.set_tool_digital_out(pin=self._cfg.tool_do_pin, value=True)
        return bool(ok)

    def release(self, speed: float = 50.0) -> bool:
        if self._cfg.gripper_mode == "none":
            return True
        ok = self._ur.set_tool_digital_out(pin=self._cfg.tool_do_pin, value=False)
        return bool(ok)

    def move_to(self, x: float, y: float, z: float, speed: float = 250.0) -> bool:
        # speed is interpreted as mm/s (if units="mm") or m/s (if units="m")
        self._last_validation_error = ""
        valid, reason = self._validate_move_inputs(x=x, y=y, z=z, speed=speed)
        if not valid:
            self._last_validation_error = reason
            return False

        cur = self._ur.get_tcp_pose()
        x_m, y_m, z_m = _to_m(x, y, z, self._cfg.units)
        rx, ry, rz = cur[3], cur[4], cur[5]

        speed_m_s = _speed_to_m_s(speed, self._cfg.units)
        accel_m_s2 = max(0.05, speed_m_s * 2.0)

        return bool(
            self._ur.moveL_to(
                x=x_m,
                y=y_m,
                z=z_m,
                rx=rx,
                ry=ry,
                rz=rz,
                speed=speed_m_s,
                accel=accel_m_s2,
            )
        )

    def rotate(self, angle: float, axis: Axis = "z", speed: float = 50.0) -> bool:
        self._last_validation_error = ""
        if not self._is_finite(angle) or not self._is_finite(speed):
            self._last_validation_error = "angle/speed must be finite"
            return False
        angle_abs_max_deg = SOFT_FENCE_ROTATION_CONFIG["angle_abs_max_deg"]
        if abs(float(angle)) > angle_abs_max_deg:
            self._last_validation_error = f"abs(angle) exceeds soft-fence limit ({angle_abs_max_deg} deg)"
            return False
        if float(speed) <= 0.0:
            self._last_validation_error = "speed must be > 0"
            return False
        if float(speed) > self._fence()["speed_max"]:
            self._last_validation_error = f"speed out of soft-fence range (max {self._fence()['speed_max']})"
            return False

        axis_l = axis.lower()
        if axis_l in ("x", "rx"):
            unit = (1.0, 0.0, 0.0)
        elif axis_l in ("y", "ry"):
            unit = (0.0, 1.0, 0.0)
        elif axis_l in ("z", "rz"):
            unit = (0.0, 0.0, 1.0)
        else:
            raise ValueError("axis must be one of: x,y,z,rx,ry,rz")

        cur = self._ur.get_tcp_pose()
        a = math.radians(float(angle))
        rx = cur[3] + unit[0] * a
        ry = cur[4] + unit[1] * a
        rz = cur[5] + unit[2] * a

        speed_m_s = max(0.02, _speed_to_m_s(speed, self._cfg.units))
        accel_m_s2 = max(0.05, speed_m_s * 2.0)

        return bool(
            self._ur.moveL_to(
                x=cur[0],
                y=cur[1],
                z=cur[2],
                rx=rx,
                ry=ry,
                rz=rz,
                speed=speed_m_s,
                accel=accel_m_s2,
            )
        )

    def stop(self, deceleration: float = 2.0) -> bool:
        return bool(self._ur.stop(deceleration=float(deceleration)))

    def stop_script(self) -> bool:
        ok = bool(self._ur.stop_script())
        if ok:
            self._connected = False
        return ok

    def get_status(self) -> dict:
        pose = self._ur.get_tcp_pose()
        q = self._ur.get_joint_positions()
        return {"connected": self.connected, "tcp_pose": pose, "q": q}


_global_claw: Optional[OpenClawUR5] = None


def init_claw(
    *,
    host: str = "127.0.0.1",
    units: Units = "mm",
    tool_do_pin: int = 0,
    gripper_mode: Literal["tool_digital_out", "none"] = "tool_digital_out",
) -> OpenClawUR5:
    """
    OpenClaw-compatible initializer.
    """
    global _global_claw
    cfg = OpenClawUR5Config(host=host, units=units, tool_do_pin=tool_do_pin, gripper_mode=gripper_mode)
    ur = init_ur5(host=cfg.host, units="m")  # keep UR5Interface in meters internally
    _global_claw = OpenClawUR5(ur=ur, cfg=cfg)
    return _global_claw


def get_claw() -> OpenClawUR5:
    global _global_claw
    if _global_claw is None:
        _global_claw = init_claw()
    return _global_claw


def _to_m(x: float, y: float, z: float, units: Units) -> Tuple[float, float, float]:
    if units == "m":
        return float(x), float(y), float(z)
    if units == "mm":
        return float(x) / 1000.0, float(y) / 1000.0, float(z) / 1000.0
    raise ValueError("units must be 'm' or 'mm'")


def _speed_to_m_s(speed: float, units: Units) -> float:
    # treat speed as linear TCP speed, same units as position
    if units == "m":
        return float(speed)
    if units == "mm":
        return float(speed) / 1000.0
    raise ValueError("units must be 'm' or 'mm'")

