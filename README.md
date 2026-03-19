# UR5 RTDE Skill (OpenClaw-Compatible)

A standalone Python skill for controlling **Universal Robots UR5** through **RTDE** with a procedure-first interface:

- `connect()`
- `calibrate()`
- `move_to()`
- `rotate()`
- `grab()` / `release()`
- `pick_and_place()`
- `recover()`

This repository is designed for OpenClaw/Jarvis-style loaders while keeping a practical and testable UR5 control backend.

## Features

- UR5 TCP pose motion via `moveL`
- Joint motion support via `moveJ`
- Tool digital output mapping for simple gripper control
- Procedure-oriented execution and structured status/error codes
- Soft-fence validation for obviously unreasonable inputs
- Configurable soft-fence values in `skill.json`

## Project Files

- `ur5_rtde_control.py`: low-level UR RTDE wrapper
- `openclaw_ur5_skill.py`: OpenClaw-compatible adapter and procedures
- `skill.json`: skill metadata and configurable `softFence`
- `SKILL.md`: detailed bilingual operation guide
- `example.py`: procedural demo flow

## Requirements

- Python 3.10 or 3.11 recommended
- `ur-rtde`
- UR controller/URSim reachable on network
- Robot in Remote Control mode
- RTDE/control ports available (commonly `30004` and `30002`)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from openclaw_ur5_skill import init_claw

claw = init_claw(host="127.0.0.1", units="mm", tool_do_pin=0)

print(claw.connect())
print(claw.calibrate())

result = claw.pick_and_place(
    pick=(300, 0, 120),
    place=(380, -80, 120),
    approach_offset=80,
    speed=220,
)
print(result)
```

## Soft-Fence Configuration

Soft-fence checks are intentionally wide and only reject extreme or invalid values.
You can tune them in `skill.json`:

```json
"softFence": {
  "mm": { "x_min": -2000, "x_max": 2000, "y_min": -2000, "y_max": 2000, "z_min": -500, "z_max": 2500, "speed_max": 3000 },
  "m":  { "x_min": -2.0,  "x_max": 2.0,  "y_min": -2.0,  "y_max": 2.0,  "z_min": -0.5,  "z_max": 2.5,  "speed_max": 3.0  },
  "rotation": { "angle_abs_max_deg": 360.0 }
}
```

## Safety Note

Soft-fence is only a software sanity check. It does **not** replace controller-side safety configuration in PolyScope (safety planes, speed limits, stop behavior, etc.).

## License

MIT (as declared in `skill.json`).
