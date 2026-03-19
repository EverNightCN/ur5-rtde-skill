from openclaw_ur5_skill import init_claw


def main() -> None:
    # URSim / Docker common host
    ROBOT_IP = "127.0.0.1"
    UNITS = "mm"
    TOOL_DO_PIN = 0

    # Safety default: do not execute pick_and_place until points are confirmed.
    RUN_PICK_AND_PLACE = False

    # Work points in selected units (mm here)
    PICK_POINT = (300.0, 0.0, 120.0)
    PLACE_POINT = (380.0, -80.0, 120.0)
    APPROACH_OFFSET = 80.0
    MOTION_SPEED = 220.0

    try:
        claw = init_claw(host=ROBOT_IP, units=UNITS, tool_do_pin=TOOL_DO_PIN)

        print("\n[1/4] connect")
        print(claw.connect())

        print("\n[2/4] calibrate")
        cal = claw.calibrate()
        print(cal)
        if not cal.get("ok", False):
            print("Calibration failed. Try recover() and re-check UR state.")
            print(claw.recover(safe_z=220.0, speed=150.0))
            return

        print("\n[3/4] execute")
        if RUN_PICK_AND_PLACE:
            result = claw.pick_and_place(
                pick=PICK_POINT,
                place=PLACE_POINT,
                approach_offset=APPROACH_OFFSET,
                speed=MOTION_SPEED,
            )
            print(result)
            if not result.get("ok", False):
                print("Execution failed, running recover...")
                print(claw.recover(safe_z=220.0, speed=150.0))
        else:
            print(
                "RUN_PICK_AND_PLACE=False, skipped motion. "
                "Set True after confirming workspace safety."
            )

        print("\n[4/4] status")
        print(claw.get_status())

    except Exception as exc:
        print(f"Startup failed: {exc}")
        print("Check UR remote control mode and network ports (30004/30002).")


if __name__ == "__main__":
    main()

