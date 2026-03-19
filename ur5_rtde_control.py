from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Sequence, Tuple


Units = Literal["m", "mm"]


@dataclass(frozen=True)
class UR5Config:
    host: str = "192.168.0.2"
    units: Units = "m"
    tcp: Optional[Tuple[float, float, float, float, float, float]] = None  # meters + rotvec(rad)
    payload_kg: Optional[float] = None
    payload_cog_m: Optional[Tuple[float, float, float]] = None


class UR5Interface:
    """
    Minimal, concrete UR5 controller wrapper over `ur-rtde`.

    Motion conventions:
      - TCP pose: (x,y,z,rx,ry,rz) where xyz are in meters, rxyz are rotation-vector radians.
      - If cfg.units == "mm", xyz inputs are treated as millimeters and converted to meters.
    """

    def __init__(self, cfg: UR5Config):
        self.cfg = cfg

        try:
            from rtde_control import RTDEControlInterface  # type: ignore
            from rtde_receive import RTDEReceiveInterface  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "This skill requires the `ur-rtde` Python package. "
                "Install it with: pip install ur-rtde"
            ) from e

        self._rtde_c = RTDEControlInterface(cfg.host)
        self._rtde_r = RTDEReceiveInterface(cfg.host)

        if cfg.tcp is not None:
            self._rtde_c.setTcp(cfg.tcp)
        if cfg.payload_kg is not None:
            if cfg.payload_cog_m is None:
                self._rtde_c.setPayload(cfg.payload_kg)
            else:
                self._rtde_c.setPayload(cfg.payload_kg, cfg.payload_cog_m)

    # ---------- state ----------

    def get_tcp_pose(self) -> Tuple[float, float, float, float, float, float]:
        pose = tuple(float(x) for x in self._rtde_r.getActualTCPPose())
        return pose  # meters + rotvec radians

    def get_joint_positions(self) -> Tuple[float, float, float, float, float, float]:
        q = tuple(float(x) for x in self._rtde_r.getActualQ())
        return q  # radians

    # ---------- motion ----------

    def moveL_to(
        self,
        *,
        x: float,
        y: float,
        z: float,
        rx: float,
        ry: float,
        rz: float,
        speed: float = 0.25,
        accel: float = 0.8,
        asynchronous: bool = False,
    ) -> bool:
        x_m, y_m, z_m = _to_m(x, y, z, self.cfg.units)
        pose = [x_m, y_m, z_m, float(rx), float(ry), float(rz)]
        return bool(self._rtde_c.moveL(pose, float(speed), float(accel), bool(asynchronous)))

    def moveJ(
        self,
        q: Sequence[float],
        *,
        speed: float = 1.05,
        accel: float = 1.4,
        asynchronous: bool = False,
    ) -> bool:
        q_list = [float(v) for v in q]
        if len(q_list) != 6:
            raise ValueError("UR5 moveJ expects 6 joint values (q0..q5) in radians.")
        return bool(self._rtde_c.moveJ(q_list, float(speed), float(accel), bool(asynchronous)))

    def stop(self, deceleration: float = 2.0) -> bool:
        # speedStop exists in ur-rtde; use it as the safe "stop current motion".
        return bool(self._rtde_c.speedStop(float(deceleration)))

    def stop_script(self) -> bool:
        """
        Stop the running program/script on the UR controller side.
        Mirrors `RTDEControlInterface.stopScript()`.
        """
        return bool(self._rtde_c.stopScript())

    # ---------- IO ----------

    def set_tool_digital_out(self, *, pin: int, value: bool) -> bool:
        return bool(self._rtde_c.setToolDigitalOut(int(pin), bool(value)))

    # ---------- lifecycle ----------

    def disconnect(self) -> None:
        # ur-rtde provides disconnect on RTDEControlInterface; keep best-effort.
        try:
            self._rtde_c.disconnect()
        except Exception:
            pass


_global_ur5: Optional[UR5Interface] = None


def init_ur5(
    *,
    host: str = "192.168.0.2",
    units: Units = "m",
    tcp: Optional[Tuple[float, float, float, float, float, float]] = None,
    payload_kg: Optional[float] = None,
    payload_cog_m: Optional[Tuple[float, float, float]] = None,
) -> UR5Interface:
    global _global_ur5
    cfg = UR5Config(
        host=host,
        units=units,
        tcp=tcp,
        payload_kg=payload_kg,
        payload_cog_m=payload_cog_m,
    )
    _global_ur5 = UR5Interface(cfg)
    return _global_ur5


def get_ur5() -> UR5Interface:
    global _global_ur5
    if _global_ur5 is None:
        _global_ur5 = init_ur5()
    return _global_ur5


def _to_m(x: float, y: float, z: float, units: Units) -> Tuple[float, float, float]:
    if units == "m":
        return float(x), float(y), float(z)
    if units == "mm":
        return float(x) / 1000.0, float(y) / 1000.0, float(z) / 1000.0
    raise ValueError("units must be 'm' or 'mm'")

