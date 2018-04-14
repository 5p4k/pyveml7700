from cmd_defs import *
from enum import IntEnum
import time
from math import fabs
import smbus2


_HUMAN_READABLE_LUX = {
    0: 'Ideal black body',
    1e-6: 'Absolute threshold of vision',
    0.0004: 'Darkest sky',
    0.001: 'Night sky',
    0.0014: 'Typical photographic scene lit by full moon',
    0.005: 'Approximate scotopic/mesopic threshold',
    0.04: 'Phosphorescent markings on a watch dial after 1h in the dark',
    2: 'Floodlit buildings, monuments, and fountains',
    5: 'Approximate mesopic/photopic threshold',
    25: 'Typical photographic scene at sunrise or sunset',
    30: 'Green electroluminescent source',
    55: 'Standard SMPTE cinema screen luminance',
    80: 'Monitor white in the sRGB reference viewing environment',
    250: 'Peak luminance of a typical LCD monitor',
    700: 'Typical photographic scene on overcast day',
    2000: 'Average cloudy sky',
    2500: 'Moon surface',
    5000: 'Typical photographic scene in full sunlight',
    7000: 'Average clear sky',
    1e4: 'White illuminated cloud',
    1.2e4: 'Fluorescent lamp',
    7.5e4: 'Low pressure sodium-vapor lamp',
    1.3e5: 'Frosted incandescent light bulb',
    6e5: 'Solar disk at horizon',
    7e6: 'Filament of a clear incandescent lamp',
    1e8: 'Possible retinal damage',
    1e9: 'Solar disk at noon'
}


class PowerStatus(IntEnum):
    PWR_ON = 0
    PWR_SAVE_1 = 1  # Must be 1
    PWR_SAVE_2 = 2  # Must be 2
    PWR_SAVE_3 = 3  # Must be 3
    PWR_SAVE_4 = 4  # Must be 4
    PWR_OFF = 5


class ThresholdEvent(IntEnum):
    NONE = 0
    LOW = 1
    HIGH = 2
    BOTH = LOW | HIGH


class SamplingPerformance(Enum):
    UPPER_END = 'upper_end'
    SWEET = 'sweet'
    LOWER_END = 'lower_end'


class VEML7700Controller:

    MAX_RESOLUTION_LUX = 0.0036      # At 800ms integration time, 2x gain
    MIN_OVERFLOW_VALUE_LUX = 236.  # Same
    MAX_GAIN = ALSGain.GAIN_DOUBLE.friendly_value
    MIN_GAIN = ALSGain.GAIN_EIGTH.friendly_value
    MIN_INTEGRATION_TIME = ALSIntegrationTime.IT_25MS.friendly_value
    MAX_INTEGRATION_TIME = ALSIntegrationTime.IT_800MS.friendly_value
    MIN_POWER_SAVING_REFRESH_TIME_OVERHEAD_MS = 500
    MAX_OUTPUT = 0xFFFF
    HIGH_LUX_THRESHOLD = 100.

    @staticmethod
    def high_lux_correction_formula(x):
        # Yes python does the power before the multiplication
        return 6.0135e-13 * x ** 4 - 9.3924e-09 * x ** 3 + 8.1488e-5 * x ** 2 + 1.0023 * x

    @property
    def estimated_refresh_time(self):
        if self.power_status is PowerStatus.PWR_ON or self.power_status is PowerStatus.PWR_OFF:
            return self.integration_time
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
        noncorrected_lux = self.output * self.lux_resolution
        if noncorrected_lux > self.__class__.HIGH_LUX_THRESHOLD:
            return self.__class__.high_lux_correction_formula(noncorrected_lux)
        return noncorrected_lux

    @property
    def threshold_event(self):
        return self._threshold_event

    @property
    def sampling_performance(self):
        if self.output < 100 and \
                (self.gain < self.__class__.MAX_GAIN or self.integration_time < self.__class__.MAX_INTEGRATION_TIME):
            return SamplingPerformance.LOWER_END
        elif self.output > 10000 and \
                (self.gain > self.__class__.MIN_GAIN or self.integration_time > self.__class__.MIN_INTEGRATION_TIME):
            return SamplingPerformance.UPPER_END
        return SamplingPerformance.SWEET

    def calibrate(self):
        _DEFAULT_INTEGRATION_TIME = 100
        self.refresh()
        while self.sampling_performance is not SamplingPerformance.SWEET:
            if self.sampling_performance is SamplingPerformance.UPPER_END:
                if self.integration_time > _DEFAULT_INTEGRATION_TIME:
                    self.decrease_integration_time()
                elif self.gain > self.__class__.MIN_GAIN:
                    self.decrease_gain()
                elif self.integration_time > self.__class__.MIN_INTEGRATION_TIME:
                    self.decrease_integration_time()
                else:
                    break  # No can do
            elif self.sampling_performance is SamplingPerformance.LOWER_END:
                if self.integration_time < _DEFAULT_INTEGRATION_TIME:
                    self.increase_integration_time()
                elif self.gain < self.__class__.MAX_GAIN:
                    self.increase_gain()
                elif self.integration_time < self.__class__.MAX_INTEGRATION_TIME:
                    self.increase_integration_time()
                else:
                    break  # No can do
            else:
                break  # Wat?
            self.refresh()

    @property
    def human_readable_lux(self):
        return _HUMAN_READABLE_LUX.get(min(_HUMAN_READABLE_LUX.keys(), key=lambda val: fabs(val - self.lux)))

    def poll_threshold_event(self):
        if not self.threshold_enabled:
            return None
        cmd = cmd_get_interrupt_status()
        status = cmd_get_interrupt_status(cmd(self._bus, DEVICE_ADDRESS))
        if status is ThresholdInterrupt.INT_TH_BOTH:
            self._threshold_event = ThresholdEvent.BOTH
        elif status is ThresholdInterrupt.INT_TH_HIGH:
            self._threshold_event = ThresholdEvent.HIGH
        elif status is ThresholdInterrupt.INT_TH_LOW:
            self._threshold_event = ThresholdEvent.LOW
        elif status is ThresholdInterrupt.INT_TH_NONE:
            self._threshold_event = ThresholdEvent.NONE
        return self._threshold_event

    def increase_gain(self):
        if self.gain < self.__class__.MAX_GAIN:
            new_gain = self.gain * 2
            # Gain skips 1/2
            if abs(new_gain - 0.5) < 0.001:
                new_gain *= 2
            self.gain = new_gain

    def decrease_gain(self):
        if self.gain > self.__class__.MIN_GAIN:
            new_gain = self.gain / 2
            # Gain skips 1/2
            if abs(new_gain - 0.5) < 0.001:
                new_gain /= 2
            self.gain = new_gain

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

    def refresh(self, refresh_output=True, refresh_white_output=False, cycle_power=True, wait_sampling=True):
        if cycle_power and self.power_status is PowerStatus.PWR_ON or self.power_status is PowerStatus.PWR_OFF:
            self.power_status = PowerStatus.PWR_OFF
            self.power_status = PowerStatus.PWR_ON
        if wait_sampling:
            time.sleep(self.estimated_refresh_time / 1000.)
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
        self._als_output = cmd_get_als_high_resolution_output_data(cmd(self._bus, DEVICE_ADDRESS))

    def _get_white_output(self):
        cmd = cmd_get_white_channel_output_data()
        self._white_output = cmd_get_white_channel_output_data(cmd(self._bus, DEVICE_ADDRESS))

    def __init__(self, bus):
        if not isinstance(bus, smbus2.SMBus):
            bus = smbus2.SMBus(bus)
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
