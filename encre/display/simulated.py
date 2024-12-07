import time
from typing import Any

import numpy
import numpy.typing

from display_protocol import Display


class Simulated:
    def __init__(self, config: dict[str, Any]):
        size = (config.get('height', 480), config.get('width', 800))
        self.buf = numpy.zeros(size, numpy.uint8)
        self._show_delay: float = config.get('delay', 5)

    def show(self):
        time.sleep(self._show_delay)


def init_display(config: dict[str, Any]) -> Display:
    return Simulated(config)
