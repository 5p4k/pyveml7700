from cmd_defs import *
from enum import IntEnum, Flag, auto


class PowerStatus(IntEnum):
    PWR_ON = 0
    PWR_SAVE_1 = 1  # Must be 1
    PWR_SAVE_2 = 2  # Must be 2
    PWR_SAVE_3 = 3  # Must be 3
    PWR_SAVE_4 = 4  # Must be 4
    PWR_OFF = 5


class ThresholdEvent(Flag):
    NONE = 0
    LOW = 1
    HIGH = 2
    BOTH = LOW | HIGH


class VEML7700Controller:

    MAX_RESOLUTION_LUX = 0.0036      # At 800ms integration time, 2x gain
    MIN_OVERFLOW_VALUE_LUX = 236.  # Same
    MAX_GAIN = ALSGain.GAIN_DOUBLE.friendly_value
    MIN_GAIN = ALSGain.GAIN_EIGTH.friendly_value
    MIN_INTEGRATION_TIME = ALSIntegrationTime.IT_25MS.friendly_value
    MAX_INTEGRATION_TIME = ALSIntegrationTime.IT_800MS.friendly_value
    MIN_POWER_SAVING_REFRESH_TIME_OVERHEAD_MS = 500

    @property
    def estimated_refresh_time(self):
        if self.power_status is PowerStatus.PWR_ON or self.power_status is PowerStatus.PWR_OFF:
            return float('inf')
        power_scale = 1 << (self.power_status.value - 1)
        return self.__class__.MIN_POWER_SAVING_REFRESH_TIME_OVERHEAD_MS * power_scale + self.integration_time

    @property
    def lux_resolution(self):
        gain_scale = int(self.__class__.MAX_GAIN / self.gain)
        time_scale = int(self.__class__.MAX_INTEGRATION_TIME / self.integration_time)
        return self.__class__.MAX_RESOLUTION_LUX * gain_scale * time_scale

    @property
    def lux_overflow_value(self):
        gain_scale = int(self.__class__.MAX_GAIN / self.gain)
        time_scale = int(self.__class__.MAX_INTEGRATION_TIME / self.integration_time)
        return self.__class__.MIN_OVERFLOW_VALUE_LUX * gain_scale * time_scale

    @property
    def lux(self):
        return self.output * self.lux_resolution

    def refresh_lux(self):
        self.refresh()
        return self.lux

    @property
    def threshold_event(self):
        return self._threshold_event

    def poll_threshold_event(self):
        if not self.threshold_enabled:
            return None
        cmd = cmd_get_interrupt_status()
        status = cmd_get_interrupt_status(cmd())
        if status is ThresholdInterrupt.INT_TH_BOTH:
            self._threshold_event = ThresholdEvent.BOTH
        elif status is ThresholdInterrupt.INT_TH_HIGH:
            self._threshold_event = ThresholdEvent.HIGH
        elif status is ThresholdInterrupt.INT_TH_LOW:
            self._threshold_event = ThresholdEvent.LOW
        elif status is ThresholdInterrupt.INT_TH_NONE:
            self._threshold_event = ThresholdEvent.NONE
        return self._threshold_event

    @property
    def is_overflowing(self):
        return self.output >= 0xFFFF

    @property
    def is_underflowing(self):
        return self.output <= 0x0

    def increase_gain(self):
        if self.gain < self.__class__.MAX_GAIN:
            self.gain *= 2

    def decrease_gain(self):
        if self.gain > self.__class__.MIN_GAIN:
            self.gain /= 2

    def increase_integration_time(self):
        if self.integration_time < self.__class__.MAX_INTEGRATION_TIME:
            self.integration_time *= 2

    def decrease_integration_time(self):
        if self.integration_time > self.__class__.MIN_INTEGRATION_TIME:
            self.integration_time /= 2

    @property
    def threshold_enabled(self):
        return self._interrupt.friendly_value

    @threshold_enabled.setter
    def threshold_enabled(self, value):
        value = ALSInterrupt.parse(value)
        if value != self._interrupt:
            self._interrupt = value
            self._configure_register()

    @property
    def gain(self):
        return self._gain.friendly_value

    @gain.setter
    def gain(self, value):
        value = ALSGain.parse(value)
        if value != self._gain:
            self._gain = value
            self._configure_register()

    @property
    def integration_time(self):
        return self._integration_time.friendly_value

    @integration_time.setter
    def integration_time(self, value):
        value = ALSIntegrationTime.parse(value)
        if value != self._integration_time:
            self._integration_time = value
            self._configure_register()

    @property
    def persistence(self):
        return self._persistence.friendly_value

    @persistence.setter
    def persistence(self, value):
        value = ALSPersistence.parse(value)
        if value != self._persistence:
            self._persistence = value
            self._configure_register()

    @property
    def power_status(self):
        if self._shutdown.friendly_value:
            return PowerStatus.PWR_OFF
        if self._power_saving.friendly_value:
            return PowerStatus(self._power_saving_mode.friendly_value)
        return PowerStatus.PWR_ON

    @power_status.setter
    def power_status(self, value):
        value = PowerStatus(value)
        if value is PowerStatus.PWR_ON:
            self._set_shutdown(False)
            self._set_power_saving(False, None)
        elif value is PowerStatus.PWR_OFF:
            self._set_shutdown(True)
            self._set_power_saving(False, None)
        else:
            self._set_shutdown(False)
            self._set_power_saving(True, value.value)

    @property
    def threshold_low(self):
        return self._low_threshold

    @threshold_low.setter
    def threshold_low(self, value):
        if value is not None and value != self._low_threshold:
            self._low_threshold = value
            self._set_low_threshold()

    @property
    def threshold_high(self):
        return self._high_threshold

    @threshold_high.setter
    def threshold_high(self, value):
        if value is not None and value != self._high_threshold:
            self._high_threshold = value
            self._set_high_threshold()

    @property
    def output(self):
        return self._als_output

    @property
    def white_output(self):
        return self._white_output

    def refresh(self, refresh_output=True, refresh_white_output=False):
        if refresh_output:
            self._get_als_output()
        if refresh_white_output:
            self._get_white_output()
        if refresh_output and not refresh_white_output:
            return self.output
        elif refresh_output and refresh_white_output:
            return self.output, self.white_output
        elif refresh_white_output and not refresh_output:
            return self.white_output

    def _set_shutdown(self, shutdown=None):
        shutdown = ALSShutdown.parse(shutdown) if shutdown is not None else self._shutdown
        if self._shutdown != shutdown:
            self._shutdown = shutdown
            self._configure_register()

    def _set_power_saving(self, enabled=None, mode=None):
        enabled = PowerSavingToggle.parse(enabled) if enabled is not None else self._power_saving
        mode = PowerSavingMode.parse(mode) if mode is not None else self._power_saving_mode
        if enabled != self._power_saving or mode != self._power_saving_mode:
            self._power_saving = enabled
            self._power_saving_mode = mode
            self._configure_power_saving()

    def _configure_register(self):
        cmd = cmd_set_configuration_register(self._gain, self._integration_time, self._persistence, self._interrupt,
                                             self._shutdown)
        cmd(self._bus, DEVICE_ADDRESS)

    def _configure_power_saving(self):
        cmd = cmd_set_power_saving_mode(self._power_saving_mode, self._power_saving)
        cmd(self._bus, DEVICE_ADDRESS)

    def _set_low_threshold(self):
        cmd = cmd_set_low_threshold_windows_setting(self._low_threshold)
        cmd(self._bus, DEVICE_ADDRESS)

    def _set_high_threshold(self):
        cmd = cmd_set_high_threshold_windows_setting(self._high_threshold)
        cmd(self._bus, DEVICE_ADDRESS)

    def _get_als_output(self):
        cmd = cmd_get_als_high_resolution_output_data()
        self._als_output = cmd_get_als_high_resolution_output_data(cmd())

    def _get_white_output(self):
        cmd = cmd_get_white_channel_output_data()
        self._white_output = cmd_get_white_channel_output_data(cmd())

    def __init__(self, bus):
        self._bus = bus
        self._gain = ALSGain.GAIN_UNIT
        self._integration_time = ALSIntegrationTime.IT_100MS
        self._persistence = ALSPersistence.PERS_1
        self._interrupt = ALSInterrupt.INT_DISABLE
        self._shutdown = ALSShutdown.POWER_ON
        self._power_saving_mode = PowerSavingMode.PSM_ONE
        self._power_saving = PowerSavingToggle.PSM_DISABLE
        self._low_threshold = None
        self._high_threshold = None
        self._als_output = None
        self._white_output = None
        self._threshold_event = None
