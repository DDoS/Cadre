# Modified from:
# https://github.com/pimoroni/inky/blob/main/library/inky/inky_ac073tc1a.py

# MIT License
#
# Copyright (c) 2018 Pimoroni Ltd.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
import warnings
import numpy
import numpy.typing

import RPi.GPIO as GPIO
import spidev

from display_protocol import Display


class GDEP073E01:
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

    WIDTH = 800
    HEIGHT = 480

    _PSR = 0x00
    _PWR = 0x01
    _POF = 0x02
    _POFS = 0x03
    _PON = 0x04
    _BTST1 = 0x05
    _BTST2 = 0x06
    _BTST3 = 0x08
    _DTM = 0x10
    _DRF = 0x12
    _IPC = 0x13
    _PLL = 0x30
    _TSE = 0x41
    _CDI = 0x50
    _TCON = 0x60
    _TRES = 0x61
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

    def __init__(self, *, cs_channel=0, dc_pin=DC_PIN, reset_pin=RESET_PIN, busy_pin=BUSY_PIN):
        """
        :param cs_channel: channel for SPI communication
        :param dc_pin: data/command pin
        :param reset_pin: device reset pin
        :param busy_pin: device busy/wait pin
        """
        self._spi_bus = None
        self._gpio = None

        self.buf = numpy.zeros((GDEP073E01.HEIGHT, GDEP073E01.WIDTH), dtype=numpy.uint8)

        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.busy_pin = busy_pin
        self.cs_channel = cs_channel

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

        self._update(buf.astype('uint8').tolist())

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
            self._spi_bus.open(0, self.cs_channel)
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
        self._send_command(GDEP073E01._CMDH, [0x49, 0x55, 0x20, 0x08, 0x09, 0x18])
        self._send_command(GDEP073E01._PWR, [0x3F, 0x00, 0x32, 0x2A, 0x0E, 0x2A])
        self._send_command(GDEP073E01._PSR, [0x5F, 0x69])
        self._send_command(GDEP073E01._POFS, [0x00, 0x54, 0x00, 0x44])
        self._send_command(GDEP073E01._BTST1, [0x40, 0x1F, 0x1F, 0x2C])
        self._send_command(GDEP073E01._BTST2, [0x6F, 0x1F, 0x16, 0x25])
        self._send_command(GDEP073E01._BTST3, [0x6F, 0x1F, 0x1F, 0x22])
        self._send_command(GDEP073E01._IPC, [0x00, 0x04])
        self._send_command(GDEP073E01._PLL, 0x02)
        self._send_command(GDEP073E01._TSE, 0x00)
        self._send_command(GDEP073E01._CDI, 0x3F)
        self._send_command(GDEP073E01._TCON, [0x02, 0x00])
        self._send_command(GDEP073E01._TRES, [0x03, 0x20, 0x01, 0xE0])
        self._send_command(GDEP073E01._VDCS, 0x1E)
        self._send_command(GDEP073E01._T_VDCS, 0x01)
        self._send_command(GDEP073E01._AGID, 0x00)
        self._send_command(GDEP073E01._PWS, 0x2F)
        self._send_command(GDEP073E01._CCSET, 0x00)
        self._send_command(GDEP073E01._TSSET, 0x00)

    def _busy_wait(self, timeout=40):
        # If the busy_pin is *high* (pulled up by host)
        # then assume we're not getting a signal from display
        # and wait the timeout period to be safe.
        if self._gpio.input(self.busy_pin):
            warnings.warn("Busy Wait: Held high. Waiting for {:0.2f}s".format(timeout))
            time.sleep(timeout)
            return

        # If the busy_pin is *low* (pulled down by display)
        # then wait for it to high.
        t_start = time.time()
        while not self._gpio.input(self.busy_pin):
            time.sleep(0.01)
            if time.time() - t_start >= timeout:
                warnings.warn("Busy Wait: Timed out after {:0.2f}s".format(time.time() - t_start))
                return

    def _update(self, buf):
        self._setup()

        self._send_command(GDEP073E01._DTM, buf)

        self._send_command(GDEP073E01._PON)
        self._busy_wait(0.4)

        self._send_command(GDEP073E01._DRF, 0x00)
        self._busy_wait(45.0)  # 41 seconds in testing

        self._send_command(GDEP073E01._POF, 0x00)
        self._busy_wait(0.4)

    def _spi_write(self, dc, values):
        self._gpio.output(self.dc_pin, dc)

        if type(values) is str:
            values = [ord(c) for c in values]

        for byte_value in values:
            self._spi_bus.xfer([byte_value])

    def _send_command(self, command, data=None):
        self._spi_write(GDEP073E01._SPI_COMMAND, [command])
        if data is not None:
            self._send_data(data)

    def _send_data(self, data):
        try:
            _ = iter(data)
        except TypeError:
            data = [data]
        self._spi_write(GDEP073E01._SPI_DATA, data)


def init_display(_) -> Display:
    return GDEP073E01()
