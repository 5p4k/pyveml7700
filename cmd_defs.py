from enum import Enum
from i2c_cmd import Command, Direction
from math import isclose


DEVICE_ADDRESS = 0x10


def bitpack(offset, length):
    """
    Decorator for Enums that adds a method `pack` to the class, which returns the first `length` bits of the value left
    shifted by `offset`.
    """
    mask = (1 << length) - 1

    def apply(cls):
        def pack(self):
            return (self.value & mask) << offset

        def unpack(value):
            return cls((value >> offset) & mask)
        cls.pack = pack
        cls.unpack = unpack
        return cls
    return apply


@bitpack(11, 2)
class ALSGain(Enum):
    GAIN_UNIT = 0b00
    GAIN_DOUBLE = 0b01
    GAIN_QUARTER = 0b10
    GAIN_EIGTH = 0b11

    @property
    def friendly_value(self):
        if self is ALSGain.GAIN_UNIT:
            return 1
        if self is ALSGain.GAIN_DOUBLE:
            return 2
        if self is ALSGain.GAIN_QUARTER:
            return 1 / 4
        if self is ALSGain.GAIN_EIGTH:
            return 1 / 8
        raise RuntimeError('Unknown instance of enum?')

    @staticmethod
    def parse(gain):
        if isinstance(gain, ALSGain):
            return gain
        if isclose(gain, 1):
            return ALSGain.GAIN_UNIT
        if isclose(gain, 2):
            return ALSGain.GAIN_DOUBLE
        if isclose(gain, 0.25):
            return ALSGain.GAIN_QUARTER
        if isclose(gain, 0.125):
            return ALSGain.GAIN_EIGTH
        raise ValueError('Cannot interpret %s as a gain; valid values: 1, 2, 1/4, 1/8.' % str(gain))


@bitpack(6, 4)
class ALSIntegrationTime(Enum):
    IT_25MS = 0b1100
    IT_50MS = 0b1000
    IT_100MS = 0b0000
    IT_200MS = 0b0001
    IT_400MS = 0b0010
    IT_800MS = 0b0011

    @property
    def friendly_value(self):
        if self is ALSIntegrationTime.IT_25MS:
            return 25
        if self is ALSIntegrationTime.IT_50MS:
            return 50
        if self is ALSIntegrationTime.IT_100MS:
            return 100
        if self is ALSIntegrationTime.IT_200MS:
            return 200
        if self is ALSIntegrationTime.IT_400MS:
            return 400
        if self is ALSIntegrationTime.IT_800MS:
            return 800
        raise RuntimeError('Unknown instance of enum?')

    @staticmethod
    def parse(time):
        if isinstance(time, ALSIntegrationTime):
            return time
        if isclose(time, 25) or isclose(time, 0.025):
            return ALSIntegrationTime.IT_25MS
        if isclose(time, 50) or isclose(time, 0.050):
            return ALSIntegrationTime.IT_50MS
        if isclose(time, 100) or isclose(time, 0.100):
            return ALSIntegrationTime.IT_100MS
        if isclose(time, 200) or isclose(time, 0.200):
            return ALSIntegrationTime.IT_200MS
        if isclose(time, 400) or isclose(time, 0.400):
            return ALSIntegrationTime.IT_400MS
        if isclose(time, 800) or isclose(time, 0.800):
            return ALSIntegrationTime.IT_800MS
        raise ValueError('Cannot interpret %s as integration time; valid values are 25ms, 50ms, 100ms, 200ms, 400ms, '
                         '800ms.' % str(time))


@bitpack(4, 2)
class ALSPersistence(Enum):
    PERS_1 = 0b00
    PERS_2 = 0b01
    PERS_4 = 0b10
    PERS_8 = 0b11

    @property
    def friendly_value(self):
        if self is ALSPersistence.PERS_1:
            return 1
        if self is ALSPersistence.PERS_2:
            return 2
        if self is ALSPersistence.PERS_4:
            return 4
        if self is ALSPersistence.PERS_8:
            return 8
        raise RuntimeError('Unknown instance of enum?')

    @staticmethod
    def parse(persistence):
        if isinstance(persistence, ALSPersistence):
            return persistence
        if isclose(persistence, 1):
            return ALSPersistence.PERS_1
        if isclose(persistence, 2):
            return ALSPersistence.PERS_2
        if isclose(persistence, 4):
            return ALSPersistence.PERS_4
        if isclose(persistence, 8):
            return ALSPersistence.PERS_8
        raise ValueError('Cannot interpret %s as a persistence value; valid values: 1, 2, 4, 8.' % str(persistence))


@bitpack(1, 1)
class ALSInterrupt(Enum):
    INT_DISABLE = 0b0
    INT_ENABLE = 0b1

    @property
    def friendly_value(self):
        if self is ALSInterrupt.INT_DISABLE:
            return False
        if self is ALSInterrupt.INT_ENABLE:
            return True
        raise RuntimeError('Unknown instance of enum?')

    @staticmethod
    def parse(interrupt):
        if isinstance(interrupt, ALSInterrupt):
            return interrupt
        if interrupt is True:
            return ALSInterrupt.INT_ENABLE
        elif interrupt is False:
            return ALSInterrupt.INT_DISABLE
        raise ValueError('Cannot interpret %s as a ALS interrupt toggle; valid values are True and False.' %
                         str(interrupt))


@bitpack(0, 1)
class ALSShutdown(Enum):
    POWER_ON = 0b0
    SHUTDOWN = 0b1

    @property
    def friendly_value(self):
        if self is ALSShutdown.POWER_ON:
            return False
        if self is ALSShutdown.SHUTDOWN:
            return True
        raise RuntimeError('Unknown instance of enum?')

    @staticmethod
    def parse(shutdown):
        if isinstance(shutdown, ALSShutdown):
            return shutdown
        if shutdown is False:
            return ALSShutdown.POWER_ON
        elif shutdown is True:
            return ALSShutdown.SHUTDOWN
        raise ValueError('Cannot interpret %s as a ALS shutdown toggle; valid values are True and False.' %
                         str(shutdown))


@bitpack(1, 2)
class PowerSavingMode(Enum):
    PSM_ONE = 0b00
    PSM_TWO = 0b01
    PSM_THREE = 0b10
    PSM_FOUR = 0b11

    @property
    def friendly_value(self):
        if self is PowerSavingMode.PSM_ONE:
            return 1
        if self is PowerSavingMode.PSM_TWO:
            return 2
        if self is PowerSavingMode.PSM_THREE:
            return 3
        if self is PowerSavingMode.PSM_FOUR:
            return 4
        raise RuntimeError('Unknown instance of enum?')

    @staticmethod
    def parse(pwr_saving_mode):
        if isinstance(pwr_saving_mode, PowerSavingMode):
            return pwr_saving_mode
        if isclose(pwr_saving_mode, 1):
            return PowerSavingMode.PSM_ONE
        if isclose(pwr_saving_mode, 2):
            return PowerSavingMode.PSM_TWO
        if isclose(pwr_saving_mode, 3):
            return PowerSavingMode.PSM_THREE
        if isclose(pwr_saving_mode, 4):
            return PowerSavingMode.PSM_FOUR
        raise ValueError('Cannot interpret %s as a power saving mode; valid values are 1, 2, 3, 4.' %
                         str(pwr_saving_mode))


@bitpack(0, 1)
class PowerSavingToggle(Enum):
    PSM_DISABLE = 0b0
    PSM_ENABLE = 0b1

    @property
    def friendly_value(self):
        if self is PowerSavingToggle.PSM_ENABLE:
            return True
        if self is PowerSavingToggle.PSM_DISABLE:
            return False
        raise RuntimeError('Unknown instance of enum?')

    @staticmethod
    def parse(pwd_saving_toggle):
        if isinstance(pwd_saving_toggle, ALSShutdown):
            return pwd_saving_toggle
        if pwd_saving_toggle is True:
            return PowerSavingToggle.PSM_ENABLE
        elif pwd_saving_toggle is False:
            return PowerSavingToggle.PSM_DISABLE
        raise ValueError('Cannot interpret %s as a ALS power saving toggle; valid values are True and False.' %
                         str(pwd_saving_toggle))


@bitpack(14, 2)
class ThresholdInterrupt(Enum):
    INT_TH_NONE = 0b00
    INT_TH_LOW = 0b10
    INT_TH_HIGH = 0b01
    INT_TH_BOTH = 0b11


def cmd_set_configuration_register(als_gain=ALSGain.GAIN_UNIT, als_integration_time=ALSIntegrationTime.IT_100MS,
                                   als_persistence=ALSPersistence.PERS_1, als_interrupt=ALSInterrupt.INT_DISABLE,
                                   als_shutdown=ALSShutdown.POWER_ON):
    if not isinstance(als_gain, ALSGain):
        raise ValueError('Gain must be one of the provided values.')
    if not isinstance(als_integration_time, ALSIntegrationTime):
        raise ValueError('Integration time must be one of the provided values.')
    if not isinstance(als_persistence, ALSPersistence):
        raise ValueError('Persistance must be one of the provided values.')
    if not isinstance(als_interrupt, ALSInterrupt):
        raise ValueError('Interrupt must be one of the provided values.')
    if not isinstance(als_shutdown, ALSShutdown):
        raise ValueError('Shutdown must be one of the provided values')
    payload = als_gain.pack()
    payload |= als_integration_time.pack()
    payload |= als_persistence.pack()
    payload |= als_interrupt.pack()
    payload |= als_shutdown.pack()
    return Command(code=0x00, payload=payload, direction=Direction.WRITE)


def cmd_set_high_threshold_windows_setting(threshold):
    return Command(code=0x01, payload=(0xFFFF & int(threshold)), direction=Direction.WRITE)


def cmd_set_low_threshold_windows_setting(threshold):
    return Command(code=0x02, payload=(0xFFFF & int(threshold)), direction=Direction.WRITE)


def cmd_set_power_saving_mode(pwr_saving_mode=PowerSavingMode.PSM_ONE, pwr_saving_toggle=PowerSavingToggle.PSM_DISABLE):
    if not isinstance(pwr_saving_mode, PowerSavingMode):
        raise ValueError('Power saving mode must be one of the provided values.')
    if not isinstance(pwr_saving_toggle, PowerSavingToggle):
        raise ValueError('Power saving toggle must be one of the provided values.')
    return Command(code=0x03, payload=pwr_saving_mode.pack() | pwr_saving_toggle.pack(), direction=Direction.WRITE)


def cmd_get_als_high_resolution_output_data(cmd=None):
    _CODE = 0x04
    if cmd is None:
        return Command(code=_CODE, direction=Direction.READ)
    if not isinstance(cmd, Command):
        raise ValueError('Not a command.')
    if not cmd.direction == Direction.READ:
        raise ValueError('Not a read command.')
    if not cmd.code == _CODE:
        raise ValueError('Not a read ALS data command.')
    return cmd.payload


def cmd_get_white_channel_output_data(cmd=None):
    _CODE = 0x05
    if cmd is None:
        return Command(code=_CODE, direction=Direction.READ)
    if not isinstance(cmd, Command):
        raise ValueError('Not a command.')
    if not cmd.direction == Direction.READ:
        raise ValueError('Not a read command.')
    if not cmd.code == _CODE:
        raise ValueError('Not a read white channel command.')
    return cmd.payload


def cmd_get_interrupt_status(cmd=None):
    _CODE = 0x06
    if cmd is None:
        return Command(code=_CODE, direction=Direction.READ)
    if not isinstance(cmd, Command):
        raise ValueError('Not a command.')
    if not cmd.direction == Direction.READ:
        raise ValueError('Not a read command.')
    if not cmd.code == _CODE:
        raise ValueError('Not a threshold interrupt command.')
    return ThresholdInterrupt.unpack(cmd.payload)
