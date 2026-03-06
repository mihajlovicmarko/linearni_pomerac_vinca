import logging
import time

import kinesis_utils as ku

from Thorlabs.MotionControl.Benchtop.PiezoCLI.PDXC2 import (
    ClosedLoopParams,
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
from System import Convert


class PDXC2Controller:
    def __init__(self, poll_ms=250, auto_connect=True, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.poll_ms = poll_ms
        self.auto_connect = auto_connect
        self.dev = None

        # Defaults from controller_info.txt
        self.amp_out = {
            "ForwardAmplitude": 100,
            "ReverseAmplitude": 100,
            "Mode": AmpOutParameters.AmpOutModes.EnableReverse,
        }
        self.closed_loop = {
            "Acceleration": 8_000_000,
            "Differential": 4000,
            "Integral": 100,
            "Proportional": 4096,
            "RefSpeed": 800_000,
        }
        self.jog = {
            "ClosedLoopAcceleration": 8_000_000,
            "ClosedLoopSpeed": 800_000,
            "ClosedLoopStepSize": 1_000_000,
            "OpenLoopAcceleration": 1000,
            "OpenLoopStepRate": 2000,
            "OpenLoopStepSize": 2000,
            "Mode": JogParameters.JogModes.Step,
        }
        self.open_loop_move = {
            "StepSize": 10_000,
        }
        self.trigger = {
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

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()

    def connect(self):
        if self.dev is None:
            ku.log_kinesis_dependency_source(self.logger, once=True)
            self.dev = ku.connect_first_device(poll_ms=self.poll_ms)
        return self.dev

    def disconnect(self):
        if self.dev is not None:
            ku.disconnect_device(self.dev)
        self.dev = None

    def initialize(self, home=True, enable_closed_loop=True):
        self.ensure_settings()
        if home:
            self.home_closed_loop()
        self.apply_all_parameters(enable_closed_loop=enable_closed_loop)
        return self

    def _require_dev(self):
        if self.dev is None:
            if self.auto_connect:
                self.connect()
            else:
                raise RuntimeError("Device not connected")
        return self.dev

    @staticmethod
    def to_decimal(value):
        try:
            return Convert.ToDecimal(value)
        except Exception:
            return Convert.ToDecimal(str(value))

    @staticmethod
    def _merge_params(base, overrides):
        values = dict(base)
        if overrides:
            values.update(overrides)
        return values

    @staticmethod
    def _sign(x):
        return -1 if x < 0 else 1

    def ensure_settings(self, timeout_ms=5000):
        dev = self._require_dev()
        try:
            dev.RequestSettings()
            dev.WaitForSettingsInitialized(timeout_ms)
        except Exception:
            pass

    def request_current_position(self, wait_s=0.1):
        dev = self._require_dev()
        try:
            dev.RequestCurrentPosition()
            time.sleep(wait_s)
        except Exception:
            pass

    def get_current_position(self, request=True, wait_s=0.1):
        dev = self._require_dev()
        if request:
            self.request_current_position(wait_s=wait_s)
        return dev.GetCurrentPosition()

    def read_control_mode(self):
        dev = self._require_dev()
        try:
            dev.RequestPositionControlMode()
            time.sleep(0.1)
        except Exception:
            pass
        try:
            return dev.GetPositionControlMode()
        except Exception:
            return None

    def try_set_control_mode(self, mode, verify=True):
        dev = self._require_dev()
        try:
            dev.SetPositionControlMode(mode)
        except Exception:
            return False
        if not verify:
            return True
        current = self.read_control_mode()
        if current is None:
            return True
        if current != mode:
            self.logger.warning(
                "Control mode reported as %s after setting %s", current, mode
            )
        return current == mode

    def is_closed_loop_supported(self):
        ok = self.try_set_control_mode(PiezoControlModeTypes.CloseLoop, verify=False)
        try:
            self._require_dev().SetPositionControlMode(PiezoControlModeTypes.OpenLoop)
        except Exception:
            pass
        return ok

    def home_closed_loop(self, timeout_s=60.0, start_timeout_s=2.0):
        dev = self._require_dev()
        self.logger.info("Starting closed-loop home...")
        try:
            dev.EnableDevice()
        except Exception:
            pass
        self.try_set_control_mode(PiezoControlModeTypes.CloseLoop, verify=False)
        try:
            dev.RequestStatusBits()
            time.sleep(0.1)
            self.logger.debug("StatusBits: %s", dev.GetStatusBits())
        except Exception as e:
            self.logger.warning("StatusBits read failed: %s", e)

        dev.Home(0)

        t0 = time.time()
        started = False
        while time.time() - t0 < start_timeout_s:
            if dev.IsDeviceBusy:
                started = True
                break
            time.sleep(0.05)

        if not started:
            self.logger.warning("Home did not start (device not busy).")
            return False

        while dev.IsDeviceBusy:
            if time.time() - t0 > timeout_s:
                raise TimeoutError("Closed-loop home timeout")
            time.sleep(0.1)

        self.logger.info("Closed-loop home complete.")
        return True

    def set_abnormal_move_detection(self, enabled=True):
        self._require_dev().SetAbnormalMoveDetectionEnabled(bool(enabled))

    def apply_amp_out_parameters(self, overrides=None):
        dev = self._require_dev()
        self.amp_out = self._merge_params(self.amp_out, overrides)

        params = AmpOutParameters()
        params.ForwardAmplitude = int(self.amp_out["ForwardAmplitude"])
        params.ReverseAmplitude = int(self.amp_out["ReverseAmplitude"])
        params.Mode = self.amp_out["Mode"]
        dev.SetAmpOutParameters(params)
        return params

    def apply_closed_loop_parameters(self, overrides=None):
        dev = self._require_dev()
        self.closed_loop = self._merge_params(self.closed_loop, overrides)

        params = ClosedLoopParams()
        params.Acceleration = int(self.closed_loop["Acceleration"])
        params.Differential = int(self.closed_loop["Differential"])
        params.Integral = int(self.closed_loop["Integral"])
        params.Proportional = int(self.closed_loop["Proportional"])
        params.RefSpeed = int(self.closed_loop["RefSpeed"])
        dev.SetClosedLoopParameters(params)
        return params

    def apply_jog_parameters(self, overrides=None):
        dev = self._require_dev()
        self.jog = self._merge_params(self.jog, overrides)

        params = JogParameters()
        params.ClosedLoopAcceleration = int(self.jog["ClosedLoopAcceleration"])
        params.ClosedLoopSpeed = int(self.jog["ClosedLoopSpeed"])
        params.ClosedLoopStepSize = int(self.jog["ClosedLoopStepSize"])
        params.OpenLoopAcceleration = int(self.jog["OpenLoopAcceleration"])
        params.OpenLoopStepRate = int(self.jog["OpenLoopStepRate"])
        params.OpenLoopStepSize = int(self.jog["OpenLoopStepSize"])
        params.Mode = self.jog["Mode"]
        dev.SetJogParameters(params)
        return params

    def apply_open_loop_move_parameters(self, overrides=None):
        dev = self._require_dev()
        self.open_loop_move = self._merge_params(self.open_loop_move, overrides)

        params = OpenLoopMoveParams()
        params.StepSize = int(self.open_loop_move["StepSize"])
        dev.SetOpenLoopMoveParameters(params)
        return params

    def apply_trigger_parameters(self, overrides=None):
        dev = self._require_dev()
        self.trigger = self._merge_params(self.trigger, overrides)

        params = TriggerParameters()
        params.AnalogOutOffset = self.to_decimal(self.trigger["AnalogOutOffset"])
        params.AnalogOutGain = self.to_decimal(self.trigger["AnalogOutGain"])
        params.AnalogInOffset = self.to_decimal(self.trigger["AnalogInOffset"])
        params.AnalogInGain = self.to_decimal(self.trigger["AnalogInGain"])
        params.RisePosition2 = int(self.trigger["RisePosition2"])
        params.RisePosition1 = int(self.trigger["RisePosition1"])
        params.FallPosition2 = int(self.trigger["FallPosition2"])
        params.FallPosition1 = int(self.trigger["FallPosition1"])
        params.FallFixedStep = int(self.trigger["FallFixedStep"])
        params.RiseFixedStep = int(self.trigger["RiseFixedStep"])
        dev.SetExternalTriggerParameters(params)
        dev.SetExternalTriggerConfig(self.trigger["Mode"])
        return params

    def apply_all_parameters(self, enable_closed_loop=True):
        self.set_abnormal_move_detection(True)
        self.apply_amp_out_parameters()
        self.apply_jog_parameters()
        self.apply_open_loop_move_parameters()
        self.apply_trigger_parameters()
        if enable_closed_loop:
            self.apply_closed_loop_parameters()

    def get_counts_per_unit(self):
        axis = self._require_dev().GetStageAxisParams()
        return int(axis.CountsPerUnit)

    def units_to_counts(self, units):
        return int(round(units * self.get_counts_per_unit()))

    def counts_to_units(self, counts):
        return counts / float(self.get_counts_per_unit())

    def move_open_loop(self, step_size=10_000, duration_s=0.5, use_jog=True):
        dev = self._require_dev()
        self.try_set_control_mode(PiezoControlModeTypes.OpenLoop, verify=False)

        direction = (
            PDXC2TravelDirection.Reverse
            if step_size < 0
            else PDXC2TravelDirection.Forward
        )
        step_abs = abs(int(step_size))

        self.apply_open_loop_move_parameters({"StepSize": step_abs})
        self.apply_jog_parameters({"OpenLoopStepSize": step_abs})

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
        self,
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
        if kp is None:
            kp = self.closed_loop["Proportional"]
        if ki is None:
            ki = self.closed_loop["Integral"]
        if kd is None:
            kd = self.closed_loop["Differential"]

        kp *= gain_scale
        ki *= gain_scale
        kd *= gain_scale

        if max_step_counts is None:
            max_step_counts = int(self.open_loop_move["StepSize"])

        self.try_set_control_mode(PiezoControlModeTypes.OpenLoop, verify=False)

        t0 = time.time()
        next_log = t0
        prev_err = None
        integral = 0.0

        while True:
            self.request_current_position(wait_s=sample_s)
            pos = self._require_dev().GetCurrentPosition()
            err = target_counts - pos

            if abs(err) <= tol_counts:
                self._require_dev().MoveStop()
                settle_start = time.time()
                settled = True
                while time.time() - settle_start < settle_s:
                    self.request_current_position(wait_s=sample_s)
                    pos = self._require_dev().GetCurrentPosition()
                    err = target_counts - pos
                    if abs(err) > tol_counts:
                        settled = False
                        break
                if settled:
                    self.logger.info("PID target settled: pos=%s err=%s", pos, err)
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
            step *= self._sign(err)

            now = time.time()
            if now >= next_log:
                elapsed = now - t0
                self.logger.info(
                    "t=%.2fs pos=%s err=%s step=%s int=%.2f",
                    elapsed,
                    pos,
                    err,
                    step,
                    integral,
                )
                next_log = now + log_s

            self.move_open_loop(step_size=step, duration_s=pulse_s, use_jog=True)

            if time.time() - t0 > timeout_s:
                self._require_dev().MoveStop()
                self.logger.warning("Open-loop PID timeout.")
                return False

    def move_closed_loop_counts(
        self,
        target_counts,
        tol_counts=50,
        timeout_s=50.0,
        start_timeout_s=1.0,
        motion_thresh_counts=5,
    ):
        dev = self._require_dev()
        if not self.try_set_control_mode(PiezoControlModeTypes.CloseLoop, verify=False):
            self.logger.warning("Closed-loop control mode not supported or not active.")
            return False

        self.apply_closed_loop_parameters()
        dev.SetClosedLoopTarget(int(target_counts))
        try:
            dev.RequestClosedLoopTarget()
            time.sleep(0.1)
            self.logger.debug("Closed-loop target set: %s", dev.GetClosedLoopTarget())
        except Exception:
            pass

        try:
            dev.MoveStart()
        except Exception:
            pass

        self.request_current_position(wait_s=0.05)
        start_pos = dev.GetCurrentPosition()
        moved = False
        t_start = time.time()
        while time.time() - t_start < start_timeout_s:
            self.request_current_position(wait_s=0.05)
            pos = dev.GetCurrentPosition()
            if abs(pos - start_pos) > motion_thresh_counts:
                moved = True
                break
            time.sleep(0.05)

        if not moved:
            self.logger.warning("No closed-loop motion detected. Trying CloseLoopSmooth.")
            self.try_set_control_mode(PiezoControlModeTypes.CloseLoopSmooth, verify=False)
            dev.SetClosedLoopTarget(int(target_counts))
            try:
                dev.MoveStart()
            except Exception:
                pass

        t0 = time.time()
        while True:
            self.request_current_position(wait_s=0.05)
            pos = dev.GetCurrentPosition()
            err = abs(pos - target_counts)
            self.logger.info("pos=%s counts  err=%s counts", pos, err)
            if err <= tol_counts:
                return True
            if time.time() - t0 > timeout_s:
                self.logger.warning("Closed-loop move timeout.")
                return False
            time.sleep(0.05)
