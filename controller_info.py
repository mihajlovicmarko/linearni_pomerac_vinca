import logging

from kinesis_utils import (
    analyze_controller_info,
    connect_first_device,
    disconnect_device,
    probe_controller_info,
    save_controller_info,
)

logger = logging.getLogger(__name__)

def run_controller_info(save_path="controller_info.txt"):
    dev = connect_first_device()
    try:
        info = probe_controller_info(dev)
        analyze_controller_info(info)
        saved_to = save_controller_info(info, save_path)
        logger.info("Saved controller info to: %s", saved_to)
        return info
    finally:
        disconnect_device(dev)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_controller_info()
