import time
import warnings
import numpy
import numpy.typing
from enum import Enum, auto

import RPi.GPIO as GPIO
import spidev

from display_protocol import Display


class _SpiDevice(Enum):
    PRIMARY = auto()
    SECONDARY = auto()
    BOTH = auto()

class EL133UF1:
    CS_PRIMARY_PIN = 8
    CS_SECONDARY_PIN = 7
    DC_PIN = 25
    RESET_PIN = 17
    BUSY_PIN = 24
    POWER_PIN = 18

    BLACK = 0
    WHITE = 1
    YELLOW = 2
    RED = 3
    # Actually 4 is unused
    BLUE = 4 # Actually 5
    GREEN = 5 # Actually 6

    WIDTH = 1600
    HEIGHT = 1200

    _PSR = 0x00
    _PWR = 0x01
    _POF = 0x02
    _PON = 0x04
    _BTST_N = 0x05
    _BTST_P = 0x06
    _DSLP = 0x07
    _DTM = 0x10
    _DRF = 0x12
    _CDI = 0x50
    _TCON = 0x60
    _TRES = 0x61
    _AN_TM = 0x74
    _AGID = 0x86
    _BUCK_BOOST_VDDN = 0xB0
    _TFT_VCOM_POWER = 0xB1
    _EN_BUF = 0xB6
    _BOOST_VDDP_EN = 0xB7
    _CCSET = 0xE0
    _PWS = 0xE3
    _CMD66 = 0xF0

    _SPI_COMMAND = 0
    _SPI_DATA = 1

    buf: numpy.typing.NDArray[numpy.uint8]

    def __init__(self, *, spi_bus=0, cs_primary_pin=CS_PRIMARY_PIN, cs_secondary_pin=CS_SECONDARY_PIN,
                 dc_pin=DC_PIN, busy_pin=BUSY_PIN, reset_pin=RESET_PIN, power_pin=POWER_PIN):
        """
        :param spi_bus: SPI bus for communication
        :param dc_pin: data/command pin
        :param busy_pin: device busy/wait pin
        :param reset_pin: device reset pin
        :param power_pin: device power on/off pin
        """
        self._gpio = None
        self._spi_bus = None

        self.buf = numpy.zeros((EL133UF1.HEIGHT, EL133UF1.WIDTH), dtype=numpy.uint8)

        self.spi_bus = spi_bus
        self.cs_primary_pin = cs_primary_pin
        self.cs_secondary_pin = cs_secondary_pin
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.busy_pin = busy_pin
        self.power_pin = power_pin

    def show(self):
        """
        Show buffer on display.
        """
        def flatten_buf(buf: numpy.typing.NDArray[numpy.uint8]):
            buf = numpy.fliplr(buf.T).flatten()

            # Remove invalid colors, correct for unused index 4
            buf = numpy.clip(buf, 0, 5)
            buf[buf >= 4] += 1

            return ((buf[::2] << 4) & 0xF0) | (buf[1::2] & 0x0F)

        secondary_buf, primary_buf = numpy.vsplit(self.buf, 2)
        self._update(flatten_buf(primary_buf), flatten_buf(secondary_buf))

    def _setup(self):
        """Set up IO if needed and reset display."""

        if self._gpio is None:
            self._gpio = GPIO
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setwarnings(False)
            self._gpio.setup(self.cs_primary_pin, self._gpio.OUT, initial=self._gpio.HIGH, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.cs_secondary_pin, self._gpio.OUT, initial=self._gpio.HIGH, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.dc_pin, self._gpio.OUT, initial=self._gpio.LOW, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.reset_pin, self._gpio.OUT, initial=self._gpio.HIGH, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.busy_pin, self._gpio.IN, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.power_pin, self._gpio.OUT, initial=self._gpio.HIGH, pull_up_down=self._gpio.PUD_OFF)

        if self._spi_bus is None:
            self._spi_bus = spidev.SpiDev()
            self._spi_bus.open(self.spi_bus, 0)
            self._spi_bus.max_speed_hz = 5000000
            self._spi_bus.no_cs = True

        self._gpio.output(self.reset_pin, self._gpio.LOW)
        time.sleep(0.1)
        self._gpio.output(self.reset_pin, self._gpio.HIGH)
        time.sleep(0.1)
        self._gpio.output(self.reset_pin, self._gpio.LOW)
        time.sleep(0.1)
        self._gpio.output(self.reset_pin, self._gpio.HIGH)

        self._busy_wait(1.0)

        # Sending init commands to display
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._AN_TM, [0xC0, 0x1C, 0x1C, 0xCC, 0xCC, 0xCC, 0x15, 0x15, 0x55])
        self._send_command(_SpiDevice.BOTH, EL133UF1._CMD66, [0x49, 0x55, 0x13, 0x5D, 0x05, 0x10])
        self._send_command(_SpiDevice.BOTH, EL133UF1._PSR, [0xDF, 0x69])
        self._send_command(_SpiDevice.BOTH, EL133UF1._CDI, 0xF7)
        self._send_command(_SpiDevice.BOTH, EL133UF1._TCON, [0x03, 0x03])
        self._send_command(_SpiDevice.BOTH, EL133UF1._AGID, 0x10)
        self._send_command(_SpiDevice.BOTH, EL133UF1._PWS, 0x22)
        self._send_command(_SpiDevice.BOTH, EL133UF1._CCSET, 0x01)
        self._send_command(_SpiDevice.BOTH, EL133UF1._TRES, [0x04, 0xB0, 0x03, 0x20])
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._PWR, [0x0F, 0x00, 0x28, 0x2C, 0x28, 0x38])
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._EN_BUF, 0x07)
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._BTST_P, [0xE8, 0x28])
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._BOOST_VDDP_EN, 0x01)
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._BTST_N, [0xE8, 0x28])
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._BUCK_BOOST_VDDN, 0x01)
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._TFT_VCOM_POWER, 0x02)

    def _busy_wait(self, timeout):
        if self._gpio.input(self.busy_pin):
            warnings.warn(f'Busy Wait: Held high. Waiting for {timeout:0.2f}s', stacklevel=2)
            time.sleep(timeout)
            return

        t_start = time.time()
        while not self._gpio.input(self.busy_pin):
            time.sleep(0.01)
            if time.time() - t_start >= timeout:
                warnings.warn(f'Busy Wait: Timed out after {time.time() - t_start:0.2f}s', stacklevel=2)
                return

    def _update(self, primary_buf, secondary_buf):
        self._setup()

        self._send_command(_SpiDevice.PRIMARY, EL133UF1._DTM, primary_buf)
        self._send_command(_SpiDevice.SECONDARY, EL133UF1._DTM, secondary_buf)

        self._send_command(_SpiDevice.BOTH, EL133UF1._PON)
        self._busy_wait(0.4)

        self._send_command(_SpiDevice.BOTH, EL133UF1._DRF, 0x00)
        self._busy_wait(45.0)

        self._send_command(_SpiDevice.BOTH, EL133UF1._POF, 0x00)
        self._busy_wait(0.4)

        self._sleep()

    def _spi_write(self, dc: int, data):
        self._gpio.output(self.dc_pin, dc)
        self._spi_bus.writebytes2(data)

    def _send_command(self, device: _SpiDevice, command, data=None):
        match device:
            case _SpiDevice.PRIMARY:
                self._gpio.output(self.cs_primary_pin, 0)
            case _SpiDevice.SECONDARY:
                self._gpio.output(self.cs_secondary_pin, 0)
            case _SpiDevice.BOTH:
                self._gpio.output(self.cs_primary_pin, 0)
                self._gpio.output(self.cs_secondary_pin, 0)

        self._spi_write(EL133UF1._SPI_COMMAND, [command])

        if data is not None:
            try:
                _ = iter(data)
            except TypeError:
                data = [data]
            self._spi_write(EL133UF1._SPI_DATA, data)

        self._gpio.output(self.cs_primary_pin, 1)
        self._gpio.output(self.cs_secondary_pin, 1)

    def _sleep(self):
        self._send_command(_SpiDevice.BOTH, EL133UF1._DSLP, 0xA5)

def init_display(_) -> Display:
    return EL133UF1()
