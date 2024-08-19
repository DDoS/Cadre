import time

import numpy
import numpy.typing

from display_protocol import Display


class Simulated:
    def __init__(self):
        self.buf = numpy.zeros((480, 800), numpy.uint8)

    def show(self):
        time.sleep(5)


def init_display() -> Display:
    return Simulated()
