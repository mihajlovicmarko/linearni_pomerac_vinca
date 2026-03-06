import argparse
import logging

from controller_control import PDXC2Controller


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run PDXC2 homing and closed-loop move."
    )
    parser.add_argument("--poll-ms", type=int, default=250)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--home", dest="home", action="store_true", default=True)
    parser.add_argument("--no-home", dest="home", action="store_false")
    parser.add_argument(
        "--enable-closed-loop-params",
        dest="enable_closed_loop_params",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--disable-closed-loop-params",
        dest="enable_closed_loop_params",
        action="store_false",
    )
    parser.add_argument(
        "--delta-units",
        type=float,
        default=2.0,
        help="Relative move in stage units.",
    )
    parser.add_argument(
        "--target-units",
        type=float,
        default=None,
        help="Absolute target in stage units (overrides --delta-units).",
    )
    parser.add_argument(
        "--target-counts",
        type=int,
        default=None,
        help="Absolute target in counts (overrides --target-units).",
    )
    parser.add_argument("--cl-tol-counts", type=int, default=50)
    parser.add_argument("--cl-timeout-s", type=float, default=50.0)
    parser.add_argument("--cl-start-timeout-s", type=float, default=1.0)
    parser.add_argument("--cl-motion-thresh-counts", type=int, default=5)
    parser.add_argument(
        "--cl-ref-speed",
        type=int,
        default=None,
        help="Closed-loop reference speed (counts/s).",
    )
    parser.add_argument(
        "--cl-acceleration",
        type=int,
        default=None,
        help="Closed-loop acceleration (counts/s^2).",
    )
    parser.add_argument(
        "--jog-cl-speed",
        type=int,
        default=None,
        help="Jog closed-loop speed (counts/s).",
    )
    parser.add_argument(
        "--jog-ol-step-rate",
        type=int,
        default=None,
        help="Jog open-loop step rate.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    ctrl = PDXC2Controller(poll_ms=args.poll_ms)

    # --- Working example: homing + closed-loop move ---
    try:
        ctrl.connect()
        ctrl.ensure_settings()
        if args.cl_ref_speed is not None:
            ctrl.closed_loop["RefSpeed"] = int(args.cl_ref_speed)
        if args.cl_acceleration is not None:
            ctrl.closed_loop["Acceleration"] = int(args.cl_acceleration)
        if args.jog_cl_speed is not None:
            ctrl.jog["ClosedLoopSpeed"] = int(args.jog_cl_speed)
        if args.jog_ol_step_rate is not None:
            ctrl.jog["OpenLoopStepRate"] = int(args.jog_ol_step_rate)
        if args.home:
            ctrl.home_closed_loop()
        ctrl.apply_all_parameters(enable_closed_loop=args.enable_closed_loop_params)

        current = ctrl.get_current_position()
        if args.target_counts is not None:
            target = int(args.target_counts)
        elif args.target_units is not None:
            target = ctrl.units_to_counts(args.target_units)
        else:
            target = current + ctrl.units_to_counts(args.delta_units)
        ctrl.move_closed_loop_counts(
            target_counts=target,
            tol_counts=args.cl_tol_counts,
            timeout_s=args.cl_timeout_s,
            start_timeout_s=args.cl_start_timeout_s,
            motion_thresh_counts=args.cl_motion_thresh_counts,
        )
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
