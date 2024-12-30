# Modified from:
# https://github.com/pimoroni/inky/blob/main/library/inky/inky_ac073tc1a.py

import time
import warnings
import numpy
import numpy.typing

import RPi.GPIO as GPIO
import spidev

from display_protocol import Display


class AC073TC1:
    DC_PIN = 22
    RESET_PIN = 27
    BUSY_PIN = 17

    BLACK = 0
    WHITE = 1
    GREEN = 2
    BLUE = 3
    RED = 4
    YELLOW = 5
    ORANGE = 6

    WIDTH = 800
    HEIGHT = 480

    _PSR = 0x00
    _PWR = 0x01
    _POF = 0x02
    _POFS = 0x03
    _PON = 0x04
    _BTST1 = 0x05
    _BTST2 = 0x06
    _DSLP = 0x07
    _BTST3 = 0x08
    _DTM = 0x10
    _DSP = 0x11
    _DRF = 0x12
    _IPC = 0x13
    _PLL = 0x30
    _TSC = 0x40
    _TSE = 0x41
    _TSW = 0x42
    _TSR = 0x43
    _CDI = 0x50
    _LPD = 0x51
    _TCON = 0x60
    _TRES = 0x61
    _DAM = 0x65
    _REV = 0x70
    _FLG = 0x71
    _AMV = 0x80
    _VV = 0x81
    _VDCS = 0x82
    _T_VDCS = 0x84
    _AGID = 0x86
    _CMDH = 0xAA
    _CCSET = 0xE0
    _PWS = 0xE3
    _TSSET = 0xE6

    _SPI_COMMAND = 0
    _SPI_DATA = 1

    buf: numpy.typing.NDArray[numpy.uint8]

    def __init__(self, *, spi_bus=0, dc_pin=DC_PIN, reset_pin=RESET_PIN, busy_pin=BUSY_PIN):
        """
        :param spi_bus: SPI bus for communication
        :param dc_pin: data/command pin
        :param reset_pin: device reset pin
        :param busy_pin: device busy/wait pin
        """
        self._gpio = None
        self._spi_bus = None

        self.buf = numpy.zeros((AC073TC1.HEIGHT, AC073TC1.WIDTH), dtype=numpy.uint8)

        self.spi_bus = spi_bus
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.busy_pin = busy_pin

    def show(self):
        """
        Show buffer on display.
        """
        buf = self.buf.flatten()

        # Remove invalid colors
        buf = numpy.clip(buf, 0, 6)

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

        if self._spi_bus is None:
            self._spi_bus = spidev.SpiDev()
            self._spi_bus.open(self.spi_bus, 0)
            self._spi_bus.max_speed_hz = 5000000

        self._gpio.output(self.reset_pin, self._gpio.LOW)
        time.sleep(0.1)
        self._gpio.output(self.reset_pin, self._gpio.HIGH)
        time.sleep(0.1)

        self._gpio.output(self.reset_pin, self._gpio.LOW)
        time.sleep(0.1)
        self._gpio.output(self.reset_pin, self._gpio.HIGH)

        self._busy_wait(1.0)

        # Sending init commands to display
        self._send_command(AC073TC1._CMDH, [0x49, 0x55, 0x20, 0x08, 0x09, 0x18])
        self._send_command(AC073TC1._PWR, [0x3F, 0x00, 0x32, 0x2A, 0x0E, 0x2A])
        self._send_command(AC073TC1._PSR, [0x5F, 0x69])
        self._send_command(AC073TC1._POFS, [0x00, 0x54, 0x00, 0x44])
        self._send_command(AC073TC1._BTST1, [0x40, 0x1F, 0x1F, 0x2C])
        self._send_command(AC073TC1._BTST2, [0x6F, 0x1F, 0x16, 0x25])
        self._send_command(AC073TC1._BTST3, [0x6F, 0x1F, 0x1F, 0x22])
        self._send_command(AC073TC1._IPC, [0x00, 0x04])
        self._send_command(AC073TC1._PLL, 0x02)
        self._send_command(AC073TC1._TSE, 0x00)
        self._send_command(AC073TC1._CDI, 0x3F)
        self._send_command(AC073TC1._TCON, [0x02, 0x00])
        self._send_command(AC073TC1._TRES, [0x03, 0x20, 0x01, 0xE0])
        self._send_command(AC073TC1._VDCS, 0x1E)
        self._send_command(AC073TC1._T_VDCS, 0x00)
        self._send_command(AC073TC1._AGID, 0x00)
        self._send_command(AC073TC1._PWS, 0x2F)
        self._send_command(AC073TC1._CCSET, 0x00)
        self._send_command(AC073TC1._TSSET, 0x00)

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

    def _update(self, buf):
        self._setup()

        self._send_command(AC073TC1._DTM, buf)

        self._send_command(AC073TC1._PON)
        self._busy_wait(0.4)

        self._send_command(AC073TC1._DRF, 0x00)
        self._busy_wait(45.0)

        self._send_command(AC073TC1._POF, 0x00)
        self._busy_wait(0.4)

        self._sleep()

    def _spi_write(self, dc, data):
        self._gpio.output(self.dc_pin, dc)
        self._spi_bus.writebytes2(data)

    def _send_command(self, command, data=None):
        self._spi_write(AC073TC1._SPI_COMMAND, [command])
        if data is not None:
            self._send_data(data)

    def _send_data(self, data):
        try:
            _ = iter(data)
        except TypeError:
            data = [data]
        self._spi_write(AC073TC1._SPI_DATA, data)

    def _sleep(self):
        self._send_command(AC073TC1._DSLP, 0xA5)


def init_display(_) -> Display:
    return AC073TC1()
