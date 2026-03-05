import logging

from controller_control import PDXC2Controller


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    ctrl = PDXC2Controller()

    # --- Working example: homing + closed-loop move ---
    try:
        ctrl.connect()
        ctrl.ensure_settings()
        ctrl.home_closed_loop()
        ctrl.apply_all_parameters(enable_closed_loop=True)

        current = ctrl.get_current_position()
        target = current + ctrl.units_to_counts(2)
        ctrl.move_closed_loop_counts(target_counts=target)
    finally:
        ctrl.disconnect()

    # --- Connection lifecycle ---
    # ctrl.connect()
    # ctrl.disconnect()

    # --- One-shot initialize (settings + optional homing + apply params) ---
    # ctrl.initialize(home=True, enable_closed_loop=True)

    # --- Basic device ops ---
    # ctrl.ensure_settings()
    # ctrl.home_closed_loop()
    # ctrl.set_abnormal_move_detection(True)

    # --- Apply parameter groups ---
    # ctrl.apply_amp_out_parameters()
    # ctrl.apply_closed_loop_parameters()
    # ctrl.apply_jog_parameters()
    # ctrl.apply_open_loop_move_parameters()
    # ctrl.apply_trigger_parameters()
    # ctrl.apply_all_parameters(enable_closed_loop=True)

    # --- Position and mode ---
    # ctrl.request_current_position()
    # pos = ctrl.get_current_position()
    # mode = ctrl.read_control_mode()
    # ok = ctrl.try_set_control_mode(mode)
    # ok = ctrl.is_closed_loop_supported()

    # --- Units conversion ---
    # counts_per_unit = ctrl.get_counts_per_unit()
    # counts = ctrl.units_to_counts(0.1)
    # units = ctrl.counts_to_units(1000)

    # --- Moves ---
    # ctrl.move_open_loop(step_size=10_000, duration_s=0.5)
    # ctrl.move_open_loop_pid(target_counts=ctrl.units_to_counts(0.1))
    # ctrl.move_closed_loop_counts(target_counts=ctrl.units_to_counts(0.1))

    # --- Context manager usage ---
    # with PDXC2Controller() as ctrl:
    #     ctrl.initialize(home=True, enable_closed_loop=True)
    #     ctrl.move_open_loop(step_size=10_000, duration_s=0.5)


if __name__ == "__main__":
    main()
