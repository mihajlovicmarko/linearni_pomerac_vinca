import logging
import time

import kinesis_utils as ku

from Thorlabs.MotionControl.Benchtop.PiezoCLI.PDXC2 import (
    JogParameters,
    OpenLoopMoveParams,
    PDXC2TravelDirection,
    TriggerModes,
    TriggerParameters,
)
from Thorlabs.MotionControl.GenericPiezoCLI.Piezo import (
    AmpOutParameters,
    PiezoControlModeTypes,
)
from Thorlabs.MotionControl.Benchtop.PiezoCLI.PDXC2 import ClosedLoopParams
from System import Convert, Decimal

logger = logging.getLogger(__name__)

# Defaults based on controller_info.txt
DEFAULT_AMP_OUT = {
    "ForwardAmplitude": 100,
    "ReverseAmplitude": 100,
    "Mode": AmpOutParameters.AmpOutModes.EnableReverse,
}

DEFAULT_CLOSED_LOOP = {
    "Acceleration": 8_000_000,
    "Differential": 4000,
    "Integral": 100,
    "Proportional": 4096,
    "RefSpeed": 800_000,
}

DEFAULT_JOG = {
    "ClosedLoopAcceleration": 8_000_000,
    "ClosedLoopSpeed": 800_000,
    "ClosedLoopStepSize": 1_000_000,
    "OpenLoopAcceleration": 1000,
    "OpenLoopStepRate": 2000,
    "OpenLoopStepSize": 2000,
    "Mode": JogParameters.JogModes.Step,
}

DEFAULT_OPEN_LOOP_MOVE = {
    "StepSize": 10_000,
}

DEFAULT_TRIGGER = {
    "AnalogOutOffset": 0,
    "AnalogOutGain": 1,
    "AnalogInOffset": 0,
    "AnalogInGain": 1,
    "RisePosition2": 0,
    "RisePosition1": 0,
    "FallPosition2": 0,
    "FallPosition1": 0,
    "FallFixedStep": 0,
    "RiseFixedStep": 0,
    "Mode": TriggerModes.Manual,
}


def to_decimal(value):
    try:
        return Convert.ToDecimal(value)
    except Exception:
        return Convert.ToDecimal(str(value))


def ensure_settings(dev, timeout_ms=5000):
    try:
        dev.RequestSettings()
        dev.WaitForSettingsInitialized(timeout_ms)
    except Exception:
        pass


def home_closed_loop(dev, timeout_s=60.0, start_timeout_s=2.0):
    """
    Closed-loop homing (uses controller's Home routine).
    """
    logger.info("Starting closed-loop home...")
    try:
        dev.EnableDevice()
    except Exception:
        pass
    try_set_control_mode(dev, PiezoControlModeTypes.CloseLoop, verify=False)
    try:
        dev.RequestStatusBits()
        time.sleep(0.1)
        logger.debug("StatusBits: %s", dev.GetStatusBits())
    except Exception as e:
        logger.warning("StatusBits read failed: %s", e)

    dev.Home(0)

    t0 = time.time()
    started = False
    while time.time() - t0 < start_timeout_s:
        if dev.IsDeviceBusy:
            started = True
            break
        time.sleep(0.05)

    if not started:
        logger.warning("Home did not start (device not busy).")
        return False

    while dev.IsDeviceBusy:
        if time.time() - t0 > timeout_s:
            raise TimeoutError("Closed-loop home timeout")
        time.sleep(0.1)

    logger.info("Closed-loop home complete.")
    return True


def request_current_position(dev, wait_s=0.1):
    try:
        dev.RequestCurrentPosition()
        time.sleep(wait_s)
    except Exception:
        pass


def set_abnormal_move_detection(dev, enabled=True):
    dev.SetAbnormalMoveDetectionEnabled(bool(enabled))


def apply_amp_out_parameters(dev, overrides=None):
    values = dict(DEFAULT_AMP_OUT)
    if overrides:
        values.update(overrides)

    params = AmpOutParameters()
    params.ForwardAmplitude = int(values["ForwardAmplitude"])
    params.ReverseAmplitude = int(values["ReverseAmplitude"])
    params.Mode = values["Mode"]
    dev.SetAmpOutParameters(params)
    return params


def apply_closed_loop_parameters(dev, overrides=None):
    values = dict(DEFAULT_CLOSED_LOOP)
    if overrides:
        values.update(overrides)

    params = ClosedLoopParams()
    params.Acceleration = int(values["Acceleration"])
    params.Differential = int(values["Differential"])
    params.Integral = int(values["Integral"])
    params.Proportional = int(values["Proportional"])
    params.RefSpeed = int(values["RefSpeed"])
    dev.SetClosedLoopParameters(params)
    return params


def apply_jog_parameters(dev, overrides=None):
    values = dict(DEFAULT_JOG)
    if overrides:
        values.update(overrides)

    params = JogParameters()
    params.ClosedLoopAcceleration = int(values["ClosedLoopAcceleration"])
    params.ClosedLoopSpeed = int(values["ClosedLoopSpeed"])
    params.ClosedLoopStepSize = int(values["ClosedLoopStepSize"])
    params.OpenLoopAcceleration = int(values["OpenLoopAcceleration"])
    params.OpenLoopStepRate = int(values["OpenLoopStepRate"])
    params.OpenLoopStepSize = int(values["OpenLoopStepSize"])
    params.Mode = values["Mode"]
    dev.SetJogParameters(params)
    return params


def apply_open_loop_move_parameters(dev, overrides=None):
    values = dict(DEFAULT_OPEN_LOOP_MOVE)
    if overrides:
        values.update(overrides)

    params = OpenLoopMoveParams()
    params.StepSize = int(values["StepSize"])
    dev.SetOpenLoopMoveParameters(params)
    return params


def apply_trigger_parameters(dev, overrides=None):
    values = dict(DEFAULT_TRIGGER)
    if overrides:
        values.update(overrides)

    params = TriggerParameters()
    params.AnalogOutOffset = to_decimal(values["AnalogOutOffset"])
    params.AnalogOutGain = to_decimal(values["AnalogOutGain"])
    params.AnalogInOffset = to_decimal(values["AnalogInOffset"])
    params.AnalogInGain = to_decimal(values["AnalogInGain"])
    params.RisePosition2 = int(values["RisePosition2"])
    params.RisePosition1 = int(values["RisePosition1"])
    params.FallPosition2 = int(values["FallPosition2"])
    params.FallPosition1 = int(values["FallPosition1"])
    params.FallFixedStep = int(values["FallFixedStep"])
    params.RiseFixedStep = int(values["RiseFixedStep"])
    dev.SetExternalTriggerParameters(params)
    dev.SetExternalTriggerConfig(values["Mode"])
    return params


def apply_all_parameters(dev, enable_closed_loop=True):
    set_abnormal_move_detection(dev, True)
    apply_amp_out_parameters(dev)
    apply_jog_parameters(dev)
    apply_open_loop_move_parameters(dev)
    apply_trigger_parameters(dev)
    if enable_closed_loop:
        apply_closed_loop_parameters(dev)


def get_counts_per_unit(dev):
    axis = dev.GetStageAxisParams()
    return int(axis.CountsPerUnit)


def units_to_counts(dev, units):
    return int(round(units * get_counts_per_unit(dev)))


def counts_to_units(dev, counts):
    return counts / float(get_counts_per_unit(dev))


def _sign(x):
    return -1 if x < 0 else 1


def read_control_mode(dev):
    try:
        dev.RequestPositionControlMode()
        time.sleep(0.1)
    except Exception:
        pass
    try:
        return dev.GetPositionControlMode()
    except Exception:
        return None


def try_set_control_mode(dev, mode, verify=True):
    try:
        dev.SetPositionControlMode(mode)
    except Exception:
        return False
    if not verify:
        return True
    current = read_control_mode(dev)
    if current is None:
        return True
    if current != mode:
        logger.warning("Control mode reported as %s after setting %s", current, mode)
    return current == mode


def is_closed_loop_supported(dev):
    ok = try_set_control_mode(dev, PiezoControlModeTypes.CloseLoop, verify=False)
    try:
        dev.SetPositionControlMode(PiezoControlModeTypes.OpenLoop)
    except Exception:
        pass
    return ok


def move_open_loop(dev, step_size=10_000, duration_s=0.5, use_jog=True):
    try_set_control_mode(dev, PiezoControlModeTypes.OpenLoop, verify=False)

    direction = (
        PDXC2TravelDirection.Reverse if step_size < 0 else PDXC2TravelDirection.Forward
    )
    step_abs = abs(int(step_size))

    apply_open_loop_move_parameters(dev, {"StepSize": step_abs})
    apply_jog_parameters(dev, {"OpenLoopStepSize": step_abs})

    if use_jog:
        dev.Jog(direction, None)
        time.sleep(duration_s)
        dev.MoveStop()
        return

    try:
        dev.MoveStart(direction)
    except Exception:
        dev.MoveStart()
    time.sleep(duration_s)
    dev.MoveStop()


def move_open_loop_pid(
    dev,
    target_counts,
    kp=None,
    ki=None,
    kd=None,
    tol_counts=50,
    timeout_s=100.0,
    sample_s=0.05,
    pulse_s=0.02,
    min_step_counts=200,
    max_step_counts=None,
    gain_scale=1.0,
    log_s=0.5,
    settle_s=2.0,
):
    """
    PID-like control in open loop using position feedback (if available).
    Uses P/I/D defaults from controller_info.txt unless overridden.
    """
    if kp is None:
        kp = DEFAULT_CLOSED_LOOP["Proportional"]
    if ki is None:
        ki = DEFAULT_CLOSED_LOOP["Integral"]
    if kd is None:
        kd = DEFAULT_CLOSED_LOOP["Differential"]

    kp *= gain_scale
    ki *= gain_scale
    kd *= gain_scale

    if max_step_counts is None:
        max_step_counts = int(DEFAULT_OPEN_LOOP_MOVE["StepSize"])

    try_set_control_mode(dev, PiezoControlModeTypes.OpenLoop, verify=False)

    t0 = time.time()
    next_log = t0
    prev_err = None
    integral = 0.0

    while True:
        request_current_position(dev, wait_s=sample_s)
        pos = dev.GetCurrentPosition()
        err = target_counts - pos

        if abs(err) <= tol_counts:
            dev.MoveStop()
            settle_start = time.time()
            settled = True
            while time.time() - settle_start < settle_s:
                request_current_position(dev, wait_s=sample_s)
                pos = dev.GetCurrentPosition()
                err = target_counts - pos
                if abs(err) > tol_counts:
                    settled = False
                    break
            if settled:
                logger.info("PID target settled: pos=%s err=%s", pos, err)
                return True

        dt = sample_s
        integral += err * dt

        if ki != 0:
            i_limit = max_step_counts / max(abs(ki), 1e-9)
            integral = max(-i_limit, min(i_limit, integral))

        if prev_err is None:
            derivative = 0.0
        else:
            derivative = (err - prev_err) / dt

        output = (kp * err) + (ki * integral) + (kd * derivative)
        prev_err = err

        step = int(min(max_step_counts, max(min_step_counts, abs(output))))
        step *= _sign(err)

        now = time.time()
        if now >= next_log:
            elapsed = now - t0
            logger.info(
                "t=%.2fs pos=%s err=%s step=%s int=%.2f",
                elapsed,
                pos,
                err,
                step,
                integral,
            )
            next_log = now + log_s
        move_open_loop(dev, step_size=step, duration_s=pulse_s, use_jog=True)

        if time.time() - t0 > timeout_s:
            dev.MoveStop()
            logger.warning("Open-loop PID timeout.")
            return False


def move_closed_loop_counts(
    dev,
    target_counts,
    tol_counts=50,
    timeout_s=50.0,
    start_timeout_s=1.0,
    motion_thresh_counts=50,
):
    if not try_set_control_mode(dev, PiezoControlModeTypes.CloseLoop, verify=False):
        logger.warning("Closed-loop control mode not supported or not active.")
        return False

    apply_closed_loop_parameters(dev)
    dev.SetClosedLoopTarget(int(target_counts))
    try:
        dev.RequestClosedLoopTarget()
        time.sleep(0.1)
        logger.debug("Closed-loop target set: %s", dev.GetClosedLoopTarget())
    except Exception:
        pass

    try:
        dev.MoveStart()
    except Exception:
        pass

    request_current_position(dev, wait_s=0.05)
    start_pos = dev.GetCurrentPosition()
    moved = False
    t_start = time.time()
    while time.time() - t_start < start_timeout_s:
        request_current_position(dev, wait_s=0.05)
        pos = dev.GetCurrentPosition()
        if abs(pos - start_pos) > motion_thresh_counts:
            moved = True
            break
        time.sleep(0.05)

    if not moved:
        logger.warning("No closed-loop motion detected. Trying CloseLoopSmooth.")
        try_set_control_mode(dev, PiezoControlModeTypes.CloseLoopSmooth, verify=False)
        dev.SetClosedLoopTarget(int(target_counts))
        try:
            dev.MoveStart()
        except Exception:
            pass

    t0 = time.time()
    while True:
        request_current_position(dev, wait_s=0.05)
        pos = dev.GetCurrentPosition()
        err = abs(pos - target_counts)
        logger.info("pos=%s counts  err=%s counts", pos, err)
        if err <= tol_counts:
            return True
        if time.time() - t0 > timeout_s:
            logger.warning("Closed-loop move timeout.")
            return False
        time.sleep(0.05)


def main():
    dev = ku.connect_first_device()
    try:
        ensure_settings(dev)
        homed = home_closed_loop(dev)
        if not homed:
            logger.warning("Closed-loop home failed to start. Continuing without homing.")

        
        closed_loop_ok = is_closed_loop_supported(dev)
        logger.info("Closed-loop supported: %s", closed_loop_ok)
        apply_all_parameters(dev, enable_closed_loop=closed_loop_ok)

        request_current_position(dev)
        current = dev.GetCurrentPosition()
        logger.info("Current position: %s counts", current)

        if closed_loop_ok:
            delta_units = -10
            delta_counts = units_to_counts(dev, delta_units)
            logger.info(
                "Closed-loop move: +%s units (%s counts)",
                delta_units,
                delta_counts,
            )
            ok = move_closed_loop_counts(dev, current + delta_counts)

            delta_units = +10
            delta_counts = units_to_counts(dev, delta_units)

            ok = move_closed_loop_counts(dev, current + delta_counts)

            if not ok:
                logger.warning("Closed-loop move did not complete.")

        """
        else:
            logger.info("Skipping closed-loop move.")
            pid_target = current + units_to_counts(dev, 0.1)
            move_open_loop_pid(dev, pid_target)
        """
        #step_units = -1
        #step_counts = units_to_counts(dev, step_units)
        #print(f"Open-loop move: step_size={step_units} units ({step_counts} counts)")
        #move_open_loop(dev, step_size=step_counts, duration_s=1.5)
        
    finally:
        ku.disconnect_device(dev)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()
logger = logging.getLogger(__name__)
