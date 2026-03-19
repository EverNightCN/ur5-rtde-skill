# UR5 RTDE Control Skill

## Overview
This is a **standalone skill** for controlling a **Universal Robots UR5** via **RTDE** using the `ur-rtde` Python package.

It is intentionally independent from the OpenClaw metadata-only skill and focuses on a concrete, testable UR5 control backend:
- TCP pose motion (`moveL`)
- Joint motion (`moveJ`)
- Tool digital outputs (simple gripper mapping)
- Stop + status feedback
- Procedure-oriented execution (`connect/calibrate/recover/pick_and_place`)

## Trigger scenarios
Use this skill when the user has clear UR5 action intent, for example:
- "Move the UR5 to a target point"
- "Run a pick-and-place cycle"
- "Open/close gripper output"
- "Stop current motion and recover"

## 触发场景（中文）
当用户有明确 UR5 动作意图时调用本技能，例如：
- "把 UR5 移动到目标点"
- "执行一次抓取放置流程"
- "打开/关闭夹爪数字输出"
- "立即停止并进入恢复流程"

## Invocation rules
- Prefer procedure-first flow: `connect -> calibrate -> execute -> recover`
- Run in non-interactive/scripted mode; avoid manual step prompts in the middle of execution
- Validate environment preconditions before motion (network, remote control mode, port mapping)
- Return concise execution result and status snapshot; avoid noisy debug output in normal path
- On any execution failure, call `recover()` before retrying

## 调用规则（中文）
- 优先使用流程化调用：`connect -> calibrate -> execute -> recover`
- 采用脚本化自动执行，尽量避免中途人工交互
- 动作执行前检查前置条件（网络、远程控制模式、端口映射）
- 正常路径只返回核心结果与状态快照，减少冗余日志
- 任一步骤失败后先执行 `recover()`，再决定是否重试

## Slug
`ur5-rtde-control`

## Requirements
- UR controller reachable over network (default port for RTDE)
- Robot in Remote Control mode (as required by your UR software / safety settings)
- Python dependency: `ur-rtde`
 - Recommended Python: **3.10 / 3.11** (Windows + Python 3.13 often triggers source builds)

### URSim / Docker port mapping note
If you run URSim in Docker and only publish `30004` (RTDE), you may be able to **read state** (RTDE Receive)
but **control** (RTDE Control) can fail because `ur-rtde` typically uploads/streams URScript via additional ports
(most commonly `30002`).

Recommended published ports (host -> container):
- `30004` (RTDE)
- `30002` (script upload / secondary interface, commonly required by RTDE Control)
- Often also `30001` / `30003` and `29999` (dashboard), depending on your workflow

## Install
```bash
pip install -r requirements.txt
```

### Windows (common install fix)
On Windows, `ur-rtde` is often built from source. If you see an error like:
`UnicodeDecodeError: 'gbk' codec can't decode ...` during `pip install`, run the install in a UTF-8 PowerShell session:

```powershell
chcp 65001
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
pip install -r requirements.txt --no-build-isolation
```

If you then hit compiler/CMake errors, install:
- Visual Studio Build Tools (Desktop development with C++)
- CMake (and optionally Ninja)

## Quick start
```python
from ur5_rtde_control import init_ur5

ur = init_ur5(host="192.168.0.2", units="m")

# Read current TCP pose (meters + rotvec radians)
print("tcp:", ur.get_tcp_pose())

# Move in a straight line to a target TCP pose
# pose: x,y,z (m), rx,ry,rz (rotation vector, rad)
ok = ur.moveL_to(x=0.30, y=0.00, z=0.20, rx=0.0, ry=3.14, rz=0.0, speed=0.25, accel=0.8)
print("moveL ok:", ok)

# Simple gripper mapping via tool DO
ur.set_tool_digital_out(pin=0, value=True)   # close
ur.set_tool_digital_out(pin=0, value=False)  # open
```

## OpenClaw-compatible adapter (for integration)
If you want to plug this skill into an OpenClaw/JARVIS-style loader that expects
`init_claw()` / `get_claw()` and methods like `grab/move_to/rotate/release`, use:

```python
from openclaw_ur5_skill import init_claw

claw = init_claw(host="127.0.0.1", units="mm", tool_do_pin=0)
claw.move_to(300, 0, 200, speed=250)  # mm, mm/s
claw.rotate(45, axis="z", speed=50)
claw.grab(force=50.0, duration=0.5)
claw.release(speed=50.0)
```

## Standard invocation format
```python
from openclaw_ur5_skill import init_claw

claw = init_claw(host="127.0.0.1", units="mm", tool_do_pin=0)
print(claw.connect())
print(claw.calibrate())
```

### Procedure-first usage (RoboClaw-style)
This skill now also supports higher-level procedures inspired by RoboClaw's execution flow:

```python
from openclaw_ur5_skill import init_claw

claw = init_claw(host="127.0.0.1", units="mm", tool_do_pin=0)

print(claw.connect())      # {"ok": True, "procedure": "connect", ...}
print(claw.calibrate())    # preflight state checks

result = claw.pick_and_place(
    pick=(300, 0, 120),
    place=(380, -80, 120),
    approach_offset=80,
    speed=220,
)
print(result)

# On fault / interruption:
print(claw.recover(safe_z=220, speed=150))
```

Each procedure returns a structured object:
- `ok`: success/failure
- `procedure`: procedure name
- `code`: machine-friendly status code
- `message`: human-readable message
- `telemetry`: minimal connection/state snapshot

## Failure/Status Code Reference
| code | meaning | recommended action |
| --- | --- | --- |
| `connect_ready` | runtime session ready | continue to `calibrate()` |
| `calibrate_ok` | preflight checks passed | continue execution |
| `calibrate_failed` | preflight checks failed | inspect `status`, verify UR mode and ports |
| `pick_and_place_ok` | sequence succeeded | return success |
| `pick_and_place_failed` | sequence failed | call `recover()`, then retry if safe |
| `recover_ok` | recovery completed | re-run `calibrate()` before next motion |
| `recover_failed` | recovery failed | stop task and request manual inspection |
| `ok` | generic success code | treat as success |

## Workflow
1. Receive user task intent (move, pick-place, stop/recover)
2. Initialize runtime via `init_claw(...)`
3. Run preflight with `connect()` and `calibrate()`
4. Execute target procedure (`move_to`, `pick_and_place`, `grab/release`, etc.)
5. If execution fails, run `recover()` and return structured failure result
6. Return final status snapshot (`get_status()`)

## 工作流程（中文）
1. 接收任务意图（移动、抓放、停止/恢复）
2. 通过 `init_claw(...)` 初始化运行时
3. 执行 `connect()` 与 `calibrate()` 预检查
4. 执行目标动作（`move_to`、`pick_and_place`、`grab/release` 等）
5. 若失败，先 `recover()`，返回结构化失败信息
6. 返回最终状态快照（`get_status()`）

## Notes on units
- This skill supports `units="m"` (recommended) or `units="mm"` for positional parameters.
- Orientation uses UR rotation-vector (axis-angle) in **radians**: `(rx, ry, rz)`.

## Safety notes
1. Ensure the robot can be safely controlled in current environment before enabling motion.
2. Confirm target point is inside reachable workspace and collision-free.
3. Verify UR controller is in remote control mode and required ports are available.
4. On first run, keep `RUN_PICK_AND_PLACE=False` and validate points with dry-run logic.
5. Keep an emergency stop path available in real hardware environment.

### Soft-fence (anti-absurd input)
The skill includes a lightweight software fence to reject clearly unreasonable commands:
- In `units="mm"`: `x/y` in `[-2000, 2000]`, `z` in `[-500, 2500]`, `speed <= 3000`
- In `units="m"`: `x/y` in `[-2.0, 2.0]`, `z` in `[-0.5, 2.5]`, `speed <= 3.0`
- Rotation rejects non-finite values and angles with `abs(angle) > 360`

This is only a software sanity check and does **not** replace controller-side safety configuration.
Soft-fence values are configurable in `skill.json` under `softFence`.

## 注意事项（中文）
1. 确保当前环境允许安全控制机械臂后再启用运动。
2. 确保目标点在可达范围内，且路径无碰撞风险。
3. 确保控制器处于远程控制模式，且关键端口可访问。
4. 首次运行建议保持 `RUN_PICK_AND_PLACE=False`，先做点位干跑验证。
5. 真机环境必须保留紧急停止通道。

## Suggested execution order
For stable real/sim operation, prefer:
1. `connect()`
2. `calibrate()`
3. motion/gripper procedures (`move_to`, `pick_and_place`, etc.)
4. `recover()` on failure, then retry or reset

