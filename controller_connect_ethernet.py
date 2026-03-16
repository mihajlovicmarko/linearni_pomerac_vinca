import argparse
import json
import logging

import kinesis_utils as ku
from controller_control import PDXC2Controller


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan an Ethernet IP range and connect to a PDXC2 controller."
    )
    parser.add_argument("--start-ip", required=True, help="Start of IP scan range.")
    parser.add_argument("--end-ip", required=True, help="End of IP scan range.")
    parser.add_argument("--port", type=int, default=40303)
    parser.add_argument(
        "--open-timeout-ms",
        type=int,
        default=200,
        help="Timeout used for each IP probe during the Ethernet scan.",
    )
    parser.add_argument(
        "--device-serial",
        default=None,
        help="Optional serial number to require after discovery.",
    )
    parser.add_argument("--poll-ms", type=int, default=250)
    parser.add_argument("--build-attempts", type=int, default=2)
    parser.add_argument("--build-delay-s", type=float, default=2.0)
    parser.add_argument("--read-position", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    scan = ku.scan_ethernet_range(
        start_ip=args.start_ip,
        end_ip=args.end_ip,
        port_no=args.port,
        open_timeout_ms=args.open_timeout_ms,
    )
    logging.info("Ethernet scan result: %s", json.dumps(scan))

    devices = ku.build_device_list(
        build_attempts=args.build_attempts,
        build_retry_delay_s=args.build_delay_s,
    )
    logging.info("Kinesis devices after scan: %s", devices)

    if not devices:
        raise RuntimeError("No Thorlabs devices found after Ethernet scan")

    ctrl = PDXC2Controller(
        poll_ms=args.poll_ms,
        serial_no=args.device_serial,
        build_attempts=args.build_attempts,
        build_retry_delay_s=args.build_delay_s,
    )

    try:
        ctrl.connect()
        ctrl.ensure_settings()
        current_counts = ctrl.get_current_position()
        current_units = ctrl.counts_to_units(current_counts)
        logging.info(
            "Connected controller serial=%s current_position=%s counts (%.6f units)",
            ctrl.serial_no or devices[0],
            current_counts,
            current_units,
        )
        if args.read_position:
            logging.info("Current position read complete.")
    finally:
        ctrl.disconnect()


if __name__ == "__main__":
    main()
