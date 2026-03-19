from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface


def main() -> None:
    # 1. 定义连接地址（本地回环）
    # Docker 映射了 -p 30004:30004，所以这里用 127.0.0.1
    ROBOT_IP = "127.0.0.1"

    try:
        # 2. 初始化接口
        # RTDEControlInterface 用于下发指令（动起来）
        # RTDEReceiveInterface 用于获取状态（读数据）
        rtde_c = RTDEControlInterface(ROBOT_IP)
        rtde_r = RTDEReceiveInterface(ROBOT_IP)

        print("Connected OK.")

        # 3. 读取当前关节角度
        actual_q = rtde_r.getActualQ()
        print(f"Actual Q: {actual_q}")

        # 4. 尝试一个小幅度的关节移动 (moveJ)
        # 参数：[基座, 肩部, 肘部, 腕1, 腕2, 腕3] (弧度)
        target_q = [-1.57, -1.57, 1.57, -1.57, -1.57, 0.0]

        print("Moving... (moveJ)")
        rtde_c.moveJ(target_q, speed=0.5, acceleration=0.3)

        # 5. 安全断开（停止脚本）
        rtde_c.stopScript()

    except Exception as e:
        print(f"Connection failed: {e!r}")

        # Quick port checks (URSim Docker often needs 30002 + 30004)
        try:
            import socket

            def port_ok(p: int) -> bool:
                try:
                    s = socket.create_connection((ROBOT_IP, p), timeout=1.0)
                    s.close()
                    return True
                except Exception:
                    return False

            p30004 = port_ok(30004)
            p30002 = port_ok(30002)
            print(f"Port check: 30004={p30004} (RTDE), 30002={p30002} (script/secondary)")
        except Exception:
            pass

        # Extra diagnosis: check whether RTDE receive works (port 30004 mapped)
        try:
            r = RTDEReceiveInterface(ROBOT_IP)
            q = r.getActualQ()
            print("RTDEReceiveInterface works (able to read ActualQ).")
            print(f"Actual Q: {q}")
            print(
                "But RTDEControlInterface failed. In URSim Docker, you likely only mapped 30004.\n"
                "ur-rtde control usually needs additional ports (commonly 30002 for script upload).\n"
                "Fix: expose at least 30002 and 30004 to localhost, and often 30001/30003 and 29999 (dashboard) too."
            )
        except Exception:
            pass

        print(
            "Checklist: ensure URSim UI (localhost:6080) shows Power On + Normal, "
            "and Docker publishes required UR ports (30002/30004)."
        )


if __name__ == "__main__":
    main()

