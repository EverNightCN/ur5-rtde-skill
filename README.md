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

---

# UR5 RTDE 技能（兼容 OpenClaw）

这是一个基于 **RTDE** 控制 **Universal Robots UR5** 的独立 Python skill，采用流程化（procedure-first）接口：

- `connect()`
- `calibrate()`
- `move_to()`
- `rotate()`
- `grab()` / `release()`
- `pick_and_place()`
- `recover()`

本仓库面向 OpenClaw/Jarvis 风格加载器，重点是提供可测试、可复用的 UR5 控制后端。

## 功能特性

- 通过 `moveL` 实现 UR5 TCP 位姿运动
- 支持 `moveJ` 关节运动
- 通过工具数字输出映射简单夹爪开合
- 支持流程化执行与结构化状态/失败码
- 内置软围栏，用于拦截明显离谱输入
- 软围栏参数可在 `skill.json` 中配置

## 项目文件

- `ur5_rtde_control.py`：UR RTDE 低层封装
- `openclaw_ur5_skill.py`：OpenClaw 兼容适配层与流程接口
- `skill.json`：skill 元数据与 `softFence` 配置
- `SKILL.md`：中英双语详细使用规范
- `example.py`：流程化调用示例

## 运行要求

- 推荐 Python 3.10 或 3.11
- `ur-rtde`
- UR 控制器/URSim 网络可达
- 机器人处于 Remote Control 模式
- RTDE/控制端口可用（常见 `30004` 与 `30002`）

安装依赖：

```bash
pip install -r requirements.txt
```

## 快速开始

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

## 软围栏配置

软围栏默认设置较宽，仅用于拦截极端或非法输入。  
你可以在 `skill.json` 中调整参数：

```json
"softFence": {
  "mm": { "x_min": -2000, "x_max": 2000, "y_min": -2000, "y_max": 2000, "z_min": -500, "z_max": 2500, "speed_max": 3000 },
  "m":  { "x_min": -2.0,  "x_max": 2.0,  "y_min": -2.0,  "y_max": 2.0,  "z_min": -0.5,  "z_max": 2.5,  "speed_max": 3.0  },
  "rotation": { "angle_abs_max_deg": 360.0 }
}
```

## 安全说明

软围栏仅是软件层输入校验，不可替代 PolyScope 控制器侧的安全配置（安全平面、速度限制、停机行为等）。

## 许可证

MIT（以 `skill.json` 中声明为准）。
