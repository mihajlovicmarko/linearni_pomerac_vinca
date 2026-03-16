import argparse
import logging
import socket

from controller_control import PDXC2Controller


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run PDXC2 homing and closed-loop move."
    )
    parser.add_argument(
        "--device-serial",
        default=None,
        help="Thorlabs device serial number to connect to.",
    )
    parser.add_argument(
        "--device-ip",
        default=None,
        help=(
            "Ethernet IP configured in Kinesis for the controller. "
            "Used for clarity/logging; Kinesis still connects by serial number."
        ),
    )
    parser.add_argument(
        "--scan-start-ip",
        default=None,
        help="Start of Ethernet IP scan range to run before connecting.",
    )
    parser.add_argument(
        "--scan-end-ip",
        default=None,
        help="End of Ethernet IP scan range to run before connecting.",
    )
    parser.add_argument(
        "--device-port",
        type=int,
        default=40303,
        help="Ethernet port for the controller (Kinesis default is 40303).",
    )
    parser.add_argument(
        "--open-timeout-ms",
        type=int,
        default=200,
        help="Timeout used for each IP probe during the Ethernet scan.",
    )
    parser.add_argument(
        "--device-build-attempts",
        type=int,
        default=2,
        help="How many times to rebuild the Kinesis device list before connecting.",
    )
    parser.add_argument(
        "--device-build-delay-s",
        type=float,
        default=2.0,
        help="Delay between Kinesis device-list rebuilds for Ethernet discovery.",
    )
    parser.add_argument("--poll-ms", type=int, default=250)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--socket-host",
        default="127.0.0.1",
        help="Host interface for the target command socket server.",
    )
    parser.add_argument(
        "--socket-port",
        type=int,
        default=5050,
        help="TCP port for the target command socket server.",
    )
    parser.add_argument(
        "--listen-for-targets",
        action="store_true",
        help="Keep running and accept target commands over a local TCP socket.",
    )
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
    parser.add_argument(
        "--print-current-position",
        action="store_true",
        help="Read and print the current position before moving.",
    )
    parser.add_argument(
        "--track-position-s",
        type=float,
        default=0.0,
        help="Track current position for this many seconds after the move.",
    )
    parser.add_argument(
        "--track-interval-s",
        type=float,
        default=0.25,
        help="Sampling interval used with --track-position-s.",
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


def resolve_target_counts(ctrl, args, current_counts=None, requested_units=None):
    if requested_units is not None:
        return ctrl.units_to_counts(requested_units)
    if args.target_counts is not None:
        return int(args.target_counts)
    if args.target_units is not None:
        return ctrl.units_to_counts(args.target_units)
    if current_counts is None:
        current_counts = ctrl.get_current_position()
    return current_counts + ctrl.units_to_counts(args.delta_units)


def move_to_target(ctrl, target_counts, args):
    logging.info(
        "Target position: %s counts (%.6f units)",
        target_counts,
        ctrl.counts_to_units(target_counts),
    )
    ctrl.move_closed_loop_counts(
        target_counts=target_counts,
        tol_counts=args.cl_tol_counts,
        timeout_s=args.cl_timeout_s,
        start_timeout_s=args.cl_start_timeout_s,
        motion_thresh_counts=args.cl_motion_thresh_counts,
    )


def handle_socket_command(ctrl, command, args):
    text = command.strip()
    if not text:
        return "ERR empty command"

    parts = text.split()
    op = parts[0].lower()

    if op in {"quit", "exit", "shutdown"}:
        return "QUIT"

    if op in {"pos", "position", "current"}:
        counts = ctrl.get_current_position()
        return f"OK {counts} {ctrl.counts_to_units(counts):.6f}"

    if op == "move":
        if len(parts) != 2:
            return "ERR usage: move <target_units>"
        target_counts = ctrl.units_to_counts(float(parts[1]))
        move_to_target(ctrl, target_counts, args)
        current = ctrl.get_current_position()
        return f"OK {current} {ctrl.counts_to_units(current):.6f}"

    if op == "move_counts":
        if len(parts) != 2:
            return "ERR usage: move_counts <target_counts>"
        target_counts = int(parts[1])
        move_to_target(ctrl, target_counts, args)
        current = ctrl.get_current_position()
        return f"OK {current} {ctrl.counts_to_units(current):.6f}"

    return "ERR unknown command"


def serve_target_socket(ctrl, args):
    logging.info(
        "Listening for target commands on %s:%s",
        args.socket_host,
        args.socket_port,
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.socket_host, args.socket_port))
        server.listen()
        while True:
            conn, addr = server.accept()
            with conn:
                data = conn.recv(4096)
                if not data:
                    continue
                try:
                    response = handle_socket_command(
                        ctrl,
                        data.decode("utf-8", errors="ignore"),
                        args,
                    )
                except Exception as exc:
                    logging.exception("Socket command failed")
                    response = f"ERR {exc}"
                conn.sendall((response + "\n").encode("utf-8"))
                if response == "QUIT":
                    logging.info("Socket server shutdown requested by %s", addr)
                    break


def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    ctrl = PDXC2Controller(
        poll_ms=args.poll_ms,
        serial_no=args.device_serial,
        device_ip=args.device_ip,
        scan_start_ip=args.scan_start_ip,
        scan_end_ip=args.scan_end_ip,
        device_port=args.device_port,
        open_timeout_ms=args.open_timeout_ms,
        build_attempts=args.device_build_attempts,
        build_retry_delay_s=args.device_build_delay_s,
    )

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
        if args.print_current_position:
            logging.info(
                "Current position: %s counts (%.6f units)",
                current,
                ctrl.counts_to_units(current),
            )
        should_run_initial_move = (
            args.target_counts is not None
            or args.target_units is not None
            or (not args.listen_for_targets and args.delta_units != 0.0)
        )
        if should_run_initial_move:
            target = resolve_target_counts(ctrl, args, current_counts=current)
            move_to_target(ctrl, target, args)
        if args.track_position_s > 0:
            samples = ctrl.track_current_position(
                duration_s=args.track_position_s,
                sample_s=args.track_interval_s,
                as_units=False,
            )
            for index, counts in enumerate(samples, start=1):
                logging.info(
                    "Track sample %s: %s counts (%.6f units)",
                    index,
                    counts,
                    ctrl.counts_to_units(counts),
                )
        if args.listen_for_targets:
            serve_target_socket(ctrl, args)
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
