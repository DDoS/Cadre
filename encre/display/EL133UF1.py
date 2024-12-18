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
    DC_PIN = 22
    RESET_PIN = 27
    BUSY_PIN = 17

    BLACK = 0
    WHITE = 1
    YELLOW = 2
    RED = 3
    # Actually 4 is unused
    BLUE = 4 # Actually 5
    GREEN = 5 # Actually 6

    WIDTH = 1200
    HEIGHT = 1600

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

    def __init__(self, *, spi_bus=0, dc_pin=DC_PIN, busy_pin=BUSY_PIN, reset_pin=RESET_PIN):
        """
        :param spi_bus: SPI bus for communication
        :param dc_pin: data/command pin
        :param busy_pin: device busy/wait pin
        :param reset_pin: device reset pin
        """
        self._gpio = None
        self._spi_primary = None
        self._spi_secondary = None

        self.buf = numpy.zeros((EL133UF1.HEIGHT, EL133UF1.WIDTH), dtype=numpy.uint8)

        self.spi_bus = spi_bus
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.busy_pin = busy_pin

    def show(self):
        """
        Show buffer on display.

        :param busy_wait: If True, wait for display update to finish before returning.
        """
        buf = self.buf.flatten()

        # Remove invalid colors, correct for unused index 4
        buf = numpy.clip(buf, 0, 5)
        buf[buf >= 4] += 1

        buf = ((buf[::2] << 4) & 0xF0) | (buf[1::2] & 0x0F)

        self._update(buf)

    def _setup(self):
        """Set up IO if needed and reset display."""

        if self._gpio is None:
            self._gpio = GPIO
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setwarnings(False)
            self._gpio.setup(self.dc_pin, self._gpio.OUT, initial=self._gpio.LOW, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.reset_pin, self._gpio.OUT, initial=self._gpio.HIGH, pull_up_down=self._gpio.PUD_OFF)
            self._gpio.setup(self.busy_pin, self._gpio.IN, pull_up_down=self._gpio.PUD_OFF)

        if self._spi_primary is None:
            self._spi_primary = spidev.SpiDev()
            self._spi_primary.open(self.spi_bus, 0)
            self._spi_primary.max_speed_hz = 5000000

        if self._spi_secondary is None:
            self._spi_secondary = spidev.SpiDev()
            self._spi_secondary.open(self.spi_bus, 1)
            self._spi_secondary.max_speed_hz = 5000000

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
            warnings.warn(f'Busy Wait: Held high. Waiting for {timeout:0.2f}s')
            time.sleep(timeout)
            return

        t_start = time.time()
        while not self._gpio.input(self.busy_pin):
            time.sleep(0.01)
            if time.time() - t_start >= timeout:
                warnings.warn(f'Busy Wait: Timed out after {time.time() - t_start:0.2f}s')
                return

    def _update(self, buf):
        self._setup()

        half_height: int = buf.shape[0] // 2
        self._send_command(_SpiDevice.PRIMARY, EL133UF1._DTM, self.buf[:half_height])
        self._send_command(_SpiDevice.SECONDARY, EL133UF1._DTM, self.buf[half_height:])

        self._send_command(_SpiDevice.BOTH, EL133UF1._PON)
        self._busy_wait(0.4)

        self._send_command(_SpiDevice.BOTH, EL133UF1._DRF, 0x00)
        self._busy_wait(45.0)

        self._send_command(_SpiDevice.BOTH, EL133UF1._POF, 0x00)
        self._busy_wait(0.4)

        self._sleep()

    def _spi_write(self, device: _SpiDevice, dc: int, data):
        self._gpio.output(self.dc_pin, dc)
        match device:
            case _SpiDevice.PRIMARY:
                self._spi_primary.writebytes2(data)
            case _SpiDevice.SECONDARY:
                self._spi_secondary.writebytes2(data)
            case _SpiDevice.BOTH:
                self._spi_primary.writebytes2(data)
                self._spi_secondary.writebytes2(data)

    def _send_command(self, device: _SpiDevice, command, data=None):
        self._spi_write(device, EL133UF1._SPI_COMMAND, [command])
        if data is not None:
            self._send_data(device, data)

    def _send_data(self, device: _SpiDevice, data):
        try:
            _ = iter(data)
        except TypeError:
            data = [data]
        self._spi_write(device, EL133UF1._SPI_DATA, data)

    def _sleep(self):
        self._send_command(_SpiDevice.BOTH, EL133UF1._DSLP, 0xA5)

def init_display(_) -> Display:
    return EL133UF1()
