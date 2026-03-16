import logging
import clr
import os
import sys
import time
from ctypes import WinDLL, c_char_p, c_int, c_uint32, create_string_buffer


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_KINESIS_PATH = os.path.join(PROJECT_ROOT, "Dependencies", "Kinesis")
FALLBACK_KINESIS_PATH = r"C:\Program Files\Thorlabs\Kinesis"
KINESIS_PATH = os.environ.get("KINESIS_PATH", PROJECT_KINESIS_PATH)
if "KINESIS_PATH" in os.environ:
    KINESIS_SOURCE = "env"
else:
    KINESIS_SOURCE = "project-relative"
if not os.path.isdir(KINESIS_PATH):
    KINESIS_PATH = FALLBACK_KINESIS_PATH
    KINESIS_SOURCE = "global-fallback"

os.environ["PATH"] = KINESIS_PATH + ";" + os.environ.get("PATH", "")
if KINESIS_PATH not in sys.path:
    sys.path.append(KINESIS_PATH)

clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.Benchtop.PiezoCLI")
clr.AddReference("Thorlabs.MotionControl.GenericPiezoCLI")

from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
from Thorlabs.MotionControl.Benchtop.PiezoCLI.PDXC2 import (
    InertiaStageController,
    OpenLoopMoveParams,
    PDXC2TravelDirection,
)
from Thorlabs.MotionControl.GenericPiezoCLI.Piezo import PiezoControlModeTypes

logger = logging.getLogger(__name__)

_KINESIS_SOURCE_LOGGED = False
_PIEZO_DLL = None


def log_kinesis_dependency_source(log=None, once=True):
    global _KINESIS_SOURCE_LOGGED
    if once and _KINESIS_SOURCE_LOGGED:
        return

    active_logger = log or logger
    if KINESIS_SOURCE == "global-fallback":
        active_logger.warning("Using global Kinesis dependencies from: %s", KINESIS_PATH)
    else:
        active_logger.info(
            "Using %s Kinesis dependencies from: %s", KINESIS_SOURCE, KINESIS_PATH
        )

    _KINESIS_SOURCE_LOGGED = True

REQUEST_METHODS = [
    "RequestAbnormalMoveDetectionEnabled",
    "RequestAmpOutParameters",
    "RequestClosedLoopParameters",
    "RequestClosedLoopTarget",
    "RequestCurrentPosition",
    "RequestExternalTriggerConfig",
    "RequestExternalTriggerParameters",
    "RequestExternalTriggerTarget",
    "RequestJogParameters",
    "RequestOpenLoopMoveParameters",
    "RequestPositionControlMode",
    "RequestSettings",
    "RequestStageAxisParams",
    "RequestStatus",
    "RequestStatusBits",
]

READ_METHODS = [
    "GetAbnormalMoveDetectionEnabled",
    "GetAmpOutParameters",
    "GetClosedLoopParameters",
    "GetClosedLoopTarget",
    "GetCurrentPosition",
    "GetExternalTriggerConfig",
    "GetExternalTriggerParameters",
    "GetExternalTriggerTarget",
    "GetJogParameters",
    "GetOpenLoopMoveParameters",
    "GetPDXC2Configuration",
    "GetPositionControlMode",
    "GetSettings",
    "GetStageAxisParams",
    "GetStatus",
    "GetStatusBits",
    "IsDeviceAvailable",
    "IsPDXC2SettingsValid",
    "IsSetControlModeActive",
    "IsSettingsInitialized",
    "IsSettingsKnown",
]


def _describe_clr_object(obj):
    lines = []
    lines.append("===== BASIC INFO =====")
    lines.append(f"Python type: {type(obj)}")

    try:
        clr_type = obj.GetType()
        lines.append(f"CLR type: {clr_type}")
        lines.append(f"Assembly: {clr_type.Assembly}")
    except Exception as e:
        lines.append(f"Not a CLR object: {e}")
        return lines

    lines.append("")
    lines.append("===== PROPERTIES =====")
    try:
        for prop in clr_type.GetProperties():
            try:
                val = getattr(obj, prop.Name)
            except Exception as e:
                val = f"<error: {e}>"
            lines.append(f"{prop.Name} ({prop.PropertyType}) = {val}")
    except Exception:
        lines.append("No properties")

    lines.append("")
    lines.append("===== FIELDS =====")
    try:
        for field in clr_type.GetFields():
            try:
                val = getattr(obj, field.Name)
            except Exception as e:
                val = f"<error: {e}>"
            lines.append(f"{field.Name} ({field.FieldType}) = {val}")
    except Exception:
        lines.append("No fields")

    lines.append("")
    lines.append("===== METHODS =====")
    try:
        for m in clr_type.GetMethods():
            lines.append(m.Name)
    except Exception:
        lines.append("No methods")

    lines.append("")
    lines.append("===== PYTHON DIR =====")
    lines.append(str(dir(obj)))
    return lines


def analyze_clr_object(obj):
    for line in _describe_clr_object(obj):
        logger.info(line)

def init_kinesis_path():
    os.environ["PATH"] = KINESIS_PATH + ";" + os.environ.get("PATH", "")
    if KINESIS_PATH not in sys.path:
        sys.path.append(KINESIS_PATH)


def _get_piezo_dll():
    global _PIEZO_DLL
    if _PIEZO_DLL is None:
        dll_path = os.path.join(KINESIS_PATH, "Thorlabs.MotionControl.Benchtop.Piezo.dll")
        _PIEZO_DLL = WinDLL(dll_path)
        _PIEZO_DLL.TLI_ScanEthernetRange.argtypes = [
            c_char_p,
            c_char_p,
            c_int,
            c_int,
            c_char_p,
            c_uint32,
        ]
        _PIEZO_DLL.TLI_ScanEthernetRange.restype = c_int
    return _PIEZO_DLL


def build_device_list(build_attempts=2, build_retry_delay_s=2.0):
    build_attempts = max(1, int(build_attempts))
    for attempt in range(build_attempts):
        DeviceManagerCLI.BuildDeviceList()
        if attempt + 1 < build_attempts:
            time.sleep(build_retry_delay_s)
    return get_device_list()


def get_device_list():
    return [str(device) for device in DeviceManagerCLI.GetDeviceList()]


def scan_ethernet_range(
    start_ip,
    end_ip,
    port_no=40303,
    open_timeout_ms=200,
    buffer_size=4096,
):
    dll = _get_piezo_dll()
    found = create_string_buffer(buffer_size)
    result = dll.TLI_ScanEthernetRange(
        str(start_ip).encode("ascii"),
        str(end_ip).encode("ascii"),
        int(port_no),
        int(open_timeout_ms),
        found,
        buffer_size,
    )
    raw = found.value.decode("ascii", errors="ignore").strip()
    addresses = [item.strip() for item in raw.split(",") if item.strip()]
    return {"result": int(result), "addresses": addresses, "raw": raw}


def connect_first_device(
    poll_ms=250,
    serial_no=None,
    build_attempts=2,
    build_retry_delay_s=2.0,
):
    devices = build_device_list(
        build_attempts=build_attempts,
        build_retry_delay_s=build_retry_delay_s,
    )
    if not devices:
        raise RuntimeError("No Thorlabs devices detected")

    if serial_no is not None:
        serial = str(serial_no)
        if serial not in devices:
            raise RuntimeError(
                f"Requested Thorlabs device '{serial}' not found. "
                f"Detected devices: {devices}"
            )
    else:
        serial = devices[0]

    dev = InertiaStageController.CreateInertiaStageController(serial)
    dev.Connect(serial)
    dev.WaitForSettingsInitialized(5000)
    dev.StartPolling(poll_ms)
    time.sleep(0.5)
    dev.EnableDevice()
    try:
        dev.RequestSettings()
        dev.WaitForSettingsInitialized(5000)
    except Exception:
        pass
    return dev


def disconnect_device(dev):
    if dev is None:
        return
    dev.StopPolling()
    dev.Disconnect(True)


def home_stage(dev):
    logger.info("Homing...")
    dev.Home(0)
    while dev.IsDeviceBusy:
        time.sleep(0.1)
    logger.info("Homed")


def set_open_loop_mode(dev):
    dev.SetPositionControlMode(PiezoControlModeTypes.OpenLoop)


def set_closed_loop_mode(dev):
    dev.SetPositionControlMode(PiezoControlModeTypes.CloseLoop)


def read_position_counts(dev):
    return dev.GetCurrentPosition()


def get_closed_loop_parameters(dev):
    """
    Read and return closed-loop parameters if supported.
    """
    try:
        dev.RequestClosedLoopParameters()
        time.sleep(0.1)
        params = dev.GetClosedLoopParameters()
        return params
    except Exception as e:
        logger.warning("GetClosedLoopParameters failed: %s", e)
        return None


def track_position(dev, duration_s=None, sample_s=0.05, on_sample=None):
    """
    Track position for a fixed duration or until interrupted.
    Returns a list of (t, pos_counts).
    """
    start = time.time()
    samples = []
    while True:
        t = time.time() - start
        pos = read_position_counts(dev)
        samples.append((t, pos))
        if on_sample:
            on_sample(t, pos)
        if duration_s is not None and t >= duration_s:
            break
        time.sleep(sample_s)
    return samples


def move_open_loop(dev, step_size=1, duration_s=0.5, sample_s=0.05):
    if step_size < 0:
        dev.Jog(PDXC2TravelDirection.Reverse, None)
        step_size *= -1

    set_open_loop_mode(dev)

    params = OpenLoopMoveParams()
    params.StepSize = int(step_size)
    dev.SetOpenLoopMoveParameters(params)

    dev.MoveStart()
    try:
        track_position(
            dev,
            duration_s=duration_s,
            sample_s=sample_s,
            on_sample=lambda t, pos: logger.info("t=%.2fs pos=%s counts", t, pos),
        )
    finally:
        dev.MoveStop()


def move_closed_loop_counts(
    dev,
    target_counts,
    tol_counts=50,
    timeout_s=10.0,
    sample_s=0.05,
):
    set_closed_loop_mode(dev)
    get_closed_loop_parameters(dev)
    dev.SetClosedLoopTarget(int(target_counts))

    t0 = time.time()
    while True:
        pos = read_position_counts(dev)
        err = abs(pos - target_counts)
        logger.info("pos=%s counts  err=%s counts", pos, err)
        if err <= tol_counts:
            break
        if time.time() - t0 > timeout_s:
            raise TimeoutError("Move timeout")
        time.sleep(sample_s)


def _call_noarg_method(dev, method_name):
    try:
        attr = getattr(dev, method_name)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    if attr is None:
        return None, "not available"
    if callable(attr):
        try:
            return attr(), None
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if "No method matches given arguments" in msg:
                return None, "requires arguments"
            return None, msg
    return attr, None


def request_controller_info(dev):
    """
    Call all known Request* methods that take no arguments.
    Returns a dict: {method_name: "ok" or error string}.
    """
    results = {}
    for name in REQUEST_METHODS:
        _, err = _call_noarg_method(dev, name)
        results[name] = "ok" if err is None else err
    return results


def read_controller_info(dev):
    """
    Call all known Get*/Is* methods that take no arguments.
    Returns a dict: {method_name: value or error string}.
    """
    results = {}
    for name in READ_METHODS:
        value, err = _call_noarg_method(dev, name)
        results[name] = value if err is None else err
    return results


def probe_controller_info(dev):
    """
    Run all request + read methods and return a combined dict.
    """
    return {
        "requests": request_controller_info(dev),
        "reads": read_controller_info(dev),
    }


def analyze_controller_info(info):
    logger.info("=== REQUEST RESULTS ===")
    for name, result in info["requests"].items():
        logger.info("%s: %s", name, result)

    logger.info("=== READ RESULTS ===")
    for name, result in info["reads"].items():
        logger.info("--- %s ---", name)
        if isinstance(result, str):
            logger.info("%s", result)
        elif isinstance(result, (int, float, bool)):
            logger.info("%s", result)
        else:
            analyze_clr_object(result)


def format_controller_info(info):
    lines = []
    lines.append("=== REQUEST RESULTS ===")
    for name, result in info["requests"].items():
        lines.append(f"{name}: {result}")

    lines.append("")
    lines.append("=== READ RESULTS ===")
    for name, result in info["reads"].items():
        lines.append(f"--- {name} ---")
        if isinstance(result, str):
            lines.append(result)
        elif isinstance(result, (int, float, bool)):
            lines.append(str(result))
        else:
            lines.extend(_describe_clr_object(result))
    return "\n".join(lines)


def save_controller_info(info, path):
    text = format_controller_info(info)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
